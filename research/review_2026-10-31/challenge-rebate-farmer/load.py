import sys, time, pickle
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import os; os.chdir('/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window, default_as_of
W='0xb55fa1296e6ec55d0ce53d93b9237389f11764d4'
AS_OF=1793318400
t=time.time()
win=load_window(W, days=30, as_of=AS_OF)
print('loaded', time.time()-t, len(win['activity']), len(win['trades']), len(win['markets']))
out='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-rebate-farmer/win.pkl'
pickle.dump({'activity':win['activity'],'trades':win['trades'],'markets':win['markets'],'as_of':win['as_of'],'start':win['start']}, open(out,'wb'))
print(win['trades'].columns.tolist()); print(win['trades'].head())
