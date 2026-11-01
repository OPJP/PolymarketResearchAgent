# Panel, iteration 3: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and maintained. That covers the uncensored resting ladder on the own recorder, the
quote function against other makers' book, the FAK limit and size, the 1-s delay cycle (pull, FAK, re-post), the
complement pairs and what they do to per-market PnL.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-3), state.json (catalog X1-X36, components, target metrics), FINAL_RULE.md,
panels/iter1-2_* and the headings of panels/iter3_{assumptions,information}.md, to avoid repeating them.

I then ran small read-only checks (scratchpad scripts; nothing written to the workspace except this file):

- **History, 16-22 Oct (before H):** `orders.parquet`, `calldata_all`, `calldata_pub`, `per_market.parquet`, the
  windowed taker tapes, `pack_orders.parquet`.
- **Live:** the own recorder `tommy_cs2_near`, 10-31 14:50-16:50 UTC (development block), on the **server clock
  `s`** only. The markets are the 8 CS2 dev-unit markets the wallet traded, taken from `dev_markets.parquet`
  (bhe-bar2, gls1-pcy, wraith-ntr, shin-isg). Its takes come from `calldata_dev`, which runs to 16:50 UTC.
- Nothing sealed was read.

All live numbers come from one 2-hour block and a few events, so they are exploratory. Own levels are attributed
by the 100-share whole-cent fingerprint only. The assumptions panel shows that its pulls also come in
inventory-scaled sizes (54 / 58 / 68), so the own-level counts below are a lower bound.

## Critique: what the investigation is missing or getting wrong

### 1. The maker price has been scored against the wrong book; the uncensored ladder shows a constrained two-sided quote

`price_within_tick` (0.305) scores filled orders, which are censored, against the last print. `ladder_decode`
scored burst tops against the pre-burst book, and that book contains the wallet's own levels (self-reference
again).

I rebuilt instead the wallet's resting ladder *state*: tracked +100 / -100 whole-cent levels, sampled every 2 s
of server time (8,189 samples). I then subtracted these levels from the book to get **others' book**.

**Where the top sits.**

| Own top minus others' best bid | +2c | +1c | 0 | -1c | -2c | -3c | -4c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| team-0 ladder (48.7% of samples) | 3.1% | 2.5% | 26.8% | 20.3% | 14.0% | 16.5% | 11.1% |
| team-1 ladder (59.5% of samples) | 1.7% | 2.2% | 34.3% | 25.2% | 10.6% | 6.9% | 9.8% |

- It almost never improves on others' best bid.
- It joins that bid or sits 1-4c below it.

**The two tops are capped jointly.** With both ladders present (40.8% of samples), the sum of its two tops is
0.95 / 0.96 / 0.97 / 0.98 in 12 / 22 / 18 / 21% of samples.

- The rule `own_top_A + own_top_B = min(others' bid sum, K)` with K = 0.97 holds within 1c in 59.4% of samples
  (K = 0.96: 51.4%; K = 0.98: 46.0%).
- When others' spread is 1c (others' bid sum 0.99), it never joins both bids: its sum is 0.95-0.98 in 80% of
  those samples.

**The shaded side moves with inventory, partly.** Inventory is the net from `calldata_dev` fills on the match
clock.

| Position | team 1 shaded more | team 0 shaded more |
| --- | --- | --- |
| long team 0 | 61% | 21% |
| flat | 29% | 59% |
| long team 1 | 31% | 61% |

Long team 1 looks like flat, so the inventory dependence is not settled.

**There is no hidden fair value in the ladder.** The skew of its two tops against others' bids does not predict
the next public mid: Spearman -0.025 at 10 s and -0.054 at 30 s (n = 3,300). So outside its own events the
maker quote is a public-book function plus own state, and the private input enters only at its events (the pull
and the re-pair).

A rule of the form "join others' bid on both tokens, capped at a pair sum K, shaded by state" has not been tested.
The 0.305 / 0.396 anchors are not its ceiling.

### 2. Outcome: the per-market PnL is the *passive* pair margin, and it is specific to the wallet's quote, not to the market path

