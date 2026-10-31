"""One 500-row activity page (most recent) per near-miss wallet: market families and maker/taker hints. Scratch cache."""
import json, sys, collections, re
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.adapters.polymarket import PolymarketData, DATA_API
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
pm = PolymarketData()
W = {"norm1e69": "0x41e2e1ccf1e4940029af02259a31c6b89b9fa354", "0x50f7": "0xee65685de42f8de9a03b4c53ee77d56a20d2cfc9",
     "johnbaster": "0x31864feb9d25dee93728c6225ba891530967e9ca", "LonnieHawkinss": "0xa797d6bd8fe6e404bb4d8e4ab3d97c38336fdede",
     "mo-money": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
res = {}
for n, w in W.items():
    rows, src = pm.http.get_json(f"{DATA_API}/activity", {"user": w, "limit": 500, "offset": 0}, adapter="data-api.activity", max_age=3600)
    tr = [r for r in rows if r.get("type") == "TRADE"]
    fam = collections.Counter(re.sub(r"-\d+$", "", (r.get("slug") or ""))[:40] for r in tr)
    usd = collections.Counter()
    for r in tr: usd[re.sub(r"-\d+$", "", (r.get("slug") or ""))[:40]] += float(r.get("usdcSize") or 0)
    res[n] = {"rows": len(rows), "trades": len(tr), "span_h": round((max(r["timestamp"] for r in rows) - min(r["timestamp"] for r in rows)) / 3600, 2) if rows else None,
              "types": dict(collections.Counter(r.get("type") for r in rows)), "sides": dict(collections.Counter(r.get("side") for r in tr)),
              "top_families_by_usd": [(k, round(v)) for k, v in usd.most_common(6)],
              "median_price": sorted(float(r["price"]) for r in tr)[len(tr) // 2] if tr else None}
    print(n, json.dumps(res[n]), flush=True)
json.dump(res, open(f"{OUT}/peek_activity.json", "w"), indent=1)
