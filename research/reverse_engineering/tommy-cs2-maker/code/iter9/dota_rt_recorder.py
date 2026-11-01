"""Own recorder (iteration 9, X118 = information panel iter8 P1): Valve's key-free Dota 2 spectator state.

Endpoints (verified 2026-11-01 02:07 UTC, key-free, HTTP 200; the api.steampowered.com versions need a key):
  https://www.dota2.com/webapi/IDOTA2League/GetLiveGames/v001                      (live league games, ~3 KB)
  https://www.dota2.com/webapi/IDOTA2MatchStats/GetRealtimeStats/v001?server_steam_id=<id>   (~10 KB, new snapshot ~4 s)

What it records (feed "tommy_dota_rt", filed through code/iter5/unit_writer.py):
  * every 30 s, one record per live league game in GetLiveGames:
      {"k":"L","t":recv_ms,"m":match_id,"l":league_id,"sid":server_steam_id,"rn":radiant_name,"dn":dire_name,
       "tm":time,"sp":spectators,"ev":matched Polymarket event slug or null,"gs":that event's game start}
  * every POLL_S (1 s), for every live game matched to an open Polymarket Dota 2 event (team names vs the moneyline
    outcomes), GetRealtimeStats; a record only when the snapshot changes (match.timestamp), stamped with the receive
    time of the first poll that saw it:
      {"k":"S","t":recv_ms,"rtt":ms,"m":match_id,"sid":..,"ev":slug,"gs":..,"ts":match.timestamp,"st":start_timestamp,
       "gt":game_time,"gst":game_state,"tm":[[team_number,score,net_worth,[[playerid,heroid,kills,deaths,assists,
       net_worth,gold,level,x,y],...]],...],"bd":[[team,type,destroyed_flag]...] (compact),"gg":last graph_gold}
Filing (the brief's unit rule): a record of a matched game is sealed iff its Polymarket event's game start, or that
time minus 30 min (fail closed at block edges), is in a sealed block, or its receive time is in a sealed block.
Unmatched games are not Polymarket units; they are filed by receive time only.
Limits: hard stop HARD_STOP (2026-11-03 00:00 UTC), stops when its folders exceed DISK_MAX_MB, small memory.
Purpose (pre-registered in NOTES iteration 9): lag of the feed's Dota takes and of the wallet's 10-share ladder events
behind the first snapshot that shows the bought team's kill; net-worth / position changes before takes without a kill.
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter9/dota_rt_recorder.py
"""
import calendar
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter5"))
import unit_writer  # noqa: E402

FEED = "tommy_dota_rt"
HARD_STOP = 1793664000
DISK_MAX_MB = 250
POLL_S = 1.0
LIST_S = 30.0
GAMMA_S = 600.0
STATUS = ROOT / ".cache/re/tommy-cs2-maker/dota_rt_recorder_status.json"
LG = "https://www.dota2.com/webapi/IDOTA2League/GetLiveGames/v001"
RT = "https://www.dota2.com/webapi/IDOTA2MatchStats/GetRealtimeStats/v001"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def sim(a, b):
    return bool(a) and bool(b) and (a in b or b in a or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]))


def feed_mb():
    tot = 0
    for part in ("dev", "sealed"):
        p = live.LIVE / part / FEED
        if p.exists():
            tot += sum(f.stat().st_size for f in p.glob("*.gz"))
    return tot / 1e6


