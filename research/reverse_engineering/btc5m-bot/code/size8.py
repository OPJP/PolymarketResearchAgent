"""Iteration 8, X49 (panel-mechanics iter7 P1): is the large size set by the operator's own book?
Orders: b1_orders_sample.parquet (calldata sample, signed sizes; BUILD hours 10-09/11/13/15, VALIDATE hours 10-16..22).
Decision second s = block second of the order's first fill. Label large = size above the hour's smallest menu size.
State at s (fills.parquet, all three wallets, block second <= s - 1): operator net on the order's outcome o
(shares o - shares o'), the wallet's own net, the siblings' net; market-only analog: BTC log return from the window open
to s - 2 (Binance 1-s close), signed toward o, the order's limit (price level of o), |p - 0.5|, rel.
Per wallet: logistic on BUILD hours -> within-wallet AUC on VALIDATE hours, for (i) market controls, (ii) + market analog,
(iii) + operator net, (iv) + siblings' net only (no own state of the wallet), and univariate AUCs; P(large) by net bin.
Also the economics of large vs small orders on VALIDATE (fills.parquet: PnL per share after fees by filled size).
Writes results/size8.json."""
import json, os
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
OUT = os.path.join(ROOT, "research", "reverse_engineering", "btc5m-bot", "results")
VAL0 = 1792108800

b = pd.read_parquet(os.path.join(C, "b1_orders_sample.parquet"))
b = b[np.isfinite(b.first_ts) & np.isfinite(b.start_ts)].copy()
b["hr"] = (b.first_ts // 3600).astype(int)
mins = b.groupby("hr")["size"].agg(lambda s: s.value_counts().index[s.value_counts().values >= 0.03 * len(s)].min())
b["large"] = (b["size"] > b.hr.map(mins) + 1e-9).astype(int)
b["s"] = (b.first_ts - b.start_ts).astype(int)
b["up"] = b.is_up.astype(bool)

f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["ts", "wallet", "shares", "start_ts", "is_up", "price", "role", "oh", "fee_usd", "up_payout", "cid"])
f["s"] = (f.ts - f.start_ts).astype(int)
f["sgn"] = np.where(f.is_up, 1.0, -1.0)
f["su"] = f.shares * f.sgn  # signed toward Up
starts = set(b.start_ts.astype(int))
ff = f[f.start_ts.astype(int).isin(starts)]
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}
b["W"] = b.wal.map(lambda x: WAL.get(str(x).lower(), x))

# cumulative signed-Up shares per (start, wallet, s)
agg = ff.groupby(["start_ts", "wallet", "s"]).su.sum().reset_index()
net_all, net_own = [], []
grp = {k: g.sort_values("s") for k, g in agg.groupby("start_ts")}
for r in b.itertuples():
    g = grp.get(r.start_ts)
    if g is None:
        net_all.append(0.0); net_own.append(0.0); continue
    m = g.s.values <= r.s - 1
    tot = g.su.values[m].sum()
    own = g.su.values[m & (g.wallet.values == r.W)].sum()
    sg = 1.0 if r.up else -1.0
    net_all.append(tot * sg); net_own.append(own * sg)
b["net_o"] = net_all; b["net_own_o"] = net_own; b["net_sib_o"] = b.net_o - b.net_own_o

