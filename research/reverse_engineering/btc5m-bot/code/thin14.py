"""Iteration 14, X134 = X138 (mechanics P5 / assumptions P4): condition 7 for XM as a random-thinning ceiling.
Units: operator taker orders of 10-17..22 with a capture match ms (dcfit14_pred.parquet) + their realized PnL from fills (taker role,
one per (tx, wallet, token)); maker-role fills kept as their own stream. Allocation model P(wallet | public state at the decision):
multinomial LightGBM on rel, hour, window index mod 4, |p_dc - 0.5| (tick strength from the re-clocked side model), leg rank, and
(oracle-ish, post hoc) the dispatch-phase flag of ab14; fitted on 10-17..19, applied to 10-20..22. Then:
 (1) ORACLE: every true operator decision with its true side, size and realized PnL, weighted by P^(XM); corr with XM's true window
     taker PnL / total PnL (maker part: XM's realized maker PnL is unknown to the oracle -> the pooled maker PnL x XM's maker share);
 (2) REDRAW: the wallet of each true decision redrawn 2,000 times from P^; corr(redrawn XM window PnL, true XM window PnL) and the
     test-retest between two redraws (its square root bounds any predictor if allocation is a thinning).
Usage: python thin14.py FRAME_DIR HF_DIR"""
import os, sys, json
import numpy as np, pandas as pd, lightgbm as lgb

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
FIT = ["2026-10-17", "2026-10-18", "2026-10-19"]
WL = ["DS", "GF", "XM"]


