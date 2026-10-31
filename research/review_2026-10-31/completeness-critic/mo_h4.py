"""mo-money (rank 242, A1-qualified only after the dormancy fix, never evaluated at A2-C): does its passive BUY flow in
the cached BTC-5m FIT/TEST tapes carry the btc5m-cluster H4 signature (signed 2-s Kraken return toward the bought
side, spot L=1 s old)? Spot-clock-shift null (1-6 h), 200 draws. Descriptive only."""
import sys, json, pickle
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
sys.path.insert(0, "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster")
import numpy as np, pandas as pd
from grid import Grid
from polyrea.analysis.updown import auc
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
d = pickle.load(open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/slim.pkl", "rb"))
MO = "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"
res = {}
for per in ("fit", "test"):
    spot = Grid(d[per]).spot
    P = d[per]["maker_prints"]; P = P[(P.ts - P.start_ts >= 0) & (P.ts - P.start_ts < 300)].reset_index(drop=True)
    y = (P.wallet == MO).to_numpy().astype(int)
    def sret(L, sh=0, k=2):
        t = P.ts.to_numpy() - L + sh; r = np.log(spot.price_at(t) / spot.price_at(t - k)); return np.where(P.is_up.to_numpy(), r, -r)
    r = {"mo_fills": int(y.sum()), "all_fills": int(len(y))}
    rng = np.random.default_rng(42)
    for L in (1, 2, 5):
        a = auc(sret(L), y)
        null = np.array([auc(sret(L, sh=int(rng.integers(3600, 21600)) * int(rng.choice([-1, 1]))), y) for _ in range(200)])
        null = null[np.isfinite(null)]
        r[f"L{L}"] = {"auc": round(float(a), 4), "null_mean": round(float(null.mean()), 4), "null_max": round(float(null.max()), 4), "perm_p": round(float((1 + (null >= a).sum()) / (1 + len(null))), 4)}
    # price / timing profile vs other makers
    r["mo_median_price"] = float(P.price[y == 1].median()); r["others_median_price"] = float(P.price[y == 0].median())
    r["mo_median_rel"] = float((P.ts - P.start_ts)[y == 1].median()); r["others_median_rel"] = float((P.ts - P.start_ts)[y == 0].median())
    res[per] = r; print(per, json.dumps(r), flush=True)
json.dump(res, open(f"{OUT}/mo_h4.json", "w"), indent=1)
