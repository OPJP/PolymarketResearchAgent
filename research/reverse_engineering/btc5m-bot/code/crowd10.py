"""Iteration 10 (panel iter9 information P2 = X74): the crowd's signing timestamps as a millisecond-exact decision record of the
shared trigger, and the cluster's participation in it.
Crowd decisions: taker BUY orders of non-operator wallets in every recorded BTC 5m match tx of 10-31 14:55-17:55 (V2 calldata:
it9/cd9 + it10/cdall10) that were signed fresh, 180 <= match - sign <= 2000 ms (match = server ms of the recorded trade), at
their sign_ms. Cluster decisions on the same clock: d = m - 180 ms for taker matches and d = insertion - 180 ms for located
lost races (the arrival is m - D, the last input ~delta = 30 ms earlier; finding 1).
100-ms grid (rel 5..285 s) x outcome; features at t from venue inputs only (six-series microprice moves toward o over
[t - 100, t) and [t - 500, t), the BTC composite over [t - 250, t), number of BTC series moving toward o over [t - 250, t),
a Binance USD-M price-level change toward o in [t - 150, t)) plus o's ask level; labels in [t, t + 100). Fit on A, scored on C:
(i) the crowd model's AUC for the crowd label; (ii) the frozen crowd model's AUC for the CLUSTER label vs a cluster-trained
model with the same features and vs the Polymarket-activity baseline (other trades in [t - 1000, t), o's ask change over
[t - 500, t), |ask - 0.5|); (iii) among the top 3% of the crowd model, P(cluster decision) and taken-vs-skipped AUC.
Usage: python crowd10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, live6, gate8
from lag7 import micro_series, mv
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
OPS = set(L.W) | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908"}
DT = (180, 2000)  # fresh-signed window (ms); argv[2:4] override (iteration 10 also ran the fast crowd 180-260 ms)
SER = (("bf", "BTC"), ("bs", "BTC"), ("ok", "BTC"), ("by", "BTC"), ("bf", "ETH"), ("ok", "ETH"))


def crowd_decisions(tokmap):
    cd = pd.concat([pd.read_parquet(C + "/it9/cd9.parquet"), pd.read_parquet(C + "/it10/cdall10.parquet")], ignore_index=True)
    cd["txl"] = cd.tx.str.lower()
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    cd["m"] = cd.txl.map(mt)
    t = cd[(cd.role == "T") & ~cd.maker.isin(OPS) & (cd.oside == 0) & cd.m.notna()].drop_duplicates(["txl", "maker", "token", "sign_ms"]).copy()
    t["dt"] = t.m - t.sign_ms
    t = t[(t.dt >= DT[0]) & (t.dt <= DT[1])]
    t["st"] = t.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[0]); t["up"] = t.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[1])
    t = t[t.st.notna()]
    return t


def grid(a, b, tokmap, crowd, lost):
    S = micro_series("btc5m_venues2", a, b)
    d = live6.own_taker(stale9.OWN, a - 5, b + 5)
    tok, books, trades = L.load_books(a - 5, b + 5)
    mt = trades.groupby("tx").s_ms.min()
    tk = d[(d.role == "T") & d.token.isin(tok.keys())].copy()
    tk["start"] = tk.token.map(lambda x: tok[x][1]); tk["is_up"] = tk.token.map(lambda x: tok[x][2]); tk["m"] = tk.tx.map(mt)
    tk = tk[tk.m.notna()]
    lo = lost[(lost.s_ins >= (a - 5) * 1000) & (lost.s_ins < (b + 5) * 1000)]
    cl = pd.concat([pd.DataFrame({"st": tk.start.astype(int), "up": tk.is_up.astype(bool), "d": tk.m.astype(np.int64) - 180}),
                    pd.DataFrame({"st": lo.mstart.astype(int), "up": lo.is_up.astype(bool), "d": lo.s_ins.astype(np.int64) - 180})])
    clg = {k: np.sort(g.d.to_numpy(np.int64)) for k, g in cl.groupby(["st", "up"])}
    crg = {k: np.sort(g.sign_ms.to_numpy(np.int64)) for k, g in crowd.groupby(["st", "up"])}
    R = gate8.raw_touch("btc5m_clob_raw2", a, b)
    trn = trades[~trades.tx.isin(set(tk.tx))].copy(); trn["st"] = trn.token.map(lambda x: tok.get(x, (None, -1))[1])
    oth = {k: np.sort(g.s_ms.to_numpy(np.int64)) for k, g in trn.groupby("st")}
    # Binance USD-M L1 mid for price-level changes
    bfT, bfmid = None, None
    rows = []
    for r in L.recs("btc5m_venues2", a - 30, b + 5):
        if r.get("v") == "bf" and r.get("y") == "BTC" and r.get("b") and r.get("a"):
            rows.append((r.get("E") or r["t"], (r["b"] + r["a"]) / 2))
    x = np.array(rows, float); x = x[np.argsort(x[:, 0], kind="stable")]; bfT = x[:, 0].astype(np.int64); bfmid = x[:, 1]
    out = []
    for st0, rg in R.groupby("m"):
        st0 = int(st0)
        g = np.arange((st0 + 5) * 1000, (st0 + 285) * 1000, 100, dtype=np.int64)
        g = g[(g >= a * 1000 + 5000) & (g < b * 1000)]
        if not len(g):
            continue
        rs = rg.s.to_numpy(np.int64); bb = rg.bb.to_numpy(float); ba = rg.ba.to_numpy(float)
        i = np.searchsorted(rs, g, "right") - 1; i5 = np.searchsorted(rs, g - 500, "right") - 1
        ok_ = (i >= 0) & (i5 >= 0)
        om = oth.get(st0, np.array([], np.int64))
        act = (np.searchsorted(om, g, "left") - np.searchsorted(om, g - 1000, "left")).astype(float)
        mvs = {}
        for key in SER:
            if key in S:
                mvs[(key, 100)] = mv(S, key, g - 100, g); mvs[(key, 500)] = mv(S, key, g - 500, g); mvs[(key, 250)] = mv(S, key, g - 250, g)
        j1 = np.searchsorted(bfT, g, "right") - 1; j0 = np.searchsorted(bfT, g - 150, "right") - 1
        dmid = np.where((j0 >= 0) & (j1 >= 0), bfmid[np.clip(j1, 0, None)] - bfmid[np.clip(j0, 0, None)], np.nan)
        for up, sg in ((True, 1.0), (False, -1.0)):
            ask = np.where(ok_, ba[np.clip(i, 0, None)] if up else 1 - bb[np.clip(i, 0, None)], np.nan)
            ask5 = np.where(ok_, ba[np.clip(i5, 0, None)] if up else 1 - bb[np.clip(i5, 0, None)], np.nan)
            row = {"t": g, "st": np.full(len(g), st0), "up": np.full(len(g), up), "ask": ask, "rp": np.sign(np.round((ask - ask5) * 100)), "act": act,
                   "pl": np.nan_to_num(sg * dmid) > 0}
            comp = np.zeros(len(g)); nmov = np.zeros(len(g))
            for key in SER:
                if (key, 100) in mvs:
                    row[f"{key[0]}{key[1]}_100"] = sg * np.nan_to_num(mvs[(key, 100)]); row[f"{key[0]}{key[1]}_500"] = sg * np.nan_to_num(mvs[(key, 500)])
                    if key[1] == "BTC":
                        v = sg * np.nan_to_num(mvs[(key, 250)]); comp += v; nmov += v > 0.002
            row["comp250"] = comp; row["nmov250"] = nmov
            for lab, gg in (("y_crowd", crg.get((st0, up))), ("y_cl", clg.get((st0, up)))):
                if gg is None:
                    row[lab] = np.zeros(len(g), bool)
                else:
                    row[lab] = (np.searchsorted(gg, g + 100, "left") - np.searchsorted(gg, g, "left")) > 0
            out.append(pd.DataFrame(row))
    D = pd.concat(out, ignore_index=True)
    D = D[np.isfinite(D.ask) & (D.ask > 0.03) & (D.ask < 0.97)].reset_index(drop=True)
    return D


def Xv(D):
    cols = [c for c in D.columns if c.endswith("_100") or c.endswith("_500")] + ["comp250", "nmov250"]
    X = D[cols].to_numpy(float)
    X = np.c_[np.clip(X, -3, 3), np.clip(X, 0, 3), D.pl, D.nmov250 >= 2, np.abs(D.ask - 0.5), D.ask]
    return X.astype(float)


def Xb(D):
    return np.c_[D.act, np.log1p(D.act), D.rp == 0, D.rp > 0, D.rp < 0, np.abs(D.ask - 0.5), D.ask].astype(float)


def fit(Xa, ya):
    mu, sd = Xa.mean(0), Xa.std(0) + 1e-9
    m = LogisticRegression(max_iter=3000, C=0.5).fit((Xa - mu) / sd, ya)
    return lambda X: m.predict_proba((X - mu) / sd)[:, 1]


def main(out):
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", 1793458500 - 600, 1793469300 + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    crowd = crowd_decisions(tokmap)
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    DA = grid(a, b, tokmap, crowd, lost); DC = grid(c0, c1, tokmap, crowd, lost)
    res = {"dt_window_ms": list(DT), "crowd_decisions": int(len(crowd)), "crowd_wallets": int(crowd.maker.nunique()),
           "grid_A": int(len(DA)), "grid_C": int(len(DC)),
           "base_crowd_A": round(float(DA.y_crowd.mean()), 4), "base_crowd_C": round(float(DC.y_crowd.mean()), 4),
           "base_cluster_A": round(float(DA.y_cl.mean()), 4), "base_cluster_C": round(float(DC.y_cl.mean()), 4)}
    XA, XC = Xv(DA), Xv(DC); BA, BC = Xb(DA), Xb(DC)
    f_crowd = fit(XA, DA.y_crowd); f_cl = fit(XA, DA.y_cl); f_bc = fit(BA, DA.y_cl); f_bcr = fit(BA, DA.y_crowd)
    pc = f_crowd(XC); pcl = f_cl(XC); pb = f_bc(BC); pbr = f_bcr(BC)
    res["auc_C"] = {"crowd_label_crowd_model": round(float(roc_auc_score(DC.y_crowd, pc)), 4),
                    "crowd_label_pm_activity_baseline": round(float(roc_auc_score(DC.y_crowd, pbr)), 4),
                    "cluster_label_frozen_crowd_model": round(float(roc_auc_score(DC.y_cl, pc)), 4),
                    "cluster_label_cluster_model": round(float(roc_auc_score(DC.y_cl, pcl)), 4),
                    "cluster_label_pm_activity_baseline": round(float(roc_auc_score(DC.y_cl, pb)), 4)}
    # co-occurrence: P(cluster decision) given a crowd decision in the same 100 ms
    yc = DC.y_crowd.to_numpy(bool); yl = DC.y_cl.to_numpy(bool)
    res["P(cluster | crowd decision same 100 ms)_C"] = round(float(yl[yc].mean()), 4)
    res["P(cluster | no crowd decision)_C"] = round(float(yl[~yc].mean()), 4)
    res["P(crowd | cluster decision)_C"] = round(float(yc[yl].mean()), 4)
    q97 = np.quantile(pc, 0.97); k = pc >= q97
    res["top3pct_crowd_model_C"] = {"n": int(k.sum()), "P(crowd)": round(float(yc[k].mean()), 4), "P(cluster)": round(float(yl[k].mean()), 4),
                                    "recall_cluster": round(float(k[yl].mean()), 4)}
    # within the top 3%: taken vs skipped by the cluster, from the venue features (fit on A's top 3% by the A threshold)
    qa = np.quantile(f_crowd(XA), 0.97); ka = f_crowd(XA) >= qa
    if DA.y_cl[ka].nunique() == 2 and DC.y_cl[k].nunique() == 2:
        g_ = fit(XA[ka], DA.y_cl[ka])
        res["top3pct_taken_vs_skipped_auc_C"] = round(float(roc_auc_score(DC.y_cl[k], g_(XC[k]))), 4)
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    if len(sys.argv) > 3:
        DT = (float(sys.argv[2]), float(sys.argv[3]))
    main(sys.argv[1])
