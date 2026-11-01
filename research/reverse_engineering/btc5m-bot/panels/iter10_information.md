# Panel, iteration 10: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

## Data used for my checks

Development data only. The current block (10-31 18-24) is sealed, so I ran no live market probe and read nothing from
`.cache/live/sealed/` or from other agents' feeds (`dm_*`, `dx_*`, `dy_*`).

- This strategy's intermediates: `it9/cd9.parquet`, `it10/cdall10.parquet`, `it10/txms10.parquet` and `it9/ins9b_M.parquet`.
- Development recordings through `live_lab.recs` / `iter_live`: `btc5m_venues2`, `btc5m_xfam` (10-31 17:45-18:00 only),
  `btc5m_clob_raw2`, `clob_crypto`, `subs` and `btc5m_rtds_stream2`.
- Endpoint and geography checks (no market data):
  - `https://clob.polymarket.com/cdn-cgi/trace` and `/time` (Cloudflare);
  - DNS of the Polymarket API hosts;
  - 1-byte range requests to `r2v2.pmxt.dev` for development hours only.
- Scripts are in
  `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p10i\`:
  `phase.py`, `order.py`, `sender.py`, `early.py`, `first.py`, `xcorr.py`, `kern_db.py` and `persist.py`. Each ran in under
  300 MB and a few minutes. They import the investigation's `live_lab`, `stale9`, `evt10`, `live6` and `gate8` read-only.

## Critique

### 1. The next exam is historical, and none of the live work can run on it.

- **What h1 is.** The h1 lot covers 10-23, 25, 27 and 29, before the recorder existed. The examiner will score the
  block-clock rule there:
  - side 76.7% against the 80% bar (it binds wherever a wallet is one-sided in 20% or more of its windows; XM was at 24.3%
    on VALIDATE);
  - PnL correlation 0.18 against the 0.5 bar;
  - presence passes by +0.054.
- **The live components need data h1 does not have.** The PIT vote, the PIT price and the decision hazard each need a
  millisecond match clock and venue microprice.
- **The historical sub-second clock has stalled.** X59 has been open for three iterations, and X60 can only serve the
  summer: pmxt ends on 2026-08-10 (check 8).
- **A clock alone is not enough for the side.** The live full-coverage side is itself only 75.5-79.4%. The side gap is
  the third of decisions with no BTC or ETH vote, and that is an information gap: proposals 1 and 2.

### 2. Every venue is timed on its exchange stamp, but the bot sits in Europe. The venues local to it were never analysed.

**Where Polymarket's origin is (check 10).**

- The laptop reaches Polymarket through the Cloudflare FRA edge (loc IL).
- An edge-only request takes 58 ms. A CLOB origin request (`/time`) takes 94 ms on average, minimum 76 ms.
- So the edge-to-origin leg is about 18-36 ms. That puts the origin in western Europe (London or Dublin). It is not
  us-east-1 (85-95 ms from FRA) and not Tokyo.

**Where the bot is.** It reads a very fresh Polymarket touch:

- its limit is exact on o's ask at m - 50 (78%) more often than at m - 180 (72%), and less often still at m - 250..400;
- so its view of the book is a few tens of ms old at arrival, which means it is co-located with the engine.

From there, each venue arrives with its own transit:

- Binance (Tokyo) about 105-115 ms after its stamp;
- OKX (Hong Kong) about 95-100 ms;
- Bybit (Singapore) about 85-90 ms;
- Coinbase (us-east-1) about 35-40 ms;
- an LD4-hosted venue about 1-2 ms.

**How that changes the readings.**

- The measured reaction (arrival 100-150 ms after a Binance stamp) is the Tokyo-to-London transit plus 0-40 ms of
  processing.
- The conclusion "Binance USD-M bookTicker is the primary stream" (kernel7) rests on Asian venues on exchange stamps.
- **Deribit.** It is the only European venue recorded (since 10-31 17:45), and it has never been tested against the
  cluster. Check 5, over 14 minutes:
  - Deribit's BTC perp follows big Binance moves by only +50..100 ms on the stamps (144 moves of 0.2 bp or more;
    directional excess 0.46 / 0.40);
  - it never leads.

  So a London process sees a Binance move in Deribit's book about as early as Binance's own feed can reach it, or earlier.
- **Not recorded at all:** Coinbase L1 (only trades by REST), Bitstamp, Kraken and LMAX.
- **The laptop's receive times differ by venue.** Deribit t - E is about -27..+22 ms, Binance USDC-M +78..81 ms and Bybit
  +233..249 ms. Any analysis on receive time mis-orders the venues by up to about 250 ms.

### 3. The crowd comparison used client clocks, and iteration 9's "crowd ahead of Binance" is at base rate.

**Client clocks.**

- crowd10 timed crowd decisions at `sign_ms`, the client's clock.
- Per-wallet minima of m - sign are spread widely:
  - median 213 ms over 260 wallets with 30 or more orders;
  - median minus minimum 69-152 ms (q25-q50);
  - some clocks are negative by up to 890 ms.
- A 100-ms venue model is blurred by that skew; the Polymarket-activity baseline over [t - 1000, t) is not.
- So "the crowd follows Polymarket, not the venues" (venue AUC 0.54-0.60 vs 0.63-0.66) may be a clock artefact. Re-timing
  the crowd on the server clock (arrival = match - 150) settles it.

**Base rate (check 3).**

- A crowd taker arrival on o falls in [tau - 300, tau) before 34-39% of Binance price-level events.
- The crowd's background rate is about 2.2 taker BUYs per second per outcome (47,366 in 3 h over 72 window-outcomes),
  which gives about 48% by chance.
- So the iteration-9 observation that crowd orders "arrived 80-130 ms before the Binance change" is not evidence that the
  crowd leads Binance.

### 4. The cluster acts only when the whole market acts, and the market's marker has been searched in Asian venues and BTC 5m only.

**Check 3.** Clean Binance USD-M price-level (or 0.05 bp and larger) events:

| | events | take rate | take rate with no crowd taker arrival on o in [tau - 300, tau + 600) |
|---|---|---|---|
| A | 293 | 30% | 2 / 53 |
| C | 181 | 29% | 0 / 33 |

Whatever makes an event actionable is shared with every fast participant.

**Check 4.** It is not simply "react to a visible crowd trade":

- in 38-47% of taken events the cluster's arrival precedes any visible crowd match on o;
- in 53-63% it precedes any change of o's ask.

**Never searched for this marker:**

- European venues;
- the alt perps;
- Polymarket's other crypto books;
- the identity of the maker at the touch.

### 5. The live cross-asset basket stops at ETH, although the side carries alt information and the trigger is "mostly ETH".

- **Historically**, SOL, XRP and DOGE moves agree with the side where neither BTC nor ETH moved:
  - 54.5-55.5% (z 5-7);
  - 64-71% at 2 bp or more (H29);
  - the alt composites are part of the frozen side model (H30: 73.2% -> 75.3% together with ETH).
- **Live**, every recorder covers BTC and ETH only.
- The weak and no-vote third of live decisions (side 64% to chance) was never checked against an alt tick.

### 6. All live inference rests on one Saturday afternoon.

- About 3.7 h of 10-31 (2,155 decisions) carry every live result. CME was closed and US equity hours were absent.
- Geography effects (which venue leads) depend on the session.
- The next development blocks are 11-01 06-12 and 18-24 (Sunday) and 11-02 00-06 and 12-18 (Monday, the first weekday EU/US
  overlap). Pre-register on Sunday and replicate on Monday 12-18.

## Proposals (ranked by the chance they close the gap)

### 1. Time every feed where the bot is: a London-arrival clock and the European venues never analysed (new: the clock and the venue set)

**Hypothesis.** The operator runs next to Polymarket's engine in western Europe and reads several BTC and ETH feeds. Each
arrives after its own transit, L_v. What decides is the order of arrival in London, not the order of exchange stamps.

Two consequences:

- (a) **The trigger.** It is the first London arrival of a move. That is often a European or US venue relaying a Binance
  move faster than Binance's own feed reaches London. The Binance-stamp kernel is then a proxy.
- (b) **The selection is a parity gate.** The bot acts on moves where it is not already behind the London makers and takers
  that read the same local venues. It skips the ones where o's ask was requoted or taken before its information arrived.
  This also explains why a third of races with nobody queued ahead are lost to maker requotes (queue10).

**Why it fits.**

- Critique 2: the origin is in Europe, and the bot's touch is fresh, so it is co-located with the engine.
- Its reaction to Binance equals the Tokyo-to-London transit plus a little processing.
- Deribit follows Binance by only 50-100 ms on the stamps.
- crowd10's venue-versus-Polymarket verdict used client clocks (critique 3).
- The marker the market shares (critique 4) is absent from Asian microprice in a third of the cluster's decisions.

**Test.** Run on 11-01 06-12; fit on its first half and score on its second; replicate unchanged on 11-01 18-24 and 11-02
12-18.

0. **Re-time the crowd.** Use the server clock (arrival = match - 150 ms) instead of `sign_ms`. Rerun crowd10 with the
   existing six series. If the venue model now beats the Polymarket-activity baseline, crowd10's conclusion was a clock
   artefact.
1. **Calibrate L_v and the clock offsets from the data.**
   - Use the two-sided lead-lag of 10-ms microprice changes for venue pairs: Binance-Deribit, Binance-Bybit, Binance-OKX,
     Deribit-Coinbase, Coinbase-Binance.
   - Also use the minimum stamp-to-arrival lag of the fastest crowd wallets per venue, on the server clock.
   - Fix L_v on the fitting half.
2. **Build the London-arrival clock.** Shift every venue's ticks to t_v + L_v. Refit the decision kernel (kernel7), the event
   unit (evt10) and the onset hazard (flag10b) on that clock, with each decision's first London arrival of a move toward o.
3. **Parity gate.** At Binance price-level onsets, classify each onset by two things:
   - whether a European or US venue showed the move at least 30 ms before the Binance tick's London arrival;
   - whether o's ask changed between that first arrival and the Binance arrival.

   Report P(take) by class and the taken-vs-skipped AUC.
4. **Lost races.** Compare P(lost to a requote | a local venue moved first) with the rest.

**Data.**

- Existing: `btc5m_xfam` (Deribit quotes, Binance USDC-M and COIN-M, Bybit L1; written in every block since 10-31 17:45),
  `btc5m_venues2` / `btc5m_xven`, `btc5m_clob_raw2`, and cd9 / cdall10 calldata for the crowd.
- New recorders, each started at a development block boundary through the `Writer`, with a hard stop, under 100 MB of
  memory and 300 MB of disk, and logged in `live_lab`. Verify each endpoint first:
  - Coinbase Exchange `wss://ws-feed.exchange.coinbase.com`, `ticker` and `level2_batch`, BTC-USD and ETH-USD;
  - Bitstamp `wss://ws.bitstamp.net`, `order_book_btcusd` and `live_trades_btcusd` (microtimestamps);
  - Kraken WS v2 `book`, BTC/USD.
