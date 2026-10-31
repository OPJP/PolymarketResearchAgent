"""H2 decision-level match: do the tape-anchored maker's state variables (fill price relative to the last implied
price of that side known 2 s earlier, plus recent tape/spot moves) predict which PASSIVE buy fills are the wallet's,
beyond static price/time? Same design as H1: logistic model fit on FIT, AUC on TEST vs (a) static-only model
(window bootstrap of the gain) and (b) clock-shift null (dynamic features from a window 5 min..6 h away, model refit)."""
import sys, json, time
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import auc, decision_metrics

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
d, G = load()
def mframe(per):
    P = d[per]["maker_prints"]
    P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy()
    P["rel"] = P.ts - P.start_ts
    return P
DYN2 = DYN + ["dev"]
def dframe(per, P, sm=None):
    D = dyn_frame(G, per, P, sm)
    D["dev"] = D["up_last_side"] - P.price.to_numpy()   # how far below the last implied price the fill is
    return D[DYN2]
Pf, Pt = mframe("fit"), mframe("test")
Sf, St = static_frame(Pf), static_frame(Pt)
fitm = lambda X, y: make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(X, y)
def shift_map(per, rng):
    out = {}
    for cid, w in G[per].wins.items():
        for _ in range(50):
            s = int(rng.integers(1, 73)) * int(rng.choice([-1, 1]))
            if (w.start_ts + 300 * s) in G[per].by_start:
                out[cid] = s; break
    return out
def run(Df, Dt, with_dyn=True):
    okf = Df.notna().all(axis=1).to_numpy(); okt = Dt.notna().all(axis=1).to_numpy()
    Xf = (pd.concat([Sf, Df], axis=1) if with_dyn else Sf)[okf]; Xt = (pd.concat([St, Dt], axis=1) if with_dyn else St)[okt]
    r = {}
    for n, w in W.items():
        yf = (Pf.wallet == w).to_numpy().astype(int)[okf]; yt = (Pt.wallet == w).to_numpy().astype(int)[okt]
        m = fitm(Xf, yf); s = m.predict_proba(Xt)[:, 1]
        r[n] = (auc(s, yt), s, yt, Pt.condition_id.to_numpy()[okt])
    return r
Df, Dt = dframe("fit", Pf), dframe("test", Pt)
real = run(Df, Dt); stat = run(Df, Dt, with_dyn=False)
res = {}
for n in W:
    a, s, yt, cids = real[n]; a0, s0, _, _ = stat[n]
    uc, inv = np.unique(cids, return_inverse=True); groups = [np.nonzero(inv == i)[0] for i in range(len(uc))]
    rb = np.random.default_rng(1); gains = []
    for _ in range(200):
        ix = np.concatenate([groups[i] for i in rb.integers(0, len(uc), len(uc))])
        gains.append(auc(s[ix], yt[ix]) - auc(s0[ix], yt[ix]))
    res[n] = {"test_wallet_passive_buys": int(yt.sum()), "auc_full": a, "auc_static": a0, "gain": a - a0, "gain_ci95": [float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))], "gain_p_le0": float(np.mean(np.array(gains) <= 0))}
print("real", json.dumps(res, default=float), flush=True)
rng = np.random.default_rng(0); nulls = {n: [] for n in W}; t0 = time.time()
for b in range(N):
    r = run(dframe("fit", Pf, shift_map("fit", rng)), dframe("test", Pt, shift_map("test", rng)))
    for n in W: nulls[n].append(r[n][0])
    if (b + 1) % 10 == 0: print(b + 1, round(time.time() - t0), {n: (round(max(v), 5), int(sum(x >= res[n]["auc_full"] for x in v))) for n, v in nulls.items()}, flush=True)
for n in W:
    v = np.array(nulls[n]); res[n]["clock_shift_null"] = {"n": len(v), "mean": float(v.mean()), "max": float(v.max()), "perm_p": float((1 + (v >= res[n]["auc_full"]).sum()) / (1 + len(v)))}
print(json.dumps(res, indent=1, default=float))
json.dump(res, open("h2_match.json", "w"), indent=1, default=float)
