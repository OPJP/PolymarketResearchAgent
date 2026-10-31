"""Load the frozen 30-day windows (as_of=2026-10-30) from the copied cache and pickle them."""
import _env, os, sys, time, pickle
os.environ.setdefault('POLYREA_OFFLINE', '0')
from polyrea.workflows.investigate import load_window
for name in sys.argv[1:]:
    w = _env.WALLETS[name]
    t = time.time()
    win = load_window(w, days=30, as_of=_env.AS_OF)
    print(name, 'rows', len(win['activity']), 'trades', len(win['trades']), 'markets', len(win['markets']), 'cov', win['activity_coverage'], 'missing', len(win['missing_markets']), f'{time.time()-t:.1f}s', flush=True)
    keep = {k: win[k] for k in ('wallet', 'as_of', 'start', 'activity', 'markets', 'missing_markets')}
    pickle.dump(keep, open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'wb'))