def gts(s):
    try:
        return calendar.timegm(time.strptime(str(s)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
    except Exception:  # noqa: BLE001
        return None


def pm_events(cli):
    """Open Polymarket Dota 2 events with a game start in [now - 6 h, now + 15 min]: (slug, gs, [names])."""
    now = time.time()
    out = []
    for off in (0, 100, 200):
        r = cli.get("https://gamma-api.polymarket.com/events", params={"series_id": "10309", "closed": "false", "limit": 100, "offset": off})
        d = r.json() or []
        for e in d:
            gs = [gts(m.get("gameStartTime")) for m in e.get("markets") or []]
            gs = [g for g in gs if g]
            if not gs:
                g0 = gts(e.get("startTime"))
                gs = [g0] if g0 else []
            if not gs:
                continue
            g = min(gs)
            if not (now - 6 * 3600 <= g <= now + 900):
                continue
            names = set()
            for m in e.get("markets") or []:
                if m.get("sportsMarketType") == "moneyline":
                    try:
                        names |= {norm(o) for o in json.loads(m.get("outcomes") or "[]")}
                    except Exception:  # noqa: BLE001
                        pass
            if len(names) >= 2:
                out.append((e.get("slug"), g, sorted(names)))
        if len(d) < 100:
            break
    return out


def match_event(g, evs):
    rn, dn = norm(g.get("radiant_name")), norm(g.get("dire_name"))
    for slug, gs, names in evs:
        if any(sim(rn, x) for x in names) and any(sim(dn, x) for x in names):
            return slug, gs
    return None, None


def compact(j):
    m = j.get("match") or {}
    tm = []
    for t in j.get("teams") or []:
        pl = [[p.get("playerid"), p.get("heroid"), p.get("kill_count"), p.get("death_count"), p.get("assists_count"),
               p.get("net_worth"), p.get("gold"), p.get("level"), round(float(p.get("x") or 0), 3), round(float(p.get("y") or 0), 3)]
              for p in t.get("players") or []]
        tm.append([t.get("team_number"), t.get("score"), t.get("net_worth"), pl])
    bd = []
    for b in j.get("buildings") or []:
        bd.append([b.get("team"), b.get("type"), 1 if b.get("destroyed") else 0])
    gg = ((j.get("graph_data") or {}).get("graph_gold") or [None])[-1]
    return {"ts": m.get("timestamp"), "st": m.get("start_timestamp"), "gt": m.get("game_time"), "gst": m.get("game_state"),
            "tm": tm, "bd": bd, "gg": gg}


def main():
    w = unit_writer.UnitWriter(FEED)
    cli = httpx.Client(timeout=10, headers={"User-Agent": "polyrea-research"})
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 2, "list_polls": 0, "rt_polls": 0, "snapshots": 0,
          "matched_games": 0, "last_error": None}
    evs, next_gamma, next_list = [], 0.0, 0.0
    matched = {}  # server_steam_id -> (match_id, slug, gs)
    last_ts = {}
    while time.time() < HARD_STOP and feed_mb() < DISK_MAX_MB:
        now = time.time()
        try:
            if now >= next_gamma:
                next_gamma = now + GAMMA_S  # set first: a failing Gamma call is retried after GAMMA_S, not every loop
                evs = pm_events(cli)
                st["pm_events_in_window"] = len(evs)
            if now >= next_list:
                next_list = now + LIST_S
                d = cli.get(LG).json() or {}
                t = int(time.time() * 1000)
                newm = {}
                for g in d.get("games") or []:
                    if not g.get("league_id"):
                        continue
                    slug, gs = match_event(g, evs) if evs else (None, None)
                    sealed_u = (gs is not None) and (unit_writer.unit_sealed(gs) or unit_writer.unit_sealed(gs - 1800))
                    w.write({"k": "L", "t": t, "m": g.get("match_id"), "l": g.get("league_id"), "sid": g.get("server_steam_id"),
                             "rn": g.get("radiant_name"), "dn": g.get("dire_name"), "tm": g.get("time"), "sp": g.get("spectators"),
                             "ev": slug, "gs": gs}, sealed_u)
                    if slug is not None and g.get("server_steam_id"):
                        newm[str(g.get("server_steam_id"))] = (g.get("match_id"), slug, gs)
                matched = newm
                st["list_polls"] += 1
                st["matched_games"] = len(matched)
            for sid, (mid, slug, gs) in list(matched.items()):
                t0 = time.time()
                x = cli.get(RT, params={"server_steam_id": sid})
                rtt = int((time.time() - t0) * 1000)
                st["rt_polls"] += 1
                if x.status_code != 200:
                    continue
                c = compact(x.json() or {})
                if c["ts"] is None or last_ts.get(sid) == c["ts"]:
                    continue
                last_ts[sid] = c["ts"]
                sealed_u = unit_writer.unit_sealed(gs) or unit_writer.unit_sealed(gs - 1800)
                rec = {"k": "S", "t": int(t0 * 1000), "rtt": rtt, "m": mid, "sid": sid, "ev": slug, "gs": gs}
                rec.update(c)
                w.write(rec, sealed_u)
                st["snapshots"] += 1
            w.flush()
        except Exception as e:  # noqa: BLE001
            st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
        st.update({"updated": int(time.time()), "disk_mb": round(feed_mb(), 2)})
        try:
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        time.sleep(POLL_S if matched else 5.0)
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
