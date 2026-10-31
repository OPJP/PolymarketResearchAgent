# btc5m-bot: frozen rule (iteration 3)

Code: `code/final_rule.py` (`evaluate(start_ts, end_ts) -> dict`, constants `USE_VENUES = True`,
`SIX_SERIES = True`). Models, all trained on BUILD only (2026-10-09 .. 2026-10-16 00:00 UTC, 2,016 windows;
negatives subsampled to 30% with weight 1/0.3; nothing fitted on VALIDATE or the holdout):

- `code/model_it3s_all_y.txt` (primary presence score), `..._yT.txt` (taker fills), `..._yM.txt` (maker fills)
- `code/model_it3s_side.txt`: side model (one row per second where the cluster bought exactly one outcome)
- `code/model_it3s_all_own_y.txt`: secondary score with own state (cluster inventory)
- `code/model_it2_market_only_y.txt`: co-occurrence baseline (market activity only, no reference feed)
- `code/model_it2_spot_tape_y.txt`: the iteration-2 rule, reported for comparison

Helpers: `cells.py`, `tape_feats.py`, `spot.py`, `rpc.py`, `build_cells_day.py`, `fetch_tapes2.py`, `ofi.py`,
`fut_cells.py`, `venue_cells.py`, `venue_cells2.py`. `evaluate` downloads every archive it needs (Binance futures and
spot aggTrades, OKX swap and spot, Bybit perp and spot daily trade files; tested against the development cache, byte
for byte the same trades) and, on a development period (end <= H), never loads a file that extends past H.

## What the rule says the bot does (mechanism as decoded so far)

1. Universe: every BTC 5-minute Up/Down window, all three wallets in the same windows. Activity at rel 2..~270 s,
   prices 0.12-0.88.
2. One order type: BUY-only limit orders priced at the current best ask of the outcome it wants, full sizes 30 / 50 /
   60 / 100 shares (60 until 2026-10-12, then mostly 30). 72% fill completely as taker, 12% partly (partial fills of
   5..25 shares, because makers rest in multiples of 5) and rest at the same price, 16% rest entirely (mostly lost
   races against other latency takers).
3. Trigger and side: a move of BTC on ANY of several exchanges. The side follows the move of the last ~2 s before
   its information horizon (about 1-2 s before the block): the strongest single features are the mean and the
   largest 2-s move across Binance USD-M futures, OKX swap, Bybit perp, Binance spot, Bybit spot and OKX spot. When
   Binance is flat but Bybit moved >= 0.5 bp, the bot buys in Bybit's direction 82% of the time (OKX 75%). Side
   accuracy rises with the largest venue move: 62% when no venue moved (26% of its one-sided seconds), 76% at
   0.5-1 bp, 80% at 1-2 bp, 84% at 2-5 bp.
4. Economics by regime (iteration 2, Binance-only split): after a visible Binance move (~1/3 of taker orders) +3.1 c
   gross, +1.6 c net per share; the other 2/3 +0.6 c gross, about -0.1 c with a 50% fee rebate. Much of that
   second group is now explained as reactions to other venues' small moves.
5. The three wallets are parallel instances of one strategy (DS 58%, GF 34%, XM 8% of VALIDATE dollars).

Distilled explicit rule (VALIDATE, `results_trigger_rule_iter3.json`): side = the sign of the largest 2-s move
among the six series (PIT). Accuracy 69.1% on all one-sided seconds (97% have some move), 80.4% on the 46% with a
move >= 0.5 bp, 82.8% at >= 1 bp. As a presence trigger (move toward o >= 0.5 bp, ask in [0.12, 0.88]): recall
33% at lift 3.0. The frozen models below add tape context and the seconds without a venue move.

## The frozen score

For each cell (window, outcome o, second s), features from public data available before s, no own state:

- Binance spot 1-s closes of seconds <= s-2 (returns toward o over 1..60 s, largest 1-s moves, sigma, z and fair
  value with the 60-s TWAP strike, time in the window);
- Binance USD-M futures aggTrades with T < (s-1)*1000 ms: moves over 0.25..10 s, order-flow imbalance, trade count,
  trade age, futures move since the last Polymarket print, basis-adjusted futures fair value and its gaps;
- OKX swap, Bybit perp, Binance spot aggTrades, Bybit spot, OKX spot trades with T < (s-1)*1000 ms: moves over
  0.5..10 s, OFI, age, count; composites: mean and largest move over 1-5 s, number of series moving each way, and the
  largest / mean move since the last Polymarket print;
- other traders' data-api taker prints with block ts <= s-1 (cluster prints and prints in transactions where a
  cluster order was the maker removed): implied ask/bid and ages, last price, VWAP, print counts, flow, volume,
  gaps, spread, recent changes.

Presence: `p = model_it3s_all_y`; a cell is flagged at `p >= 0.30` (fixed in iteration 1). Side in a second:
Up if `model_it3s_side >= 0.5`. Price: last implied ask of the chosen outcome. Selection (print level):
`score = 2*1[size in {30,50,60,100}] + 1[size in {5,10,15,20,25}] + p`, flag = full size OR (partial size AND
`p >= 0.30`). Outcome proxy (primary, chosen on VALIDATE): per second the expected volume `(p_up + p_down) x 30`
shares split by the side model, bought at the last implied ask.

## VALIDATE metrics (2026-10-16..23, all 2,016 windows, 1.21M cells)

