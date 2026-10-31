"""Iteration 9, historical check of finding 18 (live: the large size follows the tick strength at the decision): VALIDATE /
BUILD calldata sample orders (b1_orders_sample.parquet, signed sizes), decision second s = block second of the first fill.
Short-horizon Binance spot move toward o ending at s - 2 (point-in-time: second s - 2 is published at s - 1) over 1, 2, 3, 5 s
(binance_1s.parquet), and the size8 market analog (return since the open). Within-wallet univariate AUC of the large size on
VALIDATE hours, and a BUILD-fitted logistic (controls + short ticks) scored on VALIDATE hours, with and without the four-wallet
operator net (w4size9 design).
Usage: python sizetick9.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
VAL0 = 1792108800
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def main(out):
    b = pd.read_parquet(os.path.join(C, "b1_orders_sample.parquet"))
    b = b[np.isfinite(b.first_ts) & np.isfinite(b.start_ts)].copy()
    b["hr"] = (b.first_ts // 3600).astype(int)
    mins = b.groupby("hr")["size"].agg(lambda s: s.value_counts().index[s.value_counts().values >= 0.03 * len(s)].min())
    b["large"] = (b["size"] > b.hr.map(mins) + 1e-9).astype(int)
    b["up"] = b.is_up.astype(bool); b["W"] = b.wal.map(lambda x: WAL.get(str(x).lower(), x))
    bn = pd.read_parquet(os.path.join(C, "binance_1s.parquet"))
    tcol = [c for c in bn.columns if c in ("sec", "ts", "t", "open_time", "time")][0]
    ccol = [c for c in bn.columns if c in ("close", "c", "px")][0]
    px = pd.Series(bn[ccol].values.astype(float), index=(bn[tcol].values // (1000 if bn[tcol].max() > 1e11 else 1)).astype(np.int64))
    s = b.first_ts.values.astype(np.int64)
    sg = np.where(b.up, 1.0, -1.0)
    p2 = px.reindex(s - 2).values
    for k in (1, 2, 3, 5):
        b[f"tk{k}"] = np.log(p2 / px.reindex(s - 2 - k).values) * 1e4 * sg
    b["mret"] = np.log(p2 / px.reindex(b.start_ts.values.astype(np.int64) - 1).values) * 1e4 * sg
    b["lim"] = b["limit"].astype(float); b["absp"] = np.abs(b.lim - 0.5); b["rel"] = (b.first_ts - b.start_ts) / 300.0
    b = b[np.isfinite(b.tk5) & np.isfinite(b.mret)]
    res = {"n": int(len(b))}
    for W in ("DS", "GF", "XM"):
        d = b[b.W == W]; tr, te = d[d.first_ts < VAL0], d[d.first_ts >= VAL0]
        r = {"n_val": int(len(te)), "large_val": round(float(te.large.mean()), 4)}
        for k in ("tk1", "tk2", "tk3", "tk5", "mret"):
            r[f"uni_{k}"] = round(float(roc_auc_score(te.large, te[k])), 4)
            r[f"uni_abs_{k}"] = round(float(roc_auc_score(te.large, np.abs(te[k]))), 4)
        def X(z, tick):
            cols = [z.rel, z.absp, z.lim]
            if tick:
                cols += [np.tanh(z.tk1 / 1), np.tanh(z.tk2 / 1), np.tanh(z.tk3 / 2), np.tanh(z.tk5 / 3), np.abs(z.tk2)]
            return np.column_stack(cols)
        for nm, tick in (("ctrl", False), ("ctrl+ticks", True)):
            p = LogisticRegression(max_iter=1000).fit(X(tr, tick), tr.large).predict_proba(X(te, tick))[:, 1]
            r[f"auc_{nm}"] = round(float(roc_auc_score(te.large, p)), 4)
        res[W] = r
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
