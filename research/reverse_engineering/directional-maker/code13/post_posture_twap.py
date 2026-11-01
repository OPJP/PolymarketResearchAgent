"""X134 live replication: the posture at the POST time (10-31 14-18 development block, code13 fills_posts) with the
current report (stamp lag 1,250 ms) vs a TWAP-60 of the 1-s Chainlink values (stamps [s - 60, s] at the same lag) and
EWMA-30, by fill class (i) quote move / (ii) market came, and in disagreement cells. Values from the live recordings
(cl_source, development blocks only)."""
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
L = 1250
o["cs"] = ((o.post_ms - L) // 1000).astype(np.int64)
stamps = sorted(set(int(c) - j for c in o.cs for j in range(0, 61)))
clv = cl_source.cl_values(stamps, allow_sealed=False, fetch=False)
sp = spot(int(o.post_ms.min() // 1000) - 7200, int(o.post_ms.max() // 1000) + 5)
sig = sp.sigma((o.post_ms // 1000).to_numpy(), look=300) * 1.4
tau = np.maximum(o.end.to_numpy() - o.post_ms.to_numpy() / 1000, 1.0)
cur, tw, ew = [], [], []
for c in o.cs:
    v = np.array([clv.get(int(c) - j, np.nan) for j in range(0, 61)])
    ok = np.isfinite(v)
    cur.append(v[0]); tw.append(v[ok].mean() if ok.sum() >= 40 else np.nan)
    wgt = np.exp(-np.arange(61) / 30.0)
    ew.append((wgt[ok] * v[ok]).sum() / wgt[ok].sum() if ok.sum() >= 40 else np.nan)
o["cur"], o["tw"], o["ew"] = cur, tw, ew
y = (o.is_up == 1).to_numpy()
P = {c: norm.cdf(np.log(o[c].to_numpy(float) / o.K.to_numpy(float)) / (sig * np.sqrt(tau))) > o.mid.to_numpy() for c in ("cur", "tw", "ew")}
okall = o[["cur", "tw", "ew", "mid", "K"]].notna().all(axis=1).to_numpy()
res = {}
for nm, m in (("all", okall), ("class_i", okall & (o.post_at_touch == 1).to_numpy()), ("class_ii", okall & (o.post_at_touch == 0).to_numpy())):
    r = {"n": int(m.sum())}
    for c in ("cur", "tw", "ew"):
        r[c] = float((P[c] == y)[m].mean()) if m.any() else None
    for c in ("tw", "ew"):
        dis = m & (P[c] != P["cur"])
        r[c + "_disagree"] = [int(dis.sum()), float((P[c] == y)[dis].mean()) if dis.any() else None, int(o.w[dis].nunique())]
    res[nm] = r
print(json.dumps(res, indent=1))
(HERE.parent / "results/iter13_post_posture_twap.json").write_text(json.dumps(res, indent=1))
