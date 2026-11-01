"""Download one day of Binance BTCUSDT spot aggTrades (SHA-256 checked), reduce to per-trade-ms last price, delete zip.
Output: .cache/re/directional-maker/agg_<day>.parquet with columns ms (int64), px (float64), qty, buyer_maker."""
import hashlib, io, sys, zipfile
from pathlib import Path
import httpx, numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker"
day = sys.argv[1]
u = f"https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{day}.zip"
z = httpx.get(u, timeout=120, follow_redirects=True).content
chk = httpx.get(u + ".CHECKSUM", timeout=30, follow_redirects=True).text.split()[0]
assert hashlib.sha256(z).hexdigest() == chk, "checksum mismatch"
with zipfile.ZipFile(io.BytesIO(z)) as zf:
    name = zf.namelist()[0]
    df = pd.read_csv(zf.open(name), header=None, usecols=[1, 2, 5, 6], names=["px", "qty", "ms", "buyer_maker"],
                     dtype={1: "float64", 2: "float32", 5: "int64", 6: "str"})
# timestamps may be in microseconds in newer archives
if df.ms.iloc[0] > 1e14:
    df["ms"] = df.ms // 1000
df["buyer_maker"] = df.buyer_maker.str.lower().eq("true")
df.to_parquet(OUT / f"aggfut_{day}.parquet")
print(day, len(df), df.ms.min(), df.ms.max())
