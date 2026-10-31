import sys, json, pickle, time
import numpy as np, pandas as pd
W, duration = sys.argv[1], sys.argv[2]
wallets = sys.argv[3].split(',')
from polyrea.analysis.updown import SpotIndex, match_test
from polyrea.pit import TimeSeries
from polyrea.stats.significance import hac_t_test
sp = pickle.load(open(f"{W}/spot_{duration}.pkl", 'rb'))
ev = np.concatenate([sp['fit_spot'].event_ts, sp['test_spot'].event_ts]); vals = np.concatenate([sp['fit_spot'].values, sp['test_spot'].values])
o = np.argsort(ev, kind='stable')
spot = SpotIndex(TimeSeries.build(sp['fit_spot'].name, zip(ev[o].tolist(), vals[o].tolist()), availability_lag=1))
prints = pickle.load(open(f"{W}/prints_{duration}.pkl", 'rb'))
def replay(tm, w):
    mine = tm[tm['wallet'] == w]
    if not len(mine): return {}
    payout = np.where(mine['is_up'], mine['up_payout'], 1 - mine['up_payout'])
    pnl = mine['size'] * (payout - mine['price'])
    per_w = pd.Series(pnl.to_numpy(), index=mine['condition_id']).groupby(level=0).sum()
    return dict(fills=int(len(mine)), pnl=round(float(pnl.sum()),2), ret=round(float(pnl.sum()/(mine['size']*mine['price']).sum()),5), p=round(hac_t_test(per_w.to_numpy()).p_value,4))
for w in wallets:
    rec = json.load(open(f"research/wallets/{w}/updown_maker_study_btc_{duration}.json"))
    rm = rec['derived']['match_test']; rr = rec['derived']['wallet_maker_replay_test_period']
    print(w[:10], duration, 'RECORDED lat', rm['chosen_latency_s'], 'auc %.4f perm_p %.4f mcc %.5f' % (rm['test']['auc'], rm['test']['auc_perm_p'], rm['test']['decision']['mcc']), 'replay', {k: rr.get(k) for k in ('fills','pnl','return','per_window_p')})
    for label in ('orig', 'fixed'):
        fm, tm = prints[label]
        t = time.time()
        mt = match_test(fm, tm, w, spot, n_perm=200, seed=7)
        print('   ', label.ljust(5), 'lat', mt['chosen_latency_s'], 'auc %.4f perm_p %.4f mcc %.5f' % (mt['test']['auc'], mt['test']['auc_perm_p'], mt['test']['decision']['mcc']), 'replay', replay(tm, w), f"{time.time()-t:.0f}s", flush=True)
