# elmcap2 (`0xed107a85a4585a381e48c7f7ca4144909e7dd2e5`)

Leaderboard rank 87 (monthly PnL). Verdict: **REJECT**. Archetype: High-probability resting bids (bond-like carry).

Profile: https://polymarket.com/profile/0xed107a85a4585a381e48c7f7ca4144909e7dd2e5

## Mechanism

98% of sampled fills are maker fills (on-chain, 95% CI 95-99%). Median fill price 0.95; 77% of resolved markets won. Income is carry on near-certain outcomes plus Polymarket holding yield ($12.4k in 30 days). Losses come from the minority of positions bought at 0.5-0.85 that resolved against it.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 1249d: HAC t=6.2, Holm p=1.7e-07, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $242,047; median month $87,128 |
| Constant returns (low std) | pass | annualized Sharpe 3.2; positive weeks 76%; positive months 86% |
| High % profit | fail | peak capital at risk $6.46M (p95 $5.35M); 30-day PnL $242k; 3.7% per month < 10% |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed on Polygon; maker share 98% |
| Reverse-engineered rule matches the wallet | na | not run: rejected at stage A2 |
| Rule profitable in held-out PIT backtest | na | not run: rejected at stage A2 |
| Replicable on a normal computer and connection | na | not assessed |
| Conditions still hold now | na | not assessed |

## Key numbers

- 30-day PnL: $242,047
- Peak capital at risk: $6,458,210
- Monthly ROC: 3.7%
- Maker fill share: 98%
- Median fill price: 0.95

## Why this verdict

- Return on capital 3.7% per month on $6.46M peak capital at risk; the pre-registered bar is 10% per month.
- Profit depends on holding yield (a Polymarket incentive program) for about 5% of PnL.

## Evidence files

- `research/wallets/0xed107a85a4585a381e48c7f7ca4144909e7dd2e5/profile.json`
- `research/stage_a/stage_a1.json`
