import pickle, sys, pandas as pd
W = sys.argv[1]
ws = {'0x3725d52f3c252e8374999cc8617292ea2608ad88':'almach','0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed':'bosona','0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6':'GoodFallen','0x3048d65321be3497164cdfc2996f94f98a2e7537':'xMFW','0xc53375ff94e96100f2b30a4b5775db35218d69a9':'DSP','0xb55fa1296e6ec55d0ce53d93b9237389f11764d4':'0xb55f'}
for d in ('5m','15m'):
    p = pickle.load(open(f"{W}/prints_{d}.pkl",'rb'))
    for i, per in enumerate(('fit','test')):
        o, f = p['orig'][i], p['fixed'][i]
        key = ['condition_id','ts','wallet','is_up','price','size']
        oc = o[key].value_counts(); fc = f[key].value_counts()
        diff = (fc.sub(oc, fill_value=0)); diff = diff[diff > 0].reset_index()
        sub = diff[diff['wallet'].isin(ws)]
        if len(sub):
            sub = sub.assign(name=sub['wallet'].map(ws), cid=sub['condition_id'].str[:10]).drop(columns=['wallet','condition_id'])
            m = f.drop_duplicates('condition_id').set_index('condition_id')['up_payout']
            print(d, per); print(sub.to_string(index=False))
