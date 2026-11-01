# Panel, iteration 4: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and kept. That covers the ladder and its sizes, the fill engine behind every
replay, sweeps through the book, the 1-s delay window, merges, and fingerprints of the client.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-4), state.json (catalog up to X52, components, target metrics),
FINAL_RULE.md (v3) and every earlier panel file (iterations 1-3, all three lenses).

I then ran small read-only checks on development data only:

- **History, 16-22 Oct (before H):** `orders.parquet`, `calldata_all`, `calldata_pub`, the V2 fills,
  `activity_dev`, `per_market.parquet`, `events_sel.parquet` and the windowed taker tapes.
- **Dev block:** `results/pull_attrib.json` (10-31 12-18 UTC).
- **New fetches:**
  - the data-api MERGE activity of 0x51dbdd2b for 10-16..H-1, through the cached adapter;
  - 11 `eth_getTransactionByHash` calls on the wallet's MERGE and REDEEM transactions (publicnode). I read only
    `from`, `to`, the selector and the nonce.

Nothing sealed was opened. The scripts are listed at the end.

## Critique: what the investigation is missing or getting wrong

### 1. The outcome target is chased with the wrong yardstick and a fill engine nobody validated

**The maker ladder earns the 0.978 by itself.** I took the pairs formed by its maker fills alone.

| Split | Pair cost, median | Pair cost, pair-weighted |
| --- | --- | --- |
| BUILD | 0.9750 | 0.9786 |
| VALIDATE | 0.9776 | 0.9783 |

This is the same as the overall 0.9785. FINAL_RULE (iteration-4 bullet) and NOTES (iteration-4 finding 1) say
"its 0.978 pair cost includes the informed taker legs". That is wrong. The margin that the replay misses by 2.7c
per pair is a maker mechanic, and the private taker leg is not needed to reproduce it.

**Ceilings: what an exact copy of each piece would score against the wallet's per-market PnL.**

- Legs are built from on-chain fills at settlement, before fees. Their total correlates 0.98 with
  `per_market.pnl`.
- The target is `per_market.pnl`.

| An exact copy of | BUILD Pearson / Spearman | VALIDATE Pearson / Spearman |
| --- | --- | --- |
| the locked margin of all pairs | 0.85 / 0.66 | 0.83 / 0.74 |
| the locked margin of maker-only pairs | 0.73 / 0.66 | 0.63 / 0.58 |
| the whole maker leg, including its residual at settlement | 0.39 / 0.50 | 0.38 / 0.34 |
| the whole taker leg | 0.17 / -0.06 | 0.13 / 0.14 |

The two legs correlate -0.84 / -0.87 per market, and each has about 4x the variance of the total.

- So a maker-only rule can in principle reach 0.5, but only if its PnL is mostly locked margin: it must merge
  pairs and keep its own residual small.
- A rule whose residual carries the settlement noise is capped near 0.4, even when it copies the maker leg
  exactly.
- Every X17 / X44 replay was scored only on total PnL, residual included. Report both numbers.

**The X44 engine was never checked on orders whose fills are known.** The wallet's own 24k maker orders are that
check: each has a signing time, a price, an original size and the transactions it filled in. Until the engine
reproduces them, the 1.005 against 0.978 may partly come from the engine. Three suspects:

- priority by signing time instead of post time;
- the posting window inside the taker's 1-s delay;
- the match clock of slow signers.

A first consistency check is in critique 4.

**The oracle-pull variant did not test the re-pair.** After each pull it re-joined the other makers' bid as
observed 2 s earlier. The wallet instead re-posts the complement 3-8c lower at +1.04 s: re-post top plus FAK
limit has its mode at 0.95-0.96. So "inserting its pulls changes nothing" tested a pull followed by a stale
re-join.

### 2. The maker leg protects itself through its ladder structure, not through the private feed

