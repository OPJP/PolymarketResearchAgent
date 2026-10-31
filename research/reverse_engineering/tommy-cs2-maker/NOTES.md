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

---

# Iteration 5 (2026-10-31, started 19:21 UTC; 302 of 1200 budget minutes used before it)

Read first: NOTES (iterations 1-4), state.json, FINAL_RULE.md, panels/iter4_{information,mechanics,assumptions}.md. No
EXAM or wall-audit files. Calendar: no released lots; the current block 10-31 18-24 UTC is SEALED (no new development
live data arrives during this iteration; the next development block is 11-01 06-12). Shared recorder status OK at 19:24
(pid 27184). The 15 iteration-4 panel proposals and two panel critiques are catalog items X53-X69 (mapping in
state.json). The primary metric was unchanged for two iterations, so this iteration pivots the unit of decision: from
fill bins to (a) uncensored quote probes (fully consumed sweep levels), (b) a validated order-level fill engine, and (c) a
survivorship-free census of informed bursts.

## Competing explanations (iteration 5) and the observation that separates them
1. **W1 one shared vendor feed, several subscribers.** The wallet is one of several fast makers / takers on a pushed
   in-round source; its selection is the vendor's coverage. Separator: other makers avoid its FAKs (low presence ratio)
   and some act inside its 11-14 ms pre-pull window; nothing leaks from the delay queue.
2. **W2 delay-queue leak.** Pending (1-s delayed) taker orders become visible to some makers, so fast cancels are
   reactions to pending orders, not to a shared source. Separator: cancels right after the ARRIVAL of any pending order,
   uninformed retail included.
3. **W3 partial detector.** Its input covers only some in-round event types (or is slower on others); at the rest it is
   blind and its ladder is picked off. Separator: the share of informed 3c+ bursts it misses, its stale hits there, and
   whether the missed and the led bursts load on different game-event types.
4. **W4 the maker margin is a public ladder mechanic.** Deeper levels behind other makers' touch plus in-delay posts
   produce the 0.978 pair cost without private input. Separator: a VALIDATED fill engine; a public ladder below the
   stale touch reaching the wallet's pair cost and per-market PnL ranking.
5. **W5 one private valuation drives both legs.** The maker top is the bot's model value minus a half-spread (the FAK
   limit reveals the value). Separator: K - L predicts its next maker tops after takes beyond public anchors, and its
   resting-ladder presence at swept levels is not predictable from public state.
6. **W6 pair completion off its own cost.** It prices the complement at K minus its own unpaired cost. Separator: own
   cost anchors within one tick.
7. **W7 operator availability.** Part of the selection is when the bot is switched on. Separator: skips in hours with
   no orders anywhere; per-day replication after label cleaning.

## Actions (iteration 5)
- **Recorders now record in every block (X68; information panel iter4 critique 1).** `tommy_cs2_rounds` and
  `tommy_chat` idled in sealed blocks, so the examiner of a future-block exam would have had neither. New versions
  `code/iter5/round_recorder_v2.py` and `code/iter5/chat_recorder_v2.py` (same feeds) choose markets / channels from
  listing-time fields only (series, sportsMarketType, scheduled start, gridSeriesId, resolutionSource) in every block,
  and file records through `code/iter5/unit_writer.UnitWriter`: a record goes to `.cache/live/sealed/` if its receive
  time is in a sealed block OR its unit started in a sealed block, so development files never hold a sealed unit (this
  is stricter than live.Writer, which files by receive time only). Status files count only dev-filed records. v1 workers
  29380 / 28984 stopped (taskkill); v2 started 19:28 UTC (round worker pid 8668, chat worker pid 536; launchers 15676 /
  17648); hard stop 11-03 00:00 UTC; caps 200 MB / 50 MB. `tommy_cs2_near` and `tommy_dota_live` already recorded in
  every block (live.Writer). Nothing in `.cache/live/sealed/` was opened or listed.
- **Data bug found (own data, iteration 2)**: `pack_orders.parquet` was built from `calldata_pub` only, which excludes
  every transaction containing a wallet order. So the pack's 5,752 taker orders that hit the wallet's ladder (P4e is the
  taker in 1,027 wallet txs, P93 in 722) were missing from every pack-based analysis (pack clusters, pack-vs-rounds, P4e
  side shares). `code/iter5/census.py` rebuilds the informed BUY orders from both records (18,061 orders). Earlier
  pack-based numbers are biased toward pack events that did not touch the wallet's ladder.
- **X38 pre-registration (information panel iter4 critique 3), written before any chat data exists.** On development
  blocks, cross-correlate chat-rate bursts (tmi-sent-ts) with the wallet's taker signings (server clock), with a +-600-s
  time-shift null and an event block bootstrap. V1 (feed upstream of the broadcast) predicts the chat peak at the
  broadcast delay + platform latency: 60-300 s (GOTV tv_delay 90 s default; rulebooks 105 s to 3 min; co-streams add
  their own lag). V2 (feed built from the stream) predicts 0-20 s. A peak in [60, 300] s that beats the null at
  p < 0.0025 accepts V1; a peak in [0, 20] s accepts V2; neither = inconclusive. The same rule applies to the Twitch VOD
  replay (X53) if the user clears that access route.

## Findings (iteration 5); numbers in results/*.json
1. **The fill engine is valid; the replay gap is the quote rule (X57 step 1; `code/iter5/engine_check2.py`,
   `engine_check.json`).** The X44 strict price-time-priority engine, re-run with the wallet's OWN maker orders as "ours"
   (price, original size, post = sign + 24 ms, resting until its last real fill; the taker's volume re-allocated along
   the merged queue):

   | Split | Real maker shares | Assigned to the same tx | Phantom / real | Maker-only pair cost, real | Engine copy |
   | --- | --- | --- | --- | --- | --- |
   | BUILD | 794,778 | 88.3% | 6.4% | 0.9779 | 0.9752 |
   | VALIDATE | 937,868 | 88.8% | 6.5% | 0.9781 | 0.9745 |

   So the X44 replay's 1.005 came from what it quoted (one level at the 2-s-stale observed bid), not from the engine.
   (Side note: the X44 L = 3 variant double-counted volume across levels; `margin_replay.py` allocates sequentially.)
2. **Where the maker margin sits (X57 step 2, real wallet fills, 16-22 Oct).** Depth behind the transaction's best
   bid-equivalent price: touch 60-62% of shares, 1c behind 22%, 2c+ 15-18%; 60-s markouts rise with depth (touch
   +0.1 / +0.6c, 1c +0.7 / +1.2c, 2c+ +0.7 / +2.7c, BUILD / VALIDATE). Signed after the taker signed (in-delay): 15-16%
   of shares; in-delay at the touch against non-pack takers settles +3.65c / +2.81c per share (the panel's +3.0 / +3.2c).
   Pack takers: 16-18% of its maker shares, settlement -1.5c / -4.5c per share.
3. **A public ladder below the stale touch reaches the wallet's pair cost but not its PnL ranking (X57 step 3;
   `margin_replay.py`, `margin_replay.json`; top = others' bid observed >= 2 s earlier minus D, L levels 1c apart, 100
   shares, K 0.97).**

   | Variant | Pair cost B / V | Locked margin B / V | Residual B / V | corr(PnL, wallet PnL) BUILD P / S | VALIDATE P / S |
   | --- | --- | --- | --- | --- | --- |
   | D 0, L 1 (X44) | 1.010 / 1.008 | -$2.3k / -$1.9k | -$9.7k / -$9.1k | -0.31 / -0.13 | -0.06 / -0.04 |
   | D 2c, L 3 | 0.998 / 0.997 | +$0.4k / +$0.6k | -$14.4k / -$14.0k | +0.01 / +0.10 | -0.08 / -0.11 |
   | D 3c, L 5 | 0.990 / 0.993 | +$1.7k / +$1.5k | -$14.4k / -$14.3k | +0.15 / +0.22 | -0.10 / -0.08 |
   | D 4c, L 5 | 0.972 / 0.978 | +$3.8k / +$3.4k | -$13.4k / -$13.4k | +0.19 / +0.19 | +0.02 / -0.02 |
   | D 2c, L 5, IMAX 200 | 1.024 / 1.026 | -$4.2k / -$5.2k | -$8.2k / -$8.5k | -0.25 / -0.02 | -0.33 / -0.15 |

   Its own locked margin vs the wallet's PnL: VALIDATE +0.19 / +0.09 at D 4c. The public ladder copies the volume
   (paired-volume Spearman 0.79-0.92) and, 4c deep, the pair cost; but its unpaired residual loses $13-14k per split (it
   accumulates the losing side as the price trends), which the wallet avoids with its taker legs, pulls and re-pairs.
   Outcome stays unreachable from public data (best VALIDATE +0.02 / -0.02 against 0.5).
