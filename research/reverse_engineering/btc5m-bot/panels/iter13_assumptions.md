# Panel, iteration 13: assumption breaker

Lens: what the iteration-13 account takes for granted that may be false. This round tests the load-bearing claims behind the
three conditions that still fail (side 3, PnL 5, per-wallet replication 7):

- "the decision instant is a = m - 180 ms", used on the Hugging Face collector's receive clock as if it were the bot's clock
  (pre-registrations 3 and 4, the exam route `side_decision_clock`);
- "~90% of decisions have no sharp clock in any recorded feed" and "the selection shared with the fast crowd lies outside the
  recorded inputs" (X111, X101);
- "one operator-level decision fans out through a fixed-priority dispatcher (DS first, GF second)" and "the wallet that carries an
  order is barely predictable from public state (accuracy 0.61 against a base rate of 0.61)", which together carry "condition 7 is a
  measured limit for XM".

## Data and checks

Development data only:

- pre-H VALIDATE days: the reduced HF capture files already in the session scratchpad (`it13/hf_dl`: `btc_2026-10-2x`,
  `pm_trades_*`); `fills.parquet` (windows starting before H); `b1_orders_sample.parquet`; `it13/dcside13_frame.parquet`;
  `it13/streams_win.parquet`;
- the 10-31 12-18 development block: `it11/large_dec.parquet`, 2,155 decisions from 14:55-17:55.

