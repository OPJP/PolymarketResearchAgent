import pickle, numpy as np, pandas as pd
from polyrea.stats.significance import hac_t_test
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
F=pickle.load(open(W+'/frames160.pkl','rb')); tk,mk=F['tk'],F['mk']
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
wt=tk[tk.wallet==w].copy(); wt['role']='taker'
wm=mk[mk.wallet==w].copy(); wm['role']='maker'
f=pd.concat([wt,wm],ignore_index=True)
sgn=np.where(f.side=='BUY',1,-1)
f['gross']=sgn*f['size']*(f['pay']-f['price'])
f['fee']=np.where(f.role=='taker', f['size']*0.05*f['price']*(1-f['price']), 0.0)
f['usd']=f['size']*f['price']
f['net']=f['gross']-f['fee']
print(f.groupby(['role','side']).agg(n=('size','size'),usd=('usd','sum'),gross=('gross','sum'),fee=('fee','sum'),net=('net','sum')))
print('total gross',f.gross.sum(),'fees',f.fee.sum(),'net',f.net.sum(), 'usd', f.usd.sum())
# taker rebate 50% of fees; maker rebate 15% of taker fees on fills against wallet's maker orders -> compute: for maker rows, counterpart taker fee approximated by size*0.05*p*(1-p)
f['maker_rebate_est']=np.where(f.role=='maker', 0.15*f['size']*0.05*f['price']*(1-f['price']),0.0)
print('est taker rebate 50%:',0.5*f.fee.sum(),' maker rebate est', f.maker_rebate_est.sum())
# per market t-tests for maker gross and taker net
for role in ['maker','taker']:
    pm=f[f.role==role].groupby('cid')['net'].sum()
    r=hac_t_test(pm.to_numpy()); print(role,'per-market net mean',pm.mean(),'t',r.statistic,'p',r.p_value,'n',len(pm))
pickle.dump(f,open(W+'/wallet_fills160.pkl','wb'))
# taker fills: price vs prior tape: how far from the last print before (other outcome converted)
