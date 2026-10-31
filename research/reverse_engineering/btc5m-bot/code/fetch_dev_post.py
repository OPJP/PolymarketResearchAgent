"""Iteration 5: on-chain V2 OrderFilled logs of the cluster (topic2 = order owner) for DEVELOPMENT blocks after T0 only
(tools/sealed.py intervals). Every window is kept only if it STARTS in a development interval (sealed units dropped,
whatever their fill timestamps). Writes .cache/re/btc5m-bot/post/own_<a>_<b>.parquet (decoded logs, block ts from the log).
Usage: python fetch_dev_post.py START_TS END_TS"""
import os, sys, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import rpc, sealed
from fetch_chain import decode, W

OUT = _ROOT + "/.cache/re/btc5m-bot/post"


def block_at(ts, lo=96005486, hi=None):
    """Smallest block with timestamp >= ts (binary search, cached calls)."""
    if hi is None:
        hi = int(rpc.call("eth_blockNumber", [], max_age=30), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if rpc.block_ts(mid) >= ts:
            hi = mid
        else:
            lo = mid + 1
    return lo


def fetch(a_ts, b_ts, chunk=1500):
    os.makedirs(OUT, exist_ok=True)
    ivs = sealed.intervals("btc5m-bot", a_ts, b_ts, sealed=False)
    out = []
    for (a, b) in ivs:
        a, b = int(a), int(b)
        ba = block_at(a); bb = block_at(b) - 1
        print("interval", a, b, "blocks", ba, bb, flush=True)
        pads = [rpc.pad(x) for x in W.values()]
        for s in range(ba, bb + 1, chunk):
            e = min(s + chunk - 1, bb)
            for attempt in range(6):
                try:
                    logs = rpc.call("eth_getLogs", [{"address": rpc.V2_EXCHANGES, "fromBlock": hex(s), "toBlock": hex(e), "topics": [rpc.TOPIC_V2, None, pads]}], max_age=None if e < bb - 50 else 60)
                    break
                except Exception as ex:
                    time.sleep(5 * (attempt + 1))
            else:
                print("FAILED", s, e, flush=True); continue
            out += [decode(l) for l in logs]
    df = pd.DataFrame(out)
    if len(df):
        assert df.ts.max() < b_ts + 600
    return df


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    df = fetch(a, b)
    df.to_parquet(f"{OUT}/own_{a}_{b}.parquet", index=False)
    print("DONE", len(df), flush=True)
