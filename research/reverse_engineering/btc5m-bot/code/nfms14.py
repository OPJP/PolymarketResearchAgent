"""Iteration 14, PRE-REGISTRATION 6 (X131 = X137): a millisecond net-flow nowcast 'nfms14' for the exposure tracker (condition 5).
Target: operator signed shares per (window, block second s), Up +, both roles. Features stamped before tau - 1000 ms (tau = start of
block second s): capture spot book microprice slices / sharp-tick stats (exchange-equivalent clock = receive - 131), spot trades
(exchange ms), capture Polymarket non-operator trades (server ms; operator txs and W4 / W5 taker txs excluded), rel, and the frozen
nf (it4b) / nf12b cell predictions. LightGBM (nf12 PARAMS / ROUNDS) fit 10-17..19, scored once on 10-20..22; then the tracker trk_a
with target nfms14 vs the frozen avg target on the same 864 windows. Usage: python nfms14.py HF_DIR TAPE_DIR OUT_DIR"""
import os, sys, json, time, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq, lightgbm as lgb

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track12

C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
DAYS = ["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]
FIT = DAYS[:3]
TRANSIT = 131
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=400, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=12)
ROUNDS = 400


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def main():
    A, TD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
    t0 = time.time()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "cid", "rel", "is_up", "shares", "start_ts"])
    fl = fl[(fl.start_ts >= 1792195200) & (fl.start_ts < H)]
    op_tx = set(fl.tx.str.lower())
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    fl["rel"] = fl.rel.round().astype(np.int64)
    Y = fl.groupby(["cid", "rel"]).sg.sum()
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= 1792195200) & (win.start_ts < H)].reset_index(drop=True)
    tok = {}
    for r in win.itertuples():
        tok[str(r.up_token)] = (r.cid, 1); tok[str(r.down_token)] = (r.cid, 0)
    w45_tx = set()
    for cid in win.cid:
        p = f"{TD}/{cid}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            w45_tx |= set(d.loc[d.proxyWallet.str.lower().isin(W45), "transactionHash"].str.lower())
    excl = op_tx | w45_tx
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf", "ask_u", "ask_d"])
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]]
    vo = vo.merge(nb, on=["cid", "rel"], how="left")
    parts = []
    for day in DAYS:
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        W = win[(win.start_ts >= d0) & (win.start_ts < d0 + 86400)]
        cid = np.repeat(W.cid.to_numpy(), 300); s = np.tile(np.arange(300), len(W))
        tau = (np.repeat(W.start_ts.to_numpy(np.int64), 300) + s) * 1000
        F = {"cid": cid, "rel": s.astype(np.int16)}
        n = len(tau)
        # Polymarket non-operator trades (server ms)
        tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSize", "tradeSide"])
        tr = tr[~tr.transactionHash.str.lower().isin(excl)].copy()
        mp = tr.tokenId.astype(str).map(lambda k: tok.get(k, (None, None)))
        tr["cid"] = [x[0] for x in mp]; tr["isup"] = [x[1] for x in mp]
        tr = tr[tr.cid.notna()].sort_values("exchangeTimestampMs", kind="stable")
        tr["impl"] = np.where(tr.isup == 1, tr.tradePrice, 1 - tr.tradePrice)
        tr["sf"] = np.where((tr.tradeSide == "BUY") == (tr.isup == 1), 1.0, -1.0) * tr.tradeSize
        tr["bu"] = ((tr.tradeSide == "BUY") & (tr.isup == 1)).astype(float); tr["bd"] = ((tr.tradeSide == "BUY") & (tr.isup == 0)).astype(float)
        pf = {k: np.full(n, np.nan, np.float32) for k in ("pm_f1", "pm_f2", "pm_bu1", "pm_bd1", "pm_last", "pm_d3")}
        cpos = pd.Series(np.arange(n)).groupby(cid).apply(lambda x: x.to_numpy())
        for c_, g in tr.groupby("cid"):
            if c_ not in cpos.index:
                continue
            ii = cpos[c_]; T_ = g.exchangeTimestampMs.to_numpy(np.int64); tt = tau[ii]
            cs = np.concatenate([[0.0], np.cumsum(g.sf.to_numpy(float))]); cu = np.concatenate([[0.0], np.cumsum(g.bu.to_numpy())]); cd = np.concatenate([[0.0], np.cumsum(g.bd.to_numpy())])
            k1, k2, k4 = (np.searchsorted(T_, tt - x, "left") for x in (1000, 2000, 4000))
            pf["pm_f1"][ii] = cs[k1] - cs[k2]; pf["pm_f2"][ii] = cs[k2] - cs[k4]
            pf["pm_bu1"][ii] = cu[k1] - cu[k2]; pf["pm_bd1"][ii] = cd[k1] - cd[k2]
            P_ = g.impl.to_numpy(float)
            l0 = at(T_, P_, tt - 1000); pf["pm_last"][ii] = l0; pf["pm_d3"][ii] = l0 - at(T_, P_, tt - 4000)
        F.update(pf); del tr; gc.collect()
        # spot book and trades, 4-hour chunks
        sf = {k: np.full(n, np.nan, np.float32) for k in [f"dm{j}" for j in range(5)] + ["dm_old", "rmax", "rmin", "rsum", "rcnt", "bt35", "bt15"]}
        G = np.arange(-3500 + 250, -1000 + 1, 50)  # 50-ms grid ends inside [tau - 3500, tau - 1000], 250-ms returns
        for h0 in range(0, 24, 4):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 4) * 3600) * 1000
            sel = np.where((tau >= lo) & (tau < hi))[0]
            if not len(sel):
                continue
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"],
                              filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 2000)])
            ty = t.column("type").to_numpy(zero_copy_only=False); bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk] - TRANSIT
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64); pt = t.column("price").to_numpy(zero_copy_only=False)[td].astype(float)
            o = np.argsort(Tt, kind="stable"); Tt, pt = Tt[o], pt[o]
            del t, ty, bk, td, bp, bq, ap, aq; gc.collect()
            tt = tau[sel]
            for j in range(5):
                a1 = at(Tb, mic, tt - 1000 - 500 * j); a0 = at(Tb, mic, tt - 1500 - 500 * j)
                sf[f"dm{j}"][sel] = (a1 / a0 - 1) * 1e4
            sf["dm_old"][sel] = (at(Tb, mic, tt - 3500) / at(Tb, mic, tt - 5500) - 1) * 1e4
            for c0 in range(0, len(sel), 20000):
                ss = sel[c0:c0 + 20000]; tg = tau[ss][:, None] + G[None, :]
                r = (at(Tb, mic, tg.ravel()) / at(Tb, mic, tg.ravel() - 250) - 1).reshape(tg.shape) * 1e4
                r = np.nan_to_num(r)
                sf["rmax"][ss] = r.max(1); sf["rmin"][ss] = r.min(1)
                big = np.abs(r) >= 0.5
                sf["rsum"][ss] = (r * big).sum(1); sf["rcnt"][ss] = (big & (r > 0)).sum(1) - (big & (r < 0)).sum(1)
            p1 = at(Tt, pt, tt - 1000)
            sf["bt35"][sel] = (p1 / at(Tt, pt, tt - 3500) - 1) * 1e4; sf["bt15"][sel] = (p1 / at(Tt, pt, tt - 1500) - 1) * 1e4
            del Tb, mic, Tt, pt; gc.collect()
        F.update(sf)
        Fd = pd.DataFrame(F); Fd["day"] = day
        parts.append(Fd)
        print(day, len(Fd), round(time.time() - t0), flush=True)
    X = pd.concat(parts, ignore_index=True); del parts
    X = X.merge(vo, on=["cid", "rel"], how="left")
    X["y"] = Y.reindex(pd.MultiIndex.from_arrays([X.cid, X.rel.astype(np.int64)])).fillna(0).to_numpy()
    feats = [f"dm{j}" for j in range(5)] + ["dm_old", "rmax", "rmin", "rsum", "rcnt", "bt35", "bt15", "pm_f1", "pm_f2", "pm_bu1", "pm_bd1", "pm_last", "pm_d3", "rel", "nf", "nf12b"]
    fit = X.day.isin(FIT).to_numpy(); sc = ~fit
    m = lgb.train(PARAMS, lgb.Dataset(X.loc[fit, feats], X.y[fit]), num_boost_round=ROUNDS)
    m.save_model(f"{OUT}/model_it14_nfms14.txt")
    X.loc[sc, "nfms14"] = m.predict(X.loc[sc, feats], num_threads=4)
    imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
    S = X[sc]
    net = S.groupby("cid").y.sum()
    res = {"cells_fit": int(fit.sum()), "cells_scored": int(sc.sum()), "w45_tx_excluded": len(w45_tx),
           "importance_top12": {k: round(float(v / imp.sum()), 4) for k, v in imp.head(12).items()}}
    g = S.groupby("cid").agg(nfms=("nfms14", "sum"), nf=("nf", "sum"), nb=("nf12b", "sum"))
    g["avg"] = 0.5 * (g.nf + g.nb)
    res["window_net_r_10_20_22"] = {k: round(float(net.corr(g[k])), 4) for k in ("nfms", "avg", "nb", "nf")}
    early = S[S.rel < 150]; ne = early.groupby("cid").y.sum(); ge = early.groupby("cid").agg(nfms=("nfms14", "sum"), nf=("nf", "sum"), nb=("nf12b", "sum"))
    res["early_flow_r_0_150"] = {"nfms": round(float(ne.corr(ge.nfms)), 4), "avg": round(float(ne.corr(0.5 * (ge.nf + ge.nb))), 4)}
    S[["cid", "rel", "nfms14", "nf", "nf12b", "y"]].to_parquet(f"{OUT}/nfms14_val.parquet", index=False)
    print(json.dumps(res), flush=True)
    # ---- tracker on the 864 scored windows: avg (frozen) vs nfms14 (pre-registered adoption rule)
    winx = pd.read_parquet(f"{C}/windows.parquet").set_index("cid")
    cids = S.cid.unique()
    fl2 = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl2 = fl2[fl2.cid.isin(cids)]
    mk_tx = set(fl2.loc[fl2.role == "M", "tx"].str.lower())
    tparts = []
    for c_ in cids:
        p = f"{TD}/{c_}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"])
            if len(d):
                tparts.append(d.assign(cid=c_))
    TA = pd.concat(tparts, ignore_index=True); del tparts
    TA = TA[(TA.side == "BUY") & ~TA.proxyWallet.str.lower().isin(CL)]
    TA["rel"] = TA.timestamp - winx.loc[TA.cid, "start_ts"].to_numpy()
    TA = TA[(TA.rel >= -2) & (TA.rel <= 305)]
    TA["mk"] = TA.transactionHash.str.lower().isin(mk_tx); TA["up"] = TA.outcome == "Up"
    TA = TA.sort_values(["cid", "up", "rel"], kind="stable")
    tapes = {}
    for (c_, o), dd in TA.groupby(["cid", "up"], sort=False):
        tapes.setdefault(c_, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[c_][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    fl2["pay"] = np.where(fl2.is_up, fl2.up_payout, 1 - fl2.up_payout)
    fl2["pnl"] = fl2.shares * (fl2.pay - fl2.price) - fl2.fee_usd
    Wp = {w: fl2[fl2.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
    Wp["pool"] = fl2.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    blocks = winx.loc[cids, "start_ts"].to_numpy() // 7200
    half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-21 12:00", tz="UTC").timestamp())
    base = S[["cid", "rel", "ask_u", "ask_d", "nf", "nf12b", "nfms14"]].sort_values(["cid", "rel"])
    for nm, col in (("avg", None), ("nfms14", "nfms14")):
        v = base.copy()
        v["nf"] = 0.5 * (v.nf + v.nf12b.fillna(0)) if col is None else v[col]
        T, fin = track12.run(winx, v, tapes, mk_tx, track12.VARIANTS["trk_a"])
        rp = T.groupby("cid").pnl.sum().reindex(cids).fillna(0)
        o = {"fills": int(len(T)), "usd": round(float((T.price * T.shares).sum()), 1), "pnl_before_rebates": round(float(T.pnl.sum()), 1)}
        for w, wp in Wp.items():
            o[w] = [round(float(rp.corr(wp)), 4), round(float(rp.corr(wp, method="spearman")), 4)]
        rng = np.random.default_rng(14); ub = np.unique(blocks); bidx = {b: np.where(blocks == b)[0] for b in ub}
        x, yy = rp.to_numpy(), Wp["pool"].to_numpy(); bs = []
        for _ in range(1000):
            ii = np.concatenate([bidx[b] for b in rng.choice(ub, len(ub))]); bs.append(np.corrcoef(x[ii], yy[ii])[0, 1])
        o["pool_pearson_block_ci95"] = [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)]
        o["pool_halves"] = [round(float(np.corrcoef(x[h], yy[h])[0, 1]), 4) for h in (half, ~half)]
        res[f"tracker_trk_a_{nm}"] = o
        print(nm, json.dumps(o), flush=True)
    a, b = res["tracker_trk_a_avg"]["pool"], res["tracker_trk_a_nfms14"]["pool"]
    res["adopted"] = bool(b[0] > a[0] and b[1] > a[1])
    json.dump(res, open(f"{R}/nfms14.json", "w"), indent=1)
    print("adopted", res["adopted"], round(time.time() - t0))


if __name__ == "__main__":
    main()
