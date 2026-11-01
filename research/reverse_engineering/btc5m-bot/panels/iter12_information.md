# Panel, iteration 12: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

## Data used for my checks

Development data only. The current block (11-01 00-06) is sealed; nothing from it, from `.cache/live/sealed/` or from any
day at or after H was opened. My process stayed under 300 MB.

- **Investigation intermediates:**
  - `it11/large_dec.parquet` (the 2,155 live decisions of 10-31, arrival a = match - 150 ms);
  - `it11/onset_A.parquet` / `onset_C.parquet`;
  - `it10/cdall10.parquet` + `it9/cd9.parquet` (calldata), `it10/txms10.parquet` (server match ms);
  - `it9/own_1231_12_18.parquet` (operator txs), `fills.parquet`;
  - `results/kernel7_1793458200.json`.
- **Recordings through `iter_live`** (10-31 12-18 block):
  - `btc5m_clob_raw2` (unthrottled BTC 5m book, server ms);
  - `btc5m_venues2` (10 quote series plus the OKX, Hyperliquid and Coinbase trade tickers);
  - `btc5m_rtds_stream2`.
- **New public sources:**
  - Hugging Face dataset API listings (metadata only) and three dataset cards (READMEs);
  - parquet footers (schema, row-group statistics) of `Fahri-5/updown-5m-polymarket-raw` for 2026-10-20, read through
    HTTP range requests;
  - three row groups (10-20 11:26-11:32 UTC, nine columns, 5.5 MB) of the same file.

  The listings name daily files for days at or after H. I did not open, count or use any of them, and I quote no
  property of them.
