"""H1 clock-shift null (memory-light): per draw, dynamic features for FIT and TEST come from windows shifted by
1..72 windows (5 min..6 h); the full model (static + dynamic) is REFIT on shifted FIT and scored on shifted TEST.
Real AUC is the unshifted full model. p = (1 + #null >= real) / (1 + n)."""
import sys, json, time
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from common import *
from polyrea.analysis.updown import auc

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 0
d, G = load()
Pf, Pt = base_frame(d, "fit"), base_frame(d, "test")
Sf, St = static_frame(Pf), static_frame(Pt)
Y = {n: ((Pf.wallet == w).to_numpy().astype(int), (Pt.wallet == w).to_numpy().astype(int)) for n, w in W.items()}
fit = lambda X, y: make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(X, y)

def shift_map(per, rng):
    out = {}
    for cid, w in G[per].wins.items():
        for _ in range(50):
            s = int(rng.integers(1, 73)) * int(rng.choice([-1, 1]))
            if (w.start_ts + 300 * s) in G[per].by_start:
                out[cid] = s; break
    return out

def score(Dfn, Dtn):
    okf = Dfn[DYN].notna().all(axis=1).to_numpy(); okt = Dtn[DYN].notna().all(axis=1).to_numpy()
    Xf = pd.concat([Sf, Dfn[DYN]], axis=1)[okf]; Xt = pd.concat([St, Dtn[DYN]], axis=1)[okt]
    r = {}
    for n, (yf, yt) in Y.items():
        m = fit(Xf, yf[okf])
        r[n] = auc(m.predict_proba(Xt)[:, 1], yt[okt])
    return r

real = score(dyn_frame(G, "fit", Pf), dyn_frame(G, "test", Pt))
print("real", real, flush=True)
rng = np.random.default_rng(SEED)
nulls = {n: [] for n in W}
t0 = time.time()
for b in range(N):
    r = score(dyn_frame(G, "fit", Pf, shift_map("fit", rng)), dyn_frame(G, "test", Pt, shift_map("test", rng)))
    for n in W:
        nulls[n].append(r[n])
    if (b + 1) % 20 == 0:
        print(b + 1, round(time.time() - t0), {n: (round(float(np.max(v)), 5), int((np.array(v) >= real[n]).sum())) for n, v in nulls.items()}, flush=True)
        json.dump({"real": real, "nulls": nulls}, open(f"h1_null_partial_s{SEED}.json", "w"))
res = {n: {"real_auc": real[n], "null_mean": float(np.mean(v)), "null_p95": float(np.percentile(v, 95)), "null_max": float(np.max(v)), "n": len(v),
           "perm_p": float((1 + (np.array(v) >= real[n]).sum()) / (1 + len(v))), "real_minus_null_mean": real[n] - float(np.mean(v))} for n, v in nulls.items()}
print(json.dumps(res, indent=1))
json.dump(res, open(f"h1_null_s{SEED}.json", "w"), indent=1)
