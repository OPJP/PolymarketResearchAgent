"""Iteration 16 (X161 step 1 input): the frozen knee-clock hazard model_it14_hazard_full.txt scored on EVERY 50-ms bin of every (window,
outcome) of 10-20..22 exactly as hazflowD15 does, stored per bin (float16, P^(Up) and P^(Down)) so that a replica's own local decision
density (the hazard summed over the 300 ms before a decision) can be computed. Derived from hazflowD15.py (tracker part removed).
Iteration 15, PRE-REGISTRATION 8 (X144 step 2 = X143 step 4): the DEPTH-WEIGHTED decision-hazard nowcast for condition 5. Every
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
                HS.append((r.cid, int(r.start_ts), ps[1].astype(np.float16), ps[0].astype(np.float16)))
            del Tb, mic, mid, Tt, cf; gc.collect()
        print(day, round(time.time() - t0), flush=True)
    cids = [h[0] for h in HS]; sts = np.array([h[1] for h in HS], np.int64)
    np.savez_compressed(f"{OUT}/hazbins16.npz", cids=np.array(cids), starts=sts, pu=np.stack([h[2] for h in HS]), pd=np.stack([h[3] for h in HS]))
    print("saved", len(HS), "windows", round(time.time() - t0), flush=True)

if __name__ == "__main__":
    main()
