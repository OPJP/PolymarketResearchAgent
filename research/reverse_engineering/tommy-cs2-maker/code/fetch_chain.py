"""On-chain OrderFilled (V2 exchanges) where topic2 (order owner = maker field) is TommyLeePeeca.

Every fill of one of the wallet's orders emits OrderFilled with maker = wallet; resting orders
have taker = counterparty, its own aggressive orders have taker = exchange contract.
Grouping by orderHash reconstructs each resting order (limit price, filled size, life).

Development data only: the block range ends at the last block before H.
Output: .cache/re/tommy-cs2-maker/chain_fills_<start>_<end>.parquet
Usage: fetch_chain.py START_TS END_TS [STEP]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.chain import ORDER_FILLED_V2, decode_fills  # noqa: E402
from polyrea.adapters.http import HttpError, shared_client  # noqa: E402

H = 1792713600
RPC = "https://polygon-bor-rpc.publicnode.com"
EXCHANGES = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OUT = ROOT / ".cache/re/tommy-cs2-maker"
http = shared_client()


def rpc(method, params, cache=True):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for attempt in range(8):
        try:
            res, _ = http.post_json(RPC, body, adapter=f"polygon.rpc.{method}", max_age=None if cache else 0, max_retries=3)
        except HttpError as e:  # noqa: PERF203
            print("http error", method, str(e)[:160], flush=True)
            time.sleep(2 + attempt * 2)
            continue
        if isinstance(res, dict) and "result" in res and res["result"] is not None:
            return res["result"]
        print("bad result", method, str(res)[:160], flush=True)
        time.sleep(2 + attempt * 2)
    raise RuntimeError(f"rpc failed {method} {params}")


def block_ts(n: int) -> int:
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def block_at(ts: int, lo: int, hi: int) -> int:
    """Largest block with timestamp < ts (binary search)."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


def main(start_ts: int, end_ts: int, step: int = 4000) -> None:
    end_ts = min(end_ts, H)
    # anchor: block 96005486 is the first block with ts >= H (verified by a peer study); ~1.5 s blocks
    anchor = 96005486
    guess_s = anchor - int((H - start_ts) / 1.5) - 60_000
    guess_e = anchor - int((H - end_ts) / 1.5) + 60_000
    b0 = block_at(start_ts, max(guess_s, 1), guess_e) + 1
    b1 = block_at(end_ts, b0, min(guess_e, anchor))
    assert block_ts(b1) < H
    print("blocks", b0, b1, b1 - b0, flush=True)
    wtopic = "0x" + WALLET[2:].rjust(64, "0")
    rows = []
    t0 = time.time()
    for i, fb in enumerate(range(b0, b1 + 1, step)):
        tb = min(fb + step - 1, b1)
        params = [{"fromBlock": hex(fb), "toBlock": hex(tb), "address": EXCHANGES, "topics": [ORDER_FILLED_V2, None, wtopic]}]
        logs = rpc("eth_getLogs", params)
        for lg in logs:
            bts = int(lg["blockTimestamp"], 16) if lg.get("blockTimestamp") else None
            for f in decode_fills({"transactionHash": lg["transactionHash"], "logs": [lg]}):
                rows.append({
                    "block": int(lg["blockNumber"], 16), "bts": bts, "tx": f.tx_hash, "log_index": f.log_index,
                    "exchange": f.exchange, "order_hash": f.order_hash, "maker": f.maker, "taker": f.taker,
                    "side": f.side, "token_id": f.token_id, "shares": f.shares, "usdc": f.usdc, "fee": f.fee,
                })
        if i % 20 == 0:
            print(i, fb, len(rows), f"{time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df["role"] = (df["taker"].isin(EXCHANGES)).map({True: "taker", False: "maker"})
    df.to_parquet(OUT / f"chain_fills_{start_ts}_{end_ts}.parquet", index=False)
    print("done", len(df), df["role"].value_counts().to_dict(), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
