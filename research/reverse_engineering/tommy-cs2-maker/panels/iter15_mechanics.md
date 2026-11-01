# Panel, iteration 15: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built, and what the order record (filled, censored) and the live book (uncensored) can
still say about V and about the operator's valuation. The two items that block the target are price (0.322 against
0.80) and outcome (0.197 / 0.027 against 0.5). Both are gated on V. So every proposal below either changes what we
think V is (how much of the quoted level is really private), reads the operator's valuation from a record nobody has
used, or names the one input the price item still needs.

Written 2026-11-01, about 13:40-14:45 UTC, inside the sealed block 11-01 12-18. I read no record of that block.

## What I read and what I ran

I read:

- BRIEF.md: the premise, the hidden-dimensions section, the catalog, the accuracy targets and the wall;
- NOTES.md: iteration 15 in full (explanations, pre-registration, findings 1-25, ledger, unexplained, plan) and earlier
  sections by search (taker-regime clock in iteration 2, ladder_decode, X69, skew, T/CT side);
- state.json: the catalog A1-X218 and E1-E7 with their evidence (full text for X43, X57, X63, X75, X79, X96, X124,
  X133-X138, X144, X150-X155, X158, X159, X163, X165, X168, X174, X177, X181, X197, X198, X212), the components and
  target metrics;
- panels/iter14_mechanics.md in full, the headings of the iteration 12-14 panels, and the iteration-2 assumptions
  panel's pre-sign check;
- results: sameprice_sync*.json.

`tools/sealed.py tommy-cs2-maker`: no released lots; the future is examined up to 10-31 00:00; development blocks
after H are 10-31 00-06, 10-31 12-18 and 11-01 06-12; the current block 11-01 12-18 is sealed.

Every record I used is development data, already cached by the investigation:

