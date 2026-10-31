"""Event-level selection (panel X: GRID boundary + league prior), BUILD-fitted, scored on VALIDATE.
Unit = CS2 event (all its moneyline/child_moneyline markets) with earliest gameStartTime in the split.
Label = wallet has >= 1 fill in any market of the event. Listing-only rule S_lg: 0 for GRID events (gridSeriesId set),
else league rate among BUILD non-GRID events, shrunk (k=3) toward the BUILD non-GRID tier rate.
Baseline B_act: logistic on log1p(pre-game prints, volume, distinct wallets in [gs-1h, gs)) of the event (wallet
excluded). Combined: logistic on B_act features + S_lg. Gains with an event bootstrap (4000 draws)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import H, OUT, RES, SPLIT, MAKER_START, auc  # noqa: E402
from selection import frame  # noqa: E402

def thr_metrics(sb, yb, sv, yv, lift_min=3.0):
    base_b = yb.mean(); best = None
    for t in np.unique(sb)[::-1]:
        sel = sb >= t
        if sel.sum() == 0: continue
        if yb[sel].mean() / base_b >= lift_min: best = t
    if best is None: return {"thr": None}
    sel = sv >= best; base = yv.mean()
    prec = yv[sel].mean() if sel.sum() else float("nan")
    return {"thr": float(best), "val_recall": round(float(yv[sel].sum() / yv.sum()), 3), "val_lift": round(float(prec / base), 2),
            "val_precision": round(float(prec), 3), "val_selected": int(sel.sum())}

def league_score(b, v, k=3.0):
    nb = b[~b.grid]
    prior = nb.y.mean(); tr = nb.groupby("tier").y.mean(); lg = nb.groupby("league").y.agg(["sum", "size"])
    tier_rate = v.tier.map(tr).fillna(prior)
    s = v.league.map(lg["sum"]).fillna(0); n = v.league.map(lg["size"]).fillna(0)
    out = ((s + k * tier_rate) / (n + k)).astype(float)
    return np.where(v.grid, 0.0, out)

def main():
    em = pd.read_parquet(OUT / "events_meta.parquet")
    u = frame()  # market-level, gs in [MAKER_START, H), with pre-game activity and y
    ev = u.groupby("event_slug").agg(y=("y", "max"), gs=("gs_ts", "min"), n_mk=("cid", "size"), e_pre_n=("pre_n", "sum"),
                                       e_pre_v=("pre_v", "sum"), e_pre_w=("pre_w", "sum"), league=("league", "first"),
                                       tier=("tier", "first")).reset_index()
    ev = ev.merge(em[["event_slug", "grid_series_id", "resolution_source", "created_at"]], on="event_slug", how="left")
    ev["grid"] = ev.grid_series_id.notna()
    ev["lead_h"] = (ev.gs - ev.created_at) / 3600
    b, v = ev[ev.gs < SPLIT].copy(), ev[ev.gs >= SPLIT].copy()
    res = {"events_build": len(b), "events_val": len(v), "pos_build": int(b.y.sum()), "pos_val": int(v.y.sum()),
           "grid_events_build": int(b.grid.sum()), "grid_traded_build": int(b[b.grid].y.sum()),
           "grid_events_val": int(v.grid.sum()), "grid_traded_val": int(v[v.grid].y.sum()),
           "nongrid_rate_build": round(float(b[~b.grid].y.mean()), 3), "nongrid_rate_val": round(float(v[~v.grid].y.mean()), 3)}
    b["s_lg"] = league_score(b, b); v["s_lg"] = league_score(b, v)
    b["s_grid"] = (~b.grid).astype(float); v["s_grid"] = (~v.grid).astype(float)
    res["S_grid_only"] = {"val_auc": round(auc(v.s_grid, v.y), 4)}
    res["S_lg"] = {"val_auc": round(auc(v.s_lg, v.y), 4)} | thr_metrics(b.s_lg.to_numpy(), b.y.to_numpy(), v.s_lg.to_numpy(), v.y.to_numpy())
    from sklearn.linear_model import LogisticRegression
    act = ["e_pre_n", "e_pre_v", "e_pre_w"]
    def X(d, cols): return np.column_stack([np.log1p(d[c].fillna(0).to_numpy()) if c in act else d[c].to_numpy() for c in cols])
    scores = {}
    for name, cols in (("B_act", act), ("S_lg_act", act + ["s_lg"])):
        m = LogisticRegression(max_iter=5000).fit(X(b, cols), b.y)
        sv = m.predict_proba(X(v, cols))[:, 1]; sb = m.predict_proba(X(b, cols))[:, 1]
        scores[name] = sv
        res[name] = {"val_auc": round(auc(sv, v.y), 4)} | thr_metrics(sb, b.y.to_numpy(), sv, v.y.to_numpy())
    # also gradient boosting baseline (same class for both)
    import lightgbm as lgb
    for name, cols in (("B_act_gbm", act), ("S_lg_act_gbm", act + ["s_lg"])):
        m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=7, min_child_samples=10, max_bin=63, verbose=-1).fit(X(b, cols), b.y)
        sv = m.predict_proba(X(v, cols))[:, 1]; scores[name] = sv
        res[name] = {"val_auc": round(auc(sv, v.y), 4)}
    scores["S_lg"] = v.s_lg.to_numpy()
    y = v.y.to_numpy(); rng = np.random.default_rng(7); n = len(y)
    def boot(a, bname):
        g = []
        for _ in range(4000):
            i = rng.integers(0, n, n)
            if y[i].min() == y[i].max(): continue
            g.append(auc(scores[a][i], y[i]) - auc(scores[bname][i], y[i]))
        g = np.array(g); return {"gain": round(float(auc(scores[a], y) - auc(scores[bname], y)), 4), "ci95": [round(float(np.quantile(g, .025)), 4), round(float(np.quantile(g, .975)), 4)], "p_le0": round(float((g <= 0).mean()), 4)}
    res["gain_S_lg_vs_B_act"] = boot("S_lg", "B_act")
    res["gain_S_lg_act_vs_B_act"] = boot("S_lg_act", "B_act")
    res["gain_S_lg_act_gbm_vs_B_act_gbm"] = boot("S_lg_act_gbm", "B_act_gbm")
    # tables
    v2 = v.assign(platform=v.resolution_source.fillna("").str.extract(r"https?://(?:www\.)?([a-z]+)\.")[0])
    res["val_by_league_nongrid"] = v2[~v2.grid].groupby("league").y.agg(["sum", "size"]).sort_values("size", ascending=False).head(25).astype(int).to_dict("index")
    allv = pd.concat([b, v2])
    res["lead_hours_grid_vs_not"] = {"grid": round(float(allv[allv.grid].lead_h.median()), 1), "nongrid": round(float(allv[~allv.grid].lead_h.median()), 1)}
    json.dump(res, open(RES / "results/selection_event.json", "w"), indent=1, default=str)
    print(json.dumps({k: res[k] for k in res if not k.startswith("val_by")}, indent=1, default=str))
    ev.to_parquet(OUT / "events_sel.parquet", index=False)

if __name__ == "__main__":
    main()
