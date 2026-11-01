"""X139 (panel iter12 mechanics P5): the pairing-bid process from the wallet's own imbalance path (OWN STATE),
development block 10-31 14:00-16:53 (BTC 5m and 15m, dm_clob_raw; activity from the data-api live pulls).

For every own fill that changes a wallet's net Up-minus-Down position in a window to a new value Z != 0, the predicted
pairing bid is a BUY of |Z| shares (to 0.01) of the under-held outcome. Search the raw book for adds of exactly |Z| on
the under-held side of that market in [block second - 3 s, block second + 10 s] (the activity stamp is the block second;
the match is up to ~2 s earlier). Placebo: the same search for |Z| + 0.37. Report the share found, the latency from the
block second, and how long the size keeps being re-signed (last add of that size).
"""
from __future__ import annotations

import glob
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/it13"
H0, H1 = 1793455200, 1793465640   # 14:00 - 16:54
PL = 0.37


def main():
    fs = sorted(glob.glob(str(ROOT / ".cache/re/directional-maker/live_activity_17934*.parquet")))
    A = pd.concat([pd.read_parquet(f) for f in fs]).drop_duplicates(["transactionHash", "asset", "side", "size", "price", "w"])
    A = A[(A.type == "TRADE") & A.slug.str.startswith("btc-updown-") & (A.timestamp >= H0 - 600) & (A.timestamp < H1)].copy()
    A["isup"] = A.outcome.astype(str).str.lower() == "up"
    A["sgn"] = np.where(A.side == "BUY", 1.0, -1.0)
    A["d"] = A.sgn * A["size"] * np.where(A.isup, 1.0, -1.0)
    ev = []
    for (wal, slug), g in A.sort_values("timestamp").groupby(["w", "slug"]):
        # aggregate per block second (several fills in one block second change the position once)
        gs = g.groupby("timestamp").d.sum().cumsum()
        prev = 0.0
        for ts, z in gs.items():
            z = round(float(z), 2)
            if z != prev and z != 0 and ts >= H0:
                ev.append((wal, slug, int(ts), z))
            prev = z
    E = pd.DataFrame(ev, columns=["wallet", "w", "ts", "z"])
    E["size"] = E.z.abs().round(2)
    E["sd"] = np.where(E.z > 0, 0, 1)   # Up-heavy -> pairing bid on Down = an Up-book ask (sd 0); Down-heavy -> Up bid (sd 1)
    targets = set(E["size"]) | set((E["size"] + PL).round(2))
    print("imbalance changes", len(E), "distinct sizes", E["size"].nunique())
    book, hits = {}, []

    def it():
        for h in range(H0, H1, 3600):
            try:
                for r in live.iter_live("dm_clob_raw", h, min(h + 3600, H1)):
                    yield r
            except (zlib.error, EOFError, OSError) as e:
                print("read error", h, repr(e)[:60])
    for r in it():
        k = r.get("k")
        if k == "bk":
            bw = {1: {}, 0: {}}
            for p, z in r.get("b", []):
                bw[1][round(p, 3)] = z
            for p, z in r.get("o", []):
                bw[0][round(p, 3)] = z
            book[r["w"]] = bw
        elif k == "pc":
            bw = book.get(r["w"])
            if bw is None:
                continue
            for row in r["c"]:
                sd, p, z = row[0], round(row[1], 3), row[2]
                if sd >= 2:
                    continue
                old = bw[sd].get(p)
                bw[sd][p] = z
                if old is None:
                    continue
                dz = round(z - old, 2)
                if dz > 0 and dz in targets:
                    hits.append((r["w"], r["s"], sd, p, dz, row[3], row[4]))
    Hh = pd.DataFrame(hits, columns=["w", "s", "sd", "p", "dz", "bb", "ba"])
    res = []
    for e in E.itertuples(index=False):
        for plc, sz in ((0, e.size), (1, round(e.size + PL, 2))):
            g = Hh[(Hh.w == e.w) & (Hh.sd == e.sd) & (Hh.dz == sz) & (Hh.s >= (e.ts - 3) * 1000) & (Hh.s <= (e.ts + 10) * 1000)]
            gl = Hh[(Hh.w == e.w) & (Hh.sd == e.sd) & (Hh.dz == sz) & (Hh.s >= (e.ts - 3) * 1000) & (Hh.s <= (e.ts + 300) * 1000)]
            first = g.s.min() if len(g) else np.nan
            res.append(dict(wallet=e.wallet, w=e.w, ts=e.ts, size=e.size, placebo=plc, found=len(g) > 0,
                            lat=(first / 1000 - e.ts) if len(g) else np.nan, n_adds_300=len(gl),
                            last=(gl.s.max() / 1000 - e.ts) if len(gl) else np.nan,
                            rel_first=float((g.sort_values("s").iloc[0].p - g.sort_values("s").iloc[0].bb) if e.sd == 1 else (g.sort_values("s").iloc[0].ba - g.sort_values("s").iloc[0].p)) if len(g) else np.nan))
    R = pd.DataFrame(res)
    q = lambda x: np.nanpercentile(x, [10, 25, 50, 75, 90]).round(2).tolist() if np.isfinite(x).any() else None
    out = {}
    for plc, g in R.groupby("placebo"):
        nm = "placebo" if plc else "imbalance_size"
        out[nm] = {"n": int(len(g)), "found_within_10s": float(g.found.mean()), "latency_s_q": q(g.lat.to_numpy(float)),
                   "readds_in_300s_q": q(g.n_adds_300.to_numpy(float)), "last_add_after_s_q": q(g["last"].to_numpy(float)),
                   "first_add_rel_to_own_touch_q": q(g.rel_first.to_numpy(float)),
                   "by_wallet": {w: float(x.found.mean()) for w, x in g.groupby("wallet")},
                   "by_size": {"<20": float(g.found[g["size"] < 20].mean()), "20-100": float(g.found[(g["size"] >= 20) & (g["size"] < 100)].mean()),
                               ">=100": float(g.found[g["size"] >= 100].mean())}}
    print(json.dumps(out, indent=1))
    (HERE.parent / "results/iter13_pairing_process.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
