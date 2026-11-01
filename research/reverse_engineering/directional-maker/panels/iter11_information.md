# Panel after iteration 11: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 11 in full, earlier iterations by search), state.json
(catalog with every X item, components, target metrics), the "Why it works" section of FINAL_RULE.md, and the earlier
information panels' proposal lists (`iter10_information.md` in full). I did not read the iteration-11 mechanics or
assumptions panels, which are written in parallel.

Data I used, all development or released (h1 + h2):

- the RE's existing tables: `it9/volhist_{build,study,validate}`, `fut1s/<day>`, `cl/cl_hist*`, `cl/cl_grid`,
  `cl/cl_eval_cache`, `cl/ptb_lot`, `b1_takers_*`, `b1_all_makers_valid`, `chain_fills_*`. VALIDATE days (10-27..30)
  appear below only as per-day aggregates;
- data-api activity of almach and bosona in 2-h samples (12:00-14:00 UTC) on 13 days between 09-18 and 10-06, plus three
  30-min samples of almach (07-06, 08-17, 09-14);
- Binance spot 1-m klines for those 13 two-hour samples;
- one data-api `/trades` window (btc-updown-5m-1792830000, STUDY), with and without `taker_only`;
- one history.deribit.com request (10-20 00:00-00:10 UTC);
- the Hyperliquid info API for mo-money's Safe owner EOA, with every query ending before 2026-10-31 00:00 UTC.

I did not open `.cache/live/sealed/`, any sealed block, any other strategy's workspace, or any record after
10-31 06:00 UTC. Scripts: `C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i11/`
(`cl_noise_by_day.py`, `vr_by_day.py`, `offset_cl.py`). The other checks were inline.

## What my checks found

**C1. The "best k per day" is the daily favourite share of the fills, and it can be computed from the fill record alone.**

- Over the 22 days 10-09..30 (Binance stand-in, tape mid, k grid 0.35-3.0), the Spearman correlation between the daily
  favourite share of the cluster's BTC 5m maker BUY fills (fill price > 0.5) and the best k is **-0.93**.
- Replacing the tape mid with the fill price + 0.01 on the bought token reproduces the tape-mid best-k series at
  **Spearman 0.93** (0.89 with + 0.02).
- So the k series needs only the wallet's own fills plus a 1-s spot series. No tape is needed, and it can be built for
  the whole history.
- The argmax is unstable. With the wider grid, 7 of 22 days moved to a grid edge: 10-17, 10-22 and 10-25 to 0.35;
  10-20, 10-29 and 10-30 to 3.0. The RE's grid stops at 0.5-2.5, so those days showed 0.85, 1.0, 0.5, 2.5, 2.5 and 2.5.
  An MLE of log k with a block-bootstrap interval, or simply the favourite share, is a better state variable than a
  grid argmax.

**C2. On the 22 days, the weekly cycle is confounded with realised volatility.**

Daily favourite share regressed (OLS) on log RV (Binance futures 1-s, whole day) and days since Monday:

| model | R² | t-values |
| --- | --- | --- |
| log RV only | 0.32 | -3.1 |
| days since Monday only | 0.28 | 2.8 |
| both | 0.41 | -2.05 / 1.67 |
| both + a week-3 dummy | 0.53 | week 3: -2.19 |

- Spearman(best k, daily RV) = +0.58.
- Weekends are the low-vol days, so "k resets high at the Monday restart and decays toward the weekend" and "k rises
  with realised vol" are not separable on three weeks.

**C3. Earlier weeks show the Sunday-to-Monday step, but the cycle is not uniform.**

Activity samples, almach + bosona, 12:00-14:00 UTC; favourite share of their BTC 5m BUY rows (taker buys included):

| day | favourite share |
| --- | --- |
| Sunday 09-20 / 09-27 / 10-04 | 0.74 / 0.45 / 0.56 |
| Monday 09-21 / 09-28 / 10-05 | 0.31 / 0.36 / 0.15 |
| Tuesday 09-22 / 09-29 / 10-06 | 0.40 / 0.14 / 0.15 |
| Friday 09-18 / 09-25 / 10-02 | 0.21 / 0.41 / 0.37 |
| Saturday 09-19 | 0.30 |

- Correlation with Binance 1-m RV over the same 2 h: Spearman -0.35 (n 13, p 0.24).
- Saturday 09-19 and Sunday 09-20 had the same RV (2.46 vs 2.40 bp per minute) but favourite shares of 0.30 vs 0.74.
  So the Sunday-high, Monday-low step recurs in three more weeks, and it is not all volatility.
