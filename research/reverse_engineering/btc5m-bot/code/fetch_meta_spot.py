"""Gamma metadata for every BTC 5m window in [START, H) and Binance 1-s klines (dev period only)."""
import os, sys, time, json
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
import numpy as np, pandas as pd
from polyrea.workflows.updown_study import window_slugs, fetch_windows
from polyrea.analysis.updown import windows_from_markets
from polyrea.adapters.spot import binance_seconds

H = 1792713600
START = int(sys.argv[1]) if len(sys.argv) > 1 else 1791158400  # 2026-10-05? overridden by arg
OUT = "/home/user/PolymarketResearchAgent/.cache/re/btc5m-bot"
t0 = time.time()
slugs = window_slugs("btc", "5m", START, H)
markets = fetch_windows(slugs)
print("markets", len(markets), time.time() - t0, flush=True)
rows = []
for cid, m in markets.items():
    rows.append({"cid": cid, "slug": m.get("slug"), "tokens": m.get("clobTokenIds"), "outcomes": m.get("outcomes"),
                 "start": m.get("eventStartTime"), "end": m.get("endDate"), "fee": json.dumps(m.get("feeSchedule")),
                 "feesEnabled": m.get("feesEnabled"), "createdAt": m.get("createdAt"), "acceptingOrdersTimestamp": m.get("acceptingOrdersTimestamp"),
                 "orderPriceMinTickSize": m.get("orderPriceMinTickSize"), "orderMinSize": m.get("orderMinSize"),
                 "outcomePrices_SETTLEMENT_ONLY": m.get("outcomePrices"), "uma": m.get("umaResolutionStatus")})
meta = pd.DataFrame(rows)
wins = windows_from_markets(markets)
wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token, "down_token": w.down_token,
                     "fee_rate": w.fee_rate, "twap": w.twap_seconds, "up_payout": w.up_payout} for w in wins])
wdf = wdf[wdf.end_ts <= H]
meta.to_parquet(f"{OUT}/gamma_meta.parquet", index=False)
wdf.to_parquet(f"{OUT}/windows.parquet", index=False)
print("windows", len(wdf), "resolved", wdf.up_payout.notna().sum(), time.time() - t0, flush=True)
sp, _ = binance_seconds("btc", START - 86400, H)
s = pd.DataFrame(sp, columns=["sec", "close"])
s = s[s.sec < H]
s["sec"] = s.sec.astype(np.int64)
s.to_parquet(f"{OUT}/binance_1s.parquet", index=False)
print("spot rows", len(s), s.sec.min(), s.sec.max(), time.time() - t0, flush=True)
