# RN1 (`0x2005d16a84ceefa912d4e380cd32e7ff827875ea`)

Leaderboard rank 24 (monthly PnL). Verdict: **REJECT**. Archetype: In-play two-sided market maker (soccer, tennis, CS2, US sports).

Profile: https://polymarket.com/profile/0x2005d16a84ceefa912d4e380cd32e7ff827875ea

## Mechanism

92% of sampled fills are maker fills on-chain. Complete pairs bought at a median combined 0.982 lock $963,976 in 30 days; the unmatched residual loses $319,040 to adverse selection. Soccer is about 45% of its volume (tennis and esports 40%). Its best families are college football, the WTA, the Champions League, CS2, La Liga and the ATP; NFL and the 'other' soccer leagues lose. Around ESPN scoring plays 1.4% of its passive fills land in the first 5 s (all makers: 4.9%), and makers' fills there lose 26%; after soccer goals it is 6% of touch fills against 13% for other makers, already before the first public price jump (ESPN's timestamp trails that jump by a median 3.5 s).

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 447d: HAC t=8.8, Holm p=4.5e-12, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $907,319; median month $1,152,105 |
| Constant returns (low std) | pass | annualized Sharpe 9.6; positive weeks 94%; positive months 100% |
| High % profit | pass | 79%/month: 30-day PnL $907,319 on peak capital at risk $1,141,785; counting the on-chain collateral too ($2,105,457), at least 28%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 92% maker fills (95% CI 88%-95%), 93% of USDC |
| Reverse-engineered rule matches the wallet | partial | no public rule predicts which fills are RN1's: reviewer own-tape calm AUC 0.531 (p=0.59), sibling-market jumps 0.563 (p=0.12), ESPN time-since-goal 0.547 (p=0.18). It is significantly absent after ESPN-timed soccer goals (6.0% vs 12.9% of touch fills, p=0.0005, 23 of 32 held-out games), but that describes when it is gone, not when it pulls out |
| Rule profitable in held-out PIT backtest | fail | all families: tape-only two-sided maker on 70 held-out markets -7.8% to -18.9% at 0-30 s (strict), -5.1% to -8.7% at 0-5 s with first-in-queue fills; the wallet's own passive fills there +6.5% (p=0.30); only its profitable families (WTA, ATP, CS2, UCL, La Liga, Serie A, CFB): tape-only two-sided maker on 79 held-out markets -8.3% to -12.8% at 0-30 s (strict), -8.3% to -10.9% at 0-5 s with first-in-queue fills; the wallet's own passive fills there -0.9% (p=0.57); reviewer pause-after-goal maker -2.9% to -5.3% strict, about 0% at-touch (p 0.45-0.82) |
| Replicable on a normal computer and connection | fail | nearly all its volume is in markets with a 1 s delay on incoming taker orders; RN1 cancels inside that delay, before the public price moves, while other makers' fills right after plays lose heavily: copying it needs a sub-second race or a private data feed |
| Conditions still hold now | pass | last 30 days p=0.0077; decline vs earlier p=0.42; last 15 vs prior 15 p=0.60; trend p=1.00 |

## Key numbers

- 30-day PnL: $907,319
- PnL at 0% rebate tier: $829,876
- Locked pair spread (30 d): $963,976
- Residual adverse selection (30 d): -$319,040
- Other makers' fills 0-5 s after a play: -25.6%

## Why this verdict

- A public-data maker loses money in the same markets at every delay tested, including in RN1's most profitable families.
- Its edge is being off the book before the public price moves, which needs faster-than-public game data.
- No public rule reproduces which fills it gets.

## Corrections after the adversarial review (2026-10-31)

- Soccer, not tennis/esports, is its largest family (about 45% of volume), and ESPN publishes soccer event times; the reviewer's soccer test is now part of the record.
- ROC 79% counts only open positions; with its $1.5-2.4M of on-chain collateral it is still about 28% a month.
- The at-touch bound promised by the methodology is now computed for the tape-only maker.

## Evidence files

- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/profile.json`
- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/maker_replicability_study.json`
- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/maker_replicability_study_profitable_families.json`
- `research/wallets/0x2005d16a84ceefa912d4e380cd32e7ff827875ea/sports_study_maker.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/stage_a/collateral.json`
- `research/review_2026-10-31/challenge-inplay-maker-RN1/results_summary.json`
- `research/review_2026-10-31/challenge-inplay-maker-RN1/soccer_window_test.json`
