# Panel, iteration 8: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most
sharply separate the leading explanations; how to fetch that data on this laptop.

## Data used for my checks

Development data only:

- the 10-31 12-18 block, 13:55-17:55 UTC, through `live_lab.recs` / `iter_live`. Every script asserts each 30-s step is
  development, and no live probe was run: the current block, 18-24, is sealed;
- the `post/own_*.parquet` cluster fills;
- 30 Polygon blocks of 10-31 15:00-17:50, fetched in memory (decoded fields only);
- Binance USD-M REST aggTrades for SOL, XRP, DOGE and BNB perps, 16:03-17:56. Each request was a 1-minute window that
  was asserted to be development before it was sent. The files are in the scratchpad;
- Gamma `closed=true` listings and the pmxt archive for 2026-08-01, 2026-07-25 and 1-byte probes of other summer hours,
  all long before H. Only parquet footers plus three row groups' small columns were read, and only counts were kept;
- data-api activity counts for three summer hours;
- 1-byte probes of Tardis free samples for 07-01 and 08-01.

Nothing raw was stored, no sealed unit was touched, and no other agent's feeds were read.

The scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p8\`:
`phase.py`, `fetch_alts.py`, `alts_weak.py`, `pmxt_schema.py`, `pmxt_btc.py`, `pmxt_cost.py`, `blockorder.py` and
`anchors.py`.

## Critique

1. **The only ms-resolution historical record of Polymarket's book was written off against the wrong host (X18).**
   - X18 is `infeasible` because `archive.pmxt.dev` timed out. That host (65.109.107.152) is still down: connection
     refused from here and from an outside fetcher.
   - The files are not served there. They are on Cloudflare R2 at
     `https://r2v2.pmxt.dev/polymarket_orderbook_YYYY-MM-DDTHH.parquet`, which answers HTTP 206 without a key.
   - Coverage runs from 2026-04-13 to 2026-08-10 00 UTC. 08-10T06 returns 404, and every October hour I tried returns
     404, so the archive covers neither VALIDATE nor h1/h2.
   - It does cover the cluster's first seven weeks: XM from 06-20, DS and GF from 07-19/20, W4 from 07-24.
   - The schema, from the footer of 07-25T12 (430 MB, 74.3 M rows), is:
     - `timestamp` (server ms) and `timestamp_received`;
     - `market`, `event_type` and `asset_id`;
     - `bids` and `asks`;
     - `price`, `size` and `side`;
     - `best_bid` and `best_ask`;
     - `fee_rate_bps`;
     - **`transaction_hash`**;
     - the old and new tick sizes.
   - 2026-08-01T12 has 82.7 M rows in 79 row groups, sorted by market, so the row-group min/max of `market` points to the
     14 groups that hold the BTC 5m condition ids. In group 5 alone there are 179,603 BTC 5m rows:
     - 174,848 `price_change`;
     - 1,546 `last_trade_price`, all with a tx hash;
     - 3,209 `book`.

     The receive time trails the server time by 131-154 ms (median).
   - The cluster was trading:
     - 08-01 12-13 UTC: XM 168, DS 16, GF 1 TRADE rows;
     - 08-04 15-16 UTC: XM at least 500 (the cap), DS 227, GF 75;
     - 08-05 13-14 UTC: XM at least 464, DS 80, GF 27.
   - The study's whole decision-level evidence is about 3,000 live matches from one Saturday. An archive with server-ms
     match times for the cluster's taker fills on weekdays, in every hour, has been reachable all along.
