"""Iteration 8 (X36 first step, live): how executable is the decoded trigger? On the later development interval C (10-31
16:33-17:55; never used for fitting) the frozen decision-level hazard of final_rule (exam feeds) scores every 100-ms grid point;
take the top-q grid points (q = the label's base rate, i.e. as many decisions as the wallet's matches) and report precision /
recall (a grid point is a hit if a cluster taker match on that outcome follows in [t + 100, t + 600)), against the
Polymarket-activity baseline and random. Writes results/overlap8.json."""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_rule as FR
from live8 import fills_for, OWN
own, a, b = OWN["C"]
f, _, _ = fills_for(own, a, b)
y, F, B, U = FR._live_hazard_data(f, a, b)
sf = F @ np.array(FR.HAZ_FULL_COEF[1:]) + FR.HAZ_FULL_COEF[0]
sb = B @ np.array(FR.HAZ_BASE_COEF[1:]) + FR.HAZ_BASE_COEF[0]
res = {"grid_points": int(len(y)), "base_rate": round(float(y.mean()), 4)}
for mult in (1, 2, 5):
    q = min(1.0, mult * y.mean())
    for nm, sc in (("full", sf), ("pm_activity_baseline", sb)):
        thr = np.quantile(sc, 1 - q)
        sel = sc >= thr
        res[f"top_{mult}x_base_{nm}"] = {"share_flagged": round(float(sel.mean()), 4), "precision": round(float(y[sel].mean()), 4), "recall": round(float(y[sel].sum() / max(y.sum(), 1)), 4),
                                         "lift": round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3)}
print(json.dumps(res, indent=0))
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "overlap8.json"), "w"), indent=1)
