"""Stale-gap features: how far sibling markets / the game moved since the bought market last printed.
All inputs at time t use prints with ts <= t-L and ESPN plays with wallclock+D <= t-L."""
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *

def build(G,P,M,L=1,D=0):
    tape=Tape(P)
    # per game: list of sibling markets with direction mapping of token0
    tok0kind={}
    for cid,g in P.groupby('condition_id'):
        k=g[g.tok==0].side_kind.dropna()
        if len(k): tok0kind[cid]=k.iloc[0]
        else:
            k1=g[g.tok==1].side_kind.dropna()
            if len(k1): tok0kind[cid]={'home':'away','away':'home','over':'under','under':'over'}[k1.iloc[0]]
    opp={'home':'away','away':'home','over':'under','under':'over'}
    B=P[(P.side=='BUY')&P.side_kind.notna()].copy()
    q=B.ts.to_numpy()-L
    own_last=np.full(len(B),-1,np.int64)
    for cid,idx in B.groupby('condition_id').indices.items():
        own_last[idx]=tape.last_ts(cid,q[idx])
    B['own_stale']=np.where(own_last>=0,q-own_last,np.nan)
    gap_ml=np.full(len(B),np.nan); gap_sib=np.full(len(B),np.nan); nsib=np.zeros(len(B))
    ev_net=np.full(len(B),np.nan)
    Gi=G.set_index('event_slug')
    for ev,idx in B.groupby('event_slug').indices.items():
        sub=B.iloc[idx]
        cids=Gi.loc[ev,'cids']
        sk=sub.side_kind.to_numpy(); mt=sub.mtype.to_numpy(); own=sub.condition_id.to_numpy()
        ol=own_last[idx]; qq=q[idx]
        acc=np.zeros(len(idx)); cnt=np.zeros(len(idx)); accml=np.full(len(idx),np.nan)
        for c in cids:
            if c not in tok0kind: continue
            k0=tok0kind[c]; cm=M[c].get('sportsMarketType')
            a=tape.at(c,qq); b=tape.at(c,np.where(ol>=0,ol,qq))
            ch=a-b
            # direction: + if bought side kind equals token0 kind, - if opposite, nan if unrelated (team vs total)
            sg=np.where(sk==k0,1.0,np.where(sk==opp[k0],-1.0,np.nan))
            rel=np.isfinite(sg)&(own!=c)&np.isfinite(ch)
            acc[rel]+=(ch*sg)[rel]; cnt[rel]+=1
            if cm=='moneyline':
                accml=np.where(np.isfinite(sg)&(own!=c),ch*sg,accml)
        gap_sib[idx]=np.where(cnt>0,acc/np.maximum(cnt,1),np.nan); nsib[idx]=cnt; gap_ml[idx]=accml
        # ESPN: net favourable points since own last print (plays known at wallclock + D <= t-L)
        pl=np.array([(p[0],p[1],p[2]) for p in Gi.loc[ev,'plays']]) if len(Gi.loc[ev,'plays']) else np.zeros((0,3))
        if len(pl):
            kt=pl[:,0]+D
            o=np.argsort(kt,kind='stable'); kt=kt[o]; hs=pl[o,1]; as_=pl[o,2]
            hs=np.maximum.accumulate(hs); as_=np.maximum.accumulate(as_)
            def score_at(t):
                i=np.searchsorted(kt,t,side='right')-1
                return np.where(i>=0,hs[np.clip(i,0,None)],0), np.where(i>=0,as_[np.clip(i,0,None)],0)
            h1,a1=score_at(qq); h0,a0=score_at(np.where(ol>=0,ol,qq))
            dh=h1-h0; da=a1-a0
            net=np.select([sk=='home',sk=='away',sk=='over',sk=='under'],[dh-da,da-dh,dh+da,-(dh+da)],np.nan)
            ev_net[idx]=net
    B['gap_ml']=gap_ml; B['gap_sib']=gap_sib; B['nsib']=nsib; B['espn_net_since_last']=ev_net
    return B
if __name__=='__main__':
    G,P,M,split=load()
    B=build(G,P,M,L=1,D=0)
    B.to_pickle(BASE+'buys_feats2_L1.pkl')
    y=B.is_wallet.to_numpy(); fit=B.fit.to_numpy()
    for col in ('own_stale','gap_ml','gap_sib','espn_net_since_last'):
        r=[col]
        for mt in ('all','moneyline','spreads','totals'):
            m=fit & ((B.mtype==mt).to_numpy() if mt!='all' else True)
            r.append(f"{mt}:{auc(y[m],B[col].to_numpy()[m]):.3f}")
        print(' '.join(r))
    w=B[B.is_wallet&B.fit]; o=B[~B.is_wallet&B.fit]
    for col in ('gap_ml','gap_sib','espn_net_since_last'):
        print(col,'wallet q',w[col].quantile([.1,.25,.5,.75,.9]).round(3).tolist(),' others',o[col].quantile([.1,.25,.5,.75,.9]).round(3).tolist())
        print('   share>0 wallet',(w[col]>0).mean().round(3),'others',(o[col]>0).mean().round(3), ' share<0 wallet',(w[col]<0).mean().round(3),'others',(o[col]<0).mean().round(3), 'nan w',w[col].isna().mean().round(3))
