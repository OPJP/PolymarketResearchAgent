# GoodFallen (`0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6`)

Leaderboard rank 210 (monthly PnL). Verdict: **REJECT**. Archetype: BTC 5-minute Up/Down bot (three-wallet cluster).

Profile: https://polymarket.com/profile/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6

## Mechanism

Trades only BTC 5-minute windows, buying both outcomes in most windows at a median pair cost of 1.013; 33% maker fills on-chain. Its taker buys roughly break even before rebates (+0.3% held out); its maker fills earn +3.3% (p=0.097). The maker side is spot-reactive: fills come right after a 2-5 s spot move toward the bought side, strongest at 1 s on Binance, gone by 5 s. The three wallets share thousands of transactions, mostly quoting side by side; direct fills against each other are under 0.5% of each wallet's taker volume. Observed taker-rebate tier Obsidian (50% of fees); 30-day PnL at the 0% tier $24,219, Gold $38,297, Diamond $58,632, Obsidian $63,325.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 74d: HAC t=4.9, Holm p=1.3e-02, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $63,059; median month $62,212 |
| Constant returns (low std) | pass | annualized Sharpe 17.3; positive weeks 100%; positive months 100% |
| High % profit | pass | 1978%/month: 30-day PnL $63,059 on peak capital at risk $3,188; counting the on-chain collateral too ($28,261), at least 201%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 33% maker fills (95% CI 27%-40%), 15% of USDC |
| Reverse-engineered rule matches the wallet | partial | spot-reactive maker, Binance spot: stratified AUC 0.634 vs rotation null 0.498 (max 0.527), p=0.005; rule flags 27% of the wallet's decisions at 2.1x the base rate (z=14.1); same on Kraken: stratified AUC 0.601 vs rotation null 0.502 (max 0.532), p=0.005; rule flags 23% of the wallet's decisions at 1.5x the base rate (z=9.8); frozen, on 2,016 unseen windows (100 rotations, so p cannot go below 0.0099): stratified AUC 0.619 vs rotation null 0.500 (max 0.507), p=0.0099; rule flags 33% of the wallet's decisions at 1.8x the base rate (z=39.8); latency taker, Binance: stratified AUC 0.519 vs rotation null 0.507 (max 0.520), p=0.01; rule flags 6% of the wallet's decisions at 1.6x the base rate (z=2.7); directional maker (fair - price): stratified AUC 0.459 vs rotation null 0.495 (max 0.521), p=1.00; rule flags 12% of the wallet's decisions at 1.2x the base rate; Holm over the six families tested leaves the spot-reactive p far below 0.01 (z >= 9); the full bar is met on the 288-window TEST sample but not confirmed on the larger unseen sample (lift below 2 there), so partial |
| Rule profitable in held-out PIT backtest | fail | with correct fill timing (block-time slack 2 s) 0 of the 128 FIT configurations were profitable (best -6.9%); the best one, frozen (theta 5e-05, delta 0.04, 2 s move, requote 1 s, 2 s latency), on 2,011 unseen resolved windows: rest of the TEST week strict -5.7% (2,705 fills, p(profit)=1.00); the day after as_of strict -8.7% (1,124 fills, p(profit)=1.00); all, first-in-queue -5.3% (4,575 fills, p(profit)=1.00); at the size the tape allows it would lose about $9,305 a month; without the slack (optimistic): strict +2.5% (1,783 fills, p(profit)=0.12); same rule on the standard TEST sample (no slack) strict +6.8% (80 fills, p(profit)=0.23); latency taker on Binance at 0 s spot age (not achievable) +9.1% (13,866 trades, p(profit)=0.26); same taker rule frozen on the unseen windows at >= 2 s +6.7% (74,671 trades, p(profit)=0.16); directional maker strict -12.9% (5,679 fills, p(profit)=1.00); the wallet's own maker fills +3.3%, taker buys +0.3% |
| Replicable on a normal computer and connection | fail | the matched rule shows a profit only with optimistic fill timing (an order credited with trades that may have matched before it existed) and at most 1 s of spot age; timed correctly at a normal connection's 2 s it loses about $9,305 a month at the size the tape allows, nowhere near $50k. The wallet's own month depends on the rebate tier: at 0% it is $24,219 |
| Conditions still hold now | pass | last 30 days p=1.2e-05; decline vs earlier p=0.96; last 15 vs prior 15 p=0.86; trend p=1.00 |

## Key numbers

- 30-day PnL: $63,059
- PnL at 0% rebate tier: $24,219
- Spot-reactive match (Binance): AUC 0.634, z=14.1
- Frozen rule on unseen windows (strict, 2 s slack): -6.6% (p=1.00)
- Matched rule at tape size: -$9,305/month
- Its own maker fills on the unseen windows: +3.3%

## Why this verdict

- A public spot-reactive quoting rule matches part of its behaviour on held-out windows (a partial match).
- Traded as a strategy, the matched rule loses money on 2,011 unseen windows once fills are timed correctly.
- Its own profit at a 0% rebate tier is $24,219 a month.

## Corrections after the adversarial review (2026-10-31)

- The match test now uses a rotation null; the earlier 'AUC at chance' came from the broken clock-shift null.
- The spot-reactive signature was found by the reviewer and is now a polyrea hypothesis; on Binance spot it meets the full match bar for GoodFallen and x-MoneyForWhiskas.
- 'Profit relies on cross-wallet self-trading' was overstated: sibling makers fill under 0.5% of each wallet's taker volume.
- The market-vs-model Brier figures are now computed in the study files (TEST: market 0.127, Kraken model 0.137, Binance model 0.135).

## Evidence files

- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/profile.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_study_btc_5m.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_study_btc_5m_binance.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_maker_study_btc_5m.json`
- `research/wallets/0x0ca4e9d27ff826a109ecbf74754fb66b93f277a6/updown_maker_study_btc_5m_binance.json`
- `research/stage_a/updown_btc5m_frozen_rule_extension_binance.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/stage_a/collateral.json`
- `research/review_2026-10-31/challenge-btc5m-cluster/h4_match_robust.json`
- `research/review_2026-10-31/challenge-btc5m-cluster/selftrade.json`
