"""Iteration 8, X45 (panel-information iter7 P2): Gamma eventMetadata.priceToBeat for every BUILD and VALIDATE BTC 5m window
(all start before H). priceToBeat of window k is known at its start (it is window k-1's settlement); finalPrice is kept
only as a settlement / BUILD-label column (suffix _SETTLEMENT_ONLY). Multi-slug /events requests through the cached
polyrea HTTP client. Writes .cache/re/btc5m-bot/ptb.parquet. Usage: python fetch_ptb8.py"""
import os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT)
import pandas as pd
from polyrea.adapters.polymarket import PolymarketData, GAMMA_API

H = 1792713600
g = pd.read_parquet(_ROOT + "/.cache/re/btc5m-bot/gamma_meta.parquet", columns=["slug"])
g["start"] = g.slug.str.rsplit("-", n=1).str[1].astype(int)
g = g[g.start < H].sort_values("start")
pm = PolymarketData()
rows = []
sl = g.slug.tolist()
for i in range(0, len(sl), 25):
    part = sl[i:i + 25]
    d, _ = pm.http.get_json(f"{GAMMA_API}/events", [("slug", s) for s in part] + [("limit", 50)], adapter="gamma.events", max_age=30 * 86400)
    for e in d or []:
        md = e.get("eventMetadata") or {}
        rows.append((e.get("slug"), md.get("priceToBeat"), md.get("finalPrice")))
    if i % 500 == 0:
        print(i, len(rows), flush=True)
df = pd.DataFrame(rows, columns=["slug", "priceToBeat", "finalPrice_SETTLEMENT_ONLY"]).drop_duplicates("slug")
df["start"] = df.slug.str.rsplit("-", n=1).str[1].astype(int)
assert df.start.max() < H
df.to_parquet(_ROOT + "/.cache/re/btc5m-bot/ptb.parquet", index=False)
print("DONE", len(df), df.priceToBeat.notna().mean())
