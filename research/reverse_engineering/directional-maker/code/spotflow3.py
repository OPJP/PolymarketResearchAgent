"""Iteration 3, family N4 (Binance order flow): per-second Binance BTCUSDT kline fields beyond the close
(volume, trade count, taker-buy volume, high/low), re-read from the cached daily 1-s kline archives
(the same SHA-256-checked files polyrea.adapters.spot.binance_seconds uses). Days 2026-10-08..10-22 only (< H).

python code/spotflow3.py   -> .cache/re/directional-maker/spotflow_1s.parquet
"""
from __future__ import annotations

import hashlib
import io
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402
from polyrea.adapters.spot import BINANCE_ARCHIVE, BINANCE_SYMBOLS  # noqa: E402

H = 1792713600
D0 = 1791417600  # 2026-10-08
OUT = ROOT / ".cache/re/directional-maker"


def main():
    http = shared_client()
    fr = []
    t0 = time.time()
    for day0 in range(D0, H, 86400):
        day = time.strftime("%Y-%m-%d", time.gmtime(day0))
        url = BINANCE_ARCHIVE.format(sym=BINANCE_SYMBOLS["btc"], day=day)
        body, _ = http.get_bytes(url, adapter="binance.archive", max_age=None)
        check, _ = http.get_bytes(url + ".CHECKSUM", adapter="binance.archive", max_age=None)
        assert hashlib.sha256(body).hexdigest() == check.decode().split()[0], url
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            df = pd.read_csv(z.open(z.namelist()[0]), header=None)
        df = df[pd.to_numeric(df[0], errors="coerce").notna()]
        t_open = df[0].astype(np.int64).to_numpy()
        sec = np.where(t_open > 10**14, t_open // 1_000_000, t_open // 1000)
        out = pd.DataFrame({"sec": sec, "hi": df[2].astype(np.float64), "lo": df[3].astype(np.float64), "px": df[4].astype(np.float64),
                            "vol": df[5].astype(np.float32), "ntr": df[8].astype(np.int32), "tbv": df[9].astype(np.float32)})
        out = out[out["sec"] < H]
        fr.append(out)
        print(day, len(out), f"{time.time()-t0:.0f}s", flush=True)
    pd.concat(fr, ignore_index=True).to_parquet(OUT / "spotflow_1s.parquet", index=False)


if __name__ == "__main__":
    main()
