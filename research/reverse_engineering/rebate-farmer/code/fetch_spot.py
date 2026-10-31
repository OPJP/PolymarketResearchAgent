"""Binance 1-s kline closes per UTC day (development period only) -> .cache/re/rebate-farmer/spot/<asset>_<day>.parquet"""
import os, sys, time
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import pandas as pd
from polyrea.adapters.spot import binance_seconds
H = 1792713600
OUT = "/home/user/PolymarketResearchAgent/.cache/re/rebate-farmer/spot"
if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2]); assets = sys.argv[3].split(",")
    os.makedirs(OUT, exist_ok=True)
    for d0 in range(b, a - 1, -86400):
        for asset in assets:
            p = f"{OUT}/{asset}_{d0}.parquet"
            if os.path.exists(p) or d0 >= H:
                continue
            rows, _ = binance_seconds(asset, d0, min(d0 + 86400, H))
            df = pd.DataFrame(rows, columns=["sec", "px"]); df["sec"] = df.sec.astype("int64")
            assert len(df) == 0 or df.sec.max() < H
            df.to_parquet(p + ".tmp", index=False); os.replace(p + ".tmp", p)
            print(asset, time.strftime("%Y-%m-%d", time.gmtime(d0)), len(df), flush=True)
    print("DONE", flush=True)
