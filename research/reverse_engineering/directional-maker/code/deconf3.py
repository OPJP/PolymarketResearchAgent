"""Iteration 3, family N6 (deconfounding the operator schedule): in BUILD the cluster was more often off in
volatile hours (window on/off AUC of 1-h vol 0.39), in VALIDATE not (0.50), so a presence model fitted on all
BUILD windows partly learns BUILD's schedule. Variants: (a) R2 fitted on BUILD bins of active windows only
(P(fill | on), the schedule left out), (b) R2 without the slow vol feature sig, (c) both, (d) (a) plus
day-of-BUILD balancing weights. Scored on ALL VALIDATE bins (the primary metric) and within active windows.
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
from train2 import ACT, SPOT, PATH, XWIN, OWN, PARAMS, ROUNDS, auc, side_metrics, OUT, H, VAL0  # noqa: E402

R2 = ACT + SPOT + ["edge_s"] + PATH + XWIN


def main(save: bool):
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("panel2_day_*.parquet"))]
    p = pd.concat(fr, ignore_index=True)
    p = p[p["start_ts"] + 300 <= H].reset_index(drop=True)
    p["on"] = p.groupby("cid")["y"].transform("max") > 0
    b = p[p["start_ts"] < VAL0]
    v = p[p["start_ts"] >= VAL0].copy()
    res = {}
    noS = [c for c in R2 if c != "sig"]
    ACTn = ACT
    for tag, feats, sub in (("r2_all", R2, b), ("r2_on_only", R2, b[b["on"]]), ("r2_nosig", noS, b), ("r2_nosig_on_only", noS, b[b["on"]]),
                            ("act_on_only", ACTn, b[b["on"]]), ("r2own_on_only", R2 + OWN, b[b["on"]])):
        m = lgb.train(PARAMS, lgb.Dataset(sub[feats], sub["y"]), ROUNDS)
        v["p_" + tag] = m.predict(v[feats])
        res[tag] = {"auc": auc(v["y"], v["p_" + tag]), "auc_active": auc(v.loc[v["on"], "y"], v.loc[v["on"], "p_" + tag])}
        if tag.startswith("r2_"):
            res[tag]["side"] = side_metrics(v, "p_" + tag)["acc"]
        if save and tag in ("r2_on_only", "act_on_only", "r2own_on_only"):
            m.save_model(str(HERE / f"presence3_{tag}.txt"))
        print(tag, json.dumps(res[tag]), flush=True)
    (HERE.parent / "results_iter3_deconf.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "save")
