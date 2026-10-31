import sys, time, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window
AS_OF = 1793318400
W = {'bosona': '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed', 'almach': '0x3725d52f3c252e8374999cc8617292ea2608ad88'}
for name, w in W.items():
    t = time.time()
    win = load_window(w, days=30, as_of=AS_OF)
    tr = win['trades']
    print(name, 'activity', len(win['activity']), 'trades', len(tr), 'markets', len(win['markets']), 'secs', round(time.time()-t,1))
    print(tr.columns.tolist()); print(tr.head(3).to_string())
    act_types = {}
    for r in win['activity']:
        act_types[r.get('type')] = act_types.get(r.get('type'), 0) + 1
    print('activity types', act_types)
    print('sample activity row', win['activity'][100])
    pickle.dump({'trades': tr, 'activity': win['activity'], 'markets': win['markets']}, open(f'win_{name}.pkl', 'wb'))
