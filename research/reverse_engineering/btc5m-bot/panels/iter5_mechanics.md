# Panel, iteration 5: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used: calldata, resting orders, requotes, the counterparties' quotes,
inventory and capital limits, config versions, software fingerprints.

All my checks used development data only: VALIDATE and BUILD files already in `.cache/re/btc5m-bot/`, and the 10-31
13:00-13:23 development block through `live_lab.recs` / `iter_live`. W4's logs came from one `eth_getLogs` call over the
same block range. The scripts are in my scratchpad and were not added to the workspace. No sealed data was touched.

## Critique

1. **The bot does not follow other trades. It is a front-runner inside tight races.** The live analysis reads "85% of
   matches come within 0.5 s after another trade" as burst-following. I measured both directions, with one event per
   non-cluster tx and n = 265 taker matches.
   - Another trade on the same market came within 20 ms **after** the bot's match in 37% of cases (placebo 6.4%), and
     within 20 ms **before** it in 23% (placebo 7.2%). For 50 ms the shares are 52% after and 37% before (placebo
     13-15%).
   - The trade just before the match, when it is under 50 ms earlier, went the same way as the bot 72% of the time
     (n = 97).
   - So several takers hit the same market in the same direction within about ±20-50 ms of each other, and the bot is
     first at least as often as it is last. They share one trigger, and the bot is near the front.
   - The fourth sibling W4 cannot explain this. Its txs are 1.6% of the recorded non-cluster trade events and 3.4% of
     the trades just before a bot match (6.2% when the gap is under 50 ms).
   - Whatever this shared trigger is, a BTC/ETH futures trade comes before it only 16-25% of the time.
2. **X11 used a recorder that cannot see quote-size changes.** `code/rec_binance_fut.py` skips any bookTicker update
   whose (bid, ask) prices did not change (`if last.get(s) == key: continue`). It writes about 1.3 records/s, so
   queue depletion and changes in top-of-book imbalance are invisible. Those are the fastest public precursors of a
   price tick, and the Bybit book imbalance already added 1.2 points of side accuracy historically. Bybit and OKX quotes
   are not recorded live at all. X11 was tested in a weak form only: price changes, one venue, a Saturday, and 65
   covered matches.
3. **Nobody has decoded the counterparties' quotes.** C3 counted makers (top-10 = 25%) but never asked what kind of
   quote the bot lifts.
   - Live (cluster calldata for the 13:00 block): the best-priced maker order a bot taker order hit was signed a median
     1.42 s before the recorded match. 29.9% were signed less than 500 ms before it and 13.6% less than 250 ms before
     (5th percentile 119 ms).
   - 88% of those makers are complementary BUY orders. One maker, `0xec10d2301a2333b75d1a809f7a164a2cf2566eb9`, is 11.7%
     of the bot's taker counterparties.
   - Historically (11 sampled hours of calldata), 35.5% of the non-cluster makers hit by cluster taker orders were signed
     less than 3 s before the block, i.e. less than about 0.8 s before the match. For makers hit by other takers in the
     same txs the share is 22.3%.
   - **The bot often lifts quotes that were posted a few hundred ms earlier.** The quiet trigger may be a maker posting a
     mispriced quote, not a move on any feed.
4. **Some makers requote on a wall-clock timer, and every taker reacts to it.** These are other traders' maker orders in
   the calldata sample.
   - By second of the minute, second 0 holds 2,446 signatures against about 600-900 for the neighbouring seconds. By ms
     within the second, 0-99 ms holds 5,570 against about 3,100 for the other bins.
   - In VALIDATE cells, other traders' taker prints jump 1.26-1.39 times in the block bin just after each minute mark
     (rel 63, 123, 183, 243). The cluster jumps 1.16-1.28 times. There are smaller spikes at :30.
   - Both the rule and the baseline already see this through `rel`, so it adds no gain. What it gives is a population of
     makers whose quotes go stale on a timer: candidates for the bot's prey.
