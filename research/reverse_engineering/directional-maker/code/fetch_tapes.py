"""Windows (Gamma), taker tapes (data-api) and Binance 1-s spot for every BTC
Up/Down window of a duration in [start, H). Development data only.

Outputs (.cache/re/directional-maker/):
  windows_<dur>.parquet   cid, start_ts, end_ts, up_token, down_token, up_payout(settlement only)
  taker_<dur>.parquet     taker tape rows (one per aggressive order) from start-900 to end
  spot_btc_1s.parquet     Binance 1-s close (sec, px) for [start-86400, H)
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
OUT = ROOT / ".cache/re/directional-maker"
PRE = 900


def main(start: int, dur: str, do_spot: int, rev: bool = False) -> None:
    pm = PolymarketData()
    t0 = time.time()
    if do_spot:
        rows, _ = binance_seconds("btc", start - 86400, H)
        sp = pd.DataFrame(rows, columns=["sec", "px"])
        sp["sec"] = sp["sec"].astype("int64")
        sp = sp[sp["sec"] < H]
        sp.to_parquet(OUT / "spot_btc_1s.parquet", index=False)
        print("spot", len(sp), f"{time.time()-t0:.0f}s", flush=True)
    slugs = window_slugs("btc", dur, start, H)
    markets = fetch_windows(slugs)
    wins = [w for w in windows_from_markets(markets) if w.end_ts <= H]
    if rev:
        wins = wins[::-1]
    wdf = pd.DataFrame([{"cid": w.condition_id, "start_ts": w.start_ts, "end_ts": w.end_ts, "up_token": w.up_token,
                         "down_token": w.down_token, "up_payout": w.up_payout, "fee_rate": w.fee_rate,
                         "twap": w.twap_seconds} for w in wins])
    if not rev:
        wdf.to_parquet(OUT / f"windows_{dur}.parquet", index=False)
    print("windows", len(wdf), "of", len(slugs), f"{time.time()-t0:.0f}s", flush=True)

    def tape(w):
        rows, _, cov = pm.market_trades(w.condition_id, start=w.start_ts - PRE, end=min(w.end_ts, H - 1), taker_only=True)
        return w.condition_id, rows, cov.status

    out = []
    bad = 0
    with ThreadPoolExecutor(6) as ex:
        for i, (cid, rows, st) in enumerate(ex.map(tape, wins)):
            bad += st == "partial"
            for r in rows:
                if r.get("timestamp", 0) >= H:
                    continue
                out.append({"cid": cid, "ts": int(r["timestamp"]), "side": r.get("side"), "asset": str(r.get("asset")),
                            "outcome": r.get("outcome"), "price": snap_price(float(r.get("price", 0))),
                            "size": float(r.get("size", 0)), "wallet": (r.get("proxyWallet") or "").lower(),
                            "tx": r.get("transactionHash")})
            if i % 500 == 0:
                print("tapes", i, len(out), f"{time.time()-t0:.0f}s", flush=True)
    tdf = pd.DataFrame(out)
    tdf.to_parquet(OUT / (f"taker_{dur}_rev.parquet" if rev else f"taker_{dur}.parquet"), index=False)
    print("taker rows", len(tdf), "partial", bad, f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2], int(sys.argv[3]), len(sys.argv) > 4 and sys.argv[4] == "rev")
