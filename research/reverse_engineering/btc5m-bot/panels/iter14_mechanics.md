# Panel, iteration 14: mechanics and on-chain forensics

Reviewer lens: how the orders are built and filled. That covers the pre-signed ladder and its two sizes, how much of each
order actually fills and why, the remainder that rests, the per-wallet quote offset, and what a replica must simulate to
reproduce the window net.

Data I used, all development and all before H:
- `fills.parquet`: VALIDATE 10-16..22, used for window nets and PnL;
- `calldata_sample.parquet`: the 11 sample hours, with original sizes, limits and signing ms. 124 windows have 10 or more
  taker orders;
- `windows.parquet`;
- the iteration-14 frames in the session scratchpad `it14/`: `dcfit14_pred` (117,791 operator taker orders of 10-17..22,
  with dc14 side probabilities) and `hazard14_scored` (the 150,929 scored bins);
- `it13/hf_dl/pm_touch_2026-10-20/21`.

The wallet mapping, checked by joining calldata to fills on tx: GF = 0x0ca4..., XM = 0x3048..., DS = 0xc533...

Nothing sealed was read, and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` at 05:31 UTC 11-01 reported: released
none. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m14\`:
- `m14_pnl.py`: PnL decomposition;
- `m14_decomp.py` and `m14_size.py`: the oracle ladder, the sent-position controller and the seed oracle;
- `m14_orig.py`: original vs filled size;
- `m14_copyorder.py`: copy order, burst / token dispersion, the short-leg gate, mark-to-market;
- `m14_burst.py`: ladder layout of large vs small;
- `m14_redraw.py`: the size-lottery ceiling and depth-bound shares;
- `m14_rr.py` and `m14_xmdrift.py`: dispatch regularity;
- `m14_touchbase.py`: the touch-aware baseline.

Apart from this file I wrote nothing to the workspace.

## Critique

1. **Condition 5 now hinges on the realized size, and most of the realized size is the depth each order found.** Neither the
   tracker targets nor the replica plan see depth. Below is an oracle ladder on 10-20..22. It covers 759 windows and the true
   operator taker orders of `dcfit14_pred`. N is the window net over both roles, and the PnL r is corr(x * (up - 0.5),
   window PnL).

   | per-order size × side | r(N) | PnL r (P / S) |
   |---|---|---|
   | true side, unit size | 0.369 | 0.24 / 0.28 |
   | dc14 side probability, unit size | 0.403 | 0.32 / 0.33 |
   | dc14 side, public size (wallet × arm × minute, fit 10-17..19) | 0.393 | 0.31 / 0.32 |
   | dc14 side, size by (wallet, arm, the wallet's realized net on the token ≥ 2 s before) | 0.601 | 0.55 / 0.56 |
   | dc14 side, true filled size | 0.747 | 0.70 / 0.70 |
   | true side, true filled size | 0.933 | 0.83 / 0.87 |

   These are the operator's own decisions. With the public side, perfect timing gains almost nothing until the size is
   right. The public part of the size (wallet, arm, minute) is worth nothing. The step from 0.39 to 0.75 is the realized
   size.

   The calldata sample hours show what the realized size is made of (11,382 taker orders):
   - **Depth-bound orders.** 62.5% of taker orders fill less than their original size in their taker tx. That is 88.7% of
     LARGE orders and 58.3% of small ones.
   - **Large orders fill little at once.** The filled shares of a large order have quantiles 5 / 13 / 45 / 96 / 100
     (q10 / q25 / q50 / q75 / q90).
   - **Their share of the net.** Depth-bound orders carry 51.8% of the filled taker shares. Their part of the window taker
     net has r 0.716 with it, and 0.68 of its variance. By wallet, GF 0.636 of filled shares, XM 0.532, DS 0.444.
   - **Window taker net by size definition.** Counts give r 0.60, original sizes 0.837, min(small menu, filled) 0.73, and
     filled 1.

   The iteration-13 panel read the 43% of original-100 orders that fill under 45 shares as race censoring. For the window
   net it matters less why the fill is capped than that it is capped at the depth available at or below L. At the bot's
   view (a - 30 ms), that depth is a public quantity in the capture's `price_change` and `book` rows (`askPrice`,
   `askSize`, the `bids` / `asks` lists). It has never been ingested.

2. **The planned replica (next step 2: "the replica's own sent position for size") cannot reproduce the lean.** I ran a
   sent-position controller on the TRUE decision record:
   - sizes from the fit-day lookup (wallet, arm, own-net bin on the token);
   - the bin taken on the controller's own expected position;
   - no fills.

   It reaches r(N) 0.401 with dc14 sides (PnL 0.34 / 0.35) and 0.432 with true sides. Knowing the true size of each
   window's first large filled order (the "seed") lifts it only to 0.492. The 0.60 of the realized-net lookup comes from the
   realized fills. A replica therefore has to simulate its own fills on the recorded book. Sent orders are not enough.

3. **X82's bound is not the condition-5 ceiling.** X82 put the bound at r 0.47-0.58 ("race lottery amplified by
   pyramiding"). That bound came from independent race lotteries and size redraws with no depth. I redrew each taker order's
   size on the calldata hours from P(large | wallet, day, arm, the short-leg gate on the redrawn running net), kept the true
   decisions and sides, and capped each fill at the true depth of partial fills. The results:
   - two redraws correlate 0.93;
   - a redraw against the true taker net gives 0.785 [q10 0.764, q90 0.831].

   The test is optimistic: it uses the realized depth of partial fills as an oracle, and assumes a fully filled order had at
   least the redrawn size available. But it shows that the size lottery itself is not what binds. Together with X93 (the race
   is nearly deterministic given the arrival), condition 5 is bound by decoding the decisions and the depth. The wall-level
   reading of X81 / X82 should not be carried into a wall claim.

4. **The ceiling arithmetic for a ≥ 2-s tracker sets the bar for the target** (`m14_pnl.py`; VALIDATE, 1,904 windows).
   - The window PnL is net × outcome plus the set (pair) part minus fees. Pearson with net × outcome is 0.885 (Spearman
     0.907); adding the set part and fees gives 0.967 (Spearman 0.986).
   - The set part has sd $74.6 against a PnL sd of $203.
   - A tracker that enters 2 s late cannot earn the operator's snipe pairs. So its PnL r is about 0.89 × r(target net, N).
   - To reach 0.50 on both Pearson and Spearman with margin for the halves, the target's window-net r has to be about
     0.56-0.58. mix14 reaches 0.5125. Proposal 1 is the only source in view for that 0.05.

5. **The decision-clock presence margin survives a book-aware Polymarket baseline. Its remaining exam risks lie elsewhere.**
   I added best-ask touch features to the Polymarket-only hazard baseline (`m14_touchbase.py`; 10-20 / 10-21, fit one day,
   score the other). The features were:
   - o's ask, bid and ask age;
   - ask changes over 250 / 1000 ms;
   - o's bid age;
   - the other outcome's ask, ask age and changes.

   The baseline rose from 0.7606 / 0.7620 to only 0.7763 / 0.7748, against the full model's 0.8935 / 0.9016. The gain is
   +0.117 / +0.127. The makers' requotes at the touch are not a shadow of the decision.

   What remains:
   - **(a) Size-only level events in the baseline.** An examiner may add them, and they are not ingested (X114).
   - **(b) The label scope.** The label covers taker first legs only, 77.9% of fills.
   - **(c) The fit set for the examiner's baseline.** The brief says BUILD data, but the capture starts on 10-17, so the fit
     set has to be declared in the pre-registration.

6. **XM: dispatch shows no structure to exploit, and the price part is not frozen.** The thinning ceiling for XM's PnL
   (0.43) stands; see the checks below. But condition 7's price part also fails for XM at the plain anchor:
   - XM's limit is 0 c above o's ask at arrival - 30 ms in 31.5% of orders, +1 c in 35.0%, +2 c in 16.8% and +3 c in 11.2%;
   - within a tick that is 66.4%, below the 77% that condition 7 asks;
   - the per-wallet +1 c anchor reaches 83.2%, but on two calldata hours, in sample, and not frozen (iteration-13 finding
     12, iteration-14 next step 2, not done).

## Checks (so nobody redoes them)

- **The size choice is not tied to copy order or to the burst.**
  - Copy order: P(the first copy used at a (wallet, burst, token, cent) is the large one) is 0.479 against 0.456 at random.
  - Burst: within (wallet, day, arm) cells, the large share is overdispersed only mildly by (wallet, burst), chi2/df 1.23
    (placebo 0.90).
  - Token: it is overdispersed by (wallet, burst, token) at 2.08 and by (wallet, window, token) at 2.71 (placebo 0.98).
  - So the lean is a token state that persists across the window's bursts. It is not a ladder composition chosen at signing.
  - In the ladder, large and small copies of a cent are signed together; the large one comes about 0.4-0.6 ms after the
    small one.
- **The short-leg gate, own state, mechanism only** (calldata hours; the pooled operator net on the token before the order).
  P(large) by that net:

  | wallet | short > 150 | flat | long > 150 | within-wallet AUC |
  |---|---|---|---|---|
  | GF | 0.068 | 0.390 | 0.525 | 0.756 |
  | XM | 0.035 | 0.161 | 0.200 | 0.683 |
  | DS | 0.083 | 0.152 | 0.182 | 0.598 |

  P(large) is flat in the held leg's mark-to-market (price minus average cost, from -0.10 to +0.10 and beyond). Large
  orders are almost never used to pair the short leg. They are not a response to winning or losing.
- **No per-window position or cost cap.** The tails are smooth. The pooled max |cumulative net| has a 99% quantile of 1,141
  shares, a 99.9% quantile of 1,368 and a maximum of 1,394. The per-wallet tails are smooth too.
- **Dispatch is not a weighted round-robin** (`dcfit14_pred`, 10-17..22).
  - Gaps between consecutive XM orders have a CV of 1.10 (all taker orders) and 1.13 (first legs), against 0.97-0.98 for a
    geometric gap.
  - There is no periodic ACF peak (max 0.025-0.029 over lags 1-40).
  - The window-level XM first-leg share has chi2/df 1.22 (1.19 day-adjusted) and an AR(1) of 0.009 across consecutive
    windows. The hour-level chi2/df is 1.91. Daily XM shares are 0.038-0.050.
  - There is mild clustering inside windows and no persistence across them. Nothing raises XM's P^(wallet) beyond thin14.
  - Daily fee shares are stable from 10-14: XM 0.069-0.090, GF 0.30-0.37, DS 0.54-0.62. These are fixed weights, not
    quotas.
- **The touch-aware Polymarket baseline** is critique 5: 0.776 / 0.775, gain +0.117 / +0.127.
- **Set part of the PnL** is critique 4. Paired shares are buys of both outcomes; there are no MERGE rows (B4). A
  ≥ 2-s-latency rule cannot reproduce them, so do not spend time on a set-profit target.

## Proposals (ranked by the chance of closing the gap)

### 1. Filled size is the visible depth: put the capture's L2 at the bot's view into the condition-5 target and the maker remainder stream (new; strong form of X51, X132's L2 part and X133)

**Hypothesis.** Each decision's realized size is set by two things:
- **The menu size.** It depends on the wallet, on the window arm, and on the short-leg gate on the operator's position on
  the token.
- **The depth at or below the limit L at the arrival.** That is the depth the order can still take after co-arrivals and
  maker cancels in the 150-ms hold.

For large orders the depth binds almost always (89%), and for small ones more than half of the time. The depth visible at
the bot's view (a - 30 ms server time) is a public, point-in-time input that is upstream of the window net. Two things
follow:
- the remainder (menu - taker fill) rests at L for the wallet's TTL;
- so the maker-role stream M is depth-shaped as well.

**Why it fits.**
- Critique 1: the oracle ladder, 62.5% / 88.7% depth-bound orders, and depth-bound shares carrying 52% of the taker shares.
- Critique 3: once the depth is known, the size lottery does not bind.
- X61: the asks the cluster's lost races aimed at were taken by other takers in 52.9%, by the cluster's own earlier legs in
  19.2%, and requoted away in 27.9%.
- X93: the race is deterministic given the arrival.
- The capture carries the depth: `askPrice` / `askSize` / `bidPrice` / `bidSize` on `price_change` rows, plus `bids` /
  `asks` snapshots on `book` rows (schema in `it13/hf_dl/hfprobe13.json`).

**Test.** Pre-register each step before ingesting.

0. **Data.**
   - From the pinned capture revision, read only these columns for 10-17..22: `eventType`, `tokenId`,
     `exchangeTimestampMs`, `askPrice`, `askSize`, `bidPrice`, `bidSize`, `bestAsk`, `bestBid`, and the book lists.
   - Read hour by hour through the row-group footers, with at most 2 threads.
   - Reduce at once to per-token tracks of level size for levels within 3 c of the touch. Keep the reduced parquet in
     `.cache/re/btc5m-bot/` (tens of MB per day) and delete the raw rows.
   - This also gives the touch for 10-17..19 and 10-22, which proposal 4 needs.
1. **Oracle on the true decision record** (10-20..22, plus the calldata hours for original sizes). For each operator taker
   order, compute:
   - D0, the size at o's best ask at a - 30 ms;
   - D≤L, the cumulative size at or below its limit.

   Then report:
   - the share of depth-bound orders whose filled shares lie within 10% of min(orig, D≤L); the remainder of them have been
     cut by co-arrivals or cancels in the hold;
   - r(N) and the PnL r of Σ side × min(E[menu | wallet, arm, gate], D≤L), with true sides and with dc14 probabilities,
     against the ladder rows 0.39 (public menu) and 0.75 (true filled). E[menu] is fitted on 10-17..19 and the gate is taken
     on the realized net, so this is an oracle row.
   - Adding the expected co-arrival take in the hold, E[crowd take | hazard] (`coat14`: 0.233 vs 0.074), gives a second
     variant.
2. **Public target.** For every 50-ms bin, take the frozen hazard × dc14 × E[min(menu, D≤L(o))]. Subtract the same for the
   other outcome, aggregate it like pre-registration 7's h(s), mix it with avg, and run trk_a with the frozen constants.
   Adopt it only if it beats mix14 on both pooled Pearson and Spearman over the 864 windows of 10-20..22. Report the 2-h
   CI, the halves and each wallet.
3. **M stream.**
   - The expected remainder is E[menu] - E[taker fill].
   - P(maker fill within the wallet's TTL) comes from the capture's non-operator BUYs of ō at or above 1 - L (the
     complement buyers who fill it) and o SELLs at or below L.
   - Score the expected M per window against M (frozen avg target 0.298) and add it to the target. Use the same adoption
     rule.

**Data.** The capture day files for 10-17..22 (3.6-5.4 GB each; only the selected columns and row groups),
`dcfit14_pred`, `hazard14_scored`, `calldata_sample` (original sizes), `fills.parquet` (labels only).

**Signature if true.**
- In step 1, at least 70% of depth-bound orders fill within 10% of min(orig, D≤L).
- r(N) of 0.60 or more with dc14 sides and public menus × depth, against 0.39.
- In step 2, a target window-net r of 0.56 or more, a tracker at 0.52 / 0.50 or better, and GF at 0.45 or more.
- In step 3, an M r of 0.40 or more.

**If false.** The filled amounts are set by co-arrivals and cancels inside the hold, not by the visible depth. Then the hold
queue is the binding race. Quantify it on the capture as the race share of the condition-5 account; that is proposal 2's
ceiling.

### 2. A replica that simulates its own fills on the capture, and the corrected condition-5 ceiling (strong form of X113 step 5, X93 and X82; replaces the "sent position" design)

**Hypothesis.** The window net is a path through three things:
- the operator's decisions, decoded by the hazard and the side;
- the short-leg-gated stochastic size choice;
- deterministic, depth-limited fills, which feed back into the gate.

A replica that resolves its own fills on the recorded book reproduces the lean as well as its decisions overlap the
operator's. One that tracks sent orders cannot (critique 2: 0.40-0.43 even on the true decisions).

**Why it fits.**
- Critique 2: the controller fails on sent orders and needs realized fills.
- Critique 3: the size redraw is not the ceiling.
- X93: the race is deterministic given the arrival.
- The pyramiding is a token state with a short-leg gate. It is in no current target.

**Test.**
1. **Ceiling first** (VALIDATE 10-20..22, all operator taker orders, with proposal 1's depth).
   - Keep the true decisions and sides.
   - Draw the menu from P(large | arm, gate) on the redrawn running position.
   - Resolve each fill as min(menu, D≤L minus non-operator trades matched in [arrival, arrival + 150 ms] at or below L,
     minus cancels at L seen in the capture inside the hold). The operator's own trades are left out: the replica takes its
     place.
   - Report the test-retest and redraw-vs-true r of the window net and of the PnL, pooled and per wallet. This number
     replaces X82's 0.47-0.58 in any wall account.
2. **Replica.** The steps:
   - Decisions are the hazard bins above a threshold. Set the threshold so that the number of decisions per hour on
     10-17..19 matches; or sample from it, with the expected value reported.
   - The side comes from dc14.
   - The menu comes from E[size | arm, gate on the replica's simulated position] fitted on 10-17..19, pooled over wallets.
   - Fills are resolved as in step 1, and the remainder rests for the pooled TTL Weibull (rem10).
   - Use the replica's simulated net path as the tracker target, or score it directly as the executable rule under the
     examiner's strict-fill convention.

   Pre-register it with the same adoption rule as in proposal 1.

**Data.** As in proposal 1, plus the rem10 / ins9b TTL fits.

**Signature if true.**
- In step 1, a redraw-vs-true r of 0.75 or more for the window net, with public depth instead of the oracle depth.
- In step 2, a replica window-net r of 0.56 or more and a tracker at 0.50 / 0.50 or better on both halves.

**If false.** Step 1 falls well below 0.785 once the depth is public rather than realized. Then the hold queue, which is the
operator's private arrival order among co-arrivals, is the measured limit. Report that number as the condition-5 wall
component.

### 3. Condition 2 at the decision clock, finished: label every decision from on-chain order structs, then harden the baseline against the full book (strong form of next step 1, X114, X129 and X65 / X77)

**Hypothesis.** The knee-clock hazard is the honest presence route. Its margin (+0.13) is robust to Polymarket book state.
Its unit can cover all fills, because every fully lost race leaves two traces:
- an on-chain order struct (price L, original size, wallet) in the calldata of its maker-fill tx;
- a book insertion at a known price and size in the capture.

**Why it fits.**
- Critique 5: the touch-aware baseline reaches only 0.776, a gain of +0.117 / +0.127.
- Finding 16: filled decisions cover 77.9% of fills, and fully lost races the other 22%.
- ins9b truth set: partial orders insert at (o, L) 17-33 ms before the trade message.
- B1: maker orders carry the full struct in matchOrders calldata.

**Test.**
1. **Label completion.**
   - For each order hash with maker fills and no taker fill, decode the struct from its first maker-fill tx with batched
     `eth_getTransactionByHash`; 10-20..22 at most, with backoff.
   - Locate the insertion: the first rise of o's bid size at L (or of ō's ask size at 1 - L) by the original size, in
     [first maker fill - 10 s, first maker fill].
   - Calibrate insertion - m on partial orders, where m is known.
   - Map each insertion to the knee-clock bin of the hazard label.

   Report the matched share and the fill coverage, which should be 95% or more.
2. **Baseline hardening.** The strongest Polymarket-only design ends at e + 50 and adds proposal 1's level sizes:
   - sizes at the best 3 levels of both outcomes;
   - size-only decrements and increments over 50 / 150 / 250 ms;
   - quote age;
   - non-operator prints at server ms.

   Fit it with the same model class and budget.
3. **Fit-set declaration.** Write into the pre-registration that both models and the examiner's baseline fit on 10-17..19,
   because the capture has no BUILD days. Then score the complete label once on 10-20..22, with the 2-h block CI, the
   halves and each wallet.

**Data.** `fills.parquet` (order hashes and roles), Polygon RPC for maker-fill txs, the capture L2 tracks from proposal 1,
`hazard14_scored`.

**Signature if true.**
- Fill coverage of 95% or more.
- Full AUC of 0.87 or more against a book-aware baseline of 0.82 or less.
- A gain CI lower bound above 0.05 in both halves and for each wallet.

**If false.** The level-size baseline closes the gap to less than 0.05. Then the makers' size shading carries the same
information. Condition 2 then has to be argued against a co-occurrence that sits on the book, not on the tape.

### 4. The per-wallet quote function for condition 7's price part: XM's pay-up as an inverse-fitted reservation offset (strong form of X42, X80 and iteration-13 finding 12; the frozen anchor was planned and not run)

**Hypothesis.** The limit is the pre-signed cent ask_seen + k. Here k depends on:
- the wallet (DS ~0, GF ~1 c, XM 1-3 c);
- the leg rank (later legs price over the levels earlier legs consume);
- the size of the knee-clock move, because the bot pays up to the ask it expects makers to reprice to.

On the plain ask, XM's price fails condition 7 (66.4% < 77%).

**Why it fits.** Critique 6. Pay-up is deliberate, not stale (iteration-8 finding 10). The pay-up rises with leg rank
(0.18 / 0.78 / 0.72 / 1.11 c). XM pays up even as a first leg (0.96 c).

**Test.**
1. Join the calldata limits of every sample hour on 10-17..22 to the capture's touch (proposal 1's ingest gives it for every
   day) and to `dcclock14_frame`, through tx → `pm_trades` m.
2. Fetch 4 more VALIDATE hours of operator taker txs if n is too small.
3. Fit an ordinal model of k on 10-17..19 per wallet, on:
   - leg rank;
   - |250-ms spot microprice return| at the knee;
   - o's ask change over the last 250 ms;
   - |p - 0.5|;
   - rel.
4. Freeze it and score it once on 10-20..22: within a tick per wallet and half, against the plain ask and the fixed
   ask + c_w.

**Data.** `calldata_sample` (plus up to 4 fetched hours), the capture touch, `dcclock14_frame`.

**Signature if true.**
- XM within a tick 80% or more in each half.
- k rises with the move strength and the leg rank on both splits.

**If false.** k is a fixed per-wallet offset. Then freeze ask + c_w from the fit days, report it as a trivial-anchor
variant, and check that XM stays at 77% or more in both halves.
