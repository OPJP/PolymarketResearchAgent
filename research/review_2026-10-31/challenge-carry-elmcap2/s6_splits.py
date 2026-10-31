import pickle, sys
import numpy as np, pandas as pd
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',70)
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
d=pickle.load(open(OUT+'win.pkl','rb')); win=d['win']; act=pd.DataFrame(win['activity'])
act['dt']=pd.to_datetime(act.timestamp,unit='s',utc=True)
sm=act[act.type.isin(['SPLIT','MERGE','REDEEM','CONVERSION'])]
print(sm[['dt','type','title','size','usdcSize','conditionId']].sort_values('dt').to_string())
for cid in act[act.type=='SPLIT'].conditionId.unique():
    t=act[(act.conditionId==cid)&(act.type=='TRADE')]
    print('\nSPLIT market', cid[:12], t.title.iloc[0] if len(t) else '')
    print(t.groupby(['side','outcome']).agg(n=('size','size'),sh=('size','sum'),usd=('usdcSize','sum'),pmin=('price','min'),pmax=('price','max'),first=('dt','min'),last=('dt','max')).to_string())