# market analog: BTC return since the window open, signed toward o
bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
tcol = [c for c in bn.columns if c in ("sec", "ts", "t", "open_time", "time")][0]
ccol = [c for c in bn.columns if c in ("close", "c", "px")][0]
px = pd.Series(bn[ccol].values.astype(float), index=(bn[tcol].values // (1000 if bn[tcol].max() > 1e11 else 1)).astype(np.int64))
def pxat(t):
    return px.reindex(np.asarray(t, dtype=np.int64)).values
r0 = pxat(b.start_ts.values - 1); r1 = pxat(b.start_ts.values + b.s.values - 2)
b["mret_o"] = np.log(r1 / r0) * 1e4 * np.where(b.up, 1, -1)
b["lim"] = b["limit"].astype(float)
b["fav"] = (b.lim > 0.5).astype(float)
b["absp"] = np.abs(b.lim - 0.5)
b["rel"] = b.s / 300.0
b = b[np.isfinite(b.mret_o)]

def X(d, which):
    cols = [d.rel, d.absp, d.fav, d.lim]
    if "mkt" in which:
        cols += [np.tanh(d.mret_o / 10), np.tanh(d.mret_o / 3)]
    if "net" in which:
        cols += [np.tanh(d.net_o / 100), np.tanh(d.net_o / 300), (d.net_o < -200).astype(float)]
    if "sib" in which:
        cols += [np.tanh(d.net_sib_o / 100), np.tanh(d.net_sib_o / 300), (d.net_sib_o < -200).astype(float)]
    return np.column_stack(cols)

res = {"n": int(len(b)), "large_share": b.groupby("W").large.mean().round(3).to_dict()}
for W in ["DS", "GF", "XM"]:
    d = b[b.W == W]
    tr, te = d[d.first_ts < VAL0], d[d.first_ts >= VAL0]
    r = {"n_build": int(len(tr)), "n_val": int(len(te)), "large_val": round(float(te.large.mean()), 3)}
    for nm in ["ctrl", "ctrl+mkt", "ctrl+net", "ctrl+mkt+net", "ctrl+mkt+sib"]:
        lr = LogisticRegression(C=1.0, max_iter=1000).fit(X(tr, nm), tr.large)
        p = lr.predict_proba(X(te, nm))[:, 1]
        h = te.first_ts.values < np.median(te.first_ts.values)
        r[nm] = [round(roc_auc_score(te.large, p), 3), round(roc_auc_score(te.large[h], p[h]), 3), round(roc_auc_score(te.large[~h], p[~h]), 3)]
    for u in ["net_o", "net_sib_o", "net_own_o", "mret_o"]:
        r["uni_val_" + u] = round(roc_auc_score(te.large, te[u]), 3)
    res[W] = r
    print(W, json.dumps(r))
# P(large) by operator-net bin, VALIDATE hours, per wallet
bins = [-1e9, -200, -60, -1e-9, 1e-9, 60, 200, 1e9]
lab = ["<-200", "-200..-60", "-60..0", "0", "0..60", "60..200", ">200"]
v = b[b.first_ts >= VAL0].copy(); v["nb"] = pd.cut(v.net_o, bins, labels=lab)
res["p_large_by_net_val"] = {W: v[v.W == W].groupby("nb", observed=False).large.agg(["mean", "size"]).round(3).to_dict(orient="index") for W in ["DS", "GF", "XM"]}
# market analog at fixed net: P(large) by mret bin within net>=0 and net<-60
v["mb"] = pd.cut(v.mret_o, [-1e9, -5, -1, 1, 5, 1e9], labels=["<-5", "-5..-1", "-1..1", "1..5", ">5"])
res["p_large_by_mret_given_net"] = {k: v[m].groupby("mb", observed=False).large.agg(["mean", "size"]).round(3).to_dict(orient="index")
                                    for k, m in [("net>=0", v.net_o >= 0), ("net<-60", v.net_o < -60)]}
print(json.dumps(res["p_large_by_net_val"]))
print(json.dumps(res["p_large_by_mret_given_net"]))

# economics: VALIDATE orders by filled size (fills.parquet), PnL per share after fees
fv = f[(f.start_ts >= VAL0)].copy()
fv["pnl"] = fv.shares * (np.where(fv.is_up, fv.up_payout, 1 - fv.up_payout) - fv.price) - fv.fee_usd
o = fv.groupby(["wallet", "oh"]).agg(sh=("shares", "sum"), pnl=("pnl", "sum"), roles=("role", lambda x: "".join(sorted(set(x))))).reset_index()
o["big"] = o.sh >= 90
res["econ_val"] = {W: {"big_c_per_share": round(float(100 * o[(o.wallet == W) & o.big].pnl.sum() / o[(o.wallet == W) & o.big].sh.sum()), 3),
                       "small_c_per_share": round(float(100 * o[(o.wallet == W) & ~o.big].pnl.sum() / o[(o.wallet == W) & ~o.big].sh.sum()), 3),
                       "big_share_of_shares": round(float(o[(o.wallet == W) & o.big].sh.sum() / o[o.wallet == W].sh.sum()), 3)} for W in ["DS", "GF", "XM"]}
print(json.dumps(res["econ_val"]))
json.dump(res, open(os.path.join(OUT, "size8.json"), "w"), indent=1, default=str)
