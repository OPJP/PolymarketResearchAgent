# Panel after iteration 12: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 12 the working assumptions are:
- the October development data (BUILD 10-09..26, STUDY 10-23..26, VALIDATE 10-27..30) show the strategy as it is;
- the side of a fill is a decision of the cluster, and the entry side is the last public side decision left to decode;
- switching BTC 5m off is a selection decision of the engine;
- "competition rejected" (X115/X126) covers the change in the cluster's behaviour.

Written 2026-11-01, about 02:40-03:35 UTC.

**Data used.** Development data only. `tools/sealed.py directional-maker`: released h1 and h2; development
[10-23, 10-31 06:00) and [10-31 12:00, 18:00); the current block is sealed. I read the RE's own tables:
- `it12/hist_btc.parquet` (whole crypto Up/Down activity history of the three wallets, 05-22..10-07);
- `activity_*.parquet` (10-08..22) and `exam/activity_*.parquet` (lot 10-22..30), clamped to < T0;
- `it12/maker_rows.parquet` and `maker_wallet_codes.parquet`, sample windows of 10-09..26 only;
- `exam/fills_holdout.parquet` and `exam/taker5m_day_*.parquet`, STUDY days only.

VALIDATE days (10-27..30) enter only through monthly or weekly totals. Nothing from 10-31 06-12, nothing after
10-31 18:00, nothing from `.cache/live/sealed/`.

One network source: Gamma listing fields of about 40 closed BTC 5m and 15m windows between 05-25 and 10-20 (all
development). I kept only these fields: resolutionSource, cryptoMarketConfig, feeSchedule and reward fields. The
requests went through the polyrea HTTP client, so they are cached.

Outcomes of historical windows come from the wallets' own REDEEM rows: the outcome with usdcSize > 0 won, the one with
size > 0 and usdcSize 0 lost. This labels 99% of BTC 5m BUY fills. My October cash flow (markets first traded 10-08..29:
+$91.0k, plus $23.0k of rebates) reproduces the RE's $111.7k for 10-08..30, so the accounting matches.

