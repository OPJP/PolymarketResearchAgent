# Panel, iteration 9: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false: the unit and the target, pooling, the exam's
arithmetic, operational and human effects, and where the per-market PnL really comes from.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iteration 1 in full, iterations 2-8 by their findings and closing states, iteration 9 in
full with the late additions), state.json (catalog A1-X131, ledger H1-H111, components, target metrics), FINAL_RULE.md,
`code/final_rule.py` (`_gp72`, the v5 score) and panels/iter1-8. I skimmed the iteration-9 information and mechanics
panels after my own checks, to avoid duplicates. There are no EXAM or wall-audit files.

Calendar (`sealed.py tommy-cs2-maker`): no released lots; the current block (11-01 00-06) is sealed. I used only
development data:

- 16-22 Oct tables in `.cache/re/tommy-cs2-maker/` (`per_market`, `orders`, `chain_fills_*`, `calldata_all`,
  `events_groupP`, `events_meta`);
- the BUILD-live tables of the 10-31 12-18 block (`linked_adds_dev`, `level_events_dev`, `others_mid_dev`);
- the listing projections the reverse engineer already stored (`results/exam_league_mix.json`, `universe_t0`).

I opened no sealed file and read no live recording. I wrote nothing in the workspace except this file. My scripts are
in `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\tommy_iter9_asm\`:
`addlevel_fresh.py`, `touch_view.py`, `touch_by_trigger.py`, `late_adds.py`, `residual_phase.py`, `pnl_phase.py`,
`exam_power.py`, `tier2_swing.py`.

## Checks (so nobody redoes them)

### A. In development, GRID and tier were perfectly confounded for big events; h1 and h2 are not

- In `events_meta` (every CS2 event listed 09-25..H, 1,324 events), all 55 tier-2 events carry a `gridSeriesId`, and
  no tier-1 event exists. Non-GRID tier 2 is an empty stratum: in the 384-event selection universe of 16-22 Oct, tier 2
  is 6 events, all GRID.
- The h1 listing projection (`exam_league_mix.json`) has 180 CS2 events: 80 GRID; non-GRID tier 5: 62, **tier 2: 18**,
  tier 4: 16, tier 3: 4. h2 has 157 events: 62 GRID; non-GRID 5: 60, 4: 16, **2: 13**, 3: 6. The forward listings
  (`universe_t0`) show tier-1 IEM and BLAST Rivals and tier-2 PGL Masters events without a GRID key. The key is attached
  about 1 h before the start, so the far-ahead ones are not final.
- Dota's PARI Universe is non-GRID tier 2, and the wallet trades it (3 of 4 events on 10-22, 2 of 3 on 10-31).
- The v5 exam constants have tier rates for 3, 4 and 5 only. An unseen tier-2 league falls back to the prior (0.294).
  I re-scored the six development tier-2 events as non-GRID in an unseen league. v5 gives p10 / p50 / p90 =
  0.37 / 0.40 / 0.46 at gp72 = 0: one of the six is above the exam threshold of 0.472. At gp72 = 2 they score
  0.63-0.71, all above it.
- Swing on an h1-like lot: development strata resampled to the h1 counts, plus 18 stand-ins drawn from development GRID
  events re-scored as non-GRID in an unseen league. The stand-ins are a pessimistic popularity proxy. In-sample
  constants, 300 draws, medians:

  | 18 tier-2 non-GRID events | AUC | Recall | Lift |
  | --- | --- | --- | --- |
  | stratum absent | 0.973 | 0.71 | 7.7 |
  | all skipped by the wallet | 0.973 | 0.69 | 8.7 |
  | all traded, gp72 = 0 | 0.81 | 0.32 | 4.1 |
  | all traded, gp72 = 2 | 0.89 | 0.35 | 4.1 |

  The expected positives elsewhere in h1 are 12-19 events. What the wallet does with 18 events of a stratum it never
  met in development decides whether recall clears 0.5.

### B. Item 2 is partly arithmetic

- Base rate of traded CS2 events by day: 10-16 0.075, 10-17 0.21, 10-18 0.03, 10-19 0.24, 10-20 0.17, **10-21 0.32**,
  10-22 0.24.
- Lift cannot exceed 1 / base rate. On 10-21 alone, frozen v5 (build constants) has recall 0.773 at lift **2.81**. At a
  threshold of 0.40 it has 0.50 at 2.88; at 0.50, 0.32 at 3.14 (precision 1.0). No threshold gives recall >= 0.5 with
  lift >= 3 on that day. On 10-22 it has 0.71 at 3.83. Pooled VALIDATE (3.155) hides this.
- h1 is not at risk from this ceiling: its expected base rate is about 0.07-0.09. A power simulation on the h1 mix
  without the tier-2 stratum (in-sample, optimistic) gives:
  - positives: median 15 (p10 12, p90 19);
  - AUC: v5 0.968 against activity 0.864;
  - P(one-sided 99.75% event-bootstrap lower bound of the gain > 0) = 0.97;
  - P(recall >= 0.5 and lift >= 3 at the frozen threshold) = 0.97.

  The risk is a busy future-block lot. The 10-31 12-18 block had 6 of 25 events traded (0.24).

### C. Exit has an unwritten hard band, and the residual is the endgame

- Of the 24,180 maker orders (16-22 Oct), **none lies outside [0.05, 0.95]**: the minimum is 0.05 (75 orders sit
  exactly there) and the maximum 0.95 (42 orders). Taker limits run from 0.06 to 0.93. Nothing in NOTES or FINAL_RULE
  records this band.
- Per market (229 markets, `per_market`):
  - SD of PnL $224, of the locked margin (pairs x (1 - pair cost)) $202, of the residual $122;
  - corr(PnL, locked margin) = 0.84 Pearson / 0.70 Spearman (VALIDATE 0.83 / 0.74);
  - corr(PnL, pairs) = 0.50 / 0.29;
  - pair cost per market p10 / p50 / p90 = 0.930 / 0.979 / 1.030. A quarter of the markets lock a loss.
- The residual builds at the end. I took the fills after the last moment the inventory imbalance was zero or on the
  other side:
  - they start at a median 95% of the wallet's fill span in the market (p10 68%, p25 87%);
  - they are maker fills (median share 1.0);
  - the residual side's price is p10 / p25 / p50 = 0.08 / 0.13 / 0.22.

  153 losing residuals cost -$14.2k, by the price of their build-up:

  | Build-up price | Markets | Residual |
  | --- | --- | --- |
  | <= 0.10 | 43 | -$2.6k |
  | 0.10-0.25 | 78 | -$7.5k |
  | 0.25-0.50 | 26 | -$3.6k |
  | above 0.50 | 6 | -$0.5k |

  The residual is the losing team collapsing through its ladder, down to the 0.05 floor.

### D. The quote-level lead (finding 14 / H106) survives a fresh anchor and quiet books

| Own adds (2,740) vs other makers' adds (75,213), Spearman of offset vs others'-mid move | 2 s | 10 s | 30 s |
| --- | --- | --- | --- |
| as in `add_level_info.py` (anchor and move from -100 ms) | 0.52 vs 0.24 | 0.44 vs 0.17 | 0.34 vs 0.09 |
| anchor = others' mid just before the add, move from +100 ms | 0.29 vs 0.10 | 0.24 vs 0.08 | 0.19 vs 0.03 |
| same, books quiet for > 1 s before the add (602 vs 27,259) | 0.36 vs 0.10 | 0.33 vs 0.05 | 0.23 vs 0.03 |

- 53% of its adds come within 100 ms of an others'-mid change (other makers' adds: 39%).
- The mean others'-mid move in the add's direction over [-100, 0] ms is +0.007c (other makers' adds: +0.044c).
- So about half of finding 14 is the concurrent window. A lead of 3-6x the placebo survives after the add, even in
  books that were quiet for a second, and the wallet does not follow the direction of the preceding book move.
- "It copies a faster maker's re-pricing within 100 ms" does not produce the effect. Joiners pegging to it after the
  add remain possible. The information panel's P4 (bid / ask split) and the mechanics panel's receiver cascade test
  that.

### E. The touch rule's view time is not the price problem

- Full-book touch within one tick of its validated adds, by view time (my rebuild; the reverse engineer's value at
  -100 ms is 0.472):

  | View time | -1 ms | -5 ms | -20 ms | -50 ms | -100 ms | -300 ms |
  | --- | --- | --- | --- | --- | --- | --- |
  | Within one tick | 0.455 | 0.446 | 0.434 | 0.445 | 0.430 | 0.413 |

- By the add's context:
  - reactive adds (others' mid changed <= 100 ms before), n 1,458: 0.416;
  - 100 ms-1 s, n 686: 0.567;
  - quiet for > 1 s, n 604: 0.457.
- Offsets from the touch have p10 = p25 = -4c, a mass at touch - 4c.

### F. Delay-queue leak, strong form on adds (X60 step 3 tested only cancels): negative

- Wallet maker BUY orders signed after the transaction's taker signed:
  - against retail takers (<= 20 orders in the record): 13.3% of its fills against them. They sit exactly at the
    taker's limit in 0.19 of cases, against 0.37 for its earlier-signed orders;
  - against other takers: 15.8% of fills, 0.27 vs 0.40.
- Other makers behave the same way (retail 0.15 vs 0.26).
- Retail "late" offsets: median 1.7 s, p90 11 s. A retail order's signing time is not its submission time.
- It does not price into pending orders. The leak reading is closed for adds as well.

## Critique: assumptions that look false or unproven

### 1. "GRID is the coverage boundary" was learned where GRID and tier were the same thing

- Every tier-1/2 CS2 event of the development period was GRID-flagged (check A). So the data cannot tell "Feed P does
  not carry GRID events" from "Feed P does not carry big events".
- Group G's GRID-event activity (finding 4) shows that a product covers GRID events. It says nothing about whether Feed
  P covers big events that have no GRID data.
- h1 and h2 contain exactly that stratum (18 and 13 events). The frozen rule has no parameter for it: it uses the prior
  tier rate, an unseen league and gp72 = 0 for a tournament's first events.
- This is the largest unexamined risk to the one component that passes, on the next exam.
- The Dota analogue (PARI Universe, non-GRID tier 2, traded) suggests the wallet trades the stratum. That is the case
  where v5 can lose most of h1's recall.

### 2. The selection target is treated as if it measured only the decode

- Lift >= 3 at recall >= 0.5 is impossible when a half's base rate exceeds 1/3, and it needs precision of about 0.96
  at 0.32 (10-21, check B).
- The pre-registered presence label (a fill in a 30-s bin) is the weakest presence label for a continuous two-sided
  maker. It is co-occurrence with taker prints by construction, so it sits below its baseline (0.883 vs 0.891).
- The brief prefers "an order resting". The recorded books observe that label on every future block, and it would not
  depend on the lift arithmetic.
- Human and operational effects create labelled skips the rule cannot see:
  - sessions are started by hand at 08:10-09:04 UTC;
  - the brief's one-hour exchange pause on 10-29 falls in h1's later half.

### 3. "The outcome item is the price item" is half right; the other half is an exit rule nobody wrote down

- Per-market PnL is mostly the locked pair margin (0.84). Per-market pair cost spans 0.93-1.03.
- The unpaired residual, which ruins every replay, is built in the last ~5% of each market as the loser collapses
  through the wallet's ladder to a hard 0.05 floor (check C).
- None of the replays (knockouts B-D, margin replays, balanced ladders) was checked against this band and stop.
- Part of their residual mismatch may be a mechanical stop rule, not the private value.
- The rest is the take and re-pair units. The mechanics panel's critique 4 makes the same point: knockout A caps a
  maker-only rule at 0.43 / 0.33.

### 4. Reconstructed game state is treated as public at the moment the game happened

- OpenDota's parse is published after the match. A feature built from it can only enter at the event's public
  broadcast time plus a delay; the brief's template is ESPN plays at wall clock + >= 5 s.
- The feed acts at the spectator-broadcast instant, and the market follows 3-14 s later (iteration-8 finding 24). A
  rule delayed by 5 s keeps only the tail of that window.
- A Dota price rule scored without that delay, as the information panel's P1 is written ("exam-ready for h1 / h2"),
  would be a leaked match. On future blocks the Valve recorder's receive time is the exact point-in-time stamp.

### 5. Smaller points

- **Finding 14 is stronger than written** (check D), but its 2-s numbers include the concurrent window. Quote the
  post-add numbers (0.24 vs 0.08 at 10 s; 0.33 vs 0.05 in quiet books) in the wall account.
- **The outcome item's market set is not pre-registered.** `pnl_corr` uses v5's selected events, which mixes the
  rule's false positives (wallet PnL 0) with traded markets. Over the full universe the zeros alone would create a
  correlation from selection. That must not count, and the claimed set should be written down before an exam.

## Proposals, ranked by the chance they close the gap

### P1. Decide Feed P's coverage of non-GRID tier-1/2 events before h1 is examined (new; the GRID x tier confound)

- **Hypothesis.** The wallet's boundary is Feed P's coverage. In development it coincided with "non-GRID" only because
  every big CS2 event was GRID-flagged.
  - Either Feed P carries non-GRID tier-1/2 events, and the wallet trades them as it trades PARI Universe in Dota,
  - or the boundary also has a tier part, and it skips them.

  v5 only extrapolates there.
- **Why it fits.**
  - Check A: 55 of 55 development tier-2 events are GRID; h1 has 18 and h2 13 non-GRID tier-2 events; the forward
    listings have IEM, BLAST Rivals and PGL Masters without a GRID key.
  - The traded / skipped swing moves h1 recall from about 0.7 to about 0.3.
  - Dota tier-2 non-GRID is traded.
- **Test.**
  1. **Listing projection only** (the X84 route; no fills, prints, books or outcomes of sealed units). For the h1 / h2
     non-GRID tier-2 events, list league, serie and tournament strings and scheduled starts. Check which strings the
     v2 / v4 tables know; "PGL" (traded 9 of 13 as a qualifier) is not "PGL Masters". Count how many events have
     gp72 = 0 by construction, i.e. no earlier event of the same league in the previous 72 h, from the listing alone.
  2. **Development evidence.**
     - Dota non-GRID tier 2 (PARI Universe): traded rate and group-P presence.
     - CS2 events of the same organisers at lower tiers.
     - Group P's absence from GRID tier-2 events cannot separate "no big events" from "no GRID events". Only a non-GRID
       big event can.
  3. **Forward development blocks.** For every non-GRID tier-1/2 CS2 event that starts in a development block, record
     group-P prints, the wallet's trades and v5's score. IEM on 11-02 starts in the development block 00-06, provided
     its GRID key is still null about 1 h before the start. BLAST Rivals follows on 11-10/11.
  4. **Pre-register the tier-1/2 treatment before the h1 claim.**
     - A: explicit (a tier-1/2 non-GRID rate from steps 2-3).
     - B: coverage-first. Unseen big leagues are scored by group-P prints in the same tournament, including the event's
       own earlier maps before each map starts. This is point-in-time, because maps 2 and 3 start after map 1.
     - C: zero (a tier boundary).

     Report check A's h1 envelope for each.
- **Data.** Gamma listing projection for h1 / h2 (allowed fields only), `events_meta`, `universe_t0`, the Dota
  universe, development-block tapes and calldata.
- **Signature if true** (Feed P covers big non-GRID events): group-P prints and wallet trades appear in IEM / PGL
  Masters-type development units, and option A or B keeps h1 recall >= 0.5 in the envelope.
- **Signature if false:** no group-P prints in those units. Then add a tier boundary, and restate finding 4 ("GRID is a
  coverage boundary") as GRID-or-tier.
- **Why it closes the gap.** It is about 10% of h1's events, more than the positives expected elsewhere. A wrong
  treatment alone fails selection, the only component that passes.

### P2. Exit: the [0.05, 0.95] band and the endgame residual as a decodable stop rule; rebuild the outcome replays on it (new; strong form of the exit component, X124, X82)

- **Hypothesis.** The ladder is clipped at 0.05 / 0.95 (a client constant). The wallet keeps bidding a collapsing team
  down to the floor. The unpaired residual (-$8.4k on 16-22 Oct) is that collapse, in the last ~5% of each market.
  - This part of the per-market outcome is a public function of the price path, the band, the ladder depth and the
    size, not of the private value.
  - Unless the wallet pulls the loser's ladder before the public collapse, which would be a new footprint of the
    private input in the exit component.
- **Why it fits.** Check C: no order outside the band among 24,180; the build-up starts at a median 95% of the fill
  span; 121 of 153 losing residuals were built at <= 0.25. The replays lose on the residual (-$9k to -$16k), and
  nobody has written down the band or the stop.
- **Test.**
  1. **VALIDATE, describe the stop.** For each market, place the wallet's last bid on the eventual loser (time, price,
     ladder depth) against the public path: the times the loser's public price crosses 0.25 / 0.10 / 0.05.
     - Does it stop before the floor, or ever pull before the public collapse?
     - Compare with other makers' last bids in the same collapses.
  2. **Rebuild the replays on the band.** Re-run knockouts B / C / D and the best margin replay in the validated engine,
     with the band and the observed stop. Report:
     - the per-market residual's correlation with the wallet's residual;
     - the per-market PnL correlation (Pearson and Spearman) next to the prints baseline.
  3. **Decompose the wallet's per-market PnL** into the locked margin of take-and-re-pair units (X12), maker-only
     pairs, and the endgame residual. Report each part's correlation with the total, so item 5 has an exact bill of
     what it needs.
- **Data.** `chain_fills`, `orders`, taker tapes, the X57 engine (`knockout_markets`), `per_market`.
- **Signature if true.** Once the band and the stop apply, the replay residual correlates >= 0.5 with the wallet's.
  The remaining outcome gap is then the locked margin of the take units, a single number for the wall account. A
  pre-collapse pull on the loser would instead be a new private-input footprint.
- **Why it might close part of the gap.** The residual carries about a quarter of the per-market PnL variance
  (covariance share 0.24, correlation 0.45), and it is the one part of item 5 that a public rule could own. The other
  three quarters are the locked margin, which step 3 bills to the take units.

### P3. Item 2 by arithmetic and by the right label: per-lot lift ceilings, resting-order presence, labelled skips (new; metric specification)

- **Hypothesis.** The selection item can fail for reasons unrelated to the decode:
  - the lift ceiling (1 / base rate) on busy halves;
  - a presence label (fills) that is co-occurrence by construction;
  - skips caused by downtime or exchange pauses.

  A resting-order presence label is an independent route to item 2 on future blocks.
- **Why it fits.** Check B (10-21: no threshold passes); presence 0.883 vs 0.891 on the fill label; manual session
  starts; the 10-29 pause in h1's later half; X61 (a 3-hour session day costs about 0.06 AUC).
- **Test.**
  1. **Lift ceiling per lot.** For each candidate lot (the halves of h1 and h2, future 24-h sealed lots), compute the
     expected base rate from the listing projection and development stratum rates (including P1's stratum) and the
     implied ceiling. Pre-register the operating threshold that maximises P(recall >= 0.5 and lift >= 3) over a
     day-pair bootstrap of development days, instead of the 20th-percentile rule.
  2. **Resting-order presence, on BUILD-live and then VALIDATE-live.**
     - Label: a validated own resting level in the (market, 30-s bin). Use multi-level bursts and odd sizes (precision
       0.93-0.98) and the calldata-linked adds.
     - Score: v5 x market-in-play. Baseline: the activity-only model fitted on the same bins.
     - Report AUC, gain and the game-block bootstrap, and pre-register it as the presence metric for the future-block
       exam (the brief's preferred label).
  3. **Labelled skips.**
     - From public status information, list exchange pauses and engine restarts in development periods, and the
       wallet's session behaviour around them (development data only).
     - If the bot did not resume within the pause, pre-register a universe exclusion for events that start inside an
       announced pause window. The trigger is public and point-in-time.
- **Data.** `events_groupP`, listing projections, BUILD-live / VALIDATE-live books and calldata, public exchange
  status history.
- **Signature if true.** Resting presence reaches AUC >= 0.85 with a gain >= 0.05 over the activity baseline, so item 2
  has a route on future blocks without the lift arithmetic. The per-lot ceilings show which lots selection can pass at
  all.

### P4. Point-in-time accounting for game-state inputs: the lead budget after the publication delay (strong form of X118 / X123; the legality check for the information panel's P1)

- **Hypothesis.** A Dota price or timing rule is exam-legal only if it still leads the market after the publication
  delay of its input:
  - OpenDota parses enter at broadcast time + >= 5 s;
  - Valve's live snapshots enter at their receive time.

  The share of the wallet's informative Dota re-pricings and takes whose market move comes more than (5 s + snapshot
  granularity) after the message bounds what any public Dota rule can reach on h1 / h2 and on future blocks.
- **Why it fits.** Critique 4. Public moves sit 3-14 s after the feed's messages on the spectator clock (iteration-8
  finding 24). The X123 and X119 tests and the information panel's P1 score game state at its game time.
- **Test.**
  1. On the 10-22 PARI maps (P4e-fixed D) and the 10-31 development maps: the distribution of (first public >= 2c move
     - feed message time) for kill-linked messages, and the shares above 5 s and above 9 s (5 s plus a 4-s snapshot).
  2. Score every Dota game-state rule twice, at the spectator time and at +5 s. Only the +5-s version counts for
     h1 / h2. Report both.
  3. VALIDATE-live with `tommy_dota_rt`: does the first snapshot showing the state change arrive, at receive time,
     before the wallet's 10-share re-pricing and take (X118 b)? By how much, and for what share?
- **Data.** `dota_pub`, OpenDota parses (cached), `tommy_dota_rt` (development blocks), recorded Dota books.
- **Signature if true.**
  - Most market moves come more than 5-9 s after the message: a legal public Dota rule can still lead the market and
    anticipate part of the wallet's re-pricing, so the information panel's P1 is exam-relevant.
  - Most come sooner: no OpenDota rule can be both legal and leading. The Dota route is then future-block-only (Valve
    receive time), and only if the snapshots arrive before the wallet acts. That number belongs in the wall account.

## Notes for the wall account and overlap

- **Closed by my checks:**
  - leader-copying as the source of finding 14 (check D);
  - touch view time as the price problem (check E);
  - pricing into pending orders, i.e. the delay-queue leak on adds (check F).
- **Overlap with the other iteration-9 panels.**
  - The bid / ask split, the joiners and the receiver-cascade placebo for finding 14 are the information panel's P4
    and the mechanics panel's P1. My check D says what they should expect: a post-add lead of 3-6x the placebo in
    quiet books.
  - The maker-only outcome cap is the mechanics panel's critique 4. P2 adds the exit band and the endgame, which they
    do not cover.
  - P4 is the legality condition for the information panel's P1.
- **Not in the ledger or the catalog before this panel:**
  - the [0.05, 0.95] band;
  - the GRID x tier confound and the non-GRID tier-2 stratum of h1 / h2;
  - the per-day lift ceiling.
