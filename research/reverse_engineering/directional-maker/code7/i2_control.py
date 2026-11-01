"""Iteration 7 control for code7/i2_publish.py: do the cluster's re-posts right after a Chainlink publish follow the
Chainlink change itself or the futures move behind it? Agreement of exact-500 re-posts in [P_S, P_S + 200 ms) with
dCL_S, split by whether the futures mid moved the same way during stamp second S (and during [P_S - 1000, P_S))."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
a, b = int(sys.argv[1]), int(sys.argv[2])
rt = pd.DataFrame([(int(r["ts"]) // 1000, int(r["P"]), float(r["v"])) for r in iter_dm("dy_rtds", a - 30, b + 5)
                   if r.get("k") == "u" and r.get("sy") == "btc" and r.get("tp") == "cl" and r.get("P")],
                  columns=["S", "P", "v"]).drop_duplicates("S").sort_values("S")
cl, pub = dict(zip(rt.S, rt.v)), dict(zip(rt.S, rt.P))
fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 30, b) if r["r"][0] == "b" and r["r"][2]]
fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s")
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()


def fat(t):
    return fm[np.clip(np.searchsorted(fs, t, side="right") - 1, 0, None)]


ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d"])
out = {}
for tag, pre in (("15m", "btc-updown-15m"), ("5m", "btc-updown-5m")):
    e = ev[ev.w.str.startswith(pre) & (ev.d == 500)].copy()
    e["p"] = e.p.round(2)
    e = e.sort_values(["w", "side", "s"], kind="stable")
    e["dp"] = e.groupby(["w", "side"]).p.diff()
    e["dt"] = e.groupby(["w", "side"]).s.diff()
    E = e[(e.dt <= 1500) & (e.dp.abs() > 0) & (e.dp.abs() <= 0.05)]
    rows = []
    for s_, dp in zip(E.s.to_numpy(np.int64), E.dp.to_numpy()):
        for k in range(0, 4):
            S = s_ // 1000 - k
            P = pub.get(S)
            if P is None or not (P <= s_ < P + 200) or (S - 1) not in cl:
                continue
            dcl = cl[S] - cl[S - 1]
            if abs(dcl) <= 3:
                continue
            dfS = float(fat(S * 1000 + 1000) - fat(S * 1000))
            dfP = float(fat(P) - fat(P - 1000))
            rows.append((np.sign(dp) == np.sign(dcl), np.sign(dfS) == np.sign(dcl) if abs(dfS) > 2 else None,
                         np.sign(dfP) == np.sign(dcl) if abs(dfP) > 2 else None, np.sign(dp) == np.sign(dfS) if abs(dfS) > 2 else None))
    R = pd.DataFrame(rows, columns=["agree_cl", "fut_S_same", "fut_P_same", "agree_futS"])
    if not len(R):
        out[tag] = None
        continue
    o = {"n": int(len(R)), "agree_cl_all": round(float(R.agree_cl.mean()), 3)}
    for col in ("fut_S_same", "fut_P_same"):
        for val in (True, False):
            g = R[R[col] == val]
            o[f"agree_cl_when_{col}={val}"] = [round(float(g.agree_cl.mean()), 3), int(len(g))] if len(g) else None
    g = R[R.fut_S_same == False]  # noqa: E712
    o["agree_futS_when_disagree"] = [round(float(g.agree_futS.astype(float).mean()), 3), int(len(g))] if len(g) else None
    g = R[R.fut_S_same.isna()]
    o["agree_cl_when_futS_flat"] = [round(float(g.agree_cl.mean()), 3), int(len(g))] if len(g) else None
    out[tag] = o
(ROOT / "research/reverse_engineering/directional-maker/results" / f"iter7_i2_control_{a}_{b}.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
