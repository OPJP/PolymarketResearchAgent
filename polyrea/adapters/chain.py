"""Polygon RPC adapter: verifies Polymarket fills directly from transaction receipts.

The data API is a convenience index. To establish that a wallet's trades are
real on-chain fills (and whether the wallet supplied or took liquidity), this
adapter reads the receipt of a trade's transaction and decodes the exchange's
``OrderFilled`` events.

Event layouts (observed in receipts, 2026):

* CTF Exchange V1 (``0x4bfb41d5...``, NegRisk ``0xc5d563a3...``)
  topic0 ``0xd0a08e8c...``; topics ``[orderHash, maker, taker]``;
  data ``[makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled, fee]``.
  An asset id of 0 is USDC collateral.
* Exchange V2 (``0xe1111800...`` and siblings)
  topic0 ``0xd543adfd...``; topics ``[orderHash, maker, taker]``;
  data ``[side, tokenId, makerAmountFilled, takerAmountFilled, fee, ...]``,
  side 0 = BUY (maker pays USDC), 1 = SELL.

For both versions, the order of the *taker* emits an ``OrderFilled`` whose
``taker`` topic is the exchange contract itself; resting (maker) orders emit one
whose ``taker`` topic is the counterparty. That is how a wallet's role in a fill
is classified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from polyrea.adapters.http import HttpClient, HttpError, shared_client
from polyrea.evidence import Source

ARCHIVE_RPCS = ("https://polygon.drpc.org", "https://polygon-bor-rpc.publicnode.com")

ORDER_FILLED_V1 = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
ORDER_FILLED_V2 = "0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee"
USDC_DECIMALS = 6


@dataclass(frozen=True)
class Fill:
    tx_hash: str
    log_index: int
    exchange: str
    version: Literal["v1", "v2"]
    order_hash: str
    maker: str
    taker: str
    side: Literal["BUY", "SELL"]  # side of the order that emitted the event
    token_id: str
    shares: float
    usdc: float
    fee: float

    @property
    def price(self) -> float:
        return self.usdc / self.shares if self.shares else float("nan")

    def role_of(self, wallet: str) -> Literal["maker", "taker"] | None:
        """Role of ``wallet`` in this event's order (None if not its order)."""
        if self.maker != wallet.lower():
            return None
        return "taker" if self.taker == self.exchange else "maker"


def _addr(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def _words(data: str) -> list[int]:
    raw = data[2:] if data.startswith("0x") else data
    return [int(raw[i : i + 64], 16) for i in range(0, len(raw), 64)]


def decode_fills(receipt: dict[str, Any]) -> list[Fill]:
    fills: list[Fill] = []
    tx = receipt.get("transactionHash", "")
    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if len(topics) < 4 or topics[0] not in (ORDER_FILLED_V1, ORDER_FILLED_V2):
            continue
        w = _words(log.get("data", "0x"))
        exchange = log["address"].lower()
        maker, taker = _addr(topics[2]), _addr(topics[3])
        if topics[0] == ORDER_FILLED_V1:
            if len(w) < 5:
                continue
            maker_asset, taker_asset, maker_amt, taker_amt, fee = w[:5]
            if maker_asset == 0:  # maker pays USDC -> BUY shares
                side, token, usdc, shares = "BUY", taker_asset, maker_amt, taker_amt
            else:
                side, token, usdc, shares = "SELL", maker_asset, taker_amt, maker_amt
            version = "v1"
        else:
            if len(w) < 5:
                continue
            side_flag, token, maker_amt, taker_amt, fee = w[:5]
            if side_flag == 0:
                side, usdc, shares = "BUY", maker_amt, taker_amt
            else:
                side, usdc, shares = "SELL", taker_amt, maker_amt
            version = "v2"
        fills.append(
            Fill(
                tx_hash=tx,
                log_index=int(log.get("logIndex", "0x0"), 16),
                exchange=exchange,
                version=version,  # type: ignore[arg-type]
                order_hash=topics[1],
                maker=maker,
                taker=taker,
                side=side,  # type: ignore[arg-type]
                token_id=str(token),
                shares=shares / 10**USDC_DECIMALS,
                usdc=usdc / 10**USDC_DECIMALS,
                fee=fee / 10**USDC_DECIMALS,
            )
        )
    return fills


class PolygonChain:
    def __init__(self, http: HttpClient | None = None, rpcs: tuple[str, ...] = ARCHIVE_RPCS):
        self.http = http or shared_client()
        self.rpcs = rpcs

    def receipts(self, tx_hashes: list[str], batch: int = 4) -> tuple[dict[str, dict[str, Any] | None], list[Source]]:
        """Fetch receipts with JSON-RPC batches; receipts are immutable (cached forever)."""
        out: dict[str, dict[str, Any] | None] = {}
        sources: list[Source] = []
        hashes = list(dict.fromkeys(h for h in tx_hashes if h))
        for i in range(0, len(hashes), batch):
            part = hashes[i : i + batch]
            body = [
                {"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionReceipt", "params": [h]}
                for j, h in enumerate(part)
            ]
            result = None
            for rpc in self.rpcs:
                try:
                    result, src = self.http.post_json(rpc, body, adapter="polygon.rpc.receipts", max_age=None, max_retries=2)
                except HttpError:
                    continue
                if isinstance(result, list) and all(isinstance(r, dict) and r.get("result") for r in result):
                    src.records = len(result)
                    sources.append(src)
                    break
                result = None
            if result is None:
                # fall back to single calls so one bad hash does not sink a batch
                for h in part:
                    out[h] = self._single(h, sources)
                continue
            for r in result:
                out[part[r["id"]]] = r.get("result")
        return out, sources

    def _single(self, tx: str, sources: list[Source]) -> dict[str, Any] | None:
        for rpc in self.rpcs:
            try:
                res, src = self.http.post_json(
                    rpc,
                    {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx]},
                    adapter="polygon.rpc.receipts",
                    max_age=None,
                    max_retries=2,
                )
            except HttpError:
                continue
            if isinstance(res, dict) and res.get("result"):
                sources.append(src)
                return res["result"]
        return None
