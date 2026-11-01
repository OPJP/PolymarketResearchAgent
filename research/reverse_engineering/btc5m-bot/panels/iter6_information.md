# Panel, iteration 6: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained. Which data would most
sharply separate the leading explanations, and how can it be fetched on this laptop?

All my checks used development data only:
- the 10-31 14:15-15:10 development block, read through `live_lab.recs` (which calls `iter_live`). That covers the
  investigator's `btc5m_venues` / `btc5m_venues2` feeds, the shared `clob_crypto` match records and
  `post/own6_*.parquet`;
- data-api activity for DS over 15:03-15:09;
- calldata of 700 non-cluster BTC 5m taker txs from 14:50-15:03, plus the cluster's own;
- the OKX tick-by-tick book archive for 2026-10-21 (VALIDATE, before H), streamed and reduced in memory;
- `val_side_it5book.parquet` and `val_decision_presence.parquet`;
- 2-KB ranged GETs of Tardis free files for 2026-10-01.

Nothing raw was stored and no sealed unit was touched. I did not read other agents' `dm_*` feeds. The scripts are in my
scratchpad, `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`lagmode.py`, `lagmode_10ms.py`, `coracer_clock.py`, `okx_tbt_check.py`, `clock_degrade.py` and `clock_degrade_nat.py`.

## Critique

1. **The trigger was decoded live, but nothing will let it be examined.**
   - `rec_lab6.py` drops every message while the calendar block is sealed. Its docstring says "nothing sealed is ever
     written by this process", and line 344 only ever writes to `dev`.
   - The shared recorder does not record venue quotes at all.
   - So no sealed block, past or future, holds the inputs of the microprice vote: the sized top of book of
     Binance, Bybit, OKX and Hyperliquid, and the unthrottled near-touch Polymarket book.
   - The brief's design expects the opposite. A lab recorder "uses tools/live.py's Writer (so it files records the same
     way)", the Writer files sealed-block records into `.cache/live/sealed/`, and the examiner reads them with
     `allow_sealed=True`. Writing through the Writer is not opening the sealed folder.
   - The first future exam takes the sealed blocks since 10-31 00:00. That means 10-31 06-12 (already lost for the
     lab feeds), then 10-31 18-24 (it starts at 18:00 UTC today), 11-01 00-06 and so on. Every sealed hour that passes
     unrecorded is lost for good.
   - The 86% component, and any replay-based PnL, can only ever be exam-verified on these blocks. h1 and h2 cannot
     carry it (point 2).
2. **The historical side gap is the decision clock, not missing information, and the clock cannot be recovered.**
   I measured it directly on the same 412 live taker matches and the same ten quote series (`clock_degrade.py`):

   | Vote window | Coverage | Agreement |
   |---|---|---|
   | Match ms, [m-600, m-100) (frozen) | 91% | 84.8% |
   | Block timestamp, [B-3.5, B-1.0) s | 96% | **76.8%** |
   | Block timestamp, [B-3.0, B-1.3) s | 94% | 75.7% |
   | Placebo | 81% | 48.8% |

   The block-clock figure is exactly the historical side model's 76.7-77.2%. Four ways to recover a sub-second clock
   historically all fail:
   - **data-api timestamps** equal the block timestamp in 247 of 247 DS trades, so they are no match clock.
   - **Co-racers' signing ms** (the strong form of X12/X22): 700 non-cluster takers have a sign-to-match latency that is
     bimodal (10% 203 ms, median 998 ms, 75% 3.7 s). As an anchor in the same block ±1 it is within 200 ms of the
     cluster's match for 13.7% of matches, against 20.8% for "block − 2.2 s". Learned "clock wallets" with tight
     latency do no better: 11.5% vs 19.2% on held-out matches.
   - **The signing ms of consumed maker orders**, used as a lower bound, is violated in 9% of txs. Even when the bound
     is under 300 ms wide, its midpoint is within 200 ms of the match only 19.6% of the time. Signing stamps come from
     unsynchronized client clocks.
   - **The continuous block production time** from the chain-clock fit does not tighten the spread: IQR 844 ms against
     850 ms for the integer timestamp. The spread is the relayer's queueing, not rounding.
3. **More historical quote archives will not raise the block-second side.** OKX publishes a public tick-by-tick book
   history (new, see proposal 1). On VALIDATE 10-21 the OKX ETH-USDT-SWAP L1 microprice moved over [s-3, s-1) s in 90%
   of one-sided seconds and agreed 71.1%. Where the frozen it5 model is wrong, it agrees only 32.5%: it carries the same
   information as the model. A stacked logistic regression fitted on the first half of the day and tested on the second
   gives 75.91% → 75.98% (n = 8,007). The Bybit ETH book's +0.5 points looks like the ceiling of this route. Further
   historical feeds for the side model are effort with no return; the h1/h2 account should state the clock limit with
   the numbers above.
4. **Latency fingerprint, small n.**
   - Against placebo instants, the net toward-side microprice ticks before the match are about zero in the 150-230 ms
     bins. They peak at 240-300 ms for Binance USD-M ETH/BTC and OKX ETH (+0.48 per match in the 250-300 ms bin for
     Binance ETH), at 200-250 ms for Bybit, and are flat for Hyperliquid (`lagmode*.py`).
   - So the bot cannot react to anything in the last ~230 ms. Polymarket book events inside that interval (for example
     "ask rose in the last 300 ms", 36%) are co-reactions of the crowd, not causes.
   - Narrowing the vote to [m-600, m-240) gives 84.0% vs 84.8%, so the frozen window is not harmed.
   - Hyperliquid follows the others. When it moved alone it agreed 57-63% (n = 24-61), and with Hyperliquid flat the
     other series agreed 85-91%.
   - No single venue is the sole input: with Binance USD-M ETH flat, the others still agree 68% (n = 97). The numbers
     are small.
5. **All live evidence comes from one Saturday afternoon.** It is 782 matches, 204 with quotes, and a replication of
   162. VALIDATE is mostly weekdays. In US hours (Monday 11-02 12-18 is a development block) the Coinbase and CME-driven
   flow may lead, and none of the live results has been checked there.
6. **Outages are not worth chasing for presence.** Oracle removal of the 100 zero-fill VALIDATE windows (5% of cells)
   lifts the rule 0.9132 → 0.9167 and the pure baseline 0.8781 → 0.8813, so the gain is unchanged. C4b/A8 outage
   prediction is worth at most about +0.003 AUC.
7. **The "0.5 PnL correlation is unreachable by construction" argument is untested.** It rests on siblings that compete
   for the same liquidity: DS takes the touch first and GF gets the leftover or rests. A replica replayed on the
   recorded pre-match book does not compete with the bot, so the sibling ceiling need not apply. That needs the
   unthrottled book in the exam blocks, which point 1 says is not being recorded.

## Proposals (ranked by chance of closing the gap)

### 1. Record the exam inputs through the sealed blocks, and add an archive route the examiner can rebuild (new data source plus a recording fix)

- **Hypothesis.** The decoded trigger can pass a sealed exam only on future blocks, and only if its inputs exist there.
  The inputs are the venue sized top of book, the Polymarket near-touch book and the match ms. Two sources make that
  possible:
  - the investigator's own recorder, writing sealed blocks through the Writer;
  - public archives that cover any future day. These are the OKX tick-by-tick books and the Bybit ob200 archive. They
    also cover the already-lost 10-31 06-12 block.
- **Why it fits.** Critique points 1 and 2. On h1/h2 the 86% component falls to the block-clock 77%. The only exam where
  it can show is a future block, and today nothing is recorded there.
- **New source, verified from this laptop.** OKX `GET https://www.okx.com/api/v5/public/market-data-history`, no key:
  - `module=6` (path `public_tbt`) is a tick-by-tick multi-level book, CSV with `timeMs`, `exchTimeMs`,
    `bid_k_px/qty/ordCnt` and `ask_k_px/qty/ordCnt`, at about 10 ms per update. File sizes: ETH-USDT-SWAP 490 MB on
    10-15 (6.59 M rows and 3.39 M L1 microprice changes on 10-21), BTC-USDT-SWAP 344 MB and BTC-USDT spot 234 MB on
    10-21.
  - `module=4` is a 400-level L2 daily tar.gz (602 MB for ETH-USDT-SWAP on 10-15).
  - Parameters: `instType=SWAP&instFamilyList=ETH-USDT&dateAggrType=daily&begin=<ms>&end=<ms>` (`instIdList` for SPOT).
    Days are UTC. The download URLs are signed Alibaba OSS links that expire in about 10 minutes.
