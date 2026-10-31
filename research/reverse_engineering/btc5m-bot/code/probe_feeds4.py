"""Iteration 4: reachability probes for new public reference feeds, all with time-bounded queries far before H.
Coinbase Advanced Trade public market trades (start/end), Deribit history API (time-bounded), Binance ETHUSDT futures and
BTCUSD_PERP (COIN-M) aggTrades archive sizes."""
import json, sys
import httpx

H = 1792713600
T0 = 1792195200 + 15 * 3600  # 2026-10-17 15:00 UTC (VALIDATE)
out = {}
c = httpx.Client(timeout=30, follow_redirects=True)
try:
    r = c.get("https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker",
              params={"limit": 1000, "start": str(T0), "end": str(T0 + 60)})
    j = r.json() if r.status_code == 200 else {"status": r.status_code, "text": r.text[:200]}
    tr = j.get("trades", []) if isinstance(j, dict) else []
    ts = sorted(t["time"] for t in tr)
    out["coinbase"] = {"status": r.status_code, "n": len(tr), "first": ts[:1], "last": ts[-1:], "keys": list(tr[0].keys()) if tr else j}
except Exception as e:
    out["coinbase"] = repr(e)
try:
    r = c.get("https://history.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time",
              params={"instrument_name": "BTC-PERPETUAL", "start_timestamp": T0 * 1000, "end_timestamp": (T0 + 60) * 1000,
                      "count": 1000, "sorting": "asc"})
    j = r.json()
    tr = j.get("result", {}).get("trades", [])
    out["deribit"] = {"status": r.status_code, "n": len(tr), "first": tr[0]["timestamp"] if tr else None,
                      "last": tr[-1]["timestamp"] if tr else None, "has_more": j.get("result", {}).get("has_more")}
except Exception as e:
    out["deribit"] = repr(e)
for nm, url in [("eth_um", "https://data.binance.vision/data/futures/um/daily/aggTrades/ETHUSDT/ETHUSDT-aggTrades-2026-10-17.zip"),
                ("btc_cm", "https://data.binance.vision/data/futures/cm/daily/aggTrades/BTCUSD_PERP/BTCUSD_PERP-aggTrades-2026-10-17.zip"),
                ("btc_um_book", "https://data.binance.vision/data/futures/um/daily/bookTicker/BTCUSDT/BTCUSDT-bookTicker-2026-10-17.zip")]:
    try:
        r = c.head(url)
        out[nm] = {"status": r.status_code, "MB": round(int(r.headers.get("content-length", 0)) / 1e6, 1)}
    except Exception as e:
        out[nm] = repr(e)
print(json.dumps(out, indent=1, default=str))
