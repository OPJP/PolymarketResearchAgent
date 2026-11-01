"""Iteration 13 (X121 / X118 step 3; pre-registered in NOTES.md iteration 13 before any VALIDATE score): TWO-STREAM per-second
net-flow models. Targets (two13.py labels, per block second of the window, Up +): yL = the operator's LARGE-order signed
fill flow, yS = its SMALL-order flow; diagnostic yT = yL + yS. Features: nf12b's set (cell features of the Up cell, the
Down cell's tape terms, spot-only slow features; PIT as cells.py) + W13 window-state features from Binance 1-s closes
(usable from t + 2): for k in (1.5, 3.0) bp, the sign and rel of the first 1-s move with |r| >= k since the open, and the
counts of such up / down moves so far. No own state. Fit on BUILD (10-09..15) only, same PARAMS / ROUNDS as nf12;
predictions on VALIDATE -> .cache/re/btc5m-bot/it13/ls13_val.parquet; window-level scores -> results/ls13.json."""
import os, sys, json, time
os.environ["NF12_VARIANT"] = "spot"
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lightgbm as lgb
import nf12
C = _ROOT + "/.cache/re/btc5m-bot"
OUT = f"{C}/it13"; os.makedirs(OUT, exist_ok=True)
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
CODE = os.path.dirname(os.path.abspath(__file__))
VAL0, H = nf12.VAL0, nf12.H
KS = (1.5, 3.0)
W13 = [f"{a}_{str(k).replace('.', 'p')}" for k in KS for a in ("fsg", "frel", "nup", "ndn")]


def w13_feats(X, px, s0):
    st = X.start_ts.to_numpy(np.int64); rel = X.rel.to_numpy(np.int64)
    lp = np.log(px)
    out = {c: np.zeros(len(X), np.float32) for c in W13}
    order = np.lexsort((rel, st))
    ust, first = np.unique(st[order], return_index=True)
    bounds = list(first) + [len(order)]
    for i, t0 in enumerate(ust):
        idx = order[bounds[i]:bounds[i + 1]]
        j = np.arange(300)
        a = np.clip(t0 + j - s0, 1, len(lp) - 1)
        r = (lp[a] - lp[a - 1]) * 1e4  # return of second t0 + j (bp)
        s = rel[idx]; q = s - 2  # last usable return index at second s
        for k in KS:
            sk = str(k).replace('.', 'p')
            up = np.cumsum(r >= k); dn = np.cumsum(r <= -k)
            big = np.where(np.abs(r) >= k)[0]
            f = big[0] if len(big) else 10 ** 6
            ok = q >= 0
            qq = np.clip(q, 0, 299)
            out[f"nup_{sk}"][idx] = np.where(ok, up[qq], 0)
            out[f"ndn_{sk}"][idx] = np.where(ok, dn[qq], 0)
            seen = ok & (f <= q)
            out[f"fsg_{sk}"][idx] = np.where(seen, np.sign(r[min(f, 299)]), 0)
            out[f"frel_{sk}"][idx] = np.where(seen, f, -1)
    return pd.DataFrame(out, index=X.index)


