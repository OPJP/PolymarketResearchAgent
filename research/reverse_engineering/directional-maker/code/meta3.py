"""Iteration 3, family N2b: do listing-time Gamma fields of the BTC 5m windows (reward programme, fees, tick,
minimum size, ...) vary across windows and track the cluster's on/off? Reads the cached Gamma payloads via
polyrea (fetch_windows); only fields known at listing are considered (no outcomePrices, closedTime,
eventMetadata, volume/liquidity snapshots)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from polyrea.workflows.updown_study import fetch_windows, window_slugs  # noqa: E402
from panel2 import OUT, H  # noqa: E402

VAL0 = 1792108800
B0 = 1791504000
SKIP = {"outcomePrices", "closedTime", "eventMetadata", "volume", "volumeNum", "liquidity", "liquidityNum", "volume24hr",
        "volume1wk", "volume1mo", "volume1yr", "volumeClob", "liquidityClob", "volume24hrClob", "volume1wkClob", "volume1moClob",
        "volume1yrClob", "lastTradePrice", "bestBid", "bestAsk", "spread", "oneDayPriceChange", "oneHourPriceChange",
        "oneWeekPriceChange", "oneMonthPriceChange", "oneYearPriceChange", "updatedAt", "closed", "active", "umaResolutionStatus",
        "umaResolutionStatuses", "resolvedBy", "automaticallyResolved", "competitive", "archived", "acceptingOrders", "events"}


def main():
    slugs = window_slugs("btc", "5m", B0, H)
    ms = fetch_windows(slugs)
    rows = []
    for m in ms.values():
        d = {k: (json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v) for k, v in m.items() if k not in SKIP}
        rows.append(d)
    df = pd.DataFrame(rows)
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
    on = set(fills.loc[(fills["role"] == "maker") & (fills["side"] == "BUY"), "cid"])
    df = df[df["conditionId"].isin(set(w["cid"]))]
    df["on"] = df["conditionId"].isin(on)
    df = df.merge(w[["cid", "start_ts"]], left_on="conditionId", right_on="cid")
    var = {}
    for c in df.columns:
        if c in ("conditionId", "cid", "on", "start_ts", "id", "slug", "question", "questionID", "clobTokenIds", "startDate", "endDate",
                 "endDateIso", "startDateIso", "createdAt", "eventStartTime", "image", "icon", "description", "groupItemTitle", "title",
                 "marketMakerAddress", "submitted_by", "deployingTimestamp", "acceptingOrdersTimestamp", "gameStartTime"):
            continue
        nun = df[c].astype(str).nunique()
        if 1 < nun <= 30:
            t = df.groupby(df[c].astype(str))["on"].agg(["size", "mean"]).round(3)
            var[c] = t.reset_index().values.tolist()
    print("windows", len(df), "fields", len(df.columns), "listing fields that vary (<=30 values):", list(var))
    for k, v in var.items():
        print(k, v[:8])
    (HERE.parent / "results_iter3_meta.json").write_text(json.dumps({"varying_listing_fields": var}, indent=1, default=str))


if __name__ == "__main__":
    main()
