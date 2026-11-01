"""X130 / X136: the side of each filled order at its POST time (the add that put it in the book), split by class
(i) quote move to the touch vs (ii) resting order reached by the market. Posture = sign(F_up(L = 1250 ms, k 1.4) -
Up mid) at the post (mid from the Up touch carried by the add's price_change row) and at the fill (Up touch at the last
raw-book event before the fill). Development block 10-31 14-18."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import cl_source
from tracer_laws import spot
OUT = ROOT / ".cache/re/directional-maker/it13"
o = pd.read_parquet(OUT / "fills_posts.parquet")
S = pd.read_parquet(OUT / "sched_adds.parquet"); T = pd.read_parquet(OUT / "tracer_events.parquet")
A = pd.concat([S[["w", "s", "sd", "p", "dz", "bb", "ba"]], T[["w", "s", "sd", "p", "bb", "ba"]].assign(dz=T["size"])], ignore_index=True)
A["p"] = A.p.round(3); A["dz"] = A.dz.round(2)
A = A.drop_duplicates(["w", "s", "sd", "p", "dz"]).set_index(["w", "s", "sd", "p", "dz"])
o = o[o.post_ms.notna()].copy()
o["post_ms"] = o.post_ms.astype(np.int64)
key = list(zip(o.w, o.post_ms, o.sd.astype(int), o.bp.round(3), o.orig.round(2)))
bbba = A.reindex(key)[["bb", "ba"]].to_numpy()
o["bb_post"], o["ba_post"] = bbba[:, 0], bbba[:, 1]
o["mid_post"] = (o.bb_post + o.ba_post) / 2
from polyrea.workflows.updown_study import fetch_windows
raw = fetch_windows(sorted(set(o.w)))
K = {}
for m in raw.values():
    for e in m.get("events") or []:
        v = (e.get("eventMetadata") or {}).get("priceToBeat")
        if v is not None: K[m["slug"]] = float(v)
o["K"] = o.w.map(K)
o["start"] = o.w.str.rsplit("-", n=1).str[1].astype(int)
o["end"] = o.start + np.where(o.w.str.contains("-15m-"), 900, 300)
L = 1250
st = sorted(set(((o.post_ms - L) // 1000).astype(int)) | set(((o.fill_ms - L) // 1000).astype(int)))
clv = cl_source.cl_values(st, allow_sealed=False, fetch=True, max_requests=300)
sp = spot(int(o.post_ms.min() // 1000) - 7200, int(o.fill_ms.max() // 1000) + 5)
def F(ms):
    cl = ((ms - L) // 1000).map(clv).to_numpy(float)
    sig = sp.sigma((ms // 1000).to_numpy(), look=300) * 1.4
    tau = np.maximum(o.end.to_numpy() - ms.to_numpy() / 1000, 1.0)
    return norm.cdf(np.log(cl / o.K.to_numpy(float)) / (sig * np.sqrt(tau)))
o["F_post"] = F(o.post_ms)
o["post_pred_up"] = o.F_post > o.mid_post
o["y"] = o.is_up == 1
o["ok"] = o.F_post.notna() & o.mid_post.notna()
out = {}
for nm, g in [("all", o), ("class_i_quote_move", o[o.post_at_touch == 1]), ("class_ii_market_came", o[o.post_at_touch == 0])]:
    g = g[g.ok]
    out[nm] = {"n": int(len(g)), "posture_at_post": float((g.post_pred_up == g.y).mean()), "cheaper_at_post": float(((g.mid_post < 0.5) == g.y).mean()),
               "share_5m": float(g.w.str.contains("-5m-").mean())}
for nm, g in o[o.ok].groupby(o.sched.map({True: "schedule", False: "pairing"})):
    out["class_" + nm] = {"n": int(len(g)), "posture_at_post": float((g.post_pred_up == g.y).mean()),
                          "quote_move": float(g.post_at_touch.mean())}
print(json.dumps(out, indent=1))
(HERE.parent / "results/iter13_post_posture.json").write_text(json.dumps(out, indent=1))