5. **H44 / A1_B3b holds only from 10-16 on. Before that the bot had a 240-s time stop.**
   - On 10-11..10-14, mid-range taker fills (price 0.25-0.75, per 3-s block bin) drop by 75-80% at block rel 243. On
     10-13 the bins read 172, 51, 33, 19; on 10-12 they read 183, 119, 33, 16.
   - From 10-16 the drop comes at block rel 273 instead (10-19: 51, then 2; 10-22: 69, then 4).
   - Late-to-early activity ratio by day (rel 246-270 vs 210-240): 0.10-0.17 on 10-12..14, 0.44-0.82 on 10-17..22.
   - So the stop is a config parameter: about 240 s, then about 270 s. It changed at a restart inside BUILD, on 10-15 or
     10-16. Every BUILD-trained model mixes the two regimes.
   - Sizes (10-12, 10-19) and XM's share of volume (10-14) also changed at restarts. The bot has a versioned config
     vector, not one fixed rule.
6. **The price condition will fail on h1/h2 even though the data to pass it exists.** The frozen rule falls back to the
   last implied ask on h1/h2 (53%). Yet every match's calldata contains the touch: the prices of the maker orders the
   bot hit.
7. **Negative results, to save the next iteration time:**
   - The operator's matchOrders txs come from about 2,000 relayer EOAs (about 20 txs each in the sample), so relayer
     nonces cannot put matches in order. Only `tx_index` inside a block and other traders' signing times can.
   - The bot's live match times show no ms-phase periodicity (Rayleigh z < 3 at periods of 50, 100, 200, 250, 500 and
     1,000 ms; n = 265). It is event-driven, not polled.
   - Taker fills show no clear dip during the signing bursts: the 3-s bins around rel 42, 172.7 and 210.5 stay within
     about 5-10% of their neighbours. Signing does not block submission.
   - Filled copies per (wallet, burst, outcome, price, size) decay smoothly (1: 8,923; 2: 1,494; 3: 348; 4: 95; 5: 16;
     6: 3; 10: 1). There is no visible per-level cap.

## Proposals (ranked by chance of closing the gap)

### 1. Prey-maker decoding: the bot lifts freshly posted quotes that lag the composite (strong form of C3 + B3 + E7)

- **Hypothesis.** A large share of the quiet orders are triggered by a Polymarket book event, not an external move. A
  maker (often a few specific makers, some on wall-clock timers) posts or requotes at a price below the bot's composite
  fair value for that outcome, and the bot lifts it within about 100-500 ms. Fast co-racers do the same, which is why
  the races are so tight. The bot's edge is the lag in those makers' quote functions.
- **Evidence.**
  - Live: the hit quote was signed a median 1.4 s before the match, and 30% were signed under 500 ms before it.
  - Historically, 35.5% of the makers hit by cluster takers were signed under 3 s before the block, against 22.3% for
    other takers.
  - One maker is 11.7% of the bot's taker counterparties.
  - There are timer makers at :00 and :30.
  - Live: the ask the bot buys rose in the last second 60% of the time (placebo 25%), consistent with makers requoting
    after a lift.
  - Races are tight on both sides of the bot's match and mostly have no BTC/ETH trade move before them.
- **Test.**
  1. Fetch full-market calldata for about 40 random VALIDATE windows: every `matchOrders` tx on those tokens, about 1.4k
     txs and about 55 batched POSTs per window. Keep only decoded fields.
  2. For the top 30 makers by fills, rebuild each maker's quote sequence: signing time, which approximates placement
     time for makers whose sign-to-first-fill gaps are not ladder-like; price; original size.
  3. Inverse-fit each maker's quote function: price against the 6-series and ETH composite fair value at its signing ms,
     time left and the TWAP strike. Estimate its lag (which delay of the composite fits best) and its staleness at each
     moment, `stale = composite_FV(t) - quote_price` in ticks.
  4. For every filled maker order, compute P(first filler is the cluster) by staleness and age.
  5. Live: repeat with `clob_crypto` book deltas. Find every new ask level or size increase on the bought outcome, or
     every complement-bid increase, and measure the hazard of a bot match within 0-500 ms by staleness, against moments
     with no insertion.
- **Data.** Polygon RPC calldata (`calldata.py`) for VALIDATE windows; the archived venue series already in
  `.cache/re/btc5m-bot/venues/`; `clob_crypto` development blocks.
