import sys, time, pickle, random, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from collections import defaultdict
from polyrea.adapters.chain import PolygonChain, decode_fills
W = {'bosona': '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed', 'almach': '0x3725d52f3c252e8374999cc8617292ea2608ad88'}
chain = PolygonChain()
res = {}
for name, w in W.items():
    tr = pickle.load(open(f'win_{name}.pkl', 'rb'))['trades']
    groups = tr.groupby(['tx', 'asset']).agg(size=('size', 'sum'), usdc=('usdc', 'sum'), side=('side', 'first')).reset_index()
    rng = random.Random(0); idx = list(range(len(groups))); rng.shuffle(idx)
    pick = groups.iloc[idx[:200]]
    t = time.time()
    receipts, sources = chain.receipts(pick['tx'].tolist())
    cached = sum(1 for s in sources if getattr(s, 'cached', False))
    roles = defaultdict(float); cnt = defaultdict(int); fees = defaultdict(float); conf = 0
    counterparties = defaultdict(int)
    for _, g in pick.iterrows():
        rec = receipts.get(g['tx'])
        if not rec: continue
        fills = decode_fills(rec)
        mine = [f for f in fills if f.maker == w and f.token_id == str(g['asset'])]
        sh = sum(f.shares for f in mine)
        if mine and abs(sh - g['size']) <= max(0.005 * g['size'], 0.011): conf += 1
        for f in mine:
            r = f.role_of(w); roles[r] += f.usdc; cnt[r] += 1; fees[r] += f.fee
            if r == 'maker': counterparties[f.taker] += 1
    other = W['almach'] if name == 'bosona' else W['bosona']
    res[name] = {'confirmed': conf, 'roles_usdc': dict(roles), 'role_counts': dict(cnt), 'fees_by_role': dict(fees),
                 'maker_fee_rate': fees['maker'] / roles['maker'] if roles['maker'] else None,
                 'taker_fee_rate': fees['taker'] / roles['taker'] if roles['taker'] else None,
                 'maker_counterparty_is_twin': counterparties.get(other, 0), 'secs': round(time.time() - t, 1), 'cached_sources': cached, 'n_sources': len(sources)}
    print(name, json.dumps(res[name], indent=1))
json.dump(res, open('onchain_fees.json', 'w'), indent=1)
