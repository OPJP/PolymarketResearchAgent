"""dbdd-inplay-taker frozen rule, iteration 2: R-SEL-GOAL-2 (selection) + decoded order mechanics (B1).

Components (see FINAL_RULE.md for tags):
- selection/timing score over every in-play taker BUY print of a market the wallet trades: LightGBM over
  point-in-time public tape state + listing metadata + the ESPN soccer goal-recency indicator (E3 survivor,
  confirmed on VALIDATE). The co-occurrence baseline is the same model class on market-activity features only
  (no metadata, no event feed), trained on the same BUILD data.
- price: limit = best ask at decision (the touch), one FAK order (B1).
- size: integer-USDC stake (B1); no model of the amount yet.
- side: token with the larger 300-s price rise (reported against 'buy the favourite').

evaluate(start_ts, end_ts, intervals=None) fetches (through the cached polyrea adapters) the wallet's activity,
Gamma listings, public taker tapes of every market it traded with unit start in the period, ESPN soccer key
events, and the V2 calldata of its fills; applies the frozen models point-in-time; returns metrics per wallet and
pooled (one wallet). Only units starting in [start_ts, end_ts) (and in `intervals` if given) count.
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(__file__))
from polyrea_path import CACHE, ROOT
import numpy as np, pandas as pd

ALLOW_SEALED = False          # only the examiner's driver sets this to True
WALLET = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
DECISION_LAG_S = 2.0          # a print stamped T may have matched up to 2 s earlier: features use prints < T - 2
GOAL_DELAY_S = 5.0            # ESPN wall clock usable 5 s after it
GOAL_WINDOW_S = 80.0          # E3 survivor: decision excess over [0, 80] s after a goal (peak 15-25 s)
FLAG_TOP = 0.15               # pre-registered: flag the top 15% of scores within each market
STAKE_USD = 10.0              # outcome test: buy $10 at each flagged print's price
PNL_PRICE_RANGE = (0.05, 0.95) # outcome test only uses flagged prints priced inside this range
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_FULL = os.path.join(HERE, 'model_sel_full_it2.txt')
MODEL_BASE = os.path.join(HERE, 'model_sel_base_it2.txt')
BASE_FEATS = ['log_quiet', 'n_before', 'minute', 'price', 'mv60', 'mv300', 'mv900', 'flow60', 'n60', 'usd60', 'n10',
              'dp_last', 'tok_share60']
FULL_FEATS = BASE_FEATS + ['goal_recent', 'since_goal', 'fam_c', 'smt_c', 'is_over', 'fee_c']
FAMS = ['cs2', 'esports', 'tennis', 'us', 'soccer_other']
SMTS = ['moneyline', 'totals', 'spreads', 'both_teams_to_score', 'team_totals', 'first_half_totals', 'halftime_result',
        'map_handicap', 'match_handicap', 'other']


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


def market_features(tape, unit_ts, meta, goals):
    """tape: DataFrame of one market's taker rows (timestamp, side, asset, price, size, proxyWallet), sorted.
    Returns one row per in-play BUY print with point-in-time features (prints strictly before T - 2 s)."""
    t_all = tape.timestamp.values.astype(float)
    toks = list(pd.unique(tape.asset))
    buy_all = (tape.side.values == 'BUY')
    px_all = tape.price.values.astype(float)
    usd_all = px_all * tape['size'].values.astype(float)
    a_all = tape.asset.values
    own = np.array([str(x).lower() == WALLET for x in tape.proxyWallet.values])
    # features come from OTHER wallets' prints only (the wallet's own prints are never a feature)
    o = ~own
    t, px, usd, a, is_buy = t_all[o], px_all[o], usd_all[o], a_all[o], buy_all[o]
    # last traded price of token 0 as a series (token 1 maps to 1 - p)
    t0 = toks[0]
    p0 = np.where(a == t0, px, 1 - px)
    sgn0 = np.where(a == t0, 1.0, -1.0) * np.where(is_buy, 1.0, -1.0)   # +1 = flow toward token 0
    cs_n = np.arange(1, len(t) + 1)
    cs_usd = np.cumsum(usd)
    cs_flow0 = np.cumsum(sgn0 * usd)
    cs_tok0 = np.cumsum(np.where(a == t0, 1.0, 0.0))
    rows = []
    gl = np.sort(np.asarray(goals, float)) if goals is not None and len(goals) else np.array([])
    smt = (meta.get('sportsMarketType') or 'other')
    smt = smt if smt in SMTS else 'other'
    try:
        outs = json.loads(meta['outcomes']) if isinstance(meta.get('outcomes'), str) else (meta.get('outcomes') or [])
    except Exception:
        outs = []
    fee = meta.get('feeSchedule') or {}
    try:
        fee_rate = float((fee or {}).get('rate') or 0) if isinstance(fee, dict) else 0.0
    except Exception:
        fee_rate = 0.0
    f_c = FAMS.index(fam(meta.get('slug')))
    for i in np.flatnonzero(buy_all & (t_all >= unit_ts)):
        T = t_all[i]
        cut = np.searchsorted(t, T - DECISION_LAG_S, side='left')     # prints strictly before T - 2
        if cut == 0:
            prev_t, last0 = unit_ts - 3600, np.nan
        else:
            prev_t, last0 = t[cut - 1], p0[cut - 1]
        tokidx = 0 if a_all[i] == t0 else 1

        def at(h):
            k = np.searchsorted(t, T - DECISION_LAG_S - h, side='left')
            return p0[k - 1] if k > 0 else np.nan

        def window(h):
            k = np.searchsorted(t, T - DECISION_LAG_S - h, side='left')
            n = (cs_n[cut - 1] if cut else 0) - (cs_n[k - 1] if k else 0)
            u = (cs_usd[cut - 1] if cut else 0) - (cs_usd[k - 1] if k else 0)
            fl = (cs_flow0[cut - 1] if cut else 0) - (cs_flow0[k - 1] if k else 0)
            tk = (cs_tok0[cut - 1] if cut else 0) - (cs_tok0[k - 1] if k else 0)
            return n, u, fl, tk
        sg = 1.0 if tokidx == 0 else -1.0
        n60, u60, f60, tk60 = window(60)
        n10, _, _, _ = window(10)
        mv = {h: sg * (last0 - at(h)) if np.isfinite(last0) else np.nan for h in (60, 300, 900)}
        lastp_tok = last0 if tokidx == 0 else 1 - last0
        k = np.searchsorted(gl, T - GOAL_DELAY_S, side='right') - 1 if len(gl) else -1
        since_goal = (T - gl[k]) if k >= 0 else 1e5
        rows.append((i, T, tokidx, px_all[i], usd_all[i], np.log1p(max(T - prev_t, 0)), cut, (T - unit_ts) / 60.0, px_all[i],
                     mv[60], mv[300], mv[900], sg * f60, n60, u60, n10, px_all[i] - lastp_tok if np.isfinite(lastp_tok) else np.nan,
                     (tk60 / n60 if n60 else np.nan) if tokidx == 0 else ((n60 - tk60) / n60 if n60 else np.nan),
                     float(0 <= since_goal - GOAL_DELAY_S <= GOAL_WINDOW_S), min(since_goal, 1e5), f_c, SMTS.index(smt),
                     float(tokidx < len(outs) and str(outs[tokidx]).lower() in ('over', 'yes')), fee_rate,
                     bool(own[i])))
    cols = ['row', 'ts', 'tokidx', 'px', 'usd', 'log_quiet', 'n_before', 'minute', 'price', 'mv60', 'mv300', 'mv900', 'flow60',
            'n60', 'usd60', 'n10', 'dp_last', 'tok_share60', 'goal_recent', 'since_goal', 'fam_c', 'smt_c', 'is_over', 'fee_c', 'y']
    return pd.DataFrame(rows, columns=cols)


def within_market_auc(df, score):
    """Pooled Mann-Whitney over within-market pairs only, plus recall/lift at the top-15% flag."""
    from scipy.stats import rankdata
    num = den = 0.0
    flag_hits = flag_n = 0
    for c, g in df.groupby('cid'):
        y = g.y.values.astype(bool)
        npos, nneg = y.sum(), (~y).sum()
        if npos == 0 or nneg == 0:
            continue
        s = g[score].values
        r = rankdata(s)
        num += r[y].sum() - npos * (npos + 1) / 2
        den += npos * nneg
        thr = np.quantile(s, 1 - FLAG_TOP)
        fl = s >= thr
        flag_hits += (fl & y).sum()
        flag_n += fl.sum()
    pos = df.groupby('cid').y.transform('sum') > 0
    base = df[pos].y.mean()
    tot_pos = df[pos].y.sum()
    return {'auc': num / den if den else np.nan, 'recall': flag_hits / tot_pos if tot_pos else np.nan,
            'lift': (flag_hits / flag_n) / base if flag_n and base else np.nan, 'base_rate': float(base), 'n_pos': int(tot_pos),
            'n_prints': int(pos.sum())}


def block_bootstrap_gain(df, s_full, s_base, n_boot=300, seed=0):
    """Gain in within-market AUC with games (markets) resampled as blocks."""
    cids = df.cid.unique()
    rng = np.random.default_rng(seed)
    per = {}
    for c, g in df.groupby('cid'):
        y = g.y.values.astype(bool)
        if y.sum() == 0 or (~y).sum() == 0:
            continue
        from scipy.stats import rankdata
        out = []
        for s in (s_full, s_base):
            r = rankdata(g[s].values)
            out.append(r[y].sum() - y.sum() * (y.sum() + 1) / 2)
        per[c] = (out[0], out[1], y.sum() * (~y).sum())
    keys = list(per)
    A = np.array([per[k] for k in keys])
    gains = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(keys), len(keys))
        S = A[idx].sum(0)
        gains.append(S[0] / S[2] - S[1] / S[2])
    S = A.sum(0)
    return float(S[0] / S[2] - S[1] / S[2]), [float(np.quantile(gains, 0.025)), float(np.quantile(gains, 0.975))], float(np.mean(np.array(gains) <= 0))


def load_period(start_ts, end_ts, intervals=None, tape_dir=None, verbose=True):
    """Wallet activity, listings, tapes, ESPN goals and calldata for units starting in the period."""
    import glob
    from polyrea.adapters.polymarket import PolymarketData
    import sealed
    pm = PolymarketData()
    rows, _, _ = pm.activity(WALLET, start=int(start_ts) - 86400, end=int(end_ts) + 2 * 86400, types=('TRADE',))
    act = pd.DataFrame(rows)
    cids = sorted(act.conditionId.dropna().unique())
    meta, _ = pm.markets_by_condition(cids)
    first = act.groupby('conditionId').timestamp.min()
    last = act.groupby('conditionId').timestamp.max()
    keep = {}
    for c in cids:
        m = meta.get(c) or {}
        g = m.get('gameStartTime')
        try:
            u = pd.Timestamp(g).timestamp() if g else float(first[c])
        except Exception:
            u = float(first[c])
        if not (start_ts <= u < end_ts):
            continue
        if intervals is not None and not any(a <= u < b for a, b in intervals):
            continue
        if not ALLOW_SEALED and sealed.is_sealed(u, 'dbdd-inplay-taker'):
            continue
        keep[c] = (u, {k: m.get(k) for k in ('slug', 'sportsMarketType', 'outcomes', 'feeSchedule', 'clobTokenIds', 'events',
                                             'outcomePrices', 'closed', 'question')})
    act = act[act.conditionId.isin(keep)]
    tapes = {}
    for c, (u, m) in keep.items():
        if tape_dir and os.path.exists(os.path.join(tape_dir, f'{c}.parquet')):
            d = pd.read_parquet(os.path.join(tape_dir, f'{c}.parquet'))
        else:
            st = int(min(u - 3600, first[c] - 600))
            en = int(max(u + 8 * 3600, last[c] + 600))
            rr, _, _ = pm.market_trades(c, start=st, end=en, taker_only=True)
            d = pd.DataFrame(rr)
        if len(d) and 'timestamp' in d:
            tapes[c] = d.sort_values('timestamp', kind='stable').reset_index(drop=True)
    if verbose:
        print('markets', len(keep), 'with tapes', len(tapes), flush=True)
    return act, keep, tapes


def espn_goals(keep, act):
    """Goal wall clocks per market (soccer only) via ESPN, using the iteration-1 matcher."""
    from fetch_espn_soccer import find, LG
    base = {}
    for c, (u, m) in keep.items():
        slug = ((m.get('events') or [{}])[0] or {}).get('slug') or m.get('slug') or ''
        b = re.sub(r'-(more-markets|halftime-result|total-corners|exact-score|player-props|first-half.*|btts.*)$', '', slug)
        if b.split('-')[0] in LG:
            base.setdefault(b, []).append(c)
    titles = act.groupby('eventSlug').title.first().to_dict()
    goals = {}
    for b, cs in base.items():
        u = keep[cs[0]][0]
        title = titles.get(b) or next((t for e, t in titles.items() if e.startswith(b)), '')
        try:
            _, ev = find((b, title, u))
        except Exception:
            ev = None
        if not ev:
            continue
        gl = [e['wallclock'] for e in ev if e.get('scoring') and np.isfinite(e.get('wallclock', np.nan))]
        for c in cs:
            goals[c] = gl
    return goals


def build(start_ts, end_ts, intervals=None, tape_dir=None):
    act, keep, tapes = load_period(start_ts, end_ts, intervals, tape_dir)
    goals = espn_goals(keep, act)
    parts = []
    for c, d in tapes.items():
        u, m = keep[c]
        f = market_features(d, u, m, goals.get(c))
        if len(f):
            f['cid'] = c
            parts.append(f)
    F = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return act, keep, tapes, F


def score(F):
    import lightgbm as lgb
    full = lgb.Booster(model_file=MODEL_FULL)
    base = lgb.Booster(model_file=MODEL_BASE)
    F = F.copy()
    F['s_full'] = full.predict(F[FULL_FEATS].astype('float32'))
    F['s_base'] = base.predict(F[BASE_FEATS].astype('float32'))
    return F


def side_price_size(act, keep, F):
    """Side vs baselines on the wallet's in-play prints; price and size from the calldata of its fills."""
    from calldata import fetch, rows_from
    w = F[F.y]
    out = {}
    if len(w):
        # side rule: buy the token whose 300-s price move is positive (mv300 is signed toward the bought token)
        v = w[w.mv300.notna() & (w.mv300 != 0)]
        out['side_rule'] = 'buy the token whose last price rose over the 300 s before T-2 (mv300 > 0)'
        out['side_accuracy'] = float((v.mv300 > 0).mean()) if len(v) else None
        out['side_n'] = int(len(v))
        out['side_baseline_favourite'] = float((w.price > 0.5).mean())
    txs = list(dict.fromkeys(act.transactionHash.dropna()))
    m = fetch(txs, batch=20)
    tk, _ = rows_from(m, WALLET)
    tk = tk[tk.get('ok', 0) == 1] if len(tk) else tk
    if len(tk):
        j = tk.merge(act.drop_duplicates('transactionHash')[['transactionHash', 'price', 'timestamp']], left_on='tx', right_on='transactionHash')
        out['price_rule'] = 'limit = best ask at decision (touch); fill price as the touch proxy'
        out['price_within_tick'] = float((np.abs(j.t_px - j.price) <= 0.0105).mean())
        out['price_limit_eq_fill'] = float((np.abs(j.t_px - j.price) < 0.0015).mean())
        out['size_integer_usdc_share'] = float((np.abs(j.t_usdc - j.t_usdc.round()) < 1e-6).mean())
        out['size_fill_ratio_median'] = float((j.t_fill / j.t_usdc).median())
        out['decision_latency_median_s'] = float((j.timestamp - j.t_ts_ms / 1000).median())
    return out