**Scripts.** All in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p12\`;
run them from the repo root with `.venv/Scripts/python.exe -I`:
- `pnl_fam2.py`, `pnl_check.py`: cash-flow PnL by family, week and wallet;
- `decomp.py`: per-fill PnL by month x price bucket x time in window;
- `struct_hist.py`: window structure by month;
- `subst.py`: off-hours, and whether BTC 5m off means reallocation;
- `gamma_chk.py`, `gamma_sw2.py`: listing switches;
- `natexp.py`, `late_sw.py`: behaviour around the settlement switches;
- `cofill.py`: shadow makers at the cluster's levels;
- `grid.py`: off-grid prints;
- `phase.py`: 5m windows by phase in the 15m / 1h grid.

**Multiple-testing warning.** These are descriptive scans over months, buckets and days. Treat every number below as
exploratory.

## What my checks found

**F1. The development data are the strategy's anomalous tail, not its steady state.**

Whole-history cash flow, by markets' first trade, without rebates (none in the history file):
- **Totals 05-22..10-29.** BTC 5m +$709k on $24.2M bought (2.9%). BTC 15m +$204k on $6.8M (3.0%). Other crypto families
  +$341k on $9.4M (3.6%).
- **Per wallet and month ($k, almach / bosona / mo-money).**
  - Jun 32 / 47 / 31
  - Jul 94 / 73 / 145
  - Aug 106 / 117 / 130
  - Sep 96 / 92 / 98
  - Oct 58 / 72 / 68

BTC 5m by week:

| weeks | PnL per week | return | bought per week |
| --- | --- | --- | --- |
| 06-22..10-11 (16 weeks) | +$16k..+$72k | 1.4-5.8% | $0.90-1.52M |
| 10-12..18 | +$25.4k | 2.9% | $0.86M |
| 10-19..25 | **-$14.5k** | **-4.1%** | **$0.36M** |
| 10-26..30 | +$30.8k | 6.2% | **$0.50M** |

- The lot weeks ran BTC 5m at a quarter to a third of its usual volume.
- **BTC 5m off-hours (clock hours with no BTC 5m fill), from 06-02:** Jun 2.2%, Jul 0.1%, Aug 1.5%, Sep 1.8%, **Oct
  8.2%**.
- Window structure by month (`struct_hist.py`):
  - median fills per window: 12 / 18 / 20 / 22 / 15 (Jun..Oct);
  - median two-sidedness (min/max outcome shares): 0.13 / 0.25 / 0.33 / 0.44 / 0.33, with 10-16..29 at 0.22;
  - the median fill in Jun-Aug was 10-22 shares, against the lot's 500 / 62 / 250 rungs.

So the window on/off "selection", the 62-share off-session size and the low volume are October features. Every STUDY
-> VALIDATE comparison of iterations 4-12 sits inside a reconfiguration, and the verdicts' 30-day profit was earned
mostly before 10-19.

**F2. The side does not carry the PnL in any month, including the most profitable ones.**

| | Jun | Jul | Aug | Sep | Oct |
| --- | --- | --- | --- | --- | --- |
| return per $ bought | 1.5% | 3.8% | 4.0% | 3.0% | 1.6% |
| window net side (by shares) wins | 0.56 | 0.56 | 0.56 | **0.45** | 0.53 |
| first fill wins | 0.53 | 0.56 | 0.56 | 0.51 | 0.52 |
| first fill = net side | 0.75 | 0.71 | 0.72 | 0.67 | 0.75 |

The return comes from the fill price against the outcome in every price bucket:

| price bucket | Jun | Jul | Aug | Sep | Oct | share of $ |
| --- | --- | --- | --- | --- | --- | --- |
| <= 0.10 | 2.5% | 30.2% | 30.7% | 19.8% | 6.9% | 1% |
| 0.10-0.40 | 1.4% | 12.2% | 7.8% | 3.5% | 12.5% | 9-19% |
| 0.40-0.60 | 4.4% | 5.7% | 3.2% | 4.9% | **-1.8%** | 16-21% |
| 0.60-0.90 | 1.0% | 1.5% | 4.2% | 3.0% | 1.3% | 43-54% |
| > 0.90 | 2.2% | 2.4% | 2.7% | 1.8% | 2.2% | 13-20% |

- By dollars the cluster is a favourite buyer: 69-82% of dollars at prices above 0.5 in every month.
- September earned +3.0% with a net side that lost (0.45).
- A per-fill side target of 0.80 asks for a quantity that the strategy does not optimise. What it optimises is buying
  below the outcome probability, on whichever outcome is offered.

**F3. October's damage is near the strike and at the entry.**
- The 0.40-0.60 bucket fell from +3.2% to +5.7% (Jun-Sep) to -1.8% in October (-$15.4k).
- Fills in the first 30 s fell from 2.1-3.2% (Jul-Sep; June was -2.2%) to 0.4%.
- This is exactly where the decoded Chainlink posture acts: the window entry, where the fair is near 0.5 and most
  sensitive to the reference.
- The tails stayed profitable (0.10-0.40 +12.5%, > 0.90 +2.2%, last 30 s +7.1%).
- The maker-share test of X115/X126 sampled 10-09..30, which lies entirely inside the degraded regime. It cannot rule
  out a competitor or taker change at or before the break.

**F4. BTC 5m off is a wind-down, not a reallocation.**
- In hours with BTC 5m off, 20% have no crypto fill at all, and BTC 15m is on in only 31%.
- In matched hour-of-week cells (7 cells with >= 3 on and >= 3 off hours), other families active: 9.5 when BTC 5m is
  off vs 17.2 when on. Median other-family fills per hour: 71 vs 234. In no cell are more families active when BTC 5m
  is off.
- The engine does not move its budget elsewhere when BTC 5m stops. This is an operator or risk state that began in
  October, consistent with the US-Eastern supervision clock (C5, X83).

**F5. Two public settlement switches in the history, and the cluster's late-window behaviour follows them.** From
listing metadata:
- BTC 5m windows from 2026-08-07 00:00 UTC settle on `btc-usd-twap-30s-streams` (twapLookbackSeconds 30). Before that
  they settled on the `btc-usd` spot stream.
- From 2026-08-14 00:00 UTC they settle on TWAP-60.
- BTC 15m went from spot to TWAP-60 directly on 08-07 00:00.
- The fee schedule (0.07, takerOnly, rebate 0.2) and the reward fields are the same in every sample from 05-25 to
  10-20.
- Gamma's `orderPriceMinTickSize` on closed markets alternates between 0.01 and 0.001 within days. It is the final
  dynamic tick, not a listing change, so I discard it as an event.

The cluster's last-minute behaviour by regime (`late_sw.py`, windows 07-24..08-24):

| | spot | TWAP-30 | TWAP-60 |
| --- | --- | --- | --- |
| share of $ in the last 30 s | 13.4% | 13.6% | **5.3%** |
| return 30-60 s before the end | 10-12% | 7-10% | **23-26%** |
| return in the last 30 s | 3-6% | 6-20% | 16-23% |
| median seconds left at a window's last fill | 34 | 66 | 101 |

- The last-30-s share fell over 08-14..16 (12% -> 10% -> 3%).
- The last-60-s return was -1.5% on average over 07-27..08-02, and 9-40% on every day from 08-09.
- The October "withdraws ~30 s before the end" therefore looks like a settlement-aware rule. Its onset can be dated
  against a public change.
- No tape control was run: the market's own late activity may have moved too.

**F6. Two leads closed.**
- **No shadow maker at the cluster's levels** (`cofill.py`; 864 sample windows, 10-09..26, 2.30M maker BUY rows):
  - 23% of the cluster's (tx, token, price) levels have another maker filled at the same level;
  - the top co-filler (0x21f4c1a1...) has 8.9% of that size against 3.4% of all maker volume (lift 2.6), normal for a
    top-of-book maker;
  - the top-5 hold 23% and the top-20 48%;
  - the highest lift among wallets with >= 0.2% share is 6.5 (0x48052843..., 1.4% of the co-size).
  - Neither a hidden sibling nor a leader shows up at the level.
- **Off-grid prints are not a selection lever** (`grid.py`, STUDY): 0.5% of the cluster's maker fills are off the 0.01
  grid, against 7.8% of taker prints. Excluding off-grid prints lifts selection by at most 1.08x.
- Also, 5m windows that end with the 15m or the hour show no distinct decision (`phase.py`): Jun-Sep returns are 2.8 /
  3.7 / 3.1% by 15m phase, and 2.0% for windows ending on the hour.

## Critique

1. **The fitting base is a regime transition, so the residuals may be transition effects, not the strategy's nature
   (F1, F3).**
   - Iteration 12 explains the side gap as "taker-chosen switches" and the outcome gap as "queue priority". Both
     readings are drawn from the weeks in which:
     - BTC 5m ran at a third of its volume;
     - its near-strike fills stopped earning;
     - it was switched off 8% of the time;
     - it was reconfigured roughly weekly (sizes 10-16 and 10-23, deep bids from 10-26).
   - The history holds 15 stable weeks (06-22..10-11, about 0.8M BTC 5m fills) in which nobody has scored R8's public
     side, the entry run, presence or selection.
   - Until the stable period is scored, "not decodable" and "decodable but broken in October" cannot be told apart.
2. **The side target is mis-specified for this engine (F2).**
   - In every month the net side wins 0.45-0.56 while the money is made.
   - The decision variable is the bid against the engine's probability on each outcome. The fill side is its
     consequence plus the takers' choice.
   - Spending the next iteration on "what sets the entry side" optimises a by-product.
   - The counted R8 side (0.693) beats the cheaper-token baseline (0.679) by only 0.014.
3. **"Competition rejected" is out of its range (F3).** X115/X126 compared BUILD+STUDY with VALIDATE, all inside
   October. The edge broke between the stable regime and October: near-strike returns, entry returns and volume all
   fell. The competitor question has to be asked across that boundary.
4. **The on/off is an operator state that began in October (F4).**
   - Treating it as an engine selection component searches for a market input that does not exist.
   - On the history the module was essentially always on (0.1-2.2% off-hours) while the edge was largest.
5. **The history has natural experiments with exact public timestamps, and the investigation has not used them (F5).**
   - The settlement rule changed twice in one week. The cluster's late-window behaviour changed with it.
   - This is the cleanest available identification of whether the engine prices the settlement source itself, and of
     how fast the operator adapts.

## Proposals (ranked by the chance they close the gap)

### P1. Score the decoded rule on the stable profitable version (06-22..10-11) before attributing the October residual to the strategy (new; strong form of C4 and X114, which used the history for one aggregate only)

- **Hypothesis.** The decision functions of iterations 4-12 (posture at the entry, the decided-window cheap side,
  pairing, the presence model) work materially better in the stable version. October is a degraded configuration of
  the same engine, after its near-strike edge broke.
- **Why it fits.** F1 (volume, off-hours, return, two-sidedness all break in October), F3 (the entry and near-strike
  edge died in October), and the STUDY -> VALIDATE instabilities the RE keeps measuring (k 1.0 -> 1.4, favourite share,
  deep bids).
- **Test.**
  1. Pre-register the versions from public or engine events:
     - 06-22 (signer rewrite, C4b);
     - 08-07 and 08-14 (settlement switches, F5);
     - 10-12 / 10-16 / 10-23 (size changes, C4).
  2. Pre-register the folds:
     - BUILD = 08-14..09-10;
     - STUDY = 09-11..09-25;
     - VALIDATE = 09-26..10-11 (TWAP-60 settlement throughout, the last stable stretch).
  3. Sample: every BTC 5m window starting in the 02, 08, 14 and 20 UTC hours. That is the X126 design, about 2,800
     windows. Pull taker-only tapes through `market_trades(taker_only=True)`; halve the hours if fetch time binds.
  4. Reference: Binance 1-s klines (`binance_seconds`, streamed per day) as the stand-in. Chainlink history does not
     exist that far back, and the RE's BUILD stand-in posture is the comparable baseline.
  5. Score, per fold and per wallet:
     - R8's public side per fill and per run;
     - the entry run;
     - the R3-class 10-s presence and its activity baseline;
     - print-level selection (recall, lift);
     - the strict-fill replay's window correlation (posture and oracle side).
  6. Then score the same frozen functions on 10-12..30, week by week.
- **Data.** On disk: `hist_btc.parquet` and the REDEEM outcomes. To fetch: about 2,800 taker tapes (about 4-5 h polite;
  cached) and Binance 1-s for the sampled hours.
- **Signature if true.**
  - On 09-26..10-11: public side >= 0.75 per fill and entry run >= 0.80, presence gain over activity >= 0.05, positive
    near-strike return.
  - All of these fall in the weeks after 10-12.
  - The rule then needs a version detector, read from public calendar and listing data plus the previous development
    block (P4). The "taker choice" account applies only to the degraded version.
- **If false.** The stable version gives the same 0.6-0.7 side and no presence gain. The October numbers are then
  intrinsic to a two-sided maker. That is the strongest quantitative account available (15 weeks, about 0.8M fills),
  and it supports moving the side claim to "consequence, not decision" (critique 2).

### P2. Who took the near-strike edge: maker and taker composition across the September -> October boundary (strong form of X115/X126/X66, whose sample lies inside the degraded regime)

- **Hypothesis.** A new fast participant appeared shortly before or at the break, quoting or taking near 0.5 on the
  same public Chainlink relay. It could be a maker joining the cluster's touch near the strike, or a taker population
  trading the RTDS publish. It made the cluster's near-strike fills adversely selected. The October changes (size
  cuts, weekend off, deep-bid ramp, underdog tilt) are the operator's response.
- **Why it fits.**
  - F3: 0.40-0.60 went from +3-6% to -1.8%, and the first 30 s from 2-3% (Jul-Sep) to 0.4%, while the tails kept
    earning.
  - F1: the BTC 5m volume fell 3x in the lot weeks.
  - The 10-19..25 loss.
  - X115 found the cluster's favourite-side share flat and its underdog share rising inside October only.
- **Test.**
  1. Extend the pre-registered maker-row sample (same hours, `market_trades(taker_only=False)` minus taker rows, as in
     `code12/fetch_makers.py`) back to 09-01..10-08: about 1,800 windows, about 3 h polite.
  2. Per week and price bucket (0.40-0.60 vs the tails):
     - each maker's share of maker BUY volume;
     - entrants (share < 0.2% before 09-20 and >= 1% after);
     - the cluster's share.
  3. Per cluster fill at 0.40-0.60: the held-to-resolution return and the 30-s tape markout, with and without each top
     entrant active in the same window (its maker rows before the fill).
  4. Taker side: by week, the share of taker volume signed within 300 ms after a Binance futures move. Use the RE's
     taker-signing calldata tools on a few hundred transactions per week.
- **Data.** data-api full tapes (cached), Gamma tokens, activity, a calldata sample per week.
- **Signature if true.**
  - An entrant's near-strike share (or the fast-taker share) rises in the week the cluster's near-strike return turns
    negative.
  - The cluster's near-strike markout is worse in windows where that participant is active: Spearman over windows
    <= -0.3, over weeks <= -0.5.
  - The participant's public rows are then a presence input (the cluster loses or withdraws where it quotes) and a
    side input near the strike. The deployability section changes (the edge is competed away).
- **If false.** The near-strike flow composition is stable across the boundary. The cause is then inside the cluster
  (a configuration, or the Chainlink stream regime of X46/X105), and P1's version split is the model.

### P3. The settlement switches as an identification of the engine's fair: spot -> TWAP-30 (08-07 00:00) -> TWAP-60 (08-14 00:00) (new data; strong form of A1_B3b and X93)

- **Hypothesis.** The engine prices the settlement rule itself, not the market's late repricing. It changed its
  late-window fair and its withdrawal time with each switch, through an operator update within about 0-2 days. If so,
  its late-window side and presence follow a lock-in fair whose length is a listing field. That gives a pre-registerable
  rule for the last 90 s, identified by an intervention instead of a fit.
- **Why it fits.** F5:
  - the last-30-s share went 13.4% -> 13.6% -> 5.3%;
  - the 30-60-s return went 10-12% -> 7-10% -> 23-26%;
  - the median seconds left at the last fill went 34 -> 66 -> 101;
  - the last-60-s return went from -1.5% on average (07-27..08-02) to 9-40% on every day from 08-09.
  - A1_B3b already finds the lock-in fair far better than spot on the lot (MAD 0.068 vs 0.141).
- **Test.**
  1. Windows 07-24..08-24: activity on disk, REDEEM outcomes, Binance 1-s for the last 120 s of each window.
  2. For every cluster fill in the last 90 s compute three fairs with the frozen k: the spot-instant digital, the
     TWAP-30 lock-in and the TWAP-60 lock-in. The lock-in fairs use the observed part of the average plus the remaining
     spot.
  3. Per window: which fair fits the fill prices best (MAD) and which fair's side matches the cluster's last-90-s net
     side.
  4. Find the change points of "best fair" over window start times and compare them with 08-07 00:00 and 08-14 00:00.
  5. Control: the same tape-based last-print timing (taker-only tapes for a few hundred windows on each side of each
     switch) to separate the cluster's withdrawal from the market's.
- **Data.** On disk plus Binance 1-s for about 9,000 short spans, and a few hundred taker tapes.
- **Signature if true.**
  - The best fair switches exactly at the listing boundaries, within about a day, and the withdrawal moves with the
    lookback beyond the market's own shift.
  - The late-window rule (lock-in fair, withdrawal at about the lookback) is then decoded with identification. Add it
    to R8 for the last 90 s as a public component and pre-register it for the next blocks.
  - If the switch lags by days, the adaptation is a human update, which supports the operator-state reading
    (critique 4).
- **If false.** The best fair does not move at the switches, or moves before them. The late-window fit is then the
  market's repricing, and the A1_B3b fit is co-movement.

### P4. Read the configuration online from the adjacent development block: an exam unit for a reconfigured bot (new; uses the pre-registered calendar)

- **Hypothesis.** The operator changes a few parameters every few days:
  - the entry multiplier k (STUDY 1.0 vs VALIDATE 1.4);
  - the deep-bid level (4% -> 24% of orders in a week);
  - the size class (500 / 62 / 250);
  - module on/off.

  A frozen procedure that re-estimates them point-in-time from the most recent development block can track the
  operator. Every sealed future block is preceded 6 h earlier by a development block (block j of day d is sealed iff
  d + j is odd).
- **Why it fits.** F1 (weekly reconfiguration), the iteration-12 entry-k flip and deep-bid ramp, and X34's
  block-dependent size class.
- **Test.** On the lot, emulate the calendar:
  1. Label alternate 6-h blocks of 10-23..30 as "development" and "sealed".
  2. Fit (k_entry, deep on/off, size class, favourite tilt) on each development block.
  3. Apply them to the next "sealed" block, and compare with frozen constants:
     - side per fill and per entry run;
     - the replay's window PnL correlation with the session size replaced by the block's estimated class.
  4. Use a 2-h block bootstrap.
  5. Report it as own history (the parameters are read from the cluster's past fills). It is never counted for
     presence.
- **Data.** On disk (lot fills, calldata sizes, Chainlink seconds).
- **Signature if true.** Side gain >= +0.03 and outcome-correlation gain >= +0.05 over frozen constants, with bootstrap
  lower bounds > 0. Then freeze the procedure, not the values, before the next future exam.
- **If false.** The parameter swings are not persistent at a 6-12-h horizon. They are noise around one configuration,
  and the "drift" findings of iterations 11-12 should be read as sampling variation.

## Notes for the RE

- **Do not spend the next iteration on the entry side** until P1 says whether the side is a decision in the stable
  version. X128 on the live book is still worth reading, because it is cheap.
- Report window and fill statistics with the whole-history context:
  - the near-strike and entry returns, against Jun-Sep;
  - the off-hours share, against 0.1-2.2% before October.
  The examiner will judge future blocks, which may sit in either version.
- **Correct the settlement description.**
  - BTC 5m settled on the Chainlink spot stream until windows starting 08-06 23:55 UTC, on TWAP-30 for 08-07..13, and
    on TWAP-60 from 08-14 00:00. BTC 15m moved to TWAP-60 on 08-07.
  - Any historical rule using TWAP-60 lock-in before 08-14 is wrong for that period.
- Gamma's tick field on closed markets is the final dynamic tick, so it cannot date a tick-size change.
- The verdict files give a 30-day PnL of about $245k for the three wallets. Against the weekly series, most of it was
  earned before 10-19.
