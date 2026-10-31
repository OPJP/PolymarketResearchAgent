# tommy-cs2-maker: lab notebook

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`. CS2 in-play; taker until 15 Oct, two-sided maker from 16 Oct.
Frozen: as_of 1793318400 (2026-10-30), holdout H = 1792713600 (2026-10-23 00:00 UTC). Nothing at or after H is requested
(every fetch ends at H-1; the universe drops markets listed or starting at/after H).

## Pre-registration (iteration 1, written before any VALIDATE number was computed)

- **Primary metric: `presence_auc`** = AUC on VALIDATE of a point-in-time score predicting whether the wallet receives
  at least one fill in a (market, 30-second bin). Universe: every 30-s bin from gameStartTime to gameStartTime + 4 h
  (truncated at H) of every CS2 `moneyline` / `child_moneyline` market (match winner, map winners) whose gameStartTime
  is in the split. Features use only data stamped before the bin start (tape prints at block time, listing metadata,
  external feeds at publish time + delay); **no own-state features** in the primary (a with-own-inventory variant is
  reported separately). Higher is better; comparable across iterations.
- Secondary metrics (always reported): presence AUC within the markets it traded (conditional on market choice);
  selection AUC of its maker rows among all maker rows on the same tapes; side accuracy given a fill vs. the best
  market-only baseline; price within one tick (0.001 / 0.01); per-market PnL correlation rule vs. wallet; strict
  maker backtest return.
- **Split** (by market gameStartTime, maker regime only): BUILD = [2026-10-16 00:00, 2026-10-21 00:00),
  VALIDATE = [2026-10-21 00:00, H). The taker regime (before 16 Oct) may be used for BUILD exploration only.
  VALIDATE holds about 55% of the maker-regime fills (21-22 Oct are the busiest days), i.e. "last 30%+ of events".

## Data gathered (iteration 1)

- `code/fetch_activity.py`: full activity 2026-06-16 (first trade) .. H-1: 111,603 rows (106,016 TRADE, 3,343 REDEEM,
  2,129 MERGE, 93 TAKER_REBATE, 15 MAKER_REBATE); Gamma metadata for all 2,874 markets.
  Daily trade counts: 1-14 Oct 480-1,560/day, **15 Oct: 0**, 16 Oct 855, 17 Oct 3,879, 18 Oct 375, 19 Oct 6,063,
  20 Oct 5,236, 21 Oct 10,721, 22 Oct 9,537. Maker regime (15 Oct..H): 229 markets in 80 events, 96% CS2, 4% Dota 2;
  only match-winner (`moneyline`) and map-winner (`child_moneyline`) markets, never totals / handicaps / props.
- Market facts (Gamma): all its markets have `secondsDelay` = 1 (in-play taker delay), `clearBookOnStart` = true,
  tick 0.001, fee `sports_fees_v3` (rate 0.05, taker only, maker rebate share 0.15), rewardsMaxSpread 4.5c,
  rewardsMinSize 50, orderMinSize 5.
- `code/fetch_universe.py`: every Gamma CS2 event (series 10310) listed 25 Sep..H: 16,413 markets, ~100-200
  moneyline + child_moneyline per day. Universe metadata: league, leagueTier (2..5), pandascore id.
- `code/fetch_chain.py`: V2 OrderFilled with topic2 = wallet, blocks from 2026-10-04 to H-1 (publicnode, 4,000-block
  getLogs, logs carry blockTimestamp).
- `code/fetch_tapes.py`: full + taker-only tapes of every traded market (game start >= 16 Oct) and of every untraded
  CS2 match / map-winner market in the same period.
- bo3.gg API reachable (HLTV 403): `/api/v2/matches/finished?date=YYYY-MM-DD`, `/api/v1/matches/<slug>?with=games`,
  `/api/v1/games/<id>/rounds` (round_number, round_duration ns, end_reason, winner side, scores, equipment values;
  parsed from demos after the match, **no per-round wall clock**, only game `begin_at`).

## Hypotheses (ledger; details below)

(see state.json)

---

# Iteration 1 (restarted locally 2026-10-31 12:22 UTC under the 2026-10-31 brief)

The cloud iteration 1 was interrupted ~10 min into a local re-run (04:15-04:24 local). Found on disk: re-fetched
`activity_dev.parquet` (15-22 Oct only, 38,965 rows), `chain_fills_1792108800_1792713600.parquet` (V2 OrderFilled,
topic2 = wallet, 16 Oct..H: 36,666 rows = 34,968 maker + 1,698 taker), 1,020 windowed taker tapes (`tapes/*_tkw`),
the 30-s bins and a fill-presence LightGBM (`results_presence_iter1.json`: VALIDATE AUC 0.94-0.95, but the
market-activity-only model B0 already gets 0.942: gain ~0.01, i.e. co-occurrence; this is not a decode).
`common.py` pointed at a chain-fills file that no longer exists (fixed below); `fetch_tapes_window.py`/`build_bins.py`
were complete and had run.

## Calendar (tools/sealed.py, key tommy-cs2-maker)
Released lots: none. Development: everything before H = 2026-10-23 00:00 UTC, and the T0+ development blocks
(10-31 00-06, 12-18, ...). Sealed: [H, T0) and 10-31 06-12, 18-24, ... Nothing sealed is read. The live recorder
started ~12:07 UTC on 10-31 (status OK; clob_wallets, sports feeds connected).

## First new fact (logs): the wallet ONLY BUYS
All 36,666 on-chain fills of its orders in 16-22 Oct are side BUY (maker and taker). It never sells a token. It buys
both outcomes and MERGEs complete pairs (2,129 MERGE rows) or holds to resolution (REDEEM). So "two-sided maker" =
resting BUY orders on both outcome tokens; a bid on B at b is economically an ask on A at 1-b.

## Competing explanations (iteration 1) and what separates them
1. **E1 fast-feed cancel/requote (latency edge)**: quotes near the touch and pulls/requotes on round events seen in a
   feed faster than the public tape (GRID/HLTV scorebot/stream). Separator: order signing times (B1) lead the public
   price jumps; filled orders are young; few fills in the seconds after big public moves; post-fill markout ~0 while
   other makers' markouts are negative.
2. **E2 round-score Markov quoting**: fair value from P(win | round score, side, economy), quotes re-signed only at
   round boundaries. Separator: signing times bunch in bursts separated by ~round length; quote level matches a
   Markov value of the score (bo3.gg rounds; sports websocket scores live).
3. **E3 pair-completion spread capture**: standing bids on both outcomes with bid_A + bid_B < 1 (pair cost ~0.98),
   profits from in-game price oscillation (each side dips at some point) and merges; inventory balancing via price
   skew. Separator: sum of its concurrent bid prices, merge timing, share of PnL from merges vs. resolution.
4. **E4 static grid / ladder bot**: fixed price grid and fixed sizes, long-lived orders, refilled when filled.
   Separator: long resting lifetimes (minutes), prices on a coarse grid, constant sizes, sign times not tied to events.
5. **E5 rebate / reward harvesting**: quotes sized/placed for maker rebates (15% of taker fees) and liquidity rewards.
   Separator: sizes >= rewardsMinSize 50 within 4.5c of mid; REWARD rows (only 1 in 15-22 Oct); rebate share of PnL
   (maker rebate $5.7k of $43.7k in 17-29 Oct by the review).
6. **E6 directional skill (selection / fair value better than market)**: its unpaired inventory at resolution beats
   the market price (calibration of its net position vs outcome). Separator: residual PnL of net inventory vs market
   implied probability at the time it was acquired.
7. **E7 counterparty flow / delay exploitation**: it is the counterparty of predictable slow takers (1-s in-play taker
   delay, clearBookOnStart); edge is who it trades with. Separator: taker-address concentration in calldata, taker
   signing-to-block latency, PnL by counterparty.
8. **E8 cross-market quoting**: match-winner quotes priced off map-winner markets (or vice versa) that lead.
   Separator: lead-lag of its signing times against the other market's public prints.

## Pre-registration (kept from the cloud iteration 1; unchanged)
Primary metric `presence_auc` (30-s market bins, no own-state), split BUILD = gameStart in [10-16, 10-21),
VALIDATE = [10-21, H). Component metrics on VALIDATE: side accuracy, price within one tick (tick 0.001; also reported
at 0.01), PnL correlation. Order-level (B1) metrics added this iteration use the same split by market gameStartTime.

## Data gathered (this iteration)
- **B1 calldata, wallet**: `code/fetch_calldata.py` decoded `matchOrders` (selector 0x3c2b4399, V2 exchange
  0xe1111800...) of all 29,936 transactions with a wallet fill (16 Oct..H): 128,834 order rows, 0 undecoded, every
  wallet order mapped to its market. `code/orders.py` -> `orders.parquet`: 25,878 orders (24,180 maker, 1,698 taker),
  equal to the distinct orderHashes in the logs. Endpoint: publicnode batches of 40 work; drpc free plan rejects
  batches > 3 ("Batch of more than 3 requests are not allowed on free plan").
- **B1 calldata, everyone**: all 79,234 other public taker transactions of the wallet's 220 CS2 markets (windowed taker
  tapes) decoded into `calldata_pub/` (every taker and maker order with signing ms). Together: the full matched-order
  record of these markets inside [gs-1h, gs+4h10m].
- Sign-time sanity: some clients write seconds or ns in `timestamp`; keep 1.7e12 < sign_ms < 1.8e12.
- **Live lab** (`code/live_today.py`): the sports websocket carries CS2 per-round scores (`6-3|0-0|Bo3`, period `1/3`);
  `gameId` = PandaScore match id = Gamma `eventMetadata.pandascoreMatchId` (verified on 6 games). The 5 development-unit
  CS2 events so far today (gameStart in a dev block: CCT Europe x2, European Pro League, CyberClash, DFRAG) are all in
  leagues the wallet never traded in 16-22 Oct, and it has 0 fills in them (the selection rule predicts skip for all 5).
  **Tool bug**: `tools/live.py iter_live` raises `zlib.error` on the hour file still being written (only EOFError /
  OSError are caught), so the reader stops at the current hour. Workaround: wrap the generator in try/except.
- Gamma market parameters of CS2 match markets sampled daily 10-01..10-22: identical (sports_fees_v3 rate 0.05 taker
  only, rebateRate 0.15, secondsDelay 1, clearBookOnStart, rewards 50 / 4.5c, tick 0.001): no listing-level change at
  the 10-16 switch (C4b / X1, partly). Web search: no esports maker-rebate change found; a CFTC filing mentions a 2026
  market-maker program on Polymarket US (not checked further).

## Findings (iteration 1); numbers in results/*.json
1. **It only buys.** Every fill (maker and taker) is a BUY of one outcome token. 97.4% of the shares it buys end up
   in complete pairs (min(A,B)*2/total); weighted pair cost 0.9785, locking $21.6k on 16-22 Oct; the unpaired residual
   lost about $8.4k (it ends holding the losing side 68% of the time); settlement PnL (excluding fees and rebates)
   $13.1k (BUILD $5.1k, VALIDATE $8.0k). 99.1% of fills are in-play (after gameStart). (inventory.json)
2. **Maker quotes are ladders of 100-share BUY orders on whole cents.** 84.6% of maker orders are exactly 100 shares
   (10 shares 5.3%, 11-99 9.4%, smaller when |inventory| is smaller); 100% of prices are whole cents although the
   tick is 0.001; orders signed together form ladders 1 cent apart (gap 0.01 in 90%), bursts of 2-9 levels. Filled
   orders are young: signing to first fill median 15.8 s (p25 6.0, p75 44, p95 159), so it re-signs constantly. When
   both sides are signed within 200 ms, best bid A + best bid B has median 0.97 (p25 0.95, p75 0.98).
   (describe_orders.json)
3. **Maker timing is shared with every other maker.** Cross-correlogram of its signing times against every public
   taker's signing time (107k taker orders): 2.3x the baseline rate at [-0.5, 0) s and 3.0x at [+0.5, +1.0) s; the
   other top makers show the same shape (peak +1.0 s, 2.5-2.9x). 15% of its maker fills come from orders signed AFTER
   the taker signed (peak +0.5..+1.0 s), possible only because in-play taker orders wait secondsDelay = 1 s.
   (timing_xcorr.json)
4. **The maker quote's apparent lead over the public price is mechanical.** Its burst-top bid minus the last print
   predicts the next 10-120 s public move (corr 0.65; slope 0.46 at 10 s rising to 0.88 at 120 s; tape momentum ~0),
   but the 30 largest other makers in the same markets show the same (corr10 0.36-0.78, slope120 0.56-1.20): fill
   selection plus a stale last print. Its maker fills earn +0.47% at settlement (USD-weighted), markout +1.0c at 5 s
   decaying to -0.04c at 300 s; the next >= 4c public jump after a maker order goes its way only 42% of the time
   (control 49%). Several other makers earn more per fill (+1.2% to +4.4%). (lead_test.json, maker_compare.json,
   next_jump.json)
5. **The informed component is its TAKER orders.** 1,698 taker orders (23% exactly 1000 or 2000 shares, the rest odd
   sizes, median 542 shares / $235; limit 0-2c above the best fill, median 1c, usually one level; median 12% filled,
   like FAK limit orders; 15% of its USD volume) earn +5.98% at settlement (BUILD +6.7%, VALIDATE +5.2%) with markouts of
   -0.14c (5 s), +1.06c (30 s), +1.64c (60 s), +2.33c (300 s): no instant edge; the edge arrives with the next round
   result. The next >= 4c public jump comes sooner (median 32-37 s vs 90-94 s at random times) and goes the bought
   team's way 67.1% (BUILD, n=727) / 64.2% (VALIDATE, n=902) of the time vs 52.9% / 53.8% at random times (z about
   6); 74% / 67% when that jump comes within 60 s. Taker orders follow a drop of the bought team (22.5% after a >= 2c
   drop in 30 s vs 11.6%), but a public "buy after the drop" taker loses 4.5-9.2% on BUILD (best D=8c, W=30 s: -7.5%
   on VALIDATE) and overlaps only 3.5% of its taker orders; sibling-market (match vs map) moves do not precede them
   (3.2% vs 2.3%). Its taker side is unrelated to its inventory (49% short side, 50% long side). Reading: it predicts
   the winner of the round in progress about 30 s before the market reprices at round end, so it sees in-round state
   (kills, man advantage, bomb) from a live game feed or stream. (size_taker.json, taker_trigger.json,
   contrarian_taker.json, next_jump.json)
6. **Selection is by league (tournament), not by hour or market type.** In 16-22 Oct it traded 89.7% of tier-3, 36%
   of tier-4, 4% of tier-5 and 0% of tier-2 (Thunderpick WC) markets; by league: 1win Private Club 10/10, 1win 4/4,
   Circuit X 8/10, PGL 9/13, Stake Pulse 6/8, Stake Ranked 8/14, DraculaN 24/51, NODWIN 6/23; never CCT Europe (0/59),
   ESEA (0/37), CCT SA, ESL Challenger, United21, European Pro League, even inside 09-19 UTC. Within a traded event it
   trades 97% of the markets (all maps plus the match). VALIDATE: league score AUC 0.877, recall 0.636 at lift 2.65;
   pre-game activity baseline 0.882; combined 0.920 (gain over the baseline 0.033 < 0.05). (selection.json)
7. Economics, 16-22 Oct: settlement $13.1k = maker fills about +$4.0k + taker fills about +$9.1k; maker rebates $2.05k
   (17-22 Oct), taker rebates $2.2k; REWARD rows $1 (no liquidity-reward farming). Counterparties: 3,111 distinct
   takers, top-10 share 19% (no single victim). Co-maker 0xe8e1b119 (5-share orders) sits in 8,040 of its txs.
8. Fingerprint: signatureType 3 on every order, builder = metadata = 0, salts uniform up to Date.now() (median 9.0e11; consistent with
   `Math.round(Math.random() * Date.now())`, the TypeScript client), fixed 100-share size.

## Hypothesis ledger (iteration 1)
- E1 fast feed / in-round information: **supported for the taker component** (finding 5), not for the maker quotes.
- E2 round-boundary-only requoting (reviewer X2): **rejected in the strong form**: only 14.1% of maker signings fall
  within 15 s after a round-end proxy (control 8.1%), 59% are more than 60 s after one. The Markov valuation itself
  is untested.
- E3 pair-completion spread capture: **supported** for the maker component (97% paired, pair cost 0.978), but its
  per-fill edge is ordinary for the makers in these markets.
- E4 static grid: **rejected** (filled orders are young, median 16 s; constant re-signing).
- E5 rebates / rewards: rebates about 30% of the week's settlement PnL; rewards nil.
- E6 directional skill of the residual inventory: **rejected** (residual on the winner only 32%).
- E7 counterparty flow: no concentration; the 1-s taker delay lets its late orders fill (15%), as for other makers.
- E8 cross-market quoting: **rejected** for the taker triggers (no sibling lead).
- Presence (fill per 30-s bin) LightGBM M1 0.952 vs activity-only B0 0.942 (gain 0.010): co-occurrence, not a decode.
- Frozen v1 explicit rule (league score x in-play): presence 0.827 vs activity baseline 0.899; selection 0.877 vs 0.882.

## What is unexplained (quantitative)
- The taker trigger: 1,698 orders, about 70% of settlement PnL; their timing beats the public tape by about 30 s
  (next jump in their favour 64-67% vs 53-54%), and no public tape rule overlaps them (3.5%). Needed input: in-round
  state with a wall clock.
- Maker quote placement relative to the touch, the cancels and the inventory skew (67% of its maker fills are on the
  side it is short of): needs the order book (live lab) for markets of its leagues in development blocks.
- Why these leagues: candidate = coverage of its live data feed (which tournaments a scorebot or stream covers).

## Next iteration (plan)
1. Live lab: list Gamma CS2 events of its leagues (1win, Stake, PGL, Circuit X, DraculaN, NODWIN, ...) whose gameStart
   lies in development blocks (10-31 12-18, 11-01 06-12, 11-01 18-24, ...); extract books (clob_wallets), sports round
   scores and its fills and calldata; decode book levels of exactly 100 shares on whole cents (its ladder),
   requote/cancel timing vs round-score changes (latency of the sports feed vs its signing), taker orders vs round
   state. If clob_wallets subscribes a market too late, write an own recorder (Writer, hard stop).
2. bo3.gg: per-round data (winner, end reason, equipment, kills with in-round times if present) for its BUILD and
   VALIDATE matches; align round ends to the public price jumps; test the taker trigger against in-round state (man
   advantage, bomb plant) and economy (eco / force-buy rounds).
3. Fit a fair-value model of the taker decision (P(round win | state)) and of the maker ladder (inverse fit vs touch).
4. C1 siblings (0xe8e1b119 co-location, funding), C2 strong-form copy test, C4 change points inside the maker regime,
   C8 GitHub search for a 100-share whole-cent ladder bot.

## Late additions (iteration 1)
- Significance of the taker information (finding 5), event-level block bootstrap, 4000 draws, controls = 5 random
  times per order within +-15 min (code/next_jump_boot.py): BUILD n=725 orders / 40 events, next jump in favour
  0.672 vs 0.516, gain +0.156 [0.112, 0.199]; VALIDATE n=901 / 36 events, 0.642 vs 0.511, gain +0.130
  [0.095, 0.166]; one-sided p < 0.00025 in both.
- bo3.gg (api.bo3.gg, verified): `/api/v2/matches/finished?date=D&filter[discipline_id][eq]=1` (the discipline filter is
  required, else `query_params_error`), `/api/v1/matches/<slug>?with=games`, `/api/v1/games/<id>/rounds` (game
  begin_at; per round: round_duration in ns, end_reason, winner side, per-team equipment_value, loss_bonus_streak,
  win_streak, pistol_round). Match detail fields live_coverage / live_coverage_source are false / null for all 201
  matches of 20-22 Oct (not a selection signal). bo3.gg tier of the matched events: traded b 26, a 10, c 5; skipped
  c 70, b 40 (code/bo3_coverage.py, results/bo3_coverage.json): selection follows tournament tier and league.
- Frozen rule v1 and the target metrics: FINAL_RULE.md, code/final_rule.py, results/final_rule_validate.json.
- **Maker and taker components are coupled** (results/maker_around_taker.json): in the 30 s before a taker order,
  71% (-30..-5 s) and 75% (-5..0 s) of its filled maker orders in that market are on the same team as the taker order
  (it keeps bidding the team while sellers hit it: the reviewer's "bids pegged while the price falls"); after the taker
  order the filled maker orders turn to the other team (0-5 s 58%, 5-30 s 54%, 30-120 s 64% opposite): re-pairing.
  So the skew of the maker ladder before a taker order may carry the same in-round information; test next with books.
- bo3.gg round alignment, first try (code/bo3_rounds.py): cumulative round durations + a global (offset, gap) aligned
  only 13 of 109 maps (>= 50% of rounds matched to a jump in the bo3 winner's direction); timeouts / pauses break the
  cumulative clock. On those 13 maps (99 taker orders) the bought team won the round in progress 51% (BUILD, n=47) and
  65% (VALIDATE, n=52) vs 58% / 52% at random times: too few and too noisy. Next: piecewise alignment (sequence-align
  the bo3 round-winner sequence to the jump sequence), then in-round clock = time since the previous round end.
- **The maker ladder is informed exactly when the taker fires** (results/maker_pre_taker.json; conditions on its own
  later action, so descriptive only): maker orders signed within 30 s before a taker order on the SAME team see the
  next >= 4c jump in their favour 60.4% (BUILD, n=384) / 62.0% (VALIDATE, n=466); before a taker order on the OTHER
  team 37.8% / 32.0%; all other maker orders 41.9% / 41.0%. One signal (the team winning the round in progress) drives
  both the taker orders and the skew of its maker bids; the rest of the time its ladder is an uninformed maker's.
- C5: all its activity is 08-23 UTC (maker and taker; none 00-07), following the schedules of its leagues. Taker
  orders: whole shares 93.5%; whole-dollar notional 30.6%, mostly the 1000/2000-share orders at whole-cent limits;
  the ms part of the signing time is uniform. Sign-to-block 2.4-4.5 s (p5-p95): automated submission. No sign of
  manual USD-amount orders.
- Time used this iteration: about 70 minutes of work. Status: continue.
- **Caveat on the taker settlement edge** (results/taker_edge_boot.json): event-level bootstrap of the settlement edge
  of its taker fills is NOT significant per split: BUILD +6.7% (95% CI -6.9% .. +19.6%, p = 0.16, 40 events), VALIDATE
  +5.3% (-7.3% .. +17.1%, p = 0.21, 39 events). The strong evidence is the round-level next-jump test (p < 0.00025 in
  both splits); the settlement edge is consistent but noisy (binary outcomes, few events).
- **Copy-trading confound and C2** (results/copy_check.json, copy_leadlag.json): in the 3-60 s after its taker orders,
  same-team buying by other takers is 58.4% of taker USD vs 52.4% in random windows; the top-10 same-team takers
  hold 48% vs 33%. The candidates (0x93078b5d, 0x4ebc2722, 0xfe8a28be, 0x2529c68d, 0x72aaaaf9, and 0x2005d16a =
  the rn1-inplay-maker wallet) print the same team mostly in the SAME or next block as its taker tx (lag [0, 3) s:
  e.g. 0x93078b5d 386 prints vs 53 in [-3, 0) and 123 in [3, 10)), not with the delay of a copy bot. They act on the
  same trigger at the same moment: a common in-round signal shared by a few informed in-play takers. Two of them
  (0x4ebc2722, 0x93078b5d) are also the top two counterparties of its maker fills (1,027 and 722 txs): the informed
  takers that pick off its ladder at other times. The next-jump effect is therefore not copy-trading impact
  (5-s markout -0.14c; the jump comes ~30 s later).
- **It is at the front of a pack of informed takers** (results/taker_who_first.json, signing ms from the calldata of
  every taker tx): of the 5,298 other taker orders buying the same team in the same market within +-10 s of its taker
  orders, 73% are signed after its own; the bin [0, +0.5) s holds 1,214 vs 298 in [-0.5, 0) (4x): a burst of other
  takers signing the same side within half a second AFTER it, too fast to be copying (its order is not public before
  matching, which takes >= 1 s with the in-play delay). It is the first of the burst in 41% of the orders that have
  one. The trigger is an external event with a sharp timestamp (in-round game event) seen by several bots; it is
  among the fastest. Next: same test for the maker re-signing bursts, and the identity / timing of the pack
  (0x93078b5d, 0x4ebc2722, ...) as a proxy for the event time.
- Exploratory public proxy (results/follow_pack.json; pack identified on all development data, so VALIDATE is not
  clean): buy team X 1 / 3 / 10 s after the first print of a pack address buying X (+1c): BUILD +4.0% / +3.4% / +2.6%,
  VALIDATE +0.2% / -0.5% / -1.2% (about 2,100 trades per split). Following the pack's public prints does not
  reproduce its edge out of sample: the value is in the first second, i.e. in seeing the event itself.
- Live recorder: running at the end of the iteration (status OK for clob_wallets and sports).
- C4 versions inside the maker regime (results/versions_by_day.json): 10-share maker orders only on 10-22 (20% of that
  day's maker orders, none before); exact 1000/2000-share taker orders 52-64% on 10-17/18, 31-33% on 10-19/20, 12-17% on
  10-21/22 (taker sizing became variable); 10-16 is a start-up day (67% 100-share). VALIDATE (21-22 Oct) therefore
  holds a slightly different version from BUILD for sizes; decode versions separately next.

---

# Iteration 2 (2026-10-31, started 14:05 UTC; 73 of 1200 budget minutes used before it)

Read first: NOTES (iter 1), state.json, FINAL_RULE.md, panels/iter1_{information,mechanics,assumptions}.md. No EXAM or
wall-audit files exist. Calendar unchanged (no released lots; current block 10-31 12-18 UTC is development). Live recorder
status OK at 14:06 (clob_wallets, sports connected).

## Competing explanations (iteration 2) and the observation that separates them
1. **R1 round-end sniping through the 1-s taker delay.** A pushed round-end feed (server log / scorebot) reaches the
   wallet and the pack before the stream that most makers price from; it buys the round winner with FAK at stale asks.
   Separator: aligned to the game, bought team = winner of the round that just ended in >= 90%; about one decision per
   round; orders within a few seconds after the round end.
2. **R2 in-round kill-level state** (kills / man advantage / plant) from a kill feed. Separator: several pack events per
   round; bought team = winner of the round in progress 65-85%; orders spread through the round; partial reversion
   when the team then loses the round.
3. **R3 economy / freeze-end model.** Orders at round start on the equipment-advantage team. Separator: a peak right
   after freeze end; side = equipment advantage.
4. **R4 public Polymarket trigger** (book events, sibling markets, the sports socket). Separator: a public event that
   precedes its signing in most orders (book cancels before its signing, socket updates before it).
5. **R5 operator routing.** The wallet is one leg of an operator that also runs 0x4ebc2722 (sigType 3, signs ~50 ms
   earlier); a router splits one signal. Separator: shared owner / funder, complementary sizes, the wallet firing
   when the sibling is absent or capped.
6. **R6 maker-first economics.** The money is the locked pair margin + rebates of the ladder; the taker orders are
   cheap pair-completion / hedges. Separator: pair-unit PnL vs leg PnL; taker side vs inventory (already 49/50 =
   independent, so the hedge form is rejected); the re-pair legs filled by the delayed pack.
7. **R7 stream CV bot** (HUD reading of a low-latency stream). Separator: pack offsets scattered by seconds (they are
   50-300 ms IQR, so a pushed feed is more likely), orders 0.5-3 s after the stream shows the event.
8. **R8 listing-level selection = data-feed coverage** (GRID official data vs not). Separator: zero trades in GRID
   events, and a pre-game coverage proxy that predicts the traded events beyond pre-game activity.

This iteration discriminates R1 vs R2 vs R3 with the pack's event clock (public signing ms) and bo3.gg rounds, tests R8
as a frozen event-level selection rule against the activity baseline, and starts the taker-regime data expansion
(assumptions panel P2).

## Selection at event level (pre-registration for iteration 2, written before the VALIDATE PR curve was computed)
- Unit = CS2 event (all its match/map-winner markets), earliest gameStartTime in the split; label = any wallet fill.
  VALIDATE base rate 36/128 = 0.28 (BUILD 41/256 = 0.16), so lift >= 3 needs precision >= 0.84 on VALIDATE.
- The iteration-1 threshold rule (smallest t with BUILD lift >= 3) is base-rate dependent. Pre-registered now:
  t* = smallest score threshold whose BUILD precision >= 0.85 (fall back to the lift rule if none). Reported with both.
- Already computed (code/iter2/selection_event.py, results/selection_event.json): GRID events traded 0/85 (BUILD),
  0/37 (VALIDATE). League score with GRID zeroing S_lg: VALIDATE AUC 0.902; pre-game activity baseline B_act 0.897;
  S_lg + activity (logistic) 0.957, gain +0.061 [0.017, 0.114], p(gain <= 0) = 0.0015 (event bootstrap, 4000);
  LightGBM pair 0.940 vs 0.887, gain +0.053 [-0.011, 0.120], p 0.055.
- Point-in-time check of gridSeriesId (code/iter2/grid_pit.py, 14:20 UTC, future dev-block events only): the key is
  ABSENT from eventMetadata for events more than ~1 h ahead (IEM, BLAST, ESEA, Dust2.dk...), and present for events
  0.3-0.8 h ahead (CCT Europe x2 GRID, Circuito Retake GRID, CyberClash null). So GRID ids are attached about an hour
  before the start, not at listing. They are known before the in-play decisions, but the historical values were read
  after the fact; re-check at ~15:30 whether CCT Europe mnte-prodig (16:30 start, key absent at 14:20) gets it before
  its start.

## Data gathered (iteration 2)
- `code/iter2/events_meta.py`: event-level Gamma listing projection (gridSeriesId, league, tier, resolutionSource,
  createdAt) for 1,324 CS2 events listed 09-25..H with game start < H (sealed units dropped unread).
- `code/iter2/fetch_activity_taker.py`: taker-regime activity 06-16..10-16, 72,639 rows (69,350 TRADE, 3,187 REDEEM)
  over 2,645 markets (Gamma metadata in markets_taker.json). The local cache previously held only 15-22 Oct.
- `code/iter2/fetch_tapes_pre.py`: taker tapes of 506 more markets (287 maker-regime-league non-GRID markets with game
  start 09-26..10-15, before the switch, plus a 1-in-4 sample of GRID events of those days).
- `code/iter2/pack_events.py`: in-play taker orders of the pack (P4e 0x4ebc2722, P93 0x93078b5d, Pfe, P25, P72, P20,
  P8a, Pdd, Pf1) and the wallet from calldata, clustered per event (3-s single linkage): 14,972 orders, 7,349 clusters.
- Live lab, 10-31 12-18 UTC development block: the wallet trades 4 dev-unit events (cs2-bhe-bar2, cs2-gls1-pcy
  FiReSPORTS, cs2-wraith-ntr CyberClash, dota2-ty-gl): `code/iter2/dev_block_activity.py` (only units whose
  gameStartTime is in a development block are kept, everything else dropped before counting), `dev_calldata.py`
  (2,264 transactions decoded: the wallet's 365 plus every public taker tx of those markets), books from
  `clob_wallets` via iter_live (hour 12 stops with a zlib error after the 12:18 restart, as the panel reported).
- **Own recorder** `code/iter2/cs2_recorder.py` (feed `tommy_cs2_books`, through live.Writer): unthrottled CLOB
  market-channel messages (book snapshots, every price change, last trades) of EVERY CS2 match / map-winner market in
  play (47 markets at start), not only the wallet's; started 14:37 UTC 10-31 as a detached process, hard stop 11-03
  00:00 UTC, stops at 280 MB; status in .cache/re/tommy-cs2-maker/cs2_recorder_status.json. Purpose: the book-collapse
  trigger without the shared recorder's selection (it subscribes only after a studied wallet trades) and throttle.
- Endpoint checks: deposit-wallet `owner()` via eth_call works (publicnode); bo3.gg `/api/v2/matches/live` lists
  live matches with `live_coverage` / `live_coverage_source` (None for every dev-block match today, including the two
  the wallet trades). **Sealed incident**: the first bo3 live probe printed one sealed unit's live record (Nemiga-FURIA,
  start 11:00 UTC, sealed 06-12 block: map score and Thunderpick odds). Nothing from it is stored or used; the probe
  was then restricted to dev-block units.

## Findings (iteration 2); numbers in results/*.json
1. **The 10-16 switch is a change of market universe, not of fees.** In the taker regime (06-16..10-14) 99% of its
   USD (93% of markets) was in GRID events (Esports World Cup, BLAST, ESL Pro League, CCT Europe, IEM, Thunderpick),
   round-trip taking (46% of trades are sells), $13.1M traded, cash PnL +$142k before taker fees (fees of about 2.5%
   would make it negative, matching the dossier). 10-15: no trades. From 10-16: 0% GRID, 0 sells, tier-3 non-GRID
   leagues only (taker_regime.json). The informed pack was already in those leagues before the wallet came:
   09-26..10-15, P4e in 48% of the maker-regime leagues' non-GRID events, 1.3% of GRID events, 0% of other non-GRID
   events; pack share of in-play taker USD 20.7% there (the wallet: 0 of those events). It moved into an existing niche.
2. **Selection at event level (GRID boundary + league + pre-game popularity)**: GRID events traded 0/85 (BUILD) and
   0/37 (VALIDATE). Frozen v2 rule (code/final_rule.py, BUILD constants): VALIDATE AUC 0.954 vs pre-game activity
   baseline 0.892, gain +0.062 [0.019, 0.115], p(gain <= 0) = 0.002 (event bootstrap, 4000); recall 0.722 at lift
   3.30 (threshold = 20th percentile of the fitted positives' scores; the pre-registered BUILD-precision threshold gave
   recall 0.167, a base-rate artefact: BUILD base rate 0.16, VALIDATE 0.28). LightGBM pair: gain +0.053, p 0.055.
   Caveats: gridSeriesId is attached about an hour before the start (not at listing); the gain is at the significance
   edge; leagues change after 10-22 (today it trades CyberClash and FiReSPORTS, both 0-traded in 16-22 Oct).
3. **Owners differ**: the wallet's deposit-wallet contract owner() = 0x8af810f0e236cae55588ea6a084013c24122fd4f,
   P4e's = 0xbf6461fa5665f3d09cf5303b87968f19032c837b, P8a's = 0x875909d76d219a00adb0daef62e2768243c5c817 (POLY_PROXY
   wallets P93/Pfe/P25/P72/Pf1/P20 have no owner() view). R5 (one operator, two wallets) is not supported at owner level.
4. **Pack events are not round ends** (R1 not supported): 1.31 clusters per bo3 round on the map markets (P4e 0.66,
   wallet 0.26); cluster gaps median 34 s, 25% under 11.6 s. A timing-only DP alignment of clusters to bo3 round cycles
   (tight link = gap equal to the next round's duration + c within 3 s) does no better than the same DP on permuted
   durations: median 5.0 vs 4.7 tight links per map, 0 of 95 maps beat the control by 3 (round_align.json). Either
   the events are in-round or bo3 round timing is too coarse; bo3 cannot be used as the clock.
5. **Price path after its taker orders = in-round information with partial reversals** (price_paths.json): bought
   team +1.6-1.7c at 5 s, +2.6-2.9c at 10 s, +4.1-4.8c at 60 s; a >= 4c ADVERSE move within 60 s in 20-23% (random
   times 8%); P4e-only clusters move faster (+2.6c at 5 s) and reverse less (15-16%). A known round result would rarely
   reverse within 60 s, so the information is about the round in progress (R2-like).
6. **Maker price vs touch**: historical touch rebuilt from all makers' filled orders: its maker price = best known
   resting bid 24% (within 1c 40%) vs last print 11.5% (price_touch.json). Live books (dev block, 131 filled maker
   orders): price = best bid at signing 42.7%, at or above it 48.9%; spread 1c at the median; 78% are 100 shares.
   Live taker orders: limit = best ask 52%, ask + 1-2c 29% (dev_books.json). Filled orders are censored (deeper
   levels fill only when the price moves), so a point price rule is capped near the join-the-bid share.
7. **THE TAKER TRIGGER IS VISIBLE IN THE PUBLIC BOOK** (dev block; dev_book_trigger.json, dev_book_drop_detail.json,
   collapse_trigger.json, collapse_detail.json, collapse_presence.json): on the side its taker order consumes, the
   near-touch depth (within 3c of the best) is flat until 1.0 s before its signing, then falls to 48% at -0.7 s and
   18% at -0.5 s (median over 31 orders with book). Lost size median 1,222 shares over 8 levels; only 11% of the lost
   level sizes are multiples of 100 (not its own quotes); a public trade in the previous 3 s in only 9.7%, so other
   makers CANCEL. A >= 30% drop in the 2 s before: wallet 78.9%, pack 46.5%, other takers 6.5%, random times 2.9%.
   Collapse event rule (depth <= 0.5 x its max over [-1.5, -0.4] s, reference >= 200 shares, no trade in 1.5 s; team =
   the side whose asks vanished): 87% of its taker orders follow such an event on the SAME team within 2 s (0% on the
   other team); it acts on 5-8% of the events (about 66 events per market-hour); lag event -> its signing median
   0.77 s (p10 0.30, p90 0.96), pack 1.06 s. Acted events are deeper (remaining 18% vs 34%) and leave the best ask
   unmoved (59% vs 38%): there is still a stale ask to take. Taker presence on 0.5-s bins x team (115k bins, 31
   positives): S_col AUC 0.943 vs prints-only baseline 0.529 (in-sample), combined 0.953. Small sample, one block.
   Reading: fast makers with a game feed pull their stale asks on the team that just gained; the wallet (and the pack,
   about 0.3 s later) buy that team from the asks that slower makers left, FAK at ask + 0-2c. The 50-ms-tight offsets
   between independent operators (P4e -51 ms) fit consumers of one pushed public message (the CLOB book) as well as a
   shared game feed. Whether it reacts to the book or to the same game feed slightly later than the fast makers is
   not separable yet (both give tight lags); the book is a sufficient public trigger either way.
8. **Outcome**: a generic tape ladder (fair = last print - delta, 1-3 levels, 100 shares, strict trade-through fills,
   latency 2 s) loses 5-10% of USD bought and its per-market PnL correlates NEGATIVELY with the wallet's (VALIDATE
   Pearson -0.06..-0.12, Spearman -0.01..-0.15; pnl_replay.json): the wallet earns where generic makers are picked off.

## Hypothesis ledger (iteration 2)
- R1 round-end sniping: not supported (findings 4, 5). R2 in-round information: supported (5). R3 economy /
  freeze-end: untested directly. R4 public book trigger: **supported live** (7; small sample). R5 one operator: not at
  owner level (3). R6 maker-first economics: the generic maker loses (8); pair-unit PnL untested. R7 stream CV: offsets
  too tight. R8 selection = feed coverage / GRID: supported (1, 2).

## What is unexplained (quantitative)
- Which 5-8% of collapse events it acts on (depth left, stale best ask, price level, inventory?): needs more live
  blocks (31 orders so far). Whether the collapse or a game feed is its input (both precede the market's move).
- The trigger cannot be examined on h1/h2 (no books before 10-31): those lots can only judge selection, maker size,
  price vs last print and exit. The taker trigger needs the future blocks (own recorder now running).
- Maker price beyond join-the-bid (43%); the outcome target (no executable rule correlates positively yet).

## Late additions (iteration 2)
- **Recorder v2.** The first own recorder (feed `tommy_cs2_books`, 14:37-14:50 UTC) wrote 21 MB/h, too much for the
  cap. It was stopped (taskkill) and replaced by v2, feed `tommy_cs2_near`, at 14:50 UTC (pid 29844):
  - it keeps price changes within 5c of the best bid / ask;
  - near-touch snapshots every 30 s, or when the best moves >= 2c;
  - all last trades;
  - about 5.5 MB/h at the start, with the same hard stop and cap.
  Its rebuilt top of book matches `clob_wallets` (checked on 6 tokens). `final_rule.py` reads `tommy_cs2_near`, then
  `tommy_cs2_books`, then `clob_wallets` per token by time.
- **Frozen rule on the live block.** `final_rule.evaluate` (exam constants) ran end to end on the 10-31 12:00-15:00
  development block, which tests the code path after H. Results:
  - 10 events, 3 traded, 5 GRID events (0 traded);
  - live taker presence (0.5-s bins x team, all CS2 markets with books, 277,573 bins, 34 orders): S_col AUC 0.900 vs
    an in-sample prints-only logistic of 0.437;
  - pnl_corr on that block is meaningless: markets were unresolved, so outcomePrices were live prices.
- **Extended live sample to 15:00** (40 wallet taker orders with books, 3 of them Dota 2):
  - the collapse rule (frac 0.5, ref >= 200) precedes 70% of all its taker orders, and 28 of 37 (76%) of the CS2
    orders (0 of 3 Dota 2);
  - other takers 7%; never on the other team;
  - precision 3.7%;
  - taker presence S_col AUC 0.847 vs 0.532 (0.891 combined);
  - depth profile: flat to -1.0 s, 54% at -0.7 s, 25% at -0.5 s; lost size in 100-share units 9.7%.
- **X11, re-sign split** (`resign_split.py`). Rate of its (filled) maker signings in [+0.5, +2) s after a public taker
  signing:
  - taker matched the wallet: 3.7-4.1x the control;
  - taker matched only other makers: 2.8-3.2x.
  So it requotes on market events, not only after its own fills (both channels).
- **X12, take-then-make pair unit** (`pair_unit.py`). Children are its complement maker orders signed 0.5-5 s after
  its taker orders: 477 of 1,631 parents have them, child shares are 23% of parent shares, and the pair cost is a
  median 0.95 (IQR 0.93-0.96). Unit PnL vs the parent leg alone:

  | Split | Unit PnL | Event-bootstrap p | Parent leg PnL | Parent p |
  | --- | --- | --- | --- | --- |
  | BUILD | +$3.3k | 0.27 | +$5.2k | 0.15 |
  | VALIDATE | +$5.1k | 0.14 | +$3.9k | 0.22 |

  The pair unit is not significant either: binary settlement noise dominates 36-40 events per split.
- **X16, taker-regime orders** (`taker_regime_orders.py`; 11,692 transactions of 10-01..10-15 decoded with
  `fetch_calldata.py` into `calldata_taker/`):
  - every wallet order is a taker order (FAK, one tx each): 58% BUY, 42% SELL, 99.5% in-play, whole cents;
  - fill fraction median 100% (p25 35%), against 12% for the maker regime's taker orders;
  - sizes median 275 shares;
  - sign-to-block median 24.9 s (p5 3.2, p95 268), against 2.4-4.5 s in the maker regime. Unexplained: the data-api
    timestamp is used as block time (to check), or there is a longer delay in GRID events.
  In GRID events it took liquid books in full and lost to fees. In non-GRID events it only gets the stale remainder,
  but at an edge.
- **GRID point-in-time re-check, 15:00 UTC.** The gridSeriesId key appears about 1.0 h before the start: ESEA
  ep-dnk2 (16:00) has it, set to null; events 1.3 h or more ahead have no key yet (FiReSPORTS x2, CCT Europe
  mnte-prodig, Gamers Club Masters). The enrichment runs about an hour before the game, so the value is known before
  any in-play decision.

## Next iteration (plan)
1. **Live VALIDATE of the collapse trigger.** Development blocks from 11-01 18:00 UTC (pre-registered live split),
   using `tommy_cs2_near` for all CS2 markets:
   - recall and precision per order, and taker presence AUC against a GBM prints baseline;
   - decode which collapses it acts on: depth left, best-ask move, price level, inventory, map / round phase.
   Then freeze it as the taker component with constants.
2. **Separate its input.** Book cancels vs the same game feed. Test whether its lag after the collapse depends on how
   fast the collapse is (a book reader starts its clock at the collapse; a feed reader does not). Also test whether it
   fires on collapses caused by a single maker pulling a large order that holds no information (for example deep-level
   refreshes).
3. **Maker ladder from `tommy_cs2_near`.** Its 100-share levels in the full book (unfilled ones too), cancel and
   requote latency, and the price rule beyond join-the-bid (aimed at `price_within_tick`).
4. **Outcome.** An executable rule that adds the collapse-taker leg to the join-the-bid ladder, replayed on recorded
   books, per-market PnL vs the wallet (future blocks).
5. **Open X items:**
   - X4: Kick VOD stream clock. Needs the user's confirmation for video downloads.
   - X6 / X15: coverage proxy at listing time.
   - X8: bo3 per-round labels, which need a clock.
   - X13: taker size vs visible depth, now possible on live books.
   - The taker-regime sign-to-block puzzle.
   - C7, C8, B9, A8, A4b.

## Final checks (iteration 2)
- **X13, taker size vs visible depth** (`taker_size_depth.py`, 40 live orders).
  - Size relative to the depth up to its limit at signing: median 1.22 (IQR 0.91-4.29). It never equals the depth
    exactly (12.5% are within 10%).
  - Size relative to the depth 1.5 s earlier, before the collapse: median 0.26.
  - Filled shares relative to the depth at signing: median 0.95 (IQR 0.53-1.0).
  So the order is sized as a cap at or above the stale depth that is left. It takes about all of that depth
  (it survives the 1-s delay), and the sizes are not "sweep exactly what you see".
- **C7.** The wallet never matches against itself: 0 of 1,698 taker transactions in 16-22 Oct have it as a maker too.
  Referrals were not checked.
- **X6 (coverage proxy).**
  - A stream-channel prior adds +0.005 VALIDATE AUC (0.962 vs 0.957), a platform prior +0.004. Not adopted.
  - Events whose resolutionSource is hltv.org (no stream channel) are never traded: 0 of 12 on VALIDATE. Kick events
    are traded 28 of 53, Twitch 8 of 26.
- **Robustness of the live trigger against a fitted activity baseline**, 10-31 12:00-15:00. Data: 145,833 bins of
  0.5 s x team, 40 wallet taker orders, market-grouped 5-fold CV. The prints features are counts in the last 2 s and
  10 s, size in the last 10 s, and price level.

  | Model | AUC (out of sample) |
  | --- | --- |
  | LightGBM on prints | 0.512 |
  | Logistic on prints | 0.413 |
  | Collapse score S_col (no fitted parameters) | 0.846 |
  | LightGBM on prints + S_col | 0.728 (overfits on 40 positives) |

  An in-sample LightGBM on prints reaches 0.895. That is memorisation, so the CV numbers above are the ones to use.
- **A4b.** Kalshi's public API lists 1,200 open events, none of them CS2 or esports.
- **B9.** MAKER_REBATE rows are daily and carry no market id. They are a stable 0.26-0.27% of its daily traded USD.
- **The pack takes the wallet's resting bids** (10-31 development block, calldata_dev).
  - The wallet is a maker in 15.2% of the pack's taker transactions, and supplies 8.6% of their maker USD. In other
    takers' transactions it supplies 1.0%.
  - It never fills its own maker orders with its own taker orders.
  - So after an event its stale complement bids are hit by the pack while it buys the team itself from other stale
    asks. The two legs form a pair at about 0.95-0.99, which it merges. This is the "keeps bids pegged where others
    pull" fingerprint, and it explains why the maker and taker legs are -0.85 correlated per market (assumptions
    panel).
- **C8.** One web search for public Polymarket bots found general two-sided makers and a sports market maker that
  re-quotes in play. None has CS2-specific logic or trades other makers' cancels. Repositories:
  github.com/spfunctions/polymarket-sports-mm, github.com/LeapTech-Lab/poly-maker, github.com/warproxxx/poly-maker,
  github.com/rolekkona/Polymarket-Arbitrage-Trading-Bot.
- **Outcome target, more executable rules** (X17; `pnl_follow_pack.py`, plus an at-touch ladder). Per-market PnL
  correlation with the wallet, Pearson / Spearman:

  | Rule | BUILD | VALIDATE |
  | --- | --- | --- |
  | Follow the pack's public prints (+2 s, +1c, 100 shares) | -0.14 / -0.23 | -0.11 / -0.08 |
  | Plus the strict-fill ladder | -0.14 / -0.18 | -0.17 / -0.10 |
  | At-touch ladder (a print at the bid fills it) | -0.40 / -0.11 | +0.11 / +0.14 |

  None is positive in both splits. The wallet's per-market PnL is set by its residual inventory: its stale bids are
  hit by the pack while it buys the other team. A tape replay cannot reproduce that without its queue position and
  the cancels, so the outcome target needs the live books (future blocks).
- **Which collapses it acts on** (`collapse_events_dev.parquet`, 795 events, 28 acted; descriptive, small sample):
  - by remaining depth: it acts on 12.9% of the deep collapses (remaining <= 10% of the reference) and 1.8-2.9% of
    the shallower ones;
  - by the team's best ask: never when the best ask fell during the collapse (1 of 302 when it fell by 1c or more,
    0 of 124 when it fell by less), 5.7% when it was unchanged, 4-7% when it rose;
  - single-feature AUCs: remaining fraction 0.68 (inverted), ask jump 0.67, closeness of the price to 0.5 0.64.
  Reading: it buys when the team's asks vanish without the ask itself coming down, which is the signature of informed
  makers pulling and not of a seller repricing.
- **R8 mechanism on the own recorder** (`grid_collapse.py`; `tommy_cs2_near` 14:50-15:14 UTC; development-block
  units only, filtered by game start):

  | Events | Markets | Collapses per market-hour | Deep collapses (<= 10% of depth left) |
  | --- | --- | --- | --- |
  | Non-GRID | 9 | 122 | 23.7% |
  | GRID | 11 | 60 | 5.4% |

  The deep, trade-free cancel waves it acts on are mostly a non-GRID phenomenon. That fits makers who share official
  data updating together in GRID events, while in non-GRID events a few fast makers pull and stale makers stay. This
  is 25 minutes of data, so it is suggestive only.
  - Note for every reader of the live folders: a game that started in a sealed block keeps writing records after
    12:00 into dev-block files (shared recorder and own). Filter by the unit's game start, as `final_rule.py` and
    `grid_collapse.py` do.
- **GRID point-in-time, final check (15:14 UTC).** CCT Europe mnte-prodig and Gamers Club Masters lowcor1-tdp (16:30
  starts, 1.3 h ahead) now carry a GRID id. The FiReSPORTS pair (16:15) carries the key with a null value. Circuito
  Retake og1-is (17:30, 2.3 h ahead) has no key yet. The id is attached 1-1.3 h before the start, so it is known
  before any in-play decision. The wallet trades FiReSPORTS today, which is consistent with the rule.
- Time used this iteration: about 75 minutes of wall-clock (14:05-15:20 UTC). Status: continue. The own recorder
  `tommy_cs2_near` keeps running (detached, pid 29844, hard stop 11-03 00:00 UTC). The shared recorder was running
  at 14:06.
- **Does it ever sign before the collapse?** Of 49 taker orders in markets with collapse coverage (Dota 2 included):
  - 28 have a collapse in the 2 s before signing;
  - 4 have the first collapse only after signing, at +0.09, +0.37, +0.75 and +0.96 s (the first is within the 200-ms
    snapshot throttle);
  - 17 have no collapse within 2 s either way (thin books with less than 200 shares of reference, or Dota 2).
  It is mostly 0.3-1 s slower than the cancelling makers. This fits a book reader or a slower feed reader, and does
  not separate them.
- **Replication risk for the selection claim** (frozen v2, BUILD constants, `evaluate` with intervals):

  | VALIDATE day | Events | AUC | Baseline | Gain | p | Recall | Lift |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | 10-21 | 69 | 0.965 | 0.931 | +0.034 | 0.078 | 0.727 | 2.95 |
  | 10-22 | 59 | 0.927 | 0.833 | +0.094 | 0.033 | 0.714 | 3.83 |

  Per half, the gain is not significant and the lift straddles 3, so the examiner's replication rule (each half
  within 0.03) would likely fail on an h1 split. The selection claim is fragile.
- **Taker-regime clock** (40 sampled transactions of 10-01..10-15 with real block timestamps from
  eth_getBlockByNumber).
  - Signing to block: p5 3.0 s, p25 11.7 s, median 34 s, p75 88 s, p95 291 s, minimum 2.1 s. secondsDelay was 1 in
    all 2,645 of its markets.
  - Yet each of those orders was a FAK taker filled in one transaction (median fill 100%). So in the taker regime
    the client signed orders well before sending them (pre-signed orders kept ready and fired later), and the signing
    time there is NOT the decision time.
  - In the maker regime its taker orders reach the block 2.4-4.5 s after signing (p5-p95): the signing time is the
    decision time.
  This is a client change at the switch (C4 / C8). Any lead-lag study of the taker regime needs the submission time
  (about block time minus 2-3 s), not the signing time.
- **Sealed-data handling this iteration.**
  - `dev_block_activity.py` requests the wallet's activity for [T0, now]. Rows of units that did not start in a
    development block are dropped in memory before anything is counted or saved.
  - `final_rule.evaluate` keeps only the listing projection for out-of-period events.
  - All live readers filter by the unit's game start.
  - The one exception is the bo3 live-list print noted above (one sealed match's live score, not used).
- **Iteration 2 closing state.**
  - Primary metric `presence_auc` 0.8721 (iteration 1: 0.8271), still below its activity baseline 0.899.
  - Selection meets its thresholds on VALIDATE, but the gain is fragile.
  - Price (0.115) and outcome (negative) fail. The taker trigger is decoded on live data (one block); its live
    VALIDATE starts with the 11-01 18:00 UTC block.
  - Open catalog items: X2 (Markov valuation) and X8 (bo3 per-round labels), both blocked on a round clock, and X4
    (Kick VOD stream clock), which needs the user's consent to download video.
- **Join-the-bid on the unthrottled own book** (`price_join_own.py`; 16 CS2 maker orders after 14:51; the wallet's
  CS2 activity slowed). Exactly at the best bid at signing: 43.8%, within 1c 56%; the rest are 1-5c below. This matches
  the throttled-book figure (42.7%). For filled orders the point price rule tops out near 43%; the deeper levels need
  the ladder (unfilled orders) to be decoded from the own recorder next.
  **(Iteration 3: this figure is a receive-clock artefact too; on the server clock it is 29.3%, see below.)**

---

# Iteration 3 (2026-10-31, started 15:49 UTC; 150 of 1200 budget minutes used before it)

Read first: NOTES (iterations 1-2), state.json, FINAL_RULE.md, panels/iter2_{information,mechanics,assumptions}.md. No
EXAM or wall-audit files. Calendar unchanged (no released lots; the current block 10-31 12-18 UTC is development).
Shared recorder status OK at 15:50 (clob_wallets 400 tokens, sports connected; its `written` counter for sports and
rtds reads 0 although the hour files grow). Own recorder `tommy_cs2_near` running (pid 29844, 7 MB at 15:50).

## Competing explanations (iteration 3) and what separates them
The mechanics panel showed that every iteration-2 live result compared the wallet's signing ms (its own clock, equal
to the CLOB server's within ~40 ms) with the laptop's receive time (about 1 s slow). So the explanations are restated:
1. **U1 private in-round feed + delay-window sniping.** A push feed of in-round state for non-GRID tier-3 matches
   (a betting-data provider's websocket, server logs or a scout); on an in-round swing it fires FAK BUYs of the team
   that gained, before anyone moves the public book; its FAKs match 1.04 s later against makers that did not cancel.
   Separator: on the server clock nothing public precedes its signing; fan-out legs in two markets within ms.
2. **U2 one operator on both sides of the race.** The fast cancelling makers are the same operator (a sibling maker
   wallet pulls while this wallet takes). Separator: canceller identity (level decrements matched to calldata orders),
   shared owner / funder.
3. **U3 low-latency stream reader (CV on the broadcast).** Separator: offsets between the wallet and the cancellers
   would be spread over hundreds of ms or seconds (frame / segment arrival), not tens of ms.
4. **U4 market-making economics.** The money is the locked pair margin plus rebates; the taker leg only completes pairs.
   Separator: per-market PnL decomposition (pair margin carries most of the variance, assumptions panel).
5. **U5 public score model (round-score Markov valuation, X2).** Separator: a public score update precedes its orders;
   Polymarket's sports socket must carry round scores for its events.
6. **U6 follower of a faster private actor (C2 strong form, privately visible orders).** Separator: some identifiable
   wallet's orders sign before its own on the same team.
7. **U7 selection = coverage of the private feed.** It trades exactly the non-GRID events its feed covers. Separator:
   a per-match provider coverage flag (PandaScore `live.supported`, needs a token) beyond activity and GRID.

## Pre-registration (unchanged)
Primary metric `presence_auc` (30-s market bins, no own state), BUILD 10-16..10-20, VALIDATE 10-21..10-22; live split
BUILD = dev blocks before 11-01 12:00, VALIDATE = dev blocks from 11-01 18:00. New this iteration, for every live
result: **all live timing is on the CLOB server clock (record field `s`)**, never on the receive time `t`.

## Data gathered (iteration 3)
- `code/iter3/clock_probe.py`: clob.polymarket.com/time and HTTP Date second flips (15:55 UTC): server minus laptop
  = +1.38 .. +1.50 s (intersection of 6 flip bounds); Google Date +1.28 .. +1.63 s.
- `code/iter3/dev_markets.py`: dev-unit market list from the own recorder's `sub` records (49 CS2 match / map markets
  of 17 events with gameStart in 12:00-16:15 UTC; sealed units dropped first) and the wallet's trades in each via
  data-api `/trades?user&market` (takerOnly=false), so no sealed unit's wallet activity is requested (iteration 2
  fetched [T0, now] activity and dropped sealed rows in memory; this replaces it). The wallet traded 4 dev events
  (gls1-pcy 291 trades, bhe-bar2 84, wraith-ntr 7, dota2-ty-gl 383); none of the 13 events starting 14:00-16:15.
- `code/iter3/dev_calldata3.py`: calldata of every taker tx of the wallet's 9 dev-unit markets refreshed (4,234 txs).

## Findings (iteration 3); numbers in results/*.json
1. **The clock error is confirmed and the v2 book trigger is retracted** (`server_clock.json`).
   - Laptop offset t - s on trade records drifts steadily: -0.90 s (13:00 UTC), -1.07 (14:00), -1.21 (14:45), -1.31
     (15:15), -1.40 s (15:45); about -130 ms per hour. Any live timing on `t` is wrong by about a second, and by a
     drifting amount (a tool issue for every strategy that uses the shared recorder's `t`).
   - The wallet's clock: server match time minus sign_ms p5 / p50 / p90 = 1,034 / 1,040 / 1,052 ms (34 orders): the
     1-s in-play delay plus about 40 ms.
   - Consumed-side near-touch depth around its 64 CS2 + Dota taker orders with books, server clock, relative to -2 s:
     1.00 at every offset up to 0, then 0.66 (+0.1 s), 0.29 (+0.2), 0.19 (+0.5), 0.13 (+1.0), refill 0.35 at +1.04 s
     (its match). On the receive clock the same orders show the iteration-2 picture (0.41 at -0.7 s, 0.18 at -0.5 s).
   - Wave onset (first time D <= 0.8 x D(sign)) after its signing: p10 13 ms, p25 14 ms, p50 51 ms, p75 168 ms,
     p90 256 ms; 7 of 64 orders see no drop within 1.1 s.
   - Collapse rule (unchanged constants) in [sign - 2 s, sign]: 14.1% of its orders (random times 2.3%) on the server
     clock, 70.3% on the receive clock; in (sign, sign + 1.1 s]: 67.2% vs 6.2%.
   - The pack signs after the wave: its depth profile is already 0.76 at -0.2 s; other takers see a flat book.
   - So the wallet is the first public trace of the game event. The fastest cancelling makers follow it by 14-51 ms
     (median), the pack by 0.2-0.5 s. Its input is upstream of every Polymarket feed. The iteration-2 numbers that
     depended on the receive clock are void: "collapse precedes 76-87% of its taker orders", "lag 0.77 s", "acts on
     4-8% of collapses" and its filter, the live taker presence AUCs 0.846 / 0.900 / 0.943, "book reader or feed
     reader", and the 43% join-the-bid figure.
2. **Fan-out legs: one internal signal per game event** (`burst_fanout.json`). 16-22 Oct: 60 pairs of taker orders in a
   map market and the match market of the same event signed a median 1 ms apart (p90 4 ms); dev block: 11% of its
   taker orders are fan-out legs. No book precedes either leg, so the decision is per game event, not per book.
3. **Its skipped collapses are not a fill race** (assumptions P1, `burst_fanout.json` race). 1,212 server-clock
   collapse events in its markets; it acted (taker order within [-0.3, +0.1] s) on 25. In 873 events at least 30% of
   the reference depth was still resting 1 s later, so a FAK would have filled; it acted on 0.9% of those. The
   collapses it skips are not censored attempts: they are events its signal does not flag (other makers' requotes,
   or information it does not act on).
4. **Polymarket's own sports socket has no round data for its events.** Dev block: for Galorys-Procyon (gls1-pcy),
   Bounty Hunters-BARCA and WRAITH-Nuclear TigeRES the round part of the score stays `000-000` (map scores only),
   while GRID events (Saint Sinners-Misa, naocopulas-paiN, Invicta-Donstu, FOKUS-BakS, ...) carry per-round scores.
   The wallet works exactly the events in which Polymarket's feed (and GRID) gives the market no round data (U5 out).
5. **Selection with bo3.gg pre-match fields** (information P1, `selection_bo3.json`; bo3 finished lists 10-15..10-22,
   460 matches, 295 of 384 events matched by both team names and start within 3 h).
   - Non-GRID traded rate by bo3 stars: 0 stars 4.4% (n 91), 1 star 45% (60), 2 stars 87% (30), 3 stars 100% (11),
     unmatched 13% (70).
   - But stars add nothing beyond pre-game activity: VALIDATE AUC activity A 0.897; activity + GRID flag G 0.930
     (gain +0.033 [0.008, 0.065], p 0.0025); G + stars 0.929 (gain +0.033, p 0.09); inside non-GRID events A 0.899,
     G + stars 0.882. Stars are a popularity proxy. Not adopted (so the point-in-time check is moot).
   - Activity + GRID without the league rate (assumptions P2 step 1): 0.930; the frozen v2 with the league rate 0.954
     (gain +0.062, p 0.002). The league rate does add +0.024 on VALIDATE here.
6. **Price at the in-play tick** (assumptions P4, `versions_price.json`). The first sub-cent resting order in a market
   has a median price of 0.999; 89.7% of VALIDATE maker orders were signed while the tick was 0.01. Within one tick
   (the tick in force): last print 0.256, rebuilt touch 0.396 (was reported as 0.115 at a 0.001 tick). Live, server
   clock, book 50 ms before signing (368 orders): at the best bid 29.3%, 1c above 14.7%, 1c below 11.4%, within +-1c
   55.4%; with the book 300 ms after signing 46.2% at the bid (its own order is in it: self-reference).
7. **Versions** (assumptions P6). Every 10-share maker order is in a Dota 2 market (1,292 on 10-22; all Dota 2 maker
   orders of the dev block), so the "10-share version from 10-22" was the arrival of Dota 2 markets. CS2 maker orders
   are 100 shares in 89.4% (16-22 Oct) and 78.4% (dev block). Size rule v3: CS2 100, Dota 2 10. Taker orders keep
   drifting: exact 1000 / 2000-share caps 14.4% (VALIDATE) vs 0% (dev block), size median 470 vs 183 shares, fill
   fraction median 0.155 vs 0.242.
8. **Per-signer calibration** (mechanics P3). Server match minus sign (dev block): wallet 1,040 ms; pack Pfe 1,064,
   Pf1 1,082; other fast signers 1,038-1,060 (0x84ad9c5c, 0x47138dc1, 0x68915897, 0xb4cd4d6f, 0xfca6d645); slow ones
   2.0-2.2 s. With the wave starting 14-51 ms after the wallet and the pack 0.2-0.5 s after the wave, the wallet ranks
   first in the race on most events.

## Hypothesis ledger (iteration 3)
- U1 private in-round feed: **supported** (findings 1-4). U2 one operator on both sides: partly tested in the late
  additions (the earliest cancels are its own complement ladder; the other fast cancellers and late makers have
  different owners; funding links not checked). U3 stream CV: disfavoured (cancellers follow within 14-51 ms). U4: per-market PnL is the
  pair margin (panel), consistent. U5 public score model: **rejected** for its events (no round data in the socket,
  and nothing public precedes its orders). U6: nobody public signs before it. U7: open (needs a provider flag).
- H14 (book collapse trigger): **retracted** (clock artefact).

## What is unexplained (quantitative)
- The taker decisions (about 70% of settlement PnL in 16-22 Oct): on the server clock its signing precedes every public
  Polymarket trace. The consumed-side book is flat (median 1.00) up to its signing in 57 of 64 orders; the first
  cancels after it are its own (+13-16 ms), other makers' follow at +17 / +67 / +124 ms (p10 / p25 / p50); pre-sign
  collapse 14% vs 2.3% random; no excess of book changes anywhere in the event in the 100 ms before it. The input is an external game feed that
  none of the obtained data contains (sports socket: map scores only for its events; bo3: no live coverage).
- Selection inside non-GRID events beyond popularity and league.
- Maker price beyond the touch (29% at the bid on the server clock) and the outcome target.

## Late additions (iteration 3)
- **The re-pair is deliberate, not a stale bid** (mechanics P2 first part, `stale_complement.json`, 16-22 Oct
  calldata). For each of its taker orders (BUY team X at t), its maker fills on the complement token inside other
  takers' transactions whose taker signed in (t, t + 2.5 s]:
  | Split | Taker orders | With such fills | Control (t-30 s) | Maker order age at t (median) | Signed before t | Pair cost median (IQR) | Pack share of the takers |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | BUILD | 729 | 8.8% | 3.0% | +1.06 s | 1.6% | 0.96 (0.95-1.01) | 55% |
  | VALIDATE | 969 | 10.7% | 2.5% | +1.04 s | 9.1% | 0.99 (0.95-1.005) | 67% |
  The complement bids the pack fills are signed about 1.04 s after its take, i.e. as soon as its FAK returns from the
  1-s in-play delay (the client's 1,000-1,100 ms burst interval, information panel check A). They are effectively asks
  on team X at 1 - bid, which the pack's FAKs (signed 0.2-0.5 s after the wave, matching ~1 s later) consume. So
  around an event the wallet buys X from makers who did not cancel and immediately sells X back to the slower informed
  takers through complement bids, locking a pair at 0.96-0.99. The panel's "stale complement bids it does not pull"
  holds for only 2-9% of those fills. Control fills 30 s earlier are old orders (median -40 s) at pair cost 1.00.
- Mechanics P2 is therefore partly answered: the maker leg is not feed-blind around its own takes (it re-quotes the
  complement 1.04 s later, timed by its FAK response); whether it also re-quotes on other public events (hazards by
  trigger type) remains open (X26).
- `final_rule.py` v3 ran end to end on VALIDATE (build constants: selection 0.954 / 0.892, presence 0.872 / 0.899,
  price_within_tick 0.305 at the in-play tick, exact 0.115) and on the 10-31 12:00-16:30 development block (exam
  constants; live server-clock diagnostic: 61 taker orders with books, collapse before signing 14.8% vs random 2.1%,
  after signing 72.1%, match - sign p50 1,040 ms). The old receive-clock function is kept as `_live_trigger`
  (not called) and archived as `code/iter2/final_rule_v2_receive_clock.py`.
- **Race rank** (`race_rank_dev.json`, dev block, 73 taker orders, signing clocks): it is the first signer among all
  same-team takers of the market within +-2 s in 90.4% of its orders; same-team takers follow within 2 s in 27.4%
  (mean 0.86 followers vs 0.10 at random times); the first follower signs a median 375 ms after it (p10 85 ms).
- **Caveat on "first".** Its FAK reaches the engine about 34-40 ms after signing (match - sign = 1,034-1,040 ms with
  the 1,000-ms delay, if its clock is synchronized), and book messages are stamped when the server publishes them. The
  first cancels are stamped +13-14 ms (p10-p25) and +51 ms (p50) after its signing, so at the server the fastest
  cancelling makers and the wallet act on the same external event within a few tens of ms of each other. It is
  ahead of every taker (the pack by 0.2-0.5 s) and ahead of every public trace, but not provably ahead of the fastest
  cancellers' own feed.
- **It pulls its own complement ladder 13-16 ms after its FAK signing** (X26 / X34; `canceller_id.json`,
  `canceller_offsets.json`, `own_cancels.json`; own recorder from 14:50, server clock, 28 wallet taker orders).
  - In the 500 ms after its signing the consumed side loses 20 cancels per window (level decreases with no trade
    within 150 ms), against 0.93 at random times.
  - Cancels of exactly 100 shares on the consumed side (team X asks = mirrored bids on team Y) follow 60.7% of its
    taker orders within 0-40 ms (mean 2.75 levels per order), never on the other side (0%), against 4.8% after pack
    orders, 0.4% after other takers' orders and 0.0% at random times. Their offsets after its signing: p10 / p25 / p50
    / p75 = 13 / 14 / 14 / 16 ms (90 cancels). Only 1.8% of all 4,169 size-100 cancels in these books sit in such a
    window, so the coupling is specific to its takes.
  - Reading: one client sends the FAK on team X and cancels its own 100-share bids on team Y at the same moment
    (cancels are not delayed; its FAK reaches the engine about 34-40 ms after signing). It re-posts the complement 3-8c
    lower when the FAK returns (3 cases with both measured). So the maker leg is not feed-blind: the same signal pulls
    its stale complement quotes, and the earliest "wave" cancels (p10-p25 13-14 ms) are its own.
  - Other makers' cancels in the same windows: offsets p10 17 ms, p25 67, p50 124, p75 221 ms. Size fingerprints from
    calldata attribute 91 of 560 wave cancels to 0x2e3c40fa (POLY_GNOSIS_SAFE type 2, sizes 120 / 20 shares; 3.25 per
    wave vs 0.08 per control window), 7 to 0x893575c7, 7 to 0x6c1415bf; 62% stay ambiguous or unfingerprinted. Owners
    of the fast late makers (0x68915897, 0x5d40576b, 0xed446954, 0x758dac51, 0x7eeb94f2, 0x9f63eb94, 0x8a68a3dc,
    0xf1f2b3c6) all differ from the wallet's 0x8af810f0 (`late_maker_owners.json`): no shared operator at owner level.
  - Ownership check (`cancel_owner_check.json`): whether the cancelled 100-share levels had been added by a ladder
    anchored on one of its filled orders. 1.2% for the after-take cancels vs 1.0% for others. This has no power: only
    50 of its ladders are anchored (unfilled ladders cannot be anchored), so it neither confirms nor rejects. The
    attribution rests on size (100), side (the complement only), timing (IQR ~2 ms after its own signing) and
    specificity (55-61% of its takes vs 5% of the pack's). That points to the wallet's own client, or a same-operator
    process sharing its signal.
- **Delay-window requoters** (X28, `late_makers.json`). In its taker transactions of 16-22 Oct, 19% of the maker USD
  comes from orders signed after its FAK, at offsets p10 / p25 / p50 / p75 = 121 / 254 / 537 / 827 ms (only 43 of
  1,549 within 50 ms). The top late makers: 0xed446954 (8.5k USD, p50 948 ms), 0x5d40576b, 0x893575c7, 0x68915897
  (p10 83 ms), 0x2005d16a (the rn1-inplay-maker wallet), 0x758dac51. Dev block: 23% late USD, p50 346 ms. In the pack's
  dev-block transactions the second-largest late maker is the wallet itself (offset p50 683 ms after the pack signs:
  its re-pair at +1.04 s after its own take). Premium / size regression on requoter presence not run.
- **Maker re-sign hazards by trigger** (X26, `maker_hazard.json`, 16-22 Oct, filled maker orders only). Rate ratio of
  its maker signings against the same market's baseline:
  | Trigger | Same team | Complement team |
  | --- | --- | --- |
  | Its own take, [0, 100) ms | 6.6x | 0.0x |
  | Its own take, [500, 1000) ms | 1.3x | 2.6x |
  | Its own take, [1000, 1140) ms | 17x | 236x (peak bins 1,000-1,040 ms: 450-690x) |
  | Takers that hit its bids, [0, 100) ms | 1.9x | 6.4x |
  | Takers that hit only others, [1000, 1140) ms | 3.8x | 9.1x (peak 1,040 ms: 17x) |
  It never re-posts the complement during its own delay window, and re-posts it as soon as its FAK returns. On the dev
  block server clock only 3.4% of its maker signings fall within 50 ms after a trade message (0.5% with times shifted
  7 s), nearly all after its own fills (5-20 ms): public trades are not its general requote trigger
  (`maker_trade_latency.json`).
- **Quote presence in untraded markets** (assumptions P2 step 4, `quote_presence.json`): inconclusive. Whole-cent
  +100-share level additions are common in GRID markets that it never trades (median 112 per hour, up to 2,585 in CCT
  Europe), so the 100-share fingerprint is shared with other makers. Untraded non-GRID markets show a median of 0.7 per
  hour against 348 in its traded markets; the FiReSPORTS shin-isg markets showed 87-226 per hour before its first fills
  there (it then traded them, 29 trades by 16:20).
- **Taker limit and size on the server clock** (X13 redo, `taker_price_size_server.json`, 69 taker orders; book 50 ms
  before signing = the pre-event book). Limit minus the pre-event best ask: 0c 26%, +1c 22%, +2c 14.5%, +3c 14.5%,
  +4c 9%, +5c 12% (98.6% at or above the ask): it pays up to 5c over the stale ask, anticipating the repricing. Size
  is a median 0.31x of the pre-event depth up to its limit; by +0.9 s the wave has removed 82% of that depth, and it
  fills 98% of what is left (fill / pre-event depth 0.07). The iteration-2 "size 1.22x the visible depth" and "limit =
  ask 52%" were measured on the post-wave book (receive clock).
- **Full ladder from the own recorder** (X33 step 2, `ladder_decode.py` / `ladder_decode.json`; 82 filled CS2 maker
  orders after 14:50). 61% of them (98% of the 100-share ones) are confirmed by a +100 level add at their price on the
  mirrored side 19 / 24 / 170 ms (p10 / p50 / p90) after signing, so its orders reach the book ~24 ms after signing
  (its cancels at +13-16 ms come first: cancel, then sign and post). Ladders per burst: 1 level 46%, 2 12%, 3 18%,
  4-6 24%; 1c spacing 88%; filled orders sit at level 0 in 76%. Top vs the pre-burst book: at the best bid 32%, +1c
  20%, -3/-4c 32%, exactly best ask - 1c 48%. Rule scores on burst tops: "top = ask - 1c" exact 48% (within 1c 52%),
  "top = bid" exact 32% (within 1c 58%). The -3/-4c group includes its re-pair bursts after its own takes (n = 6) and
  is not explained; the sample is small (50 confirmed bursts).
- **Any public trace of the event before its signing?** (`presign_public.json`, server clock, 75 taker orders vs
  1,500 random times in the same event's markets.) A trade message in any market of the event in the last 1 s: 5.3% vs
  1.3%. Any near-touch book change in any market of the event in the last 300 ms: 54.7% vs 34.0%; in the last 100 ms:
  14.7% vs 14.4%. So its takes come in busier phases (in-round action), but nothing public marks the moment: no excess
  of book changes in the 100 ms before it, and the consumed side keeps its depth (median 1.00) up to its signing.
- **First public print** (`first_print.json`, 78 taker orders, server clock). Another trade prints in any market of the
  event within 1,040 ms after its signing in only 2.6% of its orders. The first other print comes 2.4 / 5.6 / 43 s
  later (p10 / p25 / p50). So the first public trace of the event's price is the cancel wave (+17-124 ms) and then
  its own fill (+1.04 s).
- **Opening-kill consistency check** (X8 lead, `opening_kill_rate.json`). bo3.gg per-round team stats carry
  `first_kills`, kills, trade kills and equipment (no in-round times; the kills endpoints answer 404). In 40 of its
  traded matches (16-22 Oct, 1,689 rounds with a unique opening-kill team) that team wins the round 72.1% of the time.
  Its taker orders see the next >= 4c public jump go their way 64-67% (74% / 67% when within 60 s): consistent with
  buying the team that just won a duel (an opening kill or a man advantage), not proof. Testing it needs an in-round
  clock (stream, X4 / X22) because neither bo3 nor Polymarket's socket has kill times for these events.
- **Match-clock price anchor** (X29, `match_clock_price.json`). Last print on the match clock (min(block, taker sign +
  1,040 ms); taker signing known for 100% of prints; every tx with a wallet order excluded) vs block time, VALIDATE
  maker orders: within one in-play tick 0.353 vs 0.305, exact 0.141 vs 0.115. Small gain; it may run up to ~3 s early
  for slow signers, so it is left to the examiner and not adopted.
- **SX Bet / PandaScore** (X23): infeasible without a key. `api.sx.bet/markets/active` (no key) lists in-play CS2
  markets of the same tier-3 events (FiReSPORTS ShindeN v Isurus, which the wallet trades today), but
  `/orders-v3/odds/best` and `/orders-v3` answer 401 BAD_AUTH and `/orders/odds/best` 400 "OrderBook V2 is no longer
  supported" (docs.sx.bet: V3 replaced V2). PandaScore: 403 "Token is missing" (information panel).
- **Dota 2, retrospective** (X24 variant, `dota_align.json`, `dota_end.json`): OpenDota parses its Dota 2 maps (kills_log
  in game seconds, start_time, 90-s pre-game). Matched 6 maps (PARI Universe: 10-22 Yandex-GamerLegion and
  Liquid-1win, 10-31 Yandex-GamerLegion; development units). Its 72 Dota taker orders against kills of the bought vs
  the other team show no sharp offset peak (best bins 10-13 vs 1-2 pairs at +1,036-1,044 s), and the market's
  settlement offset is unstable (-1,024 .. +1,007 s after start + duration). Inconclusive: game time does not map to
  wall time without the draft and pause lengths. The live variant (record /api/live with its `delay` field during dev
  blocks with Dota 2 events) stays open.
- **Dota 2 live recorder started** (X24 live variant): `code/iter3/dota_live_recorder.py`, feed `tommy_dota_live`,
  detached at 16:43 UTC (pid 14548; status in `.cache/re/tommy-cs2-maker/dota_recorder_status.json`). It polls OpenDota
  /api/live every 30 s (league games only, compact records with `delay`, scores, radiant_lead, game_time) only while a
  Polymarket Dota 2 PARI Universe event is in play (Gamma series 10309, checked every 10 min); live.Writer files dev /
  sealed; hard stop 11-03 00:00 UTC, 60 MB cap. Next: lead-lag of its Dota taker signings against kill-score changes,
  with the feed's `delay` (spectator delay) as the reference.
- Exposure note: the OpenDota proMatches pages fetched to find these maps (shared HTTP cache) also list other pro
  matches, including some from sealed days; their fields were skipped in code before any print or storage.
- Not done this iteration (open X items): X21 / X34 canceller identity beyond size fingerprints, X22 / X4 stream clock (needs the user's
  consent to download ~50 MB of video), X23 PandaScore `live.supported` (needs a token from the user), X24 Dota 2
  OpenDota recorder (endpoint verified: 200, 143 KB per poll, 100 live games with a `delay` field), X26 hazards,
  X28 delay-window requoters, X29 match-clock tape, X8 bo3 round labels.

- **The followers, by behaviour** (`followers.json`; other taker orders on the same team and market signed in
  (0, 1.5 s] after a wallet take).
  - 16-22 Oct: P93 0x93078b5d (388 follows, lag p50 489 ms); the 3-wallet cluster 0x72aaaaf9 / 0xfe8a28be / 0x2529c68d
    (about 300 each, p10 374-383 ms, p50 464-475 ms; 15-17% of their takes); Pf1 0xf1ee4842 (p50 168 ms); and fast
    followers at p50 149-197 ms (0x8a80528d, 0xddb6e624, 0x67706ec3, 0x14e72e19, 0xbb8ef638, 0x7c8cc255).
  - 10-31 dev block: the same 3-wallet cluster (17 / 17 / 15 follows, p10 360-366 ms, p50 376-382 ms, 19-24% of their
    takes); Pf1 and 0xfca6d645 at about 88 ms.
  - So there is a latency ladder behind the wallet: its own cancels (+13-16 ms), fast makers' cancels (+17-124 ms),
    fast takers (+85-200 ms), the 3-wallet cluster (a fixed +380 ms), P93 (+490 ms). The fast followers may be book
    readers of the wallet's own cancels, or slower subscribers of the same feed. The fixed +380 ms of the cluster fits
    a constant processing or feed lag. That is not separable with this data.

- **Selection follows the pack's coverage** (U7, `selection_pack_lag.json`; complete 16-22 Oct universe, windowed
  taker tapes of all 384 events). Every non-GRID event the wallet traded also had in-play prints by the informed pack
  (P4e, P93, the 3-wallet cluster, Pf1): 100%, against 50.3% of the non-GRID events it skipped. A point-in-time lagged
  league feature (the pack-presence rate of the league's earlier events that ended at least 4 h before, shrunk k = 3;
  only 16-22 Oct events feed it):
  | Model (logistic, BUILD fit) | VALIDATE AUC | Gain vs activity [95% CI], p | Gain 10-21 / 10-22 | Recall / lift |
  | --- | --- | --- | --- | --- |
  | Activity + GRID | 0.930 | +0.033 [0.009, 0.064], 0.002 | +0.010 / +0.056 | 0.78 / 2.77 |
  | + pack-league lag | 0.949 | +0.052 [0.018, 0.094], 0.0003 | +0.020 / +0.091 | 0.75 / 2.67 |
  | + pack lag + league rate | 0.953 | +0.056 [0.019, 0.102], 0.0003 | +0.023 / +0.097 | 0.69 / 2.96 |
  | Frozen v2 (league rate) | 0.954 | +0.062 [0.019, 0.115], 0.002 | +0.034 / +0.094 | 0.72 / 3.30 |
  On the 27 VALIDATE events of leagues not seen in BUILD (8 traded), the pack-lag model scores 0.941 against 0.914 for
  activity + GRID, so it carries over to new leagues better. The 10-21 gain stays small in every variant, so the
  replication risk remains. The frozen rule is not changed: these AUCs are within noise of v2, and switching on VALIDATE
  would be selection on the test set. Reading: the wallet trades a subset of the events its feed peers cover; whatever
  feed the pack uses covers these events too.
- **Refresh at 16:53 UTC** (more FiReSPORTS shin-isg orders; same code, results files overwritten). Server clock, 76
  taker orders: collapse in the 2 s before signing 15.8% vs 1.8% at random, after signing 61.8%; depth profile 1.00
  up to 0, then 0.65 at +0.1 s and 0.15 at +1.0 s; match - sign p50 1,040 ms (n = 40); laptop offset -1.58 s at 16:45
  (drift -0.68 s since 13:00, about -180 ms per hour). Own-cancel coupling, 40 takes after 14:50: size-100 cancels on
  the consumed side within 40 ms after 45% of its takes (other side 0%), against 4.1% of the pack's, 0.6% of other
  takers' and 0.13% at random times. Public traces before signing (82 orders): a trade in any event market in the
  last 1 s 6.1% vs 1.3%; a book change in the last 300 ms 58.5% vs 33.0%; in the last 100 ms 19.5% vs 15.9% (not
  significant at n = 82).

## Lead of its taker signing over every public source obtained (dev block 10-31, server clock)
| Source | First trace after its signing | How often it precedes the signing |
| --- | --- | --- |
| CLOB book, consumed side, own market | its own 100-share cancels +13-16 ms; other makers' cancels +17 / +67 / +124 ms (p10 / p25 / p50) | depth flat (median 1.00) up to signing; collapse in the prior 2 s 13-16% vs 1.6-2.3% at random |
| CLOB book, any market of the event | (fan-out legs signed 1-4 ms apart) | change in the prior 100 ms 14.7-19.5% vs 14.4-15.9% at random |
| CLOB trades, any market of the event | its own fill at +1.04 s; another print within 1.04 s in 2.6% | a trade in the prior 1 s 5.3-6.1% vs 1.3% at random |
| Other takers (pack and all) | first same-team follower +85 / +375 ms (p10 / p50) | it is the first same-team signer in 90.4% |
| Polymarket sports socket | map scores only for its events | no round data at all |
| Public tape repricing | next >= 4c jump a median 32-37 s later (iteration 1) | - |
| bo3.gg, HLTV, SX Bet, PandaScore | no live data / blocked / key needed | - |

## Next iteration (plan, revised at the end of iteration 3)
1. **Canceller identity beyond size fingerprints (X21 / X34).** The earliest cancels (+13-16 ms) are the wallet's own
   ladder; other makers' cancels come at +17-124 ms. Attribute those on the own recorder (size / price matching against
   calldata orders, time-shift control), then the owners and funders of the top cancellers. Test whether their
   presence across events is a selection feature (feed coverage).
2. **Outcome via the pull-and-re-pair mechanism.** An executable follower rule on the recorded books. At each
   server-clock cancel wave in a selected event, post complement bids 3-8c under the pre-wave level about 1 s later,
   and replay fills against the pack's delayed FAKs (public calldata), plus the ladder. Compare per-market PnL with the
   wallet's on the live VALIDATE blocks (from 11-01 18:00), and report it as a follower rule.
3. **Maker price.** Explain the -3/-4c ladder group (ladder_decode) on more blocks, and the ask - 1c rule.
4. **Ask the user** for a PandaScore token (X23) and for consent to fetch ~50 MB of Kick VOD segments (X22 / X4). An
   in-round clock would test the opening-kill reading of the taker trigger (X8).
5. **Dota 2 (X24).** Analyse `tommy_dota_live` (running) against its Dota 2 taker signings.
6. **Primary metric.** `presence_auc` did not move this iteration (0.8721). If the next iteration also brings < 0.01,
   the one after must pivot. A candidate is a quote-presence target (its resting ladders on the own recorder in
   non-GRID markets) instead of fill presence, which co-occurrence bounds.

## Iteration 3 closing state
- Status: continue. Primary metric `presence_auc` 0.8721 (unchanged; activity baseline 0.899). Selection 0.954 vs
  0.892 (gain +0.062, p 0.002), recall 0.72, lift 3.30. `price_within_tick` 0.305 at the in-play tick. pnl_corr
  -0.12 / -0.06. Target not met (price, outcome, presence).
- The v2 taker trigger is retracted (receive-clock artefact). `final_rule.py` is v3: selection unchanged, an in-play
  tick price metric, a size rule by game, and a server-clock live diagnostic.
- Open catalog items: X4 and X22 (stream clock; needs the user's consent to download video), X8 (bo3 round labels;
  needs an in-round clock), X24 (Dota 2 live recorder running; analysis pending). X23 is infeasible without a key or
  token from the user.
- Recorders: shared recorder running (status OK at 16:45); own `tommy_cs2_near` (pid 29844, 12.5 MB) and
  `tommy_dota_live` (pid 14548) running, both with a hard stop of 11-03 00:00 UTC.
- Time used: about 72 minutes of wall-clock (15:49-17:01 UTC); the remaining open items need the user (video consent, a PandaScore token) or future dev blocks (Dota 2 recorder, live VALIDATE from 11-01 18:00). Fan-out wave onsets (X21 event clock): only 1 pair with own-recorder coverage (onsets 9 and 15 ms), insufficient (`fanout_waves.json`).

---

# Iteration 4 (2026-10-31, started 17:29 UTC; 221 of 1200 budget minutes used before it)

Read first: NOTES (iterations 1-3), state.json, FINAL_RULE.md, panels/iter3_{information,mechanics,assumptions}.md. No
EXAM or wall-audit files. Calendar: no released lots; the current block 10-31 12-18 UTC is development, 18-24 sealed,
11-01 00-06 sealed, 11-01 06-12 development. Shared recorder status OK at 17:33 (clob_wallets 400 tokens, sports
connected); own recorders `tommy_cs2_near` (pid 29844, 18.5 MB) and `tommy_dota_live` (pid 14548) running.
The 16 iteration-3 panel proposals are catalog items X37-X52 (state.json): information P1-P6 = X37-X42, mechanics P1-P4 = X43-X46, assumptions P1-P6 = X47-X52.

## Competing explanations (iteration 4) and the observation that separates them
1. **V1 private upstream feed (server log / venue scout / GOTV without delay) + delay-window sniping, public-book
   maker.** The taker leg sees in-round events before the broadcast; the maker ladder is a public-book function
   (join others' bids, pair-sum cap) whose only private input is the pull / re-pair at its own events. Separator: an
   event clock (demo ticks, chat) puts its signings well before the broadcast (O_M - O_W >= 5 s); a replay of the
   public quote rule WITHOUT its pulls reproduces the per-market PnL ranking.
2. **V2 stream-derived provider feed (scouts / CV on the broadcast) shared with the fastest makers.** Separator: the
   event clock gives O_M ~ O_W within 1-3 s; after order-level attribution, other makers' first cancels have a floor at
   the moment its own pull becomes public (book readers), or precede it (co-subscribers).
3. **V3 the first public trace is in the round markets** (round handicap / totals of the same map, never traded by it,
   never recorded). Separator: round-market book changes in [-200, 0) ms before its signing well above the random
   rate (own round-market recorder started this iteration; historical round-market taker signings).
4. **V4 an in-play odds / win-probability feed** (e.g. the organiser-bookmaker's own live odds: 1win, Stake run several
   of its leagues). Separator: the FAK limit premium predicts the size of the repricing and the move levels off near
   the limit; fan-out premiums follow one valuation (premium ratio = series sensitivity); selection = events with
   in-play odds at that source.
5. **V5 passive liquidity provision + rebates is the money; the informed leg is secondary.** Separator: per-market
   PnL ~ passive locked margin (panel: 0.83-0.85); a queue-aware replay of a public quote rule reproduces the ranking
   (Spearman >= 0.5) without private input.
6. **V6 intermediation inside the delay window** (sell the bought team back to the slower informed pack through the
   1.04-s re-post). Separator: event pairs are 3-7% of locked dollars (panel), so this is minor unless the pulls carry
   the margin (replay with oracle pulls vs without).
7. **V7 a human spotter**: already disfavoured (decisions in concurrent events independent, assumptions panel).
This iteration discriminates V5 vs V1/V6 (queue-aware replay with and without its pulls), V4 vs raw-state feeds
(premium dose-response, fan-out ratio), V3 (round-market recorder; historical check), and V1 vs V2 (GRID-era price
paths, slow UI takers as a broadcast clock), and records the X items that need the user (demo / video downloads).

## Actions (iteration 4)
- **Round-market recorder started** (assumptions P1b, X47): `code/iter4/round_recorder.py`, feed `tommy_cs2_rounds`,
  launcher pid 33544 (worker 29380), started 17:36 UTC 10-31: books of every non-moneyline CS2 market (round handicap, round
  totals, map handicap, total maps) of NON-GRID events in play whose game start is in a development block; it idles in
  sealed blocks and never subscribes a sealed unit; same near-touch format as `tommy_cs2_near`; hard stop 11-03 00:00
  UTC, 200 MB cap. 38 markets at start.
- Disk warning: free disk on C: fell from 15.1 GB (17:39) to 2.9 GB (17:53 UTC), not from this agent (its cache is
  160 MB, its recorders < 25 MB); it was back at 14.1-14.8 GB from 18:06. No large downloads this iteration (brief:
  `--need-disk 5000`).

## Findings (iteration 4); numbers in results/*.json
1. **Queue-aware replay of a public quote rule (X44, mechanics P2; `code/iter4/queue_replay.py`,
   `queue_replay.json`).** Full matched-order record of the wallet's 229 markets (109,170 taker txs). Rule: join the
   other makers' last OBSERVED best bid on both tokens (observations only from public txs that contain no wallet
   order, usable LAT = 2 s after their match time), pair-sum cap K, shade the long side, 100 shares, strict
   price-time-priority fills (only volume the taker gave to makers below our price, or at our price with a later
   signing than our post), the wallet's taker txs removed from the flow, its maker volume displaceable.
   | Variant | BUILD return | BUILD corr P / S | VALIDATE return | VALIDATE corr P / S | paired-volume corr (B / V, Spearman) |
   | --- | --- | --- | --- | --- | --- |
   | K 0.97, 1 level | -5.2% | -0.32 / -0.13 | -4.4% | -0.04 / -0.04 | 0.79 / 0.91 |
   | + oracle pulls (its complement pulled 0-1.04 s after each take) | -5.1% | -0.35 / -0.14 | -4.4% | -0.01 / -0.02 | 0.79 / 0.91 |
   | K 0.97, 3 levels | -5.2% | -0.38 / -0.13 | -5.3% | -0.12 / -0.07 | 0.80 / 0.92 |
   | K 0.96 / 0.98 | -5.1% / -5.2% | -0.40 / -0.27 (P) | -4.7% / -4.0% | -0.15 / -0.07 (P) | ~0.79 / ~0.91 |
   | LAT 1 s (+ oracle) | -5.0% (-4.9%) | -0.36 (-0.35) | -4.2% (-4.2%) | +0.02 (+0.06) | 0.79 / 0.91 |
   The replay puts its volume where the wallet's is (paired volume Spearman 0.79-0.92), but its pair cost is a median
   1.005 against the wallet's 0.978, and per-market PnL does not correlate (best VALIDATE +0.06 / +0.01). Inserting
   the wallet's own pulls changes nothing (+/-0.03). So the margin is not carried by the event pulls at its takes; it
   needs what a 2-s-stale tape view cannot give: the live book (others' cancels, the real touch) and possibly the
   zero-fill / protective pulls (X46). The outcome target is therefore not reachable from tape and calldata alone
   (h1 / h2); it needs a live-book replay on future blocks. (The wallet's maker leg alone earned only +0.47% at
   settlement in 16-22 Oct; its 0.978 pair cost includes the informed taker legs.)
2. **The FAK limit premium is a private valuation (X45 / X48a; `code/iter4/premium_value.py`,
   `premium_value.json`).** Premium = limit - stale ask (first matched level).
   - Wallet: Spearman(premium, bought team's move) 0.26 at 10 s (event-bootstrap CI [0.16, 0.35] BUILD,
     [0.17, 0.35] VALIDATE), 0.13-0.17 at 60 s, 0.12-0.13 at 120 s. VALIDATE 60-s move by premium 0 / 1 / 2 / 3 / 4 /
     5+c: +2.2 / +2.0 / +2.1 / +5.5 / +5.0 / +9.6c.
   - Other takers in the same markets (about 42k BUY orders per split): Spearman 0.04-0.05 at 10 s, about 0 at 60 s;
     their 5c+ premiums see +0.1-0.4c. Premium scaling is specific to the wallet.
   - It does not level off at the limit: at 60-120 s the price sits a median +2 to +5c ABOVE its limit at every
     premium. The limit is "stale ask + a premium that grows with the event", kept below the post-event value (an
     edge requirement), not a fair-value target (the odds-feed form of V4, "buy up to the new fair price", is not
     supported; a model-based value with a margin fits).
   - Fan-out legs (56 pairs, map + match signed <= 5 ms apart): mean premium map 1.81c vs match 1.05c on map 1
     (ratio 0.58), 2.06c vs 1.03c on map 2 (ratio 0.50); the series sensitivity at q = 0.5 is 0.50 for maps 1-2.
     Per-pair premiums do not correlate (whole cents), but on average the match leg's premium is the map leg's times
     the series sensitivity: one valuation propagated from map to match (no map-3 pairs).
3. **No shared signer (X52, assumptions P6; `code/iter4/signer_check.py`, `signer_check.json`, 51 txs decoded).**
   The 3-wallet cluster (0x72aaaaf9, 0xfe8a28be, 0x2529c68d) are POLY_PROXY wallets (sigType 1) with three
   different signer EOAs (0xf15f4f45..., 0x21ac60ff..., 0x799204d1...); P93 signs with 0xbac5c53a..., Pf1 with
   0x5dfc48b5..., 0x893575c7 with 0xdb889f28...; the wallet, P4e and the fast late makers (0xed446954, 0x5d40576b,
   0x68915897, 0x758dac51, 0xfca6d645) are deposit wallets (sigType 3) whose signer is the wallet itself (owners read
   in iteration 2 differ). No signer is shared by two makers among all 51 txs' orders. Funding links not checked.
4. **Data-rights falsifier (X39, information P3).** PGL holds an exclusive official data partnership with Oddin.gg
   for its CS2 and Dota 2 events (2024-2026, at least 11 tier-1 CS2 tournaments; europeangaming.eu 2024-04-23,
   sbcamericas.com 2024-04-29). The wallet traded the PGL Bucharest Closed Qualifier (tier 4, community co-streams:
   twitch vanfantv / watchfulTVb / Trottah / officialhyper), 9 of 13 events. An organiser-level "official data
   holder" flag would mark PGL as covered and predict a skip: the organiser-level form is falsified. Only an event-level
   coverage flag (is this qualifier in the data deal?) could survive, and that is not public. Not adopted.
5. **Demo clock prerequisites (X37, information P1).** bo3.gg `/api/v1/games/<id>` (verified on game 190260, A NATA
   vs ARK, 10-16): `demo_url` is a relative path (`demos/manually_uploaded/1792137147_...-m3-mirage.dem`), `demo_data`
   is null, `game_rounds` carry no kill times, `duration` 3,482.9 s includes pauses. The download host is still
   unverified (iteration-3 panel: bo3.gg/<path> serves the SPA, files.bo3.gg 404). Downloading 50-300 MB demos and
   installing a demo parser from PyPI need the user's consent, and the disk has 2.9 GB free: left open for the user.
6. **Its own pull follows 90% of its takes, and some other makers act within ~10 ms of it (X49, assumptions P3;
   `code/iter4/pull_attrib.py`, `pull_attrib.json`; own recorder 14:50-18:00 UTC, server clock, 39 CS2 takes).**
   - Own pull = equal-size cancels on >= 2 levels within 5 ms, or 100-share cancels, plus remainders of its partly
     filled orders (calldata; 5 cancels). It follows 89.7% of its takes at +11 / +14 / +19 ms (p10 / p50 / p90);
     sizes 100 (19 takes), 68 (8), 54 (7), 58 (1): the assumptions panel's inventory-scaled ladder is confirmed.
   - In 20.0% of the takes with an own pull, a cancel that is NOT attributable to the wallet lands between its
     signing and its own pull, when nothing of its action is public yet (a ~11-14 ms window). The base rate for a
     random 14-ms window on that side is 0.37% (about 54x). A non-own cancel in the 50 ms before its signing: 10.3%
     (about the base rate). Others' first cancel relative to its pull: p10 -37, p25 -6, p50 +10, p75 +89 ms.
   - So the wallet is not the only fast leader. In about one take in five another maker acts on the same event
     within ~10 ms (a shared pushed source); the rest of the wave follows its pull or the event later. The
     "shared feed" reading of iteration 3 survives the order-level attribution. Whether that source sits before or
     after the broadcast is still open (X37 / X38).
7. **Zero-fill FAK attempts are a minority (X46, mechanics P4).** Own-size pulls (100 / 68 / 58 / 54, >= 2 levels):
   with an on-chain take 33, strict re-post signature (no own re-add in [60, 1000) ms, one in [1000, 1150) ms)
   63.6%, team up >= 1c at 10 s 87.9%. Without a take 829, signature 3.5% (random times 2.7%), and those 29 go up
   62.1% / down 17.2% (random 25.8% / 28.5%). About 7-11 hidden attempts against 33 visible ones (20-35% more
   attempts than fills). The signature is not specific enough to be a taker label by itself.
8. **Round-market takers follow it; none leads (X47a, assumptions P1; `code/iter4/round_takers_hist.py`,
   `round_takers_hist.json`).** VALIDATE, 39 events, 665 round / handicap / total markets, 529 decoded round-market
   taker txs near its takes and controls. A round-market taker signed in the 1 s before its take in 0.93% (controls
   at -120 / +120 / +240 s: 0.21-0.72%), in the 200 ms before in 0.10% (0-0.10%), and in the 500 ms AFTER it in
   6.7% (controls 0.2-0.8%; the 3-wallet cluster among them). The round markets add no earlier taker trace. Their
   books (cancels) are recorded from 17:36 UTC (`tommy_cs2_rounds`), but the wallet made no take between 17:36 and
   18:00, so the live test waits for the 11-01 06-12 development block.
9. **Slow UI takers are not a broadcast clock (X40, information P4; `code/iter4/ui_clock.py`, `ui_clock.json`).**
   Retail (<= 20 orders per address) net flow on its team per 4-s bin, minus time-shifted controls: contra in 0-12 s
   (-95), cumulative turn at 68 s (mid-size takers 36 s). Takes followed by a >= 4c public jump within 10 s: contra
   -65, turn at 72 s. Takes with the next jump > 40 s away: no contra, turn at 40 s. Retail trades against the public
   repricing rather than after a fixed delay: no broadcast-delay signature.
10. **The 10-16 switch changed the input's speed, not only the universe (X51, assumptions P5;
    `code/iter4/grid_latency.py`, `grid_latency.json`).** Same clock for all groups (decision = block time - 2 s);
    bet-on team's price relative to 60 s before:

    | Group | -10 s | 0 | +10 s | +60 s |
    | --- | --- | --- | --- | --- |
    | Taker regime, GRID (1,435 trades, 70 markets) | +1.41c | +2.86c | +6.17c | +6.78c |
    | Taker regime, non-GRID (208 trades, 15 markets) | +0.97c | +2.04c | +4.19c | +5.62c |
    | Maker regime takes, non-GRID (1,629) | -0.85c | -0.98c | +1.75c | +3.06c |

    Before 10-16 about 30-40% of the move came before its decision, in GRID and non-GRID events alike: late,
    momentum-like trades, consistent with its losses before fees. From 10-16 the path is flat or falling before its
    take and the move comes after. The new regime brought a faster input (and a new client: immediate signing instead
    of pre-signed orders), not only a new universe.
11. **Clock-free event type: bomb plants, not opening kills (X50, assumptions P4; `code/iter4/event_type_counts.py`,
    `event_type_counts.json`).** 91 maps of 16-22 Oct matched to bo3.gg per-round team stats. Binomial GLM (map fixed
    effects) of the share of its take events (orders within 5 ms merged) on team A, per 10 rounds of difference:

    | Model | Wallet (82 maps, 541 events) | P4e (55 maps, 1,307 events) |
    | --- | --- | --- |
    | Round wins dW | +0.28 (p 0.12) | +0.63 (p 8e-8) |
    | Opening kills dFK alone | +0.06 (p 0.71) | +0.49 (p 5e-5) |
    | dFK beyond dW | -0.17 (p 0.44) | +0.09 (p 0.59) |
    | Bomb plants dBP beyond dW, dFK, dCL | +0.60 (p 0.059) | -0.67 (p 0.0008) |

    Raw correlations of its share: dBP 0.38, dW 0.27, dK 0.27, dFK 0.11. The opening-kill reading of iteration 3 is
    not supported. A bomb plant (a discrete, feed-visible event that lifts the T side's round odds) is the leading
    candidate for its trigger, at weak power. The pack (P4e) follows round wins and leans away from plants.
12. **Other proposals.**
    - Azuro (X41): thegraph.azuro.org and thegraph-1.onchainfeed.org fail DNS, api.onchainfeed.org answers 404, and
      no LiveCore address was found. Open.
    - Dota 2 at 3-5 s (X42): OpenDota's free tier (60 calls/min, ~50k per month) rules out 3-5-s polling over days.
      The 30-s recorder runs, with no wallet Dota take inside its dev-block coverage yet. Open.
    - Chat clock (X38): an anonymous Twitch recorder was started (below). Kick needs a client key read from Kick's web
      page and was not attempted.
    - Odds sources (X48b): not probed (terms first; odds-api.io needs a key from the user).
- **Chat recorder started** (X38): `code/iter4/chat_recorder.py`, feed `tommy_chat`, launcher pid 27360 (worker
  28984), 18:16 UTC 10-31.
  - Anonymous Twitch IRC: nick justinfanNNNNN with Twitch's public anonymous placeholder pass; login verified
    ("001 Welcome").
  - Channels = the Gamma resolutionSource of non-GRID CS2 events in play that started in a development block.
  - It stores only the channel, the Twitch server timestamp (tmi-sent-ts), the receive time, the message length and
    the emote count: no text, no user names.
  - Idle in sealed blocks; hard stop 11-03 00:00 UTC; 50 MB cap. It is idle now (10-31 18-24 and 11-01 00-06 are
    sealed) and first records in 11-01 06-12.

## Hypothesis ledger (iteration 4)
- V1 private upstream feed: consistent. Nothing public precedes it, round-market takers included; a few makers act
  within ~10 ms of it; a faster input arrived with the 10-16 switch.
- V2 stream-derived provider feed: not separable from V1 yet (needs X37 / X38).
- V3 round-market lead: rejected for takers (historical); the book test is pending.
- V4 odds feed with limit = fair price: not supported (the price overshoots its limit by 2-5c). A model valuation with
  a margin and map-to-match propagation fits.
- V5 passive liquidity provision reproducible from public data: rejected on tape + calldata (the copy gets the
  volume but a 1.005 pair cost).
- V6 intermediation inside the delay window: minor (oracle pulls add nothing in the replay).
- V7 human spotter: not revisited.

## What is unexplained (quantitative)
- The taker input. None of the obtained public sources precedes its signing; ~20% of its takes share the event with
  another maker within ~10 ms; its per-map take shares follow round wins and bomb plants. Needed: an event clock
  (demo ticks, chat) to place the source relative to the broadcast.
- The maker margin. A public copy with queue priority on tape + calldata gets the wallet's volume (Spearman
  0.79-0.91) but a pair cost of 1.005 instead of 0.978 (about 2.7c per pair). The wallet's maker leg alone earned
  +0.47%, so the gap is the live book (real touch, others' cancels) plus its private pulls.
- Price: no rule reaches 0.8 within one tick (live filled orders: full-book bid 0.53, others' bid 0.46).
- The primary metric is unchanged at 0.8721 for the second iteration, so iteration 5 must pivot (quote-presence
  target on the own recorder, or the event clock).

## Next iteration (plan)
1. Pivot the primary target to quote presence: its resting ladder per token and 10-s bin, own levels by fingerprint
   100 / 68 / 58 / 54 on `tommy_cs2_near`, against an activity baseline; BUILD = 10-31 12-18, VALIDATE = from 11-01
   18:00. Or, with the user's consent, the demo-tick event clock (X37), which is also the only taker label h1 / h2
   can have.
2. 11-01 06-12 development block: X47b (round-market books before its signings), X38 (chat lead-lag), more takes for
   X46 / X49 (pull attribution), and the bomb-plant trigger once a clock exists.
3. Ask the user (through the run's reviewer): demo downloads + parser (X37), a PandaScore token (X23), an odds-api
   key or consent to probe bookmaker frontends (X48b).
4. A live-book replay of the ladder for the outcome target on future blocks: fills from the recorded book plus the
   matched-order record, pulls at the public cancel wave.
- Time used this iteration: about 81 minutes (17:29-18:50 UTC). Status: continue. Recorders: shared recorder OK
  (17:33); own `tommy_cs2_near`, `tommy_dota_live`, `tommy_cs2_rounds` and `tommy_chat` running.
- **Late check, T side or CT side?** (X50 follow-up, `code/iter4/t_side_share.py`, `t_side_share.json`). Half-level
  clock: bo3 begin_at + duration x (share of the first 12 rounds' durations) = halftime; takes within 3 min of it
  and in overtime dropped; 101 maps matched. The wallet buys the T side in 53.8% of 422 take events on 87 maps
  (binomial p 0.13, map-bootstrap CI [0.49, 0.59]; half 1 56.1%, half 2 50.8%). A plant-driven trigger would show a
  strong T preference, so the per-map bomb-plant association above is not confirmed by side. The pack P4e buys the CT
  side in 59.2% of 1,133 events (p 6e-10), so its trigger set differs from the wallet's. The clock is good enough to
  detect a side effect (P4e's), which makes the wallet's near-0.5 share informative: its trigger is close to
  side-neutral (kills / man advantage on either side), with at most a weak T lean.
- **Who cancels inside its pre-pull window** (X49 follow-up; the cancels are listed in `pull_attrib.json`). There
  are 11 cancels in 7 takes, at +3 to +14 ms (one at +34 ms), sizes 31.26, 168, 5, 45, 199, 180, 40.47, 46.75, 7.01,
  60 and 20 shares. The 168 (= 100 + 68) is probably the wallet's own double level, so the share of takes is 17-20%
  (6-7 of 35). Two of them match orders of 0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3 (199 at 0.49, and a 40.47
  remainder at 0.38). That wallet is a POLY_PROXY co-maker present in 2,185 of the wallet's 16-22 Oct transactions,
  with orders of 300 / 50 / 100 / 60 shares. The rest are unfilled orders of unknown makers. Candidate co-subscriber
  of the same event source: 0x51dbdd2b (next: its cancel timing on every take, its owner and its selection of
  events).
  Historical timing of 0x51dbdd2b (16-22 Oct matched-order record; 5,760 filled maker orders in 147 of the
  wallet's 210 markets). Rate of its filled maker signings after each wallet take, relative to its average rate in
  that market:

  | Token | 0-100 ms | 100-500 ms | 0.5-1 s | 1.00-1.15 s | 1.15-3 s |
  | --- | --- | --- | --- | --- | --- |
  | Team the wallet bought | 0.0x | 7.5x | 1.2x | 15x | 7.0x |
  | Complement (asks on that team) | 7.5x | 3.4x | 3.3x | 8.0x | 4.9x |

  It re-quotes the complement within 100 ms of the wallet's signing and the bought team from 100 ms on. That is fast
  enough to act on the same source, or on the wallet's public pull at +11-14 ms. Its +1.0-1.15 s peak matches the
  delay window. It is the first named lead for a second subscriber of the feed.
- **0x51dbdd2b has nearly the wallet's event selection** (`code/iter4/cosub_coverage.py`, `cosub_coverage.json`).
  - Its activity 10-16..10-22: 16,571 TRADE rows, 61% CS2 and 29% Dota 2.
  - It traded 68.8% of the wallet's 77 traded CS2 events, against 11.9% of the 185 non-GRID events the wallet skipped
    and 17.2% of the 122 GRID events.
  - Its signer EOA is 0xdecd4b4cb7e41b6824518b704161cb423833e780 (POLY_PROXY). That is not the wallet's owner
    0x8af810f0, and nothing links the two on chain yet.
  - A second operator therefore shares the wallet's events and timing: it cancels inside the wallet's pre-pull window
    and re-quotes within 0.1-0.5 s of its takes. It is the first named co-subscriber candidate, and its funding links
    are the next C1 check.
- Maker price anchor from own state: its own last fill price on the same token is within one tick of its next maker
  order in only 26.7% (BUILD) / 27.9% (VALIDATE), worse than the last print (0.305). Not adopted.
- `final_rule.py` v3 re-run on VALIDATE (build constants) reproduces the iteration-3 numbers: selection 0.9538 vs
  0.8916, recall 0.722, lift 3.302, presence 0.8721 vs 0.899, price 0.305, pnl -0.121 / -0.061.
- **0x51dbdd2b never leads the wallet, but sometimes acts within 9-13 ms of it** (`cosub_timing.json`; own
  recorder, its non-generic order sizes 300 / 60 / 258 / 268.3 / ... as a loose fingerprint).
  - 896 such cancels lie in the wallet's take markets. Of these, 0.11% are followed by a wallet take within 1 s, and
    1.23% are preceded by one (11x more).
  - Around the 39 takes they fall at -640, +9, +11, +12, +13, +25, +56, +108, +285, ... ms after the wallet's
    signing.
  - The +9 to +13 ms cancels are as early as the wallet's own pull message (+11-14 ms), too early to be a reaction
    to it.
  - Reading: the wallet signs first. A second operator with nearly the same event selection gets the same event
    within about 10 ms in some takes. That fits two subscribers of one pushed in-round source, with the wallet the
    faster one.
- 0x51dbdd2b also traded all 3 of the wallet's Dota 2 events of 16-22 Oct (it traded 51 Dota events in all). It is a
  maker, not a taker: 7 taker orders in the wallet's markets, 2 of them on the same team 77-84 ms after a wallet take.
  So it is a fast canceller / re-quoter, the maker-side counterpart of the wallet's information.
- **Sealed-data handling this iteration.**
  - Live data was read only through `iter_live` (development blocks), and units were filtered by game start.
  - The wallet's dev-unit trades and calldata were refreshed only for units that started in the 12-18 block. Rows
    of those units after 18:00 are development data by the unit rule, and only takes before 18:00 were analysed.
  - Every historical fetch ends before H: round-market tapes, taker-regime tapes, 0x51dbdd2b's activity, signer
    decodes and bo3 games of 10-16..10-22.
  - Once, at 18:30 UTC, `ls .cache/live/sealed/ | grep -c tommy_cs2_rounds` listed that folder's entry names, to
    confirm that the new round recorder had written nothing sealed. The count was 0, and no file there was opened.
    It will not be repeated: the recorder's own status file shows this.
- **Premium dose-response with controls** (X45 robustness; stored in `premium_value.json` under
  `controlled_ols_10s_event_clustered`). OLS of the bought team's 10-s move on the premium, controlling for the price
  level |a - 0.5|, map vs match and hours since game start, with event-clustered SEs:
  - BUILD: +0.82c per 1c of premium (SE 0.17, p 9e-7, n 518);
  - VALIDATE: +0.87c per 1c (SE 0.13, p 7e-11, n 603).
  Each cent it adds to its limit predicts most of a cent of extra repricing. The limit carries a quantitative,
  private estimate of the event's size.
- **Premium as a confidence estimate.** At premium 0 / 1 / 2 / 3+c, a favourable >= 4c move within 60 s follows 52.6 /
  61.7 / 70.1 / 83.3% of its takes (BUILD) and 53.5 / 56.5 / 58.0 / 79.1% (VALIDATE). An adverse >= 4c move follows
  21-31% at every premium. Taker size grows weakly with the premium (Spearman 0.22 BUILD, 0.14 VALIDATE). The bot's
  private estimate sets both the limit and, weakly, the size. Stored in `premium_value.json`
  (`reversal_and_size_by_premium`).

## Iteration 4 closing state
- Status: continue. Primary metric `presence_auc` 0.8721, unchanged for the second iteration, so iteration 5 must
  pivot. Frozen rule v3 is unchanged; its VALIDATE re-run reproduces selection 0.954 / 0.892, recall 0.722, lift 3.30,
  price 0.305 and pnl -0.121 / -0.061.
- Open catalog items: X4, X22 and X37 (video / demo downloads; need the user's consent); X24 and X42 (Dota 2 recorder
  running); X38 and X47 (chat and round-market recorders running; data arrives in the 11-01 06-12 development block);
  X41 (Azuro endpoints fail, address not found); X48 (odds-source probes).
- Recorders: shared recorder OK (18:48); own `tommy_cs2_near`, `tommy_dota_live`, `tommy_cs2_rounds` (idle in sealed
  blocks) and `tommy_chat` (idle in sealed blocks) are running, all with hard stop 11-03 00:00 UTC.
- Time used: about 81 minutes (17:29-18:50 UTC).
