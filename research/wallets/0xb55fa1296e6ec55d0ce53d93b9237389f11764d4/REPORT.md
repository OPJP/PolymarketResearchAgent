# 0xb55fa1296E6ec55D0cE53d93B9237389f11764d4-1777575277609 (`0xb55fa1296e6ec55d0ce53d93b9237389f11764d4`)

Leaderboard rank 209 (monthly PnL). Verdict: **REJECT**. Archetype: Fee-rebate farmer on crypto Up/Down markets.

Profile: https://polymarket.com/profile/0xb55fa1296e6ec55d0ce53d93b9237389f11764d4

## Mechanism

467k fills in 30 days across BTC/ETH/SOL 5m, 15m, hourly and 4h windows; 30% maker fills (on-chain, 95% CI 24-37%). Settled market PnL -$48.6k (locked pair spread -$90.2k, residual +$41.6k). Taker fees -$157.3k, taker rebate +$96.7k (61% of fees), maker rebate +$8.7k: incentives are 92% of its total PnL.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 152d: HAC t=4.8, Holm p=7.8e-04, bootstrap p=2.5e-04; deflated Sharpe 0.991 |
| Net profit above $50k/month | pass | last 30d $56,365; median month $78,075 |
| Constant returns (low std) | pass | annualized Sharpe 7.5; positive weeks 81%; positive months 100% |
| High % profit | pass | peak capital at risk $64.9k; 30-day PnL $56.4k; 87% per month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 30% maker |
| Reverse-engineered rule matches the wallet | fail | BTC 5m (10% of its volume): spot-latency taker AUC 0.483 (perm p=0.99), directional maker AUC 0.498 (p=0.97) |
| Rule profitable in held-out PIT backtest | fail | public-data maker -17.7% (p>0.99 for loss); fitted taker rule +2.6% (p=0.34); its own trading is loss-making before rebates (-$48.6k in 30 days) |
| Replicable on a normal computer and connection | fail | profit exists only above the Platinum rebate tier: at 0% -$40.3k/month, Gold -$12.0k, Platinum +$10.0k; tiers need $1M-$10M of 30-day weighted volume |
| Conditions still hold now | pass | last 30 days significant (p=0.034); no significant decline (daily mean $3.5k -> $1.9k, p=0.09) or trend (p=0.53); profit depends entirely on the Taker Rebate Program, in force today but changeable by Polymarket |

## Key numbers

- 30-day PnL: $56,365
- Trading PnL after fees: -$48,609
- Taker rebate received: $96,666
- PnL at 0% rebate tier: ~-$40,300
- 30-day volume: $8.3M

## Why this verdict

- The strategy loses money on trading; the profit is Polymarket's fee rebate.
- A replicator without the top rebate tier would lose money.
- No public-data rule matches its decisions.

## Evidence files

- `research/wallets/0xb55fa1296e6ec55d0ce53d93b9237389f11764d4/profile.json`
- `research/wallets/0xb55fa1296e6ec55d0ce53d93b9237389f11764d4/updown_study_btc_5m.json`
- `research/wallets/0xb55fa1296e6ec55d0ce53d93b9237389f11764d4/updown_maker_study_btc_5m.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