- Exchange stamps only, never laptop receive time.

**Signature if true.**

- Deribit or Coinbase follow Binance by less than Binance's own transit to London (100 ms or less), so local relays exist.
- On the London-arrival clock the cluster's kernel is sharper (peak directional excess at least 1.5x the Binance-stamp
  kernel), with a tight 10-40 ms lag to the first arrival.
- The crowd label on the server clock reaches venue AUC 0.70 or more with London-arrival features, above the
  Polymarket-activity baseline.
- The parity gate holds: P(take | Binance first in London) is at least 2x P(take | local venue first and o's ask already
  moved). The taken-vs-skipped AUC reaches 0.75 or more, from 0.67-0.74 now.

**If false.**

- The London-clock kernels are no sharper, and Binance on its own stamps stays primary.
- Then the bot is Binance-driven from a Polymarket-proximate host, and selection is not a geography race (quantified).
- My first look leans this way, but it is under-powered: 84 cluster decisions in 10-31 17:45:30-17:55 (check 6) gave
  Deribit BTC a diffuse peak of 0.17 at a - 100, against 0.25-0.26 for Binance USD-M (a - 250 and a - 125).

### 2. The alt-perp basket at millisecond resolution: does the no-vote third follow SOL, XRP, DOGE or BNB? (strong form of H29 / H30)

