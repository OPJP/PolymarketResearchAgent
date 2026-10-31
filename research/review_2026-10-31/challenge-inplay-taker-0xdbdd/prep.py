import pickle, json, sys, pandas as pd, numpy as np
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.analysis.profile import resolution_info, market_family
S=sys.argv[1]
d=pickle.load(open(f'{S}/window.pkl','rb'))
t=d['trades'].copy(); m=d['markets']
res={c:resolution_info(mm) for c,mm in m.items()}
t['payout']=[res.get(c,{}).get('payout',{}).get(str(a),np.nan) for c,a in zip(t.condition_id,t.asset)]
t['smt']=t.condition_id.map(lambda c:(m.get(c) or {}).get('sportsMarketType'))
t['gst']=t.condition_id.map(lambda c:pd.Timestamp(m[c]['gameStartTime']).timestamp() if m.get(c,{}).get('gameStartTime') else np.nan)
t['fam']=[market_family(s, m.get(c)) for s,c in zip(t.slug,t.condition_id)]
t['pnl']=t['size']*t['payout']-t['usdc']
t['fee']=t['usdc']-t['size']*t['price']
t.to_pickle(f'{S}/trades_enriched.pkl')
print(t.pnl.sum(), t.fee.sum(), t.usdc.sum(), t.payout.isna().sum())
