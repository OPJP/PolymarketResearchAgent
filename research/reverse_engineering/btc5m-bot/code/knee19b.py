"""Iteration 19, X191 follow-up (pre-registration 16b, written after knee19's first result and before this run, 11-01 ~13:15 UTC).
knee19 found the reaction peak to Binance spot microprice jumps at +260 ms in every session, with extra same-side mass at 0-230 ms and
negative lags in Globex-open hours only. Two alternative readings remain: (i) an input that leads Binance in open hours; (ii) more
momentum (event clustering) on weekdays, so that a decision triggered by an EARLIER move precedes a continuation jump.
Controls, all fixed here:
(a) ISOLATED events: no |z| > 2 100-ms move of either sign on the spot book in the 2,000 ms before the event (so a decision before the
    event cannot be a reaction to an earlier Binance move);
(b) the CROWD (975,955 non-operator taker BUYs, dcclock14_crowd 'mc') through the same PSTH: momentum would lift the crowd's early mass
    in open hours as well;
(c) the session boundaries that separate CME Globex from a weekday effect: the Mon-Thu break 21:00-22:00 UTC against 20-21 and 22-23,
    and Sunday 10-18 18:00-22:00 (closed) against 22:00-24:00 (open).
Statistic: E = excess (same - opposite side) legs per 1,000 events in [0, 230) ms over the excess in the reaction band [230, 320).
Reading (i) predicts E(open) > E(closed) for isolated events, for the operator only, and E jumps at the Sunday 22:00 open and drops in the
break hour. Usage: python knee19b.py FRAME_DIR HF_DIR"""
import os, sys, json, gc
import numpy as np, pandas as pd, pyarrow.parquet as pq

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
LAGS = np.arange(-500, 1000, 10)
CELLS = ("closed_weekend", "sunday_open", "break_21", "pre_break_20", "post_break_22", "open_other")


def at(T, X, t):
    i = np.searchsorted(T, t, "left") - 1
    o = X[np.clip(i, 0, len(X) - 1)].astype(float)
    o[i < 0] = np.nan
    return o


def cell(ms):
    t = pd.to_datetime(np.asarray(ms, np.int64), unit="ms", utc=True)
    wd, h = t.day_of_week.to_numpy(), t.hour.to_numpy()
    out = np.full(len(ms), "open_other", dtype=object)
    out[(wd <= 3) & (h == 22)] = "post_break_22"
    out[(wd <= 3) & (h == 20)] = "pre_break_20"
    out[(wd <= 3) & (h == 21)] = "break_21"
    out[(wd == 6) & (h >= 22)] = "sunday_open"
    out[(wd == 5) | ((wd == 6) & (h < 22)) | ((wd == 4) & (h >= 21))] = "closed_weekend"
    return out


def events(Tb, mic, lo, hi):
    G = np.arange(lo, hi, 10, dtype=np.int64)
    lm = np.log(at(Tb, mic, G))
    r = np.full(len(G), np.nan); r[10:] = lm[10:] - lm[:-10]
    sd = pd.Series(r[::10]).rolling(600, min_periods=300).std().shift(1).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        z = r / np.repeat(sd, 10)[: len(G)]
    big = np.isfinite(z) & (np.abs(z) > 3.0); mid = np.isfinite(z) & (np.abs(z) > 2.0)
    cand = np.where(big)[0]
    ev, last = [], -10 ** 9
    for i in cand:
        if i - last > 30:
            ev.append(i)
        last = i
    ev = np.asarray(ev, np.int64)
    cm = np.concatenate([[0], np.cumsum(mid)])
    pre = cm[np.clip(ev - 30, 0, None)] - cm[np.clip(ev - 230, 0, None)]  # |z|>2 grid points in [ev-2000ms, ev-300ms)
    pre2 = cm[ev] - cm[np.clip(ev - 30, 0, None)]  # in the 300 ms just before (the event's own run-up)
    iso = (pre == 0) & (pre2 <= 3)
    return G[ev], np.sign(z[ev]).astype(int), iso


