"""Fetch on-chain OrderFilled (V2) events of the wallet's own orders (topic2 = wallet), development period only.

Every fill of an order the wallet signed appears with maker topic = wallet: resting orders (role maker,
taker topic = counterparty) and its aggressive orders (taker topic = the exchange contract).
Adapted from research/reverse_engineering/btc5m-bot/code/fetch_chain.py (read-only reuse).
Writes one parquet per block chunk to .cache/re/rebate-farmer/chain/own/.
Usage: python fetch_chain.py FROM_BLOCK TO_BLOCK [chunk] [threads]
"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import pandas as pd
from polyrea.adapters.http import shared_client, HttpError

H = 1792713600
BH = 96005486  # first block with ts >= H (verified by btc5m-bot agent; re-asserted on every row below)
W = "0xb55fa1296e6ec55d0ce53d93b9237389f11764d4"
RPC = "https://polygon.drpc.org"
RPC2 = "https://polygon-bor-rpc.publicnode.com"
V2 = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
TOPIC_V2 = "0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee"
OUT = "/home/user/PolymarketResearchAgent/.cache/re/rebate-farmer/chain/own"
_http = shared_client()


def call(method, params):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last = None
    for url in (RPC, RPC2):
        for _ in range(3):
            try:
                res, _ = _http.post_json(url, body, adapter="polygon.rpc." + method, max_age=None, max_retries=3)
            except HttpError as e:
                last = e
                time.sleep(2)
                continue
            if isinstance(res, dict) and res.get("result") is not None:
                return res["result"]
            last = res
            time.sleep(2)
    raise RuntimeError(f"rpc failed {method}: {str(last)[:300]}")


def pad(a):
    return "0x" + a.lower().replace("0x", "").rjust(64, "0")


def decode(log):
    t = log["topics"]
    d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, min(len(d), 64 * 6), 64)]
    return {"block": int(log["blockNumber"], 16), "ts": int(log["blockTimestamp"], 16), "tx": log["transactionHash"],
            "li": int(log["logIndex"], 16), "ex": log["address"][-4:], "oh": t[1], "cp": "0x" + t[3][-40:],
            "side": w[0], "token": str(w[1]), "mamt": float(w[2]), "tamt": float(w[3]), "fee": float(w[4])}


def job(a, b):
    path = f"{OUT}/{a}_{b}.parquet"
    if os.path.exists(path):
        return 0
    rows = []
    for ex in V2:
        logs = call("eth_getLogs", [{"address": ex, "fromBlock": hex(a), "toBlock": hex(b), "topics": [TOPIC_V2, None, pad(W)]}])
        rows += [decode(l) for l in logs]
    df = pd.DataFrame(rows)
    if len(df):
        assert df.ts.max() < H, "holdout leak"
    df.to_parquet(path + ".tmp", index=False)
    os.replace(path + ".tmp", path)
    return len(df)


if __name__ == "__main__":
    a0, b0 = int(sys.argv[1]), int(sys.argv[2])
    chunk = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    assert b0 < BH
    os.makedirs(OUT, exist_ok=True)
    ranges = [(s, min(s + chunk - 1, b0)) for s in range(a0, b0 + 1, chunk)][::-1]
    t0 = time.time(); n = 0; done = 0
    with ThreadPoolExecutor(threads) as ex:
        for k in ex.map(lambda r: job(*r), ranges):
            n += k; done += 1
            if done % 25 == 0:
                print(f"{done}/{len(ranges)} chunks, {n} logs, {time.time()-t0:.0f}s", flush=True)
    print("DONE", n, time.time() - t0, flush=True)
