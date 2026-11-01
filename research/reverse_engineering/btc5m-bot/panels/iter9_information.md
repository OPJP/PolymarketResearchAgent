# Panel, iteration 9: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most
sharply separate the leading explanations; how to fetch that data on this laptop.

## Data used for my checks

Development data only. The current block (10-31 18-24) is sealed, so I ran no live probe.

- The 10-31 12-18 block, read through `live_lab.recs` / `iter_live` (dev only): `btc5m_clob_raw2`, `btc5m_venues2`, and
  `btc5m_rtds_stream2`. Every script asserts each 30-s step is development and drops sealed windows.
  - Interval A = 14:55-16:04 and interval C = 16:33-17:55, as in `stale9`.
- This strategy's own intermediates: `it9/cd9.parquet` (calldata of the cluster's txs), `it9/own_1231_12_18.parquet` and
  `it9/ins9b_M.parquet`.
- Polymarket metadata for one VALIDATE window, `btc-updown-5m-1792700100` (10-21, before H):
  - Gamma (`closed=true`), listing fields only;
  - `GET https://clob.polymarket.com/clob-markets/{condition_id}` (HTTP 200).

  The files were deleted after printing.
- Public documentation:
  - `docs.polymarket.com/changelog`;
  - the order-lifecycle page (English and Chinese);
  - the PolyBolt AsyncAPI contract, `https://ws-live-v2.polymarket.com/asyncapi.json` (HTTP 200, 63 KB).
- **Disclosure.** A repository-wide grep for "taker delay" printed three lines from another strategy's `NOTES.md`. They
  were about the esports `secondsDelay` field. I did not use them. Every fact about the delay below comes from
  Polymarket's docs and endpoint and from this strategy's own data.
