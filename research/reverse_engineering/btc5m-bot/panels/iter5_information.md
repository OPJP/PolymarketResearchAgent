# Panel, iteration 5: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained. That covers the
settlement feed, other venues and derivatives, Polymarket's own books and real-time feeds, and cross-market prices.
Which data would most sharply separate the leading explanations, and how can it be fetched on this laptop?

All my checks used development data only:
- the 10-31 13:00-13:24 development block, read through the investigator's `live_lab.recs` (which calls `iter_live`);
- `live_lab_cluster_orders.parquet` and the Binance futures REST parquets in `.cache/re/btc5m-bot/post/`;
- time-bounded REST trades from Binance spot and Coinbase for 13:00-13:24 only, kept in memory;
- the data-api taker tape of the five recorded development windows;
- the VALIDATE files `val_side_it4b.parquet`, `val_side_moves_iter4.parquet` and `val_pred_it4b.parquet`.

The scripts are in my scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`burst_order.py`, `burst_who.py`, `quiet_venues.py`, `cross_market.py`, `fv_calib.py`). Nothing was written to the
workspace except this file, and no sealed data was touched. Throughout, "quiet" means a taker match with no Binance
USD-M BTC or ETH trade move of more than 0.05 bp in the last 1 s. That is 183 of the 265 matches.

## Critique

1. **The quiet trigger is public and shared, and it is not in any trade feed recorded so far.** My numbers agree with
   panel-mechanics point 1 and add the following.
   - In 87% of quiet matches, another trader traded the same token within ±300 ms (placebo 55%).
   - Within those bursts the bot is first in 32% and last in only 14%. Its next other trade comes sooner (median 112 ms)
     than its previous one (212 ms).
   - The co-takers in the quiet bursts are 194 distinct wallets (632 co-trades, mapped from tx hashes through the
     data-api tape). The fourth sibling W4 is 3.3% of them and 0x9d57c42e 0%. Against non-siblings only, the bot is
     still first in 33% of the 159 quiet bursts.
   - So the crowd is real and diverse, and it reacts to the same instant as the bot. In the last 1 s before the quiet
     matches:
     - Binance spot BTC moved before only 3.8% of them (ETH spot 1.1%), against placebo rates of 1.8% and 1.8%.
     - Coinbase BTC-USD moved before 13.1%, agreeing with the side 75% (placebo 9.8% moved, 50% agreement). Over the
       last 500 ms it moved before 7.7%, agreeing 79% (placebo 4.5% and 60%).
     - Other Polymarket crypto markets traded before the quiet matches at close to placebo rates: BTC 15m 31% vs 28%,
       ETH 5m 25% vs 21%, ETH 15m 14% vs 7%. SOL 5m is the exception at 27% vs 13%, with net direction agreeing
       52-64% (n = 17-44).
   - The trigger is therefore something the whole crowd sees within a few hundred ms that no trade tape shows. That
     leaves top-of-book quotes on venues, Polymarket book events, or a venue nobody has recorded.
2. **The live trigger study looks at too little, too narrowly.**
   - It uses 22 minutes and 265 matches, while the 12:18-18:00 development block will hold well over 2,000 taker
     matches.
   - Its "moving" label uses only two series (Binance futures BTC and ETH trades over 1 s). The historical "no-move"
     label used ten series over 3 s and covered 18.7% of one-sided seconds. So the 69% live "quiet" share and the
     historical 18.7% are not comparable. Reconcile the definitions before calling 70% of orders unexplained.
3. **Every recorder used so far is blind exactly where the quiet trigger would live.**
   - The shared `clob_crypto` book is throttled to one top-10 record per token every 200 ms. It has had 26
     slow-consumer reconnects. A cheap ask that appears and is lifted inside 200 ms is invisible, and the "ask 50 ms
     before the match" can be up to 200 ms old.
   - `rec_binance_fut.py` drops every bookTicker update whose prices did not change, so queue and microprice changes
     are lost (panel-mechanics point 2).
   - The shared `rtds` feed stores only the 60-s snapshots sent on each (re)subscription: `type` is "subscribe",
     stamps are whole seconds, and the feed reconnects every 50 s. No message records when a Chainlink value
     actually arrived, and the recorder sends no application-level PING. "Chainlink RTDS carries no side information"
     therefore holds only at 1-s resolution, with availability assumed at the end of each second.
