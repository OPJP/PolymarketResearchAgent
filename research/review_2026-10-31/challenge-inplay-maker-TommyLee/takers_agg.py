import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
F=pickle.load(open(W+'/frames160.pkl','rb')); tk=F['tk'].copy()
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
sg=np.where(tk.side=='BUY',1,-1)
tk['gross']=sg*tk['size']*(tk.pay-tk.price); tk['fee']=tk['size']*0.05*tk.price*(1-tk.price)
tk['usd']=tk['size']*tk.price
o=tk[tk.wallet!=w]
print('others taker gross',o.gross.sum(),'fees',o.fee.sum(),'usd',o.usd.sum())
by=o.groupby('wallet').agg(g=('gross','sum'),fee=('fee','sum'),usd=('usd','sum'),n=('ts','size')).sort_values('usd',ascending=False)
by['net']=by.g-by.fee
print(by.head(15))
print('n taker wallets',len(by), 'profitable net (usd>1000):', (by[by.usd>1000].net>0).mean())
print(F['meta'].slug.str.replace(r'-game\d+$','',regex=True).nunique(),'events')
