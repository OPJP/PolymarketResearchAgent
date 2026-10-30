"""Point-in-time (PIT) data layer: the only door through which strategies see data.

No-future-data rule
-------------------
Every record carries two times:

* ``event_ts``     - the moment the record describes (a candle's open, a trade's block time)
* ``available_ts`` - the first moment a participant could have known it
  (``event_ts + availability_lag``; e.g. a 1-minute candle's close is only known
  60 s after its open timestamp).

A strategy evaluated at decision time ``t`` receives a :class:`PITView`. The view
only answers with records whose ``available_ts <= t``; asking for anything later
raises :class:`LookAheadError`. Market metadata is split: fields knowable when a
market is listed are visible, post-hoc fields (resolution outcome, final volume,
closed time, current prices) are masked and only the settlement engine may read
them, and only after the market's resolution time.

Because Python cannot sandbox arbitrary code, :func:`audit_no_lookahead` adds an
empirical proof: it re-runs a decision function on a store truncated at ``t``
(every record available after ``t`` deleted) and requires identical decisions.
Any dependency on future data makes the two runs disagree.
"""

from __future__ import annotations

import bisect
import dataclasses
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np


class LookAheadError(RuntimeError):
    """Raised when code evaluated at time t requests data available after t."""


# Gamma market fields that are knowable when the market is listed. Everything
# else (outcomePrices, closed, closedTime, umaResolutionStatus, volume*,
# liquidity*, bestBid/Ask, lastTradePrice, oneDayPriceChange, ...) is post-hoc.
STATIC_MARKET_FIELDS = (
    "conditionId",
    "question",
    "slug",
    "description",
    "outcomes",
    "clobTokenIds",
    "negRisk",
    "negRiskMarketID",
    "startDate",
    "createdAt",
    "endDate",
    "gameStartTime",
    "eventStartTime",
    "resolutionSource",
    "orderPriceMinTickSize",
    "orderMinSize",
    "category",
    "sportsMarketType",
    "line",
    "groupItemTitle",
    "feeSchedule",
    "takerBaseFee",
    "makerBaseFee",
    "feesEnabled",
)


@dataclasses.dataclass(frozen=True)
class TimeSeries:
    """Immutable series sorted by ``available_ts``."""

    name: str
    event_ts: np.ndarray
    available_ts: np.ndarray
    values: np.ndarray

    @staticmethod
    def build(name: str, records: Iterable[tuple[int, Any]], availability_lag: int = 0) -> "TimeSeries":
        recs = sorted(((int(t), v) for t, v in records), key=lambda r: r[0])
        ev = np.array([r[0] for r in recs], dtype=np.int64)
        vals = np.array([r[1] for r in recs], dtype=float if all(isinstance(r[1], (int, float)) for r in recs) else object)
        av = ev + int(availability_lag)
        for arr in (ev, av, vals):
            arr.setflags(write=False)
        return TimeSeries(name, ev, av, vals)

    def __len__(self) -> int:
        return len(self.event_ts)

    def cut(self, t: int) -> "TimeSeries":
        """All records available at or before ``t``."""
        k = int(np.searchsorted(self.available_ts, t, side="right"))
        return TimeSeries(self.name, self.event_ts[:k], self.available_ts[:k], self.values[:k])


@dataclasses.dataclass(frozen=True)
class Print:
    """One public fill on the market tape (any wallet)."""

    ts: int
    token_id: str
    side: str  # taker side as reported by the tape
    price: float
    size: float
    wallet: str = ""


