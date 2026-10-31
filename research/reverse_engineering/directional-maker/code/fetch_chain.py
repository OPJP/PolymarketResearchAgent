"""On-chain OrderFilled logs where the maker topic is one of the three cluster wallets.

Every fill of a wallet's order emits an OrderFilled whose topic2 (maker) is the
wallet: resting (maker) orders have taker = counterparty, the wallet's own
aggressive orders have taker = exchange contract. Grouping by orderHash
reconstructs each resting order (limit price, filled size, life).

Development data only: the block range ends at the last block before H.
Output: .cache/re/directional-maker/chain_fills_<start>_<end>.parquet
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
WALLETS = {
    "bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed",
    "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
    "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3",
}
OUT = ROOT / ".cache/re/directional-maker"
http = shared_client()


def rpc(method, params, cache=True):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for attempt in range(6):
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
    b = rpc("eth_getBlockByNumber", [hex(n), False])
    return int(b["timestamp"], 16)


def block_at(ts: int, lo: int, hi: int) -> int:
    """Largest block with timestamp < ts (binary search)."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


def main(start_ts: int, end_ts: int, step: int = 1000) -> None:
    end_ts = min(end_ts, H)
    latest = int(rpc("eth_blockNumber", [], cache=False), 16)
    lt = block_ts(latest)
    # coarse anchors at ~2 s per block, then refine
    guess_s = latest - int((lt - start_ts) / 1.5) - 200_000
    guess_e = latest - int((lt - end_ts) / 1.5) + 200_000
    b0 = block_at(start_ts, max(guess_s, 1), min(guess_e, latest)) + 1
    b1 = block_at(end_ts, b0, min(guess_e, latest))
    print("blocks", b0, b1, b1 - b0, flush=True)
    wtopics = ["0x" + w[2:].rjust(64, "0") for w in WALLETS.values()]
    rows = []
    t0 = time.time()
    for i, fb in enumerate(range(b0, b1 + 1, step)):
        tb = min(fb + step - 1, b1)
        params = [{"fromBlock": hex(fb), "toBlock": hex(tb), "address": EXCHANGES, "topics": [ORDER_FILLED_V2, None, wtopics]}]
        logs = rpc("eth_getLogs", params)
        for lg in logs:
            for f in decode_fills({"transactionHash": lg["transactionHash"], "logs": [lg]}):
                rows.append({
                    "block": int(lg["blockNumber"], 16), "tx": f.tx_hash, "log_index": f.log_index,
                    "exchange": f.exchange, "order_hash": f.order_hash, "maker": f.maker, "taker": f.taker,
                    "side": f.side, "token_id": f.token_id, "shares": f.shares, "usdc": f.usdc, "fee": f.fee,
                })
        if i % 10 == 0:
            print(i, fb, len(rows), f"{time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df["role"] = (df["taker"].isin(EXCHANGES)).map({True: "taker", False: "maker"})
    # block timestamps: exact for a sparse anchor grid, linear in between
    anchors = sorted(set(list(range(b0, b1 + 1, 2000)) + [b1]))
    ats = [block_ts(b) for b in anchors]
    import numpy as np
    df["block_ts_interp"] = np.interp(df["block"].to_numpy(), anchors, ats)
    df.to_parquet(OUT / f"chain_fills_{start_ts}_{end_ts}.parquet", index=False)
    print("done", len(df), df["role"].value_counts().to_dict(), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
