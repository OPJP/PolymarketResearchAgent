# Panel, iteration 7: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained, which data would most
sharply separate the leading explanations, and how that data can be fetched on this laptop.

All my checks used development data only:

- `calldata_sample.parquet` and `calldata_sample_txs.parquet` (sampled hours before H);
- the Binance USD-M BTC and ETH archives in `.cache/re/btc5m-bot/fut` and `venues/ethfut`, and `binance_1s.parquet`,
  all before H;
- Gamma `/events` for 144 windows on 2026-10-20 (VALIDATE), for the windows of the four VALIDATE calldata hours, and for
  two development windows on 10-31 at 13:00 and 13:05;
- `live6_events.parquet` and `post/cd6_live.parquet` (10-31 13:00-14:47, a development block);
- 13 Polygon blocks around block 96,499,000 (10-31 about 13:40 UTC), fetched in memory;
- a 12-second probe of public websockets at 17:36 UTC inside the 10-31 12-18 development block (the script asserts the
  block is development); it kept counts only.

Nothing raw was stored. No sealed unit was touched. Other agents' feeds were not read.

Scripts are in `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p7\`:
`eoa_cycle.py`, `ptb_check.py`, `edge_size.py`, `flow_size.py`, `copyidx.py` and `ws_probe.py`. The co-terminal and
signing-burst tables below came from short inline runs of the same loaders.

## Critique

1. **The unexplained side is the weak-vote regime, and its input has not been searched for.** Two facts frame it.
   - By vote strength, agreement is stable: about 65% at |vote| = 1 and 90-97% at |vote| >= 5. What changed between
     intervals is the mix: weak votes rose from 22% to 56% of voted matches as Saturday went quiet.
   - In weak votes no recorded series predicts the side: Binance USD-M 62-77%, Bybit ETH 56-74%, Hyperliquid 36-76%.

   The study has already twice found the right input on a channel it was not recording: first trades, then quotes, then
   sized quotes (the microprice). The ten quote series are still only BTCUSDT and ETHUSDT on five venues. The Binance
   books next to them are unrecorded, and they are very active. My probe at 17:36 UTC, on a quiet Saturday:
   - USDC-margined perps BTCUSDC/ETHUSDC: 140 bookTicker messages/s;
   - COIN-M BTCUSD_PERP/ETHUSD_PERP: 64/s;
   - spot BTCUSDC/BTCFDUSD/ETHUSDC: 21/s;
   - Deribit `quote.*-PERPETUAL`: 20/s.

   All four work without a key from this laptop, and so do Binance USD-M `@depth@100ms` and `!forceOrder@arr`.
   Coinbase Advanced Trade `level2` works, but its first snapshot is over 4 MB, so `max_size` has to be raised.
   Signed aggressive trade flow at exchange ms is already on disk (the `rest6_*` parquets). It has only ever been tested
   as price moves, never as signed volume in the weak-vote decisions.
2. **The historical settlement index was declared unavailable. It is not.**
   - Gamma `/events` carries `eventMetadata.priceToBeat` and `finalPrice` at full precision for every BTC 5m window. For
     example, 10-31 13:00 has priceToBeat 77414.6458 and finalPrice 77414.8076, and the latter is the 13:05 window's
     priceToBeat.
   - On 10-20 (144 windows), a 60-s TWAP of the Binance USD-M BTC last trade over [end-60, end) reproduces finalPrice
     within 0.35 bp median (p90 1.0 bp; spot 0.31 / 0.85 bp). The basis is point-in-time, taken from the previous six
     sampled windows, about an hour back. The raw offsets are -8.4 bp for futures and -12.7 bp for spot (USD against
     USDT).
   - A basis taken at each window's own open, from its priceToBeat, will be tighter still.
   - So A1_B3b (the last-minute lock-in) and X21 were left open on a false premise ("needs the Chainlink stream"). They
     can be run on all of VALIDATE.
   - My check also limits what this data buys. With the exact strike, a lognormal FV (k x realized vol, TWAP variance
     tau - 40) is still 3.6-3.9 c from the bot's taker prices at the block clock (k = 1.0-1.3). So the strike is not why
     X21's calibration failed; the vol and shape are.
3. **Information-based routes to the large size are closed at the block clock.**
   - Iteration 7 showed that moves do not predict it (AUC 0.44-0.59).
   - I added an exact-strike FV edge: within-wallet AUC 0.42-0.54 (DS, GF, XM at k = 0.6-1.8).
   - Aggressive perp flow over [B-4, B-1) s (traded notional, largest print, signed notional toward o, trade count) on
     4,583 taker orders: 0.44-0.61.
   - Windows that end on a 15m or 1h boundary show no different large share or pay-up. Ending on a 15m boundary: DS 0.119
     vs 0.080, GF 0.347 vs 0.356, XM 0.134 vs 0.154.
   - The large size is also not a ladder copy-budget effect. Within a signing burst there is no saw-tooth by order age:
     only GF's +42 s burst declines mildly (0.41 -> 0.31 over 0-140 s), and GF's +173 s burst, XM and DS are flat or
     rising. The share falls only slightly with the copy-use index at a level (GF 0.40 at k = 0, 0.32 at k >= 1). When
     a level holds both sizes, the first copy used is large in 47.6%.
   - It does not depend on the order's distance from the FV at signing either (flat).
   - What remains is millisecond information (vote strength, the Binance tick, the Polymarket depth seen about 300 ms
     before the match) or a per-event draw. Only weekday live blocks can separate those, and only if their inputs are
     recorded (point 5).
4. **The h1/h2 decision clock: one more route measured and closed.**
   - The operator sends matchOrders from a large random pool of relayer EOAs: 655 distinct senders for the 782 live
     cluster taker txs, and about 17 matchOrders txs per second overall.
   - Each EOA's nonce is monotone in match ms (127 of 127 pairs), but it advances only once per about 90 s. Only 3 of the
     38 EOAs in one block reappear 60 blocks (90 s) later, so there is no round-robin.
   - (EOA, nonce) is therefore no sub-second clock. This adds to iteration 6's four failed clocks (data-api timestamps,
     co-racers' signing ms, makers' signing ms, block production time) and to `tx_index`.
   - On h1/h2, the one lever left is information robust to +-1 s: levels, not ticks (proposal 2).
5. **The future-block exam will see a weekend regime and incomplete inputs.**
   - `rec_exam7.py` covers the sealed blocks 10-31 18-24, 11-01 00-06 and 11-01 12-18: Saturday night and Sunday, when
     the weak-vote share will be at its highest. It stops at 11-02 06:00 UTC, before any weekday sealed block (11-02
     06-12 is the first).
   - It records Binance USD-M, Binance spot and OKX only. Its vote covers 61.5% of matches, against 84.6% for the ten
     series. Bybit has a public 100-ms archive the examiner could rebuild for any sealed day, but `final_rule` does not
     use it.
   - It keeps only the size at the touch, plus 10-level snapshots every 10 s. A size or replay rule that needs depth at
     touch + 1 c around m - 300 ms has no input in any sealed block.
   - As planned, the first future exam is the one most likely to fail on side, PnL and size, for data reasons.
6. **The trigger statement claims more than the hazard shows.** P(match on o) rises from 2.3% to 8.7% per 500 ms with
   a strong tick toward o. So more than 90% of strong ticks bring no match, and the peak side information is 75% in
   100-ms bins. The tick is necessary in the active regime but not sufficient. Which ticks are acted on, and which size
   is sent, is information the study does not have yet. Unfilled submissions never reach the chain, and nothing in the
   public book attributes them (X15). So the hazard model should be read as P(submission) x P(win the race), not as the
   rule.

## Proposals (ranked by the chance they close the gap)

### 1. Record the rest of the Binance family, Deribit quotes, L2 depth and liquidations, and test them on the weak-vote decisions (strong form of X37 and X7, without waiting for Tardis)

- **Hypothesis.** The weak-vote and no-vote decisions are triggered by a quote stream outside the ten recorded series.
  The most likely candidates, for a Binance-centric bot, are:
  - the USDC-margined perps (BTCUSDC, ETHUSDC);
  - the COIN-M perps (BTCUSD_PERP, ETHUSD_PERP) and the quarterly;
  - spot BTCUSDC, BTCFDUSD and ETHUSDC;
  - level-2 queue changes on Binance USD-M, which happen before L1 moves;
  - liquidation prints;
  - Deribit perp quotes and Coinbase L1, mainly in US hours.

  Signed aggressive volume that never moves the L1 price is a further candidate, and it is already on disk.
- **Why it fits.**
  - Binance USD-M BTC is the earliest and sharpest series (m-300..-250 ms, 88%), so the bot is Binance-centric.
  - Weak votes are 64-66% accurate on every recorded series, and their share drives the decay from 86% to 75%.
  - The bot reacts within 250-400 ms, so its input must be a fast stream, and the active unrecorded Binance books are
     exactly that (critique 1).
- **Test.**
  1. Step 0, with data in hand (about 10 min). On the 14:14-16:25 matches with |vote| <= 2 or no vote, measure the side
     agreement and the 50-ms kernel of the net signed aggressive notional on Binance USD-M BTC and ETH over
     [m-600, m-100). Use `rest6` aggTrades at exchange ms and the frozen placebo instants.
  2. Step 1. A small recorder through the Writer, in development blocks first (about 2-3 MB/h with 30-ms coalescing).
     The endpoints below were verified today:
     - `wss://fstream.binance.com/stream?streams=btcusdc@bookTicker/ethusdc@bookTicker/btcusdt@depth@100ms/ethusdt@depth@100ms`;
     - `wss://dstream.binance.com/stream?streams=btcusd_perp@bookTicker/ethusd_perp@bookTicker`;
     - `wss://stream.binance.com:9443/stream?streams=btcusdc@bookTicker/btcfdusd@bookTicker/ethusdc@bookTicker`;
     - `wss://fstream.binance.com/ws/!forceOrder@arr`;
     - Deribit `public/subscribe` on `quote.BTC-PERPETUAL` and `quote.ETH-PERPETUAL`;
     - Coinbase Advanced Trade `level2` BTC-USD, with `max_size` of at least 16 MB.

     Run it on 11-01 06-12 and 18-24, 11-02 00-06, and 11-02 12-18 (the first US-hours block).
  3. Step 2. For each new series:
     - the 50-ms directional-excess kernel, as in `kernel7.py`;
     - agreement and coverage on the decisions where the frozen vote is weak, wrong or silent;
     - a sparse logistic over all series on [m-600, m-240), fitted on one block and tested on the next.

     As a secondary target, P(large | series strength) for the size.
  4. Step 3. If a series passes, add it to an exam-input recorder (Writer, every block) before the next sealed blocks,
     with a hard stop beyond 11-02 06:00.