4. **Uncensored quote probes: the resting ladder is barely predictable from public state (X56, the presence pivot;
   `code/iter5/sweep_probes.py`, `sweep_probes.json`).** Probe = a fully consumed level of another taker's in-play
   multi-level sweep; under price-time priority y = 1 iff the wallet had an order resting there. 13,400 BUILD / 15,941
   VALIDATE probes (7,572 / 8,749 sweeps), base rate 0.25 / 0.30.

   | Model (BUILD fit) | VALIDATE AUC, logistic | LightGBM |
   | --- | --- | --- |
   | Activity (prints 10 / 60 s, game time, price level) | 0.663 | 0.632 |
   | + quote state (level vs others' 2-s-stale touch, others' pair sum) | 0.669 | 0.664 |
   | + own inventory (own state) | 0.695 | 0.715 |

   Gain of quote state over activity +0.032 [0.015, 0.047] (market bootstrap). The band rule P(y | level - stale touch)
   is flat (0.18-0.30 at 0..-6c and above): its ladder's presence at a level does not follow the public touch seen 2 s
   earlier. In the panel's terms ("AUC about 0.6"), its book presence depends on fast or private state (its own recent
   fills, re-quotes within the last 2 s), not on a public quote rule. Examinable on h1/h2 (on-chain probes).
5. **The wallet's input is not a superset of the pack's (X58, assumptions P1; `code/iter5/census.py`, `census.json`).**
   Informed BUY bursts (pack + wallet signers, 1-s linkage, >= 3c move of the bought token at +10 s), in play:

   | Split | Bursts | Wallet-led | Wallet-near (< 200 ms) | Wallet-late | Wallet-absent |
   | --- | --- | --- | --- | --- | --- |
   | BUILD | 1,845 | 8.9% | 6.6% | 4.2% | 80.2% |
   | VALIDATE | 1,941 | 11.4% | 4.4% | 4.4% | 79.8% |

   In wallet-absent bursts its complement bids (asks on the bought team) are hit in 19-22% of them: 24k / 30k stale
   shares (signed before the burst) and 11k / 12k in-delay shares, markouts -1.0 / -1.9 / -3.2c (BUILD, +10 / 30 / 120 s)
   and -1.5 / -1.7 / -1.6c (VALIDATE). In wallet-led bursts it is hit in 2-9%, almost only in-delay (its re-pair), and
   never stale on BUILD (271 stale shares on VALIDATE).
6. **The missed and the led bursts are different event types (X58 step 3; `census_event_types.py`,
   `census_event_types.json`; X50 recipe, 91 bo3 maps).** Binomial GLM with map fixed effects of the per-map burst share
   on team differences per 10 rounds: wallet-absent bursts (1,161 on 87 maps) follow round wins (dW +0.79, p 3e-9;
   nothing beyond wins: dFK -0.08, dBP -0.22, n.s.); wallet-led / near bursts (196 on 64 maps) do not follow round wins
   (dW +0.25, p 0.41) but follow bomb plants beyond wins (dBP +1.21, p 0.03; raw corr 0.34). This replicates the
   iteration-4 plant association of its takes (p 0.06) with another unit, and shows the complement: the pack's
   round-win-type events are the ones it misses.
7. **Live: at pack-only events it often pulls, sometimes before the pack (X58 step 4; `pack_event_pulls.py`,
   `pack_event_pulls.json`; server clock, 10-31 14:50-18:00).** Own-size cancels (100 / 68 / 58 / 54) on the consumed
   side:

   | Anchor | n | [-300, 0) ms before its signing | [0, 150) ms after | [150 ms, match) | Wallet maker hit in the tx |
   | --- | --- | --- | --- | --- | --- |
   | Wallet takes | 39 | 2.6% (null 4.7%) | 94.9% (null 3.8%) | 25.6% (15.0%) | 0% |
   | Pack takes, no wallet take within 3 s | 54 | 20.4% (null 0.9%) | 25.9% (null 0.9%) | 27.8% (11.1%) | 37% |

   So at about one pack-only event in five it pulls before the pack signs (it saw the event first; a zero-fill FAK of
   its own is possible, X46), at another quarter within 150 ms after (the same event a little later, or the public
   cancel wave), and at the rest it does nothing and is hit (37% of those pack txs fill its maker orders). With finding
   5: its detector sees a subset of the in-round events, earlier than everyone on those, and leaves the ladder exposed
   to the rest. (Some 100-share cancels may be other makers'; the null is 0.9%. CORRECTED in the late additions: the
   time-shift null does not match the activity phase; against a busy-phase control the excess is 2.8x before / 5x after
   the pack's signing, and no pre-pack pull shows the zero-fill FAK signature, so "it saw the event first" is not
   supported.)
8. **No leak from the delay queue (X60 step 3; `leak_control.py`, `leak_control.json`).** Non-own cancels on the
   consumed side in the arrival window [match - 1,045, match - 985] ms: retail takers (n 508) 8.5% vs 5.0% null (1.7x),
   no spike against the rest of their delay (1.1-1.8x in every 100-ms bin); pack 25.8% (4.8x), other large takers 35%
   (6.4x), the wallet 56% (7.3x; its window contains its own signing and the wave). Elevated rates appear only for
   informed orders, whose events are public through the wave; uninformed pending orders trigger nothing. Reading (c) of
   the panel (a leak) is not supported; the shared-source reading stands.
9. **Avoidance census (X60 step 1; `avoid_census.py`, `avoid_census.json`).** Presence in the wallet's 1,679 FAK txs
   over presence in 69,419 other in-play FAK txs more than 3 s from its takes, 24 makers with >= 1% presence; median
   ratio 0.80. r < 0.3: 0xe40ecff6 (0.05 [0, 0.16]; sigType 3; orders of 25k-150k shares), 0x2005d16a (the
   rn1-inplay-maker wallet; 0.10 [0.03, 0.20]; also 866 taker orders), 0x51dbdd2b (0.16 [0.08, 0.25]), 0xed446954 (0.27
   [0.18, 0.36]; the top in-delay poster). A low ratio needs only a reaction faster than ~1 s (its FAK matches 1.04 s
   after signing, the public wave starts +17-124 ms), so it marks fast makers, not necessarily co-subscribers; the
   sub-15-ms evidence (iteration 4) still names only 0x51dbdd2b.
10. **Price: own-cost anchors fail; K - L holds only right after its takes (X67, assumptions P3 step 1;
    `own_cost_anchor.py`, `own_cost_anchor.json`; 10,614 BUILD / 13,277 VALIDATE in-play CS2 maker orders).** Within
    one in-play tick on VALIDATE: K - average cost of the other token 5.8%, K - last fill price on it 21.6%, K - LIFO
    unpaired cost 13.8%, against the last print 33.8% on the same rows. K - (limit of its last take on the other token),
    K = 0.94: 56.7% when signed 0-1.04 s after the take (n 247; last print 4.3%), 27.5% at 1.04-5 s, 14% at 5-120 s, 6%
    later. The re-pair top is K - L, but only for ~2% of maker orders. Pair completion off its own cost (W6) is rejected;
    the sum p + own cost on the other token has median 0.97-0.98 with IQR 0.91-1.02 (no per-pair cap).
11. **Size: no global schedule (X59, mechanics P3; `size_schedule.py`, `size_schedule.json`).** One (a, b) on own
    pairs, public in-play USD or elapsed time fits 0-4% of the non-100 CS2 maker sizes within one share (the fit
    collapses to "always 100", 88.3% on VALIDATE). 28 events (36%) start below 100 (50-96, median 54) and step up
    monotonically (median share of non-decreasing steps 1.0); a non-100 size repeats the previous order's size in 92%;
    "previous size in the event" (own state) is within one share in 99.0% / 99.5%. Start size vs pre-game USD: Spearman
    0.55 (median $1,166 for starts below 100 against $8,137 at 100). The ramp is event-specific and its step clock is not
    decoded. The FINAL_RULE "54 / 58 / 68 near small inventories" is corrected: those were event sizes.
