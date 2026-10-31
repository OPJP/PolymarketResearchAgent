"""Iteration 7 EXAM-INPUT recorder (btc5m-bot's own; catalog X34 = panel-information iter6 P1 / panel-mechanics iter6
critique 1). Records the inputs of the frozen live rule (decision-level side = microprice vote of the fast venues, price
= Polymarket touch before the match, match ms + tx hash) in EVERY calendar block. Records go through tools/live.py Writer,
which files each record into .cache/live/dev/ or .cache/live/sealed/ by its receive time's 6-hour block, exactly like the
shared recorder. This process never reads, lists or counts anything in .cache/live/sealed/: the only bookkeeping it keeps
is the compressed byte position of its own open file handles (for the disk cap), reported as one rounded total.

The SAME subset is written in development and sealed blocks, so a rule developed on the development blocks sees exactly
the inputs the examiner will see on sealed blocks.

Feeds (receive time t = laptop ms; exchange / server ms kept):
* btc5m_xclob: Polymarket CLOB market channel, BTC 5m windows only (one connection per window, opened ~4 min before its
  start, closed 15 s after its end):
    {"k":"S","t","m":start,"u":up_token,"d":down_token}                 subscription
    {"k":"f","t","s","m","u":1|0,"b":[[p,z]..10],"o":[[p,z]..10]}        book snapshot per token, at most every 10 s
    {"k":"p","t","s","m","d":"B"|"S","p","z","bb","ba"}                   every Up-token price_change AT the Up touch
                                                                          (|p - best bid| or |p - best ask| < 0.5 tick),
                                                                          with the post-change touch (bb, ba)
    {"k":"x","t","s","m","u","p","z","d","h"}                             every last_trade_price (both tokens, tx hash)
* btc5m_xven: sized top of book, coalesced to at most one record per (venue, symbol) per CO_MS (latest state wins):
    {"v":"bf"|"bs"|"ok","y":"BTC"|"ETH","t","E","b","B","a","A"}   Binance USD-M bookTicker, Binance spot bookTicker,
                                                                    OKX bbo-tbt swaps
Disk cap: REC7_DISK_CAP_MB (default 300) over everything this process wrote; hard stop --stop (UNIX ts).
Usage: python rec_exam7.py --stop 1793642400 [--test 30]"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets, httpx

SUFFIX = os.environ.get("REC7_SUFFIX", "")
STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_exam7" + SUFFIX + ".status")
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
GAMMA = "https://gamma-api.polymarket.com/markets"
CO_MS = int(os.environ.get("REC7_CO_MS", "30"))
DISK_CAP_MB = float(os.environ.get("REC7_DISK_CAP_MB", "300"))
SNAP_MS = 10000
ST = {"start": int(time.time()), "pid": os.getpid(), "err": {}, "reconnects": 0}
DEVN = {}  # record counts in DEVELOPMENT blocks only (nothing is counted while the block is sealed)


def dev_now():
    return not sealed.future_block_sealed(time.time())


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


class Out:
    """tools/live.py Writer plus the compressed size of every file this process wrote (own file handles only)."""
    def __init__(self, feed):
        self.w = live.Writer(feed)
        self.sizes = {}  # path -> compressed bytes written by this process (from its own handle)

    def write(self, obj, key=None):
        if ST.get("disk_full"):
            return False
        self.w.write(obj)
        if key and dev_now():
            DEVN[key] = DEVN.get(key, 0) + 1
        return True

    def flush(self):
        self.w.flush()
        if self.w.fh is not None:
            try:
                self.sizes[str(self.w.path)] = self.w.fh.buffer.fileobj.tell()
            except Exception as e:
                err("size", e)

    def mb(self):
        return sum(self.sizes.values()) / 1e6


CLOB = Out("btc5m_xclob" + SUFFIX)
VEN = Out("btc5m_xven" + SUFFIX)


class Coalesce:
    def __init__(self):
        self.last, self.pending = {}, {}

    def put(self, key, rec):
        now = time.time() * 1000
        if now - self.last.get(key, 0) >= CO_MS:
            self.last[key] = now
            self.pending.pop(key, None)
            VEN.write(rec, "ven_" + key[0])
        else:
            self.pending[key] = rec

    def tick(self):
        now = time.time() * 1000
        for key in list(self.pending):
            if now - self.last.get(key, 0) >= CO_MS:
                self.last[key] = now
                VEN.write(self.pending.pop(key), "ven_" + key[0])


CO = Coalesce()


async def ws_loop(name, url, on_open, on_msg, stop_at, ping=None, ping_every=None):
    while time.time() < stop_at and not ST.get("disk_full"):
        try:
            async with websockets.connect(url, open_timeout=15, ping_interval=20, max_size=2 ** 22, max_queue=4096) as ws:
                await on_open(ws)
                last_ping = time.time()
                while time.time() < stop_at and not ST.get("disk_full"):
                    if ping and time.time() - last_ping > ping_every:
                        await ws.send(ping if isinstance(ping, str) else json.dumps(ping)); last_ping = time.time()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    on_msg(msg)
        except Exception as e:
            err(name, e)
            ST["reconnects"] += 1
            await asyncio.sleep(3)


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


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


def okx(msg):
    if msg == "pong":
        return
    j = json.loads(msg)
    arg = j.get("arg", {})
    if arg.get("channel") != "bbo-tbt":
        return
    s = arg.get("instId", "")[:3]
    for d in j.get("data", []) or []:
        b, a = d.get("bids") or [], d.get("asks") or []
        if b and a:
            CO.put(("ok", s), {"v": "ok", "y": s, "t": int(time.time() * 1000), "E": int(d.get("ts", 0)), "b": fnum(b[0][0]), "B": fnum(b[0][1]), "a": fnum(a[0][0]), "A": fnum(a[0][1])})


async def venues(stop_at):
    async def nop(ws):
        return None

    async def ok_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": [{"channel": "bbo-tbt", "instId": "BTC-USDT-SWAP"}, {"channel": "bbo-tbt", "instId": "ETH-USDT-SWAP"}]}))

    async def ticker():
        while time.time() < stop_at and not ST.get("disk_full"):
            await asyncio.sleep(CO_MS / 1000)
            CO.tick()

    await asyncio.gather(
        ws_loop("bf", "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker", nop, bn_fut, stop_at),
        ws_loop("bs", "wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker", nop, bn_spot, stop_at),
        ws_loop("ok", "wss://ws.okx.com:8443/ws/v5/public", ok_open, okx, stop_at, ping="ping", ping_every=20),
        ticker())


TOK = {}


def tokens(start):
    if start in TOK:
        return TOK[start]
    with httpx.Client(timeout=15, headers={"User-Agent": "polyrea-research"}) as c:
        j = c.get(GAMMA, params={"slug": f"btc-updown-5m-{start}"}).json()
    t = json.loads(j[0]["clobTokenIds"]) if j else []  # listing field only (token ids)
    if len(t) == 2:
        TOK[start] = t
    return t


async def clob_window(start, stop_at):
    try:
        up, dn = await asyncio.to_thread(tokens, start)
    except Exception as e:
        err("clob_tok", e); return
    end_at = min(stop_at, start + 300 + 15)
    CLOB.write({"k": "S", "t": int(time.time() * 1000), "m": start, "u": up, "d": dn}, "clob_S")
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
                if now - last_f.get(a, 0) < SNAP_MS:
                    continue
                last_f[a] = now
                bids = sorted(((fnum(x["price"]), fnum(x["size"])) for x in it.get("bids", [])), reverse=True)[:10]
                asks = sorted(((fnum(x["price"]), fnum(x["size"])) for x in it.get("asks", [])))[:10]
                CLOB.write({"k": "f", "t": now, "s": int(it.get("timestamp") or 0), "m": start, "u": int(a == up), "b": bids, "o": asks}, "clob_f")
            elif "price_changes" in it:
                s = int(it.get("timestamp") or 0)
                for ch in it["price_changes"]:
                    if ch.get("asset_id") != up:
                        continue
                    p = fnum(ch.get("price")); bb = fnum(ch.get("best_bid")); ba = fnum(ch.get("best_ask"))
                    if p is None:
                        continue
                    at = (bb is not None and abs(p - bb) < 0.0005) or (ba is not None and abs(p - ba) < 0.0005)
                    if not at:
                        continue
                    CLOB.write({"k": "p", "t": now, "s": s, "m": start, "d": "B" if ch.get("side") == "BUY" else "S", "p": p, "z": fnum(ch.get("size")), "bb": bb, "ba": ba}, "clob_p")
            elif ev == "last_trade_price":
                a = it.get("asset_id")
                CLOB.write({"k": "x", "t": now, "s": int(it.get("timestamp") or 0), "m": start, "u": int(a == up), "p": fnum(it.get("price")), "z": fnum(it.get("size")),
                            "d": it.get("side"), "h": it.get("transaction_hash")}, "clob_x")

    async def on_open(ws):
        await ws.send(json.dumps({"assets_ids": [up, dn], "type": "market"}))

    await ws_loop(f"clob{start % 3600}", CLOB_WS, on_open, on_msg, end_at, ping="PING", ping_every=10)


async def clob_manager(stop_at):
    running = {}
    while time.time() < stop_at and not ST.get("disk_full"):
        now = time.time()
        cur = int(now // 300 * 300)
        for st in (cur, cur + 300):
            if st not in running and st + 300 > now and st - now < 250:
                running[st] = asyncio.create_task(clob_window(st, stop_at))
        for st in [s for s, t in running.items() if t.done()]:
            del running[st]
        await asyncio.sleep(2)


async def status(stop_at):
    while time.time() < stop_at:
        await asyncio.sleep(10)
        for o in (CLOB, VEN):
            o.flush()
        mb = CLOB.mb() + VEN.mb()
        ST["updated"] = int(time.time()); ST["stop_at"] = int(stop_at); ST["dev_now"] = dev_now()
        ST["disk_mb_total_own"] = round(mb, -1) if mb >= 10 else round(mb, 1)
        ST["dev_counts"] = DEVN
        if mb > DISK_CAP_MB:
            ST["disk_full"] = True
        with open(STATUS, "w") as fh:
            fh.write(json.dumps(ST))
        if ST.get("disk_full"):
            break


async def main(stop_at):
    try:
        await asyncio.gather(venues(stop_at), clob_manager(stop_at), status(stop_at))
    finally:
        for o in (CLOB, VEN):
            o.w.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", type=float, default=time.time() + 3600)
    ap.add_argument("--test", type=float, default=0)
    a = ap.parse_args()
    stop_at = min(a.stop, time.time() + a.test) if a.test else a.stop
    asyncio.run(main(stop_at))
    print(json.dumps(ST)[:2000])
