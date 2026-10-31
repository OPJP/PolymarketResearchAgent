"""Populate the HTTP cache with BTC 5m taker tapes for windows in [lo, hi) (rows discarded; lean memory)."""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/directional-maker"

if __name__ == "__main__":
    lo, hi, rev = int(sys.argv[1]), min(int(sys.argv[2]), H), "rev" in sys.argv[3:]
    full = "full" in sys.argv[3:]  # full tape (maker rows too) instead of taker-only
    pm = PolymarketData()
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["start_ts"] >= lo) & (w["end_ts"] <= hi)].sort_values("start_ts", ascending=not rev)
    t0 = time.time()

    def go(r):
        rows, _, _ = pm.market_trades(r[0], start=int(r[1]) - 900, end=min(int(r[2]), H - 1), taker_only=not full)
        return len(rows)

    with ThreadPoolExecutor(6) as ex:
        for i, n in enumerate(ex.map(go, list(zip(w["cid"], w["start_ts"], w["end_ts"])))):
            if i % 250 == 0:
                print(i, f"{time.time()-t0:.0f}s", flush=True)
    print("done", len(w), f"{time.time()-t0:.0f}s", flush=True)
