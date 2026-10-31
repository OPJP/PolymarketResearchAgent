"""Co-trader / leader family: does the wallet buy a token shortly after specific other wallets bought the same token?
Leaders are selected on BUILD only (excess follow rate vs a time-shift null); on VALIDATE the feature is
'a BUILD-selected leader bought this token in [T-60, T-2]' (public tape information)."""
import sys, json, glob
sys.path.insert(0, '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker/code')
import numpy as np, pandas as pd
from features import market_meta
from evalkit import selection_report

CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
OUT = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'
W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
gm = json.load(open(f'{CACHE}/gamma.json'))
F = pd.read_parquet(f'{CACHE}/feats.parquet', columns=['cid', 'ts', 'tok', 'is_wallet', 'period', 'quiet', 'flow60', 'mv30'])
F = F[F.period.isin(['BUILD', 'VALIDATE'])]
F = F[F.groupby('cid').is_wallet.transform('max').astype(bool)].reset_index(drop=True)
cids = set(F.cid.unique())
tp = pd.concat([pd.read_parquet(f, columns=['cid', 'timestamp', 'side', 'asset', 'proxyWallet']) for f in sorted(glob.glob(f'{CACHE}/tapes/chunk*_*.parquet'))])
tp = tp[tp.cid.isin(cids) & (tp.side == 'BUY')].drop_duplicates()
tp['pw'] = tp.proxyWallet.str.lower()
tokmap = {}
for c in cids:
    m = market_meta(gm[c]); tokmap.update({(c, t): i for i, t in enumerate(m['toks'])})
tp['tok'] = [tokmap.get((c, str(a)), -1) for c, a in zip(tp.cid, tp.asset)]
tp = tp[tp.tok >= 0]
per = F.groupby('cid').period.first()
tp['period'] = tp.cid.map(per)
# BUILD: for every other wallet's buy, does OUR wallet buy the same token within (2, 60] s after? vs (2,60] s after a shifted copy
B = tp[tp.period == 'BUILD']
wb = B[B.pw == W]
wkey = {}
for (c, k), g in wb.groupby(['cid', 'tok']):
    wkey[(c, k)] = np.sort(g.timestamp.to_numpy())


def follows(df, shift=0):
    out = np.zeros(len(df), bool)
    for (c, k), idx in df.groupby(['cid', 'tok']).indices.items():
        w = wkey.get((c, k))
        if w is None:
            continue
        t = df.timestamp.to_numpy()[idx] + shift
        j = np.searchsorted(w, t + 2, side='right')
        out[idx] = (j < len(w)) & (w[np.clip(j, 0, len(w) - 1)] <= t + 60)
    return out
O = B[B.pw != W].reset_index(drop=True)
O['fol'] = follows(O)
O['fol_shift'] = follows(O, shift=-900)
L = O.groupby('pw').agg(n=('fol', 'size'), fol=('fol', 'sum'), fol_shift=('fol_shift', 'sum'), mk=('cid', 'nunique'))
L['excess'] = L.fol - L.fol_shift
L = L[(L.n >= 30) & (L.mk >= 10)].sort_values('excess', ascending=False)
L['ratio'] = L.fol / (L.fol_shift + 1)
leaders = L[(L.fol >= 20) & (L.ratio >= 5)].sort_values('excess', ascending=False).index.tolist()[:50]
# asymmetry: our buy within (2,60] s after theirs vs theirs within (2,60] s after ours (same token), top leaders
asym = {}
for pw in leaders[:10]:
    lb = B[B.pw == pw]
    a_after = b_after = 0
    for (c, k), g in lb.groupby(['cid', 'tok']):
        w = wkey.get((c, k))
        if w is None:
            continue
        for t in g.timestamp.to_numpy():
            d = w - t
            a_after += int(((d > 2) & (d <= 60)).sum()); b_after += int(((d < -2) & (d >= -60)).sum())
    asym[pw] = {'ours_after_theirs': a_after, 'theirs_after_ours': b_after}
print('asymmetry', asym)
print('BUILD leader candidates', len(L), 'selected', len(leaders))
print(L.head(12).to_string())
# feature on all prints: a selected leader bought the same token in [T-60, T-2]
lead = tp[tp.pw.isin(leaders)]
lkey = {k: (np.sort(g.timestamp.to_numpy()), g.sort_values('timestamp').pw.to_numpy()) for k, g in lead.groupby(['cid', 'tok'])}
# wallet of each feature row (to exclude the print's own wallet from its leader feature)
F['pw'] = ''
tpk = tp.drop_duplicates(['cid', 'timestamp', 'tok'])[['cid', 'timestamp', 'tok', 'pw']].rename(columns={'timestamp': 'ts'})
F = F.drop(columns=['pw']).merge(tpk, on=['cid', 'ts', 'tok'], how='left')
feat = np.zeros(len(F)); since = np.full(len(F), np.nan)
for (c, k), idx in F.groupby(['cid', 'tok']).indices.items():
    lk = lkey.get((c, k))
    if lk is None:
        continue
    l, lw = lk
    t = F.ts.to_numpy()[idx]; own = F.pw.to_numpy()[idx]
    j = np.searchsorted(l, t - 2, side='right') - 1          # latest leader print <= T-2
    j2 = j - 1                                                # the one before (used when j is the print's own wallet)
    w1 = np.where(j >= 0, lw[np.clip(j, 0, None)], '')
    use = np.where(w1 != own, j, j2)
    dt = np.where(use >= 0, t - l[np.clip(use, 0, None)], np.nan)
    w2 = np.where(use >= 0, lw[np.clip(use, 0, None)], '')
    dt = np.where(w2 == own, np.nan, dt)
    since[idx] = dt
    feat[idx] = (dt >= 2) & (dt <= 60)
F['leader60'] = feat; F['leader_since'] = since
res = {'leaders': leaders, 'leader_table_top': L.head(20).reset_index().to_dict('records')}
for p in ['BUILD', 'VALIDATE']:
    G = F[F.period == p].copy()
    G['score'] = G.leader60 + 0.001 * np.log1p(G.quiet.fillna(1e5).clip(0, 1e5))
    r = selection_report(G); res[p] = r
    res[p]['wallet_share_leader60'] = float(G[G.is_wallet].leader60.mean()); res[p]['others_share_leader60'] = float(G[~G.is_wallet].leader60.mean())
    print(p, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
json.dump(res, open(f'{OUT}/leaders_result.json', 'w'), indent=1, default=float)
F[['cid', 'ts', 'tok', 'is_wallet', 'leader60', 'leader_since']].to_parquet(f'{CACHE}/leader_feat.parquet')
