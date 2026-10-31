"""Monthly ROC on peak capital for the H1 (FOMC) and H2 (deadline NO) replicator rules on TEST."""
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
df=pd.read_csv(OUT+'h1_cells.csv')
def X(d):
    e=np.clip(1-d.q0.values,1e-4,1); return np.c_[d.k.values, np.log(e), np.log(e)**2, d.k.values*np.log(e)]
fit=df[~df.test]; tst=df[df.test].copy()
lr=LogisticRegression(C=1.0,max_iter=2000).fit(X(fit),fit.y); tst['s']=lr.predict_proba(X(tst))[:,1]
th=json.load(open(OUT+'h1_backtest2.json'))['threshold']
sel=tst[tst.s>=th].copy(); bid=np.floor(sel.q0*1000)/1000; sel['filled']=sel.qmin<bid-1e-9; sel['bid']=bid
sel=sel[sel.filled]; sel['pnl']=sel.pay_cons/sel.bid-1
per=sel.groupby('key').agg(cells=('pnl','size'),pnl=('pnl','sum'))
peak=per.cells.max(); months=10  # Jan-Oct 2026 TEST span
print(per.to_string()); print('H1 replicator: total pnl per $1/cell', per.pnl.sum(), 'peak capital (cells)', peak, 'avg monthly ROC on peak', per.pnl.sum()/peak/months, 'best 30d window ROC', per.pnl.max()/peak)
b=pd.read_csv(OUT+'h2_bt_maker_TEST.csv'); bf=pd.read_csv(OUT+'h2_bt_maker_FIT.csv')
for nm,x in [('TEST',b),('FIT',bf)]:
    g=x.groupby('key').agg(n=('ret','size'),pnl=('ret','sum'))
    print('H2', nm, g.to_string(), 'ROC per deadline on capital deployed', (g.pnl/g.n).round(4).tolist())
json.dump(dict(h1_per_meeting=per.reset_index().to_dict('records'), h1_peak_cells=int(peak), h1_avg_monthly_roc=float(per.pnl.sum()/peak/months), h1_best_window_roc=float(per.pnl.max()/peak)), open(OUT+'replicator_roc.json','w'), indent=1)