- **Signature if true.**
  - Over half of the bot's quiet (no BTC/ETH move) taker orders hit a quote under 1 s old that is at least 1 tick
    stale against the composite.
  - The cluster's share of first fills on stale, fresh quotes is several times its base share.
  - Placement-to-bot-match times have a sharp mode (a fixed reaction latency).
  - On those orders, side accuracy is 80% or more when staleness is the side rule.
  - Live, staleness at the touch, a PIT feature built from the book and the reference feeds, raises the presence gain
    over a prints-only baseline.

### 2. Race anatomy on full quote streams (strong form of X11): record sized top-of-book on the fastest venues and align on the race start

- **Hypothesis.** The shared trigger of the tight races is a top-of-book event on a fast venue: queue depletion,
  imbalance flips, or touch moves on Binance futures, Bybit linear or OKX swap, for BTC or ETH. These happen without a
  trade print. The bot is among the first one or two racers to react.
- **Evidence.**
  - Other trades cluster within 20 ms on both sides of the bot's match (37% after, 23% before; placebo about 7%), and
    the trade just before goes the same way 72% of the time.
  - Only 16-25% of matches have a futures or ETH trade move in the last second.
  - The current recorder drops size-only updates.
  - The Bybit book imbalance already helps historically (+1.2 points of side accuracy).
- **Test.**
  1. Write a new development-only recorder through `tools/live.py` Writer: Binance USD-M `btcusdt@bookTicker` and
     `ethusdt@bookTicker` with every update (or the last update per 10 ms), Bybit `orderbook.1.BTCUSDT` and `ETHUSDT`
     (linear), OKX `bbo-tbt` for BTC-USDT-SWAP and ETH-USDT-SWAP, all with exchange ms. Give it a hard stop, keep it under
     100 MB of RAM and 300 MB of disk (10-ms snapshots keep it to a few MB per hour, gzipped), and record it in
     `live_lab`.
  2. Run it through the weekday development blocks: 11-02 00:00-06:00 and 12:00-18:00 UTC. 11-01 06-12 and 18-24 are
     Sunday.
  3. On Polymarket, define race clusters as two or more same-direction trades within 50 ms on one market, including the
     cluster's own, and align on the first trade.
  4. Run an event study over each feed event type (touch-size drop of at least x%, imbalance sign flip, touch move) at
     lags of 0-300 ms. Measure the hazard and the side agreement, for clusters the bot joins, clusters it misses, and
     random times.
- **Data.** New live recordings in development blocks only, plus `clob_crypto` and the cluster calldata for match
  identities.
- **Signature if true.**
  - One event type on one venue comes before 70% or more of the quiet race clusters, with a narrow lag mode (for
    example 20-80 ms).
  - Its direction agrees with the bot's side 80% or more of the time.
  - The bot joins clusters with larger events more often (a threshold).
  - Within a cluster, the bot's rank correlates with event size.
  - If it is false, top-of-book events explain no more than trades do. That is a quantitative step toward the "faster
    than every public feed" account the wall needs.

### 3. Historical price from calldata: the touch at each match is on chain (closes the h1/h2 price condition)

- **Hypothesis / point.** The decoded price rule is "limit = touch at submission, never sweep". It is a declared
  touch anchor under the brief's proviso. It can be measured on any historical lot without a book: the touch at the
  match is the price of the best maker order the taker order consumed. For lost-race remainders it is the level the
  winning competitor's tx consumed just before.
- **Evidence.**
  - The take-then-rest limit equals the taker fill price in 93%.
  - Live: the limit equals the ask 50 ms before the match in 78%, and is within one tick in 93%.
  - The frozen rule's historical fallback (last implied ask) gives 53%, a needless fail on h1/h2.
- **Test.**
  1. On the 11 sampled hours (and in `evaluate` for any period), for each cluster taker order compare its limit with
     the best-priced maker order in the same `matchOrders`. A complementary BUY at q counts as an ask at 1 - q.
  2. For pure-resting orders, fetch the non-cluster `matchOrders` txs in the previous two blocks on that condition, and
     test whether one consumed a maker level at exactly the bot's limit (same token, or the complement at 1 - limit).
  3. Report the share within one tick by role and wallet, and add `price.calldata_touch` to `final_rule.evaluate` for
     lots with no book.
