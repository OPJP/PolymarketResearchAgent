"""Point-in-time check of eventMetadata.gridSeriesId: is it set before the game starts? Lists CS2 events (series 10310)
whose start is still in the future AND inside a development block (tools/sealed.py), keeping only a projection
(slug, start, created, league, gridSeriesId present). Nothing post-hoc is read."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.http import shared_client  # noqa: E402
import sealed  # noqa: E402
KEY = "tommy-cs2-maker"

def main():
    h = shared_client(); now = time.time(); rows = []
    for off in range(0, 600, 100):
        d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"series_id": "10310", "closed": "false", "limit": 100, "offset": off}, adapter="gamma.events.live", max_age=600)
        if not d: break
        for e in d:
            st = e.get("startTime") or e.get("startDate")
            try: s = pd.Timestamp(st).timestamp()
            except Exception: continue
            if s <= now or sealed.is_sealed(s, KEY):  # only future dev-block units
                continue
            meta = e.get("eventMetadata") or {}
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except Exception: meta = {}
            rows.append({"slug": e.get("slug"), "start": pd.Timestamp(s, unit="s", tz="UTC").isoformat(), "hours_ahead": round((s - now) / 3600, 1),
                         "created_h_before": round((s - pd.Timestamp(e.get("createdAt")).timestamp()) / 3600, 1) if e.get("createdAt") else None,
                         "league": meta.get("league"), "tier": meta.get("leagueTier"), "grid": meta.get("gridSeriesId") is not None,
                         "has_key": "gridSeriesId" in meta, "regen": meta.get("context_requires_regen")})
        if len(d) < 100: break
    df = pd.DataFrame(rows)
    print(len(df)); print(df.sort_values("start").to_string(max_rows=80))

if __name__ == "__main__":
    main()
