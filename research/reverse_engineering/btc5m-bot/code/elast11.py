"""Iteration 11 (X92 step 4): elasticity of the COMPLETE live decision record (won races at match - 150, located lost races at
insertion - 150; any wallet) per (window, minute) to the minute's Binance USD-M BTC price-level events and realized vol, with
the trailing 30-min vol, 10-31 14:55-17:55 (development). A bp-threshold trigger predicts an elasticity ~1 to the count of
price-level ticks; a normalizer or a pacing rule ~0. Poisson GLM with window-clustered errors; var / mean of decisions per
minute (pacing predicts < 1).
Usage: python elast11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
import statsmodels.api as sm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, gate8, evt10

C = L.C
A, B = 1793458500, 1793469300


def r4(x):
    return round(float(x), 4)


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    x = evt10.l1("btc5m_venues2", A - 1830, B, "bf")
    T = x[:, 0].astype(np.int64); mic = (x[:, 1] * x[:, 4] + x[:, 3] * x[:, 2]) / np.maximum(x[:, 2] + x[:, 4], 1e-12)
    lr = np.r_[0.0, np.diff(np.log(mic)) * 1e4]; cs2 = np.cumsum(lr ** 2)
    ev = evt10.events(x); aT = ev.tau.to_numpy(np.int64); aP = (ev.cls == "PRICE").to_numpy(); aB = ev.bp.abs().to_numpy()
    d = live6.own_taker(stale9.OWN, A - 5, B + 5)
    tok, books, trades = L.load_books(A - 5, B + 5)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["m"] = tk.tx.map(mt); tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    dec = pd.concat([pd.DataFrame({"st": tk.start.astype(int), "a": tk.m.astype(np.int64) - 150}),
                     pd.DataFrame({"st": lost.mstart.astype(int), "a": lost.s_ins.astype(np.int64) - 150})])
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    rows = []
    for st in range((A // 300 + 1) * 300, B - 299, 300):
        if st < A:
            continue
        ds = np.sort(dec[dec.st == st].a.to_numpy(np.int64))
        rg = R[R.m == st]
        if not len(rg):
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float)
        for k in range(5):
            t0 = (st + 60 * k) * 1000; t1 = t0 + 60000
            j0, j1 = np.searchsorted(T, t0) - 1, np.searchsorted(T, t1) - 1; j30 = np.searchsorted(T, t0 - 1800000) - 1
            rvm = (cs2[j1] - cs2[max(j0, 0)]) / 60; rv30 = (cs2[max(j0, 0)] - cs2[max(j30, 0)]) / 1800
            sel = (aT >= t0) & (aT < t1)
            ts = np.arange(t0, t1, 1000); ii = np.searchsorted(rs, ts, "right") - 1
            v = np.where(ii >= 0, ba[np.clip(ii, 0, None)], np.nan); inr = float(np.nanmean((v > 0.12) & (v < 0.88)))
            rows.append((st, k, int(((ds >= t0) & (ds < t1)).sum()), int(aP[sel].sum()), int(sel.sum()), float((aB[sel] >= 0.2).sum()), rvm, rv30, inr))
    df = pd.DataFrame(rows, columns=["st", "k", "nd", "npr", "nall", "nbig", "rvm", "rv30", "inr"])
    df = df[(df.inr > 0.5) & (df.rvm > 0) & (df.rv30 > 0)].reset_index(drop=True)
    res = {"cells": int(len(df)), "windows": int(df.st.nunique()), "mean_dec_per_min": r4(df.nd.mean()), "var_over_mean": r4(df.nd.var() / df.nd.mean())}
    X = pd.DataFrame({"l_npr": np.log1p(df.npr), "l_rvm": np.log(df.rvm), "l_rv30": np.log(df.rv30), "inr": df.inr, "k0": (df.k == 0).astype(float), "k4": (df.k == 4).astype(float)})
    for spec, cols in (("npr+rvm+rv30", ["l_npr", "l_rvm", "l_rv30", "inr", "k0", "k4"]), ("rvm+rv30", ["l_rvm", "l_rv30", "inr", "k0", "k4"]), ("npr only", ["l_npr", "inr", "k0", "k4"])):
        try:
            m = sm.GLM(df.nd, sm.add_constant(X[cols]), family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": df.st})
            res[f"poisson {spec}"] = {c: [r4(m.params[c]), r4(m.bse[c])] for c in cols if not c.startswith("k")}
        except Exception as ex:
            res[f"poisson {spec}"] = repr(ex)
    # within-window: demeaned log counts (window fixed effect)
    g = df.groupby("st")
    dd = pd.DataFrame({"y": np.log1p(df.nd) - g.nd.transform(lambda v: np.log1p(v).mean()), "x": np.log1p(df.npr) - g.npr.transform(lambda v: np.log1p(v).mean()),
                       "v": np.log(df.rvm) - g.rvm.transform(lambda v: np.log(v).mean())})
    mm = sm.OLS(dd.y, sm.add_constant(dd[["x", "v"]])).fit(cov_type="cluster", cov_kwds={"groups": df.st})
    res["within_window_OLS log1p(dec) on log1p(PRICE events), log rv_min"] = {c: [r4(mm.params[c]), r4(mm.bse[c])] for c in ("x", "v")}
    res["corr(nd, npr)"] = r4(np.corrcoef(df.nd, df.npr)[0, 1]); res["corr(nd, nbig)"] = r4(np.corrcoef(df.nd, df.nbig)[0, 1])
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
