"""Own live recorder, iteration 4 (information panel iter3 P2, X38): a stream clock without video. Anonymous, read-only
Twitch chat (IRC over websocket, nick justinfanNNNNN, no credentials) of the stream channels that Gamma lists as the
resolutionSource of NON-GRID CS2 events in play whose game start lies in a DEVELOPMENT block.

Privacy: no message text, no user names are stored. Each record keeps only the channel, the Twitch server timestamp
(tmi-sent-ts, ms), the receive time, the message length and the number of emotes:
  {"k": "chat", "t": recv_ms, "s": tmi_sent_ts_ms, "ch": channel, "n": length, "em": emote_count}
  {"k": "sub", "t": recv_ms, "m": {channel: [event_slug, gameStartTime]}}
v2 (iteration 5, information panel iter4 critique 1): records in EVERY block, so the examiner of the future-block exam
has the chat clock. Channels come from listing-time fields only (resolutionSource, scheduled startTime, gridSeriesId).
Records are filed by code/iter5/unit_writer.UnitWriter: a chat record goes to the sealed folder if the receive time is in
a sealed block OR the channel's current unit (latest event on that channel that has started, else the next one) started
in a sealed block. The status file counts only dev-filed records. Feed "tommy_chat" (same feed as v1).
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from unit_writer import UnitWriter, unit_sealed  # noqa: E402

FEED = "tommy_chat"
KEY = "tommy-cs2-maker"
HARD_STOP = 1793664000
DISK_MAX_MB = 50
STATUS = ROOT / ".cache/re/tommy-cs2-maker/chat_recorder_v2_status.json"
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
            if not (now - 5 * 3600 <= g <= now + 1800) or not ch:
                continue
            out.setdefault(ch, []).append([e.get("slug"), int(g), unit_sealed(g)])
        if len(d) < 100:
            break
    return out


async def main() -> None:
    import websockets

    w = UnitWriter(FEED)
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 2, "written_dev": 0, "reconnects": 0, "channels_dev": 0, "last_error": None}

    route: dict = {}

    def ch_sealed(chans: dict, ch: str) -> bool:
        units = chans.get(ch) or []
        if not units:
            return True
        now = time.time()
        started = [u for u in units if u[1] <= now + 60]
        cur = max(started, key=lambda u: u[1]) if started else min(units, key=lambda u: u[1])
        return bool(cur[2])
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
                            tags, rest = line[1:].split(" ", 1)
                            tg = dict(kv.split("=", 1) for kv in tags.split(";") if "=" in kv)
                            try:
                                ch = rest.split(" PRIVMSG #", 1)[1].split(" ", 1)[0]
                                body = rest.split(" PRIVMSG #", 1)[1].split(" :", 1)[1] if " :" in rest.split(" PRIVMSG #", 1)[1] else ""
                            except IndexError:
                                continue
                            em = tg.get("emotes") or ""
                            n_em = sum(len(x.split(":")[1].split(",")) for x in em.split("/") if ":" in x) if em else 0
                            w.write({"k": "chat", "t": now_ms, "s": int(tg.get("tmi-sent-ts") or 0), "ch": ch, "n": len(body), "em": n_em},
                                    ch_sealed(route, ch))
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
            st.update({"updated": int(time.time()), "disk_ok": mb <= DISK_MAX_MB, "written_dev": w.n_dev,
                       "channels_dev": sum(1 for c in current if not ch_sealed(current, c))})
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
        changed = json.dumps(new, sort_keys=True) != json.dumps(current, sort_keys=True)
        route.clear()
        route.update(new)
        if set(new) != set(current):
            box["gen"] += 1
            if conn:
                conn.cancel()
            conn = asyncio.create_task(run(new, box["gen"])) if new else None
        if changed:
            if new:
                dv = {c: [u[:2] for u in us if not u[2]] for c, us in new.items() if any(not u[2] for u in us)}
                sv = {c: [u[:2] for u in us if u[2]] for c, us in new.items() if any(u[2] for u in us)}
                if dv:
                    w.write({"k": "sub", "t": int(time.time() * 1000), "m": dv}, False)
                if sv:
                    w.write({"k": "sub", "t": int(time.time() * 1000), "m": sv}, True)
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
