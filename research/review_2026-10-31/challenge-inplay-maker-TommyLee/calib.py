"""Calibration of public taker BUY prints and maker BUY fills (wallet vs others), by price bucket."""
import pickle, numpy as np, pandas as pd
W='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-inplay-maker-TommyLee'
F=pickle.load(open(W+'/frames160.pkl','rb')); tk=F['tk'].copy(); mk=F['mk'].copy()
w='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
bins=np.arange(0,1.01,0.1)
def tab(df,label):
    df=df.copy(); df['b']=pd.cut(df.price,bins)
    g=df.groupby('b',observed=True).apply(lambda x: pd.Series({'n':len(x),'shares':x['size'].sum(),'avgp':np.average(x.price,weights=x['size']),'win':np.average(x.pay,weights=x['size']),'fee':np.average(0.05*x.price*(1-x.price),weights=x['size'])}),include_groups=False)
    g['edge_gross']=g.win-g.avgp; g['edge_net_taker']=g.edge_gross-g.fee
    print('==',label); print(g.round(4))
tab(tk[(tk.side=='BUY')&(tk.wallet!=w)],'others taker BUY prints')
tab(tk[(tk.side=='BUY')&(tk.wallet==w)],'wallet taker BUY')
# maker rows: side is maker's side. maker BUY
tab(mk[(mk.side=='BUY')&(mk.wallet!=w)],'others maker BUY')
tab(mk[(mk.side=='BUY')&(mk.wallet==w)],'wallet maker BUY')
