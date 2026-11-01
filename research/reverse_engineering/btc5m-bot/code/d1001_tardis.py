"""Iteration 5: venue ORDER-BOOK (top of book) and trade streams for 2026-10-01 00:00..END UTC from Tardis.dev's free
first-day-of-month datasets (datasets.tardis.dev, no API key). 2026-10-01 is development data (BUILD side, < H).
Each csv.gz is STREAMED and decompressed on the fly; only the first hours are read (the connection is closed at END),
nothing raw is written to disk. Reduced to per-100 ms buckets and saved as parquet in .cache/re/btc5m-bot/d1001/.
  quotes (book_ticker / quotes): last bid, ask, bid size, ask size in each 100 ms bucket + update count
  trades: last price, signed volume (buyer-initiated +), count in each 100 ms bucket
Run with python -I (downloaded data is untrusted). Usage: python -I d1001_tardis.py END_HOURS name [name ...]"""
import os, sys, io, zlib, time
import httpx, numpy as np, pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
OUT = _ROOT + "/.cache/re/btc5m-bot/d1001"
H = 1792713600
DAY0 = 1790812800  # 2026-10-01 00:00 UTC
STREAMS = {  # name: (exchange, data_type, symbol)
    "bnf_book": ("binance-futures", "book_ticker", "BTCUSDT"),
    "bnf_trd": ("binance-futures", "trades", "BTCUSDT"),
    "eth_book": ("binance-futures", "book_ticker", "ETHUSDT"),
    "eth_trd": ("binance-futures", "trades", "ETHUSDT"),
    "bns_book": ("binance", "book_ticker", "BTCUSDT"),
    "bns_trd": ("binance", "trades", "BTCUSDT"),
    "byb_book": ("bybit", "quotes", "BTCUSDT"),
    "byb_trd": ("bybit", "trades", "BTCUSDT"),
    "okx_book": ("okex-swap", "quotes", "BTC-USDT-SWAP"),
    "okx_trd": ("okex-swap", "trades", "BTC-USDT-SWAP"),
    "bys_trd": ("bybit-spot", "trades", "BTCUSDT"),
    "oks_trd": ("okex", "trades", "BTC-USDT"),
}


def reduce_chunk(df, kind):
    ts = df["timestamp"].to_numpy(np.int64)  # exchange timestamp, microseconds
    b = (ts // 100_000).astype(np.int64)  # 100 ms bucket id
    if kind == "book":
        g = pd.DataFrame({"b": b, "bid": df["bid_price"].to_numpy(float), "ask": df["ask_price"].to_numpy(float),
                          "bq": df["bid_amount"].to_numpy(float), "aq": df["ask_amount"].to_numpy(float)})
        last = g.groupby("b", sort=True).last()
        last["n"] = g.groupby("b", sort=True).size()
        return last
    side = np.where(df["side"].astype(str).str.lower().str.startswith("b"), 1.0, -1.0)
    g = pd.DataFrame({"b": b, "p": df["price"].to_numpy(float), "sv": side * df["amount"].to_numpy(float)})
    last = g.groupby("b", sort=True).agg(p=("p", "last"), sv=("sv", "sum"), n=("p", "size"))
    return last


def fetch(name, end_ts):
    ex, dt, sym = STREAMS[name]
    path = f"{OUT}/{name}.parquet"
    if os.path.exists(path):
        return
    url = f"https://datasets.tardis.dev/v1/{ex}/{dt}/2026/10/01/{sym}.csv.gz"
    kind = "book" if dt in ("book_ticker", "quotes") else "trd"
    dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
    header = None; buf = b""; parts = []; done = False; nbytes = 0; t0 = time.time()
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            nbytes += len(chunk)
            buf += dec.decompress(chunk)
            if header is None:
                k = buf.find(b"\n")
                if k < 0:
                    continue
                header = buf[:k].decode().strip().split(","); buf = buf[k + 1:]
            k = buf.rfind(b"\n")
            if k < 0:
                continue
            block, buf = buf[:k + 1], buf[k + 1:]
            df = pd.read_csv(io.BytesIO(block), header=None, names=header)
            red = reduce_chunk(df, kind)
            parts.append(red)
            if df["timestamp"].iloc[-1] >= end_ts * 1_000_000:
                done = True
                break
    out = pd.concat(parts)
    # chunk boundaries can split a bucket: re-reduce
    if kind == "book":
        n = out.groupby(level=0)["n"].sum()
        out = out.groupby(level=0).last(); out["n"] = n
    else:
        out = out.groupby(level=0).agg(p=("p", "last"), sv=("sv", "sum"), n=("n", "sum"))
    out = out[(out.index >= DAY0 * 10) & (out.index < end_ts * 10)]
    assert out.index.max() < H * 10
    out = out.reset_index().rename(columns={"index": "b"})
    out.to_parquet(path, index=False)
    print(name, len(out), "buckets", round(nbytes / 1e6, 1), "MB read", round(time.time() - t0), "s", "complete" if done else "EOF", flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    end_ts = DAY0 + int(float(sys.argv[1]) * 3600)
    assert end_ts <= DAY0 + 86400 < H
    for nm in sys.argv[2:]:
        try:
            fetch(nm, end_ts)
        except Exception as e:
            print("FAILED", nm, repr(e)[:300], flush=True)
