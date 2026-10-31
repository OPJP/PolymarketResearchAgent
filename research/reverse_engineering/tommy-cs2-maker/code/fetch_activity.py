"""Full development-period activity of TommyLeePeeca (first trade .. H-1), cached via polyrea.

Output: .cache/re/tommy-cs2-maker/activity_dev.parquet and markets_dev.json (Gamma metadata
fields known at listing, plus resolution fields used ONLY for settlement).
Holdout discipline: end = H - 1, so no holdout row is ever requested.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OUT = ROOT / ".cache/re/tommy-cs2-maker"


def main(start: int = 1775000000) -> None:
    pm = PolymarketData()
    t0 = time.time()
    rows, src, cov = pm.activity(WALLET, start=start, end=H - 1)
    print("activity", len(rows), cov.status, cov.detail, f"{time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df = df[df["timestamp"] < H].reset_index(drop=True)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str)
    df.to_parquet(OUT / "activity_dev.parquet", index=False)
    cids = sorted({r["conditionId"] for r in rows if r.get("conditionId")})
    markets, _ = pm.markets_by_condition(cids)
    json.dump(markets, open(OUT / "markets_dev.json", "w"))
    print("markets", len(cids), len(markets), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
