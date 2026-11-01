# Panel, iteration 5: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that covers where the PnL comes from, whether
the wallets are one strategy, what the unit of decision is, and whether the metrics measure the decision. I ran a few
small checks on development data only (BUILD and VALIDATE fills in `.cache/re/btc5m-bot/fills.parquet`, the calldata
sample, the 10-31 13:00-13:22 live development block through `live_lab.load_books`, and data-api activity bounded
below H). Nothing sealed was read. Each number below can be reproduced from those inputs.

## Critique

1. **The taker rebate exists, and it is most of the money. NOTES B6 and FINAL_RULE are wrong on this.**
   - Data-api `/activity` has a `TAKER_REBATE` type. The polyrea adapter's `ACTIVITY_TYPES` leaves it out, and so do
     `REFERRAL_REWARD`, `DEPOSIT`, `WITHDRAWAL` and `MIGRATION`. The API lists 13 valid types.
   - Each wallet receives one row a day, and it equals 0.500 of the previous UTC day's BTC 5m taker fees, every day
     10-10..10-22, for XM, DS and GF alike.
   - VALIDATE week income:

     | source | amount |
     |---|---|
     | taker rebates (XM $2.4k, DS $18.4k, GF $10.1k) | $30.9k |
     | maker rebates | $3.1k |
     | trading PnL after fees | +$4.4k |

   - The trading PnL is not significant: t = 0.50 over 1,904 windows (DS t 0.28, GF 0.25, XM 0.67). Over 10-09..22
     trading earned +$27.3k against $75.6k of taker rebates.
   - Rebate history: XM since 06-20 ($201k), DS since 07-19 ($112k), GF since 07-20 ($63k), W4 0xd84403ef since 07-24
     ($36k). GF's first payments include $10 and $50, the Bronze and Silver level-up bonuses in `polyrea/analysis/rebates.py`.
   - So the significance screen is met by income that is a fixed function of fee volume. The premise ("not luck") does
     not require an information edge in the quiet orders.

2. **The taker edge is about the fee, and the quiet orders are break-even after the rebate.** Gross settlement edge per
   taker share divided by p(1-p):

   | period | DS | GF | XM | full fee rate |
   |---|---|---|---|---|
   | pre-switch BUILD | 0.085 | 0.076 | 0.077 | 0.070 |
   | VALIDATE | 0.067 (se 0.008) | 0.060 (se 0.017) | 0.062 (se 0.028) | 0.070 |

   - The ratio is flat across price buckets, at 0.05-0.09 in most of them.
   - Iteration 2's quiet taker gross of +0.63 c a share is about 0.026 p(1-p), close to the fee net of the rebate
     (0.035 p(1-p)).
   - This is what a volume taker at the rebate-adjusted break-even looks like. Looking for a hidden feed behind the
     quiet orders may be the wrong search.

3. **"One strategy split across accounts" is false. The wallets have their own trigger sensitivities, and the operator
   switched roles inside BUILD.**
   - **Hourly volume shares are fixed within a regime.** Before 10-13 14:10 UTC they were XM 0.51 (sd 0.035), DS 0.30
     and GF 0.20. After it, XM is 0.085 (sd 0.020) and DS/GF is 1.5-1.8. The step falls in the 14:10 window, with no
     outage at that time (the next whole-cluster gap is 27 min at 15:17). So configs change without restarts, which
     contradicts the "only at outages" assumption in the mechanics panel's proposal 4.
   - **The balanced, high-volume role moved from XM to DS:**

     | median abs(net)/gross | pre-switch | VALIDATE |
     |---|---|---|
     | XM | 0.13 | 0.45 |
     | DS | 0.20 | 0.12 |

   - **XM's share of orders rises with the size of the composite move:** 2.9% of orders when the largest six-series
     3-s move is at most 0.1 bp, then 4.7% at 0.5-1 bp, 10.5% at 2-5 bp and 13.5% above 5 bp. DS's share falls from
     71% to 55%. At equal move size, side accuracy is about the same for every wallet. XM's 81.6% overall, against DS's
     76.7%, comes from its mix of events.
   - **The side condition may well apply after all.** XM is one-sided in 24.3% of its windows. The examiner may apply
     the side condition to XM (one-sided in at least 20% of its windows, with halves within 3 points), so "does not
     apply pooled" does not settle it.
   - **BUILD (10-09..16) mixes two allocation regimes.**

