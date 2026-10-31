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
| Kraken public trades | Per-second BTC/ETH/SOL/XRP spot | Binance and Bybit REST APIs are geo-blocked from the research host |
| Binance public archive (`data.binance.vision`) | 1-second BTC/ETH klines per UTC day, SHA-256 checked | Published the next day; leads Kraken by about 1 s |
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
| Significant pre-selection profit | Newey-West HAC one-sided t-test (exact finite-sample reference, below), Holm-adjusted over all 500 wallets, p < 0.05 |
| Robust to autocorrelation | Stationary block bootstrap on pre-selection days, p < 0.01 (20,000 resamples when p is near the bar) |
| Not the luckiest of 500 | Deflated Sharpe ratio > 0.95 over the full history (null: max of 500 noise wallets, SR std 1/sqrt(T-1)); an undefined DSR fails |
| Net profit above $50k/month | Last 30 days > $50k and median of the last six 30-day blocks (fewer if the history is shorter) > $50k |
| Constant returns (low std) | Annualized daily Sharpe >= 3, >= 75% positive weeks, >= 80% positive 30-day blocks; weeks and blocks with no PnL on any day are dormancy and are left out of the shares |

The HAC t statistic is compared with its exact null distribution for iid
Gaussian data of the same length and lag count: T = Z / sqrt(Q), with Q a
weighted sum of chi-square(1) variables whose weights are the eigenvalues of
the demeaned Bartlett matrix, independent of Z, so P(T >= t) = E[Phi(-t
sqrt(Q))]. The t(n-1) reference used at first is too thin-tailed: at the
1e-4 level a Holm correction over 500 wallets needs, it rejected true nulls
3-50 times too often (more under autocorrelation or a left-skewed carry
distribution). The exact reference holds size under iid data; heavy left
skew ("rare large loss not yet seen") is a residual risk no sample test
removes, which is one reason the bootstrap and deflated Sharpe gates also
apply.

The leaderboard's own PnL figure is recorded but not used: for some wallets it
disagrees sharply with the mark-to-market series (`lb_series_inconsistent`).

## Stage A2: capital, return on capital, on-chain verification

* The wallet's fills (30 days plus a 7-day warm-up) are replayed into a
  position ledger. Capital at risk is the cost basis of open positions; a
  position stops counting when sold, merged, redeemed or when its market
  resolves. Complete sets created by splits pay exactly $1 whatever the
  outcome and merge back at any time, so they are not capital at risk (wallets
  park idle cash in them for holding yield); the peak including them is
  reported too. **High % profit** = 30-day PnL / peak capital at risk >= 10%.
  Cash posted behind resting orders is not visible in the ledger, so for
  makers this ratio overstates capital efficiency; reviewers' cash-inclusive
  figures are recorded in the verdicts.
* 200 random fills are matched to Polygon receipts. A fill is confirmed when
  the wallet's decoded `OrderFilled` shares for that token in that transaction
  equal the API size (0.5% tolerance). The same events give the wallet's role:
  for both exchange versions the taker's own order emits an `OrderFilled`
  whose taker field is the exchange contract.

## Stage B: profile

Per market: shares and average price of each outcome bought, sells matched
against those buys at average cost (realized PnL), complete pairs among the
shares still held, pair cost, locked PnL (`pairs * (1 - avg_up - avg_down)`),
directional residual PnL, win rates, price calibration (win rate of bought
shares by price bucket, buys only), timing relative to the window or game
start, and income split (fees, maker and taker rebates, rewards). For every
resolved market `pnl = realized + locked + residual`; sells of shares bought
before the window have no known basis and are reported separately. This
decides which hypothesis family to test.

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

Hypothesis families for crypto Up/Down windows:

* **LA** (latency taker): score = spot-implied fair value of the bought side
  minus its price, with spot `latency` seconds old.
* **DM** (directional maker): the same score on passive fills.
* **SR** (spot-reactive maker): score = the spot log return over the last
  1-5 s toward the bought side, with spot `latency` seconds old: a maker whose
  bids are filled right after spot moved toward that side quotes on spot.

The statistic is the **stratified AUC**: wallet decisions are compared with
other traders' decisions only inside strata, so a wallet with static
preferences does not count as matching a spot hypothesis. Two stratifications
are computed on the same null draws and a match must beat the null on both
(p is the larger of the two):

* global strata: price (50 quantile bins) x time in the window (40 bins,
  7.5 s for 5-minute windows, plus before-start and after-end) x side, which
  controls a preference for particular prices or seconds of the window;
