"""Iteration 8, X111 step 3 (mechanics panel iter7 P5, geography): each subscriber's CLOB path latency = server
match time of its FAK (live last-trade record with its transaction hash, server clock) - its signing time - the 1-s
in-play delay, on BUILD-live (10-31 14:50-18:00, tommy_cs2_near). Only the wallet and 0xf1ee4842 (and 0x51dbdd2b)
have taker orders on the recorded books. If 0xf1ee4842's ~+100-150 ms feed lag behind the wallet were network distance
to the CLOB, its path latency would be larger by about that much. Output: results/clob_latency.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
A, B = int(os.environ.get("TOMMY_BLOCK_START", 1793458232)), int(os.environ.get("TOMMY_BLOCK_END", 1793469600))
SUF = os.environ.get("TOMMY_BLOCK_SUFFIX", "")
WHO = {"0x0063b23c": "wallet", "0xf1ee4842": "0xf1ee4842", "0x51dbdd2b": "0x51dbdd2b", "0x4ebc2722": "P4e", "0x2005d16a": "0x2005d16a", "0x93078b5d": "P93", "0x8a80528d": "0x8a80528d", "0xddb6e624": "0xddb6e624"}


def main():
    cd = pd.read_parquet(OUT / f"calldata_dev{SUF}.parquet")
    cd["maker"] = cd.maker.str.lower()
    tk = cd[cd.idx == -1].copy()
    tk["who"] = tk.maker.str[:10].map(WHO)
    tk = tk[tk.who.notna()]
    want = set(tk.tx)
    first = {}
    h = A // 3600 * 3600
    while h < B:
        try:
            for r in live.iter_live("tommy_cs2_near", max(h, A), min(h + 3600, B)):
                if r.get("k") == "x" and r.get("h") in want and "s" in r:
                    first[r["h"]] = min(first.get(r["h"], 1e18), float(r["s"]))
        except Exception as e:  # noqa: BLE001
            print("feed", h, type(e).__name__)
        h += 3600
    tk["match_s"] = tk.tx.map(first)
    tk = tk[tk.match_s.notna()]
    tk["path_ms"] = tk.match_s - tk.sign_ms - 1000
    res = {}
    for w, g in tk.groupby("who"):
        v = g.path_ms.to_numpy(float)
        res[w] = {"n": int(len(v)), "p10_ms": round(float(np.percentile(v, 10)), 1), "p50_ms": round(float(np.median(v)), 1),
                  "p90_ms": round(float(np.percentile(v, 90)), 1), "min_ms": round(float(v.min()), 1)}
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES / f"clob_latency{SUF}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
