"""Iteration 6 live-lab recorder (btc5m-bot's own; X15/X18/X19/X20/X23 of the catalog). Development blocks only: every record
is dropped while the calendar block is sealed (tools/sealed.py), so nothing sealed is ever written by this process.
Files through tools/live.py Writer (same layout as the shared recorder). Hard stop (--stop UNIX ts). Small memory.

Feeds (all by receive time t = laptop ms; exchange times kept where the venue sends them):
* btc5m_clob_raw: Polymarket CLOB market channel for the BTC 5m windows only (one connection per window, opened ~4 min
  before its start, closed 15 s after its end), UNTHROTTLED:
    {"k":"S","t","m":start,"u":up_token,"d":down_token}                         subscription
    {"k":"f","t","s":server_ms,"m","u":1|0,"b":[[p,z]..15],"o":[[p,z]..15]}      book snapshot (per token)
    {"k":"p","t","s","m","d":"B"|"S","p","z","bb","ba"}                           every Up-token price_change entry whose
                                                                                    price is within 3 c of the Up touch
    {"k":"x","t","s","m","u","p","z","d","h"}                                     every last_trade_price (both tokens)
    {"k":"c","t","m","raw"}                                                        tick-size changes / other
* btc5m_venues: sized top of book, coalesced to at most one record per (venue, symbol) per 20 ms (latest state wins):
    {"v":venue,"y":sym,"t","E":exch_ms|null,"b","B","a","A"}      quotes  (bf Binance USD-M bookTicker, bs Binance spot
        bookTicker, by Bybit linear orderbook.1, ok OKX bbo-tbt swap, hl Hyperliquid bbo)
    {"v":venue+"T","y","t","E","p","q","sd"}                       trades (ok OKX swap trades, hl Hyperliquid trades,
        cb Coinbase ticker = trade with best bid/ask)
* btc5m_rtds_stream: Polymarket RTDS kept open with an application PING every 5 s, every message with its arrival ms
    {"t","m":raw}
Usage: python rec_lab6.py --stop 1793642400 [--test 60]"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets, httpx

STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_lab6" + os.environ.get("REC6_SUFFIX", "") + ".status")
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
RTDS_WS = "wss://ws-live-data.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com/markets"
CO_MS = int(os.environ.get("REC6_CO_MS", "20"))
NEAR = float(os.environ.get("REC6_NEAR", "0.0301"))
SUFFIX = os.environ.get("REC6_SUFFIX", "")
DISK_CAP_MB = float(os.environ.get("REC6_DISK_CAP_MB", "1e9"))
ST = {"start": int(time.time()), "pid": os.getpid(), "n": {}, "err": {}}


def dev_now():
    return not sealed.future_block_sealed(time.time())


def bump(k, n=1):
    ST["n"][k] = ST["n"].get(k, 0) + n


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


class Out:
    def __init__(self, feed):
        self.w = live.Writer(feed)

    def write(self, obj):
        if dev_now() and not ST.get("disk_full"):
            self.w.write(obj)
            return True
        return False


CLOB = Out("btc5m_clob_raw" + SUFFIX)
VEN = Out("btc5m_venues" + SUFFIX)
RT = Out("btc5m_rtds_stream" + SUFFIX)


class Coalesce:
    """At most one quote record per key per CO_MS; the latest state is written when the slot opens."""
    def __init__(self):
        self.last, self.pending = {}, {}

    def put(self, key, rec):
        now = time.time() * 1000
        if now - self.last.get(key, 0) >= CO_MS:
            self.last[key] = now
            self.pending.pop(key, None)
            if VEN.write(rec):
                bump("ven_" + key[0])
        else:
            self.pending[key] = rec

    def tick(self):
        now = time.time() * 1000
        for key in list(self.pending):
            if now - self.last.get(key, 0) >= CO_MS:
                self.last[key] = now
                if VEN.write(self.pending.pop(key)):
                    bump("ven_" + key[0])


CO = Coalesce()


async def ws_loop(name, url, on_open, on_msg, stop_at, ping=None, ping_every=None):
    while time.time() < stop_at:
        try:
            async with websockets.connect(url, open_timeout=15, ping_interval=20, max_size=2 ** 22, max_queue=4096) as ws:
                await on_open(ws)
                last_ping = time.time()
                while time.time() < stop_at:
                    if ping and time.time() - last_ping > ping_every:
                        await ws.send(ping if isinstance(ping, str) else json.dumps(ping)); last_ping = time.time()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    on_msg(msg)
        except Exception as e:
            err(name, e)
            bump("reconnect_" + name)
            await asyncio.sleep(3)


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


# ---------------- venues ----------------
def bn_fut(msg):
    d = json.loads(msg).get("data", {})
    if d.get("e") == "bookTicker":
        s = d["s"][:3]
        CO.put(("bf", s), {"v": "bf", "y": s, "t": int(time.time() * 1000), "E": d.get("E"), "b": fnum(d["b"]), "B": fnum(d["B"]), "a": fnum(d["a"]), "A": fnum(d["A"])})


def bn_spot(msg):
    d = json.loads(msg).get("data", {})
    if "b" in d and "a" in d:
        s = d.get("s", "")[:3]
        CO.put(("bs", s), {"v": "bs", "y": s, "t": int(time.time() * 1000), "E": None, "u": d.get("u"), "b": fnum(d["b"]), "B": fnum(d["B"]), "a": fnum(d["a"]), "A": fnum(d["A"])})


BY_BOOK = {}


def bybit(msg):
    j = json.loads(msg)
    topic = j.get("topic", "")
    if not topic.startswith("orderbook.1."):
        return
    s = topic.split(".")[-1][:3]
    d = j.get("data", {})
    bk = BY_BOOK.setdefault(s, {"b": None, "a": None})
    if d.get("b"):
        p, z = d["b"][0]; bk["b"] = (fnum(p), fnum(z))
    if d.get("a"):
        p, z = d["a"][0]; bk["a"] = (fnum(p), fnum(z))
    if bk["b"] and bk["a"]:
        CO.put(("by", s), {"v": "by", "y": s, "t": int(time.time() * 1000), "E": j.get("ts"), "b": bk["b"][0], "B": bk["b"][1], "a": bk["a"][0], "A": bk["a"][1]})


def okx(msg):
    if msg == "pong":
        return
    j = json.loads(msg)
    arg = j.get("arg", {})
    ch, inst = arg.get("channel"), arg.get("instId", "")
    s = inst[:3]
    for d in j.get("data", []) or []:
        if ch == "bbo-tbt":
            b, a = d.get("bids") or [], d.get("asks") or []
            if b and a:
                CO.put(("ok", s), {"v": "ok", "y": s, "t": int(time.time() * 1000), "E": int(d.get("ts", 0)), "b": fnum(b[0][0]), "B": fnum(b[0][1]), "a": fnum(a[0][0]), "A": fnum(a[0][1])})
        elif ch == "trades":
            if VEN.write({"v": "okT", "y": s, "t": int(time.time() * 1000), "E": int(d.get("ts", 0)), "p": fnum(d.get("px")), "q": fnum(d.get("sz")), "sd": d.get("side")}):
                bump("ven_okT")


def hyper(msg):
    j = json.loads(msg)
    ch, d = j.get("channel"), j.get("data")
    if ch == "bbo" and isinstance(d, dict):
        lv = d.get("bbo") or [None, None]
        if lv[0] and lv[1]:
            s = d.get("coin", "")[:3]
            CO.put(("hl", s), {"v": "hl", "y": s, "t": int(time.time() * 1000), "E": d.get("time"), "b": fnum(lv[0]["px"]), "B": fnum(lv[0]["sz"]), "a": fnum(lv[1]["px"]), "A": fnum(lv[1]["sz"])})
    elif ch == "trades" and isinstance(d, list):
        for x in d:
            if VEN.write({"v": "hlT", "y": x.get("coin", "")[:3], "t": int(time.time() * 1000), "E": x.get("time"), "p": fnum(x.get("px")), "q": fnum(x.get("sz")), "sd": x.get("side")}):
                bump("ven_hlT")


def _iso_ms(s):
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def coinbase(msg):
    j = json.loads(msg)
    if j.get("type") != "ticker":
        return
    if VEN.write({"v": "cbT", "y": j.get("product_id", "")[:3], "t": int(time.time() * 1000), "E": _iso_ms(j.get("time", "")), "p": fnum(j.get("price")), "q": fnum(j.get("last_size")),
                  "sd": j.get("side"), "b": fnum(j.get("best_bid")), "B": fnum(j.get("best_bid_size")), "a": fnum(j.get("best_ask")), "A": fnum(j.get("best_ask_size"))}):
        bump("ven_cbT")


async def venues(stop_at):
    async def nop(ws):
        return None

    async def by_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": ["orderbook.1.BTCUSDT", "orderbook.1.ETHUSDT"]}))

    async def ok_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": [{"channel": "bbo-tbt", "instId": "BTC-USDT-SWAP"}, {"channel": "bbo-tbt", "instId": "ETH-USDT-SWAP"},
                                                               {"channel": "trades", "instId": "BTC-USDT-SWAP"}, {"channel": "trades", "instId": "ETH-USDT-SWAP"}]}))

    async def hl_open(ws):
        for c in ("BTC", "ETH"):
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": c}}))
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": c}}))

    async def cb_open(ws):
        await ws.send(json.dumps({"type": "subscribe", "product_ids": ["BTC-USD", "ETH-USD"], "channels": ["ticker"]}))

    async def ticker():
        while time.time() < stop_at:
            await asyncio.sleep(CO_MS / 1000)
            CO.tick()

    await asyncio.gather(
        ws_loop("bf", "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker", nop, bn_fut, stop_at),
        ws_loop("bs", "wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker", nop, bn_spot, stop_at),
        ws_loop("by", "wss://stream.bybit.com/v5/public/linear", by_open, bybit, stop_at, ping={"op": "ping"}, ping_every=15),
        ws_loop("ok", "wss://ws.okx.com:8443/ws/v5/public", ok_open, okx, stop_at, ping="ping", ping_every=20),
        ws_loop("hl", "wss://api.hyperliquid.xyz/ws", hl_open, hyper, stop_at, ping={"method": "ping"}, ping_every=30),
        ws_loop("cb", "wss://ws-feed.exchange.coinbase.com", cb_open, coinbase, stop_at),
        ticker())


# ---------------- Polymarket BTC 5m book, unthrottled ----------------
TOK = {}


def tokens(start):
    if start in TOK:
        return TOK[start]
    with httpx.Client(timeout=15, headers={"User-Agent": "polyrea-research"}) as c:
        j = c.get(GAMMA, params={"slug": f"btc-updown-5m-{start}"}).json()
    t = json.loads(j[0]["clobTokenIds"]) if j else []
    if len(t) == 2:
        TOK[start] = t
    return t


async def clob_window(start, stop_at):
    try:
        up, dn = await asyncio.to_thread(tokens, start)
    except Exception as e:
        err("clob_tok", e); return
    end_at = min(stop_at, start + 300 + 15)
    CLOB.write({"k": "S", "t": int(time.time() * 1000), "m": start, "u": up, "d": dn})
    last_f = {}

    def on_msg(raw):
        if raw == "PONG":
            return
        now = int(time.time() * 1000)
        try:
            j = json.loads(raw)
        except ValueError:
            return
        for it in (j if isinstance(j, list) else [j]):
            ev = it.get("event_type")
            if ev == "book" or ("bids" in it and "asks" in it):
                a = it.get("asset_id")
                if now - last_f.get(a, 0) < 2000:  # full books arrive after every trade; the deltas carry the rest
                    bump("clob_f_skip"); continue
                last_f[a] = now
                bids = sorted(((fnum(x["price"]), fnum(x["size"])) for x in it.get("bids", [])), reverse=True)[:15]
                asks = sorted(((fnum(x["price"]), fnum(x["size"])) for x in it.get("asks", [])))[:15]
                if CLOB.write({"k": "f", "t": now, "s": int(it.get("timestamp") or 0), "m": start, "u": int(a == up), "b": bids, "o": asks}):
                    bump("clob_f")
            elif "price_changes" in it:
                s = int(it.get("timestamp") or 0)
                for ch in it["price_changes"]:
                    if ch.get("asset_id") != up:
                        continue
                    p = fnum(ch.get("price")); bb = fnum(ch.get("best_bid")); ba = fnum(ch.get("best_ask"))
                    near = (bb is not None and abs(p - bb) <= NEAR) or (ba is not None and abs(p - ba) <= NEAR)
                    if not near:
                        bump("clob_p_far"); continue
                    if CLOB.write({"k": "p", "t": now, "s": s, "m": start, "d": "B" if ch.get("side") == "BUY" else "S", "p": p, "z": fnum(ch.get("size")), "bb": bb, "ba": ba}):
                        bump("clob_p")
            elif ev == "last_trade_price":
                a = it.get("asset_id")
                if CLOB.write({"k": "x", "t": now, "s": int(it.get("timestamp") or 0), "m": start, "u": int(a == up), "p": fnum(it.get("price")), "z": fnum(it.get("size")),
                               "d": it.get("side"), "h": it.get("transaction_hash")}):
                    bump("clob_x")
            else:
                if CLOB.write({"k": "c", "t": now, "m": start, "raw": json.dumps(it)[:500]}):
                    bump("clob_c")

    async def on_open(ws):
        await ws.send(json.dumps({"assets_ids": [up, dn], "type": "market"}))

    await ws_loop(f"clob{start % 3600}", CLOB_WS, on_open, on_msg, end_at, ping="PING", ping_every=10)


async def clob_manager(stop_at):
    running = {}
    while time.time() < stop_at:
        now = time.time()
        cur = int(now // 300 * 300)
        for st in (cur, cur + 300):
            if st not in running and st + 300 > now and st - now < 250:
                running[st] = asyncio.create_task(clob_window(st, stop_at))
        for st in [s for s, t in running.items() if t.done()]:
            del running[st]
        await asyncio.sleep(2)


# ---------------- RTDS kept open ----------------
async def rtds(stop_at):
    sub = {"action": "subscribe", "subscriptions": [{"topic": t, "type": "*", "filters": json.dumps({"symbol": f"{c}/usd"})}
                                                     for t in ("crypto_prices_chainlink", "crypto_prices_twap_sixty") for c in ("btc", "eth")]
           + [{"topic": "crypto_prices", "type": "update", "filters": "btcusdt,ethusdt"}]}

    async def on_open(ws):
        await ws.send(json.dumps(sub))

    def on_msg(msg):
        if msg and msg not in ("PONG", "pong"):
            if RT.write({"t": int(time.time() * 1000), "m": msg[:4000]}):
                bump("rtds")

    await ws_loop("rtds", RTDS_WS, on_open, on_msg, stop_at, ping="PING", ping_every=5)


async def status(stop_at):
    while time.time() < stop_at:
        await asyncio.sleep(10)
        for o in (CLOB, VEN, RT):
            o.w.flush()
        ST["updated"] = int(time.time()); ST["stop_at"] = int(stop_at); ST["dev_now"] = dev_now()
        mb = 0.0
        for o in (CLOB, VEN, RT):
            for part in ("dev",):  # this recorder never writes sealed blocks; the sealed folder is never touched
                d = os.path.join(_ROOT, ".cache", "live", part, o.w.feed)
                if os.path.isdir(d):
                    mb += sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)) / 1e6
        ST["disk_mb"] = round(mb, 1)
        if mb > DISK_CAP_MB:
            ST["disk_full"] = True
        with open(STATUS, "w") as fh:
            fh.write(json.dumps(ST))


async def main(stop_at):
    try:
        await asyncio.gather(venues(stop_at), clob_manager(stop_at), rtds(stop_at), status(stop_at))
    finally:
        for o in (CLOB, VEN, RT):
            o.w.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", type=float, default=time.time() + 3600)
    ap.add_argument("--test", type=float, default=0)
    a = ap.parse_args()
    stop_at = min(a.stop, time.time() + a.test) if a.test else a.stop
    asyncio.run(main(stop_at))
    print(json.dumps(ST)[:3000])
