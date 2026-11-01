"""Iteration 11 (panel iter10 assumptions P2 = X97): is the size rule fed by REALIZED fills (own-net feedback, lean10's ceiling)
or by intentions / a slow regime? Natural experiment on the live decision record of 10-31 14:55-17:55 (development).
Decisions: won races (taker-first orders, arrival a = match - 150 ms, filled at a + 150) and located lost races (maker-first
orders placed at the old ask, it9/ins9b_M lost_300 / lost_1000, arrival a = insertion - 150, first maker fill at m1, often
seconds later). For each decision i, the NEXT operator decision j on the same window in (a_i + 200 ms, a_i + 30 s]:
large_j (order size >= 90 shares, the large menu size on 10-31), same outcome or not, same wallet or not. R_ij = i had a fill by
a_j - 30 ms (won: always; lost: m1 <= a_j - 30). Own-net feedback predicts P(large_j on the same outcome) higher with R = 1 and
P(large_j on the other outcome) lower; intention or regime sizing predicts no difference. Exogenous split of the losses: crowd
orders queued ahead in the hold (k_ahead >= 1, queue10) vs none (maker requote). Also a logistic of large_j on R, Z_i large,
same outcome and their interactions with wallet fixed effects, and the block-clock check of the operator's REALIZED vs SENT
net (sent = every decision's size, realized = fills by a_j) as predictors of large_j (own state; reported, never a feature).
Usage: python size11.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import ins9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
A, B = 1793458500, 1793469300
D = 150
OPS = set(L.W) | {"0xd84403efd50b49a1d8a7181627e00307e6ea5908"}
LARGE = 90


def r4(x):
    return round(float(x), 4)


def main(out):
    tokmap = {}
    for r in L.recs("btc5m_clob_raw2", A - 600, B + 60):
        if r.get("k") == "S":
            tokmap[str(r["u"])] = (int(r["m"]), True); tokmap[str(r["d"])] = (int(r["m"]), False)
    tm = pd.read_parquet(C + "/it10/txms10.parquet"); mt = dict(zip(tm.tx, tm.m))
    o, d = ins9.load_orders(A, B)
    o["mstart"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[0]); o["is_up"] = o.token.map(lambda t: tokmap.get(t, (np.nan, None))[1])
    o = o[o.mstart.notna()].copy()
    o["m0"] = o.tx0.str.lower().map(mt)
    o["mM"] = o.txM.str.lower().map(mt) if "txM" in o else np.nan
    won = o[(o["first"] == "T") & o.m0.notna() & o.Z.notna()].copy()
    Mi = pd.read_parquet(C + "/it9/ins9b_M.parquet"); Mi = Mi[Mi.s_ins.notna() & Mi.rcls.isin(["lost_300", "lost_1000"])].copy()
    # crowd queue ahead (queue10)
    cd = pd.concat([pd.read_parquet(C + "/it9/cd9.parquet"), pd.read_parquet(C + "/it10/cdall10.parquet")], ignore_index=True)
    cd["m"] = cd.tx.str.lower().map(mt)
    cr = cd[(cd.role == "T") & ~cd.maker.isin(OPS) & (cd.oside == 0) & cd.m.notna()].drop_duplicates(["tx", "maker", "token"]).copy()
    cr["st"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[0]); cr["up"] = cr.token.astype(str).map(lambda x: tokmap.get(x, (np.nan, None))[1])
    cr = cr[cr.st.notna()]
    crg = {(int(k[0]), bool(k[1])): np.sort(g.m.to_numpy(np.int64)) for k, g in cr.groupby(["st", "up"])}
    ev = pd.concat([pd.DataFrame({"st": won.mstart.astype(int), "up": won.is_up.astype(bool), "a": won.m0.astype(np.int64) - D, "won": True,
                                  "Z": won.Z.astype(float), "w": won.w, "fill_t": won.m0.astype(np.int64), "shT": won.shT.astype(float)}),
                    pd.DataFrame({"st": Mi.mstart.astype(int), "up": Mi.is_up.astype(bool), "a": Mi.s_ins.astype(np.int64) - D, "won": False,
                                  "Z": Mi.Z.astype(float), "w": Mi.w, "fill_t": Mi.m1.astype(float).fillna(9e18).astype(np.int64), "shT": 0.0})],
                   ignore_index=True).sort_values(["st", "a"]).reset_index(drop=True)
    kah = np.zeros(len(ev))
    for i, (st, up, a) in enumerate(zip(ev.st.to_numpy(), ev.up.to_numpy(), ev.a.to_numpy(np.int64))):
        g = crg.get((int(st), bool(up)))
        if g is not None:
            kah[i] = np.searchsorted(g, a + D) - np.searchsorted(g, a)
    ev["k_ahead"] = kah
    ev["large"] = ev.Z >= LARGE
    res = {"decisions": int(len(ev)), "won": int(ev.won.sum()), "lost": int((~ev.won).sum()), "large_share": r4(ev.large.mean()),
           "large_by_wallet": {w: [r4(g.large.mean()), int(len(g))] for w, g in ev.groupby("w")},
           "size_values": {str(int(k)): int(v) for k, v in ev.Z.round().value_counts().head(8).items()}}
    # pairs: i -> next operator decision j in the same window within (a_i + 200, a_i + 30000]
    rows = []
    for st, g in ev.groupby("st"):
        g = g.sort_values("a")
        aa = g.a.to_numpy(np.int64); up = g.up.to_numpy(bool); won_ = g.won.to_numpy(bool); Z = g.Z.to_numpy(float)
        ft = g.fill_t.to_numpy(np.int64); w = g.w.to_numpy(); lg = g.large.to_numpy(bool); ka = g.k_ahead.to_numpy()
        for i in range(len(g)):
            j = np.searchsorted(aa, aa[i] + 200, "right")
            # next decision on the same outcome and on the other outcome (each the first one after a_i + 200 ms within 30 s)
            for same in (True, False):
                jj = j
                while jj < len(g) and aa[jj] <= aa[i] + 30000 and (up[jj] == up[i]) != same:
                    jj += 1
                if jj < len(g) and aa[jj] <= aa[i] + 30000:
                    rows.append((st, i, same, bool(won_[i]), bool(lg[i]), w[i], w[jj], bool(lg[jj]), int(aa[jj] - aa[i]),
                                 bool(ft[i] <= aa[jj] - 30), float(ka[i])))
    P = pd.DataFrame(rows, columns=["st", "i", "same", "won_i", "large_i", "w_i", "w_j", "large_j", "lag", "R", "k_ahead_i"])
    res["pairs"] = int(len(P))
    tab = {}
    for same in (True, False):
        for li in (True, False):
            s = (P.same == same) & (P.large_i == li)
            row = {}
            for lab, k in (("won", P.won_i), ("lost_any", ~P.won_i), ("lost_unfilled_by_j", ~P.won_i & ~P.R), ("lost_filled_by_j", ~P.won_i & P.R),
                           ("lost_crowd_ahead", ~P.won_i & (P.k_ahead_i >= 1)), ("lost_no_crowd_ahead", ~P.won_i & (P.k_ahead_i == 0))):
                kk = s & k
                row[lab] = [r4(P.large_j[kk].mean()) if kk.any() else None, int(kk.sum())]
            tab[f"{'same' if same else 'other'}_outcome_after_{'large' if li else 'small'}_i"] = row
    res["P(large_j)"] = tab
    # same-wallet pairs only
    tab2 = {}
    for same in (True, False):
        s = (P.same == same) & (P.w_i == P.w_j)
        tab2[f"{'same' if same else 'other'}_outcome_same_wallet"] = {lab: [r4(P.large_j[s & k].mean()) if (s & k).any() else None, int((s & k).sum())]
                                                                    for lab, k in (("R=1", P.R), ("R=0", ~P.R), ("won", P.won_i), ("lost", ~P.won_i))}
    res["P(large_j) same wallet"] = tab2
    # logistic with wallet FE: large_j ~ R + same + R*same + large_i + large_i*same (+ lag)
    X = pd.DataFrame({"R": P.R.astype(float), "same": P.same.astype(float), "Rxsame": (P.R & P.same).astype(float),
                      "large_i": P.large_i.astype(float), "large_i_x_same": (P.large_i & P.same).astype(float),
                      "loglag": np.log(P.lag / 1000.0)})
    for w in ("DS", "GF", "XM"):
        X[f"wj_{w}"] = (P.w_j == w).astype(float)
    import statsmodels.api as sm
    try:
        m = sm.Logit(P.large_j.astype(float), sm.add_constant(X)).fit(disp=0, cov_type="cluster", cov_kwds={"groups": P.st})
        res["logit_large_j"] = {k: [r4(m.params[k]), r4(m.bse[k])] for k in ("R", "same", "Rxsame", "large_i", "large_i_x_same", "loglag")}
    except Exception as ex:
        res["logit_error"] = repr(ex)
    # realized vs sent operator net on the outcome at each decision (own state): which predicts large better?
    rn, sn = [], []
    for st, g in ev.groupby("st"):
        g = g.sort_values("a")
        aa = g.a.to_numpy(np.int64); up = g.up.to_numpy(bool); Z = g.Z.to_numpy(float); ft = g.fill_t.to_numpy(np.int64)
        sgn = np.where(up, 1.0, -1.0)
        for j in range(len(g)):
            prev = np.arange(j)
            sent = float(np.sum(sgn[prev] * Z[prev])); real = float(np.sum((sgn[prev] * Z[prev])[ft[prev] <= aa[j] - 30]))
            o_ = 1.0 if up[j] else -1.0
            rn.append(o_ * real); sn.append(o_ * sent)
    ev2 = ev.sort_values(["st", "a"]).reset_index(drop=True)
    ev2["net_real_on_o"] = rn; ev2["net_sent_on_o"] = sn
    ev2["dsr"] = ev2.net_sent_on_o - ev2.net_real_on_o
    y = ev2.large.to_numpy()
    if y.any():
        res["auc_large_by_operator_net_on_o (own state)"] = {"realized": r4(roc_auc_score(y, ev2.net_real_on_o)), "sent": r4(roc_auc_score(y, ev2.net_sent_on_o))}
        # partial: realized and sent together
        Xn = np.c_[np.sign(ev2.net_real_on_o) * np.log1p(np.abs(ev2.net_real_on_o)), np.sign(ev2.dsr) * np.log1p(np.abs(ev2.dsr))]
        mm = LogisticRegression(max_iter=2000).fit(Xn, y)
        res["logit_large_on_realized_and_sent_minus_realized"] = [r4(c) for c in mm.coef_[0]]
        res["P(large) by sign of net_real / net_sent"] = {f"real{a_}_sent{b_}": [r4(y[(np.sign(ev2.net_real_on_o) == a_) & (np.sign(ev2.net_sent_on_o) == b_)].mean())
                                                                               if ((np.sign(ev2.net_real_on_o) == a_) & (np.sign(ev2.net_sent_on_o) == b_)).any() else None,
                                                                               int(((np.sign(ev2.net_real_on_o) == a_) & (np.sign(ev2.net_sent_on_o) == b_)).sum())]
                                                        for a_ in (-1, 0, 1) for b_ in (-1, 0, 1)}
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))[:6000])


if __name__ == "__main__":
    main(sys.argv[1])
