import sys, pickle, random, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.adapters.chain import PolygonChain, decode_fills
from polyrea.stats.significance import hac_t_test
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
t=pd.read_pickle(S+'trades_roles.pkl')
groups=t.groupby(['tx','asset']).agg(size=('size','sum'),role_fee=('role',lambda s: s.mode()[0]),nrole=('role','nunique')).reset_index()
rng=random.Random(0); idx=list(range(len(groups))); rng.shuffle(idx); pick=groups.iloc[idx[:200]]
rec,_=PolygonChain().receipts(pick.tx.tolist())
agree=n=0
for _,g in pick.iterrows():
    r=rec.get(g.tx)
    if not r: continue
    mine=[f for f in decode_fills(r) if f.maker==W and f.token_id==str(g.asset)]
    if not mine: continue
    roles={f.role_of(W) for f in mine}
    n+=1; agree+= (g.role_fee in roles)
print('fee-inferred role agrees with on-chain role:', agree, '/', n)
d=t.copy(); d['day']=pd.to_datetime(d.ts,unit='s').dt.floor('D')
dd=d.groupby(['day','role']).pnl.sum().unstack().fillna(0)
for r in ('maker','taker'):
    print(r, 'sum', round(dd[r].sum()), hac_t_test(dd[r].to_numpy()))
# maker + maker rebate (daily from user-pnl)
dl=pd.read_pickle(S+'daily.pkl')
mr=dl['d_maker_rebate'].iloc[-30:]; mr.index=mr.index-pd.Timedelta(days=1)  # value stamped at D midnight covers D-1
mr.index=mr.index.tz_localize(None) if mr.index.tz is not None else mr.index
x=dd['maker'].reindex(mr.index).fillna(0)+mr.values
print('maker fills + maker rebate, 30d sum', round(x.sum()), hac_t_test(x.to_numpy()))
json.dump({'role_agreement':[agree,n],'maker_pnl_30d':float(dd.maker.sum()),'taker_pnl_30d_after_fees':float(dd.taker.sum()),'maker_plus_rebate_30d':float(x.sum()),'maker_plus_rebate_hac_p':hac_t_test(x.to_numpy()).p_value},open(S+'role_decomposition.json','w'),indent=1)
