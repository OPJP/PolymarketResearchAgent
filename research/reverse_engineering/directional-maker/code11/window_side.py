"""Iteration 11 (mechanics P4 = X109): the window net side against fill-free window rules (Binance stand-in posture,
time-weighted majority over the quoting seconds; posture at the first quoting second), per split and per day
(VALIDATE: aggregates per day only).
    python code11/window_side.py
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache" / "re" / "directional-maker" / "it11"
SPLIT_V = 1793059200
B = pd.read_parquet(C / "replay_window_base.parquet").drop_duplicates("cid").set_index("cid")
CW = pd.read_parquet(C / "cluster_windows.parquet")
mk = CW[CW.role == "maker"].groupby("cid").agg(up=("up", "sum"), dn=("dn", "sum"), pnl=("pnl", "sum"))
fi = CW[CW.role == "maker"].sort_values("first_ts").groupby("cid").first()[["first_up", "first_ts"]]
B = B.join(mk, how="inner").join(fi, how="left")
tot = B.up + B.dn
B["one"] = np.maximum(B.up, B.dn) / tot >= 0.7
B["net_up"] = (B.up > B.dn).astype(int)
B["post_maj_up"] = (B.post_frac_up > 0.5).astype(int)
B["win_up"] = (B.pay_up > 0.5).astype(int)
out = {}
for sp, d in (("study", B[B.st < SPLIT_V]), ("validate", B[B.st >= SPLIT_V])):
    o = d[d.one]
    rec = {"windows": int(len(d)), "one_sided": int(len(o)),
           "posture_majority_vs_net_side": round(float((o.post_maj_up == o.net_up).mean()), 4),
           "entry_posture_vs_net_side": round(float((o.entry_post_up == o.net_up)[o.entry_post_up >= 0].mean()), 4),
           "first_fill_side_vs_net_side": round(float((o.first_up == o.net_up).mean()), 4),
           "net_side_won": round(float((o.net_up == o.win_up).mean()), 4),
           "posture_majority_won": round(float((d.post_maj_up == d.win_up).mean()), 4),
           "always_up": round(float(o.net_up.mean()), 4),
           "by_session": {}}
    for s, g in o.groupby("sess"):
        rec["by_session"]["us" if s == 1 else "off"] = {"n": int(len(g)), "posture_majority": round(float((g.post_maj_up == g.net_up).mean()), 4),
                                                       "net_side_won": round(float((g.net_up == g.win_up).mean()), 4)}
    rec["by_day"] = {str(pd.to_datetime(k, unit="s").date()): {"n": int(len(g)), "posture_majority": round(float((g.post_maj_up == g.net_up).mean()), 3),
                                                               "net_side_won": round(float((g.net_up == g.win_up).mean()), 3),
                                                               "posture_won": round(float((g.post_maj_up == g.win_up).mean()), 3)}
                     for k, g in o.groupby("day")}
    out[sp] = rec
print(json.dumps(out, indent=1))
(HERE.parent / "results" / "iter11_window_side.json").write_text(json.dumps(out, indent=1))
