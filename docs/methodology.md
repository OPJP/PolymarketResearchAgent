# Methodology

This document fixes how a Polymarket wallet is judged. Thresholds were set
before any wallet was examined; the one change made after first results was a
bug fix in the deflated Sharpe ratio (see "Changes after first run").

## Data sources

| Source | Used for | Notes |
| --- | --- | --- |
| `data-api.polymarket.com/v2/leaderboard` | Top 500 wallets by monthly PnL | Snapshot saved in `research/stage_a/leaderboard_snapshot.json` |
| `data-api.polymarket.com/v2/user-pnl` | Daily mark-to-market PnL per wallet, split into trading PnL, fees, maker/taker rebates, rewards | Primary series for significance tests |
| `data-api.polymarket.com/activity` | Every fill, split, merge, redeem and income row of a wallet | Read with timestamp cursors (offset is capped at 5,000) |
| `data-api.polymarket.com/trades` | Public tape of a market (taker rows and maker rows) | Liquidity that existed at each moment |
| `gamma-api.polymarket.com/markets` | Market metadata: window start/end, game start, outcomes, fee schedule, resolution | Static and post-hoc fields are separated |
| Polygon RPC (`polygon.drpc.org`) | Transaction receipts | `OrderFilled` events of CTF Exchange V1 and Exchange V2 decoded to confirm fills and the wallet's maker/taker role |
| Kraken public trades | Per-second BTC/ETH/SOL/XRP spot | Binance and Bybit are geo-blocked from the research host |
| Coinbase / OKX candles | Minute spot (registered external sources) | |
| ESPN public site API | Play-by-play with wall-clock times and win probability | NFL, NBA, college football, MLB, NHL |
| Polymarket docs | Fee, rebate, reward and taker-delay rules | Policy dependence of each strategy |

Any public JSON time series can be added with `register_external_source`
(URL template, records path, time/value fields, and an honest
availability lag).

## Stage A1: is the wallet's profit real? (no reverse engineering)

Daily PnL = day-over-day change of `economic_pnl` (realized + unrealized
market PnL + rebates + rewards + yield). The final partial day is dropped.

Selection bias: the leaderboard ranks wallets on the last ~30 days, which
guarantees that window looks good. Significance is therefore tested on the
history **before** the ranking window, and corrected for testing 500 wallets.

| Criterion | Rule |
| --- | --- |
| Enough independent history | >= 60 days before the ranking window |
| Significant pre-selection profit | Newey-West HAC one-sided t-test, Holm-adjusted over all 500 wallets, p < 0.05 |
| Robust to autocorrelation | Stationary block bootstrap on pre-selection days, p < 0.01 |
| Not the luckiest of 500 | Deflated Sharpe ratio > 0.95 (null: max of 500 noise wallets, SR std 1/sqrt(T-1)) |
| Net profit above $50k/month | Last 30 days > $50k and median of the last six 30-day blocks > $50k |
| Constant returns (low std) | Annualized daily Sharpe >= 3, >= 75% positive weeks, >= 80% positive 30-day blocks |

The leaderboard's own PnL figure is recorded but not used: for some wallets it
disagrees sharply with the mark-to-market series (`lb_series_inconsistent`).

## Stage A2: capital, return on capital, on-chain verification

* The wallet's fills (30 days plus a 7-day warm-up) are replayed into a
  position ledger. Capital at risk is the cost basis of open positions; a
  position stops counting when sold, merged, redeemed or when its market
  resolves. **High % profit** = 30-day PnL / peak capital at risk >= 10%.
* 200 random fills are matched to Polygon receipts. A fill is confirmed when
  the wallet's decoded `OrderFilled` shares for that token in that transaction
  equal the API size (0.5% tolerance). The same events give the wallet's role:
  for both exchange versions the taker's own order emits an `OrderFilled`
  whose taker field is the exchange contract.

## Stage B: profile

Per market: shares and average price of each outcome bought, complete pairs,
pair cost, locked PnL (`pairs * (1 - avg_up - avg_down)`), directional residual
PnL, win rates, price calibration (win rate of bought shares by price bucket),
timing relative to the window or game start, and income split (fees, maker
and taker rebates, rewards). This decides which hypothesis family to test.

