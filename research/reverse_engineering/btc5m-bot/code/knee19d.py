"""Iteration 19, X191 step 2 support (pre-registration 16d, written 11-01 ~13:50 UTC before this run): the CLOCK-FREE version of
pre-registration 16b's statistic, for the US-DST natural experiment (pre-registration 20 in NOTES.md), checked on the capture days.
Events: Binance spot LAST-TRADE-PRICE jumps on the exchange clock T only (10-ms grid of the last trade price; |100-ms log return| > 3
sigma of the trailing 60-s 100-ms returns; 300-ms refractory; isolated = no |z| > 2 in the 2 s before and <= 3 such grid points in the
last 300 ms). Decisions: operator first legs at the capture's server-ms match m0 (the live lab's CLOB trade server ms out of sample).
E = excess (same - opposite side) first legs in [0, 230) ms over the excess in [230, 320) ms. Cells as knee19b plus UTC hour on open
weekdays. If E separates the Globex sessions here as the book version does (open > closed, break < neighbours), the DST test can run on
data.binance.vision aggTrades (T-stamped) with no laptop clock.
Usage: python knee19d.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knee19b import at, cell, events

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
LAGS = np.arange(-500, 1000, 10)


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["up", "m0", "rank", "day", "wallet"])
    P = P[(P["rank"] == 0) & P.wallet.isin(["DS", "GF", "XM"])].reset_index(drop=True)
    M = P.m0.to_numpy(np.int64); Y = np.where(P.up.to_numpy() == 1, 1, -1)
    rows = []
    hist = {}
    for day in sorted(P.day.unique()):
        t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "exchangeTimestampMs", "price"], filters=[("type", "=", "trade")])
        T = t.column("exchangeTimestampMs").to_numpy(zero_copy_only=False).astype(np.int64); p = t.column("price").to_numpy(zero_copy_only=False).astype(float)
        o = np.argsort(T, kind="stable"); T, p = T[o], p[o]
        del t; gc.collect()
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp()) * 1000
        for h0 in range(0, 24, 6):
            lo, hi = d0 + h0 * 3600000, d0 + (h0 + 6) * 3600000
            te, se, iso = events(T, p, lo - 60000, hi)
            k_ = (te >= lo) & (iso == 1); te, se = te[k_], se[k_]
            ce = cell(te); hh = pd.to_datetime(te, unit="ms", utc=True).hour.to_numpy()
            sel = np.where((M >= lo - 1000) & (M < hi + 1000))[0]
            o2 = np.argsort(M[sel], kind="stable"); ms_, ys_ = M[sel][o2], Y[sel][o2]
            a = np.searchsorted(ms_, te - 500, "left"); b = np.searchsorted(ms_, te + 1000, "left")
            for k in range(len(te)):
                lag = ms_[a[k]:b[k]] - te[k]; sg = np.where(ys_[a[k]:b[k]] == se[k], 1.0, -1.0)
                rows.append((te[k], ce[k], hh[k], sg[(lag >= 0) & (lag < 230)].sum(), sg[(lag >= 230) & (lag < 320)].sum()))
                h = hist.setdefault(ce[k], np.zeros(len(LAGS)))
                np.add.at(h, ((lag + 500) // 10).astype(int), sg)
        del T, p; gc.collect()
        print(day, len(rows), flush=True)
    E = pd.DataFrame(rows, columns=["t", "cell", "hour", "early", "peak"])
    E["open"] = ~E.cell.isin(["closed_weekend", "break_21"])
    def ratio(d):
        return round(float(d.early.sum() / d.peak.sum()), 3) if d.peak.sum() > 0 else None
    res = {"prereg": "16d", "isolated_trade_events": int(len(E)), "cells": {c: {"events": int((E.cell == c).sum()), "E": ratio(E[E.cell == c])} for c in sorted(E.cell.unique())},
           "E_open": ratio(E[E.open]), "E_closed": ratio(E[~E.open])}
    res["peak_lag_ms"] = {c: int(LAGS[int(np.argmax(np.convolve(h, np.ones(3) / 3, "same")))]) for c, h in hist.items()}
    blks = (E.t // 1800000).to_numpy(); ub = np.unique(blks); bi = {u: np.where(blks == u)[0] for u in ub}
    rng = np.random.default_rng(16)
    op_ = E.open.to_numpy(); br = (E.cell == "break_21").to_numpy(); nb = E.cell.isin(["pre_break_20", "post_break_22"]).to_numpy()
    ea, pk = E.early.to_numpy(), E.peak.to_numpy()
    def st(ix):
        f = lambda m: ea[ix][m[ix]].sum() / max(pk[ix][m[ix]].sum(), 1e-9)
        return f(op_) - f(~op_), f(nb) - f(br)
    b0 = st(np.arange(len(E))); bs = np.array([st(np.concatenate([bi[u] for u in rng.choice(ub, len(ub))])) for _ in range(1000)])
    res["open_minus_closed"] = [round(b0[0], 3), round(float(np.percentile(bs[:, 0], 2.5)), 3), round(float(np.percentile(bs[:, 0], 97.5)), 3), float((bs[:, 0] <= 0).mean())]
    res["neighbours_minus_break"] = [round(b0[1], 3), round(float(np.percentile(bs[:, 1], 2.5)), 3), round(float(np.percentile(bs[:, 1], 97.5)), 3), float((bs[:, 1] <= 0).mean())]
    res["E_by_utc_hour_open_weekdays"] = {int(h): ratio(E[(E.hour == h) & E.open]) for h in range(24)}
    res["E_by_utc_hour_closed"] = {int(h): ratio(E[(E.hour == h) & ~E.open]) for h in range(24)}
    print(json.dumps(res, indent=0), flush=True)
    json.dump(res, open(f"{R}/knee19d.json", "w"), indent=1)


if __name__ == "__main__":
    main()
