import pandas as pd, numpy as np
S='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/'
for dur in ['15m','5m']:
    for kind in ['tk','mk']:
        rows=[]
        for per in ['fit','test']:
            d=pd.read_pickle(S+f'{kind}_{dur}_{per}_L2.pkl'); d=d[d.up_payout.notna()]
            pay=np.where(d.is_up,d.up_payout,1-d.up_payout); usd=d['size']*d.price
            fee=(d.fee_rate*d.price*(1-d.price)*d['size']) if kind=='tk' else 0*usd
            pre=d['size']*pay-usd
            for who,m in (('wallet',d.y==1),('others',d.y==0)):
                rows.append((per,who,int(m.sum()),float(usd[m].sum()),float(pre[m].sum()/usd[m].sum()),float((pre[m]-fee[m]).sum()/usd[m].sum())))
        print(dur,kind); print(pd.DataFrame(rows,columns=['period','who','n','usd','ret_prefee','ret_postfee']).round(4).to_string(index=False))
