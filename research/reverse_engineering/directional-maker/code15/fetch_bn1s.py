"""directional-maker iteration 15: Binance spot 1-s closes for the non-BTC-5m/15m families (X173 / X175 / X164).

Archives (data.binance.vision spot daily klines 1s, SHA-256 checked, reduced at once to parquet [sec, close], zip deleted)
for the development days below; REST 1-s klines for the development blocks after the archive (10-31 00-06, 10-31 12-18,
11-01 06:00-now). Sealed blocks are never requested (tools/sealed.py intervals).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code15/fetch_bn1s.py
"""
from __future__ import annotations

import hashlib
import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "research" / "reverse_engineering" / "tools"))
import sealed  # noqa: E402

OUT = ROOT / ".cache/re/directional-maker/bn1s"
OUT.mkdir(parents=True, exist_ok=True)
ALTS = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
BUILD_DAYS = ["2026-10-08", "2026-10-10", "2026-10-12", "2026-10-14", "2026-10-16", "2026-10-18", "2026-10-20", "2026-10-22"]
LOT_DAYS = [f"2026-10-{d:02d}" for d in range(23, 31)]
KEY = "directional-maker"


def arch(sym: str, day: str) -> str:
    f = OUT / f"{sym}_{day}.parquet"
    if f.exists():
        return f"{sym} {day} cached"
    url = f"https://data.binance.vision/data/spot/daily/klines/{sym}/1s/{sym}-1s-{day}.zip"
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        r = c.get(url)
        if r.status_code != 200:
            return f"{sym} {day} HTTP {r.status_code}"
        ck = c.get(url + ".CHECKSUM")
        if ck.status_code == 200:
            want = ck.text.split()[0].strip().lower()
            got = hashlib.sha256(r.content).hexdigest()
            if want != got:
                return f"{sym} {day} CHECKSUM MISMATCH"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    with z.open(z.namelist()[0]) as fh:
        d = pd.read_csv(fh, header=None, usecols=[0, 1, 4])
    ot = d[0].to_numpy(np.int64)
    ot = np.where(ot > 10**14, ot // 1_000_000, ot // 1000)  # microseconds since 2025
    pd.DataFrame({"sec": ot.astype(np.int64), "open": d[1].astype(np.float64), "close": d[4].astype(np.float64)}).to_parquet(f, index=False)
    return f"{sym} {day} rows {len(d)}"


def rest(sym: str, a: int, b: int) -> str:
    f = OUT / f"{sym}_rest_{a}_{b}.parquet"
    if f.exists():
        return f"{sym} rest {a} cached"
    rows = []
    with httpx.Client(timeout=30) as c:
        t = a * 1000
        while t < b * 1000:
            r = c.get("https://api.binance.com/api/v3/klines", params={"symbol": sym, "interval": "1s", "startTime": t,
                                                                        "endTime": b * 1000 - 1, "limit": 1000})
            if r.status_code != 200:
                time.sleep(2)
                continue
            j = r.json()
            if not j:
                break
            rows += [(int(x[0]) // 1000, float(x[1]), float(x[4])) for x in j]
            t = int(j[-1][0]) + 1000
            time.sleep(0.12)
    pd.DataFrame(rows, columns=["sec", "open", "close"]).drop_duplicates("sec").to_parquet(f, index=False)
    return f"{sym} rest {a}-{b} rows {len(rows)}"


def main():
    jobs = [(s, d) for s in ALTS for d in BUILD_DAYS + LOT_DAYS] + [("BTCUSDT", d) for d in LOT_DAYS]
    with ThreadPoolExecutor(4) as ex:
        for msg in ex.map(lambda x: arch(*x), jobs):
            print(msg, flush=True)
    now = int(time.time()) - 5
    blocks = [(a, b) for a, b in sealed.intervals(KEY, 1793404800, now, sealed=False)]
    print("development blocks after T0:", blocks, flush=True)
    for s in ALTS + ["BTCUSDT"]:
        for a, b in blocks:
            assert not sealed.is_sealed(a, KEY) and not sealed.is_sealed(b - 1, KEY)
            print(rest(s, a, b), flush=True)


if __name__ == "__main__":
    main()
