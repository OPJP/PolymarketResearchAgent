"""Iteration 15 (X146 step 2 = mechanics P3 baseline hardening; X114 size-only level events): does the Polymarket BOOK DEPTH (the capture's
L2 sizes, never ingested before) let a market-only baseline see the operator's decisions at the knee clock? The makers cancel on the
same Binance moves, so depth decrements could be a co-occurrence route on the book.
Units: the scored knee-clock hazard bins of 10-20..22 (hazard14_scored: label y, weight w (1% negatives x 100), frozen p_full,
p_pm_only). Book features from the l2ingest15 50-ms grid at the bot's Polymarket view t = e + 50 ms and earlier (server clock):
for o and the other outcome: best ask, depth at best + 0..4 c, their changes over 100 / 250 / 1000 ms, best-ask changes.
Models (LightGBM binary, 300 rounds), fit 10-20, scored once on 10-21..22, weighted AUC:
  PMB  = logit(p_pm_only) + book features   (the hardened market-only baseline)
  FULLB = logit(p_full) + book features      (does the book add to the decoded hazard?)
reported with the frozen p_full and p_pm_only AUCs on the same bins and the 2-h block bootstrap CI of FULLB - PMB and p_full - PMB.
Usage: python -I hazbook15.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score

D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]
h = pd.read_parquet(f"{D14}/hazard14_scored.parquet")
h = h[(h.e >= 1792454400000) & (h.e < 1792713600000)].reset_index(drop=True)
GR = {}
for day in DAYS:
    tk = pd.read_parquet(f"{D15}/l2tok_{day}.parquet"); gd = pd.read_parquet(f"{D15}/l2grid_{day}.parquet")
    n = len(tk); ng = len(gd) // n
    arr = {c: gd[c].to_numpy().reshape(n, ng) for c in ("best", "c0", "c1", "c2", "c3", "c4")}
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    for i, r in enumerate(tk.itertuples()):
        if d0 <= int(r.start_ts) < d0 + 86400:
            GR[(r.cid, int(r.is_up))] = (int(r.start_ts), {c: arr[c][i] for c in arr})
    del gd, arr
F = {}
names = []
for side, upf in (("o", lambda u: u), ("x", lambda u: 1 - u)):
    for c in ("best", "c0", "c1", "c2", "c4"):
        for lag in (0, 100, 250, 1000):
            names.append(f"{side}_{c}_{lag}")
for nm in names:
    F[nm] = np.full(len(h), np.nan, np.float32)
for (cid, up), g in h.groupby(["cid", "up"]):
    for side in ("o", "x"):
        key = (cid, int(up) if side == "o" else 1 - int(up))
        if key not in GR:
            continue
        st, A = GR[key]
        t = g.e.to_numpy() + 50
        for lag in (0, 100, 250, 1000):
            k = ((t - lag) - (st * 1000 - 60000)) // 50
            ok = (k >= 0) & (k < len(A["best"]))
            kk = np.clip(k, 0, len(A["best"]) - 1)
            for c in ("best", "c0", "c1", "c2", "c4"):
                v = A[c][kk].astype(np.float32); v[~ok] = np.nan
                F[f"{side}_{c}_{lag}"][g.index.to_numpy()] = v
X = pd.DataFrame(F)
for side in ("o", "x"):
    for c in ("best", "c0", "c1", "c2", "c4"):
        for lag in (100, 250, 1000):
            X[f"{side}_{c}_d{lag}"] = X[f"{side}_{c}_0"] - X[f"{side}_{c}_{lag}"]
        for lag in (100, 250, 1000):
            X.drop(columns=[f"{side}_{c}_{lag}"], inplace=True)
BOOK = list(X.columns)
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
X["lpm"] = lg(h.p_pm_only.to_numpy()); X["lfull"] = lg(h.p_full.to_numpy())
fit = (h.e < 1792540800000).to_numpy(); sc = ~fit
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=15)
y, w = h.y.to_numpy(), h.w.to_numpy()
rep = {"bins_fit": int(fit.sum()), "bins_score": int(sc.sum()), "book_coverage_score": round(float(X.loc[sc, "o_best_0"].notna().mean()), 4)}
P = {"p_full_frozen": h.p_full.to_numpy()[sc], "p_pm_only_frozen": h.p_pm_only.to_numpy()[sc]}
for nm, cols in (("PMB", ["lpm"] + BOOK), ("FULLB", ["lfull"] + BOOK), ("BOOK_only", BOOK)):
    m = lgb.train(PARAMS, lgb.Dataset(X.loc[fit, cols], y[fit], weight=w[fit]), 300)
    P[nm] = m.predict(X.loc[sc, cols])
    imp = pd.Series(m.feature_importance("gain"), index=cols); rep[f"top_{nm}"] = (imp / imp.sum()).sort_values(ascending=False).head(6).round(3).to_dict()
for k, p in P.items():
    rep[f"auc_{k}"] = round(float(roc_auc_score(y[sc], p, sample_weight=w[sc])), 4)
blk = (h.e.to_numpy()[sc] // 7200000)
ub = np.unique(blk); rng = np.random.default_rng(15)
idx = {b: np.where(blk == b)[0] for b in ub}
for a, b in (("p_full_frozen", "PMB"), ("FULLB", "PMB")):
    gs = []
    for _ in range(300):
        ii = np.concatenate([idx[x] for x in rng.choice(ub, len(ub))])
        gs.append(roc_auc_score(y[sc][ii], P[a][ii], sample_weight=w[sc][ii]) - roc_auc_score(y[sc][ii], P[b][ii], sample_weight=w[sc][ii]))
    rep[f"gain_{a}_minus_{b}"] = {"point": round(rep[f"auc_{a}"] - rep[f"auc_{b}"], 4), "ci95": [round(float(np.quantile(gs, 0.025)), 4), round(float(np.quantile(gs, 0.975)), 4)]}



# ---- 2x2: which channel drives the take? deciles of the book-only score and the frozen spot-only score (score days)
ps = h.p_spot_only.to_numpy()[sc]; pb = P["BOOK_only"]
def wq(x, q):
    o = np.argsort(x); cw = np.cumsum(w[sc][o]); cw /= cw[-1]
    return x[o][np.searchsorted(cw, q)]
qs, qb = wq(ps, 0.9), wq(pb, 0.9)
ys, ws = y[sc], w[sc]
out = {}
for a, sa in (("spot_top10", ps >= qs), ("spot_rest", ps < qs)):
    for b, sb in (("book_top10", pb >= qb), ("book_rest", pb < qb)):
        m = sa & sb
        out[f"{a}|{b}"] = {"weighted_take_rate": round(float((ys[m] * ws[m]).sum() / ws[m].sum()), 5), "bins_weight_share": round(float(ws[m].sum() / ws.sum()), 4), "positives": int(ys[m].sum())}
json.dump(out, open(OUT.replace(".json", "_2x2.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
