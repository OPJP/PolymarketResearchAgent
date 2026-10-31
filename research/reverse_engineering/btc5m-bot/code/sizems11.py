"""Iteration 11 (F6 / X84 follow-up): the live record says the LARGE size follows the tick strength at the decision (large11:
univariate AUC 0.72, DS 0.73 / GF 0.68 / XM 0.75), but iteration 9 found nothing at the block clock with 1-s spot moves ending at
s - 2 (sizetick9: 0.45-0.53). Retest at the block clock with MILLISECOND Binance USD-M BTCUSDT aggTrades (fut/<day>.parquet,
10-09..22): for every taker-first order of the calldata sample (b1_orders_sample, BUILD and VALIDATE hours), the trigger tick
lies in [bt - 3.0 s, bt - 0.2 s] (bt = first fill's block ts, an integer second; match <= bt, arrival = match - 150 ms, venue
tick ~100-150 ms before the arrival). Features: the max 300-ms (and 500-ms) trade-price move toward o in that window (bp), the
max absolute move, and the move toward o over the whole window. Within-wallet AUC of large vs small (large = the hour's larger
menu size), BUILD and VALIDATE separately; logistic fit on BUILD scored on VALIDATE.
Usage: python sizems11.py OUT_JSON"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = _ROOT + "/.cache/re/btc5m-bot"
VAL0 = 1792108800


def r4(x):
    return round(float(x), 4)


def main(out):
    b = pd.read_parquet(C + "/b1_orders_sample.parquet")
    b = b[b.roles.str[0] == "T"].copy()
    b["hr"] = (b.first_ts // 3600).astype(int)
    mins = b.groupby("hr")["size"].min()
    b["large"] = (b["size"] > b.hr.map(mins) + 1e-9).astype(int)
    b = b[b.groupby("hr")["size"].transform("nunique") >= 2]
    rows = []
    for day, g in b.groupby(b.first_ts // 86400 * 86400):
        p = f"{C}/fut/{int(day)}.parquet"
        if not os.path.exists(p):
            continue
        f = pd.read_parquet(p, columns=["T", "p"])
        T = f["T"].to_numpy(np.int64); px = f["p"].to_numpy(float)
        # 50-ms last-price grid over the day for fast window maxima
        g0 = int(day) * 1000; n = 86400 * 20
        idx = np.searchsorted(T, g0 + np.arange(n) * 50, "right") - 1
        grid = px[np.clip(idx, 0, None)]; grid[idx < 0] = np.nan
        lg = np.log(grid) * 1e4
        for r in g.itertuples():
            bt = int(r.first_ts) * 1000
            k0 = (bt - 3000 - g0) // 50; k1 = (bt - 200 - g0) // 50
            if k0 < 10 or k1 >= n:
                continue
            sg = 1.0 if r.is_up else -1.0
            seg = lg[k0 - 10:k1 + 1]
            m300 = sg * (seg[6:] - seg[:-6]); m500 = sg * (seg[10:] - seg[:-10])
            rows.append((r.wal, int(r.large), bool(r.val), r.hr, np.nanmax(m300), np.nanmax(np.abs(seg[6:] - seg[:-6])), np.nanmax(m500),
                         sg * (lg[k1] - lg[k0])))
        del f, T, px, grid, lg
    D = pd.DataFrame(rows, columns=["w", "large", "val", "hr", "max300_to", "max300_abs", "max500_to", "win_to"])
    res = {"orders": int(len(D)), "large_share": r4(D.large.mean()), "by_split": {}}
    feats = ["max300_to", "max300_abs", "max500_to", "win_to"]
    for split, sel in (("BUILD", ~D.val), ("VALIDATE", D.val)):
        for w, g in D[sel].groupby("w"):
            if g.large.nunique() == 2:
                res["by_split"].setdefault(split, {})[w] = {"n": int(len(g)), "large": r4(g.large.mean()), **{f: r4(roc_auc_score(g.large, g[f].fillna(0))) for f in feats}}
    for w, g in D.groupby("w"):
        tr, te = g[~g.val], g[g.val]
        if tr.large.nunique() == 2 and te.large.nunique() == 2:
            X = lambda z: np.c_[np.tanh(z.max300_to / 2), np.tanh(z.max300_abs / 2), np.tanh(z.max500_to / 2), np.tanh(z.win_to / 3)]
            m = LogisticRegression(max_iter=2000).fit(X(tr), tr.large)
            res.setdefault("fit_BUILD_score_VALIDATE_auc", {})[w] = r4(roc_auc_score(te.large, m.predict_proba(X(te))[:, 1]))
    q = D.max300_to.quantile([0.5, 0.8, 0.9, 0.95]).to_numpy()
    res["P(large) by max300_to band (pooled)"] = {lab: [r4(D.large[s].mean()), int(s.sum())] for lab, s in
                                                  (("<q50", D.max300_to < q[0]), ("q50-80", (D.max300_to >= q[0]) & (D.max300_to < q[1])), ("q80-90", (D.max300_to >= q[1]) & (D.max300_to < q[2])),
                                                   ("q90-95", (D.max300_to >= q[2]) & (D.max300_to < q[3])), (">=q95", D.max300_to >= q[3]))}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
