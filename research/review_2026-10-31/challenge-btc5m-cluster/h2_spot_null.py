"""Maker-side spot-timing match (H2b): do Kraken spot returns over the last 2/10/30 s (available 2 s before the fill)
predict which PASSIVE buy fills are the wallet's, beyond static price/time? Model: static + sside_{2,10,30}, fit on FIT.
Null: spot features taken from a window 5 min..6 h away at the same relative time (spot-clock shift), model refit."""
import sys, json, time
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import auc, decision_metrics
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
SP = ["sside_2", "sside_10", "sside_30"]
d, G = load()
def mframe(per):
    P = d[per]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy(); P["rel"] = P.ts - P.start_ts; return P
Pf, Pt = mframe("fit"), mframe("test")
Sf, St = static_frame(Pf), static_frame(Pt)
def shift_map(per, rng):
    out = {}
    for cid, w in G[per].wins.items():
        for _ in range(50):
            s = int(rng.integers(1, 73)) * int(rng.choice([-1, 1]))
            if (w.start_ts + 300 * s) in G[per].by_start: out[cid] = s; break
    return out
def run(Df, Dt):
    okf = Df[SP].notna().all(axis=1).to_numpy(); okt = Dt[SP].notna().all(axis=1).to_numpy()
    Xf = pd.concat([Sf, Df[SP]], axis=1)[okf]; Xt = pd.concat([St, Dt[SP]], axis=1)[okt]
    r = {}
    for n, w in W.items():
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(Xf, (Pf.wallet == w).to_numpy().astype(int)[okf])
        r[n] = auc(m.predict_proba(Xt)[:, 1], (Pt.wallet == w).to_numpy().astype(int)[okt])
    return r
real = run(dyn_frame(G, "fit", Pf), dyn_frame(G, "test", Pt)); print("real", real, flush=True)
rng = np.random.default_rng(3); nulls = {n: [] for n in W}; t0 = time.time()
for b in range(N):
    r = run(dyn_frame(G, "fit", Pf, shift_map("fit", rng)), dyn_frame(G, "test", Pt, shift_map("test", rng)))
    for n in W: nulls[n].append(r[n])
    if (b + 1) % 20 == 0: print(b + 1, round(time.time() - t0), {n: (round(max(v), 4), int(sum(x >= real[n] for x in v))) for n, v in nulls.items()}, flush=True)
res = {n: {"real_auc": real[n], "n": len(v), "null_mean": float(np.mean(v)), "null_max": float(np.max(v)), "perm_p": float((1 + sum(x >= real[n] for x in v)) / (1 + len(v)))} for n, v in nulls.items()}
print(json.dumps(res, indent=1)); json.dump(res, open("h2_spot_null.json", "w"), indent=1)
