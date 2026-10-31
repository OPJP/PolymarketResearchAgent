# btc5m-bot: frozen rule (iteration 4)

Code: `code/final_rule.py` (`evaluate(start_ts, end_ts) -> dict`, constants `USE_VENUES = True`, `SIX_SERIES = True`,
`USE_ALTS = True`, `ALT_SET = "four"`). Models, all trained on BUILD only (2026-10-09 .. 2026-10-16 00:00 UTC, 2,016
windows; negatives subsampled to 30% with weight 1/0.3; nothing fitted on VALIDATE or the holdout):

- `code/model_it4b_all_y.txt` (primary presence score), `..._yT.txt` (taker fills), `..._yM.txt` (maker fills)
- `code/model_it4b_side_lag.txt`: side model (one row per second where the cluster bought exactly one outcome), with
  explicit lagged segments [s-3, s-2) and [s-4, s-3) of the ten series (`alt_cells.lag_feats`); `model_it4b_side.txt` is
  the same without them (75.3%)
- `code/model_it4b_shares.txt`: expected cluster shares bought per cell (primary outcome proxy, new in iteration 4)
- `code/model_it4b_netflow.txt`: signed net share flow of the cluster per second (secondary outcome proxy, new in iteration 4)
- `code/model_it4b_all_own_y.txt`: secondary score with own state (cluster inventory)
- `code/model_it2_market_only_y.txt`: co-occurrence baseline (market activity only, no reference feed)
- `code/model_it2_spot_tape_y.txt`: the iteration-2 rule, reported for comparison

Helpers: `cells.py`, `tape_feats.py`, `spot.py`, `rpc.py`, `build_cells_day.py`, `fetch_tapes2.py`, `ofi.py`,
`fut_cells.py`, `venue_cells.py`, `venue_cells2.py`, `alt_cells.py` (frozen cross-asset slopes `BETA`, measured on BUILD).
`evaluate` downloads every archive it needs (Binance BTC futures and spot aggTrades, OKX swap and spot, Bybit perp and
spot, and the Binance ETH / SOL / XRP / DOGE perpetual aggTrades; Binance archives are checksum-verified) and, on a
development period (end <= H), never loads a file that extends past H.

## What the rule says the bot does (mechanism as decoded so far)

1. Universe: every BTC 5-minute Up/Down window, all three wallets in the same windows. Activity at rel 2..~270 s,
   prices 0.12-0.88.
2. One order type: BUY-only limit orders priced at the current best ask of the outcome it wants, full sizes 30 / 50 /
   60 / 100 shares (60 until 2026-10-12, then mostly 30). 72% fill completely as taker, 12% partly (partial fills of
   5..25 shares, because makers rest in multiples of 5) and rest at the same price, 16% rest entirely (mostly lost
   races against other latency takers).
3. Trigger and side: a short-horizon forecast of BTC built from many public trade feeds. The side follows the move of
   the last ~2-3 s before its information horizon (about 1-2 s before the block) on whichever feed moved: Binance USD-M
   futures, OKX swap, Bybit perp, Binance / Bybit / OKX spot, and (new in iteration 4) the ETH perpetual and other alt
   perpetuals (SOL, XRP, DOGE). ETH leads BTC at sub-second horizons (corr of 0.5-s returns ETH -> BTC 0.218 vs
   BTC -> ETH 0.120), and the bot uses it: when no BTC feed moved but ETH moved >= 1 bp, it buys in ETH's direction 79% of
   the time. Its side agrees most with the ETH move in [s-3, s-2), the same lag as for the BTC venues.
4. Economics by regime (iteration 2, Binance-only split): after a visible Binance move (~1/3 of taker orders) +3.1 c
   gross, +1.6 c net per share; the other 2/3 +0.6 c gross, about -0.1 c with a 50% fee rebate. Much of that
   second group is reactions to other venues' and other coins' small moves.
5. The three wallets are parallel instances of one strategy (DS 58%, GF 34%, XM 8% of VALIDATE dollars).

Distilled explicit rule (iteration 3, `results_trigger_rule_iter3.json`): side = the sign of the largest 2-s move
among the six BTC series (PIT): 69.1% on all one-sided seconds, 80.4% on the 46% with a move >= 0.5 bp. Iteration-4
addition: when no BTC series moved, follow the ETH perp's 3-s move (79% when |move| >= 1 bp).

## The frozen score

For each cell (window, outcome o, second s), features from public data available before s, no own state:

- Binance spot 1-s closes of seconds <= s-2 (returns toward o over 1..60 s, largest 1-s moves, sigma, z and fair
  value with the 60-s TWAP strike, time in the window);
