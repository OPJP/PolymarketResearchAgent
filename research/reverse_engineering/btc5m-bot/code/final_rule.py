"""btc5m-bot frozen rule (iteration 1).

Point-in-time behaviour-cloning rule for the three-wallet BTC 5-minute Up/Down bot
(GF 0x0ca4e9d2..., XM 0x3048d653..., DS 0xc53375ff...). The rule scores every cell
(window, outcome, second) with a frozen LightGBM model (trained on BUILD only:
the 1,210 most recent BUILD windows before 2026-10-16 that had tapes, about 10-11 20:00 .. 10-16 00:00 UTC; model files next to this script) from public data available before the
second: Binance 1-s closes of seconds <= s-2, other traders' taker prints with block
ts <= s-1 (cluster prints and prints that traded against the cluster removed), and listing
metadata. No own-state features, nothing fitted on VALIDATE or the holdout.

evaluate(start_ts, end_ts) fetches what it needs for that period (Gamma metadata,
Binance 1-s archive, data-api taker tapes, on-chain OrderFilled logs of the cluster),
applies the frozen rule and returns the brief's metrics.
"""
from __future__ import annotations

import os
import sys
import time

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
sys.path.insert(0, "/home/user/PolymarketResearchAgent")

import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy import stats
from sklearn.metrics import roc_auc_score

from polyrea.adapters.polymarket import PolymarketData
from polyrea.adapters.spot import binance_seconds
from polyrea.analysis.updown import windows_from_markets
from polyrea.workflows.updown_study import fetch_windows, window_slugs

import cells as cellsmod
import rpc
import spot as spotmod
import tape_feats as tf

# ----------------------------------------------------------------------------- frozen constants
WALLETS = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
SPOT_FEATURES = [
    "rel", "tau", "sig", "z", "fv", "r1", "r2", "r3", "r5", "r10", "r20", "r30", "r60",
    "rn1", "rn2", "rn3", "rn5", "rn10", "rn20", "rn30", "rn60", "absr1", "mxf3", "mxa3", "mxf10", "mxa10",
]
TAPE_FEATURES = [
    "m_last", "age_last", "ask_o", "age_ask", "bid_o", "age_bid", "vwap10", "vwap30", "n1", "n2", "n5", "n30", "vol30",
    "flow1", "flow2", "flow5", "flow30", "sp_since", "gap_m", "gap_ask", "gap_vw", "spread",
]
MODEL_SET = "spot_tape"  # frozen choice made on VALIDATE (see FINAL_RULE.md): "spot_tape" or "spot_only"
if MODEL_SET == "spot_tape":
    FEATURES = SPOT_FEATURES + TAPE_FEATURES
    MODEL_Y = f"{CODE}/model_spot_tape_y.txt"   # label: any cluster BUY fill on (window, outcome, second)
    MODEL_T = f"{CODE}/model_spot_tape_yT.txt"  # label: cluster taker fill
    MODEL_M = f"{CODE}/model_spot_tape_yM.txt"  # label: cluster maker fill
else:
    FEATURES = SPOT_FEATURES
    MODEL_Y = MODEL_T = MODEL_M = f"{CODE}/model_spot_only_y.txt"
P_THRESH = 0.30          # flag a cell when the presence score >= this (fixed in iteration 1, not tuned on VALIDATE)
ORDER_SHARES = 30.0      # rule order size for the PnL proxy
FEE_RATE = 0.07
EXCHANGES = rpc.V2_EXCHANGES
EVAL_DIR = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot/eval"


