import pickle, json, time, sys
from polyrea.workflows.investigate import load_window, default_as_of
W=sys.argv[1]
wallet='0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
t0=time.time()
as_of=default_as_of()
print('as_of',as_of)
win=load_window(wallet, days=30, as_of=1793318400)
print('loaded',time.time()-t0, len(win['activity']), len(win['trades']), len(win['markets']))
pickle.dump({'activity':win['activity'],'trades':win['trades'],'markets':win['markets'],'as_of':win['as_of'],'start':win['start']}, open(W+'/window.pkl','wb'))
print(win['trades'].columns.tolist()); print(win['trades'].head())
