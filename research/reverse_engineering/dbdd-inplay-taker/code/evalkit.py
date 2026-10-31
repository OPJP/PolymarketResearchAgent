"""Metrics for dbdd-inplay-taker (pre-registered; see NOTES.md). Vectorized, NaN-safe."""
import numpy as np, pandas as pd
from scipy.stats import norm

TOP_FRAC = 0.15   # pre-registered flag threshold: top 15% of scores within each market's population


def _clean(df, score):
    s = df[score].astype(float).to_numpy()
    return np.where(np.isfinite(s), s, -1e18)


def within_auc_stats(df, score='score', label='is_wallet', group='cid'):
    """Pooled within-group Mann-Whitney AUC (pairs only inside the same group) and a stratified
    normal-approximation p-value (sum of per-group U statistics; within-group label permutation null)."""
    d = pd.DataFrame({'g': df[group].to_numpy(), 'y': df[label].to_numpy().astype(bool), 's': _clean(df, score)})
    d['r'] = d.groupby('g').s.rank(method='average')
    agg = d.groupby('g').agg(n=('y', 'size'), npos=('y', 'sum'))
    rpos = d[d.y].groupby('g').r.sum()
    agg['rpos'] = rpos.reindex(agg.index).fillna(0.0)
    agg = agg[(agg.npos > 0) & (agg.npos < agg.n)]
    nneg = agg.n - agg.npos
    U = agg.rpos - agg.npos * (agg.npos + 1) / 2
    den = (agg.npos * nneg).sum()
    if den == 0:
        return np.nan, np.nan
    auc = U.sum() / den
    var = (agg.npos * nneg * (agg.n + 1) / 12.0).sum()
    z = (U.sum() - den / 2) / np.sqrt(var)
    return float(auc), float(norm.sf(z))


def within_auc(df, score='score', label='is_wallet', group='cid'):
    return within_auc_stats(df, score, label, group)[0]


def recall_lift(df, score='score', label='is_wallet', group='cid', top=TOP_FRAC):
    """Flag the top `top` share of the population within each group; return recall, flagged share and lift."""
    s = pd.Series(_clean(df, score), index=df.index)
    pct = s.groupby(df[group]).rank(pct=True, method='average')
    flag = (pct > 1 - top).to_numpy()
    y = df[label].to_numpy().astype(bool)
    rec = flag[y].mean() if y.sum() else np.nan
    share = flag.mean()
    prec = y[flag].mean() if flag.sum() else np.nan
    return {'recall': float(rec), 'flag_share': float(share), 'lift': float(rec / share) if share else np.nan,
            'precision': float(prec), 'base_rate': float(y.mean())}


def selection_report(df, score='score', n_perm=0):
    out = {'n_prints': int(len(df)), 'n_wallet': int(df.is_wallet.sum()), 'n_markets': int(df.cid.nunique())}
    auc, p = within_auc_stats(df, score)
    out['auc'] = auc; out['perm_p_normal_approx'] = p
    out.update(recall_lift(df, score))
    return out
