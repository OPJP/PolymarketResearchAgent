"""Examiner: presence AUC when every input (tape prints, Binance seconds) reaches the rule 2 s later than it assumes
(exam_panel.py 2). python exam_lag2.py -> results/exam_lag2.json"""
import json, sys
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from exam_metrics import auc
from exam_panel import EX
c = ["cid", "rel", "side_up", "y", "p_all_path_xwin", "p_activity", "p_all_path_xwin+own"]
a = pd.concat([pd.read_parquet(f, columns=c) for f in sorted(EX.glob("panel_day_*.parquet"))])
b = pd.concat([pd.read_parquet(f, columns=c) for f in sorted(EX.glob("panel_lag2_day_*.parquet"))])
j = a.merge(b, on=["cid", "rel", "side_up"], suffixes=("", "_lag2"))
assert (j["y"] == j["y_lag2"]).all()
out = {"bins": int(len(j))}
for m in ("p_all_path_xwin", "p_activity", "p_all_path_xwin+own"):
    out[m] = {"lag0": auc(j["y"], j[m]), "lag2": auc(j["y"], j[m + "_lag2"])}
out["gain_lag2"] = out["p_all_path_xwin"]["lag2"] - out["p_activity"]["lag2"]
print(out)
(HERE.parent / "results" / "exam_lag2.json").write_text(json.dumps(out, indent=1))