- **Scripts.** Everything is in
  `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p12i\`:
  `pmkern.py`, `postarr.py`, `heldleak.py`, `batch.py`, `builder.py`, `quiet2.py`, `cbq.py`, `pmsize.py`, `onsetq.py`,
  `feedcount.py` and `feedcheck2.py`. The archive readers are in the sibling folder `p12i_scripts\`: `hfmeta.py`,
  `hfmeta_lib.py` and `hfprobe.py`. Downloaded READMEs are in `p12i\dl\`.

## Critique

### 1. The investigation's central constraint is false: a public, millisecond, historical Polymarket record exists for VALIDATE and for the exam days.

Twelve iterations have rested on one premise: "the next exam is historical, scored at the block clock, and none of the live
work can run on it". Iteration 10's information panel, critique 1, says so, and so does the strategy statement ("77% at
the block clock").

On that premise, five sub-second clocks were built and failed (X12, X22, X40, X59, X89/X108 still open). pmxt ends on 08-10.
Tardis is blocked. The live lab therefore had only one Saturday afternoon.

Hugging Face hosts several continuously updated captures of Polymarket's public market channel for the BTC 5m Up/Down
markets.

**`Fahri-5/updown-5m-polymarket-raw`** (CC0, not gated):

- Files: `polymarket/YYYY-MM-DD.parquet` and `btc/YYYY-MM-DD.parquet`, one per UTC day from 2026-10-17. VALIDATE days
  10-17 to 10-22 are 6 of the 7.
- Footer of 10-20 (read with range requests only):
  - 698 row groups of about 142k rows, sorted by time;
  - columns `eventType` (book / price_change / last_trade_price), `exchangeTimestampMs` (server ms), `receivedTimestampMs`,
    `transactionHash`, `tradePrice` / `tradeSize` / `tradeSide`, `bestBid` / `bestAsk`, the changed level's price and size,
    and full book arrays.
- The `btc/` config has:
  - Binance spot BTCUSDT bookTicker (with `updateId`) and trades (exchange and receive ms);
  - Polymarket's Chainlink RTDS price (`fullAccuracyValue`, `serverTimestampMs`).

**My probe of 10-20 11:26-11:32 UTC** (three row groups, nine columns, 5.5 MB):

- 428,120 rows, of which 1,731 are trades;
- receive minus server time 18 / 20 / 56 ms (q10 / q50 / q90), so the collector is in Europe, near the engine;
- **181 of the 204 operator txs in the span carry an archive match ms** (89%; part of the rest falls in my ±10 s edge
  margin);
- block ts minus archive match ms is 1,264 / 2,048 / 2,958 ms (q05 / q50 / q95). The live lab measured 1.29-3.20 s.

So the archive yields the operator's exact match time, and the book at that instant, on VALIDATE.

**`RabbitGo777/polymarket.btc_20261020.v4.parquet`** (not gated) covers one full VALIDATE weekday (10-20) on one collector
clock (Hetzner, Finland):

- Polymarket BTC 5m and 15m CLOB events;
- Binance spot and USD-M futures top of book, depth updates and trades;
- Bybit spot and perp (depth 1 and 50);
- OKX spot and swap (400 levels);
- Coinbase L2, ticker and trades;
- Chainlink price and TWAPs, plus "the feed's exchange prices".

There is also a 1-s aggregate version.

**Other sources:**

- `polydata5/polymarket-updown-5m-ws` holds the raw market channel plus Chainlink RTDS from 08-21. Its card lists a gap from
  10-12 13:15 to 10-14 10:47. It is gated: HTTP 401 with `X-Error-Code: GatedRepo`. Access needs the user's own HF account;
  the agent must not create one.
- `mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` is a free sample (08-08..21) from a vendor (pmdata.dev) that
  collects inside AWS London at about 5 ms. It includes **Chainlink Data Streams BTC/USD reports with bid/ask**: 1.15M
  reports in 14 days, about 0.95 per second.

**What this means:** the h1 side (76.7% against 80%), the price at the decision instant, the PIT live vote / hazard and a
deterministic-race replica for condition 5 can all be built on VALIDATE. The frozen rule can fetch the same public
columns for the exam days, because the daily files are listed. This is proposal 1.

### 2. "About 90% of decisions have no sharp clock" is wrong as stated: the unlocked decisions are sharply co-timed with the fast crowd.

**Two facts about the record:**

- **Price-level changes are rare on the recorded venues** (`feedcount.py`, 10-31 14:55-17:55):
  - Binance USD-M BTCUSDT changes its best bid or ask price 0.18 times per second, against 18.4 records per second;
  - Binance spot BTC changes 0.11 per second;
  - the book jumps in steps of $0.4-8 (a 10-min sample: 284 bid changes, sum of |change| $656).
- **So most decisions have no price-level change before them** (`quiet2.py`):
  - 79.4% have no Binance USD-M BTC or ETH price change in [a - 500, a - 10);
  - 57.4% have no price change on any of the ten recorded quote series.

**The fast crowd still arrives with the operator to within tens of ms** (`quiet2.py`, `builder.py`):

- **Definitions.** The fast crowd is the iteration-12 set: non-operator taker BUYs signed 180-400 ms before the match,
  arrival = match - 150. A decision is "first" when no operator decision on the window precedes it within 1 s. The
  placebo shifts the operator decision by ±3 and ±5 s.
- **The counts:**

  | operator decisions | n | same-outcome fast-crowd arrivals per decision, per 25 ms at [-25, 0) / [0, 25) / [25, 50) ms | placebo | excess in [-25, +50) |
  |---|---|---|---|---|
  | locked (lock12 definition) | 272 | 0.143 / 0.195 / 0.125 | 0.013-0.017 | 0.42 |
  | no Binance BTC/ETH price change in 500 ms, first | 775 | 0.088 / 0.103 / 0.080 | 0.021-0.022 | 0.206 |
  | no price change on any of 10 series in 500 ms, first | 545 | 0.073 / 0.088 / 0.079 | 0.023-0.026 | 0.167 |

- **It is sharp and directional.** Outside ±75 ms the rate is at placebo. Opposite-outcome crowd arrivals in the same bins
  total 0.058, against 0.271 on the same outcome.
- **What it means.** The quiet decisions are not a coin and not a slow state. They are triggered by a sharp, directional
  event that about 20% of them share with an independent wallet arriving within 50 ms.
- **What the event is not:**
  - not a price change on any recorded venue;
  - not a Polymarket touch-price event (`pmkern.py`: the event rate before quiet first arrivals is at placebo, ratio
    about 1.0 at lags of 0-500 ms);
  - not foresight of a later venue move (`postarr.py`: Binance, OKX and Bybit move after quiet arrivals at placebo rates);
  - only rarely a Coinbase trade (`cbq.py`: the Coinbase ticker moved toward o in [a - 500, a - 20) before 8.0% of them,
    placebo 5.8%).

### 3. The Polymarket book has been read by its touch prices only. The size at the touch carries the quiet decisions.

Every Polymarket book feature in the ledger is a touch-price event: o's ask up, down or unchanged (`unch150`, gate8, X56,
lam11), "Polymarket activity" counts, and depth for the pay-up. None measures the queue at the touch.

**The touch-queue score** (`pmsize.py`): (size leaving o's best ask + size joining o's best bid) minus (joining the ask +
leaving the bid), counted as level-size changes in `btc5m_clob_raw2` with no price change.

- **Quiet first decisions, n = 775, events in [a - 50, a):**

  | touch change | decisions | placebo |
  |---|---|---|
  | o-ask size leaving | 1.49 | 0.76 |
  | o-ask size joining | 0.61 | 1.36 |
  | o-bid size joining | 2.54 | 1.42 |
  | o-bid size leaving | 0.55 | 0.77 |

- **The time course.** The score climbs from +0.36 per 20 ms at a - 200 to +1.2 at a - 20 (placebo -0.02..+0.11). It stays
  at about +1.0 for 60 ms after the arrival.
- **Decision instants against placebo instants of the same window and outcome:**
  - AUC 0.702 over [a - 50, a), 0.720 over [a - 100, a), 0.708 over [a - 200, a);
  - P(score > 0) 0.74 vs 0.38.
- **Not mostly trades.** Non-operator trades on o in [a - 100, a) add only about +0.17 per decision over placebo, so most of
  the score is makers requoting in size.
- **Strictly PIT at the onsets.** With the window ending at tau, before any labelled arrival (`onsetq.py`):
  - the score adds +0.015 (fit A, score C: 0.6805 -> 0.6951) and +0.013 (C -> A: 0.6910 -> 0.7037) to the evt10-style FULL
    logistic;
  - with a slow term over [tau - 1000, tau - 200): 0.6994 / 0.7059;
  - univariate AUC 0.59-0.60.

  The gain is the same size as the Coinbase gate's, from data that has been recorded since 10-31 14:13. I did not compute
  a block CI.
- **The exam recorders keep this input.** rec_exam7's `btc5m_xclob` keeps every Up-token price_change at the touch with its
  size, so the score can be computed on the sealed future blocks as well.

### 4. The selection is measured on the investigator's clock, not the bot's.

- **The tables are indexed on Binance.** The onset tables index Binance USD-M L1 events, and the take label is
  conditional on such an onset.
- **The majority is left out.** Critique 2 says 79% of decisions have no Binance price change in the preceding 500 ms.
  Those decisions sit inside the onset tables only through size-only DEPLETE / REFILL events, at a base rate of about 5%.
  Their trigger cannot be found by a model that only asks "which Binance onsets are taken".
- **A Polymarket-side unit is never used.** An event table built on the Polymarket touch queue, or on the crowd's arrivals,
  has not been built.

### 5. The "shared input" is held by a few dozen direct-API wallets, and a few may be siblings.

`builder.py` grouped the 13,644 fast-crowd orders (1,196 wallets):

- **Overall.** 8.1% have an operator decision on the same window and outcome within ±100 ms (placebo 2.5%).
- **By builder code:**
  - orders with no builder code: 8.6% vs 2.5% (3.5x);
  - builder-coded orders (`ece0ef60`, `4898df15`, `26185f3f`, ...): ratios of 1.1-2.3;
  - the operator's software is a direct-API client, and so are its real peers.
- **By signature type.** Type 0 (plain EOA) gives 16.5% vs 1.9%.
- **Concentration.** The top 10 wallets carry 40% of co-decisions and the top 50 carry 69%:
  - 0xdc3f4623... (265 fast orders, 34% co-decided);
  - 0x5d634050... (30%);
  - 0x26d76c9b... (29%; 18x placebo);
  - 0xeebde7a0... (26%).
- **Lags.** Their arrival lags to the operator are broad (q10 / q50 / q90 about -100 / 0 / +140 ms), so they are
  independent. One exception is 0x764fd57b0b885cbeada5a119cdf0a113ee4ec347: -24 / +1 / +15 ms, 85% within ±30 ms, but n is
  only 13. It needs the sibling test of X102 step 3.

## Proposals (ranked by the chance they close the gap)

### 1. Use the public historical Polymarket capture: score the decision-clock rule on VALIDATE and give the frozen rule the same input for h1 (new data source; supersedes X12 / X22 / X40 / X59 / X89 / X108 as the route to a historical clock)

**Hypothesis.**

- The binding h1 conditions are side (76.7% against 80%) and PnL (0.476 / 0.440 against 0.5). Both are capped by the block
  clock, not by missing information.
- With the archive's match ms and book, the live decision-level components can be computed historically on VALIDATE, and by
  the examiner on h1. Those components are the PIT microprice vote (83% live), the limit equal to o's ask 30 ms before
  arrival, and the hazard.

**Why it fits.**

- Critique 1: 89% of operator txs are matched by tx hash, with the expected 1.3-3.0 s block lag.
- iteration 7, clock7: the same vote is 79.3% at match ms and 67.8% at block ts - 2 s.
- iteration 12, race11: races are deterministic given the arrival and the book. A historical book therefore turns the PnL
  tracker into a decision-level replica.

**Test.**

1. **Ingest.**
   - Read `polymarket/2026-10-17..22.parquet` and `btc/` of the same days with HTTP range requests, row group by row group.
     `hfmeta_lib.RangeFile` with `pyarrow.ParquetFile.read_row_groups(columns=...)` works and needs no new package.
   - Keep the columns `eventType`, `exchangeTimestampMs`, `transactionHash`, `conditionId`, `outcome`, `tradePrice` /
     `tradeSize` / `tradeSide`, and touch `bestBid` / `bestAsk` / `bidPrice` / `bidSize` / `askPrice` / `askSize`.
   - Reduce at once to:
     - a per-tx match ms table;
     - per BTC 5m market, the touch series with sizes within 2 c.
   - Cost: about 1.3 GB of range requests per day at nine columns. Keep only the reduced output, a few tens of MB.
   - Pin the dataset revision (commit sha) in the code.
2. **Verify the archive against the shared recorder.** Compare it, tx by tx and touch by touch, with the 10-31 development
   hours (00-06 and 12-18) of the shared and own recorders.
   - Use row-group min/max timestamps from the footer.
   - Fetch only row groups that lie wholly inside a development block; never fetch one that overlaps 06-12 or 18-24.
   - Report coverage per hour and the server-ms agreement.
3. **Side.** On VALIDATE, score the frozen PIT vote at a = archive match - 150 ms per decision.
   - Historical series:
     - Binance spot BTC bookTicker (archive, European receive clock);
     - Binance USD-M BTC / ETH aggTrades (ms);
     - Bybit `orderbook.200` (ms archive);
     - OKX trades.
   - On 10-20, use the full RabbitGo777 venue set: Binance futures depth, Coinbase L2 and OKX 400 levels.
   - Compare with the 76.7% block-clock side model, per wallet and per half.
4. **Price.** On VALIDATE, check the limit against o's archive ask at a - 30 ms for every calldata order, against the
   calldata-touch anchor.
5. **PnL.** Build a decision-level replica on the archive book. It needs:
   - decisions from the frozen hazard / vote;
   - races resolved by queue position against the archive's next trades and cancels;
   - strict fills, latency at least 2 s for the tracker convention.

   Score its per-window PnL correlation on VALIDATE against the exposure tracker's 0.476 / 0.440. Pre-register it as a
   candidate, not a tuning target.
6. **The exam route.** `evaluate()` fetches the same archive columns for the exam period, with the block-clock rule as a
   per-tx fallback where the archive has no match. Write the fetch so that only the examiner's driver (`ALLOW_SEALED`)
   reaches days at or after H.
7. **More history if needed.** BUILD before 10-17 needs `polydata5`, which is gated. Ask the user to request access with
   their own account. Alternatively, fit the decision-clock components on the 10-31 / 11-01 development blocks and
   validate on 10-17..22.

**Data.**

- `https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw/resolve/main/{polymarket,btc}/2026-10-DD.parquet`, DD
  17-22 only (CC0).
- `https://huggingface.co/datasets/RabbitGo777/polymarket.btc_20261020.v4.parquet` (10-20, all venues; a `.1s` aggregate
  exists).
