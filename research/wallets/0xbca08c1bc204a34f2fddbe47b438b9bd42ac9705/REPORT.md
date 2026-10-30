# justaluckydude (`0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705`)

Leaderboard rank 124 (monthly PnL). Verdict: **REJECT**. Archetype: In-play sports taker reacting to scoring plays.

Profile: https://polymarket.com/profile/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705

## Mechanism

All 200 sampled fills are taker fills (on-chain) and 99.6% happen after game start. Against ESPN play-by-play wall-clock times, the wallet's fills spike from a baseline of ~300 per 5-second bin to 1,274 in the first 5 seconds after a scoring play and 797 in the next 5, with no rise before plays. Within 20 seconds after a play, 95% of its buys favour the scoring side (other takers: 62%). These reactive trades are about 30% of its fills; the rest are not explained by scoring plays.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 156d: HAC t=4.8, Holm p=8.1e-04, bootstrap p=2.5e-04; deflated Sharpe 0.975 |
| Net profit above $50k/month | pass | last 30d $138,804; median month $207,103 |
| Constant returns (low std) | pass | annualized Sharpe 7.2; positive weeks 81%; positive months 100% |
| High % profit | pass | peak capital at risk $507k; 30-day PnL $139k; 27% per month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 0% maker (all taker) |
| Reverse-engineered rule matches the wallet | fail | partial: direction after scoring plays 95% vs 62% for other takers, permutation p=0.005 (86 held-out games), but this explains only ~30% of fills |
| Rule profitable in held-out PIT backtest | fail | REACT(D=0s, W=20s) on 86 held-out games: +3.8% on $1.26M traded, per-game p=0.21; wallet's own fills on the same games +3.2%, p=0.25 |
| Replicable on a normal computer and connection | fail | reacts 0-10 s after the play's wall clock, faster than public feeds or broadcast; +5 s delay: +1.0%, p=0.41 |
| Conditions still hold now | fail | last 30 days not significant (p=0.13); daily mean fell from $9.1k to $4.6k; negative trend p=0.004 |

## Key numbers

- 30-day PnL: $138,804
- Monthly ROC: 27%
- Fills within 0-5 s of a scoring play: 4.2x baseline
- Direction agreement after plays: 95% (others 62%)
- Held-out rule return: +3.8% (p=0.21)
- Recent-window p: 0.13

## Why this verdict

- The reverse-engineered reaction rule matches only the ~30% of fills that follow scoring plays.
- The rule is not significantly profitable on 86 held-out games (p=0.21), even with zero added delay.
- Speed is the edge: trades land within 0-10 s of the play; 5 s slower leaves +1.0% (p=0.41).
- The wallet's own PnL has a significant negative trend (p=0.004) and its last 30 days are not significant.

## Evidence files

- `research/wallets/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705/profile.json`
- `research/wallets/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705/sports_study.json`
- `research/stage_a/persistence_a1_survivors.json`
