import sys; sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer')
from feats import *
from polyrea.analysis.updown import auc
t=pd.read_pickle(S+'trades_roles.pkl')
dur=sys.argv[1]
P,spot=load(dur)
for per in ['fit']:
    p=P[per]
    flow=taker_flow(p['tapes'],p['windows'])
    tk=add_features(p['prints'],flow,spot,t)
    mk=add_features(maker_buy_prints(p['full_tapes'],p['tapes'],p['windows']),flow,spot,t)
    for name,df in (('taker',tk),('passive',mk)):
        print(f'== {dur} {per} {name}: n={len(df)} wallet={df.y.sum()} share={df.y.mean():.4f}')
        for f in ['price','secs_to_end','frac','mom30','mom120','prem','spot_edge','imb','pair_vs_own','size']:
            a=auc(df[f].to_numpy(dtype=float), df.y.to_numpy())
            w=df.loc[df.y==1,f]; o=df.loc[df.y==0,f]
            print(f'  {f:12s} AUC={a:.3f}  wallet med={w.median():.4f} others med={o.median():.4f}  wallet nan={w.isna().mean():.2f}')
    tk.to_pickle(S+f'tk_{dur}_{per}.pkl'); mk.to_pickle(S+f'mk_{dur}_{per}.pkl')
