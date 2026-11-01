"""Iteration 13 (X113 step 3; PRE-REGISTERED in NOTES.md before scoring): a DECISION-CLOCK side model on VALIDATE from the public
HF capture (revision f848a77c). Unit: operator taker order (fills role T, one per (tx, wallet, token)) with an archive match ms
m; decision instant a = m - 180 ms. Features, all PIT at a (Up-signed returns over [a - K, a), K = 100 / 250 / 500 / 1000 / 2000
ms): Binance spot book microprice and mid (archive, collector receive clock); Bybit BTC and ETH perp microprice (100-ms bins, bin
end + 150 ms); Binance USD-M BTC and ETH last trade and OKX BTC-USDT-SWAP last trade (exchange ms + 131 ms); Polymarket state
(archive touch, server clock): Up / Down asks at a, their changes over 500 / 3000 ms, rel, |Up ask - 0.5|. Model: LightGBM binary
fitted on 10-17..19 orders, scored on 10-20..22 (and the reverse, reported). Baselines on the same orders: the Polymarket-only
model (market-only), the block-clock side model ps where it exists (one-sided seconds). Success = full-coverage accuracy >= 80%
on 10-20..22. Usage: python dcside13.py ARCHIVE_DIR"""
import os, sys, json, time, gc
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd, lightgbm as lgb
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
DAYS = os.environ.get("DC_DAYS", "2026-10-17,2026-10-18,2026-10-19,2026-10-20,2026-10-21,2026-10-22").split(",")
FIT_DAYS = os.environ.get("DC_FIT", "2026-10-17,2026-10-18,2026-10-19").split(",")  # pre-registered split; any other split is a disclosed deviation
KS = (100, 250, 500, 1000, 2000)
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
              bagging_freq=1, max_bin=63, lambda_l2=10.0, verbose=-1, num_threads=4, seed=13)
ROUNDS = 300


def at(T, X, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float); o[i < 0] = np.nan
    return o


def day_frame(day, A, fl, win):
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min(); del tr
    f = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400) & (fl.role == "T")].drop_duplicates(["tx", "wallet", "token"]).copy()
    f["m"] = f.tx.str.lower().map(mt)
    n_all = len(f)
    f = f[f.m.notna()].reset_index(drop=True)
    a = f.m.to_numpy(np.int64) - 180
    F = pd.DataFrame({"cid": f.cid.to_numpy(), "wallet": f.wallet.to_numpy(), "up": f.is_up.to_numpy(int), "relb": (f.ts - f.start_ts).to_numpy(np.int64),
                      "osz": f.osz.to_numpy(), "day": day})
    F["rel"] = a / 1000.0 - f.start_ts.to_numpy()
    S = {}
    EXTRA = os.environ.get("DC_EXTRA") == "1"  # secondary (not pre-registered): signed aggressive flow and book imbalance
    b = pd.read_parquet(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"] + (["quantity", "isBuyerMaker"] if EXTRA else []))
    if EXTRA:
        tb = b[b.type == "trade"].sort_values("receivedTimestampMs", kind="stable")
        Tt = tb.receivedTimestampMs.to_numpy(np.int64); cs = np.cumsum(np.where(tb.isBuyerMaker.astype(bool).to_numpy(), -1.0, 1.0) * tb.quantity.to_numpy(float))
        for K in (100, 250, 500, 1000):
            F[f"xs_flow_{K}"] = (at(Tt, cs, a) - at(Tt, cs, a - K)).astype(np.float32)
        del tb
    b = b[b.type == "book"].sort_values("receivedTimestampMs", kind="stable")
    if EXTRA:
        Tq = b.receivedTimestampMs.to_numpy(np.int64); imb = ((b.bidQuantity - b.askQuantity) / (b.bidQuantity + b.askQuantity)).to_numpy(float)
        F["xs_imb_0"] = at(Tq, imb, a).astype(np.float32); F["xs_imb_250"] = at(Tq, imb, a - 250).astype(np.float32)
    Tb = b.receivedTimestampMs.to_numpy(np.int64)
    S["bs_mic"] = (Tb, ((b.bidPrice * b.askQuantity + b.askPrice * b.bidQuantity) / (b.bidQuantity + b.askQuantity)).to_numpy(float))
    S["bs_mid"] = (Tb, ((b.bidPrice + b.askPrice) / 2).to_numpy(float))
    del b; gc.collect()
    for nm, fn in (("by_btc", f"{C}/bybit_ob/linear_{d0}.parquet"), ("by_eth", f"{C}/bybit_ob/linear_ETHUSDT_{d0}.parquet")):
        if os.path.exists(fn):
            o = pd.read_parquet(fn, columns=["b", "bid", "ask", "bq", "aq"]).sort_values("b")
            S[nm] = ((o.b.to_numpy(np.int64) + 1) * 100 + 150, ((o.bid * o.aq + o.ask * o.bq) / (o.bq + o.aq)).to_numpy(float))
    for nm, fn in (("bf_btc", f"{C}/fut/{d0}.parquet"), ("bf_eth", f"{C}/venues/ethfut/{d0}.parquet"), ("ok_btc", f"{C}/venues/okx/{d0}.parquet")):
        if os.path.exists(fn):
            o = pd.read_parquet(fn, columns=["T", "p", "q", "m"] if EXTRA else ["T", "p"]).sort_values("T", kind="stable")
            S[nm] = (o["T"].to_numpy(np.int64) + 131, o.p.to_numpy(float))
            if EXTRA:
                cs = np.cumsum(np.where(o.m.astype(bool).to_numpy(), -1.0, 1.0) * o.q.to_numpy(float)); Tf = o["T"].to_numpy(np.int64) + 131
                for K in (100, 250, 500, 1000):
                    F[f"x{nm}_flow_{K}"] = (at(Tf, cs, a) - at(Tf, cs, a - K)).astype(np.float32)
    sg = np.where(F.up.to_numpy() == 1, 1.0, 1.0)  # features are Up-signed (label = up)
    for nm, (T_, X_) in S.items():
        x0 = at(T_, X_, a)
        for K in KS:
            F[f"{nm}_{K}"] = ((x0 / at(T_, X_, a - K) - 1) * 1e4).astype(np.float32)
    del S; gc.collect()
    touch = {}
    if os.path.exists(f"{A}/pm_touch_{day}.parquet"):  # the trades-only ingest (pmtx) has no touch: Polymarket features are NaN
        tc = pd.read_parquet(f"{A}/pm_touch_{day}.parquet"); tc["tokenId"] = tc.tokenId.astype(str)
        touch = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float)) for k, g in tc.groupby("tokenId")}
    w = win.set_index("cid")
    ut = w.loc[f.cid, "up_token"].astype(str).to_numpy(); dt = w.loc[f.cid, "down_token"].astype(str).to_numpy()
    for side, toks in (("U", ut), ("D", dt)):
        for lag in (0, 500, 3000):
            v = np.full(len(f), np.nan)
            for t_ in np.unique(toks):
                if t_ in touch:
                    sel = np.where(toks == t_)[0]
                    v[sel] = at(touch[t_][0], touch[t_][1], a[sel] - lag)
            F[f"ask{side}_{lag}"] = v.astype(np.float32)
        F[f"dask{side}_500"] = F[f"ask{side}_0"] - F[f"ask{side}_500"]
        F[f"dask{side}_3000"] = F[f"ask{side}_0"] - F[f"ask{side}_3000"]
        F = F.drop(columns=[f"ask{side}_500", f"ask{side}_3000"])
    F["dist"] = (F.askU_0 - 0.5).abs()
    return F, n_all


