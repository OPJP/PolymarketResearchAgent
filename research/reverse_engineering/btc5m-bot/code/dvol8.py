"""Iteration 8, X7 (options part) with X30: is the bot's wide-vol fair value an IMPLIED-vol fair value? Deribit BTC DVOL
(public get_volatility_index_data, hourly, VALIDATE week 10-16..23; fetched 10-31 18:38 UTC into the scratchpad, 168 rows),
converted to a per-second vol, vs the 5-min realized per-second vol of Binance spot (as revpref8) at every VALIDATE cluster
taker order: the ratio DVOL / realized = the vol multiplier k an implied-vol pricer would show. Also the cluster's value share
under sigma = DVOL (the hourly close known at the order: the previous full hour) for comparison with revpref8's fixed-k grid
(k = 2.0: 52.8%, underdog 85%, favourite 19%; k = 2.5: 52.8%, 91%, 12%). Writes results/dvol8.json. Usage: python dvol8.py DVOL_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0 = 1792108800
dv = pd.DataFrame(json.load(open(sys.argv[1]))["result"]["data"], columns=["t", "o", "h", "l", "c"])
dv["hr"] = (dv.t // 1000).astype(np.int64)
dvc = pd.Series(dv.c.values / 100.0, index=dv.hr.values)  # annualized, close of the hour starting at hr
f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["ts", "wallet", "role", "oh", "price", "start_ts", "is_up"])
f = f[(f.start_ts >= VAL0) & (f.role == "T")].sort_values("ts", kind="stable")
tk = f.groupby(["wallet", "oh"]).agg(ts=("ts", "first"), p=("price", "first"), up=("is_up", "first"), st=("start_ts", "first")).reset_index()
ptb = pd.read_parquet(os.path.join(C, "ptb.parquet")).set_index("start").priceToBeat
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
px = px[~px.index.duplicated()]
full = px.reindex(np.arange(px.index.min(), px.index.max() + 1)).ffill()
t0 = int(full.index[0]); P = full.values; R = np.r_[0.0, np.diff(np.log(P))]
cR = np.cumsum(R); cR2 = np.cumsum(R ** 2); cP = np.cumsum(P)
at = lambda arr, t: arr[np.asarray(t, np.int64) - t0]
s = tk.ts.to_numpy(np.int64); st = tk.st.to_numpy(np.int64)
n = 300
v1 = (at(cR2, s - 2) - at(cR2, s - 2 - n)) / n - ((at(cR, s - 2) - at(cR, s - 2 - n)) / n) ** 2
real = np.sqrt(np.maximum(v1, 1e-14))
prev_hr = (s // 3600) * 3600 - 3600  # the last COMPLETE hour (its close is known at s)
dvol = dvc.reindex(prev_hr).to_numpy(float) / np.sqrt(365.0 * 86400.0)
ratio = dvol / real
K = ptb.reindex(st).to_numpy(float)
om = (at(cP, st - 1) - at(cP, st - 61)) / 60.0
I = at(P, s - 2) * np.exp(np.log(K) - np.log(om))
tau = (st + 300 - (s - 2)).astype(float)
var = np.where(tau > 60, dvol ** 2 * (tau - 40), dvol ** 2 * np.maximum(tau, 1) / 3)
fu = norm.cdf(np.log(I / K) / np.maximum(np.sqrt(var), 1e-12))
fv = np.where(tk.up.to_numpy(bool), fu, 1 - fu)
gap = fv - tk.p.to_numpy(float)
und = tk.p.to_numpy(float) < 0.5
ok = np.isfinite(ratio) & np.isfinite(gap)
res = {"orders": int(ok.sum()), "dvol_annual_median": round(float(np.nanmedian(dvc.values)), 4),
       "realized_per_s_bp_quantiles": [round(float(q) * 1e4, 3) for q in np.nanquantile(real[ok], [0.1, 0.25, 0.5, 0.75, 0.9])],
       "dvol_per_s_bp_median": round(float(np.nanmedian(dvol[ok])) * 1e4, 3),
       "ratio_dvol_over_realized_quantiles": [round(float(q), 3) for q in np.nanquantile(ratio[ok], [0.1, 0.25, 0.5, 0.75, 0.9])],
       "value_share_sigma_dvol": round(float(np.mean(gap[ok] > 0)), 4), "value_share_underdog": round(float(np.mean(gap[ok & und] > 0)), 4),
       "value_share_favourite": round(float(np.mean(gap[ok & ~und] > 0)), 4), "mean_gap_c": round(float(np.mean(gap[ok]) * 100), 3)}
print(json.dumps(res))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "dvol8.json"), "w"), indent=1)