| Check | BUILD | VALIDATE |
| --- | --- | --- |
| Event pairs (its take plus complement maker fills signed 1-5 s later) | 3.1% of pairs, $686 of $9.6k locked | 3.5% of pairs, $814 of $11.9k locked |
| Per-market PnL vs passive locked margin (Pearson / Spearman) | 0.85 / 0.67 | 0.83 / 0.74 |
| Locked margin vs margin (1 - pair cost), Spearman | 0.83 | 0.81 |
| Locked margin vs pairs, Spearman | 0.31 | 0.46 |
| Wallet's per-market pair cost vs other makers' pair cost (Pearson / Spearman) | -0.15 / -0.02 | 0.05 / -0.04 |

What follows from this:

- The variance does not sit in the event pairs, and the margin drives the locked total more than the number of
  pairs does.
- The pair cost is not a property of the market path that all makers share. The comparison uses every other
  maker's in-play BUY fills on both tokens, from the full matched-order record. Against other 100-share makers
  the correlation is -0.01..0.18.
- So the outcome target depends on reproducing *its* quote rule with a realistic queue (critique 1), not on the
  private signal.
- The earlier replays used two other quote rules: last print minus delta, and follow-the-pack. They also used
  two fill models: strict trade-through (which fills only adversely) and "a print at the bid fills it". So their
  negative correlations say little about the wallet's mechanism.

### 3. The on-chain taker set is censored by fill, and the FAK-return re-post separates attempts from pulls

A FAK that finds nothing leaves no transaction, so the 1,698 on-chain takes are the attempts that got a fill.

On the own recorder, its 100-share pulls next to its own takes are strongly directional: 27 pulls, team mid +6.5c
at 10 s, up in 93%. The client's FAK cycle also leaves a fingerprint: no own re-post on the pulled side during the
delay (0 in [900, 1000) ms), then a spike at [1000, 1150) ms (8.2 adds/s against 0.66/s in [60, 900) ms).

- **Where the strict signature appears.** "No own add in [60, 1000) ms and at least one in [1000, 1150) ms":

  | Pulls | Strict signature |
  | --- | --- |
  | Own-take pulls | 30% (8 of 27) |
  | Multi-level pulls with no on-chain take | 3.3% (18 of 549) |
  | Single-level pulls with no on-chain take | 2.7% |
  | Random times | 1.3% (5 of 400) |

- **The 18 strict non-take pulls are directional.** The team mid moves +2.7c at 10 s and +4.6c at 30 s, up 72%
  against down 17%; at random times, up 18% against down 19%. The single-level ones are not directional (33% /
  30%).
- **Size of the excess.** About 11 of the 18 are excess over the random rate. With a 30% recall, that is roughly
  as many hidden attempts as visible ones.
- **Note.** The assumptions panel (P4) proposes the pull as the unit. The pull alone cannot tell a zero-fill FAK
  from a protective pull with no FAK. The silent delay window followed by the 1.04 s re-post can.

### 4. The FAK limit is not "ask + 0-5c"; it carries the size of the coming repricing

On 16-22 Oct, I measured the premium as limit minus the first matched price (n = 1,631 takes with a tape).

**Premium distribution.**

| Premium | 0c | 1c | 2c | 3c | 4c | 5c |
| --- | --- | --- | --- | --- | --- | --- |
| Share of takes | 42.8% | 24.2% | 15.3% | 7.4% | 5.5% | 4.5% |

**The premium predicts the size of the move that follows.** Moves are of the bought team's price, wallet trades
excluded.

| Split | Spearman with the 10-s move | 10-s move at premium 0 / 1 / 2 / 3+c |
| --- | --- | --- |
| BUILD | 0.26 | +2.2 / +2.3 / +3.9 / +5.6c |
| VALIDATE | 0.20 | +2.4 / +1.7 / +3.4 / +5.2c |

At 120 s, the move at premium 3+ is +8.7c (BUILD) and +6.6c (VALIDATE).

**It does not follow price level or market type.** The premium's Spearman with closeness of the price to 0.5 is
-0.03 / 0.02. The mean premium is 1.1-1.5c for both map and match markets.

So the limit is set from the bot's own estimate of the post-event value. That estimate is a second, quantitative
readout of the private signal beyond the side.

### 5. Quick checks that came out negative (so nobody redoes them)

