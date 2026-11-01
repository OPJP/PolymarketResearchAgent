"""Own live recorder, iteration 12 (information panel iter-11 P5, X162): Kick stream clock WITHOUT video.

For the Kick channels that Gamma lists as the resolutionSource of NON-GRID CS2 (series 10310) and Dota 2 (series 10309)
events in play (scheduled start within [now - 5 h, now + 30 min]), it reads the key-free channel API
(kick.com/api/v2/channels/<slug>: the Amazon IVS playback URL and the live flag) and, while the channel is live, the IVS
HLS playlists as TEXT: the master playlist (to pick the lowest-bandwidth variant) and that variant's media playlist
every POLL_S seconds. No media segment is ever fetched; no chat, no video, no account.
Record per new media sequence (one per segment):
  {"k": "pdt", "t": recv_ms, "ch": slug, "seq": media_sequence, "pdt": end of the newest segment (ms, from the last
   #EXT-X-PROGRAM-DATE-TIME plus the durations after it), "dur": newest segment ms, "td": target duration s,
   "n": segments listed, "ll": 1 if low-latency parts are listed}
  {"k": "ch", "t": recv_ms, "ch": slug, "live": 0/1, "lsid": livestream id, "lst": livestream start text}
  {"k": "sub", "t": recv_ms, "m": {slug: [[event_slug, start_ts], ...]}}
Edge latency = t - pdt. Filed by code/iter5/unit_writer.UnitWriter (sealed if the receive time is in a sealed block OR
the channel's current unit started in a sealed block). Limits: hard stop 2026-11-03 00:00 UTC, 50 MB on disk, < 2
requests/s in total, small memory. Feed "tommy_kick_pdt".
Run detached: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter12/kick_pdt_recorder.py
"""
from __future__ import annotations

import calendar
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/iter5"))
import live  # noqa: E402
from unit_writer import UnitWriter, unit_sealed  # noqa: E402

FEED = "tommy_kick_pdt"
HARD_STOP = 1793664000
DISK_MAX_MB = 50
POLL_S = 3.0
CH_REFRESH_S = 120.0
PICK_S = 120.0
STATUS = ROOT / ".cache/re/tommy-cs2-maker/kick_pdt_recorder_status.json"
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
SERIES = ("10310", "10309")
UA = {"user-agent": "Mozilla/5.0", "accept": "application/json"}


def feed_mb() -> float:
    tot = 0
    for part in ("dev", "sealed"):
        p = live.LIVE / part / FEED
        if p.exists():
            tot += sum(f.stat().st_size for f in p.glob("*.gz"))
    return tot / 1e6