**Its pulls without a take are not directional.** On the dev block there are 829 own-size pulls with no take. The
team whose asks were pulled moves up by at least 1c at 10 s in 32.0% of them and down in 30.5%, against 25.8% and
28.5% at random times (`pull_attrib.json`). Outside its own takes, the ladder does not use the feed to protect
itself.

**What protects it instead.** The table covers its maker fills in other takers' BUY transactions, 16-22 Oct,
from the matched-order record. "Behind" means that another maker in the same transaction gave the taker a
strictly better price, so the taker swept through others' levels before reaching the wallet's.

| Taker | Split | Its fills | Behind the transaction's best maker (count / USD) | Signed after the taker signed |
| --- | --- | --- | --- | --- |
| other | BUILD | 12,023 | 23.8% / 34.5% | 12.7% |
| other | VALIDATE | 14,498 | 25.2% / 35.9% | 12.2% |
| pack | BUILD | 1,889 | 38.1% / 49.1% | 28.6% |
| pack | VALIDATE | 2,257 | 43.2% / 54.6% | 28.6% |

- Against informed sweepers, about half of its USD fills at deeper levels than the touch: the other makers'
  stale bids absorb the first cents.
- 29% of those fills come from orders it signed inside the taker's 1-s delay.
- The fills signed inside the delay, at the touch, against other takers earn +3.0c per share (BUILD, n = 1,212)
  and +3.2c (VALIDATE, n = 1,365) at settlement. That is the only class positive in both splits. Settlement edges
  are noisy because outcomes are binary, so use markouts.
- A one-level replay at the observed touch is the first maker hit in every sweep, at the worst price, and it can
  never post inside the delay.

### 3. The maker size is an event-level schedule, not an inventory scaling

**The size is shared across the event.** Of 22,888 CS2 maker orders, 2,426 are not 100 shares (158 of them are a
5-share start-up run on 10-16/17).

- A size other than 100 is shared by 96-97% of the same event's orders within ±60 s. That holds on both tokens and
  in every market of the event.
- Only 1.3% of the other markets' orders are 100 shares at those moments.

**It ramps up over the game.** In 30 of 77 events the size starts at 50-73 shares and steps up monotonically to
100.

- Example, `cs2-pain-fxw7`: 50 at -21 min, 56 at +19 min, then 60, 62, 66, 69 and 81, 99 at +123 min and 100 at
  +139 min.
- The median Spearman of size with time inside these events is 0.95.

**What it follows.**

- A linear fit inside each event gives size ≈ a + b × the event's paired shares, with b at a median of 0.0103
  (CV 0.65), intercept about 52 and r about 0.9.
- It is not the unpaired inventory: the size equals the complement's unpaired shares within one share in only
  2.2% of orders.

**The start size follows pre-game activity.**

- Spearman with pre-game taker USD in [gs-1h, gs) is 0.55.
- The events that start below 100 had a median of $1,166 of pre-game USD, against $8,137 for those that start at
  100 (AUC 0.82).
- The non-GRID events it skipped had less still: a median of $188.

**What this changes.**

- "54 / 58 / 68 near small inventories" (`components.size`, FINAL_RULE) is a misreading: those were the event
  sizes at the time of the dev-block takes.
- X44 replayed 100 shares in every event.

### 4. The planned presence pivot can only be examined on future blocks, but the on-chain record already holds an uncensored probe

**How often its ladder sits in a sweep.** These are in-play BUY transactions of other takers in its CS2 markets,
16-22 Oct, that swept several price levels.

- 12,942 sweeps cross at least 2 price levels. The wallet is in 44.7% of them.
- 4,234 sweeps cross at least 3 levels:
  - in 42.6% it had a level strictly inside the fully consumed range;
  - in 6.2% it was only at the last level;
  - in 51.2% it was absent.
- Per market, its share of the 3-level sweeps runs from 0.29 to 0.71 (p10-p90).
- When it is present, its first filled level is the touch in 54.7% of sweeps, the next level in 24.2% and the third
  in 15.0%.

**The probe is consistent with price-time priority.** Take the 3,143 wallet maker orders that had a public
multi-level sweep during [signing + 300 ms, first fill).

