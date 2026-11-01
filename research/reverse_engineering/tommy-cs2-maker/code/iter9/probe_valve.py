"""Iteration 9 (X118 = information panel iter8 P1): verify Valve's key-free Dota endpoints. Prints ONLY key names,
counts and the snapshot cadence of one league game whose team names match NO open Polymarket Dota 2 listing
(listing projection: names only), so no Polymarket unit (sealed or not) is looked at."""
import json, re, time, sys
import httpx

def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

cli = httpx.Client(timeout=20, headers={"User-Agent": "polyrea-research"})
r = cli.get("https://www.dota2.com/webapi/IDOTA2League/GetLiveGames/v001")
print("GetLiveGames", r.status_code, len(r.content))
d = r.json()
games = d.get("games") or d.get("result", {}).get("games") or []
print("top keys", list(d.keys())[:10], "n games", len(games))
if games:
    print("game keys", sorted(games[0].keys()))
# Polymarket Dota names (listing projection: outcomes only)
names = set()
for off in (0, 100):
    e = cli.get("https://gamma-api.polymarket.com/events", params={"series_id": "10309", "closed": "false", "limit": 100, "offset": off}).json()
    for ev in e:
        for m in ev.get("markets") or []:
            try:
                for o in json.loads(m.get("outcomes") or "[]"):
                    names.add(norm(o))
            except Exception:
                pass
print("polymarket dota outcome names", len(names))
def gnames(g):
    return [norm(v) for k, v in g.items() if "name" in k.lower() and isinstance(v, str)]
cand = None
for g in games:
    gn = [x for x in gnames(g) if x]
    if not g.get("league_id") or len(gn) < 2:
        continue
    hit = any(a[:5] and (a[:5] in b or b[:5] in a) for a in gn for b in names if b)
    if not hit:
        cand = g
        break
print("candidate found", cand is not None)
if cand is None:
    sys.exit(0)
sid = cand.get("server_steam_id")
ts = []
keys = None
for i in range(12):
    t0 = time.time()
    x = cli.get("https://www.dota2.com/webapi/IDOTA2MatchStats/GetRealtimeStats/v001", params={"server_steam_id": sid})
    if i == 0:
        print("GetRealtimeStats", x.status_code, len(x.content), "rtt_ms", round((time.time() - t0) * 1000))
    try:
        j = x.json()
    except Exception:
        print("non-json"); break
    if keys is None:
        keys = {k: (sorted(v.keys()) if isinstance(v, dict) else type(v).__name__) for k, v in j.items()}
        print("rt keys", json.dumps(keys)[:900])
        tm = (j.get("teams") or [{}])[0]
        print("team keys", sorted(tm.keys()) if isinstance(tm, dict) else None)
        pl = (tm.get("players") or [{}])[0] if isinstance(tm, dict) else {}
        print("player keys", sorted(pl.keys()) if isinstance(pl, dict) else None)
    m = j.get("match") or {}
    ts.append((round(time.time(), 2), m.get("timestamp"), m.get("game_time")))
    time.sleep(1.0)
# cadence only: distinct snapshot timestamps over the polls
print("distinct match.timestamp in", len(ts), "polls:", len(set(t[1] for t in ts)))
print("timestamp - recv offsets (s):", sorted(set(round(t[0] - float(t[1] or 0), 1) for t in ts))[:6] if ts and ts[0][1] else None)
