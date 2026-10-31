"""Is the wallet first in a burst of same-direction taker prints (information lead) or a follower?"""
import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
F=pickle.load(open(W+'/frames160.pkl','rb')); tk=F['tk'].copy()
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
# direction of a taker print in terms of outcome 0: +1 if it buys outcome0 or sells outcome1
tk['dir0']=np.where(((tk.outcome==0)&(tk.side=='BUY'))|((tk.outcome==1)&(tk.side=='SELL')),1,-1)
tk['usd']=tk['size']*tk['price']
tk=tk.sort_values(['cid','ts']).reset_index(drop=True)
res=[]
for cid,g in tk.groupby('cid'):
    ts=g.ts.to_numpy(); d=g.dir0.to_numpy(); u=g.usd.to_numpy(); isw=(g.wallet==w).to_numpy(); side=g.side.to_numpy()
    for i in np.where(isw & (side=='BUY'))[0]:
        lo=np.searchsorted(ts,ts[i]-10,'left'); hi=np.searchsorted(ts,ts[i]+10,'right')
        same=(d[lo:hi]==d[i])&(~isw[lo:hi])
        before=same & (ts[lo:hi]<ts[i]); at=same&(ts[lo:hi]==ts[i]); after=same&(ts[lo:hi]>ts[i])
        res.append({'cid':cid,'ts':ts[i],'n_before':before.sum(),'usd_before':u[lo:hi][before].sum(),'n_same_sec':at.sum(),'n_after':after.sum(),'usd_after':u[lo:hi][after].sum(),'usd':u[i]})
R=pd.DataFrame(res)
print(len(R))
print('share with no other same-dir taker print in prior 10s:', (R.n_before==0).mean())
print('share with others in same second:', (R.n_same_sec>0).mean())
print('median usd before/after (others, same dir, 10s):', R.usd_before.median(), R.usd_after.median())
print('mean usd before/after:', R.usd_before.mean(), R.usd_after.mean())
# among bursts where total same-dir usd within +-10s >= 500
big=R[(R.usd_before+R.usd_after+R.usd)>=500]
print('big bursts',len(big),'share wallet first (no prior other within 10s):',(big.n_before==0).mean())
R.to_pickle(W+'/burst_rank.pkl')
