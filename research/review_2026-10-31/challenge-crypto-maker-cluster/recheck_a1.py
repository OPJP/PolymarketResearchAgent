import json, sys
sys.path.insert(0, '/home/user/PolymarketResearchAgent')
import numpy as np
from polyrea.adapters.polymarket import PolymarketData
from polyrea.workflows.screen import wallet_pnl_metrics, apply_criteria
from polyrea.workflows.investigate import default_as_of
from polyrea.analysis.pnl import daily_frame
from polyrea.stats import significance as S
from polyrea.stats.persistence import persistence_report

W = {'bosona': '0xc2ad03f79ca3f3c17d8c7de2612ce0c89b7d40ed', 'almach': '0x3725d52f3c252e8374999cc8617292ea2608ad88'}
pm = PolymarketData()
as_of = default_as_of()
print('as_of', as_of)
out = {}
for name, w in W.items():
    data, src = pm.user_pnl(w, max_age=None)
    pts = data if isinstance(data, list) else data.get('points', data.get('history', data))
    if isinstance(data, dict) and not isinstance(pts, list):
        print(list(data.keys())); pts = list(data.values())[0]
    m = wallet_pnl_metrics(pts, as_of)
    # Holm-like bound: single test p * 500 (Holm upper bound is p*500)
    m['p_pre_x500_bonferroni'] = min(1.0, m['p_pre'] * 500)
    sr_std = 1 / np.sqrt(m['history_days'] - 1)
    df = daily_frame(pts, as_of=as_of)
    d = df['d_economic_pnl'].iloc[1:].to_numpy()
    m['deflated_sharpe_recomputed'] = S.deflated_sharpe_ratio(d, n_trials=500, sr_trials_std=sr_std)
    m['reasons_recomputed'] = apply_criteria({**m, 'p_holm_pre': m['p_pre_x500_bonferroni'], 'deflated_sharpe': m['deflated_sharpe_recomputed']})
    pr = persistence_report(d, 30)
    m['persistence'] = pr.__dict__ if hasattr(pr, '__dict__') else str(pr)
    # last 30d components
    last = df.iloc[-30:]
    m['last30_components'] = {c: float(last[c].sum()) for c in df.columns if c.startswith('d_')}
    out[name] = m
    keys = ['history_days','last_30d_pnl','median_month_pnl','monthly_pnl_recent_first','annual_sharpe','share_positive_weeks','share_positive_months','hac_t_pre','p_pre','p_pre_x500_bonferroni','p_boot_pre','deflated_sharpe_recomputed','reasons_recomputed','last30_components']
    print(name, json.dumps({k: m[k] for k in keys}, indent=1, default=str))
    print(' persistence', str(m['persistence'])[:1500])
json.dump(out, open('recheck_a1.json', 'w'), indent=1, default=str)
