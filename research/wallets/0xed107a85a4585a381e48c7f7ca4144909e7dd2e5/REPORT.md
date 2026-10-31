# elmcap2 (`0xed107a85a4585a381e48c7f7ca4144909e7dd2e5`)

Leaderboard rank 87 (monthly PnL). Verdict: **REJECT**. Archetype: Event carry (FOMC consensus, deadline NO) on millions of capital.

Profile: https://polymarket.com/profile/0xed107a85a4585a381e48c7f7ca4144909e7dd2e5

## Mechanism

98% of sampled fills are maker fills by count. About 107% of the 30-day settled PnL is the October 2026 FOMC book (+$257.9k on $4.39M bought at 0.92-0.97 within about 5 days of the statement); every other resolved market together lost $43.7k. The rest of the book is 'nothing happens by the deadline' NO positions bought at 0.99 or more. Idle cash is parked as complete sets in a market with no trades (JD Vance 2028: a $4M split on 2026-10-28) to earn holding yield; those sets carry no outcome risk and are no longer counted as capital at risk.

## Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Profit significant, not luck | pass | pre-selection 1249d: HAC t=6.2, Holm p=6.2e-07, bootstrap p=2.5e-04; deflated Sharpe 1.000 |
| Net profit above $50k/month | pass | last 30d $242,047; median month $87,128 |
| Constant returns (low std) | pass | annualized Sharpe 3.2; positive weeks 79%; positive months 88% |
| High % profit | fail | 4%/month: 30-day PnL $242,047 on peak capital at risk $5,708,768 (peak incl. parked complete sets $6,458,210); counting the on-chain collateral too ($648,638), at least 4%/month |
| Trades verified on-chain | pass | 200/200 sampled fills confirmed in Polygon OrderFilled events; 98% maker fills (95% CI 95%-99%), 93% of USDC |
| Reverse-engineered rule matches the wallet | partial | not run by the project (rejected at A2). Reviewer rules fitted on 2025 and tested on 2026: FOMC consensus carry AUC 0.785 vs null 0.49 (p=0.0002) but recall 26%; deadline-NO carry AUC 0.854 (p=0.0003) but precision 5.6%: each describes part of the book |
| Rule profitable in held-out PIT backtest | fail | reviewer FOMC-carry maker proxy on 2026 meetings: mean +13% per meeting over 4 filled meetings, t-test p=0.053, sign test p=0.0625; deadline-NO lost on FIT (-0.10% per market, one total loss) and earned +0.52% per market on TEST with zero losers, which says nothing about tail risk |
| Replicable on a normal computer and connection | fail | slow resting bids on public information, so technically replicable, but the carry is 0.3-6% per event: a replicator reusing the capital averages about 4% per month on peak capital, below 10% |
| Conditions still hold now | fail | last 30 days not significant (p=0.18). [last 30 days p=0.18; decline vs earlier p=0.76; last 15 vs prior 15 p=0.78; trend p=1.00] The last month is one lumpy event (the October FOMC). |

## Key numbers

- 30-day PnL: $242,047
- Peak capital at risk: $5,708,768
- Monthly ROC: 4.2%
- Share of 30-day settled PnL from the October FOMC: about 107%
- Last-30-day significance: p=0.18

## Why this verdict

- Return on capital 4.2% per month on $5,708,768 peak capital at risk; the bar is 10% per month.
- The last 30 days are not significant on their own: the month's profit is essentially one FOMC meeting.
- The public-data carry rules match parts of the book but are not significantly profitable held out.

## Corrections after the adversarial review (2026-10-31)

- Capital at risk no longer counts $4M of riskless complete sets parked for holding yield (peak $6.46M -> $5.71M; ROC 3.7% -> 4.2%).
- Settled PnL in the profile is $217.4k after the SELL-accounting fix (was $214.2k).
- Persistence was recorded 'not assessed'; the recent-window test fails (p=0.157).
- The mechanism text attributed the month to long-dated political carry; it is the October FOMC book.

## Evidence files

- `research/wallets/0xed107a85a4585a381e48c7f7ca4144909e7dd2e5/profile.json`
- `research/stage_a/persistence_a1_survivors.json`
- `research/review_2026-10-31/challenge-carry-elmcap2/capital.json`
- `research/review_2026-10-31/challenge-carry-elmcap2/h1_results.json`
- `research/review_2026-10-31/challenge-carry-elmcap2/h2_results.json`
- `research/review_2026-10-31/challenge-carry-elmcap2/replicator_roc.json`
