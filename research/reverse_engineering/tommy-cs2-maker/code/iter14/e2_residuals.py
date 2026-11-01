"""E2 / E7 (BRIEF "Hidden dimensions and indicators", steps 2): out-of-fold BUILD residuals of the presence / selection
rule and their shape, plus residual synchrony across unrelated events.

BUILD = maker regime 10-16..10-21 (gameStartTime), bins of 30 s from code/build_bins.py (fill of the wallet in the bin).
Rule refitted out of fold: GroupKFold(5) over 2-hour blocks of the bin start. Per fold the league rate (the selection
component of v4 / v5) is recomputed from the training markets only, then a LightGBM presence model on market activity
(B0) + listing metadata (tier, scheduled hour, league rate) is fitted on the training bins (negatives subsampled 1:4
with weights) and scored on the held-out block. No own-state features.

Outputs (results/e2_residuals.json):
- OOF AUC overall and inside traded markets, and the OOF activity-only baseline (B0) for the same folds;
- selection residual: event-level OOF league score vs traded, misses by league / tier / hour / weekday;
- timing residual inside traded markets: mean (y - p) and AUC by elapsed time, hour, map vs match;
- E7: residual_clustering of the wallet's maker-order SIGNING times (orders.parquet, B1) whose signing bin is
  under-predicted (p_oof below the median over signing bins), across different events (market key = event), only
  orders >= 10 min after the market's start; delta 0.5 / 2 / 10 s; also on ALL signing times as a control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tools"))
import indicators as ind  # noqa: E402

OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
B0 = ["m_n30", "m_v30", "m_n120", "m_v120", "m_n600", "m_v600", "m_cum", "m_tsl", "m_p", "m_dev", "m_dp60", "m_dp300",
      "m_nw600", "e_n30", "e_v30", "e_n120", "e_v120", "e_n600", "e_v600", "e_cum", "e_tsl", "e_pre", "elapsed",
      "is_match", "map_no"]
META = ["tier", "gs_hour", "league_rate"]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, max_bin=63, verbose=-1, seed=7)


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    if y.min() == y.max():
        return None
    r = pd.Series(s).rank().to_numpy()
    n1 = y.sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1)))


def main():
    b = pd.read_parquet(OUT / "bins_1792108800_1792540800.parquet")
    b["league"] = b["league"].astype(str)
    b["blk"] = (b["start"] // 7200).astype(int)
    b["p_full"] = np.nan
    b["p_b0"] = np.nan
    b["lr_oof"] = np.nan
    rng = np.random.default_rng(0)
    for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(b, b["y"], b["blk"])):
        btr, bte = b.iloc[tr], b.iloc[te]
        mk = btr.groupby("cid").agg(y=("y", "max"), league=("league", "first"), tier=("tier", "first"))
        prior = mk["y"].mean()
        lg = mk.groupby("league")["y"].agg(["sum", "size"])
        rate = ((lg["sum"] + 5 * prior) / (lg["size"] + 5)).to_dict()
        trate = mk.groupby("tier")["y"].mean().to_dict()

        def meta(d):
            lr = d["league"].map(rate)
            return lr.fillna(d["tier"].map(trate)).fillna(prior).astype(np.float32)
        Xtr = btr.copy()
        Xtr["league_rate"] = meta(btr)
        Xte = bte.copy()
        Xte["league_rate"] = meta(bte)
        keep = (Xtr["y"] == 1) | (rng.random(len(Xtr)) < 0.25)
        w = np.where(Xtr["y"][keep] == 1, 1.0, 4.0)
        for col, feats in (("p_full", B0 + META), ("p_b0", B0)):
            m = lgb.train(PARAMS, lgb.Dataset(Xtr.loc[keep, feats], Xtr.loc[keep, "y"], weight=w), num_boost_round=250)
            b.loc[b.index[te], col] = m.predict(Xte[feats])
        b.loc[b.index[te], "lr_oof"] = Xte["league_rate"].to_numpy()
        print("fold", k, flush=True)
    y = b["y"].to_numpy()
    traded_cids = set(b.loc[b.y == 1, "cid"])
    tm = b["cid"].isin(traded_cids).to_numpy()
    out = {"bins": int(len(b)), "positives": int(y.sum()), "markets": int(b.cid.nunique()), "traded_markets": len(traded_cids),
           "oof_auc_rule": round(auc(b.p_full, y), 4), "oof_auc_activity_b0": round(auc(b.p_b0, y), 4),
           "oof_auc_rule_in_traded_markets": round(auc(b.p_full[tm], y[tm]), 4),
           "oof_auc_b0_in_traded_markets": round(auc(b.p_b0[tm], y[tm]), 4)}
    # selection residual (event level)
    ev = b.groupby("event").agg(y=("y", "max"), lr=("lr_oof", "mean"), tier=("tier", "first"), league=("league", "first"),
                                hour=("gs_hour", "first"), start=("start", "min")).reset_index()
    ev["wd"] = pd.to_datetime(ev["start"], unit="s").dt.dayofweek
    out["selection_oof_auc_league_rate"] = round(auc(ev.lr, ev.y), 4)
    thr = ev.loc[ev.y == 1, "lr"].median()
    ev["miss"] = (ev.y == 1) & (ev.lr < ev.loc[ev.y == 0, "lr"].quantile(0.75))
    ev["fa"] = (ev.y == 0) & (ev.lr >= thr)
    out["selection_residual"] = {
        "events": int(len(ev)), "traded": int(ev.y.sum()),
        "missed_traded_events (OOF league score below the untraded 75th pct)": int(ev.miss.sum()),
        "false_alarm_events (untraded, score >= traded median)": int(ev.fa.sum()),
        "missed_by_tier": {str(k): int(v) for k, v in ev[ev.miss].tier.value_counts().items()},
        "missed_leagues": {str(k): int(v) for k, v in ev[ev.miss].league.value_counts().head(12).items()},
        "false_alarm_leagues": {str(k): int(v) for k, v in ev[ev.fa].league.value_counts().head(12).items()},
        "traded_rate_by_hour_block": {str(int(h)): [round(float(g.y.mean()), 3), int(len(g))] for h, g in ev.groupby(ev.hour // 4 * 4)},
        "traded_rate_by_weekday": {str(int(h)): [round(float(g.y.mean()), 3), int(len(g))] for h, g in ev.groupby("wd")},
        "missed_rate_by_hour_block": {str(int(h)): round(float(g.miss.sum() / max(g.y.sum(), 1)), 3) for h, g in ev.groupby(ev.hour // 4 * 4)},
    }
    # timing residual inside traded markets
    t = b[tm].copy()
    t["r"] = t.y - t.p_full
    t["el_b"] = pd.cut(t.elapsed, [-1, 10, 30, 60, 90, 120, 180, 240, 1e9])
    t["hod"] = ((t.start % 86400) // 3600 // 4 * 4).astype(int)

    def summ(g):
        return {"bins": int(len(g)), "pos_rate": round(float(g.y.mean()), 4), "mean_p": round(float(g.p_full.mean()), 4),
                "auc": (round(auc(g.p_full, g.y), 3) if g.y.nunique() > 1 else None)}
    out["timing_residual_by_elapsed_min"] = {str(k): summ(g) for k, g in t.groupby("el_b", observed=True)}
    out["timing_residual_by_hour_of_day_utc"] = {str(k): summ(g) for k, g in t.groupby("hod")}
    out["timing_residual_by_book"] = {("match" if k == 1 else "map"): summ(g) for k, g in t.groupby("is_match")}
    # E7 on signing times
    o = pd.read_parquet(OUT / "orders.parquet", columns=["sign_ms", "cid", "event", "gs_ts", "role"])
    o = o[(o.role == "maker") & (o.sign_ms / 1000 < 1792540800)].copy()
    o["s"] = o.sign_ms / 1000
    o["bin_start"] = (o.gs_ts + 30 * np.floor((o.s - o.gs_ts) / 30)).astype(np.int64)
    key = b.set_index(["cid", "start"])["p_full"]
    o["p"] = key.reindex(pd.MultiIndex.from_arrays([o.cid, o.bin_start])).to_numpy()
    o = o[np.isfinite(o.p) & ((o.s - o.gs_ts) >= 600)]
    med = o.p.median()
    un = o[o.p < med]
    e7 = {"orders_with_bin": int(len(o)), "unexplained_orders": int(len(un)), "events": int(o.event.nunique())}
    for dl in (0.5, 2.0, 10.0):
        r = ind.residual_clustering(un.s.to_numpy(), un.event.to_numpy(), delta_s=dl, n_null=300, top=8)
        ra = ind.residual_clustering(o.s.to_numpy(), o.event.to_numpy(), delta_s=dl, n_null=300, top=8)
        e7[f"delta_{dl}"] = {"unexplained": {k: r[k] for k in r if k in ("near", "band", "ratio", "p", "clusters")},
                             "all_signings": {k: ra[k] for k in ra if k in ("near", "band", "ratio", "p", "clusters")}}
        print(dl, e7[f"delta_{dl}"]["unexplained"].get("ratio"), e7[f"delta_{dl}"]["unexplained"].get("p"),
              e7[f"delta_{dl}"]["all_signings"].get("ratio"), e7[f"delta_{dl}"]["all_signings"].get("p"), flush=True)
    out["e7_residual_clustering"] = e7
    b[["cid", "event", "start", "y", "p_full", "p_b0", "lr_oof"]].to_parquet(OUT / "iter14_oof_bins.parquet", index=False)
    (RES / "e2_residuals.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if not isinstance(v, dict)}, indent=1))


if __name__ == "__main__":
    main()
