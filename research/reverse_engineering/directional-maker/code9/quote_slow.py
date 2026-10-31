"""Iteration 9 (information I8-1 step 3 = X74): the quote unit (a cluster-class 500 at the touch now; iteration 8
code8/a4_ceiling.py, 10-31 14:06-16:30 BTC 5m, live split fit < 15:00, test >= 15:00) re-scored with the Chainlink edge
computed with the slow sigma (RMS of Binance spot 1-s log returns over 3,600 s, k 1) instead of 1.4 x the 300-s futures
std. The saved per-second table (it6/a4_secs_*) holds the frozen edge; x = ln(CL/K) is recovered from it with the frozen
sigma recomputed exactly as a4_ceiling.py did. Same LightGBM parameters, rounds and split. Development."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code5"))
sys.path.insert(0, str(HERE.parent / "code6"))
from pres_live import load_ref  # noqa: E402

C = ROOT / ".cache" / "re" / "directional-maker"
a, b = 1793455600, 1793464202
SPLIT = 1793458800


def main():
    import lightgbm as lgb
    S = pd.read_parquet(C / "it6" / f"a4_secs_{a}_{b}.parquet")
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    t = (S.st + S.rel).to_numpy(np.int64)
    jj = np.searchsorted(sec, t)
    sig_fz = np.array([np.std(r1[max(j - 300, 0):j]) * 1.4 for j in jj])
    sp = pd.read_parquet(C / "it9" / f"spot1s_rest_{1793448000 - 7200}_{1793469600}.parquet").sort_values("sec")
    base = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - base + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - base] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    i = t - 1 - base
    sig_sl = np.sqrt((cs[i + 1] - cs[i + 1 - 3600]) / 3600)
    up = S.s_up.to_numpy() == 1
    fair_up = np.where(up, S.e_cl + S.mid, 1 - (S.e_cl + S.mid))
    z = norm.ppf(np.clip(fair_up, 1e-9, 1 - 1e-9))
    tau = S.tau.to_numpy()
    xx = z * sig_fz * np.sqrt(tau)
    f_sl = norm.cdf(xx / (sig_sl * np.sqrt(tau)))
    S["e_cl_slow"] = np.where(up, f_sl, 1 - f_sl) - S.mid
    S["ratio"] = sig_fz / 1.4 / sig_sl
    lk = {}
    for L in (300, 900, 1800, 7200):
        sgL = np.sqrt((cs[i + 1] - cs[i + 1 - L]) / L)
        fL = norm.cdf(xx / (sgL * np.sqrt(tau)))
        S[f"e_v{L}"] = np.where(up, fL, 1 - fL) - S.mid
        lk[f"v{L}"] = round(float(roc_auc_score(S.y, S[f"e_v{L}"].fillna(0))), 4)
    lk["v3600"] = round(float(roc_auc_score(S.y, S.e_cl_slow.fillna(0))), 4)
    lk["frozen"] = round(float(roc_auc_score(S.y, S.e_cl.fillna(0))), 4)
    print("5m quote unit univariate by lookback (all seconds):", lk)
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    QA = ["rel", "s_up", "spread", "mid", "tau", "n2", "n10", "last_age", "last_sold_s", "tch_age"]
    trs, tes = S[S.st < SPLIT], S[S.st >= SPLIT].copy()
    out = {"seconds": int(len(S)), "test_seconds": int(len(tes)), "test_pos_rate": float(tes.y.mean())}
    for nm, cols in (("activity", QA), ("activity+chainlink_frozen", QA + ["e_cl"]), ("activity+chainlink_slow", QA + ["e_cl_slow"]),
                     ("activity+futures+chainlink_frozen", QA + ["e_f", "e_cl"]), ("activity+futures+chainlink_slow", QA + ["e_f", "e_cl_slow"]),
                     ("activity+both_chainlink", QA + ["e_cl", "e_cl_slow"])):
        mdl = lgb.train(P, lgb.Dataset(trs[cols], trs.y), 300)
        sc = mdl.predict(tes[cols])
        out[nm] = round(float(roc_auc_score(tes.y, sc)), 4)
        tes["sc_" + nm] = sc
    out["univariate_e_cl_frozen"] = round(float(roc_auc_score(tes.y, tes.e_cl.fillna(0))), 4)
    out["univariate_e_cl_slow"] = round(float(roc_auc_score(tes.y, tes.e_cl_slow.fillna(0))), 4)
    burst = tes.ratio > 1.5
    if burst.sum() > 100 and tes.y[burst].nunique() == 2:
        out["burst_seconds"] = int(burst.sum())
        out["burst_univariate_frozen"] = round(float(roc_auc_score(tes.y[burst], tes.e_cl[burst].fillna(0))), 4)
        out["burst_univariate_slow"] = round(float(roc_auc_score(tes.y[burst], tes.e_cl_slow[burst].fillna(0))), 4)
    ws = tes.st.unique()
    rng = np.random.default_rng(8)
    g = []
    for _ in range(300):
        pick = rng.choice(ws, len(ws), replace=True)
        sub = pd.concat([tes[tes.st == w] for w in pick])
        if sub.y.nunique() < 2:
            continue
        g.append(roc_auc_score(sub.y, sub["sc_activity+futures+chainlink_slow"]) - roc_auc_score(sub.y, sub["sc_activity+futures+chainlink_frozen"]))
    out["slow_minus_frozen_ci95"] = [round(float(np.quantile(g, .025)), 4), round(float(np.quantile(g, .975)), 4)]
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_quote_slow.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
