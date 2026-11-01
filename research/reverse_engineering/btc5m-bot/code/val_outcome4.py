"""Iteration 4: outcome proxies with the iteration-4 models, plus a new NET-FLOW proxy.
The wallet's per-window PnL is ~ its net position x outcome (corr 0.885, iteration 3), so the rule should predict the
cluster's signed net purchase in every second. NET-FLOW model (new): LightGBM regression, trained on BUILD only, of the
cluster's signed share flow in second s of a window (Up shares - Down shares bought, all roles) on the side-frame PIT
features (Up-cell features + Down-cell D_ features, no own state); zero-flow seconds subsampled 30% (weight 1/0.3).
The rule then buys max(f, 0) Up shares or max(-f, 0) Down shares at the last implied ask in every second.
Proxies (per window, before rebates, taker fee 0.07 p (1-p)): soft (p_o x 30), soft_side (expected volume split by the side
model), netflow, and soft_side with the iteration-3 models on the same rows (pipeline check).
Usage: python -I val_outcome4.py [four]"""
import os, sys, glob, json, time
CODE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, CODE)
FOUR = len(sys.argv) > 1 and sys.argv[1] == "four"
sys.argv = [sys.argv[0]] + (["four"] if FOUR else [])
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
import train5 as t5
import train3 as t3
from alt_cells import BETA
C = t3.C; R = t3.R; FEE = 0.07; SH = 30.0
TAG = t5.TAG
NPARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=300, feature_fraction=0.8,
               bagging_fraction=0.7, bagging_freq=1, verbose=-1, num_threads=3, max_bin=63)
beta = {p: BETA[p] for p, _ in t5.ALTS_USE}


def net_label(c, fills_day):
    """signed cluster share flow per (cid, rel): Up shares - Down shares; aligned to the Up half of the day frame."""
    n = len(c) // 2
    up = c.iloc[:n]
    g = fills_day.assign(r=fills_day.rel.astype(int), sg=np.where(fills_day.is_up, 1.0, -1.0) * fills_day.shares)
    g = g.groupby(["cid", "r"]).sg.sum()
    key = pd.MultiIndex.from_arrays([up.cid.to_numpy(), up.rel.to_numpy().astype(int)])
    return g.reindex(key).fillna(0.0).to_numpy()


def frame_all(c):
    n = len(c) // 2
    iu = np.arange(n)
    s = t5.side_rows(c, iu, n)
    return s


