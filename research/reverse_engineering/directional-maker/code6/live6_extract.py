"""Iteration 6: one pass over the own raw recording (dm_clob_raw, development blocks only via rawread.iter_dm) ->
compact parquet for the confirmed-order studies (panel iter5 assumptions Q1/Q2/Q3, mechanics M4).

Kept (per BTC market w, Up-token book; a BUY Down at p is an ask at 1 - p):
* adds/removals whose size delta is one of SIZES (schedule sizes, 500/100, and every filled cluster order's original
  size in the period) anywhere in the book, and every add at the touch on its own side (any size);
  columns s (server ms), w, side (1 bid / 0 ask), p, d (delta), z (size after), prev (size before), bb, ba
* touch series: (s, w, bb, ba) whenever the touch changes
* trades x: (s, w, ai, p, z, d, h)
    python code6/live6_extract.py <start_ts> <end_ts>
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
from rawread import iter_dm  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
OUT = C / "it6"
OUT.mkdir(exist_ok=True)
CL = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
      "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def main(a, b):
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet"))])
    cd = cd[cd.maker.str.lower().isin(CL) & (cd.role == "maker")]
    S = np.where(cd.oside == 0, cd.taker_amount, cd.maker_amount) / 1e6
    sizes = set(np.round(S, 2)) | {5.0, 12.0, 50.0, 62.0, 100.0, 125.0, 250.0, 500.0, 1000.0}
    lv, ev, tch, tr = {}, [], [], []
    last_touch = {}
    nrec = 0
    for r in iter_dm("dm_clob_raw", a, b):
        nrec += 1
        k, w = r["k"], r.get("w")
        if k == "bk":
            L = {(1, p): z for p, z in r["b"]}
            L.update({(0, p): z for p, z in r["o"]})
            lv[w] = L
        elif k == "pc":
            L = lv.setdefault(w, {})
            for side, p, z, bb, ba, nc in r["c"]:
                if side > 1:
                    continue
                prev = L.get((side, p), 0.0)
                d = round(z - prev, 2)
                L[(side, p)] = z
                at = (side == 1 and abs(p - bb) < 1e-9) or (side == 0 and abs(p - ba) < 1e-9)
                if abs(d) in sizes or (at and d > 0):
                    ev.append((r["s"], w, side, p, d, z, prev, bb, ba))
                if last_touch.get(w) != (bb, ba):
                    last_touch[w] = (bb, ba)
                    tch.append((r["s"], w, bb, ba))
        elif k == "x":
            tr.append((r["s"], w, r["ai"], r["p"], r["z"], r["d"], (r.get("h") or "").lower()))
    ev = pd.DataFrame(ev, columns=["s", "w", "side", "p", "d", "z", "prev", "bb", "ba"])
    for c in ("p", "d", "z", "prev", "bb", "ba"):
        ev[c] = ev[c].astype("float32")
    ev.to_parquet(OUT / f"ev_{a}_{b}.parquet")
    pd.DataFrame(tch, columns=["s", "w", "bb", "ba"]).to_parquet(OUT / f"touch_{a}_{b}.parquet")
    pd.DataFrame(tr, columns=["s", "w", "ai", "p", "z", "d", "h"]).to_parquet(OUT / f"x_{a}_{b}.parquet")
    print("records", nrec, "events", len(ev), "touch", len(tch), "trades", len(tr), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
