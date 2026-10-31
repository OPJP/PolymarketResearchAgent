"""per_market_decomposition pays q0 with clobTokenIds[0] and q1 with clobTokenIds[1]: is activity outcomeIndex aligned with the token list?"""
import _env, os, sys, pickle, json, collections
for name in sys.argv[1:]:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    c = collections.Counter()
    for r in win['activity']:
        if r.get('type') != 'TRADE': continue
        m = win['markets'].get(r['conditionId'])
        if not m: c['no market'] += 1; continue
        tok = json.loads(m.get('clobTokenIds') or '[]')
        oi = r.get('outcomeIndex')
        if oi is None or oi >= len(tok): c[f'bad index {oi} / {len(tok)} tokens'] += 1
        elif str(tok[oi]) == str(r['asset']): c['aligned'] += 1
        else: c['MISALIGNED'] += 1
        if len(tok) != 2: c[f'{len(tok)}-token market'] += 1
    print(name, dict(c))