**Hypothesis.**

- The trigger is a cross-asset composite. ETH already dominates it ("mostly ETH", iteration 6), and it also includes the
  large alt perps.
- The live decisions with no BTC or ETH microprice move in [m - 650, m - 180) are about 32%. Their side runs at 64% to
  chance, and they are alt ticks.
- At onsets, alt agreement raises the take probability.

**Why it fits.**

- Critique 5: historical alt agreement where neither BTC nor ETH moved (H29), and H30's place in the frozen side model.
- No alt series has ever been recorded live.
- The weak and no-vote decisions are the whole of the live full-coverage side's shortfall (75.5-79.4% against 80%).

**Test.**

1. **Record.** From the next development block: Binance USD-M bookTicker for SOLUSDT, XRPUSDT, DOGEUSDT and BNBUSDT; Bybit
   `orderbook.1`; OKX `bbo-tbt` for the same swaps. Use sized L1, coalesced to 30 ms like `btc5m_xfam`.
2. **Kernels.** Per-series kernels on the arrival clock (a = m - 150 or insertion - 150), 25-ms bins, with directional
   excess against placebo instants.
3. **Weak and no-vote decisions.** On the decisions whose six-series vote is 0 or 1: agreement of an alt vote (microprice
   moves scaled by BTC betas fitted on the first half) against placebo.
