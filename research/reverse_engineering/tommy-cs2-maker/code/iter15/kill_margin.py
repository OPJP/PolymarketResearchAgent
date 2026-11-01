"""X211 step 3 (simplified, mechanics P3 / K vs R): does V's winner-signed mid-round move (print-anchored clock rows of
decided_early.py) grow with the round's kill margin (deaths of the loser minus deaths of the winner, bo3)? K: yes, more
than the print's; R (round results only): no dependence beyond the print's. Map-cluster bootstrap of the slopes.
Output: results/kill_margin.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
D = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/iter15/decided_early_rows_print.parquet")
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
ct_won = D.end_reason.isin(["CTWin", "BombDefused", "TargetSaved"])
t_won = D.end_reason.isin(["TerroristsWin", "TargetBombed"])
D = D[(ct_won | t_won) & D.ct_dead.notna() & D.t_dead.notna()].copy()
cw = D.end_reason.isin(["CTWin", "BombDefused", "TargetSaved"])
D["margin"] = np.where(cw, D.t_dead - D.ct_dead, D.ct_dead - D.t_dead)
D["lead_mid"] = D.dV_mid - D.dP_mid
D["early"] = D.dV_mid + D.dV_late
D["P_early"] = D.dP_mid + D.dP_late


def slope(x, y):
    k = np.isfinite(x) & np.isfinite(y)
    if k.sum() < 10 or np.std(x[k]) == 0:
        return np.nan
    return float(np.polyfit(x[k], y[k], 1)[0])


out = {"rounds": int(len(D)), "margin_counts": {str(k): int(v) for k, v in D.margin.value_counts().sort_index().items()}}
for col in ("dV_mid", "dP_mid", "lead_mid", "early", "P_early"):
    out[f"slope_{col}_per_kill_c"] = round(slope(D.margin.to_numpy(float), D[col].to_numpy(float)) * 100, 3)
out["by_margin_bin"] = {}
D["mb"] = pd.cut(D.margin, [-10, 1, 3, 10], labels=["<=1", "2-3", ">=4"])
for b, g in D.groupby("mb", observed=True):
    out["by_margin_bin"][str(b)] = {"n": int(len(g)), "V_mid_c": round(float(g.dV_mid.mean() * 100), 2),
                                    "P_mid_c": round(float(g.dP_mid.mean() * 100), 2),
                                    "V_early_c": round(float(g.early.mean() * 100), 2), "P_early_c": round(float(g.P_early.mean() * 100), 2)}
rng = np.random.default_rng(2)
maps = D.cid.unique()
bs = {c: [] for c in ("dV_mid", "dP_mid", "lead_mid", "early")}
for _ in range(2000):
    pick = rng.choice(maps, len(maps))
    bb = pd.concat([D[D.cid == c] for c in pick])
    for c in bs:
        bs[c].append(slope(bb.margin.to_numpy(float), bb[c].to_numpy(float)))
for c, v in bs.items():
    v = np.array([x for x in v if np.isfinite(x)])
    out[f"slope_{c}_ci95_c"] = [round(float(np.quantile(v, 0.025)) * 100, 3), round(float(np.quantile(v, 0.975)) * 100, 3)]
(RES / "kill_margin.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
