"""Iteration 6, X75 (mechanics panel iter5 P1, deep-state branches; BUILD-live 10-31 14:50-18:00): which anchor predicts
the price of its FILLED maker orders on the live book, by branch?

Book state at sign - 100 ms (server clock), token-0 books of its 7 dev-unit CS2 markets, own levels by fingerprint
(its maker sizes in that market, whole cents). Candidate anchors for an order on token z:
  J  = others' best bid on z (public);
  JC = min(J, 0.99 - own top bid on the other token) (own state: its book);
  R  = the price of its most recent own level removed (cancelled or consumed) on z's side within the last 2 s (refill /
       cooldown re-post; own state), else J;
  T  = its own current top on z's side (persistence; own state), else J;
  KL = 0.94 - the limit of its last take on the other token if that take was signed within 1.2 s (own state), else J.
Branches: own top at / within 1c of others' best; 2c+ behind; no own level; within 1.2 s after its own take.
Output: results/live_price_branches.json
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
OWN0, END = 1793458232, 1793469600


def within(p, a):
    a = np.asarray(a, float)
    tick = np.where((a >= 0.04) & (a <= 0.96), 0.01, 0.001)
    return np.abs(np.asarray(p, float) - a) <= tick + 1e-9


def main():
    dm = pd.read_parquet(OUT / "dev_markets.parquet")
    dm = dm[(dm.wallet_trades > 0) & dm.slug.str.startswith("cs2-")]
    t0map = {str(r.tok0): str(r.tok0) for r in dm.itertuples()}
    t0map.update({str(r.tok1): str(r.tok0) for r in dm.itertuples()})
    cd = pd.read_parquet(OUT / "calldata_dev.parquet")
    cd["tok"] = cd.token_id.astype(str)
    cd["a"] = cd.tok.map(t0map)
    w = cd[(cd.maker == WALLET) & cd.a.notna() & (cd.sign_ms >= OWN0 * 1000) & (cd.sign_ms < END * 1000)].copy()
    w["oi"] = np.where(w.tok == w.a, 0, 1)
    mo = w[w.idx >= 0].drop_duplicates(["salt", "sign_ms"])
    tk = w[(w.idx == -1) & (w.side == 0)]
    own_sizes = {a: set(np.round(g.shares.to_numpy(float), 2)) | {100.0} for a, g in w[w.idx >= 0].groupby("a")}
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"]).reset_index(drop=True)
    E["own"] = [bool(x) and (round(float(z), 2) in own_sizes.get(a, {100.0})) for a, z, x in zip(E.a, E["size"], E.whole)]
    rows = []
    for a, g in E.groupby("a"):
        q = mo[mo.a == a].sort_values("sign_ms")
        if q.empty:
            continue
        takes = tk[tk.a == a][["sign_ms", "oi", "price"]].sort_values("sign_ms").to_numpy()
        qs = q.sign_ms.to_numpy(float) - 100.0
        qi = 0
        lvl = {"BUY": {}, "SELL": {}}
        own = {"BUY": defaultdict(float), "SELL": defaultdict(float)}
        removed = {"BUY": [], "SELL": []}
        S = g.s.to_numpy(float); SD = g.side.to_numpy(); P = g.p.to_numpy(float); Z = g.z.to_numpy(float)
        D = g.d.to_numpy(float); K = g.kind.to_numpy(); O = g.own.to_numpy()

        def ans(upto):
            nonlocal qi
            while qi < len(qs) and qs[qi] < upto:
                r = q.iloc[qi]
                t = qs[qi]
                qi += 1
                z = int(r.oi)
                side = "BUY" if z == 0 else "SELL"
                oth_side = "SELL" if z == 0 else "BUY"
                conv = (lambda x: x) if z == 0 else (lambda x: 1 - x)
                oth = [p for p, v in lvl[side].items() if v - own[side].get(p, 0.0) > 0.5]
                if not oth:
                    continue
                J = conv(max(oth) if side == "BUY" else min(oth))
                mine = [p for p, v in own[side].items() if v > 0.5]
                T = conv(max(mine) if side == "BUY" else min(mine)) if mine else None
                other_mine = [p for p, v in own[oth_side].items() if v > 0.5]
                ot = None
                if other_mine:
                    ot = (1 - min(other_mine)) if z == 0 else max(other_mine)
                JC = min(J, 0.99 - ot) if ot is not None else J
                rem = [x for x in removed[side] if t - 2000 <= x[0] <= t]
                R = conv(rem[-1][1]) if rem else J
                kl = None
                if len(takes):
                    j = np.searchsorted(takes[:, 0], t + 100) - 1
                    if j >= 0 and t + 100 - takes[j, 0] <= 1200 and int(takes[j, 1]) != z:
                        kl = round(0.94 - float(takes[j, 2]), 2)
                gap = None if T is None else round((J - T) * 100)
                br = ("after_take" if kl is not None else "no_own_level" if T is None else
                      "at_or_1c" if gap is not None and gap <= 1 else "2c_plus_behind")
                rows.append({"p": round(float(r.price), 3), "J": J, "JC": JC, "R": R, "T": T if T is not None else J,
                             "KL": kl if kl is not None else J, "branch": br})

        for i in range(len(g)):
            ans(S[i])
            side, p, z, d, k, o = SD[i], P[i], Z[i], D[i], K[i], O[i]
            lvl[side][p] = z
            if z <= 1e-9:
                lvl[side].pop(p, None)
            if k == "add" and o:
                own[side][p] += abs(d)
            elif o and k in ("cancel", "cons"):
                own[side][p] = max(0.0, own[side][p] - abs(d))
                removed[side].append((S[i], p))
            if p in own[side]:
                before = own[side][p]
                own[side][p] = min(own[side][p], lvl[side].get(p, 0.0))
                if k == "cons" and before - own[side][p] > 0.5:
                    removed[side].append((S[i], p))
        ans(1e18)
    R = pd.DataFrame(rows)
    res = {"filled_orders": int(len(R)), "branch_n": R.branch.value_counts().to_dict()}
    for nm, x in [("all", R)] + [(b, y) for b, y in R.groupby("branch")]:
        res[nm] = {c: round(float(within(x.p, x[c]).mean()), 3) for c in ("J", "JC", "R", "T", "KL")}
        res[nm]["n"] = int(len(x))
    # a branch rule: after_take -> KL; 2c_plus_behind / no_own_level -> R; else J
    pick = np.where(R.branch == "after_take", R.KL, np.where(R.branch.isin(["2c_plus_behind", "no_own_level"]), R.R, R.J))
    res["branch_rule_KL_R_J"] = round(float(within(R.p, pick).mean()), 3)
    (RES / "live_price_branches.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