class PITStore:
    """Holds every series / tape / market record a backtest may need."""

    def __init__(self) -> None:
        self.series: dict[str, TimeSeries] = {}
        self.tapes: dict[str, list[Print]] = {}  # token_id -> prints sorted by ts
        self._tape_ts: dict[str, list[int]] = {}
        self.markets: dict[str, dict[str, Any]] = {}  # condition_id -> full gamma record
        self.listed_at: dict[str, int] = {}
        self.resolution: dict[str, tuple[int, dict[str, float]]] = {}  # cond -> (resolved_ts, token->payout)

    # ------------------------------------------------------------ loading
    def add_series(self, ts: TimeSeries) -> None:
        self.series[ts.name] = ts

    def add_tape(self, token_id: str, prints: Iterable[Print]) -> None:
        rows = sorted(prints, key=lambda p: p.ts)
        self.tapes[token_id] = rows
        self._tape_ts[token_id] = [p.ts for p in rows]

    def add_market(self, market: Mapping[str, Any], listed_at: int, resolution: tuple[int, dict[str, float]] | None = None) -> None:
        cid = market["conditionId"]
        self.markets[cid] = dict(market)
        self.listed_at[cid] = int(listed_at)
        if resolution is not None:
            self.resolution[cid] = (int(resolution[0]), dict(resolution[1]))

    def view(self, t: int) -> "PITView":
        return PITView(self, int(t))

    def truncated(self, t: int) -> "PITStore":
        """Copy with every record available after ``t`` physically removed."""
        out = PITStore()
        for name, s in self.series.items():
            out.series[name] = s.cut(t)
        for tok, prints in self.tapes.items():
            k = bisect.bisect_right(self._tape_ts[tok], t)
            out.add_tape(tok, prints[:k])
        for cid, m in self.markets.items():
            if self.listed_at[cid] <= t:
                out.markets[cid] = {k: m[k] for k in STATIC_MARKET_FIELDS if k in m}
                out.listed_at[cid] = self.listed_at[cid]
        for cid, (rt, payout) in self.resolution.items():
            if rt <= t:
                out.resolution[cid] = (rt, payout)
        return out


class PITView:
    """Read-only, time-bounded view handed to decision functions."""

    __slots__ = ("_store", "t", "accessed_max_available_ts")

    def __init__(self, store: PITStore, t: int):
        self._store = store
        self.t = t
        self.accessed_max_available_ts = -math.inf

    def _guard(self, at: int) -> None:
        if at > self.t:
            raise LookAheadError(f"requested data at {at} > decision time {self.t}")

    def _note(self, available_ts: int) -> None:
        if available_ts > self.t:  # defensive: should be impossible via this API
            raise LookAheadError(f"record available at {available_ts} leaked into view at {self.t}")
        self.accessed_max_available_ts = max(self.accessed_max_available_ts, available_ts)

    # ------------------------------------------------------------ series
    def latest(self, name: str, at: int | None = None) -> tuple[int, Any] | None:
        """Most recent (event_ts, value) available at ``at`` (default: now)."""
        at = self.t if at is None else at
        self._guard(at)
        s = self._store.series.get(name)
        if s is None:
            raise KeyError(f"unknown series {name}")
        k = int(np.searchsorted(s.available_ts, at, side="right"))
        if k == 0:
            return None
        self._note(int(s.available_ts[k - 1]))
        return int(s.event_ts[k - 1]), s.values[k - 1]

    def history(self, name: str, lookback: int) -> tuple[np.ndarray, np.ndarray]:
        """(event_ts, values) of records available in (t - lookback, t]."""
        s = self._store.series.get(name)
        if s is None:
            raise KeyError(f"unknown series {name}")
        hi = int(np.searchsorted(s.available_ts, self.t, side="right"))
        lo = int(np.searchsorted(s.available_ts, self.t - lookback, side="right"))
        if hi > lo:
            self._note(int(s.available_ts[hi - 1]))
        ev, vals = s.event_ts[lo:hi].copy(), s.values[lo:hi].copy()
        ev.setflags(write=False)
        vals.setflags(write=False)
        return ev, vals

    def has_series(self, name: str) -> bool:
        return name in self._store.series

    # ------------------------------------------------------------ tape
    def prints(self, token_id: str, lookback: int) -> list[Print]:
        ts = self._store._tape_ts.get(token_id)
        if not ts:
            return []
        hi = bisect.bisect_right(ts, self.t)
        lo = bisect.bisect_right(ts, self.t - lookback)
        rows = self._store.tapes[token_id][lo:hi]
        if rows:
            self._note(rows[-1].ts)
        return list(rows)

    def last_price(self, token_id: str) -> float | None:
        ts = self._store._tape_ts.get(token_id)
        if not ts:
            return None
        k = bisect.bisect_right(ts, self.t)
        if k == 0:
            return None
        p = self._store.tapes[token_id][k - 1]
        self._note(p.ts)
        return p.price

    # ------------------------------------------------------------ markets
    def market(self, condition_id: str) -> dict[str, Any] | None:
        """Static (listing-time) fields of a market listed at or before t."""
        listed = self._store.listed_at.get(condition_id)
        if listed is None or listed > self.t:
            return None
        self._note(listed)
        m = self._store.markets[condition_id]
        return {k: m[k] for k in STATIC_MARKET_FIELDS if k in m}

    def listed_markets(self) -> list[str]:
        return [c for c, ts in self._store.listed_at.items() if ts <= self.t]

    def resolution(self, condition_id: str) -> dict[str, float] | None:
        """Payouts only once the market has resolved by t."""
        r = self._store.resolution.get(condition_id)
        if r is None or r[0] > self.t:
            return None
        self._note(r[0])
        return dict(r[1])


