"""X141 (panel iter12 assumptions P2): maker-row tapes (taker_only=False) for the pre-registered stable sample of
code13/fetch_stable.py (BTC 5m windows starting in the UTC hours 02, 08, 14, 20 of 09-11..10-11), same format as
code12/fetch_makers.py, so the maker-share accounting of X115/X126 (10-09..30) extends back across the September ->
October boundary. Balanced passes (k-th window of every (day, hour) cell first). Output: it13/makers/m_<start>.parquet."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/it13/makers"
KEEP = ["timestamp", "proxyWallet", "side", "asset", "price", "size", "transactionHash", "outcomeIndex"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = pd.read_parquet(ROOT / ".cache/re/directional-maker/it13/stable/windows.parquet")
    w["day"] = w.start_ts // 86400
    w["hour"] = (w.start_ts % 86400) // 3600
    w["k"] = ((w.start_ts % 3600) // 300).astype(int)
    w = w.sort_values(["k", "day", "hour"]).reset_index(drop=True)
    pm = PolymarketData()
    st = {"n": len(w), "done": 0, "rows": 0, "t0": time.time()}

    def one(r):
        f = OUT / f"m_{int(r.start_ts)}.parquet"
        if f.exists():
            return 0
        rows, _, cov = pm.market_trades(r.cid, int(r.start_ts) - 300, int(r.end_ts) + 60, taker_only=False)
        d = pd.DataFrame(rows)
        if d.empty:
            d = pd.DataFrame(columns=KEEP)
        d = d[[c for c in KEEP if c in d.columns]].copy()
        d["price"] = pd.to_numeric(d["price"], errors="coerce").astype("float32")
        d["size"] = pd.to_numeric(d["size"], errors="coerce").astype("float32")
        d["cid"] = r.cid
        d["cov"] = cov.status
        d.to_parquet(f, index=False)
        return len(d)

    with ThreadPoolExecutor(3) as ex:
        for n in ex.map(one, w.itertuples()):
            st["done"] += 1
            st["rows"] += n
            if st["done"] % 20 == 0:
                st["el"] = round(time.time() - st["t0"])
                (OUT / "status.json").write_text(json.dumps(st))
    st["finished"] = time.time()
    (OUT / "status.json").write_text(json.dumps(st))


if __name__ == "__main__":
    main()
