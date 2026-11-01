"""Iteration 13 (X113 step 3, descriptive): how much SIDE information sits at the decision clock vs the block clock on one VALIDATE
day. Per operator taker order with an archive match ms m (dc13 conventions), decision instant a = m - 180 ms (arrival m - 150,
posting latency 30 ms). Up-signed returns over [a - K, a) for K in 0.25..5 s of: Binance USD-M last trade (exchange clock +
the archive's spot transit), Binance spot book microprice and mid (archive receive clock), Chainlink RTDS (server clock), and
the order's own-outcome Polymarket ask (server clock). The same series at the BLOCK clock (block ts - 2 s; what a block-clock rule
sees). Reports sign agreement with the order's outcome and coverage. Usage: python dcfeat13.py DAY ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
KS = (250, 500, 1000, 2000, 3000, 5000)


def at(T, X, tt):
    i = np.searchsorted(T, tt, "right") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float); o[i < 0] = np.nan
    return o


def main():
    day, A = sys.argv[1], sys.argv[2]
    d0 = int(pd.Timestamp(day, tz="UTC").timestamp()); assert d0 + 86400 <= H
    tr = pd.read_parquet(f"{A}/pm_trades_{day}.parquet", columns=["exchangeTimestampMs", "transactionHash"])
    mt = tr.assign(h=tr.transactionHash.str.lower()).groupby("h").exchangeTimestampMs.min(); del tr
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["tx", "ts", "wallet", "role", "start_ts", "token", "is_up", "shares", "oh"])
    fl = fl[(fl.start_ts >= d0) & (fl.start_ts < d0 + 86400)]
    tot = fl.groupby("oh").shares.sum()
    f = fl[fl.role == "T"].drop_duplicates(["tx", "wallet", "token"]).copy()
    f["osz"] = tot.reindex(f.oh).to_numpy()
    f["m"] = f.tx.str.lower().map(mt)
    f = f[f.m.notna()].reset_index(drop=True)
    a = f.m.to_numpy(np.int64) - 180
    blk = (f.ts.to_numpy(np.int64) - 2) * 1000  # block clock: information up to block ts - 2 s
    up = f.is_up.to_numpy(bool)
    b = pd.read_parquet(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "exchangeTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity", "price", "serverTimestampMs"])
    bk = b[b.type == "book"].sort_values("receivedTimestampMs", kind="stable")
    tb = b[b.type == "trade"].sort_values("receivedTimestampMs", kind="stable")
    tk = b[b.type == "ticker"].sort_values("serverTimestampMs", kind="stable")
    transit = float(np.median(tb.receivedTimestampMs - tb.exchangeTimestampMs))
    S = {}
    S["spot_micro"] = (bk.receivedTimestampMs.to_numpy(np.int64), ((bk.bidPrice * bk.askQuantity + bk.askPrice * bk.bidQuantity) / (bk.bidQuantity + bk.askQuantity)).to_numpy(float))
    S["spot_mid"] = (bk.receivedTimestampMs.to_numpy(np.int64), ((bk.bidPrice + bk.askPrice) / 2).to_numpy(float))
    S["spot_trade"] = (tb.receivedTimestampMs.to_numpy(np.int64), tb.price.to_numpy(float))
    S["chainlink_rtds"] = (tk.serverTimestampMs.to_numpy(np.int64), tk.price.to_numpy(float))
    del b, bk, tb, tk
    fu = pd.read_parquet(f"{C}/fut/{d0}.parquet").sort_values("T", kind="stable")
    S["fut_trade"] = (fu["T"].to_numpy(np.int64) + int(round(transit)), fu.p.to_numpy(float))
    del fu
    res = {"day": day, "orders": int(len(f)), "transit_ms": transit, "decision": {}, "block": {}}
    for clk, t0 in (("decision", a), ("block", blk)):
        for nm, (T_, X_) in S.items():
            o = {}
            for K in KS:
                r = (at(T_, X_, t0) / at(T_, X_, t0 - K) - 1) * 1e4
                nz = np.isfinite(r) & (np.abs(r) > 1e-9)
                o[K] = [round(float(((r[nz] > 0) == up[nz]).mean()), 4) if nz.any() else None, round(float(nz.mean()), 4)]
            res[clk][nm] = o
    # Polymarket own-outcome ask change (server clock) over [a - K, a)
    tc = pd.read_parquet(f"{A}/pm_touch_{day}.parquet"); tc["tokenId"] = tc.tokenId.astype(str)
    tok = f.token.astype(str).to_numpy()
    for clk, t0 in (("decision", a), ("block", blk)):
        o = {}
        for K in (500, 1000, 3000):
            d = np.full(len(f), np.nan)
            for t_, g in tc.groupby("tokenId"):
                sel = np.where(tok == t_)[0]
                if not len(sel):
                    continue
                T_, X_ = g.exchangeTimestampMs.to_numpy(np.int64), g.bestAsk.to_numpy(float)
                d[sel] = at(T_, X_, t0[sel]) - at(T_, X_, t0[sel] - K)
            nz = np.isfinite(d) & (np.abs(d) > 1e-9)
            o[K] = {"own_ask_rose_share": round(float((d[nz] > 0).mean()), 4) if nz.any() else None, "nonzero": round(float(nz.mean()), 4)}
        res[clk]["pm_own_ask"] = o
    # by size on the decision clock, fut 1 s
    T_, X_ = S["fut_trade"]
    r = (at(T_, X_, a) / at(T_, X_, a - 1000) - 1) * 1e4; nz = np.isfinite(r) & (np.abs(r) > 1e-9)
    lg = f.osz.to_numpy() >= 45
    res["fut_1s_decision_by_size"] = {"large": round(float(((r[nz & lg] > 0) == up[nz & lg]).mean()), 4), "small": round(float(((r[nz & ~lg] > 0) == up[nz & ~lg]).mean()), 4)}
    json.dump(res, open(f"{R}/dcfeat13_{day}.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
