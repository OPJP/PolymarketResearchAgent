"""X105 (panel iter10 information I10-5): onset of the Chainlink noise regime. Lag-1 autocorrelation of 1-s changes of the
endpoint Chainlink values (cl_source._cache(): released lot and pre-H stamps only) over consecutive-second triples, by
UTC day and by hour on 10-29..30; plus the live development hours of 10-31 from the recordings."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source
c = cl_source._cache()
s = pd.Series(c).sort_index()
t = s.index.to_numpy(np.int64); v = s.to_numpy(float)
i = np.where((t[2:] - t[1:-1] == 1) & (t[1:-1] - t[:-2] == 1))[0]
d1 = v[i + 1] - v[i]; d2 = v[i + 2] - v[i + 1]; tt = t[i + 2]
D = pd.DataFrame({"t": tt, "d1": d1, "d2": d2})
D["day"] = pd.to_datetime(D.t // 86400 * 86400, unit="s").dt.strftime("%m-%d")
D["hour"] = pd.to_datetime(D.t // 3600 * 3600, unit="s").dt.strftime("%m-%d %H")
ac = lambda g: float(np.corrcoef(g.d1, g.d2)[0, 1]) if len(g) > 30 else None
out = {"by_day": {k: [int(len(g)), ac(g)] for k, g in D.groupby("day")},
       "by_hour_1029_1030": {k: [int(len(g)), ac(g)] for k, g in D[D.t >= 1793232000].groupby("hour")}}
lv = cl_source.cl_values(list(range(1793448000, 1793469600)), allow_sealed=False, fetch=False)
L = pd.Series(lv).dropna().sort_index()
if len(L):
    lt = L.index.to_numpy(np.int64); lvv = L.to_numpy(float)
    j = np.where((lt[2:] - lt[1:-1] == 1) & (lt[1:-1] - lt[:-2] == 1))[0]
    E = pd.DataFrame({"t": lt[j + 2], "d1": lvv[j + 1] - lvv[j], "d2": lvv[j + 2] - lvv[j + 1]})
    E["hour"] = pd.to_datetime(E.t // 3600 * 3600, unit="s").dt.strftime("%m-%d %H")
    out["live_1031_by_hour"] = {k: [int(len(g)), ac(g)] for k, g in E.groupby("hour")}
print(json.dumps(out, indent=0)[:3000])
(HERE.parent / "results/iter13_noise_onset.json").write_text(json.dumps(out, indent=1))
