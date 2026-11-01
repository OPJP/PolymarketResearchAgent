# Panel after iteration 6: mechanics and on-chain forensics

Lens: how the orders are built (calldata, ladders, re-quote clocks, queue and matching mechanics, inventory). Written
2026-10-31 ~17:20 UTC. Data used: development block 10-31 12:00-18:00 UTC only. That is the RE's own extraction
`.cache/re/directional-maker/it6/` (ev/x/touch/confirmed, 14:06-16:30 UTC), `dm_rtds`, `dm_bnf` and `dm_bns` through
`code5/rawread.iter_dm`, the 20-minute all-match calldata `calldata/allmatch1793460000_*` (15:20-15:40), live activity,
and two short RTDS probes of my own at 16:55-17:05 UTC (summaries printed, nothing stored). I did not touch the released
lot, the historical VALIDATE or anything sealed.

**Disclosure.** My aggregates span live BUILD and live VALIDATE (15:00-18:00). I also traced one live-VALIDATE window case by
case (btc-updown-5m-1793460000). Treat every number below as exploratory and replicate it on 11-01 06-12 UTC, which nobody
has looked at.

Scripts (all in `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`):
`cl_phase.py`, `cl_phase15.py`, `cl_phase2.py` (event study by phase), `phase.py`, `two_loops.py`, `burst_purity.py`
(re-quote clocks), `taker_vs_post.py`, `maker_sign_add.py` (speed bump), `mint_priority.py`, `ladder6b.py`,
`ladder_cl.py`, `ladder_k.py`, `ladder_inv.py`, `ladder_auc.py` (alive ladder), `clock_cal.py`, `rtds_probe.py`,
`rtds_probe2.py`.

## What my checks found

1. **The engine starts using the Chainlink report stamped S about 0.7 s after S, on the CLOB server clock.** Unit: 10,153
   exact-500 re-posts in BTC 5m whose price changed (|dp| <= 0.05, within 1.5 s of the previous 500 add on that side),
   restricted to seconds with |ΔCL| > $3. Measure: agreement of the re-post direction (in Up terms) with the Chainlink
   change, by the post's millisecond within the second. Lag 0 is ΔCL_S = CL_S - CL_{S-1}, lag 1 is ΔCL_{S-1}:

   | phase of post in second S (ms) | 0-100 | 200-300 | 400-500 | 600-700 | 700-800 | 800-900 | 900-1000 |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | agree ΔCL_S (lag 0) | 0.36 | 0.34 | 0.40 | 0.44 | 0.52 | 0.59 | 0.62 |
   | agree ΔCL_{S-1} (lag 1) | 0.62 | 0.65 | 0.60 | 0.51 | 0.52 | 0.52 | 0.50 |
   | agree ΔCL_{S-2} (= the t-2 convention) | 0.56 | 0.53 | 0.56 | 0.55 | 0.52 | 0.53 | 0.57 |

   - The switch sits at 700-800 ms. Re-posts before that point disagree with the change they cannot have seen yet
     (0.34-0.44). That follows from Chainlink's lag-1 autocorrelation of -0.47, and it is the stream's own noise signature
     inside the quotes.
   - **BTC 15m is the same** (n 15,645): lag 0 0.37-0.41 before 600 ms and 0.55-0.62 after 700 ms; lag 1 0.59-0.66 before
     600 ms. At the t-2 convention it is 0.47-0.51, which is nothing. This explains why iteration 6 found "no input
     transfers to 15m" (held-out R^2 <= -0.09).
   - Binance futures and spot 1-s changes on the same grid show no switch (0.40-0.61). The futures mid move in the 700 ms
     before the post agrees 0.57-0.70 (n 64-80 per 200-ms bin): that is the re-anchoring to the mid.
   - Clock check (`clock_cal.py`): from the receive-time envelopes, the CLOB server clock is +111 to +117 ms against
     Binance's, so the 0.7 s is not a clock artefact of a second.

