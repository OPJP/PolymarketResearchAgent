"""Iteration 9 (X76 I8-3 step 3): per wallet, the age of the filled order (own raw-book add to the match; iteration 6
confirmed orders, 10-31 14:04-16:13, BTC 5m/15m) and whether it was posted before the latest Chainlink publish (proxy:
report S published at S + 1,083 ms), joined to the posture correctness of the fill (it6/fill_side). Development."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
C = Path(__file__).resolve().parents[4] / ".cache/re/directional-maker/it6"
Q = pd.concat([pd.read_parquet(C / "confirmed_1793455600_1793463203.parquet")])
Q = Q[Q.found].drop_duplicates(["wallet", "ms", "add_s"])
F = pd.read_parquet(C / "fill_side_1793455600_1793464202.parquet")
F["ok"] = (F.e_cl > 0).astype(int) == F.up
key = F.groupby(["wallet", "T"]).ok.mean()
Q["ok"] = [key.get((w, int(t)), np.nan) for w, t in zip(Q.wallet, Q.ms)]
Q = Q.dropna(subset=["ok"])
P_last = ((Q.ms - 1083) // 1000) * 1000 + 1083
Q["stale"] = Q.add_s < P_last
out = {"orders": int(len(Q))}
for w, g in Q.groupby("wallet"):
    out[w] = {"n": int(len(g)), "age_ms_median": float(g.age_ms.median()), "age_ms_p75": float(g.age_ms.quantile(0.75)),
              "stale_share": round(float(g.stale.mean()), 3), "acc_stale": round(float(g.ok[g.stale].mean()), 3) if g.stale.any() else None,
              "acc_fresh": round(float(g.ok[~g.stale].mean()), 3) if (~g.stale).any() else None,
              "acc_age_lt_500": round(float(g.ok[g.age_ms < 500].mean()), 3), "acc_age_ge_1000": round(float(g.ok[g.age_ms >= 1000].mean()), 3) if (g.age_ms >= 1000).any() else None}
print(json.dumps(out, indent=1))
(Path(__file__).resolve().parents[1] / "results" / "iter9_wallet_age.json").write_text(json.dumps(out, indent=1))
