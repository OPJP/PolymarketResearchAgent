import sys, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
G,P,M,split=load()
for lg,g in G.groupby('league'):
    n=sum(len(x) for x in g.plays); nw=sum(sum(1 for p in x if p[4] is not None) for x in g.plays)
    games_wp=sum(any(p[4] is not None for p in x) for x in g.plays)
    print(lg, 'games',len(g),'games with wp',games_wp,'plays',n,'with wp',nw)
# sample spread market metadata
c=[c for c in M if M[c].get('sportsMarketType')=='spreads'][0]
m=M[c]; print({k:m.get(k) for k in ('question','outcomes','line','groupItemTitle','slug','feeSchedule','gameStartTime','clobTokenIds')})
c=[c for c in M if M[c].get('sportsMarketType')=='totals'][0]
m=M[c]; print({k:m.get(k) for k in ('question','outcomes','line','groupItemTitle','slug')})
# how many spread/total lines per game
P2=P.drop_duplicates('condition_id')
print(P2.groupby(['event_slug','mtype']).size().unstack().describe())
