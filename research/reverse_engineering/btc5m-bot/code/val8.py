"""Iteration 8 (follow-up of dvol8 / X30 / X56): does the LEVEL of an implied-vol value gap add to the decision-level hazard?
FV_o(t) = digital value of o with the exact strike (Gamma priceToBeat of the window, known at its open), S = Binance USD-M
BTC microprice at t x a basis fixed at the open (K / mean microprice over [start - 60, start)), sigma = Deribit DVOL of the
last complete hour per sqrt(s), variance sigma^2 max(tau - 40, tau / 3). gap_o = FV_o - ask_o. The gate8 design (activity,
tick, touch-change gate, age, |ask - 0.5|) with and without the gap features (gap, max(gap, 0), gap x tick > 0.02); fitted on
one development interval, scored on a later one (lab feeds). Usage: python val8.py PTB_JSON DVOL_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import live6, sealed
from lag7 import micro_series, mv
from gate8 import raw_touch
from live8 import OWN
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

PTB = {int(k): float(v) for k, v in json.load(open(sys.argv[1])).items()}
DV = pd.DataFrame(json.load(open(sys.argv[2]))["result"]["data"], columns=["t", "o", "h", "l", "c"])
DVC = dict(zip((DV.t // 1000).astype(int), DV.c / 100.0))


def design(own, a, b, vf="btc5m_venues2", cf="btc5m_clob_raw2"):
    d = live6.own_taker(own, a, b)
    tok, books, trades = L.load_books(a, b)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda t: tok[t][1]); tk["is_up"] = tk.token.map(lambda t: tok[t][2])
    tk = tk[np.array([not sealed.is_sealed(s, "btc5m-bot") for s in tk.start], bool)]
    tk["m"] = tk.tx.map(mt); tk = tk[tk.m.notna()].drop_duplicates(["tx", "token"])
    m = tk.m.to_numpy(np.int64); up = tk.is_up.to_numpy(bool)
    S = micro_series(vf, a - 120, b); keys = sorted(S)
    TB, PB, _ = S[("bf", "BTC")]
    R = raw_touch(cf, a, b)
    tr = trades[~trades.tx.isin(set(tk.tx))].copy(); tr["start"] = tr.token.map(lambda x: tok.get(x, (None, -1))[1])
    rows = []
    for st in sorted({tok[t][1] for t in tok}):
        if sealed.is_sealed(st, "btc5m-bot") or st not in PTB:
            continue
        g = np.arange((st + 5) * 1000, (st + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= a * 1000 + 5000) & (g < b * 1000)]
        rg = R[R.m == st]
        if not len(g) or len(rg) < 2:
            continue
        rs = rg.s.to_numpy(np.int64); ba = rg.ba.to_numpy(float); bb = rg.bb.to_numpy(float)
        def at(x, tt):
            i = np.searchsorted(rs, tt, "right") - 1
            o = x[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        def pb(tt):
            i = np.searchsorted(TB, tt, "right") - 1
            o = PB[np.clip(i, 0, None)].astype(float); o[i < 0] = np.nan
            return o
        op = pb(np.arange((st - 60) * 1000, st * 1000, 100, dtype=np.int64))
        if not np.isfinite(op).any():
            continue
        K = PTB[st]; basis = K / np.nanmean(op)
        hr = (g // 1000 // 3600) * 3600 - 3600
        sig = np.array([DVC.get(int(h), np.nan) for h in hr]) / np.sqrt(365.0 * 86400.0)
        tau = st + 300 - g / 1000.0
        sd = sig * np.sqrt(np.maximum(tau - 40, tau / 3))
        fvu = norm.cdf(np.log(pb(g) * basis / K) / np.maximum(sd, 1e-9))
        comp = np.zeros(len(g)); okc = np.zeros(len(g), bool)
        for key in keys:
            r = mv(S, key, g - 500, g); okc |= np.isfinite(r); comp += np.nan_to_num(r)
        om = np.sort(tr[tr.start == st].s_ms.to_numpy(np.int64))
        act = (np.searchsorted(om, g, "left") - np.searchsorted(om, g - 1000, "left")).astype(float)
        for o, sg in ((True, 1.0), (False, -1.0)):
            if o:
                ak, ak5, xv = at(ba, g), at(ba, g - 500), ba
            else:
                ak, ak5, xv = 1 - at(bb, g), 1 - at(bb, g - 500), bb
            ch = np.r_[True, np.diff(xv) != 0]; tch = rs[ch]; ic = np.searchsorted(tch, g, "right") - 1
            age = np.where(ic >= 0, g - tch[np.clip(ic, 0, None)], 1e5).astype(float)
            mm = np.sort(m[(up == o) & (tk.start.to_numpy() == st)])
            y = (np.searchsorted(mm, g + 600, "left") - np.searchsorted(mm, g + 100, "left")) > 0
            fv = fvu if o else 1 - fvu
            k = okc & np.isfinite(ak) & np.isfinite(ak5) & (ak > 0.03) & (ak < 0.97) & np.isfinite(fv)
            rp = np.sign(np.round((ak[k] - ak5[k]) * 100)); tick = sg * comp[k]; la = np.log1p(age[k] / 100.0); gap = fv[k] - ak[k]
            base = np.c_[act[k], np.log1p(act[k]), tick, np.abs(tick), np.clip(tick, 0, None), rp == 0, rp > 0, rp < 0,
                         np.clip(tick, 0, None) * (rp == 0), np.clip(tick, 0, None) * (rp > 0), la, la * (tick > 0.02), np.abs(ak[k] - 0.5)]
            rows.append((y[k], base.astype(float), np.c_[gap, np.clip(gap, 0, None), gap * (tick > 0.02)].astype(float)))
    y = np.concatenate([r[0] for r in rows]).astype(int); X0 = np.vstack([r[1] for r in rows]); XG = np.vstack([r[2] for r in rows])
    return y, X0, XG


if __name__ == "__main__":
    res = {}
    D = {k: design(*OWN[k]) for k in ("A", "B", "C")}
    for fit, test in (("A", "C"), ("B", "C"), ("A", "B")):
        yf, X0f, XGf = D[fit]; yt, X0t, XGt = D[test]
        m0 = LogisticRegression(max_iter=4000).fit(X0f, yf)
        m1 = LogisticRegression(max_iter=4000).fit(np.c_[X0f, XGf], yf)
        mg = LogisticRegression(max_iter=4000).fit(XGf, yf)
        r = {"n_test": int(len(yt)), "auc_gate_design": round(float(roc_auc_score(yt, m0.predict_proba(X0t)[:, 1])), 4),
             "auc_gate_plus_gap": round(float(roc_auc_score(yt, m1.predict_proba(np.c_[X0t, XGt])[:, 1])), 4),
             "auc_gap_only": round(float(roc_auc_score(yt, mg.predict_proba(XGt)[:, 1])), 4),
             "gap_coef_in_full": [round(float(c), 3) for c in m1.coef_[0][-3:]],
             "p_match_by_gap": {}}
        gb = pd.cut(XGt[:, 0], [-1, -0.05, -0.02, 0, 0.02, 0.05, 1])
        r["p_match_by_gap"] = {str(k): [round(float(yt[gb == k].mean()), 4), int((gb == k).sum())] for k in gb.categories}
        res[f"{fit}_to_{test}"] = r
        print(fit, "->", test, json.dumps(r), flush=True)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "val8.json"), "w"), indent=1)
