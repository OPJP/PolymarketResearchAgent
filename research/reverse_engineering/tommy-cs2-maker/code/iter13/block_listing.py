"""Listing-time projection (slug, scheduled start, GRID flag, resolution-source host) of open CS2 / Dota 2 events
scheduled in the current development block. Nothing post-hoc is printed or stored."""
import json, sys, time
import httpx
B0, B1 = 1793512800, 1793534400
G = "https://gamma-api.polymarket.com/events"
out = []
with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}) as c:
    for sid, title in ((10310, "cs2"), (10309, "dota2")):
        for off in range(0, 600, 100):
            d = c.get(G, params={"series_id": sid, "closed": "false", "limit": 100, "offset": off}, timeout=20).json()
            if not d: break
            for e in d:
                em = e.get("eventMetadata") or {}
                if isinstance(em, str):
                    try: em = json.loads(em)
                    except ValueError: em = {}
                st = e.get("startTime") or ""
                try:
                    import pandas as pd
                    g = pd.Timestamp(st).timestamp()
                except Exception: continue
                if not (B0 <= g < B1): continue
                src = str(e.get("resolutionSource") or "")
                host = src.split("//")[-1].split("/")[0] if src else ""
                out.append((title, e.get("slug"), time.strftime("%H:%M", time.gmtime(g)), bool(em.get("gridSeriesId")), host,
                            src.split("/")[-1][:30] if host.endswith("kick.com") or host.endswith("twitch.tv") else ""))
            if len(d) < 100: break
for r in sorted(out, key=lambda r: r[2]): print(r)