4. **The fair value used to reject the edge trigger is not calibrated.** H4 was rejected, and the live
   `fv_minus_ask` (B3/E7) was run, with fair values whose error is several times the edge being tested.
   - The FV in `live_trigger.py` uses the Chainlink 1-s return std and K = the TWAP-60 at the open. Against the
     recorded Up mid at 209 random instants (5 windows, 13:00-13:24), its median absolute error is 15.3 c (IQR -12.8 to
     +17.6 c).
   - Scaling the vol by 0.4 gives the best fit, and the error is still 4.9 c (corr 0.88). The market implies roughly 0.4
     times the 1-s realized vol.
   - The iteration-1 historical FV had a MAD of 4.6 c.
   - The placebo distribution is just as wide, so `fv_minus_ask` could not have shown an edge trigger even if one exists.
5. **The side in quiet seconds is anti-favourite, and the settlement distribution does not pay for it.**
   - In VALIDATE one-sided seconds where neither the six BTC series nor ETH moved (n = 14,480), the bot buys the
     favourite only 41.0% of the time. The share falls as prices get more extreme: 45%, 44%, 39% and 32% for
     |m - 0.5| in 0.03-0.1, 0.1-0.2, 0.2-0.3 and 0.3-0.4. In moving seconds it is 46.5%.
   - Yet on VALIDATE the market overprices underdogs. Implied asks of 0.05-0.15, 0.15-0.25 and 0.25-0.35 win 2.9, 1.9
     and 1.5 c less than their price; asks of 0.85-0.95 win 1.6 c more. Cells were sampled every 10 s with no CI.
   - So the quiet-regime side is not a "better settlement distribution" edge. It is the side the crowd is buying, or the
     output of a fair value that disagrees with the market (point 4).
6. **"No public Polymarket book history before 10-31" is not established.**
   - The pmxt v2 archive publishes hourly Parquet dumps of the CLOB market channel (`book`, `price_change`,
     `last_trade_price`, `tick_size_change`, with server and receive timestamps). Its documented key pattern is
     `polymarket_orderbook_YYYY-MM-DDTHH.parquet`, at 100-400 MB per hour.
   - From this laptop at 13:50-14:00 UTC, `archive.pmxt.dev` (65.109.107.152) refused connections on ports 443 and 80.
     The pmxt API answered 401 `{"error":"missing api key"}`. Do not create an account. Guessed `r2.pmxt.dev` keys
     returned 404.
   - The Hugging Face dataset `trentmkelly/polymarket_historical_data` has full-book snapshots, but only every ~5
     minutes (too coarse). It also contains sealed dates: never load those.
   - The Hugging Face dataset `whodisidk/polymarket-sol-updown-exchange-data` (SOL Up/Down, 2026-06-09..08-29) pairs
     Polymarket books with Binance and Hyperliquid books at 100 ms. People building Up/Down bots record Hyperliquid as a
     reference, and no iteration has looked at Hyperliquid.
7. **Smaller points.**
   - The live tx order inside a block is consistent with the match order in only 73% of pairs (325 of 443). Match to
     block is 1.28-3.25 s (5-95%, n = 768 txs). Every historical lead-lag test at block-second resolution is therefore
     blurred by about ±1 s.
   - The status file showed `rtds` connected = false and written = 0 at 13:43 while its hourly file kept growing. That
     is worth one look at the recorder.

## Proposals (ranked by chance of closing the gap)

### 1. The historical Polymarket book: the pmxt v2 archive of the CLOB market channel (new data source)

- **Hypothesis.** The price, the quiet trigger and the executable PnL all depend on the BTC 5m book at the decision
  instant. A full-resolution public record of that book exists for 10-09..10-30, so the frozen live price rule (93%
  within a tick) can be applied point-in-time to BUILD, VALIDATE and the exam lots h1 and h2. This is a PIT forecast of
  the touch, not the touch read from the bot's own counterparty, so it complements panel-mechanics proposal 3.
- **Why it fits.**
  - Price passes only where a book exists: 93.2% live against 53% from the tape anchor.
  - The PnL replica fails because a slow, book-less replica does not get the bot's fills.
  - The quiet trigger looks like a book or quote event (critique 1).
  - The first two exam lots predate the live recorder.
