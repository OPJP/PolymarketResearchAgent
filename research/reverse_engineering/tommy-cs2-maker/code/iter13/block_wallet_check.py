"""Wallet trades per market of the current block's non-GRID development-unit events (listing ids only)."""
import json, sys, time
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData, DATA_API  # noqa
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
pm = PolymarketData()
for slug in sys.argv[1:]:
    e = httpx.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=20).json()
    if not e: print(slug, "not found"); continue
    for mk in e[0].get("markets", []):
        cid = mk["conditionId"]
        d, _ = pm.http.get_json(f"{DATA_API}/trades", {"market": cid, "user": WALLET, "takerOnly": "false", "limit": 500, "offset": 0},
                                adapter="data-api.trades", max_age=60)
        d = d or []
        ts = sorted(x["timestamp"] for x in d)
        print(slug, mk.get("sportsMarketType"), mk.get("groupItemTitle"), "wallet trades", len(d),
              time.strftime("%H:%M:%S", time.gmtime(ts[0])) if ts else "", time.strftime("%H:%M:%S", time.gmtime(ts[-1])) if ts else "")
