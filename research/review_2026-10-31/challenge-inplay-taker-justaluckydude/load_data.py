"""Reproduce sports_study game sample (seed=11) and dump games + full taker tapes (BUY and SELL)."""
import json, pickle, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis.profile import resolution_info
from polyrea.workflows.sports_study import load_games, _outcome_side, SPORTS_FEE_RATE
W='0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705'
AS_OF=1793318400
OUT=sys.argv[1]; MAXG=int(sys.argv[2])
pm=PolymarketData()
t0=time.time()
loaded=load_games(W, 30, AS_OF, MAXG, 11, pm)
games, markets = loaded['games'], loaded['markets']
print('games matched', len(games), 'in', round(time.time()-t0,1),'s', flush=True)
def prints(entry):
    game=entry['game']; end=game.plays[-1].ts+600
    rows=[]
    for cid in entry['cids']:
        m=markets[cid]
        tokens=json.loads(m.get('clobTokenIds') or '[]'); outcomes=json.loads(m.get('outcomes') or '[]')
        res=resolution_info(m)
        tape,_,_=pm.market_trades(cid, start=entry['start'], end=end, taker_only=True)
        for r in tape:
            if str(r.get('asset')) not in tokens: continue
            k=tokens.index(str(r['asset']))
            outcome=outcomes[k] if k<len(outcomes) else ''
            rows.append({'event_slug':entry['event_slug'],'condition_id':cid,'mtype':m.get('sportsMarketType') or '',
                'line': m.get('line'), 'ts':int(r['timestamp']),'wallet':(r.get('proxyWallet') or '').lower(),
                'is_wallet':(r.get('proxyWallet') or '').lower()==W,'side':r.get('side'),'tok':k,'outcome':outcome,
                'side_kind':_outcome_side(outcome, game),'price':float(r['price']),'size':float(r['size']),
                'tx': r.get('transactionHash'),
                'payout':res['payout'].get(str(r['asset'])) if res['resolved'] else np.nan,
                'fee_rate':float((m.get('feeSchedule') or {}).get('rate', SPORTS_FEE_RATE))})
    return pd.DataFrame(rows)
with ThreadPoolExecutor(6) as ex:
    frames=list(ex.map(prints, games))
allp=pd.concat(frames, ignore_index=True)
print('prints', len(allp), 'wallet', allp.is_wallet.sum(), 'in', round(time.time()-t0,1),'s')
gl=[{'event_slug':e['event_slug'],'league':e['league'],'start':e['start'],'cids':e['cids'],
     'home':e['game'].home,'away':e['game'].away,
     'plays':[(p.ts,p.home_score,p.away_score,p.scoring,p.home_wp,p.text) for p in e['game'].plays]} for e in games]
mk={c:markets[c] for e in games for c in e['cids']}
pickle.dump({'games':gl,'prints':allp,'markets':mk}, open(OUT,'wb'))
