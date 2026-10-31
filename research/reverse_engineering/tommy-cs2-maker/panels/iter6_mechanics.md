# Panel, iteration 6: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are actually built and kept. That covers the signed order fields (salt, timestamp, size, limit),
the attribution of resting levels on the live book, the client's timers and loops, merges, and what the client
software is.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-6 in full for 6, by section for 1-5), state.json (catalog A1-X86, components,
hypotheses), FINAL_RULE.md (v3) and every earlier panel file. There are no EXAM or wall-audit files.

`tools/sealed.py tommy-cs2-maker`: nothing is released, and the future is examined up to 10-31 00:00. Every record I
read is development data:

- `calldata_all.parquet` (blocks of 10-16 13:39 .. 10-22 23:15 UTC);
- `activity_dev.parquet` (10-15 .. 10-22);
- `calldata_dev.parquet` and `dev_markets.parquet` (10-31 12-18 block, games starting 12:00-17:45);
- `cooldown_pairs_dev.parquet` (the same block).

One new fetch: MERGE-only data-api activity in [10-15, H) for five other wallets (0x51dbdd2b, the pack wallet P4e
0x4ebc2722 and three 1.5-s-timer makers from finding 18), through the cached polyrea adapter. I opened nothing in
`.cache/live/sealed/`, read no record of a unit starting at or after H outside the 10-31 12-18 block, and wrote
nothing outside this file. My scripts are in the scratchpad (listed at the end); each ran in under 2 minutes and
under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The live-book "own level" label is contaminated by other 100-share makers, and the frozen live rules depend on it

Every live result since iteration 3 finds the wallet's resting levels by size: a whole-cent level change of 100
(or 68 / 58 / 54) shares counts as its own. That was safe in the 16-22 Oct history (X66: no other 100-share ladder
in its markets). It is not safe on 10-31.

In `calldata_dev` (the BUILD-live block), take the filled BUY maker orders of exactly 100 shares at whole cents in the
CS2 markets whose books are recorded:

| Market | Wallet | Other makers |
| --- | --- | --- |
| gls1-pcy (match) | 118 | 17 |
| gls1-pcy map 1 | 56 | 12 |
| gls1-pcy map 2 | 21 | 2 |
| shin-isg (match) | 7 | 13 |
| shin-isg map 1 | 0 | 19 |
| wraith-ntr | 0 | 11 |
| bhe-bar2 | 0 | 1 |
| **All** | **202** | **75 (27%)** |

- **Who the others are.** 0x68915897, 0x9f63eb94, 0xf1f2b3c6, 0x758dac51 and 0x904ed7c7 are the fast late makers
  of iteration 3. 0x68915897 is also one of the six owners of the untraded 1.5-s-timer ladders (finding 18).
- **What is clean.** Sizes 68 / 58 / 54 are 85-100% the wallet's.
- **What separates them.**
  - Same-ms ladder bursts: 19% of the wallet's orders share their signing ms with another of its orders
    (25,878 orders, 16-22 Oct). For the other 100-share makers in these books it is 2.7%.
  - The others' single 100-share adds are rarely within 60 s of a wallet 100-share fill in the same market (28%).

Several conclusions rest on this label:

