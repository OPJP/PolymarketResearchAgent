"""Iteration 4 (late): does ETH on other venues (OKX ETH-USDT-SWAP, Binance ETHUSDT spot, Bybit ETHUSDT spot) add to the
it4b side model, in particular in seconds where neither the six BTC series nor the Binance ETH perp moved? Two sampled
VALIDATE days (10-19, 10-21); one-sided seconds from val_side_it4b.parquet; Up-oriented 3-s moves over [s-4, s-1)."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
S = pd.read_parquet(f"{C}/val_side_it4b.parquet"); S["s"] = (S.start_ts + S.rel).astype(np.int64)
DAYS = [1792368000, 1792540800]
VEN = ["ethokx", "ethbnspot", "ethbybitspot"]


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    def f(t):
        i = np.searchsorted(T, t, side="left")
        ok = (i > 0) & (t - 15000 >= T[0]) & (t <= T[-1])
        return np.where(ok, lp[np.clip(i - 1, 0, None)], np.nan)
    return f


out = []
for d0 in DAYS:
    g = S[(S.s >= d0 + 10) & (S.s < d0 + 86400)].copy(); te = (g.s.to_numpy(np.int64) - 1) * 1000
    for v in VEN:
        fs = [f"{C}/venues/{v}/{d}.parquet" for d in (d0, d0 + 86400) if os.path.exists(f"{C}/venues/{v}/{d}.parquet")]
        if not fs:
            g[v] = np.nan; continue
        f = lpf(pd.concat([pd.read_parquet(x, columns=["T", "p"]) for x in fs]).drop_duplicates().sort_values("T"))
        g[v] = (f(te) - f(te - 3000)) * 1e4
    out.append(g)
A = pd.concat(out); up = A.truth_up.to_numpy() == 1; ps = A.ps.to_numpy()
flat = (A.mx6.to_numpy() <= 0.1) & (np.abs(A.E_pm3000.fillna(0).to_numpy()) < 0.3)
res = {"n": int(len(A)), "flat_six_and_eth_perp": int(flat.sum()), "model_acc_flat": round(float(((ps[flat] >= 0.5) == up[flat]).mean()), 4)}
for v in VEN:
    x = A[v].to_numpy()
    r = {}
    for nm, m0 in [("all", np.ones(len(A), bool)), ("flat", flat)]:
        m = m0 & np.isfinite(x) & (np.abs(x) >= 0.3)
        if m.sum() == 0:
            r[nm] = {"n": 0}; continue
        dis = (x[m] > 0) != (ps[m] >= 0.5)
        r[nm] = {"n": int(m.sum()), "venue_acc": round(float(((x[m] > 0) == up[m]).mean()), 4), "model_acc": round(float(((ps[m] >= 0.5) == up[m]).mean()), 4),
                 "disagree_n": int(dis.sum()), "venue_right_when_disagree": round(float(((x[m] > 0) == up[m])[dis].mean()), 4) if dis.sum() else None}
    res[v] = r
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_eth_venues_iter4.json", "w"), indent=1)
