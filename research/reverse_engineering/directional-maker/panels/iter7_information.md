# Panel after iteration 7: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (all iterations, iteration 7 in full), state.json (ledger, catalog,
components, live split), FINAL_RULE.md and the panel files of iterations 4-6.

The small checks below used only these sources:

- development blocks of the live recordings, through `tools/live.py` `iter_live` (10-31 12:00-18:00; `clob_crypto`,
  `dy_rtds`, `dm_clob_raw`);
- the strategy's own cache: BUILD tape 10-21, the STUDY tapes 10-23..26 case by case, and feed-level aggregates of the
  Chainlink lot sample against Binance futures;
- public documentation;
- one Hyperliquid query limited to BUILD dates.

I did not read `.cache/live/sealed/`, any sealed block, another strategy's files, or anything after 10-31 18:00. The
current block (10-31 18-24) is sealed, so I ran no live websocket probe. My scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i7/`:
`ev1653.py`, `ev2.py`, `phase.py`, `follow.py`, `basis2.py`, `naive.py`, `naive2.py`.

## What my checks found

**C1. The Binance relay on RTDS was never observed.**

- `code5/rawrec.py` subscribed to the `crypto_prices` topic with `filters: {"symbol": "btc/usd"}`, which is the
  Chainlink symbol. NOTES records that "the `crypto_prices` subscription returns nothing".
- The Binance topic's symbols are `btcusdt`-style. On top of that, a symbol filter on the Chainlink topic also
  suppresses the 1-s updates (iteration 7).
- So the one public relay that would give an RTDS-only engine its "futures-driven mid" between Chainlink reports has no
  recording at all. `dy_rtds` records only `crypto_prices_chainlink` and `crypto_prices_twap_sixty`.

**C2. The relay publishes each stamp as one batch for all symbols.**

From `dy_rtds`, 10-31 17:29-18:00, 1,800 stamps per symbol:

- Publish minus stamp (p10/50/90) is 787 / 1,088 / 1,471 ms for BTC, with the same quantiles for ETH and SOL.
- For the same stamp, ETH and SOL are published -24..+16 ms (p10-p90) from BTC.
- The delay is autocorrelated: lag-1 0.26.
- The publish phase is concentrated at x.7-x.3 s, with about 3.5 times as many publishes in those bins as in x.4-x.7.
  It is not a fixed poll phase.
- The TWAP topic is published about 80 ms after the price topic (median 1,170 ms).
- This is a batch relay, presumably a bulk fetch per stamp. An engine that reads it re-prices all of its BTC, ETH and
  SOL ladders on the same publish. A historical publish clock cannot be rebuilt deterministically: stamp + 1.09 s
  ± 0.3 s is the best model.

**C3. Nothing external happened at the 16:53 switch-off in the shared recorder.**

- For 16:50-16:56 the shared `clob_crypto` has no gap: 493-806 'q' records and 55-355 'x' records per 30 s. Trades peak
  at 16:53:30-16:54:00 (355).
- There are no `tick_size_change` records between 16:45:00 (20 records) and 16:58:35.
- The exam recorder died at 16:53:27, 6-27 s before the cluster's last BTC 5m trades (16:53:33-54). This is most
  likely a laptop-local coincidence, not an exchange-side event that also stopped the engine. A8 offers no explanation
  for X58.

**C4. Copy-trading followers are not the cluster's counterparties.**

Pilot on BUILD 10-21: 439k BTC 5m taker prints, 357k taker decisions (wallet, window, 2-s bucket, direction), 2,933
wallets with at least 15 decisions.

- Same-direction following exists. 2,106 leader→follower pairs have at least 40 follows at 2-20 s and a
  forward/backward ratio of at least 8, against 860 pairs in the opposite-direction placebo.
- Their followers make 35.0% of the decisions that hit the cluster, against 41.1% of all decisions.
- Sharp-lag followers (at least half of their follows at one lag) make 0.5% against 1.0%.
- P(decision hits the cluster | it was preceded by its leader) is 0.0046, against 0.0040 otherwise.
- Copy-trade flow, the kind the RTDS `activity` feed supports, is not where the cluster's fills come from.

**C5. The Chainlink-Binance basis is large, but takers are not naive about it.**

Aggregate over the feed, lot sample, 13,309 seconds. Chainlink BTC/USD minus the Binance USD-M perp in the same second:

- Daily means run from -$67 (10-24) to -$113 (10-30).
- The within-day sd is $14. The change over 300 s has sd $9.2 (correlation 0.90). For comparison, the 300-s sigma is
  $83.5.
- A naive reading ("Binance perp against Gamma priceToBeat") picks the side opposite to Chainlink in **45.7%** of
  in-window seconds (0.31-0.55 by day). A Binance-consistent strike (the R3 fair) disagrees in only 3.9%.
- On STUDY (249k clean taker decisions, 250 windows), the takers' bullish share is a smooth function of the
  Chainlink-consistent distance to the strike: 0.452 at -$10..0 and 0.531 at 0..+$10.
- In matched distance bins, the naive-disagreement state is *less* bullish, not more (-$90..-70: 0.278 vs 0.336).
- So no population of naive "Binance vs price-to-beat" takers is large enough to matter.
- The lot does carry one Chainlink-specific variation: the basis drift inside a window, about 0.11 sigma. That is the
  variation R5's gap term lives on, and it bounds what any Chainlink feature can add on the lot.

**C6. Other sources.**

- **Hyperliquid.** `userFillsByTime` for 10-15..10-23 returns `[]` for mo-money's Safe owner EOA
  0xd1f9bc03d7395134647c6a7d3b468cfdd4b38292 and for the three proxy addresses. So there is no visible perp hedge for
  this key. The almach and bosona owner keys are still not recovered.
- **RTDS `activity`.** Confirmed from the official real-time-data-client README: topic `activity`, types
  `trades` / `orders_matched`, filter by `market_slug` or `event_slug`, no auth. The payload carries `proxyWallet`,
  `pseudonym`, `side`, `size`, `price`, `outcome`, `transactionHash` and `timestamp`.
- **Historical Polymarket book archive.** I found no historical book source. `archive.pmxt.dev` refuses connections
  (ECONNREFUSED 65.109.107.152:443), and `pmxt.dev/archive` returns 404.

## Critique

1. **The primary metric lives where the decoded input cannot show itself.** Iteration 7 established the posture rule:
   re-price on each Chainlink publish, and put the 500 bid at the touch on sign(Chainlink edge - mid). On the lot,
   Chainlink differs from the Binance-consistent fair only by the basis drift (C5: about 0.1 sigma per window). The
   historical presence AUC therefore cannot measure the mechanism, and +0.0075 is about what C5 allows. The next exam
   runs on future sealed blocks, where the recorders exist. Development choices should be made on the live development
   blocks with every input on its publish clock. Further historical tuning will not close the gap.
2. **The second input of the quote is named by correlation, not by source and clock.** "Between reports re-anchored to
   the futures-driven mid" rests on a direction agreement at a 50-250 ms lag (A2/X10). That lag is too slow for an
   engine that answers a Chainlink publish within 0-50 ms if it read Binance directly near the CLOB. It fits either a
   relay or a distant host. The relay that a Polymarket-RTDS bot would use (`crypto_prices`) was never recorded (C1).
   Chainlink was decoded by putting it on its own publish clock; the futures input has not had the same treatment.
   H46 says the quote state, not taker flow, is the binding factor. A quote that is exact at every millisecond needs
   both clocks.
3. **The taker-arrival search has covered only part of the obvious public triggers.** Tested so far: the display (I3),
   fast futures (X28, 0/182), taker class on the block clock (H30), and now copy-following (C4) and naive basis reading
   (C5). All are negative. The untested public trigger is Polymarket's own cross-horizon books (15m, 4h, next 5m) and
   Kalshi's same-quarter market, which settle on the same or a closely related close. A4's "overlapping window prices
   not used" is still open.
4. **Exam-data risks.**
   - The 10-31 06-12 sealed block has only the shared recorder: filtered RTDS snapshots at about 52% second coverage.
     It has no `dy_rtds` publish ms and no `dx_*` futures. The frozen rule's fallback (endpoint series, stamp
     t - 1.43 s, futures from aggTrades) must be specified before the exam, not left to the examiner.
   - The exam recorder died silently once. Add a watchdog, or at least a status-age check, for `examrec` and
     `dy_rtds`.
   - BTC 5m has been off since 16:53. If it stays off, a BTC 5m-only universe fails the 80% scope condition on the exam
     lot. The 15m inputs are recorded, and the endpoint serves the `fifteen` variant, so the rule must cover BTC 15m.

## Proposals (ranked by the chance they close the gap)

### I7-1. The between-report input on its own publish clock: the RTDS Binance relay (`crypto_prices`) or a direct Binance feed (new; strong form of A2/X10 and of the mis-filtered `crypto_prices` subscription)

**Hypothesis.** The engine is a Polymarket-RTDS bot that reads both of its price inputs on one socket:

- the Chainlink topic (decoded in iteration 7);
- the Binance relay topic `crypto_prices` (btcusdt).

Between Chainlink reports it re-anchors its ladders on each `crypto_prices` publish. Two alternatives:

- **(B)** a direct Binance futures websocket on a host far from Tokyo, with a fixed transit of about 100-150 ms;
- **(C)** a direct co-located feed. C is already unlikely given the 50-250 ms lag.

**Why it fits.**

- 95% of the exact-500 re-posts follow a futures mid move of the previous 50-250 ms. The same engine reacts to
  Chainlink publishes in 0-50 ms (bursts).
- The single-wallet re-posts between passes have no trigger clock yet.
- The only attempt to record `crypto_prices` used the Chainlink symbol as its filter (C1).
- The relay is a batch publisher with variable delay (C2). If the Binance topic works the same way, its publish times
  carry the same "variable relay delay" fingerprint that separated K1 from K2.

**Test.**

1. Before 11-01 06:00 UTC, add `crypto_prices` (filters "") to a `dy_rtds`-style recorder through `tools/live.py`
   `Writer`, so that the sealed blocks are filed correctly. Keep btcusdt (and ethusdt, solusdt) with the value stamp,
   publish ms and receive ms. The same filter mistake may affect `crypto_prices` in the shared recorder, so record it
   yourself.
2. In the first minute of the 11-01 06-12 development block, check the update rate and whether the value is spot or
   perp. Compare it at the millisecond level with `dx_bnf` bookTicker and Binance spot.
3. On 11-01 06-12, BTC 5m (BTC 15m if 5m stays off), take the cluster's exact-500 re-posts with a price change that are
   **not** within 200 ms after a Chainlink publish. Measure the agreement of the re-post direction:
   - (a) with the change in the latest RTDS-Binance update, in 25-ms bins from -1,000 to +1,000 ms around its publish
     ms;
   - (b) with the futures bookTicker change, in bins around Binance's event time E.
4. Measure the distribution of the re-post's CLOB server ms minus E of the triggering futures change. It is tight around
   a fixed transit under (B) and as wide as the relay delay under (A). Use server clocks only.
5. Rebuild the engine's quote at every millisecond. The center is the Chainlink report at its publish, plus the
   Binance-relay increment since then (or the direct futures increment). Re-run:
   - live print selection (`code7/sel_clock.py`);
   - stage 1 of the two-stage presence (P(cluster at the touch on s)), against the pre-registered 11-01 baseline.

**Data.** RTDS `crypto_prices`, not yet recorded; verify it on the development block. Also `dx_bnf`, `dx_clob`
schedule-size deltas and `dy_rtds`.

**Signature if true.**

- (A): agreement about 0.5 before the Binance-relay publish, rising to at least 0.75 in the 0-150 ms after it. Re-posts
  of all three wallets cluster on those publishes. The lag to E is as variable as the relay delay.
- (B): one step at E + about 100-150 ms whatever the relay does.
- Either way, the between-report re-pricing gets an exact public trigger.
- If the quote state is binding (H46), the two-clock quote model should take live print selection from 0.764 to at
  least 0.80, with recall of at least 50%, and lift posture side above 0.79.
- If neither clock explains the between-report re-posts, record the share of re-posts that have no public trigger.
  That is part of the quantitative account.

### I7-2. Cross-horizon Polymarket books and Kalshi as the trigger of the sellers who fill the cluster, and the source of the posture residual (strong form of A4's open part and X48)

**Hypothesis.** Part of the non-HFT sellers who meet the cluster's fresh 5m joins are cross-market traders. They
arbitrage or hedge the 5m book against a book that settles on the same Chainlink close:

- the BTC 15m window in its last third;
- the 4h window at its last 5m;
- the next 5m window around the boundary;
- Kalshi's KXBTC15M for the same quarter.

Their arrival in the 5m book follows moves in those books. The 21% of posture events where sign(Chainlink edge) is
wrong may be quotes centered on the 15m-implied fair.

**Why it fits.**

- The sellers follow neither the display (I3) nor fast futures (X28: 0/182).
- Adding futures to activity does nothing for live selection (0.637 to 0.638).
- Copy-following and naive basis reading are negative (C4, C5).
- The cluster quotes 5m and 15m at once (87% of VALIDATE fills).
- In the 5m windows that end on a 15m boundary, both markets settle on the same closing TWAP-60. The cross-book
  relation is mechanical, and nothing in R3/R5 uses it.

**Test.**

1. **Live** (11-01 06-12; the shared `clob_crypto` records BTC 5m, 15m and 4h books and trades).
   - For each 5m window that ends on a 15m or 4h boundary, compute the 15m-implied 5m fair. Take the 15m mid and its
     strike K15, find the closing-TWAP mean implied under the Chainlink-consistent sigma*sqrt(tau), and evaluate
     P(close >= K5).
   - Event study: the 5m taker sell (or complement-buy) hazard in the 0-3 s after |implied - 5m mid| crosses 2-3 c,
     against the same after equal futures moves and at random times.
   - Identify the wallets that trade both books within 10 s, from the trade records' transaction hashes joined to the
     data-api tape.
2. **Historical** (STUDY tapes of the 15m windows in `.cache/re/directional-maker/t15`).
   - Add the 15m last-clean-print-implied 5m fair and its gap to the 5m last print to R3/R5, in the aligned windows
     (one third of the 5m windows).
   - Use the non-aligned windows as the placebo.
   - Score aggregate only on VALIDATE.
3. **Kalshi.** Fetch KXBTC15M public trades (microsecond timestamps; verified by panel 6) for the same quarters. Measure
   the Polymarket 15m and 5m taker hazard after Kalshi prints that move its implied probability away from Polymarket's.

**Data.** The shared recorder books, the 15m tapes already on disk, and Kalshi's public API (no key).

**Signature if true.**

- In the aligned windows, the cross-book gap predicts 5m seller arrival with a hazard ratio of at least 2 and predicts
  cluster fills.
- Presence gains at least +0.02 in the aligned windows and about 0 in the non-aligned placebo.
- A recurring set of two-book wallets shows up among the cluster's counterparties.
- The posture residual shrinks when the 15m-implied fair is blended in.
- Otherwise A4 and X48 close with numbers, and the presence gap is taker arrival with no public trigger, which is part
  of the quantitative account.

### I7-3. The strike is public on RTDS about 1 s before the open, and later elsewhere: an opening-seconds information edge (new)

**Hypothesis.** The engine computes priceToBeat itself from the relay stream: the mean of the Chainlink stamps
st-61..st-2, complete at about st - 0.9 s given the C2 delays. Other makers wait for Gamma
`eventMetadata.priceToBeat`, or quote the open on a proxy (the previous strike, or Binance at the open). For the first
seconds of each window the cluster is the only maker centered on the exact strike. Its opening posture and fills are
therefore set by the exact-strike edge against a mid that is still stale.

**Why it fits.**

- 15.6% of fills fall in the first 30 s.
- Its first fill comes within 6 s of the open in 21% of active BUILD windows; orders rest at the open.
- The opening side follows sign(spot - TWAP strike) 66-79% of the time.
- Side accuracy is 0.769 in the first 30 s, the best-decoded segment.
- Iteration 1 notes a "strike-lag effect".
- When priceToBeat actually becomes available to the public was never measured. The brief's convention ("usable from
  the start") hides this timing.

**Test.**

1. On 11-01 06-12, for 12-20 windows, poll Gamma `/markets?slug=btc-updown-5m-<st>` (`eventMetadata.priceToBeat`) and
   the crypto-price endpoint (its `completed` flag) once a second from st - 10 to st + 120. Record when each first
   carries the strike.
2. Using the shared recorder's non-cluster sizes, test whether other makers' opening mids track the exact-strike fair
   or a stale proxy until that time.
3. On the lot: presence and fill return by second in the window, split by the strike surprise |exact strike -
   (previous strike or spot at the open)| / sigma*sqrt(tau). Add the surprise as an early-bin feature (first 60 s)
   to R5.

**Data.** Gamma and the crypto-price endpoint (polite: about 1 request per second for a few minutes), the shared
recorder, and the Chainlink lot sample.

**Signature if true.**

- Gamma's priceToBeat appears seconds to minutes after st.
- Other makers' opening mids follow the stale proxy until then.
- The cluster's fill rate and return in the first N seconds rise with the strike surprise.
- The presence gain is concentrated in the early bins.
- If Gamma publishes before st and other makers center on the exact strike at the open, close the item.

### I7-4. RTDS `activity`: taker identity in real time, as an engine input and as a millisecond-clock presence feature (new; strong form of H30)

**Hypothesis.** RTDS `activity` is the only public real-time source that names the taker of each trade (C6). The
engine's touch re-posts and pulls may depend on who just traded: re-post at the touch behind slow takers, pull after
known latency takers. That would explain why "a fresh 500 at the touch after a trade" is weak on anonymous features
(P1: AUC 0.61, placebo 2.7% against 2.4%), while the profit comes only from non-HFT first prints. The same identity
stream, on the match clock, could predict the next seller better than anonymous counts.

**Why it fits.**

- The filled orders were posted a median 95 ms after some trade.
- Latency takers never reach the cluster (0/182).
- H30 tested taker class only on 2-s block stamps and pooled; it was not tested on the clock where a 95-ms decision
  happens.

**Test.**

1. On 11-01 06-12, record `activity` (filters by `market_slug` for the current and next BTC 5m and current 15m) through
   `Writer`.
2. Measure its latency against the CLOB `last_trade_price` server ms for the same transaction hash.
3. If it arrives within about 150 ms:
   - re-run P1 with the trade's taker class (the BUILD HFT list, per-wallet history) as features;
   - test whether the cluster's at-touch 500s are cancelled or re-posted at different rates after latency takers and
     after slow takers.
4. If it arrives seconds later (published from the chain), the engine cannot use it for sub-second decisions. Close
   the item with that latency.

**Signature if true.** Activity latency is under 150 ms. P1 join AUC goes from 0.61 to at least 0.70. Re-post and
cancel rates differ at least twofold by taker class. Lower prior: C4 already shows the counterparties are not a
follower class.

## Notes for the RE

- **Today, before the next development block.** Start the `crypto_prices` (filters "") recording (I7-1). Optionally
  start an `activity` recording (I7-4). Add a watchdog or status-age alarm for `examrec` and `dy_rtds`.
- **Freeze the exam fallback.** Specify it now for the 10-31 06-12 sealed block, which has no publish ms and no futures
  recording. If BTC 5m stays off, make BTC 15m part of the rule's universe.
- **Closed or weakened by measurement this round.**
  - An exchange-side trigger for the 16:53 switch-off (C3).
  - Copy-trading followers as the cluster's counterparties (C4).
  - Naive "Binance vs priceToBeat" takers (C5).
  - A deterministic historical publish clock (C2).
  - A Hyperliquid hedge by mo-money's owner key (C6).
- **A bound for R5 on the lot.** The basis numbers in C5 bound what R5 can add there: about 0.1 sigma of
  Chainlink-specific variation per window. Report that bound with the full-VALIDATE R5 number, not as a failure of the
  Chainlink hypothesis.
