# Panel after iteration 4: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations. I read BRIEF.md, NOTES.md, state.json, FINAL_RULE.md, EXAM.md and the two
other iteration-4 panel files (assumptions, mechanics). I ran small checks on development data only: the 2026-10-31
12:00-18:00 UTC block (current, development), live websocket probes of at most 150 s (nothing stored), and one
Deribit call for a BUILD day. Scratch scripts are in my session scratchpad. Nothing in `.cache/live/sealed/` or in a
sealed period was read.

## Critique

1. **The Chainlink settlement feed is already recorded. The notebook says it is not.** NOTES and state.json
   (`live_lab_note`, A1, X3) say the recorder's rtds feed "wrote 0 records". The status counter `written` is simply
   never incremented by `rtds_feed`. `.cache/live/dev/rtds/` holds 300 snapshot messages for 12:07-13:50 UTC. Each
   carries 59 one-second values of the Chainlink price (delivered under topic `crypto_prices`) or of the Chainlink
   TWAP-60 (`crypto_prices_twap_sixty`), for btc, eth and sol. Two defects:
   - Coverage is about 52% of seconds: about 50 snapshots per topic and symbol in 90 min instead of about 108, so
     each reconnect returns only some of the six subscriptions. There are 40-56 gaps per series.
   - The newest value in a snapshot is 1.8 s old when it arrives (p10-p90 1.3-2.3 s, corrected for the laptop clock).
   A1, A1_B3b and X3 are therefore not blocked by data any more.
2. **The laptop clock is 1.05 s slow and is not synchronised.** Binance spot and futures `/time` minus the local
   midpoint is +1,049 to +1,099 ms (RTT 270-350 ms). `w32tm /query /status` shows Leap Indicator 3 (not
   synchronized) and a root dispersion of 9.7 s. The shared recorder stamps `t` with this clock. For trade records,
   server `s` minus `t` has a median of +833 ms. Any live-lab timing built on `t`, for example the pilot's "fill =
   best bid 2 s before the block", is off by about a second and can drift. Every lead-lag study must use server
   stamps: CLOB `s`/`timestamp`, Binance `E`/`T`, the RTDS payload `timestamp`. The same applies to any new recorder,
   including the `btc5m_bnfut` feed that another agent writes into the shared dev folder (check its clock before
   reusing it).
3. **The features run about 2.3 s behind what the bot sees.** The recorder's `x` records carry the transaction hash.
   127 of the cluster's 148 BTC 5m transactions on 10-31 12:00-13:13 are in that stream. Block timestamp minus server
   match time is 2,296 ms (median; p10-p90 1,412-3,032 ms), more than the brief's "up to 2 s". The bot quotes off
   matches as they happen. Every tape feature, the price anchor and the oracle-flow diagnostic see each print about
   2.3 s later, and the anchor also drops same-second prints. That is two or more of the cluster's requote cycles.
4. **The shared book recording is too coarse for the quote-state question.** It writes the top 10 levels at most
   every 200 ms per token, while the raw market channel carries about 165-310 single-order events a second for one
   BTC 5m window. On 10-31 12:00-13:13 I decoded the calldata of the cluster's 148 BTC 5m transactions: 44 distinct
   orders, 116 of 138 order rows at 500 shares, and odd sizes 352.7 and 53.45 that look like re-signed remainders.
   Only 15 of the 44 orders (34%) show an exact +size delta at their level in the 120 s before the fill. The
   mechanics panel's P1 (unaggregated recorder plus size fingerprint) is the right fix. Its data warning: my two
   probes saw ±100-share events at 11-26 a second, while the assumptions panel's 75-s probe saw 0.56 a second. So
   another maker also uses 100 at times, and the size class has to be validated against calldata before it is
   treated as the cluster's.
