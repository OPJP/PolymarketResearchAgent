"""Iteration 5, assumptions panel iter4 P4 (X61): session-clean selection labels and the downtime risk.

1. Operating windows: the wallet's orders in ALL its markets (CS2 + Dota 2; orders.parquet), 16-22 Oct.
   An event is "in session" if the wallet signed any order anywhere in [gs, gs + 1 h].
2. Label cleaning at an operations boundary (BUILD only, never a feature): drop BUILD skips that are out of session
   (the bot was off), refit the frozen recipe (league rate shrunk k = 3 to the tier rate, GRID -> 0; logistic on
   log1p pre-game prints / USD / wallets + s_lg; threshold = 20th percentile of the fitted positives' scores) and score
   VALIDATE on ALL events (as the examiner will) and per day.
3. Sensitivity: VALIDATE metrics if one VALIDATE day had a 3-hour session (traded events outside it become skips).
Output: results/session_labels.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
VAL0, H = 1792540800, 1792713600
ACT = ["e_pre_n", "e_pre_v", "e_pre_w"]


def fit(b, k=3.0):
    ng = b[~b.grid]
    prior = float(ng.y.mean())
    tr = ng.groupby(ng.tier.astype(str)).y.mean().to_dict()
    ls = ng.groupby("league").y.sum().to_dict()
    ln = ng.groupby("league").y.size().to_dict()
    C = {"k": k, "prior": prior, "tier_rate": tr, "league_sum": ls, "league_n": ln}
    X = feats(b, C)
    m = LogisticRegression(max_iter=5000).fit(X, b.y)
    a = LogisticRegression(max_iter=5000).fit(X[:, :3], b.y)
    C.update(coef=m.coef_[0].tolist(), icpt=float(m.intercept_[0]), act_coef=a.coef_[0].tolist(), act_icpt=float(a.intercept_[0]))
    sb = score(b, C)
    C["thr"] = float(np.quantile(sb[b.y.to_numpy() == 1], 0.2))
    return C


def feats(e, C):
    tier = e.tier.astype(str)
    tr = tier.map(C["tier_rate"]).fillna(C["prior"]).astype(float)
    s = e.league.map(C["league_sum"]).fillna(0).astype(float)
    n = e.league.map(C["league_n"]).fillna(0).astype(float)
    slg = np.where(e.grid.to_numpy(), 0.0, ((s + C["k"] * tr) / (n + C["k"])).to_numpy())
    return np.column_stack([np.log1p(e[c].fillna(0).to_numpy(float)) for c in ACT] + [slg])


def score(e, C):
    return 1 / (1 + np.exp(-(feats(e, C) @ np.array(C["coef"]) + C["icpt"])))


def base(e, C):
    return feats(e, C)[:, :3] @ np.array(C["act_coef"]) + C["act_icpt"]


def metrics(v, C, boot=4000):
    y = v.y.to_numpy()
    sc, ba = score(v, C), base(v, C)
    out = {"n": int(len(v)), "traded": int(y.sum()), "auc": round(float(roc_auc_score(y, sc)), 4), "baseline": round(float(roc_auc_score(y, ba)), 4)}
    sel = sc >= C["thr"]
    out["recall"] = round(float(y[sel].sum() / max(y.sum(), 1)), 3)
    out["lift"] = round(float(y[sel].mean() / max(y.mean(), 1e-9)), 3) if sel.sum() else None
    ng = ~v.grid.to_numpy()
    if y[ng].min() != y[ng].max():
        out["auc_within_nongrid"] = round(float(roc_auc_score(y[ng], sc[ng])), 4)
        out["baseline_within_nongrid"] = round(float(roc_auc_score(y[ng], ba[ng])), 4)
    rng = np.random.default_rng(0)
    g = []
    for _ in range(boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        g.append(roc_auc_score(y[i], sc[i]) - roc_auc_score(y[i], ba[i]))
    g = np.array(g)
    out["gain"] = round(out["auc"] - out["baseline"], 4)
    out["gain_ci95"] = [round(float(np.quantile(g, 0.025)), 4), round(float(np.quantile(g, 0.975)), 4)]
    out["gain_p_le0"] = round(float((g <= 0).mean()), 4)
    return out


def main():
    e = pd.read_parquet(OUT / "events_sel.parquet")
    e["grid"] = e.grid.astype(bool)
    e["tier"] = e.tier.astype(str).str.replace(r"\.0$", "", regex=True)
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms"])
    s = np.sort(o.sign_ms.to_numpy(float) / 1000.0)
    s = s[(s > 1.7e9) & (s < 1.8e9)]
    e["active"] = [bool(np.searchsorted(s, g + 3600) > np.searchsorted(s, g)) for g in e.gs.to_numpy(float)]
    # daily operating windows (first / last order per UTC day, and gaps > 30 min)
    days = {}
    d = pd.Series(s)
    for day, x in d.groupby((d // 86400).astype(int)):
        x = x.to_numpy()
        gaps = [(round(float(x[i]), 0), round(float(x[i + 1]), 0)) for i in np.flatnonzero(np.diff(x) > 1800)]
        days[pd.Timestamp(day * 86400, unit="s").strftime("%m-%d")] = {
            "first": pd.Timestamp(x[0], unit="s").strftime("%H:%M"), "last": pd.Timestamp(x[-1], unit="s").strftime("%H:%M"),
            "gaps_over_30min": [(pd.Timestamp(a, unit="s").strftime("%H:%M"), pd.Timestamp(b, unit="s").strftime("%H:%M")) for a, b in gaps]}
    b = e[e.gs < VAL0].copy()
    v = e[(e.gs >= VAL0) & (e.gs < H)].copy()
    res = {"operating_windows": days,
           "build_out_of_session_skips": int(((b.y == 0) & ~b.active).sum()),
           "build_out_of_session_traded": int(((b.y == 1) & ~b.active).sum()),
           "validate_out_of_session_skips": int(((v.y == 0) & ~v.active).sum()),
           "build_events": int(len(b)), "validate_events": int(len(v))}
    C0 = fit(b)
    bc = b[~((b.y == 0) & ~b.active)]
    C1 = fit(bc)
    res["frozen_recipe_build_all"] = {"val_all": metrics(v, C0)}
    res["session_clean_build"] = {"val_all": metrics(v, C1), "val_in_session": metrics(v[v.active], C1)}
    for nm, C in (("frozen", C0), ("clean", C1)):
        res[f"{nm}_league_rates"] = {lg: round((C["league_sum"].get(lg, 0) + C["k"] * C["tier_rate"].get("3", C["prior"])) / (C["league_n"].get(lg, 0) + C["k"]), 3)
                                     for lg in ("Stake Pulse", "PGL", "NODWIN Clutch Series", "DraculaN", "Stake Ranked")}
        per = {}
        for day, x in v.groupby((v.gs // 86400).astype(int)):
            per[pd.Timestamp(day * 86400, unit="s").strftime("%m-%d")] = metrics(x, C, boot=2000)
        res[f"{nm}_per_day"] = per
    # sensitivity: one VALIDATE day with a 3-h session (14:00-17:00 UTC), traded events outside it -> skipped
    sens = {}
    for day in sorted(set((v.gs // 86400).astype(int))):
        w = v.copy()
        dd = (w.gs // 86400).astype(int) == day
        hr = (w.gs % 86400) / 3600
        off = dd & ((hr < 14) | (hr >= 17))
        w.loc[off, "y"] = 0
        sens[pd.Timestamp(day * 86400, unit="s").strftime("%m-%d")] = metrics(w, C1, boot=2000)
    res["sensitivity_3h_session_one_day"] = sens
    (RES / "session_labels.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1)[:7000])


if __name__ == "__main__":
    main()
