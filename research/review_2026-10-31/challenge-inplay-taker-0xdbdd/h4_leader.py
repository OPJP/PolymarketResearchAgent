"""H4 COPY-LEADER: the wallet copies specific other takers. Leaders are chosen on FIT as wallets whose in-play BUY on
a token is followed by our wallet's BUY of the same token within (L, 60] s far more often than chance. On TEST:
rule fires on a print if a leader bought the same token in [t-60, t-L]. Match: label-permutation within market and
a leader-clock shift null; backtest: buy those prints (excluding leader and wallet prints)."""
import sys, json, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S)
from evalkit import backtest, perm_test
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
P=pd.read_pickle(f'{S}/prints_L2.pkl')
B=P[(P.side=='BUY')&(P.minutes>=0)].copy()
B['tok']=B.cid+':'+B.k.astype(str)
L=2; WIN=60
def preceded(df, leaders, shift=0):
    """For each print, does any leader BUY of the same token occur in [t-WIN, t-L] (leader clock shifted by `shift`)?"""
    out=np.zeros(len(df),bool)
    lead=df[df.wallet.isin(leaders)]
    lt={tok:np.sort(g.ts.to_numpy()+shift) for tok,g in lead.groupby('tok')}
    for tok,idx in df.groupby('tok').indices.items():
        if tok not in lt: continue
        a=lt[tok]; t=df.ts.to_numpy()[idx]
        lo=np.searchsorted(a,t-WIN,'left'); hi=np.searchsorted(a,t-L,'right')
        out[idx]=hi>lo
    return out
F=B[B.period=='FIT'].reset_index(drop=True); T=B[B.period=='TEST'].reset_index(drop=True)
# FIT: candidate leaders = wallets with >=20 in-play buys in FIT; rate = share of their buys followed by our wallet within (L,WIN]
wb=F[F.wallet==W]; wt={tok:np.sort(g.ts.to_numpy()) for tok,g in wb.groupby('tok')}
cand=F[F.wallet!=W].groupby('wallet').size(); cand=cand[cand>=20].index
X=F[F.wallet.isin(cand)].copy()
fol=np.zeros(len(X),bool)
for tok,idx in X.groupby('tok').indices.items():
    if tok not in wt: continue
    a=wt[tok]; t=X.ts.to_numpy()[idx]
    lo=np.searchsorted(a,t+L,'left'); hi=np.searchsorted(a,t+WIN,'right'); fol[idx]=hi>lo
X['followed']=fol
# baseline: probability that our wallet buys a token within a random 58 s window, per leader = compare with shifted (+600 s)
fol2=np.zeros(len(X),bool)
for tok,idx in X.groupby('tok').indices.items():
    if tok not in wt: continue
    a=wt[tok]; t=X.ts.to_numpy()[idx]+600
    lo=np.searchsorted(a,t+L,'left'); hi=np.searchsorted(a,t+WIN,'right'); fol2[idx]=hi>lo
X['followed_shift']=fol2
st=X.groupby('wallet').agg(n=('ts','size'),fol=('followed','sum'),fol_shift=('followed_shift','sum'),mk=('cid','nunique'))
st['rate']=st.fol/st.n; st['excess']=st.fol-st.fol_shift
leaders=st[(st.fol>=5)&(st.fol>=3*st.fol_shift.clip(lower=1))].sort_values('excess',ascending=False)
out={'fit_candidates':int(len(st)),'fit_leaders':leaders.head(20).reset_index().to_dict('records')}
Ls=set(leaders.index)
out['n_leaders']=len(Ls)
# how many of wallet's FIT buys were preceded by a leader
F['hit']=preceded(F,Ls); T['hit']=preceded(T,Ls)
out['fit_wallet_hit']=float(F.hit[F.wallet==W].mean()); out['fit_others_hit']=float(F.hit[F.wallet!=W].mean())
if Ls:
    pt=perm_test(T,'hit',n_perm=1000); out['test_match_label_perm']=pt
    rng=np.random.default_rng(5); null=[]
    for _ in range(200):
        sh=int(rng.integers(300,1500))*int(rng.choice([-1,1]))
        h=preceded(T,Ls,sh); null.append(h[T.is_wallet].mean()-h[~T.is_wallet].mean())
    null=np.array(null); out['test_match_shift_null']={'obs':pt['diff'],'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=pt['diff']).sum())/(len(null)+1))}
    out['test_backtest']=backtest(T[T.hit&~T.is_wallet&~T.wallet.isin(Ls)])
    out['test_leaders_own_buys']=backtest(T[T.wallet.isin(Ls)])
print(json.dumps(out,indent=1,default=float))
json.dump(out,open(f'{S}/h4_leader_result.json','w'),indent=1,default=float)
