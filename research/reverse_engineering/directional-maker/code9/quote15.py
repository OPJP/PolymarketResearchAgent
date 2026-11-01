"""Iteration 9 (X74 / X79 at the quote level for BTC 15m): the quote unit of iteration 8 (a cluster-class exact-500 at the
touch of side s now: an exact-500 add on s at/above the touch in (t-1 s, t] whose price is still >= the touch at t) built
for the BTC 15m windows of 10-31 14:15-16:30 from the own raw recorder (it6/ev, it6/touch, it6/x), with the Chainlink edge
under the frozen sigma (1.4 x 300-s futures std, as a4_ceiling.py) and the slow sigma (3,600-s Binance spot RMS). Fit-free
univariate AUCs on all seconds and on the test half (>= 15:00), plus the same LightGBM split as iteration 8 (fit < 15:00 on
3 windows: thin). Development."""
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
D_CL = 1432


def main():
    import lightgbm as lgb
    x = pd.read_parquet(C / "it6" / f"x_{a}_{b}.parquet")
    x = x[x.w.str.contains("btc-updown-15m")].sort_values("s", kind="stable").drop_duplicates("h")
    d = x.d.astype(str).str.upper().str[0]
    x["s_up"] = ((x.ai == 0) & (d == "S")) | ((x.ai == 1) & (d == "B"))
    ev = pd.read_parquet(C / "it6" / f"ev_{a}_{b}.parquet", columns=["s", "w", "side", "p", "d", "bb", "ba"])
    e5 = ev[(ev.d == 500.0) & ev.w.str.contains("btc-updown-15m")].copy()
    del ev
    tch = pd.read_parquet(C / "it6" / f"touch_{a}_{b}.parquet")
    tch = tch[tch.w.str.contains("btc-updown-15m")]
    fu, cl, tw = load_ref(a, b)
    fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
    sec = np.arange(fs[0] // 1000, fs[-1] // 1000 + 1)
    ms_sec = fm[np.clip(np.searchsorted(fs, sec * 1000, side="right") - 1, 0, None)]
    r1 = np.diff(np.log(ms_sec), prepend=np.log(ms_sec[0]))
    cls = np.array(sorted(cl))
    clv = np.array([cl[k] for k in cls])
    sp = pd.read_parquet(C / "it9" / "spot1s_rest_1793440800_1793469600.parquet").sort_values("sec")
    b0 = int(sp.sec.iloc[0])
    px = np.full(int(sp.sec.iloc[-1]) - b0 + 1, np.nan)
    px[sp.sec.astype(int).to_numpy() - b0] = sp.px.to_numpy()
    px = pd.Series(px).ffill().to_numpy()
    rr = np.r_[0.0, np.diff(np.log(px))]
    cs = np.r_[0.0, np.cumsum(rr * rr)]
    rows = []
    for slug in sorted(set(x.w)):
        st = int(slug.split("-")[-1])
        if st < a or st + 900 > b:
            continue
        K = tw.get(st)
        if K is None:
            continue
        gs = x[x.w == slug].s.to_numpy()
        gup = x[x.w == slug].s_up.to_numpy()
        tw_ = tch[tch.w == slug].sort_values("s")
        ts_, bb_, ba_ = tw_.s.to_numpy(), tw_.bb.to_numpy(), tw_.ba.to_numpy()
        if not len(ts_):
            continue
        q = {}
        for s_up in (True, False):
            gq = e5[(e5.w == slug) & (e5.side == (1 if s_up else 0))]
            pq = gq.p.to_numpy()
            pz = pq if s_up else 1 - pq
            touch_at = gq.bb.to_numpy() if s_up else 1 - gq.ba.to_numpy()
            q[s_up] = (gq.s.to_numpy(np.int64), pz, pz >= touch_at - 1e-9)
        for t in range(0, 900):
            T = (st + t) * 1000
            jj = np.searchsorted(sec, st + t)
            sig_f = np.std(r1[max(jj - 300, 0):jj]) * 1.4
            ii = st + t - 1 - b0
            sig_s = np.sqrt((cs[ii + 1] - cs[ii + 1 - 3600]) / 3600)
            sig_L = {L: np.sqrt((cs[ii + 1] - cs[ii + 1 - L]) / L) for L in (300, 900, 1800, 7200)}
            tau = max(900 - t, 1.0)
            k = np.searchsorted(cls, (T - D_CL) // 1000, side="right") - 1
            if k < 0 or not sig_f > 0:
                continue
            xx = np.log(clv[k] / K)
            fcf, fcs = norm.cdf(xx / (sig_f * np.sqrt(tau))), norm.cdf(xx / (sig_s * np.sqrt(tau)))
            fL = {L: norm.cdf(xx / (v * np.sqrt(tau))) for L, v in sig_L.items()}
            j = np.searchsorted(gs, T, side="right") - 1
            it = np.searchsorted(ts_, T, side="right") - 1
            if it < 0:
                continue
            for s_up in (True, False):
                bbv, bav = (bb_[it], ba_[it]) if s_up else (1 - ba_[it], 1 - bb_[it])
                mid = (bbv + bav) / 2
                tq, pz, at = q[s_up]
                m = (tq > T - 1000) & (tq <= T) & at
                lab = int(m.any() and pz[m].max() >= bbv - 1e-9)
                rows.append(dict(st=st, rel=t, s_up=int(s_up), y=lab, e_fz=(fcf if s_up else 1 - fcf) - mid, e_sl=(fcs if s_up else 1 - fcs) - mid,
                                 spread=bav - bbv, mid=mid, tau=tau, n2=int(((gs > T - 2000) & (gs <= T)).sum()), n10=int(((gs > T - 10000) & (gs <= T)).sum()),
                                 last_age=(T - gs[j]) if j >= 0 else 99999, last_sold_s=int(j >= 0 and gup[j] == s_up), tch_age=T - ts_[it],
                                 burst=int(sig_f / 1.4 / sig_s > 1.5),
                                 **{f"e_v{L}": (f_ if s_up else 1 - f_) - mid for L, f_ in fL.items()}))
    S = pd.DataFrame(rows)
    te = S[S.st >= SPLIT].copy()
    tr = S[S.st < SPLIT]
    out = {"seconds": int(len(S)), "windows": int(S.st.nunique()), "pos_rate": round(float(S.y.mean()), 4),
           "univariate_all": {"frozen": round(float(roc_auc_score(S.y, S.e_fz)), 4), "slow": round(float(roc_auc_score(S.y, S.e_sl)), 4)},
           "univariate_test": {"frozen": round(float(roc_auc_score(te.y, te.e_fz)), 4), "slow": round(float(roc_auc_score(te.y, te.e_sl)), 4)}}
    out["univariate_by_lookback_all"] = {c: round(float(roc_auc_score(S.y, S[c])), 4) for c in ("e_v300", "e_v900", "e_v1800", "e_sl", "e_v7200", "e_fz")}
    bu = S.burst == 1
    if bu.sum() > 100 and S.y[bu].nunique() == 2:
        out["univariate_burst"] = {"n": int(bu.sum()), "frozen": round(float(roc_auc_score(S.y[bu], S.e_fz[bu])), 4),
                                   "slow": round(float(roc_auc_score(S.y[bu], S.e_sl[bu])), 4)}
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    QA = ["rel", "s_up", "spread", "mid", "tau", "n2", "n10", "last_age", "last_sold_s", "tch_age"]
    if tr.y.sum() > 20:
        for nm, cols in (("activity", QA), ("activity+frozen", QA + ["e_fz"]), ("activity+slow", QA + ["e_sl"])):
            m_ = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 300)
            out[f"lgbm_{nm}"] = round(float(roc_auc_score(te.y, m_.predict(te[cols]))), 4)
    print(json.dumps(out, indent=1))
    (HERE.parent / "results" / "iter9_quote15.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
