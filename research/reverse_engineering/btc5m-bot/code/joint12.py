"""Iteration 12, panel iter11 mechanics P3 steps 2-3 (X106): (2) the joint-take excess of wallet pairs at clean onsets,
P(w and w' decide on o | k) - P(w | k) P(w' | k), within bins of the public FULL score (evt10-style logistic fitted on
the other half); (3) rerouting: when wallet w has an order in flight (its own decision in [tau - 300, tau + 150) ms), do
the other wallets take the onset more than when w is free? Decisions = it11/large_dec (arrival a); label window
[tau + 150, tau + 700) ms as in onset11."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from cbx12 import design
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
dec = pd.read_parquet(f"{C}/it11/large_dec.parquet")
W = ["DS", "GF", "XM"]
DEC = {(int(st), w): (np.sort(g.a.to_numpy(float)), g.sort_values("a").up.to_numpy(bool)) for (st, w), g in dec.groupby(["st", "w"])}
E = {}
for nm in ("A", "C"):
    e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
    e = e[e.clean.astype(bool)].reset_index(drop=True)
    o = (e.sgn > 0).to_numpy(); tau = e.tau.to_numpy(float); st = e.st.to_numpy(np.int64)
    for w in W:
        yw = np.zeros(len(e)); busy = np.zeros(len(e))
        for i in range(len(e)):
            a, up = DEC.get((int(st[i]), w), (np.zeros(0), np.zeros(0, bool)))
            j0, j1 = np.searchsorted(a, tau[i] + 150), np.searchsorted(a, tau[i] + 700)
            yw[i] = float(np.any(up[j0:j1] == o[i])) if j1 > j0 else 0.0
            b0, b1 = np.searchsorted(a, tau[i] - 300), np.searchsorted(a, tau[i] + 150)
            busy[i] = float(b1 > b0)
        e["y" + w] = yw; e["busy" + w] = busy
    E[nm] = e
res = {}
for fit, sc in (("A", "C"), ("C", "A")):
    m = LogisticRegression(max_iter=2000).fit(design(E[fit], False), E[fit].y)
    e = E[sc]; p = m.predict_proba(design(e, False))[:, 1]
    q = np.quantile(p, [0.5, 0.8, 0.95])
    bins = np.digitize(p, q)
    out = {}
    for i, w1 in enumerate(W):
        for w2 in W[i + 1:]:
            ex, n = 0.0, 0
            per = []
            for b in np.unique(bins):
                mm = bins == b
                pj = float((e["y" + w1][mm] * e["y" + w2][mm]).mean()); p1 = float(e["y" + w1][mm].mean()); p2 = float(e["y" + w2][mm].mean())
                per.append([int(b), round(pj, 4), round(p1 * p2, 4)])
                ex += (pj - p1 * p2) * mm.sum(); n += mm.sum()
            out[f"{w1}-{w2}"] = {"joint_minus_product_weighted": round(ex / n, 5), "by_score_bin[bin, joint, product]": per}
    rr = {}
    for w in W:
        others = [x for x in W if x != w]
        yo = np.clip(sum(e["y" + x] for x in others), 0, 1)
        bz = e["busy" + w].to_numpy() == 1
        rr[w] = {"busy_share": round(float(bz.mean()), 4), "P(other takes | w busy)": round(float(yo[bz].mean()), 4) if bz.any() else None,
                 "P(other takes | w free)": round(float(yo[~bz].mean()), 4),
                 "P(other takes | w busy, top score bin)": round(float(yo[bz & (bins == 3)].mean()), 4) if (bz & (bins == 3)).any() else None,
                 "P(other takes | w free, top score bin)": round(float(yo[~bz & (bins == 3)].mean()), 4) if (~bz & (bins == 3)).any() else None}
    res[f"score_fit_{fit}_on_{sc}"] = {"joint_excess": out, "rerouting": rr}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/joint12.json", "w"), indent=1)
