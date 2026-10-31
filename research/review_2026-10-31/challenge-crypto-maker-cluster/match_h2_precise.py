# Focused, higher-precision match test for the H2 spot-lead score (primary spec lb=3 s, spot latency L=1 s, chosen on FIT backtest),
# robustness over (lb, L), decision metrics at the FIT-chosen gate theta=2 bps, on 5m and (separately) 15m windows.
import sys, json; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
from scipy import stats
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
NPERM = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
P = load(dur); spot, _ = spot_index(P)
F = pickle.load(open(D + f'feat_{dur}.pkl', 'rb'))
def lead(X, lb=3, L=1, shift=0):
    s = np.where(X.is_up, 1.0, -1.0); t = X.ts.to_numpy() - L + shift
    return s * (np.log(spot.price_at(t)) - np.log(spot.price_at(t - lb))) * 1e4
def fast_circ(X, y, sc, nperm, seed):
    order = np.lexsort((X.ts.to_numpy(), X.condition_id.to_numpy()))
    cid = X.condition_id.to_numpy()[order]; ys = y[order]; s = sc[order]
    ok = np.isfinite(s)
    r = np.full(len(s), np.nan); r[ok] = stats.rankdata(s[ok])
    n1 = int(ys[ok].sum()); n0 = int(ok.sum()) - n1
    bounds = np.r_[0, np.nonzero(cid[1:] != cid[:-1])[0] + 1, len(cid)]
    pos = np.nonzero(ys == 1)[0]; win = np.searchsorted(bounds, pos, side='right') - 1
    a = bounds[win]; n = bounds[win + 1] - a
    def auc_of(pidx):
        rr = r[pidx]; m = np.isfinite(rr); k1 = m.sum(); k0 = int(ok.sum()) - k1
        return float((rr[m].sum() - k1 * (k1 + 1) / 2) / (k1 * k0))
    obs = auc_of(pos)
    rng = np.random.default_rng(seed); uw = np.unique(win); null = np.empty(nperm)
    for i in range(nperm):
        off = dict(zip(uw, rng.integers(0, 1 << 30, len(uw))))
        o = np.array([off[x] for x in win])
        null[i] = auc_of(a + (pos - a + o) % n)
    return obs, null
out = {}
for wname, ycol in (('bosona', 'y_b'), ('almach', 'y_a')):
    out[wname] = {}
    for per in ('fit', 'test'):
        X = F[per]; y = X[ycol].to_numpy()
        if y.sum() == 0: continue
        sc = lead(X)
        obs, null = fast_circ(X, y, sc, NPERM, 11)
        rng = np.random.default_rng(5); sn = []
        for _ in range(min(NPERM, 1000)):
            sh = int(rng.integers(3600, 6 * 3600)) * int(rng.choice([-1, 1])); sn.append(auc(lead(X, shift=sh), y))
        sn = np.array([v for v in sn if np.isfinite(v)])
        th = 2.0; pred = sc >= th; okk = np.isfinite(sc)
        prec = float(y[pred & okk].mean()); base = float(y[okk].mean())
        wsc = sc[(y == 1) & okk]; osc = sc[(y == 0) & okk]
        out[wname][per] = {'wallet_fills': int(y.sum()), 'passive_buys': int(len(y)), 'auc': obs,
                           'circ_null_mean': float(null.mean()), 'circ_null_p99': float(np.percentile(null, 99)), 'circ_perm_p': float((1 + (null >= obs).sum()) / (1 + len(null))),
                           'spot_shift_null_mean': float(sn.mean()), 'spot_shift_null_p99': float(np.percentile(sn, 99)), 'spot_shift_perm_p': float((1 + (sn >= obs).sum()) / (1 + len(sn))),
                           'share_wallet_fills_lead_ge_2bps': float((wsc >= th).mean()), 'share_other_fills_lead_ge_2bps': float((osc >= th).mean()),
                           'share_wallet_fills_lead_le_-2bps': float((wsc <= -th).mean()), 'share_other_fills_lead_le_-2bps': float((osc <= -th).mean()),
                           'lift_at_2bps': prec / base, 'recall_at_2bps': float((wsc >= th).mean())}
        print(dur, wname, per, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out[wname][per].items()}, flush=True)
    # robustness on TEST only (AUC; circular null 500)
    X = F['test']; y = X[ycol].to_numpy(); rob = {}
    for lb in (2, 3, 5, 10):
        for L in (0, 1, 2):
            obs, null = fast_circ(X, y, lead(X, lb=lb, L=L), 500, 3)
            rob[f'lb={lb},L={L}'] = {'auc': obs, 'circ_p': float((1 + (null >= obs).sum()) / 501)}
    out[wname]['test_robustness'] = rob
    print(dur, wname, 'robustness', {k: (round(v['auc'], 3), round(v['circ_p'], 4)) for k, v in rob.items()}, flush=True)
json.dump(out, open(D + f'match_h2_precise_{dur}.json', 'w'), indent=1)
