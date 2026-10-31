"""Iteration 11 (X84 / X97 follow-up, panel F6): is the LARGE size chosen from public information at the decision? Live decision
record of 10-31 14:55-17:55 (2,155 decisions; large = 100 shares, 111). Public features at the arrival a (point-in-time for the
bot: venue inputs up to a - 30 ms, Polymarket book at a - 30 ms): six-series tick toward o over [a - 530, a - 30) and its
magnitude, BTC composite move toward o since the window start (bp), o's ask, |ask - 0.5|, time in window, o's ask change over
[a - 1000, a - 30], other traders' prints on the window in [a - 5 s, a - 30) (crowd); own state reported apart: the operator's
SENT net on o before a (shares) and its recent decisions on the window in [a - 30 s, a). Univariate AUCs on all decisions and
by half (A = before 16:20, C = after), per wallet; logistic fit on A scored on C (public / own / both).
Usage: python large11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9, gate8, stale9, live6
from lag7 import micro_series, mv
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
A, B = 1793458500, 1793469300
SPLIT = 1793463600 + 1200  # 16:20 UTC


def r4(x):
    return round(float(x), 4)


def main(out):
    o, _ = ins9.load_orders(A, B)
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    o["st"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.st.notna()].copy(); o["m0"] = o.tx0.str.lower().map(mt)
    T = o[(o["first"] == "T") & o.m0.notna() & o.Z.notna()]
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])]
    D = pd.concat([pd.DataFrame({"st": T.st.astype(int), "up": T.up.astype(bool), "a": T.m0.astype(np.int64) - 150, "Z": T.Z.astype(float), "w": T.w}),
                   pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "a": Mi.s_ins.astype(np.int64) - 150, "Z": Mi.Z.astype(float), "w": Mi.w})],
                  ignore_index=True).sort_values(["st", "a"]).reset_index(drop=True)
    D["large"] = D.Z >= 90
    S = micro_series("btc5m_venues2", A - 400, B)
    a = D.a.to_numpy(np.int64); sg = np.where(D.up, 1.0, -1.0)
    tick = np.zeros(len(D)); nk = 0
    for key in S:
        r = mv(S, key, a - 530, a - 30); tick += np.nan_to_num(r)
    D["tick"] = sg * tick; D["abstick"] = np.abs(tick)
    st = D.st.to_numpy(np.int64)
    if ("bf", "BTC") in S:
        D["since_start"] = sg * np.nan_to_num(mv(S, ("bf", "BTC"), st * 1000 + 1000, a - 30))
    R = gate8.raw_touch("btc5m_clob_raw2", A, B)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    ask = np.full(len(D), np.nan); dask = np.full(len(D), np.nan)
    for i, (s0, up, ai) in enumerate(zip(st, D.up.to_numpy(), a)):
        x = tch.get(int(s0))
        if x is None:
            continue
        rs, bb, ba = x
        def at(t):
            j = np.searchsorted(rs, t, "right") - 1
            return np.nan if j < 0 else (ba[j] if up else 1 - bb[j])
        ask[i] = at(ai - 30); dask[i] = (ask[i] - at(ai - 1000)) * 100
    D["ask"] = ask; D["absask"] = np.abs(ask - 0.5); D["dask"] = dask; D["rel"] = a / 1000 - st
    d = live6.own_taker(stale9.OWN, A - 5, B + 5)
    tok, books, trades = L.load_books(A - 5, B + 5)
    tr = trades[~trades.tx.isin(set(d.tx))].copy(); tr["st"] = tr.token.map(lambda t: tok.get(t, (None, -1))[1])
    oth = {k: np.sort(g.s_ms.to_numpy(np.int64)) for k, g in tr.groupby("st")}
    D["crowd5"] = [(lambda om: 0 if om is None else np.searchsorted(om, ai - 30) - np.searchsorted(om, ai - 5000))(oth.get(int(s0))) for s0, ai in zip(st, a)]
    # own state: sent net on o before a, recent decisions
    sent = np.zeros(len(D)); rec = np.zeros(len(D))
    for s0, g in D.groupby("st"):
        idx = g.index.to_numpy(); aa = g.a.to_numpy(np.int64); zz = (np.where(g.up, 1.0, -1.0) * g.Z.to_numpy(float))
        cz = np.r_[0, np.cumsum(zz)]
        for k, i in enumerate(idx):
            sent[i] = (1.0 if D.up[i] else -1.0) * cz[k]
            rec[i] = k - np.searchsorted(aa, aa[k] - 30000)
    D["sent_net_on_o"] = sent; D["rec30"] = rec
    D = D[np.isfinite(D.ask)].reset_index(drop=True)
    pub = ["tick", "abstick", "since_start", "ask", "absask", "dask", "rel", "crowd5"]
    own = ["sent_net_on_o", "rec30"]
    res = {"decisions": int(len(D)), "large": int(D.large.sum())}
    y = D.large.to_numpy()
    res["univariate_auc_all"] = {f: r4(roc_auc_score(y, D[f].fillna(0))) for f in pub + own}
    for w, g in D.groupby("w"):
        if g.large.nunique() == 2:
            res.setdefault("univariate_auc_by_wallet", {})[w] = {"n_large": int(g.large.sum()), **{f: r4(roc_auc_score(g.large, g[f].fillna(0))) for f in pub + own}}
    tA = D.a < SPLIT * 1000
    for nm, cols in (("public", pub), ("own", own), ("both", pub + own)):
        XA = D.loc[tA, cols].fillna(0).to_numpy(float); XC = D.loc[~tA, cols].fillna(0).to_numpy(float)
        mu, sd = XA.mean(0), XA.std(0) + 1e-9
        m = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, y[tA])
        p = m.predict_proba((XC - mu) / sd)[:, 1]
        res.setdefault("fit_A_score_C_auc", {})[nm] = r4(roc_auc_score(y[~tA], p)) if y[~tA].any() else None
    res["P(large) by ask"] = {lab: [r4(D.large[s].mean()), int(s.sum())] for lab, s in (("<0.3", D.ask < 0.3), ("0.3-0.5", (D.ask >= 0.3) & (D.ask < 0.5)), ("0.5-0.7", (D.ask >= 0.5) & (D.ask < 0.7)), (">=0.7", D.ask >= 0.7))}
    res["P(large) by rel"] = {lab: [r4(D.large[s].mean()), int(s.sum())] for lab, s in (("<60", D.rel < 60), ("60-180", (D.rel >= 60) & (D.rel < 180)), ("180-300", D.rel >= 180))}
    D.to_parquet(C + "/it11/large_dec.parquet")
    q = D.tick.quantile(np.linspace(0, 1, 11)).to_numpy()
    dec = np.clip(np.searchsorted(q, D.tick, side="right") - 1, 0, 9)
    res["P(large) by tick decile"] = {f"d{k} [{q[k]:.3f},{q[k+1]:.3f})": [r4(D.large[dec == k].mean()), int((dec == k).sum())] for k in range(10)}
    for w, g in D.groupby("w"):
        qq = g.tick.quantile([0.5, 0.8, 0.9, 0.95]).to_numpy()
        res.setdefault("P(large) by tick band per wallet", {})[w] = {lab: [r4(g.large[s_].mean()), int(s_.sum())] for lab, s_ in
                                                                   (("<q50", g.tick < qq[0]), ("q50-80", (g.tick >= qq[0]) & (g.tick < qq[1])), ("q80-90", (g.tick >= qq[1]) & (g.tick < qq[2])),
                                                                    ("q90-95", (g.tick >= qq[2]) & (g.tick < qq[3])), (">=q95", g.tick >= qq[3]))}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
