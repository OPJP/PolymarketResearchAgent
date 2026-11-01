# Panel, iteration 18: information source and data

Reviewer lens: what the operator sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

Written 11-01 ~12:40 UTC.

## Data used for my checks

Development data only. I ran `sealed.py btc5m-bot` at 12:02 UTC: no lots released, future examined until 10-31 00:00, and the
current block (11-01 12-18) is sealed. So I connected to no live feed and read nothing from `.cache/live/`. Every market, fill and
tape row I read starts before H. Nothing was opened from another strategy's workspace. Every process stayed under 300 MB.

- **Investigation frames (10-20..22):** `it18/sib_frame.parquet`, `it16/tapes/*.parquet` (VALIDATE window tapes), `it16/cdfull_*.parquet`,
  `it15/l2ord_*`, `it15/l2grid_2026-10-21.parquet`, `it15/depth15_orders.parquet`, `it14/dcfit14_pred.parquet`,
  `it13/hf_dl/pm_trades_2026-10-20..22.parquet` (capture server-ms matches by tx hash), and `.cache/re/btc5m-bot/fills.parquet`
  (rows before H only).
- **Public documents and metadata (not market data):**
  - Polymarket docs: rate limits, per-signer trading rate limits, real-time data, post-order schema;
  - the legacy RTDS client README;
  - the PolyBolt AsyncAPI contract;
  - Polymarket Perps instrument metadata (no prices read);
  - the npm registry `time` fields of five `@polymarket/*` packages;
  - the public GitHub tree, three source files, and commit timestamps and titles of `Polymarket/ts-sdk`. I used no author
    identities.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p18i\`:

| script | what it checks |
|---|---|
| `w45_tape.py` | W4 / W5 BUY prints on the 10-20..22 tapes: count, sizes, how many pass sib18's `size >= 60` |
| `siblag.py` | the sibling state S_sib split into coverage and accuracy, under several PIT lags and large-print definitions |
| `filterloss.py` | how much the `filled >= 60` filter alone degrades an otherwise exact size state (the cluster's own record) |
| `sibnet.py` | the siblings' own window net against the cluster's |
| `stale.py` | whether persistent ask depth, a slow-maker proxy, predicts fills or the large class |
| `blockmap.py` | the Polygon block conveyor: in which block a match lands |
| `deploy.py`, `pushgap.py` | whole-cluster outages against public `@polymarket/client` CI events and pushes to `ts-sdk` main |

## Critique

### 1. Iteration 18's partial result is mostly a coverage artefact of how a sibling large print was defined

sib18 counts an order as agreeing only when S_sib equals the true S. If there is no sibling print yet, S_sib = 0, and the order
counts as a disagreement. Split into its two factors, the sibling state is right about as often as the panel's 0.814 said:

| day | coverage (S_sib set) | accuracy where set | agreement as scored |
|---|---|---|---|
| 10-20 | 0.527 | 0.820 | 0.432 |
| 10-21 | 0.625 | 0.818 | 0.512 |
| 10-22 | 0.613 | 0.784 | 0.481 |

What limits it is coverage. Coverage is limited by the definition `W4 / W5 taker BUY filled >= 60`, because most large decisions
never fill 60 shares:

- On the cluster's own complete calldata (10-20..22), only **40.4%** of large orders (original >= 90) fill >= 60 shares
  (DS 41.3%, GF 40.0%, XM 40.8%). The median large fill is 35.6 shares.
- By realized fill: 83% of fills of 30.5-60 shares are large, and 13-17% of fills below 30 are large. A fill of 30 is almost never
  large (0.5%).
- **The filter alone costs 0.17 of agreement on an otherwise exact state.** Built from the cluster's own large orders with a 2-s
  lag, S agrees with the true S 0.950 when it sees all of them. It agrees 0.780 when it sees only those filled >= 60, and 0.835
  with fills > 30.
- **The sibling route tracks that one-for-one.** With a menu-aware threshold (W4 fill > 30, W5 fill > 105), coverage rises from
  0.585 to 0.642 and agreement from 0.471 to 0.527 (+0.056), with accuracy where set unchanged at 0.82. The cluster analogue
  gained +0.055 from the same change. Only original sizes from calldata recover the rest.
- **The PIT lag is not the bottleneck.** Replacing `block ts + 2 s` with the print's capture server-ms match time changes
  agreement from 0.471 to 0.497. Block ts minus match is 1.49 / 2.23 / 2.98 s (q10 / 50 / 90).
- **W5 carries almost no S information.** Where W5's large print is the latest, it is right 0.55 of the time; W4's is right
  0.841. Adding W5 raises coverage by 0.035 and lowers accuracy from 0.841 to 0.806.
- Sibling prints of any size cover 0.92 of orders but are right only 0.51 of the time. The small stream is the two-sided pairing
  flow and is not a lean.
- W4's own taker orders are **not** in `cdfull16` (zero W4 / W5 taker orders on 10-20..22; that fetch covered DS / GF / XM txs).
  So their original sizes have never been read.

The verdict "the per-decision draw and E remain undecoded" is premature. The measured residual is to a large extent the 59.5% of
W4's large decisions that the `filled >= 60` rule cannot see.

### 2. The out-of-time side test is waiting on examiner access it does not need

The 11-01 failure (0.718, or 0.752 on the local clock) comes from the laptop's receive clock on the Binance book stream:
- the clock drifted from −637 to −1161 ms;
- the book stream lags in bursts at the knee;
- it carries no exchange stamp.

But two Binance streams already on disk carry exchange stamps: spot `@trade` (T) and USD-M `bookTicker` (E / T). The Polymarket
match time is a server stamp. A side or timing route built only from exchange-stamped inputs has no laptop clock in it at all. It
can be scored in time and out of time with the same design today, without the capture's 10-31 file (X178 / X189) and without a
restamp model (X179 / X183).

### 3. A missed information dimension: the operator's outages line up with Polymarket's public SDK CI

FINAL_RULE, A8 and C4b record the whole-cluster outages as "bot-side, no announcement". They are not unexplained. There are 12
whole-cluster gaps of 20 minutes or more before H, so 24 boundaries. Three of those boundaries fall within 5 minutes of a public
CI event of Polymarket's TypeScript SDK `@polymarket/client` (`Polymarket/ts-sdk`, npm canaries):

| operator event (block ts of the boundary fill) | push to ts-sdk main | canary build stamp / npm publish |
|---|---|---|
| 10-19 13:37:08, last fill before an 81-min outage | 13:33:34, "fix(data)!: handle Combo splits, merges and redemptions" (breaking) | 13:37:31 / 13:41:10 |
| 10-19 14:57:45, first fill after it (large size changed 50 -> 100 here) | 14:51:18, "support closed any identifier lookups" | 14:55:29 / 14:57:50 |
| 10-21 11:46:48, first fill after a 275-min outage | 11:41:56, "fix(bindings): accept INVALID and CANCELED_* order statuses" | **11:46:48** / 11:50:34 |

Observed: 3 boundaries within 5 minutes of a publication. To test that against chance, I shifted the publication series by
random whole days, which keeps time of day:
- 5-minute window: null mean 0.27, p < 0.00025 (0 of 4,000 draws reached 3);
- 10-minute window: p < 0.00025;
- 20-minute window: p 0.061;
- a plain circular shift instead: p 0.0007.

The three events fall 3.6, 6.4 and 4.8 minutes after a push to main. That is the lag of an automated pipeline that tracks main,
about the same as Polymarket's own CI job start (4.0, 4.2 and 4.9 minutes).

What does not align:
- There is no general restart signature after the other ~54 pushes. The share of pushes followed by a fill gap of 150 s or more
  within 2-10 minutes is 0.386, against 0.465 under the null.
- The 10-21 dispatch-share jump (GF's share of first legs 0.18 -> 0.44 at 15:40) does not line up with a push.
- Neither does XM's 10-13 14:10 drop.

Why the operator does not simply run ts-sdk: its order salts are the legacy `Math.random() * Date.now()`. ts-sdk has drawn 53-bit
`crypto.getRandomValues` salts since 05-14 ("fix(client): generate order salts with crypto randomness").

So the likely mechanism is that the bot's market data, discovery and order-status path depends on code or a service that these
pushes change. Breaking changes stop the whole cluster while the markets keep trading; fixes restart it. The 10-19 restart is
also where a configuration change appears. This is a public clock for some of the "configuration" events, and a window onto the
bot's I/O layer. Both feed open items: the version parameters across exam lots, X166 (which Polymarket channel the bot reads) and
the X146 cut.

### 4. Condition 2 at the block-second unit is structurally co-occurrence-bound; no new feed will fix it there

Polygon blocks alternate 1-s and 2-s gaps (5,996 / 5,954 consecutive gaps; 1.5003 s per block). Of the operator's 10-20 taker txs:
- 78.5% land in the second block stamped after the match;
- 91-95% do so when the first block falls 0.5-1.5 s after the match;
- block ts minus match is 1.25 / 2.20 / 3.13 s (q05 / 50 / 95).

So a block-second label sits about 2.2 s after the decision. Every co-reaction in that interval is point-in-time for the baseline:
the fast crowd's co-takes at m ± 100 ms, and the makers' cancel wave. That is the +0.024 against the capture-aware baseline.

Information cannot move that number. Only a decision-clock unit with a cut fixed from physics can (X146 / X190). Proposal P3 adds
the physics: the channel the bot reads (see below).

### 5. Checked, so nobody redoes them

- **Rate limits are not the take coin, and the five wallets are not rate-limit slots.** Polymarket's per-signer token buckets
  (trading-rate-limits.md) give 40 orders/s (burst 60) at Standard up to 600/s (burst 900) at Elite. Tiers follow the maker
  wallet's 30-day volume and refresh every 3 h; warning mode started 07-24. The Cloudflare IP limits allow POST /order
  5,000 / 10 s and 120,000 / 10 min. The operator's rates (DS ~27k taker orders on 10-20, ~0.3/s) are about two orders of
  magnitude below. Close `rate_limits_api` as no_effect, with this source.
- **Persistent ask depth does not predict fills** (a crude slow-maker proxy; 10-21, 608 depth-bound orders):
  - realized fill vs depth at <= L at the bot's view: Pearson 0.508 / Spearman 0.238;
  - vs the minimum depth over the previous 0.5 / 1 / 2 s: 0.367 / 0.361 / 0.303 Pearson;
  - the median over 2 s is 0: the bot's L is usually an ask that appeared within the last 2 s.

  The "stale levels survive" idea (NOTES iteration 15, Next 3a) would need order-level queue reconstruction from event-level
  `price_change` rows. Low prior.
- **The siblings' own window net** correlates with the cluster's at only 0.30-0.33 (cut at 60-300 s). A direct copy of it would
  not beat the tracker's window-net r of 0.51. Its value is the lean side (critique 1).
- **The legacy RTDS has a public `activity` topic** (`trades`, `orders_matched`; no auth; filter `market_slug`). Its payload
  carries proxyWallet, size, price, transactionHash and timestamp. It is the only feed that attributes trades to wallets before
  the block. It was never recorded. Given critique 1, its lag advantage is worth only about +0.026 of S agreement, so it is not a
  priority. I did not connect to it: the current block is sealed.
- **ts-sdk source** (`environments.ts`):
  - market stream `wss://ws-subscriptions-clob.polymarket.com/ws/market`, the same channel as the live lab's;
  - realtime `wss://ws-live-v2.polymarket.com/ws`;
  - market discovery through the "predictions gateway" `https://api.defi.polymarket.com`.

  The order payload carries `deferExec` and `postOnly` (GTC / GTD only), and responses can have status `delayed` (the taker hold).
  This bears on X184 (XM's 60-share class as post-only orders).
- **Polymarket Perps** lists a BTC-USD perpetual (public API `api.perpetuals.polymarket.com`). I read metadata only. Its market
  makers price off the same venues, so it is a lagging copy a priori. Not a priority.

## Proposals (ranked by the chance they close the gap)

### P1. Read the siblings' ORIGINAL order sizes from calldata and rebuild the size state from W4's large decisions (strong form of X182; X66 step 4)

**Hypothesis.** The operator's size state S (the side of the current large lean) is public through W4's large orders. sib18 saw
only the 40% of them that fill 60 shares or more. With original sizes from calldata, coverage rises to near the cluster analogue,
and agreement rises toward the bar.

**Why it fits.** Critique 1:
- accuracy where set is 0.78-0.82, so coverage is what binds;
- 59.5% of large orders fill below 60;
- the cluster analogue shows the filter alone costs 0.17;
- the menu-aware threshold already adds +0.056, matching the analogue one-for-one;
- lag is not binding (+0.026);
- W5 adds noise.

**Test** (all development data, fit and score splits exactly as sib18).
1. **Fetch.** Get the calldata of W4's 9,745 and W5's 650 BUY txs of 10-20..22 (their tx hashes are in the tapes):
   - batched `eth_getTransactionByHash`, 25 per POST, at most 3 POST/s, so about 420 POSTs, a few minutes on drpc;
   - decode with `code/calldata.py`;
   - keep the taker order's maker, original takerAmount, limit, signing ms and role.
2. **Pre-register "15b" before scoring.**
   - **Large decision:** a W4 order with original >= 90, taker role, usable at block ts + 2 s, shared txs excluded.
   - **W5:** report it as a separate line only, with its own class (original 210).
   - **Secondary update:** W4 maker-role fills of large originals, at their own fill block ts.
   - **Unchanged:** smach17's transition model, the true-state definitions and both splits.
   - **Bars:**
     - hybrid S agreement >= 0.75 on both splits;
     - PnL-proxy Spearman gain over the menu >= +0.15, with the 2-h block-bootstrap lower bound > 0;
     - report coverage and accuracy where set, separately.
3. **Execute.** If 15b passes, run the iteration-19 step 1 with S_cd: the mix14 tracker weighted by P(large), strict fills, both
   splits. Report it with and without W4 pending X170.
4. **Census in the same pass.** Take one pre-H hour of all BTC 5m match-tx calldata and flag every maker whose orders are signed at
   the operator's burst phases (−89.5 / +42.4 / +173.3 s). Any further carrier (W6 and so on) raises coverage again.

**Data.** Polygon RPC (drpc), the tapes on disk, sib_frame, smach17.

**Signature if true.**
- coverage >= 0.80;
- accuracy where set >= 0.85;
- public agreement >= 0.65 and hybrid >= 0.75;
- PnL-proxy Spearman >= 0.40 / 0.58 (now 0.336 / 0.511);
- the executable tracker's Spearman >= 0.50 on both splits, which is condition 5's missing 0.033.

**If false.** Calldata coverage rises but agreement stays at or below 0.60. Then W4's legs are a biased subset of decisions (its
slot sits after DS and GF), and the bias should be quantified by slot. Then what remains private is the part of S that W4 never
carries, with a number attached.

