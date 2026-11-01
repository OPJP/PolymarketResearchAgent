"""Iteration 9 (X83 groundwork for the family-general universe): data-api taker tapes of the BTC 4h and BTC hourly markets
the cluster traded in 10-16..10-30 (development and the released lot), for the next iteration's per-family presence
models. Markets from the cluster's activity (condition id, slug); tape window [start - 900, end) with start/end from the
slug (4h: unix start; hourly: the ET hour). Output: .cache/re/directional-maker/fam/<fam>_tapes.parquet (cid, ts, side,
asset, price, size, wallet, tx) and <fam>_markets.parquet. Development data only (no sealed block: everything ends before
2026-10-31 00:00 UTC)."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from polyrea.adapters.polymarket import PolymarketData  # noqa: E402
from scope import fam  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
OUT = C / "fam"
OUT.mkdir(exist_ok=True)
A, B = 1792108800, 1793404800  # 10-16 .. 10-31 00:00
MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}


def hour_start(slug):
    p = slug.split("-")  # bitcoin-up-or-down-october-31-2026-10am-et
    mon, day, yr, hh = p[-5], int(p[-4]), int(p[-3]), p[-2]
    h24 = int(hh[:-2]) % 12 + (12 if hh.endswith("pm") else 0)
    return int(pd.Timestamp(f"{yr}-{MON[mon]:02d}-{day:02d} {h24:02d}:00", tz="US/Eastern").timestamp())


def main():
    parts = []
    for n in ("bosona", "almach", "momoney"):
        for p in (C / f"activity_{n}.parquet", C / "exam" / f"activity_{n}.parquet"):
            parts.append(pd.read_parquet(p, columns=["timestamp", "type", "slug", "conditionId"]))
    a = pd.concat(parts)
    a = a[(a.type == "TRADE") & (a.timestamp >= A) & (a.timestamp < B)]
    a["fam"] = a.slug.map(fam)
    pm = PolymarketData()
    for f in ("btc_4h", "btc_hourly"):
        mk = a[a.fam == f].drop_duplicates("conditionId")[["conditionId", "slug"]].copy()
        if f == "btc_4h":
            mk["st"] = mk.slug.str.rsplit("-", n=1).str[1].astype(int)
            mk["en"] = mk.st + 14400
        else:
            mk["st"] = mk.slug.map(hour_start)
            mk["en"] = mk.st + 3600
        mk = mk[(mk.st >= A) & (mk.en <= B)]
        mk.to_parquet(OUT / f"{f}_markets.parquet", index=False)
        t0 = time.time()

        def one(r):
            rows, _, cov = pm.market_trades(r.conditionId, start=int(r.st) - 900, end=int(r.en) - 1, taker_only=True)
            return r.conditionId, rows, cov.status

        out, bad = [], 0
        with ThreadPoolExecutor(4) as ex:
            for i, (cid, rows, st) in enumerate(ex.map(one, list(mk.itertuples(index=False)))):
                bad += st == "partial"
                if rows:
                    d = pd.DataFrame(rows)
                    keep = [c for c in ("timestamp", "side", "asset", "price", "size", "proxyWallet", "transactionHash") if c in d.columns]
                    d = d[keep].rename(columns={"timestamp": "ts", "proxyWallet": "wallet", "transactionHash": "tx"})
                    d["cid"] = cid
                    out.append(d)
                if i % 50 == 0:
                    print(f, i, "of", len(mk), f"{time.time() - t0:.0f}s partial {bad}", flush=True)
        T = pd.concat(out, ignore_index=True)
        T["price"] = T.price.astype("float32")
        T["size"] = T["size"].astype("float32")
        T.to_parquet(OUT / f"{f}_tapes.parquet", index=False)
        print(f, "markets", len(mk), "rows", len(T), "partial", bad, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