- Only 2.8% of them saw a sweep strictly through their price before their first fill.
- The wallet was absent from 34% of those transactions.
- That is about 1% contradictions, using match time = taker signing + 1.04 s (slow signers are misordered).

**Why this matters.** Each sweep is an observation, with no fill censoring, of whether the ladder reached a given
price at a known millisecond.

- It holds market activity fixed by construction.
- It is on chain, so it also exists on h1 and h2.
- The quote-presence pivot planned for iteration 5 is examinable only on future blocks. This one can be judged on
  the first exam lot.

### 5. Quick checks that came out negative or descriptive (so nobody redoes them)

**The merge job is a per-event timer of about 5 minutes.**

- Gaps between merges inside an event, p10 / p25 / p50 / p75 / p90: 7 / 15 / 314 / 333 / 623 s. 52.5% fall in
  [290, 345] s.
- The 7-15-s gaps are the next market merged on the same tick.
- Merges are relayed. The 8 sampled MERGE transactions come from 8 different EOAs with nonces of 26k-39k. All go to
  0x00000000000fb5c9adea0298d729a0cb3823cc07 (selector 0x0a3c4405).
- REDEEMs go to 0x84ba896235059fe27727eaa2695a9f99220d9a7e (selector 0x765e827f).
- The senders are relayers, not the operator.

**The co-subscriber 0x51dbdd2b runs a different merge job.**

- It made 788 merges, with gaps p10 / p50 / p90 of 61 / 155 / 873 s. Only 4.8% fall in [290, 345] s.
- In 18 shared events its merges are not phase-locked to the wallet's: 5.1% fall within 5 s of a wallet merge,
  against 4.4% with jittered times.
- So it is different software. The merge job does not support the "one operator" reading.

**Size steps are not simply recomputed at merges.** A merge falls between the last old-size order and the first
new-size order in 25% of size changes, against 9% for consecutive orders of the same size.

## Proposals, ranked by the chance they close the gap

### 1. Outcome: rebuild the replay around the maker-only pair margin, after validating the fill engine on the wallet's own orders (strong form of X44 / X17 / D3)

**Hypothesis.** The per-market outcome is carried by the maker-only locked margin (pair cost 0.978 without any
taker leg). A one-level replay at a 2-s-stale touch lacks three mechanics that produce it:

- a multi-level ladder that partly sits behind the other makers' touch, so informed sweeps reach it only at better
  prices;
- posts signed inside the taker's 1-s delay, at post-event prices;
- the event size schedule (proposal 3) plus merging, which keep the residual small.

**Why it fits.** See critiques 1 and 2:

- the maker-only pair cost equals the overall one;
- an exact copy of the maker-only locked margin would correlate 0.58-0.73 with the wallet's per-market PnL;
- its fills sit behind the touch for 35-55% of USD;
- 12-29% of its fills come from in-delay posts, and the in-delay fills against other takers earn +3c per share in
  both splits;
- the pulls without a take carry no direction.

**Test.**

1. **Engine validation.**
   - Insert the wallet's own maker orders (calldata: signing time, price, original size; resting from signing
     + 24 ms, the post latency measured live, until the last fill) as "ours", and remove them from the competing
     maker volume.
   - Score three things:
     - the share of their real filled shares that the engine assigns to the same transaction;
     - the engine's maker-only pair cost, against 0.978;
     - the probe contradiction rate, which should be at most 3%.
   - Change the priority rule until it passes: post time instead of signing time, and the per-signer match clock
     of X27.
2. **Attribution of the 2.7c.** Label every wallet and replay maker fill by:
   - its depth in the sweep (touch, 1c behind, 2c or more);
   - whether it was signed before or after the taker signed;
   - the taker class: the pack, the fast followers in `followers.json`, the rest.

   Report each class's share of paired volume and its 10-s and 60-s markouts. The class where the replay and the
   wallet differ most is the missing mechanic.