### P2. A clock-free out-of-time transfer test from exchange-stamped Binance messages only (settles H7 against a regime change without the examiner; complements X178 / X179 / X183)

**Hypothesis.** The decision side and the knee transfer to the post-T0 regime. The 0.718 / 0.752 on 11-01 is the receive clock of
the book stream (critique 2), not the version.

**Test.**
1. **Pre-register, with no book stream anywhere.** Fit a book-free knee-clock model on the capture's trade rows
   (`exchangeTimestampMs` = T) of 10-17..19:
   - **Inputs:** signed trade-price return and signed aggressive notional toward o over K = 100 / 250 / 500 ms ending at X.
   - **Anchor:** X = m − c on Binance's clock, with c scanned on the fit days only (iteration 14's trade knee was ~220 ms), then
     frozen.
2. **Score once, nothing refitted.**
   - **In time:** on 10-20..22.
   - **Out of time:** on the 999 orders of 11-01 06-12. Use the T-stamped spot `@trade` messages of `btc5m_bnspot2` and the
     server-ms matches (oot17).
3. **Variant on USD-M** (the stamps there are E / T). Fit on the RabbitGo777 10-20 file (`E_`), score on `btc5m_bnusdm2`.
4. **The next development blocks** (11-01 18-24, 11-02 00-06, 11-02 12-18). Collect inputs in one of two ways:
   - a minimal recorder of spot `@trade` and USD-M `bookTicker`, both exchange-stamped, through the Writer with a hard stop;
   - or, with no recorder, Binance REST `/api/v3/aggTrades` with startTime / endTime inside the development blocks only.
