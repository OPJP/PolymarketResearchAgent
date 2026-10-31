"""Iteration 3: outcome proxies on VALIDATE with the iteration-3 models. Per window: rule PnL vs the cluster's PnL
(before rebates). Proxies: soft (p_o x 30 shares at the last implied ask), soft-side (per second the expected volume
p_up + p_dn split by the side model: Up gets ps, Down 1 - ps), and their net-position correlations.
Usage: python val_outcome3.py fut|ven"""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
import numpy as np, pandas as pd, lightgbm as lgb
import train3 as t3
FEE = 0.07; SH = 30.0
kind = sys.argv[1] if len(sys.argv) > 1 else "fut"
if kind in ("ven", "six"):
    import train4 as t4
    load_day, PRIM, SIDEF = t4.load_day, t4.PRIMARY, t4.SIDE_FEATS
    mp, ms = lgb.Booster(model_file=f"{CODE}/model_{t4.TAG}_all_y.txt"), lgb.Booster(model_file=f"{CODE}/model_{t4.TAG}_side.txt")
else:
    load_day, PRIM, SIDEF = t3.load_day, t3.PRIMARY, t3.SIDE_FEATS
    mp, ms = lgb.Booster(model_file=f"{CODE}/model_it3_spot_tape_fut_y.txt"), lgb.Booster(model_file=f"{CODE}/model_it3_side.txt")
C = t3.C; R = t3.R
win = pd.read_parquet(f"{C}/windows.parquet")
fills = pd.read_parquet(f"{C}/fills.parquet")
rows = []
for fp in sorted(glob.glob(f"{C}/cells/*.parquet")):
    d0 = int(os.path.basename(fp)[:-8])
    if not (t3.V0 <= d0 < t3.V1):
        continue
    c = load_day(fp)
    n = len(c) // 2
    up, dn = c.iloc[:n].reset_index(drop=True), c.iloc[n:].reset_index(drop=True)
    assert (up.cid.to_numpy() == dn.cid.to_numpy()).all() and (up.rel.to_numpy() == dn.rel.to_numpy()).all() and up.is_up.all()
    pu, pd_ = mp.predict(up[PRIM]), mp.predict(dn[PRIM])
    X = up.copy()
    for k in t3.DSIDE:
        X["D_" + k] = dn[k].to_numpy()
    ps = ms.predict(X[SIDEF])
    rows.append(pd.DataFrame({"cid": up.cid.to_numpy(), "rel": up.rel.to_numpy(), "pu": pu, "pd": pd_, "ps": ps,
                              "ask_u": up.ask_o.to_numpy(), "ask_d": dn.ask_o.to_numpy()}))
    print("day", d0, flush=True)
D = pd.concat(rows, ignore_index=True).merge(win[["cid", "up_payout"]], on="cid")
okU = np.isfinite(D.ask_u) & (D.ask_u > 0.05) & (D.ask_u < 0.95); okD = np.isfinite(D.ask_d) & (D.ask_d > 0.05) & (D.ask_d < 0.95)
uU = np.where(okU, D.up_payout - D.ask_u - FEE * D.ask_u * (1 - D.ask_u), 0.0)
uD = np.where(okD, (1 - D.up_payout) - D.ask_d - FEE * D.ask_d * (1 - D.ask_d), 0.0)
vol = D.pu + D.pd
variants = {
    "soft": (D.pu * okU, D.pd * okD),
    "soft_side": (vol * D.ps * okU, vol * (1 - D.ps) * okD),
    "soft_side_sharp": (vol * (D.ps >= 0.5) * okU, vol * (D.ps < 0.5) * okD),
    "soft_side_sq": (vol * D.ps ** 2 / (D.ps ** 2 + (1 - D.ps) ** 2) * okU, vol * (1 - D.ps) ** 2 / (D.ps ** 2 + (1 - D.ps) ** 2) * okD),
}
f = fills[fills.cid.isin(set(D.cid))].copy()
f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd; f["net"] = np.where(f.is_up, 1, -1) * f.shares
ww = f.groupby("cid").agg(pnl=("pnl", "sum"), usd=("usdc", "sum"), net=("net", "sum"))
res = {"kind": kind, "windows": int(D.cid.nunique())}
for nm, (wu, wd) in variants.items():
    g = pd.DataFrame({"cid": D.cid, "pnl": SH * (wu * uU + wd * uD), "usd": SH * (wu * np.nan_to_num(D.ask_u) + wd * np.nan_to_num(D.ask_d)), "net": SH * (wu - wd)}).groupby("cid").sum()
    b = g.join(ww, rsuffix="_w", how="outer").fillna(0.0)
    res[nm] = {"pnl_corr_pearson": round(float(b.pnl.corr(b.pnl_w)), 4), "pnl_corr_spearman": round(float(b.pnl.corr(b.pnl_w, method="spearman")), 4),
               "net_position_corr": round(float(b.net.corr(b.net_w)), 4), "rule_return": round(float(b.pnl.sum() / b.usd.sum()), 4)}
res["wallet_return_before_rebates"] = round(float(ww.pnl.sum() / ww.usd.sum()), 4)
# ceiling diagnostics: how much of the wallet's per-window PnL is its net position x outcome?
wv = ww.join(win.set_index("cid").up_payout)
res["diag_corr_wallet_pnl_vs_own_net_x_outcome"] = round(float(wv.pnl.corr(wv.net * (2 * wv.up_payout - 1))), 4)
json.dump(res, open(f"{R}/results_outcome_iter3_{kind}.json", "w"), indent=1)
print(json.dumps(res, indent=0))
