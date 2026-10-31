import sys, pickle, random, json
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from polyrea.adapters.chain import PolygonChain, decode_fills
d=pickle.load(open('/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/win.pkl','rb'))
trades=d['trades']; markets=d['markets']
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
groups = trades.groupby(["tx", "asset"]).agg(size=("size", "sum"), usdc=("usdc", "sum"), side=("side", "first"), cid=("condition_id","first"), price=("price","mean"), ts=("ts","first")).reset_index()
rng = random.Random(0); idx=list(range(len(groups))); rng.shuffle(idx)
pick=groups.iloc[idx[:200]]
rec,_=PolygonChain().receipts(pick['tx'].tolist())
rows=[]
for _,g in pick.iterrows():
    r=rec.get(g['tx'])
    if not r: continue
    mine=[f for f in decode_fills(r) if f.maker==W and f.token_id==str(g['asset'])]
    if not mine: continue
    role=mine[0].role_of(W)
    m=markets.get(g['cid'],{})
    rows.append(dict(role=role, api_size=g['size'], api_usdc=g['usdc'], ch_shares=sum(f.shares for f in mine), ch_usdc=sum(f.usdc for f in mine), ch_fee=sum(f.fee for f in mine), price=g['price'], ver=mine[0].version, fee_sched=json.dumps(m.get('feeSchedule')) if m.get('feeSchedule') else None, feesEnabled=m.get('feesEnabled'), slug=m.get('slug'), ts=g['ts']))
df=pd.DataFrame(rows)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(df.groupby('role').agg(n=('api_usdc','size'), api_usdc=('api_usdc','sum'), ch_usdc=('ch_usdc','sum'), ch_fee=('ch_fee','sum'), api_sz=('api_size','sum'), ch_sz=('ch_shares','sum')))
t=df[df.role=='taker'].copy()
t['fee_over_usdc']=t.ch_fee/t.ch_usdc
t['fee_over_shares_pq']=t.ch_fee/(t.ch_shares*t.price*(1-t.price))
print(t[['api_size','ch_shares','api_usdc','ch_usdc','ch_fee','price','fee_over_usdc','fee_over_shares_pq','ver','slug']].head(25))
print('fee/(shares p(1-p)) quantiles', t.fee_over_shares_pq.describe())
print(df.fee_sched.value_counts().head())
print(df.feesEnabled.value_counts(dropna=False))
