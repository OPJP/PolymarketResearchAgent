"""Real data, wallet 0xbca08c1b: reproduce the FIT scan over D (incl. negative D = future plays)
and show what the REACT backtest earns on TEST when D <= 0 versus a realistic positive delay."""
import pickle, sys
from pathlib import Path
import numpy as np, pandas as pd
from polyrea.workflows.sports_study import annotate, reaction_stats, _backtest

P = pickle.load(open(Path(__file__).parent / "data" / sys.argv[1], "rb"))
allp, events = P["allp"], P["events"]
def annotated(slugs, delay):
    parts = [annotate(allp[allp.event_slug == s], events[s], delay) for s in slugs if (allp.event_slug == s).any()]
    return pd.concat(parts, ignore_index=True)
scan = []
for D in [-10, -5, 0, 5, 10, 20, 30, 60]:
    a = annotated(P["fit"], D)
    for W in [10, 20, 30, 60, 120]:
        r = reaction_stats(a, W); scan.append({"D": D, "W": W, "excess": r["wallet_share_reactive"] - r["others_share_reactive"]})
sd = pd.DataFrame(scan).sort_values("excess", ascending=False)
print("FIT scan top 6:\n", sd.head(6).to_string(index=False))
best = sd.iloc[0]; W = int(best.W)
print(f"chosen D={int(best.D)} W={W}; best excess among D<0: {sd[sd.D<0].excess.max():.4f}, among D>=0: {sd[sd.D>=0].excess.max():.4f}")
for D in (-10, -5, -2, 0, 2, 5, 10):
    b = _backtest(annotated(P["test"], D), W)
    print(f"TEST backtest REACT(D={D:>3}, W={W}): trades {b['trades']:>6} usd {b['usd_traded']:>12,.0f} pnl {b['pnl']:>10,.0f} return {b['return_on_traded']:+.4f} per-game p {b['per_game_p']:.3f}")
# how many TEST trades at D=-10 are bought BEFORE the play actually happened (wallclock)
a = annotated(P["test"], -10)
sel = a[(a.since >= 0) & (a.since <= W) & (a.fav > 0) & a.payout.notna()]
print(f"D=-10: {(sel.since < 10).mean():.3f} of selected TEST trades are executed before the play's ESPN wall-clock time")
