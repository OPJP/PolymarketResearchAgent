"""R1 (round end known) vs R2 (in-round information): price path of the bought team after each taker cluster.
For every cluster (W = with the wallet's taker order; P4e-only; other pack-only) and random control times in the same
markets: public print price of the bought team (wallet txs excluded) at +h s relative to the last print before the
first signing, and the max / min over [0, 60] s and [0, 120] s. R1 predicts few large adverse moves within 60 s (the
next round takes ~100 s); R2 predicts adverse moves (the team loses the round in progress) in roughly a third.
Uses the map market of the cluster (else the match market). Development data 16-22 Oct only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import OUT, RES, SPLIT, TAPES  # noqa: E402

HS = [2, 5, 10, 20, 30, 60, 90, 120]


def main():
    po = pd.read_parquet(OUT / "pack_orders.parquet", columns=["cluster", "who", "cid", "team", "sign_ms", "map_no", "gs"])
    c = pd.read_parquet(OUT / "pack_clusters.parquet")
    wtx = set(pd.read_parquet(OUT / "calldata_all.parquet", columns=["tx"]).tx)
    first = po.sort_values("sign_ms").groupby("cluster").first()
    c = c.set_index("cluster").join(first[["cid"]])
    c["kind"] = np.where(c.has_W, "W", np.where(c.has_P4e, "P4e_only", "other"))
    rng = np.random.default_rng(11)
    rows = []
    for cid, g in c.groupby("cid"):
        p = TAPES / f"{cid}_tkw.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["timestamp", "price", "outcomeIndex", "transactionHash"])
        d = d[~d.transactionHash.isin(wtx)].sort_values("timestamp")
        if len(d) < 30:
            continue
        ts = d.timestamp.to_numpy().astype(float)
        p0 = np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float))
        lo, hi = ts.min(), ts.max()
        evs = [(t0 / 1000.0, team, kind, False) for t0, team, kind in zip(g.t0, g.team, g.kind)]
        evs += [(rng.uniform(lo, hi), int(rng.integers(0, 2)), "ctrl", True) for _ in range(len(g))]
        for t, team, kind, ctrl in evs:
            j0 = np.searchsorted(ts, t, side="right") - 1
            if j0 < 0:
                continue
            base = p0[j0] if team == 0 else 1 - p0[j0]
            r = {"cid": cid, "kind": kind, "gs": float(g.gs.iloc[0])}
            for hh in HS:
                j = np.searchsorted(ts, t + hh, side="right") - 1
                v = p0[j] if team == 0 else 1 - p0[j]
                r[f"m{hh}"] = v - base
            for W in (60, 120):
                a, b = np.searchsorted(ts, t, side="right"), np.searchsorted(ts, t + W, side="right")
                seg = p0[a:b] if team == 0 else 1 - p0[a:b]
                r[f"max{W}"] = (seg.max() - base) if len(seg) else 0.0
                r[f"min{W}"] = (seg.min() - base) if len(seg) else 0.0
            rows.append(r)
    x = pd.DataFrame(rows)
    x.to_parquet(OUT / "price_paths.parquet", index=False)
    res = {}
    for (kind, sp), s in x.groupby(["kind", x.gs >= SPLIT]):
        k = f"{kind}_{'VALIDATE' if sp else 'BUILD'}"
        res[k] = {"n": len(s), **{f"mean_m{hh}c": round(float(s[f'm{hh}'].mean() * 100), 2) for hh in HS},
                  "up4_within60": round(float((s.max60 >= 0.04).mean()), 3), "down4_within60": round(float((s.min60 <= -0.04).mean()), 3),
                  "down4_within120": round(float((s.min120 <= -0.04).mean()), 3),
                  "down4_first60_given_up4": round(float(((s.min60 <= -0.04) & (s.max60 >= 0.04)).mean()), 3),
                  "m60_gt0": round(float((s.m60 > 0.005).mean()), 3), "m60_lt0": round(float((s.m60 < -0.005).mean()), 3),
                  "m120_q": s.m120.quantile([.1, .25, .5, .75, .9]).round(3).tolist()}
    json.dump(res, open(RES / "results/price_paths.json", "w"), indent=1)
    for k, v in res.items():
        print(k, v)


if __name__ == "__main__":
    main()
