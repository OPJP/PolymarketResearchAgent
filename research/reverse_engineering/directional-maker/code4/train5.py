"""Iteration 4, family A3: add Binance USD-M futures features (1-s, point-in-time: second k used from k+1) to the R2
panel; fit on BUILD4 (2026-10-09..26), compare on VALIDATE4 (2026-10-27..30, aggregate only).
python train5.py [save]"""
from __future__ import annotations
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code"))
sys.path.insert(0, str(HERE))
import train2 as T  # noqa
from features2 import Spot, fair_up  # noqa
from train4 import load  # noqa
ROOT = HERE.parents[3]
C = ROOT / ".cache/re/directional-maker"
FUT = ["fair_fut_s", "z_fut_s", "edge_fut_s", "rf1", "rf2", "rf3", "rf5", "rf10", "lead1", "lead2", "lead3", "lead5",
       "basis_dev", "fimb1", "fimb3", "fimb5"]


def fut_spot(days):
    g = pd.concat([pd.read_parquet(C / "fut1s" / f"{d}.parquet") for d in days], ignore_index=True).sort_values("sec")
    return g


def add_fut(p: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    spf = Spot(g.sec.to_numpy(), g.px.to_numpy())
    t0 = int(g.sec.iloc[0]); n = int(g.sec.iloc[-1]) - t0 + 1
    vol = np.zeros(n); buy = np.zeros(n)
    vol[g.sec.to_numpy() - t0] = g.vol.to_numpy(); buy[g.sec.to_numpy() - t0] = g.buy.to_numpy()
    cv = np.concatenate([[0.0], np.cumsum(vol)]); cb = np.concatenate([[0.0], np.cumsum(buy)])
    t = (p.start_ts + p.rel).to_numpy().astype(np.int64)
    st, en = p.start_ts.to_numpy().astype(np.int64), (p.start_ts + 300).to_numpy().astype(np.int64)
    sg = np.where(p.side_up.to_numpy() == 1, 1.0, -1.0)
    fu, z = fair_up(spf, st, en, t)
    p = p.copy()
    p["fair_fut_s"] = np.where(sg > 0, fu, 1 - fu).astype(np.float32)
    p["z_fut_s"] = (z * sg).astype(np.float32)
    p["edge_fut_s"] = p.fair_fut_s - p.last_s
    stf = spf.last(t)
    for k in (1, 2, 3, 5, 10):
        p[f"rf{k}"] = (np.log(stf / spf.last(t - k)) * 1e4 * sg).astype(np.float32)
    for k in (1, 2, 3, 5):
        p[f"lead{k}"] = p[f"rf{k}"] - p[f"r{k}"]
    # futures fair minus spot fair (signed by construction through the side's fair)
    p["basis_dev"] = (p.fair_fut_s - p.fair_s).astype(np.float32)
    for k in (1, 3, 5):  # seconds [t-k, t-1] published by t
        ib = np.clip(t - t0, 0, n); ia = np.clip(t - k - t0, 0, n)
        v = cv[ib] - cv[ia]; b = cb[ib] - cb[ia]
        p[f"fimb{k}"] = (np.where(v > 0, (2 * b - v) / np.maximum(v, 1e-9), 0) * sg).astype(np.float32)
    return p


if __name__ == "__main__":
    save = "save" in sys.argv
    b, v = load()
    days = pd.date_range("2026-10-08", "2026-10-30").strftime("%Y-%m-%d")
    g = fut_spot(days)
    b = add_fut(b, g); v = add_fut(v, g)
    print("rows", len(b), len(v), "fut nan share", float(v.fair_fut_s.isna().mean()), flush=True)
    sets = {"activity": T.SETS["activity"], "all_path_xwin": T.SETS["all_path_xwin"],
            "all_path_xwin+fut": T.SETS["all_path_xwin"] + FUT, "time+fut": T.SETS["time"] + FUT,
            "all_path_xwin+fut+own": T.SETS["all_path_xwin"] + FUT + T.OWN}
    act = v.groupby("cid")["y"].transform("max") > 0
    res = {}
    imp = {}
    for nm, feats in sets.items():
        m = lgb.train(T.PARAMS, lgb.Dataset(b[feats], b["y"]), T.ROUNDS)
        v["p_" + nm] = m.predict(v[feats])
        if save:
            m.save_model(str(HERE / f"presence5_{nm}.txt"))
        if nm == "all_path_xwin+fut":
            gi = m.feature_importance("gain"); imp = dict(sorted(zip(feats, (gi / gi.sum()).round(4).tolist()), key=lambda x: -x[1])[:15])
        res[nm] = {"auc": round(T.auc(v.y, v["p_" + nm]), 4), "within_active": round(T.auc(v.y[act], v["p_" + nm][act]), 4),
                   "side": round(T.side_metrics(v, "p_" + nm)["acc"], 4)}
        print(nm, res[nm], flush=True)
    res["importance_all+fut"] = imp
    print(imp)
    (HERE.parent / "results" / "iter4_train5_fut.json").write_text(json.dumps(res, indent=1))