5. **The A-series event studies were never run against decision times.** B1 gave no signing ms (`timestamp = 0`),
   so A2/A3 were judged from correlations of fill prices with fair values at the taker's signing ms. That clock is
   the taker's decision, not the cluster's. "Futures fits everyone better" says nothing about which feed triggers the
   cluster's requotes, or at what latency. The exposure window measured on 10-26 (adverse moves of the last
   0.25-1.5 s, favourable after 2 s) is too long for a co-located Binance reader (tens of ms). It is too short for
   the RTDS relay (about 1.8 s). This is the most informative unexplained number in the notebook, and no study has
   targeted it.
6. **The size schedule's weekend clause is contradicted.** The calldata above shows 500-share orders on Saturday
   afternoon (the assumptions panel found 500s on Saturday 00-06 UTC too). The size is a runtime setting, and the
   remainders suggest a target-minus-filled re-sign. Key any size fingerprint to calldata, not to the clock.

## Proposals (ranked by the chance they close the gap)

### I1. Identify the cluster's reference feed from server-clock lead-lag of its quote changes (new; strong form of A2/A3)

- **Hypothesis.** The cluster requotes off one specific feed with a fixed latency. Candidates: Binance USD-M futures
  bookTicker or trades, Binance spot, Coinbase, OKX, Bybit, the Hyperliquid perp, Polymarket's RTDS relay, or the
  Chainlink stream. Its quote is a fixed function of that feed and of the book. With the feed and latency known, "is
  its bid at the top at t" can be computed from public inputs: its implied quote at t against the recorded best bid.
  That is the binding presence gap (oracle diagnostic: 0.73 even with the bin's own future flow).
- **Why it fits.** The 0.25-1.5 s exposure window (critique item 5). The requote rate follows Binance activity
  (Spearman 0.67). The futures fair fits limit prices better than spot. Probe (150 s, 10-31 13:50 UTC, quiet
  Saturday, server clocks): in the 0-100 ms after a Binance futures bookTicker mid move, CLOB events of size 5, 10
  and "other" rose to 1.85-2.0 times their base rate. The ±100 class fell to 0.45-0.64. So some size classes are
  event-driven and others look timer-driven. The sample is too small to conclude anything; it shows the method
  works.
- **Test.**
  1. Run a recorder with the `Writer` (hard stop, < 100 MB memory, < 300 MB disk). Feeds, BTC only: Binance futures
     and spot `bookTicker` + `aggTrade` (stamp `E`/`T`); Coinbase `ticker` and `matches` (`time`); OKX `tickers` and
     `trades` (`ts`); Bybit `tickers` and `publicTrade` (`ts`); Hyperliquid `l2Book`/`trades` (`time`); RTDS (payload
     `timestamp`). Keep the CLOB raw `price_change` and `last_trade_price` stream for the current and next BTC 5m
     market (mechanics P1), with server `timestamp`.
  2. Run it through the coming development blocks (10-31 12-18, 11-01 06-12 and 18-24, 11-02 00-06 and 12-18 UTC;
     the last is the first weekday US session). The `Writer` files sealed blocks for the examiner automatically.
  3. Define the cluster's decision events: (a) changes of its fingerprinted quotes (size class validated against the
     calldata of its fills in the block); (b) as a fallback that needs no fingerprint, the last change of the level
     where it is later filled, before the server match time of each fill (from `x` by transaction hash).
  4. For each feed, compute the cross-correlation of decision events with feed mid moves of at least $2, at lags of
     -300 to +2,000 ms in 10-ms bins. Run a signed horse race: which feed's move over the last L ms best predicts the
     direction and size of the cluster's next quote change? Use a conditional logit of direction on all feeds'
     returns at several lags.
  5. Freeze the winning feed and latency on the first blocks. Test on later development blocks, then examine on
     sealed blocks.
- **Data.** Public websockets only (all verified to work from this laptop in the brief or here), the shared CLOB
  recording, publicnode calldata for the cluster's fills in the blocks.
