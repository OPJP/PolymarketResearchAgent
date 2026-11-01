"""Iteration 4 (late): VOLUME model for the outcome proxy. The net-position diagnostic (net_diag4.py) showed that per-second
volume errors limit the per-window net-position correlation as much as side errors (oracle volume x model side 0.555).
LightGBM regression, trained on BUILD only, of the cluster's shares bought in a cell (window, outcome, second; all roles)
on the presence features (PRIMARY, no own state); zero cells subsampled 30% (weight 1/0.3). Proxy "shares_side": per second
the predicted shares (Up + Down) split by the side model. Reads val_outcome_it4b.parquet (ps, nf, asks) from val_outcome4.py.
Usage: python -I val_outcome5.py four"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
sys.argv = [sys.argv[0], "four"]
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train5 as t5
import train3 as t3
from alt_cells import BETA
C = t3.C; R = t3.R; FEE = 0.07; SH = 30.0; TAG = t5.TAG
VPARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8,
               bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
beta = {p: BETA[p] for p, _ in t5.ALTS_USE}


def shares_label(c, fd):
    g = fd.assign(r=fd.rel.astype(int)).groupby(["cid", "is_up", "r"]).shares.sum()
    key = pd.MultiIndex.from_arrays([c.cid.to_numpy(), c.is_up.to_numpy(), c.rel.to_numpy().astype(int)])
    return g.reindex(key).fillna(0.0).to_numpy()


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(2)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fills = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "rel", "is_up", "shares", "price", "fee_usd", "usdc", "up_payout", "start_ts"])
    win = pd.read_parquet(f"{C}/windows.parquet")
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    need = set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"}
    mf = f"{CODE}/model_{TAG}_shares.txt"
    if not os.path.exists(mf):
        parts = []
        for fp in files:
            d0 = int(os.path.basename(fp)[:-8])
            if d0 >= t3.V0 or not os.path.exists(f"{C}/fut/{d0}.parquet"):
                continue
            c = pd.read_parquet(fp, columns=sorted(need))
            lab = shares_label(c, fills[(fills.start_ts >= d0) & (fills.start_ts < d0 + 86400)])
            keep = (lab > 0) | (rng.random(len(c)) < 0.3)
            sub = c[keep].copy()
            RF = t5.ref_feats(sub, d0, spot)
            for k in RF.columns:
                sub[k] = RF[k].to_numpy()
            del RF
            t5.set_rel(sub, beta)
            sub["sh"] = lab[keep].astype(np.float32); sub["w"] = np.where(lab[keep] > 0, 1.0, 1 / 0.3).astype(np.float32)
            parts.append(sub[t5.PRIMARY + ["sh", "w"]]); del c, sub
            print("build day", d0, round(time.time() - t0), flush=True)
        B = pd.concat(parts, ignore_index=True); del parts
        m = lgb.train(VPARAMS, lgb.Dataset(B[t5.PRIMARY], B.sh, weight=B.w), num_boost_round=300); m.save_model(mf); del B
        print("trained shares", round(time.time() - t0), flush=True)
    mv = lgb.Booster(model_file=mf)
    O = pd.read_parquet(f"{C}/val_outcome_{TAG}.parquet")
    shu, shd = [], []
    for fp in files:
        d0 = int(os.path.basename(fp)[:-8])
        if not (t3.V0 <= d0 < t3.V1):
            continue
        c = pd.read_parquet(fp, columns=sorted(need)); n = len(c) // 2
        RF = t5.ref_feats(c, d0, spot)
        for k in RF.columns:
            c[k] = RF[k].to_numpy()
        del RF
        t5.set_rel(c, beta)
        v = np.clip(mv.predict(c[t5.PRIMARY]), 0, None)
        shu.append(pd.DataFrame({"cid": c.cid.to_numpy()[:n], "rel": c.rel.to_numpy()[:n], "shu": v[:n], "shd": v[n:]})); del c
        print("val day", d0, round(time.time() - t0), flush=True)
    O = O.merge(pd.concat(shu, ignore_index=True), on=["cid", "rel"], how="left")
    D = O.merge(win[["cid", "up_payout"]], on="cid")
    okU = np.isfinite(D.ask_u) & (D.ask_u > 0.05) & (D.ask_u < 0.95); okD = np.isfinite(D.ask_d) & (D.ask_d > 0.05) & (D.ask_d < 0.95)
    uU = np.where(okU, D.up_payout - D.ask_u - FEE * D.ask_u * (1 - D.ask_u), 0.0)
    uD = np.where(okD, (1 - D.up_payout) - D.ask_d - FEE * D.ask_d * (1 - D.ask_d), 0.0)
    vs = D.shu + D.shd
    variants = {"shares_side": (vs * D.ps * okU / SH, vs * (1 - D.ps) * okD / SH),
                "shares_per_outcome": (D.shu * okU / SH, D.shd * okD / SH),
                "netflow": (np.clip(D.nf, 0, None) / SH * okU, np.clip(-D.nf, 0, None) / SH * okD),
                "mean_netflow_shares_side": (0.5 * (np.clip(D.nf, 0, None) + vs * D.ps) / SH * okU, 0.5 * (np.clip(-D.nf, 0, None) + vs * (1 - D.ps)) / SH * okD)}
    f = fills[fills.cid.isin(set(D.cid))].copy()
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd; f["net"] = np.where(f.is_up, 1, -1) * f.shares
    ww = f.groupby("cid").agg(pnl=("pnl", "sum"), usd=("usdc", "sum"), net=("net", "sum"))
    res = {"tag": TAG}
    for nm, (wu, wd) in variants.items():
        g = pd.DataFrame({"cid": D.cid, "pnl": SH * (wu * uU + wd * uD), "usd": SH * (wu * np.nan_to_num(D.ask_u) + wd * np.nan_to_num(D.ask_d)), "net": SH * (wu - wd)}).groupby("cid").sum()
        b = g.join(ww, rsuffix="_w", how="outer").fillna(0.0)
        res[nm] = {"pnl_corr_pearson": round(float(b.pnl.corr(b.pnl_w)), 4), "pnl_corr_spearman": round(float(b.pnl.corr(b.pnl_w, method="spearman")), 4),
                   "net_position_corr": round(float(b.net.corr(b.net_w)), 4), "rule_return": round(float(b.pnl.sum() / b.usd.sum()), 4)}
    tot = pd.DataFrame({"cid": D.cid, "v": vs}).groupby("cid").v.sum().reindex(ww.index).fillna(0)
    res["window_total_shares_corr"] = round(float(np.corrcoef(tot, (f.groupby("cid").shares.sum()).reindex(ww.index).fillna(0))[0, 1]), 4)
    json.dump(res, open(f"{R}/results_outcome_iter4_shares.json", "w"), indent=1)
    print(json.dumps(res, indent=0)); print("done", round(time.time() - t0))
