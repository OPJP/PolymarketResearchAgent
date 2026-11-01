"""Iteration 14, X153 (mechanics P3 on the quote unit): posture of schedule-size posts at the touch by pass multiplicity
(number of same-size adds at the same price and book side of the window within +-25 ms; 3 = all three engines).
Development block 10-31 14-18 (it14_quote_unit.parquet from code14/lagged_quote.py; it13/sched_adds.parquet)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]; C = ROOT / ".cache/re/directional-maker"
q = pd.read_parquet(C / "it14_quote_unit.parquet")
S = pd.read_parquet(C / "it13/sched_adds.parquet", columns=["w", "s", "sd", "p", "dz"])
S["p"] = S.p.round(3)
S = S[S.dz.isin([62.0, 250.0, 500.0, 1000.0])].sort_values(["w", "sd", "p", "dz", "s"], kind="stable")
mult = np.zeros(len(q), int)
grp = {k: g.s.to_numpy(np.int64) for k, g in S.groupby(["w", "sd", "p", "dz"])}
for i, (w, sd, p, dz, s) in enumerate(zip(q.w, q.sd, q.p.round(3), q.dz, q.s)):
    a = grp.get((w, sd, p, dz))
    mult[i] = 0 if a is None else int(np.searchsorted(a, s + 25, side="right") - np.searchsorted(a, s - 25, side="left"))
q["mult"] = np.clip(mult, 1, 4)
out = {}
for h, g in q.groupby("half"):
    r = {}
    for m, gg in g.groupby("mult"):
        ok = gg.P.notna()
        r[str(m)] = {"n": int(len(gg)), "posture": float((gg.P[ok] == gg.y[ok]).mean()),
                     "share_500": float(gg.dz.isin([500.0, 1000.0]).mean())}
    out[h] = r
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parent.parent / "results/iter14_triplets_qu.json").write_text(json.dumps(out, indent=1))
