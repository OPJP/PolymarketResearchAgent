"""Public tapes (data-api /trades) for CS2 match/map-winner markets in the development period.

Order: (1) every market the wallet traded with game start in [D0, H): full tape + taker-only tape;
(2) every other CS2 moneyline / child_moneyline market with game start in [D0, H): taker-only, then full.
All requests end at H - 1 (no holdout rows). Per-market parquet in .cache/re/tommy-cs2-maker/tapes/.
Usage: fetch_tapes.py [D0]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402

H = 1792713600
OUT = ROOT / ".cache/re/tommy-cs2-maker"
TAPES = OUT / "tapes"
COLS = ["proxyWallet", "side", "asset", "outcomeIndex", "size", "price", "timestamp", "transactionHash"]


def fetch(pm, cid, start, taker_only):
    path = TAPES / f"{cid}_{'tk' if taker_only else 'full'}.parquet"
    if path.exists():
        return
    rows, _, cov = pm.market_trades(cid, start=start, end=H - 1, taker_only=taker_only, max_rows=400_000)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=COLS)
    df = df[[c for c in COLS if c in df.columns]]
    df = df[df["timestamp"] < H] if len(df) else df
    df.attrs["coverage"] = cov.status
    df.to_parquet(path, index=False)


def main(d0: int = 1792022400) -> None:
    TAPES.mkdir(parents=True, exist_ok=True)
    pm = PolymarketData()
    u = pd.read_parquet(OUT / "universe.parquet")
    act = pd.read_parquet(OUT / "activity_dev.parquet")
    traded = set(act.loc[(act["type"] == "TRADE") & (act["timestamp"] >= d0 - 86400), "conditionId"])
    u = u[u["smt"].isin(["moneyline", "child_moneyline"]) & (u["gs_ts"] >= d0) & (u["gs_ts"] < H)]
    tr = [c for c in u["cid"] if c in traded]
    # wallet markets outside the CS2 universe (e.g. Dota 2) are added too
    extra = sorted(traded - set(u["cid"]))
    un = [c for c in u["cid"] if c not in traded]
    start_of = dict(zip(u["cid"], (u["listed_ts"].astype("int64") - 3600).tolist()))
    t0 = time.time()
    jobs = [(c, False) for c in tr + extra] + [(c, True) for c in tr + extra] + [(c, True) for c in un] + [(c, False) for c in un]
    print("jobs", len(jobs), "traded", len(tr), "extra", len(extra), "untraded", len(un), flush=True)
    for i, (c, tko) in enumerate(jobs):
        try:
            fetch(pm, c, start_of.get(c, d0 - 3 * 86400), tko)
        except Exception as e:  # noqa: BLE001
            print("ERR", c, tko, str(e)[:120], flush=True)
        if i % 50 == 0:
            print(i, f"{time.time()-t0:.0f}s", flush=True)
    print("done", f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
