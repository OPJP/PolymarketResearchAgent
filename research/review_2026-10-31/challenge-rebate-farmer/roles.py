import sys, pickle, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.analysis.profile import resolution_info, market_family
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
d=pickle.load(open(S+'win.pkl','rb'))
t=d['trades'].copy(); markets=d['markets']
pay={}; fam={}; rate={}; ws={}; we={}
for cid,m in markets.items():
    r=resolution_info(m); pay.update(r['payout'])
    fam[cid]=market_family(m.get('slug'), m)
    fs=m.get('feeSchedule') or {}
    rate[cid]=fs.get('rate') if m.get('feesEnabled') else 0.0
    ws[cid]=m.get('eventStartTime'); we[cid]=m.get('endDate')
t['fam']=t.condition_id.map(fam)
t['rate']=t.condition_id.map(rate).fillna(0.0)
t['gross']=t.price*t['size']
t['fee']=t.usdc-t.gross
t['fee_model']=t['size']*t.rate*t.price*(1-t.price)
t['role']=np.where(t.fee>0.5*t.fee_model+1e-6,'taker','maker')
t.loc[t.fee_model<1e-6,'role']='unknown_nofee'
t['payout']=t.asset.astype(str).map(pay)
t['pnl']=t['size']*t.payout-t.usdc
t['pnl_prefee']=t['size']*t.payout-t.gross
print('side counts', t.side.value_counts().to_dict())
print('resolved share', t.payout.notna().mean())
print('fee vs model ratio (taker)', (t.fee/t.fee_model)[t.role=='taker'].describe())
print('maker fee abs max', t.loc[t.role=='maker','fee'].abs().max())
g=t.groupby('role').agg(fills=('usdc','size'), usd=('usdc','sum'), fees=('fee','sum'), pnl=('pnl','sum'), pnl_prefee=('pnl_prefee','sum'))
print(g); print('total pnl', t.pnl.sum(), 'total fee', t.fee.sum())
g2=t.groupby(['fam','role']).agg(fills=('usdc','size'), usd=('usdc','sum'), fees=('fee','sum'), pnl=('pnl','sum'), pnl_prefee=('pnl_prefee','sum'))
g2['ret']=g2.pnl/g2.usd
g2=g2.sort_values('usd',ascending=False)
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
print(g2.head(40))
t.to_pickle(S+'trades_roles.pkl')
