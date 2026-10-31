import pickle, json, collections, re
import pandas as pd, numpy as np
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
d=pickle.load(open(W+'/window.pkl','rb'))
t=d['trades']; mk=d['markets']; act=d['activity']
print(collections.Counter(r.get('type') for r in act))
# market types by slug pattern
def mtype(s):
    s=s or ''
    m=re.search(r'-(game\d+|map-?\d+|total|handicap|.*)$', s)
    return s.split('-')[-1] if s else ''
t['tail']=t['slug'].str.replace(r'.*-(\d{4}-\d{2}-\d{2})','DATE',regex=True)
print(t['slug'].head(20).tolist())
print(t['title'].str.extract(r' - (.*)$')[0].fillna('MATCH').value_counts().head(20))
cid=t['condition_id'].iloc[0]; m=mk[cid]
print(json.dumps({k:m.get(k) for k in ['question','slug','outcomes','gameStartTime','startDate','endDate','closedTime','feeSchedule','sportsMarketType','umaResolutionStatus','eventStartTime','groupItemTitle','orderPriceMinTickSize','orderMinSize','rewardsMinSize','rewardsMaxSpread','clobRewards','makerBaseFee','takerBaseFee','feesEnabled']},indent=1,default=str))
print(sorted(m.keys()))