def pnl_metrics(act, keep, F):
    """Rule: $10 at each flagged print's price (other takers' prints, full model top 15% in market), held to
    resolution; vs the wallet's realized per-market PnL. Resolved markets only."""
    from scipy.stats import pearsonr, spearmanr
    pay = {}
    for c, (u, m) in keep.items():
        try:
            op = json.loads(m['outcomePrices']) if isinstance(m.get('outcomePrices'), str) else m.get('outcomePrices')
            op = [float(x) for x in op]
            if len(op) == 2 and max(op) > 0.99:
                pay[c] = op
        except Exception:
            pass
    a = act[act.conditionId.isin(pay)]
    wp = {}
    for r in a.itertuples(index=False):
        wp[r.conditionId] = wp.get(r.conditionId, 0.0) + float(r.size) * pay[r.conditionId][int(r.outcomeIndex)] - float(r.usdcSize)
    rp, spent = {}, 0.0
    for c, g in F[F.cid.isin(pay)].groupby('cid'):
        thr = np.quantile(g.s_full, 1 - FLAG_TOP)
        fl = g[(g.s_full >= thr) & (~g.y) & (g.px >= PNL_PRICE_RANGE[0]) & (g.px <= PNL_PRICE_RANGE[1])]
        rp[c] = float(sum(STAKE_USD / p * pay[c][int(k)] - STAKE_USD for p, k in zip(fl.px, fl.tokidx)))
        spent += STAKE_USD * len(fl)
    cs = sorted(set(wp) & set(rp))
    if len(cs) < 3:
        return {}
    x, y = np.array([rp[c] for c in cs]), np.array([wp[c] for c in cs])
    return {'pnl_markets': len(cs), 'pnl_corr_pearson': float(pearsonr(x, y)[0]), 'pnl_corr_spearman': float(spearmanr(x, y)[0]),
            'rule_return': float(x.sum() / spent) if spent else None,
            'wallet_pnl_sum': float(y.sum())}


