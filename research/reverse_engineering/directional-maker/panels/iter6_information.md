# Panel after iteration 6: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iterations 1-6), state.json (catalog, components, live split),
FINAL_RULE.md and the iteration-4/5 panel files. I ran small checks on public feeds only:

- the shared dev block 2026-10-31 12:00-17:00 UTC (`dx_rtds` through `code5/rawread.iter_dm`, dev folder only);
- live websocket probes of 40-60 s (nothing stored);
- Gamma listing text for three dev windows;
- about 700 GETs to a Polymarket price endpoint, for seconds in BUILD, STUDY, the released lot and today's dev block.
  For 10-27..30 I computed only aggregate statistics of the public Chainlink feed. No wallet data was involved.

Nothing in `.cache/live/sealed/` or in a sealed block was read. My scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i6/`:
`rtds_probe.py`, `rtds_probe2.py`, `pm_price_probe*.py`, `cmp_rtds.py`, `hist_probe.py`, `noise_probe.py`,
`twap_check.py`, `gamma_src.py`.

## What my checks found

**C1. A historical 1-s Chainlink BTC/USD series exists, on Polymarket's own site. X42 is not infeasible.**

The request is
`GET https://polymarket.com/api/crypto/crypto-price?symbol=BTC&variant=fiveminute&eventStartTime=<ISO second>&endDate=<same>`.
`eventStartTime` can be any second, not only a window boundary. The endpoint returns `openPrice` = the Chainlink value
stamped at that second and `closePrice` = the value 300 s later, plus `completed` and `cached`.

- **Live match.** For 2026-10-31 16:00:30-37, 8 of 8 `openPrice` values equal `dx_rtds` `crypto_prices_chainlink` at
  the same stamp to every printed decimal. Example: 16:00:30 gives 77469.21110255292 on both. They are not the TWAP
  topic.
- **Settlement-grade on BUILD.** For the BTC 5m window starting 2026-10-20 12:05 UTC, Gamma `priceToBeat` =
  81420.42863455646. The mean of the endpoint's values stamped st-61..st-2 is exactly 81420.42863455646. The other
  60-s spans miss by $0.2-0.5. In the iteration-6 convention ("TWAP stamped st = mean of st-62..st-3") this means
  `priceToBeat(st)` = the TWAP stamped st+1. The endpoint therefore reproduces settlement historically.
- **Access.** About 700 requests at up to about 4 per second all returned HTTP 200 (no 429). Median latency was
  0.84 s. Responses carry `"cached": true`.
- **Other variants.** `symbol=ETH` works. `fifteen` and `fourhour` return the same open (and the close 900 s or
  14,400 s later). `hourly` returns a 2-decimal price from another source (the Binance candle the hourly markets
  settle on).
- **Cost.** Each request gives two seconds (t and t+300), so a full 5-minute window costs 150 requests.

**C2. RTDS streams every 1-s update with a server publish timestamp, but only when it is subscribed without a symbol
filter.**

`tools/live.py`, `dm_rtds`, `dx_rtds` and the `btc5m_rtds_stream*` feeds in the dev folder all subscribe with
`filters: {"symbol": "btc/usd"}`. That subscription returns one 59-s snapshot and then nothing, which is why every
recorder reconnects every 25-50 s. With `"filters": ""` the socket pushes `type: "update"` messages for every symbol,
one per second each (btc, eth, sol, xrp, hype, zec, ...). Each message carries `payload.timestamp` (the value stamp)
and a top-level `timestamp` (server publish ms). My probe sent a text `PING` every 5 s. The unfiltered stream carried
about 8 updates a second over all symbols on that topic.

Measured over 60 s of BTC updates, with the laptop clock corrected against Binance `/fapi/v1/time`:

| quantity | p10 | p50 | p90 |
| --- | --- | --- | --- |
| server publish minus value stamp | 0.97 s | 1.39 s | 1.81 s |
| laptop receive minus value stamp | 1.31 s | 1.66 s | 2.09 s |

There was one 2-s stamp gap per minute. The TWAP topic behaves the same way.

Consequences:

- **Leakage in the current convention.** "Usable from T+2 s" lets about 10% of seconds use a value that the relay had
  not yet published.
- **The lag-2 peak fits a reader of the public relay.** The iteration-6 lag-2 peak is what a bot reading that relay
  would produce. The center is built from adds of the last 1.5 s, so it is on average about 0.75 s old, and the relay
  delay adds about 1.4 s. A bot subscribed directly to Data Streams would peak at lag 1.
