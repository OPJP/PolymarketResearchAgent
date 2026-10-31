"""Iteration 3: other perpetual venues (OKX BTC-USDT-SWAP, Bybit BTCUSDT linear perp) daily trade archives for a few
pre-H days, reduced at once to parquet (T ms, p, q, m = seller-initiated) in .cache/re/btc5m-bot/venues/<venue>/<day0>.parquet;
the raw download (its own empty directory) is deleted. No checksums are published for these archives: the reduction checks
the schema, monotone-ish timestamps inside [day-1, day+2) and max T < H.
Usage: python -I fetch_venues.py okx|bybit YYYY-MM-DD [...]"""
import os, sys, io, gzip, zipfile, calendar, time, shutil, tempfile
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import httpx, numpy as np, pandas as pd
H = 1792713600
URL = {"okx": "https://static.okx.com/cdn/okex/traderecords/trades/daily/{c}/BTC-USDT-SWAP-trades-{d}.zip",
       "bybit": "https://public.bybit.com/trading/BTCUSDT/BTCUSDT{d}.csv.gz",
       "bybitspot": "https://public.bybit.com/spot/BTCUSDT/BTCUSDT_{d}.csv.gz",
       "okxspot": "https://static.okx.com/cdn/okex/traderecords/trades/daily/{c}/BTC-USDT-trades-{d}.zip",
       "bnspot": "https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{d}.zip"}

if __name__ == "__main__":
    venue = sys.argv[1]
    out_dir = f"{_ROOT}/.cache/re/btc5m-bot/venues/{venue}"; os.makedirs(out_dir, exist_ok=True)
    for d in sys.argv[2:]:
        day0 = calendar.timegm(time.strptime(d, "%Y-%m-%d")); assert day0 + 86400 <= H
        path = f"{out_dir}/{day0}.parquet"
        if os.path.exists(path):
            continue
        tmp = tempfile.mkdtemp(prefix="dl_", dir=f"{_ROOT}/.cache/re/btc5m-bot")
        raw = f"{tmp}/raw.bin"
        with httpx.stream("GET", URL[venue].format(d=d, c=d.replace("-", "")), timeout=180, follow_redirects=True) as r:
            r.raise_for_status()
            with open(raw, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        if venue == "bnspot":
            chk = httpx.get(URL[venue].format(d=d) + ".CHECKSUM", timeout=30).text.split()[0]
            assert __import__("hashlib").sha256(open(raw, "rb").read()).hexdigest() == chk, "checksum mismatch"
            with zipfile.ZipFile(raw) as zz:
                txt = zz.read(zz.namelist()[0])
            df = pd.read_csv(io.BytesIO(txt), header=None)
            if not str(df.iloc[0, 0]).isdigit():
                df = df.iloc[1:]
            T = df.iloc[:, 5].astype(np.int64).to_numpy()
            T = np.where(T > 10**14, T // 1000, T)  # spot archives may be in microseconds
            out = pd.DataFrame({"T": T, "p": df.iloc[:, 1].astype(float), "q": df.iloc[:, 2].astype(np.float32),
                                "m": df.iloc[:, 6].astype(str).str.lower().isin(["true", "1"])})
        elif venue in ("okx", "okxspot"):
            with zipfile.ZipFile(raw) as zz:
                txt = zz.read(zz.namelist()[0])
            df = pd.read_csv(io.BytesIO(txt), encoding_errors="replace")
            cols = {c.lower().strip(): c for c in df.columns}
            tcol = next(cols[k] for k in cols if "time" in k); pcol = cols["price"]; qcol = next(cols[k] for k in cols if k in ("size", "qty", "sz"))
            scol = cols["side"]
            T = pd.to_numeric(df[tcol], errors="coerce").to_numpy()
            out = pd.DataFrame({"T": T.astype(np.int64), "p": pd.to_numeric(df[pcol]).astype(float), "q": pd.to_numeric(df[qcol]).astype(np.float32),
                                "m": df[scol].astype(str).str.lower().str.startswith("s")})
        else:
            with gzip.open(raw) as g:
                df = pd.read_csv(g)
            cols = {c.lower().strip(): c for c in df.columns}
            ts = pd.to_numeric(df[cols["timestamp"]]).to_numpy(float)
            ts = np.where(ts > 1e11, ts / 1000.0, ts)  # bybit spot files are in ms, perp files in seconds
            df = df.rename(columns={cols.get("volume", cols.get("size", "size")): "size", cols["price"]: "price", cols["side"]: "side"})
            df["timestamp"] = ts
            out = pd.DataFrame({"T": (pd.to_numeric(df["timestamp"]) * 1000).round().astype(np.int64), "p": pd.to_numeric(df["price"]).astype(float),
                                "q": pd.to_numeric(df["size"]).astype(np.float32), "m": df["side"].astype(str).str.lower().str.startswith("s")})
        shutil.rmtree(tmp)
        out = out.sort_values("T", kind="stable").reset_index(drop=True)
        assert out["T"].min() >= (day0 - 86400) * 1000 and out["T"].max() < min(H, day0 + 2 * 86400) * 1000, (out["T"].min(), out["T"].max())
        assert out.p.between(10_000, 1_000_000).all()
        out.to_parquet(path, index=False)
        print(venue, d, len(out), "rows", round(out["T"].min() / 1000 - day0), round(out["T"].max() / 1000 - day0), round(os.path.getsize(path) / 1e6, 1), "MB", flush=True)
