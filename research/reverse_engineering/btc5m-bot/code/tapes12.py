"""Iteration 12: rebuild the data-api taker tapes of the BUILD / VALIDATE windows (all < H) from the shared HTTP cache
into a scratch directory (not the workspace cache). Same range and columns as fetch_tapes2 ([start-600, end+5]).
Usage: python tapes12.py A B OUT_DIR [threads]"""
import os, sys, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from fetch_tapes2 import fetch_one
H = 1792713600
C = _ROOT + "/.cache/re/btc5m-bot"
if __name__ == "__main__":
    A, B, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    th = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    assert B <= H
    os.makedirs(OUT, exist_ok=True)
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= A) & (win.end_ts <= B)].reset_index(drop=True)
    pm = PolymarketData(); t0 = time.time(); n = 0
    with ThreadPoolExecutor(th) as ex:
        for i, k in enumerate(ex.map(lambda r: fetch_one(pm, r.cid, r.start_ts, r.end_ts, H, OUT), list(win.itertuples()))):
            n += max(k, 0)
            if i % 250 == 0:
                print(i, len(win), n, round(time.time() - t0), flush=True)
    print("DONE", len(win), n, round(time.time() - t0), flush=True)
