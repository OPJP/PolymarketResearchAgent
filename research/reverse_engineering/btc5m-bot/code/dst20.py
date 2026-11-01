"""PRE-REGISTRATION 20 runner (iteration 19; NOTES.md 'PRE-REGISTRATION 20'): the US-DST natural experiment for the Globex-hours input
(X191 step 2). Nothing is fitted; the statistic is knee19d's clock-free E.

Steps per development block (11-01 18-24, 11-02 00-06, 11-02 12-18, 11-03 06-12, 11-03 18-24; sealed.intervals decides, never a
sealed block):
  1. build the block's decision record with post17.py:  RE16_SCRATCH=<BLOCK_DIR> python post17.py A_TS B_TS
     (writes <BLOCK_DIR>/it17/post17_windows / _fills / _xms.parquet: windows, on-chain fills of the five operator wallets, the live
     lab's server-ms match per tx);
  2. Binance spot trades on the exchange clock T: '--binance archive' reads data.binance.vision spot aggTrades BTCUSDT daily zips that
     the operator of this script has downloaded into AGG_DIR (BTCUSDT-aggTrades-YYYY-MM-DD.zip with its .CHECKSUM, verified here);
     '--binance live' reads the live lab feed btc5m_bnspot2 instead (only where a recorder ran);
  3. E per cell of the CST calendar (dc_exam14.globex_open_ms): closed / sunday_open / open / break (Mon-Thu 22-23 UTC) / old-break hour
     (Mon-Thu 21-22 UTC, now open), with a 30-min block bootstrap of open - closed and of neighbours - break.
Predictions (H1, a TradFi calendar): E(closed) <= 0.65; E(open) >= 0.85 with open - closed > 0 at the 2.5% bound; E(21-22 UTC) at the
open level; E(22-23 UTC on Mon-Thu) below its neighbours; reaction peak 250-270 ms. H4 (an operator UTC schedule) predicts the low hour
stays at 21-22 UTC.
Usage: python dst20.py --binance archive|live [--agg AGG_DIR] BLOCK_DIR [BLOCK_DIR ...]"""
import os, sys, json, glob, zipfile, hashlib, argparse
import numpy as np, pandas as pd
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, _ROOT + "/research/reverse_engineering/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sealed, live
from knee19b import events
from dc_exam14 import globex_open_ms


def cst_cell(ms):
    ms = np.asarray(ms, np.int64)
    t = pd.to_datetime(ms, unit="ms", utc=True); wd, h = t.day_of_week.to_numpy(), t.hour.to_numpy()
    out = np.where(globex_open_ms(ms), "open", "closed").astype(object)
    out[(wd == 6) & globex_open_ms(ms)] = "sunday_open"
    out[(wd <= 3) & (h == 22)] = "break_22"
    out[(wd <= 3) & (h == 21)] = "old_break_21"
    out[(wd <= 3) & (h == 23)] = "post_break_23"
    return out


def first_legs(bdir):
    S = f"{bdir}/it17"
    win = pd.read_parquet(f"{S}/post17_windows.parquet"); fl = pd.read_parquet(f"{S}/post17_fills.parquet"); xr = pd.read_parquet(f"{S}/post17_xms.parquet")
    assert not any(sealed.is_sealed(int(t), "btc5m-bot") for t in win.start_ts), "sealed window"
    o = fl[(fl.role == "T") & (fl.side == 0) & fl.wallet.isin(["DS", "GF", "XM"])].copy(); o["tx"] = o.tx.str.lower()
    o = o.drop_duplicates(["tx", "wallet", "token"]); o["m"] = o.tx.map(xr.dropna(subset=["s"]).groupby("tx").s.min())
    o = o[o.m.notna()].copy(); o["m"] = o.m.astype(np.int64)
    o = o.sort_values(["cid", "is_up", "m"]); new = (o.cid != o.cid.shift()) | (o.is_up != o.is_up.shift()) | (o.m - o.m.shift() >= 300)
    return o[new], int(win.start_ts.min()), int(win.end_ts.max())


