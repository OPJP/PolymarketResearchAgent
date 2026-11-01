"""X163 (mechanics panel iter-11 P1): the maker price as one private number per burst (V) plus a mechanical ladder.

Rows: the mechanics panel's V-relative ladder state on BUILD-live (10-31 14:50-18:00, raw tommy_cs2_near book,
calldata-validated own label; produced by code/iter12/slot_vrel_panel.py, copied to
.cache/re/tommy-cs2-maker/iter12/slot_vrel_rows.parquet). Every validated own add with its own levels just before the
decision (own_levels) and V_after = its own top on the token just after the burst.

Frozen machine (constants below, fitted on nothing but the panel's description; BUILD-live is its only data so far):
  * a burst = own adds on one token whose pre-times are within BURST_MS of the previous add;
  * candidate slots V, V - 1c, ..., V - (DEPTH - 1)c inside the band [0.05, 0.95];
  * free = not held before the burst; variant C also blocks slots it vacated less than COOLDOWN_MS earlier (three
    504-ms loop ticks), read from its own levels in the earlier rows of the same token;
  * a burst of n adds takes the n highest free slots, top-first (extended below DEPTH if needed).
Units: per order without within-burst rank (each order gets the burst's median predicted slot), the set unit (orders
matched to predicted slots by price rank inside the burst), and per burst (every order of the burst within one tick
under the set unit). V sources: V_after (oracle), V_after shifted by -2..+2c, and public / own-state proxies (others'
best J, J + 1c, its own top before). Output: results/ladder_machine.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker"

BURST_MS = 20.0
DEPTH = 5
BAND = (0.05, 0.95)
COOLDOWN_MS = 1512.0
import os as _os
SUF = _os.environ.get("TOMMY_BLOCK_SUFFIX", "")
OWN0, END = int(_os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(_os.environ.get("TOMMY_BLOCK_END", 1793469600))
TICK = 0.0101


def parse_levels(s):
    if not isinstance(s, str) or not s:
        return set()
    return {round(float(x), 2) for x in s.split(",") if x}


def predict_set(V, n, held, blocked=frozenset()):
    if not np.isfinite(V):
        return None
    out, k = [], 0
    while len(out) < n and k < 15:
        p = round(V - k / 100, 2)
        if p < BAND[0] - 1e-9:
            break
        if p <= BAND[1] + 1e-9 and p not in held and p not in blocked:
            out.append(p)
        k += 1
    while len(out) < n:
        out.append(out[-1] if out else round(V, 2))
    return out


def main():
    R = pd.read_parquet(OUT / f"iter12/slot_vrel_rows{SUF}.parquet")
    R = R.sort_values(["a", "oi", "t"]).reset_index(drop=True)
    R["held"] = R.own_levels.map(parse_levels)
    # vacated-recently sets from earlier rows (adds and fills) of the same token
    vac = []
    for (a, oi), g in R.groupby(["a", "oi"], sort=False):
        ts = g.t.to_numpy(); hs = g.held.tolist()
        for i in range(len(g)):
            j = i - 1; rec = set()
            while j >= 0 and ts[i] - ts[j] <= COOLDOWN_MS:
                rec |= hs[j]; j -= 1
            vac.append((g.index[i], frozenset(rec - hs[i])))
    R["vacated"] = pd.Series(dict(vac))
    A = R[R.kind == "add"].copy()
    newb = (A.groupby(["a", "oi"]).t.diff().fillna(1e9) > BURST_MS)
    A["burst"] = newb.cumsum()
    A["cls"] = np.where(~np.isfinite(A.own_top), "fresh",
                        np.where(A.V_after > A.own_top + 1e-6, "up", np.where(A.V_after < A.own_top - 1e-6, "down", "same")))
    out = {"adds": int(len(A)), "bursts": int(A.burst.nunique()), "burst_ms": BURST_MS, "depth": DEPTH, "cooldown_ms": COOLDOWN_MS,
           "burst_size_counts": {int(k): int(v) for k, v in A.groupby("burst").size().value_counts().sort_index().items()}}

    def score(Vcol_fn, use_cool=False, label=""):
        hit_norank, hit_set, burst_ok, nb, n = 0, 0, 0, 0, 0
        cls_hits = {}
        for b, g in A.groupby("burst"):
            V = Vcol_fn(g)
            if V is None or not np.isfinite(V):
                continue
            held = g.held.iloc[0]
            blocked = g.vacated.iloc[0] if use_cool else frozenset()
            pr = predict_set(V, len(g), held, blocked)
            if pr is None:
                continue
            act = np.sort(g.p.to_numpy())[::-1]
            pr = np.sort(np.array(pr))[::-1]
            med = np.median(pr)
            h_set = np.abs(act - pr) <= TICK
            h_nr = np.abs(act - med) <= TICK
            hit_set += h_set.sum(); hit_norank += h_nr.sum(); n += len(g); nb += 1; burst_ok += int(h_set.all())
            c = g.cls.iloc[0]
            cls_hits.setdefault(c, [0, 0]); cls_hits[c][0] += h_set.sum(); cls_hits[c][1] += len(g)
        if n == 0:
            return {}
        return {"orders": int(n), "bursts": int(nb), "per_order_no_rank": round(hit_norank / n, 3), "set_unit": round(hit_set / n, 3),
                "per_burst": round(burst_ok / nb, 3), "set_unit_by_class": {k: [round(v[0] / v[1], 3), int(v[1])] for k, v in cls_hits.items()}}

    def vafter(g):
        return float(g.V_after.iloc[0])
    out["V_after"] = score(vafter)
    out["V_after_cooldown"] = score(vafter, use_cool=True)
    out["V_error_curve"] = {f"{d:+d}c": score(lambda g, d=d: float(g.V_after.iloc[0]) + d / 100)["set_unit"] for d in (-2, -1, 1, 2)}
    out["proxy_J"] = score(lambda g: float(g.J.iloc[0]) if np.isfinite(g.J.iloc[0]) else None)
    out["proxy_J_plus_1c"] = score(lambda g: float(g.J.iloc[0]) + 0.01 if np.isfinite(g.J.iloc[0]) else None)
    out["proxy_own_top_before"] = score(lambda g: float(g.own_top.iloc[0]) if np.isfinite(g.own_top.iloc[0]) else None)
    # residual class: V unchanged. What are these adds? slot of the add relative to V, held state, recent vacancy
    S = A[A.cls == "same"].copy()
    S["slot"] = np.round((S.p - S.V_after) * 100)
    S["was_vacated"] = [round(p, 2) in v for p, v in zip(S.p, S.vacated)]
    out["same_V_class"] = {"adds": int(len(S)), "slot_dist": {int(k): int(v) for k, v in S.slot.value_counts().sort_index().items()},
                           "share_at_recently_vacated_price": round(float(S.was_vacated.mean()), 3),
                           "n_own_before_median": float(S.n_own.median())}
    (RES / f"results/ladder_machine{SUF}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
