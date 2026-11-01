"""Iteration 11 (C4 bot versions, X75): the posture's best sigma multiplier per day over BUILD (10-09..22) and the lot with
the Binance stand-in (code9/vol_hist.py inputs: Binance S at b - 3, Binance TWAP-60 strike, mid = last clean print at b - 3,
tau = end - (b - 2)), k grid 0.5-2.5. Checks that the stand-in reproduces the lot's step and looks for earlier steps.
VALIDATE days: per-day aggregates only.
    python code11/k_by_day_bn.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker"
KS = (0.5, 0.7, 0.85, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5)
D = pd.concat([pd.read_parquet(C / f"it9/volhist_{s}.parquet", columns=["b", "is_up", "mid_up", "v300", "S", "K", "tau", "price"])
               for s in ("build", "study", "validate")])
x = np.log(D.S / D.K).to_numpy()
y = D.is_up.to_numpy() == 1
for k in KS:
    f = norm.cdf(x / (k * D.v300.to_numpy() * np.sqrt(D.tau.to_numpy())))
    D[f"a{k}"] = ((f > D.mid_up.to_numpy()) == y).astype(float)
D["day"] = pd.to_datetime(D.b, unit="s").dt.strftime("%m-%d %a")
out = {}
for d, g in D.groupby("day"):
    acc = {k: round(float(g[f"a{k}"].mean()), 3) for k in KS}
    kb = max(acc, key=acc.get)
    out[d] = {"n": int(len(g)), "best_k": kb, "acc_best": acc[kb], "acc_0.7": acc[0.7], "acc_1.4": acc[1.4], "acc_2.0": acc[2.0],
              "fav_share": round(float((g.price > 0.5).mean()), 3)}
    print(d, out[d])
(HERE.parent / "results" / "iter11_k_by_day_binance.json").write_text(json.dumps(out, indent=1))
