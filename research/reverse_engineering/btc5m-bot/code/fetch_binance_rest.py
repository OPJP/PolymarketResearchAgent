"""Iteration 5 (live lab support): Binance USD-M futures BTCUSDT and ETHUSDT aggTrades through the public REST API for a
DEVELOPMENT interval after T0 (tools/sealed.py; refuses sealed time). Paged by fromId after a startTime anchor.
Writes .cache/re/btc5m-bot/post/bnf_<sym>_<a>_<b>.parquet with T (ms), p, q, m.
Usage: python fetch_binance_rest.py SYMBOL START END"""
import os, sys, time
import numpy as np, pandas as pd, httpx
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import sealed
URL = "https://fapi.binance.com/fapi/v1/aggTrades"
OUT = _ROOT + "/.cache/re/btc5m-bot/post"


def fetch(sym, a, b):
    for x in range(int(a), int(b), 60):
        assert not sealed.is_sealed(x, "btc5m-bot"), "sealed time"
    cl = httpx.Client(timeout=30)
    rows = []
    r = cl.get(URL, params={"symbol": sym, "startTime": int(a * 1000), "endTime": int(a * 1000) + 59_999, "limit": 1000}); r.raise_for_status()
    rows += r.json()
    while rows and rows[-1]["T"] < b * 1000:
        time.sleep(0.25)
        r = cl.get(URL, params={"symbol": sym, "fromId": rows[-1]["a"] + 1, "limit": 1000})
        if r.status_code == 429:
            time.sleep(10); continue
        r.raise_for_status()
        js = r.json()
        if not js:
            break
        rows += js
    df = pd.DataFrame(rows)
    df = pd.DataFrame({"T": df["T"].astype("int64"), "p": df["p"].astype(float), "q": df["q"].astype(float), "m": df["m"].astype(bool)})
    df = df[(df["T"] >= a * 1000) & (df["T"] < b * 1000)]
    return df


if __name__ == "__main__":
    sym, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    os.makedirs(OUT, exist_ok=True)
    df = fetch(sym, a, b)
    df.to_parquet(f"{OUT}/bnf_{sym}_{a}_{b}.parquet", index=False)
    print("DONE", sym, len(df), flush=True)