- But Friday and Saturday were low in September. That does not match the "decay by Fri-Sun" of October weeks 1-2.
- Three 30-min Monday samples of almach (07-06, 08-17, 09-14; 26-83 buys each) gave 0.77, 0.68 and 0.88. They are tiny
  and come from an older configuration, but they warn that the sign of the cycle may not hold over the whole history.

**C4. On the lot the cycle is a pure scale effect. On BUILD days the stand-in adds a level error.**

- Lot, real Chainlink (the RE's `k_by_day` inputs): a joint fit of a dollar offset on the Chainlink value and k gives
  offsets of 0 to ±6 dollars, with gains ≤ 0.015 per day (10-26: -3 dollars, 0.613 → 0.628). The favourite/underdog
  cycle is not a drift, basis or level input.
- Binance stand-in on BUILD days: the offsets reach ±12-30 dollars, with gains up to +0.067 (10-21: +30 dollars,
  0.612 → 0.679; 10-22: -12 dollars, 0.558 → 0.583; 10-18: -20 dollars).
- On the lot, the median Binance minus Chainlink is 105-153 dollars and moves by tens of dollars between and within
  days.
- So the week-1/2 part of the cycle, which is stand-in only, carries Binance-Chainlink disagreement. Refit it with the
  endpoint stamps that the detached fetch is collecting for BUILD before relying on it. The endpoint's ~30-day horizon
  reaches 10-09 around 11-08.

**C5. The market prices the 5-minute variance; the cluster does not.**

- The per-day variance ratio of Binance futures 1-s prices at 300 s is 0.92-1.97. Its square root, 0.96-1.40, brackets
  the market's implied k_m ≈ 1.15.
- Its Spearman correlation with the cluster's best k is -0.26 on the same day and +0.13 on the previous day.
- So the cluster's k is not tracking the horizon-matched variance, the calibration that the market gets right.

**C6. The Chainlink stream's own character co-moves with k (weak, exploratory).**

- Data: consecutive-second pairs of the endpoint's 1-s series near the fetched stamps, on 15 days with at least 190
  pairs.
- The ratio sd(1-s Chainlink change) / sd(1-s Binance futures change) is 0.67-1.04 per day.
- Spearman with the best k:

  | measure | Spearman with best k |
  | --- | --- |
  | sd(Chainlink) / sd(Binance) | **+0.75 (p 0.001)** |
  | sd of Chainlink changes alone | +0.41 |
  | lag-1 autocorrelation of Chainlink changes | +0.05 |

- Caveats: the ratio's range (×1.5) is much narrower than the k range, and the seconds are selected near fills. It is a
  lead, not a fit.

**C7. Endpoints and new data verified on this laptop (01:30-01:50 UTC 11-01).**

- **data-api `/trades` with `taker_only=False`** returns the maker rows with the maker's `proxyWallet`. In one STUDY
  window there were 4,592 rows against 1,488 taker rows. The identity of every competitor on every print is in the tape
  cache the RE already uses.
- **history.deribit.com `public/get_last_trades_by_currency_and_time` (kind=option)** returns HTTP 200 with per-trade
  `iv`, `mark_price` and `index_price`. The 10-20 00:00-00:10 request returned 19 trades, including the 10-24 and 10-30
  expiries. Short-dated implied vol is available historically; X13 used only DVOL, a 30-day index.
- **data-api activity** reaches back at least to July 2026 for almach and bosona. BTC 5m BUY rows are present on 07-06,
  08-17 and 09-14, and 140-680 BTC 5m buys come per 2 h in Sept-Oct.
- **Hyperliquid info API (public).** mo-money's Safe owner EOA `0xd1f9bc03d7395134647c6a7d3b468cfdd4b38292` is a
  Hyperliquid account (`userRole` = user):
  - at least 2,000 perp fills in July 2025 (SOL 1,605, XRP 395);
  - 23 ledger updates from 2025-03 to 2026-06: deposits, withdrawals, a liquidation in 2025-10, and a spot transfer on
    2026-06-13;
  - last perp fills on 2026-06-28 (ZEC), and none between 2026-07-01 and 10-31.

  There is no same-key perp hedge in the study period. The operator does trade crypto perps on Hyperliquid.

## Critique

1. **The weekly-cycle reading rests on 22 points, three Monday restarts and a grid argmax.**
   - It is confounded with realised vol (C2) and is not uniform in September (C3).
   - The investigation is about to look for "the driver of the weekly k cycle" before establishing, on the whole history,
     what the state is and how it moves.
   - The data for that are cheap and almost fully in hand: the fill record and Binance (C1). The brief asks for the
     wallet's whole history; for this question it has not been used.
2. **"Same takers, constant market demand, so the change is in the cluster's quote" leaves out the competitors at the
   touch.**
   - A maker fill needs the cluster to be at the touch, and usually first there: 78% at the touch, fresh posts
     0.1-1 s old.
   - If a competitor started bidding the favourite more aggressively on 10-26, or runs its own weekly schedule, the
     cluster's favourite fills fall while its quote is unchanged.
   - The tape carries every maker's wallet (C7). X24 ("fast makers' state from historical maker rows") has been open
     since iteration 4.
3. **k is measured on fills only.** The quote-level posture (X50, exact-500 adds at the Up/Down bid after each report)
   exists on the recorded blocks, but the cycle has never been measured on the quote. "The side change is in the quote"
   is an inference from fills.
4. **A perfect k path would not close the side bar.**
   - On the lot with real Chainlink, the per-day best accuracies are 0.615-0.750 (C4), below 0.80.
   - The residual is the 62/250 ladder outside region D and the window entry.
   - The information set of that ladder's quote is still unknown. Its re-post race (X103) runs tomorrow on one Sunday
     block.
5. **The vol input has been raced only as transforms of Binance 1-s returns** (v300, v3600, since-restart estimators,
   DVOL × c).
   - The feed the engine actually reads (Chainlink/RTDS) and short-dated options were never used as a sigma source.
   - Sigma now carries the side's cycle, so the choice of source is the decision variable.
6. **The BUILD half of the cycle is stand-in only, and the stand-in has a level error there** (C4). The Chainlink
   endpoint's 30-day horizon will start dropping BUILD days around 11-08.

## Proposals (ranked by the chance they close the gap)

### I11-1. The whole-history state of the side: favourite share and k per 6-h block from July to October, raced against the restart calendar, realised vol and own state (strong form of C4, X75, X107, X111)

- **Hypothesis.** The engine's favourite/underdog lean (k) is a slowly varying state with a point-in-time driver. The
  candidates:
  - (a) a state reset at the Monday 01:00 UTC restart and sweep, and updated through the week;
  - (b) a monotone function of realised vol;
  - (c) own PnL or drawdown since the sweep (a risk budget);
  - (d) operator configuration changes at irregular dates.

  The lot cannot separate them (C2, C3).
- **Why it fits.**
  - k is the favourite share (-0.93), and the favourite share is computable from fills (proxy 0.93; C1).
  - The Sunday-to-Monday step recurs in 3 of 3 sampled September-October weeks while Friday and Saturday do not decay
    (C3).
  - Volatility explains as much of the 22 days as the weekday (C2).
- **Test.**
  1. Data:
     - all TRADE activity of the three wallets back to the first trade (`PolymarketData().activity`, cursor paging,
       cached), keeping BTC 5m and 15m BUY rows;
     - the maker/taker split from OrderFilled logs with topic2 = wallet (V2 exchanges; V1 before the switch). As a
       first pass, activity alone will do: taker buys are about 10-15%.
  2. Per 6-h block:
     - the favourite share F_b;
     - the MLE of log k_b with the fill-price proxy and Binance 1-s spot, with a block-bootstrap interval.
  3. Pre-register models (a)-(d) on 07-01..09-30. Score them on 10-01..30 and on the development blocks after 11-01.
  4. Report:
     - the out-of-sample R² of F_b;
     - the per-fill side accuracy with a point-in-time k_b against the frozen k = 1.4, against the market-only and
       inventory baselines.
- **Data.**
  - About 120 days × 3 wallets of activity (1-2k rows per wallet-day; a few thousand cached requests).
  - Binance 1-s spot: aggTrades or 1-s kline archives, about 20 MB zipped per day. Reduce each day at once to a 1-s
    price parquet of about 1 MB and delete the zip.
  - Restart epochs from a calldata sample (about 20 transactions a day, for the salt counter).
  - Gamma listings for the window start and end.
- **Signature if true.** One reading wins and gives the frozen rule a point-in-time k:

  | reading | signature |
  | --- | --- |
  | (a) Monday state | At ≥ 80% of the ~16 Monday restarts, F falls (k jumps) by more than the within-week sd net of RV. No comparable step at the other daily 01:00 restarts. |
  | (b) volatility | F against log RV has a stable slope across months (the lot gives -0.17 per log unit) and no Monday step net of RV. |
  | (c) risk budget | F tracks the drawdown since Monday (\|rho\| > 0.5), and the "no decay" week is the winning one. |
  | (d) versions | Change points fall on irregular dates that align with salt, size or ladder version changes. |

### I11-2. The competitor at the touch: maker identities from the tape (strong form of X24; also C3 and X39)

- **Hypothesis.** The cluster's favourite share is set jointly by its quote and by the best competing bids. A competitor
  who became more aggressive on one side at the Monday steps, or who runs a weekly schedule of its own, moves the
  cluster's fills without any change in the cluster's quote.
- **Why it fits.**
  - The RE's evidence, the same takers and a constant favourite share of the market's demand, is compatible with this
    reading.
  - The cluster's fills are first-at-touch events.
  - Its own transactions already show 1,554 distinct co-makers on VALIDATE.
  - The full tape names every maker (C7). No competitor statistic has ever been computed.
- **Test.** For every BTC 5m window of 10-09..30 (the tapes the RE already fetches, with `taker_only=False`), per 6-h
  block:
  - (i) for each of the top 20 makers by maker volume: their share of the favourite-side maker volume and the favourite
    share of their own fills;
  - (ii) the effective price paid by the takers who buy the favourite, relative to the Chainlink digital at k_m = 1.15
    (the favourite-side half-spread);
  - (iii) the best k of each large maker on the RE's posture grid.

  Then ask:
  - Does a competitor's favourite-side share jump in the blocks where the cluster's falls (10-12, 10-19, 10-26)?
  - Do favourite-side spreads narrow (competition) or widen (the cluster withdrew)?
  - Do other makers share the k cycle (a common input)?

  On the recorded live blocks, check in the raw book whether the cluster's favourite-side 500s sit behind a competitor
  or are absent.
- **Data.** About 6,300 tapes, mostly cached already. Each row has `proxyWallet`, side, outcome, price, size and the
  transaction hash.
- **Signature if true.**

  | reading | signature |
  | --- | --- |
  | competition | A competitor's favourite-side share rises by ≥ 0.15 in the blocks where the cluster's falls, and favourite spreads narrow. The side rule must then carry the competitor state (a public, market-only feature, so state it against the baseline). |
  | the cluster's own quote | Competitors stay flat, and favourite spreads widen when the cluster leaves the favourite bid. |
  | a common input | Several makers show the Monday k step. Search for a shared source (the RTDS feed, a library default). |

### I11-3. Measure k on the quote, not on fills, across weekdays: live blocks and pmxt (strong form of X50 and X87 for the k cycle)

- **Hypothesis.** If the cycle is the engine's, then the k fitted on the quote unit (the exact-size adds at the Up vs
  Down best bid after each Chainlink report) equals the fill-level k of the same block and shows the Monday step. If the
  quote-level k is flat while the fill-level k moves, the "cycle" is a fill-selection effect: takers or competitors.
