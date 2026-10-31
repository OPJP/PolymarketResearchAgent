"""Smallest case: buy 100 YES @0.40, sell 100 YES @0.60, market resolves NO. True PnL +$20, nothing held."""
import _env, json, pandas as pd
from polyrea.analysis.profile import per_market_decomposition, price_bucket_calibration
tr = pd.DataFrame([dict(ts=1, condition_id='C', asset='Y', outcome_index=0, side='BUY', price=.4, size=100., usdc=40., slug='x'),
                   dict(ts=2, condition_id='C', asset='Y', outcome_index=0, side='SELL', price=.6, size=100., usdc=60., slug='x')])
mk = {'C': {'conditionId': 'C', 'clobTokenIds': json.dumps(['Y', 'N']), 'outcomePrices': json.dumps(['0', '1']), 'umaResolutionStatus': 'resolved', 'closed': True, 'closedTime': '2026-10-01 00:00:00+00'}}
r = per_market_decomposition(tr, mk).iloc[0]
print(f"coded: q0={r.q0} cost={r.cost} avg0={r.avg0} pnl={r.pnl} residual_pnl={r.residual_pnl}  (truth: q0 held 0, pnl +20)")
print('calibration rows (SELL counted as a bought share at 0.6):', price_bucket_calibration(tr, mk))
