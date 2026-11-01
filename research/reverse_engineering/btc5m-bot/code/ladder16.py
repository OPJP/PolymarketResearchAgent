"""Iteration 16: condition-5 ladder on the TRUE decision record with the MODELLED size class (X152 step 4 / X156 step 2).
Per window, x = sum over the operator's true taker orders of side_k x size_k, with side = true side or dc14 (p_dc14_spot_own, the
pre-registration-5 exam route) and size_k = E[size] from size16 predictions (30 + 70 p) or the public menu (constant) or the class
oracle; r with the window net N (both roles, all wallets) and the PnL r of x * (outcome - 0.5) with the cluster's window PnL.
Usage: python ladder16.py PRED_PARQUET"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr

S = os.environ["RE16_SCRATCH"]
pp = pd.read_parquet(sys.argv[1])
pr = pd.read_parquet(S + "/it14/dcfit14_pred.parquet", columns=["cid", "wallet", "m", "p_dc14_spot_own"])
pp = pp.merge(pr, on=["cid", "wallet", "m"], how="left")
pp["sg"] = np.where(pp.up == 1, 1.0, -1.0); pp["ps"] = 2 * pp.p_dc14_spot_own - 1
f = pd.read_parquet(".cache/re/btc5m-bot/fills.parquet", columns=["wallet", "role", "is_up", "shares", "price", "fee_usd", "start_ts", "up_payout"])
f = f[f.start_ts.isin(pp.start_ts.unique())].copy()
f["sgs"] = np.where(f.is_up, 1.0, -1.0) * f.shares
f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout); f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd
W = f.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum"), up=("up_payout", "first"))
Wl = {w: g.groupby("start_ts").agg(N=("sgs", "sum"), pnl=("pnl", "sum")) for w, g in f.groupby("wallet")}
pcols = [c for c in pp.columns if c.startswith("p|")]
menu = 30 * (1 - pp.large.mean()) + 100 * pp.large.mean()
sizes = {"menu": pd.Series(menu, index=pp.index), "class_oracle": pd.Series(np.where(pp.large == 1, 100.0, 30.0), index=pp.index)}
if "orig" in pp:
    sizes["orig_oracle"] = pp.orig
for c in pcols:
    sizes["E|" + c[2:]] = 30 + 70 * pp[c]
day = pd.to_datetime(pp.start_ts, unit="s").dt.strftime("%m-%d")
out = {}
for side in ("sg", "ps"):
    for nm, sz in sizes.items():
        if sz.isna().all():
            continue
        x = (pp[side] * sz.fillna(menu)).groupby(pp.start_ts).sum()
        J = W.join(x.rename("x"), how="inner").fillna(0); J["o"] = J.up - 0.5
        q = J.x * J.o
        rec = {"rN": round(pearsonr(J.x, J.N)[0], 4), "pnl_P": round(pearsonr(q, J.pnl)[0], 4), "pnl_S": round(spearmanr(q, J.pnl)[0], 4), "n": len(J)}
        # per wallet: the wallet's own orders only (its own size predictions) vs its own window PnL
        for w in ("DS", "GF", "XM"):
            mw = pp.wallet == w
            xw = (pp[side][mw] * sz.fillna(menu)[mw]).groupby(pp.start_ts[mw]).sum()
            Jw = Wl[w].join(xw.rename("x"), how="inner").join(W[["up"]]).fillna(0)
            rec[f"{w}_pnl_P"] = round(pearsonr(Jw.x * (Jw.up - 0.5), Jw.pnl)[0], 4)
            rec[f"{w}_pnl_S"] = round(spearmanr(Jw.x * (Jw.up - 0.5), Jw.pnl)[0], 4)
        out[f"{side}|{nm}"] = rec
for k, v in out.items():
    print(k, v)
tag = os.path.basename(sys.argv[1]).replace("size16_pred_", "").replace(".parquet", "")
json.dump(out, open(f"research/reverse_engineering/btc5m-bot/results/ladder16_{tag}.json", "w"), indent=1)
