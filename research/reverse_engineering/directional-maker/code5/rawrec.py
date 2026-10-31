"""directional-maker iteration 5: raw-event recorder (unaggregated CLOB events + reference feeds, server stamps).

Files records through tools/live.py Writer (dev/sealed by the receive time's 6-hour block). Feeds (prefix dm_):

* dm_clob_raw: every CLOB market-channel message for the current and next BTC 5m windows and the current BTC 15m
  window, unaggregated. Price changes keep only the market's first token (Up); each change is one order event
  mirrored on the two tokens. Records:
    {"k":"pc","t":recv_ms,"s":server_ms,"w":slug,"c":[[side(1=BUY bid,0=SELL ask), price, size_after, best_bid, best_ask, n_changes_in_msg]...]}
    {"k":"bk","t","s","w","b":[[p,z]..],"o":[[p,z]..]}       full book of the Up token (subscription snapshots)
    {"k":"x","t","s","w","ai":0|1,"p","z","d","h"}            last_trade_price (both tokens kept)
    {"k":"c","t","w","m":raw}                                  anything else (tick-size changes)
* dm_bnf: Binance USD-M futures BTCUSDT aggTrade ["a",T,E,p,q,m] and bookTicker on best-price change ["b",E,T,b,B,a,A]
* dm_bns: Binance spot BTCUSDT aggTrade ["a",T,E,p,q,m] and bookTicker on best-price change ["b",recv,b,B,a,A]
* dm_cb: Coinbase BTC-USD ticker [time_ms, price, last_size, side, best_bid, best_ask]
* dm_okx: OKX BTC-USDT-SWAP trades ["t",ts,px,sz,side] and tickers on change ["k",ts,last,bid,ask]
* dm_byb: Bybit linear BTCUSDT publicTrade ["t",T,p,v,S] and orderbook.1 on change ["b",ts,bid,ask]
* dm_hl: Hyperliquid BTC trades ["t",time,px,sz,side] and bbo ["b",time,bid,ask]
* dm_rtds: Polymarket RTDS raw messages, one connection per topic (btc only), reconnect every 25 s, staggered.

Every record carries "t" = local receive ms (the laptop clock is ~1 s slow: use server stamps for timing).
Hard stop (--until, default 2026-10-31 18:00 UTC, the end of the current development block), disk cap 280 MB for
the dm_ feeds, memory small (no buffering beyond the gzip writer).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code5/rawrec.py --until 1793469600
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import live  # noqa: E402

LIVE = ROOT / ".cache" / "live"
STATUS = ROOT / ".cache" / "re" / "directional-maker" / "rawrec_status.json"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DISK_CAP_MB = 280
STATE: dict = {"feeds": {}}


def st(name):
    return STATE["feeds"].setdefault(name, {"msgs": 0, "written": 0, "reconnects": 0, "err": None})


def now_ms():
    return int(time.time() * 1000)


def dm_disk_mb():
    tot = 0
    for part in ("dev", "sealed"):
        base = LIVE / part
        if base.exists():
            for d in base.glob("dm_*"):
                for p in d.glob("*.gz"):
                    try:
                        tot += p.stat().st_size
                    except OSError:
                        pass
    return tot / 1e6


async def gamma_tokens(slug, cache):
    if slug in cache:
        return cache[slug]
    import httpx

    def go():
        with httpx.Client(timeout=15, headers={"User-Agent": "polyrea-research"}) as c:
            r = c.get("https://gamma-api.polymarket.com/markets", params={"slug": slug})
            r.raise_for_status()
            return r.json()
    try:
        j = await asyncio.to_thread(go)
        toks = json.loads(j[0]["clobTokenIds"]) if j else []
    except Exception:
        return []
    if len(toks) == 2:
        cache[slug] = toks
    return toks


async def clob_market(slug, toks, w, stop, until_ts):
    """One connection per market until until_ts."""
    import websockets
    s = st("dm_clob_raw")
    up = toks[0]
    while not stop.is_set() and time.time() < until_ts:
        try:
            async with websockets.connect(CLOB_WS, open_timeout=15, ping_interval=20, max_size=2**24, max_queue=16384) as ws:
                await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                last_ping = time.time()
                while not stop.is_set() and time.time() < until_ts:
                    if time.time() - last_ping > 10:
                        await ws.send("PING")
                        last_ping = time.time()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    if msg == "PONG":
                        continue
                    t = now_ms()
                    s["msgs"] += 1
                    try:
                        j = json.loads(msg)
                    except ValueError:
                        w.write({"k": "c", "t": t, "w": slug, "m": msg[:1000]})
                        continue
                    for it in (j if isinstance(j, list) else [j]):
                        ev = it.get("event_type")
                        if "price_changes" in it:
                            ch = it["price_changes"]
                            n = len(ch)
                            rows = [[1 if c.get("side") == "BUY" else 0, float(c["price"]), float(c["size"]),
                                     float(c.get("best_bid") or 0), float(c.get("best_ask") or 0), n]
                                    for c in ch if c.get("asset_id") == up]
                            if not rows:  # keep the mirrored token if the first is missing
                                rows = [[2 + (1 if c.get("side") == "BUY" else 0), float(c["price"]), float(c["size"]),
                                         float(c.get("best_bid") or 0), float(c.get("best_ask") or 0), n] for c in ch]
                            w.write({"k": "pc", "t": t, "s": int(it.get("timestamp") or 0), "w": slug, "c": rows})
                            s["written"] += 1
                        elif ev == "book" or ("bids" in it and "asks" in it):
                            if it.get("asset_id") != up:
                                continue
                            w.write({"k": "bk", "t": t, "s": int(it.get("timestamp") or 0), "w": slug,
                                     "b": [[float(x["price"]), float(x["size"])] for x in it.get("bids", [])],
                                     "o": [[float(x["price"]), float(x["size"])] for x in it.get("asks", [])]})
                            s["written"] += 1
                        elif ev == "last_trade_price":
                            w.write({"k": "x", "t": t, "s": int(it.get("timestamp") or 0), "w": slug,
                                     "ai": 0 if it.get("asset_id") == up else 1, "p": float(it.get("price") or 0),
                                     "z": float(it.get("size") or 0), "d": it.get("side"), "h": it.get("transaction_hash")})
                            s["written"] += 1
                        else:
                            w.write({"k": "c", "t": t, "w": slug, "m": json.dumps(it)[:1000]})
        except Exception as e:
            s["err"] = f"{time.strftime('%H:%M:%S')} {slug} {e!r}"[:200]
            s["reconnects"] += 1
            await asyncio.sleep(2)


async def clob_manager(stop, hard_stop):
    w = live.Writer("dm_clob_raw")
    cache: dict = {}
    running: dict[str, asyncio.Task] = {}
    flush_t = time.time()
    while not stop.is_set():
        now = time.time()
        want = []
        b5 = int(now // 300 * 300)
        for k in (0, 1):
            st5 = b5 + 300 * k
            want.append((f"btc-updown-5m-{st5}", st5 + 300 + 20))
        if now - b5 > 240:  # open the window after next 60 s before it starts
            st5 = b5 + 600
            want.append((f"btc-updown-5m-{st5}", st5 + 300 + 20))
        b15 = int(now // 900 * 900)
        want.append((f"btc-updown-15m-{b15}", b15 + 900 + 20))
        for slug, until_ts in want:
            if slug in running and not running[slug].done():
                continue
            if time.time() >= until_ts:
                continue
            toks = await gamma_tokens(slug, cache)
            if len(toks) == 2:
                running[slug] = asyncio.create_task(clob_market(slug, toks, w, stop, min(until_ts, hard_stop)))
        for slug in [s for s, t in running.items() if t.done()]:
            del running[slug]
        if time.time() - flush_t > 3:
            w.flush()
            flush_t = time.time()
        try:
            await asyncio.wait_for(stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass
    for t in running.values():
        t.cancel()
    w.close()


async def ws_feed(name, url, sub_msgs, handler, stop, ping=None):
    import websockets
    w, s = live.Writer(name), st(name)
    state: dict = {}
    while not stop.is_set():
        try:
            async with websockets.connect(url, open_timeout=15, ping_interval=20, max_size=2**24, max_queue=16384) as ws:
                for m in sub_msgs:
                    await ws.send(json.dumps(m))
                last_flush = last_ping = time.time()
                while not stop.is_set():
                    if ping and time.time() - last_ping > 15:
                        await ws.send(ping)
                        last_ping = time.time()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    t = now_ms()
                    s["msgs"] += 1
                    try:
                        for rec in handler(msg, t, state):
                            w.write(rec)
                            s["written"] += 1
                    except Exception as e:  # malformed message: keep going
                        s["err"] = f"parse {e!r}"[:200]
                    if time.time() - last_flush > 3:
                        w.flush()
                        last_flush = time.time()
        except Exception as e:
            s["err"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
            s["reconnects"] += 1
            await asyncio.sleep(3)
    w.close()


def h_binance(spot):
    def h(msg, t, state):
        j = json.loads(msg)
        d = j.get("data", j)
        e = d.get("e")
        if e == "aggTrade":
            yield {"t": t, "r": ["a", d["T"], d["E"], float(d["p"]), float(d["q"]), 1 if d["m"] else 0]}
        elif e == "bookTicker" or ("b" in d and "a" in d and "B" in d):
            key = (d["b"], d["a"]) if spot else (d["b"], d["a"], d["B"], d["A"])  # futures: every size change (microprice)
            if state.get("bt") != key:
                state["bt"] = key
                if spot:
                    yield {"t": t, "r": ["b", t, float(d["b"]), float(d["B"]), float(d["a"]), float(d["A"])]}
                else:
                    yield {"t": t, "r": ["b", d.get("E"), d.get("T"), float(d["b"]), float(d["B"]), float(d["a"]), float(d["A"])]}
    return h


def iso_ms(s):
    # 2026-10-31T14:05:01.123456Z
    s = s.rstrip("Z")
    if "." in s:
        a, b = s.split(".")
        s = a + "." + (b + "000000")[:6]
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    return int((dt - datetime(1970, 1, 1)).total_seconds() * 1000)


def h_coinbase(msg, t, state):
    d = json.loads(msg)
    if d.get("type") == "ticker":
        yield {"t": t, "r": [iso_ms(d["time"]), float(d["price"]), float(d.get("last_size") or 0), d.get("side"),
                             float(d.get("best_bid") or 0), float(d.get("best_ask") or 0)]}


def h_okx(msg, t, state):
    if msg == "pong":
        return
    d = json.loads(msg)
    ch = d.get("arg", {}).get("channel")
    for x in d.get("data", []) or []:
        if ch == "trades":
            yield {"t": t, "r": ["t", int(x["ts"]), float(x["px"]), float(x["sz"]), x["side"]]}
        elif ch == "tickers":
            key = (x.get("bidPx"), x.get("askPx"), x.get("last"))
            if state.get("k") != key:
                state["k"] = key
                yield {"t": t, "r": ["k", int(x["ts"]), float(x["last"]), float(x["bidPx"]), float(x["askPx"])]}


def h_bybit(msg, t, state):
    d = json.loads(msg)
    topic = d.get("topic", "")
    if topic.startswith("publicTrade"):
        for x in d.get("data", []):
            yield {"t": t, "r": ["t", int(x["T"]), float(x["p"]), float(x["v"]), x["S"]]}
    elif topic.startswith("orderbook.1"):
        x = d.get("data", {})
        b = x.get("b") or []
        a = x.get("a") or []
        bid = float(b[0][0]) if b else state.get("bid")
        ask = float(a[0][0]) if a else state.get("ask")
        if (bid, ask) != (state.get("bid"), state.get("ask")):
            state["bid"], state["ask"] = bid, ask
            yield {"t": t, "r": ["b", int(d.get("ts") or 0), bid, ask]}


def h_hl(msg, t, state):
    d = json.loads(msg)
    ch = d.get("channel")
    if ch == "trades":
        for x in d.get("data", []):
            yield {"t": t, "r": ["t", int(x["time"]), float(x["px"]), float(x["sz"]), x["side"]]}
    elif ch == "bbo":
        x = d.get("data", {})
        bbo = x.get("bbo") or [None, None]
        bid = float(bbo[0]["px"]) if bbo[0] else None
        ask = float(bbo[1]["px"]) if bbo[1] else None
        if (bid, ask) != (state.get("bid"), state.get("ask")):
            state["bid"], state["ask"] = bid, ask
            yield {"t": t, "r": ["b", int(x.get("time") or 0), bid, ask]}


async def rtds_conn(topic, offset, w, stop):
    import websockets
    s = st("dm_rtds")
    sub = {"action": "subscribe", "subscriptions": [{"topic": topic, "type": "*", "filters": json.dumps({"symbol": "btc/usd"})}]}
    await asyncio.sleep(offset)
    while not stop.is_set():
        t0 = time.time()
        try:
            async with websockets.connect("wss://ws-live-data.polymarket.com", open_timeout=15, ping_interval=20, max_size=2**24) as ws:
                await ws.send(json.dumps(sub))
                while not stop.is_set() and time.time() - t0 < 25:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    except asyncio.TimeoutError:
                        continue
                    if msg and msg != "PONG":
                        w.write({"t": now_ms(), "q": topic, "m": msg})
                        s["msgs"] += 1
                        s["written"] += 1
        except Exception as e:
            s["err"] = f"{time.strftime('%H:%M:%S')} {topic} {e!r}"[:200]
            s["reconnects"] += 1
        w.flush()
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(0.5, 25 - (time.time() - t0)))
        except asyncio.TimeoutError:
            pass


async def rtds_feed(stop):
    w = live.Writer("dm_rtds")
    await asyncio.gather(rtds_conn("crypto_prices_chainlink", 0, w, stop), rtds_conn("crypto_prices_twap_sixty", 12, w, stop),
                         rtds_conn("crypto_prices", 6, w, stop))
    w.close()


async def supervisor(stop, hard_stop):
    while not stop.is_set():
        mb = dm_disk_mb()
        if mb > DISK_CAP_MB or time.time() >= hard_stop:
            stop.set()
        STATE.update({"pid": os.getpid(), "updated": int(time.time()), "disk_mb": round(mb, 1), "hard_stop": int(hard_stop)})
        STATUS.write_text(json.dumps(STATE, indent=1), encoding="utf-8")
        try:
            await asyncio.wait_for(stop.wait(), timeout=20)
        except asyncio.TimeoutError:
            pass
    STATE.update({"updated": int(time.time()), "stopped": True})
    STATUS.write_text(json.dumps(STATE, indent=1), encoding="utf-8")


async def main(until):
    stop = asyncio.Event()
    STATE["started"] = int(time.time())
    await asyncio.gather(
        supervisor(stop, until),
        clob_manager(stop, until),
        ws_feed("dm_bnf", "wss://fstream.binance.com/stream?streams=btcusdt@aggTrade/btcusdt@bookTicker", [], h_binance(False), stop),
        # since the 2025-26 endpoint split, futures aggTrade is served only under /market
        ws_feed("dm_bnfa", "wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade", [], h_binance(False), stop),
        ws_feed("dm_bns", "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/btcusdt@bookTicker", [], h_binance(True), stop),
        ws_feed("dm_cb", "wss://ws-feed.exchange.coinbase.com", [{"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["ticker"]}], h_coinbase, stop),
        ws_feed("dm_okx", "wss://ws.okx.com:8443/ws/v5/public", [{"op": "subscribe", "args": [{"channel": "trades", "instId": "BTC-USDT-SWAP"},
                                                                                              {"channel": "tickers", "instId": "BTC-USDT-SWAP"}]}], h_okx, stop, ping="ping"),
        ws_feed("dm_byb", "wss://stream.bybit.com/v5/public/linear", [{"op": "subscribe", "args": ["publicTrade.BTCUSDT", "orderbook.1.BTCUSDT"]}], h_bybit, stop,
                ping=json.dumps({"op": "ping"})),
        ws_feed("dm_hl", "wss://api.hyperliquid.xyz/ws", [{"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}},
                                                         {"method": "subscribe", "subscription": {"type": "bbo", "coin": "BTC"}}], h_hl, stop),
        rtds_feed(stop),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=float, default=1793469600)  # 2026-10-31 18:00 UTC
    a = ap.parse_args()
    asyncio.run(main(a.until))
