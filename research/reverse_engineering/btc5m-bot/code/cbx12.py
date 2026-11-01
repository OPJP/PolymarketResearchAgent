"""Iteration 12, panel iter11 information P1 step (1) (X100): the cross-venue divergence gate with the recorded Coinbase
ticker (btc5m_venues2 'cbT', exchange stamps E, 10-31 development block). For every clean Binance USD-M onset of the
iteration-11 onset tables (A = 14:55-16:04, C = 16:33-17:55), the Coinbase class over [tau - 500, tau + 70) ms
(pre-registered here before scoring): N = no Coinbase trade; M = Coinbase mid moved toward o by >= 0.1 bp from the last
record before tau - 500 to the last record in the window; S = traded without such a move. Report P(take) by class x
event class on A and C, and the out-of-sample AUC of the evt10-style FULL logistic with and without the class (fit A score
C, and fit C score A), with a window-block bootstrap of the gain."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import live_lab as L
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
C = L.C
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
A0, A1, C0, C1 = 1793458500, 1793462640, 1793464380, 1793469300  # generous bounds (exchange ms / 1000) of A and C


def cb_series(a, b):
    rows = []
    for r in L.recs("btc5m_venues2", a - 30, b + 5):
        if r.get("v") == "cbT" and r.get("y") == "BTC" and r.get("b") and r.get("a"):
            rows.append((r.get("E") or r["t"], 0.5 * (r["b"] + r["a"])))
    x = np.array(rows, float)
    return x[np.argsort(x[:, 0], kind="stable")]


def classify(ev, cb):
    E, M = cb[:, 0], cb[:, 1]
    tau = ev.tau.to_numpy(float); sg = ev.sgn.to_numpy(float)
    i0 = np.searchsorted(E, tau - 500, "left"); i1 = np.searchsorted(E, tau + 70, "left")
    n = i1 - i0
    m_before = np.where(i0 > 0, M[np.maximum(i0 - 1, 0)], np.nan)
    m_last = np.where(n > 0, M[np.maximum(i1 - 1, 0)], np.nan)
    mv = sg * (m_last - m_before) / m_before * 1e4
    cls = np.where(n == 0, "N", np.where(mv >= 0.1, "M", "S"))
    return cls, mv


def design(e, with_cb):
    X = pd.DataFrame({"lbp": np.log(np.abs(e.bp) + 1e-3), "price": (e.cls == "PRICE").astype(float), "dep": (e.cls == "DEPLETE").astype(float),
                      "unch": e.unch150.astype(float), "dask": np.abs(e.ask - 0.5), "agree": e.agree.astype(float), "spr": e.spread_bp.astype(float),
                      "act": np.log1p(e.act.astype(float)), "rp": e.rp.astype(float)})
    X = X.fillna(0)
    if with_cb:
        for k in ("N", "M"):
            X["cb_" + k] = (e.cbcls == k).astype(float)
            X["cb_" + k + "_x_price"] = X["cb_" + k] * X.price
    return X


def main():
    res = {}
    E = {}
    for nm in ("A", "C"):
        e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
        e = e[e.clean.astype(bool)].reset_index(drop=True)
        t0, t1 = e.tau.min() / 1000, e.tau.max() / 1000
        cb = cb_series(t0 - 5, t1 + 5)
        e["cbcls"], e["cbmv"] = classify(e, cb)
        E[nm] = e
        tab = {}
        for ec in ("PRICE", "DEPLETE", "REFILL", "ALL"):
            x = e if ec == "ALL" else e[e.cls == ec]
            tab[ec] = {k: [round(float(x.y[x.cbcls == k].mean()), 4) if (x.cbcls == k).any() else None, int((x.cbcls == k).sum())] for k in ("N", "S", "M")}
        res[nm] = {"events": int(len(e)), "coinbase_records": int(len(cb)), "take_by_class": tab}
    for fit, sc in (("A", "C"), ("C", "A")):
        ea, ec = E[fit], E[sc]
        out = {}
        for wc in (False, True):
            m = LogisticRegression(max_iter=2000, C=1.0).fit(design(ea, wc), ea.y)
            out["with_cb" if wc else "full"] = m.predict_proba(design(ec, wc))[:, 1]
        y = ec.y.to_numpy()
        a0, a1 = roc_auc_score(y, out["full"]), roc_auc_score(y, out["with_cb"])
        # window-block bootstrap of the gain
        w = ec.st.to_numpy(); uw = np.unique(w); rng = np.random.default_rng(12); gi = {u: np.where(w == u)[0] for u in uw}; bs = []
        for _ in range(500):
            ii = np.concatenate([gi[u] for u in rng.choice(uw, len(uw))])
            if 0 < y[ii].sum() < len(ii):
                bs.append(roc_auc_score(y[ii], out["with_cb"][ii]) - roc_auc_score(y[ii], out["full"][ii]))
        pr = (ec.cls == "PRICE").to_numpy()
        res[f"fit_{fit}_score_{sc}"] = {"auc_full": round(a0, 4), "auc_full_plus_coinbase": round(a1, 4), "gain": round(a1 - a0, 4),
                                       "gain_ci95_window_blocks": [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)],
                                       "price_events_auc_full": round(roc_auc_score(y[pr], out["full"][pr]), 4) if 0 < y[pr].sum() < pr.sum() else None,
                                       "price_events_auc_plus_coinbase": round(roc_auc_score(y[pr], out["with_cb"][pr]), 4) if 0 < y[pr].sum() < pr.sum() else None}
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(R, "cbx12.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
