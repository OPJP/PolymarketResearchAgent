"""Fetch the wallet's data-api activity one UTC day at a time, development period only (< H).

Writes .cache/re/rebate-farmer/activity/<day_ts>.parquet. Every request goes through the
polyrea cached client. Usage: python fetch_activity.py FIRST_DAY_TS LAST_DAY_TS (newest first).
"""
import os, sys, time
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData

W = "0xb55fa1296e6ec55d0ce53d93b9237389f11764d4"
H = 1792713600
OUT = "/home/user/PolymarketResearchAgent/.cache/re/rebate-farmer/activity"
KEEP = ["timestamp", "conditionId", "type", "side", "outcome", "outcomeIndex", "price", "size", "usdcSize",
        "transactionHash", "asset", "slug", "eventSlug"]


def fetch_day(pm, d0):
    path = f"{OUT}/{d0}.parquet"
    if os.path.exists(path):
        return -1
    end = min(d0 + 86400, H) - 1
    assert end < H
    rows, _, cov = pm.activity(W, start=d0, end=end)
    df = pd.DataFrame(rows)
    if len(df):
        df = df[[c for c in KEEP if c in df.columns]]
        df = df[(df.timestamp >= d0) & (df.timestamp < H)]
    df.to_parquet(path + ".tmp", index=False)
    os.replace(path + ".tmp", path)
    return len(df), cov.status


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    pm = PolymarketData()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    for d0 in range(b, a - 1, -86400):
        if d0 >= H:
            continue
        r = fetch_day(pm, d0)
        print(time.strftime("%Y-%m-%d", time.gmtime(d0)), r, f"{time.time()-t0:.0f}s", flush=True)
    print("DONE", flush=True)
