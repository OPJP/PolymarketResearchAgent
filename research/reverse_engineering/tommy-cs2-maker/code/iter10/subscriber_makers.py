"""X135 (information panel iter-9 P4): who re-prices with the wallet? Informativeness of other makers' add LEVELS by
maker class on the BUILD-live books (10-31 12-18, development), next to the wallet's (finding 14).

Classes of non-wallet adds: by calldata-linked maker identity where the add was later filled (slow trio, group G,
0x2e3c40fa the X34 cancel-wave maker, other linked), else by size (5 = trio-like, 10 = group-G-like, 20 =
0x2e3c40fa-like, other sizes). For each class: Spearman(offset from the others' mid 100 ms before the add, the others'
mid move from +100 ms to +2 / +10 / +30 s) on all adds and on adds in books quiet for 1 s before (no mid change).
Signature A (shared timing, the edge = position in the fan-out): subscriber classes about as informative as the
wallet. Signature C (unique value): the wallet's 10-s Spearman >= 0.3 against <= 0.15 for every subscriber class.
Output: results/subscriber_makers.json
"""
import json
import numpy as np, pandas as pd
from scipy.stats import spearmanr

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/subscriber_makers.json'
v5 = json.load(open('research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json'))
TRIO = {'0x72aaaaf9', '0x2529c68d', '0xfe8a28be'}
G = {a.lower()[:10] for a in v5['group_G']}

A = pd.read_parquet(f'{ROOT}/linked_adds_dev.parquet')
A['vown'] = (A.owner == 'wallet') | (A.F_mkt & (A.in_burst | (A['size'] != 100)))
A = A[A.kind == 'add'].copy()
mk8 = A.maker.fillna('').astype(str).str.lower().str[:10]


def cls(r_own, m8, size, owner):
    if r_own:
        return 'wallet'
    if owner == 'other' and m8:
        if m8 in TRIO:
            return 'trio(linked)'
        if m8 in G:
            return 'groupG(linked)'
        if m8 == '0x2e3c40fa':
            return '0x2e3c40fa(linked)'
        return 'other(linked)'
    if size == 5:
        return 'size5'
    if size == 10:
        return 'size10'
    if size == 20:
        return 'size20'
    return 'other_size'

A['cls'] = [cls(o, m, s, w) for o, m, s, w in zip(A.vown, mk8, A['size'], A.owner)]
M = pd.read_parquet(f'{ROOT}/others_mid_dev.parquet').sort_values(['a', 's'])
mids = {a: (g.s.to_numpy(float), g.mid.to_numpy(float)) for a, g in M.groupby('a')}
rows = []
for a, g in A.groupby('a'):
    x = mids.get(a)
    if x is None:
        continue
    ts, md = x
    s = g.s.to_numpy(float)
    j0 = np.searchsorted(ts, s - 100, side='right') - 1
    jq = np.searchsorted(ts, s - 1100, side='right') - 1
    j1 = np.searchsorted(ts, s + 100, side='right') - 1
    ok = j0 >= 0
    tok0 = (g.side == 'BUY').to_numpy()
    bid = np.where(tok0, g.p.to_numpy(float), 1 - g.p.to_numpy(float))
    m0 = np.where(tok0, md[np.maximum(j0, 0)], 1 - md[np.maximum(j0, 0)])
    m1 = np.where(tok0, md[np.maximum(j1, 0)], 1 - md[np.maximum(j1, 0)])
    quiet = (j0 == jq) & (jq >= 0)
    d = {'cls': g.cls.to_numpy(), 'off': (bid - m0) * 100, 'quiet': quiet, 'ok': ok}
    for h in (2, 10, 30):
        jh = np.searchsorted(ts, s + h * 1000, side='right') - 1
        mh = np.where(tok0, md[np.maximum(jh, 0)], 1 - md[np.maximum(jh, 0)])
        d[f'dm{h}'] = (mh - m1) * 100
    rows.append(pd.DataFrame(d))
X = pd.concat(rows)
X = X[X.ok & np.isfinite(X.off) & (X.off.abs() <= 15)]
res = {}
for c, g in X.groupby('cls'):
    r = {'n': int(len(g)), 'n_quiet': int(g.quiet.sum()), 'offset_p50_c': round(float(g.off.median()), 2)}
    for h in (2, 10, 30):
        r[f's{h}'] = round(float(spearmanr(g.off, g[f'dm{h}'])[0]), 3) if len(g) >= 30 else None
        q = g[g.quiet]
        r[f's{h}_quiet'] = round(float(spearmanr(q.off, q[f'dm{h}'])[0]), 3) if len(q) >= 30 else None
    res[c] = r
json.dump(res, open(OUT, 'w'), indent=1)
for c, r in sorted(res.items(), key=lambda kv: -kv[1]['n']):
    print(c, r)
