"""Q1 data: BTC 15m windows (Gamma) and their data-api taker tapes [start-120, end), development periods only
(2026-10-09 .. 2026-10-31 00:00 UTC: everything before H plus the released lot). One parquet per UTC day:
.cache/re/directional-maker/t15/taker15m_day_<day0>.parquet. Days are fetched lot first (STUDY, VALIDATE), then BUILD.
Never reads other agents' caches.

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code5/fetch15.py
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import HttpClient, HttpError  # noqa: E402
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.analysis.updown import snap_price, windows_from_markets  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows, window_slugs  # noqa: E402

T0 = 1793404800
START = 1791504000
OUT = ROOT / ".cache/re/directional-maker/t15"
PRE = 120


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    wf = OUT / "windows_15m.parquet"
    if not wf.exists():
        slugs = window_slugs("btc", "15m", START, T0)
        wins = [w for w in windows_from_markets(fetch_windows(slugs)) if w.end_ts <= T0 and w.start_ts >= START]
        wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token,
                             "down_token": w.down_token, "up_payout": w.up_payout, "fee_rate": w.fee_rate} for w in wins])
        wdf.to_parquet(wf, index=False)
        print("windows", len(wdf), "of", len(slugs), f"{time.time()-t0:.0f}s", flush=True)
    w = pd.read_parquet(wf)
    pm = PolymarketData(http=HttpClient(rates={"data-api.polymarket.com": 4.0}))
    lot = [d for d in range(1792713600, T0, 86400)]
    build = [d for d in range(1792627200, START - 1, -86400)]
    for d in lot + build:
        f = OUT / f"taker15m_day_{d}.parquet"
        if f.exists():
            continue
        wd = w[(w.start_ts >= d) & (w.start_ts < d + 86400)]

        def one(r):
            for attempt in range(6):
                try:
                    rows, _, cov = pm.market_trades(r[0], start=int(r[1]) - PRE, end=min(int(r[2]), T0 - 1), taker_only=True)
                    return r[0], rows
                except HttpError as e:
                    print("retry", r[0][:10], attempt, str(e)[:80], flush=True)
                    time.sleep(30 + 30 * attempt)
            return r[0], []
        out = []
        with ThreadPoolExecutor(3) as ex:
            for cid, rows in ex.map(one, list(zip(wd.cid, wd.start_ts, wd.end_ts))):
                for r in rows:
                    out.append((cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                                float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
        df = pd.DataFrame(out, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        df["side"] = df["side"].astype("category")
        df["price"] = df["price"].astype("float32")
        df["size"] = df["size"].astype("float32")
        df.to_parquet(f, index=False)
        print("day", d, "windows", len(wd), "rows", len(df), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
