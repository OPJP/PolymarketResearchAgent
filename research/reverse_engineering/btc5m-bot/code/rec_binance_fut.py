"""Iteration 5 live-lab recorder (btc5m-bot's own; the shared recorder has no exchange feeds): Binance USD-M futures
BTCUSDT and ETHUSDT bookTicker (kept only when the best bid or ask PRICE changes) and aggTrade, by receive time, filed
through tools/live.py's Writer (dev / sealed by calendar block) under feed "btc5m_bnfut". Records only from its start,
hard stop after --hours (default 10), small memory (no buffering beyond the gzip writer), flushes every 5 s.
Records: {"k":"b","t":recv_ms,"E":event_ms,"T":txn_ms,"s":sym,"b":bid,"a":ask,"B":bidqty,"A":askqty}
         {"k":"a","t":recv_ms,"E":event_ms,"T":trade_ms,"s":sym,"p":price,"q":qty,"m":buyer_is_maker}
Run detached: python rec_binance_fut.py --hours 10"""
import os, sys, json, time, asyncio, argparse
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import live
import websockets

URL = "wss://fstream.binance.com/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker/btcusdt@aggTrade/ethusdt@aggTrade"
FEED = "btc5m_bnfut"


async def run(hours: float):
    stop_at = time.time() + hours * 3600
    w = live.Writer(FEED)
    last = {}
    last_flush = time.time()
    status = os.path.join(_ROOT, ".cache", "re", "btc5m-bot", "rec_binance_fut.status")
    n = 0
    try:
        while time.time() < stop_at:
            try:
                async with websockets.connect(URL, ping_interval=20, max_size=2 ** 20) as ws:
                    while time.time() < stop_at:
                        msg = await asyncio.wait_for(ws.recv(), timeout=30)
                        now = int(time.time() * 1000)
                        d = json.loads(msg).get("data", {})
                        e = d.get("e")
                        if e == "bookTicker":
                            s = d["s"]; key = (d["b"], d["a"])
                            if last.get(s) == key:
                                continue
                            last[s] = key
                            w.write({"k": "b", "t": now, "E": d.get("E"), "T": d.get("T"), "s": s, "b": float(d["b"]), "a": float(d["a"]), "B": float(d["B"]), "A": float(d["A"])})
                        elif e == "aggTrade":
                            w.write({"k": "a", "t": now, "E": d.get("E"), "T": d.get("T"), "s": d["s"], "p": float(d["p"]), "q": float(d["q"]), "m": bool(d["m"])})
                        else:
                            continue
                        n += 1
                        if time.time() - last_flush > 5:
                            w.flush(); last_flush = time.time()
                            with open(status, "w") as fh:
                                fh.write(json.dumps({"pid": os.getpid(), "written": n, "updated": int(time.time()), "stop_at": int(stop_at)}))
            except Exception as ex:  # reconnect after network errors
                with open(status + ".err", "a") as fh:
                    fh.write(f"{time.strftime('%H:%M:%S')} {ex!r}\n")
                await asyncio.sleep(3)
    finally:
        w.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=10.0)
    asyncio.run(run(ap.parse_args().hours))
