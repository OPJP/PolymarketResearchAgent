# Panel, iteration 14: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

Written 11-01 ~05:35 UTC.

## Data used for my checks

I used development data only. Nothing was opened from `.cache/live/sealed/`, from any capture day file at or after H, or from any other
strategy's workspace. I ran `sealed.py btc5m-bot` at 05:04 UTC: released none, and the current block is sealed. Every process stayed under
300 MB.

- **Investigation frames** in the session scratchpad `it14/`:
  - `dcclock14_frame.parquet` (117,791 operator taker orders, 10-17..22, with m, m0, rank and the knee-scan columns k400..k150);
  - `dcfit14_pred.parquet` (the dc14 predictions, scored on 10-20..22 only);
  - `dcclock14_crowd.parquet` (975,955 non-co-arriving crowd taker BUYs).
- **The reduced HF capture** in `it13/hf_dl/`: `btc_<day>` (Binance spot bookTicker on the collector receive clock; spot trades with
  exchange ms, quantity and aggressor flag), `pm_trades_*` and `pm_touch_2026-10-20/21`.
- **The RabbitGo777 10-20 USD-M bookTicker hour** that iteration 13 had already reduced (`it13/rabbit/rabbit_bf_1792494000000000.parquet`:
  1.33M rows, 11:00-12:00 UTC, Binance event time E_).
- **Venue trade files** in `.cache/re/btc5m-bot/venues/`:
  - OKX swap and Bybit, day files 10-20..22;
  - Coinbase and Deribit, the 12 cached VALIDATE hours.
- **`fills.parquet` and `windows.parquet`.**
- **New metadata only:**
  - the footer and the kind columns of three row groups of RabbitGo777's 10-20 binance file (revision 1e0218e1), plus the repo's file list;
  - the dev-block live feeds through `iter_live` (record rates only, 10-31 16:20-16:30 UTC).
- **One web search** on Polymarket's taker delay (sources at the end).

