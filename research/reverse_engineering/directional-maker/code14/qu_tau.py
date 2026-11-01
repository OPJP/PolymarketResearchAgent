"""Iteration 14: does the quote posture's sigma scale differ with time left? Best k by time-left band on the quote unit
(500/1000 at-touch posts, 10-31 14-18), stamp lag 1,000 ms, fit 14-16 / test 16-18 reported per band."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, sec_sigma, cl_source
a, b = 1793455200, 1793469600
A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna() & A.dz.isin([500.0, 1000.0])]
E, M = fut_mid(a, b); sig = sec_sigma(E, M, 300)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(A.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
t = A.s.to_numpy(np.int64); st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300); tau = np.maximum(en - t / 1000, 1.0)
cl = clv.reindex((t - 1000) // 1000).to_numpy(float); s0 = sig.reindex(t // 1000).to_numpy(float)
kk = A.w.map(K).to_numpy(float); mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float)
half = t < (a + (b - a) // 2) * 1000
out = {}
for lo, hi in ((0, 60), (60, 120), (120, 300), (300, 600), (600, 900)):
    band = (tau >= lo) & (tau < hi)
    r = {}
    for k in (0.3, 0.5, 0.7, 1.0, 1.4, 2.0, 3.0):
        F = norm.cdf((cl - kk) / (k * s0 * np.sqrt(tau))); P = (F > mid).astype(float); ok = np.isfinite(F) & band
        r[f"k{k}"] = [round(float((P[ok & half] == y[ok & half]).mean()), 3) if (ok & half).sum() else None,
                      round(float((P[ok & ~half] == y[ok & ~half]).mean()), 3) if (ok & ~half).sum() else None, int(ok.sum())]
    out[f"{lo}-{hi}"] = r
print(json.dumps(out)); (HERE.parent / "results/iter14_qu_tau.json").write_text(json.dumps(out, indent=1))
