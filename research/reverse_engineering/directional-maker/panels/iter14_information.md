# Panel after iteration 14: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 14 in full, earlier iterations by search), state.json
(every catalog item, components, target metrics), the structure and open leads of FINAL_RULE.md, the EXAM.md verdict,
`iter13_information.md` in full and the proposal titles of every earlier information panel. I did not read the
iteration-14 mechanics or assumptions panels, which are written in parallel.

Data I touched (all development by `sealed.py`: 10-31 12-18 and 11-01 06:00-07:10 UTC; nothing sealed, nothing from
another strategy's workspace or cache):

- the RE's rebuilt quote unit `.cache/re/directional-maker/it14_qu_rebuilt_1793455200_1793469600.parquet` (6,200
  at-touch posts, 10-31 14-18);
- `iter_live` reads of the RE's own feeds dy_rtds (10-31 17:29-18:00 and 11-01 06:00-07:10), dx_bnf, dm_bnf, and record
  counts after 07:00 for dx_clob, dm_clob_raw, dw_clob and the shared clob_crypto;
- 6 requests to `polymarket.com/api/crypto/crypto-price` for development windows, 1 Binance 1h kline, 7 HEAD/GET
  probes of the pmxt hosts;
- `w32tm /query /status` (read only).

Checks ran inline; no scripts were saved and nothing was added to the cache.

## What my checks found

**C1. The laptop clock has not synchronised since 11-01 02:29 UTC, and it runs slower by a growing amount.**

- `w32tm /query /status`: "Leap Indicator: 3(not synchronized)", "Last Successful Sync Time: 10/31/2026 7:29:24 PM"
  (local UTC-7 = 11-01 02:29 UTC), root dispersion 9.68 s. The source query returned "Access is denied".
- The RE's own calibration records in dy_rtds (`{"k":"clk","off": Binance minus laptop, s}`, every 10 min) show the
  drift:

  | laptop time (UTC) | off (s) |
  | --- | --- |
  | 10-31 17:57 | 0.107 |
  | 11-01 06:03 | 0.677 |
  | 06:13 / 06:23 / 06:33 | 0.708 / 0.741 / 0.772 |
  | 06:43 / 06:53 / 07:03 | 0.804 / 0.835 / 0.867 |

  That is +0.031 s per 10 minutes, about 0.19 s per hour.
- The same shift appears in two other places:
  - laptop receive minus RTDS publish (BTC Chainlink): median +234 ms on 10-31 17:29-18:00, then -402 ms at 06:00-06:10
    and -552 ms at 07:00-07:10 on 11-01;
  - laptop receive minus Binance event time on dx_bnf: +90 ms (10-31 17:41), then -503 ms (11-01 06:00) and -704 ms
    (07:00).
- At this rate the laptop will be about 1.8 s slow at 11-01 12:00, 2.9 s at 18:00, 5.2 s at 11-02 06:00 and 7.5 s at
  11-02 18:00.
- What it does **not** touch: the rule code joins on server stamps (CLOB `s`, Binance event time, Chainlink `ts`/`P`).
  I checked `code14/qu_dx.py`, `code14/x160_block.py` and `code/final_rule.py`. The frozen metrics are not shifted.
- What it **does** touch:
  - every `Writer`, the shared recorder's included, files records into dev or sealed by laptop receive time. At each
    development-to-sealed boundary, the first `off` seconds of the sealed block land in the development file. The first
    such boundary since the drift began is **11-01 12:00 UTC (about 1.8 s)**, then 11-02 06:00 (~5 s) and 11-02 18:00
    (~7.5 s). At sealed-to-development boundaries, development records are lost to sealed instead; that is harmless;
  - `code/cl_source.py` `_live` drops sealed records by `r["t"]` (laptop time), so it cannot catch them;
  - `code/final_rule.py` lines 655 and 661 fall back to `r.get("t")` when `s` is missing;
  - any new receive-time feature (the RTDS activity race X62, the takers' clock X157, a recorder without server
    stamps) would carry a look-ahead equal to the offset.

