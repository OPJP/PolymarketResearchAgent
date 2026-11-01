# Panel, iteration 11: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

## Data used for my checks

Development data only. Everything comes from the 10-31 12-18 block (A = 14:55-16:04, C = 16:33-17:55) plus listing fields.
The current block (11-01 00-06) is sealed, and nothing from it or from `.cache/live/sealed/` was read.

- **Investigation intermediates:** `it11/onset_A.parquet`, `onset_C.parquet` (clean Binance USD-M events, label y, rec30),
  `it10/cdall10.parquet` (calldata of 45,045 BTC 5m match txs with sign ms and server match ms), `it10/txms10.parquet`
  and `it9/own_1231_12_18.parquet`.
- **Recordings through `iter_live`:** `btc5m_venues2` (Binance USD-M, OKX, Bybit, Hyperliquid and the Coinbase ticker
  `cbT`, on exchange stamps), `btc5m_clob_raw2` and `rtds`.
- **New fetches:**
  - Binance USD-M BTCUSDT aggTrades by REST for 10-31 14:55-17:55 (57,353 trades), kept in my scratchpad as
    `bnf_agg_1031.parquet`;
  - `clobTokenIds` of the 38 development windows from Gamma (`closed=true`, kept in memory only);
  - the PolyBolt AsyncAPI contract;
  - pmxt and GitHub HEAD and range probes (no market data).
