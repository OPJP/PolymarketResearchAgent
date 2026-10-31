"""Fetch on-chain OrderFilled (V2) events for the three cluster wallets, development period only.

mode 'own'  : topic2 (order owner) in cluster -> every fill of the wallets' own orders (maker and taker role)
mode 'hit'  : topic3 (counterparty) in cluster -> the resting orders the wallets' taker orders hit
Writes one parquet per block chunk to .cache/re/btc5m-bot/chain/<mode>/.
Usage: python fetch_chain.py MODE FROM_BLOCK TO_BLOCK [chunk] [threads]
TO_BLOCK must be < block at H (96005486, first block with ts >= 1792713600).
"""
import os as _os; _ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))  # repo root
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc

H = 1792713600
BH = 96005486
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
OUT = _ROOT + "/.cache/re/btc5m-bot/chain"


def decode(log):
    t = log["topics"]
    d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, min(len(d), 64 * 6), 64)]
    return {
        "block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16), "tx": log["transactionHash"],
        "li": int(log["logIndex"], 16), "ex": log["address"][-4:], "oh": t[1], "owner": "0x" + t[2][-40:], "cp": "0x" + t[3][-40:],
        "side": w[0], "token": str(w[1]), "mamt": float(w[2]), "tamt": float(w[3]), "fee": float(w[4]), "w5": str(w[5]) if len(w) > 5 else "",
    }


def job(mode, a, b):
    path = f"{OUT}/{mode}/{a}_{b}.parquet"
    if os.path.exists(path):
        return 0
    pads = [rpc.pad(x) for x in W.values()]
    topics = [rpc.TOPIC_V2, None, pads] if mode == "own" else [rpc.TOPIC_V2, None, None, pads]
    rows = []
    for ex in rpc.V2_EXCHANGES:
        logs = rpc.get_logs(ex, a, b, topics)
        rows += [decode(l) for l in logs]
    df = pd.DataFrame(rows)
    if len(df):
        assert df.ts.max() < H, "holdout leak"
    df.to_parquet(path + ".tmp", index=False)
    os.replace(path + ".tmp", path)
    return len(df)


if __name__ == "__main__":
    mode, a0, b0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    chunk = int(sys.argv[4]) if len(sys.argv) > 4 else 3000
    threads = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    assert b0 < BH
    os.makedirs(f"{OUT}/{mode}", exist_ok=True)
    ranges = [(s, min(s + chunk - 1, b0)) for s in range(a0, b0 + 1, chunk)]
    ranges = ranges[::-1]  # newest first
    t0 = time.time(); n = 0; done = 0
    with ThreadPoolExecutor(threads) as ex:
        for k in ex.map(lambda r: job(mode, *r), ranges):
            n += k; done += 1
            if done % 25 == 0:
                print(f"{done}/{len(ranges)} chunks, {n} logs, {time.time()-t0:.0f}s", flush=True)
    print("DONE", mode, n, time.time() - t0, flush=True)
