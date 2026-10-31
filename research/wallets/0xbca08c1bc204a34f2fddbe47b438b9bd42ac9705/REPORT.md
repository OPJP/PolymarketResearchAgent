# justaluckydude (`0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705`)

Leaderboard rank 124 (monthly PnL). Verdict: **REJECT**. Archetype: In-play sports taker reacting to game events.

Profile: https://polymarket.com/profile/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705

## Mechanism

All sampled fills are taker fills. Within 10 s after a scoring play known 5 s after its ESPN wall clock, 95% of its buys favour the scoring side (other takers 60%). A reviewer rule reacting to any play that moves ESPN's win probability explains more: 36% of all its buys. Its profit is concentrated in college football and MLB; NBA, which dominated the held-out games, lost money. Half of the taker fees it pays come back as an Obsidian rebate.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 156d: HAC t=4.8, Holm p=4.6e-03, bootstrap p=2.5e-04; deflated Sharpe 0.975 |
| Net profit above $50k/month | pass | last 30d $138,804; median month $207,103 |
| Constant returns (low std) | pass | annualized Sharpe 7.2; positive weeks 81%; positive months 100% |
| High % profit | pass | 27%/month: 30-day PnL $138,804 on peak capital at risk $506,910; counting the on-chain collateral too ($532,394), at least 13%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 0% maker fills (95% CI 0%-2%), 0% of USDC |
| Reverse-engineered rule matches the wallet | partial | direction after scoring plays 94.8% vs null 95th percentile 64% (perm p=0.005, 86 held-out games), but the wallet is not more reactive than other takers (11% vs 15% of fills in the window, p=0.73). Reviewer WP-REACT (any win-probability swing): AUC 0.648, p=0.005, 36% of buys - significant, but most decisions stay unexplained |
| Rule profitable in held-out PIT backtest | fail | REACT(D=5 s, W=10 s) held out +1.1% (17,783 trades, p(profit)=0.40); zero-delay upper bound +4.4% (p=0.21); reviewer WP-REACT +3.2% (p=0.068); wallet's own fills on the same games +3.2% (p=0.25) |
| Replicable on a normal computer and connection | fail | the edge sits in the first seconds after a play; with a 5 s information delay the rule earns +1.1% (p=0.40) and reviewer WP-REACT goes to about zero at +5-10 s |
| Conditions still hold now | fail | last 30 days not significant (p=0.13); significant negative trend (p=0.004). [last 30 days p=0.13; decline vs earlier p=0.15; last 15 vs prior 15 p=0.26; trend p=0.004] |

## Key numbers

- 30-day PnL: $138,804
- PnL at 0% rebate tier: $113,211
- Monthly ROC: 27%
- Direction agreement after plays: 95% (others 60%)
- Held-out rule return (5 s delay): +1.1% (p=0.40)

## Why this verdict

- The reaction signature is real but explains only part of its decisions; no rule meets the match bar.
- No public-data version is significantly profitable on held-out games with a realistic information delay.
- Its last 30 days are not significant and its daily PnL has a significant negative trend.

## Corrections after the adversarial review (2026-10-31)

- The earlier headline rule (D=0 s, W=20 s, +3.8%) assumed ESPN data arrives with no delay at all; refitted with a minimum 5 s delay it chooses D=5 s, W=10 s and earns +1.1% (p=0.40).
- The earlier 'reactive share' p-value did not mean it reacts more than other takers; it does not (its distinguishing feature is direction).
- 30-day PnL includes a 50% taker-fee rebate; at the 0% tier it is $113,211 (still above $50k).

## Evidence files

- `research/wallets/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705/profile.json`
- `research/wallets/0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705/sports_study_taker.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/stage_a/rebate_dependence.json`
- `research/review_2026-10-31/challenge-inplay-taker-justaluckydude/h2_wpreact.json`
- `research/review_2026-10-31/challenge-inplay-taker-justaluckydude/challenge_summary.json`
