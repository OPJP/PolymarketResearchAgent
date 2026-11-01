# Panel, iteration 6: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used: calldata, resting-order lifetimes, cancels, the operator's
transaction pipeline, order-type and level choices, software fingerprints.

All my checks used development data only: the VALIDATE/BUILD calldata sample, `b1_orders_sample.parquet` and `cells/`
already in `.cache/re/btc5m-bot/`, the 10-31 13:00-14:47 development-block files `live6_takers.parquet`,
`live6_events.parquet` and `post/cd6_live.parquet`, plus cached Polygon RPC calls (`eth_getTransactionByHash` for 60 live
cluster txs, `eth_getBlockByNumber` without transactions for their blocks). Scratch scripts and outputs are in my
scratchpad, not in the workspace. I read nothing sealed and did not open `.cache/live/`. Time of writing: 10-31 15:50 UTC.

## Critique

1. **The decoded trigger cannot be examined on any future sealed block, as the recorder is set up now.**
   - `code/rec_lab6.py` (both v1 and the running v2) drops every record while the calendar block is sealed
     (`Out.write` returns False unless `dev_now()`). So `btc5m_venues2` (the sized quotes behind the 86% microprice vote)
     and `btc5m_clob_raw2` (the unthrottled book and the trade events that give the match ms) will be empty for every
     sealed block.
   - `tools/live.py` `Writer` already files records into `sealed/` by receive-time block, and the brief asks recorders to
     use it "so it files records the same way". The researcher never reads `sealed/`. The examiner reads it with
     `ALLOW_SEALED = True`.
   - The next sealed block starts **10-31 18:00 UTC**. Together with 11-01 00:00-06:00, it makes the first 12 sealed
     hours a future exam would use. Unless the recorder writes sealed blocks by then, that exam can only see the shared
     recorder's `clob_crypto` (54 slow-consumer reconnects so far) and `rtds`. Seven of the ten quote series have no
     public archive (the Binance USD-M bookTicker archive is 404; OKX, Hyperliquid and Binance spot quotes have none).
   - The fix is small: write in every block through the Writer, keep the hard stop, and budget disk for both folders
     (count `sealed/` in the 250 MB cap, or coalesce to 50 ms during sealed blocks). Note it in `live_lab`. Without it,
     the only exam lots available (h1/h2, then the future blocks) can never test the one component that decodes the
     quiet matches.

2. **"An unfilled remainder rests at the limit" is wrong as stated. Remainders vanish within seconds.** I checked this
   on the 11-hour calldata sample (13,443 cluster BUY orders, fills summed per (maker, salt), against `cells/` prints
   that exclude the cluster):
   - 10,967 orders begin with a taker match, and 55.7% of them leave an unfilled remainder (taker fill fraction:
     median 0.945, lower quartile 0.333).
   - Only about 20% of those remainders ever get a later maker fill: DS 22.7%, GF 16.5%, XM 19.7%; 30-share orders
     23.8%, 100-share orders 11.9%.
   - For all 7,038 orders that end with a remainder, the same outcome printed at least 1.5 c **below** the limit,
     without filling it, in 48.5% of cases within 3-10 s after the order's last fill, 61.3% within 10-30 s and 67.0%
     within 30-90 s. Orders without a remainder show the same rates (52.9 / 62.3 / 67.1%), so the price path is
     ordinary.
   - The first such print comes a median 6-7 s after the last fill, within 1 s in 15%, 2 s in 21% and 5 s in 39%.
   - A resting BUY at L is filled first by any seller below L, including mints against a complementary BUY. So the
     remainder had already gone.
   - Where remainders did fill, the first-to-last fill span is short: take-then-rest p99 8 s, max 17 s (n = 1,653);
     pure resting p99 6 s.
   - So the bot either cancels within a few seconds or sends some orders as fill-and-kill. This changes three things:
     - the price/quote component (B2 "cancellations not observable historically" is not true: they are inferable as
       above);
     - the maker-fill part of presence: maker fills are echoes of a decision at most about 10-17 s old;
     - the side of maker fill-seconds, which is the side of that earlier decision, not of the current move. This is
       exactly XM's 4,033 "sibling bought the other outcome" seconds at 59.1%.
