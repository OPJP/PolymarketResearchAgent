"""Gamma metadata for every market RN1 traded in [p0, p1) (development data).

Decision code may read only listing-time fields (slug, question, sportsMarketType, gameStartTime,
clobTokenIds, negRisk, orderPriceMinTickSize, orderMinSize, feeSchedule, events.seriesSlug).
outcomePrices are kept for PnL settlement only.
Output: .cache/re/rn1-inplay-maker/markets_<p0>_<p1>.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

C = ROOT / ".cache/re/rn1-inplay-maker"
LISTING = ["conditionId", "slug", "question", "sportsMarketType", "gameStartTime", "clobTokenIds", "negRisk",
           "orderPriceMinTickSize", "orderMinSize", "feeSchedule", "outcomes", "startDate", "endDate",
           "makerBaseFee", "takerBaseFee", "secondsDelay", "line", "groupItemTitle"]
SETTLE = ["outcomePrices", "closedTime", "umaResolutionStatus"]


def main(p0, p1):
    acts = [pd.read_parquet(C / "activity" / f"act_{d}.parquet", columns=["type", "conditionId", "timestamp"])
            for d in range(p0, p1, 86400) if (C / "activity" / f"act_{d}.parquet").exists()]
    a = pd.concat(acts)
    cids = sorted(set(a.loc[a["type"] == "TRADE", "conditionId"].dropna()))
    pm = PolymarketData()
    mk, _ = pm.markets_by_condition(cids)
    rows = []
    for cid, m in mk.items():
        r = {k: m.get(k) for k in LISTING + SETTLE}
        ev = (m.get("events") or [{}])[0]
        r["event_slug"] = ev.get("slug")
        r["series_slug"] = ev.get("seriesSlug")
        r["event_start"] = ev.get("startTime")
        for k in ("feeSchedule", "clobTokenIds", "outcomes", "outcomePrices"):
            if r.get(k) is not None and not isinstance(r[k], str):
                r[k] = json.dumps(r[k])
        rows.append(r)
    df = pd.DataFrame(rows)
    for k in df.columns:
        if df[k].dtype == object:
            df[k] = df[k].astype(str)
    df.to_parquet(C / f"markets_{p0}_{p1}.parquet", index=False)
    print("markets", len(cids), "found", len(df))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
