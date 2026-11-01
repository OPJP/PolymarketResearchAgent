"""Iteration 15 (X147 = mechanics P4, compact): condition 7's price part. Per-wallet pay-up k = calldata limit - o's best ask at m - 180
(capture L2, server clock; ~ the arrival on the book clock). Fit c_w (the modal k per wallet) on 10-20's calldata hours, freeze, score on
10-21..22: share within one tick of ask + c_w per wallet and per day, against the plain ask (c = 0) and ask + 1 c.
Also an ordinal model of k (LightGBM multiclass on leg rank, |250-ms move|, rel, |p - 0.5|, ask change over m-500..m-180) fit 10-20.
Usage: python -I payup15.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
o = pd.read_parquet(f"{D15}/race15_orders.parquet") if False else pd.read_parquet(f"{D15}/depth15_orders.parquet")
o = o[o.Lcd.notna() & (o.b180 > 0)].copy()
o["k"] = (o.Lcd - o.b180).astype(int)
fr = pd.read_parquet(f"{D14}/dcclock14_frame.parquet", columns=["cid", "wallet", "m", "rank", "rel", "own_bs_mic_250"]).drop_duplicates(["cid", "wallet", "m"])
o = o.merge(fr, on=["cid", "wallet", "m"], how="left")
o["day"] = pd.to_datetime(o.start_ts, unit="s", utc=True).dt.strftime("%m-%d")
fit = o.day == "10-20"; sc = ~fit
rep = {"n_fit": int(fit.sum()), "n_score": int(sc.sum()), "k_dist_fit": {w: o[fit & (o.wallet == w)].k.value_counts(normalize=True).sort_index().round(3).to_dict() for w in ("DS", "GF", "XM")}}
cw = {w: int(o[fit & (o.wallet == w)].k.mode().iloc[0]) for w in ("DS", "GF", "XM")}
rep["c_w_frozen"] = cw
def within(sel, c):
    x = o[sel]
    pred = x.b180 + (x.wallet.map(c) if isinstance(c, dict) else c)
    return round(float((np.abs(x.Lcd - pred) <= 1).mean()), 4)
for w in ("DS", "GF", "XM", "all"):
    s0 = sc & ((o.wallet == w) if w != "all" else True)
    rep[f"score_{w}"] = {"n": int(s0.sum()), "plain_ask": within(s0, 0), "ask_plus_1": within(s0, 1), "ask_plus_cw": within(s0, cw),
                         "by_day_cw": {d: within(s0 & (o.day == d), cw) for d in ("10-21", "10-22")},
                         "by_day_plain": {d: within(s0 & (o.day == d), 0) for d in ("10-21", "10-22")},
                         "exact_cw": round(float((o[s0].Lcd == o[s0].b180 + o[s0].wallet.map(cw)).mean()), 4)}
json.dump(rep, open(OUT, "w"), indent=1)
print(json.dumps(rep, indent=1))
