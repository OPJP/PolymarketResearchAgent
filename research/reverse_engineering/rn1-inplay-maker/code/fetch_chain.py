"""On-chain OrderFilled logs (V2 exchanges) where topic2 (order owner) = RN1, one UTC day per file.

Every fill of one of RN1's orders emits an OrderFilled with maker topic = RN1: resting
orders have taker topic = counterparty; RN1's own aggressive orders have taker = exchange.
Grouping by orderHash reconstructs each resting order (limit price, filled size, fill span).

Development data only: block ranges end at the last block before H.
Output: .cache/re/rn1-inplay-maker/chain/chain_<day>.parquet (block timestamps exact per block via cache)
Usage: python fetch_chain.py <start_day_ts> <end_day_ts> [step]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.chain import ORDER_FILLED_V2, decode_fills  # noqa: E402
from polyrea.adapters.http import HttpError, shared_client  # noqa: E402

H = 1792713600
RPC = "https://polygon-bor-rpc.publicnode.com"
EXCHANGES = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
OUT = ROOT / ".cache/re/rn1-inplay-maker/chain"
OUT.mkdir(parents=True, exist_ok=True)
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
    """Largest block with timestamp < ts."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


def main(d0: int, d1: int, step: int = 2000) -> None:
    latest = int(rpc("eth_blockNumber", [], cache=False), 16)
    lt = block_ts(latest)
    wtopic = "0x" + W[2:].rjust(64, "0")
    for day in range(d0, min(d1, H), 86400):
        f = OUT / f"chain_{day}.parquet"
        if f.exists():
            continue
        t0 = time.time()
        end_ts = min(day + 86400, H)
        gs = latest - int((lt - day) / 1.5) - 150_000
        ge = latest - int((lt - end_ts) / 1.5) + 150_000
        b0 = block_at(day, max(gs, 1), min(ge, latest)) + 1
        b1 = block_at(end_ts, b0, min(ge, latest))
        rows = []
        for fb in range(b0, b1 + 1, step):
            tb = min(fb + step - 1, b1)
            params = [{"fromBlock": hex(fb), "toBlock": hex(tb), "address": EXCHANGES, "topics": [ORDER_FILLED_V2, None, wtopic]}]
            for lg in rpc("eth_getLogs", params):
                for fl in decode_fills({"transactionHash": lg["transactionHash"], "logs": [lg]}):
                    rows.append({"block": int(lg["blockNumber"], 16), "tx": fl.tx_hash, "log_index": fl.log_index,
                                 "exchange": fl.exchange, "order_hash": fl.order_hash, "maker": fl.maker, "taker": fl.taker,
                                 "side": fl.side, "token_id": fl.token_id, "shares": fl.shares, "usdc": fl.usdc, "fee": fl.fee})
        df = pd.DataFrame(rows)
        anchors = sorted(set(list(range(b0, b1 + 1, 400)) + [b1]))
        ats = [block_ts(b) for b in anchors]
        if len(df):
            df["role"] = np.where(df["taker"].isin(EXCHANGES), "taker", "maker")
            df["ts"] = np.round(np.interp(df["block"].to_numpy(), anchors, ats)).astype(int)
        df.to_parquet(f, index=False)
        print(day, b0, b1, len(df), (df["role"].value_counts().to_dict() if len(df) else {}), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 2000)
