# H1 "market-anchored deep bid / sweep catcher": every R s rest bids on both sides at floor(ref_s - k) (cents),
# ref = last public trade visible at t0 - L (visible = ts + 2 s). Optional: stop quoting `stop_s` before the end.
# FIT-only grid; strict trade-through fills from exact maker rows (queue_share=0) and a 0.5 at-touch variant.
import sys, json, itertools, time; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
P = load(dur)
def make_quote(k, L, stop_s):
    def qf(w, ticks, tr_ts, tr_px):
        ru = ref_up_at(tr_ts, tr_px, ticks, L)
        q_up = np.floor((ru - k) * 100 + 1e-9) / 100; q_dn = np.floor(((1 - ru) - k) * 100 + 1e-9) / 100
        bad = ~np.isfinite(ru) | (ticks > w.end_ts - stop_s)
        for q in (q_up, q_dn):
            q[(q < 0.01) | (q > 0.99) | bad] = np.nan
        return q_up, q_dn
    return qf
if __name__ == '__main__':
    res = {}
    t = time.time()
    for k, L, R, stop_s in itertools.product([0.01, 0.02, 0.03, 0.05, 0.08, 0.12], [0, 2], [2, 5], [0, 30]):
        r = simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, L, stop_s), R=R, queue_share=0.0)
        res[f'k={k},L={L},R={R},stop={stop_s}'] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
        print(f'k={k},L={L},R={R},stop={stop_s}', {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in res[f'k={k},L={L},R={R},stop={stop_s}'].items()}, round(time.time() - t), flush=True)
    json.dump(res, open(D + f'h1_fit_grid_{dur}.json', 'w'), indent=1)