| metric | VALIDATE | target |
|---|---|---|
| presence AUC, any fill, no own state (PRIMARY) | **0.9095** (it2 rule 0.8957; futures only 0.9038; three venues 0.9082) | >= 0.85 (met) |
| co-occurrence baseline (market activity only) | 0.8889 (gain +0.021) | |
| presence AUC taker / maker | 0.914 / 0.882 | |
| presence AUC per wallet GF / XM / DS | 0.908 / 0.924 / 0.897 | |
| at p >= 0.30: recall / lift / flagged share | 60.8% / 4.29 / 14.2% (p ~ 0) | |
| presence AUC WITH own state (secondary) | 0.921 | |
| side accuracy, one-sided seconds (n = 90,170) | **73.2%** (taker 75.2%) | >= 80% (not met) |
| side baselines: market-only model / favourite | 63.2% / 45.9% (McNemar p ~ 0) | |
| side: futures-only model / it2 rule | 70.3% / 67.1% | |
| side by largest six-series 3-s move: <= 0.1 / 0.5-1 / 1-2 / 2-5 bp | 62.2% / 76.2% / 80.3% / 83.7% | |
| side in Binance-flat seconds (50%) / moving | 67.1% / 79.7% | |
| selection, all 2.74M in-window taker prints (cluster 5.4%): pooled / within-window AUC | **0.866** / 0.860 | >= 0.80 (met) |
| selection at the pre-registered flag | **recall 67.7% at lift 4.65** (p ~ 0) | recall >= 50% at lift >= 3 (met) |
| selection co-occurrence baseline (size classes + market-only cell score) | 0.852 / 0.845; recall 64.1% at lift 4.78 | |
| per-window PnL correlation, primary proxy (soft_side) | 0.436 (Spearman 0.418); soft 0.412; futures-only soft 0.442 | >= 0.5 (not met) |
| net-position correlation rule vs cluster | 0.451 (cluster PnL vs its own net position x outcome: 0.885) | |
| rule proxy return / cluster before rebates | -0.45% / +0.17% | |
| taker price within one tick of the last implied ask (last 2 VALIDATE hours) | 53.2% | |

End-to-end check `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours): presence 0.889 (baseline 0.869),
side 72.2%, selection AUC 0.881 with recall 71.4% at lift 4.59, PnL correlation 0.454 (soft_side).

Files: `results_iter3_models.json` (futures), `results_iter3_venues.json`, `results_iter3_six.json`,
`results_selection_iter3.json`, `results_outcome_iter3_{fut,six}.json`, `results_fut_leadlag_iter3.json`,
`results_venues_iter3.json`, `results_wall_test_iter3*.json`, `results_side_by_composite_move_iter3.json`.

## Why it works

- Who pays it: makers whose quotes lag the BTC price. 92% of the makers it hits are resting BUY orders on the
  complementary outcome; buying Up at the Up ask is selling Down to a Down bidder who has not yet repriced after a
  move. The bot watches several exchanges at once and fires on whichever moves first, so it also picks off quotes
  that track only Binance (when Bybit or OKX moves first, it is right 75-82% of the time). That is latency
  arbitrage, worth about +3 c/share gross after a clear move.
- What it is mostly paid for in the study weeks: the fee rebate. Its taker volume pays ~1.5 c/share in fees; with a
  50% rebate the large volume of small-move orders roughly breaks even, and the rebate on all of it (~$30k in the
  VALIDATE week against ~$4k of trading profit before rebates) is most of the profit.
- Its resting remainders (lost races) earn about +2.4 c/share after moves: no fee, and the limit sits at a price
  that was the ask just before a move that continued.

## Can a normal user deploy it now

- Dependencies: low-latency feeds from several exchanges (Binance futures and spot, Bybit, OKX; all public
  websockets), order submission to the Polymarket CLOB within about 1-2 s of a move (it races other latency takers
  and often loses: most of its orders follow another trader taking the same price within 5 s), capital for
  thousands of 30-share orders a day (~$2.5M bought per week across the three wallets), and above all a high
  fee-rebate tier: without the 50% rebate the small-move volume loses ~0.9 c/share and the whole book is near zero
  (+0.17% before rebates in VALIDATE).
- Do the conditions still hold before H? Yes: activity, the fee formula (0.07 p(1-p)), the order sizes and the
  latency edge are stable through 2026-10-22, and all six exchange feeds are public and archived daily.
- What a replicator with a normal connection and computer would earn: the feeds are free, but the edge sits in the
  1-3 s after a move, against co-located racers. With >= 2 s latency and strict fills, the iteration-1 executable
  version lost 5-9% on 2,011 unseen windows; this rule's proxy (no queue priority) returns -0.45% before rebates.
  A normal user without the rebate tier should expect to lose money; with the rebate tier and a fast multi-venue
  feed the small-move volume roughly breaks even and the latency part pays.

## Known limitations

- About a quarter of its one-sided seconds have no visible trigger on any of the six trade feeds (side accuracy 62%
  there); Kraken XBT/USD does not explain them either (49.9% agreement in those seconds, 6 sampled VALIDATE hours).
  Untested: Coinbase (no archive; trade-id paging needs a post-H anchor), Deribit, order books (no
  public sub-second history: the Binance futures bookTicker archive is not published for 2026-10), and the
  Polymarket order book (no public history for the development period).
- OKX archives are UTC+8 days; on development periods ending at H the last 8 h have no OKX data (the 10-23 file
  extends past H). On the holdout the examiner gets full OKX coverage; the model handles missing venues (NaN).
- The outcome metric is a proxy (no queue/fill simulation).
- The size rule depends on the bot keeping its order sizes ({30, 50, 60, 100} full, multiples of 5 partial); a size
  change in the holdout would lower the selection metric (the cell score alone gives ~0.69).
- Tape features need data-api tapes (`evaluate` fetches them, [start-600, end+5] per window).
