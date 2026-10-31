"""Enumerate every CS2 (and Dota 2) Gamma event/market listed in the development period.

Gamma /events?series_id=... paged by listing startDate. Keeps listing-time metadata only
(slug, sportsMarketType, gameStartTime, tokens, tick, league tier); resolution fields are kept
in a separate column group used ONLY for settlement.
Output: .cache/re/tommy-cs2-maker/universe.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/tommy-cs2-maker"
SERIES = {"cs2": "10310"}


def main(listing_min: str = "2026-09-25T00:00:00Z", listing_max: str = "2026-10-23T00:00:00Z") -> None:
    h = shared_client()
    rows = []
    for name, sid in SERIES.items():
        off = 0
        while True:
            params = {"series_id": sid, "start_date_min": listing_min, "start_date_max": listing_max, "limit": 100, "offset": off}
            d, _ = h.get_json("https://gamma-api.polymarket.com/events", params, adapter="gamma.events", max_age=None)
            if not d:
                break
            for e in d:
                meta = e.get("eventMetadata")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false"))
                    except Exception:  # noqa: BLE001
                        meta = {}
                meta = meta or {}
                for m in e.get("markets") or []:
                    rows.append({
                        "series": name, "event_slug": e.get("slug"), "event_title": e.get("title"),
                        "event_start": e.get("startTime"), "league": meta.get("league"), "league_tier": meta.get("leagueTier"),
                        "pandascore_id": meta.get("pandascoreMatchId"), "cid": m.get("conditionId"), "slug": m.get("slug"),
                        "question": m.get("question"), "smt": m.get("sportsMarketType"), "game_start": m.get("gameStartTime"),
                        "listed": m.get("startDate"), "tokens": m.get("clobTokenIds"), "outcomes": m.get("outcomes"),
                        "tick": m.get("orderPriceMinTickSize"), "seconds_delay": m.get("secondsDelay"),
                        # settlement-only fields (never features)
                        "res_outcome_prices": m.get("outcomePrices"), "res_closed_time": m.get("closedTime"),
                    })
            if len(d) < 100:
                break
            off += 100
    df = pd.DataFrame(rows).drop_duplicates("cid")
    gs = pd.to_datetime(df["game_start"].str.replace(r"\+00$", "+00:00", regex=True), utc=True, errors="coerce")
    df["gs_ts"] = ((gs - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()).astype("Int64")
    ls = pd.to_datetime(df["listed"], utc=True, errors="coerce")
    df["listed_ts"] = ((ls - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()).astype("Int64")
    # holdout discipline: drop anything listed or starting at/after H (its outcome fields are never kept)
    df = df[(df["listed_ts"] < H) & (df["gs_ts"] < H)].reset_index(drop=True)
    df.to_parquet(OUT / "universe.parquet", index=False)
    print(len(df), df.smt.value_counts().to_dict())
    print("game_start in maker dev", ((df.gs_ts >= 1792022400) & (df.gs_ts < H)).sum())


if __name__ == "__main__":
    main(*sys.argv[1:])
