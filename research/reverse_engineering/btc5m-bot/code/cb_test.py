"""Iteration 4: does Coinbase BTC-USD (Advanced Trade public market-trades endpoint, time-bounded start/end queries, so
point-in-time safe) or Deribit BTC-PERPETUAL (history.deribit.com, time-bounded) explain the side of the bot in seconds
when none of the six archived series moved? Sampled VALIDATE hours; one-sided seconds from val_side_it3s.parquet.
All moves are Up-oriented log moves in bp over windows ending at the PIT horizon (s-1)*1000 ms.
Usage: python -I cb_test.py [n_hours]"""
import os, sys, json, time
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import httpx, numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
H = 1792713600
VAL0 = 1792108800
rng = np.random.default_rng(404)
NH = int(sys.argv[1]) if len(sys.argv) > 1 else 12
# the six Kraken hours first, then random VALIDATE hours (OKX has no data in the last 8 h of VALIDATE)
HOURS = [1792195200 + 15 * 3600, 1792281600 + 10 * 3600, 1792368000 + 20 * 3600, 1792454400 + 14 * 3600,
         1792540800 + 2 * 3600, 1792627200 + 9 * 3600]
cand = [VAL0 + 3600 * k for k in range(0, 7 * 24 - 9) if VAL0 + 3600 * k not in HOURS]
HOURS += [int(x) for x in rng.choice(cand, size=max(0, NH - 6), replace=False)]
os.makedirs(f"{C}/venues/coinbase", exist_ok=True); os.makedirs(f"{C}/venues/deribit", exist_ok=True)
cl = httpx.Client(timeout=30)


def cb_range(a, b, depth=0):
    for k in range(6):
        r = cl.get("https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker",
                   params={"limit": 1000, "start": str(a), "end": str(b)})
        if r.status_code == 200:
            break
        time.sleep(1 + 2 * k)
    tr = r.json().get("trades", [])
    if len(tr) >= 1000 and b - a > 1 and depth < 8:
        m = (a + b) // 2
        return cb_range(a, m, depth + 1) + cb_range(m, b, depth + 1)
    time.sleep(0.15)
    return [(t["time"], float(t["price"]), float(t["size"]), t.get("side"), t.get("bid"), t.get("ask"), t["trade_id"]) for t in tr]


def cb_hour(h0):
    path = f"{C}/venues/coinbase/{h0}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    assert h0 + 3605 < H
    rows = []
    for a in range(h0 - 60, h0 + 3605, 60):
        rows += cb_range(a, min(a + 60, h0 + 3605))
    df = pd.DataFrame(rows, columns=["time", "p", "q", "side", "bid", "ask", "tid"]).drop_duplicates("tid")
    tt = pd.to_datetime(df.time, utc=True, format="ISO8601").dt.tz_convert(None)
    df["T"] = tt.to_numpy().astype("datetime64[ms]").astype(np.int64)  # ms (pandas may store us resolution)
    assert df["T"].min() > 10**12
    assert df["T"].max() < H * 1000
    df = df[["T", "p", "q", "side", "bid", "ask"]].sort_values("T")
    df.to_parquet(path, index=False)
    return df


def dr_hour(h0):
    path = f"{C}/venues/deribit/{h0}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)
    assert h0 + 3605 < H
    rows = []
    for a in range(h0 - 60, h0 + 3605, 60):
        st = a * 1000; en = min(a + 60, h0 + 3605) * 1000
        while True:
            for k in range(6):
                r = cl.get("https://history.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time",
                           params={"instrument_name": "BTC-PERPETUAL", "start_timestamp": st, "end_timestamp": en,
                                   "count": 1000, "sorting": "asc"})
                if r.status_code == 200:
                    break
                time.sleep(1 + 2 * k)
            j = r.json()["result"]; tr = j["trades"]
            rows += [(t["timestamp"], float(t["price"]), float(t["amount"]), t["direction"], t["trade_id"]) for t in tr]
            if not j.get("has_more") or not tr:
                break
            st = tr[-1]["timestamp"]
        time.sleep(0.1)
    df = pd.DataFrame(rows, columns=["T", "p", "q", "side", "tid"]).drop_duplicates("tid")
    df["T"] = df["T"].astype(np.int64)
    assert df["T"].max() < H * 1000 if len(df) else True
    df = df[["T", "p", "q", "side"]].sort_values("T")
    df.to_parquet(path, index=False)
    return df


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    def f(t):
        i = np.searchsorted(T, t, side="left")
        return np.where(i > 0, lp[np.clip(i - 1, 0, None)], np.nan)
    return f