5. **Bar and report.** The bar is A_out >= A_in − 0.02 per order, pooled. Report it per wallet, with the m ± 3 s placebo and a
   cut-shift scan. Run the same design for the trades-only hazard at the e cut.

**Signature if true.**
- out-of-time within 2 points of in-time;
- the cut-shift optimum at 0 ± 10 ms;
- the same per-wallet pattern.

The frozen book route then needs only a clean book clock (X178 / X183), and the version parameters stay as stated.

**If false.** A drop of 5 points or more on clean clocks. Then the decision side changed with the version, and dc14 must be refit
on post-T0 development blocks before any exam on h1 / h2 or on future blocks. That is better learned before an exam round is
spent.

### P3. The operator's software supply chain as an information source: date its restarts, configuration resets and Polymarket view from Polymarket's public SDK pipeline (new; E5 / C8 / operator_schedule_config)

**Hypothesis.** The bot's I/O layer depends on code or services that pushes to `Polymarket/ts-sdk` main change: market discovery
through the predictions gateway, order-status parsing, the market stream. So:
- breaking pushes and fixes start and end whole-cluster outages (critique 3);
- restarts are where configuration changes take effect and in-memory state resets (S / E, arms, dispatch);
- the market stream the bot reads is the CLOB channel `ws-subscriptions-clob` that ts-sdk is configured for.

