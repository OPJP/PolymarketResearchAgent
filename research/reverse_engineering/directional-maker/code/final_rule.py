"""Frozen rule for the directional-maker cluster (bosona, almach, mo-money), BTC 5m Up/Down. Iteration 4 rule R3.

R3 = R2 (iteration 2; archived unchanged in final_rule_r2.py) with two changes, both chosen on the iteration-4
VALIDATE (2026-10-27..30, the second half of the released lot):
* the presence models are refitted on the expanded BUILD (2026-10-09..26: old BUILD + old VALIDATE + the lot's first
  half) with the same LightGBM parameters (code4/train6.py, code4/train4.py);
* the operator's clock schedule is an input: UTC hour, weekday and the US-session flag (weekday 12:00-21:00 UTC), the
  boundary at which the cluster's order size switches (iteration-4 calldata finding).
Everything else (tape hygiene, features, side, price, selection models and thresholds) is R2's.

* Tape hygiene: every data-api taker print in a transaction where a cluster wallet traded (maker or taker) is removed
  before any feature is computed.
* Presence: P(cluster gets >= 1 maker BUY fill on side s in the 10-s bin [t, t+10)), t in [0, 300) s
  = presence3_rule.txt on features published by t (features2.build_panel + clock): time, side, clean-tape activity,
  Binance 1-s fair value of the TWAP-60 settlement, z, returns, realized vol, edge = fair - last clean print, window
  path features, previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag. No own-state.
  Baseline: presence3_activity.txt (market activity only, same BUILD). Own-inventory variant: presence3_own.txt.
* Side (bins where it fills exactly one side): the side with the higher predicted presence.
* Price: last clean taker print on s strictly before the fill second, minus 0.01, rounded to 0.01.
* Selection: R2's selection2_all.txt / THETA_SEL (unchanged).
* Per-window rule PnL: sum over bins and sides of P(fill) * (payout_s - rule price).

evaluate(start_ts, end_ts, intervals=None) loads [start_ts, end_ts) through the polyrea adapters (Gamma windows,
data-api taker tapes [start-120, end) and the three wallets' activity, Binance 1-s archive), applies the frozen
models and returns presence / side / price / PnL / selection metrics with the market-activity-only baselines, pooled
and per wallet. With intervals (list of [a, b) pairs) only windows starting in them count. Nothing is fitted here.
local=True (development only) reads cached day files when they exist. The rule reads no live recording;
ALLOW_SEALED is kept for the examiner's driver.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from features2 import Spot, build_panel, clean_tape  # noqa: E402
from train2 import SETS  # noqa: E402

ALLOW_SEALED = False             # only the examiner's driver sets True (no live input is read by R3)
MODEL = "rule"                   # presence3_rule.txt: R2 features + clock, refit on BUILD 2026-10-09..26 (iteration 4)
BASELINE = "activity"            # presence3_activity.txt: market-activity-only (co-occurrence) baseline, same BUILD
OWN_MODEL = "own"                # presence3_own.txt: reported separately (own inventory)
CLOCK = ["hour_utc", "dow", "us_session"]
FEATS = {"rule": SETS["all_path_xwin"] + CLOCK, "activity": SETS["activity"],
         "own": SETS["all_path_xwin"] + CLOCK + ["inv_s", "inv_o"]}
THETA_SEL = {"all": 0.01698130336758783, "activity": 0.01736697994132774}  # BUILD top-15% score thresholds (sel2.py fit)
PRICE_OFFSET = 0.01
PRE = 120
SEL_NEG_FRAC = 0.10
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
CACHE = ROOT / ".cache/re/directional-maker"


def _windows(start_ts: int, end_ts: int) -> pd.DataFrame:
    from polyrea.analysis.updown import windows_from_markets
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    ws = [x for x in windows_from_markets(fetch_windows(window_slugs("btc", "5m", start_ts, end_ts)))
          if start_ts <= x.start_ts and x.end_ts <= end_ts]
    return pd.DataFrame([{"cid": x.condition_id, "start_ts": x.start_ts, "end_ts": x.end_ts, "up_token": x.up_token,
                          "down_token": x.down_token, "up_payout": x.up_payout} for x in ws]).sort_values("start_ts").reset_index(drop=True)


def _txint(x: pd.Series) -> pd.Series:
    """Compact transaction key (first 60 bits of the hash) to keep a week of tapes under ~0.5 GB."""
    def one(h):
        try:
            return int(h, 16)
        except (TypeError, ValueError):
            return 0
    return x.astype(str).str.slice(2, 17).map(one).astype(np.int64)


def _compact(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["tx"] = _txint(t["tx"])
    for c in ("cid", "asset", "wallet", "side"):
        t[c] = t[c].astype(str).astype("category")
    t["price"] = t["price"].astype(np.float32)
    t["size"] = t["size"].astype(np.float32)
    return t


def _tapes(w: pd.DataFrame, pm, end_ts: int, local: bool) -> pd.DataFrame:
    from polyrea.adapters.http import HttpError
    from polyrea.analysis.updown import snap_price
    out, have = [], set()
    if local:
        for d in sorted(set(w["start_ts"] // 86400 * 86400)):
            f = CACHE / f"taker5m_day_{d}.parquet"
            if f.exists():
                t = pd.read_parquet(f)
                t = t[t["cid"].isin(set(w["cid"])) & (t["ts"] < end_ts)]
                out.append(_compact(t))
                have |= set(t["cid"])
    rows = []
    for win in w.itertuples(index=False):
        if win.cid in have:
            continue
        try:
            rs, _, _ = pm.market_trades(win.cid, start=int(win.start_ts) - PRE, end=min(int(win.end_ts), end_ts - 1), taker_only=True)
        except HttpError:
            continue
        for r in rs:
            if int(r["timestamp"]) < end_ts:
                rows.append((win.cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                             float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
    out.append(_compact(pd.DataFrame(rows, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])))
    tk = pd.concat(out, ignore_index=True)
    for c in ("cid", "asset", "wallet", "side"):
        tk[c] = tk[c].astype(str).astype("category")
    return tk


def _cluster_trades(start_ts: int, end_ts: int, pm, local: bool) -> pd.DataFrame:
    rows = []
    for addr, name in CLUSTER.items():
        f = CACHE / f"activity_{name}.parquet"
        if local and f.exists():
            a = pd.read_parquet(f)
            a = a[(a["type"] == "TRADE") & (a["timestamp"] >= start_ts) & (a["timestamp"] < end_ts)]
            recs = a.rename(columns={"transactionHash": "tx", "asset": "token_id", "timestamp": "ts", "size": "shares",
                                     "conditionId": "cid"}).to_dict("records")
        else:
            act, _, _ = pm.activity(addr, start=start_ts, end=end_ts - 1)
            recs = [{"tx": r.get("transactionHash"), "token_id": r.get("asset"), "ts": r.get("timestamp"), "side": r.get("side"),
                     "price": r.get("price"), "shares": r.get("size"), "cid": r.get("conditionId")}
                    for r in act if r.get("type") == "TRADE" and start_ts <= int(r["timestamp"]) < end_ts]
        for r in recs:
            rows.append({"wallet": addr, "tx": r["tx"], "token_id": str(r["token_id"]), "ts": int(r["ts"]), "side": r["side"],
                         "price": float(r["price"]), "shares": float(r["shares"]), "cid": r["cid"]})
    ct = pd.DataFrame(rows, columns=["wallet", "tx", "token_id", "ts", "side", "price", "shares", "cid"])
    ct["tx"] = _txint(ct["tx"])
    return ct


def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    ok = np.isfinite(s)
    return float(roc_auc_score(y[ok], np.asarray(s)[ok])) if 0 < y[ok].sum() < ok.sum() else float("nan")


def _add_clock(panel: pd.DataFrame) -> pd.DataFrame:
    t = pd.to_datetime(panel["start_ts"], unit="s")
    panel["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32).to_numpy()
    panel["dow"] = t.dt.day_of_week.astype(np.int8).to_numpy()
    panel["us_session"] = ((panel["dow"] < 5) & (panel["hour_utc"] >= 12) & (panel["hour_utc"] < 21)).astype(np.int8)
    return panel


def _wallet_labels(panel: pd.DataFrame, w: pd.DataFrame, mk: pd.DataFrame, wallet: str) -> np.ndarray:
    """y for one wallet: >= 1 maker BUY fill of that wallet on the bin's side in [t, t+10)."""
    side_of = {**{t: (c, 1, s) for t, c, s in zip(w["up_token"], w["cid"], w["start_ts"])},
               **{t: (c, 0, s) for t, c, s in zip(w["down_token"], w["cid"], w["start_ts"])}}
    m = mk[mk["wallet"] == wallet]
    keys = set()
    for tok, ts in zip(m["token_id"], m["ts"]):
        v = side_of.get(tok)
        if v is None:
            continue
        rel = int((ts - v[2]) // 10 * 10)
        if 0 <= rel < 300:
            keys.add((v[0], v[1], rel))
    return np.array([(c, sd, r) in keys for c, sd, r in zip(panel["cid"], panel["side_up"], panel["rel"])], dtype=np.int8)


def evaluate(start_ts: int, end_ts: int, intervals=None, local: bool = False, n_perm: int = 99,
             cache_only: bool = False) -> dict:
    import lightgbm as lgb
    from scipy import stats
    if cache_only:
        os.environ["POLYREA_OFFLINE"] = "1"
    from polyrea.adapters.polymarket import PolymarketData
    from polyrea.adapters.spot import binance_seconds
    import sel2
    from train2 import side_metrics
    pm = PolymarketData()
    w = _windows(start_ts, end_ts)
    if intervals:
        keep = np.zeros(len(w), dtype=bool)
        for a_, b_ in intervals:
            keep |= (w["start_ts"].to_numpy() >= a_) & (w["start_ts"].to_numpy() < b_)
        w = w[keep].reset_index(drop=True)
    tk = _tapes(w, pm, end_ts, local)
    spd = None
    if local and (CACHE / "spot_btc_1s.parquet").exists():
        spd = pd.read_parquet(CACHE / "spot_btc_1s.parquet")
        spd = spd[(spd["sec"] >= start_ts - 7200) & (spd["sec"] < end_ts)]
        sec, px = spd["sec"].to_numpy(), spd["px"].to_numpy()
    if spd is None or len(spd) == 0:
        rows, _ = binance_seconds("btc", start_ts - 7200, end_ts)
        a = np.asarray(rows)
        sec, px = a[:, 0].astype(np.int64), a[:, 1]
    sp = Spot(sec, px)
    ct = _cluster_trades(start_ts, end_ts, pm, local)
    toks = set(w["up_token"]) | set(w["down_token"])
    buys = ct[(ct["side"] == "BUY") & ct["token_id"].isin(toks)].copy()
    own_rows = tk[tk["wallet"].isin(set(CLUSTER))]
    taker_pairs = set(zip(own_rows["tx"], own_rows["wallet"].astype(str)))
    buys["role"] = ["taker" if (x, y) in taker_pairs else "maker" for x, y in zip(buys["tx"], buys["wallet"])]
    mk = buys[buys["role"] == "maker"]
    ctx, cw = set(ct["tx"]), set(CLUSTER)
    clean = clean_tape(tk, ctx, cw)
    panel = build_panel(w, sp, clean, mk)
    panel["inv_net"] = panel["inv_s"] - panel["inv_o"]
    res = {"period": [start_ts, end_ts], "windows": int(panel["cid"].nunique()), "bins": int(len(panel)),
           "cluster_maker_fills": int(len(mk)), "cluster_taker_fills": int((buys["role"] == "taker").sum()),
           "tape_rows": int(len(tk)), "tape_rows_removed_cluster_tx": int(len(tk) - len(clean))}
    panel = _add_clock(panel)
    for nm in (MODEL, BASELINE, OWN_MODEL):
        m = lgb.Booster(model_file=str(HERE / f"presence3_{nm}.txt"))
        panel["p_" + nm] = m.predict(panel[FEATS[nm]])
    act = panel.groupby("cid")["y"].transform("max") > 0
    res["presence"] = {"auc": _auc(panel["y"], panel["p_" + MODEL]), "auc_activity_baseline": _auc(panel["y"], panel["p_" + BASELINE]),
                       "auc_with_own_inventory": _auc(panel["y"], panel["p_" + OWN_MODEL]),
                       "auc_within_active_windows": _auc(panel.loc[act, "y"], panel.loc[act, "p_" + MODEL]),
                       "pos_rate": float(panel["y"].mean()), "active_window_share": float(panel.groupby("cid")["y"].max().mean())}
    res["presence"]["gain_over_baseline"] = res["presence"]["auc"] - res["presence"]["auc_activity_baseline"]
    res["side"] = side_metrics(panel, "p_" + MODEL)
    res["side_activity_baseline"] = side_metrics(panel, "p_" + BASELINE)["acc"]
    per_wallet = {}
    for addr, name in CLUSTER.items():
        yw = _wallet_labels(panel, w, mk, addr)
        pw = panel.assign(y=yw)
        per_wallet[name] = {"fills": int((mk["wallet"] == addr).sum()),
                            "presence_auc": _auc(yw, panel["p_" + MODEL].to_numpy()),
                            "presence_auc_activity_baseline": _auc(yw, panel["p_" + BASELINE].to_numpy()),
                            "side": side_metrics(pw, "p_" + MODEL)["acc"] if yw.sum() else float("nan")}
    # price: last clean print on s strictly before the fill second - 0.01
    upset = set(w["up_token"])
    tok2cid = {**dict(zip(w["up_token"], w["cid"])), **dict(zip(w["down_token"], w["cid"]))}
    c2 = clean.merge(w[["cid", "up_token"]], on="cid")
    c2["up_px"] = np.where(c2["asset"] == c2["up_token"], c2["price"], 1 - c2["price"])
    by = {c: (g["ts"].to_numpy(), g["up_px"].to_numpy()) for c, g in c2.sort_values("ts", kind="stable").groupby("cid")}
    pred, actual, pw_wal = [], [], []
    for r in mk.itertuples(index=False):
        cid = tok2cid.get(r.token_id)
        if cid not in by:
            continue
        ts_, px_ = by[cid]
        i = np.searchsorted(ts_, r.ts, side="left") - 1
        if i < 0:
            continue
        ls = px_[i] if r.token_id in upset else 1 - px_[i]
        pred.append(round(ls - PRICE_OFFSET, 2))
        actual.append(r.price)
        pw_wal.append(r.wallet)
    e = np.abs(np.asarray(actual) - np.asarray(pred))
    res["price"] = {"n_fills": int(len(e)), "exact": float(np.mean(e < 0.0005)) if len(e) else float("nan"),
                    "within_0.01": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}
    pw_wal = np.asarray(pw_wal)
    for addr, name in CLUSTER.items():
        k = pw_wal == addr
        per_wallet[name]["price_within_0.01"] = float(np.mean(e[k] <= 0.0105)) if k.any() else float("nan")
    # PnL per window: wallet maker fills vs the rule's expected PnL
    pay = dict(zip(w["cid"], w["up_payout"]))
    mk2 = mk.assign(c=[tok2cid.get(t) for t in mk["token_id"]], up=mk["token_id"].isin(upset))
    mk2["won"] = [(pay.get(c) if u else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, u in zip(mk2["c"], mk2["up"])]
    wal = ((mk2["won"] - mk2["price"]) * mk2["shares"]).groupby(mk2["c"]).sum()
    pr = panel.dropna(subset=["won_s"]).copy()
    pr["rule_pnl"] = pr["p_" + MODEL] * (pr["won_s"] - (pr["last_s"].fillna(0.5) - PRICE_OFFSET).round(2))
    j = pd.concat([wal.rename("wallet"), pr.groupby("cid")["rule_pnl"].sum().rename("rule")], axis=1).dropna()
    usd = float((mk2["price"] * mk2["shares"]).sum())
    rule_w = pr.groupby("cid")["rule_pnl"].sum()
    for addr, name in CLUSTER.items():
        m2 = mk2[mk2["wallet"] == addr]
        ww = ((m2["won"] - m2["price"]) * m2["shares"]).groupby(m2["c"]).sum()
        jj = pd.concat([ww.rename("wallet"), rule_w.rename("rule")], axis=1).dropna()
        per_wallet[name]["pnl_pearson"] = float(jj.corr().iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_spearman"] = float(jj.corr(method="spearman").iloc[0, 1]) if len(jj) > 2 else float("nan")
        per_wallet[name]["pnl_windows"] = int(len(jj))
    res["per_wallet"] = per_wallet
    res["pnl"] = {"windows": int(len(j)), "pearson": float(j.corr().iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "spearman": float(j.corr(method="spearman").iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "wallet_maker_return_on_usd": float(((mk2["won"] - mk2["price"]) * mk2["shares"]).sum() / usd) if usd else float("nan")}
    del c2, by, clean
    # selection over in-window taker prints, per UTC day block, with the rotation null (scores aligned to rows)
    models = {nm: lgb.Booster(model_file=str(HERE / f"selection2_{nm}.txt")) for nm in ("all", "activity")}
    mk_tx = set(mk["tx"])
    rng = np.random.default_rng(12)
    te_all, S = [], []
    for d in sorted(set(w["start_ts"] // 86400 * 86400)):
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        if len(wd) < 4:
            continue
        te, pan_d, wdd = sel2.day_prints(d, w, sp, mk_tx, cw, SEL_NEG_FRAC, rng, tk=tk[tk["cid"].isin(set(wd["cid"]))],
                                         pan=panel[panel["cid"].isin(set(wd["cid"]))])
        if len(te) == 0:
            continue
        te = te.reset_index(drop=True)
        te["rid"] = np.arange(len(te))
        te["s_all"] = models["all"].predict(te[sel2.F_ALL]).astype(np.float32)
        te["s_activity"] = models["activity"].predict(te[sel2.F_ACT]).astype(np.float32)
        te["wkey"] = (te["day"] // 86400 * 1000 + te["widx"]).astype(np.int64)
        prng = np.random.default_rng(500 + d % 1000)
        sd = np.full((n_perm, len(te)), np.nan, np.float32)
        for i in range(n_perm):
            r = sel2.rotated(te, pan_d, wdd, sp, int(prng.integers(1, len(wdd))))
            sd[i, r["rid"].to_numpy()] = models["all"].predict(r[sel2.F_ALL]).astype(np.float32)
        S.append(sd)
        te_all.append(te[["wkey", "y", "wt", "q", "rel_p", "side_up", "s_all", "s_activity"]].rename(columns={"wkey": "cid"}))
        del te, pan_d, r
    sel = {}
    if te_all:
        te = pd.concat(te_all, ignore_index=True)
        S = np.concatenate(S, axis=1)
        gg, gw = sel2.strata(te, 50, 40, False), sel2.strata(te, 10, 10, True)
        y, wt = te["y"].to_numpy(), te["wt"].to_numpy()
        base = float(y.sum() / wt.sum())
        for nm in ("all", "activity"):
            s = te["s_" + nm].to_numpy()
            flag = s >= THETA_SEL[nm]
            sel[nm] = {"auc": sel2.wauc(s, y, wt), "auc_strat_global": sel2.wauc(s, y, wt, gg),
                       "auc_strat_window": sel2.wauc(s, y, wt, gw), "recall_at_theta": float(flag[y == 1].mean()),
                       "lift_at_theta": float(np.sum(flag & (y == 1)) / np.sum(wt * flag) / base) if flag.any() else float("nan")}
        ng, nw = [], []
        for i in range(n_perm):
            ok = np.isfinite(S[i])
            ng.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gg[ok]))
            nw.append(sel2.wauc(S[i][ok], y[ok], wt[ok], gw[ok]))
        if n_perm:
            ng, nw = np.array(ng), np.array(nw)
            a = sel["all"]
            a["rotation_null"] = {"global_mean": float(ng.mean()), "global_max": float(ng.max()),
                                  "global_sd": float(ng.std(ddof=1)) if n_perm > 1 else float("nan"),
                                  "window_mean": float(nw.mean()), "window_max": float(nw.max()),
                                  "window_sd": float(nw.std(ddof=1)) if n_perm > 1 else float("nan"), "n_perm": n_perm}
            nn = a["rotation_null"]
            a["z_vs_null_global"] = (a["auc_strat_global"] - nn["global_mean"]) / nn["global_sd"] if nn["global_sd"] > 0 else float("nan")
            a["z_vs_null_window"] = (a["auc_strat_window"] - nn["window_mean"]) / nn["window_sd"] if nn["window_sd"] > 0 else float("nan")
            a["p_global"] = float((1 + (ng >= a["auc_strat_global"]).sum()) / (n_perm + 1))
            a["p_window"] = float((1 + (nw >= a["auc_strat_window"]).sum()) / (n_perm + 1))
            a["perm_p"] = max(a["p_global"], a["p_window"])
            a["criterion"] = {"auc_ge_0.80": a["auc"] >= 0.80, "recall_ge_0.50": a["recall_at_theta"] >= 0.5,
                              "lift_ge_3": a["lift_at_theta"] >= 3, "p_lt_0.01": a["perm_p"] < 0.01}
        sel["prints_sampled"] = int(len(te))
        sel["wallet_prints"] = int(y.sum())
    res["selection"] = sel
    res["note"] = ("selection population = in-window taker prints except the cluster's own taker prints; label = print's "
                   "transaction holds a cluster maker fill; negatives subsampled 10% (weights 10), AUCs unbiased; rotation null: "
                   "each day's windows take the spot path of the window k places later (bin-level spot columns and print fair recomputed)")
    del stats
    return res


if __name__ == "__main__":
    import json
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(a, b, local="local" in sys.argv[3:], cache_only="cache" in sys.argv[3:]), indent=1, default=str))
