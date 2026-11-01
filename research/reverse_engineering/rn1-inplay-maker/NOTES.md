# RN1 in-play maker (0x2005d16a84ceefa912d4e380cd32e7ff827875ea): lab notebook

## Pre-registration (iteration 1, written before any VALIDATE number was computed)

Written in the interrupted cloud iteration (2026-10-30) and kept unchanged in the local iteration 1 (2026-11-01);
no VALIDATE number had been computed under it.

- Development data: timestamps < H = 1792713600 (2026-10-23). Holdout [H, ...) is never loaded.
- **BUILD** = [1790899200, 1792108800) (2026-10-02 .. 10-15, 14 days).
  **VALIDATE** = [1792108800, 1792713600) (2026-10-16 .. 10-22, 7 days). Candidate rules are chosen on VALIDATE only.
- **Primary metric: `presence_auc`** (higher is better, fixed across iterations): ROC AUC on VALIDATE of the rule's
  score for "RN1 has >= 1 maker fill in this (market, 60-s bin)", over the universe of cells
  (market, minute) such that (i) the market belongs to an event in a seeded random sample of the events RN1 traded
  in the period (all sibling markets of the sampled event are included, traded or not), (ii) the bin lies in
  [gameStart - 2 h, gameStart + 5 h], (iii) the public tape has >= 1 taker print in the market in that bin.
  Features: strictly point-in-time (data with ts < bin start, plus listing metadata). No own-state features in the
  primary score. (Caveat: the event universe is conditioned on RN1 having traded the event; it measures market
  choice inside events and timing, not event choice.)
- Secondary metrics (reported every iteration): selection AUC among public maker fill rows (is the maker RN1?);
  side accuracy (which outcome of a binary market RN1 buys in a bin, vs "buy the favourite"/"buy the underdog");
  price: share of RN1 fills whose price the rule predicts within 1 tick; per-market PnL correlation rule vs RN1.
- Live-only dimensions (books, sports websocket, from 2026-10-31): the brief's default split, BUILD = development
  6-h blocks on day d after T0 with floor(d/2) even (10-31, 11-01, 11-04, 11-05, ...), VALIDATE otherwise.
  Units (games) are assigned to the block in which they start (gameStartTime); records of games that started in a
  sealed block are dropped before anything is computed.

## Iteration 1 (local, 2026-11-01): data, competing explanations, first decoding

Clock: start 1793546415.

### Data gathered (all development, < H)

