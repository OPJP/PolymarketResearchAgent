"""X177 (mechanics panel iter-12 P2), first pass on BUILD-live adds: does a signed public delta plus its own previous top
give its value? Pre-specified rules (no fitting), scored through the frozen X163 machine (code/iter12/ladder_machine.py:
predict_set, burst 20 ms, depth 5, band [0.05, 0.95]) on the burst-set unit and per order:
  R0 V = J (others' best bid, the iteration-12 proxy);
  R1 V = own top before the burst, J if it holds none (fresh);
  R2 R1 + 1c * sign(others' mid change over [t - 1000, t - 30] ms) when |change| >= 0.5c (own token space);
  R3 J + 1c * sign(the same change) when |change| >= 0.5c, else J;
  R4 R2 for bursts whose own top is <= 1c from J, J otherwise.
Own-state rules (R1, R2, R4) are labelled as such. Halves of the block (by time) reported separately.
Output: results/tick_rule.json
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


def main():
    R = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet").sort_values(["a", "oi", "t"]).reset_index(drop=True)
    R["a"] = R.a.astype(str)
    R["held"] = R.own_levels.map(parse_levels)
    A = R[R.kind == "add"].copy()
    A["burst"] = (A.groupby(["a", "oi"]).t.diff().fillna(1e9) > BURST_MS).cumsum()
    M = pd.read_parquet(OUT / "others_mid_dev.parquet").sort_values(["a", "s"])
    M["a"] = M.a.astype(str)
    mids = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby("a")}

    def dmid(a, oi, t):
        # others_mid_dev is per token 'a' in that token's space? use the token's own series; oi is the token side
        x = mids.get(a)
        if x is None:
            return np.nan
        ts, md = x
        j1 = np.searchsorted(ts, t - 30, side="right") - 1
        j0 = np.searchsorted(ts, t - 1000, side="right") - 1
        if j0 < 0 or j1 < 0:
            return np.nan
        return float(md[j1] - md[j0])
    first = A.groupby("burst").head(1).set_index("burst")
    first["dm"] = [dmid(r.a, r.oi, r.t) for r in first.itertuples()]
    t_mid = np.median(first.t)

    def rule(name, g, f):
        J = float(f.J) if np.isfinite(f.J) else np.nan
        ot = float(f.own_top) if np.isfinite(f.own_top) else np.nan
        dm = f.dm if np.isfinite(f.dm) else 0.0
        step = 0.01 * np.sign(dm) if abs(dm) >= 0.005 else 0.0
        if name == "R0":
            return J
        if name == "R1":
            return ot if np.isfinite(ot) else J
        if name == "R2":
            return (ot + step) if np.isfinite(ot) else J
        if name == "R3":
            return J + step if np.isfinite(J) else np.nan
        if name == "R4":
            return (ot + step) if (np.isfinite(ot) and np.isfinite(J) and abs(ot - J) <= 0.0101) else J
        return np.nan
    out = {"bursts": int(A.burst.nunique()), "adds": int(len(A)),
           "share_bursts_with_mid_move_ge_half_c": round(float(np.mean(np.abs(first.dm.fillna(0)) >= 0.005)), 3)}
    for name in ("R0", "R1", "R2", "R3", "R4"):
        res = {}
        for half, sel in (("all", lambda t: True), ("first_half", lambda t: t < t_mid), ("second_half", lambda t: t >= t_mid)):
            hs, hn, n = 0, 0, 0
            for b, g in A.groupby("burst"):
                f = first.loc[b]
                if not sel(f.t):
                    continue
                V = rule(name, g, f)
                if V is None or not np.isfinite(V):
                    continue
                pr = predict_set(V, len(g), g.held.iloc[0])
                if pr is None:
                    continue
                act = np.sort(g.p.to_numpy())[::-1]
                pr = np.sort(np.array(pr))[::-1]
                hs += int((np.abs(act - pr) <= TICK).sum())
                hn += int((np.abs(act - np.median(pr)) <= TICK).sum())
                n += len(g)
            res[half] = {"orders": n, "set_unit": round(hs / n, 3) if n else None, "per_order_no_rank": round(hn / n, 3) if n else None}
        out[name] = res
    (RES / "tick_rule.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
