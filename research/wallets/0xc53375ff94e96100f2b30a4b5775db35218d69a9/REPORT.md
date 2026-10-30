# dangerously-skip-permissions (`0xc53375ff94e96100f2b30a4b5775db35218d69a9`)

Leaderboard rank 123 (monthly PnL). Verdict: **REJECT**. Archetype: BTC 5-minute Up/Down bot (multi-wallet cluster).

Profile: https://polymarket.com/profile/0xc53375ff94e96100f2b30a4b5775db35218d69a9

## Mechanism

504k fills in 30 days, all BTC 5-minute Up/Down; buys both outcomes in 98% of windows at a median pair cost of 1.004; 35% maker fills (on-chain, 95% CI 29-42%). Shares 4,845 transactions with GoodFallen and 3,229 with x-MoneyForWhiskas, including direct fills against them. 30-day income: gross trading $179.3k, taker fees -$135.3k, taker rebate +$66.5k (49%), maker rebate +$5.8k.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 74d: HAC t=6.1, Holm p=9.7e-06, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $116,255; median month $90,095 |
| Constant returns (low std) | pass | annualized Sharpe 23.6; positive weeks 100%; positive months 100% |
| High % profit | pass | peak capital at risk $4.6k; 30-day PnL $116.3k |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 35% maker |
| Reverse-engineered rule matches the wallet | fail | spot-latency taker: held-out AUC 0.565 vs a higher null (perm p=0.99); directional maker: AUC 0.477 (p=1.0) |
| Rule profitable in held-out PIT backtest | fail | public-data taker rule -2.3% (p=0.67), public-data maker -15.6% on 288 held-out windows; its own taker buys -0.2% (p=0.56), maker fills +3.3% (p=0.03) |
| Replicable on a normal computer and connection | fail | edge invisible in 1-second public data; cross-wallet self-trading; at 0% rebate tier ~$49.7k/month |
| Conditions still hold now | pass | last 30 days significant (p=2e-9), rising; depends on the Taker Rebate Program |

## Key numbers

- 30-day PnL: $116,255
- Fills (30 d): 503,851
- Taker rebate share of PnL: 57%
- PnL at 0% rebate tier: ~$49,700
- Shared tx with sibling wallets: 8,074

## Why this verdict

- No reverse-engineered rule matches its decisions on held-out windows.
- Public-data versions lose; its own taker buys break even before rebates.
- Coordinated multi-wallet operation that trades against itself; depends on the top rebate tier.

## Evidence files

- `research/wallets/0xc53375ff94e96100f2b30a4b5775db35218d69a9/profile.json`
- `research/wallets/0xc53375ff94e96100f2b30a4b5775db35218d69a9/updown_study_btc_5m.json`
- `research/wallets/0xc53375ff94e96100f2b30a4b5775db35218d69a9/updown_maker_study_btc_5m.json`
- `research/stage_a/rebate_dependence.json`