12. **Taker caps are a weak sub-policy (X62, assumptions P5; `taker_size_class.py`, `taker_size_class.json`).**

    | Class | Split | n | Fill median | Spearman(premium, 10-s move) | Markout 60 s | Settlement edge |
    | --- | --- | --- | --- | --- | --- | --- |
    | caps 1000 / 2000 | BUILD | 249 | 5.0% | 0.04 | +1.9c | +3.5% |
    | odd sizes | BUILD | 477 | 10.6% | 0.15 | +3.4c | +15.5% |
    | caps | VALIDATE | 140 | 5.8% | 0.13 | +0.3c | +2.6% |
    | odd sizes | VALIDATE | 749 | 14.7% | 0.09 | +2.2c | +10.6% |

    Daily cap share 6% (10-16), 52-64% (10-17/18), 31-32% (10-19/20), 13-20% (10-21/22), 0% on the 10-31 dev block: the
    caps were a probing / early version; odd sizes carry the information. (The Spearman here uses p(s+10) - p(s-1) of the
    public last print, lower than iteration 4's 0.26 with its own move definition.)
13. **Session-clean selection labels (X61, assumptions P4; `session_labels.py`, `session_labels.json`).** Operating
    windows from its orders in all markets: 10-16 13:38-18:51, 10-17 08:05-20:17 (gap 16:43-17:22), 10-18 14:00-16:44,
    10-19 08:04-21:56, 10-20 09:01-20:11, 10-21 08:04-23:25, 10-22 08:10-23:15 (gap 10:01-11:00). 64 of 256 BUILD events
    (5 of 128 VALIDATE) are skips while the bot had no order anywhere in [gs, gs + 1 h]. Refit on session-clean BUILD
    (same recipe): VALIDATE AUC 0.9586 vs activity 0.8964, gain +0.062 [0.019, 0.113], p 0.002, recall 0.778 at lift
    3.32 (the uncleaned recipe on the same features: 0.9574, recall 0.750, lift 3.31). League rates move (Stake Pulse
    0.78 -> 1.00, PGL 0.73 -> 0.86, NODWIN 0.28 -> 0.43). Per-day gains stay +0.034 (10-21, p 0.075) / +0.094 (10-22). A
    3-hour session on one VALIDATE day drops AUC to 0.89 (10-21) with lift ~3.25: downtime is the main exam risk for
    selection, and the rule cannot see it. Not adopted into the frozen rule (the gain is within noise, and the frozen
    pipeline computes its features from its own tapes); recorded as the candidate for the exam-constant refit.
14. **Requote trigger: co-occurrence, not a band (X63, mechanics P4, first pass; `requote_trigger.py`,
    `requote_trigger.json`; 5,373 own add bursts in 7 markets, server clock).** Within 50 ms before a burst: its own
    cancel 37.9% (null 1.6%), a near-touch change by others 44.5% (10.1%), a trade 2.6% (0.2%), none of these 37.1%
    (89%). But any non-own change in the 50 ms before vs after its bursts: 66.8% vs 69.1% (null 18.8%): symmetric, so the
    requotes and others' changes co-occur in busy phases rather than one following the other. Inter-burst intervals p10 /
    p50 / p90 = 22 / 501 / 8,077 ms, no period (2.5% in 1.00-1.15 s). The band hazard model with own-level tracking is
    still to do (open).
15. **No sibling client in the record (X66, mechanics P5, calldata part).** Among 114 makers with >= 200 orders in its
    markets, 16 are buy-only, whole-cent and sigType 3 like the wallet, but with dominant sizes 5 / 20 / 25 / 300
    (retail-like or other ladders); none has the 100-share ladder with event ramps. The merge-timer scan needs MERGE
    activity of other makers (not fetched).
16. **Ruled out with a measurement (X69, information panel iter4 critique 6).** Rerunning X51 on the taker-regime
    `sign_ms` would time pre-signing, not decisions: in the taker regime its FAKs reached the chain a median 34 s after
    signing (p95 291 s; 40 sampled txs with real block times, iteration 2) and each filled in one transaction, so its
    orders were signed in advance and fired later. Block time - 2 s (X51) is the right decision proxy there.

## Hypothesis ledger (iteration 5)
- W1 shared vendor: consistent (no leak, four fast avoiders, 0x51dbdd2b inside the pre-pull window in iteration 4).
- W2 delay-queue leak: not supported (finding 8).
- W3 partial detector: **supported** (findings 5-7): it misses ~80% of the pack's 3c+ bursts, which follow round wins,
  while its own follow bomb plants; at pack-only events it reacts in part, mostly after the pack (see the busy-phase
  correction to finding 7 in the late additions).
- W4 public ladder mechanics: the engine is valid and a 4c-deep public ladder reaches its pair cost, but the residual
  breaks the PnL ranking (findings 1-3): the margin is reproducible, the outcome is not.
- W5 one private valuation: partly (K - L right after takes; probe presence not predictable from public state).
- W6 pair completion off own cost: rejected (finding 10).
- W7 operator availability: real (64 BUILD skips out of session), small effect on VALIDATE metrics (finding 13).

## What is unexplained (quantitative)
- Taker input: upstream of every public trace on the events it acts on, but it acts on only ~20% of the informed 3c+
  bursts in its markets (the plant-type ones); the pack's round-win-type bursts are invisible to it or ignored.
- Maker quote: its resting presence at swept levels is predicted at AUC 0.66-0.67 from public state (0.72 with own
  state); the top is K - L for ~1 s after its takes and otherwise not anchored to any public quantity within one tick
  more than 34% of the time (last print).
- Outcome: the residual. A public ladder can lock pairs at the same 0.978 but loses $13-14k per split on unpaired
  inventory.

## Next iteration (plan)
1. 11-01 06-12 development block (the first with every recorder writing in all blocks): X38 under the pre-registered
   rule, X47b round markets before its signings, X54 synchronous pulls (dense label, refractory test), X63 band hazard
   with own-level tracking, census step 4 on more pack events, and the share of zero-fill FAKs at pack-only events.
2. Outcome: add a wallet-like exit to the public ladder (re-pair the long side after large repricings, a merge timer, a
   residual cap that pulls instead of shading) on the validated engine; score margin and residual separately.
3. Ask the user: the Twitch VOD chat access route (X53; affiliate VODs of 10-21/22 expire about 11-04/05), a PandaScore
   token (X55), HLTV page checks (X64), demo downloads (X37), Kick VOD (X4 / X22).
4. X65: pre-switch calldata of 0x51dbdd2b / P4e maker orders for a latency change point; X66: merge timers of the four
   fast avoiders.

## Late additions (iteration 5)
- **Census robustness** (`census.json`, keys `robustness_*`). Wallet-absent share among the informed 3c+ bursts: 78%
  when the wallet signed an order in the same market within 60 s (it was quoting); 77% for moves >= 8c; 74-76% for
  bursts of >= $100; 63-64% for bursts with >= 2 informed orders. At the event level (no wallet take in ANY market of
  the event within [-1, +30] s): 69% on both splits. So it takes in at most about 30% of the informed bursts in its
  markets.
- **T side by burst class** (`code/iter5/census_t_side.py`, `census_t_side.json`, half-level clock, 101 maps).
  Wallet-led / near bursts buy the T side 56.5% (n 154, p 0.13, map-bootstrap CI [0.49, 0.64]); wallet-absent bursts
  47.2% (n 971, p 0.08, CI [0.43, 0.52]). The difference (about 9 points, z about 2.1 unclustered) leans the way a
  plant-type trigger predicts, at weak power.
- **Oracle bound on the outcome (X57 step 4, DIAGNOSTIC: uses the wallet's private take times;
  `code/iter5/oracle_bound.py`, `oracle_bound.json`).** Base = the public 4c-deep 5-level ladder (this copy lets every
  level fill in a transaction before the inventory cap, so it differs slightly from `margin_replay.py`).

  | Variant | Pair cost B / V | Margin B / V | Residual B / V | corr(PnL, wallet) BUILD P / S | VALIDATE P / S |
  | --- | --- | --- | --- | --- | --- |
  | Public base | 0.963 / 0.966 | +$5.1k / +$5.6k | -$15.3k / -$15.5k | +0.11 / +0.11 | +0.09 / +0.01 |
  | + oracle pulls at its takes | 0.964 / 0.965 | +$4.9k / +$5.7k | -$14.7k / -$15.5k | +0.10 / +0.08 | +0.09 / +0.02 |
  | + oracle re-pair at K - L for 5 s | 0.956 / 0.952 | +$5.8k / +$7.6k | -$14.5k / -$16.0k | +0.18 / +0.13 | +0.26 / +0.13 |
  | + a copy of its taker fills | 0.948 / 0.951 | +$10.1k / +$11.0k | -$13.6k / -$15.4k | +0.56 / +0.26 | +0.24 / +0.24 |

  Even with every private take event of the wallet (pulls, re-pairs and its own take fills), a public-anchor ladder
  reaches only 0.24-0.56 Pearson and 0.24-0.26 Spearman, because its residual (-$14-16k per split) is far larger than the
  wallet's. The missing piece for the outcome is the wallet's maker quote presence itself (where its ladder is NOT when
  a price trends), which the probes show is not a function of public state. Quantitative account for the outcome gap:
  public ladder +0.01..+0.09; + the private take events +0.15..+0.24; the rest (to the wallet's own ranking) is its quote
  presence.
- **Price anchor from the matched-order record** (`code/iter5/revealed_bid_anchor.py`, `revealed_bid_anchor.json`; CS2
  maker orders in play, the revealed best bid of the other makers in the latest public tx before signing). Within one
  in-play tick on VALIDATE: revealed bid 0.251 (block clock) / 0.277 (match clock) against the last print 0.218 / 0.248
  on the same rows; revealed ask - 1c 0.248 / 0.278; exact 0.09-0.11. A 3-point gain over the last print, far from 0.8.
  Not adopted.
- Time used this iteration so far: about 50 minutes at this point (19:21-20:11 UTC).
- **The fast makers predate the switch (X65 partial; `cosub_history.json`; 1,600 sampled in-play taker txs of the 121
  non-GRID Stake Pulse / PGL / NODWIN markets with game start 10-12..10-15, calldata decoded into
  `.cache/re/tommy-cs2-maker/pre_switch/`).** Presence in other takers' txs before vs after 10-16: 0x51dbdd2b 5.9% vs
  6.7%, 0xed446954 9.1% vs 8.8%, 0x2005d16a 7.0% vs 5.2%, 0xe40ecff6 0.8% vs 2.4%. Share of their filled orders signed
  inside the taker's delay: 0x51dbdd2b 23.7% vs 17.8% (offsets p10 / p50 216 / 727 vs 136 / 668 ms), 0xed446954 12.4% vs
  18.0%, all makers 16.7% vs 16.5%. On this proxy nothing changed at the switch: the fast makers were already in these
  leagues, which fits "the wallet bought into an existing source" (information panel P5, second signature). An event-
  latency change point still needs an event clock before 10-16.
- **Which informed bursts it leads, by public state** (`census.json` `which_bursts_it_leads`). Univariate AUCs of led /
  near vs absent: price level 0.44-0.47 (it leads more when the bought team is at 0.2-0.5: 19-22%, and rarely at 0.8-1.0:
  3-8%), match vs map market 0.46 (match 19%, map 15%), game time 0.53-0.56 (more after 2 h), burst USD 0.59. No public
  filter explains why it is absent from about 80% of the informed bursts; the absence is an event-type matter (round wins),
  not a price or market filter.
- **Band hazard with own-level tracking (X63 second pass; `code/iter5/band_hazard.py`, `band_hazard.json`; 10-31
  14:50-18:00, server clock, 7 token-0 books, both of its ladders).** Own orders by fingerprint (adds of 100 / 68 / 58 /
  54 at whole cents, own-size cancels, capped by the level size); others' best = best level net of own orders.
  - Price at its 5,853 re-quote bursts (all of them, not only filled orders): new top minus others' best just before =
    0c in 37.0%, +1c 11.9%, -1c 15.5%, -2c 7.4%, +2c 5.0%, +3c 5.7%, -3c 5.0%: **"join the other makers' best bid"
    is within one tick in 67.4%** (filled orders gave 45.6% because fills select the improving orders). Live only; the
    historical anchors stay at 25-34%.
  - Hazard after a change of others' best (10,280 changes): an own add or cancel on that side within 100 ms in 22-37%
    at gaps of -3c..+3c (null 2-5%), 7% when it sits 6c+ behind, 11% when it has no level there; within 500 ms 40-54%
    (null 9-17%). It reacts to others' best within ~100 ms at any gap, with no threshold: a fast touch-follower, not a
    band. Together with the symmetric co-occurrence (finding 14), the makers in these books re-quote on each other's
    changes.
- **Probe label validated against the live book (X56 step 2; `code/iter5/probe_validate_live.py`,
  `probe_validate_live.json`).** 153 probes of the 10-31 block (other takers' multi-level sweeps in its CS2 markets). The
  live own-level tracker needs two fixes to be comparable: (1) the fingerprint must use its actual order sizes in that
  market (the event size schedule adds 57 / 59 / 60 ... to 100 / 68 / 58 / 54); (2) the book update of a match is stamped
  about 20 ms BEFORE its trade message, so the state must be read before the match (m - 150 ms). Then the probe label
  and the live own level agree in 90.8% (both absent 95, both present 44, live-only 6, probe-only 8), short of the
  panel's 95% target but enough to use the probes as a label of the resting ladder. (The band-hazard pass above used
  the 4-size fingerprint and covers the bulk of its levels.)
- **Azuro (X41) is infeasible from this laptop.** The current toolkit (@azuro-org/toolkit 7.2.0, read from unpkg) uses
  `https://api.onchainfeed.org/api/v1/public` + `/market-manager/{sports,games-by-filters,navigation,search}` and the
  subgraphs on `thegraph.onchainfeed.org`. Every feed path answers nginx 404 on api.onchainfeed.org and on
  preprod-api.azuro.org (GET .../market-manager/sports?environment=PolygonUSDT -> 404), the gateway docs path answers
  404, and thegraph.onchainfeed.org fails DNS (getaddrinfo 11001); the earlier hosts failed the same way (iteration 4).
  Used instead: Polymarket's books, the sports socket, bo3.gg and the SX Bet listing.
- Time used this iteration: about 67 minutes of analysis plus write-up (19:21-20:30 UTC). Status: continue. Recorders
  at the end: shared recorder OK (current block sealed); own `tommy_cs2_near` (pid 29844), `tommy_dota_live` (pid
  14548), `tommy_cs2_rounds` v2 (worker 8668) and `tommy_chat` v2 (worker 536) running, hard stop 11-03 00:00 UTC.
- **X38 analysis frozen in code before any data** (`code/iter5/chat_leadlag.py`): chat z-score per 1-s bin
  (rolling 120-s median / MAD), event-triggered average around the wallet's takes at lags -60..+600 s, 5-s smoothing,
  peak lag L* in [0, 600] s; null = takes shifted +-[600, 1800] s (2,000 draws); event block bootstrap of L*; decision
  V1 if p < 0.0025 and L* in [60, 300] s, V2 if p < 0.0025 and L* in [0, 20] s, else inconclusive. Dry run on 10-31
  12-18: no chat data yet (pairs = 0), as expected. Run it on 11-01 06-12 with that block's calldata.
- **Correction to finding 7 (busy-phase control; `pack_event_pulls.json`, `pack_prepull_signature.json`).** The
  time-shift null of finding 7 does not match the activity phase. Around 401 retail BUY takes (> 3 s from informed
  takes) the same own-size pulls occur in 7.2% ([-300, 0) ms) and 5.2% ([0, 150) ms). Against that busy-phase control,
  pack-only events show 2.8x (before the pack signs: 20.4%) and 5x (within 150 ms after: 25.9%). None of the 11 pre-pack
  pulls carries the zero-fill FAK-return signature (0 of 11; they sit 173-299 ms before the pack's signing, several at
  the window edge, with own re-adds inside 60-1,000 ms): they look like routine cancel-repost cycles. Revised reading: it
  reacts to some pack-only events, mostly AFTER the pack signs (via the public wave or a slower path of its feed); it is
  not first on them and makes no visible attempt to take; its ladder is hit in 37% of those transactions.

---

# Iteration 6 (2026-10-31, started 20:57 UTC; 368 of 1200 budget minutes used before it)

Read first: NOTES (iterations 1-5), state.json, FINAL_RULE.md, panels/iter5_{information,mechanics,assumptions}.md. No
EXAM or wall-audit files. Calendar: no released lots; the current block 10-31 18-24 UTC is SEALED, so no new
development live data arrives during this iteration (next development block 11-01 06-12). Shared recorder status OK at
21:01 (clob_wallets 400 tokens, sports connected). Own recorders running: `tommy_cs2_near` (pid 29844, 31.8 MB),
`tommy_dota_live` (14548), `tommy_cs2_rounds` v2 (8668), `tommy_chat` v2 (536); all with hard stop 11-03 00:00 UTC.
The 15 iteration-5 panel proposals are catalog items X70-X84 (information P1-P5 = X70-X74, mechanics P1-P5 = X75-X79,
assumptions P1-P5 = X80-X84; mapping in state.json).

**Pivot (required: progress 0.595 for three iterations).** Iterations 3-5 treated the taker as a *partial detector*
(an event-type filter) and the maker ladder as a fill/quote-presence problem. This iteration changes the unit of
decision and the model class: the unit is the **informed event** (every 3c+ informed burst in its markets), labelled
three ways from uncensored data (it TAKES; it is SEEN-and-dodged: its resting ladder is gone at the pack's sweep; it is
HIT: its stale bids fill), and the model is a **policy over events it sees** (take iff edge after the hurdle and the
stale depth left; dodge otherwise), tested against the partial-detector and the intermittent-source models. On the live
block the same events give the mechanism test of the dodge (locked to the public cancel wave, or to the event).

## Competing explanations (iteration 6) and the observation that separates them
1. **Y1 complete feed + economic take filter.** It sees nearly every in-round event of its matches (round wins too),
   takes only when the stale depth left after the fast makers' cancels and its edge clear premium + net fee, and
   otherwise protects its ladder. Separator: its ladder is absent at the pack's sweeps far from its own takes (dodge),
   its pulls at pack-only events are locked to the EVENT (tight u - p, independent of the public wave), and taken vs
   seen-not-taken events separate on depth left / edge.
2. **Y2 partial detector + public-wave follower.** Its feed carries some event types only (plants); at the others it
   follows the public cancel wave within tens of ms. Separator: pulls at pack-only events are locked to the wave
   (u - w tight, slope ~1 on w - p); dodged and hit events do not differ in depth / edge once the wave is controlled.
3. **Y3 intermittent per-match source** (stream session, relay connection, scout). Separator: within-market
   persistence of presence survives stratification by price level, market type and game time; the dodge follows the
   same on / off state (if the source is off it neither takes nor dodges).
4. **Y4 bookmaker in-play odds as the input** (organiser-bookmakers 1win / Stake run several of its leagues; limit =
   odds value - margin, which the 2-5c overshoot of iteration 4 does not reject). Separator: take rate and edge by
   league owner (bookmaker-run vs not) beyond activity; event types = what books suspend on.
5. **Y5 one operator, two wallets** (the wallet + 0x51dbdd2b, co-timed within ~10 ms). Separator: shared funding,
   direct transfers, synchronized withdrawals.
6. **Y6 liquidity provision is the money, the taker leg is a sideshow.** Separator: an activity-only pseudo-PnL and a
   maker-only ceiling reach the outcome target (>= 0.5) without the taker leg.
7. **Y7 broadcast-delay arbitrage on a low-latency stream** (Kick LL-HLS vs Twitch). Separator: edge and take rate by
   stream platform; the X38 chat clock (pre-registered) on development blocks.

## Findings (iteration 6); numbers in results/*.json
1. **At the pack's events it does not detect, its pulls are locked to the public cancel wave, not to the event (X78,
   mechanics P4; X80 step 2, assumptions P1; `code/iter6/wave_lock.py`, `wave_lock.json`; 10-31 14:50-18:00,
   BUILD-live, server clock, own sizes = its actual maker sizes per market).** p = the taker's signing, w = the first
   NON-own cancel on the consumed side in (p, match), u = its first own-size cancel there in [p - 300 ms, match).

   | Anchor | n | Own pull | Wave | u - p p25 / p50 / p75 (ms) | u - w p25 / p50 / p75 (ms) | Slope of u - p on w - p (corr, perm. p) | u before w |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | Its own takes | 39 | 97% | 95% | 14 / 15 / 17 | -90 / -26 / +3 | -0.05 (-0.12, p 0.84) | 69% |
   | Pack takes, no wallet take within 3 s | 54 | 48% | 78% | 29 / 37 / 985 | +8 / +15 / +62 | +1.40 (+0.81, p 0.008; 14 events) | 14% |
   | Retail BUY FAKs (busy-phase control) | 401 | 32% | 59% | 354 / 942 / 1,628 | 0 / +124 / +422 | +2.14 (+0.37) | 18% |

   At its own takes the pull is event-locked (IQR 3 ms, independent of the wave, before it in 69%). At the pack's
   events it pulls in about half, and then a median 15 ms AFTER the first public cancel (57% within 0-30 ms of it), with
   u - p spread over a second: a book reaction at ~15 ms (a co-located client), not its feed. The pull barely protects
   it: its maker orders fill in the pack's tx in 39% with a pull and wave, 42% with a wave and no pull, 22% with neither.
   So Y1 (complete feed, chooses not to take) is not supported: it does not see the pack's round-win-type events before
   the public book. The "dodge" of the historical probes (presence 12-19% at pack sweeps vs 31-34%) is consistent with
   this fast wave-follower plus composition; the follower is public (the examiner's books record the wave).
2. **The per-match "on / off" state is mostly sequence composition (X72, information P3; `coverage_state.py`,
   `coverage_state.json`; census bursts, wallet-late dropped).** Persistence diff = P(present | previous burst in the
   market within 120 s present) - P(present | previous absent): BUILD 0.126, VALIDATE 0.124.

   | Null (2,000 draws) | BUILD null median, p | VALIDATE null median, p |
   | --- | --- | --- |
   | Labels permuted within market | 0.035, p 0.0025 | 0.040, p 0.0035 |
   | Within market x price bin x reversal x game-time strata | 0.090, p 0.089 | 0.063, p 0.009 |
   | Composition only (match / map x price x reversal x game time, no market term) | 0.021, p 0.002 | 0.017, p 0.0015 |

   Stratifying by the reversal structure, price and game time absorbs most of the persistence (null median 0.035 ->
   0.06-0.09); a residual remains (VALIDATE p 0.009, BUILD p 0.09). The reversal effect is the strongest single pattern:
   present 29-35% when the previous burst within 120 s was on the OTHER team, 5.6-8.0% when on the same team, 19-20%
   with no burst within 120 s. A public-covariate model of which informed bursts it leads (BUILD fit; match / map,
   reversal, same-team, game time, |p - 0.5|, p, log move, log USD, orders) scores VALIDATE AUC 0.747; adding the lagged
   own label adds +0.009 (0.756). CORRECTION (point in time, `led_burst_pit.json`): move, USD and order count are
   measured after the burst starts; with pre-burst public features only (reversal, same team, log gap, game time,
   match / map, price level, |p - 0.5|) the VALIDATE AUC is 0.698, and the reversal pair alone 0.649. Reading: its events are the first move against the last informed burst (a plant
   after the other team won a round, a retake), and the pack's same-direction follow-ons (round ends after its events)
   are where it is absent; Y3 (an intermittent per-match source) loses most of its support.
3. **Outcome item: the activity baseline already reaches Pearson 0.5, and no single leg does (X82, assumptions P3;
   `outcome_baseline.py`, `outcome_baseline.json`).** Per-market correlation with the wallet's settlement PnL:

   | Quantity (wallet txs excluded from public ones) | BUILD P / S | VALIDATE P / S | VALIDATE partial given log prints, P / S |
   | --- | --- | --- | --- |
   | In-play public taker print count (= c x prints pseudo-PnL) | +0.41 [0.11, 0.65] / +0.18 [0.00, 0.35] | +0.51 [0.32, 0.67] / +0.37 [0.19, 0.53] | - |
   | Public taker USD | +0.37 / +0.13 | +0.39 / +0.33 | +0.11 / -0.00 |
   | Total variation of the 10-s last price | +0.40 / +0.21 | +0.48 / +0.30 | +0.28 / -0.02 |
   | Net displacement | -0.09 / +0.00 | +0.01 / -0.01 | -0.02 / -0.04 |
   | Its own locked margin (pairs x (1 - pair cost)) | +0.85 / +0.66 | +0.82 / +0.75 | +0.79 / +0.71 |
   | Its maker fills alone, settled | +0.39 / +0.50 | +0.38 / +0.34 | +0.39 / +0.34 |
   | Its taker fills alone, settled | +0.15 / -0.05 | +0.10 / +0.13 | +0.04 / +0.11 |

   Market counts 113 (BUILD) / 107 (VALIDATE); 95% CIs from a market bootstrap. So: (a) any executable rule with a stable small margin per
   print co-occurs at Pearson ~0.5 on VALIDATE; a pass on item 5 must be reported against this baseline and its partial
   correlation given prints. (b) A perfect copy of its maker leg alone settles at 0.38 / 0.34 (VALIDATE) and its taker
   leg alone at 0.10 / 0.13: the outcome lives in the pairs formed ACROSS the legs (locked margin 0.82 / 0.75). Item 5 is
   reachable only with both legs, i.e. with the taker input. Pre-registered from now on: the outcome metric is reported
   with `pnl_baseline_prints` and the partial correlation given log prints.
4. **The two tokens are quoted one side at a time, under a soft pair cap (X81 steps 1-2, assumptions P2;
   `joint_quote.py`, `joint_quote.json`; 5,622 own add bursts with own levels on both tokens).** Its own pair sum (top
   bid token 0 + top bid token 1) after each burst: p10 / p25 / p50 / p75 / p90 = 0.92 / 0.95 / 0.97 / 0.99 / 0.99
   (IQR 4c; modes 0.99 23%, 0.98 22%, 0.97 16%); others' pair sum 0.93 / 0.96 / 0.98 / 0.99 / 0.99. Every burst adds on
   one side only (the other side's top is unchanged in 100% of bursts). The quote is not one (mid, spread) pair (IQR
   4c > 1c); each side follows its own book with the sum capped at about 0.99. On the token not touched by the burst,
   join others' best is within one tick in 0.63 / 0.70 (first / second half), K - trigger top (K 0.98 fitted on the
   first half) 0.63 / 0.59, min(join, K - trigger) 0.67 / 0.73: the cap adds ~2 points, as the mechanics panel found.
5. **Exam lots' league mix from the listing projection (X84, assumptions P5; `exam_league_mix.py`,
   `exam_league_mix.json`; listing-time fields only, projected in memory, fetched without the shared cache, nothing
   raw stored).** h1: 180 CS2 events, 80 GRID, 100 non-GRID of which 26 (26%) in 2 leagues absent from the v3 exam
   table; h2: 157 / 62 / 95, 24 (25%) in 3 unseen leagues. Non-GRID tiers: h1 tier 5 62, tier 2 18, tier 4 16, tier 3
   only 4; h2 60 / 13 / 16 / 6. Below the panel's 30% switch threshold: v3 stays frozen (pre-registered now; the X31
   pack-lag variant remains the documented fallback). Note: tier-3 non-GRID events, its main habitat in 16-22 Oct, are
   rare in the exam lots, so the exam's base rate and recall will rest on tier-4/5 leagues.
