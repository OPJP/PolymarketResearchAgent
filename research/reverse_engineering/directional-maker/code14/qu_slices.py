"""Iteration 14: slices of the uncensored quote unit (10-31 14-18 rebuilt table) under the frozen quote posture
(L 1,000 ms, k 1.0): by size class (62/250 vs 500/1000) and in the last minute (posture vs cheaper / favourite)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]; sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, sec_sigma, cl_source
a, b = 1793455200, 1793469600
A = pd.read_parquet(ROOT / ".cache/re/directional-maker" / f"it14_qu_rebuilt_{a}_{b}.parquet"); A = A[A.mid_prev.notna()]
E, M = fut_mid(a, b); sig = sec_sigma(E, M, 300)
clv = cl_source.cl_values(list(range(a - 5, b + 1)), allow_sealed=False, fetch=False)
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(A.w))); K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
t = A.s.to_numpy(np.int64); st = A.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy()
en = st + np.where(A.w.str.contains("-15m-").to_numpy(), 900, 300); left = en - t / 1000
cl = clv.reindex((t - 1000) // 1000).to_numpy(float); sg = sig.reindex(t // 1000).to_numpy(float)
F = norm.cdf((cl - A.w.map(K).to_numpy(float)) / (sg * np.sqrt(np.maximum(en - t / 1000, 1.0))))
mid = A.mid_prev.to_numpy(float); y = (A.sd == 1).to_numpy(float); P = (F > mid).astype(float); ok = np.isfinite(F)
ch = (mid < 0.5).astype(float)
def acc(p, m): m = m & ok; return [round(float((p[m] == y[m]).mean()), 3) if m.sum() else None, int(m.sum())]
big = A.dz.isin([500.0, 1000.0]).to_numpy(); small = A.dz.isin([62.0, 250.0]).to_numpy()
out = {"500_1000": acc(P, big), "62_250": acc(P, small), "62_250_cheaper": acc(ch, small),
       "last60_500": acc(P, big & (left < 60)), "last60_500_cheaper": acc(ch, big & (left < 60)), "last60_500_fav": acc(1 - ch, big & (left < 60)),
       "last60_mid_extreme_share": round(float((np.abs(mid - 0.5) > 0.4)[big & (left < 60) & ok].mean()), 3)}
print(json.dumps(out)); (HERE.parent / "results/iter14_qu_slices.json").write_text(json.dumps(out, indent=1))
# decided-window branch on the quote unit, by half (post-hoc check written after the slice above)
half = t < (a + (b - a) // 2) * 1000
dec = np.abs(mid - 0.5) > 0.4
comb = np.where(dec, 1 - ch, P)
res2 = {}
for nm, hm in (("fit", half), ("test", ~half)):
    res2[nm] = {"posture_500": acc(P, big & hm), "decided_fav_else_posture_500": acc(comb, big & hm),
                "decided_share_500": round(float(dec[big & hm & ok].mean()), 3), "posture_on_decided": acc(P, big & hm & dec),
                "fav_on_decided": acc(1 - ch, big & hm & dec), "cheaper_on_decided": acc(ch, big & hm & dec)}
print(json.dumps(res2)); out["decided_branch_by_half"] = res2
(HERE.parent / "results/iter14_qu_slices.json").write_text(json.dumps(out, indent=1))
