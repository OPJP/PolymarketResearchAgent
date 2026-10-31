# Decision-level match on TEST: does each hypothesis' PIT score rank the wallet's passive buys above other makers' passive buys?
# Score signs are fixed by the hypothesis (not fitted on TEST). Nulls: within-window circular label shift (n=500);
# for spot-based scores also a spot-clock shift of 1-6 h (n=200), as in the repo's match_test.
import sys, json; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
P = load(dur); spot, _ = spot_index(P)
F = pickle.load(open(D + f'feat_{dur}.pkl', 'rb'))
def spot_lead(X, shift=0, L=1, lb=3):
    s = np.where(X.is_up, 1.0, -1.0); t = X.ts.to_numpy() - L + shift
    return s * (np.log(spot.price_at(t)) - np.log(spot.price_at(t - lb))) * 1e4
out = {}
for per in ('fit', 'test'):
    X = F[per]
    scores = {'H1_depth_below_last_trade': X.depth.to_numpy(), 'H2_spot_lead_3s': spot_lead(X), 'H3_dip_30s': -X.mom30.to_numpy(), 'activity_trades_30s': X.n_tr_30.to_numpy()}
    for wname, ycol in (('bosona', 'y_b'), ('almach', 'y_a')):
        y = X[ycol].to_numpy()
        for sn, sc in scores.items():
            if per == 'fit':
                out.setdefault(wname, {}).setdefault(sn, {})['fit_auc'] = auc(sc, y); continue
            r = circular_shift_null(X, y, sc, n_perm=300, seed=1)
            if sn.startswith('H2'):
                rng = np.random.default_rng(2); null = []
                for _ in range(200):
                    sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1]))
                    null.append(auc(spot_lead(X, shift=sh), y))
                null = np.array([v for v in null if np.isfinite(v)])
                r['spot_shift_null_p95'] = float(np.percentile(null, 95)); r['spot_shift_perm_p'] = float((1 + np.sum(null >= r['auc'])) / (1 + len(null)))
            out[wname][sn].update({'test_' + k: v for k, v in r.items()})
            print(wname, sn, {k: round(v, 4) for k, v in out[wname][sn].items()}, flush=True)
json.dump(out, open(D + f'match_{dur}.json', 'w'), indent=1)
