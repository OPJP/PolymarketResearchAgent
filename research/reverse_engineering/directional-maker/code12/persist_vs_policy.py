"""Iteration 12: separate quote policy from taker-flow persistence for the after-entry branch of R8-side (exploratory).
For each after-entry schedule-size BTC 5m maker fill of the lot (not a decided window; cluster position != 0), find the
cluster's previous BUY fill in the window (any wallet, maker or taker, strictly earlier second; activity rows) and its
outcome. Policy predicts the HELD outcome; persistence predicts the PREVIOUS fill's outcome. Score both where they differ.
    python code12/persist_vs_policy.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
C = HERE.parents[3] / ".cache/re/directional-maker"
STD = (500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200, 2000, 25, 31, 20, 10, 5)


def main():
    V = pd.read_parquet(C / "it12" / "typed_fills.parquet")
    acts = []
    for n in ("bosona", "almach", "momoney"):
        acts.append(pd.read_parquet(C / "exam" / f"activity_{n}.parquet", columns=["timestamp", "type", "side", "outcome", "slug"]))
    A = pd.concat(acts)
    A = A[(A.type == "TRADE") & (A.side == "BUY") & A.slug.str.startswith("btc-updown-5m-", na=False)].copy()
    A["st"] = A.slug.str.split("-").str[-1].astype(int)
    A["up"] = (A.outcome == "Up").astype(int)
    A = A.sort_values("timestamp", kind="stable")
    G = {k: (g.timestamp.to_numpy(), g.up.to_numpy()) for k, g in A.groupby("st")}
    prev = []
    for st, b in zip(V.st.astype(int), V.b.astype(int)):
        g = G.get(st)
        if g is None:
            prev.append(-1)
            continue
        i = np.searchsorted(g[0], b, side="left") - 1
        prev.append(int(g[1][i]) if i >= 0 else -1)
    V["prev_up"] = prev
    mid = V.mid_up.to_numpy()
    y = V.is_up.to_numpy() == 1
    inv = V.inv_c.to_numpy()
    sched = np.isin(V.orig.to_numpy(), STD)
    base = (np.abs(mid - 0.5) <= 0.4) & (inv != 0) & (V.prev_up.to_numpy() >= 0)
    held = inv > 0
    pv = V.prev_up.to_numpy() == 1
    out = {}
    for sp in ("study", "validate"):
        ms = (V.sp == sp).to_numpy() & base
        rec = {}
        for nm, m in (("schedule", ms & sched), ("non_schedule", ms & ~sched)):
            dis = m & (held != pv)
            rec[nm] = {"n": int(m.sum()), "held": round(float((held == y)[m].mean()), 4), "previous_fill_side": round(float((pv == y)[m].mean()), 4),
                       "share_differ": round(float(dis.sum() / max(m.sum(), 1)), 4),
                       "where_differ_held": round(float((held == y)[dis].mean()), 4) if dis.any() else None,
                       "where_differ_previous": round(float((pv == y)[dis].mean()), 4) if dis.any() else None, "n_differ": int(dis.sum())}
        out[sp] = rec
    (HERE.parent / "results" / "iter12_persist_vs_policy.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
