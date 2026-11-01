"""iteration 16, X186 light (information panel I15-4): are the idle module's alt 5m/15m quotes re-sided by the
per-symbol Chainlink publish, as the BTC ladder is (X163)? Development block 11-01 06:00-now.
Units: each public ETH / SOL Chainlink publish P_i (dy_rtds P) whose value changed (d_i = sign(v_i - v_{i-1})).
Label: configured-size adds at the touch (dw_clob 'pc' rows; ETH 5m 50/150, SOL 5m 50/100, ETH/SOL 15m 30) on the Up
bid (side 1 at the best bid) or the Down bid (side 0 at the best ask) of that symbol's 5m / 15m windows in
(P_i, P_i + 300 ms] (after) and in (P_i - 300 ms, P_i] (placebo before). Score: share of those posts on the outcome the
report change favours (Up if d_i > 0), after vs before, with the publish-by-publish binomial count.
    python alt_publish.py <a> <b>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

SIZES = {("eth", "5m"): {50.0, 150.0}, ("sol", "5m"): {50.0, 100.0}, ("eth", "15m"): {30.0}, ("sol", "15m"): {30.0}}
a, b = int(sys.argv[1]), int(sys.argv[2])
pub = {"eth": [], "sol": []}
for r in live.iter_live("dy_rtds", a - 60, b):
    if r.get("tp") == "cl" and r.get("sy") in pub and r.get("P"):
        pub[r["sy"]].append((int(r["P"]), int(r["ts"]), float(r["v"])))
adds = []
for r in live.iter_live("dw_clob", a, b):
    if r.get("k") != "pc" or not r.get("s"):
        continue
    w = r.get("w") or ""
    parts = w.split("-")
    if len(parts) < 4 or (parts[0], parts[2]) not in SIZES:
        continue
    sz = SIZES[(parts[0], parts[2])]
    bb, ba = r.get("bb"), r.get("ba")
    for row in r.get("c") or []:
        if len(row) < 4:
            continue
        sd, p, z, dz = row[0], row[1], row[2], row[3]
        if round(float(dz), 2) in sz and ((sd == 1 and abs(p - bb) < 1e-9) or (sd == 0 and abs(p - ba) < 1e-9)):
            adds.append((parts[0], parts[2], int(r["s"]), int(sd)))
A = pd.DataFrame(adds, columns=["sym", "len", "s", "sd"])
out = {"span": [a, b], "adds": int(len(A)), "by": {f"{k[0]}_{k[1]}": int(v) for k, v in A.groupby(["sym", "len"]).size().items()} if len(A) else {}}
res = {}
for sym in ("eth", "sol"):
    Pb = pd.DataFrame(pub[sym], columns=["P", "ts", "v"]).sort_values("P").drop_duplicates("ts").sort_values("P").reset_index(drop=True)
    if len(Pb) < 10:
        continue
    Pb["d"] = np.sign(Pb.v.diff())
    P = Pb.P.to_numpy(np.int64)
    d = Pb.d.to_numpy()
    for ln in ("5m", "15m"):
        g = A[(A.sym == sym) & (A.len == ln)]
        if not len(g):
            continue
        s = g.s.to_numpy(np.int64)
        y = g.sd.to_numpy()
        row = {"posts": int(len(g))}
        for lab, off in (("after", 0), ("before", 300)):
            # the publish i with P_i in [s - 300 + off, s + off): after = post within 300 ms after P_i; before = post within 300 ms before P_i
            i = np.searchsorted(P, s + off, side="left") - 1 if off == 0 else np.searchsorted(P, s, side="right")
            ok = (i >= 0) & (i < len(P))
            ii = np.clip(i, 0, len(P) - 1)
            gap = np.where(off == 0, s - P[ii], P[ii] - s)
            m = ok & (gap >= 0) & (gap <= 300) & np.isfinite(d[ii]) & (d[ii] != 0)
            fav_up = d[ii] > 0
            hit = (y == 1) == fav_up
            row[lab] = [round(float(hit[m].mean()), 3) if m.sum() else None, int(m.sum())]
        res[f"{sym}_{ln}"] = row
out["publish_anchored"] = res
print(json.dumps(out, indent=1, default=str))
(HERE.parent / "results" / f"iter16_alt_publish_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=str))
