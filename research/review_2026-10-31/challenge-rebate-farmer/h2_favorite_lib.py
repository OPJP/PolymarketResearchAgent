import numpy as np
CAP=25.0
def trades(df, T, th, m, spot_filter, exclude_wallet=True):
    d=df[df.up_payout.notna()]
    if exclude_wallet: d=d[d.y==0]
    fee_ps=d.fee_rate*d.price*(1-d.price)
    sel=(d.secs_to_end<=T)&(d.secs_to_end>0)&(d.price>=th)&(d.price<=0.995)
    if spot_filter: sel&=(d.fair_side-d.price-fee_ps>=m)
    s=d[sel].copy()
    if s.empty: return s
    s['usd']=np.minimum(s['size']*s.price,CAP); sh=s.usd/s.price
    pay=np.where(s.is_up,s.up_payout,1-s.up_payout)
    s['fee']=s.fee_rate*s.price*(1-s.price)*sh
    s['pnl']=sh*pay-s.usd-s.fee
    return s
