"""directional-maker iteration 14, X150 (panel iter13 assumptions P2): print-level selection scored with the decoded
quote geometry instead of a model output.

Unit: every clean print (first CLOB trade record of a transaction that is not a cluster TAKER transaction) of a BTC 5m or
15m window, seen as a hit on the bid of token s (taker SELL s, or taker BUY of the complement). Label: the transaction
holds a cluster maker BUY fill (calldata) on s. Score, written down before scoring (panel P2):
  d = (last clean print on s before the print, in s terms) - (print price in s terms), in ticks (0.01);
  s = 1[s = Chainlink posture side at t - 1.25 s] for d in {0, 1}; s = c for d in {2, 3}; 0 otherwise;
  c fitted on 14:00-16:00 (grid), scored on 16:00-18:00.
Reported: AUC (global and within-window), recall at the best threshold with lift >= 3, lift at recall 0.5, against the
activity-only LightGBM on the same unit (print size, time since the previous clean print, same-token and same-price
flags, prints and shares in the last 1 / 5 s, time in window, price level).

    .venv/Scripts/python.exe research/reverse_engineering/directional-maker/code14/sel_geometry.py 1793455200 1793469600
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from lagged_quote import fut_mid, at, sec_sigma, cl_source  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
IT13 = C / "it13"
CLU = {"0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed", "0x3725d52f3c252e8374999cc8617292ea2608ad88",
       "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}


def recall_at_lift(y, s, lift_min=3.0):
    o = np.argsort(-s, kind="stable"); ys = y[o]; ss = s[o]
    cum = np.cumsum(ys); n = np.arange(1, len(ys) + 1); base = y.mean()
    prec = cum / n; lift = prec / base; rec = cum / y.sum()
    # thresholds only at the end of each group of tied scores (no credit for an arbitrary order inside ties)
    endg = np.r_[ss[1:] != ss[:-1], True]
    lift, rec = lift[endg], rec[endg]
    ok = lift >= lift_min
    best = float(rec[ok].max()) if ok.any() else 0.0
    i50 = int(np.searchsorted(rec, 0.5))
    return best, float(lift[min(i50, len(lift) - 1)])


def strat_auc(df, col):
    a, w = [], []
    for _, g in df.groupby("w"):
        if g.y.nunique() == 2:
            a.append(roc_auc_score(g.y, g[col])); w.append(g.y.sum())
    return float(np.average(a, weights=w)) if a else None


def main(a, b):
    mid_t = a + (b - a) // 2
    X = pd.read_parquet(IT13 / "trades.parquet")
    X = X[(X.s >= (a - 60) * 1000) & (X.s < b * 1000)].sort_values("s", kind="stable")
    X["h"] = X.h.str.lower()
    cd = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "calldata" / "live1031_*.parquet")) +
                    glob.glob(str(C / "calldata" / "liveall1031_*.parquet"))], ignore_index=True)
    cd["maker"] = cd.maker.str.lower(); cd["tx"] = cd.tx.str.lower()
    mk_tx = set(cd.loc[(cd.role == "maker") & cd.maker.isin(CLU) & (cd.oside == 0), "tx"])
    tk_tx = set(cd.loc[(cd.role != "maker") & cd.maker.isin(CLU), "tx"])
    acts = pd.concat([pd.read_parquet(p) for p in glob.glob(str(C / "live_activity_*.parquet"))], ignore_index=True)
    acts["tx"] = acts.transactionHash.str.lower()
    fills = acts[(acts.type == "TRADE") & (acts.side == "BUY") & acts.tx.isin(mk_tx)]
    fill_up = fills.groupby("tx").outcome.agg(lambda v: set(v))
    P = X.drop_duplicates("h").copy()
    P = P[~P.h.isin(tk_tx) & (P.s >= a * 1000)]
    d_ = P.d.astype(str).str.upper().str[0]
    P["s_up"] = (((P.ai == 0) & (d_ == "S")) | ((P.ai == 1) & (d_ == "B"))).astype(int)
    P["p_s"] = np.where((P.ai == 0) == (P.s_up == 1), P.p, 1 - P.p)   # print price in terms of the hit token s
    P["y"] = [int(h in fill_up.index and (("Up" if su else "Down") in fill_up[h])) for h, su in zip(P.h, P.s_up)]
    P["cl_any"] = P.h.isin(mk_tx).astype(int)
    # last clean print on s before this print (same window), in s terms
    P = P.sort_values(["w", "s"], kind="stable")
    clean = P.copy()
    clean["p_up"] = np.where(clean.s_up == 1, clean.p_s, 1 - clean.p_s)
    last_s = np.full(len(P), np.nan); dt = np.full(len(P), np.nan); same = np.zeros(len(P)); n1 = np.zeros(len(P)); n5 = np.zeros(len(P))
    z5 = np.zeros(len(P))
    for w, ix in P.groupby("w").indices.items():
        g = P.iloc[ix]
        cg = g[g.cl_any == 0]  # prior prints in cluster transactions never enter features
        cs = cg.s.to_numpy(np.int64); cu = cg.p_up.to_numpy(float) if "p_up" in cg else None
        cu = np.where(cg.s_up == 1, cg.p_s, 1 - cg.p_s); csu = cg.s_up.to_numpy(); cz = np.concatenate([[0], np.cumsum(cg.z.to_numpy())])
        t = g.s.to_numpy(np.int64)
        j = np.searchsorted(cs, t, side="left") - 1
        pu = np.where(j >= 0, cu[np.clip(j, 0, None)], np.nan)
        last_s[ix] = np.where(g.s_up == 1, pu, 1 - pu)
        dt[ix] = np.where(j >= 0, (t - cs[np.clip(j, 0, None)]) / 1000, 999)
        same[ix] = np.where(j >= 0, (csu[np.clip(j, 0, None)] == g.s_up.to_numpy()).astype(float), -1)
        i1 = np.searchsorted(cs, t, side="left")
        n1[ix] = i1 - np.searchsorted(cs, t - 1000, side="left")
        i5 = np.searchsorted(cs, t - 5000, side="left"); n5[ix] = i1 - i5; z5[ix] = cz[i1] - cz[i5]
    P["last_s"], P["dt"], P["same"], P["n1"], P["n5"], P["z5"] = last_s, dt, same, n1, n5, z5
    P["dtick"] = np.round((P.last_s - P.p_s) / 0.01)
    P["rel"] = P.s / 1000 - P.w.str.rsplit("-", n=1).str[1].astype(int)
    P["is15"] = P.w.str.contains("-15m-").astype(int)
    # posture at t - 1.25 s (Chainlink, Gamma strike, 1.4 x futures sigma300) against the Up mid just before the print
    E, M = fut_mid(a - 3600, b)
    sig = sec_sigma(E, M, 300)
    clv = cl_source.cl_values(list(range(a - 10, b + 1)), allow_sealed=False, fetch=True, max_requests=200)
    S = pd.read_parquet(IT13 / "sched_adds.parquet", columns=["w", "s", "bb", "ba"])
    S = S[(S.s >= (a - 60) * 1000) & (S.s < b * 1000)].sort_values(["w", "s"], kind="stable")
    mid = np.full(len(P), np.nan)
    for w, ix in P.groupby("w").indices.items():
        sb = S[S.w == w]
        mid[ix] = at(sb.s.to_numpy(np.int64), ((sb.bb + sb.ba) / 2).to_numpy(float), P.s.to_numpy(np.int64)[ix] - 1)
    from polyrea.workflows.updown_study import fetch_windows
    raw = fetch_windows(sorted(set(P.w)))
    K = {}
    for m in raw.values():
        for e in m.get("events") or []:
            v = (e.get("eventMetadata") or {}).get("priceToBeat")
            if v is not None:
                K[m["slug"]] = float(v)
    t = P.s.to_numpy(np.int64)
    st = P.w.str.rsplit("-", n=1).str[1].astype(int).to_numpy(); L = np.where(P.is15 == 1, 900, 300)
    cl = clv.reindex((t - 1250) // 1000).to_numpy(float)
    sg = sig.reindex(t // 1000).to_numpy(float) * 1.4
    F = norm.cdf((cl - P.w.map(K).to_numpy(float)) / (sg * np.sqrt(np.maximum(st + L - t / 1000, 1.0))))
    post_up = (F > mid).astype(float); post_up[~(np.isfinite(F) & np.isfinite(mid))] = np.nan
    P["posture_s"] = np.where(np.isnan(post_up), np.nan, (post_up == P.s_up.to_numpy()).astype(float))
    P = P[P.posture_s.notna() & P.dtick.notna()]
    tr, te = P[P.s < mid_t * 1000], P[P.s >= mid_t * 1000].copy()

    def geo(df, c):
        dd = df.dtick.to_numpy(); ps = df.posture_s.to_numpy()
        return np.where(np.isin(dd, [0, 1]), ps, np.where(np.isin(dd, [2, 3]), c, 0.0))

    best_c, best_auc = None, -1
    for c in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2):
        au = roc_auc_score(tr.y, geo(tr, c))
        if au > best_auc:
            best_c, best_auc = c, au
    te["geo"] = geo(te, best_c)
    import lightgbm as lgb
    ACT = ["z", "dt", "same", "n1", "n5", "z5", "rel", "is15", "p_s", "dtick"]
    Pm = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=14)
    m = lgb.train(Pm, lgb.Dataset(tr[ACT], tr.y), 200); te["act"] = m.predict(te[ACT])
    m2 = lgb.train(Pm, lgb.Dataset(tr[ACT + ["posture_s"]], tr.y), 200); te["act_post"] = m2.predict(te[ACT + ["posture_s"]])
    out = {"prints_fit": int(len(tr)), "prints_test": int(len(te)), "base_rate_test": float(te.y.mean()), "c_fit": best_c,
           "fit_auc_geo": float(best_auc), "dtick_share_of_cluster_fills_test": te[te.y == 1].dtick.clip(-3, 6).value_counts(normalize=True).sort_index().round(3).to_dict()}
    te["geo_hybrid"] = te.geo.round(6) + 0.5 * te.act_post
    for col in ("geo", "act", "act_post", "geo_hybrid"):
        r, lft = recall_at_lift(te.y.to_numpy(), te[col].to_numpy())
        out[col] = {"auc": float(roc_auc_score(te.y, te[col])), "auc_within_window": strat_auc(te, col),
                    "recall_at_lift3": r, "lift_at_recall50": lft}
    (HERE.parent / "results" / f"iter14_sel_geometry_{a}_{b}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
