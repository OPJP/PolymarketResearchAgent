"""Iteration 3, information panel P1 (X22) and assumptions panel P2 (X27): event-level selection with bo3.gg
pre-match fields (stars, tier, tier_rank, bookmaker line) and an activity + GRID-flag rule without the league rate.

Data: bo3.gg /api/v2/matches/finished for 2026-10-15..10-22 (development; nothing at or after H is requested),
matched to the 384 Gamma CS2 events of 16-22 Oct (events_sel.parquet) by both normalized team names in the bo3 slug
and |start - gameStart| <= 3 h. BUILD = gs in [10-16, 10-21), VALIDATE = [10-21, 10-23).
Models (logistic, fitted on BUILD, scored on VALIDATE): A = activity (log1p e_pre_n, e_pre_v, e_pre_w);
G = A + GRID flag; S = G + bo3 stars (+ matched flag); V2 = the frozen v2 score (selection_scores.parquet) and
V2 + stars. Event bootstrap of the AUC gain over A (4000 draws); recall / lift at the 20th percentile of the fitted
positives' scores; per VALIDATE day. Output: results/selection_bo3.json, .cache/.../bo3_matches_15_22.parquet
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from polyrea.adapters.http import shared_client  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
H = 1792713600
VAL0 = 1792540800  # 2026-10-21
DAYS = ["2026-10-%02d" % d for d in range(15, 23)]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def fetch():
    h = shared_client()
    rows = []
    for day in DAYS:
        d, _ = h.get_json("https://api.bo3.gg/api/v2/matches/finished", {"date": day, "filter[discipline_id][eq]": 1},
                          adapter="bo3gg.matches", max_age=None)
        for tier, v in d["data"]["tiers"].items():
            for m in v.get("matches", []):
                st = pd.Timestamp(m["start_date"]).timestamp() if m.get("start_date") else np.nan
                if st == st and st >= H:
                    continue
                t1, t2 = m.get("team1") or {}, m.get("team2") or {}
                t1 = t1 if isinstance(t1, dict) else {"name": t1}
                t2 = t2 if isinstance(t2, dict) else {"name": t2}
                rows.append({"slug": m["slug"], "start": st, "stars": m.get("stars"), "tier": m.get("tier"),
                             "tier_group": tier, "bo": m.get("bo_type"), "bet": bool(m.get("bet_updates")),
                             "ai": bool(m.get("ai_predictions")), "t1": norm(t1.get("name") or t1.get("slug") or ""),
                             "t2": norm(t2.get("name") or t2.get("slug") or ""), "t1_id": m.get("team1_id"), "t2_id": m.get("team2_id"),
                             "tour": (m.get("tournament") or {}).get("name") if isinstance(m.get("tournament"), dict) else None,
                             "tier_rank": (m.get("tournament") or {}).get("tier_rank") if isinstance(m.get("tournament"), dict) else m.get("tier_rank")})
    b = pd.DataFrame(rows).drop_duplicates("slug")
    b.to_parquet(OUT / "bo3_matches_15_22.parquet", index=False)
    return b


def match(e, b, u):
    outs = {}
    for r in u.itertuples():
        if r.event_slug not in outs:
            o = json.loads(r.outcomes) if isinstance(r.outcomes, str) else r.outcomes
            outs[r.event_slug] = (norm(o[0]), norm(o[1]))
    ns = b.slug.map(norm).to_numpy()
    st = b.start.to_numpy()
    out = []
    for r in e.itertuples():
        a, c = outs.get(r.event_slug, ("", ""))
        a6, c6 = a[:6], c[:6]
        best = None
        if a6 and c6:
            for i in range(len(b)):
                if a6 in ns[i] and c6 in ns[i] and abs(st[i] - r.gs) <= 3 * 3600:
                    if best is None or abs(st[i] - r.gs) < abs(st[best] - r.gs):
                        best = i
        out.append(best)
    return out


def boot_gain(y, s1, s0, ev_day, n=4000, seed=3):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    g = []
    for _ in range(n):
        k = rng.choice(idx, len(idx), replace=True)
        if y[k].min() == y[k].max():
            continue
        g.append(roc_auc_score(y[k], s1[k]) - roc_auc_score(y[k], s0[k]))
    g = np.array(g)
    return [round(float(np.percentile(g, 2.5)), 4), round(float(np.percentile(g, 97.5)), 4)], round(float((g <= 0).mean()), 4)


def rec_lift(y_fit, s_fit, y, s):
    thr = np.percentile(s_fit[y_fit == 1], 20)
    pick = s >= thr
    rec = float(y[pick].sum() / max(y.sum(), 1))
    prec = float(y[pick].mean()) if pick.any() else 0.0
    return round(rec, 3), round(prec / max(y.mean(), 1e-9), 3)


def main():
    b = fetch()
    e = pd.read_parquet(OUT / "events_sel.parquet")
    u = pd.read_parquet(OUT / "universe.parquet", columns=["event_slug", "outcomes", "smt"])
    u = u[u.smt == "moneyline"]
    hit = match(e, b, u)
    e["bo3_i"] = hit
    e["matched"] = e.bo3_i.notna()
    for c in ("stars", "tier", "bet", "ai", "tier_rank", "t1_id", "t2_id", "slug"):
        e[c] = [b.iloc[int(i)][c] if i == i and i is not None else None for i in e.bo3_i]
    e["stars_f"] = pd.to_numeric(e.stars, errors="coerce").fillna(-1)
    e["minid"] = [min(x or 1e6, y or 1e6) if m else 1e6 for x, y, m in zip(e.t1_id, e.t2_id, e.matched)]
    e["la"] = np.log1p(e.e_pre_n.fillna(0))
    e["lv"] = np.log1p(e.e_pre_v.fillna(0))
    e["lw"] = np.log1p(e.e_pre_w.fillna(0))
    e["bet"] = e.bet.map(lambda v: 1.0 if v is True else 0.0)
    e["grid_f"] = e.grid.astype(float)
    sc = pd.read_parquet(OUT / "selection_scores.parquet")
    res = {"bo3_matches": int(len(b)), "events": int(len(e)), "matched": int(e.matched.sum()),
           "matched_by_split_grid": e.groupby([e.gs >= VAL0, "grid"]).matched.agg(["size", "sum"]).reset_index().astype(str).values.tolist(),
           "traded_rate_by_stars_nonGRID": e[~e.grid].groupby("stars_f").y.agg(["size", "mean"]).round(3).reset_index().values.tolist(),
           "selection_scores_columns": list(sc.columns)}
    bu, va = e[e.gs < VAL0], e[(e.gs >= VAL0) & (e.gs < H)]
    feats = {"A": ["la", "lv", "lw"], "G": ["la", "lv", "lw", "grid_f"], "S": ["la", "lv", "lw", "grid_f", "stars_f"],
             "S2": ["la", "lv", "lw", "grid_f", "stars_f", "bet"], "Sonly": ["grid_f", "stars_f"]}
    scores = {}
    for k, f in feats.items():
        X = bu[f].astype(float).to_numpy()
        lr = LogisticRegression(C=1.0, max_iter=2000).fit(X, bu.y)
        scores[k] = (lr.predict_proba(X)[:, 1], lr.predict_proba(va[f].astype(float).to_numpy())[:, 1],
                     dict(zip(f, np.round(lr.coef_[0], 3))))
    # frozen v2 score if available
    if "event_slug" in sc.columns:
        scol = [c for c in sc.columns if c not in ("event_slug", "y", "gs", "split")]
        res["v2_score_col"] = scol
    y = va.y.to_numpy()
    out = {}
    for k, (sb, sv, coef) in scores.items():
        auc = roc_auc_score(y, sv)
        ci, p = boot_gain(y, sv, scores["A"][1], None) if k != "A" else (None, None)
        rec, lift = rec_lift(bu.y.to_numpy(), sb, y, sv)
        days = {}
        for dname, m in (("10-21", va.gs < VAL0 + 86400), ("10-22", va.gs >= VAL0 + 86400)):
            m = m.to_numpy()
            if y[m].min() != y[m].max():
                days[dname] = {"auc": round(roc_auc_score(y[m], sv[m]), 4), "base": round(roc_auc_score(y[m], scores["A"][1][m]), 4),
                               "rec_lift": rec_lift(bu.y.to_numpy(), sb, y[m], sv[m])}
        out[k] = {"auc": round(auc, 4), "gain_vs_A": round(auc - roc_auc_score(y, scores["A"][1]), 4), "gain_ci95": ci, "p_gain_le0": p,
                  "recall": rec, "lift": lift, "coef": coef, "days": days}
    # non-GRID only
    ng = (~va.grid).to_numpy()
    out["nonGRID_only"] = {k: round(roc_auc_score(y[ng], scores[k][1][ng]), 4) for k in scores}
    res["models"] = out
    res["validate"] = {"events": int(len(va)), "traded": int(y.sum())}
    json.dump(res, open(RES / "selection_bo3.json", "w"), indent=1, default=str)
    e.drop(columns=["bo3_i"]).to_parquet(OUT / "events_sel_bo3.parquet", index=False)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
