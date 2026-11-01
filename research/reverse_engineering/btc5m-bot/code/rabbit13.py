"""Iteration 13 (X113 step 3 follow-up): does the Binance USD-M bookTicker, which the HF capture lacks, close the decision-clock
side gap? 10-20 11:00-12:00 UTC (development, VALIDATE), USD-M BTCUSDT bookTicker from RabbitGo777/polymarket.btc_20261020.v4.parquet
(revision 1e0218e1; collector receive clock ts_local, microseconds), operator taker orders of the dcside13 frame (a = archive
match ms - 180). Reports the univariate agreement of the USD-M microprice move over [a - K, a), the frozen-style two-series vote
(Binance spot archive + USD-M Rabbit; 0.002 bp threshold) over [a - 500, a), and the decision-clock LightGBM (fit on 10-21)
on the same orders, alone and with the USD-M vote taking precedence where it fires. Usage: python rabbit13.py RABBIT_FILE"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
import dcside13 as dc
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
A0, A1 = 1792494000000, 1792497600000
rb = pd.read_parquet(sys.argv[1]).sort_values("ts_local", kind="stable")
T = (rb.ts_local.to_numpy(np.int64) // 1000); mic = ((rb.b * rb.A_ + rb.a * rb.B_) / (rb.B_ + rb.A_)).to_numpy(float)
lagE = float(np.median(rb.ts_local.to_numpy(np.int64) / 1000.0 - rb.E_.to_numpy(np.int64)))
X = pd.read_parquet(f"{C}/it13/dcside13_frame_2021.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
X["a"] = ((X.rel + win.loc[X.cid, "start_ts"].to_numpy()) * 1000).round().astype(np.int64)
pm = ["rel", "askU_0", "askD_0", "daskU_500", "daskD_500", "daskU_3000", "daskD_3000", "dist"]
ven = [c for c in X.columns if any(c.startswith(p) for p in ("bs_", "by_", "bf_", "ok_"))]
fm = (X.day == "2026-10-21").to_numpy()
m = lgb.train(dc.PARAMS, lgb.Dataset(X.loc[fm, pm + ven], X.up[fm]), num_boost_round=dc.ROUNDS)
S = X[(X.day == "2026-10-20") & (X.a >= A0 + 5000) & (X.a < A1)].copy()
S["p"] = m.predict(S[pm + ven])
y = S.up.to_numpy() == 1; a = S.a.to_numpy(np.int64)
def at(tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = mic[np.clip(i, 0, len(mic) - 1)].astype(float); o[i < 0] = np.nan
    return o
res = {"orders": int(len(S)), "usdm_rows": int(len(rb)), "ts_local_minus_E_ms_median": round(lagE, 1)}
for K in (100, 250, 500, 1000):
    r = (at(a) / at(a - K) - 1) * 1e4
    nz = np.isfinite(r) & (np.abs(r) > 1e-9)
    res[f"usdm_{K}"] = [round(float(((r[nz] > 0) == y[nz]).mean()), 4), round(float(nz.mean()), 4)]
    q = S[f"bs_mic_{K}"].to_numpy() if f"bs_mic_{K}" in S else None
    if q is not None:
        nz2 = np.isfinite(q) & (np.abs(q) > 1e-9)
        res[f"spot_{K}_same_orders"] = [round(float(((q[nz2] > 0) == y[nz2]).mean()), 4), round(float(nz2.mean()), 4)]
rb5 = (at(a) / at(a - 500) - 1) * 1e4; rs5 = S.bs_mic_500.to_numpy()
vote = np.nan_to_num(np.sign(rb5) * (np.abs(rb5) > 0.002)) + np.nan_to_num(np.sign(rs5) * (np.abs(rs5) > 0.002))
k = vote != 0
res["vote_two_series_500"] = {"cover": round(float(k.mean()), 4), "agree": round(float(((vote[k] > 0) == y[k]).mean()), 4)}
vs = np.nan_to_num(np.sign(rs5) * (np.abs(rs5) > 0.002)); ks = vs != 0
res["vote_spot_only_500"] = {"cover": round(float(ks.mean()), 4), "agree": round(float(((vs[ks] > 0) == y[ks]).mean()), 4)}
vb = np.nan_to_num(np.sign(rb5) * (np.abs(rb5) > 0.002)); kb = vb != 0
res["vote_usdm_only_500"] = {"cover": round(float(kb.mean()), 4), "agree": round(float(((vb[kb] > 0) == y[kb]).mean()), 4)}
okm = (S.p.to_numpy() > 0.5) == y
res["dc_model_same_orders"] = round(float(okm.mean()), 4)
rb25 = (at(a) / at(a - 250) - 1) * 1e4
comb = np.where(np.isfinite(rb25) & (np.abs(rb25) > 0.002), rb25 > 0, S.p.to_numpy() > 0.5)
res["usdm250_vote_then_model"] = round(float((comb == y).mean()), 4)
json.dump(res, open(f"{R}/rabbit13.json", "w"), indent=1)
print(json.dumps(res))
