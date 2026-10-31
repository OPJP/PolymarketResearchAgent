"""H7 SOCCER-REACT on ESPN keyEvents: after a goal (ESPN wallclock + D seconds), within W seconds buy Over on totals.
Also measures the wallet's excess reaction share and direction vs other takers. ESPN soccer summaries publish goal
wallclock times; the publication delay D is a fitted parameter (never assumed 0). Events: soccer totals markets from
both tape samples; FIT/TEST split at Oct 15 by game start. Only leagues mapped below are attempted."""
import sys, json, pickle, re, numpy as np, pandas as pd
S=sys.argv[1]; sys.path.insert(0,S); sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from evalkit import backtest, perm_test
from polyrea.adapters.http import shared_client
from polyrea.adapters.espn import team_matches
from concurrent.futures import ThreadPoolExecutor
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'; SPLIT=1793318400-15*86400
LG={'epl':'eng.1','elc':'eng.2','lal':'esp.1','es2':'esp.2','bun':'ger.1','sea':'ita.1','itsb':'ita.2','fl1':'fra.1','ucl':'uefa.champions',
    'uel':'uefa.europa','mls':'usa.1','uslc':'usa.usl.1','mex':'mex.1','bra':'bra.1','bra2':'bra.2','arg':'arg.1','col1':'col.1','kor':'kor.1',
    'jap':'jpn.1','spl':'ksa.1','por':'por.1','ere':'ned.1','nor':'nor.1','per1':'per.1','ecu1':'ecu.1','tur':'tur.1','sco':'sco.1','aus':'aus.1','chi':'chn.1','nwsl':'usa.nwsl'}
# ---- prints from both samples (totals Over/Under BUYs in-play)
P=pd.read_pickle(f'{S}/prints_L2.pkl'); A=P[(P.set=='soccer_totals')&(P.side=='BUY')&(P.minutes>=0)&P.outcome.isin(['Over','Under'])][['ts','price','size','is_wallet','outcome','payout','fee_rate','cid','event_slug','gst']].copy()
tp=pickle.load(open(f'{S}/tapes.pkl','rb'))['sel'].set_index('condition_id')
A['title']=A.cid.map(tp.title)
d=pickle.load(open(f'{S}/fresh_soccer.pkl','rb'))
sys.path.insert(0,'/home/user/PolymarketResearchAgent')
from polyrea.analysis.profile import resolution_info
rows=[]
for kind,cid,mm,gst,s,rr in d['tapes']:
    if kind!='tot' or not rr: continue
    res=resolution_info(mm); tok=[str(x) for x in json.loads(mm['clobTokenIds'])]; outs=json.loads(mm['outcomes'])
    if not res['resolved']: continue
    for r in rr:
        if r.get('side')!='BUY' or str(r.get('asset')) not in tok or int(r['timestamp'])<gst: continue
        k=tok.index(str(r['asset']))
        rows.append({'ts':int(r['timestamp']),'price':float(r['price']),'size':float(r['size']),'is_wallet':(r.get('proxyWallet') or '').lower()==W,
                     'outcome':outs[k],'payout':res['payout'].get(tok[k],np.nan),'fee_rate':float((mm.get('feeSchedule') or {}).get('rate',0.05)),
                     'cid':cid,'event_slug':s,'gst':gst,'title':mm.get('question')})