**Why it fits.**
- Three of 24 outage boundaries fall within 5 minutes of a ts-sdk CI event; one matches a canary build stamp to the second
  (p < 0.00025 with time of day preserved).
- All three are 3.6-6.5 minutes after a push to main.
- The 10-19 restart carried the 50 -> 100 size change.
- X166 already leaned to the CLOB channel (its server-stamp profile peaks at a 30-ms view lag).

**Test.**
1. **Confirm on events not used here, pre-registered.**
   - **Events:** every whole-cluster gap of 10 minutes or more on all development days back to the operator's first trades, and on
     the post-T0 development blocks.
   - **A sharper restart detector:** orders signed OFF the ladder schedule (sign rel more than ±3 s from −89.5 / +42.4 /
     +173.3 s) in calldata. A restarted process should re-sign its ladder at once. Use the complete 10-20..22 and 11-01 records
     and the sample hours.
   - **Against:** ts-sdk pushes (+0..10 min), and as controls the pushes of clob-client-v2, clob-client and
     real-time-data-client, and the docs changelog entries.
   - **Null and bar:** whole-day-shift null; window fixed at 10 minutes; p <= 0.01.
2. **If it confirms, read the bot's I/O from the public source and measure it.**
   - **Polymarket view lag (X146):** the bot's view = the arrival minus the CLOB channel's latency. Measure that latency at the
     capture's own vantage, and fix condition 2's decision-clock cut from it, rather than choosing between e and e + 50.
   - **Market discovery:** test whether the outage starts follow gateway or Gamma listing anomalies (late or failed listings of the
     next window).
   - **State resets:** after each detected restart, is the first large decision a fresh seed (S reset)? Do the arms and size
     phases restart? If so, the replica resets S / E at the same public times.
