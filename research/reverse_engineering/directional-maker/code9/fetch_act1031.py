"""Iteration 9: the three wallets' activity for the development block 10-31 12:00-18:00 UTC (all markets), for the scope
table (X83) and the salt-counter test of the 16:53 BTC 5m switch-off (X82). Development data only."""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import sealed  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
A, B = 1793448000, 1793469600
assert not any(sealed.is_sealed(t, "directional-maker") for t in (A, B - 1))
pm = PolymarketData()
W = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
     "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
out = []
for n, w in W.items():
    rows, _, cov = pm.activity(w, A, B)
    d = pd.DataFrame(rows)
    d["wallet"] = w
    out.append(d)
    print(n, len(d), flush=True)
D = pd.concat(out, ignore_index=True)
D = D[(D.timestamp >= A) & (D.timestamp < B)]
keep = [c for c in ("timestamp", "type", "conditionId", "asset", "side", "outcome", "outcomeIndex", "price", "size", "usdcSize", "transactionHash", "slug", "eventSlug", "wallet") if c in D.columns]
D[keep].to_parquet(ROOT / f".cache/re/directional-maker/it9/act_{A}_{B}.parquet")
print("saved", len(D))
