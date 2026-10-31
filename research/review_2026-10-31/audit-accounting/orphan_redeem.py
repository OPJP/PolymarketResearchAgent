import _env, os, sys, pickle, collections
name = sys.argv[1]
win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
act = win['activity']
first = {}
for r in act:
    if r.get('type') in ('TRADE', 'SPLIT'): first.setdefault(r['conditionId'], r['timestamp'])
orph = [r for r in act if r.get('type') in ('REDEEM', 'MERGE') and (r['conditionId'] not in first or first[r['conditionId']] > r['timestamp'])]
c = collections.Counter((r['type'], r['conditionId'] in first, float(r.get('usdcSize') or 0) > 0) for r in orph)
print('(type, condition traded later in window?, usdc>0):', dict(c))
for r in sorted(orph, key=lambda r: -float(r.get('usdcSize') or 0))[:8]:
    print(r['timestamp'], r['type'], r.get('usdcSize'), r.get('size'), (r.get('slug') or '')[:60], 'first fill', first.get(r['conditionId']))
same_sec = [r for r in orph if r['conditionId'] in first and first[r['conditionId']] - r['timestamp'] < 5]
print('orphans whose first fill is <5s after the redeem:', len(same_sec))
