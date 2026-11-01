"""Iteration 4 (copy of selection3.py; p_mkt read from the same prediction file): print-level selection on all VALIDATE in-window taker prints with the size classes decoded on BUILD
(full orders {30, 50, 60, 100}; partial fills {5, 10, 15, 20, 25}) and the iteration-3 cell score.
score3 = 2*full + 1*partial + p; pre-registered flag = full OR (partial AND p >= 0.30). Co-occurrence baseline: the same
with the market-only cell score. Usage: python selection3.py [val_pred file]"""
import os, sys, json
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from scipy import stats
C = _ROOT + "/.cache/re/btc5m-bot"; R = _ROOT + "/research/reverse_engineering/btc5m-bot"
V0, V1 = 1792108800, 1792713600
W = {"0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "0x3048d65321be3497164cdfc2996f94f98a2e7537", "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
FULL, PART = (30.0, 50.0, 60.0, 100.0), (5.0, 10.0, 15.0, 20.0, 25.0)
FN = sys.argv[1] if len(sys.argv) > 1 else "val_pred_it4.parquet"
key = pd.read_parquet(f"{C}/{FN}", columns=["cid", "is_up", "rel", "p", "p_mkt"]).set_index(["cid", "is_up", "rel"])
win = pd.read_parquet(f"{C}/windows.parquet"); win = win[(win.start_ts >= V0) & (win.start_ts < V1)]
rows = []
for r in win.itertuples():
    p = f"{C}/tapes/{r.cid}.parquet"
    if not os.path.exists(p):
        continue
    d = pd.read_parquet(p, columns=["proxyWallet", "outcome", "timestamp", "size"])
    d = d[(d.timestamp >= r.start_ts) & (d.timestamp < r.start_ts + 300)]
    rows.append(pd.DataFrame({"cid": r.cid, "is_up": (d.outcome == "Up").to_numpy(), "rel": (d.timestamp - r.start_ts).to_numpy(),
                              "size": d["size"].to_numpy(float), "lab": d.proxyWallet.str.lower().isin(W).to_numpy()}))
T = pd.concat(rows, ignore_index=True).join(key, on=["cid", "is_up", "rel"])
sz = np.round(T["size"].to_numpy(), 2); full = np.isin(sz, FULL); part = np.isin(sz, PART); lab = T.lab.to_numpy()


def rl(flag):
    base = lab.mean(); k, n = int(lab[flag].sum()), int(flag.sum())
    return {"recall": round(float(flag[lab].mean()), 4), "lift": round(float(lab[flag].mean() / base), 3), "flag_share": round(float(flag.mean()), 4),
            "p_value": float(stats.binomtest(k, n, base, alternative="greater").pvalue)}


res = {"taker_prints": int(len(T)), "cluster_share": round(float(lab.mean()), 4)}
for nm, pc in (("rule", "p"), ("co_occurrence_baseline", "p_mkt")):
    sc = 2.0 * full + part + T[pc].to_numpy()
    aw, ww = [], []
    for _, g in pd.DataFrame({"cid": T.cid, "lab": lab, "s": sc}).groupby("cid"):
        if 0 < g.lab.sum() < len(g):
            aw.append(roc_auc_score(g.lab, g.s)); ww.append(g.lab.sum())
    res[nm] = {"auc_pooled": round(float(roc_auc_score(lab, sc)), 4), "auc_within_window": round(float(np.average(aw, weights=ww)), 4),
               "at_preregistered_flag": rl(full | (part & (T[pc].to_numpy() >= 0.30)))}
res["size_classes_only"] = {"full_only": rl(full), "full_or_partial": rl(full | part)}
json.dump(res, open(f"{R}/results_selection_iter4_{FN.replace('val_pred_', '').replace('.parquet', '')}.json", "w"), indent=1)
print(json.dumps(res))
