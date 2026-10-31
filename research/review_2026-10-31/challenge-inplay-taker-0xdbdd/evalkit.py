"""Shared evaluation: within-market label-permutation match test and per-event backtest at observed taker prints."""
import sys, numpy as np, pandas as pd
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.stats.significance import hac_t_test, stationary_bootstrap_pvalue

def backtest(sel, cap=100.0):
    """Buy each selected taker print (liquidity that traded) with <= $cap, pay market fee, settle at resolution."""
    sel=sel[sel.payout.notna()]
    if sel.empty: return {'trades':0}
    usd=np.minimum(sel['size']*sel.price, cap); sh=usd/sel.price
    fee=sel.fee_rate*sel.price*(1-sel.price)*sh
    pnl=sh*sel.payout-usd-fee
    pe=pnl.groupby(sel.event_slug).sum()
    t=hac_t_test(pe.to_numpy())
    b=stationary_bootstrap_pvalue(pe.to_numpy(), n_boot=2000).p_value if len(pe)>=5 else None
    return {'trades':int(len(sel)),'events':int(len(pe)),'usd':float(usd.sum()),'pnl':float(pnl.sum()),
            'ret':float(pnl.sum()/usd.sum()),'per_event_t':float(t.statistic),'per_event_p':float(t.p_value),'boot_p':b}

def match_stat(hit, is_w):
    return hit[is_w].mean()-hit[~is_w].mean()

def perm_test(df, hit_col, n_perm=2000, seed=0):
    """Null: within each market, wallet labels are a random subset of that market's taker buys (same count)."""
    rng=np.random.default_rng(seed)
    hit=df[hit_col].to_numpy().astype(float); w=df.is_wallet.to_numpy()
    obs=match_stat(hit,w)
    groups=[np.flatnonzero(g) for g in [ (df.cid==c).to_numpy() for c in df.cid.unique()]]
    nw=[w[g].sum() for g in groups]
    null=np.empty(n_perm)
    for i in range(n_perm):
        lab=np.zeros(len(df),bool)
        for g,k in zip(groups,nw):
            if k: lab[rng.choice(g,k,replace=False)]=True
        null[i]=match_stat(hit,lab)
    return {'wallet_hit_rate':float(hit[w].mean()),'others_hit_rate':float(hit[~w].mean()),'diff':float(obs),
            'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(n_perm+1)),'n_wallet':int(w.sum()),'n_others':int((~w).sum())}

def within_auc(df,f):
    num=0;den=0
    for cid,g in df.groupby('cid'):
        w=g.loc[g.is_wallet,f].dropna().to_numpy(); o=g.loc[~g.is_wallet,f].dropna().to_numpy()
        if len(w)==0 or len(o)==0: continue
        o=np.sort(o); lt=np.searchsorted(o,w,'left'); le=np.searchsorted(o,w,'right')
        num+=(lt+0.5*(le-lt)).sum(); den+=len(w)*len(o)
    return num/den if den else np.nan

def perm_auc(df,f,n_perm=1000,seed=0):
    rng=np.random.default_rng(seed); obs=within_auc(df,f)
    d=df[['cid',f,'is_wallet']].copy(); null=[]
    for i in range(n_perm):
        d['is_wallet']=d.groupby('cid').is_wallet.transform(lambda s: rng.permutation(s.to_numpy()))
        null.append(within_auc(d,f))
    null=np.array(null)
    return {'auc':float(obs),'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(n_perm+1))}
