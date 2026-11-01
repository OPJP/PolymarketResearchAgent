"""Iteration 11: aggregate scores of chosen replay configurations (STUDY and VALIDATE aggregates; nothing per window).
    python code11/replay_keys.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker" / "it11"
SPLIT_V = 1793059200


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return [float("nan"), float("nan")]
    return [round(float(np.corrcoef(a, b)[0, 1]), 3), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 3)]


R = pd.read_parquet(C / "replay_windows.parquet")
B = pd.read_parquet(C / "replay_window_base.parquet").drop_duplicates("cid").set_index("cid")
CW = pd.read_parquet(C / "cluster_windows.parquet")
mk = CW[CW.role == "maker"].groupby("cid").agg(pnl=("pnl", "sum"), up=("up", "sum"), dn=("dn", "sum"))
B = B.join(mk, how="left").fillna({"pnl": 0, "up": 0, "dn": 0})
B["has"] = (B.up + B.dn) > 0
tot = B.up + B.dn
B["one"] = B.has & (np.maximum(B.up, B.dn) / tot.where(tot > 0, 1) >= 0.7)
B["sideup"] = (B.up > B.dn).astype(int)
out = {}
for L in (0, 2):
    for touch, delta in ((0, 0.0), (0, 0.01), (1, 0.01)):
        for side in ("posture", "two", "cheaper", "fav", "pickoff"):
            g = R[(R.L == L) & (R.touch == touch) & (R.delta == delta) & (R.side == side) & (R.q == "q500") & (R.flow == "full")]
            g = g.set_index("cid").reindex(B.index).fillna({"pnl": 0, "up": 0, "dn": 0})
            net = g.up - g.dn
            pu = np.where(net != 0, (net > 0).astype(int), (B.post_frac_up > 0.5).astype(int))
            rec = {}
            for sp, m in (("study", B.st < SPLIT_V), ("validate", B.st >= SPLIT_V)):
                a = m & B.has
                o = m & B.one
                rec[sp] = {"corr": corr(g.pnl[a], B.pnl[a]), "net_side": round(float(np.mean(pu[o] == B.sideup[o])), 3)}
            out[f"L{L}_touch{touch}_d{delta}_{side}"] = rec
for k, v in out.items():
    print(k, v)
(HERE.parent / "results" / "iter11_replay_keys.json").write_text(json.dumps(out, indent=1))
