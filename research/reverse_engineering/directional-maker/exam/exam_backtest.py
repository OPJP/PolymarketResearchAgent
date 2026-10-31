"""Examiner: strict-fill backtest of the frozen rule R2 turned into an executable maker strategy.

R2 is a presence model plus a price rule; it has no quoting threshold, and its own "rule PnL" (sum of P(fill) x
(payout - price)) is an expectation, not a trade. The examiner fixes the executable translation BEFORE looking at any
holdout result (primary configuration P, everything else is a reported sensitivity):

  P: at every bin start t (t = start + 0, 10, ..., 290 s) and side s, if p_R2(t, s) >= THETA (the 85th percentile of
     p_R2 over all BUILD bins 2026-10-09..16, computed from the development panels; i.e. the BUILD top 15%, the same
     convention as THETA_SEL) and a last clean print on s exists, rest a BUY of SIZE = 20 shares on s at
     q = round(last clean print on s before t - 0.01, 2) (the rule's price), valid for 0.01 <= q <= 0.99.
     Latency L = 2 s: the order is live in (t + L, t + L + 10]. Block-time slack 2 s: a print stamped T is attributed
     to the order live at T - 2. Strict trade-through fills only: a taker SELL of s below q, or a taker BUY of the other
     outcome above 1 - q (complementary mint); fill = min(SIZE, through volume in the order's life). No taker fee, no
     maker rebate (0% tier). Settlement at the resolved payout.
  Sensitivities: THETA = BUILD top 5%, THETA = 0 (quote every bin), only the higher-p side per bin, L = 5 s,
  slack 0 (optimistic), at-touch fills (first in queue, optimistic bound), SIZE = 100.
Significance: HAC one-sided t-test of the per-window PnL over ALL windows (zero when no fill) and a stationary
bootstrap; also the per-day series.

python exam_backtest.py theta          THETA from BUILD panels (development data)  -> results/exam_theta.json
python exam_backtest.py run holdout    holdout days (exam panels + tapes)          -> results/exam_backtest_holdout.json
python exam_backtest.py run validate   VALIDATE days (development data, sanity)    -> results/exam_backtest_validate.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = HERE.parent / "code"
RES = HERE.parent / "results"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CODE))
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue  # noqa: E402
from train2 import SETS  # noqa: E402

DEV = ROOT / ".cache/re/directional-maker"
EX = DEV / "exam"
H = 1792713600
VAL0 = 1792108800
B0 = 1791504000
MODEL = "all_path_xwin"
CONFIGS = {
    "P_primary": dict(theta="q85", L=2, slack=2, at_touch=False, size=20, one_side=False),
    "theta_q95": dict(theta="q95", L=2, slack=2, at_touch=False, size=20, one_side=False),
    "theta_0_all_bins": dict(theta="zero", L=2, slack=2, at_touch=False, size=20, one_side=False),
    "higher_p_side_only": dict(theta="q85", L=2, slack=2, at_touch=False, size=20, one_side=True),
    "latency_5s": dict(theta="q85", L=5, slack=2, at_touch=False, size=20, one_side=False),
    "slack_0_optimistic": dict(theta="q85", L=2, slack=0, at_touch=False, size=20, one_side=False),
    "at_touch_optimistic": dict(theta="q85", L=2, slack=2, at_touch=True, size=20, one_side=False),
    "size_100": dict(theta="q85", L=2, slack=2, at_touch=False, size=100, one_side=False),
}


def theta() -> None:
    m = lgb.Booster(model_file=str(CODE / f"presence2_{MODEL}.txt"))
    ps = []
    for f in sorted(DEV.glob("panel2_day_*.parquet")):
        d = int(f.stem.split("_")[-1])
        if not (B0 <= d < VAL0):
            continue
        p = pd.read_parquet(f, columns=SETS[MODEL])
        ps.append(m.predict(p[SETS[MODEL]]).astype(np.float32))
    a = np.concatenate(ps)
    out = {"q85": float(np.quantile(a, 0.85)), "q95": float(np.quantile(a, 0.95)), "zero": 0.0, "n_build_bins": int(len(a)),
           "build_days": [d for d in range(B0, VAL0, 86400)]}
    (RES / "exam_theta.json").write_text(json.dumps(out, indent=1))
    print(out)


def day_inputs(mode: str, d: int, m=None):
    if mode == "holdout":
        p = pd.read_parquet(EX / f"panel_day_{d}.parquet", columns=["cid", "start_ts", "rel", "side_up", "last_s", "p_" + MODEL])
        tk = pd.read_parquet(EX / f"taker5m_day_{d}.parquet", columns=["cid", "ts", "side", "asset", "price", "size"])
    else:
        p = pd.read_parquet(DEV / f"panel2_day_{d}.parquet")
        p["p_" + MODEL] = m.predict(p[SETS[MODEL]]).astype(np.float32)
        p = p[["cid", "start_ts", "rel", "side_up", "last_s", "p_" + MODEL]]
        tk = pd.read_parquet(DEV / f"taker5m_day_{d}.parquet", columns=["cid", "ts", "side", "asset", "price", "size"])
    return p, tk


def simulate(p: pd.DataFrame, tk: pd.DataFrame, w: pd.DataFrame, th: float, L: int, slack: int, at_touch: bool, size: float,
             one_side: bool) -> pd.DataFrame:
    """Returns one row per filled order: cid, rel, side_up, q, shares, pnl."""
    p = p.copy()
    if one_side:
        mx = p.groupby(["cid", "rel"])["p_" + MODEL].transform("max")
        p = p[p["p_" + MODEL] >= mx]
        p = p[~p.duplicated(["cid", "rel"], keep="first")]
    p = p[(p["p_" + MODEL] >= th) & np.isfinite(p["last_s"])]
    p["q"] = np.round(p["last_s"].astype(float) - 0.01, 2)
    p = p[(p["q"] >= 0.01 - 1e-9) & (p["q"] <= 0.99 + 1e-9)]
    if p.empty:
        return pd.DataFrame(columns=["cid", "rel", "side_up", "q", "shares", "pnl"])
    wi = w.set_index("cid")
    tk = tk[tk["cid"].isin(set(p["cid"]))].merge(w[["cid", "start_ts", "up_token"]], on="cid")
    is_up = (tk["asset"].astype(str).to_numpy() == tk["up_token"].astype(str).to_numpy())
    side = tk["side"].astype(str).to_numpy()
    price = tk["price"].to_numpy().astype(float)
    tm = tk["ts"].to_numpy().astype(np.int64) - slack
    j = np.floor((tm - tk["start_ts"].to_numpy() - L - 1) / 10).astype(np.int64)
    okp = (j >= 0) & (j < 30)
    eps = -1e-9 if at_touch else 1e-9
    prints = pd.DataFrame({"cid": tk["cid"].to_numpy()[okp], "rel": (j[okp] * 10).astype(np.int64), "is_up": is_up[okp],
                           "sell": side[okp] == "SELL", "buy": side[okp] == "BUY", "price": price[okp],
                           "size": tk["size"].to_numpy().astype(float)[okp]})
    out = []
    for s in (1, 0):
        o = p[p["side_up"] == s][["cid", "rel", "q"]]
        if o.empty:
            continue
        x = prints.merge(o, on=["cid", "rel"], how="inner")
        su = s == 1
        through = ((x["is_up"] == su) & x["sell"] & (x["price"] < x["q"] - eps)) | ((x["is_up"] != su) & x["buy"] & (x["price"] > 1 - x["q"] + eps))
        v = x[through].groupby(["cid", "rel"])["size"].sum().rename("avail").reset_index()
        f = o.merge(v, on=["cid", "rel"], how="inner")
        f["shares"] = np.minimum(size, f["avail"])
        pay = wi.loc[f["cid"], "up_payout"].to_numpy().astype(float)
        f["payout"] = pay if su else 1 - pay
        f["pnl"] = f["shares"] * (f["payout"] - f["q"])
        f["side_up"] = s
        out.append(f[["cid", "rel", "side_up", "q", "shares", "pnl"]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["cid", "rel", "side_up", "q", "shares", "pnl"])


def summarize(f: pd.DataFrame, w: pd.DataFrame) -> dict:
    per_w = f.groupby("cid")["pnl"].sum().reindex(w["cid"], fill_value=0.0).to_numpy()
    usd = float((f["q"] * f["shares"]).sum()) if len(f) else 0.0
    t = hac_t_test(per_w)
    b = stationary_bootstrap_pvalue(per_w, n_boot=5000)
    day = (w.set_index("cid")["start_ts"] // 86400 * 86400)
    dser = pd.Series(per_w, index=w["cid"].to_numpy()).groupby(day.loc[w["cid"]].to_numpy()).sum()
    td = hac_t_test(dser.to_numpy()) if len(dser) >= 5 else None
    return {"fills": int(len(f)), "windows": int(len(w)), "windows_with_fills": int(f["cid"].nunique()) if len(f) else 0,
            "shares": float(f["shares"].sum()) if len(f) else 0.0, "usd_bought": usd, "pnl": float(per_w.sum()),
            "return_on_bought": float(per_w.sum() / usd) if usd else float("nan"),
            "fill_win_rate": float((f["pnl"] > 0).mean()) if len(f) else float("nan"),
            "per_window_t": t.statistic, "per_window_p_one_sided": t.p_value, "per_window_bootstrap_p": b.p_value,
            "daily_pnl": {str(pd.Timestamp(k, unit="s").date()): round(float(v), 2) for k, v in dser.items()},
            "daily_t": td.statistic if td else None, "daily_p": td.p_value if td else None}


def run(mode: str) -> None:
    th = json.loads((RES / "exam_theta.json").read_text())
    if mode == "holdout":
        w = pd.read_parquet(EX / "windows_5m.parquet")
        days = sorted(int(f.stem.split("_")[-1]) for f in EX.glob("panel_day_*.parquet"))
        m = None
    else:
        w = pd.read_parquet(DEV / "windows_5m.parquet")
        w = w[(w["start_ts"] >= VAL0) & (w["end_ts"] <= H)]
        days = list(range(VAL0, H, 86400))
        m = lgb.Booster(model_file=str(CODE / f"presence2_{MODEL}.txt"))
    w = w[w["up_payout"].notna()].reset_index(drop=True)
    fills = {k: [] for k in CONFIGS}
    wins = []
    for d in days:
        p, tk = day_inputs(mode, d, m)
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        wins.append(wd)
        p = p[p["cid"].isin(set(wd["cid"]))]
        for k, c in CONFIGS.items():
            fills[k].append(simulate(p, tk, wd, th[c["theta"]], c["L"], c["slack"], c["at_touch"], c["size"], c["one_side"]))
        print("day", d, {k: int(len(v[-1])) for k, v in fills.items()}, flush=True)
        del p, tk
    w = pd.concat(wins, ignore_index=True)
    out = {"mode": mode, "theta": th, "configs": CONFIGS, "results": {}}
    for k in CONFIGS:
        f = pd.concat(fills[k], ignore_index=True)
        out["results"][k] = summarize(f, w)
        if k == "P_primary":
            f.to_parquet(EX / f"bt_fills_{mode}.parquet", index=False)
        r = out["results"][k]
        print(k, r["fills"], round(r["usd_bought"]), round(r["pnl"], 1), round(r["return_on_bought"], 4), "p", round(r["per_window_p_one_sided"], 4), flush=True)
    if mode == "holdout":
        fwd0 = 1793318400  # as_of: days after it did not exist when the study was designed
        f = pd.concat(fills["P_primary"], ignore_index=True)
        wf = w[w["start_ts"] >= fwd0]
        out["forward_days_P_primary"] = summarize(f[f["cid"].isin(set(wf["cid"]))], wf.reset_index(drop=True)) if len(wf) else None
    (RES / f"exam_backtest_{mode}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    if sys.argv[1] == "theta":
        theta()
    else:
        run(sys.argv[2])
