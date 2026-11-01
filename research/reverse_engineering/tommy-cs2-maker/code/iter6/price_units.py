"""Iteration 6, X75 step 2 (mechanics panel iter5 P1: which price unit the examiner should score): on the BUILD-live
block, the join rule scored on three units of its maker quoting (own levels by fingerprint with its actual sizes):
  (a) filled orders (calldata; live_price_branches.json: J 0.419);
  (b) every own add (each level of every burst): rule J (others' best before the burst) and the ladder rule
      J - k cents for the k-th add of the burst in price order from the top (k = 0, 1, ...);
  (c) top changes only: bursts after which its own top differs from its top before the burst; rule J.
Output: results/price_units.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["a"] = cd.token_id.astype(str).map(t0map)
    wm = cd[(cd.idx >= 0) & (cd.maker == WALLET) & cd.a.notna()]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in wm.groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"]).reset_index(drop=True)
    E["own"] = [bool(x) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, x in zip(E.a, E["size"], E.whole)]
    adds, tops = [], []
    for (a, side), g in E.groupby(["a", "side"]):
        sgn = 1.0 if side == "BUY" else -1.0
        lvl, own = {}, defaultdict(float)

        def best(own_only):
            b = None
            for p, z in lvl.items():
                v = own.get(p, 0.0) if own_only else z - own.get(p, 0.0)
                if v > 0.5 and (b is None or sgn * (p - b) > 1e-9):
                    b = p
            return b

        S = g.s.to_numpy(float); P = g.p.to_numpy(float); Z = g.z.to_numpy(float); D = g.d.to_numpy(float)
        K = g.kind.to_numpy(); O = g.own.to_numpy()
        burst = None
        for i in range(len(g)):
            if K[i] == "add" and O[i] and burst is None:
                burst = {"J": best(False), "T0": best(True), "prices": []}
            p = P[i]
            lvl[p] = Z[i]
            if Z[i] <= 1e-9:
                lvl.pop(p, None)
            if K[i] == "add" and O[i]:
                own[p] += abs(D[i])
                burst["prices"].append(p)
            elif K[i] in ("cancel", "cons") and O[i]:
                own[p] = max(0.0, own[p] - abs(D[i]))
            if p in own:
                own[p] = min(own[p], lvl.get(p, 0.0))
            if burst is not None:
                nxt = i + 1 < len(g) and K[i + 1] == "add" and O[i + 1] and S[i + 1] - S[i] <= 5
                if not nxt:
                    J = burst["J"]
                    if J is not None:
                        pr = sorted(set(burst["prices"]), key=lambda x: -sgn * x)  # from the best price down
                        for k, x in enumerate(pr):
                            adds.append((round(sgn * (x - J) * 100), round(sgn * (x - (J - sgn * k / 100)) * 100)))
                        T1 = best(True)
                        if T1 is not None and (burst["T0"] is None or abs(T1 - burst["T0"]) > 1e-9):
                            tops.append(round(sgn * (T1 - J) * 100))
                    burst = None
    A = pd.DataFrame(adds, columns=["d_join", "d_ladder"])
    T = pd.Series(tops)
    res = {"unit_b_every_own_add": {"n": int(len(A)), "join_within_1c": round(float((A.d_join.abs() <= 1).mean()), 3),
                                    "ladder_within_1c": round(float((A.d_ladder.abs() <= 1).mean()), 3),
                                    "join_exact": round(float((A.d_join == 0).mean()), 3), "ladder_exact": round(float((A.d_ladder == 0).mean()), 3)},
           "unit_c_top_changes": {"n": int(len(T)), "join_within_1c": round(float((T.abs() <= 1).mean()), 3),
                                  "join_exact": round(float((T == 0).mean()), 3),
                                  "dist_c": T.clip(-6, 4).value_counts(normalize=True).sort_index().round(3).to_dict()},
           "unit_a_filled_orders": "live_price_branches.json: J 0.419, own top 0.453 (172 orders)"}
    (RES / "price_units.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
