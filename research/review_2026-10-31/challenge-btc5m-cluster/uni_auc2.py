import numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import auc
F = pd.read_pickle("features_taker2.pkl")
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
rows = []
for per in ("fit", "test"):
    P = F[per]
    P = P[(P.rel >= 0) & (P.rel < 300)]
    for k, w in W.items():
        y = (P.wallet == w).to_numpy().astype(int)
        r = {"period": per, "wallet": k}
        for c in ["fside_20", "fxside_5", "fxside_20", "fxside_60", "dside_60", f"inv_{k}", f"invgross_{k}"]:
            r[c.replace(k, "own")] = round(auc(P[c].to_numpy(dtype=float), y), 3)
        # inventory relative: wallet's inventory as share of its gross
        rel_inv = P[f"inv_{k}"] / P[f"invgross_{k}"].replace(0, np.nan)
        r["inv_rel_own"] = round(auc(rel_inv.fillna(0).to_numpy(), y), 3)
        rows.append(r)
print(pd.DataFrame(rows).set_index(["period", "wallet"]).T.to_string())
