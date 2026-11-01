"""B1: V2 matchOrders calldata decoder for a sample of RN1's trade transactions (development data only).

matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders, uint256 takerFillAmount,
            uint256[] makerFillAmounts, uint256 takerFeeAmount, uint256[] makerFeeAmounts)
Order(uint256 salt, address maker, address signer, uint256 tokenId, uint256 makerAmount, uint256 takerAmount,
      uint8 side, uint8 signatureType, uint256 timestamp, bytes32 metadata, bytes32 builder, bytes signature)

Every order of the transaction is kept (taker order + all maker orders), so the counterparty context is known:
role (taker/maker), maker address, side, limit price, original size, signing time (ms), fill amount, fee.
Only decoded fields are stored (no raw input), in .cache/re/rn1-inplay-maker/calldata/cd_<day>.parquet.
Raw responses bypass the shared HTTP cache (httpx direct, ~1.5 req/s, batched 20 tx per request).

Usage: python fetch_calldata.py <day_ts> [n_per_day] [seed]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
H = 1792713600
W = "0x2005d16a84ceefa912d4e380cd32e7ff827875ea"
C = ROOT / ".cache/re/rn1-inplay-maker"
OUT = C / "calldata"
OUT.mkdir(parents=True, exist_ok=True)
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
SEL = "0x3c2b4399"


def _addr(x: int) -> str:
    return "0x" + format(x, "040x")[-40:]


def decode_match(inp: str) -> dict | None:
    if not inp.startswith(SEL):
        return None
    b = inp[10:]
    n = len(b) // 64
    w = [int(b[64 * i:64 * (i + 1)], 16) for i in range(n)]
    hexw = [b[64 * i:64 * (i + 1)] for i in range(n)]

    def order(s: int) -> dict:
        return {"salt": w[s], "maker": _addr(w[s + 1]), "signer": _addr(w[s + 2]), "token_id": str(w[s + 3]),
                "maker_amount": w[s + 4], "taker_amount": w[s + 5], "side": w[s + 6], "sig_type": w[s + 7],
                "sign_ms": w[s + 8], "metadata": hexw[s + 9], "builder": hexw[s + 10]}

    cond = hexw[0]
    t = order(w[1] // 32)
    a = w[2] // 32
    k = w[a]
    makers = [order(a + 1 + w[a + 1 + i] // 32) for i in range(k)]
    fa = w[4] // 32
    fills = [w[fa + 1 + i] for i in range(w[fa])]
    fe = w[6] // 32
    fees = [w[fe + 1 + i] for i in range(w[fe])]
    t["fill"] = w[3]
    t["fee"] = w[5]
    t["role"] = "taker"
    t["pos"] = -1
    for i, m in enumerate(makers):
        m["fill"] = fills[i] if i < len(fills) else None
        m["fee"] = fees[i] if i < len(fees) else None
        m["role"] = "maker"
        m["pos"] = i
    return {"cond": "0x" + cond, "orders": [t] + makers}


def fetch_batch(cli: httpx.Client, txs: list[str]) -> list[dict]:
    body = [{"jsonrpc": "2.0", "id": i, "method": "eth_getTransactionByHash", "params": [tx]} for i, tx in enumerate(txs)]
    for attempt in range(6):
        url = RPCS[attempt % len(RPCS)]
        try:
            r = cli.post(url, json=body, timeout=60)
            if r.status_code == 429:
                time.sleep(3 + 3 * attempt)
                continue
            r.raise_for_status()
            js = r.json()
            if isinstance(js, list):
                return js
        except Exception as e:  # noqa: BLE001
            print("err", url, str(e)[:120], flush=True)
            time.sleep(2 + 2 * attempt)
    return []


def main(day: int, n_per_day: int = 400, seed: int = 0) -> None:
    f = OUT / f"cd_{day}.parquet"
    if f.exists():
        print("exists", f)
        return
    act = pd.read_parquet(C / "activity" / f"act_{day}.parquet")
    act = act[(act["type"] == "TRADE") & (act["timestamp"] < H)]
    txs = act["transactionHash"].dropna().unique()
    rng = np.random.default_rng(seed + day)
    sample = list(rng.choice(txs, size=min(n_per_day, len(txs)), replace=False))
    rows = []
    cli = httpx.Client(headers={"content-type": "application/json"})
    t0 = time.time()
    for i in range(0, len(sample), 20):
        chunk = sample[i:i + 20]
        res = fetch_batch(cli, chunk)
        for r in res:
            tx = r.get("result")
            if not tx:
                continue
            d = decode_match(tx.get("input", ""))
            if d is None:
                rows.append({"tx": tx["hash"], "block": int(tx["blockNumber"], 16), "to": tx["to"], "sel": tx["input"][:10]})
                continue
            for o in d["orders"]:
                o.update({"tx": tx["hash"], "block": int(tx["blockNumber"], 16), "to": tx["to"], "sel": SEL,
                          "cond": d["cond"], "operator": tx["from"]})
                rows.append(o)
        time.sleep(0.6)
    df = pd.DataFrame(rows)
    for c in ("salt", "maker_amount", "taker_amount", "sign_ms", "fill", "fee"):
        if c in df.columns:
            df[c] = df[c].astype("float64") if c != "salt" else df[c].astype(str)
    df.to_parquet(f, index=False)
    print(day, len(sample), len(df), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 400, int(sys.argv[3]) if len(sys.argv) > 3 else 0)