2. **The h1/h2 clock was declared unrecoverable after global fits only. Inside a block it is not.**
   - X12, X22 and X40 fitted the lag on `tx_index` across all blocks (27.5% within 200 ms against 26.5% for a constant),
     and used co-racers' signing ms directly. Neither handles the real unknown, which is each block's batch offset.
   - On 4,449 cluster txs (10-31 14:00-17:55):
     - the within-block Spearman between log index and match ms has a median of 0.80 over 529 blocks with at least 3
       cluster txs;
     - match ms within one block spread over a median of 775 ms;
     - interpolating each tx between the other cluster txs of its block (oracle anchors) gives |error| < 200 ms for
       54.9% (median 159 ms), against 24.5% for the constant lag.
   - Realistic anchors exist. In 30 sampled blocks there are a median 52.5 matchOrders txs per block, and 76.5% of the
     non-cluster taker orders were signed within 4 s before the block.
     - Of 943 labelled crypto-market txs, match minus signing time is 200 / 232 / 334 ms at p10 / p25 / p50 (p75 1.2 s).
       Most other bots sign just before they post.
     - Naive interpolation over every such anchor (fixed 276 ms latency, no signer selection) puts 38.9% of 95 cluster
       txs within 200 ms (median 267 ms), against 25.3% (median 488 ms) for the constant lag.
   - That is already the best historical clock in the study, before any per-signer calibration. The 11-25 point side
     loss at the block clock (X38) is largely a per-block offset problem with abundant anchors, not a data wall.
3. **The "decision overlap" limit is read as missing information, but nobody has measured who won the races.**
   - The frozen hazard catches 8.2% of decision instants at matched volume. P(match) peaks at 22% per 500 ms, and
     matches sit inside other traders' bursts (85% within 0.5 s of another trade).
   - Bot-size insertions at the old ask are about 25 times the fills (X15), and each wallet has one in-flight order.
   - Whether the missing 92% are races the cluster lost (to about 5 known fast wallets, or to its own busy slots) or
     decisions it never made decides whether more feeds can help the PnL condition at all. The recordings and data-api
     wallet attribution can answer this. It has not been asked.
4. **The fair-value evidence is weaker than the strategy statement implies.**
   - A value-gated taker with the right FV should have the large majority of its buys below FV. The best fit reaches
     53.6% (DVOL), against 52.8% for a fixed multiple of realized vol: a 0.8-point margin, on a 30-day index.
   - The level adds 0.002-0.005 AUC and the hazard is U-shaped in the gap. Both point to a mis-specified FV object
     (wrong anchor or wrong vol), not to "levels don't matter".
   - The faded older moves (23-46%) and the underdog tilt also fit an FV anchored on a lagging Polymarket mid.
5. **Two of my checks close directions without proposals.**
   - **Alt perps on weak votes.** On 721 taker matches (16:04-17:55), the sign of SOL/XRP/DOGE/BNB perp trade-price moves
     (> 0.05 bp, Binance USD-M) is no better than placebo:

     | votes | n | [m-600, m-100) | [m-1500, m-100) | placebo (600 / 1,500 ms) |
     |---|---|---|---|---|
     | no vote | 121 | 55.6% | 50.0% | 53.2% / 51.0% |
     | weak | 293 | 49.4% | 53.5% | 50.0% / 49.2% |
     | strong | 307 | 67.0% | 65.2% | 45.6% / 46.3% |

     On strong votes, alts move with BTC and ETH (they agree with the vote 79% at placebo times). The historical
     alt-factor signal (iteration 4) is not the weak-vote input at ms.
   - **No periodic aggregated feed.** Cluster match ms are not phase-locked to any period from 50 to 1,000 ms: Rayleigh
     R ≤ 0.046 for n = 1,581, against a null of about 0.025. The ~56k other matches show a 200/500-ms rhythm (R 0.017 /
     0.016, null 0.004), so the bot is not keyed to a periodic aggregator tick such as Pyth's 400-ms slots, a
     Chainlink report cadence or a polled REST loop.

## Proposals (ranked by the chance they close the gap)

### 1. A per-block historical match clock from fresh-signed anchors (strong form of X12 / X22 / X40; the h1 exam's side and presence)

- **Hypothesis.** The tx order inside a Polygon block follows the matching engine. Other takers' orders, signed about
  200-330 ms before their own match, pin each block's batch offset. The cluster's match ms can then be recovered for most
  historical decisions, and the live decision-level side (85% per decision, 90-97% on strong votes) becomes partly
  available on h1/h2 instead of the block-clock 72.7%.
