"""Iteration 6, X84 (assumptions panel iter5 P5): the exam lots' league mix from the LISTING PROJECTION only.

For CS2 events (Gamma series 10310) whose earliest moneyline gameStartTime lies in [H, T0) (the sealed historical lots
h1 / h2), keep only listing-time fields, projected in memory immediately after each page arrives: the lot (h1 / h2 by
the UTC day of the earliest game start), league, league tier, and whether gridSeriesId is set. No outcome prices,
volume, liquidity, closed flags, resolution or tick size is read, printed or stored; the HTTP fetch bypasses the
shared cache (httpx, no persistence), so no raw Gamma record of a sealed market is stored anywhere.
Output (aggregates only): results/exam_league_mix.json: per lot, non-GRID event counts by whether the league has a
fitted constant in the frozen v3 exam table, and the share in unseen leagues; then the VALIDATE seen / unseen AUCs of
v3 (from selection_scores / events_sel) reweighted to that mix.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H, T0 = 1792713600, 1793404800
H1_DAYS = {"2026-10-23", "2026-10-25", "2026-10-27", "2026-10-29"}


def ts(s):
    try:
        return int(pd.Timestamp(s).tz_convert("UTC").timestamp()) if pd.Timestamp(s).tzinfo else int(pd.Timestamp(s, tz="UTC").timestamp())
    except Exception:  # noqa: BLE001
        return None


def project_page(events):
    """Return listing-only rows; every other field of the raw records is discarded here."""
    rows = []
    for e in events:
        mk = e.get("markets") or []
        gss = [ts(m.get("gameStartTime")) for m in mk
               if m.get("gameStartTime") and m.get("sportsMarketType") in ("moneyline", "child_moneyline")]
        gss = [g for g in gss if g]
        if not gss:
            continue
        g0 = min(gss)
        if not (H <= g0 < T0):
            continue
        meta = e.get("eventMetadata")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:  # noqa: BLE001
                meta = {}
        meta = meta or {}
        day = pd.Timestamp(g0, unit="s", tz="UTC").strftime("%Y-%m-%d")
        rows.append({"lot": "h1" if day in H1_DAYS else "h2", "league": meta.get("league"),
                     "tier": meta.get("leagueTier"), "grid": bool(meta.get("gridSeriesId"))})
    return rows


def main():
    rows = []
    off = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "research"}) as c:
        while True:
            params = {"series_id": "10310", "start_date_min": "2026-10-21T00:00:00Z",
                      "start_date_max": "2026-11-01T00:00:00Z", "limit": 100, "offset": off}
            r = c.get("https://gamma-api.polymarket.com/events", params=params)
            r.raise_for_status()
            d = r.json()
            n = len(d)
            rows.extend(project_page(d))
            del d, r
            if n < 100 or off > 3000:
                break
            off += 100
            time.sleep(0.6)
    L = pd.DataFrame(rows)
    cons = json.loads((ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v2_constants.json").read_text())
    seen = set(cons["exam"]["league_n"].keys())
    res = {}
    for lot, x in L.groupby("lot"):
        ng = x[~x.grid]
        res[lot] = {"events": int(len(x)), "grid_events": int(x.grid.sum()), "non_grid": int(len(ng)),
                    "non_grid_in_seen_league": int(ng.league.isin(seen).sum()),
                    "non_grid_unseen_league": int((~ng.league.isin(seen)).sum()),
                    "share_unseen": round(float((~ng.league.isin(seen)).mean()), 3) if len(ng) else None,
                    "unseen_leagues_n": int(ng.loc[~ng.league.isin(seen), "league"].nunique()),
                    "non_grid_by_tier": ng.tier.astype(str).value_counts().to_dict()}
    (RES / "exam_league_mix.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