- Scripts are in
  `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p9i\`:
  `delay.py`, `gap.py`, `evlock.py` and `evlock2.py` (with JSON outputs). Each ran in under 300 MB and under 2 minutes.

## Critique

### 1. The investigation never modelled Polymarket's taker delay. The BTC 5m markets have one.

**What Polymarket publishes:**

- The CLOB market record of a VALIDATE BTC 5m window carries `"itode": true`. The order-lifecycle docs name this as the
  flag for the "taker delay used on selected crypto and finance up/down markets".
- A marketable order is held. Validation then runs again, and the order is matched or placed on the book (status
  `unmatched`). During the delay the order is pending and cannot be cancelled. If balance, allowance or risk checks fail
  when the delay expires, the order is rejected.
- The changelog dates the delay:
  - 250 ms until 2026-08-17 11:00 UTC;
  - 50 ms until 2026-09-04 14:00 UTC;
  - 150 ms since then.

  (The English lifecycle page still says 250 ms. Secondary reports add a 500-ms delay removed in February 2026 and a
  "locked" 250-ms window from 06-05.)
- Iteration 7's changelog read covered only 09-15..10-31, so it missed the 08-07, 08-14, 08-17 and 09-04 entries.

**What the data show (`delay.py`):**

- Sample: 2,456 taker orders of other wallets, freshly signed, in txs where a cluster wallet was the maker (10-31
  14:13-17:55). Match ms (raw2, by tx hash) minus signing ms has a hard floor at 180-190 ms:
  - 8 orders in all fall between 0 and 179 ms;
  - 63 are negative (signer clock skew);
  - the 10-ms bins hold 14 orders at 180 ms, 68 at 190, 48 at 200 and 59 at 210.
- Several independent fast wallets have their minimum at 186-199 ms (0xdc3f4623, 0x1b44945f, 0xe29042f5, 0x26d76c9b,
  0xb755a02e). That points to a common hold of about 150 ms plus 30-40 ms of signing and posting. It is not one
  wallet's clock.

**What this changes in the current account:**

- **The decision instant is the arrival a ≈ m − 150 ms, not m − 50..150.**
  - FINAL_RULE §3 says "the Polymarket leg is fast ... so the lag is upstream". That misreads the evidence. The limit
    equals the ask at m − 50..200 because the ask the bot saw before arrival usually survives the hold.
  - With the kernel peak at m − 300..−250, the bot arrives about 100-150 ms after the Binance exchange stamp, so its own
    processing is small.
- **Point-in-time leaks in the live components.**
  - The frozen live side vote reads [m − 600, m − 100). The live price anchor `PRE_MATCH_MS` reads the ask at m − 50.
  - Both run 50-100 ms past the decision. That is not the bot's own effect (it does not move Binance), but it is
    information the bot could not have. An examiner applying "features at the decision time" can reject it.
  - The lag profile (P(limit == ask(m − L)) = 74.9 / 73.7 / 70.8% at L = 50 / 100 / 200 ms) suggests the fix is cheap.
    It has not been measured.
- **"One in-flight order per wallet" is the delay lock** (`gap.py`).
  - DS's 952 taker matches are never closer than 240 ms, except 5 pairs at 123-184 ms. 240 ms ≈ D + a round trip of
    about 90 ms, so the bot waits for each delayed order's result.
  - flag9's busy test used "a cluster match in [t − 300, t)". That window catches wallets that are already free and
    misses the ones that are pending at t (matches in (t, t + 150]).
- **Lost races happen in the delay queue.**
  - who9: the trade that took the targeted ask came a median 139 ms (other takers) or 58 ms (the operator's own earlier
    legs) before the cluster's insertion. With a 150-ms hold, at least half of the lost races had the ask taken during
    the cluster's own hold. They are later places in a FIFO queue or maker cancels during the hold, not stale views.
  - The fan-out (DS, then GF 69 ms later, then XM 15 ms after that) is the bot buying several places in that queue.
- **Pay-up has a natural reading under the delay.** A limit 1 c above the touch covers an earlier queued order lifting
  the touch during the hold.

### 2. The selection is measured against a label that misses the decisions most likely to be "skipped".

- The decision label in flag9, select9 and stale9 is "taker match or located maker-first lost race". A lost race is
  only located if it later got a maker fill.
- Unfilled `unmatched` placements are about 0.45 per filled order, about 31% of all decisions by ins9b's own estimate.
  They are labelled 0.
- They concentrate exactly in the class flag9 calls "skipped, another taker bought o" (80%).
- So the AUC of 0.58 and the ~23% take rate both understate what the bot does at flagged instants.
- The recordings can show these placements:
  - they appear on o's bid at the old ask at a + D;
  - they carry the day's sizes;
  - they rest 1-10 s, against the crowd's median cancel life of 70 ms (pianon9);
  - they follow the fan-out offsets.

### 3. Event-locked, the selection is not a threshold on the venue move (`evlock2.py`).

**Setup:**

- Events: Binance USD-M BTC microprice moves of at least θ bp over 150 ms (exchange ms), with a 600-ms refractory per
  sign. The outcome o is the side the move favours.
- Kept: o's ask in 0.12-0.88, and no cluster decision on the window in [τ − 600, τ + 150).
- Label: a cluster decision on o in [τ + 100, τ + 700).

**Results:**

| interval | θ = 0.1 bp | θ = 0.3 bp | θ = 0.5 bp | no other taker buys o within 700 ms |
|---|---|---|---|---|
| A | 30.7% (n = 140) | 29.7% (101) | 29.5% (78) | 0-4.4% (n = 19-29) |
| C | 30.4% (92) | 29.0% (76) | 25.9% (58) | 0-5.3% (n = 14-22) |

- The take rate does not rise with the size of the move.
- When no other taker responds, the cluster almost never acts. When one does, it acts in about 38% of events.
- Two other conditions do not move the rate consistently between A and C: continuation of the move over [τ, τ + 100]
  (23.9% vs 34.6% flat on A; 37.1% vs 22.5% on C), and OKX/Bybit confirmation. Cells hold 6-65 events.
- The bot and the crowd select the same events. Whatever marks an event as actionable is shared, and the crowd's
  response is its best marker so far.
- The crowd's first BUY of o comes at q10 = 17-70 ms after τ. With D = 150, those orders arrived 80-130 ms before the
  Binance bookTicker change, so part of the crowd acts on an earlier or different signal.

### 4. PolyBolt is not the trigger, but it holds a public feed nobody records.

- The PolyBolt contract says `price.crypto` (gated) carries "about one update per second per symbol": Chainlink by default
  since 10-02, Pyth optionally. It is far too slow for a trigger that acts 100-150 ms after sub-bp microprice ticks.
- `price.polymarket` is public with no auth: a per-token best bid and ask with a producer timestamp. It is conflated
  ("latest wins") for slow clients and has a `dropped` counter.
- A TypeScript bot that follows Polymarket's current docs may read its touch here rather than on the CLOB market
  channel. The investigation has recorded only the latter.

## Proposals (ranked by the chance they close the gap)

### 1. Put the taker delay into the decision record: arrival-time decisions, point-in-time-clean windows, the full label (new; nothing in the ledger or catalog)

- **Hypothesis.** Every cluster decision is an arrival a = m − D (or a = insertion − D for an `unmatched` placement),
  with D ≈ 150 ms now.
  - The bot's information ends at a − δ, with δ the posting latency.
  - Its race is a FIFO queue in the delay buffer, plus makers' last look during D.
  - Its wallets are locked for D + RTT.

  Re-timing and completing the record should change three things: the point-in-time status of the live side and price
  components, the busy-state test, and the measured selectivity.
- **Why it fits.** Critique 1: `itode: true`, a sign→match floor of 180-190 ms across independent wallets, a per-wallet
  floor of 240 ms, competitor trades 58-139 ms before lost-race insertions. Critique 2: the label gap.
- **Test.**
  1. **Measure D and the round trip.**
     - Recompute the fresh-signed sign→match floor per hour. Use the 10-31 blocks (cd9 already holds the cluster-maker
       txs) and the VALIDATE calldata sample hours (taker orders of other wallets in txs where the cluster was maker).
     - Control: the same floor on a market without `itode` (any non-crypto market's matchOrders txs in a development
       hour). It should be about 30-50 ms.
     - Per wallet, the gap floor between consecutive taker matches gives D + RTT.
  2. **Point-in-time fix.** Pre-register before 11-01 06-12 and score there next to the frozen versions:
     - the live vote over [a − 500, a − δ), with a = m − D_hat;
     - the price as the ask at a − δ.
  3. **Busy state, own state, reported separately.** A wallet is busy at t if it has an arrival in (t − D − RTT, t].
     Redo flag9's P(decision | flagged) by the number of free wallets.
  4. **Complete the label.** Attribute unfilled `unmatched` placements from the unthrottled book. An attributed placement
     is:
     - a size increment of exactly the day's menu size on o's bid at a price that was o's ask in the 300 ms before;
     - at least 1 s of life, then removed without a trade;
     - aligned to a fan-out offset or to a venue tick 100-150 ms before (its insertion time minus D).

     Validate on remainders, as ins9 did. Then rerun flag9 and select9 with arrival-aligned windows (features up to
     t − δ, label = an arrival in [t, t + 100)).
  5. **Queue model of q.** For each cluster arrival, count the non-cluster arrivals at the same (o, price) in [a − D, a):
     their matches or placements within D before the cluster's own match. Measure P(fill | k ahead).
- **Data.**
  - The 10-31 and 11-01 development recordings (`btc5m_clob_raw2`, `btc5m_xclob`).
  - cd9 and the VALIDATE calldata sample.
  - One control-market hour of calldata.
  - The clob-markets endpoint (listing field `itode`).
- **Signature if true.**
  - The control market's floor is 30-50 ms against 180-190 ms on BTC 5m.
  - The per-wallet floor equals D + RTT for every wallet.
  - The point-in-time-clean vote stays within 1-2 points and the price stays above 90% within a tick, so the live
    components become exam-safe.
  - With the full label, P(decision | top 1%) rises from about 23% to 35% or more, and taken-vs-skipped AUC rises from
    0.58 to 0.65 or more with the same public features. Part of the "selection gap" would then be a label and clock
    artefact.
  - If neither moves, the selectivity is real and proposals 2-3 are the route.

### 2. The crowd's signing timestamps as a ms-exact decision record of the shared trigger: find what makes a tick actionable, at 10-50x the sample (strong form of X72; new data)

- **Hypothesis.** The cluster and the crowd act on the same "actionable" events (critique 3). The crowd's fresh-signed
  orders carry their exact decision time (`sign_ms`). Their arrival is about 30-40 ms after signing and their match
  about 150 ms after that.
  - Learning which venue information triggers anyone, with the crowd's far larger record, should find the input that
    separates taken from skipped events for the cluster.
  - Or it should show that the cluster's participation is a thinning, at a rate p ≈ 0.3-0.4, independent of every input.
- **Why it fits.**
  - The cluster's take rate after Binance moves is 0-5% without a crowd response and about 38% with one.
  - The rate is flat in the move size, so the actionable marker is not the bookTicker move.
  - The crowd's earliest orders precede the Binance bookTicker change by 80-130 ms.
  - select9 used microprice terms only: no venue trades, no sweep depth, no liquidations, no cross-venue lead order.
- **Test.**
  1. Fetch the calldata of every BTC 5m matchOrders tx in 10-31 14:14-17:55 and in the 11-01 06-12 development block.
     Keep decoded fields only, in memory then parquet (batched `eth_getTransactionByHash`; ins9 fetched 5,091 txs in
     2 minutes).
  2. Keep the non-operator taker orders with 180 ms ≤ match − sign ≤ 2 s as crowd decisions at `sign_ms`.
  3. Fetch Binance USD-M BTC and ETH aggTrades by time-bounded REST strictly inside development blocks (the
     `fetch_rest6.py` pattern). Add OKX, Coinbase and Hyperliquid trades and Bybit L1 from the existing feeds, plus
     `btc5m_xliq`.
  4. On a 100-ms grid, fit P(crowd decision on o in [t, t + 100)) from venue inputs only:
     - aggressive notional toward o in the last 50/100/250 ms;
     - whether the tick was trade-driven or quote-driven (a trade at the touch within 20 ms);
     - levels swept;
     - which venue moved first and by how much;
     - liquidation prints;
     - o's touch, spread and fee.

     Fit on A and score on C, then on 11-01.
  5. Freeze that crowd-trigger model. Then, among crowd-triggered events, score taken vs skipped for the cluster (decision
     label from proposal 1).
  6. The crowd is used only to discover features. The rule stays venue-only, so no co-occurrence term enters it. Report
     the Polymarket-activity baseline beside it as always.
- **Data.**
  - Polygon RPC (drpc, batched).
  - Binance `fapi/v1/aggTrades` with startTime/endTime inside development blocks, or the daily archive once published.
  - The existing development venue feeds.
- **Signature if true.**
  - A venue input reaches crowd AUC of 0.75 or more and also lifts the cluster's taken-vs-skipped AUC to 0.65 or more
    (from 0.58), replicating on 11-01.
  - Example: trade-driven ticks of at least X BTC, or a lead of at least 2 bp on the first venue.
  - The new input joins the live hazard, and its matched-volume overlap is re-measured (currently 8%).
- **If false.** The cluster's participation among crowd-triggered events is independent of every input.
  - State that as the quantified unexplained part.
  - Recompute the PnL test-retest ceiling with q' = p × q, not q. Under random thinning the true rule's replay is
    another thinning. At p ≈ 0.35, q' ≈ 0.25, which is the pooled q that pnlceil9 says is needed for r = 0.5, so
    condition 5 becomes borderline by construction.

### 3. The delay regimes and Polymarket's other dated rule changes as natural experiments on the bot's inputs (strong form of X9 / X26 and X60)

- **Hypothesis.** The bot is a race taker whose fill probability depends on D. If its selection is fill-aware (it
  submits only when the quote is likely to survive the hold), its decisions per venue event jump when D falls.
  - D fell from 250 to 50 ms at 2026-08-17 11:00 UTC and rose from 50 to 150 ms at 09-04 14:00.
  - If the rule is fixed, only the outcomes change: maker share and fill rate.
  - The other dated changes test other inputs:
    - 08-07: TWAP for both opening and settlement prices, 30-s lookback;
    - 08-14: 60-s TWAP for 5m;
    - 09-15: RTDS legacy, replaced by PolyBolt;
    - 10-02: `price.crypto` defaults to Chainlink.

    For example, a value model on the settlement TWAP should shift its late-window behaviour at 08-07/08-14. A bot that
    read RTDS streaming should break at 09-15.
- **Why it fits.**
  - The history from 06-20 (XM) and 07-19/20 (DS, GF) to 10-09 has never been examined (X9, X26 open).
  - Every one of these changes is exogenous and dated to the hour.
  - The pmxt v2 archive (server ms, tx hashes; verified in iteration 9) covers only the 250-ms regime (to 08-10), which
    gives a clean ms-level comparison with 10-31.
- **Test.**
  1. **ms level, D = 250.** On pmxt hours with the cluster active (08-01 12-13, 08-04 15-16, 08-05 13-14), with the
     Tardis free 08-01 binance-futures book_ticker for the venue side, check:
     - the per-wallet gap floor (prediction ≈ 340 ms if it is D + RTT; 240 ms if it is the bot's own loop);
     - the Binance tick → match kernel (prediction: the peak moves +100 ms, to m − 350..−450);
     - the who9 analogue (competitor trade → insertion bounded by about 250 ms).
  2. **Block level, 06-20..10-09, per day and per hour around each date.**
     - Source: the four wallets' OrderFilled logs (topic2/topic3 = wallet; verify the V1/V2 exchange addresses for
       July-September from a receipt).
     - Measures:
       - fills per window, normalized by the window's Binance 1-s realized volatility and by the crowd's taker volume
         (tapes, the polyrea data-api adapter);
       - maker share (lost races);
       - share of multi-wallet fills in the same block;
       - pair cost and PnL per share;
       - active wallets;
       - from a 2-h calldata sample per week: pay-up share, size menu and burst schedule.
     - Significance: a placebo distribution of step sizes at every other hour in the ±10 days around each date (at least
       2,000 draws with a block bootstrap).
- **Data.** pmxt `r2v2.pmxt.dev` (reduce each hour at once, run `resources.py --need-disk 5000` first), Tardis 08-01,
  Polygon logs (drpc), the data-api, Binance archives.
- **Signature if true.**
  - Steps at exactly 08-17 11:00 and 09-04 14:00 UTC.
  - At D = 50 relative to D = 150: maker share down, decisions per volatility unit up, and pay-up share and fan-out
    legs down.
  - The ms predictions in step 1 hold.
  - A jump in decisions per event at D = 50 implies a fill-aware selection (the bot models survival of the quote). The
    selection search should then include the maker's demonstrated reaction speed at the touch (did this level survive
    the last venue tick unchanged?).
  - No step at 09-15 rules out RTDS streaming as an input over the whole history.

### 4. Record the bot's other possible view of the Polymarket touch: PolyBolt's public `price.polymarket`, next to the CLOB market channel (new data source)

- **Hypothesis.** The bot reads the touch from PolyBolt's public best-bid/ask channel, or from a CLOB channel that
  conflates differently. Its view at a − δ is then what that channel showed, not what our raw CLOB recorder shows.
  - That would explain the "stale view" decisions: the 19.7% `lost_1000` class, which aimed at asks gone 150-850 ms
    before arrival, with a vote of 56% (placebo 64%).
  - It may explain part of the 25% of won races whose limit is not the ask at m − 50.
- **Why it fits.**
  - The bot follows Polymarket's own tooling (clob-client, pre-signed V2 orders).
  - PolyBolt is the documented replacement for RTDS.
  - `price.polymarket` needs no credentials, carries a producer timestamp and a `dropped` counter, and conflates
    "latest wins" for slow clients.
  - Stale-view decisions are not explained by the signing bursts. Measured: the `lost_1000` share is 14% within 8 s
    after a burst against 20.6% elsewhere, and maker-first insertions fall in post-burst windows at their time share
    (9.5% vs 8.6%).
- **Test.**
  1. Verify unauthenticated subscribe on `wss://ws-live-v2.polymarket.com/ws` (`{op: subscribe, channel:
     price.polymarket, filter: {asset_id}}`).
  2. Record it for the current and next BTC 5m tokens with the live `Writer`: a hard stop, under 100 MB of memory and
     300 MB of disk, starting at a development block boundary, logged in `live_lab`.
  3. Per touch change, measure the arrival-time difference against `btc5m_clob_raw2` (same price change, both server or
     producer stamps).
  4. Score the bot's limit against each channel's ask at a − δ. Check whether `lost_1000` decisions coincide with a
     conflation or lag episode on either channel.
- **Data.** The PolyBolt public channel (verify first), the existing raw CLOB feed, the 11-01 development blocks.
- **Signature if true.**
  - The limit equals the PolyBolt ask at a − δ in 85% or more, against 74% on the CLOB channel.
  - `lost_1000` decisions follow PolyBolt lag or `dropped` frames.
  - Then the bot's Polymarket input is identified, and the exam recorder must add the channel before the next sealed
    blocks.

## Not proposed (measured here)

- **PolyBolt `price.crypto` (Chainlink or Pyth) as the trigger.** It runs at about 1 update per second per symbol
  (documented). The trigger acts 100-150 ms after sub-bp ticks.
- **Post-tick confirmation as the selector:** the Binance move continuing over [τ, τ + 100], or OKX/Bybit moving the same
  way. The sign is inconsistent between A and C (critique 3). If anything, the cluster acts more often when the other
  venues have not moved yet (confirm = 0: 33-50% on A, 17-44% on C, small n), which proposal 2 can test with power.
- **Signing-burst blindness as the cause of stale-view decisions** (proposal 4's evidence). Not supported.

## Sources

- [Polymarket changelog](https://docs.polymarket.com/changelog): taker delay 250 → 50 ms (08-17 11:00 UTC) and 50 → 150
  ms (09-04 14:00 UTC); Chainlink TWAP changes on 08-07 and 08-14; PolyBolt from 09-15; `price.crypto` Chainlink default
  on 10-02.
- [Order lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md) and its
  [Chinese version](https://docs.polymarket.com/cn/concepts/order-lifecycle.md): taker delay, `itode`, the `delayed` and
  `unmatched` statuses, no cancel during the delay.
- [PolyBolt AsyncAPI contract](https://ws-live-v2.polymarket.com/asyncapi.json): `price.polymarket` is public, and
  `price.crypto` runs at about 1 Hz.
- Secondary reports on the delay's history (not relied on for dates):
  [Protos](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/) and
  [DEV Community](https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5).
