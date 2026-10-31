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
