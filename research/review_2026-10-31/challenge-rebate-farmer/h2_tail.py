import sys, json; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
import numpy as np, pandas as pd
from scipy import stats
from h2_favorite_lib import trades
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
R=json.load(open(S+'h2_favorite_results.json'))
out={}
for key in R:
    dur,var=key.split('_')
    p=R[key]['fitted']
    for per in ('fit','test'):
        df=pd.read_pickle(S+f'tk_{dur}_{per}_L2.pkl')
        f=trades(df,p['T'],p['theta'],p['m'],var=='spot')
        if len(f)==0: continue
        pay=np.where(f.is_up,f.up_payout,1-f.up_payout)
        f['won']=pay>0.5
        w=f.groupby('condition_id').agg(pnl=('pnl','sum'),usd=('usd','sum'),lost=('won',lambda s:(~s).any()),be=('price','mean'))
        # breakeven per-window loss prob: cost per $1 payout = mean(price*(1+rate*(1-price)))
        be=float(((f.price+f.fee_rate*f.price*(1-f.price))*f.usd).sum()/f.usd.sum())
        n=len(w); k=int(w.lost.sum())
        # exact one-sided binomial: P(losses <= k | loss rate = 1-be)
        pb=float(stats.binom.cdf(k,n,1-be))
        out[f'{key}_{per}']={'windows':n,'windows_with_loss':k,'breakeven_cost_per_$1':be,'binomial_p_one_sided':pb,'pnl':float(f.pnl.sum()),'usd':float(f.usd.sum())}
        print(key,per,out[f'{key}_{per}'])
json.dump(out,open(S+'h2_tail_check.json','w'),indent=1)
