"""Iteration 9, follow-up of fee9: the hazard steps up ~8x where the fee-aware edge V crosses 0, but 97% of decisions sit at
V <= 0 at sigma = 0.67 bp / sqrt(s). Scan the delta multiplier k (V_k = k * gain - cost; k > 1 = a fair value that reacts more
than the DVOL digital, e.g. a realized-vol delta): per k, recall (share of decision grid points with V_k > 0), precision
P(decision | V_k > 0), P(decision | V_k <= 0), the step ratio P(0 < V_k <= 1) / P(-1 < V_k <= 0), on A and C; then FULL + V_k
(k chosen on A by the step ratio x recall) fit on A, scored on C. Also the match-only label in the negative tail.
Usage: python fee9b.py OUT_JSON"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lab as L
import stale9, fee9
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

C = L.C
KS = (1.0, 1.5, 2.0, 3.0, 5.0, 8.0)


def scan(df, k):
    V = k * df.gain.to_numpy() - df.cost.to_numpy(); y = df.y_dec.to_numpy(); ym = df.y_match.to_numpy()
    pos = V > 0
    s1 = (V > 0) & (V <= 1); s0 = (V > -1) & (V <= 0)
    return {"recall_dec": round(float(pos[y].mean()), 4), "precision": round(float(y[pos].mean()), 4) if pos.any() else None,
            "p_le0": round(float(y[~pos].mean()), 4), "share_pos": round(float(pos.mean()), 4),
            "step_ratio": round(float(y[s1].mean() / max(y[s0].mean(), 1e-9)), 2) if s1.any() and s0.any() else None,
            "auc_V": round(float(roc_auc_score(y, V)), 4), "neg_tail_p_dec_match": [round(float(y[V < -2].mean()), 4), round(float(ym[V < -2].mean()), 4), int((V < -2).sum())]}


def main(out):
    lost = pd.read_parquet(C + "/it9/ins9b_M.parquet"); lost = lost[lost.rcls.isin(["lost_300", "lost_1000"])]
    F = {}
    for nm in ("A", "C"):
        gd, tk, S = stale9.grid(*stale9.IV[nm], lost)
        F[nm] = fee9.frame(gd, S)
    res = {"scan": {nm: {str(k): scan(df, k) for k in KS} for nm, df in F.items()}}
    best = max(KS, key=lambda k: (res["scan"]["A"][str(k)]["step_ratio"] or 0) * res["scan"]["A"][str(k)]["recall_dec"])
    res["chosen_k_on_A"] = best
    A, Cc = F["A"], F["C"]
    for d in (A, Cc):
        d["V"] = best * d.gain - d.cost; d["gain"] = best * d.gain
    xa, xc = np.c_[stale9.X_of(A, "full"), fee9.Xv(A)], np.c_[stale9.X_of(Cc, "full"), fee9.Xv(Cc)]
    fa, fc = stale9.X_of(A, "full"), stale9.X_of(Cc, "full")
    P = {}
    for nm, (u, v) in (("full", (fa, fc)), ("full+Vk", (xa, xc))):
        mu, sd = u.mean(0), u.std(0) + 1e-9
        P[nm] = LogisticRegression(max_iter=3000).fit((u - mu) / sd, A.y_dec).predict_proba((v - mu) / sd)[:, 1]
    y = Cc.y_dec.to_numpy()
    res["C_auc"] = {k: round(float(roc_auc_score(y, v)), 4) for k, v in P.items()}
    res["C_gain_CI"] = stale9.boot_gain(y, P["full+Vk"], P["full"], Cc.st.to_numpy())
    # a two-parameter rule alone: decide iff V_k > 0 -> precision / recall on C vs the matched-volume FULL score
    pos = Cc.V.to_numpy() > 0
    thr = np.quantile(P["full"], 1 - pos.mean()) if pos.any() else 1
    fl = P["full"] >= thr
    res["C_rule_Vk_gt_0"] = {"flagged_share": round(float(pos.mean()), 4), "precision": round(float(y[pos].mean()), 4) if pos.any() else None,
                             "recall": round(float(pos[y].mean()), 4), "FULL_at_same_volume_precision": round(float(y[fl].mean()), 4), "FULL_recall": round(float(fl[y].mean()), 4)}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