6. **Resting occupancy on the live book is not a fast public function (X70 steps 1-2, information P1; X80 step 1;
   `live_occupancy.py`, `live_occupancy.json`).** Dense label: every 1 s per token-0 book side, each whole-cent level
   from others' best +2c to -8c, y = an own order rests there (627,712 level-samples, base rate 0.272; presence at
   others' best 0.47, 1-4c behind 0.35-0.36, 5c+ 0.17-0.29, above others' best 0.04-0.13). First half fit, second
   half scored: gap only AUC 0.635; all fast public features (gap, others' size at / ahead of the level, non-own
   cancels within 2c of the touch in the last 200 / 1,000 ms, others'-best changes in 500 ms, time since others'
   best changed, time since the last trade, price level) 0.688 logit / 0.767 LightGBM. Importance: price level 2,410,
   others' size at the level 1,720, gap 1,540, size ahead 1,435, time since trade 1,188, since best change 619;
   the delay-window cancel features 6 / 38 / 44. The assumptions panel's "signature if false" holds for presence:
   sub-second waves explain nothing of where its ladder sits; slow book shape gives 0.77 (one block, book identity
   may inflate it). The outcome replay with this ladder (step 3) is left for the 11-01 blocks. Leave-one-book-out
   (6 books with both classes): fast public features 0.74 / 0.47 / 0.56 / 0.70 / 0.77 / 0.77 (median ~0.72), gap only
   0.67 / 0.38 / 0.51 / 0.65 / 0.65 / 0.70 (median ~0.65): the slow-book-shape model transfers across markets only
   partly, with two books near chance.
