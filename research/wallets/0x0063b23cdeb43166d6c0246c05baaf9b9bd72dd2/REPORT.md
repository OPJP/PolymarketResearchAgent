# TommyLeePeeca (`0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`)

Leaderboard rank 258 (monthly PnL). Verdict: **REJECT**. Archetype: In-play two-sided market maker (CS2 esports).

Profile: https://polymarket.com/profile/0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2

## Mechanism

87% of sampled fills are maker fills (on-chain, 95% CI 82-91%); 99% occur after match start; 98% of volume is CS2. It buys both outcomes in 92% of markets at a median pair cost of 1.00 (balance 0.84). Locked pair spread is -$50k over 30 days and the residual +$137k, so profit comes from leaning quotes toward the side that wins rounds, which needs live round-level information.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 105d: HAC t=4.6, Holm p=3.1e-03, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $60,279; median month $58,068 |
| Constant returns (low std) | pass | annualized Sharpe 12.3; positive weeks 84%; positive months 100% |
| High % profit | pass | peak capital at risk $9.6k; 30-day PnL $60.3k; 629% per month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 87% maker |
| Reverse-engineered rule matches the wallet | fail | no public timestamped CS2 round feed exists to reconstruct its quote decisions; tape-only rule does not reproduce its fills |
| Rule profitable in held-out PIT backtest | fail | public-data two-sided maker on 80 held-out matches: -8.3% (0 s) to -9.3% (30 s), all significant losses; wallet's own passive fills there +1.9% (p=0.056) |
| Replicable on a normal computer and connection | fail | needs low-latency live game data to avoid adverse selection; at a 0% taker rebate tier its 30-day PnL would be ~$33k (< $50k) |
| Conditions still hold now | pass | last 30 days significant (p=0.013); no decline (p=0.48) |

## Key numbers

- 30-day PnL: $60,279
- Monthly ROC: 629%
- Maker fill share: 87%
- Taker rebate rate observed: 50% (Obsidian)
- PnL at 0% rebate tier: ~$32,900
- Slow imitator, held out: -8.3% to -9.3%

## Why this verdict

- A public-data maker loses significantly in the same CS2 markets at every delay tested.
- Its edge depends on live round-level information that has no free public feed.
- It relies on the 50% Obsidian taker rebate to clear $50k per month.

## Evidence files

- `research/wallets/0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2/profile.json`
- `research/wallets/0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2/maker_replicability_study.json`
- `research/stage_a/rebate_dependence.json`
- `research/stage_a/persistence_a1_survivors.json`