- Bybit archives and Binance aggTrades already in use.

**Signature if true.**

- On VALIDATE, the per-decision side at the archive clock is at least 80% pooled, and within 3 points per wallet with 300
  or more fills. The live 83% replicates on weekdays.
- The archive-touch price is within a tick for at least 95% of orders.
- The decision-level replica reaches PnL Pearson and Spearman of at least 0.5.
- The tx-hash match covers at least 95% of operator txs per VALIDATE day.

**If false.**

- If the side at the archive clock stays near 77%, the side loss is information (the no-vote third), not the clock. Then
  proposal 2 is the remaining route.
- If archive coverage is below about 90%, the clock is partial. Report the scope.

### 2. The Polymarket touch-queue fade as the trigger of the quiet decisions (new input; strong form of X90 and X111 step 3; not in the onset design)

**Hypothesis.**

- For the 60-80% of decisions with no venue price-level change, the bot and its peers read Polymarket's own book in size.
  Makers pull size from o's best ask and add size at o's best bid: a requote in size that precedes their price change.
- The bot takes the remaining stale ask before the level clears. Its 30-ms view of the book (lam11) makes that feasible.
- The fast crowd reads the same queue, which explains part of the co-take that FULL leaves unexplained.

**Why it fits.** Critique 3:

- the score at decision instants rises from 200 ms before the arrival, against 0 at placebo instants;
- AUC 0.70-0.72 against same-window placebo instants;
- PIT at onsets: +0.013 / +0.015 over FULL in both directions.

