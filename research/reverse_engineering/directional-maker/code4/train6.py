"""Iteration 4, family C5 (operator clock schedule): add UTC hour, weekday and the US-session flag (weekday 12-21 UTC,
the size-schedule boundary found in B1) to R2; BUILD4 fit, VALIDATE4 aggregate. python train6.py [save]"""
from __future__ import annotations
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
import train2 as T  # noqa
from train4 import load  # noqa
CLOCK = ["hour_utc", "dow", "us_session"]


def add_clock(p):
    t = pd.to_datetime(p.start_ts, unit="s")
    p = p.copy()
    p["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32)
    p["dow"] = t.dt.day_of_week.astype(np.int8)
    p["us_session"] = ((p.dow < 5) & (p.hour_utc >= 12) & (p.hour_utc < 21)).astype(np.int8)
    return p


if __name__ == "__main__":
    save = "save" in sys.argv
    b, v = load()
    b, v = add_clock(b), add_clock(v)
    act = v.groupby("cid")["y"].transform("max") > 0
    sets = {"all_path_xwin": T.SETS["all_path_xwin"], "all_path_xwin+clock": T.SETS["all_path_xwin"] + CLOCK,
            "activity+clock": T.SETS["activity"] + CLOCK, "all_path_xwin+session": T.SETS["all_path_xwin"] + ["us_session"],
            "all_path_xwin+clock+own": T.SETS["all_path_xwin"] + CLOCK + T.OWN}
    res = {}
    for nm, feats in sets.items():
        m = lgb.train(T.PARAMS, lgb.Dataset(b[feats], b["y"]), T.ROUNDS)
        v["p_" + nm] = m.predict(v[feats])
        if save:
            m.save_model(str(HERE / f"presence6_{nm}.txt"))
        res[nm] = {"auc": round(T.auc(v.y, v["p_" + nm]), 4), "within_active": round(T.auc(v.y[act], v["p_" + nm][act]), 4),
                   "side": round(T.side_metrics(v, "p_" + nm)["acc"], 4)}
        print(nm, res[nm], flush=True)
    # descriptive: fill-bin rate by session on VALIDATE (aggregate) and BUILD
    for nm, d in (("BUILD4", b), ("VALIDATE4", v)):
        print(nm, "pos rate by us_session", d.groupby("us_session").y.mean().round(4).to_dict())
    (HERE.parent / "results" / "iter4_train6_clock.json").write_text(json.dumps(res, indent=1))
