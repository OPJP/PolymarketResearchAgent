import numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.analysis.updown import auc
F = pd.read_pickle("features_taker.pkl")
W = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
cols = ["price", "rel", "px_vs_last", "edge_spot", "n_prior"] + [f"{a}_{k}" for a in ("dside", "fside", "sside", "nprints") for k in (2, 5, 10, 20, 30, 60)]
rows = []
for per in ("fit", "test"):
    P = F[per]
    P = P[(P.rel >= 0) & (P.rel < 300)]  # cluster never trades pre-window; compare within window
    for k, w in W.items():
        y = (P.wallet == w).to_numpy().astype(int)
        r = {"period": per, "wallet": k, "n_wallet": int(y.sum()), "n": len(y)}
        for c in cols:
            r[c] = round(auc(P[c].to_numpy(dtype=float), y), 3)
        rows.append(r)
df = pd.DataFrame(rows).set_index(["period", "wallet"]).T
pd.set_option("display.width", 200)
print(df.to_string())