**C2. The crypto-price endpoint is a recording-free settlement reference for every family in the weekend blocks.**

| request (development window) | openPrice / closePrice | compared with |
| --- | --- | --- |
| ETH 5m, 10-31 17:45 | 2250.58474 / 2252.304154490578 | dy_rtds `cl eth` at 17:50: 2252.304154490578 (identical) |
| SOL 15m, 17:45 | 95.88270963 / 95.92234749 | dy_rtds `cl sol` at 17:45: 95.88270963 (identical) |
| XRP 5m, 11-01 06:30 | 1.2522454544 / 1.251075205 | dv_rtds `cl xrp` at 06:30 / 06:35 (identical) |
| BTC 5m, 10-31 17:45 | 77521.19553744 / 77576.47106967 | dy_rtds `cl btc` (identical) |
| BTC 4h (`fourhour`), 16:00 | 77490.8989 / 77457.6751 | unrounded, Chainlink-like |
| BTC hourly (`hourly`), 16:00 | 77622.01 / 77626.27 | Binance BTCUSDT 1h kline open 77622.01, close 77626.27 (identical) |

- So every Chainlink-settled family (5m, 15m and 4h of each symbol) and the Binance-settled hourly family have a
  settlement-grade historical value per stamp, at about 1.5 requests/s.
- R9's planned "else the cheaper token" fallback (X161) is not needed for any family. BTC hourly needs the Binance
  candle, not Chainlink.
- Recording coverage of the next future exam's sealed blocks:
  - the shared recorder's first development file is 10-31 12:00;
  - the RE's books start at 14:04 (dm_clob_raw) and 15:57 (dx_*);
  - dw_clob (non-BTC books) starts at 22:59, and dv_rtds (XRP/DOGE/BNB/HYPE Chainlink) at 11-01 03:44.

  So the sealed block 10-31 06-12 has no own recording at all. In 10-31 18:00-22:59 there are no non-BTC books except
  the shared ETH/SOL top of book. On those blocks only a recording-free path can score the rule.

**C3. The relay's publish delay does not persist, so a historical publish clock cannot be reconstructed.**

- dy_rtds, 11-01 06:00-07:00, BTC (3,520 reports): delay P - stamp at p5/25/50/75/95 = 736 / 893 / 1,074 / 1,239 /
  1,605 ms.
- Its lag-1 autocorrelation is 0.26, lag-10 0.17 and lag-60 -0.01. The publish phase (P mod 1,000) is spread over the
  whole second.
- A trailing 30-report median predicts the next delay no better than the global median (median absolute error 182 vs
  174 ms). ETH is published within 5 ms of BTC for only 22% of stamps.
- So the exact publish clock exists only where dy_rtds recorded it: from 10-31 17:29, including the sealed blocks
  10-31 18-24 and 11-01 00-06, for BTC, ETH and SOL (plus dv_rtds for XRP/DOGE/BNB/HYPE from 03:44).
- On history, the fixed p90 lag (1,432 ms) is the only point-in-time option. On recorded blocks that lag discards the
  input the engine uses: the report is a median 360 ms older than the latest published one.

**C4. The 62/250 at-touch posts of 10-31 14-18 are in-session deep rungs, not an off-session ladder.**

- In the rebuilt table (6,200 posts), 0.4% of 62/250 posts have a post on the opposite outcome within 100 ms. For
  500/1000 posts the share is also 0.4%, so both size classes are one-sided.
- 44% of the 62/250 posts come in pairs or triplets (500/1000: 53%), and all 524 fall between 14:00 and 18:00 UTC on
  10-31, while the 500 schedule was running.
- Their at-chance side (0.51) therefore describes deep rungs (500/8 and 500/2) that became the touch. It says nothing
  about the weekend or off-session configuration, whose side has not been measured on its own posts.

