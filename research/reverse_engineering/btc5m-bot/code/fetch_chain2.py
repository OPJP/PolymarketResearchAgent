"""Iteration 2: fetch on-chain V2 OrderFilled logs (topic2 = cluster order owner) for blocks [A, B], B < block at H.
Both V2 exchanges are passed as one address list (one RPC call per chunk). Writes one parquet per chunk to
.cache/re/btc5m-bot/chain/own/. Holdout guard: asserts every log has ts < H.
Usage: python fetch_chain2.py FROM_BLOCK TO_BLOCK [chunk] [threads]"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc
from fetch_chain import decode, W, OUT, H, BH


def job(a, b):
    path = f"{OUT}/own/{a}_{b}.parquet"
    if os.path.exists(path):
        return 0
    pads = [rpc.pad(x) for x in W.values()]
    for attempt in range(6):
        try:
            logs = rpc.call("eth_getLogs", [{"address": rpc.V2_EXCHANGES, "fromBlock": hex(a), "toBlock": hex(b), "topics": [rpc.TOPIC_V2, None, pads]}])
            break
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    else:
        print("FAILED", a, b, flush=True)
        return 0
    df = pd.DataFrame([decode(l) for l in logs])
    if len(df):
        assert df.ts.max() < H, "holdout leak"
    df.to_parquet(path + ".tmp", index=False)
    os.replace(path + ".tmp", path)
    return len(df)


if __name__ == "__main__":
    a0, b0 = int(sys.argv[1]), int(sys.argv[2])
    chunk = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    assert b0 < BH
    os.makedirs(f"{OUT}/own", exist_ok=True)
    ranges = [(s, min(s + chunk - 1, b0)) for s in range(a0, b0 + 1, chunk)][::-1]  # newest first
    t0 = time.time(); n = 0; done = 0
    with ThreadPoolExecutor(threads) as ex:
        for k in ex.map(lambda r: job(*r), ranges):
            n += k; done += 1
            if done % 20 == 0:
                print(f"{done}/{len(ranges)} chunks, {n} logs, {time.time()-t0:.0f}s", flush=True)
    print("DONE", n, time.time() - t0, flush=True)
