"""Iteration 15 (X144 / X143 / X145 step 1, the 'if false' branch): how much of the operator's realized taker-step fill is predictable
from what is public at the bot's view (m - 180 ms server clock) plus the decision record? LightGBM regression, fit 10-20, scored once on
10-21..22 (operator taker orders with capture match ms; true decisions = oracle on timing / side / wallet).
Features: the capture's ask book of o at m - 180 (depth at best + 0..3 c, best ask, depth at <= L_pub), the spot microprice moves at
the order's own decision anchor (|100 / 250 / 500-ms| and signed toward o, dcclock14_frame), rel, hour, window index mod 4, leg rank,
wallet (one-hot; it carries the menu mix), |best - 0.5|.
Reported: r(pred, filled) on the score days; oracle ladder r(N) / PnL r with dc14 side x predicted fill against the public menu
(0.395) and the true fill (0.747); feature gains. Usage: python -I fillpred15.py IT15_DIR IT14_DIR OUT.json"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
from scipy.stats import pearsonr, spearmanr

D15, D14, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
C = ".cache/re/btc5m-bot"
DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]
o = pd.read_parquet(f"{D15}/depth15_orders.parquet")
vec = {}
for day in DAYS:
    od = pd.read_parquet(f"{D15}/l2ord_{day}.parquet", columns=["cid", "wallet", "m"]); ov = np.load(f"{D15}/l2ord_{day}.npy")[:, 2]
    for i, k in enumerate(zip(od.cid, od.wallet, od.m)):
        vec[k] = i
    vec[day] = (od, ov)
rows = []
for day in DAYS:
    od, ov = vec[day]
    key = pd.MultiIndex.from_frame(od[["cid", "wallet", "m"]])
    sub = o.set_index(["cid", "wallet", "m"]).reindex(key)
    b = sub.b180.fillna(0).astype(int).to_numpy()
    cs = np.cumsum(ov, 1)
    idx = np.arange(len(b))
    f = {}
    for kk in range(4):
        hi = np.clip(b + kk, 0, 100); lo = np.clip(b - 1, 0, 100)
        f[f"dep{kk}"] = cs[idx, hi] - cs[idx, lo]
    f["lvl0"] = ov[idx, np.clip(b, 0, 100)]
    x = pd.DataFrame(f); x["cid"] = od.cid.to_numpy(); x["wallet"] = od.wallet.to_numpy(); x["m"] = od.m.to_numpy()
    rows.append(x)
X = pd.concat(rows, ignore_index=True)
o = o.merge(X, on=["cid", "wallet", "m"], how="left")
fr = pd.read_parquet(f"{D14}/dcclock14_frame.parquet", columns=["cid", "wallet", "m", "rank", "rel", "own_bs_mic_100", "own_bs_mic_250", "own_bs_mic_500", "dec_pm_dist"]).drop_duplicates(["cid", "wallet", "m"])
o = o.merge(fr, on=["cid", "wallet", "m"], how="left")
sg = np.where(o.is_up, 1.0, -1.0)
for K in (100, 250, 500):
    o[f"mv{K}"] = o[f"own_bs_mic_{K}"] * sg; o[f"amv{K}"] = o[f"own_bs_mic_{K}"].abs()
o["hour"] = (o.m // 1000 % 86400) // 3600; o["k4"] = (o.start_ts // 300) % 4
o["bdist"] = (o.b180 / 100 - 0.5).abs()
for w in ("DS", "GF", "XM"):
    o[f"w_{w}"] = (o.wallet == w).astype(int)
FE = ["dep0", "dep1", "dep2", "dep3", "lvl0", "D_m180", "b180", "bdist", "mv100", "mv250", "mv500", "amv100", "amv250", "amv500", "rel", "hour", "k4", "rank", "w_DS", "w_GF", "w_XM"]
FE_NOBOOK = [c for c in FE if c not in ("dep0", "dep1", "dep2", "dep3", "lvl0", "D_m180")]
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, max_bin=63, verbose=-1, num_threads=4, seed=15)
fit = (o.start_ts < 1792540800).to_numpy(); sc = ~fit
rep = {"n_fit": int(fit.sum()), "n_score": int(sc.sum())}
W = None
f2 = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "role", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f2 = f2[f2.start_ts.isin(o.start_ts[sc].unique())].copy()
f2["sgs"] = np.where(f2.is_up, 1.0, -1.0) * f2.shares; f2["pay"] = np.where(f2.is_up, f2.up_payout, 1 - f2.up_payout); f2["pnl"] = f2.shares * (f2.pay - f2.price) - f2.fee_usd
Wn = f2.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
S = o[sc].copy()
for nm, cols in (("book_plus_state", FE), ("state_only", FE_NOBOOK)):
    m = lgb.train(PARAMS, lgb.Dataset(o.loc[fit, cols], o.shares[fit]), 400)
    p = m.predict(S[cols]); S[f"pred_{nm}"] = p
    imp = pd.Series(m.feature_importance("gain"), index=cols)
    rep[nm] = {"r_pred_filled": round(float(pearsonr(p, S.shares)[0]), 4), "spearman": round(float(spearmanr(p, S.shares)[0]), 4),
               "r_by_wallet": {w: round(float(pearsonr(p[S.wallet == w], S.shares[S.wallet == w])[0]), 4) for w in ("DS", "GF", "XM")},
               "top_gain": (imp / imp.sum()).sort_values(ascending=False).head(8).round(3).to_dict()}
for nm, col in (("true_fill", "shares"), ("public_menu", "Emenu"), ("pred_book_plus_state", "pred_book_plus_state"), ("pred_state_only", "pred_state_only")):
    x = (S.ps * S[col]).groupby(S.start_ts).sum()
    J = Wn.join(x.rename("x"), how="inner").fillna(0); J["o"] = J.up - 0.5
    rep[f"ladder_{nm}"] = {"rN": round(float(pearsonr(J.x, J.N)[0]), 4), "pnlP": round(float(pearsonr(J.x * J.o, J.pnl)[0]), 4), "pnlS": round(float(spearmanr(J.x * J.o, J.pnl)[0]), 4), "windows": int(len(J))}
json.dump(rep, open(OUT, "w"), indent=1)
print(json.dumps(rep, indent=1))
