"""H1 FAIR-LINE: cross-line fair value from a normal model of final margin / total.

At decision time q = t - L, every sibling market of the same family (moneyline + all spread
lines for the home margin H; all total lines for the total T) contributes its last implied
probability P(X > x_i) from taker prints with ts <= q (fresh only: q - last_ts <= F).
Probit-linear WLS  z_i = a + b * x_i  (b = -1/sigma < 0) gives a fair P for the target line.
Score for a BUY print at price p of outcome k = fair_k - p. Target market excluded from its own fit.
"""
import sys, numpy as np, pandas as pd
from scipy.stats import norm
sys.path.insert(0,'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-taker-justaluckydude')
from common import *

def market_geometry(P,M):
    """cid -> (family, x threshold, token index whose event is X > x)"""
    geo={}
    for cid,g in P.groupby('condition_id'):
        m=M[cid]; mt=m.get('sportsMarketType'); line=m.get('line')
        k0=g[g.tok==0].side_kind.dropna(); k1=g[g.tok==1].side_kind.dropna()
        kind0=k0.iloc[0] if len(k0) else ({'home':'away','away':'home','over':'under','under':'over'}.get(k1.iloc[0]) if len(k1) else None)
        if kind0 is None: continue
        if mt=='moneyline' and kind0 in('home','away'):
            geo[cid]=('H',0.0, 0 if kind0=='home' else 1)
        elif mt=='spreads' and kind0 in ('home','away') and line is not None:
            l=float(line)
            # token0 team covers if its margin + line > 0
            if kind0=='home': geo[cid]=('H',-l,0)      # P(H > -l) = p(token0)
            else: geo[cid]=('H',l,1)                   # token0 away covers if H < l  -> P(H > l) = p(token1)
        elif mt=='totals' and kind0 in ('over','under') and line is not None:
            geo[cid]=('T',float(line), 0 if kind0=='over' else 1)
    return geo

def fair_scores(B,P,M,G,tape,geo,L=1,F=60,shift=None,pmin=0.04):
    """Return fair probability of the bought outcome for each BUY print in B (nan if not computable).
    shift: dict event_slug -> seconds added to sibling lookups (permutation null)."""
    out=np.full(len(B),np.nan)
    q_all=B.ts.to_numpy()-L
    cid_all=B.condition_id.to_numpy(); tok_all=B.tok.to_numpy()
    for ev,idx in B.groupby('event_slug').indices.items():
        cids=[c for c in G.loc[ev,'cids'] if c in geo]
        sh=(shift or {}).get(ev,0)
        for fam in ('H','T'):
            sib=[c for c in cids if geo[c][0]==fam]
            if len(sib)<2: continue
            sel=np.array([geo.get(c,(None,))[0]==fam for c in cid_all[idx]])
            ii=idx[sel]
            if len(ii)==0: continue
            q=q_all[ii]+sh
            X=np.array([geo[c][1] for c in sib])
            Pm=np.empty((len(ii),len(sib))); A=np.empty((len(ii),len(sib)))
            for j,c in enumerate(sib):
                p0=tape.at(c,q); lt=tape.last_ts(c,q)
                Pm[:,j]=np.where(geo[c][2]==0,p0,1-p0)   # P(X > x_j)
                A[:,j]=np.where(lt>=0,q-lt,1e9)
            own=np.array([[c==cc for c in sib] for cc in cid_all[ii]])
            W=((A<=F)&np.isfinite(Pm)&(Pm>=pmin)&(Pm<=1-pmin)&~own).astype(float)
            Z=norm.ppf(np.clip(np.nan_to_num(Pm,nan=0.5),1e-4,1-1e-4))
            sw=W.sum(1); mx=(W*X).sum(1)/np.maximum(sw,1e-9); mz=(W*Z).sum(1)/np.maximum(sw,1e-9)
            sxx=(W*(X-mx[:,None])**2).sum(1); sxz=(W*(X-mx[:,None])*(Z-mz[:,None])).sum(1)
            b=np.where(sxx>1e-9,sxz/np.maximum(sxx,1e-9),np.nan); a=mz-b*mx
            ok=(sw>=2)&(sxx>1e-6)&(b<0)
            xt=np.array([geo[c][1] for c in cid_all[ii]]); kt=np.array([geo[c][2] for c in cid_all[ii]])
            pf=norm.cdf(a+b*xt)   # fair P(X > x_target)
            fair=np.where(tok_all[ii]==kt,pf,1-pf)
            out[ii]=np.where(ok,fair,np.nan)
    return out

if __name__=='__main__':
    G,P,M,split=load(); Gi=G.set_index('event_slug')
    tape=Tape(P); geo=market_geometry(P,M)
    print('markets with geometry',len(geo),'families',pd.Series([g[0] for g in geo.values()]).value_counts().to_dict())
    B=P[(P.side=='BUY')&P.condition_id.isin(geo.keys())].copy().reset_index(drop=True)
    res={}
    for L in (1,):
        for F in (30,120,600):
            f=fair_scores(B,P,M,Gi,tape,geo,L=L,F=F)
            B[f'fair_L{L}_F{F}']=f
            s=f-B.price.to_numpy()
            y=B.is_wallet.to_numpy(); fit=B.fit.to_numpy()
            cov_w=np.isfinite(s[fit&y]).mean(); cov_o=np.isfinite(s[fit&~y]).mean()
            print(f'L{L} F{F}: FIT AUC wallet-vs-others {auc(y[fit],s[fit]):.3f}  coverage wallet {cov_w:.2f} others {cov_o:.2f}  median score wallet {np.nanmedian(s[fit&y]):.3f} others {np.nanmedian(s[fit&~y]):.3f}')
            for mt in ('moneyline','spreads','totals'):
                m=fit&(B.mtype==mt).to_numpy()
                print(f'    {mt}: AUC {auc(y[m],s[m]):.3f}  share score>0.03 wallet {(s[m&y]>0.03).mean():.3f} others {(s[m&~y]>0.03).mean():.3f}')
    B.to_pickle(BASE+'buys_fv.pkl')
