"""Extra PIT features: tape flow excluding the cluster's own fills, and each wallet's own inventory before the print."""
import pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
GAP = 2
CL = {"GF": "0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6", "XM": "0x3048d65321be3497164cdfc2996f94f98a2e7537", "DS": "0xc53375ff94e96100f2b30a4b5775db35218d69a9"}
CLS = set(CL.values())
d = pickle.load(open("data.pkl", "rb"))
F = pd.read_pickle("features_taker.pkl")
for per in ("fit", "test"):
    t = d[per]
    wins = {w.condition_id: w for w in t["windows"]}
    P = F[per]
    extra = []
    for cid, g in P.groupby("condition_id", sort=False):
        w = wins[cid]
        full = t["full_tapes"].get(cid, [])
        taker = t["tapes"].get(cid, [])
        cl_tx = {r["transactionHash"] for r in full if (r.get("proxyWallet") or "").lower() in CLS}
        # other-wallet taker flow, excluding any tx touching the cluster
        rows = [(int(r["timestamp"]), r["asset"] == w.up_token, r["side"], float(r["size"]) * float(r["price"])) for r in taker if r["transactionHash"] not in cl_tx and r["asset"] in (w.up_token, w.down_token)]
        rows.sort()
        fts = np.array([x[0] for x in rows], dtype=np.int64)
        sgn = np.array([(1 if x[1] else -1) * (1 if x[2] == "BUY" else -1) * x[3] for x in rows])
        cum = np.cumsum(sgn) if len(sgn) else np.array([])
        tt = g["ts"].to_numpy() - GAP
        side = np.where(g["is_up"].to_numpy(), 1.0, -1.0)
        out = pd.DataFrame(index=g.index)
        i_now = np.searchsorted(fts, tt, side="right") - 1
        c_now = np.where(i_now >= 0, cum[np.clip(i_now, 0, None)] if len(cum) else 0, 0.0)
        for k in (5, 20, 60):
            j = np.searchsorted(fts, tt - k, side="right") - 1
            c_k = np.where(j >= 0, cum[np.clip(j, 0, None)] if len(cum) else 0, 0.0)
            out[f"fxside_{k}"] = side * (c_now - c_k)
        # own inventory of each cluster wallet (all its BUY fills, maker or taker) before t-GAP
        for name, wal in CL.items():
            fills = sorted((int(r["timestamp"]), 1.0 if r["asset"] == w.up_token else -1.0, float(r["size"])) for r in full if (r.get("proxyWallet") or "").lower() == wal and r["side"] == "BUY" and r["asset"] in (w.up_token, w.down_token))
            if fills:
                ft = np.array([x[0] for x in fills]); net = np.cumsum([x[1] * x[2] for x in fills]); tot = np.cumsum([x[2] for x in fills])
                k = np.searchsorted(ft, tt, side="right") - 1
                inv = np.where(k >= 0, net[np.clip(k, 0, None)], 0.0)
                gross = np.where(k >= 0, tot[np.clip(k, 0, None)], 0.0)
            else:
                inv = np.zeros(len(tt)); gross = np.zeros(len(tt))
            out[f"inv_{name}"] = side * inv          # >0: wallet already long the side being bought
            out[f"invgross_{name}"] = gross
        extra.append(out)
    E = pd.concat(extra).sort_index()
    for c in E.columns:
        P[c] = E[c]
    F[per] = P
    print(per, "done")
pd.to_pickle(F, "features_taker2.pkl")