4. **Fills are not decisions.**
   - About 28% of orders rest (take-then-rest 12%, pure resting 16%), and lost-race submissions that never fill cannot
     be seen at all.
   - Studies conditioned on a fill are biased toward quiet periods, because in moving periods the bot more often loses
     the race. "70% of live matches have no futures move" is a share of matches, not of decisions.
   - The live L2 book records sizes, and the bot's sizes (30/60/100) are rare among other traders (2.3% of their
     prints). So the submissions that did not fill are recoverable going forward. B2 (cancellations, lifetimes) was
     never measured.

5. **The decision unit spans the wallets.**
   - Live: 25.3% of cluster taker matches come within 300 ms after another cluster match on the same market (DS->GF 41,
     GF->DS 8, XM->DS 5, GF->XM 4).
   - VALIDATE taker first-fills, same outcome within ±2 s: P(DS | XM) = 0.78 and P(GF | XM) = 0.64, but P(XM | DS) =
     0.11. Participation is roughly nested (XM inside GF inside DS), which fits one signal with per-wallet thresholds.
   - W4 made only 4.6% of the "other trades" in the 0.5 s before cluster matches. The bursts the bot joins are mostly
     other traders. It also means X5 alone will not move the baseline much.

6. **The PnL-correlation target may be capped by the execution lottery, not by the rule.**
   - Per-window trading PnL of the sibling wallets correlates DS-GF 0.20, DS-XM 0.00 and GF-XM 0.15. Pooled per-window
     SD is $203, with variance shares GF 0.52, DS 0.38 and XM 0.10.
   - Even the operator's own wallets, run by the same engine, do not reproduce each other's per-window PnL. Better fill
     replay will not take 0.18 to 0.5.

7. **Checked and not supported** (so nobody redoes them):
   - Own-wallet inventory rebalancing as the side rule: each wallet buys its own less-held outcome in 49-55% of orders,
     and 50-57% in no-move seconds.
   - A copy budget per ladder level: filled copies per (wallet, burst, outcome, price, size) are mostly 1 (99th
     percentile 3-4, max 6-10). On levels that used both sizes, the large order came first in 53%, so the bot does not
     use up its small copies first.
   - Delta-scaled tiny moves in no-move seconds: the sign of the sub-0.1-bp composite or ETH move agrees 49-55% even in
     the top quartile of FV-unit move, and model accuracy in no-move seconds falls as delta rises (0.68 to 0.60).
   - Trade-side convention in `live_trigger.py`: verified. All 252 recorded events of cluster taker transactions are
     BUY on the bot's own token.

## Proposals (ranked by chance of closing the gap)

### 1. A value threshold net of the rebate: fire when (FV - ask) >= k p(1-p) (strong form of H4 and B3; new X13)

- **Hypothesis.**
  - The bot submits the pre-signed ladder order at the ask whenever its fast fair value beats the ask by a
    fee-shaped margin, k p(1-p), with k between the net-of-rebate fee (0.035) and the full fee (0.07).
  - Moving-regime orders are large FV jumps.
  - Quiet orders are the marginal cases, where the ask sits within the margin of FV. The cause may be a maker repricing,
    other takers consuming levels, small composite drift, or time decay. A private feed is not needed.
  - This is a level rule, not an event rule, which is why the event studies find no trigger.
- **Evidence.**
  - Rebates are about 80% of income.
  - Taker gross edge is about 0.06-0.085 p(1-p), and the quiet orders' edge is about 0.026 p(1-p), close to the 0.035
    net fee.
  - H4 was rejected with a crude Binance-only FV whose residual IQR is ±5 c. That is far too noisy to find a margin of
    about 1 c.
