"""Event-level listing metadata for every CS2 Gamma event (series 10310) listed 25 Sep..H with game start < H.
Keeps listing-time fields only (eventMetadata incl. gridSeriesId, resolutionSource, createdAt); drops any event whose
earliest market gameStartTime is >= H before anything else is read. Output: .cache/re/tommy-cs2-maker/events_meta.parquet"""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402
H = 1792713600
OUT = ROOT / ".cache/re/tommy-cs2-maker"

def ts(s):
    if not s: return None
    try:
        return int(pd.Timestamp(str(s).replace("+00", "+00:00") if str(s).endswith("+00") else s).tz_convert("UTC").timestamp())
    except Exception:
        try: return int(pd.Timestamp(s).timestamp())
        except Exception: return None

def main():
    h = shared_client(); rows = []; keys = {}
    off = 0
    while True:
        params = {"series_id": "10310", "start_date_min": "2026-09-25T00:00:00Z", "start_date_max": "2026-10-23T00:00:00Z", "limit": 100, "offset": off}
        d, _ = h.get_json("https://gamma-api.polymarket.com/events", params, adapter="gamma.events", max_age=None)
        if not d: break
        for e in d:
            mk = e.get("markets") or []
            gss = [ts(m.get("gameStartTime")) for m in mk if m.get("gameStartTime")]
            gss = [g for g in gss if g]
            if not gss or min(gss) >= H:  # sealed or unscheduled unit: drop unread
                continue
            meta = e.get("eventMetadata")
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except Exception: meta = {}
            meta = meta or {}
            for k in meta: keys[k] = keys.get(k, 0) + 1
            rows.append({"event_slug": e.get("slug"), "event_id": e.get("id"), "gs_min": min(gss),
                         "created_at": ts(e.get("createdAt")), "start_date": ts(e.get("startDate")),
                         "resolution_source": e.get("resolutionSource") or (mk[0].get("resolutionSource") if mk else None),
                         "grid_series_id": meta.get("gridSeriesId"), "league": meta.get("league"), "league_tier": meta.get("leagueTier"),
                         "pandascore_id": meta.get("pandascoreMatchId"), "meta_json": json.dumps(meta),
                         "n_markets": len(mk), "n_ml": sum(1 for m in mk if m.get("sportsMarketType") in ("moneyline", "child_moneyline")),
                         "event_keys": ",".join(sorted(k for k in e.keys()))})
        if len(d) < 100: break
        off += 100
    df = pd.DataFrame(rows).drop_duplicates("event_slug")
    df.to_parquet(OUT / "events_meta.parquet", index=False)
    print(len(df), "events; eventMetadata keys:", keys)
    print(df[["grid_series_id"]].notna().sum().to_dict())
    print(df.iloc[0].to_dict())

if __name__ == "__main__":
    main()
