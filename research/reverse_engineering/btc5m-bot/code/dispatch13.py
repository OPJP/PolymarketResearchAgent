"""Iteration 13 (X122 step 2 / X120 step 5, on the archive decision clock): is the WALLET that carries an operator taker order
predictable from public state at the decision? dcside13 frame (10-20 / 10-21 operator taker orders, a = m - 180 ms): LightGBM
multiclass P(wallet | rel, |Up ask - 0.5|, Up ask, Polymarket ask changes, |spot microprice tick| over 100 / 250 / 500 ms, hour of
day) fitted on one day, scored on the other; accuracy and log loss against the base rate; and P(XM) calibration by decile.
Also the fan-out structure: legs per event (same window and outcome, match ms within 300 ms) and the first-leg wallet."""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd, lightgbm as lgb
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
X = pd.read_parquet(f"{C}/it13/dcside13_frame{sys.argv[1]}.parquet")
win = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
X["a"] = (X.rel + win.loc[X.cid, "start_ts"].to_numpy()) * 1000.0
X["hour"] = (X.a // 3600000) % 24
for K in (100, 250, 500):
    X[f"abs_tick_{K}"] = X[f"bs_mic_{K}"].abs()
W = ["DS", "GF", "XM"]; X["w"] = X.wallet.map({w: i for i, w in enumerate(W)})
feats = ["rel", "dist", "askU_0", "daskU_500", "daskD_500", "abs_tick_100", "abs_tick_250", "abs_tick_500", "hour"]
P = dict(objective="multiclass", num_class=3, learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, max_bin=63, verbose=-1, num_threads=4, seed=13)
res = {"share": {w: round(float((X.wallet == w).mean()), 4) for w in W}}
for fd in sorted(X.day.unique()):
    fm = (X.day == fd).to_numpy(); sm_ = ~fm
    m = lgb.train(P, lgb.Dataset(X.loc[fm, feats], X.w[fm]), num_boost_round=200)
    p = m.predict(X.loc[sm_, feats])
    y = X.w.to_numpy()[sm_]
    base = np.bincount(X.w[fm], minlength=3) / fm.sum()
    ll = -np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1))); llb = -np.mean(np.log(np.clip(base[y], 1e-9, 1)))
    pxm = p[:, 2]; dec = pd.qcut(pxm, 10, labels=False, duplicates="drop")
    res["fit_" + fd] = {"acc": round(float((p.argmax(1) == y).mean()), 4), "acc_base": round(float((y == base.argmax()).mean()), 4),
                        "logloss": round(float(ll), 4), "logloss_base": round(float(llb), 4),
                        "xm_share_by_pred_decile": [round(float((y[dec == k] == 2).mean()), 4) for k in range(int(dec.max()) + 1)]}
# fan-out events
X = X.sort_values(["cid", "up", "a"]).reset_index(drop=True)
new = (X.cid != X.cid.shift()) | (X.up != X.up.shift()) | (X.a - X.a.shift() > 300)
X["ev"] = new.cumsum()
g = X.groupby("ev")
legs = g.size()
res["legs_per_event"] = {str(k): int(v) for k, v in legs.value_counts().sort_index().head(6).items()}
first = g.wallet.first()
res["first_leg_share"] = {w: round(float((first == w).mean()), 4) for w in W}
multi = legs[legs >= 2].index
res["first_leg_share_multi"] = {w: round(float((first.loc[multi] == w).mean()), 4) for w in W}
res["wallets_in_event_xm_share_by_rank"] = {}
X["rank"] = g.cumcount()
for r in range(3):
    s = X[(X["rank"] == r) & X.ev.isin(multi)]
    res["wallets_in_event_xm_share_by_rank"][str(r)] = {w: round(float((s.wallet == w).mean()), 4) for w in W}
json.dump(res, open(f"{R}/dispatch13{sys.argv[1]}.json", "w"), indent=1)
print(json.dumps(res))
