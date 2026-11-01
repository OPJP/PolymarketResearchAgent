"""Iteration 14, X126 = X136 (compact form): the operator's TAKE HAZARD on the knee clock with a 50-ms label.
Unit: 50-ms bins on the exchange-equivalent clock, every (window, outcome, bin) of 10-17..22; bin end e. Label: an operator FIRST
leg (an event's first taker order, dcfit14_pred rank 0) on that outcome with match m0 in [e + 205, e + 255) (information horizon
230 +- 25 ms before the match, the fit-day knee). Features end at e (spot, exchange-equivalent = receive - 131) or e + 50 (Polymarket
server ms; the bot reads Polymarket ~30 ms before its arrival at m0 - 150 >= e + 55): outcome-signed spot microprice returns over
50 / 100 / 250 / 500 / 1000 / 3000 ms, mid price-level change over 100 / 250 ms, microprice update count over 250 ms, spot taker
flow over 250 / 1000 ms (capture trades, isBuyerMaker); Polymarket (others' prints, operator and W4 / W5 txs excluded): last implied
o price, its 1 / 5-s change, BUY counts on o and on the other outcome over 1 / 3 s, |p - 0.5|; rel. Baseline: the same model class on
the Polymarket features + rel only. Negatives sampled 1% (weight 100). Fit 10-17..19, score 10-20..22 (weighted AUC).
Usage: python hazard14.py FRAME_DIR HF_DIR TAPE_DIR"""
import os, sys, json, time, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq, lightgbm as lgb
from sklearn.metrics import roc_auc_score

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
REVERSE = os.environ.get("HZ_REVERSE") == "1"  # robustness only: fit 10-20..22, score 10-17..19; never saves models or the scored frame
PM2 = os.environ.get("HZ_PM2") == "1"  # robustness only: a STRONGER Polymarket-only baseline (finer bins, ages, sizes, sells, the other outcome price); never saves models
OWN = os.environ.get("HZ_OWN") == "1"  # mechanism only (own state): + kernels of the operator own past first legs; never saves models or the scored frame
FIT = {"2026-10-20", "2026-10-21", "2026-10-22"} if REVERSE else {"2026-10-17", "2026-10-18", "2026-10-19"}
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
NEG = 0.01
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=14)
SP = [f"sp_r{K}" for K in (50, 100, 250, 500, 1000, 3000)] + ["sp_mid100", "sp_mid250", "sp_nupd250", "sp_flow250", "sp_flow1000"]
PM = ["pm_last", "pm_d1", "pm_d5", "pm_bo1", "pm_bo3", "pm_bx1", "pm_bx3", "pm_dist", "rel"]


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def main():
    D, A, TD = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time(); rng = np.random.default_rng(14)
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "up", "m0", "rank", "day", "start_ts"])
    P = P[P["rank"] == 0]
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= 1792195200) & (win.start_ts < H)].reset_index(drop=True)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "start_ts"])
    excl = set(fl.loc[fl.start_ts >= 1792195200, "tx"].str.lower())
    for cc in win.cid:
        p = f"{TD}/{cc}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            excl |= set(d.loc[d.proxyWallet.str.lower().isin(W45), "transactionHash"].str.lower())
    rows = []
    for day in sorted(P.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        W = win[(win.start_ts >= d0) & (win.start_ts < d0 + 86400)]
        # instants: all positives + 1% of the negatives, per (window, outcome)
        recs = []
        for r in W.itertuples():
            st = int(r.start_ts) * 1000
            e = st + 50 * np.arange(1, 5401)  # bin ends over [0, 270) s
            for up in (1, 0):
                recs.append((r.cid, up, st, e))
        # positives by searchsorted of (m0 - 205 .. m0 - 255] bins
        Pd = P[P.day == day]
        pos = {}
        for (cc, up), g in Pd.groupby(["cid", "up"]):
            pos[(cc, up)] = np.sort(g.m0.to_numpy(np.int64))
        E, CID, UP, Y, WT = [], [], [], [], []
        for cc, up, st, e in recs:
            mm = pos.get((cc, up))
            y = np.zeros(len(e), np.int8)
            if mm is not None and len(mm):
                j0 = np.searchsorted(mm, e + 205, "left"); j1 = np.searchsorted(mm, e + 255, "left")
                y = (j1 > j0).astype(np.int8)
            keep = (y == 1) | (rng.random(len(e)) < NEG)
            E.append(e[keep]); CID.append(np.full(keep.sum(), cc, object)); UP.append(np.full(keep.sum(), up, np.int8)); Y.append(y[keep])
            WT.append(np.where(y[keep] == 1, 1.0, 1.0 / NEG))
        F = pd.DataFrame({"cid": np.concatenate(CID), "up": np.concatenate(UP), "e": np.concatenate(E), "y": np.concatenate(Y), "w": np.concatenate(WT)})
        F["start_ts"] = F.cid.map(W.set_index("cid").start_ts).astype(np.int64)
        F["rel"] = F.e / 1000.0 - F.start_ts
        sg = np.where(F.up.to_numpy() == 1, 1.0, -1.0)
        e = F.e.to_numpy(np.int64); n = len(F)
        # spot (6-h chunks)
        feats = {k: np.full(n, np.nan, np.float32) for k in SP}
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            sel = np.where((e >= lo) & (e < hi))[0]
            if not len(sel):
                continue
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "quantity", "isBuyerMaker"],
                              filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 2000)])
            ty = t.column("type").to_numpy(zero_copy_only=False); bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk] - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); mid = (bp + ap) / 2; o = np.argsort(Tb, kind="stable"); Tb, mic, mid = Tb[o], mic[o], mid[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64)
            qq = t.column("quantity").to_numpy(zero_copy_only=False)[td].astype(float); bm = t.column("isBuyerMaker").to_numpy(zero_copy_only=False)[td].astype(bool)
            o = np.argsort(Tt, kind="stable"); Tt = Tt[o]; cf = np.concatenate([[0.0], np.cumsum(np.where(bm[o], -1.0, 1.0) * qq[o])])
            del t, ty, bk, td, bp, bq, ap, aq, qq, bm; gc.collect()
            ee = e[sel]; s_ = sg[sel]; x0 = at(Tb, mic, ee)
            for K in (50, 100, 250, 500, 1000, 3000):
                feats[f"sp_r{K}"][sel] = (x0 / at(Tb, mic, ee - K) - 1) * 1e4 * s_
            y0 = at(Tb, mid, ee)
            for K in (100, 250):
                feats[f"sp_mid{K}"][sel] = (y0 / at(Tb, mid, ee - K) - 1) * 1e4 * s_
            feats["sp_nupd250"][sel] = np.searchsorted(Tb, ee, "left") - np.searchsorted(Tb, ee - 250, "left")
            for K in (250, 1000):
                feats[f"sp_flow{K}"][sel] = (cf[np.searchsorted(Tt, ee, "left")] - cf[np.searchsorted(Tt, ee - K, "left")]) * s_
            del Tb, mic, mid, Tt, cf; gc.collect()
        for k, v in feats.items():
            F[k] = v
        # Polymarket others' prints (server ms), cut at e + 50
        tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide", "tradeSize"])
        tr = tr[~tr.transactionHash.str.lower().isin(excl)].assign(tokenId=lambda x: x.tokenId.astype(str)).sort_values("exchangeTimestampMs", kind="stable")
        tok = {}
        for r in W.itertuples():
            tok[r.cid] = (str(r.up_token), str(r.down_token))
        byt = {k: g for k, g in tr.groupby("tokenId")}
        pmf = {k: np.full(n, np.nan, np.float32) for k in PM if k != "rel"}
        for (cc, up), ii in F.groupby(["cid", "up"]).indices.items():
            to, tx = tok[cc] if up == 1 else tok[cc][::-1]
            cut = e[ii] + 50
            g = byt.get(to)
            if g is not None and len(g):
                Tg = g.exchangeTimestampMs.to_numpy(np.int64); pr = g.tradePrice.to_numpy(float)
                l0 = at(Tg, pr, cut); pmf["pm_last"][ii] = l0; pmf["pm_d1"][ii] = l0 - at(Tg, pr, cut - 1000); pmf["pm_d5"][ii] = l0 - at(Tg, pr, cut - 5000)
                Tb_ = Tg[g.tradeSide.to_numpy() == "BUY"]
                pmf["pm_bo1"][ii] = np.searchsorted(Tb_, cut, "left") - np.searchsorted(Tb_, cut - 1000, "left")
                pmf["pm_bo3"][ii] = np.searchsorted(Tb_, cut, "left") - np.searchsorted(Tb_, cut - 3000, "left")
            g = byt.get(tx)
            if g is not None and len(g):
                Tb_ = g.exchangeTimestampMs.to_numpy(np.int64)[g.tradeSide.to_numpy() == "BUY"]
                pmf["pm_bx1"][ii] = np.searchsorted(Tb_, cut, "left") - np.searchsorted(Tb_, cut - 1000, "left")
                pmf["pm_bx3"][ii] = np.searchsorted(Tb_, cut, "left") - np.searchsorted(Tb_, cut - 3000, "left")
        for k, v in pmf.items():
            F[k] = v
        F["pm_dist"] = (F.pm_last - 0.5).abs()
        if PM2:
            ext = {k: np.full(n, np.nan, np.float32) for k in ("q_age_o", "q_age_x", "q_bo05", "q_bo10", "q_bx05", "q_bx10", "q_so1", "q_sx1", "q_vo1", "q_vx1", "q_last_x", "q_sz_last")}
            for (cc, up), ii in F.groupby(["cid", "up"]).indices.items():
                to, tx = tok[cc] if up == 1 else tok[cc][::-1]
                cut = e[ii] + 50
                for side_, tk in (("o", to), ("x", tx)):
                    g = byt.get(tk)
                    if g is None or not len(g):
                        continue
                    Tg = g.exchangeTimestampMs.to_numpy(np.int64); sd = g.tradeSide.to_numpy(); sz = g.tradeSize.to_numpy(float); pr = g.tradePrice.to_numpy(float)
                    j = np.searchsorted(Tg, cut, "left")
                    ext[f"q_age_{side_}"][ii] = np.where(j > 0, cut - Tg[np.clip(j - 1, 0, len(Tg) - 1)], np.nan)
                    Tbu = Tg[sd == "BUY"]; Tse = Tg[sd == "SELL"]
                    cb = np.concatenate([[0.0], np.cumsum(sz[sd == "BUY"])])
                    for K, nm in ((500, "05"), (10000, "10")):
                        ext[f"q_b{side_}{nm}"][ii] = np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - K, "left")
                    ext[f"q_s{side_}1"][ii] = np.searchsorted(Tse, cut, "left") - np.searchsorted(Tse, cut - 1000, "left")
                    ext[f"q_v{side_}1"][ii] = cb[np.searchsorted(Tbu, cut, "left")] - cb[np.searchsorted(Tbu, cut - 1000, "left")]
                    if side_ == "x":
                        ext["q_last_x"][ii] = at(Tg, pr, cut)
                    else:
                        ext["q_sz_last"][ii] = at(Tg, sz, cut)
            for k, v in ext.items():
                F[k] = v
        if OWN:  # own-state kernels: the operator's first legs matched before e on the same window (any outcome / same outcome), 30-s and 60-s decay
            Pd2 = P[P.day == day]
            allw = {cc: np.sort(g.m0.to_numpy(np.int64)) for cc, g in Pd2.groupby("cid")}
            for tau in (30000, 60000):
                ka = np.zeros(n, np.float32); ks = np.zeros(n, np.float32)
                for (cc, up), ii in F.groupby(["cid", "up"]).indices.items():
                    ee_ = e[ii]
                    for arr, out in ((allw.get(cc), ka), (pos.get((cc, up)), ks)):
                        if arr is None or not len(arr):
                            continue
                        j = np.searchsorted(arr, ee_, "left")
                        cs = np.concatenate([[0.0], np.cumsum(np.exp(arr / tau - arr.max() / tau))])
                        out[ii] = (cs[j] * np.exp(arr.max() / tau - ee_ / tau)).astype(np.float32)
                F[f"own_all_{tau // 1000}"] = ka; F[f"own_same_{tau // 1000}"] = ks
        F["day"] = day
        rows.append(F)
        print(day, len(F), int(F.y.sum()), round(time.time() - t0), flush=True)
        del tr, byt; gc.collect()
    X = pd.concat(rows, ignore_index=True); del rows
    fit = X.day.isin(FIT).to_numpy(); sc = ~fit
    res = {"instants_fit": int(fit.sum()), "instants_score": int(sc.sum()), "positives_fit": int(X.y[fit].sum()), "positives_score": int(X.y[sc].sum())}
    P_ = {}
    OWNF = ["own_all_30", "own_same_30", "own_all_60", "own_same_60"]
    Q2 = ["q_age_o", "q_age_x", "q_bo05", "q_bo10", "q_bx05", "q_bx10", "q_so1", "q_sx1", "q_vo1", "q_vx1", "q_last_x", "q_sz_last"]
    SETS_ = (("full", SP + PM), ("pm_only", PM), ("spot_only", SP + ["rel"])) + ((("full_own", SP + PM + OWNF), ("pm_own", PM + OWNF)) if OWN else ()) + ((("pm2_only", PM + Q2), ("full_pm2", SP + PM + Q2)) if PM2 else ())
    for nm, cols in SETS_:
        m = lgb.train(PARAMS, lgb.Dataset(X.loc[fit, cols], X.y[fit], weight=X.w[fit]), num_boost_round=300)
        p = m.predict(X.loc[sc, cols], num_threads=4); P_[nm] = p
        if not REVERSE and not OWN and not PM2:
            m.save_model(f"{os.path.dirname(os.path.abspath(__file__))}/model_it14_hazard_{nm}.txt")
        res[f"auc_{nm}"] = round(float(roc_auc_score(X.y[sc], p, sample_weight=X.w[sc])), 4)
        if nm == "full":
            imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
            res["full_importance_top10"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(10).items()}
        print(nm, res[f"auc_{nm}"], flush=True)
    res["gain_full_vs_pm_only"] = round(res["auc_full"] - res["auc_pm_only"], 4)
    # 2-h block bootstrap of the gain (weighted AUC)
    blocks = (X.e.to_numpy()[sc] // 7200000); ub = np.unique(blocks); bidx = {b: np.where(blocks == b)[0] for b in ub}
    yy, ww = X.y.to_numpy()[sc], X.w.to_numpy()[sc]; gs = []
    for _ in range(300):
        ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))])
        gs.append(roc_auc_score(yy[ii], P_["full"][ii], sample_weight=ww[ii]) - roc_auc_score(yy[ii], P_["pm_only"][ii], sample_weight=ww[ii]))
    res["gain_block_ci95_300"] = [round(float(np.quantile(gs, 0.025)), 4), round(float(np.quantile(gs, 0.975)), 4)]
    half = X.e.to_numpy()[sc] < int(pd.Timestamp("2026-10-18 12:00" if REVERSE else "2026-10-21 12:00", tz="UTC").timestamp()) * 1000
    res["halves"] = {nm: {k: round(float(roc_auc_score(yy[h], P_[k][h], sample_weight=ww[h])), 4) for k in ("full", "pm_only")} for nm, h in (("first", half), ("second", ~half))}
    # per wallet: label = a first leg CARRIED by that wallet in the bin (other wallets' first legs count as negatives)
    S_ = X.loc[sc, ["cid", "up", "e", "y", "w"]].reset_index(drop=True)
    for k in P_:
        S_[f"p_{k}"] = P_[k]
    Pw = P[P.day.isin(sorted(set(X.day[sc])))]
    for wname in ("DS", "GF", "XM"):
        g = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["cid", "up", "m0", "rank", "wallet"])
        g = g[(g["rank"] == 0) & (g.wallet == wname)]
        pos = {k: np.sort(v.m0.to_numpy(np.int64)) for k, v in g.groupby(["cid", "up"])}
        yw = np.zeros(len(S_), np.int8)
        for (cc, up), ii in S_.groupby(["cid", "up"]).indices.items():
            mm = pos.get((cc, up))
            if mm is not None and len(mm):
                ee = S_.e.to_numpy(np.int64)[ii]
                yw[ii] = (np.searchsorted(mm, ee + 255, "left") > np.searchsorted(mm, ee + 205, "left")).astype(np.int8)
        res.setdefault("by_wallet_first_legs", {})[wname] = {k: round(float(roc_auc_score(yw, S_[f"p_{k}"], sample_weight=S_.w)), 4) for k in ("full", "pm_only")} | {"positives": int(yw.sum())}
    if not REVERSE and not OWN and not PM2:
        S_.to_parquet(f"{D}/hazard14_scored.parquet", index=False)
    json.dump(res, open(f"{R}/hazard14{'_reverse' if REVERSE else ''}{'_own' if OWN else ''}{'_pm2' if PM2 else ''}.json", "w"), indent=1)
    print(json.dumps(res), round(time.time() - t0))


if __name__ == "__main__":
    main()