4. **Pre-registered extended vote.** The BTC/ETH vote first, the alt vote as the fallback. Write it before scoring 11-01
   18-24 and 11-02 12-18, and report the full-coverage side.
5. **Selection.** Add alt agreement to the onset hazard (flag10b). Fit on A and score on C.
6. **Historical.** Feed the Bybit `orderbook.200` archives for SOLUSDT, XRPUSDT and DOGEUSDT (100-ms buckets, as was done
   for ETH in iteration 6) into a new frozen side-model candidate on VALIDATE.

**Data.**

- Binance, Bybit and OKX public websockets, which work from this laptop (brief). Expect about 4-5 MB/h, so prune
  `bybit_ob` and `cells` first: the cache is at 1,450 MB.
- Bybit archives, streamed and reduced at once.

**Signature if true.**

- Alt kernels peak in the same 100-350 ms band as ETH.
- The alt vote agrees with 70% or more of the no-vote decisions, on at least 30% of them (placebo about 50%).
- The full-coverage live side reaches 80% or more, from 75.5%.
- The taken-vs-skipped AUC gains 0.03-0.05, and the historical side gains 0.5-1 point.

**If false.** Alt agreement sits at placebo. Then the no-vote third is not a cross-asset tick, and the "unrecorded
microprice" family for the side closes except for proposal 1's local venues.

### 3. A historical match clock from complete blocks: anchors from every Polymarket market, not only BTC 5m (strong form of X59)

**Hypothesis.** The cluster's match-engine times on h1 and h2 can be recovered to within 100-200 ms from chain data alone.

- Use every Polymarket match tx in the block as an anchor or as an ordering constraint, not just the BTC 5m ones. With that
  clock and the millisecond venue archives (Bybit `orderbook.200` BTC/ETH, Binance USD-M aggTrades), the pre-registered
  PIT vote, PIT price and decision hazard become runnable on the historical lots.
- That is the only route by which the live findings can reach the h1 and h2 exams.

**Why it fits (checks 2 and 3).**

- **BTC 5m is a small, noisy share of each block.**
  - It makes up about 5 of about 40 Polymarket txs per 2-s block. Over 10-31 14:55-17:55 that is 48,868 txs in 6,538 blocks.
  - Within a block, match times span 1.09 s at the median and 1.83 s at q90.
  - tx_index order is only partly match order: Spearman 0.79, with 30% of adjacent pairs inverted by a median 291 ms.
- **The relayer is a FIFO-like pool of exactly 2,000 EOAs.**
  - Each tx in a block comes from a different sender.
  - Successive-appearance rank correlation is 0.67-0.82.
  - Nonces advance about 3 per 294 s per sender, so about 20 txs/s globally.
  - The block builder orders by tip (Spearman(tip, index) -0.75 in blocks where the tip varies).
- **Non-delayed markets give much tighter anchors:** a 35-73 ms floor (ctl10), against 186 ms or more on BTC 5m, where only
  31 wallets (2,497 orders) are tight to within 40 ms.