**C5. The recorders resumed at 07:00.** Records in 11-01 07:00-07:10: dx_clob 52,643 (BTC 5m/15m), dm_clob_raw 300,536,
dw_clob 115,535 (HYPE, BNB, DOGE, XRP, ETH), clob_crypto 14,815. The current development block (06-12, Sunday morning UTC)
can carry every replication below.

**C6. pmxt has no later archive.** `r2v2.pmxt.dev` returns 404 for 08-10, 08-20, 09-15 and 10-24 (08-09 answered 200
in iteration 10), and `archive.pmxt.dev` timed out. So no historical full-depth book exists there for the lot or the
weekend analogs.

## Critique

1. **The look-ahead correction threw the information away instead of re-anchoring the unit.**
   - The withdrawn +0.090 (quote presence with a 1.0-s stamp lag) measured the content of "the report just published".
     The engine uses that report 0-150 ms after the relay publishes it.
   - On a 1-s grid that content is reachable only with look-ahead: the report stamped T-1 is published at about
     T + 0.07 s, inside the label second.
   - On a unit anchored at each publish ms the same content is point in time: at P_i the report is public.
   - The RE instead moved to a 1,432-ms fixed lag, which is stale for most cells (C3), and carried that lag into the X160
     runner. The safe +0.029 is the gain of a stale input, not of the engine's input. The brief's D1 asks for
     "per event for triggers", and the publish is the trigger.
2. **The next future exam is a weekend lot, and one of its blocks has no recording (C2).**
   - The examinable path for 10-31 06-12 is the recording-free one: in-block clock, taker signing ms and the endpoint.
   - R9 as planned still falls back to the cheaper token where no Chainlink recording exists. That fallback is
     unnecessary for every family, and the hourly family settles on Binance.
3. **The machine's clock is drifting, and nothing in the workspace has noticed (C1).**
   - The numbers so far are safe because the code joins on server stamps.
   - The dev/sealed filing is not safe: the first leaking boundary is 11-01 12:00 UTC, and the offset grows by about
     4.5 s a day.
   - It needs the user (a resync) and a code guard. An examiner auditing the boundaries would find the leak.
4. **"62/250 at chance" is read as a statement about the off-session ladder, but on 10-31 it describes in-session deep
   rungs (C4).**
   - The weekend configuration's side has never been measured on its own posts.
   - The block now being recorded (Sunday 06-12 UTC) is the first chance to do so.
5. **The time-left structure of the quote's sigma is fitted by band, after the fact.**
   - The settlement average has its own variance law, which gives k of about 0.29 in the last 30 s with no free
     parameter (I14-4).
   - Band fitting lost out of sample (0.803 vs 0.811). A structural law cannot overfit in that way.
6. **The weekend switch-offs are still explained only by own drawdown, at no fixed level.**
   - What the operator sees at those moments in public data has not been raced against the drawdown: competition at its
     own prices, and the taker populations.
   - On weekends, scope and presence depend on this module state.

## Proposals (ranked by the chance they close the gap)

### I14-1. Presence and side on the relay's publish clock: one cell per Chainlink publish, at the exact publish ms (strong form of I13-2, X147, X162 and the presence step of X160)

- **Hypothesis.** The engine's quote decision is a function of the report it has just read on the public relay.
  - Unit: cells anchored at each publish ms P_i (dy_rtds `P`).
  - Features at P_i: the posture from report i, the posture from report i-1, whether the new posture flipped relative
    to the current touch, |edge| and time left.
  - Prediction 1: these features predict the cluster's quote (an at-touch schedule-size post on outcome s within
    [P_i, P_i + 300 ms)) well above activity at P_i.
  - Prediction 2: they predict its fill presence in [P_i, P_{i+1}) at least 0.05 above activity.