DecisionFn = Callable[[PITView, Any], Any]


def audit_no_lookahead(
    decide: DecisionFn,
    store: PITStore,
    probes: list[tuple[int, Any]],
) -> dict[str, Any]:
    """Empirically prove a decision function ignores future data.

    For every ``(t, opportunity)`` probe the function is evaluated twice: on the
    full store and on a copy truncated at ``t``. A decision function that only
    uses the PIT view as intended returns identical decisions; any reliance on
    future records (including through closures, globals or the masked market
    fields) shows up as a mismatch or as a ``LookAheadError``.
    """
    mismatches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    cache: dict[int, PITStore] = {}
    for t, opp in probes:
        try:
            full = decide(store.view(t), opp)
        except LookAheadError as exc:
            errors.append({"t": t, "error": str(exc)})
            continue
        trunc_store = cache.get(t) or store.truncated(t)
        cache[t] = trunc_store
        if len(cache) > 64:
            cache.pop(next(iter(cache)))
        try:
            cut = decide(trunc_store.view(t), opp)
        except Exception as exc:  # a truncated store must never break a valid strategy
            errors.append({"t": t, "error": f"truncated run failed: {exc!r}"})
            continue
        if _canon(full) != _canon(cut):
            mismatches.append({"t": t, "full": _canon(full), "truncated": _canon(cut)})
    return {
        "probes": len(probes),
        "mismatches": mismatches[:20],
        "mismatch_count": len(mismatches),
        "errors": errors[:20],
        "error_count": len(errors),
        "passed": not mismatches and not errors,
    }


def _canon(x: Any) -> str:
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        x = dataclasses.asdict(x)
    return json.dumps(x, sort_keys=True, default=str)


# ---------------------------------------------------------------- external data
@dataclasses.dataclass(frozen=True)
class ExternalSourceSpec:
    """A public time series that can be pulled into the PIT store.

    ``url_template`` may contain ``{start}``, ``{end}`` (unix seconds),
    ``{start_ms}``, ``{end_ms}``, ``{start_iso}``, ``{end_iso}``.
    ``records_path`` is a dotted path to the list of records in the JSON body
    ("" for a top-level list). ``time_field`` / ``value_field`` are dict keys or
    list indices. ``availability_lag_seconds`` is how long after ``event_ts``
    the value was public; it must be set honestly (e.g. 60 for a 1-minute
    candle keyed by its open time).
    """

    name: str
    url_template: str
    records_path: str
    time_field: str | int
    value_field: str | int
    time_unit: str = "s"  # "s" | "ms" | "iso"
    availability_lag_seconds: int = 0
    chunk_seconds: int = 86400
    description: str = ""

    def __post_init__(self) -> None:
        if not self.url_template.startswith("https://"):
            raise ValueError("external sources must be public https URLs")
        if self.time_unit not in ("s", "ms", "iso"):
            raise ValueError("time_unit must be s, ms or iso")
        if self.availability_lag_seconds < 0:
            raise ValueError("availability lag cannot be negative")
        if not self.name.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("name must be alphanumeric with - _ .")


