"""Examiner: the one selection-feature mismatch of exam_trunc.py. Prints stamped in the first seconds of a window:
compare fair_p computed on full spot with fair_p on spot truncated at T-2 (the rule's stated lag) and at T (published
by the print time). python exam_trunc_sel_open.py -> results/exam_trunc_sel_open.json"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "code")); sys.path.insert(0, str(HERE))
from features2 import Spot, fair_up
from exam_panel import EX
w = pd.read_parquet(EX / "windows_5m.parquet").sort_values("start_ts")
spd = pd.read_parquet(EX / "spot_btc_1s.parquet"); sec, px = spd["sec"].to_numpy(), spd["px"].to_numpy()
sp = Spot(sec, px)
rng = np.random.default_rng(1)
out = {}
for rel in range(0, 6):
    ws = w.sample(60, random_state=rel)
    d2 = dT = 0
    for r in ws.itertuples():
        T = int(r.start_ts) + rel
        f0, _ = fair_up(sp, np.array([r.start_ts]), np.array([r.end_ts]), np.array([T - 2]))
        k2, kT = sec < T - 2, sec < T
        f2, _ = fair_up(Spot(sec[k2], px[k2]), np.array([r.start_ts]), np.array([r.end_ts]), np.array([T - 2]))
        fT, _ = fair_up(Spot(sec[kT], px[kT]), np.array([r.start_ts]), np.array([r.end_ts]), np.array([T - 2]))
        d2 += int(f0[0] != f2[0]); dT += int(f0[0] != fT[0])
    out[f"rel_{rel}s"] = {"n": 60, "mismatch_trunc_T_minus_2": d2, "mismatch_trunc_T": dT}
print(out)
(HERE.parent / "results" / "exam_trunc_sel_open.json").write_text(json.dumps(out, indent=1))
