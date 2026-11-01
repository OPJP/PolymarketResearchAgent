"""X134 (panel iter12 information I12-5): slow Chainlink references for the side. At each lot BTC 5m maker fill with the
endpoint grid around it (X102 / X90 caches through cl_source._cache(); stamps <= b - 4 only, point-in-time): TWAP-60 =
mean of the available 1-s values stamped in [b - 64, b - 4]; EWMA(tau 10 / 30 / 60 s) over the same stamps; the
current report = the value stamped b - 4. Posture = sign(digital(ref; Gamma strike, 1.4 x 300-s vol) - Up mid at b - 3).
Disagreement cells (slow posture != current posture): which one the fill follows, by half, session (12-21 UTC = US) and
calldata rung class (500 x 2^k, 62/250, other). Fills need >= 20 grid values in the 60-s span."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
import cl_source
d = pd.read_parquet(ROOT / ".cache/re/directional-maker/it12/typed_fills.parquet")
d = d[d.Kg.notna() & d.v300.notna() & d.tau_cl.notna() & d.mid_up.notna() & ((d.en - d.st) == 300)].copy()
cache = cl_source._cache()
ks = np.array(sorted(cache.keys()), dtype=np.int64); vs = np.array([cache[k] for k in ks], dtype=float)
rows = []
for r in d.itertuples(index=False):
    a, b = int(r.b) - 64, int(r.b) - 4
    i0, i1 = np.searchsorted(ks, a), np.searchsorted(ks, b, side="right")
    if i1 - i0 < 20 or ks[i1 - 1] != b:
        rows.append((np.nan,) * 5); continue
    t, v = ks[i0:i1], vs[i0:i1]
    out = [v.mean()]
    for tau in (10, 30, 60):
        wgt = np.exp(-(b - t) / tau); out.append(float((wgt * v).sum() / wgt.sum()))
    out.append(v[-1])
    rows.append(tuple(out))
R = pd.DataFrame(rows, columns=["twap60", "ew10", "ew30", "ew60", "cur"], index=d.index)
d = d.join(R)
d = d[d.cur.notna()].copy()
sig = 1.4 * d.v300.to_numpy() * np.sqrt(np.maximum(d.tau_cl.to_numpy(float), 1.0))
y = (d.is_up == 1).to_numpy()
post = {c: norm.cdf(np.log(d[c].to_numpy() / d.Kg.to_numpy(float)) / sig) > d.mid_up.to_numpy() for c in ("twap60", "ew10", "ew30", "ew60", "cur")}
d["half"] = np.where(d.st >= 1793059200, "validate", "study")
d["us"] = ((d.st % 86400) // 3600).between(12, 20)
o = d.orig.to_numpy()
d["cls"] = np.where(np.isin(o, [500, 1000, 2000]), "500", np.where(np.isin(o, [62, 250, 125]), "62_250", "other"))
dec = ((d.mid_up - 0.5).abs() > 0.4).to_numpy()
res = {"n_fills_with_grid": int(len(d)), "windows": int(d.cid.nunique())}
for half in ("study", "validate"):
    m0 = (d.half == half).to_numpy() & ~dec
    h = {"n": int(m0.sum()), "cur": float((post["cur"] == y)[m0].mean()) if m0.any() else None}
    for c in ("twap60", "ew10", "ew30", "ew60"):
        dis = m0 & (post[c] != post["cur"])
        h[c] = {"all": float((post[c] == y)[m0].mean()) if m0.any() else None, "disagree_n": int(dis.sum()),
                "disagree_windows": int(d.cid[dis].nunique()), "slow_wins_in_disagreement": float((post[c] == y)[dis].mean()) if dis.any() else None}
        for nm, mm in (("US", d.us.to_numpy()), ("off", ~d.us.to_numpy()), ("62_250", (d.cls == "62_250").to_numpy()), ("500", (d.cls == "500").to_numpy())):
            k = dis & mm
            h[c]["disagree_" + nm] = [int(k.sum()), float((post[c] == y)[k].mean()) if k.any() else None]
    res[half] = h
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_slow_ref.json").write_text(json.dumps(res, indent=1))