# ----------------------------------------------------------------------------- data loading
def _find_block(ts: int) -> int:
    """First block with timestamp >= ts (binary search over cached eth_getBlockByNumber)."""
    head = int(rpc.call("eth_blockNumber", [], max_age=60), 16)
    lo, hi = 1, head
    est = head - int((rpc.block_ts(head) - ts) / 1.5)
    lo, hi = max(1, est - 200_000), min(head, est + 200_000)
    while rpc.block_ts(lo) >= ts:
        lo = max(1, lo - 400_000)
    while rpc.block_ts(hi) < ts:
        hi = min(head, hi + 400_000)
        if hi == head:
            break
    while lo < hi:
        mid = (lo + hi) // 2
        if rpc.block_ts(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _decode(log):
    t = log["topics"]; d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, min(len(d), 64 * 5), 64)]
    return {"block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16) if "blockTimestamp" in log else -1,
            "tx": log["transactionHash"], "li": int(log["logIndex"], 16), "oh": t[1], "owner": "0x" + t[2][-40:], "cp": "0x" + t[3][-40:],
            "side": w[0], "token": str(w[1]), "mamt": float(w[2]), "tamt": float(w[3]), "fee": float(w[4])}


def cluster_fills(start_ts: int, end_ts: int, windows: pd.DataFrame) -> pd.DataFrame:
    """Every OrderFilled of the cluster's own orders (maker and taker role) in [start_ts, end_ts)."""
    b0, b1 = _find_block(start_ts), _find_block(end_ts)
    pads = [rpc.pad(x) for x in WALLETS]
    rows = []
    for a in range(b0, b1, 3000):
        b = min(a + 2999, b1 - 1)
        for ex in EXCHANGES:
            rows += [_decode(l) for l in rpc.get_logs(ex, a, b, [rpc.TOPIC_V2, None, pads])]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    miss = df.ts < 0
    if miss.any():
        for blk in df.loc[miss, "block"].unique():
            df.loc[df.block == blk, "ts"] = rpc.block_ts(int(blk))
    df = df.drop_duplicates(["tx", "li"])
    df = df[(df.ts >= start_ts) & (df.ts < end_ts)]
    df["wallet"] = df.owner.map(WALLETS)
    df["role"] = np.where(df.cp.isin([e.lower() for e in EXCHANGES]), "T", "M")
    buy = df.side == 0
    df["usdc"] = np.where(buy, df.mamt, df.tamt) / 1e6
    df["shares"] = np.where(buy, df.tamt, df.mamt) / 1e6
    df["price"] = df.usdc / df.shares
    df["fee_usd"] = df.fee / 1e6
    up = windows[["cid", "start_ts", "end_ts", "up_token", "up_payout"]].rename(columns={"up_token": "token"}).assign(is_up=True)
    dn = windows[["cid", "start_ts", "end_ts", "down_token", "up_payout"]].rename(columns={"down_token": "token"}).assign(is_up=False)
    df = df.merge(pd.concat([up, dn]), on="token", how="inner")
    df["rel"] = df.ts - df.start_ts
    return df[df.side == 0].sort_values(["block", "li"]).reset_index(drop=True)


def load_windows(start_ts: int, end_ts: int) -> pd.DataFrame:
    markets = fetch_windows(window_slugs("btc", "5m", start_ts, end_ts))
    ws = windows_from_markets(markets)
    w = pd.DataFrame([{"cid": x.condition_id, "start_ts": x.start_ts, "end_ts": x.end_ts, "up_token": x.up_token, "down_token": x.down_token,
                       "fee_rate": x.fee_rate, "up_payout": x.up_payout} for x in ws])
    return w[(w.start_ts >= start_ts) & (w.end_ts <= end_ts)].reset_index(drop=True)


def load_tapes(windows: pd.DataFrame, end_ts: int) -> str:
    d = f"{EVAL_DIR}/tapes"
    os.makedirs(d, exist_ok=True)
    pm = PolymarketData()
    for r in windows.itertuples():
        p = f"{d}/{r.cid}.parquet"
        if os.path.exists(p):
            continue
        rows, _, cov = pm.market_trades(r.cid, start=int(r.start_ts) - 3600, end=min(int(r.end_ts) + 120, int(end_ts) - 1), taker_only=True)
        df = pd.DataFrame(rows)
        keep = [c for c in ["proxyWallet", "side", "asset", "conditionId", "size", "price", "timestamp", "outcome", "outcomeIndex", "transactionHash"] if c in df.columns]
        df = df[keep] if len(df) else df
        df["coverage"] = cov.status
        df.to_parquet(p, index=False)
    return d


