"""Iteration 7 (X9 / X39 on/off; own state, reported separately): is the BTC 5m switch-off a stop-loss?

Live trigger: on 2026-10-31 the three wallets' last BTC 5m trades came at 16:53:33-54 UTC, inside window 16:50 (which
lost $1,565 of $2,426 bought), at the day's cumulative low (-$2,424; $3,062 below the 15:40 peak); BTC 15m continued.
Historical test (BUILD 10-09..26 incl. STUDY case by case; VALIDATE 10-27..30 aggregate): per BTC 5m window, the
cluster's cash PnL on its trades held to resolution; off-runs = >= 12 consecutive windows without a cluster trade;
switch-off window = the last active window before an off-run. Compare its PnL, the day's running PnL and the drawdown
from the running 24-h peak with all active windows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / ".cache/re/directional-maker"
OUT = ROOT / "research/reverse_engineering/directional-maker/results"
V0 = 1793059200


def main():
    A = []
    for n in ("almach", "bosona", "momoney"):
        a = pd.read_parquet(C / f"activity_{n}.parquet")
        b = pd.read_parquet(C / f"exam/activity_{n}.parquet")
        d = pd.concat([a, b]).drop_duplicates(["transactionHash", "asset", "side", "size", "price"])
        d["wal"] = n
        A.append(d)
    d = pd.concat(A)
    d = d[(d["type"] == "TRADE") & d["slug"].astype(str).str.startswith("btc-updown-5m")].copy()
    d["st"] = d["slug"].str.rsplit("-", n=1).str[1].astype(int)
    d = d[(d.st >= 1791504000) & (d.st < 1793404800)]
    w1 = pd.read_parquet(C / "windows_5m.parquet")[["start_ts", "up_token", "up_payout"]]
    pt = pd.read_parquet(C / "cl/ptb_lot.parquet")
    w2 = pt.assign(up_payout=(pt["final"] >= pt["ptb"]).astype(float))[["start_ts", "up_payout"]]
    pay = dict(zip(w1.start_ts, w1.up_payout))
    pay.update(dict(zip(w2.start_ts, w2.up_payout)))
    d["upq"] = d["outcome"].astype(str).str.lower().eq("up")
    d["won"] = [(pay.get(s, np.nan) if u else 1 - pay.get(s, np.nan)) for s, u in zip(d.st, d.upq)]
    sg = np.where(d["side"] == "BUY", 1.0, -1.0)
    d["pnl"] = sg * (d["won"] - d["price"].astype(float)) * d["size"].astype(float)
    d["usd"] = np.where(d["side"] == "BUY", d["price"].astype(float) * d["size"].astype(float), 0.0)
    g = d.groupby("st").agg(pnl=("pnl", "sum"), usd=("usd", "sum"), n=("pnl", "size"))
    allw = pd.DataFrame(index=np.arange(1791504000, 1793404800, 300))
    allw = allw.join(g).fillna({"n": 0, "pnl": 0.0, "usd": 0.0})
    allw["active"] = allw.n > 0
    # running PnL: cumulative over the trailing 24 h (288 windows) and the drawdown from its running max
    allw["cum"] = allw.pnl.cumsum()
    allw["cum24"] = allw.pnl.rolling(288, min_periods=1).sum()
    allw["peak24"] = allw.cum.rolling(288, min_periods=1).max()
    allw["dd24"] = allw.peak24 - allw.cum
    allw["day"] = allw.index // 86400 * 86400
    allw["daycum"] = allw.groupby("day").pnl.cumsum()
    allw["daydd"] = allw.groupby("day").cum.cummax() - allw.cum
    # off-runs
    act = allw.active.to_numpy()
    idx = allw.index.to_numpy()
    offs = []
    i = 0
    while i < len(act):
        if not act[i]:
            j = i
            while j < len(act) and not act[j]:
                j += 1
            if j - i >= 12 and i > 0 and act[i - 1]:
                offs.append((int(idx[i - 1]), int(j - i)))
            i = j
        else:
            i += 1
    A_ = allw[allw.active]
    rows = []
    for s, L in offs:
        r = allw.loc[s]
        prev = allw.loc[s - 300] if s - 300 in allw.index else None
        rows.append({"switch_window": s, "utc": pd.to_datetime(s, unit="s").strftime("%m-%d %H:%M"), "off_windows": L,
                     "pnl": round(float(r.pnl), 1), "usd": round(float(r.usd), 1),
                     "pnl_pct_rank": round(float((A_.pnl < r.pnl).mean()), 3),
                     "pnl2": round(float(r.pnl + (prev.pnl if prev is not None else 0)), 1),
                     "daycum": round(float(r.daycum), 1), "daydd": round(float(r.daydd), 1), "dd24": round(float(r.dd24), 1),
                     "dd24_pct_rank": round(float((A_.dd24 < r.dd24).mean()), 3), "valid": bool(s >= V0)})
    sw = pd.DataFrame(rows)
    res = {"n_switch_offs": int(len(sw)), "build": sw[~sw.valid].to_dict("records") if len(sw) else [],
           "validate_aggregate": {"n": int(sw.valid.sum()),
                                  "median_pnl_pct_rank": float(sw[sw.valid].pnl_pct_rank.median()) if sw.valid.any() else None,
                                  "median_dd24_pct_rank": float(sw[sw.valid].dd24_pct_rank.median()) if sw.valid.any() else None},
           "all_active_windows": {"pnl_q10_50_90": [round(float(x), 1) for x in A_.pnl.quantile([0.1, 0.5, 0.9])],
                                  "dd24_q50_90": [round(float(x), 1) for x in A_.dd24.quantile([0.5, 0.9])]}}
    # does a large window loss predict a switch-off right after it? (BUILD)
    B = A_[A_.index < V0].copy()
    sset = set(sw.switch_window)
    B["is_switch"] = [x in sset for x in B.index]
    for thr in (-500, -1000, -1500):
        m = B.pnl <= thr
        res[f"build_P_switch_given_pnl_le_{-thr}"] = [round(float(B[m].is_switch.mean()), 3) if m.any() else None, int(m.sum())]
    res["build_P_switch_overall"] = round(float(B.is_switch.mean()), 4)
    from sklearn.metrics import roc_auc_score
    if B.is_switch.sum() > 1:
        res["build_auc_switch_by_neg_pnl"] = float(roc_auc_score(B.is_switch, -B.pnl))
        res["build_auc_switch_by_dd24"] = float(roc_auc_score(B.is_switch, B.dd24))
        res["build_auc_switch_by_neg_daycum"] = float(roc_auc_score(B.is_switch, -B.daycum))
    OUT.joinpath("iter7_stoploss.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "build"}, indent=1, default=float))
    print(sw[~sw.valid].drop(columns=["valid"]).to_string(index=False))


if __name__ == "__main__":
    main()
