# Descriptive: wallet's own passive-buy PnL on TEST split by the PIT spot-lead score (3 s, L=1), vs other makers.
import sys, json; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
from polyrea.stats.significance import hac_t_test
P = load('5m'); spot, _ = spot_index(P)
out = {}
for per in ('fit', 'test'):
    X = pickle.load(open(D + 'feat_5m.pkl', 'rb'))[per]
    s = np.where(X.is_up, 1.0, -1.0); t = X.ts.to_numpy() - 1
    X['lead'] = s * (np.log(spot.price_at(t)) - np.log(spot.price_at(t - 3))) * 1e4
    X['usd'] = X.price * X.sz; X['pnl'] = X.sz * X.pnl_ps
    X['bk'] = pd.cut(X.lead, [-1e9, -2, -0.5, 0.5, 2, 1e9])
    X['grp'] = np.where(X.y_b == 1, 'bosona', np.where(X.y_a == 1, 'almach', 'others'))
    g = X.groupby(['grp', 'bk'], observed=True).agg(n=('ts', 'size'), usd=('usd', 'sum'), pnl=('pnl', 'sum'))
    g['ret'] = g.pnl / g.usd
    print(per); print(g.round(4).to_string())
    for nm in ('bosona', 'almach'):
        x = X[X.grp == nm]; pw = x.groupby('condition_id').pnl.sum(); tt = hac_t_test(pw.to_numpy())
        out[f'{per}_{nm}'] = {'fills': int(len(x)), 'usd': float(x.usd.sum()), 'pnl': float(x.pnl.sum()), 'ret': float(x.pnl.sum() / x.usd.sum()), 'per_window_p': tt.p_value,
                              'by_lead_bucket': {str(k): {'n': int(v.n), 'ret': float(v.ret)} for k, v in g.loc[nm].iterrows()}}
    o = X[X.grp == 'others']; out[f'{per}_others_ret'] = float(o.pnl.sum() / o.usd.sum())
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'by_lead_bucket'}) for k, v in out.items()}, indent=1))
json.dump(out, open(D + 'wallet_pnl_by_lead_5m.json', 'w'), indent=1)
