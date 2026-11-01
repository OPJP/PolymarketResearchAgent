"""X224 live part (mechanics panel iter-15 P2): can public live-book state predict which anchor its new top is clamped
to? BUILD-live adds (iter12/slot_vrel_rows, kind add, 10-31 12-18). Regimes of the new top V_after: pinned at others'
ask - 1c, join (= J, others' best bid), between, below J, at/above ask. Features, public only: spread, J freshness, J size,
J level, distance of J from 0.5; own-state variant adds own top gap, own levels held, top age. Time split: first half
(by t) fit, second half scored. Rule: anchor = ask - 1c if the predicted regime is 'pinned', else J; within one tick of
V_after against J alone and the oracle choice (0.703). Output: results/clamp_regime.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / ".cache/re/tommy-cs2-maker"
RES = ROOT / "research/reverse_engineering/tommy-cs2-maker/results"
r = pd.read_parquet(OUT / "iter12/slot_vrel_rows.parquet")
r = r[(r.kind == "add") & r.V_after.notna() & r.J.notna() & r.spread.notna()].copy().sort_values("t")
r["ask"] = r.J + r.spread / 100
eJ = np.round((r.V_after - r.J) * 100)
eA = np.round((r.V_after - (r.ask - 0.01)) * 100)
r["reg"] = np.select([eA >= 1, eA == 0, eJ == 0, eJ < 0], ["cross", "pinned", "join", "below"], "between")
r["Jdist"] = np.abs(r.J - 0.5)
pub = ["spread", "J_fresh_ms", "J_size", "J", "Jdist"]
own = pub + ["gap_J_own", "n_own", "top_age_ms", "held_m1", "held_m2"]
h = len(r) // 2
tr, te = r.iloc[:h], r.iloc[h:]
out = {"adds": int(len(r)), "regime_shares": r.reg.value_counts(normalize=True).round(3).to_dict()}


def w1(pred, y):
    return round(float((np.abs(np.round((y - pred) * 100)) <= 1).mean()), 3)


for nm, feats in (("public", pub), ("with_own_state", own)):
    X = tr[feats].astype(float).fillna(-1).to_numpy()
    m = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05, random_state=0).fit(X, tr.reg)
    pr = m.predict(te[feats].astype(float).fillna(-1).to_numpy())
    acc = float((pr == te.reg.to_numpy()).mean())
    base = float(te.reg.value_counts(normalize=True).max())
    anchor = np.where(pr == "pinned", te.ask - 0.01, te.J)
    out[nm] = {"regime_accuracy": round(acc, 3), "largest_class_share": round(base, 3),
               "w1_rule": w1(anchor, te.V_after.to_numpy()), "w1_J": w1(te.J.to_numpy(), te.V_after.to_numpy()),
               "w1_oracle_J_or_askm1": w1(np.where(np.abs(te.V_after - te.J) <= np.abs(te.V_after - (te.ask - 0.01)), te.J, te.ask - 0.01), te.V_after.to_numpy())}
(RES / "clamp_regime.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
