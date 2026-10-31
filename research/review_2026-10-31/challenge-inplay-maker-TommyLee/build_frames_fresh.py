"""Build tidy frames: taker tape, maker rows, wallet fills labelled maker/taker, for the 160 sampled markets."""
import pickle, json
import numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
d=pickle.load(open(W+'/window.pkl','rb')); markets=d['markets']
T=pickle.load(open(W+'/tapes_fresh60.pkl','rb'))
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
tk_rows=[]; mk_rows=[]
for cid,taker,full,_,_ in T['parts']:
    m=markets[cid]; tokens=json.loads(m.get('clobTokenIds') or '[]')
    keys={}
    for r in taker:
        if str(r.get('asset')) not in tokens: continue
        k=(r.get('transactionHash'),(r.get('proxyWallet') or '').lower(),str(r.get('asset')),r.get('side'))
        keys[k]=keys.get(k,0)+1
        tk_rows.append({'cid':cid,'ts':int(r['timestamp']),'outcome':tokens.index(str(r['asset'])),'side':r['side'],'price':float(r['price']),'size':float(r['size']),'wallet':(r.get('proxyWallet') or '').lower(),'tx':r.get('transactionHash')})
    for r in full:
        if str(r.get('asset')) not in tokens: continue
        k=(r.get('transactionHash'),(r.get('proxyWallet') or '').lower(),str(r.get('asset')),r.get('side'))
        if keys.get(k,0)>0:
            keys[k]-=1; continue
        mk_rows.append({'cid':cid,'ts':int(r['timestamp']),'outcome':tokens.index(str(r['asset'])),'side':r['side'],'price':float(r['price']),'size':float(r['size']),'wallet':(r.get('proxyWallet') or '').lower(),'tx':r.get('transactionHash')})
tk=pd.DataFrame(tk_rows); mkr=pd.DataFrame(mk_rows)
pay=T['payouts']
for df in (tk,mkr):
    df['pay0']=df['cid'].map(pay)
    df['pay']=np.where(df['outcome']==0, df['pay0'], 1-df['pay0'])
meta={}
for cid in T['cids']:
    m=markets[cid]
    fs=m.get('feeSchedule') or {}
    meta[cid]={'slug':m.get('slug'),'q':m.get('question'),'gst':m.get('gameStartTime'),'secondsDelay':m.get('secondsDelay'),'rate':fs.get('rate'),'exp':fs.get('exponent'),'rebateRate':fs.get('rebateRate'),'smt':m.get('sportsMarketType'),'tick':m.get('orderPriceMinTickSize')}
meta=pd.DataFrame(meta).T
print(meta[['secondsDelay','rate','exp','rebateRate','smt','tick']].astype(str).value_counts().head(20))
pickle.dump({'tk':tk,'mk':mkr,'meta':meta,'payouts':pay,'active':T['active'],'cids':T['cids']}, open(W+'/frames_fresh60.pkl','wb'))
print(len(tk),len(mkr), (tk.wallet==w).sum(), (mkr.wallet==w).sum())
