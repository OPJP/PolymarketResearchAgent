"""Second-resolution spot prices from public exchange trade feeds.

Kraken's public ``Trades`` endpoint accepts ``since`` (ns timestamp) and returns
~1000 trades per call, so any historical window is reachable directly. Trades
are reduced to one value per second (last trade in that second). A second's
value is only *available* once that second has ended, so the series is built
with ``availability_lag=1``.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from polyrea.adapters.http import HttpClient, shared_client
from polyrea.evidence import Source
from polyrea.pit import TimeSeries

KRAKEN_TRADES = "https://api.kraken.com/0/public/Trades"
KRAKEN_PAIRS = {"btc": "XBTUSD", "eth": "ETHUSD", "sol": "SOLUSD", "xrp": "XRPUSD", "doge": "XDGUSD"}


def kraken_trades(asset: str, start: int, end: int, http: HttpClient | None = None) -> tuple[list[tuple[float, float]], list[Source]]:
    """(unix_seconds_float, price) for every Kraken trade in [start, end)."""
    http = http or shared_client()
    pair = KRAKEN_PAIRS[asset.lower()]
    out: list[tuple[float, float]] = []
    sources: list[Source] = []
    since = int(start) * 1_000_000_000
    settled = end < time.time() - 3600
    guard = 0
    while True:
        guard += 1
        if guard > 5000:
            break
        data, src = http.get_json(
            KRAKEN_TRADES,
            {"pair": pair, "since": since, "count": 1000},
            adapter="kraken.trades",
            max_age=None if settled else 300,
            cache_if=lambda d: isinstance(d, dict) and not d.get("error") and "result" in d,
        )
        if data.get("error"):
            raise RuntimeError(f"kraken error {data['error']}")
        res = data["result"]
        key = next(k for k in res if k != "last")
        rows = res[key]
        src.records = len(rows)
        sources.append(src)
        if not rows:
            break
        for r in rows:
            ts = float(r[2])
            if ts >= end:
                return out, sources
            if ts >= start:
                out.append((ts, float(r[0])))
        nxt = int(res["last"])
        if nxt <= since:
            break
        since = nxt
    return out, sources


def per_second_series(name: str, trades: list[tuple[float, float]], start: int, end: int) -> TimeSeries:
    """Last trade price per second, forward-filled, available one second later."""
    if not trades:
        return TimeSeries.build(name, [], availability_lag=1)
    secs = np.floor(np.array([t for t, _ in trades])).astype(np.int64)
    px = np.array([p for _, p in trades])
    # last trade within each second
    last_idx = np.r_[np.nonzero(np.diff(secs))[0], len(secs) - 1]
    s_secs, s_px = secs[last_idx], px[last_idx]
    grid = np.arange(max(start, int(s_secs[0])), end, dtype=np.int64)
    pos = np.searchsorted(s_secs, grid, side="right") - 1
    vals = s_px[np.clip(pos, 0, None)]
    return TimeSeries.build(name, zip(grid.tolist(), vals.tolist()), availability_lag=1)
