"""Second-resolution spot prices from public exchange trade feeds.

Kraken's public ``Trades`` endpoint accepts ``since`` (ns timestamp) and returns
~1000 trades per call, so any historical window is reachable directly. Trades
are reduced to one value per second (last trade in that second). A second's
value is only *available* once that second has ended, so the series is built
with ``availability_lag=1``.

Binance's REST API is geo-blocked from the research host, but its public
archive (data.binance.vision) publishes 1-second klines per UTC day, with a
SHA-256 checksum file, the day after. A kline's close is the last trade of
that second, the same quantity as the Kraken series. Binance leads Kraken by
about a second in price discovery, so it is the better public proxy for the
Chainlink feed that settles the Up/Down markets.
"""

from __future__ import annotations

import csv
import hashlib
import io
import time
import zipfile
from typing import Any

import numpy as np

from polyrea.adapters.http import HttpClient, shared_client
from polyrea.evidence import Source
from polyrea.pit import TimeSeries

KRAKEN_TRADES = "https://api.kraken.com/0/public/Trades"
KRAKEN_PAIRS = {"btc": "XBTUSD", "eth": "ETHUSD", "sol": "SOLUSD", "xrp": "XRPUSD", "doge": "XDGUSD"}
BINANCE_ARCHIVE = "https://data.binance.vision/data/spot/daily/klines/{sym}/1s/{sym}-1s-{day}.zip"
BINANCE_SYMBOLS = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT", "doge": "DOGEUSDT"}


def binance_seconds(asset: str, start: int, end: int, http: HttpClient | None = None) -> tuple[list[tuple[float, float]], list[Source]]:
    """(second, close) of Binance 1-second klines in [start, end), from the daily archive.

    Each day's zip is checked against its published SHA-256 before use.
    """
    http = http or shared_client()
    sym = BINANCE_SYMBOLS[asset.lower()]
    out: list[tuple[float, float]] = []
    sources: list[Source] = []
    for day0 in range(int(start) // 86400 * 86400, int(end), 86400):
        day = time.strftime("%Y-%m-%d", time.gmtime(day0))
        url = BINANCE_ARCHIVE.format(sym=sym, day=day)
        body, src = http.get_bytes(url, adapter="binance.archive", max_age=None)
        check, _ = http.get_bytes(url + ".CHECKSUM", adapter="binance.archive", max_age=None)
        expected = check.decode().split()[0]
        if hashlib.sha256(body).hexdigest() != expected:
            raise RuntimeError(f"checksum mismatch for {url}")
        sources.append(src)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            text = z.read(z.namelist()[0]).decode()
        for row in csv.reader(io.StringIO(text)):
            if not row or not row[0].isdigit():
                continue
            t_open = int(row[0])
            sec = t_open // 1_000_000 if t_open > 10**14 else t_open // 1000  # archive switched ms -> us in 2025
            if start <= sec < end:
                out.append((float(sec), float(row[4])))
    return out, sources


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
