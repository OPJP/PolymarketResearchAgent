"""X139 (mechanics panel iter-9 P4): one quote function across receivers? Event feed vs price feed.

Development on-chain record 16-22 Oct (calldata_pub + calldata_all). Messages = P4e taker signings merged within 50 ms
per event. Receivers' FAK BUY limits on the SAME token signed in [-100, +900] ms of the message: P4e, the wallet,
0x2005d16a, the slow trio, group G (v5 json). Common public input = the last public print on the token before the
message (wallet prints and txs where it is the maker excluded). premium = limit - last print (cents).
ICC(1) of premiums after receiver fixed effects (BUILD medians), messages with >= 2 receivers; the same for the raw
limits (which share the price level trivially). Price feed predicts ICC >= 0.8 beyond the print; event feed <= 0.4.
Also: within-message spread (max - min of fixed-effect-adjusted premiums) and agreement within 1c.
Output: results/receiver_icc.json
"""
import glob, json
import numpy as np, pandas as pd

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/receiver_icc.json'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
P4E = '0x4ebc2722adc772bde8680792d0a6fdf15499a33d'
VAL0, H = 1792540800, 1792713600
v5 = json.load(open('research/reverse_engineering/tommy-cs2-maker/code/final_rule_v5_groupP.json'))
REC = {P4E: 'P4e', W: 'wallet'}
for a in v5['members']:
    REC.setdefault(a.lower(), a.lower()[:10])
for a in v5['group_G']:
    REC.setdefault(a.lower(), 'G_' + a.lower()[:10])

cols = ['tx', 'idx', 'maker', 'side', 'token_id', 'price', 'sign_ms', 'condition_id']
P = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(f'{ROOT}/calldata_pub/*.parquet'))])
C = pd.read_parquet(f'{ROOT}/calldata_all.parquet', columns=cols + ['event', 'gs_ts'])
ev = C.dropna(subset=['event']).drop_duplicates('condition_id').set_index('condition_id').event.to_dict()
gs_of = C.dropna(subset=['event']).groupby('event').gs_ts.min().to_dict()
D = pd.concat([P, C.drop(columns=['event', 'gs_ts'])]).drop_duplicates(['tx', 'idx'])
D['maker'] = D.maker.str.lower(); D['ev'] = D.condition_id.map(ev)
D = D.dropna(subset=['ev'])
D = D[(D.sign_ms > 1.79e12) & (D.sign_ms < H * 1000)]
T = D[(D.idx == -1) & (D.side == 0) & D.maker.isin(REC)].drop_duplicates('tx').copy()
T['rec'] = T.maker.map(REC)
T = T.sort_values(['ev', 'sign_ms'])

f = pd.read_parquet(f'{ROOT}/chain_fills_1792108800_1792713600.parquet', columns=['tx', 'role'])
maker_tx = set(f[f.role == 'maker'].tx)
o = pd.read_parquet(f'{ROOT}/orders.parquet', columns=['token_id', 'cid', 'oi']).drop_duplicates('token_id').set_index('token_id')
tapes = {}


def last_print(cid, tok_oi, t_ms):
    d = tapes.get(cid)
    if d is None:
        fs = glob.glob(f'{ROOT}/tapes/{cid}_tkw.parquet')
        if not fs:
            tapes[cid] = False; return np.nan
        d = pd.read_parquet(fs[0])
        d = d[(d.proxyWallet.str.lower() != W) & (~d.transactionHash.isin(maker_tx))].sort_values('timestamp')
        d = (d.timestamp.to_numpy(float), np.where(d.outcomeIndex.astype(int) == 0, d.price.astype(float), 1 - d.price.astype(float)))
        tapes[cid] = d
    if d is False:
        return np.nan
    ts, p0 = d
    k = np.searchsorted(ts, t_ms / 1000, side='left')
    if k == 0:
        return np.nan
    v = p0[k - 1]
    return v if tok_oi == 0 else 1 - v

rows = []
p4 = T[T.rec == 'P4e']
for e, g in p4.groupby('ev'):
    t = g.sign_ms.to_numpy(float)
    keep = np.r_[True, np.diff(t) > 50]
    for r in g[keep].itertuples():
        w = T[(T.ev == e) & (T.token_id == r.token_id) & (T.sign_ms >= r.sign_ms - 100) & (T.sign_ms <= r.sign_ms + 900)]
        w = w.drop_duplicates('rec')
        if len(w) < 2:
            continue
        if r.token_id not in o.index:
            continue
        cid, oi = o.loc[r.token_id, 'cid'], int(o.loc[r.token_id, 'oi'])
        lp = last_print(cid, oi, r.sign_ms)
        if not np.isfinite(lp):
            continue
        for x in w.itertuples():
            rows.append({'msg': f'{e}|{r.sign_ms}', 'rec': x.rec, 'L': x.price, 'lp': lp, 'gs': gs_of.get(e, 0), 'lag': x.sign_ms - r.sign_ms})
R = pd.DataFrame(rows)
R['prem'] = (R.L - R.lp) * 100
fe = R[R.gs < VAL0].groupby('rec').prem.median()
R['adj'] = R.prem - R.rec.map(fe).fillna(R.prem.median())


def icc1(df, col):
    g = df.groupby('msg')[col]
    n_i = g.size(); k = n_i[n_i >= 2]
    df = df[df.msg.isin(k.index)]
    g = df.groupby('msg')[col]
    N = len(df); a = g.ngroups
    grand = df[col].mean()
    msb = (g.size() * (g.mean() - grand) ** 2).sum() / (a - 1)
    msw = ((df[col] - g.transform('mean')) ** 2).sum() / (N - a)
    n0 = (N - (g.size() ** 2).sum() / N) / (a - 1)
    return round(float((msb - msw) / (msb + (n0 - 1) * msw)), 3), int(a), int(N)

res = {'receivers_rows': R.rec.value_counts().to_dict(), 'fe_build_premium_c': {k: round(float(v), 2) for k, v in fe.items()}}
for sp, sel in (('BUILD', R.gs < VAL0), ('VALIDATE', R.gs >= VAL0), ('ALL', R.gs > 0)):
    y = R[sel]
    sp_ = y.groupby('msg').adj.agg(lambda s: s.max() - s.min())
    res[sp] = {'icc_raw_limit': icc1(y.assign(Lc=y.L * 100), 'Lc'), 'icc_premium': icc1(y, 'prem'), 'icc_premium_fe_adjusted': icc1(y, 'adj'),
               'within_msg_spread_adj_c_p50_p90': [round(float(sp_.median()), 2), round(float(sp_.quantile(0.9)), 2)],
               'share_msgs_all_within_1c_adj': round(float((sp_ <= 1.01).mean()), 3),
               'premium_sd_c': round(float(y.prem.std()), 2)}
    # wallet vs others on the same message
    wv = y[y.rec == 'wallet'].set_index('msg').adj
    ov = y[y.rec != 'wallet'].groupby('msg').adj.mean()
    j = pd.concat([wv, ov], axis=1, keys=['w', 'o']).dropna()
    if len(j) >= 5:
        res[sp]['wallet_vs_others_adj_corr'] = [round(float(np.corrcoef(j.w, j.o)[0, 1]), 3), int(len(j))]
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
