"""B1 over all decoded wallet orders (development units only): order type, limit vs fill, stake, latency,
quotes hit, fingerprint, and the stake-vs-edge test (size component). Writes results/iter2_b1.json."""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import pandas as pd, numpy as np
from scipy import stats

WS = os.path.join(ROOT, 'research', 'reverse_engineering', 'dbdd-inplay-taker')
W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
H = 1792713600
gm = json.load(open(f'{CACHE}/gamma2.json'))
act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
act = act[act.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
tk = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/calldata/taker_*.parquet')])
mk = pd.concat([pd.read_parquet(f, columns=['tx', 'm_maker', 'm_side', 'm_px', 'm_sh', 'm_ts_ms', 'm_fill']) for f in glob.glob(f'{CACHE}/calldata/maker_*.parquet')])
tk = tk[tk.ok == 1]
a1 = act.drop_duplicates('transactionHash')
d = tk.merge(a1[['transactionHash', 'timestamp', 'price', 'size', 'usdcSize', 'conditionId', 'slug', 'eventSlug', 'outcome', 'outcomeIndex']],
             left_on='tx', right_on='transactionHash', how='inner')


def fam(slug):
    p = (slug or '').split('-')[0]
    if p in ('cs2', 'csgo'):
        return 'cs2'
    if p in ('dota2', 'lol', 'val', 'mlbb', 'ow', 'r6', 'cod'):
        return 'esports'
    if p in ('atp', 'wta', 'itf', 'challenger') or 'tennis' in p:
        return 'tennis'
    if p in ('nba', 'nfl', 'mlb', 'nhl', 'cfb', 'cbb', 'wnba', 'mls'):
        return 'us'
    return 'soccer_other'


d['fam'] = d.slug.map(fam)
d['unit'] = d.conditionId.map(lambda c: gm[c]['unit_ts'])
d['period'] = np.where(d.unit < 1791849600, 'BUILD', np.where(d.unit < H, 'VALIDATE', 'POST_T0_DEV'))
res = {'n_orders': int(len(d)), 'by_period': d.period.value_counts().to_dict()}
res['taker_order_is_wallet'] = float(d.is_wallet_taker.mean())
res['side_buy_share'] = float((d.t_side == 0).mean())
res['sigtype'] = {str(k): int(v) for k, v in d.t_sigtype.value_counts().items()}
res['signers'] = d.t_signer.value_counts().head(3).to_dict()
res['builder_nonzero_share'] = float((d.t_builder.str.strip('0') != '').mean())
res['metadata_nonzero_share'] = float((d.t_meta.str.strip('0') != '').mean())
lat = d.timestamp - d.t_ts_ms / 1000.0
res['block_minus_sign_s_q'] = {str(q): float(np.quantile(lat, q)) for q in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99)}
res['sign_after_block_share'] = float((lat < 0).mean())
u = d.t_usdc
res['order_usdc_q'] = {str(q): float(np.quantile(u, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)}
res['order_usdc_integer_share'] = float((np.abs(u - u.round()) < 1e-6).mean())
res['order_usdc_top'] = {str(k): int(v) for k, v in u.round(2).value_counts().head(20).items()}
fr = d.t_fill / d.t_usdc
res['fill_ratio_q'] = {str(q): float(np.quantile(fr, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
res['full_fill_share'] = float((fr > 0.999).mean())
slip = d.t_px - d.price
res['limit_minus_avgfill_q'] = {str(q): float(np.quantile(slip, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
res['limit_eq_avgfill_share'] = float((np.abs(slip) < 0.0015).mean())
res['limit_on_cent_grid_share'] = float((np.abs(d.t_px * 100 - np.round(d.t_px * 100)) < 0.02).mean())
s = d.t_salt.astype(float)
res['salt_log10_q'] = {str(q): float(np.quantile(np.log10(s + 1), q)) for q in (0.01, 0.5, 0.99)}
res['hour_utc_share'] = {str(k): float(v) for k, v in (pd.to_datetime(d.t_ts_ms, unit='ms').dt.hour.value_counts(normalize=True).sort_index()).items()}
res['ms_mod_1000_uniform_ks_p'] = float(stats.kstest((d.t_ts_ms % 1000) / 1000.0, 'uniform').pvalue)
res['sec_mod_10_share'] = {str(k): float(v) for k, v in ((d.t_ts_ms // 1000) % 10).value_counts(normalize=True).sort_index().items()}
# quotes hit
m = mk.merge(d[['tx', 'timestamp', 't_ts_ms', 'fam', 'period']], on='tx')
m['age_block'] = m.timestamp - m.m_ts_ms / 1000.0
m['age_sign'] = (m.t_ts_ms - m.m_ts_ms) / 1000.0
res['makers_per_fill_q'] = {str(q): float(np.quantile(d.n_makers, q)) for q in (0.5, 0.9, 0.99)}
res['quote_age_at_block_q'] = {str(q): float(np.nanquantile(m.age_block, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
res['quote_signed_after_wallet_signed_share'] = float((m.age_sign < 0).mean())
res['maker_distinct'] = int(m.m_maker.nunique())
res['maker_top10_share_of_rows'] = float(m.m_maker.value_counts().head(10).sum() / len(m))
res['self_match_rows'] = int((m.m_maker.str.lower() == W).sum())
res['maker_signer_eq_wallet_signer'] = 0
# per family
pf = {}
for f_, g in d.groupby('fam'):
    pf[f_] = {'n': int(len(g)), 'usdc_med': float(g.t_usdc.median()), 'fill_ratio_med': float((g.t_fill / g.t_usdc).median()),
              'limit_eq_fill': float((np.abs(g.t_px - g.price) < 0.0015).mean()),
              'latency_med': float((g.timestamp - g.t_ts_ms / 1000).median())}
res['by_family'] = pf
# stake vs edge (size component): realized edge = payout - fill price, for resolved development units
pay = {}
for c, mm in gm.items():
    if mm.get('sealed', 1):
        continue
    op = mm.get('outcomePrices')
    try:
        op = json.loads(op) if isinstance(op, str) else op
        op = [float(x) for x in op]
    except Exception:
        continue
    if len(op) == 2 and max(op) > 0.99:
        pay[c] = op
d['payout'] = [pay[c][int(i)] if c in pay else np.nan for c, i in zip(d.conditionId, d.outcomeIndex)]
e = d[d.payout.notna()].copy()
e['edge'] = e.payout - e.price
e['lstake'] = np.log(e.t_usdc)
qs = pd.qcut(e.t_usdc.rank(method='first'), 5, labels=False)
res['stake_quintile_edge'] = {str(int(k)): {'usdc_med': float(g.t_usdc.median()), 'mean_edge': float(g.edge.mean()),
                                         'n': int(len(g)), 'roi': float((g.payout * g.t_fill / g.price - g.t_fill).sum() / g.t_fill.sum())}
                              for k, g in e.groupby(qs)}
res['spearman_stake_edge'] = float(stats.spearmanr(e.t_usdc, e.edge).correlation)
res['spearman_stake_price'] = float(stats.spearmanr(e.t_usdc, e.price).correlation)
# stake vs price within family
res['stake_by_price_bin'] = {str(k): float(g.t_usdc.median()) for k, g in e.groupby(pd.cut(e.price, [0, .2, .4, .6, .8, 1]), observed=True)}
json.dump(res, open(os.path.join(WS, 'results', 'iter2_b1.json'), 'w'), indent=1, default=str)
for k, v in res.items():
    if k not in ('hour_utc_share', 'order_usdc_top', 'sec_mod_10_share'):
        print(k, v)
d[['tx', 'timestamp', 't_ts_ms', 't_px', 't_usdc', 't_fill', 'price', 'size', 'conditionId', 'outcomeIndex', 'slug', 'eventSlug',
   'fam', 'period', 'unit', 'payout']].to_parquet(f'{CACHE}/orders.parquet')