- **Data.** Calldata (already decoded for the cluster's txs; neighbour txs for the remainders).
- **Signature if true.** At least 90% within one tick on VALIDATE takers, and at least 80% including the remainders, on
  every wallet and both halves. The examiner can then check the price condition on h1/h2. Say clearly that this
  measures the decoded rule and is not a PIT forecast of the touch.

### 4. Versioned config vector: the time stop moved from 240 s to 270 s inside BUILD (strong form of C4; corrects H44)

- **Hypothesis.** The bot runs a config that changes only at restarts or outages: (time stop, small/large size,
  large share per wallet, ladder price range, wallet weights, signing offsets). The presence model trained on BUILD
  learned a mixture: a 240-s stop on 10-11..14 and 270 s from 10-16. That costs late-window AUC on VALIDATE and on
  every later lot.
- **Evidence.** The mid-range taker fill cliff at block rel 243 on 10-11..14 (10-13: 172, 51, 33, 19) moves to 273 from
  10-16 (10-22: 69, then 4). The late-to-early ratio is 0.10-0.17, then 0.44-0.82. Sizes changed on 10-12 and 10-19
  (restart). XM's median spend per window fell from about 500-1,000 to about 100-190 on 10-14.
- **Test.**
  1. Build a per-window, per-wallet config vector from fills and calldata: the last match rel given a mid-range price,
     size pair, large share, min and max filled ladder price, share of cluster volume, and burst offset.
  2. Run change-point detection (PELT or binary segmentation) over the whole history (back to July, V1 included where
     the fields exist).
  3. Test whether every change point falls inside an outage gap.
  4. Refit the BUILD presence models with the decoded stop (for example `tau_stop = 270 - rel` and a hard zero after the
     stop) as an explicit rule component, not a fitted feature. Compare VALIDATE AUC and the gain on rel at or above 240
     and overall.
- **Data.** `fills.parquet` (have), the calldata sample, and history before 10-09 (V1 and V2 logs).
- **Signature if true.**
  - Parameters are piecewise constant and switch only at outages.
  - With the latest regime's stop hard-coded, presence on rel 240-270 cells rises clearly and the overall block-second
    gain grows above 0.055.
  - `evaluate` reports a regime check (for example, share of fills after the stop) so the examiner sees any new config.

### 5. Capital and fan-out policy: which wallets fire on a trigger, and is participation capped by free collateral? (strong form of B5)

- **Hypothesis.** One process routes each trigger to a subset of wallets. Participation is bounded by each wallet's free
  collateral: the CLOB rejects BUY orders beyond balance minus open orders, and capital comes back only at the
  once-per-window REDEEM. It may also follow per-wallet weights or thresholds. XM's sparse trading (one-sided in 24% of
  its windows, with a median of 2 fills in those windows) would then be a capacity or allocation effect. The brief's
  per-wallet side condition may apply to XM, so this has to be decoded.
- **Evidence.**
  - Per-window spend has soft ceilings: p99 is about 0.9 of the max on every day (10-22: XM 529/595, GF 1,383/1,550,
    DS 2,004/2,173).
  - XM's spend fell about five times on 10-14, yet the same process kept signing its ladders.
  - 82% of GF orders have a DS order within ±2 s, so most triggers are fanned out.
- **Test.**
  1. Rebuild each proxy wallet's collateral balance path from Transfer events of the collateral token (deposits,
     withdrawals, trade settlements, redemptions) on VALIDATE. Use logs or `eth_call balanceOf` at past blocks, never
     the current-state endpoints.
  2. Compute free balance per second, net of the notional of the wallet's resting remainders.
  3. Group cluster orders into trigger events (same outcome, within 1 s) and fit P(wallet participates) on its free
     balance, the composite move size and the price.
  4. Check whether XM's 10-14 drop coincides with a withdrawal.
- **Data.** Polygon logs for the collateral token on the three proxies (and W4), `fills.parquet`, and the calldata
  sample.
- **Signature if true.** Participation drops to about zero below a balance threshold, or XM participates only above a
  move threshold (then its side accuracy on its own seconds is above the pooled 76.7%). Per-window volume is capped by
  free balance, which improves the volume half of the net-position error that limits PnL correlation (oracle volume
  times model side gives 0.555).
