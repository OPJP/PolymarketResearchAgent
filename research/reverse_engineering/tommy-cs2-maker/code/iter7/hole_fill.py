"""Iteration 7, X100 (assumptions panel iter6 P4): is the price of each own add the highest unoccupied level of a target
ladder {J, J - 1c, ..., J - (N - 1)c} (J = the join anchor), given its own resting set? BUILD-live only (10-31
14:50-18:00 UTC, tommy_cs2_near, server clock, the 7 token-0 books); the first half (by time) chooses N, the second half
scores it.

Queries: own adds = calldata-linked wallet adds (filled orders, ground truth) and validated own adds (label_validate.py).
State at the add's server time - 120 ms (its sign -> add latency is ~24 ms; the rule reads the book 100 ms before signing):
  J = others' best bid on the add's token (own levels removed by the tracker), whole cent (floor);
  R = its own resting whole-cent levels on that token (tracker: frozen F_mkt label for recall, or validated label);
  prediction = max{J - k c : k = 0..N-1, J - k c not in R}, else J - N c.
Baselines on the same rows: join J; own top (max R); J - 1c.
Price units: token-1 bids are the SELL side of the token-0 book at 1 - p (converted to bid terms).
Output: results/hole_fill.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
OWN0, END = 1793458232, 1793469600
VIEW = 120.0


def main():
    A = pd.read_parquet(OUT / "linked_adds_dev.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    books = set(A.a)
    own_sz = {a: set(g["size"]) | {100.0} for a, g in A[A.F_mkt].groupby("a")}
    vset = {(r.a, r.side, round(float(r.p), 3), int(r.s)) for r in A[A.vown].itertuples()}
    Q = A[A.vown & A.whole].copy()
    Q["truth"] = Q.owner == "wallet"
    Q["qt"] = Q.s - VIEW
    Q = Q.sort_values("qt")
    qs = {a: g[["qt", "side", "p", "truth", "s", "in_burst"]].to_numpy() for a, g in Q.groupby("a")}
    qi = {a: 0 for a in qs}
    st = {}
    rows = []
    trackers = ("frozen", "valid")

    def bidterms(side, p):
        return round(p, 2) if side == "BUY" else round(1 - p, 2)

    def answer(a, upto):
        b, o, own = st[a]
        arr = qs[a]
        while qi[a] < len(arr) and arr[qi[a]][0] < upto:
            qt, side, p, truth, s, ib = arr[qi[a]]
            qi[a] += 1
            rec = {"a": a, "s": float(s), "side": side, "q": bidterms(side, float(p)), "truth": bool(truth), "single": not bool(ib)}
            for tr in trackers:
                ob, oo = own[tr]
                if side == "BUY":
                    oth = [x for x, z in b.items() if z - ob.get(x, 0.0) > 0.5]
                    J = max(oth) if oth else None
                    R = sorted({round(x, 2) for x, z in ob.items() if z > 0.5 and abs(x * 100 - round(x * 100)) < 1e-6})
                else:
                    oth = [x for x, z in o.items() if z - oo.get(x, 0.0) > 0.5]
                    J = (1 - min(oth)) if oth else None
                    R = sorted({round(1 - x, 2) for x, z in oo.items() if z > 0.5 and abs(x * 100 - round(x * 100)) < 1e-6})
                rec["J_" + tr] = None if J is None else np.floor(J * 100 + 1e-6) / 100
                rec["R_" + tr] = R
            rows.append(rec)

    h = int(OWN0 // 3600 * 3600)
    while h < END:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, OWN0), min(h + 3600, END)):
                a = r.get("a")
                if a not in qs or "s" not in r:
                    continue
                s = float(r["s"])
                if a in st:
                    answer(a, s)
                k = r.get("k")
                if k in ("q", "f"):
                    b = {float(p): float(z) for p, z in (r.get("b") or [])}
                    o = {float(p): float(z) for p, z in (r.get("o") or [])}
                    own = {}
                    for tr in trackers:
                        if a in st:
                            pb, po = st[a][2][tr]
                            own[tr] = ({p: min(v, b.get(p, 0.0)) for p, v in pb.items()}, {p: min(v, o.get(p, 0.0)) for p, v in po.items()})
                        else:
                            own[tr] = ({}, {})
                    st[a] = (b, o, own)
                elif k == "pc" and a in st:
                    b, o, own = st[a]
                    for sd, p, z in r.get("c") or []:
                        p, z = float(p), float(z)
                        book = b if sd == "BUY" else o
                        d = z - book.get(p, 0.0)
                        whole = abs(p * 100 - round(p * 100)) < 1e-6
                        fz = whole and round(abs(d), 2) in own_sz.get(a, {100.0})
                        for tr in trackers:
                            ow = own[tr][0] if sd == "BUY" else own[tr][1]
                            if d > 0:
                                ok = fz if tr == "frozen" else ((a, sd, round(p, 3), int(s)) in vset)
                                if ok:
                                    ow[p] = ow.get(p, 0.0) + d
                            elif fz:
                                ow[p] = max(0.0, ow.get(p, 0.0) + d)
                        if z == 0:
                            book.pop(p, None)
                        else:
                            book[p] = z
                        for tr in trackers:
                            ow = own[tr][0] if sd == "BUY" else own[tr][1]
                            if p in ow:
                                ow[p] = min(ow[p], book.get(p, 0.0))
        except Exception as e:  # noqa: BLE001
            print("feed", type(e).__name__, flush=True)
        h += 3600
    for a in qs:
        if a in st:
            answer(a, 1e18)
    D = pd.DataFrame(rows)
    D = D.sort_values("s").reset_index(drop=True)
    half = D.s.median()

    def pred(J, R, N):
        if J is None or (isinstance(J, float) and np.isnan(J)):
            return np.nan
        occ = set(R)
        for k in range(N):
            x = round(J - k / 100, 2)
            if x not in occ:
                return x
        return round(J - N / 100, 2)

    def within(x, y):
        ok = ~np.isnan(y)
        return round(float((np.abs(x[ok] - y[ok]) <= 0.01 + 1e-9).mean()), 3) if ok.any() else None

    res = {"queries": int(len(D)), "truth_rows": int(D.truth.sum())}
    for tr in trackers:
        J = D["J_" + tr].astype(float).to_numpy()
        x = D.q.to_numpy(float)
        top = np.array([max(r) if len(r) else np.nan for r in D["R_" + tr]])
        first = (D.s <= half).to_numpy()
        fitN = {N: within(x[first], np.array([pred(j, r, N) for j, r in zip(J[first], D["R_" + tr][first])])) for N in range(2, 9)}
        Nbest = max(fitN, key=lambda n: fitN[n] or 0)
        P = np.array([pred(j, r, Nbest) for j, r in zip(J, D["R_" + tr])])
        o = {"fit_first_half_by_N": fitN, "N": Nbest}
        for nm, m in (("second_half_all", ~first), ("second_half_single", (~first) & D.single.to_numpy()),
                      ("second_half_filled_truth", (~first) & D.truth.to_numpy()),
                      ("all_filled_truth", D.truth.to_numpy())):
            o[nm] = {"n": int(m.sum()), "hole_fill": within(x[m], P[m]), "join": within(x[m], J[m]),
                     "join_minus_1c": within(x[m], J[m] - 0.01), "own_top": within(x[m], top[m]),
                     "exact_hole_fill": round(float((np.abs(x[m] - P[m]) < 1e-9).mean()), 3) if m.any() else None}
        res[tr] = o
    (RES / "hole_fill.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
