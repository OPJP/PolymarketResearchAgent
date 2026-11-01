"""Iteration 4, X49 follow-up: is the fast co-canceller 0x51dbdd2b a peer with the same feed coverage?

Its data-api TRADE activity 10-16..10-22 (development, before H), mapped to Gamma CS2 events (events_meta.parquet:
gridSeriesId) by eventSlug. Reported: CS2 events it traded, split GRID / non-GRID, and its overlap with the wallet's
traded events and with the non-GRID events the wallet skipped (events_sel.parquet, y = wallet traded).
Output: results/cosub_coverage.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
X = "0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3"
T1, H = 1792108800, 1792713600


def main():
    rows, _, cov = PolymarketData().activity(X, start=T1, end=H - 1, types=("TRADE",), max_rows=200_000)
    a = pd.DataFrame(rows)
    res = {"rows": int(len(a))}
    if len(a) == 0:
        json.dump(res, open(RES / "cosub_coverage.json", "w"), indent=1)
        print(res)
        return
    a["ts"] = a.timestamp.astype(int)
    a = a[a.ts < H]
    cs2 = a[a.eventSlug.astype(str).str.startswith("cs2-")]
    res["share_cs2_rows"] = round(len(cs2) / len(a), 3)
    res["top_event_prefixes"] = a.eventSlug.astype(str).str.split("-").str[0].value_counts().head(6).to_dict()
    em = pd.read_parquet(OUT / "events_meta.parquet", columns=["event_slug", "grid_series_id"])
    grid = dict(zip(em.event_slug, em.grid_series_id.notna()))
    ev = pd.Series(sorted(set(cs2.eventSlug)))
    g = ev.map(grid)
    res["cs2_events"] = int(len(ev))
    res["cs2_events_grid"] = int((g == True).sum())  # noqa: E712
    res["cs2_events_nongrid"] = int((g == False).sum())  # noqa: E712
    res["cs2_events_unknown"] = int(g.isna().sum())
    es = pd.read_parquet(OUT / "events_sel.parquet", columns=["event_slug", "y", "grid", "gs"])
    es = es[(es.gs >= T1) & (es.gs < H)]
    xs = set(ev)
    for lab, sel in (("wallet_traded", es.y == 1), ("nongrid_skipped", (es.y == 0) & (~es.grid)), ("grid", es.grid)):
        e = es[sel]
        res[f"share_of_{lab}_events_with_0x51"] = round(float(e.event_slug.isin(xs).mean()), 3) if len(e) else None
        res[f"n_{lab}_events"] = int(len(e))
    json.dump(res, open(RES / "cosub_coverage.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
