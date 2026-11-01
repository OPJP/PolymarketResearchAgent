"""B1: decode V2 matchOrders calldata (selector 0x3c2b4399) into orders with signing time, size, price, signer.

matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders, uint256 takerFillAmount,
            uint256[] makerFillAmounts, uint256 takerFeeAmount, uint256[] makerFeeAmounts)
Order(uint256 salt, address maker, address signer, uint256 tokenId, uint256 makerAmount, uint256 takerAmount,
      uint8 side, uint8 signatureType, uint256 timestamp, bytes32 metadata, bytes32 builder, bytes signature)
Only decoded fields are kept (no raw input).
"""
from __future__ import annotations
import json, sys, time
import httpx

RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
SEL = "3c2b4399"


def _w(b: bytes, i: int) -> int:
    return int.from_bytes(b[32 * i: 32 * i + 32], "big")


def _order(b: bytes, off: int) -> dict:
    w = lambda k: int.from_bytes(b[off + 32 * k: off + 32 * k + 32], "big")
    sig_off = w(11)
    siglen = int.from_bytes(b[off + sig_off: off + sig_off + 32], "big")
    return {
        "salt": str(w(0)), "maker": "0x%040x" % w(1), "signer": "0x%040x" % w(2), "token_id": str(w(3)),
        "maker_amount": w(4), "taker_amount": w(5), "oside": w(6), "sig_type": w(7), "sign_ms": w(8),
        "metadata": "%064x" % w(9), "builder": "%064x" % w(10), "sig_len": siglen,
    }


def decode(inp: str) -> dict | None:
    if not inp or inp[2:10] != SEL:
        return None
    b = bytes.fromhex(inp[10:])
    cond = "0x%064x" % _w(b, 0)
    t_off, m_off = _w(b, 1), _w(b, 2)
    taker_fill = _w(b, 3)
    mf_off = _w(b, 4)
    taker_fee = _w(b, 5)
    mfee_off = _w(b, 6)
    taker = _order(b, t_off)
    n = _w(b, m_off // 32)
    base = m_off + 32
    makers = []
    for i in range(n):
        o = int.from_bytes(b[base + 32 * i: base + 32 * i + 32], "big")
        makers.append(_order(b, base + o))
    nf = _w(b, mf_off // 32)
    fills = [_w(b, mf_off // 32 + 1 + i) for i in range(nf)]
    nfe = _w(b, mfee_off // 32)
    fees = [_w(b, mfee_off // 32 + 1 + i) for i in range(nfe)]
    for i, m in enumerate(makers):
        m["fill_amount"] = fills[i] if i < len(fills) else None
        m["fee_amount"] = fees[i] if i < len(fees) else None
    return {"condition_id": cond, "taker": taker, "makers": makers, "taker_fill": taker_fill, "taker_fee": taker_fee}


def fetch_txs(hashes: list[str], batch: int = 25, pause: float = 0.25, client: httpx.Client | None = None):
    """Yield (hash, tx dict or None). Batched eth_getTransactionByHash."""
    cl = client or httpx.Client(timeout=30)
    for i in range(0, len(hashes), batch):
        part = hashes[i:i + batch]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)]
        res = None
        for attempt in range(6):
            rpc = RPCS[attempt % len(RPCS)]
            try:
                r = cl.post(rpc, json=body)
                if r.status_code == 429:
                    time.sleep(2 + 2 * attempt); continue
                r.raise_for_status()
                res = r.json()
                if isinstance(res, list) and all(isinstance(x, dict) and x.get("result") for x in res):
                    break
                res = None
                time.sleep(1 + attempt)
            except Exception as e:  # noqa
                time.sleep(1 + attempt)
        if res is None:
            for h in part:
                yield h, None
            continue
        byid = {x["id"]: x.get("result") for x in res}
        for j, h in enumerate(part):
            yield h, byid.get(j)
        time.sleep(pause)


if __name__ == "__main__":
    for h, tx in fetch_txs(sys.argv[1:]):
        d = decode(tx["input"]) if tx else None
        print(h, tx and tx.get("to"), tx and int(tx["blockNumber"], 16))
        print(json.dumps(d, indent=1)[:3000])
