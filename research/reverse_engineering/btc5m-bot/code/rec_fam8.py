"""Iteration 8 recorder (btc5m-bot's own; catalog X44 = panel-information iter7 P1, X46 = panel-information iter7 P3).

Records the quote streams NEXT to the ten series of the frozen live vote, which no recorder had: the rest of the Binance
family (USDC-margined perps, COIN-M perps, spot USDC / FDUSD books), Deribit perp quotes, Bybit linear L1 (so the exam
inputs carry it too) and Binance USD-M liquidations. Records go through tools/live.py Writer, which files each record into
.cache/live/dev/ or .cache/live/sealed/ by its receive time's 6-hour block, exactly like the shared recorder; this process
never reads, lists or counts anything in .cache/live/sealed/ (the only bookkeeping is the compressed byte position of its
own open file handles, reported as one rounded total, and record counts in DEVELOPMENT blocks only).

The same subset is written in development and sealed blocks, so a series that passes on development blocks can be scored
by the examiner on sealed blocks with exactly the same inputs.

Feeds (receive time t = laptop ms; exchange ms E kept):
* btc5m_xfam: sized top of book, coalesced to at most one record per (venue, symbol) per CO_MS (latest state wins):
    {"v","y","t","E","b","B","a","A"} with v in
      uc  Binance USD-M USDC-margined perp (BTCUSDC, ETHUSDC) bookTicker
      cm  Binance COIN-M perp (BTCUSD_PERP, ETHUSD_PERP) bookTicker (sizes in contracts)
      su  Binance spot BTCUSDC / ETHUSDC bookTicker
      sf  Binance spot BTCFDUSD bookTicker
      db  Deribit quote.BTC-PERPETUAL / quote.ETH-PERPETUAL (sizes in USD)
      by  Bybit linear orderbook.1 BTCUSDT / ETHUSDT
* btc5m_xliq: Binance USD-M !forceOrder@arr, BTC* / ETH* symbols only, every record:
    {"t","E","s","S","q","p","ap","X","T"}
Disk cap: REC8_DISK_CAP_MB (default 290) over everything this process wrote; hard stop --stop (UNIX ts).
Usage: python rec_fam8.py --stop 1793728800 [--test 30]"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets

STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_fam8.status")
CO_MS = int(os.environ.get("REC8_CO_MS", "30"))
DISK_CAP_MB = float(os.environ.get("REC8_DISK_CAP_MB", "290"))
ST = {"start": int(time.time()), "pid": os.getpid(), "err": {}, "reconnects": 0}
DEVN = {}


def dev_now():
    return not sealed.future_block_sealed(time.time())


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


class Out:
    def __init__(self, feed):
        self.w = live.Writer(feed)
        self.sizes = {}

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


FAM = Out("btc5m_xfam")
LIQ = Out("btc5m_xliq")


class Coalesce:
    def __init__(self):
        self.last, self.pending = {}, {}

    def put(self, key, rec):
        now = time.time() * 1000
        if now - self.last.get(key, 0) >= CO_MS:
            self.last[key] = now
            self.pending.pop(key, None)
            FAM.write(rec, "fam_" + key[0])
        else:
            self.pending[key] = rec

    def tick(self):
        now = time.time() * 1000
        for key in list(self.pending):
            if now - self.last.get(key, 0) >= CO_MS:
                self.last[key] = now
                FAM.write(self.pending.pop(key), "fam_" + key[0])


CO = Coalesce()


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


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
                    try:
                        on_msg(msg)
                    except Exception as e:
                        err(name + "_parse", e)
        except Exception as e:
            err(name, e)
            ST["reconnects"] += 1
            await asyncio.sleep(3)


def bn_book(v):
    def f(msg):
        d = json.loads(msg).get("data", {})
        if "b" in d and "a" in d:
            s = d.get("s", "")[:3]
            if v == "su" and d.get("s", "").endswith("FDUSD"):
                return
            CO.put((v, s), {"v": v, "y": s, "t": int(time.time() * 1000), "E": d.get("E") or d.get("T"), "b": fnum(d["b"]), "B": fnum(d["B"]),
                            "a": fnum(d["a"]), "A": fnum(d["A"])})
    return f


def bn_fdusd(msg):
    d = json.loads(msg).get("data", {})
    if "b" in d and "a" in d and d.get("s", "").endswith("FDUSD"):
        s = d.get("s", "")[:3]
        CO.put(("sf", s), {"v": "sf", "y": s, "t": int(time.time() * 1000), "E": None, "b": fnum(d["b"]), "B": fnum(d["B"]), "a": fnum(d["a"]), "A": fnum(d["A"])})


def bn_spot(msg):
    d = json.loads(msg).get("data", {})
    if d.get("s", "").endswith("FDUSD"):
        bn_fdusd(msg)
    else:
        bn_book("su")(msg)


def liq(msg):
    j = json.loads(msg)
    o = j.get("o") if isinstance(j, dict) else None
    if not o:
        return
    s = o.get("s", "")
    if not (s.startswith("BTC") or s.startswith("ETH")):
        return
    LIQ.write({"t": int(time.time() * 1000), "E": j.get("E"), "s": s, "S": o.get("S"), "q": fnum(o.get("q")), "p": fnum(o.get("p")), "ap": fnum(o.get("ap")),
               "X": o.get("X"), "T": o.get("T")}, "liq")


def deribit(msg):
    j = json.loads(msg)
    p = j.get("params") or {}
    ch = p.get("channel", "")
    if not ch.startswith("quote."):
        return
    d = p.get("data", {})
    s = ch.split(".")[1][:3]
    CO.put(("db", s), {"v": "db", "y": s, "t": int(time.time() * 1000), "E": d.get("timestamp"), "b": fnum(d.get("best_bid_price")), "B": fnum(d.get("best_bid_amount")),
                       "a": fnum(d.get("best_ask_price")), "A": fnum(d.get("best_ask_amount"))})


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


async def main(stop_at):
    async def nop(ws):
        return None

    async def db_open(ws):
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "public/subscribe",
                                  "params": {"channels": ["quote.BTC-PERPETUAL", "quote.ETH-PERPETUAL"]}}))

    async def by_open(ws):
        await ws.send(json.dumps({"op": "subscribe", "args": ["orderbook.1.BTCUSDT", "orderbook.1.ETHUSDT"]}))

    async def ticker():
        while time.time() < stop_at and not ST.get("disk_full"):
            await asyncio.sleep(CO_MS / 1000)
            CO.tick()

    async def status():
        while time.time() < stop_at:
            await asyncio.sleep(10)
            for o in (FAM, LIQ):
                o.flush()
            mb = FAM.mb() + LIQ.mb()
            ST["updated"] = int(time.time()); ST["stop_at"] = int(stop_at); ST["dev_now"] = dev_now()
            ST["disk_mb_total_own"] = round(mb, -1) if mb >= 10 else round(mb, 1)
            ST["dev_counts"] = DEVN
            if mb > DISK_CAP_MB:
                ST["disk_full"] = True
            with open(STATUS, "w") as fh:
                fh.write(json.dumps(ST))
            if ST.get("disk_full"):
                break

    try:
        await asyncio.gather(
            ws_loop("uc", "wss://fstream.binance.com/stream?streams=btcusdc@bookTicker/ethusdc@bookTicker", nop, bn_book("uc"), stop_at),
            ws_loop("cm", "wss://dstream.binance.com/stream?streams=btcusd_perp@bookTicker/ethusd_perp@bookTicker", nop, bn_book("cm"), stop_at),
            ws_loop("sp", "wss://stream.binance.com:9443/stream?streams=btcusdc@bookTicker/btcfdusd@bookTicker/ethusdc@bookTicker", nop, bn_spot, stop_at),
            ws_loop("liq", "wss://fstream.binance.com/ws/!forceOrder@arr", nop, liq, stop_at),
            ws_loop("db", "wss://www.deribit.com/ws/api/v2", db_open, deribit, stop_at),
            ws_loop("by", "wss://stream.bybit.com/v5/public/linear", by_open, bybit, stop_at, ping={"op": "ping"}, ping_every=15),
            ticker(), status())
    finally:
        for o in (FAM, LIQ):
            o.w.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", type=float, default=time.time() + 3600)
    ap.add_argument("--test", type=float, default=0)
    a = ap.parse_args()
    stop_at = min(a.stop, time.time() + a.test) if a.test else a.stop
    asyncio.run(main(stop_at))
    print(json.dumps(ST)[:2000])
