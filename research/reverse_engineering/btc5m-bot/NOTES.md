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

### Iteration 10 (2026-10-31 21:04 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 21:04 UTC): released
lots none; this iteration runs inside the sealed block 10-31 18-24, and 11-01 00-06 is sealed too, so there is no new live development
data until 11-01 06:00. Every live analysis uses the 10-31 12-18 development block (my unthrottled book from 14:55). Shared recorder
running (`live.py status` 21:05 UTC: clob_crypto, clob_wallets, rtds, sports connected). Nothing sealed was read.

Panel after iteration 9 (panels/iter9_*.md): 14 proposals, added as X73-X86. Priority-1 proposals tested first: information P1 (the
150-ms taker delay, X73), mechanics P1 (ghost orders, X77) with assumptions P5 (never-filled remainders, X86), assumptions P1 (the
large-order lean and a PnL ceiling with the size feedback re-simulated, X82).

Competing explanations at the start of iteration 10 (about the parts still open: the selection among trigger instants, and what
drives the per-window PnL), and what separates them:
- F1 deterministic trigger + invisible lost races: the bot acts on (nearly) every strong venue tick; under the 150-ms taker delay it
  loses many races, and its lost-race bids at the old ask are cancelled unfilled after ~0.1-1 s, so the 'skips' are hidden
  decisions. Separates: menu-size bids at o's old ask with a cluster-like life (>= ~100 ms floor) concentrate after big moves and
  at the instants the cluster 'skipped'; decisions per filled order >= 2; P(decision | top 1%) >= 40% on the complete label.
- F2 memoryless thinning: a constant hazard (~0.09 per 100 ms) while the trigger state lasts (rate limit, random jitter, a token
  bucket). Separates: episode take rate = 1 - (1 - p)^n by run length; no point-in-time feature beats the in-state indicator.
- F3 evidence accumulation with hysteresis: one decision per episode when an accumulated composite crosses a threshold.
  Separates: the hazard rises with accumulated evidence, not with time in state; episode-level AUC >= 0.70.
- F4 a window-level rate (free collateral after REDEEMs, a schedule, the operator's set state): separates: window random effects
  explained by the collateral path or a schedule; AR(1) of window effects.
- F5 the per-window PnL is the large-order lean, set by own-state feedback (first large order, then pyramiding) and seeded by race
  outcomes: a coin with respect to the outcome. Separates: large-only PnL carries the window PnL; the feedback test-retest ceiling
  falls below 0.5 if sizes are re-drawn from the own-net rule under independent race outcomes.
- F6 the lean is set by public information at the first strong event (tick strength): separates: the first large order and
  sign(netLarge) are predictable from public features at the decision (within-wallet AUC >= 0.75; sign agreement >= 70%).
- F7 a queue-position strategy under the delay: the wallets are parallel places in the delay FIFO; participation depends on free
  wallets (pending orders lock a wallet for D + RTT). Separates: per-wallet gap floor = D + RTT; P(decision | flagged) rises
  with the number of free wallets.

Data added (iteration 10):
- `it10/ghost_cand.parquet`: every positive size increment at a level that was o's ask in the previous 300 ms (the lost-race
  geometry), 10-31 14:55-17:55, 208,198 rows (41,218 of 30 / 60 / 100 shares), with base size, fate (filled / cancel / censored
  at 10 s), life, fill tx, Binance USD-M BTC move toward o over [s - 800, s - 200); `it10/rem10.parquet` (T-first remainders
  looked up in the book).
- V2 calldata of 500 sampled match txs of the shared recorder's `clob_wallets` markets (sports / esports / events, 10-31 12-18,
  decoded in memory only; results/ctl10.json) as the no-delay control.
- `it10/cdall10.parquet`: V2 calldata (decoded fields only) of every BTC 5m match tx my book recorded in 10-31 14:55-17:55 that
  was not already in cd9 (~36k txs, fetched 21:27-21:47 UTC), and `it10/txms10.parquet` (match server ms per tx).

Findings (iteration 10):
1. THE TAKER DELAY IS REAL AND MEASURED (X73 = panel-information P1, steps 1-3; `delay10.py`, `ctl10.py`, results/delay10.json,
   ctl10.json). Fresh-signed taker orders of other wallets in cluster txs (cd9, 10-31 13:00-17:55): sign-to-match q1 per hour
   186.5-189.8 ms (q5 192.7-203.5 ms; 10 fast wallets have their minimum at 186-199 ms). Control: fresh-signed taker orders on
   the shared recorder's sports / esports / event markets: two wallets at a 35-73 ms floor (markets without a delay) and the rest
   at ~1,033-1,046 ms (q5 1,034 ms: the in-play sports delay). So D ~ 150 ms on BTC 5m plus ~35 ms of signing and posting, as the
   changelog says (150 ms since 09-04 14:00 UTC). Per-wallet gap between consecutive cluster taker matches: DS q1 254 ms (min 123,
   6 of 1,017 gaps < 240 ms), GF q1 196 ms, XM q1 152 ms; across wallets 11% of gaps < 100 ms (the fan-out). The decision instant is
   the arrival a = m - 150 ms and the bot's last input is ~m - 180 ms.
   Point-in-time fix, scored on 16:04-17:55 (exam feeds, 778 taker matches; nothing fitted): the vote over [m - 650, m - 180)
   (= [a - 500, a - delta), delta = 30 ms) agrees 83.3% on 67.6% voted (placebo 50.2%) vs the frozen [m - 600, m - 100) 83.2% on
   65.8% (placebo 52.7%); full coverage 75.5% vs 74.7%; [m - 700, m - 200) 82.7%, [m - 750, m - 250) 80.9%, [m - 800, m - 300)
   78.2%. Price: o's ask at m - 180 is within a tick for 90.7% (exact 72.1%) vs 92.3% (78.2%) at the frozen m - 50; m - 250 85.9%,
   m - 400 78.7%. The PIT-clean versions cost <= 1.6 points: PRE-REGISTERED in final_rule.py (side_live_decision_pit,
   price_live_book_pit, presence_live_decision.pit_label = the frozen hazard scored against a match in [t + 180, t + 680)), first
   clean test 11-01 06-12, reported next to the frozen versions.
2. EVERY DECISION LEAVES A BOOK TRACE (X86 = panel-assumptions P5; `ghost10.py`, results/ghost10.json): of 271 T-first orders
   with an unfilled remainder and no maker fill, 88.2% have the remainder's insertion at (o, L) 17-33 ms before the trade message
   (filled-later remainders 97.4%); by wallet DS 88%, GF 88%, XM 89%; 30-share 87.5%, 100-share 95.7%. Lifetime to the removal
   (found, cancelled): p25 94 ms, median 240 ms, p75 789 ms, p90 3.0 s (the 2-c band and 30-ms coalescing add some short false
   cancels). No class of submission (FAK, rejected) is missing at scale.
3. GHOST LOST RACES: ATTRIBUTABLE ONLY FOR XM'S 60-SHARE LEGS, AND THEY SIT IN VISIBLE EVENTS (X77 = panel-mechanics P1; ghost10,
   `ghost10b.py`, results/ghost10b.json). The crowd places 30-share bids at the old ask 41.7k times in 3 h (median life 48 ms) and
   other bot sizes too (20: 18k, 24: 12.6k, 64: 2.4k, 88: 2.0k, 50: 2.6k), so size and lifetime cannot attribute DS / GF ghosts.
   Every size class is 4-8x over-represented 0-300 ms after a visible cluster event on the same token (co-racing). XM uses 60
   shares on 10-31 and has one in-flight order: crowd classes follow DS : GF : XM visible events ~2.7 : 1 : 1 (XM-preceded share
   0.21), the unknown 60-share insertions 287 : 112 : 23 (0.05). So >= 313 of the 422 unknown 60-share insertions within 300 ms of a
   cluster event are XM's ghost legs (median life 527 ms). XM's 363 filled 60-share orders of 14:55-17:55 are ALL maker-first (0
   won races): XM makes >= 1.86 decisions per filled 60-share order (<= 4.4 if every unknown 60 were XM's). The non-co-occurring
   60s (815) are consistent with the crowd's own 60-share orders (expected ~870 from the crowd's co-occurrence rate), i.e. ~0-180
   XM ghosts in fully invisible events.
4. THE SKIPPED FLAGGED INSTANTS ARE NOT HIDDEN DECISIONS (X77 step 5 / X83; `flag10.py`, results/flag10.json; frozen FULL design,
   decision label, fit A, scored C, AUC 0.728): unknown old-ask insertions on o in [t + 100, t + 900) per instant, skipped vs taken:
   top 1%: 60-share 0.097 vs 0.404 (ratio 0.24), 100-share 0.34 vs 0.75 (0.46), 30-share 4.0 vs 6.1 (0.66), crowd sizes 11.7 vs
   22.3 (0.53); top 3%: 0.17 / 0.31 / 0.49 / 0.43. If the skips were the bot's unfilled lost races, the 60- and 100-share rates at
   skipped instants would approach the taken rates relative to the crowd; they fall further than the crowd's: at most ~12% of the
   skipped instants carry a hidden decision with XM's participation rate. F1 rejected: the selectivity is real (the 1.45-1.7
   decisions per filled order of iteration 9 stand for DS / GF; XM's legs are under-counted, finding 3).
5. THE TAKE PROBABILITY IS FRONT-LOADED AT THE EPISODE ONSET, NOT ACCUMULATED AND NOT MEMORYLESS (X83 = panel-assumptions P2;
   flag10, `flag10b.py`, results/flag10b.json; episodes = runs of top-3% points, gaps <= 1 s): episode take rate A 41.7% (252
   episodes), C 35.3% (173) vs 27.1% / 20.4% per grid point; the panel's constant-hazard null (p = 0.094 per point, fitted on A)
   reproduces C by run length (9.7 / 29.6 / 38.8 / 61.3% vs 9.4 / 22.0 / 44.0 / 78.5%) but the hazard of the FIRST decision by step
   since onset is 26.2% (A) / 23.1% (C) at the first flagged point, then 4.7 / 4.8 / 8.4 / 4.3 / 4.9% (A) and 3.8 / 2.4 / 4.3 /
   4.4 / 6.4% (C) at steps 1, 2, 3-5, 6-10, 11+. At the onset the take rate rises with the onset tick on C (terciles 17 / 28 / 50%;
   A 23 / 29 / 29%). Discrete-time hazard fit on A, scored on C (per-step AUC): step dummies 0.723, + instantaneous terms 0.735,
   + accumulated evidence (cumulative tick, max tick, ask change since onset, venues agreeing) 0.728. F2 and F3 rejected: the bot
   reacts (or not) to the event that opens the flagged state, with probability ~1/4-1/2 that rises with its strength, and rarely
   later in the same episode. Window overdispersion against the null replicates (chi2 / df 2.01 on A, 1.97 on C).
   (The episode-level AUCs printed by flag10b use only the hazard rows, which truncates taken episodes; they are not used.)
6. BUSY WALLETS DO NOT SUPPRESS DECISIONS (X73 step 3, own state reported separately; flag10b): wallet busy at t = a taker match in
   (t - 100, t + 150]; P(new decision on o in [t + 250, t + 600) | flagged) by busy wallets 0 / 1 / 2: A 18.1% / 27.9% / 36.2%,
   C 12.9% / 27.8% / 22.2%. Decisions cluster (fan-out); they are not limited by free slots: F7 rejected as a selection rule.
7. THE PER-WINDOW PnL IS THE LARGE-ORDER LEAN, AND THE SIZE FEEDBACK CUTS WHAT ANY REPLAY CAN REACH (X82 = panel-assumptions P1;
   `lean10.py`, results/lean10.json, lean10_v3.json; VALIDATE 1,904 windows, large = filled shares > 1.5 x the day's modal size):
   corr(window PnL, large-only PnL) pooled 0.77 (DS 0.53, GF 0.90, XM 0.81; halves 0.77 / 0.78), small-only 0.06 (DS 0.67, GF
   -0.13, XM 0.18); var(large) / var(total) 1.51; corr(PnL, netLarge x (2Y - 1)) 0.75; sign(netLarge) agrees with the outcome
   48.8% (DS 47.4, GF 49.2, XM 48.9%): a coin. P(large | operator net state on o) short 9.6%, flat 13.5%, long 17.9%; large orders
   sit on the long leg 56.8%, short 33.3%, flat 9.9%. Replays of the observed decisions with independent race outcomes
   (fill probability q per decision; r = mean over 100 replay pairs):

   | size rule in the replay | q = 0.61: r (rho) pooled | DS / GF / XM | q = 0.70: r (rho) pooled | DS / GF / XM |
   |---|---|---|---|---|
   | V0 sizes fixed (iteration-9 assumption) | 0.70 (0.70) | 0.61 / 0.69 / 0.60 | 0.77 (0.77) | 0.70 / 0.77 / 0.69 |
   | V3 coupled monotone (most deterministic own-net rule) | 0.50 (0.52) | 0.53 / 0.54 / 0.53 | 0.58 (0.59) | 0.62 / 0.62 / 0.62 |
   | V1 state-consistent (observed size if same state) | 0.47 (0.49) | 0.52 / 0.47 / 0.49 | 0.55 (0.57) | 0.61 / 0.56 / 0.57 |
   | V2 full re-draw from the state table | 0.50 (0.46) | 0.52 / 0.41 / 0.53 | 0.57 (0.53) | 0.59 / 0.48 / 0.59 |

   With the own-state size feedback the TRUE rule replayed under independent races correlates with itself at only 0.47-0.58
   pooled (0.41-0.62 per wallet): condition 5 (>= 0.5 Pearson and Spearman, per wallet and per half) is at the edge of what even a
   perfect decode can reach, and any replica that reproduces fewer than all decisions falls below it. Selection overlap
   (iteration-9 finding 24) is no longer the only binding term; the race lottery amplified by pyramiding is. This is the
   quantified account of condition 5 (XM's lower q from finding 3, q <= 0.54 for its 60-share legs, lowers XM further).
8. THE TRIGGER UNIT AS A BINANCE BOOKTICKER EVENT (X78 = panel-mechanics P2; `evt10.py`, results/evt10.json; clean events, no
   cluster decision in [tau - 600, tau + 150); label = decision on o in [tau + 150, tau + 700)): 28,070 (A) / 30,812 (C) events,
   base 6.2% / 4.7%. PRICE-level changes (293 / 181 events) 30.0% / 28.7% (0.05-0.2 bp 40.5% / 34.1%); size-only DEPLETE 5.8% /
   4.7% and REFILL 6.1% / 4.4% = the base rate (the panel's queue-depletion trigger is not supported per event). o's ask moved by
   tau + 150: PRICE 41.9% / 40.5% vs unchanged 28.6% / 25.7%; OKX / Bybit agreeing in [tau - 100, tau]: 0 / 1 / 2 venues 4.4 / 6.6
   / 12.5% (A), 3.4 / 5.4 / 10.6% (C). Logistic fit A, scored C: AUC 0.681 vs the Polymarket-activity baseline 0.574; top 10% of
   events 12.7%; precision at matched volume 15.1%. A Binance price-level tick with other venues agreeing is the strongest event
   class, but no event class reaches 40%: the per-event take probability stays the open part.
9. THE REMAINDER CANCEL IS TIMER-LIKE, NOT TICK-TRIGGERED (X79 = panel-mechanics P3, first step; `rmv10.py`, results/rmv10.json;
   196 never-filled remainders with a located removal; life q10 / 50 / 90 = 44 / 264 / 2,793 ms): at the removal vs a control
   instant drawn inside the same order's life, o's ask is >= L + 1 c in 100% vs 99.5% (>= 2 c 57% vs 51%), o's bid is above L
   (outbid) 47% vs 37%, a Binance / OKX tick toward o in the 300 ms before 3.1% vs 4.6% and against o 1.5% vs 0%; at the insertion
   the ask was still L (99%). The market has left the level for the whole life, so "leave when the ask moves k c above L" does
   not discriminate; an adverse-tick cancel is rejected; being outbid adds ~10 points. Best description: a drawn time-to-live of
   ~0.1-1 s with a long tail. The maker-echo replica (steps 3-4) is not built.
10. EXAM PATH WITH THE PRE-REGISTERED PIT KEYS (smoke test, `evaluate(1793464500, 1793466300)` = 10-31 16:35-17:05, development,
    118 s; the historical part fails for 10-31 as in iterations 8-9 and the live-only path returns): frozen vote 87.5% (full
    coverage 78.5%), PIT vote 85.2% on 55.1% voted (placebo 37.9%; full coverage 79.4%); price within a tick 92.9% (frozen m - 50)
    vs 88.6% (PIT m - 180; exact 72.9%); hazard AUC 0.652 vs 0.573 (frozen label) and 0.642 vs 0.573 on the PIT label (gain +0.069,
    window bootstrap [0.049, 0.090]). The PIT versions cost 1-4 points and keep every live component's gain.
11. POLYBOLT PUBLIC CHANNEL RECORDER (X76 = panel-information P4): the AsyncAPI contract (HTTP 200, 63 KB, read 21:35 UTC) lists
    price.polymarket as public (no auth; filter {asset_id}; envelope with producer ms, seq, snapshot, dropped). `code/rec_pb10.py`
    (launcher pid 15792, started 21:36 UTC) sleeps until 11-01 06:00 UTC (a development block start) and records feed btc5m_pb
    through tools/live.py's Writer until 11-02 12:00 UTC (cap 150 MB; acks and counts are written to its status file only in
    development blocks). Whether the subscription is accepted is unknown until 06:00 (no probe was run in the sealed block).
12. CHASE EPISODES WALK UP WITH THE VENUE MOVE, WEAKLY (X80 = panel-mechanics P4, descriptive first step; `chase10.py`,
    results/chase10.json; 2,155 decisions = taker-first orders at the match + located lost races at the insertion, 10-31
    14:55-17:55, any wallet; episodes = same window and outcome, gaps < 1 s): 1,174 episodes (499 with >= 2 decisions; n median 1,
    p90 3). Limit steps inside episodes: up 532 / flat 255 / down 194. Reach = max limit - o's ask 500 ms before the first decision:
    q10 / 50 / 90 = -1 / 0 / +3 c, rising with the episode length (median 0 / 1 / 1 / 3 c for 1 / 2 / 3 / 4+ decisions). At the
    stop, o's ask 1 s after the last decision is above the max limit in 68% (median +1 c). Reach vs the delta-scaled Binance move
    since the start: Spearman 0.20, OLS reach = 0.61 c + 1.00 x (100 Delta dS): consistent with a reservation price
    R = mid0 + 1.0 Delta dS + ~0.6 c that the bot chases up to, but the fit is loose (rho 0.20). The interval regression of the
    panel (submit / stop bounds, fit on A, scored on C) is not done.
13. THE CROWD'S SIGNING TIMES ARE NOT A VENUE TRIGGER: THE CROWD FOLLOWS POLYMARKET (X74 = panel-information P2;
    `fetchcrowd10.py`, `crowd10.py`, results/crowd10.json, crowd10_fast.json; calldata of 45,045 recorded BTC 5m match txs of
    10-31 14:55-17:55 plus cd9): 47,366 non-operator taker orders with a match ms; sign-to-match p1 187 / p5 195 / p25 272 /
    median 556 ms / p90 2.4 s (the 150-ms hold plus a spread of client latencies). Decisions on one clock: crowd = sign ms of
    fresh-signed BUYs; cluster = m - 180 (taker matches) or insertion - 180 (lost races). 100-ms grid x outcome, label in
    [t, t + 100), venue inputs only (six series over [t - 100, t) and [t - 500, t), BTC composite, venues agreeing, a Binance
    price-level change in [t - 150, t)); fit A, scored C:

    | crowd set | decisions (wallets) | crowd label: venue model / PM-activity baseline | cluster label: frozen crowd model / cluster venue model / PM activity | P(cluster | crowd in the same 100 ms) vs not | top 3% of crowd model: P(crowd) / P(cluster) / cluster recall | taken vs skipped AUC (top 3%) |
    |---|---|---|---|---|---|---|
    | fresh 180-2,000 ms | 28,293 (1,896) | 0.599 / 0.632 | 0.606 / 0.655 / 0.657 | 2.1% vs 0.81% | 30.5% / 5.9% / 18.6% | 0.702 |
    | fast 180-260 ms | 7,903 (763) | 0.540 / 0.656 | 0.572 / 0.655 / 0.657 | 3.2% vs 0.89% | 4.9% / 4.1% / 12.9% | 0.666 |

    The panel's signature (a venue input with crowd AUC >= 0.75 that lifts the cluster's taken-vs-skipped AUC to >= 0.65) is
    not met for the crowd: even the fastest fresh-signed takers are predicted better by Polymarket activity than by the venues
    (0.54-0.60 vs 0.63-0.66). The crowd that races the cluster is mostly Polymarket-feed driven; the cluster's side is venue
    driven (83%), and its decisions co-occur with crowd decisions 2.6-3.6x. Among the instants the crowd model flags, the venue
    features separate the cluster's taken from skipped ones at AUC 0.67-0.70 out of sample (select9's grid-point unit: 0.58), the
    best selection number so far but far from a rule. Caveat: on the 100-ms decision clock the cluster's own venue model reaches
    only 0.655, no better than Polymarket activity (0.657): the venue tick decides the side more than the instant.
14. THE DELAY REGIMES AS NATURAL EXPERIMENTS: THE MAKER SHARE MOVES, BUT NOT WITH D ALONE (X75 = panel-information P3, block-level
    first step; `delayreg10.py`, results/delayreg10.json; the four operator wallets' OrderFilled logs, hour 16-17 UTC on
    Monday-Thursday around each changelog date; every fill is on the V2 exchanges already in August; drpc's free plan now limits
    eth_getLogs to ~100 blocks per call (10-31 21:50 UTC: 200+ blocks -> HTTP 400 "ranges over 10000 blocks are not supported on
    free plan"; publicnode refuses archive ranges without a token), so the sample is one hour per day). Maker share of the
    cluster's fills (DS + GF + XM): D = 250 ms (08-10..13) 45.1% (days 23 / 43 / 57 / 50%) -> D = 50 ms right after 08-17
    (08-18..21) 25.8% (26.5 / 25.1 / 25.6 / 26.1%), change -19.2 points, day-bootstrap CI [-28.0, -6.4] (as the delay-queue
    mechanism predicts); but two weeks later at the same D = 50 ms (08-31..09-03) 57.8% (52 / 62 / 63 / 55%), and after the rise
    to D = 150 ms (09-07..10) 47.4%, change -10.4 [-19.6, -2.8], the OPPOSITE of the prediction. Fills per active hour also
    moved 1.5-4x between the periods (GF 93 / 277 / 371 / 128, DS 275 / 424 / 788 / 335). The 08-17 drop is consistent with lost
    races in the delay queue, the later levels are not: the maker share follows something else as well (activity / volatility,
    bot versions, the crowd's adaptation). The panel's full design (fills per window normalized by realized vol and the crowd's
    volume, a placebo distribution of step sizes) is the next step; tried, not decisive.

Panel proposals of iteration 9 (catalog X73-X86) and what happened to them:
- X73 (information P1, taker delay): tried (findings 1, 6, 10). D = 150 ms measured against a no-delay control; PIT-clean side,
  price and hazard label pre-registered; busy state does not suppress decisions. Step 5 (queue model of q) not done.
- X74 (information P2, the crowd's signing times): see finding 13.
- X75 (information P3, delay regimes as natural experiments): open (needs the July-October fill history and pmxt hours).
- X76 (information P4, PolyBolt public channel): recorder launched for 11-01 06:00 UTC (finding 11); open until compared.
- X77 (mechanics P1, ghost orders): tried (findings 3-4). Selectivity is real; XM's ghost legs sit inside visible events.
- X78 (mechanics P2, bookTicker event unit): tried (finding 8). Price-level ticks + venue agreement; depletion is not a trigger.
- X79 (mechanics P3, cancel rule): first step (finding 9): timer-like; the maker-echo replica is open.
- X80 (mechanics P4, chase / reservation price): first step (finding 12); the interval regression is open.
- X81 (mechanics P5, live state-machine replica for condition 5): ruled out by the X82 bound (finding 7).
- X82 (assumptions P1, large-order lean and the feedback ceiling): tried (finding 7).
- X83 (assumptions P2, episodes vs constant hazard): tried (finding 5).
- X84 (assumptions P3, large stream as a state machine): partial (finding 7 state table); initiation test open (needs 11-01).
- X85 (assumptions P4, window-level rate): overdispersion replicated (finding 5); collateral path open.
- X86 (assumptions P5, never-filled remainders): tried (finding 2).

Timing note for the next iterations: the current block (10-31 18-24) and 11-01 00-06 are sealed, so new live development data
starts only at 11-01 06:00 UTC. Iterations that run before then should take the historical directions: X75 (July-October
history around the 08-17 and 09-04 delay changes; V1 / V2 exchange addresses to verify), X60 / X18 (pmxt v2 hours of the 250-ms
regime with server ms and tx hashes), X59 (per-block match clock for h1), X66 / X70 (baseline audit with bot-size print counts
and W4 removed), X85 / X27 (collateral path from USDC Transfer logs), X33 / X53 (rebate tiers), X9 / X26 (full-history change
points), X5.
16. THE RACE IS PARTLY A FIFO QUEUE IN THE DELAY BUFFER (X73 step 5; `queue10.py`, results/queue10.json; 2,155 located decisions
    of 10-31 14:55-17:55 = 1,326 won races + 829 lost races, arrival a = match - 150 ms or insertion - 150 ms; 40,224 crowd taker
    BUYs with match ms): crowd orders AHEAD of the cluster's arrival (crowd matches on o in [a, a + 150)): P(won) 67.4% with none
    ahead (n = 1,130), 63.3% with one (545), 45.8% with two or more (480); DS 80.1% vs 68.7%, GF 72.2% vs 61.4%, XM 12.0% vs 17.2%
    (XM's races are lost to the operator's own earlier legs). Orders queued ahead lower the win rate, but a third of the races
    with nobody ahead are lost too: the maker requotes during the hold (iteration 9: 28% of the asks aimed at were requoted
    away) and complement-side or sell-side takers (not counted) account for the rest. q is therefore partly predictable from the
    queue, which the replica of condition 5 cannot see historically.
17. BOT VERSIONS: FRESH-SIGNED ORDERS UNTIL 08-18, PRE-SIGNED LADDERS FROM 08-22 (X9 / C4 and X75; `version10.py`, `version10b.py`,
    `version10c.py`, `version10_table.py`, results/version10*.json; per day hour 16-17 UTC, the operator wallets' fill logs in
    100-block chunks, 80 sampled txs, V2 calldata decoded in memory): share of the cluster's orders signed inside the ladder burst
    phases (rel -89.5 / +42 / +173 s), the size menu and the taker-order share:
    - 08-01..18: 2-16% in the bursts (orders signed FRESH at decision time); ONE size per day that changes almost daily (90, 60,
      60, 60, 60, 60, 50/100/30, 100, 100, 20, 50, 100, 80, 80, 50, 50, 30); taker-order share 0.15-0.76;
    - 08-19..21: 28-36% (transition; 30 / 60 / 90; taker-order share 0.72-0.86);
    - from 08-22: 99-100% PRE-SIGNED two-size ladders (30 / 90 on 08-22, 25 / 75 on 08-23..25, 50 / 150 on 08-26..31; 20 / 60 /
      80 / 200 on 09-01 and 09-08); taker-order share 0.65-0.74 (08-22..24), 0.29-0.59 (08-26..31).
    The switch to pre-signing falls between 08-21 and 08-22 16:00 UTC, five days after Polymarket cut the taker delay from 250 to
    50 ms (08-17 11:00): with a short hold, the ~30-40 ms of signing became a large share of the race, which pre-signing removes
    (hypothesis). The maker-share path of finding 14 follows the versions: within the fresh-signed version the delay cut lowered
    it 45% -> 26% (the delay-queue prediction); the pre-signed GTC ladder raised it again (58% in late August). The 09-04 rise to
    150 ms coincides with a lower maker share (47%), against the prediction; the September scan (version10c) is below.
15. (written after 16-17) VOLATILITY DOES NOT EXPLAIN THE MAKER-SHARE STEPS (X75 follow-up; `vol10.py`, results/vol10.json; Binance
    spot BTCUSDT 1-s klines by REST for the 16 sampled hours, not cached): corr(maker share, log 1-s realized vol) = -0.15 across
    the hours; OLS of the maker share on log vol plus the period dummies (base D = 250 ms, 08-10..13): log vol -0.03, D = 50 ms
    right after 08-17 -0.16, D = 50 ms late August +0.16, D = 150 ms after 09-04 +0.04. The period effects are not volatility;
    they line up with the bot versions of finding 17.

PRE-REGISTERED replication targets for the next development block (11-01 06-12 UTC), written 10-31 ~22:01 UTC before any 11-01
data exists (code unchanged: ghost10 / ghost10b / flag10 / flag10b / evt10 / queue10 / crowd10 with the interval constants moved
to the block):
- R1 (taker delay): the fresh-signed sign-to-match q1 per hour lies in 180-200 ms.
- R2 (PIT live components, final_rule): side_accuracy_live_decision_pit >= 0.80 on voted decisions; price_within_tick_live_pit
  >= 0.85; presence_live_decision pit_label gain over the PM-activity baseline > 0 with the window-bootstrap CI above 0.
- R3 (skips are not hidden decisions): at top-1% skipped instants, unknown 60-share (XM size) old-ask insertions per instant
  <= 0.5 x the taken-instant rate, and below the crowd-size ratio.
- R4 (onset hazard): first-decision hazard at the episode onset point >= 2x the mean hazard of steps 1-10.
- R5 (event unit): Binance USD-M price-level events have P(decision) >= 3x the base rate of clean events.
- R6 (queue): P(won | 0 crowd orders ahead) - P(won | 2+ ahead) >= 0.10 pooled.
- R7 (crowd): the crowd label's venue-model AUC stays below its Polymarket-activity baseline.

18. THE LARGE SIZE IS NOT PLACED AT EPISODE ONSETS (X84 = panel-assumptions P3, quick live check; results/large10.json; 2,155
    sized decisions of 10-31 14:55-17:55, large >= 90 shares = 5.2%): P(large) 4.7% at the first decision of an episode vs 5.7%
    later; by episode length 1 / 2 / 3+: 4.9 / 4.2 / 6.0%; by rank in the window 1-5 / 6-20 / 21+: 5.9 / 4.9 / 5.2%; DS 2.3% vs
    3.7%, GF 7.6% vs 7.7%, XM 15.4% vs 6.1% (first vs later). On this Saturday the large share is small and shows no initiation
    structure; the state-machine test (initiation from public features while flat, then pyramiding) needs the weekday blocks.
17b. (addendum to 17, version10c) September and early October: 99-100% pre-signed every day; menu 80 / 200 (+ 20 / 60) on
    09-01..09, then 50 / 100 from 09-10 (75 / 150 on 09-11, 50 only on 09-12..14), 50 / 100 through 09-30, 60 / 100 from 10-02 (to the BUILD start 10-09); taker-order
    share 0.34-0.81. The 09-04 delay rise (50 -> 150 ms) falls INSIDE the 80 / 200 version (09-01..09), so with the version held
    fixed the maker share fell 58% -> 47% when the hold tripled: against the delay-queue prediction. Within the fresh-signed
    version the 250 -> 50 ms cut lowered it 45% -> 26% (for the prediction). The delay is not the main driver of the maker share
    in the pre-signed version; what is (the crowd's speed, the bot's cancel timing, volatility regimes) is open.
19. EXAM PATH ON AN UNCACHED PERIOD (after the getLogs fix): `evaluate(1792692000, 1792699200)` (VALIDATE 10-22 18:00-20:00,
    never evaluated before) runs end to end in 105 s: presence 0.873 vs pure baseline 0.813, side 79.1%, price within a tick
    97.4%, PnL 0.04 / 0.17 (24 windows). Before the fix, cluster_fills would have raised on any uncached period.
Status after iteration 10: target not reached; the frozen historical rule and its VALIDATE metrics are unchanged (primary 0.9132
all seconds; block seconds 0.8747 vs the stronger baseline 0.8211; side 76.7%; price 95.1%; PnL 0.18 / 0.17). What changed is the
account of the two open parts:
- timing / selection: the decision instant is the arrival 150 ms before the match (taker delay measured); every decision leaves a
  book trace; the skipped flagged instants are real non-decisions; the bot reacts to the onset of a flagged state with probability
  ~1/4-1/2 rising with the onset strength, rarely later; busy wallets, accumulated evidence, queue depletion and the stale-quote
  edge do not select. What decides ~1 in 3 onsets is still open (best out-of-sample AUC 0.68-0.74 from every recorded input).
- PnL (condition 5): the per-window PnL is the large-order lean, a coin that race outcomes seed and the own-net size rule
  amplifies; the true rule replayed with that feedback correlates with itself at 0.47-0.58 pooled, so condition 5 is at the edge
  of attainability for a perfect decode, and below it for any partial one. With the side condition not binding in substance,
  presence passing by +0.054, and price passing on the trivial anchor, condition 5 is the binding target condition and it is
  bounded by the bot's own race randomness (quantified: lean10).
- PIT-clean live versions pre-registered (vote [m - 650, m - 180), price at m - 180, hazard label [t + 180, t + 680)).
- Bot versions decoded for August-September: fresh-signed orders with one size per day until 08-18, pre-signed ladders from
  08-22 (five days after the 250 -> 50 ms delay cut); the delay regimes are confounded with these versions (finding 17).
- Exam path made robust to drpc's new getLogs limit (finding 19): without the fix the examiner's run on h1 would have failed.
Recorders at the end: shared (pid 27184), rec_lab6 v2 (pid 14304), rec_exam7 (pid 32576), rec_fam8 (pid 20608), rec_exam8 launcher
(pid 19600), rec_pb10 launcher (pid 15792, starts 11-01 06:00). Disk: 14.9 GB free; this workspace's cache is 1,450 MB (it10 20 MB),
just under the 1.5 GB cap: the next iteration should prune before fetching (bybit_ob 289 MB and cells 360 MB are the candidates).
Shared recorder at the end (live.py status 22:08 UTC): process running; clob_wallets, rtds and sports connected; clob_crypto reconnecting after a 'slow consumer: send buffer full' close at 22:07:52 UTC (99 reconnects since the start; the recorder retries by itself and was not touched). Iteration 10 wall time ~65 minutes.

## Next (iteration 11)

1. If the iteration runs before 11-01 06:00 UTC (no new development data), take the historical directions: X75 continued (the
   July-October history around 08-17 / 09-04: fills per window and maker share by day, pay-up share and fan-out legs from a 2-h
   calldata sample per week), X60 / X18 (pmxt v2 hours of the 250-ms regime with server ms: the per-wallet gap floor, predicted
   ~340 ms if it is D + RTT; the tick-to-match kernel shifted by +100 ms), X59 (per-block match clock for the h1 side), X66 / X70
   (presence baseline with bot-size print counts, sub-second intensities and W4 removed), X85 / X27 (collateral path from USDC
   Transfer logs vs the window-level take rate), X33 / X53 (rebate tiers), X9 / X26 (full-history change points), X5.
2. On 11-01 06-12 (development): score every pre-registered test (PIT vote / price / hazard label, full-coverage side,
   edge_rule_V8, size-from-tick); replicate ghost10 / flag10 / flag10b / evt10 / crowd10; compare btc5m_pb (PolyBolt) with
   btc5m_clob_raw2 (X76: limit == PolyBolt ask at a - delta?); X84 initiation of the large stream at decision level.
3. X79 steps 3-4 (maker-echo replica with the timer-like cancel), X80 interval regression, the queue model of finding 16 with
   the complement-side and sell-side takers counted.
4. X9 / C4 continued: the version history of July (XM from 06-20, DS / GF from 07-19/20) and of 09-01..10-08 (version10c),
   decoded per version; check the 08-22 switch against the changelog (C4b).
5. Still open from earlier: X5, X7, X9, X18, X26, X27, X33, X36, X37, X44, X51, X53, X57, X59, X60, X66, X70, X72; new: X76,
   X84, X85.
Environment note (10-31 21:50 UTC): drpc's free plan now refuses eth_getLogs ranges above ~100-199 blocks (HTTP 400 with the
message "ranges over 10000 blocks are not supported on free plan"), and publicnode refuses archive ranges without a token. The
older fetchers (fetch_chain*.py, final_rule.cluster_fills) use larger ranges; their cached responses still serve VALIDATE, but
a new period (an exam lot) needs 100-block chunks. FIXED in final_rule.cluster_fills (data loading only, the rule is unchanged): `_get_logs_chunked` tries the 3,000-block range first (cached responses stay valid) and otherwise fetches 100-block chunks with 2 threads and retries; tested on the uncached BUILD hour 10-14 01:00-02:00 UTC: 1,872 fills (T 1,470, M 402) in 15.9 s, i.e. ~25 min of log fetching for a 4-day lot. Without the fix the examiner's run on h1 would have failed in cluster_fills.

### Iteration 11 (2026-10-31 22:46 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 22:48 UTC): released
lots none; this iteration runs inside the sealed block 10-31 18-24 and 11-01 00-06 is sealed too, so there is again no new live
development data (the next development block starts 11-01 06:00; at ~100 min per iteration and 567 budget minutes left, only the
last one or two iterations will see it). Shared recorder running (`live.py status` 22:48 UTC, pid 27184: clob_crypto, clob_wallets,
rtds, sports connected). Nothing sealed was read. Every live analysis uses the 10-31 12-18 development block (lab feeds from 14:55).

Panel after iteration 10 (panels/iter10_*.md): 13 proposals, added as X87-X99 (information P1-P5 = X87-X91, mechanics P1-P4 =
X92-X95, assumptions P1-P4 = X96-X99). Priority-1 first: mechanics P1 (the trigger's normalizer, X92) and assumptions P1 (a
conflated / confirmed venue input, X96) share one onset table and run together; information P1 (London-arrival clock, X87) step 0
(the crowd on the server clock) and step 1 (venue-pair transit calibration) run on 10-31; its new venues get a recorder for the
next development block.

Competing explanations at the start of iteration 11 (the open parts: which onsets it takes, the large-size regime that carries the
per-window PnL, and therefore what any replica can reach), and what separates them:
- G1 normalizer: the take decision compares the onset tick with a scale the bot keeps itself (|tick| / sigma_h >= z*, sigma over
  5-300 s, or a tick count). Separates: z_h lifts taken-vs-skipped AUC at onsets well above bp (0.80 signature); the decision
  rate is flat in the minute's tick count; the take rate is a step in z, stable across A / C.
- G2 pacing: a rate controller thins onsets toward a target rate per window / minute. Separates: P(take | onset) falls with the
  operator's recent decisions (own state, reported apart); decisions per minute under-dispersed (var / mean < 1) within regimes.
- G3 conflated / confirmed input: the bot acts on a snapshot or a tick still in place after a confirmation delay; the skipped
  onsets reverted first. Separates: P(take | reverted by +100 ms) at the base rate, P(take | survived) >= 50% in every strength
  tercile; the (a - onset) kernel is flat-topped with the snapshot period as its width.
- G4 London-arrival race: the bot sits next to Polymarket's engine (Europe) and reads several venues, each with its own transit;
  selection is a parity gate against makers reading local venues. Separates: the crowd's venue AUC on the server clock beats
  Polymarket activity; local venues (Deribit, Coinbase) lead Binance's London arrival; per-venue leading edges match one region.
- G5 size regime: the large size follows a slow operator regime or the bot's intentions, not realized fills. Separates: next
  sizes after WON vs LOST large races (exogenous losses) differ by <= 3 points (regime / intention) or carry the own-net signs
  (feedback).
- G6 counterparty last look: the bot fires when o's ask is held by a slow maker. Separates: P(take | slow maker at the touch)
  >= 2x fast; maker class alone separates taken from skipped.
- G7 (how it earns, unlikely to be wrong but restated): rebates + a paired-set edge pay the strategy; the per-window lean is a
  coin. Separates: lean PnL mean ~0 across windows while rebate + set edge carry the total (iterations 6-8 economics).

Data added (iteration 11):
- `it11/onset_A.parquet`, `it11/onset_C.parquet`: evt10's clean Binance USD-M BTC bookTicker events (A 28,070 / C 30,812) with the
  normalizer terms (z_rv_h, z_ev_h, n_h, np_h for h = 5..300 s, within-window percentile), survival at +50..+200 ms, OKX / Bybit
  confirmation, the first decision's (a - tau) and the operator's recent decisions (rec30 / rec60, own state).
- Operator OrderFilled logs per order hash, hour 16-17 UTC on the 16 delayreg10 days (counts only, results/refill11.json); V2 calldata
  of 60 sampled operator txs on each of 08-05, 08-12, 08-15 16:00-16:20 UTC (decoded in memory; results/version11.json).
- New recorder rec_eu11 (European / US venues, alt perps, snapshot streams) from 11-01 05:59 UTC (finding 11).

Findings (iteration 11):
1. NO NORMALIZER: A SELF-KEPT VOL SCALE DOES NOT SELECT THE ONSETS (X92 = panel-mechanics P1; `onset11.py`, results/onset11.json;
   event unit of evt10, fit A, scored C). Out-of-sample AUC: Polymarket-activity base 0.574, evt10 FULL 0.681 (reproduced), the
   normalizer terms without raw bp 0.657, FULL + normalizer 0.697 (gain +0.015, block CI [-0.002, +0.032]). Univariate on C: |bp|
   0.588 vs z_rv_h 0.51-0.57 (h = 5 / 15 / 30 / 60 / 120 / 300 s; the longest is best), tick counts n_h 0.49-0.53, within-window
   percentile 0.584 (= |bp|). Within price-level events |bp| 0.46 / 0.51 and z_rv_5 0.56 / 0.59 (A / C; n 293 / 181). The event-level
   window overdispersion stays (chi2 / df 14.8 FULL -> 11.7 with the normalizer, 16 windows). The decision rate is barely elastic to
   activity (`elast11.py`, results/elast11.json; complete live record, 110 window-minutes): Poisson coefficient of log(1 + Binance
   price-level events in the minute) 0.08 (se 0.18) with the minute's and the trailing 30-min realized vol as controls, 0.18 (0.09)
   alone; minute RV 0.04-0.06; trailing 30-min RV -0.03 (0.18); within-window OLS 0.30 (0.21); decisions per minute var / mean 13.4.
   So the mechanics panel's critique 3 holds on the complete live record (no bp-scaled rate response), but neither form of its
   hypothesis does: (a) z* in self-kept units is no better than bp; (b) a pacing controller predicts under-dispersion and a take rate
   that FALLS with recent decisions, while P(take) RISES with the operator's own decisions on the window in the last 30 s (rec30 = 0 /
   1-2 / 3-5 / 6+: 1.5 / 4.7 / 4.8 / 7.5% on A, 1.4 / 3.6 / 4.4 / 6.2% on C; own state, reported apart). G1 and G2 rejected.
2. NO CONFLATED OR CONFIRMED INPUT (X96 = panel-assumptions P1; onset11): within |bp| terciles P(take | the onset's move still >= 50%
   in place at +D) exceeds P(take | reverted) by only 0.4-2.5 points at D = 50-200 ms (top tercile at +100: C 7.2% vs 5.4%, A 9.4% vs
   6.5%), far from the signature (reverted at the base rate, survived >= 50%). Price-level events survive almost always (180 / 181 on C)
   and are taken at 29% either way. As a diagnostic that the bot could not have used, survival + OKX / Bybit confirmation adds +0.031
   [0.021, 0.042] (0.712 on C), through later ticks (continuation by +150-200 ms univariate 0.62) and venue confirmation (both OKX and
   Bybit moved the same way by +150 ms: 9.7% vs 2.5% with neither on C; 11.5% vs 3.4% on A): more ticks, not a snapshot. The (a - tau)
   kernel of taken clean events is flat over 0-550 ms (~30 per 10-ms bin on A and C): no snapshot period or confirmation delay at
   the event unit. Venue-clock phase locking was already measured by the information panel (Rayleigh Z <= 3.0 at 10-2,000 ms). G3
   rejected; the snapshot streams are recorded for the next development block anyway (finding 11).
3. THE CROWD ON THE SERVER CLOCK STILL FOLLOWS POLYMARKET (X87 step 0 = panel-information P1; `crowd11.py`, results/crowd11_fresh.json,
   crowd11_all.json; every crowd taker re-timed at m - 180 like the cluster): crowd-label venue model 0.582 (fresh set) / 0.587 (all
   40,224 non-operator taker BUYs) vs the Polymarket-activity baseline 0.657 / 0.653 (on sign_ms: 0.599 vs 0.632). The clock was not
   the artefact; the gap widens. On one clock the two co-arrive more tightly: P(cluster | crowd decision in the same 100 ms) 3.2% vs
   0.68% (4.7x; 2.6x on sign_ms), P(crowd | cluster decision) 35.5% (all takers 43%); taken vs skipped among the crowd model's top 3%
   0.670 / 0.699.
4. POLYMARKET'S OTHER CRYPTO BOOKS DO NOT CONFIRM ONSETS (X91 = panel-information P5; `xmkt11.py`, results/xmkt11.json; 9-10k other
   trades per interval on BTC 15m / 4h, ETH and SOL 5m / 15m / 4h, direction-mapped): a same-direction trade in [tau - 300, tau)
   raises P(take) (A 10.7% vs 5.4%, C 6.2% vs 4.4%) but an opposite-direction one raises it about as much (A: BTC-long 9.0%, ETH
   10.0%): activity, not confirmation; on price-level events of C it goes the other way (23.5% with vs 29.9% without; univariate
   0.44-0.50). FULL 0.681 -> FULL + cross-market 0.674 on C.
5. THE SIZE FOLLOWS INTENTIONS, NOT REALIZED FILLS (X97 = panel-assumptions P2; `size11.py`, results/size11.json; 2,155 live
   decisions, 111 large 100-share ones: DS 2.8%, GF 7.7%, XM 9.1%): P(the next operator decision on the SAME outcome within 30 s is
   large) after a large decision that WON 19.1% (n 47) vs LOST 27.1% (48), the opposite of own-net feedback; after a small decision
   3.9% (1,175) vs 3.6% (694); losses with crowd orders queued ahead (exogenous) 27.8% (36). Other outcome after a large decision: won
   0% (50), lost 3.9% (51). AUC of 'large' by the operator's net on o (own state): realized 0.668, SENT (every decision's size, filled
   or not) 0.680; in one logit realized and sent-minus-realized carry similar weights (0.10, 0.09); P(large) is highest with the sent
   net long and the realized net still short (17.6%, n 34): large orders come in bursts sent before the earlier ones fill. Sizing
   reads the bot's intended position or a slow regime, so lean10's realized-fill ceiling (0.47-0.58) is not supported and the ceiling
   for a replay that reproduces the decisions is the fixed-size one, 0.70-0.77 (lean10 V0). Under-powered (111 large decisions on a
   Saturday); the panel's block-clock fill-fraction check (-0.01 +- 0.20) agrees. G5 supported (tentatively).
   Condition 5 restated with iteration 7's strict7 oracle (the wallet's own taker decisions, TRUE sizes, strict fills on the tape):
   per-window r = 0.68 / 0.66 with fills in [s - 1, s + 1] but 0.40 / 0.39 at a latency of 1-3 s: under the latency >= 2 s convention
   the PnL condition is out of reach even for the oracle, and at the block clock the binding terms are decision overlap and the
   large-size regime.