- **Test.**
  1. Live development blocks, as a revealed-preference fit. Build three FV families per 100-ms slice and outcome:
     - (a) Polymarket microprice 200 ms earlier plus beta(tau, moneyness) times the composite move since then (stale
       quote);
     - (b) a digital on the Chainlink-basis-adjusted composite, with the window's strike from RTDS and sigma fitted on
       BUILD;
     - (c) a blend of the two.
  2. Compute x = (FV - ask)/(p(1-p)), and fit a monotone hazard of each wallet's taker match within 300 ms on x.
  3. Two-sided check: for opposite-outcome cluster orders within 1 s, test whether FV moved enough between them for both
     to clear the margin. If it did not, no single FV rule with k > 0 exists, and the side choice in two-sided bursts is
     not value-based. That is decisive either way.
  4. Historically on VALIDATE: the markout of each taker order (the implied price from others' prints 5-15 s later minus
     the fill price) divided by p(1-p), quiet against moving and per wallet. Then add x (and x times wallet) to the
     block-second presence model and the side model.
- **Data.** `iter_live` `clob_crypto` (L2), `rtds`, `btc5m_bnfut` quotes, the VALIDATE tapes and venues already cached,
  and the cluster's fills.
- **Signature if true.**
  - A step in the hazard at the same normalised threshold in quiet and moving periods.
  - Quiet-order markouts bunched just above k, with a cents value that scales with p(1-p).
  - Per-wallet thresholds with k_DS < k_GF < k_XM.
  - A presence gain over the pure baseline that rises above +0.055, because x is not a market-activity feature.
- **Signature if false.** No step in x, and quiet markouts near zero or flat in cents. Then the bot is a volume
  generator, its quiet side is a by-product, and the honest account is quantitative: about 80% of income is a fixed
  50% of fees.

### 2. Per-wallet decision rules and a role switch at 10-13 14:10 UTC (strong form of C1/C4; extends the mechanics panel's proposals 4-5; new X14)

- **Hypothesis.**
  - One engine computes the signal, and each wallet fires when the signal clears its own threshold, with its own size
    menu.
  - The operator reassigns roles live, without a restart. DS is now the low-threshold volume wallet and XM the
    high-threshold directional one.
  - Pooled models fit a mixture of three thresholds and two regimes.
- **Evidence.** See critique 3: fixed hourly shares, the step at 10-13 14:10 without a gap, the abs(net)/gross swap, XM's
  share rising from 2.9% to 13.5% with move size, equal side accuracy at equal move size, and nested participation
  (critique 5).
- **Test.**
  1. Per wallet, fit P(fires within 1 s | composite move in bp and in FV units, x from proposal 1, price) separately on
     pre-switch BUILD, post-switch BUILD (10-13 14:10..10-16) and VALIDATE. Read off thresholds and slopes.
  2. Run minute-level change-point detection on per-wallet share, size mix, no-move share and abs(net)/gross over all
     history back to July (V1 logs and TAKER_REBATE rows). Check whether switches fall at outages, at operator hours
     (10-13 14:10 and the 10-19 13:40 restart are both around 13:40-14:10 UTC on weekdays) or at tier events.
  3. Retrain presence and side per wallet, or with wallet x regime interactions, on post-switch BUILD only. Report each
     wallet's presence gain, with DS now marginal at +0.052, and XM's side accuracy on all of XM's own one-sided
     seconds. 4,033 of XM's 10,749 one-sided seconds are seconds where a sibling bought the other outcome; they have no
     pooled side prediction today.
- **Data.** `fills.parquet`, the venue and alt caches, and chain or activity history before 10-09.
- **Signature if true.**
  - Thresholds are stable within a regime and jump at the switch.
  - Per-wallet models beat the pooled model on DS presence gain and XM side, and both halves hold.
  - `evaluate` should carry a regime detector, because a switch inside an exam lot would otherwise break the rule
    silently.

### 3. Decode submissions, not fills: lost races and resting remainders from the live L2 bid side (strong form of B2; new X15)

- **Hypothesis.** The bot submits more often than it fills, mostly in moving periods, where it loses races. The fill
  record under-samples moving-period decisions, so the quiet share of decisions is smaller than 70%. The unfilled
  remainders also show the cancel policy (lifetime), which drives the maker fills: 18% of gross volume and 77% of
  trading PnL in 10-09..22 (+$21.0k of +$27.3k).