def load_spot(start_ts: int, end_ts: int) -> spotmod.Spot:
    sp, _ = binance_seconds("btc", start_ts - 7200, end_ts)
    s = pd.DataFrame(sp, columns=["sec", "close"])
    s["sec"] = s.sec.astype(np.int64)
    return spotmod.Spot(frame=s)


# ----------------------------------------------------------------------------- metrics helpers
def _auc(y, p):
    y = np.asarray(y); p = np.asarray(p)
    ok = np.isfinite(p)
    if y[ok].min() == y[ok].max():
        return None
    return round(float(roc_auc_score(y[ok], p[ok])), 4)


def _recall_lift(y, flag):
    y = np.asarray(y).astype(bool); flag = np.asarray(flag).astype(bool)
    base = y.mean(); rec = flag[y].mean() if y.any() else np.nan
    prec = y[flag].mean() if flag.any() else np.nan
    lift = prec / base if base > 0 else np.nan
    # one-sided binomial test of precision vs base rate
    k, n = int(y[flag].sum()), int(flag.sum())
    pval = float(stats.binomtest(k, n, base, alternative="greater").pvalue) if n > 0 else None
    return {"recall": round(float(rec), 4), "precision": round(float(prec), 4), "lift": round(float(lift), 3), "flag_share": round(float(flag.mean()), 4), "p_value": pval}


