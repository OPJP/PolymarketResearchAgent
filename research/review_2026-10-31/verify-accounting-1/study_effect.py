# Rebuild the maker-study passive-buy populations (original vs fixed scan) from the cache copy, offline.
import sys, json, pickle, time
from collections import Counter
sys.path.insert(0, sys.argv[1])
W = sys.argv[1]; duration = sys.argv[2]
import fixed_scan
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.updown_study import load_period, sample_blocks, DAY
from polyrea.workflows.investigate import default_as_of
from polyrea.analysis.updown import maker_buy_prints
as_of = 1793318400; print('as_of', as_of)
fitb = sample_blocks(as_of - 14*DAY, as_of - 7*DAY, 12, 7200, 7)
testb = sample_blocks(as_of - 7*DAY, as_of, 12, 7200, 8)
walks = json.load(open(W + '/walks.json'))
wcids = {w['market'] for w in walks}
res = {}
for label in ('orig', 'fixed'):
    (fixed_scan.install if label == 'fixed' else fixed_scan.uninstall)()
    t = time.time()
    pm = PolymarketData()
    fit = load_period('btc', duration, fitb, pm, with_full_tape=True)
    test = load_period('btc', duration, testb, pm, with_full_tape=True)
    fm = maker_buy_prints(fit['full_tapes'], fit['tapes'], fit['windows'])
    tm = maker_buy_prints(test['full_tapes'], test['tapes'], test['windows'])
    aff_fit = sorted(c for c in fit['full_tapes'] if c in wcids); aff_test = sorted(c for c in test['full_tapes'] if c in wcids)
    print(label, f"{time.time()-t:.0f}s windows fit/test {len(fit['windows'])}/{len(test['windows'])} full rows fit {sum(map(len, fit['full_tapes'].values()))} test {sum(map(len, test['full_tapes'].values()))} passive buys fit {len(fm)} test {len(tm)} affected cids fit {len(aff_fit)} test {len(aff_test)} partial taker tapes {len(fit['partial_tapes'])}/{len(test['partial_tapes'])}")
    res[label] = dict(fm=fm, tm=tm)
    if label == 'orig':
        pickle.dump(dict(fit_spot=fit['spot'], test_spot=test['spot']), open(f"{W}/spot_{duration}.pkl", 'wb'))
pickle.dump({k: (v['fm'], v['tm']) for k, v in res.items()}, open(f"{W}/prints_{duration}.pkl", 'wb'))
wallets = {'0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6':'GoodFallen','0x3048d65321be3497164cdfc2996f94f98a2e7537':'x-MoneyForWhiskas','0x3725d52f3c252e8374999cc8617292ea2608ad88':'almach','0xb55fa1296e6ec55d0ce53d93b9237389f11764d4':'0xb55f','0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed':'bosona','0xc53375ff94e96100f2b30a4b5775db35218d69a9':'dangerously-skip-permissions'}
for per in ('fm', 'tm'):
    a = Counter(res['orig'][per]['wallet']); b = Counter(res['fixed'][per]['wallet'])
    print(per, 'total', len(res['orig'][per]), '->', len(res['fixed'][per]), f"(+{len(res['fixed'][per])-len(res['orig'][per])}, {(len(res['fixed'][per])-len(res['orig'][per]))/len(res['orig'][per]):.3%})")
    for w, n in wallets.items():
        print('   ', n, a[w], '->', b[w])
