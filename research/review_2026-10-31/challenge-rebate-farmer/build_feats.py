import sys; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from feats import *
t=pd.read_pickle(S+'trades_roles.pkl')
dur=sys.argv[1]
P,spot=load(dur)
for per in ['fit','test']:
    p=P[per]
    flow=taker_flow(p['tapes'],p['windows'])
    flow.to_pickle(S+f'flow_{dur}_{per}.pkl')
    for lag in (2,):
        tk=add_features(p['prints'],flow,spot,t,lag=lag)
        tk.to_pickle(S+f'tk_{dur}_{per}_L{lag}.pkl')
        mk=add_features(maker_buy_prints(p['full_tapes'],p['tapes'],p['windows']),flow,spot,t,lag=lag)
        mk.to_pickle(S+f'mk_{dur}_{per}_L{lag}.pkl')
        print(dur,per,lag,len(tk),tk.y.sum(),len(mk),mk.y.sum(),flush=True)
