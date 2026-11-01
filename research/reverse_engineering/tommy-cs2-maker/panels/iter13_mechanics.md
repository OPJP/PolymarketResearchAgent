# Panel, iteration 13: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built, which process signs them, and what the order record can and cannot say about V.
Covers V's map-to-match mapping, the clock under finding 18, the loop and size mechanics, and the operator's other
accounts outside esports.

Written 2026-11-01, about 10:25-11:20 UTC, inside the development block 11-01 06-12.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 13 in full, plus earlier sections by heading (X47 round markets, X56 sweep probes, X59 sizes,
  X137 message ledger, X158 loop, X160 / X171 round clocks);
- state.json: the catalog A1-X188, the components, the target metrics;
- panels/iter12_mechanics.md in full;
- results: inround_drift.json, inround_lead.json, event_value_coupling.json, sibling_history.json,
  round_takers_hist.json.

`tools/sealed.py tommy-cs2-maker`: no released lots; the future is examined up to 10-31 00:00; the current block is
development.

Every record I used is development data:

- `orders.parquet` / `calldata_all` (signed before H);
- the per-market tapes clipped to H;
- bo3 rounds of the 86 development maps (16-22 Oct), through the shared cached client;
- sibling activity, through `PolymarketData().activity`, clamped to before H;
- Gamma `markets_by_condition` for 60 September sport markets of 0x52661b8e (development units).

