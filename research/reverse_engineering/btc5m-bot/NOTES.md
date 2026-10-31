# btc5m-bot: lab notebook

Strategy: BTC 5-minute Up/Down bot run across three wallets
(GF = GoodFallen 0x0ca4e9d2..., XM = x-MoneyForWhiskas 0x3048d653...,
DS = dangerously-skip-permissions 0xc53375ff...).

## Pre-registration (iteration 1, fixed for all iterations)

- Holdout H = 1792713600 (2026-10-23 00:00 UTC). Nothing at or after H is
  loaded: every fetch is bounded below H (chain fetch asserts max ts < H;
  block 96005486 is the first block with ts >= H and is never requested).
- VALIDATE = [1792108800, 1792713600) = 2026-10-16 00:00 .. 2026-10-23 00:00 UTC
  (the last 7 days before H). Rules are chosen on VALIDATE only.
- BUILD = everything before 1792108800 that I fetch. Iteration 1: 2026-10-02 ..
  2026-10-16 (14 days). May be extended further back in later iterations
  (never forward).
- PRIMARY METRIC (higher is better): `presence_auc` = pooled ROC AUC, over all
  VALIDATE cells (window w, outcome o in {Up, Down}, second s in [0, 300) of the
  window), of a frozen point-in-time score for the label "at least one of the
  three wallets has a BUY fill (taker or maker role, on-chain OrderFilled) on
  outcome o of window w with block timestamp in second s". The score may use
  only public information available before second s (spot klines ending
  <= s-1 i.e. Binance second s-2 and earlier, other traders' tape prints with
  block ts <= s-1, metadata known at listing) and NO own-state features.
  Secondary metrics (always reported): same AUC with own-state features
  (inventory), taker-only and maker-only presence AUC, per-wallet AUC, side
  accuracy given action vs market-only baseline, price-within-one-tick share,
  selection AUC (match_test where tapes exist), per-window PnL correlation.

## Data gathered (iteration 1)

- On-chain V2 OrderFilled, topic2 (order owner) in cluster, blocks 94796054..96005485
  (2026-10-02 .. H): `.cache/re/btc5m-bot/chain/own/*.parquet`. Logs carry
  `blockTimestamp`, so no block lookups are needed. Exchange 0xe2222... had
  no cluster logs in a test range; both exchanges are queried.
- ~57.6k Polygon blocks per day (1.5 s blocks), block at H = 96005486.

## Hypotheses

(see state.json for the ledger; narrative below)

## Log

### Iteration 1 (2026-10-31 07:23 UTC start)

Data added:
- On-chain own-order fills (topic2 = cluster) for 2026-10-02..H: 719,604 OrderFilled logs, all BUY,
  all on exchange 0xe1111800..., all mapping to BTC 5m Up/Down tokens (fills.parquet).
- On-chain "hit" logs (topic3 = cluster: resting orders of others that cluster taker orders hit) for
  VALIDATE: ~310k logs.
- Gamma metadata for all 6,048 BTC 5m windows 2026-10-02..H (outcomePrices used for settlement only).
- Binance 1-s klines 2026-10-01..H-1 (1.9M seconds).
- data-api taker tapes for VALIDATE windows (all 2,016) and BUILD windows 2026-10-09..16 (in progress),
  saved per window in .cache/re/btc5m-bot/tapes/.

Facts measured (BUILD+VALIDATE unless noted):
1. ORDER STRUCTURE (new, from orderHash grouping). Every order is a BUY limit order of a fixed share size:
   60 shares until 2026-10-12, then 30 (50 on 10-17/18 for GF/XM). Order kinds on VALIDATE: pure taker
   (fully filled on arrival) 73%, take-then-rest (MT) 13%, pure resting (M) 14% of orders.
   For MT orders the resting limit equals the taker fill price in 93% of cases: the bot sends a limit
   BUY AT THE CURRENT BEST ASK (it never sweeps deeper), and any unfilled remainder rests at that price.
   38% of maker fill events (30% of maker shares) come from such remainders; they fill within 0-2 s
   (median 0 s, p90 2 s). Pure resting orders: 1 fill median, first-to-last fill span 0 s median.
2. Fee in the V2 event = 0.07 p (1-p) shares exactly for taker fills; makers pay 0.
3. TIMING: fills only at rel 2..291 s of the window (none before the open, ~none after 270 s);
   roughly uniform 0-240 s, tapering 240-270 s. Fill prices 0.12-0.88 (1st-99th pct); avoids extremes.
4. LEAD-LAG (VALIDATE, per second): corr(net Up-minus-Down cluster taker fills at block-second s,
   Binance 1-s return during second s+k) peaks at k=-3 (0.100) and k=-2 (0.085), -1: 0.045,
   0: 0.031, +1: 0.024, +2: 0.019 (small positive tail into the future). Maker fills: peak k=-3 (0.053).
   The bot reacts to Binance moves ~1-3 s before the block timestamp; no evidence of acting BEFORE
   Binance (the k>0 tail is small and consistent with 1-s momentum / block-time jitter).
   On-chain block timestamps can be out of order by up to 2 s (some resting remainders appear 1-2 s
   BEFORE the taker part of the same order).
5. STRIKE: limit prices of MT orders correlate 0.91 with a Binance fair value using the 60-s TWAP
   strike (mean over [start-60, start)) but only 0.69 with the open-price strike: the bot (and market)
   use the TWAP strike. Residual vs my FV is wide (MAD 0.046): the bot's price is not my FV.
   Pure taker fill price - FV(lag 2) median -0.002, IQR [-0.05, +0.05]: it buys at the ask when the
   ask is anywhere near FV, so the trigger is not an FV-vs-ask level threshold.
6. WALLETS: the three wallets trade the same windows (VALIDATE: all three in 1,725 of 1,904 traded
   windows). 82% of GF orders have a DS order on the same token within +-2 s; 72% of XM orders have a
   GF order within 2 s. They are parallel instances firing on the same events. Activity shifted:
   XM was the most active until 10-13, then DS. Shared txs only 0.7%, cluster-vs-cluster fills 0.2%.
   Weekend days have ~half the orders (fewer spot moves).
7. COUNTERPARTIES (VALIDATE hit logs): 92% of the makers it hits are BUY orders on the complementary
   token (mint matches), 8% sells. 2,523 distinct makers; top-10 = 25% of shares (not concentrated).

Presence model, spot-only PIT features (BUILD 14 days, VALIDATE 7 days, no own-state):
- any fill 0.805, taker 0.815, maker 0.779 (results_spot_model.json). Top gain: z / fv (price
  level), largest favourable 1-s Binance move in the last 3 s (mxf3), rel, sigma.
8. LOST-RACE TEST (VALIDATE, 300 random windows): for the bot's PURE RESTING orders, another trader
   took liquidity at exactly the bot's limit price on that outcome within the 5 s before the bot's
   first fill in 68.6% of orders (placebo 60 s earlier: 7.4%); for take-then-rest orders 76.5%; for
   pure taker orders 83.1% (placebo 8%). So nearly all orders are the same "buy at the ask" race
   orders fired on the same event as competing latency takers; most maker fills are the leftover of
   a lost or partly lost race (the competitor took the ask first, the bot's order rested at the old
   ask and was filled shortly after). This unifies the taker and maker sides: one trigger, one order
   type; whether it fills as taker or maker depends on who wins the race.

Presence model, spot + other traders' tape PIT features (H8; BUILD = 1,210 windows with tapes,
2026-10-11..16; VALIDATE = all 2,016 windows; cluster prints and prints in txs where a cluster
order was the maker are removed from the tape; no own-state):
- PRIMARY presence_auc = 0.892 (any fill); taker 0.893; maker 0.867; per wallet GF 0.888,
  XM 0.902, DS 0.880 (results_tape_model.json). Same windows, 14-day spot-only model: 0.805.
