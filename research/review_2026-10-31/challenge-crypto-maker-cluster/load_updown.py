# Run with cwd=/home/user/PolymarketResearchAgent (so the repo HTTP cache is used). Writes only to scratch (absolute paths).
import sys, time, pickle
S = '/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-crypto-maker-cluster/'
sys.path.insert(0, S); sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.adapters.polymarket import PolymarketData
from base import frames
AS_OF = 1793318400
dur = sys.argv[1] if len(sys.argv) > 1 else '5m'
pm = PolymarketData()
fitb = sample_blocks(AS_OF - 14 * DAY, AS_OF - 7 * DAY, 12, 7200, 7)
testb = sample_blocks(AS_OF - 7 * DAY, AS_OF, 12, 7200, 8)
out = {}
for nm, b in (('fit', fitb), ('test', testb)):
    t = time.time()
    P = load_period('btc', dur, b, pm, with_full_tape=True)
    T, M = frames(P)
    print(nm, dur, 'windows', len(P['windows']), 'taker rows', len(T), 'passive rows', len(M), 'partial', len(P['partial_tapes']), 'spot', len(P['spot']), 'secs', round(time.time() - t, 1), flush=True)
    out[nm] = {'blocks': b, 'windows': P['windows'], 'T': T, 'M': M, 'partial': P['partial_tapes'], 'spot_ev': P['spot'].event_ts, 'spot_val': P['spot'].values}
pickle.dump(out, open(S + f'updown_btc_{dur}.pkl', 'wb'))