6. THE BOT SEES POLYMARKET'S BOOK ~30 MS OLD (X98 step 2 = panel-assumptions P3; `lam11.py`, results/lam11.json): among the 1,252
   decisions whose o-ask changed in [a - 400, a], P(limit == o's ask at a - Lambda) peaks at Lambda = 30 ms (0.481; 0.455 at 0, 0.391
   at 150, 0.274 at 300; inside the hold, Lambda < 0, a placebo: 0.44 at -30, 0.36 at -120); DS 50 ms (0.544), GF 10 ms (0.445), XM
   30 ms (0.416). Won races peak at 30 ms (0.647), LOST races at 180 ms (0.378): a lost race is a decision priced on an ask that had
   already moved 30-180 ms before the arrival. With the Binance reaction (arrival 100-150 ms after the Binance stamp), the bot reads
   Polymarket ~30 ms old and Binance ~100+ ms old: it runs near Polymarket's engine, far from Tokyo (supports the information panel's
   location argument). The per-venue tau_v and the (Lambda, tau) AUC profile (steps 1 and 3) are not done.
7. THE 'ON' PERIODS ARE DIRECTIONAL: decisions in 30-s bins with >= 5 decisions (165 bins, 10-31 14:55-17:55): mean |share Up - 0.5|
   0.224 vs a binomial null 0.130 (q99 0.151); 12% of such bins fully one-sided; decisions per active 30-s bin q50 / 90 / 99 = 7 / 18 /
   44.
8. AMONG PRICE-LEVEL EVENTS NOTHING PUBLIC SELECTS (`price11.py`, results/price11.json; taken 30.0% A / 28.7% C): univariate AUCs (A /
   C) |bp| 0.46 / 0.51, z_rv_5 0.56 / 0.59, venue agreement 0.58 / 0.53, OKX / Bybit confirmation at +150 0.58 / 0.52, o's ask 0.52 /
   0.64 (C: < 0.3 19%, >= 0.7 39%), activity 0.57 / 0.46, tick counts 0.43-0.61, time in window 0.51 / 0.45 (none taken at 240-285 s:
   0 / 8 on A); own state rec30 0.58 / 0.64 (no recent decision: 0 / 19 on A, 2 / 16 on C). The take decision among the strongest
   onsets is statistically indistinguishable from a coin given every public input recorded, and correlates with the bot's own recent
   activity.
9. REMAINDER TTL AND THE DELAY REGIMES (X94 = panel-mechanics P3): live cancelled never-filled remainders (rem10), life from the
   insertion: DS median 328 ms (q10 45, q90 4,485; n 100), GF 240 (36, 867; 38), XM 124 (48, 747; 12); Weibull shape 0.63-0.77
   (decreasing hazard, no sharp timer); minimum 14-26 ms after the insertion (cancels sent during the hold). Inside one regime the
   hold is a constant 150 ms, so the life from the POST is the life from the insertion + 150 ms and 'sharper from the POST' cannot
   discriminate there. Across regimes (`refill11.py`, results/refill11.json; per order hash, 16 operator hours): P(a taker-first order
   later gets a maker fill) 8.3% (08-10..13, D 250) -> 6.4% (08-18..21, D 50; -1.9 points, day bootstrap [-6.2, +2.6]) and 22.4%
   (08-31..09-03, D 50) -> 17.5% (09-07..10, D 150; -4.9 [-8.8, -0.9]). The 09-04 step has the predicted sign (a longer hold eats the
   resting time), the 08-17 step does not (predicted up). Maker-first share of filled orders 25.7% -> 14.7% at 08-17 and 31.2% ->
   23.2% at 09-04: at 09-04 more lost races should have raised it, so a shorter resting time fits better. Partly supported; levels
   move with the versions (6-8% mid-August vs 17-22% in September).
