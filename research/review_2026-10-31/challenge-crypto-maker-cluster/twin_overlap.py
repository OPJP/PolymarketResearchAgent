# Recompute twin overlap over the 30-day window from cached activity; check twin-as-taker in the sampled public tapes.
import sys, json, pickle; sys.path.insert(0, '/home/user/PolymarketResearchAgent'); sys.path.insert(0, '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster')
from polyrea.workflows.investigate import load_window
AS_OF = 1793318400
B = load_window('0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed', 30, as_of=AS_OF)['trades']
A = load_window('0x3725d52f3c252e8374999cc8617292ea2608ad88', 30, as_of=AS_OF)['trades']
tb, ta = set(B.tx), set(A.tx)
mb, ma = set(B.condition_id), set(A.condition_id)
sb = set(zip(B.condition_id, B.ts)); sa = set(zip(A.condition_id, A.ts))
res = {'bosona_tx': len(tb), 'almach_tx': len(ta), 'shared_tx': len(tb & ta), 'bosona_markets': len(mb), 'almach_markets': len(ma), 'shared_markets': len(mb & ma),
       'share_of_bosona_markets_shared': len(mb & ma) / len(mb), 'share_of_almach_markets_shared': len(mb & ma) / len(ma),
       'market_second_pairs_bosona': len(sb), 'market_second_pairs_almach': len(sa), 'shared_market_second_pairs': len(sb & sa), 'jaccard_market_second': len(sb & sa) / len(sb | sa)}
# in shared txs: same token / same price?
j = B[B.tx.isin(tb & ta)].groupby(['tx']).agg(asset=('asset', 'first'), price=('price', 'mean')).join(A[A.tx.isin(tb & ta)].groupby('tx').agg(asset_a=('asset', 'first'), price_a=('price', 'mean')))
res['shared_tx_same_token_share'] = float((j.asset == j.asset_a).mean()); res['shared_tx_same_price_share'] = float(((j.price - j.price_a).abs() < 0.005).mean())
res['bosona_buy_share'] = float((B.side == 'BUY').mean()); res['almach_buy_share'] = float((A.side == 'BUY').mean())
print(json.dumps(res, indent=1))
json.dump(res, open('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster/twin_overlap.json', 'w'), indent=1)
