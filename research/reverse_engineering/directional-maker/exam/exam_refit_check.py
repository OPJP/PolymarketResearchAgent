"""Examiner: are the frozen presence models a BUILD-only fit? Refit them with train2.PARAMS / ROUNDS on the BUILD
development panels (start < 2026-10-16) and compare predictions with the frozen model files on a VALIDATE day.
python exam_refit_check.py -> results/exam_refit_check.json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CODE = HERE.parent / "code"
sys.path.insert(0, str(CODE))
from train2 import PARAMS, ROUNDS, SETS, load  # noqa: E402
b, v = load()
v = v[v["start_ts"] < 1792195200]  # one VALIDATE day for the comparison
out = {"lightgbm": lgb.__version__, "n_build": int(len(b)), "build_start_max": int(b["start_ts"].max())}
for nm in ("all_path_xwin", "activity"):
    m = lgb.train(PARAMS, lgb.Dataset(b[SETS[nm]], b["y"]), ROUNDS)
    f = lgb.Booster(model_file=str(CODE / f"presence2_{nm}.txt"))
    a, c = m.predict(v[SETS[nm]]), f.predict(v[SETS[nm]])
    out[nm] = {"max_abs_diff": float(np.max(np.abs(a - c))), "corr": float(np.corrcoef(a, c)[0, 1]), "n_trees_frozen": f.num_trees()}
    print(nm, out[nm], flush=True)
(HERE.parent / "results" / "exam_refit_check.json").write_text(json.dumps(out, indent=1))