- Top gain: m_last (last traded price of the outcome, i.e. price level), vwap10, n1/n2 (other
  traders' prints in the previous 1-2 s), age_last, bid_o, rel, mxf3, r2, sigma.
- Ablation (results_ablation.json): without the 1-2 s activity and age features 0.831, i.e. ~0.06
  of AUC is race co-occurrence (competing takers print in the second before the cluster's fill).
  Market-only (tape features + rel/tau, NO Binance): 0.878. So most of the presence AUC is the
  Polymarket tape itself (price level + other takers' activity); Binance adds ~0.014 on top. Caveat
  for the examiner: the presence target is met largely through co-occurrence with other racers,
  not through a decoded private decision rule; the side and price metrics are the real test.
- At P_THRESH 0.30 (fixed, not tuned): recall 55.8% at lift 3.81 (flag share 14.6%, p~0).
- WITH own state (cluster inventory in the window up to s-1: shares of o and of the other outcome,
  net, average costs, pair cost if it buys now; no own fill counts or times): 0.906
  (results_own_state.json); inventory adds ~0.014 (avg_o, inv_o, inv_other in the top 12).
- Side (seconds where the cluster bought exactly one outcome, n=90,170): 66.3% vs favourite
  baseline 45.9% (it buys the underdog slightly more often) and tape-flow baseline 52.5%
  (McNemar p~0). 18% of active seconds have buys on both outcomes.
- Price: taker fills within one tick of the last implied ask (from others' prints <= s-1): 49.2%
  (exact 25.7%); maker fills 50.0%. The book estimate from prints is too coarse.
- Selection (all 2.74M in-window taker prints; cluster = 5.4%): pooled AUC 0.692, within-window
  0.679, recall 62.9% at lift 1.64. Cell-level scores cannot separate the cluster from co-racers
  in the same second; a print-level model (size: the fixed 30/50/60-share orders, price vs touch)
  is the next step.
- Outcome (crude proxy: rule buys 30 shares at the last implied ask when flagged): per-window PnL
  corr with the cluster 0.305 (Spearman 0.256); rule return -1.9%; cluster return before
  rebates +0.17% (taker -0.25%, maker +1.7%) on VALIDATE.
- End-to-end check: final_rule.evaluate(1792706400, 1792713600) (last 2 VALIDATE hours, fetched
  from scratch) gives presence AUC 0.873, side 64.8%, consistent.

Status after iteration 1: presence target met on VALIDATE (0.892 >= 0.85) but side accuracy
(66% < 80%) and PnL correlation (0.31 < 0.5) are not; target not reached.

Polyrea bugs: none found this iteration. (Gotcha, not a bug: `pkill -f <pattern>` inside a Bash
call kills the calling shell when the pattern appears in its own command line.)

## Next (iteration 2)

1. SIDE: model the side decision directly (pairwise per second): signed Binance move since the
   last print, the outcome's own price vs the other's (underdog preference), which outcome's ask
   was just taken by others (race direction: flow1/flow2 per outcome), own inventory (report with
   and without own state).
2. PRICE/BOOK: rebuild the touch better: use full tapes (maker rows) and the on-chain "hit" logs
   (exact maker prices hit) to estimate the best ask per second; predict the fill price as the ask
   at the race moment; check the 0.01 grid.
3. SELECTION: print-level model inside each second (size == bot's current fixed size, price ==
   touch, outcome) to separate the cluster from co-racers; use polyrea match_test (rotation null).
4. INFORMATION SOURCE: Binance aggTrades (ms), Binance USD-M futures aggTrades, Coinbase; lead-lag
   of cluster orders (taker part timestamps) vs each feed; test whether a faster feed explains the
   race wins (taker) vs losses (resting).
5. MORE DATA: tapes for all BUILD days (10-02..10-11 still missing), history before 10-02 (wallets
   active since ~mid-July; V1 exchange before V2), and a matched set of non-traded windows
   (VALIDATE: 112 windows without cluster fills: what is different?).
6. PnL: strict-fill backtest of the race rule (order at the ask after a Binance move, 2 s latency,
   match_slack 2), compare per-window PnL with the cluster.

Side diagnostics (VALIDATE one-sided seconds, n=90,170):
- side = sign of the Binance 2-s move ending at s-2: 67.7% on the 61% of seconds with a nonzero
  move (1 s: 63.9%, 3 s: 66.4%, 5 s: 62.1%, 10 s: 57.1%); underdog rule 54.1%; model 66.3%.
- On clear moves (|3-s move| > 2 bp, 4.7% of one-sided seconds) the sign rule is 83.5% accurate.
  Most one-sided buys happen without a visible Binance move: the side driver there is unknown
  (candidates: a faster/different feed such as Binance futures or Coinbase, or Polymarket-internal
  events such as a fresh ask below the bot's value after other traders' prints). This is the main
  open question for iteration 2.

Intermediates kept in .cache/re/btc5m-bot/: chain/own (3 weeks), chain/hit (VALIDATE), fills.parquet,
windows.parquet, gamma_meta.parquet, binance_1s.parquet, tapes/ (VALIDATE all, BUILD partial),
val_pred_tape.parquet (VALIDATE predictions), spot_model_y.txt; eval/ (evaluate() cache).
Background at the end of iteration 1: the BUILD tape fetcher (first run died silently at 1,210
windows, probably killed under memory pressure) was restarted for 2026-10-02..16
(`fetch_tapes.py 1790899200 1792108800 desc`, log fetch_tapes_build2.log); it skips existing files
and only requests pre-H data. Iteration 2 should check it finished and retrain on all BUILD tapes.

### Iteration 2 (2026-10-31 08:40 UTC start, local Windows laptop)

Setup: the cloud intermediates and the iteration-1 model files (`model_spot_tape_*.txt`) were gone, so the frozen
rule could not run. All code paths were made repo-relative (`_ROOT`), everything below was re-fetched (all < H),
and the presence models were retrained (`code/model_it2_*.txt`). Split unchanged: BUILD = 2026-10-09..16 (7 days,
2,016 windows), VALIDATE = 2026-10-16..23 (2,016 windows). Bug fixed in my own code: `fills.is_up` was object dtype
after the token merge, so `~is_up` silently gave wrong inventories; `build_fills.py` now drops unmapped tokens and
casts to bool (iteration-1 own-state numbers may have been affected; the AUC models used `is_up` only through
`np.where`, which was correct).

Data (iteration 2):
- Chain: V2 OrderFilled topic2 = cluster, blocks 95,190,000..96,005,485 (both exchanges in one `address` list per
  call): 483,048 logs, 477,121 mapped to the 4,032 BTC 5m windows of 10-09..H (`fetch_chain2.py`, ~7 min).
- Gamma metadata 4,032 windows; Binance BTCUSDT 1-s klines 10-08..H-1.
- data-api taker tapes for ALL 4,032 windows, range [start-600, end+5] (`fetch_tapes2.py`, seeded random order).
- NEW: Binance SPOT BTCUSDT aggTrades (REST, ms, aggressor flag) for 32 random whole hours (16 BUILD, 16 VALIDATE),
  `fetch_aggtrades.py`, `.cache/re/btc5m-bot/aggtrades/`.
- NEW: Binance USD-M FUTURES BTCUSDT aggTrades daily archive 2026-10-15 (BUILD; 1.82M trades, checksum-verified,
  reduced to parquet, zip deleted), `fetch_futures.py`. Futures REST aggTrades only serve the last 2 days.

Findings (VALIDATE unless noted):
1. Order kinds: pure taker 71.8%, pure resting 16.1%, take-then-rest 12.1% (175,831 orders).
2. Order-level lead-lag (`results_order_leadlag_iter2.json`): agreement of the side with the sign of the Binance
   return during second s+k (s = block second of the order's first fill), taker-first orders: k=-6 48.8%, -5 49.8%,
   -4 53.1%, -3 62.9%, -2 62.4%, -1 57.8%, 0 55.9%, +1 54.5%, +2 54.0%, +3 52.8%.
3. QUIET vs MOVING (new decomposition): 67% of taker orders come when the visible Binance move (klines s-4..s-2) is
   < 0.5 bp. For these quiet orders the side is ~unrelated to every PIT signal I have: my FV gap (fv_o > price
   48.8%), others' last PIT print (51.4%), net others' prints in (s-3, s-1] (48.5%), own inventory (buys the
   less-held side 54.2%), Binance klines at any lag (<= 57%). Same-second co-racers (non-PIT) agree 63%.
4. EDGE DECOMPOSITION (`results_edge_decomposition_iter2.json`, per share): taker-moving gross +3.12 c, fee 1.50 c,
   net +1.63 c (return +3.3%); taker-quiet gross +0.63 c, fee 1.49 c, net -0.86 c before rebates (-1.8%), -0.12 c
   with a 50% fee rebate; maker-moving +2.38 c (+4.6%); maker-quiet +0.23 c (+0.5%). VALIDATE totals: trading PnL
   before rebates +$4.4k on $2.54M bought; 50% of taker fees would be ~$30.8k. So in this week ~85-90% of the
   profit is the rebate, and the quiet taker volume is rebate-driven volume with a weak side signal.
5. ANTICIPATION: when Binance spot was flat over klines s-4..s (including the two seconds my PIT rule cannot see),
   the bot's side still agrees with the FUTURE Binance move over s+1..s+3 in 53.7% (10 s: 54.2%; exactly zero past
   move: 53.1% / 53.4%; placebo 50.0%). Binance 1-s autocorrelation is 0.136 (lag 1), which cannot create this on a
   flat past. The bot has a weak signal that leads Binance spot by seconds. Replicated on BUILD (150,541 taker
   orders): flat past 53.9% (3 s) / 54.4% (10 s), exactly flat 53.3%; maker-first orders 53.0% / 53.6%.
6. SUB-SECOND SPOT (aggTrades, 21,954 taker orders in the 32 sampled hours): move over [s-2, s-1) agrees 63.6%,
   [s-3, s-2) 63.2%, but [s-1, s) (non-PIT) only 56.8% (quiet 51.6%): the bot's information horizon ends about one
   second before the block timestamp, so the brief's 1-s availability lag is NOT what limits the side metric.
   Aggressor-signed volume (OFI) is weaker than price moves (57-59%). Verdict: no new information at ms resolution.
7. FUTURES (2026-10-15, BUILD): futures move in [s-3, s-2) agrees 64.8% (quiet-spot subset 59.6% vs ~57% for spot);
   futures lead spot (corr of futures second t with spot second t+1 = 0.168); 44.5% of spot seconds vs 36.5% of
   futures seconds have no price change. Futures add a few points in quiet-spot periods, not the missing signal.
8. SIDE MODELS (`results_side_iter2.json`, BUILD->VALIDATE, 40% of windows at the time): any fill 66.8%, taker
   67.0%, maker 67.2%; + own state 67.3%; market-only (tape, no Binance) 63.1%; own-state only 55.2%. Accuracy by
   |visible 3-s move|: 0 bp (60% of one-sided seconds!) 59.6%, 0.01-0.5 bp 72.6%, 0.5-1 77.0%, 1-2 81.4%, 2-5 84.0%.
   Ceiling check with the non-PIT klines s-1 and s added: 68.0% (vs 67.0%).
9. Inventory balancing (H12) rejected; strict Up/Down pairing rejected (30% of orders have an opposite-outcome
   cluster order in the same second vs ~16% for uniform timing: bursts on both sides, not pairs).
10. Wallets: DS 58%, GF 34%, XM 8% of VALIDATE USD, stable day to day; returns before rebates +0.09% / +0.17% /
    +0.74%: one strategy split across accounts. Moving-regime share is highest 12-16 UTC (41% vs 22-30%).
11. PRESENCE retrained (`results_presence_iter2.json`, all 2,016 VALIDATE windows, 1.21M cells, BUILD 10-09..16,
    negatives 30% with weights, 200 rounds): PRIMARY spot+tape no own state **0.8957** (taker 0.8966, maker 0.8753;
    GF 0.892, XM 0.909, DS 0.884; at p >= 0.30 recall 56.4% lift 3.89). Co-occurrence baseline (market only) 0.8889
    (gain +0.007): the presence target is met almost entirely by market activity, as in iteration 1. Spot only 0.799;
    with own state 0.909. End-to-end `final_rule.evaluate(1792706400, 1792713600)` (fetched from scratch): 0.874,
    baseline 0.869, side 66.2%, taker price within one tick 53.2%, runs in ~20 s for 2 hours.
12. SIDE (full VALIDATE, n = 90,170 one-sided seconds): spot+tape 67.1% (taker 67.1%, maker 68.2%), own state 67.5%,
    market-only model 63.9% (McNemar p ~ 1e-99), favourite 45.9%. 60% of one-sided seconds have a visible 3-s
    Binance move of exactly 0; accuracy there is 60.1%; 0.5-1 bp 77.2%, 1-2 bp 80.7%, 2-5 bp 83.5%.
13. OUTCOME (`results_outcome_iter2.json`): soft proxy (p x 30 shares at the last implied ask in every cell)
    per-window PnL correlation 0.399 (Spearman 0.363), hard proxy 0.316; net-position correlation 0.415; proxy
    returns -2.8% (soft) / -1.8% (hard); cluster +0.17% before rebates.
14. SELECTION at print level (new family: sizing rule, `results_selection_print_iter2.json`): among all 2.74M
    in-window taker prints, score = 1[size in {30, 50, 60}] + cell p: pooled AUC 0.837, within-window 0.825 (cell
    score alone 0.691 / 0.661). 49.8% of cluster taker prints have one of these sizes vs 2.3% of others' prints.
    Pre-registered flag (size rule and p >= 0.30): recall 31.3% at lift 12.7; size rule alone: recall 49.8% at lift
    10.2. Selection AUC >= 0.80 is met; recall >= 50% at the pre-registered flag is not. Co-occurrence baseline
    (size rule + market-only cell score): 0.827, so Binance adds +0.010; the jump comes from the decoded size rule.

15. FUTURES SIDE MODEL (late in iteration 2, `results_futures_side_iter2.json`, `futures_side.py`): futures
    aggTrades archives for 10-12..10-15 (BUILD) and all 7 VALIDATE days; PIT futures features (trades with
    T < (s-1)*1000 ms: moves over 0.25-10 s, signed volume, trade count, age, futures-minus-spot 3-s move). Side,
    BUILD 4 days -> VALIDATE 7 days: any fill 66.4% -> **69.8%** (seconds with zero spot 3-s move 59.2% -> 64.1%);
    taker 66.7% -> **70.7%** (59.0% -> 65.1%); futures-only model (no spot, no tape) 66.7% / 68.4%, better than
    spot + tape. The bot watches Binance futures (or a feed that moves with it); BTCUSDT spot is a sparse, lagging
    proxy (44.5% of its seconds have no price change). Not yet in the frozen rule (needs futures in evaluate() and a
    retrain); this is the best lead for the side metric.

Status after iteration 2: presence (0.896) and selection AUC (0.837) pass their thresholds, but side accuracy
(67.1% < 80%) and per-window PnL correlation (0.40 < 0.5) do not; the side gap is the quiet regime (2/3 of orders),
whose driver is not in any public historical feed tested. Target not reached. Status: continue.

Partial information-wall evidence (not a full wall): for quiet-regime orders the side agrees <= 56-60% with every
public signal tested at any lag (Binance spot 1 s and 1 ms, Binance futures, other traders' prints, FV gap,
inventory), yet predicts later Binance moves (53-54%, placebo 50%). Untested public sources: Coinbase trades,
Chainlink Data Streams (resolution source; only live via Polymarket RTDS), the Polymarket order book (no public
history for the development period; a live recording now would be holdout-period data, so for development it is a
wall).

Polyrea bugs: none found. Gotchas: Binance futures REST aggTrades only serve the last 2 days (use the daily
archive, ~22 MB/day); data-api tape fetchers can die with MemoryError under machine-wide memory pressure (restart
them; they skip finished windows).

## Next (iteration 3)

1. FUTURES into the frozen rule: fetch the archive for every BUILD day (10-09..15; 10-12..15 and VALIDATE are in
   .cache/re/btc5m-bot/fut/), add the PIT futures features of `futures_side.py` to the presence and side models, let
   evaluate() download the futures archive for its period, retrain, re-validate (side 69.8-70.7% already on
   VALIDATE). Then look for the remaining quiet-regime signal (futures book? Coinbase? Polymarket book).
2. COINBASE BTC-USD trades (REST paging by trade_id from a pre-H anchor; never probe ids after H) for a few BUILD and
   VALIDATE hours: does the quiet-regime side follow Coinbase (a Chainlink input) when Binance is flat?
3. ON-CHAIN BOOK of others: fetch OrderFilled for ALL makers in the cluster's windows (topic0 only, per window block
   range) and reconstruct other makers' resting orders (orderHash, price, fill times). Test whether quiet-regime
   buys hit freshly placed or repriced maker orders (an order-book event trigger), which the data-api tape cannot show.
4. SELECTION: a print-level LightGBM on BUILD prints (size, price vs last ask, outcome, cell features) with out-of-fold
   cell scores, to raise recall at lift >= 3 above 50%; check the size set per day (order size changes).
5. PnL: strict-fill backtest of the rule (latency 2 s, match_slack 2) and a side-weighted soft proxy.
Intermediates kept in .cache/re/btc5m-bot/ (1.1 GB): chain/own (10-09..H), fills.parquet, orders.parquet (VALIDATE),
windows/gamma_meta, binance_1s, tapes/ (all 4,032 windows), cells/ (14 days), aggtrades/ (32 hours), fut/ (10-15),
val_pred_presence.parquet, val_side_pred.parquet, eval/ (evaluate cache).

### Iteration 3 (2026-10-31 ~09:26 UTC start, local Windows laptop, ~50 min)

Split and primary metric unchanged (BUILD = 2026-10-09..16, VALIDATE = 2026-10-16..23, nothing at or after H).

Data added (all daily trade archives reduced at once to parquet `T ms, p, q, m`; raw downloads deleted):
- Binance USD-M futures aggTrades for the remaining BUILD days 10-09..11 (`fetch_futures.py`; all 14 days now in `fut/`).
- NEW venues (`fetch_venues.py`, run with `python -I`; each download in its own empty temp dir): OKX BTC-USDT-SWAP and
  OKX BTC-USDT spot (static.okx.com; files are UTC+8 days, file D covers [D-8h, D+16h) UTC; the 10-23 file extends
  past H and is never loaded, so the last 8 h of VALIDATE have no OKX data), Bybit BTCUSDT linear perp and Bybit spot
  (public.bybit.com, UTC days), Binance spot BTCUSDT aggTrades (data.binance.vision, checksummed). 10-09..10-22, in
  `.cache/re/btc5m-bot/venues/<venue>/`. No checksums exist for OKX/Bybit; the reducer checks schema, ts range, max T < H.
- Not available: Binance futures bookTicker archive (404 for 2026-10; only 30-s `bookDepth` snapshots), so no
  public sub-second order-book history; Coinbase has no archive and its trade-id paging needs a post-H anchor (skipped).

Findings (VALIDATE unless noted):
1. Futures order-level lead-lag at 0.5-s resolution (`fut_leadlag.py`, `results_fut_leadlag_iter3.json`, taker-first
   orders): side agrees with the futures move in [s-6,s-4) 49.3%, [s-4,s-3) 52.9%, [s-3,s-2) 62.9% (peak),
   [s-2,s-1.5) 60.9%, [s-1.5,s-1) 58.1%, [s-1,s-0.5) 56.1%, [s-0.5,s) 54.2%, then 53-54% for 0-5 s after the block.
2. Futures in the frozen rule (`fut_cells.py`, `train3.py`, `results_iter3_models.json`): PIT futures moves, OFI,
   futures move since the last Polymarket print (F_since), basis-adjusted futures fair value (F_z, F_fv, F_gap_*).
   Presence 0.8957 -> 0.9038; dedicated side model 70.3% (quiet 64.8%, moving 78.8%); presence-argmax side 70.0%.
3. INFORMATION-WALL TEST (`wall_test.py`): in Binance-flat seconds (futures |3 s| < 0.3 bp and spot r3 = 0 up to the
   PIT horizon; 50% of one-sided seconds) our futures+spot+tape model predicts the NEXT futures move at chance
   (50.3-51.4%) but the side of the bot predicts it at 55.2% ([s-1,s)), 55.4% ([s,s+2)), 54.1% ([s+2,s+5)), 52.3%
   ([s+5,s+15)); logit z: bot 17.6, ours 2.3; even with futures flat up to s (non-PIT) 55.0%. So the bot sees
   something Binance does not show yet.
4. OTHER VENUES explain most of it (`venue_test.py`, `results_venues_iter3.json`): when Binance is flat, the side of
   the bot agrees with the OKX [s-4,s-1) move 56.0% and the Bybit move 60.3%; when Binance is flat but the venue moved
   >= 0.5 bp (4-5% of those seconds) 74.8% (OKX) and 81.6% (Bybit). 1-s returns: venues and Binance futures lead each
   other symmetrically (corr 0.09-0.12 at +-1 s): price discovery is spread over venues and the bot listens to several.
5. MULTI-VENUE MODELS (`venue_cells.py`, `venue_cells2.py`, `train4.py [six]`): presence / side on VALIDATE
   - + OKX swap + Bybit perp + composites (C_pm = mean move, C_mx = largest venue move): 0.9082 / 72.7%
   - + Binance spot aggTrades + Bybit spot + OKX spot + six-series composites (C6_*): **0.9095 / 73.2%** (taker
     side 75.2%; spot-r3-zero seconds 68.9%; Binance-flat 67.1%; moving 79.7%; McNemar vs futures-only p ~ 1e-111).
   Top side features: C6_pm2000 (mean 2-s move of the six series), C6_mx2000, C_mx2000, C_pm2000. Presence by
   wallet GF 0.908 / XM 0.924 / DS 0.897; with own state 0.921; at p >= 0.30 recall 60.8% at lift 4.29.
6. Wall test with the six-series model (`results_wall_test_iter3_val_side_it3s.json`): in Binance-flat seconds our
   model now predicts the next futures move at 53.8% / 54.5% / 53.1% / 52.0% vs the bot at 55.2% / 55.4% / 54.1% /
   52.3%; logit z bot 11.2, ours 14.8; when the bot disagrees with our model it is right 51.6% (n = 12,546). The
   iteration-2 "anticipation" was mostly cross-venue information, not a private feed. A small residual remains.
7. What is left (`results_side_by_composite_move_iter3.json`): side accuracy by the largest 3-s move of the six
   series: <= 0.1 bp (26% of one-sided seconds, no venue moved) 62.2%; 0.1-0.3 68.4%; 0.3-0.5 72.0%; 0.5-1 76.2%;
   1-2 80.3%; 2-5 83.7%. In no-move seconds 67% are taker seconds and taker accuracy is 62.3%: a quarter of the
   activity of the bot has no visible trigger on any of six public trade feeds (candidates: order-book events on a
   venue or on Polymarket, Coinbase, or rebate volume with an internal side rule).
8. SELECTION v3 (`selection3.py`, `results_selection_iter3.json`): size classes decoded on BUILD (full orders 30 /
   50 / 60 / 100 shares; partial taker fills 5..25, multiples of 5 because makers rest in multiples of 5). Score =
   2*full + partial + p; pre-registered flag = full OR (partial AND p >= 0.30) (0.30 fixed in iteration 1). All 2.74M
   in-window VALIDATE taker prints: pooled AUC 0.866, within-window 0.860, recall 67.7% at lift 4.65 (p ~ 0).
   Co-occurrence baseline (same with the market-only cell score): 0.852 / 0.845, recall 64.1% at lift 4.78. The
   selection part of the target is met; the jump comes from the decoded size rule, not from co-occurrence.
9. OUTCOME (`val_outcome3.py`): the per-window PnL of the wallet correlates 0.885 with its own net position x
   outcome, so the PnL metric is a net-position prediction problem. Per-window PnL correlation: futures model soft
   0.442 (net position 0.453); six-series soft 0.412, soft_side (expected volume p_up + p_dn split by the side model)
   0.436 (Spearman 0.418, net position 0.451; rule return -0.45%); sharp side split 0.412 (rule return +1.75%).
   Frozen primary = soft_side. Still < 0.5.
10. End-to-end `final_rule.evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, six-series rule): presence 0.889
    (baseline 0.869), side 72.2% (taker 72.6%; market-only 63.3%; favourite 44.3%), selection v3 AUC 0.881, recall
    71.4% at lift 4.59, soft_side PnL corr 0.454; OKX coverage 0 there by design (file extends past H). 9 s from the
    local cache; it downloads futures / OKX / Bybit / Binance-spot archives for any other period.

11. KRAKEN (`kraken_test.py`, `results_kraken_iter3.json`; XBT/USD REST trades paged by `since`, which is
    point-in-time safe; 6 sampled VALIDATE hours, 3,436 one-sided seconds): overall the Kraken [s-4, s-1) move agrees
    with the side 63.6%, but in the seconds where none of the six archived series moved (27.9%) it agrees 49.9%
    (n = 335 nonzero): Kraken does not explain the no-trigger quarter either (7 public trade feeds now tested).

12. DISTILLED TRIGGER RULE (`trigger_rule.py`, `results_trigger_rule_iter3.json`): side = sign of C6_mx2000 (the
    largest 2-s move among the six series, PIT). One-sided VALIDATE seconds: any nonzero move (97% coverage) 69.1%
    (the full side model: 73.2%); |move| >= 0.1 bp (65%) 77.2%; >= 0.3 bp (56%) 79.0%; >= 0.5 bp (46%) 80.4%;
    >= 1 bp (25%) 82.8%; >= 2 bp (6.5%) 83.8%. As a presence trigger (move toward o >= 0.5 bp and ask in
    [0.12, 0.88]): 11.0% of cells flagged, recall 33.3% at lift 3.0. The explicit rule: "buy the outcome the fastest
    venue moved toward in the last ~2 s before the horizon, at the ask"; the models add tape context (whether an ask
    is there to hit, race activity) and the no-move quarter.

Status after iteration 3: presence (0.9095) and selection (AUC 0.866, recall 67.7% at lift 4.65) meet their
thresholds; side 73.2% (< 80%) and per-window PnL correlation 0.44 (< 0.5) do not. Target not reached; the
information-wall claim of iteration 2 is withdrawn (other venues explain most of it). Status: continue.

Polyrea bugs: none found. Gotchas: OKX daily trade files are UTC+8 days; Bybit spot timestamps are ms while perp
files are seconds; Binance spot aggTrades archives may be in microseconds; Binance futures bookTicker archives are
not published for 2026-10. Bash heredocs containing apostrophes failed in this tool; write files with the Write tool.

Cache housekeeping (kept under 1.5 GB): deleted the iteration-3 sidecars `cells_fut/`, `cells_ven/`, `cells_ven2/`
(regenerate with `fut_cells.py`, `venue_cells.py`, `venue_cells2.py`, ~4 min), the VALIDATE prediction files, the
iteration-2 spot aggTrades sample and the raw chain logs `chain/own` (fills.parquet keeps every decoded field).

## Next (iteration 4)

1. Residual quarter with no visible trigger: Coinbase BTC-USD (only with a pre-H trade-id anchor), Kraken (REST
   `since` paging by time), Deribit perp (REST by time), Bitget / Gate / HTX archives if public; ETH perps.
2. Explicit trigger rule: distil the side model into "buy o at the ask when the largest 2-s move among the six series
   toward o exceeds x bp" and measure precision / recall; fit a per-venue latency (futures peak [s-3, s-2)).
3. Side model capacity (more rounds, lower learning rate, explicit [s-3, s-2) / [s-2, s-1) windows per venue) and a
   longer BUILD (cells for 10-02..10-08 need tapes for those windows).
4. PnL: strict-fill backtest of the multi-venue trigger (latency >= 2 s, match_slack 2) and a net-position-focused
   proxy (side-model volume restricted to seconds with a visible composite move).

### Iteration 4 (2026-10-31, local Windows laptop, ~50 min)

Split and primary metric unchanged (BUILD = 2026-10-09..16, VALIDATE = 2026-10-16..23, nothing at or after H).

Data added (all time-bounded queries or daily archives that end before H):
- Binance USD-M perpetual aggTrades daily archives (data.binance.vision, checksummed) for ETHUSDT, SOLUSDT, XRPUSDT and
  DOGEUSDT, 2026-10-09..10-22 (`fetch_eth.py`, `ALT_SYM=...`), reduced to parquet in `.cache/re/btc5m-bot/venues/{eth,sol,xrp,doge}fut/`.
- Coinbase BTC-USD trades through the Advanced Trade public market-trades endpoint with `start`/`end` (time-bounded,
  point-in-time safe; no trade-id anchor needed) and Deribit BTC-PERPETUAL trades through history.deribit.com
  (time-bounded), 12 sampled VALIDATE hours (`cb_test.py`, `venues/coinbase`, `venues/deribit`).
- Deleted the BUILD-window data-api tapes (284 MB) to stay under 1.5 GB: they are only needed to rebuild BUILD cells,
  which exist (`cells/`); re-fetch with `fetch_tapes2.py` if new tape features are needed for BUILD.

Findings (VALIDATE unless noted):
1. COINBASE and DERIBIT do not explain the no-move quarter (`results_coinbase_deribit_iter4.json`, 6,533 one-sided
   seconds): in seconds where none of the six archived BTC series moved, the Coinbase 3-s move agrees with the side 56.6%
   (n = 1,103) and Deribit 62.0% (n = 862), but where they disagree with the iteration-3 side model they are right only
   51.3% / 51.1%. Nine BTC trade feeds tested now; none adds information beyond the six archived series.
2. CROSS-ASSET LEAD (new family, `eth_test.py`, `results_eth_iter4.json`): the ETH perpetual explains much of the
   no-move quarter. In seconds where none of the six BTC series moved (> 0.1 bp over [s-4, s-1)), the ETH 3-s move agrees
   with the bot's side 63.2% (n = 16,333, z = 34); when |ETH move| >= 1 bp 79.1% (n = 2,394) and >= 2 bp 83.6%. Where ETH
   (>= 1 bp) disagrees with the iteration-3 side model, ETH is right 69.5% (n = 817). Over all one-sided seconds the ETH
   3-s move alone agrees 71.5% (BTC futures alone ~70%). ETH moves 1.235 bp per BTC bp over 3 s (BUILD slope).
3. OTHER ALTS (`alt_test.py`, `results_alts_iter4.json`, 3 sampled days): in seconds where neither the six BTC series nor
   ETH moved, SOL / XRP / DOGE 3-s moves still agree 55.5% / 54.5% / 53.7% (z 5-7); >= 2 bp 64-71%. The bot reads a
   broad crypto factor, not only BTC.
4. ETH LEAD-LAG (`eth_leadlag.py`, `results_eth_leadlag_iter4.json`): on 0.5-s returns, corr(ETH_t, BTCperp_{t+0.5s}) =
   0.218 vs corr(BTCperp_t, ETH_{t+0.5s}) = 0.120 (contemporaneous 0.708): ETH leads BTC at sub-second horizons. The bot's
   side agrees most with the ETH move in [s-3, s-2) (65.3-65.7%, more than the BTC futures move in the same windows,
   61.8-63.1%), the same reaction lag as for the BTC venues; in no-move seconds the peak is [s-3, s-2.5) (58.2%).
5. MODELS (`alt_cells.py`, `train5.py [four]`, `results_iter4_models.json`, `results_iter4_models_four.json`; same
   split, sampling and parameters as iteration 3; the iteration-3 models reproduce 0.9095 / 73.2% on the same rows):
   - it4 (+ ETH perp: moves 0.5-10 s, OFI, age, count, ETH-minus-beta x six-series move, move since the last print):
     presence 0.9127, side 75.0% (taker 77.5%, no-move 66.6%).
   - it4b (+ SOL, XRP, DOGE and BTC-equivalent alt composites): **presence 0.9132** (taker 0.9187, maker 0.8832, own state
     0.9242; GF / XM / DS 0.912 / 0.924 / 0.901; at p >= 0.30 recall 64.0% at lift 4.30), **side 75.3%** (taker 77.9%,
     no-move 67.6%, moving 78.0%; McNemar vs it3s p ~ 2e-82). A bigger side model (900 rounds, 63 leaves) gives 75.3%
     too: capacity is not the limit. Alt features carry 22% of the side model's gain (A_pmmean2000 is 5th).
6. SIDE BY SEGMENT (it4): taker seconds (77.5% of one-sided seconds) 77.5%, of which taker seconds with a visible move
   80.1% (n = 54k) and without 68.6%; maker-only seconds 66.4% (maker fills also follow the venue move: C6 sign agrees
   66.8% in moving maker seconds, consistent with lost-race remainders, not adverse selection).
7. SELECTION (`selection4.py`): it4b cell score with the decoded size classes: pooled AUC 0.869, within-window 0.864,
   recall 68.6% at lift 4.63 at the pre-registered flag (co-occurrence baseline 0.852 / 0.845, recall 64.1% at lift 4.78).
8. WALL TEST with it4b (`wall_test4.py`, `results_wall_test_iter4_val_side_it4b.json`): over all one-sided seconds our
   PIT model now predicts the next Binance futures move better than the bot's own side (0-2 s: 58.3% vs 57.1%); when the
   bot disagrees with our model it is right 48.3%. In the 18.7% of one-sided seconds where neither the six BTC series nor
   ETH moved, the bot's side still predicts the next 0-2 s futures move at 53.0% (ours 51.3%; logit z bot 5.7, ours
   1.2; bot right 52.9% when it disagrees with us, n = 4,871). A small residual of information that is not in any public
   trade archive tested (candidates: venue order-book quote changes, which have no public history for 2026-10).
9. OUTCOME (`val_outcome4.py`, `results_outcome_iter4_it4b.json`): new NET-FLOW proxy (LightGBM regression of the
   cluster's signed share flow per second, BUILD only): per-window PnL correlation 0.434 (Spearman 0.412, net-position
   correlation 0.458, the best so far); soft_side with it4b 0.426; it3s soft_side on the same pipeline 0.436. The better
   side model does not raise the PnL correlation. Diagnostic (`net_diag4.py`, `results_net_diag_iter4.json`): the net
   position is a small difference of large two-sided volumes (median |net| = 12% of gross; 34% of gross volume is in
   seconds where both outcomes are bought); per-window Up / Down share predictions correlate 0.78 / 0.77 with the truth;
   ORACLE per-second volume x model side would give 0.555 and model volume x ORACLE side 0.548: volume and side errors
   limit the net-position correlation about equally.
10. End-to-end `final_rule.evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, it4b + netflow, 8.7 s): presence
    0.893 (baseline 0.869), side 74.3% (taker 75.7%; it3s gave 72.2% on the same hours), selection v3 AUC 0.884 with
    recall 72.4% at lift 4.57; it downloads the four alt-perp archives (checksummed) for any other period.
11. VOLUME MODEL (`val_outcome5.py`, `results_outcome_iter4_shares.json`): LightGBM regression of the cluster's shares
    per cell (BUILD only) predicts per-window total shares at corr 0.875 (presence-based volume 0.785). Proxy "shares"
    (buy the predicted shares of each outcome in every cell at the last implied ask): per-window PnL correlation **0.439**
    (Spearman 0.414, net-position correlation 0.467), the best so far but within noise of the others (netflow 0.434,
    netflow/shares mean 0.437, shares split by the side model 0.419). Frozen as the primary outcome proxy.
12. ETH ON OTHER VENUES (`fetch_eth_venues.py`, `eth_venue_test.py`, `results_eth_venues_iter4.json`, VALIDATE 10-19 and
    10-21): OKX ETH swap, Binance ETH spot and Bybit ETH spot add nothing beyond the it4b model (when their 3-s move
    disagrees with the model they are right 33-50%). Rejected; the Binance ETH perp plus the alt composites carry it.

13. DECISION-TIME ALIGNMENT (`side_lag.py`, `results_side_lag_iter4.json`): explicit lagged segments [s-3, s-2) and
    [s-4, s-3) (differences of the PIT windows) for the ten series (alts in BTC units), the signed largest [s-3, s-2) move
    across series, the net count of series moving each way, and the composites' segments: side 75.46% vs 75.26%
    (taker 78.2% vs 77.9%; McNemar p = 0.006; lag features 11% of the gain). Frozen (`model_it4b_side_lag.txt`,
    `alt_cells.lag_feats`). End-to-end on the last 2 VALIDATE hours: 74.1% (1,183 seconds; the plain model 74.3%).

14. STRICT-FILL BACKTEST (`strict_bt4.py`, `results_strict_backtest_iter4.json`; also in `evaluate` as
    outcome.strict_fill_backtest): 30-share BUY limits at the last implied ask of the side-model outcome when p >= 0.30;
    fills only against other traders' taker BUY prints with block ts in [s+1, s+3] (latency >= 2 s after the information
    horizon) at price <= limit, capture 1.0 (upper bound). VALIDATE: 60,466 fills, $262k bought, PnL before rebates
    -$4.2k (-1.6%), fees $8.9k, +0.1% with a 50% fee rebate; per-window PnL corr with the cluster 0.18. The wallet:
    +0.17% before rebates. A slow replicator only breaks even with the rebate tier.
    `evaluate` timing: ~3 s per UTC day of reference archives (drop_duplicates on the concatenated day files dominates)
    plus ~0.1 s per window.

Status after iteration 4: presence (0.9132) and selection (AUC 0.869, recall 68.6% at lift 4.63) meet their thresholds;
side 75.5% (< 80%) and per-window PnL correlation 0.439 (< 0.5) do not. Target not reached. Status: continue (primary
metric +0.0175 over the last two iterations, side +2.1 points this iteration with a genuinely new family, cross-asset).

Polyrea bugs: none found. Gotchas: pandas 2 parses ISO timestamps with microseconds to datetime64[us], so
`.astype("int64") // 10**6` gives SECONDS, not ms (my first Coinbase run was wrong for this reason; fixed with
`.to_numpy().astype("datetime64[ms]")`). Coinbase Advanced Trade's public `/market/products/{id}/ticker` accepts
`start`/`end` for historical periods (time-bounded, PIT-safe) and returns at most 1,000 trades (split the range when full);
its bid/ask fields are empty for history. Deribit history API (history.deribit.com) is time-bounded too. Backgrounded
`&` jobs inside the Bash tool keep running after the tool call returns (the tool reports completion at once).

Cache housekeeping (1.4 GB at the end): deleted the BUILD tapes, the ETH-on-other-venues test files, val_pred_it4 /
val_side_it4 (ETH-only, superseded) and val_side_it3s.parquet (input of kraken_test / cb_test / eth_test: pass or adapt
them to val_side_it4b.parquet, same columns plus mx6 / E_* moves). Kept: venues/{eth,sol,xrp,doge}fut (14 days each),
venues/{coinbase,deribit} (12 hours), val_pred_it4b.parquet (all VALIDATE cells: p, p3, p4, p_mkt, labels),
val_side_it4b.parquet (one-sided seconds), val_outcome_it4b.parquet (per second pu, pd, ps, nf, asks),
val_side_moves_iter4.parquet (six-series and ETH moves per one-sided second).

## Next (iteration 5, the last)

1. Side (75.3%): the remaining gap is in seconds with no visible move on any BTC series or ETH (19%, ~64%) and maker-only
   seconds (66%). Candidates: more alts (BNB, AVAX, LINK, SUI perps) or an alt index; a longer BUILD (cells for
   10-02..10-08 need tapes for those windows, ~1 h of fetching), which may matter more than features; a side model
   trained on taker seconds only (decision-aligned) blended with the current one.
2. PnL correlation (0.44): volume and side errors limit it equally (oracle volume x model side 0.555). A joint per-second
   model of Up shares and Down shares (two regressions with the side information as features) may help; also predicting
   the two-sided seconds (34% of gross volume).
3. Information residual: in flat seconds the bot still predicts the next 0-2 s BTC move at 53% (ours 51%); a full wall
   claim would need order-book data (none archived for 2026-10).

### Iteration 5 (restart under the 2026-10-31 brief; 2026-10-31 12:22 UTC start, local Windows laptop)

Interrupted first attempt (about 25 min, 11:00-11:25 UTC, before the restart): Tardis free first-of-month book samples
(`d1001_*.py`, 2026-10-01 00:00-08:00, `results_book_test_iter5.json`) and the Bybit public orderbook.200 archive
(quote-saver.bycsi.com, `bybit_ob.py`, `book_feats.py`, `side_book.py`, `results_side_book_iter5.json`): Bybit perp top-of-book
features (imbalance averaged over the last second, mid changes) raise the side model on VALIDATE from 75.46% to **76.66%**
(McNemar p = 1e-32; taker seconds 79.4%, no-move seconds 66.1%); wired into `final_rule.py` as `USE_BOOK` (side model
`model_it5_side_book.txt`, BUILD-trained). In the Tardis sample the venue book imbalances agree with the side 64-70% overall
and 51-62% in no-BTC-move seconds. Kept as the current side rule.

Brief changes adopted now: decision-level decoding (component by component), B1 calldata first, catalog + X items in
state.json, sealed calendar via tools/sealed.py (development after H: 10-31 00:00-06:00 and 12:00-18:00 UTC so far; the
live recorder started 10-31 12:18 UTC), target conditions incl. gain >= 0.05 over the market-activity baseline.

Competing explanations (iteration 5) and what separates them:
- E1 cross-venue latency taker: fires BUY-at-ask after a fast composite (BTC venues + ETH/alts) moves. Predicts: decision
  (submission) times follow venue moves by a short fixed latency; side = move sign; limit = current ask; edge grows with move.
- E2 pre-signed order pool or ladder: orders are signed long before they reach the book (first calldata sample: cluster
  taker orders signed 30-100 s before their block). Either a latency pool (signed in advance, submitted on a trigger:
  the trigger is still E1) or a plan made at signing time (price/side decided at signing). Separates by: is the limit of a
  taker order the touch at submission or a price fixed at signing; do sign times cluster (batches, window open, periodic).
- E3 rebate / volume farmer: the objective is taker volume (50% rebate tier); side has a weak tilt; volume follows a target.
  Separates by: steady volume per hour/day regardless of moves; edge per order near zero in quiet seconds.
- E4 two-sided inventory maker / complete-set builder: buys both sides below a pair cost of 1 and merges. Separates by:
  pair cost per window, MERGE/REDEEM activity, inventory-driven side.
- E5 tape follower / copy trader: buys what other takers just bought. Separates by: order decision time vs the other
  takers' prints (sign or submission time BEFORE the competitor print = racer, AFTER = follower).
- E6 settlement-feed fair value (Chainlink Data Streams via RTDS): explains the multi-venue sensitivity (a median of venues).
  Separates by: live lead-lag of its orders vs RTDS Chainlink updates vs Binance.
- E7 Polymarket book-event sniper: in quiet seconds it lifts asks that appear below its value (no spot move needed).
  Separates by: live books: does a new ask / removed bid on the bought token precede its quiet-second orders.
- E8 scheduled loop: orders on a timer (fixed cadence, ms-phase). Separates by: inter-order intervals, sign-ms phase.

B1 calldata decode (iteration 5; `code/calldata.py`, `code/b1_analysis.py`; results_b1_iter5.json, results_b1_ladder_iter5.json):
- Data: batched eth_getTransactionByHash (25 calls per JSON-RPC POST, <= 3 POST/s, drpc then publicnode; raw inputs NOT
  stored) for every cluster transaction in 11 sampled whole hours (7 VALIDATE days, 4 BUILD days): 17,709 txs, 57,966
  decoded orders (taker order + maker orders of each matchOrders, selector 0x3c2b4399), of which 17,863 cluster orders
  (13,443 distinct orders by (maker, salt)). Saved decoded only: .cache/re/btc5m-bot/calldata_sample.parquet.
- Fingerprint (C8): every cluster order is a BUY, signatureType 3 (signer = maker = the wallet contract), 317-byte wrapped
  signature, metadata = 0 and builder = 0 (5.8% of other orders carry a builder code). salt / timestamp is uniform on
  [0, 1] (deciles 0.10, 0.25, 0.51, 0.75, 0.90; max 1.0, never above): salt = round(Math.random() * Date.now()), the
  TypeScript @polymarket/clob-client generator.
- ORDERS ARE PRE-SIGNED. Signing time (order `timestamp`) to block: taker orders median 72 s (1% 3.9 s, 99% 133 s; other
  traders' taker orders median 3.1 s). So the signing time is NOT the decision time.
- LADDER SCHEDULE: 99.9% of filled cluster orders were signed in one of THREE bursts per window, at rel = -89.5 s (+-0.2;
  1-99%: -89.97..-89.03), +42.0 s (40.3..44.3) and +172.7 s (170.5..174.9) from the window open (spacing ~131.5 s; the
  first burst is 90 s BEFORE the window opens, while the previous window runs). Orders are used 4-136 s after signing
  (99.9% quantile 136.5 s), i.e. each burst serves the next ~131 s.
- LADDER STRUCTURE: within a burst, the signing offset is a monotone function of price within each outcome (Spearman rho
  median 1.0; ~1.66 ms per cent), i.e. a loop over the 1-cent price grid (filled prices 0.13..0.88 seen); several orders
  share the same ms at the same price (copies; up to 10 filled copies of one level), and the large size (100) is signed
  at the same ms as the small one (30) at the same price. Example DS burst (window 10-22 15:15): Down 0.24..0.77 in
  0-93 ms, then Up 0.18..0.76 in 924-1021 ms. The bot pre-signs a full BUY ladder (both outcomes, every cent, a few
  copies, two sizes) and at trigger time submits the pre-signed order whose price equals the current best ask.
- ONE PROCESS, THREE KEYS (C1): per window the three wallets' bursts are staggered, XM first, DS +1.06 s, GF +2.17 s
  (medians; 10-90%: GF-DS 0.16..1.90 s, XM-DS -2.02..-0.14 s): one process signs the three wallets' ladders one after
  another. The wallet contracts are proxies with `owner()` = three different EOAs (GF 0x78a42b84..., XM 0x07c18787...,
  DS 0xd2564062...; GF/DS owners have nonce 0, XM's owner has an EIP-7702-style 23-byte code); no common owner key.
- SIZES (per order, calldata): 30 (52%), 60 (26%), 100 (11%), 50 (9%), 200 (1%). Each day runs a (small, large) pair:
  10-09..11 (60, 100), 10-15 (30, 50), 10-16 (50, 30, 200), 10-17..18 (50, 30), 10-19..22 (30, 100); 10-31 00-06: 30 /
  60 / 100. Large share by wallet DS 5%, GF 30%, XM 32% (10-19..22): mostly a per-wallet setting; weakly higher after
  large moves either way (16-21% vs 8% without a move).
- Side component, window level: the pooled cluster buys both outcomes in 99.8% of VALIDATE windows (one-sided 0.2%; DS
  0.2%, GF 3.1%, XM 24.3%), so the brief's side condition (one-sided in >= 20% of windows) does not apply pooled; the
  per-second side remains a decoded decision and is still reported.
- Siblings (C1): in the same transactions, other orders with the cluster's schedule (signing time within the three
  burst windows), signatureType 3, 317-byte signature and builder 0 and a gap > 4 s: 451 of 40,103 other orders (chance
  rate of the burst windows ~2.5-4%); top maker 0xd84403ef... (77 orders), 0x9d57c42e... (32): candidate siblings, open.
- FOURTH WALLET (C1, new): 0xd84403efd50b49a1d8a7181627e00307e6ea5908 runs the same bot: BUY only, signatureType 3,
  317-byte signatures, salt/timestamp uniform on [0, 1], the same three-burst schedule (rel_sign quantiles 5% -89.2 s,
  median 46.1 s, 75-95% 176.1-176.6 s: ~3-4 s after GF, i.e. fourth in the signing loop XM -> DS -> GF -> W4), sizes
  30 / 100 / 50 / 60 / 200, gaps 10-125 s. In VALIDATE hour 10-21 13:00 it had 344 fills (60% taker), all BUY, all on
  BTC 5m tokens (the three studied wallets ~2,000); its counterparty is a cluster wallet in 0.6% of its fills. Not in the
  scored cluster (the target is defined on the three studied wallets); a sibling to add to the cluster definition and to
  remove from the "other traders" tape features in a later iteration (its prints currently count as market activity).
- TIME STOP vs PRICE RANGE (B3b, timing): the fill rate per cell GIVEN a mid-range price (last print 0.15-0.85) RISES
  through the window (0.11 at 0-15 s, 0.14-0.16 at 60-150 s, 0.21-0.25 at 180-240 s, 0.32-0.34 at 240-270 s) and drops
  only at 270-285 s (0.18) and 285-300 s (0.07). The 240-270 s taper of raw activity is the price leaving the ladder's
  range (mid-range share falls from 99.7% to 8%), not a stop at the start of the 60-s settlement TWAP. The bot keeps
  trading through the first half of the TWAP minute and stops ~270-290 s.
- NON-TRADE ACTIVITY (B4, B6, B7, B8; data-api activity with a types filter, VALIDATE week 10-16..23): no REWARD, YIELD,
  MERGE, SPLIT or CONVERSION rows for any wallet; REDEEM once per traded window (GF 2,218 rows / $877k, XM 1,814 / $221k,
  DS 2,256 / $1.51M); MAKER_REBATE once a day (week totals GF $1,057, XM $318, DS $1,678). So: no liquidity rewards (B7
  ruled out), no holding rewards (B8 ruled out), no complete-set merging (B4: it holds both sides to resolution and
  redeems the winner), maker rebates ~$3.1k/week. The taker-fee rebate the dossier mentions (Obsidian tier) is not an
  activity row; the on-chain taker fee is the full 0.07 p (1 - p).

BASELINE BUG (found in iteration 5, my own code, not polyrea): the "market-only" co-occurrence baseline used since
iteration 2 (`MKT` = rel, tau, TAPE_FEATS, EXTRA) contains reference-feed features: `sp_since` (Binance move since the last
print) and `gap_m`, `gap_ask`, `gap_vw`, `dgap5`, `dgap10` (Binance fair value minus Polymarket prices). The brief's
baseline is market activity only. PURE baseline (`decision_presence.py`, results_decision_presence_iter5.json; same BUILD,
sampling and LightGBM parameters): presence 0.8781 (old 0.8889) -> gain of the it4b rule **+0.0351** (not +0.0243); by wallet
GF 0.912 vs 0.869, XM 0.924 vs 0.877, DS 0.901 vs 0.868. Selection (size classes + cell score) 0.8693 vs pure baseline
0.8461 (gain +0.023; old baseline 0.852); at the pre-registered flag recall 68.6% at lift 4.63 vs 61.7% at lift 5.07.

D1 DECISION-ALIGNED PRESENCE (label = cluster fill at block second s + k from cell-s features, horizon s - 1):
k = 0: 0.9132 vs pure 0.8781 (+0.0351); k = 1 (horizon at the decision time, block - 2 s): 0.9070 vs 0.8717 (+0.0353);
k = 2: 0.8893 vs 0.8691 (+0.0202). Aligning the label to the decision time does not raise the gain: the market-activity
co-occurrence is not an artefact of the block-time label. Remaining gap to the target's +0.05: ~0.015 AUC.

LIVE LAB (iteration 5; `code/live_lab.py`, `code/live_trigger.py`, `code/fetch_dev_post.py`, `code/fetch_binance_rest.py`):
- The shared recorder runs (pid 27184, started 10-31 12:18 UTC; clob_crypto had 18 "slow consumer" reconnects by 13:02,
  so the book record has gaps). Data used: development block [12:00, 18:00) only, through `iter_live`.
- TOOLS BUG (tools/live.py, not mine): `iter_live` raises `zlib.error: invalid block type` on
  `.cache/live/dev/clob_crypto/20261031T12.jsonl.gz` after the record at 12:24:51 (the file holds a broken gzip member
  boundary, probably from the recorder restart at 12:18); `iter_live` only catches EOFError/OSError, so the remaining
  35 minutes of that hour are unreadable through the sanctioned reader. My wrapper catches zlib.error and keeps what was
  read; I did not read the file any other way. The 13:00 file reads fine in near real time.
- Cluster on-chain fills in the development blocks after T0: 10-31 00:00-06:00 9,420 fills (DS 4,303, XM 2,806, GF
  2,311; sizes still 30/60/100); 12:00-13:00 2,420 fills (quieter Saturday midday).
- First live numbers (12:14-12:25 readable span, 15 taker orders with a recorded match): the order MATCHES 2.0 s
  (median; 5-95% 1.4-2.7 s) before its block timestamp (maker fills 2.3 s); the server clock runs 0.72 s ahead of the
  laptop clock (recv - server = -0.72 s); taker limit vs the recorded best ask just before the match: equal 47%,
  within one tick 87% (limit one cent below the ask in 5 of 15: the book moved inside the 200-ms recording granularity);
  at SIGNING time the limit equalled the then-ask in only 7% (orders are pre-signed ladder levels, not priced at
  signing). The bot's match follows another trader's trade on the same market within 0.5 s in 73% (placebo 53%) and a
  trade at the same price within 0.5 s in 57%. Chainlink RTDS 1-s move over the 3 s before the match agrees with the
  side 80% (n = 10 moved; placebo 33%). Too few orders to conclude; rerun on the 13:00 file below.
- 13:00 file (13:00:01-13:06:11, first look; `recs` now reads hour by hour so the broken 12:00 file does not abort
  later hours): 352 cluster fills in recorded development windows, 93% with a recorded match time (same tx hash).
  Taker orders (n = 130): match -> block median 2.16 s (5-95% 1.27-3.23 s). PRICE: the bot's limit vs the recorded best
  ask of the bought outcome at match - 50 ms: EQUAL 70.8%, within one tick 86.2%; at match - 100 ms 70.8% / 84.6%;
  at the match itself only 40% / 81.5% because the record at the match already shows the post-trade book (limit one cent
  below the "ask" in 35%); 500 ms before 32% / 65%; 1 s before 22% / 42% (the touch moves in the second before the bot's
  order: it trades when the book is moving). Against block - 2.0 s (a fixed lag, no match record): 36% / 60%. At the
  SIGNING time the limit equalled the then-ask in 0.8%. Decoded price rule: limit = the best ask at the decision
  instant; frozen in `final_rule.py` as the recorded ask 50 ms before the recorded match (`PRE_MATCH_MS`), used for the
  price metric wherever the live recorder covers the exam period (future blocks), else the tape anchor (53%).
- Live trigger, first look on the 13:00 file (n = 130 taker orders; `results_live_trigger_iter5.json`, re-run at the end):
  Binance USD-M BTC futures (REST aggTrades, exchange ms) moved > 0.05 bp in the 2 s before the match for only 20 of
  130 orders (Saturday, ~5 trades/s); when it moved, it moved toward the bought side 70% (placebo 47%); ETH perp in the
  last 1-2 s: 84-87% (n = 15-19; placebo 58-60%). Chainlink RTDS 1-s price over the last 1-3 s: 50-54% (n = 95; placebo
  47-50%): the bot does NOT follow the settlement feed's 1-s price (E6 rejected at this n). Polymarket: its match comes
  a median 80 ms after another trader's trade on the same market (87% within 0.5 s; placebo 72%, median 249 ms); the
  ask of the bought outcome ROSE in the second before the match in 58.5% (fell 30.8%; placebo 22% / 25%); the signed
  size of the other traders' trades in the last 100-2,000 ms agrees with its side only 53-62% (placebo ~50%). So most
  live orders come inside bursts of other traders' trades while the bought outcome's price is moving its way, with no
  BTC/ETH futures trade move in the previous 2 s: the missing trigger is faster than trades (quotes) or Polymarket-internal.
- NEW RECORDER (live_lab): `code/rec_binance_fut.py`, Binance USD-M futures BTCUSDT + ETHUSDT bookTicker (only when the
  best bid/ask PRICE changes) through tools/live.py's Writer, feed `btc5m_bnfut`, started 10-31 13:11:24 UTC (pid 7095 via
  nohup; python pid 31524 in its status file `.cache/re/btc5m-bot/rec_binance_fut.status`), hard stop 10 h (23:11 UTC),
  ~3 records/s (~1-2 MB/h gz). The combined-stream aggTrade channel delivered nothing (trades come from the REST/daily
  archives instead). The exchange event time runs ~0.8 s ahead of the laptop clock (use E/T, not t). Purpose: test the
  quiet-order trigger against futures QUOTE changes at ms resolution (no public bookTicker archive exists for 2026-10).
- C2 COPY TRADING, strong form (`code/c2_copy.py`, results_c2_copy_iter5.json; 300 VALIDATE windows, 21,863 cluster taker
  orders, 246 other wallets with >= 200 in-window BUY prints): no leader. The largest co-occurrence is the FOURTH WALLET
  0xd84403ef... (same outcome in the same block second before 12.3% of cluster orders, placebo 2.8%; 2-10 s lead lift
  2.4) followed by ~5 fast wallets at ~10% same-second co-occurrence (0x41e2e1cc..., 0x2ed94d1a..., 0xeebde7a0...,
  0x19b38230...; 2-10 s lead lift 1.7-1.8). Any single wallet precedes the cluster at a 2-10 s lag in <= 35% of orders
  (placebo 15-20%), spread over lags with no fixed delay: co-racers on common triggers, not a copied leader.

Frozen rule (iteration 5, `code/final_rule.py`): `evaluate(start_ts, end_ts, intervals=None)`, `ALLOW_SEALED = False`;
adds the pure market baseline (presence and selection), decision-aligned presence with a 2-hour block bootstrap of the
gain, the live-book price rule (`PRE_MATCH_MS = 50`), the B1 ladder check (seeded 1,500-tx calldata sample) and the
brief's `target_metrics` keys; side model `model_it5_side_book.txt`. End-to-end on the last 2 VALIDATE hours (69 s):
presence 0.893 vs pure 0.857 (old 0.869), decision-aligned 0.888 vs 0.854, side 77.9%, selection 0.884 vs pure 0.870
(recall 72.4% at lift 4.57), price (tape anchor) 53.2%, strict-fill PnL corr 0.38 / 0.32 (24 windows; VALIDATE week
0.18 / 0.17), ladder check 100% of 1,514 orders (chance 5%). The frozen live price rule on the 10-31 13:00-13:06 dev
block (95 taker orders): within one tick 96.7%, exact 86.7%. NOTE for successors: never run `evaluate` on a period
after H that is not wholly development (its spot loader reaches 2 h before the start and the daily archives span the
whole UTC day, which includes sealed blocks); test live-period code with the harness approach used here instead.

Status after iteration 5: target not reached. Presence 0.9132 vs a PURE market baseline 0.8781 (gain +0.035 < 0.05);
selection gain +0.023 (< 0.05); side 76.7% per second, but the bot is two-sided in 99.8% of windows (the side
condition does not apply pooled); price within a tick: 53% historically (no book), 97% where the book is recorded;
executable PnL correlation 0.18 (< 0.5). Status: continue.

What is decoded now, mechanically: the order factory (pre-signed 1-cent BUY ladders on a ~131.5-s window-locked
schedule, sizes, salts, signing order of the wallets, a fourth wallet), the price (touch at the decision instant), the
exit (hold to resolution), the time stop and price range. What is not: the trigger of the ~70% of orders with no BTC/ETH
trade move in the preceding 2 s (live) and therefore the presence gain over market activity and the PnL replication.

## Next (iteration 6)

1. Quiet-order trigger at ms resolution with the live lab (now three aligned clocks: Polymarket server ms for the bot's
   matches, Binance exchange ms for quotes from `rec_binance_fut.py`, Chainlink RTDS): event study of the bot's matches
   vs futures bookTicker mid/imbalance changes (X11), Polymarket maker reprices without trades (ask rises before 59% of
   its orders vs 22% at random), and the 15m market (X8). Add OKX/Bybit quote websockets to the recorder if Binance
   quotes do not explain it.
2. X5: add the fourth wallet 0xd84403ef... to the cluster and drop its prints from the market-activity features (BUILD
   tapes must be re-fetched: ~1 h through the cached data-api adapter); X12: other traders' calldata signing times as
   ms decision times for the race order within a block.
3. A price-aware executable replica for the PnL target: submit at the touch from the decoded trigger with the bot's
   sizes and the live book (future blocks), and a tape-only version for h1/h2.
4. Remaining catalog items: A4b (Kalshi), A8 (operational events), B9 (maker rebate pool share), C4b, D2 (hazard /
   state-machine model of submissions), X7 (funding, liquidations, options), X9 (change points over the full history),
   X10 (public GitHub template with pre-signed ladders).

Addendum (A8 operational events / C4 versions, measured): 292 of the 4,032 BUILD+VALIDATE windows have no cluster
fill at all, mostly in whole-cluster OUTAGES (all wallets at once): 10-09 09:35 (3.3 h), 10-11 12:35 (4.3 h), 10-12
09:15 (5.1 h), 10-21 07:15 (4.5 h), and 40-75 min on 10-09, 10-15, 10-16 (x2), 10-19, 10-19, 10-20. Sizes before and
after are unchanged except at the 10-19 13:40-14:55 restart, where the large size changed from 50 to 100 (a config
change at a restart). The outages are bot-side (the markets kept trading); they are all negatives in the presence
metric for both the rule and the baseline. Not yet matched to Polymarket announcements or API incidents (C4b).

THE BLOCK CLOCK (iteration 5, `code/block_bins.py`, results_block_bins_iter5.json): the cluster's fill rate per cell has a
strict period-3 pattern in the window second (e.g. rel 30..38: 0.227, 0.047, 0.212, 0.244, 0.046, 0.228, ...): Polygon
produced a block every 1.5 s, so one second in three holds no block and can never hold a fill (VALIDATE fills by Unix
second mod 3: 0.476 / 0.094 / 0.430; phase-locked on 6 of 7 days; BUILD uniform because the phase jumped). These
structural zeros are free AUC for any model that can infer the block phase, and the market-activity baseline infers it
from the timing of other traders' prints (n1, n2, age_last are its top features). Chain-clock fit per UTC hour,
ts = floor(phi + 1.5 (block - b_ref)) from (block number, block timestamp) pairs (the cluster's fills used only as a
source of chain timestamps): 154 of 166 VALIDATE hours locked (one phi explains >= 98% of pairs); in locked hours only
block seconds are kept (66.5% of cells) and NO positive falls outside them (100% of fills are in predicted block seconds).
Presence over block seconds with the iteration models (trained on all seconds): rule 0.8752 vs PURE baseline 0.8192,
gain **+0.056**; decision-aligned (label s+1) 0.8628 vs 0.8062, +0.057. The gain over market activity is above the
target's 0.05 once the impossible bins are removed: the block is the right presence unit (D1). Retrained on BUILD block
seconds: `code/block_presence.py` (results_block_presence_iter5.json, with halves, wallets and a 2-hour block bootstrap).

Final numbers of iteration 5 (supersede the interim lines above where they differ):
- Block-second presence retrained on BUILD block seconds (`block_presence.py`, `model_it5_blk_*.txt`): VALIDATE 804,746
  block-second cells: rule **0.8747** vs PURE baseline 0.8193, gain **+0.0554**, 2-hour block bootstrap (2,000 draws, 84
  blocks) 95% CI [0.0524, 0.0582], one-sided p < 0.0005; halves 0.875/0.820 and 0.873/0.818; wallets GF 0.8745/0.8098,
  XM 0.8927/0.825, DS 0.8571/0.8047; at p >= 0.30 recall 66.2% at lift 2.95. All-seconds gain +0.035 has CI
  [0.0337, 0.0364]. The presence condition of the target holds on VALIDATE in the block-second unit with my baseline.
- Live price, frozen code, 10-31 13:00-13:22 (277 taker orders): fill price within one tick of the recorded ask 50 ms
  before the match 93.2% (exact 78.1%; DS 95.4%, GF 94.7%, XM 62.5% of few); fixed lag block - 2 s 56%.
- Live trigger, 265 matches: BTC futures trades moved in the last 1 s before 16% of them (agree 85.7%, placebo 50%), ETH
  perp trades 25% (86.6%); futures QUOTES (own recorder, 65 covered): BTC moved before 19 (84%), ETH 27 (78%); Chainlink
  RTDS 1-s price 50.5% (n = 212): no information; the bought outcome's ask rose in the last 1 s before 59.6% (placebo
  24.9%), lifted by other traders' trades in 101 cases vs 14 maker reprices; 85% of matches come within 0.5 s after
  another trade (placebo 66%); BTC 15m market mid moved its way in the last 1 s in 66% (n = 88; placebo 54%).
