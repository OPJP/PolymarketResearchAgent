"""Own live recorder, iteration 4 (assumptions panel iter3 P1b): CLOB market-channel books of the ROUND markets
(round handicap, round totals, map handicap, total maps; every CS2 sportsMarketType except moneyline /
child_moneyline) of NON-GRID CS2 events in play whose gameStartTime lies in a DEVELOPMENT block. Purpose: test whether
any public book of the wallet's events moves before its taker signing (server clock), i.e. extend "nothing public
precedes" from the match / map books to the whole event.
Same record format and near-touch filter as code/iter2/cs2_recorder.py (feed tommy_cs2_near), feed "tommy_cs2_rounds",
filed by live.Writer. It records ONLY while the current 6-h block is a development block (idle in sealed blocks) and
subscribes only to units that started in a development block, so it writes no sealed unit at all.
  {"k": "f"|"pc"|"x"|"sub", ...} as in cs2_recorder.py; "sub" values are [tok0, tok1, gameStartTime, slug, smt].
Limits: hard stop 2026-11-03 00:00 UTC, 200 MB on disk, small memory footprint.
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter4/round_recorder.py
"""
from __future__ import annotations

import asyncio
import calendar
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402

FEED = "tommy_cs2_rounds"
KEY = "tommy-cs2-maker"
HARD_STOP = 1793664000  # 2026-11-03 00:00 UTC
DISK_MAX_MB = 200
NEAR = 0.05  # keep price changes within 5c of the best bid / ask
SNAP_W = 0.10  # snapshots keep levels within 10c of the best
F_EVERY = 30000  # unforced snapshot at most every 30 s per token (forced when the best moves >= 2c)
STATUS = ROOT / ".cache/re/tommy-cs2-maker/round_recorder_status.json"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"


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
        return out  # idle in sealed blocks
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
                continue  # GRID events: not the wallet's universe
            for m in e.get("markets") or []:
                smt = m.get("sportsMarketType")
                if smt in ("moneyline", "child_moneyline", None):
                    continue
                gs = m.get("gameStartTime") or e.get("startTime")
                try:
                    g = calendar.timegm(time.strptime(str(gs)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
                except Exception:
                    continue
                if not (now - 5 * 3600 <= g <= now + 1800):
                    continue
                if sealed.is_sealed(g, KEY):
                    continue  # unit started in a sealed block
                toks = m.get("clobTokenIds")
                toks = json.loads(toks) if isinstance(toks, str) else toks
                if toks and len(toks) == 2:
                    out[m["conditionId"]] = [str(toks[0]), str(toks[1]), int(g), m.get("slug"), smt]
        if len(d) < 100:
            break
    return out


async def main() -> None:
    import websockets

    w = live.Writer(FEED)
    st = {"pid": os.getpid(), "started": int(time.time()), "msgs": 0, "written": 0, "reconnects": 0, "markets": 0, "last_error": None}
    stop = asyncio.Event()
    current: dict = {}

    books: dict = {}
    last_f: dict = {}
    last_best: dict = {}

    def snap(a, now_ms, s, force):
        """Near-touch snapshot (levels within SNAP_W of the best), at most every F_EVERY ms unless forced."""
        if not force and now_ms - last_f.get(a, 0) < F_EVERY:
            return
        bd, od = books[a]
        bb = max(bd) if bd else 0.0
        ba = min(od) if od else 1.0
        w.write({"k": "f", "t": now_ms, "s": s, "a": a,
                 "b": sorted([[p, z] for p, z in bd.items() if p >= bb - SNAP_W - 1e-9], reverse=True),
                 "o": sorted([[p, z] for p, z in od.items() if p <= ba + SNAP_W + 1e-9])})
        st["written"] += 1
        last_f[a] = now_ms
        last_best[a] = (bb, ba)

    async def run(markets: dict, gen_box: dict, gen: int) -> None:
        keep = {v[0] for v in markets.values()}
        tokens = sorted({t for v in markets.values() for t in v[:2]})
        while not stop.is_set() and gen_box["gen"] == gen:
            try:
                async with websockets.connect(live.CLOB_WS, open_timeout=15, ping_interval=20, max_size=2**24, max_queue=8192) as ws:
                    await ws.send(json.dumps({"assets_ids": tokens, "type": "market"}))
                    last_ping = time.time()
                    while not stop.is_set() and gen_box["gen"] == gen:
                        if time.time() - last_ping > 10:
                            await ws.send("PING")
                            last_ping = time.time()
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        if msg == "PONG":
                            continue
                        now_ms = int(time.time() * 1000)
                        st["msgs"] += 1
                        try:
                            j = json.loads(msg)
                        except ValueError:
                            continue
                        for it in (j if isinstance(j, list) else [j]):
                            ev = it.get("event_type")
                            s = int(it.get("timestamp") or 0)
                            if ev == "book" or ("bids" in it and "asks" in it):
                                a = it.get("asset_id")
                                if a in keep:
                                    bd = {float(x["price"]): float(x["size"]) for x in it.get("bids", [])}
                                    od = {float(x["price"]): float(x["size"]) for x in it.get("asks", [])}
                                    books[a] = (bd, od)
                                    snap(a, now_ms, s, force=False)
                            elif "price_changes" in it:
                                by = {}
                                for ch in it["price_changes"]:
                                    a = ch.get("asset_id")
                                    if a not in keep or a not in books:
                                        continue
                                    bd, od = books[a]
                                    p, z = float(ch["price"]), float(ch["size"])
                                    book = bd if ch.get("side") == "BUY" else od
                                    if z == 0:
                                        book.pop(p, None)
                                    else:
                                        book[p] = z
                                    bb = max(bd) if bd else 0.0
                                    ba = min(od) if od else 1.0
                                    near = (ch.get("side") == "BUY" and p >= bb - NEAR - 1e-9) or (ch.get("side") != "BUY" and p <= ba + NEAR + 1e-9)
                                    if near:
                                        by.setdefault(a, []).append([ch.get("side"), p, z])
                                for a, c in by.items():
                                    w.write({"k": "pc", "t": now_ms, "s": s, "a": a, "c": c})
                                    st["written"] += 1
                                    bd, od = books[a]
                                    bb = max(bd) if bd else 0.0
                                    ba = min(od) if od else 1.0
                                    lb = last_best.get(a)
                                    if lb is None or abs(bb - lb[0]) >= 0.02 - 1e-9 or abs(ba - lb[1]) >= 0.02 - 1e-9:
                                        snap(a, now_ms, s, force=True)
                            elif ev == "last_trade_price":
                                a = it.get("asset_id")
                                w.write({"k": "x", "t": now_ms, "s": s, "a": a, "p": float(it.get("price") or 0), "z": float(it.get("size") or 0),
                                         "d": it.get("side"), "h": it.get("transaction_hash")})
                                st["written"] += 1
            except Exception as e:  # noqa: BLE001
                st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
            if stop.is_set() or gen_box["gen"] != gen:
                return
            st["reconnects"] += 1
            await asyncio.sleep(3)

    async def flusher() -> None:
        while not stop.is_set():
            await asyncio.sleep(5)
            w.flush()
            mb = feed_mb()
            st.update({"updated": int(time.time()), "disk_mb": round(mb, 1), "markets": len(current)})
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
            if time.time() >= HARD_STOP or mb > DISK_MAX_MB:
                stop.set()

    ft = asyncio.create_task(flusher())
    gen_box = {"gen": 0}
    conn = None
    while not stop.is_set():
        try:
            new = await pick()
        except Exception as e:  # noqa: BLE001
            st["last_error"] = f"pick {e!r}"[:200]
            new = current
        if set(new) != set(current):
            gen_box["gen"] += 1
            old = conn
            conn = asyncio.create_task(run(new, gen_box, gen_box["gen"])) if new else None
            if new:
                w.write({"k": "sub", "t": int(time.time() * 1000), "m": new})
            current = new
            await asyncio.sleep(2)
            if old:
                old.cancel()
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