Scripts and outputs (one `.json` per script) are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p14i\`:

| script | what it checks |
|---|---|
| `transit.py` | collector transit |
| `resid.py` | where the dc14 errors sit |
| `away.py`, `away_late.py` | earlier and later spot windows on 'away' orders; the Polymarket touch |
| `revert.py` | microprice reversal placebo |
| `value.py` | a Polymarket-overshoot value rule |
| `away_own.py` | pairing |
| `suff.py` | information sufficiency of dc14 |
| `slices.py`, `slices_w.py`, `slices_t.py` | 20/30-ms slice profiles: book, trades, by wallet, right vs wrong |
| `aggr.py` | Binance aggressor time-lock |
| `slices_v.py`, `slices_cb.py` | OKX, Bybit, Coinbase, Deribit on the wrong subset |
| `usdm_knee.py` | USD-M at the corrected clock |
| `rabbit_kinds.py` | Rabbit record kinds |

**On the scored days.** I looked at aggregates of 10-20..22, which are the pre-registered scoring days, so every constant below must be
chosen on 10-17..19 or by physics before it is scored.

## Critique

### 1. A sixth of the decisions anticipate a Binance move that starts 40-90 ms after the bot's physical horizon. "Flat past the knee" hides it.

The knee result (+15.5 points from 320 to 260 ms, +1.2 after) is a property of the pooled 250-ms cumulative window. Split the scored first
legs by whether dc14 gets them right, and use the exact-ms Binance spot trades (no collector clock involved), and the picture changes.

**Where the dc14 errors are** (`resid.json`). 18.2% of scored orders have the 250-ms spot microprice at the knee moving AWAY from the side
bought. Those orders carry 70% of dc14's errors (dc14 37.3% on them; dc14_full 44.5%). Nothing else on disk points to the side for them:

| what | agreement with the side on 'away' orders |
|---|---|
| USD-M BTC trades | 0.40 |
| USD-M ETH trades | 0.45-0.51 |
| OKX | 0.40 |
| Bybit BTC / ETH | 0.48 / 0.50 |
| Polymarket flow (1 s / 5 s) | 0.51 |
| complement of the operator's realized net (pairing) | 0.560, against 0.537 on 'toward' orders (`away_own.json`) |

Earlier Binance windows do not help either. The 250-ms window ending X ms before the knee agrees at most 0.53 (X = 300) and is 0.49-0.51
from 600 to 1,500 ms (`away.json`).

**Exact-ms trade slices** (`slices_t.json`; 20-ms slices [m0 - c - 20, m0 - c) on the exchange clock, first legs plus followers, 10-20..22):

| c (ms before m0) | 340-280 | 260 | 250 | 240 | 230 | 220 | 210 | 200 | 150 |
|---|---|---|---|---|---|---|---|---|---|
| dc14 right (n ≈ 2.6-5k per slice) | 0.78-0.83 | **0.871** | 0.860 | 0.832 | 0.788 | 0.770 | 0.762 | 0.767 | 0.755 |
| dc14 wrong (n ≈ 340-520 per slice) | 0.28-0.36 | 0.364 | 0.460 | 0.536 | 0.594 | 0.631 | **0.702** | 0.686 | 0.609 |

The trade that ends each slice has the same collector transit for both groups (median 125-128 ms for wrong, 129-130 for right), so this
is not a collector-path artefact.

**Aggressor time-lock** (`aggr.json`; Binance spot taker trades toward the side, per first leg per 10-ms bin of m0 - T, against a placebo
at m0 - 3 s):

| bin of m0 - T | 260-270 ms | 340-260 ms | 210-220 ms | 170-250 ms |
|---|---|---|---|---|
| right (47,868) | 1.94 (placebo 0.23): the trigger burst | | | |
| wrong (9,762) | | 0.03-0.06 (below placebo 0.14-0.24) | 0.42 (placebo 0.26) | 0.25-0.42 |

For the wrong first legs, flow away from the side over 340-260 ms sits at placebo level (~0.2). Over 170-250 ms, toward flow is
elevated and away flow falls to 0.10-0.15. Trade sizes are ordinary (median 0.00007 BTC in both groups), so there is no fingerprint of an
operator Binance leg.

**Information-sufficiency test** (`suff.json`). Given dc14's own prediction, does the bot's actual side still predict the spot move over
exchange [m0 - 260, m0 - 150), which lies after the horizon and before arrival?

| | [m0 - 260, m0 - 150) | after arrival, [m0 - 150, m0) |
|---|---|---|
| dc14 wrong (n 7,022) | **0.738** | 0.588 |
| dc14 wrong, confident (abs(p - 0.5) >= 0.3; n 2,041) | 0.698 | |
| dc14 right | 0.707 | 0.578 |

Without information beyond the features, a move that pointed away at the horizon persists. Conditional reversal is:

- 0.34 at random instants (`revert.json`);
- 0.26 for the non-co-arriving crowd's 'away' orders.

For the operator it is 0.52-0.53 (`dcclock14_frame` k-columns, signed).

**Every venue on disk moves after the horizon on these decisions, none before** (`slices_v.json`, `slices_cb.json`, `slices.py`). On the
wrong subset, each venue sits at or below 0.5 until about 240-260 ms and then rises:

| venue (own exchange clock) | rise toward the side | peak |
|---|---|---|
| OKX swap | 0.54 at 240 | 0.65 at 190-200 |
| Coinbase (60-ms window) | 0.56-0.57 at 240-280 | 0.62-0.66 at 180-220 |
| Bybit | later | 0.73 at 150 |
| USD-M bookTicker (10-20 11h, n ≈ 105-126) | | 0.79 at 200 |
| Deribit | never | |

A move that shows up at about the same time in Tokyo, Hong Kong and the US, 40-90 ms after the London bot's Binance horizon, cannot be read
off any of those venues by a London host. The bot either has an input that predicts it, or, for these decisions, a later horizon.

The cancel-during-delay route that would also produce this selection is closed by Polymarket's own rule: "A marketable order in a pending
delay window cannot be canceled during that window" (order-lifecycle docs).

This is the quantitative core of what is still unexplained in the side and take. About 17% of decisions use information the capture's L1
spot book does not contain at the physical horizon. It is also why XM (away share 20.2%; late window 29.4%) falls below 80% in its later
half.

### 2. The wallets do not share one information clock.

20-ms slice peaks on first legs (`slices_w.json`; exact-ms trades, fit days 10-17..19 / scored days):

| wallet | peak on trades (fit) | peak on trades (score) | peak on the book |
|---|---|---|---|
| DS | sharp at c = 260: 0.873 | 0.840 | 0.80 at 260 |
| GF | 20-50 ms earlier: 0.884 at 310 | 0.83 at 300-260 | 0.75 at 280 |
| XM | broad, 0.89 at 290 | 0.87 at 280; already 0.83 at 340 | 0.66-0.68 over 340-280 |

dc14 and the hazard use one anchor (m0 - 260, label m0 in [e + 205, e + 255)) tuned to DS, which carries 77% of first legs. Together with
XM's stall-free signing loop (iteration-13 mechanics panel), this looks like per-wallet pipelines with different decision-to-match
latencies and XM firing on longer-lived moves. The thinning ceiling for XM (0.43) assumes XM is an i.i.d. draw given P(wallet | public
state) at AUC 0.67. A wallet-specific clock is one input that P was never given.

### 3. Iteration 13's "the missing USD-M bookTicker does not close the gap" was measured on the old clock.

`rabbit13` scored the full-rate USD-M book at a = m - 180 on the receive clock, one hour only. On the same 929 orders at the corrected
clock (`usdm_knee.json`; E_ <= m0 - 260, 250-ms microprice):

- **Overall:** USD-M agrees 0.803, spot 0.789.
- **DS first legs:** USD-M agrees 0.845.
- **Spot-'away' orders (n 162):** USD-M agrees 0.531, against 0.350 for the crowd's spot-away orders.

So USD-M is not redundant at the knee. But it is not the lead for the late subset, because it moves after spot there.

The RabbitGo777 10-20 capture is far richer than the one series that was used. Its binance file (200M rows, 4,011 row groups, Finland
collector, µs local stamps, exchange E / T, update ids u / U / pu) holds, per its kind column:

- spot and USD-M depthUpdate (diff L2);
- bookTicker, trades and depth snapshots for both.

The repo also has bybit (349 MB), okx (484 MB), coinbase (228 MB), chainlink and polymarket 5m / 15m day files (`rabbit_kinds.py`). It is
the only full development day on disk with Binance L2 and the futures book on one clock.

### 4. No development block has a full-rate feed; the planned recorder is too narrow.

The dev-block live feeds are coalesced:

- `btc5m_venues2`: spot BTC 13 / s, USD-M BTC 20 / s;
- `btc5m_bnfut`: 1.7 / s.

The capture has spot at ~140 / s, and Rabbit has USD-M at 370 / s.

The next-step recorder covers only the spot bookTicker. Critiques 1-3 need:

- spot and USD-M depth;
- the USD-M bookTicker with E / T;
- aggressor trades.

Without them no out-of-time check of P1 / P3 is possible, and future-block exams depend entirely on Fahri-5 continuing to publish.

### 5. Checked and not supported (so nobody redoes them)

- **Collector-transit drift** (`transit.json`).
  - Spot-trade transit median is 131-134 ms per day and 121-140 per hour.
  - The local mean transit around the anchor is more than 20 ms off 131 for only 1.1% of scored orders.
  - Not an error source. dc14 does score 81.2% where no spot trade falls in [a - 150, a + 50) (51% of orders), against 86.2% with trades:
    quiet books are where it loses.
- **Polymarket batch timer.** Match-time phases per transaction on 10-20 (399k): Rayleigh z = 3.8 at 150 ms, 2.1 at 50 ms. There is no
  batch release that would make the delay variable.
- **Polymarket overshoot ("buy o after its ask fell faster than spot implies")**, on 'away' orders, 10-20 / 10-21 (`away.json`,
  `value.json`).
  - o's ask fell over the last 1 s in 43.3% of them, against 31.4% for 'toward' orders.
  - The value-residual rule is right 56.7% overall and 66.5% in the top abs-residual tercile (> 3.2 c).
  - It is a minor component (about a third of 'away' orders), not the main explanation.
- **Own-state pairing on 'away' orders:** 56.0% buy the complement of the realized net, against 53.7% on 'toward' orders.
- **An earlier Binance trigger for 'away' orders:** none (critique 1).
- **A London or US lead venue for the late subset:** Coinbase and Deribit do not lead it (critique 1).
- **Cancel-in-delay:** excluded by the documented rule (critique 1).

## Proposals (ranked by the chance they close the gap)

### P1. Decode the late-trigger sixth with Binance L2 order-book dynamics from the RabbitGo777 10-20 capture

**Hypothesis.** For about 17% of decisions the trigger is not an L1 price or queue move but an L2 state at the horizon, which predicts the
market-wide move 40-90 ms ahead. Candidates:

- spot or USD-M depth imbalance at levels 1-20;
- add / cancel volume by side over the last 50-250 ms;
- depletion of the queue behind the touch;
- a futures-depth or basis shift.

The bot sees this through the depth streams. The capture keeps only spot L1 and trades, so dc14 sees an 'away' or flat L1 and the
decision looks anticipatory.

**Why it fits.**

- On the wrong subset, every venue moves toward the side only after m0 - 240 and none before (critique 1).
- The post-horizon agreement is 0.74 given dc14's prediction, against a 0.26-0.34 reversal null.
- No collector artefact, no lead venue, no pairing.
- The sub-tick queue-imbalance trigger (iteration-14 finding 7) already points below L1 price changes.

**Test** (offline, development day 10-20).

1. Read the binance file's spot and futures depthUpdate, bookTicker and trade rows by ts_local row-group statistics. Use coalesced
   ranges, <= 2 threads and 429 back-off, as `rabbit_bf13.py` does: about 56 MB of the 1.35 GB per hour. Reduce at once and keep only
   per-decision features.
2. Rebuild L2 books from the depth snapshots plus diffs, using the u / U / pu continuity check.
3. At the physical horizon (E <= m0 - 260, which is also the Binance stamp the bot could have read; no data after it), compute for o's
   direction:
   - imbalance at 1 / 5 / 10 / 20 levels;
   - signed add, cancel and trade volume per level band over 50 / 100 / 250 ms;
   - L2-weighted microprice changes;
   - the futures-spot basis change.
4. Pre-register the split before scoring: 10-20 odd UTC hours to fit, even hours to score, and the reverse. Before any feature is
   computed, pre-register the dc14-wrong first legs of the scoring hours (dc14 is frozen and fitted on 10-17..19) as the primary subset.
5. Report:
   - dc14 + L2 against dc14, pooled and on the subset;
   - per wallet;
   - the sufficiency statistic recomputed with the L2 model (P(post-horizon spot move toward the bot's side | model wrong)).

**Data.**

- RabbitGo777/polymarket.btc_20261020.v4.parquet at revision 1e0218e1 (not gated): binance file plus README for the stream names and
  the collector.
- The `dcclock14` frame for 10-20 (27,008 orders).

**Signature if true.**

- On the late subset, the L2 model raises accuracy from ~0.37 to >= 0.60, and the pooled side by >= 3 points.
- The bot side's residual predictive power for the post-horizon move falls from 0.74 toward <= 0.55.
- The hazard's misses shrink the same way.

The exam limit must be stated: L2 exists for 10-20 only, so this becomes a live-recorded input for future blocks (P4) and a measured
account for h1 / h2.

**If false.** L2 adds < 1 point on the subset. The sixth is then either a decision-specific later horizon (P2) or an unrecorded feed
(live, P4). Either way it stays the wall's quantitative residual: about 17% of decisions anticipate Binance by 40-90 ms.

### P2. Per-wallet and per-decision information clocks: XM as its own pipeline (condition 7, and the XM side in the later half)

**Hypothesis.** The operator runs separate pipelines with different decision-to-match latencies:

| wallet | horizon (ms before the match) |
|---|---|
| DS | 260 |
| GF | ~280-310 |
| XM | broad, ~290-340, firing on longer-lived moves |

XM's allocation is then partly determined by which pipeline fires, through its own clock and trigger type, and not by an i.i.d. lottery.
A minority of decisions also has a later horizon (critique 1).

**Why it fits.**

- The slice peaks in critique 2.
- XM's stall-free signing loop.
- XM's higher price-level-locked share (11.2%).
- XM's hazard AUC of 0.919, the highest of the three wallets.
- DS leads 77% of first legs, as the fastest pipeline would.
- The second toward-flow mode of the wrong subset at m0 - 220..-200.

**Test** (capture, exact-ms trades plus the book).

1. Per wallet, day and hour, estimate the trigger offset from the aggressor time-lock histogram of `aggr.py`: the peak bin and its
   width. Freeze the per-wallet anchors on 10-17..19.
2. Tabulate the late-trigger share (no toward taker flow over 260-340 ms, toward flow over 170-250 ms) by wallet, hour, A/B arm, leg
   rank, window minute and order size. Check whether it has a sharp offset or a broad one.
3. Refit dc14 and the hazard with per-wallet anchors. Score once on 10-20..22.
4. Refit P(wallet | public state) with each wallet's clock features (XM's 300-ms horizon move, its move-persistence) and rerun thin14's
   redraw ceiling.

A sharp late offset (around 205-215 ms) would contradict the Tokyo-to-London geometry. It would point to a different delay path for some
orders. Check the fresh-signed crowd's sign-to-match floor by hour and order kind for a second delay mode.

**Data.** The capture already in `it13/hf_dl`, and the `dcclock14` frame.

**Signature if true.**

- XM-vs-others AUC among operator decisions >= 0.85 (from 0.67-0.785).
- The redraw-vs-redraw correlation rises enough that the XM ceiling exceeds 0.47.
- XM's per-order side in its later half >= 0.80 (from 0.786).
- The late-trigger share concentrates in identifiable pipelines.

**If false.** One clock fits all wallets within 10 ms once leg structure is controlled, and the XM ceiling stands as measured.

### P3. Reopen iteration-13 finding 14 at the corrected clock: the full-rate USD-M book and the other venues' L1 / L2 on their physical cuts, over the whole 10-20 day

**Hypothesis.** The futures L1 book is part of the bot's input at the knee. On one hour it already gives:

- 0.803 overall against 0.789 for spot on the same orders;
- 0.53 on spot-'away' orders against 0.35 for the crowd.

The negative finding came from the old anchor. Bybit L2 (50 levels), OKX L2 (400) and Coinbase L2 from the same Rabbit day, each cut
at its own physical horizon (m0 - 150 - r - T(venue to London)), may add a few points, especially for XM.

**Test.**

1. Read the USD-M bookTicker rows for all 24 hours (`rabbit_bf13.py` with the hour bounds; ~64 s per hour).
2. Read the other Rabbit venue files by the same row-group method.
3. Add the series to dc14 at E <= m0 - 260 (Binance) and at venue-specific cuts. Fix those cuts beforehand from the venues' London
   transits, measured in the 10-31 dev-block venue recordings as t - E per venue relative to Binance.
4. Fit and score on the odd / even hour split of P1.
5. Report pooled, per wallet, by window minute, and the hazard increment.

**Data.** The Rabbit files (binance 1.35 GB, bybit 349 MB, okx 484 MB, coinbase 228 MB), read by row groups. Also re-list
RabbitGo777's datasets by name, keeping only day names before H, in case more development days were published.

**Signature if true.**

- Side +1.5-3 points pooled and more for XM.
- A hazard gain of >= 0.01 over the spot-only knee hazard.

The exam route would then need the USD-M bookTicker for exam days. Its archive is 404, so this is a live-recorder input (P4) and a
VALIDATE-only diagnostic for h1 / h2.

**If false.** Gain < 0.5 points. Finding 14 then holds on the right clock, and the spot book is sufficient at L1.

### P4. A full-rate, raw, Writer-filed recorder of the Binance family plus the Tardis 11-01 free day (strong form of next step 4 and X37)

**Hypothesis.** The out-of-time check and every future-block exam depend on inputs that no development recording keeps at full rate:

- spot bookTicker ~140 / s;
- USD-M bookTicker ~370 / s;
- spot and USD-M depth@100ms;
- aggressor trades with E / T.

If the HF capture stops publishing, the exam route has no input at all.

**Test.**

1. Before 06:00 UTC, start one recorder through `tools/live.py` Writer with a hard stop at the end of each development block and
   < 100 MB RAM. Record raw:
   - spot `btcusdt@bookTicker`, `@trade`, `@depth@100ms`;
   - USD-M `btcusdt@bookTicker`, `@aggTrade`, `@depth@100ms`;
   - laptop receive time in µs.
2. Size the disk. Gzip per hour with compact keys. Estimates: USD-M bookTicker ~40-60 MB/h, the rest ~20 MB/h. That exceeds the
   300-MB cap over a 6-h block, so either:
   - record bookTicker deltas only (price or size changed) plus depth for 06-12; or
   - split into two processes with separate caps.
3. Join the operator's server-ms matches from the shared recorder's `clob_crypto` 'x' records (tx hashes) to the operator's dev-block
   fills.
4. Score frozen `dc_exam14` and `dc_hazard14`, and P1 / P3, out of time.
5. On 11-02, HEAD-check `https://datasets.tardis.dev/v1/binance/quotes/2026/11/01/BTCUSDT.csv.gz` (and incremental_book_L2, and
   binance-futures quotes). If it is free, take only the 11-01 06-12 and 18-24 development hours, reduce on the fly and delete. Never
   touch the 00-06 or 12-18 rows.

