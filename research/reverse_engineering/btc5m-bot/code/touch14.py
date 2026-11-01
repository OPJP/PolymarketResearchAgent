"""Iteration 14, X114 / X119 (compact): does the Polymarket TOUCH state just before the decision (maker requotes, the age of o's best
ask) add to the knee-clock take hazard? Only 10-20 / 10-21 carry the capture's touch (pm_touch_*), so: fit on the 10-20 scored bins,
score on 10-21 and the reverse. Units: hazard14_scored.parquet bins (operator first-leg positives + 1% negatives, weight 100).
Touch features at e + 50 ms server time (the bot's Polymarket view): o's best ask and bid, the age of the current best ask, the
number of best-ask changes over 250 / 1000 ms, the ask change over 250 / 1000 ms, and the other outcome's best ask. Models: logistic
on logit(P^ full) alone (recalibration) vs LightGBM on logit(P^ full) + touch features. Usage: python touch14.py FRAME_DIR HF_DIR"""
import os, sys, json
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def main():
    D, A = sys.argv[1], sys.argv[2]
    S = pd.read_parquet(f"{D}/hazard14_scored.parquet")
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"]).set_index("cid")
    S["day"] = pd.to_datetime(win.loc[S.cid, "start_ts"].to_numpy(), unit="s", utc=True).strftime("%Y-%m-%d")
    S = S[S.day.isin(["2026-10-20", "2026-10-21"])].reset_index(drop=True)
    tc = pd.concat([pd.read_parquet(f"{A}/pm_touch_{d}.parquet") for d in ("2026-10-20", "2026-10-21")])
    tc["tokenId"] = tc.tokenId.astype(str)
    TK = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float), g.bestBid.to_numpy(float)) for k, g in tc.sort_values("exchangeTimestampMs", kind="stable").groupby("tokenId")}
    n = len(S); feats = {k: np.full(n, np.nan, np.float32) for k in ("t_ask", "t_bid", "t_age", "t_nch250", "t_nch1000", "t_d250", "t_d1000", "t_ask_x")}
    for (cc, up), ii in S.groupby(["cid", "up"]).indices.items():
        to, tx = (str(win.at[cc, "up_token"]), str(win.at[cc, "down_token"])) if up == 1 else (str(win.at[cc, "down_token"]), str(win.at[cc, "up_token"]))
        cut = S.e.to_numpy(np.int64)[ii] + 50
        if to in TK:
            T_, a_, b_ = TK[to]
            ch = np.concatenate([[True], np.diff(a_) != 0]); Tc = T_[ch]
            a0 = at(T_, a_, cut); feats["t_ask"][ii] = a0; feats["t_bid"][ii] = at(T_, b_, cut)
            j = np.searchsorted(Tc, cut, "left"); feats["t_age"][ii] = np.where(j > 0, cut - Tc[np.clip(j - 1, 0, len(Tc) - 1)], np.nan)
            for K in (250, 1000):
                feats[f"t_nch{K}"][ii] = np.searchsorted(Tc, cut, "left") - np.searchsorted(Tc, cut - K, "left")
                feats[f"t_d{K}"][ii] = a0 - at(T_, a_, cut - K)
        if tx in TK:
            T_, a_, b_ = TK[tx]; feats["t_ask_x"][ii] = at(T_, a_, cut)
    for k, v in feats.items():
        S[k] = v
    S["lf"] = np.log(np.clip(S.p_full, 1e-6, 1 - 1e-6) / (1 - np.clip(S.p_full, 1e-6, 1 - 1e-6)))
    cols = ["lf"] + list(feats)
    P = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, max_bin=63, verbose=-1, num_threads=4, seed=14)
    res = {"bins": int(len(S)), "touch_coverage": round(float(np.isfinite(S.t_ask).mean()), 4)}
    for a, b in (("2026-10-20", "2026-10-21"), ("2026-10-21", "2026-10-20")):
        fa, fb = (S.day == a).to_numpy(), (S.day == b).to_numpy()
        m0 = lgb.train(P, lgb.Dataset(S.loc[fa, ["lf"]], S.y[fa], weight=S.w[fa]), num_boost_round=100)
        m1 = lgb.train(P, lgb.Dataset(S.loc[fa, cols], S.y[fa], weight=S.w[fa]), num_boost_round=200)
        a0 = roc_auc_score(S.y[fb], m0.predict(S.loc[fb, ["lf"]]), sample_weight=S.w[fb]); a1 = roc_auc_score(S.y[fb], m1.predict(S.loc[fb, cols]), sample_weight=S.w[fb])
        imp = pd.Series(m1.feature_importance("gain"), index=cols).sort_values(ascending=False)
        res[f"fit_{a}_score_{b}"] = {"auc_hazard_only": round(float(a0), 4), "auc_hazard_plus_touch": round(float(a1), 4), "gain": round(float(a1 - a0), 4),
                                     "importance_top6": {k: round(float(v / imp.sum()), 3) for k, v in imp.head(6).items()}}
    pos, neg = S[S.y == 1], S[S.y == 0]
    res["ask_age_ms_median"] = {"decisions": float(np.nanmedian(pos.t_age)), "negatives": float(np.nanmedian(neg.t_age))}
    res["ask_changed_last_250ms_share"] = {"decisions": round(float((pos.t_nch250 > 0).mean()), 4), "negatives_weighted": round(float(np.average((neg.t_nch250 > 0), weights=neg.w)), 4)}
    json.dump(res, open(f"{R}/touch14.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
