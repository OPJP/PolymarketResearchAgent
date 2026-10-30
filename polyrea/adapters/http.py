"""Rate-limited, retrying, disk-cached HTTP client used by every adapter.

Responses are cached in SQLite keyed by method + URL + body. Callers choose a
``max_age`` per request: historical windows that can no longer change are read
with ``max_age=None`` (cache forever), live views such as the leaderboard with a
short TTL. Every response is returned together with a :class:`Source` so tools
can report provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit

import httpx

from polyrea.evidence import Source, utc_now_iso

DEFAULT_CACHE_DIR = Path(os.environ.get("POLYREA_CACHE_DIR", Path.cwd() / ".cache"))

# Requests per second per host. Public endpoints throttle aggressively; these
# rates stay well under the observed limits.
DEFAULT_RATES = {
    "data-api.polymarket.com": 8.0,
    "gamma-api.polymarket.com": 6.0,
    "clob.polymarket.com": 8.0,
    "polygon.drpc.org": 4.0,
    "polygon-bor-rpc.publicnode.com": 4.0,
    "api.exchange.coinbase.com": 3.0,
    "api.kraken.com": 0.6,
    "www.okx.com": 5.0,
}


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} for {url}: {body[:300]}")
        self.status = status
        self.url = url
        self.body = body


class _RateLimiter:
    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_at - now
            self.next_at = max(now, self.next_at) + self.interval
        if delay > 0:
            time.sleep(delay)


class ResponseCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, url TEXT, "
            "fetched_at REAL, status INTEGER, body BLOB)"
        )
        self._db.commit()

    def get(self, key: str, max_age: float | None) -> tuple[float, bytes] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT fetched_at, body FROM responses WHERE key=?", (key,)
            ).fetchone()
        if row is None:
            return None
        fetched_at, blob = row
        if max_age is not None and time.time() - fetched_at > max_age:
            return None
        return fetched_at, zlib.decompress(blob)

    def put(self, key: str, url: str, status: int, body: bytes) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?)",
                (key, url, time.time(), status, zlib.compress(body, 6)),
            )
            self._db.commit()


class HttpClient:
    """Thread-safe JSON client. One instance is shared across adapters."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        rates: dict[str, float] | None = None,
        max_retries: int = 6,
        timeout: float = 45.0,
        offline: bool = False,
    ):
        self.cache = ResponseCache((cache_dir or DEFAULT_CACHE_DIR) / "http.sqlite")
        self.rates = {**DEFAULT_RATES, **(rates or {})}
        self._limiters: dict[str, _RateLimiter] = {}
        self._limiters_lock = threading.Lock()
        self.max_retries = max_retries
        self.offline = offline
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "polyrea/0.1 (research)", "Accept": "application/json"},
            follow_redirects=True,
        )

    def _limiter(self, host: str) -> _RateLimiter:
        with self._limiters_lock:
            if host not in self._limiters:
                self._limiters[host] = _RateLimiter(self.rates.get(host, 4.0))
            return self._limiters[host]

    @staticmethod
    def build_url(base: str, params: dict[str, Any] | list[tuple[str, Any]] | None) -> str:
        """Encode params; a list of pairs allows repeated keys (e.g. condition_ids)."""
        if not params:
            return base
        pairs = params.items() if isinstance(params, dict) else params
        clean = [(k, v) for k, v in pairs if v is not None]
        return f"{base}?{urlencode(clean, doseq=True)}"

    def get_json(
        self,
        base: str,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
        *,
        adapter: str,
        max_age: float | None = 3600.0,
        allow_status: tuple[int, ...] = (),
        cache_if: Callable[[Any], bool] | None = None,
    ) -> tuple[Any, Source]:
        """GET JSON. ``cache_if`` rejects 200 bodies that are really errors.

        A rejected body is neither cached nor returned; it is retried like a
        throttled response, because APIs such as Kraken report rate limits in a
        200 body.
        """
        url = self.build_url(base, params)
        return self._request("GET", url, None, adapter=adapter, max_age=max_age, allow_status=allow_status, cache_if=cache_if)

    def post_json(
        self,
        url: str,
        body: Any,
        *,
        adapter: str,
        max_age: float | None = None,
        max_retries: int | None = None,
    ) -> tuple[Any, Source]:
        return self._request("POST", url, body, adapter=adapter, max_age=max_age, allow_status=(), max_retries=max_retries)

    def _request(
        self,
        method: str,
        url: str,
        body: Any,
        *,
        adapter: str,
        max_age: float | None,
        allow_status: tuple[int, ...],
        max_retries: int | None = None,
        cache_if: Callable[[Any], bool] | None = None,
    ) -> tuple[Any, Source]:
        payload = json.dumps(body, sort_keys=True) if body is not None else ""
        key = hashlib.sha256(f"{method} {url} {payload}".encode()).hexdigest()
        hit = self.cache.get(key, max_age)
        if hit is not None and cache_if is not None and not cache_if(json.loads(hit[1])):
            hit = None  # a previously cached error body is never served
        if hit is not None:
            fetched_at, raw = hit
            return json.loads(raw), Source(
                adapter=adapter,
                url=url,
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(fetched_at)),
                body_sha256=hashlib.sha256(raw).hexdigest(),
                cached=True,
            )
        if self.offline:
            raise HttpError(0, url, "offline mode and no cached response")
        host = urlsplit(url).hostname or ""
        limiter = self._limiter(host)
        last_exc: Exception | None = None
        retries = self.max_retries if max_retries is None else max_retries
        for attempt in range(retries + 1):
            limiter.wait()
            try:
                if method == "GET":
                    resp = self._client.get(url)
                else:
                    resp = self._client.post(url, content=payload, headers={"Content-Type": "application/json"})
            except httpx.HTTPError as exc:  # network level
                last_exc = exc
                time.sleep(min(60.0, 1.5 * 2**attempt + random.random()))
                continue
            if resp.status_code == 200 or resp.status_code in allow_status:
                raw = resp.content
                data = json.loads(raw) if raw else None
                if resp.status_code == 200 and cache_if is not None and not cache_if(data):
                    last_exc = HttpError(200, url, raw[:300].decode(errors="replace"))
                    if attempt < retries:
                        time.sleep(min(60.0, 2.0 * 2**attempt + random.random()))
                    continue
                if resp.status_code == 200:
                    self.cache.put(key, url, resp.status_code, raw)
                return data, Source(
                    adapter=adapter,
                    url=url,
                    fetched_at=utc_now_iso(),
                    body_sha256=hashlib.sha256(raw).hexdigest(),
                    cached=False,
                )
            if resp.status_code in (429, 500, 502, 503, 504, 520, 522, 524):
                retry_after = resp.headers.get("retry-after")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 1.5 * 2**attempt
                if attempt < retries:
                    time.sleep(min(90.0, wait + random.random()))
                last_exc = HttpError(resp.status_code, url, resp.text)
                continue
            raise HttpError(resp.status_code, url, resp.text)
        raise HttpError(-1, url, f"retries exhausted: {last_exc}")


_shared: HttpClient | None = None
_shared_lock = threading.Lock()


def shared_client() -> HttpClient:
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = HttpClient(offline=os.environ.get("POLYREA_OFFLINE") == "1")
        return _shared