I read no live recordings, opened nothing in `.cache/live/sealed/`, decoded no new calldata and wrote nothing outside
this file. My scripts and intermediate rows are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m13\`.
Of these, `drift_tok.py` is a copy of `code/iter13/inround_drift.py` that also writes each round's tokens, guards, bo3
kills and durations. Every process ran for under 5 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. Finding 5 ("one value, the same cents on both books, not scaled by the series sensitivity") reflects the 1-cent tick

I re-ran `event_value_coupling.py` unchanged, writing its 53 nonzero pairs to my scratchpad. The "same cents" median
comes from the 14 pairs with a 1-cent map move, where 57% of the match moves are also 1 cent. The tick cannot show
anything smaller. On larger moves the match book moves by s x the map move:

| Map moves included | Pairs | Slope on dV_map | Slope on s x dV_map | Median abs(dV_match / dV_map) | Median s |
| --- | --- | --- | --- | --- | --- |
| all (>= 1c) | 53 | 0.495 | 1.054 | 1.00 | 0.46 |
| >= 2c | 39 | 0.490 | 1.043 | 0.63 | 0.45 |
| >= 3c | 32 | 0.493 | 1.047 | 0.57 | 0.45 |
| >= 4c | 27 | 0.486 | 1.036 | 0.57 | 0.45 |

The data support one map-level value written into the match book through a series model, with a slope of about 1 on
s x dV_map. They do not support "the same cents" or "about twice a series model". The public match print still barely
moves (ratio 0.11), so the series mapping is private too. Consequences:

- the strategy statement and the price component should say "map value V, match value = series(V)";
- the match book's quote is a deterministic function of the map book's (proposal P5).

### 2. Finding 18 holds, but its clock mixes rounds, and the kill profile does not show a kill-by-kill state

**Token-mix control (passes).** In A-won rounds the last burst is on token 1 in 0.566 of rounds; in B-won rounds, 0.450.
This is the expected fill selection: buyers of the gaining team fill its bids on the other token. On a single token the
drift still predicts the round winner:

- token 0: AUC 0.845 against the print's 0.647 (617 rounds);
- token 1: AUC 0.839 against 0.639 (640 rounds).

**Clock check (mixed).** About half of the print-inferred "rounds" span more than one real round. In 48.7% of them the
bursts span more time than bo3's own `round_duration` for that round (40.4% even with 30 s of tolerance). Burst spans
have p50 / p75 / p90 of 116 / 236 / 458 s, against bo3 round durations of 120 / 147 / 169 s. Those segments carry the
highest AUC:

| Segment class (span relative to the bo3 round duration) | Rounds | AUC, its drift | AUC, print | Gap 95% CI (map bootstrap) | Winner-signed move: its value / print |
| --- | --- | --- | --- | --- | --- |
| span <= 0.5 x duration | 274 | 0.808 | 0.664 | [0.081, 0.209] | 3.54c / 0.92c |
| 0.5-1.0 x duration | 185 | 0.893 | 0.588 | [0.219, 0.392] | 6.36c / 0.64c |
| span > duration | 435 | 0.937 | 0.714 | [0.171, 0.274] | 7.81c / 1.69c |
| tight: first burst to the next segment's first burst <= duration | 250 | 0.884 | 0.659 | | |

In the tight subset the 45-s guard gives 0.792 against 0.655 (137 rounds). Before the print's first 2-cent move it
gives 0.778 against 0.504 (197 rounds).

Two further checks on the short segments:

- the drift does not predict the previous round's winner (0.525), so it does not carry a result already known;
- it predicts the next round's winner only weakly (0.568).

So finding 18 is real: its value leads the print on round outcomes inside clean single-round windows.

**Kill profile (the open question).** A kill-by-kill in-round state predicts that the drift grows with the winner's
dominance, and that clutch rounds drift toward the eventual loser for most of the round. The data show neither:

- Spearman(winner-signed move / leverage, the winner's kill margin) = -0.017 (p 0.61);
- rounds where the winner was out-killed or level (43): AUC 0.937 against the print's 0.518, a 6.8c move toward the
  winner, the same as dominant rounds (6.3c);
- by the winner's survivors (<= 1 / 2 / 3 / 4-5):
  - all segments: 5.8 / 6.1 / 6.7 / 6.1c;
  - 45-s guard: 2.8 / 3.5 / 4.1 / 3.8c;
  - clean segments only: 3.6 / 3.8 / 5.7 / 4.8c (Spearman 0.08, p 0.11);
- only the pre-print-move window shows a gradient: 0.9 / 1.8 / 2.5 / 2.1c.

The move scales with the round's leverage. By leverage tercile it is 4.5 / 5.5 / 9.1c, or 0.41 / 0.31 / 0.30 of the
full round swing, against 0.04-0.08 for the print. That is the signature of a correctly levered valuation, but it does
not say what the valuation's input is.

With a clock that is off by tens of seconds, "V knows the round's decisive event (last kill, plant outcome, the round
end) seconds before the print" fits the data at least as well as "V tracks kills". The strategy statement's "in-round
win-probability state fed by kills and plants" is not yet established. Proposal P2 is the test.

### 3. bo3 `begin_at` plus cumulative `round_duration` is not an absolute clock

Against the print-inferred segments, the per-map offset of bo3 time (median over rounds 0-4) is spread over p10 / p90
of -272 / +530 s. Consecutive-round changes of the lag are within 20 s in only 15.7% of pairs. `begin_at` is not the
live start, and the durations include pauses. The durations can still fix the relative spacing of rounds within a map,
but a clock needs per-map anchoring on wallet-independent evidence (P2).

### 4. The 504-ms loop is not a fixed-phase timer (historical, censored record)

I scanned the period over 16-22 Oct, using the wallet's maker bursts with those within 2 s after its own takes removed.
Over a whole session there is no coherent phase: the Rayleigh Z at 504.00 ms is 0.6-4.4, about the median of the scan.
The best period in 15-30-minute windows wanders between 503.0 and 504.7 ms (24 windows with Z > 9: p10 / p50 / p90 of
503.45 / 504.15 / 504.68 ms), and the phase at a fixed period drifts between windows.

This fits a loop that sleeps about 500 ms after each pass, so its period is 500 ms plus that pass's work. It does not
fit a server-side snapshot cadence of the feed (E17 branch a), which would keep its phase for hours. I found no
dependence of the period on load: Spearman with the number of distinct markets is -0.02 (24 windows), which is
underpowered. The live record can decide this (P1, step 5).

### 5. Size step-ups are not tied to the merge loop (negative check)

There are 125 step-ups in the 28 ramping CS2 events. Of these, 4.0% fall within 5 s after a merge, against 5.7% of all
orders. So freed collateral (merges releasing USDC) does not set the size; the CLOB balance limit is not the ramp.

Step-ups follow a long silence in the event (the gap before them has a median of 163 s) and fall near a new book's
first own order slightly more often than at random: 13.6% within 120 s, against 7.2%. This weakly points to a
recomputation when a market starts or re-starts, not to an inventory rule.

### 6. The operator's accounts also quote sports with public play-by-play, and nobody has looked

The X176 census opened the operator's esports history only (`sibling_history.json` has the title list).

**0x52661b8e ("TommyLeePeeecan"), September.**

- 1,334 sport trades in 421 events: BUY 1.000, whole cents 0.872, band 0.987, size mode 50.
- 146 MERGEs inside sport events.
- Football in about 60 leagues (Champions League, Championship, Brasileirão A / B / C, Argentina, Chile, Colombia,
  Europe), plus MLB (434 trades).
- In a sample of 60 markets, all moneyline, 89.9% of trades fall between 0 and 150 minutes after the game start
  (median 74 minutes): in-play.
- That is the wallet's BUY-only plus MERGE maker design, run in play on sports where ESPN and MLB statsapi publish
  timestamped events.
- In July and August the same account quoted esports two-sided (BUY 0.49 / 0.35, SELL 7.6k / 7.0k).

**0x67119033.** It trades ITF tennis two-sided (984 trades, BUY 0.51, no merges), plus NHL, MLS and AHL.

**0x7d67f01d.** It has no trades in August: the June-July two-sided design and the September BUY-only design are
separated by a one-month gap.

These are the cleanest natural experiments left for V (P1, P3).

## Proposals, ranked by the chance they close the gap

### P1. The operator's in-play SPORTS quoting as a public-input twin of V (new data; outside every X item)

- **Hypothesis.** The same process and valuation pipeline quote football and MLB in play on 0x52661b8e (and NHL / ITF on
  0x67119033): the same BUY-only five-slot ladder, merge loop, sleep loop and fan-out position. They are fed by the same
  vendor's push feed. In these sports the inputs are public with wall clocks:
  - ESPN soccer key events (goals and red cards) and play-by-play;
  - MLB statsapi pitch-level `playEvents` times;
  - NHL api-web play-by-play.

  So V's model form can be fitted against public state. That form is "pre-match prior + event jumps + a clock term
  sampled by the loop". The feed's lead over the public clock, and the vendor (through the co-receivers), can be
  measured.
- **Why it fits.** Critique 6 (BUY 1.000, 146 sport merges, 90% in play, size 50), the one-process finding of iteration 13,
  and the feed's fan-out. 0x2005d16a, a group-P member, trades NBA and other sports through a push feed (X114). If
  that feed and the operator's are one multi-sport product, the co-receivers show it.
- **Test** (development periods only).
  1. Decode the calldata of 0x52661b8e's September sport transactions (about 1,300 trades, a few hundred txs; the
     `fetch_calldata.py` path used for `sib7d67`) and of 0x67119033's NHL / ITF ones. Keep sign_ms, limit, size, side
     and maker / taker.
  2. **Design fingerprint.** Check whole cents, the band, the slots per 50-ms burst (V..V-4), the merge law
     (period and increment), salts at ms scale, and the local 504-ms phase lock of quiet bursts (X158 tracker).
  3. **Public clock.** Map events to ESPN game ids (team names plus start time) and to MLB statsapi gamePks. Then run
     an event study of its order signings (maker re-pricing bursts and takes) around goals, red cards and scoring plays,
     at lags of -60..+60 s, against the ESPN wall clock and the first public print reaction on Polymarket.
  4. **Value form.** Compare its burst tops to a public in-play model:
     - football: a Poisson model from the pre-game price, the score, the minute and red cards;
     - MLB: the win expectancy from inning, outs, base state and score.

     Score within one tick. Between events, test whether quiet tops drift with the clock (the draw-decay derivative for
     football) at the predicted rate on the 504-ms grid.
  5. **Co-receivers.** On the same markets, check whether P4e, 0x2005d16a, the trio or group G take within 0-200 ms of
     the operator's takes, with the CS2 lag order (the operator +34-65 ms behind P4e). Also check whether the loop's
     period lengthens with the number of books it quotes (critique 4).
- **Data.** Activity (cached), Polygon calldata for about 2,000 trades, Gamma listings, ESPN soccer / NHL and MLB
  statsapi (polyrea adapters or key-free endpoints), and the tapes of those markets.
- **Signature if true.**
  - The same fingerprints.
  - Quiet tops within one tick of a public-state model plus a constant margin on >= 60% of orders, with a clock-driven
    drift between events.
  - Jumps at goals or runs signed a constant L s after the true event and ahead of ESPN.
  - The CS2 co-receivers present at the same lags.

  Then V's model class is decoded on public inputs, the vendor is a multi-sport push-feed product (the information
  panel can name it, and a user could license it), and the CS2 V is "the same model on that product's esports
  events".
- **Signature if false.**
  - The sports quotes sit at the public print (like the June CS2 version), or follow ESPN with a public lag.
  - No co-receivers.

  The private feed is then an esports-only product. That narrows the vendor search and closes the multi-sport branch
  with a measurement.

### P2. A wallet-independent true round clock (the strong form of X160 steps 1-3), then the kill-state vs early-result test

- **Hypothesis.** The X171 print HMM puts round boundaries tens of seconds off, and about half of its "rounds" span
  more than one real round (critique 2). On a true clock, V's private information is one of two kinds:
  - **(R)** mostly the round's decisive event or result, received seconds before the market: V is then a series /
    MR12 valuation of a fast score plus a small in-round part;
  - **(K)** a kill-by-kill in-round state.

  These need different data. (R) needs a fast score, which the sports socket carries for GRID, HLTV scorebot carries
  with the user's help, and the multi-market traces carry in the public record. (K) needs a kill feed: demos (X37 /
  X122) or the stream (X4 / X22), both with consent.
- **Why it fits.** Critique 2:
  - 48.7% of segments are longer than the round;
  - the AUC is highest in those segments (0.937);
  - the move is flat in the winner's kill margin and survivors, even with a 45-s guard (2.8 / 3.5 / 4.1 / 3.8c);
  - finding 24's table test (3.96c vs the print's 2.82c) was run at print-inferred round starts, which can sit inside
    the next round.
- **Test.**
  1. **Clock.** Per map, the round-end times are e_r = T0 + sum of bo3 `round_duration` up to r + pauses, with pauses
     >= 0 inserted only between rounds and a penalty per pause. Anchor T0 and the pauses on wallet-independent public
     reactions, using constraint e_r <= the first reaction to round r's result. The candidate reactions are:
     - a >= 2c print in the winner's direction on ANY book of the event: map, match, and the round handicap / totals
       markets of X47 (665 markets, whose prices must step at every round end);
     - the pack's take clusters (signing ms, on chain).

     Fit by the lower envelope: minimize the sum of (first reaction - e_r) subject to the constraint, allowing a few
     outliers. Report the clock's residual against held-out reactions.
  2. **Validate the clock** where a truth exists:
     - GRID maps of the operator's GRID accounts (X188), against the sports socket's round scores on development
       blocks;
     - BUILD-live non-GRID maps, against the co-mover cluster clock (X180 step 2).
  3. **On the true clock**, measure:
     - the share of V's winner-signed move that falls in [end - 5, end + 10] s, against earlier in the round;
     - the survivor / kill-margin gradient before end - 5 s;
     - finding 24's side-aware table and X171 re-run at true round starts (freeze time);
     - V's reaction latency to the true end against the print's.
- **Data.** bo3 rounds (durations, end reasons, team kills, plants; already cached for the 86 maps), all tapes of each
  event's markets including round handicap and totals (X47's list), pack calldata clusters, and the sports socket for
  GRID on development blocks.
- **Signature if (R).**
  - At least 70% of the winner-signed move lies within [end - 5, end + 10] s.
  - A flat survivor profile.
  - The table residual at true round starts is <= 2c (print 2.8c).

  Then V = series(MR12 / side table, fast score) plus offsets. That is an examinable price model on future blocks
  wherever a fast public score exists, and a quantified lag bound on h1 / h2.
- **Signature if (K).**
  - The move accumulates through the round.
  - The survivor gradient is at least 2x before end - 5 s.
  - The table residual stays near 4c.

  The in-round event feed is then indispensable, and the user's consent items (demos, VOD) become the only route to
  the historical half.

### P3. The operator's version history from July to September: date the private value and read V from two-sided quotes (strong form of C4 / X185)

- **Hypothesis.** The private V entered the process on a datable day D between the June version (at the public print,
  offset 0c, 0.455 within one tick) and late September (-3c, 0.218, +65 ms behind P4e). Intermediate versions are
  natural experiments:
  - 0x52661b8e's July-August esports quoting was two-sided (BUY 8.0k / SELL 7.6k in July; 3.8k / 7.0k in August). A
    two-sided quote's mid is V itself, with no ladder or slot ambiguity;
  - 0x7d67f01d has a one-month gap (no August trades) between its two designs.
- **Why it fits.** X185 compared only June with late September. The one-process finding makes every account a view of
  the same valuation. A two-sided version gives an uncensored V (bid and ask both fill), which the BUY-only record never
  does.
- **Test.**
  1. Decode a weekly sample (about 300 txs per week) for 0x52661b8e (07-03..09-30), 0x7d67f01d (06-19..07-31) and
     0x67119033 (09-27..10-15).
  2. Per week and per account, measure:
     - the maker share, BUY / SELL, sizes, whole cents, slots per burst and the merge law;
     - the offset from the last print, and the within-one-tick share;
     - for two-sided periods, the mid of same-ms bid / ask pairs (or of bid fills and ask fills within 2 s) against the
       print.
  3. On CS2 maps of each week with bo3 rounds, run the in-round drift test with P2's clock if available (otherwise
     X181's, with the tight-subset filter of critique 2).
  4. **Co-signing lag.** Measure the lag of its takes behind P4e / 0x2005d16a takes on the same token, and find the first
     dates of P4e and 0x2005d16a in these leagues.
  5. Detect change points in (offset, within-tick, in-round AUC, co-signing lag).
- **Data.** Activity (cached), Polygon calldata (a few thousand txs), tapes of the sampled markets, bo3 rounds for July-
  September maps, and P4e / 0x2005d16a calldata on those markets.
- **Signature if true.**
  - A change point D where the in-round AUC jumps from the print's level to about 0.9, together with the +30-65-ms
    co-signing and the offset change.
  - Or an intermediate version whose two-sided mid tracks a public source with a fixed lag, which decodes V's map from
    that source.

  D also dates the operator's subscription, which the information panel can match to a product launch or league
  coverage change.
- **Signature if false.** No week shows a private V before co-signing begins, and the two-sided mid sits at the print
  until D. The private value then arrives with the feed, as a step and not a gradual build. This is a quantified
  statement for the wall account.

### P4. Uncensor V with price-time priority: every public trade bounds its quote (strong form of X56, used for V instead of presence)

- **Hypothesis.** Its quote is observable far more often than its fills show. Under price-time priority, a public taker
  transaction that consumed liquidity on side X down to the price p_worst, without filling the wallet, proves that the
  wallet had no order on X better than p_worst at that match time. That is an upper bound on its top for that book. With
  the exact levels of its own fills, every book gets a dense interval-censored series of V.
- **Why it fits.**
  - X56 used fully consumed sweep levels only as a presence label (AUC about 0.66-0.72).
  - The validated X44 / X57 engine (88% of its maker shares assigned to the right transaction) already implements
    price-time priority, mint matching included.
  - The in-round and reaction-time questions (P2) are limited by sparse filled bursts (critique 2: many segments have
    two bursts).
- **Test.**
  1. Run the X57 engine over all 79k public taker txs of 16-22 Oct with the wallet's orders as "ours". Per transaction
     and book, emit an exact level (own fill), an upper bound (consumed without the wallet), or nothing.
  2. Fit a censored (Tobit-type) piecewise-constant V per book, with changes allowed on the 504-ms grid and at event-path
     times.
  3. Re-run the in-round drift and its reaction latency at bound resolution (with P2's clock).
  4. Measure how often a bound binds, i.e. is within 1c of the next exact level.
- **Data.** calldata_pub (79k txs), calldata_all and the engine code (code/iter4 / iter5); no new fetch.
- **Signature if true.**
  - Bounds bind on >= 30% of public sweeps, so observations of V per round rise 5-10x.
  - The timing of its moves relative to round ends sharpens to a few seconds.
  - The examiner also gets a historical V path for the burst-set unit.
- **Signature if false.** Bounds rarely bind (the wallet sits far below the swept prices). Its quote then stays censored
  between fills, and the fill record is the measurement ceiling. That is worth stating in the wall account.

### P5. The examinable historical price rule: one event value transported through the series map and the complement (strong form of X137 / X152 / X173)

- **Hypothesis.** On h1 / h2 the best honest price anchor is own state. It is better than per-token persistence (0.500)
  when it uses the facts established above:
  - V is one map value, and the match book follows series(V) (critique 1);
  - the two tokens of a book sit about 1c either side of V (pair sum 0.97-0.98);
  - orders take the slots V..V-4.

  The freshest own fill on ANY book of the event, published on chain before the signing, therefore predicts the new
  order better than the same token's last fill.
- **Why it fits.**
  - Critique 1 (slope 1.05 on s x dV_map).
  - Iteration-13 finding 10: the slot profile is 116 / 57 / 35 / 16 / 11 / 3.
  - X137: own previous level 0.543 on quiet orders, K - complement 0.315 because the complement's fill is stale.
- **Test** (VALIDATE, historical; reported as own state).
  1. For each maker order, take every wallet fill in the event with block time before sign_ms. Map each to the order's
     book and token:
     - same book: identity or K - p (K per event from BUILD);
     - map to match: series(V_map; maps won, the other maps' prior from the pre-game match price);
     - match to map: the inverse.
  2. Use the freshest mapped value. Predict the order at V - 1c, since a prediction of V - 1c covers V, V - 1c and V - 2c
     within one tick. Report V as well.
  3. Score within one tick against persistence (0.500), the last print (0.305-0.322) and the touch rules, by class
     (quiet / follow / message / repair).
- **Data.** orders.parquet, calldata_all, bo3 map results; no new fetch.
- **Signature if true.** >= 0.60 within one tick on VALIDATE, with a gain over persistence whose bootstrap interval is
  above 0. That is the best examinable historical price rule, tagged own state, and the measured remainder (V's moves
  between own fills) is the private share of the price item.
- **Signature if false.** No gain over per-token persistence. The private value then moves between fills on all books at
  once, and the price item's wall share is about 50 points.

## Overlap with the ledger, the catalog and the other panels

- **P1.** New. Existing: X114 (0x2005d16a's non-esports fan-out), X130 (the wallet's titles), X176 (esports sibling
  census), X184 (LoL), X188 (GRID CS2). Nobody has decoded the operator's football / MLB / NHL / ITF quoting.
- **P2.** Existing: X160 steps 1-3 (pause-aware DP clock, not run), X171 / X181 (print-HMM clock), X164 (rounds-book
  clock, live), X180 step 2 (co-mover clock). New: evidence that the print clock straddles rounds in about half the
  segments, the lower-envelope anchoring on all event markets, and the kill-state vs early-result discriminator.
- **P3.** Existing: C4 (the wallet's versions), X185 (June vs late September only). New: the July-August two-sided
  quotes as an uncensored V, the August gap, and change-point dating against co-signing and in-round AUC.
- **P4.** Existing: X56 (sweep probes as presence labels), X44 / X57 (the engine). New: bounds from every public trade
  as interval-censored observations of V.
- **P5.** Existing: X137 / X152 (per-token persistence 0.50), X67 (K - L after takes), X173 / finding 5. New: the series
  map, cross-book transport and the slot-shifted prediction.
- **Negative checks, so nobody redoes them:**
  - the token-mix control of finding 18 (critique 2);
  - the period and phase of the historical loop (critique 4);
  - size step-ups against merges and against new books (critique 5);
  - bo3 `begin_at` as an absolute clock (critique 3).
