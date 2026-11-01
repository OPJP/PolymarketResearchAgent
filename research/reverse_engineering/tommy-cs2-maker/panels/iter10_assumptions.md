# Panel, iteration 10: assumption breaker (fresh eyes)

Written 2026-11-01 04:40-05:30 UTC, inside the sealed block 11-01 00-06. Nothing sealed was opened. No live recording
was read; I only listed the schema of the BUILD-live table `live/20261031T1253_books.parquet` (development block
10-31 12-18). Every number below comes from development tables already in `.cache/re/tommy-cs2-maker/` (16-22 Oct,
before H): `ledger_rows_iter10`, `calldata_all`, `calldata/`, `calldata_pub/`, `per_market`, `knockout_band_markets`,
`price_offset_rows`, `events_feedcov`, `events_groupP` and `universe`. My scripts are in the session scratchpad
(`peer_anchor.py`, `peer2.py`, `xmkt.py`, `invisible_msg.py`, `dv_agree.py`, `sync_trigger.py`). Each process stayed
under 300 MB.

I read BRIEF.md, NOTES iterations 9-10 in full plus the earlier findings each proposal depends on, state.json (all 143
catalog items), FINAL_RULE.md, and panels/iter1-9 (assumptions in full, the headings of the other two lenses).

## Where the gap is

Selection passes on VALIDATE. Price (0.32 historical, 0.47 live touch, against 0.80 needed) and outcome (-0.13
against 0.50) fail. Everything the investigation has measured points to one private valuation V, re-priced on Feed P's
messages. My checks below mostly confirm that. I found two places where the evidence for "V is the wallet's own and
nobody else's" rests on the wrong object or a censored clock. I also found one item (outcome) that may be out of
reach by the brief's own definitions, whatever the decode.

## Checks (so nobody redoes them)

**A. The examiner's activity baseline cannot easily erase the selection gain.** Logistic models fitted on BUILD and
scored on VALIDATE (events_feedcov + events_groupP):
- activity alone (e_pre_n / v / w, n_mk): 0.894;
- + all72: 0.891; + all72 + nprev72: 0.895; + all24 / all72 / nprev24 / nprev72: 0.877;
- + cov72: 0.931; + gp72: 0.954.

Generic league-history activity adds nothing. Only identity-selected coverage (group P) carries the gain, so an
examiner's baseline built from market activity alone stays near 0.89 unless it picks wallet identities.

**B. There is no hidden event-level hedge behind the per-market outcome unit.** I aligned net exposure to one team
across each event's match and map markets (74 events, 143 match-map pairs):
- match vs map net Spearman 0.09, against a cross-event permutation 95% band of [-0.17, 0.16];
- sign agreement 0.55;
- residual (PnL - locked margin) correlation 0.03;
- median |sum of net| / sum of |net| = 0.78.

Per-market PnL is not one leg of a cross-market hedge.

**C. Price does not skew with inventory.** The offset from the last print moves by -0.07c (BUILD) and -0.02c
(VALIDATE) per 100 shares of own inventory (t -3.8 / -1.2, R² 0.002 / 0.001). It is flat across inventory bins.

**D. There is no per-market or proportional offset parameter.** Market x token fixed effects explain 9.6% of the
offset variance in sample, event fixed effects 1.2%. Multiplicative anchors score at or below additive ones
(last print x 0.98: 0.287 vs last print 0.305, VALIDATE).

**E. Between its own orders, the level does not follow the public price.** This is on consecutive filled orders of one
token. Carrying the previous own offset from the last print forward ("last print + previous offset") scores 0.390
(VALIDATE), against 0.449 for the own previous level and 0.322 for the last print. At 10-60-s gaps the three score
0.376 / 0.505 / 0.376. V moves on its own, not with the tape.

**F. Updating from its own level in the other market barely helps.** Match orders updated by beta x the change of its
own latest map-market level: corr(dV_match, dV_map) is 0.63-0.67 at gaps over 60 s. Within one tick moves from 0.22
(persistence) to 0.27-0.29 for those orders, and map orders get worse. This confirms one valuation but gives no usable
anchor.