* within-window strata: window x price (10) x time (10) x side, which
  controls a wallet that is simply more active in some windows.

The **permutation null rotates spot paths between windows of the same
2-hour block**: in each draw every block's windows take the spot path of the
window k_b positions later (cyclically, k_b != 0, drawn independently per
block; at least 4 windows per block are required). Every decision keeps its
price, timing, side and window and is scored on another real spot path, so
the statistics are exchangeable when the wallet's choices depend only on the
stratum features. A wallet that reacts to something correlated with spot,
such as the market's own tape, can still pass; `tape_momentum_sign` adds the
recent tape move as an extra control stratum to separate the two. 200
rotations; pass: p < 0.01.

**Effect size**: the rule at the FIT threshold (max MCC) must also flag at
least 20% of the wallet's TEST decisions (recall >= 0.2) at least twice as
often as the base rate (lift >= 2). A significant but small association is
reported as a partial match, not a match.

**Multiplicity**: each wallet is tested on several hypothesis families (LA,
DM, SR, on Kraken and Binance spot), so a match must also survive Holm over
the families tested for that wallet. With 200 rotations the smallest
attainable permutation p is 0.005, so where Holm binds, the null is
summarized by its mean and standard deviation and the z-score of the
observed statistic (normal approximation of the rotation null) is reported.

For sports: reaction share, direction agreement after scoring plays, and the
lag histogram of the wallet's fills relative to ESPN wall-clock times, against
a null that shifts each game's play timeline by 5-25 minutes.

### Backtesting the rule

* Up/Down fair value: the strike is the 60 s spot TWAP before the window
  (the market's `priceToBeat` is the previous window's closing Chainlink TWAP;
  555/555 consecutive pairs agree); the close is the 60 s TWAP at the end.
* Taker rules buy at observed taker prints (liquidity that traded) when the
  rule fires using information available `latency` seconds earlier; fees use
  the market's own `feeSchedule` (`fee = shares * rate * p * (1 - p)`).
* Bids are placed on the exchange's dynamic tick: 0.01 between 0.04 and 0.96,
  0.001 outside (mid-range tape prices sit on the cent grid 96% of the time;
  Gamma's `orderPriceMinTickSize` is read after resolution and says 0.001).
* The SR maker bids on a side only after the spot return toward it exceeds
  theta, at the side's last public tape price minus delta. Its parameters
  (theta, delta, horizon, requote interval, latency in {2, 3} s) are chosen
  on FIT by per-window t, counting windows without fills as zero.
* Maker rules rest bids and are filled only by later taker prints that trade
  **through** the bid (a taker sell below it, or a complementary taker buy of
  the other outcome above `1 - bid`). Rebates are excluded.
* Maker results are reported under strict trade-through fills and, as an
  optimistic upper bound, at-touch fills (a print at the bid also fills it,
  as if first in queue). A rule only counts as replicable if it is profitable
  under the strict model; a loss under the optimistic bound is decisive.
* Alternative maker hypotheses that need no external data (fixed-price
  resting bids, "buy the overreaction") are tested on the same windows
  (`research/stage_a/updown_btc5m_maker_at_touch_bound.json`, and the ladder
  results in each verdict).
* Where no public event feed exists (esports, tennis), the maker
  replicability study backtests a slow two-sided maker whose fair value is
  the last public print known `latency` seconds late, with the same
  trade-through fills, on the wallet's own markets (fit/test split by market
  start time). It answers whether the market-making economics survive for a
  replicator without the wallet's speed or data.
* Settlement uses the resolved payout, which decision code never sees.
* Rules chosen on FIT are also evaluated, frozen, on every 2-hour block of the
  TEST week the standard sample did not use, and on the day after `as_of`
  (data that did not exist when the study was designed).
* Block-time slack: tape timestamps are Polygon block times, so a print
  stamped T was matched somewhere in [T - 2 s, T]. In the frozen-rule
  extension the SR maker is fitted and evaluated with each print attributed to
  the order live at its earliest possible match time (`match_slack=2`), so no
  fill can come from a trade that may predate the order; the slack-0 result is
  reported as the optimistic reference. The DM and tape-only maker results use
  slack 0, which favours those strategies, and they lose regardless.