7. **The reversal effect, decomposed (`reversal_detail.json`; census bursts, wallet-late dropped).** P(it leads the
   burst) by the previous burst in the market:

   | Gap to the previous burst | Previous burst | Same team BUILD / VALIDATE | Other team BUILD / VALIDATE |
   | --- | --- | --- | --- |
   | 0-5 s | pack only | 8.4% (297) / 6.3% (284) | (1 / 4 cases) |
   | 5-30 s | pack only | 12.3% (146) / 9.9% (172) | 28.6% (91) / 23.2% (99) |
   | 30-120 s | pack only | 7.3% (192) / 14.1% (213) | 35.7% (112) / 26.4% (140) |
   | 120-600 s | pack only | 13.9% (230) / 18.1% (232) | 21.7% (207) / 19.2% (214) |
   | 5-30 s | wallet | 30.0% (30) / 33.3% (36) | 26.9% (26) / 25.0% (28) |
   | 30-120 s | wallet | 12.5% (24) / 16.7% (48) | 29.0% (31) / 44.8% (29) |

   Within 5-120 s after a pack-only (round-win type) burst on team X, it leads the next informed burst 2-5x more often
   when that burst is on the OTHER team: its events are the in-round turn against the team that just gained (the
   next round's plant / man advantage of the other side). An economy reading (the surprise is larger against the
   round winner) was tested with bo3.gg per-round equipment (`census_event_types_econ.py`,
   `census_event_types_econ.json`, 91 maps): its per-map share does not load on upset wins (dU p 0.75) or on breaks
   (rounds won right after the opponent won; dBR p 0.92); bomb plants stay the only lead (dBP +1.03, p 0.059). The
   absent bursts load on round wins (p 3e-9) and weakly on upsets (p 0.10). So the reversal is a sequence property of
   its event class, not a per-map count.
