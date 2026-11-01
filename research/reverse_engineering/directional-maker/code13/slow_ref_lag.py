"""X134 control: on the lot (VALIDATE aggregate), is the TWAP-60 win a clock-alignment artefact? Current-report posture at
stamps b - j (j = 1..10, where the endpoint grid has the stamp) vs the TWAP-60 posture on the same fills; and on fills
whose in-block execution-order clock places the match early or late in the block second (it11 inblock tables are not
needed: the block second b and stamp lags are enough for this check)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source
d = pd.read_parquet(ROOT / ".cache/re/directional-maker/it12/typed_fills.parquet")
d = d[d.Kg.notna() & d.v300.notna() & d.tau_cl.notna() & d.mid_up.notna() & ((d.en - d.st) == 300)].copy()
d = d[(d.mid_up - 0.5).abs() <= 0.4]
cache = cl_source._cache()
ks = np.array(sorted(cache.keys()), dtype=np.int64); vs = np.array([cache[k] for k in ks], dtype=float)
pos = {int(k): i for i, k in enumerate(ks)}
b = d.b.to_numpy(np.int64)
tw = np.full(len(d), np.nan)
for n_, bb in enumerate(b):
    i0, i1 = np.searchsorted(ks, bb - 64), np.searchsorted(ks, bb - 4, side="right")
    if i1 - i0 >= 20: tw[n_] = vs[i0:i1].mean()
sig = 1.4 * d.v300.to_numpy() * np.sqrt(np.maximum(d.tau_cl.to_numpy(float), 1.0))
K = d.Kg.to_numpy(float); mid = d.mid_up.to_numpy(); y = (d.is_up == 1).to_numpy()
half = np.where(d.st >= 1793059200, "validate", "study")
ptw = norm.cdf(np.log(tw / K) / sig) > mid
res = {}
for h in ("study", "validate"):
    r = {}
    for j in range(0, 11):
        v = np.array([vs[pos[int(x - j)]] if int(x - j) in pos else np.nan for x in b])
        m = np.isfinite(v) & np.isfinite(tw) & (half == h)
        if m.sum() < 30:
            continue
        pc = norm.cdf(np.log(v / K) / sig) > mid
        dis = m & (pc != ptw)
        r[f"b-{j}"] = {"n": int(m.sum()), "current": round(float((pc == y)[m].mean()), 3), "twap60": round(float((ptw == y)[m].mean()), 3),
                       "disagree_n": int(dis.sum()), "twap_wins": round(float((ptw == y)[dis].mean()), 3) if dis.any() else None}
    res[h] = r
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_slow_ref_lag.json").write_text(json.dumps(res, indent=1))
