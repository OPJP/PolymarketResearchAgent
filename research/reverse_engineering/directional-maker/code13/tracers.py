"""directional-maker iteration 13, X135 / X136 / X138 (panel iter12 mechanics P1, P2, P4): tracer orders.

A tracer is a cluster maker BUY order whose calldata original size is not a schedule size (the imbalance pairing bid,
X92). Its size is unique to 0.01 share, so every re-sign is visible in the full-depth raw book (dm_clob_raw, every
price change with server ms) as an add of exactly that size. Development block 10-31 12-18 only (iter_live returns
development blocks only; the 14:00 file has a corrupt gzip block and is read up to it).

Output: .cache/re/directional-maker/it13/tracer_events.parquet (one row per exact-size add before the order's fill) and
it13/sched_adds.parquet (schedule-size adds within 0.20 of the touch, for the same-pass ladder), it13/trades.parquet.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code13/tracers.py 1793455200 1793469600
"""
from __future__ import annotations

import glob
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
CL = {"0x32ed2e546b187ca15e2841edc82b22c713cf8ec3": "momoney", "0x3725d52f3c252e8374999cc8617292ea2608ad88": "almach",
      "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed": "bosona"}
SCHED = {5, 10, 12, 20, 25, 31, 40, 50, 62, 100, 125, 200, 250, 300, 400, 500, 1000, 2000}
RUNG = {500.0, 250.0, 62.0, 100.0, 12.0, 50.0, 125.0, 1000.0, 25.0, 31.0, 200.0, 2000.0}


def it(h0, h1):
    for h in range(h0, h1, 3600):
        try:
            for r in live.iter_live("dm_clob_raw", h, min(h + 3600, h1)):
                yield r
        except (zlib.error, EOFError, OSError) as e:
            print("read error in hour", h, repr(e)[:80])


def main(h0, h1):
    OUT.mkdir(parents=True, exist_ok=True)
    fs = sorted(glob.glob(str(ROOT / ".cache/re/directional-maker/calldata/live1031*"))) + \
        glob.glob(str(ROOT / ".cache/re/directional-maker/calldata/liveall1031*"))
    d = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    d["maker"] = d["maker"].str.lower()
    clu = d[d.maker.isin(set(CL)) & (d.role == "maker") & (d.oside == 0)].copy()
    clu["orig"] = (clu.taker_amount / 1e6).round(2)
    clu["lim"] = (clu.maker_amount / clu.taker_amount).round(4)
    clu["tx"] = clu.tx.str.lower()
    cl_txs = set(d[d.maker.isin(set(CL))].tx.str.lower())
    u = clu[~clu.orig.isin(SCHED)].drop_duplicates(["maker", "salt"]).copy()
    targets = set(u.orig.round(2).tolist())
    print("cluster maker BUY orders", clu.drop_duplicates(["maker", "salt"]).shape[0], "tracer orders", len(u),
          "distinct sizes", len(targets))
    book: dict = {}
    tr, sc, xs = [], [], []
    n = 0
    for r in it(h0, h1):
        k = r.get("k")
        n += 1
        if k == "bk":
            w = r["w"]
            bw = {1: {}, 0: {}}
            for p, z in r.get("b", []):
                bw[1][round(p, 3)] = z
            for p, z in r.get("o", []):
                bw[0][round(p, 3)] = z
            book[w] = bw
        elif k == "pc":
            w = r["w"]
            s = r["s"]
            bw = book.get(w)
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
                if dz == 0:
                    continue
                bb, ba = row[3], row[4]
                adz = abs(dz)
                if adz in targets:
                    # ex-tracer touch on the order's own side of the Up book
                    if sd == 1:
                        lv = [q for q, zz in bw[1].items() if zz > 1e-9 and not (q == p and zz - max(dz, 0) <= 1e-6)]
                        ex = max(lv) if lv else np.nan
                    else:
                        lv = [q for q, zz in bw[0].items() if zz > 1e-9 and not (q == p and zz - max(dz, 0) <= 1e-6)]
                        ex = min(lv) if lv else np.nan
                    tr.append((w, s, sd, p, dz, bb, ba, ex, z))
                elif dz > 0 and dz in RUNG:
                    near = (sd == 1 and p >= bb - 0.20) or (sd == 0 and p <= ba + 0.20)
                    if near:
                        sc.append((w, s, sd, p, dz, bb, ba))
        elif k == "x":
            h = (r.get("h") or "").lower()
            xs.append((r["w"], r["s"], int(r.get("ai", -1)), float(r["p"]), float(r["z"]), str(r.get("d")), h, h in cl_txs))
    print("records", n, "tracer-size deltas", len(tr), "schedule adds", len(sc), "trades", len(xs))
    T = pd.DataFrame(tr, columns=["w", "s", "sd", "p", "dz", "bb", "ba", "ex", "lvl_after"])
    S = pd.DataFrame(sc, columns=["w", "s", "sd", "p", "dz", "bb", "ba"])
    X = pd.DataFrame(xs, columns=["w", "s", "ai", "p", "z", "d", "h", "cluster_tx"])
    S.to_parquet(OUT / "sched_adds.parquet", index=False)
    X.to_parquet(OUT / "trades.parquet", index=False)
    # tracer chains: fill server ms of the order's tx, exact-size adds on its side in the 120 s before the fill
    first_x = X.drop_duplicates("h").set_index("h")
    rows = []
    for o in u.itertuples():
        if o.tx not in first_x.index:
            continue
        fx = first_x.loc[o.tx]
        w, sf = fx.w, int(fx.s)
        g = T[(T.w == w) & (T.dz.abs().round(2) == o.orig) & (T.s >= sf - 120000) & (T.s <= sf + 50)]
        if g.empty:
            continue
        adds = g[g.dz > 0].sort_values("s")
        # own side from the book side: an Up BUY rests on the Up bid (sd 1), a Down BUY as an Up ask (sd 0)
        sd_mode = int(adds.sd.mode().iloc[0]) if len(adds) else -1
        for j, a in enumerate(adds.itertuples()):
            rows.append(dict(order=f"{o.maker}_{o.salt}", wallet=CL[o.maker], w=w, size=o.orig, lim=o.lim, token=str(o.token_id),
                             fill_ms=sf, s=int(a.s), sd=int(a.sd), sd_mode=sd_mode, p=a.p, bb=a.bb, ba=a.ba, ex=a.ex,
                             j=j, n_adds=len(adds)))
    R = pd.DataFrame(rows)
    R.to_parquet(OUT / "tracer_events.parquet", index=False)
    print("tracer orders with chains", R.order.nunique() if len(R) else 0, "re-sign events", len(R))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
