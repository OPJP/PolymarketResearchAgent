"""Taker tapes (data-api /trades takerOnly=true) for BTC 5m windows in [A, B), B <= H. Same call signature as
polyrea load_period (start-3600, end+120) so earlier cached tapes are reused; end is capped below H."""
import os, sys, time, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData
H = 1792713600
C = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
A, B = int(sys.argv[1]), int(sys.argv[2])
order = sys.argv[3] if len(sys.argv) > 3 else "desc"
assert B <= H
os.makedirs(f"{C}/tapes", exist_ok=True)
win = pd.read_parquet(f"{C}/windows.parquet")
win = win[(win.start_ts >= A) & (win.end_ts <= B)].sort_values("start_ts", ascending=(order != "desc"))
pm = PolymarketData()
def job(r):
    path = f"{C}/tapes/{r.cid}.parquet"
    if os.path.exists(path):
        return 0
    rows, _, cov = pm.market_trades(r.cid, start=int(r.start_ts) - 3600, end=min(int(r.end_ts) + 120, H - 1), taker_only=True)
    df = pd.DataFrame(rows)
    if len(df):
        assert df.timestamp.max() < H
        keep = [c for c in ["proxyWallet", "side", "asset", "conditionId", "size", "price", "timestamp", "outcome", "outcomeIndex", "transactionHash"] if c in df.columns]
        df = df[keep]
    df["coverage"] = cov.status
    df.to_parquet(path + ".tmp", index=False); os.replace(path + ".tmp", path)
    return len(df)
t0 = time.time(); n = 0
with ThreadPoolExecutor(3) as ex:
    for i, k in enumerate(ex.map(job, [r for r in win.itertuples()])):
        n += k
        if i % 100 == 0:
            print(i, len(win), n, round(time.time() - t0), flush=True)
print("DONE", n, time.time() - t0, flush=True)
