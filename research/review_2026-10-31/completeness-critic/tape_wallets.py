"""Per-wallet settled PnL of BUY fills (taker with fee, maker without fee) in the cached BTC-5m FIT/TEST tapes.
Used to (a) profile mo-money (rank 242, untested after A1) and (b) look for profitable BTC-5m wallets outside the
screened top 500 (universe coverage). Settlement uses up_payout only (no decision use)."""
import pickle, json, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/PolymarketResearchAgent")
from polyrea.stats.significance import hac_t_test
SL = "/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-btc5m-cluster/slim.pkl"
d = pickle.load(open(SL, "rb"))
lb = json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/leaderboard_snapshot.json"))["rows"]
rank = {r["user_id"].lower(): r["rank"] for r in lb}
a1 = json.load(open("/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json"))
MO = "0x32ed2e546b187ca15e2841edc82b22c713cf8ec3"
def pnl(P, taker):
    P = P[P.up_payout.notna()]
    usd = P["size"] * P.price
    pay = np.where(P.is_up, P.up_payout, 1 - P.up_payout)
    fee = P.fee_rate * P.price * (1 - P.price) * P["size"] if taker else 0.0
    return P.assign(usd=usd, pnl=P["size"] * pay - usd - fee)
out = {}
rows = []
for per in ("fit", "test"):
    T = pnl(d[per]["prints"], True); M = pnl(d[per]["maker_prints"], False)
    for role, X in (("taker", T), ("maker", M)):
        g = X.groupby("wallet").agg(n=("pnl", "size"), usd=("usd", "sum"), pnl=("pnl", "sum"))
        g["per"] = per; g["role"] = role
        rows.append(g.reset_index())
    for role, X in (("taker", T), ("maker", M)):
        x = X[X.wallet == MO]
        if len(x):
            pw = x.groupby("condition_id").pnl.sum()
            allw = pd.Series(0.0, index=[w.condition_id for w in d[per]["windows"]]); allw.loc[pw.index] = pw.values
            t = hac_t_test(allw.to_numpy())
            out[f"mo_{per}_{role}"] = {"fills": int(len(x)), "windows": int(pw.size), "usd": round(float(x.usd.sum()), 1), "pnl": round(float(x.pnl.sum()), 1),
                                         "ret": round(float(x.pnl.sum() / x.usd.sum()), 4), "hac_p": round(float(t.p_value), 4),
                                         "median_price": round(float(x.price.median()), 3), "median_rel_s": float((x.ts - x.start_ts).median())}
        else:
            out[f"mo_{per}_{role}"] = {"fills": 0}
R = pd.concat(rows)
tot = R.groupby(["wallet", "per"]).agg(usd=("usd", "sum"), pnl=("pnl", "sum")).unstack("per").fillna(0)
tot.columns = [f"{a}_{b}" for a, b in tot.columns]
tot["pnl_both"] = tot.pnl_fit + tot.pnl_test
# 12 x 2h blocks = 24 h sampled per 7-day period -> both periods = 2 sampled days; monthly ~ 15 x pnl_both
tot["monthly_est"] = 15 * tot.pnl_both
tot = tot.sort_values("pnl_both", ascending=False)
top = tot.head(25).copy()
top["lb_rank"] = [rank.get(w, None) for w in top.index]
print(top.round(0).to_string())
out["top25_wallets_by_sampled_pnl"] = [{"wallet": w, **{k: (None if (isinstance(v, float) and np.isnan(v)) else (round(float(v), 1) if v is not None else None)) for k, v in r.items()}} for w, r in top.iterrows()]
out["n_wallets_monthly_est_over_50k"] = int((tot.monthly_est > 50000).sum())
out["n_over_50k_not_in_top500"] = int(((tot.monthly_est > 50000) & ~tot.index.isin(list(rank))).sum())
out["mo_money_rank"] = rank.get(MO)
print(json.dumps({k: v for k, v in out.items() if k.startswith("mo_") or k.startswith("n_")}, indent=1))
json.dump(out, open("/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/completeness-critic/tape_wallets.json", "w"), indent=1, default=float)
