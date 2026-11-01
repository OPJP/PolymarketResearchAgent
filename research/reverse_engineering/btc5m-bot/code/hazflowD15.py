"""Iteration 15, PRE-REGISTRATION 8 (X144 step 2 = X143 step 4): the DEPTH-WEIGHTED decision-hazard nowcast for condition 5. Every
50-ms bin of every (window, outcome) of 10-20..22 is scored with the frozen model_it14_hazard_full.txt (as hazflow14); each bin's
probability is weighted by the expected realized taker fill at the bot's Polymarket view (grid time e + 50 ms, server clock):
E[min(menu, D1)] = (1 - pL) min(30, D1) + pL min(100, D1), D1 = the capture's ask depth at best + 0..1 c of that outcome (l2ingest15),
pL = P(original size >= 90) of the operator taker orders on the pre-10-20 calldata hours of the 30 / 100 menu.
hD(s) = sum over bins with end e in [s - 2, s - 1) s of P^(Up) w(Up) - P^(Down) w(Down); nfhazD15 = cD x hD, cD = no-intercept OLS of
the operator's per-second signed flow on hD on 10-20 ONLY (the only capture-L2 day before the score days). Score days 10-21..22
(576 windows): tracker trk_a (frozen constants, strict fills) with avg, mix14 (frozen) and mix15 = 0.5 avg + 0.5 nfhazD15.
Adoption: mix15 replaces mix14 only if it beats mix14 on BOTH pooled Pearson and Spearman over the 576 windows of 10-21..22.
Usage: python hazflowD15.py HF_DIR TAPE_DIR L2_DIR OUT_DIR"""
import os, sys, json, time, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq, lightgbm as lgb

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import track12
from dc_hazard14 import _at as at

CODE = os.path.dirname(os.path.abspath(__file__))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
DAYS = ["2026-10-20", "2026-10-21", "2026-10-22"]
FIT = set(DAYS[:1])
W45 = {"0xd84403efd50b49a1d8a7181627e00307e6ea5908", "0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c"}
CL = track12.CL