* Sports rules may not use a play before its ESPN wall clock plus an
  information delay of at least 5 s (FIT chooses D in {5, 10, 20, 30, 60}); the
  zero-delay result is reported only as an upper bound.
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
  earlier days (p > 0.05), the last 15 days have not significantly declined
  vs. the 15 before (p > 0.05; catches a regime change inside the window),
  there is no significant negative trend (p > 0.05), and the policy the
  strategy relies on (fees, rebates, rewards, market listings, taker delay) is
  still in force. One-off taker-rebate level-up bonuses are removed first
  (the "recurring" series). A CUSUM break is reported but only counts against
  the wallet when the break is a decline. Results:
  `research/stage_a/persistence_a1_survivors.json`.
* **Rebate tiers** (`research/stage_a/rebate_dependence.json`): the observed
  tier is the median daily rebate / previous day's taker fees; PnL is
  recomputed at every tier of the Taker Rebate Program (None 0%, Bronze 3%,
  Silver 8%, Gold 18%, Platinum 32%, Diamond 44%, Obsidian 50% of fees) with
  maker rebates, rewards and yield kept and level-up bonuses ($10 to
  $25,000, paid once) removed.

## Changes after first run

* Deflated Sharpe ratio: the first implementation used the cross-sectional
  std of observed Sharpe ratios (which includes real skill and short-history
  noise) as the null dispersion. That made the benchmark arbitrarily strict
  (an annualized Sharpe of 9.6 over 477 days scored 1e-7). The null now uses
  the sampling std of a single Sharpe estimate, 1/sqrt(T-1). Thresholds were
  not changed. Effect: 5 -> 11 wallets passed stage A1.

### Second round: adversarial review (2026-10-31)

An independent review re-derived every stored number from the cache, audited
the code for look-ahead, statistical and accounting errors, and tried to
overturn each rejection with new hypotheses. Six defects were confirmed and
fixed; each fix has a regression test. All studies were re-run with the same
frozen `as_of` (2026-10-30 00:00 UTC), seeds and samples.

| Defect | Effect before the fix | Fix |
| --- | --- | --- |
| Match-test null shifted the spot clock by 1-6 h, but spot is only loaded around the sampled blocks | Null draws scored a median 35% of prints, on stale spot, and kept a price-only signal; a spot-blind wallet that prefers expensive prints "matched" at p=0.005, while real spot-driven selection was missed | Within-block window-rotation null, stratified AUC, effect-size floor |
| Sports FIT grid allowed negative information delays | Latent (no stored study chose one), but a rule could act on plays before they happened | Delay >= 0 enforced; FIT minimum 5 s; D=0 reported as an upper bound |
| Dormant weeks/blocks counted as losing periods | mo-money (rank 242) failed A1 only because of 16 weeks with no trades after a $50 test trade | Inactive weeks/blocks left out of the positive shares |
| HAC t-test used a t(n-1) reference | 3-50x too many false rejections at the alphas Holm needs | Exact finite-sample reference |
| Per-market decomposition summed SELL fills as purchases | TommyLeePeeca's settled PnL read $86.6k (true $27.2k) and its mechanism was mis-described | Sells matched to buys at average cost |
| Descending tape scan walked dense seconds without `limit` | 81% of rows in 19 dense seconds were lost (BTC maker studies); bosona's own 5m fills read +3.5% (true -0.1%) | `limit` sent, walk completeness reported |

Smaller corrections: an undefined deflated Sharpe now fails; the bootstrap
uses 20,000 resamples near the 0.01 bar; complete sets are not capital at
risk; the Up/Down strike is the pre-window 60 s TWAP; maker backtests use the
dynamic tick; the tape-only maker reports the at-touch bound; rebate
dependence identifies the observed tier and removes one-off level-up bonuses;
persistence adds a last-15-vs-prior-15-days decline test. The effect-size
floor for (6) and the late-window decline test were added after first
results; both can only turn passes into failures.

Effect on stage A1: 12 wallets pass (mo-money added, none lost). Failure
counts: deflated Sharpe 463 (15 more: undefined DSR), Holm 305, positive
weeks 317, positive months 312, bootstrap 247; the others are unchanged.

A second audit of the round-2 code (2026-10-31) found that four
time-in-window bins were too coarse (a wallet trading only in the first 15 s
of a window looked spot-driven 7-15% of the time at a nominal 1%), that the
pooled statistic was anti-conservative for wallets more active in some
windows, that a tape-following maker passes the spot-return test without a
tape control, and that the rotation is degenerate with fewer than 4 windows
per block. The match test now uses 40 time bins, requires the within-window
statistic too, offers the tape control, and refuses degenerate blocks; the
synthetic size tests cover each case. The same audit fixed float noise in
tape prices, the closing TWAP after the window end, and the persistence
references (now exact; mo-money's persistence changed from fail to pass).