- Status: target not reached (price historically 53%, executable PnL correlation 0.18); continue.
- Block clock verified against block HEADERS (`results_block_clock_headers_iter5.json`): in 8 random locked VALIDATE
  hours, the timestamps of 80 consecutive blocks (eth_getBlockByNumber) give exactly the block seconds predicted by the
  per-hour fit (agreement 100% in all 8; 80 distinct seconds per ~120 s, 1.49-1.51 s per block). The unit is a chain
  property; the cluster's fills only supply (block, timestamp) pairs.
- Recorder check at the end: `rec_binance_fut.py` still writing (status file updated); the shared recorder still running.

### Iteration 6 (2026-10-31 14:07 UTC start, local Windows laptop; development data: before H, and the 10-31 12:00-18:00 block)

Split and primary metric unchanged (BUILD = 2026-10-09..16, VALIDATE = 2026-10-16..23; nothing sealed read). Calendar
(tools/sealed.py): released lots none; development after H so far = 10-31 00:00-06:00 and 12:00-18:00 UTC. The shared
recorder runs (pid 27184; clob_crypto 34 slow-consumer reconnects; its 12:00 files of clob_crypto and rtds are unreadable
after ~12:18-12:24 through iter_live, zlib.error, so the live studies use 13:00 onward). Other agents' recorder feeds in
.cache/live/dev/ (dm_*) were NOT read.