def main():
    A, TD, L2, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    t0 = time.time()
    cd = pd.read_parquet(f"{C}/calldata_sample.parquet", columns=["tx", "role", "maker", "taker_amt"])
    cd = cd[(cd.role == "T") & cd.maker.str.lower().isin(CL)].merge(pd.read_parquet(f"{C}/calldata_sample_txs.parquet"), on="tx", how="left")
    cd = cd[(cd.ts < 1792454400) & cd.taker_amt.astype(float).round().isin([30.0, 100.0])]
    PL = float((cd.taker_amt.astype(float) >= 90).mean()) if len(cd) > 100 else 0.15
    print("pL", PL, len(cd), flush=True)
    GR = {}
    for day in DAYS:
        tk = pd.read_parquet(f"{L2}/l2tok_{day}.parquet"); gd = pd.read_parquet(f"{L2}/l2grid_{day}.parquet", columns=["ti", "k", "c1"])
        c1 = gd.c1.to_numpy(np.float32).reshape(len(tk), -1)
        for i, r in enumerate(tk.itertuples()):
            if int(r.start_ts) >= int(pd.Timestamp(day, tz="UTC").timestamp()) and int(r.start_ts) < int(pd.Timestamp(day, tz="UTC").timestamp()) + 86400:
                GR[(r.cid, int(r.is_up))] = c1[i]
        del gd

    def wexp(D):
        return (1 - PL) * np.minimum(30.0, D) + PL * np.minimum(100.0, D)
    mf = lgb.Booster(model_file=f"{CODE}/model_it14_hazard_full.txt"); FN = mf.feature_name()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "cid", "rel", "is_up", "shares", "start_ts"])
    fl = fl[(fl.start_ts >= 1792195200) & (fl.start_ts < H)].copy()
    excl = set(fl.tx.str.lower())
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    win = win[(win.start_ts >= 1792195200) & (win.start_ts < H)].reset_index(drop=True)
    for cc in win.cid:
        p = f"{TD}/{cc}.parquet"
        if os.path.exists(p):
            d = pd.read_parquet(p, columns=["proxyWallet", "transactionHash"])
            excl |= set(d.loc[d.proxyWallet.str.lower().isin(W45), "transactionHash"].str.lower())
    HS = []
    for day in DAYS:
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSide"])
        tr = tr[~tr.transactionHash.str.lower().isin(excl)].assign(tokenId=lambda x: x.tokenId.astype(str)).sort_values("exchangeTimestampMs", kind="stable")
        byt = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.tradePrice.to_numpy(float), g.tradeSide.to_numpy()) for k, g in tr.groupby("tokenId")}
        del tr
        Wd = win[(win.start_ts >= d0) & (win.start_ts < d0 + 86400)].sort_values("start_ts")
        for h0 in range(0, 24, 4):
            Wc = Wd[(Wd.start_ts >= d0 + h0 * 3600) & (Wd.start_ts < d0 + (h0 + 4) * 3600)]
            if not len(Wc):
                continue
            lo, hi = int(Wc.start_ts.min()) * 1000, (int(Wc.start_ts.max()) + 300) * 1000
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "quantity", "isBuyerMaker"],
                              filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 2000)])
            ty = t.column("type").to_numpy(zero_copy_only=False); bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk] - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); mid = (bp + ap) / 2
            o = np.argsort(Tb, kind="stable"); Tb, mic, mid = Tb[o], mic[o], mid[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64)
            qq = t.column("quantity").to_numpy(zero_copy_only=False)[td].astype(float)
            bm = t.column("isBuyerMaker").to_numpy(zero_copy_only=False)[td].astype(bool)
            o = np.argsort(Tt, kind="stable"); Tt = Tt[o]; cf = np.concatenate([[0.0], np.cumsum(np.where(bm[o], -1.0, 1.0) * qq[o])])
            del t, ty, bk, td, bp, bq, ap, aq, qq, bm; gc.collect()
            for r in Wc.itertuples():
                st = int(r.start_ts) * 1000; ee = st + 50 * np.arange(1, 5401)
                base = {}
                x0 = at(Tb, mic, ee)
                for K in (50, 100, 250, 500, 1000, 3000):
                    base[f"sp_r{K}"] = (x0 / at(Tb, mic, ee - K) - 1) * 1e4
                y0 = at(Tb, mid, ee)
                for K in (100, 250):
                    base[f"sp_mid{K}"] = (y0 / at(Tb, mid, ee - K) - 1) * 1e4
                base["sp_nupd250"] = (np.searchsorted(Tb, ee, "left") - np.searchsorted(Tb, ee - 250, "left")).astype(float)
                for K in (250, 1000):
                    base[f"sp_flow{K}"] = cf[np.searchsorted(Tt, ee, "left")] - cf[np.searchsorted(Tt, ee - K, "left")]
                ps = {}
                for up in (1, 0):
                    sg = 1.0 if up == 1 else -1.0
                    F = {k: (v * sg if k != "sp_nupd250" else v) for k, v in base.items()}
                    F["rel"] = ee / 1000.0 - r.start_ts
                    to, tx = (str(r.up_token), str(r.down_token)) if up == 1 else (str(r.down_token), str(r.up_token))
                    cut = ee + 50
                    for k in ("pm_last", "pm_d1", "pm_d5", "pm_bo1", "pm_bo3", "pm_bx1", "pm_bx3"):
                        F[k] = np.full(len(ee), np.nan)
                    if to in byt:
                        Tg, pr, sd = byt[to]
                        l0 = at(Tg, pr, cut); F["pm_last"] = l0; F["pm_d1"] = l0 - at(Tg, pr, cut - 1000); F["pm_d5"] = l0 - at(Tg, pr, cut - 5000)
                        Tbu = Tg[sd == "BUY"]
                        F["pm_bo1"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 1000, "left")).astype(float)
                        F["pm_bo3"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 3000, "left")).astype(float)
                    if tx in byt:
                        Tg, pr, sd = byt[tx]; Tbu = Tg[sd == "BUY"]
                        F["pm_bx1"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 1000, "left")).astype(float)
                        F["pm_bx3"] = (np.searchsorted(Tbu, cut, "left") - np.searchsorted(Tbu, cut - 3000, "left")).astype(float)
                    F["pm_dist"] = np.abs(F["pm_last"] - 0.5)
                    ps[up] = mf.predict(np.column_stack([F[k] for k in FN]), num_threads=4)
                sec = ((ee - st) // 1000 + 2).astype(np.int64)
                kk = 1201 + np.arange(1, 5401)
                wu = wexp(GR[(r.cid, 1)][kk]) if (r.cid, 1) in GR else np.full(len(ee), 30.0)
                wd = wexp(GR[(r.cid, 0)][kk]) if (r.cid, 0) in GR else np.full(len(ee), 30.0)
                hh = np.bincount(sec, weights=ps[1] - ps[0], minlength=302)[:300]
                hd = np.bincount(sec, weights=ps[1] * wu - ps[0] * wd, minlength=302)[:300]
                aa = np.bincount(sec, weights=ps[1] + ps[0], minlength=302)[:300]
                HS.append(pd.DataFrame({"cid": r.cid, "rel": np.arange(300), "h": hh.astype(np.float32), "hd": hd.astype(np.float32), "act": aa.astype(np.float32), "day": day}))
            del Tb, mic, mid, Tt, cf; gc.collect()
        print(day, round(time.time() - t0), flush=True)
    Hs = pd.concat(HS, ignore_index=True); del HS
    fl["sg"] = np.where(fl.is_up, 1.0, -1.0) * fl.shares
    fl["rel"] = fl.rel.round().astype(np.int64)
    Y = fl.groupby(["cid", "rel"]).sg.sum()
    Hs["y"] = Y.reindex(pd.MultiIndex.from_arrays([Hs.cid, Hs.rel.astype(np.int64)])).fillna(0).to_numpy()
    fit = Hs.day.isin(FIT).to_numpy()
    c = float((Hs.hd[fit] * Hs.y[fit]).sum() / (Hs.hd[fit] ** 2).sum())
    Hs["nfhazD"] = c * Hs.hd
    h14 = pd.read_parquet(os.path.join(os.path.dirname(OUT.rstrip("/")), "it14", "hazflow14.parquet"), columns=["cid", "rel", "nfhaz", "h"]).rename(columns={"h": "h14"})
    Hs = Hs.merge(h14, on=["cid", "rel"], how="left")
    Hs.to_parquet(f"{OUT}/hazflowD15.parquet", index=False)
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf", "ask_u", "ask_d"]).merge(
        pd.read_parquet(f"{C}/it12/nf12b_val.parquet")[["cid", "rel", "nf12b"]], on=["cid", "rel"], how="left")
    S = Hs[~fit].merge(vo, on=["cid", "rel"], how="left").sort_values(["cid", "rel"])
    S["avg"] = 0.5 * (S.nf + S.nf12b.fillna(0)); S["mix14"] = 0.5 * S.avg + 0.5 * S.nfhaz; S["mix15"] = 0.5 * S.avg + 0.5 * S.nfhazD
    g = S.groupby("cid").agg(y=("y", "sum"), nfhaz=("nfhaz", "sum"), nfhazD=("nfhazD", "sum"), avg=("avg", "sum"), mix14=("mix14", "sum"), mix15=("mix15", "sum"))
    res = {"pL": PL, "cD_fit_10_20": round(c, 5), "check_h_vs_h14_r": round(float(np.corrcoef(Hs.h.fillna(0), Hs.h14.fillna(0))[0, 1]), 4),
           "per_second_r_fit": round(float(np.corrcoef(Hs.hd[fit], Hs.y[fit])[0, 1]), 4),
           "per_second_r_score": round(float(np.corrcoef(S.hd, S.y)[0, 1]), 4), "per_second_r_score_h14": round(float(np.corrcoef(S.h, S.y)[0, 1]), 4),
           "window_net_r_10_21_22": {k: round(float(g.y.corr(g[k])), 4) for k in ("nfhaz", "nfhazD", "avg", "mix14", "mix15")},
           "window_net_spearman_10_21_22": {k: round(float(g.y.corr(g[k], method="spearman")), 4) for k in ("nfhaz", "nfhazD", "avg", "mix14", "mix15")}}
    print(json.dumps(res), flush=True)
    winx = pd.read_parquet(f"{C}/windows.parquet").set_index("cid"); cids = S.cid.unique()
    fl2 = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "wallet", "role", "shares", "price", "fee_usd", "cid", "start_ts", "is_up", "up_payout"])
    fl2 = fl2[fl2.cid.isin(cids)]
    mk_tx = set(fl2.loc[fl2.role == "M", "tx"].str.lower())
    parts = [pd.read_parquet(f"{TD}/{c_}.parquet", columns=["proxyWallet", "side", "size", "price", "timestamp", "outcome", "transactionHash"]).assign(cid=c_)
             for c_ in cids if os.path.exists(f"{TD}/{c_}.parquet")]
    TA = pd.concat(parts, ignore_index=True); del parts
    TA = TA[(TA.side == "BUY") & ~TA.proxyWallet.str.lower().isin(CL)]
    TA["rel"] = TA.timestamp - winx.loc[TA.cid, "start_ts"].to_numpy(); TA = TA[(TA.rel >= -2) & (TA.rel <= 305)]
    TA["mk"] = TA.transactionHash.str.lower().isin(mk_tx); TA["up"] = TA.outcome == "Up"
    TA = TA.sort_values(["cid", "up", "rel"], kind="stable")
    tapes = {}
    for (c_, o), dd in TA.groupby(["cid", "up"], sort=False):
        tapes.setdefault(c_, {True: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool)), False: (np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros(0, bool))})
        tapes[c_][bool(o)] = (dd.rel.to_numpy(np.int64), dd.price.to_numpy(float), dd["size"].to_numpy(float), dd.mk.to_numpy())
    fl2["pay"] = np.where(fl2.is_up, fl2.up_payout, 1 - fl2.up_payout); fl2["pnl"] = fl2.shares * (fl2.pay - fl2.price) - fl2.fee_usd
    Wp = {w: fl2[fl2.wallet == w].groupby("cid").pnl.sum().reindex(cids).fillna(0) for w in ("GF", "XM", "DS")}
    Wp["pool"] = fl2.groupby("cid").pnl.sum().reindex(cids).fillna(0)
    blocks = winx.loc[cids, "start_ts"].to_numpy() // 7200
    half = winx.loc[cids, "start_ts"].to_numpy() < int(pd.Timestamp("2026-10-22 00:00", tz="UTC").timestamp())
    for nm in ("avg", "mix14", "mix15", "nfhazD"):
        v = S[["cid", "rel", "ask_u", "ask_d"]].copy(); v["nf"] = S[nm].to_numpy()
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
    a, b = res["tracker_trk_a_mix14"]["pool"], res["tracker_trk_a_mix15"]["pool"]
    res["adopted_mix15"] = bool(b[0] > a[0] and b[1] > a[1])
    json.dump(res, open(f"{R}/hazflowD15.json", "w"), indent=1)
    print("adopted", res["adopted_mix15"], round(time.time() - t0))


if __name__ == "__main__":
    main()
