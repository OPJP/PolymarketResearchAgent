"""Iteration 4: Binance USD-M ETHUSDT perpetual aggTrades daily archive (cross-asset lead test), checksum-verified,
reduced at once to parquet (T ms int64, p float64, q float32, m bool) in .cache/re/btc5m-bot/venues/ethfut/<day0>.parquet;
the zip is downloaded into its own empty temp dir and deleted. Only days with day0 + 86400 <= H.
Usage: python -I fetch_eth.py YYYY-MM-DD [...]"""
import os, sys, io, hashlib, zipfile, calendar, time, tempfile, shutil
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import httpx, numpy as np, pandas as pd
H = 1792713600
SYM = os.environ.get("ALT_SYM", "ETHUSDT")  # other perps: ALT_SYM=SOLUSDT etc.
OUT = _ROOT + "/.cache/re/btc5m-bot/venues/" + ("ethfut" if SYM == "ETHUSDT" else SYM.lower().replace("usdt", "") + "fut")
URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/" + SYM + "/" + SYM + "-aggTrades-{d}.zip"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for d in sys.argv[1:]:
        day0 = calendar.timegm(time.strptime(d, "%Y-%m-%d")); assert day0 + 86400 <= H
        path = f"{OUT}/{day0}.parquet"
        if os.path.exists(path):
            continue
        tmp = tempfile.mkdtemp(prefix="ethfut_")
        try:
            z = os.path.join(tmp, "a.zip")
            with httpx.stream("GET", URL.format(d=d), timeout=120, follow_redirects=True) as r:
                r.raise_for_status()
                with open(z, "wb") as fh:
                    for chunk in r.iter_bytes(1 << 20):
                        fh.write(chunk)
            chk = httpx.get(URL.format(d=d) + ".CHECKSUM", timeout=30).text.split()[0]
            assert hashlib.sha256(open(z, "rb").read()).hexdigest() == chk, "checksum mismatch"
            with zipfile.ZipFile(z) as zz:
                raw = zz.read(zz.namelist()[0])
            df = pd.read_csv(io.BytesIO(raw), header=None, usecols=[1, 2, 5, 6], dtype=str)
            df = df[df[5].str.isdigit()]
            df = pd.DataFrame({"T": df[5].astype(np.int64), "p": df[1].astype(float), "q": df[2].astype(np.float32),
                               "m": df[6].str.lower().isin(["true", "1"])})
            if df["T"].max() > 10**14:  # microseconds
                df["T"] = df["T"] // 1000
            assert df["T"].max() < H * 1000 and df["T"].min() >= (day0 - 60) * 1000
            df.sort_values("T").to_parquet(path, index=False)
            print(d, len(df), "rows", round(os.path.getsize(path) / 1e6, 1), "MB", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
