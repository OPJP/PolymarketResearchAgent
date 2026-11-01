"""Iteration 8 (A5 / X73): Binance BTCUSDT USD-M futures and spot aggTrades for one June day at 50-ms resolution
(SHA-256 checked, the zip is held in memory and never stored): last trade price per 50-ms bin.
Output .cache/re/directional-maker/june/{fut,spot}50_<day>.parquet with columns b50 (= ms // 50), px.
    python code8/fut_ms.py 2026-06-12
"""
import hashlib
import io
import sys
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker/june"
URLS = {"fut": "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip",
        "spot": "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"}


def get(kind, d, cl):
    p = OUT / f"{kind}50_{d}.parquet"
    if p.exists():
        return
    u = URLS[kind].format(d=d)
    r = cl.get(u)
    r.raise_for_status()
    z = r.content
    chk = cl.get(u + ".CHECKSUM").text.split()[0]
    if hashlib.sha256(z).hexdigest() != chk:
        raise RuntimeError(f"checksum mismatch {kind} {d}")
    zf = zipfile.ZipFile(io.BytesIO(z))
    n = zf.namelist()[0]
    head = zf.open(n).readline().decode()
    cols = [1, 5]
    df = pd.read_csv(zf.open(n), header=0 if head[0].isalpha() else None, usecols=cols, dtype={1: "float64"} if not head[0].isalpha() else None)
    df.columns = ["px", "ms"]
    del z, zf
    ms = df.ms.to_numpy(np.int64)
    if ms[0] > 1e14:
        ms = ms // 1000
    b = ms // 50
    last = np.r_[b[1:] != b[:-1], True]
    out = pd.DataFrame({"b50": b[last], "px": df.px.to_numpy()[last].astype("float64")})
    out.to_parquet(p, index=False)
    print(kind, d, len(df), "trades ->", len(out), "bins", flush=True)


if __name__ == "__main__":
    cl = httpx.Client(timeout=300, follow_redirects=True)
    for d in sys.argv[1:]:
        for k in ("fut", "spot"):
            get(k, d, cl)