8. **Funding graph: no shared counterparty (X74, information P5; `funding_graph.py`, `funding_graph.json`; Polygon
   eth_getLogs of USDC.e and USDC Transfers, blocks 95,371,932-96,005,476 = 10-12..H).** The wallet: $1.01M in / out
   with Polymarket contracts (CTF 0x4d97dcd9, the V2 collateral wrapper 0xc011a7e1 seen minting on its MERGE
   receipts, exchanges, adapters) and one external counterparty, 0x4cd00e38 (2 outgoing transfers, $2,220).
   0x51dbdd2b: $173k / $175k with Polymarket contracts and one external sender, 0x3a3bd7bb (73 small incoming
   transfers, $2,104: a payout pattern). The wallet's owner EOA 0x8af810f0: $2,000 in from 0xf70da978 and $2,000 out
   to 0x116342d6 (followed by address-poisoning dust from look-alike 0x1163...3829 addresses); 0x51dbdd2b's signer
   0xdecd4b4c: none. No overlap between the two sides, no direct transfer. Y5 (one operator) gets no support in this
   window (USDC only; POL funding of the EOAs and earlier history not scanned).
9. **Led share by organiser owner and stream platform (X85 / X86; `burst_by_owner.py`, `burst_by_owner.json`).**
   Sportsbook-branded leagues (1win, Stake: 28 events) 0.160 [0.135, 0.185] vs others (49 events) 0.168 [0.143,
   0.195]: no bookmaker effect (Y4 not supported). Kick 0.176 [0.152, 0.202] (53 events) vs Twitch 0.141 [0.117,
   0.165] (23 events): a weak platform difference (Y7 open). By league: 1win 0.09, PGL 0.14, 1win Private Club 0.14,
   DraculaN 0.16, Stake Pulse 0.17, NODWIN 0.20, Stake Ranked 0.20, Circuit X 0.24, CIS LAN 0.27.
10. **Organiser-side sources, first pass (X71, information P2; web search as a normal visitor).** Traded leagues of
    16-22 Oct: DraculaN (Digital Crusade, Bucharest; offline series with online stages), 1win Private Club #2
    (offline, Serbia, 19-22 Oct), Stake Ranked (StarLadder LAN circuit), Stake Pulse (Black Molly Entertainment
    studio), Circuit X Curitiba (offline LAN, Brazil), NODWIN Clutch Series (online), PGL Bucharest qualifier
    (online). A LAN-only selection is therefore not the rule (online NODWIN 6 / 23 and PGL qualifier 9 / 13 traded).
    The tournament hub rdy.gg (lists "live standings, match and map results") answers HTTP 403 to a plain fetch
    (bot protection; not bypassed). No public CSTV / GOTV+ relay link or live match panel was found for these
    leagues in this pass.
11. **SX Bet trade history is not key-free (X73).** `api.sx.bet/trades` and `/trades/consolidated` answer 404
    {"message":"Not Found"}; `/sports` and `/leagues/active` answer 200 (listing only). The chain route (SX Network
    RPC and the exchange's fill events) was not verified this iteration.
12. **Price: an aggressor-side-adjusted last print adds nothing historically; the frozen live join rule is in
    `evaluate()` (`price_side_anchor.py`, `price_side_anchor.json`; `final_rule._live_price`).** Historical (all
    in-play CS2 maker orders): last print 0.306 / 0.305 (BUILD / VALIDATE); side-adjusted (hit: print, lift: print -
    1c; fitted on BUILD) 0.316 / 0.313; by print age 0.36-0.38 within 10 s, 0.18-0.19 beyond 60 s. 27% of the orders
    whose last print hit the bid sit 6c+ below it (deep ladder levels): no point anchor on the tape can reach 0.8 on
    filled orders. Live (frozen in `final_rule.py`, constants LIVE_VIEW_MS 100, PAIR_CAP 0.99; BUILD-live check on the
    10-31 block, 172 filled maker orders with books): join others' best (own levels removed) within one tick 0.424
    (exact 0.198), with the 0.99 pair cap 0.424, against the last trade on the same rows 0.187. The future-block
    examiner now gets `live_price` from `evaluate()`.
13. **A hard 1.5-s re-post timer (X79 steps 1-2, mechanics P5; `cooldown.py`, `cooldown.json`; BUILD-live).** Own
    cancel -> next own add on the same side: 225 intervals in [1,500, 1,520) ms against 4-12 per 20-ms bin around it
    (29 in the bin before, 21 after). The cancelled level's age is not constant (p10 / p50 / p90 121 ms / 3.3 s /
    49 s): not a refresh timer. The re-post lands at the cancelled price in 50.8% (other cancels 14.9%); a non-own
    change in the 100 ms before the cancel in 50% (other cancels 67%). So one cancel class is "pull, wait exactly 1.5
    s, re-post at the same price": deterministic 1.5-s holes in the ladder, part of its patchy presence and a
    software fingerprint (the sibling scan across all books, step 4, remains).

