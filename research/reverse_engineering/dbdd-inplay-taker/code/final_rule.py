"""Frozen rule for dbdd-inplay-taker (iteration 1): LightGBM behaviour-cloning score over point-in-time tape
features (no own-state features), frozen in model_lgb_public.txt. See FINAL_RULE.md.

evaluate(start_ts, end_ts) loads, for markets the wallet traded whose game starts in [start_ts, end_ts):
the wallet's activity, Gamma metadata and full public taker tapes (data-api, cached), builds the same
point-in-time features (prints at T use only tape prints <= T-2), scores every in-play taker BUY print and
returns selection, behaviour-cloning and outcome metrics. Nothing is fitted inside evaluate().
"""
import sys, json, os
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np, pandas as pd

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
MODEL = os.path.join(HERE, 'model_lgb_public.txt')
SPEC = os.path.join(HERE, 'model_lgb_public_spec.json')
TOP_FRAC = 0.15


def _prep(F, spec):
    F = F.copy()
    F['smt_c'] = pd.Categorical(F.smt, categories=spec['smt_categories'])
    F['fam_c'] = pd.Categorical(F.fam, categories=spec['fam_categories'])
    F['log_quiet'] = np.log1p(F.quiet.clip(0, 1e5)); F['log_sib_quiet'] = np.log1p(F.sib_quiet.clip(0, 1e6))
    return F


def load_period(start_ts, end_ts, workers=4):
    from concurrent.futures import ThreadPoolExecutor
    from polyrea.adapters.polymarket import PolymarketData
    from features import market_meta
    pm = PolymarketData()
    rows, _, _ = pm.activity(W, start=start_ts - 86400, end=end_ts - 1)
    act = pd.DataFrame(rows)
    tr = act[(act.type == 'TRADE') & (act.timestamp < end_ts)]
    cids = sorted(tr.conditionId.dropna().unique())
    gm, _ = pm.markets_by_condition(cids)
    first = tr.groupby('conditionId').timestamp.min(); last = tr.groupby('conditionId').timestamp.max()
    jobs = []
    for c in cids:
        if c not in gm:
            continue
        m = market_meta(gm[c]); ref = m['gst'] if np.isfinite(m['gst']) else first[c]
        if ref < start_ts or ref >= end_ts:
            continue
        st = int(min(ref - 3600, first[c] - 600))
        ct = None
        try:
            ct = pd.Timestamp(str(gm[c].get('closedTime')).replace(' ', 'T').replace('+00', '+00:00')).timestamp() if gm[c].get('closedTime') else None
        except Exception:
            ct = None
        en = int(min(ref + 8 * 3600, ct if ct else ref + 8 * 3600, end_ts - 1))  # same tape window as fetch_data.py
        en = int(max(en, min(int(last[c]) + 600, end_ts - 1)))
        jobs.append((c, st, en))

    def fetch(j):
        c, st, en = j
        try:
            r, _, _ = pm.market_trades(c, start=st, end=en, taker_only=True)
        except Exception:
            return None
        if not r:
            return None
        d = pd.DataFrame(r)
        d = d[[k for k in ['timestamp', 'side', 'asset', 'price', 'size', 'proxyWallet', 'outcomeIndex', 'transactionHash'] if k in d.columns]].copy()
        d['cid'] = c
        return d[d.timestamp < end_ts]
    with ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(fetch, jobs) if p is not None]
    tapes = pd.concat(parts, ignore_index=True)
    return tapes, gm


def score_frame(F):
    import lightgbm as lgb
    spec = json.load(open(SPEC))
    m = lgb.Booster(model_file=MODEL)
    F = _prep(F, spec)
    F['score'] = m.predict(F[spec['features']])
    return F


def metrics(F):
    from evalkit import selection_report, within_auc
    F = F[F.groupby('cid').is_wallet.transform('max').astype(bool)].copy()
    out = {'selection': selection_report(F, 'score')}
    # side: at each wallet print, would the rule rather buy this token or its complement? compare the score of the
    # wallet's print with the score of the nearest-in-time print on the other token (same market, within 300 s before).
    w = F[F.is_wallet]
    out['side'] = {'wallet_prints': int(len(w)), 'favourite_baseline': float((w.price > 0.5).mean()),
                   'note': 'side model not frozen in iteration 1; favourite share reported as the market-only baseline'}
    # outcome: per-market PnL of the rule (buy each flagged print, $10 cap, at its price incl. fee) vs the wallet's
    pct = F.groupby('cid').score.rank(pct=True)
    sel = F[(pct > 1 - TOP_FRAC) & F.payout.notna() & ~F.is_wallet]
    fee = sel.fee_rate.fillna(0.05) * (1 - sel.price)
    usd = np.minimum(sel.usd, 10.0); sh = usd / sel.price
    sel = sel.assign(pnl=sh * sel.payout - usd * (1 + fee), usd_cap=usd)
    wp = w[w.payout.notna()].assign(pnl=lambda d: d.usd / d.price * d.payout - d.usd * (1 + d.fee_rate.fillna(0.05) * (1 - d.price)))
    pm_rule = sel.groupby('cid').pnl.sum(); pm_w = wp.groupby('cid').pnl.sum()
    j = pd.concat([pm_rule.rename('rule'), pm_w.rename('wallet')], axis=1).fillna(0)
    out['outcome'] = {'rule_trades': int(len(sel)), 'rule_usd': float(sel.usd_cap.sum()), 'rule_pnl': float(sel.pnl.sum()),
                      'rule_return': float(sel.pnl.sum() / sel.usd_cap.sum()) if len(sel) else None,
                      'wallet_pnl_est': float(wp.pnl.sum()), 'wallet_return_est': float(wp.pnl.sum() / wp.usd.sum()) if len(wp) else None,
                      'per_market_pnl_corr': float(j.rule.corr(j.wallet)) if len(j) > 2 else None,
                      'note': 'rule buys other takers\' flagged prints (observed liquidity, latency >= 2 s by construction of features); conditional on the wallet\'s market choice'}
    return out


def evaluate(start_ts, end_ts):
    from build_features import build
    tapes, gm = load_period(start_ts, end_ts)
    F = build(tapes, gm, v0=start_ts, b0=start_ts)
    F = F[(F.gst >= start_ts) & (F.gst < end_ts)]
    F = score_frame(F)
    return metrics(F)


if __name__ == '__main__':
    s, e = int(sys.argv[1]), int(sys.argv[2])
    print(json.dumps(evaluate(s, e), indent=1, default=float))