- data-api activity of RN1 for 10-02 .. 10-22 (21 days), one UTC day per call:
  `.cache/re/rn1-inplay-maker/activity/act_<day>.parquet`. 162,984 TRADE rows ($43.0M), 19,599 markets,
  5,682 events, 19,153 REDEEM rows; no MERGE, SPLIT or CONVERSION rows; **every TRADE row is a BUY** (no sells).
  Income rows in 21 days: MAKER_REBATE $93.3k, TAKER_REBATE $48.8k, REWARD $24.8k (= $167k, about 25% of the
  wallet's ~$0.9M/month PnL at the monthly rate).
- Family shares of USDC (slug prefix): atp 16.3%, wta 11.1%, nfl 7.7%, ucl 7.4%, cs2 7.0%, cfb 6.5%, unl 6.4%,
  epl 5.2%, lal 4.2%, sea 3.4%, uel 2.6%, other soccer leagues ~15%, mlb/nhl ~1.7%.
- Fill prices: median 0.46 (5%-95%: 0.03-0.93). Sizes: median 92 shares, 75% 555, 95% 2,891, 99% 5,151.
- Only 44.8% of its markets have buys on both outcomes.
- On-chain OrderFilled logs (V2 exchanges, topic2 = RN1), per day: `.cache/re/rn1-inplay-maker/chain/`.
- **B1 calldata**: decoder `code/fetch_calldata.py` for V2 `matchOrders` (selector 0x3c2b4399), verified on tx
  0x6520ccc7...: every order of the transaction is decoded (taker order + all maker orders: maker, signer,
  token, makerAmount, takerAmount, side, signatureType, ms signing timestamp, metadata, builder, fill and fee).
  1,000 random RN1 trade transactions per day, all 21 days (`.cache/re/rn1-inplay-maker/calldata/`). RN1 signs
  with signatureType 1 (POLY_PROXY: an EOA signs for the proxy).
- Gamma listing metadata of every market it traded: `markets_1790899200_1792713600.parquet`.

### Competing explanations (each names its dimensions; status in state.json `dimensions`)

1. **H1 Fast-feed protected pair maker.** Rests bids on both outcomes with a combined price below 1 and earns the
   pair spread; it withdraws or requotes on a game feed faster than the public one (official data such as
   Sportradar/Genius/IMG, or courtside), inside the sports taker delay. Dimensions: `event_feed_official`
   (missing/blocked), `polymarket_sports_ws` (have, live-only), `espn_pbp` (have). Tells apart: its order
   cancels/requotes (B1 signing gaps, B2 stop-filling, live books) lead the sports websocket and ESPN, with a
   localized peak, and its post-event requote prices already reflect the new state.
2. **H2 Public-book follower behind the speed bump.** No private feed: it watches the public book (and sibling
   markets) and pulls when other makers or the first takers move; the taker delay (Gamma `secondsDelay`) gives it
   time to cancel before delayed takers hit. Dimensions: `clob_book_levels` (have live; tape pre-T0),
   `sibling_markets` (have), `taker_delay` (have). Tells apart: its withdrawals lag the first public book change by
   < 1 s instead of leading it; in markets without a delay it is adversely selected like everyone else.
3. **H3 Sharp-line quoting.** Its quotes sit at a fair value taken from a sharp book or exchange (Pinnacle,
   Betfair in-play) minus a margin; pair cost < 1 is the margin. Dimensions: `sportsbook_odds` (blocked: keys),
   `betfair_exchange` (blocked). Tells apart: its quote midpoint at signing leads the Polymarket mid (predicts the
   next price move), and its bid skew (bid_yes vs 1 - bid_no) carries information beyond the book.
4. **H4 Inventory-driven pair completion.** The side and price of the next bid are set by its own inventory: it
   bids the outcome it lacks to complete pairs, at a price that keeps (avg cost held + bid) below 1 - margin.
   Dimension: `own_inventory` (have, from fills). Tells apart: the side of its next fill follows the inventory
   deficit; its price on the deficit side tracks 1 - avg cost of the held side - margin.
5. **H5 Rebate and reward farming.** Part of the edge is Polymarket's maker rebates, taker rebates and liquidity
   rewards; quotes are shaped by `rewardsMinSize`/`rewardsMaxSpread` and markets chosen by rebate pools.
   Dimensions: `rebates_rewards` (have: activity rows, Gamma). Tells apart: share of PnL from rebate rows; whether
   order sizes and prices cluster at the reward thresholds; market selection vs rebate pool.
6. **H6 Late-game favourite harvesting.** The residual (unpaired) inventory is dominated by high-price bids on the
   near-certain outcome late in games, which mostly settle at 1. Dimension: `time_to_end`, `score_state`
   (have/proxy). Tells apart: PnL by price bucket and minutes to the end.
7. **H7 Combos/RFQ hedging** (reviewer lead, catalog C6). Its single-market fills hedge or source the combo / RFQ
   flow it makes. Dimension: `rfq_combo_flow` (missing: Gamma `rfqEnabled` only). Tells apart: fills cluster
   across the legs of the same combo, rfqEnabled markets dominate, distinct settlement transactions.
8. **H8 Counterparty flow.** It profits from a few predictable takers; it quotes deep when they are active.
   Dimension: `counterparties` (have: calldata taker orders). Tells apart: concentration of its PnL by taker and
   whether its quoting starts with those takers' activity.

At least H1, H3 and H7 rest on missing or blocked dimensions.

### Log

#### Endpoints verified (2026-11-01)

- data-api `/activity` (one UTC day per call, 3-11 s/day), Gamma `/markets?condition_ids=` and `/events?slug=`
  (markets carry `events[0].gameId`, which matches the sports websocket `gameId`), data-api `/trades`
  (taker_only true/false), Polygon `eth_getLogs` and batched `eth_getTransactionByHash` (20 per JSON-RPC batch) on
  publicnode: all work. drpc is the fallback.
- **Bug in `tools/live.py` `iter_live`**: a corrupt gzip member raises `zlib.error` ("invalid block type"), which
  the reader does not catch (it catches EOFError/OSError only); the dev file `clob_wallets/20261031T12.jsonl.gz`
  hits it. Worked around by reading hour by hour and skipping the rest of a corrupt hour
  (`code/live_quotes.py`, `code/live_sports.py`). Not fixed in tools/ (not my folder).
- Live recorder status at start: running (pid 27184, hard stop 1793881098); `sports` feed connected.

#### B1 / B2: decoded orders (pre-H sample: 1,000 random RN1 trade tx per day, 21 days; `results/b1_orders_*.json`)

- RN1 signs every order with ONE EOA, `0x5d4fd194c4181ad61b1b5cb72dab8f9c4f9a2edc`, signatureType 1 (POLY_PROXY);
  builder and metadata are zero on every order. **Salt / signing-ms is uniform on (0, 1)** (quantiles 0.01/0.25/0.5/
  0.75/0.99 = 0.01/0.26/0.51/0.75/0.99): `salt = round(Math.random() * Date.now())`, i.e. the TypeScript
  clob-client order builder (C8).
- All orders are BUY. In the VALIDATE sample 6,658 maker / 538 taker order fills (92.5% maker).
- **Resting age of filled maker orders (signing -> fill block)**: median 12.8 s; 5% 2.8 s, 25% 5.7 s, 75% 31.7 s,
  95% 141 s, 99% 646 s; nothing below ~2 s. Other makers filled in the same transactions: median 18.6 s, 95%
  868 s. Its filled quotes are fresh: it re-signs quotes every few seconds to tens of seconds.
- Takers that fill it: their orders are a median 3.8 s old at the block (5% 2.3 s), consistent with the 1-s sports
  taker delay (`secondsDelay` = 1 on 98.7% of its markets) plus matching and settlement. 15.8% of its filled maker
  orders were signed after the taker order that filled them (7.0% within 1 s after): part of its fills are new
  quotes that meet takers already held in the delay.
- 86% of its maker fills are matched against a taker who BUYS the complement (a mint), 14% against a taker who
  sells the same token. Counterparties: 2,669 distinct takers in the VALIDATE sample, top taker 6.8%, top 10 18.6%.
- It is the first maker of the transaction in 69% of its maker fills (median 1 maker per transaction): it is
  usually alone at the best price.
- **Size**: original order size is in shares and independent of price (log-log slope 0.017, corr 0.02): median
  ~1,550 shares in every price bucket, modes near ~700, ~1,500 and ~3,000 shares (live block 10-31: median 2,999).
- Price grid: 83% of its prices on the 0.01 grid, the rest on 0.001 sub-ticks (the 0.001 tick at extreme prices).
- Signing ms within the second is uniform (no wall-clock-aligned loop). Orders signed in the same ms as another of
  its orders: 72 of 2,617 (live block, all filled orders).

#### Pair structure (activity, VALIDATE)

- When it is filled on both outcomes of a market within 2 s, the two prices sum to **0.99** (median 0.990, q25
  0.990, q75 0.990, n = 517); 2-10 s apart, median 0.990 (q10 0.970, q90 1.000). It quotes both outcomes as a
  **1-tick market**: bid p on one outcome and 0.99 - p on the other, i.e. a bid at p and an ask at p + 0.01 on one
  token.
- Live block (all filled orders): of 2,617 unique filled orders, 8 have a filled complement order signed within 50
  ms (sum 0.990), 67 within 1-10 s (median sum 0.990). Both sides are not signed in one batch.

#### Quote placement against the recorded book (live lab; post-T0 development blocks, development units only)

- `code/fetch_live_fills.py`: RN1 OrderFilled logs + calldata in [10-31 12:00, 18:00) and [11-01 06:00, 12:00);
  rows of games that started in a sealed block are dropped in memory before anything is written. Block 1: 4,136
  dev-unit fills, 2,617 unique filled orders in 836 markets; block 2: 793 fills, 528 orders in 110 markets.
- `code/live_quotes.py`: book of the market (first token; second token = 1 - price) at the order's signing time,
  aligned on the **server** timestamp `s` (the recorder's receive clock lags the server by ~0.7-0.84 s).
  604 orders with a fresh book (< 5 s old) in 125 markets:
  - **Posting latency** (signing -> the level at its price grows by >= half its size): median 272 ms (block 1),
    231 ms (block 2); 10% ~67 ms, 90% 0.4-1.2 s; found for 92-97% of orders (validates the alignment).
  - Offset from the best same-side quote at signing: join 0 ticks 46.7%, improve +1 tick 31.1%, -1 tick 13.9%,
    <= -2 ticks 6.4%, >= +2 ticks 1.2% (block 1).
  - By the spread at signing: 1-tick spread -> joins (63%), 20% one tick behind, 9% improves; 2-tick spread ->
    improves by one tick (68%), joins 20%; 3 ticks -> improves one tick (50%).
  - Rule "join a 1-tick spread, improve a wider one by one tick": exact 55.5%, within one tick 87.9%. Trivial
    anchor "touch (best same side)": exact 39.9%, within one tick 90.7%; "opposite best - 1 tick": exact 48.0%.
    So within one tick does not separate the rule from the touch; the exact match does (55.5% vs 39.9%).
  - After posting, its level is one tick from the opposite best in 52% of orders: it makes the inside market.

#### Own inventory (H4) and side

- P(next fill on the outcome it holds less of) = 0.424 (BUILD), 0.411 (VALIDATE); 0.36-0.38 at small imbalances,
  ~0.50 above 5,000 shares. Its fills run on the side it already holds more of: it does not complete pairs by
  skewing toward the deficit side (H4 rejected in this form). An own-inventory side baseline ("same side as held")
  scores ~0.58.
- Tape side rules on VALIDATE (60 events, 1,234 one-sided (market, minute) cells): buy the underdog 0.541, the
  favourite 0.459, against-recent-flow 0.482. Its side in a minute is the complement of the taker's direction,
  not a choice the public tape reveals.

#### Price on the tape (pre-H; no book)

- VALIDATE RN1 maker fills of the sampled events (n = 2,230): last other-trader print on the same outcome within one
  tick 72.1% (exact 27.3%); minus one tick when that print lifted the ask: within one tick 71.5% (exact 34.6%).

#### PnL decomposition (activity, settled with Gamma outcomePrices; trading only, rebates separate)

- BUILD 14 d: $27.1M bought, PnL +$465k (+1.71%): pair-locked +$372k, unpaired residual +$93k.
- VALIDATE 7 d: $15.7M bought, PnL +$58.5k (+0.37%): pair-locked +$184k, residual -$125k.
- Rebates and rewards over the 21 days: MAKER_REBATE $93.3k, TAKER_REBATE $48.8k, REWARD $24.8k.
- Return by fill price (BUILD): 0-0.1 +27.7%, 0.1-0.3 0.0%, 0.3-0.5 +3.0%, 0.5-0.7 +0.1%, 0.7-0.9 +2.6%,
  0.9-1 +0.5%. Best families BUILD: cfb, wta, epl, ucl, bun; VALIDATE: ucl, cfb, col1, tur, atp.

#### Sports websocket (X2 / A5a, live block 10-31 12-18, BUILD for live-only dimensions)

- Gamma `events[0].gameId` maps 2,781 of 2,824 of its filled orders to 145 games; 112 games appear in the sports
  feed with 842 score changes (atp 370, cfb 89, wta/challenger 117, soccer leagues ~180).
- Event study (decisions = its filled-order signing times, events = ws score changes at receive time + 0.713 s
  clock offset, units = games on separate time axes, swap null, 102 of 112 units in the null): max_lag 120 s:
  p_level 0.20, p_shape 0.03, p_link 0.20; max_lag 20 s: p_link 0.41. No timing link at this sample size.
  Raw counts in 5-s bins from -60 s: signings 18,12,13,11,20,22,12,15,28,17,25,15 | 13,12,9,9,13,5,16,11,6,14,9,15
  (fewer after the ws score change); its fills 15,20,13,18,13,11,21,15,15,23,31,27 | 36,27,20,21,21,20,27,14,...
  (fills peak from -10 s to +5 s around the ws timestamp).
- ws vs book (`code/live_ws_vs_book.py`): for 201 of 1,537 ws score changes there is a >= 3-tick midpoint move
  within +-60 s in the game's recorded markets; the nearest such move is a median 11.7 s BEFORE the ws message
  (book first in 63%); among moves within +-15 s (n = 75) the median is 0.0 s (IQR -9.1 .. +4.6 s); soccer
  (n = 54) median -1.7 s. Nearest-move matching mixes unrelated moves; inconclusive. Next: per-goal largest move.

#### E7 synchrony (B1 signing times, BUILD sample)

- Its filled-order signing times > 30 min after the game start, 9,717 orders in 1,976 games, market label = game:
  ratio 1.30 at 0.25 s (p 0.044), 1.01 at 1 s (p 0.46), 1.06 at 2 s (p 0.21). No cross-game synchrony at the
  pre-registered bar (p <= 0.01 and ratio >= 1.5): no shared second-scale driver across unrelated games in its
  filled orders.

#### Quick catalog checks (measurements)

- C1: its EOA signs for no other proxy in the 21,000 sampled transactions (only RN1's own transactions were
  sampled, so this is not a full sibling search).
- C7: 0 of 21,000 sampled transactions have RN1 as both taker and maker (no self-matching).
- C4: per-day calldata sample: median order size alternates between ~1.5k and ~2.9k shares (10-10, 10-13, 10-14,
  10-17, 10-21 at ~2.9k); maker share 84-96% (lower on 10-02..10-04). No formal change-point test yet.
- C5: fills peak 17-21 UTC (19 UTC 11.5%, 20 UTC 10.6%) and drop sharply at 21 UTC (1.9%), then 22-02 UTC 2-4%.
- C6 / X1 (Combos/RFQ): `rfqEnabled` is false on every market of the BUILD/VALIDATE cells (26,459 cells) and on 989
  of 989 live development-unit markets. Ruled out.
- B7: `rewardsMinSize` 50 and `rewardsMaxSpread` 4.5 c on 934 of 989 live markets; its ~1,500-share inside quotes
  always qualify; REWARD income $24.8k in 21 days (small).
- `secondsDelay` = 1 on every cell of the BUILD/VALIDATE universe.

#### Presence (primary metric), first models (60 + 60 pre-registered events)

- Cells: BUILD 11,824 (8.7% positive, 60 events, 659 markets); VALIDATE 14,635 (8.9%, 60 events, 725 markets).
- VALIDATE AUC: ACT (activity-only) 0.728; LIST (+ listing) 0.742; FULL (+ siblings, pair price) 0.744; gain FULL
  vs ACT +0.017 (95% game-bootstrap CI -0.003 .. +0.041, p 0.055). OOF BUILD AUC 0.756.
- Structure: pre-game cells are almost never filled (0-1.2%) vs 10-13.5% in play; within the markets it trades,
  it is filled in ~15-18% of in-play minutes with a taker print. RN1 markets are ~30% of the markets but 71-78% of
  the cells. An oracle "market is an RN1 market" scores 0.62-0.66 alone, 0.71-0.73 with in-play: most of the AUC
  is timing inside its markets, which the activity features already carry.

## Missing dimensions (E2, from out-of-fold BUILD residuals of the FULL presence model, GroupKFold by game)

Misses = positive cells in the lowest third of OOF scores (344); false alarms = negative cells in the top OOF
decile (1,080).

- **Which component fails.** Presence (selection + timing) fails, not the quote shape: price and pair structure are
  regular (pair sum 0.990, inside placement). The side is the complement of the taker's direction (not a choice we
  can predict from the tape: 0.54). Size tiers (1.5k vs 2.9k) are unexplained (risk or confidence input).
- **Misses** over-represent CS2 (20% of misses vs 10% of positives), child_moneyline markets (12% vs 6%), first-half
  totals (9% vs 4.5%), the first 15 minutes of play and pre-game (19% vs 13%), and prices above 0.7 (27% vs 21%).
  It is filled where and when the tape says the market is quiet: a market-level input says "this game is live and
  quotable" before the tape does (candidate: the game-state feed going live, e.g. the sports websocket `live` flag
  or the official data feed; esports data for CS2).
