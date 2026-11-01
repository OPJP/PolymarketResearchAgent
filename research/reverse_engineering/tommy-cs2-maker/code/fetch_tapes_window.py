"""Taker-only public tapes of every CS2 match / map-winner market, restricted to the presence window.

Window per market: [gameStartTime - 1 h, min(gameStartTime + 4 h + 10 min, H - 1)]; nothing at or after H
is ever requested. Markets with gameStartTime in [d0, d1). Order: VALIDATE days first if asked.
One parquet per market in .cache/re/tommy-cs2-maker/tapes/<cid>_tkw.parquet.
Usage: fetch_tapes_window.py D0 D1 [kind]   kind = tk (taker-only, default) | full
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/tommy-cs2-maker"
TAPES = OUT / "tapes"
COLS = ["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash"]


def main(d0: int, d1: int, kind: str = "tk") -> None:
    TAPES.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u["smt"].isin(["moneyline", "child_moneyline"]) & (u["gs_ts"] >= d0) & (u["gs_ts"] < min(d1, H))]
    u = u.sort_values("gs_ts", ascending=False)  # latest first (VALIDATE before BUILD)
    t0 = time.time()
    print("markets", len(u), flush=True)
    for i, (cid, gs) in enumerate(zip(u["cid"], u["gs_ts"].astype("int64"))):
        path = TAPES / f"{cid}_{kind}w.parquet"
        if path.exists():
            continue
        start, end = int(gs) - 3600, min(int(gs) + 4 * 3600 + 600, H - 1)
        try:
            rows, _, cov = pm.market_trades(cid, start=start, end=end, taker_only=(kind == "tk"), max_rows=200_000)
        except Exception as e:  # noqa: BLE001
            print("ERR", cid, str(e)[:120], flush=True)
            continue
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=COLS)
        df = df[[c for c in COLS if c in df.columns]]
        if len(df):
            df = df[(df["timestamp"] >= start) & (df["timestamp"] < H)]
        df.to_parquet(path, index=False)
        if i % 25 == 0:
            print(i, len(df), cov.status, f"{time.time()-t0:.0f}s", flush=True)
    print("done", f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]), int(a[1]), *(a[2:3]))
