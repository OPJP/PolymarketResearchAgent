"""Examiner round 2: the examiner's own market-activity baselines for BTC 5m presence, fitted with the rule's model class
(LightGBM, train2.PARAMS, 300 rounds: the same tuning budget, i.e. no tuning) on the rule's BUILD data (train4.load: panel2
days 10-09..22 + the lot days 10-23..26, start < 10-27; development data).
  E1 'act_ext': the RE's ACT set + activity-only derived features (distance of the last print from 0.5, total prints and
     volume per horizon, side imbalance of prints and volume, recent-vs-since-open print rate);
  E2 'act_clock': ACT + the operator clock (UTC hour, weekday, US-session flag), a sensitivity variant (the clock is the
     rule's own schedule input, so it is not used as the counted examiner baseline);
  refit of the RE's 'activity' set (must reproduce presence3_activity.txt).
Models go to .cache/exam/directional-maker/models/."""
from __future__ import annotations

import json
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

from r2_common import EXC, RES, WS

sys.path.insert(0, str(WS / "code4"))
import train2 as T  # noqa: E402
from train4 import load  # noqa: E402

MD = EXC / "models"
MD.mkdir(parents=True, exist_ok=True)
CLOCK = ["hour_utc", "dow", "us_session"]


def add_ext(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    p["dist_half"] = (p["last_s"] - 0.5).abs().astype(np.float32)
    for k in (10, 30, 60):
        p[f"hit_tot{k}"] = (p[f"hit_s{k}"] + p[f"hit_o{k}"]).astype(np.float32)
        p[f"vol_tot{k}"] = (p[f"vol_s{k}"] + p[f"vol_o{k}"]).astype(np.float32)
        p[f"hit_imb{k}"] = ((p[f"hit_s{k}"] - p[f"hit_o{k}"]) / (1 + p[f"hit_tot{k}"])).astype(np.float32)
        p[f"vol_imb{k}"] = ((p[f"vol_s{k}"] - p[f"vol_o{k}"]) / (1 + p[f"vol_tot{k}"])).astype(np.float32)
    p["rate_ratio"] = ((p["hit_tot30"] / 30.0) / ((p["n_in"] + 1) / (p["rel"] + 10))).astype(np.float32)
    return p


def add_clock(p: pd.DataFrame) -> pd.DataFrame:
    t = pd.to_datetime(p["start_ts"], unit="s")
    p = p.copy()
    p["hour_utc"] = (t.dt.hour + t.dt.minute / 60).astype(np.float32)
    p["dow"] = t.dt.day_of_week.astype(np.int8)
    p["us_session"] = ((p["dow"] < 5) & (p["hour_utc"] >= 12) & (p["hour_utc"] < 21)).astype(np.int8)
    return p


EXT = [f"{a}{k}" for a in ("hit_tot", "vol_tot", "hit_imb", "vol_imb") for k in (10, 30, 60)] + ["dist_half", "rate_ratio"]
SETS = {"activity_refit": T.SETS["activity"], "act_ext": T.SETS["activity"] + EXT, "act_clock": T.SETS["activity"] + CLOCK}


def main():
    b, _ = load()
    b = add_clock(add_ext(b))
    out = {"build_rows": int(len(b)), "build_pos": int(b["y"].sum()), "build_start_min": int(b.start_ts.min()), "build_start_max": int(b.start_ts.max())}
    for nm, fs in SETS.items():
        m = lgb.train(T.PARAMS, lgb.Dataset(b[fs], b["y"]), T.ROUNDS)
        m.save_model(str(MD / f"exam_{nm}.txt"))
        out[nm] = {"features": fs, "imp": dict(sorted(zip(fs, m.feature_importance("gain").round(0).tolist()), key=lambda x: -x[1])[:8])}
        print(nm, "saved", flush=True)
    (RES / "exam_r2_baseline_fit.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
