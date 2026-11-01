"""Iteration 7, panel iter6 information I3 (X45): do takers react to the Chainlink display (the RTDS relay publish)?

For each Chainlink BTC update (stamp S, publish ms P_S, dy_rtds) and each BTC 5m / 15m market, taker flow in Up terms
(shares that sell Up: taker SELL Up or taker BUY Down; minus shares that buy Up) in [P, P + W) and [P - W, P), and the
futures mid change over the same windows (dm_bnf bookTicker). Regress the change in net Up selling on dCL_S (the
displayed move) and on the futures move; compare the response after the publish with the same measure before it.
Also the hazard of a print in 0-1 s after publishes with |dCL| > $10 vs < $2.
"""
from __future__ import annotations

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
OUT = ROOT / "research/reverse_engineering/directional-maker/results"


def main(a, b):
    rows = [(int(r["ts"]) // 1000, int(r["P"]), float(r["v"])) for r in iter_dm("dy_rtds", a - 30, b + 5)
            if r.get("k") == "u" and r.get("sy") == "btc" and r.get("tp") == "cl" and r.get("P")]
    rt = pd.DataFrame(rows, columns=["S", "P", "v"]).drop_duplicates("S").sort_values("S")
    rt["dcl"] = rt.v.diff()
    rt = rt[(rt.P >= a * 1000) & (rt.P < b * 1000 - 3000)].dropna()
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    x = x.sort_values("s").drop_duplicates("h")
    d = x.d.astype(str).str.upper().str[0]
    x["sell_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    x["q"] = np.where(x.sell_up, 1.0, -1.0) * x.z.astype(float)
    fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dm_bnf", a - 30, b) if r["r"][0] == "b" and r["r"][2]]
    if not fut:
        fut = [(r["r"][2], (r["r"][3] + r["r"][5]) / 2) for r in iter_dm("dx_bnf", a - 30, b) if r["r"][0] == "b" and r["r"][2]]
    fu = pd.DataFrame(fut, columns=["s", "m"]).sort_values("s")
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()

    def fut_at(t):
        i = np.searchsorted(fs, t, side="right") - 1
        return fm[np.clip(i, 0, None)]
    out = {"updates": int(len(rt)), "trades": int(len(x))}
    for tag, pre in (("5m", "btc-updown-5m"), ("15m", "btc-updown-15m")):
        g = x[x.w.str.startswith(pre)]
        ts, q = g.s.to_numpy(np.int64), g.q.to_numpy()
        cq = np.concatenate([[0.0], np.cumsum(q)])
        cn = np.arange(len(ts) + 1, dtype=float)
        res = {}
        for W in (1000, 2000):
            P = rt.P.to_numpy(np.int64)
            i0, i1, i2 = (np.searchsorted(ts, P - W), np.searchsorted(ts, P), np.searchsorted(ts, P + W))
            after, before = cq[i2] - cq[i1], cq[i1] - cq[i0]
            n_after, n_before = cn[i2] - cn[i1], cn[i1] - cn[i0]
            dfut_after = fut_at(P + W) - fut_at(P)
            dfut_before = fut_at(P) - fut_at(P - W)
            dcl = rt.dcl.to_numpy()
            X = np.column_stack([np.ones(len(P)), dcl, dfut_before, dfut_after])
            yv = after - before
            beta = np.linalg.lstsq(X, yv, rcond=None)[0]
            res[f"W{W}"] = {"corr_netsell_after_vs_minus_dcl": float(np.corrcoef(after, -dcl)[0, 1]),
                            "corr_netsell_before_vs_minus_dcl": float(np.corrcoef(before, -dcl)[0, 1]),
                            "corr_netsell_after_vs_minus_dfut_after": float(np.corrcoef(after, -dfut_after)[0, 1]),
                            "ols_change_on[dcl,dfut_before,dfut_after]": [round(float(v), 3) for v in beta[1:]],
                            "prints_after_big_dcl": float(n_after[np.abs(dcl) > 10].mean()),
                            "prints_after_small_dcl": float(n_after[np.abs(dcl) < 2].mean()),
                            "prints_before_big_dcl": float(n_before[np.abs(dcl) > 10].mean()),
                            "prints_before_small_dcl": float(n_before[np.abs(dcl) < 2].mean())}
        out[tag] = res
    OUT.joinpath(f"iter7_i3_display_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
