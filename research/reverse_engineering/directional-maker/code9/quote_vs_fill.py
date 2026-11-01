"""Iteration 9: is the per-fill side decided by the quote or by the taker? For every BTC 5m cluster maker fill of 10-31
14:06-16:30 (it6/fill_side), the quote-unit labels of iteration 8 (it6/a4_secs: a cluster-class exact-500 at the touch of
side s at second t, from the own raw book) for BOTH sides at the fill second. If the cluster's 500 is at the touch on
only one side, the quote decides the side; if on both, the taker does. Development, descriptive."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"
S = pd.read_parquet(C / "it6" / "a4_secs_1793455600_1793464202.parquet", columns=["st", "rel", "s_up", "y", "e_cl"])
lab = {(int(a), int(b), int(c)): int(d) for a, b, c, d in zip(S.st, S.rel, S.s_up, S.y)}
F = pd.read_parquet(C / "it6" / "fill_side_1793455600_1793464202.parquet")
F = F[F.fam == "5m"].copy()
F["rel"] = (F["T"] // 1000 - F.st).astype(int)
rows = []
for r in F.itertuples(index=False):
    own = lab.get((int(r.st), int(r.rel), int(r.up)))
    oth = lab.get((int(r.st), int(r.rel), 1 - int(r.up)))
    if own is None or oth is None:
        continue
    # also the second before (quote state just before the match)
    own1 = lab.get((int(r.st), int(r.rel) - 1, int(r.up)), own)
    oth1 = lab.get((int(r.st), int(r.rel) - 1, 1 - int(r.up)), oth)
    rows.append(dict(own=max(own, own1), oth=max(oth, oth1), post=int(r.e_cl > 0) == int(r.up), T=r.T))
D = pd.DataFrame(rows)
cls = np.select([(D.own == 1) & (D.oth == 0), (D.own == 0) & (D.oth == 1), (D.own == 1) & (D.oth == 1)], ["only_bought_side", "only_other_side", "both"], "neither")
out = {"fills": int(len(D))}
for c in ("only_bought_side", "only_other_side", "both", "neither"):
    k = cls == c
    out[c] = {"share": round(float(k.mean()), 3), "posture_acc": round(float(D.post[k].mean()), 3) if k.any() else None}
one = (cls == "only_bought_side") | (cls == "only_other_side")
out["quote_side_predictor_acc_when_one_sided"] = round(float((cls[one] == "only_bought_side").mean()), 3)
out["one_sided_share"] = round(float(one.mean()), 3)
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_quote_vs_fill.json").write_text(json.dumps(out, indent=1))
