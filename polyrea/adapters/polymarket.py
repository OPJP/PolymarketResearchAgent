"""Polymarket public data adapters: data-api, gamma-api and clob.

All endpoints are public and unauthenticated. Paging rules observed live
(2026-10):

* ``data-api /v2/leaderboard`` returns up to 500 rows per call; further pages are
  cursor-only.
* ``data-api /activity`` and ``/trades`` cap ``offset`` at a few thousand, so full
  history is read with timestamp cursors (``start``/``end``) and overlap de-dup.
* ``clob /prices-history`` rejects ``startTs``/``endTs`` windows longer than about
  a week at fine fidelity, so long ranges are read in chunks.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Iterable

from polyrea.adapters.http import HttpClient, HttpError, shared_client
from polyrea.evidence import Coverage, Source

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

PAGE = 500
ACTIVITY_TYPES = ("TRADE", "SPLIT", "MERGE", "REDEEM", "REWARD", "CONVERSION", "MAKER_REBATE", "YIELD")

# A day in seconds; historical windows that ended more than this long ago are
# treated as immutable and cached forever.
_SETTLED_AFTER = 2 * 86400


def _age_policy(end_ts: int | None) -> float | None:
    """Cache forever once a window is settled; otherwise reuse for 12 hours.

    Investigations pin ``end`` to an ``as_of`` timestamp, so a recent window
    re-read within the TTL describes the same frozen period.
    """
    if end_ts is not None and end_ts < time.time() - _SETTLED_AFTER:
        return None
    return 12 * 3600.0


def as_of_now() -> int:
    """Current time floored to the hour: the default frozen investigation end."""
    return int(time.time()) // 3600 * 3600


def activity_key(r: dict[str, Any]) -> tuple:
    return (
        r.get("transactionHash"),
        r.get("asset"),
        r.get("type"),
        r.get("side"),
        r.get("size"),
        r.get("price"),
        r.get("timestamp"),
        r.get("conditionId"),
    )


def merge_cursor_pages(pages: Iterable[list[dict[str, Any]]], ts_field: str = "timestamp") -> list[dict[str, Any]]:
    """Merge oldest-first pages read with timestamp cursors into one oldest-first list.

    Each page was requested from the previous page's boundary timestamp
    (inclusive), so rows at that timestamp can repeat. Repeats are removed by
    multiset subtraction against the rows already merged at the boundary, so
    genuinely identical rows (two equal fills in one transaction) survive.
    """
    out: list[dict[str, Any]] = []
    tail_ts: Any = None
    tail: Counter = Counter()
    for page in pages:
        overlap = Counter(tail)
        for row in page:
            ts = row.get(ts_field)
            if ts == tail_ts:
                k = activity_key(row)
                if overlap[k] > 0:
                    overlap[k] -= 1
                    continue
            out.append(row)
            if ts != tail_ts:
                tail_ts = ts
                tail = Counter()
            tail[activity_key(row)] += 1
    return out


class PolymarketData:
    def __init__(self, http: HttpClient | None = None):
        self.http = http or shared_client()

    # ---------------------------------------------------------------- leaderboard
    def leaderboard(
        self, time_period: str = "month", order_by: str = "PNL", limit: int = 500, category: str | None = None
    ) -> tuple[list[dict[str, Any]], list[Source]]:
        rows: list[dict[str, Any]] = []
        sources: list[Source] = []
        cursor = None
        while len(rows) < limit:
            params = {"timePeriod": time_period, "orderBy": order_by, "limit": min(PAGE, limit - len(rows))}
            if category:
                params["category"] = category
            if cursor:
                params["cursor"] = cursor
            data, src = self.http.get_json(f"{DATA_API}/v2/leaderboard", params, adapter="data-api.leaderboard", max_age=6 * 3600)
            page = data.get("data", [])
            src.records = len(page)
            sources.append(src)
            rows.extend(page)
            pag = data.get("pagination") or {}
            cursor = pag.get("next_cursor")
            if not page or not pag.get("has_more") or not cursor:
                break
        return rows[:limit], sources

    # ---------------------------------------------------------------- pnl series
    def user_pnl(self, wallet: str, interval: str = "all", fidelity: str = "1d", max_age: float = 6 * 3600) -> tuple[dict[str, Any], Source]:
        data, src = self.http.get_json(
            f"{DATA_API}/v2/user-pnl",
            {"user": wallet.lower(), "interval": interval, "fidelity": fidelity},
            adapter="data-api.user-pnl",
            max_age=max_age,
        )
        body = (data or {}).get("data") or {}
        src.records = len(body.get("points") or [])
        return body, src

    def portfolio_value(self, wallet: str) -> tuple[float | None, Source]:
        data, src = self.http.get_json(f"{DATA_API}/value", {"user": wallet.lower()}, adapter="data-api.value", max_age=6 * 3600)
        value = data[0]["value"] if isinstance(data, list) and data else None
        return value, src

    def positions(self, wallet: str, closed: bool = False, max_rows: int = 5000) -> tuple[list[dict[str, Any]], list[Source]]:
        path = "closed-positions" if closed else "positions"
        rows: list[dict[str, Any]] = []
        sources: list[Source] = []
        page_size = 50 if closed else PAGE
        offset = 0
        while offset < max_rows:
            try:
                data, src = self.http.get_json(
                    f"{DATA_API}/{path}",
                    {"user": wallet.lower(), "limit": page_size, "offset": offset, "sizeThreshold": 0},
                    adapter=f"data-api.{path}",
                    max_age=6 * 3600,
                )
            except HttpError as exc:
                if exc.status == 400:
                    break
                raise
            src.records = len(data or [])
            sources.append(src)
            if not data:
                break
            rows.extend(data)
            if len(data) < page_size:
                break
            offset += page_size
        return rows, sources

    # ---------------------------------------------------------------- activity
    def activity(
        self,
        wallet: str,
        start: int | None = None,
        end: int | None = None,
        types: tuple[str, ...] | None = None,
        max_rows: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[Source], Coverage]:
        """Full activity history with timestamp cursors, oldest first."""
        end = end if end is not None else as_of_now()
        return self._cursor_scan(
            f"{DATA_API}/activity",
            {"user": wallet.lower(), **({"type": ",".join(types)} if types else {})},
            start=start,
            end=end,
            adapter="data-api.activity",
            max_rows=max_rows,
        )

    def market_trades(
        self,
        condition_id: str,
        start: int | None = None,
        end: int | None = None,
        max_rows: int | None = 200_000,
        taker_only: bool = False,
    ) -> tuple[list[dict[str, Any]], list[Source], Coverage]:
        """Public tape of one market, oldest first.

        ``taker_only=True`` returns one row per aggressive order (the taker's
        side, price and wallet); otherwise maker rows are included too.
        """
        end = end if end is not None else as_of_now()
        return self._cursor_scan(
            f"{DATA_API}/trades",
            {"market": condition_id, "takerOnly": "true" if taker_only else "false"},
            start=start,
            end=end,
            adapter="data-api.trades",
            max_rows=max_rows,
            ascending_supported=False,
        )

    def _cursor_scan(
        self,
        url: str,
        base_params: dict[str, Any],
        *,
        start: int | None,
        end: int | None,
        adapter: str,
        max_rows: int | None,
        ascending_supported: bool = True,
    ) -> tuple[list[dict[str, Any]], list[Source], Coverage]:
        sources: list[Source] = []
        pages: list[list[dict[str, Any]]] = []
        total = 0
        truncated = False
        if ascending_supported:
            cursor = start or 0
            stall = 0
            while True:
                params = {**base_params, "limit": PAGE, "start": cursor, "end": end, "sortBy": "TIMESTAMP", "sortDirection": "ASC"}
                page, src = self._page(url, params, adapter, end)
                sources.append(src)
                if pages and len(page) == PAGE and page[-1].get("timestamp") == cursor:
                    # every row sits on one timestamp: walk it with offset
                    stall += 1
                    if stall > 10:
                        truncated = True
                        break
                    extra = self._offset_walk(url, {**params, "start": cursor, "end": cursor}, adapter, end, sources)
                    pages.append(extra)
                    cursor = cursor + 1
                    continue
                pages.append(page)
                total += len(page)
                if len(page) < PAGE:
                    break
                if max_rows is not None and total >= max_rows:
                    truncated = True
                    break
                cursor = page[-1]["timestamp"]
            rows = merge_cursor_pages(pages)
        else:
            cursor_end = end
            while True:
                params = {**base_params, "limit": PAGE, "start": start, "end": cursor_end}
                page, src = self._page(url, params, adapter, cursor_end)
                sources.append(src)
                page = list(reversed(page))  # API returns newest first
                if len(page) == PAGE and page[0].get("timestamp") == page[-1].get("timestamp"):
                    # a full page on one timestamp: walk that second with offset
                    ts = page[0]["timestamp"]
                    extra = self._offset_walk(url, {**base_params, "start": ts, "end": ts}, adapter, ts, sources)
                    pages.append(extra)
                    total += len(extra)
                    if start is not None and ts - 1 < start:
                        break
                    cursor_end = ts - 1
                    continue
                pages.append(page)
                total += len(page)
                if len(page) < PAGE:
                    break
                if max_rows is not None and total >= max_rows:
                    truncated = True
                    break
                cursor_end = page[0]["timestamp"]
            rows = merge_cursor_pages(list(reversed(pages)))
        coverage = Coverage(
            "partial" if truncated else ("complete" if rows else "empty"),
            f"{len(rows)} rows via {len(sources)} requests" + ("; truncated at max_rows" if truncated else ""),
        )
        return rows, sources, coverage

    def _page(self, url: str, params: dict[str, Any], adapter: str, end: int | None) -> tuple[list[dict[str, Any]], Source]:
        data, src = self.http.get_json(url, params, adapter=adapter, max_age=_age_policy(end))
        page = data if isinstance(data, list) else []
        src.records = len(page)
        return page, src

    def _offset_walk(self, url: str, params: dict[str, Any], adapter: str, end: int | None, sources: list[Source]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while offset <= 5000:
            try:
                page, src = self._page(url, {**params, "offset": offset}, adapter, end)
            except HttpError as exc:
                if exc.status == 400:
                    break
                raise
            sources.append(src)
            rows.extend(page)
            if len(page) < PAGE:
                break
            offset += PAGE
        return rows

    # ---------------------------------------------------------------- gamma
    def markets_by_condition(self, condition_ids: list[str], chunk: int = 20) -> tuple[dict[str, dict[str, Any]], list[Source]]:
        out: dict[str, dict[str, Any]] = {}
        sources: list[Source] = []
        ids = sorted(set(c for c in condition_ids if c))
        for i in range(0, len(ids), chunk):
            part = ids[i : i + chunk]
            data, src = self.http.get_json(
                f"{GAMMA_API}/markets",
                [("condition_ids", c) for c in part] + [("limit", len(part) * 2), ("closed", "true")],  # type: ignore[arg-type]
                adapter="gamma.markets",
                max_age=24 * 3600,
            )
            found = {m.get("conditionId"): m for m in (data or [])}
            missing = [c for c in part if c not in found]
            if missing:
                data2, src2 = self.http.get_json(
                    f"{GAMMA_API}/markets",
                    [("condition_ids", c) for c in missing] + [("limit", len(missing) * 2)],  # type: ignore[arg-type]
                    adapter="gamma.markets",
                    max_age=3600,
                )
                for m in data2 or []:
                    found[m.get("conditionId")] = m
                sources.append(src2)
            src.records = len(found)
            sources.append(src)
            out.update(found)
        return out, sources

    def active_markets(self, tag_slug: str | None = None, limit: int = 500, **filters: Any) -> tuple[list[dict[str, Any]], list[Source]]:
        rows: list[dict[str, Any]] = []
        sources: list[Source] = []
        offset = 0
        while len(rows) < limit:
            params = {"closed": "false", "active": "true", "limit": min(100, limit - len(rows)), "offset": offset, **filters}
            if tag_slug:
                params["tag_slug"] = tag_slug
            data, src = self.http.get_json(f"{GAMMA_API}/markets", params, adapter="gamma.markets", max_age=3600)
            src.records = len(data or [])
            sources.append(src)
            if not data:
                break
            rows.extend(data)
            if len(data) < params["limit"]:
                break
            offset += len(data)
        return rows, sources

    # ---------------------------------------------------------------- clob
    def price_history(
        self, token_id: str, start: int, end: int, fidelity_minutes: int = 1, chunk_seconds: int = 4 * 86400
    ) -> tuple[list[tuple[int, float]], list[Source]]:
        points: dict[int, float] = {}
        sources: list[Source] = []
        t = start
        while t < end:
            t2 = min(end, t + chunk_seconds)
            try:
                data, src = self.http.get_json(
                    f"{CLOB_API}/prices-history",
                    {"market": token_id, "startTs": t, "endTs": t2, "fidelity": fidelity_minutes},
                    adapter="clob.prices-history",
                    max_age=_age_policy(t2),
                )
            except HttpError as exc:
                if exc.status in (400, 404):
                    t = t2
                    continue
                raise
            hist = (data or {}).get("history") or []
            src.records = len(hist)
            sources.append(src)
            for p in hist:
                points[int(p["t"])] = float(p["p"])
            t = t2
        return sorted(points.items()), sources