- **Test.**
  1. Before 18:00 UTC today, restart the v2 recorder through the Writer with sealed writing enabled. Never read the
     sealed folder; check it only through the status counts.
  2. Keep it under the brief's 300 MB.
     - The v2 recorder writes about 12.9 MB/h (8.3 MB in 38.7 min), and about 50 h remain to its hard stop, which would
       be about 640 MB.
     - Keep the series that have no public archive: Binance USD-M (and spot) bookTicker ETH/BTC, every size change,
       coalesced to 25-50 ms (about 27% of venue records now, ≈ 2 MB/h).
     - Keep the Polymarket near-touch book within 1 c, with trades and tx hashes (≈ 3 MB/h).
     - Keep OKX and Bybit live only in development blocks, since they are archived.
     - The total is ≈ 5 MB/h, ≈ 250 MB.
     - Alternatively, run a second, minimal "exam-input" recorder with its own budget. Record it in `live_lab`.
  3. On the 10-31 12-18 and 11-01 06-12 development blocks, measure the archived subset alone:
     - the vote of OKX tbt (10 ms) plus Bybit ob200 (100 ms), with Binance aggTrades and OKX trades at exchange ms, at
       the recorded match ms: its coverage and agreement against the full ten-series vote;
     - whether the archived OKX L1 equals the live `bbo-tbt` L1 record by record at exchange ms.
     - Mixed-day files after T0 hold sealed hours. Stream them and discard rows by the `exchTimeMs` field before
       parsing anything else; never keep or count sealed rows.
  4. In `final_rule.evaluate`:
     - use the live vote where `btc5m_venues*` exists;
     - otherwise fall back to the archive vote (OKX + Bybit + trades) with the shared `clob_crypto` match ms;
     - fall back to the block-second model where neither exists (h1/h2).
