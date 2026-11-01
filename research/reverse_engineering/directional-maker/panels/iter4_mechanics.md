# Panel after iteration 4: mechanics and on-chain forensics

Reviewer lens: how the orders are built (calldata, salts, resting lifetimes, requote and cancel cadence, queue
position, complement and merge mechanics, inventory and exit rules). Written 2026-10-31 ~13:50 UTC. All my checks used
development data only: the released lot's first half (STUDY, 2026-10-23..26) case by case, and the live recorder's
development block 2026-10-31 13:00-14:20 UTC. I did not touch VALIDATE (10-27..30) fills or anything sealed. The check
scripts are in my scratchpad (`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`rate_onoff.py`, `salt_pairs.py`, `salt_pairs2.py`, `book_deltas.py`, `live_anchor.py`). The queue and taker checks
below are inline snippets that read `.cache/re/directional-maker/b1_all_makers_study.parquet` and
`exam/fills_holdout.parquet` with `ts < 1793059200`.

## Critique

The notebook describes the engine's outline well (one counter-salted signer, requote intensity, the clock schedule of
sizes). But the investigation has still never observed a single resting quote, and every model still uses fills as
its unit. The oracle diagnostic already says the gap is the quote state: whether its bid is at the front when takers
arrive. Specifically:

1. **There are still no decision times.** `timestamp = 0` removed B1's signing ms. The salt-based age in
   `code4/b1_age.py` is degenerate: counter anchors (the wallet's fills in all markets) are a median 39-48 s apart,
   so for 85.4% of BTC 5m orders the order's own salt is the envelope (lag = 0, age "0 s"), and the tail (2,400 s at
   the 90th percentile) is reset or ordering noise. The only age evidence left is "multi-fill orders are consumed in
   0-2 s" and the noisy neighbour-ms bound.
2. **The claim "the counter and the signing rate do not change while BTC 5m is off" (state.json selection component)
   does not hold up under a controlled comparison.** I regressed hourly envelope rates (STUDY, 267 wallet-hours) on
   log Binance-futures price changes per hour. Hours with BTC 5m on show **+0.234 log rate (se 0.047)**. With
   US-session, night and weekend controls it is **+0.107 (se 0.037)**. Night hours: off 11.6/s vs on 15.2/s at similar
   Binance activity (1,704 vs 1,874 changes per hour). So BTC 5m takes roughly 10-20% of the signed orders while it is
   on, i.e. about 1.5-3 orders/s for its few live slots, so each BTC 5m quote is re-signed about every 1-3 s. "Off"
   most likely means "not quoting", not "quoting wide". The rate is also an order budget the RE can decompose (P3).
3. **The exit component misses an explicit rule.** In STUDY the cluster has 219 BTC 5m taker fills, all BUY. 72% buy
   the outcome it holds less of. For the 157 pair-completing buys, the size equals the share imbalance exactly
   (size / gap: median 1.0, 75th percentile 1.0), at a pair cost (taker price + average cost of the held side) of
   median 1.12 (10-90%: 0.82-1.42). These are loss-locking hedges, not arbitrage, placed at a median 176 s into the
   window, and merges follow (median 65 s before the end). The bot never sells. It exits by buying the complement and
   merging. "Holds to resolution, occasional merges" is incomplete, and the rule's PnL (an expectation over maker
   fills) cannot correlate with per-window PnL in windows where this rule fires.
4. **The queue evidence points to back-of-queue fills, and the notebook has not drawn the consequence.** In STUDY
   same-price multi-maker groups (calldata `idx` order = the engine's priority order), the cluster's >= 50-share orders
   are the last filled order at their price in **56.5%** of groups, against **29.3%** under a uniform-position null. They
   are first in 13.7%. Other makers' >= 50-share orders are last in 14.9% (null 14.4%) and first in 19.0%. So the
   cluster's filled order is usually the youngest at its level, which means it is filled when a taker uses up the
   queue ahead of it. That fits P(filled | hit) being flat in edge deciles but rising with hits per bin, the deep
   levels at its fills (median 1,246 shares in the live pilot), and the adverse moves after its fills (a cleared
   level is one the price goes through). Presence is then mostly level depletion at the best bid, not its fair edge.
5. **The side component treats as a decision what may be the taker's choice.** 85-89% of its fills are mint matches,
   where a taker buys the complement. The cluster's BUY on s is its ask on the other outcome, so which side fills is
   set by the direction of taker flow. "Adds to the side it holds" may be flow persistence in trending windows. The
   decision to decode is the skew (which side it widens or pulls). The RE has not compared that statistic with other
   makers'.
6. **The exam route has changed, and the plan should use it.** Both historical lots are released. The next exams use
   the future sealed blocks, and the shared recorder covers those with books. Rules with book inputs are now
   examinable point-in-time. But the shared recorder writes top-10 snapshots at most every 200 ms per token, which
   merges single orders. I checked: in 13:00-14:20 UTC today (12 BTC 5m tokens, 16,971 records), level increments of
   exactly 62 occur 21 times vs 22 / 32 at 61 / 63, so no 62-share fingerprint is visible. Exactly 500 occurs 75 times
   (vs 1 / 0 at 498 / 502) and 250 occurs 27 times (vs 1 / 1), but other bots use those round sizes too. In the 15 s
   before 172 cluster fills, the increments at the fill level are dominated by 5, 10 and 30 shares. The quote cannot
   be read off this feed. It needs raw events (P1).

## Proposals (ranked by the chance they close the gap)

### P1. Record unaggregated book events and identify the cluster's own quotes by its size schedule (strong form of X2 / B2; new item)

- **Hypothesis.** The cluster's resting orders are single-order level changes of its schedule sizes: 500 with a
  100 second level in weekday US hours, 62/12 or 250/50 otherwise. They are posted and cancelled on both tokens of
  the window. With them, presence = P(its quote is at the best level when a level-clearing hit arrives), and price =
  its quote, both observable point-in-time and examinable on future sealed blocks.
- **Why it fits.** Calldata original sizes follow a strict clock schedule (75.7% / 65.3% of STUDY orders on schedule).
  B1 has no signing times. The oracle diagnostic puts the gap in the quote state. In the live pilot, fill = best bid
  in 11 of 15. The 200-ms snapshots hide single orders (critique item 6).
- **Test.** A small recorder (tools/live.py `Writer`, hard stop, < 100 MB memory, < 300 MB disk, filed by block) of
  every market-channel `price_change` and `last_trade_price` message for the current and next BTC 5m market, with
  server timestamps and no aggregation. Run it through the development blocks, including a weekday US session
  (2026-11-02 12:00-18:00 UTC is development). For every cluster fill in those blocks (data-api activity by tx hash,
  plus calldata of those txs for original size and limit price), find the +S event at (token, price) before the fill.
  Then classify every +S / -S event at the schedule sizes and measure:
  - post time vs Binance futures ms moves;
  - the post price relative to the best bid and the implied best ask (join, penny or improve) and to the futures
    TWAP-60 fair;
  - lifetime to cancel (-S with no trade);
  - re-sign cadence;
  - whether the Up and Down quotes move together;
  - the depth ahead of it.

  Then fit presence = P(at best) x P(hit consumes the queue ahead) from book features only.
- **Data.** Public CLOB market websocket (no auth), publicnode calldata for the live-block cluster txs, data-api
  activity, Binance futures websocket or aggTrades.
- **Signature if true.** A sharp excess of exact-S events over S +- 1. At least 70% of cluster fills preceded by a +S
  at the fill level within the order's life. -S cancels at a 1-3 s cadence (P3's budget). Then a book-feature
  presence model on development blocks at >= 0.85, gaining >= 0.05 over an activity-plus-book baseline that has no
  cluster-quote features. Price = its observed quote within a tick for > 80% of fills.

### P2. Back-of-queue: it is filled when a hit uses up its level (level-depletion mechanics; new item)

- **Hypothesis.** It joins the best bid and is usually the youngest order there, because it re-signs often and loses
  time priority each time. So it is filled only when a taker consumes the whole queue ahead of it. Presence =
  P(level-clearing hit on s), driven by depth at the best bid and large-taker arrival, not by its fair-value edge.
- **Why it fits.** Last at its price in 56.5% of shared levels vs a 29.3% null (first in 13.7%), while similar-size
  other makers are at their null (critique item 4). P(filled | hit) is flat in edge deciles and rises with hits per
  bin (0.039 -> 0.130). Fill levels are deep (median 1,246 shares). Fills are followed by adverse moves.
- **Test.**
  - (a) No new data. For every clean bid-hit print on s in STUDY, mark whether it cleared the level: the next bid
    hit on s is lower, or the calldata match fills a lower level too. Compare P(cluster in the tx | cleared) with
    P(cluster in the tx | not cleared), stratified by price and time in the window.
  - (b) Live lab. P(cluster filled | trade at the best bid) against trade size / depth at that level in the last
    snapshot at least 200 ms before.
  - (c) Point-in-time presence features: best-bid depth on s, that depth relative to recent large hits, best-bid
    age, and the number of levels within 0.02.
- **Data.** STUDY tapes and calldata already cached. Live books from the shared recorder (depth is fine at 200 ms).
- **Signature if true.** The cluster's share is close to 0 among hits that do not clear the level and many times
  higher among clearing hits. In the live lab, P(filled) steps up as size / depth approaches 1. Depth features add
  >= 0.05 AUC over activity-only on development blocks.

### P3. The salt counter as a requote-event counter: the per-market order budget and the re-sign law (strong form of B1/B2, replaces the degenerate b1_age)

- **Hypothesis.** The counter increments once per signed order in all markets. Decomposing its rate by enabled
  market and by reference events tells two cases apart:
  - the engine re-signs on every reference update or timer tick, including unchanged prices, so it loses priority
    (which supports P2);
  - it re-signs only when its target price crosses a tick.

  Either way, the decomposition gives each BTC 5m quote's age at fill.
- **Why it fits.** The rate is +11-23% higher when BTC 5m is on, after controls (critique item 2). There is also a
  hint of re-signs at an unchanged price: in the 16 STUDY matches where one wallet has two orders on the same token,
  the salts are mostly consecutive (median gap 1) and the later order is at the same price in 7 and one tick higher
  in 6. Among same-token, same-window filled pairs with salt gap <= 6 (70 pairs, mostly filled in the same second),
  the later one is at the same price in 22 and +0.01 in 30. The pattern is post-before-cancel replacement with the old
  order still live.
- **Test.**
  - Densify the counter. Fetch calldata for every cluster transaction in all markets on 2-3 STUDY days. The
    cluster's own taker orders (726 in STUDY) are tight anchors, signed ~0.1-0.3 s before their match.
  - Build C(t) per wallet at 10-60 s resolution.
  - Regress the salt increments per interval on two candidate drivers: (number of enabled markets x Binance-futures
    updates), and the sum over enabled markets and tokens of tick crossings of floor((F - h)/0.01).
  - Estimate the on/off coefficient per market type.
  - Compute the point-in-time "hypothetical quote age" (time since its fair-implied tick last changed) and test it
    as a presence feature.
- **Data.** publicnode `eth_getTransactionByHash` (about 6k other-market txs per STUDY half already decoded, so the
  extra is small), Binance futures 1-s / aggTrades (cached).
- **Signature if true.**
  - Price-change triggered: the rate tracks tick crossings (coefficient about 2 tokens x levels), and presence rises
    with quote age (older quote, further ahead in the queue).
  - Timer or event triggered: the rate tracks Binance updates whatever the crossings, and P2's back-of-queue holds.

### P4. Exit by buying the complement: an exact-size flatten rule followed by a merge (new form of B4/B5)

- **Hypothesis.** It never sells. When its directional residual turns bad it taker-buys exactly the imbalance on the
  other outcome (locking a loss) and merges the pairs: a stop-loss with a threshold on the held side's fair value
  and the time left.
- **Why it fits.** Critique item 3: 157 pair-completing taker buys in STUDY, size = imbalance, pair cost median 1.12,
  at a median 176 s into the window, followed by merges about 65 s before the end.
- **Test.**
  - Per window-wallet and second: the hazard of a flatten event against the held side's futures TWAP-60 fair, time
    left, imbalance size, and unrealised loss at the current ask. Fit on BUILD and STUDY; VALIDATE aggregate only.
  - Add the fitted flatten-and-merge rule to the executable per-window PnL and recompute the PnL correlation.
  - Check what share of VALIDATE's "locked pairs" (+$38.1k) came from maker-maker pairs and what share from
    flattening pairs costing more than 1.
- **Data.** Activity (TRADE, MERGE) and fills, already cached.
- **Signature if true.** A threshold rule (for example held-side fair < x after y s with imbalance > z) predicts
  flatten events with AUC > 0.85 and exact sizes, and the per-window PnL correlation rises by >= 0.05.

### P5. Censored inverse fit of the quote from every match (strong form of B3)

- **Hypothesis.** q(t) = floor((w * book mid + (1 - w) * F_fut(t - tau) - h(time left, vol, inventory)) / 0.01), with
  a skew per side. It is identified by bounds:
  - in every bid-hit match on s without the cluster (in a window where it is active), its bid was at or below the
    lowest filled level;
  - at its fills, q equals the fill price.

  w close to 1 means a book-pegged (join) quote, which would explain why fills are flat across Binance-edge deciles.
- **Why it fits.** B3 so far fitted only filled prices. 40% of fills are at or above the Binance fair. The pilot book
  has the cluster at the top in 1.1% of 9,778 matches, so absence bounds outnumber fills about 100 to 1.
- **Test.** STUDY full tapes with maker rows (data-api trades, `taker_only=False`) or calldata of all BTC 5m matches.
  Interval-censored likelihood over (w, tau, h, skew), holding out the last STUDY day. Report the at-top AUC among
  hits.
- **Signature if true.** Parameters are stable across days and the at-top AUC among hits is >= 0.8. If instead w is
  about 1, the quote is book-pegged, and the RE should pivot fully to P1/P2.

### P6. Under mint matching the side is the taker's choice: test the anti-balancing as flow persistence (new item)

- **Hypothesis.** "Adds to the side it holds" (0.60) is the persistence of taker flow in trending windows, not a
  decision. The decision is the skew: which side it widens or pulls after a Binance move.
- **Test.**
  - Compute the same "next one-sided fill bin is on the held side" statistic for other makers of similar size
    (STUDY maker rows) and for a symmetric fixed-spread pseudo-maker run on the clean tape.
  - In the live lab (with P1), measure the skew directly: its bid on s minus the best bid, and its implied ask minus
    the best ask, by inventory and after Binance moves.
- **Signature if true.** Other makers and the pseudo-maker show about 0.60 too. The side target should then be
  redefined as skew, and the 0.80 side accuracy is bounded by how predictable the direction of taker flow is. If the
  cluster's persistence is far above theirs, the inventory-driven skew is real and should show in its quote prices.
