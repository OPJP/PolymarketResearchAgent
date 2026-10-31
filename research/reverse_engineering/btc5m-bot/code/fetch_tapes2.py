"""Iteration 2: taker tapes (data-api /trades takerOnly=true) for BTC 5m windows in [A, B), B <= H, fetched in a
seeded random order (any prefix is a random sample). Range per window: [start-600, end+5] (capped below H).
Usage: python fetch_tapes2.py A B [seed] [threads]"""
import os, sys, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
H = 1792713600
C = _ROOT + "/.cache/re/btc5m-bot"
PRE, POST = 600, 5
KEEP = ["proxyWallet", "side", "asset", "size", "price", "timestamp", "outcome", "transactionHash"]


def fetch_one(pm, cid, start_ts, end_ts, cap_end, out_dir):
    path = f"{out_dir}/{cid}.parquet"
    if os.path.exists(path):
        return -1
    rows, _, cov = pm.market_trades(cid, start=int(start_ts) - PRE, end=min(int(end_ts) + POST, int(cap_end) - 1), taker_only=True)
    df = pd.DataFrame(rows)
    if len(df):
        assert df.timestamp.max() < cap_end
        df = df[[c for c in KEEP if c in df.columns]]
    df["coverage"] = cov.status
    df.to_parquet(path + ".tmp", index=False); os.replace(path + ".tmp", path)
    return len(df)


if __name__ == "__main__":
    A, B = int(sys.argv[1]), int(sys.argv[2])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    assert B <= H
    os.makedirs(f"{C}/tapes", exist_ok=True)
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= A) & (win.end_ts <= B)].reset_index(drop=True)
    win = win.iloc[np.random.default_rng(seed).permutation(len(win))]
    pm = PolymarketData()
    t0 = time.time(); n = 0
    with ThreadPoolExecutor(threads) as ex:
        for i, k in enumerate(ex.map(lambda r: fetch_one(pm, r.cid, r.start_ts, r.end_ts, H, f"{C}/tapes"), list(win.itertuples()))):
            n += max(k, 0)
            if i % 100 == 0:
                print(i, len(win), n, round(time.time() - t0), flush=True)
    print("DONE", n, time.time() - t0, flush=True)