- **Data.** The investigator's recorder (Writer, sealed on), the OKX `market-data-history` modules 6 and 4, the Bybit
  ob200 archive (already in `bybit_ob.py`) and the shared `clob_crypto` trade records with server ms.
- **Signature if true.**
  - Status counts show sealed-folder records for 10-31 18-24 onward.
  - On development blocks the archived-only vote reaches at least 82% agreement at 85% or more coverage, against
    84-86% for the full vote.
  - Archive and live OKX L1 agree in at least 99% of records.
  - The examiner can then score the decision-level side and price on at least 12 sealed hours. If the archived-only
    vote falls well below the full vote, Binance quotes are essential, and recording them in sealed blocks is the only
    route.

### 2. A decision-level replay replica on the recorded book, to test the "PnL ceiling by construction" claim (strong form of D3)

- **Hypothesis.** Per-window PnL is about net position times outcome (corr 0.885). A replica that decides on the same
  ticks and fills against the recorded pre-match book (the touch and its size) would take the same liquidity the pooled
  cluster took. Its per-window PnL would then track the pooled cluster far above the sibling level of 0.0-0.2. The
  siblings decorrelate because they race each other (DS first in 80%; event size 1 in 76%), not because the per-window
  PnL is unpredictable.
- **Why it fits.**
  - The frozen strict-fill replica (0.18) had latency of at least 2 s and tape-only liquidity, so it never sees the
    bot's fills.
  - The live price rule puts the touch 50 ms before the match within one tick for 93%.
  - The vote covers 90% of decisions at 84-86%.