- **The laptop clock drifts.** It is now 1.63 s slow. Iteration 4 measured 1.05 s, and iteration 6 measured 1.12 s.
  Every "arrival" number based on laptop receive time (the "1.2-1.8 s" in NOTES) drifts with it.

**C3. The Chainlink 1-s stream changed character after the lot.**

For each sample I took 24-30 consecutive seconds from the endpoint, twice per time (t and t+300). For each run I
computed the lag-1 autocorrelation of the 1-s changes and their standard deviation:

| period (UTC) | lag-1 autocorr of 1-s changes | sd of 1-s change |
| --- | --- | --- |
| 10-14 15:00, 10-20 15:00, 10-24 15:00, 10-25 03:00, 10-26 15:00 and 21:00 | -0.24 .. +0.42 (11 of 12 runs above -0.19) | $0.5-7.8 |
| 10-27..10-30, 03:00 and 15:00 each day (aggregate, public feed) | -0.30 .. +0.63 (15 of 16 above -0.19) | $1.8-11.7 |
| **10-31 00:30, 02:00, 04:00, 05:30, 13:00, 14:00, 16:20** | **-0.75 .. -0.19 (13 of 14 runs at or below -0.19; one +0.41)** | **$0.7-11.9 (median about 8)** |

The white-noise-like component (iteration 6: autocorrelation -0.47, held-out correlation +0.244 with the skew) is
absent from every sample before 10-31. It starts between 10-30 15:00 and 10-31 00:30 UTC. 10-24 was also a Saturday
and shows none of it, so this is not a weekend effect. The Gamma rules text and `resolutionSource` are identical
(same text hash) for windows on 10-20, 10-25 and 10-31. The samples are small, so the change hour has to be pinned
with full series.

**C4. Kalshi's KXBTC15M public market data works.**

`api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=settled` returns `floor_strike` and
`expiration_value`, and `/markets/trades?ticker=` returns trades with microsecond `created_time`, both without auth.
A4b is not blocked.

## Critique

1. **The leading input was never scored where the primary metric lives.** Iteration 6 found the first input that
   beats co-occurrence (Chainlink: +0.07-0.11 print-level AUC, +0.04 at the bin level, held-out skew R^2 0.21). It
   then concluded that "the historical VALIDATE and the released lot cannot score that input" after one 429 from
   data.chain.link. C1 shows that Polymarket serves the exact settlement-grade series for any second. The 27,988
   VALIDATE fills, R3's features, the side rule and the PnL correlation can all be rebuilt on the Chainlink fair now.
   The same endpoint can also serve the frozen rule on the sealed blocks, so the rule does not depend on recorder
   coverage.
2. **The identifying variation of iteration 6 may not exist in the lot.** The skew was shown to track Chainlink's 1-s
   noise, and the "no exchange contains it" argument rests on that noise. C3 says the noise appeared after 10-30
   15:00 UTC. Two readings are still open:
   - (a) the engine always priced off Chainlink (RTDS), and the new noise made that visible;
   - (b) something that started on 10-31 correlates with the noise.

   They predict different historical results (proposal I1/I4). There is also a risk for the exam: if the regime
   reverts, any R5 term that keys on the noise will fail.
3. **"The 2-s lag is the stamp convention, not staleness" is not established.** The TWAP stamp offset is real. But
   the relay publishes each value 0.97-1.81 s after its stamp (C2), and that alone produces the lag-2 peak. Iteration
   6 cannot tell a public-relay reader from a direct Data Streams subscriber, because every recording is snapshot-only
   and has no arrival times. That is the one question this lens most needs answered: does the wallet see the
   settlement stream earlier than the public?
4. **The future exam has no arrival-time data.** `dx_rtds` (filtered snapshots) is the only Chainlink input recorded
   through 18-24 UTC today, 11-01 00-06 and 11-01 12-18. If R5 uses arrival times, a streaming recorder must start
   before the 18:00 UTC sealed block. Otherwise the examiner gets only stamps and the 2-s rule (with its about 10%
   look-ahead).
5. **The presence gap is a taker-arrival gap, and the takers' information set is still unmeasured.** The fills are
   fresh joins matched about 0.7 s later by the next seller, and the profit comes from non-HFT first prints. What
   makes a non-HFT taker sell token s within a second? X28 tested only the futures trigger. The obvious candidate for
   a slow taker is what the Polymarket page shows: the RTDS Chainlink price against the "price to beat". It needs the
   publish ms of C2.

## Proposals (ranked by the chance they close the gap)

### I1. Score the Chainlink input on the historical lot with Polymarket's crypto-price endpoint (reopens X42; strong form of A1/X41)

