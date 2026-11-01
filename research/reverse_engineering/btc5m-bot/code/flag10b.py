"""Iteration 10 (panel iter9 assumptions P2 = X83, information P1 step 3 = X73): selection on EPISODES (evidence accumulation vs a
constant hazard) and the BUSY state from in-flight orders under the 150-ms taker delay.
Same frozen setup as flag9 / flag10: FULL hazard design, decision label (matches + located lost races), fit on A (10-31
14:55-16:04), scored on C (16:33-17:55), never refit; flagged = score >= the A 97th percentile; episode = run of flagged points
(same window and outcome, gaps <= 1 s).
(1) Discrete-time hazard of the FIRST decision in an episode, per 100-ms step, censored at the episode end: models
    S  = step dummies only (time since onset; the constant-hazard null is S with one level),
    I  = S + instantaneous terms (FULL logit, tick toward o, |ask - 0.5|),
    AC = I + accumulated evidence since onset (sum of the tick over the episode's points, max tick so far, change of o's ask
         since onset, number of points with tick > 0).
    Fit on A's episode points, scored on C: per-step AUC and the episode-level AUC of 1 - prod(1 - h).
(2) Busy state (own state, reported separately, never a feature): wallet j is BUSY at t if it has a taker match in
    (t - 100, t + 150] (an order in the delay or awaiting the response). P(new decision in [t + 250, t + 600) | flagged) by the
    number of busy wallets (DS, GF, XM).
Usage: python flag10b.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C


def ep_frame(d, p, thr, gap=1000):
    k = p >= thr
    x = d.assign(p=p)[k].sort_values(["st", "o", "t"]).reset_index(drop=True)
    ep = np.zeros(len(x), int); e = -1; prev = None
    for i, (st, o, t) in enumerate(zip(x.st.to_numpy(), x.o.to_numpy(), x.t.to_numpy())):
        if prev is None or prev[0] != st or prev[1] != o or t - prev[2] > gap:
            e += 1
        ep[i] = e; prev = (st, o, t)
    x["ep"] = ep
    x["k"] = x.groupby("ep").cumcount()
    x["lg"] = np.log(np.clip(x.p, 1e-6, 1 - 1e-6) / (1 - np.clip(x.p, 1e-6, 1 - 1e-6)))
    x["cum_tick"] = x.groupby("ep").tick.cumsum()
    x["max_tick"] = x.groupby("ep").tick.cummax()
    x["npos"] = x.groupby("ep").tick.transform(lambda v: (v > 0.002).cumsum())
    x["ask0"] = x.groupby("ep").ask.transform("first")
    x["dask"] = (x.ask - x.ask0) * 100
    # first-decision hazard: keep points up to and including the first positive point
    x["cumy"] = x.groupby("ep").y_dec.cumsum()
    x["before"] = x.groupby("ep").cumy.shift(1).fillna(0)
    h = x[x.before == 0].copy()
    return x, h


def design(h, kind):
    k = h.k.to_numpy()
    S = np.c_[k == 0, k == 1, k == 2, (k >= 3) & (k <= 5), (k >= 6) & (k <= 10), k > 10].astype(float)
    if kind == "S":
        return S
    I = np.c_[S, h.lg, h.tick, np.abs(h.ask - 0.5)]
    if kind == "I":
        return I
    return np.c_[I, np.clip(h.cum_tick, -20, 20), np.clip(h.max_tick, -5, 5), np.clip(h.dask, -10, 10), h.npos]


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    gA, tkA, _ = stale9.grid(a, b, lost); gC, tkC, _ = stale9.grid(c0, c1, lost)
    dA = stale9.stack(gA, 2.0, "any"); dC = stale9.stack(gC, 2.0, "any")
    XA, XC = stale9.X_of(dA, "full"), stale9.X_of(dC, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    lr = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, dA.y_dec)
    pA = lr.predict_proba((XA - mu) / sd)[:, 1]; pC = lr.predict_proba((XC - mu) / sd)[:, 1]
    thr = float(np.quantile(pA, 0.97))
    xA, hA = ep_frame(dA, pA, thr); xC, hC = ep_frame(dC, pC, thr)
    res = {"episodes_A": int(xA.ep.nunique()), "episodes_C": int(xC.ep.nunique()), "hazard_rows_A": int(len(hA)), "hazard_rows_C": int(len(hC))}
    models = {}
    for kind in ("S", "I", "AC"):
        Xa, Xc = design(hA, kind), design(hC, kind)
        m_, s_ = Xa.mean(0), Xa.std(0) + 1e-9
        m = LogisticRegression(max_iter=3000, C=1.0).fit((Xa - m_) / s_, hA.y_dec)
        hc = m.predict_proba((Xc - m_) / s_)[:, 1]
        hC["h_" + kind] = hc
        eps = hC.groupby("ep").agg(y=("y_dec", "max"), P=("h_" + kind, lambda v: 1 - np.prod(1 - v.to_numpy())))
        models[kind] = {"step_auc_C": round(float(roc_auc_score(hC.y_dec, hc)), 4),
                        "episode_auc_C": round(float(roc_auc_score(eps.y, eps.P)), 4),
                        "coef": [round(float(c), 3) for c in m.coef_[0]]}
    res["first_decision_hazard"] = models
    # empirical hazard by step (A and C)
    for nm, h in (("A", hA), ("C", hC)):
        res[f"hazard_by_step_{nm}"] = {lab: [round(float(h.y_dec[sel].mean()), 4), int(sel.sum())] for lab, sel in
                                       (("k0", h.k == 0), ("k1", h.k == 1), ("k2", h.k == 2), ("k3-5", (h.k >= 3) & (h.k <= 5)),
                                        ("k6-10", (h.k >= 6) & (h.k <= 10)), ("k11+", h.k > 10)) if sel.any()}
        # hazard by accumulated evidence within step strata
        q = h.cum_tick.quantile([0.33, 0.67]).to_numpy()
        res[f"hazard_by_cum_tick_terciles_{nm}"] = {f"k{lo}-{hi}": [round(float(h.y_dec[(h.k >= lo) & (h.k <= hi) & (h.cum_tick <= q[0])].mean()), 4),
                                                                     round(float(h.y_dec[(h.k >= lo) & (h.k <= hi) & (h.cum_tick > q[0]) & (h.cum_tick <= q[1])].mean()), 4),
                                                                     round(float(h.y_dec[(h.k >= lo) & (h.k <= hi) & (h.cum_tick > q[1])].mean()), 4)]
                                                    for lo, hi in ((0, 0), (1, 2), (3, 5), (6, 1000))}
    # busy state on C (and A)
    for nm, d, p, tk in (("A", dA, pA, tkA), ("C", dC, pC, tkC)):
        k = p >= thr
        t = d.t.to_numpy(np.int64); st = d.st.to_numpy(np.int64); o = d.o.to_numpy(bool)
        # cluster matches per wallet (any outcome of the window) and decisions on o
        mw = {}
        for w, g in tk.groupby("wal"):
            mw[w] = np.sort(g.m.to_numpy(np.int64))
        nb = np.zeros(len(t), int)
        for w, arr in mw.items():
            i0 = np.searchsorted(arr, t - 100, "right"); i1 = np.searchsorted(arr, t + 150, "right")
            nb += (i1 > i0).astype(int)
        # new decision on o in [t + 250, t + 600): matches + lost races
        dec = {}
        lo_ = lost[(lost.s_ins >= (a if nm == "A" else c0) * 1000) & (lost.s_ins < (b if nm == "A" else c1) * 1000)]
        for (s0, up), g in tk.groupby(["start", "is_up"]):
            dec[(int(s0), bool(up))] = list(g.m.to_numpy(np.int64))
        for r in lo_.itertuples():
            dec.setdefault((int(r.mstart), bool(r.is_up)), []).append(int(r.s_ins))
        dec = {kk: np.sort(np.array(v, np.int64)) for kk, v in dec.items()}
        y2 = np.zeros(len(t), bool)
        for i in np.where(k)[0]:
            arr = dec.get((int(st[i]), bool(o[i])))
            if arr is not None:
                y2[i] = np.searchsorted(arr, t[i] + 600) > np.searchsorted(arr, t[i] + 250)
        res[f"busy_{nm}"] = {f"n_busy={j}": [round(float(y2[k & (nb == j)].mean()), 4) if (k & (nb == j)).any() else None, int((k & (nb == j)).sum())]
                             for j in range(4)}
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])
