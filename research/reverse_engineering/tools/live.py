"""Shared live recorder for the deep reverse engineering, and a reader that respects the sealed calendar.

One recorder process serves every strategy. It records, by receive time:

* ``clob_crypto``: CLOB order books of the BTC, ETH and SOL Up/Down 5m, 15m and 4h windows (current and
  next);
* ``clob_wallets``: CLOB order books of the markets the studied sports, esports and event wallets traded in
  the last 6 hours (found by polling their public trades every 3 minutes);
* ``rtds``: Polymarket's real-time data socket, Chainlink prices and the Chainlink 60-s TWAP (the BTC
  Up/Down settlement source) for btc, eth and sol. The socket only sends a 60-second snapshot after each
  subscription, so the recorder reconnects every 50 s; dedupe on (topic symbol, timestamp);
* ``sports``: Polymarket's public sports websocket (live scores, periods, CS2 and Valorant maps), raw;
* ``subs``: which markets and tokens were subscribed when.

Book records (one JSON object per line). Every price change arrives mirrored on the market's two tokens,
so only the first token of each market (Up / Yes) is kept; the other side's book is 1 - price with sides
swapped.

* ``{"k": "q", "t": recv_ms, "s": server_ms, "a": token, "b": [[price, size], ...], "o": [[price, size], ...]}``:
  top 10 bid and ask levels, written at most every 200 ms per token while the book changes;
* ``{"k": "f", ...}``: the same with every level, every 30 s and after each (re)subscription;
* ``{"k": "x", "t", "s", "a", "p", "z": size, "d": side, "h": tx hash, "fr": fee rate bps}``: each last trade;
* ``{"k": "c", "t", "m": raw}``: tick-size changes and anything unrecognised.

Files: ``.cache/live/<dev|sealed>/<feed>/<YYYYmmddTHH>.jsonl.gz``. The 6-hour block of the calendar in
``tools/sealed.py`` that contains the receive time decides dev or sealed. Agents read only the dev folder
(``iter_live``); examiners pass ``allow_sealed=True``.

Run it detached; it stops by itself after ``--hours``::

    .venv/Scripts/python.exe research/reverse_engineering/tools/live.py record --hours 120
    .venv/Scripts/python.exe research/reverse_engineering/tools/live.py status
"""
from __future__ import annotations

import argparse
import asyncio
import calendar
import gzip
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sealed  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / ".cache" / "live"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
RTDS_WS = "wss://ws-live-data.polymarket.com"
SPORTS_WS = "wss://sports-api.polymarket.com/ws"
GAMMA = "https://gamma-api.polymarket.com/markets"
DATA_TRADES = "https://data-api.polymarket.com/trades"
COINS = ("btc", "eth", "sol")
WINDOWS = (("5m", 300, 2), ("15m", 900, 2), ("4h", 14400, 2))  # (tag, seconds, windows from the current one)
WALLETS = {  # the studied wallets that trade sports, esports or event markets
    "jld-inplay-taker": "0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705",
    "dbdd-inplay-taker": "0xdbdd45150249e229eb4ca8aa48a30dca21faa5de",
    "rn1-inplay-maker": "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
    "tommy-cs2-maker": "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2",
    "elmcap2-carry": "0xed107a85a4585a381e48c7f7ca4144909e7dd2e5",
}
MAX_WALLET_MARKETS = 200
TOP, THROTTLE_MS, FULL_EVERY = 10, 200, 30
DISK_SOFT_MB, DISK_HARD_MB = 3000, 4000


class Writer:
    """Hourly gzip JSONL files, split into dev and sealed folders by the receive time's calendar block."""

    def __init__(self, feed: str):
        self.feed, self.path, self.fh, self.n = feed, None, None, 0

    def write(self, obj: dict | str) -> None:
        now = time.time()
        part = "sealed" if sealed.future_block_sealed(now) else "dev"
        path = LIVE / part / self.feed / (time.strftime("%Y%m%dT%H", time.gmtime(now)) + ".jsonl.gz")
        if path != self.path:
            self.close()
            path.parent.mkdir(parents=True, exist_ok=True)
            self.fh, self.path = gzip.open(path, "at", encoding="utf-8", compresslevel=6), path
        self.fh.write((obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":"))) + "\n")
        self.n += 1

    def flush(self) -> None:
        if self.fh:
            self.fh.flush()

    def close(self) -> None:
        if self.fh:
            self.fh.close()
        self.fh, self.path = None, None


STATE: dict = {"feeds": {}}


def _feed_state(name: str) -> dict:
    return STATE["feeds"].setdefault(name, {"connected": False, "msgs": 0, "written": 0, "reconnects": 0, "tokens": 0, "last_error": None})


