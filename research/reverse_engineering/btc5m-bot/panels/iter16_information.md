# Panel, iteration 16: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

Written 11-01 ~09:30 UTC.

## Data used for my checks

Development data only. I ran `sealed.py btc5m-bot` at 08:54 UTC: no lots released, future examined until 10-31 00:00, and the
current block (11-01 06-12) is development. Nothing was opened from `.cache/live/sealed/`, from any capture day at or after H,
or from another strategy's workspace. Every process stayed under 300 MB.

- **Investigation frames in the session scratchpad:**
  - `it16/cdfull_10-20..22.parquet` (the complete calldata) and `it16/tapes`;
  - `it14/dcfit14_pred.parquet`;
  - `it15/l2grid_*`, `it15/l2tok_*`;
  - `it13/hf_dl/btc_2026-10-18/20.parquet` and `pm_trades_*`.
- **From the strategy cache:** `windows.parquet`.
- **Live lab, development block 11-01 07-08 UTC:** `btc5m_clob_raw2`, `btc5m_pb`, `btc5m_bnspot2`, all through `iter_live`.
- **Live, development block, nothing stored except summaries:**
  - 120 s of five simultaneous Binance spot `btcusdt@bookTicker` connections (08:56 UTC);
  - 180 s of one combined `bookTicker` + `trade` connection (09:16 UTC).
- **data-api `/activity`:** the five operator wallets over three 30-minute samples, all in development periods: 10-21 12:00,
  10-31 13:00 and 11-01 07:00 UTC.