S = pd.read_parquet(f"{C}/val_side_it3s.parquet"); S["s"] = (S.start_ts + S.rel).astype(np.int64)
SER = {"F": "fut", "O": "venues/okx", "B": "venues/bybit", "S": "venues/bnspot", "Y": "venues/bybitspot", "K": "venues/okxspot"}
out = []
for h0 in HOURS:
    g = S[(S.s >= h0 + 10) & (S.s < h0 + 3600)].copy()
    if g.empty:
        continue
    d0 = h0 // 86400 * 86400
    te = (g.s.to_numpy(np.int64) - 1) * 1000
    mv = {}
    for p, sub in SER.items():
        fs = [f"{C}/{sub}/{d}.parquet" for d in (d0 - 86400, d0, d0 + 86400) if os.path.exists(f"{C}/{sub}/{d}.parquet")]
        df = pd.concat([pd.read_parquet(f, columns=["T", "p"]) for f in fs]).sort_values("T")
        f = lpf(df); mv[p] = (f(te) - f(te - 3000)) * 1e4
    st = np.stack([mv[p] for p in SER], axis=1)
    g["mx6"] = np.nanmax(np.abs(st), axis=1)
    g["n6"] = np.isfinite(st).sum(axis=1)
    t0 = time.time(); cb = cb_hour(h0); fc = lpf(cb); t1 = time.time()
    dr = dr_hour(h0); fd = lpf(dr); t2 = time.time()
    for w in (1000, 2000, 3000, 5000):
        g[f"cb{w}"] = (fc(te) - fc(te - w)) * 1e4
        g[f"dr{w}"] = (fd(te) - fd(te - w)) * 1e4
    g["cb_m1"] = (fc(te + 1000) - fc(te)) * 1e4  # [s-1, s): non-PIT diagnostic
    g["dr_m1"] = (fd(te + 1000) - fd(te)) * 1e4
    # Coinbase quote mid at the last trade before the horizon, if bid/ask are populated
    try:
        bb = pd.to_numeric(cb.bid, errors="coerce").to_numpy(); aa = pd.to_numeric(cb.ask, errors="coerce").to_numpy()
        g["cb_has_book"] = float(np.isfinite(bb).mean())
    except Exception:
        g["cb_has_book"] = 0.0
    out.append(g)
    print("hour", h0, "cells", len(g), "coinbase", len(cb), round(t1 - t0), "s deribit", len(dr), round(t2 - t1), "s", flush=True)

A = pd.concat(out)
res = {"hours": HOURS, "n_one_sided": int(len(A)), "coinbase_book_fields_populated": float(A.cb_has_book.mean())}
up = A.truth_up.to_numpy() == 1


def agree(x, mask):
    m = mask & np.isfinite(x) & (x != 0)
    if m.sum() == 0:
        return {"n": 0}
    a = float(((x[m] > 0) == up[m]).mean())
    return {"n": int(m.sum()), "agree": round(a, 4), "z": round((a - 0.5) / np.sqrt(0.25 / m.sum()), 2)}


nomove = (A.mx6.to_numpy() <= 0.1) & (A.n6.to_numpy() >= 5)
allm = np.ones(len(A), bool)
res["share_nomove"] = round(float(nomove.mean()), 4)
for nm in ["cb1000", "cb2000", "cb3000", "cb5000", "cb_m1", "dr1000", "dr2000", "dr3000", "dr5000", "dr_m1"]:
    x = A[nm].to_numpy()
    res[nm] = {"all": agree(x, allm), "nomove": agree(x, nomove),
               "nomove_big05": agree(np.where(np.abs(x) >= 0.5, x, 0), nomove)}
# model residual: in no-move seconds, does Coinbase add to the side model?
ps = A.ps.to_numpy()
for nm in ["cb3000", "dr3000"]:
    x = A[nm].to_numpy(); m = nomove & np.isfinite(x) & (np.abs(x) >= 0.3)
    if m.sum():
        res[nm + "_vs_model_nomove"] = {"n": int(m.sum()), "model_acc": round(float(((ps[m] >= 0.5) == up[m]).mean()), 4),
                                         "feed_acc": round(float(((x[m] > 0) == up[m]).mean()), 4),
                                         "disagree_n": int(((x[m] > 0) != (ps[m] >= 0.5)).sum()),
                                         "feed_right_when_disagree": round(float(((x[m] > 0) == up[m])[(x[m] > 0) != (ps[m] >= 0.5)].mean()), 4) if ((x[m] > 0) != (ps[m] >= 0.5)).sum() else None}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_coinbase_deribit_iter4.json", "w"), indent=1)
