"""Presence models (BUILD fit, VALIDATE score): co-occurrence baseline vs. selection-aware models.

Feature sets
  B0  market activity only (co-occurrence baseline): prints / volume / price moves of this market and its
      event in the previous 30 / 120 / 600 s, time since last print, price level, elapsed time, match vs map.
  M1  B0 + listing metadata the wallet can select on (league tier, scheduled hour, league rate fitted on BUILD).
  M2  B0 + tier + hour (no league identity).
Reports VALIDATE AUC overall and inside the markets the wallet traded, plus feature importances.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, RES, auc  # noqa: E402

B0 = ["m_n30", "m_v30", "m_n120", "m_v120", "m_n600", "m_v600", "m_cum", "m_tsl", "m_p", "m_dev", "m_dp60", "m_dp300",
      "m_nw600", "e_n30", "e_v30", "e_n120", "e_v120", "e_n600", "e_v600", "e_cum", "e_tsl", "e_pre", "elapsed",
      "is_match", "map_no"]
PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=200, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, max_bin=63, verbose=-1, seed=7)


def league_rates(b: pd.DataFrame) -> tuple[dict, dict, float]:
    mk = b.groupby("cid").agg(y=("y", "max"), league=("league", "first"), tier=("tier", "first"))
    prior = mk["y"].mean()
    k = 5.0
    lg = mk.groupby("league", observed=True)["y"].agg(["sum", "size"])
    rate = ((lg["sum"] + k * prior) / (lg["size"] + k)).to_dict()
    tr = mk.groupby("tier")["y"].mean().to_dict()
    return rate, tr, prior


def add_meta(d: pd.DataFrame, rate: dict, tr: dict, prior: float) -> pd.DataFrame:
    d = d.copy()
    lr = d["league"].astype(str).map(rate)
    d["league_rate"] = lr.fillna(d["tier"].map(tr)).fillna(prior).astype(np.float32)
    return d


def fit_eval(b, v, feats, rounds=300):
    m = lgb.train(PARAMS, lgb.Dataset(b[feats], b["y"]), num_boost_round=rounds)
    pv = m.predict(v[feats])
    imp = dict(sorted(zip(feats, m.feature_importance("gain")), key=lambda x: -x[1]))
    tot = sum(imp.values())
    return m, pv, {k: round(x / tot, 3) for k, x in list(imp.items())[:10]}


def main() -> None:
    b = pd.read_parquet(OUT / "bins_1792108800_1792540800.parquet")
    v = pd.read_parquet(OUT / "bins_1792540800_1792713600.parquet")
    rate, tr, prior = league_rates(b)
    b, v = add_meta(b, rate, tr, prior), add_meta(v, rate, tr, prior)
    vt = v["cid"].isin(set(v.loc[v.y == 1, "cid"]))
    res = {"n_build": len(b), "pos_build": int(b.y.sum()), "n_val": len(v), "pos_val": int(v.y.sum())}
    sets = {"B0": B0, "M2": B0 + ["tier", "gs_hour"], "M1": B0 + ["tier", "gs_hour", "league_rate"],
            "META_only": ["tier", "gs_hour", "league_rate", "elapsed", "is_match", "map_no"]}
    for name, feats in sets.items():
        _, pv, imp = fit_eval(b, v, feats)
        res[name] = {"val_auc": round(auc(pv, v.y), 4), "val_auc_in_traded_markets": round(auc(pv[vt.to_numpy()], v.y[vt]), 4), "importance": imp}
        v[f"s_{name}"] = pv
        print(name, res[name], flush=True)
    v[["cid", "start", "y"] + [c for c in v.columns if c.startswith("s_")]].to_parquet(OUT / "val_scores.parquet", index=False)
    json.dump(res, open(RES / "results_presence_iter1.json", "w"), indent=1)


if __name__ == "__main__":
    main()
