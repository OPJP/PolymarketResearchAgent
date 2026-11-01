"""X91 follow-up: are the class-(ii) resting-rung fills stale quotes (posted on the posture side, filled after the posture
flipped) or placed against the posture from the start? Development block 10-31 14-18. Posture at the post (F_up at stamp
lag 1,000 ms vs the Up mid carried by the add's price_change row) and at the fill (F_up at the fill's server ms vs the
mid implied by the order being at the touch: its own Up-book price +- 0.005)."""
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
o["mid_post"] = (bbba[:, 0] + bbba[:, 1]) / 2
o["mid_fill"] = np.where(o.sd == 1, o.bp + 0.005, o.bp - 0.005)
from polyrea.workflows.updown_study import fetch_windows
K = {}
for m in fetch_windows(sorted(set(o.w))).values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
o["K"] = o.w.map(K); o["start"] = o.w.str.rsplit("-", n=1).str[1].astype(int)
o["end"] = o.start + np.where(o.w.str.contains("-15m-"), 900, 300)
L = 1000
st = sorted(set(((o.post_ms - L) // 1000).astype(int)) | set(((o.fill_ms - L) // 1000).astype(int)))
clv = cl_source.cl_values(st, allow_sealed=False, fetch=False)
sp = spot(int(o.post_ms.min() // 1000) - 7200, int(o.fill_ms.max() // 1000) + 5)
def F(ms):
    cl = ((ms - L) // 1000).map(clv).to_numpy(float)
    sig = sp.sigma((ms // 1000).to_numpy(), look=300) * 1.4
    tau = np.maximum(o.end.to_numpy() - ms.to_numpy() / 1000, 1.0)
    return norm.cdf(np.log(cl / o.K.to_numpy(float)) / (sig * np.sqrt(tau)))
y = (o.is_up == 1).to_numpy()
pp = (F(o.post_ms) > o.mid_post.to_numpy()) == y      # posture agreed with the order's outcome at the post
pf = (F(o.fill_ms) > o.mid_fill.to_numpy()) == y      # ... at the fill
ok = np.isfinite(F(o.post_ms)) & np.isfinite(o.mid_post.to_numpy()) & np.isfinite(F(o.fill_ms))
res = {}
for ad, nm in CL.items():
    for cls, cm in (("i", o.post_at_touch == 1), ("ii", o.post_at_touch == 0)):
        m = ok & (o.maker == ad).to_numpy() & cm.to_numpy()
        if not m.any():
            continue
        a, b = pp[m], pf[m]
        res[f"{nm}_class_{cls}"] = {"n": int(m.sum()), "posture_at_post": round(float(a.mean()), 3), "posture_at_fill": round(float(b.mean()), 3),
                                     "posted_with_then_flipped_against (stale)": round(float((a & ~b).mean()), 3),
                                     "posted_against_and_still_against": round(float((~a & ~b).mean()), 3),
                                     "posted_against_then_with": round(float((~a & b).mean()), 3), "with_throughout": round(float((a & b).mean()), 3),
                                     "age_median_s": round(float(o.age[m].median()), 2)}
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_stale_rungs.json").write_text(json.dumps(res, indent=1))