Competing explanations at the start of iteration 6 (what separates them; verdict at the end of this iteration):
- E1 cross-venue TRADE latency taker: buys o at the touch ~100-600 ms after a fast venue's trade price moves toward o.
  Separates: a venue trade move in [m - 600, m - 100) ms before most matches, side agreement >= 90%, placebo far lower.
- E2 cross-venue QUOTE latency taker (top-of-book / microprice on Binance, Bybit, OKX, Hyperliquid, Coinbase) before
  trades print. Separates: quote moves before the matches that have no trade move.
- E3 Polymarket book sniper / prey makers: lifts freshly posted or stale maker quotes. Separates: quote age at the match
  (calldata signing ms of the consumed maker order), a new cheaper ask in the last 50-500 ms, maker identity.
- E4 level (value) rule: fires when FV - ask > k p(1 - p); quiet orders are marginal cases (overshoot fades, drift).
  Separates: side agreement with a value gap (FV move minus Polymarket move) in quiet matches; fade of older moves.
- E5 rebate-volume farmer with a weak tilt: income = 50% of taker fees; quiet trading near the rebate-adjusted break-even.
  Separates: TAKER_REBATE rows = 0.5 x fees; quiet edge ~ net fee; volume steady regardless of moves.
- E6 crowd follower (copies the first taker within ms). Separates: bot match before vs after other trades within 20-50 ms.
- E7 settlement-feed (Chainlink Data Streams) fair value. Separates: Chainlink RTDS move before the match, at any lag.
- E8 an unrecorded feed (private, paid, or a venue not tested). Separates: residual after E1-E4 on all recorded feeds.

Data added (iteration 6):
- NEW RECORDER `code/rec_lab6.py` (live_lab; pid 15084; started 10-31 14:13:33 UTC, hard stop 11-02 18:00 UTC; writes ONLY
  in development blocks, drops every message while the calendar block is sealed; ~12 MB/h gz): feed `btc5m_clob_raw` =
  Polymarket CLOB market channel for the BTC 5m windows only, one connection per window, UNTHROTTLED (every Up-token
  price change within 3 c of the touch with server ms and the post-change touch, every last trade with tx hash, book
  snapshots at most every 2 s); feed `btc5m_venues` = sized top of book coalesced to 20 ms per symbol for Binance USD-M
  bookTicker (every update incl. size-only), Binance spot bookTicker, Bybit linear orderbook.1, OKX bbo-tbt swaps,
  Hyperliquid bbo, plus OKX swap / Hyperliquid / Coinbase (ticker) trades, BTC and ETH, with exchange ms; feed
  `btc5m_rtds_stream` = RTDS kept open with an application PING every 5 s (it still only sends the initial 60-s snapshot:
  4 messages in 40 s, no streaming updates, so the arrival time of Chainlink values remains unobservable this way).
- `code/fetch_rest6.py`: time-bounded REST trades at exchange ms strictly inside the development block (asserts every
  30 s step is development): Binance USD-M and spot BTCUSDT/ETHUSDT aggTrades, Coinbase BTC-USD/ETH-USD, OKX
  BTC-USDT-SWAP/ETH-USDT-SWAP history-trades (type 2), 10-31 12:00-15:1x; `post/rest6_*.parquet`.
- On-chain cluster fills 10-31 12:00-15:1x (`fetch_dev_post.py`) and the calldata of every live cluster taker tx
  (`post/cd6_live.parquet`, decoded fields only).
- data-api activity rows TAKER_REBATE / MAKER_REBATE / REFERRAL_REWARD for GF, XM, DS and W4, 2026-06-01..H
  (`code/rebate6.py`, results_rebate_iter6.json). pmxt archive (X18): `curl https://archive.pmxt.dev/` and
  `/docs/v2-data-overview` from this laptop at 14:15 UTC: connection timed out after 15 s (the panel saw refused
  connections at 13:50-14:00); not used, keyed pmxt API not used.

