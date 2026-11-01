"""X120/X116/X125 (panel iter11: assumptions P3 = information I11-2 = mechanics P3, the competitor at the touch):
the full data-api tape WITH maker rows (taker_only=False) for a pre-registered sample of BTC 5m windows: every window
starting in the UTC hours 02, 08, 14, 20 of 2026-10-09..30 (development + released lot; VALIDATE days 10-27..30 are
read only as per-block aggregates). Fetched in balanced passes (pass k = the k-th window of every (day, hour) cell) so
that a partial fetch is balanced across days and hours. One parquet per window:
.cache/re/directional-maker/it12/makers/m_<start>.parquet (timestamp, proxyWallet, side, asset, price, size,
transactionHash, outcomeIndex)."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H_LOT_END = 1793404800  # 10-31 00:00, end of the released lot
D0 = 1791504000  # 10-09 00:00
OUT = ROOT / ".cache/re/directional-maker/it12/makers"
HOURS = (2, 8, 14, 20)
KEEP = ["timestamp", "proxyWallet", "side", "asset", "price", "size", "transactionHash", "outcomeIndex"]


def windows() -> pd.DataFrame:
    a = pd.read_parquet(ROOT / ".cache/re/directional-maker/windows_5m.parquet", columns=["cid", "start_ts", "end_ts"])
    b = pd.read_parquet(ROOT / ".cache/re/directional-maker/exam/windows_5m.parquet", columns=["cid", "start_ts", "end_ts"])
    w = pd.concat([a, b]).drop_duplicates("cid")
    w = w[(w.start_ts >= D0) & (w.start_ts < H_LOT_END) & (w.end_ts <= H_LOT_END)]
    w["hour"] = (w.start_ts % 86400) // 3600
    w = w[w.hour.isin(HOURS)].copy()
    w["day"] = w.start_ts // 86400
    w["k"] = ((w.start_ts % 3600) // 300).astype(int)
    return w.sort_values(["k", "day", "hour"]).reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = windows()
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