**G. Peer revealed levels reach 0.65, but co-fills select them.** The anchor is the latest filled order of one other
maker on the same token, signed >= 20 ms before and <= 20 s before. It scores:
- 0xd9e0aaca 0.657, 0xe8e1b119 0.651, 0xaeb90af4 0.647, 0x51dbdd2b 0.584, 0x2005d16a 0.566;
- any other maker 0.51-0.52;
- on the same rows, own previous level 0.59-0.65 and last print 0.31-0.48.

The peer's next order after the wallet's is even closer (0.69-0.72). Both orders are known only because the same
sweeps filled them. The point-in-time form is iteration 5's revealed bid (0.25-0.28), so do not adopt this anchor. It
does show that a few fast makers sit at the wallet's level far more often than the stale public anchors do (P1).

**H. "Quiet" orders are synchronous with fast co-receiver makers, without a public trigger.** The six fast makers are
0xed446954, 0x51dbdd2b, 0xaeb90af4, 0xe8e1b119, 0x2005d16a and 0x893575c7.
- **Synchrony.** 6.69% of the 16,731 quiet-class orders have a filled order of one of these makers on the same event
  within ±60 ms. The same window shifted by +5 s gives 1.55% (4.3x).
- **No public trigger.** Only 4.6% of the synchronous ones have a public print (match clock = taker sign + 1,040 ms)
  in the 300 ms before; non-synchronous quiet orders have one 3.4% of the time.
- **Per maker.** The ratio to the shifted control is 4-20x in the quiet class, for example 0x51dbdd2b 1.78% vs 0.09%
  and 0xed446954 0.91% vs 0.10%.
- **Censoring.** Both sides are filled orders only, so the true synchronous share is several times larger.

Same-token synchronous re-pricings, the change from each maker's own previous level:

| Pair | n | dV correlation | Sign agreement | Control at -1..-3 s (corr / sign) |
| --- | --- | --- | --- | --- |
| wallet / 0x2005d16a | 53 | 0.58 | 0.75 | 0.05 / 0.39 |
| wallet / 0x51dbdd2b | 42 | 0.56 | 0.60 | 0.13 / 0.44 |
| wallet / 0xe8e1b119 | 202 | 0.31 | 0.68 | 0.19 / 0.51 |
| wallet / 0x893575c7 | 77 | 0.34 | 0.61 | 0.14 / 0.41 |
| wallet / 0xed446954 | 27 | 0.27 | 0.54 | 0.34 / 0.41 |

The samples are small and censored, but the pattern is not what "nobody shares the value" predicts.

**I. Price anchors show no heterogeneity by size, day or hour** (last print / own previous level):
- 100-share orders 0.316 / 0.521; ramp sizes 50-99 0.234 / 0.487;
- days 0.23-0.36 / 0.47-0.54;
- UTC hour bands 0.27-0.31 / 0.48-0.50.

No pooled sub-policy is hiding.

**J. Level steps.** In 95% of filled-order pairs 10 ms-5 s apart, the previous order was still resting at the new
signing. Then the new order sits +1c above it in 45% of pairs, -1c in 20% and +2c in 11%. When the previous order had
already filled, the new order repeats its price in 34% (19% at 5-60 s gaps). Note on legality: the frozen
"own previous level" anchor (0.500) needs the predecessor to have filled, almost always after t. On h1 / h2 it is a
censoring lookahead, not own state.

**K. No public anchor in silence either.** In the message ledger, orders 1-10 min after the last visible message
score 0.38 against the last print and 0.54-0.55 against the own previous level. Maker PnL is -$2.5k within 5 s of a
visible message and +$8.6k at 15-600 s.

## Critique: assumptions that look false or unproven

### 1. "Quiet" is defined by the takers' clock, and that clock is censored

The wallet-independent message clock (X137) is built from group-P TAKER actions. A Feed P message on which P4e,
0x2005d16a and the trio do not take is invisible to it. Quiet orders are 71% of fills, 56% of maker PnL and most of the
price gap, yet check H shows they are synchronous with fast co-receiver MAKERS without any public print. X63 already
saw the same thing on the live books: others' near-touch changes were symmetric around its bursts (66.8% before,
69.1% after, null 18.8%).

