# 0xdbdd45150249e229eB4cA8aa48A30Dca21Faa5de-1757094771846 (`0xdbdd45150249e229eb4ca8aa48a30dca21faa5de`)

Leaderboard rank 243 (monthly PnL). Verdict: **REJECT**. Archetype: In-play multi-sport taker (soccer goals, quiet books).

Profile: https://polymarket.com/profile/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de

## Mechanism

All sampled fills are taker fills; median fill about $11. US-league fills lose (-0.75%; spreads -8.4%); everything outside the US leagues earns +$59.8k on $1.32M (+4.5%). In soccer totals, 26% of its buys fall within 60 s after an ESPN goal wall clock (other takers 10%) and 96% of those are Over. It also trades disproportionately when the book has been quiet for 10 s or more.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 321d: HAC t=5.1, Holm p=6.7e-04, bootstrap p=2.5e-04; deflated Sharpe 0.999 |
| Net profit above $50k/month | pass | last 30d $61,712; median month $102,447 |
| Constant returns (low std) | pass | annualized Sharpe 6.4; positive weeks 76%; positive months 100% |
| High % profit | pass | 185%/month: 30-day PnL $61,712 on peak capital at risk $33,408; counting the on-chain collateral too ($244,193), at least 22%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 0% maker fills (95% CI 0%-2%), 0% of USDC |
| Reverse-engineered rule matches the wallet | partial | US leagues (ESPN REACT): direction 59% vs 55% for other takers (perm p=0.005), no excess reaction (p=0.30). Reviewer rules: soccer Over after an ESPN goal hit 38% vs 11% (p=0.001); spreads lagging the moneyline matched on 141 fresh games (p=0.001). Real but narrow signatures |
| Rule profitable in held-out PIT backtest | fail | REACT(D=10 s, W=120 s) held out +4.6% (47,819 trades, p(profit)=0.25); reviewer rules: soccer goal-react -12.3% (p=0.82), spreads-lag -3.4% to -6.2% on fresh games, win-probability gap +10.1% (p=0.13, five games give all of it); wallet's own fills +8.2% (p=0.19) |
| Replicable on a normal computer and connection | fail | speed is not the binding constraint, but no public rule reproduces its choice of line and price after a goal, so there is nothing to replicate |
| Conditions still hold now | pass | last 30 days p=0.004; decline vs earlier p=0.12; last 15 vs prior 15 p=0.67; trend p=0.81. Its last three 30-day blocks were $62k, $24k and $22k after $184k, $237k and $143k; the tests do not call the decline significant, but two of the last three months were below $50k. |

## Key numbers

- 30-day PnL: $61,712
- Monthly ROC: 185%
- Profit outside US leagues: +$59.8k on $1.32M
- Taker rebate tier: Gold
- Held-out REACT return: +4.6% (p=0.25)

## Why this verdict

- Several public rules identify slices of its trading, but none reproduces most of its decisions.
- No rule that matches it is profitable on held-out or fresh games.

## Corrections after the adversarial review (2026-10-31)

- The earlier reason 'most of its volume has no public timestamped event feed' is wrong for soccer: ESPN's soccer API publishes goal times, and soccer is where it profits.
- The original ESPN test covered only US leagues, which is its losing segment.

## Evidence files

- `research/wallets/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de/profile.json`
- `research/wallets/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de/sports_study_taker.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/review_2026-10-31/challenge-inplay-taker-0xdbdd/h7_espn_soccer_result.json`
- `research/review_2026-10-31/challenge-inplay-taker-0xdbdd/h5_fresh_result.json`
- `research/review_2026-10-31/challenge-inplay-taker-0xdbdd/h3_espn_wp_result.json`
