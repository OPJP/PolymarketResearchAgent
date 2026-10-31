# H2-lead: FIT refinement grid -> select by per-window t (>=30 fills) under realistic tape lag 2 s -> evaluate once on TEST.
import sys, json, itertools; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
import engine
from engine import *
import h2_fit
from h2_fit import make_quote, P
grid = list(itertools.product([0.0, 0.01, 0.02], [2, 3, 5], [1.0, 2.0, 3.0, 5.0]))
out = {'fit': {}, 'selected': None, 'test': {}}
engine.TAPE_LAG = 2
for k, X, th in grid:
    r = simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, X, th, 'lead'), R=2, queue_share=0.0)
    out['fit'][f'k={k},X={X},theta={th}'] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
best = max(out['fit'], key=lambda c: (out['fit'][c]['per_window_t'] or -1e9) if (out['fit'][c]['fills'] or 0) >= 30 else -1e9)
out['selected'] = best; print('FIT selected', best, out['fit'][best])
top = sorted(out['fit'].items(), key=lambda kv: -(kv[1]['per_window_t'] or -1e9))[:6]
for c, v in top: print('  fit', c, {kk: (round(x, 4) if isinstance(x, float) else x) for kk, x in v.items()})
kv = dict(x.split('=') for x in best.split(','))
k, X, th = float(kv['k']), int(kv['X']), float(kv['theta'])
for lag in (2, 1, 0):
    engine.TAPE_LAG = lag
    for qs in (0.0, 0.5, 1.0):
        for Ls in (1, 2, 3, 5):
            r = simulate(P['test']['windows'], P['test']['M'], make_quote(k, X, th, 'lead', L=Ls), R=2, queue_share=qs)
            key = f'tape_lag={lag},queue={qs},spot_latency={Ls}'
            out['test'][key] = {kk: r.get(kk) for kk in ('fills', 'windows', 'usd', 'pnl', 'ret', 'per_window_t', 'p', 'boot_p', 'fill_win_rate')}
            print('TEST', key, {kk: (round(x, 4) if isinstance(x, float) else x) for kk, x in out['test'][key].items()}, flush=True)
json.dump(out, open(D + 'h2_lead_test_' + sys.argv[1] + '.json', 'w'), indent=1)