- **Why it fits.**
  - The re-price pass comes 0-150 ms after the publish (iteration-7 pilot: 0.81-0.91 agreement at 0-200 ms).
  - The quote side on the exact clock is 0.831, against 0.78-0.79 for every fixed lag on the same 585 posts.
  - Quote presence with the look-ahead lag gained +0.090 [+0.058, +0.117], and its WHICH-outcome part +0.195. At the
    stale safe lag the gain is +0.029. The difference is the content of the report published inside the second.
  - C3: the publish delay is unpredictable noise, so no fixed lag can stand in for the exact clock. The exact clock
    exists in every recorded block from 10-31 17:29, including the sealed blocks 10-31 18-24 and 11-01 00-06.
- **Test** (pre-register before reading the outcomes of 11-01 07:00-12:00).
  1. Units: (window, outcome, publish interval) for BTC 5m and 15m. As a second family, ETH and SOL 5m/15m: dy_rtds
     records eth and sol with P, and their books are in dw_clob and clob_crypto.
  2. Labels:
     - Q: an at-touch 500/1000 add (or session-size add) on s in [P_i, P_i + 300 ms) with pass multiplicity >= 2 (the
       cluster's paired passes, which reduces the ~12% contamination from other makers), and separately at any
       multiplicity;
     - F: a cluster maker BUY fill on s, matched in [P_i, P_{i+1}).
  3. Features strictly at or before P_i, on server ms only (see I14-5).
     - Baselines: activity alone on the same cells, and an examiner-style baseline with the same model class and tuning
       budget.
     - Placebo: the same cells shifted to P_i + 500 ms with only report i-1 available. The gain must collapse there.
  4. Fit on 07:00-09:30, test on 09:30-12:00 (11-01). Then freeze and score on 11-01 18-24 and 11-02 00-06
     (development). Use a 2-hour block bootstrap.
  5. In `evaluate()`: use the exact clock wherever dy_rtds exists, the fixed 1,432-ms lag elsewhere, and report the two
     separately.
- **Data.** dy_rtds, dx_clob and dm_clob_raw, cluster fills from calldata or the data-api, dm_bnf and dx_bnf. All are
  being recorded now (C5).
- **Signature if true.**
  - Q gain >= +0.08 with a positive lower bound on both development blocks, and a WHICH-outcome gain >= +0.15.
  - F gain >= +0.05 with AUC >= 0.85 on BTC 15m.
  - Placebo gain <= +0.03.
  - If the exact-clock gain is also <= +0.03, the "decision clock" account of the presence gap is refuted, and the
    remainder is measured as the takers' choice.

### I14-2. A recording-free settlement reference per family for the weekend exam blocks (strong form of X161, X131, X84 and the side part of X101)

- **Hypothesis.** In the weekend configuration, the cluster's orders in each family follow the posture of that family's
  own settlement reference, not the cheaper token: Chainlink for the 5m, 15m and 4h windows of each symbol, the Binance
  candle for hourly and daily.
- **Why it fits.**
  - C2: the endpoint returns the settlement values of every family, and hourly is the Binance candle.
  - The weekend analog blocks hold BTC 4h 32-51% of dollars, BTC hourly 14-16%, BTC daily 12%, ETH 15m 7-11% and XRP 5m
    3-7%.
  - 10-31 06-12 has no recording.
  - X84 found the hourly fills follow their own reference at 0.63-0.68 on the block clock. That result was
    inconclusive, because Chainlink and Binance agree in the smooth regime.
  - Since 10-30/31 the Chainlink 1-s stream carries white noise (sd about $9/s) that Binance does not. The two
    references now disagree often enough to be separated.
- **Test.**
  1. Before any side scoring, measure per family the maker / taker share and the size classes in the weekend analog
     blocks: 10-24 06-12, 10-24 18-24, 10-25 00-06 and 10-25 12-18 (STUDY), and 10-31 00-06 (development).
  2. Freeze R9:
     - universe: every listed crypto Up/Down family;
     - price: R7 on the in-block clock;
     - side: the posture of the family's settlement reference at the point-in-time stamp (in-block match clock minus
       1,432 ms, or block second minus 2 s), fetched from the endpoint at one request per fill second;
     - sigma: the family's own Binance 300-s volatility; for BTC 4h and daily also test X84's slow 3,600-s sigma.
  3. Score per family and pooled against the cheaper, favourite and tape-momentum baselines on the analogs.
  4. Check on the 11-01 development blocks that the endpoint path gives the same posture as the recorded references
     (dy_rtds, dv_rtds).
  5. Hourly natural experiment: BTC hourly fills since 10-30 where the Chainlink posture and the Binance-candle posture
     disagree. Which one does the cluster follow?
