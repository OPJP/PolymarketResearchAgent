"""Iteration 8 (A1 / X69): R3's presence model class on BTC 15m windows (same features via code8/features15.py, same
LightGBM parameters and rounds, clock features), fitted on BUILD (15m windows starting 2026-10-09..26) and scored on
VALIDATE (2026-10-27..30, aggregate only); plus the union BTC 5m (frozen R3, code/presence3_*.txt on the lot panels) +
BTC 15m pooled presence AUC on VALIDATE. With 'save' writes code/presence15_{rule,activity}.txt.
    python code8/train15.py [save]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE.parent / "code4"))
import train2 as T  # noqa: E402
from train6 import add_clock, CLOCK  # noqa: E402

C = ROOT / ".cache/re/directional-maker"
V0, V1 = 1793059200, 1793404800


def main(save: bool):
    p = pd.concat([pd.read_parquet(f) for f in sorted((C / "p15").glob("panel15_day_*.parquet"))], ignore_index=True)
    p = add_clock(p)
    b = p[p.start_ts < V0].reset_index(drop=True)
    v = p[(p.start_ts >= V0) & (p.start_ts < V1)].reset_index(drop=True)
    feats = {"rule": T.SETS["all_path_xwin"] + CLOCK, "activity": T.SETS["activity"]}
    res = {"build_rows": int(len(b)), "validate_rows": int(len(v)), "build_pos": round(float(b.y.mean()), 4),
           "validate_pos": round(float(v.y.mean()), 4), "validate_windows": int(v.cid.nunique())}
    for nm, f in feats.items():
        m = lgb.train(T.PARAMS, lgb.Dataset(b[f], b["y"]), T.ROUNDS)
        v["p_" + nm] = m.predict(v[f])
        if save:
            m.save_model(str(HERE.parent / "code" / f"presence15_{nm}.txt"))
    act = v.groupby("cid")["y"].transform("max") > 0
    res["btc15m"] = {"auc": round(T.auc(v.y, v.p_rule), 4), "baseline": round(T.auc(v.y, v.p_activity), 4),
                     "within_active": round(T.auc(v.y[act], v.p_rule[act]), 4), "active_window_share": round(float(act.groupby(v.cid).max().mean()), 3),
                     "side": T.side_metrics(v, "p_rule"), "side_activity": T.side_metrics(v, "p_activity")["acc"]}
    # union with BTC 5m (frozen R3 models on the lot panels)
    q = pd.concat([pd.read_parquet(C / "exam" / f"panel_day_{d}.parquet") for d in range(V0, V1, 86400)], ignore_index=True)
    q = add_clock(q[[c for c in q.columns if not c.startswith("p_")]])
    r3 = lgb.Booster(model_file=str(HERE.parent / "code" / "presence3_rule.txt"))
    r3a = lgb.Booster(model_file=str(HERE.parent / "code" / "presence3_activity.txt"))
    q["p_rule"] = r3.predict(q[feats["rule"]])
    q["p_activity"] = r3a.predict(q[feats["activity"]])
    res["btc5m_r3_check"] = {"auc": round(T.auc(q.y, q.p_rule), 4), "baseline": round(T.auc(q.y, q.p_activity), 4)}
    u = pd.concat([q[["y", "p_rule", "p_activity", "start_ts"]].assign(fam="5m"), v[["y", "p_rule", "p_activity", "start_ts"]].assign(fam="15m")])
    res["union_5m_15m"] = {"auc": round(T.auc(u.y, u.p_rule), 4), "baseline": round(T.auc(u.y, u.p_activity), 4),
                           "rows": int(len(u)), "pos": int(u.y.sum())}
    # 2-h block bootstrap of the union gain
    rng = np.random.default_rng(8)
    blk = (u.start_ts // 7200).to_numpy()
    ub = np.unique(blk)
    idx = {k: np.where(blk == k)[0] for k in ub}
    g = []
    for _ in range(300):
        pick = rng.choice(ub, len(ub), replace=True)
        ii = np.concatenate([idx[k] for k in pick])
        g.append(T.auc(u.y.values[ii], u.p_rule.values[ii]) - T.auc(u.y.values[ii], u.p_activity.values[ii]))
    res["union_5m_15m"]["gain_ci95"] = [round(float(np.quantile(g, .025)), 4), round(float(np.quantile(g, .975)), 4)]
    (HERE.parent / "results" / "iter8_train15.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main("save" in sys.argv)