**Test.**

1. **The quiet-instant event unit.**
   - Every 10 ms instant of 10-31 A / C with no venue price change in the last 500 ms.
   - Label: an operator arrival on o in the next 100 ms.
   - Features: touch-queue score windows ending at the instant (0-50, 50-150, 150-500 ms), with trades separated from
     cancels by matching level decreases to `x` records within ±5 ms; touch sizes; |ask - 0.5|; rel; FULL's venue terms.
   - Fit on A, score on C, and the reverse. Compare with the same design without the queue terms, and with the
     market-activity baseline restricted to prints.
2. **The crowd label.** Is the crowd's arrival also predicted by the score at quiet instants? A shared input predicts both.
   - Use the iteration-12 X101 framework: the crowd log OR conditional on FULL + queue.
   - Pre-registered success: the conditional log OR falls from 0.82 / 0.97 to 0.5 or below.
3. **Replicate on 11-01 06-12 and 18-24.** Pre-register before 06:00: the queue window, the trade/cancel split and the
   success thresholds (AUC gain at least +0.03 at quiet instants, block CI above 0).
4. **Replicate historically** on the archive of proposal 1 for 10-17..22.
5. **The co-occurrence account.** Report the gain over the market-activity baseline both ways: with book state counted as
   market activity, and without. The examiner may count quotes as market activity, and the rule should not depend on that
   reading.