- **Data.** Public websockets (no key), the `rest6` parquets, the v2 lab feeds, and on-chain cluster fills for the
  development blocks.
- **Signature if true.**
  - One series, or one L2 feature, has a sharp onset at m-250..-400 ms.
  - It agrees at least 80% on weak or no-vote decisions and covers at least 30% of them.
  - The decision-level side then reaches 85% or more in the quiet intervals, and stays there on the next block.
  - If false: no fast venue moves before those decisions. The weak-vote residual is then quantified as not a tick, and
    weight moves to proposal 2.

### 2. The settlement index, recovered from Gamma: time-driven value (theta and the TWAP lock-in) as the trigger of the quiet late decisions (strong form of A1_B3b and X21; new data source)

- **Hypothesis.** The quiet decisions are value decisions driven by time, not by moves. Two effects move the FV with no
  price change:
  - theta: at fixed S - K the FV changes as tau shrinks;
  - the TWAP lock-in: in the last minute, the observed partial average pins the settlement.

  Polymarket quotes do not reprice with time. The bot then lifts the outcome whose ask fell behind its FV.
- **Why it fits.**
  - The quiet share by window third is 24% / 38% / 69%.
  - Weak votes come later in the window (mean rel 142-170 s vs 109-123 s).
  - Pay-up rises from 13-15% to 35% at 240-300 s, and late small orders near 0.5 lean to the favourite (44.5%).
  - For small orders at |p - 0.5| 0.3-0.4, the underdog tilt fades through the window: 0.62 at 0-60 s, then 0.62, 0.59,
    0.51 and 0.48 at 240-300 s (`tilt7.json`). A constant vol multiplier cannot produce that, because at a fixed p it
    predicts the same tilt at every tau. A time-dependent value term can.
  - Unlike ticks, levels survive the +-1 s block clock, so this is the only information route that could lift h1/h2
    (critique 4).
