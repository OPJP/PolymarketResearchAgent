import _env, os, pickle, json, collections
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import resolution_info
win = pickle.load(open(os.path.join(_env.SCR, 'win_elmcap2.pkl'), 'rb'))
act, markets = win['activity'], win['markets']
res_ts = {cid: r['closed_ts'] for cid, m in markets.items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
split_cids = {r['conditionId'] for r in act if r['type'] in ('SPLIT', 'MERGE')}
for cid in split_cids:
    rows = [r for r in act if r.get('conditionId') == cid]
    m = markets.get(cid, {})
    print('== cid', cid[:14], m.get('slug'), 'resolved_ts', res_ts.get(cid), 'n rows', len(rows))
    for r in rows:
        if r['type'] != 'TRADE' or len(rows) < 40:
            print('   ', r['timestamp'], r['type'], r.get('side'), r.get('outcomeIndex'), 'size', r.get('size'), 'usdc', r.get('usdcSize'), 'px', r.get('price'), r.get('transactionHash', '')[:12])
    tr = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if r['type'] == 'TRADE':
            k = (r.get('outcomeIndex'), r.get('side')); tr[k][0] += float(r['size']); tr[k][1] += float(r['usdcSize'])
    print('    trade totals (outcome, side) -> [shares, usdc]:', {k: [round(a), round(b)] for k, (a, b) in tr.items()})
led = build_ledger(win['wallet'], act, res_ts)
for k, p in led.positions.items():
    if p.condition_id in split_cids:
        print('pos', k[:20], 'shares', round(p.shares, 2), 'cost', round(p.cost, 2), 'closed', p.closed_at, p.close_kind)
# exact duplicates
full = collections.Counter(json.dumps(r, sort_keys=True) for r in act)
for k, v in full.items():
    if v > 1:
        r = json.loads(k); print('DUP x', v, r['timestamp'], r['type'], r.get('side'), r.get('size'), r.get('usdcSize'), r.get('transactionHash'))