**Data.**

- Existing: `btc5m_clob_raw2`, the onset tables, cdall10.
- 11-01 development blocks: `btc5m_xclob`, `btc5m_clob_raw2`.
- VALIDATE: the archive.

**Signature if true.**

- At quiet instants, the queue terms lift out-of-sample AUC by +0.03 or more in both halves and on 11-01.
- The crowd co-take OR conditional on FULL + queue falls by half.
- The excess of crowd co-arrivals in critique 2 is concentrated in instants with a positive score.

**If false.** The score is a co-moving trace of makers reacting to the same unseen driver. The tell is that the score
keeps rising after the arrival with no lead structure. Then proposal 3 searches for that driver.

### 3. Crowd co-arrival instants as the event clock: find the input of the quiet majority by kernel, feed by feed (new instrument; strong form of X111 step 3 and X101 step 3)

**Hypothesis.** The sharp ±40-ms co-arrival of the operator and independent fast wallets (critique 2) marks the true
trigger instants. A feed that carries the trigger shows a sharp, directional kernel at a fixed lag before those instants.
The lag is the venue's London transit plus a reaction time. The kernel appears for the operator's arrivals and the crowd's
arrivals alike, and not before placebo or operator-only instants.

**Why it fits.**

- Locked decisions show the kernel on Binance (excess 0.42 crowd arrivals per decision).
- Quiet decisions keep a 3.3-4.5x co-arrival peak with no recorded price change.
- The trigger exists, so a kernel search over feeds has a target instant to within tens of ms, instead of the operator's
  diffuse onset tables.

**Test.**

1. **Events.**
   - Co-arrival instants: an operator decision with at least one fast-crowd same-outcome arrival in [-25, +50) ms. Use the
     instant's median arrival.
   - The crowd's own quiet arrivals: about 6x the operator's sample (13.6k fast orders per 3 h).
   - Controls: operator-only quiet decisions, and placebo instants.
