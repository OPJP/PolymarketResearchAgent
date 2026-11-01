# Panel after iteration 16: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md (premise, hidden dimensions, catalog), NOTES.md (iteration 16 in full, earlier
iterations by search), state.json (every catalog item, components, splits, live_lab), EXAM.md, and the proposal titles of
every earlier information panel (iteration 15 in full). I did not read the iteration-16 mechanics or assumptions panels,
which were written in parallel.

Data I touched. All of it is development by `sealed.py` (10-31 14:00-15:40 and 11-01 07:00-10:10 UTC, plus listing-time
fields of three BTC 5m windows of 10-09..22 and twelve BUILD/STUDY days of the RE's own day-level results). Nothing sealed
was read. I opened nothing from another strategy's workspace or feeds; listing `.cache/live/dev/` shows feed names only.

- `iter_live` reads of `dy_rtds`, `dm_bnf` and `clob_crypto` (trades with tx hash and server ms);
- the RE's `windows_5m.parquet` (3 condition ids), `results/iter13_noise_onset.json`, `results/iter11_k_by_day_binance.json`,
  and `code4/calldata.py` (imported, unchanged);
- about 640 `eth_getTransactionByHash` calls (publicnode / drpc) for random `clob_crypto` trades in four 10-minute dev
  windows; 6 CLOB `/clob-markets` and `/markets` requests; 12 Polymarket Perps API requests; Polymarket docs pages and
  changelogs; PyPI and npm release metadata; 3 Pyth requests (401); 4 Base/Arbitrum `eth_getLogs` probes.

The scripts ran from my session scratchpad and are not saved in the workspace; each check states its construction so it
can be rebuilt. Nothing was added to `.cache/re/`.

## What my checks found

**C1. BTC 5m windows have a venue taker hold, and the investigation has been reading it as taker latency.**

- `GET https://clob.polymarket.com/clob-markets/{condition_id}` returns `"itode": true` for the three BTC 5m windows I
  checked (10-09 00:00, 10-15 22:40, 10-22 21:20 UTC). The docs' order-lifecycle page defines the flag: a marketable
  order "is held ... then validation runs again and the order is matched or placed on the book", and "during the delay,
  the order is pending and cannot be canceled". `seconds_delay: 0`, which iteration 13's information panel read as "no
  venue delay", is the separate sports delay field.
- The Predictions changelog dates the crypto hold:
  - 250 ms before 2026-08-17 11:00 UTC;
  - 50 ms from then;
  - 150 ms from 2026-09-04 14:00 UTC.

  The order-lifecycle page still says 250 ms. SDK 0.15.0 (PyPI and npm, 10-29 14:47 UTC) adds a per-market
  `takerDelayMs` field.
- Measured hold: match server ms (`clob_crypto` 'x') minus the taker order's signed `timestamp` (calldata). I took 160
  random trades from all BTC/ETH/SOL 5m/15m/4h books in each window; 158-159 decoded per window.

  | window (UTC) | p5 | p10 | p25 | median | share < 250 ms |
  | --- | --- | --- | --- | --- | --- |
  | 10-31 14:10-14:20 | 186 | 191 | 207 | 492 | 0.34 |
  | 10-31 15:20-15:30 | 192 | 204 | 256 | 746 | 0.23 |
  | 11-01 08:00-08:10 | 186 | 187 | 200 | 271 | 0.48 |
  | 11-01 09:00-09:10 | 187 | 194 | 214 | 410 | 0.35 |

  The floor is about 185-195 ms on both blocks, which is a 150-ms hold plus about 35-45 ms of transport. The hold did not
  change between the 10-31 and 11-01 blocks.
- The share of automated takers (matched at the hold floor) varies twofold between windows (0.23-0.48). It is highest in
  11-01 08:00-08:10, which is the fast move where mo-money's 48 fills had a report accuracy of 0.125.

**C2. The Chainlink value stamped s reflects the futures about 0.5 s before s, and it is published about 1.1 s after s.**

- Data: `dy_rtds` BTC reports (consecutive 1-s stamps) against the `dm_bnf` futures mid at Binance event ms, on
  11-01 07:00-08:00 and 08:00-09:00 (clean regime).
- I correlated dCL(s) with the futures move F(s - L) - F(s - L - 1 s):

  | hour | L 0 | 0.25 | **0.5** | 0.75 | 1.0 | 1.5 |
  | --- | --- | --- | --- | --- | --- | --- |
  | 07-08 | 0.30 | 0.49 | **0.50** | 0.49 | 0.42 | 0.18 |
  | 08-09 | 0.57 | 0.65 | **0.67** | 0.59 | 0.36 | 0.18 |

  The detrended level gap sd(CL - F(s - L)) is smallest at L 0.5-1.0 s.
- The publish delay is p50 1,084 ms (p10 781, p90 1,479).
- So the report the engine re-sides on carries futures information about 1.6 s old.
- X179's nowcast adds F(t) - F(s), with the basis taken at the stamp. That basis is misaligned by about 0.5 s. This is
  the same order as the 0.45-s "futures move" window that defines the re-pegs.

**C3. Polymarket Perps is a live venue with public data. It is not the cluster's hedge venue, and its mark is not a
Chainlink nowcast.**

- The API at `api.perpetuals.polymarket.com/v1/info/*` is keyless:
  - BTC-USD is instrument 6, ETH 7, SOL 8.
  - `mark-history` at 1 s is historical, 1,000 points per request.
  - `tickers` carries the index price, which is "computed from Pyth, Chainlink Data Streams, Hyperliquid ... published
    every 200 ms". The index exists only live; `index?asset=BTC` returns no constituents.
  - `registered?address=` is public.
- Collateral is pUSD on Polygon, through deposit contract `0xDCa4af75705dbB50f62437045afF9921947917d2`.
- `registered` is false for the three proxies and for the three owner EOAs (0xd1f9bc03..., 0xb3f8b214..., 0x4acd0e52...).
  The three sweep EOAs were not checked; I only have their prefixes.
- 1-s mark against Chainlink and futures, 11-01 07:00-08:07, 4,000 s:
  - dMark moves with dBN at lag 0 (0.41).
  - It leads dCL by about 1 s (0.30).
  - Adding (Mark - CL) to a regression of the next 1-s Chainlink change on (dBN, BN - CL) leaves R² at 0.167. The mark
    is a fast Binance-like composite with no information on the next report beyond the futures.

**C4. No venue change matches the engine's October configuration steps.**

- October entries in the Predictions changelog:
  - 10-02: PolyBolt `price.crypto` defaults to Chainlink, and Pyth pins are added;
  - 10-07: data API `/v2/tokens`;
  - 10-21: PolyBolt equity status.
- `polymarket-client` releases (PyPI): 0.11.0 on 09-23 (PolyBolt streams), 0.12.0 on 10-01, 0.13.0 on 10-09
  (Chainlink or Pyth provider pins), 0.14.0 on 10-21 (order heartbeats with timeout cancel), 0.15.0 on 10-29
  (`takerDelayMs`).
- Nothing falls on the Monday k jumps (10-12, 10-19, 10-26), the 10-26 deep-bid step, the 10-30 15:00 noise onset or the
  11-01 instance split. C1 rules out a hold change across 10-31 / 11-01.
- This is the strong form of C4b, which ran one web search. The configuration steps remain operator or engine state.
- Two facts for the data plan:
  - RTDS, the source of every Chainlink recording here, is "legacy for reference prices" since 09-15.
  - The SDK notes put the removal of the legacy price topics "one month after" 0.11.0, that is about 10-23. They still
    work today.

**C5. The engine's sigma is not a Chainlink-sampled realised vol.** On the 12 BUILD and STUDY days with an endpoint
estimate (10-13..26), the Spearman correlation of the daily lag-1 autocorrelation of 1-s Chainlink changes with the
per-day best k (Binance stand-in) is 0.05 (p 0.88). Against the favourite share it is 0.08. A smoother stream (higher
autocorrelation) does not come with a lower k. Pyth is blocked as the brief says: Hermes `/v2/updates/price/latest` and
`/{ts}` and Benchmarks all return 401. My on-chain Pyth `PriceFeedUpdate` probes found 0 logs in 400 Arbitrum and 60 Base
blocks, so that route is unverified.

## Critique

1. **The 11-01 mandate of the brief has not been started for this strategy.**
   - state.json has no `dimensions` or `indicators` ledger, and E1-E7 are not in the catalog.
   - NOTES.md has no "Missing dimensions" section, and `residual_clustering` has never been run.
   - This wallet trades about 20 families at once, so E7 is required. It is also the cheapest way to tell whether the
     side and presence misses (the 11-01 split, the clean-block small-edge failure, the off-session ladder) share a
     second-level driver (a feed, a restart, the engine loop) or are independent per market.

2. **The venue's taker hold is the mechanism behind several results, and it has been misread (C1).**
   - Iteration 6 named a "~190-ms speed bump" (K8). Iteration 13's information panel then ruled out a venue delay from
     `seconds_delay = 0`, and X157 was framed on that premise: "(b) would need a non-public channel".
   - The hold is on (`itode`), it is 150 ms, and a held order cannot be canceled.
   - Every taker therefore commits about 190 ms before its match. A maker that re-prices within 150 ms of a public event
     meets every taker who reacted to the same event with newer information than that taker had.
   - That fits three measurements:
     - the cluster's reaction times (0-150 ms after a publish, 50-250 ms after a futures move);
     - 0 of 182 latency-taker fills (X28);
     - 39% of the takers who fill fresh posts signed before the post (iteration-13 C3; they were held).
   - The strict replays that fail the outcome bar (X106, X124, X154, X183; examiner: latency 2 s, trade-through fills at
     block seconds) cannot represent any of this. "The pairs need queue priority" is, at least in part, "the pairs need
     the hold".

3. **"The side configuration moves between blocks" mixes the quote with who takes it.**
   - A fill's side, measured at the match, is censored by the taker's information.
   - Automated takers (C1: 23-48% of trades by window) commit 190 ms ahead with a Binance view. The small-edge fills they
     choose should land on the outcome the futures favour, which is the side the cluster's 1.6-s-old report (C2) does
     not yet see.
   - That predicts what X178 found: inside bosona the large-edge side is unchanged (0.86 / 0.86), and the small-edge
     fills drop below chance in the hour with the most automated takers.
   - The posts are not censored. But the "still" posts are partly replenishment of rungs that takers consumed, so their
     side inherits the taker mix.
   - The center-slope drop (0.30 to 0.13) is also exposed to the errors-in-variables bias the RE noted. In the clean
     regime the true F - mid spread is small next to the error in our reconstructed F (C2 misalignment, unidentified
     sigma).
   - Before the 11-01 block is read as a new configuration, these two information effects (taker class, reference
     alignment) need to be measured. Neither has been.

4. **The live-input path to the exam depends on a deprecated feed (C4).**
   - The shared `rtds` feed and the RE's `dy_rtds` and `dv_rtds` read legacy RTDS price topics. Their planned removal is
     overdue.
   - If they are removed during a sealed block, `side_nowcast_match_clock`, `quote_unit_side` and the publish-clock
     blocks lose their input silently.
   - Legacy RTDS carries no `source` field. PolyBolt now stamps the vendor on every payload, and PolyBolt can serve
     Pyth or Chainlink. A vendor change inside the legacy feed would therefore be invisible in our recordings.

5. **Negative results that close doors (C3-C5):**
   - the Polymarket Perps mark, and Perps as a hedge venue for these six addresses;
   - venue changes as drivers of the October steps or the 11-01 shift;
   - a Chainlink-smoothing sigma.

   They should enter the ledger so no later iteration spends time on them. The Perps index (live only) and the sweep
   EOAs remain open; see I16-4.

## Proposals (ranked by the chance they close the gap)

### I16-1. The taker hold as the decision clock: a hold-aware strict replay, a leak test, and the two hold changes as natural experiments (new; strong form of K8, corrects the premise of X157, and the strong form of the replays X106 / X124 / X154 / X183)

- **Hypothesis.**
  - The cluster's fills are, to a large extent, held takers (committed ≥ 150 ms before the match) expiring against
    quotes it re-priced inside the hold.
  - Its edge, and its per-window PnL, is the information it gains during the hold (the Chainlink publish, the futures
    re-peg) over takers who cannot cancel.
  - A replay that models the hold reproduces per-window PnL. Replays at block seconds or 2-s latency cannot.
- **Why it fits.**
  - C1: the hold exists and is 150 ms.
  - The reaction times fit inside it: 0-150 ms after a publish (X44), 50-250 ms after a futures move (X10).
  - Latency takers never fill the cluster (0/182, X28). Takers who fill fresh posts were mostly already signed (39%,
    115 vs 63 in the 200 ms before or after the post).
  - Locked pairs carry the money (+11% VALIDATE), and every strict replay fails on queue priority.
- **Test.**
  1. Units: every taker order matched in BTC 5m/15m on the live development blocks (10-31 14:00-16:53 and 11-01
     07:00-12:00).
     - Calldata gives the taker's sign ms, side, token, limit and size.
     - The recorder's 'x' match ms is the hold expiry.
     - Arrival = sign + transport (the floor minus 150 ms, about 40 ms).
  2. Replay R8's frozen quote law (R7 price, posture side, half-spread 0.075, 500 x 2^k rungs) with a re-price 150 ms
     after each `dy_rtds` publish and each futures move of $2 or more.
     - A held taker fills the rule's rung if, at expiry, the rung is at or better than the taker's limit and at least as
       good as the other makers' best.
     - Other makers' depth is the full-depth book (`dm_clob_raw`) minus the cluster's fingerprinted orders.
     - At an equal price the rule queues behind the size that was there before its post.
  3. Pre-register three variants and score the same windows: (A) hold-aware; (B) the same law with a 2-s latency and
     takers arriving at the match; (C) A without the hold (takers arrive at the match).
     - Report Pearson and Spearman of per-window PnL against the wallet's, per wallet and pooled, and the share of the
       wallet's fills the rule reproduces (same window, outcome and price, within 0.5 s).
  4. Leak test, for branch (b) of X157: in the 0-190 ms before each match, count `dm_clob_raw` events on the token and
     its complement:
     - a `price_change` at the taker's limit with the taker's size;
     - a crossed or locked touch;
     - a `best_bid_ask` flicker.

     Compare the counts with placebo windows of the same length. Then run the cluster's post hazard against those events.
  5. Natural experiments: the hold changed at 08-17 11:00 UTC (250 to 50 ms) and 09-04 14:00 UTC (50 to 150 ms). Use the
     wallets' whole-history activity (fetched in iteration 12), Binance 1-s archives, and calldata samples (taker sign ms)
     for ±7 days around each change. Measure:
     - the cluster's BTC 5m maker markouts at 1, 5 and 30 s against Binance futures;
     - the share of its fills taken by takers at the hold floor (sign-to-block latency);
     - its favourite share and its daily fill count.

     Run a change-point test at the two hours against 20 placebo hours.
- **Data.** All live inputs are on disk:
  - `dm_clob_raw` and `dy_rtds` for 11-01;
  - `dx_*` for 10-31;
  - the shared `clob_crypto` trades;
  - calldata through `code4/calldata.py`: about 6,000 BTC transactions per hour, about 3 minutes per 1,000 at the polite
    rate; sample whole windows.

  History: activity, Binance archives, publicnode calldata.
- **Signature if true.**
  - (A) tracks per-window PnL at ≥ 0.5 Pearson and Spearman on both blocks, with ≥ 30 windows each and ≥ +0.2 over (B),
    while (C) falls back toward (B).
  - The markouts break at 08-17 11:00, worse at 50 ms, and recover after 09-04 14:00, with no break at the placebo hours.
  - If (A) stays below 0.3, the per-window PnL is queue and taker luck that the hold does not explain. Say so
    quantitatively.
  - If the leak test fires (≥ 3x placebo before ≥ 30% of matches), the held order is visible. That is an information
    source every fast maker shares, and it belongs in the rule and in the activity baseline.

### I16-2. Fill side by the taker's information class: is the 11-01 "regime" the counterparties? (new; strong form of X66, X81, X104 and X159 on the per-fill side, with the taker's commit time instead of its wallet type)

- **Hypothesis.**
  - Fills by automated takers (matched at the hold floor) land on the outcome the futures favour at commit, whatever the
    cluster's report says. Fills by slow takers follow the cluster's quote.
  - The posture's per-fill accuracy, by |F - mid| band, then depends on the automated share.
  - On that reading, the 11-01 small-edge collapse and the lot's half split are taker composition, not a new engine
    setting.
- **Why it fits.**
  - Inside one instance the large-edge side is unchanged across the blocks (0.86 / 0.86). The small-edge fills fell to
    0.44-0.58, and the large-edge share halved.
  - The automated share is highest in exactly the window where mo-money's fills were 0.125 on the report and 0.792 on
    the nowcast (C1). C2 shows the report is about 1.6 s behind the futures at publish, and an automated taker sees the
    futures.
  - Iteration-13 C3 already found prompt takers in flight. X66 and X159 measured populations by signature type, never by
    commit time.
- **Test.** Pre-register the classes before scoring:
  1. For every cluster BTC 5m/15m mid-band fill with a match ms (X178's sets: 10-31 14:00-16:53, n 1,728; 11-01
     07:00-12:00), fetch the fill transaction's calldata. Compute L = match ms - taker sign ms.
  2. Fixed classes: automated L ≤ 300 ms; mid 0.3-2 s; slow > 2 s. A second key: the taker address's 30-s markout
     sign on 10-31 14-16 only (BUILD), so each taker is labelled informed or uninformed.
  3. Per block, class and band (< 0.05, 0.05-0.1, ≥ 0.1), score the report posture (k 1.0), the nowcast, the cheaper
     token, and "the outcome the futures moved toward over the 500 ms before commit".
  4. Reweight 10-31's class-by-band accuracies by 11-01's class shares, and compare the result with 11-01's observed
     band accuracy.
  5. On the lot, use the same classes on b1_takers (sign ms already decoded), with L proxied by the in-block execution
     order and block time. The classes are coarser there; report the aggregate only on VALIDATE.
- **Data.**
  - About 2,100 fill transactions; 10-31's are in `calldata/live1031_*` and `liveall1031_*`, so only 11-01 needs
    fetching, about 3-5 minutes.
  - Recorder trades and books, `dy_rtds`, `dm_bnf`.
- **Signature if true.**
  - Slow-class accuracy holds within 0.03 across the blocks in every band with n ≥ 30.
  - Automated-class fills in the small-edge band follow the futures-move side at ≥ 0.75 and the report at ≤ 0.5 on both
    blocks.
  - The reweighted 10-31 accuracies reproduce 11-01 within 0.03.

  If it holds:
  - The counted side stays the quote's (posts and entries).
  - The per-fill gap gets a quantitative account: the share decided by takers who commit with fresher information.
  - "The configuration moves between blocks" is withdrawn.
  - The automated share is public at the block, so it is a legitimate reported conditioning variable; it is not a rule
    input that counts.

  If slow-class accuracy also falls on 11-01, the quote itself changed and the RE's reading stands, now with the
  counterparty confound measured.

### I16-3. E1 and E7: the dimension inventory, and residual synchrony across families and wallets, with the top clusters looked up in feed, venue and news records (required by the brief; not in the ledger)

- **Hypothesis.**
  - At least one of the unexplained parts is driven by a common second-level event rather than per-market state:
    - the 11-01 instance split;
    - the clean-block small-edge misses;
    - the off-session 62/250 ladder (region D at chance);
    - the 10-31 16:53 switch-off.
  - Candidates:
    - a feed gap or reconnect (an RTDS publish gap, a futures stream gap);
    - an engine pass or restart (salt-counter jumps);
    - a CLOB event (tick-size messages);
    - an operator action.
  - A per-instance driver shows as synchrony within one wallet's markets but not across wallets.
- **Why it fits.**
  - One engine posts 29% triplets on 10-31, yet only bosona runs the main ladder on 11-01 for 75-90 minutes. Mo-money
    rejoins at about 08:30 and almach and mo-money both start at 07:15:03 on the same second. Those are instance-level
    events at second precision.
  - The X89 switch study looked only at Chainlink runs near six switches.
  - The brief requires E7 for multi-market wallets, and its threshold (p ≤ 0.01, ratio ≥ 1.5) is designed to separate a
    common driver from shared busy minutes.
- **Test.**
  1. Write `dimensions` with the entries this panel adds:
     - PolyBolt (blocked: CLOB credentials; the engine's likely price socket);
     - legacy RTDS (have; deprecated, no vendor field);
     - the taker hold (have: `itode` and the changelog);
     - taker commit times (have: calldata);
     - the Perps index (have live, from now; mark history at 1 s);
     - Pyth (blocked, 401);
     - Perps accounts (checked: not registered).
  2. Out-of-fold misses per (market, second):
     - R8 side errors on cluster fills;
     - quote-unit misses on 11-01, meaning a pure 500 post on the non-posture outcome, or a predicted at-touch post
       absent within 300 ms;
     - R9 misses on the alt, hourly and 4h fills.

     Use GroupKFold over 2-hour blocks.
  3. Run `residual_clustering` with period_s 900 (5m + 15m), then 3,600 (with hourly) and 14,400 (with 4h), pooled and
     per wallet. For the off-session ladder use the lot's 00-12 UTC hours (STUDY case by case, VALIDATE aggregate).
  4. Look up the top 10 cluster seconds in:
     - `dy_rtds` publish gaps over 2 s and `dm_bnf` gaps over 1 s;
     - the `subs` feed (resubscriptions) and `clob_crypto` 'c' records;
     - salt-counter discontinuities in the cluster's calldata;
     - status.polymarket.com;
     - GDELT 15-min (bitcoin, crypto, polymarket), which is also E5 for the selection component.
- **Data.** All on disk or keyless. GDELT allows one request per 5 s.
- **Signature if true.**
  - Clusters at p ≤ 0.01 and ratio ≥ 1.5.
  - At least half of the top 10 coincide within 2 s with a named event of one class.
  - For an instance driver: synchrony within a wallet's markets but ratio ~1 across wallets.

  If no synchrony passes, the misses are per-market state (quote and taker). Record that as the E7 verdict, with the
  power of the test, so later iterations stop searching for a common driver.

### I16-4. Re-align the nowcast to the settlement stream's own lag, and record the Perps index as the one public licensed-feed composite not yet raced (strong form of X179 and X59; new source)

- **Hypothesis.**
  - The engine's between-publish reference is the last report moved by the futures increment since the time the
    report's value reflects (about s - 0.5 s, C2), not since its stamp.
  - Or the engine reads a licensed composite earlier than legacy RTDS, for which the Perps index (Pyth, Chainlink Data
    Streams and Hyperliquid, every 200 ms, published by Polymarket itself) is the public proxy.
  - Either one reduces the 0.5-1.6 s staleness that makes small-edge sides look random in the clean regime.
- **Why it fits.**
  - The nowcast is never worse than the report and adds +0.06-0.12 on the clean block (X179), with a basis misaligned
    by about 0.5 s (C2).
  - A quarter of the clean block's at-touch posts are futures re-pegs (0.89-0.96).
  - A credentialed engine would read PolyBolt rather than legacy RTDS (C4). Its latency relative to RTDS is unknown,
    because PolyBolt is blocked for us.
- **Test.**
  1. No new fitting. Rerun `code16/nowcast.py` with the basis F(s_i - L), L ∈ {0, 0.5, 0.75} s, chosen on 10-31 14-18
     (safe clock).
     - Score per hour on 11-01 07-12, on still posts and in the small-edge band (< 0.05).
     - Also score how well each L predicts the next report (an information-only check, no cluster data).
  2. Record `wss://ws.perpetuals.polymarket.com/v1/ws` `tickers::6/7/8` (index, mark, server ts) with `live.py`'s
     `Writer`:
     - hard stop 11-03 00:00;
     - under 60 MB disk and 50 MB memory;
     - entered in `live_lab`.
  3. On the 11-01 18-24 and 11-02 00-06 / 12-18 development blocks:
     - (a) cross-correlate 100-ms index changes with `dy_rtds` publishes and with futures moves;
     - (b) event-study the pure 500 post side against index changes in the gaps between publishes, with placebo shifts,
       against the futures-move rule.
- **Data.** `dy_rtds`, `dm_bnf` / `dx_bnf`, the rebuilt quote tables, the new Perps recording.
- **Signature if true.**
  - The aligned nowcast is at least +0.03 over L = 0 in every clean hour, and best at the L that best predicts the next
    report.
  - For the index: its changes lead RTDS reports by 300 ms or more, and the cluster's between-publish re-sides follow
    them at ≥ 0.75 within 300 ms (≥ 2x placebo, beyond the futures rule).

  Otherwise mark the Perps index `no_effect`, with its min_detectable_share, and keep the futures nowcast.

### I16-5. Keep the exam's Chainlink input alive, and make a silent vendor change detectable (data integrity; new; time-critical)

- **Hypothesis.** This is a data risk, not a model of the wallet. Legacy RTDS price topics can disappear or change vendor
  during a sealed block. Without a second path, the examiner's live-input blocks and the publish-clock units of the next
  exam cannot be scored. With one, they can, and a vendor change becomes a recorded operational event (A8).
- **Why it fits.**
  - C4: RTDS is legacy for reference prices, its planned removal date has passed, and it has no `source` field.
  - Every live side result, the nowcast and the publish unit rest on `rtds`, `dy_rtds` or `dv_rtds`, whose hard stops
    are 11-02 and 11-03 in any case.
- **Test.**
  1. Each hour, compare 60 stamps of `dy_rtds` BTC/ETH/SOL with the keyless `polymarket.com/api/crypto/crypto-price`
     values, on development hours only. Log the max |diff| and any stamp gap over 5 s.
  2. Confirm that `code/cl_source.py` falls back to the endpoint with the same point-in-time convention when the stream
     is empty. Smoke-test it with the stream file hidden.
  3. Add the Perps `tickers` recording (I16-4) as a third, independent path.
  4. Tell the user before the 11-02 / 11-03 hard stops which recorders need a successor run for the next exam window.
     Repeat the Windows clock resync request: the offset was 1.3 s at 09:26 UTC.
- **Data.** The endpoint, `dy_rtds`, Perps tickers.
- **Signature.**
  - Diffs under $0.01 while RTDS lives, and an endpoint-only `evaluate()` that matches the stream version on one
    development hour.
  - A vendor change shows up as a step in the diffs at one second.

## Ledger entries this panel's checks support (for the RE to record)

- **C3, Perps hedge venue:** `ruled_out` for the three proxies and the three owner EOAs (`registered` false). Open for
  the three sweep EOAs (full addresses in `code12` outputs).
- **C3, Perps mark as a Chainlink nowcast:** `no_effect` on 11-01 07:00-08:07 (R² 0.167 to 0.167).
- **C4, October venue changes as configuration drivers:** `ruled_out`, as the strong form of C4b (changelog and SDK
  release dates read in full).
- **C5, Chainlink-sampled RV as the engine's sigma:** `no_effect` on 12 BUILD and STUDY days (Spearman 0.05). The
  since-Monday estimator of `code11/k_since_restart.py` carries a self-reported epoch bug and has not been rerun. It is
  the remaining untested form of a running sigma.
- **C1, correction to iteration-13 C3 and X157:** a 150-ms taker hold (`itode: true`) exists, and the ~190-ms
  sign-to-match floor is hold plus transport. X157 stays open in the corrected form (I16-1, steps 4-5).