def main():
    A = sys.argv[1]
    t0 = time.time()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "ts", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh", "cid"])
    fl = fl[(fl.start_ts >= 1792195200) & (fl.start_ts < H)]
    fl["osz"] = fl.groupby("oh").shares.transform("sum")
    win = pd.read_parquet(f"{C}/windows.parquet")
    parts, cover = [], {}
    for day in DAYS:
        F, n_all = day_frame(day, A, fl, win)
        cover[day] = [int(len(F)), int(n_all)]
        parts.append(F); print(day, len(F), n_all, round(time.time() - t0), flush=True)
    X = pd.concat(parts, ignore_index=True); del parts
    X.to_parquet(f"{C}/it13/dcside13_frame{os.environ.get('DC_TAG', '')}.parquet", index=False)
    pm = ["rel", "askU_0", "askD_0", "daskU_500", "daskD_500", "daskU_3000", "daskD_3000", "dist"]
    ven = [c for c in X.columns if any(c.startswith(p) for p in ("bs_", "by_", "bf_", "ok_", "xs_", "xbf_", "xok_"))]
    sd = pd.read_parquet(f"{C}/val_side_it5book.parquet", columns=["cid", "rel", "ps"]).rename(columns={"rel": "relb"})
    X = X.merge(sd, on=["cid", "relb"], how="left")
    res = {"coverage_archive_ms": cover, "n": int(len(X)), "features_venue": ven}
    early = X.day.isin(FIT_DAYS).to_numpy()
    res["fit_days"] = FIT_DAYS; res["days"] = DAYS
    for nm, fm, sm_ in (("fit_A_score_B", early, ~early), ("fit_B_score_A", ~early, early)):
        o = {}
        y = X.up.to_numpy()
        for tag, cols in (("full", pm + ven), ("market_only", pm), ("venue_only", ["rel"] + ven)):
            m = lgb.train(PARAMS, lgb.Dataset(X.loc[fm, cols], y[fm]), num_boost_round=ROUNDS)
            p = m.predict(X.loc[sm_, cols], num_threads=4)
            ok = (p > 0.5).astype(int) == y[sm_]
            o[tag] = {"acc": round(float(ok.mean()), 4), "by_wallet": {w: round(float(ok[X.wallet.to_numpy()[sm_] == w].mean()), 4) for w in ("DS", "GF", "XM")}}
            if tag == "full":
                imp = pd.Series(m.feature_importance("gain"), index=cols).sort_values(ascending=False)
                o["importance_top12"] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(12).items()}
                pf = p
                hp = X.ps.notna().to_numpy()[sm_]
                o["same_orders_with_ps"] = {"n": int(hp.sum()), "dc_full_acc": round(float(ok[hp].mean()), 4),
                                            "block_ps_acc": round(float(((X.ps.to_numpy()[sm_][hp] > 0.5).astype(int) == y[sm_][hp]).mean()), 4)}
                lg = X.osz.to_numpy()[sm_] >= 45
                o["by_size"] = {"large": round(float(ok[lg].mean()), 4), "small": round(float(ok[~lg].mean()), 4)}
                halves = X.day.to_numpy()[sm_]
                o["by_day"] = {d: round(float(ok[halves == d].mean()), 4) for d in np.unique(halves)}
        res[nm] = o
        print(nm, json.dumps(o), flush=True)
    json.dump(res, open(f"{R}/dcside13{os.environ.get('DC_TAG', '')}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