Scripts and outputs are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p16i\`:

| script | what it checks |
|---|---|
| `multiconn.py` | whether simultaneous Binance bookTicker connections see the same updates |
| `btorder.py`, `capbtorder.py` | whether bookTicker shows a cleared level before or after the trade message (live, and inside the capture) |
| `pbvsclob.py` | PolyBolt `price.polymarket` against the CLOB market channel: lag and missing states |
| `w45book.py` | whether finding 17's drained-book marker for XM is the footprint of W4 / W5 |
| `sibcensus.py`, `sibsign.py` | a blind census for a sixth sibling wallet ahead of XM, and its signing fingerprint |
| `selfcross.py` | how often the operator's takers hit the operator's own resting orders |

**On the scored days.** I looked only at aggregates of 10-20..22, which are pre-registered scoring days.

## Critique

### 1. The regime the exam will see is not the regime the rule was fitted on

Operator transactions (taker and maker fills) in 30-minute samples of development time, from data-api `/activity`:

| sample (UTC) | DS | GF | XM | W4 | W5 | XM share of DS + GF + XM |
|---|---|---|---|---|---|---|
| 10-21 12:00-12:30 | 843 | 438 | 125 | 225 | - | 9% |
| 10-31 13:00-13:30 | 425 | 232 | 306 | 126 | - | 32% |
| 11-01 07:00-07:30 | 262 | 130 | 184 | 49 | 2 | 32% |

On 10-20..22, XM led 4.4% of first legs (2,534 of 57,630). On 11-01, XM fills 60-share orders, a size outside the capture-day
menus.

These are all fitted on 10-17..22:
- the five-slot priority list;
- the per-wallet large shares (DS 3.8%, GF 32%, XM 34%) and the lean table;
- XM's PnL ceilings.

The h1 lot (10-23..29) lies between the two regimes. Every future-block exam lies in the new one. Condition 7 judges XM on the
lot, so a rule that is right about 10-20..22 can still fail the exam on XM and on scope.

The investigation knows about XM's 10-31 role (X9, X67, X162). But no frozen component has been checked in the new regime, and
the only new-regime data with millisecond feeds is the live lab of 10-31 00-06 / 12-18 and 11-01 06-12 (proposals 1 and 2).

### 2. Six catalog items have waited for "the next development block". It is recording now, with every feed, and nothing has been scored there

These items say they need 11-01 06-12:
- X44 (USDC / FDUSD spot, COIN-M, Deribit perp, Bybit L1);
- X76 (PolyBolt);
- X87 / X100 (Coinbase level2, Bitstamp, Kraken);
- X88 (alt perps);
- X142 (full-rate Binance spot and USD-M).

All of them are on disk for 06:00-09:00 UTC so far. The operator is active: DS 262, GF 130, XM 184, W4 49 transactions in 30
minutes.

What is missing is the decision record of the block: the calldata of its operator taker txs (original size, limit, signing ms).
That is about 3-6k txs, or 2-3 minutes at cdfull16's ~35 tx/s.

The out-of-time check the iteration-15 notes planned on `rec_bn15 v2` had one open worry, the input density (~140 msg/s in the
capture against 25-55 msg/s live). My check settles it as a weekday effect, not a collector effect:

| source | bookTicker rows per second |
|---|---|
| capture, 10-18 (Sunday) 07-08 / 08-09 UTC | 86.5 / 41.4 |
| capture, 10-20 (Tuesday) 07-08 / 08-09 / 14-15 UTC | 131.8 / 126.5 / 448.5 |
| `rec_bn15 v2`, 11-01 (Sunday) 07-08 UTC | 46.7 |
| my five connections, 11-01 08:56 UTC | 55.4 each |

### 3. The capture's Binance book clock runs slightly early, at the scale where condition 2 is decided

The spot bookTicker has no exchange stamp. The investigation times it as capture receive - 131 ms, the trade-stream transit.
But Binance pushes the bookTicker before the trade message of the same match:

- **Live, one combined connection, 180 s, 1,641 level-clearing pairs.** The bookTicker that shows a cleared level arrives first
  94% of the time, a median 4.6 ms earlier (q25 7.4, q5 11.9 ms earlier).
- **Inside the capture itself.** Book row first in 85.5% (10-20, 11 h, 68,177 pairs) and 80.3% (10-18, 07 h, 17,222 pairs).
  Median 4 ms earlier, q25 7-8 ms, q5 16-20 ms. The trade transit q50 is 132-133 ms.

So Te = receive - 131 stamps book events about 2-3 ms before the trade that caused them (median), and up to ~15 ms in the tail.
A spot-book feature cut at Te <= e therefore contains some Binance book events published after e. That is the leak direction.

Condition 2 at the decision clock stands at +0.058 (CI lower bound 0.050) on the forward split. A 50-ms move of the Polymarket cut
is worth ~0.05 AUC there. The correction is small, but it is the kind an examiner who audits PIT will make, and it should be
pre-registered before the exam (proposal 4).

The defensible PIT statement for the e cut is also the brief's own definition, not the bot's view. For a bin ending at e, every
feature uses data published at or before e on its publisher's clock: Polymarket by its server stamp, Binance by its exchange stamp.
The e + 50 baseline then simply uses future data for that bin.

### 4. The bot's Polymarket channel was never identified, and PolyBolt fits the measured staleness

PolyBolt `price.polymarket` against the CLOB market channel, BTC 5m Up tokens, 11-01 07-08 UTC, both received on this laptop:

| measure | value |
|---|---|
| CLOB best-ask changes | 3,831 |
| shown by PolyBolt | 82.2% (17.8% short-lived ask states never appear) |
| receive lag, PolyBolt minus CLOB (q5 / q25 / q50 / q75 / q95) | -24 / +21 / +27 / +33 / +204 ms |
| PolyBolt producer ts minus CLOB server ms (median) | +1 ms (same engine stamp) |
| `x` (dropped) on 1.03 M records | 0 |

The bot's view is ~30 ms older than its arrival (X98: Λ peak 30 ms; view16: DS's view in (m - 250, m - 180] on the book clock),
and its Binance-to-arrival processing is only ~10 ms. A London bot that reads PolyBolt would look exactly like that.

This matters for three things:
- the price anchor (which ask the bot saw);
- XM's spread over +0 / +1 / +2 c;
- the per-wallet view edges that condition 2's cut argument and X151 rest on.

The 17.8% of CLOB-only transient states give a sharp instrument (proposal 3).

### 5. Checked, so nobody redoes them

- **Binance feed sampling is not a take coin.**
  - Five simultaneous bookTicker connections (three to `:9443`, one to `data-stream.binance.vision`, one combined on `:443`)
    received 6,648-6,653 messages in 120 s. The Jaccard of update ids is 0.999-1.000.
  - The 250-ms microprice sign differs between connections on 0.5-3.1% of 50-ms grid points, from ±10 ms receive jitter.
  - The bot's Binance input equals any recorder's, up to path jitter.
- **The XM drained-book marker (finding 17) is not W4 / W5's footprint.**
  - Among first legs with no W4 / W5 leg in the 1.5 s before m0, the XM-vs-rest AUC of o's depth to best + 4 c (m0 - 230
    relative to 500 ms earlier) is 0.672. On all first legs it is 0.631.
  - Median ratio: XM 0.58, DS 0.95, GF 0.88.
  - So XM's legs come after the makers have already pulled, consistent with a later slot. A same-outcome W4 / W5 leg in the 1.5 s
    before m0 precedes 41.6% of XM-led first legs, 11.0% of GF-led and 7.9% of DS-led.
- **No sixth sibling ahead of XM.** Blind census over the taker BUYs of 10,547 non-operator wallets on 10-20..22 (same window and
  outcome, within 300 ms before a first leg; placebo 3 s earlier):
  - W4 precedes 31.1% of XM-led first legs (placebo 2.0%) and 1.8% of DS-led (placebo 1.5%).
  - The next wallet, 0xeebde7a0, precedes 6.9% of XM-led (placebo 2.0%). It signs with sig type 1 / length 65 and 40-42-share
    sizes: another software stack.
  - Dozens of crowd wallets precede XM 1-3 points more often than DS, because XM is late in moves.
- **The operator almost never trades against its own resting orders.** Operator-owned maker orders are 0.3% / 0.4% / 0.6% of the
  maker shares in its taker txs (77 / 96 / 154 orders on 10-20 / 21 / 22). All are complement BUYs (mints), never the same wallet.
- **Pre-signed stock does not bind.** Uses per (wallet, token, signing burst, cent, size) cell on 10-20 decline geometrically, with
  no cliff:

  | uses per cell | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|
  | DS cells | 10,072 | 2,521 | 625 | 180 | 46 | 12 | 1 |

  GF 6,082 / 512 / 61 / 2; XM 1,426 / 37 / 1.
- **RTDS is no input.** The RTDS Binance relay (`crypto_prices`) and the Chainlink topics only send their snapshot on this socket
  (iteration 6). The bot cannot run on them; nothing to test there.

## Proposals (ranked by the chance they close the gap)

### P1. The first out-of-time complete decision record, in the new regime, across every recorded feed (strong form of X142 / X150; closes the scoring steps of X44, X87, X88, X100)

**Hypothesis.** Two things are true:
- The frozen routes transfer out of time: dc_exam14 (side), dc_hazard14 at the decision clock with the e cut (presence), DS's
  public size model, and the price-size coupling.
- The feeds recorded only live carry no part of the two binding coins, which are take selection among top-hazard instants and
  GF / XM's large class.

**Why it fits.**
- Critique 1 (regime shift) and critique 2 (the block is recording; density validated).
- No component has ever been scored out of time on its exam route. Iteration 13's live check failed only on input density, and
  that objection is now gone for Sunday blocks.

**Test.**
1. **Decision record.** Operator fills of 11-01 06:00-12:00 (and of 10-31 00-06 / 12-18 if the shared recorder's `clob_crypto`
   'x' records cover them) from data-api `/activity` for the five wallets. Calldata of every operator taker tx with cdfull16.py.
   Server-ms matches from the `clob_crypto` / `btc5m_clob_raw2` 'x' records by tx hash.
2. **Clock.** Laptop-to-server offset from `btc5m_clob_raw2` (t - s) and from Binance T in `btc5m_bnspot2`. Book events timed as
   in proposal 4.
3. **Pre-register and score once, frozen.** Write the pre-registration first:
   - side per taker order and per wallet (bar 0.80);
   - the hazard's gain over the book-aware baseline at the e cut (bar 0.05);
   - DS's size AUC with the size16 'cd' public model (bar 0.75);
   - the five-slot priority list's carrier accuracy (iteration-16 value 0.778 on three wallets).
4. **Live-only feeds on the binding targets, not on the side.** For each feed, the marginal AUC on (a) taken vs skipped
   top-3%-hazard bins and (b) the large class of GF / XM. Pre-registered bar +0.03, block bootstrap by window. Feeds:
   - USDC / FDUSD spot and COIN-M (`btc5m_xfam`);
   - alt perps (`btc5m_xeu`);
   - Coinbase / Bitstamp / Kraken (rec_eu11);
   - USD-M full rate (`btc5m_bnusdm2`).
5. Repeat on 11-01 18-24 and 11-02 00-06 / 12-18, the next development blocks, as the two halves condition 7 asks for.

**Data.** All on disk or one fetch away: the live lab feeds above, data-api `/activity` (development blocks only), Polygon calldata
through drpc (`eth_getTransactionByHash`, batched).

**Signature if true.** Side >= 0.80, presence gain >= 0.05 and DS size >= 0.75 hold out of time, and no live-only feed adds 0.03 to
either coin. The coins are then not missing data, and the residual account can say so with a feed list.

**If false.**
- The side or hazard drops by more than 0.03: the rule is version-bound and has to be refit in the new regime before any exam.
- The priority list's carrier accuracy collapses: proposal 2.

### P2. The XM regime change as a natural experiment for the dispatcher and the size coin (strong form of X162 and X9)

**Hypothesis.** The tripling of XM's share is a dispatcher reconfiguration: a new priority order, slot length or menu.

Under the iteration-16 reading:
- the size is a per-wallet configuration (E3);
- or it follows the slot position in a burst (E6).

The two make opposite predictions for the new regime:
- under E6, a wallet that moved up the priority list sends fewer large orders. XM would approach DS's ~4% if it now leads
  bursts;
- under E3, each wallet keeps its base rate;
- in both, the lean table P(large | none / with / against) per wallet stays fixed if it is the operator's inventory controller.

**Why it fits.**
- XM went from 4.4% of first legs to ~32% of transactions, with 60-share orders (critique 1).
- The capture days cannot separate E3 from E6, because the slot and the wallet are confounded there (GF / XM are later slots).
  A configuration change breaks that confound.

**Test.**
1. With P1's decision record (11-01 06-12; add 10-31 12-18 by fetching its operator taker calldata), recompute disp16b on the new
   regime:
   - the best order of the five wallets and the slot length;
   - XM's share as leader;
   - the tick lock by carrier (disp16's PSTH: GF +20 ms, XM +40 ms on the capture days).
2. Per wallet, compute the large share and the lean table on exact calldata sizes, split by slot position: leader of a visible
   event, follower within 300 ms, and follower of a book-visible lost leg (the hidden16 marker).
3. Date the change point.
   - Use daily operator fill counts from data-api on development days only: before H and 10-31 / 11-01 development blocks. The
     sealed days stay unread, so the bracket is (10-22, 10-31).
   - Check Gamma `feeSchedule`, `makerRebatesFeeShareBps` and rewards fields of the listed BTC 5m windows (listing projection
     only).
   - Check `docs.polymarket.com/changelog` entries dated in development time.

**Data.** P1's record, data-api `/activity` (development periods), Gamma listings, the changelog.

**Signature if true.**
- E6: P(large | wallet) moves with the slot position, the same table across regimes by slot, not by wallet.
- E3: P(large | wallet) is unchanged while the slots changed.

Either way the size term of condition 5 gets a mechanism that transfers. If E6 holds, X161's replica with simulated occupancy also
reproduces the size class, and that is the route to condition 5 and to condition 7 for XM.

**If false.** Both the slots and the large shares move together with no stable table. The size is then a per-version configuration
draw, and the exam's new-regime blocks need the new base rates. Record them as such.

### P3. Is PolyBolt the bot's Polymarket view? Use the CLOB-only transient asks as an instrument (strong form of X76)

**Hypothesis.** The operator reads o's best ask from PolyBolt `price.polymarket` (conflated best bid / ask, ~27 ms behind the CLOB
market channel), not from the CLOB market channel.

**Why it fits.**
- Critique 4: the PolyBolt lag matches the bot's ~30-ms-old view while its own processing is ~10 ms.
- PolyBolt launched on 09-15, before the capture days.

**Test.**
1. For every operator taker order of 11-01 06-12 (P1's calldata), the ask the bot saw is a_seen = L - (0 c for a small order,
   1 c for a large one; iteration-16 finding 7).
2. On the laptop receive clock, find the latest state before the arrival (m0 - 150 on the server clock, converted) whose best ask
   equals a_seen, on each feed. Report P(match) by lag Λ = 0..120 ms per feed and per wallet.
3. **The discriminating subset.** Orders for which, inside [arrival - 120, arrival - 10], the CLOB channel shows a best ask that
   PolyBolt never displays.
   - A CLOB reader's limit equals that transient at its base rate.
   - A PolyBolt reader's limit equals it about never.
4. Add the matching control: transient states that PolyBolt does show late.

**Data.** `btc5m_clob_raw2` and `btc5m_pb` (on disk, 06-12), P1's calldata.

**Signature if true.**
- The limits equal CLOB-only transients in <= 10% of the CLOB-reader expectation.
- The view profile on PolyBolt's own timeline peaks at Λ ≈ 0-10 ms.
- The same holds for every wallet, or XM differs, which would explain its +1 / +2 c spread as a stale view.

If true:
- the timing / price component gains a decoded input;
- the per-wallet view edges for X151 / X155 come from the feed, not from a host;
- the condition-2 cut argument gains a physical anchor: any CLOB-channel participant sees the makers' cancels ~27 ms before the
  bot can.

**If false.** The limits match CLOB-only transients at the CLOB rate. Then the bot reads the market channel, and the 30-ms
staleness is its own processing or queueing, which bounds the hold-race account.

### P4. Audit the Binance book clock before the exam, and re-score condition 2 with the corrected stamp (new; guards conditions 2 and 3)

**Hypothesis.** The capture's spot-book Te = receive - 131 ms is early, because bookTicker leads the trade stream (critique 3). The
decoded hazard and dc14 therefore see ~2-3 ms (median) and up to ~15 ms (tail) of Binance book events after their nominal cut.

**Why it fits.**
- The live lead is 4.6 ms median, 94% bookTicker first.
- In the capture it is 4 ms median, 80-86% first, q5 16-20 ms.
- The condition-2 margin is +0.058 with a CI lower bound of 0.050, decided at the scale of tens of ms.

**Test.**
1. In each capture day file, estimate the book-to-trade lead on level-clearing pairs (`capbtorder.py`), by hour.
2. Re-time book rows as Te' = receive - (trade transit_hour - lead_hour), with a conservative variant at the q90 lead.
3. Re-score both pre-registered splits once each: dc14 side, and the hazard's gain over PMB at the e cut, with the Polymarket cut
   unchanged.
4. Pre-register the corrected clock in final_rule.py before the exam.

**Data.** The capture day files on disk (`it13/hf_dl/btc_*`), plus a 30-minute live calibration in a development block (combined
bookTicker + trade + `depth@100ms`, whose E and u give a third anchor).

**Signature if true.**
- Side changes by < 0.5 point and the gain stays >= 0.05 at both the median and the q90 correction. The claim is then
  examiner-proof on this point.
- If the gain falls under 0.05 at the q90 correction, condition 2 needs a larger margin (P1's out-of-time block or a finer
  label band) before it is claimed.

### P5. The bot's fair value prices with short-dated implied vol: test it on the large class and the window lean (strong form of X7 / X117 / X30 for size)

**Hypothesis.** The large-order intent (and with it the window's large lean) follows the edge under a digital priced at implied
vol. The relevant vol is short-dated option IV or DVOL, not the 300-s realized vol that size16's G6 uses.

A time-varying IV / RV ratio is an input that G6's trees cannot reconstruct from lnSK, tau and sig300.

**Why it fits.**
- Large orders are more underdog-tilted than small ones (68.7% vs 58.3% at |p - 0.5| 0.3-0.4; other takers 34.8%; X30).
- The revealed vol multiplier is 2-3 times realized and tracks DVOL / RV (quartiles 1.53 / 2.11 / 2.85; X7).
- The value side under an RV digital is anti-value (0.4495; X124).

**Test.**
1. σ_IV(t) comes from two sources:
   - DVOL 1-min, already in the HTTP cache through iv13.py's `dvol_minutes`;
   - Deribit `public/get_last_trades_by_currency_and_time` (kind=option), keeping the `iv` of near-ATM trades in the nearest
     daily expiry over the last 15 minutes. That gives 10-17..22 for the capture days.
2. edge_IV = Φ(lnSK / (σ_IV √τ)) - ask_o at the decision. Add edge_IV, σ_IV / σ_RV and the IV-edge sign to size16's public group.
3. Fit on 10-20 and score on 10-21..22, and the reverse.
4. At the window level, test the share of windows whose final large-net sign equals sign(edge_IV) at the first large order.

**Data.** Deribit public API (no key), the HTTP cache, size16's frame.

**Signature if true.**
- GF / XM within-wallet public AUC +0.03 or more over G6.
- Window-lean agreement > 60% against a placebo of ~50%.
- The ladder r(N) with E[class] from the IV model above 0.45 on the true decisions.

**If false.** No gain. That leaves the size coin to own state (P2) and to the PRNG (X149), and the information lens has no
further candidate for it.

## Sources

- **Binance spot streams** (development block, nothing stored):
  - `wss://stream.binance.com:9443/ws/btcusdt@bookTicker`;
  - `wss://data-stream.binance.vision/ws/btcusdt@bookTicker`;
  - `wss://stream.binance.com:443/stream?streams=btcusdt@bookTicker/btcusdt@trade`.
- **PolyBolt:** `price.polymarket` as recorded by `rec_pb10.py` (feed `btc5m_pb`), envelope `ts` producer ms, `pt` payload ms,
  `x` dropped.
- **data-api** `/activity` through `PolymarketData().activity`: operator wallets, development periods only.
- **Deribit public API:** `get_volatility_index_data` (cached by iv13.py) and `get_last_trades_by_currency_and_time` (not yet
  fetched; no key).
