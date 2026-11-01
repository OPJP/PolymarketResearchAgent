"""Iteration 9: constants of frozen rule v5 (= v4 selection score + group-P coverage gp72, X127, adopted under the
pre-registered criterion). build: logistic(logit v4_build, log1p gp72) fitted on BUILD CS2 events; exam: the same
recipe on all development events before H with the v4 exam score. Members fixed on BUILD (selection_groupP.json).
Output: code/final_rule_v5_groupP.json"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
import final_rule as FR
X = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/events_groupP.parquet")
X["grid"] = X.grid.astype(bool)
r = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/results/selection_groupP.json"))
out = {"members": r["members"], "hours": 72, "recipe": "score = logistic(a * logit(v4 score) + b * log1p(gp72) + c); thr = 20th pct of fitted positives"}
for name, d in (("build", X[X.split == "build"]), ("exam", X)):
    C = dict(FR.CALL[name])
    if name == "exam":
        C["league_sum"] = {**C["league_sum"], **FR.DOTA["exam"]["league_sum"]}; C["league_n"] = {**C["league_n"], **FR.DOTA["exam"]["league_n"]}
    ev = d.rename(columns={"e_pre_n": "n", "e_pre_v": "v", "e_pre_w": "w"})
    s = np.clip(FR.selection_score(ev, C), 1e-6, 1 - 1e-6)
    M = np.column_stack([np.log(s / (1 - s)), np.log1p(d.gp72.fillna(0).to_numpy(float))])
    lr = LogisticRegression(max_iter=5000, C=1.0).fit(M, d.y)
    p = lr.predict_proba(M)[:, 1]
    thr = float(np.quantile(p[d.y.to_numpy() == 1], 0.2))
    out[name] = {"coef": [float(c) for c in lr.coef_[0]], "icpt": float(lr.intercept_[0]), "thr": thr, "n_events": int(len(d)), "n_traded": int(d.y.sum())}
json.dump(out, open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json", "w"), indent=1)
print(json.dumps(out, indent=1))