- **False alarms** over-represent soccer (77% vs 70% of positives) and totals (43% vs 40%) in mid-game (45-150 min):
  busy soccer minutes where it is absent. Candidate: withdrawals triggered by match events (goals, cards, VAR,
  dangerous attacks) from a game feed, i.e. an event-state trigger (H1), or a risk limit per game (own state).
- **When.** Its fills concentrate 12-21 UTC; residuals follow the same hours (no hour-specific gap identified).
- **Synchrony (E7).** Misses of the sampled BUILD events are too sparse for cross-game synchrony (332 fills, 0
  near pairs). On the 9,717 B1 signing times across 1,976 games: ratio 1.30 at 0.25 s (p 0.044), 1.01 at 1 s: no
  shared second-scale driver across unrelated games.
- **Lead.** Sports websocket: no localized timing link of its filled-order signing times (p_link 0.20); its fills
  peak from -10 s to +5 s around ws score changes, and big book moves come a median ~12 s before the ws message,
  so the ws is slower than the book (and than whatever RN1 uses). The real trigger is upstream of the public ws.
- **Who else.** Not yet measured (co-signers of withdrawals).
- **Unexplained share.** Presence: AUC 0.744 vs 0.728 activity-only; most of the timing inside its markets is not
  explained beyond activity. Side: 46% of one-sided minutes. Price on the tape: 28% of fills outside one tick (on
  live books 12%). Size tier: unexplained.

