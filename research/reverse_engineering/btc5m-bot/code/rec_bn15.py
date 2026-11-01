"""Iteration 15 recorder (btc5m-bot's own; panel iter14 information P4 = X142: full-rate raw Binance family for an out-of-time
check of the decision-clock routes dc_exam14 / dc_hazard14, which the shared recorder's coalesced quotes cannot support).

Feeds, all through tools/live.py Writer (each record filed into .cache/live/dev/ or .cache/live/sealed/ by its receive time's
6-hour block, like the shared recorder; this process never reads, lists or counts anything in .cache/live/sealed/):
* btc5m_bnspot2 every message (not coalesced) of Binance SPOT btcusdt@bookTicker {"k":"q","t":recv_ms,"tu":recv_us,"u","b","B","a","A"}
                and btcusdt@trade {"k":"x","t":recv_us,"E","T","p","q","m","i"}
* btc5m_bnusdm2 every message of Binance USD-M btcusdt@bookTicker {"k":"q","t","E","T","u","b","B","a","A"} and
                btcusdt@aggTrade {"k":"x","t","E","T","p","q","m","i"}; this feed stops first when the disk budget runs low.
Disk cap: USD-M stops at 170 MB own disk, everything at 280 MB. Hard stop --stop; --start sleeps until then.
v1 (06:00-06:57 UTC 11-01, feeds btc5m_bnspot / btc5m_bnusdm) wrote "t" in microseconds, which iter_live cannot filter (it
expects ms): those files are not usable through iter_live. v2 (from 06:58) writes t = receive ms and tu = receive us.
Usage: python rec_bn15.py --start 1793512770 --stop 1793534400"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live, sealed
import websockets

STATUS = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_bn15.status")
CAP_USDM, CAP_ALL = 170.0, 280.0
ST = {"start": int(time.time()), "pid": os.getpid(), "err": {}, "reconnects": 0}
DEVN = {}


def dev_now():
    return not sealed.future_block_sealed(time.time())


def err(k, e):
    ST["err"][k] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]


class Out:
    def __init__(self, feed):
        self.w = live.Writer(feed); self.sizes = {}; self.stopped = False

    def write(self, obj, key):
        if self.stopped or ST.get("disk_full"):
            return
        self.w.write(obj)
        if dev_now():
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


SPOT = Out("btc5m_bnspot2")
USDM = Out("btc5m_bnusdm2")


def on_spot(msg):
    tu = time.time_ns() // 1000; t = tu // 1000
    j = json.loads(msg); s = j.get("stream", ""); d = j.get("data", {})
    if s.endswith("@bookTicker"):
        SPOT.write({"k": "q", "t": t, "tu": tu, "u": d.get("u"), "b": d.get("b"), "B": d.get("B"), "a": d.get("a"), "A": d.get("A")}, "spot_q")
    elif s.endswith("@trade"):
        SPOT.write({"k": "x", "t": t, "tu": tu, "E": d.get("E"), "T": d.get("T"), "p": d.get("p"), "q": d.get("q"), "m": d.get("m"), "i": d.get("t")}, "spot_x")


def on_usdm(msg):
    tu = time.time_ns() // 1000; t = tu // 1000
    j = json.loads(msg); s = j.get("stream", ""); d = j.get("data", {})
    if s.endswith("@bookTicker"):
        USDM.write({"k": "q", "t": t, "tu": tu, "E": d.get("E"), "T": d.get("T"), "u": d.get("u"), "b": d.get("b"), "B": d.get("B"), "a": d.get("a"), "A": d.get("A")}, "usdm_q")
    elif s.endswith("@aggTrade"):
        USDM.write({"k": "x", "t": t, "tu": tu, "E": d.get("E"), "T": d.get("T"), "p": d.get("p"), "q": d.get("q"), "m": d.get("m"), "i": d.get("a")}, "usdm_x")


async def ws_loop(name, url, on_msg, stop_at, out):
    while time.time() < stop_at and not ST.get("disk_full") and not out.stopped:
        try:
            async with websockets.connect(url, open_timeout=15, ping_interval=20, max_size=2 ** 22, max_queue=8192) as ws:
                while time.time() < stop_at and not ST.get("disk_full") and not out.stopped:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        on_msg(msg)
                    except Exception as e:
                        err(name + "_parse", e)
        except Exception as e:
            err(name, e); ST["reconnects"] += 1
            await asyncio.sleep(3)


async def main(stop_at):
    async def status():
        while time.time() < stop_at:
            await asyncio.sleep(10)
            for o in (SPOT, USDM):
                o.flush()
            mb = SPOT.mb() + USDM.mb()
            ST["updated"] = int(time.time()); ST["stop_at"] = int(stop_at); ST["dev_now"] = dev_now()
            ST["disk_mb_total_own"] = round(mb, 1); ST["dev_counts"] = DEVN
            if mb > CAP_USDM and not USDM.stopped:
                USDM.stopped = True; ST["usdm_stopped"] = int(time.time())
            if mb > CAP_ALL:
                ST["disk_full"] = True
            with open(STATUS, "w") as fh:
                fh.write(json.dumps(ST))
            if ST.get("disk_full"):
                break

    loops = [
        ws_loop("spot", "wss://stream.binance.com:9443/stream?streams=btcusdt@bookTicker/btcusdt@trade", on_spot, stop_at, SPOT),
        ws_loop("usdm", "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/btcusdt@aggTrade", on_usdm, stop_at, USDM),
        status(),
    ]
    try:
        await asyncio.gather(*loops)
    finally:
        for o in (SPOT, USDM):
            try:
                o.w.close()
            except Exception:
                pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--stop", type=float, required=True)
    a = ap.parse_args()
    if a.stop - time.time() > 8 * 3600:
        sys.exit("stop more than 8 h ahead refused")
    if a.start > time.time():
        ST["sleeping_until"] = int(a.start)
        with open(STATUS, "w") as fh:
            fh.write(json.dumps(ST))
        time.sleep(a.start - time.time())
    asyncio.run(main(a.stop))
    with open(STATUS, "w") as fh:
        fh.write(json.dumps(ST))