- **Scripts** (each under 300 MB and a few minutes) are in
  `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p11i\`:
  `peers.py`, `presign.py`, `presign2.py`, `cbtime.py`, `cbmodel.py`, `tradetick.py`, `trend.py`, `makerage.py`,
  `lagtest.py`, `cltest.py`, `novote.py` and `fetch_agg.py`.

## Critique

### 1. The selection is called private, yet the fastest independent wallets pick the same onsets.

Iteration 11 concludes that among Binance price-level ticks the take is "a coin given public inputs", driven by "an
internal, self-exciting state". The crowd's own choices among the same 293 (A) and 181 (C) price-level events contradict
the "private" part.

The fast crowd here is non-operator taker BUYs with sign-to-match of 180-400 ms, matched on o in [tau + 150, tau + 400).
Their arrival is before tau + 250, so they decided before the cluster's trade could be seen.

| | A | C |
|---|---|---|
| P(>= 1 fast crowd wallet takes o), cluster took | 0.36 | 0.40 |
| same, cluster skipped | 0.12 | 0.11 |
| odds ratio | 4.1 | 5.4 |
| univariate AUC for the cluster's take | 0.62 | 0.65 |

- **Many wallets, not one.** The co-takers are 34 (A) and 16 (C) distinct wallets, led by 0x5d6340.., 0xeebde7.. and
  0x26d76c.. with 4-8 events each.
- **Pre-signed crowd takers co-select too:** 0.42 vs 0.21 in both halves.
- **No crowd activity before the onset separates them:** the crowd in [tau - 300, tau + 150) gives 0.51-0.54.
- **The fast crowd does not share the cluster's self-excitation.** Its take rate does not rise with the cluster's rec30
  (0 / 1-5 / 6+: A 0.21 / 0.15 / 0.21; C 0.19 / 0.08 / 0.27).

So the event-level selection is shared with about 20-30 independent fast wallets (odds ratio about 4-5), and only the
self-excitation looks private. The shared part must sit in an input those wallets also see. The current wall account
("statistically indistinguishable from random given every state variable measured") therefore names a gap in the
recorded inputs, not a private coin. That is proposal 2.

### 2. Coinbase L1 is already in the record, and it carries the first consistent public selector at price-level events.

- **The record exists.** `btc5m_venues2` has carried the Coinbase ticker channel since 10-31 14:55: every BTC-USD match with
  best bid/ask and an exchange stamp, about 4.35 per second. Iteration 10's information panel said Coinbase L1 was "not
  recorded", and X87 waits for `rec_eu11` (11-01 05:59).
- **The take falls in steps with what Coinbase did** in [tau - 500, tau + 70). That is the window in which Coinbase would
  reach a London host before the Binance tick does (transit about 38 ms against about 110 ms).

  | Coinbase in [tau - 500, tau + 70) | A: n | A: P(take) | C: n | C: P(take) |
  |---|---|---|---|---|
  | no trade | 23 | 0.48 | 7 | 0.43 |
  | traded, no move toward o | 201 | 0.31 | 116 | 0.34 |
  | moved >= 0.3 bp toward o | 69 | 0.22 | 58 | 0.17 |
  | moved against o | 15 | 0.00 | 4 | 0.00 |

- **The pattern holds within every |bp| tercile in both halves.** Coinbase moved vs not:
  - A: 0.29 vs 0.36, 0.25 vs 0.34, 0.17 vs 0.27;
  - C: 0.12 vs 0.28, 0.13 vs 0.46, 0.24 vs 0.28.
- **It also holds when o's ask is unchanged at tau + 150:**
  - Coinbase-first (first move before tau + 70): A 0.22 (n = 67) vs 0.31 (n = 195);
  - C 0.10 (n = 42) vs 0.32 (n = 102).
- **Background Coinbase activity does not explain it.** Trades in [tau - 5 s, tau - 0.5 s] give AUC 0.46-0.47.
- **At size-only Binance events the sign flips.** A Coinbase move toward o raises the take 4x: A 0.217 vs 0.059, C 0.182
  vs 0.045 (10k sampled clean events).
- **A crude London-arrival logistic gains in both directions.** It adds "Coinbase / OKX / Bybit moved toward o before
  tau + 110 - L_v" and the move sizes to evt10's FULL features:

  | | all clean events | price-level events |
  |---|---|---|
  | fit A, scored C | 0.681 -> 0.697 | 0.535 -> 0.582 |
  | fit C, scored A | 0.691 -> 0.712 | 0.597 -> 0.618 |

  Price-level events are where every recorded feature was at or below 0.58 and inconsistent.
- **The fast crowd shows the Coinbase gradient on A** (none 0.27 vs 0.00-0.14 after a Coinbase move), but not clearly on C.

So the bot takes Binance-led price-level ticks that Coinbase has not yet reflected, and skips the ones the US venue had
already moved. That is the sign X87's parity gate predicts, and it can be tested today instead of waiting for 11-01. The
catch is that `cbT` is trade-sampled. Proposal 1.

### 3. The binding exam conditions are historical, and no proposal yet changes what the block clock can see.

- **What binds.** h1 is scored at the block clock: side 76.7% against 80%, and PnL 0.18 against 0.5.
- **The live improvements cannot reach it.** The PIT vote, price and hazard need a ms match clock and venue microprice.
- **pmxt is no route.** It still ends on 08-10. Re-probed now:
  - 08-09T23 answers 206;
  - 08-10T23, 08-11T00, 08-15T12, 09-01T00 and 10-20T12 answer 404;
  - `www.pmxt.dev` redirects;
  - the `pmxt-dev` GitHub org has no newer archive repository (`polymarket-orderbook-collector` was last pushed 07-31).
- **Critique 2 supplies a route.** Unlike the Polymarket book, Coinbase and Binance trades are archived or fetchable at ms
  for October, so the venue-arrival class of every Binance onset can be computed for VALIDATE, h1 and h2. A
  "Binance-led, Coinbase-silent" condition is a feature the block clock does not blur: it is fixed on the venues'
  ms stamps, not on the match time. Proposal 1, step 4.

### 4. Twenty per cent of the crowd's taker orders are pre-signed, and nobody has looked at them.

- **The size of the gap.** crowd10 and crowd11 keep fresh signers only (180-2,000 ms). In `cdall10`, 7,707 of 37,886
  non-operator taker BUYs (20%) were signed more than 3 s before their match, from 779 wallets.
- **These are the bot's closest peers.** Several carry the cluster's mechanical fingerprint (proposal 3). The sibling
  census of iteration 10 searched only the cluster's own burst intervals (-89.5 / +42 / +172.7 s), so a clone or sibling
  on another schedule could not be found that way.
- **Two wallets stand out:**
  - 0xbee23727e1ff966525b87a3f04ae8cae56b0d4a4 signs 94% of its taker orders in the 10 s before a window opens;
  - 0x1b414826a2c991d5ae1669a754291626d0df0b56 is the other.

### 5. The "directional on-state" (finding 7) is tested against a fair-coin null, not against the tick-direction mix.

- **The test.** The mean |share Up - 0.5| in active 30-s bins is 0.224, against a binomial(0.5) null of 0.130.
- **The confound.** The side is the tick direction in 83% of decisions, and 30-s bins of BTC are trending. The bins
  would look directional even if the bot took ticks at random.
- **The right null** is the Up share of the clean events available in the same bin, ideally the price-level ones.
- **Why it matters.** Until that null is run, "directional" is not evidence for an internal directional state.

## Proposals (ranked by the chance they close the gap)

### 1. The cross-venue divergence gate: the bot takes Binance moves that Coinbase and the European venues have not yet reflected (new as a selector; strong form of X87 steps 2-3; brings the test forward to data that exists)

**Hypothesis.**

- The take among flagged onsets is gated by the *order of arrival* of the move across venues on the bot's London clock.
- **Binance-led, US/EU-silent price-level ticks** are taken, at about 35-48%. The Polymarket touch, and the makers who
  read the closer venues, have not repriced, so the bot's edge is real.
- **Ticks already shown by Coinbase** (and probably Bitstamp and Kraken) are skipped, at 17-22%. Two readings: they are
  continuations, not onsets, or the makers already know.
- **Size-only Binance changes** become actionable when a US venue confirms them.
- The same gate is read by the fast crowd. That accounts for part of critique 1's co-selection.
- The large size and the operator's lean may follow the size of the divergence. This would carry condition 5.

**Why it fits.**

- Critique 2: a monotone gradient in both halves and every |bp| tercile.
- The sign flips between price-level and size-only events.
- The logistic gains +0.016 / +0.021 on all events and +0.02-0.05 on price-level events.
- The bot sits next to Polymarket's engine in Europe (lam11, xcorr11), where Coinbase arrives about 70 ms before Binance.
- OKX and Bybit moving well before the tick ([tau - 500, tau - 100)) also lowers the take: A 0.26 / 0.23 and C 0.18 /
  0.24, against 0.27-0.35 with no move.

**Test.**

1. **Today, on 10-31 A/C, with `cbT`.**
   - Build the London-arrival clock with xcorr11's stamp offsets (OKX +10 ms, Bybit and Deribit +60 ms relative to Binance)
     and the transits L_v (Binance 110, OKX 97, Bybit 87, Coinbase 38, Deribit 2 ms).
   - Classify every clean event by the first London arrival of the move toward o, and by the lead of that arrival over
     the Binance tick.
   - Report P(take) by class x event class.
   - Fit on A and score on C, and the reverse, against FULL.
   - Use the same event classes for the fast-crowd label (proposal 2).
   - Control for Coinbase's trade sampling: report "no Coinbase trade in the window" as its own class.
2. **On 11-01 06-12, pre-registered before 06:00.**
   - Repeat with `rec_eu11`'s Coinbase `level2_50` top, Bitstamp microtimestamps and the Kraken v2 book, which give L1
     between trades.
   - Pre-register the gate: P(take | Binance-first and no US/EU move toward o before the Binance London arrival) is at
     least 1.8x P(take | a US/EU venue first), on price-level events.
   - Pre-register the gain: FULL + London-arrival class is at least +0.03 on all clean events.
   - Replicate on 11-01 18-24 and 11-02 12-18. The first EU/US weekday overlap is where Coinbase leads most.
3. **Size.**
   - P(large | divergence class) on the 111 large decisions of 10-31, and on 11-01.
   - The large size follows tick strength (AUC 0.72). Does it follow the divergence instead: a large Binance move with
     Coinbase silent?
4. **Historical, for h1.**
   - Get Coinbase Exchange BTC-USD trades with ms stamps for BUILD and VALIDATE (`/products/BTC-USD/trades`, trade-id
     cursor; about 1k pages a day, a few minutes a day at the public rate limit; or the Advanced Trade time-bounded
     ticker used in `fetch_rest6`).
   - Use Binance USD-M aggTrades from the daily archives. Per block second and outcome, compute the divergence state: a
     Binance trade-price move toward o in [bt - 3.0, bt - 0.2] s with no Coinbase trade beyond the pre-move price.
   - Add it to the block-second presence model and to the side vote: the vote restricted to Binance-led moves, with the
     full vote as fallback.
   - Score on VALIDATE with the existing pipeline, against the 0.8211 baseline and the 76.7% side.

**Data.**

- `btc5m_venues2` (`cbT`, `ok`, `by`, `bf`) and the onset tables, both existing.
- `rec_eu11` feeds from 11-01 05:59.
- Coinbase Exchange REST trades and Binance aggTrades archives for October, streamed and reduced to per-second
  divergence flags at once (a few MB). Prune `bybit_ob` and `cells` first (the cache is at the cap).

**Signature if true.**

- On 10-31 and replicated on 11-01: P(take | Binance-led) / P(take | US-led) is 1.8 or more at price-level events in
  every half.
- The London-arrival model gains +0.03 or more on all events and +0.06 or more on price-level events. The fast crowd
  shows the same gradient.
- Historically, the divergence flag lifts block-clock presence by +0.005 or more over FULL and the Binance-led side vote
  by 1-3 points. That is the only route proposed so far by which h1's side can approach 80%.

**If false.** The gradient vanishes once Coinbase L1 is sampled between trades (11-01 `level2_50`). Then the 10-31
pattern was Coinbase trade sampling, and the selector is not geographic: record that X87's parity gate failed on L1
data.

### 2. The shared-actionability instrument: use the independent fast crowd as a second label and as a falsification test for every candidate input (new; strong form of X72 / X74; changes the wall account)

**Hypothesis.** Most of the selection among flagged onsets is a function S(public inputs) that the cluster shares with
about 20-30 fast wallets. Only a small residual (the self-excitation) is the operator's own.

**Why it fits.** Critique 1: odds ratio 4.1-5.4 between the cluster's take and the fast crowd's take at price-level events,
decided independently. The pre-signed crowd co-selects too. The fast crowd does not follow the cluster's rec30.

**Test.**

1. **The co-take table.**
   - Per clean event of A and C: the cluster's y, the fast-crowd indicator (sign-to-match 180-400 ms, match in
     [tau + 150, tau + 400)) and the pre-signed-crowd indicator. The scripts here already do this from `cdall10`.
   - The crowd indicators are diagnostics only, never rule features: they are co-occurrence.
2. **Conditional independence.**
   - For each candidate feature set X, fit logit(y_cluster) on X + fast-crowd indicator, on A, and score C.
   - Candidates: FULL, the normalizer, survival, the London-arrival class of proposal 1, the PolyBolt touch (X76), depth5,
     alt perps, Bitstamp and Kraken.
   - The right X drives the crowd coefficient's odds ratio from about 4.7 toward 1.
   - Report the share of the co-take log-odds-ratio each X explains.
3. **Label pooling.**
   - Fit the selector on the fast crowd's take: about 3-5x more positives per event set when pooled over wallets, with
     per-wallet fixed effects.
   - Transfer it to the cluster, and compare it with the cluster-fitted model on C.
   - A shared selector transfers; a private one does not.
4. **Wall account.**
   - Split the unexplained selection into shared (the log odds ratio left after the best X) and private (the operator's
     rec30 effect within crowd-matched events).
   - "Private" is what a wall can claim.

**Data.** `cdall10` (exists). The same calldata for 11-01 06-12 and 18-24: about 45k match txs per 3 h through
`fetchcrowd10.py`'s batched `eth_getTransactionByHash`, the same plan as iteration 10. The onset tables.

**Signature if true.**

- One feature set X separates both labels: AUC 0.65 or more at price-level events for the cluster and for the fast crowd.
- With X in the model, the co-take odds ratio falls below 2.
- The crowd-fitted selector transfers to the cluster within 0.02 AUC.

**If false.** The odds ratio stays at about 4-5 under every recorded X. Then the shared input is unrecorded, and the
account states it quantitatively: "a signal shared with N independent fast wallets, odds ratio 4-5, present in no
recorded feed". That replaces "a coin given public inputs".

### 3. The pre-signed peer census: clones of the same software and possible siblings on other schedules (strong form of X66 step 4, C1 and C8; new data subset)

**Hypothesis.**

- (a) Other operators run the same template (pre-signed 1-cent ladders, `round(Math.random() * Date.now())` salts,
  signature type 3, 317-byte signatures). Their decisions follow the same rule with other parameters, so their combined
  record decodes the rule with more data and other settings.
- (b) Some are the operator's own wallets on other burst phases. They then belong out of the market-activity baseline
  (the brief's own-prints rule) and into the operator net (size, X84).

**Why it fits (check, `presign2.py` / `peers.py`).**

Ten wallets with at least 40 pre-signed orders show the ladder loop: |Spearman(sign ms, price)| of 0.9 or more within
bursts on at least 3 bursts, and salt / timestamp in [0, 1]. W4 is one, at 1.68 ms per cent (the cluster's is 1.66).

| | 0xbee23727 | 0x1b414826 |
|---|---|---|
| ms per cent | 1.51 | 4.42 |
| taker share | 89% | 99% |
| median sign-to-match | 85 s | 122 s |
| signing phase | 94% in [-10, 0) s of a window | |
| P(takes at price-level events), cluster took (A / C) | 0.15 / 0.25 | 0.02 / 0.12 |
| same, cluster skipped (A / C) | 0.04 / 0.02 | 0.005 / 0.05 |
| co-arrival with a cluster taker match, +-50 ms (placebo +-2 s) | 5.8% (1.0%) | 1.9% (0.8-1.5%) |

0xbee23727 also has signature type 3 and 317-byte signatures. The iteration-10 candidate 0x03b4c58b co-arrives in 75%
(n = 12). The clones co-take with the cluster rather than complementing it, so the dispatcher reading is not supported
on 10-31. The clone reading is.

**Test.**

1. **Fingerprint census.**
   - Over all 45k txs of 10-31 and the VALIDATE calldata samples (`calldata_sample.parquet`).
   - Features: ladder monotonicity and ms per cent, same-ms copies, salt generator, signature type and length, builder,
     sizes, burst phases (mod 300), BTC-5m-only.
   - Cluster the wallets.
2. **Clone rule test.**
   - For each clone, P(take | price-level onset) and its own rec30 effect, kernel and vote on A / C.
   - Do the clones show the same divergence gradient (proposal 1) and the same self-excitation?
   - Do they have their own on-states that co-occur with the cluster's? If so, the on-state is a shared software state
     driven by a public input. If not, it is per-operator.
3. **Sibling test.**
   - Shared funding addresses (USDC Transfer logs) and `owner()` EOAs created together.
   - Complementarity with the cluster on shared events.
   - Moving the confirmed siblings' prints out of the baseline features changes presence_baseline. A small gain in
     condition-2 margin.

**Data.** `cdall10` and `calldata_sample` (existing). Polygon logs for funding links, through drpc in 100-block chunks.

**Signature if true.**

- A clone cluster with the cluster's loop fingerprint, whose take shares the cluster's predictors at a pooled n that
  separates them (AUC 0.65 or more on its own events).
- Or a sibling set with common funding whose removal from the baseline lowers presence_baseline by 0.003 or more.

### 4. The bot's private channel: does its own fill (the user channel) re-arm the take? A natural experiment for the self-excitation (new; complements X97, which tested only the size)

**Hypothesis.**

- The bot learns its race outcome on the CLOB user channel about 150 ms after arrival.
- A WON race (a stale ask confirmed) raises its take hazard on the next ticks of that window: the self-excitation is
  fill-driven.
- The alternative is a common driver, an on-state input, that raises both.

**Why it fits.**

- P(take) rises with rec30 beyond public crowd activity (finding 13).
- The fast crowd does not share that rise (critique 1).
- The race outcome is nearly deterministic given the arrival and the crowd queued ahead (race11). That makes losses to a
  queued crowd order exogenous to the bot's information, the same device X97 used for the size.

**Test.**

1. **Decisions.** Use the 2,155 live decisions (taker-first matches plus located lost races).
2. **Hazard after won vs lost.** Compute the operator-level hazard of the next decision on the same window over
   [m + 150, m + 1,000), [1, 5) s and [5, 30) s, after:
   - WON decisions;
   - LOST decisions with a crowd order queued ahead (exogenous);
   - LOST decisions to a requote.

   Match on tick strength, time in window and o's ask.
3. **Exclude the mechanical gap.** Use the other wallets' next decisions, or exclude same-wallet decisions inside its
   one-in-flight gap floor (D + 2-104 ms).
4. **Date the feedback.** A kink in the hazard ratio at m + delta, with delta about 5-50 ms of user-channel latency, after
   won but not after lost decisions.
5. **Model it.** If fill feedback holds, write the take as a hazard with a fill-triggered excitation kernel. Keep it in
   the replica only: own-state features never count toward the target.

**Data.** Existing (`race11` / `size11` decision tables). Repeat on 11-01 06-12.

**Signature if true.** The hazard after WON is 1.5x or more the hazard after an exogenous LOST in the first 1-5 s, and
equal after 30 s. **If false** (equal): the self-excitation is a common driver, and proposals 1-2 should find it.

## Checked and not supported (so nobody redoes them)

All on 10-31 A / C price-level events unless noted. Each entry gives AUC for the cluster's take, or (cluster / fast crowd).

- **Trade-driven vs quote-driven Binance price-level ticks** (`tradetick.py`; aggTrades REST):
  - P(take) with a same-direction aggressor trade in [tau - 150, tau + 5] is 0.29 / 0.28, against 0.36 / 0.38 without
    (A / C);
  - aggressor volume AUC 0.37-0.53 (cluster) and 0.46-0.57 (fast crowd).

  The trade stream is not the selector; if anything, quote-driven ticks are taken more.
- **Agreement of the tick with the BTC trend** over 5 / 15 / 30 / 60 / 120 s (`trend.py`): A 0.46-0.51, C 0.41-0.68
  (inconsistent across halves); return since the open toward o 0.49 / 0.58.
- **Age and identity of the maker orders** consumed by the first crowd take after the onset (`makerage.py`; 220 / 135
  events): youngest age 0.47 / 0.45, median age 0.51 / 0.38, distinct makers 0.59 / 0.50, maker frequency 0.54 / 0.48.
  Inconsistent. Maker signing time is not posting time, so X90 stays open, but this cheap form gives nothing.
- **Feed staleness as seen from the laptop** (`lagtest.py`): Polymarket WS (t - s) residual over a rolling 60-s minimum,
  and Binance (t - E), at or before tau: 0.42-0.52.
- **Chainlink 1-s points** (`rtds` `crypto_prices` and `crypto_prices_twap_sixty`, `cltest.py`): move toward o over
  [-3, -1], [-2, 0], [-1, +1] and [0, +2] s gives 0.40-0.57, inconsistent. PolyBolt's `price.crypto` is gated and "about
  one update per second per symbol" (contract read), so it cannot be a 100-ms trigger.
- **Coinbase leadership regime** (share of Coinbase-first events over the last 30 s): 0.47-0.55. The leadership acts per
  event, not as a slow regime.
- **The Coinbase ticker as fallback vote for the no-vote decisions** (`novote.py`): it covers only 3% of no-vote
  taker-first decisions, because it is trade-sampled at 4.35/s. The no-vote third cannot be tested on `cbT`; it needs
  `rec_eu11`'s `level2_50` (X88 / X87 on 11-01).

## Sources

- **PolyBolt contract:** `https://ws-live-v2.polymarket.com/asyncapi.json` (HTTP 200, read 10-31 23:58 UTC).
  - Channels: `price.polymarket` (public), and `price.crypto`, `price.crypto.twap`, `price.equity`, `price.equity.twap`
    (gated by an Access Token or CLOB credentials, which must not be created).
  - `price.crypto` names its vendor per payload (Pyth or Chainlink, a per-symbol operator decision).
- **pmxt:** 1-byte range requests to `https://r2v2.pmxt.dev/polymarket_orderbook_<hour>.parquet`, development hours only;
  `https://api.github.com/orgs/pmxt-dev/repos` (unauthenticated).
- **Binance:** `https://fapi.binance.com/fapi/v1/aggTrades`, BTCUSDT, startTime/endTime inside 10-31 14:55-17:55 UTC
  (development block, asserted with `sealed.future_block_sealed`).