## Pre-registration: first E3 screen (event-state family), to run on live BUILD blocks, confirm on live VALIDATE

- Dimension family: event state. Indicators: (1) sports websocket score change per game; (2) the same gated by sport
  (soccer goal = goals field change; tennis game/set change; CS2 round/map change; US football score); (3) period
  change; (4) first `live = true` since listing (`first_occurrence`); (5) compound: score change and no >= 3-tick
  book move within the previous 10 s (event before the book) and its complement (book first).
- Decision series: (a) B1 signing times of its filled orders; (b) withdrawals inferred from the recorded book (a
  level of its order size at its price disappearing without a trade, B2), as a separate series; (c) re-sides.
- Lags: max_lag_s 20 (core +-10 s), 120 (core +-60 s), 1200 (core +-600 s); bins 1 s; swap null with league-class
  strata, units = games on separate time axes; 1,000 draws.
- Family: every indicator x lag range x decision series, plus signed variants for side; BH q <= 0.10 on BUILD
  (live days 10-31, 11-01, 11-04, 11-05); confirmation on live VALIDATE days (11-02, 11-03, ...) one-sided alpha
  0.01 with Holm; incremental_auc over the presence ACT baseline with game groups.
- ESPN (pre-H, BUILD 10-02..15): scoring plays at wall clock + 5 s, same lags, same nulls, against B1 signing times.