Caveat to finding 1: half of its pulls at pack-only events come 29-37 ms after the pack's signing, i.e. 12-20 ms after
a first public cancel that itself comes 14-17 ms after the pack signs (probably the pack client's own complement pull,
the same mechanism the wallet shows at its takes). The slope test rests on 14 events; the decisive part is that in
the events with a late first cancel the wallet's pull is late too (u before w in only 14%).

## Live split re-registered (written before any 11-01 data exist)
The iteration-2 live split put VALIDATE-live at development blocks from 11-01 18:00 UTC. At the current pace (about
95 budget minutes per ~2 h of wall clock) the 1,200-minute budget ends around 11-01 10:00-12:00 UTC, before that block,
so no live rule could ever be validated. Re-registered now, before any record of 11-01 exists: BUILD-live = the
10-31 12-18 block; VALIDATE-live = the 11-01 06-12 block and every later development block. Frozen live rules to be
scored there without refitting: `final_rule._live_price` (join, LIVE_VIEW_MS 100, PAIR_CAP 0.99), the wave follower
(H62: first own-size pull within 0-30 ms after the first non-own cancel at pack-only events), the 1.5-s re-post
timer, and the occupancy model recipe of `live_occupancy.py` (refit allowed only on BUILD-live).

## Hypothesis ledger (iteration 6)
- Y1 complete feed + economic take filter: **rejected for the pack's events** (finding 1: wave-locked pulls; 14% before
  the wave vs 69% at its own takes). X83 ruled out on this measurement.
- Y2 partial detector + public-wave follower: **supported** (findings 1, 2, 7; BUILD-live for the follower).
- Y3 intermittent per-match source: mostly composition (finding 2); residual persistence p 0.009 (VALIDATE).
- Y4 bookmaker odds feed: no support from take shares (finding 9); odds probes (X48) still not run.
- Y5 one operator, two wallets: no shared USDC counterparty or transfer 10-12..H (finding 8); but 0x51dbdd2b reacts
  to the wallet's event class and not to the pack's (finding 21): one shared source (or one operator) stays open.
- Y6 liquidity provision is the money: rejected for the outcome item (finding 3): the maker leg alone 0.38 / 0.34,
  activity alone 0.51 / 0.37, both legs' margin 0.82 / 0.75.
- Y7 low-latency stream platform: weak (finding 9), open.
- Maker quote: not one two-token quote (finding 4); occupancy not a fast public function (finding 6); a 1.5-s re-post
  timer (finding 13).

## What is unexplained (quantitative)
- The taker input: upstream of every public trace on its events; 16-20% of the informed bursts in its markets,
  concentrated on the first in-round turn against the team that just gained (2-5x within 5-120 s after a pack burst
  on the other team). Its event stream is not public; no organiser-side source was found; SX trade history is keyed.
- The maker ladder: occupancy AUC 0.77 from slow live book shape (one block), 0.635 from the gap; price on filled
  orders 0.42 (live join) and 0.31 (historical); the deep states are its own history (fills, cooldowns, takes).
- The outcome: needs both legs; activity alone already gives 0.51 / 0.37.

## Next iteration (plan)
1. When 11-01 06-12 data exist (VALIDATE-live under the re-registered split): score the frozen live rules (live
   price, wave follower, cooldown) and the X38 chat clock (pre-registered), X47b, X54.
2. X79 step 4: scan every CS2 book of `tommy_cs2_near` (dev-start units only) for the 1.5-s same-price re-post with
   consistent sizes; map sizes to wallets through calldata (sibling software, C8).
3. X77 series fair value (historical price anchor), X76 oracle-leg hedge search (wall account for outcome), X73 SX
   chain fills, X71 second pass (Liquipedia pages of the traded leagues: server / platform fields).
4. Ask the user (unchanged): X53 Twitch VOD chat route (VODs of 10-21/22 expire ~11-04/05), X55 PandaScore token, X64
   HLTV pages, X37 demos, X4 / X22 Kick VODs, X48 odds-source probes.

## Late additions (iteration 6)
14. **The 1.5-s re-post timer is shared with other bots (X79 step 4; `cooldown_siblings.py`, `cooldown_siblings.json`;
    every CS2 book of `tommy_cs2_near` 14:50-18:00 whose unit started in a development block, sealed-start units
    dropped before counting).** Same-size, same-price re-adds 1,490-1,530 ms after a trade-free decrease, against the
    same pairing at 1,290-1,330 and 1,690-1,730 ms (two control windows summed):

    | Markets / size | Spike pairs | Control pairs (two windows) |
    | --- | --- | --- |
    | Traded by the wallet, 100 | 221 | 105 |
    | Traded, 70 / 99.99 | 45 / 36 | 0 / 0 |
    | Untraded, 100 | 656 | 392 |
    | Untraded, 30 | 324 | 55 |
    | Untraded, 23.25 / 88.52 / 99.98 | 33 / 32 / 29 | 2 / 0 / 2 |
    | Untraded, 10 / 15 / 5 | 4,321 / 362 / 357 | 11,135 / 3,411 / 798 (no spike) |

    Several ladders in markets the wallet never trades (GRID events included, e.g. FOKUS-BakS, Gamers Club lowcor1-tdp,
    ESEA ep-dnk2) carry the same 1.5-s same-price re-post, so it is a common client behaviour (a shared library or
    framework default), not a unique fingerprint of this operator. The 100-share untraded excess could be the same
    software in other hands; mapping it to wallets needs the calldata of those markets.
15. **Outcome ceiling with an exact copy of its maker leg plus a public residual hedge (X76, mechanics P2 step 1;
    DIAGNOSTIC, uses its real maker fills; `hedge_ceiling.py`, `hedge_ceiling.json`).** Hedge H(X): when |inventory|
    exceeds X, buy the short outcome at the first public taker BUY print at least 2 s later, at that price + 1c, within
    120 s. Per-market correlation with the wallet's PnL, Pearson / Spearman:

    | Variant | BUILD | VALIDATE | Sum PnL B / V |
    | --- | --- | --- | --- |
    | Maker leg only | 0.39 / 0.50 | 0.38 / 0.34 | -$0.1k / +$4.1k |
    | H(100) | -0.22 / 0.04 | 0.25 / 0.23 | -$4.6k / -$6.3k |
    | H(400) | 0.12 / 0.26 | 0.62 / 0.42 | -$1.8k / -$0.3k |
    | H(600) | 0.20 / 0.40 | 0.62 / 0.50 | -$0.8k / +$3.0k |
    | H(800) | 0.23 / 0.40 | 0.56 / 0.54 | -$1.3k / +$3.8k |

    The BUILD choice is no hedge (every hedge lowers BUILD), which scores 0.38 / 0.34 on VALIDATE; hedges help only on
    VALIDATE and lose money. So even an exact maker copy with a BUILD-chosen public residual control stays below 0.5:
    the outcome item needs its private taker leg (the wall account's outcome number: maker copy 0.38 / 0.34, activity
    baseline 0.51 / 0.37, both legs' locked margin 0.82 / 0.75).

16. **No price unit reaches 0.8 on the live book, own state included (X75, mechanics P1; `price_units.py`,
    `price_units.json`, `live_price_branches.py`, `live_price_branches.json`; BUILD-live).** Join others' best (own
    levels removed) within one tick: (a) filled orders 0.419 (172); (b) every own add 0.380, the ladder rule "k-th
    level of the burst from the top = J - k cents" 0.396 (7,137 adds); (c) top changes only 0.628 (exact 0.38; 2,360).
    Own-state anchors on the filled orders: its own current top (persistence) 0.453, the price of its last removed own
    level within 2 s (refill / cooldown re-post) 0.297, K - L after its take 4 of 5. By branch (filled orders): own top
    at or within 1c of others' best (138) J 0.442 / own top 0.486; 2c+ behind (27) J 0.407 / own top 0.370. The
    signature of the mechanics proposal (>= 0.80 on unit a or b with public state plus own inventory) fails already
    in sample; the price account for the wall is: top changes 0.63, every level 0.38-0.40, fills 0.42-0.45.
