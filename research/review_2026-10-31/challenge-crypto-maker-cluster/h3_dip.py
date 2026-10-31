# H3 "tape-dip maker": every R=2 s, bid on side s at floor(ref_s - k) only if the side's public last-trade price
# moved by mom in [lo, hi] over the last `lb` seconds (a dip). ref/mom use trades visible at t0 (ts + 2 <= t0).
# FIT grid -> select by per-window t (>=30 fills) -> TEST once (+ latency/queue sensitivity).
import sys, json, itertools; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
import engine
from engine import *
P = load(sys.argv[1] if len(sys.argv) > 1 else '5m')
def make_quote(k, lb, lo, hi, L=0):
    def qf(w, ticks, tr_ts, tr_px):
        ru = ref_up_at(tr_ts, tr_px, ticks, L); ru_b = ref_up_at(tr_ts, tr_px, ticks - lb, L)
        mom_up = ru - ru_b
        q_up = np.floor((ru - k) * 100 + 1e-9) / 100; q_dn = np.floor(((1 - ru) - k) * 100 + 1e-9) / 100
        for q, m in ((q_up, mom_up), (q_dn, -mom_up)):
            q[(q < 0.01) | (q > 0.99) | ~np.isfinite(ru) | ~np.isfinite(m) | (m < lo) | (m > hi)] = np.nan
        return q_up, q_dn
    return qf
if __name__ == '__main__':
    out = {'fit': {}, 'test': {}}
    engine.TAPE_LAG = 2
    for k, lb, (lo, hi) in itertools.product([0.0, 0.01, 0.03], [10, 30, 60], [(-0.10, -0.03), (-0.20, -0.05), (-0.06, -0.02), (-1.0, -0.03)]):
        r = simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, lb, lo, hi), R=2)
        out['fit'][f'k={k},lb={lb},lo={lo},hi={hi}'] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
    best = max(out['fit'], key=lambda c: (out['fit'][c]['per_window_t'] or -1e9) if (out['fit'][c]['fills'] or 0) >= 30 else -1e9)
    out['selected'] = best
    for c, v in sorted(out['fit'].items(), key=lambda kv: -(kv[1]['per_window_t'] or -1e9))[:8]:
        print('fit', c, {kk: (round(x, 4) if isinstance(x, float) else x) for kk, x in v.items()})
    print('worst fit t', min(v['per_window_t'] for v in out['fit'].values()))
    kv = dict(x.split('=') for x in best.split(','))
    k, lb, lo, hi = float(kv['k']), int(kv['lb']), float(kv['lo']), float(kv['hi'])
    for lag in (2, 0):
        engine.TAPE_LAG = lag
        for qs in (0.0, 0.5, 1.0):
            for L in (0, 1, 3, 5):
                r = simulate(P['test']['windows'], P['test']['M'], make_quote(k, lb, lo, hi, L=L), R=2, queue_share=qs)
                key = f'tape_lag={lag},queue={qs},extra_latency={L}'
                out['test'][key] = {kk: r.get(kk) for kk in ('fills', 'windows', 'usd', 'pnl', 'ret', 'per_window_t', 'p', 'boot_p', 'fill_win_rate')}
                print('TEST', key, {kk: (round(x, 4) if isinstance(x, float) else x) for kk, x in out['test'][key].items()}, flush=True)
    json.dump(out, open(D + 'h3_dip_5m.json', 'w'), indent=1)