#### E3 screen, part (a), run on the live BUILD block 10-31 12-18 (`results/e3_screen_live_1793448000.json`)

- 112 games, 2,347 decisions (its filled-order signing times on per-game time axes), swap null with league-class
  strata (94-104 of 112 units in the null), 500 draws, 15 rows (5 indicators with >= 5 events x 3 lag ranges;
  `first_live` had too few events inside the block), one BH family.
- **One BUILD survivor: `score_soccer@1200`**: shape peak at **+57.5 s** after the ws soccer score change, width
  5 s, lift 2.17, p_level 0.004, p_shape 0.004, p_link 0.004, q 0.060; at max_lag 120 the same peak at +55.5 s
  (p_link 0.022, q 0.165). Its filled orders are signed about a minute after the ws reports a soccer score change:
  it re-enters about a minute after goals (about 35-40 s after the first book jump, see below).
- `score_any@20`, `score_soccer@20`, `score_tennis@20`: level excess (p_level 0.010-0.026) but the level peak sits
  in the flank (rerun wider; not counted). Tennis, US football, period changes: nothing (p_link >= 0.18).
- To confirm on the live VALIDATE days (11-02, 11-03) once they are recorded: one-sided alpha 0.01, Holm.

#### First public price jump vs the sports websocket, and RN1 around it (`results/live_jump_align_1793448000.json`)

