"""Local re-fetch (iteration 2): Gamma BTC 5m windows, cluster activity, Binance 1-s spot and
data-api taker tapes, all clamped to < H (development data only).

  meta                 windows_5m.parquet, activity_<name>.parquet, spot_btc_1s.parquet
  tapes LO HI [rev]    taker tapes [start-PRE, end) of the windows starting in [LO, HI),
                       one parquet per UTC day: taker5m_day_<day0>.parquet

Paths are relative to the repository root (run from it).
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from polyrea.adapters.spot import binance_seconds  # noqa: E402
from polyrea.analysis.updown import snap_price, windows_from_markets  # noqa: E402
from polyrea.workflows.updown_study import fetch_windows, window_slugs  # noqa: E402

H = 1792713600
START = 1791504000  # 2026-10-09 00:00 UTC (BUILD start)
OUT = ROOT / ".cache/re/directional-maker"
PRE = 120
WALLETS = {
    "bosona": "0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed",
    "almach": "0x3725d52f3c252e8374999cc8617292ea2608ad88",
    "momoney": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3",
}


def meta() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    t0 = time.time()
    slugs = window_slugs("btc", "5m", START, H)
    wins = [w for w in windows_from_markets(fetch_windows(slugs)) if w.end_ts <= H and w.start_ts >= START]
    wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token,
                         "down_token": w.down_token, "up_payout": w.up_payout, "fee_rate": w.fee_rate} for w in wins])
    wdf.to_parquet(OUT / "windows_5m.parquet", index=False)
    print("windows", len(wdf), "of", len(slugs), f"{time.time()-t0:.0f}s", flush=True)
    for name, addr in WALLETS.items():
        rows, _, cov = pm.activity(addr, start=START - 86400, end=H - 1)
        df = pd.DataFrame(rows)
        df = df[df["timestamp"] < H]
        keep = [c for c in ["timestamp", "type", "conditionId", "asset", "side", "outcome", "outcomeIndex", "price", "size",
                            "usdcSize", "transactionHash", "slug", "eventSlug"] if c in df.columns]
        df[keep].to_parquet(OUT / f"activity_{name}.parquet", index=False)
        print(name, len(df), cov.status, f"{time.time()-t0:.0f}s", flush=True)
    rows, _ = binance_seconds("btc", START - 86400, H)
    sp = pd.DataFrame(rows, columns=["sec", "px"])
    sp["sec"] = sp["sec"].astype("int64")
    sp = sp[sp["sec"] < H]
    sp.to_parquet(OUT / "spot_btc_1s.parquet", index=False)
    print("spot", len(sp), f"{time.time()-t0:.0f}s", flush=True)


def tapes(lo: int, hi: int, rev: bool, rate: float = 5.0) -> None:
    from polyrea.adapters.http import HttpClient, HttpError
    pm = PolymarketData(http=HttpClient(rates={"data-api.polymarket.com": rate}))
    w = pd.read_parquet(OUT / "windows_5m.parquet")
    w = w[(w["start_ts"] >= lo) & (w["start_ts"] < min(hi, H)) & (w["end_ts"] <= H)]
    days = sorted(set(w["start_ts"] // 86400 * 86400), reverse=rev)
    t0 = time.time()

    other = ROOT / ".cache/re/btc5m-bot/tapes"  # read-only reuse of another agent's identical data-api pulls

    def one(r):
        f = other / f"{r[0]}.parquet"
        if f.exists():
            try:
                o = pd.read_parquet(f)
                if len(o) and "coverage" in o.columns and (o["coverage"] == "complete").all():
                    o = o[(o["timestamp"] >= int(r[1]) - PRE) & (o["timestamp"] < min(int(r[2]), H))]
                    return r[0], [{"timestamp": a, "side": b, "asset": c, "price": d, "size": e, "proxyWallet": g, "transactionHash": h}
                                  for a, b, c, d, e, g, h in zip(o["timestamp"], o["side"], o["asset"], o["price"], o["size"],
                                                                 o["proxyWallet"], o["transactionHash"])]
            except Exception as e:  # noqa: BLE001
                print("other read failed", r[0][:10], str(e)[:60], flush=True)
        for attempt in range(6):
            try:
                rows, _, cov = pm.market_trades(r[0], start=int(r[1]) - PRE, end=min(int(r[2]), H - 1), taker_only=True)
                return r[0], rows
            except HttpError as e:  # Cloudflare 429: back off and retry this window
                print("retry", r[0][:10], attempt, str(e)[:80], flush=True)
                time.sleep(30 + 30 * attempt)
        return r[0], []

    for d in days:
        f = OUT / f"taker5m_day_{d}.parquet"
        if f.exists():
            continue
        wd = w[(w["start_ts"] >= d) & (w["start_ts"] < d + 86400)]
        out = []
        with ThreadPoolExecutor(4) as ex:
            for cid, rows in ex.map(one, list(zip(wd["cid"], wd["start_ts"], wd["end_ts"]))):
                for r in rows:
                    if r.get("timestamp", 0) >= H:
                        continue
                    out.append((cid, int(r["timestamp"]), r.get("side"), str(r.get("asset")), snap_price(float(r.get("price", 0))),
                                float(r.get("size", 0)), (r.get("proxyWallet") or "").lower(), r.get("transactionHash")))
        df = pd.DataFrame(out, columns=["cid", "ts", "side", "asset", "price", "size", "wallet", "tx"])
        df["side"] = df["side"].astype("category")
        df["price"] = df["price"].astype("float32")
        df["size"] = df["size"].astype("float32")
        df.to_parquet(f, index=False)
        print("day", d, "windows", len(wd), "rows", len(df), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "meta":
        meta()
    else:
        tapes(int(sys.argv[2]), int(sys.argv[3]), len(sys.argv) > 4 and sys.argv[4] == "rev")
