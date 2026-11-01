# Panel, iteration 15: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

Written 11-01 ~07:35 UTC.

## Data used for my checks

Development data only. I ran `sealed.py btc5m-bot` at 07:28 UTC: released none, current block 11-01 06-12 is development.
Nothing was opened from `.cache/live/sealed/`, from any capture day at or after H, or from another strategy's workspace.
Every process stayed under 300 MB.

- **Session-scratchpad frames of the investigation:**
  - `it14/dcclock14_frame.parquet`, `it14/dcclock14_crowd.parquet`, `it14/dcfit14_pred.parquet`;
  - `it15/l2ordb_2026-10-20.*` (o's 100-level ask vector at 16 offsets m - 1 .. m - 500), `it15/depth15_orders.parquet`,
    `it15/cl_orders.parquet`;
  - `it13/hf_dl/` (`btc_<day>` Binance spot book and trades, `pm_touch_2026-10-20/21`, `pm_trades_*`, `btcrtds_*`).
- **From the strategy cache:** `windows.parquet`, and `fills.parquet` restricted to the 10-20 windows.
- **Live, development block, nothing stored:**
  - 12 s each of Binance spot `btcusdt@depth@100ms`, USD-M `btcusdt@depth@100ms` / `@depth@500ms` and spot `@kline_1s` at
    07:07 UTC (event stamps only);
  - the public PolyBolt contract `https://ws-live-v2.polymarket.com/asyncapi.json` (HTTP 200, 63 KB).

Scripts and outputs are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p15i\`:

| script | what it checks |
|---|---|
| `relladder.py` | oracle ladder on 10-20 with depth at the release instant, and with the size class known |
| `sizebook.py` | which decision-time inputs separate large from small orders (calldata orders) |
| `envelope.py` / `envelope2.py` / `envelope3.py` | how fast any Polymarket maker moves the BTC 5m touch after a Binance spot move |
| `oplag.py` | the operator's first-leg hazard after the same clean onsets |
| `phase.py` / `phase2.py` / `phase3.py`, `depthphase.py` | UTC phase locks of operator and crowd matches; emission phase of Binance batched streams |
| `lamw.py` | per-wallet limit vs o's ask at 16 offsets before the match |
| `fillphase.py` | survival of visible depth through the hold by UTC phase |

**On the scored days.** I looked only at aggregates of 10-20..22, which are pre-registered scoring days. Any constant
below must be chosen on 10-17..19 or from physics before it is scored.

## Critique

### 1. Condition 5 is bound by the large-size class, not by the makers' cancel race

Iteration 15 says that about 0.3 of the window-net r on the true decisions is set by the makers' cancellations inside the
hold. On 10-20 the gap belongs to which orders were large.

The check (`relladder.py`):
- 265 windows, 27,008 true operator taker orders, N = window net over both roles;
- depth at or below the public limit L = o's best ask at m - 180 + c_w (DS 0, GF 1, XM 1 c);
- "class known" means 100 if the order's realized total fill (osz) is above 30, else 30. This is a lower bound of the true
  large flag: large orders that filled 30 or less count as small, which changes N little.

| per-order size | r(N), true side | r(N), dc14 p | PnL r P / S (dc14 p) |
|---|---|---|---|
| public menu (constant E[size]) | 0.433 | 0.481 | 0.426 / 0.411 |
| min(menu, depth at the bot's view, m - 180) | 0.457 | 0.506 | 0.447 / 0.415 |
| min(menu, depth at the release, m - 35) | 0.461 | 0.555 | 0.509 / 0.455 |
| **size class known** | **0.911** | **0.781** | **0.732 / 0.739** |
| size class known, capped at the release depth | 0.861 | 0.771 | 0.727 / 0.706 |
| true total fill | 0.946 | 0.816 | 0.768 / 0.766 |

What this shows:
- **The large leg is the net.** The large orders' part of the net correlates 0.775 with N; the small orders' part
  correlates -0.002. Large orders are 8% of taker orders: DS 3.1%, GF 17.7%, XM 20.1%.
- **Depth predicts the small fill, not the net.** min(menu, depth at the release) correlates 0.46 with the filled taker
  shares, against 0.14 for depth at the bot's view. It still adds at most 0.07 to r(N).
- **The class is worth 0.30-0.48 of r(N).** Once the class is known, capping by depth lowers r(N), because large orders'
  remainders rest at L and fill as maker.

Next step 3 (the cancel race from level age and size patterns) can at best move the small leg. **The lever for condition 5
is the large decision.**

What I found on the large decision, on 3,718 calldata orders of 10-20..22 (455 large; `sizebook.py`), as the AUC of each
single input for large:

| input | DS | GF | XM |
|---|---|---|---|
| thin depth at the view (1 - AUC of depth at m - 180) | 0.649 | 0.513 | 0.559 |
| time in window | 0.625 | 0.409 | 0.331 |
| leg rank | 0.622 | 0.578 | 0.490 |
| 1-s spot microprice toward o | 0.588 | 0.566 | 0.613 |
| dc14 confidence | 0.482 | 0.574 | 0.583 |

No single public input exceeds 0.65. The iteration-14 mechanics panel's own-net lookup reaches r(N) 0.601. The class oracle
says 0.78 is there with the dc14 side.

### 2. No London maker reacts to a Binance move before the bot's view, so the e cut is physics, not generosity

The condition-2 result hinges on the book cut: +0.058 / +0.081 with the book cut at e, and +0.008 / +0.023 at e + 50. That
can be settled by measuring when anyone in London can first react, not only by the bot's own λ.

**The test** (`envelope3.py`, `oplag.py`):
- clean Binance spot onsets: a move of 1 bp or more within 50 ms on exchange-ms trades, after 500 ms with a range under
  0.5 bp, 1-s refractory;
- 3,860 onsets on 10-20 and 10-21 (the days with the capture's touch), 6,168 onset-token pairs;
- placebo: the same token 2-20 s earlier.

The hazard ratio (event / placebo) of the first directional move of a BTC 5m touch (Up's ask down or bid up after an up
move, and the mirror), on the book clock, by lag after the Binance stamp:

| lag (ms) | 0-50 | 60-120 | 130-170 | 180-230 | 240-290 |
|---|---|---|---|---|---|
| makers' touch moves (10-ms bins) | 0.95-1.48 (activity bias, mean ~1.2) | 1.5-1.8 | 2.3-3.5 | 3.2-5.3 | 4.5-7.8 (takers' releases) |

The operator's first-leg matches after the same onsets (trade clock, 50-ms bins):
- 1.5 / 2.1 / 1.7 at 0-150 ms;
- 2.9 at 150-200, 4.4 at 200-250;
- a peak of 8.1 at 250-300.

That is the 260-ms knee.

**The clocks.** The knee is m0 - 260 on Binance's clock. The bot's view is m0 - 180 on the trade clock, which is about
m0 - 205 on the book clock, because book events are stamped about 25 ms before the trades of the same match. So the bot's
view is at about stamp + 55 ms on the book clock.

The makers' first, weak excess appears about 5 ms after that. Their clear reaction (2.3x or more) starts about 75 ms after
it. Nothing visible at the touch reacts before the bot's view. So the baseline with the book at e + 50 sees 0-50 ms of
reactions that come after the view.

**The caveat.** This is the touch only. The top input of hazbook15 is the change of size at best .. best + 4 c, and
size-only cancels may come earlier than price changes. The test has to be redone on the price_change size events
(proposal 1).

### 3. The book's side information at the view cannot be fresher Binance information

On the orders dc14 gets wrong, the book at m0 - 210 is right 62% of the time. By critique 2 the London makers have not yet
reacted to the onset at the bot's view. So what the book adds is the makers' slower state (a value or stale-quote
component), or a common input that both the bot and the makers already had.

The only Binance stream never examined is the L2 depth stream. X139 has been open for two iterations, and the RabbitGo777
10-20 file's spot and USD-M depthUpdate rows have never been read.

Two facts bear on how the bot would read L2:
- **Spot depth@100ms runs on a fixed UTC grid.** In a live check its event stamps sit at E mod 100 = 14-15 ms.
- **No wallet's first legs phase-lock at 100 ms.** On six capture days the Rayleigh Z is at most 3.9 (n = 377 to 16,919 per
  wallet and day).

So no wallet triggers on spot depth snapshots, unless its path jitter exceeds ~40 ms. If L2 matters, it is as state
(depth-weighted fair value), not as the trigger. USD-M depth@100ms drifts on a ~102-ms cadence, so it can only be tested
against its own E stamps.

### 4. XM sits on the same dispatcher path; its broad knee is a different decision, not a different place

XM's broad, earlier knee and its weaker price match looked like a remote host. The fan-out gaps say no (`dcclock14_frame`,
rank-1 legs after a first leg):

| first leg -> follower | median gap (ms) | q10 / q90 (ms) |
|---|---|---|
| DS -> GF | 16 | 5 / 45 |
| DS -> XM | 25 | 7 / 49 |
| GF -> XM | 26 | 8 / 51 |
| XM -> DS | 20 | 6 / 48 |

XM's spread equals GF's. XM's orders leave the same host about 10 ms later.

What the evidence does not settle:
- **XM's Polymarket view time was never measured on the capture.** On 10-20 there are only 43 XM calldata orders (`lamw.py`).
- **A one-moment scan of the limit against the ask is confounded.** GF's limit equals the ask at m - 35 in 64.6% of orders,
  and the ask at m - 180 + 1 c in 48.7%: makers re-quote o's ask up by the match, so GF's +1 c pay-up and a later view
  look alike.
- **XM's condition-7 presence part (+0.030 at the e cut) depends on where XM's own cut lies.**

### 5. Checked, so nobody redoes them

- **Market-wide rhythm.**
  - The crowd's matches lock to the UTC second (Z 83-134 per day, phase 370-426 ms) and to 500 ms (Z 23-83).
  - DS first legs lock weakly at 500 ms on three of six days (Z 16-19, phase 363-402 ms, an amplitude of about ±1%). GF
    and XM do not.
  - RTDS Chainlink arrives 1.4-1.7 s after its own timestamp, and `@kline_1s` is emitted about 37 ms after the second. The
    crowd's 1-s clock is therefore a Binance 1-s poll, not the settlement feed.
  - A UTC-phase feature belongs to the market-only class. Its amplitude makes it a negligible baseline risk.
- **Survival through the hold by UTC phase.** The visible depth's survival through the hold (D(m - 150) / D(m - 180)) is
  flat by UTC phase, 0.898-0.917 by decile of the second or of 500 ms. The makers' cancels are not poll-driven.
- **PolyBolt.**
  - `price.crypto` is gated and "about one update per second per symbol"; `price.crypto.twap` is gated.
  - `price.polymarket` is public best bid / ask, conflated when the client is slow.
  - No sub-second reference price is available there, publicly or with credentials.
- **Large size vs visible depth (pooled).** AUC 0.508. Size is not "send 100 when 100 is visible".

## Proposals (ranked by the chance they close the gap)

### P1. Fix the condition-2 cut from two measured clocks, per wallet: the bot's view and the makers' first reaction (condition 2, and condition 7's presence part)

**Hypothesis.**
- Each wallet's Polymarket view is at arrival - λ_w.
- The fastest makers' visible reaction to a Binance onset (size cancels at best .. best + 4 c) comes later than every
  wallet's view.

If both hold, a market-only participant who is as fast as the fastest maker cannot have the cancel wave by the bot's view.
The cut "book <= view_w, prints <= view_w + 25" is then point-in-time for any market-only baseline, and the +0.058 / +0.081
margin is honest. Neither the RE's planned physics cut (λ = 30 ms from the 10-31 laptop-clock live lab) nor its 10-ms grid
measures the makers' side.

**Why it fits.**
- Critique 2: touch reactions start 5-75 ms after the bot's view.
- Finding 12: the book's power appears exactly between e and e + 50.
- Finding 14: XM's margin is the smallest, and XM's view time is unknown.

**Test.**
1. **The view clock.** Fetch calldata for about 4k operator taker txs of 10-17..19 (all XM taker txs plus a DS / GF sample),
   with batched `eth_getTransactionByHash` (`fetchcrowd10.py`'s plan). For fully lost races, take the struct from the first
   maker-fill tx (X146 step 1 needs the same).
   - Keep the orders whose o-ask changed in [m - 400, m - 120] on the book clock.
   - From the capture's price_change rows at event resolution, compute P(L - c_w = o's best ask at t) on a 5-ms grid.
   - Per wallet, the latest t where it is still at the plateau is the view edge.
   - Including the lost races removes the survivorship that taker fills carry: a stale limit below a risen ask does not
     fill as taker.
2. **The maker envelope.** On the same days, with the clean-onset design of `envelope3.py`, take the hazard of size
   decreases at o's best .. best + 4 c (askSize decreases that are not trades) by 5-ms lag against the placebo. Report the
   first lag above the activity-bias level.
3. **Pre-register and score.** Pre-register cut_w = view edge_w - 5 ms and the decision-clock presence unit with the
   fill-covering label. Score once on the days whose book has not been used (10-17..19 with the L2 ingest, or the reverse
   split).

**Data.**
- Polygon RPC (drpc, batched; about 2.7 KB per tx, keeping decoded fields only).
- The capture's polymarket day files for 10-17..19: price_change askPrice / askSize / exchangeTimestampMs / tokenId, by row
  groups, about 0.6 GB of range requests per day (`l2ingest15.py`'s reader, event-level output for the queried tokens only).
- The capture's Binance spot trades (exchange ms), already in `it13/hf_dl`.

**Signature if true.**
- DS / GF view edges within about 10 ms of m0 - 180 on the trade clock.
- The size-cancel envelope's first excess at least 10 ms after the earliest view edge.
- Per-wallet gain at cut_w of 0.05 or more with a CI lower bound above 0 for DS and GF.
- If XM's edge is 30 ms or more earlier, XM's gain at its own cut rises from +0.030 toward 0.05.

**If false.** Size cancels start before the bot's view. Then some makers are as fast as or faster than the bot, and the
book at the view carries the trigger. Condition 2 at the decision clock fails against any honest book-aware baseline, and
the account must say that the operator is one of several equal-speed reactors.

### P2. Condition 5 is the large-size decision: look for its input in public data at the physical cut, over the full population of large orders (strong form of X130 / X132)

**Hypothesis.** The window net is the large leg (critique 1). The large decision is keyed to state observable at the
decision. Candidates, in order:
- (i) conviction across feeds at their physical cuts (spot L1 plus USD-M plus ETH agreement, the L2 state of P3);
- (ii) the Polymarket book at the view: o's thin depth (DS AUC 0.65), the size of the cancel wave, and the other outcome's
  book;
- (iii) the window arm and minute;
- (iv) the rule's own exposure deficit. This is a target-tracking controller that sends 100 when its realized leg is far
  below its target. It is own state: legitimate for the policy and for a replica, but reported separately.

**Why it fits.**
- Class known: r(N) 0.911 / 0.781 against 0.433 / 0.481 for the menu.
- Only 455 large calldata orders exist, too few for per-wallet models.
- The inputs tested so far were the knee move and |p - 0.5|. Neither the book at the view nor the cross-feed agreement has
  been tried.

**Test.**
1. Label every taker order of 10-17..22 by size class from on-chain order-hash totals. A total of taker plus maker fills
   above the (day, arm) small menu size means large; mind the 30 / 50 menus of 10-17 / 10-18 (size14). Take calldata only
   for hashes at or below the small size that have a remainder. That gives several thousand large orders (8% of 10-20's
   taker orders), not 455.
2. Per wallet, fit LightGBM P(large) on 10-17..19, adding feature groups in steps:
   - arm and minute;
   - plus the book at the view;
   - plus all feeds at their physical cuts;
   - plus the rule-own deficit (reported separately).
3. Score once on 10-20..22.
4. Run the ladder r(N) with E[class] times the dc14 side, then trk_a with that target.

**Data.** `fills.parquet` order hashes; a calldata top-up for the ambiguous hashes; the capture's book (critique 1's
offsets); the venue series on disk.

**Signature if true.**
- Within-wallet AUC of 0.75 or more from public groups (without own state).
- Ladder r(N) of 0.60 or more.
- A tracker target at window-net r of about 0.56-0.58, which the iteration-14 mechanics panel computed as the bar for 0.5
  on both Pearson and Spearman.

**If false.** AUC stays at 0.65 or less on every public group, and only the own-state deficit lifts it. The large decision
is then internal (configuration, pyramiding or a coin). Condition 5 can only be carried by a replica that simulates its own
fills and state (X145). Record the class-oracle numbers as the quantitative account of the unexplained part.

### P3. Binance L2 on the subsets where the gap lives, with a batched-feed fingerprint and an out-of-time replication on the Tardis 11-01 free day (strong form of X139 / X37)

**Hypothesis.** The bot's fair value weights the Binance book beyond L1, through a depth-weighted microprice or the
depth@100ms snapshot imbalance. On the orders dc14 gets wrong, the L1 queue flickers against the deeper book and reverts.
That would give:
- the late-trigger sixth: post-horizon agreement of 0.738 against a reversal null of 0.26-0.34;
- part of the book-only takes, because the makers use the same L2 state.

**Why it fits.**
- Critique 3: what the book knows at the view is not fresher Binance information.
- Every L1 venue on disk is a lagging copy.
- The trigger is a sub-tick queue imbalance (iteration-14 finding 7), which is an L2 phenomenon one level deep.

**Test.**
1. Read RabbitGo777 10-20 spot and USD-M depthUpdate plus snapshots by row groups (`rabbit_bf13.py`'s reader, 2 threads, 429
   back-off). Rebuild L2 with the u / U / pu continuity check.
2. At each first leg's horizon (E <= m0 - 260), compute two versions of the features:
   - as of the last depth@100ms update before the horizon (the batched reading);
   - continuously.
   The features are imbalance at 1 / 5 / 10 / 20 levels, depth-weighted microprice changes over 100 / 250 ms, and add and
   cancel volume by side.
3. Pre-register the primary subsets before computing anything:
   - the dc14-wrong first legs of the score hours;
   - the book-only bins of finding 9 (top book-score decile and not top spot decile).
   Use the odd / even hour split, and its reverse.
4. **Out of time.** On 11-02, HEAD-check Tardis `binance/incremental_book_L2/2026/11/01/BTCUSDT.csv.gz` and the binance-futures
   files. Stream-reduce only the 06-12 and 18-24 development rows, never touching 00-06 or 12-18. Join the operator's
   on-chain fills of those blocks to the shared recorder's `clob_crypto` match ms, and rerun steps 2-3 frozen.

**Data.** RabbitGo777/polymarket.btc_20261020.v4.parquet (revision 1e0218e1, not gated; about 56 MB of range requests per
hour); Tardis's free first-of-month day; the `dcclock14` frame.

**Signature if true.**
- Side on dc14-wrong legs from about 0.37 to 0.60 or more.
- Pooled side +2 points or more.
- At least 50% of the book's marginal power on book-only bins absorbed by L2.
- If the snapshot-timed features beat the continuous ones, the bot reads depth@100ms (a feed fingerprint).
- The result replicates on 11-01.

**If false.** L2 adds less than 1 point. By critique 2 the residual is not in London either. Record the quantitative wall
residual: about 17% of decisions anticipate the Binance move 40-90 ms after every observable input.

### P4. XM's feed fingerprint: the same path, a different trigger (condition 7)

**Hypothesis.** XM shares the dispatcher's host (critique 4) but fires on a different stream or rule:
- USD-M L1;
- ETH;
- a longer-memory spot signal;
- or the follower role (XM's first legs might be events whose earlier leg went to W4 / W5).

The thinning model treats XM as an i.i.d. draw. A wallet-specific trigger is an input that P(wallet | state) has never been
given.

**Why it fits.**
- XM's knee is broad and earlier (0.625 already at 400 ms).
- XM's hazard AUC is the highest (0.919), so its decisions are predictable, just not as a share of the pooled stream.
- XM's fan-out gaps are normal, so path jitter does not explain the breadth.

**Test.**
1. XM-led first legs of 10-17..22 (about 4.1k). Compute the knee profile against each exact-stamped feed:
   - spot trades T;
   - USD-M BTC and ETH trades T (archives);
   - USD-M bookTicker E (Rabbit 10-20, the full day);
   - OKX / Bybit.
   The feed with the sharpest knee is XM's. Measure the knee as the rise within 20 ms.
2. Check how many XM "first legs" have a W4 / W5 leg in the preceding 300 ms (W4 / W5 fills on-chain).
3. Refit XM's allocation and hazard with its own feed and anchor, then rerun the thin15 ceiling.

**Data.** On disk, plus the Rabbit 10-20 USD-M rows (`rabbit_bf13.py` with all hours).

**Signature if true.**
- One feed gives XM a sharp knee (a rise of 0.08 or more within 20 ms), or 20% or more of XM first legs follow a W4 / W5
  leg.
- An XM-specific model lifts the XM-vs-rest AUC from 0.805 toward 0.85, and the redraw ceiling above 0.47.

**If false.** The breadth persists on every feed. XM then fires on longer-lived moves by rule. Its PnL ceiling of 0.43-0.46
stands as a measured limit, with the fan-out evidence that it is not a location effect.

### P5. Does the bot read the Polymarket book? A kink test at the measured view (lower priority; reuses P1's data)

**Hypothesis.** Finding 9's "book-only" takes come from the bot reading the book as a confirmation, not only from
co-reaction.

**Test.**
1. On the price_change event stream, with each wallet's view edge from P1, regress the 50-ms take hazard on size cancels at
   o's best .. best + 4 c in 10-ms bins from view - 50 to view + 50.
2. If the bot reads the book, cancels just before the view raise P(take) by a step that cancels just after it do not. A
   kink with the bot's read latency would appear at the edge. Co-reaction gives a smooth function across the edge.

**Data.** P1's.

**Signature if true.** A discontinuity of 1.5x or more at view - r for a fixed r (0-20 ms). The Polymarket book at the view
then becomes a decoded input of the take and the side (dc14 + book 0.838). Book state is market activity, so this changes
the strategy statement, not the presence gain.

**If false.** The function is smooth across the edge: a co-reaction, and the book stays out of the rule.

## Sources

- **PolyBolt contract:** `https://ws-live-v2.polymarket.com/asyncapi.json` (title "Polymarket PolyBolt WebSocket 2.0.0").
  Channels `price.polymarket` (public), `price.crypto`, `price.equity` and their `.twap` variants (gated by an Access Token
  or CLOB credentials).
- **Binance stream cadences:** live, 07:07 UTC 11-01, development block, nothing stored.
  - Spot `@depth@100ms`: E steps of 100 ms at a fixed UTC phase of 14-15 ms.
  - USD-M `@depth@100ms`: 102 ms, drifting.
  - USD-M `@depth@500ms`: 502 ms.
  - Spot `@kline_1s`: E about 37 ms after the second.