3. **Public-input variants on history.**
   - Ladder: L = 2-6 levels below the observed touch minus d, with d = 0-3c.
   - Levels sized by the event schedule.
   - Pair-sum cap K, a 5-min merge, and a residual cap.

   Score pair cost and per-market correlation against the wallet's total PnL and against its maker-only locked
   margin. Report the rule's own locked margin and residual separately.
4. **Oracle bounds (diagnostic only).**
   - Re-post the complement at K minus the FAK limit, 1.04 s after the wallet's takes, instead of re-joining the
     stale bid.
   - Post inside the delay at the post-event price after every pack signing.

   These bound what the in-delay channel is worth.
5. **Live dev block (10-31 12-18; then 11-01 06-12).**
   - Run the same ladder on the other makers' live book (own levels subtracted), with the validated queue model.
   - Add a re-post inside the delay, triggered by the first non-own cancel wave on the server clock. That trigger
     is public and executable on future blocks.

**Data.** On disk: `calldata_all`, `calldata_pub`, `orders`, `per_market`, `followers.json`, the X44 code. Live:
`tommy_cs2_near`, `calldata_dev`.

**Signature if true.**

- Step 1 passes.
- If step 3 brings the pair cost to 0.99 or below and the correlation to 0.5 or more in both splits, the outcome
  is examinable on h1/h2.
- If only steps 4-5 close the gap, outcome is a future-block claim. The in-delay post needs an event clock, and the
  public cancel wave is enough.
- If nothing closes it, the wall becomes quantitative: x% of the maker margin sits in the in-delay class.

### 2. Sweep probes: an uncensored on-chain label of the resting ladder for the quote decode and the presence pivot (new; examinable on h1/h2)

**Hypothesis.** Whether its ladder reaches price p at match time m is a function of its quote rule: the top
relative to the other makers' touch, the depth L, the pair-sum cap, and the event size and state. Every
multi-level sweep by another taker reveals this without fill censoring.

**Why it fits.** See critique 4:

- it is in only 43-49% of multi-level sweeps;
- that share runs from 0.29 to 0.71 across markets;
- its first level is the touch in only 55% of the sweeps it is in;
- the probe agrees with price-time priority to about 1%.

The quote decode so far rests on 171 live filled orders. History holds about 13k probes, and h1/h2 have their own.

**Test.**

1. **Probe table.** Use every in-play transaction of another taker that fully consumed at least one level above
   its last price. Count both directions:
   - a BUY of token t consumes sells of t and bids on the complement;
   - a SELL of t consumes bids on t.

   For each consumed level p, set y = 1 if the wallet filled at that level or a better one in the transaction.
   Keep the depth index of its first level. The match time is the taker's signing plus its per-signer delay.
   Exclude the wallet's own takes. Never use prints where it was the maker as features.
2. **Validation against the live book.** On the dev block, compare the probe label with own-level presence from
   the size fingerprint (100, or the event size from proposal 3). Target: at least 95% agreement.
3. **Fit and score.**
   - Fit P(y) on BUILD probes from point-in-time state at m - 2 s:
     - the match-clock tape;
     - the other makers' touch as revealed by earlier public transactions, and their pair sum;
     - game time, the event size state and price level;
     - with and without own inventory.
   - Distill it into an explicit band rule (top = touch - d(state), L levels) and score it on VALIDATE probes.
   - The baseline is the same model without the quote-state features. Activity is fixed by construction.
4. **Presence pivot.** Make the probe the unit of the iteration-5 pivot: presence = "an order rests at the swept
   price". It is examinable on h1/h2 because the probes come from on-chain data.

**Data.** On disk: `calldata_all`, `calldata_pub`, `orders`, `tapes/*_tkw`. Live: `tommy_cs2_near` for step 2.
On the exam lots: the same calldata decode, through `evaluate()`.

**Signature if true.**

