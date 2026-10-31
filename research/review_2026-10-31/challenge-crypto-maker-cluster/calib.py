# Calibration of public PIT fair values on a 5 s grid. Blend fitted on FIT only; TEST only scored.
import sys, json; sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from engine import *
from sklearn.linear_model import LogisticRegression
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
P = load(dur); spot, _ = spot_index(P)
L = 1
def grid(per):
    M = P[per]['M']; TR = trade_stream(M).sort_values(['condition_id', 'ts'], kind='stable'); trg = dict(tuple(TR.groupby('condition_id')))
    rows = []
    for w in P[per]['windows']:
        if w.up_payout is None or w.condition_id not in trg: continue
        tr = trg[w.condition_id]; t = np.arange(w.start_ts + 5, w.end_ts, 5)
        ru = ref_up_at(tr.ts.to_numpy(), tr.up_px.to_numpy(), t, L)
        mu = fair_up_vectorized(spot, np.full(len(t), w.start_ts), np.full(len(t), w.end_ts), t - L, w.twap_seconds)
        rows.append(pd.DataFrame({'cid': w.condition_id, 't': t, 'tleft': (w.end_ts - t) / (w.end_ts - w.start_ts), 'ref_up': ru, 'model_up': mu, 'y': float(w.up_payout)}))
    return pd.concat(rows, ignore_index=True)
def lg(p): p = np.clip(p, 1e-3, 1 - 1e-3); return np.log(p / (1 - p))
def X(g): return np.c_[lg(g.ref_up), lg(g.model_up), lg(g.ref_up) * g.tleft, lg(g.model_up) * g.tleft]
def ll(p, y): p = np.clip(p, 1e-4, 1 - 1e-4); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
out = {}
G = {per: grid(per).dropna() for per in ('fit', 'test')}
clf = LogisticRegression(C=1e3, max_iter=2000).fit(X(G['fit']), G['fit'].y)
for per, g in G.items():
    pb = clf.predict_proba(X(g))[:, 1]
    out[per] = {'n': len(g), 'logloss_ref': ll(g.ref_up.clip(0.001, 0.999), g.y), 'logloss_model': ll(g.model_up, g.y), 'logloss_blend': ll(pb, g.y),
                'brier_ref': float(np.mean((g.ref_up - g.y) ** 2)), 'brier_model': float(np.mean((g.model_up - g.y) ** 2)), 'brier_blend': float(np.mean((pb - g.y) ** 2))}
out['blend_coef'] = clf.coef_.tolist(); out['blend_intercept'] = clf.intercept_.tolist()
print(json.dumps(out, indent=1)) if False else print(out)
pickle.dump({'clf': clf}, open(D + f'blend_{dur}.pkl', 'wb'))