def _err(st: dict, where: str, e: BaseException) -> None:
    st["last_error"] = f"{time.strftime('%H:%M:%S')} {where} {e!r}"[:240]


async def _http_json(url: str, params: dict) -> object:
    import httpx

    def go():
        with httpx.Client(timeout=20, headers={"User-Agent": "polyrea-research"}) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r.json()
    return await asyncio.to_thread(go)


TOKENS_BY_SLUG: dict[str, list[str]] = {}
TOKENS_BY_CID: dict[str, list[str]] = {}


async def crypto_markets() -> dict[str, list[str]]:
    """market slug -> its two token ids, for the current and next Up/Down windows."""
    now = int(time.time())
    out = {}
    for coin in COINS:
        for tag, sec, ahead in WINDOWS:
            for k in range(ahead):
                slug = f"{coin}-updown-{tag}-{now // sec * sec + k * sec}"
                if slug not in TOKENS_BY_SLUG:
                    try:
                        j = await _http_json(GAMMA, {"slug": slug})
                        TOKENS_BY_SLUG[slug] = json.loads(j[0]["clobTokenIds"]) if j else []
                    except Exception:
                        continue
                if len(TOKENS_BY_SLUG[slug]) == 2:
                    out[slug] = TOKENS_BY_SLUG[slug]
    return out


async def wallet_markets() -> dict[str, list[str]]:
    """condition id -> its token ids, for the markets the studied wallets traded in the last 6 hours."""
    since = time.time() - 6 * 3600
    recent: dict[str, float] = {}
    for w in WALLETS.values():
        try:
            rows = await _http_json(DATA_TRADES, {"user": w, "limit": 200})
        except Exception:
            continue
        for r in rows or []:
            ts, cid = float(r.get("timestamp") or 0), r.get("conditionId")
            if cid and ts >= since:
                recent[cid] = max(recent.get(cid, 0), ts)
        await asyncio.sleep(1)
    out = {}
    for cid in sorted(recent, key=recent.get, reverse=True)[:MAX_WALLET_MARKETS]:
        if cid not in TOKENS_BY_CID:
            try:
                j = await _http_json(GAMMA, {"condition_ids": cid})
                TOKENS_BY_CID[cid] = json.loads(j[0]["clobTokenIds"]) if j else []
            except Exception:
                continue
        if len(TOKENS_BY_CID[cid]) == 2:
            out[cid] = TOKENS_BY_CID[cid]
    return out


class Books:
    """Order books of the first token of each market, from snapshots and (mirrored) price changes."""

    def __init__(self, w: Writer, st: dict):
        self.w, self.st = w, st
        self.keep: set[str] = set()
        self.bids: dict[str, dict[float, float]] = {}
        self.asks: dict[str, dict[float, float]] = {}
        self.dirty: dict[str, int] = {}
        self.last_write: dict[str, int] = {}
        self.server_ts: dict[str, int] = {}

    def set_markets(self, markets: dict[str, list[str]]) -> None:
        self.keep = {toks[0] for toks in markets.values()}
        for d in (self.bids, self.asks, self.dirty, self.last_write, self.server_ts):
            for a in [a for a in d if a not in self.keep]:
                del d[a]

    def _levels(self, a: str, n: int | None) -> tuple[list, list]:
        b = sorted(self.bids.get(a, {}).items(), reverse=True)
        o = sorted(self.asks.get(a, {}).items())
        return [list(x) for x in b[:n]], [list(x) for x in o[:n]]

    def snapshot(self, a: str, kind: str, now_ms: int) -> None:
        b, o = self._levels(a, TOP if kind == "q" else None)
        self.w.write({"k": kind, "t": now_ms, "s": self.server_ts.get(a), "a": a, "b": b, "o": o})
        self.st["written"] += 1
        self.last_write[a] = now_ms
        self.dirty.pop(a, None)

    def on_message(self, raw: str) -> None:
        now_ms = int(time.time() * 1000)
        try:
            j = json.loads(raw)
        except ValueError:
            self.w.write({"k": "c", "t": now_ms, "m": raw[:2000]})
            return
        for it in (j if isinstance(j, list) else [j]):
            ev = it.get("event_type")
            if ev == "book" or ("bids" in it and "asks" in it):
                a = it.get("asset_id")
                if a not in self.keep:
                    continue
                self.bids[a] = {float(x["price"]): float(x["size"]) for x in it.get("bids", [])}
                self.asks[a] = {float(x["price"]): float(x["size"]) for x in it.get("asks", [])}
                self.server_ts[a] = int(it.get("timestamp") or 0)
                self.snapshot(a, "f", now_ms)
            elif "price_changes" in it:
                s = int(it.get("timestamp") or 0)
                for ch in it["price_changes"]:
                    a = ch.get("asset_id")
                    if a not in self.keep:
                        continue
                    side = self.bids if ch.get("side") == "BUY" else self.asks
                    book = side.setdefault(a, {})
                    p, z = float(ch["price"]), float(ch["size"])
                    if z == 0:
                        book.pop(p, None)
                    else:
                        book[p] = z
                    self.server_ts[a] = s
                    self.dirty[a] = now_ms
            elif ev == "last_trade_price":
                self.w.write({"k": "x", "t": now_ms, "s": int(it.get("timestamp") or 0), "a": it.get("asset_id"), "p": float(it.get("price") or 0),
                              "z": float(it.get("size") or 0), "d": it.get("side"), "h": it.get("transaction_hash"), "fr": it.get("fee_rate_bps")})
                self.st["written"] += 1
            else:
                self.w.write({"k": "c", "t": now_ms, "m": json.dumps(it)[:2000]})

    def tick(self, full: bool) -> None:
        now_ms = int(time.time() * 1000)
        if full:
            for a in list(self.keep):
                if a in self.bids or a in self.asks:
                    self.snapshot(a, "f", now_ms)
            return
        for a in list(self.dirty):
            if now_ms - self.last_write.get(a, 0) >= THROTTLE_MS:
                self.snapshot(a, "q", now_ms)