- Binance USD-M futures aggTrades with T < (s-1)*1000 ms: moves over 0.25..10 s, order-flow imbalance, trade count,
  trade age, futures move since the last Polymarket print, basis-adjusted futures fair value and its gaps;
- OKX swap, Bybit perp, Binance spot aggTrades, Bybit spot, OKX spot trades with T < (s-1)*1000 ms: moves over
  0.5..10 s, OFI, age, count; six-series composites (mean and largest move over 1-5 s, number of series moving each
  way, largest / mean move since the last Polymarket print);
- Binance ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT perpetual aggTrades with T < (s-1)*1000 ms: moves over 0.5..10 s, OFI,
  age, count, the alt move not yet seen in BTC (alt move - BETA x six-series mean move; BETA from BUILD: ETH 1.235,
  SOL 1.508, XRP 1.376, DOGE 1.428), move since the last Polymarket print, and BTC-equivalent alt composites;
- other traders' data-api taker prints with block ts <= s-1 (cluster prints and prints in transactions where a
  cluster order was the maker removed): implied ask/bid and ages, last price, VWAP, print counts, flow, volume,
  gaps, spread, recent changes.

Presence: `p = model_it4b_all_y`; a cell is flagged at `p >= 0.30` (fixed in iteration 1). Side in a second:
Up if `model_it4b_side_lag >= 0.5`. Price: last implied ask of the chosen outcome. Selection (print level):
`score = 2*1[size in {30,50,60,100}] + 1[size in {5,10,15,20,25}] + p`, flag = full size OR (partial size AND
`p >= 0.30`). Outcome proxy (primary, chosen on VALIDATE in iteration 4): in every cell buy the predicted number of
shares the cluster buys there (`model_it4b_shares`, a regression on the presence features) at the last implied ask.
Secondary: the predicted signed net share flow per second (`model_it4b_netflow`) and soft_side.

## VALIDATE metrics (2026-10-16..23, all 2,016 windows, 1.21M cells)

| metric | VALIDATE | target |
|---|---|---|
| presence AUC, any fill, no own state (PRIMARY) | **0.9132** (it3s 0.9095; ETH only 0.9127; it2 0.8957) | >= 0.85 (met) |
| co-occurrence baseline (market activity only) | 0.8889 (gain +0.024) | |
| presence AUC taker / maker | 0.919 / 0.883 | |
| presence AUC per wallet GF / XM / DS | 0.912 / 0.924 / 0.901 | |
| at p >= 0.30: recall / lift / flagged share | 64.0% / 4.30 / 14.9% (p ~ 0) | |
| presence AUC WITH own state (secondary) | 0.924 | |
| side accuracy, one-sided seconds (n = 90,170) | **75.5%** (taker seconds 78.2%); without the lag segments 75.3% (McNemar p = 0.006) | >= 80% (not met) |
| side baselines: market-only model / favourite | 63.2% / 45.9% (McNemar p ~ 0) | |
| side: it3s rule (six BTC series) / ETH only | 73.2% / 75.0% (McNemar it4b vs it3s p ~ 2e-82) | |
| side in seconds with no six-series move (26%) / moving | 67.6% / 78.0% (model without lag segments) | |
| side in taker seconds with a visible move (60% of one-sided seconds) | 80.1% (ETH-only model) | |
| selection, all 2.74M in-window taker prints (cluster 5.4%): pooled / within-window AUC | **0.869** / 0.864 | >= 0.80 (met) |
| selection at the pre-registered flag | **recall 68.6% at lift 4.63** (p ~ 0) | recall >= 50% at lift >= 3 (met) |
| selection co-occurrence baseline (size classes + market-only cell score) | 0.852 / 0.845; recall 64.1% at lift 4.78 | |
| per-window PnL correlation, primary proxy (shares) | 0.439 (Spearman 0.414); netflow 0.434; soft_side 0.426; it3s soft_side 0.436 | >= 0.5 (not met) |
| net-position correlation rule vs cluster (shares) | 0.467 (netflow 0.458; oracle volume x model side would give 0.555) | |
| per-window total shares: rule vs cluster | 0.875 (presence-based volume 0.785) | |
| rule proxy return / cluster before rebates | -1.5% (shares; netflow +4.9%; no queue/fill check) / +0.17% | |
| STRICT-FILL backtest (latency >= 2 s, observed liquidity, capture 1.0) | $262k bought, -1.6% before rebates, +0.1% with a 50% fee rebate; per-window PnL corr 0.18 | |
| taker price within one tick of the last implied ask (last 2 VALIDATE hours) | 53.2% | |

