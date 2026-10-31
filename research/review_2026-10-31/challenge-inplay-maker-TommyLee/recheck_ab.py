"""Recheck ROC (ledger peak capital), on-chain sample (same seed, cached receipts) split by phase, rebate rows, Holm p."""
import pickle, json, numpy as np, pandas as pd, collections
from polyrea.workflows.investigate import load_window, verify_onchain
from polyrea.analysis.ledger import capital_and_roc
from polyrea.adapters.chain import PolygonChain, decode_fills
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
win=load_window(w,days=30,as_of=1793318400)
daily=pd.read_pickle(W+'/daily_pnl.pkl')['d_economic_pnl']
cap=capital_and_roc(win['ledger'],daily); print('capital',cap)
pk=win['ledger'].daily_peak_exposure(); print('peak exposure by day (last 32):'); print(pk.tail(32).round(0).to_string())
act=win['activity']
c=collections.defaultdict(float)
for r in act:
    if r.get('type') in ('TAKER_REBATE','MAKER_REBATE','REWARD') and r['timestamp']>=1790726400: c[r['type']]+=float(r.get('usdcSize') or 0)
print('income rows in window',dict(c))
v=verify_onchain(w,win['trades'],sample=200,seed=0)
print({k:v[k] for k in ('sampled','receipts_found','confirmed','maker_fill_share','maker_usdc_share','taker_fee_rate_observed')})
# phase split of the same sample
chain=PolygonChain(); t=win['trades']
groups=t.groupby(['tx','asset']).agg(size=('size','sum'),ts=('ts','min')).reset_index()
import random
rng=random.Random(0); idx=list(range(len(groups))); rng.shuffle(idx); pick=groups.iloc[idx[:200]]
rec,_=chain.receipts(pick.tx.tolist())
rows=[]
for _,g in pick.iterrows():
    r=rec.get(g.tx)
    if not r: continue
    for f in decode_fills(r):
        if f.maker==w and f.token_id==str(g.asset): rows.append({'ts':g.ts,'role':f.role_of(w),'usdc':f.usdc})
R=pd.DataFrame(rows); R['phase']=np.where(R.ts>=pd.Timestamp('2026-10-16T12:00Z').timestamp(),'Oct16+','before')
print(R.groupby(['phase','role']).agg(n=('usdc','size'),usdc=('usdc','sum')))
a1=json.load(open('/home/user/PolymarketResearchAgent/research/stage_a/stage_a1.json'))
ps=[(x['wallet'],x['metrics'].get('p_pre')) for x in a1 if x.get('metrics') and x['metrics'].get('p_pre') is not None]
from statsmodels.stats.multitest import multipletests
pv=np.array([p for _,p in ps]); rej,ph,_,_=multipletests(pv,method='holm')
i=[k for k,(ww,_) in enumerate(ps) if ww==w][0]; print('Holm p recomputed',ph[i],'n tests',len(pv))
