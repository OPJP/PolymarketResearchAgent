# btc5m-bot: frozen rule (iteration 2)

Code: `code/final_rule.py` (`evaluate(start_ts, end_ts) -> dict`). Models, all trained on BUILD only
(2026-10-09 .. 2026-10-16 00:00 UTC, 2,016 windows, every window with a tape; negatives subsampled to 30% with
weight 1/0.3; nothing fitted on VALIDATE or the holdout):

- `code/model_it2_spot_tape_y.txt` (primary score), `..._yT.txt` (taker fills), `..._yM.txt` (maker fills)
- `code/model_it2_market_only_y.txt`: co-occurrence baseline (market activity only, no Binance)
- `code/model_it2_spot_tape_own_y.txt`: secondary score with own state (cluster inventory)

Helpers: `cells.py`, `tape_feats.py`, `spot.py`, `rpc.py`, `build_cells_day.py` (`add_inv`, `add_extra`),
`fetch_tapes2.py` (`fetch_one`). Iteration 1's model files were lost with the cloud machine; iteration 2 retrained
the same model family locally (plus five PIT price-change features) and re-measured everything.

## What the rule says the bot does (mechanism as decoded so far)

1. Universe: every BTC 5-minute Up/Down window (all three wallets in the same windows). Activity at rel 2..~270 s,
   prices 0.12-0.88.
2. One order type: BUY-only limit orders of a fixed share size (60 shares until 2026-10-12, then 30; 50 on some
   days), priced at the current best ask of the outcome it wants. 72% fill completely as taker, 12% fill partly and
   rest at the same price, 16% rest entirely (mostly lost races: another taker took that ask first).
3. Two regimes with the same order type (new in iteration 2):
   - MOVING (~33% of taker orders): Binance BTCUSDT moved >= 0.5 bp in the visible 3 s before the order. Latency
     taking: the side follows the move of seconds s-3..s-2 before the block (62-63% agreement per second, 80-84%
     when the 3-s move is 1-5 bp). Gross edge +3.1 c/share, fee 1.5 c, net +1.6 c/share (+3.3%).
   - QUIET (~67% of taker orders): no visible Binance move. Side is almost unrelated to every public signal I could
     get (fair-value gap, other traders' prints, own inventory, Binance spot at 1 s or 1 ms resolution, order flow;
     Binance futures adds a few points). Gross edge only +0.6 c/share, fee 1.5 c: -0.9 c/share before rebates,
     about -0.1 c with a 50% fee rebate. This is rebate-driven volume with a weak side signal that predicts the
     next Binance moves (53-54% agreement with the move 1-10 s AFTER the order on a flat past; placebo 50%).
4. The bot's information horizon ends about 1 s before the block timestamp (the Binance move in the last second
   before the block barely matters: 57% overall, 52% in quiet periods), so the brief's 1-s availability lag is not
   what limits the rule.
5. The three wallets are parallel instances of one strategy (DS 58%, GF 34%, XM 8% of VALIDATE dollars; stable
   shares per day; same edge profile).

## The frozen score

For each cell (window, outcome o, second s), `p = model_it2_spot_tape_y(features)`, features from public data
available before s, no own state:

- Binance 1-s closes of seconds <= s-2: signed returns toward o over 1..60 s (raw and vol-normalised), largest
  favourable/adverse 1-s moves in the last 3 and 10 s, 30-min sigma, z-score and fair value of o (60-s TWAP strike),
  seconds elapsed/remaining.
- Other traders' data-api taker prints with block ts <= s-1 (cluster prints and every print in a transaction where
  a cluster order was the maker removed): last implied ask/bid of o and their ages, last price, VWAP 10/30 s, print
  counts 1/2/5/30 s, signed flow, 30-s volume, Binance move since the last print, FV-minus-market gaps, implied
  spread, and (new) the 5/10/30-s change of the last price and the 5/10-s change of the FV-minus-price gap.

A cell is flagged when `p >= 0.30` (fixed in iteration 1). Predicted side in a second = the outcome with the higher
`p`. Predicted taker price = last implied ask of that outcome. Selection (print level): a taker print scores
`1[size in {30, 50, 60} shares] + p` of its cell; it is flagged at score >= 1.30 (size rule and p >= 0.30). Outcome proxy: the rule buys `p * 30` shares at the
last implied ask in every cell (soft proxy, chosen on VALIDATE over the iteration-1 hard proxy).

## VALIDATE metrics (2026-10-16..23, all 2,016 windows, 1.21M cells)