- The probes agree with the live book at least 95% of the time.
- A band rule predicts VALIDATE probes at AUC 0.8 or more, with a gain of at least 0.05 over activity.
- The same rule, applied to its filled orders, moves `price_within_tick` above 0.305.
- If the probes cannot be predicted from public state (AUC about 0.6), its book presence depends on the private
  signal or on own state. That is itself a quantitative account.

### 3. The size schedule, and selection as a size rule censored at its floor (new)

**Hypothesis.** The size follows s_e(t) = clip(round(a + b·X_e(t)), 50, 100), with one pair (a, b) and one
cumulative quantity X.

- The start size is a function of pre-game public liquidity.
- The bot trades an event only if that function reaches its floor of 50.

This turns "favours popular events" into a mechanism, and gives a graded selection label: 0 for a skip, 50-100
for a trade.

**Why it fits.** See critique 3:

- the size is shared across the event;
- it rises monotonically;
- its floor is 50;
- its slope is about +1 share per 100 pairs;
- the start size follows pre-game USD, and skipped events have the least.

**Test.**

1. **Exact size rule.** Candidates for X:
   - own paired shares, or own merged USDC (own state, allowed for the policy, reported as such);
   - cumulative event USD on the full tape since listing;
   - cumulative in-play USD;
   - elapsed game time;
   - maps finished.

   Fit one (a, b) per X on the BUILD ramp events. Score exact and within-one-share accuracy on VALIDATE orders,
   and the timing of the steps.
2. **Start size.** A Tobit (censored at 100) on pre-game quantities known at listing:
   - cumulative event volume since listing, at gs, from the full data-api tape;
   - distinct pre-game traders;
   - pre-game depth and spread from the matched-order record;
   - tier.
3. **Censored selection.** Score the non-GRID events by predicted start size and trade those at 50 or more.
   Report AUC, recall and lift per VALIDATE day (the replication rule), against frozen v3 and the activity
   baseline.
4. **Other games and runs.** Check whether Dota 2 (10 shares) has its own floor and cap, and explain the 5-share
   run of 10-16/17.

**Data.** On disk: `orders`, the fills, `activity_dev` (merges), `events_sel`, the windowed tapes. Full tapes
since listing need a fetch for the traded and skipped non-GRID events (development only).

**Signature if true.**

- One X and one (a, b) fit at least 80% of the non-100 orders within one share.
- The start size is explained by a public pre-game measure.
- Censored selection gains at least 0.05 on each VALIDATE day.
- If X is own pairs, the ramp is an "earn to scale" risk budget (state). It is still an exact size rule,
  examinable on h1/h2 because sizes are on chain, and proposal 1's replay must use it.

### 4. The requote trigger as a hysteresis band on the other makers' book (maker timing and price; the rule that proposal 2 scores)

**Hypothesis.** The bot re-signs a token's ladder only on one of these:

- its top leaves a band around the other makers' best bid (a gap above g, or the pair-sum cap broken);
- an own fill;
- an own take.

Otherwise the ladder rests.

**Why it fits.**

- Its bursts do not follow trades: 0.0% come within 60 ms of a trade.
- Its co-movement with other makers' touch changes is symmetric: 28% before against 26% after.
- Its top sits at the other makers' bid or 1-4c below it.
- None of the rules tested so far has a trigger. They only place a price at the wallet's own signing times, which
  conditions on its presence.

**Test.**

1. **State.** On every dev block of the own recorder, server clock, rebuild its ladder and the other makers' book
   per token:
   - `level_events_dev.parquet`;
   - the size fingerprint, with the expected size per event and time taken from proposal 3.
2. **Hazard.** For each 10-ms step, estimate the hazard of an own cancel or add on the token as a function of:
   - the gap between the other makers' bid and its top, in both directions;
   - the other makers' bid sum against its own;
   - the time since its last change;
   - own fills.

   Use a time-shift null.
3. **Price.** Fit the new top after each requote as a function of the same state.

**Data.** `tommy_cs2_near`, `calldata_dev`, and from 11-01 06-12 the next development block.

**Signature if true.**

