"""Own recorder v2 (iteration 11; X144 = information panel iter-10 P1 steps 1-2, X148 = P5 step 1).

Superset of code/iter10/tp_odds_recorder.py (feed tommy_tp_odds, v1), written to a NEW feed "tommy_tp_odds2" so the two
never share a file. Three bo3.gg request streams (all key-free, one host, total < 0.9 request/s):
  B  the live index (status=current, CS2) every POLL_S = 3 s, as v1;
  U  the upcoming index (status=upcoming, start_date < now + 90 min) every UP_S = 30 s: the PRE-GAME Thunderpick line
     (bet_updates) of matches about to start, recorded per state change (pre-game window, no game state);
  P  the per-match object api/v1/matches/<slug> for in-play matches matched to a Polymarket CS2 event whose unit is a
     DEVELOPMENT unit, round-robin, one request every PM_S = 2 s in total (cadence check: does the per-match object
     change more often than the index?).
Every record also carries bo3's live-coverage fields (lc = live_coverage, lcs = live_coverage_source,
lca = live_coverage_advantage) for X148. Record format as v1 plus "k" in {B, U, P} and those fields.
Filing (unit rule, fail closed, code/iter5/unit_writer.py): sealed iff the bo3 start_date, the matched event's game
start, or either minus 30 min lies in a sealed block, or the receive time does.
Limits: hard stop HARD_STOP (2026-11-03 00:00 UTC), stops above DISK_MAX_MB, small memory.
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter11/tp_odds_recorder_v2.py
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import live  # noqa: E402
import sealed  # noqa: E402
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter5"))
import unit_writer  # noqa: E402
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter10"))
import tp_odds_recorder as v1  # noqa: E402  (pm_events, match_event, compact, gts)

FEED = "tommy_tp_odds2"
HARD_STOP = 1793664000  # 2026-11-03 00:00 UTC
DISK_MAX_MB = 150
POLL_S, UP_S, PM_S, GAMMA_S = 3.0, 30.0, 2.0, 600.0
STATUS = ROOT / ".cache/re/tommy-cs2-maker/tp_odds_recorder_v2_status.json"
IDX = "https://api.bo3.gg/api/v1/matches"
P_CUR = {"filter[matches.status][in]": "current", "filter[matches.discipline_id][eq]": "1", "page[limit]": "50"}


def feed_mb():
    tot = 0
    for part in ("dev", "sealed"):
        p = live.LIVE / part / FEED
        if p.exists():
            tot += sum(f.stat().st_size for f in p.glob("*.gz"))
    return tot / 1e6


def cov(x):
    return {"lc": 1 if x.get("live_coverage") else 0, "lcs": x.get("live_coverage_source"),
            "lca": x.get("live_coverage_advantage")}


def sig_of(c):
    return json.dumps([c.get(k) for k in ("st", "s1", "s2", "c1", "a1", "c2", "a2", "mc", "am", "lu", "lc", "lcs")],
                      separators=(",", ":"))


def unit_is_sealed(c, gs):
    sd = v1.gts(c["sd"])
    starts = [s for s in (sd, gs) if s]
    return (not starts) or any(unit_writer.unit_sealed(s) or unit_writer.unit_sealed(s - 1800) for s in starts)


def main():
    w = unit_writer.UnitWriter(FEED)
    cli = httpx.Client(timeout=10, headers={"User-Agent": "polyrea-research"})
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 2, "polls_b": 0, "polls_u": 0, "polls_p": 0,
          "records": 0, "live_max": 0, "matched": 0, "errors": 0, "last_error": None}
    evs, next_gamma, next_up, next_pm = [], 0.0, 0.0, 0.0
    last = {}
    pm_targets, rr = [], 0

    def emit(kind, c, rtt, tq):
        key = (kind, c["id"])
        sg = sig_of(c)
        if last.get(key) == sg:
            return
        last[key] = sg
        slug, gs = v1.match_event(c["n1"], c["n2"], evs) if evs else (None, None)
        rec = {"k": kind, "t": int(tq * 1000), "rtt": rtt, "ev": slug, "gs": gs}
        rec.update(c)
        w.write(rec, unit_is_sealed(c, gs))
        st["records"] += 1

    while time.time() < HARD_STOP and feed_mb() < DISK_MAX_MB:
        t0 = time.time()
        try:
            if t0 >= next_gamma:
                next_gamma = t0 + GAMMA_S
                try:
                    evs = v1.pm_events(cli)
                except Exception as e:  # noqa: BLE001
                    st["last_error"] = f"gamma {time.strftime('%H:%M:%S')} {e!r}"[:200]
                st["pm_events_in_window"] = len(evs)
            # B: live index
            r = cli.get(IDX, params=P_CUR)
            rtt = int((time.time() - t0) * 1000)
            st["polls_b"] += 1
            tg = []
            if r.status_code == 200:
                res = (r.json() or {}).get("results") or []
                st["live_max"] = max(st["live_max"], len(res))
                nm = 0
                for x in res:
                    c = v1.compact(x)
                    c.update(cov(x))
                    emit("B", c, rtt, t0)
                    slug, gs = v1.match_event(c["n1"], c["n2"], evs) if evs else (None, None)
                    if slug:
                        nm += 1
                        if not unit_is_sealed(c, gs) and not sealed.future_block_sealed(time.time()):
                            tg.append(c["slug"])
                st["matched"] = max(st["matched"], nm)
                del res
            else:
                st["errors"] += 1
                st["last_error"] = f"{time.strftime('%H:%M:%S')} B HTTP {r.status_code}"
            pm_targets = tg
            # U: upcoming index (pre-game line)
            if time.time() >= next_up:
                next_up = time.time() + UP_S
                tu = time.time()
                pu = {"filter[matches.status][in]": "upcoming", "filter[matches.discipline_id][eq]": "1",
                      "page[limit]": "50",
                      "filter[matches.start_date][lt]": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(tu + 5400))}
                ru = cli.get(IDX, params=pu)
                st["polls_u"] += 1
                if ru.status_code == 200:
                    for x in (ru.json() or {}).get("results") or []:
                        c = v1.compact(x)
                        c.update(cov(x))
                        emit("U", c, int((time.time() - tu) * 1000), tu)
                else:
                    st["errors"] += 1
                    st["last_error"] = f"{time.strftime('%H:%M:%S')} U HTTP {ru.status_code}"
            # P: per-match objects of matched development-unit in-play matches, round-robin
            while pm_targets and time.time() >= next_pm and time.time() - t0 < POLL_S - 0.3:
                next_pm = time.time() + PM_S
                slug_b = pm_targets[rr % len(pm_targets)]
                rr += 1
                tp = time.time()
                rp = cli.get(f"{IDX}/{slug_b}")
                st["polls_p"] += 1
                if rp.status_code == 200:
                    x = rp.json() or {}
                    c = v1.compact(x)
                    c.update(cov(x))
                    emit("P", c, int((time.time() - tp) * 1000), tp)
                else:
                    st["errors"] += 1
                    st["last_error"] = f"{time.strftime('%H:%M:%S')} P HTTP {rp.status_code}"
                time.sleep(0.05)
            w.flush()
        except Exception as e:  # noqa: BLE001
            st["errors"] += 1
            st["last_error"] = f"{time.strftime('%H:%M:%S')} {e!r}"[:200]
        st.update({"updated": int(time.time()), "disk_mb": round(feed_mb(), 2), "pm_targets": len(pm_targets),
                   "dev_records": w.n_dev})
        try:
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        if st["errors"] > 3000:
            break
        time.sleep(max(0.3, POLL_S - (time.time() - t0)))
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
