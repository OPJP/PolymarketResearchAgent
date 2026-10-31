# H2 "market-anchored maker with spot-move protection": every R s rest a bid on side s at floor(ref_s - k)
# only if the signed Kraken move toward s over the last X s (spot available at t0 - L) is >= gate.
#   mode 'protect': gate = -theta (pull the bid when spot moved against s by more than theta bps)
#   mode 'lead'   : gate = +theta (bid only on the side spot just moved toward; market-lag directional maker)
# FIT-only grid (strict trade-through fills, exact maker rows).
import sys, json, itertools, time; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
import engine
from engine import *
P = load(sys.argv[1] if len(sys.argv) > 1 else '5m'); spot, _ = spot_index(P)
def make_quote(k, X, theta, mode, L=1, Lt=0):
    def qf(w, ticks, tr_ts, tr_px):
        ru = ref_up_at(tr_ts, tr_px, ticks, Lt)
        mv = (np.log(spot.price_at(ticks - L)) - np.log(spot.price_at(ticks - L - X))) * 1e4  # toward Up, bps
        q_up = np.floor((ru - k) * 100 + 1e-9) / 100; q_dn = np.floor(((1 - ru) - k) * 100 + 1e-9) / 100
        gate = -theta if mode == 'protect' else theta
        ok_up = mv >= gate; ok_dn = -mv >= gate
        for q, okk in ((q_up, ok_up), (q_dn, ok_dn)):
            q[(q < 0.01) | (q > 0.99) | ~np.isfinite(ru) | ~np.isfinite(mv) | ~okk] = np.nan
        return q_up, q_dn
    return qf
if __name__ == '__main__':
    res = {}
    for lag in (2, 0):
        engine.TAPE_LAG = lag
        for k, X, theta, mode in itertools.product([0.01, 0.03], [3, 10], [0.5, 2.0], ['protect', 'lead']):
            r = simulate(P['fit']['windows'], P['fit']['M'], make_quote(k, X, theta, mode), R=2, queue_share=0.0)
            key = f'tape_lag={lag},k={k},X={X},theta={theta},mode={mode}'
            res[key] = {kk: r.get(kk) for kk in ('fills', 'usd', 'pnl', 'ret', 'per_window_t', 'p')}
            print(key, {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in res[key].items()}, flush=True)
    json.dump(res, open(D + 'h2_fit_grid_5m.json', 'w'), indent=1)
