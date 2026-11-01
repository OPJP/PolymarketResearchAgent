"""Taker-regime activity (assumptions panel X: decode the trigger where most decisions are): 2026-06-16 .. 2026-10-16.
Output: .cache/re/tommy-cs2-maker/activity_taker.parquet and markets_taker.json (Gamma listing + settlement fields)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
OUT = ROOT / ".cache/re/tommy-cs2-maker"

def main(start=1781568000, end=1792108799):
    pm = PolymarketData(); t0 = time.time()
    rows, src, cov = pm.activity(WALLET, start=start, end=end)
    print("activity", len(rows), cov.status, cov.detail, f"{time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    for c in df.columns:
        if df[c].dtype == object: df[c] = df[c].astype(str)
    df.to_parquet(OUT / "activity_taker.parquet", index=False)
    cids = sorted({r["conditionId"] for r in rows if r.get("conditionId")})
    markets, _ = pm.markets_by_condition(cids)
    json.dump(markets, open(OUT / "markets_taker.json", "w"))
    print("markets", len(cids), len(markets), f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()
