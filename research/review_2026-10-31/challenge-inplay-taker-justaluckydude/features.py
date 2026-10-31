import sys, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *
G,P,M,split=load()
tape=Tape(P)
Gi=G.set_index('event_slug')
# ML condition per game and which token is home
ml={}
for _,g in G.iterrows():
    for c in g.cids:
        if M[c].get('sportsMarketType')=='moneyline':
            sub=P[(P.condition_id==c)]
            if len(sub)==0: continue
            k0=sub[sub.tok==0].side_kind.dropna()
            if len(k0)==0: continue
            ml[g.event_slug]=(c, k0.iloc[0])  # side_kind of token 0 ('home'/'away')
            break
print('games with ML tape', len(ml), 'of', len(G))
B=P[(P.side=='BUY')&P.side_kind.notna()].copy()
L=1
def feats(B,L=1):
    out={}
    dirn=np.where(B.tok==0,1.0,-1.0)
    q=B.ts.to_numpy()-L
    for N in (5,15,30,60,180):
        mom=np.full(len(B),np.nan)
        for cid,idx in B.groupby('condition_id').indices.items():
            a=tape.at(cid,q[idx]); b=tape.at(cid,q[idx]-N)
            mom[idx]=(a-b)*dirn[idx]
        out[f'own_mom_{N}']=mom
    stale=np.full(len(B),np.nan)
    for cid,idx in B.groupby('condition_id').indices.items():
        stale[idx]=q[idx]-tape.last_ts(cid,q[idx])
    out['own_stale']=stale
    # moneyline momentum in favour of the bought team (team-sided outcomes only)
    for N in (5,15,30,60,180):
        mm=np.full(len(B),np.nan)
        for ev,idx in B.groupby('event_slug').indices.items():
            if ev not in ml: continue
            c,k0=ml[ev]
            sk=B.side_kind.to_numpy()[idx]
            sgn=np.where(sk==k0,1.0,np.where(np.isin(sk,['home','away']),-1.0,np.nan))
            a=tape.at(c,q[idx]); b=tape.at(c,q[idx]-N)
            mm[idx]=(a-b)*sgn
        out[f'ml_mom_{N}']=mm
    return pd.DataFrame(out,index=B.index)
F=feats(B)
B=B.join(F)
B.to_pickle(BASE+'buys_feats.pkl')
y=B.is_wallet.to_numpy()
fit=B.fit.to_numpy()
for col in F.columns:
    r=[col]
    for mt in ('all','moneyline','spreads','totals'):
        m=fit & ((B.mtype==mt).to_numpy() if mt!='all' else True)
        r.append(f"{mt}:{auc(y[m],B[col].to_numpy()[m]):.3f}")
    print(' '.join(r))
w=B[B.is_wallet&B.fit]; o=B[~B.is_wallet&B.fit]
for col in ('own_mom_15','own_mom_60','ml_mom_15','ml_mom_60','own_stale'):
    print(col,'wallet q',w[col].quantile([.1,.25,.5,.75,.9]).round(3).tolist(),' others',o[col].quantile([.1,.25,.5,.75,.9]).round(3).tolist())
    print('   share>0 wallet',(w[col]>0).mean().round(3),'others',(o[col]>0).mean().round(3), ' share<0 wallet',(w[col]<0).mean().round(3),'others',(o[col]<0).mean().round(3))
