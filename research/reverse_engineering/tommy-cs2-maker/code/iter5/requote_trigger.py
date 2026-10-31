"""Iteration 5, mechanics panel iter4 P4 (X63), first pass on the 10-31 14:50-18:00 development block (server clock):
what precedes the wallet's maker re-quote bursts, and is there an internal clock?

Own adds = level increases of exactly 100 / 68 / 58 / 54 shares at whole-cent prices (its ladder fingerprint) in the
token-0 books of its dev-unit CS2 markets (level_events_dev.parquet); adds within 5 ms on one market = one burst.
For each burst at s, the share with, in [s - W, s - 2] ms on the same market: (a) a consumption (trade) event,
(b) an own-size cancel (its own pull), (c) a non-own level change within 1c of the best on either side (others' touch
moving), (d) none of these. Null: the same windows at s + 7 / 13 / 23 s shifts.
Clock: inter-burst intervals per market (p10..p90) and the share within 1,000-1,150 ms (the FAK-return interval) and
in narrow bins around multiples of a candidate period.
Output: results/requote_trigger.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
OWN = (100.0, 68.0, 58.0, 54.0)
SHIFTS = (7000, 13000, 23000, -7000, -13000)


def main():
    E = pd.read_parquet(OUT / "level_events_dev.parquet").sort_values("s")
    E["own"] = E["size"].round(2).isin(OWN) & E.whole
    adds = E[(E.kind == "add") & E.own]
    res = {"markets": int(E.a.nunique()), "own_adds": int(len(adds))}
    out = {}
    allint = []
    for W in (50, 200, 1000):
        hits = {"cons": [], "own_cancel": [], "others_touch": [], "none": []}
        nulls = {"cons": [], "own_cancel": [], "others_touch": [], "none": []}
        for a, g in E.groupby("a"):
            ad = adds[adds.a == a].s.to_numpy(float)
            if len(ad) == 0:
                continue
            b = ad[np.r_[True, np.diff(ad) > 5]]
            if W == 50:
                allint.extend(np.diff(b).tolist())
            s = g.s.to_numpy(float)
            kind = g.kind.to_numpy()
            own = g.own.to_numpy()
            p = g.p.to_numpy(float)
            # best bid / ask of the token-0 book is not stored per event; approximate "near the touch" by events at the
            # extreme prices seen in the last 2 s on each side
            side = g.side.to_numpy()
            cons_t = s[kind == "cons"]
            oc_t = s[(kind == "cancel") & own]
            no = (~own) & (kind != "cons")
            nt_s, nt_p, nt_side = s[no], p[no], side[no]

            def flags(t):
                c = np.searchsorted(cons_t, t - 2) - np.searchsorted(cons_t, t - W) > 0
                o = np.searchsorted(oc_t, t - 2) - np.searchsorted(oc_t, t - W) > 0
                lo, hi = np.searchsorted(nt_s, t - W), np.searchsorted(nt_s, t - 2)
                tch = False
                if hi > lo:
                    # touch proxy: max bid / min ask among level events of the last 2 s
                    l2 = np.searchsorted(s, t - 2000)
                    pb = p[l2:np.searchsorted(s, t)][side[l2:np.searchsorted(s, t)] == "BUY"]
                    pa = p[l2:np.searchsorted(s, t)][side[l2:np.searchsorted(s, t)] != "BUY"]
                    bb = pb.max() if len(pb) else -1
                    ba = pa.min() if len(pa) else 2
                    x_p, x_s = nt_p[lo:hi], nt_side[lo:hi]
                    tch = bool(np.any(((x_s == "BUY") & (x_p >= bb - 0.0105)) | ((x_s != "BUY") & (x_p <= ba + 0.0105))))
                return c, o, tch

            for t in b:
                c, o, tch = flags(t)
                hits["cons"].append(c); hits["own_cancel"].append(o); hits["others_touch"].append(tch); hits["none"].append(not (c or o or tch))
                for sh in SHIFTS:
                    c, o, tch = flags(t + sh)
                    nulls["cons"].append(c); nulls["own_cancel"].append(o); nulls["others_touch"].append(tch); nulls["none"].append(not (c or o or tch))
        out[f"W{W}ms"] = {k: {"rate": round(float(np.mean(hits[k])), 4), "null": round(float(np.mean(nulls[k])), 4),
                              "ratio": round(float(np.mean(hits[k]) / max(np.mean(nulls[k]), 1e-9)), 2)} for k in hits}
        out[f"W{W}ms"]["bursts"] = len(hits["none"])
    res["preceding"] = out
    iv = np.array(allint)
    iv = iv[iv > 0]
    res["inter_burst_ms_p10_p25_p50_p75_p90"] = [round(float(x), 0) for x in np.percentile(iv, [10, 25, 50, 75, 90])]
    res["share_in_1000_1150ms"] = round(float(((iv >= 1000) & (iv < 1150)).mean()), 4)
    h, edges = np.histogram(iv[iv < 5000], bins=np.arange(0, 5001, 50))
    res["interval_hist_top_bins_ms"] = [(int(edges[i]), int(h[i])) for i in np.argsort(h)[::-1][:12]]
    (RES / "requote_trigger.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
