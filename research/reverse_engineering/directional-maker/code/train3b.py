"""Iteration 3: presence with Binance order-flow features (flow3.py), compared with R2 in the same run."""
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
from flow3 import FLOW, Flow  # noqa: E402

R2 = ACT + SPOT + ["edge_s"] + PATH + XWIN


def load():
    fr = [pd.read_parquet(f) for f in sorted(OUT.glob("panel2_day_*.parquet"))]
    p = pd.concat(fr, ignore_index=True)
    p = p[p["start_ts"] + 300 <= H].reset_index(drop=True)
    fl = Flow(pd.read_parquet(OUT / "spotflow_1s.parquet"))
    sign = np.where(p["side_up"].to_numpy() == 1, 1.0, -1.0)
    f = fl.features(p["start_ts"].to_numpy() + p["rel"].to_numpy(), p["start_ts"].to_numpy(), sign)
    p = pd.concat([p, f], axis=1)
    return p[p["start_ts"] < VAL0].reset_index(drop=True), p[p["start_ts"] >= VAL0].reset_index(drop=True)


SETS = {"spot": ["rel", "side_up"] + SPOT, "spot+flow": ["rel", "side_up"] + SPOT + FLOW, "r2": R2, "r2+flow": R2 + FLOW,
        "r2+flow+own": R2 + FLOW + OWN}


def main(save: bool):
    b, v = load()
    act_w = v.groupby("cid")["y"].transform("max") > 0
    res = {"models": {}}
    for name, feats in SETS.items():
        m = lgb.train(PARAMS, lgb.Dataset(b[feats], b["y"]), ROUNDS)
        v["p_" + name] = m.predict(v[feats])
        res["models"][name] = {"auc": auc(v["y"], v["p_" + name]), "auc_active": auc(v.loc[act_w, "y"], v.loc[act_w, "p_" + name]),
                               "imp": dict(sorted(zip(feats, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:12])}
        if name.startswith("r2"):
            res["models"][name]["side"] = side_metrics(v, "p_" + name)
        if save:
            m.save_model(str(HERE / f"presence3_{name}.txt"))
        print(name, round(res["models"][name]["auc"], 4), round(res["models"][name]["auc_active"], 4),
              res["models"][name].get("side", {}).get("acc"), flush=True)
    # univariate: does the cluster's side follow Binance order flow? (one-sided fill bins)
    key = ["cid", "rel"]
    up = v[v["side_up"] == 1].set_index(key)
    dn = v[v["side_up"] == 0].set_index(key)
    lab = (up["y"] > 0).astype(int) - (dn["y"] > 0).astype(int)
    one = lab[lab != 0].index
    tu = (lab.loc[one] > 0).to_numpy()
    for c in ("ofi1", "ofi3", "ofi5", "ofi10", "ofi30", "ofi_win"):
        x = up.loc[one, c].to_numpy()
        nz = x != 0
        res.setdefault("side_by_flow_sign", {})[c] = {"acc": float(np.mean((x[nz] > 0) == tu[nz])), "n": int(nz.sum())}
    print(json.dumps(res["side_by_flow_sign"]), json.dumps({k: v_["imp"] for k, v_ in res["models"].items() if k == "r2+flow"})[:800])
    (HERE.parent / "results_iter3_flow.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(len(sys.argv) > 1 and sys.argv[1] == "save")
