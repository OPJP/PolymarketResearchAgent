# Panel after iteration 9: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 9 in full, iteration 8 and earlier by section),
state.json (catalog, components, latest statement), FINAL_RULE.md, EXAM.md (head) and the information panels of
iterations 7-8. I did not read `iter9_mechanics.md`, which was written in parallel.

Data I used, all development:

- the RE's per-fill side table `.cache/re/directional-maker/it9/side_D_1793448000_1793469600.parquet` (10-31 12-18, 2,244
  fills);
- Chainlink 1-s values from the RE's `code/cl_source.py`, recordings only, no fetch, `allow_sealed=False`;
- the cluster's cached activity (10-08..22) and `it9/act_*` (10-31 12-18);
- data-api activity and tapes for single hours of June, July and August 2026, through the cached polyrea adapters;
- footers and selected row groups of public pmxt order-book dumps for 2026-06-12, 06-16, 07-01, 07-10, 07-15..18, 07-22,
  07-28, 08-01, 08-05 and 08-08 (HTTP range reads, nothing stored except a 3-market extract);
- one `eth_getLogs` query on Arbitrum.

I did not read `.cache/live/sealed/`, any sealed block, any other strategy's workspace, or anything after 10-31 18:00. My
scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i9/`:
`rangefile.py` (HTTP range reader for parquet), `pmxt_footer.py`, `pmxt_probe.py`, `pmxt_join.py`, `pmxt_cov.py`,
`keccak.py`.

## What my checks found

**C1. There is a historical source for the unaggregated CLOB book. The iteration-7 panel ruled it out too early.**

The iteration-7 panel tried `archive.pmxt.dev`, the docs host, which still refuses connections, and wrote "no historical
book source". The data host answers.

- **What it is.** `https://r2v2.pmxt.dev/polymarket_orderbook_YYYY-MM-DDTHH.parquet` is one file per UTC hour, 300-500 MB,
  no auth. HEAD returns 200 from 2026-04-17 to 2026-08-10 00:00 UTC, and 404 from 08-10 06:00 onward and for every
  September and October hour I tried.
- **Schema** (read from the footer of 06-12T14, 83.7M rows in 80 row groups):
  - `timestamp_received`, `timestamp` (server ms), `market` (condition id), `event_type` (`book`, `price_change`,
    `last_trade_price`, `tick_size_change`), `asset_id`;
  - `bids` / `asks` (full-depth JSON on `book` rows);
  - `price`, `size` (the new aggregate size of the level), `side`, `best_bid`, `best_ask`, `fee_rate_bps`;
  - **`transaction_hash` on every trade**.

  So this is the CLOB market-channel stream that `dm_clob_raw` records: every price change with server ms, not throttled.
- **Cheap to read.** The files are sorted by market (row-group min/max statistics), so one market costs a few row groups:
  19 MB for 3 BTC 5m windows of one hour, ~70 MB for 12, with 8-11 columns read through range requests.
- **Coverage of the cluster's markets** (`pmxt_cov.py`; the cluster's own markets per hour from activity):

  | hour | BTC 5m | BTC 15m |
  | --- | --- | --- |
  | 06-12T14 | 0 of 10 | 0 of 4 |
  | 06-16T15 | 0 of 12 | 0 of 3 |
  | 07-01T13 | 0 of 11 | 0 of 4 |
  | 07-10T13 | 0 of 11 | 0 of 4 |
  | 07-15T13 | 1 of 12 | 0 of 4 |
  | 07-16T13 | **9 of 9** | 4 of 4 |
  | 07-17T13 | 12 of 12 | 4 of 4 |
  | 07-18T13 | 11 of 11 | 3 of 3 |
  | 07-22T13 | 11 of 11 | 3 of 3 |
  | 07-28T13 | 12 of 12 | 4 of 4 |
  | 08-01T02 | 7 of 7 | 5 of 5 |
  | 08-05T13 | 13 of 13 | 3 of 3 |
  | 08-08T20 | 10 of 10 | 4 of 4 |

  Before 07-16 the hourly and daily markets are covered and the short-lived 5m/15m windows are not. On 08-05 every family
  the cluster traded was covered: ETH/SOL/XRP/BNB/DOGE 5m and 15m, and hourly and daily.
