"""Iteration 11: the strict-fill replay of the frozen side rule (posture) at the rule's own price (last print - 0.01) and
the session size, latency 2 s, slack 2, all prints; per-window PnL corr with the cluster (VALIDATE aggregate) per wallet
and per half; this is the executable outcome metric reported in target_metrics.
    python code11/replay_frozen.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker" / "it11"
SPLIT_V, HALF_V = 1793059200, 1793232000


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [round(float(np.corrcoef(a, b)[0, 1]), 4), round(float(pd.Series(a).corr(pd.Series(b), method="spearman")), 4)]


R = pd.read_parquet(C / "replay_windows.parquet")
B = pd.read_parquet(C / "replay_window_base.parquet").drop_duplicates("cid").set_index("cid")
CW = pd.read_parquet(C / "cluster_windows.parquet")
mkw = CW[CW.role == "maker"]
out = {}
for delta in (0.01, 0.0):
    g = R[(R.L == 2) & (R.touch == 0) & (R.delta == delta) & (R.side == "posture") & (R.q == "qsess") & (R.flow == "full")].set_index("cid")
    rec = {}
    for sp, m in (("study", B.st < SPLIT_V), ("validate", B.st >= SPLIT_V), ("validate_h1", (B.st >= SPLIT_V) & (B.st < HALF_V)),
                  ("validate_h2", B.st >= HALF_V)):
        ids = B.index[m]
        cl = mkw[mkw.cid.isin(ids)].groupby("cid").pnl.sum()
        rp = g.pnl.reindex(cl.index).fillna(0.0)
        rec[sp] = {"pooled": corr(rp, cl), "windows": int(len(cl)), "replay_return": round(float(g.pnl.reindex(ids).sum() / g.usd.reindex(ids).sum()), 4)}
        for wname, gw in mkw[mkw.cid.isin(ids)].groupby("wallet"):
            s = gw.groupby("cid").pnl.sum()
            rec[sp][wname] = corr(g.pnl.reindex(s.index).fillna(0.0), s)
    out[f"posture_delta{delta}_qsess_L2_strict"] = rec
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter11_replay_frozen.json").write_text(json.dumps(out, indent=1))
