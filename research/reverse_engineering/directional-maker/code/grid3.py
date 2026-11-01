"""Iteration 3, family N11 (grid position of the touch): the cluster quotes on the 0.01 grid, one tick below the last
print. LightGBM with max_bin 63 cannot see where the last clean print sits relative to that grid, so add it
explicitly: distance of last_s to the grid below, whether last_s is on the grid, and the implied cluster quote
gap (fair_s - (floor_to_grid(last_s) - 0.01)). R2 + these vs R2 on VALIDATE (same BUILD fit settings).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train2 import ACT, SPOT, PATH, XWIN, PARAMS, ROUNDS, auc, side_metrics, OUT, H, VAL0  # noqa: E402

R2 = ACT + SPOT + ["edge_s"] + PATH + XWIN
GRID = ["g_off", "g_on", "q_gap"]


def main():
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("panel2_day_*.parquet"))]
    p = pd.concat(fr, ignore_index=True)
    p = p[p["start_ts"] + 300 <= H].reset_index(drop=True)
    x = p["last_s"].to_numpy() * 100
    fl = np.floor(x + 1e-6)
    p["g_off"] = (x - fl).astype(np.float32)
    p["g_on"] = (np.abs(x - np.round(x)) < 1e-3).astype(np.float32)
    p["q_gap"] = (p["fair_s"] - (fl / 100 - 0.01)).astype(np.float32)
    b = p[p["start_ts"] < VAL0]
    v = p[p["start_ts"] >= VAL0].copy()
    res = {}
    for tag, feats in (("r2", R2), ("r2+grid", R2 + GRID), ("activity", ACT), ("activity+grid", ACT + ["g_off", "g_on"])):
        m = lgb.train(PARAMS, lgb.Dataset(b[feats], b["y"]), ROUNDS)
        v["p"] = m.predict(v[feats])
        res[tag] = {"auc": auc(v["y"], v["p"])}
        if tag.startswith("r2"):
            res[tag]["side"] = side_metrics(v, "p")["acc"]
        print(tag, json.dumps(res[tag]), flush=True)
    res["val_last_on_grid_share"] = float(v["g_on"].mean())
    (HERE.parent / "results_iter3_grid.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
