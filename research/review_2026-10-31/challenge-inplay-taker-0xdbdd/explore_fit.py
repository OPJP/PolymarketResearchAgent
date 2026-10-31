"""FIT-only exploration: which point-in-time tape features separate the wallet's buys from other takers' buys
in the same markets? Within-market AUC (pairs wallet-print vs other-print in the same market)."""
import pandas as pd, numpy as np, sys
S=sys.argv[1]
P=pd.read_pickle(f'{S}/prints_L2.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)&(P.period=='FIT')].copy()
B['size_usd']=B['size']*B.price
feats=['price','minutes','mom10','mom30','mom60','mom120','mom300','gap','since_last_print','flowk_30','flowk_120','n60','size_usd','pk_known']
def within_auc(df,f):
    num=0;den=0
    for cid,g in df.groupby('cid'):
        w=g.loc[g.is_wallet,f].dropna().to_numpy(); o=g.loc[~g.is_wallet,f].dropna().to_numpy()
        if len(w)==0 or len(o)==0: continue
        o=np.sort(o)
        lt=np.searchsorted(o,w,side='left'); le=np.searchsorted(o,w,side='right')
        num+=(lt+0.5*(le-lt)).sum(); den+=len(w)*len(o)
    return num/den if den else np.nan
for s in ['soccer_totals','general']:
    x=B[B.set==s]
    print(s, 'wallet',x.is_wallet.sum(),'others',(~x.is_wallet).sum())
    for f in feats:
        print(f'  {f:18s} AUC={within_auc(x,f):.3f}  wallet_med={x.loc[x.is_wallet,f].median():.4g} others_med={x.loc[~x.is_wallet,f].median():.4g}')
    print('  Under share wallet', (x[x.is_wallet].outcome=='Under').mean(), 'others', (x[~x.is_wallet].outcome=='Under').mean())