2. **Feeds, all on exchange stamps shifted by the London transits of X87.** For each feed, the event rate and the
   direction agreement in 10-ms bins over [-500, 0):
   - Binance USD-M BTC / ETH L1 size depletion on the side toward o (btc5m_venues2 sizes);
   - Binance `depth5@100ms`, OKX `books5`, Bybit `orderbook.50` (rec_eu11 `btc5m_xsnap`, from 11-01);
   - Coinbase `level2_batch` top, Bitstamp, Kraken (`btc5m_xeu`);
   - Deribit perp quotes, Binance USDC-M, COIN-M, spot FDUSD / USDC (`btc5m_xfam`);
   - liquidations (`btc5m_xliq`);
   - Polymarket ETH / SOL 5m and BTC 15m / 4h touches (`clob_crypto`);
   - PolyBolt `price.polymarket` (rec_pb10, from 11-01 06:00);
   - for 10-20, every RabbitGo777 venue on one clock (Binance futures depth updates, Coinbase L2, OKX 400 levels, Bybit 50
     levels, Chainlink).
3. **Score each feed** by the share of the co-arrival excess it accounts for: instants with a feed event at the feed's
   peak lag, and their excess over placebo.
4. **Sibling check.** Run the sibling check for 0x764fd57b... (funding links, owner key, complementarity). If it is
   operator-owned, it belongs in the operator net, not in the crowd.

**Data.** All recorded or recording now (11-01 06-12 and 18-24 are development blocks), plus RabbitGo777 10-20.

**Signature if true.** One feed (or the Polymarket queue of proposal 2) shows a kernel peak of at least 3x placebo in a
25-ms bin at a fixed lag, with at least 75% direction agreement. It accounts for at least 50% of the quiet co-arrival
excess, for the operator and the crowd alike.

**If false.** No recorded or recordable public feed accounts for the quiet co-arrivals. The wall account can then state:
"X% of decisions are sharply co-timed (±40 ms) with N independent direct-API wallets on an input absent from every public
feed obtained". The candidates left are paid aggregators (Chainlink Data Streams direct, Pyth Lazer) or private flow. That
is a far more specific statement than "no sharp clock".

### 4. The settlement feed at report resolution and its constituent venues: does the window net follow the Chainlink-vs-Binance basis? (new data; strong form of A1 / X21 for condition 5)

**Hypothesis.**

- The operator's fair value is anchored on the settlement stream, Chainlink Data Streams (a multi-venue USD median),
  while the crowd prices off Binance USDT.
- Changes in the basis inside a window then shift the operator's net path relative to the crowd's. That would be part of
  the r 0.48 to 0.55 gap of condition 5, which slow spot-path features did not close.
- It would also explain why "previous window's outcome" (a Chainlink quantity) enters the net path while pre-open Binance
  M1 / M2 flip sign.

**Why it fits.**

- Iteration 12: the net leans with the previous window's outcome (t 3.5 / 3.8), a settlement-feed quantity.
- Binance-defined M1 / M2 and the strike gap flip sign between BUILD and VALIDATE.
- RTDS 1-s points were only tested as a 100-ms trigger (cltest, X21), never as a slow FV input for the net.

**Test.**

1. **VALIDATE (archive `btc/`).** The basis b(t) = Chainlink RTDS price minus Binance spot mid, at 1 s, per window. Regress
   the BUILD-fitted residual of the window net (wallet net minus the nf ensemble prediction) on Δb over each window minute,
   and on b at the open.
   - BUILD has no archive. Fit on 10-17..19 and score 10-20..22, pre-registered.
2. **10-20.** Recompute with RabbitGo777's Chainlink "exchange prices" (the constituents) to see which venue drives Δb.
3. **August.** On the pmxt hours of 08-08..10, which overlap the vendor sample's Data Streams reports, test whether
   unlocked decisions follow report arrivals or report bid/ask moves (a kernel, as in proposal 3).

**Data.**

- Fahri-5 `btc/` (VALIDATE days).
- RabbitGo777 `chainlink.btc_20261020.v4.parquet` (17 MB).
- `mileswangs/.../chainlink_streams/date=2026-08-0{8,9}/BTCUSD.parquet` and `date=2026-08-10` (about 4.4 MB each).

**Signature if true.**

- Δb terms raise the out-of-sample window-net correlation by +0.03 or more, with a stable sign in both VALIDATE halves.
- The tracker on the augmented target crosses 0.5 in both Pearson and Spearman.

**If false.** The net path is Binance-anchored. Δb stops being a candidate for the lean, and condition 5's remaining gap is
race outcomes (proposal 1, step 5).

### 5. Short-dated implied volatility as the scale of the buy-back (strong form of X7 for the exposure path)

