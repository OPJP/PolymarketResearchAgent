"""Own recorder v2 (iteration 7, X88 = information panel iter6 P2; v1 iteration 3, X24): OpenDota /api/live (public,
no key) while ANY Polymarket Dota 2 event is in play (v1: PARI Universe only), polled every 15 s (v1 30 s), records
filed by UNIT through code/iter5/unit_writer.py: a record is sealed if the Dota game's activate_time, or that time
minus 30 min (fail closed near block edges), lies in a sealed block; also by receive time (live.Writer rule).
v1 docstring follows.

Every 10 min it lists open Gamma events of the Dota 2 series (10309) in the wallet's Dota 2 league (PARI Universe, the
only one it traded) with a game start in [now - 4 h, now + 10 min].
Only while at least one is in play does it poll https://api.opendota.com/api/live every POLL_S seconds (about 143 KB per
poll) and keep league games only (league_id > 0), as compact records:
  {"k": "g", "t": recv_ms, "m": match_id, "l": league_id, "rt": radiant team, "dt": dire team, "rs": radiant_score,
   "ds": dire_score, "rl": radiant_lead, "gt": game_time, "lu": last_update_time, "dl": delay, "bs": building_state}
Records go through tools/live.py Writer (feed "tommy_dota_live"), so they are filed into dev or sealed folders by the
calendar block of their receive time; this agent reads dev blocks only (iter_live). Purpose: lead-lag of the wallet's
Dota 2 taker orders (signing ms) against a public, spectator-delayed game-state feed (field `delay`).
Limits: hard stop HARD_STOP (2026-11-03 00:00 UTC), stops when its folders exceed DISK_MAX_MB, tiny memory.
Run detached:  .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter3/dota_live_recorder.py
"""
import calendar
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter5"))
import unit_writer  # noqa: E402

FEED = "tommy_dota_live"
HARD_STOP = 1793664000
DISK_MAX_MB = 150
POLL_S = 15
STATUS = ROOT / ".cache/re/tommy-cs2-maker/dota_recorder_v2_status.json"


def feed_mb():
    tot = 0
    for part in ("dev", "sealed"):
        p = live.LIVE / part / FEED
        if p.exists():
            tot += sum(f.stat().st_size for f in p.glob("*.gz"))
    return tot / 1e6


def dota_live(cli):
    now = time.time()
    n = 0
    try:
        r = cli.get("https://gamma-api.polymarket.com/events", params={"series_id": "10309", "closed": "false", "limit": 100})
        for e in r.json():
            meta = e.get("eventMetadata") or {}
            for m in e.get("markets") or []:
                gs = m.get("gameStartTime") or e.get("startTime")
                try:
                    g = calendar.timegm(time.strptime(str(gs)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
                except Exception:  # noqa: BLE001
                    continue
                if now - 4 * 3600 <= g <= now + 600:
                    n += 1
    except Exception:  # noqa: BLE001
        return -1
    return n


def main():
    w = unit_writer.UnitWriter(FEED)
    cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea-research"})
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 2, "polls": 0, "written": 0, "last_error": None, "active": False}
    next_check, active = 0.0, False
    while time.time() < HARD_STOP and feed_mb() < DISK_MAX_MB:
        now = time.time()
        if now >= next_check:
            k = dota_live(cli)
            active = k > 0
            st.update({"active": active, "dota_markets_in_play": k})
            next_check = now + 600
        if active:
            try:
                d = cli.get("https://api.opendota.com/api/live").json()
                t = int(time.time() * 1000)
                for g in d:
                    if not g.get("league_id"):
                        continue
                    at = float(g.get("activate_time") or 0) or time.time()
                    sealed_u = unit_writer.unit_sealed(at) or unit_writer.unit_sealed(at - 1800)
                    w.write({"k": "g", "t": t, "m": g.get("match_id"), "l": g.get("league_id"), "rt": g.get("team_name_radiant"),
                             "dt": g.get("team_name_dire"), "rs": g.get("radiant_score"), "ds": g.get("dire_score"),
                             "rl": g.get("radiant_lead"), "gt": g.get("game_time"), "lu": g.get("last_update_time"),
                             "dl": g.get("delay"), "bs": g.get("building_state"), "at": at, "v": 2}, sealed_u)
                    st["written"] += 1
                st["polls"] += 1
                w.flush()
            except Exception as e:  # noqa: BLE001
                st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
        st.update({"updated": int(time.time()), "disk_mb": round(feed_mb(), 2)})
        STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
        time.sleep(POLL_S if active else 60)
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