**Signature if true.**

- dc14's live per-order side is within 3 points of 0.837 on full-rate inputs; the iteration-13 live 59.6% was coalescing.
- The L2 / USD-M increments of P1 / P3 replicate out of time.

**If false.** The live side stays well below the archive's even with full-rate inputs. The capture-based number would then be
day-specific, which is an exam risk to state before h1.

### P5. Deterministic fills from the capture's L2 sizes: is condition 5 bounded by a race lottery or by missing depth data? (data form of X93 / X132)

**Hypothesis.** The PnL gap comes from filled size, not side. The tracker's strict-fill rule and the "independent race lottery" ceiling
(0.47-0.58) treat the fill fraction as noise. Given the visible depth at the limit at the release instant (server m0) and the co-arriving
crowd matches in the operator's 150-ms queue, the fill fraction is close to deterministic. The live race11 flip rate was only 4-7%.

The capture holds the data on every day, exam days included:

- askSize / bidSize per level in price_change rows;
- bids / asks snapshots;
- the crowd's server-ms trades.

Only the touch (10-20 / 10-21) and trades were ingested.

**Test.**

1. Ingest the polymarket day files' price_change sizes for BTC 5m tokens (10-17..22) by coalesced column ranges: askSize / askPrice /
   bidSize / bidPrice / exchangeTimestampMs / tokenId / eventType, roughly 0.5-0.8 GB of range requests per day, reduced at once.
