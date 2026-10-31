"""Iteration 8: does the side (and the size) reference the operator's own book? (X50 = panel-mechanics iter7 P2,
complete sets; X49 = panel-mechanics iter7 P1, size from the operator net). Own state is legitimate for describing the
policy (brief: report every model with and without own state).

Side part (this script): every VALIDATE one-sided block second (val_side_it5book.parquet: the frozen side model psb and the
truth), plus every VALIDATE taker decision (orders.parquet: first fill of each taker-first order). Operator state at block
second s = the three wallets' filled shares per outcome in the window with block second <= s - LAG (fills.parquet;
LAG = 1, strictly earlier seconds, and LAG = 2).
  own-only baseline:  buy the leg the operator is short (fewer shares); ties abstain
  own model:          logistic on BUILD one-sided seconds: P(Up) ~ tanh(d/100), tanh(d/100) * rel/300, avg-cost terms
  combined (frozen):  logit(psb) + (own_logit - logit(build base rate))  [no VALIDATE fitting]
  diagnostic:         combination weights fitted on VALIDATE first half (by start_ts), scored on the second half
Writes results/own8_side.json."""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
OUT = os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results")
VAL0 = 1792108800


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["ts", "wallet", "role", "oh", "shares", "price", "start_ts", "is_up", "cid"])
f["s"] = (f.ts - f.start_ts).astype(int)
f["up"] = f.is_up.astype(bool)
# per (cid, s) bought shares and cost by outcome (all roles: the operator's book)
g = f.groupby(["cid", "s", "up"]).agg(sh=("shares", "sum"), cost=("price", lambda x: 0.0)).reset_index()
f["usd"] = f.shares * f.price
g = f.groupby(["cid", "s", "up"]).agg(sh=("shares", "sum"), usd=("usd", "sum")).reset_index()
gw = g.pivot_table(index=["cid", "s"], columns="up", values=["sh", "usd"], fill_value=0.0)
gw.columns = [f"{a}_{'U' if b else 'D'}" for a, b in gw.columns]
gw = gw.reset_index().sort_values(["cid", "s"])
for k in ["sh_U", "sh_D", "usd_U", "usd_D"]:
    gw["c_" + k] = gw.groupby("cid")[k].cumsum()
start = f.groupby("cid").start_ts.first()


def state_at(keys, lag):
    """operator cumulative state through block second s - lag for each (cid, s) in keys (DataFrame with cid, s)."""
    q = keys[["cid", "s"]].copy()
    q["sq"] = q.s - lag
    q = q.reset_index().rename(columns={"index": "_i"})
    # merge_asof per cid on sq <= s
    a = gw[["cid", "s", "c_sh_U", "c_sh_D", "c_usd_U", "c_usd_D"]].rename(columns={"s": "sq"})
    q = q.sort_values("sq"); a = a.sort_values("sq")
    m = pd.merge_asof(q, a, on="sq", by="cid", direction="backward")
    m = m.sort_values("_i")
    for k in ["c_sh_U", "c_sh_D", "c_usd_U", "c_usd_D"]:
        m[k] = m[k].fillna(0.0)
    return m.set_index("_i")


def feats(m, rel):
    d = (m.c_sh_U - m.c_sh_D).values
    avgU = np.where(m.c_sh_U > 0, m.c_usd_U / np.maximum(m.c_sh_U, 1e-9), np.nan)
    avgD = np.where(m.c_sh_D > 0, m.c_usd_D / np.maximum(m.c_sh_D, 1e-9), np.nan)
    x = np.column_stack([np.tanh(d / 100.0), np.tanh(d / 100.0) * rel / 300.0, np.tanh(d / 30.0),
                         np.nan_to_num(avgU - 0.5, nan=0.0), np.nan_to_num(avgD - 0.5, nan=0.0),
                         np.isnan(avgU).astype(float), np.isnan(avgD).astype(float)])
    return x, d