3. **X15 was ruled out on a weak form.** "Unfilled submissions are not attributable" was decided on order size alone
   (bot sizes are common). Two fingerprints were never tried:
   - the cancel lifetime of a submission (point 2 suggests it is short and possibly fixed);
   - the fan-out lag pattern: DS, then GF a median 54 ms later, then XM 15 ms after GF, as identical-size insertions at
     the same level.

   A decision record that includes lost races is the presence target the brief prefers ("whether it has an order
   resting"). It would also be the only way to measure P(win race | decision), the part of fill presence no public
   feed can explain.
4. **Historical decision times: what the operator's pipeline does and does not carry** (live, 782 taker txs, per-hour
   chain clock fitted from (block, ts) pairs):
   - Match to block: median 2.48 s, 5-95% 1.66-3.39 s, sd 533 ms. The spread is about one block interval, so it is
     the phase of the match inside the block cycle.
   - Gas fields carry nothing. In 40 of 60 txs maxFeePerGas = 12.00 x maxPriorityFeePerGas, a fixed relayer formula.
     The tip is uncorrelated with the delay (Spearman -0.02) and with tx_index (0.03).
   - The relative position in the block helps: tx_index / block tx count has Spearman -0.57 with the delay (raw
     tx_index -0.43, n = 200). Fitted on the first half by time and tested on the second, |error| < 200 ms rises from
     26% (constant) to 37%, and < 400 ms from 53% to 65%; sd falls from 511 to 439 ms.
   - The freshest consumed maker's signing ms as a lower bound takes the < 200 ms share to 43%. Clip it first: 5.6% of
     non-cluster maker orders carry a signing timestamp after the match.
   - This is useful but not yet enough to align a 100-600 ms reaction window historically (proposal 2).
5. **Two negatives that save time:**
   - **Quiet bursts are not child orders of one parent decision.** A quiet match has the same side as the previous
     cluster match in the same window 72% of the time at 0.3-1 s back, 66% at 1-2 s and 44% at 2-5 s. Moving matches
     give 68 / 66 / 47%. The bot flips side within a second about 30% of the time: these are fresh decisions.
   - **There are no further siblings among the makers.** Of the non-cluster makers with at least 40 orders in the
     calldata sample, only 0xd84403ef (W4) is pre-signed (median sign-to-block 66 s). The four C2 co-racers
     (0x41e2e1cc, 0x2ed94d1a, 0xeebde7a0, 0x19b38230) and the prey 0xec10d230 sign 3-4 s before the block, in real
     time. The tight ±20 ms races are other operators, not the cluster.
6. **Measurement notes:**
   - The selection baseline includes the print's own size class ("size classes + pure market cell score"). Size is the
     decoded sizing component, not market activity, which the brief defines as other traders' prints and timing, time
     in the window and price level. Report the selection gain against a baseline without the candidate print's own
     size as well. The examiner's baseline may not contain it, and then the selection route (+0.023 now) may pass.
   - The microprice threshold of 0.002 bp is below one ETH tick, so it fires on any queue-size change. The vote covers
     81% of placebo instants too. The evidence is in the agreement, not the coverage. The out-of-sample quiet subset is
     77.3% on 22 voted matches, on a Saturday.

## Proposals (ranked by the chance of closing the gap)

### 1. Decode the remainder lifecycle (cancel / TTL / fill-and-kill) and use it to recover the full decision record (strong form of B2 and X15; new)

- **Hypothesis.** Each submission is a pre-signed ladder order sent at (or just above) the touch. Any unfilled
  remainder is removed after a short, fixed or event-driven time: a cancel after a timeout, a cancel on the next contrary
  microprice tick, or fill-and-kill for some orders. Three consequences follow:
  - maker fills are deterministic echoes of decisions at most ~10-17 s old;
  - unfilled submissions carry a lifetime fingerprint that separates the cluster from the other bots using the same
    sizes;
  - the side of a maker fill-second is the side of the echoing decision.
- **Evidence.**
  - Critique point 2: 55.7% of taker orders leave a remainder and only ~20% of those ever fill again, although the
    outcome trades through the limit within a median 6-7 s.
  - Take-then-rest fill spans have p99 8 s and max 17 s.
  - The share of remainders that rest and fill differs by size (30 shares 23.8%, 100 shares 11.9%) and by wallet (DS
    22.7%, GF 16.5%). The order type or TTL may be a per-wallet or per-size setting.
  - H10: 69% of pure resting orders follow a competitor's take at the same price within 5 s (placebo 7%). They are lost
    races, and they rest only briefly.
