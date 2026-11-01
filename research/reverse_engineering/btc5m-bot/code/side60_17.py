"""Iteration 17 (X177 step 3): do XM's 60-share resting orders (and DS / GF 30-share maker-first orders) carry the SAME decision side as
the takers? Their arrival is the book posting t_post (post60_17.py), so the taker-equivalent match is m_eq = t_post + 150 ms (arrival =
match - 150) and the frozen dc_exam14 model is scored at m_eq on the live feed with the local clock offset (as oot17b). Reported:
accuracy by class, placebo -/+ 3 s. Not a pre-registered claim (a consistency check of the decoded side on a new order class).
Usage: python side60_17.py"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oot17 as base
import dc_exam14 as dx
xt, xT, qt = base.xt, base.xT, base.qt
lag = (xt - xT).astype(float); sec = xt // 1000
g = pd.Series(lag).groupby(sec).median()
full = pd.Series(np.nan, index=np.arange(sec.min(), sec.max() + 1)); full.loc[g.index] = g.values
loc = full.rolling(60, min_periods=5).median().ffill().bfill()
Tb = qt - loc.reindex(qt // 1000).ffill().bfill().to_numpy() + 131
R = pd.read_parquet(base.S + "/post60_17.parquet"); o = pd.read_parquet(base.S + "/mkx17_orders.parquet")
R["start_ts"] = o.start_ts.to_numpy(); R["cid"] = o.cid.to_numpy()
R = R[R.post_rel.notna()].copy(); R["m"] = ((R.post_rel + R.start_ts) * 1000.0 + 150).astype(np.int64)
R = R[(R.m >= int(Tb[0]) + 3000 + 260)]
res = {}
for nm, gg in (("XM60", R[(R.wallet == "XM") & (R.orig.round() == 60)]), ("DS30", R[(R.wallet == "DS") & (R.orig.round() == 30)]), ("GF30", R[(R.wallet == "GF") & (R.orig.round() == 30)])):
    if not len(gg):
        continue
    m = gg.m.to_numpy(np.int64); st = gg.start_ts.to_numpy(np.int64); up = gg.is_up.to_numpy(bool)
    p = base.mdl.predict(dx.features(m, st, Tb, base.mic, base.mid, xT, base.xp)[base.FN])
    d = {"n": int(len(gg)), "acc": round(float(((p > 0.5) == up).mean()), 4)}
    for k, sh in (("placebo_minus_3s", -3000), ("placebo_plus_3s", 3000)):
        Xp = dx.features(m + sh, st, Tb, base.mic, base.mid, xT, base.xp); Xp["rel"] = Xp.rel + sh / 1000.0
        d[k] = round(float(((base.mdl.predict(Xp[base.FN]) > 0.5) == up).mean()), 4)
    res[nm] = d
json.dump(res, open(base._ROOT + "/research/reverse_engineering/btc5m-bot/results/side60_17.json", "w"), indent=1)
print("RESULT", json.dumps(res))