| metric | VALIDATE | target |
|---|---|---|
| presence AUC, any fill, no own state (PRIMARY) | **0.896** | >= 0.85 (met) |
| co-occurrence baseline (market activity only, same model family) | 0.889 (gain +0.007) | |
| presence AUC taker / maker | 0.897 / 0.875 | |
| presence AUC per wallet GF / XM / DS | 0.892 / 0.909 / 0.884 | |
| at p >= 0.30: recall / lift / flagged share | 56.4% / 3.89 / 14.5% (p~0); baseline 50.3% / 3.81 | |
| spot-only model | 0.799 | |
| presence AUC WITH own state (secondary) | 0.909 | |
| side accuracy, one-sided seconds (n=90,170) | 67.1% (taker 67.1%, maker 68.2%) | >= 80% (not met) |
| side baselines: market-only model / favourite | 63.9% / 45.9% (McNemar p ~ 1e-99 vs market-only) | |
| side with own state | 67.5% | |
| side by visible 3-s Binance move 0 / 0.5-1 / 1-2 / 2-5 bp | 60.1% / 77.2% / 80.7% / 83.5% | |
| per-window PnL correlation (soft proxy) | 0.399 (Spearman 0.363); hard proxy 0.316 | >= 0.5 (not met) |
| net-position correlation rule vs cluster | 0.415 | |
| rule return (proxy, buys at last implied ask) / cluster before rebates | -2.8% / +0.17% | |
| selection among all 2.74M in-window taker prints (cluster 5.4%): size rule + cell score, pooled / within-window AUC | **0.837** / 0.825 (cell score alone 0.691) | >= 0.80 (met) |
| selection co-occurrence baseline (size rule + market-only cell score) | 0.827 (gain +0.010; market-only cell score alone 0.676) | |
| selection at the pre-registered flag (size rule AND p >= 0.30) | recall 31.3% at lift 12.7 (p~0) | recall >= 50% at lift >= 3 (not met) |
| selection, size rule alone (print size in {30, 50, 60}) | recall 49.8% at lift 10.2 (flags 4.9% of prints) | |
| taker price within one tick of last implied ask (iteration 1; 53.2% on the last 2 VALIDATE hours) | 49.2% | |

Files: `results_presence_iter2.json`, `results_side_iter2.json`, `results_outcome_iter2.json`,
`results_order_leadlag_iter2.json`, `results_edge_decomposition_iter2.json`, `results_futures_leadlag_iter2.json`,
`results_ofi_side_iter2.json`, `results_selection_print_iter2.json`.

## Why it works

- Who pays it: the makers on the other side of its taker buys, mostly resting BUY orders on the complementary
  outcome (92% of hits are mints). After a Binance move those bids are stale: buying Up at the Up ask is selling
  Down to a Down bidder whose bid has not caught up. That is classic latency arbitrage against slow quoters, worth
  about +3 c/share gross on the third of its orders that follow a visible move.
- What it is mostly paid for in the study weeks: the fee rebate. Its taker volume pays ~1.5 c/share in fees; with a
  50% rebate the large "quiet" volume roughly breaks even, and the rebate on all of it (~$30k in the VALIDATE week
  against ~$4k of trading profit before rebates) is most of the profit. The quiet orders' weak side signal (+0.6 c
  gross) is just enough to make the volume free.
- Its resting remainders (lost races) earn +2.4 c/share when placed after a move and ~0 otherwise: no fee, and the
  limit sits at a price that was the ask a moment before a move that continued.

## Can a normal user deploy it now

- Dependencies: a co-located or low-latency Binance feed (the edge sits in the 1-3 s after a move and competes with
  other latency takers who often win: 69-83% of its orders follow another trader taking the same price within 5 s),
  fast order submission to the Polymarket CLOB, enough capital for thousands of 30-share orders a day (~$2.5M bought
  per week across the three wallets), and above all a high fee-rebate tier: without the 50% rebate the quiet volume
  loses ~0.9 c/share (-1.8%) and the whole book is near zero (+0.17% before rebates in VALIDATE).
- Do the conditions still hold before H? Yes in the latest data: activity, fee formula (0.07 p(1-p)) and the
  latency edge are stable through 2026-10-22; the moving-regime edge is +1.6 c/share net of fees in VALIDATE.
- What a replicator with a normal connection and computer would earn: the latency part needs to beat co-racers that
  act within ~1-2 s; a normal home setup (>= 2 s latency, strict fills) loses: the iteration-1 frozen executable
  version lost 5-9% on 2,011 unseen windows, and the rule proxy here returns -2.8% (buys at the last observed ask
  without queue priority). A normal user without the rebate tier should expect to lose money.

## Known limitations

- Not frozen yet: PIT Binance USD-M futures features raise VALIDATE side accuracy to 69.8% (taker 70.7%) in a
  side model trained on 4 BUILD days (`results_futures_side_iter2.json`); the frozen rule still uses spot only.

- The side decision in quiet periods (2/3 of orders) is not decoded; candidates not yet tested: Coinbase / Chainlink
  Data Streams (the resolution source) and the Polymarket order book itself (no public history for the development
  period; a live recording would be holdout-period data).
- The outcome metric is a proxy (no queue/fill simulation). The price metric was re-measured only on the last two
  VALIDATE hours (53.2%); `evaluate` computes it.
- The size rule depends on the bot keeping its order sizes in {30, 50, 60} shares; a size change in the holdout
  would lower the selection metric (the cell score alone gives 0.69).
- Tape features need data-api tapes (`evaluate` fetches them, [start-600, end+5] per window).