def main():
    D, A = sys.argv[1], sys.argv[2]
    P = pd.read_parquet(f"{D}/dcfit14_pred.parquet", columns=["up", "m0", "rank", "day"])
    P = P[P["rank"] == 0].reset_index(drop=True)
    Cw = pd.read_parquet(f"{D}/dcclock14_crowd.parquet", columns=["mc", "up", "day"])
    groups = {"operator": (P.m0.to_numpy(np.int64), np.where(P.up.to_numpy() == 1, 1, -1), P.day.to_numpy()),
              "crowd": (Cw.mc.to_numpy(np.int64), np.where(Cw.up.to_numpy() == 1, 1, -1), Cw.day.to_numpy())}
    acc = {(g, c, iso): {"same": np.zeros(len(LAGS)), "opp": np.zeros(len(LAGS)), "events": 0} for g in groups for c in CELLS for iso in (0, 1)}
    for day in sorted(P.day.unique()):
        d0 = int(pd.Timestamp(day, tz="UTC").timestamp())
        for h0 in range(0, 24, 6):
            lo, hi = (d0 + h0 * 3600) * 1000, (d0 + (h0 + 6) * 3600) * 1000
            t = pq.read_table(f"{A}/btc_{day}.parquet", columns=["type", "receivedTimestampMs", "bidPrice", "bidQuantity", "askPrice", "askQuantity"],
                              filters=[("receivedTimestampMs", ">=", lo - 70000), ("receivedTimestampMs", "<", hi + 2000), ("type", "=", "book")])
            Tb = t.column("receivedTimestampMs").to_numpy() - 131
            bp, bq, ap, aq = (t.column(k).to_numpy(zero_copy_only=False).astype(float) for k in ("bidPrice", "bidQuantity", "askPrice", "askQuantity"))
            mic = (bp * aq + ap * bq) / (bq + aq); o = np.argsort(Tb, kind="stable"); Tb, mic = Tb[o], mic[o]
            del t, bp, bq, ap, aq; gc.collect()
            if len(Tb) < 1000:
                continue
            te, se, iso = events(Tb, mic, lo - 60000, hi)
            k_ = te >= lo; te, se, iso = te[k_], se[k_], iso[k_]
            ce = cell(te)
            for g, (M, Y, Dd) in groups.items():
                sel = np.where((M >= lo - 1000) & (M < hi + 1000))[0]
                o2 = np.argsort(M[sel], kind="stable"); ms_, ys_ = M[sel][o2], Y[sel][o2]
                a = np.searchsorted(ms_, te - 500, "left"); b = np.searchsorted(ms_, te + 1000, "left")
                for c in CELLS:
                    for isv in (0, 1):
                        m_ = (ce == c) & ((iso == 1) if isv else np.ones(len(te), bool))
                        acc[(g, c, isv)]["events"] += int(m_.sum())
                for k in np.where(b > a)[0]:
                    lag = ms_[a[k]:b[k]] - te[k]; yy = ys_[a[k]:b[k]]
                    bi = ((lag + 500) // 10).astype(int)
                    same = yy == se[k]
                    for isv in ((0, 1) if iso[k] else (0,)):
                        d_ = acc[(g, ce[k], isv)]
                        np.add.at(d_["same"], bi[same], 1.0); np.add.at(d_["opp"], bi[~same], 1.0)
            del Tb, mic; gc.collect()
        print(day, flush=True)
    res = {"prereg": "16b", "cells": {}}

    def band(d, a, b):
        m = (LAGS >= a) & (LAGS < b); ne = max(d["events"], 1)
        return float((d["same"][m].sum() - d["opp"][m].sum()) / ne * 1000)
    for (g, c, isv), d in acc.items():
        if d["events"] < 50:
            continue
        pk = band(d, 230, 320); e0 = band(d, 0, 230); en = band(d, -500, 0)
        ex = (d["same"] - d["opp"]) / max(d["events"], 1) * 1000
        sm = np.convolve(ex, np.ones(3) / 3, "same"); kk = int(np.argmax(sm))
        res["cells"][f"{g}|{c}|{'iso' if isv else 'all'}"] = {"events": d["events"], "excess_[-500,0)": round(en, 2), "excess_[0,230)": round(e0, 2),
                                                               "excess_[230,320)": round(pk, 2), "E_early_over_peak": round(e0 / pk, 3) if pk > 0 else None,
                                                               "E_neg_over_peak": round(en / pk, 3) if pk > 0 else None, "peak_lag_ms": int(LAGS[kk])}
    for k, v in res["cells"].items():
        print(k, v, flush=True)
    json.dump(res, open(f"{R}/knee19b.json", "w"), indent=1)


if __name__ == "__main__":
    main()