17. **Source probes.** Liquipedia tournament pages answer HTTP 403 to a plain fetch (like rdy.gg and HLTV); not
    bypassed (the MediaWiki API needs a contact User-Agent, which the agent will not invent or fill with the user's
    address). SX Bet docs (docs.sx.bet): the V3 trade / fill / position endpoints (`GET /trades-v3`, `/fills-v3`,
    `/positions-v3`) "all require an API-key and you can only see your own activity"; the V2 `GET /trades` answers 404:
    SX trade history is not available to the agent; the chain route needs the exchange contract (not on the docs
    landing page).

18. **The 100-share buy-only whole-cent ladder with the 1.5-s timer is a common design, not this operator's mark
    (X79 follow-up, C1 / C8; `timer_owner.py`, `timer_owner.json`, `timer_owner_owners.json`; dev-start units of the
    10-31 12-18 block, data-api trades + publicnode calldata of 1,456 transactions in the four untraded markets with the
    most 100-share timer pairs: FOKUS-BakS map 2 and JJH-BMB map 1 (GRID-era style events), SKR2-FOR10, Gamers Club
    lowcor1-tdp).** Their filled 100-share whole-cent maker orders belong to other deposit wallets (sigType 3,
    buy-only): 0xca0b532d (31 orders, 2 markets), 0x2b55d2ee (29), 0xd3bd48ab (25), 0x68915897 (23, 3 markets; a fast
    late maker of iteration 3), 0xd2bb9459 (10), 0x5d40576b (4; also a fast late maker). Their owner() EOAs are all
    different from the wallet's 0x8af810f0 (0xdd952f37, 0x4e87b336, 0x6ba1d290, 0xc96948e1, 0x3afe7c14, 0xb5951d42).
    So buy-only two-token ladders of 100 shares at whole cents, deposit wallets and the 1.5-s re-post are shared by
    several makers in markets the wallet never trades; what sets the wallet apart is its event selection and its
    taker feed, not its maker client.
19. **No freeze-time clock in the reversal bursts (`reversal_gap.json`).** Gaps from a pack-only burst to the next
    informed burst on the other team: wallet-led p10 / p50 / p90 9.9 / 48 / 100 s (136), pack-only 8.4 / 40 / 100 s
    (312), with mass at 6-24 s in both (an interval that a round end would fill with the restart delay and freeze
    time); its presence rate by gap is flat (0.24-0.39 from 6 to 120 s). The pack bursts it reverses are therefore not
    clean round ends, and no buy-phase (loadout) timing shows; the event type stays unclocked.

X77 (series fair value), where it stands: the historical half is bounded by finding 12 (fresh prints < 2 s old give
0.36; 27% of filled orders sit 6c+ below the last print, a depth a fair value cannot predict), so it cannot lift h1 / h2
price toward 0.8; the live half (wide books) needs the pre-game match price r, which the BUILD-live recorder missed
(it started at 14:50, after most dev-unit games began): run it on 11-01 06-12.

20. **Selection survives stronger activity baselines (`selection_baseline_robust.json`; examiner-style logistic
    baselines fitted on BUILD, scored on VALIDATE, 256 / 128 events).** Stored v3 scores AUC 0.957; pre-game activity
    logistic (log prints, USD, wallets) 0.893 (gain +0.065); its degree-2 polynomial 0.899 (+0.059); plus the pre-game
    favourite price 0.898 (+0.060). The gain stays near 0.06 against these baselines (point estimates; the examiner's
    own baseline may differ, and the per-day gain on 10-21 was +0.034).

21. **The co-timed maker 0x51dbdd2b reacts to the wallet's events, not to the pack's (`cosub_wave_lock.py`,
    `cosub_wave_lock.json`; BUILD-live; its cancels by a loose fingerprint of sizes no other maker uses there, 704
    cancels).** It cancels on the consumed side at 30.8% of the wallet's takes (12 of 39; c - p p25 / p50 11 / 41 ms;
    before the first public cancel that is neither the wallet's nor its own in 58%), but at only 7.4% of the pack's
    takes without a wallet take (4 of 54, mostly seconds later). Its event set is the wallet's event class, not the
    pack's: with no funding link and different owners (finding 8), this supports one source shared by the wallet and
    0x51dbdd2b (or one operator with unlinked wallets), and a different source behind the pack's round-win events.
    Historical check (`cosub_hist.py`, `cosub_hist.json`; 16-22 Oct full matched-order record; 7,675 filled maker
    orders of 0x51dbdd2b): its filled maker signings, as a rate ratio to its in-play average in that market, after
    the wallet's 1,682 takes: bought token 0-100 ms 0.0x, 100-500 ms 17.8x, 1.00-1.15 s 34x; complement 0-100 ms
    11.2x, 1.00-1.15 s 22x; after the pack's 14,260 takes without a wallet take: bought 8.4x / 8.3x / 18.8x, complement
    0-100 ms 27.5x. So it also re-quotes within 100 ms after the pack's signings (filled orders, which the pack's own
    FAK selects, so the rates are a censored view). The live cancel test separates the two anchor types (ahead of
    the public wave at the wallet's events in 58%, rare cancels at the pack's); the historical re-quote rates do not.
    Finding 21 is therefore suggestive, not established (12 and 4 live events).
22. **Its pull at the pack's events follows the size of the public wave** (`wave_lock.json`, `wave_size_by_pull`):
    non-own cancels on the consumed side within 100 ms after the pack signs: 2.13 when it pulls vs 0.82 when it does
    not (AUC 0.70; within 300 ms 3.33 vs 2.49, AUC 0.65; 54 events). At its own takes the wave size does not
    predict its pull (AUC 0.29-0.49: it pulls at 97% regardless). A public trigger for the protective pull exists
    (a fast, large first wave), with weak power on one block.

## Runbook for the first VALIDATE-live block (11-01 06-12 UTC, re-registered split)
1. `code/iter3/dev_markets.py` and `code/iter3/dev_calldata3.py`: set the block to [11-01 06:00, 12:00) (dev-start units
   only; they read the own recorder's `sub` records and drop sealed-start units first); refresh `dev_markets.parquet`,
   `dev_wallet_trades.parquet`, `calldata_dev.parquet` into a new suffix so the BUILD-live files stay intact.
2. `code/iter4/pull_attrib.py` (level-events builder; OWN0 / END constants) for that block -> a new
   `level_events_<block>.parquet`.
3. Score without refitting: `final_rule.evaluate(start, end)` (exam constants) -> `live_price`; `code/iter6/wave_lock.py`
   (H62), `cooldown.py` (H69), `price_units.py`, `live_occupancy.py` (apply the BUILD-live fit, do not refit),
   `code/iter5/chat_leadlag.py` (X38, pre-registered decision rule), the round-market book check (X47b).

Reviewer leads of 2026-10-31, where they stand: (C4b) no Polymarket listing-level change at the 10-16 switch (fee,
delay, rebate and reward parameters identical 10-01..10-22, iteration 1); the switch is the wallet's own (a faster input
and a new client: immediate signing instead of pre-signed orders, iteration 4). (Round / map boundaries) its quotes do
not move only at boundaries: one-sided re-quote bursts every ~0.5 s (median), a 1.5-s re-post timer, and the
socket has no round data for its events (map scores only), so a round-score Markov quote is not its input. (Sports
socket map scores) recorded in the shared `sports` feed; for its non-GRID events only map scores, per-round scores
only in GRID events.

## Iteration 6 closing state
- Status: continue. Primary metric `presence_auc` 0.8721 (unchanged; activity baseline 0.899). Frozen rule v3
  re-run on VALIDATE (build constants) reproduces selection 0.954 / 0.892 (gain +0.062, p 0.002), recall 0.722, lift
  3.30, price 0.305, pnl -0.121 / -0.061; new outcome baseline 0.515 / 0.357 (all scored markets), 0.513 / 0.369
  (traded markets); the rule's partial correlation given log prints -0.053 (`final_rule_v3_validate_iter6.json`).
- `final_rule.py` additions: `pnl_baseline_prints_*`, `pnl_corr_partial_given_prints`, and `live_price` (frozen live
  join rule, LIVE_VIEW_MS 100, PAIR_CAP 0.99; BUILD-live 0.424 on 172 filled orders vs last trade 0.187).
- Recorders at the end: shared recorder OK; own `tommy_cs2_near`, `tommy_dota_live`, `tommy_cs2_rounds` v2 and
  `tommy_chat` v2 running (hard stop 11-03 00:00 UTC). No new recorder this iteration.
- Sealed-data handling: live data only through `iter_live` (development blocks), units filtered by game start; the
  exam-lot league mix used the listing projection only (in-memory projection, no shared cache, aggregates stored); no
  file in `.cache/live/sealed/` was opened or listed; every historical read ends before H.
