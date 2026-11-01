"""X133 analysis, first stage (pre-registered in NOTES iteration 10; frozen before any development record existed).

Usage: .venv/Scripts/python.exe research/reverse_engineering/tommy-cs2-maker/code/iter10/tp_odds_analysis.py START END
(UTC epoch seconds of a DEVELOPMENT block; iter_live returns development records only).

Per bo3 match matched to a Polymarket CS2 event (record field ev):
 (a) cadence: state changes per in-play minute, median interval between changes, suspension episodes (a1 = a2 = 0);
 (b) p_TP = (1/c1) / (1/c1 + 1/c2) mapped to the match market's first token by team name; the full-book mid of that
     token from the shared recorder's clob_wallets 'q' records (server clock 's'); cross-correlation of 5-s changes on
     a 1-s grid at lags -60..+60 s (positive lag = p_TP moves first), peak lag, and a 10-min block bootstrap of the
     peak's sign;
 (c) the wallet's maker fills on the match market (public data-api activity of the development block): SD of (fill
     price - p_TP 5 s before the fill) vs SD of (fill price - mid 5 s before);
 (d) within one tick of round(p_TP - delta) (delta = median of fill - p_TP on the first half) vs the mid on the second
     half (fills, not adds; the add-level version needs the BUILD-live labelling pipeline).
Output: results/tp_odds_analysis_<START>.json
"""
from __future__ import annotations

import json, re, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'research/reverse_engineering/tools'))
import live  # noqa: E402
import sealed  # noqa: E402

KEY = 'tommy-cs2-maker'
W = '0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2'
RES = ROOT / 'research/reverse_engineering/tommy-cs2-maker/results'


def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def sim(a, b):
    return bool(a) and bool(b) and (a in b or b in a or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]))


def gamma_event(slug):
    from polyrea.adapters.http import shared_client
    h = shared_client()
    d, _ = h.get_json('https://gamma-api.polymarket.com/events', {'slug': slug}, adapter='gamma.events', max_age=3600)
    e = (d or [None])[0]
    if not e:
        return None
    for m in e.get('markets') or []:
        if m.get('sportsMarketType') == 'moneyline':
            outs = json.loads(m.get('outcomes') or '[]'); toks = json.loads(m.get('clobTokenIds') or '[]')
            gst = m.get('gameStartTime')
            return {'cid': m.get('conditionId'), 'outcomes': outs, 'tokens': toks, 'gst': gst}
    return None


