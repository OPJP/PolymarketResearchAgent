"""Examiner: are the frozen selection models and THETA_SEL a BUILD-only fit? Re-run sel2.main's training part
(BUILD days only, same seed) and compare with selection2_*.txt and final_rule.THETA_SEL.
python exam_refit_sel.py -> results/exam_refit_sel.json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
CODE = HERE.parent / "code"
sys.path.insert(0, str(CODE))
import sel2  # noqa: E402
from features2 import Spot  # noqa: E402
from final_rule import THETA_SEL  # noqa: E402
OUT = sel2.OUT
w = pd.read_parquet(OUT / "windows_5m.parquet")
spd = pd.read_parquet(OUT / "spot_btc_1s.parquet")
sp = Spot(spd["sec"].to_numpy(), spd["px"].to_numpy())
fills = pd.read_parquet(OUT / "cluster_btc5m_fills.parquet")
mk_tx = set(fills.loc[fills["role"] == "maker", "tx"])
cw = set(sel2.WALLETS.values())
days = sorted(int(f.stem.split("_")[-1]) for f in OUT.glob("panel2_day_*.parquet"))
rng = np.random.default_rng(11)
tr = pd.concat([sel2.day_prints(d, w, sp, mk_tx, cw, 0.10, rng)[0] for d in days if d < sel2.VAL0], ignore_index=True)
out = {"build_prints": int(len(tr)), "build_pos": int(tr["y"].sum()), "max_ts": int(tr["ts"].max())}
for nm, fs in (("all", sel2.F_ALL), ("activity", sel2.F_ACT)):
    m = lgb.train(sel2.PARAMS, lgb.Dataset(tr[fs], tr["y"], weight=tr["wt"]), 300)
    s = m.predict(tr[fs])
    o = np.argsort(-s)
    cw_ = np.cumsum(tr["wt"].to_numpy()[o]) / tr["wt"].sum()
    th = float(s[o][np.searchsorted(cw_, 0.15)])
    fz = lgb.Booster(model_file=str(CODE / f"selection2_{nm}.txt"))
    c = fz.predict(tr[fs].iloc[:50000])
    out[nm] = {"theta_refit": th, "theta_frozen": THETA_SEL[nm], "max_abs_pred_diff": float(np.max(np.abs(m.predict(tr[fs].iloc[:50000]) - c)))}
    print(nm, out[nm], flush=True)
(HERE.parent / "results" / "exam_refit_sel.json").write_text(json.dumps(out, indent=1))
