"""Iteration 13 (X113 = information panel P1, steps 1-3 on one VALIDATE day): the SIDE at the DECISION CLOCK on VALIDATE from the
public HF capture Fahri-5/updown-5m-polymarket-raw (revision f848a77c, CC0): per operator taker order (fills role T, one per
(tx, wallet, token)), the matching-engine ms m = the archive trade's exchangeTimestampMs for the order's tx hash; the vote of
the Binance series over the frozen window [m - 600, m - 100) and the PIT-clean window [m - 650, m - 180) (iteration 10);
series: Binance spot BTCUSDT bookTicker microprice (archive, collector receive clock) and Binance USD-M BTCUSDT aggTrades last
price (data.binance.vision, exchange clock + the median spot transit measured on the archive's spot trades). A series votes when
|move| > 0.002 bp (frozen LIVE_TICK_BP). Full coverage = the iteration-8 frozen fallbacks on the archive touch of each token
(ask rose over [m - 600, m - 100) -> that outcome; else ask fell over [m - 3000, m - 100) -> that outcome; else the underdog at
m - 100). Compared on the same orders with the block-clock side model ps. Usage: python dc13.py DAY ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
TICK = 0.002
WINS = {"frozen_600_100": (600, 100), "pit_650_180": (650, 180)}


def at(T, X, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def main():
    day, A = sys.argv[1], sys.argv[2]
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp()); assert d0 + 86400 <= H
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min()
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "ts", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh", "rel", "cid"])
    fl = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400)]
    tot = fl.groupby("oh").shares.sum()
    f = fl[fl.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    f["osz"] = tot.reindex(f.oh).to_numpy()
    f["m"] = f.tx.str.lower().map(mt)
    res = {"day": day, "taker_orders": int(len(f)), "with_archive_ms": round(float(f.m.notna().mean()), 4)}
    f = f[f.m.notna()].sort_values("m").reset_index(drop=True)
    m = f.m.to_numpy(np.int64); up = f.is_up.to_numpy(bool)
    # Binance spot bookTicker from the archive (receive clock) and the spot transit from its trades
    b = pd.read_parquet(f"{A}/btc_{day}.parquet")
    res["btc_types"] = {str(k): int(v) for k, v in b.type.value_counts().items()}
    res["btc_symbols"] = {str(k): int(v) for k, v in b.symbol.value_counts().head(5).items()}
    bt = b[b.bidPrice.notna() & b.askPrice.notna() & b.bidQuantity.notna()].sort_values("receivedTimestampMs", kind="stable")
    tb = b[b.price.notna() & b.exchangeTimestampMs.notna()]
    transit = float(np.median(tb.receivedTimestampMs - tb.exchangeTimestampMs)) if len(tb) else 120.0
    res["spot_transit_ms_median"] = transit
    Tbs = bt.receivedTimestampMs.to_numpy(np.int64)
    mic = ((bt.bidPrice * bt.askQuantity + bt.askPrice * bt.bidQuantity) / (bt.bidQuantity + bt.askQuantity)).to_numpy(float)
    fu = pd.read_parquet(f"{C}/fut/{d0}.parquet").sort_values("T", kind="stable")
    Tbf = (fu["T"].to_numpy(np.int64) + int(round(transit))); pbf = fu.p.to_numpy(float)
    series = {"bs_book": (Tbs, mic), "bf_trade": (Tbf, pbf)}
    del b
    # Polymarket touch of every token (server clock)
    tc = pd.read_parquet(f"{A}/pm_touch_{day}.parquet")
    tc["tokenId"] = tc.tokenId.astype(str)
    touch = {k: (g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float)) for k, g in tc.groupby("tokenId")}
    win = pd.read_parquet(f"{C}/windows.parquet")
    win = win[(win.start_ts >= d0) & (win.start_ts < d0 + 86400)]
    comp = {}
    for r in win.itertuples():
        comp[str(r.up_token)] = str(r.down_token); comp[str(r.down_token)] = str(r.up_token)
    tok = f.token.astype(str).to_numpy()
    own_tok = tok; oth_tok = np.array([comp.get(t, "") for t in tok])
    def ask_at(tokens, tt):
        out = np.full(len(tt), np.nan)
        for t_ in np.unique(tokens):
            if t_ not in touch:
                continue
            sel = np.where(tokens == t_)[0]
            T_, A_ = touch[t_]
            out[sel] = at(T_, A_, tt[sel])
        return out
    # outcome-signed: positive = toward the order's own outcome? No: votes are Up-signed; the order's truth is up.
    rng = np.random.default_rng(13)
    pl = m + (rng.choice([-1, 1], len(m)) * rng.uniform(5000, 60000, len(m))).astype(np.int64)
    out = {}
    is_up_tok = up  # the order's own token is Up iff is_up
    for wn, (w0, w1) in WINS.items():
        V, Vp = np.zeros(len(m)), np.zeros(len(m)); cov = np.zeros(len(m), bool); per = {}
        for nm, (T_, X_) in series.items():
            def mv(tt):
                a0, a1 = at(T_, X_, tt - w0), at(T_, X_, tt - w1)
                r = (a1 / a0 - 1) * 1e4
                r[(tt < T_[0] + 3000) | (tt > T_[-1] - 500)] = np.nan
                return r
            q, qp = mv(m), mv(pl)
            cov |= np.isfinite(q)
            v = np.nan_to_num(np.sign(q) * (np.abs(q) > TICK)); vp = np.nan_to_num(np.sign(qp) * (np.abs(qp) > TICK))
            V += v; Vp += vp
            k1 = v != 0
            per[nm] = {"voted": round(float(k1.mean()), 4), "agree": round(float(((v[k1] > 0) == up[k1]).mean()), 4) if k1.any() else None}
        k = cov & (V != 0); kp = cov & (Vp != 0)
        ok = (V > 0) == up
        o = {"per_series": per, "cover": round(float(k.mean()), 4), "agree_on_voted": round(float(ok[k].mean()), 4),
             "placebo_cover": round(float(kp.mean()), 4), "placebo_agree": round(float(((Vp[kp] > 0) == up[kp]).mean()), 4)}
        # full coverage with the frozen Polymarket-touch fallbacks (Up-signed predictions)
        pred = np.where(k, np.sign(V), 0.0)
        src = np.where(pred != 0, 0, -1)
        upt = np.where(is_up_tok, own_tok, oth_tok); dnt = np.where(is_up_tok, oth_tok, own_tok)
        aU1, aU6, aU30 = ask_at(upt, m - 100), ask_at(upt, m - 600), ask_at(upt, m - 3000)
        aD1, aD6, aD30 = ask_at(dnt, m - 100), ask_at(dnt, m - 600), ask_at(dnt, m - 3000)
        dU6, dD6, dU30, dD30 = aU1 - aU6, aD1 - aD6, aU1 - aU30, aD1 - aD30
        rose = np.where((dU6 > 0.005) & ~(dD6 > 0.005), 1.0, np.where((dD6 > 0.005) & ~(dU6 > 0.005), -1.0, 0.0))
        kk = (pred == 0) & (rose != 0); pred[kk] = rose[kk]; src[kk] = 1
        fell = np.where((dU30 < -0.005) & ~(dD30 < -0.005), 1.0, np.where((dD30 < -0.005) & ~(dU30 < -0.005), -1.0, 0.0))
        kk = (pred == 0) & (fell != 0); pred[kk] = fell[kk]; src[kk] = 2
        kk = (pred == 0) & np.isfinite(aU1); pred[kk] = np.where(aU1[kk] < 0.5, 1.0, -1.0); src[kk] = 3
        okf = (pred > 0) == up; cv = pred != 0
        o["full_coverage"] = {"covered": round(float(cv.mean()), 4), "accuracy": round(float(okf[cv].mean()), 4),
                              "by_source": {nm: [round(float(okf[src == i].mean()), 4) if (src == i).any() else None, int((src == i).sum())]
                                            for i, nm in enumerate(("vote", "pm_ask_rose_600", "pm_ask_fell_3000", "underdog"))},
                              "by_wallet": {w: round(float(okf[cv & (f.wallet.to_numpy() == w)].mean()), 4) for w in ("DS", "GF", "XM")}}
        lg = (f.osz.to_numpy() >= 45)
        o["voted_by_size"] = {"large": round(float(ok[k & lg].mean()), 4) if (k & lg).any() else None, "small": round(float(ok[k & ~lg].mean()), 4)}
        o["by_wallet_voted"] = {w: [round(float(ok[k & (f.wallet.to_numpy() == w)].mean()), 4), int((k & (f.wallet.to_numpy() == w)).sum())] for w in ("DS", "GF", "XM")}
        out[wn] = o
    # block-clock side model on the same orders (one-sided seconds only) and per-order block-clock accuracy
    sd = pd.read_parquet(f"{C}/val_side_it5book.parquet", columns=["cid", "rel", "ps"])
    f["relb"] = (f.ts - f.start_ts).astype(np.int64)
    j = f.merge(sd, left_on=["cid", "relb"], right_on=["cid", "rel"], how="left")
    has = j.ps.notna().to_numpy()
    okb = (j.ps.to_numpy() > 0.5) == up
    res["block_clock_ps_on_same_orders"] = {"coverage": round(float(has.mean()), 4), "accuracy": round(float(okb[has].mean()), 4)}
    for wn in WINS:
        # combined: vote where voted, else the block-clock ps where available, else the touch fallbacks
        o = out[wn]
    res["windows"] = out
    json.dump(res, open(f"{R}/dc13_{day}.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
