"""Iteration 4: do other alt perps (SOL, XRP, DOGE; Binance USD-M) explain the side beyond the six BTC series and ETH?
Three sampled VALIDATE days (10-17, 10-19, 10-21). One-sided seconds from val_side_moves_iter4.parquet (eth_test.py)."""
import os, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
A = pd.read_parquet(f"{C}/val_side_moves_iter4.parquet"); A["s"] = (A.start_ts + A.rel).astype(np.int64)
DAYS = [1792195200, 1792368000, 1792540800]
ALT = {"SOL": "solfut", "XRP": "xrpfut", "DOGE": "dogefut"}


def lpf(df):
    T = df["T"].to_numpy(np.int64); lp = np.log(df.p.to_numpy())
    def f(t):
        i = np.searchsorted(T, t, side="left")
        return np.where(i > 0, lp[np.clip(i - 1, 0, None)], np.nan)
    return f


out = []
for d0 in DAYS:
    g = A[(A.s >= d0 + 10) & (A.s < d0 + 86400)].copy(); te = (g.s.to_numpy(np.int64) - 1) * 1000
    for nm, sub in ALT.items():
        f = lpf(pd.read_parquet(f"{C}/venues/{sub}/{d0}.parquet", columns=["T", "p"]))
        for w in (2000, 3000):
            g[f"{nm}{w}"] = (f(te) - f(te - w)) * 1e4
    out.append(g)
A = pd.concat(out); up = A.truth_up.to_numpy() == 1


def agree(x, mask):
    m = mask & np.isfinite(x) & (x != 0)
    if m.sum() == 0:
        return {"n": 0}
    a = float(((x[m] > 0) == up[m]).mean())
    return {"n": int(m.sum()), "agree": round(a, 4), "z": round((a - 0.5) / np.sqrt(0.25 / m.sum()), 2)}


nomove = (A.mx6.to_numpy() <= 0.1) & (A.n6.to_numpy() >= 4)
noeth = nomove & (np.abs(A.E3000.fillna(0).to_numpy()) < 0.3)
res = {"n": int(len(A)), "nomove": int(nomove.sum()), "nomove_and_no_eth": int(noeth.sum())}
for nm in ALT:
    for w in (2000, 3000):
        x = A[f"{nm}{w}"].to_numpy()
        res[f"{nm}{w}"] = {"all": agree(x, np.ones(len(A), bool)), "nomove": agree(x, nomove), "nomove_no_eth": agree(x, noeth),
                           "nomove_no_eth_ge2bp": agree(np.where(np.abs(x) >= 2, x, 0), noeth)}
x = A.E3000.to_numpy(); res["ETH3000_nomove_same_days"] = agree(x, nomove)
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_alts_iter4.json", "w"), indent=1)
