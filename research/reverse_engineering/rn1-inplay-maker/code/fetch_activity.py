"""RN1 data-api activity, one UTC day per call (cached, resumable).

Development data only: every request ends before H.
Output: .cache/re/rn1-inplay-maker/activity/act_<day>.parquet
Usage: python fetch_activity.py <start_day_ts> <end_day_ts>
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
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
OUT = ROOT / ".cache/re/rn1-inplay-maker/activity"
OUT.mkdir(parents=True, exist_ok=True)
KEEP = ["type", "timestamp", "conditionId", "asset", "side", "price", "size", "usdcSize", "transactionHash",
        "outcomeIndex", "outcome", "slug", "eventSlug", "title"]


def main(d0: int, d1: int) -> None:
    pm = PolymarketData()
    for day in range(d0, min(d1, H), 86400):
        f = OUT / f"act_{day}.parquet"
        if f.exists():
            continue
        t0 = time.time()
        end = min(day + 86400 - 1, H - 1)
        rows, _, cov = pm.activity(W, start=day, end=end)
        df = pd.DataFrame(rows)
        for k in KEEP:
            if k not in df.columns:
                df[k] = None
        df = df[KEEP]
        df = df[(df["timestamp"] >= day) & (df["timestamp"] < min(day + 86400, H))]
        df.to_parquet(f, index=False)
        print(day, len(df), cov.status, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
