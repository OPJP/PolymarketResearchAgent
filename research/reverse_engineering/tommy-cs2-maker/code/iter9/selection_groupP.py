"""Iteration 9, X127 (assumptions panel iter8 P1): selection = coverage of the feed product the wallet buys (group P).

Pre-registered in NOTES iteration 9 before computing.
1. Membership, BUILD only (sign / print times and game starts in [10-16, 10-21)): fixed-lag co-signers of P4e's
   P4e-ALONE taker BUYs (no wallet take within 1 s; same token, +-1 s, n >= 10, n >= 5 x the 30-s shift null with
   20 draws, IQR <= 300 ms), plus P4e; keep those with <= 2% of their BUILD taker prints in GRID events (taker tapes of
   every CS2 match / map-winner market). The +100-230 ms group (group G) should drop out by its GRID share.
2. Feature for event e: gp72 / gp24 = distinct members with a taker print in ANOTHER event of the same league whose
   game start lies in [gs_e - 72 h, gs_e) / 24 h, counting only prints stamped before gs_e.
3. Scored without refit: raw AUC on BUILD, VALIDATE, VALIDATE unseen-league events, VALIDATE non-GRID events; recall /
   lift at gp > 0. BUILD-fitted logistics (activity + GRID + gp72; activity + GRID + gp24; v4 build score + gp72) on
   VALIDATE, against v4 (build constants) on the same events.
Output: results/selection_groupP.json
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
W = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
B0, BUILD_END, H = 1792108800, 1792540800, 1792713600


def auc(s, y):
    from scipy.stats import rankdata
    s, y = np.asarray(s, float), np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def membership():
    cols = ["tx", "idx", "maker", "side", "token_id", "sign_ms"]
    a = pd.read_parquet(OUT / "calldata_all.parquet", columns=cols)
    b = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted(glob.glob(str(OUT / "calldata_pub" / "*.parquet")))])
    T = pd.concat([a, b]).drop_duplicates(["tx", "idx"])
    T["maker"] = T.maker.str.lower()
    T["token_id"] = T.token_id.astype(str)
    T = T[(T.idx == -1) & (T.side == 0) & (T.sign_ms > B0 * 1000) & (T.sign_ms < BUILD_END * 1000)]
    wt = np.sort(T.loc[T.maker == W, "sign_ms"].to_numpy(float))
    pt = T[T.maker == P4E].sort_values("sign_ms")
    k = np.searchsorted(wt, pt.sign_ms.to_numpy(float))
    near = np.zeros(len(pt), bool)
    for j, (kk, s) in enumerate(zip(k, pt.sign_ms.to_numpy(float))):
        for q in (kk - 1, kk):
            if 0 <= q < len(wt) and abs(wt[q] - s) <= 1000:
                near[j] = True
    pa = pt[~near]
    ot = T[(T.maker != P4E) & (T.maker != W)]
    g = {kk: (v.sign_ms.to_numpy(float), v.maker.to_numpy()) for kk, v in ot.groupby("token_id")}
    lag, who = [], []
    for r in pa.itertuples():
        x = g.get(r.token_id)
        if x is None:
            continue
        d = x[0] - r.sign_ms
        m = np.abs(d) <= 1000
        lag += list(d[m])
        who += list(x[1][m])
    rng = np.random.default_rng(9)
    nul = {}
    for _ in range(20):
        sh = rng.choice([-1, 1], len(pa)) * 30000
        for r, s_ in zip(pa.itertuples(), sh):
            x = g.get(r.token_id)
            if x is None:
                continue
            d = x[0] - (r.sign_ms + s_)
            for w_ in x[1][np.abs(d) <= 1000]:
                nul[w_] = nul.get(w_, 0) + 1 / 20
    L = pd.DataFrame({"lag": lag, "who": who})
    st = L.groupby("who").lag.agg(n="size", med="median", q1=lambda v: np.percentile(v, 25), q3=lambda v: np.percentile(v, 75))
    st["null"] = st.index.map(lambda w_: nul.get(w_, 0.0))
    st["iqr"] = st.q3 - st.q1
    fixed = st[(st.n >= 10) & (st.n >= 5 * np.maximum(st.null, 0.2)) & (st.iqr <= 300)].sort_values("n", ascending=False)
    return fixed, int(len(pa)), int(len(pt))


def main():
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u.smt.isin(["moneyline", "child_moneyline"])].copy()
    u["gs_ts"] = pd.to_numeric(u.gs_ts, errors="coerce")
    em = pd.read_parquet(OUT / "events_meta.parquet")[["event_slug", "grid_series_id"]]
    eg = u.groupby("event_slug").agg(gs=("gs_ts", "min"), league=("league", "first")).reset_index().merge(em, on="event_slug", how="left")
    eg["grid"] = eg.grid_series_id.notna()
    grid_ev = set(eg.loc[eg.grid, "event_slug"])
    cid_ev = dict(zip(u.cid, u.event_slug))
    ev_gs = dict(zip(eg.event_slug, eg.gs))
    prints = []  # (event, wallet, ts)
    for f in glob.glob(str(OUT / "tapes" / "*_tkw.parquet")):
        cid = Path(f).name.split("_")[0]
        e = cid_ev.get(cid)
        if e is None:
            continue
        d = pd.read_parquet(f, columns=["proxyWallet", "timestamp"])
        d["proxyWallet"] = d.proxyWallet.str.lower()
        d = d[d.proxyWallet != W]
        prints.append(pd.DataFrame({"e": e, "w": d.proxyWallet.to_numpy(), "t": d.timestamp.astype("int64").to_numpy()}))
    P = pd.concat(prints, ignore_index=True)
    P["gs"] = P.e.map(ev_gs)
    P["grid"] = P.e.isin(grid_ev)
    fixed, n_alone, n_p4e = membership()
    Pb = P[(P.gs >= B0) & (P.gs < BUILD_END)]
    gshare = Pb.groupby("w").grid.agg(["mean", "size"])
    cand = list(fixed.index) + [P4E]
    rows = {}
    members = []
    for w_ in cand:
        gm = float(gshare.loc[w_, "mean"]) if w_ in gshare.index else None
        nb = int(gshare.loc[w_, "size"]) if w_ in gshare.index else 0
        info = {"n_cosign": int(fixed.loc[w_, "n"]) if w_ in fixed.index else None,
                "median_lag_ms": round(float(fixed.loc[w_, "med"]), 1) if w_ in fixed.index else 0.0,
                "iqr_ms": round(float(fixed.loc[w_, "iqr"]), 1) if w_ in fixed.index else None,
                "build_prints": nb, "build_grid_share": round(gm, 4) if gm is not None else None}
        info["member"] = bool(gm is not None and gm <= 0.02 and nb >= 20)
        rows[w_] = info
        if info["member"]:
            members.append(w_)
    MEM = set(members)
    sub = P[P.w.isin(MEM)]
    sub_t = {e: list(zip(g.w, g.t)) for e, g in sub.groupby("e")}
    by_lg = {lg: g.sort_values("gs") for lg, g in eg.groupby("league")}
    feats = []
    for r in eg.itertuples():
        g = by_lg.get(r.league)
        o = {"event_slug": r.event_slug}
        for hrs in (24, 72):
            ss = set()
            if g is not None:
                prev = g[(g.gs >= r.gs - hrs * 3600) & (g.gs < r.gs) & (g.event_slug != r.event_slug)]
                for e2 in prev.event_slug:
                    ss |= {w_ for w_, t in sub_t.get(e2, []) if t < r.gs}
            o[f"gp{hrs}"] = len(ss)
        feats.append(o)
    F = pd.DataFrame(feats)
    es = pd.read_parquet(OUT / "events_sel.parquet")
    X = es.merge(F, on="event_slug", how="left")
    X["grid"] = X.grid.astype(bool)
    X["split"] = np.where(X.gs < BUILD_END, "build", "validate")
    bl = set(X.loc[X.split == "build", "league"])
    X["unseen"] = (X.split == "validate") & ~X.league.isin(bl)
    res = {"p4e_build_takes": n_p4e, "p4e_alone_build_takes": n_alone, "candidates": rows, "members": members,
           "by_split": {}}
    for sp, g in [("build", X[X.split == "build"]), ("validate", X[X.split == "validate"]),
                  ("validate_unseen_league", X[X.unseen]), ("validate_nongrid", X[(X.split == "validate") & ~X.grid])]:
        o = {"events": int(len(g)), "traded": int(g.y.sum())}
        for c in ("gp24", "gp72"):
            o[f"auc_{c}"] = round(auc(g[c].fillna(0), g.y), 4)
            sel = g[c].fillna(0) > 0
            o[f"{c}_gt0"] = {"selected": int(sel.sum()), "recall": round(float(g.y[sel].sum() / max(g.y.sum(), 1)), 3),
                             "lift": round(float(g.y[sel].mean() / max(g.y.mean(), 1e-9)), 3) if sel.sum() else None,
                             "grid_selected": int((sel & g.grid).sum())}
        res["by_split"][sp] = o
    from sklearn.linear_model import LogisticRegression
    import final_rule as FR
    C = FR.CALL["build"]
    b, v = X[X.split == "build"].copy(), X[X.split == "validate"].copy()
    for d in (b, v):
        ev = d.rename(columns={"e_pre_n": "n", "e_pre_v": "v", "e_pre_w": "w"})
        d["v4"] = FR.selection_score(ev, C)

    def mat(d, cols):
        m = []
        for c in cols:
            if c == "act":
                m += [np.log1p(d[k].fillna(0).to_numpy(float)) for k in ("e_pre_n", "e_pre_v", "e_pre_w")]
            elif c == "grid":
                m.append(d.grid.to_numpy(float))
            elif c == "v4":
                m.append(np.log(d.v4.clip(1e-6, 1 - 1e-6) / (1 - d.v4.clip(1e-6, 1 - 1e-6))).to_numpy(float))
            else:
                m.append(np.log1p(d[c].fillna(0).to_numpy(float)))
        return np.column_stack(m)
    fits = {}
    for name, cols in (("act_grid", ["act", "grid"]), ("act_grid_gp72", ["act", "grid", "gp72"]),
                       ("act_grid_gp24", ["act", "grid", "gp24"]), ("act_gp72", ["act", "gp72"]),
                       ("v4_gp72", ["v4", "gp72"])):
        lr = LogisticRegression(max_iter=5000, C=1.0).fit(mat(b, cols), b.y)
        sv = lr.predict_proba(mat(v, cols))[:, 1]
        sb = lr.predict_proba(mat(b, cols))[:, 1]
        thr = float(np.quantile(sb[b.y.to_numpy() == 1], 0.2))
        sel = sv >= thr
        un = v.unseen.to_numpy()
        fits[name] = {"auc_validate": round(auc(sv, v.y), 4), "auc_build_insample": round(auc(sb, b.y), 4),
                      "recall": round(float(v.y[sel].sum() / max(v.y.sum(), 1)), 3),
                      "lift": round(float(v.y[sel].mean() / max(v.y.mean(), 1e-9)), 3) if sel.sum() else None,
                      "coef": [round(float(c), 3) for c in lr.coef_[0]], "icpt": round(float(lr.intercept_[0]), 3),
                      "thr": round(thr, 5),
                      "auc_validate_unseen": round(auc(sv[un], v.y[un]), 4) if un.sum() else None,
                      "recall_unseen": round(float(v.y[sel & un].sum() / max(v.y[un].sum(), 1)), 3) if un.sum() else None}
    res["build_fitted_logistic"] = fits
    un = v.unseen.to_numpy()
    selv4 = v.v4.to_numpy() >= C["thr"]
    res["v4_build_on_same_events"] = {"auc": round(auc(v.v4, v.y), 4), "auc_unseen": round(auc(v.v4[un], v.y[un]), 4),
                                      "recall": round(float(v.y[selv4].sum() / max(v.y.sum(), 1)), 3),
                                      "lift": round(float(v.y[selv4].mean() / max(v.y.mean(), 1e-9)), 3),
                                      "recall_unseen": round(float(v.y[selv4 & un].sum() / max(v.y[un].sum(), 1)), 3),
                                      "unseen_events": int(un.sum()), "unseen_traded": int(v.y[un].sum())}
    X.to_parquet(OUT / "events_groupP.parquet", index=False)
    print(json.dumps({k: res[k] for k in ("members", "by_split", "build_fitted_logistic", "v4_build_on_same_events")}, indent=1, default=str))
    json.dump(res, open(RES / "selection_groupP.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