2. **The re-quotes are phase-locked to the UTC second, and only the cluster's are.** Exact-500 adds and removals carry
   11.8% of their events in 200-300 ms against 7.9% in 500-700 ms, per 100-ms bin (n 66k; chi^2 p ~1e-264). The pattern
   is the same in 5m and 15m and stable over hours 14-16. Controls are flat: exact-100 adds (other makers') 9.7-11.6%,
   other sizes 9.7-10.8%, trades 9.5-10.4%. The density is high from about 800 ms to 400 ms of the next second, which
   matches a re-price pass that starts when the report arrives at about S+0.7 s.

3. **There are two order loops, and fills come mainly from the asynchronous one.**
   - Exact-500 adds split into singles 45%, same-price pairs within 25 ms 25%, and three-wallet triplets 29%.
   - Triplets are the most phase-locked (6.6% vs 12.7% per bin) and the least print-triggered (P(trade <= 150 ms before)
     0.22).
   - Singles are weakly locked (8.9% vs 11.3%) and print-triggered (0.35).
   - Of the 1,122 calldata-confirmed filled 500s, **64.6% were posted as singles** (20.9% pairs, 14.5% triplets).
   - So the synchronous 1-Hz ladder pass is mostly background. The fills come from per-wallet re-posts triggered by
     prints.

4. **The alive ladder is not the "top 500 adds of the last 1.5 s".** I rebuilt it from exact-500 adds and removals,
   capped the count at each level by the level size (z // 500) and dropped levels through the touch (1,146 random moments
   in 29 windows; crude, see M2).
   - Alive cluster-class rungs: median 2 on Up and 1 on Down.
   - Top rung: median 5 / 7 ticks below the touch. It is at the touch 15% / 10% of the time, on exactly one side 23% of
     the time, and on both sides 0.1%.
   - Pair sum of the alive tops: median 0.84 (IQR 0.78-0.89). The total depth (Up + Down ticks) has an IQR of 11-21
     ticks, so the spread is not fixed.
   - corr(Up depth, Down depth) = -0.20.
   - The depth of successive same-side bursts has a lag-1 autocorrelation of 0.44 (about 0.9 s apart), and its increments
     have -0.34. One example: the Down rung walked from 0.71 to 0.55 in 2.6 s while the touch stood still and Chainlink
     rose $20 toward the strike.

5. **The Chainlink edge sets which side is near the touch, but at the t-2 clock it is a weak predictor.** Here
   e = Chainlink digital fair (stamp <= t-2) - mid.
   - Across e quintiles, the Up top-rung depth goes from 11 to 2 ticks and its at-touch share from 1.6% to 17.7%; the Down
     depth goes from 4.5 to 16 ticks. corr(depth asymmetry, e) is 0.41.
   - Side of the at-touch rung when exactly one side is at the touch: sign(e) is right 0.736 of the time, always-Up 0.591
     (n 159).
   - At-touch state AUC: e alone 0.66; activity-only GBM 0.58; activity + e 0.62 (grouped CV over 29 windows; small and
     prone to overfitting).
   - A wider vol scale (k 2 instead of 1.4) raises the asymmetry correlation slightly (0.44-0.49).
   - Own window inventory adds nothing (R^2 0.17 -> 0.18), and its sign is wrong for an inventory skew: more Up held puts
     the Up rung nearer the touch. The implied center against the PM mid has R^2 0.81.

6. **Taker orders have a speed bump of about 190 ms, which makers' orders do not.**
   - Across all 5,528 matches, signing to the server match has almost no mass below 175 ms (1-4 per 25-ms bin), then 348
     at 175-200 ms and 535 at 200-225 ms. The 5% quantile is 191 ms.
   - The per-taker minimum (130 takers with >= 10 orders) has p10 188 ms and p25 197 ms.
   - Makers' orders with a signing ms reach the book 0-75 ms after signing in 13% of 364 located cases.
   - Takers who filled the cluster: 41% signed before the cluster posted, but only 7.7% in the 0-200 ms before it. So
     "posting in front of takers already in flight" is not the mechanism. The bump does explain why no taker reacting to a
     print can arrive within the ~95 ms in which the cluster re-joins.

7. **Matching priority between direct and complement orders: no asymmetry. Drop that direction.**
   - In 590 mixed (tx, price) groups, the mean relative position is 0.489 for direct makers and 0.498 for complement
     makers. P(first is direct) is 0.417, against a direct share of 0.409.
   - The cluster's fills are 94.6% complement matches (the taker buys the other outcome), against 77.6% for all makers.
   - The cluster is the last maker at its price in 79% of shared-price groups.

8. **The public RTDS stream exists, but neither recorder receives it.** I probed four subscription forms:
   - With the `{"symbol": "btc/usd"}` filter (both `tools/live.py` and `code6/examrec.py` use it): one 59-60-value snapshot,
     then no updates.
   - With no filter or an empty filter: `update` messages, one value each, for all 8 symbols, about once a second.
   - btc/usd age on arrival: q10/50/90 1,251 / 1,578 / 2,090 ms, laptop-corrected by Binance server time. My best RTT to
     Binance was 592 ms, so allow +-0.3 s.
   - So the public stream reaches this laptop about 0.5-1.4 s after the engine has acted on the same report.

## Critique

1. **"The value stamped t-2 s is now" is the public-feed convention, not the engine's clock.** It came from 1-s level
   regressions on a center built from posts in the last 1.5 s, and that window smears the lag. On the posting clock
   (finding 1) the engine acts on stamp S from about S+0.7 s, in 5m and in 15m alike. The t-2 rule is the right
   point-in-time convention for a public rule. But it means the rule is always one report behind the engine, and with
   lag-1 autocorrelation -0.47 the newest change it has not seen is anti-correlated with the one it uses. That is likely
   the biggest single part of the unexplained presence, selection and side gap, and it has not been measured. The 15m
   verdict ("undecided") should be reopened at once.
2. **The ladder measurement mixes things.** "Highest 500 add in the last 1.5 s" mixes two loops (finding 3), other
   makers' 500s, and rungs re-signed at random depths (finding 4). The fixed pair sum of 0.88 and h = 0.06 do not hold for
   the alive ladder (median 0.84, wide spread). The center R^2 of 0.21 is partly a measurement ceiling.
3. **"Fresh joins" is not established by its null.** The fill age (q25/50/75: 195 / 684 / 1,986 ms) equals the plain
   lifetime of at-touch 500/100 rungs (204 / 620 / 1,732 ms). A fill ends an order's life, so its age is a lifetime,
   whereas the 11-s length-biased null is the residual age at a random moment. That null is also inflated by other
   makers' long-lived 100s and by FIFO mispairing of the three wallets' same-size orders at one level. The comparison
   needs fill hazard by age, on exact-500s, with order-level tracking. The timing component (confidence 0.7) is
   over-stated until then.
4. **The rule models the wrong order stream.** Fills come mostly from single-wallet re-posts triggered by prints
   (finding 3), yet the center race and the rung-reach rule use the synchronous ladder. That is why gap >= 0 flags only
   11.8% of fills.
5. **The venue's speed bump belongs in the description.** It is the mechanical reason the cluster is never picked off
   (0 of 182). It also changes what "posted 95 ms after a trade" means: in that window only makers can act.

## Proposals (ranked by the chance they close the gap)

### M1. Put every input on the engine's own clock, and measure the latency part of the gap (new; strong form of A1, X41, X40, D1)

- **Hypothesis.**
  - One 1-Hz loop re-prices the three wallets' ladders when the Chainlink report stamped S arrives, at about S+0.7 s.
  - A second, print-triggered loop re-posts single rungs in between.
  - The center skew, the side and the at-touch posture follow CL_S from S+0.7 s.
  - A public client sees CL_S only at S+1.3-2.0 s. So part of the gap is the engine's latency edge on the settlement
    stream, which is measurable.
- **Why it fits.** Findings 1-3 and 8: the clean switch at 700-800 ms in 5m and 15m, the anti-agreement before it,
  phase-locking specific to the cluster's 500s, no switch for futures or spot, and RTDS arriving later than the engine
  acts.
- **Test.**
  1. Pre-register on 11-01 06-12 UTC (dx_* feeds) the phase-split agreement table:
     - for every feed: Chainlink by stamp, Binance futures and spot, Coinbase, OKX, Bybit, Deribit, Bitstamp, and a
       cross-venue median of mids;
     - separately for triplets and singles, 5m and 15m;
     - with a window block bootstrap;
     - and a change-point fit of the switch phase phi*.
  2. Calibrate the clocks: record the CLOB WS and the unfiltered RTDS stream on the same machine (as in `clock_cal.py`) to
     get RTDS emission time against server time.
  3. Re-run the center race, print selection, 10-s presence and side with Chainlink on three clocks: the engine clock
     (stamp S usable from S + phi*, a latency oracle), the public-stream clock (measured arrival) and t-2. The difference
     is the latency-attributable part of each metric.
  4. Look for a public path that closes it:
     - the unfiltered RTDS stream (finding 8);
     - the data.chain.link live endpoint with polite backoff;
     - a nowcast of CL_S at S+0.3 s from the venues' mids plus Chainlink's AR(1) noise (lag-1 -0.47).
     If a nowcast works, freeze R5 on it.
  5. Start a small streaming-RTDS recorder now (no symbol filter; `Writer`; hard stop), so that the sealed blocks have
     arrival times on the streaming path. The existing backfill gives values by stamp but not this.
- **Data.** `it6/ev`, `x`, `touch`, `dm_rtds` / `dx_rtds`, `dm_*` / `dx_*` venue feeds, and the 11-01 06-12 block.
- **Signature if true.** At the engine clock, center R^2 rises well above 0.21 and print-selection AUC above 0.74 (toward
  0.80) in both 5m and 15m, while the public clock stays near today's numbers. That is either the quantitative account
  the brief asks for ("decisions precede the public settlement stream by X s in Y% of re-quotes"), or, if a nowcast
  recovers it, the missing input for R5.

### M2. Score the quote, not the fill: resting-order presence and the single-join decision (new target; strong form of B2, X19, X33; the brief's "or better, whether it has an order resting")

- **Hypothesis.** The decision is the posture of the rung (at the touch, or how deep), set by the engine-clock center.
  Fills are that posture times taker arrival. Resting-order presence and the side of the at-touch rung can then reach the
  target where 10-s fill presence, capped by taker arrival, cannot.
- **Why it fits.**
  - Finding 5: the Up at-touch share rises 11x across e quintiles even at the t-2 clock, and side is 0.736 by sign(e).
  - X15: P(fill in 10 s) is 29% with the cluster at the touch, against 10% otherwise.
  - The fills are 78% at the touch, from single re-posts.
- **Test.**
  1. Order-level ladder state per ms:
     - exact-class adds and removals, capped by z // 500, levels through the touch removed;
     - remainders tracked through `x` and the calldata remainder sizes (492, 76, ...);
     - singles, pairs and triplets labelled;
     - purity measured on the all-match slice: the share of at-touch 500 levels whose next fill is the cluster's.
  2. Labels per (window, side, second): rung at the touch; rung within 1 tick.
  3. Two models:
     - a censored (Tobit) model of top-rung depth on the engine-clock e (M1), mid, time left and vol;
     - an event model: for every print that moves the touch on s, P(a cluster single 500 at the new touch within 150 ms).
  4. A two-stage fill presence = P(at touch) x P(the taker reaches it | queue ahead, activity). It shows how much of the
     fill-presence gap is the quote and how much is taker arrival.
  Report every model against the activity-only baseline. dx_clob records schedule-size deltas within 3 ticks of the touch
  and the touch size every 200 ms, so the label exists on the sealed blocks; pre-register the target definition with the
  examiner first.
- **Data.** `it6/ev`, `x`, `confirmed`, the all-match calldata, and dx_clob for later blocks.
- **Signature if true.** Resting-at-touch AUC >= 0.85 with a gain of at least 0.05 over activity, and side >= 0.80 in
  one-sided states, replicated per wallet and per half. If not, the fitted model gives the presence ceiling with numbers.

### M3. Test whether the residual rung depth is designed noise (new; the brief's "indistinguishable from random" account)

- **Hypothesis.** Below the engine's anchor, each re-post draws its depth at random (anti-gaming or queue sampling). Part
  of the at-touch state is then unpredictable by construction, and the share can be computed.
- **Why it fits.**
  - The 500-add depth histogram is flat at 4.5-6% per tick from 1 to 14 ticks, with a pile at 0 (10.4%).
  - Burst depth has autocorrelation 0.44 at about 0.9 s and its increments -0.34.
  - The walk example in finding 4.
  - The depth sum varies (IQR 11-21 ticks).
- **Test.** After removing the M1/M2 center, test the depth residuals for:
  - uniformity on a fixed tick grid;
  - independence across successive re-posts, across sides and across hours;
  - identity inside a triplet (one draw for all three wallets) against independence across singles;
  - dependence on the ms phase and on the salt counter of filled orders (depth against salt mod k, calldata).
  Compare with a deterministic sweep (sawtooth or counter cycle).
- **Data.** `it6/ev`, the confirmed orders with salts (`calldata/live1031_*`).
- **Signature if true.**
  - If the residual is i.i.d. uniform over 0..K (K about 14), the per-re-post at-touch probability is about 1/(K+1) after
    censoring. That puts an analytic ceiling on presence, to report as the unexplained remainder.
  - If instead it is a deterministic cycle, it becomes predictable from the engine's past re-posts (own state, reported
    separately).

