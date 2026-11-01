"""Iteration 8 (X112, scope): Gamma universe of Dota 2 (series 10309) and CS2 (series 10310) match / map-winner markets.

Listing projection only (event slug, league, tier, grid id, pandascore id, cid, sportsMarketType, gameStartTime, tokens,
outcomes). The resolution (outcome prices) is kept ONLY for development units (gameStart before H, or in a development
block after T0 per tools/sealed.py); for every other unit it is never stored.
Output: .cache/re/tommy-cs2-maker/universe_dota.parquet (Dota 2, 2026-10-01 .. now) and
        .cache/re/tommy-cs2-maker/universe_t0.parquet (CS2 + Dota 2 units starting at/after T0, projection, dev resolution).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
from polyrea.adapters.http import shared_client  # noqa: E402
import sealed  # noqa: E402

KEY = "tommy-cs2-maker"
H = 1792713600
T0 = 1793404800
OUT = ROOT / ".cache/re/tommy-cs2-maker"


def _gs(s):
    s = str(s)
    if s.endswith("+00"):
        s += ":00"
    try:
        t = pd.Timestamp(s)
        return (t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")).timestamp()
    except Exception:  # noqa: BLE001
        return None


def is_dev(gs):
    if gs is None or gs != gs:
        return False
    if gs < H:
        return True
    return not sealed.is_sealed(int(gs), KEY)


def fetch(series, lo, hi):
    h = shared_client()
    rows, off = [], 0
    while True:
        d, _ = h.get_json("https://gamma-api.polymarket.com/events", {"series_id": series, "start_date_min": lo,
                          "start_date_max": hi, "limit": 100, "offset": off}, adapter="gamma.events", max_age=1800)
        if not d:
            break
        for e in d:
            meta = e.get("eventMetadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:  # noqa: BLE001
                    meta = {}
            for m in e.get("markets") or []:
                gs = _gs(m.get("gameStartTime"))
                r = {"series": series, "event_slug": e.get("slug"), "league": meta.get("league"),
                     "league_tier": meta.get("leagueTier"), "grid_series_id": meta.get("gridSeriesId"),
                     "pandascore_id": meta.get("pandascoreMatchId"), "tournament": meta.get("tournament"),
                     "cid": m.get("conditionId"), "smt": m.get("sportsMarketType"), "game_start": m.get("gameStartTime"),
                     "gs_ts": gs, "tokens": m.get("clobTokenIds"), "outcomes": m.get("outcomes"),
                     "res_outcome_prices": None}
                if is_dev(gs):  # settlement field kept for development units only
                    r["res_outcome_prices"] = m.get("outcomePrices")
                rows.append(r)
        if len(d) < 100:
            break
        off += 100
    return rows


def main():
    now = int(time.time())
    hi = pd.Timestamp(now, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
    d = pd.DataFrame(fetch("10309", "2026-10-01T00:00:00Z", hi)).drop_duplicates("cid")
    d = d[d["smt"].isin(["moneyline", "child_moneyline"])]
    d.to_parquet(OUT / "universe_dota.parquet", index=False)
    c = pd.DataFrame(fetch("10310", "2026-10-10T00:00:00Z", hi)).drop_duplicates("cid")
    c = c[c["gs_ts"] >= T0]
    c = c[c["smt"].isin(["moneyline", "child_moneyline"])]
    t = pd.concat([c, d[d["gs_ts"] >= T0]], ignore_index=True)
    t = t[t["gs_ts"] >= T0]
    t.to_parquet(OUT / "universe_t0.parquet", index=False)
    dd = d[d["gs_ts"] < H]
    dd = dd.assign(day=pd.to_datetime(dd["gs_ts"], unit="s").dt.strftime("%m-%d"))
    ev = dd.groupby("event_slug").agg(day=("day", "min"), league=("league", "first"), tier=("league_tier", "first"),
                                      grid=("grid_series_id", lambda s: s.notna().any()), n=("cid", "size")).reset_index()
    print("dota dev events", len(ev), "markets", len(dd))
    print(ev.groupby(["day", "league"]).size().to_string())
    print("T0+ units:", t.groupby([t["series"], t["gs_ts"].map(is_dev)]).size().to_dict())


if __name__ == "__main__":
    main()
