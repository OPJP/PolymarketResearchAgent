"""Examiner: fetch the holdout data [H, END) through the polyrea adapters (shared HTTP cache) into
.cache/re/directional-maker/exam/ in the same file format as code/fetch_local.py, so that
final_rule.evaluate(H, END, local=True) can read it day by day without holding a week of raw JSON rows
in memory (the adapter path of _tapes keeps every row as a Python tuple: ~2 GB for 8 days).

  python exam_fetch.py meta END     windows_5m.parquet, activity_<name>.parquet, spot_btc_1s.parquet
  python exam_fetch.py tapes END    taker5m_day_<d>.parquet for every holdout day
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
from polyrea.adapters.spot import binance_seconds  # noqa: E402
from polyrea.analysis.updown import snap_price, windows_from_markets  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows, window_slugs  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/directional-maker/exam"
PRE = 120
WALLETS = {"bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
           "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def meta(end: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    t0 = time.time()
    wins = [w for w in windows_from_markets(fetch_windows(window_slugs("btc", "5m", H, end))) if w.start_ts >= H and w.end_ts <= end]
    wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token,
                         "down_token": w.down_token, "up_payout": w.up_payout, "fee_rate": w.fee_rate} for w in wins])
    wdf.to_parquet(OUT / "windows_5m.parquet", index=False)
    print("windows", len(wdf), "resolved", int(wdf["up_payout"].notna().sum()), f"{time.time()-t0:.0f}s", flush=True)
    for name, addr in WALLETS.items():
        rows, _, cov = pm.activity(addr, start=H - 86400, end=end - 1)
        df = pd.DataFrame(rows)
        df = df[df["timestamp"] < end]
        keep = [c for c in ["timestamp", "type", "conditionId", "asset", "side", "outcome", "outcomeIndex", "price", "size",
                            "usdcSize", "transactionHash", "slug", "eventSlug"] if c in df.columns]
        df[keep].to_parquet(OUT / f"activity_{name}.parquet", index=False)
        print(name, len(df), cov.status, f"{time.time()-t0:.0f}s", flush=True)
    rows, _ = binance_seconds("btc", H - 86400, end)
    sp = pd.DataFrame(rows, columns=["sec", "px"])
    sp["sec"] = sp["sec"].astype("int64")
    sp.to_parquet(OUT / "spot_btc_1s.parquet", index=False)
    print("spot", len(sp), int(sp["sec"].min()), int(sp["sec"].max()), f"{time.time()-t0:.0f}s", flush=True)


def tapes(end: int, rate: float = 4.0) -> None:
    pm = PolymarketData(http=HttpClient(rates={"data-api.polymarket.com": rate}))
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["start_ts"] >= H) & (w["end_ts"] <= end)]
    days = sorted(set(w["start_ts"] // 86400 * 86400))
    t0 = time.time()
    cov_rows = []

    def one(r):
        for attempt in range(6):
            try:
                rows, _, cov = pm.market_trades(r[0], start=int(r[1]) - PRE, end=int(r[2]) - 1, taker_only=True)
                return r[0], rows, cov.status
            except HttpError as e:  # Cloudflare 429: back off and retry this window
                print("retry", r[0][:10], attempt, str(e)[:80], flush=True)
                time.sleep(30 + 30 * attempt)
        return r[0], [], "failed"

    for d in days:
        f = OUT / f"taker5m_day_{d}.parquet"
        if f.exists():
            continue
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        out = []
        with ThreadPoolExecutor(4) as ex:
            for cid, rows, st in ex.map(one, list(zip(wd["cid"], wd["start_ts"], wd["end_ts"]))):
                cov_rows.append((cid, d, st, len(rows)))
                for r in rows:
                    out.append((cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                                float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
        df = pd.DataFrame(out, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        del out
        df["side"] = df["side"].astype("category")
        df["price"] = df["price"].astype("float32")
        df["size"] = df["size"].astype("float32")
        df.to_parquet(f, index=False)
        print("day", d, "windows", len(wd), "rows", len(df), f"{time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(cov_rows, columns=["cid", "day", "coverage", "rows"]).to_parquet(OUT / f"coverage_{d}.parquet", index=False)
        cov_rows = []


if __name__ == "__main__":
    if sys.argv[1] == "meta":
        meta(int(sys.argv[2]))
    else:
        tapes(int(sys.argv[2]))
