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
