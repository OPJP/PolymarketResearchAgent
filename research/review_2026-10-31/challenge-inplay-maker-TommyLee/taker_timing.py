"""Where do the wallet's taker buys sit relative to the public price path?"""
import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
F=pickle.load(open(W+'/frames160.pkl','rb')); tk=F['tk']; f=pickle.load(open(W+'/wallet_fills160.pkl','rb'))
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
tk=tk.sort_values(['cid','ts']).reset_index(drop=True)
tk['p0']=np.where(tk.outcome==0,tk.price,1-tk.price)
series={cid:(g.ts.to_numpy(),g.p0.to_numpy()) for cid,g in tk.groupby('cid')}
def p0_at(cid,t,side='right'):
    ts,p=series[cid]; k=np.searchsorted(ts,t,side=side)-1
    return p[k] if k>=0 else np.nan
rows=[]
for role in ['taker','maker']:
    sub=f[(f.role==role)&(f.side=='BUY')]
    for r in sub.itertuples():
        sgn=1 if r.outcome==0 else -1
        out={'role':role,'cid':r.cid,'ts':r.ts,'price':r.price,'size':r.size,'pay':r.pay}
        for lag in [-120,-60,-30,-10,-5,-2,-1]:
            out[f'd{lag}']=sgn*(p0_at(r.cid,r.ts+lag,'right')-p0_at(r.cid,r.ts-1,'right')) if lag!=-1 else 0
        for lag in [1,5,10,30,60,300]:
            out[f'f{lag}']=sgn*(p0_at(r.cid,r.ts+lag)-p0_at(r.cid,r.ts-1))
        out['price_vs_last']=r.price-(p0_at(r.cid,r.ts-1) if r.outcome==0 else 1-p0_at(r.cid,r.ts-1))
        rows.append(out)
X=pd.DataFrame(rows)
pd.set_option('display.width',200)
for role,g in X.groupby('role'):
    wts=g['size']
    print(role, len(g))
    print(' mean move of bought outcome (past: p(t+lag)-p(t-1) for negative lag means p(t-1) relative to earlier is -d):')
    print('  past (p(t-1)-p(t-L)):', {c:round(-np.nanmean(g[c]),4) for c in ['d-120','d-60','d-30','d-10','d-5','d-2']})
    print('  future (p(t+L)-p(t-1)):', {c:round(np.nanmean(g[c]),4) for c in ['f1','f5','f10','f30','f60','f300']})
    print('  price - last print:', g.price_vs_last.describe()[['mean','25%','50%','75%']].round(4).to_dict())
    print('  edge at settle (pay-price) share-weighted:', np.average(g.pay-g.price,weights=wts))
X.to_pickle(W+'/fill_timing.pkl')
