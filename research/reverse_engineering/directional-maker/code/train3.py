"""Iteration 3: presence models with the N3 counterparty-type / size-arrival features (feat3.py) joined to the
iteration-2 clean panels. Same BUILD / VALIDATE split, same LightGBM settings as train2.py.

python code/train3.py [save]
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
from feat3 import NEW  # noqa: E402

R2 = ACT + SPOT + ["edge_s"] + PATH + XWIN
SETS = {
    "activity": ACT,
    "activity+n3": ACT + NEW,
    "r2": R2,
    "r2+n3": R2 + NEW,
    "r2+n3+own": R2 + NEW + OWN,
}


def load():
    fr = []
    for f in sorted(OUT.glob("panel2_day_*.parquet")):
        d = f.stem.split("_")[-1]
        p = pd.read_parquet(f)
        g = pd.read_parquet(OUT / f"feat3_day_{d}.parquet")
        fr.append(p.merge(g, on=["cid", "rel", "side_up"], how="left", validate="one_to_one"))
    p = pd.concat(fr, ignore_index=True)
    p = p[p["start_ts"] + 300 <= H]
    return p[p["start_ts"] < VAL0].reset_index(drop=True), p[p["start_ts"] >= VAL0].reset_index(drop=True)


def main(save: bool):
    b, v = load()
    act_w = v.groupby("cid")["y"].transform("max") > 0
    res = {"n_build": len(b), "n_val": len(v), "models": {}}
    for name, feats in SETS.items():
        m = lgb.train(PARAMS, lgb.Dataset(b[feats], b["y"]), ROUNDS)
        v["p_" + name] = m.predict(v[feats])
        imp = dict(sorted(zip(feats, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:12])
        res["models"][name] = {"auc": auc(v["y"], v["p_" + name]), "auc_active_windows": auc(v.loc[act_w, "y"], v.loc[act_w, "p_" + name]),
                               "imp": imp}
        if name.startswith("r2"):
            res["models"][name]["side"] = side_metrics(v, "p_" + name)
        if save:
            m.save_model(str(HERE / f"presence3_{name}.txt"))
        print(name, round(res["models"][name]["auc"], 4), round(res["models"][name]["auc_active_windows"], 4), flush=True)
    print(json.dumps(res, indent=1, default=str)[:4000])
    (HERE.parent / "results_iter3_presence.json").write_text(json.dumps(res, indent=1, default=str))
    v[["cid", "start_ts", "rel", "side_up", "y"] + [c for c in v.columns if c.startswith("p_")]].to_parquet(OUT / "val_scores3.parquet", index=False)


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "save")
