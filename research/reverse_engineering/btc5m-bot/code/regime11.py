"""Iteration 11 (X72 / X85 follow-up): is the 'on / off' regime of the decisions public? At evt10's clean Binance events (onset
tables it11/onset_{A,C}.parquet), P(decision) rises with the operator's own recent decisions on the window (rec30: 1.4% with
none in the last 30 s vs 6-7.5% with 6+; own state). Compare with the PUBLIC analogue: other traders' prints on the window over
[tau - 30 s, tau - 600 ms) (crowd30; the operator's own txs removed) and over [tau - 5 s, tau - 600 ms) (crowd5). Logistic fit
on A, scored on C: evt10 FULL, FULL + crowd terms (public), FULL + rec30 (own state, reported apart), FULL + both. If rec30
adds beyond the public crowd terms, the regime is internal to the bot.
Usage: python regime11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, evt10
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C


def r4(x):
    return round(float(x), 4)


def main(out):
    E = {}
    for nm in ("A", "C"):
        a, b = stale9.IV[nm]
        ev = pd.read_parquet(C + f"/it11/onset_{nm}.parquet")
        d = live6.own_taker(stale9.OWN, a - 40, b + 5)
        tok, books, trades = L.load_books(a - 40, b + 5)
        own = set(d.tx)
        tr = trades[~trades.tx.isin(own)].copy(); tr["st"] = tr.token.map(lambda t: tok.get(t, (None, -1))[1])
        oth = {k: np.sort(g.s_ms.to_numpy(np.int64)) for k, g in tr.groupby("st")}
        tau = ev.tau.to_numpy(np.int64); st = ev.st.to_numpy(np.int64)
        c30 = np.zeros(len(ev)); c5 = np.zeros(len(ev))
        for i in range(len(ev)):
            om = oth.get(int(st[i]))
            if om is not None:
                c30[i] = np.searchsorted(om, tau[i] - 600) - np.searchsorted(om, tau[i] - 30000)
                c5[i] = np.searchsorted(om, tau[i] - 600) - np.searchsorted(om, tau[i] - 5000)
        ev["crowd30"] = c30; ev["crowd5"] = c5
        E[nm] = ev
    res = {}
    def X(e, kind):
        full = evt10.X(e, "full")
        cr = np.c_[np.log1p(e.crowd30), np.log1p(e.crowd5)]
        ow = np.c_[np.log1p(e.rec30), np.log1p(e.rec60)]
        return {"full": full, "full+crowd": np.c_[full, cr], "full+own": np.c_[full, ow], "full+crowd+own": np.c_[full, cr, ow]}[kind]
    P = {}
    for kind in ("full", "full+crowd", "full+own", "full+crowd+own"):
        XA, XC = X(E["A"], kind), X(E["C"], kind)
        mu, sd = XA.mean(0), XA.std(0) + 1e-9
        m = LogisticRegression(max_iter=4000, C=0.5).fit((XA - mu) / sd, E["A"].y)
        P[kind] = m.predict_proba((XC - mu) / sd)[:, 1]
        res.setdefault("auc_C", {})[kind] = r4(roc_auc_score(E["C"].y, P[kind]))
        pe = (E["C"].cls == "PRICE").to_numpy()
        res.setdefault("auc_C_PRICE_events", {})[kind] = r4(roc_auc_score(E["C"].y[pe], P[kind][pe]))
    for nm in ("A", "C"):
        e = E[nm]
        res[f"corr(rec30, crowd30)_{nm}"] = r4(np.corrcoef(np.log1p(e.rec30), np.log1p(e.crowd30))[0, 1])
        q = e.crowd30.quantile([1 / 3, 2 / 3]).to_numpy(); tc = np.digitize(e.crowd30, q)
        tab = {}
        for t_ in range(3):
            for lab, s in (("rec30=0", e.rec30 == 0), ("rec30 1-5", (e.rec30 >= 1) & (e.rec30 <= 5)), ("rec30 6+", e.rec30 >= 6)):
                k = (tc == t_) & s
                tab[f"crowd30_tercile{t_} {lab}"] = [r4(e.y[k].mean()) if k.any() else None, int(k.sum())]
        res[f"P(decision) by crowd30 tercile x rec30_{nm}"] = tab
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
