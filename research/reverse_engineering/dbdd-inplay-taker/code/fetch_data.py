"""Data expansion for dbdd-inplay-taker (development period only: every timestamp < H).

Phase 1: the wallet's full activity history [0, H) via cursor paging (cached).
Phase 2: Gamma metadata for every market it traded in the tape window [T0, H).
Phase 3: full taker tapes (one row per aggressive order) for EVERY market it traded
         in the tape window, newest games first, truncated at H. Written in parquet
         chunks under .cache/re/dbdd-inplay-taker/tapes/.

Usage: python fetch_data.py [phase...]   (default: all phases)
"""
import sys, os, json, time, glob
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from polyrea.adapters.polymarket import PolymarketData

W = '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de'
H = 1792713600            # holdout start 2026-10-23 00:00 UTC: nothing at or after H is loaded
T0 = 1792713600 - 30 * 86400   # tape window start 2026-09-23
CACHE = '/home/user/PolymarketResearchAgent/.cache/re/dbdd-inplay-taker'
os.makedirs(f'{CACHE}/tapes', exist_ok=True)
pm = PolymarketData()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def phase_activity():
    t0 = time.time()
    rows, src, cov = pm.activity(W, start=0, end=H - 1)
    df = pd.DataFrame(rows)
    df = df[df.timestamp < H]
    keep = [c for c in ['timestamp', 'type', 'conditionId', 'asset', 'side', 'price', 'size', 'usdcSize', 'outcome',
                        'outcomeIndex', 'title', 'slug', 'eventSlug', 'transactionHash'] if c in df.columns]
    df = df[keep]
    df.to_parquet(f'{CACHE}/activity.parquet')
    log('activity', len(df), 'rows', cov.status, cov.detail, round(time.time() - t0), 's',
        'first', pd.Timestamp(df.timestamp.min(), unit='s'), 'last', pd.Timestamp(df.timestamp.max(), unit='s'))


def phase_gamma():
    act = pd.read_parquet(f'{CACHE}/activity.parquet')
    tr = act[(act.type == 'TRADE') & (act.timestamp >= T0 - 2 * 86400)]
    cids = sorted(tr.conditionId.dropna().unique())
    log('gamma for', len(cids), 'markets')
    t0 = time.time()
    out, _ = pm.markets_by_condition(cids)
    keep = ['conditionId', 'question', 'slug', 'clobTokenIds', 'outcomes', 'outcomePrices', 'gameStartTime', 'sportsMarketType',
            'closedTime', 'umaResolutionStatus', 'closed', 'feeSchedule', 'line', 'groupItemTitle', 'events', 'startDate', 'endDate',
            'orderPriceMinTickSize', 'negRisk', 'createdAt', 'acceptingOrdersTimestamp', 'gameId', 'volumeNum', 'liquidityNum']
    slim = {c: {k: m.get(k) for k in keep} for c, m in out.items()}
    for c, m in slim.items():
        ev = m.get('events') or []
        m['events'] = [{k: e.get(k) for k in ('slug', 'title', 'seriesSlug', 'startTime', 'eventDate', 'gameId', 'tags')} for e in ev][:1]
    json.dump(slim, open(f'{CACHE}/gamma.json', 'w'))
    log('gamma done', len(slim), 'of', len(cids), round(time.time() - t0), 's')


def _gst(m):
    g = m.get('gameStartTime')
    if not g:
        return np.nan
    try:
        return pd.Timestamp(g).timestamp()
    except Exception:
        return np.nan


def phase_tapes():
    act = pd.read_parquet(f'{CACHE}/activity.parquet')
    gm = json.load(open(f'{CACHE}/gamma.json'))
    tr = act[(act.type == 'TRADE')]
    first = tr.groupby('conditionId').timestamp.min()
    last = tr.groupby('conditionId').timestamp.max()
    jobs = []
    for cid, m in gm.items():
        if cid not in first.index:
            continue
        gst = _gst(m)
        f0 = int(first[cid])
        ref = gst if np.isfinite(gst) else f0
        if ref < T0 or ref >= H:
            continue
        st = int(min(ref - 3600, f0 - 600))
        ct = None
        try:
            ct = pd.Timestamp(str(m.get('closedTime')).replace(' ', 'T').replace('+00', '+00:00')).timestamp() if m.get('closedTime') else None
        except Exception:
            ct = None
        en = int(min(ref + 8 * 3600, ct if ct else ref + 8 * 3600, H - 1))
        en = int(max(en, min(int(last[cid]) + 600, H - 1)))
        jobs.append((ref, cid, st, en))
    jobs.sort(reverse=True)  # newest first (VALIDATE first)
    done = set()
    for f in glob.glob(f'{CACHE}/tapes/chunk_*.parquet'):
        done |= set(pd.read_parquet(f, columns=['cid']).cid.unique())
    for f in glob.glob(f'{CACHE}/tapes/empty_*.json'):
        done |= set(json.load(open(f)))
    jobs = [j for j in jobs if j[1] not in done]
    log('tape jobs', len(jobs), 'already done', len(done))

    def fetch(job):
        ref, cid, st, en = job
        try:
            rows, src, cov = pm.market_trades(cid, start=st, end=en, taker_only=True)
        except Exception as e:
            return cid, None, str(e)[:100]
        return cid, rows, cov.status

    buf, empties, n_chunk = [], [], len(glob.glob(f'{CACHE}/tapes/chunk_*.parquet'))
    t0 = time.time()
    cols = ['timestamp', 'side', 'asset', 'price', 'size', 'proxyWallet', 'outcomeIndex', 'transactionHash']
    with ThreadPoolExecutor(4) as ex:
        for i, (cid, rows, st) in enumerate(ex.map(fetch, jobs)):
            if rows:
                d = pd.DataFrame(rows)
                d = d[[c for c in cols if c in d.columns]].copy()
                d = d[d.timestamp < H]
                d['cid'] = cid
                d['cov'] = st
                buf.append(d)
            else:
                empties.append(cid)
            if (i + 1) % 200 == 0 or i == len(jobs) - 1:
                if buf:
                    pd.concat(buf, ignore_index=True).to_parquet(f'{CACHE}/tapes/chunk_{n_chunk:04d}.parquet')
                    n_chunk += 1
                    buf = []
                if empties:
                    json.dump(empties, open(f'{CACHE}/tapes/empty_{n_chunk:04d}_{i}.json', 'w'))
                    empties = []
                log('tapes', i + 1, '/', len(jobs), round(time.time() - t0), 's')


if __name__ == '__main__':
    phases = sys.argv[1:] or ['activity', 'gamma', 'tapes']
    for p in phases:
        globals()[f'phase_{p}']()
