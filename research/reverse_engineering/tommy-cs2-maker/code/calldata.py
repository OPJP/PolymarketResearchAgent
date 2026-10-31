"""B1: decode V2 exchange matchOrders calldata (selector 0x3c2b4399).

matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders, uint256 takerFillAmount,
            uint256[] makerFillAmounts, uint256 takerFeeAmount, uint256[] makerFeeAmounts)
Order(uint256 salt, address maker, address signer, uint256 tokenId, uint256 makerAmount, uint256 takerAmount,
      uint8 side, uint8 signatureType, uint256 timestamp, bytes32 metadata, bytes32 builder, bytes signature)

`timestamp` is the client signing time in milliseconds. side 0 = BUY (makerAmount is USDC, takerAmount shares),
1 = SELL (makerAmount shares, takerAmount USDC). Amounts have 6 decimals.
"""
from __future__ import annotations

SEL = "0x3c2b4399"


def _w(data: bytes, i: int) -> int:
    return int.from_bytes(data[32 * i: 32 * i + 32], "big")


def _order(data: bytes, off: int) -> dict:
    """Decode one Order tuple whose head starts at byte offset `off` (relative to the args start)."""
    def w(k):
        return int.from_bytes(data[off + 32 * k: off + 32 * k + 32], "big")
    side = w(6)
    mk, tk = w(4), w(5)
    if side == 0:  # BUY: pays makerAmount USDC for takerAmount shares
        price = mk / tk if tk else float("nan")
        shares = tk / 1e6
    else:
        price = tk / mk if mk else float("nan")
        shares = mk / 1e6
    return {
        "salt": str(w(0)),
        "maker": "0x" + data[off + 32 + 12: off + 64].hex(),
        "signer": "0x" + data[off + 64 + 12: off + 96].hex(),
        "token_id": str(w(3)),
        "maker_amount": mk / 1e6,
        "taker_amount": tk / 1e6,
        "side": side,
        "sig_type": w(7),
        "sign_ms": w(8),
        "metadata": "0x" + data[off + 32 * 9: off + 32 * 10].hex(),
        "builder": "0x" + data[off + 32 * 10: off + 32 * 11].hex(),
        "price": price,
        "shares": shares,
    }


def decode_match_orders(inp: str) -> dict | None:
    if not inp or not inp.startswith(SEL):
        return None
    data = bytes.fromhex(inp[10:])
    cond = "0x" + data[0:32].hex()
    taker_off = _w(data, 1)
    makers_off = _w(data, 2)
    taker_fill = _w(data, 3)
    mfills_off = _w(data, 4)
    taker_fee = _w(data, 5)
    mfees_off = _w(data, 6)
    taker = _order(data, taker_off)
    n = _w(data, makers_off // 32)
    base = makers_off + 32
    makers = []
    for k in range(n):
        o = int.from_bytes(data[base + 32 * k: base + 32 * k + 32], "big")
        makers.append(_order(data, base + o))
    nf = _w(data, mfills_off // 32)
    fills = [_w(data, mfills_off // 32 + 1 + k) / 1e6 for k in range(nf)]
    nfe = _w(data, mfees_off // 32)
    fees = [_w(data, mfees_off // 32 + 1 + k) / 1e6 for k in range(nfe)]
    return {"condition_id": cond, "taker": taker, "makers": makers, "taker_fill": taker_fill / 1e6,
            "maker_fills": fills, "taker_fee": taker_fee / 1e6, "maker_fees": fees}