10. FINDING 17 RETRACTED: AUGUST WAS PRE-SIGNED TOO (X95 = panel-mechanics P4; `version11.py`, results/version11.json; 60 sampled txs
    per day, 16:00-16:20 UTC, calldata decoded in memory): operator orders were signed 3-121 s before their block (08-05: DS taker
    median 48 s, XM taker 61 s, XM maker 60 s; 08-12: DS taker 111 s, XM taker 92 s, XM maker 72 s; within 5 s of the block 1.7-3.3%)
    against a median 2.8-3.5 s for the other wallets' taker orders in the same txs; signing phases in two bursts per window (08-05: 39
    of 61 orders at 0-30 s mod 300, 18 at 150-180 s; 08-12: 45 at 30-90 s, 15 at 180-240 s); one size per day (60 on 08-05; 100 and
    W4's 5 on 08-12); 10-33% of orders share a signing ms. Iteration 10 counted only the October burst phases. The strategy statement
    and FINAL_RULE drop 'fresh-signed until 08-18'; the 08-17 delay cut falls inside one pre-signed schedule, which makes its maker-share
    drop (45% -> 26%) a cleaner natural experiment; no fresh-signed segment (a historical ms decision record) exists in August.
11. RECORDER rec_eu11 (`code/rec_eu11.py`, pid 14192): sleeps until 11-01 05:59 UTC, records to 11-02 18:00 UTC (cap 280 MB, every
    block filed by the Writer, never read in sealed blocks): btc5m_xeu = Coinbase BTC-USD / ETH-USD (level2_50 book top + ticker),
    Bitstamp order_book (microtimestamp), Kraken v2 book, and the SOL / XRP / DOGE / BNB perps on Binance USD-M, Bybit and OKX, sized L1
    coalesced to 30 ms; btc5m_xsnap = Binance USD-M depth5@100ms BTC / ETH, OKX books5 BTC / ETH swaps, Bybit orderbook.50 BTCUSDT,
    every message. All nine subscriptions acknowledged by a probe at 22:55 UTC that read acknowledgement messages only (Coinbase maps
    level2_batch to level2_50).
12. THE RACE IS NEARLY DETERMINISTIC GIVEN THE ARRIVAL (X93 first step = panel-mechanics P2; `race11.py`, results/race11.json;
    2,155 decisions, recorded o-ask at the would-be match time a + 150 + delta): a LOST race would have been won by an arrival
    10 / 25 / 50 / 75 / 100 / 150 ms EARLIER in 3 / 11 / 21 / 31 / 40 / 51% of cases, by a later one in <= 1%; a WON race keeps
    ask <= L for arrivals 25 / 50 / 100 / 150 ms earlier in 87 / 95 / 96 / 97% (the last ~25 ms before the match read 55-58%: the
    30-ms coalescing of the recording and the order of book and trade messages, not the race). Operator near-ties (another
    operator arrival on the same outcome within 5 ms) win 37.2% (n 121) vs 63.0% for clear arrivals: the later fan-out leg loses
    to the earlier one. So on a recorded book a replica that reproduces a decision within 25-50 ms reproduces its race outcome in
    ~93-96% of cases: X82's independent-lottery ceiling applies to block-clock replays (VALIDATE, h1, h2), not to recorded future
    blocks (the mechanics panel's critique 2 holds). The full simulator (queue, maker refills, per-window PnL) is not built.
13. THE REGIME IS INTERNAL, NOT PUBLIC CROWD ACTIVITY (`regime11.py`, results/regime11.json; onset tables): fit A, scored C: FULL
    0.681, + public crowd activity on the window over 5 s and 30 s 0.685, + the operator's own recent decisions (rec30, rec60; own
    state) 0.715, both 0.717; on price-level events 0.535 / 0.579 / 0.599 / 0.589. corr(rec30, crowd30) 0.50-0.56, and within each
    crowd tercile rec30 still raises P(decision) (A top tercile 0.0% / 6.6% / 8.5% for 0 / 1-5 / 6+ recent decisions; C bottom
    tercile 1.2% / 3.7% / 6.2%). The decisions are self-exciting beyond the public activity: the bot has 'on' periods (directional,
    finding 7) whose trigger is not in any recorded public series. Own-state features never count (the brief: own fill counts
    predict activity trivially); this is a mechanism statement, quantified for the wall account.
14. LIVE, THE LARGE SIZE FOLLOWS THE TICK; AT THE BLOCK CLOCK IT DOES NOT SHOW (F6; `large11.py`, results/large11.json; 2,155
    decisions, 111 large): univariate AUC of 'large' for the six-series tick toward o over [a - 530, a - 30) 0.723 (DS 0.733, GF
    0.681, XM 0.745), |tick| 0.705, o's ask change over the last second 0.632, the operator's SENT net (own state) 0.680; fit A
    (to 16:20) scored C: public 0.644, own 0.571, both 0.717. P(large) by tick decile: 1.4-5.6% in deciles 1-8, 10.7% at 0.67-1.88
    bp, 17.1% above 1.88 bp (XM 36-38% above its q90; GF 18-24% at q80-95; DS 8-10% above q90). Historical retest with
    MILLISECOND Binance USD-M aggTrades (`sizems11.py`, results/sizems11.json; 9,728 taker-first calldata orders): the max 300-ms
    move toward o in [bt - 3.0, bt - 0.2] gives within-wallet AUC 0.52 / 0.52 / 0.57 (BUILD) and 0.49 / 0.50 / 0.48 (VALIDATE;
    DS / GF / XM); BUILD-fit scored on VALIDATE 0.48-0.52. The VALIDATE large share is 16-44% against 10-31's 5%: either the block
    clock's 2.8-s window hides the deciding tick, or the size rule differs by menu regime (30 / 60 / 100 on 10-31). The
    pre-registered 11-01 06-12 test (iteration 9) decides; the historical size remains own-state (operator net) only.
15. VENUE STAMPS: OKX ~ BINANCE, BYBIT AND DERIBIT +60 MS (X87 step 1 / X98 step 1, partial; `xcorr11.py`, results/xcorr11.json;
    10-ms microprice changes on exchange stamps, 10-31 14:55-17:55; Deribit 17:46-17:55 only): cross-correlation peak of Binance
    USD-M BTC -> OKX BTC at +10 ms (0.206; 0 ms 0.201), -> Bybit +60 ms (0.196), -> Deribit perp +60 ms (0.269), -> Binance ETH 0 ms,
    -> OKX ETH +10 ms. Around 846 big Binance moves (>= 0.2 bp in 10 ms): OKX had already moved the same way in the preceding 100 ms
    in 87% (after: 73%), Binance ETH 87% (69%), Bybit 60% (91% after). A London host sees a Binance move on Deribit's own feed ~60
    ms after the Binance stamp, ~45-50 ms before Binance's feed arrives (Tokyo -> London ~105-115 ms): a local relay exists (the
    information panel's first signature). Whether the bot uses it needs more Deribit decisions and the European venues
    (rec_eu11 from 11-01 05:59). Note the cluster's kernel peaks (kernel7: Bybit 100 ms before Binance) are not explained by
    Bybit's stamps, which LAG Binance by 60 ms: the per-venue kernels are not simple reactions to the same move.
16. VERSION SAMPLE 08-15: the third day of version11 returned no sample (drpc returned no logs / calldata in time); the retraction
    rests on 08-05 and 08-12 (two schedules) plus the panel's 08-12 sample (202 orders).

Panel proposals of iteration 10 (catalog X87-X99) and what happened to them:
- X87 (information P1, London-arrival clock): step 0 tried (finding 3: rejected); step 1 partial (finding 15: OKX ~ Binance,
  Bybit / Deribit +60 ms on the stamps; Deribit relays Binance moves to London ~45-50 ms before Binance's own feed); steps 2-4 need
  the European venues: recorder rec_eu11 from 11-01 05:59 (finding 11). Open.
- X88 (information P2, alt-perp basket): recorder rec_eu11 (finding 11); historical step 6 not run. Open.
- X89 (information P3, historical match clock): not tested. Open.
- X90 (information P4, maker last look): not tested; related facts in findings 6 and 12. Open.
- X91 (information P5, other crypto books): tried, rejected (finding 4).
- X92 (mechanics P1, normalizer): tried, rejected (finding 1).
- X93 (mechanics P2, race on the recorded book): first step (finding 12); full simulator open.
- X94 (mechanics P3, cancel timer from the POST): tried, partly supported (finding 9).
- X95 (mechanics P4, version history): tried (finding 10: finding 17 retracted).
- X96 (assumptions P1, conflated / confirmed input): tried, rejected (finding 2); snapshot streams recorded.
- X97 (assumptions P2, size-feedback channel): tried (finding 5: no realized-fill feedback; tentative).
- X98 (assumptions P3, bot clock alignment): step 2 tried (finding 6: Lambda ~30 ms); steps 1 / 3 partial or open (finding 15). Open.
- X99 (assumptions P4, PRNG state from salts): not tested. Open.
Also closed with the assumptions panel's measurement: X27 (collateral balances 15-100x a window's spend) and X85 (collateral ruled
out; the window-level rate is the internal self-exciting state of finding 13, cause under X72).

Status after iteration 11: target not reached; the frozen historical rule and its VALIDATE metrics are unchanged (primary 0.9132 all
seconds; block seconds 0.8747 vs the stronger baseline 0.8211; side 76.7%; price 95.1%; PnL 0.18 / 0.17). What changed is the account:
- selection: every public mechanism the panel proposed for choosing the onsets (normalizer, snapshot gate, cross-market
  confirmation, crowd timing) is rejected with measurements; among the strongest (price-level) ticks the take is a coin given every
  recorded public input, and it rises with the bot's own recent activity (an internal, self-exciting, directional 'on' state). What
  remains untested: European venues and alt perps (recording from 11-01 05:59), the maker at the touch (X90), the PRNG (X99).
- size / PnL: no realized-fill feedback; live the large size follows the tick strength (not visible at the block clock); on a recorded
  book the race is deterministic given the arrival. Condition 5 at the block clock is bounded by decision overlap and the
  size regime (fixed-size ceiling 0.70-0.77); under the >= 2 s convention even the oracle reaches 0.40.
- location: the bot reads Polymarket ~30 ms old and Binance ~100+ ms old: it runs next to Polymarket's engine.
- versions: August was pre-signed (finding 17 of iteration 10 retracted).
Recorders at the end: shared (pid 27184), rec_lab6 v2, rec_exam7, rec_fam8, rec_exam8 launcher, rec_pb10 launcher (starts 11-01
06:00), rec_eu11 (pid 14192, starts 11-01 05:59). Cache: it11 adds ~13 MB (onset tables, large_dec); the workspace cache is at the
1.5 GB cap: the next iteration must prune (bybit_ob 289 MB, cells 360 MB) before any fetch.

## Next (iteration 12)

1. If before 11-01 06:00 UTC (no new development data): X89 (historical match clock with all-market anchors on the 10-31 12-18
   truth; the only route for the PIT side / price / hazard to reach h1 / h2), X99 (PRNG strong form: JSC xorshift128+ with z3 on
   dense same-ms copy groups, V8 multi-call variants; if a state is found, the hidden draws between bursts vs flagged onsets), X90
   (maker last look: link touch quotes to maker orders via ins9, rate makers on A, score taken vs skipped on C), X93 (the full
   recorded-book simulator with the wallet's own decisions and per-window PnL), X88 historical step (alt perps at 100 ms into the
   VALIDATE side model; prune the cache first).
2. On 11-01 06-12 (development): every pre-registered test of iterations 9-10 (PIT vote / price / hazard label, full-coverage side,
   edge_rule_V8, size-from-tick, R1-R7), the PolyBolt comparison (X76), and the new feeds: London-arrival clock (X87 steps 1-4:
   Deribit / Coinbase / Bitstamp / Kraken leading edges vs Binance's London arrival, the parity gate), alt kernels and the
   no-vote third (X88), snapshot-stream lags (X96 step 4), the (Lambda, tau) profile (X98 step 3).
3. Still open from earlier: X5, X7, X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X59, X60, X66, X70, X72, X76, X84.

Addendum (written 23:31-23:45 UTC, after the 'Next' list above; X60 = panel iteration 8 information P2, re-opened as a natural
experiment of the 250-ms delay regime):
17. THE pmxt ARCHIVE READS THROUGH RANGE REQUESTS, AND THE 250-MS REGIME MOVES THE WALLET GAP FLOOR UP (`pmxt11.py`,
    results/pmxt11.json, pmxt11_0806.json; r2v2.pmxt.dev hourly parquet, no key; the file is sorted by market, so only the 14-16
    row groups whose market range holds one of the hour's 13 BTC 5m condition ids are read, column subset, ~100-115 MB per hour of
    range requests; only derived subsets are kept in it11/; condition ids from Gamma with closed=true, listing fields only). On
    08-06 16-17 UTC (D = 250 ms): 26,671 BTC 5m trades with server ms and tx hash; 1,174 cluster txs matched; per-wallet gap
    between consecutive TAKER matches: XM (514 matches) min 204 ms, q01 377, q05 500, share < 350 ms 0.4%; DS (102) min 361, q01
    393; GF 21 matches (inactive). On 10-31 (D = 150): DS q1 254, GF 196, XM 152. The floor sits at ~D + 130 ms in August and D +
    2-104 ms on 10-31: one order in flight per wallet, held for the delay plus a response time that was longer in August (08-01
    12-13 was a quiet hour: XM only, 56 taker matches, min gap 381 ms).
18. THE CROWD FLOOR AND THE CLUSTER KERNEL MOVE WITH THE DELAY (`kern11.py`, results/kern11.json; Binance USD-M BTCUSDT aggTrades
    of 08-06, checksum-verified, reduced at once to the hour; V2 calldata of 250 sampled non-operator BTC 5m match txs): crowd
    sign-to-match min positive 248 ms, q05 353, q10 385, median 1,040 ms (10-31: q1 186.5-189.8 ms): D = 250 ms confirmed from
    the data. Cluster reaction kernel (sign of the Binance trade-price change toward the bought outcome over [m - L - 50, m - L),
    minus placebo): peak at L = 475 ms before the match (+0.116), elevated over 275-575 ms; DS peak 400 ms, XM 300 ms with a
    second hump at 450-500. The same kernel on 10-31 (`kern11b.py`, results/kern11b.json; bookTicker mid, 1,331 matches) peaks at
    L = 250 ms (DS 250, GF 250, XM 300). The deciding tick sits 150-225 ms further back from the match when the hold is 100 ms
    longer and the August bot answered ~30-125 ms slower: the match lag is (bot reaction) + D, as the delay mechanism requires.
    The two kernels use different price inputs (trades vs mid) and different bot versions; a like-for-like replication hour
    (08-05 16-17) is below if it finished.
    Replication 08-05 16-17 UTC (pmxt11_0805.json, kern11_0805.json; 25,055 trades, 776 cluster txs): crowd sign-to-match min
    positive 303 ms, q01 316, q05 365, median 575 ms; XM (311 taker matches) gap min 252, q01 325, q05 482 ms; DS (62) min 454, q01
    494; kernel peak L = 500 ms (+0.086; elevated 300-550), DS 400, XM 450. Both August hours agree: in the 250-ms regime the
    crowd floor is ~250-300 ms, the per-wallet gap floor ~325-395 ms and the deciding tick ~400-500 ms before the match, against
    186-190, 152-254 and ~250 ms on 10-31 (150 ms). X60 tried.
19. THE SIDE VOTE REPLICATES IN AUGUST WITH ONE SERIES (`side11.py`, results/side11.json; pmxt hours 08-05 / 08-06 16-17 UTC,
    D = 250 ms; Binance USD-M BTCUSDT trade prices only): sign of the move over the hold-shifted PIT window [m - 850, m - 280)
    agrees with the bought outcome on 72.3% of 60.6% voted decisions on 08-06 (placebo 55.8%; DS 72.1%, XM 71.5%) and similarly
    on 08-05 (DS 65.0%, XM 71.7%; placebo 53.7%); the 10-31 window [m - 650, m - 180) scores 73.7-75.8% (it reads past the August
    bot's last input, so the extra is continuation); inside the hold [m - 280, m - 30) 57.9-63.3%. With one trade series instead
    of six microprices the vote is ~8-10 points weaker than on 10-31 (83%), but the side follows the venue tick in the older
    version too.
20. AUGUST VIEW LAG ~50 MS: THE BOT WAS ALREADY NEXT TO POLYMARKET; IT REACTED TO BINANCE MORE SLOWLY (`lam11b.py`,
    results/lam11b.json; pmxt price_change touches, 3.7M rows read through range requests and not stored; calldata of the 637
    cluster taker txs of 08-06 16-17 UTC; a = m - 250): among 270 decisions whose ask changed in [a - 400, a], P(limit == o's ask
    at a - Lambda) peaks at Lambda = 50 ms (0.785; 0.737 at 0, 0.774 at 100, 0.682 at 150, 0.556 at 200, 0.267 at 300; inside the
    hold 0.726 at -50, 0.60 at -100). On 10-31 the peak is 30 ms. So the bot read Polymarket's book a few tens of ms old in both
    versions: the extra ~130 ms of the August wallet gap floor (finding 17) is not distance to the engine but the bot's own
    response time, and the August kernel (deciding tick 150-250 ms before the arrival, finding 18) against ~100 ms on 10-31 says
    its venue reaction got ~50-150 ms faster between August and October (a faster feed or processing in the 08-22 version;
    hypothesis).
Budget note: no new live development data exist until 11-01 06:00 UTC, and the decisive tests of X87 / X88 / X96 step 4 / X98 step 3
need it; this iteration stopped at ~55 minutes of work to leave budget for the iterations that will have those blocks.

### Iteration 12 (2026-11-01 00:12 UTC start, local Windows laptop; PIVOT: condition 5 as an exposure-path target; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 00:12 UTC): released
lots none; the current block 11-01 00-06 is sealed; no new live development data (next development block 11-01 06:00). Shared
recorder running (`live.py status` 00:12 UTC: clob_crypto, clob_wallets, rtds, sports connected). Nothing sealed was read.

Why this pivot: progress has been flat at 0.859 for three iterations. It decomposes exactly as the mean of five capped
conditions (presence 1, side 0.7666 / 0.80, price 1, PnL min(0.1755, 0.1692) / 0.5 = 0.338, coverage 1): the PnL condition is
the binding gap, and the frozen replica (30-share orders on flagged cells) is capped by its own design (iteration 7: the
30-share oracle under convention (a) reaches only 0.14 / 0.21). The assumptions panel (iter11 P2) re-framed condition 5 as
an exposure target: per window PnL ~ net x outcome (VALIDATE r = 0.884 pooled, 0.887-0.921 per wallet, net12.json), so a
rule that reproduces the operator's SIGNED NET PATH reproduces the PnL without reproducing the decisions. New target: the
window's signed net exposure (and its 30-s increments); new unit: the window / 30-s bin; new execution: a deficit-tracking
replica that keeps re-sending the unfilled part (so its realized net follows the predicted net through strict-fill failures).

Competing explanations of how the money is made (iteration 12; what separates them on the exposure target):
- E1 rebate + paired-set harvester, lean = noise: window PnL mean ~0 from the lean; the net is unpredictable beyond race
  luck. Separates: out-of-sample window-net r <= 0.25 with every public model.
- E2 own fair value with a different strike / drift: the net follows a structural FV (strike = spot at open or open - 60 s,
  momentum drift). Separates: pre-open M1 (+) / M2 (-) and lagged-minute coefficients replicate BUILD -> VALIDATE; one FV
  variant reproduces them.
- E3 stale-quote sniper: the net follows the current tick; sign agreement with the outcome rises with the move size.
  Separates: the current-bin move carries the net, lagged moves add nothing.
- E4 inventory-balanced maker around a faster FV: buys back after moves; the net mean-reverts inside the window.
  Separates: negative lagged-minute coefficients; corr(net before 120 s, final net) well below 1 (measured 0.66).
- E5 underdog / convexity accumulator: accumulates the underdog-since-open on ticks toward the strike. Separates: window
  net sign = underdog side beyond the tick-direction null.
- E6 liquidity-driven: the net is whichever side's asks were available (makers' quotes, ask-sum < 1). Separates: the net
  is predicted by the touch / ask asymmetry from the tape, not by the BTC path.
- E7 internal regime / races: the net is seeded by won races and amplified by the size regime. Separates: residual net
  after every public model is uncorrelated with every public series and with the outcome.

Pre-registration (00:20 UTC, before any replica below is scored): EXPOSURE TRACKER (primary 'trk_a'): per window, target
net N*(s) = sum_{t <= s} nf(t), nf = the frozen it4b per-second netflow model (BUILD-fitted, PIT, Up positive); the
replica's own realized net R (own state of the RULE, legitimate); at each free second s, deficit d = N*(s) - R; if
|d| >= LOT = 10 shares, BUY floor(|d| / 10) x 10 shares of Up (d > 0) or Down (d < 0) at limit = that outcome's last
implied ask (cell ask_o, info <= s - 1) + SLACK = 0.02, only when the ask is in (0.05, 0.95); strict fills only against
OTHER traders' taker BUY prints on that outcome with block ts in [s + 1, s + 3] at <= limit, at the print price, for
min(print, remaining) (capture 1.0, the frozen convention), excluding prints whose taker is a cluster wallet AND prints in
transactions that contain a cluster maker fill; taker fee 0.07 p (1 - p); one open order per window, next decision at
s + 4; the unfilled part stays in the deficit. Convention (b) ('trk_b'): prints [s, s + 2], next decision s + 3. Secondary
(reported, not chosen): SLACK 0 / 0.01 / 0.05, LOT 5 / 30, capture 0.5, cluster-maker txs kept.

Results so far (00:35 UTC):
- trk_a (pre-registered primary, convention (a), strict fills, latency >= 2 s): per-window PnL r pooled Pearson 0.4409 /
  Spearman 0.4187 (2-h block CI of Pearson [0.387, 0.489]; halves 0.438 / 0.443) against the frozen 30-share replica's
  0.1755 / 0.1692; realized net tracks its target at r = 0.993 and the wallet's net at 0.460; GF 0.32, DS 0.40, XM 0.03.
  Every secondary variant lands at 0.432-0.442 (slack 0 / 0.01 / 0.05, lot 5 / 30, capture 0.5, cluster-maker txs kept):
  execution is no longer binding, the net PREDICTION is (window-net r 0.458 for the it4b netflow sum).
- nf12 (new per-second net-flow model with slow path features, no venue / alt features): window-net r 0.4185 on VALIDATE;
  the average of nf12 and the it4b netflow 0.4769 (corr between them 0.70); per-wallet nf12 models do not beat the pooled one.
Pre-registration 2 (00:36 UTC, before it is scored): 'trk_a_avg' = trk_a with target flow 0.5 x (nf_it4b + nf12b), where
nf12b is nf12 retrained with spot-only slow features (no Gamma priceToBeat, so the frozen rule can compute it from its own
spot index). It replaces trk_a as the reported primary only if it beats trk_a on VALIDATE in BOTH pooled Pearson and
Spearman; otherwise trk_a stays primary.
Result of pre-registration 2 (00:40 UTC): trk_a_avg pooled Pearson 0.4758 / Spearman 0.4404 (CI [0.423, 0.522]; halves
0.460 / 0.487; GF 0.344 / 0.353, DS 0.425 / 0.394, XM 0.055 / 0.055) beats trk_a on both: it is the primary. Convention (b)
0.4738 / 0.4378. nf12b alone 0.4389 / 0.3917. Frozen into final_rule.py (`_nf12b_flow`, `_strict_tracker`, `TRK_*`,
`MODEL_NF12B`); `smoke12.py` reproduces the offline numbers exactly through final_rule's functions on the whole VALIDATE week,
and the end-to-end `evaluate(1792627200, 1792638000)` (36 windows, 77 s, RPC fills + tapes + cells + models) returns exactly
the offline tracker on the same windows (2,361 fills, $12,526, Pearson 0.3706, Spearman 0.3712).
Pre-registration 3 (00:52 UTC, before scoring): nf12c = the it4b side-frame features (incl. futures / OKX / Bybit / six-series /
alt perps) + nf12b's spot-only slow features, BUILD-fitted like the it4b netflow (nonzero rows + 30% of zeros). 'trk_a_ens3'
= trk_a with the target flow (nf_it4b + nf12b + nf12c) / 3. It replaces trk_a_avg as primary only if it beats it on BOTH
pooled Pearson and Spearman on VALIDATE; this is the last candidate of this iteration (no further tuning on VALIDATE).

Panel after iteration 11 (panels/iter11_*.md): 13 proposals, added as X100-X112 (information P1-P4 = X100-X103, mechanics
P1-P5 = X104-X108, assumptions P1-P4 = X109-X112). This iteration's pivot is assumptions P2 (X110); X100 step 1, X106 step 1 and
X109 step 1 were measured; X103 is closed on the mechanics panel's own measurement; the rest stay open (below).

Findings (iteration 12):
1. CONDITION 5 IS AN EXPOSURE CONDITION (net12.py, results/net12.json): per window, PnL vs net x (2 outcome - 1): VALIDATE pooled
   r 0.884 (GF 0.921, XM 0.917, DS 0.887), BUILD 0.845; the net's sign matches the outcome in 48.5% of VALIDATE windows (54.5%
   BUILD); mean |net| 329 shares against a gross of 2,600 per window. The net after 60 / 120 / 180 / 240 s correlates 0.46 /
   0.66 / 0.81 / 0.93 with the final net. The frozen it4b per-second netflow model (BUILD-fitted, PIT, never used for the PnL
   rule before) summed over the window predicts the VALIDATE window net at r 0.458 (Spearman 0.450), at a constant rate
   through the window (0.47-0.49 for the net before 60 / 120 / 180 / 240 s); corr(PnL, predicted net x outcome) 0.404.
2. THE EXECUTABLE EXPOSURE TRACKER REACHES 0.44-0.48 UNDER STRICT FILLS (track12.py, results/track12*.json; pre-registered rules
   in this entry): with the it4b target 0.441 / 0.419 (pre-registered primary 1), with the average target 0.476 / 0.440
   (primary, pre-registration 2), CI [0.423, 0.522], halves 0.460 / 0.487; convention (b) the same (0.474 / 0.438). The
   realized net follows the target at r 0.993; execution variants (slack 0-5 c, lot 5 / 30, capture 0.5, cluster-maker txs kept)
   move it by <= 0.01. The iteration-7 'oracle' ceiling (0.40 for the wallet's own decisions under (a)) is not a ceiling for an
   exposure rule: the tracker re-sends unfilled shares at the new ask instead of dropping them. Economics: $569k bought on
   VALIDATE, -3.1% before rebates, -1.6% with a 50% fee rebate: copying the net from public data at >= 2 s does not pay.
3. PER WALLET IT IS 0.06-0.43, AND THE WALLETS' LEANS ARE NEARLY INDEPENDENT: tracker vs GF 0.344 / 0.353, DS 0.425 / 0.394, XM
   0.055 / 0.055. Per-window PnL correlations between wallets on VALIDATE: DS-GF 0.198, DS-XM 0.002, GF-XM 0.145 (each vs pool
   0.69 / 0.80 / 0.36). Per-wallet net-flow models predict their own wallet's net no better than the pooled model (GF 0.297,
   DS 0.342, XM 0.045 vs pooled-model 0.301 / 0.355 / 0.086). One operator, three nearly independent leans: condition 7
   (per-wallet replication of condition 5) is out of reach for XM with public inputs on VALIDATE (XM's BUILD-to-VALIDATE
   activity fell 5x, mean gross 1,153 -> 213 shares per window).
4. THE NET PATH: BUY THE MOVE, PAIR IT BACK LATER (fvnet12.py, results/fvnet12.json; window-minute OLS, HC1 t, BUILD / VALIDATE):
   net bought in minute k rises with the minute-k BTC move (t 5.8 / 10.8 in minute 0, 6.9 / 11.1 in minute 1, 7.8 / 8.0 in
   minute 2, 6.0 / 4.7 in minute 3, 3.7 / 4.7 in minute 4) and falls with the earlier minutes' moves (minute 1 on w0: -3.4 /
   -11.7; minute 2 on w0, w1: -4.8 / -6.4, -4.2 / -4.7); the previous window's outcome adds + (minute 0: 3.1 / 2.3; window total
   3.5 / 3.8); pre-open M1 / M2 and the open-vs-strike gap do NOT replicate in sign (minute-0 M2 +3.4 / -2.9, gap -4.9 / -1.0).
   E3 (stale-quote sniping of the current move) + E4 (pairing back later) describe the inventory path; E2 (a fair value with
   another strike or a momentum drift) is not supported; E5's underdog accumulation is not visible at the window-minute level
   (the buy-back is against the earlier moves whatever the favourite). Window-total R2 0.03-0.06; BUILD-fit OLS on the whole
   path scores VALIDATE at r 0.18 (the panel's 0.20): the linear structure is real but small; the LightGBM per-second models
   carry 0.42-0.48.
5. SLOW PATH FEATURES ADD A DIVERSE PREDICTOR (nf12.py, results/nf12.json / nf12b.json): nf12 (cell features of both outcomes +
   M1 / M2 / since-open / lagged minutes / 2-, 5-, 15-min moves / exact-strike z from Gamma priceToBeat / previous outcome / ask
   sum) 0.4185; nf12b (spot-only slow features, computable inside the frozen rule) 0.4237; slow features carry 12-16% of the
   gain; the average with the it4b netflow 0.4797 (the two correlate 0.70). Top features: r2, n2, vwap10, n1, rn2, bid_o, the FV
   gaps of both outcomes, D_dm5, age_last.
6. PRE-REGISTRATION 3 NOT ADOPTED (nf12c.py, results/nf12c.json, track12_ens3.json): nf12c (the it4b side-frame inputs incl.
   futures / OKX / Bybit / six-series / alt perps + nf12b's slow features) is the best single net predictor (window-net r 0.4703
   vs 0.4583; slow features 5% of its gain; top inputs C6_pm2000, n2, vwap10, C_pm2000, D_ask_o); the three-model average 0.4841.
   Its tracker: 0.4756 / 0.4446 (CI [0.424, 0.521]) against trk_a_avg's 0.4758 / 0.4404: Pearson is not higher, so by the
   pre-registered rule trk_a_avg stays the primary (no further candidates were scored on VALIDATE).
7. CO-OCCURRENCE CHECK OF THE PnL RULE (nf12.py NF12_VARIANT=mkt, trkgain12.py, results/nf12m.json, trkgain12.json): a
   market-activity-only net-flow model (both outcomes' tape state, rel, tau; no spot or venue input) predicts the window net at
   r 0.338, and the same tracker on it reaches 0.360 / 0.315. The reference feeds add +0.116 Pearson (paired 2-h block CI
   [0.075, 0.159], 0 of 2,000 draws <= 0) and +0.125 Spearman ([0.087, 0.158]). So about three quarters of the reproduced PnL
   co-moves with other traders' flows (the crowd leans with the same BTC moves), and the decoded venue inputs carry the rest.
   Per VALIDATE day the primary tracker is 0.370 / 0.485 / 0.511 / 0.499 / 0.542 / 0.452 / 0.512 (market-only 0.26-0.50).
8. THE CROSS-VENUE (COINBASE) GATE, STEP 1 (X100; cbx12.py, results/cbx12.json; 10-31 A / C clean onsets, Coinbase class over
   [tau - 500, tau + 70) ms on exchange stamps): price-level Binance onsets are taken 0.48 / 0.43 when Coinbase did not trade
   (n 23 / 7), 0.31 / 0.34 when it traded without moving toward o, 0.25 / 0.22 when it had already moved toward o (n 120 / 85);
   at size-only onsets a Coinbase move toward o raises the take 3-4x (DEPLETE 0.239 vs 0.054-0.059 on A, 0.184 vs 0.044-0.046 on
   C). Adding the class to the evt10-style FULL logistic: fit A score C 0.6805 -> 0.6963 (+0.016, window-block CI [0.006,
   0.028]); fit C score A 0.6910 -> 0.7052 (+0.014, [0.004, 0.025]); price-level events 0.526 -> 0.565 and 0.530 -> 0.582. A
   small replicated gain: strong Binance ticks are taken more when they are FRESH relative to Coinbase, weak ones when Coinbase
   confirms. The panel's gate ratio (>= 1.8) holds at N vs M (1.9) but N is tiny; step 2 needs 11-01 06-12.
9. NO SELF-EXCITATION WITHIN TWO MINUTES (X109 step 1; regime12.py, results/regime12.json; 200 redraws per half): the LPM
   coefficient of log(1 + rec30) on the take, with segment FE: A L300 +0.019, L120 +0.0075 (null 0.0058 +- 0.0019, p 0.36), L60
   -0.0205 (null -0.0115 +- 0.0026, p < 0.005), L30 -0.043; C L300 +0.016, L120 +0.0033 (null 0.0060 +- 0.0015, p 0.07, below
   the null), L60 -0.0056 (null -0.0041 +- 0.0021, p 0.53), L30 -0.029. The assumptions panel's critique replicates with 200
   draws: the pooled 'self-excitation' of iteration 11 (finding 13) is a between-segment effect; within 2 minutes the own-recent
   effect is inside the mechanical null, and on A it is refractory at 1 minute. The latent is a slow 1-2-minute regime.
10. WHERE THE STATE LIVES (X106 step 1; regime12.py): per wallet, P(w decides on o in [tau + 150, tau + 700)) on log(1 + w's own
    decisions on the window in the last 30 s) and log(1 + the other wallets'), 120-s segment FE: A: DS own -0.001 / other
    +0.006, GF -0.0005 / +0.011, XM -0.008 / +0.007; C: DS +0.004 / -0.008, GF -0.009 / +0.007, XM -0.009 / +0.003. GF and XM
    take more after the OTHER wallets (mostly DS) were active and are refractory to their own recent orders in both halves; DS
    is mixed (A other > own, C own > other). The regime is largely operator-level (shared), with each wallet a refractory slot;
    not a per-wallet process.

Panel proposals of iteration 11 (catalog X100-X112) and what happened to them:
- X100 (information P1, Coinbase / London-arrival divergence gate): step 1 tried (finding 8: small replicated gain +0.014 /
  +0.016); step 2 (pre-registered scoring of 11-01 06-12 with rec_eu11 Coinbase level2_50 / Bitstamp / Kraken) needs the next
  development block. Open.
- X101 (information P2, shared-actionability instrument with the fast crowd as a second label): steps 1-2 tried for the
  recorded design (finding 14: it explains 14-21% of the shared selection); other inputs (11-01 feeds) and step 3 open. Open.
- X102 (information P3, pre-signed peer census / clones): tried (finding 15: no independent clone; a fifth operator fan-out
  wallet 0x03b4c58b... follows the exact burst schedule). Closed as tried.
- X103 (information P4, own fill re-arms the take): tried on the mechanics panel's own measurement (re-fire within 1 s after a
  won race 33.4% vs after an exogenous loss 33.3%) and finding 10 (a wallet's take does not rise with its own recent decisions);
  the ms kink test not run. Closed as tried.
- X104 (mechanics P1, archived live labs 07-01 / 08-01): not tested. Open.
- X105 (mechanics P2, PRNG with the signing-loop layout): not tested (with X99). Open.
- X106 (mechanics P3, where the state lives): step 1 tried (finding 10: operator-level, wallets as refractory slots; DS mixed).
- X107 (mechanics P4, exit as slot discipline in the simulator): not tested. Open.
- X108 (mechanics P5, requote-echo anchors as a historical clock): not tested (with X89). Open.
- X109 (assumptions P1, the 1-2-minute regime): step 1 tried (finding 9: no self-excitation inside 2 minutes; the panel's
  critique replicates with 200 draws); step 2 compact (finding 18: an own-decision kernel with 30-60-s decay beats a slow
  proxy); step 5 measured (finding 11: nothing at the block clock); steps 3-4 open. Open.
- X110 (assumptions P2, condition 5 as an exposure target): tried, the pivot (findings 1-7).
- X111 (assumptions P3, locked vs unlocked decisions): steps 1-2 tried (finding 13: ~9% locked beyond placebo); step 3 needs
  the 11-01 feeds. Open.
- X112 (assumptions P4, competition-aware controller): tried (finding 12: no 2x after mostly won races with the count fixed;
  inconsistent signs); exogenous-loss split not run (no effect to split). Closed as tried.
Correction recorded in X85: the iteration-11 'self-exciting internal state' is a slow operator-level regime (findings 9-10).

Recorders at 01:00 UTC: shared recorder (pid 27184), rec_lab6 v2 (14304), rec_exam7 (32576), rec_fam8 (20608), rec_exam8
launcher (19600, starts 11-02 05:59), rec_pb10 launcher (15792, starts 11-01 06:00), rec_eu11 (14192, starts 11-01 05:59): all
alive. No polyrea bug found this iteration. Cache: it12 adds ~40 MB (net-flow predictions); the rebuilt tapes (530 MB) live in the
session scratchpad only.
11. THE SLOW PUBLIC STATE ADDS NOTHING TO PRESENCE AT THE BLOCK CLOCK (X109 step 5; blkslow12.py, results/blkslow12.json;
    measurement only): the block-second presence model retrained on the same BUILD block seconds with outcome-signed slow
    spot-path features (M1, M2, since-open, lagged minutes, 2 / 5 / 15-min moves, previous-outcome proxy, ask sum, the other
    outcome's ask, FV gap) scores VALIDATE block seconds 0.8747, identical to the frozen model (difference CI [-0.0002, +0.0003];
    halves 0.8748 / 0.8728 vs 0.8750 / 0.8725); the slow terms take 6% of the gain, almost all of it the other outcome's ask (a
    market feature). The panel's signature (block-second gain >= +0.065) is not met: the 1-2-minute regime is not visible in
    slow public state at the block clock.
12. NO RACE-SUCCESS CONTROLLER (X112 steps 1 / 3; ctrl12.py, results/ctrl12.json): the 2,155 live decisions labelled won / lost
    (all 829 located lost races matched); per clean onset, the operator's decisions on the window in the previous 120 s and the
    share that won. With the count held fixed (bins 1-3 / 3-8 / 8-20 / 20+), P(take) for the low / middle / high win-share
    terciles: A n8-20 0.068 / 0.052 / 0.030, n20+ 0.062 / 0.081 / 0.082; C n8-20 0.035 / 0.052 / 0.050, n20+ 0.058 / 0.077 / 0.072
    (inconsistent, high / low 0.45-1.6); LPM win-share coefficient with 120-s FE +0.013 (A) / +0.016 (C), with window FE -0.023 /
    +0.021. The signature (>= 2x after mostly won races) is absent; together with the equal 1-s re-fire after won vs exogenously
    lost races (mechanics panel), the regime is not a race-success controller.

Status after iteration 12: target not reached. What changed in target_metrics: pnl_corr_pearson 0.1755 -> 0.4758 and
pnl_corr_spearman 0.1692 -> 0.4404 (the exposure tracker, pre-registered, frozen in final_rule.py and verified end to end); every
other key unchanged (presence 0.8747 vs 0.8211 on block seconds; side 0.7666; price 0.9512; coverage 1 / 1). Progress (the mean
of the five capped conditions) 0.859 -> ~0.968. Still failing: side (76.7% < 80%), PnL (0.476 / 0.440 < 0.5), and per-wallet
replication of the PnL condition (GF 0.34, DS 0.43, XM 0.06: the wallets' leans are nearly independent). The decoded account
of the PnL now says what carries it: the window net is the sum of a buy-the-move / buy-back-later path that public data
predicts at r ~0.48 (0.34 from market activity alone), and the rest is the per-wallet lean that no public input predicts on
VALIDATE (XM ~0).

## Next (iteration 13)

1. On 11-01 06-12 (development, from 06:00 UTC): every pre-registered live test of iterations 9-11 (PIT vote / price / hazard
   label, full-coverage side, edge_rule_V8, size-from-tick, PolyBolt X76), X100 step 2 (the Coinbase / Bitstamp / Kraken
   freshness gate, pre-register the class rule of cbx12 first), X87 steps 1-4, X88, X96 step 4, X98 step 3, X111 (locked vs
   unlocked decisions with the new feeds), and the exposure tracker on the live block (its decisions at the decision clock).
2. Condition 5 above 0.5: the window-net prediction must reach ~0.55. Candidates: (a) the large-size regime (the lean is the
   large orders; live the 100-share size follows the ms tick at AUC 0.72, invisible at the block clock) through ms aggTrades
   aggregated per second as net-flow features; (b) per-outcome gross-flow targets (presence x expected shares) instead of the
   signed net; (c) a decision-level replica on the recorded books of the live blocks (the race is deterministic there).
   Pre-register every candidate; no more tuning on VALIDATE (three candidates were scored this iteration).
3. Condition 7 (per wallet): why XM's lean is unpredictable on VALIDATE (its activity fell 5x after 10-14; X67 late fan-out
   legs): a per-wallet share-of-decision model (which wallet carries the next leg) on top of the pooled net path.
4. X109 steps 2-4 (Hawkes vs Cox/HMM held-out likelihood on the onset tables; public regressors of the decoded state), X106 steps
   2-4, X101 (fast-crowd co-take instrument), X102 (clone census), X104 (07-01 / 08-01 archived labs), X105 / X99 (PRNG), X107,
   X108 / X89.
5. Still open from earlier: X5, X7, X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X59, X66, X70, X72, X76, X84, X87, X88, X89,
   X90, X93, X98, X99.
13. ONLY ~9% OF THE DECISIONS ARE TIME-LOCKED TO A VENUE TICK (X111 steps 1-2; lock12.py, results/lock12.json; 2,155 live
    decisions of 10-31). Pre-registered at 01:05 UTC: locked = a microprice change toward o inside the kernel7 peak bin +-25 ms of
    any of the seven series with excess >= 0.05 (Binance USD-M BTC / ETH, Binance spot ETH, Bybit ETH, Hyperliquid BTC / ETH, OKX
    ETH); that flagged 98.5% vs a placebo of 97.6% (any change is too common), so the definition was amended once, before any
    locked-vs-unlocked comparison was read, to a NET move >= 0.1 bp toward o over the widened bin: P(locked) 13.2% vs placebo
    (m - 2 s / m - 4 s) 4.7%, an excess of 8.5% (DS 8.6, GF 9.3, XM 7.0%). Locked vs unlocked: six-series tick toward o 96% vs
    71%, no tick 5% vs 61%, large 10.2% vs 4.4%, won 68.7% vs 60.5%, rel median 107 vs 151 s, |ask - 0.5| 0.21 vs 0.17,
    since-open toward o 49% vs 47%. The timing component's 'about 100-150 ms after a microprice tick' describes a strong-tick
    minority (the snipes that carry the large size); most decisions have no sharp clock in the recorded feeds, which is what
    the flat onset kernel (iteration 11) and the 61% no-tick share say. Step 3 (clocks for the unlocked majority from the 11-01
    feeds) is open.
14. THE SELECTION SHARED WITH THE FAST CROWD IS MOSTLY OUTSIDE THE RECORDED INPUTS (X101 steps 1-2; coat12.py, results/coat12.json;
    fast crowd = 13,644 non-operator taker BUYs from 1,196 wallets with sign-to-match 180-400 ms, matched in [tau + 150, tau + 700)
    ms; diagnostic only, never a rule feature): P(fast-crowd take | cluster took the onset) 0.42 / 0.39 vs 0.20 / 0.17 when it
    skipped (A / C; price-level onsets 0.51 / 0.52 vs 0.19 / 0.20); raw log OR 1.03 / 1.13. Conditional on the evt10-style FULL
    design (class, |bp|, ask unchanged, |ask - 0.5|, venue agreement, spread, Polymarket activity) the crowd log OR is still 0.82
    / 0.97 (FULL explains 21% / 14% of it) and the Coinbase class adds nothing (21% / 14%). The cluster and the fast crowd pick the
    same onsets on something that is not in the recorded design: the information panel's reading (a shared input, not a private
    coin) is supported. Caveat: the crowd window does not exclude orders signed after the cluster's match could be seen (the
    panel's stricter version); the logit hit overflow warnings (coefficients stable, se ~0.05).
15. NO INDEPENDENT CLONE OF THE LADDER BOT; A FIFTH OPERATOR WALLET (X102; census inline, results/clone12.json, w5clone12.json; 10-31
    match-tx calldata, 152,576 orders): the operator's signature fields (sig_type 3, length 317, zero builder / metadata) are
    shared by 84k other orders; its distinctive marks are pre-signing (97.5-99.3% > 5 s before the match), the burst phases
    (99.6-100% within +-3 s of -89.5 / +42.4 / +173.3 s; W4 37%) and same-ms copies (60-81%). Of 551 non-operator wallets with >=
    40 orders, 139 are mostly pre-signed, but only 0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c follows the burst schedule (64 orders,
    100% in-burst, median lag 42 s, all BUY, 47 maker-role): its signing ms sit 5 / 249 ms (q10 / q50) from an operator order's,
    14% of its txs hold an operator order, and its matches fall 0 / 34 / 508 ms (q10 / q50 / q90) from an operator match on the
    same token (76% within 100 ms). It is a fifth fan-out leg of the same operator (like W4), not an independent clone; the
    clones' take behaviour (steps 2-3) has no subject. Its fills are not in the three-wallet target (fills of W4 / W5 are outside
    the dossier's scope) but they belong in the operator net for size (X66).
16. THE WALLETS TAKE THE SAME ONSETS JOINTLY (X106 step 2; joint12.py, results/joint12.json; public FULL score fitted on the
    other half, four score bins): P(w and w' both decide on o) far exceeds P(w) P(w') in every bin (score fit A, scored C: DS-GF
    0.0029 vs 0.0001 in the bottom bin, 0.025 vs 0.0044 in the top bin; DS-XM 0.0136 vs 0.0037, GF-XM 0.0097 vs 0.0020 at the
    top; the reverse fit the same): one operator-level decision fans out to several wallets, so the take is decided once per
    onset, not per wallet. Step 3 (rerouting while a wallet is busy) is not identifiable on the clean onset tables (by
    construction no operator decision precedes a clean onset within 600 ms; the 0.5-2.7% 'busy' cases are definition
    mismatches next to fan-outs) and needs the full onset set. X107 note: the assumptions panel measured that only 6.6% of 196
    cancelled remainders have a same-wallet arrival within +-100 ms of the removal (cancel-then-send is not the TTL rule); the
    simulator part of X107 is not built.
Additional 'Next' item: run evaluate() on the 10-31 00-06 and 12-18 development blocks once the 10-31 Binance / OKX / Bybit
daily archives are published (an out-of-time test of the exposure tracker a week after VALIDATE, on a weekend).
17. LEAK CHECK: THE OPERATOR'S FOURTH / FIFTH WALLETS IN THE TAPE FEATURES DO NOT DRIVE ANY MODEL (w45chk12.py, results/w45chk12.json).
    Every frozen tape feature excludes the three dossier wallets and transactions with their maker fills, but not W4 (0xd844...)
    or W5 (0x03b4...): on VALIDATE W4 has 18,347 in-window taker prints (0.71% of non-cluster prints, in 1,796 of 2,016 windows),
    45.8% of them followed by a cluster taker fill on the same outcome within 1-2 s, and 7.4% of the cluster's taker seconds are
    preceded by a W4 print. Rebuilding the VALIDATE cells' tape features with W4 / W5 removed (and W4 / W5 dropped from the
    tracker's fill liquidity): frozen block-second presence 0.8747 (unchanged) vs pure 0.8190 (gain +0.0557 vs +0.0554); the
    it4b netflow predictions correlate 0.9994 with the originals; the exposure tracker 0.4756 / 0.4394 (vs 0.4758 / 0.4404; GF
    0.347, DS 0.422, XM 0.055). The frozen metrics stand; the W4 / W5 exclusion should still be made explicit in the next
    rebuild of the rule (it is not in final_rule.py's tape features).
18. THE OWN-DECISION KERNEL HAS A 30-60-S DECAY (X109 step 2, compact; hawkes12.py, results/hawkes12.json; own state, a mechanism
    measurement): added to the public FULL onset design (logistic, fit one half, score the other): a Hawkes-type kernel of the
    operator's past decisions on the window, decay chosen on the fit half (60 s on A, 30 s on C): held-out log loss 0.17577 /
    0.21273, AUC 0.718 / 0.718; a slow proxy that excludes the last 30 s (decisions 30-120 s and 120-300 s before the onset):
    0.17791 / 0.21461, AUC 0.704 / 0.708; both together 0.17598 / 0.21277 (no gain over the kernel); FULL alone 0.1810 / 0.2185
    (AUC 0.681 / 0.691). With finding 9 (no rec30 effect inside 2-minute segments beyond the redraw null) the latent's time scale
    is ~0.5-1 minute: a kernel that decays over 30-60 s, which 2-minute fixed effects absorb; neither a sub-30-s self-excitation
    nor a regime slower than 2 minutes. The state is operator-level (findings 10, 16). Still own state: not a public input.

19. PER-WALLET PnL IS MOSTLY THE TAKER LEAN (walletpnl12.json, inline; VALIDATE): taker-role fills carry 70-79% of each wallet's
    per-window PnL variance (corr with the total 0.85-0.93; GF / XM / DS taker PnL -$2,959 / -$528 / -$1,400 before rebates)
    and maker-role fills 21-30% (+$4,408 / +$2,111 / +$2,756); the taker-role and maker-role nets of a window are uncorrelated
    for XM and DS (0.02) and weakly for GF (0.22). Condition 7 therefore needs each wallet's own TAKER lean, i.e. which wallet
    carries which fan-out leg (X67); the pooled tracker cannot supply it.

Pre-registration for the next development block (written 01:23 UTC 11-01, before any 11-01 data exists; X100 step 2): on
11-01 06-12 UTC, rebuild the evt10 clean Binance USD-M onsets and their take labels exactly as onset11 / evt10; add the cbx12
Coinbase class (N / S / M over [tau - 500, tau + 70) ms from btc5m_venues2 'cbT', and the same class from rec_eu11's Coinbase
ticker in btc5m_xeu as a replication) to the evt10-style FULL logistic fitted on 10-31 A + C pooled, frozen, and score the
11-01 onsets. Success = AUC gain >= +0.01 with a window-block CI above 0 AND P(take | N) / P(take | M) >= 1.8 at price-level
onsets. Same protocol for Bitstamp and Kraken classes (rec_eu11) as secondary. Also: run final_rule.evaluate on 10-31 00-06 and
12-18 once the 10-31 daily archives are published (out-of-time test of the exposure tracker).
Iteration 12 ended 01:24 UTC (about 72 minutes of work).

### Iteration 13 (2026-11-01 02:02 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 02:03 UTC): released
lots none; the current block 11-01 00-06 is sealed; no new live development data during this iteration (next development block
11-01 06:00). Shared recorder running (`live.py status` 02:03 UTC: clob_crypto, clob_wallets, rtds, sports connected). Nothing
sealed was read. Panel after iteration 12 (panels/iter12_*.md): 12 proposals, added as X113-X124 (information P1-P5 = X113-X117,
mechanics P1-P3 = X118-X120, assumptions P1-P4 = X121-X124).

Competing explanations (iteration 13; what separates them):
- E1 TWO-STREAM OPERATOR: a large-size directional lean (fanned out to every wallet, seeded near the open, pyramided) plus a
  small-size taker counter-flow that buys back the operator's REALIZED large inventory within ~2 min. Separates: a dose-response
  kernel of the small orders' side on the realized large fills that survives the crowd's path and a small-fill placebo; stream
  models that predict the window net better than a model trained on the cancelling sum; per-wallet nets as loadings on two
  shared streams.
- E2 REBATE / COMPLETE-SET HARVESTER WITH A RANDOM LEAN: the 'pairing' is the mechanical consequence of buying both sides when
  the ask sum < 1. Separates: after a large fill the small orders' complement share equals that after a same-side small fill
  of the same size class (placebo), once the ask state is controlled.
- E3 STALE-QUOTE SNIPER ON A FASTER CLOCK: side and selection live at ms; the block clock (decision ~2 s before the block) costs the
  side its last points. Separates: the decision-clock vote on VALIDATE (public HF capture with server-ms trades and tx hashes)
  is >= 80% where the block-clock model is 76.7%.
- E4 OWN FAIR VALUE WITH IMPLIED VOL: the buy-back strength scales with IV / RV across windows. Separates: an (earlier move) x
  log(IV / RV) term in the window-minute net path with the same sign in BUILD and VALIDATE.
- E5 SETTLEMENT-BASIS ANCHOR: the bot prices off Chainlink Data Streams while the crowd prices off Binance; the net residual
  follows the Chainlink - Binance basis. Separates: a Delta-basis term in the residual of the window net, stable across halves.
- E6 QUEUE READER: the quiet majority of decisions is triggered by size-only requotes at o's touch (touch-queue fade).
  Separates: queue terms lift quiet-instant AUC by >= 0.03 in both halves and absorb the crowd co-take.
- E7 PRIVATE / INTERNAL: the residual after every public input is unrelated to every public series (dispatch and race luck).
This iteration discriminates E1 vs E2 (stream decomposition, kernel with placebo and crowd control, two-stream tracker),
measures the per-wallet consequence of E1 (condition-7 ceilings), and starts E3 on the public archive (ingest and coverage).

PRE-REGISTRATION (written 02:17 UTC 11-01, before any two-stream model is fitted or scored on VALIDATE):
- Stream labels (two13.py): LARGE = an order (fills grouped by order hash) with total filled shares >= 80 for windows starting
  before 10-12 00:00 UTC (60/100 menu) and >= 45 later; SMALL otherwise.
- Models (ls13.py): LightGBM per-second regressions L13 (target: the operator's large-order signed flow per block second, Up +)
  and S13 (small-order flow), BUILD 10-09..15 only, nf12's PARAMS / ROUNDS, features = nf12b's set (spot-only slow features,
  no Gamma priceToBeat) + W13 window-state features (for k in 1.5 / 3.0 bp: the sign and rel of the first 1-s Binance move with
  |r| >= k since the open, as of s - 2; the counts of such up / down moves so far). No own state. T13 (same features, target
  the sum) is trained as a diagnostic only.
- PRIMARY CANDIDATE 'trk_a_2s' = trk_a (same TRK constants, convention a, strict fills) with target flow 0.5 x (nf_it4b + L13 +
  S13). It replaces trk_a_avg as the primary ONLY IF it beats trk_a_avg (0.4758 / 0.4404) on BOTH pooled Pearson and Spearman on
  VALIDATE. This is the only candidate scored for adoption this iteration.
- Secondary (reported, never adopted this iteration): window-net r of L13 / S13 / L13 + S13 / T13; 'trk_a_LS' (target L13 +
  S13 alone); per-wallet trackers with target a_w L13 + b_w S13 (a_w, b_w = BUILD per-window OLS of the wallet's net on the
  pooled L and S nets); per-wallet PnL r.
- Side tilt (side13.py, own state, reported with and without, never part of the presence rule): logit(p) = logit(psb) + b1 z(K)
  + b2 z(K) x |logit(psb)|, K = sum over the operator's realized LARGE fills in [s - 180, s - 2] of signed shares x exp(-(s -
  t) / 60); b1, b2 cross-fitted on VALIDATE halves (fit one half, score the other); pre-registered success = pooled side >= 78%.
PRE-REGISTRATION 2 (02:33 UTC, before basis13 is run; X116 = information P4): basis b(t) = RTDS Chainlink btc/usd (HF capture
revision f848a77c, timestampMs second) minus the Binance 1-s close; per window the residual of the pooled net after the frozen
primary target's window sum; OLS on [b at the open, Delta b per window minute 0..4] fitted on 10-17..19, scored on 10-20..22 and
the reverse. Success = out-of-sample window-net r gain >= +0.03 in both directions with the same signs.
PRE-REGISTRATION 3 (02:36 UTC, before dcside13 is run; X113 step 3): DECISION-CLOCK side model on VALIDATE (code/dcside13.py
docstring has the exact feature list): unit = operator taker order with an archive match ms m (HF capture revision f848a77c),
decision instant a = m - 180 ms; Up-signed returns over [a - K, a) (K = 100..2000 ms) of Binance spot book microprice / mid
(archive receive clock), Bybit BTC / ETH perp microprice (100-ms bins, + 150 ms), Binance USD-M BTC / ETH and OKX swap last
trade (+ 131 ms), and the Polymarket state at a; LightGBM binary (15 leaves, 300 rounds) fitted on 10-17..19 orders, scored on
10-20..22. Success = full-coverage per-order accuracy >= 80% on 10-20..22. Reported against the Polymarket-only model and the
block-clock side model ps on the same orders.

Findings (iteration 13):
1. THE TWO STREAMS ARE REAL, AND THEIR CANCELLATION IS WHY THE WALLET TOTALS LOOK INDEPENDENT (two13.py, results/two13.json;
   replicates both panels): VALIDATE cross-wallet correlations of the window nets: large-order nets L 0.35-0.47 (DS-GF 0.456, DS-XM
   0.346, GF-XM 0.468), small-order nets S 0.25-0.51, totals 0.00-0.21; within wallet corr(L, S) GF -0.60, XM -0.46, DS -0.26, pooled
   -0.60 (BUILD: cross-wallet L 0.24-0.45, within -0.16..-0.41). Large share of shares on VALIDATE: GF 45%, XM 53%, DS 17%.
2. CONDITION 7 IS BOUNDED BY DISPATCH, MEASURED (two13.json 'oracle_ceilings_validate'; upper bounds): per-wallet PnL r against a
   PERFECT pooled net x outcome: GF 0.695, DS 0.630, XM 0.304 (halves XM 0.320 / 0.292); against a perfect pooled LARGE lean: GF
   0.753, DS 0.339, XM 0.366; a_w L + b_w S with BUILD loadings: GF 0.766, DS 0.640, XM 0.218; from the OTHER wallets' legs only
   (the shared operator part, no own flow): GF 0.420, DS 0.175, XM 0.036. So no rule that predicts the operator's pooled streams,
   however well, can give XM the ~0.47 that condition 7 asks. XM's net is its own dispatch share (XM-specific legs), and no public
   input carries it (per-wallet nf12_XM 0.045). This is a measured wall component for condition 7 (XM), not a missing input.
3. THE PRE-REGISTERED TWO-STREAM TRACKER IS NOT ADOPTED (ls13.py, track13.py; results/ls13.json, track13.json): L13 predicts the
   VALIDATE window L at r 0.324 (nf12b 0.309), S13 the window S at 0.098 (nf12b 0.048), and L13 + S13 the net N at 0.4195 (nf12b
   0.4237; T13 on the sum with the same features 0.4212). corr(L13 + S13, nf12b) = 0.957: the same public information. The W13
   window-state features (first k-bp move after the open, move counts) carry 2.0-2.3% of the gain. trk_a_2s (the primary
   candidate) scores 0.4681 / 0.4320 (block CI [0.416, 0.519]) against trk_a_avg's 0.4758 / 0.4404: lower on both, so it is NOT
   adopted. trk_a_LS 0.425 / 0.376; per-wallet trackers with BUILD loadings GF 0.318, XM 0.064, DS 0.361 (all below the pooled
   tracker's per-wallet values). The panels' 'signature if false' holds: the public share of the window net is bounded by the
   public share of the lean L (r ~0.32 at the block clock).
4. THE PAIRING MECHANISM IS CONFIRMED, BUT IT IS OWN STATE AND MOVES THE SIDE BY < 0.5 POINT (side13.py, results/side13.json,
   side13_ps.json; VALIDATE one-sided seconds, offset = the frozen side model, window-clustered):
   - On SMALL-order seconds (79% of one-sided seconds) the operator's realized LARGE net over [s - 180, s - 2] (60-s decay) has
     coefficient -0.30 (t -26.5): the small orders buy the complement of the realized large inventory.
   - The SMALL-order placebo K_S is +0.04 (t +4.0): same-side clustering, not pairing.
   - The crowd's 120-s Up-signed taker flow is 0.000 (t -0.01): the pairing is not market-driven.
   - On LARGE-order seconds the sign flips: +0.27 (t 8.6). The large leg pyramids.
   - Raw: small seconds with |K_L| >= 30 buy the complement 56.9% of the time (n 53,159); placebo |K_S| >= 30: 46.2%.
   E1 (two-stream operator) is supported over E2 (mechanical complete-set pairing). The pre-registered tilt logit(ps) + b1 z(K_L) +
   b2 z(K_L) |logit ps|, cross-fitted on VALIDATE halves: 76.87% vs 76.66% (psb version 75.43% vs 75.28%); small seconds +0.4,
   large seconds -0.6 points (the rule cannot know the size class in advance). Pre-registered success (>= 78%) NOT met. The
   own-inventory-only rule (complement of K_L) is right 52.7% of the time on 87% coverage.
5. THE PUBLIC HF CAPTURE IS A VERIFIED HISTORICAL DECISION CLOCK FOR VALIDATE (session scratchpad it13/hfprobe13.py,
   it13/hfingest13.py; results/dc13_2026-10-20.json):
   - Fahri-5/updown-5m-polymarket-raw, CC0, not gated, revision pinned f848a77ccfce4421d3cedbbe585576db77d36662 (last modified
     11-01 01:16 UTC); day files polymarket/ and btc/ for 10-17..22. Only the names of days < H were kept from the listing.
   - polymarket/2026-10-20: 97.7M rows in 698 row groups, 5.4 GB. The needed columns (eventType, exchangeTimestampMs,
     transactionHash, tokenId, trade price / size / side, bestBid / bestAsk) are 392 MB of range requests (218 s), reduced to
     399k trades and 421k touch changes.
   - 97.3% of the operator's 39,899 txs on 10-20 carry an archive match ms (99.1-100% in hours 0-22). The day file covers
     00:00-23:00 server time, so hour 23 is in the next file. Block ts minus match ms q05 / q50 / q95 = 1,247 / 2,202 / 3,138 ms
     (no negative lags; the live lab measured 1.29-3.20 s).
   - btc/: Binance spot BTCUSDT book (12.2M rows, collector receive clock; spot trade transit receive - exchange 131-132 ms),
     trades (3.0M), and Polymarket's RTDS Chainlink btc/usd (81k 'ticker' rows, ~0.95 / s, serverTimestampMs ~1.7 s after the
     price's own timestamp).
   - HF answered 429 when two ingests ran in parallel (6 + 4 threads). The ingest now coalesces column-chunk ranges and backs off
     45 s on 429.
6. AT THE DECISION CLOCK, THE SIDE IS THE LAST 100-250 MS OF THE BINANCE SPOT BOOK: 77% PER ORDER AT FULL COVERAGE (dcfeat13.py,
   dcside13.py, dcown13.py; results/dcfeat13_2026-10-20.json, dcside13_2021.json, dcown13_2021.json).
   - Univariate on 10-20 (27,008 taker orders, decision a = m - 180 ms): the Binance spot microprice over [a - 250, a) agrees
     70.9% on 93.5% of orders, over 500 ms 67.2%, 1 s 62.7%, 2 s 58.5%. The sharp decay with the horizon marks a trigger, not a
     trend. USD-M last trade 250 ms: 59.6% on 37%. Chainlink RTDS: 48-49% (slightly contrarian).
   - The frozen live vote windows with only these two series agree 65.7% on 57% ([m - 600, m - 100)) and 55.9% on 52% (PIT
     [m - 650, m - 180)). The live six-series vote's 83% needed the USD-M bookTicker and ETH series that the archive lacks.
   - LightGBM on the decision-clock features (spot book, Bybit BTC / ETH 100-ms book, USD-M BTC / ETH and OKX trades,
     Polymarket state), fit 10-20 -> score 10-21 and the reverse. This is a disclosed deviation from pre-registration 3, whose
     10-17..19 fit needs the trades-only ingest. FULL coverage per taker order: 77.2% / 77.3% (GF 80.9 / 82.2%, XM 80.4 /
     84.7%, DS 74.8 / 74.8%); venue-only 76.1 / 76.3%; Polymarket-state-only (market-only) 58.8 / 58.6%; with the own-state
     pairing kernel 77.6 / 77.4% (DS +0.5). Top inputs: spot microprice 250 ms (26% of gain), 100 ms (19-22%), 500 ms (6-9%).
   - The block-clock per-order side was 72.7% (VALIDATE chunks): the decision clock adds ~4.5 points per order.
   - On the 65% of orders that fall in one-sided block seconds, the block-clock ps scores 81.5-82.6% against the decision
     clock's 79.1-79.9%. The block-clock features (spot <= block ts - 2 s, a median ~0.2 s AFTER the match) partly read the
     post-decision continuation: on 10-20 the 1-s Binance mid move ending at block ts - 2 s agrees 69% vs 54% at the decision,
     and o's ask rose over the last 500 ms before block ts - 2 s for 71.8% of orders vs 56.0% at the decision. The block-clock
     side is PIT by the block-time rule, but part of it is co-movement, not the decision's input.
7. THE SIDE RULE HOLDS EARLY IN THE WINDOW AND FADES LATE (dcown13_2021.json, late13_2021.json):
   - Decision-clock full-model accuracy by window time: 81-83% in [0, 120) s, 78% in [120, 180), 72% in [180, 240), 62-65% in
     [240, 270). There are no operator taker orders after 270 s.
   - Late, the spot tick agrees 62-66% and the complement of the operator's realized net 55.5-58.6% (own state, rising toward
     the end).
   - The partial settlement TWAP (RTDS mean from second 240 to a) vs the strike agrees 52% (near / far from the strike 52.0 /
     51.9%): no last-minute lock-in by the settlement TWAP (B3b).
   - The Chainlink favourite vs the strike: 44-48% in the first 4 minutes (the bot leans to the Chainlink underdog), 53% at
     240-270 s.
   The late decisions are a mix of weaker tick-following and inventory pairing.
8. THE OPEN IS NOT A SEPARATE DECISION TYPE (X124 step 1 on the archive; open13.py, results/open13_2021.json): decisions in [0, 15) s
   follow the same tick (73.8% vs 70.7% after 30 s). The exact-strike value side (FV from RTDS Chainlink, Gamma priceToBeat and the
   15-min RV) agrees 45.0% (43.3% where |gap| > 5 c: the bot's FV is wider than an RV digital, the known underdog tilt), and the
   exact-strike favourite 48%. P(large) is 9.0% vs 6.6% later (1.4x, not the panel's 2x). Signature (>= 75% value-following, 2x
   large) not met.
9. NO SETTLEMENT-BASIS INPUT IN THE NET PATH (X116, pre-registration 2; basis13.py, results/basis13.json): Chainlink btc/usd minus
   Binance BTCUSDT is -$102 median (q05 / q95 -$119 / -$71; the USDT premium). Basis terms vs the residual of the window net: |r| <=
   0.045. OLS fit 10-17..19 -> 10-20..22 gain -0.007, reverse +0.0004 (base r 0.504 / 0.488). E5 not supported.
10. THE 'IMPLIED-VOL SCALE' OF THE BUY-BACK IS A REALIZED-VOL SCALE (X117; iv13.py, results/iv13.json, iv13_split.json; Deribit DVOL
    at 1 min, 20,190 minutes 10-09..22, end < H): in the window-minute panel (minutes 1..4), earlier-move x log(DVOL / RV15) is
    -2.40 (t -6.4) on BUILD and -2.80 (t -7.3) on VALIDATE; current-move x z +2.99 (t 2.4) / +3.01 (t 2.9): replicated. Split into
    log RV15 and log DVOL, the earlier-move interaction is all realized vol (+2.13, t 4.9 / +2.79, t 7.4 on log RV), and DVOL's own
    term is insignificant (t 1.15 / 0.24). The bot scales its buy-back by recent realized vol (moves in sigma units), which the nf
    features already carry (rn*, sig, since_open_n); no new nf candidate was pre-registered. E4 (implied-vol fair value) is not
    supported.
11. THE WALLET THAT CARRIES AN ORDER IS NOT PREDICTABLE FROM PUBLIC STATE; THE LEG ORDER IS (X120 step 5 / X122 step 2; dispatch13.py,
    share13 inline, results/dispatch13_2021.json, share13.json):
    - On the archive decision clock (10-20 / 10-21; DS 64%, GF 29%, XM 6% of taker orders), a multiclass model on public state at the
      decision (rel, ask level and changes, |spot tick|, hour) gets accuracy 0.612 / 0.677 against base rates of 0.607 / 0.674 (log
      loss 0.80 / 0.71 vs 0.87 / 0.79). XM's share by predicted decile runs from 0.5% to 25%, so some states are XM states, but they
      carry no side.
    - Fan-out events (same token, match ms within 300 ms): 29,127 single-leg, 6,661 two-leg and 1,620 three-or-more-leg events. In
      multi-leg events the FIRST leg is DS 79%, the SECOND GF 74%, the third DS 47% / GF 27% / XM 27%: a fixed leg order.
    - Even with XM's TRUE per-window gross share times the PERFECT pooled net, XM's PnL r is only 0.406 (hour-of-day share 0.30):
      condition 7 for XM needs the side of XM's own legs.
12. THE PAY-UP RISES WITH THE LEG RANK AND DIFFERS BY WALLET (payrank13.py, results/payrank13.json; 2,476 calldata taker orders on 10-20
    11:00 and 10-21 13:00 against the archive ask at arrival - 30 ms):
    - limit - ask in cents: DS 0 for 87.5% (+1 c 7.1%); GF 0 for 49.5%, +1 c 41.4%; XM 0 for 31.5%, +1 c 35.0%, +2 c 16.8%, +3 c 11.2%.
    - Mean premium by leg rank: first leg 0.18 c, second 0.78 c, third 0.72 c, later 1.11 c (single-leg events 0.15 c, multi-leg 0.60 c).
      By wallet and rank: DS 0.10 / 0.51 / 0.97, GF 0.37 / 0.79 / 0.54, XM 0.96 / 1.33 / 1.34. The later legs price over the level the
      earlier legs consume, and XM pays up even as a first leg.
    - A per-wallet anchor ask + c_w (DS 0, GF 1 c, XM 1 c; chosen on the same orders, descriptive) is within a tick for 94.5% pooled
      (DS 95.5%, GF 94.4%, XM 83.2%), against 92.7% (XM 66.4%) for the plain ask. Condition 7's price part for XM needs this per-wallet
      term (VALIDATE-only, two calldata hours; not frozen).
13. PER DECISION THE DECISION-CLOCK SIDE IS ~75%, PER ORDER 77% (dclegs13 inline, results/dclegs13.json; the dcside13 full model fit on
    one of 10-20 / 10-21 and scored on the other). Fan-out follower legs score 80-87%: they arrive up to 300 ms after the first leg,
    and their features already contain more of the move. FIRST legs, which are the operator's decisions, score 75.4% / 74.9%.
    Single-leg orders: DS 74.0 / 73.6%, GF 79.0 / 78.5%, XM 77.4 / 85.5%. The honest decision-level figure is about 75%. The
    per-order 77% is what an examiner scoring orders or fills would see.
14. THE MISSING USD-M BOOKTICKER DOES NOT CLOSE THE GAP (rabbit13.py, session scratchpad it13/rabbit_bf13.py; results/rabbit13.json).
    Source: RabbitGo777/polymarket.btc_20261020.v4.parquet, not gated, revision 1e0218e12491c7e1d6183350a424fb3489539129, a one-day
    all-venue capture of 10-20 (binance 1.35 GB, bybit, okx, coinbase, chainlink, Polymarket 5m / 15m). The binance file has 200M
    rows in 4,011 row groups (kind_local, e, ts_local in microseconds on a Finland collector, E_, b / B_ / a / A_). Its USD-M
    BTCUSDT bookTicker rows were read for the 133 row groups wholly inside 10-20 11:00-12:00 UTC: 1.33M rows, ts_local - E_ =
    136 ms median.
    On the 926 operator taker orders of that hour:
    - the USD-M microprice over [a - 250, a) agrees 72.7% on 98% of orders, against 70.9% on 89% for the archive's spot book;
    - over 100 ms: 72.0% on 89%;
    - the frozen-style vote with USD-M (0.002 bp, 500 ms): 64.6% on 32%;
    - the decision-clock model (fit on 10-21, without USD-M): 76.5%. With the USD-M 250-ms tick taking precedence where it moved
      it is 75.6%.
    The live six-series 83% (10-31, a Saturday, on the voted 68%) is therefore not a missing-series effect. On VALIDATE weekdays
    the public side information at the decision instant is ~75-77% at full coverage.
15. PRE-REGISTRATION 3 SCORED: THE DECISION-CLOCK SIDE IS 76.3% ON 10-20..22, SUCCESS NOT MET (dcside13.py, results/dcside13.json).
    - Ingest: trades-only (pmtx) for 10-17, 10-18, 10-19 and 10-22, so the Polymarket touch exists only on 10-20 / 10-21. Spot
      book for all six days.
    - Archive coverage of operator taker orders: 99.4% / 95.6% / 93.5% / 97.5% / 95.3% / 96.2% (10-17..22).
    - Fit 10-17..19 -> score 10-20..22: full coverage per taker order 76.28% (DS 74.3%, GF 79.7%, XM 80.0%; by day 76.5 / 76.0 /
      76.3%; large 78.3%, small 76.1%).
    - The Polymarket features are missing on the fit days, so 'full' equals 'venue-only' (76.28%). Market-only: 50.4%.
    - Reverse (fit 10-20..22 -> score 10-17..19, the weekend first): 74.1% (venue-only 75.9%).
    - On the 61% of scored orders that fall in one-sided block seconds: decision clock 78.3% vs block-clock ps 81.9%.
    Pre-registered success (>= 80%) is NOT met. The decision-clock side on VALIDATE is 74-77% per order and ~75% per decision.
    The six-series live 83% was a voted subset on a Saturday (finding 14: no missing-series effect).

16. FOR XM, THE WALLET THE SIDE CONDITION APPLIES TO, THE DECISION CLOCK PASSES 80% (dcwin13 inline, results/dcwin13.json; the
    pre-registered model fitted on 10-17..19, saved as code/model_it13_dcside_A.txt, scored on 10-20..22).
    - XM is one-sided by its taker orders in 172 of its 692 windows (24.9%; the condition applies at >= 20%). DS and GF are
      one-sided in 0.1% and 1.7% of their windows, so the condition does not apply to them.
    - XM's window side, predicted by the mean decision-clock probability of its orders in the window: 84.3% (by day 94.2 / 82.9 /
      74.2%; 87.0% on the 69 multi-order windows).
    - XM per taker order: 80.0% (by day 84.0 / 80.3 / 75.7%).
    - The block clock gave XM 72.6% per one-sided second, 73.1% per taker order and 69% per window by first decision.
    The daily spread (74-94% on ~57 windows a day) is wide, so condition 7's 3-point replication across halves is not assured.
    This is the best side result so far for the wallet the examiner is likely to test. It is VALIDATE-only and not yet in
    evaluate(); that is item 1 of the next iteration.

Panel proposals of iteration 12 (catalog X113-X124) and what happened to them:
- X113 (information P1, the public HF capture as the decision clock): steps 1-4 tried (findings 5-6 and 12). The pre-registered
  10-17..19 -> 10-20..22 side split is below (run at the end of the iteration if the trades-only ingest completed). Step 5
  (decision-level replica on the archive book) and step 6 (the exam route in evaluate()) are open. Open.
- X114 (information P2, touch-queue fade): not tested. Open.
- X115 (information P3, crowd co-arrival kernel search): not tested (needs the 11-01 feeds). Open.
- X116 (information P4, settlement basis): tried, no gain (finding 9).
- X117 (information P5, implied-vol scale): tried; the interaction is realized vol (finding 10).
- X118 (mechanics P1, two-leg inventory policy): tried. The mechanism is confirmed (finding 4), the side tilt adds < 0.5 point, and
  the two-leg tracker is X121's (not adopted).
- X119 (mechanics P2, pre-onset repricing state): not tested. Open.
- X120 (mechanics P3, per-wallet allocation of the two legs): steps 1-3 and 5 tried (findings 2, 3, 11); step 4 (version transfer)
  not run. Tried.
- X121 (assumptions P1, two-stream target): tried; pre-registered and not adopted (finding 3).
- X122 (assumptions P2, dispatch roles and the attainability ledger): ledger done (findings 2, 11); role table and W4 / W5
  test-retest open. Open.
- X123 (assumptions P3, co-takers' signing ms as clocks): not tested. Open.
- X124 (assumptions P4, the open as a decision type): step 1 on the archive (finding 8: not distinct); step 2 open. Open.
- X84 (iteration-9 panel, large and small as two decision streams) is closed as tried with X121's evidence.

## Next (iteration 14)

1. The decision-clock exam route (X113 step 6). It is the top item, because XM's one-sided windows reach 81-84% at the decision
   clock against 69-73% at the block clock (findings 16-17). The spot-book-only route is DONE: final_rule.evaluate() reports
   'side_decision_clock' (code/dc_exam13.py, pre-registration 4). Still to do:
   - route the full venue model (model_it13_dcside_A.txt: + Bybit ob, USD-M / ETH / OKX trades through final_rule's archive
     helpers) the same way;
   - decide, before the next exam, whether the decision-clock XM window side should become target_metrics.side_accuracy
     (the condition applies to XM only);
   - check the daily spread (74-94%) on the 10-31 / 11-01 development blocks, from the shared recorder's btc5m clob trades
     with tx hashes.
   Ingest politely: coalesced ranges, <= 2 threads, 429 backoff. The exam days' files must not be opened by me.
2. Condition 7, price part: freeze the per-wallet / per-leg pay-up anchor (finding 12) on BUILD-era calldata hours (10-09..15
   sample hours with the block-clock touch), then score it on the 10-20 / 10-21 archive orders.
3. Presence gain margin (+0.054 vs the 0.05 bar): rebuild the block-second presence model and its market-activity baseline with
   millisecond Binance spot book features that end before s - 1 (the archive, PIT by the block-time rule), fitted on 10-17..19 and
   scored on 10-20..22, both models with the same data, pre-registered.
4. On 11-01 06-12 (development, from 06:00 UTC): every pre-registered live test of iterations 9-12 (PIT vote / price / hazard, the
   Coinbase class rule of cbx12 = X100 step 2, edge_rule_V8, size-from-tick, PolyBolt X76), and X114 / X115 / X119 / X123 on the
   new feeds.
5. Condition 5 stays bounded by the public share of the lean (r ~0.32 for L, 0.48 for the net). The remaining candidates are the
   decision-level replica on the archive book (X113 step 5) and sub-second net-flow inputs. A further block-clock net-flow model is
   not one.
6. Still open from earlier: X5, X7 (funding), X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X59, X66, X70, X72, X76, X87, X88, X89, X90,
   X93, X98, X99, X100, X101, X104, X105, X107, X108, X109, X111.

Recorders at 02:51 UTC: shared recorder (pid 27184; clob_crypto, clob_wallets, rtds, sports connected), rec_lab6 v2 (14304),
rec_exam7 (32576), rec_fam8 (20608), rec_exam8 launcher (19600, starts 11-02 05:59), rec_pb10 launcher (15792, starts 11-01
06:00) and rec_eu11 (14192, asleep until 11-01 05:59): all alive. No new recorder this iteration. No polyrea bug found.
Cache: it13/ adds ~19 MB (stream labels, two-stream predictions, the decision-clock frame). The stale iteration-5
val_decision_presence.parquet (23 MB, used only by block_bins.py / decision_presence.py, which can rebuild it) was deleted, so
.cache/re/btc5m-bot stays at ~1.55e9 bytes (1.44 GiB). The reduced HF capture (trades with server ms, touch, Binance spot book,
RTDS) lives in the session scratchpad it13/hf_dl only (~1 GB). Re-ingest with it13/hfingest13.py (pinned revision, <= 2
threads, coalesced ranges).

Status after iteration 13: target not reached; target_metrics unchanged (presence 0.8747 vs 0.8211; side 0.7666; price 0.9512;
PnL 0.4758 / 0.4404; coverage 1 / 1). What changed is the account of the two failing conditions:
- condition 5 is bounded by the public share of the lean (two-stream models carry the same information);
- condition 7 is bounded by dispatch for XM under every pooled-stream oracle (0.30-0.41);
- the side at the true decision instant on VALIDATE is measurable from a public capture: 76.3% of taker orders at full coverage
  on the pre-registered split (~75% per decision). It is not limited by a missing venue series (the USD-M bookTicker adds
  nothing, finding 14) but by the late-window decisions and by DS's single-leg orders (74%).

PRE-REGISTRATION 4 (03:06 UTC, before it is fitted or scored): the EXAM-ROUTE decision-clock side model uses only inputs that the
public HF capture itself carries for every day, exam days included: Binance spot book microprice and mid returns over [a - K, a)
for K = 100 / 250 / 500 / 1000 / 2000 ms and rel. LightGBM with dcside13's PARAMS / ROUNDS, fitted on the 10-17..19 operator taker
orders and scored once on 10-20..22 (per order pooled and per wallet, and XM's one-sided windows). It goes into evaluate() as the
reported component 'side_decision_clock' whatever its score. It does not replace the frozen block-clock side in target_metrics in
this iteration.

17. PRE-REGISTRATION 4 SCORED AND THE EXAM ROUTE BUILT (results/dcside13_spot.json; code/dc_exam13.py, model_it13_dcside_spot.txt;
    final_rule.evaluate() now reports 'side_decision_clock').
    - The spot-book-only model (fitted on 10-17..19), scored once on 10-20..22: 74.2% per taker order (DS 72.1%, GF 77.8%, XM
      78.1%; by day 74.2 / 73.9 / 74.5%).
    - XM's one-sided windows: 81.4% (by day 89.9 / 80.5 / 72.6%), against 84.3% for the full venue model, which needs
      non-capture venue files and is therefore not exam-routed.
    - End to end, decision_clock_side() on 10-20 11:00-12:00 reads only the overlapping row groups (53 s) and reproduces the
      offline frame exactly (929 orders, 71.04%; DS 69.0%, GF 77.9%, XM 62.8%).
    - The development guard skips every capture day file that starts at or after H. The examiner's ALLOW_SEALED = True reaches
      the h1 / h2 day files that the listing shows exist.
    - The full venue model (model_it13_dcside_A.txt, 76.3%) is saved for the next iteration. Its exam route needs the Bybit
      ob / USD-M / OKX day archives that final_rule already downloads for the block-clock models.

Catalog closures this iteration besides the panel items: X84 (two decision streams, iteration-9 panel) is closed as tried with X121's
evidence. X59, X89 and X108 (anchor-interpolated historical match clocks) are closed as tried: X113 supersedes them, because the public
capture gives the server-ms match time directly (97% of txs). Open after iteration 13: 36 items (state.json
catalog_open_after_iteration13).
18. NO VALID OUT-OF-TIME CHECK ON THE LIVE RECORDINGS (dclive13.py, results/dclive13.json). The frozen spot route was scored on the
    2,155 live decisions of 10-31 12-18 with the spot bookTicker recorded by rec_exam7 (btc5m_xven 'bs'), shifted to the capture's
    clock (laptop t - median(t - E) of the USD-M records, which is -1,406 ms, + 131 ms).
    - The result is 59.6% (DS 59.8%, GF 59.9%, XM 58.4%; large 75.7%, small 58.7%; 64.8% in minutes 0-1).
    - The recorder keeps price-change-only, 30-ms-coalesced quotes: 6.8 records/s against ~140/s in the capture. So the 100-250-ms
      microprice returns the model depends on mostly do not exist there.
    This is an input-density mismatch, not evidence against the model. It also means the future-block exams must read the
    capture's own day files (which evaluate() does through dc_exam13), not the live recordings. An out-of-time development
    check needs the capture's 10-31 / 11-01 day files. Those files also contain sealed blocks, so they stay unopened until the
    question whether a footer-only row-group selection is allowed is settled (they are not opened now).
Iteration 13 ended 03:15 UTC (about 73 minutes of work).

### Iteration 14 (2026-11-01 03:52 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 03:53 UTC): released
lots none; the current block 11-01 00-06 is sealed; the next development block (11-01 06-12) starts after this iteration ends, so
there is no new live development data this iteration. Shared recorder running (`live.py status`: current block sealed, wallet feed
not stopped). Nothing sealed was read. Panel after iteration 13 (panels/iter13_*.md): 14 proposals, added as X125-X138 (information
P1-P5 = X125-X129, mechanics P1-P5 = X130-X134, assumptions P1-P4 = X135-X138). X125 and X135 are the same test (the decision clock
re-anchored on exchange time) and are run once; X134 and X138 are the same (the dispatch thinning ceiling); X131 and X137 are both
condition 5 at millisecond resolution; X126 and X136 are both the take hazard at the corrected clock.

Competing explanations (iteration 14; what separates them):
- E1 CLOCK-ARTEFACT TICK SNIPER: the side is the Binance spot microprice over the ~250 ms before EXCHANGE time m - 260 (a London
  host that reads Binance ~105 ms after the stamp and arrives 150 ms before its match); the 74-77% of pre-registrations 3 / 4 is
  what is left after cutting the trigger's last 50-60 ms. Separates: re-clocked side >= 80% per decision, a curve that is flat past
  the knee, no knee at placebo instants, no knee for crowd orders that do not co-arrive with the operator.
- E2 POST-DECISION CONTINUATION: the rise near exchange m - 250 is the continuation of a move the bot decided on earlier; separates:
  accuracy keeps rising past the knee, and orders that do not co-arrive show the same rise.
- E3 SCHEDULED CONFIGURATION (A/B ARMS): base sizes and dispatch weights are experimental settings by window index mod 4 and phase,
  not responses to inputs; separates: inside a phase the arm explains the size mix / DS share while the take rate and side do not
  move, with phase boundaries at restarts.
- E4 TWO-STREAM OPERATOR, OWN-STATE SIZE: the side is public (tick), the lean's size is own state (pyramiding); separates: original-
  size labels still give a size AUC < 0.6 on public inputs; the window net is formed in [0, 150) s where the public side is best.
- E5 RANDOM-THINNING DISPATCH: the wallet that carries a decision is an i.i.d. weighted draw (plus a per-wallet slot and a fixed leg
  order); separates: XM's PnL r under 2,000 redraws of the wallet from public weights stays below 0.47 at the 97.5% quantile.
- E6 ACK-LOOP FOLLOWERS: the 180-220-ms follower legs are re-decisions fired on the bot's own acknowledgements; separates: follower
  limits track their own-instant ask, and P(follower) depends on the previous leg's outcome.
- E7 PRIVATE INPUT: some input is in no public feed; separates: a residual after re-clocking that no venue's knee explains.
This iteration discriminates E1 vs E2 (pre-registration 5 below, with its controls), measures E3 (the A/B schedule) and, if time
allows, E5 (the redraw ceiling).

PRE-REGISTRATION 5 (written 03:58 UTC 11-01, before any re-clocked feature is computed or any model fitted; X125 = X135):
- Units: operator taker orders (fills role T, one per (tx, wallet, token)) of windows starting 10-17..22 that carry a capture match
  ms m (minimum exchangeTimestampMs of the tx in the capture's trade rows, revision f848a77c). Events: orders on the same (window,
  outcome) less than 300 ms after the previous order of the event; first leg = rank 0; m0 = the first leg's m.
- Anchor, fixed by physics, not by accuracy: c = D + T + r = 150 + 105 + 5 = 260 ms on exchange time (D = the measured taker delay,
  T = the iteration-11 Binance-to-London transit, r = reaction). Exchange-stamped series are cut at X* = m - 260; the capture's
  spot book (collector receive clock) is cut at a* = X* + 131 = m - 129 (131 ms = the capture's median spot-trade transit,
  iteration 13). Everything published at or before X* is published at least ~110 ms before the order arrived (m - 150).
- PRIMARY model 'dc14_spot' (the exam route; inputs the capture carries for every day): Up-signed spot-book microprice and mid
  returns over [a* - K, a*), spot-trade last-price returns over [X* - K, X*) (exchangeTimestampMs), K = 100 / 250 / 500 / 1000 /
  2000 ms, and rel. LightGBM with dcside13's PARAMS / ROUNDS, fitted on 10-17..19, scored ONCE on 10-20..22.
- SECONDARY model 'dc14_full': + Binance USD-M BTC / ETH aggTrades and OKX swap trades (exchange ms, cut at X*) and Bybit BTC / ETH
  100-ms book bins (bin end <= X*). Same fit / score. Reported, not exam-routed.
- Reported for both: per order (own anchor), per DECISION (every leg scored with features at its event's first-leg anchor m0),
  first legs only, per wallet, by window minute, by day and VALIDATE half (10-20 / 10-21..22), XM's one-sided windows (mean p of
  XM's orders), the old-anchor models on the same orders, and a market-only baseline from the capture's Polymarket trades (others'
  last prices and signed flow, operator txs excluded) with the same model class.
- Success = pooled accuracy >= 80% per decision AND per order on 10-20..22 at full coverage, with DS >= 77%.
- Falsification controls, reported whatever the result: (i) placebo anchors m - 3000 and m + 3000 (expect ~50%); (ii) the knee
  re-estimated on the FIT days only (univariate spot-book microprice sign over [m0 - c - 250, m0 - c), c = 400 .. 150 ms in 10-ms
  steps, two-segment linear fit) and the univariate gain from c = 260 to c = 200 on the fit days (E1 needs <= 1.5 points; E2 a
  continued rise); (iii) the knee per wallet and on the weekend fit days; (iv) a crowd control: non-operator taker BUYs more than
  1 s from any operator match on the same window, univariate profile against c on their own match ms (E1 needs it flat).
- Consequence fixed now: if success, 'dc14_spot' (anchor constants frozen) replaces model_it13_dcside_spot as the exam route
  'side_decision_clock', and target_metrics.side_accuracy reports its pooled per-order accuracy on 10-20..22 (the block-clock
  per-second value stays in the notes). If not, target_metrics.side_accuracy is unchanged and the route stays as it is.

Findings (iteration 14):
1. PRE-REGISTRATION 5 MET: AT THE PHYSICAL DECISION CLOCK THE SIDE IS 83.7% PER ORDER AND 82.4% PER DECISION ON 10-20..22 (dcclock14.py,
   dcfit14.py; results/dcclock14.json; frame in the session scratchpad it14/). 117,791 operator taker orders (10-17..22), anchor
   X = m - 260 ms exchange time (book receive m - 129), fitted on 10-17..19 (45,214 orders), scored once on 10-20..22 (72,577):
   - PRIMARY dc14_spot (spot book + spot trades from the capture, the exam route): per order 0.8369 (DS 0.8306, GF 0.8547, XM
     0.8132); per decision 0.8236 (DS 0.8265, GF 0.8257, XM 0.7833); first legs 0.8306. By day 0.857 / 0.837 / 0.815; 36-h halves
     0.852 / 0.823; per wallet and half DS 0.843 / 0.818, GF 0.877 / 0.839, XM 0.847 / 0.786 (per decision XM 0.807 / 0.764). By
     window minute 0.88 / 0.87 / 0.84 / 0.78 / 0.69; large 0.838, small 0.837. Share-weighted 0.8245. Top inputs: spot microprice
     250 ms (49% of gain), 100 ms (23%), 500 ms (16%).
   - Secondary dc14_full (+ USD-M BTC / ETH, OKX, Bybit BTC / ETH at the same exchange cut): 0.8516 per order, 0.8383 per decision
     (DS 0.846, GF 0.866, XM 0.836 per order). Not exam-routed (it needs non-capture archives).
   - Same orders: the frozen old-anchor route (m - 180 receive clock) 0.7421; market-only from the capture's non-operator
     Polymarket trades (last implied price, its 0.5 / 3-s changes, signed flow 1 / 5 s, |p - 0.5|, rel; same model class) 0.5676;
     own-inventory baseline (complement of the operator's realized net at block ts <= m - 2 s) 0.5394 on 95.9% coverage.
   - Controls: placebo anchors m - 3 s / m + 3 s 0.4985 / 0.4999. Knee re-estimated on the FIT days only (first legs, univariate
     microprice sign over [m0 - c - 250, m0 - c)): two-segment knee at c = 230 ms (level 0.834), slope 1.54 points per 10 ms before
     it and 0.07 after; 0.606 / 0.670 / 0.750 / 0.825 / 0.832 / 0.837 / 0.837 at c = 400 / 320 / 280 / 260 / 240 / 200 / 150; the
     gain from 260 to 200 is +1.2 points (weekend -0.3, 10-19 +3.0), from 320 to 260 +15.5. Per wallet the knee sits at 230 (DS,
     XM) and 250 (GF). Crowd control (975,955 non-operator taker BUYs more than 1 s from any operator match on the window): 0.556 /
     0.571 / 0.579 / 0.581 / 0.579 / 0.574 / 0.566 at the same cutoffs, flat (+1.0 point from 320 to 260). E1 (a clock artefact)
     is supported over E2 (post-decision continuation): the information arrives in a 60-ms band ending ~230-260 ms before the
     match, only for the operator, and nothing is added after it.
   - Pre-registered consequence applied: dc14_spot (model_it14_dcside_spot.txt; code/dc_exam14.py) replaces the iteration-13 route
     in final_rule.evaluate() and target_metrics.side_accuracy = 0.8369 (block-clock 0.7666 kept as side_accuracy_block_clock).
     End to end on 10-20 11:00-12:00 the route reads only that hour's row groups (58 s) and reproduces the offline frame exactly
     (929 orders, 0.8364 per order, 0.8138 per decision; old anchor 0.7104; placebo 0.476 / 0.489).
   - Physics: the knee implies Binance-to-arrival ~80-110 ms (the knee at 230-260 minus the 150-ms delay), i.e. a host near the
     Polymarket engine reading Binance directly; the information panel's reading. The old anchor stacked the collector's 131 ms and
     a 30-ms posting latency on top.
2. THE OPERATOR RUNS WINDOW-INDEX A/B ARMS (X130; ab14.py, results/ab14.json, ab14_hours.csv; mechanics panel replicated). Arm B =
   (start / 300) mod 4 in {1, 2}. Per UTC hour (324 development hours), Welch t of per-window means B vs A:
   - size: 37 hours with |t| >= 4 on the mean filled taker size, in runs 10-14 08-22, 10-15 18-21, 10-16 11-16, 10-18 13-17, 10-18 22
     -> 10-19 03, 10-19 07-11 (BUILD and VALIDATE). Inside them B windows fill 33.9 shares per taker order vs 24.6 (P(filled >= 45)
     0.445 vs 0.059); outside them B still 29.1 vs 26.3 (0.216 vs 0.069). On VALIDATE 76.5 / 80.0 / 84.0 / 78.0% of LARGE (>= 45
     filled) taker shares on 10-16..19 come from B windows (B holds 52-58% of all taker shares), 50 / 50 / 42% on 10-20..22.
   - dispatch: one phase, 10-21 16 -> 10-22 13 (21 flagged hours): DS share 0.685 (A) vs 0.426 (B), GF 0.263 vs 0.500, orders per
     window 92 vs 84; outside it DS 0.676 vs 0.677.
   - mod 2 shows nothing (1 hour with |t| >= 4).
   Consequences: the size classes on 10-16..19 are mostly the B arm's base size (two13's L stream, X49's size AUCs and the size
   component describe a configuration, not an input response); the dispatch phase makes DS / GF shares predictable from the window
   index inside it. Neither changes the side (finding 1 has no arm term) or the take rate. The calldata original sizes of the
   sample hours are reported in ab14.json (BUY takerAmount is already in shares in calldata_sample).
3. CONDITION 7 FOR XM IS A RANDOM-THINNING CEILING (X134 = X138; thin14.py, results/thin14.json; 10-20..22, 864 windows). The wallet of
   each TRUE operator taker decision (true side, size, realized PnL) is allocated by P^(wallet | public state at the decision) fitted
   on 10-17..19 (multinomial LightGBM on rel, hour, window index mod 4, re-clocked tick strength, leg rank; one-vs-rest AUC DS 0.710,
   GF 0.690, XM 0.670; log loss 0.724 vs 0.825 for base rates):
   - oracle (true decisions weighted by P^(XM); XM's maker part as the pooled maker PnL x XM's maker share): r with XM's window PnL
     0.393 (taker part 0.382; halves 0.415 / 0.373); with base-rate weights 0.320;
   - 2,000 redraws of the wallet from P^: corr(redrawn XM PnL, true XM PnL) median 0.165 [0.067, 0.255]; two redraws correlate
     0.185, so under thinning no predictor of XM's PnL can exceed sqrt(0.185) = 0.43; base-rate weights 0.31.
   - the dispatch-phase flag adds nothing for XM (the phase moves DS / GF only).
   Every oracle that knows the operator's decisions exactly stays below the 0.47 that condition 7 asks of XM. XM's realized PnL
   behaves like one draw of a random thinning of the operator's decisions (redraw-vs-true 0.165 against redraw-vs-redraw 0.185).

PRE-REGISTRATION 6 (written 04:13 UTC 11-01, before nfms14 is built or scored; X131 = X137, the millisecond nowcast for condition 5):
- Target: the operator's signed filled shares per (window, block second s), Up +, both roles (the nf12 target), 10-17..22.
- Features at block second s, all from data stamped before tau - 1000 ms (tau = the start of block second s; the same 1-s horizon as
  the frozen cells): from the capture's Binance spot book (exchange-equivalent = receive - 131) the microprice change over the five
  500-ms slices of [tau - 3500, tau - 1000) and over [tau - 5500, tau - 3500); on a 50-ms grid over [tau - 3500, tau - 1000) the
  max / min 250-ms microprice return, the signed sum of the 250-ms returns with |r| >= 0.5 bp and the up-minus-down count of such
  returns; spot-trade last-price change over [tau - 3500, tau - 1000) and [tau - 1500, tau - 1000) (exchange ms); from the capture's
  Polymarket trades (server ms; operator txs, W4 and W5 taker txs excluded) the Up-signed flow over [tau - 2000, tau - 1000) and
  [tau - 4000, tau - 2000), BUY counts on Up and Down over [tau - 2000, tau - 1000), the last implied Up price at tau - 1000 and its
  3-s change; rel; and the frozen nf (it4b) and nf12b predictions of the same cell (stacking).
- Model nfms14: LightGBM regression with nf12's PARAMS / ROUNDS, fitted on 10-17..19, scored once on 10-20..22.
- Adoption (the only scored candidate): nfms14 replaces the avg target of the exposure tracker ONLY IF trk_a (frozen TRK constants,
  strict fills, latency >= 2 s) with target nfms14 beats trk_a with the frozen avg target on BOTH pooled Pearson and Spearman over
  the 864 windows of 10-20..22. Reported either way: window-net r of nfms14 / avg / nf12b on 10-20..22, per-wallet PnL r, the 2-h
  block CI and the 36-h halves. If adopted, target_metrics.pnl_corr_* report the 10-20..22 values (disclosed) and the exam route
  (capture day files) is built before any claim.
4. PRE-REGISTRATION 6 SCORED: THE MILLISECOND NOWCAST DOES NOT LIFT CONDITION 5, NOT ADOPTED (X131 = X137; nfms14.py, results/nfms14.json;
   259,200 cells fitted on 10-17..19, 259,200 scored on 10-20..22; 16,478 W4 / W5 taker txs excluded besides the operator's).
   - Window-net r on 10-20..22: nfms14 0.514, frozen avg target 0.505, nf12b 0.459, it4b nf 0.470; early flow [0, 150) s: nfms14
     0.493 vs avg 0.540. The stacked model leans on the frozen nf (28% of gain), then the capture's Polymarket price change and
     flows (pm_d3 8%, pm_f2 4%, pm_bd1 4%) and the 500-ms spot slices (4% each).
   - Tracker trk_a on the 864 windows: avg 0.4973 / 0.4607 (CI [0.424, 0.563], halves 0.474 / 0.514; GF 0.390, DS 0.456, XM 0.015);
     nfms14 0.4845 / 0.4510 (GF 0.379, DS 0.469, XM -0.036). Lower on both, so not adopted (pre-registered rule).
   - The mechanics panel's 'signature if false' holds: at millisecond resolution the public share of the window net is ~0.51 (the
     same as the block-clock avg target, 0.505 on these days); the re-clocked side does not carry over to the net because the net is
     set by the size of the lean (own state, finding 2's arm sizes and the pyramiding), not by the side of each decision.
5. THE BLOCK-SECOND PRESENCE MARGIN DOES NOT SURVIVE A CAPTURE-AWARE MARKET BASELINE (X129 = information P5; pres14.py,
   results/pres14.json; VALIDATE block seconds, new models fitted on 10-17..19 because BUILD has no capture, scored on 10-20..22,
   341,960 cells):
   - frozen full model (model_it5_blk_full, BUILD-fitted) 0.8701; frozen augmented baseline (model_it9_blk_aug) 0.8174; the same
     augmented baseline refitted on 10-17..19 (AUGR) 0.8104;
   - capture-aware market baseline MSB = AUGR's features + others' BUY counts / sizes on o and on the other outcome in five 500-ms
     bins of server ms over [s - 3.5 s, s - 1 s) + SELL count on o (operator, W4 and W5 txs excluded; no reference feed): 0.8464.
     The capture prints carry 25% of its gain (top: pm_o_n_2 / pm_o_n_3, the bins 2.0-1.5 s and 2.5-2.0 s before the block second,
     where the co-arriving fast crowd's matches sit);
   - gains: frozen full vs MSB +0.0237, 2-h block CI [0.0172, 0.0314] (p < 0.0005 for > 0, but below the 0.05 bar); vs AUGR +0.0597;
     FULLMS (frozen features + the capture prints + knee-clock spot slices / sharp ticks, refitted on the same three days) 0.8600,
     +0.0136 over MSB [-0.003, 0.026];
   - per wallet (full / MSB): GF 0.863 / 0.842, XM 0.883 / 0.882, DS 0.851 / 0.828; halves 0.879 / 0.854 and 0.862 / 0.839.
   Condition 2's +0.054 margin belongs to the block clock: a baseline that sees the crowd's co-arriving matches at server ms (1-2 s
   before the operator's block second) recovers half of it. Honest status: condition 2 FAILS against the stronger (capture-aware)
   market baseline on the days where it can be built (+0.024 < +0.05). target_metrics.presence_* now report this comparison.
6. NO VENUE ADDS INFORMATION AFTER THE BINANCE SPOT KNEE; THE KNEE IS THE BOT'S BINANCE ROUTE (X127 = information P3, compact; knee14.py,
   results/knee14.json; first legs, fit days, each venue on its own exchange clock, univariate):
   - two-segment knees: spot book 230 ms (level 0.837, slope after ~0), spot trades 220, USD-M BTC 220, USD-M ETH 210, OKX swap 200.
     On covered orders at c = 260: spot trades 0.733 (28% covered), USD-M BTC 0.728 (39%), USD-M ETH 0.764 (47%), OKX 0.712 (19%).
   - Bybit BTC (100-ms book bins) has no knee: it keeps rising past the arrival (0.645 / 0.676 / 0.795 / 0.822 at c = 260 / 230 /
     150 / 100), i.e. it moves AFTER the order has arrived (c < 150): a lagging copy of the Binance move, not an input.
   - No venue's knee lies later than Binance's by a transit advantage (Deribit and Coinbase not fetched this iteration). The fast
     input is the Binance spot book read ~80-110 ms after the stamp; the bot sits near the Polymarket engine.
7. EVEN AT THE CORRECTED CLOCK FEW DECISIONS ARE LOCKED TO A PRICE-LEVEL TICK; THE TRIGGER IS THE SPOT QUEUE IMBALANCE (X126 = X136, locked
   share; knee14.json): a spot microprice net move toward o >= 0.1 bp over the knee band [m0 - 320, m0 - 230) precedes 7.7% of first
   legs (placebo bands 3 s / 5 s earlier 1.2%; DS 6.9, GF 9.9, XM 11.2%); a spot mid price-level change toward o 9.2% (placebo 1.5%).
   The side information (83%) is carried by sub-tick microprice moves (L1 queue-size changes): the microprice changes in 96% of the
   250-ms windows and points to the side 84% of the time; a price-level change is the exception. X111's 'only ~9% locked' stands on
   the right clock with spot BTC included; what the 'unlocked' decisions follow is the queue imbalance, which no earlier recorder kept.
8. AT THE KNEE CLOCK THE TAKE ITSELF IS DECODED: A 50-MS DECISION HAZARD REACHES AUC 0.889 AGAINST 0.759 FOR POLYMARKET ACTIVITY
   (X126 = X136, compact form, designed before it was scored and scored once, NOT pre-registered as a target metric; hazard14.py,
   results/hazard14.json; models model_it14_hazard_*.txt; exam route code/dc_hazard14.py, wired into evaluate() as
   'presence_decision_clock'):
   - unit: 50-ms bins on the exchange-equivalent clock of every (window, outcome) of 10-17..22, bin end e; label: an operator FIRST
     leg on that outcome with m0 in [e + 205, e + 255) (the fit-day knee 230 +- 25 ms); features end at e (spot book / trades) and
     e + 50 (others' Polymarket prints, server ms; operator, W4 and W5 txs excluded), all before the order's arrival at m0 - 150;
     negatives sampled 1% with weight 100; fit 10-17..19 (127,793 bins, 34,438 positives), scored once on 10-20..22 (150,929 bins,
     57,629 positives).
   - weighted AUC: full 0.8885, Polymarket-only baseline 0.7591, spot-only 0.8064; gain +0.1294, 2-h block CI [0.122, 0.137];
     halves 0.899 / 0.761 and 0.878 / 0.758; per wallet (first legs the wallet carried; the other wallets' first legs count as
     negatives) DS 0.881 / 0.749, GF 0.903 / 0.773, XM 0.919 / 0.841. Top inputs: the 100-ms spot microprice return toward o (25%
     of gain), |p - 0.5| (21%), the 250-ms return (13%), spot book update count (5%).
   - End to end on 10-20 11:00-12:00 the route reproduces the offline positives exactly (718) and the AUC within sampling noise
     (0.922 vs 0.920; baseline 0.807 vs 0.812; 70 s).
   - Reading: on the right clock the operator's selection is mostly the Binance spot queue-imbalance move toward o against the
     Polymarket price level; the crowd's co-arrivals cannot help a baseline at the decision clock because they match after the
     decision. Caveats: taker first legs only (maker fills are not in the label, so the unit does not cover >= 80% of fills); not a
     pre-registered target metric; the block-second presence (target_metrics) fails the capture-aware baseline (finding 5).
9. FOLLOWER LEGS ARE RE-DECISIONS ON FRESHER INFORMATION (X128 = information P4, steps 1-3 partial; results/legs14.json, inline):
   gaps between consecutive legs of an event (six days) are bimodal: 0-40 ms (8,773; fan-out) and 180-220 ms (4,133; one taker delay
   + 30-70 ms). On 10-20..22 the side at the follower's OWN anchor vs its event's first-leg anchor: fan-out (< 60 ms) 0.844 / 0.821,
   60-150 ms 0.884 / 0.776, sequential 150-300 ms 0.863 / 0.790 (first legs 0.831). Wallet transitions: fan-out DS -> GF 7,527, XM
   after DS 797 / after GF 239; sequential GF -> DS 5,186, DS -> GF 2,292. So the sequential follower is a new decision taken after
   the previous leg's response (~150 + RTT) on the then-current spot book, mostly by the other main wallet. Steps 1 (limit vs
   own-instant ask, calldata), 2 (P(follower) by the previous leg's fill outcome) and 4 (dispatch replay) are open.

PRE-REGISTRATION 7 (written 04:33 UTC 11-01, before hazflow14 is run; X113 step 5 / X137 strong form, the decision-hazard nowcast for
condition 5): every 50-ms bin of every (window, outcome) of 10-17..22 is scored with the frozen model_it14_hazard_full.txt; per
window second s the hazard imbalance h(s) = sum over bins with end e in [s - 2, s - 1) s of (P^(Up) - P^(Down)), known before s - 1
(the horizon of the frozen cells); nfhaz14(s) = c x h(s), c = no-intercept OLS of the operator's per-second signed flow on h on
10-17..19. PRIMARY candidate: the tracker target 0.5 x avg + 0.5 x nfhaz14 ('mix14'), adopted ONLY IF trk_a (frozen TRK constants,
strict fills, latency >= 2 s) beats the frozen avg target on BOTH pooled Pearson and Spearman over the 864 windows of 10-20..22.
nfhaz14 alone and the window-net r of each are reported.
10. PRE-REGISTRATION 7 SCORED AND ADOPTED: THE DECISION-HAZARD IMBALANCE ADDS TO THE TRACKER TARGET, BY A LITTLE (hazflow14.py,
    results/hazflow14.json; per-second hazard imbalance in the session scratchpad it14/hazflow14.parquet):
    - h(s) from all 50-ms bins of every window (3.1M per day); c = 5.935 (no-intercept OLS on 10-17..19); per-second r with the
      operator flow 0.085 (fit) / 0.063 (score): weak per second, because the bin-to-block-second mapping is loose (block lag
      1.25-3.14 s).
    - Window-net r on 10-20..22: nfhaz14 alone 0.370, avg 0.505, mix14 0.5125.
    - Tracker trk_a, 864 windows: mix14 0.5065 / 0.4674 (CI [0.437, 0.571], halves 0.495 / 0.515; GF 0.401 / 0.382, DS 0.467 / 0.448,
      XM -0.001 / 0.023) against avg 0.4973 / 0.4607; nfhaz14 alone 0.390 / 0.352. mix14 is higher on both, so it is ADOPTED under the
      pre-registered rule: final_rule.evaluate() computes it through dc_hazard14.hazard_imbalance (capture day files) and makes it
      the primary tracker ('mix14_a'); target_metrics.pnl_corr_* = 0.5065 / 0.4674 (10-20..22, disclosed). The gain is small (+0.009 /
      +0.007, inside the CI) and Spearman stays below 0.5: condition 5 still fails, and condition 7 fails for XM.
    - The mix14 tracker trades $145k (vs $276k for avg) at -2.3% before rebates (avg -2.8%).

11. THE ORIGINAL SIZE IS NOT A RESPONSE TO THE KNEE-CLOCK MOVE (X132 steps 1-3, compact; size14.py, results/size14.json; 5,293 cluster
    taker orders of the six calldata sample hours on 10-17..22 joined to the decision-clock frame; original size = BUY takerAmount):
    - menus by arm: 10-17 / 10-18 arm A 30 (78-80%) / 50, arm B 50 only (97%); from 10-19 30 / 100 in both arms (large 11-21%).
      So in the 10-16..19 size phase the B arm's single size IS the large label of two13 (finding 2).
    - large = above the (day, arm) modal size: AUC of |250-ms spot microprice return| at the knee anchor 0.598 (first legs 0.619;
      DS 0.591, GF 0.562, XM 0.567), signed toward the outcome 0.595, |p - 0.5| 0.478, rel 0.499.
    The panel's 'signature if false' (AUC < 0.6 with original labels) holds within wallet: the size is configuration (arms, menus)
    plus own-state pyramiding, not an input response. The L2-depth part of X132 (visible depth at o's ask) is not tested; X132 stays
    open for it.
12. THE KNEE-CLOCK HAZARD REPLICATES IN THE REVERSE SPLIT (X136 step 'reverse fit'; hazard14.py with HZ_REVERSE=1, results/
    hazard14_reverse.json; models not saved): fit 10-20..22, score 10-17..19 (incl. the weekend): 0.925 vs Polymarket-only 0.781
    (+0.145, CI [0.135, 0.154]); halves 0.932 / 0.775 and 0.917 / 0.782; per wallet DS 0.920 / 0.769, GF 0.940 / 0.807, XM 0.940 /
    0.863. Exam-route data access is now segment-wise (<= 6 h of window starts per pass; only overlapping row groups are read, the next
    day's file only when a segment reaches hour 23): dc_exam14 reproduces the offline frame exactly again (929 orders, 0.8364 /
    0.8138, 50 s), and dc_hazard14's hazard imbalance matches the offline h at r 0.9993 (W4 / W5 are not excluded in the route).
13. FOLLOWERS DO NOT WAIT FOR A REMAINDER (X128 step 2, compact; follow14.py, results/follow14.json; 117,791 taker orders of 10-17..22):
    after a leg whose remainder rested and was hit (its order hash later has maker fills; 16,994 legs, median 12 filled shares) the
    next leg of the event follows within 150-300 ms 8.2% of the time, within 60 ms 4.7%, within 300 ms 16.2%; after a leg without a
    resting fill (100,797, median 30 = fully filled) 9.2% / 9.6% / 22.8% (first legs 7.0 vs 8.2% sequential). XM 14.1 vs 12.6%. The
    sequential follower is not triggered by a remainder; it is slightly more frequent after full fills, which a persisting signal
    explains as well as an acknowledgement loop. E6 is not separated from a continuing hazard; X128 stays open for steps 1 and 4.

14. HALF OF THE SELECTION SHARED WITH THE FAST CROWD IS THE KNEE-CLOCK SPOT DESIGN (X136 / X101 on the knee clock; coat14.py,
    results/coat14.json; the 150,929 scored hazard bins of 10-20..22; crowd take = a non-operator taker BUY on the same outcome
    matched in the operator's knee band [e + 205, e + 255), W4 / W5 excluded; diagnostic only): P(crowd take | operator took the bin)
    0.2334 vs 0.0744 otherwise; raw log OR 1.3312; conditional on the knee-clock hazard score
    0.625 (53.0% explained), on the Polymarket-only score 1.0327 (22.4%), both
    0.6026 (54.7%). Iteration 12 explained 14-21% with the USD-M onset design on the laptop clock. The panel's
    signature (>= 50% explained) is met: the 'unrecorded shared input' was mostly the full-rate Binance spot book on the right clock.
    A residual log OR of ~0.6 remains (the exact tick inside the 50-ms band, the touch, or a shared route). Standard errors are
    understated by the 1% negative sampling weights.

15. DERIBIT (LONDON) AND COINBASE ARE LAGGING COPIES OF THE BINANCE MOVE, NOT FASTER INPUTS (X127 steps 1-2 for the remaining venues;
    knee14b.py, results/knee14b.json; cached hourly trades of 12 VALIDATE hours on 10-17..22, 7943 first legs): Deribit's agreement keeps
    rising past the arrival (on covered orders 0.685 / 0.720 / 0.797 / 0.810 at c = 260 / 230 / 150 / 100 ms), Coinbase likewise (0.608 / 0.648 /
    0.710 / 0.725). In the band after the Binance knee and before the arrival, [m0 - 230, m0 - 150), Deribit moves for 25.6% of first legs and
    agrees 0.8133, but where it disagrees with the Binance spot sign at the knee (393 legs) Deribit is right only
    0.2366 (Coinbase 0.3231); letting the late move override the Binance sign lowers the side from 0.8331 to
    0.8072 (Coinbase 0.816). No venue on disk carries information the bot uses beyond the Binance spot book at its knee.
    E7 (a faster or private input) has no support among Binance spot / USD-M, OKX, Bybit, Deribit and Coinbase; the per-trader knee
    map (X127 step 3) is not done.

16. SCOPE OF A DECISION-LEVEL PRESENCE (results/scope14.json; VALIDATE fills): taker-role fills are 62.6% of the operator's fills;
    fills of orders that had at least one taker fill (the decisions the hazard labels, credited with their remainders' maker fills)
    are 77.9% of fills (DS 79.8, GF 75.8, XM 68.7%) and 86.3% of the absolute PnL; 40.7% of maker fills belong to such orders. The
    other 22% of fills come from fully lost races (no taker fill). A decision unit that also labels the fully lost races (their book
    insertion at the old ask, visible in the capture's price_change events) would cover all fills; with filled decisions only the
    fill scope is just under the 80% bar, the PnL scope above it.

17. THE 'OPERATOR STATE' WAS MOSTLY SPOT ACTIVITY ON THE WRONG CLOCK (X136, own-kernel increment; hazard14.py with HZ_OWN=1,
    results/hazard14_own.json; own state, mechanism only, models not saved): kernels of the operator's own earlier first legs on the
    window (any outcome and same outcome, 30-s and 60-s decay, decisions matched before the bin) added to the knee-clock hazard: full
    0.8885 -> 0.8988 (+0.0103), Polymarket-only 0.7591 -> 0.7876 (+0.0285). On the iteration-12 onset tables the same kind of
    kernel added +0.037 (0.681 -> 0.718). The panel's signature (the own-kernel increment at least halved) is met: about three
    quarters of the 30-60-s 'operator state' was spot-book activity that the USD-M onset design on the laptop clock did not see.

18. THE DECISION-CLOCK GAIN SURVIVES A STRONGER POLYMARKET BASELINE (hazard14.py with HZ_PM2=1, results/hazard14_pm2.json; models not
    saved): adding to the Polymarket-only design the age of the last print on o and on the other outcome, BUY counts over 0.5 s and 10 s,
    SELL counts and BUY volume over 1 s on both outcomes, the other outcome's last price and the last print size gives 0.7623 (from
    0.7591); the full model stays 0.8885 (0.8894 with the extra features): the gain over the stronger baseline is
    +0.1262. At the decision clock the crowd's prints cannot reveal a decision that has not yet been matched, so the
    co-occurrence route that erodes the block-second margin (finding 5) is closed by construction.

19. THE POLYMARKET TOUCH ADDS NOTHING BEYOND THE KNEE-CLOCK HAZARD (X119, and the best-ask part of X114; touch14.py, results/touch14.json;
    10-20 / 10-21 scored bins, the only days with the capture's touch; fit one day, score the other): touch features at the bot's
    Polymarket view (e + 50 ms: o's best ask / bid, the age of the best ask, best-ask changes and moves over 250 / 1000 ms, the other
    outcome's ask) on top of logit(P^ hazard): AUC 0.8935 -> 0.896 and 0.9016 -> 0.9031 (+0.0025 / +0.0015). Decisions do come
    when o's ask is young (median age 433 ms vs 1100 ms; changed in the last 250 ms 0.377 vs
    0.1955), but that is the makers requoting on the same spot moves: given the spot design the touch carries no
    selection. The size-only requotes of X114 (queue sizes at o's touch) need the capture's askSize / bidSize columns (not ingested).

20. THE ARMS AS A NATURAL EXPERIMENT, ECONOMICS ONLY (X130 step 3, descriptive; results/abecon14.json; all development windows < H): in the
    size phases B windows trade 3634 vs 2751 gross shares per window and pay 45.0 vs 34.7 USD of taker fees, for a return before
    rebates of -0.0006 vs 0.0135 (-1.1 vs 18.1 USD per window; 220 / 221 windows); in the dispatch phase -0.0101 vs
    0.0008; outside both 0.0096 vs 0.0012. Per-window PnL is too noisy at these counts for a verdict (no test run); the larger
    base size buys more fee volume (the rebate is half the taker fees) at an unchanged or lower gross return. Fill fractions and race
    losses per arm (calldata) are not measured.

Panel proposals of iteration 13 (catalog X125-X138) and what happened to them:
- X125 = X135 (re-clock the side on exchange time): tried, pre-registration 5 met (finding 1); exam route rebuilt.
- X126 (hazard on the knee clock): tried in compact form (finding 8; 50-ms label instead of 30 ms); exam route dc_hazard14.
- X127 (per-venue knee map): tried for every venue on disk incl. Deribit and Coinbase (findings 6 and 15); the per-trader knees (step 3) are open.
- X128 (follower legs on acknowledgements): partly tried (finding 9); open.
- X129 (presence margin vs a capture-aware baseline): tried (finding 5): the block-second margin falls to +0.024.
- X130 (A/B schedule): step 1 tried (finding 2) and the economics of step 3 (finding 20); the arm-aware relabel, fill fractions per arm
  and the exam-risk check are open.
- X131 (early-segment ms model) and X137 (ms nowcast): tried (findings 4 and 10): nfms14 not adopted, mix14 adopted (+0.009).
- X132 (true size decision with original sizes): open (not run).
- X133 (maker-role remainder process): open (not run).
- X134 = X138 (random-thinning ceiling for XM): tried (finding 3): oracle 0.39, redraw ceiling 0.43 < 0.47.
- X136 (strong form of X126): tried (findings 12, 14, 17): the reverse fit replicates, the knee-clock design explains 53% of the crowd
  co-take, and the own-kernel increment falls from +0.037 to +0.010.
Also closed this iteration: X111 (step 3 answered at the corrected clock, finding 7), X101 (finding 14), X98 (the bot's clock: findings 1, 6, 8,
15), X109 (step 3: finding 17; step 4 not run) and X119 (finding 19). X113 stays open for its step 5 (the decision-level
replica on the archive book; mix14 is its first, aggregate form).

## Next (iteration 15)

1. Condition 2 at the decision clock (the honest presence route): pre-register the knee-clock hazard as a presence metric with a
   fill-covering unit (filled decisions cover 77.9% of fills and 86.3% of |PnL| (finding 16); add the fully lost races through
   their book insertion in the capture price_change events), so that the scope condition (>= 80% of fills) holds;
   then the examiner-style baseline (same model class, Polymarket-only, capture prints) and the 2-h CI. The block-second unit
   fails against a capture-aware baseline (+0.024).
2. Condition 5: mix14 is +0.009; the decision-level replica (X113 step 5) with the hazard as P(take), the side model as side and
   the replica's own sent position for size (own-state size feedback), executed under the tracker's strict-fill rule; and the
   arm-aware size (X130 step 2: B windows carry the larger base size in phases, which a public rule can know from the window index).
3. X130 steps 2-5 (arm-aware relabel of two13 / ls13 / side13; size and dispatch natural experiments; mod-4 terms in the size and
   dispatch models; the exam-risk simulation for condition 7's halves), X132 (L2 visible depth), X133 (maker remainder replay on
   the archive book), X128 steps 1 / 4, X127 step 3 (per-trader knees).
4. On 11-01 06-12 and later development blocks: the live recorder keeps coalesced spot quotes only, so the knee-clock models cannot
   be checked live; add a full-rate Binance spot bookTicker recorder (tools/live.py Writer, hard stop, < 100 MB) before the next
   development block, and score dc_exam14 / dc_hazard14 on it out of time.
5. Still open from earlier: X5, X7, X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X66, X70, X72, X76, X87, X88, X90, X93, X99, X100, X104, X105, X107, X113, X114, X115, X122, X123, X124, X127, X128, X130, X132, X133.

Recorders at the end of iteration 14: the shared recorder runs (live.py status: current block sealed, wallet feed not stopped); no
recorder was started this iteration. No polyrea bug found. Cache: nothing large was added to .cache/re/btc5m-bot (the iteration-14
frames live in the session scratchpad it14/, ~150 MB); new small files in code/ (models model_it14_*.txt) and results/.

Status after iteration 14: target not reached. On VALIDATE (10-20..22 where the capture exists):
- condition 2 (presence): FAILS against my stronger, capture-aware baseline at the block clock (0.870 vs 0.846, +0.024); at the
  decision clock the take hazard is 0.889 vs 0.759 (+0.129) but it covers taker first legs only and was not pre-registered;
- condition 3 (side): MET at the decision clock (0.837 per taker order, pre-registered; XM 0.813, halves 0.847 / 0.786);
- condition 4 (price): met (0.951, trivial touch anchor);
- condition 5 (PnL): NOT met (0.507 / 0.467 with the adopted mix14 target);
- condition 7: NOT met for XM's PnL (a measured random-thinning ceiling of ~0.43 < 0.47).
Iteration 14 ended about 05:02 UTC 11-01 (about 70 minutes of work).

### Iteration 15 (2026-11-01 05:46 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18, 11-01 06-12)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 05:48 UTC): released lots
none; the current block 11-01 00-06 was sealed; 11-01 06-12 is a development block (d + j = 2). Shared recorder running (pid 27184). Panel
after iteration 14 (panels/iter14_*.md): 12 proposals, added as X139-X150 (information P1-P5 = X139-X143, mechanics P1-P4 = X144-X147,
assumptions P1-P3 = X148-X150). X143 (information P5) and X144 (mechanics P1) are the same test (filled size = visible depth) and are run
once; X145 (mechanics P2) and X148 (assumptions P1 step 2) share the fill-resolving simulator.

PIVOT (required: progress < 0.02 over two iterations). New paradigm: DEPTH-LIMITED EXECUTION. The unit is the operator's taker order as an
execution against the visible ask book; the new data source is the public capture's L2 level sizes (price_change askSize / book asks,
never ingested before); the target is the realized fill (min(menu, depth at or below the limit)) and the window net it builds. Second,
independent paradigm tested in parallel: the operator's coins as a recoverable PRNG stream (salts as an input; a cryptanalytic model class).

Competing explanations (iteration 15; what separates them):
- E1 DEPTH-LIMITED EXECUTION: the window lean = decisions x min(menu, visible ask depth <= L at the bot's view). Separates: on the true
  decision record, sum of dc14 side x E[min(menu, D<=L)] reaches r(N) >= 0.6 against 0.39 for the public menu, and >= 70% of depth-bound
  calldata orders fill within 10% of min(orig, D<=L).
- E2 HOLD-QUEUE RACE: the fill is set by co-arrivals and maker cancels inside the 150-ms hold, not by the depth the bot saw. Separates:
  D<=L at m - 1 (the book the order met) predicts the fill far better than D<=L at m - 180 (the bot's view).
- E3 OWN-STATE PYRAMIDING: the size is a menu coin plus a short-leg gate on the realized net; given the depth, the menu and the gate still
  add. Separates: min(menu, D) beats D alone; the gate adds within wallet.
- E4 PRNG COINS: the wallet / size / take choices are Math.random draws of the same isolate that makes the salts. Separates: the salts of
  same-ms copies solve as nearby V8 (or JSC) outputs, validated by exact prediction of held-out salts.
- E5 CSPRNG OR ANOTHER RUNTIME: the salts are not recoverable V8 output. Separates: no consistent V8 state in >= 20 copy groups while the
  same solver recovers real Node output.
- E6 LATE-HORIZON SIXTH (information P1): ~17% of decisions use a Binance L2 state the L1 capture lacks. Separates: Rabbit 10-20 L2
  features lift the side on dc14-wrong orders from 0.37 to >= 0.60.
- E7 PER-WALLET PIPELINES (information P2): XM fires on its own, earlier clock. Separates: XM-vs-others AUC >= 0.85 with clock features.
This iteration discriminates E1 / E2 / E3 (the capture's L2) and E4 / E5 (salts), and starts the full-rate recorder that E6 / X142 need.

Live lab: rec_bn15 (code/rec_bn15.py; information P4 = X142) records the full-rate Binance spot btcusdt@bookTicker + @trade and USD-M
btcusdt@bookTicker + @aggTrade (every message, receive-time us; feeds btc5m_bnspot / btc5m_bnusdm through the Writer) for the
development block 11-01 06:00-12:00 (start 05:59:30, hard stop 12:00, disk cap 280 MB, USD-M stops first at 170 MB). Started 05:56 UTC
(pid 9312). First 140 s: spot quotes 25/s, spot trades 10/s, USD-M quotes 153/s, ~15 bytes per record compressed.

PRE-REGISTRATION 8 (written 06:08 UTC 11-01, before hazflowD15 is run and before any L2 depth of 10-21 / 10-22 is looked at; X144 step 2 =
X143 step 4; code/hazflowD15.py): every 50-ms bin of every (window, outcome) of 10-20..22 is scored with the frozen
model_it14_hazard_full.txt; each bin's probability is weighted by the expected realized taker fill at the bot's Polymarket view (grid
time e + 50 ms, server clock): w = (1 - pL) min(30, D1) + pL min(100, D1), D1 = the capture's ask depth at best + 0..1 c of that outcome,
pL = P(original size >= 90) of the operator's taker orders on the pre-10-20 calldata hours with the 30 / 100 menu. hD(s) = sum over bins
with end e in [s - 2, s - 1) s of P^(Up) w(Up) - P^(Down) w(Down); nfhazD15 = cD x hD, cD = no-intercept OLS of the operator's
per-second signed flow on hD on 10-20 only (the capture L2 exists only from my ingest; 10-20 is the fit day). Scored once on 10-21..22
(576 windows) with tracker trk_a (frozen TRK constants, strict fills, latency >= 2 s): avg, mix14 (frozen), mix15 = 0.5 avg + 0.5
nfhazD15. ADOPTION: mix15 replaces mix14 only if it beats mix14 on BOTH pooled Pearson and Spearman over those 576 windows. Reported
either way: window-net r, per wallet, 2-h block CI, the day halves.

Data added (iteration 15): the ASK-side L2 book of every BTC 5m token on 10-20, 10-21 and 10-22 from the public capture's price_change
level sizes and book snapshots (code/l2ingest15.py; pinned revision f848a77c; columns eventType / exchangeTimestampMs / tokenId /
askPrice / askSize / bestAsk / asks only, row groups by HTTP range requests, 2 threads; 570-600 MB read per day, 11-13 min; nothing raw
kept). The market channel mirrors the outcomes (an Up ask at p is a Down bid at 1 - p), so the ask rows of both tokens give both ask
books. Reconstruction check: the rebuilt best ask equals the capture's own bestAsk after 98.2 / 98.4 / 98.2% of ask rows (8.0M / 7.9M /
7.3M checked); 0.6-0.9% of ask rows are sub-cent levels (dropped). Kept (session scratchpad it15/, ~460 MB): the 100-level ask vector
at m - 1 / m - 150 / m - 180 for every operator taker order with a capture match ms (73,577 orders), a 50-ms grid of best ask and
depth at best + 0..4 c for both outcomes of every window, and (10-20 only, l2ingest15b.py) the ask vector at 16 offsets m - 1 .. m - 500.

Findings (iteration 15):
1. THE REALIZED TAKER SIZE IS NOT THE VISIBLE DEPTH (X143 = X144 step 1; depth15.py, results/depth15.json; 10-20..22, 73,577 operator
   taker orders, 759 windows; calldata limits and original sizes for 3,718 of them). E1 is rejected:
   - calldata orders: 44.1% fill less than their original size; for those, the ask depth at or below the limit is a median 107 shares
     at the bot's view (m - 180) and 71 at the arrival (m - 150) against a median fill of 11; only 11.6% (m - 180) / 15.8% (m - 150) of
     them fill within 10% of min(original, visible depth) (signature >= 70%);
   - oracle ladder on the TRUE decision record (dc14 side x size, r with the window net N over both roles): true total fill 0.747
     (reproduces the mechanics panel), public menu 0.395, unit 0.403, min(E[menu], depth at the bot's view) 0.430, at the arrival
     0.440, E[min(menu, depth)] 0.431, depth alone 0.367 (signature >= 0.6). The visible depth is worth +0.035 of r(N).
2. THE DEPTH THE BOT SAW IS CANCELLED DURING THE 150-MS HOLD, NOT TAKEN (race15.py, decay15.py; results/race15.json, decay15.json):
   - decay of the depth at or below L before the match (10-20, ask vectors at m - x): calldata depth-bound orders (453, median fill 14)
     median 357 / 187 / 108 / 71 / 31 / 17 / 15 / 0 shares at x = 500 / 250 / 180 / 150 / 100 / 50 / 35 / 20 ms; fully filled orders
     255 / 205 / 200 / 167 / 122 / 100 / 96 / 60 / 50. The capture's book events of a match are stamped ~20-35 ms before its trade rows
     (the step between m - 35 and m - 20 is the match itself), so on the book clock the order meets the book ~25 ms before m: what is
     left there (median 15) is what a depth-bound order fills (14);
   - accounting of the gap D(m - 180) - filled (all 73,577 orders): non-operator taker BUYs of o at <= L and SELLs of the other outcome
     at >= 1 - L matched in (m - 180, m) explain 3.5% of it, the operator's own other legs 1.0%; the rest (~95%) leaves the book
     untraded, i.e. makers cancel (XM orders: crowd 10.2%). E2 holds in its cancel form: the hold queue that binds is the makers'
     cancellation race, not co-arriving takers;
   - the fill is barely predictable at the decision: LightGBM on the book at the bot's view + decision state + wallet, fit 10-20,
     scored 10-21..22 (fillpred15.py): r(pred, filled) 0.291 (DS 0.275, GF 0.259, XM 0.175; state only 0.191); ladder r(N) with it
     0.391 vs public menu 0.350 vs true fill 0.696 on the 494 score windows.
   Consequence for condition 5: ~0.3 of the window-net r on the TRUE decisions (0.70-0.75 -> 0.39-0.44) is set by maker cancellations
   inside the taker delay, after the decision. This replaces X82's race-lottery bound in the account and answers the mechanics panel's
   "if false" branch: the binding race is the makers' cancel race, measured on the capture.
3. PRE-REGISTRATION 8 SCORED: THE DEPTH-WEIGHTED HAZARD NOWCAST IS NOT ADOPTED (hazflowD15.py, results/hazflowD15.json; cD = 0.10888 on
   10-20, pL = 0.2268 from 3,474 pre-10-20 calldata orders of the 30 / 100 menu). On the 576 windows of 10-21..22, tracker trk_a: mix15
   0.4772 / 0.4556 against mix14 0.4792 / 0.4594 (avg 0.4809 / 0.4591; nfhazD alone 0.3446 / 0.3361); window-net r mix15 0.5024 vs
   mix14 0.5032. Lower on both: mix14 stays the target. (The rebuilt unweighted h correlates 1.0 with iteration 14's h.)
4. THE POLYMARKET BOOK PREDICTS THE OPERATOR'S DECISIONS AS WELL AS THE BINANCE TRIGGER DOES: THE DECISION-CLOCK PRESENCE MARGIN DOES
   NOT SURVIVE A BOOK-AWARE MARKET BASELINE (X146 step 2, X114; hazbook15.py, results/hazbook15.json; the scored knee-clock hazard bins of
   10-20..22, fit 10-20, scored once on 10-21..22, 98,827 bins, weighted AUC; book features at the bot's Polymarket view e + 50 ms:
   best ask and depth at best + 0..4 c of both outcomes and their 100 / 250 / 1000-ms changes):
   - frozen full hazard 0.8808; frozen Polymarket-trades-only 0.7570; book only 0.8706; trades-only + book (PMB) 0.8730; full + book
     0.9054. Gains: full - PMB +0.0078 [0.0022, 0.0127]; (full + book) - PMB +0.0324 [0.0278, 0.0365]. Top book input: the change of
     o's ask depth (best .. best + 4 c) over the last 100 ms (makers pulling o's asks).
   - Own-print check: on the 62% of score bins with no operator match on the window in [t - 1500, t + 100] ms (15,919 positives), full
     0.912, book only 0.911, PMB 0.910: the book signal is other makers' quote changes, not the operator's own fills.
   Reading: the makers and the operator react to the same Binance move; the makers' cancellations show in the Polymarket book within
   ~50 ms of the Binance stamp, before the operator's order arrives (~e + 80..130), and the operator takes the asks that are left. At
   the decision clock a market-only baseline that watches the book is within 0.01 of the decoded hazard. Condition 2 therefore FAILS
   against a book-aware baseline at the decision clock as well (block clock: +0.024 vs the capture-aware baseline, iteration 14).
5. THE BOOK ALSO CARRIES PART OF THE LATE-TRIGGER SIXTH (X139 alternative; sidebook15.py, results/sidebook15.json; 46,569 operator
   taker orders of 10-21..22 scored, fit 10-20; book of both outcomes at m0 - 210 ms, before the bot's arrival on the book clock):
   book-only side 0.712 per order (DS 0.721, GF 0.713, XM 0.624), right on 62.3% of the orders dc14 gets wrong (18.7% of orders);
   dc14 (frozen, per-decision anchor) 0.8135 -> dc14 + book 0.8380 (DS 0.847, GF 0.838, XM 0.754), rescuing 35.7% of dc14's errors.
   Designed and scored once, not pre-registered; target_metrics.side_accuracy is unchanged (pre-registration 5's dc14 value).
6. V8 MATH.RANDOM IS REJECTED AS THE SALT SOURCE (X149 = assumptions P2, V8 part; strong form of X99 / X105; prng15.py, v8real15.py,
   results/prng15.json). Model: V8 xorshift128+, double = (state0 >> 12) / 2^52, 64-entry cache read last-in-first-out, salt =
   round(r x Date.now()). Units: 130 copy groups of >= 4 distinct salts at one (wallet burst, token, price) signed in the same ms
   (calldata sample hours); a depth-first GF(2) search over generation offsets in [-12, 12] (and [-24, 24]), validated by exact
   prediction of the burst's other filled salts over +-3,000 outputs.
   - Solver validated: synthetic self-test 6 / 6; REAL Node v22 output (local) 3 / 3 groups solved from 5 sparse salts, 120 / 120
     held-out salts predicted exactly.
   - Operator: 0 / 40 groups consistent at Date.now() tolerance 2 ms, 0 / 20 at 50 ms, 0 / 6 at span +-24; at 1.5 s, 7 / 13
     "consistent" but 0 validated (too few known bits; false positives).
   So the salts are not V8 output of nearby calls. JavaScriptCore / Bun (xorshift128+ with the SUM output, not GF(2)-linear) is
   untested: it needs a SAT / SMT solver, which the shared venv does not have (z3, pysat, ortools absent; nothing installed). X149
   stays open for the JSC variant.
7. A SHARPER ALLOCATION MODEL RAISES THE XM CEILING TO 0.46, STILL BELOW 0.47 (X140 = information P2 steps 3-4, X148 step 4; xmclock15.py,
   xmknee15.py, thin15.py; results/xmclock15.json, xmknee15.json, thin15.json):
   - per-leader knee profiles (first legs, fit days; agreement of the 250-ms spot microprice return ending c ms before m0): DS 0.599 /
     0.657 / 0.741 / 0.829 / 0.837 at c = 400 / 320 / 280 / 260 / 220 (sharp knee at 260); GF 0.633 / 0.720 / 0.790 / 0.825 / 0.834
     (rises 20-50 ms earlier); XM 0.625 / 0.695 / 0.740 / 0.765 / 0.785 (broad, no sharp knee, lower plateau);
   - XM-vs-rest among first legs with pre-horizon clock features (k400..k260, decision-anchor returns; fit 10-17..19, scored 10-20..22):
     AUC 0.805 vs 0.716 without them (DS 0.675, GF 0.623); top inputs k340 / k350 / k360;
   - thin15 (thin14 with these features; all taker orders): XM one-vs-rest AUC 0.791 (thin14 0.670); oracle XM total PnL r 0.4426
     (halves 0.455 / 0.433; thin14 0.3925); redraw test-retest 0.2146 -> ceiling 0.4633 (thin14 0.4304); base rates 0.3145.
   The ceiling is model-relative, as the assumptions panel said: 0.31 (base rates) -> 0.43 (AUC 0.67) -> 0.46 (AUC 0.79). Caveat: the
   clock features are anchored on the realized first-leg match, so they partly encode XM's later arrival (its slower or jittered
   path) rather than a decision-time input; even so the oracle (true decisions, sides, sizes, PnL) stays below 0.47.
8. CONDITION 7, PRICE PART: THE ITERATION-13 PER-WALLET ANCHOR HOLDS OUT OF SAMPLE (X147 compact; payup15.py, results/payup15.json;
   calldata taker orders, limit vs o's best ask at m - 180 from the capture L2): anchor ask + (DS 0, GF 1, XM 1) c within one tick on
   10-21 / 10-22: DS 0.947 / 0.947, GF 0.937 / 0.948, XM 0.820 / 0.795 (n 100 / 73); pooled 0.937. The plain ask gives XM 0.640 / 0.712.
   A "modal k on 10-20" freeze (written into the script before scoring) picked c_XM = 0 from 43 orders and fails (0.671): the +1 c
   anchor is the iteration-13 hypothesis, not a refit.
9. BOTH CHANNELS DRIVE THE TAKE, WITH EQUAL MARGINAL POWER (hazbook15_2x2.py, results/hazbook15_2x2.json; score days 10-21..22, weighted
   take rate per 50-ms bin by the top weighted decile of the book-only score and of the frozen spot-only hazard): both top 6.16%,
   spot only 1.48%, book only 1.90%, neither 0.21% (base 0.0062 overall). Where the Polymarket makers pull o's asks without a Binance
   L1 move the operator still takes 9x more often than baseline. Either the bot reads the Polymarket book itself (the makers' cancel
   wave as trigger or confirmation) or both react to a common faster input (Binance L2 / other venues: X139, X141). Separating them
   needs the order of events at ms on one clock (the bot's read of the book vs of Binance): next iteration.
10. THE OPERATOR TRADES INTO THE MAKERS' CANCELLATION WAVE (wave15.py, results/wave15.json; 59,630 first legs of 10-20..22; capture L2 grid,
    server clock): o's ask depth at best .. best + 4 c relative to m0 - 1500 ms is 1.00 at 800-1500 ms before m0, 0.968 at 500, 0.920 at 300,
    0.852 at 200, 0.607 at 100, 0.520 at m0 (the last step includes the operator's own match, ~25 ms before m on the book clock); at the
    placebo anchor m0 - 5 s it stays 1.00-1.01. A >= 30% drop over 100 ms ends at m0 - 100 for 39.9% of first legs (placebo 6.8%), at
    m0 - 200 for 13.6%, at m0 - 500 for 9.9%. The other outcome's ask depth RISES (1.075 at 200 ms, 1.16 at 100 ms) and o's best ask
    rises 0.19 c by m0 - 250 and 0.59 c by m0: the makers re-quote toward o. The wave starts ~0.5 s before the match (the move builds),
    and its steep part (m0 - 200 .. m0 - 100) coincides with the arrival of the knee-band Binance move in London; the operator's
    order arrives (~m0 - 175 on the book clock) inside it and is filled by the asks the slower makers have not pulled when its
    150-ms hold ends.
11. FINDING 4 BY DAY AND BY BOOK STATE (hazbook15_splits.py, results/hazbook15_splits.json): full / PMB / full + book on 10-21 0.894 /
    0.877 / 0.915, on 10-22 0.870 / 0.8705 / 0.898. 98% of the takes fall in the book-ACTIVE half of the bins (book-only score above its
    weighted median: 35,894 positives vs 672): there the decoded hazard is 0.789, the book-aware baseline 0.761 and full + book 0.821
    (+0.060 over the baseline, but on a subset chosen by the baseline's own score, which no exam unit allows).

Live-lab correction: rec_bn15 v1 (06:00-06:57 UTC) wrote the receive time 't' in MICROSECONDS, which tools/live.py iter_live cannot
filter (it compares 't' with ms), so feeds btc5m_bnspot / btc5m_bnusdm are not usable through iter_live. v1 was stopped (taskkill, my
own pid 9312) and v2 restarted at 06:56 UTC (pid 29736, same hard stop 12:00) on feeds btc5m_bnspot2 / btc5m_bnusdm2 with t = receive ms
and tu = receive us; verified through iter_live (spot quotes, spot trades, USD-M quotes). Two facts for the out-of-time check: the
laptop clock runs ~0.65 s BEHIND Binance (spot trade E - receive t = +652 ms on the first record), so the offset must be calibrated
from the trade stamps; and the USD-M @aggTrade stream delivers no messages on this endpoint (0 records in v1 and v2), so USD-M trades
are missing from this recording.

Panel proposals of iteration 14 (catalog X139-X150) and what happened to them:
- X139 (Binance L2 for the late-trigger sixth): not run; the Polymarket book carries part of it instead (finding 5). Open.
- X140 (per-wallet clocks): tried (finding 7). X141 (full-day USD-M / venue L2 at physical cuts): not run, open.
- X142 (full-rate recorder): rec_bn15 recording 11-01 06-12; the out-of-time scoring and the Tardis 11-02 check are open.
- X143 = X144 (filled size = visible depth): tried and rejected (findings 1-3); the 'if false' branch is measured (finding 2).
- X145 (fill-simulating replica): its step-1 input measured (fill r 0.29 from public data); the simulator is open.
- X146 (condition 2 at the decision clock): step 2 tried (finding 4: the book-aware baseline closes the gap); step 1 open.
- X147 (per-wallet pay-up): tried (finding 8). X148 (attainability): step 4 in one point (finding 7); steps 1-3 open.
- X149 (PRNG): V8 rejected (finding 6); JSC / Bun open. X150 (pseudo-lot run of the examiner's procedure): not run, open.
Also closed this iteration: X99 and X105 (V8 forms, finding 6), X132 (L2 part, findings 1-2), X114 (size-only level events, finding 4).

## Next (iteration 16)

1. Condition 2 is now the binding question, and it is a question of the BASELINE'S CUT, not of decoding (findings 4, 11, 12): with
   the Polymarket book ending at e + 50 ms a market-only baseline is within 0.01 AUC of the decoded hazard; with it ending at e,
   before the bot's own Polymarket view for every label of the band, the hazard gains +0.058 [0.050, 0.065]. Steps: (a) re-ingest
   the capture's book on a 10-ms grid (l2ingest15.py with a finer GRID_MS for the bins only) and fix the cut from physics BEFORE
   scoring: book <= e, prints <= e + 25 (the bot's view is arrival - 30 ms on the trade clock, book events are stamped ~25 ms before
   the trades of a match); (b) pre-register the decision-clock presence unit with a fill-covering label (X146 step 1: the fully lost
   races from their on-chain structs), the fit set (10-17..19 or 10-20, declared), the examiner-style baseline (trades + book, same
   model class) and the 2-h CI; (c) score once on days not yet used for the book (10-17..19 need the L2 ingest, ~12 min per day).
   If the operator reads the Polymarket book itself (finding 9), that is a decoded input; the cut decides whether it can be shown.
2. Out-of-time check of the frozen routes on rec_bn15 v2 (feeds btc5m_bnspot2 / btc5m_bnusdm2 from 06:56 UTC 11-01; v1 files are not
   iter_live-compatible; USD-M aggTrade delivered nothing): operator fills from the chain for the block, server-ms matches from the shared recorder's clob_crypto 'x'
   records (tx hashes), the laptop transit offset from the trade E / T stamps, then dc_exam14 (side) and dc_hazard14 (take) scored
   once. The spot bookTicker rate seen live was 25-55/s (the capture had ~140/s on 10-20): compare rates before scoring.
3. Condition 5: the realized fill is the makers' cancel race inside the hold (finding 2). A replica can only use its expectation
   at the decision (r 0.29). Two untested ways to get closer: (a) the cancel race as a function of the makers present (the depth's
   AGE and the identity / size pattern of the resting levels at the bot's view: stale old levels survive, fresh ones are pulled);
   (b) the operator's own lost-race remainders (X133) resting at L after a depth-bound fill. Then the M stream.
4. X149 JSC / Bun: a SAT / SMT solve of xorshift128+ with the SUM output on 4-6 same-ms copies per group (z3 is not in the shared
   venv; ask before installing anything, or write a small bit-level guess-and-check over the carry into bit 15).
5. X146 step 1 (label the fully lost races from their on-chain structs), X148 steps 1-3 (fan-out-merged split-half, decoded-process
   simulator), X150 (pseudo-lot run of evaluate()), X139 / X141 (Binance L2 and the full-day USD-M book at the corrected clock).
6. Still open from earlier: X5, X7, X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X66, X70, X72, X76, X87, X88, X90, X93, X100, X104,
   X107, X113, X115, X122, X123, X124, X127, X128, X130, X133.

Recorders at the end of iteration 15: the shared recorder runs (pid 27184); rec_bn15 (pid 9312, my own, hard stop 11-01 12:00 UTC,
~6.5 MB after 33 min) records btc5m_bnspot / btc5m_bnusdm; rec_eu11 (pid 14192) is alive. No polyrea bug found. Cache:
.cache/re/btc5m-bot gained only a state backup (state_backup_iter14.json); the L2 reductions (~460 MB) live in the session scratchpad
it15/ (rebuild with code/l2ingest15.py, ~12 min per day, 2 threads).

Status after iteration 15: target not reached; target_metrics unchanged (presence 0.8701 vs 0.8464 at the block clock; side 0.8369;
price 0.9512; PnL 0.5065 / 0.4674; coverage 1 / 1). What changed is the account of the failing conditions:
- condition 2 fails against a book-aware market baseline at the decision clock too (+0.008), because the makers' cancellations show
  the operator's trigger in the Polymarket book;
- condition 5 is bounded by the makers' cancel race inside the 150-ms hold (realized fills r 0.29 from public data at the decision);
- condition 7: XM's PnL ceiling 0.43-0.46 < 0.47 under thinning; the price part holds per wallet with the iteration-13 anchor.

12. THE BOOK'S MATCH TO THE OPERATOR SITS IN THE LAST 50 MS BEFORE ITS OWN VIEW: THE PRESENCE MARGIN DEPENDS ON THE BOOK CUT (hazbook15_shift.py,
    results/hazbook15_shift{25,50,100,200}.json; same bins / split / models as finding 4, book features sampled at t = e + 50 - shift on
    the 50-ms grid; the frozen full hazard and the trades-only score unchanged): book cut at e + 50: baseline PMB 0.873 (gain of the
    decoded hazard +0.008); at e (shift 25 and 50 fall on the same grid point): PMB 0.823, book only 0.818, gain +0.0579 [0.0501,
    0.0646], full + book 0.894 (+0.071 over PMB); at e - 50: PMB 0.799 (+0.082); at e - 150: 0.780 (+0.101). The makers' cancels that
    mirror the operator's decision arrive within ~50 ms of the bot's own Polymarket view: a co-reaction to the same Binance move, not
    a lead the bot could have followed. Physics of the cut: the bot's Polymarket view is its arrival - 30 ms (price evidence, trade
    clock) = m0 - 180, i.e. [e + 25, e + 75) on the trade clock and [e, e + 50) on the book clock (book events are stamped ~25 ms
    before the trades of the same match) for the label band m0 in [e + 205, e + 255). A market-only baseline that is point-in-time
    for every label in the band must end its book at e and its prints at e + 25; under that cut the decoded hazard clears the 0.05
    bar (+0.058, CI lower bound 0.050); under the iteration-14 convention (everything Polymarket at e + 50) it does not (+0.008).
    Next: pre-register the cut from this physics, ingest a 10-ms book grid (the 50-ms grid cannot resolve e + 25), and re-score.

PRE-REGISTRATION 9 (written 06:59 UTC 11-01, before it is run): reverse-split replication of finding 12's cut. Same bins, features and
models as hazbook15 / hazbook15_shift, but FIT on 10-21..22 and SCORE once on 10-20 (whose labels were only used for fitting so far),
book cut at e (shift 50 on the 50-ms grid), prints as in the frozen trades-only score. Claim tested: the frozen full hazard's weighted
AUC exceeds the book-aware baseline PMB by >= 0.05 with a 2-h block CI lower bound > 0. Reported whatever the result, with the e + 50
cut alongside.
13. PRE-REGISTRATION 9 MET: THE CUT RESULT REPLICATES IN THE REVERSE SPLIT (hazbook15_shift_rev.py, results/hazbook15_rev_shift{50,0}.json;
    fit 10-21..22, scored once on 10-20): book cut at e: frozen full hazard 0.9018 vs book-aware baseline PMB 0.8213, gain +0.0805
    [0.0752, 0.0861] (book only 0.8181; full + book 0.9122); book cut at e + 50: PMB 0.8787, gain +0.0231 [0.0198, 0.0262]. On both
    splits the decoded decision-clock hazard clears the 0.05 bar against a book-aware market baseline that ends before the bot's own
    Polymarket view (+0.058 and +0.081) and fails it when the baseline may look 25-50 ms past that view (+0.008 and +0.023). Scope
    caveats unchanged: taker first legs (77.9% of fills with their remainders), not the pre-registered presence unit of target_metrics.
14. PER WALLET THE CUT-AT-e GAIN HOLDS FOR DS AND GF, NOT FOR XM (hazbook15_shift_wallet.py, results/hazbook15_wallet_shift{50,0}.json;
    10-21..22; positives = first legs the wallet carried, against all negatives): book cut at e: DS full 0.8734 vs PMB 0.8147 (+0.059),
    GF 0.8958 vs 0.8347 (+0.061), XM 0.9121 vs 0.8822 (+0.030; full + book 0.9164, +0.034); cut at e + 50: DS +0.005, GF +0.014, XM
    +0.013. Condition 7 for the presence part therefore fails for XM even under the PIT cut: the book anticipates XM's decisions better
    than the others' (XM's broad, earlier clock, finding 7, gives the makers time to react before XM's view).

Next-step addendum (after findings 12-14): wire the per-wallet price anchor (DS 0, GF 1, XM 1 c; finding 8) into evaluate() as a
reported price component before the next exam, and carry XM's presence part (+0.030 at the e cut) into the condition-7 account.
Iteration 15 ended about 07:06 UTC 11-01 (about 77 minutes of work). rec_bn15 v2 (pid 29736) keeps recording until 12:00 UTC.

### Iteration 16 (2026-11-01 07:39 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18, 11-01 06-12)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 07:39 UTC): released lots
none; future examined until 10-31 00:00; the current block 11-01 06-12 is development. Shared recorder running (live.py status: clob_crypto /
clob_wallets / rtds / sports connected). Panel after iteration 15 (panels/iter15_*.md): 13 proposals, added as X151-X163:
information P1-P5 = X151-X155, mechanics P1-P4 = X156-X159, assumptions P1-P4 = X160-X163. Overlaps: X152 (large-size input) and X157
(complete decision record, original-size decision) share one label set and one model ladder; X159 (zero-fill slot record) and X160
(priority dispatcher with hidden occupancy) are the same dispatcher test; X161 is X160's payoff.

PIVOT (required: < 0.01 on the primary metric over iterations 14-15). New target, unit and model class: the operator's ORIGINAL-SIZE
decision per taker order (the large class, ~12% of orders, carries the window net: its part of N correlates 0.775 with N, the small
part -0.002; information panel) on the COMPLETE decision record (calldata of every operator taker tx of 10-20..22, never fetched before:
~72.6k txs, code/cdfull16.py, running in the background), and the carrying wallet as a deterministic PRIORITY-SLOT STATE MACHINE over
the operator's own in-flight orders (D2 state machine) instead of a thinning lottery.

Competing explanations (iteration 16; what separates them):
- E1 PRIORITY-SLOT DISPATCHER: one decision stream; each decision goes to the first free wallet in DS > GF > XM; a wallet is busy while
  its last order is in the hold, filled or not (unfilled lost races are hidden occupancy). XM is the overflow slot. Separates: a
  deterministic priority rule on own in-flight orders names the carrier far above the fills-only 72%; XM-led first legs are locked
  to a LATER tick of the same move as sharply as DS's.
- E2 SLOW XM PATH: XM is a slower or jittered path that receives random decisions. Separates: XM's tick-lock distribution shifted by
  a constant or broadened; no occupancy excess.
- E3 SIZE = PER-WALLET COIN: P(large) is a per-wallet constant (DS ~5%, GF ~30%, XM ~32%). Separates: within wallet no input lifts
  the AUC for large above ~0.6.
- E4 SIZE = CONVICTION (public): large when the move or the edge (fair value from Binance minus the ask) is large, or when the
  Polymarket book shows a deep book being pulled. Separates: within-wallet AUC >= 0.75 from public inputs at the physical cut.
- E5 SIZE = OWN-STATE CONTROLLER: large when the operator's realized exposure lags its signal (pyramiding / deficit). Separates:
  own-state inputs lift the within-wallet AUC well above the public ones.
- E6 SIZE = BURST POSITION (size follows the dispatcher): the large order is a later decision of a burst (DS busy), which the
  priority list sends to GF / XM. Separates: P(large) rises with the number of operator orders in flight and the leg rank within
  wallet, and large DS orders are also follow-ups.
- E7 POST-HOLD EXECUTION: given the original size the fill is min(size, depth left ~35 ms before the match) (mechanics panel, r 0.876),
  so condition 5 is a decision-replica problem. Separates: the ladder with the MODELLED size reaches r(N) >= 0.6 on the true decisions.
This iteration discriminates E3-E6 on the complete record (and its on-chain proxy for 10-19..22), E1 vs E2 on the routing record, and
bounds E7 with the modelled size.

Data added (iteration 16): the COMPLETE decision record of the capture days: V2 matchOrders calldata of every operator taker tx of
10-20..22 (code/cdfull16.py; 72,602 txs fetched with batched eth_getTransactionByHash at ~35 tx/s: 10-20 26,780 in 773 s, 10-21 20,715
in 567 s, 10-22 25,107; plus 3,741 already decoded), decoded fields only, in the session scratchpad it16/cdfull_*.parquet (the strategy
cache is at its 1.5 GB cap). Every operator taker order of 10-20..22 now has its original size, limit and signing ms (before: 5%). The
VALIDATE taker tapes were rebuilt from the HTTP cache into it16/tapes (2,016 windows, 2.9 M rows, 113 s).

Findings (iteration 16):
1. DISPATCH: A FIXED PRIORITY LIST DS > GF > XM WITH A 300-MS SLOT NAMES 73-82% OF CARRIERS ON VISIBLE OCCUPANCY ALONE, STABLE BY DAY
   (X160 step 3 / X159 / X162 step 1 on the capture days; disp16.py, results/disp16.json, disp16_days.json; 117,791 taker orders of
   10-17..22; a wallet is busy if it has a match in (m - H, m)): best rule H = 300 ms, order DS > GF > XM: 0.778 pooled (H 250 0.772,
   200 0.751, 150 0.734, 100 0.722; every other order is lower), always-DS 0.639; by day 0.797 / 0.782 / 0.802 / 0.823 / 0.742 / 0.731
   (always-DS 0.65-0.67, 0.61 on 10-21 / 22). P(GF | DS busy) 0.88-0.94 on every day; P(XM | nobody visibly busy) 0.03-0.06; P(GF |
   nobody busy) 0.15-0.18 on 10-17..20 and 0.23-0.25 on 10-21..22 (the known dispatch phase 10-21 16 h -> 10-22 13 h). Events: 78.5%
   single-leg, 17.4% two legs, 4% three or more (sequences DS 57%, GF 18%, DS>GF 13%, XM 3%). A slot that frees ~150 ms after the match
   (300 ms after the arrival) fits best: the bot frees a wallet when the match is acknowledged, not when the hold ends.
2. TICK LOCK BY CARRIER: GF- AND XM-LED FIRST LEGS ARE SHIFTED BY THE FAN-OUT GAPS (X160 step 1; X154 step 1 for spot; disp16.py; first
   legs of 10-20..22 (DS 42,649, GF 12,447, XM 2,534); signed Binance spot microprice ticks toward o per leg per 10-ms bin of m0 - Te,
   Te = capture receive - 131 ms, placebo m0 - 3 s subtracted): peak DS 265 ms (half-maximum 175-305), GF 285 (205-355), XM 305 (215-425);
   per 50-ms bin DS 3.41 / 4.68 / 2.04 at 200 / 250 / 300 ms, XM 3.96 / 6.00 / 7.06 / 5.00 / 4.19 at 200..400 ms, with XM's pre-trigger
   level ~2 per bin out to 800 ms (DS ~0.1-0.2). The shifts (+20 ms GF, +40 ms XM) equal the fan-out positions (DS -> GF 16 ms, GF -> XM
   26 ms, information panel), while XM in a VISIBLE DS -> XM fan-out comes only 25 ms after DS: a constant slow XM path (E2) would put
   XM >= 40 ms behind DS in every fan-out. Reading: a GF- or XM-led 'first leg' is the second or third slot of a fan-out whose earlier
   legs lost their races unseen (E1), on long moves (XM's high pre-trigger level). Not yet proven: the hidden-occupancy census (the
   lost legs' bid insertions in the event-level L2) is not run.
3. THE BOT'S POLYMARKET VIEW, PER WALLET, FROM THE COMPLETE 10-20 CALLDATA (X151 step 1, 16 offsets only; view16.py, results/view16.json;
   27,008 orders, 12,818 whose o-ask changed between m - 500 and m - 125): DS's limit equals o's ask at m - 180 .. m - 35 for 81.4-83.8%,
   at m - 250 65.5%, at m - 500 3.8%: DS's view lies in (m - 250, m - 180] on the book clock. GF at +0 c rises monotonically to 0.769
   at m - 35 while GF at +1 c peaks at m - 250 (0.484): either a later view or a +1 c pay-up on an earlier one (16 offsets cannot tell).
   XM spreads over +0 / +1 / +2 c (0.60 at m - 35 for +0; 0.31 at m - 180 for +1; 0.21 at m - 250 for +2). Orders were pre-signed 13-120 s
   before the match (median 65-68 s, every wallet).
4. SIGNING THROUGHPUT IS FLAT IN THE NUMBER OF ORDERS PER CENT (X163 step 1; calldata sample + complete 10-20; 39,261 operator BUY orders):
   ms per cent 1.62-1.71 on every day whatever the menu (10-16 with 30 / 50 / 200: 1.667; the one-size days 10-17 / 18: 1.639 / 1.660;
   two-size days 1.62-1.71); per burst, Spearman of ms per cent with filled orders per cent 0.037 (p 0.065); same-ms groups of one
   (wallet, token) hold up to 8 distinct salts, 92% of them one size, 0.8% span two cents. The per-cent time is not single-thread signing
   work (parallel signers, or a timestamp scheduled per cent): the assumptions panel's regrouping by signer is the right next step for
   X149 / X163 (step 2 open).
5. UNSEEN HIGHER-PRIORITY LEGS PRECEDE GF-LED FIRST LEGS (X160 step 2 / X159, a fills-based proxy of the census; hidden16.py, results/
   hidden16_10-20.json, hidden16_10-21.json; first legs with complete calldata limits; maker-FIRST operator order hashes = maker fills
   only, no taker fill): a DS maker-first hash at exactly L_GF - 1 c (where a DS leg priced on the same view rests: DS pays +0, GF +1)
   whose first maker fill lands in [m0 - 1, m0 + 4] s follows 9.48% / 8.83% / 8.54% of GF-led first legs on 10-20 / 21 / 22 (n 3,354 / 3,896 / 5,197),
   against 1.2-2.4% at the neighbouring cents (L - 0, L - 2), 0.24-0.28% in the placebo 30 s earlier, and 1.7-2.0% for the symmetric
   check on DS-led legs (GF at L_DS - 1). XM-led first legs: GF at L_XM - 2 5.1% (10-21), DS at L - 1 2.0-2.5%. Only remainders that rest
   AND are hit within seconds are visible (lost legs rest below a market that just moved away), so >= 9% is a lower bound on the GF-led
   first legs that follow a lost DS leg. Together with findings 1-2 this supports the priority-slot dispatcher with hidden occupancy
   (E1) over a slow XM path (E2). The book-insertion census (all lost legs, filled or not) is still open.
6. THE REALIZED FILL IS EXECUTION ON THE POST-HOLD BOOK, ON THE COMPLETE RECORD (X156 step 1; posthold16.py, results/posthold16.json; all
   27,008 operator taker orders of 10-20 with their original size and limit): fill = min(original, o's ask depth <= L at m - 35 on the
   book clock) at r 0.895 (85.4% within 10%; DS 0.883, GF 0.897, XM 0.894; large 0.876, small 0.858), 0.845 at m - 50, 0.672 at m - 100,
   0.503 at the bot's view m - 180; the original size alone 0.432; 45.0% of orders fill less than their original size. The mechanics
   panel's 0.876 on 929 orders replicates on the full population.

PRE-REGISTRATION 10 (written 08:19 UTC 11-01, before size16 with exact labels is scored and before lean16 sees 10-22; lean16 was already
run once with score day 10-21, see finding 8): (a) size16 'cd' (exact calldata labels, original size >= 90): per-wallet LightGBM ladder
of feature groups, FIT 10-20 (its 19-h size phase included as is), SCORE once on 10-21..22; a measurement, nothing adopted. (b) E5 as a
replica input: the lean controller with the rule's OWN simulated state (lean16 'lean_sim') counts as a usable size input only if, with
the dc14 side on the true decision record of 10-21..22, it beats the public menu by >= 0.05 in window-net r. (c) The reverse split
(fit 10-21..22, score 10-20) is reported alongside.
7. PRICE AND SIZE ARE ONE DECISION: LARGE ORDERS PAY ABOVE THE ASK, SMALL ONES AT IT (complete 10-20 calldata, outside the 19-h size
   phase; L - o's best ask at m - 180 on the book clock): DS small 0 c in 94.3% (+1 c 3.2%), DS large +1 c 60.4%, +2..3 c 20.7%, 0 c 17.6%;
   GF small 0 c 65.5% / +1 c 28.3%, GF large +1 c 83.7% / 0 c 8.3%; XM small 0 c 48% / +1 24% / +2..3 26%, XM large +1 40% / +2..3 45%.
   Large orders come in a MOVING Polymarket book: o's ask rose a(m-180) - a(m-500) = +1.10 c before DS's large orders (small -0.11), XM
   +1.27 (+0.11), GF +0.28 (+0.13); within wallet, L - a(m-500) has AUC 0.812 for DS's large class (GF 0.604, XM 0.614), the depth <= L
   at m - 500 0.694 / 0.639 / 0.644. So the iteration-13 per-wallet pay-up anchor (DS 0, GF 1, XM 1 c) is mostly the per-wallet LARGE
   share: the limit is ask + 0 for a small order and ask + 1 (or more) for a large one, priced ahead of a move already under way.
   Exact large shares outside size phases (10-20): DS 3.8%, GF 32.3%, XM 34.4%; not a pre-signed-stock effect (P(large) by the use index
   of the (wallet, burst, token, cent) cell DS 3.8 / 3.2 / 2.8%, GF 32 / 26 / 25%; flat in ladder age); size phases raise every wallet
   (10-19 01-13 h: 0.3-0.5; 10-20 19 h: DS 0.71, GF 0.64, XM 0.57).
8. THE SIZE IS A LEAN-RELATIVE COIN THAT A REPLICA CANNOT SYNCHRONIZE (PRE-REGISTRATION 10 (b): E5 FAILS AS A REPLICA INPUT; lean16.py,
   results/lean16_10-21.json, lean16_10-21_10-22.json, lean16_10-20.json; complete calldata labels; fit 10-20 -> score 10-21..22, and
   the reverse):
   - P(large | wallet, the order's side vs the operator's realized LARGE net so far in the window) on 10-20: DS none / with / against
     0.038 / 0.057 / 0.018, GF 0.478 / 0.506 / 0.131, XM 0.552 / 0.590 / 0.152 (two streams at the order level: GF / XM send large about
     half the time unless the order goes against the realized large lean, which is the small pairing flow); same wallet and window,
     after a large order on the same side P(large) GF 0.589 / XM 0.618 / DS 0.132, on the other side 0.126 / 0.157 / 0.015;
   - multi-leg events carry the large legs: mean number of large legs per event (on-chain proxy label, total fill > 30) 0.047 (one leg),
     0.274 (two), 0.380 (three), 0.532 (four legs); 78.5% of events have one leg;
   - ladder on the TRUE decision record (timing and carrier known), dc14 side, window-net r on 10-21..22 (494 windows): public menu 0.356,
     per-wallet constant 0.351, lean controller on the rule's OWN simulated state 0.314 (AUC for the large class 0.52-0.54), the same
     controller on the operator's TRUE realized state 0.521 (AUC 0.59-0.64), class oracle 0.619, true fill 0.707; reverse split (score
     10-20, 265 windows): 0.480 / 0.475 / 0.456 / 0.633 / 0.739 / 0.816. With the true side the class oracle reaches 0.801 (menu 0.330).
   The size realizations carry +0.26 of window-net r with the dc14 side (+0.47 with the true side). A rule's own simulated lean has no
   information on them; only the operator's realized large orders do (own state the replica does not share). This is the quantitative
   account of condition 5's gap: the binding term is the per-order size coin, conditioned on the operator's own realized lean.
9. PRE-REGISTRATION 10 (a): THE ORIGINAL-SIZE CLASS ON THE COMPLETE RECORD: PUBLIC FOR DS, MOSTLY OWN STATE FOR GF / XM (X152, X157 steps
   2-3; size16.py 'cd', results/size16_cd.json; fit 10-20 (27,008 orders), scored once on 10-21..22 (46,569 orders, 6,118 large); within-
   wallet AUC for original size >= 90): groups G0 config (arm, window index mod 4, time in window, hour, price), G1 Binance spot at the
   decision AND the leg's own anchor, G2 USD-M / ETH / OKX / Bybit, G3 Polymarket trades, G6 digital fair value, edge and the delta-scaled
   predicted move, G4 / G4o the capture's book at m0 - 230 / m - 230 (book clock) and its 100-1000-ms changes, G5a own inventory (operator
   net and realized LARGE net toward o, fills <= m - 2 s), G5 adds leg rank and own in-flight orders (fill-count-like, reported only):
   - DS (1,344 large): G0 0.572, +spot 0.761, all public w/o book 0.766, + book 0.796, + own-anchor book 0.801, + G5a 0.842 (G6 alone 0.714;
     top inputs o's ask depth to best + 4 c at m - 230, the 250-ms spot microprice return at the leg's own anchor, the 250-ms ask change,
     USD-M 250 ms);
   - GF (3,728): public 0.661, + book 0.660-0.667, G5a alone 0.714, public + G5a 0.775, public + G5 0.830;
   - XM (1,046): public 0.624, + book 0.637, G5a alone 0.776, public + G5a 0.810, public + G5 0.811;
   - pooled: public + book 0.817 (mostly wallet identity), + G5a 0.868.
   The information panel's signature (within-wallet public AUC >= 0.75) holds for DS only; for GF / XM the 'if false' branch applies
   (public <= 0.67, own realized lean lifts it). Ladder with these E[size] on the true decisions, dc14 side (ladder16.py, results/
   ladder16_cd.json, 494 windows): menu 0.358, public model 0.401, public + G5a 0.578 (operator state, oracle for a replica), class
   oracle 0.685.
10. NO FEED GIVES XM A SHARP KNEE (X154 step 1 on every exact-stamped trade feed on disk; psth16.py, results/psth16.json; first legs of
    10-20..22; peak lag and half-maximum span of m0 - T): Binance USD-M trades DS 265 [195, 305], GF 285 [235, 355], XM 325 [265, 395];
    OKX swap trades 275 [185, 305] / 295 [235, 365] / 335 [205, 545]; Binance spot trades 265 [185, 295] / 275 [225, 355] / 305 [265, 695]
    (spot book ticks, finding 2: 265 / 285 / 305). XM is later and broader on every feed by about the same amount: not a different feed,
    a later slot (finding 2) on longer moves.

Panel proposals of iteration 15 (catalog X151-X163) and what happened to them:
- X151 (per-wallet view clock and maker envelope): step 1 at 16 offsets (finding 3); the event-level steps are open.
- X152 (large-size input in public data): tried (findings 7-9): public for DS (0.80), mostly own realized lean for GF / XM.
- X153 (Binance L2, Tardis 11-01): not run, open. X154 (XM's feed): every trade feed on disk (finding 10) and spot ticks (finding 2);
  no XM-specific feed; W4 / W5 preceding legs open. X155 (kink test): open (needs X151 at event resolution).
- X156 (closed-loop replica on the post-hold book): step 1 replicated on the complete record (finding 6, r 0.895); step 2 measured
  (finding 8): the 'if false' branch applies (original size binding), so the replica is RULED OUT as a route to the signature.
- X157 (complete decision record): tried (data added; findings 7-9). X158 (latency dispersion): open (event-level book).
- X159 = X160 (priority dispatcher with hidden occupancy): visible-occupancy rule, tick lock, fills-based hidden-leg proxy (findings 1,
  2, 5); the book-insertion census is open. X161 (replica with simulated occupancy): open. X162 (dispatcher versions): capture days
  only (finding 1), open. X163 (PRNG by signer): step 1 FLAT (finding 4), step 2 open.
Also this iteration: X145 ruled out with X156 (same ceiling); X93 tried (the race is execution on the post-hold book, finding 6).

## Next (iteration 17)

1. Condition 5 is bounded by the per-order size coin conditioned on the operator's REALIZED large lean (findings 7-9): with the true
   decisions and the dc14 side the window-net r is 0.36 with the menu, 0.40 with the public size model, 0.58 with the operator's own
   realized lean (a state a replica does not share) and 0.69 with the true classes. Untested ways in: (a) a size-weighted hazard target
   (every 50-ms bin scored with a frozen P(large | public inputs at the bin, own-anchor spot and book), pre-registered against mix14 in
   the tracker; DS's public model is 0.80); (b) X163 step 2 (per-signer salt chains through the V8 GF(2) solver): if a generator is
   recovered, test whether it also draws the size and the carrier; (c) JavaScriptCore (X149) only after (b).
2. Condition 7 through the dispatcher (findings 1, 2, 5, 11, 12, 15, 16): XM is the slot after W4 and its PnL ceiling is 0.51-0.62 once
   the operator's local decision density is known, but the public hazard does not reproduce that density (0.48). Steps: (a) a model of
   the operator's decision COUNT in the next / last 300 ms (burst intensity) from public inputs (the makers' cancel wave on both
   outcomes, the knee-clock move, the hazard's own 300-ms sum), scored against the true density; (b) re-ingest the capture's 10-20
   book at event level for the complement's ask at 1 - L (a lost leg rests as a bid at L) to count the unseen legs; (c) X161's replica
   with simulated occupancy (five slots incl. W4 / W5) and per-wallet trackers; the public book's cancel wave already names XM's
   overflow legs at AUC 0.832 (finding 17), so the first pre-registered test is an XM tracker with that allocation (bins scored with it).
3. Condition 2: X151 at event resolution (5-ms view edges per wallet with the lost legs included; the makers' size-cancel envelope after
   clean onsets), then pre-register the per-wallet cut and score once on days whose book has not been used (10-17..19 need the L2 ingest).
4. Exam readiness: the out-of-time check of dc_exam14 / dc_hazard14 on rec_bn15 v2 (11-01 06:56-12:00 UTC, feeds btc5m_bnspot2 /
   btc5m_bnusdm2; laptop offset from the trade stamps); the Tardis 11-01 HEAD check on 11-02 (X153 step 4); the price component's
   size coupling (ask + 0 small, + 1 large) in FINAL_RULE.md.
5. Still open: X5, X7, X9, X18, X26, X33, X36, X37, X44, X51, X53, X57, X66, X70, X72, X76, X87, X88, X90, X100, X104, X107, X113, X115,
   X122, X123, X124, X127, X128, X130, X133, X139, X141, X142, X146, X148, X149, X150, X151, X153, X154, X155, X158, X159, X160, X161,
   X162.

Recorders at the end of iteration 16: the shared recorder runs (pid 27184); rec_bn15 v2 (pid 29736, my own, hard stop 11-01 12:00 UTC)
and rec_eu11 (pid 14192) are alive; no recorder was started this iteration. No polyrea bug found. Cache: nothing added to
.cache/re/btc5m-bot (at its 1.5 GB cap); the complete calldata (it16/cdfull_*.parquet, ~25 MB) and the rebuilt tapes (it16/tapes) live in
the session scratchpad (rebuild: code/cdfull16.py ~35 min; tapes8_run.py ~2 min).

Status after iteration 16: target not reached; target_metrics unchanged (presence 0.8701 vs 0.8464 at the block clock; side 0.8369;
price 0.9512; PnL 0.5065 / 0.4674; coverage 1 / 1). The account of the failing conditions changes:
- condition 5: the binding term is the original-size coin (large ~4% DS, ~32-34% GF / XM, priced at ask + 1), repeated on the side of
  the operator's realized large lean; given the size, the fill is execution on the post-hold book (r 0.895). A replica's own simulated
  lean carries no information on the size realizations (pre-registration 10 (b) failed: 0.314 vs 0.356);
- condition 7: the carrier follows a fixed priority list over in-flight orders (0.778 on visible occupancy), with unseen lost legs ahead
  of GF / XM-led legs (DS remainders at L_GF - 1 c for >= 9% of GF-led first legs; tick lock shifted by the slot gaps); XM's ceiling of
  0.43-0.46 assumed a lottery and is not yet re-measured under the dispatcher;
- condition 2: unchanged (cut convention at the decision clock; DS's view in (m - 250, m - 180] on the book clock).

Addendum (08:35 UTC):
11. XM'S 'FIRST LEGS' FOLLOW THE OPERATOR'S 4TH WALLET (X154 step 2: SIGNATURE MET; w45lead16.py, results/w45lead16.json; W4 0xd84403ef /
    W5 0x03b4c58b taker BUYs from the data-api tapes (10,028 with server ms from the public capture), operator first legs of 10-20..22):
    a W4 / W5 taker leg on the same window in the 300 ms before m0 precedes 36.6% of XM-led first legs (placebo 3 s earlier 4.3%) against
    2.7% of DS-led (placebo 2.9%) and 3.7% of GF-led (3.5%); the gap is a median 45 ms (q10 8, q25 15, q75 125, q90 202) and 86% are on
    the same outcome. After a W4 / W5 leg the next operator leg within 300 ms is XM 1,690 times, DS 1,517, GF 649 (none 6,172), although
    XM carries only ~6% of the three wallets' legs. XM is the slot after W4.
12. FIVE-WALLET PRIORITY LIST (disp16b.py, results/disp16b.json; 83,605 taker legs of DS / GF / XM / W4 / W5 on 10-20..22, visible
    occupancy = a match in (m - H, m)): the best of the 120 orders x 3 slot lengths is DS > GF > W4 > XM > W5 with H = 300 ms (all legs
    0.693, the three studied wallets 0.762; XM precision 0.645, recall 0.072); DS > GF > XM > W4 > W5 has XM precision 0.219 at recall 0.143.
    With W4 placed ahead of XM the rule's XM calls are right two times in three, but most XM legs still come while the visible slots are
    free (hidden occupancy: lost legs of the higher slots, finding 5).
13. PER-SIGNER PRNG CHAINS ARE NOT V8 OUTPUT EITHER (X163 step 2; prng16.py, results/prng16.json): chains = (wallet, token, signing burst,
    size) with >= 6 cents carrying one observed salt each (3,252 chains in the complete calldata of 10-20..22 plus samples); layouts M = 1-4
    Math.random calls per order, one order per cent in signing order, V8's 64-entry cache read last-in-first-out with any phase (64), the
    'hi' mantissa, Date.now() within +-2 ms of each order's timestamp; a consistent full-rank GF(2) system is a recovery. Self-test on the
    same layouts: 4 / 4 synthetic chains recovered (true M and phase found). Real: 0 / 299 chains consistent under any of the 256
    hypotheses. With prng15's copy groups (0 / 130) the salts are neither nearby nor per-signer sequential V8 outputs; JavaScriptCore /
    Bun or a CSPRNG remain (X149).
14. FINDING 9 REPLICATES IN THE REVERSE SPLIT (size16.py 'cd' fit 10-21..22 -> score 10-20, results/size16_cd_rev.json; 27,008 orders,
    3,499 large): DS public 0.805, + book 0.836, + own lean 0.861; GF public 0.680, + book 0.696, lean alone 0.739, public + lean 0.801;
    XM public 0.661, + book 0.683, lean alone 0.784, public + lean 0.831.
15. UNDER THE DISPATCHER, XM'S PNL CEILING EXCEEDS 0.47: THE THINNING WALL COMPONENT IS VOID (X161 step 2 / X154 step 3, oracle for the
    dispatch part; thin16.py, results/thin16.json; thin15 with the operator's own occupancy as allocation inputs: DS / GF / XM matches in
    (m - 300, m), operator legs in the last 300 ms, a W4 / W5 leg in the last 300 ms; fit 10-17..19, score 10-20..22; 600 redraws):
    XM one-vs-rest AUC 0.868 (clock model 0.791); oracle XM total PnL r 0.525 (halves 0.546 / 0.507) against 0.443 (clock) and 0.320
    (base rates); redraw ceiling sqrt(test-retest) 0.620 against 0.468 / 0.309; occupancy and leg rank alone: AUC 0.765, oracle 0.506,
    ceiling 0.613. 41.7% of all XM taker orders have a W4 / W5 leg in the 300 ms before them. The inputs are the operator's TRUE
    occupancy (own state of the operator and its sibling wallets), so this bounds a replica that simulates its own dispatcher (its own
    decisions, lost races and the W4 slot); it is not a public rule yet. Condition 7 for XM is attainable in principle, and the next step
    is X161's replica with simulated occupancy and per-wallet trackers.

16. ...BUT A PUBLIC REPLICA DOES NOT YET SEE THAT DENSITY (thin16.py variants, results/thin16_density.json, thin16_haz.json,
    thin16_hazbin.json; hazbins16.py stores the frozen knee-clock hazard on every 50-ms bin of 10-20..22, it16/hazbins16.npz):
    - carrier-agnostic TRUE decision density (operator legs of all five wallets in the 300 ms before the order) + the clock features,
      fit 10-17..19 -> score 10-20..22: XM AUC 0.852, oracle XM total PnL r 0.529 (halves 0.558 / 0.504), redraw ceiling 0.559; without
      leg rank 0.840 / 0.512 / 0.541;
    - fit 10-20 -> score 10-21..22: clock only 0.773 / 0.486 (halves 0.625 / 0.451) / 0.427; + the PUBLIC hazard summed over the 300 /
      600 ms before the decision band 0.788 / 0.479 / 0.457; + the hazard per second 0.772 / 0.478 / 0.444; TRUE density 0.838 / 0.556 /
      0.535.
    The public hazard does not reproduce the operator's local decision density (the take among top-hazard instants is still a coin,
    P(take) ~6% in the top decile), so XM's PnL ceiling for a public replica stays at ~0.43-0.48; with the operator's own decision times
    it is 0.51-0.56. Condition 7 for XM is bounded by the take coin, not by an i.i.d. carrier lottery.

17. THE MAKERS' CANCEL WAVE IN THE PUBLIC BOOK NAMES XM'S OVERFLOW LEGS ALMOST AS WELL AS THE TRUE DENSITY (thin16.py THIN16_BOOK,
    results/thin16_hazbin_book.json; fit 10-20 -> score 10-21..22; book features at the order's own view cut m - 230 on the book clock from
    the capture L2 grid: o's and the other outcome's depth to best + 4 c relative to 250 / 500 / 1500 ms earlier, o's best-ask change over
    500 ms): XM one-vs-rest AUC 0.832 (0.819 without leg rank) against 0.773 for the clock model and 0.838 for the TRUE decision density;
    oracle XM total PnL r 0.498 (taker 0.527; halves 0.651 / 0.461), redraw ceiling 0.491 (clock 0.424, true density 0.535); without leg
    rank 0.484 / 0.465. The drained book before XM's view (assumptions panel) is a public marker of the overflow slot; with it XM's PnL
    ceiling reaches the 0.47 bar pooled but not in the later half. Not pre-registered; next: per-wallet trackers with this allocation.

Iteration 16 ended about 08:50 UTC 11-01 (about 71 minutes). The shared recorder, rec_bn15 v2 and rec_eu11 are alive; no recorder was
started this iteration.

### Iteration 17 (2026-11-01 09:30 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18, 11-01 06-12)

Split and primary metric unchanged (BUILD = 10-09..16, VALIDATE = 10-16..23). Calendar (`sealed.py btc5m-bot`, 09:31 UTC): released lots
none; future examined until 10-31 00:00; the current block 11-01 06-12 is development. Shared recorder running (pid 27184, updated
09:31). Budget: 1046 of 1200 minutes used before this iteration. The brief changed on 11-01 (hidden dimensions and indicators): E1-E7
are added to the catalog; the `dimensions` (E1) and `indicators` ledgers are added to state.json; a "Missing dimensions" section
follows below. Panel after iteration 16 (panels/iter16_*.md): 13 proposals, added as X164-X176: information P1-P5 = X164-X168,
mechanics P1-P4 = X169-X172, assumptions P1-P4 = X173-X176. Overlaps: X164 (out-of-time decision record), X165 (XM regime change)
and X175 (configuration drift) share one new-regime decision record; X169 (decision-memory state machine) and X176 (lean's free
draws) share one replica; X173 (size-keyed routing) restates the size unit for X169.

PIVOT (required: < 0.01 on the primary metric over iterations 15-16). New DATA and new UNIT: (1) the first OUT-OF-TIME complete
decision record, in the new routing regime (11-01 06-12 development block: on-chain fills of all five operator wallets, calldata of
every operator taker tx, server-ms matches from the live lab's trade records, the full-rate Binance spot feed rec_bn15 v2), on which
the frozen exam routes are scored once; (2) the size class as a DECISION-level variable drawn before routing (assumptions panel), with
the bot's own DECISION MEMORY (side of its last large order, commitment since) as the state of a hysteresis state machine (D2 state
machine; mechanics panel), run on the replica's own sent orders.

Competing explanations (iteration 17; what separates them):
- H1 LATENCY-ARB TAKER ON A FASTER VIEW: the bot reads Binance spot top-of-book (sub-tick queue imbalance) ~100 ms after the exchange
  stamp, decides at the knee 230-260 ms before its match, and takes the Polymarket ask before the makers re-quote; profit = rebate +
  maker remainders, takers about break even. Separates: frozen dc14 side holds out of time (>= 0.80) in the new regime.
- H2 VERSION-BOUND CONFIGURATION: the side and timing transfer, but the size menu, routing lists and per-wallet roles are scheduled
  configuration (whole UTC hours, window-index arms) that changed after VALIDATE (XM ~10k fills a day on 10-31). Separates: per-wallet
  large shares and carrier tables move between regimes while the decision-level quantities (pooled large share, side) do not.
- H3 SIZE = DECISION MEMORY STATE MACHINE (mechanics panel): the large class follows the side of the bot's last large order S and the
  commitment E since; seed / early flips / width are the only coins. Separates: a replica that runs S on its OWN sent orders agrees with
  the operator's S (>= 0.75) and lifts window-net r over the menu by >= 0.05.
- H4 SIZE = PRIVATE CONVICTION COIN: the class is drawn per decision from an input the public record lacks (an internal fair value or
  a random draw), so no replica memory synchronizes with it. Separates: S_own agreement near the base rate implied by side accuracy
  alone, and no lift.
- H5 TWO-STREAM MARKET MAKER IN DISGUISE: the money is the maker remainder stream and the pair margin (assumptions panel: makers +$8
  per window, takers -$4), and the taker decisions are the cost of keeping the remainders resting where the flow arrives. Separates: in
  the new regime XM's role (maker share) changes and its PnL comes from the maker stream.
- H6 SETTLEMENT-WINDOW EDGE (unlikely): the edge is in the last-60-s TWAP lock-in, not in the knee. Separates: side accuracy and take
  rate by window minute; lock-in studies (iteration 13: B3b) showed no late-band change, kept as a control.
- H7 SHARED SIGNAL VENDOR (unlikely): the five wallets and the fast crowd subscribe to one private feed. Separates: crowd co-takes
  explained by the knee-clock design (53%, iteration 14) vs a residual fixed-lag cluster; 0xeebde7a0 another software stack (panel).
This iteration discriminates H1 vs H2 on the out-of-time record, H3 vs H4 on the replica, and characterizes H5 in the new regime.

PRE-REGISTRATION 11 (written 09:37 UTC 11-01, before any score of the new-regime record): OUT-OF-TIME SCORE OF THE FROZEN SIDE ROUTE on
the 11-01 06:00-09:30 development windows (code/oot17.py). Orders: operator taker BUY orders of DS / GF / XM (one per (tx, wallet,
token)), match ms m = the minimum server ms 's' of the live lab's trade records ('x', clob_crypto or btc5m_clob_raw2) with the order's
tx hash. Binance: rec_bn15 v2 feed btc5m_bnspot2 (every bookTicker and trade message, laptop receive clock). Clock substitution
(physics, fixed now): the capture's book cut X + 131 ms (its median spot-trade transit) becomes X + tau_lap, tau_lap = the median of
(receive ms - T) of the block's trade messages, implemented by shifting the book receive times by (131 - tau_lap); trades by T.
Model, features, anchor C_EX_MS = 260 and the 0.5 threshold are dc_exam14's, unchanged. Reported once: accuracy per order (pooled,
per wallet), per decision (first-leg anchor), placebo m -/+ 3 s, coverage; bar 0.80 per order pooled (target condition 3); per wallet
reported. W4 / W5 orders are scored as a separate line (not in the target). Whatever the result, nothing is refitted on it.

PRE-REGISTRATION 12 (written 09:37 UTC 11-01, before smach17 runs): THE DECISION-MEMORY STATE MACHINE AS A REPLICA SIZE INPUT
(X169 steps 1, 2 and 4; X173 step 3; code/smach17.py). Record: operator taker orders of 10-20..22 (dcfit14 frame, exact calldata
classes, large = original size >= 90; 10-20's 19-h size phase kept as is). Frozen definitions: slot class from the gap g to the
previous operator taker order on the same (window, outcome): fast follower g < 150 ms, sequential 150-400 ms, first otherwise;
S = outcome of the most recent large order of any of the three wallets matched strictly before m; E = large shares sent on S since S
was last set; rel = none / with / against. Transition model: logistic regression on one-hot (slot x rel), log1p(E) x against,
window-time bins (0-30, 30-60, 60-120, 120-300 s), FIT on 10-20 with the TRUE state, two versions: decision-level (no wallet) and
per-wallet (wallet one-hots, as lean16; reported only, since the true carrier leaks the class). Replica on 10-21..22 (timing and slot
class from the true record, an oracle for those parts only): side = dc14 (p_dc14_spot_own), S_own / E_own from the replica's OWN
drawn classes on its OWN sides, 300 redraws, expected window net; the deterministic argmax version alongside. Claim tested: window-net
r with the dc14 side >= menu + 0.05 on 10-21..22 AND on the reverse split (fit 10-21..22, score 10-20), and S_own agreement with the
operator's S >= 0.75 of legs. Reported: AUC of the replica's P(large) for the large class (pooled, per wallet), the oracle-state
version (the same model with the operator's TRUE S / E), the menu and lean16's 0.356 / 0.314 for reference.

PRE-REGISTRATION 13 (written 09:53 UTC 11-01, before phase17 runs): TWO-PHASE HAZARD TARGET IN THE TRACKER (mechanics panel P3 = X171
step 2; assumptions P4 = X176 step 2 in its phase form; code/phase17.py). Target flow mix17 = 0.5 x avg + 0.5 x nfhaz2 with nfhaz2(s) =
c_e h(s) 1(s < 60) + c_l h(s) 1(s >= 60), h = the frozen knee-clock hazard imbalance of hazflow14 (it14/hazflow14.parquet, unchanged),
(c_e, c_l) = no-intercept OLS on 10-17..19 of the operator's per-second signed flow on the two phase terms (nfhaz14's fit split at the
panel's fixed 60-s boundary). Tracker trk_a unchanged; scored once on the 864 windows of 10-20..22 in the same run as mix14; ADOPTED
only if it beats mix14 on BOTH pooled Pearson and Spearman. Secondary, reported only: three phases (0-60, 60-180, 180-300 s).

Data added (iteration 17): the FIRST OUT-OF-TIME decision record, in the new regime (code/post17.py, 93 s): 30 BTC 5m windows of 11-01
06:00-09:30 UTC (development block; every window starts in it; Gamma listed 30 of the 42 starts at fetch time), on-chain V2
OrderFilled of all FIVE operator wallets (3,230 BUY fills: DS 673 T / 771 M, GF 254 / 312, XM 73 / 804, W4 136 / 193, W5 8 / 6),
calldata of every operator taker tx (1,144) and of every maker-only tx (1,864, code/mk17.py), server-ms match times from the live lab's
trade records by tx hash (1,143 of 1,144; clob_crypto and btc5m_clob_raw2), the full-rate Binance spot feed of rec_bn15 v2 (481,575
bookTicker and 157,703 trade messages, 53 book msg/s), PolyBolt (btc5m_pb) and the unthrottled CLOB channel (btc5m_clob_raw2), all
through iter_live (development blocks only); in the session scratchpad it17/ (the strategy cache is at its cap). Also read: the
cached on-chain fills of 10-31 00-06 / 12-18 (post/own_*.parquet) and the capture day files' trade rows (transit check).

Findings (iteration 17):
1. PRE-REGISTRATION 11 FAILED: THE FROZEN SIDE ROUTE IS 0.718 OUT OF TIME (oot17.py, results/oot17_side.json; 999 DS / GF / XM taker
   orders, coverage 0.999): per order 0.7177 (DS 0.712, GF 0.751, XM 0.658), per decision 0.704, placebo m -/+ 3 s 0.487 / 0.507,
   halves 0.583 / 0.836, by window minute 0.77 / 0.79 / 0.67 / 0.64 / 0.63. The cause of the halves: the LAPTOP's receive clock drifts
   against Binance T from -637 ms (06:30) to -1161 ms (09:30), so one block-median offset misplaces the book cut by up to about 250 ms
   (too early in the first half, too late, a leak direction, in the second). PRE-REGISTRATION 11b (post hoc, written after seeing 11;
   physics only: trailing 60-s median offset; oot17b.py, results/oot17b_side_localclock.json): 0.7518 (DS 0.746, GF 0.775, XM 0.726),
   halves 0.712 / 0.787, by minute 0.82 / 0.77 / 0.73 / 0.68 / 0.67, placebo 0.51 / 0.52; W4 / W5 (not in the target) 0.799. Both are
   below the 0.80 bar. Diagnostic only (not a claim, not adopted): shifting the local cut by +25 / +50 / +100 ms gives 0.804 / 0.804 /
   0.791, by -25 / -50 / -100 ms 0.676 / 0.671 / 0.653: the side information is present, but the score moves by about 5 points per
   25 ms of clock mapping. The capture's own collector clock is stable (transit17.py, results/transit17.json: hourly median spot-trade
   transit 125-140 ms, day medians 131-134 on 10-17..22), so the exam route on capture days keeps its fitted mapping within about 9 ms;
   a live route needs a local clock offset. A Sunday sample of 30 windows is small.
2. THE DECISION CLOCK DID NOT MOVE (knee17.py, results/knee17.json; 770 first legs, local clock): signed spot microprice ticks toward o
   peak at m0 - Te = 255 ms (DS 255, GF 285; XM n = 42, noisy), the 50-ms band [250, 300) carrying the most (0.244 against 0.05-0.14
   elsewhere); capture days DS 265, GF 285 (iteration 16 finding 2). Timing and the slot shift transfer to the new regime.
3. THE NEW REGIME IS A MAKER COMPONENT ON XM, NOT A NEW TAKER ROUTING (census17.py, results/census17.json; 11-01 06:00-09:30 against the
   complete calldata of 10-20..22):
   - taker order shares of DS / GF / XM 0.674 / 0.253 / 0.073 (capture 0.630 / 0.309 / 0.061); menu 30 / 100 for every wallet (W5 105 /
     210); small first legs DS 0.76 / GF 0.15 / XM 0.03 / W4 0.06 (capture DS 0.78 / GF 0.19 / XM 0.03); 1.44 legs per event (1.28);
     the visible five-wallet priority rule DS > GF > W4 > XM > W5 names 0.707 of all legs;
   - the LARGE class fell: P(large) DS 0.036 (capture 0.043), GF 0.083 (0.268), XM 0.233 (0.347), W4 0.206; pooled first-leg large share
     0.053 (0.083), n = 42 large first legs; large first legs DS 0.24 / GF 0.24 / XM 0.29 / W4 0.24 (capture DS 0.28 / GF 0.53 / XM 0.19);
   - XM's fills are 92% maker (capture 43%), 86% of its shares, and 99% of its maker fills come from maker-FIRST orders (never a taker
     fill): 60-share BUY orders (274 of XM's 337 maker orders; mkx17.py, results/mkx17.json), signed in the same pre-signed ladder
     bursts as everything else (rel -89.6 / +40.5..42 / +172 s), limits spread 0.12-0.77 (median 0.38), both outcomes (Up 0.515), 3-18
     per window in every window, first fill at rel 22-207 s (median 114), sign-to-first-fill 17-126 s (median 83), filled fraction
     median 0.23. The same 60-share maker-first orders were 21-42% of XM's maker-first orders on 10-09..13 (BUILD), about 0 on 10-14..22
     (the whole VALIDATE week and the capture days), and dominant again on 10-31 00-06 / 12-18 (XM 2,483 / 2,158 maker against 323 / 135
     taker fills).
   - Reading: the size-class RATE, the large list and XM's maker component are version parameters (configuration); the taker routing's
     small list, the menu, the knee and the price-size coupling are invariant from 10-20..22 to 11-01. Neither E3 (per-wallet size rates)
     nor the assumptions panel's invariance prediction (pooled first-leg large share stays 0.08-0.10) holds; the class rate is scheduled
     configuration. Block PnL (30 windows, before rebates, noisy): XM maker -$185 / taker +$118, DS -$241 / +$9, GF +$26 / +$158.
4. PRE-REGISTRATION 12 FAILED: A REPLICA CANNOT SYNCHRONIZE THE OPERATOR'S DECISION MEMORY (smach17.py, results/smach17_10-21_10-22.json,
   smach17_10-20.json; 73,577 orders with exact classes; fit 10-20 -> score 10-21..22 / reverse):
   - step 1 (state definitions, true side): the S-relation's AUC for the large class by wallet x slot: fast followers DS 0.842, GF 0.847,
     XM 0.880; sequential 0.70 / 0.72 / 0.81; first legs 0.69 / 0.72 / 0.80 (reverse split within 0.02);
   - replica with its OWN memory (dc14 side, 200 redraws): S_own agrees with the operator's S on 0.546 / 0.558 of legs (bar 0.75); AUC of
     its P(large) 0.693 / 0.754 pooled (DS 0.66 / 0.69, GF 0.67 / 0.71, XM 0.54 / 0.58); window-net r 0.304 vs menu 0.290 (+0.015) /
     0.478 vs 0.435 (+0.043); argmax 0.285 / 0.399; per-wallet version 0.302 / 0.469;
   - the same transition model with the operator's TRUE S / E (oracle state, dc14 side): 0.583 / 0.731, ABOVE the class oracle with the
     dc14 side (0.556 / 0.709): the operator's memory carries side information that the dc14 side lacks.
   The state machine describes the operator's size controller (H3 as a description), but its realization cannot be reproduced from a
   replica's own decisions (H4: the class selection is a private coin).
5. THE FREE DRAWS ARE WHICH DECISIONS ARE LARGE, NOT THEIR SIDE (seed17.py, results/seed17.json; 759 windows of 10-20..22): the seed (first
   large order) comes at median 9.3 s (q10 2.4, q90 37.9) and its side equals the dc14 side of the same order 0.918 (0.41 bits); every
   large order 0.878, flips 0.896; 2.0 flips per window (34% none); final S = seed 0.589; final large-net sign = seed 0.661, = final S
   0.875. A replica knows the side of a large decision as well as that of any decision; it does not know which of its decisions the
   operator made large. Class-keyed dispatch (X173 step 2; fit 10-20, scored on 10-21..22): small list DS > GF > XM, large list GF > DS >
   XM (both 300-ms slots): carrier accuracy 0.7505 against 0.7353 size-blind; large class 0.656 against 0.540, small 0.765 both; XM inside
   the large class precision 0.55, recall 0.11. Size-keyed routing is real but names only two thirds of large carriers on visible
   occupancy.
6. PRE-REGISTRATION 13 FAILED: TWO PHASES ADD NOTHING TO THE TRACKER (phase17.py, results/phase17.json; the harness reproduces mix14
   exactly): per-second OLS on 10-17..19 gives c_e 5.31 (< 60 s) and c_l 6.26 (>= 60 s) against the uniform 5.93; tracker trk_a on 864
   windows of 10-20..22: mix17 0.5064 / 0.4675 against mix14 0.5065 / 0.4674 (three phases 0.5051 / 0.4657); halves' Spearman 0.413 /
   0.514. Not adopted. The mechanics panel's two-phase effect is on the LARGE net, which a linear per-second target on the total flow
   cannot separate.
7. POLYBOLT AGAINST THE CLOB CHANNEL (X166; pbview17.py, results/pbview17.json; 1,143 orders of the new record; a_seen = L - 0 / 1 c by
   size): P(o's ask == a_seen) peaks on the CLOB channel's own server stamps at Lam = 30 ms before the arrival (0.736 all, DS 0.911), on
   the laptop-received CLOB at Lam 10 (0.658 / 0.834) and on laptop-received PolyBolt at Lam 0 (0.697 / 0.884). Among the 52 orders whose
   CLOB channel showed an ask value in [A - 120, A - 10] that PolyBolt never displayed within [A - 400, A + 100], a_seen equals such a
   CLOB-only transient in 4 (7.7%; a uniform CLOB-reader expectation 12.8%); a pure PolyBolt reader cannot produce those. Inconclusive
   at n = 52, leaning to the CLOB market channel; the server-stamp profile (0.911 at the known 30-ms view lag) fits the CLOB channel.

## Missing dimensions (E1 / E2 / E7; brief of 2026-11-01)

Dimension inventory: state.json `dimensions` (31 dimensions, every family of the brief). Earlier feed and event studies are entered
in state.json `indicators` (period 'legacy'), with this iteration's rows.

Residual of the best rule, by component (what is unexplained, its shape, the dimensions it points to):
- SIDE (dc14, 0.837 per taker order on 10-20..22; e2_17.py, results/e2_17.json; aggregates of the scored days, the fit days carry no
  stored out-of-fold prediction): misses rise through the window, 0.119 / 0.127 / 0.158 / 0.220 / 0.310 by minute 0-4, and with weak
  knee moves, 0.45 / 0.35 / 0.26 / 0.17 / 0.04 by model confidence |p - 0.5| in 0.1 bins; flat by price level (0.157-0.170) and UTC
  hour (0.127-0.197, no session pattern); first legs 0.170, followers 0.142; large orders 0.124, small 0.169; GF 0.145, DS 0.169, XM
  0.187. Misses cluster by window (variance of window miss rates 0.0044 against 0.0026 under within-day shuffles, p < 0.005). Up / Down
  track synchrony of misses within 2 s (residual_clustering, period 300 s, the only cross-'market' pair a one-market bot has): ratio
  0.95, p 1.0, none. Points to: OWN STATE late in the window (pairing buys of the complement, iteration 13 B3b: late decisions mix
  weaker tick-following and own-state pairing) and, for weak-signal decisions, a trigger input other than the spot microprice (no
  venue tested adds to it: A2 / A3 / X100 / X87).
- TIMING (the take coin): the knee-clock hazard reaches 0.889 at the decision clock, but among the top-decile instants the take is a
  coin (P(take) about 6%), and the public hazard does not reproduce the operator's local decision density (thin16). Lead: none; the
  operator acts 230-260 ms after the Binance spot move on every feed recorded (psth16, knee17), never before. Who else: W4 / W5 (the
  operator's own slots), the fast crowd's co-takes (explained 53% by the knee-clock design), 0xeebde7a0 (another software stack).
  Points to: the operator's own in-flight state (dispatcher occupancy, lost legs) and a private coin.
- SIZE (the binding term of condition 5): which decisions are large. Their side is public (0.878, seed 0.918); the class rate is
  configuration that changes by hour and regime (10-19 01-13 h, 10-20 19 h, the 11-01 regime with GF 0.08); within a regime the
  operator's own decision memory S / E names the class at AUC 0.75-0.79 (true state) and a replica's own memory at 0.69-0.75. Points to:
  OWN STATE (decision memory) and the OPERATOR's configuration schedule; the remaining coin carries no public information found.
- SELECTION: none (every window; outages are bot-side, A8).
- XM IN THE NEW REGIME: a resting 60-share maker component the frozen rule does not model (finding 3); points to a quote-placement
  input (posting time and price relative to the book) still undecoded (new X177).
Information dimensions (news, social, calendars; E5) have no plausible path into decisions that follow a 255-ms Binance knee in every
window; their only possible role is the configuration schedule (size phases and XM's maker component switch on whole UTC hours or
days), which E5 should screen against announcements and scheduled releases (open).

Update (iteration 19; details in that iteration's findings 1-5): the TIMING and SIDE residuals have a CME-calendar shape that the
pooled 'flat by UTC hour' reading above hid. When CME Globex is closed (weekend, Mon-Thu 21-22 UTC under CDT) the operator's knee
saturates at 260 ms on Binance; when Globex is open about 12-16% of its first legs are triggered before every 24/7 venue on disk
moves (pre-reaction same-side mass E 0.96 vs 0.39; break hour 0.21 vs 0.73-0.78; reaction to Binance unchanged at 260 ms). New
dimension `tradfi_globex_feed` (missing, paid: CME BTC / MBT or ES / NQ at ms); the DST natural experiment is pre-registration 20.

Findings (iteration 17, continued):
8. XM'S 60-SHARE 'MAKER' ORDERS ARE LOST RACES OF THE LATE SLOT, NOT QUOTES (X177 steps 1-2; post60_17.py, post60b_17.py, results/post60_17.json,
   post60b_17.json): every one of the 274 XM 60-share maker-first orders of 11-01 06:00-09:30 is found POSTED in the unthrottled near-touch
   channel (272) or the top-10 snapshots (2) as a +60 size change at its level. At posting its limit L is the bought outcome's best bid in
   69% (1-2 c below it 31%) and one tick below the best ask in 57% (2-3 c in 40%); posted at rel 7.6 / 75.5 / 196.7 s (q10 / median /
   q90), first filled a median 9.1 s later (q10 3.0, q90 51.9). The bought outcome's ask was EQUAL to L 100 ms before the posting in 62.8%
   (150-180 ms 54-58%) and below L in 10-20%: the order was priced at the ask of its view and arrived after the makers had pulled, the
   lost-race signature, stronger than in the DS 30-share control (known lost-race remainders: 46-47% at 100-180 ms) and GF / XM 30-share
   (43-46%). The 60-share class never takes in this block (0 of XM's 73 taker fills are 60 shares), so it is either always late
   (XM is the slot after W4) or sent post-only at the ask (a post-only order at a still-marketable ask is rejected and leaves no trace,
   so only lost races would ever be seen): the record cannot separate the two. This confirms, with the book posting and the
   ask-by-lag test, the iteration-10 live observation that XM's 60-share races on 10-31 all rested at the old ask.
9. ...AND THEY CARRY THE SAME DECISION SIDE (side60_17.py, results/side60_17.json; not pre-registered, a consistency check): the frozen
   dc_exam14 model scored at the taker-equivalent match m_eq = posting + 150 ms on the live feed (local clock): XM 60-share 0.799 (placebo
   -/+ 3 s 0.547 / 0.507; n 274), GF 30-share maker-first 0.729, DS 30-share 0.631. The new regime's XM 'maker component' is the same
   Binance-knee decision stream, routed to a late slot whose orders rest and fill on the way back.

Panel proposals of iteration 16 (catalog X164-X176) and what happened to them:
- X164 (out-of-time record, new regime): record built; side scored once (pre-registration 11, failed at 0.718; 11b local clock 0.752);
  knee unchanged; hazard / size / live-only feeds still open.
- X165 (XM regime change): tried (finding 3): the change is a configuration of the class rate and of XM's role; E3 and E6 both fail.
- X166 (PolyBolt): tried (finding 7), inconclusive, leaning to the CLOB channel.
- X167 (Binance clock audit): step 1 in part (capture collector stable to ~+-9 ms per hour); the condition-2 re-score is open.
- X168 (implied vol for the size class): tried in lite form with DVOL (finding 10): no effect; the option-trade IV variant not fetched.
- X169 (decision-memory state machine): tried, pre-registration 12 failed (finding 4).
- X170 (W4 / W5 ruling): open, needs the examiner; FINAL_RULE states the question.
- X171 (early-window side, two-phase target): tried (step 1: early side not weaker; step 2 = pre-registration 13 failed).
- X172 (fast follower as a second trigger): tried (finding 11): partly a second trigger, the sharp signature not met.
- X173 (size-keyed routing): tried (steps 1-3; finding 5 and census17): class-keyed lists real (+0.12 inside the large class), the
  invariance prediction fails out of time (the class rate is configuration).
- X174 (three-stream replica): stream (iii) tried (pre-registration 14 failed, finding 12); stream (ii) open.
- X175 (configuration drift): new-regime part done (finding 3); the hourly change-point scan is open.
- X176 (lean's free draws): tried (step 1: seed side 0.918; step 2 in phase form failed).
New: X177 (XM's 60-share resting orders): steps 1-3 done (findings 3, 8, 9); open for the post-only vs late-slot question and their
PnL. Also closed this iteration: X142 (scored), X162 (versions: new-regime part), X9 (XM role history), X76 (= X166).

## Next (iteration 18)

1. Exam readiness before anything else (the budget is nearly spent and the examiner's next lot is h1): (a) the frozen rule's
   components that are version parameters must be written as such (done in FINAL_RULE this iteration: the class rate, the large list,
   XM's role); (b) X167 / X164: a per-hour transit guard for the capture exam route, adopted only after a non-inferiority run on
   10-20..22 (the capture's own clock is stable, so the gain is insurance); (c) X150 pseudo-lot run of evaluate().
2. Condition 5: the binding term is WHICH decisions are large (finding 5); a replica's own memory does not synchronize (finding 4), no
   valuation edge picks them (finding 10), and a replica's resting remainders are adversely selected (finding 12). Remaining routes:
   X174 stream (ii) (the pair margin from a small two-sided stream at the decoded decisions), the fast follower's public part as a
   width input (finding 11: the gap-band move toward o, 54.5% vs 43.9%), and E6 (a fitted latent state over the five wallets' decisions
   matched to an external series). XM's new-regime PnL is its lost-race resting stream (finding 8): condition 7 for XM needs the
   operator's own lost legs, which a public replica only approximates.
3. The new regime on the next development blocks (11-01 18-24, 11-02 00-06 / 12-18): the out-of-time side with the local clock as
   pre-registered from the start (11b's definition), the hazard at the e cut on the live books, and XM's resting stream's PnL.
4. Still open: E3 (other dimension families with the tool), E5 (social / calendars; GDELT rate-limited), E6, X5, X7, X18, X26, X33, X36, X37, X44, X51, X53, X57, X66, X70, X72, X87, X88, X90, X100, X104, X107, X113,
   X115, X122, X123, X124, X127, X128, X130, X133, X139, X141, X146, X148, X149, X150, X151, X153, X154, X155, X158, X159, X160, X161,
   X164, X167, X170, X172, X174, X175, X177.

Recorders at the end of iteration 17: the shared recorder runs (pid 27184); rec_bn15 v2 (my own, hard stop 11-01 12:00 UTC), rec_pb10,
rec_lab6 v2, rec_exam7 / rec_exam8 launcher, rec_fam8 and rec_eu11 were not touched; no recorder was started this iteration. No polyrea
bug found. Cache: nothing added to .cache/re/btc5m-bot (at its cap); the new-regime record lives in the session scratchpad it17/
(rebuild: post17.py ~2 min, mk17.py ~1 min).

Status after iteration 17: target not reached; target_metrics unchanged (presence 0.8701 vs 0.8464 at the block clock; side 0.8369;
price 0.9512; PnL 0.5065 / 0.4674; coverage 1 / 1). Out of time (11-01, live feed) the side route reads 0.72-0.75, below the bar.

### Iteration 18 (2026-11-01 11:07 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18, 11-01 06-12)

Split and primary metric unchanged (BUILD 10-09..16, VALIDATE 10-16..23; the size / tracker work is on the capture days 10-17..22,
fit 10-17..19 or 10-20, scored on the held-out day set). Calendar (`sealed.py btc5m-bot`, 11:08 UTC): released none; future examined
until 10-31 00:00; current block 11-01 06-12 development. Shared recorder running (pid 27184, 1799 MB). Budget before this iteration:
1108 of 1200 minutes. rec_bn15 v2 stops 11-01 12:00; no recorder started or stopped this iteration.

PIVOT (required: < 0.02 progress over iterations 15-17). NEW DATA SOURCE and a different account of the SIZE component, the binding
term of condition 5. Iterations 14-17 established that side / timing / price are decoded and the one undecoded quantity that bounds
conditions 5 and 7 is WHICH decisions are large; iteration 17 (pre-registration 12) drove the size state S from the replica's OWN
drawn classes and it did not synchronize with the operator (agreement 0.546 / 0.558, bar 0.75), so the class selection looked like a
private coin (H4). This iteration tests H3' instead: the size state is held at the OPERATOR level and is leaked publicly by the
sibling wallets W4 / W5, whose large taker prints are on chain within ~2 s. Paradigm name: "operator decision-memory read from the
siblings' public large prints". Mechanics panel iter17 P1 (= X170 / X66 / X169).

Panel after iteration 17 (panels/iter17_*.md): information P1-P4 = X178-X181, mechanics P1-P4 = X182-X185, assumptions P1-P5 =
X186-X190. Added to the catalog as X items. Overlaps: information P1 (X178, capture 10-31 file) and assumptions P4 (X189) are the same
capture-file exam route and need the examiner's access ruling (X170 family), not runnable here; information P2/P3 (X179/X180) and
mechanics P2 (X183) are the live-clock restamp; mechanics P1 (X182, this iteration) and assumptions P1 (X186, two-stream tracker)
share the size/PnL target.

Competing explanations (iteration 18; what separates them):
- H1 PRIVATE SIZE COIN (iter17 H4): which decisions are large is drawn from an input the public record lacks. Dimension: own state
  (missing / inferable). Separates: NO public state, siblings included, synchronizes with the operator's S above the ~0.55 own-memory
  floor; the replica's P(large) AUC and window-net r stay at the iter17 own-memory level.
- H3' OPERATOR-LEVEL DECISION MEMORY, LEAKED BY THE SIBLINGS: the size hysteresis state S / E is shared across all five wallets; W4 /
  W5's public large prints are a lagged observation of it. Dimension: operator own state, PROXY via sibling prints (have, lagged ~2 s).
  Separates: S read from W4/W5 agrees with the operator's true S near the panel's 0.814 and well above 0.55; a hybrid replica state
  lifts P(large) AUC toward the true-state ceiling (0.80-0.84 within wallet) and window-net r toward 0.58 / 0.73.
- H5 REBATE-TIER VOLUME CONTROLLER (information P4 = X181): the large-class RATE is set by the operator's 30-day weighted-volume tier
  arithmetic, not per-decision. Dimension: fees/rebates (have, the TAKER_REBATE ledger). Separates: the daily large share tracks public
  pooled weighted-volume slack and configuration change-points fall on low-slack days. Not the per-decision coin; a rate-level account.
- H6 TWO INDEPENDENT STREAMS AFTER T0 (assumptions P1 = X186): post-T0 the per-window PnL is mostly the maker/resting stream, nearly
  independent of the taker stream, so a taker-only tracker fails condition 5 by construction. Dimension: own resting orders (have, from
  the book). Separates: frozen tracker r collapses on 10-31 dev blocks; a two-stream tracker recovers it. (A regime claim; development
  data is weekend-only, assumptions P2 = X187.)
- H7 CLOCK ARTEFACT, NOT A SIZE PROBLEM: the open gaps are instrument lag, not an undecoded decision. Separates: a restamped live clock
  / the capture collector clock restores the out-of-time side to >= 0.80 (not this iteration's target; X178-X180, X183).
This iteration discriminates H1 vs H3' on the siblings' public large prints (the primary test), and records H5 / H6 as the next pivots.

PRE-REGISTRATION 15 (written 11:24 UTC 11-01, in code/sib18.py before it was run to completion): THE OPERATOR'S SIZE-STATE S READ
FROM THE SIBLINGS' PUBLIC LARGE PRINTS. Record: operator taker orders of 10-20..22 (dcfit14 frame, exact calldata classes, large =
original size >= 90), the frozen smach17 transition model and state machine, dc14 side, the window-net / PnL proxy, all unchanged.
New state input, point-in-time: a W4 / W5 taker BUY leg filled >= 60 shares is a confirmed large print, usable at block_ts + 2 s;
txs that also contain a cluster wallet (DS/GF/XM) are excluded (shared-tx rule). S_pub = side of the most recent public W4/W5 large
print in the window before the order; E_pub its accumulated shares since the last flip. States scored: smach_own (iter17 reproduce),
smach_sib (public-only, deterministic), smach_hyb (own draws whose S/E are overwritten by a more-recent public print), class_oracle
and smach_true_state (ceilings), menu. Transition model fit on 10-20 with the TRUE state and TRUE side; scored on 10-21..22 and on
the reverse split (fit 10-21..22, score 10-20). CLAIM: the sibling state lifts (a) S agreement with the operator's true S to >= 0.75
on both splits, and (b) the replica's window-net r to >= menu + 0.05 on both splits, approaching the true-state ceiling; reported
with the P(large) AUC per wallet, the pub coverage, and the PnL proxy Pearson / Spearman. Whatever the result, nothing is refitted and
no target claim rests on W4/W5 until the examiner's X170 ruling (they are treated as other-trader market activity, as the frozen rule
already does; iter12 w45chk showed removing them leaves every metric unchanged).

10. NO VALUATION INPUT PICKS WHICH DECISIONS ARE LARGE (X168 in lite form; iv17.py, results/iv17.json; complete classes of 10-20..22): the
    digital fair value of o under Deribit DVOL (and under 300-s realized vol) minus the last non-operator Polymarket trade on o at m - 230,
    its absolute value, log(IV / RV) and |fv - 0.5| add nothing to the large-class AUC: public base (slot, window time) 0.673 -> 0.671
    (fit 10-20, scored 10-21..22) and 0.720 -> 0.720 (reverse); decision-memory base 0.816 -> 0.813 / 0.839 -> 0.837 (that base, with the
    operator's TRUE S / E, names the class at 0.80 / 0.84 / 0.87 for DS / GF / XM). P(large) is flat across |edge_IV| quintiles (GF 0.27 /
    0.28 / 0.29 / 0.27 / 0.23) and slightly lower when the edge favours o (GF 0.257 vs 0.279, XM 0.320 vs 0.370). Short-dated option-trade
    IV was not fetched (DVOL is the 30-day index).

11. THE FAST FOLLOWER IS PARTLY A SECOND TRIGGER (X172; fol17.py, results/fol17.json; capture day 10-21, 2,716 fast followers, gap q10 /
    median / q90 6 / 35 / 116 ms): the spot PSTH aligned at the follower's own match peaks at 295 ms (half-max 210-370, height 0.072)
    against 285 ms (150-360, 0.065) aligned at the leader's match; the spot move in the gap band (m_L - 260, m_F - 260], information the
    follower could see and the leader could not, is toward o in 54.5% of followers against 43.9% for singles given the same gaps
    (against o 18.2% vs 22.8%), rising with the gap (0.31 / 0.44 / 0.57 / 0.73 / 0.77 for gaps <= 10 / 30 / 60 / 100 / 150 ms). The
    panel's sharp signature (half-max <= 60 ms, >= 60% after the leader's event) is not met: the width is partly public (a continued
    move re-fires the decision), partly a coin of one decision.

13. THE NEW CONFIGURATION IS STABLE OVER THE THREE POST-T0 DEVELOPMENT BLOCKS (census31_17.py, results/census31_17.json; cached on-chain
    fills of the three studied wallets and the calldata of 1,500 sampled taker txs per block): taker order shares DS / GF / XM 0.626 /
    0.285 / 0.089 (10-31 00-06) and 0.681 / 0.261 / 0.057 (10-31 12-18), against 0.674 / 0.253 / 0.073 (11-01 06-09:30) and 0.630 / 0.309 /
    0.061 (10-20..22); menu 30 / 100 throughout; P(large) DS 0.042 / 0.023 / 0.036, GF 0.105 / 0.079 / 0.083, XM 0.187 / 0.302 / 0.233,
    pooled 0.073 / 0.053 / 0.062 (capture days DS 0.043, GF 0.268, XM 0.347, pooled 0.131); XM maker fills 2,483 / 2,158 / 804 against
    taker 323 / 135 / 73. Every block after T0 shows the same version: GF's large share cut to about a third, XM resting 60-share orders,
    the taker routing unchanged. The h1 / h2 lots (10-23..30) lie between 10-22 and 10-31; when the switch happened is unknown (sealed).

14. E3, FIRST PRE-REGISTERED SCREEN WITH tools/indicators.py (e3_17.py, results/e3_17.json; family and settings fixed in its docstring
    before the run: decisions = first legs at m0 - 180 ms, units = windows, swap null, max lag 2 s, 50-ms bins, 300 draws; screen
    10-19 with BH, confirm 10-20): Binance spot microprice jumps (3 sigma over 50 / 100 / 250 ms, 4 sigma over 100 ms) are survivors
    (q 4e-14 .. 4e-13, signed q 1e-18 .. 3e-16) and confirmed on 10-20 (p_link 5e-15 .. 8e-14, signed shape z 15.8-16.1), the timing
    shape peaking at +25 ms after the event on the decision clock (the knee); other traders' Polymarket taker BUY bursts are a survivor
    (q 2e-11) and confirmed (p 2e-10) but at a NEGATIVE lag (-0.53 / -0.58 s: the operator decides before the crowd's burst, which is
    downstream of the same move, not an input); spot crossings of the strike are not (q 0.43, signed q 0.066). The decoded input passes the
    brief's screen; the market-activity indicator lags the decisions.
15. E5, FIRST NEWS SCREEN OF THE CONFIGURATION SCHEDULE (e5b_17.py, results/e5_17.json; GDELT DOC 2.0 timelinevolraw, 24-h windows at 15-min
    bins around 10 dated changes and outages; a first 14-day query returned daily bins only and was discarded): GDELT answered HTTP 429
    for many requests even after retries; 'polymarket' 4 events usable, mean within-day rank of the news-volume share
    0.2292 (uniform 0.5; one-sided p 0.9706); 'bitcoin' 1 usable, mean rank
    0.0 (p 1.0). No news peak at the operator's configuration changes in what came back;
    the screen is weak (sparse 15-min volume, rate limits) and E5 stays open (social / calendar sources, live recording).

PRE-REGISTRATION 14 (written 10:15 UTC 11-01, before rest17 runs): A RESTING-REMAINDER STREAM IN THE TRACKER (assumptions panel P2 stream
(iii) = X174; finding 8). Tracker trk_a with the mix14 target, unchanged, plus: the unfilled part of each tracker order rests as a BUY
bid on o at its limit L for TTL = 30 s after its taker window, and fills strictly against later taker BUY prints of OTHER traders on the
complement at price >= 1 - L + 0.02 (match_slack 2 c; a mint against the resting bid), capturing 0.5 of each such print (other bids at L
compete; no queue data offline); resting fills add to the tracker's realized net. Scored once on the 864 windows of 10-20..22 in the same
run as mix14; ADOPTED only if pooled Pearson AND Spearman both beat mix14 (0.5065 / 0.4674). Reported: per wallet (XM in particular),
halves, TTL 10 / 60 s variants (reported only).

12. PRE-REGISTRATION 14 FAILED: A RESTING-REMAINDER STREAM IS ADVERSELY SELECTED AND DECORRELATES THE TRACKER (X174 stream (iii); rest17.py,
    results/rest17.json; the re-implementation reproduces trk_a / mix14 exactly at TTL 0): with the unfilled part resting 30 s at its limit
    and filling against complement taker BUYs at >= 1 - L + 2 c (capture 0.5), the tracker gets 35,503 resting fills (201,837 shares) that
    lose $13,654 (-6.8 c a share) and the pooled r falls to 0.4365 / 0.4226 (mix14 0.5065 / 0.4674; XM -0.004 / 0.021); TTL 10 s 0.4956 /
    0.4508, TTL 60 s 0.3285 / 0.4078. The operator's remainders earn because they rest at the PRE-move ask of a fresh Binance move; a
    replica's remainders, 1-3 s late at ask + 2 c, are the stale quotes that faster traders pick off. Not adopted. Stream (ii) (the pair
    margin from a small two-sided stream at the decoded decisions) is still untested.

Findings (iteration 18):
1. PRE-REGISTRATION 15 (PIVOT; sib18_prep.py + sib18_run.py, results/sib18_10-21_10-22.json, sib18_10-20.json; forward = fit 10-20,
   score 10-21..22 / reverse = fit 10-21..22, score 10-20; ? W4/W5 large prints):
   THE OPERATOR'S SIZE STATE S IS RECOVERABLE FROM THE SIBLINGS' PUBLIC LARGE PRINTS. A W4/W5 taker BUY filled >= 60 shares is a
   confirmed large print, usable at block_ts + 2 s, shared txs (with DS/GF/XM) excluded; pub coverage of SCO orders 0.58
   / 0.497.
   - S AGREEMENT with the operator's true S (three-wallet, exact calldata >= 90): public-only S_sib 0.495 / 0.4319;
     hybrid S_hyb (own draws overwritten by a more-recent public print) 0.6096 / 0.6102; replica OWN memory
     0.5564 / 0.5606 (iter17 pre-registration 12: 0.546 / 0.558). Bar 0.75 on both splits: hyb False.
   - P(large) AUC (large class, pooled): hyb 0.7994 / 0.8554; sib 0.8001 / 0.8481; own 0.7933 /
     0.8485; true-state ceiling 0.8183 / 0.8655. Per wallet (hyb): GF 0.7098/0.75,
     DS 0.6184/0.6819, XM 0.624/0.6269.
   - WINDOW-NET r(N) (size-expectation proxy, NOT the executable tracker): menu 0.2895 / 0.4345; sib 0.3872
     / 0.5359; hyb 0.3524 / 0.514; true-state ceiling 0.588 /
     0.7214. rN >= menu + 0.05 (hyb, both splits): True. PnL-proxy Spearman: menu 0.2244/0.4053,
     hyb 0.3139/0.486, ceiling 0.5659/0.7055; Pearson hyb
     0.281/0.4903. Paired 2-h block bootstrap of the PnL-proxy Spearman GAIN vs the menu (no-sibling) baseline: sib +0.111 [0.070,
     0.152] (forward) / +0.109 [0.022, 0.204] (reverse), hyb +0.089 [0.065, 0.115] / +0.081 [0.018, 0.134] -- lower CI bound > 0 on
     both splits, so the sibling size signal is a significant, reproducible gain over the baseline that already contains W4/W5 prints.
   VERDICT: H3' PARTIAL: the siblings' public large prints carry PART of the within-window size state (PnL-proxy Spearman beats own-memory and the menu on both splits) but S agreement stays below 0.75 and the lift reaches only ~60% of the true-state ceiling; the within-window coin and commitment E remain undecoded. This is a ceiling / attainability result (E[size] expectation, not the strict-fill executable tracker), so it does
   NOT move target_metrics.pnl_corr this iteration; it raises condition 5's ceiling and gives the next iteration an executable path
   (feed the public sibling size signal into the mix14 tracker). It rests on W4/W5 being 'other traders' (X170); the frozen rule already
   treats their prints as market activity and iter12's w45chk showed removing them leaves every metric unchanged, so it is admissible
   under the current treatment pending the examiner's ruling. Note the panel's 0.814 S-agreement (w4S.py) was a CROSS-window running
   state on its covered subset; under smach17's WITHIN-window S with the 2 s PIT lag and the shared-tx exclusion the coverage is ~0.5 and
   the agreement is 0.49-0.61, which is why the lift is partial. H1 (a fully private size coin) is weakened: the siblings carry part of
   the state's SIDE; the undecoded residual is the within-window commitment E and which of the shared-S decisions are drawn large.

Missing-dimensions update (E2): the SIZE residual's dominant term 'which side is the current large lean' (S) is no longer a private
coin -- it is a public lagged dimension (operator own state observed via the siblings W4/W5, dimensions own_decision_memory -> proxy,
operator_sibling_wallets -> drives). What remains undecoded for size: the per-decision draw (which of the shared-S decisions are large)
and the commitment E. Side / timing / price unchanged; condition 2 (presence gain) and the executable condition 5/7 are unchanged.

Panel proposals of iteration 17 (catalog X178-X190) and what happened to them:
- X182 (mechanics P1, this iteration): TRIED -- the pivot (finding 1); H3' PARTIAL.
- X178 / X189 (info P1 / asm P4, capture 10-31 day file on the collector clock) and X170: OPEN -- need the examiner's access ruling; the
  single clean out-of-time test of whether the side route transfers to the new regime. Stated for the examiner in FINAL_RULE.
- X179 / X180 / X183 (info P2 / P3, mechanics P2, the clock): OPEN -- the live-feed burst lag (spot/USD-M residual r=0.78) and the capture
  burst lag; the restamp and a minimal recorder for the next development blocks.
- X181 (info P4, rebate-tier volume controller on pooled wV): OPEN -- the next pivot for the size RATE (vs this iteration's size STATE).
- X184 / X188 (mechanics P3 / asm P3, XM 60-share post-only GTC counterfactual + resting-stream replica): OPEN (= X177).
- X185 (mechanics P4, salt-generator draw counting): OPEN (= X149).
- X186 (asm P1, re-target conditions 5/7 for the post-T0 regime + two-stream tracker): OPEN -- the regime PnL route.
- X187 (asm P2, weekend-mode check on 11-02 weekday dev blocks): OPEN.
- X190 (asm P5, presence as an ORDER unit vs a fill second): OPEN -- the strongest route to flip condition 2 (decision-clock gain
  +0.058 [0.050, 0.065] already exists at the order level).

## Next (iteration 19)

Status after iteration 18: target not reached; target_metrics UNCHANGED (presence 0.8701 vs 0.8464 block clock; side 0.8369; price
0.9512; PnL 0.5065 / 0.4674; coverage 1 / 1). PIVOT result (pre-registration 15, sib18): the operator's size STATE S is PARTIALLY a
public lagged dimension carried by the sibling wallets W4/W5. The pre-registered rN-lift bar (window-net r >= menu + 0.05 on both
splits) is MET by the public (sib) and hybrid state (rN 0.387/0.536 vs menu 0.290/0.435; reverse 0.536/0.514 vs 0.435); PnL-proxy
Spearman sib 0.336/0.511 and hyb 0.314/0.486 beat own-memory 0.268/0.446 and menu 0.224/0.405 on both splits. The S-agreement bar
(>= 0.75) is NOT met: within-window S agreement is 0.49 (public) / 0.61 (hybrid), coverage ~0.5 (the panel's cross-window 0.814 does
not survive the within-window PIT definition + 2 s lag + shared-tx exclusion). It reaches ~60-75% of the true-state ceiling
(pnl_S 0.566/0.706). So part of condition 5's "which decisions are large" is public (the SIDE of the current large lean, lagged via
the siblings); the undecoded residual is the within-window commitment E and the per-decision draw. This is a ceiling/attainability
result (E[size] proxy, not the strict-fill tracker), pending the X170 ruling on W4/W5.

1. EXECUTE the public sibling size signal in the mix14 tracker (the step this iteration did not take): weight the per-second net-flow
   target by the public-state P(large) at each decision and re-measure target_metrics.pnl_corr (strict fills), both splits, vs the
   co-occurrence baseline that already contains W4/W5 prints. This is the test of whether the partial size decode moves the EXECUTABLE
   condition 5 (not only the proxy). Report with and without W4/W5 pending X170.
2. X190 (panel asm P5, strongest route to flip condition 2): make the presence unit an ORDER (taker submission at m-150 + maker
   postings), not a fill second; the decision-clock order-level gain over a book-aware baseline at the e cut is already +0.058
   [0.050, 0.065]. Establish coverage (>= 80% of fills / abs PnL) by combining the knee hazard (taker submissions) with the ladder-burst
   clock (maker postings).
3. X181 (panel info P4): the size-class RATE as an Obsidian-tier pooled-weighted-volume controller (the complement to this iteration's
   size STATE). Development fee days only.
4. X178/X189 + X170: ask the examiner for the capture 10-31 day-file access ruling (the clean out-of-time side test) and the W4/W5
   admissibility ruling. X179/X180/X183: the live/capture burst-clock restamp for the out-of-time side.
5. Still open (64): E3, E5, E6, X5, X7, X18, X26, X33, X36, X37, X44, X51, X53, X57, X70, X72, X87, X88, X90, X100, X104, X107, X113,
   X115, X122, X123, X124, X127, X128, X130, X133, X139, X141, X146, X148, X149, X150, X151, X153, X154, X155, X158, X159, X160, X161,
   X164, X167, X170, X172, X174, X175, X177, X178-X190.

Recorders at the end of iteration 18: the shared recorder runs (pid 27184); rec_bn15 v2 (hard stop 11-01 12:00 UTC) and the other
recorders were not touched; no recorder started or stopped this iteration. No polyrea bug found. New scratch: it18/sib_frame.parquet
(the cached operator frame + sibling-print state; rebuild sib18_prep.py ~10 s once the heavy jobs are off the laptop). polyrea PERF
NOTE (not a bug): pandas Series.isin(python_set) rebuilds the hashtable each call; use set-membership on the small subset instead
(cost me one wasted run before the fix).

### Iteration 19 (2026-11-01 12:43 UTC start, local Windows laptop; development data: before H, and 10-31 00-06 / 12-18, 11-01 06-12)

Split and primary metric unchanged (BUILD 10-09..16, VALIDATE 10-16..23; the capture-day work fits on 10-17..19 and scores 10-20..22,
plus the reverse split). Calendar (`sealed.py btc5m-bot`, 12:48 UTC): released none; future examined until 10-31 00:00; current block
11-01 12-18 sealed (nothing from it touched). Shared recorder running (`live.py status`: wallet feed not stopped, current block sealed,
hard stop 1793881098). Budget before this iteration: 1158 of 1200 minutes. No recorder started or stopped. No network fetch this
iteration (every input was already on disk); no download.

PIVOT (required: < 0.01 progress over iterations 17-18). NEW DIMENSION and a new unit of analysis: the operator's decision clock split
by the public CME Globex calendar, read as an event-aligned PSTH around Binance spot jumps (assumptions panel iter18 P1 = X191). The
question is no longer "which venue adds to the knee" (iterations 4-17, all on pooled days) but "does the knee itself depend on whether
a TradFi venue is open".

Competing explanations (written at the start of the iteration; what separates them):
- H1 A GLOBEX-HOURS LEADING INPUT (missing dimension, `tradfi_globex_feed`: CME BTC / MBT futures or CME equity-index futures; paid /
  not on disk): when Globex is open the operator also acts on moves that every 24/7 venue prints later. Separates: (i) the reaction
  peak to Binance jumps stays at its closed-hour lag (~260 ms) in open hours, (ii) open hours add same-side decisions BEFORE the
  reaction band, also for isolated jumps, (iii) the extra mass vanishes in the Mon-Thu Globex break (21-22 UTC under CDT) and appears at
  the Sunday 22:00 UTC open, (iv) after the US DST change it follows the calendar to 22-23 UTC.
- H2 A SHORTER LATENCY CHAIN ON WEEKDAYS (own infrastructure): the whole knee moves ~100 ms later on weekdays. Separates: the reaction
  peak itself shifts to ~160 ms in open hours; the break hour looks like its neighbours.
- H3 WEEKDAY MOMENTUM (no new input): Binance jumps are more often continuations on weekdays, so earlier decisions on the same side
  precede them. Separates: the open-hour excess disappears for isolated jumps and the crowd shows the same excess.
- H4 AN OPERATOR UTC SCHEDULE (configuration): the operator switches a feature off on weekends and at 21:00-22:00 UTC. Separates: only
  the DST shift (H1 moves the low hour to 22-23 UTC from 11-02; H4 keeps it at 21-22).
- H5 A CLOCK ARTEFACT of the capture's book mapping (receive - 131 ms) under weekday load. Separates: the effect persists on
  exchange-stamped trades (T) and on USD-M trades; the crowd's peak would move with it.
- H6 (size, carried over) a private per-decision size coin inside the register vs H7 the siblings' public view of the register.
  Separates: exchangeability of the class within strata; the sibling state's out-of-time gate.
At least H1 rests on a missing dimension. This iteration discriminates H1-H5 on disk and pre-registers the DST test (H1 vs H4), and
closes the sibling route's out-of-time gate (H7) and the exchangeability test (H6).

PRE-REGISTRATION 16 (code/knee19.py docstring, before the run): session-split per-venue knee profiles (knee14's definition) and an
event-aligned PSTH around Binance spot microprice jumps, operator first legs of 10-17..22, Globex calendar on CDT.
PRE-REGISTRATION 16b (code/knee19b.py, after 16's first result, before its run): isolated jumps (no |z| > 2 move in the 2 s before),
the crowd through the same PSTH, and the session boundaries (break hour vs 20-21 / 22-23 UTC; Sunday 18-22 vs 22-24 UTC); statistic E =
same-minus-opposite first legs in [0, 230) ms after the jump over the same excess in the reaction band [230, 320) ms.
PRE-REGISTRATION 16c (code/knee19c.py): T1 open > closed (hourly Mann-Whitney; 30-min block bootstrap), T2 break < neighbours (per
day and bootstrap), T3 operator's session effect > the crowd's.
PRE-REGISTRATION 16d (code/knee19d.py): the same statistic on exchange-stamped spot TRADES only (no receive clock), as the instrument for
the DST test.

Findings (iteration 19):
1. THE OPERATOR'S KNEE DEPENDS ON THE CME GLOBEX SESSION; NO 24/7 VENUE ON DISK IS THE INPUT (pre-registration 16; knee19.py,
   results/knee19.json; 92,073 first legs; closed 19,646 / open 72,427). G = acc(c = 160) - acc(c = 260), sign of the venue's change over
   [m0 - c - 250, m0 - c):
   | venue (own clock) | closed: acc 260 / 160 / G | open: acc 260 / 160 / G |
   |---|---|---|
   | spot book (receive - 131) | 0.837 / 0.827 / -0.010 | 0.798 / 0.839 / +0.041 |
   | spot trades (T) | 0.565 / 0.568 / +0.004 | 0.563 / 0.583 / +0.020 |
   | USD-M BTC trades (T) | 0.592 / 0.590 / -0.001 | 0.581 / 0.601 / +0.020 |
   | USD-M ETH trades (T) | 0.631 / 0.644 / +0.013 | 0.607 / 0.645 / +0.038 |
   | OKX swap trades (T) | 0.535 / 0.540 / +0.005 | 0.550 / 0.567 / +0.017 |
   | Coinbase (12 cached hours) | 0.531 / 0.552 / +0.021 | 0.542 / 0.594 / +0.053 |
   | Deribit perp (12 cached hours) | 0.538 / 0.589 / +0.051 | 0.545 / 0.625 / +0.080 |
   Spot book G per wallet closed / open: DS -0.011 / +0.046, GF -0.011 / +0.024, XM +0.001 / +0.039; per day: 10-17 -0.011, 10-18
   closed -0.011 and its open 22-24 h +0.013, 10-19 +0.043, 10-20 +0.064, 10-21 +0.040, 10-22 +0.017; the three break hours of 10-20..22
   -0.003 / -0.022 / -0.005. Every 24/7 venue keeps rising past its knee in open hours and none saturates there (the panel's step 1
   adoption condition is not met by any venue). Bybit's 100-ms bins read +0.12-0.14 in both sessions (the bin-end clock, uninformative).
   The crowd (975,955 non-operator taker BUYs) peaks at c = 250-260 in every session (G -0.011 closed, -0.015 / -0.013 open).
2. THE REACTION TO BINANCE DOES NOT CHANGE; OPEN HOURS ADD DECISIONS THAT PRECEDE IT (H2 rejected; pre-registration 16, PSTH; 57,811
   spot microprice jumps): the operator's same-side excess peaks at +260 ms after the jump in closed, open-US and open-other hours alike
   (half-max 250-300 / 170-340 / 230-310 ms). Same-side minus opposite-side first legs per 1,000 jumps in [0, 230) ms: closed 31.3,
   open-US 81.0, open-other 76.5; in the reaction band [230, 320): 81.6 / 64.8 / 81.1.
3. THE EXTRA MASS FOLLOWS THE CME CALENDAR, NOT THE WEEKDAY, AND SURVIVES ISOLATED JUMPS (H3 rejected for the operator; pre-registrations
   16b / 16c; knee19b.py, knee19c.py, results/knee19b.json, knee19c.json; 31,435 isolated jumps). E (isolated jumps):
   | cell | operator E | crowd E |
   |---|---|---|
   | weekend (closed) | 0.413 | 0.234 |
   | Mon-Thu 21-22 UTC (Globex break) | **0.211** | 0.279 |
   | Mon-Thu 20-21 UTC | 0.776 | 0.517 |
   | Mon-Thu 22-23 UTC | 0.730 | 0.435 |
   | Sunday 10-18 22-24 UTC (Globex reopened) | 0.549 | 0.541 |
   | other open hours | **0.996** | 0.438 |
   T1: operator E open 0.960 vs closed 0.388, hourly Mann-Whitney p = 1.1e-15 (85 / 49 hours; medians 0.95 / 0.375), block bootstrap of
   the difference +0.571 [0.473, 0.668] (p < 0.0005); crowd +0.206 [0.154, 0.260]. T3: the operator's session effect exceeds the
   crowd's by +0.365 [0.263, 0.473]. T2: neighbours minus break +0.538 [0.307, 0.851] (p < 0.0005); per day break / neighbours 0.11 / 0.49
   (10-19), 0.21 / 0.80 (10-20), 0.33 / 0.90 (10-21), 0.23 / 0.91 (10-22): lower on 4 of 4 days; crowd +0.189 [-0.038, 0.381] (p 0.041).
   Per wallet E open / closed: DS 1.10 / 0.41, GF 0.68 / 0.35, XM 0.62 / 0.28. The reaction peak stays at 260-270 ms in every cell.
4. THE CLOCK-FREE INSTRUMENT SEES IT TOO (H5 rejected; pre-registration 16d; knee19d.py, results/knee19d.json; 33,474 isolated
   last-trade-price jumps on T, server-ms matches): E open 0.994 vs closed 0.536, difference +0.458 [0.331, 0.576] (p < 0.001);
   neighbours minus break +0.405 [0.086, 0.805] (p 0.009); break 0.328, weekend 0.565, 20-21 h 0.793, 22-23 h 0.698, other open 1.034;
   reaction peak 250-270 ms in every cell. So the DST test (pre-registration 20) can run on data.binance.vision aggTrades with no
   laptop clock.
5. SIZE OF THE MISSING INPUT (sess19.py, results/sess19.json; first legs): univariate knee accuracy at c = 260 is 0.837 closed against
   0.798 open; under a two-class mixture (Binance-led decisions at the closed-hour accuracy, the rest at a_g = 0.5-0.6) the share of
   open-hour first legs triggered by the hidden input is pi = 0.115-0.163, i.e. about 9-13% of all first legs (open hours carry 79% of
   them). By UTC hour on open weekdays G is positive in every hour (0.008-0.069; highest 06 UTC 0.069, 07-08 0.053-0.054, 12 0.053, 14
   0.055; lowest 23 UTC 0.008 and 20 UTC 0.019); in closed hours -0.037..+0.023. The frozen knee-clock hazard (hazard14_scored, 10-20..22,
   weighted AUC) by session: closed 0.933 full / 0.887 spot-only / 0.746 Polymarket-only; open-US 0.879 / 0.789 / 0.744; open-other
   0.889 / 0.808 / 0.764: the spot-only margin over market activity is +0.141 closed against +0.044 open.
6. PRE-REGISTRATION 18 FAILED: SESSION-AWARE SIDE ROUTES ADD NOTHING WITHOUT THE INPUT (X193; sess19.py; dcfit14's frame, PARAMS and
   SPOT columns). Forward (fit 10-17..19, score 10-20..22): base 0.8369 (open 0.8363 / closed 0.8610), + Globex indicator 0.8359, split
   fits 0.8360. Reverse: base 0.8507 (0.8429 / 0.8578), indicator 0.8515, split 0.8467. Neither variant improves on both splits; nothing
   adopted. The frozen dc14 side is 2.5 points better when Globex is closed (0.861 vs 0.836).
7. PRE-REGISTRATION 17 FAILED: A CLOCK-FREE TRADE-ONLY SIDE IS WEAK BUT TRANSFERS (X195 = information P2; oot19.py, results/oot19.json;
   model_it19_tradeside.txt). Exchange-stamped spot trades only (returns and signed aggressive quantity over 100-2000 ms at X = m - 260),
   fit 10-17..19: in time 0.6035 per order (first legs 0.594; placebo -/+3 s 0.504 / 0.478; DS 0.59 / GF 0.62 / XM 0.65), out of time
   (11-01 06:00-09:30, 999 orders, server-ms matches) 0.6176 (first legs 0.604; placebo 0.50 / 0.55; DS 0.588, GF 0.656, XM 0.753;
   halves 0.618 / 0.618). c = 230: 0.614 / 0.665; c = 300: 0.570 / 0.577. The side information at the knee is in the BOOK (microprice),
   not in prints (top gain: signed aggressive quantity over 100 / 250 ms). Out of time the exchange-stamped part loses nothing (0.618 vs
   0.604 in time), so the book route's out-of-time drop (0.72-0.75) sits in the book feed's clock (H7 of iteration 18), not in a regime
   change of what the operator reacts to.
8. THE SIBLING SIZE ROUTE IS VERSION-BOUND (X200 step 3 = mechanics P2 gate; X199 = mechanics P1; X192 = assumptions P2; the panel's
   chk13 / chk15 re-run unchanged from it19/p18m_rerun/). In time the corrected state reproduces: W4 only, fill >= 31, E x k (k = 6.0 /
   5.0 on the fit days): covered agreement 0.841 / 0.823, coverage 0.651 / 0.588, PnL-proxy Spearman 0.444 / 0.577, gain over sib18
   +0.106 [0.067, 0.149] / +0.066 [0.020, 0.109] (the assumptions panel's >= 0.80 covered-agreement bar holds in time). Out of time
   (11-01 06:00-09:30, 999 orders, 62 large) the pre-registered gate fails: covered agreement 0.564 (W4 >= 31; 0.412 at >= 60), P(large |
   with) / P(large | against) = 0.073 / 0.055 = 1.33 (bars 0.75 and 2), while the operator's own S still separates (0.115 / 0.033 /
   0.049 with / against / none). The route stays out of the frozen rule whatever X170 rules; the executable tracker run (P1 step 3) and
   the W4 calldata fetch (X196) were therefore not run.
9. THE SIZE CLASS IS NEARLY, NOT EXACTLY, A COIN INSIDE THE REGISTER (pre-registration 19, X198 step 1; exch19.py, results/exch19.json;
   73,577 orders, 1,436 strata wallet x hour x slot x S-relation x E tercile, 2,000 within-stratum permutations): lag-1 same-class
   rate, same wallet and window 0.8189 vs null 0.8087 (+0.010, p < 0.0005); pooled operator sequence 0.7901 vs 0.7781 (+0.012); gaps
   < 2 s +0.012, >= 2 s +0.008 (both p < 0.0005); large runs 7,039 vs 7,378 (clustering, p < 0.0005). Not exchangeable at 0.01, but the
   dependence beyond the register is small (a lag-1 correlation of about 0.03-0.05), largest at short gaps (copies of one decision).
   Condition 5's size term stays bounded by the expectation ceiling of iteration 18 (true-state PnL-proxy Spearman 0.566 / 0.706). The
   JavaScriptCore WeakRandom solver (step 2) was not run.
10. RESTARTS AND THE PUBLIC SDK PIPELINE: NOT CONFIRMED ON FRESH EVENTS (pre-registration 21, X197 = information P3 step 1; sdk19.py,
   results/sdk19.json): the cluster fill record before H (10-09..22) has only 2 fresh whole-cluster gaps of 10-20 minutes, neither within
   10 minutes after a ts-sdk push (p 1.0: no power). On the panel's own 24 boundaries of gaps >= 20 minutes, 4 fall within 10 minutes
   after a push against a whole-day-shift null mean of 0.49 (p 0.0002; adds 10-15 07:51:32 to the panel's three); +60-minute shifted
   control 0. Open (needs the post-T0 development blocks or older pushes).
11. EXAM ROUTE REPORTING (no rule change): dc_exam14.decision_clock_side() now also returns `by_globex_session` (and per wallet), with a
   DST-aware CME calendar (`globex_open_ms`: CDT until 11-01 07:00 UTC, CST after). Smoke test on 10-20 20:30-21:30 (the break hour
   inside): 922 of 924 orders matched, 0.8471 per order (as before), open 0.824 (545) / closed 0.881 (377), 56 s.


PRE-REGISTRATION 20 (the US-DST natural experiment, X191 step 2; written 11-01 ~14:05 UTC, BEFORE any of its data exist). US DST ended on
11-01 07:00 UTC, so from then on CME Globex opens Sunday 23:00 UTC, breaks Mon-Thu 22:00-23:00 UTC and closes Friday 22:00 UTC.
- Units: operator first legs (DS / GF / XM taker BUY orders; 300-ms rule per (window, outcome)) in the development blocks 11-01 18-24,
  11-02 00-06, 11-02 12-18, 11-03 06-12, 11-03 18-24 (sealed.intervals; every window asserted not sealed).
- Match ms m: the live lab's Polymarket trade records with tx hash (clob_crypto / btc5m_clob_raw2 'x' records, server ms), the
  operator's taker txs from on-chain V2 OrderFilled (post17.py steps 1, 2 and 4 per block).
- Binance: data.binance.vision spot aggTrades BTCUSDT for 11-01..11-03 (T-stamped; published the next morning; .CHECKSUM verified;
  reduced at once and the zip deleted). No receive clock enters.
- Statistic: knee19d's E (isolated last-trade-price jumps; early [0, 230) over reaction [230, 320)), per cell of the CST calendar:
  closed = 11-01 18:00-23:00; sunday_open = 11-01 23:00-24:00; open = 11-02 and 11-03 outside 22-23 UTC; break = 11-03 22:00-23:00;
  old-break hour = 21:00-22:00 UTC on 11-02 / 11-03 (now open). 30-min block bootstrap, 2,000 draws.
- Predictions (H1): E(closed) <= 0.65 (capture closed 0.54); E(open) >= 0.85 (capture open 0.99) with open - closed > 0 at the
  bootstrap's 2.5% bound; E(old-break hour 21-22 UTC) at the open level; E(11-03 22-23 UTC) below its neighbours; reaction peak
  250-270 ms in every cell. H4 (an operator UTC schedule) predicts the low hour stays at 21-22 UTC and 22-23 UTC reads open.
- Whatever the result nothing is refitted. If H1 holds, `tradfi_globex_feed` is confirmed as a calendar-locked input and step 3 (CME
  millisecond data, paid: Databento CME MDP3 BTC / MBT and ES / NQ for a few weekday hours of 10-19..22) is the decisive data request,
  which needs the user's approval.

Missing-dimensions update (E1 / E2): new dimension `tradfi_globex_feed` (family related markets; status missing, paid; verdict drives,
inferred from the calendar-locked lead). The timing and side residuals now have a shape: in Globex-open hours about 12-16% of first
legs are triggered before any 24/7 venue on disk moves (finding 5), the side at the knee is 3.9 points lower than when Globex is closed
(0.798 vs 0.837), and the knee-clock hazard's margin over market activity is a third of its closed-hour value (+0.044 vs +0.141). The
earlier entry "flat by UTC hour (no session pattern)" (side misses by hour) pooled weekdays and weekends; split by the CME calendar the
pattern is clear. The size residual: nearly a coin inside the register (finding 9); the siblings' view of the register does not survive
the regime change (finding 8).

More findings (iteration 19, after the first block):
12. PRE-REGISTRATION 22 FAILED: AT THE BLOCK CLOCK THE PRESENCE MARGIN IS NOT CONCENTRATED IN CLOSED HOURS (pres19.py, results/pres19.json;
   pres14's pipeline unchanged, both directions). Forward (MSB fit 10-17..19, scored 10-20..22): pooled frozen 0.8701 vs MSB 0.8466,
   +0.0235 [0.017, 0.031]; open 0.8703 vs 0.8465 (+0.024 [0.017, 0.032]); closed (the three break hours, 13,810 cells) 0.8503 vs 0.8451
   (+0.005, too few blocks for the bootstrap). Reverse (MSB fit 10-20..22, scored 10-17..19): pooled 0.8722 vs 0.8476, +0.025 [0.021,
   0.028]; open (116,456 cells) 0.8729 vs 0.8470 (+0.026 [0.021, 0.031]); closed (224,668 cells, the weekend) 0.8672 vs 0.8472 (+0.020
   [0.017, 0.023]). So the Globex input explains part of the DECISION-clock timing residual (finding 5: hazard margin +0.14 closed vs
   +0.04 open), but not the BLOCK-second presence gap of condition 2: where the operator's trigger is entirely on Binance (the weekend)
   the frozen block-second rule still gains only +0.020 over market activity. At the block clock the binding term is the co-arrival
   structure (the crowd's prints in the same seconds), as iteration 14 found; CME data would not by itself flip condition 2 at this unit.
13. THE POLYMARKET BOOK'S EXTRA SIDE INFORMATION EXISTS ONLY WHEN GLOBEX IS OPEN (pre-registration 23; sidebook19.py, results/sidebook19.json;
   sidebook15 unchanged plus the session split and the reverse split). DC14 + book minus DC14: forward open +0.025 (45,262 orders) vs
   closed -0.004 (1,307, the break hours); reverse open +0.023 (26,408) vs closed -0.025 (600). Book-only accuracy open 0.713 / 0.715 vs
   closed 0.674 / 0.677. Reading: in open hours other participants move Polymarket's book with the same hidden input before the operator
   decides, so iteration 15's 'dc14 + book' gain (+0.025) is the public trace of the Globex input (a partial proxy, at m0 - 210 ms, inside
   the operator's own view window); the closed samples are small (break hours only), so this is suggestive, consistent on both splits.
14. OUT OF TIME, CLOSED SESSION, CLOCK-FREE (pre-registration 20b; oot19b.py, results/oot19b.json; 11-01 06:00-09:30, Sunday, 770 first
   legs, 366 isolated trade jumps from the live lab's T-stamped trades, server-ms matches): E = 0.162 (excess 6 early / 37 reaction),
   reaction peak at 250 ms; the closed-session prediction (E <= 0.65) holds (small sample). The clock-free knee reproduces out of time.
15. WHO ELSE: A FEW OTHER FAST TAKERS SHOW A WEAKER GLOBEX-HOURS LEAD; NONE MATCHES THE OPERATOR (pre-registration 24; who19.py,
   results/who19.json; 15,139 non-operator taker wallets on the VALIDATE tapes of 10-17..22, timed by the capture's server ms, operator
   wallets and every tx with an operator fill excluded). Crowd total E open 0.446 vs closed 0.252. Of the 67 wallets with a reaction
   excess >= 15 in both sessions, the open-minus-closed difference dE has quantiles 10% -0.067 / 50% +0.042 / 90% +0.352; the largest are
   0xb55fa129... (E 0.79 / 0.31, dE 0.48), 0x3c58ef42... (0.94 / 0.49), 0x21f4c1a1... (0.77 / 0.32), 0xeb942f0f... (0.49 / 0.05), 0x764fd57b...
   (0.61 / 0.18); only 1 has E_open >= 0.8 with E_closed <= 0.5. The operator's dE (+0.57) is larger than every eligible wallet's. So
   the Globex-hours input is not private to the operator: a minority of fast takers react to something that leads Binance in open
   hours, more weakly (consistent with a paid but public TradFi feed such as CME futures). Evidence only; no wallet's prints enter any
   rule (brief, 'Who else').

Panel proposals of iteration 18 (catalog X191-X201) and what happened to them:
- X191 (assumptions P1, Globex-hours input): step 1 TRIED (findings 1-5; no on-disk venue saturates, so none is adopted); step 2
  PRE-REGISTERED (pre-registration 20; its data start with the 11-01 18-24 development block); step 3 needs paid CME data and the
  user's approval. OPEN.
- X192 (assumptions P2, W4-only coverage-aware state): TRIED in time (covered agreement 0.84 / 0.82 >= 0.80); the tracker execution
  and the switch were stopped by the out-of-time gate (finding 8). The two-part X170 question is in FINAL_RULE.
- X193 (assumptions P3, session-aware frozen routes): TRIED, pre-registration 18 failed (finding 6).
- X194 (assumptions P4, configuration tracker): OPEN (W4 variant carries the X170 caveat and the sibling view failed out of time).
- X195 (information P2, clock-free out-of-time side): TRIED, pre-registration 17 failed the bar but transfers (finding 7).
- X196 (information P1, W4 / W5 calldata): OPEN, deprioritized (the route cannot enter the frozen rule after finding 8).
- X197 (information P3, SDK-pipeline restarts): step 1 TRIED on fresh events without power (finding 10). OPEN.
- X198 (mechanics P3, size coin + JSC solver): step 1 TRIED (finding 9); step 2 OPEN.
- X199 (mechanics P1, rescale E / W4 only): TRIED (reproduced in time; tracker run stopped by the gate, finding 8).
- X200 (mechanics P2, copy baseline + out-of-time gate): gate TRIED and failed (finding 8); the executable copy tracker not run.
- X201 (mechanics P4, XM 60-share natural counterfactual): OPEN.

## Next (iteration 20)

Status after iteration 19: target not reached; target_metrics UNCHANGED (presence 0.8701 vs 0.8464 at the block clock; side 0.8369;
price 0.9512; PnL 0.5065 / 0.4674; coverage 1 / 1). The budget (1200 minutes) is spent with this iteration; if it is extended, in order:
1. RUN PRE-REGISTRATION 20 (the US-DST natural experiment) as soon as data.binance.vision publishes the 11-02 / 11-03 / 11-04 spot
   aggTrades: post17.py per development block (11-01 18-24, 11-02 00-06, 11-02 12-18, 11-03 06-12, 11-03 18-24) for the operator's taker
   txs and the live lab's server-ms matches, then knee19d's statistic on T-stamped trades; nothing refitted.
2. ASK THE USER for a CME millisecond source (Databento CME MDP3: BTC / MBT and ES / NQ, a few weekday hours of 10-19..22 where the
   capture gives the operator's server-ms matches). Then: the operator's knee on CME's clock (expected ~190-220 ms = ~40 ms to London +
   150 ms hold), which product's moves precede the open-hour pre-Binance decisions, the side and the knee-clock hazard on CME in open
   hours (expected back to the closed-hour levels 0.85 / 0.89), and whether the 10-22 side anomaly (iteration-18 assumptions panel)
   disappears on CME. This is the one input that could lift condition 2 at the decision clock, because makers who read Binance react
   after the operator.
3. Until then: report every presence / timing / side metric by Globex session (the exam route does this for the side now).
4. Still open: E3, E5, E6, X5, X7, X18, X26, X33, X36, X37, X44, X51, X53, X57, X66, X70, X72, X87, X88, X90, X100, X104, X107, X113,
   X115, X122, X123, X124, X127, X128, X130, X133, X139, X141, X146, X148, X149, X150, X151, X153, X154, X155, X158, X159, X160, X161,
   X164, X167, X170, X174, X175, X177, X178-X181, X183-X190, X191, X194, X196, X197, X198, X201 (70 items; the exact list is
   state.json catalog_open_after_iteration19).

Recorders at the end of iteration 19: the shared recorder runs; no recorder started or stopped; rec_bn15 v2 ended at its 11-01 12:00
hard stop (before this iteration). No polyrea bug found. Engineering note (not a polyrea bug): blkaug9.py / block_presence.py /
decision_presence.py rewrite sys.argv at import (insert "four"); a script that imports them must read its own arguments first (cost
one failed pres19 run). New scratch: it19/ (logs, the panel-script re-runs in it19/p18m_rerun/, state_backup_before19.json).
New code: knee19.py, knee19b.py, knee19c.py, knee19d.py, sess19.py, oot19.py (+ model_it19_tradeside.txt), exch19.py, sdk19.py,
pres19.py, sidebook19.py, oot19b.py, who19.py; dc_exam14.py gained `globex_open_ms` and the `by_globex_session` report. New results: knee19*.json,
sess19.json, oot19.json, oot19b.json, exch19.json, sdk19.json, pres19.json, sidebook19.json, who19.json.

Late findings (iteration 19, written after the 'Next' list above; they do not change it):
16. THE E STATISTIC IS ROBUST AND ITS PLACEBO IS FLAT (pre-registration 16e; knee19e.py, results/knee19e.json). Per 1,000 isolated
   jumps, same-minus-opposite first legs early [0, 230) / reaction [230, 320): open 77.1 / 80.0, closed 34.5 / 87.0 (baseline |z| > 3,
   isolation 2 s: E 0.965 / 0.397); |z| > 4: E 0.985 / 0.377; isolation 4 s: E 0.979 / 0.414. Placebo (first legs shifted -3 s): -4.2 /
   -2.3 open and -2.7 / +1.0 closed per 1,000 jumps; shifted +3 s: 13.1 / 5.0 and 5.6 / 3.4 (a little momentum, an order of magnitude
   below the real early excess). The reaction to Binance is the same in both sessions (80 vs 87 per 1,000 jumps); only the early mass
   doubles.
17. ECONOMICS BY SESSION (D4; inline, results/econ19_session.json; on-chain fills of 10-09..22): Globex-open windows carry twice the
   volume (3,686 vs 1,844 shares per window, 2,520 vs 1,220 windows); trading PnL after fees per window is the same ($7.25 vs $7.41), so
   per share it halves (0.197 vs 0.402 c), and with the 50% taker-fee rebate the open-hour window earns more ($30.3 vs $17.2). Taker
   fills: -0.013 c per share after fees open vs +0.442 c closed; maker fills (lost races resting at the old ask): +1.246 c open vs +0.290
   c closed. Reading (not a test): the extra open-hour decisions add volume and rebate, and the remainders that rest after a race are
   much better placed in Globex hours, as expected if the move they race continues on Binance after a TradFi lead. Weekday activity is a
   confounder here.
18. SHAPE OF THE LEAD (knee19.json PSTH, open minus closed, per 1,000 jumps per 20-ms bin): a flat floor of +1.6..+3.2 over lags -200..0
   ms and +2.0..+3.8 over 0..140 ms, then a ramp of +5.3..+6.4 at 160-220 ms just before the reaction onset (240 ms), and about zero
   inside the reaction peak. Two components: a fixed latency advantage of a few tens of ms (the ramp: a source that sees the same move
   ~40-80 ms before Binance reaches London; CME Aurora -> London ~35-40 ms vs Tokyo -> London ~105 ms predicts ~65 ms), and moves that
   originate on the hidden venue and reach Binance hundreds of ms later (the floor). Both are what CME price discovery in Globex hours
   would look like; neither identifies the product.
19. PER DAY (diagnostic, knee19f.py, results/knee19f.json; open-hour E per capture day vs the frozen dc14 side in open / closed hours of
   the scored days): E 0.879 (10-19), 1.055 (10-20), 0.867 (10-21), 1.097 (10-22); dc14 open / closed 0.857 / 0.845 (10-20), 0.837 / 0.859
   (10-21), 0.814 / 0.876 (10-22). The iteration-18 '10-22 anomaly' day has the highest pre-Binance share and the largest open-vs-closed
   side gap (6.2 points), but 10-20 is high on E with the best side: three days, inconclusive.
20. PRE-REGISTRATION 20 RUNNER (code/dst20.py): builds E per CST-calendar cell from post17-style block records (RE16_SCRATCH=<BLOCK_DIR>
   python post17.py A B, one directory per development block) and either data.binance.vision aggTrades (checksum verified) or the live
   lab's btc5m_bnspot2; self-tested on the 11-01 06-12 record with the live source (770 first legs, 366 isolated jumps, closed E 0.162 =
   oot19b; results/dst20_selftest_11-01_06-12.json). The aggTrades path is untested (no download this iteration).