- **Test.**
  1. *Historical, on disk.* For every cluster order with a remainder in the calldata sample, use two bounds on its
     removal time:
     - upper bound: the earliest non-cluster print on the outcome at or below L - 1 tick after its last fill;
     - lower bound: the last maker fill.

     Fit the removal-time distribution as interval-censored data. Do it by wallet, size, day (config changes),
     regime (a fast venue move vs quiet at the taker match) and window time. A point mass near 0 points to
     fill-and-kill, a sharp mode to a TTL, a spread to cancel-on-event.
  2. *Live, at server ms* (`btc5m_clob_raw` / `btc5m_clob_raw2`, `post/cd6_live.parquet`, own fills):
     - For each on-chain cluster taker order, compute the remainder R = original size minus the taker fill, at L on
       outcome o. This is a bid at L on the Up book, or for Down the mirrored Up ask at 1 - L.
     - Find the size increment of R at that level within ±50 ms of the match.
     - Then find its later decrement by R with no trade print at that level in the same ms.
     - Measure the cancel delay. Check its sharpness, its synchrony across wallets (a cancel-all), and its alignment
       with contrary venue microprice ticks or with the next ladder burst.
     - Remainders that never appear in the book are fill-and-kill orders.
  3. *Attribution.*
     - Classify every bot-size insertion at the bought outcome's touch by (lifetime close to the decoded TTL) and
       (identical insertions at the same level spaced at the fan-out lags of ~54 ms and ~15 ms).
     - Measure precision on the insertions that later link to an on-chain cluster fill.
     - Build the decision record for 10-31 13:00-17:00 and the next development blocks: decisions per minute,
       P(fill | decision) by regime, and the microprice-vote side agreement on unfilled decisions.
  4. *Use it in the rule.*
     - Add a maker-echo component: P(maker fill at s on o) rises with the PIT triggers toward o in [s - TTL, s) whose
       touch was at the current price.
     - For fill-seconds the rule assigns to an echo, predict the side as the echoing trigger's side.
     - Re-score XM's one-sided seconds and the block-second presence gain.
- **Data.** Already on disk: calldata sample, cells, live calldata. Plus the development-block raw book through
  `iter_live` and the next development blocks (11-01 06-12 and 18-24, 11-02 00-06).
- **Signature if true.**
  - Removal times concentrate: for example ≥ 70% within ±100 ms of one value, or within 200 ms after a contrary
    microprice tick. A per-wallet or per-size point mass at 0 means fill-and-kill.
  - Bot-size insertions with the decoded lifetime are ≥ 60-70% cluster-linked where it can be checked.
  - Side agreement on unfilled decisions matches the filled ones (~86%): one trigger.
  - XM's sibling-opposite seconds rise from 59% toward the taker level (≥ 75%), taking XM's one-sided-second side from
    72.6% toward 80%.
  - The maker-echo component adds to the presence gain over the pure baseline.
  - If false (no fingerprint), the removal-time bounds still correct the rule description and quantify how much of
    fill presence comes from race outcomes.

### 2. Exam-ready decision times for h1/h2: a per-block match clock from the operator's tx ordering and co-racers' signing ms (strong form of X22 and X12)

- **Hypothesis.** The 1.7-s blur between match and block is mostly the phase of the match inside the block cycle. Two
  things recover it to about ±150 ms historically:
  - the order in which the operator's relayers land matchOrders txs inside a block;
  - the signing ms of co-racers who sign at decision time.

  With that, the Bybit ETH/BTC 100-ms book archive (all 14 development days on disk, and fetchable for h1/h2) can
  reproduce the live microprice trigger historically. The side model then gains more than the +0.5 points the
  block-second alignment allows.
- **Evidence.**
  - Critique point 4: relative block position has Spearman -0.57 with the delay, and |error| < 200 ms goes from 26% to
    37% out of sample (43% with maker lower bounds). The gas fields carry nothing.
  - Other traders' taker orders are signed a median 3.1 s before the block, close to their match.
  - Live, the microprice vote gives 86% at the true match ms. Historically, the block-second Bybit ETH features add
    only 0.5 points.