## Stage C: reverse engineering

Every hypothesis is a decision rule evaluated through the point-in-time
layer and tested walk-forward:

* **FIT** period (older): chooses the rule's free parameters (latency, threshold, quote offset, reaction window).
* **TEST** period (newer, untouched): measures agreement with the wallet and backtest PnL.

### Matching the wallet (decision level)

The population is every comparable decision available in the market: every
taker buy on the tape (for taker strategies), every passive buy (for maker
strategies), or every in-play fill around game events (for sports). The
wallet's own decisions are labelled. The rule's score must predict which ones
are the wallet's.

* AUC of the score on TEST, compared with a **permutation null** that shifts
  the external clock (spot path or play-by-play timeline) by 5 minutes to
  6 hours. This keeps every marginal distribution and autocorrelation and only
  destroys the timing link the hypothesis claims. Pass: permutation p < 0.01.
* Decision metrics at the fitted threshold (precision, recall, MCC, lift).
* For sports: reaction share, direction agreement after scoring plays, and the
  lag histogram of the wallet's fills relative to ESPN wall-clock times.

### Backtesting the rule

* Taker rules buy at observed taker prints (liquidity that traded) when the
  rule fires using information available `latency` seconds earlier; fees use
  the market's own `feeSchedule` (`fee = shares * rate * p * (1 - p)`).
* Maker rules rest bids and are filled only by later taker prints that trade
  **through** the bid (a taker sell below it, or a complementary taker buy of
  the other outcome above `1 - bid`). Rebates are excluded.
* Where no public event feed exists (esports, tennis), the maker
  replicability study backtests a slow two-sided maker whose fair value is
  the last public print known `latency` seconds late, with the same
  trade-through fills, on the wallet's own markets (fit/test split by market
  start time). It answers whether the market-making economics survive for a
  replicator without the wallet's speed or data.
* Settlement uses the resolved payout, which decision code never sees.
* Significance: HAC t-test and block bootstrap over per-window or per-game
  PnL. Pass: p < 0.05 on TEST.
* Latency degradation (+1 to +60 s) and queue-share sensitivity show what a
  slower or smaller replicator would get.
* The wallet's own fills on the same TEST markets are scored the same way
  ("original strategy" outcome) for comparison.

### No future data

1. Every record has `event_ts` and `available_ts`; a strategy at time `t`
   only sees `available_ts <= t` through `PITView`, which raises
   `LookAheadError` otherwise.
2. A per-second spot value is available one second after its second ends; a
   minute candle one minute after its open.
3. Market metadata exposes only listing-time fields to decisions; outcome
   prices, closed time, volume and resolution status are post-hoc.
4. Vectorized fast paths are audited on every study: sampled fair values are
   recomputed through `PITView` and again on a store physically truncated at
   the decision time; any difference fails the study.
5. Parameters are fitted on FIT only; nothing measured on TEST feeds back.
6. Unit tests corrupt all data after each decision time and require identical
   decisions.

## Replicability and persistence

* **Replicable**: the edge must survive at a latency a normal connection
  achieves (>= 1-2 s for decision plus order), without private data feeds,
  without self-trading between accounts, and without a fee-rebate tier the
  replicator would not hold (Polymarket's taker rebate tiers run from 0% to 50%
  of fees by 30-day weighted volume).
* **Conditions persist**: the wallet's last 30 days are significant on their
  own (HAC one-sided p < 0.05), mean PnL has not significantly declined vs.
  earlier days (p > 0.05), there is no significant negative trend (p > 0.05),
  and the policy the strategy relies on (fees, rebates, rewards, market
  listings, taker delay) is still in force. A CUSUM break is reported but only
  counts against the wallet when the break is a decline. Results:
  `research/stage_a/persistence_a1_survivors.json`.

## Changes after first run

* Deflated Sharpe ratio: the first implementation used the cross-sectional
  std of observed Sharpe ratios (which includes real skill and short-history
  noise) as the null dispersion. That made the benchmark arbitrarily strict
  (an annualized Sharpe of 9.6 over 477 days scored 1e-7). The null now uses
  the sampling std of a single Sharpe estimate, 1/sqrt(T-1). Thresholds were
  not changed. Effect: 5 -> 11 wallets passed stage A1.
