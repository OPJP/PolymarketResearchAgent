"""Iteration 12, panel iter11 assumptions P1 step 2 (X109), compact version: a Hawkes-type kernel of the operator's own past
decisions vs a slow-regime proxy, as additions to the public FULL onset design (logistic, fit on one half, scored on the
other; own state, a mechanism measurement only). (a) H_k = sum over the operator's decisions on the window before tau of
exp(-(tau - a_j) / k), k chosen on the fit half among 5 / 15 / 30 / 60 s; (b) slow = log(1 + decisions in [tau - 120 s,
tau - 30 s)) and log(1 + decisions in [tau - 300 s, tau - 120 s)) (excluding the last 30 s); (c) both. Held-out log loss and AUC."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss
from cbx12 import design
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
dec = pd.read_parquet(f"{C}/it11/large_dec.parquet")
G = {int(st): np.sort(g.a.to_numpy(float)) for st, g in dec.groupby("st")}
KS = (5, 15, 30, 60)


def feats(e):
    tau = e.tau.to_numpy(float); st = e.st.to_numpy(np.int64)
    H = {k: np.zeros(len(e)) for k in KS}; s1 = np.zeros(len(e)); s2 = np.zeros(len(e))
    for i in range(len(e)):
        a = G.get(int(st[i]))
        if a is None:
            continue
        past = a[a < tau[i]]
        dt = (tau[i] - past) / 1000.0
        for k in KS:
            H[k][i] = np.exp(-dt / k).sum()
        s1[i] = ((dt >= 30) & (dt < 120)).sum(); s2[i] = ((dt >= 120) & (dt < 300)).sum()
    return H, np.log1p(s1), np.log1p(s2)


def main():
    E = {}
    for nm in ("A", "C"):
        e = pd.read_parquet(f"{C}/it11/onset_{nm}.parquet")
        e = e[e.clean.astype(bool)].reset_index(drop=True)
        E[nm] = (e, design(e, False), feats(e))
    res = {}
    for fit, sc in (("A", "C"), ("C", "A")):
        ef, Xf, (Hf, s1f, s2f) = E[fit]; es, Xs, (Hs, s1s, s2s) = E[sc]
        yf, ys = ef.y.to_numpy(), es.y.to_numpy()
        best_k, best_ll = None, 1e9
        for k in KS:  # choose the Hawkes decay on the fit half (in-sample log loss)
            m = LogisticRegression(max_iter=3000).fit(Xf.assign(H=np.log1p(Hf[k])), yf)
            ll = log_loss(yf, m.predict_proba(Xf.assign(H=np.log1p(Hf[k])))[:, 1])
            if ll < best_ll:
                best_k, best_ll = k, ll
        out = {"hawkes_k_s": best_k}
        for lab, addf, adds in (("full", {}, {}), ("hawkes", {"H": np.log1p(Hf[best_k])}, {"H": np.log1p(Hs[best_k])}),
                                ("slow", {"s1": s1f, "s2": s2f}, {"s1": s1s, "s2": s2s}),
                                ("both", {"H": np.log1p(Hf[best_k]), "s1": s1f, "s2": s2f}, {"H": np.log1p(Hs[best_k]), "s1": s1s, "s2": s2s})):
            m = LogisticRegression(max_iter=3000).fit(Xf.assign(**addf), yf)
            p = m.predict_proba(Xs.assign(**adds))[:, 1]
            out[lab] = {"heldout_logloss": round(float(log_loss(ys, p)), 5), "heldout_auc": round(float(roc_auc_score(ys, p)), 4)}
        res[f"fit_{fit}_score_{sc}"] = out
        print(fit, sc, json.dumps(out), flush=True)
    json.dump(res, open(f"{R}/hawkes12.json", "w"), indent=1)


if __name__ == "__main__":
    main()