2. For every operator taker order, predict filled shares as min(original size, depth at <= limit at m0 - 1 ms minus co-arriving crowd
   takes on o at [m0 - 5, m0]) and the remainder.
3. Score the correlation with filled shares, and the AUC of 'fully filled' vs 'left a remainder'.
4. Replace the tracker's strict fills by this deterministic execution, with no wallet information. Rerun trk_a on the 864 windows.

**Signature if true.**

- Filled-share r >= 0.8 and remainder AUC >= 0.9.
- The tracker's Spearman moves above 0.5 with Pearson.
- The race-lottery ceiling no longer binds, because the races resolve on public data.

**If false.** Fill fractions stay noisy given the depth. Condition 5 is then bounded by unobservable queue position, and the account
should say so with this measurement.

## Sources

- **Polymarket order lifecycle** (taker delay, and no cancellation during the delay window):
  [docs.polymarket.com/concepts/order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle) and the Chinese edition
  [docs.polymarket.com/cn/concepts/order-lifecycle.md](https://docs.polymarket.com/cn/concepts/order-lifecycle.md), which states a
  250-ms hold.
- **Delay history** (context only; the investigation's own fresh-signed crowd floor of ~187 ms fits 150 ms):
  [dev.to/abrownfox001/what-actually-changed-for-bots-63l](https://dev.to/abrownfox001/what-actually-changed-for-bots-63l) (150 ms from
  09-04) and
  [san-1510.aid.brainsum.com news item](https://san-1510.aid.brainsum.com/news/top-news/polymarket-locks-taker-orders-curb-automated-gaming)
  (250-ms lock from 06-05).
- **RabbitGo777 dataset**, metadata only: `https://huggingface.co/datasets/RabbitGo777/polymarket.btc_20261020.v4.parquet` at revision
  1e0218e12491c7e1d6183350a424fb3489539129 (file list, the binance file's footer and three row groups' kind columns).
