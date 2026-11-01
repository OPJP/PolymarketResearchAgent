"""Iteration 13 (X116 = information panel P4; pre-registered in NOTES.md before scoring): does the window net follow the
Chainlink-vs-Binance BASIS? b(t) = Polymarket RTDS Chainlink btc/usd price stamped t (public HF capture, revision f848a77c) minus
the Binance BTCUSDT 1-s close of second t. Per VALIDATE window: residual = the pooled operator net minus the frozen primary
target's window sum (0.5 x (nf_it4b + nf12b)); regressors = b at the open and Delta b over each window minute (k = 0..4).
OLS fitted on 10-17..19 windows, scored on 10-20..22 (and the reverse). Success = out-of-sample window-net r gain >= +0.03
with the same coefficient signs in both fits. Usage: python basis13.py ARCHIVE_DIR"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
C = _ROOT + "/.cache/re/btc5m-bot"
R = _ROOT + "/research/reverse_engineering/btc5m-bot/results"
H = 1792713600
D17, D20 = 1792195200, 1792454400


def main():
    A = sys.argv[1]
    cl = pd.concat([pd.read_parquet(f"{A}/btcrtds_2026-10-{d}.parquet", columns=["timestampMs", "fullAccuracyValue"]) for d in (17, 18, 19, 20, 21, 22)])
    cl["sec"] = (cl.timestampMs // 1000).astype(np.int64)
    cl["p"] = cl.fullAccuracyValue.astype(float) / 1e18
    cs = cl.groupby("sec").p.last()
    b = pd.read_parquet(f"{C}/binance_1s.parquet")
    bn = b.set_index("sec").close
    sec = np.arange(D17 - 600, H + 600)
    cs = cs.reindex(sec).ffill(limit=5); bn = bn.reindex(sec).ffill(limit=5)
    basis = (cs - bn)
    res = {"rtds_seconds": int(cl.sec.nunique()), "basis_usd_q": [round(float(x), 2) for x in np.nanpercentile(basis, [5, 25, 50, 75, 95])]}
    D = pd.read_parquet(f"{C}/it13/streams_win.parquet")
    v = D[(D.start_ts >= D17) & (D.start_ts < H)].copy()
    nb = pd.read_parquet(f"{C}/it12/nf12b_val.parquet").groupby("cid").nf12b.sum()
    vo = pd.read_parquet(f"{C}/val_outcome_it4b.parquet", columns=["cid", "rel", "nf"]).groupby("cid").nf.sum()
    v["pred"] = 0.5 * (vo.reindex(v.index).fillna(0) + nb.reindex(v.index).fillna(0))
    v["res"] = v.N - v.pred
    bs = basis
    st = v.start_ts.to_numpy(np.int64)
    X = pd.DataFrame(index=v.index)
    X["b_open"] = bs.reindex(st).to_numpy()
    for k in range(5):
        X[f"db{k}"] = bs.reindex(st + 60 * (k + 1)).to_numpy() - bs.reindex(st + 60 * k).to_numpy()
    X["db_tot"] = bs.reindex(st + 299).to_numpy() - bs.reindex(st).to_numpy()
    ok = X.notna().all(axis=1).to_numpy()
    res["windows"] = int(len(v)); res["windows_with_basis"] = int(ok.sum())
    res["corr_with_residual"] = {c: round(float(np.corrcoef(X.loc[ok, c], v.res[ok])[0, 1]), 4) for c in X.columns}
    res["corr_with_net"] = {c: round(float(np.corrcoef(X.loc[ok, c], v.N[ok])[0, 1]), 4) for c in X.columns}
    cols = ["b_open"] + [f"db{k}" for k in range(5)]
    out = {}
    for nm, fm, sm_ in (("fit_17_19_score_20_22", st < D20, st >= D20), ("fit_20_22_score_17_19", st >= D20, st < D20)):
        fm, sm_ = fm & ok, sm_ & ok
        Xf = np.c_[np.ones(fm.sum()), X.loc[fm, cols].to_numpy()]
        beta = np.linalg.lstsq(Xf, v.res[fm].to_numpy(), rcond=None)[0]
        ps = np.c_[np.ones(sm_.sum()), X.loc[sm_, cols].to_numpy()] @ beta
        base = float(np.corrcoef(v.pred[sm_], v.N[sm_])[0, 1])
        aug = float(np.corrcoef(v.pred[sm_] + ps, v.N[sm_])[0, 1])
        out[nm] = {"beta": dict(zip(["const"] + cols, [round(float(x), 2) for x in beta])), "r_base": round(base, 4), "r_aug": round(aug, 4),
                   "gain": round(aug - base, 4), "r_pred_residual": round(float(np.corrcoef(ps, v.res[sm_])[0, 1]), 4)}
    res["ols"] = out
    json.dump(res, open(f"{R}/basis13.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
