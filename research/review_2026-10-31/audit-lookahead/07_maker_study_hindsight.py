"""maker_study: (a) the replicator's quoting window per market is the WALLET's own
[first trade, last trade] over the 30-day window (known only in hindsight), and the market
universe is markets where the wallet later made >= 5 trades; (b) FIT/TEST are split by the
wallet's first-trade time, so FIT markets keep trading after TEST markets start.
Rebuilds run_maker_replicability_study's internals with the module's own helpers."""
import json, random, sys, pickle
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
from polyrea.analysis.tape_maker import tape_maker_backtest
from polyrea.workflows.investigate import load_window
from polyrea.workflows.maker_study import _flow_and_passive

wallet = sys.argv[1].lower(); max_markets = int(sys.argv[2]) if len(sys.argv) > 2 else 160
pm = PolymarketData()
win = load_window(wallet, days=30, pm=pm)
t, markets = win["trades"], win["markets"]
agg = t.groupby("condition_id").agg(first=("ts", "min"), last=("ts", "max"), n=("ts", "size"), usd=("usdc", "sum"))
agg = agg[agg["n"] >= 5]
rng = random.Random(5); cids = list(agg.index)
if len(cids) > max_markets: cids = rng.sample(cids, max_markets)
payouts, active = {}, {}
for cid in cids:
    r = resolution_info(markets.get(cid) or {}); tokens = json.loads((markets.get(cid) or {}).get("clobTokenIds") or "[]")
    if r["resolved"] and len(tokens) == 2:
        payouts[cid] = r["payout"].get(str(tokens[0]), 0.0); active[cid] = (int(agg.at[cid, "first"]), int(agg.at[cid, "last"]))
cids = [c for c in cids if c in payouts]
with ThreadPoolExecutor(6) as ex:
    parts = list(ex.map(lambda c: _flow_and_passive(c, markets[c], wallet, active[c][0] - 1800, active[c][1] + 600, pm), cids))
flow = pd.concat([p[0] for p in parts], ignore_index=True)
split = int(np.median([active[c][0] for c in cids]))
fit_c = {c for c in cids if active[c][0] < split}; test_c = {c for c in cids if active[c][0] >= split}
print(f"markets {len(cids)} fit {len(fit_c)} test {len(test_c)} taker prints {len(flow)}")
# (b) temporal overlap
fit_last = np.array([active[c][1] for c in fit_c]); test_first = min(active[c][0] for c in test_c)
fit_flow = flow[flow.condition_id.isin(fit_c)]
print(f"FIT markets whose wallet activity ends after the split: {(fit_last > split).sum()}/{len(fit_c)}; "
      f"FIT taker prints stamped after the first TEST market opened: {(fit_flow.ts >= test_first).mean():.3f} of {len(fit_flow)}")
# (a) quoting window: hindsight (wallet first..last) vs. non-hindsight alternatives
test_flow = flow[flow.condition_id.isin(test_c)]
best = 0.05
dur = np.array([active[c][1] - active[c][0] for c in test_c])
print(f"TEST markets: wallet active-span median {np.median(dur)/60:.1f} min")
for L in (0, 2, 10):
    hind = tape_maker_backtest(test_flow, payouts, best, latency=L, active=active)
    # no hindsight on the stop time: start at the wallet's first trade (as the study does), stop at the market's last observed print
    act2 = {c: (active[c][0], int(test_flow[test_flow.condition_id == c].ts.max()) if (test_flow.condition_id == c).any() else active[c][1]) for c in test_c}
    nohind = tape_maker_backtest(test_flow, payouts, best, latency=L, active=act2)
    print(f"latency {L:>2}s delta {best}: wallet-window quoting pnl {hind['pnl']:>9.1f} ret {hind['return_on_bought']:+.4f} fills {hind['fills']:>5} p {hind['per_market_p']:.4f} | "
          f"until-last-print quoting pnl {nohind['pnl']:>9.1f} ret {nohind['return_on_bought']:+.4f} fills {nohind['fills']:>5} p {nohind['per_market_p']:.4f}")
