"""Iteration 7, X98 step 4 (assumptions panel iter6 P2): do the exam lots' CS2 match / map-winner markets carry the same
trading parameters as 16-22 Oct (in-play delay, clear-book-on-start, fee schedule, rebate share, reward parameters)?

LISTING PROJECTION only (as exam_league_mix.py): each Gamma page is projected in memory as soon as it arrives to the
parameter fields named below plus the lot of the market's gameStartTime; no outcome price, volume, liquidity, closed
flag, resolution or tick size is read, printed or stored; the fetch bypasses the shared cache (httpx, no persistence).
Lots: dev16_22 (game start 10-16..H), h1 / h2 (sealed historical days), dev_T0 / sealed_T0 (6-h blocks from T0 by
tools/sealed.py). Output (aggregate value counts only): results/exam_params.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402

RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
KEY = "tommy-cs2-maker"
H, T0 = 1792713600, 1793404800
D16 = 1792108800
H1_DAYS = {"2026-10-23", "2026-10-25", "2026-10-27", "2026-10-29"}
PARAMS = ("secondsDelay", "clearBookOnStart", "feeSchedule", "feeType", "feesEnabled", "makerBaseFee", "takerBaseFee",
          "makerRebatesFeeShareBps", "rewardsMinSize", "rewardsMaxSpread", "orderMinSize", "negRisk", "rfqEnabled",
          "holdingRewardsEnabled", "enableOrderBook")


def ts(s):
    try:
        t = pd.Timestamp(s)
        return int((t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")).timestamp())
    except Exception:  # noqa: BLE001
        return None


def lot_of(g):
    if D16 <= g < H:
        return "dev16_22"
    if H <= g < T0:
        return "h1" if pd.Timestamp(g, unit="s", tz="UTC").strftime("%Y-%m-%d") in H1_DAYS else "h2"
    if g >= T0:
        return "sealed_T0" if sealed.is_sealed(g, KEY) else "dev_T0"
    return None


def main():
    agg = defaultdict(lambda: defaultdict(Counter))
    nmk = Counter()
    off = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "research"}) as c:
        while True:
            params = {"series_id": "10310", "start_date_min": "2026-10-14T00:00:00Z",
                      "start_date_max": "2026-11-03T00:00:00Z", "limit": 100, "offset": off}
            r = c.get("https://gamma-api.polymarket.com/events", params=params)
            r.raise_for_status()
            d = r.json()
            n = len(d)
            for e in d:  # projection: only PARAMS and the lot leave this loop
                for m in e.get("markets") or []:
                    if m.get("sportsMarketType") not in ("moneyline", "child_moneyline"):
                        continue
                    g = ts(m.get("gameStartTime")) if m.get("gameStartTime") else None
                    lot = lot_of(g) if g else None
                    if lot is None:
                        continue
                    nmk[lot] += 1
                    for k in PARAMS:
                        v = m.get(k)
                        if isinstance(v, (dict, list)):
                            v = json.dumps(v, sort_keys=True)
                        agg[lot][k][str(v)] += 1
            del d, r
            if n < 100 or off > 4000:
                break
            off += 100
            time.sleep(0.6)
    res = {"markets": dict(nmk), "params": {lot: {k: dict(v.most_common(6)) for k, v in kv.items()} for lot, kv in agg.items()}}
    (RES / "exam_params.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:5000])


if __name__ == "__main__":
    main()