def main():
    t0 = time.time()
    b = pd.read_parquet(f"{C}/binance_1s.parquet")
    s0 = int(b.sec.min()); px = b.set_index("sec").close.reindex(np.arange(s0, int(b.sec.max()) + 1)).ffill().to_numpy(float)
    pt = pd.read_parquet(f"{C}/ptb.parquet"); ptb = pt.set_index("start").priceToBeat.astype(float)
    fl = pd.read_parquet(f"{C}/fills.parquet", columns=["wallet", "shares", "cid", "rel", "is_up", "start_ts"])
    X = nf12.load(px, s0, ptb, fl); del fl
    X = X.drop(columns=[c for c in X.columns if c.startswith("y") and c != "y"])
    st = pd.read_parquet(f"{OUT}/streams_sec.parquet", columns=["cid", "rel", "yL", "yS"])
    idx = pd.MultiIndex.from_arrays([X.cid.to_numpy(), X.rel.to_numpy().astype(np.int64)])
    s2 = st.set_index(["cid", "rel"])
    X["yL"] = s2.yL.reindex(idx).fillna(0).to_numpy(np.float32)
    X["yS"] = s2.yS.reindex(idx).fillna(0).to_numpy(np.float32)
    X = pd.concat([X, w13_feats(X, px, s0)], axis=1)
    print("rows", len(X), "load s", round(time.time() - t0), "check y == yL + yS:", float(np.abs(X.y - X.yL - X.yS).max()), flush=True)
    feats = nf12.SPOT + nf12.TAPE + ["D_" + c for c in nf12.DT] + nf12.SLOW_SPOT + W13
    tr = (X.start_ts < VAL0).to_numpy(); va = ((X.start_ts >= VAL0) & (X.start_ts < H)).to_numpy()
    preds = pd.DataFrame({"cid": X.cid[va].to_numpy(), "rel": X.rel[va].to_numpy()})
    res = {"features": feats, "importance_top20": {}}
    for tgt, nm in (("yL", "L13"), ("yS", "S13"), ("y", "T13")):
        m = lgb.train(nf12.PARAMS, lgb.Dataset(X.loc[tr, feats], X.loc[tr, tgt], free_raw_data=True), num_boost_round=nf12.ROUNDS)
        m.save_model(f"{CODE}/model_it13_{nm}.txt")
        preds[nm] = m.predict(X.loc[va, feats], num_threads=4).astype(np.float32)
        imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
        res["importance_top20"][nm] = {k: round(float(v / imp.sum()), 4) for k, v in imp.head(20).items()}
        res.setdefault("w13_share", {})[nm] = round(float(imp[W13].sum() / imp.sum()), 4)
        print(nm, "trained", round(time.time() - t0), flush=True)
    preds.to_parquet(f"{OUT}/ls13_val.parquet", index=False)
    D = pd.read_parquet(f"{OUT}/streams_win.parquet")
    v = D[(D.start_ts >= VAL0) & (D.start_ts < H)]
    P = preds.groupby("cid")[["L13", "S13", "T13"]].sum().reindex(v.index)
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet").groupby("cid").nf12b.sum().reindex(v.index)
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"]).groupby("cid").nf.sum().reindex(v.index)
    LS = P.L13 + P.S13
    sc = lambda a, b: round(float(np.corrcoef(np.asarray(a, float), np.asarray(b, float))[0, 1]), 4)
    res["validate_window"] = {
        "L13_vs_L": sc(P.L13, v.L), "S13_vs_S": sc(P.S13, v.S), "LS_vs_N": sc(LS, v.N), "T13_vs_N": sc(P.T13, v.N),
        "nf12b_vs_L": sc(nb, v.L), "nf12b_vs_S": sc(nb, v.S), "nf12b_vs_N": sc(nb, v.N), "avg_it4b_nf12b_vs_N": sc(0.5 * (vo + nb), v.N),
        "avg_it4b_LS_vs_N": sc(0.5 * (vo + LS), v.N), "corr_LS_nf12b": sc(LS, nb), "corr_L13_S13": sc(P.L13, P.S13),
        "spearman_LS_vs_N": round(float(pd.Series(LS.to_numpy()).corr(pd.Series(v.N.to_numpy()), method="spearman")), 4),
    }
    for w in ("GF", "XM", "DS"):
        res["validate_window"][w] = {"L13_vs_Lw": sc(P.L13, v["L" + w]), "S13_vs_Sw": sc(P.S13, v["S" + w]), "LS_vs_Tw": sc(LS, v["T" + w]),
                                     "nf12b_vs_Tw": sc(nb, v["T" + w]), "avg_it4b_LS_vs_Tw": sc(0.5 * (vo + LS), v["T" + w])}
    json.dump(res, open(f"{R}/ls13.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=1))


if __name__ == "__main__":
    main()
