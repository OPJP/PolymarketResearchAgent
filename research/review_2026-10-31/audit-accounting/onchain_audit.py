"""Re-run verify_onchain from cache and extend it: does the matched event also agree on side and USDC?
Also: what does 'confirmed' ignore (side, price), and how is maker share counted?"""
import _env, os, sys, pickle, random, collections, json
import pandas as pd
os.environ['POLYREA_OFFLINE'] = os.environ.get('POLYREA_OFFLINE', '0')
from polyrea.adapters.chain import PolygonChain, decode_fills
from polyrea.analysis.ledger import build_ledger
from polyrea.analysis.profile import resolution_info
from polyrea.workflows.investigate import verify_onchain
for name in sys.argv[1:]:
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    res_ts = {cid: r['closed_ts'] for cid, m in win['markets'].items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
    led = build_ledger(win['wallet'], win['activity'], res_ts)
    tr = pd.DataFrame(led.trades); tr = tr[(tr.ts >= win['start']) & (tr.ts < win['as_of'])].reset_index(drop=True)
    prof = json.load(open(f'/home/user/PolymarketResearchAgent/research/wallets/{win["wallet"]}/profile.json'))['derived']['onchain_verification']
    n = prof['sampled']
    res = verify_onchain(win['wallet'], tr, sample=n)
    print(f'== {name}: re-run confirmed {res["confirmed"]}/{res["sampled"]} maker share {res["maker_fill_share"]:.3f} (profile.json {prof["confirmed"]}/{prof["sampled"]}, {prof["maker_fill_share"]:.3f})')
    groups = tr.groupby(['tx', 'asset']).agg(size=('size', 'sum'), usdc=('usdc', 'sum'), side=('side', 'first'), nside=('side', 'nunique')).reset_index()
    idx = list(range(len(groups))); random.Random(0).shuffle(idx); pick = groups.iloc[idx[:n]]
    rec, _ = PolygonChain().receipts(pick['tx'].tolist())
    w = win['wallet']; side_bad = usdc_bad = mixed = 0; usdc_diff = []
    for _, g in pick.iterrows():
        mine = [f for f in decode_fills(rec[g['tx']]) if f.maker == w and f.token_id == str(g['asset'])]
        sides = {f.side for f in mine}
        if sides != {g['side']}: side_bad += 1
        if g['nside'] > 1: mixed += 1
        cu = sum(f.usdc for f in mine); fee = sum(f.fee for f in mine)
        usdc_diff.append(g['usdc'] - cu)
        if abs(g['usdc'] - cu) > max(0.005 * g['usdc'], 0.02): usdc_bad += 1
    s = pd.Series(usdc_diff)
    print(f'   side mismatches {side_bad}, groups mixing BUY+SELL {mixed}, USDC mismatches >0.5%: {usdc_bad}; API usdc - chain usdc: median {s.median():.4f} max {s.max():.4f} sum {s.sum():.2f}')
