# Panel, iteration 11: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built (the ladder under the wallet's value, the operator's matching record, the
totals books of the same map), and which mechanical claims in the wall account survive a direct test.

Written 2026-11-01, about 06:40-08:10 UTC, inside the development block 11-01 06-12.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 11 in full, iterations 1, 5, 6, 9 and 10 by section;
- state.json: the catalog (A1-X157), the components, the target metrics;
- FINAL_RULE.md, by section;
- panels/iter10_mechanics.md in full, and the proposal headings of every earlier mechanics panel;
- panels/iter11_assumptions.md and panels/iter11_information.md, to avoid duplicating them (see "Overlap").

`tools/sealed.py tommy-cs2-maker`: no released lots, future examined up to 10-31 00:00. The current block (11-01 06-12)
is development.

Every record I read is development data:

- on-chain tables of 16-22 Oct (`calldata_all`, `orders`, `chain_fills_*`, `markets_dev.json`, the tapes);
- BUILD-live tables and recordings of the 10-31 12-18 block (`linked_adds_dev`, `level_events_dev`,
  `calldata_dev`, `dev_markets`), with `tommy_cs2_near` 14:50-18:00 and `tommy_cs2_rounds` 15:20-18:00 read through
  `iter_live`.

I did not read the 11-01 06-12 recordings (the reverse engineer's VALIDATE-live). I opened nothing in
`.cache/live/sealed/` and called no endpoint. I wrote nothing outside this file.

My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m11\`:

| Script | Built from | What it does |
| --- | --- | --- |
| `slot_vrel.py` | `code/iter11/slot_ceiling.py` | V-relative ladder state and the target-ladder machine |
| `beyond_survival.py` | `code/iter11/remainder_survival.py` | stale depth beyond its limit, to +8 s |
| `size_touch.py` | `code/iter11/fresh_touch_v2.py` | size-filtered touch |
| `queue_pos.py` | new | engine queue order |
| `series_check.py` | new | map-3 identity; aborted, see check E |

Each process ran in under 15 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. "Even with V known, slot choice caps a per-order rule at 0.71-0.75" is a feature omission, not a property of the bot

X150 (`slot_ceiling.py`) defines the target as the slot relative to V_after (its own top after the burst). But every
ladder feature it gives the classifier is relative to its OLD top: `held_m1..m5`, `gap_J_own`, `own_top`. The
classifier never learns which slots under V are already held, or by how much the top moved. So it measures "V as a
reference", not "V known".

The same rows, with two additions (`slot_vrel.py`, BUILD-live, 2,698 validated adds):

- **dV** = V_after - old top;
- **hv0..hv6**: own level held at V - k before the add.

| Rule, V = own top after the burst | Adds within one tick | Exact |
| --- | --- | --- |
| "price = V" (X150) | 0.625 | |
| X150 LightGBM, leave-one-event-out | 0.750 | |
| Same LightGBM plus dV and hv0..hv6 | **0.789** | |
| Machine: every add at the highest free V-relative slot | 0.70 | 0.50 |
| Machine: a burst of n adds takes the n highest free slots, top-first; per order, the burst's median slot (n known, no within-burst rank) | 0.75-0.76 | |
| Machine, burst prices matched to the n free slots by rank (set unit) | **0.861** | 0.765 |

The set-unit machine by burst size and by V move:

| Class | n adds | Within one tick |
| --- | --- | --- |
| Single adds (no ranking needed) | 966 | 0.890 |
| Bursts of 3 | 249 | 0.948 |
| Bursts of 5 | 461 | 0.866 |
| V up (new top) | 988 | 0.929 |
| Fresh ladder (no own level on the token before) | 1,182 | 0.860 |
| V down | 238 | 0.899 |
| V unchanged | 290 | **0.603** (the residual) |

What these numbers mean:

- **The ladder under V is close to mechanical.** It fills the highest free whole-cent slots under V, top-first. The
  per-order ceiling with V known is about 0.79, not 0.71-0.75, and about 0.86 once a burst's exchangeable orders are
  matched to its slot set.
- **The within-burst order is not identified by any field.** The orders of a burst are signed in the same
  millisecond, and the book feed lists them ascending as often as descending (35% / 35%). So a per-order score must
  either guess the order (0.75-0.79) or match by rank (0.86). The burst-identity cap alone (identical features within
  a burst) is 0.916, so it does not explain the old 0.75.
- **V must be exact to the cent.** Shifting V by one cent drops the set unit to 0.71 / 0.76 (V - 1c / V + 1c);
  two cents collapses it (0.24 / 0.03). "Within one tick" on V is not enough, because the machine's exact rate
  (0.765) is the error budget.
- **Public V proxies gain almost nothing through the machine.** On the same rows:

  | Proxy for V | Set unit | Highest free slot |
  | --- | --- | --- |
  | Others' best J | 0.483 | 0.425 |
  | J + 1c | 0.438 | 0.373 |
  | Own top before | 0.31-0.42 | |

  The touch alone scores 0.419.
- **Most adds are V decisions.** 80% of adds come at a V change: 988 up, plus 1,182 that re-enter with no own level on
  the token (44% of all adds). 77.5% belong to bursts that set V_after themselves.

So the price item is "one private number per burst, to the cent, plus a mechanical ladder". It is not "a ladder no
rule can score". The wall account (finding 3, the X150 evidence, the strategy statement and FINAL_RULE.md) should
quote 0.79 per order / 0.86 per set with V known. It should also state the residual class: V unchanged, 0.60. With
the information panel's 504-ms loop, that class may be loop-tick refills (proposal P1, step 3).

This sharpens the assumptions panel's critique 1. That panel argued from the fill-time unit; at signing time the
claimed cap does not hold either.

Caveats:

- 77.5% of the adds sit in bursts that set V_after, so "V known" includes the top decision itself. This is the
  definition of the oracle.
- The set unit uses price ranks inside the burst.
- One block, 7 events: BUILD-live only.

### 2. The outcome wall is not a replay-convention artefact: a first measurement of the assumptions panel's P3

The T_lo / T_hi split hinges on whether the slow makers' stale orders survive after the wallet's match.

`beyond_survival.py` (BUILD-live, 39 in-play FAK BUYs, 35 with depth there) measures the stale band JUST ABOVE the
wallet's limit L, (L, L + 3c]. The wallet does not consume that band, so its survival is the makers' own counterfactual
behaviour. Times are from its match m = sign + 1,040 ms, own levels removed.

| Time after m | +0.1 s | +0.3 s | +0.5 s | +1 s | +2 s | +3 s | +8 s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Median depth / depth at m - 50 ms | 0.92 | 0.61 | 0.57 | 0.42 | 0.11 | 0.08 | 0.01 |
| Share of takes keeping >= 50% | 0.71 | 0.57 | 0.54 | 0.43 | 0.40 | 0.34 | 0.31 |
| Median depth / depth at signing | 0.21 | 0.12 | 0.11 | 0.05 | 0.012 | 0.013 | 0.0 |

At <= L, the median residual over its fill is 0 at every time from m to m + 8 s. No one refills its band.

So the T_hi assumption (no maker cancels in (m, m + L]) is far from the data at L = 2 s. In the median take, the
stale levels near its limit are gone (cancelled or taken) about 1-2 s after its match: the T_lo world, in which an
oracle copy at 2 s fails.

Two cautions:

- The distribution is bimodal: 40% of takes keep half of the band at +2 s. A per-market T_emp, not a median, decides
  the wall.
- Decreases are not yet split into cancels and trades.

The assumptions panel's P3 (wallet-absent bursts, T_emp in the X155 grid) is the right completion. This check
predicts its "if false" branch.

### 3. The operator's matching record holds a book-free queue, and nobody used it

In every V2 `matchOrders` the operator lists maker orders in matching order (`queue_pos.py`, `calldata_all`, 16-22
Oct):

- In 14,829 transactions with at least 2 makers, the effective price for the taker is monotone in `idx` in 100%.
- Within a price level, `sign_ms` increases with `idx` in 90.3% of 20,318 levels. So the list is price-time priority,
  and arrival order tracks signing order.

For the wallet's 34,968 maker fill rows:

| Queue position at its own price level | Share of fill rows |
| --- | --- |
| First in queue (nobody ahead) | 76.8% |
| Alone at the level | 54.6% |
| Behind others | 23.2% |

- Orders queued behind it were signed a median 11 s later (p10 +141 ms).
- 3,001 of them (10.7%) were signed 0-200 ms after it. The most frequent are 0xe8e1b119 (817), 0xaeb90af4 (345),
  0x51dbdd2b (294), 0x52661b8e (172), 0x68915897 (119) and 0x893575c7 (102).
- Orders ahead of it were signed a median 2.2 s earlier.

These numbers are fill-selected (the head of a queue fills first). Even so, this is the only historical, book-free and
examiner-computable record of where its price sat against the others: it created the level far more often than it
joined one. The record also carries the follower set and relative arrival latency (proposal P3).

### 4. Smaller points

- **The historical "rebuilt touch" is a look-ahead.** The rebuilt touch of B3 / X33 (0.396) counts other makers' orders
  "signed before s and filled after s" (`code/iter2/price_touch.py`). That uses future fills, so it is not examinable
  on h1 / h2. The catalog should mark it as a look-ahead, like the fill-selected own anchors corrected in iteration 11.
  A point-in-time version from partial fills has never been built (proposal P3).
- **The examinable price per title stays low without V.** On future blocks, the machine with any public V proxy stays
  at 0.42-0.48 (critique 1). The forward price score therefore depends entirely on the V search: X144, X118 and
  assumptions P1 for Dota.

## Checks (so nobody redoes them)

**A. A size-filtered touch does not help** (`size_touch.py`, BUILD-live raw book). The anchor is the poly-maker style
"best price with size >= S", optionally +1c when the size there is >= 1.5 S, capped at ask - 1c, for S from 0 to 1,001
shares.

| Population | n | Touch | Best size filter |
| --- | --- | --- | --- |
| Adds, full sample | 1,973 | 0.452 | 0.453 (J_S at S <= 11 equals the touch; larger S is worse) |
| Fills, second half | 87 | 0.402 | 0.379 (fitted on the first half; gain CI [-0.094, +0.088]) |

The apparent +0.07 on adds in the second half comes from the touch's offset, which was fitted on the first half and
missed there.

**B. Ask - 1c is not its top rule.** It scores 0.277 on adds against the touch's 0.452. It matches the touch at a 1c
spread and falls to 0.05-0.16 at spreads of 4c or more.

- 19.2% of its filled orders sit at or above the others' best ask measured 100 ms before signing. It posts through the
  stale ask, its value running ahead of the book.

**C. No penny war.** The step-ups follow a rising market, not queue competition:

| Add class | Others added at its old top in the previous 1 s |
| --- | --- |
| +1c new top | 45.8% (n 358) |
| +2c or more new top | 41.7% |
| Same-V adds | 25.2% |
| Down-V adds | 15.1% |

There is no +1c specificity.

**D. Burst structure of validated adds.**

- 1,610 bursts: 963 singles, 429 pairs, 83 triples, 43 of four, 91 of five.
- 64.4% of adds are in multi-add bursts.
- Multi-add bursts are contiguous at 1c in 66.5%.

**E. No map-3 identity test exists.** Polymarket lists only Match, Map 1 and Map 2 winner markets for its BO3s: 67 of 80
events. One BO5 has a map 3. A "match = map-3" coherence test is therefore impossible. The series coherence must use
map 2 at 1-0 / 0-1.

## Proposals, ranked by the chance they close the gap

### P1. Freeze the value-plus-machine price decode, close its residual class, and pre-register the burst unit (strong form of X150; corrects finding 3)

- **Hypothesis.** The maker price is one private number per burst, V to the cent, plus a deterministic ladder:
  - fill the n highest free whole-cent slots under V, top-first;
  - skip slots in the 1.5-s (three-tick) cooldown;
  - refill slots vacated by own fills on the next loop tick.

  With V known, this scores at least 0.85 per order on the set unit, and about 0.80 per order without the
  within-burst rank, once the V-unchanged class is fixed. The price item is then gated only by V. The 0.71-0.75
  "structural cap" leaves the wall account.
- **Why it fits.**
  - Critique 1: 0.789 per order (classifier) and 0.861 per set from V-relative state alone.
  - The only weak class is V unchanged (290 adds, 0.603). Those are refills: the information panel's 504-ms loop, and
    X79's re-post at the cancelled price in 50.8%.
- **Test** (BUILD-live fit; score on every VALIDATE-live block without refitting).
  1. Port `slot_vrel.py`'s machine into code with frozen constants: slot depth 0..-4 (CS2; measure the Dota depth
     separately), top-first assignment, band [0.05, 0.95], pair cap 0.99.
  2. Add per-slot state: the time since its own cancel at that price (unavailable < 1,512 ms), and the time since its
     own fill at that price. Detect own fills from `x` trade records whose decrease matches its size at a level it
     held, confirmed by `calldata_dev`. Add the loop-tick phase from the information panel's 504-ms clock.
  3. Score three units:
     - per order without rank;
     - per order with rank inside the burst by price (the set unit);
     - per burst: the predicted set equals the realized set within one tick.

     Report each with V = V_after (oracle), V = the touch, V = own top before, and V = any candidate from X144 / X118
     / assumptions P1. Split by class (up, fresh, down, same) and by title (CS2 100-share, Dota 10-share).
  4. Report the V-error tolerance curve (V shifted by -2..+2c).
  5. Ask the user before any exam whether the examiner may score the set unit. The orders of a burst share every field
     except price and are signed in the same millisecond, so their order inside the burst is not a decision. This
     resolves an unidentifiable permutation; it does not narrow scope, because every order is scored.
- **Data.**
  - On disk: `linked_adds_dev`, `level_events_dev`, `calldata_dev`, `tommy_cs2_near` (10-31 14:50-18:00).
  - To come: the VALIDATE-live blocks, and the information panel's loop-phase estimate.
- **Signature if true.**
  - With V known: set unit >= 0.85 and per order >= 0.80 on VALIDATE-live; the V-unchanged class >= 0.75.
  - The wall account then reads: "the price item fails only because V is private; given V to the cent the ladder
    passes."
  - Any V source found later converts directly into a price pass, provided it hits V exactly on about 90% of bursts.
- **Signature if false.**
  - With V known, the per-order score stays below 0.80 after the cooldown and fill state are added, and the set unit
    below 0.85.
  - Then a real slot policy exists beyond V (for example inventory-dependent depth), and the item needs two decodes.
    Report which state the classifier uses.

### P2. A point-in-time round-score clock for non-GRID CS2 from the totals and handicap books of the same map (new public input; complements assumptions P5 and information P3)

- **Hypothesis.** Each round end re-prices the map's total-rounds O/U lines and round handicaps by a computable amount.
  The O/U line nearest the projected total moves most. A line "locks" at 0.99 once the total passes it, and a handicap
  locks once the margin passes it.

  The makers of those books react to the same feed or to the stream. Their synchronous quote jumps are therefore a
  public, millisecond round clock. With the map market's jump direction they give the round winner, and the locks give
  absolute checkpoints of total and margin.

  If the wallet's V between in-round events is a round-state valuation (assumptions P5), this clock makes V_markov a
  point-in-time public input on future blocks. That is the first public game-state input for its events.
- **Why it fits.**
  - X2 / X125 closed the round model only for lack of a public round clock: the socket's round part is constant
    000-000 for non-GRID games, and the bo3 timing alignment did not beat the control.
  - The wallet's events list "Map k Total Rounds O/U 15.5-36.5" and round handicaps (X47: 665 such markets in 39
    VALIDATE events). The wallet never trades them, and their tapes are too sparse for a historical clock (529 taker txs
    in 665 markets).
  - Their books are alive. In `tommy_cs2_rounds`, 10-31 15:20-18:00 (24 minutes of records), 43 assets show 5,799 price
    changes. Five of them carry 846-2,257 changes; across the six assets with more than five changes, the median
    gap between changes is 27-60 ms (bursts).
  - The recorder covers every block and files units by the unit rule, so the examiner can replay it.
- **Test** (development blocks only; fit on the first block with traded events, score on the later ones).
  1. **Round-end detector.** Per map: at least 2 of its totals / handicap books change best bid or ask by >= 3c within
     1 s, with no wallet involvement. Report a refractory period and the count per map.
  2. **Validation against bo3** (`/games/<id>/rounds` after the match, development maps only):
     - detected count against bo3 total rounds;
     - the detected winner sequence (the sign of the map market's move within 2 s) against bo3's winners (NW identity
       against 200 permutations);
     - lock checkpoints against bo3's cumulative score.
  3. **V_markov(t).** P(map win | score, side) from MR12 with overtime, with the per-team round-win probability
     inverted from the map market's last print before the map. Propagate it to the match market with the BO3 series
     formula at 1-0 / 0-1 (check E: no map-3 market).
  4. **Scores on the wallet's levels.** Its burst tops in the buy phase (the first 20 s after a detected round end with
     no message) and overall, against the touch. Also V_markov + P1's machine per order.
  5. **Timing.** The share of its V-up bursts within ±3 s of a detected round end, against shifted ends.
- **Data.**
  - `tommy_cs2_rounds` (11-01 06-12 onward, development units), `tommy_cs2_near`, the `sports` feed (map switches);
  - bo3.gg finished rounds (development matches);
  - the listing projection for the totals / handicap condition ids.
  - Not available for h1 / h2: they have no books, and the historical tapes are too sparse.
- **Signature if true.**
  - The count is within one round on >= 80% of maps, and the winner sequence beats >= 99% of the permutations.
  - V_markov is within one tick of its buy-phase tops on >= 0.6, against the touch's 0.42-0.45.
  - The private part of V then shrinks to in-round deviations, with a public, examinable score input for the
    future-block exams.
- **Signature if false.**
  - The clock works but V_markov is no better than the touch: V is not a score table (this matches assumptions P5's
    false branch, now on uncensored levels).
  - Or the totals books do not move at round ends: those makers re-quote on in-round events only, and the clock does
    not exist.

### P3. The operator's queue as a book-free historical record: a point-in-time partial-fill book for h1 / h2, the follower set, and relative arrival latency (new data object; strong form of B2 / B3 / X57)

- **Hypothesis.** The price-time ordered `makerOrders` lists and the per-order cumulative fills give three things for
  the exam lots without books:
  - **(a) A point-in-time lower bound of the resting book.** Count other makers' orders with at least one fill in a
    block at or before t - 2 s whose cumulative fill is below their size. Drop an order as soon as a later sweep before
    t trades through its price without filling it (it was cancelled). This beats the stale last print on h1 / h2, where
    the touch is not otherwise examinable.
  - **(b) The followers that join the wallet's level within 0-200 ms.** These are pegging bots that copy its price.
    Removing them shows how much of "its level leads the public mid" is pegging (the iteration-9 caveat).
  - **(c) Per-maker arrival latency.** Queue inversions (an order signed earlier but queued behind the wallet at the
    same price) bound each maker's sign-to-engine delay against the wallet's. This places P4e's -50-ms sign lead on the
    server's clock without books.
- **Why it fits.**
  - Critique 3: 100% price-monotone lists, 90% time priority, the wallet first at its level in 77% of fill rows, and 10.7%
    of the queue behind it joining within 200 ms. The followers are dominated by 0xe8e1b119, which sits in 8,040 of its
    transactions.
  - Critique 4: the only historical book so far (0.396) was a look-ahead.
- **Test.**
  1. Build the partial-fill book (a) on BUILD and VALIDATE, with orders older than 60 s since their last fill dropped
     (age cutoff fitted on BUILD). Score its best bid (and the complement-implied ask cap) within one tick of the
     wallet's maker orders, against the last print (0.309 / 0.305), with coverage and an event bootstrap. Freeze it in
     `evaluate()` only if VALIDATE gains >= +0.05.
  2. Followers (b):
     - for each maker, the excess of same-price joins behind the wallet in (0, 200] ms over joins in (1, 5] s;
     - on BUILD-live and VALIDATE-live, recompute the add-level lead (finding 14 / X135: Spearman of its offset with
       the others'-mid move at 2 / 10 / 30 s) with the followers' adds removed from the others' book.
  3. Latency (c): per maker, the distribution of `sign_ms(X) - sign_ms(W)` over inversions (X queued behind the wallet
     W at the same price in one transaction), for P4e, 0x2005d16a, 0xed446954, 0x51dbdd2b and the trio.
- **Data.** `calldata_all`, `calldata_pub` (every matched order with `sign_ms`, size, fill and block); block times
  interpolated as in `price_touch.py`; the BUILD-live and VALIDATE-live tables for step 2.
- **Signature if true.**
  - (a) scores >= 0.36 on VALIDATE: the best examinable h1 / h2 anchor, frozen with a declared point-in-time
    construction.
  - (b) the 2-s lead falls by more than half without followers while the 30-s lead stays, which quantifies pegging.
  - (c) the wallet is rarely behind earlier-signed orders while P4e is often behind later ones. Its sign lag then
    overstates its arrival lag, and the wall account's millisecond statements should use the engine order.
- **Signature if false.** (a) is no better than the last print (partial fills too sparse), the lead is unchanged
  without followers, and inversions are symmetric. The historical price bound then stays the last print, measured
  against the only other historical book.

### P4. Lineage of the deposit wallet: its creation, first funding and a possible predecessor wallet (strong form of C1 / C4 / X74; on-chain forensics)

- **Hypothesis.** The deposit wallet (signature type 3, DepositWallet v1, owner 0x8af810f0) was opened for the 06-16
  start; deposit wallets are recent. If its first funding came from an older Polymarket proxy or Safe wallet of the
  same operator, that wallet's history may hold an earlier, simpler build of the bot. That build might be a maker
  quoting off an external line, or the GRID taker's precursor, and could name V's source or its model class.
- **Why it fits.**
  - C4 covers only this address since its first trade.
  - X74's funding graph covers 10-12..H, USDC only, Polygon only.
  - X110 ties every order to one owner key, but that key's earliest history was never read.
  - The bot shows a mature, versioned design (event-wide size ramps, a 300-s merge loop with a 7.28-s per-merge law, a
    504-ms loop, a 1.5-s cooldown, a hard band). Such a design rarely starts on a fresh wallet.
- **Test.**
  1. Find the wallet's deployment block: the factory creation log, or a binary search with `eth_getCode` on an archive
     RPC.
  2. Pull the USDC.e and USDC `Transfer` logs to the wallet from deployment to 06-16 + 7 d, chunked to a few thousand
     blocks.
  3. For each source, read `eth_getCode` and `owner()`, then data-api activity (development periods only).
  4. Do the same for the owner EOA's first incoming transfers and its nonce.
  5. If a predecessor trades, run the fingerprint battery on it: whole-cent buy-only ladders, 100-share orders, the
     band, salt magnitude, merge cadence. Then decode its order calldata for any period before H.
- **Data.** Polygon RPC (publicnode batches of 40), data-api activity; all before H.
- **Signature if true.** A predecessor wallet with the same fingerprints. Its earlier version is decoded separately
  (C4); if it quoted an external line, the line is a V candidate for X144.
- **Signature if false.** The first funds come from an exchange or bridge and no Polymarket predecessor exists. C1 / C4
  then close at the lineage level, which is one more line for the wall account.

## Overlap with the ledger, the catalog and the other panels

- **P1.**
  - Existing: X150 / finding 3 (cap 0.71-0.75), X108 (own-state machine without V, 0.29), X100 (hole fill, 0.48), X79
    (1.5-s re-post) and iteration-10 mechanics P2.
  - New: V-relative state, the measured 0.79 / 0.86, the residual class, the V-error tolerance and the set-unit
    question.
  - It complements the assumptions panel's critique 1 (fill-time unit) and uses the information panel's 504-ms loop.
- **P2.**
  - Existing: X2 / X125 (no round clock), X47 (round markets as a lead-lag source for takers, historical half run, live
    half pending), iteration-3 assumptions P1 (round markets as the first public trace), assumptions P5 (clock-free HMM
    fit of V to a score table) and information P3 (a bo3 clock aligned to the tape, historical).
  - New: using the totals and handicap books as a millisecond, point-in-time score clock with lock checkpoints,
    examinable on future blocks.
- **P3.**
  - Existing: X57 / X44 (a price-time engine on the matched record, used for replays), B3 / X33 (the look-ahead
    rebuilt touch) and X27 (per-signer calibration through the delay).
  - New: the queue list as a label, the point-in-time partial-fill book, followers and latency from inversions.
- **P4.** Existing: C1 / C4 / X74 / X110. New: the history before the first trade and the funding sources at creation.
- **Not proposed, because covered elsewhere.**
  - The counterfactual remainder is assumptions P3; my check under critique 2 is its first measurement.
  - The taker as a threshold on its own V is assumptions P4.
  - Azuro on chain is information P4.
  - The 504-ms loop is information P1.
- **Negative checks A-E** close four candidate mechanisms and one test design: a size-filtered touch, an ask - 1c
  top rule, a penny war, a burst-identity explanation of the old cap, and the map-3 identity test.
