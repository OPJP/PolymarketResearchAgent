"""Iteration 8, X108 (mechanics panel iter7 P2): the maker ladder as an own-state machine (price item), BUILD-live.

Own ladder per (book, token): prices q (as bids on that token: token-0 bids = BUY side p, token-1 bids = SELL side 1 - p)
with a validated own add and, since that add, no validated own cancel at q and no drop of the level to 0. For every
validated own add (single adds and each level of multi-level bursts; the add's price as a bid on its token), candidate
predictions from state just before the burst (s - 1 ms):
  touch    = best bid on the token (full book) at s - 100 ms (the frozen live anchor);
  refill   = the most recently vacated own price on the token (own validated cancel or level -> 0) within 3 s;
  top      = own top (highest own bid) before the burst; extend = own bottom - 1c;
  machine  = refill if a slot was vacated within 3 s, else (touch if the token has no own level, else own bottom - 1c),
             and for the k-th level of a multi-level burst, (first-level prediction) - (k - 1) cents.
Score: share of adds within one tick (0.01 mid-range, else 0.001) per rule, first half vs second half of the block
(the machine has no fitted constants; the 3-s window and the rule order were set before scoring). Own state is used:
reported separately from the no-own-state touch. Output: results/ladder_machine.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")


def main():
    A = pd.read_parquet(OUT / f"linked_adds_dev{SUF}.parquet")
    A["vown"] = (A.owner == "wallet") | (A.F_mkt & (A.in_burst | (A["size"] != 100)))
    E = pd.read_parquet(OUT / f"level_events_dev{SUF}.parquet", columns=["a", "s", "side", "p", "z", "kind", "d"])
    E = E[E.a.isin(set(A.a))].sort_values("s")
    own_sz = {a: set(g["size"]) for a, g in A[A.vown].groupby("a")}
    C = E[E.kind == "cancel"].copy()
    C["size"] = C.d.abs().round(2)
    C["f"] = [bool(abs(p * 100 - round(p * 100)) < 1e-6) and z in own_sz.get(a, {100.0}) for a, p, z in zip(C.a, C.p, C["size"])]
    multi = np.zeros(len(C), bool)
    C = C.reset_index(drop=True)
    for _, g in C[C.f].groupby(["a", "side"]):
        s_, z_, ix = g.s.to_numpy(), g["size"].to_numpy(), g.index.to_numpy()
        for i in range(len(g)):
            if ((np.abs(s_ - s_[i]) <= 5) & (z_ == z_[i])).sum() >= 2:
                multi[ix[i]] = True
    C["vown"] = C.f & (multi | (C["size"] != 100))
    q = lambda side, p: round(p, 3) if side == "BUY" else round(1 - p, 3)  # noqa: E731
    out = []
    for (a, side), adds in A[A.vown].sort_values("s").groupby(["a", "side"]):
        Ls = E[(E.a == a)]
        Lside = Ls[Ls.side == side]
        cans = C[(C.a == a) & (C.side == side) & C.vown]
        zero = Lside[Lside.z <= 0]
        # event stream for own state: adds (+), own cancels (-), level -> 0 (-)
        evs = [(r.s, 1, q(side, r.p)) for r in adds.itertuples()] + [(r.s, -1, q(side, r.p)) for r in cans.itertuples()] + \
              [(r.s, -1, q(side, r.p)) for r in zero.itertuples()]
        evs.sort()
        # best bid on the token at time t (full book): token-0 bids = BUY side; token-1 bids = 1 - best ask of token 0
        st = Ls[["s", "side", "p", "z"]].to_numpy()
        lv = {}
        times, tops = [], []
        for s_, sd, p_, z_ in st:
            if z_ > 0:
                lv[(sd, p_)] = z_
            else:
                lv.pop((sd, p_), None)
            if side == "BUY":
                bb = max([pp for (ss, pp) in lv if ss == "BUY"], default=np.nan)
            else:
                aa = min([pp for (ss, pp) in lv if ss == "SELL"], default=np.nan)
                bb = 1 - aa if aa == aa else np.nan
            times.append(s_)
            tops.append(bb)
        times, tops = np.array(times, float), np.array(tops, float)
        own, vac = {}, []  # own price -> count; vacated (time, price)
        k = 0
        bursts = []
        cur = []
        for r in adds.itertuples():
            if cur and r.s - cur[0].s > 5:
                bursts.append(cur)
                cur = []
            cur.append(r)
        if cur:
            bursts.append(cur)
        for bu in bursts:
            s0 = bu[0].s
            while k < len(evs) and evs[k][0] < s0:
                t_, sg, pr = evs[k]
                if sg > 0:
                    own[pr] = own.get(pr, 0) + 1
                elif own.get(pr, 0) > 0:
                    own[pr] -= 1
                    if own[pr] == 0:
                        own.pop(pr)
                    vac.append((t_, pr))
                k += 1
            j = np.searchsorted(times, s0 - 100, side="right") - 1
            touch = tops[j] if j >= 0 else np.nan
            rec = [pr for t_, pr in vac if s0 - 3000 <= t_ < s0]
            refill = rec[-1] if rec else np.nan
            top = max(own) if own else np.nan
            bottom = min(own) if own else np.nan
            first = refill if rec else (touch if not own else round(bottom - 0.01, 3))
            prices = sorted({q(side, r.p) for r in bu}, reverse=True)
            for kk, pr in enumerate(prices):
                out.append({"a": a, "side": side, "s": s0, "n": len(prices), "k": kk, "p": pr, "touch": touch - 0.01 * kk,
                            "refill": refill - 0.01 * kk if rec else np.nan, "top": top - 0.01 * kk if own else np.nan,
                            "extend": round(bottom - 0.01 * (kk + 1), 3) if own else np.nan, "machine": round(first - 0.01 * kk, 3),
                            "has_refill": bool(rec), "has_own": bool(own)})
            # the burst's adds enter own state through evs (already in the stream)
    X = pd.DataFrame(out)
    X = X[X.touch.notna()]
    tick = np.where((X.p >= 0.04) & (X.p <= 0.96), 0.01, 0.001)
    mid = X.s.median()
    res = {"adds": int(len(X)), "bursts": int(X.groupby(["a", "side", "s"]).ngroups), "share_with_refill": round(float(X.has_refill.mean()), 3),
           "share_with_own": round(float(X.has_own.mean()), 3)}
    for c in ("touch", "refill", "top", "extend", "machine"):
        ok = (np.abs(X.p - X[c]) <= tick + 1e-9) & X[c].notna()
        res[c] = {"all": round(float(ok.mean()), 3), "first_half": round(float(ok[X.s < mid].mean()), 3),
                  "second_half": round(float(ok[X.s >= mid].mean()), 3),
                  "first_level_only": round(float(ok[X.k == 0].mean()), 3)}
    m = X.has_refill
    res["refill_when_available"] = round(float(((np.abs(X.p - X.refill) <= tick + 1e-9) & m).sum() / max(m.sum(), 1)), 3)
    res["touch_when_refill_available"] = round(float(((np.abs(X.p - X.touch) <= tick + 1e-9) & m).sum() / max(m.sum(), 1)), 3)
    best = np.zeros(len(X), bool)
    for c in ("touch", "refill", "top", "extend"):
        best |= (np.abs(X.p - X[c]) <= tick + 1e-9).to_numpy() & X[c].notna().to_numpy()
    res["oracle_union_of_4_rules"] = round(float(best.mean()), 3)
    off = np.round((X.p - X.touch) * 100).clip(-8, 4)
    res["offset_from_touch_cents"] = {str(int(k)): round(float(v), 3) for k, v in off[X.k == 0].value_counts(normalize=True).sort_index().items()}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"ladder_machine{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
