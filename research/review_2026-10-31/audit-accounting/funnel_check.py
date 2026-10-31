"""Funnel/report consistency: stage_a1 pass set vs verdict set, ledger.json vs README, hard-coded A1 'pass' statuses."""
import _env, json, glob, os, re
R = '/home/user/PolymarketResearchAgent/research'
a1 = json.load(open(f'{R}/stage_a/stage_a1.json'))
passers = {r['wallet'] for r in a1['wallets'] if r['stage_a1_pass']}
verd = {os.path.basename(p)[:-5].lower(): json.load(open(p)) for p in glob.glob(f'{R}/verdicts/*.json')}
print('A1 passers', len(passers), 'verdicts', len(verd), 'same set:', passers == set(verd))
print('derived a1_pass list matches:', set(a1['evidence']['derived']['a1_pass']) == passers)
led = json.load(open(f'{R}/ledger.json'))
print('ledger.json funnel:', [(f['label'], f['count']) for f in led['funnel']])
readme = open(f'{R}/README.md').read()
for f in led['funnel']:
    assert f'| {f["label"]} | {f["count"]} |' in readme, f
print('README funnel == ledger.json funnel: True')
# recompute funnel independently
rows = {r['wallet']: r for r in a1['wallets']}
alive = [w for w in verd if rows[w]['stage_a1_pass']]
for k in ['roc', 'onchain', 'match', 'backtest', 'replicable', 'persistence']:
    alive = [w for w in alive if (verd[w].get('criteria', {}).get(k) or {}).get('status') == 'pass']
    print('  ', k, len(alive))
# A1 metrics of passers vs thresholds (criteria are hard-coded 'pass' in report.a1_criteria)
c = a1['evidence']['derived']['criteria']
for w in sorted(passers):
    m = rows[w]['metrics']
    bad = []
    if m['p_holm_pre'] >= c['max_holm_p']: bad.append('holm')
    if m['p_boot_pre'] > c['max_bootstrap_p']: bad.append('boot')
    if m['deflated_sharpe'] < c['min_deflated_sharpe']: bad.append('dsr')
    if m['last_30d_pnl'] < 5e4 or m['median_month_pnl'] < 5e4: bad.append('50k')
    if m['annual_sharpe'] < 3 or m['share_positive_weeks'] < .75 or m['share_positive_months'] < .8: bad.append('consistency')
    prof = json.load(open(f'{R}/wallets/{w}/profile.json'))
    print(f'  {w[:10]} A1 last_30d ${m["last_30d_pnl"]:,.0f} vs profile window_pnl ${prof["derived"]["capital"]["window_pnl"]:,.0f}; violations {bad or "-"}; stage_a1 as_of {a1["evidence"]["subject"]["as_of"]} profile as_of {prof["subject"]["as_of"]}')
# leaderboard pnl vs series
inc = [(r['wallet'][:10], r['metrics'].get('lb_series_inconsistent')) for r in a1['wallets'] if r['stage_a1_pass']]
print('lb_series_inconsistent among passers:', inc)
