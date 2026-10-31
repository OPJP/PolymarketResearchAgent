import pickle, sys, json, time
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
from polyrea.workflows.investigate import verify_onchain
OUT='/tmp/claude-0/-home-user-PolymarketResearchAgent/fbff9ea9-e0dd-5fe1-93b9-0952feb8b6ba/scratchpad/wf/challenge-carry-elmcap2/'
W='0xed107a85a4585a381e48c7f7ca4144909e7dd2e5'
d=pickle.load(open(OUT+'win.pkl','rb')); tr=d['win']['trades']
t0=time.time(); r=verify_onchain(W, tr, sample=200, seed=0)
print('seconds', round(time.time()-t0,1)); print({k:v for k,v in r.items() if k!='sources'}); print([s.get('cached') for s in r['sources'][:3]])
# independent second sample, different seed, smaller (network)
r2=verify_onchain(W, tr, sample=40, seed=7)
print('seed7', {k:v for k,v in r2.items() if k not in ('sources','mismatches')})
json.dump(dict(seed0={k:v for k,v in r.items() if k!='sources'}, seed7={k:v for k,v in r2.items() if k!='sources'}), open(OUT+'onchain_recheck.json','w'), indent=1, default=str)