- **Test.**
  1. Retry `archive.pmxt.dev` and read `/docs/v2-data-overview` for the key layout.
  2. HEAD one development key, for example `2026-10-20T13`.
  3. Read only the Parquet footer and the needed columns (timestamps, `asset_id`, `event_type`, price, size, side,
     `best_bid`/`best_ask`, tx hash if present) through HTTP range requests (pyarrow plus fsspec HTTP). Filter to that
     hour's BTC 5m tokens, write the result to `.cache/re/btc5m-bot/pmxt/` and keep nothing raw.
  4. Validate against ground truth:
     - for every cluster taker fill of the hour, compare the archive best ask of the bought token 50 ms before the
       archive's own `last_trade_price` event of that tx, or before block - 2.2 s if the tx hash is missing;
     - cross-check one 10-31 12-18 development hour against the shared `clob_crypto` recording.
  5. If it validates:
     - compute price within a tick on 8-12 seeded VALIDATE hours;
     - run a book-replay strict-fill replica (D3) with the decoded trigger;
     - run E7 at scale: new best-ask or complementary-bid events in the 50-500 ms before quiet orders, against
       placebo.
  6. For the exams, have `evaluate()` fetch a pre-registered, seeded sample of archive hours per lot. A full 96-h lot
     is 10-40 GB, too heavy for the laptop.
  7. If the host stays down, record the failing request as `infeasible` evidence. Never use the keyed pmxt API.
- **Data.** pmxt hourly Parquet through HTTP range reads, about 100-300 MB per hour after column projection
  (estimated). Run `resources.py --need-disk` first and delete the raw data at once.
- **Signature if true.**
  - The archive best ask equals the cluster taker fill price within a tick for at least 90% of VALIDATE fills, on every
    wallet and both halves, against 53% now.
  - The book-replay replica's per-window PnL correlation rises well above 0.18.
  - Book-event features add presence gain over the prints-only baseline historically, not only live.

### 2. An unthrottled BTC 5m book recorder: is the quiet trigger a book event inside 200 ms? (strong form of E7 and A7; the data panel-mechanics proposal 1 needs)

- **Hypothesis.** The crowd, the bot included, races to lift a quote that has just become cheap: a new ask below fair
  value, a complementary bid stepping up (an implied ask), or a lost-race remainder from the other side. This happens
  within 50-300 ms, too fast for the 200-ms throttled shared recording. It is a quote event, not a print, so the
  prints-only baseline cannot see it.
- **Why it fits.**
  - The burst anatomy in critique 1: a shared instant, the bot often first, a diverse crowd, and no trade feed before
    it.
  - Before bot matches the ask fell in the last second 29% of the time (placebo 21%) and rose 60% (placebo 25%).
  - Panel-mechanics found that the quote the bot hits was often signed less than 500 ms earlier (30%).
- **Test.**
  1. Start now a recorder through `tools/live.py` `Writer`, feed `btc5m_clob_raw`. It subscribes to the market channel
     for the BTC 5m current and next windows only (4 tokens) and writes every raw `price_change` and
     `last_trade_price` message with server ms. It has no throttle, sends application-level PING, has its own
     connection (so no slow-consumer drops), a hard stop, and stays under 100 MB of RAM. Record it in `live_lab`.
  2. Run it on the coming development blocks: 11-01 06-12, then 11-01 18:00 - 11-02 06:00, which includes weekday
     hours. It also files sealed-block data the examiner can use for the future exams.
  3. For each cluster taker match (tx hash) and each crowd-burst onset (two or more distinct takers on one token
     within 300 ms), classify the last book event on the bought token or its complement in [-500, 0) ms: new lower best
     ask, size added at the ask, complement bid up, bid pulled.
  4. Fit the hazard of a match 0-500 ms after each event type against matched random instants.
  5. Check that the bot's limit equals the newly appeared ask.
- **Data.** A new recorder (a few MB per hour gzipped); data-api taker tape for wallet identities; calldata for the
  maker orders' signing times.
- **Signature if true.**
  - At least 50% of quiet matches come within 300 ms of a "new cheaper ask" event on the bought outcome (placebo 15% or
    less), with a narrow lag mode.
  - The bot's limit equals that new ask in 70% or more of them.
  - Side accuracy on these orders, using "the outcome whose ask just became cheaper", is 80% or more.
  - If false, quote events on Polymarket are ruled out at ms resolution: a measured step toward the wall account.