- **No phase lock of signing times to a periodic feed frame.** The test is a Rayleigh test of `sign_ms mod P`
  within each match, for P = 100-5,000 ms, over 67 events with at least 8 takes.
  - Wallet taker orders: mean z 0.85-1.16, against 1.0 under the null and 0.72-1.22 for a jittered control.
  - Its maker bursts: mean z 0.83-1.10.
  - Pack signers reach 1.0-1.9 at every period alike. That is clustering inside bursts, not a period.

  So this is not a polled or framed feed with a stable phase per match.
- **Its re-posts do not react to public trades.**
  - Of its +100 add bursts (4,075; 89% single-level), 0.0% follow a trade message within 60 ms, and 43% are
    cancel-replace (an own cancel in the previous 60 ms).
  - The interval between bursts on a token side has a median of 0.66 s (p25 0.10 s, p90 16 s), with no fixed timer.
  - On history, only 9.6-9.7% of maker signings fall 0-150 ms after a public match (taker signing + 1,040 ms). Their
    price is within 1c of that trade's price in only 25-29%.
- **Co-movement with others' touch changes is symmetric.**
  - 37% of its add bursts follow another maker's change at the touch within 30 ms, against 4.1% at random times.
  - But the shares before and after are about equal: pure adds 28% before vs 26% after; its cancels 34% vs 37%.

  Timing alone does not show that it pegs to the touch. Show it by price consistency (proposal 1, step 4).
- **The maker price is not locked to its cost basis.**
  - Maker price plus its last complement fill: within 1c of 0.98 in only 23-24%.
  - Short-side bid plus the cost of the unpaired long inventory (average or LIFO): within 1c of the mode in
    17-23%.
- **The re-pair is a partial lock.** 360 of 1,698 takes have a filled complement re-post signed 1.00-1.15 s
  later. Re-post top plus the FAK limit has its mode at 0.96 (BUILD) / 0.95 (VALIDATE) and falls within 1c of that
  mode in 54% / 65%. That is a usable sub-rule for that state, not the general quote.

## Proposals, ranked by the chance they close the gap

### 1. The maker quote is a pair-sum-capped join of others' best bids: decode it on others' book, not on fills (strong form of X33 / ladder_decode, and of the iter-2 mechanics P2 price step)

- **Hypothesis.** For each token X, `top_X = others' best bid on X - s_X`, with `s_X >= 0`.
  - The shades satisfy `s_A + s_B = max(0, obb_A + obb_B - K)`, with K about 0.96-0.97. So it joins both bids when
    others' spread is at least 3-4c and steps back when it is 1-2c.
  - The shade goes to one side by state: inventory, time since its last take, and possibly price level.
  - Below the top sit 1-8 levels at 1c, of 100 shares in CS2 (inventory-scaled when small). It never bids above
    others' best bid.
  - There is no private fair value in it. The private input enters only through the pull and the re-pair
    (K - limit, mode 0.95-0.96) at its events.
