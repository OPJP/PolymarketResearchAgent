# Fake data-api /trades: newest first, default limit 100 when 'limit' is absent (live API behaviour
# confirmed by the cache: 19/19 no-limit walk pages hold exactly 100 rows while the same seconds hold 503-658).
import sys
from urllib.parse import urlsplit, parse_qs
from polyrea.adapters.polymarket import PolymarketData
from polyrea.evidence import Source
sys.path.insert(0, sys.argv[1]); import fixed_scan
rows = [{"timestamp": 1000 + i // 3, "transactionHash": f"0x{i:06x}", "asset": "a", "type": "TRADE", "side": "BUY", "size": 1, "price": .5, "conditionId": "c"} for i in range(900)]
rows += [{"timestamp": 1100, "transactionHash": f"0xd{i:05x}", "asset": "a", "type": "TRADE", "side": "BUY", "size": 1, "price": .5, "conditionId": "c"} for i in range(1200)]  # dense second
rows += [{"timestamp": 1101 + i // 3, "transactionHash": f"0xe{i:05x}", "asset": "a", "type": "TRADE", "side": "BUY", "size": 1, "price": .5, "conditionId": "c"} for i in range(300)]
class FakeHttp:
    def get_json(self, url, params, adapter, max_age=None):
        q = dict(params); lim = int(q.get("limit", 100)); off = int(q.get("offset", 0))
        sel = [r for r in rows if (q.get("start") is None or r["timestamp"] >= q["start"]) and (q.get("end") is None or r["timestamp"] <= q["end"])]
        sel = sorted(sel, key=lambda r: -r["timestamp"])
        return sel[off:off + lim], Source(adapter=adapter, url=url, fetched_at="", body_sha256="", cached=False)
for label in ("current", "fixed"):
    (fixed_scan.install if label == "fixed" else fixed_scan.uninstall)()
    pm = PolymarketData(FakeHttp())
    got, src, cov = pm.market_trades("c", start=900, end=2000, taker_only=False)
    dense = sum(r["timestamp"] == 1100 for r in got)
    print(f"{label:7s} truth {len(rows)} got {len(got)} missing {len(rows)-len(got)}; dense second kept {dense}/{sum(r["timestamp"] == 1100 for r in rows)}; coverage={cov.status!r}; requests {len(src)}")
