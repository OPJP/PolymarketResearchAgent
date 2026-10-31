"""Iteration 8: verification of panel iter7 A3 rung-shift check (scratchpad p7/rungshift.py) on 10-31 14:06-16:30 UTC (own raw recorder extract)."""
# level law vs shift law for the exact-500 rungs (development raw book, 10-31 16:00-16:30 UTC, Up-token book; side 1 = Up bids, side 0 = Up asks = Down bids mirrored)
import pandas as pd, numpy as np
e=pd.read_parquet('.cache/re/directional-maker/it6/ev_1793455600_1793464202.parquet')
e=e.sort_values('s',kind='stable').reset_index(drop=True)
e['mid']=(e.bb+e.ba)/2
res=[]
for (w,sd),g in e.groupby(['w','side']):
    g=g[(g.d.round(2).abs()==500)]
    # orient: price of a bid on "this side's token": side1 -> Up bid p ; side0 -> Down bid 1-p, mid -> Down mid 1-mid
    if sd==0: P=1-g.p.values; M=1-g.mid.values
    else: P=g.p.values; M=g.mid.values
    S=g.s.values; D=g.d.values
    last_add={}  # price -> (time, mid) of latest +500 at that price
    for i in range(len(g)):
        if D[i]>0:
            last_add[round(P[i],2)]=(S[i],M[i])
        else:
            # removal: find an add within 20 ms after at a different price
            j=i+1
            while j<len(g) and S[j]-S[i]<=20:
                if D[j]>0 and abs(P[j]-P[i])>0.004:
                    po=round(P[i],2)
                    if po in last_add:
                        t0,m0=last_add[po]
                        res.append(dict(w=w,side=sd,age=S[i]-t0,dp=P[j]-P[i],dmid=M[j]-m0,off_old=P[i]-m0,off_new=P[j]-M[j],mid_now=M[j],touchdist_new=P[j]-M[j]))
                    break
                j+=1
r=pd.DataFrame(res)
r=r[(r.age>0)&(r.age<10000)]
print('moves',len(r),'median age ms',r.age.median())
print('corr(off_old, off_new) =',round(np.corrcoef(r.off_old,r.off_new)[0,1],3))
print('corr(dp, dmid since old post) =',round(np.corrcoef(r.dp,r.dmid)[0,1],3))
# shift law: dp == dmid rounded to tick?  level law: off_new independent of off_old
r['shift_err']=(r.dp-r.dmid).round(3)
print('share |dp - dmid| <= 0.005:',round((r.shift_err.abs()<=0.005).mean(),3),' <= 0.0105:',round((r.shift_err.abs()<=0.0105).mean(),3))
r['lvl_err']=(r.off_new-r.off_new.median())
print('share |off_new - median off| <= 0.0105:',round((r.lvl_err.abs()<=0.0105).mean(),3))
# regress dp on dmid
b=np.polyfit(r.dmid,r.dp,1); print('dp = %.3f*dmid + %.4f'%tuple(b))
# persistence by off_old quintile
r['q']=pd.qcut(r.off_old,5,labels=False,duplicates='drop')
print(r.groupby('q').agg(off_old=('off_old','median'),off_new=('off_new','median'),n=('dp','size')).round(3))
# null: shuffle off_old within market-minute
r['min']=(r.mid_now*0+1)
# refinement: remove common slow drivers (time left, regime) by demeaning within (market, side, 5-s bucket)
r2=[]
import collections
# recompute with move time

# iteration 8 addition: is the step tied to the Chainlink change since the old post (the move law of A3 step 2)?
import sys as _sys
_sys.path.insert(0, 'research/reverse_engineering/directional-maker/code5'); _sys.path.insert(0, 'research/reverse_engineering/directional-maker/code6')
from pres_live import load_ref
fu, cl, tw = load_ref(1793455600, 1793464202)
cls = np.array(sorted(cl)); clv = np.array([cl[k] for k in cls])
fs, fm = fu.s.to_numpy(np.int64), fu.m.to_numpy()
res2 = []
for (w, sd), g in e.groupby(['w', 'side']):
    g = g[(g.d.round(2).abs() == 500)]
    P = 1 - g.p.values if sd == 0 else g.p.values
    S = g.s.values; D = g.d.values
    last_add = {}
    for i in range(len(g)):
        if D[i] > 0:
            last_add[round(P[i], 2)] = S[i]
        else:
            j = i + 1
            while j < len(g) and S[j] - S[i] <= 20:
                if D[j] > 0 and abs(P[j] - P[i]) > 0.004:
                    po = round(P[i], 2)
                    if po in last_add and 0 < S[i] - last_add[po] < 10000:
                        t0, t1 = last_add[po], S[j]
                        k0 = np.searchsorted(cls, (t0 - 1432) // 1000, side='right') - 1
                        k1 = np.searchsorted(cls, (t1 - 1432) // 1000, side='right') - 1
                        f0 = fm[max(np.searchsorted(fs, t0, side='right') - 1, 0)]
                        f1 = fm[max(np.searchsorted(fs, t1, side='right') - 1, 0)]
                        sg = 1 if sd == 1 else -1
                        res2.append(dict(dp=P[j] - P[i], dcl=(clv[k1] - clv[k0]) * sg if k0 >= 0 and k1 >= 0 else np.nan, dfut=(f1 - f0) * sg))
                    break
                j += 1
r2 = pd.DataFrame(res2).dropna()
print('moves with CL', len(r2))
print('corr(dp, dCL since old post, signed to the token)', round(float(np.corrcoef(r2.dp, r2.dcl)[0, 1]), 3))
print('corr(dp, dfutures since old post)', round(float(np.corrcoef(r2.dp, r2.dfut)[0, 1]), 3))
print('share dp>0', round(float((r2.dp > 0).mean()), 3))
print('dp>0 share when dCL>+5:', round(float((r2.dp[r2.dcl > 5] > 0).mean()), 3), ' when dCL<-5:', round(float((r2.dp[r2.dcl < -5] > 0).mean()), 3), ' when |dCL|<=1:', round(float((r2.dp[r2.dcl.abs() <= 1] > 0).mean()), 3))
