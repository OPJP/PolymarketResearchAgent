"""X91 / X94: mo-money's posture deficit, decomposed by fill class on the exact live clock (10-31 14-18): per wallet the
share of class (i) quote moves, and the Chainlink posture at the post on class (i) and class (ii) fills."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import cl_source
from tracer_laws import spot
OUT = ROOT / ".cache/re/directional-maker/it13"
CL = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach", "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona"}
o = pd.read_parquet(OUT / "fills_posts.parquet")
S = pd.read_parquet(OUT / "sched_adds.parquet"); T = pd.read_parquet(OUT / "tracer_events.parquet")
A = pd.concat([S[["w", "s", "sd", "p", "dz", "bb", "ba"]], T[["w", "s", "sd", "p", "bb", "ba"]].assign(dz=T["size"])], ignore_index=True)
A["p"] = A.p.round(3); A["dz"] = A.dz.round(2)
A = A.drop_duplicates(["w", "s", "sd", "p", "dz"]).set_index(["w", "s", "sd", "p", "dz"])
o = o[o.post_ms.notna()].copy(); o["post_ms"] = o.post_ms.astype(np.int64)
bbba = A.reindex(list(zip(o.w, o.post_ms, o.sd.astype(int), o.bp.round(3), o.orig.round(2))))[["bb", "ba"]].to_numpy()
o["mid"] = (bbba[:, 0] + bbba[:, 1]) / 2
from polyrea.workflows.updown_study import fetch_windows
K = {}
for m in fetch_windows(sorted(set(o.w))).values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
o["K"] = o.w.map(K); o["start"] = o.w.str.rsplit("-", n=1).str[1].astype(int)
o["end"] = o.start + np.where(o.w.str.contains("-15m-"), 900, 300)
res = {}
for L in (1000, 1250, 1500, 2000):
    clv = cl_source.cl_values(sorted(set(((o.post_ms - L) // 1000).astype(int))), allow_sealed=False, fetch=False)
    sp = spot(int(o.post_ms.min() // 1000) - 7200, int(o.post_ms.max() // 1000) + 5)
    cl = ((o.post_ms - L) // 1000).map(clv).to_numpy(float)
    sig = sp.sigma((o.post_ms // 1000).to_numpy(), look=300) * 1.4
    tau = np.maximum(o.end.to_numpy() - o.post_ms.to_numpy() / 1000, 1.0)
    F = norm.cdf(np.log(cl / o.K.to_numpy(float)) / (sig * np.sqrt(tau)))
    ok = np.isfinite(F) & np.isfinite(o.mid.to_numpy())
    hit = (F > o.mid.to_numpy()) == (o.is_up == 1).to_numpy()
    r = {}
    for ad, nm in CL.items():
        m = ok & (o.maker == ad).to_numpy()
        c1 = m & (o.post_at_touch == 1).to_numpy(); c2 = m & (o.post_at_touch == 0).to_numpy()
        r[nm] = {"n": int(m.sum()), "class_i_share": round(float(c1.sum() / max(m.sum(), 1)), 3), "posture_all": round(float(hit[m].mean()), 3),
                 "posture_class_i": round(float(hit[c1].mean()), 3), "posture_class_ii": round(float(hit[c2].mean()), 3) if c2.any() else None}
    res[f"L{L}"] = r
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_wallet_class.json").write_text(json.dumps(res, indent=1))