- **About 24 days of full coverage** (07-16 to 08-10, roughly 590 hours and about 7,000 BTC 5m windows) by the
  timestamp-0 engine (after 06-22).
- **The cluster was active then.** Late June, mid July and early August hours have 180-350 trades per wallet-hour, about
  half in BTC 5m. Sizes look different (5 / 50 / 300 plus remainders, against 500 x 2^k in October).
- **The match clock** (`pmxt_join.py`, 07-15T13, the covered window):
  - 93% of the data-api tape's transactions and 87% of the cluster's are in the archive's `last_trade_price` events;
  - block second minus server match ms is 1.5 / 2.5 / 3.3 s (q10 / median / q90);
  - the server-minus-receive lag is 58 / 150 / 259 ms.

**C2. The Chainlink history beyond the endpoint's 30 days cannot be rebuilt from on-chain reports.**

- On Arbitrum, the Data Streams `ReportVerified` event (topic `0x58ca95...`, verifier `0x2237...fb83`) fired 36 times in
  10 minutes over 8 feeds, at most 1.4 per minute per feed. The BTC/USD stream was not among them.
- So no public chain carries a dense archive of the settlement stream.
- Polymarket's `crypto-price` endpoint, which the RE uses for historical Chainlink seconds, refuses dates older than 30
  days (NOTES iteration 8). **BUILD (10-09..22) starts to age out around 11-08 and the released lot around 11-22.** The RE
  holds only the stride-16 X43 sample of the lot plus the `cl_grid` cache (464 KB).

**C3. The historical side tests used Binance as the reference. Live, Binance is a poor stand-in for the posture.**

- H-VOL (`code9/vol_hist.py`) took S = Binance spot second b-3 and K = the Binance TWAP-60 strike.
- On the 10-31 fills the same posture with the Binance fair (`fair_bn`) scores 0.578, against 0.786 with Chainlink (per
  wallet 0.56-0.60 against 0.76-0.81).
- The Chainlink and Binance postures disagree on 42% of those fills (932 of 2,244).
- Region D, where the reference and the mid disagree on the favourite, is defined by the reference's sign against the
  strike, so a proxy reference also misclassifies the D/A split. That may be part of why region D scores 0.575 on the
  historical VALIDATE and 0.855 live.
