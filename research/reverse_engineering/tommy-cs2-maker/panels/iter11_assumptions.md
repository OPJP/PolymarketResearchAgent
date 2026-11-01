# Panel, iteration 11: assumption breaker (fresh eyes)

Written 2026-11-01 about 06:30-07:40 UTC, inside the development block 11-01 06-12. Nothing sealed was opened. All
numbers below come from development tables:
- `ledger_rows_iter10`, `calldata_all` and `calldata_pub` (16-22 Oct; every block is below the H boundary block
  96,005,476);
- `own_bursts_dev` and `linked_adds_dev` (BUILD-live, 10-31 14:50-17:56);
- the shared `sports` feed for 10-31 13:00-18:00, read through `iter_live`.

My scripts are in the session scratchpad: `attention.py`, `xevent_sync.py`, `xevent_pairs.py`, `live_xevent.py`,
`phase.py`, `sibling_level.py`, `limit_anchor.py`, `post_take_drift.py` and `sports_cadence.py`. Each process stayed
under 300 MB.

What I read:
- BRIEF.md;
- NOTES iteration 11 in full, plus the earlier findings that each proposal depends on;
- state.json (all 157 X items, the non-X catalog, the progress gauges);
- FINAL_RULE.md;
- panels/iter10_assumptions.md in full, and the proposal headings of every earlier panel.

## Where the gap is

Selection passes on VALIDATE. Price (0.305 historical, 0.42-0.45 live) and outcome fail. Iteration 11 turned both
failures into wall components:
- "even with V known, slot choice caps a per-order rule at 0.71-0.75";
- "outcome out of reach at the 2-s latency even for an oracle copy".

I think both statements rest on conventions rather than measurements. "V is private" is also proven for CS2 only,
while the forward exams will be about half Dota by order count. The remaining external test (Thunderpick through
bo3) is designed in its weakest form.

## Checks (so nobody redoes them)

**A. No single-attention signature in the maker's valuation.** Units are the wallet's filled maker orders of 16-22
Oct, grouped into bursts (orders within 50 ms on one event); there are 14,179 quiet-class bursts. Pairs of quiet
bursts on DIFFERENT events, against ±20-60-s shifts:

| Window (ms) | 100 | 250 | 500 | 1,000 | 2,000 |
| --- | --- | --- | --- | --- | --- |
| Observed / shifted | 1.26 | 1.09 | 1.09 | 1.10 | 1.00 |

There is no deficit, so one person valuing concurrent matches is excluded. A desk with one trader per match is not
excluded.

**B. There is no batched or polled multi-match value source.**
- Historical, in fine lags: [0, 10) ms 34 pairs against 11.8 (SD 1.6), or 2.9x; [10, 25) 1.2x; [25, 50) 1.1x;
  [100, 250) 0.87x.
- The coincident pairs carry price changes in both events. One is a CS2 / Dota pair in the same millisecond (10-22
  15:19:08.098). The excess, however, is about 22 pairs in 14,179 bursts (0.15%).
- On the uncensored BUILD-live own bursts (2,998), cross-event coincidences within 10 ms are 0 adds against 0.4 at
  shifts, and 4 bursts against 5.0.
- The historical excess is a shared processing step (an event-loop flush), not an odds snapshot that re-prices every
  match at once.

**C. No wall-clock polling phase.** Rayleigh z ≤ 3.3 for every period from 0.1 to 300 s, on the quiet bursts (14,179)
and on all bursts (19,401).

**D. The merge-law sibling is not a public copy of V.**
- The sibling is 0xf1f2b3c6: 91.9% merge-law adherence, buy-only, whole-cent, in 63 of the wallet's events.
- Within 1c of its latest filled BUY on the same token, signed 20 ms-20 s before the wallet's order: 0.468 (618 rows;
  the last print scores 0.309 on the same rows).
- Ten other makers score 0.42-0.66 on the same measure (0xe8e1b119 0.657, 0xaeb90af4 0.643). All of these figures are
  co-fill selected.
- Only 29 of its orders are synchronous with the wallet's (±60 ms).
- Same software does not mean the same valuation.

**E. Other takers' FAK limits are worse anchors than the last print.** The anchor is the latest non-wallet taker BUY
limit that was on chain before signing (≤ 30 s; block time interpolated from `calldata_all`).

| Class (VALIDATE) | Same token, limit - 0..3c | Complement, 0.98 - limit | Last print |
| --- | --- | --- | --- |
| quiet | 0.23-0.31 | 0.15 | 0.38 |
| follow | 0.12-0.17 | 0.11 | 0.17 |
| msg | 0.10-0.13 | 0.14 | 0.17 |

