"""A3: Binance USD-M futures BTCUSDT aggTrades daily archives (SHA-256 checked, held in memory, never stored) reduced to
per-second last price, volume and taker-buy volume: .cache/re/directional-maker/fut1s/<day>.parquet."""
import hashlib, io, sys, time, zipfile
from datetime import date, timedelta
from pathlib import Path
import httpx, numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / ".cache/re/directional-maker/fut1s"
OUT.mkdir(parents=True, exist_ok=True)
BYBIT = "https://public.bybit.com/trading/BTCUSDT/BTCUSDT{d}.csv.gz"
URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"


def get_day(d: str, client: httpx.Client | None = None) -> pd.DataFrame:
    p = OUT / f"{d}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    cl = client or httpx.Client(timeout=180, follow_redirects=True)
    r = cl.get(URL.format(d=d))
    if r.status_code == 404:  # Binance futures archive not published (e.g. 2026-10-28): Bybit BTCUSDT perp trades
        return _bybit_day(d, cl)
    z = r.content
    chk = cl.get(URL.format(d=d) + ".CHECKSUM").text.split()[0]
    if hashlib.sha256(z).hexdigest() != chk:
        raise RuntimeError(f"checksum mismatch {d}")
    zf = zipfile.ZipFile(io.BytesIO(z)); n = zf.namelist()[0]
    head = zf.open(n).readline().decode()
    df = pd.read_csv(zf.open(n), header=0 if head[0].isalpha() else None, usecols=[1, 2, 5, 6])
    df.columns = ["px", "qty", "ms", "bm"]
    if df.ms.iloc[0] > 1e14:
        df["ms"] = df.ms // 1000
    df["sec"] = df.ms // 1000
    df["bm"] = df.bm.astype(str).str.lower().eq("true")
    df["buy"] = np.where(df.bm, 0.0, df.qty)
    g = df.groupby("sec").agg(px=("px", "last"), vol=("qty", "sum"), buy=("buy", "sum")).reset_index()
    g["px"] = g.px.astype("float64"); g["vol"] = g.vol.astype("float32"); g["buy"] = g.buy.astype("float32")
    g.to_parquet(p)
    return g


def _bybit_day(d: str, cl: httpx.Client) -> pd.DataFrame:
    import gzip
    r = cl.get(BYBIT.format(d=d))
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(gzip.decompress(r.content)), usecols=["timestamp", "side", "size", "price"])
    df = df.sort_values("timestamp", kind="stable")
    df["sec"] = np.floor(df.timestamp).astype(np.int64)
    df["buy"] = np.where(df.side == "Buy", df["size"], 0.0)
    g = df.groupby("sec").agg(px=("price", "last"), vol=("size", "sum"), buy=("buy", "sum")).reset_index()
    g["px"] = g.px.astype("float64"); g["vol"] = g.vol.astype("float32"); g["buy"] = g.buy.astype("float32")
    g.to_parquet(OUT / f"{d}.parquet")
    return g


if __name__ == "__main__":
    a, b = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
    cl = httpx.Client(timeout=180, follow_redirects=True)
    d = a
    while d <= b:
        t0 = time.time()
        g = get_day(d.isoformat(), cl)
        print(d, len(g), round(time.time() - t0, 1), "s", flush=True)
        d += timedelta(days=1)
