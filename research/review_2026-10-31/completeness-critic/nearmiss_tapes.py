"""Near-miss wallets (0x50f7 #413, norm1e69 #159, mo-money #242) inside the cached BTC-5m FIT/TEST tapes:
fills by role, price band, time in window, settled return of BUY fills (taker pays 0.07*p*(1-p) fee)."""
import pickle, json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.stats.significance import hac_t_test
OUT = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic"
d = pickle.load(open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/slim.pkl", "rb"))
W = {"0x50f7": "0xee65685de42f8de9a03b4c53ee77d56a20d2cfc9", "norm1e69": "0x41e2e1ccf1e4940029af02259a31c6b89b9fa354", "mo-money": "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"}
res = {}
for n, w in W.items():
    res[n] = {}
    for per in ("fit", "test"):
        wins = [x.condition_id for x in d[per]["windows"]]
        for role, key in (("taker", "prints"), ("maker", "maker_prints")):
            X = d[per][key]; x = X[(X.wallet == w) & X.up_payout.notna()]
            if not len(x):
                res[n][f"{per}_{role}"] = {"fills": 0}; continue
            usd = x["size"] * x.price; pay = np.where(x.is_up, x.up_payout, 1 - x.up_payout)
            fee = x.fee_rate * x.price * (1 - x.price) * x["size"] if role == "taker" else 0
            pnl = x["size"] * pay - usd - fee
            s = pd.Series(0.0, index=wins); g = pd.Series(pnl.to_numpy(), index=x.condition_id.to_numpy()).groupby(level=0).sum(); s.loc[g.index] = g.values
            t = hac_t_test(s.to_numpy())
            res[n][f"{per}_{role}"] = {"fills": int(len(x)), "windows": int(g.size), "usd": round(float(usd.sum()), 1), "pnl": round(float(pnl.sum()), 1),
                                        "ret": round(float(pnl.sum() / usd.sum()), 3), "hac_p": round(float(t.p_value), 4), "win_rate": round(float((pay > 0.5).mean()), 3),
                                        "price_q": [round(float(q), 3) for q in x.price.quantile([0.1, 0.5, 0.9])],
                                        "rel_s_q": [float(q) for q in (x.ts - x.start_ts).quantile([0.1, 0.5, 0.9])]}
    print(n, json.dumps(res[n]), flush=True)
json.dump(res, open(f"{OUT}/nearmiss_tapes.json", "w"), indent=1)