- **Test.**
  1. Fetch `eventMetadata.priceToBeat` for all 4,032 BUILD and VALIDATE windows (one Gamma `/events?slug=` GET each).
     Use `finalPrice` only as a BUILD training label for the index replica.
  2. Index replica: Binance USD-M (plus spot and OKX, weights fitted on BUILD) times a basis fixed at each window's open
     from its own priceToBeat. Target error: at most 0.3 bp median against finalPrice on VALIDATE.
  3. FV with market-implied sigma per window (fitted on the window's mids before the decision, BUILD-calibrated), in two
     versions: FV_TWAP (true settlement with the observed partial average A) and FV_spot (as if settled at the end price).
  4. On every VALIDATE taker order and one-sided second at rel >= 180 s:
     - side vs sign(FV_o - ask_o) under each version, quiet (no move on the ten historical series) against moving;
     - the "theta hazard": where the touch of o has not changed for at least 3 s, does the cluster's hazard of buying o
       rise with the time-only FV change since the last touch change?
     - X30 step 3: the revealed-preference sigma multiplier per window third, compared with realized vol and with Deribit
       DVOL (X7 options).
- **Data.** Gamma events (about 4,000 small GETs through the cached adapter) and the Binance and OKX archives already
  reduced.
  - For exam windows, `final_rule` must read priceToBeat only; it is known at the window's open, so it is
    point-in-time. It must never read finalPrice.
- **Signature if true.**
  - In quiet late seconds the side is at least 75% under the right settlement model.
  - The two models disagree in at least 15% of late seconds, and the bot sides with one of them at least 65% of the time.
  - The theta hazard steps up.
  - A sigma profile reproduces the fading tilt.
  - The gain persists at the block clock, which matters for h1/h2.
  - If false: the late quiet decisions are not time-driven value. Then they are an unrecorded tick (proposal 1) or a
    rebate-driven decision near the break-even point, at 64-66% side.

### 3. Make the future-block exam's inputs complete: weekday sealed blocks, the Bybit archive, near-touch depth and the proposal-1 series (strong form of X34)

- **Hypothesis.** As recorded today, the first future exam cannot show the decoded components. It gets weekend blocks
  only, six of ten series, and no near-touch depth. The rule will fail there for data reasons that can be fixed now.
- **Why it fits.** Critique 5. On the 16:04-16:25 interval the six-series vote covers 61.5% at 80.4%, against 84.6%
  coverage for the ten series. The weak-vote share was 56% by Saturday evening, and the sealed blocks recorded so far
  are Saturday night and Sunday.
- **Test.**
  1. Extend `rec_exam7` (or start a second exam recorder through the Writer, with its own disk budget) past 11-02 06:00,
     to cover the weekday sealed blocks 11-02 06-12 and 18-24 and 11-03 00-06 and 12-18.
  2. Add the Polymarket near-touch book (within 2 c, every change, with server ms), as `btc5m_clob_raw2` already does in
     development blocks, so a size or replay rule has its inputs.
  3. Add any proposal-1 series that passes.
  4. Add the Bybit ob200 public archive (already in `bybit_ob.py`) to `final_rule._live_vote` as an archive input that
     the examiner can rebuild for sealed days.
  5. On development blocks, check that the archived 100-ms Bybit vote restores the ten-series coverage.
  6. Pre-register which sealed blocks the side and size claims are made on (weekday ones), and report the weekend blocks
     separately by vote-strength mix.
- **Data.** Existing recorders, extended, and Bybit `quote-saver.bycsi.com` ob200 daily files.
- **Signature if true.**
  - Status counts show weekday sealed hours with venue quotes and near-touch depth.
  - On development blocks the vote with archived Bybit covers at least 80% at the six-series accuracy.
  - The examiner can then score side, size and the replay replica (X36) on weekday sealed blocks, where the strong-vote
    share is like VALIDATE's.

### 4. The bot's decision instant on a single clock: the limit against the Polymarket touch at m - L, at 10 ms (strong form of X39 and X41, for the Polymarket leg)

- **Hypothesis.** The limit is the touch the bot saw at its decision instant d, plus a deliberate pay-up. The lag
  L* = m - d is a fixed latency of the bot's Polymarket leg. It can be measured on Polymarket's server clock alone, so
  the +-100 ms cross-exchange clock uncertainty that blurs the venue kernels does not enter.
- **Why it fits.**
  - Iteration 5, on the throttled 200-ms book: the limit equals the ask at m - 50 and m - 100 ms in 70.8% of matches, but
    only 32% at m - 500 ms.
  - The venue kernels disagree by 50-150 ms between analyses: Bybit peaks at m - 400 in `kernel7` but at 200-250 ms in
    iteration 6's `lagmode`. That is the size of the clock uncertainty.
  - Pay-up (17% overall, 42% at 100 shares) mixes two causes: a stale view (the ask fell after d) and a deliberate
    sweep.
- **Test.**
  1. On `btc5m_clob_raw2` (unthrottled, within 2 c, server ms) for all development taker matches, compute
     P(limit == ask_o(m - L)) for L in 0..800 ms in 10-ms steps, on matches where the ask changed in that span, against
     placebo.
  2. Locate L* (the end of the plateau).
  3. Re-align the ten-series kernel on d = m - L* and check whether the side peak sharpens.
  4. Split pay-up orders into ask(d) > ask(m) (stale) and ask(d) = ask(m) < limit (deliberate), by size.
- **Data.** Existing v2 lab feeds and live calldata.
- **Signature if true.**
  - There is a plateau with a sharp drop at a stable L*.
  - The kernel aligned on d is narrower than the one aligned on m.
  - Most small-order pay-up is stale view, while large-order pay-up is deliberate. That gives the replica (X36) the
    bot's information set at d, and it isolates the "aggressive" decision (large and sweep) as the one left to decode.

### 5. Co-terminal cross-market consistency: the Polymarket BTC 15m, 1h and 4h windows that end with a 5m window (strong form of X8)

- **Hypothesis.** A 5m window that ends on a 15m, 1h or 4h boundary settles on the same TWAP-60 at the same instant as
  the longer window. Given both priceToBeats, the longer market's price implies P5. The bot lifts the 5m outcome that is
  cheap relative to that implied value. This is a level signal that needs no venue tick.
- **Why it fits.**
  - X8 tested only moves of the 15m mid in the last 1 s (66% vs 54%), and 1h and 4h were never tested.
  - Polymarket's longer markets are a second, slower-updating market estimate of the same random variable.
  - My window-level check found no difference in size or pay-up, so this is a side or presence test only. That is why it
    is ranked low.
- **Test.** On VALIDATE, for the windows co-terminal with 15m and 1h windows:
  1. Take the longer window's last implied price before each decision (data-api taker tape) and both priceToBeats from
     Gamma.
  2. Compute P5_implied with market-implied sigma.
  3. Score the cluster's side in quiet one-sided seconds against sign(P5_implied - P5_mid).
  4. Compare the hazard against |gap|, against non-co-terminal windows and against a time-shift null.
- **Data.** data-api tapes of BTC 15m and 1h windows in VALIDATE (cached adapter), and Gamma events.
- **Signature if true.**
  - Quiet-second side agreement of at least 65% with the gap in co-terminal windows, against 50% in others.
  - The hazard rises with |gap|.
  - If false: Polymarket's other windows are followers, which closes X8 including 1h and 4h.

## Not proposed (measured here, low value)

- **The operator EOA nonce as a historical clock.** It comes from a random pool with no round-robin (critique 4).
- **The exact-strike FV edge, perp flow, signing-time FV distance and the ladder copy budget as predictors of the large
  size.** All are flat or at most 0.61 AUC at the block clock (critique 3).
- **A Chainlink Data Streams stream for the level.** The Gamma-anchored Binance replica already gives 0.3-0.35 bp
  (critique 2). PolyBolt needs CLOB credentials and stays out of bounds.