3. **A version clock for the exams.** List the public ts-sdk pushes in [10-23, 10-31). This is software metadata, not data of
   sealed units. Give them to the examiner as candidate switch times for the h1 / h2 diagnosis, since the regime switch lies
   between 10-22 and 10-31. In the frozen rule, state version boundaries as "at a restart", not as calendar dates.

**Data.** npm registry `time` fields; the GitHub commit API (timestamps and titles only; 60 requests/h without a token); the
strategy's fills and calldata; Gamma listing times.

**Signature if true.**
- p <= 0.01 on the fresh events;
- off-schedule signing bursts at push + 3-7 minutes;
- menu or class-rate changes only at restarts;
- the measured CLOB-channel latency equal to the 30-ms view lag of X98 / X166.

**What it buys.**
- **Condition 7:** version boundaries become public, so replication across the halves of a lot that spans a switch can be
  handled honestly.
- **Condition 2:** the cut gets its physics.
- **E5:** the configuration schedule gets a public driver instead of "private configuration".

**If false.** The fresh events show no alignment. Then record the three coincidences as a one-off incident pair and close E5's
software route with its numbers.

**Sensitivity.** Commit metadata includes author names and emails. Use timestamps and titles only, and identify no individual.
Whatever the mechanism, the question is timing, not who the operator is.

## Sources

- Polymarket docs:
  - https://docs.polymarket.com/api-reference/rate-limits.md and https://docs.polymarket.com/api-reference/trading-rate-limits.md
    (per-signer token buckets and tiers);
  - https://docs.polymarket.com/market-data/realtime-data.md;
  - https://docs.polymarket.com/api-reference/trade/post-a-new-order.md (`deferExec`, `postOnly`, `delayed` status).
- Legacy RTDS client README (`activity` topic):
  https://raw.githubusercontent.com/Polymarket/real-time-data-client/main/README.md
- PolyBolt contract: https://ws-live-v2.polymarket.com/asyncapi.json (channels price.polymarket / crypto / equity; sources
  chainlink, pyth; gated).
- npm registry: https://registry.npmjs.org/@polymarket%2fclient (also clob-client-v2, clob-client, order-utils,
  real-time-data-client).
- ts-sdk source and history:
  - https://github.com/Polymarket/ts-sdk (packages/client/src/environments.ts,
    packages/client/src/actions/orders/orders.ts, post.ts);
  - commits API `https://api.github.com/repos/Polymarket/ts-sdk/commits` (timestamps and titles).
- Polymarket Perps: https://api.perpetuals.polymarket.com/v1/info/instruments (metadata only).
