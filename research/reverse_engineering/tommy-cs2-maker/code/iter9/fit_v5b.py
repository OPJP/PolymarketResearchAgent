"""Iteration 9: v5b = v4 with a monotone group-P boost, score = logistic(logit(v4) + b * log1p(gp72)), threshold = v4's
(so an event with gp72 = 0 keeps exactly its v4 decision). b fitted by maximum likelihood with logit(v4) as an offset
(no intercept) on BUILD CS2 events (build) and on all development events before H (exam). Compared on VALIDATE with v4
and the two-parameter v5. Output: appends "boost" to code/final_rule_v5_groupP.json; prints VALIDATE metrics."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize_scalar
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "research/reverse_engineering/tommy-cs2-maker/code"))
import final_rule as FR
X = pd.read_parquet(ROOT / ".cache/re/tommy-cs2-maker/events_groupP.parquet"); X["grid"] = X.grid.astype(bool)
def auc(s, y):
    from scipy.stats import rankdata
    s, y = np.asarray(s, float), np.asarray(y).astype(bool); r = rankdata(s); n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
def v4(d, name):
    C = dict(FR.CALL[name])
    if name == "exam":
        C["league_sum"] = {**C["league_sum"], **FR.DOTA["exam"]["league_sum"]}; C["league_n"] = {**C["league_n"], **FR.DOTA["exam"]["league_n"]}
    ev = d.rename(columns={"e_pre_n": "n", "e_pre_v": "v", "e_pre_w": "w"})
    return np.clip(FR.selection_score(ev, C), 1e-6, 1 - 1e-6), C["thr"]
cfg = json.load(open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json"))
cfg["boost"] = {}
for name, d in (("build", X[X.split == "build"]), ("exam", X)):
    s, thr = v4(d, name); off = np.log(s / (1 - s)); g = np.log1p(d.gp72.fillna(0).to_numpy(float)); y = d.y.to_numpy(float)
    nll = lambda b: -np.sum(y * -np.logaddexp(0, -(off + b * g)) + (1 - y) * -np.logaddexp(0, off + b * g))
    b = float(minimize_scalar(nll, bounds=(0, 10), method="bounded").x)
    cfg["boost"][name] = {"b": b, "thr": float(thr)}
json.dump(cfg, open(ROOT / "research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json", "w"), indent=1)
v = X[X.split == "validate"]; s, thr = v4(v, "build"); g = np.log1p(v.gp72.fillna(0).to_numpy(float)); y = v.y.to_numpy()
b = cfg["boost"]["build"]["b"]; sb = 1 / (1 + np.exp(-(np.log(s / (1 - s)) + b * g)))
un = v.unseen.to_numpy()
for nm, sc, t in (("v4", s, thr), ("v5b", sb, thr)):
    sel = sc >= t
    print(nm, "auc", round(auc(sc, y), 4), "unseen", round(auc(sc[un], y[un]), 4), "recall", round(y[sel].sum() / y.sum(), 3), "lift", round(y[sel].mean() / y.mean(), 3),
          "recall_unseen", round(y[sel & un].sum() / max(y[un].sum(), 1), 3), "selected", int(sel.sum()))
print(cfg["boost"])
