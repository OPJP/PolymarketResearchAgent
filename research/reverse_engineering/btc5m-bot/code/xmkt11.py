"""Iteration 11 (panel iter10 information P5 = X91): Polymarket's OTHER crypto books as the market-wide confirmation of an onset.
Event unit = evt10's clean Binance USD-M BTC bookTicker events (label: cluster decision on o in [tau + 150, tau + 700); fit on A,
scored on C). Features from the shared recorder's clob_crypto trades (server ms 's', taker side 'd') on the OTHER crypto
Up/Down markets (BTC 15m / 4h, ETH 5m / 15m / 4h, SOL 5m / 15m / 4h), direction-mapped (taker BUY of Up or SELL of Down = +1),
counted toward / against the event's direction in [tau - 300, tau) and [tau - 1000, tau); also the same for the BTC 5m window
itself (other traders only; the cluster's txs removed) for reference. These are other traders' activity: they decode the
mechanism but belong in the co-occurrence baseline, never in a presence gain. Also the lead check: share of taken events with a
same-direction cross-market trade in [tau - 300, tau) that precedes the cluster's arrival.
Usage: python xmkt11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, evt10
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
GROUPS = {"btc_long": ("btc-updown-15m", "btc-updown-4h"), "eth": ("eth-updown-5m", "eth-updown-15m", "eth-updown-4h"),
          "sol": ("sol-updown-5m", "sol-updown-15m", "sol-updown-4h")}


def r4(x):
    return round(float(x), 4)


def token_dir(a, b):
    tk = {}
    for r in L.recs("subs", a - 4 * 3600 - 600, b):
        if r.get("feed") != "clob_crypto":
            continue
        for slug, tks in r["markets"].items():
            fam = slug.rsplit("-", 1)[0]
            tk[str(tks[0])] = (fam, 1.0); tk[str(tks[1])] = (fam, -1.0)
    return tk


def xtrades(a, b, tk, own_tx):
    rows = []
    for r in L.recs("clob_crypto", a - 2, b + 2):
        if r.get("k") != "x":
            continue
        t = str(r["a"])
        if t not in tk or r.get("h", "").lower() in own_tx:
            continue
        fam, dirn = tk[t]
        sd = 1.0 if r.get("d") == "BUY" else -1.0
        rows.append((int(r["s"]), fam, dirn * sd, float(r.get("z") or 0)))
    return pd.DataFrame(rows, columns=["s", "fam", "dir", "z"])


def feats(ev, X):
    tau = ev.tau.to_numpy(np.int64); sg = ev.sgn.to_numpy(float)
    out = {}
    for g, fams in list(GROUPS.items()) + [("btc5m", ("btc-updown-5m",))]:
        x = X[X.fam.isin(fams)].sort_values("s")
        s = x.s.to_numpy(np.int64); d = x.dir.to_numpy(float)
        cpos = np.r_[0, np.cumsum(d > 0)]; cneg = np.r_[0, np.cumsum(d < 0)]
        for w in (300, 1000):
            i0 = np.searchsorted(s, tau - w, "left"); i1 = np.searchsorted(s, tau, "left")
            up_ = cpos[i1] - cpos[i0]; dn_ = cneg[i1] - cneg[i0]
            out[f"{g}_tow_{w}"] = np.where(sg > 0, up_, dn_); out[f"{g}_agn_{w}"] = np.where(sg > 0, dn_, up_)
    return pd.DataFrame(out, index=ev.index)


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    res = {}
    E = {}
    for nm in ("A", "C"):
        a, b = stale9.IV[nm]
        ev = evt10.build(a, b, lost)
        d = live6.own_taker(stale9.OWN, a - 5, b + 5)
        own_tx = set(d.tx.str.lower())
        tk = token_dir(a, b)
        X = xtrades(a, b, tk, own_tx)
        res[f"xtrades_{nm}"] = {f: int(n) for f, n in X.fam.value_counts().items()}
        F = feats(ev, X)
        E[nm] = pd.concat([ev, F], axis=1)
    cols = [c for c in E["A"].columns if "_tow_" in c or "_agn_" in c]
    xcols = [c for c in cols if not c.startswith("btc5m")]
    for nm in ("A", "C"):
        e = E[nm]
        tab = {}
        for g in ("btc_long", "eth", "sol"):
            s = e[f"{g}_tow_300"] > 0; s2 = e[f"{g}_agn_300"] > 0
            tab[g] = {"tow>0": [r4(e.y[s].mean()) if s.any() else None, int(s.sum())], "agn>0": [r4(e.y[s2].mean()) if s2.any() else None, int(s2.sum())],
                      "none": [r4(e.y[~s & ~s2].mean()), int((~s & ~s2).sum())]}
        anyx = (e[[f"{g}_tow_300" for g in GROUPS]].sum(1) > 0)
        tab["any_cross_tow_300"] = [r4(e.y[anyx].mean()), int(anyx.sum()), "vs", r4(e.y[~anyx].mean()), int((~anyx).sum())]
        pe = e[e.cls == "PRICE"]; ax = (pe[[f"{g}_tow_300" for g in GROUPS]].sum(1) > 0)
        tab["PRICE_any_cross_tow_300"] = [r4(pe.y[ax].mean()) if ax.any() else None, int(ax.sum()), "vs", r4(pe.y[~ax].mean()) if (~ax).any() else None, int((~ax).sum())]
        s5 = e.btc5m_tow_300 > 0
        tab["btc5m_others_tow_300"] = [r4(e.y[s5].mean()), int(s5.sum()), "vs", r4(e.y[~s5].mean()), int((~s5).sum())]
        res[f"P(take)_{nm}"] = tab
    # models fit on A, scored on C
    def Xm(e, kind):
        full = evt10.X(e, "full")
        xx = np.log1p(e[xcols].to_numpy(float))
        x5 = np.log1p(e[[c for c in cols if c.startswith("btc5m")]].to_numpy(float))
        base = evt10.X(e, "base")
        return {"base": base, "base+x": np.c_[base, xx, x5], "full": full, "full+x": np.c_[full, xx], "full+x+btc5m": np.c_[full, xx, x5]}[kind]
    P = {}
    for kind in ("base", "base+x", "full", "full+x", "full+x+btc5m"):
        XA, XC = Xm(E["A"], kind), Xm(E["C"], kind)
        mu, sd = XA.mean(0), XA.std(0) + 1e-9
        m = LogisticRegression(max_iter=4000, C=0.5).fit((XA - mu) / sd, E["A"].y)
        P[kind] = m.predict_proba((XC - mu) / sd)[:, 1]
        res.setdefault("auc_C", {})[kind] = r4(roc_auc_score(E["C"].y, P[kind]))
    # PRICE class only: does cross-market agreement separate taken from skipped?
    pc = E["C"][E["C"].cls == "PRICE"]
    if pc.y.nunique() == 2:
        res["PRICE_C_univariate_auc"] = {c: r4(roc_auc_score(pc.y, pc[c])) for c in cols if c.endswith("_300")}
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:5000])


if __name__ == "__main__":
    main(sys.argv[1])
