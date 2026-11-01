"""Iteration 11 recorder (btc5m-bot's own; panel iter10 information P1 = X87 London-arrival clock / venues never recorded,
information P2 = X88 alt-perp basket, assumptions P1 step 4 = X96 snapshot / conflated streams).

Feeds, all through tools/live.py Writer (each record filed into .cache/live/dev/ or .cache/live/sealed/ by its receive time's
6-hour block, like the shared recorder; this process never reads, lists or counts anything in .cache/live/sealed/; counts go to
the status file only while the current block is a development block):
* btc5m_xeu  sized top of book coalesced to <= 1 record per (venue, symbol) per 30 ms (latest state wins),
    {"v","y","t" (receive ms),"E" (exchange ms),"b","B","a","A"} with v in
      cb  Coinbase Exchange BTC-USD / ETH-USD (level2_batch book top; ticker channel adds trade-time quotes as v=cbt)
      bt  Bitstamp order_book_btcusd / order_book_ethusd (microtimestamp)
      kr  Kraken v2 book BTC/USD, ETH/USD depth 10 (timestamp of the update)
      ba  Binance USD-M bookTicker SOL / XRP / DOGE / BNB USDT perps
      ya  Bybit linear orderbook.1 SOL / XRP / DOGE / BNB USDT
      oa  OKX bbo-tbt SOL / XRP / DOGE / BNB -USDT-SWAP
* btc5m_xsnap  every message of the SNAPSHOT streams (not coalesced; best level only):
      d5  Binance USD-M btcusdt / ethusdt @depth5@100ms (E, T)
      o5  OKX books5 BTC-USDT-SWAP / ETH-USDT-SWAP (ts)
      y50 Bybit linear orderbook.50 BTCUSDT (ts; snapshot + deltas, top kept)
Disk cap 280 MB over everything this process wrote; hard stop --stop; --start makes it sleep until then.
--probe: connect, subscribe and report ONLY the subscription acknowledgements (no market message is parsed or kept).
Usage: python rec_eu11.py --start 1793512740 --stop 1793642400 | --probe"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets

STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_eu11.status")
CO_MS = 30
DISK_CAP_MB = 280.0
ST = {"start": int(time.time()), "pid": os.getpid(), "err": {}, "reconnects": 0, "acks_dev": {}}
DEVN = {}
ALTS = ("SOL", "XRP", "DOGE", "BNB")


def dev_now():
    return not sealed.future_block_sealed(time.time())


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


class Out:
    def __init__(self, feed):
        self.w = live.Writer(feed); self.sizes = {}

    def write(self, obj, key=None):
        if ST.get("disk_full"):
            return
        self.w.write(obj)
        if key and dev_now():
            DEVN[key] = DEVN.get(key, 0) + 1

    def flush(self):
        self.w.flush()
        if self.w.fh is not None:
            try:
                self.sizes[str(self.w.path)] = self.w.fh.buffer.fileobj.tell()
            except Exception as e:
                err("size", e)

    def mb(self):
        return sum(self.sizes.values()) / 1e6


EU = Out("btc5m_xeu")
SNAP = Out("btc5m_xsnap")


class Coalesce:
    def __init__(self):
        self.last, self.pending = {}, {}

    def put(self, key, rec):
        now = time.time() * 1000
        if now - self.last.get(key, 0) >= CO_MS:
            self.last[key] = now; self.pending.pop(key, None); EU.write(rec, "eu_" + key[0])
        else:
            self.pending[key] = rec

    def tick(self):
        now = time.time() * 1000
        for key in list(self.pending):
            if now - self.last.get(key, 0) >= CO_MS:
                self.last[key] = now; EU.write(self.pending.pop(key), "eu_" + key[0])


CO = Coalesce()


def now_ms():
    return int(time.time() * 1000)


class Book:
    """price -> size maps with a lazily maintained best level."""
    def __init__(self):
        self.b, self.a = {}, {}

    def set(self, side, p, z):
        d = self.b if side == "b" else self.a
        if z <= 0:
            d.pop(p, None)
        else:
            d[p] = z

    def top(self):
        if not self.b or not self.a:
            return None
        bb = max(self.b); ba = min(self.a)
        return bb, self.b[bb], ba, self.a[ba]


CB = {}


def iso_ms(s):
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def coinbase(msg):
    j = json.loads(msg); ty = j.get("type")
    pid = j.get("product_id", "")
    y = pid.split("-")[0]
    if ty == "snapshot":
        bk = Book()
        for p, z in j.get("bids", [])[:400]:
            bk.set("b", float(p), float(z))
        for p, z in j.get("asks", [])[:400]:
            bk.set("a", float(p), float(z))
        CB[y] = bk
    elif ty == "l2update" and y in CB:
        bk = CB[y]
        for s, p, z in j.get("changes", []):
            bk.set("b" if s == "buy" else "a", float(p), float(z))
        t = bk.top()
        if t:
            CO.put(("cb", y), {"v": "cb", "y": y, "t": now_ms(), "E": iso_ms(j.get("time", "")), "b": t[0], "B": t[1], "a": t[2], "A": t[3]})
    elif ty == "ticker":
        CO.put(("cbt", y), {"v": "cbt", "y": y, "t": now_ms(), "E": iso_ms(j.get("time", "")), "b": fnum(j.get("best_bid")), "B": fnum(j.get("best_bid_size")),
                            "a": fnum(j.get("best_ask")), "A": fnum(j.get("best_ask_size"))})


def bitstamp(msg):
    j = json.loads(msg)
    if j.get("event") != "data":
        return
    ch = j.get("channel", ""); d = j.get("data", {})
    y = "BTC" if ch.endswith("btcusd") else "ETH"
    if d.get("bids") and d.get("asks"):
        b0, a0 = d["bids"][0], d["asks"][0]
        mt = d.get("microtimestamp")
        CO.put(("bt", y), {"v": "bt", "y": y, "t": now_ms(), "E": int(int(mt) / 1000) if mt else None, "b": fnum(b0[0]), "B": fnum(b0[1]), "a": fnum(a0[0]), "A": fnum(a0[1])})


KR = {}


def kraken(msg):
    j = json.loads(msg)
    if j.get("channel") != "book":
        return
    for d in j.get("data", []):
        y = d.get("symbol", "").split("/")[0]
        if j.get("type") == "snapshot" or y not in KR:
            KR[y] = Book()
        bk = KR[y]
        for lv in d.get("bids", []):
            bk.set("b", float(lv["price"]), float(lv["qty"]))
        for lv in d.get("asks", []):
            bk.set("a", float(lv["price"]), float(lv["qty"]))
        # keep the book small (depth 10 subscription; drop far levels)
        if len(bk.b) > 40:
            for p in sorted(bk.b)[:-20]:
                bk.b.pop(p, None)
        if len(bk.a) > 40:
            for p in sorted(bk.a)[20:]:
                bk.a.pop(p, None)
        t = bk.top()
        if t:
            CO.put(("kr", y), {"v": "kr", "y": y, "t": now_ms(), "E": iso_ms(d.get("timestamp", "")) if d.get("timestamp") else None,
                               "b": t[0], "B": t[1], "a": t[2], "A": t[3]})


def bn_alt(msg):
    d = json.loads(msg).get("data", {})
    if "b" in d and "a" in d:
        y = d.get("s", "").replace("USDT", "")
        CO.put(("ba", y), {"v": "ba", "y": y, "t": now_ms(), "E": d.get("E") or d.get("T"), "b": fnum(d["b"]), "B": fnum(d["B"]), "a": fnum(d["a"]), "A": fnum(d["A"])})


BY = {}


def bybit_alt(msg):
    j = json.loads(msg); topic = j.get("topic", "")
    if not topic.startswith("orderbook.1."):
        return
    y = topic.split(".")[-1].replace("USDT", ""); d = j.get("data", {})
    bk = BY.setdefault(y, {"b": None, "a": None})
    if d.get("b"):
        p, z = d["b"][0]; bk["b"] = (fnum(p), fnum(z))
    if d.get("a"):
        p, z = d["a"][0]; bk["a"] = (fnum(p), fnum(z))
    if bk["b"] and bk["a"]:
        CO.put(("ya", y), {"v": "ya", "y": y, "t": now_ms(), "E": j.get("ts"), "b": bk["b"][0], "B": bk["b"][1], "a": bk["a"][0], "A": bk["a"][1]})


def okx_alt(msg):
    if msg == "pong":
        return
    j = json.loads(msg); arg = j.get("arg", {})
    if arg.get("channel") != "bbo-tbt" or not j.get("data"):
        return
    d = j["data"][0]; y = arg.get("instId", "").split("-")[0]
    if d.get("bids") and d.get("asks"):
        CO.put(("oa", y), {"v": "oa", "y": y, "t": now_ms(), "E": int(d.get("ts")) if d.get("ts") else None, "b": fnum(d["bids"][0][0]), "B": fnum(d["bids"][0][1]),
                           "a": fnum(d["asks"][0][0]), "A": fnum(d["asks"][0][1])})


def bn_d5(msg):
    d = json.loads(msg).get("data", {})
    if d.get("b") and d.get("a"):
        y = d.get("s", "")[:3]
        SNAP.write({"v": "d5", "y": y, "t": now_ms(), "E": d.get("E"), "T": d.get("T"), "b": fnum(d["b"][0][0]), "B": fnum(d["b"][0][1]),
                    "a": fnum(d["a"][0][0]), "A": fnum(d["a"][0][1])}, "snap_d5")


def okx_b5(msg):
    if msg == "pong":
        return
    j = json.loads(msg); arg = j.get("arg", {})
    if arg.get("channel") != "books5" or not j.get("data"):
        return
    d = j["data"][0]; y = arg.get("instId", "").split("-")[0]
    if d.get("bids") and d.get("asks"):
        SNAP.write({"v": "o5", "y": y, "t": now_ms(), "E": int(d.get("ts")) if d.get("ts") else None, "b": fnum(d["bids"][0][0]), "B": fnum(d["bids"][0][1]),
                    "a": fnum(d["asks"][0][0]), "A": fnum(d["asks"][0][1])}, "snap_o5")


Y50 = {}


def bybit_50(msg):
    j = json.loads(msg); topic = j.get("topic", "")
    if not topic.startswith("orderbook.50."):
        return
    y = topic.split(".")[-1][:3]; d = j.get("data", {})
    if j.get("type") == "snapshot" or y not in Y50:
        Y50[y] = Book()
    bk = Y50[y]
    for p, z in d.get("b", []):
        bk.set("b", float(p), float(z))
    for p, z in d.get("a", []):
        bk.set("a", float(p), float(z))
    t = bk.top()
    if t:
        SNAP.write({"v": "y50", "y": y, "t": now_ms(), "E": j.get("ts"), "b": t[0], "B": t[1], "a": t[2], "A": t[3]}, "snap_y50")


def ack_of(name, msg):
    """subscription acknowledgements only (no market content)."""
    try:
        j = json.loads(msg)
    except Exception:
        return None
    if not isinstance(j, dict):
        return None
    if name.startswith("cb") and j.get("type") in ("subscriptions", "error"):
        return {"type": j.get("type"), "channels": [c.get("name") if isinstance(c, dict) else c for c in j.get("channels", [])], "msg": j.get("message")}
    if name == "bt" and str(j.get("event", "")).startswith("bts:"):
        return {"event": j.get("event"), "channel": j.get("channel")}
    if name == "kr" and j.get("method") in ("subscribe",):
        return {"method": "subscribe", "success": j.get("success"), "error": j.get("error"), "channel": (j.get("result") or {}).get("channel")}
    if name in ("oa", "o5") and j.get("event") in ("subscribe", "error"):
        return {"event": j.get("event"), "arg": j.get("arg"), "msg": j.get("msg")}
    if name in ("ya", "y50") and j.get("op") == "subscribe":
        return {"success": j.get("success"), "ret_msg": j.get("ret_msg")}
    return None


async def ws_loop(name, url, on_open, on_msg, stop_at, ping=None, ping_every=None, probe=None):
    while time.time() < stop_at and not ST.get("disk_full"):
        try:
            async with websockets.connect(url, open_timeout=15, ping_interval=20, max_size=2 ** 23, max_queue=4096) as ws:
                await on_open(ws)
                if probe is not None:
                    probe[name] = {"connected": True, "acks": []}
                last_ping = time.time()
                while time.time() < stop_at and not ST.get("disk_full"):
                    if ping and time.time() - last_ping > ping_every:
                        await ws.send(ping if isinstance(ping, str) else json.dumps(ping)); last_ping = time.time()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    ak = ack_of(name, msg)
                    if probe is not None:
                        if ak:
                            probe[name]["acks"].append(ak)
                        continue  # probe: nothing else is parsed or kept
                    if ak and dev_now():
                        ST["acks_dev"].setdefault(name, []).append(ak); ST["acks_dev"][name] = ST["acks_dev"][name][-6:]
                    try:
                        on_msg(msg)
                    except Exception as e:
                        err(name + "_parse", e)
        except Exception as e:
            err(name, e)
            if probe is not None:
                probe.setdefault(name, {})["error"] = repr(e)[:200]
            ST["reconnects"] += 1
            await asyncio.sleep(3)


async def main(stop_at, probe=None):
    async def nop(ws):
        return None

    async def cb_open(ws):
        await ws.send(json.dumps({"type": "subscribe", "product_ids": ["BTC-USD", "ETH-USD"], "channels": ["level2_batch", "ticker"]}))

    async def bt_open(ws):
        for ch in ("order_book_btcusd", "order_book_ethusd"):
            await ws.send(json.dumps({"event": "bts:subscribe", "data": {"channel": ch}}))

    async def kr_open(ws):
        await ws.send(json.dumps({"method": "subscribe", "params": {"channel": "book", "symbol": ["BTC/USD", "ETH/USD"], "depth": 10}}))

    async def ya_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": [f"orderbook.1.{s}USDT" for s in ALTS]}))

    async def oa_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": [{"channel": "bbo-tbt", "instId": f"{s}-USDT-SWAP"} for s in ALTS]}))

    async def o5_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": [{"channel": "books5", "instId": i} for i in ("BTC-USDT-SWAP", "ETH-USDT-SWAP")]}))

    async def y50_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": ["orderbook.50.BTCUSDT"]}))

    async def ticker():
        while time.time() < stop_at and not ST.get("disk_full"):
            await asyncio.sleep(CO_MS / 1000)
            CO.tick()

    async def status():
        while time.time() < stop_at:
            await asyncio.sleep(10)
            for o in (EU, SNAP):
                o.flush()
            mb = EU.mb() + SNAP.mb()
            ST["updated"] = int(time.time()); ST["stop_at"] = int(stop_at); ST["dev_now"] = dev_now()
            ST["disk_mb_total_own"] = round(mb, -1) if mb >= 10 else round(mb, 1)
            ST["dev_counts"] = DEVN
            if mb > DISK_CAP_MB:
                ST["disk_full"] = True
            with open(STATUS, "w") as fh:
                fh.write(json.dumps(ST))
            if ST.get("disk_full"):
                break

    alts_bn = "/".join(f"{s.lower()}usdt@bookTicker" for s in ALTS)
    loops = [
        ws_loop("cb", "wss://ws-feed.exchange.coinbase.com", cb_open, coinbase, stop_at, probe=probe),
        ws_loop("bt", "wss://ws.bitstamp.net", bt_open, bitstamp, stop_at, probe=probe),
        ws_loop("kr", "wss://ws.kraken.com/v2", kr_open, kraken, stop_at, probe=probe),
        ws_loop("ba", f"wss://fstream.binance.com/stream?streams={alts_bn}", nop, bn_alt, stop_at, probe=probe),
        ws_loop("ya", "wss://stream.bybit.com/v5/public/linear", ya_open, bybit_alt, stop_at, ping={"op": "ping"}, ping_every=15, probe=probe),
        ws_loop("oa", "wss://ws.okx.com:8443/ws/v5/public", oa_open, okx_alt, stop_at, ping="ping", ping_every=20, probe=probe),
        ws_loop("d5", "wss://fstream.binance.com/stream?streams=btcusdt@depth5@100ms/ethusdt@depth5@100ms", nop, bn_d5, stop_at, probe=probe),
        ws_loop("o5", "wss://ws.okx.com:8443/ws/v5/public", o5_open, okx_b5, stop_at, ping="ping", ping_every=20, probe=probe),
        ws_loop("y50", "wss://stream.bybit.com/v5/public/linear", y50_open, bybit_50, stop_at, ping={"op": "ping"}, ping_every=15, probe=probe),
    ]
    if probe is None:
        loops += [ticker(), status()]
    try:
        await asyncio.gather(*loops)
    finally:
        for o in (EU, SNAP):
            try:
                o.w.close()
            except Exception:
                pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--stop", type=float, default=time.time() + 3600)
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    if a.probe:
        pr = {}
        asyncio.run(main(time.time() + 12, probe=pr))
        print(json.dumps(pr, indent=1)[:4000])
        sys.exit(0)
    if a.start > time.time():
        ST["sleeping_until"] = int(a.start)
        with open(STATUS, "w") as fh:
            fh.write(json.dumps(ST))
        time.sleep(a.start - time.time())
    asyncio.run(main(a.stop))
    print(json.dumps(ST)[:2000])