- **Test.**
  1. *Necessity first (live, about 30 minutes).* Restrict the frozen vote to the series that have a historical archive
     (Bybit ETH and BTC, reduced to 100-ms buckets as `bybit_ob.py` does). Compute side agreement on the 366 covered
     matches three ways:
     - (i) at the true match ms;
     - (ii) at block time minus the median delay;
     - (iii) at the relative-position estimate.

     If (i) is ≥ 80% and (ii) falls near the 77% block-second level, alignment is the bottleneck and the rest of this
     proposal is worth doing.
  2. *Co-racer clocks.*
     - For every non-cluster taker tx in the same blocks as live cluster matches (tx hashes from the recorded trade
       events or the data-api tape; calldata through `calldata.py`), calibrate each wallet's sign-to-match lag against
       its recorded match ms.
     - Wallets with tight lags (p10-p90 under ~150 ms) become clocks.
     - Estimate each cluster match by its in-block position between clock txs (tx_index), bounded by the freshest
       consumed maker's sign ms and the block time.
  3. *Apply on the 7 sampled VALIDATE hours.* Fetch co-racer txs for those hours (about 1-2k txs per hour, decoded fields
     only), compute the Bybit microprice vote over [m-hat - 600, m-hat - 100) ms, and score taker-order side by wallet
     and halves.
- **Data.** Live development blocks (on disk). Polygon RPC (`eth_getBlockByNumber` without transactions is light;
  `eth_getTransactionByHash` for co-racers). The data-api tape tx hashes. Bybit orderbook.200 (on disk for
  development days).
- **Signature if true.**
  - m-hat is within 150 ms of the true match for ≥ 60% of live matches.
  - Historical taker-order side with the Bybit microprice vote at m-hat is ≥ 82% (vs 80.3% for the it6 candidate), and
    XM's taker side is ≥ 80%, on both halves.
  - The block-second presence gain rises once the presence model is fed the m-hat-aligned microprice.
  - If (i) is not clearly above (ii) in step 1, drop the proposal: the historical lots cannot carry the trigger, and
    that is a quantitative statement for the wall account.

### 3. The live reaction kernel: which venue's book the bot actually reads, and from where (strong form of X24 and C8; new)

- **Hypothesis.** The bot reads one primary quote stream, or a fixed composite, with a fixed processing and network
  path. The lag from a microprice tick on that stream to the Polymarket match is then sharp: a narrow peak at a
  venue-specific delay. Other venues show broader, later peaks that come through correlation. The fixed
  [m - 600, m - 100) ms window for all ten series mixes these. A venue-specific window would raise agreement and cut
  placebo coverage, and the per-venue minimum lags locate the bot (for example near Tokyo vs near the CLOB).
- **Evidence.**
  - Live agreement is 94% for trades and 85-90% for microprices over a 500-ms window. Placebo coverage of the vote is 81%,
    so the window is too wide to separate.
  - ETH series dominate.
  - Iteration 5 found no ms-phase periodicity (event-driven).
  - Fan-out lags of 54 ms and 15 ms show sequential HTTP submissions from one process. The time between decision and
    match therefore includes the bot-to-CLOB path.
- **Test.**
  1. For each of the ten quote series and eight trade series (exchange ms), take every microprice tick (sized, any
     queue change) and trade-price move.
  2. Build the cross-intensity with the cluster's first match per fire event, at 10-ms resolution over lags of 0-1,000
     ms, split by direction (toward the bought outcome vs away). Use a placebo-time null and the matches of other
     takers as a control.
  3. Identify the venue and series with the earliest, sharpest directional peak. Freeze a narrow window per series
     (for example peak ± 2 FWHM) on 10-31 13:00-15:00, and test it on 15:00-17:00 and the next development blocks.
  4. Compare the minimum lag per venue with the TCP RTTs already measured: Binance 347 ms, OKX/Bybit/Coinbase 68-77 ms,
     Polymarket edge 79 ms.
- **Data.** `btc5m_venues` / `btc5m_venues2`, `rest6_*` trades, live matches (on disk), next development blocks.
- **Signature if true.**
  - One series (most likely the Binance USD-M or OKX ETH book) shows a peak with FWHM under ~100 ms at a lag of
    ~150-350 ms, earlier than every other series.
  - The narrow-window rule keeps ≥ 85% side agreement at ≥ 60% coverage, with placebo coverage down to ≤ 30%.
  - Quiet-match agreement rises above 84%.
  - This also gives the hazard model (D2) its kernel.
  - If every venue shows the same broad bump, the bot uses an unrecorded composite or a faster private feed: a
    measured limit for the wall account.

