# Panel after iteration 5: assumption breaker

Lens: what the investigation takes for granted that may be false. That covers whose orders the quote model describes,
which decision produces the fills, the unit and target, the queue test, where the PnL comes from, and who flips the
BTC 5m switch. Written 2026-10-31 at about 15:20 UTC.

Data used, development only:
- STUDY (2026-10-23..26) calldata and taker tapes, case by case;
- BUILD fills and windows (before H);
- the current development block's raw recording (`dm_clob_raw`, `dm_bnf`, 2026-10-31 14:06:40-14:35 UTC) and the
  calldata of the cluster's fills in it (`calldata/live1031_*`);
- two archive `eth_call`s at a pre-H block.

I did not touch VALIDATE (10-27..30) fills or anything sealed.

Check scripts are in my scratchpad:
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`
(`chain_back.py`, `burst_attr.py`, `post_trigger2.py`, `snapcheck.py`, `adj5.py`, `seq_taker.py`, `pos15.py`).
Run them from the repo root with `<start> <end>` = `1793455600 1793457300` where needed.

## Critique

1. **The iteration-5 quote law was fitted on orders nobody has shown are the cluster's. The cluster's confirmed
   orders behave differently.** "Confirmed" means a calldata-identified filled order whose posting add (exactly its
   original size, at its limit, within 5 s before the server match) was found in the raw book. There are 111 of them in
   the block.
   - **Placement.** 74% were posted at the touch, against 4.6% of 3,000 other exact-500/100 adds.
   - **Fresh, not re-priced.** 72 of the 111 (65%) have no removal of the same size on the same side in the 50 ms
     before the add. They are new orders, not a rung re-priced by cancel and re-add. Where a predecessor exists, it
     sat deep: 31 of 92 ancestors were 12 or more ticks behind the touch.
   - **Bursts carry no extra cluster signal.** Of the confirmed 500/100 orders, 58% were posted as single adds, 17% in
     pairs and 25% in triples. All exact-500 adds split 56/21/23, the same mix. `iter5_live_k` (at the touch 3.9% of
     the time, fill AUC 0.54) used burst quotes only, so it left out most of the orders that actually fill.
   - **Trigger.** A confirmed post follows a trade in the same market a median **85 ms** later (99% have one within
     1 s). Other exact-500/100 adds follow one after a median 286-312 ms (73-77% within 1 s). In 28-37% of confirmed
     posts the price equals that trade's price, against 5% for other adds.
   - **Futures direction.** In the second before a confirmed post, the futures mid moved toward the token in only 8 of
     the 28 cases that had a move. For unconfirmed at-touch 500/100 adds it moved toward the token in 13 of 15. The
     "re-posts follow the futures mid 91%" result was measured on unconfirmed near-touch re-posts.
   - **What this means.** The 500/100 class holds at least two streams:
     - a futures-following ladder, whose owner is unproven;
     - fresh at-touch posts that react to Polymarket prints, which are the ones that fill.

     Iteration 6's first step, "model the ladder rung law", would decode the first stream.
   - **Limits.** This is 25 minutes of one quiet Saturday block, n = 111. The book reconstruction is sound: 99% of 9,761
     snapshots match the delta-rebuilt book exactly, so the add timings are not a snapshot-reset artefact.
2. **"Three wallets post the same quote within 20 ms" has no identity check, and the STUDY calldata argues against
   it.**
   - In multi-maker matches, the order right after a cluster order at the same price is another cluster wallet in
     36.5% of 1,322 cases, against a 21.9% cluster share of those price groups.
   - Two or more cluster wallets share a price in the same match in only 6% of the cluster's 7,663
     (tx, token, price) groups.
   - Three orders posted within 20 ms at one price would sit next to each other in time priority.
   - The triplets may instead be one wallet's rungs, another operator, or a mix.
3. **X16 tested the wrong form of back-of-queue.** The cluster's orders are 500 shares and the median print is 11-18
   shares. When a print reaches a back-of-queue cluster order, it fills only part of it and the level holds with the
   remainder. So "P(cluster | level holds) > P(cluster | level cleared)", the 0.63 ratio, is what back-of-queue
   predicts; it does not reject it. The strong form needs the queue ahead of the order when it was posted, which only
   the live book shows.
4. **A fill target on 10-s bins may never show a +0.05 gain, even with the strategy decoded.**
   - If item 1 holds, the cluster's decision is a post at the touch about 85 ms after a print, and its fill comes from
     the next print about 0.6 s later (median post-to-match 604 ms).
   - A 10-s bin with prints is exactly what the market-activity baseline predicts.
   - The brief allows "has an order resting" as the presence label, and the live blocks show that state. But fills are
     the only ground truth on sealed blocks, so that label is usable only once the fingerprint's precision is proven
     (proposal Q2).
5. **The largest and most volatile PnL item sits outside the model.** On VALIDATE, BTC 15m earned +$28.3k (+30.5% on
   dollars bought) against BTC 5m's +$23.0k; on STUDY it lost 13.3%. Its fills come in the last 5 minutes of the
   15-minute window, when the concurrent 5m window settles on the same closing TWAP-60. The presence model has never
   seen this decision (proposal Q6).
6. **Checked here and not supported, so not proposed.**
   - **A capital limit as the on/off.** drpc serves archive `eth_call`; publicnode refuses with "Archive requests
     require a personal token". At block 95,800,000 (2026-10-19 06:22 UTC, inside the 13-h BTC 5m off run) the wallets
     held $22.47k, $22.64k and $22.66k pUSD, far more than 500-share rungs need.
     - The near-equal split hints at one treasury spread evenly over the three wallets.
     - This is one sample. The RE can sample the full series cheaply: one batched call per 5-minute step.
   - **Overlapping-window position.** BTC 5m participation by position inside the 15-minute grid is flat (BUILD active
     0.84 / 0.85 / 0.82), and so is it by position in the hour. Returns by position flip sign between BUILD and old
     VALIDATE.
   - **Taker signature types.** Takers in cluster transactions: type 3 66%, type 1 21%, type 2 12%, type 0 2%. Takers
     in the public sample: 60% / 28% / 9% / 2%. The difference is small (the sample was size-filtered, so sizes are not
     comparable).

## Proposals (ranked by the chance they close the gap)

### Q1. The fills come from a fresh post at the touch about 85 ms after a Polymarket print: decode that hazard on confirmed orders (new; replaces "model the ladder")

- **Hypothesis.** The cluster runs two order types:
  - a deep background ladder pegged to the futures and the mid, which rarely fills;
  - a reactive order: after a print (a hit on s's bid, or a lift of the complement's ask), it posts a fresh 500/100
    BUY on s at the new touch or at the printed price, when its fair says that post-print touch is cheap.

  The next print fills it. Its side is the side that was just sold, and its price is the post-print touch.
- **Why it fits.** Critique item 1:
  - 74% of confirmed posts are at the touch (4.6% for others);
  - 65% are fresh orders;
  - they follow a print by a median 85 ms (others 286-312 ms);
  - in the second before them the futures mid usually moved against the token.

  It also fits three earlier findings: the price anchor "last print - 0.01" works where fair models fail; P(fill)
  rises with the number of hits in a bin; and fills follow a 2-5 s move of the token.
- **Test.**
  1. Keep `code5/rawrec.py` running in every development block (11-01 06-12 and 18-24, 11-02 00-06 and 12-18 UTC).
     Confirm the posting add of every cluster fill, as in `post_trigger2.py`. Expect 150-400 orders per block.
  2. Build the controls. For every print in the recorded BTC markets, record whether a confirmed post followed within
     300 ms (a lower bound, since only posts that later fill are confirmed). Also record whether any exact-size add at
     the touch followed (an upper bound).
  3. Features at the print:
     - which side was hit, the print size, and whether it cleared the level;
     - the touch after the print;
     - the futures TWAP-60 fair at t-50..250 ms minus the new touch;
     - time left;
     - own inventory, reported separately.
  4. Fit a hazard or logistic model of the post. Test the side rule "the side just sold" and the price rule "the new
     touch or the printed price". Fit on one block and test on the next.
  5. Carry it to history. Add features "a print on s's bid in the last 1-2 s, and the futures fair minus the post-print
     price > x" to R3. Compare against an activity baseline that also gets the print sequence.
- **Data.** `dm_clob_raw` and `dm_bnf` (own recorder), data-api activity, and publicnode calldata of each block's
  cluster transactions; for history, STUDY and BUILD tapes and futures 1-s data (all on disk).
- **Signature if true.**
  - The post hazard peaks sharply 50-150 ms after prints, with a futures-gap threshold that holds across blocks.
  - The side of confirmed posts is the side just hit in more than 80% of cases.
  - Their price is the post-print touch (or the printed price) within one tick in more than 80% of cases.
  - On the tape, the print-sequence interaction lifts presence by far more than the +0.0007 that futures features
    added.
- **If false.** Confirmed posts follow prints no more often than other makers' exact-size touch adds do, once matched
  on touch changes.

### Q2. Prove whose orders the 500/100 stream is with the salt counter, before fitting any quote law to it (strong form of X17/X23)

- **Hypothesis to break.** The futures-following deep ladder and the 2-3-add bursts are the cluster's.
- **Why it fits.**
  - A resting 500 at the hit level raises P(cluster) only to 12.5%.
  - Burst structure adds nothing that separates the cluster's filled orders (critique item 1).
  - The adjacency check contradicts "three wallets at one price" (critique item 2).
  - The signed-vs-posted check so far is one average ratio (21 adds/s against 51 signatures/s).
- **Test.**
  1. In each block, each wallet's confirmed fills give pairs of (match time, salt). Between consecutive confirmed fills
     of a wallet, the salt difference is the exact number of orders it signed in all markets.
  2. Count the exact-size adds of the block's size class in every recorded crypto book. For one block, extend the raw
     recorder to the current ETH and SOL 5m and 15m windows so that most of the cluster's markets are covered.
  3. Regress adds per interval on the summed salt differences of the three wallets. The intercept counts other makers'
     adds. Intervals with more adds than signatures prove foreign orders.
  4. Get a direct identity: for one hour, fetch the calldata of every match (about 1-3k transactions at 75 tx/s).
     Compute P(the consumed order belongs to the cluster), split by:
     - posted alone, in a pair or in a triple;
     - at the touch or deep;
     - following the futures or following a print.
- **Data.** Own raw recorder, calldata of all matches for one hour, activity.
- **Signature if true (the stream is the cluster's).** Adds track signatures (R^2 > 0.7, intercept near 0, never
  more adds than signatures), and P(cluster | consumed burst order) is far above 12.5%.
- **If false.** The iteration-5 ladder law, the futures-latency result and `iter5_live_k` describe another maker. Refit
  the quote law on confirmed orders and their cancel/re-add chains only (`chain_back.py`).

### Q3. The queue-ahead fill law: the strong form of X16 (corrects a mis-specified test)

- **Hypothesis.**
  - A confirmed post is filled when the taker volume traded at its level after the post exceeds the depth that was
    ahead of it when it was posted.
  - Posts that improve the touch start first in the queue. That is 22-27% of confirmed posts, measured against the
    touch 250 ms earlier.
- **Why it fits.** Critique item 3; median post-to-match 604 ms (p10 52 ms); P(fill | hits) rises with the number of
  hits per bin.
- **Test.** For each confirmed order, measure:
  - the depth at its level just before the add (the queue ahead);
  - whether it improved the touch;
  - the cumulative taker volume at that level from the post to its first fill (`x` records plus level decrements).

  For fingerprinted posts that never fill, once Q2 has validated them, measure the same up to their removal. Fit
  P(fill before removal) against volume / queue ahead, and compare fills with a back-of-queue model and a pro-rata
  model.
- **Data.** Own raw recorder (levels and trades with server ms).
- **Signature if true.**
  - Fill probability steps up at a ratio of 1, with almost no fills below it.
  - Touch-improving posts fill on the first volume at their level.
  - Presence then factors into P(post at touch) (Q1) x P(volume >= queue ahead). Both come from public book data plus
    the decoded post rule, which the activity baseline cannot compute.

### Q4. The PnL comes from continuing taker sequences: a fill's position in a sequence, not size class or futures edge, separates winning fills (strong form of C2/C3/E8)

- **Hypothesis.** The cluster's money comes from the later child orders of large taker sequences (split parent orders
  that push the price), after which the price reverts. Its fresh at-touch post (Q1) is how it catches the continuation.
  First children and fast-taker flow earn nothing or lose.
- **Why it fits.**
  - STUDY: 1.72M taker prints, 7,551 of which fill the cluster. Stratified by the taker's daily activity and the print
    size, cluster-filled prints follow the same taker's print in the same window within 3 s 1.22x as often as other
    prints, and are followed by one 1.18x as often.
  - For prints over 200 shares from low-activity takers (200 prints a day or fewer), the rate is 0.26-0.31 against
    0.08-0.15 (2-3x).
  - The exam found +$26.8k of +$28.4k in the largest quartile of fills.
  - The per-window PnL correlation is 0.33 against a 0.69 / 0.78 ceiling, so the rule misses which fills pay.
- **Test.**
  1. For each cluster fill (STUDY case by case, VALIDATE aggregate), label the taker's sequence: same taker, window
     and direction, with gaps of 3 s or less.
  2. Record the fill's position in the sequence, the sequence's size so far, and the price displacement from its start.
  3. Record the taker's class: activity, signature type, builder code, and first-seen date.
  4. Compute dollar PnL and 60-s markouts by position and class.
  5. Then test a point-in-time feature, "an open non-HFT sequence on s with displacement d", on its own and interacted
     with the cluster's fair gap. Use it to size the rule's per-window PnL.
- **Data.** STUDY and BUILD tapes with taker wallets, calldata (taker builder codes and signature types), outcomes.
  All on disk.
- **Signature if true.**
  - Profit is concentrated in second and later children of large sequences with 2-3+ ticks of displacement.
  - First children and HFT sequences are flat or negative.
  - A rule weighted by sequence state lifts the per-window PnL correlation toward 0.5.

### Q5. BTC 5m on/off is competitor avoidance driven by who is making the market (strong form of N2/X24 for selection)

- **Hypothesis.** The engine or the operator turns BTC 5m off when particular faster makers hold the touch, judged
  from public maker fills, and turns it back on when they leave.
- **Why it fits.**
  - On/off is the largest single cap: presence 0.716 now, about 0.86 with a window oracle.
  - Every correlate tried so far used takers, spot, the clock, markouts, own PnL or incidents. None used maker identities.
  - The switches happen at unrounded times and are not tied to restarts.
  - The cluster is never at the top where a competing order is under 0.5 s old (iteration-4 book pilot).
  - Capital is not the limit (critique item 6).
- **Test.**
  1. Get the maker side of BUILD and STUDY BTC 5m matches: data-api `/trades` with `taker_only=False`, or calldata of
     a few hundred matches per hour.
  2. Per hour, compute each top-20 maker's share of maker volume at the best price.
  3. Run an event study around the 12-15 off/on switches in BUILD, STUDY and the development blocks.
  4. Fit a window-level on/off AUC from the previous hour's maker composition: BUILD, then VALIDATE in aggregate.
  5. Report separately (own state) whether the cluster's own share at the touch falls before switch-offs.
- **Data.** data-api maker rows or match calldata, activity.
- **Signature if true.**
  - Switch-offs come 30-60 min after one maker's (or one set's) share at the touch passes a fixed threshold, and
    switch-ons come after it leaves.
  - Window on/off AUC is above 0.7, against 0.47-0.58 for every earlier correlate.

### Q6. The BTC 15m late window is priced off the concurrent BTC 5m book, which shares its settlement (strong form of A4)

- **Hypothesis.** In the last 300 s the BTC 15m window and the concurrent 5m window settle on the same closing TWAP-60
  with different strikes. The engine quotes the 15m market off the 5m book, or the other way round, mapping
  probability across the strike gap. The 15m PnL (+30.5% on VALIDATE, -13.3% on STUDY) is the gap between the two
  books.
- **Why it fits.**
  - The 15m fills sit in exactly that last 5 minutes (median 718-726 s of 900).
  - Within a tick, the 15m price rule scores 66% against BTC 5m's 71%.
  - The 15m PnL is the largest and least stable item (critique item 5).
  - BTC 5m behaviour does not depend on its position in the 15-minute grid, so the link, if any, runs from 5m to 15m.
- **Test.**
  1. For 15m maker fills in the last 300 s (BUILD and STUDY case by case, VALIDATE aggregate), compare the fill price
     with three predictions:
     - (a) the 15m last clean print - 0.01;
     - (b) a 5m-implied 15m probability, P15 = Phi(Phi^-1(P5 mid) + (K5 - K15) / (sigma sqrt(tau))), with sigma from
       realised vol x 1.4 and each window's Binance-proxy strike;
     - (c) the futures fair.
  2. Live: do 15m re-posts and confirmed posts follow 5m touch moves? The raw recorder already holds both books.
  3. Compute the 15m PnL by the 15m-vs-5m-implied gap at fill time.
- **Data.** `.cache/re/directional-maker/t15/` tapes, BTC 5m tapes, Binance 1-s, the raw recorder.
- **Signature if true.**
  - (b) beats (a) and (c) on MAD and on within-tick.
  - 15m posts follow 5m touch moves within 100-250 ms.
  - 15m PnL rises with the gap.
  - The pooled 5m+15m universe (0.868 / 0.891 coverage) gets a price rule above 0.8 on the 15m part.
