"""Cluster activity in the current development block (from 12:00 UTC 2026-10-31), via the polyrea adapter.
Only units (windows) starting in development blocks are kept."""
import sys, time, json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa
from polyrea.adapters.polymarket import PolymarketData
W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
a = int(sys.argv[1]); b = int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time())
pm = PolymarketData()
rows = []
for n, w in W.items():
    res = pm.activity(w, a, b)
    recs = res[0] if isinstance(res, tuple) else res
    recs = getattr(recs, "data", recs)
    for r in recs:
        r = dict(r); r["w"] = n; rows.append(r)
df = pd.DataFrame(rows)
df = df[df.timestamp.apply(lambda t: not sealed.is_sealed(int(t), "directional-maker"))]
out = ROOT / f".cache/re/directional-maker/live_activity_{a}_{b}.parquet"
keep = [c for c in ["timestamp", "type", "conditionId", "asset", "side", "outcome", "price", "size", "usdcSize", "transactionHash", "slug", "w"] if c in df]
df[keep].to_parquet(out)
print(len(df), df.type.value_counts().to_dict() if len(df) else {}, df.slug.str.extract(r"^([a-z]+-updown-[0-9a-z]+)")[0].value_counts().head(6).to_dict() if len(df) else {})
print("last ts", df.timestamp.max() if len(df) else None)