def evaluate(start_ts: int, end_ts: int) -> dict:
    t0 = time.time()
    win = load_windows(start_ts, end_ts)
    win = win[win.up_payout.notna()].reset_index(drop=True)
    sp = load_spot(start_ts, end_ts)
    fills = cluster_fills(start_ts, end_ts, win)
    tf.TAPE_DIR = load_tapes(win, end_ts)
    cells = cellsmod.build_cells(win, fills, sp)
    cells = tf.add_tape_feats(cells, fills, sp)
    X = cells[FEATURES]
    p = lgb.Booster(model_file=MODEL_Y).predict(X)
    pT = lgb.Booster(model_file=MODEL_T).predict(X)
    pM = lgb.Booster(model_file=MODEL_M).predict(X)
    cells["p"] = p
    flag = p >= P_THRESH
    out = {"period": [int(start_ts), int(end_ts)], "windows": int(len(win)), "cells": int(len(cells)), "cluster_fills": int(len(fills))}
    # (a) presence
    out["presence"] = {
        "auc_any_no_own_state": _auc(cells.y, p), "auc_taker": _auc(cells.yT, pT), "auc_maker": _auc(cells.yM, pM),
        "auc_any_by_wallet": {w: _auc(cells[f"y{w}"], p) for w in ("GF", "XM", "DS")},
        "base_rate": round(float(cells.y.mean()), 4), "at_threshold": _recall_lift(cells.y, flag),
        "with_own_state": "not implemented in iteration 1",
    }
    # (b) side: seconds where the cluster bought exactly one outcome
    pv = cells.pivot_table(index=["cid", "rel"], columns="is_up", values=["p", "y", "m_last", "flow5"], aggfunc="first")
    one = (pv[("y", True)] + pv[("y", False)]) == 1
    sub = pv[one]
    truth_up = sub[("y", True)] == 1
    pred_up = sub[("p", True)] >= sub[("p", False)]
    fav_up = sub[("m_last", True)] >= 0.5
    mom_up = sub[("flow5", True)] >= 0
    acc = float((pred_up == truth_up).mean()); acc_fav = float((fav_up == truth_up).mean()); acc_mom = float((mom_up == truth_up).mean())
    b = int(((pred_up == truth_up) & (fav_up != truth_up)).sum()); c = int(((pred_up != truth_up) & (fav_up == truth_up)).sum())
    mcnemar_p = float(stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c > 0 else None
    out["side"] = {"n_seconds": int(len(sub)), "accuracy": round(acc, 4), "baseline_favourite": round(acc_fav, 4), "baseline_tape_flow5": round(acc_mom, 4), "mcnemar_p_vs_favourite": mcnemar_p}
    # (c) price: predicted taker price = last implied ask of the outcome from others' prints (<= s-1)
    key = cells.set_index(["cid", "is_up", "rel"])[["ask_o", "bid_o"]]
    fz = fills[(fills.rel >= 0) & (fills.rel < 300)]
    j = fz.join(key, on=["cid", "is_up", "rel"])
    for role in ("T", "M"):
        g = j[j.role == role]
        out.setdefault("price", {})[f"{role}_within_1tick_of_last_ask"] = round(float((np.abs(g.price - g.ask_o) <= 0.0101).mean()), 4) if len(g) else None
    # selection: all in-window taker prints (every trader), cluster vs others, scored by p of the print's cell
    rows = []
    for cid in win.cid:
        tp = f"{tf.TAPE_DIR}/{cid}.parquet"
        if os.path.exists(tp):
            d = pd.read_parquet(tp)
            if len(d) and "timestamp" in d:
                rows.append(d[["proxyWallet", "outcome", "timestamp", "price"]].assign(cid=cid))
    if rows:
        tp = pd.concat(rows)
        tp = tp.merge(win[["cid", "start_ts"]], on="cid")
        tp["rel"] = tp.timestamp - tp.start_ts
        tp = tp[(tp.rel >= 0) & (tp.rel < 300)]
        tp["is_up"] = tp.outcome == "Up"
        tp = tp.join(cells.set_index(["cid", "is_up", "rel"])["p"], on=["cid", "is_up", "rel"])
        lab = tp.proxyWallet.str.lower().isin(WALLETS).to_numpy()
        out["selection"] = {"taker_prints": int(len(tp)), "cluster_share": round(float(lab.mean()), 4), "auc": _auc(lab, tp.p.to_numpy()),
                            "at_threshold": _recall_lift(lab, tp.p.to_numpy() >= P_THRESH), "note": "pooled AUC, no rotation null in iteration 1"}
    # outcome: crude PnL proxy (rule buys ORDER_SHARES at the last implied ask when flagged)
    c2 = cells[flag & np.isfinite(cells.ask_o) & (cells.ask_o > 0.05) & (cells.ask_o < 0.95)].merge(win[["cid", "up_payout"]], on="cid")
    pay = np.where(c2.is_up, c2.up_payout, 1 - c2.up_payout)
    c2["pnl"] = ORDER_SHARES * (pay - c2.ask_o - FEE_RATE * c2.ask_o * (1 - c2.ask_o))
    c2["usd"] = ORDER_SHARES * c2.ask_o
    rule_w = c2.groupby("cid").pnl.sum()
    fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
    fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
    wal_w = fw.groupby("cid").pnl.sum()
    both = pd.concat([rule_w.rename("rule"), wal_w.rename("wallet")], axis=1).reindex(win.cid).fillna(0.0)
    out["outcome"] = {
        "per_window_pnl_corr_pearson": round(float(both.rule.corr(both.wallet)), 4),
        "per_window_pnl_corr_spearman": round(float(both.rule.corr(both.wallet, method="spearman")), 4),
        "rule_return_crude": round(float(c2.pnl.sum() / c2.usd.sum()), 4) if len(c2) else None,
        "wallet_return_before_rebates": round(float(fw.pnl.sum() / fw.usdc.sum()), 4) if len(fw) else None,
        "note": "rule PnL is a crude proxy (buys at the last observed ask at s-1, no queue/fill check); strict-fill backtest not implemented in iteration 1",
    }
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    import json
    print(json.dumps(evaluate(a, b), indent=1, default=str))
