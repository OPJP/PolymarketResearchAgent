"""Iteration 15 (X139 alternative / condition-3 baseline risk): does the Polymarket BOOK at the decision instant carry the side?
Operator taker orders of 10-20..22 (dcfit14_pred: frozen dc14 per-decision probability p_dc14_spot_dec, scored on 10-20..22 by
pre-registration 5). Book features from the l2ingest15 50-ms grid for BOTH outcomes at t = m0 - 210 ms (server clock; the capture's
book events of a match are stamped ~25 ms before its trade rows, so t is before the bot's arrival) and their changes over 100 / 250 /
1000 ms: best ask, depth at best + 0..4 c. Models (LightGBM binary on 'bought Up'), fit 10-20, scored once on 10-21..22:
BOOK (book only), DC14 (frozen p), DC14+BOOK. Accuracy per order, per wallet, and on the dc14-wrong orders (the late-trigger sixth).
Usage: python -I sidebook15.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
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
fit = (p.start_ts < 1792540800).to_numpy(); sc = ~fit
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=15)
rep = {"n_fit": int(fit.sum()), "n_score": int(sc.sum())}
P = {"DC14": p.p_dc14_spot_dec.to_numpy()[sc]}
for nm, cols in (("BOOK", BOOK), ("DC14+BOOK", ["ldc"] + BOOK)):
    m = lgb.train(PARAMS, lgb.Dataset(X.loc[fit, cols], y[fit]), 300)
    P[nm] = m.predict(X.loc[sc, cols])
    imp = pd.Series(m.feature_importance("gain"), index=cols); rep[f"top_{nm}"] = (imp / imp.sum()).sort_values(ascending=False).head(6).round(3).to_dict()
ys = y[sc]; ws = p.wallet.to_numpy()[sc]
wrong = (P["DC14"] > 0.5).astype(int) != ys
for nm, q in P.items():
    acc = (q > 0.5).astype(int) == ys
    rep[nm] = {"acc": round(float(acc.mean()), 4), **{w: round(float(acc[ws == w].mean()), 4) for w in ("DS", "GF", "XM")},
               "acc_on_dc14_wrong": round(float(acc[wrong].mean()), 4), "acc_on_dc14_right": round(float(acc[~wrong].mean()), 4)}
rep["dc14_wrong_share"] = round(float(wrong.mean()), 4)
json.dump(rep, open(OUT, "w"), indent=1)
print(json.dumps(rep, indent=1))
