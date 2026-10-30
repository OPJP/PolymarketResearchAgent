# RN1 (`0x2005d16a84ceefa912d4e380cd32e7ff827875ea`)

Leaderboard rank 24 (monthly PnL). Verdict: **REJECT**. Archetype: In-play two-sided market maker (tennis, esports, US sports).

Profile: https://polymarket.com/profile/0x2005d16a84ceefa912d4e380cd32e7ff827875ea

## Mechanism

92% of sampled fills are maker fills (on-chain, 95% CI 88-95%); 97% happen after game start. Pairs are bought at a median combined 0.98, locking +$964k of spread in 30 days, while the unmatched residual loses $319k to adverse selection. Around ESPN scoring plays, only 2.6% of its passive fills land in the 10 s after a play versus 9.7% for other makers, whose fills in that window lose 26-29%: RN1 cancels quotes within seconds of events.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 447d: HAC t=8.8, Holm p=1.0e-14, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $907,319; median month $1,152,105 |
| Constant returns (low std) | pass | annualized Sharpe 9.6; positive weeks 94%; positive months 100% |
| High % profit | pass | peak capital at risk $1.14M; 30-day PnL $907k; 79% per month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed; 92% maker |
| Reverse-engineered rule matches the wallet | fail | quote pulling after plays observed (2.6% vs 9.7% of passive fills in 0-10 s), but no public-data quoting rule reproduces its fills; most volume is tennis/esports with no public event feed |
| Rule profitable in held-out PIT backtest | fail | public-data two-sided maker on 70 held-out RN1 markets: -7.8% (0 s), -11.7% (2 s), -12.2% (5 s), -18.9% (30 s); RN1's own passive fills there +6.5% |
| Replicable on a normal computer and connection | fail | requires cancelling quotes within seconds of live events; stale passive fills right after scoring plays lose 26-29% for other makers |
| Conditions still hold now | pass | last 30 days significant (p=0.0025); no decline (p=0.41) |

## Key numbers

- 30-day PnL: $907,319
- Monthly ROC: 79%
- 30-day fills / volume: 248,770 / $64.7M
- Locked pair spread (30 d): +$963,976
- Residual adverse selection (30 d): -$319,040
- Slow imitator, held out: -7.8% to -18.9%

## Why this verdict

- A slow two-sided maker with public data loses money in the same markets at every tested delay (0-30 s).
- RN1's edge depends on pulling quotes within seconds of live events, which needs low-latency sports and esports data.
- No public-data rule reproduces its quoting at the required significance.

## Evidence files

- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/profile.json`
- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/maker_replicability_study.json`
- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/sports_study_maker.json`
- `research/stage_a/persistence_a1_survivors.json`
