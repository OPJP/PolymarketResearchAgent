"""Iteration 14, PRE-REGISTRATION 5 (X125 = X135; written in NOTES.md before this script was run): the decision clock re-anchored on
EXCHANGE time at c = 150 + 105 + 5 = 260 ms before the operator's match (physics, not accuracy).

Units: operator taker orders (fills role T, one per (tx, wallet, token)) of windows starting 10-17..22 with a capture match ms m (min
exchangeTimestampMs of the tx in the public capture's trade rows, revision f848a77c). Events: orders on the same (window, outcome)
less than 300 ms after the previous order of the event; m0 = the first leg's m.
Anchors: exchange-stamped series cut at X = m - 260; the capture's Binance spot book (collector receive clock) at X + 131.
PRIMARY 'dc14_spot' (exam-routable: inputs the capture carries every day): spot-book microprice / mid returns over [X+131-K, X+131),
spot-trade last-price returns over [X-K, X) (exchange ms), K = 100..2000, rel. SECONDARY 'dc14_full': + USD-M BTC / ETH, OKX swap
trades (exchange ms) and Bybit BTC / ETH 100-ms book bins (bin end <= X). LightGBM, dcside13 PARAMS / ROUNDS, fit 10-17..19, scored
once on 10-20..22. Controls: placebo anchors m -/+ 3000; fit-day knee scan; crowd control (non-operator taker BUYs > 1 s from any
operator match on the window); market-only baseline from the capture's non-operator Polymarket trades; own-inventory baseline.
Usage: python dcclock14.py HF_DIR OUT_DIR"""
import os, sys, json, time, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq, lightgbm as lgb

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CODE = os.path.dirname(os.path.abspath(__file__))
H = 1792713600
DAYS = ["2026-10-17", "2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]
FIT = DAYS[:3]
KS = (100, 250, 500, 1000, 2000)
C_EX = 260          # exchange-time cutoff before the match (ms), fixed by physics in pre-registration 5
TRANSIT = 131       # capture collector receive - Binance exchange stamp (median of spot trades, iteration 13)
OLD_LAG = 180       # pre-registrations 3 / 4: a = m - 180 on the collector receive clock
PL = 3000           # placebo shift (ms)
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=13)
ROUNDS = 300
CSCAN = list(range(400, 140, -10))


def at(T, X, t, how="left"):
    i = np.searchsorted(T, t, how) - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def rets(T, X, cut, how="left"):
    x0 = at(T, X, cut, how)
    return {K: ((x0 / at(T, X, cut - K, how) - 1) * 1e4).astype(np.float32) for K in KS}


