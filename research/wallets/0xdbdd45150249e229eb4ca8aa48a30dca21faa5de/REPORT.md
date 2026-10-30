# 0xdbdd45150249e229eB4cA8aa48A30Dca21Faa5de-1757094771846 (`0xdbdd45150249e229eb4ca8aa48a30dca21faa5de`)

Leaderboard rank 243 (monthly PnL). Verdict: **REJECT**. Archetype: In-play multi-sport taker (tennis, NBA, esports).

Profile: https://polymarket.com/profile/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de

## Mechanism

All 200 sampled fills are taker fills (on-chain); 99.5% occur after game start; median fill $11; peak capital at risk $33k. Bought shares win more often than their price at 0.65-0.85 (e.g. paid 0.746, won 80.7%). On 128 ESPN-covered games there is no fill spike right after scoring plays (only a small bump 10-15 s after), and direction agreement after plays is 59% vs 55% for other takers.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 321d: HAC t=5.1, Holm p=1.5e-04, bootstrap p=2.5e-04; deflated Sharpe 0.999 |
| Net profit above $50k/month | pass | last 30d $61,712; median month $102,447 |
| Constant returns (low std) | pass | annualized Sharpe 6.4; positive weeks 76%; positive months 100% |
| High % profit | pass | peak capital at risk $33.4k; 30-day PnL $61.7k; 185% per month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 0% maker |
| Reverse-engineered rule matches the wallet | fail | ESPN-covered games: direction 59% vs 55% for other takers (perm p=0.005, weak), no excess reaction (perm p=0.30); ~70% of volume is in tennis/esports/other with no public event feed to test against |
| Rule profitable in held-out PIT backtest | fail | REACT(D=10s, W=120s) on 66 held-out games: +4.6%, per-game p=0.25; wallet's own fills on those games +8.2%, p=0.19 |
| Replicable on a normal computer and connection | fail | decision inputs unknown; the testable public-data proxy is not significantly profitable |
| Conditions still hold now | pass | last 30 days significant (p=0.004); no significant decline (p=0.12) or trend (p=0.81) |

## Key numbers

- 30-day PnL: $61,712
- Monthly ROC: 185%
- Maker fill share: 0%
- Taker rebate tier: ~18% (Gold)
- Held-out rule return: +4.6% (p=0.25)

## Why this verdict

- No reverse-engineered rule matches its decisions at the required significance; the scoring-play reaction is weak (59% vs 55%).
- Most of its volume trades sports without a public timestamped event feed, so its signal cannot be reconstructed from public data.
- The best public-data proxy is not significantly profitable on held-out games (p=0.25).

## Evidence files

- `research/wallets/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de/profile.json`
- `research/wallets/0xdbdd45150249e229eb4ca8aa48a30dca21faa5de/sports_study_taker.json`
- `research/stage_a/persistence_a1_survivors.json`
