# x-MoneyForWhiskas (`0x3048d65321be3497164cdfc2996f94f98a2e7537`)

Leaderboard rank 177 (monthly PnL). Verdict: **REJECT**. Archetype: BTC 5-minute Up/Down bot (multi-wallet cluster).

Profile: https://polymarket.com/profile/0x3048d65321be3497164cdfc2996f94f98a2e7537

## Mechanism

291k fills in 30 days, all BTC 5-minute Up/Down; buys both outcomes in 88% of windows at a median pair cost of 1.008; 40% maker fills (on-chain, 95% CI 34-47%). Price quantiles (0.16/0.32/0.48/0.64/0.82) and within-window timing match GoodFallen exactly. 30-day income: gross trading $120.5k, taker fees -$91.7k, taker rebate +$48.6k (53%), maker rebate +$4.7k.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 111d: HAC t=8.2, Holm p=1.4e-10, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $82,115; median month $93,219 |
| Constant returns (low std) | pass | annualized Sharpe 25.0; positive weeks 100%; positive months 100% |
| High % profit | pass | peak capital at risk $5.8k; 30-day PnL $82.1k |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 40% maker |
| Reverse-engineered rule matches the wallet | fail | spot-latency taker: held-out AUC 0.525 (perm p=0.97); directional maker: AUC 0.460 (p=0.85) |
| Rule profitable in held-out PIT backtest | fail | public-data taker rule -$6.9k (p=0.62) and public-data maker -15.6% on 288 held-out windows |
| Replicable on a normal computer and connection | fail | sub-second edge not visible in 1-second public data; cross-wallet self-trading; at 0% rebate tier ~$33k/month |
| Conditions still hold now | pass | last 30 days significant (p=7e-5), no decline (p=0.40); depends on the Taker Rebate Program |

## Key numbers

- 30-day PnL: $82,115
- Fills (30 d): 291,525
- Taker rebate share of PnL: 59%
- PnL at 0% rebate tier: ~$33,500
- Shared tx with sibling wallets: 5,095

## Why this verdict

- No reverse-engineered rule matches its decisions on held-out windows.
- Public-data versions of the strategy lose money.
- Coordinated with two sibling wallets that trade against each other; needs the top rebate tier to clear $50k/month.

## Evidence files

- `research/wallets/0x3048d65321be3497164cdfc2996f94f98a2e7537/profile.json`
- `research/wallets/0x3048d65321be3497164cdfc2996f94f98a2e7537/updown_study_btc_5m.json`
- `research/wallets/0x3048d65321be3497164cdfc2996f94f98a2e7537/updown_maker_study_btc_5m.json`
- `research/stage_a/rebate_dependence.json`