- **Why it fits.** Critique 2:
  - within-block rank correlation 0.80;
  - oracle-anchor ceiling 54.9% within 200 ms;
  - naive fresh anchors 38.9%, against 25.3% for a constant and 27.5% for the old tx_index fit.

  Trade archives at exchange ms exist for every historical day. Live, the trade-feed vote alone gave 86.5% on the 50%
  of matches where a Binance or OKX trade series moved, and the composite over 1 s gave 80.6% on 63.4%. The Bybit ob200
  archive adds an ms microprice historically.
- **Test.**
  1. Labels.
     - The 10-31 and 11-01 development blocks: `clob_crypto` and `clob_wallets` trades with tx hash and server ms.
     - pmxt summer hours (proposal 2), where every Polymarket tx in a block has a label.
     - Learn per-signer latency (match minus signing ms) and keep as anchors only signers with a tight latency (IQR
       < 100 ms on labels).
  2. Model per block: a robust (Huber) fit of match ms against within-block position, using the anchors'
     signing ms + signer latency. As an alternative, a small LightGBM on position rank, the nearest anchors before and
     after, the number of Polymarket txs, block interval and fill count. Select on 10-31 labels and test on 11-01 06-12
     labels.
  3. Apply it to the VALIDATE sampled calldata hours. Each cluster block needs only the matchOrders txs around the
     cluster's position: OrderFilled logs give hashes and positions, then batched `eth_getTransactionByHash` for about
     10-20 neighbours, roughly 2.7 KB each.
  4. Re-score the side by clock-error class:
     - a trade-feed vote (Binance USD-M and spot, OKX) plus the Bybit ob200 microprice, at the estimated m over
       [m-600, m-100);
     - the decision-level hazard at the estimated m.

     Compare both with the block-clock models on the same orders.
- **Data.** Polygon RPC (drpc or publicnode, batched); the Binance, OKX and Bybit archives already on disk for VALIDATE.
  - Cost for an exam lot: about 1,000 cluster blocks per hour times 15 neighbours is about 15k tx fetches per hour.
  - So `final_rule` must budget a seeded window sample for the side metric, or about 1.4 M fetches for 96 h.
  - Decide this before freezing.
- **Signature if true.**
  - At least 60% of held-out cluster taker txs within 200 ms of the true match.
  - The VALIDATE side, re-scored at the estimated m, rises by at least 5 points over 72.7% for every wallet, and most
    on strong-trade-move decisions.
  - A decision-level presence gain appears historically.
- **If false.** Anchor latencies are too heterogeneous. The h1/h2 clock wall is then quantified by the oracle-anchor
  ceiling (55%) and the achieved share.

### 2. A historical live lab: the pmxt v2 archive (server-ms book and trades, 2026-04-13 to 08-10) plus the Tardis free days 07-01 and 08-01 (strong form of X18 and X37)

- **Hypothesis.** The weak/no-vote residual (31-45% of live decisions, measured on one Saturday) is either:
  - a specific unrecorded series, which a day with every venue tick by tick will show; or
  - a stable non-tick component, which ~10^5 historical decisions across weekdays and hours will quantify.

  Either way the decision-level side, hazard and size rules get a large out-of-sample test outside the Saturday regime.
- **Why it fits.**
  - Critique 1: the data exist, are free and have tx hashes for joining to on-chain fills.
  - The Tardis free samples for **2026-08-01** (Saturday, all three wallets and W4 active) and **2026-07-01** (Wednesday,
    XM only) answer 206 for:
    - `binance-futures` book_ticker and `incremental_book_L2` BTCUSDT;
    - `bybit` book_snapshot_25 BTCUSDT;
    - `coinbase` quotes BTC-USD;
    - `binance-futures` book_ticker ETHUSDT (07-01).

    These are full 24-hour days with every venue, Binance L2 diffs and liquidations included, aligned with match ms.
    That is now, instead of waiting for the 11-01 sample and the 11-02 weekday blocks.
  - The Binance futures bookTicker archive is 404 for 2026-07-25 (206 for 2024-01-15). So outside those two days, the
    ms quotes come from the Bybit ob200 archive, and trades from the Binance, OKX, Coinbase and Deribit histories.
