"""Tommy: profile summary stats as coded vs from buys only / net-held positions."""
import json
import numpy as np, pandas as pd
from polyrea.workflows.investigate import load_window
from polyrea.analysis.profile import per_market_decomposition, summarize_profile, timing_features
w = "0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2"
prof = json.load(open(f"research/wallets/{w}/profile.json"))
win = load_window(w, days=30, as_of=prof["subject"]["as_of"])
tr, mk = win["trades"], win["markets"]
pm = per_market_decomposition(tr, mk)
s = summarize_profile(tr, pm, timing_features(tr, mk))
b = tr[tr.side == "BUY"]
pmb = per_market_decomposition(b, mk)  # buys only: correct pair_cost / two_sided of what it BOUGHT
sb = summarize_profile(b, pmb, timing_features(b, mk))
rec = prof["derived"]["profile"]
for k in ("share_two_sided_markets", "median_pair_cost", "median_balance", "residual_win_rate", "market_win_rate", "usd_volume"):
    print(f"{k:24s} recorded {rec[k]:.4f} | as coded {s[k]:.4f} | buys-only {sb[k]:.4f}")
print("buys-only settled_pnl (ignores sell proceeds; NOT a correct pnl):", round(sb["settled_pnl"]))
# per-market pnl sign changes among resolved markets
res = pm[pm.resolved].set_index("condition_id")
def corr(g):
    m = mk.get(g.name) or {}
    return None
sells = tr[tr.side=="SELL"]
cash = tr.assign(sg=np.where(tr.side=="BUY",1,-1))
net = cash.assign(nq=cash["size"]*cash.sg, nc=cash.usdc*cash.sg).groupby(["condition_id","outcome_index"])[["nq","nc"]].sum().unstack(fill_value=0)
from polyrea.analysis.profile import resolution_info
rows=[]
for cid in res.index:
    m=mk[cid]; r=resolution_info(m); t=json.loads(m["clobTokenIds"])
    p0,p1=r["payout"].get(str(t[0]),0),r["payout"].get(str(t[1]),0)
    nq0=net.loc[cid,("nq",0)] if ("nq",0) in net.columns else 0; nq1=net.loc[cid,("nq",1)] if ("nq",1) in net.columns else 0
    nc=net.loc[cid,"nc"].sum()
    rows.append((cid, res.loc[cid,"pnl"], nq0*p0+nq1*p1-nc))
d=pd.DataFrame(rows,columns=["cid","coded","correct"])
print(f"resolved markets {len(d)}; |coded-correct|>$1 in {int((abs(d.coded-d.correct)>1).sum())}; sign flips {int((np.sign(d.coded)!=np.sign(d.correct)).sum())}")
print(f"market_win_rate coded {(d.coded>0).mean():.3f} vs correct {(d.correct>0).mean():.3f}")
print(f"sum coded {d.coded.sum():,.0f} correct {d.correct.sum():,.0f}")
