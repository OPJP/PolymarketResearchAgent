"""X135 / X130: the tracer's quote unit. P(tracer re-sign at or above its own ex-tracer touch) by the Chainlink edge over
that touch, F_own(L = 1250 ms, k = 1.4) - bid_ex, and by the edge over the ex-tracer mid; uncensored re-sign sample."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
R = pd.read_parquet(ROOT / ".cache/re/directional-maker/it13/tracer_features_own.parquet")
R["att"] = (R.p_own >= R.bid_ex - 1e-9).astype(int)
R["e_touch"] = R.F2 - R.bid_ex
R["e_mid"] = R.F2 - R.mid_ex
out = {"n": int(len(R)), "at_share": float(R.att.mean())}
for col in ("e_touch", "e_mid"):
    q = pd.cut(R[col], [-1, -0.3, -0.15, -0.05, 0, 0.05, 0.15, 0.3, 1])
    t = R.groupby(q, observed=True).agg(n=("att", "size"), atshare=("att", "mean"), rel=("p_own", lambda s: float((s - R.loc[s.index, "bid_ex"]).median())))
    out[col] = {str(k): {"n": int(v.n), "at_share": round(float(v.atshare), 3), "median_rel": round(float(v.rel), 3)} for k, v in t.iterrows()}
from sklearn.metrics import roc_auc_score
out["auc_at_touch_by_e_touch"] = float(roc_auc_score(R.att, R.e_touch))
out["auc_at_touch_by_e_mid"] = float(roc_auc_score(R.att, R.e_mid))
out["auc_at_touch_by_age"] = float(roc_auc_score(R.att, -R.age))
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter13_tracer_touch.json").write_text(json.dumps(out, indent=1))