Coverage is 55-65% of orders. The informed limit carries no more public value than the stale print. (Not filtered to
group P.)

**F. No timer-driven value path after its takes.** This is the post-plant "bomb timer" form. Own maker steps in the
bought direction (bought token up, complement down):

| Window after the take | 1.1-5 s | 5-15 s | 15-45 s | 45-120 s | Shifted control |
| --- | --- | --- | --- | --- | --- |
| Share of steps | 0.596 | 0.502 | 0.505 | 0.498 | 0.471 |

Only the 1.04-s repair window shows a direction.

**G. No event class in which it quotes a public value.** The last-print within-1c share per event (73 events with
≥ 50 filled orders) has mean 0.29, SD 0.08 and range 0.08-0.46, and it is unimodal.

**H. The sports socket has no hidden round clock in its message timing.**
- For non-GRID CS2 games on 10-31 13-18, messages repeat every 20.26-20.41 s (median per game), with the round part
  constant at 000-000.
- The extra `turn` / `elapsed` / `sportradarGameId` fields appear only on college-football games.

**I. The weak form of P4 below is null.**
- On censored filled orders, the level jump at its own takes (`own_msg`, n 56) and at wallet-independent messages it did
  not take (`msg`, 654) is the same: |dp| q25 / q50 / q75 of 1 / 1 / 3c against 1 / 1 / 2c.
- Their offsets from the last print are also alike (p50 -6c against -7c).
- The strong form needs the uncensored book.

## Critique: what the investigation is taking for granted

### 1. "Structurally capped" price is a property of one unit, not of the strategy

The 0.71-0.75 ceiling holds for signing-time prices of every ladder add. The brief allows "orders (or fills)". At fill
time, 93% of its fill rows lie within 1c of its highest order hit in the same transaction (iteration 11, finding 3):
a decode of V alone would score about 0.9 on that unit.

The wall account should therefore say that the price item fails because V is private. It should not say that the ladder
makes the item impossible. Which unit the examiner scores is the user's call, and it should be asked, not assumed.

### 2. "Outcome out of reach whatever the decode" depends on two conventions

**First convention: where the 2-s latency applies.** The brief attaches "latency >= 2 s" to the held-out return. Target
item 5 asks only for strict fills.

**Second convention: which book is replayed.** At L = 2 s:

| World | VALIDATE (Pearson / Spearman) | BUILD |
| --- | --- | --- |
| T_lo (the observed book) | 0.431 / 0.404 | 0.233 / 0.357 |
| T_hi (a book where the rule replaces the wallet) | 0.709 / 0.635 | 0.686 / 0.505 |

- T_lo is the observed book, which the wallet's own FAK has already emptied (median residual 0 after its match). There
  the oracle copy fails.
- T_hi passes at 2 s.
- T_hi's only untested assumption is that the stale makers do not cancel in (m, m + L]. That can be measured, because
  80% of the informed bursts have no wallet take (P2).

### 3. "V is private" is proven for CS2, but the forward exams are half Dota

- The investigation's own alignment puts the feed's Dota messages on the public spectator clock. Valve publishes that
  state key-free every ~4 s (X118).
- The only level test (X123) used a generic outcome-trained logistic on per-minute OpenDota leads. It did not use an
  inverse fit of the wallet's own levels.
- On the 10-31 block, Dota is 54% of TRADE rows. Its last-print anchor (0.431) already beats CS2's (0.305).

"Dota's V is private" has not been tested. Nor has "one model serves both titles".

### 4. The last external CS2 candidate is tested in its weakest form

The frozen X144 tests use the following:
- value agreement;
- the wallet's maker FILLS (censored), on the MATCH market only;
- a relay cached up to 15 s (`max-age=15`).

