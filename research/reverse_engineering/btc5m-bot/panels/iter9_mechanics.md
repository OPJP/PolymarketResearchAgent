# Panel, iteration 9: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers calldata, the ladder and its copies, insertions, cancels and
lifetimes, the fan-out, sets and inventory, fees and rebates, and fingerprints of the bot.

Data I used, all development:
- `it9/cd9.parquet`, `it9/own_1231_12_18.parquet`, `it9/ins9b_M.parquet`, `b1_orders_sample.parquet`, `fills.parquet`
  (VALIDATE windows only) and `binance_1s.parquet`;
- the lab feeds `btc5m_clob_raw2` and `btc5m_venues2` for 10-31 14:55-17:55, a development block, read only through
  `live_lab.recs`, i.e. `iter_live` with `allow_sealed=False`;
- the iteration-9 code reused unchanged: `stale9.grid` and `X_of('full')` fitted on A and scored on C as in `flag9`, and
  `ins9.load_orders` / `stream_book`.

I did not open `.cache/live/sealed/` and read nothing sealed. The scripts are in my session scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`phase.py`, `series.py`, `sizetick.py`, `ttl.py`, `ttl2.py`, `peg.py`, `legs.py`, `selfmk.py`, `wslag.py`, `slot1.py`,
`first_large.py`, `first_large2.py`, `loop3.py`). I wrote nothing to the workspace except this file. Time of writing:
10-31 ~21:20 UTC.

## Critique

1. **The decision label behind the selectivity findings is censored, and the censoring rises with the move.** The
   hazard, `flag9`, `select9`, `fee9` and `overlap8` all score the same positives: won races plus the lost races that
   later got a maker fill (the M-first orders of `ins9b`). A lost race that is cancelled unfilled is not in the label.
   - By the iteration's own estimate, these unfilled lost races are about 0.45 decisions per filled order, roughly 30%
     of all decisions.
   - They are not spread evenly. In the top 3% of the FULL hazard on C, split by the Binance USD-M BTC microprice move
     toward o over [t - 500, t):

     | move (bp) | P(match) | P(labelled decision) | lost races in the label |
     |---|---|---|---|
     | 0.002-0.2 | 30.7% | 39.8% | 23% |
     | 0.2-0.5 | 19.8% | 26.4% | 25% |
     | 0.5-1 | 16.8% | 26.4% | 36% |
     | > 1 | 11.6% | 24.0% | 51% |

   - The bot loses most races on big moves. After a big move its bid at the old ask is the least likely to refill, so
     the invisible share is largest exactly where the trigger is strongest.
   - With the remainders' refill rate (0.46), P(decision) at moves above 1 bp is about 0.39, not 0.24. With a refill
     rate of 0.2 it is about 0.74.
   - The refill rate at big moves is not identified. Remainders happen almost only at small moves: 14 of 490 come after
     a move above 0.5 bp.
   - So the 1.45 decisions per filled order, the q of the PnL ceiling, "it acts about one time in four" and the AUC of
     0.58 for taken vs skipped are all conditional on the censored label.
   - The headline "another taker bought o in 80% of the skipped instants" is also what a lost race looks like by
     definition: somebody else took the ask first.
   - This has not been measured. The ghost-order attribution (iteration-6 mechanics P1 step 3, iteration-8 mechanics P3
     step 2) never ran. `pianon9` measured only the anonymous crowd's fill rate.

2. **The exit description is wrong live. Remainders rest for tenths of a second, not seconds.** I located 464 remainders
   at server ms and found the removal of 85% of them (a decrement of R with no trade within 60 ms).
   - Lifetime of unfilled remainders: p5 92 ms, p10 100 ms, p25 169 ms, median 410 ms, p75 1.13 s, p90 8.5 s.
   - Remainders that filled later: median 558 ms.
   - Per wallet median: DS 458 ms, GF 538 ms, XM 602 ms.
   - There is a hard floor at about 90-100 ms, which looks like one round trip.
   - The historical "at most a few seconds" (X35) is a block-resolution upper bound. `FINAL_RULE.md` exit and the
     strategy statement should say "about 0.1-1 s".
   - This lifetime also separates the cluster from the crowd: `pianon9` gives a 70-ms median for the anonymous
     bot-size insertions.

