import sys, pickle, time
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.sports_study import load_games, game_prints, scoring_events
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'; AS_OF=1793318400
pm=PolymarketData(); t0=time.time()
loaded=load_games(W, 30, AS_OF, int(sys.argv[2]), 11, pm)
games, markets = loaded['games'], loaded['markets']
print('games', len(games), time.time()-t0, flush=True)
with ThreadPoolExecutor(6) as ex:
    frames=list(ex.map(lambda e: game_prints(e, markets, W, pm, 'taker'), games))
print('prints', sum(len(f) for f in frames), time.time()-t0)
pickle.dump({'games':games,'frames':frames,'markets':{c:markets[c] for e in games for c in e['cids']}}, open(sys.argv[1],'wb'))