- **Test.**
  1. On the development blocks with `btc5m_clob_raw*` (10-31 14:13-18:00, then 11-01 06-12, 18-24 and 11-02 00-06,
     about 200+ windows), simulate:
     - at each vote event (decision time = tick + 240 ms), buy the outcome at the recorded touch;
     - take the size from the day's menu, capped by the recorded touch size;
     - let the remainder rest at the limit and fill only when later recorded trades print through it;
     - hold to resolution and add the 50% fee rebate.
  2. Compute the per-window Pearson and Spearman correlation with the pooled cluster's realized PnL from on-chain fills.
     Report a second version with the brief's latency of at least 2 s.
  3. Compare against the sibling matrix, and against an oracle replica that copies the cluster's own decision times
     (the ceiling of the information).
- **Data.** The recorded unthrottled book and venue quotes (development blocks now, sealed blocks after proposal 1),
  cluster fills from `fetch_dev_post.py`, and outcomes.
- **Signature if true.**
  - Replica-to-cluster per-window correlation of 0.5 or more on development blocks (the oracle-time replica higher still).
  - It collapses toward 0.2 at a latency of 2 s.
  - That settles whether the PnL condition is reachable at all, and with which latency definition. If even the
    oracle-time replica stays below 0.4, the ceiling claim holds with a measured number.

### 3. The Tardis 2026-11-01 free sample: every venue, tick by tick, aligned to recorded match ms (new data; strong form of the 10-01 test)

- **Hypothesis.** The quiet matches that are still wrong or uncovered (live: 14-16% wrong, 9-10% uncovered; quiet
  77-84%) are triggered by a series the lab never recorded. Candidates:
  - USDC-margined perps;
  - COIN-M inverse perps;
  - FDUSD/USDC spot books;
  - Bitget, Gate, Deribit or BitMEX;
  - book depth beyond L1 (queue depletion at L2-L5);
  - liquidation prints;
  - un-coalesced bookTicker (the v2 recorder coalesces to 30 ms).
- **Why it fits.**
  - The investigator measured 10 quote series and 8 trade series. Price discovery is spread over venues (iteration 3),
    and no single venue is the sole input (critique 4).
  - The 10-01 Tardis test ran at block-second resolution, which proposal 3's numbers show cannot separate inputs.
  - 11-01 is the first free day that overlaps recorded match ms: 06-12 and 18-24 UTC are development blocks for
    btc5m-bot.
- **Verified access.** Ranged GETs of `https://datasets.tardis.dev/v1/<exchange>/<type>/2026/10/01/<symbol>.csv.gz`
  return 206 without a key for:
  - `binance-futures` book_ticker BTCUSDC and ETHUSDC;
  - `binance` book_ticker BTCFDUSD and BTCUSDC;
  - `binance-delivery` book_ticker BTCUSD_PERP;
  - `hyperliquid` quotes BTC;
  - `bitget-futures` book_ticker BTCUSDT;
  - `coinbase` quotes BTC-USD;
  - `binance-futures` liquidations.

  HEAD requests return 404, so use GET.
- **Test.**
  1. When the 11-01 files appear, likely early on 11-02, stream each needed series. Discard rows whose timestamp is in
     the sealed blocks (00-06, 12-18) before parsing anything else, keep only the 06-12 and 18-24 rows reduced to
     microprice changes, and close the connection at the last needed hour.
  2. For each cluster taker match (shared `clob_crypto` and `clob_raw2` server ms):
     - draw each series' net toward-side intensity profile in 10-ms lag bins against placebo;
     - measure the agreement of each series where the frozen vote is wrong or abstains;
     - fit a sparse logistic regression over all series on [m-600, m-240) on 06-12 and test it on 18-24.
- **Data.** The Tardis free first-of-month files (trades, book_ticker or quotes, incremental_book_L2, liquidations,
  derivative_ticker) and the recorded match ms.
- **Signature if true.**
  - A series (or L2 queue feature) with a sharp onset near the 240 ms reaction latency explains at least 50% of the
    currently wrong or uncovered quiet matches at 75% or more agreement.
  - Decision-level side reaches 90% or more on 18-24.
  - That series then joins the proposal-1 recording list.
