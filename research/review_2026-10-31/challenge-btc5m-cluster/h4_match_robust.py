"""Robustness of the maker-side spot-momentum match: TEST AUC at latencies 1/2/3 s with spot-clock-shift nulls
(100 draws each), AUC within price buckets and within time-in-window buckets, and the same score on the
cluster's TAKER buys (should not show it if the link is specific to quoting)."""
import json, numpy as np, pandas as pd
from common import *
from polyrea.analysis.updown import auc
d, G = load()
spot = G["test"].spot
P = d["test"]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
T = d["test"]["prints"]; T = T[(T.ts - T.start_ts >= 0) & (T.ts - T.start_ts < 300)].reset_index(drop=True)
def sret(P, L, k=2, sh=0):
    t = P.ts.to_numpy() - L + sh; r = np.log(spot.price_at(t) / spot.price_at(t - k)); return np.where(P.is_up.to_numpy(), r, -r)
out = {}
for n, w in W.items():
    y = (P.wallet == w).to_numpy().astype(int); yT = (T.wallet == w).to_numpy().astype(int)
    r = {}
    for L in (1, 2, 3, 5):
        a = auc(sret(P, L), y); rng = np.random.default_rng(L)
        null = np.array([auc(sret(P, L, sh=int(rng.integers(3600, 21600)) * int(rng.choice([-1, 1]))), y) for _ in range(100)])
        null = null[np.isfinite(null)]
        r[f"L{L}"] = {"auc": round(a, 4), "null_mean": round(float(null.mean()), 4), "null_max": round(float(null.max()), 4), "perm_p": round(float((1 + (null >= a).sum()) / (1 + len(null))), 4)}
    s = sret(P, 1)
    pb = pd.cut(P.price, [0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0])
    r["auc_within_price_bucket"] = {str(k): round(auc(s[(pb == k).to_numpy()], y[(pb == k).to_numpy()]), 3) for k in pb.cat.categories}
    rb = pd.cut(P.ts - P.start_ts, [0, 60, 120, 180, 240, 300], right=False)
    r["auc_within_time_bucket"] = {str(k): round(auc(s[(rb == k).to_numpy()], y[(rb == k).to_numpy()]), 3) for k in rb.cat.categories}
    r["same_score_on_wallet_taker_buys_auc"] = round(auc(sret(T, 1), yT), 4)
    out[n] = r; print(n, json.dumps(r), flush=True)
json.dump(out, open("h4_match_robust.json", "w"), indent=1)
