"""Iteration 6 (X20 = panel-information proposal 3, step 1): time-bounded REST trades at exchange ms for a DEVELOPMENT
interval after T0 only (refuses any minute that tools/sealed.py marks sealed; no daily archives that span sealed blocks):
  bnf  Binance USD-M BTCUSDT / ETHUSDT aggTrades     (fapi, startTime + fromId paging)
  bns  Binance spot BTCUSDT / ETHUSDT aggTrades      (api v3, startTime + fromId paging)
  cb   Coinbase BTC-USD / ETH-USD trades             (Advanced Trade public ticker with start/end, split when full)
  okx  OKX BTC-USDT-SWAP / ETH-USDT-SWAP trades      (history-trades type=2, paged backwards by timestamp)
Writes .cache/re/btc5m-bot/post/rest6_<venue>_<SYM>_<a>_<b>.parquet with T (ms), p, q, s (+1 buyer aggressor, -1 seller).
Usage: python fetch_rest6.py START END [venues...]"""
import os, sys, time
import numpy as np, pandas as pd, httpx
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
import sealed
OUT = _ROOT + "/.cache/re/btc5m-bot/post"
cl = httpx.Client(timeout=30, headers={"User-Agent": "polyrea-research"})


def check(a, b):
    for x in range(int(a), int(b), 30):
        assert not sealed.is_sealed(x, "btc5m-bot"), "sealed time"


def binance(base, sym, a, b):
    rows = []
    r = cl.get(base, params={"symbol": sym, "startTime": int(a * 1000), "endTime": int(a * 1000) + 59_999, "limit": 1000}); r.raise_for_status()
    rows += r.json()
    while rows and rows[-1]["T"] < b * 1000:
        time.sleep(0.2)
        r = cl.get(base, params={"symbol": sym, "fromId": rows[-1]["a"] + 1, "limit": 1000})
        if r.status_code == 429:
            time.sleep(10); continue
        r.raise_for_status()
        js = r.json()
        if not js:
            break
        rows += js
    df = pd.DataFrame(rows)
    return pd.DataFrame({"T": df["T"].astype("int64"), "p": df["p"].astype(float), "q": df["q"].astype(float), "s": np.where(df["m"].astype(bool), -1, 1)})


def cb_range(prod, a, b, depth=0):
    for k in range(6):
        r = cl.get(f"https://api.coinbase.com/api/v3/brokerage/market/products/{prod}/ticker", params={"limit": 1000, "start": str(a), "end": str(b)})
        if r.status_code == 200:
            break
        time.sleep(1 + 2 * k)
    tr = r.json().get("trades", [])
    if len(tr) >= 1000 and b - a > 1 and depth < 8:
        m = (a + b) // 2
        return cb_range(prod, a, m, depth + 1) + cb_range(prod, m, b, depth + 1)
    time.sleep(0.12)
    return [(t["time"], float(t["price"]), float(t["size"]), t.get("side"), t["trade_id"]) for t in tr]


def coinbase(prod, a, b):
    rows = []
    for x in range(int(a), int(b), 60):
        rows += cb_range(prod, x, min(x + 60, int(b)))
    df = pd.DataFrame(rows, columns=["time", "p", "q", "side", "tid"]).drop_duplicates("tid")
    tt = pd.to_datetime(df.time, utc=True, format="ISO8601").dt.tz_convert(None)
    T = tt.to_numpy().astype("datetime64[ms]").astype(np.int64)
    # Coinbase 'side' is the maker side: SELL = buyer was the aggressor
    return pd.DataFrame({"T": T, "p": df.p, "q": df.q, "s": np.where(df.side.str.upper() == "SELL", 1, -1)})


def okx(inst, a, b):
    rows, after = [], str(int(b * 1000))
    while True:
        for k in range(6):
            r = cl.get("https://www.okx.com/api/v5/market/history-trades", params={"instId": inst, "type": "2", "after": after, "limit": 100})
            if r.status_code == 200:
                break
            time.sleep(1 + 2 * k)
        d = r.json().get("data", [])
        if not d:
            break
        rows += d
        last = int(d[-1]["ts"])
        if last < a * 1000:
            break
        after = str(last)
        time.sleep(0.11)
    df = pd.DataFrame(rows).drop_duplicates("tradeId")
    return pd.DataFrame({"T": df.ts.astype("int64"), "p": df.px.astype(float), "q": df.sz.astype(float), "s": np.where(df.side == "buy", 1, -1)})


def main(a, b, venues):
    check(a, b)
    os.makedirs(OUT, exist_ok=True)
    jobs = {"bnf": [(s, lambda s=s: binance("https://fapi.binance.com/fapi/v1/aggTrades", s, a, b)) for s in ("BTCUSDT", "ETHUSDT")],
            "bns": [(s, lambda s=s: binance("https://api.binance.com/api/v3/aggTrades", s, a, b)) for s in ("BTCUSDT", "ETHUSDT")],
            "cb": [(s, lambda s=s: coinbase(s, a, b)) for s in ("BTC-USD", "ETH-USD")],
            "okx": [(s, lambda s=s: okx(s, a, b)) for s in ("BTC-USDT-SWAP", "ETH-USDT-SWAP")]}
    for v in venues:
        for sym, fn in jobs[v]:
            path = f"{OUT}/rest6_{v}_{sym}_{a}_{b}.parquet"
            if os.path.exists(path):
                continue
            t0 = time.time()
            try:
                df = fn()
            except Exception as e:
                print("FAIL", v, sym, repr(e)[:200], flush=True); continue
            df = df[(df["T"] >= a * 1000) & (df["T"] < b * 1000)].sort_values("T")
            df.to_parquet(path, index=False)
            print("DONE", v, sym, len(df), round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    main(a, b, sys.argv[3:] or ["bnf", "bns", "cb", "okx"])
