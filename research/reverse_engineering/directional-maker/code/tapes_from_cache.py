"""Build the taker-tape parquet for BTC 5m windows in [lo, hi) from the HTTP cache only
(POLYREA_OFFLINE=1); windows whose tape is not cached yet are skipped and counted."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["POLYREA_OFFLINE"] = "1"
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpError  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.analysis.updown import snap_price  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/directional-maker"
PRE = 900

if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    pm = PolymarketData()
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["start_ts"] >= lo) & (w["end_ts"] <= min(hi, H))]
    out, miss = [], 0
    for win in w.itertuples(index=False):
        try:
            rows, _, cov = pm.market_trades(win.cid, start=win.start_ts - PRE, end=min(win.end_ts, H - 1), taker_only=True)
        except HttpError:
            miss += 1
            continue
        for r in rows:
            if r.get("timestamp", 0) >= H:
                continue
            out.append((win.cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                        float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
    df = pd.DataFrame(out, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
    df.to_parquet(OUT / f"taker_5m_{lo}_{hi}.parquet", index=False)
    print("windows", len(w), "missing", miss, "rows", len(df))
