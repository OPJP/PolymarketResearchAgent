"""Own recorder (iteration 10, X133 = information panel iter-9 P2): an external in-play price for CS2, key-free.

bo3.gg's public live index (verified 2026-11-01 03:57 UTC: HTTP 200, ~1.4 KB per live match, keys total/results/links)
  https://api.bo3.gg/api/v1/matches?filter[matches.status][in]=current&filter[matches.discipline_id][eq]=1
carries, per live CS2 match, `bet_updates`: Thunderpick's odds object (team_1 / team_2 {name, coeff, active, team_id,
max_coeff, aggrement_score}, provider, markets_count, additional_markets [{bet_type, coeff, active, ...}]), plus the
maps score. ONE request covers every live match, so the recorder polls only the index (every POLL_S = 3 s, i.e.
< 0.4 request/s to one host) and never a per-match page or a bookmaker site.

Record (feed "tommy_tp_odds", filed by code/iter5/unit_writer.py), written only when a match's state changes, stamped
with the receive time of the first poll that saw it:
  {"k":"B","t":recv_ms,"rtt":ms,"id":bo3 id,"slug":..,"sd":start_date,"st":status,"s1":team1_score,"s2":team2_score,
   "n1":name1,"c1":coeff1,"a1":active1,"m1":max_coeff1,"n2":..,"c2":..,"a2":..,"m2":..,"mc":markets_count,
   "am":[[bet_type,coeff,active],...],"lu":live_updates (<= 300 chars),"ev":matched Polymarket slug or null,"gs":its game start}
Matching: Gamma open CS2 events (series 10310) with a game start in [now - 8 h, now + 20 min], team names of the
moneyline outcomes vs bet_updates team names (normalized containment, as tommy_dota_rt), refreshed every 10 min.
Filing (unit rule, fail closed): sealed iff the bo3 start_date, the matched event's game start, or either minus 30 min
lies in a sealed block, or the receive time does (UnitWriter). Unmatched matches are filed by the same rule on start_date.
Limits: hard stop HARD_STOP (2026-11-02 06:00 UTC), stops when its folders exceed DISK_MAX_MB, small memory.
Purpose (pre-registered in NOTES iteration 10): cadence and suspensions of Thunderpick's in-play odds; lead-lag of the
de-margined p_TP against the others' mid and the wallet's add levels; SD of the wallet's burst top minus p_TP vs 3.2c
against the mid; within one tick of round(p_TP - delta) vs the touch; p_TP changes vs the feed's messages.
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter10/tp_odds_recorder.py
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

FEED = "tommy_tp_odds"
HARD_STOP = 1793599200  # 2026-11-02 06:00 UTC
DISK_MAX_MB = 150
POLL_S = 3.0
GAMMA_S = 600.0
STATUS = ROOT / ".cache/re/tommy-cs2-maker/tp_odds_recorder_status.json"
IDX = "https://api.bo3.gg/api/v1/matches"
PARAMS = {"filter[matches.status][in]": "current", "filter[matches.discipline_id][eq]": "1", "page[limit]": "50"}


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
    """Open Polymarket CS2 events with a game start in [now - 8 h, now + 20 min]: (slug, gs, [names])."""
    now = time.time()
    out = []
    for off in (0, 100, 200, 300):
        r = cli.get("https://gamma-api.polymarket.com/events", params={"series_id": "10310", "closed": "false", "limit": 100, "offset": off})
        d = r.json() or []
        for e in d:
            gs = [gts(m.get("gameStartTime")) for m in e.get("markets") or []]
            gs = [g for g in gs if g]
            if not gs:
                continue
            g = min(gs)
            if not (now - 8 * 3600 <= g <= now + 1200):
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
        n = len(d)
        del d
        if n < 100:
            break
    return out


def match_event(n1, n2, evs):
    a, b = norm(n1), norm(n2)
    for slug, gs, names in evs:
        if any(sim(a, x) for x in names) and any(sim(b, x) for x in names):
            return slug, gs
    return None, None


def compact(x):
    bu = x.get("bet_updates") or {}
    t1, t2 = bu.get("team_1") or {}, bu.get("team_2") or {}
    am = [[m.get("bet_type"), m.get("coeff"), 1 if m.get("active") else 0] for m in (bu.get("additional_markets") or [])][:40]
    lu = x.get("live_updates")
    return {"id": x.get("id"), "slug": x.get("slug"), "sd": x.get("start_date"), "st": x.get("status"),
            "s1": x.get("team1_score"), "s2": x.get("team2_score"),
            "n1": t1.get("name"), "c1": t1.get("coeff"), "a1": 1 if t1.get("active") else 0, "m1": t1.get("max_coeff"),
            "n2": t2.get("name"), "c2": t2.get("coeff"), "a2": 1 if t2.get("active") else 0, "m2": t2.get("max_coeff"),
            "mc": bu.get("markets_count"), "pv": bu.get("provider"), "am": am,
            "lu": (json.dumps(lu, separators=(",", ":"))[:300] if lu is not None else None)}


def main():
    w = unit_writer.UnitWriter(FEED)
    cli = httpx.Client(timeout=10, headers={"User-Agent": "polyrea-research"})
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 1, "polls": 0, "records": 0, "live_max": 0,
          "matched": 0, "errors": 0, "last_error": None}
    evs, next_gamma = [], 0.0
    last = {}
    while time.time() < HARD_STOP and feed_mb() < DISK_MAX_MB:
        t0 = time.time()
        try:
            if t0 >= next_gamma:
                next_gamma = t0 + GAMMA_S
                try:
                    evs = pm_events(cli)
                except Exception as e:  # noqa: BLE001
                    st["last_error"] = f"gamma {time.strftime('%H:%M:%S')} {e!r}"[:200]
                st["pm_events_in_window"] = len(evs)
            r = cli.get(IDX, params=PARAMS)
            rtt = int((time.time() - t0) * 1000)
            st["polls"] += 1
            if r.status_code == 200:
                res = (r.json() or {}).get("results") or []
                st["live_max"] = max(st["live_max"], len(res))
                nm = 0
                for x in res:
                    c = compact(x)
                    key = c["id"]
                    sig = json.dumps([c[k] for k in ("st", "s1", "s2", "c1", "a1", "c2", "a2", "mc", "am", "lu")], separators=(",", ":"))
                    if last.get(key) == sig:
                        continue
                    last[key] = sig
                    slug, gs = match_event(c["n1"], c["n2"], evs) if evs else (None, None)
                    nm += slug is not None
                    sd = gts(c["sd"])
                    starts = [s for s in (sd, gs) if s]
                    sealed_u = (not starts) or any(unit_writer.unit_sealed(s) or unit_writer.unit_sealed(s - 1800) for s in starts)
                    rec = {"k": "B", "t": int(t0 * 1000), "rtt": rtt, "ev": slug, "gs": gs}
                    rec.update(c)
                    w.write(rec, sealed_u)
                    st["records"] += 1
                st["matched"] = max(st["matched"], nm)
                del res
            else:
                st["errors"] += 1
                st["last_error"] = f"{time.strftime('%H:%M:%S')} HTTP {r.status_code}"
            w.flush()
        except Exception as e:  # noqa: BLE001
            st["errors"] += 1
            st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
        st.update({"updated": int(time.time()), "disk_mb": round(feed_mb(), 2)})
        try:
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        if st["errors"] > 2000:
            break
        time.sleep(max(0.5, POLL_S - (time.time() - t0)))
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
