"""Iteration 2: print-level selection on VALIDATE. Among all in-window taker prints (every trader), score each print by
(a) the frozen cell score p_y of its (window, outcome, second) and (b) a frozen size rule: the print's size equals one
of the bot's fixed order sizes {30, 50, 60} shares (decoded from BUILD order reconstruction in iteration 1).
Score = 1[size rule] + p_y (lexicographic). Reports pooled and within-window AUC, recall/lift at score >= 1.30."""
import os, sys, glob, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from scipy import stats
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
CL = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
SIZES = (30.0, 50.0, 60.0)
v = pd.read_parquet(f"{C}/val_pred_presence.parquet", columns=["cid", "start_ts", "is_up", "rel", "p_y"])
key = v.set_index(["cid", "is_up", "rel"]).p_y
rows = []
for cid, st in v.groupby("cid").start_ts.first().items():
    d = pd.read_parquet(f"{C}/tapes/{cid}.parquet")
    if len(d) == 0 or "timestamp" not in d:
        continue
    d = d[(d.timestamp >= st) & (d.timestamp < st + 300)]
    rows.append(pd.DataFrame({"cid": cid, "is_up": (d.outcome == "Up").to_numpy(), "rel": (d.timestamp - st).to_numpy(), "size": d["size"].astype(float).to_numpy(),
                              "lab": d.proxyWallet.str.lower().isin(CL).to_numpy()}))
P = pd.concat(rows, ignore_index=True)
P["p"] = key.reindex(pd.MultiIndex.from_arrays([P.cid, P.is_up, P.rel])).to_numpy()
P["size_rule"] = np.isin(np.round(P["size"], 2), SIZES)
P["score"] = P.size_rule.astype(float) + P.p
res = {"prints": int(len(P)), "cluster_share": round(float(P.lab.mean()), 4),
       "cluster_prints_with_size_rule": round(float(P.size_rule[P.lab].mean()), 4), "other_prints_with_size_rule": round(float(P.size_rule[~P.lab].mean()), 4)}
for nm in ("p", "score"):
    res[f"auc_pooled_{nm}"] = round(float(roc_auc_score(P.lab, P[nm])), 4)
    aw = []; ww = []
    for cid, g in P.groupby("cid"):
        if 0 < g.lab.sum() < len(g):
            aw.append(roc_auc_score(g.lab, g[nm])); ww.append(g.lab.sum())
    res[f"auc_within_window_{nm}"] = round(float(np.average(aw, weights=ww)), 4)
flag = P.score >= 1.30
base = P.lab.mean(); k, n = int(P.lab[flag].sum()), int(flag.sum())
res["at_score_1.30"] = {"recall": round(float(flag[P.lab].mean()), 4), "lift": round(float(P.lab[flag].mean() / base), 3), "flag_share": round(float(flag.mean()), 4),
                        "p_value": float(stats.binomtest(k, n, base, alternative="greater").pvalue)}
flag2 = P.size_rule
res["size_rule_only"] = {"recall": round(float(flag2[P.lab].mean()), 4), "lift": round(float(P.lab[flag2].mean() / base), 3), "flag_share": round(float(flag2.mean()), 4)}
print(json.dumps(res, indent=1))
json.dump(res, open(f"{R}/results_selection_print_iter2.json", "w"), indent=1)