### 4. The chosen ladder level and the decision not to chase: a censored readout of the bot's reservation price (strong form of B3 and X21; new)

- **Hypothesis.** The ladder offers every cent at every moment, so the level the bot submits is a free choice that
  reveals its reservation price. So does its failure to resubmit after a lost race. Every submission at L implies
  FV - margin ≥ L. When it does not chase, even though the next level is pre-signed and the trigger persists, it
  implies FV - margin < the new touch. Interval-censored regression on these bounds identifies the bot's FV directly,
  without having to calibrate an FV against the mid first. X21 failed at 4.8 c of calibration error.
- **Evidence.**
  - 11.4% of taker limits sit above every consumed level: 23% for 100-share orders, DS 8.8%, GF 16.7%, XM 11.5%.
  - 55.7% of taker orders leave a remainder that is then dropped (critique point 2).
  - Live, the touch moves in the second before the match: equal at -50 ms 71-78%, at -1 s 22%.
- **Test.**
  1. Live, from the raw book at the decision instant (m - 100..300 ms), classify each cluster submission:
     - at the touch;
     - paid up by k ticks;
     - for lost races (point 2's attribution, or on-chain resting orders): whether a resubmission at a higher level
       followed within 1 s.
  2. Fit P(pay-up) and k against the microprice and trade move size, delta = phi(d) / (sigma sqrt(tau)), time left,
     size and wallet.
  3. Build interval bounds on FV - margin per decision. Fit FV = Phi(composite microprice level, strike, tau, sigma),
     with the margin set to the net taker fee 0.035 p(1 - p) or left free, by interval regression.
  4. Score the fitted FV's sign rule (argmax FV_o - ask_o) on quiet decisions, out of sample.
- **Data.** Raw book and venue quotes (development blocks), live calldata (on disk). Historically: calldata limits and
  touches for the pay-up part.
- **Signature if true.**
  - Pay-up probability rises monotonically with the signal.
  - Fewer than 10% of the bounds contradict one smooth FV.
  - The fitted margin is close to the net fee (the rebate-adjusted break-even, X13).
  - The FV side rule gets ≥ 80% on quiet decisions where the move-based value gap gets 59-68%.

### 5. Find the bot's software with authenticated GitHub code search (strong form of X10)

- **Hypothesis.** The operator built the bot from, or published, a public TypeScript project. The wallet name
  "dangerously-skip-permissions" (a Claude Code flag) points to agent-written code, which is often pushed to GitHub. If
  it is found, its defaults state the trigger thresholds, the TTL and the FV model outright.
- **Evidence.**
  - X10 was one web search.
  - `gh` on this laptop is logged in (`gh auth status`: account OPJP). `gh search code "btc-updown-5m"` returns at
    least 30 files, among them `KaustubhPatange/polymarket-trade-engine`, `yyq7903/auto-trading` (`btc5m-trader/`),
    `openclawby/claw-poly`, `evan-kolberg/prediction-market-backtesting`, `TorchTrade/torchtrade` and
    `pmxt-dev/pmxt`.
  - Four fingerprint queries returned nothing: "presign createOrder updown", "bbo-tbt bookTicker clob-client",
    "microprice polymarket updown" and "TAKER_REBATE polymarket".
  - grep.app returned HTTP 429 at 15:45 UTC.
- **Test.**
  1. Enumerate the repos that reference the Up/Down slugs (`btc-updown-5m`, `updown`) together with clob-client order
     creation (`createOrder`, `signOrder`, `postOrders`) in a loop over prices. Also search for multi-key configs
     (several private keys or funders) and for Binance/OKX/Bybit/Hyperliquid book subscriptions.
  2. Read the defaults: sizes, re-sign schedule, ladder range, thresholds, cancel timeout.
  3. Test each candidate's default rule against the live decision record: side, timing kernel, sizes 30/60/100,
     re-signing at -89.5/+42/+172.7 s, ladder 0.12-0.88.
- **Data.** GitHub code search through `gh` (rate-limited, keep queries few), then the repos' source.
- **Signature if true.** A repo whose defaults reproduce at least two of: the burst schedule (~131.5 s), the 1-cent
  two-outcome ladder with copies, the 30/60/100 size menu, a cancel timeout matching proposal 1, and a microprice or
  bookTicker trigger. Its rule then reaches the live 86% or better without fitting.
