"""Per passive-BUY features (PIT). Run for both periods; saves feature tables."""
import sys; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
P = load(dur); spot, _ = spot_index(P)
L = 1
res = {}
for per in ('fit', 'test'):
    M = P[per]['M']
    TR = trade_stream(M).sort_values(['condition_id', 'ts'], kind='stable')
    MB = M[M.side == 'BUY'].copy().reset_index(drop=True)
    MB['ref_up'] = np.nan; MB['ref_up_30'] = np.nan; MB['ref_up_10'] = np.nan; MB['n_tr_30'] = np.nan
    trg = dict(tuple(TR.groupby('condition_id')))
    for cid, idx in MB.groupby('condition_id').groups.items():
        tr = trg[cid]; ts, px = tr.ts.to_numpy(), tr.up_px.to_numpy()
        t = MB.loc[idx, 'ts'].to_numpy()
        MB.loc[idx, 'ref_up'] = ref_up_at(ts, px, t, L)
        MB.loc[idx, 'ref_up_10'] = ref_up_at(ts, px, t - 10, L)
        MB.loc[idx, 'ref_up_30'] = ref_up_at(ts, px, t - 30, L)
        vis = ts + TAPE_LAG
        MB.loc[idx, 'n_tr_30'] = np.searchsorted(vis, t - L, side='right') - np.searchsorted(vis, t - L - 30, side='right')
    s = np.where(MB.is_up, 1.0, -1.0)
    MB['ref_s'] = np.where(MB.is_up, MB.ref_up, 1 - MB.ref_up)
    MB['depth'] = MB.ref_s - MB.price                      # how far below the last visible trade the fill price is
    MB['mom10'] = s * (MB.ref_up - MB.ref_up_10)           # recent tape move of the bought side
    MB['mom30'] = s * (MB.ref_up - MB.ref_up_30)
    fu = fair_up_vectorized(spot, MB.start_ts.to_numpy(), MB.end_ts.to_numpy(), MB.ts.to_numpy() - L, 60)
    MB['model_up'] = fu
    MB['model_s'] = np.where(MB.is_up, fu, 1 - fu)
    MB['model_edge'] = MB.model_s - MB.price
    MB['model_vs_ref'] = MB.model_s - MB.ref_s
    sp_now = spot.price_at(MB.ts.to_numpy() - L); sp_30 = spot.price_at(MB.ts.to_numpy() - L - 30)
    MB['spot_mom30_bps'] = s * (np.log(sp_now) - np.log(sp_30)) * 1e4
    MB['y_b'] = (MB.wallet == BOS).astype(int); MB['y_a'] = (MB.wallet == ALM).astype(int)
    MB['pnl_ps'] = MB.payout - MB.price
    res[per] = MB
    print(per, len(MB), 'ref NaN share', float(MB.ref_up.isna().mean()))
pickle.dump(res, open(D + f'feat_{dur}.pkl', 'wb'))