- **Why it fits.** See critique 1:
  - the top sits at others' bid or 1-4c below it, almost never above;
  - the pair sum follows min(others' sum, 0.97) within 1c in 59%;
  - the shaded side moves with inventory in one of the two directions;
  - the ladder skew does not predict the mid;
  - re-posts do not react to trades.

  This is also the mechanism the 97% pairing at a pair cost of 0.978 needs.
- **Test.**
  1. **Attribution.** In its non-GRID traded markets, track its levels by a whole-cent ±100 change plus the
     inventory-scaled sizes found by the assumptions panel's P3. Validate the attribution on its filled orders
     (+100 add at +19-24 ms after signing). Use untraded non-GRID markets as a control (0.7 such adds per hour
     against 348 in its markets). Others' book = book minus own levels.
  2. **Fit.** On live BUILD blocks (before 11-01 12:00 UTC), fit (top_A, top_B, depth) at each own change. Use a
     depth-3 tree or an explicit rule on:
     - others' best bid and ask on both tokens, and others' bid sum;
     - its net inventory (report the model with and without it);
     - time since its last take and its last fill;
     - price level.

     Freeze K and the shade rule.
  3. **Score.** On live VALIDATE blocks (from 11-01 18:00 UTC), score `price_within_tick` (0.01) on every ladder
     level and on its filled orders. Compare against the trivial anchors: join others' bid, last print, and its
     own pre-burst touch.
  4. **Price consistency of the peg.** When others' best bid on X moves by ±1c, or the mirrored ask on the
     complement moves, does its top on X move the same way within 50 ms? Compare with a time-shift null. This
     settles the symmetric co-movement in critique 5.
  5. **Historical analogue for h1/h2.** Rebuild others' book from the matched-order record: maker orders signed
     before t and filled after t, both tokens mirrored, its own orders removed. Score the frozen rule on the
     VALIDATE fills of 21-22 Oct, and report what the censored book costs.
- **Data.** `tommy_cs2_near` (all dev blocks), `calldata_dev` refreshed per block, `calldata_all` + `calldata_pub`
  for the historical book.
- **Signature if true.**
  - K is stable across blocks (within 1c).
  - The shade side is predicted well above chance.
  - At least 75-80% of levels, and of filled orders, fall within one tick on VALIDATE blocks, against 50-62% for
    "join others' bid".
  - It also yields a clean quote-presence label (a ladder resting on token X per bin) for the presence pivot the
    RE plans. That label is examinable on future blocks only.
- **If false.** If the shade cannot be predicted, the price component is capped near 0.6 and should be tagged that
  way.

### 2. Outcome by a queue-aware replay of that quote on the full matched-order record (strong form of X17 and iter-1 assumptions P3; examinable on h1/h2)

- **Hypothesis.** The per-market PnL ranking is set by the passive pair cost that its quote rule realizes with its
  queue position. A frozen proposal-1 quote, replayed with price-time priority against the actual takers,
  reproduces that ranking without the private signal.
- **Why it fits.** See critique 2:
  - event pairs are 3% of pairs and 7% of the locked dollars;
  - per-market PnL follows the passive locked margin (0.83-0.85 Pearson);
  - its pair cost is unrelated to other makers' pair cost, so the margin is a property of its own rule;
  - no earlier replay used its rule or a queue model.
- **Test.**
  1. **Order record.** For every development market (16-22 Oct plus dev blocks), list every taker tx: signing ms,
     limit, size, token and side, and the per-signer match delay from X27, about 1,040 ms for fast signers. Add the
     maker orders each tx matched: signing ms, price, original size.
  2. **Replay.** Post the proposal-1 ladder: others' book from the record, re-quoted on others' touch changes on
     the match clock, 100 shares, pair-sum cap K. A taker tx fills our order when two conditions hold:
     - it matched resting liquidity on the same economic side (a BUY of X at p, or a BUY of the complement at
       1 - p) at a price no better for the taker than ours;
     - our order had priority: a better price, or the same price and an earlier signing than the makers it
       actually hit.

     Our fill removes the same quantity from the makers who were behind us. Merge pairs, hold the residual,
     settle.
  3. **Correlation.** Report the per-market Pearson and Spearman of PnL, and of pair cost, against the wallet,
     BUILD and VALIDATE separately. Variants:
     - (a) no event pulls;
     - (b) its pulls at its takes inserted as given (oracle, diagnostic only);
     - (c) on future blocks, pulls at the public cancel-wave proxy (the first non-own cancel wave on the server
       clock).
- **Data.** On disk: calldata_all, calldata_pub, per_market, outcomes. Live blocks for (c).
- **Signature if true.**
  - Variant (a) reaches Spearman 0.5 or more on pair cost and PnL in both splits. The outcome component is then
    executable and h1/h2-examinable.
  - If only (b) reaches 0.5, the margin depends on the event pulls, and the outcome claim has to wait for
    variant (c) on future blocks.

### 3. Inverse-fit the FAK limit and size as the bot's private post-event value (new; B3 for the taker leg)

- **Hypothesis.**
  - The limit is the pre-event best ask plus `g(D)`, where D is the bot's estimate of the event's price impact.
  - Size is a function of the stale depth up to that limit (median 0.31x).
  - In fan-out pairs, the match-leg and map-leg premiums are linked by the series sensitivity dP_match/dP_map.
  - D is a measurable, per-decision readout of what the private feed reports, beyond the side.
- **Why it fits.** See critique 4:
  - the dose-response from premium 0 to 3+ is +2.2 to +5.6c at 10 s, and holds in both splits;
  - the premium does not follow price level or market type;
  - the fan-out legs are signed 1-4 ms apart, so they carry one estimate.
- **Test.**
  1. **History, 16-22 Oct.** Regress the bought team's move at +10 / +30 / +60 s (tape, wallet excluded) on the
     premium. Controls: price level, map or match, time since map start, and pre-event stale depth (from the stale
     maker orders its FAK hit, signed before it). Use an event bootstrap.
  2. **Fan-out pairs** (60 historical plus the live ones). Compare `premium_match / premium_map` with the public
     sensitivity from pre-event prices. Under map independence, the sensitivity is P(series | win map k) minus
     P(series | lose map k), from the other maps' and the match market's prices. Slope about 1 means one valuation
     model drives both legs.
  3. **Event classes.** Fit a 2-3 component mixture to (premium, size / depth). Calibrate the classes on Dota 2,
     where `tommy_dota_live` gives kill and teamfight sizes with a clock (X24).
  4. **Taker price rule.** `limit = pre-event ask + round(a + b * predicted D)`, with D predicted from pre-event
     public state, scored within one tick on live VALIDATE blocks. Today "pre-event ask + 1c" is within one tick
     for 82% on history (first matched price as the ask proxy) and 62.5% live.
- **Data.** On disk: orders, calldata_all, tapes, pack_orders. Live: `tommy_cs2_near`, `tommy_dota_live`.
- **Signature if true.**
  - Positive slopes in both splits.
  - The fan-out premium ratio tracks the sensitivity.
  - Discrete classes appear.

  This gives a taker price rule and tells which in-round event the feed carries (a kill-sized against a
  round-sized D), without a stream. If the ratio does not track the sensitivity, the legs use a fixed premium
  schedule, which is itself a frozen rule.

### 4. Count zero-fill FAK attempts with the FAK-return re-post fingerprint (complements assumptions P4; strong form of X30)

- **Hypothesis.** On a signal, the client sends a FAK, pulls its complement ladder at +11-22 ms, waits for the FAK
  response and re-posts at +1.00-1.15 s, whether or not the FAK filled.
  - Zero-fill attempts are invisible on chain.
  - Pull-only protection (no FAK) has no reason to wait exactly one delay before re-posting.
- **Why it fits.** See critique 3:
  - the strict signature follows 30% of the pulls at its own takes, 3.3% of multi-level pulls with no on-chain
    take, and 1.3% of random times;
  - those 18 pulls are 72% directional (+2.7c at 10 s), like its takes;
  - X30 tested censoring only through other makers' collapses, using on-chain takes as the label.
- **Test.**
  1. **Detector.** On every dev block of `tommy_cs2_near`: a pull is at least 2 own-level cancels on one token side
     within 5 ms, with own sizes attributed as in proposal 1. The strict form adds no own add on that side in
     [60, 1000) ms and at least one in [1000, 1150) ms. Check the complement token too, for fan-out.
  2. **Calibration.** Measure recall on the on-chain takes. Measure the false-positive rate against a time-shift
     null (±k × 7 s) and on GRID markets.
  3. **What the excess looks like.** For pulls with the signature but no take: directionality (team mid at +10 s),
     the other-maker cancel wave after the pull, the pack's response, and the pre-event stale depth on the consumed
     side, which should be thin for zero-fill attempts.
  4. **Rates.** Attempts per pack event and per bo3 round, and the attempt fill share against stale depth.
- **Data.** `tommy_cs2_near`, `calldata_dev` (refresh it to the end of each block so late takes are not counted as
  non-takes).
- **Signature if true.** An excess over the time-shift null in every block, at least 70% directional, with thinner
  pre-event depth than its filled takes.
  - Then the taker decision unit is the attempt, the "acts on x% of events" figures are fill-censored, and the
    examiner gets a fill-independent taker label on future blocks.
  - If the excess is zero, its pulls without a take are protective-only decisions on the same signal, which is
    worth stating in the maker component.

## Overlap with the other iteration-3 panels

- The assumptions panel's P3 (order-level cancel attribution, including its non-100 sizes) is a prerequisite for my
  proposals 1 and 4.
- Its P4 (the pull as the unit) is the parent of my proposal 4. Mine adds the timing test that separates zero-fill
  FAKs from protective pulls.
- Its P6 (signer EOA and funding) covers the C1 line, so I do not repeat it.
