"""X182 step 1 (assumptions panel iter-12 P3): are there quote followers that peg to its new top? BUILD-live
(10-31 12-18). For every own ADD burst (untriggered and triggered separately), the rate of non-own adds (level events,
kind add, BUY side, own-size levels removed by the burst table within 3 ms) at its new top price on the same token
within (0, 2] s after the burst, against the same count at +-5..+-30-s shifted burst times; also at its top +- 1c, and
the share of its top price level that is held by others 2 s later. If followers peg to it, the 'lead' of its level
over the others' mid (X135 / finding 14) can be partly theirs.
Output: results/follower_census.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"


def main():
    ob = pd.read_parquet(OUT / "own_bursts_dev.parquet")
    ob["a"] = ob.a.astype(str)
    le = pd.read_parquet(OUT / "level_events_dev.parquet", columns=["a", "s", "side", "p", "kind", "size", "d"])
    le["a"] = le.a.astype(str)
    adds = le[(le.kind == "add") & (le.side == "BUY")].copy()
    # remove own levels: events within 3 ms of an own burst on the same token
    own_t = {a: np.sort(g.s.to_numpy(float)) for a, g in ob.groupby("a")}
    keep = np.ones(len(adds), bool)
    for a, g in adds.groupby("a"):
        arr = own_t.get(a)
        if arr is None:
            continue
        s = g.s.to_numpy(float)
        j = np.searchsorted(arr, s)
        d = np.minimum(np.abs(s - arr[np.clip(j - 1, 0, len(arr) - 1)]), np.abs(s - arr[np.clip(j, 0, len(arr) - 1)]))
        keep[adds.index.get_indexer(g.index)] = d > 3
    oth = adds[keep]
    byk = {}
    for (a, p), g in oth.groupby(["a", "p"]):
        byk[(a, round(float(p), 2))] = np.sort(g.s.to_numpy(float))

    def count(a, p, t0, t1):
        arr = byk.get((a, round(float(p), 2)))
        if arr is None:
            return 0
        return int(np.searchsorted(arr, t1, side="right") - np.searchsorted(arr, t0, side="right"))
    own_adds = ob[(ob.kind == "add") & (ob.side == "BUY")]
    out = {}
    for name, sel in (("untriggered", ~own_adds.triggered.astype(bool)), ("triggered", own_adds.triggered.astype(bool))):
        X = own_adds[sel]
        obs, ctl, obs_pm1, ctl_pm1 = [], [], [], []
        for r in X.itertuples():
            top = r.pmax
            obs.append(count(r.a, top, r.s, r.s + 2000))
            obs_pm1.append(count(r.a, top - 0.01, r.s, r.s + 2000) + count(r.a, top + 0.01, r.s, r.s + 2000))
            c, c1 = [], []
            for sh in (-30000, -20000, -10000, -5000, 5000, 10000, 20000, 30000):
                c.append(count(r.a, top, r.s + sh, r.s + sh + 2000))
                c1.append(count(r.a, top - 0.01, r.s + sh, r.s + sh + 2000) + count(r.a, top + 0.01, r.s + sh, r.s + sh + 2000))
            ctl.append(np.mean(c))
            ctl_pm1.append(np.mean(c1))
        obs, ctl = np.array(obs), np.array(ctl)
        out[name] = {"bursts": int(len(X)), "share_with_follower_at_top_0_2s": round(float(np.mean(obs > 0)), 3),
                     "mean_followers_at_top": round(float(obs.mean()), 3), "shifted_mean_at_top": round(float(ctl.mean()), 3),
                     "ratio": round(float(obs.mean() / max(ctl.mean(), 1e-9)), 2),
                     "mean_at_top_pm1c": round(float(np.mean(obs_pm1)), 3), "shifted_mean_pm1c": round(float(np.mean(ctl_pm1)), 3)}
    (RES / "follower_census.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
