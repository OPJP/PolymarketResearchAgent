"""Iteration 19 (X191 follow-up; pre-registration 23, written 11-01 ~14:20 UTC before the run): sidebook15 unchanged (fit 10-20, score once on 10-21..22; Polymarket book of both outcomes at m0 - 210 ms), now SPLIT BY CME GLOBEX SESSION (dc_exam14.globex_open_ms) and also run in reverse (fit 10-21..22, score 10-20). Question: is the book's value on the orders dc14 gets wrong concentrated in Globex-open hours (makers that read the same TradFi input move first), i.e. is the Polymarket book a public partial proxy of the missing input? Closed hours here are the Mon-Thu 21-22 UTC breaks only (small). Usage: python sidebook19.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dc_exam14 import globex_open_ms
D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]
p = pd.read_parquet(f"{D14}/dcfit14_pred.parquet", columns=["cid", "wallet", "up", "m", "m0", "rank", "start_ts", "p_dc14_spot_dec", "p_dc14_spot_own"])
p = p[p.start_ts >= 1792454400].reset_index(drop=True)
GR = {}
for day in DAYS:
    tk = pd.read_parquet(f"{D15}/l2tok_{day}.parquet"); gd = pd.read_parquet(f"{D15}/l2grid_{day}.parquet")
    n = len(tk); ng = len(gd) // n
    arr = {c: gd[c].to_numpy().reshape(n, ng) for c in ("best", "c0", "c1", "c2", "c4")}
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    for i, r in enumerate(tk.itertuples()):
        if d0 <= int(r.start_ts) < d0 + 86400:
            GR[(r.cid, int(r.is_up))] = (int(r.start_ts), {c: arr[c][i] for c in arr})
    del gd, arr
F = {}
for side in ("U", "D"):
    for c in ("best", "c0", "c1", "c2", "c4"):
        for lag in (0, 100, 250, 1000):
            F[f"{side}_{c}_{lag}"] = np.full(len(p), np.nan, np.float32)
for cid, g in p.groupby("cid"):
    for side, upv in (("U", 1), ("D", 0)):
        if (cid, upv) not in GR:
            continue
        st, A = GR[(cid, upv)]
        t = g.m0.to_numpy() - 210
        for lag in (0, 100, 250, 1000):
            k = ((t - lag) - (st * 1000 - 60000)) // 50
            ok = (k >= 0) & (k < len(A["best"])); kk = np.clip(k, 0, len(A["best"]) - 1)
            for c in ("best", "c0", "c1", "c2", "c4"):
                v = A[c][kk].astype(np.float32); v[~ok] = np.nan
                F[f"{side}_{c}_{lag}"][g.index.to_numpy()] = v
X = pd.DataFrame(F)
for side in ("U", "D"):
    for c in ("best", "c0", "c1", "c2", "c4"):
        for lag in (100, 250, 1000):
            X[f"{side}_{c}_d{lag}"] = X[f"{side}_{c}_0"] - X[f"{side}_{c}_{lag}"]
        X = X.drop(columns=[f"{side}_{c}_{lag}" for lag in (100, 250, 1000)])
for c in ("c0", "c1", "c2", "c4"):
    for lag in ("0", "d100", "d250", "d1000"):
        X[f"UD_{c}_{lag}"] = X[f"U_{c}_{lag}"] - X[f"D_{c}_{lag}"]
BOOK = list(X.columns)
X["ldc"] = np.log(np.clip(p.p_dc14_spot_dec, 1e-4, 1 - 1e-4) / (1 - np.clip(p.p_dc14_spot_dec, 1e-4, 1 - 1e-4)))
y = p.up.astype(int).to_numpy()
gx_all = globex_open_ms(p.m0.to_numpy(np.int64))
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=15)
rep = {"prereg": "23"}
for split, fit in (("forward", (p.start_ts < 1792540800).to_numpy()), ("reverse", (p.start_ts >= 1792540800).to_numpy())):
    sc = ~fit
    P = {"DC14": p.p_dc14_spot_dec.to_numpy()[sc]}
    for nm, cols in (("BOOK", BOOK), ("DC14+BOOK", ["ldc"] + BOOK)):
        m = lgb.train(PARAMS, lgb.Dataset(X.loc[fit, cols], y[fit]), 300)
        P[nm] = m.predict(X.loc[sc, cols])
    ys = y[sc]; gx = gx_all[sc]
    wrong = (P["DC14"] > 0.5).astype(int) != ys
    o = {"n_score": int(sc.sum()), "n_open_closed": [int(gx.sum()), int((~gx).sum())]}
    for sn, mk in (("all", np.ones(len(ys), bool)), ("open", gx), ("closed", ~gx)):
        o[sn] = {}
        for nm, q in P.items():
            acc = (q > 0.5).astype(int) == ys
            o[sn][nm] = {"acc": round(float(acc[mk].mean()), 4) if mk.any() else None,
                         "acc_on_dc14_wrong": round(float(acc[mk & wrong].mean()), 4) if (mk & wrong).any() else None}
        o[sn]["dc14_wrong_share"] = round(float(wrong[mk].mean()), 4) if mk.any() else None
        o[sn]["gain_dc14book_over_dc14"] = round(o[sn]["DC14+BOOK"]["acc"] - o[sn]["DC14"]["acc"], 4) if mk.any() else None
    rep[split] = o
json.dump(rep, open(OUT, "w"), indent=1)
print(json.dumps(rep, indent=1))