if __name__ == "__main__":
    t0 = time.time(); rng = np.random.default_rng(1)
    spot = pd.read_parquet(f"{C}/binance_1s.parquet")
    spot = spot.rename(columns={spot.columns[0]: "sec", spot.columns[1]: "close"}) if "sec" not in spot else spot
    spot["sec"] = spot.sec.astype(np.int64)
    fills = pd.read_parquet(f"{C}/fills.parquet", columns=["cid", "rel", "is_up", "shares", "price", "fee_usd", "usdc", "up_payout", "start_ts"])
    win = pd.read_parquet(f"{C}/windows.parquet")
    files = sorted(glob.glob(f"{C}/cells/*.parquet"))
    need = set(t3.COLS) | {"age_last", "ask_o", "m_last", "sig", "tau", "r3", "z"}
    model_file = f"{CODE}/model_{TAG}_netflow.txt"
    if not os.path.exists(model_file):
        parts = []
        for fp in files:
            d0 = int(os.path.basename(fp)[:-8])
            if d0 >= t3.V0 or not os.path.exists(f"{C}/fut/{d0}.parquet"):
                continue
            c = pd.read_parquet(fp, columns=sorted(need)); n = len(c) // 2
            lab = net_label(c, fills[(fills.start_ts >= d0) & (fills.start_ts < d0 + 86400)])
            keep = (lab != 0) | (rng.random(n) < 0.3)
            idx = np.where(keep)[0]; idx = np.r_[idx, idx + n]
            sub = c.iloc[idx].copy(); sub.index = idx
            RF = t5.ref_feats(sub, d0, spot)
            for k in RF.columns:
                sub[k] = RF[k].to_numpy()
            del RF
            t5.set_rel(sub, beta)
            s = t5.side_rows(sub, np.where(keep)[0], n)
            s["net"] = lab[keep].astype(np.float32); s["w"] = np.where(lab[keep] != 0, 1.0, 1 / 0.3).astype(np.float32)
            parts.append(s[t5.SIDE + ["net", "w"]])
            del c, sub, s
            print("build day", d0, int(keep.sum()), round(time.time() - t0), flush=True)
        B = pd.concat(parts, ignore_index=True); del parts
        m = lgb.train(NPARAMS, lgb.Dataset(B[t5.SIDE], B.net, weight=B.w), num_boost_round=300)
        m.save_model(model_file); del B
        print("trained netflow", round(time.time() - t0), flush=True)
    mn = lgb.Booster(model_file=model_file)
    mp = lgb.Booster(model_file=f"{CODE}/model_{TAG}_all_y.txt"); ms = lgb.Booster(model_file=f"{CODE}/model_{TAG}_side.txt")
    mp3 = lgb.Booster(model_file=f"{CODE}/model_it3s_all_y.txt"); ms3 = lgb.Booster(model_file=f"{CODE}/model_it3s_side.txt")
    rows = []
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
        p = mp.predict(c[t5.PRIMARY]); p3 = mp3.predict(c[t5.PRIMARY3])
        s = frame_all(c)
        rows.append(pd.DataFrame({"cid": s.cid.to_numpy(), "rel": s.rel.to_numpy(), "pu": p[:n], "pd": p[n:], "pu3": p3[:n], "pd3": p3[n:],
                                  "ps": ms.predict(s[t5.SIDE]), "ps3": ms3.predict(s[t5.SIDE3]), "nf": mn.predict(s[t5.SIDE]),
                                  "ask_u": c.ask_o.to_numpy()[:n], "ask_d": c.ask_o.to_numpy()[n:]}))
        del c, s
        print("val day", d0, round(time.time() - t0), flush=True)
    D = pd.concat(rows, ignore_index=True).merge(win[["cid", "up_payout"]], on="cid")
    okU = np.isfinite(D.ask_u) & (D.ask_u > 0.05) & (D.ask_u < 0.95); okD = np.isfinite(D.ask_d) & (D.ask_d > 0.05) & (D.ask_d < 0.95)
    uU = np.where(okU, D.up_payout - D.ask_u - FEE * D.ask_u * (1 - D.ask_u), 0.0)
    uD = np.where(okD, (1 - D.up_payout) - D.ask_d - FEE * D.ask_d * (1 - D.ask_d), 0.0)
    vol = D.pu + D.pd; vol3 = D.pu3 + D.pd3
    nfu = np.clip(D.nf, 0, None) / SH; nfd = np.clip(-D.nf, 0, None) / SH
    variants = {
        "soft": (D.pu * okU, D.pd * okD),
        "soft_side": (vol * D.ps * okU, vol * (1 - D.ps) * okD),
        "soft_side_it3s_same_pipeline": (vol3 * D.ps3 * okU, vol3 * (1 - D.ps3) * okD),
        "netflow": (nfu * okU, nfd * okD),
        "netflow_x_side": (nfu * (D.ps >= 0.5) * okU, nfd * (D.ps < 0.5) * okD),
    }
    f = fills[fills.cid.isin(set(D.cid))].copy()
    f["pay"] = np.where(f.is_up, f.up_payout, 1 - f.up_payout)
    f["pnl"] = f.shares * (f.pay - f.price) - f.fee_usd; f["net"] = np.where(f.is_up, 1, -1) * f.shares
    ww = f.groupby("cid").agg(pnl=("pnl", "sum"), usd=("usdc", "sum"), net=("net", "sum"))
    res = {"tag": TAG, "windows": int(D.cid.nunique())}
    for nm, (wu, wd) in variants.items():
        g = pd.DataFrame({"cid": D.cid, "pnl": SH * (wu * uU + wd * uD), "usd": SH * (wu * np.nan_to_num(D.ask_u) + wd * np.nan_to_num(D.ask_d)), "net": SH * (wu - wd)}).groupby("cid").sum()
        b = g.join(ww, rsuffix="_w", how="outer").fillna(0.0)
        res[nm] = {"pnl_corr_pearson": round(float(b.pnl.corr(b.pnl_w)), 4), "pnl_corr_spearman": round(float(b.pnl.corr(b.pnl_w, method="spearman")), 4),
                   "net_position_corr": round(float(b.net.corr(b.net_w)), 4), "rule_return": round(float(b.pnl.sum() / b.usd.sum()), 4)}
    res["wallet_return_before_rebates"] = round(float(ww.pnl.sum() / ww.usd.sum()), 4)
    json.dump(res, open(f"{R}/results_outcome_iter4_{TAG}.json", "w"), indent=1)
    D[["cid", "rel", "pu", "pd", "ps", "nf", "ask_u", "ask_d"]].to_parquet(f"{C}/val_outcome_{TAG}.parquet", index=False)
    print(json.dumps(res, indent=0)); print("done", round(time.time() - t0))
