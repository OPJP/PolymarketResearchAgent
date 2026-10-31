"""F5: on-chain OrderFilled events of the wallet's own orders, from receipts of its trade transactions
(activity transactionHash) in [D0, D1) < H. drpc's free plan rejects eth_getLogs ranges above ~100 blocks, so
receipts (cached forever) are used instead. Keeps logs whose maker topic is the wallet (its orders); role =
taker when the taker topic is the exchange contract, else maker (resting order)."""
import sys, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import pandas as pd
from polyrea.adapters.chain import PolygonChain, decode_fills
H = 1792713600
W = '0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
OUT = '/home/user/PolymarketResearchAgent/.cache/re/elmcap2-carry/'
D0, D1, tag = sys.argv[1], sys.argv[2], sys.argv[3]
a = pd.read_parquet(OUT + 'activity_preH.parquet')
t0s, t1s = pd.Timestamp(D0, tz='UTC').timestamp(), min(pd.Timestamp(D1, tz='UTC').timestamp(), H)
tr = a[(a.type == 'TRADE') & (a.timestamp >= t0s) & (a.timestamp < t1s)]
txs = tr.transactionHash.dropna().unique().tolist()
print('trades', len(tr), 'txs', len(txs), flush=True)
ch = PolygonChain()
rows = []; t0 = time.time()
for i in range(0, len(txs), 40):
    rec, _ = ch.receipts(txs[i:i + 40], batch=4)
    for tx, r in rec.items():
        if not r: continue
        blk = int(r.get('blockNumber', '0x0'), 16)
        for f in decode_fills(r):
            if f.maker != W: continue
            rows.append(dict(tx=tx, block=blk, li=f.log_index, exchange=f.exchange, version=f.version, order_hash=f.order_hash, taker=f.taker,
                             role='taker' if f.taker == f.exchange else 'maker', side=f.side, token=f.token_id, shares=f.shares, usdc=f.usdc, fee=f.fee))
    if (i // 40) % 25 == 0: print('tx', i, len(txs), 'own fills', len(rows), round(time.time() - t0), flush=True)
df = pd.DataFrame(rows)
df.to_parquet(OUT + f'chain_own_{tag}.parquet')
print('done own fills', len(df), 'orders', df.order_hash.nunique() if len(df) else 0, flush=True)