### M4. Build a historical millisecond match clock from takers' signatures, using the ~190-ms speed bump (strong form of X11 and X8, weak so far)

- **Hypothesis.** Every match's taker order carries its signing ms, and marketable orders wait at least ~190 ms after
  signing. A frozen latency map (match ~ sign + max(190 ms, the taker's typical latency), ordered by block, tx and log
  index) then rebuilds the match clock for the released lot and the historical VALIDATE. R4's match-clock price rule and
  the print-time features then score historically, not only live.
- **Why it fits.**
  - Finding 6: floor at 175-200 ms, per-taker minimum 188-197 ms, 5,512 of 5,528 takers sign.
  - R4 is 0.83-0.86 on the match clock against 0.709 on the block clock.
- **Test.**
  1. Fit the latency map on live blocks (true server match ms) and report its median absolute error.
  2. Apply it to the lot and score R4's price rule and the trivial anchors on the predicted clock (VALIDATE aggregate).
  3. Check that the bump is constant across hours and markets (a venue rule).
  4. Re-measure pick-off exposure as taker signing time minus the cluster's last re-quote.
- **Data.** Calldata of the lot (`calldata/valid_*`, `study_*`, which are taker rows), live `x` for the fit.
- **Signature if true.** Historical price within a tick of 0.80 or more with the frozen map, per wallet, and the
  block-clock deficit closed. It does not move presence by itself; it removes the clock confound from every historical
  print feature.

## Notes for the RE

- Run order: M1 step 1 on 11-01 06-12 (it needs only feeds that are already recorded), then M2. M3 reuses M2's state, and
  M4 is cheap and historical.
- Start the streaming-RTDS recorder (no symbol filter) before the next sealed block if M1 might use arrival times.
- Ruled out by my checks, so not worth your time: matching priority between direct and complement orders (finding 7), and
  an inventory skew of the ladder (finding 5).