- **Why it fits.** Every k so far comes from fills (critique 3). The recorded blocks and the pmxt archive show the quote
  directly.
- **Test.**
  1. Recorded development blocks: 10-31 12-18 (Saturday), 11-01 06-12 (Sunday), and the Monday 11-02 development blocks.
     Fit k per block on the quote unit and on the fills, with bootstrap intervals.
  2. Pre-register: "the quote-level k of the Monday 11-02 blocks exceeds Sunday's by ≥ 0.5, and quote k equals fill k
     within the interval on every block".
  3. For more Mondays, use pmxt (07-16..08-10; Mondays 07-20, 07-27, 08-03 and 08-10). Quote-level k per day with the
     Binance stand-in (the RE shows it tracks Chainlink k on the lot), from two sampled hours per day (12-14 UTC).
     That is about 67 MB of range reads per hour, reduced on the fly: about 3.5 GB streamed and under 50 MB kept.
- **Data.** The raw recorders (dm_clob_raw and successors) and pmxt range reads. No Chainlink is needed for July.
- **Signature if true.**

  | outcome | reading |
  | --- | --- |
  | Quote k = fill k, and the Monday step appears in pmxt | The cycle is an engine parameter. Its driver comes from I11-1. |
  | Quote k flat (~1.4) while fill k moves | The side rule must be re-scoped: fit the fill side with the competitor and taker state of I11-2, not with a cycling sigma. |