Nothing sealed was read, listed or counted, and `.cache/live/sealed/` was not opened. I checked the calendar with
`sealed.py btc5m-bot` at 11-01 03:44 UTC: no lots released, the current block is sealed.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p13a\`.
Each ran under 300 MB and under 2 minutes.

| script | what it checks |
|---|---|
| `spotend.py` | side agreement of the Binance spot microprice / mid move over [m - E - K, m - E) as a function of the window end E (collector clock), all orders and first legs |
| `spotE.py` | the same profile on Binance spot TRADES by their EXCHANGE timestamp; the collector transit |
| `spotkern.py` | decision-locked kernel of spot book updates around the operator's match ms, 10-ms bins, placebo m - 3 s / m - 5 s |
| `sizeE.py` | large size vs the spot move at the corrected clock |
| `dispatch_busy.py`, `xm_solo.py` | first-free priority dispatcher; leg structure and idle state of the wallets (live 10-31) |
| `xm_alloc.py` | AUC of "XM carries this order" from decision-clock public state; within-window allocation oracle for XM's window net |
| `deplete.py`, `large_seq.py`, `ladrange.py` | ladder-copy depletion, large = re-use of a level, per-wallet ladder ranges |

m is the server-ms match time of the operator's taker order: the minimum `exchangeTimestampMs` of its tx in `pm_trades`. The
three VALIDATE slices are:

- 10-20 10:49-13:57 UTC (4,093 taker orders);
- 10-21 15:23-18:50 (3,668);
- 10-22 02:40-06:53 (4,258).

## Critique

### 1. The decision-clock features end about 50 ms before the bot's inputs do

The exam route and both decision-clock side models set the decision at a = m - 150 (taker delay) - 30 (posting), and read the
Binance spot book over [a - K, a) on the **collector's receive clock**. That clock is not the bot's.

- The capture's Binance spot trades arrive 122 / 134 / 166 ms (q01 / q50 / q95) after their exchange stamp.
- Iteration 11 measured that the bot reads Binance about 100 ms old.
- An event the bot saw at its decision instant therefore reaches the collector about 30 ms later. The bot's horizon on the
  collector clock is about m - 146 (with 30 ms of posting) to m - 116 (with none), not m - 180.

The data agree. The net spot microprice move over [m - E - 100, m - E), against the side, all taker orders (coverage in
brackets), placebo m - 3 s at 48-51% everywhere:

| window end E (ms before m) | 300 | 180 (RE) | 150 | 140 | 130 | 120 | 100 | 50 | 0 |
|---|---|---|---|---|---|---|---|---|---|
| 10-20 | 60.8 | 70.8 (0.81) | 78.4 | 82.2 | **84.8** (0.89) | **84.8** | 83.8 | 80.9 | 68.8 |
| 10-21 | 61.8 | 73.4 (0.82) | 80.0 | 83.0 | **83.4** (0.91) | 82.9 | 80.8 | 71.4 | 61.6 |
| 10-22 | 61.7 | 69.1 (0.76) | 73.8 | 76.5 | 79.3 (0.86) | **79.8** | 77.3 | 73.7 | 64.6 |

- **Per decision**: the first or single legs, which are the operator's decisions, score 68.8% / 72.3% at E = 180 and 79.9% / 84.4%
  at E = 130 (10-22 / 10-21). With K = 250 they score 80.3% / 83.9% at E = 120, on 97% coverage.
- **Per wallet** (10-20, E = 130): DS 84.8%, GF 85.3%, XM 81.2%. At E = 180 the same wallets score 69.1%, 73.5% and 78.4%.
- **On Binance's own clock**, where no collector is involved: the last spot trade price change over [m - X - 100, m - X) peaks at
  X = 250-260 ms (78.1-78.3% on 20% of orders; 58.5% at X = 400, 69.9% at X = 150; placebo 50-51%; 10-21). The bot's inputs end
  about 100 ms of Binance-to-arrival latency before its arrival at m - 150. On the collector clock that is m - 250 + 134 = m - 116,
  where the book profile peaks.
- **Reading**: the two clocks are independent and give the same horizon. The univariate spot microprice at that horizon (80-85%
  per decision) beats the pre-registered full venue model at the old anchor (76.3%).
- **What the old anchor cost**: iteration 13 read the steep fall of accuracy with the window length as a trigger. The trigger sits
  in the last 50-60 ms that a = m - 180 cuts away.

This is not yet proof that the decision used those last 50 ms; continuation is possible. Against continuation: the 100-ms
window that lies wholly after the arrival, [m - 100, m), falls back to 62-69%. Proposal 1 has a control that separates the two.

The PIT rule is not stretched. In exchange time, the window that ends at collector m - 128 ends at E_exch <= m - 250, i.e. at
least 100 ms before the arrival. The brief only requires publication at or before t.

### 2. The timing and selection accounts were built without the input the side names

Three facts together:

- **The input is the spot book, size changes included.** At the decision clock, the side follows the Binance SPOT top-of-book
  microprice, i.e. size changes, not only price changes. Only 7.3% of DS taker orders, 13.2% of GF's and 27.7% of XM's have a
  spot microprice move above 0.02 bp in [a - 250, a); the rest move with queue sizes.
- **That input is missing from every feed the timing and selection results rest on.**
  - The live recorders kept the spot BTC quotes price-change-only and coalesced (6.8 / s against 146 / s in the capture;
    iteration-13 finding 18).
  - X111's lock test used seven series and spot BTC was not among them.
  - The onset tables (evt10, onset11) are Binance USD-M L1 events on the laptop clock.
- **Decisions sit inside spot book bursts.** Around the operator's matches, the capture's spot book updates 2.7 times as often in
  collector [m - 200, m - 100) as in the placebo: 26.0 toward-o and 14.1 away microprice updates per order, against 7.3 / 7.5
  (spotkern.py). Price-level spot changes in that window run 21:1 toward o (0.69 vs 0.03 per order; placebo 0.09 / 0.10).
  - A pure toward-o price-level change in [m - 250, m - 100) precedes 12.2% of orders (placebo 2.2%). Per wallet, over
    [m - 400, m - 150): XM 24.9% (placebo 1.5%), GF 14.4% (3.7%), DS 5.8% (3.0%).

"About 90% of decisions have no sharp clock" and "the recorded design explains only 14-21% of the shared selection" were measured
without that input and on the wrong clock. The fast crowd taking the same onsets is what one expects if everyone fast reacts
to the same spot book at about 100 ms. The claim that the shared input exists but is not recorded may simply mean that the
spot book was recorded too coarsely.

### 3. "Fixed-priority dispatcher" is falsified, and "barely predictable" was a metric artefact. XM's wall still stands

**The dispatcher.** On the live development block (10-31 14:55-17:55, 2,155 decisions):

- A first-free rule (DS, then GF, then XM, busy for T ms after an arrival) is at best 0.671 against a base rate of 0.571
  (T = 250 ms).
- In 58.9% of XM's decisions, both DS and GF were idle for more than 200 ms.
- XM leads 76 of 434 multi-leg events, and in those DS and GF were idle for more than 300 ms in 94.7% and 97.4%.
- The second leg follows the first by a median 57-74 ms. That looks like a re-decision on later updates, not a serial send.
- On VALIDATE, leaders are DS 78.6%, GF 14.8% and XM 6.6% (n 20,090).

**The metric.** Multiclass accuracy against the base rate cannot show a 6% class. Fitted on 10-17..19 and scored on 10-20..22
(xm_alloc.py):

- P(XM carries the order | public decision-clock state) has AUC 0.768 (spot only) to 0.785 (all venues and both asks).
- XM's share runs from 0.7% to 19.9% across the deciles.
- GF's AUC is 0.59.

**The consequence.** The allocation is predictable, but that does not rescue XM.

- Take the TRUE operator taker decisions, with their true sides and sizes, and weight each by P̂(XM).
- That oracle correlates with XM's window taker net at only 0.436-0.439, on 692 windows.
- The true per-window share times the pooled net gives 0.425, and the pooled net alone 0.309.
- For GF the same oracles give 0.79 / 0.81 / 0.80.

So XM's window net behaves like a random thinning of the operator's decisions. Even a perfect replica of the operator plus the
best public allocation leaves XM near 0.44 (window net), below the 0.47 that condition 7 requires. Proposal 4 makes this a
formal ceiling.

### 4. Size is not in the immediate spot move, even at the corrected clock

On 10-21 (3,668 orders, 5.7% large), the AUC of "large" on the spot microprice move or the count of book updates over
[m - 378, m - 128) is 0.585 / 0.612 for first legs (sizeE.py). At the old anchor it is 0.647 / 0.637.

The live "size follows the tick" (AUC 0.72) does not carry over to VALIDATE weekdays. Size stays own state: the operator's net
gives AUC 0.75 (X49). For condition 5 this matters: the corrected clock can sharpen the side and the timing of the replica, but
the lean's size has to come from the replica's own sent position.

## Checked and not supported (so nobody redoes them)

- **Ladder-copy depletion as the take or dispatch state.** Uses of one (wallet, burst, outcome, cent, size) level: 1 in 8,923
  levels, 2 in 1,494, 3 in 348, 4 in 95, 5 in 16, 6 in 3 and 10 in 1. There is no cap, and the counts taper geometrically.
- **"Large" is the re-use of a level whose small copy was consumed.** No. P(large) by use rank at the same level is 23.6% / 16.2%
  / 16.6%.
- **A per-wallet position cap.** The window net tails are smooth, with no pile-up: |T| q99 / max GF 856 / 1,173, XM 372 / 769,
  DS 747 / 1,046 shares.
- **Per-wallet ladder ranges that force an order to XM.** |limit - last price at signing| > 0.30 for 9.7% / 11.5% / 16.1% of
  DS / GF / XM orders, with no partition. XM's +0.09 mean shift is its strong-tick mix.
- **A different venue per wallet.** The univariate ranking is the same for every wallet (spot 250 ms first, then Bybit, then the
  USD-M / OKX trades); DS is lower on every series.

## Proposals (ranked by the chance of closing the gap)

### 1. Re-anchor the decision clock on Binance's own clock (strong form of X98 and X113 steps 3 / 6; corrects pre-registrations 3 and 4)

**Hypothesis.** The bot's Binance inputs end at a Binance-to-Polymarket-arrival latency of about 100 ms before its arrival at
m - 150: exchange time about m - 250, collector receive about m - 120..130. At that anchor the side is at least 80% per decision
at full coverage. The 76.3% of pre-registration 3 and the 74.2% exam route are what is left when the trigger's last 50-60 ms are
removed.

**Evidence.** Critique 1:

- the univariate agreement rises from 69-73% at E = 180 to 79-85% at E = 120-130 on three VALIDATE slices, and per decision too;
- the exchange-clock trade profile peaks at X = 250-260 ms;
- the collector transit is 122 / 134 ms (q01 / q50), against the bot's ~100 ms;
- the window after the arrival falls back to 62-69%.

**Test.** Pre-register before any VALIDATE score:

1. **Fix the anchor on fit days only.** On 10-17..19, compute both profiles in 10-ms steps:
   - the collector book profile, E from 300 to 0 ms;
   - the exchange-clock trade profile, X from 400 to 100 ms.

   Fix the latency L as the end of the plateau of the exchange-clock trade profile, rounded up to 10 ms and never below 100 ms.
   The collector anchor then follows: book receive <= m - 150 - L + 122 (the q01 transit), i.e. m - 128 for L = 100; trades
   E_exch <= m - 150 - L. Freeze L.
2. **Refit both models at the new anchor.** Refit the spot-only exam route (`model_it13_dcside_spot.txt` features) and the full
   venue model with every window ending at the anchor; venues without an exchange stamp are shifted by their own measured
   transit floor. Fit on 10-17..19 and score once on 10-20..22. Report:
   - per order and per decision (first and single legs), per wallet, by window minute;
   - XM's one-sided windows, and the own-state pairing kernel on top;
   - the market-only baseline and the old-anchor model on the same orders.
3. **Separate continuation from decision (the control).** For the crowd's fresh-signed taker orders in the calldata sample hours
   (10-20 11:00 and 10-21 13:00: every non-operator taker that hit a cluster resting order carries its `sign_ms`), compute the same
   profile relative to their match AND relative to their `sign_ms`. If their agreement peaks at a fixed offset from `sign_ms`,
   while the operator's peaks at a fixed offset from m, both are decision clocks. If both peak at m - 130 whatever the signing
   time, the operator's peak is market-wide continuation.
4. **Robustness.** Repeat with L = 110 / 120 ms. Also add a per-order clock from the Polymarket touch on 10-20 / 10-21: the
   latest instant before m at which o's ask equalled the order's limit (the bot prices off the ask about 30 ms old). Does the
   taker delay vary per order?
5. **Ship it.** Put the frozen re-anchored route into `evaluate()` (the capture's h1 day files are reachable under ALLOW_SEALED).

**Data.** The reduced HF capture (`btc_*`, `pm_trades_*`, `pm_touch_*`, 10-17..22), `fills.parquet`, `calldata_sample.parquet`, and
the dcside13 / dc_exam13 code.

**Signature if true.**

- At least 80% per decision at full coverage pooled, with DS at least 78%.
- The late-window minutes (now 62-72%) rise.
- XM's one-sided windows reach at least 85%, with a narrower daily spread than 73-94%.
- The crowd control peaks relative to `sign_ms`.

**Signature if false.**

- The re-fit models stay at 77% or less.
- Or the crowd's profile also peaks at a fixed offset from its match, which means continuation.
- Then the side's account keeps the old anchor and reports both profiles.

### 2. Re-open timing and selection on the full-rate spot book at the corrected clock (strong form of X111 step 3, X101, X63 / edge_rule_V8 and X119)

**Hypothesis.** The take is a threshold rule on the spot-microprice-implied value of o against o's touch, read at the corrected
clock. The "coin among price-level ticks", the 90% "unlocked" decisions, the operator-level 30-60-s state and the shared crowd
selection are largely artefacts of three things:

- conditioning on Binance USD-M L1 events on the laptop clock;
- live spot quotes that are price-change-only and coalesced;
- a lock set that excludes spot BTC.

**Evidence.** Critique 2:

- the 2.7x spot book burst in collector [m - 200, m - 100);
- price-level spot changes toward o at 21:1 in that window;
- toward-only price-level locks of 12.2% vs a 2.2% placebo (XM 24.9% vs 1.5% over [m - 400, m - 150));
- DS's quiet single-leg decisions (median USD-M tick about 0 live) still agree 85% with the spot microprice at the corrected
  clock (10-20).

**Test.** On 10-20 / 10-21, where the capture's Polymarket touch exists at server ms. Ingest the touch for 10-17..19 and 10-22
politely: at most 2 threads, coalesced ranges.

1. **Hazard model.** A 10-ms hazard of "an operator taker arrival on o in [t + 150, t + 160)", or the event unit (spot microprice
   moves of at least k over 100 ms at the corrected clock). Features:
   - spot microprice drift and queue depletion / refill at the corrected clock;
   - o's touch age, size and changes at server ms, ending at t - 30;
   - rel and |ask - 0.5|.
2. **Baseline.** The same model class on Polymarket trades and touch only. Fit day A, score day B, and the reverse.
3. **Recompute the old accounts with the new input:**
   - X111's locked share against a placebo, with spot BTC included;
   - X101's crowd co-take log OR explained;
   - hawkes12's own-kernel increment in held-out log loss.

**Data.** The HF capture (book, trades, Polymarket touch and trades), `fills.parquet`, and the calldata sample hours for the crowd's
`sign_ms`.

**Signature if true.**

- The hazard AUC gains at least +0.05 over the Polymarket-only baseline in both directions.
- At least 40% of decisions are locked to a spot event beyond the placebo.
- At least 50% of the crowd co-take log OR is explained.
- The own-kernel increment is halved: the "operator state" was spot book activity.

**Signature if false.** The take stays at the old AUC with the right input and the right clock. Then the selection really runs
on something outside public market data, and that sentence can go into the wall account with these numbers.

### 3. Condition 5 from a millisecond nowcast of flow already decided (strong form of next-step 5 and X113 step 5)

**Hypothesis.** Block-second s flow was matched at about s - 2.2 s and decided about 2.4 s before s. The tracker executes at least
2 s after its information horizon. Its target may therefore use every Binance spot event up to s - 1 at ms. The right target is a
**nowcast of the operator's already-decided flow**, built from:

- the corrected-clock side, about 83% per order against 72.7% at the block clock;
- the take hazard of proposal 2;
- E[size | the replica's own sent position], because size is own state (critique 4; X49: operator net AUC 0.75).

The 1-s kline features cannot carry that side precision.

**Evidence.**

- The oracle that knows the operator's orders with their size class reaches 0.88. With fixed size and no fill model it reaches
  only 0.41-0.49.
- The tracker already reaches 0.476 / 0.440 with block-clock side information.
- The side information per order rises by about 10 points at the corrected clock.

**Test** (pre-register target, constants and the single adoption rule):

1. Nowcast flow per (window, outcome, block second) = sum over spot events of P̂(take) x side x E[size | sent state], where the
   sent state is the replica's own cumulative target. Fit on 10-17..19, score 10-20..22.
2. Window-net r against nf12b and trk_a_avg on the same days.
3. The tracker with the TRK constants unchanged, strict fills, latency >= 2 s. Report Pearson / Spearman with the 2-h block CI and
   per wallet.
4. Adopt only if it beats trk_a_avg on both Pearson and Spearman on those days.

**Data.** The HF capture for 10-17..22 (spot book and Polymarket trades), the it12 tracker code and the cells.

**Signature if true.** Window-net r of at least 0.53, and the tracker at least 0.50 on both Pearson and Spearman, with the CI lower
bound above 0.476.

**Signature if false.** Window r of 0.50 or less. The account then reads: public side and timing at ms explain x of the
window net, and the rest is the own-state size of the lean.

### 4. Make condition 7 for XM a formal ceiling: random thinning, not "dispatch" (strong form of X122 / X120 / X55)

**Hypothesis.** XM's legs are a random draw among the operator's decisions. The draw is not deterministic in any observable
state; at most it depends on the operator's PRNG, which no executable rule can see. Then no rule can give XM the 0.47 that
condition 7 asks, and that should be stated as proven.

**Evidence.** Critique 3:

- the fixed-priority dispatcher is falsified;
- the allocation AUC is 0.77-0.79;
- the allocation oracle is 0.436-0.439, against 0.425 for the share oracle.

**Test.**

1. **Determinism on own state.** On the capture's match clock (10-17..22), model the carrying wallet on the full own ms state:
   - per-wallet in-flight status and time since its last arrival and match;
   - the burst segment;
   - per-wallet daily fee volume;
   - the operator's net per wallet.

   Report the AUC per wallet.
2. **Thinning test-retest.** Redraw each operator decision's wallet 1,000 times from P̂(wallet | public + own state), over the
   true decision stream. Then:
   - compute the correlation of the redrawn XM window net and PnL with XM's true ones;
   - compute the same for DS and GF;
   - compare with the allocation oracle.
3. **Halves.** Do it on both VALIDATE halves, so the ceiling's own replication is known.

**Data.** `dcside13_frame` with a match-ms column added, plus maker-role orders from fills and calldata for the in-flight
state. Also `large_dec` for 10-31.

**Signature if true** (wall component). The own-state AUC stays below 0.9, and XM's redraw ceiling is 0.45 or less on both
halves. Write condition 7 for XM as unattainable by any executable rule, with the number, next to the measured gaps of the
pooled conditions.

**Signature if false.** The own-state AUC is 0.95 or more. Dispatch is then deterministic: XM's net is a function of the
operator's decision stream, and condition 7 reduces to proposal 3.
