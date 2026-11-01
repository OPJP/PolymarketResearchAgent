"""Iteration 16 (X154 step 3 / X161 step 2, the DISPATCH-ORACLE ceiling): thin15 with the operator's own visible occupancy (DS / GF
matches in (m - 300, m)), the operator legs in the last 300 ms and a W4 / W5 leg in the last 300 ms as allocation inputs: these are
OWN STATE of the operator (and its sibling wallets), so the result bounds what a replica that simulates the dispatcher could reach,
not a public rule. Base text of thin15 follows.
Iteration 15 (X140 = information P2 step 4; X148 = assumptions P1 step 4): thin14 rerun with a SHARPER allocation model that
adds the per-wallet clock features (the 250-ms spot microprice returns ending c = 400..260 ms before the event's first-leg match,
k400..k260, and the decision-anchor returns dec_bs_mic_* / dec_bt_*; all end at or before the physical horizon m0 - 260). Caveat:
like thin14's tick strength these are anchored on the realized match time. Otherwise identical to thin14:
Iteration 14, X134 = X138 (mechanics P5 / assumptions P4): condition 7 for XM as a random-thinning ceiling.
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
    KC = [f"k{c}" for c in range(400, 250, -10)] + [f"dec_bs_mic_{K}" for K in (100, 250, 500, 1000, 2000)] + [f"dec_bt_{K}" for K in (100, 250, 500, 1000, 2000)]
    Fr = pd.read_parquet(f"{D}/dcclock14_frame.parquet", columns=["cid", "wallet", "up", "m"] + KC).drop_duplicates(["cid", "wallet", "up", "m"])
    T = T.merge(Fr, on=["cid", "wallet", "up", "m"], how="left")
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
    # ---- dispatch state (own / sibling occupancy) at each order: matches of DS / GF / any operator wallet, and W4 / W5 legs, in (m - 300, m)
    allp = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["wallet", "m"])
    mv = T.m.to_numpy()
    for wn in ("DS", "GF", "XM"):
        a = np.sort(allp.m[allp.wallet == wn].to_numpy())
        T[f"busy_{wn}"] = (np.searchsorted(a, mv, "left") - np.searchsorted(a, mv - 300, "right")).astype(float)
    aa = np.sort(allp.m.to_numpy()); T["nop300"] = (np.searchsorted(aa, mv, "left") - np.searchsorted(aa, mv - 300, "right")).astype(float)
    W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
    TD = os.environ["RE16_SCRATCH"] + "/it16/tapes"
    wl = []
    for c_ in T.cid.unique():
        fn = f"{TD}/{c_}.parquet"
        if os.path.exists(fn):
            d_ = pd.read_parquet(fn, columns=["proxyWallet", "side", "transactionHash"])
            d_ = d_[d_.proxyWallet.str.lower().isin(W45) & (d_.side == "BUY")]
            wl += d_.transactionHash.str.lower().tolist()
    wm = mt.reindex(pd.Index(sorted(set(wl)))).dropna().to_numpy()
    wm = np.sort(wm.astype(np.int64))
    T["w45_300"] = (np.searchsorted(wm, mv, "left") - np.searchsorted(wm, mv - 300, "right")).astype(float)
    print("w45 legs with ms", len(wm), "share of XM orders with a w45 leg in 300 ms", round(float((T.w45_300[T.wallet == "XM"] > 0).mean()), 4), flush=True)
    fit = T.day.isin(FIT).to_numpy(); sc = ~fit
    res = {"orders": int(len(T)), "frame_match_coverage": round(cov, 4)}
    DSP = ["busy_DS", "busy_GF", "busy_XM", "nop300", "w45_300"]
    T["nop_all300"] = T.nop300 + T.w45_300   # carrier-agnostic decision density (all five wallets), what a replica could count on its own stream
    # PUBLIC decision density: the frozen knee-clock hazard summed over the 50-ms bins ending in [s - 2, s - 1) s (hazflowD15: act = sum of
    # P^(Up) + P^(Down), h = their difference), at the order's window second s; 10-20..22 only
    hz = pd.read_parquet(os.environ["RE16_SCRATCH"] + "/it15/hazflowD15.parquet", columns=["cid", "rel", "act", "h"])
    T["rsec"] = (T.m // 1000 - T.start_ts).astype(int)
    T = T.merge(hz.rename(columns={"rel": "rsec", "act": "hz_act", "h": "hz_h"}), on=["cid", "rsec"], how="left")
    T["hz_h_o"] = np.where(T.up == 1, T.hz_h, -T.hz_h)
    hz2 = hz.rename(columns={"rel": "rsec", "act": "hz_act_m1", "h": "hz_h_m1"}); hz2["rsec"] = hz2.rsec + 1
    T = T.merge(hz2, on=["cid", "rsec"], how="left")
    if os.environ.get("THIN16_HAZBIN") == "1":
        # PUBLIC local decision density at the bin level: the frozen hazard summed over the 50-ms bins ending in (m - 255 - X, m - 255]
        # (X = 300 / 600 ms; both outcomes, and the bought outcome minus the other), i.e. before the order's own decision band
        zb = np.load(os.environ["RE16_SCRATCH"] + "/it16/hazbins16.npz", allow_pickle=True)
        zi = {c: i for i, c in enumerate(zb["cids"].tolist())}; zst = zb["starts"]; PU = zb["pu"].astype(np.float32); PD = zb["pd"].astype(np.float32)
        CU = np.concatenate([np.zeros((len(PU), 1), np.float32), np.cumsum(PU, 1)], 1); CDn = np.concatenate([np.zeros((len(PD), 1), np.float32), np.cumsum(PD, 1)], 1)
        T = T[T.day.isin(["2026-10-20", "2026-10-21", "2026-10-22"])].reset_index(drop=True)
        for X in (300, 600):
            a_all = np.full(len(T), np.nan); a_o = np.full(len(T), np.nan)
            for i_, r_ in enumerate(T[["cid", "m", "up"]].itertuples(index=False)):
                z = zi.get(r_.cid)
                if z is None:
                    continue
                st = int(zst[z]) * 1000
                k1 = int((r_.m - 255 - st) // 50); k0 = int((r_.m - 255 - X - st) // 50)
                k1 = min(max(k1, 0), 5400); k0 = min(max(k0, 0), 5400)
                u = CU[z, k1] - CU[z, k0]; d_ = CDn[z, k1] - CDn[z, k0]
                a_all[i_] = u + d_; a_o[i_] = (u - d_) if r_.up == 1 else (d_ - u)
            T[f"hzb{X}"] = a_all; T[f"hzb{X}_o"] = a_o
        # PUBLIC book wave at the order's own view cut (m - 230 on the book clock) from the capture L2 grid: o's and the other outcome's
        # depth to best + 4 c relative to 250 / 500 / 1500 ms earlier, and o's best-ask change (the makers' cancellation wave)
        S16 = os.environ["RE16_SCRATCH"]
        gb = {}
        for d in ("2026-10-20", "2026-10-21", "2026-10-22"):
            tk = pd.read_parquet(f"{S16}/it15/l2tok_{d}.parquet"); gd = pd.read_parquet(f"{S16}/it15/l2grid_{d}.parquet", columns=["best", "c4"])
            n_ = len(tk); B_ = gd.best.to_numpy().reshape(n_, -1).astype(np.float32); C4 = gd.c4.to_numpy().reshape(n_, -1).astype(np.float32)
            for i_, r_ in enumerate(tk.itertuples()):
                gb[(r_.cid, int(r_.is_up))] = (int(r_.start_ts), B_[i_], C4[i_])
            del gd
        def at_grid(key, t):
            if key not in gb:
                return np.nan, np.nan
            st, B_, C4 = gb[key]; k = int((t - (st * 1000 - 60000)) // 50)
            if k < 0 or k >= len(C4):
                return np.nan, np.nan
            return B_[k], C4[k]
        cols = {c: np.full(len(T), np.nan) for c in ("o_c4_r250", "o_c4_r500", "o_c4_r1500", "x_c4_r250", "x_c4_r1500", "o_best_d500", "o_c4_0")}
        for i_, r_ in enumerate(T[["cid", "m", "up"]].itertuples(index=False)):
            ko, kx = (r_.cid, int(r_.up)), (r_.cid, 1 - int(r_.up)); t0_ = r_.m - 230
            bo0, co0 = at_grid(ko, t0_); bx0, cx0 = at_grid(kx, t0_)
            for X in (250, 500, 1500):
                bo, co = at_grid(ko, t0_ - X)
                if X in (250, 500, 1500):
                    cols.get(f"o_c4_r{X}", {}) if False else None
                    if f"o_c4_r{X}" in cols:
                        cols[f"o_c4_r{X}"][i_] = co0 / co if co and co > 0 else np.nan
                    if X == 500:
                        cols["o_best_d500"][i_] = bo0 - bo if bo == bo and bo0 == bo0 else np.nan
                bx, cx = at_grid(kx, t0_ - X)
                if f"x_c4_r{X}" in cols:
                    cols[f"x_c4_r{X}"][i_] = cx0 / cx if cx and cx > 0 else np.nan
            cols["o_c4_0"][i_] = co0
        for c_, v_ in cols.items():
            T[c_] = v_
        BK = list(cols)
        FIT[:] = ["2026-10-20"]
        fit = T.day.isin(FIT).to_numpy(); sc = ~fit
        HB = ["hzb300", "hzb300_o", "hzb600", "hzb600_o"]
        if os.environ.get("THIN16_BOOK") == "1":
            feats_sets = {"clock": ["rel", "hour", "k4", "tick", "rank"] + KC, "clock_book": ["rel", "hour", "k4", "tick", "rank"] + KC + BK,
                          "clock_book_hazbin": ["rel", "hour", "k4", "tick", "rank"] + KC + BK + HB, "clock_book_hazbin_no_rank": ["rel", "hour", "k4", "tick"] + KC + BK + HB,
                          "density_true_oracle": ["rel", "hour", "k4", "tick", "rank", "nop_all300"] + KC}
        else:
            feats_sets = {"base_rate": None, "clock": ["rel", "hour", "k4", "tick", "rank"] + KC, "clock_hazbin_density": ["rel", "hour", "k4", "tick", "rank"] + HB + KC,
                          "clock_hazbin_no_rank": ["rel", "hour", "k4", "tick"] + HB + KC, "density_true_oracle": ["rel", "hour", "k4", "tick", "rank", "nop_all300"] + KC}
    elif os.environ.get("THIN16_HAZ") == "1":
        FIT[:] = ["2026-10-20"]
        T = T[T.day.isin(["2026-10-20", "2026-10-21", "2026-10-22"])].reset_index(drop=True)
        fit = T.day.isin(FIT).to_numpy(); sc = ~fit
        feats_sets = {"base_rate": None, "clock": ["rel", "hour", "k4", "tick", "rank"] + KC, "clock_hazard_density": ["rel", "hour", "k4", "tick", "rank", "hz_act", "hz_h_o", "hz_act_m1"] + KC,
                      "clock_hazard_density_no_rank": ["rel", "hour", "k4", "tick", "hz_act", "hz_h_o", "hz_act_m1"] + KC, "density_true_oracle": ["rel", "hour", "k4", "tick", "rank", "nop_all300"] + KC}
    elif os.environ.get("THIN16_DENSITY") == "1":
        feats_sets = {"clock": ["rel", "hour", "k4", "tick", "rank"] + KC, "density_clock": ["rel", "hour", "k4", "tick", "rank", "nop_all300"] + KC,
                      "density_no_rank": ["rel", "hour", "k4", "tick", "nop_all300"] + KC}
    else:
        feats_sets = {"base_rate": None, "clock": ["rel", "hour", "k4", "tick", "rank"] + KC, "dispatch_oracle": ["rel", "hour", "k4", "tick", "rank"] + KC + DSP,
                      "dispatch_only": ["rank"] + DSP}
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
        for b in range(600):
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
    json.dump(res, open(f"{R}/thin16" + (("_hazbin_book" if os.environ.get("THIN16_BOOK") == "1" else "_hazbin") if os.environ.get("THIN16_HAZBIN") == "1" else "_haz" if os.environ.get("THIN16_HAZ") == "1" else ("_density" if os.environ.get("THIN16_DENSITY") == "1" else "")) + ".json", "w"), indent=1)


if __name__ == "__main__":
    main()