async def _recv(ws, stop: asyncio.Event, timeout: float = 5.0):
    """ws.recv() that wakes up every few seconds to notice a stop."""
    while not stop.is_set():
        try:
            return await asyncio.wait_for(ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            continue
    return None


async def clob_feed(name: str, pick, refresh: float, subs: Writer, stop: asyncio.Event) -> None:
    """Books for a set of markets; the connection is replaced (with overlap) whenever the set changes."""
    import websockets

    w, st = Writer(name), _feed_state(name)
    books = Books(w, st)
    gen_box = {"gen": 0}

    async def run(tokens: list[str], ready: asyncio.Event, gen: int) -> None:
        while not stop.is_set() and gen_box["gen"] == gen:
            try:
                # A large queue: with the library's default of 16, bursts stall reads and the server drops a slow consumer.
                async with websockets.connect(CLOB_WS, open_timeout=15, ping_interval=20, max_size=2**24, max_queue=8192) as ws:
                    await ws.send(json.dumps({"assets_ids": tokens, "type": "market"}))
                    st["connected"] = True
                    last_ping = time.time()
                    while not stop.is_set() and gen_box["gen"] == gen:
                        if time.time() - last_ping > 10:
                            await ws.send("PING")
                            last_ping = time.time()
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        if msg == "PONG":
                            continue
                        ready.set()
                        st["msgs"] += 1
                        books.on_message(msg)
            except Exception as e:  # reconnect after any network error
                _err(st, "ws", e)
            st["connected"] = False
            if stop.is_set() or gen_box["gen"] != gen:
                return
            st["reconnects"] += 1
            await asyncio.sleep(3)

    async def ticker() -> None:
        n = 0
        while not stop.is_set():
            await asyncio.sleep(THROTTLE_MS / 1000)
            n += 1
            books.tick(full=(n % int(FULL_EVERY * 1000 / THROTTLE_MS) == 0))
            if n % 25 == 0:
                w.flush()

    tick_task = asyncio.create_task(ticker())
    current: dict[str, list[str]] = {}
    conn: asyncio.Task | None = None
    while not stop.is_set():
        try:
            new = await pick()
        except Exception as e:
            _err(st, "pick", e)
            new = current
        if new and set(new) != set(current):
            gen_box["gen"] += 1
            ready, old = asyncio.Event(), conn
            books.set_markets({**current, **new})
            conn = asyncio.create_task(run(sorted({t for toks in new.values() for t in toks}), ready, gen_box["gen"]))
            try:
                await asyncio.wait_for(ready.wait(), timeout=20)
            except asyncio.TimeoutError:
                pass
            if old:
                old.cancel()
            books.set_markets(new)
            current = new
            st["tokens"] = sum(len(v) for v in new.values())
            subs.write({"t": int(time.time() * 1000), "feed": name, "markets": new})
            subs.flush()
        try:
            await asyncio.wait_for(stop.wait(), timeout=refresh)
        except asyncio.TimeoutError:
            pass
    for t in (conn, tick_task):
        if t:
            t.cancel()
    w.close()


async def rtds_feed(stop: asyncio.Event) -> None:
    """Reconnect every 50 s: each subscription returns the last 60 one-second values."""
    import websockets

    w, st = Writer("rtds"), _feed_state("rtds")
    sub = {"action": "subscribe", "subscriptions": [
        {"topic": topic, "type": "*", "filters": json.dumps({"symbol": f"{c}/usd"})}
        for topic in ("crypto_prices_chainlink", "crypto_prices_twap_sixty") for c in COINS]}
    while not stop.is_set():
        t0 = time.time()
        try:
            async with websockets.connect(RTDS_WS, open_timeout=15, ping_interval=20, max_size=2**24) as ws:
                await ws.send(json.dumps(sub))
                st["connected"] = True
                while not stop.is_set() and time.time() - t0 < 50:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    if msg and msg != "PONG":
                        w.write({"t": int(time.time() * 1000), "m": msg})
                        st["msgs"] += 1
        except Exception as e:
            _err(st, "ws", e)
            st["reconnects"] += 1
        st["connected"] = False
        w.flush()
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(1.0, 50 - (time.time() - t0)))
        except asyncio.TimeoutError:
            pass
    w.close()