A=pd.concat([A,pd.DataFrame(rows)],ignore_index=True)
A=A[A.outcome.isin(['Over','Under'])&A.payout.notna()]
A['pref']=A.event_slug.str.split('-').str[0]
A=A[A.pref.isin(LG)]
print('candidate events',A.event_slug.nunique(),flush=True)
h=shared_client()
def espn_goals(slug):
    g=A[A.event_slug==slug].iloc[0]; lg=LG[g.pref]; mt=re.match(r'(.+?) vs\.? (.+?):',g.title or '')
    if not mt: return slug,None
    a,b=mt.group(1),mt.group(2)
    for off in (0,-1,1):
        day=pd.Timestamp(int(g.gst)+off*86400,unit='s',tz='UTC').strftime('%Y%m%d')
        try: sb,_=h.get_json(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard',{'dates':day},adapter='espn.scoreboard',max_age=None)
        except Exception: continue
        for ev in sb.get('events') or []:
            comps=ev.get('competitions',[{}])[0].get('competitors',[])
            if len(comps)==2 and any(team_matches(a,c) for c in comps) and any(team_matches(b,c) for c in comps) and abs(pd.Timestamp(ev['date']).timestamp()-g.gst)<4*3600:
                try: sm,_=h.get_json(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/summary',{'event':ev['id']},adapter='espn.summary',max_age=None)
                except Exception: return slug,None
                ke=sm.get('keyEvents') or []
                goals=[int(pd.Timestamp(k['wallclock']).timestamp()) for k in ke if k.get('scoringPlay') and k.get('wallclock')]
                kick=[k for k in ke if k.get('wallclock')]
                return slug,{'goals':sorted(goals),'n_key':len(kick)}
    return slug,None
with ThreadPoolExecutor(4) as ex: G=dict(ex.map(espn_goals,sorted(A.event_slug.unique())))
G={k:v for k,v in G.items() if v and v['n_key']>0}
A=A[A.event_slug.isin(G)].reset_index(drop=True)
A['period']=np.where(A.gst<SPLIT,'FIT','TEST')
print('matched events',len(G),'FIT',A[A.period=='FIT'].event_slug.nunique(),'TEST',A[A.period=='TEST'].event_slug.nunique(),'wallet prints',int(A.is_wallet.sum()),flush=True)
def since_goal(df,D,shift=None,rng=None):
    out=np.full(len(df),np.nan)
    for s,idx in df.groupby('event_slug').indices.items():
        gl=np.array(G[s]['goals'],float)
        if not len(gl): continue
        sh=0 if shift is None else int(rng.integers(300,1500))*int(rng.choice([-1,1]))
        kn=np.sort(gl+D+sh); tq=df.ts.to_numpy()[idx]; j=np.searchsorted(kn,tq,side='right')-1
        out[idx]=np.where(j>=0,tq-kn[np.clip(j,0,None)],np.nan)
    return out
def hit(df,D,Wn,shift=None,rng=None):
    sg=since_goal(df,D,shift,rng); return (df.outcome=='Over').to_numpy()&(sg>=0)&(sg<=Wn)&(df.price>=0.05).to_numpy()&(df.price<=0.95).to_numpy()
F=A[A.period=='FIT'].reset_index(drop=True); T=A[A.period=='TEST'].reset_index(drop=True)
rows=[]
for D in (-10,0,10,20,30,60,90):
    for Wn in (15,30,60,120,300):
        hF=hit(F,D,Wn)
        if hF.sum()<20: continue
        bt=backtest(F[hF]); rows.append({'D':D,'W':Wn,'fit_t':bt['per_event_t'],'fit_ret':bt['ret'],'fit_trades':bt['trades'],
            'fit_match_diff':float(hF[F.is_wallet.to_numpy()].mean()-hF[~F.is_wallet.to_numpy()].mean())})
R=pd.DataFrame(rows); out={'matched_events':len(G),'goals_total':int(sum(len(v['goals']) for v in G.values())),'fit_events':int(F.event_slug.nunique()),'test_events':int(T.event_slug.nunique()),
     'wallet_fit':int(F.is_wallet.sum()),'wallet_test':int(T.is_wallet.sum())}
rng=np.random.default_rng(17)
for nm,b in [('match_fit',R.sort_values('fit_match_diff',ascending=False).iloc[0]),('profit_fit',R.sort_values('fit_t',ascending=False).iloc[0])]:
    D,Wn=int(b.D),int(b.W); T2=T.copy(); T2['hit']=hit(T2,D,Wn)
    res={'D':D,'W':Wn,'fit':b.drop(['D','W']).to_dict(),'test_backtest':backtest(T2[T2.hit]),'test_backtest_excl_wallet':backtest(T2[T2.hit&~T2.is_wallet]),
         'test_match_label_perm':perm_test(T2,'hit',n_perm=1000)}
    obs=res['test_match_label_perm']['diff']; null=[]
    for _ in range(300):
        hh=hit(T2,D,Wn,True,rng); null.append(hh[T2.is_wallet.to_numpy()].mean()-hh[~T2.is_wallet.to_numpy()].mean())
    null=np.array(null); res['test_match_shift_null']={'obs':obs,'null_p95':float(np.percentile(null,95)),'perm_p':float((1+(null>=obs).sum())/(len(null)+1))}
    out[nm]=res
# wallet reaction: share of wallet vs others' buys within 60 s after a goal (D=0..30), any outcome; direction = Over share
for D in (0,30):
    sg=since_goal(A,D); r=(sg>=0)&(sg<=60)
    out[f'reaction_D{D}_W60']={'wallet_share':float(r[A.is_wallet.to_numpy()].mean()),'others_share':float(r[~A.is_wallet.to_numpy()].mean()),
        'wallet_over_share_in_window':float((A.outcome[r&A.is_wallet.to_numpy()]=='Over').mean()) if (r&A.is_wallet.to_numpy()).sum() else None,
        'others_over_share_in_window':float((A.outcome[r&~A.is_wallet.to_numpy()]=='Over').mean())}
print(json.dumps(out,indent=1,default=float)); print(R.sort_values('fit_t',ascending=False).head(5).to_string())
json.dump(out,open(f'{S}/h7_espn_soccer_result.json','w'),indent=1,default=float)
