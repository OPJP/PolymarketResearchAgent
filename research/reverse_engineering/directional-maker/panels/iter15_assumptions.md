# Panel after iteration 15: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 15 the working assumptions are:
- one engine runs the three accounts and posts each decision in all three ("the engine" and "the cluster" are used
  interchangeably in every component, and the per-wallet numbers are read as small deviations of one process);
- the side of the BTC ladder is a digital fair with a volatility multiplier k, and what moved between 10-31 and 11-01 is
  that k, driven by the Chainlink noise regime;
- R7 ("last clean trade - 0.01") is the price law of the engine wherever the anchor is fresh, and the non-BTC families
  fail it only because their prints are stale;
- the outcome bar is out of reach because of the BTC 5m weekday replay ceiling (0.47-0.53).

Written 2026-11-01, 08:40-09:30 UTC.

**Data used (development only).** `tools/sealed.py directional-maker`: released h1 and h2; development
[10-23, 10-31 06:00), [10-31 12:00, 18:00) and [11-01 06:00, now); sealed [10-31 06:00, 12:00) and [10-31 18:00,
11-01 06:00).
- Cluster activity: `.cache/re/directional-maker/activity_*.parquet`, `exam/activity_*.parquet` and the RE's `act15_*`
  files. BUILD (10-08..22) and STUDY (10-23..26) were used per 6-h block. VALIDATE (10-27..30) was used only as
  aggregate counts. I also used the development blocks 10-31 12-18 and 11-01 06:00-08:02. Units are counted by their
  window start, and sealed units are dropped with `sealed.is_sealed`.
