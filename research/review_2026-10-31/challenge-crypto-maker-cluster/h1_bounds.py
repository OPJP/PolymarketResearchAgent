# H1 optimistic bounds on FIT: zero tape lag, 1-2 s requote, at-touch queue share up to 1.0
import sys, json, itertools; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
import engine
from h1_fit import make_quote, load
P = load('5m')
res = {}
for lag, k, R, qs in itertools.product([0, 2], [0.01, 0.03, 0.05], [1, 2], [0.0, 0.5, 1.0]):
    engine.TAPE_LAG = lag
    r = engine.simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, 0, 0), R=R, queue_share=qs)
    key = f'tape_lag={lag},k={k},R={R},queue={qs}'
    res[key] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
    print(key, {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in res[key].items()}, flush=True)
json.dump(res, open(engine.D + 'h1_fit_bounds_5m.json', 'w'), indent=1)