- **Data.** `polymarket.com/api/crypto/crypto-price` (verified today per symbol and variant; about 1.5 requests/s, so a
  few hundred fills per block take minutes), Binance 1-s klines, data-api activity and market trades, Gamma listings
  (the projection for sealed units).
- **Signature if true.**
  - Pooled weekend side >= 0.75, and >= the cheaper token + 0.05 in each analog block.
  - Scope 1.00.
  - On the 11-01 development blocks the endpoint posture equals the recorded posture on >= 99% of fills.
  - If every family sits at its baseline, the weekend side is the takers' choice, and R9 must say so with the measured
    numbers.

### I14-3. What the operator sees at the weekend switch-offs: competition at the cluster's own prices (strong form of X39, X141 and X158)

- **Hypothesis.**
  - The BTC 5m and 15m switch-offs, including the ~18:15-18:30 ET weekend-evening ones, follow a public change in who
    quotes at the cluster's prices: a fast competitor's share of the maker fills at the touch jumps.
  - Re-enables follow that competitor's retreat.
  - The drawdown is the consequence of this competition, not the trigger.
- **Why it fits.**
  - The drawdown at the switch-off has no fixed level ($1.1k-$14.6k), and three of the events look scheduled.
  - In October the entrant cohort reached ~15% of maker volume (X141), while the top-20 counterparties' share of the
    cluster's fills fell 63% (X159).
  - X39 was never run, because only 5.5% of VALIDATE windows were inactive. In the weekend blocks the exam will use,
    scope and presence depend on module state.
- **Test.**
  1. Fetch the data-api maker rows (proxyWallet, price, size, time) of every BTC 5m and 15m window from 3 h before to
     3 h after each of the 7 BTC 5m and 25 BTC 15m switch-off events, and around each re-enable. Development only:
     about 70 windows per event, with the RE's `fetch_makers` code.
  2. Per window, compute:
     - the share of maker volume at the touch held by the top-k non-cluster makers;
     - the makers' HHI;
     - the number of distinct sub-second requoters (from competitors' signing ms in calldata);
     - taker volume by population.
  3. Use the at-risk points of `code14/trip.py`. Report the AUC per fold for each public measure against the drawdown
     (own state) and the calendar gate.
- **Data.** data-api `/trades` maker and taker rows for about 2,000 windows, and calldata of the event windows.
- **Signature if true.**
  - A public competition measure ranks the switch-offs at AUC >= 0.85 in BUILD and STUDY (at least the drawdown's
    0.82-0.88), at a stable level (CV <= 0.25).
  - It predicts on/off in the weekend analog blocks. Presence would then have a public module-state input for the
    exam.
  - If false, on/off stays own state, and the weekend presence bound is recorded as such.

### I14-4. The settlement average's own variance law as the time-left profile of the quote (strong form of A1_B3b, X93 and the RE's k-by-band fit; side)

- **Hypothesis.**
  - The engine prices the settlement value (the 60-s Chainlink average), not the spot price.
  - At time left tau, the settlement is normal with centre ((60 - tau) * A + tau * S) / 60 for tau <= 60, where A is
    the mean of the published values since end - 60, and with centre S for tau > 60.
  - Its standard deviation is sigma * sqrt(tau) * k(tau), with k(tau) = tau / (60 * sqrt(3)) for tau <= 60 and
    sqrt((tau - 40) / tau) for tau > 60.
  - With the global k = 1.0 x futures sigma300 the law adds no parameter.
- **Why it fits.**
  - The post-hoc band fit found k 0.3 in the last 60 s (0.830 / 0.878). The law gives 0.29 at tau = 30 s and 0.58 at
    60 s.
  - The quote sits on the favourite near the end.
  - Band-wise fitting lost out of sample (0.803 vs 0.811).
  - A1_B3b: fill prices in the last minute fit a lock-in fair (MAD 0.068 vs 0.141 for spot only).
- **Test.**
  1. On the rebuilt quote unit of 10-31 14-18, with no fitting, compare per tau band the law, one global k and the band
     fit.
  2. Freeze, and score on 11-01 07-12 and 18-24 on the exact publish clock (I14-1).
  3. On fills, replace R8's decided-window branch with the law. On the lot use the endpoint values for A.
- **Signature if true.**
  - Posts in the last 120 s at >= 0.83 on both halves and on 11-01, without fitting.
  - Overall +0.01 to +0.02.
  - R8's "decided window: cheaper token" branch becomes unnecessary, or is explained.
  - If the law loses to one global k, the engine does not model the average.

### I14-5. Keep the clock honest: server stamps everywhere, the `clk` offsets applied, and a resync by the user (data integrity; new; time-critical)

- **Hypothesis (operational).**
  - From 11-01 02:29 UTC the laptop clock drifts about 0.19 s per hour (C1).
  - Uncorrected, the filing misplaces the first 1.8-7.5 s of each sealed block into development files at 11-01 12:00,
    11-02 06:00 and 11-02 18:00.
  - Any receive-time feature carries a look-ahead equal to the offset.
  - The shared recorder files the same way, so every strategy is affected.
- **Why it fits.** C1: the w32tm status, the RE's own `clk` records, and two independent server clocks (RTDS publish and
  Binance event time) agree on the drift.
