"""btc5m-bot frozen rule (iteration 2; models retrained locally because the iteration-1 model files were lost).

Point-in-time behaviour-cloning rule for the three-wallet BTC 5-minute Up/Down bot
(GF 0x0ca4e9d2..., XM 0x3048d653..., DS 0xc53375ff...). The rule scores every cell
(window, outcome, second) with a frozen LightGBM model (trained on BUILD only:
BUILD windows 2026-10-09 .. 2026-10-16 00:00 UTC that had tapes; model files model_it2_*.txt next to this script) from public data available before the
second: Binance 1-s closes of seconds <= s-2, other traders' taker prints with block
ts <= s-1 (cluster prints and prints that traded against the cluster removed), and listing
metadata. No own-state features, nothing fitted on VALIDATE or the holdout.

evaluate(start_ts, end_ts) fetches what it needs for that period (Gamma metadata,
Binance 1-s archive, data-api taker tapes, on-chain OrderFilled logs of the cluster),
applies the frozen rule and returns the brief's metrics.
"""
from __future__ import annotations
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root

import os
import sys
import time

CODE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CODE)
sys.path.insert(0, _ROOT + "")

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
from build_cells_day import add_inv, add_extra, OWN, EXTRA
from fetch_tapes2 import fetch_one as _fetch_tape

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
FEATURES = SPOT_FEATURES + TAPE_FEATURES + list(EXTRA)          # primary score: public PIT data only, no own state
MARKET_FEATURES = ["rel", "tau"] + TAPE_FEATURES + list(EXTRA)    # co-occurrence baseline: market activity only (no Binance)
OWN_FEATURES = FEATURES + list(OWN)                               # secondary: + cluster inventory (own state)
MODEL_Y = f"{CODE}/model_it2_spot_tape_y.txt"     # label: any cluster BUY fill on (window, outcome, second)
MODEL_T = f"{CODE}/model_it2_spot_tape_yT.txt"    # label: cluster taker fill
MODEL_M = f"{CODE}/model_it2_spot_tape_yM.txt"    # label: cluster maker fill
MODEL_MKT = f"{CODE}/model_it2_market_only_y.txt" # co-occurrence baseline
MODEL_OWN = f"{CODE}/model_it2_spot_tape_own_y.txt"  # with own state (secondary)
ORDER_SIZES = (30.0, 50.0, 60.0)  # the bot's fixed order sizes (shares), decoded on BUILD (iteration 1)
SEL_THRESH = 1.30  # print-level selection flag: size rule AND cell score >= P_THRESH (fixed before VALIDATE was scored)
P_THRESH = 0.30         # flag a cell when the presence score >= this (fixed in iteration 1, not tuned on VALIDATE)
ORDER_SHARES = 30.0      # rule order size for the PnL proxy
FEE_RATE = 0.07
EXCHANGES = rpc.V2_EXCHANGES
EVAL_DIR = _ROOT + "/.cache/re/btc5m-bot/eval"


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
    """Taker tapes for every window, same range and columns as in training (fetch_tapes2.fetch_one: [start-600, end+5])."""
    d = f"{EVAL_DIR}/tapes"
    os.makedirs(d, exist_ok=True)
    pm = PolymarketData()
    for r in windows.itertuples():
        _fetch_tape(pm, r.cid, r.start_ts, r.end_ts, int(end_ts), d)
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


def _side(cells: pd.DataFrame, pcol: str, lab: str = "y") -> pd.DataFrame:
    """Per second where the cluster bought exactly one outcome (label lab): truth and the pcol scores of both outcomes."""
    pv = cells.pivot_table(index=["cid", "rel"], columns="is_up", values=[pcol, lab, "m_last"], aggfunc="first")
    one = (pv[(lab, True)] + pv[(lab, False)]) == 1
    sub = pv[one]
    return pd.DataFrame({"truth_up": (sub[(lab, True)] == 1).to_numpy(), "pred_up": (sub[(pcol, True)] >= sub[(pcol, False)]).to_numpy(),
                         "fav_up": (sub[("m_last", True)] >= 0.5).to_numpy()})


def _mcnemar(a_ok, b_ok):
    b = int((a_ok & ~b_ok).sum()); c = int((~a_ok & b_ok).sum())
    return float(stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue) if b + c > 0 else None


