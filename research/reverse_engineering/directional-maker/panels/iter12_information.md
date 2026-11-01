# Panel after iteration 12: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 12 in full, earlier iterations by search), state.json
(catalog with every X item, components, target metrics), FINAL_RULE.md and `iter11_information.md`. I did not read the
iteration-12 mechanics or assumptions panels, which are written in parallel.

Data I used, all development or released (h1 + h2):

- the RE's tables: `it12/typed_fills` (lot fills; VALIDATE only as aggregates), `b1_takers_{study,valid}` (taker order
  of every cluster fill transaction), `it12/maker_rows` (the 1,056-window maker-row sample, 10-09..30), `fut1s`
  (Binance USD-M 1-s, 10-23..30), the Chainlink endpoint caches `cl/*` (filtered with `sealed.is_sealed`, nothing after
  10-31 18:00), and the lot taker tapes `exam/taker5m_day_*`;
- five single requests to `polymarket.com/api/crypto/crypto-price` for the 10-20 12:00 UTC window (XRP, DOGE, BNB,
  HYPE, ETH).

I did not open `.cache/live/sealed/`, any sealed block, any other strategy's workspace, or any record after
10-31 18:00. I did not connect to any live websocket, because the current block (11-01 00-06) is sealed. Scripts:
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i12/`
(`taker_runs.py`, `burst_sign.py`, `burst_move.py`, `onesided.py`, `onesided2.py`, `persist_inputs.py`, `fade_mid.py`,
`twap_side.py`, `strike_race.py`, `cl_noise_day.py`). The other checks were inline.

## What my checks found

Unit: one taker transaction that fills the cluster in a BTC 5m window ("event"; 1.07-1.09 cluster fills each). Events
are ordered by block second and the taker's signing ms. STUDY first, VALIDATE second.

**C1. The "same-side runs" are not taker campaigns: 94% of consecutive cluster fills come from different takers.**

- The same taker fills the cluster twice in a row in only 6.0% / 6.3% of consecutive pairs.
- Probability that consecutive events are on the same outcome:
  - same taker: 0.986 / 0.987;
  - different takers: 0.922 / 0.925.
- Different-taker pairs, by gap in block seconds:

  | gap | STUDY | VALIDATE |
  | --- | --- | --- |
  | < 1 s (same block) | 0.997 (3,812) | 0.995 (14,080) |
  | 1-3 s | 0.989 | 0.980 |
  | 3-10 s | 0.886 | 0.872 |
  | 10-30 s | 0.767 | 0.734 |
  | >= 30 s | 0.527 | 0.520 |

- Bursts (same window and outcome, gaps < 3 s): 2,526 / 7,304. Bursts of 3 or more events hold 72% / 79% of the fills.
  They have a median of 4-5 events from 4 distinct takers, and the median block span is 1 s.
- Inside a burst the takers' signing times spread over a median of 12 s / 23 s (IQR 2.2-132 s / 2.6-190 s). A burst is
  not one common taker trigger. It is several unrelated takers hitting one cluster rung inside one or two blocks.

**C2. The cluster is filled on one outcome per second while the takers in that second go both ways.**

Maker-row tapes, every second with a cluster maker BUY fill (BUILD 3,494 s, STUDY 553 s, VALIDATE 1,854 s):

- The cluster is filled on both outcomes in the same second only 19 / 7 / 9 times (0.5-1.3%).
- Opposite flow is takers buying the outcome the cluster did not buy: maker BUY of that outcome, or maker SELL of the
  cluster's outcome. In the cluster's one-sided seconds, it is on average 0.43 / 0.41 / 0.42 of the other makers' fills
  (0.32 / 0.31-0.35 / 0.28 by shares). The figure is 0.50 in seconds without a cluster fill.
- The figure is the same for windows starting at 02, 08, 14 and 20 UTC (0.426-0.434), so it holds in both sessions.
- Two-way taker flow reaches other makers on the other outcome while the cluster gets none of it. So the cluster's quote
  sits at only one outcome's touch in each second. This fits the 0.88 pair sum of its top rungs (X30).
- **The fill side after entry is therefore the cluster's own quote state, not the takers' choice.** Iteration 12 read the
  switches between runs as "taker-chosen switches that no public input predicts". That reading does not hold. They are
  switches of the cluster's quote, whose input has not been found.

**C3. The quote state has a memory of about 25-30 s. It is stickier than the posture at short gaps and reverses at long
gaps.**

VALIDATE, all consecutive event pairs (the same within 0.02 in the 12-21 UTC session and outside it):

| gap | cluster side | posture of the same events |
| --- | --- | --- |
| < 1 s | 0.995 | 0.988 |
| 1-3 s | 0.981 | 0.895 |
| 3-10 s | 0.874 | 0.850 |
| 10-30 s | 0.735 | 0.759 |
| 30-60 s | 0.581 | 0.681 |
| > 60 s | 0.445 | 0.607 |

- The excess over chance decays like exp(-gap / ~26-30 s).
- When the cluster switches outcome, the posture flips in only 0.33-0.34 of cases (0.06-0.07 when the cluster stays).
- The cluster ignores the posture's 1-3 s flips (0.98 against 0.90). Beyond 60 s it reverses more often than chance
  (0.445). The pairing leg would produce that reversal.

**C4. At decision points the own-state composite is the better description; the own-history baseline only wins inside
bursts.**

Burst starts by the gap since the cluster's previous fill in the window. "Composite" is my approximation of R8's
own-state branch: decided -> cheaper; no position -> posture; schedule size -> held outcome; other sizes -> under-held
outcome.

| gap | previous side | composite (own state) | public R8 |
| --- | --- | --- | --- |
| 3-10 s | 0.889 / 0.874 | 0.769 / 0.781 | 0.523 / 0.650 |
| 10-30 s | 0.769 / 0.735 | 0.741 / 0.741 | 0.498 / 0.622 |
| >= 30 s | 0.531 / 0.522 | **0.669 / 0.649** | 0.509 / 0.590 |

- The own-history baseline (0.82 per fill) is mostly the same-block clustering of C1.
- After a pause of 30 s or more, the held-outcome / under-held composite beats it by 0.13-0.14 on both halves.
- Withdrawing the composite as "only fill persistence" was correct for the per-fill count. On the decision unit, the
  burst start, the inventory policy is real.

**C5. Every tape-only reference stays at ~0.69 on the block clock (VALIDATE per event; STUDY in brackets).**

- Posture (frozen): 0.687 (0.570).
- Against the Binance futures move over the last 30 / 60 / 120 s: 0.632-0.673 (0.51-0.58). This is mostly the
  cheaper-token direction.
- A fade of Polymarket's own price (mean of clean prints over the last 10-120 s vs the last print):
  - alone: 0.642-0.692 (0.53-0.55);
  - plus the Chainlink edge: 0.691-0.705 (0.54-0.57).
- At burst starts (gap >= 10 s), the outcome favoured by the last 1-4 s futures move (|move| >= $5): 0.545 on 1,603
  bursts (0.606 on 548).
- Strike race:
  - The Gamma TWAP strike and the Chainlink value stamped at the open differ by a median of $12.
  - Where the two postures differ, the open-stamp strike wins only 0.23-0.40 (442-1,098 fills, 28-76 windows per cell).
  - The engine uses the correct strike. No gap there.
- TWAP-60 race (my 60-s mean of the endpoint values; 39 VALIDATE windows covered by X102 so far):
  - where the TWAP-60 posture and the current-report posture disagree, the TWAP-60 posture wins 0.76 (91 fills, but only
    11 windows and 20 bursts);
  - on STUDY it loses (8 fills).
  - Inconclusive. X91 rejected the TWAP topic for the live US-session 500s.

**C6. The Chainlink noise regime starts on 10-30 afternoon, four days after the deep-bid ramp (X105, partly
answered).**

- Lag-1 autocorrelation of 1-s Chainlink changes, from the endpoint caches (consecutive-second triples):
  - +0.06 to +0.47 on every day from 10-13 to 10-30;
  - by hour it first turns negative at 10-30 15:00 UTC (-0.26, -0.04, -0.22, -0.14, then +0.14 at 19:00);
  - it is -0.35 to -0.51 from 10-30 23:00 and in every development hour of 10-31.
- The regime therefore cannot explain:
  - the 10-26 deep-bid ramp;
  - the 10-25/26 entry-multiplier step.
- It is a 10-30/31 event only. It matches the ad-hoc 10-31 switch-off (X89).

**C7. Data checks.**

- `crypto-price` serves Chainlink values for XRP, DOGE, BNB and HYPE (HTTP 200, `completed: true`; 10-20 12:00 UTC),
  as well as BTC, ETH and SOL.
- The shared recorder subscribes the RTDS Chainlink and TWAP topics for btc, eth and sol only (`live.py` `COINS`).
- The cluster's whole history has substantial XRP and DOGE 5m/15m volume (rows to 10-08):

  | family | rows |
  | --- | --- |
  | doge-15m | 41.6k |
  | xrp-15m | 28.4k |
  | doge-5m | 23.8k |
  | xrp-5m | 23.3k |

- C7 recheck: 0 of 33,749 lot fill transactions have a cluster taker against a cluster maker.

## Critique

1. **The after-entry side was closed on the wrong reading.**
   - C2 shows the takers are two-directional in the very seconds the cluster is filled on one outcome. The cluster
     chooses which touch it occupies.
   - So "one public decision per window, then taker-chosen switches" (X129) should be restated: one entry decision,
     then quote-state switches whose input is unknown.
   - That input is the largest public gap left on the side.
2. **The per-fill unit hides the decisions.**
   - 72-79% of the fills sit in multi-taker bursts that last one or two blocks.
   - The per-fill side, the own-history baseline and the composite are all weighted by burst size.
   - At burst starts the ranking reverses (C4). The side should be reported per burst start as well. That count (7,304
     on VALIDATE) is the number of quote decisions the side rule must get right.
3. **The centre race never had Polymarket's own book in it.**
   - X27 / X41 raced exchange feeds, Kalshi, Deribit and Bitstamp.
   - X47(b) (ex-cluster depth-weighted mid, microprice, complement-implied mid) did not run.
   - Chainlink explains ~21% of the skew variance. Every tape-only reference stops at ~0.69 (C5), so the missing input
     is either in the book or in own state.
4. **The yardstick is the historical block clock, but the next exams run on recorded blocks.**
   - Live (one Saturday US-session block) the public side is 0.79-0.84 per fill. On the lot it is 0.69.
   - The off-session ladder (half of the fills) has never been observed in a recorded book. The shared recorder starts
     at 10-31 12:00.
   - The first recorded weekday off-session development block is 11-02 00-06 UTC.
   - The only multi-day book history for the off-session hours is pmxt (07-16..08-10, X87), which has only been piloted.
5. **The next future exam is likely to fail on scope, and the data to fix it is not being recorded.**
   - The sealed blocks since T0 that the next exam will take include 10-31 18-24 and 11-01 00-06.
   - These are weekend evening and night blocks after the 10-31 16:53 BTC 5m switch-off.
   - R8's universe (BTC 5m + 15m) holds >= 80% of trades and dollars in only 34% of 6-h blocks (0% of weekend 00-06
     blocks).
   - The family-general universe needs settlement streams for XRP, DOGE, BNB and HYPE. The shared RTDS recorder does not
     subscribe them (C7), while the historical endpoint serves them.

## Proposals (ranked by the chance they close the gap)

### I12-1. Read the one-sided touch state per second from the recorded books, and race Polymarket's own book state on it (strong form of X47(b), X27/X41, X71 and X128 extended from the entry to every switch)

- **Hypothesis.** The fill side is S(t), the outcome whose touch the cluster's top rung occupies. S(t) =
  sign(F(t) - mid(t)), where F is the ladder centre. Besides the Chainlink edge (~21% of the skew variance), F carries
  one of the following:
  - (a) ex-cluster book state: the microprice (size-weighted touch) or the top-3 depth imbalance of each outcome's book,
    or 1 minus the complement book's microprice;
  - (b) a re-price-pass hysteresis: S changes only at a re-price pass whose edge change exceeds theta. This would give
    the 1-3 s stickiness and the 26-30 s memory of C3;
  - (c) the cluster-level inventory: own state, reported separately (C4 says it carries the long-gap decisions).
- **Why it fits.**
  - C2: one-sided per second with two-way takers.
  - C3: a memory that matches neither the posture nor any Binance momentum.
  - C5: every tape-only reference stops at ~0.69.
  - X47(b) never ran. The race has never seen the book the engine quotes into.
- **Test.**
  1. Data:
     - 10-31 12-18 (the shared `clob_crypto` trades and books, `dm_clob_raw` / `clob_raw2` price_change events with
       server ms, `dy_rtds` publishes, `btc5m_bnfut`);
     - then 11-01 18-24, 11-02 00-06 (the first recorded weekday off-session block) and 11-02 12-18 (`dx_clob` full
       depth).
  2. Per 100-ms step, S(t) is in {Up, Down, none}. It is set by a cluster-class exact-size rung (500 / 250 / 62 / 2^k
     schedule, calldata ownership) at each outcome's touch. Subtract the cluster's identified rung sizes from the book
     before computing any book feature.
  3. Inputs:
     - (a)'s book quantities;
     - the Chainlink edge at the publish clock;
     - the futures change since the last report;
     - clean taker flow over 1-10 s;
     - the RTDS TWAP-60 edge;
     - (c) separately.
  4. Fit on 12:00-15:00 and score on 15:00-18:00. Freeze the model, then score it on every later development block.
     Report, per second, per burst start and per fill:
     - (i) the persistence profile of the fitted sign against C3's;
     - (ii) the share of S(t) switches preceded within 0-150 ms by each event: report publish, futures move, a
       book-state threshold crossing, or the cluster's own fill.
  5. Replicate (a) and (b) on pmxt (two sampled hours per day of 07-16..08-10, both sessions, with Binance as the stand-in
     reference; X87 pilot: about 67 MB of range reads per hour, reduced on the fly).
- **Data.** Recordings already on disk; the next development blocks; pmxt range reads (stream them, keep under 50 MB).
- **Signature if true.**

  | reading | signature |
  | --- | --- |
  | (a) | The book term adds >= 0.10 held-out R² to F - mid. Per-second S accuracy >= 0.85 and per-fill side >= 0.80 in both sessions, with switches >= 0.75. The side rule is then market-only and must be stated against the market-only baseline. |
  | (b) | A one-parameter hysteresis on the publish-clock edge reproduces C3's profile (0.98 / 0.87 / 0.74 / 0.58) and lifts burst starts to >= 0.75. |
  | (c) | Only the inventory term predicts the long-gap switches. Report it as own state. The public side remains the entry plus the decided branch. |

### I12-2. Record and fetch the settlement streams of every family the cluster trades, so that the universe can pass scope in the weekend blocks the next exam will use (strong form of X83 and X95 on the data side)

- **Hypothesis.** The same engine quotes XRP, DOGE, BNB, HYPE, ETH and SOL Up/Down windows with the same Chainlink
  posture. When BTC 5m is off, they carry most of the cluster's fills. A rule that has those streams can meet the
  0.80 scope bar in every block type. Without them the next exam fails on scope whatever the BTC side scores.
- **Why it fits.**
  - U1 meets the scope bar in 34% of blocks, U5 (all families) in 100% (X83).
  - The next exam's sealed blocks follow the 10-31 16:53 BTC 5m switch-off.
  - The endpoint serves XRP / DOGE / BNB / HYPE (C7).
  - The shared recorder subscribes only btc / eth / sol.
  - The family book recorder `dw_clob` has run since 10-31 22:59.
- **Test.**
  1. Start a small RTDS recorder with `live.py` `Writer`:
     - `crypto_prices_chainlink` and `crypto_prices_twap_sixty` with symbols xrp, doge, bnb and hype;
     - a hard stop at 11-03 00:00, under 100 MB;
     - recorded in `state.json` `live_lab`.
     Verify at its first development minute (11-01 06:00) that RTDS publishes those symbols. If it does not, record that
     and use the endpoint.
  2. For BUILD and the lot, fetch the endpoint values at the fill seconds (b - 4) of the cluster's fills in those
     families. Use the polite queue, after X102, and sample per family if the count is large.
  3. Score R8's components per family: the R3-class presence refitted, the posture side and the R7 in-block price.
  4. Compute scope per 6-h development block with the per-family universe frozen before any exam.
- **Data.** A few thousand endpoint requests per family; an RTDS recorder of a few MB; the `dw_clob` books; Gamma
  listings.
- **Signature if true.**
  - The family-general universe holds >= 0.80 of fills and of |PnL| in every development block type, including weekend
    00-06.
  - Each family's posture side and in-block price stay within 3 points of BTC's.
  - If one family breaks the pattern (for example DOGE with no skew), that family is the next decoding target.

### I12-3. The burst start on the lot's millisecond clock: which public event puts the cluster at one touch (historical complement to I12-1; strong form of X10 and X110 on the burst unit)

- **Hypothesis.** Each burst starts when the cluster's rung reaches one outcome's touch. One of three things causes it:
  - (i) the cluster re-posts after a futures move or a Chainlink report (side = the outcome the move favours);
  - (ii) the market moves into a resting rung (side = against the move since the last re-price pass);
  - (iii) no public event (a timer, or an inventory-driven re-post).
- **Why it fits.**
  - C1: bursts last one or two blocks.
  - At 1-s resolution the last 1-4 s futures move gives 0.61 STUDY / 0.55 VALIDATE at burst starts. That is too coarse
    to separate (i) from (ii).
  - The lot has 7,304 VALIDATE burst starts. The live blocks will need weeks to match that.
- **Test.**
  1. Match time per burst start:
     - the in-block execution position (`it11/inblock_blocks_all`);
     - the taker's signing ms + ~620 ms (X97 calibration; clipped as in X97).
  2. Binance USD-M aggTrades daily archives for 10-23..30:
     - download one day at a time into `.cache/re/directional-maker/`;
     - verify the `.CHECKSUM`;
     - reduce at once to 50-ms bins of last price and signed volume;
     - delete the zip.
  3. Chainlink endpoint values: X102's 1-s / 2-s grids where they exist, b - 4 otherwise.
  4. Event study in [-3 s, 0] before each burst start, against continuation fills and against placebo times in the same
     windows. Use 25-ms bins for the futures move size and sign, and mark endpoint report changes and clean in-block
     print jumps.
  5. Classify each burst as (i) / (ii) / (iii) with thresholds frozen on STUDY, and score on VALIDATE (aggregate).
- **Data.** About 8 futures archive days, processed one at a time (disk peak about one zip); tables already on disk for
  the rest.
- **Signature if true.**
  - Class (i) or (ii) covers >= 50% of burst starts with side accuracy >= 0.80 on STUDY, and holds on VALIDATE.
  - A ms peak of futures moves at 50-250 ms before (i) starts (the live X10 re-post lag) that placebo times do not show.
  - Class (iii) bursts, with their share, become the quantitative unexplained remainder of the side.

### I12-4. The cluster's aggregate crypto delta across horizons and assets as the state behind entries and long-gap switches (cross-market own state; strong form of E9)

- **Hypothesis.** Iteration 12 found that the engine's state is the cluster position, not the wallet's. The next level
  is the cluster's whole book: every open BTC 15m / 1h / 4h / daily window and the correlated ETH / SOL / XRP windows,
  summarised as a delta Δ = Σ_w q_w ∂fair_w/∂S. The BTC 5m side at entries and at switches after a pause hedges or adds
  to Δ.
- **Why it fits.**
  - E9 used only the overlapping 15m position. It found a sign that flips between the halves:
    - the entry follows it 0.70 on STUDY;
    - where the two disagree, the 15m position wins 0.35 on VALIDATE.
  - The entry multiplier flips between the halves in the same way. A hedge against a changing mix of other horizons
    would produce both flips.
  - C4: after pauses of 30 s or more, own state carries the decision (0.65-0.67) while public inputs do not (0.51-0.59).
- **Test.**
  1. Data: the lot activity of all families (`exam/activity_*`, all slugs) and the Gamma listings.
  2. At each 5m entry and each burst start with a gap of 30 s or more, compute Δ from the Chainlink (or Binance
     stand-in) digital of every open window, and scale other assets by a 1-h beta to BTC.
  3. Choose the rule on STUDY (hedge or add, a threshold on |Δ|). Score it on VALIDATE against the own-inventory baseline
     (the 5m held outcome) and the public R8.
  4. Report it as own state.
- **Data.** Activity and listings on disk or in the HTTP cache. Endpoint values or Binance 1-s for the deltas.
- **Signature if true.**
  - >= 0.75 at entries and long-gap burst starts where |posture edge| is small, on both halves, with one stable sign.
  - The entry multiplier drift disappears once Δ is conditioned on.
  - If the sign is unstable between halves, the cross-market state is rejected with evidence.

### I12-5. Slow Chainlink references for the off-session ladder: the TWAP-60 topic and the full X102 grid (cheap; data already being fetched)

- **Hypothesis.** The off-session 62 / 250 ladder (no skew in region D) centres on a slow settlement reference: the
  RTDS TWAP-60 value, or an EWMA of the report with τ ~ 30 s, rather than the current report. Its mean lag of 30 s
  would match C3's memory.
- **Why it fits.**
  - C5: on the few covered VALIDATE windows, the TWAP-60 posture wins 0.76 where it disagrees with the current report.
  - X91 tested the TWAP-60 topic only on the live US-session 500s.
  - The X102 grid (every even second of 365-s spans) finishes by 11-01 22:00.
- **Test.**
  1. When X102 completes, compute the TWAP-60 and EWMA(τ = 10, 30, 60 s) fairs at every covered lot fill.
  2. Race them against the current report in disagreement cells, by session and rung class, with the size classes of
     `typed_side` (calldata). Choose on STUDY and score on VALIDATE.
  3. Live: the 11-02 00-06 block with the recorded `crypto_prices_twap_sixty` topic, on the match clock.
- **Data.** X102 (queued) and the shared `rtds` recordings.
- **Signature if true.**
  - Off-session 62 / 250 fills follow the slow reference >= 0.75 where it disagrees with the current report, on both
    halves and live.
  - Otherwise close the slow-reference family for the off-session ladder.

## Notes for the RE

- **Cheapest first.**
  - Report the side per burst start (C1, C4) in `evaluate()` beside the per-fill numbers. Restate X129's "taker-chosen
    switches" as quote-state switches (C2).
  - Start I12-2's RTDS recorder at the first development minute (11-01 06:00). It costs nothing and its data only
    exists from the moment it starts.
- **Order of I12-1.**
  1. Read S(t) on 10-31 12-18 first (books already on disk).
  2. Freeze the model.
  3. Score it on 11-02 00-06: the first recorded off-session weekday block, where the side gap actually is.
- **Closed by my checks.**
  - The strike definition: Gamma's TWAP strike is the one the engine uses.
  - The noise regime as the cause of the 10-26 ramp (C6).
  - Self-matching (C7).
  - A Polymarket slow-mid fade (C5).
- If a book-state feature enters the side or presence model, it belongs in the market-only baseline as well.
