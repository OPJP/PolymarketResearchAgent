import json, pickle, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.analysis.profile import resolution_info, market_family
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
d=pickle.load(open(OUT+'win.pkl','rb')); win=d['win']
tr=win['trades']; mk=win['markets']; led=win['ledger']
pd.set_option('display.width',250); pd.set_option('display.max_colwidth',60)
tr['dt']=pd.to_datetime(tr.ts,unit='s',utc=True)
g=tr.groupby('condition_id').agg(title=('title','first'),slug=('slug','first'),n=('size','size'),usdc=('usdc','sum'),shares=('size','sum'),
   first=('dt','min'),last=('dt','max'),pmin=('price','min'),pmed=('price','median'),pmax=('price','max'),buy=('side',lambda s:(s=='BUY').mean()))
rows=[]
for cid,r in g.iterrows():
    m=mk.get(cid,{}); ri=resolution_info(m)
    rows.append(dict(cid=cid, endDate=m.get('endDate'), closedTime=m.get('closedTime'), resolved=ri['resolved'], closed_ts=pd.to_datetime(ri['closed_ts'],unit='s',utc=True) if ri['closed_ts'] else None,
     created=m.get('createdAt'), negRisk=m.get('negRisk'), fam=market_family(r.slug,m)))
g=g.join(pd.DataFrame(rows).set_index('cid'))
g=g.sort_values('usdc',ascending=False)
print(g[['title','n','usdc','first','last','pmin','pmed','pmax','buy','endDate','closed_ts','resolved']].head(40).to_string())
g.to_csv(OUT+'markets_summary.csv')
