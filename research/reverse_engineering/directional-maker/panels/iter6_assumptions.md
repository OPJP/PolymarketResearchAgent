# Panel after iteration 6: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means:
- how a filled order is tied to its posting add;
- what the "center" measures;
- the unit of decision;
- how strong the activity baseline is;
- where the PnL comes from;
- which clock the operator runs on.

Written 2026-10-31, about 17:00-18:10 UTC.

Data used (development only):
- the iteration-6 extracts in `.cache/re/directional-maker/it6/` (14:06-16:13 UTC raw book events, touch and trades);
- the own raw recording `dm_clob_raw`, `dm_bnf` and `dm_rtds` for 14:06-16:13 UTC;
- the live calldata `calldata/live1031_*` and `calldata/allmatch1793460000_*`, plus `live_activity_*` filtered to that
  window;
- STUDY cluster orders (`b1_cluster_orders_study.parquet`, 2026-10-23..26).

I did not touch VALIDATE (10-27..30) case by case, the 10-31 06-12 block, or anything sealed.

My check scripts are in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p6\`:
- `ambig.py` (identification ambiguity);
- `qtrace.py` + `prio.py` + `joint.py` (queue and priority);
- `saltclock.py`;
- `confound.py` (Chainlink-center confounds);
- `invskew.py` (inventory);
- `leader.py`;
- `mtype.py`.

Run them from the repo root.

## Critique

1. **Tying a filled order to its "posting add" is ambiguous for most fills. The queue facts built on that tie are
   mostly an artefact.**
   - **How the tie is made.** `q1_confirmed.py` takes the *latest* add of exactly the order's size at its level before
     the match.
   - **How often that is ambiguous.** Of the 1,316 confirmed orders:
     - 79% have more than one exact-size add at that level in the 30 s before the match;
     - 52% have two or more such adds still alive (adds minus same-size removals);
     - the previous same-size add came a median 108 ms before the chosen one (p25 9 ms: the three-wallet bursts).
   - **What changes in the clean subset.** The order of exactly 500 shares said to be "already there" when the cluster
     joined is often the filled order itself.

     | statistic | unambiguous (one exact-size add in 30 s, n 273) | two or more candidates alive (n 682) |
     | --- | --- | --- |
     | queue ahead, median | 78 | 1,005 |
     | "joined" a level | 0.54 | 0.80 |
     | age at match, median | 656 ms | 716 ms |
     | trigger lag, median | 52 ms | 126 ms |
     | P(trigger lag <= 150 ms) | 0.70 | 0.55 |

     The fresh-join timing survives, and is sharper, in the clean subset. The "joins a 500-deep level" description and
     the queue law (X37, "prints cover the queue ahead in only 19%") do not.
   - **Apparent priority violations.** I traced the level size from the add to the match for 586 joined at-touch fills
     (15:00-16:00 UTC, raw book, with the filling match's calldata).
     - In 34% of them the younger cluster order was filled by a small taker (median 4 shares). Less volume had left the
       level than the queue ahead, and the match held no other maker at that price. Older orders, median 494 shares,
       were still resting.
     - 97% of these cases have two or more same-size candidates, against 52% of the rest. So they come from the
       tie-making, not from the matching engine.
     - Where other makers at the level are in the same match, the older ones are listed first (ahead median 0.8 s
       older, behind 23 ms). That is ordinary price-time priority.
   - **The salt counter does not fix this cheaply from BTC fills alone.** Unambiguous anchors are a median 129 s apart,
     and interpolating salt to time picks a candidate a median 6.4 s away from the prediction.
   - **Also worth knowing.** A filled cluster order loses a median 1.2% of its 500 shares per match.
2. **The Chainlink center holds up against two confounds I could name. I checked them so the RE does not have to.**
   - **Takers reacting to the Chainlink price on the Polymarket page.** Clean taker flow (net selling of Up per
     second) does not follow the Chainlink noise component at stamp lags 0-6 s (|corr| <= 0.022).
   - **Another maker's exact-500 orders setting the top rungs.** Rebuilding the center from bursts only (two or more
     exact-500 adds at one market, side and price within 20 ms, the three-wallet copy signature; 57% of 500 adds) gives
     held-out R^2 **0.304**. Single adds give 0.151, and all adds 0.206.
   - **Quiet seconds.** Seconds with no trade in the previous 1 s give 0.296 (n 115 / 132, small).
   - **Own window inventory** adds nothing: 0.206 -> 0.211 (+0.004 per 1,000 net Up shares, in the anti-balancing
     direction).
   - **Conclusion.** The engine itself reads Chainlink. The 0.21 understates the law, because the measurement mixes in
     non-cluster 500s and at-touch joins.
3. **The unit of decision is still wrong for the target.**
   - The 10-s bin (primary) and the print (selection) both mix two things: the cluster's per-trade decision to post a
     fresh 500 at the new touch about 50-100 ms after a trade, and the next taker's arrival.
   - The only quote label tried was "an exact-500 add within a tick of the touch in a 10-s bin". Its base rate is 56%,
     so it is too coarse to show a threshold.
   - The rung-reach rule used the ladder's half-spread (0.065) and modelled prints, not joins (AUC 0.657).
   - The join decision itself has never been modelled at its own resolution (D2 is open).
4. **The +0.10 print-level gain is measured against a weak activity baseline.**
   - `sel_live.py`'s baseline has 12 coarse features: time since the previous print, same-side and same-price flags,
     counts and shares sold over 1 and 5 s, size, time in the window, price.
   - The examiner fits its own baseline from the shared recorder, with the same model class.
   - Sub-second book features would capture "a trade just moved the touch, and the cluster joins". Those are the time
     since the last sell or touch change on s, the post-trade touch and its depth, and whether the print cleared the
     level.
   - Book depth also contains the cluster's own visible 500s, which are 88% of exact-500 orders. The brief's
     hygiene rule removes own prints and cluster-maker transactions, not own resting quotes. A depth feature that
     carries them would be leakage of the decision itself.
5. **The investigation assumes the Chainlink skew is the edge. Its own economics say the skew is the cost.**
   - On 1,430 live fills, those where Chainlink valued the token more than 3 c above the futures (67% of fills) lost
     4.6%.
   - Fills where the two agreed earned +26% to +43%.
   - Per-share PnL correlates +0.27 with the futures edge and -0.10 with the Chainlink edge.
   - The rule does not model which fills fall on which side of that split, so the 0.33 PnL correlation has no route
     to 0.5.
6. **Process.**
   - The primary metric (historical presence 0.716) has not moved for three iterations and cannot carry the input
     now believed decisive.
   - Every live number comes from one quiet Saturday afternoon: about 90 minutes of live VALIDATE and 14-18 test
     windows.
   - The sealed blocks the exam recorder covers are all weekend blocks (Sat 18-24, Sun 00-06, Sun 12-18).
   - The exam recorder stops at 11-02 00:00, so no weekday session block can be examined with a full-coverage
     Chainlink feed.
   - US DST ends at 11-01 06:00 UTC, so weekday clock features keyed to UTC may shift by an hour in every later block
     (P5).
   - Recommendations:
     - pre-register the live print-level selection (and the join model of P1) as the primary metric before reading
       11-01 06-12;
     - extend `examrec.py`, with a new hard stop, over the 11-02 / 11-03 weekday sealed blocks.
7. **Checked and not supported, so not proposed.**
   - Quote copying of a leader maker: a previous add at the same level within 20 ms is as common for other 500/100
     at-touch adds (0.55) as for the cluster's (0.51).
   - A matching-type priority (mint before direct): in 587 mixed-type levels in the all-match calldata, 64% are
     type-sorted, with no consistent first type.
   - The inventory skew (above).

## Proposals (ranked by the chance they close the gap)

### P1. Decode the per-trade join decision as its own unit (strong form of D2, X31 and iter5 Q1 step 4)

- **Hypothesis.**
  - After every trade that moves a token's touch, each wallet decides within about 50-150 ms whether to post a fresh
    500 BUY at the new touch.
  - It posts if the post-trade touch is at or below its Chainlink-skewed reservation price minus a small join margin
    h_j. The reservation price is mid + k(CLfair(stamp <= t-2) - mid). The join margin is not the ladder's 0.065.
  - Otherwise it leaves only the deep rungs.
  - A fill follows if another sell arrives in the roughly 1 s before the next re-post.
  - Presence and selection are this join hazard times taker arrival. Only the first factor carries the cluster's
    information.
- **Why it fits.**
  - In unambiguous confirmed posts, the trigger lag is a median 52 ms (70% within 150 ms) and the age at the match
    0.66 s.
  - The burst-only center follows Chainlink at held-out R^2 0.30.
  - The 10-s quote label (base rate 56%) and the rung-reach rule cannot show a threshold.
  - Print-level Chainlink gains (+0.07 to +0.10) are larger than bin-level gains (+0.04), as expected if the
    information acts per event.
- **Test.**
  1. Build an event table of every clean trade in the BTC 5m and 15m books: live BUILD 10-31 12-15, live VALIDATE
     15-18, and then 11-01 06-12 from dx_* and the own raw recorder.
  2. Label each event by whether a burst-signature exact-500 add (two or more within 20 ms) appears at the post-trade
     touch of Up, of Down, or of neither within 150 ms. Variants: any exact-500, 300 ms.
  3. Features:
     - gap_cl = mid + k(CLfair - mid) - touch_s, with k fitted on BUILD;
     - futures fair minus touch;
     - time left;
     - spread;
     - depth left at the touch, net of exact size-class increments;
     - trade size;
     - whether the trade cleared the level;
     - which token was sold.
  4. Fit a logistic or hazard model and a LightGBM, with and without Chainlink and futures (the activity baseline).
  5. Fit h_j as a threshold in gap_cl, and check it is the same on the next block.
  6. Run a two-stage selection: score each print by P(join after the latest trade on its token within the last ~1 s),
     times a queue term (P2). Compare it with the print-level LightGBM on 11-01 06-12.
- **Data.** Own raw recorder, dx_clob, dx_rtds, dx_bnf / dm_bnf, cluster calldata of the blocks. All on disk or
  recording.
- **Signature if true.**
  - Join AUC >= 0.80, with Chainlink adding >= 0.10 over the activity version.
  - A step in P(join) at a stable h_j (within a tick across blocks).
  - Two-stage print selection >= 0.80 with recall >= 50% at lift >= 3 on 11-01 06-12.
- **If false.** Joins follow every touch move whatever the gap. The information then sits only in the deep ladder,
  and selection stays capped near 0.74.

### P2. Re-derive the queue and age facts on resolved orders before using them (it breaks the X33/X37/J3 numbers)

- **Hypothesis to break.** "The filled orders are fresh joins behind about 500 shares, filled when the match sweeps
  the queue ahead."
- **Why.** Critique 1.
  - The tie-making picks the latest of two or more alive candidates in 52% of fills.
  - The 500 ahead is often the filled order itself.
  - All of the apparent 34% priority violations are this artefact.
  - The unambiguous subset says: fresh (0.66 s), sharply triggered (52 ms), small queue ahead (78).
- **Test.**
  1. Report every age, trigger, side-sold and queue statistic separately for orders with zero, one, and two or more
     alive same-size candidates.
  2. Resolve the ambiguous ones with two methods:
     - the remainder trail: a filled 500 is later removed or re-posted as an order of exactly its remainder (e.g.
       494.0, a unique size), which ties the add to the order's end;
     - a salt clock built from the lower envelope of (salt, match ms) over the wallet's fills in all markets. Use the
       all-market calldata of the block. BTC-only anchors are too sparse: 129 s apart, picking a candidate 6.4 s from
       the prediction.
  3. Then fit the queue law on resolved orders: P(fill before removal) against the taker volume at the level after
     the post, divided by the queue ahead.
- **Data.** Own raw recorder, all-market calldata of the cluster's live transactions (publicnode, as in
  `live_refresh.py`).
- **Signature.**
  - If the RE's reading holds:
    - resolved ages stay at about 0.6 s, with a trigger within 150 ms for at least 60%;
    - the queue ahead is under 100 shares in most fills;
    - the fill law steps at volume / queue ahead = 1.
  - If not:
    - a large share of fills come from rungs several seconds old;
    - the timing component falls back to "resting at-touch rung";
    - P1's label must be rebuilt.

### P3. Prove the gain against the strongest activity baseline the examiner can fit, with a clean-book rule (new; target condition 2)

- **Hypothesis to break.** "Chainlink adds +0.10 AUC over market activity at the print level."
- **Why.** Critique 4.
  - The current baseline lacks sub-second sequence and book state, which the shared recorder provides.
  - Book depth contains the cluster's own resting 500s.
- **Test.**
  1. On live BUILD, fit a strong activity model. Features:
     - ms since the last clean sell on s and since the last touch change on s;
     - the post-trade touch of s and its depth at t - 200 ms;
     - spread;
     - level changes in the last 1 s;
     - cleared-level flag;
     - print price minus touch;
     - everything in `sel_live.py`.
  2. Fit it in two versions: raw book, and a clean book. The clean book removes every exact increment of the
     size-class ladder (500, 250, 62, 100 and the remainders of filled cluster orders), mirroring the clean-tape rule.
  3. Measure the Chainlink(+futures) gain over each on live VALIDATE and on 11-01 06-12, with a 2-hour or window block
     bootstrap.
  4. Freeze the clean-book function in `final_rule.py` and state in FINAL_RULE.md which book fields are admissible.
- **Data.** Shared `clob_crypto` and own raw recorder, dx_rtds, dx_bnf.
- **Signature if the gain is real.**
  - The gain over the clean strong baseline is >= 0.05 with lower bound > 0.
  - The raw-book baseline scores higher. That proves the contamination and shows why the clean rule must be frozen.
- **If false.** The gain collapses and P1's threshold is the only route.

### P4. Locate the PnL by order type and by the source of the Chainlink-futures gap (strong form of D4 and iter6 economics)

- **Hypothesis.** Two mechanisms are pooled.
  - Fresh joins gated by futures carry the profit.
  - Chainlink-skewed rungs lose when Chainlink lags a futures move ("lag" gap) or spikes on its 1-s noise ("noise"
    gap). They are reached by sellers who have seen the futures.
  - The losing 67% (gap > 3 c) is concentrated in one of these cells.
- **Why it fits.**
  - Gap > 3 c fills: -4.6%. Agreeing fills: +26% to +43%.
  - PnL correlates with the futures edge (+0.27), not with the Chainlink edge (-0.10).
  - Latency takers inside 300 ms never hit the cluster, but slower ones may.
- **Test.** On the live fills with match clock, settled by the RTDS TWAP rule:
  1. Split by order type from P2's resolved identification: fresh join (<= 150 ms after a trade), other at-touch,
     deep rung reached by a sweep.
  2. Within each type, split by gap source: noise = CL(t-2) - mean CL(t-6..t-3); lag = futures change over the last
     2 s.
  3. Compute PnL and 60-s markouts per cell.
  4. Then weight the rule's per-window expected PnL by a gap model fitted on BUILD fills, and re-measure the PnL
     correlation on live VALIDATE.
- **Data.** Own raw recorder, dm_rtds / dx_rtds, futures, live activity and calldata.
- **Signature if true.**
  - At least 70% of the loss sits in one cell (e.g. lag-gap deep rungs).
  - Fresh joins earn in every gap bucket.
  - A gap-weighted rule PnL lifts per-window correlation toward 0.5 on live VALIDATE.

### P5. Which clock the operator runs on: the US DST change on 11-01 as a natural experiment (new; C5 and size)

- **Hypothesis.** The size session (500 from 12:00 UTC on weekdays, back to 62/250 at about 21:00 UTC) and possibly the
  daily salt restart (01:00-01:08 UTC) are set in US Eastern time: 08:00, 17:00 and 21:00 EDT. After DST ends at
  11-01 06:00 UTC, they would move to 13:00, 22:00 and 02:00 UTC. The frozen UTC-hour features in R3/R5 and the size
  controller would then be an hour off in every weekday block from 11-02 on.
- **Why it fits.**
  - The session switch at exactly 12:00 UTC on 10-26..30, and the end at 21:00 UTC on 10-26, are 08:00 and 17:00
    EDT.
  - The 01:00 UTC restart did not move across the EU DST change of 10-25, which rules out a CET or London clock.
  - On Friday 10-23 the first 500s came at 11:25:50 UTC (all three wallets by 11:32, 250 before). Either that is a
    volatility upgrade at the 11:25 open or the session clock is not UTC. Check the 300-s futures vol at that open.
- **Test.** On development blocks only:
  - 11-02 00-06 UTC: is the salt restart at 01:0x or at 02:0x UTC?
  - 11-02 12-18 UTC: is the first exact-500 cluster order at 12:00:0x or 13:00:0x UTC?

  Use the live activity, calldata and raw book.
- **Data.** Live activity and calldata of those blocks, futures vol.
- **Signature if true.** Both events shift by one hour. Re-key the clock features to America/New_York before freezing
  R5, and note it in FINAL_RULE.md. If nothing shifts, the clock is UTC (or Asia). Then record it, and leave the
  features as they are.