### 3. Venues not yet aligned with the live matches: Hyperliquid, Coinbase/USD venues, Binance spot quotes, OKX/Bybit trades at match ms (strong form of A2, A3 and X11)

- **Hypothesis.** The common quiet trigger is a move on a venue that has never been put on the live match clock.
  Candidates:
  - Hyperliquid BTC and ETH perps, never tested anywhere;
  - the USD venues behind Chainlink's settlement price (Coinbase, Kraken, Bitstamp), which can move while the USDT
    venues are still;
  - Binance spot top of book;
  - OKX and Bybit trades and quotes at exchange ms.
- **Why it fits.**
  - In my check Coinbase moved before 13.1% of quiet matches with 75% agreement (placebo 9.8%, 50%), and before 7.7%
    in the last 500 ms with 79% agreement. That is small but above placebo.
  - The live analysis aligned only Binance futures BTC/ETH (trades for 265 matches, price-only quotes for 65).
  - The historical multi-venue results were at block-second resolution, blurred by the 1.3-3.2 s match-to-block spread.
  - Hyperliquid is a top BTC perp venue, and other Up/Down bot builders record it (the HF SOL dataset).
  - Panel-mechanics proposal 2 records sized top of book on Binance, Bybit and OKX. This proposal adds the venues and
    trade feeds it leaves out.
- **Test.**
  1. Now, for the whole 12:18-18:00 development block, with no recorder needed: fetch time-bounded REST trades at
     exchange ms for the following, keeping strictly inside the development block (no daily archives that span sealed
     blocks):
     - OKX `history-trades` (BTC-USDT-SWAP, ETH-USDT-SWAP, BTC-USDT);
     - Coinbase BTC-USD and ETH-USD (`start`/`end`);
     - Kraken (`since`);
     - Deribit (history API);
     - Binance spot BTC/ETH aggTrades (`startTime`/`endTime`);
     - Binance USD-M SOL/XRP/DOGE aggTrades.
  2. For every taker match and crowd-burst onset, find the earliest move of each feed in [-1500, 0) ms. Report its
     agreement with the side against placebo, the lag distribution, and which feed moves first.
  3. For the next development blocks, add a recorder (or add these to panel-mechanics' recorder):
     - Hyperliquid `wss://api.hyperliquid.xyz/ws`, `trades` and `bbo` for BTC and ETH;
     - Coinbase `ticker` (best bid/ask) for BTC-USD and ETH-USD;
     - Binance spot `bookTicker` for BTCUSDT and ETHUSDT, every update including size-only ones.
  4. As a cheap historical diagnostic, use the HF SOL dataset to measure whether Hyperliquid leads Binance at 100 ms
     for SOL.
- **Data.** Public REST endpoints (verified on this laptop for Binance spot and Coinbase), public websockets, and the
  HF SOL dataset (June-August 2026, before every sealed period).
- **Signature if true.**
  - One feed (or a USD-venue composite) moves before at least 50% of quiet matches and crowd onsets, agrees 75% or
    more, and shows a narrow lag mode.
  - Adding it lifts live quiet-match side accuracy from about 64% to 75% or more.
  - For the exam lots, the feed has a historical archive (OKX and Bybit do; Hyperliquid would need a live-only rule for
    the future blocks).

### 4. Inverse-fit the bot's own fair value from its side choices (strong form of H4, B3 and E6), with a streaming Chainlink record

- **Hypothesis.** The bot fires when the ask of an outcome falls below its own fair value by more than the fee. That
  fair value is built on the settlement feed's level (Chainlink BTC/USD against the TWAP-60 strike, with a basis to
  the fast venues) and uses a vol, and perhaps tails, different from the market's. That would explain:
  - quiet orders, where the level is stale even though nothing moved in the last second;
  - the anti-favourite tilt in quiet seconds, from a higher-vol fair value (critique 5);
  - the activity rising through the window, as gamma and theta grow.

  H4 and the live `fv_minus_ask` were tested only with fair values off by 5-15 c.
- **Why it fits.** See critique points 4 and 5. Quiet taker volume earns +0.63 c/share gross (iteration 2), a small
  but systematic edge that needs a reference level, not a move.
