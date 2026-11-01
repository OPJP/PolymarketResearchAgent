"""Iteration 8, X42 (panel-mechanics iter6 P4: ladder level chosen / reservation price from pay-up): does the bot pay up above
the touch when its fair value is further above the touch? VALIDATE calldata hours (cluster taker orders with their limit and
the best consumed effective ask, as version8.payup); FV_DVOL(o) at the block second s: exact strike (priceToBeat), Binance
spot close at s - 2 x open basis, sigma = Deribit DVOL of the last complete hour, TWAP variance. P(pay-up) by gap = FV - touch,
and whether pay-up limits stay below the FV (a reservation price). Writes results/pay8.json. Usage: python pay8.py DVOL_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import final_rule as FR


def payup(d):
    """same as version8.payup (copied: version8 runs at import)."""
    d = d.copy()
    d["px"] = np.where(d.oside == 0, d.maker_amt / d.taker_amt, d.taker_amt / d.maker_amt)
    tk = d[(d.role == "T") & d.maker.str.lower().isin(FR.WALLETS)].copy()
    mk = d[d.role == "M"][["tx", "token", "oside", "px"]].merge(tk[["tx", "token"]].rename(columns={"token": "t_token"}), on="tx")
    same = mk.token == mk.t_token
    mk["eff"] = np.where(same & (mk.oside == 1), mk.px, np.where(~same & (mk.oside == 0), 1.0 - mk.px, np.nan))
    tk = tk.join(mk.groupby("tx").eff.min().rename("best"), on="tx")
    tk = tk[tk.best.notna()]
    tk["wallet"] = tk.maker.str.lower().map(FR.WALLETS)
    tk["pay"] = (tk.px - tk.best).round(4) > 0.0001
    tk["size"] = tk.taker_amt.round(0)
    return tk
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0 = 1792108800
dv = pd.DataFrame(json.load(open(sys.argv[1]))["result"]["data"], columns=["t", "o", "h", "l", "c"])
DVC = dict(zip((dv.t // 1000).astype(int), dv.c / 100.0))
cs = pd.read_parquet(os.path.join(C, "calldata_sample.parquet"))
tk = payup(cs)
b1 = pd.read_parquet(os.path.join(C, "b1_orders_sample.parquet"), columns=["salt", "first_ts", "start_ts", "is_up"])
b1["salt"] = b1.salt.astype(str); tk["salt"] = tk.salt.astype(str)
tk = tk.merge(b1.drop_duplicates("salt"), on="salt", how="inner")
tk = tk[tk.first_ts >= VAL0].copy()
ptb = pd.read_parquet(os.path.join(C, "ptb.parquet")).set_index("start").priceToBeat
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
px = px[~px.index.duplicated()]
full = px.reindex(np.arange(px.index.min(), px.index.max() + 1)).ffill()
t0 = int(full.index[0]); P = full.values; cP = np.cumsum(P)
at = lambda arr, t: arr[np.asarray(t, np.int64) - t0]
s = tk.first_ts.to_numpy(np.int64); st = tk.start_ts.to_numpy(np.int64)
K = ptb.reindex(st).to_numpy(float)
om = (at(cP, st - 1) - at(cP, st - 61)) / 60.0
I = at(P, s - 2) * np.exp(np.log(K) - np.log(om))
sig = np.array([DVC.get(int(h), np.nan) for h in (s // 3600) * 3600 - 3600]) / np.sqrt(365.0 * 86400.0)
tau = (st + 300 - (s - 2)).astype(float)
sd = sig * np.sqrt(np.maximum(tau - 40, tau / 3))
fu = norm.cdf(np.log(I / K) / np.maximum(sd, 1e-12))
tk["fv"] = np.where(tk.is_up.astype(bool), fu, 1 - fu)
tk["gap"] = tk.fv - tk.best
ok = np.isfinite(tk.gap)
x = tk[ok]
gb = pd.cut(x.gap, [-1, -0.05, -0.02, 0, 0.02, 0.05, 0.1, 1])
res = {"orders": int(len(x)), "payup_share": round(float(x.pay.mean()), 4),
       "p_payup_by_gap": {str(k): [round(float(x.pay[gb == k].mean()), 4), int((gb == k).sum())] for k in gb.cat.categories},
       "payup_limit_below_fv": round(float((x.px[x.pay] < x.fv[x.pay]).mean()), 4), "nonpayup_touch_below_fv": round(float((x.best[~x.pay] < x.fv[~x.pay]).mean()), 4),
       "median_gap_payup_c": round(float(x.gap[x.pay].median() * 100), 2), "median_gap_nonpayup_c": round(float(x.gap[~x.pay].median() * 100), 2)}
big = x["size"] >= 100
res["by_size"] = {"large": {"n": int(big.sum()), "payup": round(float(x.pay[big].mean()), 4), "median_gap_c": round(float(x.gap[big].median() * 100), 2)},
                  "small": {"n": int((~big).sum()), "payup": round(float(x.pay[~big].mean()), 4), "median_gap_c": round(float(x.gap[~big].median() * 100), 2)}}
print(json.dumps(res))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "pay8.json"), "w"), indent=1)
