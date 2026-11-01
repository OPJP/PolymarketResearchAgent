"""iteration 16, X180 follow-up (own state, reported only): does the cluster's own inventory explain the ladder center's
shrink toward 0.5 on 11-01? Units from code16/ladder_center.py (it16_center_units_*.parquet: one per window and public
publish with a 500-class add on both outcomes). Inventory = the cluster's net Up minus Down BUY shares in the window from
activity fills with block time <= P_i / 1000 - 2. Regress c - mid on (F1_nowcast - mid, 0.5 - mid) with and without the
inventory terms (sign of the net position, and the net position on the cheaper outcome)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from inst_side import acts  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
BLOCKS = [(1793467740, 1793469600), (1793516400, 1793524500)]


def fit(X, y):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ beta
    return [round(float(v), 4) for v in beta], round(float(1 - res.var() / y.var()), 4)


out = {}
for a, b in BLOCKS:
    U = pd.read_parquet(C / f"it16_center_units_{a}_{b}.parquet")
    d = acts(a - 1800, b)
    d = d[d.slug.isin(set(U.w))]
    d["sg"] = np.where(d.outcome == "Up", 1.0, -1.0) * d["size"].astype(float)
    inv = np.zeros(len(U))
    for w, g in d.groupby("slug"):
        g = g.sort_values("timestamp")
        ts = g.timestamp.to_numpy(np.int64)
        cs = np.cumsum(g.sg.to_numpy())
        m = (U.w == w).to_numpy()
        k = np.searchsorted(ts, U.P.to_numpy(np.int64)[m] // 1000 - 2, side="right") - 1
        inv[m] = np.where(k >= 0, cs[np.clip(k, 0, None)], 0.0)
    mid = U.mid.to_numpy()
    y = U.c.to_numpy() - mid
    x1 = U.F1_now.to_numpy() - mid
    x2 = 0.5 - mid
    sgn = np.sign(inv)
    cheap_up = mid < 0.5
    on_cheap = np.where(inv == 0, 0.0, np.where((inv > 0) == cheap_up, 1.0, -1.0))
    blk = {"units": int(len(U)), "share_with_position": round(float((inv != 0).mean()), 3),
           "share_holding_cheaper": round(float((on_cheap > 0).mean()), 3), "share_holding_favourite": round(float((on_cheap < 0).mean()), 3)}
    blk["base_edge_cheap"] = fit(np.column_stack([x1, x2]), y)
    blk["with_inv_sign"] = fit(np.column_stack([x1, x2, sgn]), y)
    blk["with_inv_sign_and_size_k"] = fit(np.column_stack([x1, x2, sgn, np.clip(inv / 1000.0, -5, 5)]), y)
    # center side vs the held outcome
    m = inv != 0
    blk["center_toward_held_outcome"] = round(float(((U.c.to_numpy() > mid) == (inv > 0))[m].mean()), 3) if m.any() else None
    out[f"{a}_{b}"] = blk
    print(a, b, json.dumps(blk))
(HERE.parent / "results/iter16_center_inv.json").write_text(json.dumps(out, indent=1))
