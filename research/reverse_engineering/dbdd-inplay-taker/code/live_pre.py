"""Live lab, development blocks: what precedes a decision, measured strictly before it (book at t_sign - 1 s,
so the wallet's own match, which the recorder can receive slightly before the signing stamp, is excluded).

(a) limit vs best ask 1 s before signing; (b) mid move of the bought token over the 10 s / 60 s / 300 s before
that; (c) X3: seconds since the sports websocket's last score change in the same game (gameId), for decisions
and for control times in the same markets. Writes results/iter2_live_pre.json.
"""
import sys, os, glob, json, zlib
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd, numpy as np
from live_books import load_maps, BLOCKS, safe

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
gm = json.load(open(f'{CACHE}/gamma2.json'))
tok0, idx_of, ev_of, cid_of_tok = load_maps()
Z = np.load(f'{CACHE}/live_books_arrays.npz')
B = {k[1:]: Z[k] for k in Z.files}
act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/dev_*.parquet')])
act = act[act.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
O = pd.read_parquet(f'{CACHE}/orders.parquet', columns=['tx', 't_ts_ms', 't_px', 't_usdc'])
d = act.merge(O, left_on='transactionHash', right_on='tx')
d = d[[any(a <= x < b for a, b in BLOCKS) for x in d.timestamp]].copy()

# sports websocket score changes per gameId
sc = {}
last = {}
for a, b in BLOCKS:
    for r in safe('sports', a, b):
        try:
            m = json.loads(r['m']) if isinstance(r.get('m'), str) else r.get('m')
        except Exception:
            continue
        if not isinstance(m, dict) or 'gameId' not in m:
            continue
        g, s = m.get('gameId'), m.get('score')
        if s is None:
            continue
        if g in last and last[g] != s:
            sc.setdefault(g, []).append(r['t'])
        last[g] = s
SC = {g: np.array(sorted(v), float) for g, v in sc.items()}
print('sports ws games with score changes', len(SC), 'changes', sum(len(v) for v in SC.values()))


def gid(c):
    m = gm.get(c) or {}
    g = m.get('gameId') or ((m.get('events') or [{}])[0] or {}).get('gameId')
    try:
        return int(g)
    except Exception:
        return None


def feat(c, idx, ts):
    arr = B.get(tok0.get(c))
    out = {}
    if arr is not None:
        def at(ms):
            i = np.searchsorted(arr[:, 0], ms, side='right') - 1
            return arr[i] if i >= 0 else None
        r1 = at(ts - 1000)
        if r1 is not None:
            out['ask1'] = r1[3] if idx == 0 else 1 - r1[1]
            mid1 = (r1[1] + r1[3]) / 2
            for h in (10, 60, 300):
                r0 = at(ts - 1000 - h * 1000)
                if r0 is not None:
                    out[f'mv{h}'] = (mid1 - (r0[1] + r0[3]) / 2) * (1 if idx == 0 else -1)
    g = gid(c)
    if g is not None and g in SC:
        s = SC[g]
        k = np.searchsorted(s, ts, side='right') - 1
        out['since_score'] = (ts - s[k]) / 1000.0 if k >= 0 else np.inf
        out['ws_game'] = 1
    else:
        out['ws_game'] = 0
    return out


rng = np.random.default_rng(5)
rows = []
for r in d.itertuples(index=False):
    c, idx, ts = r.conditionId, int(r.outcomeIndex), float(r.t_ts_ms)
    f = feat(c, idx, ts)
    rows.append(dict(kind='wallet', cid=c, limit=r.t_px, slug=r.slug, **f))
    for j in range(5):
        tc = ts + rng.uniform(-1800, 1800) * 1000
        rows.append(dict(kind='control', cid=c, slug=r.slug, **feat(c, idx, tc)))
X = pd.DataFrame(rows)
w, cc = X[X.kind == 'wallet'], X[X.kind == 'control']
res = {'n_decisions': int(len(w)), 'with_book': int(w.ask1.notna().sum()),
       'limit_eq_ask_1s_before': float(np.mean(np.abs(w.limit - w.ask1) < 0.005)),
       'limit_within_1tick_of_ask_1s_before': float(np.mean(np.abs(w.limit - w.ask1) <= 0.0105)),
       'limit_below_ask_1s_before': float(np.mean(w.limit - w.ask1 < -0.005)), 'limit_above_ask_1s_before': float(np.mean(w.limit - w.ask1 > 0.005))}
for h in (10, 60, 300):
    col = f'mv{h}'
    res[f'{col}_wallet_mean'] = float(w[col].mean())
    res[f'{col}_control_mean'] = float(cc[col].mean())
    res[f'{col}_wallet_pos_share_nonzero'] = float((w[col] > 0).sum() / max((w[col] != 0).sum(), 1))
    res[f'{col}_control_pos_share_nonzero'] = float((cc[col] > 0).sum() / max((cc[col] != 0).sum(), 1))
    res[f'{col}_wallet_nonzero'] = float((w[col].fillna(0) != 0).mean())
    res[f'{col}_control_nonzero'] = float((cc[col].fillna(0) != 0).mean())
ws_w, ws_c = w[w.ws_game == 1], cc[cc.ws_game == 1]
res['decisions_in_ws_games'] = int(len(ws_w))
for lo, hi in ((0, 30), (30, 60), (60, 120), (0, 120)):
    res[f'score_change_{lo}_{hi}s_before_wallet'] = float(((ws_w.since_score >= lo) & (ws_w.since_score < hi)).mean()) if len(ws_w) else None
    res[f'score_change_{lo}_{hi}s_before_control'] = float(((ws_c.since_score >= lo) & (ws_c.since_score < hi)).mean()) if len(ws_c) else None
json.dump(res, open(os.path.join(WS, 'results', 'iter2_live_pre.json'), 'w'), indent=1)
for k, v in res.items():
    print(k, v)
