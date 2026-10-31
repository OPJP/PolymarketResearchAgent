"""Shared loaders for the challenge study (scratch, not repo code)."""
import sys, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.pit import TimeSeries
from polyrea.analysis.updown import SpotIndex, fair_up_vectorized

D = '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster/'
BOS = '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed'
ALM = '0x3725d52f3c252e8374999cc8617292ea2608ad88'

def load(dur='5m'):
    P = pickle.load(open(D + f'updown_btc_{dur}.pkl', 'rb'))
    for k in ('fit', 'test'):
        for X in ('T', 'M'):
            if X in P[k]:
                P[k][X] = P[k][X].rename(columns={'size': 'sz'})
    return P

def spot_index(P):
    ev = np.concatenate([P['fit']['spot_ev'], P['test']['spot_ev']]); vals = np.concatenate([P['fit']['spot_val'], P['test']['spot_val']])
    o = np.argsort(ev, kind='stable')
    ts = TimeSeries.build('spot.kraken.btc', zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1)
    return SpotIndex(ts), ts

def frames(per):
    """Return (taker df, passive-buy df) with tx hashes. Taker rows = takerOnly tape; passive = full tape rows minus taker rows."""
    by = {w.condition_id: w for w in per['windows']}
    trows, prow = [], []
    for cid, tape in per['tapes'].items():
        w = by.get(cid)
        if w is None or w.up_payout is None: continue
        keys = {}
        for r in tape:
            a = str(r.get('asset'))
            if a not in (w.up_token, w.down_token): continue
            k = (r.get('transactionHash'), (r.get('proxyWallet') or '').lower(), a, r.get('side'))
            keys[k] = keys.get(k, 0) + 1
            trows.append((cid, int(r['timestamp']), (r.get('proxyWallet') or '').lower(), a == w.up_token, r.get('side'), float(r['price']), float(r['size']), r.get('transactionHash'), w.start_ts, w.end_ts, w.up_payout, w.fee_rate))
        for r in per['full_tapes'].get(cid, []):
            a = str(r.get('asset'))
            if a not in (w.up_token, w.down_token): continue
            k = (r.get('transactionHash'), (r.get('proxyWallet') or '').lower(), a, r.get('side'))
            if keys.get(k, 0) > 0:
                keys[k] -= 1; continue
            prow.append((cid, int(r['timestamp']), (r.get('proxyWallet') or '').lower(), a == w.up_token, r.get('side'), float(r['price']), float(r['size']), r.get('transactionHash'), w.start_ts, w.end_ts, w.up_payout, w.fee_rate))
    cols = ['condition_id', 'ts', 'wallet', 'is_up', 'side', 'price', 'size', 'tx', 'start_ts', 'end_ts', 'up_payout', 'fee_rate']
    T = pd.DataFrame(trows, columns=cols); M = pd.DataFrame(prow, columns=cols)
    for X in (T, M):
        X['payout'] = np.where(X['is_up'], X['up_payout'], 1 - X['up_payout'])
        X['frac'] = (X['ts'] - X['start_ts']) / (X['end_ts'] - X['start_ts'])
    return T, M