A shared upstream (an odds supplier's event feed) shows up first in timing. A bookmaker suspends in play at the events
its feed reports, and the recorder already stores the active flags. Value agreement can fail under a shared vendor
whenever the wallet prices with its own model (E1).

### 5. The kind filter on the taker was never tested against the wallet's own value

- "No edge-based decline" (X99) used public realized edge (later takers' shares at ≤ P4e's limit).
- The wallet reveals its own post-event value within milliseconds on the live book: its re-posted levels and K - L.
- Its untriggered private events are 2.6x its takes.
- Whether the take is "V_new - stale ask >= θ" has never been measured on that object. If it is, the strategy has one
  private input, not two.

## Proposals, ranked by the chance they close the gap

### P1. Dota's V as a learnable function of Valve's public spectator state: an inverse fit of the wallet's own uncensored levels (strong form of X123 / X118; new object, the level rather than the lag)

- **Hypothesis.** For Dota, the wallet's valuation is a deterministic map of public spectator-delayed game state:
  - net worth and XP leads, kills;
  - towers, barracks, Roshan / aegis;
  - buybacks and game time;
  - series state.

  X123 failed because its functional form was an outcome model, not the wallet's own map. The input is not missing.
- **Evidence.**
  - The feed's Dota messages sit on the 900-s spectator clock (`dota_feed_align*.json`).
  - The DotaTV relay set is broader than the feed's coverage (X117), so the vendor reads a public relay.
  - The X129 kill-lag spread leans machine-timed.
  - X123's model had in-sample outcome AUC 0.837 but scored 0.411 against 0.431 for the last print: a calibration or
    form mismatch, not proof of a missing input.
  - The forward mix is Dota-heavy.
- **Test.**
  1. **Historical first pass, runnable now.**
     - Data: the 6 Dota maps of 10-22 (1,292 orders). OpenDota per-second kill and objective logs plus per-minute
       gold / XP. The clock per map comes from P4e's takes only (finding 24).
     - Fit the wallet's filled-order price on lagged state (monotone GAM or LightGBM, max_bin 63).
     - Leave one map out. Score within one tick against the last print and X123.
  2. **VALIDATE-live (any development block with Dota in play).**
     - From `tommy_dota_rt` at receive time (laptop offset corrected with the rolling server offset), build per-second
       state.
     - The target is the wallet's own top on each Dota token at every re-price burst. It is uncensored: calldata-linked
       10-share adds, with other 10-share makers removed by calldata.
     - Scan the lag (0-8 s). Fit on half the maps and score the other half. Report adds and fills against the touch,
       the last print, X123 and a ±60-300-s shifted-state null.
  3. Pre-register the features and the lag grid before the first block is read.
- **Data.** `dota_pub`, `dota_train_minutes`, `dota_v_anchor_rows` and `calldata_all` for the historical pass;
  `tommy_dota_rt`, `clob_wallets`, `linked_adds_dev`-style links and development-block calldata for the live pass.
- **Signature if true.**
  - Dota fills within one tick ≥ 0.65 and ≥ touch + 0.15, collapsing under shifted state.
  - The best lag equals the feed's lead over the snapshot (X118 (a)).
  - Consequence: the pooled forward price item rises by about 0.1-0.15 at the 10-31 mix. The Dota half becomes a
    public-data rule, and V is "a public model of public state" in one title.
- **If false.** "V private beyond public game state" extends to Dota with a measured ceiling. That is the strong form
  auditors will ask for.

### P2. Strengthen the Thunderpick test before its first development record: suspension timing as the event clock, uncensored levels, map lines (strong form of X144 / X133; an add-on pre-registration, not a change to the frozen file)

- **Hypothesis.** Group P's vendor is (or supplies) an in-play odds operation. Its event stream drives the bookmaker's
  suspensions and the wallet's re-pricings, even when the wallet prices with its own model.
- **Evidence.**
  - The selection is a vendor-coverage boundary (non-GRID, tiered, not organiser-level).
  - The feed carries raw events and no shared odds value (X105 / X139), which is exactly what an odds vendor's event
    feed looks like to a client.
  - The current tests can miss a shared vendor: value agreement, censored match-market fills, a 15-s cache.
- **Test** (development blocks only).
  1. **Markers.** From the P records (per-match object, 2-s round robin), take suspension starts and ends (a1 = a2 = 0
     and back) and re-open coefficients. The wallet's private-event markers are:
     - its takes (calldata);
     - validated untriggered own pulls and re-price bursts (no public event on any book of the event in 300 ms);
     - group-P takes.
  2. **Timing.** The share of suspension starts with a wallet marker in [s - 20 s, s + 2 s], and the share of markers
     followed by a suspension within 20 s. Null: 2,000 within-match circular shifts. Estimate the relay lag from the B
     vs P cadence.
  3. **Kind.** Are suspensions with no wallet marker followed by group-P takes (round wins: the kind it does not
     receive)?
  4. **Level.** At each re-open, compare the TP prop / lay price with the wallet's uncensored own top 0-30 s after its
     marker, on the match market and on map markets when bet_updates carries map lines.
  5. **Verdicts** (written before the first matched development record):
     - shared vendor iff timing ≥ 3x the null at p < 0.0025;
     - E4 (value) iff the level is within 1c on ≥ 0.6 of re-opens.
- **Data.** `tommy_tp_odds2` (P / B / U), `tommy_cs2_near` / `clob_wallets` with the validated own label, calldata of
  the block.
- **Signature if true.**
  - Suspensions lag the wallet's markers by a constant close to the relay lag, at ≥ 3x the null.
  - Suspensions it lacks are taken by group P.
  - If the levels also match, V has a public lagged form for CS2 (the only route found for the CS2 price item). If only
    the timing matches, the vendor is identified, E1 is refined to "own model on a supplier's event feed", and the
    suspension clock is a public lagged proxy of the private clock for future-block timing items.

### P3. Measure the counterfactual stale remainder on wallet-absent informed bursts, and fix the outcome conventions before the wall account (strong form of X155 / X149 step 2 / finding 7)

- **Hypothesis.** Without the wallet's own take, the stale makers' orders at ≤ an informed limit survive for at least
  2-3 s after the leader's match. Then T_hi is the realistic replay, and the outcome item is reachable at 2 s with a
  V + take decode.
- **Evidence.**
  - Finding 7 measured the remainder only at the wallet's own takes, where its own FAK consumes it (median residual 0).
  - Depth at its limit was flat over the last ~200 ms before its match (0.145 of the signing depth).
  - T_hi passes at 2 s; T_lo fails.
  - 80% of the informed bursts have no wallet take (census), so the counterfactual is observed directly.
- **Test.**
  1. **Historical (16-22 Oct; `census_bursts` label wallet-absent vs wallet-led / near, `calldata_pub`,
     `calldata_all`).**
     - For each burst: leader limit L, leader match m = sign + 1,040 ms.
     - Measure the shares that later takers obtained at prices ≤ L, by their match time in (m, m + 4 s].
     - Match wallet-absent and wallet-present bursts on move10, the leader's size and the pre-burst depth (from the
       pack's own fills).
     - Wallet-absent bursts give a lower bound on survival (only liquidity that someone actually consumed).
  2. **Live (VALIDATE-live; needs X115's leader takes on recorded books).** Depth at ≤ L with own levels removed, from m
     to m + 3 s, at group-P-only bursts.
  3. **Re-run X155.** Replace T_hi's no-cancel assumption with the empirical survival curve (T_emp) and report the
     oracle copy at 2 s.
  4. **Ask the user** in the return:
     - Is item 5 scored at the 2-s latency or only with strict fills?
     - Does the examiner's replay remove the wallet's own orders from the book?
- **Data.** `census_bursts`, `pack_orders` (rebuilt census version), `calldata_pub`, `latency_bound_markets`; the
  recorded books of later development blocks.
- **Signature if true.** In wallet-absent bursts, ≥ 50% of the liquidity at ≤ L that the wallet takes in matched
  wallet-present bursts is still consumed by takers matched at m + 2-3 s, and T_emp at 2 s is ≥ 0.5 / 0.5. The
  investigation must then drop "unreachable whatever the decode". The outcome wall becomes "unreachable without V and
  the take", which is a different and weaker claim.
- **If false** (survival about 0 by m + 1-2 s even without the wallet). T_lo is the world, and the latency component of
  the wall stands with evidence that auditors cannot dispute.

### P4. One latent value, two legs: the take as a threshold on the wallet's own revealed V against the stale ask (strong form of X99 / Y1 on the uncensored own levels; a reduction of the open inputs from two to one)

- **Hypothesis.** It takes iff V_new - (stale best ask) ≥ θ. Here V_new is the post-event value that it reveals by
  re-posting within milliseconds. The "plant / turn kind filter" is what that threshold looks like through public
  proxies.
- **Evidence.**
  - Its untriggered private events are 2.6x its takes (X94).
  - The premium scales with the expected repricing (+0.87c of 10-s move per 1c, X45).
  - The repair sits at K - L (X67).
  - The legs correlate -0.87.
  - X99's null used public realized edge, which includes followers' behaviour, not its own value.
  - The censored historical view (check I) has no power: its levels after takes and after non-taken messages are alike
    on filled orders.
- **Test** (BUILD-live, then VALIDATE-live).
  1. Markers: own takes, and validated untriggered own pulls or re-price bursts.
  2. At each marker:
     - V_before = its own top on token X and on the complement;
     - V_after = its first re-posted top within 1.5 s (complement: K - top);
     - dV, and gap = V_after_X - others' best ask on X at the marker.
  3. Fit take ~ gap (+ |dV|, depth at the ask) on BUILD-live. Report the AUC on VALIDATE-live with an event bootstrap,
     against X99's kind proxy (the previous burst's team) and a shuffled-marker control. Then check the premium
     (limit - ask) against gap on its takes.
- **Data.** `level_events_dev`, `linked_adds_dev`, `own_bursts_dev` and calldata (BUILD-live); the same tables on the
  development blocks of 11-01 and later.
- **Signature if true.**
  - AUC ≥ 0.85 with a sharp θ.
  - Non-taken markers have gap < θ.
  - The premium rises with gap.
  - The taker leg is then decoded given V, and both price and outcome reduce to the one private input V.
- **If false.** Takes are not separable by its own value. The wall account then needs two private inputs: a
  kind-labelled event stream and a valuation. That is the stronger statement, and today it is assumed, not measured.

### P5. The valuation half of X2 was never tested: a clock-free fit of CS2 V to a round-state model (strong form of X2 / E2; NOTES iteration 1 "the Markov valuation itself is untested")

- **Hypothesis.** Between in-round events, its CS2 V is a round-state valuation:

      P(map win | round score, side, map, pre-map strength)

  It is propagated to the match by the series formula. The feed is only the CLOCK, so the private part is when, not
  what.
- **Evidence.**
  - The quiet class (70.6% of orders) is the part no message explains.
  - My quick check on its 16-22 Oct quiet-class level steps: the share that moves toward the last print is 0.43 at
    0-2 s since its previous order, 0.52 at 2-10 s, 0.62 at 10-60 s and 0.79 beyond 60 s. At short gaps the steps lead
    the print; at long gaps the print catches up, as a leading value would do.
  - Its match / map levels are coherent (series sensitivity).
  - X2 was closed only for lack of a public round clock, not on the model.
- **Test** (16-22 Oct, runnable now).
  1. Data: the 95 maps of `round_align_maps` with bo3 round-winner sequences.
  2. Hidden state: the round index k(t), non-decreasing over the map.
  3. Emission: its filled-order level on the map token ~ N(M_k + μ, σ²), where M_k is a standard MR12 / overtime Markov
     value with the round-win probability fitted to the pre-map last print.
  4. Prior: round durations 60-140 s. Fit with Viterbi / EM per map.
  5. Compare:
     - the true sequence against 200 permuted sequences with the same final score;
     - the same alignment of the public last print (control);
     - the residual SD at the aligned round starts (freezetime).
  6. Pre-register: round-state V iff the true sequence beats ≥ 99% of the permutations for V, σ_V ≤ σ_print - 1.5c,
     and the freezetime residual SD ≤ 3c.
- **Data.** `round_align_maps`, `bo3_taker_rounds`, `ledger_rows_iter10`, the tapes (last print in `a_last`).
- **Signature if true.** V's plateaus sit on the Markov table and the print's do not. The decode then names V's model,
  and the private part is reduced to the round clock. On future blocks, the round-handicap / total-rounds books
  (`tommy_cs2_rounds`) and the chat clock (X38) are candidate public lagged clocks.
- **If false.** V is not a score table even between events. That supports E1 (an in-round model) with a measurement
  rather than by default.

## Notes for the wall account and overlap

- **Unit-specific claims.** The price cap and the outcome bound are unit- or convention-specific. Report:
  - price per order at signing (0.71-0.75 with V known), and per fill at fill time (about 0.93);
  - outcome under T_lo, T_hi and T_emp (P3), at the latency the user confirms.
- **"Private" is title-specific until P1 runs.** Write "CS2 V private against every public and second-venue series
  obtained", and keep Dota open.
- **Overlap.**
  - P1 strengthens X123 / X118 (level instead of lag; inverse fit instead of an outcome model).
  - P2 adds the timing and level tests to X144 without touching the frozen file.
  - P3 strengthens X155 / X149 with the natural experiment and the convention question.
  - P4 is the own-value form of X99.
  - P5 is the untested valuation half of X2.
  - None duplicates an open item.
- **Negative checks A-I** close the following:
  - a single human valuer (attention);
  - a polled or batched multi-match value source;
  - wall-clock polling;
  - the merge-law sibling as a value copy;
  - other takers' limits as anchors;
  - a post-take timer path;
  - event-level regime pooling;
  - a hidden round clock in the sports socket's message timing;
  - the censored form of P4.
