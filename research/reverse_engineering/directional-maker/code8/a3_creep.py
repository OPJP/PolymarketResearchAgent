"""Iteration 8 (A3 / X71, public state-machine features for the quote unit): if the cluster's 500 creeps up toward the
touch while the Chainlink posture favours its side, the at-touch state should depend on HOW LONG the posture has favoured
the side, not only on its current sign. Public path features per (window, side, second) from the quote-unit panel of
code8/a4_ceiling.py: run length (s) of e_cl > 0 up to t, of e_cl > 2 c, the mean e_cl over the last 3 / 10 s, and the
seconds since the touch of s last changed. Same live split (fit < 15:00, test >= 15:00), LightGBM as a4_ceiling.
    python code8/a3_creep.py 1793455600 1793464202
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
C = ROOT / ".cache" / "re" / "directional-maker"
SPLIT = 1793458800


def runlen(x):
    out = np.zeros(len(x))
    c = 0
    for i, v in enumerate(x):
        c = c + 1 if v else 0
        out[i] = c
    return out


def main(a, b):
    import lightgbm as lgb
    S = pd.read_parquet(C / "it6" / f"a4_secs_{a}_{b}.parquet").sort_values(["st", "s_up", "rel"])
    parts = []
    for (st, su), g in S.groupby(["st", "s_up"]):
        g = g.copy()
        e = g.e_cl.fillna(0).to_numpy()
        g["run_pos"] = runlen(e > 0)
        g["run_pos2"] = runlen(e > 0.02)
        g["run_neg"] = runlen(e < 0)
        g["e_mean3"] = pd.Series(e).rolling(3, min_periods=1).mean().to_numpy()
        g["e_mean10"] = pd.Series(e).rolling(10, min_periods=1).mean().to_numpy()
        parts.append(g)
    S = pd.concat(parts)
    QA = ["rel", "s_up", "spread", "mid", "tau", "n2", "n10", "last_age", "last_sold_s", "tch_age"]
    CR = ["run_pos", "run_pos2", "run_neg", "e_mean3", "e_mean10"]
    P = dict(objective="binary", num_leaves=7, min_data_in_leaf=40, learning_rate=0.05, lambda_l2=10, max_bin=63, verbose=-1, seed=8)
    tr, te = S[S.st < SPLIT], S[S.st >= SPLIT]
    out = {"seconds": int(len(S)), "test_pos_rate": round(float(te.y.mean()), 4)}
    for nm, cols in (("activity", QA), ("activity+chainlink", QA + ["e_cl"]), ("activity+futures+chainlink", QA + ["e_f", "e_cl"]),
                     ("activity+chainlink+creep_state", QA + ["e_cl"] + CR), ("activity+futures+chainlink+creep_state", QA + ["e_f", "e_cl"] + CR)):
        m = lgb.train(P, lgb.Dataset(tr[cols], tr.y), 300)
        out[nm] = round(float(roc_auc_score(te.y, m.predict(te[cols]))), 4)
    for c in CR:
        out["univariate_" + c] = round(float(roc_auc_score(te.y, te[c])), 4)
    out["rate_by_run_pos_s"] = te.groupby(pd.cut(te.run_pos, [-1, 0, 1, 2, 4, 8, 16, 32, 300]), observed=True).y.mean().round(4).rename(index=str).to_dict()
    (HERE.parent / "results" / f"iter8_a3_creep_{a}_{b}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
