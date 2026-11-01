# Panel after iteration 17: mechanics and on-chain forensics

Lens: how the orders are built and what sets their price and side. The main finding of this panel is about R8c, the
NYSE-open rule. **R8c is most likely a volatility input that the quote model gets wrong, not a calendar override.**

- The weekday BTC 5m window that starts at 13:30 UTC has the highest forward volatility of any 5-minute slot of the
  weekday. It is also the only slot whose forward volatility is far above the trailing 300-s volatility that R8's
  posture uses (2.6x).
- Any engine with a forward-looking or scheduled volatility would pull its fair toward 0.5 there. It would then buy the
  token the opening move made cheap, which is exactly what R8c describes.
- The investigation has tested only trailing volatility measures: G3 (trailing 2-h realised vol), X74 and X117 (implied
  vol at the block level). It has never tried a scheduled one.

Written 2026-11-01, 11:40-12:40 UTC.

**Data I used.** Development and released data only (checked with `tools/sealed.py directional-maker`):
- BUILD 10-08..22: `spot_btc_1s`, `activity_*`, `windows_5m`, `it17_side_decisions`;
- STUDY 10-23..26, case by case (the released lot's first half, the convention the reverse engineer uses):
  `it12/typed_fills`, `calldata/study_*`, `othstudy_*`, `exam/activity_*`, `b1_cluster_orders_study`.

Nothing from VALIDATE was read case by case. No sealed block was opened.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`open_vol.py`, `seas_side.py`, `open_sweep.py`, `open_takers.py`, `salt_rate.py`, `taker_slack.py`,
`taker_slack2.py`, `taker_slack3.py`, `redeem_cap.py` and `merge_stop.py`. Each runs in under a minute and stays
under 300 MB.

## What my checks found

1. **The NYSE-open window is the volatility outlier, and only against a trailing estimate** (`open_vol.py`, BUILD,
   11 weekdays). Forward vol means the realised vol of 1-s Binance returns inside the window. Trailing vol is the same
   measure over the 300 s before the window starts.

   | slot (UTC) | forward vol, median (bp / 5 min) | trailing vol, median | ratio |
   | --- | --- | --- | --- |
   | **13:30** | **17.0** | **6.8** | **2.50** |
   | 13:35 | 16.7 | 17.0 | 0.98 |
   | 13:40 | 15.9 | 16.7 | 0.95 |
   | 14:00-14:10 | 15.2-15.8 | 13.4-15.5 | 0.98-1.16 |
   | all weekday slots | 5.7 | | 0.98 |

   - At 13:30 the ratio is 1.43-3.59 on every one of the 11 days (median 2.6).
   - The next window (13:35) is just as volatile, but its trailing 300 s already contain the open, so the two measures
     agree there.
   - This matches iteration 17's result that the 13:35 window follows the posture on VALIDATE (0.976).
2. **Swapping in a scheduled volatility turns the posture at the open without a calendar rule** (`seas_side.py`, BUILD,
   crude). Settings:
   - Binance stand-in strike and spot;
   - mid approximated as the fill price + 0.01;
   - the profile is in-sample: the median forward vol per weekday slot over BUILD itself.

   My posture agrees with the per-decision labels in R8's file only 52% of the time, so only the contrast within this
   one method means anything. Replacing 1.4 x v300 with 1.4 x max(v300, slot profile) gives:

   | decisions | 1.4 x v300 | 1.4 x max(v300, slot profile) |
   | --- | --- | --- |
   | open window (661) | 0.47 | 0.82 |
   | other non-decided | 0.452 | 0.459 |
   | of which \|edge\| < 0.05 | 0.461 | 0.484 |

   The cheaper token takes 0.988 of the open window. This is a pointer for P1, not a test.
3. **The open-window fills are fresh rungs at the touch, bought by many takers** (`open_sweep.py`, `open_takers.py`,
   STUDY).
   - On 10-23 there are 75 fills on Down. They come at 34 distinct prices between 0.11 and 0.25, 60 of them in the first
     45 s, while the Up mid stood at 0.80-0.83.
   - There is one cluster order per transaction (1.01 fills per tx, none at two cluster prices), and all are of size 500.
   - So this is a rung that is re-posted and filled repeatedly, not a deep straddle swept by one taker.
   - The 107 open-window fills have 66 distinct takers; the largest takes 11%. There is no single predictable opening
     counterparty, so an "October fade-the-opener" story is unlikely.
4. **The cluster's own taker orders do not reveal its valuation** (`taker_slack*.py`, STUDY, 955 taker BUY orders).
   - The limit (calldata makerAmount / takerAmount) equals the execution price in 57% of orders.
   - In BTC 5m it is 1-5 c above the execution price in 60% (median 0.01). The gap is wider in the last 30 s (mean
     0.035).
   - Corr(limit, execution price) is 0.94. Corr(limit, 1 - the held side's average cost) is 0.10.
   - These are marketable limits with a small buffer, so they cannot serve as an uncensored readout of the fair. The fee
     in the activity amounts is exactly 0.07 x p(1 - p) per share.
5. **Collateral does not bind** (`redeem_cap.py`, BUILD).
   - The cost per (window, outcome) is a median of $77-91, with p99 at $1.1-1.2k. Each wallet's working capital is
     about $22-49k.
   - The REDEEM transactions run on a 300-s timer at second :04-:06 of the minute, 59-98 s after the window ends, in all
     three wallets. Capital is recycled in about a minute.
   - So a hidden budget or balance state is not what drives selection or the cheap-token share. I drop that direction.
6. **Merges are pairing housekeeping, not a close-out** (`merge_stop.py`, BUILD).
   - 414-505 windows per wallet have a merge. In 39-48% of them the wallet trades again after the first merge.
   - The merge comes a median 1-10 s after the wallet's last trade.
   - So merge times do not read out the stop decision.
7. **The salt counter's rate is a fill-free readout of how much the engine quotes** (`salt_rate.py`, STUDY). Per
   wallet, in 10-minute bins, using every decoded cluster order from both the BTC 5m and the other-market calldata:

   | | median salt rate (orders/s) | IQR |
   | --- | --- | --- |
   | bins with BTC 5m fills | 16.6-16.9 | 13-22 |
   | bins without BTC 5m fills | 13.2-13.5 | 11-18 |
   | idle weekend days 10-24 / 10-25 | 13.4 / 12.1 | |
   | weekdays 10-23 / 10-26 | 19.6 / 18.8 | |

   The BTC module contributes roughly 3-4 orders/s per wallet. The two distributions overlap, so the size of that
   contribution has to be calibrated on the live blocks (P2).

## Critique

1. **The quote's volatility input was only ever looked for backwards in time.**
   - Every volatility test so far uses the past: the k-grid on v300 and v3600, G3's trailing 2-h realised vol, the
     running estimators since the restart (X74, iteration 11), and Deribit IV at the block level (X117).
   - A market maker in 5-minute digitals has every reason to use a scheduled forward volatility: the intraday profile
     of the US session and the release calendar.
   - The one place where trailing and forward volatility differ by 2.6x is the place where R8 is wrong 90% of the time,
     and that is what R8c patches.
   - Three other readings in the notebook point the same way:
     - the "October configuration" (cheap share at the open 0.06-0.64 from May to September, 0.997 in October) looks
       like a change of volatility estimator;
     - the margin falls as the block's volatility rises (rho -0.33);
     - the weekly k-cycle.
   - If this is right, R8c is a symptom, and the same mis-specification is spread thinly over every small-edge fill.
     That is where the side fails (miss share 0.41 at \|edge\| < 0.05).
2. **R8c is frozen on the UTC/New York clock without knowing which one drives it, and the next exam sits on the other
   side of the change.**
   - From 11-02 the NYSE opens at 14:30 UTC.
   - The 11-03 open falls in a sealed block (d + j = 5). The 11-02 open is in a development block (12-18, d + j = 4).
   - That development open is the only chance to see which clock drives the behaviour, and whether the behaviour is
     anticipatory (scheduled) or reactive, before the exam.
   - The shared feeds do not show the favourite side's deep rungs: `dx_clob` records only within 3 ticks, and
     `clob_crypto` is sparse top-10 snapshots. The full-depth `dm_*` recording ended at 11-01 12:00.
3. **The per-fill side mixes a decision with the takers' choice, and the money is in pairs.**
   - D4 shows the money is in the pairs: on VALIDATE, locked pairs made +$38.1k and directional holdings lost -$14.4k.
   - At small edges the cluster quotes both outcomes, and takers decide which leg fills.
   - A fair compressed by forward volatility makes the quote more symmetric exactly at the high-volatility moments. That
     is how a scheduled volatility would show up in the fills: as more cheap-token fills, not as a "side switch".
4. **The presence residual is read without knowing whether the module was on.**
   - 54% of the filled cells score low out of fold. Iteration 17 attributes them to "the taker's arrival".
   - That attribution holds only if the engine was quoting in those cells.
   - B1 signing times do not exist for this cluster (timestamp 0). But the salt counter is a fill-free signal of how much
     the engine is signing (check 7), so module-on and module-off minutes can be labelled historically.
   - Without those labels, selection (confidence 0.45) is fitted on fills, which are censored twice: by the quote and by
     the taker.
5. **The 11-01 trigger is still unnamed.**
   - The iteration-16 panel showed that 85-90% of the 11-01 walk steps follow neither a publish, nor a futures move, nor
     a print.
   - The futures screen (T13) found a link, but its event stamps sit at the end of a 0.5-s detection horizon, so it
     cannot measure the reaction floor.
   - Direction-agreement tests (A2, X10) cannot tell the consumed feed apart from feeds correlated with it. The lag
     floor can.

Doors this panel closes (checks 4-6, plus the counterparty part of check 3):
- taker limits as a valuation readout;
- a collateral or balance budget;
- merges as the stop decision;
- a single opening counterparty.

## Proposals (ranked by the chance they close the gap)

### P1. The fair uses a scheduled, forward-looking volatility; R8c is its symptom (strong form of B3, X74, X117 and T16/G3; suggested X215)

- **Hypothesis.**
  - The engine's sigma is a forward profile, max(trailing, scheduled). The scheduled part is the expected volatility of
    the coming minutes from the intraday or weekly profile, keyed on the exchange calendar, plus bumps at scheduled
    releases.
  - At the NYSE open the profile is 2.6x the trailing vol. The fair is pulled toward 0.5, and the cheap token is bought.
  - The same input, applied everywhere, moves the small-edge side.
  - The October step at the open is the date this estimator came in.
- **Why it fits.**
  - Checks 1-2.
  - The 13:35 window follows the posture (its trailing vol has caught up).
  - The margin falls with the block's vol, and the cheap share rises with it.
  - The open-window orders are fresh main-ladder posts made at the open (T10).
  - The open behaviour vanishes on NYSE holidays: the profile follows the exchange, not the UTC clock.
- **Test.**
  1. **Profile, point in time.** For each 5-minute slot of the New York trading week, take the median realised 1-s vol
     of that slot over the previous 4 weeks, with NYSE holidays mapped to weekend profiles. Build three variants:
     - (a) keyed on the New York clock;
     - (b) keyed on the UTC clock;
     - (c) (a) plus scheduled-release bumps: BLS 08:30 ET releases and FOMC 14:00 ET, from the public calendars, with the
       slot medians taken over past release days.
  2. **The rule.** In `code/side_sm.py`'s Chainlink posture (with the Binance stand-in fallback), replace sigma by
     k x max(v300, profile) and by k x profile. Then:
     - remove R8c's calendar branch;
     - choose the variant and k on BUILD only;
     - pre-register;
     - score per fill on STUDY (case by case) and VALIDATE (aggregate) against R8c, by \|edge\| band and in the open
       window.
  3. **History (C4).** On `it12/hist_btc.parquet` (May-October), compute the monthly cheap share in the slots with the
     highest forward-to-trailing ratio: the open, release mornings, the Sunday CME reopen. An estimator switch predicts
     that the October step shows in every one of these slots. A configured calendar rule predicts it shows at 13:30
     only.
  4. **The k-cycle.** Take the per-block best k from iteration 11 and compare it with the block's median profile / v300
     at the fills.
- **Data.** Binance 1-s klines (or the aggTrades archives) back to August for the 4-week profile. The BLS and FOMC
  calendars. All of it is on disk or public; the release calendars need one fetch.
- **Signature if true.**
  - The variant reproduces the open window (cheaper token >= 0.85 on STUDY and on VALIDATE) with no calendar term.
  - The VALIDATE per-fill side is >= R8c + 0.005, with the gain concentrated at \|edge\| < 0.05 and at the other high-ratio
    moments.
  - The October step appears in every high-ratio slot.
  - Spearman(k_best, profile / v300) >= 0.4.
  - If the profile helps only at 13:30, R8c is a configured calendar override, and P4 must decide its clock before the
    exam.

### P2. A fill-free module state from the salt counter's rate (strong form of X17, X65 and X82; serves X9, selection and the E2 presence residual; suggested X216)

- **Hypothesis.**
  - One counter per wallet counts every signed order in every market, and signed ≈ posted (X17, X23).
  - So the counter's rate between any two of a wallet's fills, in any family, equals c + Σ_m q_m · 1[market m is
    quoted], with a stable quantum q_m per market type.
  - The BTC 5m module's on and off state can then be read for every minute of history, including minutes and windows
    with no BTC fill.
- **Why it fits.**
  - Check 7: 16.6-16.9 vs 13.2-13.5 orders/s, and 12-13 orders/s on the idle weekend days against 19 on weekdays.
  - The single-instance mode on 11-01 halved bosona's rate relative to the three accounts on 10-31.
  - At the 10-31 16:53:54 switch-off the counters ran on (X82): the process lived while the module stopped.
- **Test.**
  1. **Calibrate on the live development blocks.**
     - Per 60-s bin, compute each wallet's salt rate from all its fills: the recorder's trade stream plus calldata.
     - Count the recorded exact schedule-size adds per market (`dm_clob_raw` for BTC, `dw_clob` for the alts) and
       regress the rate on the set of markets with cluster adds.
     - Checks: the rate drops by q(BTC 5m) within a minute of 16:53:54 while BTC 15m continues; on 11-01 bosona's rate
       equals the sum of the main-ladder quanta of 10-31.
  2. **Historical labels.**
     - Decode calldata for a dense sample of every family's cluster fills on BUILD and STUDY (>= 1 per wallet per
       minute).
     - Infer the BTC 5m module state per window from the calibrated quantum.
     - Add the REDEEM timer (every 300 s at second :04-:06, in all wallets) as a liveness readout, so that "process down"
       is kept apart from "module off".
  3. **Use the labels.**
     - Split the E2 presence misses (FN cells) into module-on cells (taker-censored, at the ceiling) and module-off
       cells (a selection decision still to be explained).
     - Refit selection on the module state rather than on fills.
     - Run E3 and E6 on the module-off episodes, against the drawdown since the restart (X152), the instance mode and the
       public calendar.
- **Data.** The live recordings of 10-31 and 11-01. Calldata on disk, plus about 10-20k more transactions fetched
  politely (one fill per wallet per minute over BUILD).
- **Signature if true.**
  - The quanta are stable across blocks (CV < 0.3), and the 16:53 drop equals q(BTC 5m) ± 1 order/s.
  - At least 70% of the quiet FN cells fall in module-on minutes. Presence on the fill unit is then at its censoring
    ceiling, and the remaining selection target is the module state, scored on its own labels.
  - The module-off episodes are explained by a stated trigger with AUC >= 0.85 out of fold.

### P3. Name the consumed feed by its reaction-lag floor, venue by venue (strong form of A2, X10 and X202's event study; suggested X217)

- **Hypothesis.**
  - The engine reacts to one feed, or a few, with a fixed transit and processing delay. Reactions to the feed it
    consumes therefore show a narrow lag mode above a hard floor.
  - Correlated venues give smeared lags, even when they agree with the direction of the move 90% or more of the time.
  - On 10-31 the consumed feed was the RTDS Chainlink publish (10-25 ms on the server clock). On 11-01 it is
    something else.
- **Why it fits.**
  - The iteration-16 panel's checks 2 and 4: publish-clocked steps on 10-31 and not on 11-01, and a global pass across
    markets.
  - On 11-01, 85-90% of steps follow no known event.
  - T13 links the futures but cannot measure the floor, because its event stamps sit at the end of a 0.5-s horizon.
- **Test.**
  1. Take every up-step and reset (the iteration-16 definitions) and every at-touch 500 post on 10-31 14-18 and 11-01
     07:00-09:15.
  2. For each, find the last event of each feed whose sign matches the step, and separately one of the opposite sign as a
     control. Use each venue's own exchange timestamp. The feeds:
     - Binance USD-M bookTicker E and T (`dm_bnf`);
     - Binance spot and USD-M aggTrades (archives, ms);
     - Bybit linear trades (public.bybit.com archive);
     - OKX swap trades (archive);
     - Deribit perpetual trades (history.deribit.com);
     - Coinbase BTC-USD trades;
     - the RTDS Binance relay (`dz_rtdsbn`);
     - Chainlink BTC, ETH and SOL publishes (`dy_rtds`, `dv_rtds`);
     - book events in the other recorded Polymarket markets.
  3. Per feed, report:
     - the lag histogram at 5-ms resolution;
     - the share of steps inside [floor, floor + 30 ms];
     - the same share under a ±0.5-2 s shifted null, and for the opposite-sign control.
  4. Also measure the floor relative to Polymarket-internal events (prints in the same book), so that the engine's own
     processing can be separated from each feed's transit.
- **Data.** On disk for 10-31 and 11-01. The 11-01 venue archives appear on 11-02.
- **Signature if true.**
  - One feed has >= 30% of steps inside a 30-ms band above its floor (<= 10% in the null), with the floor stable within
    10 ms across both blocks.
  - If no recorded feed shows a floor on 11-01, enter the missing feed in `dimensions`. Candidates: Chainlink Data
    Streams direct, or Hyperliquid, whose keyless websocket can be recorded from 11-02. Then add a recorder for the
    development blocks.

### P4. The 11-02 NYSE open, live and at full depth: anticipatory or reactive, two-sided or one-sided, and on which clock (pre-registered; decisive for freezing R8c before the post-DST exam; suggested X218)

- **Hypotheses**, each with what it predicts:
  - (a) scheduled volatility (P1): both outcomes' ladders widen and re-centre toward 0.5 at or just before 14:30:00 UTC,
    before any move.
  - (b) a fast reactive volatility (an EWMA): the widening lags the first >= 3-sigma futures move.
  - (c) a calendar side override: fresh bids go only on the token the move made cheap, and the favourite's rungs are
    pulled.
  - (d) a UTC-keyed configuration: the behaviour appears at 13:30 UTC (an ordinary window after DST) and not at 14:30.
- **Why it fits.**
  - Check 3: fresh 500 rungs at 34 prices, filled one by one.
  - T10: posted after the last pre-open fill.
  - Calldata cannot see the unfilled favourite-side rungs, so (a) and (c) look the same in fills.
- **Test.**
  1. Run a small full-depth recorder through `tools/live.py`'s Writer, with a hard stop and within the disk cap. It
     covers the BTC 5m and 15m books 13:20-13:45 and 14:20-14:45 UTC on 11-02. Confirm with `sealed.py` that 11-02
     12-18 is development (d + j = 4).
  2. Keep `dm_bnf` and `dy_rtds` running alongside it.
  3. Per second, record the cluster's exact schedule-size rungs on each outcome: price minus mid and count. Also record
     the ladder centre (X180's definition) and the time of the first cheap-side add relative to 14:30:00 and to the
     first futures jump.
  4. Write each of the four predictions down before 13:20 UTC.
- **Data.** The new recorder, plus the shared recorder's trade stream for the fills.
- **Signature.**
  - (a) Both ladders move within ±2 s of 14:30:00, ahead of the move, by roughly the profile ratio.
  - (b) The widening comes >= 1 s after the first move.
  - (c) The favourite's rungs vanish while the cheap side's rungs are re-posted.
  - (d) The behaviour appears at 13:30 UTC.
  - R8c is frozen for the exam on the clock that this block shows.
