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
