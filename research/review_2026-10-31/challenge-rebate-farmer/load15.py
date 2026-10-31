import sys, time, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.adapters.polymarket import PolymarketData
AS_OF=1793318400
dur=sys.argv[1]
fit_b=sample_blocks(AS_OF-14*DAY, AS_OF-7*DAY, 12, 7200, 7)
test_b=sample_blocks(AS_OF-7*DAY, AS_OF, 12, 7200, 8)
pm=PolymarketData()
out={}
for name,b in (('fit',fit_b),('test',test_b)):
    t=time.time()
    p=load_period('btc', dur, b, pm, with_full_tape=True)
    print(name, dur, 'windows', len(p['windows']), 'prints', len(p['prints']), 'partial', len(p['partial_tapes']), 'secs', round(time.time()-t,1), flush=True)
    out[name]={**p, 'blocks':b}
pickle.dump(out, open(f'/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/period_btc_{dur}.pkl','wb'))
