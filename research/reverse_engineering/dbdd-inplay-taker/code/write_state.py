"""Assemble state.json from the result files of this iteration."""
import json, os
D = '/home/user/PolymarketResearchAgent/research/reverse_engineering/dbdd-inplay-taker'


def rd(n):
    p = f'{D}/{n}'
    return json.load(open(p)) if os.path.exists(p) else {}


ms = rd('model_selection_result.json'); ex = rd('explicit_rules_result.json'); ld = rd('leaders_result.json')
es = rd('espn_leadlag_result_BUILD.json'); mo = rd('markout_result_BUILD.json'); pr = rd('presence_result.json')
pick = lambda r: {k: r.get(k) for k in ['auc', 'recall', 'lift', 'precision', 'base_rate', 'perm_p_normal_approx', 'n_wallet', 'n_prints', 'n_markets'] if k in r}
hyp = []
for nm, r in (ex or {}).items():
    hyp.append({'id': nm, 'family': 'tape-microstructure (explicit)', 'description': nm,
                'validate_metrics': pick(r.get('VALIDATE', {})), 'build_metrics': pick(r.get('BUILD', {})), 'verdict': 'weak'})
if ms:
    hyp.append({'id': 'R-LGB-PUB-1', 'family': 'behaviour cloning: tape + sibling-market + metadata (LightGBM)',
                'description': 'LightGBM over point-in-time tape/sibling/metadata features, no own-state, no own size',
                'validate_metrics': pick(ms.get('lgb_public', {})), 'importance_gain_top': ms.get('lgb_public', {}).get('importance_gain'),
                'verdict': 'best so far; far below target'})
    hyp.append({'id': 'R-LGB-FP-1', 'family': 'diagnostic fingerprint (own print size added)',
                'description': 'same + log USD of the print itself (not a strategy feature)',
                'validate_metrics': pick(ms.get('lgb_fingerprint_size', {})), 'verdict': 'diagnostic only'})
if ld:
    hyp.append({'id': 'R-CLUSTER-1', 'family': 'co-trader cluster (public tape wallets)',
                'description': 'a BUILD-selected co-trader other than the printer bought the same token in [T-60,T-2]',
                'validate_metrics': {**pick(ld.get('VALIDATE', {})), 'wallet_share_leader60': ld.get('VALIDATE', {}).get('wallet_share_leader60'),
                                     'others_share_leader60': ld.get('VALIDATE', {}).get('others_share_leader60')},
                'n_leaders': len(ld.get('leaders', [])), 'verdict': 'real signal (2x enrichment); add to model next iteration'})
if es:
    hyp.append({'id': 'D-ESPN-GOAL', 'family': 'soccer score feed (ESPN wall clock), descriptive lead-lag on BUILD',
                'description': 'timing of prints relative to the nearest ESPN goal wall clock',
                'build_metrics': {'wallet': es.get('wallet'), 'others': es.get('others')}, 'verdict': 'see NOTES'})
if mo:
    hyp.append({'id': 'D-MARKOUT', 'family': 'informed-trading diagnostic (future prices; descriptive only)',
                'description': 'bought-token price change 5 s..10 min after the print and to resolution, wallet vs others (BUILD)',
                'build_metrics': {'wallet': mo.get('wallet'), 'others': mo.get('others')}, 'verdict': 'wallet strongly informed on a minutes horizon'})
if pr:
    hyp.append({'id': 'P-LGB-1', 'family': 'presence (market, 10 s bin) LightGBM', 'description': 'tape state at bin start',
                'validate_metrics': {k: pr.get(k) for k in ['pooled_auc', 'within_market_auc', 'bins_validate', 'pos_validate']}, 'verdict': 'see NOTES'})
best = ms.get('lgb_public', {})
state = {
    'strategy': 'dbdd-inplay-taker', 'wallet': '0xdbdd45150249e229eb4ca8aa48a30dca21faa5de',
    'primary_metric': "sel_auc: within-market selection AUC on VALIDATE (wallet taker BUY prints vs other takers' BUY prints, in-play, same-market pairs only, no own-state features)",
    'split': {'H': 1792713600, 'BUILD': [1790121600, 1791849600], 'VALIDATE': [1791849600, 1792713600], 'unit': 'gameStartTime (fallback first wallet fill)'},
    'preregistered': {'flag_threshold': "top 15% of scores within each market's print population", 'p_value': 'stratified rank-sum (within-market permutation null, normal approx.)', 'decision_lag_s': 2},
    'best': {'rule_id': 'R-LGB-PUB-1', 'validate_metrics': pick(best)},
    'hypotheses': hyp,
    'data_sources': [
        'data-api /activity full history 2025-11-12..2026-10-22 (509,053 rows)',
        'gamma markets_by_condition for 14,020 markets traded since 2026-09-21',
        'data-api /trades takerOnly full tapes for all 13,262 markets traded with game start in [2026-09-23, H) (3.25M taker rows)',
        'ESPN soccer summaries keyEvents for 500 matched games (13,363 key events with wall clocks)'],
    'iterations': [{'n': 1, 'minutes': 60, 'best_validate_score': best.get('auc'),
                    'families': ['tape-microstructure explicit rules', 'LightGBM behaviour cloning (tape+sibling+metadata)', 'co-trader cluster', 'ESPN soccer goal lead-lag', 'markout/informedness diagnostic', 'presence model']}],
}
json.dump(state, open(f'{D}/state.json', 'w'), indent=1, default=float)
print('state written; best', state['best'])