- **If false.** The measured statement "no venue among N moved in [m-600, m-240) before X% of quiet matches" is the
  quantitative information-wall account for the residual.

### 4. Make the clock limit the formal historical account, per wallet, and stop adding historical side features (strong form of X12/X22, now measured negative)

- **Hypothesis.** On h1/h2 every component that depends on the sub-second trigger is capped by the block clock.
  - Side: about 77% on the same data that gives 85% at match ms.
  - XM's side condition (one-sided in 24.3% of windows) cannot reach 80% historically from any public data.
  - The clock cannot be recovered (critique 2).
- **Why it fits.** The degraded live vote at the block clock (76.8%) equals the historical side model (76.7-77.2%). OKX
  tick data adds +0.07 points at block seconds.
- **Test.**
  1. Freeze `clock_degrade.py` as a ledger item.
  2. On every development block run, per wallet (DS, GF, XM) and pooled:
     - the vote at match ms;
     - the vote at the block clock;
     - the historical block-second side model applied to the same matches.
  3. Bootstrap by window.
  4. For presence, run the same comparison with a decision-level hazard at match ms against the block-second
     presence model.
  5. If the block-clock vote beats the historical model by more than 3 points on any wallet, the historical pipeline is
     losing information, and the fix is a feature change, not new data: for example Bybit ob200 at native resolution
     and lag-mixture windows over [B-3.3, B-1.2] s.
- **Data.** Existing live recordings, block timestamps and historical predictions.
- **Signature if true.**
  - The block-clock vote lands within ±1.5 points of the historical model on every block and wallet.
  - The FINAL_RULE account for h1/h2 can then say exactly where the unexplained side comes from: 8 points of blur from
    a 1.3-3.2 s relayer queue.
  - Effort moves to proposals 1-3.

### 5. Calibrate the exchange clocks and use the reaction latency to name the bot's input feed and decision horizon (new; small-n evidence in critique 4)

- **Hypothesis.** The bot's tick-to-match latency is fixed for its input feed. Comparing per-venue onsets on calibrated
  clocks identifies:
  - the feed it listens to first;
  - where it is hosted (Binance in Tokyo, OKX in Hong Kong, Bybit in Singapore, Coinbase in us-east);
  - the exact decision horizon the exam rule should use.
- **Why it fits.**
  - The onsets are at 240-300 ms for Binance and OKX and at 200-250 ms for Bybit, which may be a timestamp-semantics
    effect (Bybit `ts` push time vs `cts` matching time).
  - Hyperliquid is a follower.
  - The laptop clock runs about 1.1-1.2 s off (minimum receive minus stamp), so only exchange-to-exchange comparisons
    are meaningful.
- **Test.**
  1. In the next development block, log the server time of Binance `/fapi/v1/time`, OKX `/api/v5/public/time` and
     Bybit `/v5/market/time` every 10 s, with minimum-RTT filtering, to bound the inter-exchange offsets.
  2. Record Bybit `cts` and OKX `ts` alongside the push times.
  3. Redo the 10-ms onset profiles with bootstrap CIs on at least 1,500 matches from three blocks, including the Monday
     12-18 US-hours block.
  4. Natural experiment: compare the agreement of matches where only one venue ticked in [m-600, m-240) (n ≥ 50 per
     venue).
- **Data.** Existing recorders plus three REST time endpoints (a few bytes every 10 s).
- **Signature if true.**
  - One venue's onset is at least 20 ms earlier and narrower than the others on calibrated clocks.
  - Its "moved alone" matches agree at least 85% while the others' agree at most 65%.
  - The exam rule can then be a single-feed rule on [m-W, m-L) with measured L.
- **If false.** A broad multi-venue onset supports a composite (median-of-venues) fair value, which the lab should
  then record as a composite.

## Not proposed (measured here, low value)

- **Co-racer and maker signing ms as a historical clock (X12/X22).** Worse than a constant (critique 2).
- **More historical quote archives for the block-second side model.** OKX tbt adds +0.07 points (critique 3).
- **Outage prediction (A8/C4b) for presence.** At most +0.003 AUC, and the gain is unchanged (critique 6).
