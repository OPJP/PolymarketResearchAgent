# Panel, iteration 17: assumption breaker

Lens: what the iteration-17 account takes for granted that may be false. After iteration 17 the account is:

- side, timing and price are decoded on VALIDATE;
- the side check out of time failed, and the failure is put down to the laptop clock;
- condition 5 is bounded by a private size coin ("which decisions are large");
- condition 7 for XM is bounded by the take coin and the dispatcher;
- the post-T0 blocks are a "new regime" whose only differences are configuration: the class rate, the large list and XM's role.

My central finding is that the last point understates the change. On the post-T0 development blocks the operator's per-window PnL is
no longer a taker-stream quantity. Most of its variance now sits in maker-role fills, which the frozen tracker does not trade at
all. XM's PnL moves with the pooled PnL. The 60-share class has never taken, so it is a quote decision, not a late slot. And every
post-T0 development hour falls on a weekend. Together these change what the next exam will measure.

## Data and checks

Development data only. I ran `sealed.py btc5m-bot` at 10:42 UTC on 11-01. It showed: released none; future examined until 10-31
00:00; development blocks 10-31 00-06 and 12-18, and 11-01 06-12 (the current block). Nothing sealed was read and
`.cache/live/sealed/` was not opened. One HTTP call listed the file names and sizes of the public HF capture (no contents read).

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p17a\`.
Each ran in under 300 MB and under 2 minutes.

| script / check | what it measures |
|---|---|
| `regime_pnl31.py` | per-window PnL split by fill role (maker / taker) and wallet: the two 10-31 development blocks (142 windows) against 10-20..22. Inputs: `.cache/re/btc5m-bot/post/own_*.parquet` (on-chain fills), windows and outcomes from `final_rule.load_windows`, only over `sealed.intervals(..., sealed=False)`, with every start asserted development |
| `regime_pnl.py` | the same split on 11-01 06:00-09:30 (`it17/post17_fills.parquet`), with 30-window noise bands drawn from 10-20..22 |
| inline census (`it17/cd31_blk0/2`, `post17_cd`, `post17_mk_cd`) | order sizes by role: does a 60-share order ever take? |
| inline (`it17/mkx17_orders.parquet`) | limits and outcomes of XM's 60-share orders against the taker orders of the same block |
| `flip_move.py` (complete calldata `it16/cdfull_10-20..22`) | are lean flips (large orders against S) driven by the price path since S was set? |
| inline Gamma (4 development windows: 10-15, 10-22, 10-31 00:15, 10-31 12:15) | fee, rebate and reward fields across the regimes |
| inline data-api activity (10-01 to H, types REWARD and MAKER_REBATE) | reward and maker-rebate income by day |
| HF API tree listing of `Fahri-5/updown-5m-polymarket-raw` (names and sizes only; nothing downloaded) | whether the exam's own data source covers a post-T0 development block |

## Critique

### 1. After T0 the target is the resting stream, and the frozen rule does not trade it

The exit component treats maker-role fills as a by-product: remainders and lost races, 16.5% of the window-PnL variance on
10-20..22. `regime_pnl31.py` splits the operator's per-window PnL (DS + GF + XM, before rebates) into maker-role and taker-role
fills, on the same code path for both periods:

| | 10-20..22 (794 windows) | 10-31 00-06 (72) | 10-31 12-18 (70) |
|---|---|---|---|
| corr(W, maker part), Pearson / Spearman | 0.605 / 0.600 | **0.797 / 0.800** | **0.870 / 0.831** |
| corr(W, taker part), Pearson / Spearman | 0.919 / 0.930 | 0.592 / 0.616 | 0.733 / 0.670 |
| variance share, maker / taker part | 0.165 / 0.674 | **0.650 / 0.364** | **0.510 / 0.267** |
| mean per window, maker / taker ($) | +8.1 / -4.0 | -8.5 / -8.1 | -18.0 / +10.5 |
| maker share of fills, DS / GF / XM | 0.32 / 0.36 / 0.43 | 0.54 / 0.59 / 0.89 | 0.54 / 0.59 / 0.94 |
| corr(pooled W, XM's W) | **0.317** | **0.776** | **0.731** |

On 11-01 06:00-09:30 (30 windows; noisy) corr(W, maker part) is 0.947 and the maker variance share 0.49.

The implied correlation between the maker and taker parts is about 0.0 on 10-31 00-06 and 0.3 on 12-18. The two streams are nearly
independent, so a taker-only replica cannot pick up the maker stream indirectly.

Consequences the account has not drawn:

- **The frozen tracker is likely to fail condition 5 in this regime, by construction.** A perfect replica of the taker stream would
  reach Spearman 0.62-0.67 against W. A realistic one would land well below 0.5.
- **Iteration 17's resting-stream test (pre-registration 14) cannot be transferred.** It was run where the maker stream carried 16%
  of the variance and earned +$8 a window. After T0 the operator's own maker stream loses money too (-$8.5 to -$18 a window), and it
  carries most of the variance. Adverse selection in a replica's resting fills is then a resemblance to the operator, not a defect.
- **Condition 7 for XM changes shape.** XM's PnL tracks the pooled PnL at 0.73-0.78, against 0.32 before. In this regime XM fails or
  passes with the pooled rule, not with the dispatcher.
- **Iteration 9's ceiling (pnlceil9b: attainable on 10-31) still holds**, but it is a ceiling for the operator's own decisions,
  including their resting part. The executable rule has to include that part to reach it.

### 2. The 60-share class never takes: it is a quote, not "the late slot"

Finding 8 leaves "always late or post-only" open, and the record can in fact separate the two:

- In the 3,000 sampled operator taker transactions of the two 10-31 development blocks, and in all 1,144 of 11-01 06-09:30, **no
  60-share order appears as a taker order, for any wallet**.
- 60-share orders do appear as maker orders: 696 times in the 11-01 maker-only transactions (XM), plus GF 12 and W4 1.
- XM's own 30-share and 100-share orders in the same block take freely. On 11-01, 73 XM taker orders were 30 or 100 shares, and 63
  XM 30 / 100 orders were maker-first: about 54% of them take.
- If the 60-share orders were ordinary GTC orders in a late slot, P(0 of 274 take) would be below 1e-6 even at a 5% take rate.

So the 60-share class is sent post-only, or only when the bot's view says the ask has already moved. Either way it is a separate
QUOTE decision, not a lost race. Its limits also lean cheaper than the taker stream: 36.5% are below 0.25, against 19.5% of the
block's taker orders and 27% of DS's 30-share maker-first orders. Condition 7 for XM in this regime is therefore a quote-placement
problem (when, where, and how long the order rests), not a dispatch problem.

### 3. The out-of-time side check ran on the wrong data path

Pre-registration 11 scored dc_exam14 on a laptop feed whose clock drifts 175 ms per hour, and the account reads its failure as a feed
artefact. The examiner's route reads the HF capture instead. The capture's listing (revision f848a77c, last modified 11-01 01:16 UTC)
has a **2026-10-31 day file**: polymarket/ 3.32 GB and btc/ 116 MB. It contains the two 10-31 development blocks, 142 windows, on
the collector's stable clock, in the post-T0 configuration.

Iteration 13 deferred these files pending a ruling on footer-only row-group selection. Nobody has asked for that ruling since. Until
it is asked, the side component counts as the one passing condition on a test that has never been run where the exam will run it.

### 4. Every post-T0 development hour is a weekend hour

10-31 is a Saturday and 11-01 a Sunday. The reference period, 10-20..22, is Tuesday to Thursday. Before H, weekends already looked
different:

- DS / GF maker fill shares were 0.45-0.50 on 10-10/11 and 10-17/18, against 0.29-0.38 on 10-20..22;
- order counts were about half.

XM's 60-share component and the maker variance share (0.19-0.28 on pre-H weekends) are not weekend effects. Part of the "new
regime" may be one, though (the DS / GF maker share, possibly the class rate). The h1 lot holds a Friday, a Sunday, a Tuesday and a
Thursday. The first weekday development blocks, 11-02 00-06 and 12-18, end within hours.

### 5. Smaller points

- **The presence label changes meaning in a maker-heavy regime.** "Operator BUY fill in this second" is now mostly a maker fill.
  Its timing is set by another trader's taker print, which the co-occurrence baseline sees by construction. Expect condition 2 to
  weaken further on post-T0 lots unless the unit moves to orders (posted or submitted), which the brief prefers anyway ("or better,
  whether it has an order resting").
- **The own-state line for size is drawn by assumption, not by ruling.** The brief allows own inventory for describing the policy
  (reported with and without), and G5a (fills older than m - 2 s) is point-in-time. The investigation calls it an "oracle for a
  replica" and has never asked the examiner whether a size component may use it. The executable condition-5 rule must not copy the
  wallet's realized net. That is a separate question, and it should stay separate.

## Checked and not supported (so nobody redoes them)

- **Lean flips do not follow the price path since the lean was set** (`flip_move.py`; 72,602 operator taker orders of 10-20..22,
  exact classes; block / tx_index order):
  - P(large) is 0.231 with S, 0.042 against S and 0.147 with no S;
  - the AUC for a flip, from the move of the market toward the order's outcome since S was set, is 0.542 (n 35,920, 1,492 flips);
  - by bins the flip rate runs only 0.03 to 0.06;
  - by age of S it is 0.036 at 4 s or less and 0.046 at 60-120 s, and 0.078 only beyond 120 s (n 450);
  - favourite against underdog: 0.039 / 0.043.

  A stop-and-reverse rule on the price path is not the transition driver.
- **No fee or rebate parameter changed between the regimes.** Gamma's feeSchedule (rate 0.07, takerOnly, rebateRate 0.2),
  makerRebatesFeeShareBps 10000, rewardsMinSize 50, rewardsMaxSpread 4.5, feeType crypto_fees_v2 and the base fees are identical on
  10-15, 10-22 and both 10-31 development blocks. The regime is not a response to a listed fee or reward change.
- **There are no REWARD rows before H** (DS, GF, XM, 10-01 to H). MAKER_REBATE rows follow XM's maker component: XM got $160-355 a day
  on 10-04..14, then $30-62 a day from 10-15, a day after the 10-13 14:10 switch. That is small next to the post-T0 maker stream's
  losses (pooled -$8.5 to -$18 a window, about -$2.4k to -$5k a day before rebates). Rebates do not explain the 60-share component
  economically. The 60-share size does clear rewardsMinSize (50), but no reward income is visible before H.

## Proposals (ranked by the chance they close the gap)

### P1. Re-target conditions 5 and 7 for the regime the exam may see: score the frozen tracker there, and add the resting stream (new; strong form of X174 (iii), X133 and X175)

**Hypothesis.** On post-T0 lots the per-window PnL is mostly the resting stream: the maker-role fills of lost races, remainders and
post-only quotes. The frozen taker-only tracker therefore fails condition 5 there, and a replica's resting stream raises its
correlation instead of lowering it. XM's PnL follows the pooled PnL, so condition 7 for XM rides on the pooled rule.

**Why it fits.** Critique 1:

- maker variance share 0.51-0.65 against 0.165;
- corr(W, maker part) 0.80-0.87 against 0.605;
- the maker and taker parts are nearly independent;
- XM against pooled 0.73-0.78 against 0.32;
- the operator's own maker stream is adversely selected (negative mean), as the rest17 replica was.

**Test** (all on development data).

1. Score the frozen evaluate() tracker once on the 142 windows of the 10-31 development blocks and on 11-01 06-12. Use the tape-only
   avg route now, and mix14 once the capture extract of P4 exists. Report pooled, per-wallet and halves.
2. Pre-register a two-stream tracker before fitting anything:
   - trk_a / mix14;
   - a resting stream: the unfilled part of each tracker order, plus a 60-share quote at L for decisions on XM's slot;
   - the resting life drawn from the TTL distribution measured from book traces on 10-31 00-06 (live lab clob_crypto /
     btc5m_clob_raw*);
   - strict maker fills, match_slack 2.
3. Fit on 10-31 00-06 and score once on 10-31 12-18, 11-01 06-12 and the 11-02 development blocks. Adopt it as a regime route only
   if it beats the frozen tracker on both Pearson and Spearman there, and stays non-inferior (within 0.01) on 10-20..22.
4. State to the examiner which route applies to which configuration.

**Data.**

- `.cache/re/btc5m-bot/post/own_*.parquet`, `it17/post17_*`, `it17/mk17` / `mkx17` (maker-only calldata);
- Gamma outcomes for development windows;
- data-api tapes of those windows;
- live-lab book traces, through iter_live only.

**Signature if true.**

- The frozen tracker's pooled r is at most about 0.40 on the post-T0 windows. Its Spearman ceiling against W is 0.62-0.67 even with
  a perfect taker stream.
- The replica's resting PnL correlates at 0.4 or more with the operator's maker PnL per window.
- The two-stream tracker clears 0.5 on both measures in the new configuration, with XM's per-wallet r within 0.03 of pooled.

**If false.** The frozen tracker holds 0.5 on post-T0 windows. The maker stream then co-varies with something the taker target
already sees. Write the measured split into the exit component either way.

### P2. Is the "new regime" a weekend mode? Replicate the census on the weekday development blocks before freezing version parameters (new; guards X175 and the exam statement)

**Hypothesis.** Part of what iteration 17 calls the new configuration is a weekend operating mode, set on purpose or by the
environment. Candidates are the DS / GF maker share and possibly the large-class rate. Weekday blocks would then look like
10-20..22, while XM's 60-share quote component and the maker variance share may persist.

**Why it fits.** Critique 4:

- all post-T0 development hours fall on 10-31 (Saturday) and 11-01 (Sunday);
- pre-H weekends already show DS / GF maker fill shares of 0.45-0.50 against 0.29-0.38 on the weekday reference, and about half the
  orders;
- h1 is Friday, Sunday, Tuesday and Thursday.

**Test.**

1. Run census17 / census31_17 and `regime_pnl31.py` unchanged on 11-02 00-06 and 11-02 12-18 (both development by the calendar)
   as soon as they end. Report:
   - per-wallet P(large), the large list and pooled first-leg share;
   - XM's maker share and 60-share count;
   - the maker / taker variance split.
2. On pre-H days, fit day-level shares on weekday / weekend plus BTC activity (Binance 1-s absolute returns) and crowd taker volume.
   This separates the calendar from the market's own quietness.

**Data.** Calendar-cleared 11-02 blocks (on-chain fills, sampled calldata), `fills.parquet` and `b1_orders_sample` for the pre-H days,
`binance_1s.parquet`.

**Signature if true.**

- On 11-02 weekdays: GF P(large) back near 0.27, pooled first-leg large near 0.08, DS / GF maker fill shares at 0.30-0.38, maker
  variance share near 0.2.
- Then the frozen rule needs a day-of-week (or activity) switch, and h1's Sunday (10-25) is the outlier day.

**If false.** The configuration of 10-31 / 11-01 is a dated version change. P1's two-stream route is the one to freeze.

### P3. Decode the 60-share class as a post-only quote with its own trigger (strong form of X177; it closes X177's open question)

**Hypothesis.** The 60-share orders are post-only bids at the ask of the bot's view, sent on the same Binance knee as the taker
stream (frozen dc14 0.80 at posting + 150 ms). They survive only when the makers have already pulled, so the visible ones sit at the
vacated level, one tick below the new ask. They carry their own lifetime rule, and their fills are the PnL of XM in this regime.

**Why it fits.** Critique 2:

- 0 of thousands of 60-share orders ever take, while XM's 30 / 100-share orders in the same block take about 54% of the time;
- 274 of 274 postings were found in the book;
- the ask equalled L 100 ms before posting in 63%;
- limits lean to cheap prices (36.5% below 0.25).

**Test** (11-01 06-12 book traces now; the 10-31 capture extract when it exists).

1. **Posting hazard.** Model P(60-share posting on o in a 50-ms bin | public state) on the knee clock. The candidate trigger is a
   Binance knee move toward o followed by o's ask stepping up by one or more ticks within the hold. Score it against a book-aware
   market baseline at the e cut, and against the taker-first-leg hazard (is it the same trigger with a different price rule?).
2. **Lifetime rule.** From book traces: posting to removal, against age, the price move since posting and the next ladder burst
   (+42 / +172.7 s). Is it a fixed TTL, a price stop, or a cancel at the next burst?
3. **Replica.** Post 60-share bids at the same L on the decoded trigger, with the decoded life, strict fills (match_slack 2) and
   queue behind the operator's size. Report the per-window corr with XM's maker PnL, pooled and by half.

**Data.** `it17/post60_17.parquet`, `mkx17_orders.parquet`, post17 / mk17 calldata, btc5m_clob_raw2 (iter_live), rec_bn15 v2 spot
(local clock as in 11b).

**Signature if true.**

- Posting hazard AUC of 0.85 or more, with a gain of 0.05 or more over the book-aware baseline at e.
- A lifetime rule that names 70% or more of removals within 1 s.
- Replica corr of 0.5 or more with XM's maker PnL. Condition 7 for XM in this regime then has a decoded route.

**If false.** Postings are not tied to a public trigger beyond the taker hazard. XM's quote stream is then the same decision
stream, and its PnL ceiling is the taker stream's thinning ceiling.

### P4. Run the exam route out of time on its own data source: a development-only extract of the capture's 10-31 day file (strong form of X164, X150 and X167)

**Hypothesis.** Pre-registration 11's 0.718 measured the laptop feed, not the rule. On the capture's collector clock the frozen
dc_exam14 holds 0.80 or more out of time. If it does not, the side component, the only condition counted as met, is at risk on h1.

**Why it fits.**

- The laptop clock drifted by 524 ms in 3 h.
- A 25-ms cut shift moves the score by 5 points.
- The capture collector's transit is stable within about 9 ms per hour.
- The capture's 10-31 file exists: polymarket/ 3.32 GB, btc/ 116 MB.
- Iteration 13 deferred it on a procedural question that was never put to the examiner.

**Test.**

1. Ask now for one of two things:
   - an examiner-made extract of `polymarket/2026-10-31.parquet` and `btc/2026-10-31.parquet` restricted to [00:00, 06:00) and
     [12:00, 18:00) UTC and to windows starting there;
   - or a ruling that footer-only row-group selection on exchangeTimestampMs is allowed.
2. Pre-register the score before reading: dc_exam14 per taker order pooled ≥ 0.80, per wallet reported, with placebos and halves.
3. Then run evaluate() end to end on the 142 windows:
   - side;
   - presence_decision_clock;
   - mix14 tracker (feeds P1);
   - the L2 ingest (feeds P1 and P3).
4. When the capture publishes 11-01, score the same 999 orders of 11-01 06-09:30 on it. Laptop against capture on identical orders
   isolates the feed effect.

**Data.** The extract, own_*.parquet, the cd31 samples (or complete calldata of the 142 windows, about 10 min with cdfull16.py).

**Signature if true.**

- Side 0.82-0.85 per order with flat halves, and the 11-01 capture-vs-laptop gap of about 10 points on identical orders.
- If the side is 0.78 or less on the capture: the route decays out of time, and that must be known before an exam round is spent.

### P5. Make the presence unit an order, not a fill second, before the next claim (strong form of D1 / X146 for the post-T0 configuration)

**Hypothesis.** With most fills now maker fills, the block-second label "operator fill in this second" is mostly a maker fill.
Another trader's taker print sets its timing, and the market-activity baseline sees that print by construction. So condition 2's gain
shrinks further, possibly below zero, on post-T0 lots. A decision-level unit gives the decoded knee a fair test in both
configurations. The unit is "the operator submits a taker order or posts a quote on o in this 50-ms bin", built from calldata plus
book postings.

**Why it fits.**

- Critique 1: maker share of fills 0.54-0.94 after T0.
- The decision-clock hazard already beats activity at 0.889 against 0.759 on taker first legs.
- Finding 8 shows that quote postings are recoverable from the public book (274 of 274).

**Test.**

1. On the 10-31 development blocks, compute the frozen block-second presence AUC and the capture-aware baseline, split by the role
   of each positive second (maker-only against taker).
2. On 11-01, build the order-level unit: taker submissions (match ms - 150) plus 60- and 30-share postings found in btc5m_clob_raw2.
   Score the frozen knee-clock hazard against a book-aware baseline cut at e.
3. Put the unit to the examiner as part of the pre-registration.

**Data.** As P1 and P3; the frozen block-second model and the pres14 baseline.

**Signature if true.**

- The gain is near 0 on maker-only seconds and positive only on taker seconds.
- The order-level unit keeps a gain of 0.05 or more over the book-aware baseline at e in both configurations.
