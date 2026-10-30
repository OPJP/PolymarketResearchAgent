# GoodFallen (`0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6`)

Leaderboard rank 210 (monthly PnL). Verdict: **REJECT**. Archetype: BTC 5-minute Up/Down bot (multi-wallet cluster).

Profile: https://polymarket.com/profile/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6

## Mechanism

Trades only BTC 5-minute Up/Down markets: 252k fills in 30 days, buying both outcomes in 94% of windows at a median pair cost of 1.0125. 33% of sampled fills are maker fills. Bought shares win 1-2 points more often than their price at every price level. It shares 4,845 transactions with dangerously-skip-permissions and 1,866 with x-MoneyForWhiskas; in sampled shared transactions about a quarter are the cluster's wallets filling against each other. 30-day income: gross trading $98.9k, taker fees -$78.2k, taker rebate +$38.8k (50%), maker rebate +$3.5k.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 74d: HAC t=4.9, Holm p=1.6e-03, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $63,059; median month $62,212 |
| Constant returns (low std) | pass | annualized Sharpe 17.3; positive weeks 100%; positive months 100% |
| High % profit | pass | peak capital at risk $3.2k; 30-day PnL $63.1k |
| Trades verified on-chain | pass | 150/150 sampled fills confirmed; 33% maker |
| Reverse-engineered rule matches the wallet | fail | spot-latency taker rule: held-out AUC 0.556 vs null 0.573 (perm p=0.95), flat lag scan; directional-maker rule: AUC 0.485 (p=0.96) |
| Rule profitable in held-out PIT backtest | fail | public-data taker rule -2.3% on traded (288 held-out windows); public-data maker -15.6% (p>0.99 for loss); the wallet's own taker buys +0.3% (p=0.41), maker fills +3.2% (p=0.10) |
| Replicable on a normal computer and connection | fail | market price beats a 1-second public spot model (Brier 0.170 vs 0.218); edge is sub-second; profit relies on cross-wallet self-trading and the 50% Obsidian rebate (at 0%: ~$24k/month) |
| Conditions still hold now | pass | last 30 days significant (p=1e-7), no decline; depends on the Taker Rebate Program (since 2026-05-28) staying unchanged |

## Key numbers

- 30-day PnL: $63,059
- Fills (30 d): 251,974
- Taker rebate share of PnL: 62%
- PnL at 0% rebate tier: ~$24,200
- Shared tx with sibling wallets: 6,711
- Public-data maker, held out: -15.6%

## Why this verdict

- No reverse-engineered rule matches its decisions: both the taker and maker hypotheses are at chance on held-out windows.
- Rules built from public data lose money in the same windows, at any latency.
- It is one of three coordinated wallets that trade against each other, and below the top rebate tier its month falls under $50k.

## Evidence files

- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/profile.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_study_btc_5m.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_maker_study_btc_5m.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