### I11-4. Short-dated options and the engine's own feed as the sigma source (new sources; strong form of X13 and X75)

- **Hypothesis.** The engine's sigma comes from a source that has never been raced. Two candidates:
  - (a) the ATM implied vol of Deribit's front daily or weekly expiry. Weekend expiries carry low IV, the front rolls at
    08:00 UTC, and the weekly expiry is on Friday.
  - (b) the realised vol of the Chainlink stream the engine reads, as the engine receives it on RTDS (reports, gaps,
    duplicates). Its noise differs from Binance's and changes by regime: 10-31 has sd $8-9 per second and lag-1
    autocorrelation -0.5 (X46).
- **Why it fits.**
  - X13 used DVOL only, which is 30-day and smooth.
  - Every running estimator so far was a Binance 1-s transform.
  - The sd(Chainlink) / sd(Binance) ratio co-moves with k: Spearman +0.75 over 15 days, against +0.58 for Binance RV
    (C6).
  - The cluster ignores the horizon-matched variance that the market prices (C5).
- **Test.**
  - (a) Front-expiry ATM IV per hour from history.deribit.com option trades (C7): nearest expiry ≥ 1 h out, strikes
    within 2% of the index, 1,000 trades per page, 10-09..10-30. Extend to the whole history with I11-1.
  - (b) RV of the 1-s and 2-s Chainlink returns per block, from the X102 fetch (every even second of 365-s spans) and
    the iteration-10 fetch. Live, from dy_rtds with the engine's reception gaps.
  - Regress the engine's sigma, log(k_b × v300_b), per 6-h block on log IV_front, log RV_CL and log RV_BN. Pre-register
    on BUILD (with the Chainlink refit of C4) and score on the lot.