- **Evidence.**
  - About 28% of orders rest.
  - Resting fills come 0-2 s after the race (median 0 s), and pure resting orders have one fill (median), which points
    to short lifetimes or cancels.
  - The lost-race test matched 69-83%.
  - Bot sizes make up only 2.3% of other traders' prints, and the recorder stores sized L2.
- **Test.**
  1. On `clob_crypto` development blocks, detect bid-level size increments on a token of exactly 30/60/100 (or a cluster
     remainder size) at a price that was the best ask within the previous 300 ms.
  2. Link them to later cluster fills by token, price and size. The unlinked ones are unfilled submissions.
  3. Measure lifetime until the level shrinks without a trade (a cancel) against fills.
  4. Redo the live trigger study on all submissions, with matches as a subset, and on the first submission of each
     event (proposal 4).
- **Data.** `iter_live` `clob_crypto`, and the cluster's on-chain fills and calldata for the same blocks.
- **Signature if true.**
  - Unfilled bot-sized insertions cluster right after composite moves.
  - They are cancelled after a fixed time, or live until resolution.
  - The quiet share of decisions falls well below the 70% of matches, and the trigger study's agreement with venue
    moves rises.

### 4. The decision event across four wallets (strong form of D1/C1; extends X5; new X16)

- **Hypothesis.** The unit is the operator's fire event. One signal fans out to the wallets that clear their thresholds,
  in a fixed submission order (DS before GF in 41 of 49 DS/GF pairs live). Per-wallet fills are thinned copies, and the
  presence label pools them.
- **Evidence.** 25.3% of live taker matches come within 300 ms after another cluster match. Historically participation
  is nested. One process signs XM -> DS -> GF -> W4.
- **Test.**
  1. Cluster all four wallets' live matches (and the submissions from proposal 3) into events: same window and outcome,
     within 300-500 ms.
  2. Measure event size, order and inter-wallet lags (fixed lag = sequential submission by one process).
  3. Run the trigger event study on first submissions only.
  4. Historically, use an event-level presence label (any of the three scored wallets, with W4 and confirmed siblings
     removed from the features) and report per-wallet participation given an event.
  5. Run a sibling census on the calldata sample: wallets with the burst schedule, signatureType 3, a 317-byte signature
     and salt/timestamp uniform on [0, 1].
- **Data.** Live development blocks, the calldata sample, and W4's fills (data-api activity or OrderFilled logs for the
  same blocks).
- **Signature if true.** Constant inter-wallet lags inside events, participation predicted by event strength rather than
  market activity, and a sharper trigger lead-lag on first submissions than on all matches.

### 5. A ceiling on PnL correlation and an honest outcome account (strong form of D4; new X17)

- **Hypothesis.**
  - Per-window PnL is an execution lottery on two-sided volume: abs(net) is 12% of gross for DS. A faithful decoded
    rule therefore cannot reach a per-window PnL correlation of 0.5 under strict fills.
  - The money is a fixed function of fee volume.
- **Evidence.** Sibling wallets' per-window PnLs correlate 0.00-0.20 with each other. Trading PnL is not significant on
  VALIDATE (t 0.50), and the rebate is exactly 50% of fees.
- **Test.**
  1. Estimate a replication ceiling. Resample each cluster order's fill outcome at its empirical fill probability (given
     its race context), recompute per-window PnL, and correlate it with the actual. Compare with the sibling
     correlations and with oracle-side or oracle-volume proxies.
  2. Report the outcome as economic PnL per window (trading + 0.5 x taker fees + maker rebate share). Check that a
     rule's predicted fee volume per window tracks the wallet's: predicted shares correlate 0.875 already.
- **Data.** `fills.parquet`, the calldata sample (race context) and TAKER_REBATE rows (development periods only).
- **Signature if true.** The resampled ceiling is far below 0.5 (sibling-like 0.2-0.4), while predicted fee volume (the
  income) tracks the wallet at above 0.8. Effort should then move from fill replay to proposals 1-4, and FINAL_RULE
  should state the ceiling with numbers.