async def sports_feed(stop: asyncio.Event) -> None:
    import websockets

    w, st = Writer("sports"), _feed_state("sports")
    while not stop.is_set():
        try:
            async with websockets.connect(SPORTS_WS, open_timeout=15, ping_interval=20, max_size=2**24) as ws:
                st["connected"] = True
                n = 0
                while not stop.is_set():
                    msg = await _recv(ws, stop)
                    if msg is None:
                        break
                    if msg and msg != "PONG":
                        w.write({"t": int(time.time() * 1000), "m": msg if isinstance(msg, str) else msg.decode("utf-8", "replace")})
                        st["msgs"] += 1
                        n += 1
                        if n % 50 == 0:
                            w.flush()
        except Exception as e:
            _err(st, "ws", e)
        st["connected"] = False
        if not stop.is_set():
            st["reconnects"] += 1
            await asyncio.sleep(3)
    w.close()


def disk_mb() -> float:
    return sum(p.stat().st_size for p in LIVE.rglob("*.gz")) / 1e6 if LIVE.exists() else 0.0


async def supervisor(stop: asyncio.Event, hard_stop: float, wallet_stop: asyncio.Event) -> None:
    while not stop.is_set():
        mb = disk_mb()
        if mb > DISK_SOFT_MB:
            wallet_stop.set()
        if mb > DISK_HARD_MB or time.time() >= hard_stop:
            stop.set()
        STATE.update({"pid": os.getpid(), "updated": int(time.time()), "disk_mb": round(mb, 1), "hard_stop": int(hard_stop),
                      "current_block": "sealed" if sealed.future_block_sealed(time.time()) else "dev", "wallet_feed_stopped": wallet_stop.is_set()})
        (LIVE / "status.json").write_text(json.dumps(STATE, indent=1), encoding="utf-8")
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass
    STATE.update({"updated": int(time.time()), "stopped": True})
    (LIVE / "status.json").write_text(json.dumps(STATE, indent=1), encoding="utf-8")


async def record(hours: float) -> None:
    LIVE.mkdir(parents=True, exist_ok=True)
    (LIVE / "recorder.pid").write_text(str(os.getpid()), encoding="utf-8")
    stop, wallet_stop = asyncio.Event(), asyncio.Event()
    hard_stop = time.time() + hours * 3600
    STATE.update({"started": int(time.time())})
    subs = Writer("subs")

    async def wallets() -> None:
        both = asyncio.Event()

        async def watch():
            while not (stop.is_set() or wallet_stop.is_set()):
                await asyncio.sleep(5)
            both.set()
        wt = asyncio.create_task(watch())
        await clob_feed("clob_wallets", wallet_markets, 180, subs, both)
        wt.cancel()

    await asyncio.gather(
        supervisor(stop, hard_stop, wallet_stop),
        clob_feed("clob_crypto", crypto_markets, 30, subs, stop),
        wallets(),
        rtds_feed(stop),
        sports_feed(stop),
    )
    subs.close()


def iter_live(feed: str, start: float, end: float, allow_sealed: bool = False):
    """Yield parsed records with receive time in [start, end). Agents get development blocks only;
    pass allow_sealed=True only as an examiner. A file cut off by a crash is read up to its last flush."""
    parts = ["dev", "sealed"] if allow_sealed else ["dev"]
    files = [p for part in parts for p in (LIVE / part / feed).glob("*.jsonl.gz")]
    for p in sorted(files, key=lambda p: p.name):
        hour = calendar.timegm(time.strptime(p.name[:11], "%Y%m%dT%H"))
        if hour + 3600 <= start or hour >= end:
            continue
        fh = gzip.open(p, "rt", encoding="utf-8")
        try:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if start * 1000 <= r["t"] < end * 1000:
                    yield r
        except (EOFError, OSError):
            pass
        finally:
            fh.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Shared live recorder")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("record")
    r.add_argument("--hours", type=float, default=120)
    sp.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "record":
        asyncio.run(record(a.hours))
    else:
        p = LIVE / "status.json"
        print(p.read_text(encoding="utf-8") if p.exists() else "no status yet")


if __name__ == "__main__":
    main()
