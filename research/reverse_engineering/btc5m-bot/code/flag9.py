"""Iteration 9 (panel iter8 information P3, flagged-instant part; the selectivity question): at the instants the decoded
hazard flags, what happens instead of a cluster decision? FULL hazard design (stale9.X_of 'full'), positives = DECISIONS
(taker matches + lost-race insertions, ins9b), fit on interval A (10-31 14:55-16:04), scored on C (16:33-17:55), never refit.
For grid points in the top 1% / 3% of the score and for the bottom 50%, classify [t + 100, t + 600) on outcome o:
  decision (cluster match or lost-race insertion on o) / another taker BUYS o (raw-feed trades, cluster txs excluded) /
  o's ask moves UP with no trade (a requote) / nothing.
And P(decision | flagged) by the cluster's own slot state (a cluster taker match on any outcome of the window in [t - 300, t):
reported as own state, not a model feature) and by window time.
Usage: python flag9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, gate8
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    gA, tkA, _ = stale9.grid(a, b, lost); gC, tkC, _ = stale9.grid(c0, c1, lost)
    dA = stale9.stack(gA, 2.0, "any"); dC = stale9.stack(gC, 2.0, "any")
    XA, XC = stale9.X_of(dA, "full"), stale9.X_of(dC, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    lr = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, dA.y_dec)
    p = lr.predict_proba((XC - mu) / sd)[:, 1]
    dC["p"] = p
    res = {"auc_C_ydec": round(float(roc_auc_score(dC.y_dec, p)), 4), "n": int(len(dC)), "base_rate": round(float(dC.y_dec.mean()), 4)}
    # other takers' BUY trades of o and o's touch on C
    tr = []
    ctx = set(tkC.tx.str.lower())
    for r in L.recs("btc5m_clob_raw2", c0 - 60, c1 + 60):
        if r.get("k") == "x" and r.get("d") == "BUY":
            h = (r.get("h") or "").lower()
            if h and h not in ctx:
                tr.append((int(r["s"]), int(r["m"]), int(r.get("u") or 0)))
    T = pd.DataFrame(tr, columns=["s", "m", "u"])
    oth = {k: np.sort(g.s.to_numpy(np.int64)) for k, g in T.groupby(["m", "u"])}
    R = gate8.raw_touch("btc5m_clob_raw2", c0, c1)
    tch = {m: (g.s.to_numpy(np.int64), g.bb.to_numpy(float), g.ba.to_numpy(float)) for m, g in R.groupby("m")}
    cm = {}
    for s0, g in tkC.groupby("start"):
        cm[int(s0)] = np.sort(g.m.to_numpy(np.int64))
    t = dC.t.to_numpy(np.int64); st = dC.st.to_numpy(np.int64); o = dC.o.to_numpy(bool)
    other = np.zeros(len(t), bool); requote = np.zeros(len(t), bool); busy = np.zeros(len(t), bool)
    for i in range(len(t)):
        arr = oth.get((int(st[i]), int(o[i])))
        if arr is not None:
            j0 = np.searchsorted(arr, t[i] + 100); j1 = np.searchsorted(arr, t[i] + 600)
            other[i] = j1 > j0
        tc = tch.get(int(st[i]))
        if tc is not None:
            rs, bb, ba = tc
            i0 = np.searchsorted(rs, t[i] + 100, "right") - 1; i1 = np.searchsorted(rs, t[i] + 600, "right") - 1
            if i0 >= 0 and i1 >= 0:
                a0 = ba[i0] if o[i] else 1 - bb[i0]; a1 = ba[i1] if o[i] else 1 - bb[i1]
                requote[i] = a1 > a0 + 1e-6
        cmm = cm.get(int(st[i]))
        if cmm is not None:
            busy[i] = np.searchsorted(cmm, t[i]) > np.searchsorted(cmm, t[i] - 300)
    y = dC.y_dec.to_numpy(bool)
    q99, q97, q50 = np.quantile(p, [0.99, 0.97, 0.5])
    for nm, k in (("top1pct", p >= q99), ("top3pct", p >= q97), ("bottom50pct", p <= q50)):
        nd = k & ~y
        res[nm] = {"n": int(k.sum()), "P(decision)": round(float(y[k].mean()), 4),
                   "no_decision": {"n": int(nd.sum()), "other_taker_buys_o": round(float(other[nd].mean()), 4),
                                   "ask_up_no_other_trade": round(float((requote[nd] & ~other[nd]).mean()), 4),
                                   "nothing": round(float((~other[nd] & ~requote[nd]).mean()), 4)},
                   "with_decision": {"other_taker_buys_o_too": round(float(other[k & y].mean()), 4) if (k & y).any() else None},
                   "P(decision|busy)": [round(float(y[k & busy].mean()), 4) if (k & busy).any() else None, int((k & busy).sum())],
                   "P(decision|not busy)": [round(float(y[k & ~busy].mean()), 4) if (k & ~busy).any() else None, int((k & ~busy).sum())]}
    rel = (t / 1000 - st)
    k = p >= q97
    res["top3pct_P(decision)_by_rel"] = {f"{lo}-{hi}": [round(float(y[k & (rel >= lo) & (rel < hi)].mean()), 4), int((k & (rel >= lo) & (rel < hi)).sum())]
                                         for lo, hi in ((0, 60), (60, 120), (120, 180), (180, 240), (240, 300))}
    ask = dC.ask.to_numpy(float)
    res["top3pct_P(decision)_by_ask"] = {f"{lo}-{hi}": [round(float(y[k & (ask >= lo) & (ask < hi)].mean()), 4), int((k & (ask >= lo) & (ask < hi)).sum())]
                                         for lo, hi in ((0.0, 0.15), (0.15, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.0))}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
