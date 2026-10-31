"""directional-maker iteration 6: slim exam recorder (panel iter5 information I4 / mechanics critique 5).

Purpose: record, through the future sealed blocks, the inputs a quote-level or match-clock rule needs, so that the
examiner can score such a rule on sealed blocks. Files records through tools/live.py Writer (dev/sealed by the receive
time's 6-hour block, like every recorder); agents read only dev blocks (code5/rawread.iter_dm with ALLOW_SEALED False).

Feeds (prefix dx_):
* dx_clob: CLOB market channel of the current and next BTC 5m windows and the current BTC 15m window, reduced:
    {"k":"pc","s":server_ms,"t":recv_ms,"w":slug,"bb":best_bid,"ba":best_ask,"c":[[side,p,size_after,delta],...]}
      kept rows: changes within BAND (0.031) of the touch whose size delta is one of the schedule sizes (5, 12, 50, 62,
      100, 125, 250, 500, 1000, 2000), plus the size at the touch (queue) when the touch moves and at most every
      AT_EVERY_MS (200 ms) per side otherwise;
      a record is written when it keeps a row or when the touch changed.
    {"k":"bk","s","t","w","b":[[p,z]..],"o":[[p,z]..]} book of the Up token, levels within BAND_BK (0.031) of the touch,
      at most one every BK_EVERY (5 s) per market (all snapshots still reset the level sizes in memory)
    {"k":"x","s","t","w","ai","p","z","d","h"} every last_trade_price (both tokens), with the tx hash
    {"k":"c","t","w","m"} tick-size changes / other
* dx_bnf: Binance USD-M futures BTCUSDT bookTicker on best-price change ["b",E,T,bid,bidqty,ask,askqty] and aggTrade
  ["a",T,E,p,q,m] (aggTrade from the /market path, which is the only one that serves it now).
* dx_rtds: Polymarket RTDS raw, crypto_prices_chainlink and crypto_prices_twap_sixty (btc), one connection per topic
  reconnected every 25 s, staggered.
* dx_drb: Deribit public ws: deribit_price_index.btc_usd and ticker.BTC-PERPETUAL.100ms (mark, index, best bid/ask,
  last), raw JSON 'params.data' with the server timestamp.
* dx_bst: Bitstamp live_trades_btcusd [microtimestamp_us, price, amount, type].

Hard stop --until (default 2026-11-02 00:00 UTC), disk cap 280 MB over dx_* (dev + sealed), memory: one level dict
per market, no buffering beyond the gzip writers.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code6/examrec.py --until 1793577600
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import live  # noqa: E402

LIVE = ROOT / ".cache" / "live"
STATUS = ROOT / ".cache" / "re" / "directional-maker" / "examrec_status.json"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DISK_CAP_MB = 280
BAND, BAND_BK, BK_EVERY, AT_EVERY_MS = 0.031, 0.031, 5.0, 200
SCHED = {5.0, 12.0, 50.0, 62.0, 100.0, 125.0, 250.0, 500.0, 1000.0, 2000.0}
STATE: dict = {"feeds": {}}


def st(name):
    return STATE["feeds"].setdefault(name, {"msgs": 0, "written": 0, "reconnects": 0, "err": None})


def now_ms():
    return int(time.time() * 1000)


def dx_disk_mb():
    tot = 0
    for part in ("dev", "sealed"):
        base = LIVE / part
        if base.exists():
            for d in base.glob("dx_*"):
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
    import websockets
    s = st("dx_clob")
    up = toks[0]
    while not stop.is_set() and time.time() < until_ts:
        levels: dict = {}
        touch = [None, None]
        last_bk = [0.0]
        last_at = [0, 0]
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
                        continue
                    for it in (j if isinstance(j, list) else [j]):
                        ev = it.get("event_type")
                        if "price_changes" in it:
                            rows, bb, ba = [], None, None
                            for c in it["price_changes"]:
                                if c.get("asset_id") != up:
                                    continue
                                side = 1 if c.get("side") == "BUY" else 0
                                p, z = float(c["price"]), float(c["size"])
                                bb, ba = float(c.get("best_bid") or 0), float(c.get("best_ask") or 0)
                                prev = levels.get((side, p), 0.0)
                                levels[(side, p)] = z
                                d = round(z - prev, 4)
                                at = (side == 1 and abs(p - bb) < 1e-9) or (side == 0 and abs(p - ba) < 1e-9)
                                near = (side == 1 and p >= bb - BAND) or (side == 0 and p <= ba + BAND)
                                if near and abs(d) in SCHED:
                                    rows.append([side, p, z, d])
                                elif at and ([bb, ba] != touch or t - last_at[side] >= AT_EVERY_MS):
                                    rows.append([side, p, z, d])  # queue size at the touch, sampled
                                    last_at[side] = t
                            if bb is None:
                                continue
                            if rows or [bb, ba] != touch:
                                touch = [bb, ba]
                                w.write({"k": "pc", "s": int(it.get("timestamp") or 0), "t": t, "w": slug, "bb": bb, "ba": ba, "c": rows})
                                s["written"] += 1
                        elif ev == "book" or ("bids" in it and "asks" in it):
                            if it.get("asset_id") != up:
                                continue
                            if time.time() - last_bk[0] < BK_EVERY:
                                bids = [[float(x["price"]), float(x["size"])] for x in it.get("bids", [])]
                                asks = [[float(x["price"]), float(x["size"])] for x in it.get("asks", [])]
                                levels = {(1, p): z for p, z in bids}
                                levels.update({(0, p): z for p, z in asks})
                                continue
                            last_bk[0] = time.time()
                            bids = [[float(x["price"]), float(x["size"])] for x in it.get("bids", [])]
                            asks = [[float(x["price"]), float(x["size"])] for x in it.get("asks", [])]
                            levels = {(1, p): z for p, z in bids}
                            levels.update({(0, p): z for p, z in asks})
                            bbk = max((p for p, z in bids), default=0.0)
                            bak = min((p for p, z in asks), default=1.0)
                            w.write({"k": "bk", "s": int(it.get("timestamp") or 0), "t": t, "w": slug,
                                     "b": [x for x in bids if x[0] >= bbk - BAND_BK], "o": [x for x in asks if x[0] <= bak + BAND_BK]})
                            s["written"] += 1
                        elif ev == "last_trade_price":
                            w.write({"k": "x", "s": int(it.get("timestamp") or 0), "t": t, "w": slug,
                                     "ai": 0 if it.get("asset_id") == up else 1, "p": float(it.get("price") or 0),
                                     "z": float(it.get("size") or 0), "d": it.get("side"), "h": it.get("transaction_hash")})
                            s["written"] += 1
                        elif ev in ("tick_size_change",):
                            w.write({"k": "c", "t": t, "w": slug, "m": json.dumps(it)[:500]})
        except Exception as e:
            s["err"] = f"{time.strftime('%H:%M:%S')} {slug} {e!r}"[:200]
            s["reconnects"] += 1
            await asyncio.sleep(2)


async def clob_manager(stop, hard_stop):
    w = live.Writer("dx_clob")
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
        if now - b5 > 240:
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
        if len(cache) > 50:
            for k in list(cache)[:-20]:
                del cache[k]
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


async def ws_feed(name, url, sub_msgs, handler, stop, ping=None, writer=None):
    import websockets
    w, s = writer or live.Writer(name), st(name)
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
                    except Exception as e:
                        s["err"] = f"parse {e!r}"[:200]
                    if time.time() - last_flush > 3:
                        w.flush()
                        last_flush = time.time()
        except Exception as e:
            s["err"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
            s["reconnects"] += 1
            await asyncio.sleep(3)
    if writer is None:
        w.close()


def h_bnf(msg, t, state):
    j = json.loads(msg)
    d = j.get("data", j)
    e = d.get("e")
    if e == "aggTrade":
        yield {"t": t, "r": ["a", d["T"], d["E"], float(d["p"]), float(d["q"]), 1 if d["m"] else 0]}
    elif e == "bookTicker" or ("b" in d and "a" in d and "B" in d):
        key = (d["b"], d["a"])  # best-price changes only (slim)
        if state.get("bt") != key:
            state["bt"] = key
            yield {"t": t, "r": ["b", d.get("E"), d.get("T"), float(d["b"]), float(d["B"]), float(d["a"]), float(d["A"])]}


def h_drb(msg, t, state):
    d = json.loads(msg)
    p = d.get("params") or {}
    ch, x = p.get("channel"), p.get("data")
    if not ch or x is None:
        return
    if ch.startswith("deribit_price_index"):
        yield {"t": t, "r": ["i", x.get("timestamp"), x.get("price")]}
    elif ch.startswith("ticker"):
        key = (x.get("best_bid_price"), x.get("best_ask_price"), x.get("mark_price"))
        if state.get("k") != key:
            state["k"] = key
            yield {"t": t, "r": ["k", x.get("timestamp"), x.get("best_bid_price"), x.get("best_ask_price"), x.get("mark_price"),
                                 x.get("index_price"), x.get("last_price")]}


def h_bst(msg, t, state):
    d = json.loads(msg)
    if d.get("event") == "trade":
        x = d.get("data", {})
        yield {"t": t, "r": [int(x.get("microtimestamp") or 0), float(x.get("price") or 0), float(x.get("amount") or 0), x.get("type")]}


async def rtds_conn(topic, offset, w, stop):
    import websockets
    s = st("dx_rtds")
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
    w = live.Writer("dx_rtds")
    await asyncio.gather(rtds_conn("crypto_prices_chainlink", 0, w, stop), rtds_conn("crypto_prices_twap_sixty", 12, w, stop))
    w.close()


async def supervisor(stop, hard_stop):
    while not stop.is_set():
        mb = dx_disk_mb()
        if mb > DISK_CAP_MB or time.time() >= hard_stop:
            STATE["stop_reason"] = "disk" if mb > DISK_CAP_MB else "hard_stop"
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
    drb_sub = [{"jsonrpc": "2.0", "id": 1, "method": "public/subscribe",
                "params": {"channels": ["deribit_price_index.btc_usd", "ticker.BTC-PERPETUAL.100ms"]}}]
    await asyncio.gather(
        supervisor(stop, until),
        clob_manager(stop, until),
        ws_feed("dx_bnf", "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker", [], h_bnf, stop),
        ws_feed("dx_bnfa", "wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade", [], h_bnf, stop),
        ws_feed("dx_drb", "wss://www.deribit.com/ws/api/v2", drb_sub, h_drb, stop,
                ping=json.dumps({"jsonrpc": "2.0", "id": 9, "method": "public/test", "params": {}})),
        ws_feed("dx_bst", "wss://ws.bitstamp.net", [{"event": "bts:subscribe", "data": {"channel": "live_trades_btcusd"}}], h_bst, stop),
        rtds_feed(stop),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=float, default=1793577600)  # 2026-11-02 00:00 UTC
    a = ap.parse_args()
    asyncio.run(main(a.until))
