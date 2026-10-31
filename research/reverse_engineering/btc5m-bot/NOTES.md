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