- The hazard steps up at a gap threshold (ratio of 10 or more).
- At least 80% of bursts are explained by a band crossing, an own fill or an own take.
- The top after a requote is within one tick at least 80% of the time.
- If there is no threshold, the clock is internal. Check the burst intervals (median 0.66 s) for a period. The
  price rule is then capped where X43 found it.

### 5. Scan for sibling wallets by software fingerprint (strong form of C1 / C8 / X52)

**Hypothesis.** The operator runs other wallets on the same client (other games, GRID events, a second CS2 maker).
Such siblings would widen the decision sample and map the feed's coverage.

**Why it fits.** The fingerprints are now specific enough to search for, and none of them existed when C1, C8 and
X52 were run:

- a per-event merge timer of 290-345 s, with 7-15-s bursts across markets;
- the event size ramp from about 50;
- whole-cent ladders 1c apart;
- the complement re-post 1.00-1.15 s after its own FAKs;
- `Math.random()*Date.now()` salts;
- builder = metadata = 0.

0x51dbdd2b fails the merge test (critique 5).

**Test.**

1. Take every maker with at least 50 MERGE rows in CS2, Dota 2 or Valorant markets in 10-01..10-22 (data-api
   MERGE activity, cached).
2. Compute its share of within-event merge gaps in [290, 345] s.
3. For candidates above 30%, run the size-ramp, whole-cent and re-post-hazard tests on their calldata.
4. Also check whether the wallet merged at all before 10-16.

**Data.** data-api activity (MERGE only) for the makers in the record; calldata of the candidates.

**Signature if true.** A wallet with at least 40% of its merge gaps in the band and the same size ramp runs the
same software. Compare its selection (GRID events? other games?) and the timing of its takes with the wallet's.

## Overlap with earlier panels and the ledger

- **Proposal 1** extends X44 / X17 and iteration-3 mechanics P2. That proposal asked for a queue replay; its
  engine was never validated, and the target and the re-join it was run with were wrong.
- **Proposal 2** is new.
  - It gives iteration-3 mechanics P1 (the pair-capped join) and X43 a historical test bed with no fill
    censoring.
  - It makes the planned quote-presence pivot examinable on h1/h2.
- **Proposal 3** corrects `components.size` and X35.
- **Proposal 4** is the timing half of X43 and of iteration-3 mechanics P1 step 4.
- **Proposal 5** continues X52 / C1 with new fingerprints.
- The information lens (X37 / X38, the event clock) stays the only route to the taker input. Nothing here replaces
  it. Proposal 1 says whether the outcome needs that input at all.

## How to reproduce my quick numbers

The scripts are in
`C:/Users/Remote-BEAST/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`.
They read development data only.

| Script | What it computes |
| --- | --- |
| `size_state.py` | Size against unpaired inventory |
| `size_event.py` | Size sharing across the event |
| `size_runs.py` | Per-event size sequences |
| `size_vol.py` and `size_lock.py` | Size against volume, pairs and merges |
| `size_start.py` | Start size against pre-game activity |
| `size_merge.py` | Size steps against merges |
| `leg_ceiling.py` | Leg and margin ceilings |
| `sweep_pos.py` | Sweep depth, in-delay fills and their edge |
| `sweep_probe.py` | Probes and the contradiction check |
| `merge_tx.py` | Merge senders and the merge timer |
| `cosub_merge.py` | The co-maker's merge cadence and phase |

Definitions used in these checks:

- **Maker-only pairs** = min over the two tokens of shares bought by maker fills, per market. Pair cost = the sum
  of the two average prices.
- **Bid-equivalent "pay" in a taker BUY of t** = a maker SELL of t at p pays p; a maker BUY of the complement at q
  pays 1 - q. "Behind" = the wallet's pay exceeds the transaction's minimum by at least half a cent.
- **Match time** = taker signing + 1,040 ms. This misorders slow signers by about 1 s, so the 2.8% contradiction
  rate is an upper bound.
- **Scope of the sweep checks** = only taker BUYs. The full probe table should add taker SELLs.
