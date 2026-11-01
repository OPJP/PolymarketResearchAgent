"""X136 step 2 (panel iter12 mechanics P2): the historical level-crossing switch rule (OWN STATE: the under-held outcome).
Lot BTC 5m maker fills after entry (cluster position != 0, not decided), block clock: the fill is predicted on the
under-held outcome u when F_CL(u) - h >= mid(u) - 0.01 (F_CL: report stamped b - 4, Gamma strike, 1.4 x 300-s vol; mid:
last clean print at b - 3), else on the held outcome. h chosen on STUDY over {0, 0.01, 0.03, 0.05, 0.07, 0.10, 0.15};
VALIDATE aggregate only. Baselines: held outcome; the posture sign (h = -0.01 equivalent); the cluster's previous fill side.
Scored per fill and at the first fill of every later run (switch decisions)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
d = pd.read_parquet(ROOT / ".cache/re/directional-maker/it12/typed_fills.parquet")
d = d[d.cl.notna() & d.Kg.notna() & d.v300.notna() & d.tau_cl.notna() & d.mid_up.notna() & ((d.en - d.st) == 300)].copy()
d = d.sort_values(["cid", "b"], kind="stable")
d["prev_up"] = d.groupby("cid").is_up.shift()
d["run"] = d.groupby("cid").is_up.transform(lambda s: (s != s.shift()).cumsum())
d["run_first"] = ~d.duplicated(["cid", "run"])
fu = norm.cdf(np.log(d.cl / d.Kg) / (1.4 * d.v300 * np.sqrt(np.maximum(d.tau_cl, 1.0))))
d["Fu"] = fu
dec = (d.mid_up - 0.5).abs() > 0.4
a = d[~dec & (d.inv_c != 0)].copy()
a["held_up"] = a.inv_c > 0
a["F_under"] = np.where(a.held_up, 1 - a.Fu, a.Fu)
a["mid_under"] = np.where(a.held_up, 1 - a.mid_up, a.mid_up)
a["y"] = a.is_up == 1
a["half"] = np.where(a.st >= 1793059200, "validate", "study")
def pred(x, h):
    under = (x.F_under - h >= x.mid_under - 0.01)
    return np.where(under, ~x.held_up, x.held_up)
res = {}
hs = [0.0, 0.01, 0.03, 0.05, 0.07, 0.10, 0.15]
st = a[a.half == "study"]
acc_s = {h: float((pred(st, h) == st.y).mean()) for h in hs}
h_best = max(acc_s, key=acc_s.get)
res["study_acc_by_h"] = acc_s; res["h_chosen_on_study"] = h_best
for half, x in a.groupby("half"):
    o = {"n": int(len(x)), "rule": float((pred(x, h_best) == x.y).mean()), "held": float((x.held_up == x.y).mean()),
         "posture": float(((x.Fu > x.mid_up) == x.y).mean()), "prev_fill": float(((x.prev_up == 1) == x.y)[x.prev_up.notna()].mean())}
    s = x[x.run_first & (x.run > 1)]
    o["switch_first_fills"] = {"n": int(len(s)), "rule": float((pred(s, h_best) == s.y).mean()), "held": float((s.held_up == s.y).mean()),
                               "posture": float(((s.Fu > s.mid_up) == s.y).mean()), "prev_fill": float(((s.prev_up == 1) == s.y)[s.prev_up.notna()].mean())}
    o["share_predicted_under"] = float((pred(x, h_best) != x.held_up).mean())
    res[half] = o
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_level_cross.json").write_text(json.dumps(res, indent=1))
