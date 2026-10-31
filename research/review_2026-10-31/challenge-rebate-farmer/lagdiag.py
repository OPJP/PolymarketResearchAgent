import sys, json, pickle; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from feats import load
from polyrea.analysis.updown import taker_buy_prints, score_prints, auc
import numpy as np
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
P,spot=load('15m')
H=pickle.load(open(S+'period_btc_1h.pkl','rb'))
sets={'15m':(P['fit']['prints'],P['test']['prints']),'1h':(taker_buy_prints(H['fit']['tapes'],H['fit']['windows']),taker_buy_prints(H['test']['tapes'],H['test']['windows']))}
lags=[-10,-5,-3,-2,-1,0,1,2,3,5,10]
out={}
for k,(f,t) in sets.items():
    for nm,df in (('fit',f),('test',t)):
        y=(df.wallet==W).to_numpy().astype(int)
        out[f'{k}_{nm}']={L:round(auc(score_prints(df,spot,L),y),3) for L in lags}
        print(k,nm,out[f'{k}_{nm}'])
json.dump(out,open(S+'lag_diagnostic.json','w'),indent=1)
