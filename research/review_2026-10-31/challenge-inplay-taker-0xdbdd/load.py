import pickle, time, sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import load_window
W='0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
AS_OF=1793318400
t0=time.time()
win=load_window(W, days=30, as_of=AS_OF)
print('loaded', time.time()-t0, len(win['activity']), win['trades'].shape, len(win['markets']))
pickle.dump({'trades':win['trades'],'markets':win['markets'],'activity':win['activity']}, open(sys.argv[1],'wb'))