def evaluate(start_ts: int, end_ts: int) -> dict:
    t0 = time.time()
    win = load_windows(start_ts, end_ts)
    win = win[win.up_payout.notna()].sort_values("start_ts").reset_index(drop=True)
    sp = load_spot(start_ts, end_ts)
    fills = cluster_fills(start_ts, end_ts, win)
    tf.TAPE_DIR = load_tapes(win, end_ts)
    cells = cellsmod.build_cells(win, fills, sp)
    cells = tf.add_tape_feats(cells, fills, sp)
    cells = add_inv(cells, fills, len(win))
    cells = add_extra(cells)
    p = lgb.Booster(model_file=MODEL_Y).predict(cells[FEATURES])
    pT = lgb.Booster(model_file=MODEL_T).predict(cells[FEATURES])
    pM = lgb.Booster(model_file=MODEL_M).predict(cells[FEATURES])
    pK = lgb.Booster(model_file=MODEL_MKT).predict(cells[MARKET_FEATURES])
    pO = lgb.Booster(model_file=MODEL_OWN).predict(cells[OWN_FEATURES])
    cells["p"] = p; cells["p_mkt"] = pK
    flag = p >= P_THRESH
    out = {"period": [int(start_ts), int(end_ts)], "windows": int(len(win)), "cells": int(len(cells)), "cluster_fills": int(len(fills))}
    # (a) presence, with the co-occurrence baseline (market activity only) and the own-state variant
    a_any = _auc(cells.y, p); a_mkt = _auc(cells.y, pK)
    out["presence"] = {
        "auc_any_no_own_state": a_any, "auc_taker": _auc(cells.yT, pT), "auc_maker": _auc(cells.yM, pM),
        "auc_any_by_wallet": {w: _auc(cells[f"y{w}"], p) for w in ("GF", "XM", "DS")},
        "co_occurrence_baseline_auc": a_mkt, "gain_over_baseline": round(a_any - a_mkt, 4) if a_any and a_mkt else None,
        "auc_with_own_state": _auc(cells.y, pO),
        "base_rate": round(float(cells.y.mean()), 4), "at_threshold": _recall_lift(cells.y, flag),
        "baseline_at_threshold": _recall_lift(cells.y, pK >= P_THRESH),
    }
    # (b) side: seconds with a one-sided cluster buy; rule = outcome with the higher presence score
    sd = {}
    for lab in ("y", "yT"):
        s1 = _side(cells, "p", lab); s0 = _side(cells.assign(p=pK), "p", lab)
        ok1 = s1.pred_up.to_numpy() == s1.truth_up.to_numpy(); ok0 = s0.pred_up.to_numpy() == s0.truth_up.to_numpy()
        okf = s1.fav_up.to_numpy() == s1.truth_up.to_numpy()
        sd[lab] = {"n_seconds": int(len(s1)), "accuracy": round(float(ok1.mean()), 4), "baseline_market_only_model": round(float(ok0.mean()), 4),
                   "baseline_favourite": round(float(okf.mean()), 4), "mcnemar_p_vs_market_only": _mcnemar(ok1, ok0), "mcnemar_p_vs_favourite": _mcnemar(ok1, okf)}
    out["side"] = sd
    # (c) price: predicted taker price = last implied ask of the outcome from others' prints (<= s-1)
    key = cells.set_index(["cid", "is_up", "rel"])[["ask_o"]]
    fz = fills[(fills.rel >= 0) & (fills.rel < 300)]
    j = fz.join(key, on=["cid", "is_up", "rel"])
    out["price"] = {}
    for role in ("T", "M"):
        g = j[(j.role == role) & np.isfinite(j.ask_o)]
        out["price"][f"{role}_within_1tick_of_last_ask"] = round(float((np.abs(g.price - g.ask_o) <= 0.0101).mean()), 4) if len(g) else None
    # selection: all in-window taker prints (every trader), cluster vs others, scored by p of the print's cell
    rows = []
    for cid in win.cid:
        tp = f"{tf.TAPE_DIR}/{cid}.parquet"
        if os.path.exists(tp):
            d = pd.read_parquet(tp)
            if len(d) and "timestamp" in d:
                rows.append(d[["proxyWallet", "outcome", "timestamp", "price", "size"]].assign(cid=cid))
    if rows:
        tp = pd.concat(rows).merge(win[["cid", "start_ts"]], on="cid")
        tp["rel"] = tp.timestamp - tp.start_ts
        tp = tp[(tp.rel >= 0) & (tp.rel < 300)]
        tp["is_up"] = tp.outcome == "Up"
        tp = tp.join(cells.set_index(["cid", "is_up", "rel"])[["p", "p_mkt"]], on=["cid", "is_up", "rel"])
        lab = tp.proxyWallet.str.lower().isin(WALLETS).to_numpy()
        # iteration 2: print-level score = 1[print size is one of the bot's fixed order sizes] + cell score p
        size_rule = np.isin(np.round(tp["size"].astype(float).to_numpy(), 2), ORDER_SIZES)
        score = size_rule.astype(float) + tp.p.to_numpy()
        aw, ww = [], []
        for _, g in pd.DataFrame({"cid": tp.cid.to_numpy(), "lab": lab, "score": score}).groupby("cid"):
            if 0 < g.lab.sum() < len(g):
                aw.append(roc_auc_score(g.lab, g.score)); ww.append(g.lab.sum())
        out["selection"] = {"taker_prints": int(len(tp)), "cluster_share": round(float(lab.mean()), 4),
                            "auc_cell_score_only": _auc(lab, tp.p.to_numpy()), "co_occurrence_baseline_auc": _auc(lab, tp.p_mkt.to_numpy()),
                            "auc_size_plus_cell_score": _auc(lab, score),
                            "co_occurrence_baseline_auc_size_plus_market_only_score": _auc(lab, size_rule.astype(float) + tp.p_mkt.to_numpy()),
                            "auc_within_window_size_plus_cell_score": round(float(np.average(aw, weights=ww)), 4) if aw else None,
                            "at_preregistered_threshold_score_ge_1.30": _recall_lift(lab, score >= SEL_THRESH),
                            "size_rule_only": _recall_lift(lab, size_rule),
                            "note": "pooled AUC over in-window taker prints of every trader"}
    # outcome: per-window PnL correlation, hard proxy (flag -> buy 30 at last implied ask) and soft proxy (p * 30 shares)
    c2 = cells[np.isfinite(cells.ask_o) & (cells.ask_o > 0.05) & (cells.ask_o < 0.95)].merge(win[["cid", "up_payout"]], on="cid")
    pay = np.where(c2.is_up, c2.up_payout, 1 - c2.up_payout)
    unit = pay - c2.ask_o - FEE_RATE * c2.ask_o * (1 - c2.ask_o)
    c2["pnl_h"] = np.where(c2.p >= P_THRESH, ORDER_SHARES * unit, 0.0); c2["usd_h"] = np.where(c2.p >= P_THRESH, ORDER_SHARES * c2.ask_o, 0.0)
    c2["pnl_s"] = c2.p * ORDER_SHARES * unit; c2["usd_s"] = c2.p * ORDER_SHARES * c2.ask_o
    rule_w = c2.groupby("cid")[["pnl_h", "pnl_s", "usd_h", "usd_s"]].sum()
    fw = fills.assign(pay=np.where(fills.is_up, fills.up_payout, 1 - fills.up_payout))
    fw["pnl"] = fw.shares * (fw.pay - fw.price) - fw.fee_usd
    wal_w = fw.groupby("cid").pnl.sum().rename("wallet")
    both = rule_w.join(wal_w, how="outer").reindex(win.cid).fillna(0.0)
    out["outcome"] = {
        "per_window_pnl_corr_hard_pearson": round(float(both.pnl_h.corr(both.wallet)), 4),
        "per_window_pnl_corr_soft_pearson": round(float(both.pnl_s.corr(both.wallet)), 4),
        "per_window_pnl_corr_soft_spearman": round(float(both.pnl_s.corr(both.wallet, method="spearman")), 4),
        "rule_return_hard": round(float(both.pnl_h.sum() / both.usd_h.sum()), 4) if both.usd_h.sum() > 0 else None,
        "rule_return_soft": round(float(both.pnl_s.sum() / both.usd_s.sum()), 4) if both.usd_s.sum() > 0 else None,
        "wallet_return_before_rebates": round(float(fw.pnl.sum() / fw.usdc.sum()), 4) if len(fw) else None,
        "note": "rule PnL is a proxy (buys at the last observed ask at s-1, no queue/fill check), not a strict-fill backtest",
    }
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    import json
    print(json.dumps(evaluate(a, b), indent=1, default=str))
