"""Iteration 10 (X77 / X83, panel iter9 mechanics P1 and assumptions P2): are the instants the decoded hazard flags and the
cluster 'skips' hidden decisions (unfilled lost races)? FULL hazard design (stale9.X_of 'full'), decision label (matches +
located lost races), fit on A (14:55-16:04), scored on C (16:33-17:55), never refit (as flag9). For flagged grid points
(top 1% / 3%) split into taken / skipped, and for the bottom 50%: the rate of UNKNOWN old-ask insertions on o (not a located
cluster order; ghost10's candidates) in [t + 100, t + 900) by size class: 60 (XM's small size on 10-31; attributable by the
fan-out fingerprint, ghost10b), 100 (the large size of all wallets), 30 (DS / GF small, also a common crowd size), and crowd
sizes (5, 10, 20, 24, 50, 64). If skips were hidden cluster decisions, the 60- and 100-share rates at skipped instants would
approach those at taken instants, relative to the crowd classes. Also episodes (assumptions P2): runs of flagged points
(same window and outcome, gaps <= 1 s), the episode take rate, and the constant-hazard null by run length (p fitted on A).
Usage: python flag10.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
CLS = {"z60": (60,), "z100": (100,), "z30": (30,), "crowd": (5, 10, 20, 24, 50, 64)}


def episodes(d, flag, gap=1000):
    d = d.assign(flag=flag)[flag].sort_values(["st", "o", "t"])
    ep = np.zeros(len(d), int); e = -1; prev = None
    for i, (st, o, t) in enumerate(zip(d.st.to_numpy(), d.o.to_numpy(), d.t.to_numpy())):
        if prev is None or prev[0] != st or prev[1] != o or t - prev[2] > gap:
            e += 1
        ep[i] = e; prev = (st, o, t)
    d["ep"] = ep
    g = d.groupby("ep").agg(n=("t", "size"), y=("y_dec", "max"), st=("st", "first"))
    return g


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    a, b = stale9.IV["A"]; c0, c1 = stale9.IV["C"]
    gA, tkA, _ = stale9.grid(a, b, lost); gC, tkC, _ = stale9.grid(c0, c1, lost)
    dA = stale9.stack(gA, 2.0, "any"); dC = stale9.stack(gC, 2.0, "any")
    XA, XC = stale9.X_of(dA, "full"), stale9.X_of(dC, "full")
    mu, sd = XA.mean(0), XA.std(0) + 1e-9
    lr = LogisticRegression(max_iter=3000).fit((XA - mu) / sd, dA.y_dec)
    pA = lr.predict_proba((XA - mu) / sd)[:, 1]; pC = lr.predict_proba((XC - mu) / sd)[:, 1]
    res = {"auc_C_ydec": round(float(roc_auc_score(dC.y_dec, pC)), 4), "n_C": int(len(dC))}
    F = pd.read_parquet(C + "/it10/ghost_cand.parquet")
    U = F[~F.known_cluster].copy(); U["zi"] = U.z.round(0)
    idx = {}
    for nm, zs in CLS.items():
        g = U[U.zi.isin(zs)]
        idx[nm] = {k: np.sort(x.s.to_numpy(np.int64)) for k, x in g.groupby(["m", "bid"])}
    t = dC.t.to_numpy(np.int64); st = dC.st.to_numpy(np.int64); o = dC.o.to_numpy(bool); y = dC.y_dec.to_numpy(bool)
    cnt = {nm: np.zeros(len(t)) for nm in CLS}
    for nm in CLS:
        for i in range(len(t)):
            arr = idx[nm].get((int(st[i]), bool(o[i])))
            if arr is not None:
                cnt[nm][i] = np.searchsorted(arr, t[i] + 900) - np.searchsorted(arr, t[i] + 100)
    q99, q97, q50 = np.quantile(pC, [0.99, 0.97, 0.5])
    for nm, k in (("top1pct", pC >= q99), ("top3pct", pC >= q97), ("bottom50pct", pC <= q50)):
        row = {"n": int(k.sum()), "P(decision)": round(float(y[k].mean()), 4)}
        for part, kk in (("taken", k & y), ("skipped", k & ~y)):
            row[part] = {c: round(float(cnt[c][kk].mean()), 4) if kk.any() else None for c in CLS}
            row[part]["n"] = int(kk.sum())
        res[nm] = row
    # ratio of 60 / 100 to crowd rates, skipped vs taken
    for nm in ("top1pct", "top3pct"):
        r = res[nm]
        res[nm]["ratio_skipped_over_taken"] = {c: round(r["skipped"][c] / r["taken"][c], 3) if r["taken"][c] else None for c in CLS}
    # episodes (assumptions P2) with the A threshold of the top 3%
    thrA = np.quantile(pA, 0.97)
    eA = episodes(dA, pA >= thrA); eC = episodes(dC, pC >= thrA)
    pts = dA[pA >= thrA]
    # constant hazard p per flagged point fitted on A episodes: P(taken) = 1 - (1 - p)^n, MLE by grid
    ps = np.linspace(0.01, 0.4, 391)
    ll = [np.sum(eA.y * np.log(1 - (1 - p) ** eA.n) + (1 - eA.y) * eA.n * np.log(1 - p)) for p in ps]
    p_hat = float(ps[int(np.argmax(ll))])
    rows = {}
    for nm, e in (("A", eA), ("C", eC)):
        rr = {"episodes": int(len(e)), "take_rate": round(float(e.y.mean()), 4), "points": int(e.n.sum()),
              "point_take_rate": round(float((dA if nm == 'A' else dC)[(pA if nm == 'A' else pC) >= thrA].y_dec.mean()), 4)}
        for lo, hi in ((1, 1), (2, 3), (4, 9), (10, 10 ** 6)):
            s = (e.n >= lo) & (e.n <= hi)
            if s.any():
                rr[f"run {lo}-{hi}"] = [round(float(e.y[s].mean()), 4), round(float((1 - (1 - p_hat) ** e.n[s]).mean()), 4), int(s.sum())]
        # window overdispersion vs the null
        e2 = e.assign(pp=1 - (1 - p_hat) ** e.n)
        gw = e2.groupby("st").agg(o_=("y", "sum"), e_=("pp", "sum"), v_=("pp", lambda x: float(np.sum(x * (1 - x)))), k=("y", "size"))
        gw = gw[gw.k >= 2]
        chi = float(np.sum((gw.o_ - gw.e_) ** 2 / np.maximum(gw.v_, 1e-9)))
        rr["window_chi2_df"] = [round(chi / max(len(gw), 1), 3), int(len(gw))]
        rows[nm] = rr
    res["episodes_top3_gap1s"] = {"p_hat_per_point_A": p_hat, **rows}
    json.dump(res, open(out, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))


if __name__ == "__main__":
    main(sys.argv[1])
