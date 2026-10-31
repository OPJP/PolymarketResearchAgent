"""What the bca08c1b study reports if the FIT grid is restricted to D >= floor (same code path as run_sports_study)."""
import pickle, sys
import numpy as np, pandas as pd
from polyrea.workflows.sports_study import annotate, reaction_stats, _backtest
from polyrea.stats.significance import permutation_pvalue
d = pickle.load(open(sys.argv[1], "rb")); allp, events, fit, test = d["allp"], d["events"], d["fit"], d["test"]
def annotated(slugs, delay, shifts=None):
    return pd.concat([annotate(allp[allp["event_slug"] == s], events[s], delay, (shifts or {}).get(s, 0)) for s in slugs if (allp["event_slug"] == s).any()], ignore_index=True)
fa = {D: annotated(fit, D) for D in [-10, -5, 0, 5, 10, 20, 30, 60]}
for floor in (-10, 0, 5):
    scan = [(D, W, reaction_stats(fa[D], W)) for D in fa if D >= floor for W in (10, 20, 30, 60, 120)]
    D, W, _ = max(scan, key=lambda x: x[2]["wallet_share_reactive"] - x[2]["others_share_reactive"])
    ta = annotated(test, D); obs = reaction_stats(ta, W)
    rng = np.random.default_rng(11); na = []
    for _ in range(200):
        sh = {s: int(rng.integers(300, 1500)) * int(rng.choice([-1, 1])) for s in test}
        na.append(reaction_stats(annotated(test, D, sh), W)["wallet_direction_agree"])
    bt = _backtest(ta, W)
    print(f"floor D>={floor:>3}: chosen D={D} W={W} | TEST direction agree {obs['wallet_direction_agree']:.3f} (others {obs['others_direction_agree']:.3f}) perm p {permutation_pvalue(obs['wallet_direction_agree'], np.array(na)):.4f} | backtest trades {bt['trades']} usd {bt['usd_traded']:,.0f} return {bt['return_on_traded']:+.4f} per-game p {bt['per_game_p']:.3f}")
