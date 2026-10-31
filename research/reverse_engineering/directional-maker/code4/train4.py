"""Iteration 4: refit the presence models on the expanded BUILD (2026-10-09..26 = old BUILD + old VALIDATE + lot first
half) and compare on the new VALIDATE (2026-10-27..30, aggregate metrics only). Same features and LightGBM params as R2.
python train4.py [save]"""
from __future__ import annotations
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
import train2 as T  # noqa  (feature sets, params, side_metrics)
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
V0, V1 = 1793059200, 1793404800
S0 = 1792713600


def load():
    old = [pd.read_parquet(f) for f in sorted(C.glob("panel2_day_*.parquet"))]
    lot = [pd.read_parquet(C / f"exam/panel_day_{d}.parquet") for d in range(S0, V1, 86400)]
    p = pd.concat(old + lot, ignore_index=True)
    p = p[[c for c in p.columns if not c.startswith("p_")]]
    b = p[p.start_ts < V0].reset_index(drop=True)
    v = p[(p.start_ts >= V0) & (p.start_ts < V1)].reset_index(drop=True)
    return b, v


def fit(b, feats, w=None):
    return lgb.train(T.PARAMS, lgb.Dataset(b[feats], b["y"], weight=w), T.ROUNDS)


if __name__ == "__main__":
    save = "save" in sys.argv
    b, v = load()
    print("BUILD rows", len(b), "days", b.start_ts.min(), b.start_ts.max(), "VALIDATE rows", len(v), flush=True)
    res = {}
    act = v.groupby("cid")["y"].transform("max") > 0
    variants = {
        "all": (lambda d: d, None),
        "recent_10_16": (lambda d: d[d.start_ts >= 1792108800], None),
        "lot_study_only": (lambda d: d[d.start_ts >= S0], None),
    }
    for vn, (sel, _) in variants.items():
        bb = sel(b)
        for nm in ("activity", "all_path_xwin", "all_path_xwin+own"):
            m = fit(bb, T.SETS[nm])
            v["p_" + nm] = m.predict(v[T.SETS[nm]])
            if save and vn == "all":
                m.save_model(str(HERE / f"presence4_{nm}.txt"))
        r = {"auc": T.auc(v.y, v.p_all_path_xwin), "baseline": T.auc(v.y, v.p_activity),
             "own": T.auc(v.y, v["p_all_path_xwin+own"]), "within_active": T.auc(v.y[act], v.p_all_path_xwin[act]),
             "side": T.side_metrics(v, "p_all_path_xwin")["acc"], "side_activity": T.side_metrics(v, "p_activity")["acc"],
             "side_own": T.side_metrics(v, "p_all_path_xwin+own")["acc"], "build_rows": len(bb)}
        r["gain"] = r["auc"] - r["baseline"]
        res[vn] = {k: (round(x, 4) if isinstance(x, float) else x) for k, x in r.items()}
        print(vn, res[vn], flush=True)
    (HERE.parent / "results" / "iter4_train4.json").write_text(json.dumps(res, indent=1))
