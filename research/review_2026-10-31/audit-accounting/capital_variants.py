"""Capital-at-risk sensitivity: the as-coded number vs. corrected/alternative accounting.

V0 as coded (capital_and_roc)
V1 window aligned to the PnL days (pnl index D = calendar day D-1, so exposure days [end-30d, end-1d])
V2 V1 + intra-second peaks (running max inside each second, processing order) + carried-in level at day start
V3 V2 + SPLIT re-opens a merged split position (bug fix: closed_at never reset on SPLIT)
V4 V3 with complete sets (split positions) excluded from capital
Also: where the full-history raw peak lies and REDEEM/MERGE rows for conditions the ledger never saw (invisible capital).
"""
import _env, os, sys, pickle, json, collections
import numpy as np, pandas as pd
from polyrea.adapters.polymarket import PolymarketData
from polyrea.analysis import ledger as L
from polyrea.analysis.pnl import daily_frame
from polyrea.analysis.profile import resolution_info

def patched_build(wallet, activity, res_ts, fix_split=False, exclude_split=False):
    """Re-implementation of build_ledger with optional fixes; tracks events in processing order."""
    orig = L.build_ledger
    led = orig(wallet, activity, res_ts)
    if not (fix_split or exclude_split):
        return led
    # minimal re-run: copy of build_ledger with the SPLIT branch patched
    import types
    src = open(L.__file__).read()
    if fix_split:
        src = src.replace("            if pos.opened_at is None:\n                pos.opened_at = ts\n            del assets",
                          "            if pos.opened_at is None or pos.closed_at is not None:\n                pos.opened_at = ts\n            pos.closed_at, pos.close_kind = None, None\n            del assets")
    if exclude_split:
        src = src.replace("            led.exposure_events.append((ts, usdc))\n            assets = sorted", "            assets = sorted")
        src = src.replace("                released += basis if p.closed_at is None else 0.0", "                released += basis if (p.closed_at is None and not a.startswith('split:')) else 0.0")
        src = src.replace("                if p.closed_at is None:\n                    released += p.cost", "                if p.closed_at is None and not a.startswith('split:'):\n                    released += p.cost")
    key = f'ledger_patched_{int(fix_split)}{int(exclude_split)}'
    mod = types.ModuleType(key); sys.modules[key] = mod; mod.__dict__['__name__'] = key
    exec(compile(src, key, 'exec'), mod.__dict__)
    assert ('pos.closed_at, pos.close_kind = None, None\n            del assets' in src) == fix_split
    return mod.build_ledger(wallet, activity, res_ts)

def peak_variants(led, daily, aligned=True, intrasecond=True):
    end = daily.index.max(); start = end - pd.Timedelta(days=30)
    ev = led.exposure_events
    if intrasecond:
        # processing order is the append order except resolution releases; sort stably by ts only
        order = sorted(range(len(ev)), key=lambda i: ev[i][0])
        ts = np.array([ev[i][0] for i in order]); lvl = np.cumsum([ev[i][1] for i in order])
        s = pd.Series(lvl, index=pd.to_datetime(ts, unit='s', utc=True)).clip(lower=0)
        day_max = s.resample('D').max()
        carried = s.resample('D').last().shift(1)  # level carried into the day
        peak = pd.concat([day_max, carried], axis=1).max(axis=1).ffill()
    else:
        peak = led.daily_peak_exposure()
    if aligned:
        sel = peak[(peak.index >= start - pd.Timedelta(days=0)) & (peak.index < end)]
    else:
        sel = peak[(peak.index > start) & (peak.index <= end)]
    return float(sel.max()), sel.idxmax()

def run(name):
    win = pickle.load(open(os.path.join(_env.SCR, f'win_{name}.pkl'), 'rb'))
    act, markets = win['activity'], win['markets']
    res_ts = {cid: r['closed_ts'] for cid, m in markets.items() if (r := resolution_info(m))['resolved'] and r['closed_ts']}
    body, _ = PolymarketData().user_pnl(win['wallet'])
    daily = daily_frame(body.get('points') or [], as_of=win['as_of'])['d_economic_pnl'].iloc[1:]
    pnl = float(daily[daily.index > daily.index.max() - pd.Timedelta(days=30)].sum())
    led0 = L.build_ledger(win['wallet'], act, res_ts)
    v0 = L.capital_and_roc(led0, daily, 30)['peak_capital']
    v1, d1 = peak_variants(led0, daily, aligned=True, intrasecond=False)
    v2, d2 = peak_variants(led0, daily, aligned=True, intrasecond=True)
    led3 = patched_build(win['wallet'], act, res_ts, fix_split=True)
    v3, d3 = peak_variants(led3, daily)
    led4 = patched_build(win['wallet'], act, res_ts, fix_split=True, exclude_split=True)
    v4, d4 = peak_variants(led4, daily)
    full = led0.exposure_series()
    print(f'== {name}: 30d PnL ${pnl:,.0f}')
    for tag, v, d in (('V0 as coded', v0, None), ('V1 aligned', v1, d1), ('V2 +intra-second', v2, d2), ('V3 +split fix', v3, d3), ('V4 excl. complete sets', v4, d4)):
        print(f'   {tag:24s} peak ${v:>13,.0f}  ROC {pnl / v:8.2%}' + (f'  (peak day {d.date()})' if d is not None else ''))
    print(f'   raw ledger max over warm-up+window ${full.max():,.0f} at {full.idxmax()}')
    seen = {r['conditionId'] for r in act if r.get('type') in ('TRADE', 'SPLIT')}
    first_seen = {}
    for r in act:
        if r.get('type') in ('TRADE', 'SPLIT'): first_seen.setdefault(r['conditionId'], r['timestamp'])
    orphan = [r for r in act if r.get('type') in ('REDEEM', 'MERGE') and (r['conditionId'] not in first_seen or first_seen[r['conditionId']] > r['timestamp'])]
    orphan_in_win = [r for r in orphan if r['timestamp'] >= win['start']]
    print(f'   REDEEM/MERGE rows with no earlier fill in the loaded history: {len(orphan)} (in 30d window: {len(orphan_in_win)}), usdc ${sum(float(r.get("usdcSize") or 0) for r in orphan):,.0f} (window ${sum(float(r.get("usdcSize") or 0) for r in orphan_in_win):,.0f})')
    return led0

if __name__ == '__main__':
    for n in sys.argv[1:]:
        run(n)