- **Signature if true.** One feed shows a sharp peak at a fixed lag (for example 30-80 ms after Binance futures, or
  about 1.8 s after RTDS) that the other feeds lose once that one is conditioned on. The quote direction follows that
  feed's last move in at least 85% of quote changes. The exposure window equals its latency plus the requote period.
  A quote rule "fair(feed at t - lag) minus the offset, capped by the book" puts at least 80% of fills within one
  tick and lifts presence well above 0.72 on development blocks. If no feed peaks and the class is timer-driven, the
  trigger is a clock with a tick period visible in the inter-event times. That is also decodable.

### I2. Decide on the match clock, not the block clock (new)

- **Hypothesis.** The bot's information set at a decision is the matching engine's trade and book stream, about
  2.3 s ahead of the block-stamped tape. Part of the price rule's 29% misses, and part of the presence model's
  reliance on generic activity, come from anchoring on prints the bot saw two requote cycles earlier, and from
  dropping same-second prints it did see.
- **Why it fits.** Critique item 3: block minus server match time is 2,296 ms (median). The price anchor improved
  from 0.585 to 0.709 within one tick only through better print ordering and refits. Within-second order mattered
  (0.506 vs 0.585 with an unstable sort). Its fills follow a favourable 2-5 s move of its token, so it reacts to
  recent state.
- **Test.**
  - Live: in the development blocks, rebuild the price anchor and the R3 features from the recorder's `x` stream
    (server `s`, transaction hash, size, side) instead of data-api block times. Use prints matched at or before
    t - L, with L in {0, 250, 500, 1,000} ms. Compare within-tick and presence AUC with the block-time version on
    the same fills and bins, against an activity baseline built the same way.
  - Historical: the all-match calldata pilot (10-26 13:00-13:30, 9,778 transactions) already holds every match's
    taker signing ms. Recompute the anchor on that clock for a few STUDY hours (2-3 more hours of all-match calldata
    is about 40k transactions, a few minutes at about 75 tx/s).
- **Data.** Shared `clob_crypto` `x` records (have), calldata (have, or a small fetch).
- **Signature if true.** Within one tick rises toward 0.8, presence gains at least 0.02 over the block-clock
  version, and the gain over the same-clock activity baseline grows. It is legitimate on the examiner's live sealed
  blocks, because the websocket publishes at match time.

### I3. Use the Chainlink recording that already exists: fix coverage, then race Chainlink against Binance futures as the quote reference (strong form of A1 / A1_B3b / X3)

- **Hypothesis (E3, settlement-informed).** The cluster prices off the settlement feed: the Chainlink 1-s price and
  TWAP-60 against the true strike `priceToBeat`. Binance plus a fixed basis is not its reference. The difference
  shows where the Chainlink-Binance basis moves (5-95% range -116 to -63 USD) around the open and in the last
  minute.
- **Why it fits.** Settlement is Chainlink TWAP-60. The opening side follows the strike gap (66%, 76-79% when the
  gap exceeds 3 bp), and that gap is measured against a Binance proxy strike. The side model is strongest at the
  open (0.735-0.769 in the first 30 s). The RE never tested it against the real strike, because "Chainlink is not
  recorded" (critique item 1).
- **Test.**
  1. Own RTDS recorder: one connection per (topic, symbol), restarted every 25 s with the six streams staggered,
     dedupe on (topic, symbol, timestamp). That gives about 100% second coverage. Also try `type: "update"`
     subscriptions; my 75-s probe got only the snapshot.
  2. Check on development windows which topic reproduces settlement (TWAP at the end = the next window's
     `priceToBeat`).
  3. Horse race on development blocks:
     - (a) fill prices and fingerprinted quotes against a TWAP-60 fair from Chainlink 1-s with strike =
       `priceToBeat` (known from the window start), against the Binance futures fair with the Binance strike
       (MAD, correlation);
     - (b) opening side against sign(Chainlink(t) - `priceToBeat`) and against sign(Binance(t) - Binance strike),
       in windows where the two disagree;
     - (c) last 60 s: P(Up | the partly observed closing TWAP) against the cluster's late side and its stop time.