def evaluate(start_ts, end_ts, intervals=None, tape_dir=None):
    act, keep, tapes, F = build(start_ts, end_ts, intervals, tape_dir)
    if F.empty:
        return {'error': 'no data'}
    F = score(F)
    sel = within_market_auc(F, 's_full')
    base = within_market_auc(F, 's_base')
    gain, ci, p_le0 = block_bootstrap_gain(F, 's_full', 's_base')
    # coverage: wallet fills (and |PnL| proxy = USD) inside the scored population
    n_all = len(act)
    in_pop = int(F.y.sum())
    usd_all = float(act.usdcSize.sum())
    usd_pop = float(F[F.y].usd.sum())
    res = {'wallet': WALLET, 'rule_id': 'R-SEL-GOAL-2',
           'selection_auc': sel['auc'], 'selection_recall': sel['recall'], 'selection_lift': sel['lift'],
           'selection_baseline': base['auc'], 'selection_gain': gain, 'selection_gain_ci95': ci, 'p_gain_le_0': p_le0,
           'n_wallet_prints': sel['n_pos'], 'n_prints': sel['n_prints'], 'base_rate': sel['base_rate'],
           'coverage_fills': in_pop / n_all if n_all else None, 'coverage_usd': usd_pop / usd_all if usd_all else None}
    res.update(side_price_size(act, keep, F))
    res.update(pnl_metrics(act, keep, F))
    res['pooled'] = {k: v for k, v in res.items() if k != 'pooled'}   # one wallet: pooled == per wallet
    return res


if __name__ == '__main__':
    a, b = (float(x) for x in sys.argv[1:3])
    print(json.dumps(evaluate(a, b), indent=1, default=float))
