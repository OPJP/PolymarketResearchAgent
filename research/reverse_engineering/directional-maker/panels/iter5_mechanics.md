# Panel after iteration 5: mechanics and on-chain forensics

Lens: how the orders are built and what the order record says about the decision (calldata, salts, ladders, requote
cadence, complement pairs, queue position, size controller). Written 2026-10-31 ~15:30 UTC. I used development data only:
the released lot's first half (STUDY, 2026-10-23..26) case by case through `b1_orders_lot.parquet` with `tag == 'study'`,
Binance futures 1-s files for 10-22..26, the live activity of 10-31 00:00-06:00 and 12:00-14:43 UTC, and the RE's raw
recorder (`dm_clob_raw`, read with `code5/rawread.iter_dm`, which refuses sealed blocks) for 14:30-14:45 and 14:50-15:10
UTC of the current development block. I did not touch VALIDATE (10-27..30) cases or anything sealed. Check scripts are in
my scratchpad (`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`pair_check.py`, `pair_check2.py`, `pair_check3.py`, `pair_check4.py`; the size and run-length checks were inline reads
of `b1_orders_lot.parquet` and `fut1s/`).

## What my checks found (inputs to the proposals)

1. **The two sides of the ladder are one quote with a fixed total spread.** 14:50-15:10 UTC, 2,575 multi-wallet exact-500
   bursts, 906 matched pairs. For each Up burst I took the highest Up burst and the highest Down burst (as BUY prices) of
   the same window in the previous 1.5 s. The sum of these top rungs has a median of **0.88** (IQR 0.85-0.90,
   MAD 0.02). It is the same in BTC 5m and BTC 15m (0.88 / 0.88), flat across price levels (0.87-0.89 from mid 0.1 to
   0.9), and drops to 0.77 only with 60-120 s left in BTC 5m (n 48). This matches the paired cost of its VALIDATE pairs
   (0.89). A single side's burst minus the token mid has MAD 0.03-0.04, so most of the RE's residual (0.037) is rung depth
   and skew, not noise around one price.
2. **The ladder re-anchors to the current mid, not a lagged or smoothed one.** Burst price on the token mid at lags
   0 / 0.5 / 1 / 2 / 5 / 10 / 30 s: slope 1.00 / 1.00 / 0.99 / 0.98 / 0.93 / 0.86 / 0.74, residual MAD 0.039 / 0.040 /
   0.039 / 0.042 / 0.050 / 0.066 / 0.103 (EMAs: 1 s 0.038, 10 s 0.048, 30 s 0.064). Within a tick only 13-16% at best.
   The "dip-buying ladder on a slow anchor" idea is rejected; I do not propose it.
3. **The skew (implied mid of the pair minus the PM mid) is small and does not follow recent futures moves.** Median
   -0.025, IQR -0.045..0.00, corr 0.98 between implied and PM mid. Correlation of the skew with the futures bookTicker mid
   move over the last 0.25 / 1 / 3 / 10 / 30 s: -0.06 / -0.16 / +0.03 / -0.03 / +0.02. It does not predict the next PM mid
   change either (0.02). This is a level test without the TWAP-60 digital fair and with uncalibrated CLOB-vs-Binance
   server clocks, so it does not settle the question. But a futures-move skew is not obvious.
4. **Single 500 adds and 2-3-wallet bursts sit at the same depth.** Median 7 ticks below the touch for n = 1, 2, 3;
   6.4-7.5% at or through the touch. There is no "one lead wallet at the touch, the others deep" structure.
5. **A zero-fill window was fully quoted.** Window btc-updown-5m-1793457300 (14:35-14:40 UTC) had **211** multi-wallet
   bursts, median 8 ticks below the touch, 3.8% at the touch, and **0** cluster fills (activity read through 14:43 UTC).
   The windows before and after had 142 bursts / 17 fills and 254 bursts / 23 fills. On 10-31 00:00-06:00 UTC ten BTC 5m
   windows have no cluster fill, all isolated (runs of one or two windows) between windows with 5-84 fills.
6. **Most short "off" gaps are probably sampling zeros.** STUDY: 569 of 1,152 BTC 5m windows have no cluster maker fill.
   405 of them (71%) sit in two long runs (10-23 20:39 -> 10-24 15:25 and 10-24 evening -> 10-25 ~13:00), and 164 (29%)
   are gaps of 1-6 windows (84 isolated). In the old VALIDATE (NOTES, iteration 1) 62% of inactive windows were in runs
   shorter than 1 h.
7. **Size is one shared controller with power-of-two levels.** STUDY calldata base sizes are 500 / 250 / 62 (BUILD 1000 /
   500 / 250 / 125), i.e. 500 x 2^k with k = +1..-3, plus the one-fifth level (100 / 50 / 12). Switches happen in all
   three wallets in the same second: 10-23 04:20:56 / 56 / 57 to 250, 02:35:03 / 03 / 05 to 500, 10-25 15:02:20-27 and
   22:05:06-08 to 500. 562 of 575 STUDY windows use one class only. Outside the weekday 12-21 UTC session, 26 of 343
   windows run at 500. They come as 2-5-minute bursts that often start at a window open (02:35:03, 22:05:06, 12:05:21).
   They are predicted by futures realised vol before the open: AUC 0.70 / 0.72 / 0.70 for 60 / 300 / 900 s vol, and 0.72
   for |60-s return|. That is a small sample, but a public input that moves the controller.

## Critique

1. **The on/off cap is overstated, because the oracle used the label.** The 0.862 "oracle on/off" score set p = 0 in
   every window without a cluster fill, so it handed the model a window-level aggregate of the label. Finding 5 shows
   a zero-fill window can be fully quoted, and finding 6 puts 29-62% of non-participating windows in short gaps. The
   true quoting oracle (long runs only) is weaker. The rest of the gap, within quoted windows, is the fill process:
   whether a rung meets a taker. "The binding gap is an operator schedule with no public correlate" should be
   re-measured before it steers the next iteration. In STUDY the real schedule is two events.
2. **"Its filled orders were posted 0-5 s before the match (46% within 1 s vs 6% at random)" uses the wrong null.** The
   null is "the same level 20 s earlier". With every rung re-posted about once a second (exact-500 lifetime median
   0.69 s), any live cluster order is young, so most fills would be "posted within 1 s" even if posting were not
   reactive at all. The right null is the age of the cluster's live rungs at the same distance from the touch at random
   moments (length-biased). As it stands, this result says nothing about whether it posts in reaction to a coming
   taker.
3. **X20 misreads its own numbers.** Burst minus mid is -0.085 when flat and -0.18 when long > 200 shares (n 77). That
   is a downward skew of the bid on the side it holds: the textbook inventory skew. It contradicts the iteration-1
   reading "adds to the held side" (which is flow persistence; see the iteration-4 mechanics panel's P6). The pair
   decomposition below measures this cleanly.
4. **The single-side quote fit mixes three things.** It fits spread, skew and rung depth in one regression on a token
   mid that the ladder itself re-anchors to. The quote within a tick (21% held out) cannot improve that way. The top-rung
   pair sum is an invariant (MAD 0.02) that removes the spread, which leaves the skew, the only directional part.
5. **The live plan makes a quote-level rule unexaminable.** The next step says "restart rawrec in every development
   block". The examiner's next lots are the future sealed blocks, and the shared recorder shows only 10-11% of the
   bursts as exact increments. If the raw feed does not run through the sealed blocks (the `Writer` files those records
   into `sealed/` by itself), no rule or label that uses the cluster's rungs can be scored. Disk is the constraint: hour
   14 of `dm_clob_raw` is 22.7 MB, about 0.5 GB a day, above the 300 MB cap. A reduced format would fit several days:
   deltas of the schedule sizes (5, 12, 50, 62, 100, 125, 250, 500, 1000) plus the touch every 100 ms.
6. **The presence target may be infeasible in 10-s bins for any rule. Measure that before chasing it.** In the live
   block, knowing the cluster's own current quote (at the touch or not) ranks fills in the next 10 s at AUC 0.54, and
   quote minus best bid at 0.62 (`iter5_live_k`). If even perfect knowledge of its quote at the bin start plus public
   activity stays well below 0.85, the presence branch is capped by the market's path, not by an undecoded input. The
   selection branch (which print fills it), where the quote state at the print time is the decisive input, is then
   the target to pursue. That would also be the quantitative account of the unexplained part that the brief asks for.

## Proposals (ranked by the chance they close the gap)

### M1. Decompose the ladder by its complement pair: fixed total spread, one skew, and identify the engine's fair from the skew (new; strong form of B3, X19 and B4)

- **Hypothesis.** The engine sets one center c(t) and a total spread 2H(time left) for both outcomes: top rung on Up =
  c - H, top rung on Down = (1 - c) - H, deeper rungs at fixed offsets below. c = PM mid + skew, with skew =
  lambda x (F(t - tau) - PM mid) + kappa x own net inventory. With a common lambda on both sides the RE's own fit
  (0.69 mid + 0.25 F - 0.055) already implies a constant pair sum, which is what I observe (0.88). The directional
  decision is the skew alone; H only sets how deep the ladder sits.
- **Why it fits.** Finding 1: top-rung pair sum 0.88, MAD 0.02 in 5m and 15m, flat in price, widening only in the
  last two minutes. It equals the VALIDATE paired cost of 0.89 (the profit centre in busy periods). The single-side
  residual is twice as wide. X20's -0.18 vs -0.085 by inventory is a skew. Finding 3 shows the skew is small (MAD 0.02),
  so it is a precise target.
- **Test.** In each development block, from `dm_clob_raw` (bursts with n >= 2):
  - match Up and Down top rungs (highest burst price per side within 1.5 s; also with explicit rung tracking: adds
    minus removals of exact-S at each level);
  - compute 2H = 1 - (q_up + q_down) and skew = (q_up - q_down)/2 - (mid_up - 0.5);
  - regress the skew on (TWAP-60 digital fair of the futures bookTicker at t - tau, tau in 0-1000 ms, vol = realised
    x k) minus the PM mid, on own net inventory (Up minus Down shares, from activity; report with and without), and on
    time left;
  - fit H on time left and vol;
  - calibrate the CLOB and Binance server clocks first, using trades that print on both sides of a block.
  Fit on one block (14:04-16:00 today), test on the next development block (2026-11-01 06:00-12:00 UTC).
- **Data.** `dm_clob_raw`, `dm_bnf`, `dm_rtds` (already recorded), live activity for inventory.
- **Signature if true.** H depends only on time left (and maybe vol), with day-to-day stability within a tick. The
  skew is explained with R^2 >= 0.5 by lambda (F - mid) and/or kappa x inventory, with stable coefficients on the
  held-out block. The top rung on each side is then predicted within a tick for >= 60% of bursts (now 21%). If the skew
  is pure inventory (lambda about 0), the engine is a symmetric two-sided market maker around the PM mid. Its "side" is
  then the taker's choice plus an inventory skew, and the side component should say so: it is a valid description
  under the brief's proviso.

### M2. Take the selection branch with a rung-reach classifier, and measure the presence ceiling first (new; changes the unit to the print, uses M1)

- **Hypothesis.** A taker print at price p on side s fills the cluster when its top rung on s, from the frozen quote
  function of M1 at the print's match clock minus the reaction lag, is at or above p. Whether a print happens is the
  market's path. Whether a given print reaches the cluster is the cluster's quote. So selection AUC >= 0.80 with recall
  >= 50% at lift >= 3 can be reached even if 10-s presence cannot.
- **Why it fits.** R2's selection is 0.685, and its within-window strata were never significant (p 0.04-0.35). The
  missing input is exactly where its rung stands relative to the print. The live block shows the quote state is
  observable and anchored to public inputs (mid, futures, time left). Critique 6: knowing its current quote at the bin
  start predicts 10-s fills at only 0.54-0.62, so presence is path-bound.
- **Test.**
  1. Ceiling (live, development blocks): AUC of "cluster filled in [t, t+10)" from (a) the observed cluster top rung
     minus the best bid at t, (b) (a) plus public activity, (c) (b) plus the bin's own future taker flow
     (diagnostic). If (b) is below about 0.80, write the presence cap down with these numbers.
  2. Selection pilot (live): for every bid-hit print on s, gap = observed top rung - p; AUC, recall and lift of
     "gap >= 0" within windows.
  3. Historical, examinable: rebuild the predicted rung from public inputs only (mid from the clean tape's last
     bid-hit / ask-lift, futures aggTrades at ms, time left), with M1's frozen H and lambda. Score STUDY prints case by
     case and VALIDATE prints in aggregate. Compare with the activity-only selection model (0.743-0.744) and the
     rotation null, stratified within windows.
- **Data.** `dm_clob_raw` and `dm_bnf` for 1-2; STUDY tapes, calldata match clocks (`b1_takers_study.parquet`) and
  futures aggTrades (`aggfut_*`, `fut1s/`) for 3. For the exam: a reduced-format raw recorder running through sealed
  blocks (critique 5) if the rule takes the observed book; the historical version needs only tapes and futures.
- **Signature if true.** Within-window selection AUC >= 0.75 live and >= 0.70 historically, above every rotation draw
  (it is about 0.66 now), recall >= 50% at lift >= 3. The live ceiling (b) for 10-s presence is <= 0.80, which shows
  the presence target is path-capped and gives the quantitative account.

### M3. Separate "not quoting" from "quoting but unfilled", and re-run the on/off cap with a quoting oracle (strong form of X9 and H13/H20)

- **Hypothesis.** Window non-participation mixes two things. One is a few true off regimes (two runs in STUDY, the
  13-h overnight runs in the old VALIDATE). The other is many quoted windows where no taker reached a rung (Poisson
  zeros; finding 5). The window-level oracle that gave 0.862 counted both as "off", so it leaked the label. With a
  quoting-only oracle the cap is lower, and the gap moves into the fill process.
- **Why it fits.** Findings 5 and 6: the 14:35 window carried 211 cluster bursts and no fill; 29% (STUDY) to 62% (old
  VALIDATE) of inactive windows are in short gaps; the ten zero-fill windows of 10-31 00-06 UTC are isolated.
- **Test.**
  - (a) Live: per BTC 5m window in every development block, cluster bursts vs fills. Report P(0 fills | quoted) and
    its link to the window's price range and taker volume.
  - (b) Historical: a hurdle / Poisson model of fills per window given "quoted". Fit it on public flow and range in
    the long-run-on stretches of BUILD and STUDY. Then test whether the short-gap zeros fit its predicted P(0) (a
    likelihood-ratio test against an extra off state).
  - (c) Recompute the oracle score with off = the long runs only (>= 1 h), and with off = predicted P(0) > 0.5.
  - (d) Restrict the "schedule" problem to the true switch events. Time them from the edges of the long runs and from
    the size controller (M5).
- **Data.** `dm_clob_raw`, live activity; STUDY fills and tapes; BUILD fills.
- **Signature if true.** Most short-gap zeros are consistent with P(0 | quoted) (LR test not significant). The
  quoting oracle lifts presence much less than 0.862 (e.g. under 0.80). The true off events are a handful of operator
  switches, best described as such in the selection component. Effort then moves to M1 and M2.

### M4. Improve or join? Queue forensics of each filled order, with the right age null (strong form of X15 and X16)

- **Hypothesis.** Its at-touch fills come from one of two mechanisms. (i) It improves the best bid by a tick when its
  rung crosses the touch and is hit while alone at the new level. (ii) It joins an existing level behind the queue and
  is filled when a taker clears it. The two give different rules: (i) is an event trigger "q* > best bid", (ii) is
  level depletion. The current evidence cannot tell them apart, because the age statistic has no proper null
  (critique 2).
- **Why it fits.** 63% of filled orders were posted "at the touch", and 29% matched within 250 ms. The calldata queue
  order puts the cluster last at its price in 56.5% of shared levels (iteration-4 mechanics panel). The tape version of
  level clearing (X16) was weak (ratio 0.63), but the tape cannot see the level.
- **Test.** For every live cluster maker fill, from `dm_clob_raw` before its add:
  - the level size at its price before the add (0 means it created or improved the level);
  - the best bid before the add;
  - the depth ahead of it at the match (adds before it minus removals and earlier fills at that level);
  - its age, compared with the residual age of all live cluster rungs at the same tick distance from the touch at
    random moments (length-biased null).
  Also compare the improve-and-filled share with other makers' fresh orders.
- **Data.** `dm_clob_raw` (server ms), calldata of the live txs (original size and limit), live activity.
- **Signature if true.** Mechanism (i): most fills have level size 0 before the add, age under 250-500 ms, and are
  younger than the residual-age null. Then the at-touch trigger is a sharp event model. Fit P(improve | q* - best bid)
  and use it as the presence and selection input. Mechanism (ii): the depth ahead at the fill is used up by that print,
  ages match the null, and P(fill) steps with print size over depth.

### M5. The size controller as the observable state machine of the engine: power-of-two levels, set for all wallets at once, partly vol-triggered (new; strong form of C4/C5/H42)

- **Hypothesis.** One controller sets a per-window size multiplier 2^k (k = +1..-3) for all three wallets. A session
  default (500 in the weekday US session, 62 otherwise) is overridden by short-term volatility: up to 500 for about one
  window after a futures vol spike at night. The long off runs are the controller's "0" level, set by the same inputs or
  by hand. Its transitions are dozens of exactly timed events per day: a far better place to learn the controller's
  inputs than two off runs.
- **Why it fits.** Finding 7: switches in all three wallets in the same second; 562 of 575 windows with one class; the
  2^k set; night 500-bursts of 2-5 minutes, often from the window open, predicted by futures vol at AUC 0.70-0.72
  (n 343 windows, 26 bursts, STUDY). The first long off run began a minute after a 500 -> 62 switch (10-23
  20:37-20:38) and ended with a switch straight to 500 (10-24 15:25:50). The second began and ended at 62.
- **Test.**
  - Per window, the base size class from calldata original sizes (BUILD from filled sizes, lower bound), STUDY case by
    case, VALIDATE in aggregate.
  - A discrete-time hazard of up and down transitions on futures realised vol and |return| (60-900 s), the previous
    window's range and taker volume, time of day, and own trailing PnL (reported separately).
  - Fit the hold time after an upgrade. Check whether the same thresholds precede the start and end of the long off
    runs, and whether BTC 15m and ETH windows switch in the same seconds (one global multiplier or one per market).
  - Live: the size of the burst triplets per window, in real time.
- **Data.** `b1_orders_lot.parquet`, calldata of other-market txs (`othstudy_*`), `fut1s/`, live raw book.
- **Signature if true.** A threshold rule (e.g. 300-s futures vol above x at the open -> 500 for one window) explains
  >= 80% of off-session 500 windows on held-out days, and the switches are global across markets. If the same variable
  with hysteresis also precedes the off runs, the selection component gets its first public correlate. Size also enters
  the PnL metric (worth little on VALIDATE per X22, but it is the decoded size component).

## Notes for the RE

- Run order: M3(a) and M1 can start on today's recording now (14:04-18:00 UTC). M4 needs the fills of 14:04-18:00
  joined to raw adds, which `code5/live5.py` already does in part. M2's ceiling can run on the same block. M5 is
  historical and cheap.
- For the exam route, move `rawrec.py` to a reduced format and let it run through the sealed blocks (hard stop, `Writer`
  filing). Otherwise nothing measured in the live lab can be examined.
- Please do not count "posted just before the match" as evidence of reactive quoting until M4's null is in.
