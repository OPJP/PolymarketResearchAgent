"""H1 data: FOMC 'Fed Decision in <month>' events 2025-2026, hourly price history, wallet activity per market."""
import json, re, sys, pickle, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.adapters.http import shared_client
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
h=shared_client()
evs=[]
for off in range(0,600,100):
    d,s=h.get_json('https://gamma-api.polymarket.com/events',{'tag_slug':'fed-rates','closed':'true','limit':100,'offset':off,'order':'endDate','ascending':'false'},adapter='gamma.events',max_age=24*3600)
    if not d: break
    evs+=d
    if min((e.get('endDate') or '9') for e in d) < '2024-12-01': break
fed=[e for e in evs if re.match(r'^Fed [Dd]ecision in [A-Z][a-z]+\??$', e.get('title','')) and '2025-01-01'<=(e.get('endDate') or '')<'2026-11-01']
seen=set(); fed2=[]
for e in sorted(fed,key=lambda e:e['endDate']):
    if e['id'] in seen: continue
    seen.add(e['id']); fed2.append(e)
for e in fed2: print(e['slug'], e['endDate'], len(e.get('markets') or []), round(float(e.get('volume') or 0)))
# FOMC statement dates (public Federal Reserve calendar, published in advance); statement at 14:00 ET
FOMC={'2025-01':'2025-01-29T19:00','2025-03':'2025-03-19T18:00','2025-05':'2025-05-07T18:00','2025-06':'2025-06-18T18:00','2025-07':'2025-07-30T18:00','2025-09':'2025-09-17T18:00','2025-10':'2025-10-29T18:00','2025-12':'2025-12-10T19:00',
      '2026-01':'2026-01-28T19:00','2026-03':'2026-03-18T18:00','2026-04':'2026-04-29T18:00','2026-06':'2026-06-17T18:00','2026-07':'2026-07-29T18:00','2026-09':'2026-09-16T18:00','2026-10':'2026-10-28T18:00'}
import pandas as pd
data=[]
for e in fed2:
    end=pd.Timestamp(e['endDate'])
    key=None
    for k,v in FOMC.items():
        t=pd.Timestamp(v+'Z')
        if abs((end-t).total_seconds())<3*86400: key=k
    if key is None: print('no FOMC match', e['slug'], e['endDate']); continue
    dec=int(pd.Timestamp(FOMC[key]+'Z').timestamp())
    mks=[]
    for m in e.get('markets') or []:
        toks=json.loads(m.get('clobTokenIds') or '[]'); 
        if len(toks)!=2: continue
        ph,_=h.get_json('https://clob.polymarket.com/prices-history',{'market':toks[0],'startTs':dec-15*86400,'endTs':dec,'fidelity':60},adapter='clob.prices-history',max_age=None)
        act=[]; off=0
        while True:
            a,_=h.get_json('https://data-api.polymarket.com/activity',{'user':W,'market':m['conditionId'],'limit':500,'offset':off},adapter='data-api.activity',max_age=None)
            act+=a or []
            if not a or len(a)<500: break
            off+=500
        mks.append(dict(cid=m['conditionId'], q=m.get('question'), group=m.get('groupItemTitle'), toks=toks, outcomePrices=m.get('outcomePrices'), closedTime=m.get('closedTime'),
                        feeType=m.get('feeType'), feesEnabled=m.get('feesEnabled'), createdAt=m.get('createdAt'), hist=(ph or {}).get('history',[]), act=act))
        print(key, m.get('groupItemTitle'), len(mks[-1]['hist']), 'wallet rows', len(act), m.get('outcomePrices'), m.get('feeType'))
    data.append(dict(key=key, slug=e['slug'], decision_ts=dec, markets=mks))
pickle.dump(data, open(OUT+'h1_fomc.pkl','wb'))
