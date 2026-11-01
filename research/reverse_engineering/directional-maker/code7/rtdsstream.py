"""directional-maker iteration 7: streaming RTDS recorder with server publish ms (panel iter6 information I2,
mechanics M1 step 5).

The shared recorder and code6/examrec.py subscribe to RTDS with filters {"symbol": "btc/usd"}, which returns one
~60-value snapshot and no streaming updates. With filters "" the socket pushes one `update` per symbol per second,
carrying payload.timestamp (the value stamp) and a top-level timestamp (server publish ms). This recorder keeps the
btc/eth/sol updates of crypto_prices_chainlink and crypto_prices_twap_sixty.

Records (feed dy_rtds, tools/live.py Writer: dev/sealed by receive-time block):
  {"k":"u","tp":"cl"|"tw","sy":"btc"|"eth"|"sol","v":value,"ts":value_stamp_ms,"P":server_publish_ms,"t":recv_ms}
  {"k":"clk","t":recv_ms,"off":binance_minus_laptop_s,"rtt":s}   every 10 min (laptop clock calibration)
  {"k":"conn","t":recv_ms,"tp":topic,"ev":"open"|"close","err":...}
Hard stop --until (default 2026-11-03 00:00 UTC), disk cap 60 MB over dy_* , memory: nothing buffered.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code7/rtdsstream.py --until 1793664000
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
STATUS = ROOT / ".cache" / "re" / "directional-maker" / "rtdsstream_status.json"
URL = "wss://ws-live-data.polymarket.com"
TOPICS = {"crypto_prices_chainlink": "cl", "crypto_prices_twap_sixty": "tw"}
KEEP = {"btc/usd": "btc", "eth/usd": "eth", "sol/usd": "sol", "btc": "btc", "eth": "eth", "sol": "sol"}
DISK_CAP_MB = 60
STATE: dict = {"msgs": 0, "written": 0, "reconnects": 0, "err": None}


def now_ms():
    return int(time.time() * 1000)


def disk_mb():
    tot = 0
    for part in ("dev", "sealed"):
        d = LIVE / part / "dy_rtds"
        if d.exists():
            for f in d.glob("*.jsonl.gz"):
                try:
                    tot += f.stat().st_size
                except OSError:
                    pass
    return tot / 1e6


async def conn(topic, w, stop):
    import websockets
    tp = TOPICS[topic]
    while not stop.is_set():
        try:
            async with websockets.connect(URL, open_timeout=15, max_size=2 ** 22, ping_interval=None, close_timeout=2) as ws:
                await ws.send(json.dumps({"action": "subscribe", "subscriptions": [{"topic": topic, "type": "*", "filters": ""}]}))
                w.write({"k": "conn", "t": now_ms(), "tp": tp, "ev": "open"})
                lp = time.time()
                last_msg = time.time()
                while not stop.is_set():
                    if time.time() - lp > 5:
                        await ws.send("PING")
                        lp = time.time()
                    if time.time() - last_msg > 30:
                        raise RuntimeError("no message for 30 s")
                    try:
                        m = await asyncio.wait_for(ws.recv(), timeout=1)
                    except asyncio.TimeoutError:
                        continue
                    last_msg = time.time()
                    if not m or m == "PONG":
                        continue
                    STATE["msgs"] += 1
                    try:
                        j = json.loads(m)
                    except Exception:
                        continue
                    if j.get("type") != "update":
                        continue
                    p = j.get("payload") or {}
                    sy = KEEP.get(str(p.get("symbol", "")).lower())
                    if not sy:
                        continue
                    w.write({"k": "u", "tp": tp, "sy": sy, "v": p.get("value"), "ts": p.get("timestamp"),
                             "P": j.get("timestamp"), "t": now_ms()})
                    STATE["written"] += 1
        except Exception as e:  # reconnect
            STATE["reconnects"] += 1
            STATE["err"] = f"{time.strftime('%H:%M:%S')} {tp} {e!r}"[:200]
            try:
                w.write({"k": "conn", "t": now_ms(), "tp": tp, "ev": "close", "err": repr(e)[:120]})
            except Exception:
                pass
            await asyncio.sleep(2)


async def clock(w, stop):
    import httpx
    while not stop.is_set():
        try:
            def go():
                offs = []
                with httpx.Client(timeout=5) as c:
                    for _ in range(5):
                        t0 = time.time()
                        r = c.get("https://fapi.binance.com/fapi/v1/time")
                        t1 = time.time()
                        offs.append((r.json()["serverTime"] / 1000 - (t0 + t1) / 2, t1 - t0))
                offs.sort(key=lambda x: x[1])
                return offs[0]
            off, rtt = await asyncio.to_thread(go)
            w.write({"k": "clk", "t": now_ms(), "off": round(off, 4), "rtt": round(rtt, 4)})
        except Exception as e:
            STATE["err"] = f"clk {e!r}"[:200]
        for _ in range(600):
            if stop.is_set():
                return
            await asyncio.sleep(1)


async def supervisor(stop, until, w):
    while not stop.is_set():
        mb = disk_mb()
        if mb > DISK_CAP_MB or time.time() >= until:
            STATE["stop_reason"] = "disk" if mb > DISK_CAP_MB else "hard_stop"
            stop.set()
        STATE.update({"pid": os.getpid(), "updated": int(time.time()), "disk_mb": round(mb, 2), "hard_stop": int(until)})
        try:
            STATUS.write_text(json.dumps(STATE, indent=1))
        except Exception:
            pass
        w.flush()
        await asyncio.sleep(10)


async def main(until):
    stop = asyncio.Event()
    w = live.Writer("dy_rtds")
    try:
        await asyncio.gather(supervisor(stop, until, w), clock(w, stop),
                             *[conn(t, w, stop) for t in TOPICS])
    finally:
        w.close()
        STATE["ended"] = int(time.time())
        STATUS.write_text(json.dumps(STATE, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", type=float, default=1793664000)  # 2026-11-03 00:00 UTC
    a = ap.parse_args()
    asyncio.run(main(a.until))