def archive_trades(agg, a_ms, b_ms):
    T, p = [], []
    for d in pd.date_range(pd.to_datetime(a_ms, unit="ms").normalize(), pd.to_datetime(b_ms, unit="ms").normalize(), freq="D"):
        z = f"{agg}/BTCUSDT-aggTrades-{d:%Y-%m-%d}.zip"
        ck = open(z + ".CHECKSUM").read().split()[0]
        assert hashlib.sha256(open(z, "rb").read()).hexdigest() == ck, "checksum mismatch " + z
        with zipfile.ZipFile(z) as zf:
            df = pd.read_csv(zf.open(zf.namelist()[0]), header=None, usecols=[1, 5])
        if not str(df.iloc[0, 0]).replace(".", "").isdigit():
            df = df.iloc[1:]
        tt = df.iloc[:, 1].astype(np.int64).to_numpy()
        if tt.max() > 10 ** 14:  # microseconds in newer archives
            tt = tt // 1000
        k = (tt >= a_ms) & (tt < b_ms); T.append(tt[k]); p.append(df.iloc[:, 0].astype(float).to_numpy()[k])
    T = np.concatenate(T); p = np.concatenate(p); o = np.argsort(T, kind="stable")
    return T[o], p[o]


def live_trades(a_ms, b_ms):
    T, p = [], []
    for r in live.iter_live("btc5m_bnspot2", a_ms // 1000, b_ms // 1000 + 1):
        if r.get("k") == "x":
            T.append(r["T"]); p.append(float(r["p"]))
    T = np.asarray(T, np.int64); o = np.argsort(T, kind="stable")
    return T[o], np.asarray(p)[o]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--binance", choices=["archive", "live"], required=True); ap.add_argument("--agg"); ap.add_argument("blocks", nargs="+")
    a = ap.parse_args()
    rows = []
    for bdir in a.blocks:
        f, st0, st1 = first_legs(bdir)
        a_ms, b_ms = (st0 - 120) * 1000, (st1 + 10) * 1000
        T, p = archive_trades(a.agg, a_ms, b_ms) if a.binance == "archive" else live_trades(a_ms, b_ms)
        te, se, iso = events(T, p, int(T[0]), int(T[-1]))
        k = (te >= int(T[0]) + 61000) & (iso == 1); te, se = te[k], se[k]
        M = f.m.to_numpy(np.int64); Y = np.where(f.is_up.to_numpy(bool), 1, -1); o = np.argsort(M); M, Y = M[o], Y[o]
        lo_ = np.searchsorted(M, te - 500, "left"); hi_ = np.searchsorted(M, te + 1000, "left")
        cells = cst_cell(te)
        for i in range(len(te)):
            lag = M[lo_[i]:hi_[i]] - te[i]; sg = np.where(Y[lo_[i]:hi_[i]] == se[i], 1.0, -1.0)
            rows.append((int(te[i]), cells[i], sg[(lag >= 0) & (lag < 230)].sum(), sg[(lag >= 230) & (lag < 320)].sum()))
        print(bdir, len(f), "first legs,", int(k.sum()), "isolated jumps", flush=True)
    E = pd.DataFrame(rows, columns=["t", "cell", "early", "peak"])
    ratio = lambda d: round(float(d.early.sum() / d.peak.sum()), 3) if d.peak.sum() > 0 else None
    res = {"prereg": "20", "binance": a.binance, "blocks": a.blocks, "cells": {c: {"events": int((E.cell == c).sum()), "E": ratio(E[E.cell == c])} for c in sorted(E.cell.unique())}}
    opn = E.cell.isin(["open", "sunday_open", "old_break_21", "post_break_23"]).to_numpy(); brk = (E.cell == "break_22").to_numpy(); nb = E.cell.isin(["old_break_21", "post_break_23"]).to_numpy()
    blk = (E.t // 1800000).to_numpy(); ub = np.unique(blk); bi = {u: np.where(blk == u)[0] for u in ub}; rng = np.random.default_rng(20)
    ea, pk = E.early.to_numpy(), E.peak.to_numpy()
    def st(ix):
        f_ = lambda m: ea[ix][m[ix]].sum() / max(pk[ix][m[ix]].sum(), 1e-9)
        return f_(opn) - f_(~opn & ~brk), f_(nb) - f_(brk)
    b0 = st(np.arange(len(E))); bs = np.array([st(np.concatenate([bi[u] for u in rng.choice(ub, len(ub))])) for _ in range(2000)])
    res["open_minus_closed"] = [round(b0[0], 3), round(float(np.nanpercentile(bs[:, 0], 2.5)), 3), round(float(np.nanpercentile(bs[:, 0], 97.5)), 3)]
    res["neighbours_minus_break_22"] = [round(b0[1], 3), round(float(np.nanpercentile(bs[:, 1], 2.5)), 3), round(float(np.nanpercentile(bs[:, 1], 97.5)), 3)] if brk.any() else None
    print(json.dumps(res, indent=1))
    json.dump(res, open(_ROOT + "/research/reverse_engineering/btc5m-bot/results/dst20.json", "w"), indent=1)


if __name__ == "__main__":
    main()
