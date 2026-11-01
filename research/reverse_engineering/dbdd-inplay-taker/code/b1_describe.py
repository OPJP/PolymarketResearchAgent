"""B1 first look: the wallet's taker orders from calldata (limit price, order size, fill ratio, signing latency,
age of the maker quotes it hits, fingerprint fields). Development units only."""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE
import pandas as pd, numpy as np

gm = json.load(open(f'{CACHE}/gamma2.json'))
act = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/activity/*.parquet')])
act = act[act.conditionId.map(lambda c: (gm.get(c) or {}).get('sealed', 1) == 0)]
tk = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/calldata/taker_*.parquet')])
mk = pd.concat([pd.read_parquet(f) for f in glob.glob(f'{CACHE}/calldata/maker_*.parquet')])
tk = tk[tk.ok == 1]
a1 = act.drop_duplicates('transactionHash')[['transactionHash', 'timestamp', 'price', 'size', 'usdcSize', 'conditionId', 'slug', 'eventSlug', 'outcome']]
d = tk.merge(a1, left_on='tx', right_on='transactionHash', how='inner')
print('orders decoded', len(tk), 'joined dev', len(d))
print('wallet is taker-order maker:', d.is_wallet_taker.mean().round(4), 'sides', d.t_side.value_counts().to_dict(), 'sigtype', d.t_sigtype.value_counts().to_dict())
print('signers', d.t_signer.value_counts().head(3).to_dict())
print('builder nonzero', (d.t_builder.str.strip('0') != '').mean().round(4), 'metadata nonzero', (d.t_meta.str.strip('0') != '').mean().round(4))
lat = d.timestamp - d.t_ts_ms / 1000.0
print('block_ts - signing (s): q', np.round(np.nanquantile(lat, [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]), 2), 'neg share', (lat < -1).mean().round(4))
# order amounts
buy = d[d.t_side == 0]
u = buy.t_usdc
print('order USDC quantiles', np.round(np.quantile(u, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99]), 2))
print('top order USDC values', u.round(2).value_counts().head(15).to_dict())
print('share integer USDC', (np.abs(u - u.round()) < 1e-6).mean().round(3), 'share integer shares (t_sh)', (np.abs(buy.t_sh - buy.t_sh.round()) < 1e-6).mean().round(3))
# limit vs fill
fr = buy.t_fill / buy.t_usdc
print('fill ratio (filled USDC / order USDC) q', np.round(np.quantile(fr, [0.1, 0.25, 0.5, 0.75, 0.9]), 3), 'full fill share', (fr > 0.999).mean().round(3))
slip = buy.t_px - buy.price
print('limit minus avg fill price q', np.round(np.quantile(slip, [0.05, 0.25, 0.5, 0.75, 0.95]), 4), 'limit==fill (<0.0015)', (np.abs(slip) < 0.0015).mean().round(3))
lp = buy.t_px
print('limit price on 0.01 grid', (np.abs(lp * 100 - np.round(lp * 100)) < 0.02).mean().round(3), 'on 0.001 grid', (np.abs(lp * 1000 - np.round(lp * 1000)) < 0.02).mean().round(3))
# salts
s = buy.t_salt.astype(float)
print('salt log10 q', np.round(np.quantile(np.log10(s + 1), [0.01, 0.5, 0.99]), 2))
# makers hit
m = mk.merge(d[['tx', 'timestamp', 't_token']], on='tx')
m['age'] = m.timestamp - m.m_ts_ms / 1000.0
print('maker orders per fill q', np.round(np.quantile(d.n_makers, [0.5, 0.9, 0.99]), 1))
print('age of maker quotes hit (s) q', np.round(np.nanquantile(m.age, [0.1, 0.25, 0.5, 0.75, 0.9]), 1))
print('maker side', m.m_side.value_counts().to_dict(), 'maker token == taker token', (m.m_token == m.t_token).mean().round(3))
print('top maker wallets', m.m_maker.value_counts().head(8).to_dict(), 'distinct', m.m_maker.nunique())