- **The baseline to beat.** X59's oracle-anchor interpolation used BTC 5m only: 54.9% of txs within 200 ms, against 24.5%
  for a constant lag.

**Test.** On the 10-31 12-18 development block, with the truth taken from the recorded match ms of every BTC 5m tx.

1. **Fetch.**
   - Get V2 `OrderFilled` logs from both exchanges for all markets, in 100-block chunks.
   - Fetch the calldata for a 1-hour sample with batched `eth_getTransactionByHash`.
   - Keep only decoded fields: taker `sign_ms`, owner, token, `tx_index`, tip, sender.
2. **Fit the clock.**
   - Take each wallet's latency floor by market delay class (`itode`, in-play delay; listing fields only).
   - Fit match ms within each block isotonically on (`tx_index`, tip), constrained by the anchors m >= sign + floor_w.
   - Fit on one half of the hour and score on the other: the share of BTC 5m txs within 100 ms and within 200 ms.
3. **Rescore the side.** If 75% or more fall within 200 ms, score the frozen PIT vote and price on the VALIDATE calldata
   sample hours at m-hat, with the Bybit archive and Binance aggTrades. Report the voted and full-coverage side against
   the block clock's 76.7%.
4. **Keep the examiner's fetch small.** On a lot, restrict the fetch to blocks with cluster txs and to anchor wallets
   identified on development data, filtered by log topic. That keeps it at tens of thousands of txs, under drpc's
   100-block getLogs cap.

**Data.** Polygon RPC (drpc), the shared recordings for the truth, the Bybit archives already in `bybit_ob`, and the Binance
aggTrades archives.

**Signature if true.**

- 75% or more of BTC 5m txs land within 200 ms, and 50% or more within 100 ms.
- The VALIDATE voted side at m-hat reaches 80% or more, on 60% or more voted.
- The full-coverage side gains at least 2 points over the block clock. Its ceiling is the live full coverage unless
  proposals 1-2 explain the no-vote third.

**If false.** If 60% or fewer land within 200 ms even with all-market anchors:

- the block clock is the h1 / h2 clock, quantified as such;
- the historical side and PnL conditions are then bounded by construction, and the remaining rounds rest on the future
  blocks.

### 4. Who holds the ask: the maker's last-look speed as a fill-aware selector (Polymarket book plus calldata; new)

**Hypothesis.** Under the 150-ms hold, makers get a last look.

- The bot sees its own fills per counterparty and the book. It fires when o's ask is held by a slow maker: one that does
  not requote within 150 ms of a venue tick.
- It skips asks held by fast makers.
- The selection is then a learned, counterparty-level fill probability. No public feature of the instant shows it.

**Why it fits.**

- queue10: a third of races with nobody queued ahead are lost to requotes during the hold.
- who9: 27.9% of the asks that lost races aimed at were requoted away.
- gate8: the hazard is highest when o's ask fell while the venue ticked toward o, which is a maker quoting the wrong way.
- comp9 tested only the takers' identities. select9's touch age does not separate makers. X23 measured the age of consumed
  quotes only at taken instants.

**Test.**

1. **Link quotes to makers.** Link each insertion at o's ask in `btc5m_clob_raw2` to its maker order in cd9 / cdall10, which
   carry every BTC 5m match's maker orders with owner, size and `sign_ms`. Use ins9's validated insertion finder (92%).
2. **Rate each maker on A.** The last-look speed is P(its touch quote is cancelled or requoted within 150 ms of a venue tick
   of 0.05 bp or more toward the taker). Unlinked quotes that never fill form their own class.
3. **Score on C.** At flagged onsets, report:
   - P(take) by the touch maker's speed class, at matched tick strength;
   - the quote's age (arrival - the maker order's `sign_ms`);
   - the taken-vs-skipped AUC;
   - P(won | decision) by maker class.

**Data.** `btc5m_clob_raw2`, cd9 / cdall10 and `btc5m_venues2`, all existing. The test replicates on 11-01.

**Signature if true.**

- P(take | slow maker) is at least 2x P(take | fast maker).
- Maker class alone reaches a taken-vs-skipped AUC of 0.70 or more (select9: 0.58).
- Won races are more frequent on slow makers.

