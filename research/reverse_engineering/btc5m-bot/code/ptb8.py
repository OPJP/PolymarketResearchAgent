"""Iteration 8, X45 (panel-information iter7 P2): time-driven value with the exact strike (Gamma priceToBeat, known at the
window open) as the side of the quiet late decisions, at the block clock (VALIDATE one-sided seconds, val_side_it5book).
Index replica I(s) = Binance spot 1-s close at s - 2 x exp(basis), basis = ln K - ln(mean close over [start - 60, start - 1])
(point-in-time at the open). sigma = std of 1-s log returns over [s - 302, s - 2] times k.
  FV_spot : P(I_end > K), variance sigma^2 tau
  FV_TWAP : settlement = mean of I over [end - 60, end): tau > 60: variance sigma^2 (tau - 40); tau <= 60: the observed partial
            average A over [end - 60, s - 2] with weight w = (60 - tau) / 60, remaining part variance (1 - w)^2 sigma^2 tau / 3
Side rule: buy Up iff FV_up > m_last (the last tape Up price at s - 1). Scored on all / quiet (no six-series move) / late
(rel >= 180) / last-minute seconds against the frozen side model psb; where FV_TWAP and FV_spot disagree, which one the bot
follows. Writes results/ptb8.json."""
import os, json
import numpy as np, pandas as pd
from scipy.stats import norm

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
v = pd.read_parquet(os.path.join(C, "val_side_it5book.parquet"), columns=["cid", "rel", "start_ts", "truth_up", "psb", "m_last"])
w = pd.read_parquet(os.path.join(C, "val_side_book_it5.parquet"), columns=["cid", "rel", "nomove"])
v = v.merge(w.drop_duplicates(["cid", "rel"]), on=["cid", "rel"], how="left")
ptb = pd.read_parquet(os.path.join(C, "ptb.parquet")).set_index("start")
v["K"] = v.start_ts.astype(int).map(ptb.priceToBeat)
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
px = px[~px.index.duplicated()]
full = px.reindex(np.arange(px.index.min(), px.index.max() + 1)).ffill()
t0 = int(full.index[0]); P = full.values; LP = np.log(P); R = np.r_[0.0, np.diff(LP)]
cR = np.cumsum(R); cR2 = np.cumsum(R ** 2); cP = np.cumsum(P)


def at(arr, t):
    return arr[np.asarray(t, np.int64) - t0]


st = v.start_ts.to_numpy(np.int64); rel = v.rel.to_numpy(np.int64); s = st + rel
S = at(P, s - 2)
open_mean = (at(cP, st - 1) - at(cP, st - 61)) / 60.0
basis = np.log(v.K.to_numpy(float)) - np.log(open_mean)
I = S * np.exp(basis)
n = 300
var1 = (at(cR2, s - 2) - at(cR2, s - 2 - n)) / n - ((at(cR, s - 2) - at(cR, s - 2 - n)) / n) ** 2
sig = np.sqrt(np.maximum(var1, 1e-12))
tau = (300 - rel + 2).astype(float)  # seconds from the information time s - 2 to the end
K = v.K.to_numpy(float)
end = st + 300
# observed partial average of I over [end - 60, s - 2] (only when s - 2 >= end - 60)
obs_n = np.clip((s - 2) - (end - 60) + 1, 0, 60)
sumP = np.where(obs_n > 0, at(cP, s - 2) - at(cP, np.maximum(end - 61, s - 2 - obs_n)), 0.0)
A = np.where(obs_n > 0, sumP / np.maximum(obs_n, 1) * np.exp(basis), np.nan)
res = {"n": int(len(v)), "K_missing": int(np.isnan(K).sum())}
y = v.truth_up.to_numpy(int); psb = v.psb.to_numpy(float); ml = v.m_last.to_numpy(float)
quiet = v.nomove.fillna(False).to_numpy(bool)
masks = {"all": np.ones(len(v), bool), "quiet": quiet, "late_ge180": rel >= 180, "late_quiet": (rel >= 180) & quiet, "last_minute": rel >= 240,
         "last_minute_quiet": (rel >= 240) & quiet}
for k in (0.8, 1.0, 1.3, 1.6, 2.0):
    sd = k * sig
    fv_spot = norm.cdf(np.log(I / K) / np.maximum(sd * np.sqrt(tau), 1e-9))
    w_obs = obs_n / 60.0
    mean_tw = np.where(obs_n > 0, w_obs * A + (1 - w_obs) * I, I)
    var_tw = np.where(tau > 60, sd ** 2 * (tau - 40), (1 - w_obs) ** 2 * sd ** 2 * np.maximum(tau, 1) / 3)
    fv_tw = norm.cdf(np.log(mean_tw / K) / np.maximum(np.sqrt(var_tw), 1e-9))
    r = {}
    for nm, mk in masks.items():
        mk = mk & np.isfinite(fv_tw) & np.isfinite(ml)
        r[nm] = {"n": int(mk.sum()), "psb": round(float(((psb[mk] > 0.5) == y[mk]).mean()), 4),
                 "value_twap": round(float(((fv_tw[mk] > ml[mk]) == y[mk]).mean()), 4),
                 "value_spot": round(float(((fv_spot[mk] > ml[mk]) == y[mk]).mean()), 4),
                 "mean_abs_fv_minus_mlast_twap": round(float(np.mean(np.abs(fv_tw[mk] - ml[mk]))), 4)}
        dis = mk & ((fv_tw > ml) != (fv_spot > ml))
        r[nm]["disagree_share"] = round(float(dis.sum() / max(mk.sum(), 1)), 4)
        r[nm]["follows_twap_when_disagree"] = round(float(((fv_tw[dis] > ml[dis]) == y[dis]).mean()), 4) if dis.any() else None
        # add the value gap to the side model (no fitting: equal-weight logit sum, gap in probability units scaled by 10)
        lg = np.log(np.clip(psb, 1e-4, 1 - 1e-4) / (1 - np.clip(psb, 1e-4, 1 - 1e-4))) + 10 * (fv_tw - ml)
        r[nm]["psb_plus_gap"] = round(float(((lg[mk] > 0) == y[mk]).mean()), 4)
    res[f"k{k}"] = r
    print(k, json.dumps({nm: r[nm] for nm in ("all", "quiet", "late_quiet", "last_minute_quiet")}))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "ptb8.json"), "w"), indent=1)