def main(start, end):
    assert not sealed.is_sealed(start, KEY) and not sealed.is_sealed(end - 1, KEY), 'not a development block'
    # iteration 11: v1 (feed tommy_tp_odds) stopped 11-01 05:30 UTC before any development block; v2 writes the same B
    # records (plus U / P kinds and coverage fields) to tommy_tp_odds2. Data plumbing only; the tests are unchanged.
    R = [r for fd in ('tommy_tp_odds', 'tommy_tp_odds2') for r in live.iter_live(fd, start, end) if r.get('k') == 'B' and r.get('ev')]
    res = {'block': [start, end], 'records': len(R), 'matches': {}}
    if not R:
        (RES / f'tp_odds_analysis_{int(start)}.json').write_text(json.dumps(res, indent=1))
        print(json.dumps(res)); return
    B = pd.DataFrame(R)
    books = {}
    for h0 in range(int(start), int(end), 3600):  # hour by hour: a corrupt hour file (zlib error) is skipped, not fatal
        try:
            for x in live.iter_live('clob_wallets', h0, min(h0 + 3600, end)):
                if x.get('k') == 'q' and x.get('b') and x.get('o'):
                    books.setdefault(x['a'], []).append((x['s'], (float(x['b'][0][0]) + float(x['o'][0][0])) / 2))
        except Exception as e:  # noqa: BLE001
            res.setdefault('book_hours_skipped', []).append([h0, repr(e)[:80]])
    try:
        from polyrea.adapters.polymarket import PolymarketData
        rows_, _, _ = PolymarketData().activity(W, int(start), int(end))
        act = pd.DataFrame(rows_)
    except Exception as e:  # noqa: BLE001
        act = pd.DataFrame(); res['activity_error'] = repr(e)[:200]
    for mid_, g in B.groupby('id'):
        g = g.sort_values('t')
        r = {'slug': g.slug.iloc[0], 'ev': g.ev.iloc[0], 'n_states': int(len(g))}
        span = (g.t.iloc[-1] - g.t.iloc[0]) / 60000
        dt = np.diff(g.t.to_numpy(float)) / 1000
        r['changes_per_min'] = round(len(g) / span, 3) if span > 0 else None
        r['median_interval_s'] = round(float(np.median(dt)), 1) if len(dt) else None
        susp = ((g.a1 == 0) & (g.a2 == 0)).to_numpy()
        r['suspension_episodes'] = int(np.sum(np.diff(np.r_[0, susp.astype(int)]) == 1))
        ok = g.c1.notna() & g.c2.notna() & (g.c1 > 1) & (g.c2 > 1)
        g = g[ok]
        if g.empty:
            res['matches'][str(mid_)] = r; continue
        ge = gamma_event(r['ev'])
        if not ge or len(ge['outcomes']) != 2:
            res['matches'][str(mid_)] = r; continue
        gs_ = pd.Timestamp(ge['gst']).tz_convert('UTC').timestamp() if ge.get('gst') and pd.Timestamp(ge['gst']).tzinfo else (pd.Timestamp(ge['gst'], tz='UTC').timestamp() if ge.get('gst') else None)
        if gs_ is None or sealed.is_sealed(float(gs_), KEY) or sealed.is_sealed(float(gs_) - 1800, KEY):
            r['skipped'] = 'unit not a development unit (unit rule, fail closed)'
            res['matches'][str(mid_)] = r; continue
        o0 = norm(ge['outcomes'][0]); n1 = norm(g.n1.iloc[0]); n2 = norm(g.n2.iloc[0])
        flip = sim(o0, n2) and not sim(o0, n1)
        p1 = (1 / g.c1) / (1 / g.c1 + 1 / g.c2)
        p = (1 - p1) if flip else p1
        tok0 = ge['tokens'][0]
        bk = books.get(tok0)
        r['token_mapped'] = True; r['flip'] = bool(flip); r['book_samples'] = len(bk) if bk else 0
        if bk:
            bk = pd.DataFrame(bk, columns=['s', 'mid']).sort_values('s')
            t0, t1 = max(g.t.min(), bk.s.min()), min(g.t.max(), bk.s.max())
            if t1 - t0 > 600000:
                grid = np.arange(t0, t1, 1000.0)
                pt = pd.Series(p.to_numpy(float), index=g.t.to_numpy(float))
                ip = np.searchsorted(pt.index.to_numpy(), grid, side='right') - 1
                im = np.searchsorted(bk.s.to_numpy(float), grid, side='right') - 1
                P_ = pt.to_numpy()[np.maximum(ip, 0)]; M_ = bk.mid.to_numpy(float)[np.maximum(im, 0)]
                dP = P_[5:] - P_[:-5]; dM = M_[5:] - M_[:-5]
                lags = list(range(-60, 61))
                cc = []
                for L in lags:  # positive L: p_TP change at t, mid change at t + L (p_TP first)
                    a = dP[:len(dP) - L] if L > 0 else dP[-L:]
                    b = dM[L:] if L > 0 else dM[:len(dM) + L]
                    cc.append(float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else np.nan)
                k = int(np.nanargmax(cc))
                r['xcorr_peak_lag_s'] = lags[k]; r['xcorr_peak'] = round(cc[k], 3)
                r['xcorr_at_0'] = round(cc[60], 3)
                r['level_gap_c_p50_sd'] = [round(float(np.median((P_ - M_) * 100)), 2), round(float(np.std((P_ - M_) * 100)), 2)]
        if len(act) and 'conditionId' in act:
            f = act[(act.conditionId == ge['cid']) & (act['type'] == 'TRADE')] if 'type' in act else act[act.conditionId == ge['cid']]
            if len(f):
                f = f.assign(p0=np.where(f.outcomeIndex.astype(int) == 0, f.price.astype(float), 1 - f.price.astype(float)))
                tf = f.timestamp.to_numpy(float) * 1000 - 5000
                ip = np.searchsorted(g.t.to_numpy(float), tf, side='right') - 1
                ptp = np.where(ip >= 0, p.to_numpy(float)[np.maximum(ip, 0)], np.nan)
                d = (f.p0.to_numpy() - ptp) * 100
                r['fills'] = int(len(f)); r['fill_minus_ptp_c_sd'] = round(float(np.nanstd(d)), 2)
                if bk is not None and len(bk):
                    im = np.searchsorted(bk.s.to_numpy(float), tf, side='right') - 1
                    mm = np.where(im >= 0, bk.mid.to_numpy(float)[np.maximum(im, 0)], np.nan)
                    r['fill_minus_mid_c_sd'] = round(float(np.nanstd((f.p0.to_numpy() - mm) * 100)), 2)
                h = len(d) // 2
                if h >= 10:
                    delta = np.nanmedian(d[:h]) / 100
                    pr = np.round(ptp[h:] + delta, 2)
                    r['within_tick_ptp_second_half'] = round(float(np.nanmean(np.abs(f.p0.to_numpy()[h:] - pr) <= 0.0101)), 3)
        res['matches'][str(mid_)] = r
    (RES / f'tp_odds_analysis_{int(start)}.json').write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float)[:3000])


if __name__ == '__main__':
    main(float(sys.argv[1]), float(sys.argv[2]))
