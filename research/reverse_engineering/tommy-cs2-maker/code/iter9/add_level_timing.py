"""Iteration 9, finding 14 robustness: when does the others' mid move after the wallet's validated adds? Split the
others'-mid change into (s-0.1, s+0.1], (s+0.1, s+2], (s+2, s+10] s, by the add's offset tercile, for own adds and
for other makers' adds. Immediate pegging by quote followers would sit in the first 100 ms; information keeps moving
the mid later. Output: results/add_level_timing.json"""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"; RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
A = A[A.kind == "add"]
M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
mids = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}
rows = []
for r in A.itertuples():
    x = mids.get(r.a)
    if x is None: continue
    ts, md = x
    def m_at(t):
        j = np.searchsorted(ts, t, side="right") - 1
        return md[j] if j >= 0 else np.nan
    tok0 = r.side == "BUY"
    sg = 1 if tok0 else -1
    m0 = m_at(r.s - 100)
    if not np.isfinite(m0): continue
    bid = r.p if tok0 else 1 - r.p
    mt = m0 if tok0 else 1 - m0
    pts = [m_at(r.s + 100), m_at(r.s + 2000), m_at(r.s + 10000)]
    rows.append({"own": bool(r.vown), "off": (bid - mt) * 100, "d0": sg * (pts[0] - m0) * 100, "d1": sg * (pts[1] - pts[0]) * 100, "d2": sg * (pts[2] - pts[1]) * 100})
X = pd.DataFrame(rows); X = X[X.off.abs() <= 15]
res = {}
for nm, g in (("own", X[X.own]), ("other", X[~X.own])):
    q = pd.qcut(g.off, 3, labels=["low", "mid", "high"], duplicates="drop")
    res[nm] = {str(k): {"n": int(len(v)), "d_0_100ms": round(float(v.d0.mean()), 3), "d_100ms_2s": round(float(v.d1.mean()), 3), "d_2_10s": round(float(v.d2.mean()), 3)}
               for k, v in g.groupby(q, observed=True)}
print(json.dumps(res, indent=1)); json.dump(res, open(RES / "add_level_timing.json", "w"), indent=1)
