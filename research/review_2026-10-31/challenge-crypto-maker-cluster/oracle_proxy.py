# How often does the Kraken proxy (S0 at window start, mean of last 60 s) disagree with the Chainlink TWAP resolution?
import sys, json; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
out = {}
for dur in ('5m', '15m'):
    P = load(dur); spot, _ = spot_index(P)
    for per in ('fit', 'test'):
        W = [w for w in P[per]['windows'] if w.up_payout is not None]
        st = np.array([w.start_ts for w in W]); en = np.array([w.end_ts for w in W]); y = np.array([w.up_payout for w in W])
        s0 = spot.price_at(st); tw = spot.mean_between(en - 60, en, en + 5)
        pred = (tw >= s0).astype(float); move_bps = np.abs(np.log(tw / s0)) * 1e4
        ok = np.isfinite(pred) & np.isfinite(move_bps)
        mis = (pred != y) & ok
        out[f'{dur}_{per}'] = {'windows': int(ok.sum()), 'kraken_vs_resolution_mismatch_rate': float(mis.sum() / ok.sum()),
                               'mismatch_rate_when_|move|<2bps': float(mis[move_bps < 2].sum() / max(1, (ok & (move_bps < 2)).sum())), 'share_windows_|move|<2bps': float((ok & (move_bps < 2)).mean()),
                               'median_|move|_bps_mismatched': float(np.median(move_bps[mis])) if mis.any() else None}
print(json.dumps(out, indent=1)); json.dump(out, open(D + 'oracle_proxy.json', 'w'), indent=1)