**Hypothesis.** The net path buys the current minute's move and sells back against earlier minutes. That is the signature
of a fair value with a different volatility from the market's. The bot's sigma is the options market's short-dated IV,
which moves across hours and days. So the buy-back strength varies with IV / RV across windows, and a constant-sigma model
(the nf features) cannot capture it.

**Why it fits.**

- fvnet12: the earlier-minute coefficients are large but unstable in size between BUILD and VALIDATE.
- dvol8 / revpref8: the revealed vol multiplier is DVOL / RV = 1.5-2.9, a wide distribution. Only hourly DVOL was ever
  used.

**Test.**

1. **Fetch.** Deribit `public/get_volatility_index_data` (BTC, resolution 60) and
   `public/get_last_trades_by_currency_and_time` (kind option, with `iv`) for 10-09..22. From them, build the per-minute
   ATM IV of the nearest expiry.
2. **Regress.** In the fvnet12 window-minute OLS, add (earlier-minute move) x log(IV / RV_15m) and the same for the
   current minute.
3. **Model.** As a pre-registered nf feature pair, score the window-net correlation on VALIDATE.

**Data.** Deribit public REST, already verified.

**Signature if true.**

- The buy-back interaction is significant with the same sign in BUILD and VALIDATE.
- The window-net prediction gains +0.02 or more.

**If false.** Close X7's option part with the measurement.

## Checked and not supported (so nobody redoes them)

All on 10-31 14:55-17:55 unless noted.

- **Polymarket's RTDS Binance relay (`crypto_prices`, type update) does not stream to this laptop.**
  - `btc5m_rtds_stream2` holds only `subscribe` snapshots: 6 per hour, each with 1-s values. It cannot be a 100-ms
    trigger.
  - The shared recorder does not subscribe to it at all.
- **No held taker order leaks into the public book.**
  - There are no crossed books in 1.38M price_change entries.
  - Bids at or above the trade price are rarer in the 150-ms hold before a crowd match (5.7%) than at placebo (17.7%).
- **The taker delay is a per-order hold, not a batch release.**
  - Consecutive match gaps on a market show no spike at 0-2 ms (1.7% of 45,007).
  - Rayleigh n R^2 is 4.8 or less at periods of 25-1,000 ms.
  - Fresh sign-to-match q1 is 186 ms.
- **No post-arrival foresight.** For no-tick and quiet decisions, Binance, OKX and Bybit microprices move after the arrival
  at placebo rates over 0-450 ms. Hyperliquid's post-arrival excess is its known lag behind Binance.
- **Polymarket touch-price events are not the clock of quiet first decisions.** The event rate in the 500 ms before the
  arrival is at placebo (ratio about 1.0). Crowd trades on o in [a - 100, a) are 1.6x, a small excess.
- **The Coinbase ticker** moved toward o before 8.0% of quiet first decisions (placebo 5.8%; agreement 0.81). It cannot
  carry them.
- **Builder-coded and managed-bot orders are not the co-deciders.**
  - Builder-coded orders: ratios of 1.1-2.3.
  - The `polybot.managed.v1` metadata tag: 18 orders.

## Sources

- **Hugging Face dataset API**, metadata only:
  - `https://huggingface.co/api/datasets?search=polymarket&sort=lastModified`;
  - `https://huggingface.co/api/datasets/<id>/tree/main?recursive=true`;
  - `https://huggingface.co/api/datasets/<id>` (gating flags).
- **Fahri-5** (CC0, not gated):
  - `https://huggingface.co/datasets/Fahri-5/updown-5m-polymarket-raw/resolve/main/polymarket/2026-10-20.parquet` (footer
    and row groups 349-351, nine columns);
  - `.../btc/2026-10-20.parquet` (footer only).
- **RabbitGo777** (not gated): `https://huggingface.co/datasets/RabbitGo777/polymarket.btc_20261020.v4.parquet` (card
  read).
- **polydata5:** `https://huggingface.co/datasets/polydata5/polymarket-updown-5m-ws`. The card was read. Files answer HTTP
  401 with `X-Error-Code: GatedRepo`.
- **mileswangs:** `https://huggingface.co/datasets/mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` (card read;
  Chainlink Data Streams 08-08..21, from pmdata.dev).
- **Not used:**
  - commercial vendors named in that card (pmdata.dev, Telonex), which would need an account and payment (the user's
    decision);
  - anything dated at or after 2026-10-23 in any of these datasets.
