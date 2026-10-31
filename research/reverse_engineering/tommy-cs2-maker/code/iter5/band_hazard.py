"""Iteration 5, mechanics panel iter4 P4 (X63) second pass: the maker re-quote as a band on OTHERS' book, with own-level
tracking, on the 10-31 14:50-18:00 development block (server clock; level_events_dev.parquet, the wallet's 7 dev-unit
CS2 token-0 books; both of its ladders: bids on token 0 = BUY side, bids on token 1 = SELL side at 1 - p).

Own levels by fingerprint: an add of exactly 100 / 68 / 58 / 54 shares at a whole cent adds an own order there; an
own-size cancel removes one; the own amount at a level is capped by the level's size after every event (consumption).
Others' best = the best price on that side whose size net of own orders is > 0.5 share. Its top = its best own level.
(a) Price rule at its re-quotes: for each own add burst (adds within 5 ms on a side), new top minus others' best
    just before, in cents (positive = better than others), split by whether the burst follows its own take (1-1.15 s).
(b) Hazard: after each change of others' best on a side, the gap g = its top - others' best (cents, in the side's
    "better" direction); the share of such moments followed by an own add or own cancel on that side within 100 / 500 ms,
    by g bucket; time-shift null = the same moments' own-action rate in [+5, +5.1] / [+5, +5.5] s.
Output: results/band_hazard.json
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
OWN = (100.0, 68.0, 58.0, 54.0)


def better(side, a, b):
    """True if price a is better than b on this side (BUY: higher; SELL: lower)."""
    return a > b + 1e-9 if side == "BUY" else a < b - 1e-9


def main():
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values(["a", "s"])
    E["own"] = E["size"].round(2).isin(OWN) & E.whole
    req_rows, haz_rows = [], []
    for (a, side), g in E.groupby(["a", "side"]):
        lvl = {}  # price -> size
        own = defaultdict(float)
        s_arr = g.s.to_numpy(float); p_arr = g.p.to_numpy(float); z_arr = g.z.to_numpy(float); d_arr = g.d.to_numpy(float)
        k_arr = g.kind.to_numpy(); o_arr = g.own.to_numpy()
        own_act = s_arr[o_arr & (k_arr != "cons")]

        def tops():
            ob = None
            mt = None
            for p, z in lvl.items():
                if z - own.get(p, 0.0) > 0.5 and (ob is None or better(side, p, ob)):
                    ob = p
                if own.get(p, 0.0) > 0.5 and (mt is None or better(side, p, mt)):
                    mt = p
            return ob, mt

        prev_ob = None
        last_burst = -1e18
        burst_pre = None
        for i in range(len(g)):
            s, p, z, d, k, o = s_arr[i], p_arr[i], z_arr[i], d_arr[i], k_arr[i], o_arr[i]
            ob0, mt0 = tops()
            if k == "add" and o:
                if s - last_burst > 5:
                    burst_pre = (ob0, mt0, s)
                last_burst = s
            lvl[p] = z
            if z <= 1e-9:
                lvl.pop(p, None)
            if k == "add" and o:
                own[p] += abs(d)
            elif k == "cancel" and o:
                own[p] = max(0.0, own[p] - abs(d))
            if p in own:
                own[p] = min(own[p], lvl.get(p, 0.0))
            ob1, mt1 = tops()
            # (a) record the burst's resulting top vs others' best before it (when the next event is not in the same burst)
            if k == "add" and o and burst_pre is not None:
                nxt_same = i + 1 < len(g) and k_arr[i + 1] == "add" and o_arr[i + 1] and s_arr[i + 1] - s <= 5
                if not nxt_same and burst_pre[0] is not None and mt1 is not None:
                    sign = 1 if side == "BUY" else -1
                    req_rows.append((a, side, s, round(sign * (mt1 - burst_pre[0]) * 100, 1)))
            # (b) hazard after others' best changes
            if ob1 is not None and (prev_ob is None or abs(ob1 - prev_ob) > 1e-9) and not o:
                sign = 1 if side == "BUY" else -1
                gap = None if mt1 is None else round(sign * (mt1 - ob1) * 100, 1)
                j1 = np.searchsorted(own_act, s + 1) ; j100 = np.searchsorted(own_act, s + 100); j500 = np.searchsorted(own_act, s + 500)
                n0 = np.searchsorted(own_act, s + 5000); n100 = np.searchsorted(own_act, s + 5100); n500 = np.searchsorted(own_act, s + 5500)
                haz_rows.append((a, side, s, gap, int(j100 > j1), int(j500 > j1), int(n100 > n0), int(n500 > n0)))
            prev_ob = ob1
    R = pd.DataFrame(req_rows, columns=["a", "side", "s", "top_minus_others_c"])
    Hh = pd.DataFrame(haz_rows, columns=["a", "side", "s", "gap_c", "act100", "act500", "null100", "null500"])
    res = {"requote_bursts": int(len(R)), "others_best_changes": int(len(Hh))}
    vc = R.top_minus_others_c.clip(-6, 3).value_counts(normalize=True).sort_index()
    res["requote_top_minus_others_best_c_share"] = {str(k): round(float(v), 3) for k, v in vc.items()}
    res["requote_within_1c_of_others_best"] = round(float((R.top_minus_others_c.abs() <= 1.0).mean()), 3)
    res["requote_exactly_join"] = round(float((R.top_minus_others_c == 0).mean()), 3)
    Hh["gap_b"] = np.where(Hh.gap_c.isna(), "no_own_level", Hh.gap_c.clip(-6, 3).astype(str))
    hz = {}
    for b, x in Hh.groupby("gap_b"):
        hz[b] = {"n": int(len(x)), "own_action_100ms": round(float(x.act100.mean()), 3), "null_100ms": round(float(x.null100.mean()), 3),
                 "own_action_500ms": round(float(x.act500.mean()), 3), "null_500ms": round(float(x.null500.mean()), 3)}
    res["hazard_by_gap_c"] = hz
    (RES / "band_hazard.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
