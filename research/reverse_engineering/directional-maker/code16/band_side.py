"""iteration 16, T6 (pre-registered 09:45 UTC): R8b public side = decided -> cheaper; |F_cl - mid| < 0.05 -> cheaper; else
the Chainlink posture; vs R8's public side, on the lot's typed fills (it12/typed_fills.parquet), STUDY and VALIDATE."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
HALF_V = 1793232000
V = pd.read_parquet(C / "it12" / "typed_fills.parquet")
y = (V.is_up == 1).to_numpy()
mid = V.mid_up.to_numpy()
f = np.where(np.isfinite(V.f_cl) & np.isfinite(mid), V.f_cl, V.f_bn)
post = f > mid
dec = np.abs(mid - 0.5) > 0.4
cheap = mid < 0.5
dead = np.abs(f - mid) < 0.05
r8 = np.where(dec, cheap, post)
r8b = np.where(dec, cheap, np.where(dead, cheap, post))
out = {}
for sp in ("study", "validate"):
    ms = (V.sp == sp).to_numpy() & np.isfinite(mid) & np.isfinite(f)
    rec = {"n": int(ms.sum()), "dead_zone_share": round(float((dead & ~dec)[ms].mean()), 4)}
    for nm, r in (("R8", r8), ("R8b", r8b), ("cheaper", cheap)):
        a = r == y
        rec[nm] = {"fill": round(float(a[ms].mean()), 4), "dead_zone": round(float(a[ms & dead & ~dec].mean()), 4),
                   "per_wallet": {w: round(float(a[ms & (V.w == w).to_numpy()].mean()), 4) for w in ("almach", "bosona", "momoney")}}
        if sp == "validate":
            h1 = (V.b < HALF_V).to_numpy()
            rec[nm]["halves"] = [round(float(a[ms & h1].mean()), 4), round(float(a[ms & ~h1].mean()), 4)]
    rec["posture_in_dead_zone"] = round(float((post == y)[ms & dead & ~dec].mean()), 4)
    out[sp] = rec
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter16_band_side.json").write_text(json.dumps(out, indent=1))
