"""X201 (assumptions panel iter-13 P3): lag tolerance of the price item. How much of the frozen X163 ladder machine's
score survives when its value input lags the wallet's own value by L?

Data: BUILD-live (10-31 14:50-18:00) uncensored own adds with their own levels before the decision
(.cache/re/tommy-cs2-maker/iter12/slot_vrel_rows.parquet, the X163 rows). Bursts as in ladder_machine.py (20 ms).
V(t) is taken as the wallet's own value path: the top it left after its latest add burst on the same token (V_after).
V_L for a burst at t = V_after of the latest earlier burst on that token that started at or before t - L; if none, the
others' best bid J at the burst (fresh book, public). L in {0+, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 30} s. The machine
(predict_set, depth 5, band) is frozen; nothing is fitted. Scored per order (no rank) and on the burst-set unit,
by class: V-change bursts (V_after != V_0+) vs refills (V unchanged), and by title (CS2 / Dota), with the share of
orders and of filled orders in each class (filled = a later own fill row at the same price before the next own add at
that price). Oracle (L = 0, V = V_after) reported for reference. Output: results/lag_tolerance.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter12"))
from ladder_machine import BURST_MS, TICK, parse_levels, predict_set  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
LAGS = [0.001, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 30]


def main():
    R = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet").sort_values(["a", "oi", "t"]).reset_index(drop=True)
    R["a"] = R.a.astype(str)
    R["held"] = R.own_levels.map(parse_levels)
    F = R[R.kind == "fill"]
    A = R[R.kind == "add"].copy()
    A["burst"] = (A.groupby(["a", "oi"]).t.diff().fillna(1e9) > BURST_MS).cumsum()
    # filled flag per add
    fills = {k: np.sort(g.t.to_numpy()) for k, g in F.groupby(["a", "p"])}
    adds_at = {k: np.sort(g.t.to_numpy()) for k, g in A.groupby(["a", "p"])}
    filled = []
    for r in A.itertuples():
        ft = fills.get((r.a, r.p))
        if ft is None:
            filled.append(False)
            continue
        at = adds_at[(r.a, r.p)]
        j = np.searchsorted(at, r.t, side="right")
        nxt = at[j] if j < len(at) else np.inf
        k = np.searchsorted(ft, r.t, side="right")
        filled.append(bool(k < len(ft) and ft[k] < nxt))
    A["filled"] = filled
    B = A.groupby("burst").agg(a=("a", "first"), oi=("oi", "first"), t=("t", "min"), V=("V_after", "first"),
                               J=("J", "first"), slug=("slug", "first"), n=("p", "size")).reset_index()
    B["title"] = np.where(B.slug.str.startswith("dota2"), "dota2", "cs2")
    hist = {k: (g.t.to_numpy(), g.V.to_numpy()) for k, g in B.groupby(["a", "oi"])}

    def v_lag(r, L):
        ts, vs = hist[(r.a, r.oi)]
        j = np.searchsorted(ts, r.t - L * 1000.0, side="right") - 1
        # exclude the burst itself (its own start is at r.t; for L > 0 the search stops before it)
        while j >= 0 and ts[j] >= r.t:
            j -= 1
        if j >= 0 and np.isfinite(vs[j]):
            return float(vs[j])
        return float(r.J) if np.isfinite(r.J) else np.nan
    B["V0"] = [v_lag(r, 0.001) for r in B.itertuples()]
    B["cls"] = np.where(np.abs(B.V - B.V0) < 1e-6, "refill_same_V", "V_change")
    groups = {b: g for b, g in A.groupby("burst")}

    def score(vfun, sel):
        hs = hn = n = nf = hsf = 0
        for r in B[sel].itertuples():
            V = vfun(r)
            g = groups[r.burst]
            if V is None or not np.isfinite(V):
                n += len(g)
                nf += int(g.filled.sum())
                continue
            pr = predict_set(V, len(g), g.held.iloc[0])
            act_o = np.argsort(-g.p.to_numpy())
            act = g.p.to_numpy()[act_o]
            fl = g.filled.to_numpy()[act_o]
            pr = np.sort(np.array(pr))[::-1]
            h = np.abs(act - pr) <= TICK
            hs += int(h.sum())
            hn += int((np.abs(act - np.median(pr)) <= TICK).sum())
            hsf += int(h[fl].sum())
            n += len(g)
            nf += int(fl.sum())
        return {"orders": n, "set_unit": round(hs / n, 3) if n else None, "per_order_no_rank": round(hn / n, 3) if n else None,
                "filled_orders": nf, "set_unit_filled": round(hsf / nf, 3) if nf else None}
    out = {"bursts": int(len(B)), "adds": int(len(A)), "filled_adds": int(A.filled.sum()),
           "class_share_orders": {k: round(float(B.loc[B.cls == k, "n"].sum() / B.n.sum()), 3) for k in B.cls.unique()},
           "class_share_filled": {k: round(float(A[A.burst.isin(B.loc[B.cls == k, "burst"])].filled.sum() / max(A.filled.sum(), 1)), 3)
                                  for k in B.cls.unique()},
           "title_share_orders": {k: round(float(B.loc[B.title == k, "n"].sum() / B.n.sum()), 3) for k in B.title.unique()}}
    sels = {"all": np.ones(len(B), bool), "V_change": (B.cls == "V_change").to_numpy(), "refill_same_V": (B.cls == "refill_same_V").to_numpy(),
            "cs2": (B.title == "cs2").to_numpy(), "dota2": (B.title == "dota2").to_numpy()}
    out["oracle_L0_V_after"] = {k: score(lambda r: float(r.V), s) for k, s in sels.items()}
    for L in LAGS:
        out[f"L_{L:g}s"] = {k: score(lambda r, L=L: v_lag(r, L), s) for k, s in sels.items()}
        print(L, out[f"L_{L:g}s"]["all"], out[f"L_{L:g}s"]["V_change"]["set_unit"], out[f"L_{L:g}s"]["refill_same_V"]["set_unit"], flush=True)
    out["public_J"] = {k: score(lambda r: float(r.J) if np.isfinite(r.J) else np.nan, s) for k, s in sels.items()}
    (RES / "lag_tolerance.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("bursts", "adds", "filled_adds", "class_share_orders", "class_share_filled", "title_share_orders")}, indent=1))


if __name__ == "__main__":
    main()