- The H-VOL failure is therefore confounded twice: by the fill mix (the RE's finding) and by the reference (mine).

**C4. The side does not follow the Chainlink innovation, which rules out a simple "lean on the news" reading.**

- With sign(CL(T-1.432 s) - CL(T-1.432 s - k)) as the side:
  - all fills: 0.51 / 0.57 / 0.67 / 0.67 / 0.64 / 0.64 / 0.63 for k = 1 / 2 / 3 / 5 / 10 / 20 / 30 s;
  - region A: 0.48-0.64.
- R6 scores 0.786 on all fills and 0.762 in region A (Chainlink coverage of the needed seconds 81%).
- A hybrid (the reference's favourite in D, the 5-s innovation in A) scores 0.705.
- The level-based digital posture is the right family; the residual is not news timing.

**C5. Mo-money's deficit sits where the Chainlink and Binance postures disagree, and Binance does not fix it.**

- Where the two disagree, the Chainlink posture scores almach 0.807 (n 311), bosona 0.769 (268) and **mo-money 0.686
  (353)**. That is 43% of mo-money's fills.
- Blending the fairs, a x fair_CL + (1 - a) x fair_BN, peaks for mo-money at 0.770 (a = 0.9; 0.762 at a = 1). The deficit
  is not a Binance-weighted reference.
- Cluster-level inventory does not explain the side: buying the cluster's under-held side scores 0.27-0.32 in every wallet
  (it adds to the held side).
- A wallet's fill copies the side of another wallet's fill in the same window within 2 s 0.90-0.97 of the time (n
  199-223 per wallet). The per-wallet fills are not independent decisions; a taker sweeps several wallets' rungs.
- Weight the per-wallet replication condition by taker event, not by fill.

**C6. Scope of the shared recorder's families**

- The families the shared recorder covers (BTC/ETH/SOL 5m, 15m, 4h) hold at least 0.80 of the cluster's trades and dollars
  in 82% of the 60 development 6-h blocks of 10-08..22 with at least 30 trades.
- The worst blocks are weekend 06 UTC (min 0.46 of dollars) and weekday 00 and 06 (0.60-0.66).
- The missing part is the Binance-settled hourly and daily markets (median 5-10% of dollars) and XRP/BNB/DOGE (median about
  1%, sometimes more).
- On 10-31 12-18 the recorded families held 0.949 of trades and 0.954 of dollars.

## Critique

1. **Every quote-level and match-clock claim rests on about 6 hours of live data.** That covers the sigma question, the
   ladder state machine, the quote-bound vs taker-bound side, the presence ceiling of 0.80, mo-money's 500 pass and the
   strict replay. Several of them rest on the 2.4 h of the own raw recorder (for 15m, a LightGBM on 3 windows). Iteration
   9 shows what that costs: the live fills, the quote unit, the block clock and the cross-family test point in different
   directions on sigma, and nothing can be decided. A public archive of the same unaggregated CLOB stream covers 24 days
   of the timestamp-0 engine across every family it trades, including FOMC (07-29) and US payrolls (08-07). It was
   closed after one failed request to the docs host.
2. **The primary metric cannot pass on its own unit.** With the cluster's observed quote as an oracle, 10-s fill
   presence reaches 0.80 (iteration 8). Tuning fill presence cannot reach 0.85; only the quote unit ("whether it has an
   order resting", which the brief prefers) or print selection can. But the quote-unit label exists only in the RE's own
   raw recorder for the BTC books, and the slim exam recorder stops on 11-02 00:00. Unless the label can be computed from
   what the shared recorder writes in the sealed blocks, the examiner cannot score the unit that could pass.
3. **The historical side and sigma tests used a proxy reference** (C3), so "H-VOL fails" has two confounds. The data
   needed to redo it with the settlement stream itself disappears from the only source (the 30-day endpoint) from about
   11-08, and no chain archives it (C2).
4. **The next exam's blocks are weekend blocks.** There, the module state decides most of the presence variance: when
   BTC 5m is off, other traders still print, so the activity baseline is wrong exactly where a module predictor is right.
   Hourly/daily and XRP/BNB/DOGE matter there too. The module trigger has been studied on two weekends (since 10-16).
   The full history (June-October, about 19 weekends, two DST changes) and books that separate "off" from "quoting but
   not filled" have not been used.
5. **Per-wallet replication is computed per fill, but fills are not independent across wallets** (C5: 0.90-0.97 copy the
   sibling's side within 2 s). Mo-money's deficit concentrates where Chainlink and Binance disagree and is not a Binance
   blend. Its input is still unknown.

## Proposals (ranked by the chance they close the gap)

### I9-1. The pmxt archive: 24 days of the unaggregated CLOB stream and match clock for every market the cluster traded (new data source; strong form of X52, X64, X68, X71, X72 and X75)

- **Hypothesis.** The quote mechanism, the posture sigma and the fill ceiling can be identified on a sample about 100
  times larger than the 10-31 block, for the same engine family (timestamp 0, per-wallet salt counter). The unit that can
  pass is the quote, and a large sample shows whether public inputs predict it to at least 0.80 with a gain of at least
  0.05.
- **Why it fits.**
  - Iteration 9 could not identify sigma: the per-bin intervals span a factor of 16, the quote level and the fills point
    opposite ways, and the block clock is confounded.
  - X71 (state machine) and X64 (replay) are blocked on "the generator's level is not decodable" from 2.4 h.
  - The fill-presence ceiling (0.80) comes from 360 bins.
  - All of these are sample-size problems on an unaggregated book with server ms, which C1 provides.
- **Test.**
  1. **Version check** (about 1,000 cluster fills of 07-20..08-08, calldata via publicnode with `code4/calldata.py`):
     - timestamp, metadata and builder are 0;
     - per-wallet sequential salt and its rate;
     - rung sizes;
     - from the archive, the October fingerprints: posts about 95 ms after a trade, filled-order age about 0.7 s, 78% at
       the touch, the three wallets within 20 ms.

     If they match, July/August is the same engine with a different size schedule.
  2. **Reduce and label.**
     - Take 3 hours per day (12-15 and 20-23 UTC, plus 02-05 on weekends) for 07-16..08-09 into per-market parquet:
       server ms, asset, price, new size, side, best bid/ask, tx hash.
     - Derive level deltas.
     - Label the cluster-class adds at the touch, confirmed by joining each filled order's calldata (original size,
       price) to its add 0.05-3 s before the `last_trade_price` with the same tx hash.
  3. **Pre-register** fit 07-16..31 and score 08-01..09:
     - quote-unit AUC from public inputs (Binance 1-s and futures aggTrades, the Gamma strike, the book excluding
       cluster-class levels, the clock) against the activity baseline;
     - the fill-presence AUC with the quote as an oracle, over thousands of windows;
     - per-print selection with the quote known.
  4. **Sigma at the quote level** across about 100 burst episodes and the scheduled shocks (FOMC statement 07-29 18:00
     UTC and US payrolls 08-07 12:30 UTC; check both against A6):
     - which estimator puts the at-touch 500-equivalent on the side the engine posts in region A;
     - the reference is Binance anchored to each window's `priceToBeat` (C3: use it for A/D only where |x| exceeds the
       basis uncertainty).
  5. **Strict-fill replay (X64)** of the frozen quote model through the recorded takers, with queue position from the
     level sizes. Report the per-window PnL correlation against the wallets on 08-01..09.
  6. **Module schedule** with quoting visible: the 4 weekends 07-18/19 .. 08-08/09 (feeds I9-3).
- **Data.**
  - r2v2.pmxt.dev hourly files, range-read only the row groups and columns needed (`rangefile.py` in my scratchpad
    works). About 70 x 66 hours ≈ 4.6 GB of transfer, spread over time on the shared line; reduce at once, keep under 0.5
    GB, store no raw dumps.
  - Data-api tapes and activity (cached adapters), calldata (publicnode), Binance aggTrades archives.
- **Signature if true.**
  - The July engine shows the October fingerprints.
  - The quote-unit AUC from public inputs is at least 0.80, with a gain of at least 0.05 over activity (2-h block
    bootstrap lower bound > 0) on 08-01..09.
  - The fill-presence oracle stays near 0.80. That proves the fill unit cannot pass and justifies pre-registering the
    quote unit as primary (it must then also be examinable: I9-2).
  - One sigma family fits the region-A quote side through FOMC/NFP.
  - If the fingerprints differ (another version), use July/August only for mechanism (ladder law, queue, replay
    calibration) and say so.

### I9-2. Make the quote unit examinable in the sealed blocks, and record the families the shared recorder misses (new; the condition for any quote-unit target)

- **Hypothesis.** The cluster-class quote at the touch can be labelled from the shared recorder's throttled top-10 `q`
  records (every 200 ms at most, plus full books every 30 s) well enough for the examiner to score the quote unit on
  every sealed block since 10-31. The scope gap on weekend blocks then closes only if the missing families are recorded
  too.
- **Why it fits.**
  - Critique 2: the passable unit has no examinable label.
  - C6: the recorded families miss 0.80 in 18% of blocks (worst 0.46 of dollars), from hourly/daily and XRP/BNB/DOGE.
  - examrec (BTC only) stops on 11-02 00:00.
- **Test.**
  1. On 10-31 14:04-16:30 (development), compute the label "a +500 change at the best level within one `q` interval" from
     the shared recorder only. Compare it per second with the raw-recorder label (precision, recall, and the quote-unit
     AUC of the frozen public model under each label).
  2. On pmxt July, throttle the unaggregated stream to 200 ms top-10 in software and measure the loss over 24 days.
  3. If recall is below about 0.9, start a reduced recorder with the shared `Writer` at the next development boundary
     (11-01 06:00 UTC), with a hard stop, under 100 MB of memory and 300 MB of disk:
     - price changes within ±5 c of the touch, plus every trade;
     - all crypto Up/Down families the cluster trades, including XRP/BNB/DOGE and the Binance-settled hourly/daily
       markets;
     - the RTDS Chainlink symbols the shared recorder skips (xrp and others, if published).

     Record it in `state.json` `live_lab`.
- **Data.** Shared recorder, own raw recorder, pmxt.
- **Signature if true.** The throttled label agrees with the raw one at recall and precision of at least 0.9, and the
  quote-unit AUC under both labels is within 0.01. The universe covered by recorded families reaches 100% of 6-h blocks.
  Otherwise the reduced recorder is the only route, and every block it misses is lost for the quote unit.

### I9-3. Module state from public triggers and the operator's clock, on the full history (strong form of X9, X57, X70 and X83)

- **Hypothesis.** BTC 5m/15m on/off is set by a human operator on a local-time schedule (weekend evenings), plus ad-hoc
  breaks after visible public-data trouble, such as the Chainlink 1-s noise regime and a large Chainlink-CEX divergence,
  rather than by own PnL alone. A public module-state predictor is the largest presence gain available in weekend blocks,
  because the activity baseline cannot see that the cluster is off.
- **Why it fits.**
  - Every long off-run starts Fri-Sun 16:35-18:30 ET (5 of 5 since 10-16).
  - The two ad-hoc restarts after 10-31 16:53 were sequential, 40 s apart, one engine left running: an operator.
  - 10-31 is the first day of the Chainlink noise regime.
  - The gate has been fitted on 2 weekends only (AUC 0.68).
  - On 10-31 00-06 BTC 5m presence was 0.679 against 0.695 for activity, the pattern expected when off-windows are
    negatives that activity calls likely.
- **Test.**
  1. On/off runs per family from the activity back to the first trade (June-October, about 19 weekends), and from pmxt
     books 07-16..08-10, where cluster-class adds show "quoting but not filled" apart from "off".
  2. Fit the switch-time distribution in UTC, US Eastern, Central European and UTC+8. The EU DST change (10-25, already in
     the data) and the US change (11-01; X57, development blocks from 11-02) each shift the UTC times by one hour in
     exactly one zone.
  3. For every October switch, measure the Chainlink-Binance divergence and the Chainlink 1-s noise (lag-1
     autocorrelation) over the preceding 2 h. Use the crypto-price endpoint at a 5-s stride, still inside its 30-day
     window, against the same hours of non-switch days.
  4. The owner EOAs (Safe owners, C1): times of their manual Polygon transactions as a human-presence clock, reported as
     operator state and kept out of the no-own-state metrics.
  5. Freeze a local-time gate plus a public data-quality trigger, and score window presence on the union with and without
     it (VALIDATE aggregate, then 11-01 06-12).
- **Data.** Data-api activity (cached adapter), pmxt, the crypto-price endpoint, Binance archives, Polygon RPC.
- **Signature if true.**
  - Off-switch times concentrate in one local-time window, shifted by exactly 1 h UTC after that zone's DST date.
  - Ad-hoc switches follow a data-quality excursion within minutes; calendar switches do not.
  - Union presence in weekend blocks gains at least 0.05 over activity with the gate.
  - If switch times are uniform in local time and unrelated to public signals, the module state is own state (PnL), and
    weekend scope must be met through the other families.

### I9-4. Save the settlement stream for BUILD and the lot before it expires, and redo the historical posture with the real reference (time-critical; strong form of X43, X74 and the H-VOL replications)

- **Hypothesis.** On the historical block clock the posture, region D and the sigma comparison look weak partly because
  S and K came from Binance (C3). With the Chainlink value at each fill second, the volatility-free part replicates near
  the live 0.855, and the H-VOL / H-VOL15 contrast changes.
- **Why it fits.**
  - Live, Binance scores 0.578 against Chainlink's 0.786 on the same fills.
  - Region D scores 0.575 on VALIDATE against 0.855 live.
  - The only source (the 30-day endpoint) loses 10-09 around 11-08 and the lot from 11-22, and C2 shows no chain
    substitute.
- **Test.**
  1. Before 11-08, fetch the Chainlink value at T-1 s and T-2 s for every unique cluster BTC 5m and 15m fill second of
     BUILD and the lot. That is about 60-70k unique seconds, about 12 h at the endpoint's ~1.5 requests/s, run detached
     at the polite limit, with priority to the fill seconds of 10-09..16.
  2. Re-run `vol_hist.py` and the region D/A split with S = Chainlink and K = Gamma `priceToBeat`. The confirmation is
     already pre-registered; keep it unchanged.
  3. Keep the cache for `evaluate()` (`FETCH_CL` otherwise fails on these dates after the horizon).
- **Data.** `polymarket.com/api/crypto/crypto-price` (verified by the RE), the existing fill tables.
- **Signature if true.** On BUILD+STUDY and on VALIDATE, region D with the Chainlink reference is at least 0.75 and the
  frozen-vs-slow ordering matches the quote level (I9-1). If region D stays near 0.58, the fill mix (complement mints)
  explains the historical side and the block clock is retired as a side measurement.

### I9-5. Mo-money's third input (strong form of X76)

- **Hypothesis.** Mo-money's 500 pass reads a reference that is neither a delayed Chainlink nor a Binance blend (C5). The
  candidates:
  - (a) the RTDS `crypto_prices` Binance relay (Polymarket's own relay, X59; `dz_rtdsbn` exists);
  - (b) the RTDS Chainlink TWAP-60 topic (0.577 pooled, never scored per wallet);
  - (c) another market's book (the BTC 15m mid for 5m rungs);
  - (d) the complement token's best ask (pair-sum anchoring).
- **Why it fits.**
  - It scores 0.686 where Chainlink and Binance disagree (others 0.77-0.81).
  - It is off the posture already at the add (0.646).
  - It is flat across Chainlink delays.
  - Its other sizes score 0.851, so the input belongs to one rung pass, not to the wallet.
- **Test.** For mo-money's exact-500 adds (iteration-6 confirmed orders, 10-31 14:04-16:13), compare the posture at the add
  time under each candidate reference with the same for almach and bosona's 500s. Then score the best candidate on
  11-01 06-12 (pre-registered), per taker event (C5).
- **Data.** `dm_rtds` / `dy_rtds` TWAP topic, `dz_rtdsbn` (development blocks), the shared and own book recordings.
- **Signature if true.** One candidate lifts mo-money's 500s to at least 0.80 at the add while changing the other wallets'
  500s by at most 0.02. If none does, freeze mo-money's 500 pass as a separate, pre-registered component.

## Notes for the RE

- **pmxt.**
  - The docs host `archive.pmxt.dev` refuses connections; use `r2v2.pmxt.dev` directly.
  - A missing hour is a 404 (no events), not an error.
  - The `size` on `price_change` is the new level size, not a delta.
  - Each event in a market appears for its `asset_id`; `last_trade_price` carries the tx hash.
  - My range reader (`rangefile.py`) plus row-group pruning on `market` statistics keeps memory under about 300 MB.
- **Ruled out by my checks.**
  - An on-chain archive of Data Streams reports as a Chainlink history: Arbitrum density is at most 1.4 per minute per
    feed and BTC/USD was absent in 10 minutes.
  - The side as a Chainlink innovation sign (C4).
  - Cluster-level inventory balancing as mo-money's (or anyone's) side rule (C5).
- **Telonex** (Polymarket historical book files) needs an account, which may not be created. Not used.

Sources for the archive facts: [pmxt archive](https://archive.pmxt.dev/), [v2 data overview](https://archive.pmxt.dev/docs/v2-data-overview),
[Telonex datasets](https://telonex.io/datasets), [Chainlink Data Streams feed ids and verifier addresses](https://docs.chain.link/data-streams/stream-ids).