def main():
    D = sys.argv[1]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet")
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "token", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl = fl[fl.start_ts >= 1792195200].copy()
    fl["pay"] = np.where(fl.is_up, fl.up_payout, 1 - fl.up_payout)
    fl["pnl"] = fl.shares * (fl.pay - fl.price) - fl.fee_usd
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    # one row per taker order; attach PnL to the frame by (cid, wallet, up, m-order): rebuild the same unit from fills
    T = fl[fl.role == "T"].groupby(["tx", "wallet", "token"], as_index=False).agg(cid=("cid", "first"), up=("is_up", "first"), pnl=("pnl", "sum"), sg=("sg", "sum"), start_ts=("start_ts", "first"))
    # the frame lacks tx; recover by matching (cid, wallet, up) order sequences is fragile -> rebuild m per tx from the frame's order
    # instead: allocate at the level of fills' taker orders, using the frame only for the decision-clock state of the same window second
    T["day"] = pd.to_datetime(T.start_ts, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    T = T[T.day.isin(sorted(P.day.unique()))].reset_index(drop=True)
    # public state per taker order: join the frame on (cid, wallet, up, m), m = the capture match ms of the order's tx
    A = sys.argv[2]
    mt = pd.concat([pd.read_parquet(f"{A}/pm_trades_{d}.parquet", columns=["exchangeTimestampMs", "transactionHash"]) for d in sorted(P.day.unique())])
    mt = mt.assign(h=mt.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    T["m"] = T.tx.str.lower().map(mt)
    T["up"] = T.up.astype(int)
    Pj = P.drop_duplicates(["cid", "wallet", "up", "m"])[["cid", "wallet", "up", "m", "rank", "rel", "p_dc14_spot_own"]]
    T = T.merge(Pj, on=["cid", "wallet", "up", "m"], how="left")
    T.loc[T["rank"].isna(), "m"] = np.nan
    cov = float(T.m.notna().mean())
    T = T[T.m.notna()].reset_index(drop=True)
    T["hour"] = ((T.m // 1000) % 86400) // 3600
    T["k4"] = (T.start_ts // 300) % 4
    T["tick"] = (T.p_dc14_spot_own.fillna(0.5) - 0.5).abs()
    ab = pd.read_csv(f"{R}/ab14_hours.csv")
    dph = set(ab.loc[ab.disp_phase, "hour"].astype(int))
    T["phase"] = ((T.start_ts // 3600) * 3600).isin(dph).astype(int)
    T["y"] = T.wallet.map({w: i for i, w in enumerate(WL)})
    fit = T.day.isin(FIT).to_numpy(); sc = ~fit
    res = {"orders": int(len(T)), "frame_match_coverage": round(cov, 4)}
    feats_sets = {"base_rate": None, "public": ["rel", "hour", "k4", "tick", "rank"], "public_plus_phase": ["rel", "hour", "k4", "tick", "rank", "phase"]}
    S = T[sc].reset_index(drop=True)
    cids = np.unique(S.cid)
    ci = pd.Index(cids)
    wi = ci.get_indexer(S.cid)
    # true XM window PnL (taker) and total (taker + maker)
    xm_t = np.bincount(wi, weights=np.where(S.wallet == "XM", S.pnl, 0.0), minlength=len(cids))
    flS = fl[fl.cid.isin(cids)]
    xm_tot = flS[flS.wallet == "XM"].groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
    mk_pool = flS[flS.role == "M"].groupby("cid").pnl.sum().reindex(cids).fillna(0).to_numpy()
    xm_mk_share = float(fl[(fl.role == "M") & fl.cid.isin(T[fit].cid.unique())].wallet.eq("XM").mean())
    st_w = S.groupby("cid").start_ts.first().reindex(cids).to_numpy()
    half = st_w < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
    rng = np.random.default_rng(14)
    for nm, cols in feats_sets.items():
        if cols is None:
            q = np.tile(np.bincount(T.y[fit], minlength=3) / fit.sum(), (len(S), 1))
            auc = None
        else:
            m = lgb.train(dict(objective="multiclass", num_class=3, learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, max_bin=63, verbose=-1, num_threads=4, seed=14),
                          lgb.Dataset(T.loc[fit, cols], T.y[fit]), num_boost_round=200)
            q = m.predict(S[cols])
            from sklearn.metrics import roc_auc_score
            auc = {w: round(float(roc_auc_score((S.wallet == w).astype(int), q[:, i])), 4) for i, w in enumerate(WL)}
        ll = float(-np.mean(np.log(np.clip(q[np.arange(len(S)), S.y.to_numpy()], 1e-9, 1))))
        orc_t = np.bincount(wi, weights=q[:, 2] * S.pnl.to_numpy(), minlength=len(cids))
        orc_tot = orc_t + xm_mk_share * mk_pool
        o = {"auc_one_vs_rest": auc, "log_loss": round(ll, 4),
             "oracle_xm_taker_pnl_r": round(float(np.corrcoef(orc_t, xm_t)[0, 1]), 4),
             "oracle_xm_total_pnl_r": round(float(np.corrcoef(orc_tot, xm_tot)[0, 1]), 4),
             "oracle_xm_total_pnl_r_halves": [round(float(np.corrcoef(orc_tot[h], xm_tot[h])[0, 1]), 4) for h in (half, ~half)]}
        # redraws
        cq = np.cumsum(q, 1)
        rr, tr = [], []
        prev = None
        for b in range(2000):
            u = rng.random(len(S))
            z = (u[:, None] > cq).sum(1) == 2
            xr = np.bincount(wi, weights=np.where(z, S.pnl.to_numpy(), 0.0), minlength=len(cids))
            rr.append(np.corrcoef(xr, xm_t)[0, 1])
            if prev is not None and b % 2 == 1:
                tr.append(np.corrcoef(xr, prev)[0, 1])
            prev = xr
        rr, tr = np.array(rr), np.array(tr)
        o["redraw_corr_with_true_xm_taker_pnl"] = {"q025": round(float(np.quantile(rr, 0.025)), 4), "median": round(float(np.median(rr)), 4), "q975": round(float(np.quantile(rr, 0.975)), 4)}
        o["redraw_test_retest"] = {"median": round(float(np.median(tr)), 4), "sqrt_median_ceiling": round(float(np.sqrt(max(np.median(tr), 0))), 4)}
        res[nm] = o
        print(nm, json.dumps(o), flush=True)
    res["xm_maker_share_fit"] = round(xm_mk_share, 4)
    res["windows_scored"] = int(len(cids))
    json.dump(res, open(f"{R}/thin14.json", "w"), indent=1)


if __name__ == "__main__":
    main()
