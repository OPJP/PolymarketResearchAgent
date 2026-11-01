"""Iteration 8, X113 + X102 (assumptions P2, information P2): selection = the feed's coverage today, read from the
feed subscribers' public takes in EARLIER events of the same league (point-in-time, wallet-independent), against the
same feature built from all takers (league popularity control).

Pre-registered before computing (written in NOTES iteration 8): primary variant cov24 = number of distinct feed
subscribers (P4e, 0x2005d16a, 0x8a80528d, 0xddb6e624, 0xf1ee4842, P93) with a taker print in another event of the same
league whose game start is in [gs_e - 24 h, gs_e), counting only prints stamped before gs_e. Variants: cov72 (72 h), P4e
only (p4e24), same day (UTC). Control: log1p distinct takers in the same earlier events (all24). Scored WITHOUT refit as
raw scores (AUC, recall / lift at score > 0) on BUILD (10-16..10-20), VALIDATE (10-21..22) and VALIDATE events of leagues
unseen in BUILD; plus a BUILD-fitted logistic (activity + GRID + cov24) scored on VALIDATE, against v3 and the
activity baseline. Labels: the wallet traded the event (events_sel.y). Universe: CS2 events of events_sel.
Output: results/selection_feedcov.json
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
WALLET = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
SUBS = {"0x4ebc2722adc772bde8680792d0a6fdf15499a33d", "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
        "0x8a80528dce46711a54aa3455c2cc81dea51e11c5", "0xddb6e6246546230503f153506ac1e9914978b9b3",
        "0xf1ee4842fa0c7283632185e42577027452d4519c", "0x93078b5dd1c34d0f288d2f51b23f1347520d9da3"}
P4E = "0x4ebc2722adc772bde8680792d0a6fdf15499a33d"
BUILD_END, H = 1792540800, 1792713600


def auc(s, y):
    from scipy.stats import rankdata
    s, y = np.asarray(s, float), np.asarray(y).astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    u = pd.read_parquet(OUT / "universe.parquet")
    u = u[u.smt.isin(["moneyline", "child_moneyline"])].copy()
    u["gs_ts"] = pd.to_numeric(u.gs_ts, errors="coerce")
    eg = u.groupby("event_slug").agg(gs=("gs_ts", "min"), league=("league", "first")).reset_index()
    cid_ev = dict(zip(u.cid, u.event_slug))
    # per event: subscriber takers and all takers with their print timestamps (taker-only windowed tapes)
    sub_t, all_t = {}, {}
    for f in glob.glob(str(OUT / "tapes" / "*_tkw.parquet")):
        cid = Path(f).name.split("_")[0]
        e = cid_ev.get(cid)
        if e is None:
            continue
        d = pd.read_parquet(f, columns=["proxyWallet", "timestamp"])
        d["proxyWallet"] = d.proxyWallet.str.lower()
        d = d[d.proxyWallet != WALLET]
        for w_, t in zip(d.proxyWallet, d.timestamp):
            all_t.setdefault(e, []).append((w_, int(t)))
            if w_ in SUBS:
                sub_t.setdefault(e, []).append((w_, int(t)))
    eg["has_tape"] = eg.event_slug.isin(all_t)
    by_lg = {lg: g.sort_values("gs") for lg, g in eg.groupby("league")}
    feats = []
    for r in eg.itertuples():
        g = by_lg.get(r.league)
        o = {"event_slug": r.event_slug}
        for hrs, key in ((24, "24"), (72, "72")):
            prev = g[(g.gs >= r.gs - hrs * 3600) & (g.gs < r.gs) & (g.event_slug != r.event_slug)] if g is not None else g
            ss, s4, aa = set(), 0, set()
            if prev is not None:
                for e2 in prev.event_slug:
                    for w_, t in sub_t.get(e2, []):
                        if t < r.gs:
                            ss.add(w_)
                            s4 += w_ == P4E
                    for w_, t in all_t.get(e2, []):
                        if t < r.gs:
                            aa.add(w_)
            o[f"cov{key}"], o[f"p4e{key}"], o[f"all{key}"] = len(ss), int(s4 > 0), np.log1p(len(aa))
            o[f"nprev{key}"] = 0 if prev is None else int(len(prev))
        day0 = r.gs // 86400 * 86400
        prev = g[(g.gs >= day0) & (g.gs < r.gs) & (g.event_slug != r.event_slug)] if g is not None else None
        ss = set()
        if prev is not None:
            for e2 in prev.event_slug:
                ss |= {w_ for w_, t in sub_t.get(e2, []) if t < r.gs}
        o["covday"] = len(ss)
        feats.append(o)
    F = pd.DataFrame(feats)
    es = pd.read_parquet(OUT / "events_sel.parquet")
    X = es.merge(F, on="event_slug", how="left")
    X["grid"] = X.grid.astype(bool)
    X["split"] = np.where(X.gs < BUILD_END, "build", "validate")
    bl = set(X.loc[X.split == "build", "league"])
    X["unseen"] = (X.split == "validate") & ~X.league.isin(bl)
    res = {"events": int(len(X)), "by_split": {}}
    for sp, g in [("build", X[X.split == "build"]), ("validate", X[X.split == "validate"]),
                  ("validate_unseen_league", X[X.unseen]), ("validate_nongrid", X[(X.split == "validate") & ~X.grid])]:
        o = {"events": int(len(g)), "traded": int(g.y.sum())}
        for c in ("cov24", "cov72", "p4e24", "covday", "all24", "all72"):
            o[f"auc_{c}"] = round(auc(g[c].fillna(0), g.y), 4)
        for c in ("cov24", "p4e24", "cov72"):
            sel = g[c].fillna(0) > 0
            o[f"{c}_gt0"] = {"selected": int(sel.sum()), "recall": round(float(g.y[sel].sum() / max(g.y.sum(), 1)), 3),
                             "lift": round(float(g.y[sel].mean() / max(g.y.mean(), 1e-9)), 3) if sel.sum() else None}
        # non-GRID gate (the v3 hard boundary) combined with coverage
        sel = (~g.grid) & (g.cov24.fillna(0) > 0)
        o["nongrid_and_cov24"] = {"selected": int(sel.sum()), "recall": round(float(g.y[sel].sum() / max(g.y.sum(), 1)), 3),
                                  "lift": round(float(g.y[sel].mean() / max(g.y.mean(), 1e-9)), 3) if sel.sum() else None}
        res["by_split"][sp] = o
    # BUILD-fitted logistic: activity (3) + GRID + cov24 (+ control all24), scored on VALIDATE; v3 for reference
    from sklearn.linear_model import LogisticRegression
    b, v = X[X.split == "build"], X[X.split == "validate"]

    def mat(d, cols):
        m = [np.log1p(d[c].fillna(0).to_numpy(float)) for c in ("e_pre_n", "e_pre_v", "e_pre_w")]
        for c in cols:
            m.append(d[c].fillna(0).to_numpy(float) if c != "grid" else d.grid.to_numpy(float))
        return np.column_stack(m)
    fits = {}
    for name, cols in (("act", []), ("act_grid", ["grid"]), ("act_grid_cov24", ["grid", "cov24"]),
                       ("act_grid_all24", ["grid", "all24"]), ("act_grid_cov24_all24", ["grid", "cov24", "all24"]),
                       ("act_grid_p4e24", ["grid", "p4e24"])):
        lr = LogisticRegression(max_iter=5000, C=1.0).fit(mat(b, cols), b.y)
        sv = lr.predict_proba(mat(v, cols))[:, 1]
        sb = lr.predict_proba(mat(b, cols))[:, 1]
        thr = float(np.quantile(sb[b.y.to_numpy() == 1], 0.2))
        sel = sv >= thr
        fits[name] = {"auc_validate": round(auc(sv, v.y), 4), "auc_build_insample": round(auc(sb, b.y), 4),
                      "recall": round(float(v.y[sel].sum() / max(v.y.sum(), 1)), 3),
                      "lift": round(float(v.y[sel].mean() / max(v.y.mean(), 1e-9)), 3) if sel.sum() else None,
                      "coef": [round(float(c), 3) for c in lr.coef_[0]],
                      "auc_validate_unseen": round(auc(sv[v.unseen.to_numpy()], v.y[v.unseen]), 4) if v.unseen.sum() else None}
    res["build_fitted_logistic"] = fits
    try:
        import final_rule as FR
        C = FR.CALL["build"]
        ev = v.rename(columns={"e_pre_n": "n", "e_pre_v": "v", "e_pre_w": "w"}).copy()
        sc = FR.selection_score(ev, C)
        res["v3_build_on_validate"] = {"auc": round(auc(sc, v.y), 4),
                                       "auc_unseen": round(auc(sc[v.unseen.to_numpy()], v.y[v.unseen]), 4) if v.unseen.sum() else None}
    except Exception as e:  # noqa: BLE001
        res["v3_error"] = repr(e)[:200]
    res["tape_coverage_events"] = int(X.event_slug.isin(all_t).sum())
    res["subscriber_presence_by_grid"] = {str(k): round(float((g.cov24 > 0).mean()), 3) for k, g in X.groupby("grid")}
    X.to_parquet(OUT / "events_feedcov.parquet", index=False)
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(RES / "selection_feedcov.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
