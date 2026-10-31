"""Descriptive (not a decision feature): price path of the bought token after each in-play taker BUY print,
wallet vs other takers in the same markets; plus pre-trade state contrasts. BUILD+VALIDATE (all < H)."""
import sys, json, glob
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd
from features import market_meta

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
gm = json.load(open(f'{CACHE}/gamma.json'))
F = pd.read_parquet(f'{CACHE}/feats.parquet')
PER = sys.argv[1] if len(sys.argv) > 1 else 'BUILD'   # explore on BUILD only
F = F[F.period == PER]
F = F[F.groupby('cid').is_wallet.transform('max').astype(bool)]
tapes = pd.concat([pd.read_parquet(f, columns=['cid', 'timestamp', 'asset', 'price']) for f in sorted(glob.glob(f'{CACHE}/tapes/chunk*_*.parquet'))]).drop_duplicates()
rows = []
TG = dict(tuple(tapes[tapes.cid.isin(F.cid.unique())].groupby('cid')))
for c, g in F.groupby('cid'):
    m = market_meta(gm[c]); t = TG[c].sort_values('timestamp')
    tok = t.asset.astype(str).map({m['toks'][0]: 0, m['toks'][1]: 1}); ok = tok.notna().to_numpy()
    ts = t.timestamp.to_numpy()[ok]; p0 = np.where(tok.to_numpy()[ok] == 0, t.price.to_numpy()[ok], 1 - t.price.to_numpy()[ok])
    q = g.ts.to_numpy(); sgn = np.where(g.tok.to_numpy() == 0, 1, -1)
    r = {'cid': c, 'is_wallet': g.is_wallet.to_numpy(), 'price': g.price.to_numpy(), 'payout': g.payout.to_numpy(),
         'quiet': g.quiet.to_numpy(), 'mv60': g.mv60.to_numpy(), 'mv10': g.mv10.to_numpy(), 'sib_n10': g.sib_n10.to_numpy(),
         'fam': g.fam.to_numpy(), 'smt': g.smt.to_numpy(), 'dp_print': g.dp_print.to_numpy(), 'usd': g.usd.to_numpy(),
         'outcome': g.outcome.to_numpy(), 'minute': g.minute.to_numpy(), 'period': g.period.to_numpy()}
    for dt in (5, 30, 120, 600):
        j = np.searchsorted(ts, q + dt, side='right') - 1
        fut0 = p0[np.clip(j, 0, None)]
        futk = np.where(sgn == 1, fut0, 1 - fut0)
        r[f'mo{dt}'] = futk - g.price.to_numpy()
    rows.append(pd.DataFrame(r))
M = pd.concat(rows, ignore_index=True)
M['mo_res'] = M.payout - M.price
out = {}
for k, g in M.groupby('is_wallet'):
    out['wallet' if k else 'others'] = {c: round(float(g[c].mean()), 4) for c in ['mo5', 'mo30', 'mo120', 'mo600', 'mo_res']}
    out['wallet' if k else 'others'].update({'n': int(len(g)), 'quiet_med': float(g.quiet.median()), 'quiet_ge10': float((g.quiet >= 10).mean()),
                                             'mv60_mean': float(g.mv60.mean()), 'mv10_mean': float(g.mv10.mean()),
                                             'sib_n10_mean': float(g.sib_n10.mean()), 'dp_print_mean': float(g.dp_print.mean()),
                                             'price_mean': float(g.price.mean()), 'usd_med': float(g.usd.median())})
fam = M.groupby(['fam', 'is_wallet']).agg(n=('price', 'size'), mo30=('mo30', 'mean'), mo600=('mo600', 'mean'), mo_res=('mo_res', 'mean'),
                                          quiet_ge10=('quiet', lambda s: (s >= 10).mean())).reset_index()
fam = fam[fam.groupby('fam').n.transform('sum') > 3000]
out['by_fam'] = fam.round(4).to_dict('records')
w = M[M.is_wallet]
out['wallet_mo_res_by_price'] = w.groupby(pd.cut(w.price, [0, .2, .4, .5, .6, .7, .8, .9, 1])).mo_res.agg(['size', 'mean']).round(4).reset_index().astype({'price': str}).to_dict('records')
json.dump(out, open(f'{OUT}/markout_result_{PER}.json', 'w'), indent=1, default=str)
print(json.dumps({k: out[k] for k in ['wallet', 'others']}, indent=0))
print(fam.round(4).to_string())
M.to_parquet(f'{CACHE}/markout_{PER}.parquet')
