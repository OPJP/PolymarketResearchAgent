"""directional-maker iteration 8: RTDS Binance relay recorder (panel iter7 information I7-1 = X59).

code5/rawrec.py subscribed to the RTDS `crypto_prices` topic (Polymarket's Binance relay) with the Chainlink symbol
as its filter and recorded nothing. This recorder subscribes with filters "" and keeps every update of btcusdt /
ethusdt / solusdt (value, value stamp, server publish ms, receive ms), so the between-report input can be put on its
own publish clock on the 11-01 06-12 development block (and the examiner has it on the sealed blocks).
Messages of an unknown shape are written raw (first 200 per connection) so the format can be checked on a
development block. Same structure as code7/rtdsstream.py (one connection, reconnect on silence, Binance clock).

Records (feed dz_rtdsbn, tools/live.py Writer: dev/sealed by receive-time block):
  {"k":"u","tp":"bn","sy":"btc"|"eth"|"sol","v":value,"ts":value_stamp_ms,"P":server_publish_ms,"t":recv_ms}
  {"k":"raw","t":recv_ms,"m":message}   (unknown shapes, capped)
  {"k":"clk",...}, {"k":"conn",...}     as in dy_rtds
Hard stop --until (default 2026-11-03 00:00 UTC), disk cap 60 MB over dz_rtdsbn, nothing buffered.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code8/rtdsbn.py --until 1793664000
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
STATUS = ROOT / ".cache" / "re" / "directional-maker" / "rtdsbn_status.json"
URL = "wss://ws-live-data.polymarket.com"
TOPICS = {"crypto_prices": "bn"}
KEEP = {"btcusdt": "btc", "ethusdt": "eth", "solusdt": "sol", "btc/usdt": "btc", "eth/usdt": "eth", "sol/usdt": "sol"}
DISK_CAP_MB = 60
STATE: dict = {"msgs": 0, "written": 0, "raw": 0, "reconnects": 0, "err": None}


def now_ms():
    return int(time.time() * 1000)


def disk_mb():
    tot = 0
    for part in ("dev", "sealed"):
        d = LIVE / part / "dz_rtdsbn"
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
                nraw = 0
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
                    p = j.get("payload") or {}
                    sy = KEEP.get(str(p.get("symbol", "")).lower()) if isinstance(p, dict) else None
                    if j.get("type") != "update" or not sy:
                        if nraw < 200:
                            w.write({"k": "raw", "t": now_ms(), "m": m[:2000]})
                            nraw += 1
                            STATE["raw"] += 1
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
    w = live.Writer("dz_rtdsbn")
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
