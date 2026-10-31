"""H1: contrarian tape taker. Does recent public tape/spot movement AGAINST a side predict the cluster's taker buys of that side?

FIT: logistic model (dynamic features + static price/time controls) per wallet.
TEST: AUC vs (a) static-only model (window-cluster bootstrap of the AUC gain),
      (b) clock-shift null: dynamic features taken from a window shifted by 1..72 windows (5 min..6 h),
          model REFIT on FIT under the same shift, so the null model can exploit everything except timing.
"""
import pickle, sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from polyrea.analysis.updown import auc, decision_metrics
from grid import Grid, DYN

W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 else 100
d = pickle.load(open("data.pkl", "rb"))
G = {per: Grid(d[per]) for per in ("fit", "test")}

def base_frame(per):
    P = d[per]["prints"]
    P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True).copy()
    P["rel"] = P.ts - P.start_ts
    return P

def dyn_frame(per, P, shift_of=None):
    """shift_of: dict cid -> shift in windows (None = true clock)."""
    cols = {c: np.full(len(P), np.nan) for c in DYN}
    for cid, idx in P.groupby("condition_id").indices.items():
        s = shift_of.get(cid, 0) if shift_of else 0
        f = G[per].feats(cid, P.ts.to_numpy()[idx], P.is_up.to_numpy()[idx], shift_windows=s)
        if f is None:
            continue
        for c in DYN:
            cols[c][idx] = f[c]
    return pd.DataFrame(cols)

def static_frame(P):
    x = pd.DataFrame({"price": P.price, "price2": P.price ** 2, "price3": P.price ** 3, "rel": P.rel / 300, "rel2": (P.rel / 300) ** 2, "is_up": P.is_up.astype(float)})
    return x

def fit_model(X, y):
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, C=1.0))
    m.fit(X, y)
    return m

def shift_map(per, rng):
    starts = sorted(G[per].by_start)
    out = {}
    for cid, w in G[per].wins.items():
        for _ in range(50):
            s = int(rng.integers(1, 73)) * int(rng.choice([-1, 1]))
            if (w.start_ts + 300 * s) in G[per].by_start:
                out[cid] = s
                break
    return out

Pf, Pt = base_frame("fit"), base_frame("test")
Sf, St = static_frame(Pf), static_frame(Pt)
Df, Dt = dyn_frame("fit", Pf), dyn_frame("test", Pt)
okf = Df.notna().all(axis=1).to_numpy(); okt = Dt.notna().all(axis=1).to_numpy()
res = {}
rng = np.random.default_rng(0)
t0 = time.time()
# null draws: shifted dynamic features for FIT and TEST (shared across wallets)
null_draws = []
for b in range(N_PERM):
    smf, smt = shift_map("fit", rng), shift_map("test", rng)
    null_draws.append((dyn_frame("fit", Pf, smf), dyn_frame("test", Pt, smt)))
print("null features built", round(time.time() - t0, 1), flush=True)
for name, wal in W.items():
    yf = (Pf.wallet == wal).to_numpy().astype(int); yt = (Pt.wallet == wal).to_numpy().astype(int)
    Xf_full = pd.concat([Sf, Df], axis=1)[okf]; Xt_full = pd.concat([St, Dt], axis=1)[okt]
    m_full = fit_model(Xf_full, yf[okf]); s_full = m_full.predict_proba(Xt_full)[:, 1]
    m_stat = fit_model(Sf[okt.shape and okf], yf[okf]); s_stat = m_stat.predict_proba(St[okt])[:, 1]
    m_dyn = fit_model(Df[okf], yf[okf]); s_dyn = m_dyn.predict_proba(Dt[okt])[:, 1]
    y_te = yt[okt]
    a_full, a_stat, a_dyn = auc(s_full, y_te), auc(s_stat, y_te), auc(s_dyn, y_te)
    # window-cluster bootstrap of AUC gain full - static
    cids = Pt.condition_id.to_numpy()[okt]
    uc, inv = np.unique(cids, return_inverse=True)
    groups = [np.nonzero(inv == i)[0] for i in range(len(uc))]
    rb = np.random.default_rng(1)
    gains = []
    for _ in range(300):
        pick = rb.integers(0, len(uc), len(uc))
        ix = np.concatenate([groups[i] for i in pick])
        gains.append(auc(s_full[ix], y_te[ix]) - auc(s_stat[ix], y_te[ix]))
    gains = np.array(gains)
    # clock-shift null with refit
    null_full, null_dyn = [], []
    for Dfn, Dtn in null_draws:
        okfn = okf & Dfn.notna().all(axis=1).to_numpy(); oktn = okt & Dtn.notna().all(axis=1).to_numpy()
        mn = fit_model(pd.concat([Sf, Dfn], axis=1)[okfn], yf[okfn])
        sn = mn.predict_proba(pd.concat([St, Dtn], axis=1)[oktn])[:, 1]
        null_full.append(auc(sn, yt[oktn]))
        md = fit_model(Dfn[okfn], yf[okfn])
        null_dyn.append(auc(md.predict_proba(Dtn[oktn])[:, 1], yt[oktn]))
    null_full, null_dyn = np.array(null_full), np.array(null_dyn)
    coefs = dict(zip(list(Xf_full.columns), np.round(m_full[-1].coef_[0], 3).tolist()))
    # decision metrics at the FIT-optimal threshold (max MCC on FIT)
    sf_full = m_full.predict_proba(Xf_full)[:, 1]
    grid = np.quantile(sf_full, np.linspace(0.5, 0.995, 60))
    best = max(grid, key=lambda th: (lambda m: m if np.isfinite(m) else -1)(decision_metrics(sf_full, yf[okf], th)["mcc"]))
    dm = decision_metrics(s_full, y_te, best)
    res[name] = {
        "fit_wallet_prints": int(yf.sum()), "test_wallet_prints": int(yt.sum()), "test_prints": int(okt.sum()),
        "auc_test_full": a_full, "auc_test_static_only": a_stat, "auc_test_dynamic_only": a_dyn,
        "auc_gain_full_minus_static": a_full - a_stat,
        "auc_gain_bootstrap_ci95": [float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))],
        "auc_gain_bootstrap_p_le0": float((gains <= 0).mean()),
        "clock_shift_null_full": {"mean": float(null_full.mean()), "p95": float(np.percentile(null_full, 95)), "max": float(null_full.max()), "perm_p": float((1 + (null_full >= a_full).sum()) / (1 + len(null_full)))},
        "clock_shift_null_dynamic_only": {"mean": float(null_dyn.mean()), "p95": float(np.percentile(null_dyn, 95)), "max": float(null_dyn.max()), "perm_p": float((1 + (null_dyn >= a_dyn).sum()) / (1 + len(null_dyn)))},
        "coefficients_standardized": coefs,
        "decision_at_fit_threshold": dm,
    }
    print(name, json.dumps(res[name], default=float), flush=True)
json.dump({"n_perm": N_PERM, "results": res}, open("h1_match.json", "w"), indent=1, default=float)