So two readings are confounded on most orders:
- the "fast touch-follower" reading (band hazard: it acts within 100 ms after others' best changes);
- the "event-locked own valuation" reading.

A faster co-receiver that moves first on an invisible message looks exactly like the wallet following the book. The
cascade test (X136) settled this only on the 446 VISIBLE messages.

### 2. Finding 5 ("event feed, not price feed") is tested on the wrong object

The receiver ICC (X139) and the co-signer premium correlation (X105) use FAK limits. A FAK limit is the visible ask
plus a slack:
- C8: the wallet's own limits are the ask + 0-2c;
- group G adds 7-11c, and two members send marketable limits;
- receivers at +18 to +500 ms see different asks, because the consumed side collapses inside the 1-s delay (depth
  1.00 at signing, 0.66 at +0.1 s, 0.13 at +1.0 s; X25).

If one receiver's slack is a constant policy, the premium correlation is near 0 even when both share a value. A low
ICC is therefore expected under a broadcast value as well. The object that carries a value is a maker's new level.
On synchronous same-token re-pricings, dV agrees with two group-P receivers at r ≈ 0.56-0.58 (check H). That sits
between "own model" (≈ 0) and "broadcast" (≈ 0.9), so the question is not settled.

### 3. Every live price test used a public summary that mixes stale and fresh levels

The touch, others' best, the join rule, hole filling, the ladder machines and the R anchor ("the latest add of any
maker") all pool the stale levels of slow makers and retail with the fresh levels of fast receivers. None filters by
level freshness or by maker class. If V is roughly shared by the fast receivers, the full touch is the wrong public
proxy. That would explain both facts: the touch tops out at 0.47 on fills and 0.63 on top changes, and a few
identified makers co-locate with the wallet at 0.65 under co-fill selection (check G).

### 4. The outcome item may be unreachable by definition, not by decode

Item 5 asks for an executable rule (strict fills; the held-out return is defined at latency >= 2 s).
- Per-market PnL is 75% locked-margin covariance (`per_market`: covariance share 0.76 BUILD / 0.75 VALIDATE;
  corr(PnL, margin) 0.82 / 0.75).
- The margin can be copied only with the wallet's prices. In `knockout_band_markets`, the margin of the replay of its
  own orders (A) correlates 0.75-0.79 with the wallet's margin. The executable public set (D) reaches 0.31-0.37, and its
  residual SD is 361-483, against the wallet's 122.
- The margin depends on the +50-ms take and the complement repair at ~1.04 s. The take hedges the adverse maker fills
  that the same message causes, which is why the legs correlate -0.87.
- Every replay so far kept the wallet's maker timing (A-E) or swapped in a public quote set (D, G, H). X138 delayed
  only the taker.

Nobody has measured how fast the outcome correlation decays when the wallet's OWN decisions are delayed. That curve
bounds any rule at public latency, whatever its inputs. It also decides whether to keep paying for outcome replays.

### 5. The primary metric cannot register progress

presence_auc (0.883 against a 0.891 baseline) is co-occurrence by construction for a two-sided maker that is present in
every in-play bin of its events. It has moved only through selection since iteration 3. The pivot rule therefore forces
a new paradigm every iteration, and the analyses of the running recorders keep being deferred: X38, X47b, X54, X70,
X87, X91, X101, X115, X118 and X133 all wait on 11-01 blocks.

The binding items are price and outcome. Re-register, with reasons (not results), a progress gauge that can move:
- live price within one tick on the uncensored add population and on top changes;
- the outcome latency bound L* (P3).

Keep reporting presence_auc as pre-registered.

### 6. The forward lots are not the VALIDATE bot

On the only post-H development block, Dota 2 is 54% of the wallet's trades (358 Dota vs 301 CS2 TRADE rows). The
taker caps of 1000 / 2000 have disappeared (14.4% to 0%), the taker size median fell from 470 to 183, and the CS2
100-share share fell from 89.4% to 78.4%. All price and outcome numbers are VALIDATE 16-22 Oct, which is 96% CS2. The
future-block exams will be scored on this newer, Dota-heavy mix. The Dota half has a key-free public game-state
recording (X118, Valve snapshots every ~4 s), so it is the half of the price item most likely to move, and it should
get the first VALIDATE-live slot.

### 7. The 10-29 exchange pause sits inside h1's later half

X142 decided that a one-hour pause "cannot remove whole events (matches last 1-3 h)". That holds only if the bot
resumes after the pause. Its sessions start once a day (08:10-09:04 UTC, 10-18 at 14:17) and end at 16:40-23:30, which
is consistent with a manual or scheduled start. If the process does not survive an exchange pause, the rest of 10-29 is
skipped, and replication (item 7) of the only passing component can fail on h1's later half.

## Proposals, ranked by the chance they close the gap

### P1. A freshness- and identity-filtered touch as the public form of V (new anchor class; strong form of X43 / X75 / X100 / X136)

- **Hypothesis.** V is roughly shared with the fast Feed-P makers. The full touch fails because it also holds stale
  levels of slow makers and retail. The best bid among recently re-priced levels (a "fresh touch") anchors the wallet's
  price far better than the full touch.
- **Evidence.**
  - Check G: three specific makers co-locate at 0.65 under co-fill selection, against 0.31-0.48 for the last print.
  - Check H: synchronous re-pricings with group-P makers have dV correlation 0.56-0.58.
  - Critique 3: the touch tops out at 0.47 on fills and 0.63 on top changes.
  - The touch-follower hazard (the wallet acts within 100 ms after others' best changes) fits "fast receivers move first
    on the same message" as well as "it follows the book".
- **Test (BUILD-live 10-31 12-18 for fitting, then every VALIDATE-live block).**
  1. From `level_events_dev`, with own levels removed by the validated label, rebuild each bid level with the time of
     its last non-own change. The fresh touch FT_Δ(t) is the best bid among levels changed in [t - Δ, t - 20 ms], for
     Δ in {0.25, 0.5, 1, 2, 5, 15, 60} s; fall back to the full touch when no level qualifies.
  2. Identity form: the best bid among levels whose last add is linked (`linked_adds_dev`, calldata) to a fast maker
     (median sign lag <= 100 ms behind P4e on messages: 0xed446954, 0x2005d16a, 0x51dbdd2b, 0xaeb90af4, ...). Fix
     membership on BUILD-live only.
  3. Fit Δ and a constant offset on BUILD-live. Score within one tick on the frozen populations: filled orders, all
     validated adds, top changes and the burst's first level. Report it against the touch (0.47 / 0.38 / 0.63), the
     join rule and the last print on the same rows. Block bootstrap by event.
- **Data.** The own `tommy_cs2_near` books (`level_events_dev`), `linked_adds_dev`, `calldata_dev`, and the VALIDATE-live
  blocks 11-01 06-12 and later. This is not computable point-in-time on h1 / h2 (no books), so it is a future-block
  rule.
- **Signature if true.** Within one tick rises steadily as Δ shrinks toward the feed's cadence and beats the touch by
  >= 0.10 on filled orders (to >= 0.57) and by >= 0.10 on top changes (to >= 0.73). The gain concentrates after visible
  or synchronous messages. The fast-maker identity anchor beats the slow-maker one.
- **Signature if false.** FT ≤ touch + 0.03 for every Δ. Then V is not shared with the fast makers' levels, which closes
  critique 2 on the right object and strengthens the wall account.

### P2. Invisible messages: rebuild the message clock from maker synchrony and test shared increments (strong form of X137 / X139 / X63 / X121)

- **Hypothesis.** Most "quiet" re-pricings respond to Feed P messages that no group-P taker acts on. On each message,
  the receivers' level changes are either a shared increment (a value or odds product) or each receiver's own model.
  The answer decides whether the price gap is a missing public proxy or a true private model.
- **Evidence.** Check H: quiet-class synchrony is 4.3x the shifted control (4-20x per maker) without public prints, and
  synchronous dV correlation is 0.56-0.58 with 0x2005d16a and 0x51dbdd2b. X63's symmetric co-occurrence and X94's
  informative untriggered pulls point the same way.
- **Test.**
  1. **Historical (16-22 Oct, calldata).** A message candidate is >= 2 distinct fast makers, the wallet included,
     signing on one event within 60 ms with no public print (match clock) in the 300 ms before. Estimate the censoring
     factor from BUILD-live: the share of each fast maker's adds that end filled. Reclassify X137's quiet orders and
     report the share of the price gap that moves into the message class.
  2. **Live, uncensored.** Cross-book synchrony: a non-own add or cancel on a DIFFERENT market of the same event within
     ±40 ms of a validated own re-price, with no trade on any book of the event in the 300 ms before. Compare with
     ±5-s shifts (2,000). The different market rules out a reaction to the wallet's own book (its orders reach the
     book about 24 ms after signing).
  3. **Shared increment.** On each message, compare the wallet's dV with each co-receiver's dV on the same token, or
     map them through the series ratio (0.4-0.6) when they are on different markets. Report the correlation, the share
     with |dV_w - dV_peer| ≤ 1c and sign agreement, against a within-event permutation (2,000).
  4. **Pre-register.** Shared increment iff corr >= 0.8 and |ΔdV| ≤ 1c on >= 60% of messages. Own model iff
     corr ≤ 0.3. Anything in between is partial sharing (same events, similar models).
- **Data.** `calldata/`, `calldata_pub/`, `calldata_all`, `ledger_rows_iter10`; `level_events_dev` / `linked_adds_dev`;
  the VALIDATE-live blocks.
- **Signature if true.** Synchrony without a public trigger covers >= 30% of quiet re-pricings on the uncensored books,
  and dV is shared. The price rule becomes "own level + the first co-receiver's dV whenever it posts >= 20 ms before
  the wallet". That is point-in-time on the books, and P1 is its static form. If dV is not shared, the wall account
  extends "own valuation" from the 446 visible messages to the invisible ones, which is the strong form that auditors
  will ask for.

### P3. The outcome item's latency bound, measured on the wallet's own decisions (new; strong form of X138 / X124)

- **Hypothesis.** The per-market PnL ranking needs decisions inside the 1-s delay window. If even the wallet's own
  decisions delayed by L lose the correlation for L well below 2 s, item 5 is out of reach under the brief's executable
  conditions, whatever the decode.
- **Evidence.**
  - Margin is 75% of the PnL covariance; the legs correlate -0.87; the take hedges the same message's adverse fills.
  - E (oracle maker + real taker) gives 0.87 / 0.80, but the taker moved to block + 1 s gives 0.43 / 0.39.
  - No replay delays the maker leg.
- **Test.** In the validated X57 engine (strict price-time priority, match_slack 2), delay every own decision by L in
  {0, 50, 100, 250, 500, 1000, 2000} ms:
  - maker placements at sign + L, each order kept for its observed lifetime shifted by L;
  - takes as FAKs at sign + L + the in-play delay, against the book the engine holds then;
  - complement repairs at their own times + L.

  Measure per-market Pearson / Spearman against the wallet on BUILD and VALIDATE (event bootstrap), plus the realized
  pair cost.

  Maker cancels are not observed historically. Check the lifetime-shift assumption on BUILD-live, where cancels are
  visible: the share of shifted orders that would have been pulled before the fills the engine assigns them.
- **Data.** knockout and engine inputs already on disk (`engine_check_rows`, `knockout_markets`, `calldata_pub`),
  BUILD-live books for the cancel check.
- **Signature if true.** Both coefficients fall below 0.5 at some L* ≤ 500 ms. Write item 5 as a proven wall
  component with L* and the pair cost at L*, stop outcome replays, and put the remaining budget on price (P1 / P2,
  X133, X118).
- **Signature if false.** Correlation stays >= 0.5 at L = 2 s. The outcome item is then reachable at public latency with
  a correct maker decode, the knockout failures are decode failures, and the next replay should copy the wallet's
  quote set at L = 2 s rather than search public anchors.

### P4. Score the forward lots by title, and give the Dota half the first VALIDATE-live slot (planning fix for critique 6; not a new catalog item, it reorders X118 / X132)

- **Hypothesis.** The future-block exams will be Dota-heavy (54% of TRADE rows on the only post-H block). Dota is the
  title where a key-free public game state exists at the spectator delay, the delay at which the feed's Dota messages
  arrive. The Dota price is where item 4 can move most, and the CS2 VALIDATE numbers understate what the forward exam
  can reach.
- **Test.**
  1. On every VALIDATE-live block, compute price within one tick, outcome correlation and coverage separately for Dota
     and CS2, with the frozen rule and with X118's Valve-state anchor. Pre-register X118's anchor on Valve receive time
     plus the measured lead.
  2. Report the pooled value that each title mix implies: the 16-22 Oct mix and the 10-31 mix.
  3. Before any future exam, check the build fingerprints on the development blocks: merge-loop law 300.22 s + 7.28 s
     x merges, the [0.05, 0.95] band, the 1.5-s timer, the size ladder, the +51-ms lag. The frozen constants were fitted
     on 16-22 Oct.
- **Data.** The tommy_dota_rt recorder (X118), the books, and calldata of the development blocks.
- **Signature if true.** Dota within one tick ≥ 0.6 with Valve state, against ≤ 0.43 for the last print (VALIDATE Dota
  0.431). The pooled price item at the forward mix is then materially above the CS2-only number. A fingerprint change
  means the frozen constants must be re-fitted on BUILD-live before the future exam.

### P5. Operational continuity across the 10-29 pause, decided on development analogues (strong form of X142 step 3 / X106)

- **Hypothesis.** The wallet's process does not survive exchange-side disruptions. A pause ends its day's session, so
  the rest of 10-29 is skipped, and h1's later-half selection recall drops below the replication tolerance.
- **Test.**
  1. In development periods, from the full public tape of its leagues' markets, list exchange-wide disruptions: minutes
     with zero prints across all in-play esports and sports markets, post-only windows, and Polymarket status-page or
     announcement times for 10-01..10-22 and 10-31.
  2. For each one, check whether the merge loop (300.22 s + 7.28 s x merges) stayed phase-continuous through it, and
     when the first own order came after it.
  3. Take the 10-29 pause time only from public announcements; do not use h1 data.
  4. Pre-register before the h1 exam how `evaluate()` reports selection on events that start after a known pause in the
     same session: reported both ways, with no universe change unless the development analogue shows a session break.
- **Data.** Development tapes, activity rows (MERGE), public incident notes.
- **Signature if true.** The merge loop breaks at past disruptions and restarts only the next morning. h1's 10-29
  remainder is then a known recall risk, documented before the exam. If the loop resumes within minutes, X142's
  conclusion stands with evidence.

## Notes for the wall account and overlap

- **What is unexplained.** The price gap is now framed as V on messages that the taker clock does not see. P1 and P2
  are the strong form of "own valuation" that auditors will ask for. "No public anchor reaches 0.8" holds today only
  against summaries that mix stale and fresh levels.
- **Outcome.** P3 turns the outcome failure into a number (L*) that does not depend on the decode.
- **Overlap.**
  - P1 and P2 are new in their object (maker levels and increments, freshness and identity). They build on X136
    (visible messages only), X139 / X105 (FAK limits), X135 (size classes), X63 / X94 (live co-occurrence) and X121
    (cancels around takes).
  - P3 is new: no maker-delay sweep exists.
  - P4 reorders X118 and adds a per-title report.
  - P5 strengthens X142 step 3.
- **Negative checks A-K.** They close cross-market hedging, inventory skew, per-market and proportional offsets,
  offset persistence, the cross-market own update, a generic examiner baseline for selection, and size or day pooling.
- **Legality warning.** Check J's own-previous-level anchor needs the predecessor's later fill on the historical record.
  Do not adopt it in the h1 / h2 rule.