- **Data.** RTDS (works; recorded now), Gamma `priceToBeat` for development windows, Binance futures (have or
  record).
- **Signature if true.** The Chainlink fair beats the futures fair on quote residuals. In disagreement windows the
  opening side follows the Chainlink gap in at least 70%. Late fills lean to the side the partial TWAP favours. If
  false, the futures fair wins everywhere and E3 is closed with evidence, which the catalog still lacks.

### I4. Implied volatility as the fair value's vol input (strong form of A3; the options part was never tried)

- **Hypothesis.** The cluster's fair value uses an implied vol (Deribit DVOL, or short-dated ATM IV) rather than the
  1-s realised vol in R2/R3. The quote's steepness around the strike follows the implied vol, and the "1.4x realised
  vol" that fit the fills better (iteration 1) is the variance risk premium.
- **Why it fits.** A 1.4x scale on realised vol fit fill prices better (MAD 0.058 vs 0.068). The scale was never
  allowed to vary over time. The worst VALIDATE losses were near the money (fair 0.4-0.6: -14.9%), where the vol
  input matters most. The DVOL history works from this laptop: `public/get_volatility_index_data` for BTC at 60-s
  resolution returned 361 points for 10-16 00:00-06:00 (about 38.7).
- **Test.** Fetch DVOL at 1 min for 10-09..30 (about 30k points, cached). Also fetch hourly snapshots of the nearest
  Deribit expiry's ATM IV (`get_book_summary_by_currency`; live only, record it in development blocks). Fit the fill
  prices, and later the fingerprinted quotes, with fair(z; sigma = k x DVOL per second) against
  fair(z; sigma = k x realised), with k fitted on BUILD. Check the residuals for a vol-regime structure: per-day
  fitted k against DVOL / realised. Then add the DVOL fair edge to R3 and to the side model.
- **Data.** Deribit public API (verified).
- **Signature if true.** With the DVOL-based fair, one constant k fits every day while realised needs a drifting
  scale. Residual MAD falls and near-the-money side accuracy rises. If false, per-day k tracks realised vol and DVOL
  adds nothing.

### I5. Settlement-disagreement windows: does the cluster lean to the true outcome when the Binance proxy is wrong? (new; cheap historical test of E3)

- **Hypothesis.** If the cluster saw a better estimate of the settlement than Binance, its net position before the
  stop (fills up to end - 30 s) would favour the Chainlink outcome in the windows where the Binance-TWAP proxy
  outcome is wrong (1.9% of windows) and in near-strike windows.
- **Why it fits.** The proxy misses 1.9% of outcomes, and those windows are where the settlement feed is worth the
  most. The test uses only data already on disk.
- **Test.** BUILD + STUDY (and VALIDATE in aggregate). Take all windows where the Binance-proxy outcome differs from
  the real one, about 100 windows, plus windows whose proxy margin is within the 10% closest to the strike. Compare
  the sign of the cluster's net shares (Up minus Down) at end - 30 s with the real outcome. Do the same for the
  other makers' net maker buys (maker rows or calldata) and for the last clean print. The outcome is a label for
  description only; nothing is fitted.
- **Data.** Windows, outcomes, fills and Binance 1-s (all have).
- **Signature if true.** The cluster's late net side wins at least 65% of the disagreement windows, while the market
  and other makers are at or below 50%. That would be strong evidence for a settlement-side input and would make I3
  the priority. If false (about 50% or less), E3 is dead for the historical data, and I1 and I2 are where the gap
  is.

## Notes for the RE

- Development blocks ahead (`tools/sealed.py`): 10-31 12-18 (current), 11-01 06-12 and 18-24, 11-02 00-06 and
  12-18 UTC (verified with `sealed.future_block_sealed`). Start the recorders in I1 and I3 now: Monday 11-02 12-18 UTC
  is the first weekday US-session development block.
- Use the `x` records' transaction hash to get the server match ms of every cluster fill. No calldata or taker clock
  is needed for that.
