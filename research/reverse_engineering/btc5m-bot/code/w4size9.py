"""Iteration 9 (panel iter8 mechanics P4 = X66 step 2): add the fourth operator wallet W4 (0xd84403ef...) to the operator net
that drives the large size (size8.py, X49). W4's V2 OrderFilled logs (topic2 = W4) for the calldata sample hours (all pre-H;
holdout asserted), mapped to windows through windows.parquet; the size8 design (BUILD hours -> VALIDATE hours, logistic,
within-wallet AUC) with the operator net from the three wallets vs the four.
Usage: python w4size9.py OUT_JSON"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
import rpc
from fetch_chain import decode

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
C = os.path.join(ROOT, ".cache", "re", "btc5m-bot")
H = 1792713600; VAL0 = 1792108800
W4 = "0xd84403efd50b49a1d8a7181627e00307e6ea5908"
WAL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6": "GF", "0x3048d65321be3497164cdfc2996f94f98a2e7537": "XM", "0xc53375ff94e96100f2b30a4b5775db35218d69a9": "DS"}


def main(out):
    b = pd.read_parquet(os.path.join(C, "b1_orders_sample.parquet"))
    b = b[np.isfinite(b.first_ts) & np.isfinite(b.start_ts)].copy()
    b["hr"] = (b.first_ts // 3600).astype(int)
    mins = b.groupby("hr")["size"].agg(lambda s: s.value_counts().index[s.value_counts().values >= 0.03 * len(s)].min())
    b["large"] = (b["size"] > b.hr.map(mins) + 1e-9).astype(int)
    b["s"] = (b.first_ts - b.start_ts).astype(int); b["up"] = b.is_up.astype(bool)
    b["W"] = b.wal.map(lambda x: WAL.get(str(x).lower(), x))
    f = pd.read_parquet(os.path.join(C, "fills.parquet"), columns=["block", "ts", "wallet", "shares", "start_ts", "is_up"])
    starts = set(b.start_ts.astype(int))
    # block ranges of the sample windows
    fw = f[f.start_ts.astype(int).isin(starts)]
    rng_ = fw.groupby((fw.ts // 3600).astype(int)).block.agg(["min", "max"])
    logs = []
    for h, r in rng_.iterrows():
        a0, b0 = int(r["min"]) - 200, int(r["max"]) + 200
        for a in range(a0, b0 + 1, 2000):
            bb = min(a + 1999, b0)
            for ex in rpc.V2_EXCHANGES:
                logs += [decode(l) for l in rpc.get_logs(ex, a, bb, [rpc.TOPIC_V2, None, [rpc.pad(W4)]])]
    w4 = pd.DataFrame(logs)
    res = {"w4_fills": int(len(w4))}
    if len(w4):
        assert w4.ts.max() < H, "holdout"
        win = pd.read_parquet(os.path.join(C, "windows.parquet"), columns=["start_ts", "up_token", "down_token"])
        tok = {str(r.up_token): (int(r.start_ts), True) for r in win.itertuples()}
        tok.update({str(r.down_token): (int(r.start_ts), False) for r in win.itertuples()})
        w4["start_ts"] = w4.token.map(lambda t: tok.get(str(t), (np.nan, None))[0]); w4["is_up"] = w4.token.map(lambda t: tok.get(str(t), (np.nan, None))[1])
        w4 = w4[w4.start_ts.notna() & (w4.side == 0)].copy()
        w4["shares"] = w4.tamt / 1e6; w4["wallet"] = "W4"
        res["w4_fills_in_windows"] = int(len(w4))
        f2 = pd.concat([f[f.start_ts.astype(int).isin(starts)][["ts", "wallet", "shares", "start_ts", "is_up"]], w4[["ts", "wallet", "shares", "start_ts", "is_up"]]])
    else:
        f2 = f[f.start_ts.astype(int).isin(starts)][["ts", "wallet", "shares", "start_ts", "is_up"]]
    f2["s"] = (f2.ts - f2.start_ts).astype(int); f2["su"] = f2.shares * np.where(f2.is_up.astype(bool), 1.0, -1.0)
    agg = f2.groupby(["start_ts", "wallet", "s"]).su.sum().reset_index()
    grp = {k: g.sort_values("s") for k, g in agg.groupby("start_ts")}
    n3, n4 = [], []
    for r in b.itertuples():
        g = grp.get(r.start_ts)
        if g is None:
            n3.append(0.0); n4.append(0.0); continue
        m = g.s.values <= r.s - 1
        sg = 1.0 if r.up else -1.0
        n4.append(g.su.values[m].sum() * sg); n3.append(g.su.values[m & (g.wallet.values != "W4")].sum() * sg)
    b["net3"] = n3; b["net4"] = n4
    b["lim"] = b["limit"].astype(float); b["absp"] = np.abs(b.lim - 0.5); b["fav"] = (b.lim > 0.5).astype(float); b["rel"] = b.s / 300.0

    def X(d, col):
        return np.column_stack([d.rel, d.absp, d.fav, d.lim, np.tanh(d[col] / 100), np.tanh(d[col] / 300), (d[col] < -200).astype(float)])
    for W in ("DS", "GF", "XM"):
        d = b[b.W == W]; tr, te = d[d.first_ts < VAL0], d[d.first_ts >= VAL0]
        r = {"n_val": int(len(te))}
        for col in ("net3", "net4"):
            p = LogisticRegression(max_iter=1000).fit(X(tr, col), tr.large).predict_proba(X(te, col))[:, 1]
            r[f"auc_ctrl+{col}"] = round(float(roc_auc_score(te.large, p)), 4)
            r[f"uni_{col}"] = round(float(roc_auc_score(te.large, te[col])), 4)
        res[W] = r
    res["w4_share_of_operator_abs_flow"] = round(float(f2[f2.wallet == "W4"].shares.sum() / f2.shares.sum()), 4)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