- **Hypothesis.** The engine's reservation price follows the Chainlink BTC/USD stream (RTDS) on every day, not only
  on 10-31. In the smooth pre-10-31 regime the identifying variation is the drift between Chainlink and futures (the
  basis, Chainlink's aggregation and smoothing lag) rather than 1-s noise. A fair built on Chainlink stamped
  <= t-2 s, with the exact strike and the exact TWAP lock-in, therefore explains the historical fills, prints and
  sides better than the Binance futures fair in R3.
- **Why it fits.**
  - Iteration 6 found center R^2 0.21 for Chainlink at 2 s against <= 0.03 for every venue.
  - The Chainlink edge is the best univariate print score live (0.675 vs futures 0.525).
  - Futures beat Chainlink on quote levels in iteration 5 (MAD 0.037 vs 0.105). That race used single-side near-touch
    quotes and a stamping that was later corrected. It never used the fills of the lot.
- **Test.**
  1. Fetch the 1-s series through the polyrea `HttpClient`, so it is cached and rate-limited. Use at most 4 parallel
     requests and back off on 429. Pair windows: `eventStartTime` = st+k returns st+k and st+300+k, so a window costs
     150 requests.
  2. Sample design:
     - BUILD: 150 windows;
     - STUDY 10-23..26: 150 windows, case by case;
     - VALIDATE 10-27..30: 300 windows, stratified by hour and day, aggregate only.

     That is about 90k seconds, roughly 45k requests or 3 h in the background.
  3. Verify `priceToBeat(st)` = mean CL[st-61..st-2] on 20 windows.
  4. Build `fair_CL(t)` = digital(CL stamped <= t-2 vs priceToBeat, realised vol of CL or futures), with the known
     part of the closing TWAP in the last 60 s.
  5. On these windows compare, against the activity baseline:
     - (a) the fill price residual of cluster fills against `fair_CL` vs `fair_futures` (MAD, and the slope of fill
       price on fair - last print);
     - (b) R3 refitted with `fair_CL` replacing or added to the futures fair (BUILD), evaluated on the VALIDATE sample:
       presence AUC, side accuracy, print-level selection AUC with recall and lift, per-window PnL correlation;
     - (c) the same split by day.
  6. For the exam, give `final_rule.py` this endpoint as the Chainlink source, with the recorder as cross-check.
     Point-in-time comes from the stamp plus the measured publish delay (I2).
- **Data.** The endpoint (C1, verified), the lot fills and tape already on disk, and Gamma `priceToBeat` for BUILD and
  STUDY.
- **Signature if true.**
  - On STUDY and VALIDATE, `fair_CL` gives a smaller fill-price MAD than futures.
  - Over activity + futures it adds at least +0.02 bin presence, +0.04 print-level selection AUC and +0.02 side, every
    day and for each wallet.
  - The per-window PnL correlation rises.

  If it adds nothing historically but does so live, the Chainlink dependence is regime-specific (see I4). The
  historical gap then has to be explained by something else, and the NOTES claim "the engine reads the settlement
  stream" must be narrowed to 10-31.

### I2. Streaming RTDS with server publish ms: pin what the engine reads with a millisecond event study, and record it through the sealed blocks (new; strong form of the iteration-6 stamp convention)

- **Hypothesis.** Two readings remain.
  - **(A)** The engine reads Polymarket's public RTDS relay, the same one the web page uses. Its re-posts then move
    the center by the new value's innovation 50-150 ms after the relay publishes, the same reaction time it shows to
    CLOB trades (95 ms).
  - **(B)** It subscribes to Chainlink Data Streams directly. Its center then moves 0.5-1 s before the relay
    publishes: a real information lead over every public feed.
- **Why it fits.**
  - C2: relay publish delay 0.97-1.81 s.
  - The lag-2 peak matches (A) under the 1.5-s add window, and the stamp-based analysis cannot separate (A) from a
    slightly faster source.
  - The 0.84-s spread of publish delays means the stamp+2 alignment pairs the center with the wrong value in a large
    share of seconds. The held-out R^2 of 0.21 is probably understated.
- **Test.**
  1. Run a small streaming recorder now, before the 18:00 UTC sealed block: `filters: ""`, keep btc/eth/sol updates
     of both topics, text PING every 5 s, through `tools/live.py` `Writer`, hard stop 2026-11-02 00:00 UTC. After that
     filter it is about 6 messages a second, roughly 1 MB/h gzipped. Record it in `live_lab`.
  2. On dev blocks (10-31 17-18 UTC, 11-01 06-12):
     - (a) For each BTC update (stamp T, publish P), compute the center change of the cluster's exact-500 re-posts in
       25-ms bins from P-1,000 to P+1,000 ms, regressed on the innovation of `fair_CL`. Repeat with bins relative to
       T.
     - (b) Re-run the iteration-6 center race with the value available at the relay at each re-post's server ms,
       instead of stamp <= t-2.
  3. Use server clocks only: CLOB `s` and RTDS `timestamp`. Never the laptop clock (C2).
- **Data.** RTDS with `filters: ""` (verified), `dx_clob` schedule-size deltas, and the cluster's calldata for
  ownership.
- **Signature if true.**
  - (A): the regression coefficient is zero before P and steps up 50-150 ms after it. The arrival-aligned center race
    reaches held-out R^2 >= 0.3, with the residual autocorrelation lower than at 0.44.
  - (B): the step comes before P. Report the lead (ms, share of updates) as the unexplained part: "the engine sees
    the settlement stream X ms before the public relay".

  Either way, R5's Chainlink feature becomes exactly point-in-time.

### I3. What triggers the takers who fill it: the Polymarket page's Chainlink display (strong form of X28; the presence gap)

- **Hypothesis.** The non-HFT takers whose first prints pay the cluster, and the sell waves that a fresh touch join
  meets within about 0.7 s, are triggered by RTDS display updates. That is especially true when the displayed price
  moves toward or across the price to beat for token s. Presence at 10 s is bound by taker arrival. This trigger is
  the missing public input for that arrival, and the cluster's own Chainlink-skewed center positions it for exactly
  those waves.
- **Why it fits.**
  - Profit comes from non-HFT first prints: +5.7% on VALIDATE, about 0 against HFT.
  - Fills follow a trade that sold the token (61%).
  - Activity predicts presence only at 0.60-0.64.
  - Live, Chainlink lifts print selection more than futures does (0.70 vs 0.63).
  - X28 found latency takers acting on futures never fill the cluster. Its RTDS-display class was never built,
    because it needs publish times (C2).
- **Test.**
  1. Sample 20 minutes of all-match calldata in each dev block (takers' `sign_ms`) and take server-ms prints.
  2. Estimate the hazard of a taker SELL of token s (or a complementary BUY) in 0-3 s after each RTDS publish, as a
     function of the displayed move of `fair_CL` against s, and of a strike crossing by the displayed price. Compare
     it with the hazard after futures moves of the same size and at random times.
  3. Split by HFT and non-HFT takers (the iteration-6 classes).
  4. Add "time since the last publish that moved `fair_CL` against s by >= x" and its size to activity + Chainlink in
     the bin and print models (live BUILD fit, choice on 11-01 06-12).
  5. For a coarse historical version, use I1's series with the publish-delay model (T + 1.39 s) and the STUDY taker
     `sign_ms` (`b1_takers_study.parquet`).
- **Data.** RTDS streaming (I2), publicnode calldata, the shared `x` stream, the I1 series.
- **Signature if true.**
  - The non-HFT sell hazard on s rises 2-5x in the 0.3-2 s after display moves against s. Futures moves without a
    display move do not do this.
  - Cluster fills concentrate in those windows of time.
  - Bin presence gains >= +0.03 over activity + Chainlink.
  - Per-window cluster PnL correlates with display-driven non-HFT volume (>= 0.4).

  If takers ignore the display, presence is bound by flow the public record does not time, which is a quantitative
  wall statement for this component.

### I4. The 10-30/10-31 change in Chainlink's 1-s stream as a natural experiment (new)

- **Hypothesis.** A Chainlink-side change (aggregation, providers or report cadence) between 10-30 15:00 and 10-31
  00:30 UTC made the 1-s stream noisy. Since then the engine's center has carried that noise, because the engine reads
  Chainlink unfiltered. That is evidence for reading (a) of critique 2, and it explains the live loss on fills where
  Chainlink valued the token above futures (-4.6%). The alternative is that the cluster also changed (a new version)
  at the same moment.
- **Why it fits.**
  - C3: 26 of 28 pre-10-31 runs have a lag-1 autocorrelation above -0.19, while 13 of 14 runs on 10-31 are at or
    below it.
  - The rules text is unchanged.
  - Iteration 6's noise result and its "pricing off the settlement stream has a cost" finding both come from 10-31
    only.
- **Test.**
  1. With the endpoint, fetch 10-30 12:00 - 10-31 06:00 UTC at 1 s for BTC, ETH and SOL (feed-level aggregates
     only; 10-31 06-12 is sealed, so skip it). Per 10 minutes, compute the lag-1 autocorrelation of the changes and
     the sd of CL minus Binance spot 1-s (Binance archive). Find the change point and check that it is common to all
     symbols.
  2. Compare, in aggregate, the hours before and after the change on the lot side (10-30 evening) with the 10-31
     00-06 dev block. Measures:
     - cluster fills per window, size class and pair sum (from fills);
     - PnL per fill, and the share of fills with `fair_CL - fair_futures` > 3 c;
     - R4 price accuracy.
  3. In every new dev and exam block, report which regime holds.
- **Data.** The endpoint (C1), Binance spot 1-s, the cluster's activity on 10-30 (aggregate) and 10-31 00-06 (dev).
- **Signature if true.**
  - One sharp change hour across symbols.
  - The cluster's sizes and timing are unchanged across it, while its PnL on CL-above-futures fills drops after it.
    That is an engine that did not adapt.

  If the cluster changed at the same hour, record it as a new bot version (C4) and fit R5 on the new regime only. In
  both cases R5 should key on the `fair_CL` level, not on a noise-specific feature, so that it survives a reversion.

### I5. Is the Chainlink skew the cluster's own reading or inherited from other makers' quotes? (quote-level co-occurrence check of J4)

- **Hypothesis (null).** Other makers price off RTDS Chainlink. The cluster pegs to the book (depth-weighted mid,
  microprice, or the complementary book's implied mid). The center's Chainlink skew is then co-occurrence at the
  quote level, not the cluster's input.
- **Why it fits.**
  - The skew is measured against the touch mid, and the cluster joins existing levels in 68% of cases.
  - The iteration-6 race used only exchange feeds and Chainlink. No book-state candidate was entered, and other
    makers' quotes were not checked for the same noise.
- **Test.** Same dev blocks and the same streaming RTDS as I2.
  - (a) For each Chainlink update, the millisecond response of the cluster's exact-500 re-posts vs other makers'
    near-touch adds (other sizes, `dx_clob` deltas), in 25-ms bins after the publish.
  - (b) Enter book-state candidates (ex-cluster depth-weighted mid within 3 ticks, microprice, 1 - the complement's
    mid) into the center race. Check whether they carry the Chainlink noise and whether they lead the cluster.
- **Data.** `dx_clob`, RTDS streaming, calldata ownership (88% of exact-500 fills are the cluster's).
- **Signature if true (null).** Other makers respond to updates first and as strongly, and an ex-cluster book quantity
  explains the skew as well as Chainlink. The component must then be restated as book-pegging, and the activity
  baseline must include book state. If the cluster responds first and other makers weakly, the input is its own.

### I6. Kalshi KXBTC15M for the BTC 15m scope (strong form of A4b; low prior, cheap)

- **Hypothesis.** The BTC 15m center is undecided (held-out R^2 <= 0 for every input) because the 15m quotes are
  anchored on a quarter-hour price outside Polymarket. Kalshi's same-quarter BTC market (CF Benchmarks settlement) is
  the only such public price.
- **Test.**
  1. Kalshi public trades (µs) and 1-Hz orderbook polls for the matching KXBTC15M market during dev blocks. Fetch
     historical trades for STUDY quarter hours.
  2. Map Kalshi's floor strike and probability to an implied BTC level, and enter it in the 15m center race and in
     the 15m print-selection model next to `fair_CL` (with I1's series for history).
- **Data.** Kalshi public API (C4, verified), the I1 series.
- **Signature if true.** Kalshi or the implied level gives held-out R^2 > 0.1 on the 15m skew where Chainlink fails,
  and lifts 15m selection. Otherwise A4b closes as tried with numbers, and 15m stays on X40 (priced off the 5m book).

## Notes for the RE

- **Before 18:00 UTC if possible.** Start the streaming RTDS recorder from I2 (`filters: ""`), because the next block
  is sealed. Tell the shared recorder's owner that the symbol filter suppresses updates. Do not change `tools/live.py`
  yourself.
- **The point-in-time rule for Chainlink.** Use the relay publish ms where it was recorded. Otherwise use stamp
  <= t-3 s for strict tests (p90 publish delay 1.81 s, plus client latency) and report stamp <= t-2 as the optimistic
  variant.
- **Fetch etiquette for I1.** Go through the polyrea `HttpClient` cache, use at most 4 concurrent requests, and start
  with the STUDY and VALIDATE samples, which drive the primary metric. One 5m window costs 150 requests, and
  `eventStartTime` must be an ISO second (`YYYY-MM-DDTHH:MM:SSZ`).