- **Test.**
  1. Reducer, run with `python -I`, streaming, nothing raw kept:
     - per hour, list the day's BTC 5m condition ids (Gamma `closed=true`) and keep only the row groups whose `market`
       min/max brackets one;
     - read `timestamp, asset_id, event_type, price, size, side, best_bid, best_ask, transaction_hash`. On 08-01T12
       that is 66 MB transferred per hour, against 477 MB for the file;
     - write a 1-3 MB per-hour parquet to `.cache/re/btc5m-bot/pmxt/`.
  2. Fetch on-chain cluster fills for those days (the existing `fetch_chain`) and join them by tx hash: match ms for
     every cluster taker fill, plus the touch at ms from `best_bid`/`best_ask`.
  3. On 08-01 first, with the Tardis series reduced to microprice changes:
     - rerun `kernel7`, `vote7` and the weak-vote agreement over every series: Binance USD-M, USDC-M, COIN-M, spot USDT,
       USDC and FDUSD, and the L2 queue at L2-L5; Bybit, OKX, Coinbase, Deribit, Hyperliquid, Bitget; liquidations;
     - fit a sparse logistic regression on weak/no-vote decisions on 00-12 and test it on 12-24;
     - repeat on 07-01 for XM.
  4. On weekdays 08-03 to 08-07 (then 07-20 to 07-31), with the trade vote plus the Bybit ob200 microprice at ms:
     - side by vote strength and the weak-vote share by hour and weekday;
     - the frozen decision-level hazard against a Polymarket-activity baseline;
     - P(large) against the operator's net;
     - version differences in sizes and schedule (X9/X26).
  5. Budget: about 1.6 GB transferred per day. Prioritize 08-01, 07-01, 08-03 to 08-07. Run `resources.py
     --need-disk 5000` before each day.
- **Data.** `r2v2.pmxt.dev` (no key), `datasets.tardis.dev` free days (GET with Range; HEAD returns 404), the Bybit
  `quote-saver` archive, the Binance `data.binance.vision` aggTrades, Polygon logs, Gamma.
- **Signature if true.**
  - On 08-01, one series or L2 feature agrees at least 80% on weak/no-vote decisions with at least 30% coverage, and
    replicates between halves and on 07-01. It then joins the exam recorders before the next sealed blocks.
  - If no series among all of Tardis's venues does this, the residual is not a public tick. That is the quantified
    information-wall statement for the side.
  - Separately, the 70/80/90/97% side-by-strength profile replicates on weekdays at n of 10^4 or more.

### 3. Who takes the liquidity at the instants the trigger flags: a lost race or no decision? (strong form of X36 and X15, with identities)

- **Hypothesis.** Most flagged-but-missed instants are races that the cluster lost, either to the ~5 fast co-racer
  wallets or because its own slots were busy (one in-flight order per wallet). They are not instants where it decided
  not to trade.
  - If so, the PnL and overlap gap is bounded by the race, not by a missing input.
  - Further feed hunting cannot lift the PnL condition. A race model (competitor presence, own slot state) can.
- **Why it fits.** Critique 3:
  - 85% of matches come within 0.5 s after another trade;
  - C2 found ~5 fast wallets co-occurring in the same second about 10% of the time;
  - X15 found bot-size insertions at the old ask at about 25 times the fill count;
  - the refractory period is 120-300 ms per wallet.
- **Test.** On intervals A-C of 10-31 and on 11-01 06-12:
  1. For grid points in the top 1-3% of the frozen exam-feed hazard for outcome o (and a matched set of low-hazard
     points), classify [t+100, t+600) as one of:
     - a cluster taker match on o;
     - another taker buying o at the touch or better. Identify the wallet from the tx hash (OrderFilled taker field) or
       from data-api `/trades` proxyWallet for the window;
     - o's touch moving away with no trade (a maker cancel);
     - nothing.
  2. Within 50-300 ms after another taker's win, look for a bot-size insertion at the old ask (a lost-race remainder) in
     `btc5m_clob_raw2`.
  3. Estimate P(cluster wins | race) by competitor set and by whether each cluster wallet had a match in the previous
     120-300 ms (own state, reported separately).