def parse_ts(s: str) -> float | None:
    try:
        base = calendar.timegm(time.strptime(s[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
        frac = 0.0
        if len(s) > 19 and s[19] == ".":
            j = 20
            while j < len(s) and s[j].isdigit():
                j += 1
            frac = float("0" + s[19:j])
        return base + frac
    except Exception:  # noqa: BLE001
        return None


def pick(c: httpx.Client) -> dict:
    now = time.time()
    out: dict = {}
    for sid in SERIES:
        for off in range(0, 500, 100):
            try:
                d = c.get(GAMMA_EVENTS, params={"series_id": sid, "closed": "false", "limit": 100, "offset": off}, timeout=20).json()
            except Exception:  # noqa: BLE001
                break
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
                if "kick.com/" not in src:
                    continue
                ch = src.split("kick.com/")[1].split("/")[0].split("?")[0].lower().strip()
                g = parse_ts(str(e.get("startTime") or ""))
                if g is None or not ch or not (now - 5 * 3600 <= g <= now + 1800):
                    continue
                out.setdefault(ch, []).append([e.get("slug"), int(g), unit_sealed(g)])
            if len(d) < 100:
                break
    return out


def ch_sealed(chans: dict, ch: str) -> bool:
    units = chans.get(ch) or []
    if not units:
        return True
    now = time.time()
    started = [u for u in units if u[1] <= now + 60]
    cur = max(started, key=lambda u: u[1]) if started else min(units, key=lambda u: u[1])
    return bool(cur[2])


def media_state(text: str) -> dict | None:
    seq, td, last_pdt, after, n, ll, lastdur = None, None, None, 0.0, 0, 0, None
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            seq = int(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-TARGETDURATION:"):
            td = float(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            last_pdt = parse_ts(line.split(":", 1)[1]); after = 0.0
        elif line.startswith("#EXT-X-PART:"):
            ll = 1
        elif line.startswith("#EXTINF:"):
            try:
                pending = float(line.split(":", 1)[1].split(",")[0])
            except ValueError:
                pending = None
        elif line and not line.startswith("#") and pending is not None:
            n += 1; after += pending; lastdur = pending; pending = None
    if seq is None or last_pdt is None:
        return None
    return {"seq": seq + n - 1, "pdt": int((last_pdt + after) * 1000), "dur": int((lastdur or 0) * 1000), "td": td, "n": n, "ll": ll}


def main() -> None:
    w = UnitWriter(FEED)
    st = {"pid": os.getpid(), "started": int(time.time()), "version": 1, "written_dev": 0, "polls": 0, "live_channels": 0,
          "errors": 0, "last_error": None}
    c = httpx.Client(headers=UA, follow_redirects=True)
    route: dict = {}
    chinfo: dict = {}   # slug -> {"next": ts, "live": bool, "media": url, "last_seq": int}
    next_pick = 0.0
    next_status = 0.0
    while True:
        now = time.time()
        if now >= HARD_STOP:
            break
        if now >= next_pick:
            try:
                new = pick(c)
                if json.dumps(new, sort_keys=True) != json.dumps(route, sort_keys=True):
                    dv = {k: [u[:2] for u in us if not u[2]] for k, us in new.items() if any(not u[2] for u in us)}
                    sv = {k: [u[:2] for u in us if u[2]] for k, us in new.items() if any(u[2] for u in us)}
                    if dv:
                        w.write({"k": "sub", "t": int(now * 1000), "m": dv}, False)
                    if sv:
                        w.write({"k": "sub", "t": int(now * 1000), "m": sv}, True)
                route = new
                for k in list(chinfo):
                    if k not in route:
                        chinfo.pop(k)
                for k in route:
                    chinfo.setdefault(k, {"next": 0.0, "live": False, "media": None, "last_seq": None})
            except Exception as e:  # noqa: BLE001
                st["errors"] += 1; st["last_error"] = f"pick {e!r}"[:200]
            next_pick = now + PICK_S
        for ch, info in chinfo.items():
            now = time.time()
            if now >= info["next"]:
                info["next"] = now + CH_REFRESH_S
                try:
                    j = c.get(f"https://kick.com/api/v2/channels/{ch}", timeout=15).json()
                    ls = j.get("livestream") if isinstance(j, dict) else None
                    is_live = bool(isinstance(ls, dict) and ls.get("is_live"))
                    w.write({"k": "ch", "t": int(now * 1000), "ch": ch, "live": int(is_live), "lsid": (ls or {}).get("id") if isinstance(ls, dict) else None,
                             "lst": (ls or {}).get("created_at") if isinstance(ls, dict) else None}, ch_sealed(route, ch))
                    info["live"] = is_live
                    info["media"] = None
                    if is_live and j.get("playback_url"):
                        mt = c.get(j["playback_url"], timeout=15).text
                        best, url = None, None
                        lines = mt.splitlines()
                        for i, line in enumerate(lines):
                            if line.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines):
                                bw = None
                                for part in line.split(":", 1)[1].split(","):
                                    if part.startswith("BANDWIDTH="):
                                        try:
                                            bw = int(part.split("=", 1)[1])
                                        except ValueError:
                                            pass
                                u = lines[i + 1].strip()
                                if bw is not None and u and not u.startswith("#") and (best is None or bw < best):
                                    best, url = bw, u
                        if url and not url.startswith("http"):
                            url = j["playback_url"].rsplit("/", 1)[0] + "/" + url
                        info["media"] = url
                except Exception as e:  # noqa: BLE001
                    st["errors"] += 1; st["last_error"] = f"{time.strftime('%H:%M:%S')} ch {ch} {e!r}"[:200]
            if info.get("live") and info.get("media"):
                try:
                    txt = c.get(info["media"], timeout=10).text
                    st["polls"] += 1
                    ms = media_state(txt)
                    if ms and ms["seq"] != info.get("last_seq"):
                        info["last_seq"] = ms["seq"]
                        w.write({"k": "pdt", "t": int(time.time() * 1000), "ch": ch, **ms}, ch_sealed(route, ch))
                except Exception as e:  # noqa: BLE001
                    st["errors"] += 1; st["last_error"] = f"{time.strftime('%H:%M:%S')} media {ch} {e!r}"[:200]
                    info["next"] = 0.0
        if time.time() >= next_status:
            w.flush()
            mb = feed_mb()
            st.update({"updated": int(time.time()), "written_dev": w.n_dev, "live_channels": sum(1 for v in chinfo.values() if v.get("live")),
                       "channels": len(chinfo), "disk_mb": round(mb, 2)})
            STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")
            next_status = time.time() + 15
            if mb > DISK_MAX_MB:
                break
        time.sleep(POLL_S)
    w.close()
    st["stopped"] = int(time.time())
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