- **Data.** Deribit option trades: about 10-20k per day, 10-20 requests per day. The Chainlink seconds are already
  queued (X102) or recorded (dy_rtds).
- **Signature if true.**
  - sd(log(sigma_engine / (c × source))) across blocks is below 0.3, against 0.77 for v300 now, and the Monday step is
    absorbed.
  - Falsifier for (b), runnable now: on 10-31 12-18 (noise regime) the engine's best k on a wide grid must be ≥ 2.5. If
    it is about 1.4, (b) is out.

### I11-5. The operator's other accounts and the weekly treasury path (strong form of C1; new venue)

- **Hypothesis.** The weekly Monday sweep feeds a treasury that funds other books: a sibling Polymarket account, or perp
  hedges or strategies on another venue. The Monday k reset and the Fri-Sun ET switch-offs of BTC 5m/15m are then
  portfolio decisions visible in those accounts (capital or attention moved elsewhere).
- **Why it fits.**
  - The sweeps sit exactly at the weekly restart (X95).
  - BTC 5m/15m are switched off while other markets keep trading (X82: the salt counters run on).
  - mo-money's owner is an active crypto-perp trader on Hyperliquid, though not with that key during the study (C7).
- **Test.**
  1. Decode the Monday 01:00 sweep transfers (USDC Transfer logs from the three proxies, development weeks only) to
     their destinations.
  2. Recover the almach and bosona owners (Safe `getOwners` via `eth_call` on each proxy).
  3. For every owner and sweep destination, query:
     - Hyperliquid `userFillsByTime` and `userNonFundingLedgerUpdates`, with the end before the last development block;
     - Polygon: the Safe proxies created by that owner (other Polymarket accounts);
     - Arbitrum and Base transaction counts.

  About 100 calls in all.
- **Data.** Polygon RPC (drpc or publicnode) and the public Hyperliquid info API (verified, C7).
- **Signature if true.**
  - A sibling account whose fills or ledger moves line up with the cluster's switch-offs or the Monday reset.
  - Or the weekly sweep size or working balance tracks the k state (a risk budget).
  - A negative result closes C1's strong form with evidence.

## Notes for the RE

- Cheapest first step:
  1. Rebuild C1's favourite share per 6-h block from the activity you already have (10-08..30).
  2. Extend it back with activity paging. It needs no tape and no Chainlink.
  3. Then decide between I11-1 (a)-(d) before spending the iteration on a weekly-driver story.
- Use an MLE of log k with block-bootstrap intervals, or the favourite share, instead of a grid argmax. 7 of 22 days sit
  at a grid edge once the grid is widened (C1).
- Time-critical: refit the BUILD part of the cycle with the endpoint Chainlink stamps (C4) before the endpoint's horizon
  passes 10-09 (around 11-08).
- The tape's maker rows (C7) also give a market-only "competitor state" feature. If it enters any side or presence
  model, it belongs in the baseline as well.
