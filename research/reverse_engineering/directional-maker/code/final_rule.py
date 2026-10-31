"""Frozen rule for the directional-maker cluster (bosona, almach, mo-money), BTC 5m Up/Down.

Iteration 1 rule (all parameters constant, model files frozen next to this file):

* Presence: P(the cluster gets >= 1 maker BUY fill on side s in the 10-s bin [t, t+10))
  = frozen LightGBM model `presence_model_<MODEL>.txt` on point-in-time features at t
  (time in window, Binance 1-s fair value of the TWAP-60 settlement, spot returns, realized vol,
  last taker print on s, fair - last print, taker hits on s/complement bids in the last 10/30/60 s,
  tape price changes). No own-state features.
* Side (given a fill in a bin on exactly one side): the side with the higher predicted presence.
* Price (given a fill at second T on side s): last taker print on s strictly before T, minus 0.01,
  rounded to the 0.01 grid.
* Per-window rule PnL: sum over bins and sides of P(fill) * (payout_s - rule price) per share.

evaluate(start_ts, end_ts) loads everything it needs for [start_ts, end_ts) through the polyrea
adapters (Gamma windows, data-api taker tapes and cluster activity, Binance 1-s archive), builds
the same features, applies the frozen model and returns the metrics. Nothing is fitted here.
Maker/taker role of a cluster fill: a fill is the cluster's taker fill when the data-api taker
tape lists the same transaction with the cluster wallet as the taker; otherwise it is a maker
fill (checked against on-chain OrderFilled roles on BUILD: see NOTES.md).
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

from features import BIN, Spot, build_panel  # noqa: E402

MODEL = "all"  # chosen on VALIDATE among {all, all_reg} (iteration 1)
BASELINE_MODEL = "activity"  # market-activity-only baseline, frozen too
F_TIME = ["rel", "side_up"]
F_SPOT = ["fair_s", "z_s", "sig", "r1", "r2", "r3", "r5", "r10", "r30", "r60"]
F_TAPE = ["last_s", "edge_s", "n_prints"] + [f"{a}{k}" for a in ("hit_s", "hit_o", "vol_s", "vol_o", "dpx_s") for k in (10, 30, 60)]
F_ACT = ["rel", "n_prints"] + [f"{a}{k}" for a in ("hit_s", "hit_o", "vol_s", "vol_o") for k in (10, 30, 60)]
FEATS = {"all": F_TIME + F_SPOT + F_TAPE, "all_reg": F_TIME + F_SPOT + F_TAPE, "activity": F_ACT, "activity_reg": F_ACT}
PRICE_OFFSET = 0.01
CLUSTER = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
           "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney"}
PRE = 900


def _windows(start_ts: int, end_ts: int) -> pd.DataFrame:
    from polyrea.analysis.updown import windows_from_markets
    from polyrea.workflows.updown_study import fetch_windows, window_slugs
    ms = fetch_windows(window_slugs("btc", "5m", start_ts, end_ts))
    ws = [w for w in windows_from_markets(ms) if start_ts <= w.start_ts and w.end_ts <= end_ts]
    return pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token,
                          "down_token": w.down_token, "up_payout": w.up_payout} for w in ws])


def _tapes(w: pd.DataFrame, pm) -> pd.DataFrame:
    from polyrea.adapters.http import HttpError
    from polyrea.analysis.updown import snap_price
    out = []
    for win in w.itertuples(index=False):
        try:
            rows, _, _ = pm.market_trades(win.cid, start=int(win.start_ts) - PRE, end=int(win.end_ts) - 1, taker_only=True)
        except HttpError:
            continue  # only in cache-only mode
        for r in rows:
            out.append((win.cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                        float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
    return pd.DataFrame(out, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])


def _cluster_maker_fills(start_ts: int, end_ts: int, w: pd.DataFrame, tk: pd.DataFrame, pm) -> pd.DataFrame:
    toks = set(w["up_token"]) | set(w["down_token"])
    rows = []
    for addr in CLUSTER:
        act, _, _ = pm.activity(addr, start=start_ts, end=end_ts - 1)
        for r in act:
            if r.get("type") == "TRADE" and str(r.get("asset")) in toks and r.get("side") == "BUY" and start_ts <= r["timestamp"] < end_ts:
                rows.append({"wallet": addr, "tx": r.get("transactionHash"), "token_id": str(r["asset"]), "ts": int(r["timestamp"]),
                             "price": float(r["price"]), "shares": float(r["size"]), "cid": r.get("conditionId")})
    f = pd.DataFrame(rows, columns=["wallet", "tx", "token_id", "ts", "price", "shares", "cid"])
    taker_tx = set(zip(tk["tx"], tk["wallet"]))
    f["role"] = ["taker" if (a, b) in taker_tx else "maker" for a, b in zip(f["tx"], f["wallet"])]
    return f


def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else float("nan")


def evaluate(start_ts: int, end_ts: int, cache_only: bool = False) -> dict:
    import lightgbm as lgb
    from scipy import stats
    if cache_only:
        os.environ["POLYREA_OFFLINE"] = "1"
    from polyrea.adapters.polymarket import PolymarketData
    from polyrea.adapters.spot import binance_seconds
    pm = PolymarketData()
    w = _windows(start_ts, end_ts)
    tk = _tapes(w, pm)
    sec_px, _ = binance_seconds("btc", start_ts - 7200, end_ts)
    spd = np.asarray(sec_px)
    sp = Spot(spd[:, 0].astype(np.int64), spd[:, 1])
    fills = _cluster_maker_fills(start_ts, end_ts, w, tk, pm)
    mk = fills[fills["role"] == "maker"]
    panel = build_panel(w, sp, tk, mk)
    panel = panel[panel["rel"] >= 0].reset_index(drop=True)
    model = lgb.Booster(model_file=str(HERE / f"presence_model_{MODEL}.txt"))
    base = lgb.Booster(model_file=str(HERE / f"presence_model_{BASELINE_MODEL}.txt"))
    panel["p"] = model.predict(panel[FEATS[MODEL]])
    panel["p_base"] = base.predict(panel[FEATS[BASELINE_MODEL]])
    res = {"period": [start_ts, end_ts], "windows": int(panel["cid"].nunique()), "bins": int(len(panel)),
           "cluster_maker_fills": int(len(mk)), "cluster_taker_fills": int((fills["role"] == "taker").sum()),
           "presence": {"auc": _auc(panel["y"], panel["p"]), "auc_activity_baseline": _auc(panel["y"], panel["p_base"]),
                        "pos_rate": float(panel["y"].mean())}}
    # side given a one-sided fill bin
    key = ["cid", "rel"]
    up = panel[panel["side_up"] == 1].set_index(key)
    dn = panel[panel["side_up"] == 0].set_index(key)
    lab = (up["y"] > 0).astype(int) - (dn["y"] > 0).astype(int)
    one = lab[lab != 0].index
    true_up = (lab.loc[one] > 0).to_numpy()
    pick = (up.loc[one, "p"] > dn.loc[one, "p"]).to_numpy()
    fav = (up.loc[one, "last_s"] > 0.5).to_numpy()
    bfav = (up.loc[one, "fair_s"] > 0.5).to_numpy()
    acc, acc_fav, acc_bfav = float(np.mean(pick == true_up)), float(np.mean(fav == true_up)), float(np.mean(bfav == true_up))
    dis = pick != fav
    k = int(np.sum((pick == true_up) & dis))
    p_side = float(stats.binomtest(k, int(dis.sum()), 0.5, alternative="greater").pvalue) if dis.sum() else float("nan")
    res["side"] = {"n_bins": int(len(one)), "accuracy": acc, "baseline_favourite_last_print": acc_fav,
                   "baseline_binance_favourite": acc_bfav, "p_vs_favourite_sign_test": p_side}
    # price: last taker print on the fill's side strictly before the fill second, minus PRICE_OFFSET, 0.01 grid
    tok_up = dict(zip(w["up_token"], w["cid"]))
    tok_dn = dict(zip(w["down_token"], w["cid"]))
    tkw = tk.copy()
    upset = set(w["up_token"])
    tkw["up_px"] = np.where(tkw["asset"].isin(upset), tkw["price"], 1 - tkw["price"])
    tkw = tkw.sort_values("ts")
    by = {c: (g["ts"].to_numpy(), g["up_px"].to_numpy()) for c, g in tkw.groupby("cid")}
    preds, acts = [], []
    for r in mk.itertuples(index=False):
        is_up = r.token_id in tok_up
        cid = tok_up.get(r.token_id) or tok_dn.get(r.token_id)
        if cid not in by:
            continue
        ts_, px_ = by[cid]
        i = np.searchsorted(ts_, r.ts, side="left") - 1
        if i < 0:
            continue
        last_s = px_[i] if is_up else 1 - px_[i]
        preds.append(round(last_s - PRICE_OFFSET, 2))
        acts.append(r.price)
    e = np.abs(np.asarray(acts) - np.asarray(preds))
    res["price"] = {"n_fills": int(len(e)), "exact_share_0.001_tick": float(np.mean(e < 0.0005)) if len(e) else float("nan"),
                    "within_0.01_share": float(np.mean(e <= 0.0105)) if len(e) else float("nan")}
    # per-window PnL: wallet maker fills vs rule expected PnL
    pay = dict(zip(w["cid"], w["up_payout"]))
    mk2 = mk.assign(cid2=[tok_up.get(t) or tok_dn.get(t) for t in mk["token_id"]], is_up=mk["token_id"].isin(upset))
    mk2["won"] = [(pay.get(c) if u else 1 - pay.get(c)) if pay.get(c) is not None else np.nan for c, u in zip(mk2["cid2"], mk2["is_up"])]
    wal = (mk2.assign(pnl=(mk2["won"] - mk2["price"]) * mk2["shares"]).groupby("cid2")["pnl"].sum())
    pr = panel.dropna(subset=["won_s"]).copy()
    pr["rule_pnl"] = pr["p"] * (pr["won_s"] - (pr["last_s"].fillna(0.5) - PRICE_OFFSET).round(2))
    rule = pr.groupby("cid")["rule_pnl"].sum()
    j = pd.concat([wal.rename("wallet"), rule.rename("rule")], axis=1).dropna()
    res["pnl"] = {"windows": int(len(j)), "pearson": float(j.corr().iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "spearman": float(j.corr(method="spearman").iloc[0, 1]) if len(j) > 2 else float("nan"),
                  "wallet_maker_return_on_usd": float(((mk2["won"] - mk2["price"]) * mk2["shares"]).sum() / (mk2["price"] * mk2["shares"]).sum()) if len(mk2) else float("nan")}
    res["selection"] = "not implemented in iteration 1 (match_test planned for iteration 2)"
    return res


if __name__ == "__main__":
    import json
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(a, b, cache_only=len(sys.argv) > 3 and sys.argv[3] == "cache"), indent=1, default=str))
