"""Own live recorder, iteration 4 (information panel iter3 P2, X38): a stream clock without video. Anonymous, read-only
Twitch chat (IRC over websocket, nick justinfanNNNNN, no credentials) of the stream channels that Gamma lists as the
resolutionSource of NON-GRID CS2 events in play whose game start lies in a DEVELOPMENT block.

Privacy: no message text, no user names are stored. Each record keeps only the channel, the Twitch server timestamp
(tmi-sent-ts, ms), the receive time, the message length and the number of emotes:
  {"k": "chat", "t": recv_ms, "s": tmi_sent_ts_ms, "ch": channel, "n": length, "em": emote_count}
  {"k": "sub", "t": recv_ms, "m": {channel: [event_slug, gameStartTime]}}
Filed by tools/live.py Writer (feed "tommy_chat"); idles in sealed blocks and never joins a sealed unit's channel.
Limits: hard stop 2026-11-03 00:00 UTC, 50 MB on disk, small memory.
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter4/chat_recorder.py
"""
from __future__ import annotations

import asyncio
import calendar
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

FEED = "tommy_chat"
KEY = "tommy-cs2-maker"
HARD_STOP = 1793664000
DISK_MAX_MB = 50
STATUS = ROOT / ".cache/re/tommy-cs2-maker/chat_recorder_status.json"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
WS = "wss://irc-ws.chat.twitch.tv:443"


def feed_mb() -> float:
    tot = 0
    for part in ("dev", "sealed"):
        p = live.LIVE / part / FEED
        if p.exists():
            tot += sum(f.stat().st_size for f in p.glob("*.gz"))
    return tot / 1e6


async def pick() -> dict:
    now = time.time()
    out = {}
    if sealed.is_sealed(now, KEY):
        return out
    for off in range(0, 500, 100):
        d = await live._http_json(GAMMA_EVENTS, {"series_id": "10310", "closed": "false", "limit": 100, "offset": off})
        if not d:
            break
        for e in d:
            em = e.get("eventMetadata") or {}
            if isinstance(em, str):
                try:
                    em = json.loads(em)
                except ValueError:
                    em = {}
            if em.get("gridSeriesId"):
                continue
            src = str(e.get("resolutionSource") or "")
            if "twitch.tv/" not in src:
                continue
            ch = src.split("twitch.tv/")[1].split("/")[0].split("?")[0].lower().strip()
            gs = e.get("startTime")
            try:
                g = calendar.timegm(time.strptime(str(gs)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
            except Exception:  # noqa: BLE001
                continue
            if not (now - 5 * 3600 <= g <= now + 1800) or sealed.is_sealed(g, KEY) or not ch:
                continue
            out[ch] = [e.get("slug"), int(g)]
        if len(d) < 100:
            break
    return out


async def main() -> None:
    import websockets

    w = live.Writer(FEED)
    st = {"pid": os.getpid(), "started": int(time.time()), "msgs": 0, "written": 0, "reconnects": 0, "channels": 0, "last_error": None}
    stop = asyncio.Event()
    current: dict = {}
    box = {"gen": 0}

    async def run(chans: dict, gen: int) -> None:
        while not stop.is_set() and box["gen"] == gen:
            try:
                async with websockets.connect(WS, open_timeout=15, ping_interval=60, max_size=2**20) as ws:
                    await ws.send("CAP REQ :twitch.tv/tags")
                    await ws.send("PASS SCHMOOPIIE")  # Twitch anonymous placeholder (not a credential)
                    await ws.send(f"NICK justinfan{random.randint(10000, 99999)}")
                    for ch in chans:
                        await ws.send(f"JOIN #{ch}")
                    while not stop.is_set() and box["gen"] == gen:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        now_ms = int(time.time() * 1000)
                        for line in str(msg).split("\r\n"):
                            if not line:
                                continue
                            if line.startswith("PING"):
                                await ws.send("PONG :tmi.twitch.tv")
                                continue
                            if " PRIVMSG #" not in line or not line.startswith("@"):
                                continue
                            st["msgs"] += 1
                            tags, rest = line[1:].split(" ", 1)
                            tg = dict(kv.split("=", 1) for kv in tags.split(";") if "=" in kv)
                            try:
                                ch = rest.split(" PRIVMSG #", 1)[1].split(" ", 1)[0]
                                body = rest.split(" PRIVMSG #", 1)[1].split(" :", 1)[1] if " :" in rest.split(" PRIVMSG #", 1)[1] else ""
                            except IndexError:
                                continue
                            em = tg.get("emotes") or ""
                            n_em = sum(len(x.split(":")[1].split(",")) for x in em.split("/") if ":" in x) if em else 0
                            w.write({"k": "chat", "t": now_ms, "s": int(tg.get("tmi-sent-ts") or 0), "ch": ch, "n": len(body), "em": n_em})
                            st["written"] += 1
            except Exception as e:  # noqa: BLE001
                st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
            if stop.is_set() or box["gen"] != gen:
                return
            st["reconnects"] += 1
            await asyncio.sleep(5)

    async def flusher() -> None:
        while not stop.is_set():
            await asyncio.sleep(10)
            w.flush()
            mb = feed_mb()
            st.update({"updated": int(time.time()), "disk_mb": round(mb, 2), "channels": len(current)})
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
            if time.time() >= HARD_STOP or mb > DISK_MAX_MB:
                stop.set()

    ft = asyncio.create_task(flusher())
    conn = None
    while not stop.is_set():
        try:
            new = await pick()
        except Exception as e:  # noqa: BLE001
            st["last_error"] = f"pick {e!r}"[:200]
            new = current
        if set(new) != set(current):
            box["gen"] += 1
            if conn:
                conn.cancel()
            conn = asyncio.create_task(run(new, box["gen"])) if new else None
            if new:
                w.write({"k": "sub", "t": int(time.time() * 1000), "m": new})
            current = new
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(1.0, min(120.0, sealed.block_bounds(time.time())[1] - time.time() + 1.0)))
        except asyncio.TimeoutError:
            pass
    if conn:
        conn.cancel()
    ft.cancel()
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
