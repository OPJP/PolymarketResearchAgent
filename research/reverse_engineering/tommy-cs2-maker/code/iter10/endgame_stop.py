"""X141 (assumptions panel iter-9 P2), step 1: the exit band and the endgame on the eventual loser (16-22 Oct, dev).

(1) Band: share of the wallet's maker / taker orders outside [0.05, 0.95] vs every public maker BUY order in the same
    markets (calldata_pub).
(2) Endgame, per market: the loser's public price path (public taker prints on the loser token, wallet prints and txs
    where it is the maker excluded): first times at or below 0.25 / 0.10 / 0.05. The wallet's maker fills on the
    loser: last fill time and price, share of loser-token maker shares bought at or below 0.10, and fills after the
    public 0.10 crossing. Other makers on the loser: from the public prints after the 0.10 crossing (counter-check of
    whether the wallet stops earlier or later than the public ladder).
(3) The unpaired residual: per-market residual value = PnL - locked margin (pairs x (1 - pair cost)); its correlation
    with PnL, and with the loser-token shares the wallet bought after the public 0.10 crossing.
Output: results/endgame_stop.json
"""
import glob, json
import numpy as np, pandas as pd
from scipy import stats

ROOT = '.cache/re/tommy-cs2-maker'
OUT = 'research/reverse_engineering/tommy-cs2-maker/results/endgame_stop.json'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
VAL0, H = 1792540800, 1792713600

pm = pd.read_parquet(f'{ROOT}/per_market.parquet').set_index('cid')
o = pd.read_parquet(f'{ROOT}/orders.parquet')
tok = o.drop_duplicates('token_id').set_index('token_id')[['cid', 'oi']]
f = pd.read_parquet(f'{ROOT}/chain_fills_1792108800_1792713600.parquet')
f = f[f.bts < H].merge(tok, left_on='token_id', right_index=True, how='left')
f = f[f.cid.isin(pm.index)]
f['px'] = f.usdc / f.shares
maker_tx = set(f[f.role == 'maker'].tx)
rows = []
for cid, r in pm.iterrows():
    los = 1 - int(r.win)
    fs = glob.glob(f'{ROOT}/tapes/{cid}_tkw.parquet')
    if not fs:
        continue
    d = pd.read_parquet(fs[0])
    d = d[(d.proxyWallet.str.lower() != W) & (~d.transactionHash.isin(maker_tx))].sort_values('timestamp')
    if d.empty:
        continue
    pl = np.where(d.outcomeIndex.astype(int) == los, d.price.astype(float), 1 - d.price.astype(float))
    ts = d.timestamp.to_numpy(float)
    after_gs = ts >= r.gs
    def first_le(x):
        k = np.where(after_gs & (pl <= x + 1e-9))[0]
        return float(ts[k[0]]) if len(k) else np.nan
    t25, t10, t05 = first_le(0.25), first_le(0.10), first_le(0.05)
    t_end = float(ts[-1])
    wl = f[(f.cid == cid) & (f.oi == los) & (f.role == 'maker')]
    ww = f[(f.cid == cid) & (f.oi == int(r.win)) & (f.role == 'maker')]
    rec = {'cid': cid, 'gs': r.gs, 'val': r.gs >= VAL0, 'pnl': r.pnl, 'pairs': r.pairs, 'pc': r.pair_cost,
           'margin': r.pairs * (1 - r.pair_cost), 't25': t25, 't10': t10, 't05': t05, 't_end': t_end,
           'min_print_loser': float(pl[after_gs].min()) if after_gs.any() else np.nan}
    if len(wl):
        rec.update({'w_last_t': float(wl.bts.max()), 'w_last_px': float(wl.sort_values('bts').px.iloc[-1]),
                    'w_min_px': float(wl.px.min()), 'w_sh': float(wl.shares.sum()),
                    'w_sh_le10': float(wl.shares[wl.px <= 0.10 + 1e-9].sum()),
                    'w_usd_after_t10': float(wl.usdc[wl.bts >= t10].sum()) if np.isfinite(t10) else 0.0,
                    'w_sh_after_t10': float(wl.shares[wl.bts >= t10].sum()) if np.isfinite(t10) else 0.0,
                    'w_sh_after_t25': float(wl.shares[wl.bts >= t25].sum()) if np.isfinite(t25) else 0.0})
    # public BUY prints on the loser after the 0.10 crossing (other buyers of the collapsing team)
    if np.isfinite(t10):
        m = (ts >= t10) & (d.side.to_numpy() == 'BUY') & (d.outcomeIndex.astype(int).to_numpy() == los)
        rec['pub_buy_sh_after_t10'] = float(d['size'].to_numpy(float)[m].sum())
    rows.append(rec)
X = pd.DataFrame(rows)
X['resid'] = X.pnl - X.margin


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    k = np.isfinite(a) & np.isfinite(b)
    if k.sum() < 5:
        return None
    return [round(float(stats.pearsonr(a[k], b[k])[0]), 3), round(float(stats.spearmanr(a[k], b[k])[0]), 3), int(k.sum())]

res = {}
for sp, sel in (('BUILD', ~X.val), ('VALIDATE', X.val)):
    y = X[sel]
    w = y.dropna(subset=['w_last_t'])
    r = {'markets': int(len(y)), 'with_loser_maker_fills': int(len(w)),
         'loser_public_reaches_0.10': round(float(np.isfinite(y.t10).mean()), 3),
         'loser_public_reaches_0.05': round(float(np.isfinite(y.t05).mean()), 3),
         'w_last_loser_fill_px_p10_p50_p90': [round(float(np.percentile(w.w_last_px, q)), 3) for q in (10, 50, 90)],
         'w_min_loser_px_p10_p50_p90': [round(float(np.percentile(w.w_min_px, q)), 3) for q in (10, 50, 90)],
         'share_markets_w_min_px_le_0.06': round(float((w.w_min_px <= 0.06).mean()), 3),
         'share_loser_shares_bought_le_0.10': round(float(w.w_sh_le10.sum() / w.w_sh.sum()), 3),
         'share_loser_shares_after_public_0.25': round(float(w.w_sh_after_t25.sum() / w.w_sh.sum()), 3),
         'share_loser_shares_after_public_0.10': round(float(w.w_sh_after_t10.sum() / w.w_sh.sum()), 3),
         'usd_on_loser_after_public_0.10': round(float(w.w_usd_after_t10.sum()), 1)}
    k = w[np.isfinite(w.t10)]
    if len(k):
        r['w_last_fill_minus_t10_s_p10_p50_p90'] = [round(float(np.percentile(k.w_last_t - k.t10, q)), 1) for q in (10, 50, 90)]
        r['share_w_fills_after_t10'] = round(float((k.w_last_t >= k.t10).mean()), 3)
        r['w_share_of_public_buy_after_t10'] = round(float(k.w_sh_after_t10.sum() / max(k.w_sh_after_t10.sum() + k.pub_buy_sh_after_t10.fillna(0).sum(), 1e-9)), 3)
    r['corr_resid_pnl'] = corr(y.resid, y.pnl)
    r['corr_margin_pnl'] = corr(y.margin, y.pnl)
    r['corr_resid_vs_usd_after_t10'] = corr(w.resid, -w.w_usd_after_t10)
    r['resid_sum'] = round(float(y.resid.sum()), 1)
    res[sp] = r
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