- `orders.parquet`, `orders_inv.parquet`, `orders_ctx.parquet`, `calldata_all.parquet` (16-22 Oct);
- `calldata_taker/` and `taker_regime_txs_1001_1015.parquet` (the wallet's taker-regime transactions, 10-01..10-15);
- `iter12/slot_vrel_rows.parquet` and `own_bursts_dev.parquet` (BUILD-live, 10-31 14:50-18:00);
- bo3 match and round responses already in the shared HTTP cache (read through `shared_client` with `max_age=None`, no
  new request), and the per-market tapes clipped to H.

I opened nothing in `.cache/live/sealed/`, wrote nothing outside this file and my scratchpad, and started no
recorder. Scripts and outputs are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m15\`
(`clamp_presign.py` with `clamp_presign.json`; `ct_drift.py` with `ct_drift_rows.parquet` and `ct_drift_steps.parquet`).
Each process ran under 300 MB and under 5 minutes, after `resources.py --wait-mem 600`.

## Critique: what the investigation is missing or getting wrong

### 1. The quote is clamped to the public book, so the "level" that every fit reads is not V

On BUILD-live (2,699 validated own adds, own top after the burst = V_after; J = others' best bid, ask = others' best
ask, both with own levels removed):

| Where the new top sits | Share of adds | Share of up-moves (n 2,171) |
| --- | --- | --- |
| At or above others' ask (would cross) | 3.0% | - |
| Exactly others' ask - 1c | 23.0% | 25.4% |
| Exactly J (join) | 34.0% | 36.7% |
| Strictly between J and ask - 1c | 23.8% | - |
| Below J | 26.9% | - |

So the bot almost never crosses (97% of adds at or below ask - 1c: a post-only constraint or its own guard), and 57%
of its tops sit exactly on one of two public anchors. The private value V* shows up as a free level only in about half
of the adds (between, below J). Three consequences:

- **Level fits are censored by the clamp, not only by fills.** X171 (MR12 HMM), X181 step 4 (side-aware table), X213
  (series identity), X197 (price-time bounds) and the Dota fits (X123, X167) all read the filled or added top as V. A
  top pinned at ask - 1c only says V* >= ask - 1c; a top at J may say V* >= J. Fitting those as exact values inflates
  the residual SD of any table and can by itself produce "no closer than the print" and "not one exact line" (X213:
  SD 1.34c, 56% within 1c).
- **Part of what is counted as V-changes are anchor moves.** When the top is pinned, its move is the book's move. The
  historical V-change label (E3-1, findings 16-18 and 23) cannot see the book, so it cannot tell pinned moves from
  free ones.
- **The set-unit question to the user must be posed precisely.** Under a loose "slot range" reading (an order counts
  if its price lies within [V-hat - 5c, V-hat + 1c]), J alone scores 0.792 on these adds and floor((J + ask - 1c) / 2)
  scores 0.807, a pass with a trivial anchor. X163's machine set unit, which places each of the n adds on a specific
  free slot, gives J 0.50. Only the machine form is an honest set unit; the question to the user should say so.

The clamp also bounds what any public anchor rule can reach. Choosing, with an oracle, whichever of J and ask - 1c is
nearer to the true top gives 0.703 within one tick on burst tops (J alone 0.589, J + 1c 0.529, ask - 1c 0.388). The
regime does not follow the trigger code of `own_bursts_dev` (ask - 1c in 24% of both triggered and untriggered adds),
so no simple public selector exists. This is a quantitative wall clause for the price item on the live book.

### 2. The taker regime kept a book of pre-signed conditional orders, and nobody has read it

X69 closed the taker-regime `sign_ms` as "not the decision time". It is not the fire time, but it is when the order and
its limit were decided. On the 11,692 FAK orders of 10-01..10-15:

- Sign-to-block lag: p5 3.2 s, p25 7.8 s, median 24.9 s, p75 92 s, p95 268 s.
- **Same-moment order sets.** 352 pairs of its orders were signed within 50 ms of each other; 95% in the same market;
  46% fired more than 5 s apart (median 3 s, p75 44 s, maximum 600 s).
- Different-token pairs in one market split into two kinds:
  - **Same direction on both books** (BUY one token and SELL the other; 177 pairs; limits sum to about 1): one
    position split over the two books, usually fired together.
  - **Opposite directions** (BUY / BUY 31, SELL / SELL 64). The BUY / BUY limits sum to 1.03-1.20 (median 1.06), and
    81% fired more than 5 s apart. Firing both at once would lock a 6c loss, so these are conditional orders: one per
    outcome of the next event, with the bracket [1 - L_B, L_A] around the bot's current value (median width 6c).
- **Re-arm clock.** The next order in a market is signed a median 1.9 s before the previous order's block, and 19.5%
  of them 0-1 s after the newest counterparty maker order of that previous fill was signed (a sharp peak, 4.0% in
  1-2 s). The bot re-armed at the moment it fired.

This is the only record in the study where the operator's value appears as a two-sided bracket, at known times, rather
than as a censored and clamped top. It belongs to an earlier version (C4: other universe, slower input, other client),
so it cannot carry the exam, but it can show what the operator's valuation is a function of (proposal P3).

### 3. No round-timer term in V (negative check, so nobody redoes it)

B3 asks for the quote "as a function of time left". The CS2 analogue is the round timer: with no plant, the CT side's
win probability rises as the clock runs; after a plant, the T side's does. On the print-anchored clock of
`decided_early.py` (340 rounds with bo3 sides, 68 maps; mid window [a + 10, z - 10] s), with map-clustered SEs:

| Change in the mid window | Round winner | Previous round's winner | Team A on CT |
| --- | --- | --- | --- |
| Its value | +2.15c (p < 0.001) | +2.51c (p < 0.001) | -0.55c (p 0.30) |
| Clean print | +0.78c (p 0.14) | +2.27c (p 0.001) | -0.61c (p 0.22) |

No-plant rounds give -0.88c (p 0.70), plant rounds -0.21c (p 0.80). Of 743 value steps inside the mid windows, 44% move
toward CT when T wins the round and 55% when CT wins it. In the late half of the window the small steps lean a little
more toward the eventual winner (CT-won rounds 0.56 against 0.49 early; T-won rounds 0.44 in both halves), not toward
CT. So there is no CT drift:
V carries no deterministic round-clock term on the filled record. That fits finding 18 (moves at a few moments per
round, not continuous) and removes the "alive count + timer" form of K. The previous winner's coefficient exceeds the
current winner's even 10 s after the anchored end (finding 23 again).

### 4. Smaller points

- **The long-side taper is partly a price skew.** On 21,919 filled maker orders (16-22 Oct, price 0.1-0.9), the offset
  from the last print has a median of -1c while the wallet is short or flat in that token, -2c at net +200..+600 and
  -2.5c above +600 (n 41). The means are flatter (-1.6 to -2.4c) and fills are censored, so this is weak; but no price
  rule uses own inventory, and own state is admissible if reported both ways.
- **Taker sizes are not inventory.** Only 0.2% of the non-cap taker sizes equal the wallet's net position (1,270
  orders). 93% are integers, 23% are the 1,000 / 2,000 caps, and the non-integer 7% look like a USD amount divided by
  the limit (market orders by amount).
- **The outcome wall holds at any public latency.** X155 already shows it, but it is worth stating plainly: even an
  oracle copy of its own maker orders at 100 ms with the delayed taker leg scores 0.448 / 0.375 on VALIDATE. A
  live-book rule that reacts to the public cancel wave (+17-124 ms) cannot reach 0.5 either. Reading item 5 without
  the 2-s convention would not change the verdict.

### 5. Where this leaves the mechanics side

The machine is decoded: ladder, cooldown, loop, merge, cap, band, sizes, and now the clamp. The price item fails
because about half of the levels carry the private V*, and the other half are pinned to anchors whose choice depends
on V*. The outcome item fails because the taker leg is a race lost at 100 ms. No mechanics-only route reaches 0.80 or
0.5 on public data. The proposals therefore aim to (a) find out whether V* is a function of a public score once clamp
and fill censoring are removed, which says exactly which input the price item needs, and (b) read the operator's
valuation where it is not censored.

## Proposals, ranked by the chance they close the gap

### P1. Is V* a public-score table once the clamp and fill censoring are removed? (strong form of X171 / X181 step 4 / X212 / X213)

- **Hypothesis.** Between feed messages, the operator's free value V* is a deterministic function of the public match
  state (map score, round score, sides, a pre-game strength q), for example an MR12 / MR3 table plus a fixed offset.
  The earlier fits rejected this only because they fitted clamped and fill-censored tops as exact values.
- **Why it fits.**
  - Critique 1: 57% of live tops sit on J or ask - 1c, and fills select stale lower slots.
  - Finding 23: its moves are mostly round results; critique 3: no timer term. Both are what a round-score table
    predicts.
  - X181 step 4's residual SD (3.96c against the print's 2.82c) could come from pinning and slot censoring rather than
    from the table (not yet measured: that is step 3 below).
- **Test.**
  1. **Free tops only.** On BUILD-live (shin-isg map 1 with about 457 value moments, gls1-pcy map 2, the match books),
     label each top as pinned (= ask - 1c, = J, or = K - own complement top) or free. On the historical record,
     approximate this with the revealed others' bid and ask of the latest wallet-free transactions and with the
     sibling union top (X176), and keep only bursts whose top lies at least 2c below the revealed ask and 1c above the
     revealed bid.
  2. **Diagnostic clock (not a rule).** Candidate round ends are ms-synchronous co-repricings of the map and match
     books in one team direction with |delta map| >= 2c on free tops. Align them to bo3's winner sequence and durations
     with the pause-aware DP, against reversed and permuted sequences. Using its own moves for the clock is acceptable
     here because the test is about levels, and alignment uses only timing and direction.
  3. **Level fit.** At free tops that are quiet (at least 20 s after an aligned end, no visible group-P take within
     10 s), fit V* = table(score; q, sides) + a per-token offset, with pinned tops entered as censored observations
     (Tobit), on BUILD maps; score on VALIDATE maps.
- **Data.** All cached: `slot_vrel_rows`, `own_bursts_dev`, `tommy_cs2_near` (10-31 12-18), bo3 rounds of the 10-31
  maps (fetched for X212) and of the 86-92 matched maps, `orders.parquet`, `calldata_all` / `calldata_pub`, the
  sibling calldata, tapes.
- **Signature if true.** Aligned ends snap at least twice as often as the reversed sequence. Free quiet tops lie
  within 1c of the fitted table in at least 70% of cases, with residual SD at most 1.2c against the print's 2.8-4c.
  The Tobit q matches the pre-game implied map strength within 3c. Then the price item needs only the public round
  score at signing time plus the clamp, and the missing dimension is narrowed to "round score in real time" (stream
  HUD, X4 / X22 / X162; or the vendor feed, X206), with nothing else private.
- **Signature if false.** Even unclamped quiet tops scatter by 2c or more around every table: V* is not a score table.
  The feed then delivers a price (hypothesis V, an odds product) or a richer state, and the vendor route (X206) is the
  only one left.
- **Chance.** Low to moderate for the verdict; closing the item still needs a real-time score source on the exam
  blocks afterwards.

### P2. A clamp-aware price rule with an own-inventory skew, frozen for the forward blocks (strong form of X43 / X63 / X75 / X163)

- **Hypothesis.** The quote is top = min(max(V* - s(net), J-join rule), ask - 1c), placed into the five-slot machine.
  The regime choice (pin ask - 1c, join J, free) depends on V* only through whether V* lies above ask - 1c, at or
  above J, or below it. s(net) is about 1c when net > +200 in that token.
- **Why it fits.** Critique 1 (97% never cross, 23% / 34% at the two anchors, oracle anchor choice 0.703 on tops)
  and critique 4 (-1c to -2c median offset by net). Neither the clamp nor the skew is in `evaluate()`'s live price
  rule.
- **Test.**
  1. On BUILD-live, fit a four-way regime classifier on public live-book state only: spread, J and ask freshness, the
     side of the last cancel wave on the event's books, a visible group-P take in the last 2 s and its direction, and
     the pair state. Report the accuracy against the share of the largest class.
  2. Put "selected anchor, else J - k" through the X163 machine with the cooldown and held slots. Score per order and
     on the machine set unit, with and without s(net), against J alone (0.412 per order, 0.50 set).
  3. Freeze it as the live price rule for the future-block exam (books recorded), next to the order-unit tape rule.
- **Data.** `slot_vrel_rows`, `own_bursts_dev`, `tommy_cs2_near` and `level_events_dev` (10-31 12-18),
  `orders_inv` for net.
- **Signature if true.** Regime accuracy at least 0.75, and the machine set unit rises by at least 0.10 over J. The
  live price item then splits into a public part (anchored adds) and a private part (free adds) with measured shares.
- **Signature if false.** No public feature predicts the regime beyond its base rate. Then the anchor choice is itself
  V*, and the live price item is bounded at about 0.70 on tops with an oracle selector.
- **Chance.** Low (the oracle ceiling is about 0.70 on tops), but cheap. It also makes the forward rule's price
  component honest about what it can and cannot see.

### P3. Read the operator's valuation from the taker regime's conditional order sets (new; strong form of X16 / X51 / X69; version decode C4)

- **Hypothesis.** In the taker regime the client kept pre-signed conditional FAK orders, one for each outcome of the
  next event, and re-armed them after each fill. The opposite-direction pairs signed in the same 50 ms bracket the
  operator's value at that moment: [1 - L_B, L_A], median width 6c. Their sign times are the operator's state updates.
- **Why it fits.** Critique 2: 352 same-moment pairs; BUY / BUY limits summing to 1.03-1.20 and fired apart; the
  re-arm peak 0-1 s after the previous fill's newest maker order. These were GRID tier-1/2 events, with liquid prints
  (a much better print-anchored round clock than tier 3) and complete bo3 round data.
- **Test.**
  1. Decode the wallet's taker-regime transactions back to 06-16 (only 10-01..10-15 are decoded), with real block
     times for a sample, and group its orders into sign moments (50 ms).
  2. Fire-trigger check: is each fire preceded by a public event (a >= 2c clean-print jump or a GRID round end on the
     print clock within 3 s), or only by a newly posted maker order at <= L? This separates conditional event orders
     from standing snipe limits.
  3. Bracket fit: midpoint and width against the round table at the bo3 score at the sign moment (and q from the
     pre-game price). Under R the width is the table's round swing (5-12c by score); under K it is a kill swing
     (smaller, and set by alive counts).
  4. Sign-moment count per round against bo3 rounds and kills (Poisson, map clustered), and timing against the print
     clock's round ends.
  5. Transfer: does the same table, shifted by one offset, fit the maker regime's free quiet tops of P1?
- **Data.** Polygon calldata for the wallet's taker-regime transactions (activity already fetched: 72,639 rows
  06-16..10-16), block timestamps, tapes of those GRID markets before 10-16, and bo3 rounds (tier-1/2 coverage is
  complete).
- **Signature if true.** Bracket midpoints within 1c of a score table; widths equal the table's round swing at that
  score; about one sign moment per round, within a few seconds of the print-anchored end. The operator's valuation is
  a round-score table (R), decoded for that version, and P1 tests it on the current version.
- **Signature if false.** Brackets track the last print plus a constant (standing snipes, no model), or widths match
  kill swings with several moments per round (K-type state in the operator's model).
- **Chance.** Low for the exam (earlier version, slower input), but it is the operator's value without clamp or fill
  censoring, and it costs only calldata of a period that is all development data.

### P4. Clock-free R versus K from per-map counts of round-sized co-repricings (strong form of finding 18 / X173 / X198)

- **Hypothesis.** If V moves at round results, the number of large ms-synchronous map / match co-repricings per map
  scales with the map's rounds. If it moves at kills or plants, the count of smaller ones scales with kills or plants.
  Per-map totals need no clock at all, unlike finding 18's per-round counts on the print clock.
- **Why it fits.** Every R / K test so far rests on a clock that snaps only 1.30-1.45 times as often as a reversed
  sequence. bo3 gives per-map totals of rounds, kills, plants and end reasons without timing. Rounds and kills per map
  are correlated, but kills per round (5-10), plants per round (0.3-0.6) and overtime vary between maps.
- **Test.** On the 86-92 bo3-matched maps of 16-22 Oct, take co-repricing moments: map and match books (and other map
  books) re-priced within 5 ms by the wallet or its 5-share siblings' union top, in one team direction. Split them by
  size: |delta map| at least half the table's round swing at the score implied by the map's running print, or
  smaller. Fit a negative binomial of each class's count per map on rounds, total kills and plants, with log(own
  filled orders) and log(public in-play prints) as offsets or controls. Use the free-top filter of P1 where it
  applies.
- **Data.** Cached: `orders.parquet`, the sibling calldata, tapes, bo3 rounds.
- **Signature if R.** Large co-repricings: coefficient on rounds about 1 per round, no kills effect; small ones explained
  by fills (mechanics).
- **Signature if K.** A positive kills or plants coefficient at fixed rounds for one of the two classes.
- **Chance.** Low; it is a cheap cross-check on P1 and P3 that does not depend on the clock.

## Overlap with the ledger, the catalog and the other panels

- **P1.** Related: X171, X181 step 4, X212, X213, X197, X163. New: the clamp-censoring correction (critique 1), the
  free-top filter, a Tobit level fit, and the wallet's own co-repricings used as a diagnostic clock for a levels-only
  test.
- **P2.** Related: X43, X63, X75, X153, X163, X177, X218 (skew in the replay only). New: the measured never-cross clamp
  and the two-anchor pinning, a regime classifier, and the own-inventory price skew in the price rule.
- **P3.** Related: X16, X51, X69 (closed as "not the decision time"), the iteration-2 assumptions panel's pre-sign check,
  C4. New: same-moment conditional pairs, the bracket reading, the re-arm clock and the GRID-era valuation fit.
- **P4.** Related: finding 18 (`dark_per_round.json`), X173, X198, X213. New: per-map totals (no clock) and size-classed
  co-repricings.
- **Negative checks, so nobody redoes them.**
  - No CT-side round-timer drift in V (critique 3).
  - Taker sizes do not equal the net position (critique 4).
  - The loose slot-range set unit passes with trivial anchors (critique 1), so it must not be the unit put to the user.
  - The outcome item fails even at 100 ms latency with oracle maker orders (critique 4, from X155).
