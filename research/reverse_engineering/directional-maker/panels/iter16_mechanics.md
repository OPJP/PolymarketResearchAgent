# Panel after iteration 16: mechanics and on-chain forensics

Lens: how the orders are built, how a resting rung moves between its post and its fill or cancel, and which clock moves
it. Two points matter most.

1. **Most of the cluster's 500 adds are steps of a walking rung, not fresh quotes at a target.** Iteration 8 measured
   this (fast re-posts step up 3-4 c, 95% upward, unrelated to the mid, Chainlink and futures) and left it as "a ratchet
   or a three-wallet pairing artefact". Every later quote test treated each add as a decision at its target: X146, X163,
   X166, X180 (ladder center), X181 (fair cap) and X135 (tracers). On the 11-01 single-instance block, where no sibling
   copies exist to mis-pair, the walk is still there. So the fair-cap and center fits on adds measure transit positions.
   Their low fits (0.14-0.30) and the 10-31 vs 11-01 "center coefficient" (0.30 vs 0.13) are partly built into the unit.
2. **The clock that moves the ladder changed between the two blocks, and it is a global pass across markets.** On 10-31
   the walk steps and resets come right after public Chainlink publishes. On 11-01 they do not. In both blocks the steps
   in one BTC window coincide to the 20 ms with the cluster's changes in another BTC window. X180 anchored its 11-01
   units on publishes that, on that block, did not trigger the passes.

Written 2026-11-01, 10:10-10:45 UTC.