- **Data.** The shared recordings (`clob_crypto`, `btc5m_clob_raw2` trades with tx hash and server ms), data-api trades
  for the development windows, Polygon logs.
- **Signature if true.**
  - At top-hazard instants without a cluster match, another taker buys o in at least 50% of cases, against at most 15%
    at low-hazard points.
  - The winners concentrate in at most 10 wallets.
  - Lost-race remainders follow a share of those wins.
  - The cluster's win share falls when its slots are busy.

  Then the PnL condition is reported as race-bounded, with that number.
- **If false.** If nobody trades at flagged instants, the bot did not fire. The gate has a missing input, and proposal
  2's series search is the route.

### 4. Which reference the bot prices against: an absolute digital with implied vol, or a Polymarket-anchored value (strong form of X30, X45 and the X7 options part)

- **Hypothesis.** The bot's fair value is one of two kinds.
  - (a) An absolute digital on a venue index, with priceToBeat as the strike and an options-implied vol.
  - (b) The Polymarket mid anchored on its own lagged value plus delta × the venue change. With an anchor half-life of
    seconds, this produces the fade of older moves and the underdog tilt, because the lagging anchor overvalues the
    drifting underdog.

  So far only (a) has been scored, with inputs chosen by the investigator.
- **Why it fits.**
  - Critique 4.
  - `value6`'s gap δ·dS - dPM reached 59-68% on quiet matches.
  - Older moves are faded 23-46% of the time.
  - Pay-up rises with FV above the touch.
  - 87% of shares end paired, and 34% of gross volume falls in seconds where both outcomes are bought. The bot's
    opposite-outcome buys bracket its own FV.
- **Test.**
  1. On live development matches (ms, calldata limits), turn each pair of opposite-outcome cluster buys within 1 s into
     an interval bound: FV_up in [a_up + θ, 1 - a_down - θ], with θ fitted on BUILD, about 1 c given the pair cost
     0.979. Track the bracket midpoint path.
  2. Regress it, holding out the second half of each window and then the next interval, on:
     - (a) Φ(ln(S/K)/(σ√τ)), with K = priceToBeat, S = the Binance USD-M microprice × the open basis, and σ one of:
       DVOL, the nearest-expiry ATM IV (from history.deribit.com option trades' `iv` field, hourly), k × realized;
     - (b) EMA_h(PM mid) + δ·ΔS, for h from 0.5 to 10 s.
  3. Historically, compare the hourly revealed σ with DVOL, the 1-day IV and realized vol.
- **Data.** Development live blocks, VALIDATE calldata, `ptb.parquet`, the Deribit public history API (time-bounded,
  pre-H or development blocks only).
- **Signature if true.**
  - One family puts at least 80% of bracket midpoints within 1 c, and at least 80% of held-out buys below its FV.
  - With (b), the bot's level information is the Polymarket book itself, and the weak/no-vote side becomes
    sign(FV_b - ask) (pre-register it before 11-01 06-12).
  - With (a) and the 1-day IV tracking hourly, the implied-vol component moves from hypothesis to VALIDATE-only.
  - If neither family puts most buys below FV, the bot is not value-gated, and the side is a pure change rule plus
    noise near the rebate break-even.

## Not proposed (measured here)

- **Alt perps (SOL/XRP/DOGE/BNB) as the weak-vote input.** 49-56% on weak and no-vote decisions, against a 50-53%
  placebo (critique 5).
- **A periodic aggregator as the trigger** (Pyth slots, Chainlink report cadence, a polled REST loop). There is no phase
  lock at periods of 50-1,000 ms (critique 5). The 1-s RTDS snapshot remains the only Chainlink record, and PolyBolt needs
  credentials.
- **Other Polymarket book archives.** polyorderbooks is 1-s resolution behind an API key. Struct docs are
  password-gated. pmxt's keyed API must not be used; the free R2 files are enough.

Sources: [pmxt archive v2 overview](https://archive.pmxt.dev/docs/v2-data-overview) (host down; the data host
`r2v2.pmxt.dev` was verified directly), [pmxt archive](https://archive.pmxt.dev/),
[polyorderbooks](https://github.com/polyorderbooks).