Findings (iteration 6; live numbers are development block 10-31 13:00-15:0x, a Saturday; historical numbers VALIDATE):
1. ECONOMICS (X17, B6 corrected; `rebate6.py`): data-api /activity has a TAKER_REBATE type (polyrea's ACTIVITY_TYPES
   omits it; passing types=("TAKER_REBATE",) to PolymarketData.activity works). Every wallet gets one row a day equal to
   exactly 0.500 of its previous UTC day's BTC 5m taker fees (13 of 13 days 10-10..10-22 for GF, XM and DS: min = max =
   0.500). History (all development, rows before H): taker rebates XM $201.1k since 06-20, DS $111.7k since 07-19, GF
   $63.4k since 07-20, W4 0xd84403ef $36.5k since 07-24; maker rebates XM $29.8k, DS $13.5k, GF $7.3k, W4 $5.1k. Rows paid
   10-17..10-22 (fees of 10-16..10-21): taker rebates DS $15.2k, GF $8.4k, XM $2.0k (W4 $3.7k); maker rebates $2.6k. VALIDATE
   on-chain taker fees $61.6k -> rebate $30.8k against trading PnL after fees +$4.4k (t = 0.50). So ~85% of the cluster's
   VALIDATE income is the taker rebate, a fixed function of fee volume; the B6 entry of iteration 5 ("the taker-fee rebate
   is not an activity row") was wrong.
2. PNL-CORRELATION CEILING (X17): per-window VALIDATE PnL (1,904 windows) of the operator's own wallets correlates DS-GF
   0.198, DS-XM 0.002, GF-XM 0.145 (Spearman 0.278 / 0.023 / 0.167); each wallet against the rest of the cluster 0.10-0.24
   (Spearman 0.13-0.34); net positions correlate 0.00-0.21. The same engine on the same triggers does not reproduce its
   own sibling's per-window PnL beyond ~0.2-0.3: per-window PnL is an execution lottery on two-sided volume. An
   executable replica that does not see the wallet's own fills is a fourth sibling; the 0.5 target is then out of reach
   by construction (the frozen rule's 0.18 is at the sibling level).
3. PRICE FROM CALLDATA (X25 = panel-mechanics proposal 3; `calldata_touch6.py`, results_calldata_touch_iter6.json): for
   11,382 cluster taker orders of the 11 sampled development hours, the limit equals the best (lowest) effective ask of
   the maker orders the same match consumed in 83.1% and is within one tick in **94.8%** (DS 96.1%, GF 92.5%, XM 93.9%;
   makers are 93% complementary BUYs, i.e. mints); 92.7% consume a single level; in 11.4% the limit is above every
   consumed level (more often for the large size: 100-share orders 23%, equal-to-touch 58%): the bot does sometimes post
   its pre-signed order one or more cents above the touch. This is the trivial "touch" anchor measured on the match
   itself (not a PIT forecast of the touch); it is now `price.calldata_touch` in `final_rule.evaluate` and becomes
   `price_within_tick` wherever no live book covers the period (h1/h2).
4. LIVE TRIGGER AT EXCHANGE MS (X20, `live6.py`, results_live6_iter6.json; 13:00-14:22, 633 taker matches, 486 events):
   the side agrees with the move of a fast venue over the reaction window [m - 600, m - 100) ms (m = matching-engine ms):
   Binance USD-M ETH 98.3% when it moved (> 0.1 bp; 19% of matches vs 6% at placebo times), Binance spot ETH 97.6%,
   Binance spot BTC 93.3%, Binance USD-M BTC 91.7%, Coinbase BTC 78% (placebo agreement 32-56%). Over [m - 300, m):
   97-98% for the Binance series. Composite of 7 trade feeds (Binance futures and spot BTC/ETH, Coinbase BTC/ETH, OKX
   BTC swap) over the last 1 s: a move before 54.7% of matches, vote agreement 79.6%; the remaining 45% are QUIET on every
   trade feed (iteration 5's 69% used only two feeds). Chainlink RTDS 1-s values under any assumed availability lag 0-3 s:
   agreement 46-51% (placebo 49-55%): E7 rejected at every lag.
5. QUOTES (X19/X24 recorder; 70 covered matches by 14:22, rerun at the end below): when a venue's microprice moved in
   [m - 600, m - 100) ms the side agreed 93-100% (Bybit BTC, Binance futures ETH, Hyperliquid ETH, OKX ETH), but in the
   quiet matches the quote feeds barely moved either (0-12%).
6. PREY MAKERS (X23, `prey6.py`, results_prey_iter6.json; calldata of all 633 live taker txs): age of the best consumed
   maker order (match ms minus its signing ms): median 2.0 s (quiet 1.65 s, moving 2.35 s), under 500 ms 23% (quiet 26%,
   moving 21%); 88% are complementary BUYs. Fresh quotes are not specific to quiet matches: E3 as "lift a just-posted
   quote" explains at most a quarter of them. One maker, 0xec10d230..., is 11% of the bot's quiet-match counterparties
   against 3% in moving matches (a slow maker the bot picks off when nothing moves: open lead).
7. VALUE vs FADE in quiet matches (X13/X21, `value6.py`, results_value_iter6.json): with the market's own implied
   d = Phi^-1(mid) and delta = phi(d) / (sigma sqrt(tau)), the value gap delta x dS - dPM (BTC move minus the Polymarket
   Up-mid move over 5-10 s, sigma fitted on the first half) predicts the quiet-match side at 61-67% on the second half
   (BTC futures 10 s 67.3%, Binance spot 65.7%); fading the Polymarket mid move over 5-10 s gives 60-61%; BTC momentum over
   3-10 s 47-49%. Older moves (1-3 s before, > 0.1 bp, then quiet) are faded: side agrees 23-46% (n = 44 for BTC futures).
   Historically (VALIDATE quiet one-sided seconds, n = 18,907) the older ETH move agrees 53% (no fade), so the fade is
   not replicated at block-second resolution; the side model reaches 64% there. Verdict: the quiet side carries a weak
   value signal (E4 partially supported, far from 80%).
8. FAN-OUT (X16, `fanout6.py`, results_fanout_iter6.json): 633 live taker matches form 486 fire events (same window and
   outcome, < 300 ms apart): size 1: 367, 2: 99, 3+: 20; DS first in 80%; DS -> GF lag median 69 ms (p10 7, p90 246),
   GF -> XM 15 ms; participation does not rise with the trigger strength on this Saturday (DS 79-86%, GF 31-40%, XM
   3-12% in every bin of the largest Binance move): no per-wallet threshold structure visible live (n small above 1 bp).
9. PER-WALLET SIDE (X14 partial): XM is one-sided in 24.3% of its VALIDATE windows, so the brief's side condition likely
   applies to XM. On XM's one-sided seconds the pooled side model is 80.6% on the 6,716 seconds the pooled cluster was
   one-sided, but 4,033 XM seconds have a sibling on the other outcome; presence-argmax over all 10,749 XM seconds 72.7%
   (GF 75.2%, DS 72.4%): XM's own side decisions are not decoded where its siblings disagree.
10. TIME STOP (X26 partial): VALIDATE block-second AUC by window time (it4b scores): 0.80 at 0-120 s, 0.85 at 120-180,
    0.91 at 180-240, 0.96-0.98 at 240-270, 0.98-0.99 after; the 240 -> 270 s stop change costs nothing visible late in the
    window; the presence deficit is early in the window.
11. SUBMISSIONS (X15, `subs6.py`, results_subs_iter6.json; unthrottled book 14:13-14:22): 2,756 size increments of exactly
    a bot size (30/50/60/100/200) at a price that was the bought outcome's ask within the previous 300 ms, ~25 times the
    cluster's fills in the same minutes; 20% link to a cluster fill (same window, outcome, price, -2..+30 s), 81% of the
    cluster's resting orders are preceded by such an insertion. Bot sizes are common among other inserters (and W4), and
    unfilled orders never reach the chain, so the book cannot attribute unfilled submissions to the cluster: ruled out
    as a decoder of the cluster's lost races (identity is not observable), kept as a description of the race crowd.
12. QUIET MATCHES, PROFILE (live 13:00-14:22): rel median 202 s (moving 97 s); share quiet by window third 24% (0-100 s),
    38% (100-200 s), 69% (200-300 s); 59% come within 2 s of a previous cluster match in the same window, itself quiet in
    65-76% (quiet comes in bursts); sub-tick moves (any change, below 0.02 bp) of the fast venues over [m - 600, m - 100)
    agree 62-68% in quiet matches (Binance USD-M ETH 68.0%, BTC 62.9%, OKX BTC 63.5%; placebo 41-51%); a delta-scaled
    (fair-value unit) threshold is not better than a bp threshold; quiet late matches buy the LESS-held outcome only 43%
    (no balancing) and the favourite 42%. Settlement-TWAP lock-in (last minute: observed partial Chainlink average minus
    the current value, n = 83-85) agrees 51-57% (lag 1 s 56.6%; permutation 97.5% = 0.61): not significant.
13. Historically (VALIDATE, block seconds): the late-window AUC is high (0.96-0.98 at rel 240-270 s); the deficit is early
    in the window (0.80 at 0-120 s), where moving matches dominate live. Decision times are blurred by the block clock
    (match-to-block 1.3-3.2 s), which is why the live reaction window [m - 600, m - 100) ms cannot be used directly.

FINAL LIVE NUMBERS of iteration 6 (supersede findings 4-8 where they differ; 10-31 13:00-14:47 development block,
782 cluster taker matches = DS 521 / GF 222 / XM 39, 606 fire events; quotes and raw book cover 14:13-14:47, 219 matches):
- Trade feeds at exchange ms (8: Binance USD-M BTC/ETH, Binance spot BTC/ETH, Coinbase BTC/ETH, OKX swap BTC/ETH), move
  over the reaction window [m - 600, m - 100) ms (> 0.1 bp), share of matches moved / side agreement (placebo moved /
  agreement): Binance USD-M ETH 23.9% / 94.1% (5.4% / 52%), OKX ETH 21.2% / 94.0% (7.0% / 56%), Binance spot BTC 11.8% /
  93.5%, Binance USD-M BTC 10.5% / 93.9%, OKX BTC 7.9% / 90.3%, Binance spot ETH 16.5% / 89.9%, Coinbase BTC 15.6% / 78.7%,
  Coinbase ETH 15.2% / 79.8%. Largest move of the six Binance/OKX series: 50.1% of matches moved, 86.5% agreement.
  Composite over the last 1 s: 63.4% moved, vote 80.6%; QUIET on all eight feeds: 36.6% of matches.
- Quote feeds (microprice, [m - 600, m - 100)): ETH quotes moved before 25-36% of matches with 87-94% agreement (Binance
  USD-M 92.4%, Hyperliquid 94.4%, OKX 90.0%, Bybit 89.0%), BTC quotes 7-12% with 86-95%; before the 67 covered QUIET
  matches they moved in 0-12% (Bybit ETH 12%, 50% agreement): sized top of book on five venues does NOT explain the quiet
  matches (E2 rejected for them at this n).
- Unthrottled Polymarket book (end 20 ms before the match): over the last 300 ms the bought outcome's ask rose in 36%
  (quiet 42%) and its bid rose in 37% (quiet 40%) vs 9% / 9% at placebo times; the FIRST touch change of the bought
  outcome in the last second is: ask up 28% (placebo 16%), bid down 22% (12%), both 15% (13%), cheaper ask 5% (3%), bid up
  3% (2%), none 27% (56%); the quiet matches show the same mix. Matches sit inside Polymarket book activity in both
  directions (the crowd lifting o, or the other outcome being lifted), not after a specific maker event.
- Prey makers (782 txs): best consumed quote age median 1.9 s quiet vs 2.5 s moving, < 500 ms 26% vs 21%; 0xec10d230
  9% of quiet vs 5% of moving counterparties.
- Value / fade in quiet matches (286; second-half test): value gap over 5 s 59-68% (Binance USD-M ETH 67.9%, BTC 66.4%,
  Coinbase 66.4%), fade of the Polymarket mid over 3-10 s 60-61%, BTC momentum over 3-10 s 40-46% (i.e. mild fade).
- Fan-out: 606 events, size 1 in 76%; DS first 80%; DS -> GF median 54 ms; participation flat in trigger strength.

Status after iteration 6: target not reached (side, PnL correlation). Primary metric unchanged at 0.9132 (all seconds;
block seconds 0.8747) for iterations 5 and 6, so iteration 7 must pivot paradigm (see Next). What is decoded now: the
order factory, the price (touch, 95% from calldata), the exit, the economics (85% of income is the 50% taker rebate), and
the trigger of the moving half of the matches (a fast-venue move in the 100-600 ms before the match, ETH first, ~94%).
What is not: the trigger and side of the quiet third to half of the matches (late in the window, inside Polymarket book
activity, no move on 8 trade and 5 quote feeds, side 60-68% from weak value / fade / sub-tick signals), XM's own side,
and any executable PnL correlation above the sibling level (0.00-0.20).

Live lab at the end of iteration 6: rec_lab6.py (feeds btc5m_clob_raw, btc5m_venues, btc5m_rtds_stream) ran 14:13-15:0x;
it is replaced by the same code with a disk cap (REC6_SUFFIX=2 -> feeds btc5m_clob_raw2, btc5m_venues2,
btc5m_rtds_stream2; near-touch window 2 c, venue quotes coalesced to 30 ms, cap 250 MB, development blocks only, hard
stop 11-02 18:00 UTC). Read both feed names in iteration 7 (the old hour file may end in a truncated gzip member: use
live_lab.recs, which keeps what was read).

Polyrea bugs / gotchas (iteration 6): polyrea/adapters/polymarket.py ACTIVITY_TYPES omits TAKER_REBATE (and
REFERRAL_REWARD, DEPOSIT, WITHDRAWAL, MIGRATION); activity(types=("TAKER_REBATE",)) works because the tuple is passed
through, but any caller relying on the default list misses ~85% of this cluster's income. tools/live.py: the shared
recorder's 10-31 12:00 files (clob_crypto, rtds) raise zlib.error after the 12:18 restart (iter_live does not catch it).
The Bash tool blocks chained `sleep`; Git Bash `date` shows UTC with `-u`.

## Next (iteration 7: pivot required)

1. PARADIGM: a decision-level hazard model at matching-engine ms on the live unit (D1/D2): P(cluster match in the next
   100 ms | fast-venue moves at lags 100-600 ms (ETH first), Polymarket touch and its last changes (unthrottled feed),
   time left, value gap), trained on the development blocks 10-31 12-18 and 11-01 06-12, validated on 11-01 18-24 and
   11-02 00-06; then a block-second version for h1/h2. This is the rule the future sealed blocks can be examined with
   (shared recorder + Binance/OKX archives).
2. X21: a calibrated LEVEL fair value (strike = Chainlink TWAP-60 before the open, vol fitted, ETH-led composite) fitted by
   maximum likelihood of the side in quiet matches; test a hazard step in (FV - ask)/p(1-p).
3. X14 / XM: per-wallet side and presence models (post-switch BUILD 10-13 14:10..10-16); XM's seconds where a sibling
   bought the other outcome.
4. X23 historical: full-market calldata for ~40 VALIDATE windows, quote functions of the top makers (0xec10d230 first).
5. X22 with co-racers' signing ms; X5 (remove W4 from the market features); X26 change points; X27 collateral; A4b
   Kalshi; C4b announcements; X7 funding/liquidations/options; X9; X10; X12.

Addendum (X14, per-wallet side, `side_wallet6.py`, results_side_wallet_iter6_XM.json): rows = VALIDATE seconds where XM
bought exactly one outcome (10,749; 62.5% of them pooled one-sided). Frozen pooled side model: 72.6% (80.7% where the
pooled cluster was one-sided, 59.1% where a sibling bought the other outcome; XM taker seconds 79.1%; halves 73.2 / 72.1);
an XM-only model trained on XM's BUILD seconds (45,982): 72.4%, no better. The seconds where siblings bought opposite
outcomes are mostly a fill-timing artefact (a resting remainder of an earlier decision filling while a sibling takes the
other side), so the side condition for XM should be read per decision (taker seconds 79.1%), not per fill-second.
(The post-switch-only XM model found 0 BUILD rows after 10-13 14:10 in the side pipeline: to check in iteration 7.)
Addendum (X21, calibrated LEVEL fair value, `levelfv6.py`, results_levelfv_iter6.json; 781 live matches, 689 placebo
instants): FV_Up = P(settlement TWAP-60 > strike) with strike = Chainlink RTDS mean over [start - 60, start), S = Binance
USD-M BTC x Chainlink basis, TWAP variance (tau - 40) s before the last minute and the partial-average formula inside it,
sigma = k x realized 1-s vol (k = 1.3 chosen at placebo instants): calibration median |FV - mid| = 4.8 c (the panel's
1.5 c bar is NOT met), and the side rule argmax(FV_o - ask_o) is at chance (50.5%; quiet 47.9%; last minute 42.1%). With a
4.8-c calibration error a ~1-c edge cannot be seen: inconclusive, not a rejection of E4. The market prices off something
this FV lacks (strike source, vol term structure, or the fast composite level).

KEY FINDING OF ITERATION 6 (late; X24 strong form, `results_micro_iter6.json`): the QUIET matches are not trigger-less.
(a) Anticipation: in quiet matches the fast venues move in the bot's direction AFTER the match: Binance USD-M BTC over
    (m, m + 1 s] 92.3% (n = 13), (m + 1, m + 3 s] 78.1% (n = 32); OKX ETH 75.9% / 75.4%; Coinbase BTC 88.0% (n = 25); i.e. the
    bot reacts to the very start of a move. Clock check: minimum (receive - stamp) is -1,224 ms for Polymarket server ms
    and -1,107..-1,184 ms for Binance / Bybit / OKX / Coinbase exchange ms; with TCP RTTs of 79 ms (Polymarket CloudFront edge),
    347 ms (Binance Tokyo), 68-77 ms (OKX, Bybit, Coinbase edges) the exchange clocks and Polymarket's server clock agree
    within roughly +-100 ms, so neither the reaction window nor the 1-3 s anticipation is a clock artefact.
(b) Microprice: the sized top of book recorded by rec_lab6.py shows it. Over [m - 600, m - 100) ms the microprice
    ((bid x ask size + ask x bid size) / (bid size + ask size)) of the ETH perps moves by more than 0.002 bp before most
    quiet matches, in the bot's direction: Binance USD-M ETH 85.3% (34 of 61 covered quiet matches), OKX ETH 82.8% (29/61),
    Bybit ETH 80.6% (31/63), Bybit BTC 89.5% (19/63); placebo 35-56%. Vote of the ten quote series (Binance USD-M and spot,
    Bybit, OKX, Hyperliquid; BTC and ETH): covers 90% of the 204 covered matches with 86.4% side agreement (quiet 79% covered
    at 84.0%, moving 95% at 87.3%; placebo 46%); sum of microprice moves (ETH in BTC units) > 0.01 bp: 81% covered at 89.8%
    (quiet 62% at 82.1%, moving 90% at 92.1%). The level of the touch imbalance is not informative in quiet matches
    (44-56%); its CHANGE (queue depletion moving the microprice) is. This is the trigger the trade-only and price-only
    studies could not see (rec_binance_fut.py dropped size-only updates; the panel's critique was right).
(c) So the decoded trigger is: "a tick-level microprice move of the BTC/ETH perps (mostly ETH; Binance, OKX, Bybit) in the
    100-600 ms before the match -> buy that direction at the touch", ~84-90% of live taker decisions, both regimes; n = 204
    on a Saturday afternoon (34 minutes): to be replicated on the next development blocks (rec_lab6.py ...2 feeds).
(d) Historical route (h1/h2 have no live quotes): Bybit publishes orderbook.200 archives for ETHUSDT as for BTCUSDT;
    started fetching all 14 development days (bybit_ob.py with BYBIT_SYM=ETHUSDT -> bybit_ob/linear_ETHUSDT_<day0>.parquet;
    bybit_ob.py's BTC price-range assert made symbol-aware) and wrote side_book_eth6.py (side model + ETH book features).
(e) OUT-OF-SAMPLE REPLICATION (`micro_rep6.py`, frozen definitions, later interval 14:55-15:10 recorded by the capped v2
    recorder btc5m_venues2, results_micro_rep_iter6_1793458500.json): 162 taker matches; the microprice vote covers 90.7%
    with 83.0% side agreement (quiet 71% covered at 77.3%, n = 22 voted; moving 95% at 84.0%); placebo covers 81% at 55.3%.
    Same code on the first interval 14:15-14:47 (results_micro_rep_iter6_1793456100.json): 163 matches, 92.0% at 86.7%
    (quiet 87.1%), placebo 48.2%. The trigger replicates on unseen live data.
(f) HISTORICAL ETH BOOK (`side_book_eth6.py`, results_side_book_eth_iter6.json): Bybit ETHUSDT linear orderbook.200 archive
    for all 14 development days (bybit_ob.py with BYBIT_SYM=ETHUSDT, 100-ms buckets, ~11 MB/day; ~170-235 MB streamed per
    day, nothing raw stored), the iteration-5 book features renamed BE_* added to the frozen side model's features:
    VALIDATE one-sided seconds 77.17% vs 76.66% (it5 frozen and a same-rows control without ETH both 76.66%), McNemar
    p = 1.3e-9; taker seconds 80.26% vs 79.36%; halves 76.5% / 77.8%; ETH book features 14% of the gain (BE_mid3,
    BE_mid_d21, BE_imb_avg1 on top). With only 2 BUILD days of ETH book (first try) the gain over its control was +0.5
    points as well. Historically the block clock blurs the decision by +-1 s, so the sub-second microprice tick that gives
    86% live cannot be aligned; the 100-ms book at the block-second horizon adds +0.5 points. NOT yet wired into
    final_rule.py (evaluate would need to stream the ETH archive for the exam days; book_feats.stream_day has a BTC URL and
    a BTC price-range check): first step of iteration 7, together with the live microprice rule for the future blocks.

### Iteration 7 (2026-10-31 15:57 UTC start, local Windows laptop; PIVOT: the target becomes order overlap, size and exam inputs)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (tools/sealed.py): released lots
none; development after H = 10-31 00-06 and 12-18 UTC; 10-31 18-24 and 11-01 00-06 are SEALED. The shared recorder runs
(pid 27184). My rec_lab6 v2 (pid 14304, development blocks only) runs. Other agents' feeds (dm_*, dx_*) were NOT read.

Pivot (iterations 5 and 6 both 0.9132 on the primary metric): from fill presence to (a) the PnL target as an
order-overlap problem with the size decision as its own unit (X28/X29), (b) a decision-level hazard at matching-engine
ms on the live unit (D2/X31), (c) recording the decoded rule's inputs through the sealed blocks (X34).

Competing explanations at the start of iteration 7 (what separates them; verdict in the findings):
- E1 rebate harvester with latency-arb timing: income = 50% taker rebate; trades are near break-even latency takes on
  perp microprice ticks. Separates: hazard steps up with the tick toward o; trading PnL ~ 0 before rebates.
- E2 bot-specific fair value (different vol or lag): buys o when ask_o < FV_bot,o - m. Signature: underdog tilt that grows
  with |p - 0.5| and persists at static prices (vol/shape) or appears only after moves (lag).
- E3 event-level sizing: the large size is chosen on strong events and shared across wallets. Separates: large-size
  co-occurrence across wallets above a within-wallet permutation null; P(large | trigger strength) AUC >= 0.75.
- E4 size is a per-wallet dice (dispatcher ratio): co-occurrence at the null; P(large | features) ~ 0.5.
- E5 ladder/queue artefacts (burst blocking, copy budget) drive part of the timing and the tilt.
- E6 remainder lifecycle: GTC remainder with a short TTL vs fill-and-kill vs resting until filled.
- E7 the microprice tick is a correlate of an unrecorded faster input: side agreement rises monotonically through the
  match; hazard flat in tick size.
- E8 the PnL is replicable only through order overlap (split-half ~0), so a replica needs the same orders and sizes.

Data added (iteration 7):
- EXAM-INPUT RECORDER (X34; `code/rec_exam7.py`, pid 32576, started 10-31 16:03:48 UTC, hard stop 11-02 06:00 UTC, cap
  300 MB over everything it writes; status `.cache/re/btc5m-bot/rec_exam7.status`): writes in EVERY calendar block through
  tools/live.py Writer. Sealed blocks are filed into .cache/live/sealed/ by the Writer and are never read, listed or
  counted by me; the status keeps only the compressed byte position of the process's own file handles (one rounded
  total, ~7 MB/h) and record counts of development blocks. Feeds: `btc5m_xclob` (Polymarket BTC 5m: Up-token price changes
  AT the touch with the post-change touch, every last trade with server ms and tx hash, 10-level snapshots every 10 s)
  and `btc5m_xven` (Binance USD-M and spot bookTicker, OKX bbo-tbt; BTC and ETH; sized top of book coalesced to 30 ms).
  The same subset is written in development and sealed blocks, so the frozen live rule is developed on exactly the
  inputs the examiner gets. Sealed blocks covered: 10-31 18-24, 11-01 00-06, 11-01 12-18 (10-31 06-12 is lost).
- All 2,016 VALIDATE taker tapes re-read from the shared HTTP cache (0.05 s per window; kept only in the session
  scratchpad, 267 MB, deleted at the end, because .cache/re/btc5m-bot is at 1.4 GB of its 1.5 GB).
- On-chain cluster fills 10-31 14:50-16:26 (`post/own_1793458200_1793462700.parquet`, `post/own_1793462640_1793464380.parquet`).

Findings (iteration 7):
1. PNL = ORDER OVERLAP (X28, `pnl7.py`, results/pnl7.json; VALIDATE 2,016 windows, 235,525 fills, 175,831 orders):
   per-window PnL vs net x outcome r = 0.88-0.93. Split-half of a wallet's own orders (order-hash parity): DS -0.03,
   GF 0.14, XM -0.03, pool 0.16 (both VALIDATE halves alike): no window-level direction, the PnL is a sum of order-level
   bets. Big orders (>= 90 filled shares; DS 1.5%, GF 8.4%, XM 10.3% of orders) vs total: DS 0.35, GF 0.85, XM 0.73,
   pool 0.70; across siblings 0.47-0.55 (totals 0.00-0.20). ORACLE replays of the wallet's own orders: at a fixed 30 shares
   DS 0.77, GF 0.40, XM 0.54, pool 0.41 / 0.49 (Spearman); at the size class (30 / 100) DS 0.88, GF 0.91, XM 0.89, pool
   0.88 / 0.87; taker orders only at true size 0.85-0.93. The panel's critique holds: siblings are not a ceiling; the size
   carries the variance.
2. STRICT-FILL ORACLE (X28 step 3, `strict7.py`, results/strict7.json; 142,638 taker orders): the wallet's OWN taker
   decisions (window, outcome, block second s of the first fill, its highest fill price as the limit) through the frozen
   strict-fill model (fills only against other traders' taker BUY prints on o at <= limit, at the print price):

   | prints window | size | fill share | DS | GF | XM | pool (Pearson / Spearman) |
   |---|---|---|---|---|---|---|
   | [s+1, s+3] (latency >= 2 s, frozen) | true | 0.37 | 0.50 | 0.48 | 0.49 | 0.40 / 0.39 |
   | [s+1, s+3] | 30 | 0.36 | 0.43 | 0.17 | 0.30 | 0.14 / 0.21 |
   | [s-1, s+1] (same block window) | true | 0.70 | 0.75 | 0.72 | 0.75 | 0.68 / 0.66 |
   | [s-1, s+1] | 30 | 0.70 | 0.62 | 0.26 | 0.43 | 0.26 / 0.31 |
   | [s, s+5] | true | 0.74 | 0.75 | 0.75 | 0.76 | 0.70 / 0.69 |

   So the frozen replica's 0.18 equals the ceiling of its own design (30 shares and >= 2 s latency: pool 0.14 / 0.21 with
   PERFECT decisions). Under the >= 2 s strict-fill model no rule can reach 0.5 pooled even with the wallet's own
   decisions and sizes (0.40). At the decoded latency (same block window) and the right size class the ceiling is
   0.66-0.76; with 30-share orders it is 0.26-0.31 pooled. PRE-REGISTERED now, before any new replica is scored: the PnL
   correlation is reported (a) under the brief's held-out-return convention (latency >= 2 s, prints in [s+1, s+3]) and
   (b) at the decoded latency (decision at s from information <= s-1, fills against other takers' prints in [s, s+2]);
   (b) counts toward the target only if the examiner accepts the decoded latency for the correlation condition.
3. SIZE (X29, `size7.py`, results/size7.json; calldata sample, SIGNED sizes): menus per hour as in iteration 5; large share
   DS 7.9%, GF 32.9%, XM 13.0%. Co-occurrence: 6,622 pairs of taker-first orders of two wallets on the same token within
   1 s; both-large rate = 1.68 x independence against a within-(wallet, hour) permutation null of 0.75 (97.5% 0.84;
   p = 0.0005, 2,000 draws); P(partner large | large) 0.379 vs 0.182 given small: the large size is partly an EVENT-level
   decision (E3 supported, E4 rejected). But P(large | point-in-time features) is not predictable at the block clock:
   logistic BUILD -> VALIDATE AUC 0.70, of which wallet identity alone gives 0.66; within wallet 0.44-0.59; single
   features: signed BTC move over the 2-4 s before 0.563, |move| 0.538, |p - 0.5| 0.483, rel 0.520; large share 13% with
   no BTC move vs 16-18% with one. Live (14:14-14:48, 173 taker matches with calldata, Saturday): only 3.5% large: too few.
4. TRIGGER vs CORRELATE (X31, `lag7.py`, results/lag7_*.json). LAG PROFILE of the ten-series microprice vote in 100-ms bins
   on 14:50-16:05 (695 taker matches, 610 covered): agreement 53-60% at m - 1.5..-0.8 s, 63% at m - 700, 69-70% at
   m - 600..-400, PEAK 75.3% / 74.4% at [m - 400, m - 200), 69% at [m - 200, m - 100), 64% at [m - 100, m), then 59%
   (m..m + 100), 52-56% after m + 100 ms and ~50% at m + 300..+1,000 (placebo 45-56% throughout). A trigger profile: the
   side information sits 200-500 ms BEFORE the match and is gone 100 ms after it (E7's monotonic rise is rejected in
   100-ms bins; the 1-3 s post-match continuation of iteration 6 was a coarser-window effect). HAZARD on a 100-ms grid of
   all covered window time (D2; 39,428 points; label = cluster match on o in [t + 100, t + 600)): P(match) by the signed
   ten-series move toward o over [t - 500, t): 2.3% (|move| < 0.02 bp), 2.2-2.5% for moves AGAINST o, 5.1% (0.02-0.1 bp
   toward), 5.6% (0.1-0.5), 8.7% (> 0.5 bp); first interval 14:14-14:48 (19,000 points): 1.0%, 0.7-1.9% against, 3.1%,
   4.7%, 9.4%. AUC of the signed move 0.643 / 0.728 vs market activity (other trades in the last 1 s) 0.692 / 0.607;
   activity + move (half-split logistic) 0.717 vs 0.695 and 0.677 vs 0.600: the tick adds +0.02 / +0.08 AUC over activity
   at the decision level. The hazard steps up with the tick toward o: the microprice tick is a trigger (the signature the
   panel named for "trigger"), with a low base hazard (necessary, not sufficient).
5. LIVE SIDE, THIRD OUT-OF-SAMPLE INTERVAL (frozen vote, `final_rule._live_vote`, 10-31 16:04-16:25, 273 taker matches,
   all with match ms): the ten-series vote (v2 feed) covers 84.6% at 75.3% agreement (placebo 73% / 50%); the six-series
   vote of the exam-input feeds (Binance USD-M + spot, OKX) covers 61.5% at 80.4% (DS 81.8%, GF 75.5%, XM 8/9; placebo 41% /
   52.7%), identical on the v2 feed (60.4% / 80.6%): the exam recorder reproduces the lab recorder. Agreement of the
   ten-series vote by interval: 86.4% (14:15-14:47), 83.0% (14:55-15:10), 75.3% (16:04-16:25): it decays; the 80% side bar
   is not reliably met per decision.
6. REMAINDERS (X35, `remainder7.py`, results/remainder7.json; calldata sample, 10,967 taker-first orders): 59.4% leave a
   remainder (median 60% of the size; 30-share 49%, 100-share 84%, 200-share 91%); only 19% of remainders ever fill
   again, and then within 0 s (median; p75 2 s, p90 3 s) of the taker fill; upper bound of the removal (the first other
   taker's BUY print on o at <= limit - 1 c after the last fill, which a resting bid would have matched): median 5 s
   (p25 2 s, p75 15 s, p90 42 s), <= 3 s in 42%, <= 10 s in 69% (485 of 3,298 censored). Decoded: GTC remainders that
   rest at most a few seconds (refills <= 3 s) and are cancelled (TTL ~2-5 s), not left to rest, and not fill-and-kill
   (19% get maker fills). Exit component: maker fills are echoes of decisions <= ~3 s old.
7. UNDERDOG TILT (X30 steps 1-2, `tilt7.py`, results/tilt7.json; 142,638 cluster taker orders, 1.97 M other BUY prints):
   at |p - 0.5| in [0.3, 0.4) the cluster buys the underdog in 58.3% of small orders and 68.7% of big ones, other takers
   in 34.8%; near 0.5 (0.02-0.1) 49.2% vs 47.6%. At STATIC prices (Up price moved < 2 c over the previous 30 s) the tilt
   stays (57.0%, n = 1,881; others 36.5%) and equals the one after moves (58.5%): not a lag or fade effect; a different
   vol or shape of the bot's FV (wider vol, FV closer to 0.5 than the market) or a ladder/liquidity artefact. Late
   (240-300 s) small orders near 0.5 lean to the favourite (44.5%). The revealed-preference fit (step 3) is not done.

Code changes: `final_rule.py` gains `_live_vote` (decision-level side on the exam-input feeds; frozen window
[m - 600, m - 100) ms, tick 0.002 bp, ETH scale 1.235; reported as `side_accuracy_live_decision`) and `_pnl_overlap`
(diagnostics from the wallet's own fills: split-half, big orders, oracle 30-share and size-class ceilings; never counted
toward the target). Everything else in the frozen rule is unchanged.

Status after iteration 7: target not reached. Primary metric unchanged (0.9132 all seconds; block seconds 0.8747 vs
0.8193). What changed: the PnL condition now has a quantitative account (an order-overlap problem; the >= 2 s strict-fill
model caps even the wallet's own decisions at 0.40 pooled; the size class is required; the large size is event-level but
not predictable at the block clock); the microprice trigger passed the trigger-vs-correlate test (lag peak 200-500 ms
before the match, hazard stepping with the tick); remainders are decoded (cancelled within seconds); the decoded rule's
inputs are now recorded in sealed blocks for a future-block exam.

## Next (iteration 8)

1. Executable size-aware replica at the decoded latency (pre-registered convention (b)): block-second presence + side
   model + size class; score on VALIDATE against the oracle ceilings of finding 2 (0.66-0.70 pooled).
2. Size decoder live: touch depth at the match (exam feed snapshots + touch changes) and microprice strength vs the
   signed size on weekday blocks (11-02 00-06 and 12-18): needs >= 100 large orders.
3. Hazard model (D2) on the exam-input feeds: a frozen decision-level presence rule for the future-block exam, with the
   market-activity baseline at the same unit; per-wallet side (XM) per decision.
4. X30 step 3 (revealed-preference FV with a free vol multiplier and lag) and X32 (burst-time dips per wallet).
5. Open from before: A4b Kalshi, C4b, X5, X7, X9, X10 (authenticated GitHub search unavailable: no token), X12, X14,
   X21-X23, X26, X27, X33.

Addendum, iteration 7 (late findings; supersede the Next list above where they differ):
8. EXECUTABLE REPLICA, first version (X28 step 4, `replica7.py`, results/replica7.json; frozen it4b cell scores, presence
   per outcome >= 0.30 -> BUY at the last implied ask; one open order per window and outcome): convention (a) (prints
   [s+1, s+3], busy 3 s) 30 shares pool 0.10 / 0.11, presence-weighted size (100 x p) 0.12 / 0.11; convention (b) (prints
   [s, s+2], busy 2 s) 30 shares 0.16 / 0.14, presence-weighted 0.18 / 0.16 (DS 0.19, GF 0.12, XM -0.01; $1.04M bought,
   +0.5% before rebates). Far below the oracle ceilings of finding 2 (0.26-0.31 at 30 shares, 0.66-0.70 at true size):
   the block-second decisions do not overlap the wallet's orders enough, and the size class is missing.
9. BLOCK-CLOCK LIMIT PER WALLET (X38, `clock7.py`, results/clock7.json): the same ten-series vote on the same live taker
   matches at (i) the matching-engine ms, (ii) block ts - 2.0 s (the historical decision clock), (iii) (ii) with a
   1.6-s window: 14:50-16:04 (695 matches) 79.3% (DS 80.3%, GF 78.0%, XM 72.4% of 29) -> 67.8% (DS 69.9%, GF 66.9%, XM
   51.5%) -> 70.6%; 16:04-16:25 (273) 75.3% -> 50.2% -> 60.1%. Placing the decision on the block clock costs 11-25 points
   for every wallet: the sub-second trigger cannot be aligned on h1/h2 (block median 2.17-2.25 s after the match). The
   historical side model (76.7%) already beats the vote at the block clock; the h1/h2 side ceiling is set by the clock.
10. XM SIDE IN DECISION UNITS (critique 5 of the panel, X14; `xm_unit7.py`, results/xm_unit7.json; frozen side model
    psb at the block second of each taker order's first fill, available where the pooled cluster was one-sided):
    XM per taker order 82.2% (coverage 55.7% of 8,761 orders); per XM one-sided window, first decision 85.8% (coverage
    72% of 332 windows with a taker order); GF 82.5% / 95.1%; DS 78.6% per order. PRE-REGISTERED unit for the side
    condition (iteration 7): per taker decision (order), and per one-sided window by its first taker decision; maker
    remainders belong to the decision that created them. The uncovered seconds (siblings on the other outcome in the
    same second) are the hard ones, so these are upper bounds until the side model is scored on every taker second.
11. BURST DIPS (X32 step 1, `burst7.py`, results/burst7.json; VALIDATE taker first fills per block second, 3-s rolling,
    relative to rel 150-168): around the +172.7 s burst all three wallets dip together (XM 0.74 at block rel 170-172,
    GF 0.84 at 169-175, DS 0.84-0.90 at 172-178) and spike together at block rel 184-186 (XM 1.53, GF 1.43, DS 1.16),
    then stay elevated (~1.1-1.3). The dip starts ~3 s BEFORE the burst (decisions ~2 s before the block) and is not
    staggered in the signing order (XM -> DS -> GF): one process-level pause or ladder swap, not each wallet's signer;
    the post-burst spike is a synchronized release ~10 s after signing. Weaker at +42 s (XM 0.85-0.87, spike 1.20 at
    rel 54) and at the next window's burst (rel 207-218: 0.80-0.92). A deterministic schedule term worth a few percent
    of decisions.
12. TIER BONUSES (X33 step 1, `tier7.py`, results/tier7.json; TAKER_REBATE rows before H): one-off round rows on each
    wallet's first days ($10 and $50: GF 07-20 / 07-26, DS 07-19 / 07-21, W4 07-24) and XM $1,500 on 07-15 (DS $170 on 08-11,
    $2,080 on 09-24, W4 $1,070 on 10-10 are round too): the wallets went through the tier level-up bonuses. The
    allocation test (10-13 shift vs tier crossings, 30-day volume vs $10M) is not done.
13. REACTION KERNEL PER SERIES (X41, `kernel7.py`, results/kernel7_1793458200.json; 695 taker matches 14:50-16:04, 50-ms
    bins over [m - 1000, m + 200), directional excess = moved share x (2 agree - 1) minus placebo): the earliest sharp
    peak is Binance USD-M BTC at [m - 300, m - 250) (a tick in 14.9% of matches, 87.9% toward the bought side, excess
    0.110, the largest), then Binance USD-M ETH at m - 300 (13.1%, 80.0%), OKX BTC m - 300 (5.7%, 94.3%), OKX ETH and Bybit
    ETH m - 350, Bybit BTC m - 400; Hyperliquid peaks later (ETH m - 200, BTC m - 100): it follows Binance and is a
    correlate. The primary quote stream is the Binance USD-M perps' bookTicker, with ~250-350 ms from the Binance event
    time to the Polymarket match (clocks agree within ~100 ms, iteration 6).
14. SIZE vs DEPTH (from finding 6): 84% of 100-share and 91% of 200-share taker orders leave a remainder (30-share 49%),
    so the large size is NOT chosen when the touch is deep enough to fill it; a depth-capped size rule is rejected
    historically.
15. THE LIVE SIDE DECAY IS A REGIME MIX (`vote7.py`, results/vote7.json; three intervals 14:14-14:48, 14:50-16:04,
    16:04-16:25): side agreement of the frozen ten-series vote by vote strength |vote| (net number of agreeing series) is
    STABLE: |vote| = 1: 65% / 66% / 64%; 2: 62% / 74% / 71%; 3: 100% (n = 14) / 76% / 84%; 5: 92% / 90% / 94%; >= 6: 95% /
    97% / 96%; by composite move > 0.5 bp 91% / 88% / 81%, < 0.01 bp 72% / 67% / 65%. What changed is the mix: weak votes
    (|vote| <= 2) were 22.5%, 42% and 56% of the voted matches. The decoded side rule is stable per decision strength; the
    80% bar holds in active markets and fails in quiet ones (the quiet decisions are the unexplained part of the side).
16. SIDE IN DECISION UNITS, FULL COVERAGE (`final_rule.evaluate` now reports `side.decision_units`: the frozen side model
    at the block second of EVERY taker order's first fill, plus the market-only baseline; three VALIDATE 2-h chunks
    10-22 22-24, 10-17 12-14, 10-19 18-20): pool 75.3% / 71.9% / 75.8% (market-only 60.1% / 60.9% / 58.3%); GF 79.2% /
    74.0% / 76.9%; DS 73.3% / 71.5% / 75.3%; XM 78.6% (103) / 65.9% (44) / 75.2% (105), i.e. ~75% over 252 orders; XM
    one-sided windows by first decision 3/6, 5/8, 2/4 (10/18). Finding 10's 82-86% were upper bounds of the covered subset
    (pooled one-sided seconds): with every decision scored, the side is ~72-79% per decision at the block clock, below the
    80% bar for every wallet. The live per-decision rule reaches 90-97% on strong votes (finding 15) but the block clock
    removes it (finding 9).
Disk: .cache/re/btc5m-bot was at 1.5 GB after the evaluate runs; three superseded files deleted (val_side_moves_iter4,
val_side_it4b, val_presence_book; 29 MB) -> 1.4 GB. The largest items are venues/ (523 MB), cells/ (360 MB) and bybit_ob/
(289 MB); a successor that needs room should drop cells/ of BUILD days only after checking that no training script is
needed again.
17. BINANCE-FIRST SIDE RULE (`bnfirst7.py`, results/bnfirst7.json): side = sign of the Binance USD-M microprice composite
    when it ticked, else the ten-series vote: 84.2% / 78.8% / 77.4% vs the vote 86.3% / 79.3% / 75.3% (chosen on the first
    two intervals: the vote stays frozen). When Binance USD-M ticked (83% / 53% / 51% of matches) it agrees 86% / 83% / 81%.
    In weak-vote matches no single recorded series is strongly predictive (Binance USD-M 62-77%, Bybit ETH 56-74%,
    Hyperliquid 36-76%): the weak-vote decisions are not explained by any recorded series.
18. PAY-UP ABOVE THE TOUCH (X42 first step, `payup7.py`, results/payup7.json; 11,382 taker orders of the calldata sample):
    the limit is 0 c above the best consumed ask in 83.2%, +1 c 11.5%, +2 c 2.9%, +3 c 1.2%, >= +4 c 1.2%. Pay-up >= 1 c by
    size: 30-share 11.6%, 50 19.7%, 60 14.9%, 100 41.7%, 200 37.5%; by wallet GF 27%, XM 16%, DS 12%; by window time 13-15%
    before 180 s, 21% at 180-240 s, 35% at 240-300 s; by |BTC 1-s move| 15.6% (none) -> 21% (> 2 bp). The large size and
    the higher ladder level go together (an "aggressive" decision: more size, a sweep of 2-5 levels), more often late in
    the window; its trigger is not visible at the block clock (as for the size, finding 3).

Iteration 7 end: recorders running (shared pid 27184; rec_lab6 v2 pid 14304; rec_exam7 pid 32576, ~6 MB written so far).
19. ANNOUNCEMENTS (C4b, A8; fetched 10-31 17:02 UTC): status.polymarket.com/history lists no incident or maintenance in
    10-01..10-23 (its October entries are 10-27 and 10-29, in the sealed period, not used); docs.polymarket.com/changelog
    for 09-15..10-31 has nothing on fees, rebates, tiers, rewards, order types, rate limits, the matching engine or the
    CLOB (entries: 09-15 PolyBolt websocket launched and RTDS marked LEGACY for crypto/TWAP reference prices; 09-28
    resolution time estimates; 09-29 PolyBolt TWAP channels; 10-02 price.crypto defaults to Chainlink; 10-07 Data API v2;
    10-21 PolyBolt forex). So the cluster's outages and config changes (10-13 14:10 XM share drop, 10-19 large size
    50 -> 100) match no announcement (bot-side / operator decisions), and the RTDS legacy status explains why the kept-open
    RTDS socket sends only its initial snapshot (X21: the streaming replacement, PolyBolt, needs CLOB credentials).
Limitation of rec_exam7 (for a successor): its `p` records keep only price changes AT the post-change touch, so a touch
removal (old best level emptied) shows up only with the next change at the new touch or the next trade; the shared
recorder's clob_crypto keeps the throttled touch as before.
20. KALSHI (A4b, endpoint verified 10-31 17:05 UTC): api.elections.kalshi.com/trade-api/v2 without a key lists series
    KXBTC15M (BTC 15 min) and KXBTCD (hourly); /markets?series_ticker=KXBTC15M&min_close_ts&max_close_ts&status=settled
    returns development-period markets; /markets/trades?ticker=... gives trades with microsecond created_time. The
    lead-lag test against the bot's decisions is left for iteration 8 (A4b stays open).
21. WEAK-VOTE DECISIONS (`weak7.py`, results/weak7.json): underdog share by vote strength, 14:50-16:04 / 16:04-16:25:
    no vote 55% / 67%, |vote| 1-2 41% / 63%, 3-4 45% / 58%, >= 5 54% / 52%; weak votes come later in the window (mean rel
    142-170 s vs 109-123 s for strong votes). No stable value (underdog) signature in the weak-vote decisions at this n.
22. SIDE IN DECISION UNITS, SEVEN CHUNKS (supersedes the three-chunk numbers of finding 16; `du_summary7.py`,
    results/side_decision_units7.json; seven VALIDATE 2-h chunks = 14 h, 13,189 taker orders, every order scored): pool
    72.7% per order (market-only baseline 59.9%); GF 74.6% (3,712), XM 73.1% (769; baseline 63.9%), DS 71.8% (8,708); XM
    one-sided windows by first decision 20/29 = 69.0%. The side condition fails for every wallet at the block clock.
23. KALSHI BTC 15-MINUTE MARKET (A4b, `kalshi7.py`, results/kalshi7.json; 7 KXBTC15M markets, 253,071 trades with
    microsecond times, 968 cluster taker matches 14:50-16:25): the Kalshi YES price moved (>= 0.5 c) over [m - 600, m - 100)
    before 46.9% of matches and agreed with the bot's side in 74.0% (placebo 41.6% moved, 48.9% agree); over
    [m - 2000, m - 100) 57.5% at 67.7% (placebo 49.4% / 49.8%). Kalshi moves with the same underlying ticks but less
    sharply than the Binance USD-M microprice (87.9% at its peak): a co-follower, not the bot's input (A4b tried).

### Iteration 8 (2026-10-31 17:40 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18 blocks)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar: released lots none; 10-31 18-24 and
11-01 00-06 are SEALED (this iteration ran into the 18-24 block from 18:00 UTC: no live record after 18:00 was read). The
shared recorder runs (pid 27184); rec_lab6 v2 (pid 14304) and rec_exam7 (pid 32576) run. Other agents' feeds not read.

Competing explanations at the start of iteration 8 (and what separates them):
- E1 latency taker on venue microprice ticks, paid by the taker rebate (current model). Separates: the side follows the vote
  out of sample; trading PnL ~ 0 after fees.
- E2 complete-set builder: the SIDE references the operator's own book (buy the leg it is short when the set is cheap).
  Separates: own-state terms add to the frozen side model on VALIDATE (panel-mechanics P2).
- E3 position-scaling overlay: the SIZE follows the operator's net on the outcome, not market features (panel-mechanics P1).
  Separates: within-wallet AUC of the net (BUILD -> VALIDATE) far above market controls and above a market-only trend analog.
- E4 stale-liquidity gate: the bot fires only while the touch of o is still unrepriced after a tick (panel-assumptions P3).
  Separates: hazard high for tick x unrepriced, low when the touch already moved.
- E5 Polymarket-internal value taker: without a venue tick it buys the outcome whose Polymarket ask just fell.
- E6 an unrecorded fast stream (Binance USDC-M / COIN-M / FDUSD books, Deribit, liquidations, signed aggressive flow) drives
  the weak-vote decisions (panel-information P1).
- E7 time-driven value (theta, the TWAP lock-in) with the exact strike drives the quiet late decisions (panel-information P2).
- E8 the wallets are concurrency slots (one in-flight order each), which is why the operator runs several (panel-assumptions P2).

Data added (iteration 8):
- NEW RECORDER `code/rec_fam8.py` (pid 20608, started 10-31 17:45:19 UTC, hard stop 11-03 18:00 UTC, cap 290 MB, ~4 MB/h;
  status .cache/re/btc5m-bot/rec_fam8.status): feed `btc5m_xfam` = Binance USDC-M perps (uc), COIN-M perps (cm), spot
  BTCUSDC/ETHUSDC (su) and BTCFDUSD (sf) bookTicker, Deribit quote.*-PERPETUAL (db), Bybit linear orderbook.1 (by), sized top of
  book coalesced to 30 ms; feed `btc5m_xliq` = Binance USD-M !forceOrder (BTC*/ETH*). Written in EVERY block through the Writer
  (sealed blocks filed into .cache/live/sealed/ and never read), so a series that passes on development blocks has exam inputs.
  Test run 17:44 (25 s): db 21/s, by 12/s, uc 11/s, cm 6/s, su 5/s, sf 1/s; no liquidation in 25 s.
- EXAM-INPUT CONTINUATION `code/rec_exam8.py` (launcher pid 19600, sleeps until 11-02 05:59:00 UTC, then runs rec_exam7's
  recorder unchanged under feed names btc5m_xclob8 / btc5m_xven8 until 11-03 18:00 UTC, cap 290 MB; status
  rec_exam78.status): covers the WEEKDAY sealed blocks 11-02 06-12, 11-02 18-24, 11-03 00-06, 11-03 12-18 (rec_exam7 stops at
  11-02 06:00). final_rule reads both name sets.
- On-chain cluster fills 10-31 16:33-17:56 (`post/own_1793464380_1793469400.parquet`, 1,498 fills; a FOURTH live interval).
- Gamma eventMetadata.priceToBeat for all 4,032 BUILD + VALIDATE windows (`.cache/re/btc5m-bot/ptb.parquet`, 99.98% filled;
  finalPrice kept only as `finalPrice_SETTLEMENT_ONLY`). Multi-slug /events requests (25 slugs per GET) work.
- VALIDATE taker tapes re-read from the shared HTTP cache into the session scratchpad (2,016 windows, 2.9 M rows, 70 s).

Findings (iteration 8):
1. SIDE DOES NOT REFERENCE THE SET (X50 = panel-mechanics P2, `own8.py`, results/own8_side.json; 90,170 VALIDATE one-sided
   seconds; operator state = the three wallets' filled shares per outcome with block second <= s - 1 or s - 2): the own-only
   rule "buy the leg the operator is short" 51.0% (cover 98%); 48.4% at rel 0-60 s rising to 57.6% at 240-300 s; BUILD-fitted
   own model 55.5%; the frozen side model psb 75.3%; psb + own logit (no VALIDATE fit) 75.5%; VALIDATE-half-fitted weights
   75.9% vs 75.6% on the second half. +0.2 points overall, +0.7-0.9 at 240-300 s: the complete-set side hypothesis is rejected
   at the block clock (pairing is an accident of two-sided triggers, plus a small late balancing tilt).
2. THE LARGE SIZE IS OWN-STATE POLICY (X49 = panel-mechanics P1, `size8.py`, results/size8.json; calldata sample, signed
   sizes; BUILD hours 10-09/11/13/15 -> VALIDATE hours 10-16..22). Within-wallet VALIDATE AUC of P(large):

   | wallet (VALIDATE orders) | market controls | + BTC return since open (market analog) | + operator net | + siblings' net only | univariate net |
   |---|---|---|---|---|---|
   | GF (2,139) | 0.489 | 0.528 | 0.751 (halves 0.72 / 0.81) | 0.650 | 0.745 |
   | XM (488) | 0.353 | 0.420 | 0.666 (0.64 / 0.71) | 0.642 | 0.762 |
   | DS (4,924) | 0.546 | 0.558 | 0.578 (0.56 / 0.73) | 0.598 | 0.567 |

   The market analog alone is 0.52-0.53 (univariate), so the net is not a proxy for the trend. P(large) by operator net on o
   (VALIDATE): GF 12% (< -200 shares) -> 28% -> 47% -> 77% (flat) -> 59-63% (long); XM 15% -> 38% -> 59% -> 83% -> 59-69%; DS
   10% -> 21% -> 21% -> 24% -> 18-27%. At a fixed net, P(large) is highest when BTC has not moved since the open (|ret| < 1 bp:
   42% at net >= 0, 27% at net < -60). Large orders lose after fees (VALIDATE, >= 90 filled shares): DS -1.92, GF -1.06,
   XM -1.62 c per share; small orders +0.17 / +0.54 / +1.32 c. So the size is an own-book overlay: large when flat or adding,
   small when the order reduces an opposite position; it is value-destroying and invisible to market features (why X29
   failed).
3. OWN-NET SIZING DOES NOT LIFT THE EXECUTABLE REPLICA (X49 step 4, `replica8.py`, results/replica8.json; BUILD table
   P(large | net bin) = 5.8% / 14.2% / 19.9% / 21.5% / 18.5% / 23.8% / 25.0%): convention (b) pool Pearson / Spearman: 30
   shares 0.158 / 0.137, presence-weighted 0.179 / 0.159 (iteration 7), net table 0.149 / 0.142, net threshold 0.128 / 0.120,
   net table x presence 0.156 / 0.146; convention (a) 0.09-0.12. The replica's own net does not track the wallet's net: the
   binding constraint of the PnL condition is DECISION OVERLAP (block-clock decisions), not the size rule. (The panel's oracle
   0.60 used the wallet's own decisions.)
4. FOURTH OUT-OF-SAMPLE LIVE INTERVAL (10-31 16:33-17:55, 462 taker matches; `live8.py`, results/live8.json): the frozen
   exam-feed vote (`final_rule._live_vote`, six series) covers 68.0% at 85.4% (placebo 47.0% / 53.9%; DS 85.6%, GF 85.5%, XM
   7/9); the ten-series lab vote 85.2% on 81.6% voted, by strength |vote| = 1: 69.9% (93), 2: 79.7% (69), 3-4: 89.5% (76),
   >= 5: 96.8% (126); weak share 44.5%. Agreement by interval: 86.4% / 83.0% / 75.3% / 85.2% (ten-series), 80.4% / 85.4%
   (six-series exam feeds): the 75.3% of 16:04-16:25 was a low, not a trend; per-strength agreement stays stable.
5. THE GATE IS A MOVING TOUCH, NOT A STALE ONE (X56 = panel-assumptions P3, `gate8.py`, results/gate8_1793458500.json;
   14:55-16:04, 59,784 grid points of 100 ms, 610 matches): P(match on o in [t+100, t+600)) by the ten-series tick toward o
   over [t-500, t) x the change of o's ask over [t-500, t): tick > 0.5 bp: ask fell 22.2% (279), ask rose 12.0%, unchanged
   11.4%; 0.1-0.5 bp: 13.0% / 9.2% / 6.4%; no tick: 5.3% / 5.2% / 2.1% (25,831); tick against o: 5.5-6.2% / 2.8-3.9% /
   1.7-2.2%. The "unrepriced touch" hypothesis is reversed: the hazard doubles whenever the Polymarket touch of o is moving,
   and is highest when the venue ticks toward o while o's ask falls (a maker moving the wrong way). Interleaved half-split
   AUC: activity 0.641, tick 0.636, activity + tick 0.674, activity + tick + gate 0.742, Polymarket-activity-only (trades +
   touch changes + age + price) 0.697.
6. DECISION-LEVEL PRESENCE OUT OF SAMPLE (`live8.py`, `fit_hazard8.py`, results/live8.json, hazard8_frozen_C.json): models
   fitted on one interval and scored on a later one (no refit). Lab feeds, fit 14:55-16:04: on 16:04-16:33 full 0.759 vs
   Polymarket-activity baseline 0.718 (gain +0.041, window-block 95% CI [0.016, 0.073]); on 16:33-17:55 0.700 vs 0.608
   ([0.066, 0.119]). EXAM feeds (btc5m_xven six series + btc5m_xclob), fit 16:04-16:33, frozen in final_rule as
   `HAZ_FULL_COEF` / `HAZ_BASE_COEF` (`_live_hazard`, reported as presence_live_decision): on 16:33-17:55 (16 windows, 67,030
   points, 1,993 positives) AUC 0.656 vs 0.598, gain +0.058 [0.041, 0.076], p(gain <= 0) = 0 / 2,000. A decision-level
   presence rule with a positive gain over a Polymarket-activity baseline exists for the future-block exam; its AUC (0.66-0.76
   on a 100-ms grid) is far below the 0.85 bar of the block-second unit.
7. WEAK-VOTE SIDE: NO FLOW SIGNAL, AN UNSTABLE POLYMARKET SIGNAL (X44 step 0 = panel-information P1, `weakflow8.py`,
   results/weakflow8.json; 302 matches 14:22-14:47 + 14:54-15:10 with REST aggTrades): signed aggressive notional of Binance
   USD-M over [m-600, m-100) agrees on weak votes BTC 55.1% (placebo 55.8%, n = 68), ETH 47.3% (40.0%); no vote 45% / 40%
   (n = 25); strong votes BTC 60.8%, ETH 68.1% (> $10k: 70% / 87%). Signed flow follows the same ticks and adds nothing on weak
   votes. Polymarket book (`pmside8.py`, results/pmside8_1793458500.json): on 14:55-16:04 weak votes (n = 223) buy the outcome
   whose ask FELL over [m-600, m-100) in 56.1% (placebo 44.8%) and against the Up-mid move 55.2%; strong votes follow the mid
   (60.2% vs 47.7%). On 16:33-17:55 (`fallback8.py`, results/fallback8.json) no-vote decisions did the opposite at 600 ms
   (ask fell 29-32%, i.e. they bought the outcome whose ask ROSE 68-71%) and the value direction only at 3 s (57-67%).
   The weak / no-vote side is not a stable function of any recorded Polymarket or venue input at these n.
8. FULL-COVERAGE LIVE SIDE (PRE-REGISTERED 10-31 18:16 UTC in `final_rule._live_vote`, chosen on intervals A-C; first clean
   test = 11-01 06-12): vote -> outcome whose ask rose over [m-600, m-100) -> outcome whose ask fell over [m-3000, m-100) ->
   underdog. In-sample: B (16:04-16:33) 70.6%, C (16:33-17:55) 78.2% (vote 85.4% on 314, rose-600 64.2% on 53, fell-3000
   57.6% on 66, underdog 70.6% on 17). The first pre-registered order (fell-600 first, favourite last) gave 72.2% (six
   series) / 78.0% (ten series) on C: below 80%.
9. TIME-DRIVEN VALUE WITH THE EXACT STRIKE IS NOT THE QUIET SIDE (X45 = panel-information P2, `ptb8.py`, results/ptb8.json;
   VALIDATE one-sided seconds, FV from Binance spot x a basis fixed at the open from priceToBeat, vol k x 5-min realized):
   "buy Up iff FV_up > last tape Up price" scores 50-55% overall for k = 0.8-2.0 (psb 75.3%); in quiet late seconds (no move,
   rel >= 180, n = 4,281) 47-55% (psb 61.5%); last-minute quiet 51-54% (psb 56.3%); where FV_TWAP and FV_spot disagree (6-33%
   of seconds) the bot follows the TWAP version 42-53%; adding the gap to psb lowers accuracy (69.9-73.3%). Rejected at the
   block clock (the theta hazard on the live unit is not done).
10. DECISION INSTANT ON POLYMARKET'S CLOCK (X47 = panel-information P4, `lstar8.py`, results/lstar8.json; 171 live taker
    orders with calldata limits inside my unthrottled book, 14:14-14:47): P(limit == ask_o(m - L)) = 29.8% at L = 0 (the
    match itself moves the ask), 74.9% at 50 ms, 73.7% at 100 ms, 70.8% at 200 ms, 62.6% at 300 ms, 49.1% at 500 ms, 38% at
    1 s (placebo 5-7%; changed-in-1-s subset 73.1% at 50 ms). The bot's view of the touch is <= ~50-150 ms old at the match:
    the Polymarket leg is fast and the 250-350 ms venue-to-match lag is mostly upstream (venue feed + decision). Pay-up (21 of
    171, 12.3%): 18 deliberate (the ask it saw = the consumed touch < limit), 1 stale. Pay-up is a deliberate limit above the
    touch, not a stale view.
11. WALLETS ARE CONCURRENCY SLOTS (X55 = panel-assumptions P2, `events8.py`, results/refractory8.json, events8_1793458500.json;
    replication on two new intervals): taker matches of one wallet are never < 120 ms apart (14:55-16:04: DS min 123 ms, p1
    256, n = 406; GF 128 / 206, n = 169; XM 171 / 206, n = 35; 16:04-16:33: DS 288, GF 76 (one gap), XM 320); same-wallet pairs
    among < 300 ms pairs 14 of 161 (8.7%) and 3 of 76 (3.9%) vs an independence share of 52% / 51%; within 100 ms 0 / 1
    same-wallet vs 75 / 37 cross-wallet. One in-flight order per wallet (~120-300 ms) is a mechanical reason to run several
    wallets; the dispatcher (which wallet gets which leg) is not fitted yet.
12. MULTI-LEG EVENTS: INTENSITY IS WEAKLY PREDICTABLE (X54 = panel-assumptions P1, `events8.py`; 14:55-16:04, 604 taker matches
    -> 494 events, legs 1: 412, 2: 67, 3+: 15; every multi-leg event spans >= 2 wallets): P(legs >= 2) 16.6%; univariate AUC
    rel 0.64, |vote| 0.58, composite toward o 0.58, |composite| 0.56, ask change of o 0.40 (more legs when o's ask fell);
    half-split logistic activity (trades, |p - 0.5|, rel) 0.61 / 0.63 vs + trigger features 0.64 / 0.67; P(multi-leg) by
    |composite|: 15.7% (< 0.01 bp), 12.0%, 16.5%, 22.2% (0.5-1 bp), 25.0% (> 1 bp). The panel's signature (>= 0.70 vs an
    activity baseline <= 0.60) is not met; the reservation-price fit is not done.
13. VERSIONS TRANSFER (X57 step 4 = panel-assumptions P4, `version8.py`, results/version8.json; calldata, VALIDATE hours vs
    10-31 13:00-14:47): signing-time quantiles of filled taker orders (rel s) [-89.7, 40.8, 42.9, 172.7, 174.6] vs [-89.6,
    42.3, 43.5, 173.2, 174.7] (BUILD [-89.8, 40.5, 42.2, 170.5, 174.1]); pay-up share 16.1% vs 16.0% (DS 9.6 / 9.4%, GF 26.9
    / 26.1%, XM 38.4 / 46.2%); consecutive same-block same-token cluster pairs cross-wallet 70.7% vs 79.5% (BUILD 79.3%),
    +-1 c apart 45% vs 53%. The menu changed (VALIDATE 30/50 then 30/100; 10-31 30/100 with 30/60/100 later) and the large
    share is much lower on the Saturday sample (DS 0.6%, GF 5.4%; XM 46%). Schedule, pay-up and the multi-leg structure
    transfer to h1; the large share is day / regime dependent.
14. ECONOMICS: LOCKED SETS + REBATE (X50 step 4, `econ8.py`, results/econ8.json; VALIDATE 1,904 cluster windows): 87.4% of
    bought shares are paired within the window at a share-weighted pair cost of 0.9786; gross trading PnL before fees
    $65,960 = locked sets $48,923 + unpaired remainder $17,037; fees $61,572; taker rebate (0.5 x taker fees) $30,786;
    per-window total vs unpaired r = 0.93, vs locked 0.39. BUILD: paired 90.2%, pair cost 0.983, locked $48,374, unpaired
    $52,991, fees $78,451. The gross edge is mostly set-building (2.1 c per pair from buying each leg below its later value);
    the per-window PnL variance is the unpaired remainder, which the value-destroying large overlay builds.

Code changes: `final_rule.py`: LIVE_VOTE_FEEDS read both the rec_exam7 and the rec_exam8 feed names (same rule);
`side_live_decision_ext` (pre-registered secondary: the six series plus Bybit L1 from btc5m_xfam); `_live_vote` adds a
pre-registered FULL-COVERAGE side (finding 8; reported as side_accuracy_live_decision_full_coverage); `_live_hazard` /
`_live_hazard_data` (finding 6; frozen HAZ_*_COEF; reported as presence_live_decision). Historical metrics unchanged
(smoke test `evaluate(1792706400, 1792713600)`: identical to iteration 7, 51 s; the live entries return None there).

Status after iteration 8: target not reached; primary metric unchanged (0.9132 all seconds; block seconds 0.8747 vs
0.8193). Closed this iteration: the complete-set side (rejected), the size as own-state policy (VALIDATE-only; no executable
PnL gain), the stale-touch gate (reversed: the bot acts in moving books), time-driven value with the exact strike (rejected
at the block clock), signed flow on weak votes (no signal), the refractory (replicated), the Polymarket-leg latency
(<= 50-150 ms). The unexplained parts, quantified: (i) the weak / no-vote live decisions (31-45% of decisions; side 64-80%
by strength 1-2, unstable fallbacks); (ii) at the block clock the side is capped at ~73-77% by the clock itself
(iteration 7); (iii) the executable PnL correlation is capped by decision overlap (replica 0.16-0.18 at the decoded latency
for every size rule tried; oracle with the wallet's own decisions 0.41 at 30 shares, 0.60 with the own-net size table).

## Next (iteration 9)

1. 11-01 06-12 UTC (the next development block, Sunday): first clean test of the pre-registered full-coverage side and of the
   frozen decision-level hazard on the exam feeds; per-series kernels and weak-vote agreement of the NEW btc5m_xfam series
   (uc, cm, su, sf, db, by) and of btc5m_xliq; the extended eight-series vote (side_live_decision_ext).
2. Weekday development blocks 11-02 00-06 and 12-18: the weekend vs weekday regime (weak-vote share, large share, legs per
   event) and the live size decoder (operator net vs microprice strength) with >= 100 large orders.
3. Still open: X48 co-terminal 15m/1h/4h, X51 depth-aware strict fills from calldata, X52 single triggering message, X53
   rebate-tier controller, X58 return-unit threshold, X30 step 3, X36 replay replica, X5, X7 (options), X9, X10/X43
   (GitHub, no token), X12, X21-X23, X26, X27, X33, X37 (Tardis 11-01 sample, available from 11-01), X39, X40, X42.

Addendum, iteration 8:
15. SINGLE TRIGGERING MESSAGE (X52 = panel-mechanics P4, `msg8.py`, results/msg8.json; per-series lags from the iteration-7
    kernels, never refit; trigger = the tick with the latest lag-shifted time in [m - W, m]): weak votes 16:04-16:33 vote
    66.2% vs single message 56.5-59.1% (W = 100-250 ms), 16:33-17:55 74.1% vs 66.4-71.2%; strong votes 85.4% / 94.1% vs
    80.6-84.0% / 82.8-85.4%; no-vote decisions 36-58%. The bot does not act on one identifiable message; the vote (an
    accumulated composite over ~500 ms) is the better description, and the hazard of finding 6 is its presence form.
16. UNDERDOG TILT: NOT A RETURN-UNIT THRESHOLD (X58 = panel-assumptions P5, `tilt8.py`, results/tilt8.json; 147,489 VALIDATE
    cluster taker orders, Binance 1-s moves toward the bought outcome): at matched |p - 0.5| the median 4-s move preceding a
    buy (given a move toward o) is the same for favourite and underdog buys (ratio 0.96-1.03 for |p - 0.5| 0.02-0.4) where a
    return threshold predicts 1.28-5.14. Underdog buys come more often on flat 4-s moves (78-79% vs 72-74%) and after ADVERSE
    12-s moves (23-25% vs 13-15% for favourite buys at |p - 0.5| >= 0.1; mean 12-s move -0.15 to -0.26 bp vs +0.35 to
    +0.53 bp). The tilt is a value / fade component on the underdog side (consistent with a wider-vol or slower fair value),
    not a threshold in return units; the cent / log-odds families are not distinguished by this test.
17. EIGHT-SERIES EXAM VOTE, PIPELINE CHECK (side_live_decision_ext; 10-31 17:46-17:55, the only development minutes with
    btc5m_xfam): 54 taker matches; six-series 84.1% on 81.5% (placebo 55.9%), eight series with Bybit L1 from btc5m_xfam
    86.4% on 81.5% (placebo 52.9%). Too few matches to judge; it shows that the recorded Bybit series reads correctly.
18. REVEALED-PREFERENCE FAIR VALUE (X30 step 3, `revpref8.py`, results/revpref8.json; 147,489 VALIDATE cluster taker orders
    vs 579,045 other takers' BUY prints from a seeded 600-window sample; exact strike from priceToBeat, index = Binance spot
    x open basis, vol k x 5-min realized, TWAP variance, spot lag L): the share of buys priced below the FV ('value') rises
    with k for the cluster relative to other takers: k = 0.8: 49.5% vs 58.1% (excess -0.09); k = 1.3: 51.4% vs 48.1%
    (+0.03); k = 2.0: 52.8% vs 39.0% (+0.14); k = 2.5-3.0: 51-53% vs 36-38% (+0.145-0.150, saturated). The lag L (0-20 s)
    changes the excess by <= 0.01. At high k the 'value' buys are the underdog buys (underdog 85-94% value, favourite 8-15%):
    a fair value ~2.5-3x wider than 5-min realized vol reproduces the underdog TILT (the bot's FV sits closer to 0.5 than
    the market's), but no (k, L) makes more than 53% of its buys value trades: the decisions are tick-triggered, and the
    level FV only shapes which side the tilt favours. No lag (slow FV) signature.
Disk note (10-31 18:30 UTC): free disk on the laptop fell from ~14.7 GB to 2.9 GB between 18:20 and 18:30, not from this
workspace (.cache/re/btc5m-bot 1.4 GB, unchanged; .cache/live 422 MB in total); no new downloads were started after that.
The session scratchpad tapes (274 MB) were deleted at the end of the iteration (rebuildable from the HTTP cache in 70 s).
19. PUBLIC BOT TEMPLATES (X10 / X43, catalog C8): unauthenticated GitHub code search returns HTTP 401 "Requires
    authentication" (10-31 18:35 UTC), so X43 is infeasible. Two more web searches found Up/Down bots built on
    clob-client-v2 (github.com/lorine93s/dfdsf; an OpenClaw skill with momentum / whale-flow signals), a two-sided maker
    spread bot, and a Binance + Bybit websocket micro-arb with a >= 0.35% momentum threshold; none has the decoded
    fingerprint (pre-signed 1-cent ladders at -89.5 / +42 / +172.7 s, 30/100 menus, 0.002-bp microprice ticks, one in-flight
    order per wallet). No untrusted code was downloaded or run.
20. WHO THE BOT TAKES FROM, HISTORICALLY (X23 historical part, X51 step 5; `prey8.py`, results/prey8.json; calldata sample,
    11 pre-H hours, 24,976 maker orders consumed by 11,382 cluster taker orders): 93.2% are BUY orders on the complementary
    token (mints), 6.8% SELLs; 1,217 distinct makers, the top 10 hold 17.3% (0xd4fa2e10, 0x41e2e1cc, 0x31393e2f, 0x239e726f,
    0xec10d230); 88% of the consumed orders belong to makers with more than 3 orders in the hour (quoters); median original
    size 10 shares, only 3.6% at least 3x the cluster order; median age at the block 3.6 s (~1.4 s at the match, the block
    comes ~2.2 s later), 8% older than 60 s. Large and small cluster orders, quiet and moving markets take the same kind of
    counterparty (age 3.9 vs 3.6 s, quoters 84% vs 89%, >= 3x size 3.0% vs 3.7%). The prey is a fragmented crowd of small,
    frequently re-quoting makers whose quotes are ~1-2 s old, not stale retail lottery orders and not large resting makers;
    the panel-mechanics claim that big fills come from large hidden makers is not supported.
21. THE WIDE-VOL FAIR VALUE IS AN IMPLIED-VOL FAIR VALUE (X7 options part with X30; `dvol8.py`, results/dvol8.json; Deribit
    public get_volatility_index_data, BTC DVOL hourly for 10-16..23, HTTP 200, 168 rows, fetched 18:38 UTC into the
    scratchpad; 146,611 VALIDATE cluster taker orders): DVOL median 37.7% annualized = 0.67 bp per sqrt(s); the 5-min
    realized vol of Binance spot at the orders has quartiles 0.24 / 0.32 / 0.44 bp per sqrt(s), so DVOL / realized has
    quartiles 1.53 / 2.11 / 2.85 (p10 1.03, p90 3.95): exactly the multiplier the revealed-preference fit found (k ~ 2-3).
    With sigma = DVOL of the last complete hour, 53.6% of the cluster's buys are below the fair value (underdog 81.3%,
    favourite 24.2%, mean gap +0.76 c), higher than at any fixed multiplier of realized vol (max 52.8%). Hypothesis (VALIDATE-
    only): the bot prices the digital with an implied (options-market) vol about twice the short-horizon realized vol, so its
    fair value sits closer to 0.5 than Polymarket's and underdogs look cheap; this is the underdog tilt.
22. HOW EXECUTABLE THE DECODED TRIGGER IS, LIVE (X36 first step, `overlap8.py`, results/overlap8.json; interval C, frozen
    exam-feed hazard, 67,030 grid points, base rate 2.97%): flagging the top 2.97% of grid points (as many as the wallet's
    match-points) catches 8.2% of them (precision = recall 8.2%, lift 2.75; Polymarket-activity baseline 7.3%, lift 2.46); at
    2x volume recall 16.1% (baseline 11.8%), at 5x 32.0% (25.4%). At matched volume ~92% of the wallet's decision instants are
    not reproduced within its 100-600 ms reaction window: the decoded trigger is necessary but far from sufficient, which is
    the live face of the decision-overlap limit on the PnL condition.
23. WEEKEND REGIME, HISTORICALLY (X57 step 1 on VALIDATE, `weekend8.py`, results/weekend8.json): the share of one-sided block
    seconds with no six-series move is 28.0% on Saturday-Sunday (Sat 36.1%, Sun 21.2%) vs 14.6% on weekdays (12.7-16.1%);
    the block-clock side accuracy is 74.1% vs 75.6% (Sat 74.3%, Sun 73.9%, weekdays 74.8-76.5%). The weekend doubles the
    quiet (weak-trigger) decisions; the block-clock side barely moves; the large-share comparison is confounded by the day's
    menu (no orders >= 90 shares on the 30/50 days 10-14, 10-18). The first future-block exam (weekend blocks) will see the
    weak-trigger regime; the weekday sealed blocks are now recorded (rec_exam8).

Next (iteration 9), additions from the late findings 16-23:
4. Pre-register BEFORE looking at 11-01 06-12 (then score it there): (a) a DVOL fair-value side for no-vote decisions (buy
   the outcome with the larger FV_DVOL - ask gap) as an alternative fallback to the frozen one; (b) the hazard with the
   DVOL fair-value gap as an extra feature. Keep the frozen rules unchanged and report both.
5. Liquidations (btc5m_xliq) and funding (X7): event study of the cluster's match rate and side around liquidation prints on
   the next development blocks; funding as a regime variable.
6. Disk dipped to 2.9 GB free at 18:30 UTC (external, recovered to 14.3 GB by 18:42): run resources.py --need-disk 5000
   before the larger fetches (X48 15m/1h tapes, X51 calldata).
Sealed-data note (10-31 18:41 UTC): a Deribit DVOL request for 10-31 13:00-18:00 used an inclusive end timestamp and
returned one hourly bar starting 18:00 (inside the sealed block 18-24). Its one value was printed once by the loading check
and the bar was then deleted from the scratchpad file; it was not used in any analysis (only bars ending by 18:00 are kept).
Disk note, update (18:42 UTC): free disk is back at 14.3 GB (the drop was temporary and external to this workspace).
24. THE VALUE-GAP LEVEL DOES NOT TIME THE DECISIONS (follow-up of 21 and 6; `val8.py`, results/val8.json; lab feeds; exact
    strike from Gamma priceToBeat for the 38 development windows of 10-31 14:50-17:55 (finalPrice not kept), S = Binance
    USD-M BTC microprice x open basis, sigma = DVOL of the last complete hour): gap = FV_o - ask_o alone has AUC 0.48-0.50
    for a match on o in the next 100-600 ms; added to the frozen gate design it moves AUC from 0.700 to 0.702 (fit
    14:55-16:04 -> 16:33-17:55) and from 0.680 to 0.685 (fit 16:04-16:33 -> 16:33-17:55). P(match) is U-shaped in the gap
    (3.0% below -5 c, 1.4-1.6% at -5..0 c, 2.1-2.8% at 0..5 c, 3.2% above 5 c): large gaps mark fast markets, not value. The
    bot reacts to CHANGES (venue ticks, a moving Polymarket touch); the implied-vol level shapes which side it leans to
    (finding 21), not when it acts.
25. EXAM PATH FOR FUTURE BLOCKS FIXED (code): `evaluate` on a 10-31 period crashed in load_spot (the Binance 1-s daily
    archive of a day is published the next day, so the spot frame was empty) before any live component ran. `evaluate` is
    now a wrapper: `_evaluate_full` (unchanged rule) and, if it raises, `_evaluate_live_only` (windows, on-chain fills, the
    frozen live vote with its full-coverage fallback, the eight-series vote, the frozen hazard and the live-book price;
    historical keys None, error recorded). Test through the exam path, evaluate(1793464500, 1793466300) (10-31 16:35-17:05,
    development, 6 windows, 463 fills, 76 s): live vote 87.5% on 54.4% (placebo 39.3%), full coverage 78.5% on 91.8%,
    hazard 0.652 vs 0.573 (gain +0.079, CI [0.055, 0.099]), price within a tick 92.9%. (In-sample for the fallback choice:
    the interval overlaps C.) For a lot whose archives are published, the full path runs as before.
26. CO-TERMINAL 15m WINDOWS (X48 = panel-information P5, `coterm8.py`, results/coterm8.json; 120 seeded VALIDATE 15m windows,
    Gamma priceToBeat for both windows (open-time fields), the 15m data-api taker tape over the co-terminal 5m window, DVOL as
    the common scale): P5_implied = Phi(Phi^-1(p15) + ln(K15/K5) / v) vs the 5m tape price on 5,436 cluster one-sided
    seconds: "buy Up iff P5_implied > m_last" 50.5% (quiet 52.0%; psb 74.2% / 62.6%), BELOW its 60-s time-shift null (53.0% /
    56.1%). Caveat: the mean |gap| is 20 c, so a DVOL-scaled conversion between the two markets is noisy (Polymarket's
    prices imply a different scale); a common market-implied scale per window would be the refined test. As measured, the
    15m market carries no side information for the bot's co-terminal 5m decisions at the block clock (X8 had found the 15m
    mid a co-follower live).

Catalog after iteration 8: 12 items open (X5, X7, X9, X26, X27, X33, X36, X37, X44, X51, X53, X57); X48 and X42 were closed by
findings 26 and 27 (listed as open in the Next list above, written before them). Iteration 8 wall time ~75 minutes.
Recorders at the end: shared (pid 27184), rec_lab6 v2 (pid 14304, development blocks only), rec_exam7 (pid 32576, to 11-02
06:00), rec_fam8 (pid 20608, to 11-03 18:00), rec_exam8 launcher (pid 19600, starts 11-02 05:59, to 11-03 18:00).
27. PAY-UP AS A (WEAK) RESERVATION PRICE (X42, `pay8.py`, results/pay8.json; 6,306 VALIDATE calldata taker orders; FV at
    sigma = DVOL with the exact strike): P(limit above the consumed touch) is 12-14% when the FV is below the touch, 15% at
    0-2 c above, 17% at 2-10 c, 23% at > 10 c; median FV - touch +2.6 c for pay-up orders vs +0.3 c otherwise; pay-up
    limits are below the FV in 54.4% (touch below FV for the others 51.8%); large orders pay up 41% (median gap +1.6 c) vs
    small 12.8% (+0.5 c). The ladder depth rises with the implied-vol value above the touch, but the limit is not a clean
    reservation price (FV - margin) at the block clock. With finding 10 (pay-up is deliberate, not stale), X42 is tried.

### Iteration 9 (2026-10-31 19:26 UTC start, local Windows laptop; PIVOT: the decision record from the book; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar: released lots none; this iteration ran
inside the sealed block 10-31 18-24, so there is no new live development data (the next development block is 11-01 06-12);
every live analysis below uses the 10-31 12-18 development block (14:14-17:55 for my unthrottled book). Shared recorder running
(pid 27184, `live.py status` 19:29 UTC). Nothing sealed was read.

PIVOT (required: progress flat for three iterations). New unit of decision: the BOOK INSERTION of every cluster order, including
the orders that lost the race and filled later as maker (maker fills were 49-65% of the cluster's filled shares on 10-31, and
every earlier live metric scored race winners only). New target: the PnL condition's attainable ceiling (a test-retest bound)
instead of more replica variants. Then the selectivity question this exposes, and an audit of the presence baseline.

Competing explanations at the start of iteration 9 (and what separates them):
- E1 race-lottery latency taker: every decision is a GTC BUY at o's touch after a microprice tick; it wins a fraction q of the
  races; lost races rest at the old ask (like remainders) and sometimes fill as maker. Separates: maker-first limits = o's ask
  seen within ~300 ms before insertion; the vote at insertion equals the vote at won races; >= 2.5 decisions per filled order and
  a PnL test-retest ceiling < 0.5 (panel-assumptions P3).
- E2 a passive quoting component (XM's 60-share class, panel-assumptions P1): post-only bids below the ask, not tick-locked.
  Separates: limit < ask seen by >= 1 c, vote near placebo, never at the ask in the seconds before.
- E3 a selective trigger: the bot decides rarely; most high-hazard instants are non-decisions. Separates: ~1-1.5 decisions per
  filled order.
- E4 shared capacity across assets (panel-assumptions P5): the same process trades ETH / SOL 5m or BTC 15m with other wallets.
  Separates: fingerprinted wallets signing in the -89.5 / +42 / +172.7 s bursts of other assets' windows.
- E5 a stale-quote sniper against a Polymarket-anchored value (panel-mechanics P1). Separates: the edge since o's touch last
  changed adds AUC beyond the tick terms, and the weak-vote side follows it (>= 75%).
- E6 a depth-reading sweeper (panel-mechanics P2): pay-up = the level where visible depth covers the order; large size when the
  depth is large. Separates: limit == depth-cover level >= 70%; within-wallet AUC of the large size from depth >= 0.70.
- E7 a liquidity-rewards farmer: XM's 60-share size clears the 50-share rewardsMinSize, so resting 60s would farm rewards.
  Separates: 60s resting near the midpoint for minutes without a trigger (E2's measurements; REWARD rows for 10-31 would be
  timestamped in a sealed block and were not read).

Data added (iteration 9):
- V2 calldata of ALL 7,179 cluster txs of 10-31 12:00-17:56 (5,091 fetched now into `.cache/re/btc5m-bot/it9/cd9.parquet`,
  18,046 decoded order rows, 2 min); merged on-chain fills `it9/own_1231_12_18.parquet` (7,725 fills).
- Calldata of 1,882 sampled ETH 5m / SOL 5m / BTC 15m / BTC 5m match txs of 10-31 16:00-17:00 (decoded fields only, in
  memory; the summary is results/other9.json).
- pmxt v2 archive endpoint verified: `https://r2v2.pmxt.dev/polymarket_orderbook_2026-08-01T12.parquet` answers HTTP 206 to a
  1-byte range request with no key (Content-Range bytes 0-0/477191092, 0.39 s, 10-31 19:57 UTC). X18 was infeasible only
  against archive.pmxt.dev; the data host works (panel-information iter8 critique 1). Not downloaded yet (disk: free space
  fell to 3.3 GB at 20:00 UTC, external to this workspace, which stays at 1.4 GB).

Findings (iteration 9):
1. MAKER-FIRST ORDERS ARE LOST RACES (X68 = panel-assumptions P2, X65 = mechanics P3 step 1; `ins9.py`, `ins9b.py`,
   results/ins9.json, ins9b.json). 2,427 cluster orders of 14:14-17:55 (T-first 1,336, M-first 1,091; calldata for 100%). The
   insertion finder (the latest size increment of exactly the order's size at (o, limit) in the Up book before the first maker
   fill; a BUY Down at L is an Up ask at 1 - L) was validated on 502 take-then-rest remainders: 92.4% found, 17-38 ms before the
   trade message. 1,041 M-first insertions located (95.8%; 57% had more than one same-size increment at the level, the latest
   was taken). Classes by o's ask path before the insertion:

   | class | all (1,041) | unambiguous (422) | 8-series vote at insertion (placebo) | by strength 1 / 2 / 3-4 / 5+ |
   |---|---|---|---|---|
   | lost race: limit was o's ask within 300 ms | 60.0% | 73.9% | 80.5% on 78.9% voted (52.0%) | 62.6 / 83.5 / 86.1 / 94.7% |
   | lost race within 1 s | 19.7% | 19.7% | 56.3% (64.2%) | |
   | passive: never at the ask in 2 s | 14.3% | 3.1% | 43.2% (57.7%) | |
   | won races (T-first matches), for comparison | | | 80.6% on 78.3% voted (51.9%) | 70.9 / 74.6 / 84.0 / 95.5% |

   The lost races are the same tick-triggered decisions as the won races (same vote, same strength profile); the "passive" class
   is mostly attribution noise (3% of unambiguous insertions, vote below placebo). View age: won races' limit >= o's ask at
   m - 50..200 ms in 95-97% (== 71-72%); maker-first limits refer to the ask 150-1,000 ms before the insertion. Gate check: o's
   ask rose over [s - 500, s - 100) before 33.6% of lost-race insertions vs 24.5% of won races (fell 19.4% vs 21.3%): losing a
   race goes with an ask that moved away first.
2. XM'S 60-SHARE CLASS IS LATE TAKER LEGS, NOT A PASSIVE COMPONENT (X67 = panel-assumptions P1; ins9b, `who9.py`,
   results/who9.json): 346 XM 60-share maker-first orders: lost races 87% (69% within 300 ms), passive 10%; vote 79.8% on 77%
   (65 / 77 / 89 / 96% by strength; placebo 51%). The ask they aimed at was taken by DS (26%) or GF (8%), by other takers (45%),
   or requoted away (21%), a median 124 ms before XM's insertion. XM's 91% maker share on 10-31 is its place at the end of the
   fan-out: it loses most races and its order rests at the old ask. E2 and E7 rejected (tick-locked; rests seconds, not minutes).
3. WHO TOOK THE ASKS THE LOST RACES AIMED AT (X61 = panel-information P3, part; who9): of 624 lost_300 insertions, other takers
   52.9%, the cluster's own earlier legs 19.2%, no trade at that price (the maker requoted) 27.9%; median lag from that trade to
   the insertion 58 ms (cluster) / 139 ms (others).
4. DECISIONS PER FILLED ORDER: ~1.45, A SELECTIVE BOT (X65 = mechanics P3; ins9 / ins9b): P(a T-first remainder gets >= 1 maker
   fill) = 0.458 (DS 0.47, GF 0.45, XM 0.27); remainders on 37.7% of T-first orders. Unfilled lost races = lost-race M-first
   orders x (1 - 0.458) / 0.458: 3,457-3,532 decisions for 2,427 filled orders, 1.42-1.46 decisions per filled order, q = P(fill
   | decision) = 0.69-0.70. The panel's thresholds: a race lottery needs >= 2.5, a selective bot ~1.5. E1 (lottery) rejected; E3.
5. THE PnL CONDITION IS ATTAINABLE IN PRINCIPLE: TEST-RETEST CEILING 0.74-0.80 (X69 = panel-assumptions P3, strong form of X17;
   `pnlceil9.py`, results/pnlceil9.json; VALIDATE, 175,831 orders, 1,904 windows). With independent races, the true rule
   replayed (another q-thinning of the same decisions) correlates with the wallet at r = 1 - (1 - q) kappa, kappa = E[sum over
   orders of x_d^2] / Var(window PnL), x_d = the order's PnL after fee and rebate (exact under the model, no distributional
   assumption). The model predicts the empirical random split-half: pooled 0.199 vs 0.201, DS 0.011 vs 0.013, GF 0.188 vs 0.193,
   XM -0.024 vs -0.020.

   | unit | kappa | r at q = 0.5 | q = 0.61 (2-h block CI) | q = 0.70 | q needed for r = 0.5 |
   |---|---|---|---|---|---|
   | pooled cluster | 0.668 | 0.67 | 0.74 [0.71, 0.76] | 0.80 [0.78, 0.82] | 0.25 |
   | DS | 0.978 | 0.51 | 0.62 [0.58, 0.66] | 0.71 | 0.49 |
   | GF | 0.683 | 0.66 | 0.73 [0.71, 0.76] | 0.80 | 0.27 |
   | XM | 1.049 | 0.48 | 0.59 [0.54, 0.63] | 0.69 | 0.52 |

   Gaussian-copula Spearman: pooled 0.72 (q = 0.61), 0.79 (0.70). An upper bound (the own-state size overlay adds replay
   variance), but far above 0.5 at the measured q: condition 5 is NOT a race-lottery wall. It is bound by DECISION OVERLAP: the
   replica's 0.18 reflects a rule that reproduces ~8% of the wallet's decision instants. (VALIDATE q: maker-first orders are
   17-27% of orders and pi_rem 0.19 (X35), so q ~ 0.5-0.6 there.)
6. THE SIDE CONDITION DOES NOT BIND IN SUBSTANCE (X67 step 1; `census9.py`, results/census9.json): one-sided share of the wallet's
   windows vs the order-count null (keep each wallet's order count per window, draw sides from the pooled cluster's Up share in
   that window, 200 draws): VALIDATE XM 24.3% vs 26.1%, GF 3.1% vs 3.7%, DS 0.2% vs 0.7%; BUILD XM 5.8% vs 6.9%; 10-31 XM 3.5% vs
   6.1%, GF 6.3% vs 6.8%, DS 0.7% vs 1.6%. No wallet is more one-sided than its order count implies, and on 10-31 none reaches the
   20% bar. Maker share of fills: XM 41% (BUILD) -> 44% (VALIDATE) -> 91% (10-31); DS 33 -> 36 -> 54%; GF 30 -> 39 -> 59%.
7. THE STALE-QUOTE EDGE IS SUBSUMED BY THE TICK (X63 = panel-mechanics P1; `stale9.py`, results/stale9.json; 100-ms grid, fit on
   A = 14:55-16:04, scored on B = 16:04-16:33 and C = 16:33-17:55, never refit): E_o = mid_o(a) + k Delta_o dS - ask_o (anchor
   a = the last change of o's bid or ask, capped at 10 s; dS = mean BTC microprice move in bp from a - 250 to t - 250 ms; Delta_o
   at sigma = 0.67 bp / sqrt(s); k = 2 chosen on A among six variants with univariate AUC 0.48-0.52). The hazard is U-shaped in
   E (A: P(decision) 12.4% at E < -2 c, 5.0% at -1..0 c, 27-29% at E > 2 c): large |E| marks fast markets. FULL + E vs FULL:
   +0.0002 / +0.0003 (match label, B / C), +0.0013 / +0.0009 (decision label), CIs include 0. Weak / no-vote side by argmax E at
   m - 50: A 58-72%, B 52-54%, C 64-70%. E5 rejected: the bot does not anchor on o's last touch change. With DECISIONS (matches +
   lost races) as positives, the frozen FULL design's out-of-sample AUC rises from 0.759 to 0.768 (B) and from 0.700 to 0.728
   (C; gain over the Polymarket-activity baseline +0.084 [0.061, 0.108]): censoring to race winners cost 0.01-0.03 AUC.
8. VISIBLE DEPTH DOES NOT SET THE PAY-UP (X64 = panel-mechanics P2; `depth9.py`, results/depth9.json; 1,326 T-first orders, the
   book of o rebuilt at m - 50 ms from snapshots and near-touch changes): pay-up limits equal the cheapest level whose cumulative
   depth covers the order in 17.6% (touch + 1 c 51.8%), and the touch alone covered the order in 54.8% of pay-ups; P(pay-up |
   touch size < order) 30.4% vs 25.3%. Large orders come with THIN books (within-wallet AUC of the touch size DS 0.37, GF 0.46,
   XM 0.53; depth within 2 c 0.31 / 0.38 / 0.42; only 19 / 20 / 16 large orders: under-powered). E6 rejected for the price; the
   size stays own-state policy (iteration 8) with a possible thin-book tilt. (The rebuilt touch sometimes trails the true one:
   96 pay-ups >= 5 c above it; treat the depth numbers as approximate.)
9. THE PROCESS IS BTC-5m-ONLY (X71 = panel-assumptions P5; `other9.py`, results/other9.json; 1,882 sampled txs of 11 windows of
   10-31 16:00-17:00: ETH 5m x3, SOL 5m x3, BTC 15m x2, BTC 5m x3; 5,493 orders): the operator wallets appear only in BTC 5m
   (DS 32, XM 19, GF 13, W4 8 orders; 100% / 88% inside the bursts); on the other assets no maker with >= 8 orders signs >= 60%
   of them inside the -89.5 / +42 / +172.7 s bursts, and fingerprinted orders (type 3, 317 bytes, zero builder and metadata) are
   3.1% in-burst (random timing). E4 rejected.
10. AT THE INSTANTS THE TRIGGER FLAGS, SOMEONE ELSE TAKES THE LIQUIDITY (X61 = panel-information P3, flagged-instant part;
    `flag9.py`, results/flag9.json; FULL design, decision label, fit on A, scored on C, AUC 0.728, base rate 4.0%): top 1% of
    the score: P(cluster decision in [t + 100, t + 600)) 23.3%; where it did not decide (515), another taker bought o in 79.8%,
    the ask moved up with no trade 2.5%, nothing 17.7% (bottom 50%: other takers 35.1%, nothing 63.0%); where it decided, others
    bought o too in 93.6%. Top 3%: P(decision) 17.4%; no decision: others 72.5%, nothing 25.5%. Own slot state (a cluster match
    in [t - 300, t), reported, not a feature): P(decision | top 3%) 23.5% busy vs 16.5% not busy (busy slots do not suppress
    decisions). By ask level (top 3%): 49% (< 0.15), 35% (0.15-0.3), 16% (0.3-0.5), 13% (0.5-0.7), 23% (0.7-0.85), 19%
    (> 0.85). The flagged instants are real opportunities that a crowd of fast takers takes; the cluster takes part in ~1 of 4-5
    (up to ~1 of 3 counting its unfilled lost races) and more at cheap asks. What makes it skip the rest is not its own slots,
    not another asset, not the stale-quote edge or depth: the selection rule is the open part of the timing component.
11. THE BLOCK-SECOND PRESENCE GAIN SURVIVES A STRONGER BASELINE (X70 = panel-assumptions P4, partial; `blkaug9.py`,
    results/blkaug9.json, model_it9_blk_aug.txt): the pure baseline plus dm1, dm2, the OTHER outcome's tape state (ask, bid,
    their ages, n1/n2/n5/n30, vol30, flow1/2/5, dm5/dm10) and the Up + Down ask sum, same LightGBM budget on the same BUILD
    block seconds: VALIDATE AUC 0.8211 (pure 0.8193); the frozen full model 0.8747: gain +0.0536, 2-h block bootstrap 95%
    [0.0506, 0.0563], p(gain <= 0) = 0 / 2,000; per wallet GF +0.063, XM +0.066, DS +0.051; halves +0.053 / +0.053 (804,746
    cells). The other outcome's ask is the third most important baseline feature, but it adds only +0.002. Still not covered: counts
    of other traders' bot-size prints, sub-second intensities and W4's prints (X66 / X70 remain open for those).
    target_metrics.presence_baseline now reports this stronger baseline (0.8211).

Status after iteration 9: target not reached; primary metric unchanged (0.9132 all seconds; block seconds 0.8747 vs the stronger
baseline 0.8211, gain 0.054). What changed is the account of what is unexplained:
- the decision record: maker-first fills (half of 10-31's filled shares) are lost races of the same tick trigger (vote 80.5% =
  won races 80.6%), XM's role change is its position at the end of the fan-out, and the bot makes ~1.45 decisions per filled
  order (selective, not a race lottery);
- the PnL condition is attainable in principle (true-rule test-retest ceiling 0.74-0.80 pooled, 0.59-0.73 per wallet at the
  measured q): the gap (0.18) is decision overlap, not luck;
- the selection rule among flagged instants is the open part: at the top 1% of the decoded hazard others take the liquidity in
  80% of the instants the cluster skips, and its own slots, other assets, the stale-quote edge and visible depth do not explain
  the skips;
- the side condition does not bind in substance (no wallet beyond its order-count null);
- presence passes against a stronger market baseline (+0.054, CI [0.051, 0.056]).

## Next (iteration 10)

1. 11-01 06-12 UTC (development, Sunday): score the pre-registered iteration-8 tests (full-coverage side, frozen hazard,
   eight-series vote); replicate the decision record (ins9 / ins9b) and the flagged-instant classification (flag9) there; the
   selectivity search on that block: which state separates the flagged instants the cluster takes from those it skips (the
   competitor set from tx senders, the queue ahead at the touch, the size at the touch, the time since o's last trade, the
   window's running volume).
2. X60 (pmxt v2 summer archive + Tardis 07-01 / 08-01): the decision record and the selectivity search on weekday hours with
   tx hashes, at 10^4+ decisions (disk permitting: free disk was 3.3 GB at 20:00 UTC; reduce each hour at once).
3. X59 (per-block historical match clock from fresh-signed anchors) for the h1 side and presence at ms; X66 / X70 (W4 out of
   the baseline, bot-size print counts in the baseline); X62 (the bracket midpoints of opposite-outcome pairs).
4. Still open from earlier: X5, X7, X9, X26, X27, X33, X36, X37, X44, X51, X53, X57.

Addendum, iteration 9 (selectivity, after the Next list above was written):
12. A FEE-AWARE EDGE MARKS PART OF THE SELECTION (X72 step; `fee9.py`, `fee9b.py`, results/fee9.json, fee9b.json; lab feeds,
    decision label): V_k = k x 100 Delta_o x move - cost, move = mean BTC microprice move toward o over [t - 600, t - 100) ms,
    Delta_o at sigma = 0.67 bp / sqrt(s), cost = 100 x (half spread + 0.035 p (1 - p)) (the taker fee net of the 50% rebate).
    The decision hazard steps up 6-10x where V_k crosses 0 at every k from 1 to 8 (k = 1: A 3.0% at -1..0 c -> 26.2% at 0..1 c;
    C 3.3% -> 26.7%), but few decisions reach V_k > 0 (recall 3-4% at k = 1, 13-14% at k = 8; precision 20-29%), and the
    negative tail (V < -2 c) also has an elevated hazard (8-13% vs 4% base: decisions after strong moves against o). Inside the
    top 3% of the hazard, V separates taken from skipped instants with AUC 0.62 (cost alone 0.61, gain alone 0.64, other
    trades 0.47). Fit on A, scored on C: FULL + V +0.001 [0.0004, 0.0018] (k = 1), +0.0037 [0.0015, 0.0059] (k = 8, chosen on
    A by step ratio x recall). The two-parameter rule "decide iff V_8 > 0" flags 2.7% of C's grid points at precision 19.7% /
    recall 13.0%, at least as good as the fitted FULL hazard at the same volume (18.1% / 11.9%). k is not well identified (the
    step persists at every k; k trades recall for precision): the rule is a move threshold that scales with cost / Delta
    (higher when the spread is wide, the fee is high near 0.5, or Delta is small early in the window or at extreme prices).
13. OWN-BOOK SET COMPLETION TILTS THE SELECTION (own state, reported separately; `setgate9.py`, results/setgate9.json; C, top 3%
    of the hazard, holdings from the three wallets' fills matched > 300 ms before t): P(decision) 12.0% with no holdings of the
    other outcome, 14.2% with holdings but nothing unpaired, 31.1% when buying o would pair unpaired shares at a pair cost below
    0.97, 21.1% at 0.97-1.00, 15.7% at >= 1.00; AUC (taken vs skipped) of -pair cost 0.59, unpaired shares 0.60, -own net 0.59.
    The SIDE does not reference the set (X50), but the decision to act on a flagged instant leans toward cheap set completion
    (confounded in part with window activity: holdings mean earlier decisions in the window). VALIDATE-only (live development),
    own state.
14. THE EDGE RULE ON THE EXAM FEEDS (pre-registered in `final_rule.py` as `presence_live_decision.edge_rule_V8`: EDGE_K = 8,
    EDGE_SIGMA_BP = 0.67, EDGE_FEE_NET = 0.035, BTC series of btc5m_xven, match label; first clean test 11-01 06-12): exam path
    `evaluate(1793464500, 1793466300)` (10-31 16:35-17:05, development, 57 s; historical part unavailable for 10-31, as in
    iteration 8): flagged 1.17% of 26,938 grid points, precision 18.8%, recall 9.0%, lift 7.7 (base 2.4%), against the frozen
    FULL hazard at the same volume 5.7% / 2.8%; the hazard itself unchanged (0.652 vs 0.573, gain +0.079 [0.055, 0.099]).
    Other intervals (results/edge9_exam_feeds.json): 16:04-16:33 (the hazard's own fit interval) edge rule 6.6% / 2.5% (lift
    1.5) vs the hazard 22.9% / 8.7%; 17:05-17:55 edge 10.3% / 8.9% (lift 3.1) vs 9.6% / 8.3%. The edge rule is UNSTABLE between
    30-minute intervals (lift 1.5-7.7): a real but weak selection marker, not the selection rule. The hazard's out-of-sample
    gain over the Polymarket-activity baseline is +0.078 [0.055, 0.098] (16:35-17:05) and +0.048 [0.032, 0.071] (17:05-17:55).
15. Next-iteration addition: score edge_rule_V8 and the decision record on 11-01 06-12 (pre-registered); search the selection
    rule with the edge V, the set-completion state (own, reported separately), the competitor set and the queue at the touch
    on that block (X72).
16. THE PnL CEILING REPLICATES ON 10-31 (`pnlceil9b.py`, results/pnlceil9b.json; the 142 development windows of 10-31 00-06
    and 12-18 with Gamma outcomes (settlement only; every slug asserted development), 10,104 orders, 17,145 fills): pooled
    kappa 0.407; predicted split-half 0.422 vs empirical 0.417 (the model fits again); ceiling at the live q = 0.70: pooled
    0.878 [0.845, 0.897]; DS 0.85, GF 0.67, XM 0.72; q needed for 0.5: pooled any q, DS 0.03, GF 0.55, XM 0.47. Condition 5 is
    attainable in principle in both regimes.
17. THE DECISION COUNT IS ROBUST TO THE LOST-RACE FILL RATE (`pianon9.py`, results/pianon9.json; 44,525 anonymous bot-size
    increments on o's bid at the price that was o's ask within 300 ms, 10-31 14:55-17:55): filled before the level lost that
    size 33.9% (30 shares 34.7%, 60: 27.4%, 100: 17.4%), cancelled 60.7% (median life 70 ms, the crowd cancels much faster than
    the cluster's remainders), expired after 10 s 5.4%. With pi = 0.34 instead of the cluster's own pi_rem = 0.46, the decision
    count becomes ~1.70 per filled order (q = 0.59); with 0.46, 1.45 (q = 0.70). Either way below the 2.5 of a race lottery, and
    the PnL ceiling at q = 0.59 is ~0.73 (VALIDATE kappa) to ~0.83 (10-31 kappa) pooled.
18. THE LARGE SIZE HAS A PUBLIC, DECISION-LEVEL COMPONENT LIVE: THE TICK STRENGTH (`size9.py`, results/size9.json; 1,287
    taker-first orders of 10-31 14:55-17:55 with calldata sizes, 50 large (>= 90 shares); features at the last 100-ms grid point
    before m - 50 ms, lab feeds): within-wallet AUC of the large size from the tick toward o over [t - 500, t): DS 0.62, GF 0.71,
    XM 0.81 (pooled 0.71); from the delta-scaled gain: 0.61 / 0.67 / 0.74; from the cost (half spread + net fee): DS 0.82, GF
    0.59, XM 0.47 (DS's large orders sit near 0.5, |ask - 0.5| AUC 0.31); P(large | V > 0) 20.0% (n = 40) vs 3.4% at V <= 0
    (DS 10.5% vs 1.6%, GF 25% vs 4.8%, XM 40% vs 23%). Historically at the block clock market controls gave 0.35-0.55
    (iteration 8): the block clock blurs the tick. Small sample (16-19 large orders per wallet): a hypothesis, to be tested on
    11-01 06-12 (pre-registered: within-wallet AUC of the large size from the six-series exam-feed tick toward o at m - 50 ms
    >= 0.65 for DS and GF), alongside the own-net overlay (iteration 8). If it holds, the size class becomes partly public and
    the executable replica can carry it (the own-decision oracle rises from 0.41 at 30 shares to 0.88 at the size class).
19. THE COMPETITORS AT FLAGGED INSTANTS ARE A BROAD CROWD (X61 with identities; `comp9.py`, results/comp9.json; C, top 3% of the
    hazard, taker wallets from data-api /trades by tx hash, operator wallets incl. W4 excluded): 516 distinct wallets bought o in
    [t + 100, t + 600) at the flagged instants the cluster skipped; the top 10 hold 19.8% of them, and each top competitor also
    appears at the instants the cluster took (ratio 2-4 : 1, like the base 83 : 17). A top competitor's activity on the window in
    the previous 2 s does not change the cluster's P(decision | flagged) (15-19% with vs 17-19% without, no consistent sign).
    The selection is not a reaction to specific competitors.
20. W4 BELONGS IN THE OPERATOR NET (X66 step 2 = panel-mechanics P4; `w4size9.py`, results/w4size9.json; W4's 2,615 V2 fills in
    the calldata sample hours, all pre-H, by topic2): W4 is 14.2% of the operator's absolute flow in those windows; with the
    four-wallet net the within-wallet VALIDATE AUC of the large size rises DS 0.578 -> 0.591, GF 0.751 -> 0.771, XM 0.666 ->
    0.703 (univariate 0.567 -> 0.572, 0.745 -> 0.766, 0.762 -> 0.789); the three-wallet numbers reproduce iteration 8 exactly.
    The size overlay reads the whole operator's book, W4 included (the panel's +0.02-0.05 signature: met for GF and XM).
    Not done: removing W4's prints from the tape features of the presence rule and its baselines (X66 step 3 / X70).
21. THE LIVE SIZE-FROM-TICK RESULT DOES NOT SHOW AT THE BLOCK CLOCK (`sizetick9.py`, results/sizetick9.json; 13,443 calldata
    sample orders): Binance spot move toward o over 1-5 s ending at s - 2: within-wallet VALIDATE AUC of the large size 0.45-0.53
    (|move| 0.43-0.50); BUILD-fitted controls + ticks 0.549 / 0.545 / 0.393 vs controls 0.546 / 0.496 / 0.354 (DS / GF / XM).
    Either the block clock blurs the tick (as it does for the side) or finding 18 is a small-sample Saturday effect (large share
    1.8-25% on 10-31 vs 18-43% in the VALIDATE sample hours): the pre-registered test on 11-01 06-12 decides.
22. OPPOSITE-OUTCOME BRACKETS ARE ANCHORED ON THE POLYMARKET MID, SHIFTED BY THE VENUE MOVE (X62 = panel-information P4, first
    step; `bracket9.py`, results/bracket9.json; 140 pairs of taker-first orders on opposite outcomes of a window within 1 s, 10-31
    14:14-17:55): the implied FV_up bracket [L_up, 1 - L_down] is <= 1 c wide in 71% of pairs and NEGATIVE (pair cost > 1) in 42%,
    so it rarely contains the Polymarket mid at the first match (2.1%); the bracket midpoint equals the mid at the median (p10 -2.05 c,
    p90 +3.0 c), and on the 20 pairs with a Binance USD-M move above 0.1 bp in the 500 ms before, midpoint - mid follows the move
    (correlation 0.94, same sign 95%). The legs are reactions to successive opposite ticks at the then-current asks (42% of such
    pairs cost more than 1), and the implied value is the Polymarket mid plus the venue move (family (b) of the panel), not an
    absolute digital level (which sits ~5 c from the mid, X21). Small n; the full regression of the panel (held-out halves, EMA
    half-lives, implied-vol candidates) is not done.
23. A WEEKLY CYCLE IN THE MAKER SHARE, AND XM'S STEPS (X9 / X26 / X57 partial; census9 by day, 10-09..22 and 10-31): the maker
    share of fills rises on weekends for every wallet (DS 0.46-0.50 on 10-10/11 and 0.45-0.48 on 10-17/18 vs 0.28-0.37 on weekdays;
    maker-first orders 0.21-0.26 vs 0.13-0.18), so more races are lost on weekends; 10-31 (Saturday) DS 0.54 / GF 0.59 fits that
    cycle, XM's 0.91 does not (its weekend level was 0.48-0.53). XM's fill count steps from 19-20k a day (10-09..13) to 1.6-3.1k
    (10-14..22) and back up on 10-31 (a ~10k-a-day pace) mostly as the late leg. XM's one-sided share tracks its order-count null
    on every day (e.g. 10-15 0.19 vs 0.19, 10-17 0.35 vs 0.40). The full-history change-point search (back to July, V1) is not done.
24. WHAT THE PnL CONDITION NEEDS (corollary of finding 5, same model): a replica that reproduces a random fraction phi of the
    wallet's decisions (same side, price and size) and makes its other decisions independently, at the wallet's volume,
    correlates at about phi x r_ceiling. With r_ceiling 0.74 (VALIDATE, q = 0.61) the PnL condition needs phi >= ~0.68 of the
    decisions reproduced; the frozen live hazard reproduces ~8% at matched volume (overlap8), the edge rule 9-13%. The next
    gains on condition 5 must come from the selection rule (X72), not from fill or size conventions.

Smoke tests at the end of iteration 9 (code/final_rule.py with the pre-registered edge_rule_V8): `evaluate(1792706400, 1792713600)`
(last 2 VALIDATE hours, 50 s) reproduces iteration 8 exactly (presence 0.846 vs 0.784, side 77.9%, selection 0.884 at recall 72.4% /
lift 4.57, price 96.4%, PnL 0.38 / 0.32); the exam path `evaluate(1793464500, 1793466300)` returns the live components (hazard
0.652 vs 0.573, edge rule lift 7.7). Recorders at the end: shared (pid 27184), rec_lab6 v2 (pid 14304), rec_exam7 (pid 32576),
rec_fam8 (pid 20608), rec_exam8 launcher (pid 19600) all running. Disk: free space dipped to 3.3 GB at ~20:00 UTC (external) and
was back at 15.1 GB by 20:11; this workspace's cache is 1.4 GB (it9/ adds ~2 MB). Catalog after iteration 9: 18 open (X5, X7, X9,
X18, X26, X27, X33, X36, X37, X44, X51, X53, X57, X59, X60, X66, X70, X72). Iteration 9 wall time ~66 minutes.
25. THE SELECTION AMONG FLAGGED INSTANTS IS MOSTLY UNEXPLAINED (X72; `select9.py`, results/select9.json; lab feeds, decision
    label; flagged = the top 3% of the FULL hazard with the threshold from A): P(decision | flagged) 27.1% (A), 20.4% (C). Taken vs
    skipped, fit on A's 1,794 flagged instants, scored on C's 1,094: public features (fee-aware edge at k = 1 and 8, gain, cost,
    tick, other trades, rel, |ask - 0.5|, ask change, touch age) AUC 0.578; + the operator's set state (own state) 0.602; the set
    state alone 0.601; the FULL score itself 0.570. Quantified unexplained part of the timing component: given that the trigger
    fires, which instants the bot takes is close to random in every recorded public input (AUC 0.58).
