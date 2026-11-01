"""Iteration 9, selectivity: does the OPERATOR'S OWN BOOK gate the decision at a flagged instant (set completion)? Own state,
reported separately (never a presence feature). For outcome o at grid point t (interval C, top 3% of the FULL hazard fit on
A, decision label): the three wallets' holdings in the window from on-chain fills whose match ms (raw-feed trade with the
same tx hash) is < t - 300 ms: shares and average price per outcome. unpaired_other = max(H_other - H_o, 0) (buying o would
complete sets); pair_cost = ask_o + avg price of the other outcome's holdings. P(decision) by these states, and the AUC of
-pair_cost / unpaired_other for taken vs skipped flagged instants.
Usage: python setgate9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
EX = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"}


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    gA, _, _ = stale9.grid(*stale9.IV["A"], lost); gC, tkC, _ = stale9.grid(*stale9.IV["C"], lost)
    dA = stale9.stack(gA, 2.0, "any"); dC = stale9.stack(gC, 2.0, "any")
    XA, XC = stale9.X_of(dA, "full"), stale9.X_of(dC, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    p = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, dA.y_dec).predict_proba((XC - mu) / sd)[:, 1]
    c0, c1 = stale9.IV["C"]
    # own fills with match ms and window / outcome
    f = pd.read_parquet(C + "/it9/own_1231_12_18.parquet")
    f = f[(f.ts >= c0 - 400) & (f.ts < c1 + 60)].copy()
    tok = {}; txms = {}
    for r in L.recs("btc5m_clob_raw2", c0 - 600, c1 + 60):
        k = r.get("k")
        if k == "S":
            tok[str(r["u"])] = (int(r["m"]), True); tok[str(r["d"])] = (int(r["m"]), False)
        elif k == "x" and r.get("h"):
            h = r["h"].lower(); txms[h] = min(txms.get(h, 10 ** 18), int(r["s"]))
    f["token"] = f.token.astype(str)
    f["st"] = f.token.map(lambda t: tok.get(t, (np.nan, None))[0]); f["up"] = f.token.map(lambda t: tok.get(t, (np.nan, None))[1])
    f["ms"] = f.tx.str.lower().map(txms)
    f = f[f.st.notna() & f.ms.notna()].copy()
    f["sh"] = f.tamt / 1e6; f["usd"] = f.mamt / 1e6
    hold = {}
    for (s0, u), g in f.groupby(["st", "up"]):
        g = g.sort_values("ms")
        hold[(int(s0), bool(u))] = (g.ms.to_numpy(np.int64), np.cumsum(g.sh.to_numpy()), np.cumsum(g.usd.to_numpy()))
    t = dC.t.to_numpy(np.int64); st = dC.st.to_numpy(np.int64); o = dC.o.to_numpy(bool); ask = dC.ask.to_numpy(float)
    Ho = np.zeros(len(t)); Hx = np.zeros(len(t)); Cx = np.full(len(t), np.nan)
    for i in range(len(t)):
        for own, arrH in ((o[i], "o"), (not o[i], "x")):
            h = hold.get((int(st[i]), bool(own)))
            if h is None:
                continue
            j = np.searchsorted(h[0], t[i] - 300, "left") - 1
            if j < 0:
                continue
            if arrH == "o":
                Ho[i] = h[1][j]
            else:
                Hx[i] = h[1][j]; Cx[i] = h[2][j] / h[1][j]
    unp = np.maximum(Hx - Ho, 0); pair = ask + Cx
    y = dC.y_dec.to_numpy(bool)
    q97 = np.quantile(p, 0.97); k = p >= q97
    res = {"n_top3": int(k.sum()), "P(decision|top3)": round(float(y[k].mean()), 4)}
    def P(m):
        return [round(float(y[m].mean()), 4) if m.any() else None, int(m.sum())]
    res["top3_by_state"] = {"no_holdings_other": P(k & (Hx == 0)), "unpaired_other_0": P(k & (Hx > 0) & (unp == 0)),
                            "unpaired_other_pos_pair<0.97": P(k & (unp > 0) & (pair < 0.97)), "unpaired_other_pos_pair_0.97-1.0": P(k & (unp > 0) & (pair >= 0.97) & (pair < 1.0)),
                            "unpaired_other_pos_pair>=1.0": P(k & (unp > 0) & (pair >= 1.0))}
    kk = k & np.isfinite(pair)
    res["top3_auc_neg_pair_cost"] = round(float(roc_auc_score(y[kk], -pair[kk])), 4) if kk.any() and y[kk].any() and (~y[kk]).any() else None
    res["top3_auc_unpaired_other"] = round(float(roc_auc_score(y[k], unp[k])), 4)
    res["top3_auc_own_net_o(neg=short)"] = round(float(roc_auc_score(y[k], -(Ho - Hx)[k])), 4)
    allk = np.isfinite(pair)
    res["all_grid_by_state"] = {"unpaired_other_pos_pair<0.97": P(allk & (unp > 0) & (pair < 0.97)), "unpaired_other_pos_pair>=1.0": P(allk & (unp > 0) & (pair >= 1.0)),
                                "no_holdings_other": P(Hx == 0)}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
