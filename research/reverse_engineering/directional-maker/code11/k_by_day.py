"""Iteration 11 (X111 (b) engine change / C4 bot versions): the sigma multiplier k of the posture per lot day and 6-h block.
Per-fill posture with the real Chainlink value (T_hat - 1,432 ms; where the detached fetch has it), Gamma strike, mid = last
clean print at b - 3, sigma = k x v300; accuracy for k in a fixed grid; the best k per day. Descriptive (version detection);
VALIDATE per-day aggregates only; no rule is chosen from it.
    python code11/k_by_day.py
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import cl_source  # noqa: E402
from side_inblock import that  # noqa: E402
C = ROOT / ".cache/re/directional-maker"
KS = (0.5, 0.7, 0.85, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5)
ptb = pd.read_parquet(C / "cl/ptb_lot.parquet")
K = dict(zip(ptb.start_ts.astype(int), ptb.ptb.astype(float)))
clv = cl_source._cache()
rows = []
for sp, fn in (("study", "b1_takers_study"), ("validate", "b1_takers_valid")):
    v = pd.read_parquet(C / f"it9/volhist_{sp}.parquet", columns=["txh", "b", "st", "en", "is_up", "mid_up", "v300", "price"])
    t = pd.read_parquet(C / f"{fn}.parquet", columns=["tx", "sign_ms"])
    t["tx"] = t.tx.str.lower()
    t = t.drop_duplicates("tx").set_index("tx")
    v["txh"] = v.txh.str.lower()
    v["T_hat"] = that(v.txh.map(t.sign_ms), v.b.astype(float) * 1000)
    v["cl"] = ((v.T_hat - 1432) // 1000).astype(np.int64).map(lambda s: clv.get(int(s), np.nan))
    v["K"] = v.st.map(K)
    v["tau"] = np.maximum(v.en - v.T_hat / 1000.0, 1.0)
    rows.append(v.dropna(subset=["cl", "K", "mid_up"]))
D = pd.concat(rows)
x = np.log(D.cl / D.K).to_numpy()
y = D.is_up.to_numpy() == 1
for k in KS:
    f = norm.cdf(x / (k * D.v300.to_numpy() * np.sqrt(D.tau.to_numpy())))
    D[f"a{k}"] = ((f > D.mid_up.to_numpy()) == y).astype(float)
D["day"] = pd.to_datetime(D.b, unit="s").dt.strftime("%m-%d")
D["blk"] = pd.to_datetime(D.b // 21600 * 21600, unit="s").dt.strftime("%m-%d %H")
D["fav"] = D.price > 0.5
out = {"by_day": {}, "by_block": {}}
for nm, col in (("by_day", "day"), ("by_block", "blk")):
    for d, g in D.groupby(col):
        acc = {k: round(float(g[f"a{k}"].mean()), 3) for k in KS}
        kb = max(acc, key=acc.get)
        out[nm][d] = {"n": int(len(g)), "best_k": kb, "acc_best": acc[kb], "acc_1.4": acc[1.4], "acc_0.85": acc[0.85], "fav_share": round(float(g.fav.mean()), 3)}
print(json.dumps(out["by_day"], indent=0))
for d, r in out["by_block"].items():
    print(d, r)
(HERE.parent / "results" / "iter11_k_by_day.json").write_text(json.dumps(out, indent=1))
