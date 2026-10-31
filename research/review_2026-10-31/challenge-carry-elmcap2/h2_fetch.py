"""H2 data: binary deadline markets ('by/before/in <Month>') ending at Jul 31, Aug 31 (FIT), Sep 30, Oct 15 (TEST) 2026."""
import json, re, sys, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.adapters.http import shared_client, HttpError
import pandas as pd
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
h=shared_client()
WINDOWS={'2026-07-31':('FIT','2026-07-31T00:00:00Z','2026-08-01T12:00:00Z'),'2026-08-31':('FIT','2026-08-31T00:00:00Z','2026-09-01T12:00:00Z'),
         '2026-09-30':('TEST','2026-09-30T00:00:00Z','2026-10-01T12:00:00Z'),'2026-10-15':('TEST','2026-10-15T00:00:00Z','2026-10-16T12:00:00Z')}
pat=re.compile(r'\b(by|before|in)\s+(the\s+end\s+of\s+)?(July|August|September|October|Jul|Aug|Sep|Sept|Oct)\b', re.I)
out=[]
for key,(split,a,b) in WINDOWS.items():
    rows=[]
    def scan(a_ts,b_ts):
        got=[]; off=0
        while True:
            try:
                d,_=h.get_json('https://gamma-api.polymarket.com/markets',{'closed':'true','end_date_min':pd.Timestamp(a_ts,unit='s',tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'),'end_date_max':pd.Timestamp(b_ts,unit='s',tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ'),'limit':100,'offset':off},adapter='gamma.markets',max_age=24*3600)
            except HttpError as e:
                if e.status==422 and b_ts-a_ts>1:
                    mid=(a_ts+b_ts)//2; return scan(a_ts,mid)+scan(mid+1,b_ts)
                print('  gamma truncated at', a_ts, b_ts, off, flush=True); return got
            got+=d or []
            if not d or len(d)<100: return got
            off+=100
            if off>=2000:
                if b_ts-a_ts<=1:
                    print('  gamma truncated (same-second endDate) at', a_ts, flush=True); return got
                mid=(a_ts+b_ts)//2; return scan(a_ts,mid)+scan(mid+1,b_ts)
    rows=scan(int(pd.Timestamp(a).timestamp()), int(pd.Timestamp(b).timestamp()))
    rows=list({m['conditionId']:m for m in rows if m.get('conditionId')}.values())
    cand=[]
    for m in rows:
        q=m.get('question') or ''
        try: outs=json.loads(m.get('outcomes') or '[]'); toks=json.loads(m.get('clobTokenIds') or '[]'); pays=[float(x) for x in json.loads(m.get('outcomePrices') or '[]')]
        except Exception: continue
        if outs!=['Yes','No'] or len(toks)!=2 or not pays or max(pays)<0.999: continue
        if not pat.search(q): continue
        if float(m.get('volumeNum') or 0)<20000: continue
        cand.append(m)
    print(key, split, 'gamma rows', len(rows), 'deadline binary vol>=20k', len(cand))
    for m in cand:
        toks=json.loads(m['clobTokenIds']); end=int(pd.Timestamp(m['endDate']).timestamp())
        try:
            ph,_=h.get_json('https://clob.polymarket.com/prices-history',{'market':toks[1],'startTs':end-11*86400,'endTs':end,'fidelity':60},adapter='clob.prices-history',max_age=None)
        except HttpError as e:
            ph={}
        act=[]; off=0
        while True:
            aa,_=h.get_json('https://data-api.polymarket.com/activity',{'user':W,'market':m['conditionId'],'limit':500,'offset':off},adapter='data-api.activity',max_age=None)
            act+=aa or []
            if not aa or len(aa)<500: break
            off+=500
        out.append(dict(key=key, split=split, cid=m['conditionId'], q=m['question'], event=(m.get('events') or [{}])[0].get('slug'), end=end, toks=toks,
                        pays=[float(x) for x in json.loads(m['outcomePrices'])], tick=float(m.get('orderPriceMinTickSize') or 0.01), feeType=m.get('feeType'),
                        fee_rate=float((m.get('feeSchedule') or {}).get('rate',0) or 0), vol=float(m.get('volumeNum') or 0), hist=(ph or {}).get('history',[]), act=act))
    print(' wallet traded in', sum(1 for x in out if x['key']==key and any(r.get('type')=='TRADE' for r in x['act'])))
pickle.dump(out, open(OUT+'h2_deadline.pkl','wb'))