- All-match calldata of 11-01 06:00-07:38 (`it15_today_orders.parquet`, the RE's file).
- The RE's rebuilt quote-unit tables `it14_qu_rebuilt_1793455200_1793469600` (10-31 14-18) and
  `it14_qu_rebuilt_1793516400_1793520000` (11-01 07-08). For the posture I used dy_rtds publish ms and recorded Chainlink
  values (`cl_source`, `allow_sealed=False`), the dm_bnf futures mid, and Gamma strikes. All of these were read through
  the RE's `iter_live` helpers, which return development blocks only.
- Binance 1-s data: `spot_btc_1s.parquet` (BUILD) and the RE's `bn1s/` day files for STUDY 10-23..26.
- `it15_nb_public_lot.parquet` (STUDY rows only).
- Nothing from `.cache/live/sealed/` or from sealed units.

**Scripts** (all in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p15a\`;
run from the repo root with `.venv/Scripts/python.exe`):
- `wallet_mix.py`: the per-block wallet mix of BTC 5m buys and the per-wallet tilt;
- `module_gaps.py`: extreme-price fills during main-ladder off-runs;
- `twofeat.py`: the edge + cheapness law, with a transfer between the two blocks;
- `tilt_drivers.py`: day-level public calibration drivers of the tilt;
- `nb_price.py`: a fair-anchored price for the non-BTC later fills.

Each runs in under 3 minutes and under 300 MB.

## Quick checks

**Q1. The three accounts stopped being copies on 11-01. In the whole development history before that, they never
were anything else.**

- BTC 5m BUY fills per 6-h block (blocks with at least 30 fills):

  | fold | blocks | single-wallet blocks (one wallet with at least 0.80 of the fills) | other facts |
  | --- | --- | --- | --- |
  | BUILD | 56 | 0 | |
  | STUDY | 12 | 0 | |
  | VALIDATE (aggregate) | 16 | 0 | median top-wallet share 0.35 |
  | 11-01 06-12 block (to 08:02) | 1 | 1 | almach 7, bosona 189, mo-money 12 (bosona 0.91) |

  Over the 68 three-wallet BUILD/STUDY blocks, the per-wallet cheaper-token shares move together (correlation 0.84-0.89,
  median spread 0.08).
- The all-match calldata of 11-01 06:00-07:38 shows a clean split by price:

  | wallet | BTC 5m filled orders at 0.10-0.90 | other BTC fills | first BTC fill |
  | --- | --- | --- | --- |
  | bosona | 90 | | 07:00:48 |
  | almach | 2 | at <= 0.10 or >= 0.90, plus one BTC 15m sweep at 0.69/0.70 at 07:15:03 | 07:15:03 |
  | mo-money | 0 | the same | 07:15:03 |

  almach and mo-money start in the same second.
- In activity, almach's and mo-money's BTC 15m fills of 07-08 have a median price of 0.05, against 0.25 for bosona.
- The alt 5m/15m fills are also mostly bosona's: ETH 5m 6 / 0 / 0, ETH 15m 4 / 0 / 0, SOL 5m 8 / 3 / 3 (bosona / almach
  / mo-money). The Binance-settled hourly and daily families run in all three about equally (hourly 13 / 19 / 13, daily
  24 / 26 / 27).
- The posts tell the same story. Non-extreme pure-500 posts at the touch, by pass multiplicity (same-size adds at one
  price within 25 ms):

  | block | posts | singles | pairs | triplets |
  | --- | --- | --- | --- | --- |
  | 10-31 14-18 | 4,948 | 0.43 | 0.27 | 0.29 (0.74 in hour 14) |
  | 11-01 07-08 | 429 | 0.88 | 0.08 | 0.04 |

  The 11-01 quote unit is essentially one engine instance.
- When the split happened:
  - On 10-31 17:06-18:00 (after the ad-hoc restarts of almach and mo-money at 17:05:52 and 17:06:32; bosona was not
    restarted), all three still filled BTC 15m at mid prices: 70 / 39 / 47 fills, median price 0.54-0.66.
  - So the split appeared inside the sealed stretch 10-31 18:00 - 11-01 06:00. That stretch contains the 01:00 restart
    and the 05:00-06:59 listing gap.

**Q2. Historically the BTC 5m module switched as one piece.** In all 5 BUILD/STUDY off-runs of the mid-price ladder
(at least 60 min without a 0.10-0.90 BTC 5m fill: 10-17 20:32, 10-17 22:29, 10-18 22:11, 10-23 20:38, 10-24 22:27), the
extreme-price fills stopped too, in every wallet (0 fills).
- Outside the off-runs, extreme-price fills are 14-17% of each wallet's BTC 5m buys.
- On 11-01, for the first time, the extreme-price module and the mid-price ladder run in different instances.

**Q3. The 10-31 → 11-01 change in the quote side is a level preference that no single edge-plus-cheapness law
absorbs** (`twofeat.py`, pure-500 non-extreme posts, k 1.0 futures sigma). The table gives the cheaper-token share of
the posts per |F - mid| band:

| block, clock | < 0.02 | 0.02-0.05 | 0.05-0.1 | 0.1-0.2 | >= 0.2 | all (posture / cheaper) |
| --- | --- | --- | --- | --- | --- | --- |
| 10-31, exact publish | 0.43 | 0.36 | 0.46 | 0.20 | 0.27 | 0.863 / 0.335 (n 489) |
| 10-31, safe lag | 0.40 | 0.48 | 0.48 | 0.38 | 0.45 | 0.78 / 0.41 |
| 11-01, exact publish | 0.61 | 0.58 | 0.66 | 0.71 | 0.65 | 0.601 / 0.642 (n 358) |

- On 10-31 the posts lean to the favourite at every edge size; on 11-01 they lean to the underdog at every edge size.
- A logistic fit on (F - mid, 0.5 - mid):
  - fitted on 10-31: 0.78-0.87 in sample, 0.55-0.58 on 11-01;
  - fitted on 11-01: 0.68 in sample, 0.47-0.48 on 10-31.

  The blocks differ in a tilt parameter, not in how strongly the posts follow the report.
- What the investigation has not shown is where that tilt sits. It could be the fair's volatility (the "k" reading), or
  it could be the ladder (an asymmetric half-spread, or a center pulled to 0.5).

**Q4. Public calibration quantities do not track the daily tilt** (`tilt_drivers.py`, 14 BUILD days, against iteration
11's per-day best k and favourite share). Three drivers were tried, each on day d, on d-1 and on the mean of d-2..d-1:
- the realized-move ratio sqrt(mean ln(S_end/S_start)^2 / mean(v300^2 x 300));
- the market favourite's excess win rate (last print at 120-150 s);
- the trailing versions of both.

Spearman |rho| <= 0.40 in every case (p >= 0.16). The engine is not chasing recent calibration errors of the market or
of v300. This is only a light check, and the RE need not repeat it.

**Q5. The non-BTC later fills are not priced off a Binance fair** (`nb_price.py`, STUDY later fills; delta fitted on
10-23/24, scored on 10-25/26; sigma = v300 or v3600 x k with k in 0.7 / 1.0 / 1.4). Share of fills within a tick:

| family | fair - delta (best variant) | last print - 0.01 | last print |
| --- | --- | --- | --- |
| 4h | 0.30 | 0.32 | 0.40 |
| hourly | 0.24 | 0.56 | 0.51 |
| alt 15m | 0.23 | 0.42 | 0.40 |
| alt 5m | 0.17 | 0.18 | 0.17 |

The price there is anchored to the market, but the stale print is a bad proxy for that anchor. So a fair-anchored price
(proposed by the iteration-14 panel, P1 step 4 and P3 step 4) is ruled out on this sample.

## Critique

1. **"One engine, three copies" stopped being true, and two iteration-15 conclusions rest on it.**

   Since some time in the sealed stretch after 10-31 18:00:
   - bosona alone runs the mid-price BTC 5m ladder and most of the alt 5m/15m quoting;
   - almach and mo-money run the extreme-price (decided-window) bids and the Binance-settled slow families (Q1).

   This had not happened once in 84 earlier blocks (Q1, Q2). Two consequences:
   - **The "earlier half fails scope (0.54; almach 0.51, mo-money 0.52)" on 11-01 07-08 is this split**, not the
     weekend scope pattern.
   - **The "quote side did not replicate on 11-01" is a one-instance measurement after a reconfiguration.** The
     findings state the Chainlink noise regime as "the cause". That is post hoc: it is confounded with the
     incident-driven reconfiguration, the 01:00 restart, the listing gap and the DST change. It should be tagged as a
     hypothesis.

   The examiner's next lot is the sealed later half, which sits in or straddles the split. The per-wallet replication
   condition (every wallet with at least 300 fills or 30 markets) will then compare a main-ladder instance with two
   deep-bid/slow-family instances.
2. **The side model's single free parameter is assumed to be the fair's volatility.** Every iteration since 11 fits "k".
   Q3 shows that the blocks differ by a tilt that flips at every edge size, and that no single (edge, cheapness) law
   transfers between them.
   - A volatility multiplier is one way to produce such a tilt.
   - An asymmetric ladder is another: a different half-spread on the favourite and the underdog, or a center pulled
     toward 0.5. That would leave the fair at k 1.0 on both blocks.

   The two readings send the search for a driver to different places: the fair's inputs, or the ladder configuration
   per instance. The investigation has measured only the at-touch post side, which cannot separate them.
3. **The price law is assumed to be R7 everywhere.**
   - On the thin non-BTC books, neither R7 (0.18-0.56) nor a Binance fair (<= 0.30) prices the later fills (Q5).
   - Those later fills hold the module's money (+5-10% per $ on 4h and hourly).
   - The natural anchor on a thin book is the best bid of the other makers. It is recorded for the alt 5m/15m (dw_clob)
     and for the 4h (clob_crypto) books, but it has never been scored.
4. **The outcome bar is judged from the BTC 5m weekday replay only.** The iteration-14 panel critique (item 3) still
   stands: no strict replay has been run on the idle families.
   - There the opening fill sets the market's net side in 91-92% of markets.
   - The public opening posture is decoded at 0.87-0.92.
   - So the per-market correlation could be far higher than 0.21 on the half of the lot that the idle module carries.
5. **Selection is assumed to be "BTC 5m on/off by hand".** On 11-01 the operator's unit of switching is
   (instance, module):
   - Chainlink-settled main ladders were concentrated in one instance;
   - the extreme-price bids and the Binance-settled families stayed on in the other two.

   That is a different selection component from the one in `components.selection`.

## Proposals (ranked by the chance they close the gap)

### P1. Decode per engine instance from the 11-01 split onward (new: the "three copies" assumption broke; a strong form of X95, X123 and X138 for the post-incident configuration)

- **Hypothesis.** After the 10-31 incident, the operator reconfigured the instances individually.
  - bosona runs the mid-price BTC 5m/15m ladder and the alt 5m/15m quoting.
  - almach and mo-money run the decided-window extreme-price bids (<= 0.10, >= 0.90) and the Binance-settled
    hourly/daily families. They form one configuration: both started BTC in the same second, 07:15:03.
  - The post-incident blocks (the 11-01 development block and the later half of the next exam lot) must be decoded and
    reported per instance.
  - The 11-01 quote-side value (0.60) describes bosona's ladder in its post-incident configuration.
- **Why it fits.** Q1 and Q2. The split never happened in 84 earlier blocks:
  - post multiplicity fell from 0.29 to 0.04 triplets;
  - the BTC 5m mid-band orders were 90 / 2 / 0;
  - the BTC 15m median fill price was 0.05 for almach and mo-money against 0.25 for bosona;
  - the slow families are equal across the three wallets.
- **Test.**
  1. **Instance-module map** for every development block since T0 (10-31 00-06, 12-18, 11-01 06-12, then each new
     one), per 15-min slot:
     - fills per wallet × family × price band (<= 0.10, 0.10-0.90, >= 0.90) from activity;
     - owner-attributed filled orders from the all-match calldata of the dm_clob_raw transactions;
     - pre-registered definition of "split": one wallet holds at least 0.80 of the mid-band BTC 5m fills in a slot with
       at least 20 of them.
  2. **Instance fingerprints** before 16:53 on 10-31, in 17:06-18:00 (after the ad-hoc restarts) and on 11-01:
     - salt slope (orders/s);
     - size classes;
     - start lag after the window open and withdrawal time before the end;
     - R7 within a tick, per wallet;
     - the extreme-price share.
  3. **Natural experiment for the side reading.**
     - Compare bosona's own filled orders (calldata owner) on 10-31 14:00-16:53 with those on 11-01 07-12:
       match-clock posture k 1.0, cheaper token, and the ladder tilt of P2.
     - If bosona's per-fill posture falls with the noise ratio (8.2 → 0.92), the regime reading survives within one
       instance.
     - If bosona's tilt is unchanged and only the instance mix changed, the "regime-specific quote side" finding is
       withdrawn.
  4. **Exam preparation.**
     - Run evaluate() per wallet on 11-01 06-12 (r9 block, R7, side, presence) and pre-register how each instance's
       metrics will be reported.
     - The universe stays all-family, so scope is met for every instance.
     - Freeze per-instance side and price descriptions: main ladder = R8 public side; deep-bid instances = the
       decided-window branch, which is the cheaper-token baseline and must be stated as such.
- **Data.**
  - Activity of the three wallets for the development blocks.
  - The dm_clob_raw transactions and their calldata (Polygon RPC, the RE's code14/code15 readers).
  - dy_rtds, dm_bnf, Gamma.
- **Signature if true.**
  - The split holds for the whole 11-01 06-12 block and the next development blocks.
  - almach's and mo-money's fingerprints changed together at their restart or at 01:00, and bosona's did not.
  - bosona's own fill-level tilt on 11-01 matches its pre-incident tilt within about 0.05 (10-31 cheaper share 0.59,
    11-01 0.66 from activity; redo it on the match clock).
  - Then the side, price and presence components are re-scored per instance. The per-instance rules are what the
    examiner's per-wallet replication will see.
- **If false.** If the split is a transient of the first hour after the listing gap (the instances rejoin within the
  block), record it as an operational event and keep the pooled rule. The noise-regime reading stays a hypothesis
  either way until a clean-regime block with all three instances is scored.

### P2. Separate the ladder's center from its favourite-underdog spread asymmetry on both blocks (strong form of X116, X80 and X27; the "k" parametrization assumption)

- **Hypothesis.** What moved between 10-31 and 11-01 is a tilt in the ladder, not the volatility of the fair.
  - The ladder center c (the midpoint of the instance's implied bid and ask on Up) follows the latest published
    Chainlink digital at about k 1.0 on both blocks.
  - The half-spreads differ by outcome: the favourite tighter on 10-31, the underdog tighter on 11-01.
  - The at-touch post side mixes the two.
- **Why it fits.** Q3:
  - the tilt flips at every edge band;
  - a fixed (edge, cheapness) law transfers at 0.47-0.58;
  - "best k 2-3" on 11-01 equals the cheaper-token score (0.65 vs 0.63-0.64), which is what a uniform underdog
    preference would also produce;
  - the ladder-center k of 10-31 (X116: 5m 1.14, 15m 1.37) was never measured on 11-01.
- **Test.**
  1. Units: each public publish P_i (dy_rtds) in 10-31 17:29-18:00 and in 11-01 07:00-12:00 (bosona-only, Q1).
  2. From dm_clob_raw, take the instance's visible schedule-size levels on both outcomes 300 ms after P_i: exact
     500 × 2^k adds at non-extreme prices (purity 0.91). On 10-31 use triplets for purity.
  3. Read the top rung on each outcome (b_up, b_dn). Compute:
     - the center c = (b_up + 1 - b_dn) / 2;
     - the half-spread h = (1 - b_dn - b_up) / 2;
     - the asymmetry a = (c - favourite's top rung) - (c - underdog's top rung), in favourite and underdog terms.
  4. Per block:
     - regress c - mid on F_k - mid for k in {1.0, 1.4, 2.0, 3.0} (`code12/quote_k.py` already does the center part);
     - report the slope, the intercept and the k that fits c best;
     - report the distribution of a.
  5. No fitting across blocks. Pre-register the two readings:
     - **(i) k reading:** the best k for c moves from about 1 to 2-3, and a ≈ 0 on both blocks;
     - **(ii) spread reading:** the best k for c is within 0.3 on both blocks, and a changes sign.
- **Data.** dm_clob_raw (both blocks), dy_rtds publish ms, dm_bnf futures mid, Gamma priceToBeat.
- **Signature if true (reading ii).**
  - c follows the k-1.0 posture with R^2 of at least 0.4 on both blocks.
  - a is negative on 10-31 (favourite closer) and positive on 11-01.
  - Then the information component is one law across regimes and instances. The side failure is a per-instance spread
    parameter, which P1's fingerprints may predict (it is set at a restart, not by the market).
  - The counted side description should then be rewritten: the fill side is the takers' choice within a skewed,
    asymmetric ladder.
- **If false (reading i).** The volatility of the fair did move. Look for its driver in the fair's inputs: a
  Chainlink-noise-dependent sigma, or an instance-specific configuration loaded at the 01:00 restart (P1 step 2).

### P3. Measure the outcome criterion where it can be met: a strict per-market replay of the idle module's decoded opening (strong form of X174 and of the iteration-14 panel P2 step 3, never run)

- **Hypothesis.** On the idle half of a weekend lot, the per-market strict-fill PnL correlation can reach 0.5:
  - the module's per-market PnL is set by its net side;
  - the net side equals the first fill's side in 91-92% of markets;
  - the public opening posture decodes that side at 0.87-0.92.

  The "0.47-0.53 oracle ceiling" is a statement about BTC 5m weekdays.
- **Why it fits.**
  - `nb_persist`: the majority side equals the first fill's side in 91-92% of markets.
  - T1d/T1e: the opening posture is 0.866 VALIDATE, 0.924 STUDY and 0.882 BUILD.
  - 77-85% of the markets are one-sided.
  - Sizes are fixed per family, so a replay can use the exact sizes.
- **Test.**
  1. Units: every non-BTC market in each half of the three weekend mock lots (X174) and in the development blocks
     after T0. Include the alt 5m/15m markets, and the hourly and 4h markets with their settlement references (Binance
     stand-in, flagged).
  2. Replay rule: at the open, post the family size on the public-posture side (k 0.7 against the last clean print
     <= T - 2, frozen as in T1d) at the last clean print - 0.01, and at the recorded touch where the book exists. Strict
     fills: trade-through on the clean taker tape after 2 s, `match_slack` 2. Hold to resolution.
  3. Report per market:
     - Pearson and Spearman against the cluster's per-market PnL, per half and per wallet (P1);
     - the same with the cluster's own opening side as an oracle;
     - the pooled all-family correlation of each half, with BTC 5m/15m from the existing replay.
- **Data.** Tapes of the non-BTC markets (most are already cached for nb_public / nb_side), Binance 1-s per symbol
  (`bn1s/`), activity.
- **Signature if true.** Per-market correlation of at least 0.5 (both measures) on the idle halves with the public
  posture, and an oracle-side correlation of at least 0.6. The outcome criterion is then reachable on the half the idle
  module carries, and the account of the gap must be split by half.
- **If false.** Below 0.3 even with the oracle side means the later two-sided fills, where the money is, dominate
  per-market PnL. That is then the quantitative reason the outcome bar fails on the idle half too.

### P4. Price on thin books: the best bid of the other makers, not the stale last print (new; the "R7 everywhere" assumption)

- **Hypothesis.** On the non-BTC books, the instance's bid is set relative to the best bid of the other makers (it
  joins it or improves it by a tick). R7 works on BTC 5m only because there the last trade sits at that touch within
  0.1-1 s.
- **Why it fits.**
  - Q5: a Binance fair is at most 0.30, the last print 0.17-0.51, and R7 0.18-0.56 within a tick on STUDY later fills.
  - The anchors are 2-108 s old (iteration-14 panel, Q4).
  - The opening fills sit in empty books, where the instance's bid is the touch.
- **Test.** On the recorded books of the development blocks from 11-01 06:00 (dw_clob for the alt 5m/15m, clob_crypto
  for BTC/ETH/SOL 4h):
  1. For each cluster fill outside BTC 5m/15m, rebuild the book just before the match without the instance's own
     family-size level.
  2. Score these laws against R7 and against the trivial anchors, per family and per instance:
     - price = best other bid + 0.01;
     - price = best other bid;
     - price = best other ask - 0.01.
  3. Hourly and daily books are not recorded. Start a small recorder now with `tools/live.py` Writer for the BTC/ETH/SOL
     hourly and daily books: hard stop 11-03 00:00, under 100 MB, entered in `live_lab`.
- **Data.** dw_clob, clob_crypto, activity, the calldata of the matched transactions (original order prices); the new
  recorder for hourly and daily.
- **Signature if true.** One touch law is within a tick for at least 0.80 of non-BTC fills in every family, and the
  examiner's pooled all-family price stays at or above 0.80 on the idle half.

  If it is "join the touch", say so: that is a trivial anchor and a valid description.
- **If false.** The bids are fixed-level resting orders. Decode them as a ladder from the calldata original prices
  (`fixed_price_ladder_backtest`).

## Notes for the RE

- **Do P1 first.** It is all activity and calldata on disk. It decides how every other number of the 11-01 block, and of
  the exam's later half, should be read. Until it is done, tag "regime-specific quote side" as a hypothesis in
  FINAL_RULE and in `components.side`.
- **Where to stop looking.** These ran here and failed, so nobody needs to repeat them:
  - A fixed (edge, cheapness) law across blocks transfers at 0.47-0.58 (Q3).
  - Day-level calibration chasing (the realized 5-min move ratio, the favourite's excess win rate, trailing versions)
    does not track the daily tilt (Q4; |rho| <= 0.40).
  - A Binance-fair price on the non-BTC later fills is at most 0.30 within a tick (Q5).
  - In BUILD/STUDY the extreme-price bids never kept running while the mid-price ladder was off (Q2), so before 11-01
    the module switched as one piece.
- **Exam bookkeeping.** The split began inside the sealed stretch 10-31 18:00 - 11-01 06:00, and bosona's mid-band share
  on 11-01 is 0.91. Report per-wallet metrics for the exam as separate rules where the instances differ. A pooled number
  that hides an instance-level difference will not survive the per-wallet replication condition.
