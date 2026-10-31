# H1 on a given duration: FIT grid (tape lag 2, strict) -> select by per-window t (>=30 fills) -> TEST under lag/queue variants.
import sys, json, itertools; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
import engine
from h1_fit import make_quote, load
dur = sys.argv[1]; P = load(dur); out = {'fit': {}, 'test': {}}
engine.TAPE_LAG = 2
for k, R in itertools.product([0.01, 0.03, 0.05, 0.08, 0.12], [2, 5]):
    r = engine.simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, 0, 0), R=R)
    out['fit'][f'k={k},R={R}'] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
best = max(out['fit'], key=lambda c: (out['fit'][c]['per_window_t'] or -1e9) if (out['fit'][c]['fills'] or 0) >= 30 else -1e9)
out['selected'] = best; print(dur, 'FIT best', best, out['fit'][best]); print(' FIT range of ret', min(v['ret'] for v in out['fit'].values()), max(v['ret'] for v in out['fit'].values()))
kv = dict(x.split('=') for x in best.split(',')); k, R = float(kv['k']), int(kv['R'])
for lag, qs in itertools.product([2, 0], [0.0, 1.0]):
    engine.TAPE_LAG = lag
    r = engine.simulate(P['test']['windows'], P['test']['M'], make_quote(k, 0, 0), R=R, queue_share=qs)
    key = f'tape_lag={lag},queue={qs}'; out['test'][key] = {kk: r.get(kk) for kk in ('fills', 'windows', 'usd', 'pnl', 'ret', 'per_window_t', 'p', 'boot_p')}
    print(dur, 'TEST', key, {kk: (round(x, 4) if isinstance(x, float) else x) for kk, x in out['test'][key].items()}, flush=True)
json.dump(out, open(engine.D + f'h1_select_test_{dur}.json', 'w'), indent=1)