# ---- one-sided seconds: BUILD truth from fills, VALIDATE from val_side_it5book
os_ = f.groupby(["cid", "s"]).up.agg(["min", "max"]).reset_index()
os_ = os_[os_["min"] == os_["max"]].rename(columns={"min": "truth_up"})
os_["start_ts"] = os_.cid.map(start)
os_["truth_up"] = os_.truth_up.astype(int)
v = pd.read_parquet(os.path.join(C, "val_side_it5book.parquet"), columns=["cid", "rel", "start_ts", "truth_up", "psb"])
v["s"] = v.rel.astype(int)
res = {"n_val_one_sided": int(len(v))}
for lag in (1, 2):
    b = os_[os_.start_ts < VAL0].reset_index(drop=True)
    mb = state_at(b, lag)
    xb, db = feats(mb, b.s.values.astype(float))
    yb = b.truth_up.values
    lr = LogisticRegression(C=1.0, max_iter=500).fit(xb, yb)
    base = logit(np.array([yb.mean()]))[0]
    mv = state_at(v, lag)
    xv, dv = feats(mv, v.s.values.astype(float))
    yv = v.truth_up.values.astype(int)
    own_l = lr.decision_function(xv)
    p_own = 1 / (1 + np.exp(-own_l))
    comb = logit(v.psb.values) + (own_l - base)
    r = {"build_n": int(len(b)), "build_coef": [round(c, 3) for c in lr.coef_[0]], "build_intercept": round(float(lr.intercept_[0]), 3)}
    acc = lambda pred, y, msk=None: float(np.mean((pred == y)[msk] if msk is not None else (pred == y)))
    r["psb_acc"] = acc((v.psb.values > 0.5).astype(int), yv)
    nz = dv != 0
    r["own_short_leg_cover"] = float(nz.mean())
    r["own_short_leg_acc"] = acc((dv < 0).astype(int), yv, nz)
    r["own_model_acc"] = acc((p_own > 0.5).astype(int), yv)
    r["combined_acc"] = acc((comb > 0).astype(int), yv)
    # by window time
    bins = [0, 60, 120, 180, 240, 300]
    rb = {}
    for lo, hi in zip(bins[:-1], bins[1:]):
        k = (v.s.values >= lo) & (v.s.values < hi)
        rb[f"{lo}-{hi}"] = {"n": int(k.sum()), "psb": acc((v.psb.values > 0.5).astype(int), yv, k), "comb": acc((comb > 0).astype(int), yv, k),
                            "short_leg": acc((dv < 0).astype(int), yv, k & nz)}
    r["by_rel"] = rb
    # by psb confidence
    conf = np.abs(v.psb.values - 0.5)
    rc = {}
    for lo, hi in [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5)]:
        k = (conf >= lo) & (conf < hi)
        rc[f"{lo}-{hi}"] = {"n": int(k.sum()), "psb": acc((v.psb.values > 0.5).astype(int), yv, k), "comb": acc((comb > 0).astype(int), yv, k)}
    r["by_psb_conf"] = rc
    # diagnostic: weights fitted on VALIDATE first half, scored on the second
    mid = np.median(v.start_ts.values)
    h1 = v.start_ts.values < mid
    X = np.column_stack([logit(v.psb.values), own_l - base])
    lr2 = LogisticRegression(C=1.0, max_iter=500).fit(X[h1], yv[h1])
    r["diag_half_fit_coef"] = [round(c, 3) for c in lr2.coef_[0]]
    r["diag_second_half_acc"] = acc((lr2.decision_function(X[~h1]) > 0).astype(int), yv[~h1])
    r["diag_second_half_psb_acc"] = acc((v.psb.values[~h1] > 0.5).astype(int), yv[~h1])
    res[f"lag{lag}"] = r
    print(lag, json.dumps({k: r[k] for k in ["psb_acc", "own_short_leg_cover", "own_short_leg_acc", "own_model_acc", "combined_acc", "diag_second_half_acc", "diag_second_half_psb_acc"]}))
    print("  by_rel", json.dumps(rb))

json.dump(res, open(os.path.join(OUT, "own8_side.json"), "w"), indent=1)
