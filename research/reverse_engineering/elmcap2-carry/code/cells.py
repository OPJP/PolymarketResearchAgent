"""Cell builder: (market, 6h bin) cells for universe U with point-in-time features and wallet labels.
Features use only CLOB hourly prices stamped <= t0 - 60 s and listing fields. No own-state features here."""
import json, re
import numpy as np, pandas as pd
BIN = 6 * 3600
LAG = 60
FAMS = ['fomc', 'mention', 'deadline', 'election', 'crypto', 'other']

def family(q, slug):
    s = (str(slug) + ' ' + str(q)).lower()
    if 'fed-decision' in s or 'fomc' in s or ('fed' in s and ('rate' in s or 'bps' in s or 'decision' in s)): return 'fomc'
    if re.search(r'\b(say|said|mention|tweet|post)\b', s): return 'mention'
    if re.search(r'\b(bitcoin|btc|ethereum|eth|solana|xrp|crypto)\b', s) or 'price of' in s: return 'crypto'
    if re.search(r'\b(election|win the|governor|senate|president|primary|nominee|mayor|parliament|prime minister|seats|confirmed)\b', s): return 'election'
    if re.search(r'\b(by|before|through|in) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|the end|end of|20\d\d|q[1-4])', s) or re.search(r'\bby\b.*\d', s): return 'deadline'
    return 'other'

def build_cells(meta, prices, buys):
    """meta: universe rows (non-sport, non-updown); prices: {cid: [(t,p)]}; buys: wallet BUY fills (timestamp, conditionId, outcomeIndex, price, usdcSize)."""
    bys = {c: g.sort_values('timestamp') for c, g in buys.groupby('conditionId')} if len(buys) else {}
    out = []
    for r in meta.itertuples():
        pts = prices.get(r.conditionId) or []
        if not pts: continue
        t = np.array([x[0] for x in pts], dtype=np.int64); p = np.array([x[1] for x in pts], dtype=float)
        start = max(r.end_ts - 14 * 86400, r.start_ts if r.start_ts == r.start_ts else -1e18)
        stop = min(r.closed_ts, r.end_ts + 14 * 86400)
        t0s = np.arange(np.ceil(start / BIN) * BIN, stop, BIN).astype(np.int64)
        if len(t0s) == 0: continue
        fam = family(r.question, r.slug)
        wb = bys.get(r.conditionId)
        for t0 in t0s:
            i = np.searchsorted(t, t0 - LAG, side='right') - 1
            if i < 0: continue
            p0 = p[i]; fav = 0 if p0 >= 0.5 else 1
            def fp(dt):
                j = np.searchsorted(t, t0 - LAG - dt, side='right') - 1
                if j < 0: return np.nan
                return p[j] if fav == 0 else 1 - p[j]
            pf = p0 if fav == 0 else 1 - p0
            w = (t > t0 - LAG - 86400) & (t <= t0 - LAG)
            pw = p[w] if fav == 0 else 1 - p[w]
            below = np.where(((p[:i + 1] if fav == 0 else 1 - p[:i + 1]) < 0.99))[0]
            hrs99 = (t0 - t[below[-1]]) / 3600 if len(below) else (t0 - t[0]) / 3600
            below95 = np.where(((p[:i + 1] if fav == 0 else 1 - p[:i + 1]) < 0.95))[0]
            hrs95 = (t0 - t[below95[-1]]) / 3600 if len(below95) else (t0 - t[0]) / 3600
            y = 0; usd = 0.0; side_fav = np.nan; wpx = np.nan; n = 0
            if wb is not None:
                s = wb[(wb.timestamp >= t0) & (wb.timestamp < t0 + BIN)]
                if len(s):
                    y = 1; usd = float(s.usdcSize.sum()); n = len(s)
                    side_fav = float((s.outcomeIndex.astype(int) == fav).mean())
                    wpx = float(np.average(s.price, weights=s.usdcSize + 1e-9))
            out.append((r.conditionId, int(t0), fam, bool(r.negRisk) if r.negRisk is not None else False, pf, fav,
                        (r.end_ts - t0) / 3600, fp(6 * 3600), fp(24 * 3600), fp(72 * 3600),
                        float(np.std(np.diff(pw))) if len(pw) > 2 else np.nan, len(pw), min(hrs99, 24 * 30), min(hrs95, 24 * 30),
                        (t0 - (r.start_ts if r.start_ts == r.start_ts else t[0])) / 3600, (t0 % 86400) // 3600, int(pd.Timestamp(t0, unit='s').dayofweek),
                        float(r.orderPriceMinTickSize or 0.01), y, usd, n, side_fav, wpx))
    cols = ['cid', 't0', 'fam', 'neg_risk', 'pf', 'fav', 'h_end', 'pf6', 'pf24', 'pf72', 'vol24', 'npts24', 'hrs99', 'hrs95', 'age_h', 'hour', 'dow', 'tick_final',
            'y', 'usd', 'n', 'side_fav', 'wpx']
    d = pd.DataFrame(out, columns=cols)
    d['lpf'] = -np.log10(np.clip(1 - d.pf, 1e-4, 1))
    d['after_end'] = (d.h_end < 0).astype(int)
    d['jump24'] = d.pf - d.pf24
    d['jump72'] = d.pf - d.pf72
    for f in FAMS: d['fam_' + f] = (d.fam == f).astype(int)
    return d
