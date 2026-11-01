"""Iteration 11 (panel iter10 mechanics P1 = X92, the trigger's NORMALIZER; assumptions P1 = X96, a CONFLATED / CONFIRMED venue
input). One onset table, the evt10 event unit (Binance USD-M BTC bookTicker events that change the microprice, same-sign updates
within 50 ms merged; clean = no cluster decision on the window in [tau - 600, tau + 150); label = a cluster decision on o, taker
match at engine ms or located lost-race insertion, in [tau + 150, tau + 700)). Fit on A (14:55-16:04), scored on C (16:33-17:55).
Added point-in-time (X92):
  z_rv_h = |bp| / realized vol of the bf microprice over [tau - h, tau) (bp per sqrt s), h in {5, 15, 30, 60, 120, 300} s;
  z_ev_h = |bp| / RMS event size over [tau - h, tau);  n_h = events in [tau - h, tau); np_h = PRICE events;
  pct_win = within-window percentile of |bp| among the window's earlier events.
Diagnostic, NOT point-in-time for the bot (X96): survival of the event at tau + D (D = 50 / 100 / 150 / 200 ms): the bf microprice
still moved >= 50% of the event's size in its direction since the pre-event level; OKX / Bybit confirmation over [tau - 100,
tau + D]. P(take | survived) vs P(take | reverted) within |bp| terciles; kernel of (a - tau) for taken events (a = first
decision - 150) in 10-ms bins; rate controller (G2): P(take) by the operator's decisions on the window in [tau - 30 s, tau - 600)
(own state, reported apart). Elasticity (X92 step 4): decisions per (window, minute) on the complete live record vs the
minute's Binance PRICE events and realized vol, with the trailing 30-min vol.
Usage: python onset11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, gate8, evt10
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
HS = (5, 15, 30, 60, 120, 300)
DS_ = (50, 100, 150, 200)


def series(a, b, venue):
    x = evt10.l1("btc5m_venues2", a - 330, b, venue)
    T = x[:, 0].astype(np.int64); mic = (x[:, 1] * x[:, 4] + x[:, 3] * x[:, 2]) / np.maximum(x[:, 2] + x[:, 4], 1e-12)
    return T, mic


def at(T, p, t):
    i = np.searchsorted(T, t, "right") - 1
    out = p[np.clip(i, 0, len(p) - 1)].astype(float); out[i < 0] = np.nan
    return out


def build11(a, b, lost):
    ev = evt10.build(a, b, lost)  # clean events with y, st, rel, ask, unch150, agree, act, rp, cls, bp, sgn, tau
    T, mic = series(a, b, "bf")
    lr = np.r_[0.0, np.diff(np.log(mic)) * 1e4]  # bp per update
    cs2 = np.cumsum(lr ** 2)
    # all-event list of the bf series for n_h / RMS event size / percentile (recompute events on the extended range)
    xx = evt10.l1("btc5m_venues2", a - 330, b, "bf")
    allev = evt10.events(xx)
    aT = allev.tau.to_numpy(np.int64); aB = np.abs(allev.bp.to_numpy()); aP = (allev.cls == "PRICE").to_numpy()
    cB2 = np.cumsum(aB ** 2); cP = np.cumsum(aP)
    tau = ev.tau.to_numpy(np.int64); bp = np.abs(ev.bp.to_numpy()); sg = ev.sgn.to_numpy()
    j1 = np.searchsorted(T, tau, "left") - 1  # last update strictly before tau
    for h in HS:
        j0 = np.searchsorted(T, tau - h * 1000, "left") - 1
        rv = (cs2[np.clip(j1, 0, None)] - cs2[np.clip(j0, 0, None)]) / h
        ev[f"z_rv_{h}"] = bp / np.sqrt(np.maximum(rv, 1e-8))
        k1 = np.searchsorted(aT, tau, "left"); k0 = np.searchsorted(aT, tau - h * 1000, "left")
        n = k1 - k0
        ev[f"n_{h}"] = n
        s2 = np.where(k1 > 0, cB2[np.clip(k1 - 1, 0, None)], 0) - np.where(k0 > 0, cB2[np.clip(k0 - 1, 0, None)], 0)
        ev[f"z_ev_{h}"] = bp / np.sqrt(np.maximum(s2 / np.maximum(n, 1), 1e-8))
        ev[f"np_{h}"] = np.where(k1 > 0, cP[np.clip(k1 - 1, 0, None)], 0) - np.where(k0 > 0, cP[np.clip(k0 - 1, 0, None)], 0)
    # within-window percentile of |bp| among the window's earlier events
    st = ev.st.to_numpy(np.int64)
    pct = np.full(len(ev), np.nan)
    for i in range(len(ev)):
        k0 = np.searchsorted(aT, st[i] * 1000, "left"); k1 = np.searchsorted(aT, tau[i], "left")
        if k1 - k0 >= 5:
            pct[i] = float((aB[k0:k1] < bp[i]).mean())
    ev["pct_win"] = pct
    # survival (diagnostic): bf microprice at tau + D vs the pre-event level
    pre = mic[np.clip(j1, 0, None)]
    for D in DS_:
        m_ = at(T, mic, tau + D)
        mvD = (m_ / pre - 1) * 1e4 * sg
        ev[f"surv_{D}"] = mvD >= 0.5 * bp
        ev[f"mv_{D}"] = mvD
    for v in ("ok", "by"):
        Tv, mv_ = series(a, b, v)
        p0 = at(Tv, mv_, tau - 100)
        for D in DS_:
            pD = at(Tv, mv_, tau + D)
            ev[f"cf_{v}_{D}"] = np.nan_to_num((pD / p0 - 1) * 1e4 * sg) > 0
    # first decision time (for the kernel) and the operator's recent decisions (own state)
    d = live6.own_taker(stale9.OWN, a - 40, b + 5)
    tok, books, trades = L.load_books(a - 40, b + 5)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2]); tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()]
    lo = lost[(lost.s_ins >= (a - 40) * 1000) & (lost.s_ins < (b + 5) * 1000)]
    dec = pd.concat([pd.DataFrame({"st": tk.start.astype(int), "up": tk.is_up.astype(bool), "s": tk.m.astype(np.int64)}),
                     pd.DataFrame({"st": lo.mstart.astype(int), "up": lo.is_up.astype(bool), "s": lo.s_ins.astype(np.int64)})])
    decg = {k: np.sort(g.s.to_numpy(np.int64)) for k, g in dec.groupby(["st", "up"])}
    decw = {k: np.sort(g.s.to_numpy(np.int64)) for k, g in dec.groupby("st")}
    up = sg > 0
    first = np.full(len(ev), np.nan); rec30 = np.zeros(len(ev)); rec60 = np.zeros(len(ev))
    for i in range(len(ev)):
        g = decg.get((int(st[i]), bool(up[i])))
        if g is not None:
            j = np.searchsorted(g, tau[i] + 150)
            if j < len(g) and g[j] < tau[i] + 700:
                first[i] = g[j] - 150 - tau[i]
        gw = decw.get(int(st[i]))
        if gw is not None:
            rec30[i] = np.searchsorted(gw, tau[i] - 600) - np.searchsorted(gw, tau[i] - 30000)
            rec60[i] = np.searchsorted(gw, tau[i] - 600) - np.searchsorted(gw, tau[i] - 60000)
    ev["a_minus_tau"] = first; ev["rec30"] = rec30; ev["rec60"] = rec60
    return ev, dec, (T, mic), allev


def Xm(ev, kind):
    base = evt10.X(ev, "base"); full = evt10.X(ev, "full")
    if kind == "base":
        return base
    if kind == "full":
        return full
    z = np.c_[[np.log(np.clip(ev[f"z_rv_{h}"].to_numpy(float), 1e-3, 1e4)) for h in HS]].T
    ze = np.c_[[np.log(np.clip(ev[f"z_ev_{h}"].to_numpy(float), 1e-3, 1e4)) for h in HS]].T
    n = np.c_[[np.log1p(ev[f"n_{h}"].to_numpy(float)) for h in HS]].T
    npr = np.c_[[np.log1p(ev[f"np_{h}"].to_numpy(float)) for h in HS]].T
    pc = np.nan_to_num(ev.pct_win.to_numpy(float), nan=0.5)
    norm_ = np.c_[z, ze, n, npr, pc, (ev.cls == "PRICE") * pc]
    surv = np.c_[[ev[f"surv_{D}"].to_numpy(float) for D in DS_]].T
    cf = np.c_[[ev[f"cf_{v}_{D}"].to_numpy(float) for v in ("ok", "by") for D in DS_]].T
    if kind == "z_only":  # the normalizer alone: z, n, percentile + class (no raw bp)
        return np.c_[base, ev.cls == "PRICE", ev.cls == "DEPLETE", norm_].astype(float)
    if kind == "full+norm":
        return np.c_[full, norm_].astype(float)
    if kind == "full+surv":
        return np.c_[full, surv, cf].astype(float)
    if kind == "full+norm+surv":
        return np.c_[full, norm_, surv, cf].astype(float)
    raise ValueError(kind)


def fit_score(eA, eC, kind):
    XA, XC = Xm(eA, kind), Xm(eC, kind)
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    m = LogisticRegression(max_iter=5000, C=0.5).fit((XA - mu) / sd, eA.y)
    return m.predict_proba((XC - mu) / sd)[:, 1], m.predict_proba((XA - mu) / sd)[:, 1]


def boot(y, p1, p0, blocks, n=1000, seed=7):
    ub, inv = np.unique(blocks, return_inverse=True); idx = [np.where(inv == i)[0] for i in range(len(ub))]
    rng = np.random.default_rng(seed); g = []
    for _ in range(n):
        ii = np.concatenate([idx[p] for p in rng.integers(0, len(ub), len(ub))])
        if y[ii].min() == y[ii].max():
            continue
        g.append(roc_auc_score(y[ii], p1[ii]) - roc_auc_score(y[ii], p0[ii]))
    return [round(float(x), 4) for x in np.percentile(g, [2.5, 50, 97.5])]


def r4(x):
    return round(float(x), 4)


def survival_tables(e):
    out = {}
    q = e.bp.abs().quantile([1 / 3, 2 / 3]).to_numpy()
    terc = np.digitize(e.bp.abs().to_numpy(), q)
    for D in DS_:
        row = {}
        for t_ in range(3):
            s = terc == t_
            sv = e[f"surv_{D}"].to_numpy(bool)
            row[f"tercile{t_}"] = {"survived": [r4(e.y[s & sv].mean()) if (s & sv).any() else None, int((s & sv).sum())],
                                   "reverted": [r4(e.y[s & ~sv].mean()) if (s & ~sv).any() else None, int((s & ~sv).sum())]}
        out[f"D{D}"] = row
    # PRICE events only
    pe = e[e.cls == "PRICE"]
    out["PRICE_only"] = {f"D{D}": {"survived": [r4(pe.y[pe[f'surv_{D}']].mean()) if pe[f'surv_{D}'].any() else None, int(pe[f'surv_{D}'].sum())],
                                   "reverted": [r4(pe.y[~pe[f'surv_{D}']].mean()) if (~pe[f'surv_{D}']).any() else None, int((~pe[f'surv_{D}']).sum())]}
                         for D in DS_}
    out["confirm_ok_by_at_150"] = {f"{int(a_)}{int(b_)}": [r4(e.y[(e.cf_ok_150 == a_) & (e.cf_by_150 == b_)].mean()) if ((e.cf_ok_150 == a_) & (e.cf_by_150 == b_)).any() else None,
                                                          int(((e.cf_ok_150 == a_) & (e.cf_by_150 == b_)).sum())] for a_ in (0, 1) for b_ in (0, 1)}
    return out


def norm_tables(e):
    out = {}
    for h in (5, 30, 120):
        z = e[f"z_rv_{h}"]; q = z.quantile([0.5, 0.8, 0.9, 0.95, 0.99]).to_numpy()
        out[f"z_rv_{h}_P_by_quantile"] = {lab: [r4(e.y[s].mean()) if s.any() else None, int(s.sum())] for lab, s in
                                          (("<q50", z < q[0]), ("q50-80", (z >= q[0]) & (z < q[1])), ("q80-90", (z >= q[1]) & (z < q[2])),
                                           ("q90-95", (z >= q[2]) & (z < q[3])), ("q95-99", (z >= q[3]) & (z < q[4])), (">=q99", z >= q[4]))}
    pc = e.pct_win
    out["pct_win"] = {lab: [r4(e.y[s].mean()) if s.any() else None, int(s.sum())] for lab, s in
                      (("<0.5", pc < 0.5), ("0.5-0.9", (pc >= 0.5) & (pc < 0.9)), ("0.9-0.99", (pc >= 0.9) & (pc < 0.99)), (">=0.99", pc >= 0.99))}
    # PRICE events: does z matter at fixed bp?
    pe = e[e.cls == "PRICE"]
    if len(pe) > 40:
        med = pe.z_rv_30.median()
        out["PRICE_by_z30_half"] = {"low_z": [r4(pe.y[pe.z_rv_30 < med].mean()), int((pe.z_rv_30 < med).sum())],
                                    "high_z": [r4(pe.y[pe.z_rv_30 >= med].mean()), int((pe.z_rv_30 >= med).sum())]}
        medb = pe.bp.abs().median()
        out["PRICE_by_bp_half"] = {"low_bp": [r4(pe.y[pe.bp.abs() < medb].mean()), int((pe.bp.abs() < medb).sum())],
                                   "high_bp": [r4(pe.y[pe.bp.abs() >= medb].mean()), int((pe.bp.abs() >= medb).sum())]}
    out["rate_controller_own_state"] = {f"rec30={lab}": [r4(e.y[s].mean()) if s.any() else None, int(s.sum())] for lab, s in
                                        (("0", e.rec30 == 0), ("1-2", (e.rec30 >= 1) & (e.rec30 <= 2)), ("3-5", (e.rec30 >= 3) & (e.rec30 <= 5)), ("6+", e.rec30 >= 6))}
    return out


def elasticity(a, b, dec, Tm, allev):
    T, mic = series(a - 1500, b, "bf")  # trailing 30-min vol needs 1,800 s before the first minute
    lr = np.r_[0.0, np.diff(np.log(mic)) * 1e4]
    cs2 = np.cumsum(lr ** 2)
    rows = []
    aT = allev.tau.to_numpy(np.int64); aP = (allev.cls == "PRICE").to_numpy()
    R = gate8.raw_touch("btc5m_clob_raw2", a, b)
    for st in range((a // 300 + 1) * 300, b - 299, 300):
        ds = dec[dec.st == st].s.to_numpy(np.int64) if (dec.st == st).any() else np.array([], np.int64)
        rg = R[R.m == st]
        for k in range(5):
            t0 = (st + 60 * k) * 1000; t1 = t0 + 60000
            j0, j1 = np.searchsorted(T, t0) - 1, np.searchsorted(T, t1) - 1
            j30 = np.searchsorted(T, t0 - 1800000) - 1
            rvm = (cs2[j1] - cs2[max(j0, 0)]) / 60; rv30 = (cs2[max(j0, 0)] - cs2[max(j30, 0)]) / 1800
            npr = int(aP[(aT >= t0) & (aT < t1)].sum()); nall = int(((aT >= t0) & (aT < t1)).sum())
            nd = int(((ds >= t0 + 150) & (ds < t1 + 150)).sum())
            # share of the minute with the Up ask in the ladder range (0.12, 0.88) at 1-s samples
            if len(rg):
                rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float)
                ts = np.arange(t0, t1, 1000); ii = np.searchsorted(rs, ts, "right") - 1
                v = np.where(ii >= 0, ba[np.clip(ii, 0, None)], np.nan)
                inr = float(np.nanmean((v > 0.12) & (v < 0.88)))
            else:
                inr = np.nan
            rows.append((st, k, nd, npr, nall, rvm, rv30, inr))
    df = pd.DataFrame(rows, columns=["st", "k", "nd", "npr", "nall", "rvm", "rv30", "inr"]).dropna()
    df = df[(df.inr > 0.5) & (df.rvm > 0) & (df.rv30 > 0)]
    import statsmodels.api as sm
    X = pd.DataFrame({"l_npr": np.log1p(df.npr), "l_rvm": np.log(df.rvm), "l_rv30": np.log(df.rv30), "inr": df.inr})
    for k in range(1, 5):
        X[f"k{k}"] = (df.k == k).astype(float)
    X = sm.add_constant(X)
    out = {"cells": int(len(df)), "mean_decisions_per_min": r4(df.nd.mean()), "var_over_mean": r4(df.nd.var() / max(df.nd.mean(), 1e-9))}
    try:
        m = sm.GLM(df.nd, X, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": df.st})
        out["poisson_coef"] = {k: [r4(m.params[k]), r4(m.bse[k])] for k in ("l_npr", "l_rvm", "l_rv30", "inr")}
        X2 = X.drop(columns=["l_npr"])
        m2 = sm.GLM(df.nd, X2, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": df.st})
        out["poisson_coef_no_npr"] = {k: [r4(m2.params[k]), r4(m2.bse[k])] for k in ("l_rvm", "l_rv30", "inr")}
    except Exception as ex:
        out["error"] = str(ex)
    # dispersion within terciles of rv30
    q = df.rv30.quantile([1 / 3, 2 / 3]).to_numpy()
    tt = np.digitize(df.rv30, q)
    out["var_over_mean_by_rv30_tercile"] = [r4(df.nd[tt == i].var() / max(df.nd[tt == i].mean(), 1e-9)) for i in range(3)]
    return out


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    eA, decA, TmA, allA = build11(a, b, lost)
    eC, decC, TmC, allC = build11(c0, c1, lost)
    res = {"events_A": int(len(eA)), "events_C": int(len(eC)), "base_A": r4(eA.y.mean()), "base_C": r4(eC.y.mean())}
    P = {}
    for kind in ("base", "full", "z_only", "full+norm", "full+surv", "full+norm+surv"):
        pC, pA = fit_score(eA, eC, kind)
        P[kind] = pC
        res.setdefault("auc", {})[kind] = {"A_in_sample": r4(roc_auc_score(eA.y, pA)), "C_out_of_sample": r4(roc_auc_score(eC.y, pC))}
    blk = eC.st.to_numpy()
    yC = eC.y.to_numpy()
    res["gain_CI_C"] = {"full+norm vs full": boot(yC, P["full+norm"], P["full"], blk), "full+surv vs full": boot(yC, P["full+surv"], P["full"], blk),
                        "z_only vs full": boot(yC, P["z_only"], P["full"], blk)}
    # univariate AUCs on C (PIT normalizer features and raw bp)
    uni = {"abs_bp": r4(roc_auc_score(yC, eC.bp.abs()))}
    for h in HS:
        uni[f"z_rv_{h}"] = r4(roc_auc_score(yC, eC[f"z_rv_{h}"].fillna(0)))
        uni[f"z_ev_{h}"] = r4(roc_auc_score(yC, eC[f"z_ev_{h}"].fillna(0)))
        uni[f"n_{h}"] = r4(roc_auc_score(yC, eC[f"n_{h}"]))
    uni["pct_win"] = r4(roc_auc_score(yC, eC.pct_win.fillna(0.5)))
    for D in DS_:
        uni[f"surv_{D}(diag)"] = r4(roc_auc_score(yC, eC[f"surv_{D}"].astype(float)))
        uni[f"mv_{D}(diag)"] = r4(roc_auc_score(yC, eC[f"mv_{D}"].fillna(0)))
    res["univariate_auc_C"] = uni
    # PRICE events alone (the strongest class): AUC of z vs bp within the class
    for nm, e in (("A", eA), ("C", eC)):
        pe = e[e.cls == "PRICE"]
        if pe.y.nunique() == 2:
            res.setdefault("PRICE_class_univariate", {})[nm] = {"n": int(len(pe)), "P": r4(pe.y.mean()), "abs_bp": r4(roc_auc_score(pe.y, pe.bp.abs())),
                                                               **{f"z_rv_{h}": r4(roc_auc_score(pe.y, pe[f"z_rv_{h}"].fillna(0))) for h in HS},
                                                               "pct_win": r4(roc_auc_score(pe.y, pe.pct_win.fillna(0.5))),
                                                               "surv_100(diag)": r4(roc_auc_score(pe.y, pe.surv_100.astype(float))),
                                                               "mv_150(diag)": r4(roc_auc_score(pe.y, pe.mv_150.fillna(0)))}
    for nm, e in (("A", eA), ("C", eC)):
        res[f"survival_{nm}"] = survival_tables(e)
        res[f"normalizer_{nm}"] = norm_tables(e)
        k = e.a_minus_tau.dropna().to_numpy()
        hist = np.histogram(k, bins=np.arange(0, 560, 10))[0]
        res[f"kernel_a_minus_tau_{nm}"] = {"n": int(len(k)), "q": [r4(x) for x in np.percentile(k, [5, 10, 25, 50, 75, 90])] if len(k) else None,
                                           "hist10ms_0_550": [int(x) for x in hist]}
        # z* stability: the z_rv_30 threshold that gives the same flagged share as the top-5% raw bp on A
    # window overdispersion: chi2/df of taken events per window against the full+norm model expectation (C)
    for kind in ("full", "full+norm", "full+norm+surv"):
        e2 = eC.assign(pp=P[kind])
        gw = e2.groupby("st").agg(o_=("y", "sum"), e_=("pp", "sum"), v_=("pp", lambda x: float(np.sum(x * (1 - x)))), k=("y", "size"))
        gw = gw[gw.k >= 5]
        res.setdefault("window_chi2_df_C", {})[kind] = [r4(np.sum((gw.o_ - gw.e_) ** 2 / np.maximum(gw.v_, 1e-9)) / max(len(gw), 1)), int(len(gw))]
    # elasticity of the complete decision record (both intervals plus B)
    lost_all = lost
    try:
        dec_all = pd.concat([decA, decC]).drop_duplicates()
        Tm = (np.r_[TmA[0], TmC[0]], np.r_[TmA[1], TmC[1]])
        o_ = np.argsort(Tm[0], kind="stable"); Tm = (Tm[0][o_], Tm[1][o_])
        allev = pd.concat([allA, allC]).drop_duplicates("tau").sort_values("tau")
        res["elasticity_A"] = elasticity(a, b, decA, TmA, allA)
        res["elasticity_C"] = elasticity(c0, c1, decC, TmC, allC)
    except Exception as ex:
        res["elasticity_error"] = repr(ex)
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:9000])


if __name__ == "__main__":
    main(sys.argv[1])