def main():
    A, OUT = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "ts", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh", "cid", "side"])
    fl = fl[(fl.start_ts >= 1792195200) & (fl.start_ts < H)].copy()
    fl["osz"] = fl.groupby("oh").shares.transform("sum")
    op_tx = set(fl.tx.str.lower())
    win = pd.read_parquet(f"{C}/windows.parquet", columns=["cid", "start_ts", "up_token", "down_token"])
    tok = {}
    for r in win.itertuples():
        tok[str(r.up_token)] = (r.cid, 1, r.start_ts); tok[str(r.down_token)] = (r.cid, 0, r.start_ts)
    parts, crowd_parts, knee_parts, cover = [], [], [], {}
    for day in DAYS:
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp()); d0ms = d0 * 1000
        tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash", "tokenId", "tradePrice", "tradeSize", "tradeSide"])
        tr["h"] = tr.transactionHash.str.lower()
        mt = tr.groupby("h").exchangeTimestampMs.min()
        f = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400) & (fl.role == "T")].drop_duplicates(["tx", "wallet", "token"]).copy()
        f["m"] = f.tx.str.lower().map(mt)
        n_all = len(f)
        f = f[f.m.notna()].copy(); f["m"] = f.m.astype(np.int64)
        f = f.sort_values(["cid", "is_up", "m"], kind="stable").reset_index(drop=True)
        new = (f.cid != f.cid.shift()) | (f.is_up != f.is_up.shift()) | (f.m - f.m.shift() >= 300)
        f["ev"] = new.cumsum().astype(np.int64) + len(parts) * 10_000_000
        f["rank"] = f.groupby("ev").cumcount()
        f["m0"] = f.groupby("ev").m.transform("first")
        cover[day] = [int(len(f)), int(n_all)]
        # ---- Polymarket market-only state (non-operator trades; server clock cut at m - 180) and the crowd control set
        tr = tr[~tr.h.isin(op_tx)].copy()
        tr["tokenId"] = tr.tokenId.astype(str)
        mp = tr.tokenId.map(lambda k: tok.get(k, (None, None, None)))
        tr["cid"] = [x[0] for x in mp]; tr["isup"] = [x[1] for x in mp]
        tr = tr[tr.cid.notna()].sort_values("exchangeTimestampMs", kind="stable")
        tr["impl_up"] = np.where(tr.isup == 1, tr.tradePrice, 1 - tr.tradePrice)
        sgn = np.where((tr.tradeSide == "BUY") == (tr.isup == 1), 1.0, -1.0)
        tr["sflow"] = sgn * tr.tradeSize.to_numpy(float)
        pmS = {}
        for cid, g in tr.groupby("cid"):
            pmS[cid] = (g.exchangeTimestampMs.to_numpy(np.int64), g.impl_up.to_numpy(float), np.cumsum(g.sflow.to_numpy(float)))
        # crowd taker BUYs: one per (tx, token); exclude those within 1 s of any operator match on the same window
        cb = tr[tr.tradeSide == "BUY"].groupby(["h", "tokenId"], as_index=False).agg(mc=("exchangeTimestampMs", "min"), cid=("cid", "first"), up=("isup", "first"))
        opm = f.groupby("cid").m.apply(lambda s: np.sort(s.to_numpy()))
        keep = np.ones(len(cb), bool)
        for cid, g in cb.groupby("cid"):
            if cid in opm.index:
                om = opm[cid]; mc = g.mc.to_numpy()
                j = np.searchsorted(om, mc)
                dl = np.abs(mc - om[np.clip(j - 1, 0, len(om) - 1)]); dr = np.abs(om[np.clip(j, 0, len(om) - 1)] - mc)
                keep[g.index.to_numpy()] = np.minimum(dl, dr) > 1000
        cb = cb[keep].copy(); cb["day"] = day
        # ---- spot book (receive clock) and spot trades (exchange clock), 4-hour chunks
        n = len(f)
        feats = {k: np.full(n, np.nan, np.float32) for k in
                 [f"{s}_{nm}_{K}" for s in ("own", "dec", "plm", "plp") for nm in ("bs_mic", "bs_mid", "bt") for K in KS] +
                 [f"old_bs_{nm}_{K}" for nm in ("mic", "mid") for K in KS]}
        knee = {c: np.zeros(n, np.float32) for c in CSCAN}
        cknee = {c: np.zeros(len(cb), np.float32) for c in CSCAN}
        mm = f.m.to_numpy(np.int64); m0 = f.m0.to_numpy(np.int64); mcb = cb.mc.to_numpy(np.int64)
        for h0 in range(0, 24, 4):
            lo, hi = d0ms + h0 * 3600000, d0ms + (h0 + 4) * 3600000
            so = (mm >= lo) & (mm < hi); sc = (mcb >= lo) & (mcb < hi)
            if not so.any() and not sc.any():
                continue
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price"],
                              filters=[("receivedTimestampMs", ">=", lo - 8000), ("receivedTimestampMs", "<", hi + 8000)])
            ty = t.column("type").to_numpy(zero_copy_only=False)
            bk = ty == "book"; td = ty == "trade"
            Tb = t.column("receivedTimestampMs").to_numpy()[bk]
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False)[bk].astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); mid = (bp + ap) / 2
            del bp, bq, ap, aq
            o = np.argsort(Tb, kind="stable"); Tb, mic, mid = Tb[o], mic[o], mid[o]
            Tt = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False)[td].astype(np.int64)
            pt = t.column("price").to_numpy(zero_copy_only=False)[td].astype(float)
            o = np.argsort(Tt, kind="stable"); Tt, pt = Tt[o], pt[o]
            del t, ty, bk, td; gc.collect()
            idx = np.where(so)[0]
            for tag, base in (("own", mm[idx]), ("dec", m0[idx]), ("plm", mm[idx] - PL), ("plp", mm[idx] + PL)):
                X = base - C_EX
                for nm, S in (("bs_mic", mic), ("bs_mid", mid)):
                    for K, v in rets(Tb, S, X + TRANSIT).items():
                        feats[f"{tag}_{nm}_{K}"][idx] = v
                for K, v in rets(Tt, pt, X).items():
                    feats[f"{tag}_bt_{K}"][idx] = v
            for nm, S in (("mic", mic), ("mid", mid)):  # the old anchor exactly as dc_exam13 (receive clock, 'right')
                for K, v in rets(Tb, S, mm[idx] - OLD_LAG, how="right").items():
                    feats[f"old_bs_{nm}_{K}"][idx] = v
            Te = Tb - TRANSIT
            for c in CSCAN:  # univariate knee profile: sign of the microprice change over [m0 - c - 250, m0 - c), exchange-equivalent clock
                knee[c][idx] = (at(Te, mic, m0[idx] - c) - at(Te, mic, m0[idx] - c - 250)).astype(np.float32)
            jdx = np.where(sc)[0]
            if len(jdx):
                for c in CSCAN:
                    cknee[c][jdx] = (at(Te, mic, mcb[jdx] - c) - at(Te, mic, mcb[jdx] - c - 250)).astype(np.float32)
            del Tb, mic, mid, Tt, pt, Te; gc.collect()
        F = pd.DataFrame({"cid": f.cid.to_numpy(), "wallet": f.wallet.to_numpy(), "up": f.is_up.to_numpy(int), "m": mm, "m0": m0,
                          "rank": f["rank"].to_numpy(), "ev": f.ev.to_numpy(), "osz": f.osz.to_numpy(float), "start_ts": f.start_ts.to_numpy(np.int64), "day": day})
        F["rel"] = (mm - OLD_LAG) / 1000.0 - F.start_ts.to_numpy()
        F["rel_dec"] = (m0 - OLD_LAG) / 1000.0 - F.start_ts.to_numpy()
        for k, v in feats.items():
            F[k] = v
        for c in CSCAN:
            F[f"k{c}"] = knee[c]
        # ---- secondary venues (exchange ms, cut at X)
        ven = {}
        for nm, fn in (("bf_btc", f"{C}/fut/{d0}.parquet"), ("bf_eth", f"{C}/venues/ethfut/{d0}.parquet"), ("ok_btc", f"{C}/venues/okx/{d0}.parquet")):
            if os.path.exists(fn):
                o = pd.read_parquet(fn, columns=["T", "p"]).sort_values("T", kind="stable")
                ven[nm] = (o["T"].to_numpy(np.int64), o.p.to_numpy(float), "left")
        for nm, fn in (("by_btc", f"{C}/bybit_ob/linear_{d0}.parquet"), ("by_eth", f"{C}/bybit_ob/linear_ETHUSDT_{d0}.parquet")):
            if os.path.exists(fn):
                o = pd.read_parquet(fn, columns=["b", "bid", "ask", "bq", "aq"]).sort_values("b")
                ven[nm] = ((o.b.to_numpy(np.int64) + 1) * 100, ((o.bid * o.aq + o.ask * o.bq) / (o.bq + o.aq)).to_numpy(float), "right")
        for nm, (T_, X_, how) in ven.items():
            for tag, base in (("own", mm), ("dec", m0), ("plm", mm - PL), ("plp", mm + PL)):
                for K, v in rets(T_, X_, base - C_EX, how).items():
                    F[f"{tag}_{nm}_{K}"] = v
        del ven; gc.collect()
        # ---- market-only (Polymarket non-operator trades, server clock cut at m - 180) for own and dec anchors
        for tag, base in (("own", mm), ("dec", m0)):
            cut = base - OLD_LAG
            lp, d5, d30, f1, f5 = (np.full(n, np.nan, np.float32) for _ in range(5))
            for cid, g in F.groupby("cid"):
                if cid not in pmS:
                    continue
                Tq, P, CS = pmS[cid]; ii = g.index.to_numpy(); cc = cut[ii]
                x0 = at(Tq, P, cc); lp[ii] = x0
                d5[ii] = x0 - at(Tq, P, cc - 500); d30[ii] = x0 - at(Tq, P, cc - 3000)
                c0 = at(Tq, CS, cc); f1[ii] = c0 - at(Tq, CS, cc - 1000); f5[ii] = c0 - at(Tq, CS, cc - 5000)
            F[f"{tag}_pm_last"] = lp; F[f"{tag}_pm_d500"] = d5; F[f"{tag}_pm_d3000"] = d30; F[f"{tag}_pm_f1"] = f1; F[f"{tag}_pm_f5"] = f5
            F[f"{tag}_pm_dist"] = np.abs(lp - 0.5)
        # ---- own-inventory baseline: operator net (Up - Down BUY shares, all three wallets) from fills with block ts <= m/1000 - 2
        fw = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400) & (fl.side == "BUY")]
        own = np.zeros(n, np.float32)
        for cid, g in F.groupby("cid"):
            h = fw[fw.cid == cid]
            if not len(h):
                continue
            ts = h.ts.to_numpy(float); sg = np.where(h.is_up.to_numpy(int) == 1, 1.0, -1.0) * h.shares.to_numpy(float)
            o = np.argsort(ts); ts, cs = ts[o], np.cumsum(sg[o])
            ii = g.index.to_numpy(); j = np.searchsorted(ts, g.m.to_numpy() / 1000.0 - 2.0, "right") - 1
            own[ii] = np.where(j >= 0, cs[np.clip(j, 0, len(cs) - 1)], 0.0)
        F["own_net"] = own
        parts.append(F)
        cb = cb.reset_index(drop=True)
        for c in CSCAN:
            cb[f"k{c}"] = cknee[c]
        crowd_parts.append(cb[["mc", "cid", "up", "day"] + [f"k{c}" for c in CSCAN]])
        print(day, len(F), n_all, len(cb), round(time.time() - t0), flush=True)
        del tr, f, F, cb; gc.collect()
    X = pd.concat(parts, ignore_index=True); del parts
    CB = pd.concat(crowd_parts, ignore_index=True); del crowd_parts
    X.to_parquet(f"{OUT}/dcclock14_frame.parquet", index=False)
    CB.to_parquet(f"{OUT}/dcclock14_crowd.parquet", index=False)
    print("frame", X.shape, CB.shape, round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
