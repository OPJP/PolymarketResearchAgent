import pickle, collections, json
import pandas as pd
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
out={}
for dur in ('15m','5m'):
    P=pickle.load(open(S+f'period_btc_{dur}.pkl','rb'))
    cp=collections.Counter(); cp_usd=collections.Counter(); n_tx=0; self_tx=0
    as_maker_vs=collections.Counter()
    for per in ('fit','test'):
        for cid,tape in P[per]['tapes'].items():
            full=P[per]['full_tapes'].get(cid,[])
            bytx=collections.defaultdict(list)
            for r in full: bytx[r.get('transactionHash')].append(r)
            for r in tape:
                tx=r.get('transactionHash'); tk=(r.get('proxyWallet') or '').lower()
                rows=bytx.get(tx,[])
                makers=[(x.get('proxyWallet') or '').lower() for x in rows if not ((x.get('proxyWallet') or '').lower()==tk and x.get('side')==r.get('side') and x.get('asset')==r.get('asset'))]
                if tk==W:
                    n_tx+=1
                    if W in makers: self_tx+=1
                    for m in set(makers): cp[m]+=1
                elif W in makers:
                    as_maker_vs[tk]+=1
    tot=sum(cp.values()); totm=sum(as_maker_vs.values())
    out[dur]={'wallet_taker_orders':n_tx,'self_matched':self_tx,'top_makers_vs_wallet_taker':[(k,v,round(v/max(n_tx,1),3)) for k,v in cp.most_common(5)],
              'wallet_maker_fills_takers_top':[(k,v,round(v/max(totm,1),3)) for k,v in as_maker_vs.most_common(5)],'wallet_maker_fill_events':totm}
    print(dur, json.dumps(out[dur],indent=0))
json.dump(out,open(S+'counterparties.json','w'),indent=1)