BUILTIN_SOURCES: dict[str, ExternalSourceSpec] = {
    f"coinbase.{a}usd.1m": ExternalSourceSpec(
        name=f"coinbase.{a}usd.1m",
        url_template=f"https://api.exchange.coinbase.com/products/{a.upper()}-USD/candles?granularity=60&start={{start_iso}}&end={{end_iso}}",
        records_path="",
        time_field=0,
        value_field=4,
        time_unit="s",
        availability_lag_seconds=60,  # candle keyed by open; close known one minute later
        chunk_seconds=300 * 60,
        description=f"Coinbase {a.upper()}-USD 1-minute candle close",
    )
    for a in ("btc", "eth", "sol", "xrp", "doge")
} | {
    f"okx.{a}usdt.1m": ExternalSourceSpec(
        name=f"okx.{a}usdt.1m",
        url_template=f"https://www.okx.com/api/v5/market/history-candles?instId={a.upper()}-USDT&bar=1m&after={{end_ms}}&before={{start_ms}}&limit=100",
        records_path="data",
        time_field=0,
        value_field=4,
        time_unit="ms",
        availability_lag_seconds=60,
        chunk_seconds=100 * 60,
        description=f"OKX {a.upper()}-USDT 1-minute candle close",
    )
    for a in ("btc", "eth", "sol")
}


class ExternalRegistry:
    """Registry of external public sources, persisted as JSON in the research tree."""

    def __init__(self, path: Path | None = None):
        self.path = path
        self.sources: dict[str, ExternalSourceSpec] = dict(BUILTIN_SOURCES)
        if path and path.exists():
            for raw in json.loads(path.read_text()):
                spec = ExternalSourceSpec(**raw)
                self.sources[spec.name] = spec

    def register(self, spec: ExternalSourceSpec) -> None:
        self.sources[spec.name] = spec
        if self.path:
            custom = [dataclasses.asdict(s) for n, s in sorted(self.sources.items()) if n not in BUILTIN_SOURCES]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(custom, indent=2))

    def fetch(self, name: str, start: int, end: int, http: Any = None) -> tuple[TimeSeries, list[Any]]:
        from polyrea.adapters.http import shared_client

        spec = self.sources[name]
        http = http or shared_client()
        records: dict[int, float] = {}
        sources = []
        t = start
        import time as _time

        while t < end:
            t2 = min(end, t + spec.chunk_seconds)
            url = spec.url_template.format(
                start=t, end=t2, start_ms=t * 1000, end_ms=t2 * 1000, start_iso=_iso(t), end_iso=_iso(t2)
            )
            settled = t2 < _time.time() - 2 * 3600
            data, src = http.get_json(url, None, adapter=f"external.{spec.name}", max_age=None if settled else 600)
            body = _dig(data, spec.records_path)
            src.records = len(body) if isinstance(body, list) else 0
            sources.append(src)
            for row in body or []:
                try:
                    ts = _parse_time(row[spec.time_field], spec.time_unit)
                    val = float(row[spec.value_field])
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if start <= ts < end:
                    records[ts] = val
            t = t2
        return TimeSeries.build(spec.name, records.items(), spec.availability_lag_seconds), sources


def _dig(data: Any, path: str) -> Any:
    if not path:
        return data
    for part in path.split("."):
        data = data[int(part)] if isinstance(data, list) else data.get(part) if isinstance(data, dict) else None
        if data is None:
            return []
    return data


def _parse_time(raw: Any, unit: str) -> int:
    if unit == "s":
        return int(float(raw))
    if unit == "ms":
        return int(float(raw)) // 1000
    import datetime as dt

    return int(dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp())


def _iso(ts: int) -> str:
    import datetime as dt

    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
