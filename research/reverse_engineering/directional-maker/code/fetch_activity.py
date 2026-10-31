"""Fetch the full data-api activity of the three cluster wallets, first trade .. H-1.

Development data only: end is clamped to H - 1 (holdout never loaded).
Output: .cache/re/directional-maker/activity_<name>.parquet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
WALLETS = {
    "bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed",
    "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
    "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3",
}
OUT = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker"


def main(start: int) -> None:
    pm = PolymarketData()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, w in WALLETS.items():
        t0 = time.time()
        rows, srcs, cov = pm.activity(w, start=start, end=H - 1)
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df[df["timestamp"] < H]
        keep = [c for c in ["timestamp", "type", "conditionId", "asset", "side", "outcome", "outcomeIndex", "price", "size", "usdcSize", "transactionHash", "slug", "eventSlug"] if c in df.columns]
        df = df[keep]
        df.to_parquet(OUT / (f"activity_{name}.parquet" if start > 0 else f"activity_full_{name}.parquet"), index=False)
        print(name, len(df), cov.status, cov.detail, "first", df["timestamp"].min() if len(df) else None, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