**Data I used.** Development data only (checked with `tools/sealed.py directional-maker`):
- `dm_clob_raw` (full depth) for 10-31 15:00-15:45, 10-31 17:33-18:00 and 11-01 07:30-08:15;
- `dy_rtds` (BTC publish ms) and `dm_bnf` (Binance USD-M bookTicker) for the same spans;
- `b1_cluster_orders_study.parquet` (STUDY calldata, 10-23..26: released lot, first half);
- `it15_today_orders.parquet` (11-01 06:07-07:38 calldata).

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it16m\`:
`ratchet.py`, `ratchet2.py` ... `ratchet7.py`, `bands.py`, `salt_rungs.py` and `salt_rungs2.py`. Run them from the repo
root as `python <script> <start> <end> <label>`. Each one peaks below 300 MB and takes 2-4 minutes per 45-minute span.

Definitions used below:
- A **fast step** is an exact -500 level change followed or preceded within 20 ms by an exact +500 change at another
  price, on the same window and outcome. Prices are in bid terms of the outcome: an Up-book ask at p is a Down bid at
  1 - p.
- A **delayed re-add** is a removal with no such partner, followed by the next +500 add on that window and outcome within
  20 ms to 2 s.

## What my checks found

1. **The walk persists without sibling copies, with a fixed step and a touch cap.**

   | | 10-31 15:00-15:45 (triplets) | 11-01 07:30-08:15 (bosona alone) |
   | --- | --- | --- |
   | removals of an exact 500 | 19,890 | 12,564 |
   | fast step to another price | 34.5% | 40.9% |
   | of which upward | 94.1% | 87.9% |
   | step of +2 c / +3 c / +4 c | 38% / 25% / 9% | 32% / 34% / 7% |
   | new price below the touch / at it / above it | 90.1% / 9.9% / 0% | 96.3% / 3.7% / 0% |
   | delayed re-add (20 ms - 2 s), share of removals | 62.1% | 54.5% |
   | delayed re-add lower / higher | 71.5% / 22.2% (median -2 c) | 74.0% / 17.7% (median -2 c) |
   | same-price re-add within 100 ms | 15.5% | 24.6% |

   - The step does not grow with the distance to the touch. On 11-01 a rung 2-3 c below the touch steps +2 c (median), a
     rung more than 10 c below steps +3 c. On 10-31 the medians are +2 c and +3 c.
   - A rung 2-3 c below the touch reaches it in 61-62% of its steps. From 4-6 c below, only 5-11% of steps reach it.
     Rungs therefore climb in fixed increments and stop at the touch. They never post above it.
   - Down moves are cancel first, then a later, lower add.
   - Rotation check (`ratchet3.py`). A ladder block at 1-c spacing would show live exact-500 units at the intermediate
     prices of a +2/+3 c step. Those prices hold one in only 6-14% of steps, the same as the prices just above the new
     one (5-11%). So a single rung walks; it is not a block shifting by rotation.
2. **What clocks the steps changed between the blocks** (`ratchet4.py`, `ratchet5.py`, `ratchet6.py`).
   - Share of moves within 300 ms after a public BTC publish:

     | | up-steps | resets | random moments |
     | --- | --- | --- | --- |
     | 10-31 17:33-18:00 | 0.514 | 0.560 | 0.297 |
     | 11-01 07:30-08:15 | 0.342 | 0.307 | 0.301 |

   - On 10-31 the delay since the publish has p10 10 ms and p25 25 ms, against 102 ms and 248 ms at random moments. The
     engine reacts to the publish within ~10-25 ms on the CLOB server clock.
   - Binance futures moves of $5 or more in the prior 300 ms precede 2.8-3.2% of up-steps (always toward the outcome)
     and 2.1-3.4% of resets (always against it), against 0.2-0.5% at random moments. Futures moves are a real trigger,
     but a rare one.
   - On 11-01, a print in the same window within 150 ms precedes 26% of up-steps, against 18% at random moments. That
     is weak.
   - On 11-01, therefore, about 85-90% of the walk steps follow neither a publish nor a futures move nor a print.
3. **The age of the stepped unit has median 663-664 ms on both blocks.** On 11-01 there is also a mass under 100 ms
   (p10 48 ms): rungs take several steps in quick succession.
4. **One pass for all markets** (`ratchet7.py`, 11-01 07:30-08:15).
   - 46.2% of the up-steps in one BTC window have an exact-500 change in another concurrently recorded BTC window within
     +-20 ms.
   - At the same moments shifted by +-250 or +-500 ms the share is 15.4-17.4%. At +1,000 ms it is 19.8%, a hint of a
     ~1-s periodic component.
5. **The own-outcome book mid is not the walk's reference** (`bands.py`). At up-steps, mid minus the old price and mid
   minus the new price are as diffuse as mid minus the price of every other exact-500 add: the top eight half-tick bins
   hold 36-37% against 32%, with no modes. A band keeper on the book mid would show sharp modes.
6. **Salt adjacency is too thin to read the ladder historically** (`salt_rungs2.py`, STUDY).
   - Filled orders of one wallet with consecutive salts: 44 pairs. All are on the same token, at +1 c in 25 and at 0 c
     in 11, mostly 62/62 sizes. The off-session ladder is signed bottom-up at a 1-c spacing.
   - Only 61 transactions fill two or more of one wallet's orders. Rungs are rarely swept together, so the calldata
     alone cannot reconstruct the ladder.
7. **The signing rate fell in the single-instance mode** (`it15_today_orders`, 11-01 06:07-07:38). Median pairwise salt
   slopes: bosona 9.3 orders/s (IQR 8.4-10.5), mo-money 7.2, almach 6.9. On 10-31 each wallet signed 16.7-17.2 orders/s
   (X17). So the per-account signing budget does not bind, and the three accounts do not exist to multiply an API rate
   budget.

## Critique

1. **The quote is decoded as a level when it is a process.**
   - The engine's decision is a state machine: post at an origin, step up in fixed increments on each pass, stop at the
     touch, cancel and re-add lower on a reset.
   - The tests since iteration 13 regress single adds on a fair. With a fixed step and a touch cap, an add says only
     that the target lies at or above the new price. The informative events are the step and reset times, plateaus
     (same-price re-signs) and truncated steps (+1 c, or a step that lands on the touch).
   - The fair-cap rejection (X181, 0.14-0.27) and the 11-01 center coefficient (0.13) are what a slew-limited walker
     produces when it is sampled at random transit points. They are not evidence of a weaker reference.
2. **The reference was dismissed with a test that cannot detect it.**
   - "dp unrelated to the mid, Chainlink and futures change (corr 0.002-0.023)" is expected for any band or slew-limited
     keeper, because the step size is fixed by design.
   - The reference shows in WHEN a rung moves (the hazard as a function of R - p), not in how far it moves.
3. **X180 on 11-01 used the wrong clock.** On 11-01 the walk steps are not anchored at publishes (0.34 against 0.30 at
   random moments), so "the top add within 300 ms after a publish" is an add from an unrelated pass. The 10-31 vs 11-01
   comparison of the center is confounded by the clock change, just as X160 was confounded by the instance mode.
4. **The pass structure is ignored in every presence and selection unit.**
   - Presence is binned in 10 s, quotes in 300 ms after publishes, selection per print.
   - The engine acts in global passes (check 4). The natural unit is the pass: the resting state after pass n is
     fixed until pass n + 1.
   - Pass times are observable from the public book: simultaneous exact-size changes across markets.
5. **The exam can only see part of what is being decoded.** The sealed blocks have `dx_clob` (schedule-size deltas
   within 3 ticks of the touch, the touch queue every 200 ms) and the shared top-10 books, not full depth. Any walk-based
   rule has to be scored on the last 1-2 steps into the touch, which those feeds do record. Check this before freezing.

## Proposals (ranked by the chance they close the gap)

### P1. Decode the walking bid as a state machine, and predict the at-touch resting state from it (strong form of X71 and X51; the input X188 lacks)

- **Hypothesis.**
  - Each main-ladder rung (500 class) is a walker. On a pass with the target above it, it is re-signed d in {2, 3} c
    higher (cancel and re-add within 20 ms), never above the touch. When the target falls below it, it is cancelled
    and re-added lower 20 ms to 2 s later (the reset).
  - A fill needs a rung that has walked into the touch and a taker that reaches it before the next pass. So the resting
    state at a print is a function of the rung's last origin and time, d, the pass cadence and the touch cap.
  - That function is what print selection (oracle 0.81-0.83, X72) needs and public inputs have not supplied (0.742,
    X150).
- **Why it fits.**
  - Checks 1-3: a fixed step, a touch cap, cancel-first resets and a 0.66-s median step age on both blocks.
  - B2 and X33: fills come from fresh at-touch posts (age 0.68 s).
  - R7 (last print - 1 tick): a rung walking into a vacated level.
  - X135 and X181: no level law above 0.27, which is what transit sampling gives.
- **Test.**
  1. **Chains.** On 11-01 07:00-09:15 (bosona alone in 7 of 10 slots), link each exact-500 removal to its fast-step
     partner, or to its delayed re-add. A chain runs from an origin add (after a reset or a fresh post) to its fill or
     its next reset.
     - Anchor identity at the chain's end: the fill's trade hash in `dm_clob_raw` 'x' records gives the all-match
       calldata, whose makerOrders must contain bosona, size 500, at that price.
     - Report chain purity.
     - Repeat on 10-31 14:00-16:53 with the per-wallet triplet structure.
  2. **Move law, pre-registered.** Fit on 07:00-08:15 and score on 08:15-09:15.
     - (a) d against the gap to the touch, the time left, the mid and |F - mid|.
     - (b) the step cadence per chain.
     - (c) the share of chains that end at the touch.
     - (d) the reset trigger: a futures move against the rung, a posture flip at a publish, the touch falling through
       the rung, an own fill (reported as own state).
     - (e) the origin price after a reset, against public inputs (touch - k ticks, mid - h, F - h).
  3. **Forward replay.** Start the walk from each public origin, using (e) where it is decoded, else the observed origin
     (reported as own state). Use no later book information about the cluster's own orders. Predict the cluster's
     at-touch presence at every print in the next 1-5 s.
     - Score print selection (AUC; recall at lift 3) against the activity LightGBM, and against the true resting state.
  4. **Exam visibility.** Rerun step 3 with only what the sealed blocks record (`dx_clob` within 3 ticks, `clob_crypto`
     top 10). Report how much of the gain survives.
- **Data.** `dm_clob_raw` 11-01 06-12 and 10-31 14-18; all-match calldata of the fill transactions; `dy_rtds`; `dm_bnf`.
- **Signature if true.**
  - On held-out data, at least 85% of fast steps are +2 or +3 c.
  - The pass at which a chain reaches the touch is predicted within one pass in at least 70% of chains.
  - The walk replay from public origins lifts print selection from 0.74 to 0.80 or more at recall of at least 0.50.
  - If d instead scales with a reference change on held-out data, the ladder re-prices rather than walks: go to P2 with
    a re-pricing model.

### P2. Identify the reference by the hazard of the steps and resets, not by their size (strong form of the iteration-8 correlation test, B3, X180 and X181)

- **Hypothesis.**
  - The walk tracks a target T(t) = F_R(t) - m on some reference R. It steps up when F_R - p rises above an upper
    threshold, and is reset when F_R - p falls below a lower one (a band keeper or a slew limiter).
  - The right R makes the step and reset hazards a step function of x = F_R - p at constant thresholds, the same on both
    blocks. The "regime change" of the side would then be a change in R's inputs, not in the engine.
- **Why it fits.**
  - Check 1: the step size is fixed. Check 5: the book mid shows no modes.
  - Iteration 8: dp is unrelated to the Chainlink change (corr 0.007), which a fixed step predicts.
  - The posture works on 10-31 (0.85), so R is Chainlink-like there. X179: the nowcast helps on 11-01.
  - Check 2: steps react to publishes within 10-25 ms on 10-31.
- **Test.**
  1. Live rungs come from P1's chains, or from exact-500 levels between their add and their removal. For each live rung
     and each 50-ms bin, compute x_R = F_R(t) - p.
  2. Candidates R:
     - the Chainlink report on the exact publish clock and the nowcast k1.0;
     - the futures digital;
     - the own mid, the microprice, the last print, 1 - the other outcome's mid;
     - TWAP-60;
     - EWMAs of each at 1, 5 and 30 s;
     - for each, the vol multipliers k 1.0, 1.4 and 2.0.
  3. Fit a two-threshold hazard: P(up-step in the next 50 ms | x) and P(reset | x). Pre-register on 11-01 07:00-08:15.
     Score on 08:15-09:15 and, frozen, on 10-31 14-16 and 16-18.
  4. Report per R the step-hazard AUC among live rungs, the fitted thresholds and their stability across blocks.
- **Data.** As P1, plus `dz_rtdsbn` (the RTDS Binance relay) and `dv_rtds` for the cross-symbol candidates.
- **Signature if true.**
  - One R gives a step-hazard AUC of 0.85 or more, with the same thresholds within one tick on both blocks.
  - If Chainlink passes on 10-31 and nothing passes on 11-01, the 11-01 reference is a missing dimension. Run the same
    hazard on the ETH and SOL Chainlink publishes and on Binance spot, and record it in `dimensions`.

### P3. One engine pass for all markets: detect pass times from cross-market synchrony and find what triggers a pass (new; the timing component, and the unit for presence)

- **Hypothesis.**
  - The engine loops over every quoted market. Each pass re-signs or steps rungs everywhere. A pass starts on a union
    of triggers, for example:
    - a BTC, ETH or SOL Chainlink publish;
    - a futures move;
    - a print or touch change in any market;
    - an own fill;
    - a timer.
  - The trigger set differs between the 10-31 and 11-01 modes.
  - The resting state after pass n holds until pass n + 1.
- **Why it fits.**
  - Check 4: 46% vs 15-17%, with a hint of 1-s periodicity.
  - Check 2: steps are publish-clocked on 10-31, not on 11-01.
  - X17: one salt counter per wallet across all markets.
  - X53: trade-triggered joins are weak (0.61).
- **Test.**
  1. **Pass detector.** A cluster pass is a burst of exact schedule-size changes in two or more markets within 20 ms:
     - 500, 1000 and 2000 in BTC 5m/15m;
     - 400 in BTC 4h;
     - the deep-bid sizes.
     Use `dm_clob_raw`, `clob_crypto` and `dw_clob`. Validate with calldata: filled orders from one detected pass should
     have salts within the pass size.
  2. **Event study** of pass times against:
     - every publish series (`dy_rtds` and `dv_rtds`, every symbol);
     - BTC, ETH and SOL futures jumps (`dm_bnf`; Binance archives for ETH and SOL);
     - prints and touch changes in every recorded market;
     - own fills (own state, reported).
     Run a periodogram of pass times at 10-ms resolution over 0.1-2 s periods.
  3. **Presence unit.** Use (market, outcome, pass): is a cluster 500 at the touch after the pass? Fit the activity
     baseline at the same pass times.
- **Data.** `dm_clob_raw`, `dw_clob`, `clob_crypto`, `dy_rtds`, `dv_rtds`, `dm_bnf`; calldata of the fills.
- **Signature if true.**
  - A small trigger set with a fixed latency floor explains at least 80% of pass times, or a periodic component carries
    the remainder.
  - The trigger sets of 10-31 and 11-01 explain the clock change of check 2.
  - On the pass unit, at-touch presence beats the activity baseline by 0.05 AUC or more.

### P4. The side is decided at the chain's origin, not at the fill (new; the 11-01 side failure)

- **Hypothesis.**
  - The rung's outcome and origin are set when it is posted or reset. After that the walk is mechanical, so the side of
    a fill follows the posture at the chain's origin, one to several seconds before the match.
  - In the clean regime the posture moves between origin and match. That would explain why small-edge fills fell below
    chance on 11-01 (0.44-0.58, X178) while large-edge fills held (0.86).
- **Why it fits.**
  - X172: mo-money's resting rungs carry the posture of about 1 s earlier.
  - X96 rejected the taker's arrival posture, which is a different time.
  - Check 3: chains of several 0.66-s steps put origins 1-5 s before the fill.
  - Check 2: on 11-01 the steps are not re-checked at publishes.
- **Test.**
  1. For every filled 500 order of bosona on 11-01 07:00-09:15, and of each wallet on 10-31 14:00-16:53 (calldata plus
     the recorder's match ms), walk its chain back to the origin add (P1).
  2. Score the posture (report and nowcast, k 1.0) at the origin time against the posture at the match, by |F - mid|
     band.
  3. Pre-register: the origin posture beats the match posture by 0.05 or more in the 11-01 small-edge band.
- **Data.** As P1, plus the shared recorder's trade stream with tx hashes.
- **Signature if true.**
  - The origin posture scores 0.80 or more on 11-01 (against 0.56-0.63 at the match) and about 0.85 on 10-31.
  - The origin-to-fill lag predicts which fills fail.
  - Historical form for VALIDATE: the origin is unobservable without books, so report coverage. The exam blocks have
    `dx_clob` within 3 ticks: score the posture at the first within-3-tick add of the chain.

### P5. Do the engine instances share state? Cross-account crossing and joint caps in the split mode (new; the instance_mode component)

- **Hypothesis.**
  - A single engine with common state over the three accounts never lets bosona's main-ladder bid on one outcome and
    almach's or mo-money's deep bid on the other sum to 1 or more, which would mint the cluster against itself. It caps
    them jointly.
  - Three independent processes running the same code would not.
  - The answer decides whether instance_mode is one engine's module table (one rule with a switch) or three policies
    (per-wallet rules for the exam's replication condition).
- **Why it fits.**
  - X177 and X178: on 11-01 bosona runs the main ladder while the others run deep bids and the slow families.
  - C7 found no cluster-against-cluster matches on STUDY, but only in the triplet mode.
  - X76 and X172: the instances differ in reference delay and cancel lag.
- **Test.**
  1. On 11-01 07-12, from `dm_clob_raw`, compute at every event the sum of the highest exact-500 bid on outcome A and the
     highest deep-module bid on outcome B (deep-module sizes from calldata). Count how often the sum reaches 0.99 or
     more, against a null that shifts outcome B's series by +-30 to 120 s.
  2. Check the all-match calldata of 11-01 for any cluster taker matched against a cluster maker.
- **Data.** `dm_clob_raw` 11-01 06-12; all-match calldata of that block.
- **Signature if true (shared state).** Zero crossings and a hard ceiling of the sum below 1 - m that the shifted null
  breaks. Crossings, or cluster-against-cluster mints, mean independent processes, and the rule and the exam scoring
  should be per instance.