3. **The flagged set is diluted, and its scoring geometry penalizes a deterministic bot.**
   - 58.6% of the top-3% flagged points have no BTC perp microprice moving toward o (P(labelled decision) 10.7%). They
     are flagged by the activity and ETH/Hyperliquid terms.
   - Where Binance USD-M BTC moved toward o, P is 31%. Where it was flat, 12%. Where it moved against o, 8%.
   - The tick terms of FULL are sums in bp, so a queue-only microprice change (top-of-book size changes, price
     unchanged) carries almost no weight. Yet those are the bot's best opportunities:
     - top 3%: P(decision) 41.1% and P(match) 30.7%, against 26.2% / 17.0% for a price-level tick;
     - all grid points: 12.4% against a 4.0% base rate;
     - but only 192 of the 3,191 queue-only points reach the top 3%.
   - The label geometry (features over [t - 500, t), label over [t + 100, t + 600), reaction ~250-350 ms) caps the
     taken share of a tick's five flagged grid points. P(decision | top 1%) is 29% when the largest move toward o is in
     the last 200 ms and 17% when it is 400-500 ms old. The phase alone separates taken from skipped at AUC 0.57-0.63.
   - So select9's 0.578 measures a misaligned unit as much as the bot's selectivity.

4. **Finding 24 ("about 68% of decisions must be reproduced") assumes independent decisions within a window. That is false
   here, and it does not help a public replica at the block clock.**
   - On VALIDATE the window PnL is coupled through the size overlay. Corr(window PnL, first large order's side x
     outcome) is 0.34 pooled (each wallet's own first large: GF 0.49, XM 0.50, DS 0.27). Corr with the net large
     exposure x outcome is 0.69.
   - 65% of later large orders follow the first one's side. The first large order comes at a median of 25 s into the
     window and at order rank 9.
   - It agrees with the 4-s Binance move at the block clock 76% of the time (all orders 61%). But even with the wallet's
     own timing (an oracle), the public sign of that move gives a PnL correlation of only 0.13.
   - Condition 5 on h1/h2 is therefore bound by the own-state overlay as well as by decision overlap. The only route
     to 0.5 is a live, decoded-latency replica on future blocks. The wall account should say so.

5. **Cheap negatives** (each one measurement, so nobody needs to re-run them):
   - **No resting-order slot.** A resting remainder does not block its wallet. Among DS orders whose fills span two or
     more blocks, 13.7% had another order of the same wallet first filled as taker inside their life (17.1% expected
     under independence). The one-order limit is the in-flight HTTP submission (refractory of 120 ms or more).
   - **The fan-out is parallel, not a retry.** P(second leg within 300 ms) does not depend on the first leg's fill
     state: fully filled 26.5%, lost race 25.3%, remainder 24.2%. Second legs come a median 50-77 ms later, with p10
     4-8 ms, below the ~90-ms round trip. They are dispatched at trigger time.
   - **No cancel-all and no cancel-replace.**
     - 3 of 393 removals fall within 5 ms of another one.
     - The wallet's next decision follows a removal within 150 ms in 1.3% of cases.
     - Removals follow a venue move toward o more often than placebo (26.9% vs 14.5%), and against o less often (14.0%
       vs 18.1%). This looks like a "give up the old level when the market leaves" rule, not an adverse-tick cancel.
   - **No self-match avoidance at scale.** Only 4.6% of other takers' BUY trades on C (6.7% of their size) filled a
     cluster maker order.
   - **No stale-feed guard.** The cluster's share of all BUY takes is 2.2% when the Polymarket ws excess lag is 3 ms or
     less, and 3.4-3.9% at higher lags. The bot does not avoid lagging feeds.
   - **Being beaten does not cause skips.** P(decision | top 3%) is 18.5% when another taker buys o within 100 ms of t,
     and 21-23% at 100-600 ms.
   - **No binding copy cap.** Used copies per (wallet, burst, token, cent, size) reach 6 for DS and 10 for XM.

## Proposals (ranked by the chance of closing the gap)

### 1. Complete the decision record: recover the unfilled lost races from the book with a mechanical fingerprint, then re-score selectivity, q and the PnL ceiling (strong form of X15 / X65; iteration-6 mechanics P1 step 3 and iteration-8 mechanics P3 step 2, never run)

- **Hypothesis.** Most of the "skipped" strong-tick instants are decisions the bot made and lost, whose bids at the old
  ask were cancelled unfilled after ~0.1-1 s. The bot acts on most strong ticks. It loses the races on price-level ticks
  that everyone sees, and its lost-race bids rarely refill after big moves.
  - X72's "selection rule" would then mostly be a race outcome.
  - q would be lower than 0.69, and the PnL ceiling would be lower too: at 2 decisions per filled order, DS is about
    0.51 and XM 0.48 on VALIDATE kappa.
- **Evidence.** Critique 1:
  - the lost-race share of the labelled decisions rises from 23% to 51% with the move;
  - P(match) falls from 31% to 12%;
  - the refill rate at big moves is unmeasured;
  - "others bought o" is the signature of a lost race.

  Critique 2 gives the fingerprint: a lifetime with a ~100-ms floor and a 0.4-s median, against the crowd's 70 ms.
- **Test** (lab feeds 10-31 14:14-17:55, then 11-01 06-12 and 18-24).
  1. Truth set, positives: the 464 located remainders plus the 1,041 located maker-first insertions. Record for each:
     size (day menu 30/60/100, and menu minus the taker part), price relation (L = o's ask in the previous 300 ms),
     lifetime to removal (no trade within 60 ms), co-insertions at the fan-out lags (4-250 ms, other wallets, 0 to +1 c)
     and the 120-ms per-wallet refractory.
  2. Negatives: bot-size insertions at the old ask whose later maker fill has a non-cluster maker on chain (data-api
     `/trades` by tx, or `OrderFilled` topic2), plus `pianon9`'s crowd lifetimes.
  3. Build a mechanics-only classifier. Use no trigger features, so that the hazard test stays non-circular. Report
     precision and recall on held-out truth and negatives.
  4. Apply it to every bot-size insertion at o's old ask. Subtract a background: the same filter at levels that were
     never o's ask in the previous 300 ms, and on the non-traded outcome.
  5. Re-run `flag9`, `select9`, `fee9` and the decision count on the complete label. Report P(decision | top 1% / 3%) and
     the refill rate by move-size bin, then q, and the PnL ceiling per wallet at the new q.
- **Data.** On disk (`btc5m_clob_raw2`, cd9, own fills, `ins9b_M`); data-api trades by tx for the negatives; the next
  development blocks.
- **Signature if true.**
  - Unfilled ghost lost races concentrate at moves above 0.5 bp.
  - P(decision | top 1%) rises from 23% to at least 40%.
  - Decisions per filled order reach 2 or more, with the extra decisions on price-level ticks.
  - The refill rate at moves above 1 bp is 0.3 or less.
  - Taken-vs-skipped AUC rises above 0.65 because the skip set loses its hidden decisions.
  - Then:
    - state presence on the complete record, the brief's "has an order resting" label;
    - account for condition 5 per wallet at the corrected q. If DS and XM fall below 0.5, that is a quantified
      race-lottery wall for them;
    - retarget X72 to the remainder.
- **If false.** Ghost counts stay near the 0.45-per-filled-order estimate and are spread evenly over move sizes. Then
  1.45 stands and the selectivity is real.

### 2. The trigger is a bookTicker event, scored per event with sign features and the complete label (strong form of D1 and X52; new unit)

- **Hypothesis.** The bot evaluates on each top-of-book message of the BTC/ETH perps (sign of the microprice change, of
  any size), led by queue-depletion updates, not on bp magnitudes over a 500-ms window. Its opportunities are messages,
  not 100-ms grid points.
- **Evidence.** Critique 3:
  - queue-only microprice changes are the best opportunities: 41% decision and 31% match in the top 3%, 12.4% at all
    grid points;
  - FULL gives them almost no weight, so only 6% of them are flagged;
  - 59% of the flagged set has no BTC-perp tick toward o;
  - the grid phase alone moves P(decision) from 29% to 17%.

  The side vote, which uses signs at 0.002 bp, works at 80-86%. The hazard, which uses magnitudes, does not.
- **Test.**
  1. Events: every update of Binance USD-M BTC/ETH, OKX and Bybit L1 that moves the microprice toward o. Merge updates
     within 50 ms and apply a per-event refractory.
  2. Event features:
     - message type: size-only depletion at the touch vs a price-level change vs a refill;
     - depleted size / touch size;
     - venue;
     - number of series agreeing within 100 ms;
     - o's ask unchanged since the event vs already moved, at the event and at event + 150 ms (the bot's view, 50-150 ms
       stale);
     - fee-aware V;
     - |ask - 0.5|.
  3. Label: a decision on o in [tau + 150, tau + 700) ms, using proposal 1's complete label when it exists and the
     current one otherwise.
  4. Fit on A, score on C and on 11-01 06-12. Report the event-level P(decision) by class, the AUC within events, and
     the overlap at matched volume (decisions reproduced within +-100 ms of tau + the per-series lag).
  5. Pre-register an examinable version on `btc5m_xven` before 11-01 18-24.
- **Data.** `btc5m_venues2` (sizes are recorded), `btc5m_xven`, raw book; on disk plus the next development blocks.
- **Signature if true.**
  - Event-level P(decision) of 40% or more for the top class (queue depletion on Binance USD-M BTC with o's ask
    unchanged).
  - Within-event AUC of 0.70 or more out of sample.
  - Overlap at matched volume of 25% or more, against 8.2% for the grid hazard. This is the lever for condition 5 live.
  - If price-level ticks fall below depletion events even on the complete label, the bot's edge is reading queue
    sizes before the price moves, and the vote's sign rule is the trigger.

### 3. Decode the cancel rule (the exit and requote cadence) at server ms, and carry it into the replica's maker fills (strong form of X35 and X51; iteration-6 mechanics P1 step 2, never run)

- **Hypothesis.** Remainders and lost races are cancelled by a rule, not after "seconds". The candidates:
  - (a) a short drawn TTL;
  - (b) leave the level when o's ask moves k cents above L or when the venue composite moves on (chase);
  - (c) cancel on an adverse tick;
  - (d) cancel when the operator's set completes on o'.

  Maker fills are half of the 10-31 filled shares and 36-44% on VALIDATE. Their PnL depends entirely on this rule, and
  no replica models it.
- **Evidence.** Critique 2: the floor is about 100 ms, the median 410 ms and the tail reaches 10 s. There is no
  cancel-all and no cancel-replace. Removals follow moves toward o (27% vs 14.5% at placebo).
  - After a lost race, the next cluster decision on the same token within 1 s is 1-3 c higher in 61% of cases.
  - Same-wallet consecutive same-token decisions within 1 s are at least 1 c higher in 53-70% of cases.

  Both point to "move up with the market", not "wait".
- **Test.**
  1. Competing-risks / Cox model of the removal hazard on the 393 removals, plus the lost races' removals from the
     proposal-1 truth set.
  2. Covariates: age; o's ask - L in cents; o's bid > L (outbid); venue ticks toward / against o in the previous
     100-500 ms; a cluster decision on o in the previous 300 ms (chase); an operator fill on o' (set completed); time to
     the next burst; wallet; size.
  3. Find the smallest rule that explains at least 70% of removals within +-100 ms.
  4. Then:
     - a maker-echo fill model: a replica's lost race or remainder rests at L until the rule fires and fills against
       other takers' prints at L while it rests (`match_slack` as in the brief);
     - re-score the decoded-latency replica and the strict-fill oracle with it.
- **Data.** On disk, plus the next development blocks.
- **Signature if true.**
  - A rule with one or two parameters reproduces the lifetime distribution (KS p > 0.05) and at least 70% of removals.
  - The maker-echo model reproduces the measured refill rates (remainders 0.46 by wallet; DS 0.47, GF 0.45, XM 0.27).
  - The decoded-latency oracle with maker echoes gets closer to the wallet's PnL than the strict taker-only fills.
  - The rule also supplies the lifetime fingerprint for proposal 1.

### 4. Chase episodes as a censored readout of the reservation price (strong form of iteration-6 mechanics P4, which never ran; ties together X42, X62 and the pay-up)

- **Hypothesis.** A decision is an episode: buy o at the current ask, and keep re-entering at higher pre-signed levels
  while the reservation price R stays above the ask. The model is R = mid_o(episode start) + k Delta_o dS(composite) - c.
  - Pay-up (16%), the walk-up after lost races and the parallel second legs at 0 to +1 c are all parts of one episode.
  - The episode stops when R < ask, which is part of the selection.
- **Evidence.**
  - The walk-up of critique 5 and proposal 3.
  - `bracket9`: the bracket midpoint equals the Polymarket mid plus the venue move (corr 0.94).
  - Pay-up rises with the value above the touch (12% to 23%, `pay8`).
  - X42 tested only the block-clock level. The "decision not to chase" bound was never used.
- **Test.**
  1. Segment the complete decision record (proposal 1) into episodes: same outcome, gaps below 1 s, any wallet.
  2. Each submission at L gives R >= L. Each episode end with the next level available (the book shows o's ask at L' and
     no cluster order follows within 1 s) gives R < L'.
  3. Fit (k, c) by interval regression on A and score on C:
     - share of bounds violated;
     - c against the net fee 0.035 p(1 - p);
     - the side of weak-vote decisions as argmax_o (R_o - ask_o);
     - episode length and pay-up level as predictions.
- **Data.** On disk plus the next development blocks.
- **Signature if true.**
  - Fewer than 10% of bounds violated.
  - c within 0.5 c of the net fee.
  - k between 1 and 3, consistent with `bracket9` and the DVOL multiplier.
  - Weak-vote side of 75% or more.
  - Pay-up level predicted within a tick for at least 70% of pay-up orders.
  - The price component then covers the pay-up mode with an explicit quote function, beyond the trivial touch anchor.

### 5. A live state-machine replica for condition 5: large size on the first strong event with a flat book, then the own-net overlay, scored at the decoded latency (new; for the PnL condition on future blocks, and the account for h1/h2)

- **Hypothesis.** Window PnL is set by a few coupled large decisions. The first large order sets the side of 65% of the
  later ones, and the net large exposure explains r = 0.69.
  - Live, the large size follows the tick (`size9`: P(large | V > 0) 20% vs 3.4%).
  - A replica at the decoded latency can therefore reproduce the exposure sign much better than at the block clock,
    where even oracle timing with a public side gives 0.13 (critique 4).
- **Test.**
  1. On the development blocks of 10-31 and 11-01, run the event replica of proposal 2. Size it with:
     - large on the first top-class event of the window while the replica's book is flat;
     - large afterwards only when the replica's net is flat or long o;
     - small otherwise.
  2. Fill it at the decoded latency, with proposal 3's maker echoes.
  3. Report the per-window PnL correlation with the wallet, pooled and per wallet, and its window-bootstrap CI.
  4. Report alongside it the block-clock upper bound of critique 4 for h1/h2, as part of the wall account.
- **Data.** Development blocks only, about 72 windows per block, so pool 2-3 blocks.
- **Signature if true.**
  - Live per-window correlation of 0.3 or more where the block-clock replica gives 0.18.
  - The sign of the replica's net large exposure agrees with the wallet's in at least 70% of windows.
  - If not, condition 5 is bound by the own-state overlay at any clock, and that goes into the wall account with these
    numbers.