End-to-end check `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 7.8 s from the local cache): presence
0.893 (baseline 0.869), side 74.1% (taker 75.5%; 1,183 seconds), selection AUC 0.884 with recall 72.4% at lift 4.57 (24 windows, so
the PnL correlations there are noisy: shares 0.39).

Files: `results_strict_backtest_iter4.json`, `results_iter4_models.json` (ETH), `results_iter4_models_four.json` (it4b), `results_selection_iter4_it4b.json`,
`results_outcome_iter4_it4b.json`, `results_outcome_iter4_shares.json`, `results_net_diag_iter4.json`, `results_eth_venues_iter4.json`, `results_side_lag_iter4.json`, `results_eth_iter4.json`, `results_alts_iter4.json`,
`results_eth_leadlag_iter4.json`, `results_coinbase_deribit_iter4.json`, `results_wall_test_iter4_val_side_it4b.json`.

## Why it works

- Who pays it: makers whose quotes lag the crypto price. 92% of the makers it hits are resting BUY orders on the
  complementary outcome; buying Up at the Up ask is selling Down to a Down bidder who has not yet repriced after a
  move. The bot forecasts BTC's next second from many feeds at once (BTC on six venues, and ETH and other coins, which
  lead BTC by a fraction of a second), so it also picks off quotes that track only Binance BTC. That is latency /
  cross-asset arbitrage, worth about +3 c/share gross after a clear move.
- What it is mostly paid for in the study weeks: the fee rebate. Its taker volume pays ~1.5 c/share in fees; with a
  50% rebate the large volume of small-move orders roughly breaks even, and the rebate on all of it (~$30k in the
  VALIDATE week against ~$4k of trading profit before rebates) is most of the profit.
- Its resting remainders (lost races) earn about +2.4 c/share after moves: no fee, and the limit sits at a price
  that was the ask just before a move that continued.

## Can a normal user deploy it now

- Dependencies: low-latency feeds from several exchanges and coins (Binance futures and spot, Bybit, OKX; ETH, SOL,
  XRP, DOGE perps; all public websockets), order submission to the Polymarket CLOB within about 1-2 s of a move (it
  races other latency takers and often loses: most of its orders follow another trader taking the same price within
  5 s), capital for thousands of 30-share orders a day (~$2.5M bought per week across the three wallets), and above
  all a high fee-rebate tier: without the 50% rebate the small-move volume loses ~0.9 c/share and the whole book is
  near zero (+0.17% before rebates in VALIDATE).
- Do the conditions still hold before H? Yes: activity, the fee formula (0.07 p(1-p)), the order sizes and the
  latency edge are stable through 2026-10-22, and all ten trade feeds are public and archived daily.
- What a replicator with a normal connection and computer would earn: the feeds are free, but the edge sits in the
  1-3 s after a move, against co-located racers. With >= 2 s latency and strict fills, the iteration-1 executable
  version lost 5-9% on 2,011 unseen windows. This rule under strict fills (`evaluate` -> outcome.strict_fill_backtest:
  30-share limits at the last ask, filled only against other traders' taker prints 2-4 s after the information
  horizon, an upper bound because it assumes we win every contested print) bought $262k on VALIDATE and lost 1.6%
  before rebates; with a 50% fee rebate it is about +0.1%. The no-queue proxies (shares -1.5%, netflow +4.9%) overstate
  what a slow replicator gets. A normal user
  without the rebate tier should expect to lose money; with the rebate tier and a fast multi-venue, multi-coin feed
  the small-move volume roughly breaks even and the latency part pays.

## Known limitations

- 18.7% of one-sided seconds have no visible move on the six BTC series or on ETH; side accuracy there is ~64%, and
  the bot's side still predicts the next 0-2 s BTC move at 53% (our model 51%; `results_wall_test_iter4_*.json`): a
  small residual of information not in any public trade archive tested (Kraken, Coinbase and Deribit add nothing for
  BTC; ETH on OKX swap, Binance spot and Bybit spot adds nothing beyond the Binance ETH perp).
  Untested: venue order books (no public sub-second history for 2026-10), the Polymarket order book (no public
  history for the development period).
- OKX archives are UTC+8 days; on development periods ending at H the last 8 h have no OKX data (the 10-23 file
  extends past H). On the holdout the examiner gets full OKX coverage; the models handle missing venues (NaN).
- The outcome metric is a proxy (no queue/fill simulation). The per-window net position is a small difference of
  large two-sided volumes (median |net| = 12% of gross), so volume errors limit the PnL correlation as much as side
  errors.
- The size rule depends on the bot keeping its order sizes ({30, 50, 60, 100} full, multiples of 5 partial); a size
  change in the holdout would lower the selection metric (the cell score alone gives ~0.69).
- Tape features need data-api tapes (`evaluate` fetches them, [start-600, end+5] per window).