- **Test.**
  1. Before 11-01 12:00 UTC, ask the user to resync Windows time (Settings > Time & language > Sync now, or an
     elevated `w32tm /resync`). Agents cannot change system settings.
  2. Build the offset series from the dy_rtds `clk` records, cross-checked by laptop t minus Binance E. Record it in
     NOTES and in `state.json` `live_lab`.
  3. In code:
     - filter sealed records by server stamps (CLOB `s`, RTDS `P`, Binance `E`) and by unit start, never by laptop `t`
       (`cl_source._live`);
     - remove or offset-correct the `or r.get("t")` fallbacks in `final_rule.py`.
  4. After each development-to-sealed boundary, count the records in the development folder whose server stamp lies in
     the sealed block, and drop them in every reader of the RE's own feeds.
- **Data.** The RE's own dy_rtds `clk` records and the server stamps already in every feed.
- **Signature if true.**
  - The offset series rises monotonically by about 0.031 s per 10 min until a resync.
  - Without a resync, a nonzero boundary-leak count at 11-01 12:00, and none at sealed-to-development boundaries.
  - With a resync before 12:00 the leak never appears.
  - This item does not close the gap by itself. It keeps the exam's live inputs and the replications (I14-1, X160)
    clean, and it costs minutes.

## Notes for the RE

- Do I14-5 first. It is cheap, and its first deadline is 11-01 12:00 UTC.
- `code14/x160_block.py` scores presence with the fixed 1,432-ms lag. On every block with dy_rtds, use the exact
  publish clock (C3: no fixed lag approximates it) and the publish-anchored unit of I14-1.
- When X160 reports the 62/250 posts, split them by size-session state. On 10-31 they are deep rungs of the 500 ladder
  (C4), not the off-session configuration.
- Endpoint variants verified today: `fiveminute` (BTC, ETH, XRP), `fifteen` (SOL), `fourhour` (BTC) return Chainlink
  values identical to the recorded `cl` stamps; `hourly` returns the Binance 1h candle open and close. Other symbols
  and the daily variant are untested.
- The dy_rtds feed already records ETH and SOL Chainlink (and the TWAP topic) with publish ms, so the exact clock is
  available for the ETH/SOL families as well.
- pmxt offers nothing after 08-09 (C6). The pre-October historical book is not available from that archive.