- Aligning each ws score change on the first >= 3-tick move of the book midpoint (within 3 s) in the game's recorded
  markets inside [ws - 30 s, ws + 10 s]: the **book moves a median 20.8 s before the ws soccer score change**
  (29 events) and 18.1 s before tennis ones (54 events). The public sports websocket is ~20 s slower than the
  market: it cannot be the input that protects RN1 (X2 answered for the ws; ESPN comparison still open).
- RN1's fills around the first jump, soccer, per 10 s from -60 s: 6, 5, 2, 7, 5, 10 | 3, 15, 10, 13, 9, 9, 12 ...
  (a dip in the 10 s after the jump, back from +10 s); tennis: 8, 1, 1, 1, 1, 0 | 9, 5, 8, 1, ... Only 2 (soccer)
  and 6 (tennis) of its orders that rested through the jump were filled within 10 s after it. Small counts.

#### Ladder and requotes (live blocks, all filled orders)

- 3,145 filled orders on 1,261 tokens: 134 pairs of filled orders on the same token at different prices had
  overlapping lifetimes (a second level resting), 53 at the same price: mostly one level, sometimes two.
- Gap between consecutive filled orders on a token: median 279 s (10% 18.6 s); the price changes between them in
  87% of cases (63% by more than one tick).

#### Side, market level

- One-sided markets (only one outcome bought) are 54-57% of its markets but only 10% of its USDC, and mostly markets
  with a single fill (median 1 fill vs 7-8 in two-sided markets); among markets with >= 3 fills 23-26% are
  one-sided; in one-sided markets it bought the outcome priced < 0.5 at its first fill in 56-58%.

#### Presence v2 (VALIDATE 120 events = pre-registered sample + a disjoint seeded sample; BUILD 60 events)

- Cells: VALIDATE 26,181 (8.4% positive, 1,404 markets); BUILD 11,824 (the extra BUILD sample was still
  downloading and is left for iteration 2).
- VALIDATE AUC: ACT 0.7268, ACT2 (+ tape spread proxies) 0.7290, LIST 0.7479, **FULL 0.7521**, FULL2 (FULL +
  spread proxies) 0.7490. FULL vs ACT +0.025 (95% game-bootstrap CI +0.007 .. +0.043, p 0.003); FULL2 vs ACT2
  +0.020 (CI +0.003 .. +0.039). FULL vs LIST +0.004 (CI -0.003 .. +0.011). The gain is listing metadata (market
  type, family), not timing.
- Chosen on VALIDATE: FULL (frozen as `models/presence_FULL.txt`).
