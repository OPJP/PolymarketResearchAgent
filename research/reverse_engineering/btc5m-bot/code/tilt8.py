"""Iteration 8, X58 (panel-assumptions iter7 P5): is the underdog tilt a RETURN-UNIT threshold (fires when (FV - ask) / ask
>= theta: favourite buys need ~p_fav / p_und times the underdog's move, both follow the tick) or a WIDER-VOL fair value
(underdog buys without or against a tick)? VALIDATE cluster taker orders (fills.parquet, first fill per order hash, price
of that fill, block second s); Binance spot 1-s closes: signed BTC move toward the bought outcome over [s-4, s-2] and
[s-12, s-2] (bp). At matched |p - 0.5| bins, compare underdog and favourite buys: mean signed move, share with a move
toward o (> 0.5 bp), share against (< -0.5 bp), share flat. The digital's delta is symmetric in p, so at a matched |p - 0.5|
a cent threshold predicts equal moves, a return threshold predicts favourite moves ~p_fav / p_und larger, a vol premium
predicts underdog buys on flat or adverse moves. Writes results/tilt8.json."""
import os, json
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0 = 1792108800
f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["ts", "wallet", "role", "oh", "price", "start_ts", "is_up", "shares"])
f = f[(f.start_ts >= VAL0) & (f.role == "T")].sort_values("ts", kind="stable")
o = f.groupby(["wallet", "oh"]).agg(ts=("ts", "first"), p=("price", "first"), up=("is_up", "first"), st=("start_ts", "first"), sh=("shares", "sum")).reset_index()
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
px = pd.Series(bn.close.values.astype(float), index=bn.sec.values.astype(np.int64)).sort_index()
px = px[~px.index.duplicated()]
full = px.reindex(np.arange(px.index.min(), px.index.max() + 1)).ffill()
t0 = int(full.index[0]); P = full.values
s = o.ts.to_numpy(np.int64)
sg = np.where(o.up.to_numpy(bool), 1.0, -1.0)
m4 = (P[s - 2 - t0] / P[s - 4 - t0] - 1) * 1e4 * sg
m12 = (P[s - 2 - t0] / P[s - 12 - t0] - 1) * 1e4 * sg
o["m4"] = m4; o["m12"] = m12
o["d"] = np.abs(o.p - 0.5); o["und"] = o.p < 0.5
o["rel"] = o.ts - o.st
res = {"orders": int(len(o))}
bins = [(0.02, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.48)]
for lo, hi in bins:
    k = (o.d >= lo) & (o.d < hi)
    r = {"n": int(k.sum()), "underdog_share": round(float(o.und[k].mean()), 3)}
    for nm, sel in (("underdog", k & o.und), ("favourite", k & ~o.und)):
        x = o[sel]
        r[nm] = {"n": int(len(x)), "mean_m4_bp": round(float(x.m4.mean()), 3), "toward_m4": round(float((x.m4 > 0.5).mean()), 3), "against_m4": round(float((x.m4 < -0.5).mean()), 3),
                 "flat_m4": round(float((x.m4.abs() <= 0.5).mean()), 3), "mean_m12_bp": round(float(x.m12.mean()), 3), "toward_m12": round(float((x.m12 > 1).mean()), 3),
                 "against_m12": round(float((x.m12 < -1).mean()), 3), "median_abs_m4_given_toward": round(float(x.m4[x.m4 > 0.5].median()), 3) if (x.m4 > 0.5).any() else None,
                 "mean_price": round(float(x.p.mean()), 3)}
    # ratio of the median move given a move toward o, favourite / underdog, vs the return-threshold prediction p_fav / p_und
    a, b = r["favourite"]["median_abs_m4_given_toward"], r["underdog"]["median_abs_m4_given_toward"]
    r["move_ratio_fav_over_und"] = round(a / b, 3) if a and b else None
    r["return_threshold_prediction"] = round(r["favourite"]["mean_price"] / max(r["underdog"]["mean_price"], 1e-9), 3)
    res[f"{lo}-{hi}"] = r
    print(f"{lo}-{hi}", json.dumps(r))
json.dump(res, open(os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results", "tilt8.json"), "w"), indent=1)