**If false.** The bot is not fill-aware, and the requote losses are the race lottery that lean10 already assumes.

### 5. Polymarket's other crypto books as the market-wide confirmation (cross-market Polymarket data; new for selection)

**Hypothesis.** The market-wide response that must be present for the cluster to act (critique 4) shows first on
Polymarket's other crypto markets: the BTC 15m, 1h and 4h windows and ETH 5m. They reprice or trade in the same direction
within 100-300 ms. The bot is already on the CLOB market channel and confirms its venue tick with that flow.

**Why it fits.**

- Check 3: with no crowd response, the cluster almost never acts.
- crowd10's Polymarket-activity baseline is BTC 5m only.
- X8 and X48 tested the 15m market for the side, never for selection.
- `clob_crypto` records those books (200-ms throttle) and every trade with its tx hash.

**Test.**

1. At flagged onsets (flag10b episodes, evt10 events), build features from `clob_crypto` over [t - 300, t):
   direction-mapped taker trades and ask changes on BTC 15m / 4h and ETH 5m, with their count and recency.
2. Fit on A and score on C: taken-vs-skipped AUC and the onset hazard.
3. Check that the cross-market events precede the cluster's arrival.
4. These are other traders' activity, so they also go into the co-occurrence baseline. They decode the mechanism, but they
   cannot count as presence gain.

**Data.** `clob_crypto` and `subs` (development blocks), and evt10 / flag10b's onset tables.

**Signature if true.** P(take | a same-direction cross-market trade within 300 ms) is at least 2x the rest, and the
taken-vs-skipped AUC reaches 0.72 or more.

**If false.** The shared response is local to BTC 5m.

## Not proposed (measured here)

- **A timer-loop or polling decision clock** (`phase.py`). The cluster's 1,375 taker matches of 10-31 14:55-17:55 show no
  phase locking:
  - Rayleigh Z is 3.0 or less at periods of 10-2,000 ms (DS 4.9 at 150 ms; XM 6.0 at 250 ms, n = 66);
  - the best of 961 periods per 30-minute chunk reaches Z 6.4-9.6, about the null maximum.

  The crowd shows weak epoch phases at 10, 200 and 500 ms (Z 12-13), which are its own pollers.
- **A 100-ms snapshot stream (depth@100ms) hiding fleeting ticks** (`persist.py`). Price-level Binance events keep 75% or
  more of their move at +500 ms in 96-98% of cases (A 281 / 293, C 178 / 181), and the take rate is the same (31% / 29%).
  Persistence does not select.
- **RTDS `crypto_prices` (Polymarket's Binance relay)** (`btc5m_rtds_stream2`). The hourly files are 2.6-2.9 KB: one 60-s
  Chainlink snapshot per connection and nothing from the `crypto_prices` subscription. It does not stream to an
  unauthenticated client, so nobody trades on it.
- **pmxt for BUILD, VALIDATE or the lots.**
  - `polymarket_orderbook_2026-08-09T23` and `2026-08-10T00` answer HTTP 206.
  - 08-10T12, 08-20T12, 09-15T12, 10-05T12, 10-20T12 and 10-31T13 answer 404 (Cloudflare not-found).
  - The archive ends on 08-10, so X60 serves the 250-ms regime only.
- **A crowd lead over Binance** (iteration 9 information critique 3): at base rate (critique 3).

## Sources

- **Cloudflare trace:** `https://clob.polymarket.com/cdn-cgi/trace` gave `colo=FRA`, `loc=IL`; latencies from 8 curl
  timings each (`time_starttransfer - time_appconnect`). `ws-subscriptions-clob.polymarket.com` resolves to CloudFront
  (`d2us0gdi1lpi01.cloudfront.net`) and `clob.polymarket.com` to Cloudflare, so the origins are not directly locatable. The
  Europe inference rests on the edge-to-origin leg alone.
- **pmxt:** range requests to `https://r2v2.pmxt.dev/polymarket_orderbook_<hour>.parquet`, development hours only.
- **Exchange and transit figures:** Polymarket's own docs (taker delay, `itode`) as cited in panels/iter9_information.md;
  inter-region transits are typical public-internet one-way figures, to be replaced by proposal 1's step 1 calibration.