- **H69 (the wallet's hard 1.5-s timer).** By book, the spike excess of 100-share re-adds at 1,500-1,520 ms
  (`cooldown_pairs_dev.parquet`) is:
  - 79 in gls1-pcy (87% of its 100-share fills are the wallet's);
  - 41.5 in shin-isg (35%);
  - 25.5 in bhe-bar2, where the wallet has no 100-share fill at all;
  - 8 in wraith-ntr (no wallet fill).

  At least part of "its" timer belongs to someone else, and the most likely owner (0x68915897) is the largest other
  100-share maker in its books.
- **H62 / X78 (the wave follower).** At the pack's events a "pull" includes any single cancel of exactly 100 shares.
  The other 100-share makers post exactly such singletons. The finding that the pull barely changes the wallet's hit
  rate (39% vs 42%) is what pulls that are not the wallet's would produce. Y1 is rejected either way, but whether
  the wallet follows the public wave at all, and its 15-ms latency, are not established.
- **`live_price`, frozen in `evaluate()`, and X75.** "Others' best with own levels removed" also removes the
  competitors' 100-share levels at the touch. That pushes J below the true others' best, which may be part of why the
  join rule scores only 0.198 exact / 0.424 within one tick on filled orders.
- **X81 (pair-sum IQR 4c, "one token per burst") and X70 / X63 (occupancy, triggers).** Mixing two makers' tops
  produces exactly an incoherent pair sum and untriggered "own" bursts.

The re-registered VALIDATE-live block (11-01 06-12) is the next data to arrive. If these rules are scored there before
the label is validated, the pre-registered test is run on a mis-specified label, and a later fix would be fitted on
VALIDATE-live.

### 2. The wallet has a unique, deterministic software clock on chain, and nobody looked at it

Its MERGE transactions follow a loop law (16-22 Oct, all 2,129 merges, my check):

- **One pass merges each market in turn.** Each market with at least 100 paired shares gets one merge, and each merge
  takes about 7.3 s (the relayer round trip). No merge is smaller than 100.0 shares.
- **Then the loop sleeps 300.0 s.** The interval between pass starts is 300.22 s + 7.28 s x (merges in the previous
  pass): 683 intervals, residual sd 1.33 s, 95.5% within 3 s. The last merge to the next pass is 306-308 s.
- **Empty passes are invisible but keep the phase.** After gaps of 400-7,200 s, the next pass lands within 3 s of
  (last merge + 307 + 300.0 k) in 48 of 49 cases.

No other wallet I checked shares this law:

| Wallet | Merges | Residual sd of the law | Min merge | Gap inside a pass |
| --- | --- | --- | --- | --- |
| 0x51dbdd2b | 804 | 117 s | 10 | 1-5 s |
| P4e | 749 | 144 s | 5 | |
| Timer maker 0xca0b532d | 247 | 102 s | 250 | 45-54 s |
| Timer maker 0x2b55d2ee | 257 | 134 s | 250 | 45-54 s |
| Timer maker 0xd3bd48ab | none | | | |

0x51dbdd2b's passes are not phase-locked to the wallet's (offset to the previous wallet pass: p10 / p50 / p90
41 / 194 / 901 s).

Unlike the shared 1.5-s re-post, this loop is specific to the wallet's software. It is:

- a process-uptime and restart clock;
- a fingerprint to find siblings;
- a key for identifying the client.

X66 named "the merge-timer scan" but never ran it.

### 3. The salt is treated as a distribution, not as a stream

The salt is the only field of a signed order that carries the client's internal state. The investigation used it
once, as "uniform up to Date.now()".

On the full record it holds tightly:

- salt / sign_ms lies in [0, 1] for all 25,878 orders, with a maximum of 0.99999;
- the ratio is uniform (KS p 0.70);
- it never exceeds 1.

So salt = round(U x T) with T at or just before the signing ms. If U comes from a small-state generator, its state
can be recovered, and the hidden stream (every order signed, filled or not) becomes countable. My weak-form test of
Node / V8 is negative (quick checks), which already narrows the client's runtime.

### 4. Smaller points

- **The three components are three loops.** The maker leg is an event loop (per-token re-quote bursts, a cooldown),
  the inventory leg a 300-s timer loop, and the taker leg a feed handler. Decode them as separate state machines
  with separate clocks, not as one quote function. The merge loop shows that at least one loop is deterministic to
  the second.
- **The other 100-share makers changed between history and the live block** (absent in X66's 16-22 Oct scan,
  present on 10-31). The own-level label is not stationary, so any live rule that the examiner runs on future blocks
  with the size fingerprint inherits a drifting error.

## Quick checks (so nobody redoes them)

1. **V8 Math.random() salts, weak form: negative.**
   - Model: salt = round(U x T), T in [sign_ms - 3, sign_ms] ms; U a V8 xorshift128+ output, both mantissa
     conventions (state0 >> 12, and the older state0 & mask).
   - Test: GF(2) linear solve of the 128-bit state on the 37-39 known top bits per output. Every assignment of a
     ladder burst's orders to consecutive generator positions was tried (the 64-value LIFO cache makes any order
     possible), with up to 2 gaps, and on 5-order bursts with strides 1-4 in price order.
   - Result: 0 of 197 4-order bursts and 0 of 71 5-order bursts are consistent (one noise hit at 13 redundant bits
     with gaps, below the expected false-hit count).
   - Control: the solver recovers synthetic V8 streams with 32 redundant equations on 4 outputs.
   - So the client is not Node / V8 with the salt as its only Math.random() consumer.
2. **No transport tick in the taker signing times.**
   - Pairwise intervals of its 1,642 taker decisions (taker orders within 5 ms merged) within 2.5-120 s in the same
     event: the Rayleigh scan over 100-8,000 ms peaks at Z 14 near 1,059-1,095 ms. That is the FAK-return chain
     (sign, then about 1.05 s later sign again), not a feed tick.
   - Nothing at 250 / 500 / 1,000 / 3,000 ms.
   - The per-event phase scan over 20 ms-20 s reaches z 4.1 at most, which is not significant after the
     look-elsewhere correction.
   - So no polled or fragment-quantised source shows at this resolution.
3. **The size ramps are not released by merges.**
   - There are 115 up-steps of the event-wide size in 27 ramp events. 7.0% of them fall within 15 s after a merge,
     against 10.2% of all maker signings in those events.
   - Steps are small and continuous (68 -> 69 -> 83 -> 85 -> 86 -> 87 -> 89), so they are not freed collateral
     at merges.
4. **The merge-loop law is unique to the wallet** (critique 2).

## Proposals, ranked by the chance they close the gap

### P1. Validate the own-level label against calldata, then re-run and re-freeze the live rules before 11-01 06-12 (correction; strong form of X43 / X63 / X75 / X78 / X79)

- **Hypothesis.** A material share of the levels labelled "own" on the live book belongs to the five other
  100-share whole-cent BUY makers in the same books. Three findings are partly artefacts of that:
  - the 1.5-s timer;
  - the wave-following pulls at the pack's events;
  - the low join score of `live_price`.

  With a validated label:
  - the join rule's score on filled orders changes materially;
  - the price units (top changes, adds) are re-measured on the wallet's own decisions.
- **Evidence.** Critique 1:
  - 27% of 100-share fills in its recorded CS2 books belong to others (100% in two books);
  - the timer excess appears in a book where the wallet has no 100-share fill;
  - the "pull" has no protective effect (39% vs 42%).
- **Test (BUILD-live, 10-31 12-18; nothing from 11-01 is opened).**
  1. Link ground truth. For every filled maker order in `calldata_dev` (every maker), find its add on the server-clock
     book: same token side, price and size increase within [sign_ms, sign_ms + 500 ms]. Label each linked add wallet
     or other. Report the precision and recall of the current fingerprint per book and per size.
  2. Build an attribution rule from features that unfilled orders also have:
     - membership in a same-size multi-level burst within 5 ms;
     - contiguity with the existing own ladder (1c spacing);
     - the post-take complement re-post at about 1.04 s;
     - sizes 68 / 58 / 54.

     Measure its precision on the linked adds (target at least 0.95). For the timer, attribute spike re-adds that
     later filled to their owner through calldata (an order signed within 50 ms before the add).
  3. Re-run on validated own levels only:
     - H62 / `wave_lock.py` with multi-level pulls only;
     - H69 / `cooldown.py`;
     - `final_rule._live_price` (remove only validated own levels from others' best);
     - `price_units.py`, `joint_quote.py` and `live_occupancy.py`.
  4. Re-freeze `live_price`, H62 and H69 with the new label in `final_rule.py` and state.json `live_split`, before
     reading the 11-01 06-12 block. Then score them there unchanged.
- **Data.** `calldata_dev.parquet`, `level_events_dev.parquet` (or rebuild with all level deltas),
  `cooldown_pairs_dev.parquet`, `dev_markets.parquet`; all on hand.
- **Signature if true.**
  - The fingerprint's precision is below about 0.8 in the shin-isg / wraith-ntr / bhe-bar2 books.
  - The 1.5-s spike re-adds that later filled belong mostly to 0x68915897 or the other timer makers.
  - The wallet's multi-level pulls at the pack's events are rarer than 48%, or their timing against the wave changes.
  - `live_price` with others' best restored moves away from 0.424 on the same 172 filled orders (in either
    direction; the frozen number is then wrong).
- **Signature if false.** Precision is at least 0.95 everywhere, and the re-runs reproduce the iteration-6 numbers
  within noise. The live findings then stand on a validated label, which the wall account needs anyway.

### P2. Identify the client software from its fingerprints and run its quote function (strong form of C8 / X66; new data class: source code)

- **Hypothesis.** The maker leg is an existing bot, public or a fork, whose quote function, cooldowns and merge loop
  are in readable code. The wallet's private part is the taker feed handler.
- **Evidence.**
  - The wallet's maker client has deterministic constants: a 300.0-s merge sleep after sequential awaited merges
    (about 7.3 s each); one merge per market; a minimum merge of 100 shares; 100-share whole-cent buy-only ladders on
    both tokens; a pair cap near 0.99; merges of complete pairs.
  - Its salts are millisecond-scale. The Python py-clob-client seed is round(now_seconds x random()), seconds-scale,
    like the 0xd553 maker in its books (salt 1.2e9).
  - The V8 weak test fails, so plain Node with no other Math.random() use is unlikely, and the language is open.
  - A web search found candidates whose design matches part of this:
    - warproxxx/poly-maker and its forks quenos/poly-maker and itgoyo/poly-maker. Per the search summary, it buys
      YES at r - delta and NO at (1 - r) - delta, so both tokens are bought. It has a separate `poly_merger` module.
    - abocchi1/polymarket-trading-bot: Node.js, ladders (LADDER_LEVELS=5), a merge threshold and merge / redeem
      automation.
    - PolyScripts2/polymarket-market-maker-bot.

  None is confirmed to match; that is the test.
- **Test.**
  1. Read the source of each candidate as text; do not run it.
  2. Extract the merge cadence and size threshold, order size, ladder levels and spacing, pair cap, cancel / re-post
     cooldown, re-quote trigger and salt generator.
  3. Score each candidate on these fingerprints against the wallet. A match needs the merge law (300 s plus
     sequential merges, minimum 100) plus at least two of the others.
  4. For a match, port the quote function to the recorded books (P1's validated label). Fit only its config
     parameters (delta, levels, size) on BUILD-live, and score per own add, per top change and per filled order on
     VALIDATE-live.
  5. If no repo matches, search for the merge law's constants (a 300-s / 300,000-ms merge interval, minimum merge size
     100) in public Polymarket bot code, and record the negative.
- **Data.** The public GitHub pages (normal-visitor reads), the recorded books, and calldata.
- **Signature if true.** The candidate code holds a 300-s merge loop with a minimum of 100 and a 1.5-s re-quote /
  cooldown. Its quote function reaches at least 0.8 within one tick on top changes and adds on VALIDATE-live, and it
  reproduces the one-token-per-burst re-quotes and the deep states the public join rule misses (for example "step
  one tick behind if the best's size is below X").
- **Why rank 2.** It is the only route found that could lift price from 0.42-0.63 toward 0.8 in one step. The match
  probability is modest, but a negative is cheap.

### P3. The untriggered re-quotes as a dense label of the private feed (strong form of `maker_pre_taker`, X46 and X63; run on P1's validated label)

- **Hypothesis.** Its in-round input reaches the maker leg between takes. Re-quote bursts with no public, own-fill or
  timer trigger are fair-value updates from the private feed. They lead the market in their direction and make the
  feed's event stream visible at several times the take rate.
- **Evidence.**
  - 37% of its add bursts have no public trigger within 50 ms (22.5% within 200 ms; X63), part of which may be other
    makers (P1).
  - Maker orders signed within 30 s before a same-team take see the next 4c+ jump in their favour in 60-62% of cases,
    against 41-42% for its other orders (iteration 1, conditioned on its later take).
  - The 29 strict-signature pulls without a take go up 62% / down 17% (random 26% / 29%; X46).
  - The pack-event pulls were tested; its own-event-class pulls without takes were not.
- **Test (BUILD-live, then VALIDATE-live).**
  1. Classify each validated own burst on token i. Triggered means at least one of the following preceded it:
     - an others' level change within 2c of either token's touch, a print, or an own fill in [-300, 0] ms;
     - an own cancel at the same price 1,480-1,540 ms earlier;
     - an own take in the previous 2 s.

     Otherwise the burst is untriggered.
  2. Direction: top raised vs lowered (or the ladder shifted toward / away from token i).
  3. Markout: token i's others'-mid change at +2 / +10 / +30 s, excluding bursts within 5 s before its own takes,
     so as not to condition on its later action.
  4. Null: the same bursts shifted by plus or minus 60-600 s within the market (at least 2,000 draws).
  5. If it is informed, time the untriggered bursts against the X38 chat clock and the round markets (X47b) to type
     the events: kills vs plants vs economy.
- **Data.** The recorded books (own recorder), `calldata_dev` and the round-market recorder; on hand or recording.
- **Signature if true.**
  - Untriggered raises are followed by moves in their favour beyond triggered raises and beyond the null
    (p < 0.0025), and untriggered lowerings by adverse moves.
  - Their rate is several times the take rate.
  - They precede the next informed burst more often on the reversal pattern (after a pack burst on the other team).
  - The feed is then continuous (a full event log, not a plant alarm), and the taker's 16-20% coverage is a take
    filter on a denser input.
- **Signature if false.** Untriggered bursts carry no markout. The maker leg is an uninformed state machine of
  public, own and timer inputs, which bounds the price residual to the client's internal logic (P2) and confines
  the private input to the taker.

### P4. The merge loop as the process clock: uptime, restarts, versions and siblings (new; C1 / C4 / C5 strong form)

- **Hypothesis.** The 300-s loop runs for the life of the client process. Its phase gives exact uptime segments and
  restarts across the whole maker regime, and on every later lot, because MERGE activity is public. Restarts mark
  version changes. Any other wallet with the same loop law is the same software, and a phase-locked one is the same
  process.
- **Evidence.**
  - The law fits with residual sd 1.33 s.
  - Empty passes are exactly 300.0 s, with the phase continuous across gaps of up to 2 h (48 of 49).
  - There are 6 breaks of 2 h or more in 16-22 Oct.
  - The law is not shared by 0x51dbdd2b, P4e or the timer makers (critique 2).
- **Test.**
  1. Segment 10-16..10-22 into phase-continuous runs and mark phase jumps as restarts. Mark the first appearance of
     the loop around the 10-16 switch: merges in the taker regime or not.
  2. Compare the restarts with:
     - the 64 downtime skips of X61 (are they outside the runs?);
     - the starts of the event-wide size ramps (36% of events: does a ramp start after a restart?);
     - change points in maker size, ladder depth or taker caps (C4).
  3. Report selection AUC on events whose whole in-play span lies inside a run, as a diagnostic only: uptime is
     own activity and cannot be an exam feature.
  4. Sibling scan:
     - fetch MERGE activity (development periods, polite, MERGE type only) for every maker with at least 50 fills in
       its markets (`calldata_all`), and for the makers of a matched sample of untraded non-GRID CS2 / Dota events;
     - fit the law;
     - test the phase-lock to the wallet's passes.
- **Data.** data-api activity (MERGE) for development periods; `calldata_all`.
- **Signature if true.** Skips inside runs are real decisions, and those outside are downtime. Size-ramp episodes or
  versions start at restarts. A wallet with the same law, and its passes interleaved within one 300-s cycle of the
  wallet's, is a second wallet of the operator: it widens the scope and gives more data for the taker leg.
- **Why rank 4.** It does not move the exam metrics directly. It cleans the selection labels, settles Y5 at the
  process level and makes the wall account exact on uptime.

### P5. Recover the client's random-number state from the salts: uncensored order counts and process identity (strong form of C8)

- **Hypothesis.** The salts are consecutive outputs of a small-state generator other than plain V8, for example:
  - Bun / JavaScriptCore or SpiderMonkey (xorshift128+ with an additive output);
  - V8 with k extra draws per order (a bot calling Math.random() elsewhere).

  Recovering its state makes every draw countable, including unfilled ladder levels, rejected posts and zero-fill
  FAKs, from the on-chain record alone.
- **Evidence.**
  - salt / sign_ms is uniform in [0, 1] and never above 1: a ms-scale U x Date.now().
  - Ladder bursts give 4-10 orders signed within 3 ms: 294 groups of at least 4.
  - The V8 weak form is negative (quick check 1), so the runtime is not plain V8 with salt-only draws.
- **Test.**
  1. V8 with k = 1..8 extra draws per order: all assignments for bursts of 5-6, with a strict criterion of at least
     24 redundant equations.
  2. JSC / SpiderMonkey: a z3 model of xorshift128+ with output (s0 + s1) & (2^53 - 1) on bursts of 5-6. This needs
     `z3-solver`; install it in a separate target folder, not the shared venv, and with the user's consent if
     required.
  3. If a state is recovered:
     - step it forward and backward (it is invertible);
     - locate every later filled salt of the wallet;
     - count the draws between consecutive filled orders, and compare them with the own adds visible on the live book
       (draws minus visible adds = hidden orders, such as FAKs with no fill);
     - search the stream for the salts of 0x51dbdd2b, the pack and the timer makers (a hit on 40 bits is not
       chance).
  4. If every family fails, record the runtime as one with a CSPRNG (for example a Rust or Go client), which narrows
     P2.
- **Data.** `calldata_all` and `calldata_dev` (salt, sign_ms), on hand.
- **Signature if true.** Consistent solutions on most bursts. Then:
  - the counted draws give the full signing rate per market and per event;
  - the number of take attempts per informed burst becomes measurable on h1 / h2 once released (the taker's 16-20%
    coverage, uncensored);
  - shared streams identify one process across wallets;
  - stream breaks date the restarts.
- **Why rank 5.** It has a high payoff, but the most common runtime has already failed.

## Overlap with the ledger and earlier panels

- **P1 corrects H62, H69 and X75 / X78 / X79 / X81 / X70.** None of them validated the size label against other
  makers' calldata on the live block. X66 checked sibling sizes only in the 16-22 Oct history, and finding 18 found
  the 100-share timer ladders only in untraded markets.
- **P2 is the strong form of C8**, after one generic web search in iteration 1, with fingerprints that did not exist
  then (merge law, timer, salt scale).
- **P3 is new as a test.** Iteration 1 conditioned on its later take, X46 looked only at pulls, and X63 measured
  trigger rates without markouts.
- **P4 runs the merge-timer scan named but not run in X66.** It is new as a process clock.
- **P5 is new.** The salt was only described.

## How to reproduce my quick numbers

The scripts are in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`.
Run them from the repository root with `.venv/Scripts/python.exe`:

| Script | What it checks |
| --- | --- |
| `v8salt.py <hi\|lo> <dT> <maxn> <gaps>` | GF(2) consistency test of ladder-burst salts as V8 outputs |
| `v8selftest.py` | Synthetic control for the solver |
| `v8stride.py <hi\|lo> <dT>` | Strided draws on 5-order bursts |
| `phase.py` | Per-event phase scan of taker signing times |
| `phase2.py` | Pairwise interval scan of taker signing times |
| `merge_loop.py <out.json>` | MERGE fetch and loop law for the wallet and five others; result in `merge_loop.json` there |

The contamination table and the timer split by book were one-off pandas reads of `calldata_dev.parquet`,
`dev_markets.parquet` and `cooldown_pairs_dev.parquet`:

- BUY maker rows with shares == 100 at whole cents, by maker and market slug;
- spike vs control counts for 100-share pairs by slug.

## Sources (web search)

- [warproxxx/poly-maker](https://docsearch.algolia.com/mcp/docs/repo/warproxxx/poly-maker)
- [quenos/poly-maker](https://github.com/quenos/poly-maker)
- [itgoyo/poly-maker](https://github.com/itgoyo/poly-maker)
- [abocchi1/polymarket-trading-bot](https://github.com/abocchi1/polymarket-trading-bot/wiki)
- [PolyScripts2/polymarket-market-maker-bot](https://github.com/PolyScripts2/polymarket-market-maker-bot)