- **Test.**
  1. On BUILD quiet one-sided seconds, fit a fair-value family by maximum likelihood of the chosen side, with
     edge_o = FV_o - ask_o - 0.07 p (1 - p). The family:
     - strike: Chainlink TWAP-60 `priceToBeat` (usable from the window start) or a Binance TWAP;
     - level: Binance futures mid plus a rolling Chainlink basis;
     - vol: k times realized vol at 1 s, 10 s or 1 min, or implied from the market mid at the open;
     - tails: Student-t with nu degrees of freedom.
  2. First require calibration: median |FV - mid| of 1.5 c or less at random instants.
  3. Validate on VALIDATE quiet seconds:
     - side accuracy of sign(edge_Up - edge_Down);
     - hazard of a cluster fill against the edge;
     - whether the fitted k differs from the market-implied k.
  4. Live: repeat with the exact recorded asks. Add a small RTDS recorder that sends an application-level `PING`
     every 5 s and keeps the streaming `crypto_prices_chainlink` updates with their arrival ms. That makes it possible
     to measure when each Chainlink value becomes usable, which the snapshot-only shared record cannot show.
- **Data.** Existing cells (Binance 1 s, venues, tape asks), Gamma `priceToBeat` used PIT, the live book, and a new RTDS
  streaming recorder (a few kB per minute).
- **Signature if true.**
  - A calibrated fair-value family whose edge sign predicts the quiet-second side at 75% or more (against about 64% now
    and 41% for the favourite).
  - A hazard step near edge = fee minus rebate.
  - A fitted vol or tail parameter above the market's, which accounts for the underdog tilt.
  - If false: with a calibrated fair value, quiet orders show no edge, which supports the rebate-volume or crowd-joining
    explanations with a measured null.

### 5. Recover decision times historically: calibrate a match-time estimator on the live block, and use co-racers' signing ms as trigger stamps (strong form of X12)

- **Hypothesis.** The historical lead-lag tests failed to find the quiet trigger partly because the decision instant is
  known only to within ±1 s (match to block 1.28-3.25 s). The cluster's own orders are pre-signed. But many co-racers
  sign at submission, so their order timestamps in the same txs and neighbouring blocks mark the shared trigger
  instant at ms resolution over 14 days of history, where the live lab has only hours.
- **Why it fits.**
  - Races are shared and tight (critique 1).
  - Other traders' taker orders are signed a median 3.1 s before the block, against 72 s for the cluster.
  - `tx_index` orders matches only 73% of the time, and relayer nonces not at all (panel-mechanics point 7).
- **Test.**
  1. For one live development hour, fetch calldata for every BTC 5m `matchOrders` tx (not only the cluster's).
  2. Fit match_ms from (block ts, tx_index, max signing ms of non-ladder taker orders in the tx and its neighbours).
     Measure the error against the recorded server-ms match times.
  3. If the error is 200 ms or less for most txs, apply the estimator to the 11 sampled historical hours (extend them).
     Then redo the multi-venue and ETH event study in 100-ms bins, aligned on the estimated race start rather than the
     block second.
- **Data.** Polygon RPC calldata (`calldata.py`, batched), the live `clob_crypto` match times (development only), and the
  archived venue series in `.cache/re/btc5m-bot/venues/`.
- **Signature if true.**
  - Estimated match times fall within 200 ms of the truth for at least 70% of txs.
  - Historical venue agreement peaks sharpen to the live values (for example ETH [-500, -250) ms at 85% or more).
  - The no-move residual (18.7% of one-sided seconds, about 64% side) shrinks once the lag is right.
  - Or, if no archived feed leads the co-racers' stamps, that is the quantitative "faster than every archived feed"
    measurement the wall needs.

## Sources consulted for the archive question

- pmxt v2 archive docs (unreachable from the laptop at check time): https://archive.pmxt.dev/docs/v2-data-overview
- pmxt archive index: https://archive.pmxt.dev/
- pmxt fetchOrderBook API docs (historical `since`/`until`, needs a key): https://www.pmxt.dev/docs/api-reference/fetch-order-book.md
- Hugging Face, 5-minute Polymarket snapshots: https://huggingface.co/datasets/trentmkelly/polymarket_historical_data
- Hugging Face, SOL Up/Down with Hyperliquid and Binance books: https://huggingface.co/datasets/whodisidk/polymarket-sol-updown-exchange-data
