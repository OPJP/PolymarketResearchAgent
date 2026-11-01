"""Iteration 2: Binance USD-M BTCUSDT perpetual aggTrades daily archive (data.binance.vision), checksum-verified,
reduced at once to parquet (T ms, p, q, m) in .cache/re/btc5m-bot/fut/<day0>.parquet; the zip is deleted.
Only days < H. Usage: python fetch_futures.py YYYY-MM-DD [...]"""
import os, sys, io, hashlib, zipfile, calendar, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import httpx, numpy as np, pandas as pd
H = 1792713600
OUT = _ROOT + "/.cache/re/btc5m-bot/fut"
URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for d in sys.argv[1:]:
        day0 = calendar.timegm(time.strptime(d, "%Y-%m-%d")); assert day0 + 86400 <= H
        path = f"{OUT}/{day0}.parquet"
        if os.path.exists(path):
            continue
        z = f"{OUT}/{d}.zip"
        with httpx.stream("GET", URL.format(d=d), timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(z, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        chk = httpx.get(URL.format(d=d) + ".CHECKSUM", timeout=30).text.split()[0]
        assert hashlib.sha256(open(z, "rb").read()).hexdigest() == chk, "checksum mismatch"
        with zipfile.ZipFile(z) as zz:
            raw = zz.read(zz.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw), header=None if not raw[:3].isalpha() else 0)
        if not str(df.iloc[0, 0]).isdigit():
            df = df.iloc[1:]
        df = df.iloc[:, [1, 2, 5, 6]]; df.columns = ["p", "q", "T", "m"]
        df = pd.DataFrame({"T": df["T"].astype(np.int64), "p": df.p.astype(float), "q": df.q.astype(np.float32),
                           "m": df.m.astype(str).str.lower().isin(["true", "1"])})
        assert df["T"].max() < H * 1000
        df.to_parquet(path, index=False); os.remove(z)
        print(d, len(df), "rows", round(os.path.getsize(path) / 1e6, 1), "MB", flush=True)
