# directional-maker: lab notebook

Strategy: directional crypto Up/Down maker run across three wallets
(bosona 0xc2ad03f7..., almach 0x3725d52f..., mo-money 0x32ed2e54...).
Brief: research/reverse_engineering/BRIEF.md. Workspace: this folder and
.cache/re/directional-maker/.

## Pre-registration (iteration 1, fixed for all iterations)

- Frozen dates: as_of = 1793318400, H = 1792713600 (2026-10-23 00:00 UTC).
  Nothing at or after H is loaded by any development script (every fetch is
  clamped to end < H).
- BUILD = [2026-10-09 00:00, 2026-10-16 00:00) = [1791504000, 1792108800).
  VALIDATE = [2026-10-16 00:00, 2026-10-23 00:00) = [1792108800, 1792713600).
  Earlier history (back to the first trade) is used for description only.
  Rules are chosen on VALIDATE only.
- Primary metric (higher is better): **presence AUC on VALIDATE** for BTC 5m
  Up/Down windows. Unit = (window, outcome side, 10-second bin inside the
  window's life [start-?, end)); label = the cluster (any of the 3 wallets)
  receives >= 1 maker BUY fill on that side in that bin; features use only
  information published at or before the bin start; no own-state features
  (a with-own-state variant is reported separately). A market-activity-only
  baseline AUC is reported next to it so wallet-specific signal is visible.
- Secondary metrics (reported every iteration): side accuracy (per window
  where the cluster's maker buys are >= 70% one side by shares; vs. the
  market-only baseline "buy the favourite at the time of its first fill"),
  price-within-one-tick share, per-window PnL correlation, match_test
  selection AUC / recall / lift.

## Data gathered

(see sections below; large files in .cache/re/directional-maker/)

## Hypotheses ledger

(see state.json for the machine-readable ledger)

## Log

### Iteration 1 (2026-10-31, started 07:24 UTC)

Data gathered (all < H):
- data-api activity of the 3 wallets, 2026-10-08..H: bosona 49,345 rows, almach 47,789, mo-money 52,405
  (`activity_<name>.parquet`). Full-history fetch (start=0) postponed (slow; cache makes a restart cheap).
- **On-chain OrderFilled logs** (V2 exchanges, topic2 = any of the 3 wallets), 2026-10-09..H, via
  `polygon-bor-rpc.publicnode.com` (drpc free plan refuses eth_getLogs ranges > ~100 blocks; publicnode takes 5,000):
  109,822 fills (97,074 maker, 12,748 taker), `chain_fills_1791504000_1792713600.parquet`. 100% join to activity on (tx, token, wallet).
  Polygon block time is ~1.5 s now (not 2 s).
- Gamma metadata of all 4,032 BTC 5m windows 2026-10-09..H (`windows_5m.parquet`), Binance 1-s klines 2026-10-08..H
  (`spot_btc_1s.parquet`), data-api taker tapes [start-900, end) of every BTC 5m window (in progress, `taker_5m*.parquet`).

Market facts (Gamma, BTC 5m): resolves on the Chainlink BTC/USD **TWAP-60s** data stream: Up iff TWAP at the end >= TWAP at
the start (priceToBeat). priceToBeat(W) == finalPrice(W-1) exactly (all windows). Gamma closedTime is 52-87 s after the end.
Tick 0.001, min order 5 shares, taker fee 7%*p(1-p), maker rebate 20%, markets listed ~24 h ahead.
Chainlink-minus-Binance basis ~ -96 USD (5-95%: -116..-63), autocorrelation 0.97 per window, 0.93 at 1 h: the Binance TWAP proxy
gets the outcome right in 98.1% of windows. (Diagnostic only; priceToBeat/finalPrice never used as features.)

BUILD description (BTC 5m, cluster maker BUY fills, 2026-10-09..16):
- 35,631 fills, $1.12M, in 1,684 of 2,016 windows. 99.3% of fill prices on the 0.01 grid (the 0.001 tick is not used).
- Fills only inside the window: none before the start; 10% by 18 s, median 139 s, 90% by 253 s; 15.6% in the first 30 s,
  only 3.7% in the last 30 s (it stops quoting near the end of the closing TWAP).
- Win rate 48.5% at avg price 0.46; USD-weighted edge +4.1% per $ bought.
- 13,650 orders (orderHash): 1 fill per order (median), 99.8% single price, 78.5% with one fill only; filled size per order
  median 69 shares, frequent 500 (572 orders), 1000, 498, 502, 333; 5 = minimum size.
- Per window: 3-6 orders (median), fills on both sides in 63% of windows, >= 70% one side in 74%; 1-3 wallets per window
  (median 2). Only 2.5% of taker transactions fill two cluster wallets at once: the wallets do not stack at the same moment.
- Counterparties: 5,310 distinct takers, top-10 = 10.5% (includes other studied wallets 0xc53375ff, 0x3048d653).
- Fill price vs Binance fair value: corr 0.85 at lag 0-2 s, 0.78 at 5 s, 0.72 at 10 s, 0.54 at 30 s (prices track fair value
  within seconds). Median price - fair_s = -0.03. Signed spot return before/after fills = 0.0 bp at 1-30 s: no adverse
  selection and no positive selection visible on Binance 1-s data.
- Fills where Binance fair_s > 0.9 have avg price 0.80 and win 0.81 (Binance fair 0.96); fair_s < 0.1: price 0.10, win 0.13.
  Conditional on a fill the market price, not the Binance fair, is calibrated.
- Dominant side (by shares) per window wins 55.9% (one-sided windows 55.8%) at a dominant-side average price 0.569; it equals
  the Binance favourite at the first fill in only 58% (59% one-sided), best at start+10 s (59-61%).
  => The cluster looks more like a fast two-sided maker earning ~4% below-fair fills than a side predictor.

More iteration-1 measurements:
- **Sweeps (600 BUILD receipts):** the cluster's price is the best price in the sweep in 90.5% (the last level in 98%);
  median 1 level and 1 maker per sweep; the cluster takes all of the hit volume in the median sweep. Counterparty taker
  orders: 85.5% BUY the complement (mint match), 14.5% SELL the same token. => top-of-book two-sided maker.
- **Lead-lag (BUILD, 21k fills with fair 0.15-0.85):** MAD(price - Binance fair) and corr are best with spot shifted
  -1..-2 s from the block timestamp (corr 0.751) and get worse into the future (+3 s: 0.711). No sign of a faster or
  private feed in the quote levels; no information wall.
- **Roles:** data-api taker tape (tx, proxyWallet) reproduces on-chain maker/taker roles for 99.97% of VALIDATE fills
  (13,925 maker, 889 taker agree; 5 taker fills mislabeled maker). final_rule.py uses the tape method (no RPC needed).
- **Three wallets:** same per-wallet stats (fills 11-13k, edge 3.6-4.7% on BUILD); within shared windows the dominant
  side agrees 81-84%, up-fraction corr 0.71-0.74; 33% of fill bins have >= 2 wallets; size signatures 500 (almach),
  498 (bosona), 502 (mo-money). Three instances of one bot with the same signals.
- **Window participation:** BUILD 83.5% of windows (93% in the calmest vol quintile, 77-80% in the two most volatile).
  VALIDATE only 1,086/2,016 (54%): 310 inactive runs, max 171 windows (14 h), 355 windows in runs >= 1 h (operator off;
  not predictable from market data). VALIDATE BTC 5m maker edge -2.5..-2.8% (BUILD +4.1%), fills down ~60%.
- **Inventory:** when net long Up (> 50 sh) the next one-sided fill bin is Up 60% (BUILD 0.606, VALID 0.601); long Down
  -> Up only 36-41%. It adds to the side it holds (anti-balancing), i.e. a persistent side state not captured by
  public features (own-inventory model +0.05 AUC).
- **Side rule by time in window:** "side where Binance fair - last print is larger" is 0.70 (BUILD) / 0.67 (VALID) in
  the first 30 s, ~0.60 in 30-180 s, 0.50-0.58 after 180 s. Binance favourite rule: 0.44 at 180-240 s (it buys the
  underdog late).
- **Presence models (VALIDATE, 2,016 windows, 120,960 bins, pos rate 3.3%):** time 0.545, activity 0.720 (reg 0.732),
  spot 0.700, tape 0.756, all 0.768, all_reg **0.772** (frozen), all+own inventory 0.823, tape book proxies
  (last bid-hit / ask-lift price, ages) 0.7726 (no gain, not adopted). Top gain: sig, edge, last_s, hit_s10, volumes.
  Daily AUC 0.73-0.80. Within active windows 0.743; window-level activity AUC 0.69.
- **Price rule:** last print on the side before the fill - 0.01: exact 21%, within 0.01 53% (VALIDATE).
- **PnL:** per-window corr rule vs wallet 0.418 Pearson / 0.492 Spearman.

polyrea notes (no bug fixed, nothing modified):
- drpc free plan rejects eth_getLogs over ranges of ~500+ blocks with a misleading "ranges over 10000 blocks" message;
  publicnode accepts 5,000-block ranges. `fetch_chain.py` here uses publicnode.
- `pkill -f <pattern>` from a shell whose own command line contains the pattern kills that shell (exit 144). Use pids.

## Next steps (iteration 2)
1. Full tapes (maker rows) for BTC 5m windows -> competitor book at each moment (who is at the top, at what price);
   test "cluster at top iff its fair - delta > competitors' best bid".
2. Identify the cluster's fair value: fit bid = g(reference) on fill prices with alternative references: Binance
   aggTrades (ms), Coinbase/OKX/Kraken composite (Chainlink-like), different vol models and TWAP handling; pick the one
   that minimizes the residual dispersion and maximizes side accuracy (BUILD) and check on VALIDATE.
3. The anti-balancing persistence: find the public state behind it (e.g. a slow composite fair vs market gap).
4. Run match_test (selection metric) and a maker backtest of the frozen rule under strict fills.
5. Extend to BTC 15m (28% of volume) with the same pipeline; fetch full activity history (start=0) for persistence.
- **Window participation is the main gap.** From public pre-window features (vol, hour, pre-window prints, |60 s return|,
  previous window's market activity) the window-level participation AUC on VALIDATE is only 0.54. With an oracle for which
  windows the cluster is on, the frozen presence model would score 0.866 (hour-level oracle 0.808). So the on/off decision
  (operator downtime: off-runs up to 14 h; VALIDATE only 54% of windows active) caps the no-own-state presence AUC near 0.77
  unless a public correlate of the on/off is found. Candidate information wall for the presence metric (not the quotes).
- **Fair-value variants:** a Binance fair with 1.4x the 1-s realized vol (300-900 s lookback) fits the fill prices better
  (MAD 0.058 vs 0.068) but does not change presence (0.7727) or side (0.594 edge rule). Not adopted.
- **Selection pilot** (`code/selection.py`): among all 2.7M taker prints inside VALIDATE BTC 5m windows, which ones fill a
  cluster maker order (base rate 0.48%)? LightGBM fitted on BUILD: VALIDATE AUC 0.755; flagging BUILD's top 15% of scores
  catches 43.2% of the cluster's fills at lift 3.78. Top features: the print's size, implied maker price, vol, fair - price.
  Without the print size: AUC 0.703, recall 30.5% at lift 3.15 (book-depth mechanics carry part of it).
  Stratified AUC (implied price decile x 30-s bucket x side) of the full pilot: 0.746, so it is not price/time structure.
  Not yet the brief's match_test (no rotation null / stratification): do that in iteration 2.

- **Early side commitment:** the side of a window's first cluster fill is the window's dominant side in 79.7% (BUILD) /
  85.6% (VALIDATE) of windows, and 75-79% of the window's shares are on it. First fill: BUILD win 54.1% at avg price 0.513,
  VALIDATE 51.6% at 0.515. Together with the anti-balancing inventory effect: it picks a side early (first fill median
  36 s; the fair-vs-last-print edge rule is 0.67-0.70 right after the open) and keeps bidding that side.
  Iteration-2 idea: model the first-fill side (opening TWAP-strike effect) and the per-window commitment explicitly.

## Iteration-1 checkpoint
- Primary metric (presence AUC, VALIDATE, no own-state): **0.7723** (rule R1, `code/final_rule.py`, end-to-end run).
- Target not met: presence 0.77 < 0.85; side 0.675 < 0.80 (but far above the 0.515 favourite baseline, p=5e-45);
  PnL corr 0.42 (Spearman 0.49) < 0.5; selection pilot 0.755 with recall 43% at lift 3.8 (close to the recall/lift bar).
- Status: continue. Background cache warmers for full tapes (maker rows) were started at the end of iteration 1 and
  stopped at the checkpoint; whatever they fetched is in the shared HTTP cache (`warm_tapes.py ... full`).

### Iteration 2 (2026-10-31, local Windows laptop, started 08:40 UTC)

Local re-fetch (all < H; `code/fetch_local.py`; HTTP cache was empty):
- Gamma metadata of the 4,032 BTC 5m windows 2026-10-09..H (`windows_5m.parquet`), activity of the 3 wallets
  2026-10-08..H (49,345 / 47,789 / 52,405 rows: identical counts to iteration 1), Binance 1-s klines 2026-10-08..H.
- data-api taker tapes [start-120, end) of every BTC 5m window 2026-10-09..H (14 day files `taker5m_day_<d>.parquet`,
  ~430k rows/day). About half of the windows were read (read-only) from another agent's identical pulls in
  `.cache/re/btc5m-bot/tapes/<cid>.parquet` (same endpoint, wider range [start-600, end+5], cut to ours). Running two
  fetchers at 8 req/s next to the other agent triggered Cloudflare 429 (retries exhausted) once; the fetcher now backs
  off per window (5 req/s, 4 threads). PRE is 120 s now (was 900): only `last_s` at rel=0 and `n_prints` change meaning.
- Free disk on C: dropped to 2.2 GB for a few minutes at ~09:00 UTC (not this agent: our folder is ~0.2 GB);
  it recovered to 17 GB later.

**LEAK FIX (important).** Iteration 1 computed every tape feature from the full taker tape, including the prints that
filled the cluster (hit_s10 etc. partly counted its own fills; last_s was often its own fill price). The brief forbids
it. `features2.clean_tape` now drops every print whose transaction contains any cluster trade (maker or taker) or whose
taker is a cluster wallet. Only ~1% of tape rows are removed (the cluster is a small share of BTC 5m taker prints).
The iteration-1 primary score 0.7723 is therefore leaky; the comparable clean v1 feature set scores 0.7592.

New measurements (descriptive, activity + spot only, `code/onoff_side.py`, `code/open_wallets.py`):
- **On/off is not downtime.** In 5-min slots where the cluster has no BTC 5m fill it still trades other markets in 89%
  (VALIDATE) / 93% (BUILD) of slots. VALIDATE BTC 5m participation by hour: 38-40% of windows 00-12 UTC, 74-75%
  12-20 UTC, 51% 20-24 UTC (BUILD flat 77-94%). By day x 3-h block it is a regime, not a clock: BTC 5m off for
  13 h twice, 10-17 23:00 -> 10-18 12:00 and 10-18 23:00 -> 10-19 12:00 UTC (while trading other markets), then 33-86%
  per block on 10-20..22 (BUILD blocks 50-100%); 10-19 was its worst day (fills won 0.327 at avg price 0.407). Public clean-tape statistics of on and off windows are the
  same (VALIDATE medians at rel=60: prints since start 296 vs 277, s-bid hits in 60 s 141 vs 141, distinct takers 158 vs
  152, vol 0.27 vs 0.28 bp/s). => a per-market schedule chosen by the operator, invisible in public data.
- **Opening decision:** first fill <= 6 s after the start in 21% of active BUILD windows (11% VALIDATE): orders rest at
  the open. Side = sign(Binance spot at the start - Binance TWAP strike) 66% (BUILD), 76-79% when |gap| > 3 bp
  (n = 59 / 24); price corr 0.85-0.89 with the Binance fair at the open. First fill side = previous window's proxy
  outcome 60-62% (momentum; the same strike-lag effect).
- **Three wallets:** no rotation by window index (first-wallet shares equal across window index mod 3), no side split
  (Up share 0.47-0.50 each), same median second (133-154 s); all 3 wallets in 56-63% of active windows. Consecutive
  fills come from the same wallet 72% of the time vs 43% under a within-window shuffle: each wallet works its own
  resting orders in parallel (three copies of one quoting engine).

Presence (primary metric, `code/train2.py`, BUILD = 2026-10-09..16, VALIDATE = 2026-10-16..23, clean tape,
LightGBM 15 leaves / min leaf 1000 / l2 10 / 300 rounds / max_bin 63):

| model | VALIDATE AUC | within active windows |
| --- | --- | --- |
| time only | 0.546 | 0.548 |
| market activity only (co-occurrence baseline) | 0.735 | 0.712 |
| spot only (+time) | 0.710 | 0.685 |
| all, iteration-1 features (clean) | 0.759 | 0.732 |
| + window path features | 0.760 | 0.733 |
| **+ path + previous-window features (R2, frozen)** | **0.763** | 0.736 |
| R2 + own inventory (reported separately) | 0.822 | 0.756 |
| activity + own inventory | 0.812 | 0.738 |

Daily R2 AUC 0.724-0.786. Top gain: edge_s, last_s, hit_o10, sig, hit_s10, rel, strike_move_s, vol_s60, e_open_s.
Window on/off from the mean predicted presence in the first 60 s: AUC 0.576.
Side (3,805 one-sided fill bins): R2 0.679 vs favourite 0.515 / Binance favourite 0.545 (sign test p ~ 0);
by time in window 0.769 (0-30 s), 0.715 (30-120 s), 0.638 (120-300 s); in the 25% / 10% most confident bins 0.816 / 0.879.

Price (`code/price2.py`, 13,934 VALIDATE maker fills; 99.0% of them on the 0.01 grid, as in BUILD; price2's own
`grid_0.01_share_val` = 0.816 is a float-tolerance artefact of the activity prices, ignore it): last clean print on s - 0.01: exact 31.4%, within 0.01 58.5% (BUILD 32.5% / 58.5%). Alternatives worse:
floor(fair - m) 11%, last ask-lift - 0.01 51.7%, last hit bid 50.7%, LightGBM regression 51.1%; own previous fill price
adds nothing. Price - last clean print: -0.01 (34%), 0 (16%), -0.02 (12%).

Selection (`code/sel2.py`; population = in-window taker prints except the cluster's own taker prints; label = the
print's transaction holds a cluster maker fill; BUILD negatives 10%, VALIDATE 25% with weights; threshold = BUILD top 15%):

| score | AUC | strat. AUC price50 x time40 x side | within-window strata | recall | lift |
| --- | --- | --- | --- | --- | --- |
| all (bin panel + print fields + spot) | 0.769 | 0.758 (null 0.678, max 0.694) | 0.665 (null 0.655, max 0.660) | 49.0% | 3.80 |
| market activity only | 0.743 | 0.724 | 0.660 | 47.2% | 3.22 |

Rotation null with 10 draws (p = 1/11 is the floor; observed above every draw on both strata). Top features: print size,
maker price, vol, price minus last clean print, opening edge, strike move, edge.

99-draw rotation null (`code/null99.py`, VALIDATE negatives 10%): stratified (price x time x side) AUC 0.756 vs null
0.679 +- 0.009 (max 0.698): p = 0.01, z = 8.7. Within-window strata: 0.658 vs null 0.653 +- 0.008 (max 0.674): p = 0.35,
z = 0.5. => the spot part of the selection score separates windows / moments (vol, strike move, opening edge), not
which print inside a window fills the cluster; inside a window the print's size and its price relative to the last
print do the work. The brief's selection criterion (p = max of both < 0.01, AUC >= 0.80) fails; recall 49% at lift 3.8.
End-to-end `final_rule.evaluate(VALIDATE, local=True)` reproduces every number above (presence 0.7634 / baseline 0.7349 /
own 0.8216, side 0.679, price 0.313 / 0.585, selection 0.7695 / 0.7578 / 0.6652, recall 48.9%, lift 3.81) and gives the
per-window PnL correlation rule vs wallet: Pearson 0.334, Spearman 0.393 (1,086 windows; iteration 1's 0.418 / 0.492
was on the leaky tape). Wallet's own BTC 5m maker return on VALIDATE -2.3%.
Within-second print order matters for the price rule: an unstable sort by second gave 0.255 / 0.506 instead of
0.313 / 0.585; every sort is now stable (data-api row order, i.e. on-chain order within a second).

polyrea / environment notes (nothing modified):
- Two fetchers at 8 req/s each plus another agent's fetchers on data-api /trades hit Cloudflare 429 ("retries
  exhausted") within 3 minutes; HttpClient's per-process limiter cannot see other processes. Use <= 5 req/s per process
  and per-window retry with back-off when several agents share the connection.

On-chain orders, VALIDATE (`code/fetch_chain.py` via publicnode, 5,000-block ranges, 190 s: 40,357 OrderFilled of
the 3 wallets, 36,595 maker / 3,762 taker, 37% in BTC 5m; `code/orders2.py`): one price per order (100%); 58.5% of
BTC 5m orders filled once; filled shares per order median 76, modes 500 (363 orders), 125 (275), 250 (247), 5, 10, 25,
50 (BUILD modes were 500 / 1000 / 498 / 502 / 333: smaller orders in VALIDATE, a 500-250-125 ladder); ~4 orders per
active window. Multi-fill orders are consumed within 0-2 s (99% within 8 s): the fill record shows no long-resting
orders; only 73 orders rest >= 5 s between fills, where the Binance fair moved no less than at random times
(|dfair| median 0.003 vs 0.004): too few to measure requote rules. At the first fill the bid is ~0.019 below the Binance
fair (median).

Window-level side (817 active VALIDATE windows with >= 70% of the shares on one side; dominant side forecast from the
mean R2 presence per side over the first T seconds, point-in-time at T): T = 30 s 0.621, 60 s 0.641, 120 s 0.657 vs
favourite by last print 0.51-0.54 and Binance favourite 0.53-0.55 (sign test p 5e-5 .. 4e-9); most confident half
0.665 / 0.694 / 0.716. The window's side is only partly decodable from public data.

Final end-to-end run of the frozen rule on VALIDATE (`final_rule.evaluate(1792108800, 1792713600, local=True)`, defaults
n_perm = 99, selection negatives 10%; output `results_iter2_evaluate_validate.json`): presence 0.7634 (baseline 0.7349,
own 0.8216, active windows 0.7363); side 0.679 (activity-only model 0.621; favourite 0.515; Binance favourite 0.545;
p = 1.7e-46); price 0.313 / 0.585; PnL corr 0.334 / 0.393; selection AUC 0.770, stratified 0.757 (null 0.680 +- 0.009,
p = 0.01, z 8.7), within-window 0.669 (null 0.655 +- 0.008, max 0.670, p = 0.04, z 1.7), recall 48.9% at lift 3.80;
activity-only selection 0.744 / 0.724 / 0.664, recall 47.1%, lift 3.23. The within-window null p moves between 0.04
and 0.35 with the negative subsample (null99.py used another seed): not significant at 0.01 either way.

Schedule vs own PnL (own-state, descriptive): next-hour BTC 5m participation does not depend on the last 3 hours' PnL
(corr 0.009 BUILD, 0.062 VALIDATE; flat by quartile). The two long VALIDATE off runs both ran 23:00 -> 12:00 UTC
(13 h, 10-17/18 and 10-18/19) and both followed a 6-h loss of 22% on the dollars bought (-$3.3k, -$1.7k): an overnight
stop after bad evenings, two events only.

Counterparties (clean classification of every BTC 5m taker print): the prints that fill the cluster come from many
takers (5,305 in BUILD, 3,200 in VALIDATE; top-10 = 11% / 13%) and are larger than other prints (median 11 / 18 shares vs
7 / 8; 90th pct 193 / 312 vs 53 / 57); 86-89% are takers buying the complement (others 84-85%). The busiest takers
(0xc53375ff: 94,770 VALIDATE prints) hit the cluster in only 0.3% of their prints: it is not the bots' liquidity, it
absorbs the larger, dispersed orders at the top of the book.

On/off cap with the clean features: giving R2 an oracle for which windows the cluster trades (p = 0 elsewhere) lifts
the VALIDATE presence AUC from 0.763 to 0.862 (hour-level oracle 0.802; activity baseline with the window oracle 0.849).

Examiner path checked: `evaluate(1792418400, 1792425600)` with local=False (adapters only) runs in 24 s on 24 windows
(311 fills; presence 0.780 vs baseline 0.722). A full holdout run fetches ~3 data-api pages per window (about 15-20 min for
a week at 8 req/s) and the 99-draw null adds ~5 min per week of windows.

Stability (walk-forward inside VALIDATE, test 10-20..22): frozen BUILD-only R2 0.777; refit on BUILD + 10-16..19 0.781;
10-16..19 only 0.780 (activity baseline 0.754 / 0.761 / 0.755). The presence relationship is stable across the
regime change; a refit on all pre-H data would add ~0.004, so R2 stays frozen as validated.

## Iteration-2 checkpoint
- Primary metric (presence AUC, VALIDATE, no own-state, clean tape): **0.7634** (rule R2, `code/final_rule.py`);
  activity-only baseline 0.7349 (gain +0.029); with own inventory 0.8216. Iteration 1's 0.7723 was leaky (clean: 0.7592),
  so the honest improvement this iteration is +0.004 from the new path and cross-window features.
- Target not met: presence 0.763 < 0.85 (capped by the operator's BTC 5m schedule, which is invisible in public data);
  side 0.679 < 0.80 (0.769 in the first 30 s, 0.816 in the 25% most confident bins); price within 0.01 58.5%;
  PnL corr 0.33 / 0.39 < 0.5; selection AUC 0.770 (strat 0.757, p = 0.01 global but p = 0.04-0.35 within windows),
  recall 49% at lift 3.8.
- Status: continue.

## Next steps (iteration 3)
1. Order level (on-chain orderHash, VALIDATE fetched at the end of iteration 2: `chain_fills_1792108800_1792713600.parquet`,
   `code/orders2.py`): how long orders rest, how far fair moves before it requotes, replacement triggers (spot move,
   print, time), order sizes; a requote model would turn the presence model into a quote model.
2. Reference feed at the open: windows where the Binance gap (spot at the start vs TWAP strike) and the Chainlink-implied
   gap disagree (priceToBeat as a diagnostic, basis carried from the previous window): which one does the opening side
   follow? Coinbase/Kraken trades around the open as a third feed.
3. Full tapes (maker rows) for a sample of VALIDATE windows: competitor bids at the cluster's fill moments; test "its
   bid is at the top iff its quote > best competitor bid"; competitor maker prints are public features.
4. Within-window selection is driven by print mechanics: features of the print relative to the predicted quote
   (q - (last clean print - 0.01)), size relative to 500, prints in the same second.
5. Own-state description of the schedule (does it switch BTC 5m off after losses?), reported separately.
6. BTC 15m (28% of volume) with the same pipeline.

### Iteration 3 (2026-10-31, local Windows laptop, started 09:28 UTC)

Data added (all < H):
- On-chain OrderFilled logs of the 3 wallets for BUILD 2026-10-09..16 via publicnode (`code/fetch_chain.py 1791504000
  1792108800 5000`, 254 s): 69,465 fills (60,479 maker / 8,986 taker), `chain_fills_1791504000_1792108800.parquet`.
  BUILD now has the order-level (orderHash) view as well.
- Binance BTCUSDT 1-s kline fields beyond the close (volume, trade count, taker-buy volume, high/low) re-read from the
  cached, SHA-256-checked daily archives 2026-10-08..22 (`code/spotflow3.py` -> `spotflow_1s.parquet`; no network).
- Frozen list of the 72 high-frequency takers (>= 5,000 clean BTC 5m prints in the BUILD week, 36.6% of BUILD clean
  prints): `code/hft_takers3.json` (BUILD only).
- Gamma listing fields of the 4,032 BTC 5m windows re-read from the HTTP cache (`code/meta3.py`).

New hypothesis families (all fitted on BUILD, compared on VALIDATE; R2 = 0.7634 is the reference):

**N1 print signature (selection), `code/sig3.py`.** Can the prints that fill the cluster be recognised by its 0.01 price
grid or its order-size ladder? No. 93% of the other makers' prints are on the 0.01 grid too; cluster-filled prints are
on it less often (86%, because larger prints sweep two levels and print a VWAP). Ladder sizes (500/250/125/498/502/
1000/333) occur in only 0.4% of cluster-filled prints (lift 2.1 on that sliver). Rejected.

**N2 public correlates of the BTC 5m on/off, `code/onoff3.py`, `code/meta3.py`.** Window-level LightGBM fitted on BUILD
windows, AUC on VALIDATE windows: previous-hour taker mix of the clean tape (top-20 taker share, HFT share, share of
prints >= 50 sh, buy share, distinct takers, median size, last slot's prints) 0.466; spot regime (1-h and 4-h vol,
|1-h return|) 0.540; both 0.490; plus hour of day 0.509. Univariate relationships flip between the splits (1-h vol
AUC 0.394 in BUILD, where the cluster was off in volatile hours, vs 0.497 in VALIDATE; 1-h print count 0.445 vs
0.554). Listing-time Gamma fields do not vary (reward programme min size 50, max spread 4.5, daily rate 0.001 for
4,030 of 4,032 windows). Own activity elsewhere (descriptive): with BTC 5m off it still trades BTC 15m in 38% of the
slots (53% with BTC 5m on) and ETH 5m in 22% (29%). Rejected: still no public correlate of the schedule.

**N3 who is arriving (counterparty type and order size), `code/feat3.py`, `code/train3.py`.** Bid hits on s by big
(>= 20 sh) prints over 30/60/120 s, by HFT vs other takers, the largest print in 60 s, the time since the last
>= 50-sh hit, the direction of the last 20 prints, HFT share and distinct non-HFT takers in 60 s (clean tape).
Presence R2 + N3 0.7630 (R2 0.7634); activity baseline + N3 0.7358 (0.7349). Rejected.

**N4 Binance order flow, `code/flow3.py`, `code/train3b.py`.** Taker-buy imbalance over 1/3/5/10/30 s and since the
window start, normalised imbalance, volume, trade count, 5-s range (seconds published by the bin start). R2 + flow
0.7619 (worse); spot + flow 0.7094 vs spot 0.7102. Side of one-sided fill bins by the flow sign: 0.48-0.50 (1 s:
0.477, n = 3,225, slightly contrarian: its bid on s is hit just after Binance flow against s). Rejected: its quotes do
not lean on Binance order flow.

**N5 conditional side model, `code/side3.py`.** P(Up | exactly one side filled) from both sides' public features,
LightGBM on BUILD one-sided bins: VALIDATE 0.660 (600 rounds 0.665; top-25% confidence 0.79-0.81; first 30 s
0.743-0.747) vs 0.679 from comparing the two presence scores. Window-level dominant side from it 0.626 / 0.651 /
0.661 at T = 30 / 60 / 120 s (R2 route 0.621 / 0.641 / 0.657). Rejected. Capacity check of R2 (same features): 800
rounds 0.7632, 31 leaves 0.7633, 7 leaves 0.7612: R2 sits on a plateau.

**N6 deconfounding the schedule, `code/deconf3.py`.** BUILD's off windows were the volatile ones, VALIDATE's were not,
so R2 partly learns BUILD's schedule. R2 fitted on active BUILD windows only: 0.7605 overall (0.7365 inside active
windows, R2 0.7363); R2 without the 30-min vol `sig` 0.7564; both 0.7547. Rejected: vol helps on VALIDATE too.

**N7 what happens after a fill (mechanism; later prints and spot used only to describe), `code/converge3.py`,
`code/who3.py`.** Cluster maker BUY fills more than 60 s before the end vs a 5% sample of other makers' fills (clean
bid hits at their implied maker price q):

| | BUILD cluster | BUILD others | VALIDATE cluster | VALIDATE others |
| --- | --- | --- | --- | --- |
| Binance fair of s minus q at the fill | +0.0285 | -0.0010 | +0.0287 | -0.0027 |
| last clean print on s before the fill minus q / Binance fair minus that print | +0.005 / +0.024 | +0.011 / -0.012 | +0.013 / +0.016 | +0.012 / -0.015 |
| market (last clean print on s) minus q after 5 / 30 / 60 s | +0.004 / +0.006 / +0.012 | -0.002 / -0.001 / -0.002 | +0.001 / -0.007 / -0.005 | -0.003 / -0.003 / -0.003 |
| market minus the pre-fill print after 5 / 30 / 60 s | -0.001 / +0.001 / +0.007 | -0.013 / -0.012 / -0.013 | -0.012 / -0.019 / -0.017 | -0.015 / -0.015 / -0.015 |
| Binance fair move after 5 / 30 / 60 s | -0.002 / -0.008 / -0.007 | -0.003 / -0.003 / -0.003 | -0.003 / -0.012 / -0.016 | -0.003 / -0.005 / -0.003 |
| payout minus q | +0.021 | -0.001 | -0.017 | -0.005 |

(The "minus the pre-fill print" row of other makers is dominated by the bid-ask bounce: their bid hit usually follows
a print at the ask. Compare the cluster with itself across splits, and the fair columns across groups.)

The cluster buys about 2.9 cents below the Binance fair while other makers trade at it; it fills when the market is
below Binance (BUILD: the last print was 2.4 c under the fair). In BUILD the market then rose +0.7 c above the
pre-fill print within 60 s (+1.2 c above the fill price) while Binance fell 0.7 c: it earned from the market catching
up with Binance, not from forecasting spot. In VALIDATE the same 2.9-c discount was followed by a 1.6-c adverse Binance
move within 60 s (others -0.3 c) and the market followed it down (-1.7 c): its fills became adversely selected on
future spot, which is the edge decay (+2.1 c per share in BUILD, -1.7 c in VALIDATE).

Caveat on the fair moves (`code/where3.py`): the Binance fair is not the cluster's fair. 40% of its fills are at or
above the Binance fair (BUILD 11,766 of 29,576), and the mean discount comes from fills where the model's fair is
extreme (edge > 0.1: mean 0.19). After a fill the model's fair moves toward the fill price in both directions (BUILD:
+5.9 c after fills priced above the fair, -9.6 c after fills 10+ c below it), so the model is over-confident and part
of every post-fill fair move is that reversion. Compare splits, not groups: with the same mean discount (+2.9 c) the
fair fell 0.7 c in BUILD and 1.6 c in VALIDATE, and payout minus price fell from +2.1 c to -1.7 c. Where VALIDATE lost
(dollar-weighted return of the fills): by time in the window 0-10 s -1.6%, 10-30 s +0.3%, 30-120 s -10.7%, 120-240 s
-1.8% (BUILD +7.1% / -4.3% / +2.1% / +6.7%); by Binance fair of the side 0.4-0.6 -14.9% and 0.6-0.8 -10.0% (BUILD
+9.5% / -2.9%); i.e. near-the-money fills in mid-window lost most. The adverse selection is broad, not one new sniper: the top-10 counterparties (14% of
VALIDATE fills) show -0.023 vs -0.015 for the rest; takers already seen in BUILD -0.018 vs new ones -0.012. BUILD's
profit came mostly from the largest taker orders (top size quartile, > 62 sh: +$34.8k of the week); in VALIDATE the two
largest quartiles lost $11.3k and $7.7k.

**N8 cancel latency / stale-quote pick-off, `code/pickoff3.py`.** Per second of active windows and side (Binance fair
of s in 0.1-0.9): after the fair of s fell by more than 6 c over the last 3 s, other makers' bid hits on s triple (683
vs 228 per 100 s: takers dump s into stale bids) but the cluster's fills rise only 1.6x, so its share of the hits
halves (BUILD 0.90% vs 1.64% with a stable fair; VALIDATE 0.69% vs 0.97%). It reprices or cancels faster than the
average competing maker after Binance moves (less so in VALIDATE, x0.71 vs x0.55). Its VALIDATE losses are therefore
not stale quotes picked off on past moves but fills ahead of future moves (N7). Cluster fill rates per 100 s:
BUILD 6.23 after a > 6-c drop vs 3.80 with a stable fair (x1.64; others x2.99); VALIDATE 4.37 vs 2.27 (x1.93; others
x2.73). (A first run overflowed int16 in the rate columns; fixed and rerun, `results_iter3_pickoff.json`.)

**N11 grid position of the touch, `code/grid3.py`.** Distance of the last clean print to the 0.01 grid, on-grid flag,
fair minus the implied quote (grid level below the last print - 0.01): R2 + grid 0.7629 (R2 0.7634), side 0.681;
activity + grid 0.7348. Rejected.

**N12 another reference feed (Kraken), `code/kraken3.py`** (one BUILD day, 2026-10-14, 166,380 Kraken XBT/USD trades
in 38,561 distinct seconds; 2,214 cluster maker fills, ~1,350 of them with fair 0.15-0.85): correlation of the fill price with the fair value is higher on Binance
(0.831 / 0.835 / 0.833 at lags 0 / 1 / 2 s) than on Kraken (0.815 / 0.807 / 0.803); median |price - fair| 0.059
(Binance, 2 s) vs 0.057 (Kraken, 1 s); opening side 0.68 vs 0.71 on 31 windows (too few). No sign that it quotes off
Kraken rather than Binance; Kraken prints in only 43% of seconds, so it would be a slower reference.

**N9 sizing, `code/orders3.py`** (BUILD 13,650 / VALIDATE 6,271 BTC 5m maker orders; filled shares per order are a
lower bound of its size). Ladder classes (1000/500/250/125) are 13.7% / 18.8% of orders (the rest partly filled). The
class mix does not depend on the edge at the first fill, the price or the time in the window (BUILD: 500-class 62-68%
in every edge bucket); it rises with vol only through fuller consumption (1000-class 31% above 0.8 bp/s vs 7% below
0.3). The ladder moved from 500/1000 (BUILD) to 500/250/125 (VALIDATE: 32/29/36% of ladder orders), the same in the
three wallets. => a fixed size ladder; no edge-dependent sizing.

**N10 when it stops.** Last fill per active window: median 202 s (BUILD) / 200 s (VALIDATE), 90% by 268-270 s; fills
per 30-s slot fall to about a third in the last 30 s (BUILD 1,422 vs 3,000-5,400 in earlier slots): it stops quoting
about 30 s before the end, inside the closing TWAP-60.

## Iteration-3 checkpoint
- Primary metric unchanged: **0.7634** (R2 kept; no candidate beat it: N3 0.7630, N4 0.7619, N6 0.7605 / 0.7564,
  capacity variants 0.7612-0.7633). Secondary metrics unchanged (see FINAL_RULE.md).
- **Stop: diminishing returns (brief).** Best VALIDATE presence AUC on the clean metric: iteration 1 0.7592 (clean
  equivalent of its leaky 0.7723), iteration 2 0.7634, iteration 3 0.7634: +0.004 over the last two iterations (< 0.01),
  although iteration 2 tried 12 and iteration 3 tried 12 new families (N1-N12). The cap is structural: which BTC 5m windows the
  cluster trades is an operator schedule with no public correlate (window AUC 0.47-0.58 from tape statistics, taker mix,
  competitor identity, spot regime, listing fields); with an oracle for it R2 would score 0.862. Not an information
  wall on quotes: no lead over Binance 1-s, and it cancels faster than other makers.
- What a successor could still try (low expected value for the target): a longer BUILD (history before 2026-10-09;
  a walk-forward refit added only +0.004); full maker-row tapes for competitor identities at the top of the book; BTC 15m.

### Iteration 4 (2026-10-31, local Windows laptop, started 12:21 UTC; 152 of 1,200 budget minutes used before it)

Context: exam round 1 (lot h1 + h2 = 2026-10-23..30, 2,304 BTC 5m windows, 36,244 cluster maker fills) judged R2
"match partial": presence 0.700 vs 0.681 activity-only, side 0.655 vs 0.600, price within a tick 0.688, selection
AUC 0.681 (recall 32% at lift 2.6), PnL corr 0.29; the executable rule lost 12.8% under strict fills while the wallets'
own BTC 5m maker fills earned +3.95% (p = 0.005). The lot is now released. Per the brief and the task:
- **New split (pre-registered here, before any lot analysis):** STUDY = lot first half [2026-10-23, 2026-10-27)
  (case-by-case study allowed); **VALIDATE = lot second half [2026-10-27 00:00, 2026-10-31 00:00) = [1793059200,
  1793404800)** (aggregate metrics only; 1,152 windows); BUILD = everything before 2026-10-27 (10-09..10-26).
  Development live-lab blocks after T0 (10-31 00-06, 12-18 UTC, ...) are extra description data.
- Primary metric unchanged (presence AUC, no own-state, clean tape), now on the new VALIDATE.
- state.json brought to the brief's current format (catalog with every item, target_metrics, component tags).
- Live recorder: running (pid 27184, restarted 12:18 UTC); dev recordings exist only from 2026-10-31 12:18 UTC on
  (no 00-06 UTC block recording), so the live lab gives about 1.5 h of books in this iteration.

**Competing explanations (iteration 4) and the observation that separates them**
1. E1 latency-advantaged top-of-book maker on a Binance (or Chainlink) fair value: profit = spread from dispersed
   takers minus adverse selection, protected by cancelling faster than other makers. Test: B1 signing times cluster
   within a few hundred ms after reference moves; short sign-to-fill lifetimes; many re-signed orders per window.
2. E2 liquidity-rewards farmer (BTC 5m rewardsMinSize 50, rewardsMaxSpread 4.5 c): two-sided >= 50-share quotes near
   the mid; the directional residual is a by-product. Test: original order sizes from calldata (>= 50?), distance of
   the limit price from the mid at signing, REWARD rows vs its quoting.
3. E3 informed on the settlement: a better estimate of the Chainlink TWAP-60 settlement (Data Streams, composite) than
   the market's. Test: signing times after Chainlink/RTDS updates rather than Binance; side vs outcome beyond market.
4. E4 operator/meta-controller schedule (risk stops, capital allocation across markets, competitor presence). Test:
   on/off switches simultaneous in the 3 wallets, at window boundaries (opening orders signed or not), tied to own
   PnL or to other markets.
5. E5 pre-positioned ladder / queue priority: orders signed long before they fill (at the open or listing) and earn
   from being first in the queue when big takers sweep. Test: sign-to-fill lifetimes of minutes; batch signing at
   fixed times; limit prices fixed per window.
6. E6 sibling wallets: the operator runs more wallets (same builder/metadata codes, signature format, salt pattern,
   owner key) that trade the windows these three skip, so the "schedule" is a work split. Test: other makers in the
   same transactions with the same fingerprint; complementary activity.
7. E7 cross-market hedge/arbitrage with overlapping 15m/1h/4h windows. Test: 5m side vs its own 15m/1h inventory and
   the 5m-vs-15m implied-probability gap.
8. E8 predictable counterparty flow (copy traders, scheduled retail): it quotes ahead of large dispersed takers. Test:
   quote signing before large prints; identity/lag structure of the takers that fill it.

This iteration discriminates mainly with B1 (V2 calldata of every lot transaction that filled the cluster: signing
ms, original size and limit price, signature format, builder/metadata, other makers in the same match).

**Data added (iteration 4).** All from development periods (the released lot and the 2026-10-31 12:00-18:00 block):
- B1 calldata (`code4/calldata.py`, `code4/fetch_calldata.py`, publicnode batched `eth_getTransactionByHash`, ~75
  tx/s, decoded fields only, `.cache/re/directional-maker/calldata/`): every transaction that filled the cluster in
  BTC 5m in the lot (STUDY 7,777 txs / 37,811 orders; VALIDATE 26,829 txs, aggregate use only), the cluster's
  other-market fills in STUDY (6,026 txs), 7,500 sampled public BTC 5m txs from STUDY (5,000 in the cluster's BTC 5m
  off periods) and 3,000 sampled public BTC 5m txs of 2026-10-26. Decoder verified on the reviewer's tx 0xc1d694...
  (maker BUY 30 at 0.20, signed 1793446973.797).
- Binance spot aggTrades 2026-10-26 (ms) and Binance USD-M futures aggTrades 2026-10-08..30 reduced to 1-s
  (`code4/fut1s.py`, SHA-256 checked, zips never stored). The 2026-10-28 futures archive is not published (HTTP 404
  NoSuchKey for the zip and its .CHECKSUM); that day is filled with Bybit BTCUSDT perp trades (public.bybit.com).
- Cluster activity of the current development block (`code4/live_activity.py`, from 12:00 UTC) and the live
  recorder's books (`code4/livex.py`).
- tools/live.py note: `iter_live` raises `zlib.error` on an hourly file that is still being written (it only catches
  EOFError/OSError), which ends the generator. `code4/livex.py` reads the same dev files and stops a file there.

**B1 findings (calldata of the cluster's own orders)**
1. **No signing time.** All 8,256 STUDY and all VALIDATE cluster orders carry `timestamp = 0`, `metadata = 0`,
   `builder = 0`. Other makers set millisecond timestamps (0.66% of their orders have 0, all from one unrelated wallet,
   0x56f609c6, with random uint32 salts). So B1's decision-time measurement is impossible for this cluster; the
   taker's signing ms in the same match is used as the match clock instead.
2. **The salt is a per-wallet order counter.** Salts are small integers that increase with time (97-98% monotone
   between consecutive fills), restart near 0 in the same minute in all three wallets, and are shared by all markets
   a wallet trades (other-market orders within 30 s of a BTC 5m fill have salts within 1% in 84% of cases).
   Restarts: daily at 01:00-01:08 UTC (10-23, 24, 25, 26, 28, 30) plus ad-hoc ones (10-26 16:38-16:42 and
   19:36-19:39; 10-28 13:00-13:03 and 19:55-20:01). One scheduled process (or three restarted together) signs every
   order.
3. **Signing rate = requote intensity.** About 10-23 orders/s per wallet (median 13). It rises with Binance activity:
   Spearman 0.67 with the hourly number of Binance 1-s price changes; in 60-s buckets by |return| quintile 10.9 ->
   14.3 -> 15.5 -> 19.2 -> 22.7 orders/s. An event-driven requote engine on top of a ~10/s base loop (E1 supported).
4. **BTC 5m on/off is not a process stop.** During the BTC 5m off periods (10-24 02-15 UTC, 10-25 02-13 UTC) the
   counter kept running at the same rate (11-12/s, vs 11.7-12.1/s in on hours of the same days) and the wallets kept
   filling in other markets. The switch is made inside the running engine (a per-market enable), not by restarts.
5. **Order sizes follow a clock schedule.** Weekdays: 500-share orders from 12:00 UTC (first 500-share order at
   12:00:04-12:00:54 on 10-26..30) until about 21:00 UTC (on some days until midnight); nights and the weekend: 62
   shares (10-23..28) or 250 (nights of 10-29/30). A second level of one fifth (100 / 12 / 50) is common. STUDY: in
   the US session 75.7% of orders are 500; at night or on the weekend 65.3% are 62. VALIDATE (aggregate): 70.4% /
   38.8% (+25.7% at 250). Returns follow the schedule: US session +4.7% (STUDY) / +5.1% (VALIDATE) on dollars bought,
   night and weekend +0.4% / +3.3%. It sizes up when its edge is largest.
6. **Rewards are not the motive (E2 ruled out).** 88% of STUDY orders have >= 50 shares (98.7% of dollars), but the
   REWARD rows of all three wallets over 2026-10-22..30 total $0.81. MAKER_REBATE rows total $4,975 (8% of the lot
   PnL).
7. **Signatures.** almach and bosona: signatureType 3 (317-byte wrapped signature: 65-byte ECDSA, a domain separator,
   a struct hash and the Order type string), signer = maker. mo-money: signatureType 2 (Gnosis Safe), signer = EOA
   0xd1f9bc03d7395134647c6a7d3b468cfdd4b38292, which signs for no other maker in the sampled transactions.
8. **No same-engine sibling (E6 ruled out for this fingerprint).** In 7,500 sampled public BTC 5m txs (5,000 in the
   off periods, prints >= 20 shares) no maker other than the three has timestamp 0 with a counter salt (< 3e6).

**Timing at millisecond resolution (10-26, STUDY): the requote window.** Match clock = the taker order's signing
ms. Mean Binance move (USD) over the last L ms, signed so that < 0 is adverse to the maker's token: cluster +0.02
(100 ms), -0.24 (250 ms), -0.35 (0.5-1 s), +0.14 (2 s), +0.79 (3 s); other makers (public sample) -0.29, -0.78,
-0.9 to -1.0 (0.5-3 s); random times about 0. Share of fills after an adverse move > $5: in the last 250 ms cluster
4.1% vs others 7.2% (random 1.4%); in the last 1 s 9.8% vs 12.5% (6.0%). Other makers' orders older than 5 s are hit
after adverse moves about 4x larger than fresh ones (-2.2 to -2.4 vs -0.5 USD at 1 s). So the cluster is exposed only
to moves of the last ~0.25-1.5 s. Older moves are already in its quote (it requotes within about a second; other
makers take 3-5 s), and its fills follow a favourable 2-5 s move of its token.

**B3/A3 reference.** Limit prices of filled orders vs the TWAP-60 fair at the match clock (10-26): cluster corr
0.838 with spot at 0 s, peaking 0.25-0.5 s after the taker's signing (0.840) and falling to 0.744 at 3 s before; with
a Binance USD-M futures fair 0.846 at 0 s (0.852 at +0.25 s). Other makers: spot 0.814, futures 0.846. The futures
fair explains everyone's quotes better (perps lead spot); the cluster shows no lead of its own over other makers.
Presence with futures features (fair, z, edge, 1-10 s returns, futures-minus-spot lead, basis, flow imbalance) on
BUILD4 -> VALIDATE: 0.7142 vs 0.7135 without (side 0.662 vs 0.657). Not adopted (a second archive for +0.0007).

**Why the presence AUC is capped (oracle diagnostic, VALIDATE aggregate).** Giving the model the future clean taker
flow of the bin itself (bid hits and volume on s and on the other side in [t, t+10)) reaches only 0.682 alone and
0.730 with R2's features (within active windows 0.674 / 0.723). In active windows 89.5% of bins have bid hits on s,
but the cluster is filled in only 11.7% of them (0.8% without hits). The missing variable is not taker arrival. It is
whether the cluster's bid is at the top of the book at that moment (its quote vs the competitors' quotes), which the
historical tape does not show. Only books (the live lab) or a book rebuilt from every match's calldata can show it.

**Live lab pilot (2026-10-31 12:18-13:00 UTC, development block).** 15 cluster BTC 5m maker fills with a recorded
book: the fill price equals the best bid of its token 2 s before the block in 11 of 15 (one or two ticks below in 4),
spread 0.01 in 11, depth at the fill price median 1,246 shares (it shares a deep level). Too few fills today
(Saturday, low activity) for a model. The recorder now accumulates development blocks (12 h a day).

**Refits and the clock (presence, BUILD4 = 2026-10-09..26 -> VALIDATE4 = 2026-10-27..30, aggregate).** Frozen R2
0.7051 (baseline 0.6734). R2 features refit on BUILD4 0.7135 (refit baseline 0.6843; 10-16..26 only 0.7115; lot first
half only 0.6867). Plus the clock (UTC hour, weekday, US-session flag): **0.7159** (within active windows 0.708, side
0.663). Activity + clock 0.692; + own inventory 0.747. R3 = refit + clock (frozen in `code/final_rule.py`; R2 is
archived as `code/final_rule_r2.py`).

**More iteration-4 measurements**
- **Price anchor by the last print's direction (STUDY case by case, VALIDATE aggregate).** Using the last clean
  print itself when it hit a bid on s and print - 0.01 when it lifted an ask raises exact matches (VALIDATE 0.450 vs
  0.359) but lowers within-one-tick (0.675 vs 0.709): after a bid hit the cluster is often filled two ticks lower (the
  hit level was used up). Adding the Binance fair move since that print does not help (0.645-0.687). R2's anchor
  stays. STUDY error of R2's anchor: after an ask lift 44% exact, 14% one tick low; after a bid hit 31% one tick high.
- **Side baselines (the brief's two).** Own-inventory-only (side with more own shares bought so far): VALIDATE 0.575
  where it holds inventory (83% of one-sided bins), 0.594 with R2 as fallback; market-activity-only model 0.613; R3
  0.663 (R2 0.652). STUDY: 0.603 / 0.643 / R2 0.663.
- **Cross-horizon side (E7).** In 5-min slots where it buys both BTC 5m and the overlapping BTC 15m window, the net
  direction agrees in 70% of slots where both are one-sided (n = 66, corr of net Up share 0.30); with BTC 4h 52%. One
  short-horizon directional view across markets, not hedging (E7 hedging rejected).
- **Listings.** BTC 5m Gamma records (2026-10-26, three windows): rfqEnabled False, holdingRewardsEnabled False,
  negRisk False, makerRebatesFeeShareBps 10000, feeSchedule rate 0.07 takerOnly rebateRate 0.2, rewards 50 / 4.5.
  B8 and C6 are not applicable.
- **Self-matching (C7).** No transaction in STUDY BTC 5m (7,777) has a cluster wallet as taker against a cluster
  maker; 2 of 6,026 other-market transactions do. No circular volume.
- **Weekend nights.** BTC 5m was off overnight on Sat/Sun 10-17/18 and Fri/Sat 10-23/24 (21:00-23:00 to 12:00-15:30
  UTC), but fully on during 10-10/11 and on the night of Fri 10-30 -> Sat 10-31 (00-06 UTC development block: 102-400
  BTC 5m trades an hour). So it is not a calendar rule; the switch stays an operator decision (hypothesis).
- **Off switches vs own PnL.** The 10-23 20:39 stop followed a -5.8% 6-h (-6.6% 24-h) BTC 5m return; the 10-24 22:27
  stop followed +6.8% (+9.8%). Not consistently loss-triggered (STUDY 6-h returns range -9% to +14%).
- **Live lab tooling.** The shared recorder was restarted at 12:18 UTC inside an hourly file, leaving a truncated gzip
  member at its start; `tools/live.py` `iter_live` loses every record after the truncation and stops with zlib.error
  on files still being written. `code4/livex.py` decompresses each gzip member separately (same dev folder, same
  filter) and recovers 2026-10-31 12:07-13:12 UTC (81k book updates, 22k full books, 19k trades). The recorder's rtds
  feed wrote no records (330 messages, 0 written at 12:50 UTC). `code4/live_panel.py` builds per-bin book features
  (best bid/ask of the side, spread, depth, updates, best-bid age) with the cluster's fills as labels: 11 windows, 660
  bins, 23 positive bins so far. Positive bins sit on cheaper sides (best bid median 0.24 vs 0.61), deeper best levels
  (678 vs 431 shares) and younger best levels (1.1 vs 2.3 s). Descriptive only.

- **What the quote state does not depend on (VALIDATE aggregate, active windows, 56,561 bins with bid hits on s).**
  P(cluster filled | bids on s hit in the bin) is nearly flat in our edge (fair - last print) deciles, 0.06-0.17
  and U-shaped; it falls with the side's fair (0.175 below 0.1, 0.063 above 0.9) and rises with the number of hits in
  the bin (1 hit 0.039, 2-3 0.038, 4-9 0.067, 10+ 0.130). Being at the front of the book is not "our fair is above the
  market": it behaves like queue mechanics at a shared best level (the live pilot's fill levels held a median 1,246
  shares), where it is filled when takers use up the orders ahead of it. Next step: measure its queue position from
  book depth changes in the live lab (and whether its 10-23 re-signings per second keep or lose time priority).

- **Queue position from the match calldata (STUDY, 3,238 cluster orders in multi-maker matches).** Within a match,
  other makers at the same price appear in signing-time order (71% of 16,157 consecutive same-price pairs signed
  later, 24% earlier: price-time priority with client-clock noise). The cluster is first at its price level in only
  31% of these matches; in 2,220 other makers at its price were filled ahead of it. It sits at the best price (90% of
  sweeps) but usually behind part of the queue, so it is filled when a taker uses up the orders ahead of it, which is
  why fills need many or large bid hits. Bounds on its join time from neighbours' signing ms are too noisy (client
  clocks) to time its quotes (median: joined within ~0.2-0.5 s of the match, wide tails).

- **Queue-level features from the tape (rejected).** Age of the current bid level on s, its price and its number of
  changes in 10/30 s (bid-hit prints of the clean tape): R3 + level 0.7158 vs R3 0.7159; activity + level 0.6851 vs
  0.6843. The tape cannot see the queue.
- **PnL decomposition (D4; STUDY case by case, VALIDATE aggregate).** Per window, locked pairs = min(Up, Down shares)
  x (1 - average Up price - average Down price), directional = the rest. STUDY: total +$4.8k (+2.7%), locked +$0.3k
  (+0.4% on locked dollars), directional +$4.5k (+4.6%). VALIDATE: total +$23.7k (+4.3%), locked **+$38.1k (+11.0%
  on $347k locked)**, directional **-$14.4k (-7.3%)**. In the busy second half it earned by buying both outcomes
  cheaply at different moments of the window (average Up + Down price 0.89 on the paired shares), and lost on the
  unpaired residual. The dossier's "profit is the directional residual, the locked pair spread is about zero" held in
  quiet periods (STUDY), not in the busy one: it is a two-sided liquidity provider whose round trips across the two
  outcomes pay, with a losing directional remainder.
- **Copy / follow (C2, STUDY).** For 3,448 cluster fill events, the wallets that BUY the same token within 30 s
  after a fill are the same high-frequency takers that bought it within 30 s before (0xc53375ff 0.73 after vs 0.80
  before; next four 0.50-0.59 vs 0.48-0.63): co-activity, no leader or follower asymmetry. The strong form (fixed size
  ratio, same side) was not tested.

- **Cross-asset (A4).** Binance ETH and SOL 1-s returns over 1-30 s (signed by side) and their 1-5 s lead over BTC:
  R3 + ETH/SOL 0.7149 vs R3 0.7159 (side 0.663 both). No gain. Overlapping 15m/1h/4h window prices not tried yet.

- **Operational events in the live feed (A8).** The recorder's 'c' records (39 on 2026-10-31 12:07-13:30 UTC) are tick-size changes 0.01 -> 0.001 (the dynamic tick at extreme prices). No matching-engine restart events in any public feed found yet.

- **Merges (B4, STUDY).** It merges exactly its paired Up+Down amount (merged/paired median 1.0) in 87 of 662 BTC 5m windows with paired shares, a median 65 s before the end (10-90%: 165-12 s before); otherwise it holds to resolution (2,052 REDEEM rows, $155k).

- **Book from every match's calldata (pilot, STUDY 2026-10-26 13:00-13:30 UTC, 6 windows, all 9,778 match txs).**
  Each match's filled maker orders expressed as bids on a side (BUY s, or SELL of the other outcome at 1 - p). The
  cluster is filled at the best filled bid in 104 of 9,778 bid-hit events (1.1%; 113 with it anywhere). Where it is,
  fewer other makers share that price (median 0 vs 1) and they are older (median age at the match 3.7 s vs 0.8 s;
  youngest 1.7 s vs 0.5 s). At levels where another maker's order is under 0.5 s old the cluster is at the top in
  0.1% of 4,680 events. So it is not the fastest maker in the book: sub-second makers own the freshly repriced levels,
  and the cluster is filled where its price stands alone or ahead of older orders (more often on cheap sides, p < 0.1:
  3.2%). The rule's quote-state problem is "where does its price beat older competing orders", which needs the book.

## Iteration-4 checkpoint
- Primary metric (presence AUC, no own state, VALIDATE = 2026-10-27..30): **0.716** with rule R3 (frozen R2 on the
  same days 0.705; activity-only baseline 0.685, gain +0.032 < 0.05). Side 0.663 (baselines 0.613 activity, 0.594
  own inventory), price within one tick 0.709, PnL corr 0.329 / 0.325, selection 0.685 (recall 29%, lift 2.9).
  Per wallet: presence 0.705-0.712, side 0.654-0.666, price 0.706-0.710, PnL Pearson 0.29-0.32. Target not met.
- What is decoded now (component by component): engine and restarts, requote intensity and its sub-second exposure
  window, the clock schedule of order sizes, the absence of rewards and same-engine siblings, the side's link to a
  shared short-horizon view. What is not: the quote state (when its bid is at the top), which an oracle-flow test shows
  is the binding gap (presence 0.73 even with the bin's own future taker flow), and the BTC 5m on/off decision.
- Verdicts on the competing explanations: E1 (fast top-of-book maker) supported (signing rate follows Binance, sub-second exposure window, at the best price but often behind the queue); E2 (rewards) ruled out ($0.81); E3 (better settlement estimate) not supported (no lead over other makers; futures fair explains everyone; Chainlink not recorded); E4 (operator schedule) supported for sizes (clock) and for the BTC 5m switch (runtime, not restarts, not a calendar rule, not consistently after losses); E5 (pre-positioned ladder) rejected (requotes 10-23/s; orders consumed in seconds); E6 (same-engine siblings) ruled out in samples; E7 (cross-market hedge) rejected (5m and 15m directions agree 70%); E8 (copy/predictable flow) not supported in the weak test. Economics: in busy periods paired round trips across the two outcomes pay (+11% on paired dollars) and the directional remainder loses.
- Status: continue. Paradigm for the next iterations: the quote itself, from books. (1) Live lab: with the
  tolerant reader, build per-bin book features in every development block and fit presence = P(top of book) x taker
  arrival. A rule with book inputs can be examined on the future sealed blocks, which the recorder also covers.
  (2) Rebuild the historical book from the calldata of every BTC 5m match (each filled maker order gives price,
  original size, signing ms and fills; an order filled at time f was resting from its signing until f), first for a
  few STUDY hours, to measure the competitors' best bid when the cluster is and is not filled. (3) Recover the owner
  EOAs of almach and bosona from their wrapped signatures (ERC-1271) and search for the same signer elsewhere.
  (4) Coinbase / OKX ms trades and a composite (A2), cross-asset moves (A4), Kalshi (A4b), matching-engine events
  (A8, X7), hazard / HMM models (D2), an own sub-second replay (D3).

### Iteration 5 (2026-10-31, local Windows laptop, started 13:59 UTC; 225 of 1,200 budget minutes used before it)

Read first: NOTES, state.json, FINAL_RULE.md, panels/iter4_{information,mechanics,assumptions}.md, EXAM.md. The 16 panel
proposals are catalog items X10-X25 (state.json). Split unchanged (BUILD < 2026-10-27, STUDY = 10-23..26 case by case,
VALIDATE = 10-27..30 aggregate only; development live blocks after T0 = extra description data). Primary metric unchanged.
Shared recorder running (pid 27184). Own raw-event recorder `code5/rawrec.py` started 14:04 UTC (restarted 14:06 to add
the futures aggTrade stream, which Binance now serves only under `fstream.binance.com/market/stream`; the old
`/stream` path delivers bookTicker only), hard stop 18:00 UTC (end of this development block), feeds `dm_*`.

**Competing explanations (iteration 5) and what separates them**
1. H1 fast fair-value requoter (E1): quotes = f(Binance futures fair) re-signed every ~1 s; edge = spread minus a
   smaller adverse selection than slower makers. Separates: its fingerprinted quotes in the raw book move within a
   fixed lag (tens to hundreds of ms) after futures moves; quote prices sit at fair - h, not at the touch.
2. H2 book-pegged back-of-queue joiner (panel P2/P5): it joins the best bid (price set by the book, not by fair) and is
   filled only when a taker clears the level; edge = level-clearing takers are large uninformed sweeps. Separates:
   P(cluster in the match | the hit clears the level) >> P(... | not clearing); its quote = best bid whatever the fair.
3. H3 post-only race at the touch (panel Q3): most signed orders never rest; it fires post-only orders at the new touch
   right after a reprice and is the youngest order there. Separates: posted/signed << 1 at its size class; adds live
   < 1-2 s and cluster 100-500 ms after futures moves.
4. H4 settlement-informed (E3): prices off Chainlink TWAP-60 vs the true priceToBeat. Separates: in windows where the
   Binance proxy outcome is wrong, its late net side follows the true outcome (panel I5); RTDS-based fair beats the
   futures fair on quote residuals.
5. H5 risk controller (panel Q5): markets and size classes are switched by rolling markouts. Separates: switch-offs
   follow drops of market-wide or own markouts; on/off AUC from markouts > 0.7.
6. H6 cross-outcome round-tripper: profit is buying both outcomes cheaply at different moments (pair cost 0.89 in busy
   periods), with a flatten-and-merge exit (panel P4). Separates: its complement bids tighten as the held side's
   average cost falls; exact-size complement taker buys after adverse moves.
7. H7 one cross-market engine (panel Q1): BTC 15m/hourly/4h and ETH/SOL quotes are the same function with horizon
   parameters; BTC 15m loses. Separates: per-family price/side rules transfer; coverage needs the union.
This iteration discriminates H1/H2/H3 with the raw recorder (live, development block) and the historical
level-clearing test, H4 with the disagreement windows, H6 with the flatten rule, H7 with coverage by family.

**Data added (iteration 5).** (1) Own raw-event recorder `code5/rawrec.py` (tools/live.py Writer, dev/sealed by block, feeds
`dm_*`, hard stop 18:00 UTC, disk cap 280 MB, ~12 MB per 40 min for the CLOB feed): every CLOB market-channel message of the
current and next BTC 5m and the current BTC 15m window (price_change rows of the Up token, book snapshots, last trades with
tx hash, server ms); Binance USD-M futures bookTicker (`/stream`, every size change from 14:22:43) and aggTrade (served only
under `fstream.binance.com/market/stream` now: the old path returns bookTicker only), Binance spot, Coinbase ticker, OKX
swap, Bybit perp, Hyperliquid, and RTDS with one connection per topic reconnected every 25 s, staggered (~99% second
coverage vs ~52% in the shared feed; the `crypto_prices` subscription returns nothing). Read with `code5/rawread.py`, which
splits files at real gzip member starts (a member cut by a restart keeps its complete lines; my first reader lost whole
members). Restarts at 14:06 and 14:22 (feed fixes) and 14:41 (detached, so it survives the iteration; status in
`.cache/re/directional-maker/rawrec_status.json`). (2) Cluster activity of the block and calldata of its live txs, plus
calldata of all 797 trades of 14:10-14:13 UTC. (3) BTC 15m windows and taker tapes 2026-10-09..30
(`.cache/re/directional-maker/t15/`, 148 MB, `code5/fetch15.py`).

**Historical tests (development data; VALIDATE aggregate only)**
- **Q1 coverage (X21), `code5/coverage5.py`.** Cash-flow PnL per market (SELL + MERGE + REDEEM - BUY - SPLIT; redemptions
  arrive ~90 s after the end). VALIDATE: BTC 5m 78.3% of fills / 68.6% of absolute PnL (+$23.0k, +3.9%); BTC 15m 8.5% /
  20.5% (+$28.3k, +30.5% on dollars bought); BTC 5m + 15m 86.8% / 89.1%. STUDY: BTC 5m 53.6% / 55.5%; BTC 15m 9.1% / 19.2%
  (-$6.3k, -13.3%); 80/80 needs six families (BTC 5m, 15m, hourly, XRP 5m, ETH 15m, BTC 4h: 82.7% / 92.4%). A BTC 5m-only
  rule cannot meet the scope condition in quiet periods. `coverage_abs_pnl` of R3's universe on VALIDATE = 0.686.
- **BTC 15m transfer (`code5/q1_15m.py`).** 94-97% maker; R3's price rule (last clean print - 0.01) is within one tick for
  65.6% (STUDY) / 66.6% (VALIDATE) of its 15m maker fills (BTC 5m 70.9%); fills sit late in the window (median 718-726 s of
  900, p10 331 / 72 s): the engine works the 15m window mostly in its last five minutes. Same engine, horizon parameter.
- **P2(a) level clearing (X16), `code5/clear5.py`.** 938k bid hits in STUDY: P(cluster in the tx | the next hit on s is lower
  = level cleared) 0.63% vs 0.85% when the level holds (stratified rate ratio 0.63); 83% of the cluster's prints are followed
  by a hit at the same or a higher level. The strong form ("filled only when a hit uses up the level") is rejected. P(cluster)
  rises with print size (4.8% for prints > 200 sh) and with volume already absorbed at the level (0.75% -> 1.27%).
- **I5 settlement-disagreement windows (X14), `code5/disagree5.py`.** The Binance-TWAP proxy outcome is wrong in 1.8-2.6% of
  windows. The cluster's net shares at end - 30 s follow the real outcome in 7/10 (STUDY), 18/30 (VALIDATE), 38/65 (BUILD) =
  60% pooled (one-sided p ~0.02) while the last clean print follows it in 85% / 73%; near-strike decile 51% vs 80-85%. Over
  all VALIDATE windows its late net side wins only 40.7% (its profit there came from paired shares). Not settlement-informed.
- **P4 flatten (X18), `code5/flatten5.py`.** 219 STUDY / 621 VALIDATE BTC 5m taker buys: 72% / 83% buy the under-held side;
  size = imbalance exactly in 46% / 42% (median ratio 1.0 / 0.80, p25 0.2: the one-fifth level); pair cost median 1.12 / 1.06
  (10-90%: 0.82-1.42 / 0.72-1.32); median 176 / 115 s into the window; a MERGE follows in 17% / 51%. Taker-fill PnL +$215 /
  +$422 (4% / 2% of the period PnL); maker-maker pairs are 89-90% of paired shares. Real but small.
- **Q2 size in the PnL metric (X22), `code5/q2size5.py`.** VALIDATE (1,089 windows): per-share R3 rule 0.329 / 0.325; x public
  clock size (500 in the weekday US session else 62) 0.321 / 0.283; x own-state size (largest own BTC 5m fill in the previous
  30 min, reported separately) 0.341 / 0.288; ceiling (its own fills at one share) 0.688 / 0.780. On STUDY (inside R3's BUILD)
  0.466 -> 0.499 / 0.520 with size. Size is not what keeps the PnL correlation below 0.5 on VALIDATE.

**Live lab (development block 2026-10-31 14:04-14:45 UTC, quiet Saturday; descriptive, not VALIDATE)**
1. **Sizes today: 500 with a 100 second level**, plus re-signed remainders (492.44, 76.38, 51.x): a partially filled order is
   re-posted with the remainder. The clock schedule (62 at weekends) is contradicted.
2. **Signed ~ posted (X17, X23).** Salt slopes 16.7-17.2 orders/s per wallet (51/s for three, all markets); exact-500 and
   exact-100 adds in the three recorded BTC markets alone run at 7.1 + ~14 per second (sizes 499/501 almost never). Orders are
   not post-only (one 500 BUY at 0.66 matched first as the taker, its remainder later as a maker, same salt).
3. **The three-wallet signature.** Exact-500 adds come in bursts on the same side of a market within 20 ms: 1 add 49.5%,
   2 adds 22.4%, **3 adds 27.4%, 4+ adds 0.6%**, 88% at one price. Bursts of 2-3 are the three copies of the engine posting
   the same quote (3,460 bursts in 31 min, half in BTC 15m). The size class alone is shared with other makers (a resting 500
   at the hit level raises P(cluster in the trade) only to 12.5% from 0.96%; `iter5_live_f`).
4. **Its filled orders were posted just before the match** (`iter5_live_j`): an add of exactly the order's original size at
   its level within 250 ms / 1 s / 5 s before the match for 29% / 46% / 80% of its 138 filled maker orders, vs 3.6% / 5.8% /
   14.5% at the same level 20 s earlier (null); 63% were posted at the touch.
5. **Requote cadence.** Each side's burst quote is re-posted about every second (median 0.98 s, p25 0.48 s, p75 1.9 s) at a
   new price 96% of the time; cancel-to-re-add 15 ms; Up and Down are re-posted independently (0.4% within 50 ms).
6. **Reference feed = Binance USD-M futures (X10, A2).** Direction of the next re-post vs each venue's move over the previous
   window: near-touch 500/100 re-posts follow the futures bookTicker mid in 97% (50-250 ms, n 77; 0-500 ms 92.5%; 1-3 s 62%);
   the cluster's bursts 89.5% (0-100 ms, n 38), 85.5% (0-250 ms), 51% (0.5-2 s). Bybit perp 57-74%, OKX swap 59-68%, Coinbase
   41-53%, Binance spot 53-55%, Hyperliquid 40-53%; the futures microprice (size-weighted) 55-62%. But 94% of near-touch
   re-posts follow no futures mid move in the previous 0.5 s (quiet market): between futures moves the re-posts follow the
   Polymarket touch of the token (89% of 396 cases with a touch move in the previous 250 ms). Rerun on 14:06-15:00 UTC (55 min): near-touch re-posts agree with the futures mid move over 50-250 ms before in 91% (n 255; 0-100 ms 76%, n 115; 0-500 ms 89%, n 451; 1-3 s 55%), Bybit 70%, OKX 66%, Coinbase 52%, Binance spot 55%, Hyperliquid 48% (`iter5_live_c_1793455600_1793458800.json`): the reaction comes mostly 50-250 ms after the futures move.
7. **Quote level.** Burst quotes: OLS q = -0.055 + 0.246 x futures fair + 0.688 x token mid (residual MAD 0.037, within one
   tick 14.5%); q - mid median -0.075 (MAD 0.04), q - futures fair -0.080 (MAD 0.045, corr 0.93); 51% of burst quotes sit 8+
   ticks below the touch and 5% at it. The gap widens near the end (q - fair -0.07 with > 2 min left, -0.18 at 60-120 s, -0.27
   in the last minute) and above fair 0.8 (-0.19). The cluster's ladder rests well below the touch and is filled when the
   market comes down to it. (Near-touch 500/100 adds fit fair - 0.02 with MAD 0.03, but that subset is selected on the touch.)
8. **Quote state vs fills (`iter5_live_k`).** In 2,312 window-side seconds of four BTC 5m windows the cluster's latest burst
   quote is at the token's best bid 3.9% of the time; P(fill in the next 10 s) is 28.9% then vs 10.0% otherwise (AUC 0.54);
   its quote minus the best bid ranks fills at AUC 0.62, the futures edge at 0.59. Too few windows for a model yet; the
   at-touch state explains only a small part of its fills.
9. **Settlement source (A1, X12).** RTDS `crypto_prices_twap_sixty` stamped at the window end equals Gamma `finalPrice` to 4+
   decimals (3/3 windows); the Chainlink 1-s mean over [end-60, end) equals the TWAP stamped one second later. Near-touch
   quotes vs a Chainlink TWAP-60 fair: MAD 0.105 / corr 0.90 vs futures 0.037 / 0.97 (the +0.08 median offset of the Chainlink
   fair needs a recheck of its stamping before it counts as more than indicative).

**Verdicts on the iteration-5 explanations.** H1 (fast futures-fair requoter): supported in part: it follows Binance futures
within ~250 ms when they move (85-97%), but its level is mostly anchored to the Polymarket mid (weight 0.69) with a fair
component (0.25) and a time-left widening. H2 (book-pegged back-of-queue): the level-clearing form is rejected on the tape;
the quote is book-anchored, though, and usually rests well below the touch. H3 (post-only race, signed >> posted): rejected.
H4 (settlement-informed): not supported. H5 (markout controller): not tested. H6 (round-tripper with flatten): the flatten
exit exists but carries 2-4% of PnL. H7 (one engine across horizons): supported (same price rule within 4 points in BTC 15m,
the same burst quote stream in BTC 15m live, the 15m window worked in its last five minutes).

- **Late addendum (live, 14:04-14:43 UTC).** The burst quotes form a ladder: within 1.5 s a side shows 2+ distinct burst
  prices 65% of the time (2-4 ticks apart in 55% of those), and only 44% of bursts follow a 500-removal on the same side
  within 50 ms, so each wallet keeps several 500-share rungs per side and re-posts them one by one. A held-out-in-time
  LightGBM of the burst price on (futures fair, token best bid and ask, time left, horizon, side) is within one tick for
  only 20.8% (MAD 0.04) of the later 40% of bursts, no better than "best bid - 7.5 ticks" (21.3%; `iter5_live_quotefit.json`).
  So a single quote function of public inputs does not exist at tick precision: the next iteration should model the rung
  structure (rung index, spacing, which rung is re-posted when) and the at-touch rung only.

- **Skew vs own inventory (X20, live, own state, descriptive).** Burst quote minus the token mid: -0.085 when flat or long 1-200 shares, -0.18 when long > 200 (n 77), -0.105 / -0.125 when short (n 366 / 107); slope ~0 per 100 shares. It does not bid higher on the side it holds, so its "adds to the held side" pattern is not a quote skew.

- **X13 DVOL (`code5/dvol5.py`).** Deribit DVOL 1-min for the lot (public API works). Fill prices vs a TWAP-60 digital fair: realised 1-s vol x 1.4 (fitted on STUDY) gives VALIDATE MAD 0.043 (per-day best k 1.0-1.4); DVOL x k is best at the grid edge k = 0.6 with MAD 0.062 and an unstable per-day k (DVOL/realised median 1.62). Its vol input is short-term realised vol scaled ~1.2-1.4, not implied vol.
- **X25 markout controller (`code5/markout5.py`).** Trailing market-wide maker returns of the clean tape (12/36/72 resolved windows) predict window activity at AUC 0.524 (fit 10-10..19) / 0.474 (test 10-20..26) / 0.480 (VALIDATE agg.); own markouts 0.546 / 0.475 / 0.487. Rejected.
- **Shared-feed visibility.** The shared recorder's 200-ms top-10 snapshots show exact +1000 / +1500 increments (122 / 65 in 20 min, neighbours ~0) but only 10-11% of the raw bursts appear as an exact increment (57-64% inside a larger change): a rule fed by the shared recorder sees the cluster's quotes only partly.
- **Live presence pilot (`results/iter5_live_presence.json`).** Six BTC 5m windows (360 bins, about 14 positive test bins): too small to read; no conclusion.
- Clock note: the detached recorder restart was at 14:41 UTC (not 14:48); the live analyses cover 14:04-14:45 UTC.

- **A1_B3b last-60-s lock-in.** Fills in [end-60, end): prices fit a TWAP-60 lock-in fair (known part of the closing average + remaining spot) far better than a spot-only fair (MAD 0.068 vs 0.141 STUDY, 0.087 vs 0.138 VALIDATE agg.); where the two favourites disagree, 64% (n 39) / 67% (n 294) of its fills are on the lock-in favourite. It prices the partly observed closing TWAP and withdraws (quotes 0.18-0.27 below the fair in the last two minutes live; fills fall to a third in the last 30 s).

- **C8 bot fingerprint search.** Polymarket's V2 migration docs: the signed `timestamp` is the order-creation ms and replaces the nonce as the uniqueness check; the official V2 SDKs default metadata/builder to zero bytes. The cluster's timestamp 0 with a sequential salt therefore means a custom signer. `gh search` for public Polymarket market makers and BTC 5m Up/Down bots (0xbrutusdev/polymarket-5min-crypto-trading-bot, miracle709/polymarket-market-maker-bot, KaustubhPatange/polymarket-trade-engine, and others) found no salt counter, timestamp 0 or 500/100 defaults. No public match.

- **A8 / X7 operational events.** status.polymarket.com/history lists for 10-09..31 only: 10-27 Perpetuals maintenance 08-09 UTC, 10-29 CLOB maintenance 05-06 UTC, 10-29 security incident 17:38-18:15 UTC and cancel-only 18:05-19:05 UTC. None is on the dates of the BTC 5m off-switches (10-17/18, 10-18/19, 10-23/24, 10-24/25) or of the ad-hoc counter restarts (10-26, 10-28). Not the cause.

## Iteration-5 checkpoint
- Primary metric unchanged at **0.716** (R3; no new rule this iteration). The paradigm moved from fills to observed quotes:
  the cluster's own quote events are visible in the raw book (three-wallet 500-bursts), and the reference feed and its
  latency are identified (Binance USD-M futures, <= 250 ms). The quote level is not decoded to a tick yet (residual MAD
  0.037), which is what a quote-state rule needs.
- Target metrics: R3 values unchanged; `coverage_fills` 0.783 and `coverage_abs_pnl` 0.686 measured for BTC 5m on VALIDATE
  (BTC 5m + 15m: 0.868 / 0.891).
- tools/live.py notes: the shared rtds feed's `written` counter is never incremented (records exist); `iter_live` stops at
  a gzip member cut by a restart (zlib.error not caught); `code5/rawread.py` handles both for the dm_ feeds.
- Next (iteration 6): (1) keep `code5/rawrec.py` running in development blocks (it stops at 18:00 UTC; restart it with
  `--until <block end>` in the next development block, 2026-11-01 06:00-12:00 UTC) and fit the burst-quote law
  q = f(futures fair(t - lag), token mid / touch, time left, inventory) to a tick on one block, test it on the next (D3
  replay); (2) the examinable route: a rule whose inputs are the shared recorder's books (200 ms) and Binance futures aggTrades
  archives (public the next day), predicting the cluster's quote and P(at the touch); (3) extend R3 to BTC 15m (tapes
  fetched) to reach 80/80 scope on VALIDATE; (4) open items X11 (match clock), X13 (DVOL), X19, X20 (skew vs inventory), X24
  (fast makers' maker rows), X25 (markout controller), A8/X7 (engine events), D2 (hazard/HMM), C8 (GitHub bots).

### Iteration 6 (2026-10-31, local Windows laptop, started 15:40 UTC; 288 of 1,200 budget minutes used before it)

Read first: NOTES, state.json, FINAL_RULE.md, panels/iter5_{information,mechanics,assumptions}.md, EXAM.md. The 15 panel
proposals are catalog items X26-X40 (information I1-I4 = X26-X29, mechanics M1-M5 = X30-X34, assumptions Q1-Q6 =
X35-X40). Split unchanged for the tape rules (BUILD < 2026-10-27, STUDY = 10-23..26 case by case, VALIDATE = 10-27..30
aggregate). **New pre-registered split for live-input rules (before any look at it):** live BUILD = development block
2026-10-31 12:00-15:00 UTC, live VALIDATE = 2026-10-31 15:00-18:00 UTC (aggregate numbers only); later development
blocks (11-01 06-12, 18-24, ...) extend live VALIDATE. Shared recorder running (pid 27184). Own raw recorder
code5/rawrec.py running to 18:00 UTC.

**Competing explanations (iteration 6) and what separates them**
1. J1 reactive touch-poster (assumptions Q1): the fills come from fresh 500/100 posts at the touch ~85 ms after a
   Polymarket print; the deep futures-pegged ladder is background (maybe another maker's). Separates: confirmed posts
   (calldata-identified fills whose exact-size add is in the raw book) are at the touch, fresh, and follow prints much
   faster than other makers' touch adds; side = the side just sold; price = post-print touch / printed price.
2. J2 futures-pegged ladder maker (iteration 5 H1): fills come from deep rungs pegged to futures fair and the mid that
   the market comes down to. Separates: confirmed posts deep, re-posted rungs (a same-size removal just before), futures
   moved toward the token before the post.
3. J3 back-of-queue joiner (Q3/M4): it joins an existing best level and is filled when takers use up the depth ahead.
   Separates: level size before the add > 0 (join) vs 0 (improve / new level); volume traded at the level after the
   post vs the queue ahead; post-to-fill age vs a length-biased null.
4. J4 center-skew market maker (M1/I2): both ladders hang off one reservation price; the skew is the only directional
   decision. Separates: pair sum invariant; skew explained by an input (futures, Chainlink, inventory) or not.
5. J5 flow-continuation harvester (Q4): its profit comes from later children of large non-HFT taker sequences.
   Separates: PnL by the fill's position in the taker's sequence.
6. J6 controller with few switches (M3/M5): most zero-fill windows are quoted but unfilled; the true off events are
   a handful of operator switches; size is a 2^k state machine. Separates: P(0 fills | quoted) live; the on/off oracle
   restricted to long runs; size transitions vs futures vol.
7. J7 information-fresh pricer (I1): its price is the latest Polymarket print or touch at the match clock; the block
   clock makes the price rule look worse. Separates: within-tick accuracy of "last clean print - 0.01" on server ms vs
   block time on the same fills.
This iteration discriminates J1/J2/J3 on all confirmed live orders of 14:06-15:48 UTC, measures J7 on the shared
recorder, J6 (M3) on VALIDATE in aggregate, and starts the slim exam recorder (I4) so that a live-input rule can be
examined on the future sealed blocks.

**I4 (X29) slim exam recorder, started 15:57 UTC.** `code6/examrec.py` (tools/live.py Writer, dev/sealed by block;
pid 20820 under the venv launcher 9952; status `.cache/re/directional-maker/examrec_status.json`), hard stop
2026-11-02 00:00 UTC (1793577600), disk cap 280 MB over dx_*. Feeds: dx_clob (BTC 5m current + next, BTC 15m current:
every trade with tx hash and server ms; the touch whenever it moves; the size at the touch sampled every 200 ms per
side; every schedule-size delta (5..2000) within 3 ticks of the touch; books within 3 ticks every 5 s), dx_bnf / dx_bnfa
(Binance USD-M futures bookTicker on best-price change, aggTrade), dx_rtds (staggered Chainlink + TWAP-60), dx_drb
(Deribit index + BTC-PERPETUAL ticker 100 ms), dx_bst (Bitstamp trades). Measured in three 35-s tests: the full near-touch
band was 32 MB/h, the slim format ~7-9 MB/h, so the cap lasts ~31-40 h (it covers the sealed blocks 10-31 18-24,
11-01 00-06 and 11-01 12-18 and the development blocks 11-01 06-12 and 18-24).

**Data added (iteration 6).** Cluster activity and the calldata of all its live transactions to 16:13 UTC
(`code6/live_refresh.py`; 1,742 + 741 txs, 0 bad); one compact pass over the own raw recording 14:06-16:13 UTC
(`code6/live6_extract.py` -> `.cache/re/directional-maker/it6/`: 3.06M schedule-size or at-touch book events, 28,912
touch changes, 45,523 trades with server ms and tx hash). Point-in-time convention for Chainlink (new): a Chainlink 1-s
value stamped T is usable from T + 2 s. Measured: RTDS snapshots arrive every ~28 s per topic (no streaming updates on
this subscription) and their newest value is stamped 1.2-1.8 s before the arrival (laptop clock 1.12 s slow vs the
Binance server clock; median arrival minus newest stamp +475 ms on the laptop clock, p90 +749 ms). data.chain.link (the
stream page and `/api/live-data-engine-streams-data`) answered HTTP 429 (text/html, 36,991 bytes) at 16:20 UTC: no
historical Chainlink 1-s series for the lot (catalog X42).

**Q1/M4/Q3 on all confirmed orders (X35, X33, X37; `code6/q1_confirmed.py`,
`results/iter6_q1_confirmed_1793455600_1793463203.json`).** 1,316 of 1,390 cluster BTC maker orders of 14:06-16:13 UTC
are confirmed (posting add of exactly the order's original size at its limit found in the raw book; 93% within 5 s of
the match). Placement: 78% at the touch after the add, 9.5% improved the touch, 68% joined an existing level (median
size already there 500), 67% fresh (no same-size removal on the same side in the 50 ms before). Trigger: the previous
trade in the market came a median 95 ms before the add (P <= 150 ms 0.59) vs 184-227 ms for other makers' at-touch adds
(P 0.41-0.46) and 1.6 s at random times (P 0.18); that trade sold the post's token (hit its bid) in 61% vs 42-44% for
other at-touch adds. The post price equals that trade's price in 37% (others 46-47%). Age at the match: median 0.68 s
(p25 0.2, p75 2.0 s) against a length-biased null of at-touch 500/100 orders alive at random moments of median 11.2 s:
the fills come from recent posts, not from orders that rest. Queue: at-touch joins had a median 500 shares ahead; prints
at the level between the post and the match (excluding the fill's own transaction) covered that queue in only 19%, so
the fill's own match usually sweeps the queue ahead (or orders ahead cancel); the strict back-of-queue law needs each
match's maker list (calldata) and stays open. Futures before the post (`code6/q1_fair.py`): when the futures mid moved
in the previous second (18% of posts) it moved toward the token in only 23% (other at-touch 500/100 adds 82%);
futures-fair edge at the post median +0.016 (others +0.005). Verdict: J1 (reactive touch-poster) partly supported: the
filled orders are fresh joins at the touch right after the token was sold, but the print trigger is only modestly
sharper than other makers' (0.59 vs 0.41-0.46 within 150 ms), the side rule "token just sold" is 61% (not > 80%) and the
price rule "the trade's price" 37%. J2 (futures-pegged ladder) rejected for the filled orders. J3 (back-of-queue) open.

**Q2 salt counter vs adds (X36; `code6/q2_salt.py`).** Signatures 41.6/s for the three wallets (13.3-13.8/s each, all
markets); exact-500/100 adds in the recorded BTC 5m/15m books 21.2/s; in none of 124 60-s bins do the adds exceed the
signatures; OLS adds = 0.39 x signatures + 4.8/s, R^2 0.53. Consistent with most of the 500/100 stream being the
cluster's (not proven: the intercept leaves room for foreign adds; the all-match calldata identity check is not done).

**M3 quoted vs unfilled (X32; `code6/m3_quoted.py`).** All 24 live BTC 5m windows were quoted (median 437 near-touch
500/100 adds per window); one had no fill (14:35, 324 adds, 738 prints): P(0 fills | quoted) = 0.04. On VALIDATE 94.5%
of windows are active and R3 scores 0.708 inside them (0.716 overall), so the on/off decision is not where the presence
gap is on VALIDATE; the 0.862 oracle of iterations 2-3 used the label (panel critique) and the old VALIDATE.

**I1 price on the match clock (X26; `code6/i1_price_match.py`, `results/iter6_i1_price_1793448000_1793463203.json`).**
Shared recorder trade stream, 1,519 cluster BTC 5m maker fills 12:18-16:13 UTC (98.3% of fills found by tx hash). Rule
(a) "last clean print before the match minus 0.01": live BUILD (12-15 UTC, n 550) 0.795 within a tick; **live VALIDATE
(15:00-16:13, n 969) 0.858** (exact 0.541; bosona 0.870, almach 0.854, mo-money 0.852). Trivial anchors on the same
fills: last print 0.847, touch 200 ms before the match 0.863 (contaminated by the cluster's own resting order), touch -
0.01 0.864. With the anchor at least L ms old: 0.805 (250 ms), 0.630 (1 s), 0.592 (2 s), 0.526 (3 s): the block clock
(prints seen ~1-3 s late) explains R3's 0.709. Errors: 0 ticks 54%, +1 tick (fill at the print) 28%. The price is the
trivial anchor on a fresh clock; frozen as R4's price part (`final_rule.price_match_clock`; smoke-tested on a STUDY
slice through `evaluate()` and on live VALIDATE 15:00-15:48: 0.885 with coverage 99.7%).

**M1/I2 the ladder center and the information race (X30, X27; `code6/m1_center.py`, `code6/m1_race.py`).** Exact-500
adds of the last 1.5 s on both books, 3,045 seconds of 24 BTC 5m windows: top-rung pair sum median 0.88 (h* = 0.06,
p10-p90 0.025-0.105; 0.083 in the last minute); skew F* - mid median -0.005 (IQR -0.03..+0.03), autocorrelation 0.44 at
1 s. Regressing the skew on (fair_X - mid), fitted before 15:00 UTC, held out after (1,861 s), held-out R^2:

| input X (digital fair, own pre-start TWAP strike) | lag 0 | 1 s | 2 s | 3 s | 4 s |
| --- | --- | --- | --- | --- | --- |
| Chainlink (RTDS, by value stamp; strike = true TWAP-60) | -0.03 | 0.00 | **0.206** | 0.128 | 0.02 |
| Binance USD-M futures bookTicker mid | -0.03 | -0.04 | -0.03 | -0.03 | -0.03 |
| Binance spot, Coinbase, OKX swap, Bybit perp | <= -0.01 at every lag | | | | |

(in-sample 0.198 for Chainlink at 2 s vs <= 0.08 for every venue). The peak sits exactly at the measured arrival delay of the Chainlink stream (1.2-1.8 s; the stamp check below shows the t-2 value IS the current
report on the settlement clock): **the engine's reservation price follows the Chainlink BTC/USD stream, the settlement
source, not Binance.** No exchange price at any lag reproduces it, so it is not
a delayed or composite exchange price. (Iteration 5's "re-posts follow Binance futures within 250 ms" was measured on
unconfirmed near-touch re-posts; the confirmed fills go the other way, see Q1.)

**The Chainlink input in the decision metrics (live, pre-registered split; `code6/sel_live.py`, `code6/pres_live.py`).**
Print level (M2 selection, X31): 34,109 BTC 5m prints, 1,188 fill the cluster; test = 15:00-16:13 (21,528 prints, 967
positive). Held-out AUC: activity only 0.636 (recall 24% at lift 2.1); + futures fair 0.632; + Chainlink fair (stamp <=
t - 2 s) 0.703; + both 0.747 (recall 39% at lift 2.8). Univariate: Chainlink edge 0.675, futures edge 0.525. Bin level
(the primary metric's unit, 14 test windows, 840 bins): activity 0.604, + futures 0.610, + Chainlink 0.638, all 0.641.
The Chainlink fair is the first public input in six iterations that adds clearly more than co-occurrence at the print
level (+0.07 to +0.11 AUC held out); at the 10-s bin level the gain is +0.035, consistent with the panel's view that
10-s presence is bound by taker arrival. Small sample (one Saturday afternoon); it must replicate on 11-01 06-12 UTC.

**Q4 taker sequences (X38; `code6/q4_sequences.py`, released lot).** Cluster fills are the first print of the taker's
sequence (same taker, window and sold token, gaps <= 3 s) in 67% (STUDY) / 73% (VALIDATE agg.) vs 64% of all prints: no
enrichment in continuation children. PnL by position: STUDY first prints +$3.8k (+3.1%), 2nd -1.1%, 3-5 -2.9%, 6+
+22.6% (n 929); VALIDATE first +$19.0k (+4.9%), 2nd +$6.9k (+9.2%), 3-5 -2.4%, 6+ -3.4%. By taker class: non-HFT
first prints carry the profit (STUDY +3.7%, VALIDATE +5.7% = +$19.4k), HFT takers about zero (-0.9%..+0.1%). Rejected
in the proposed form: the profit is from fresh non-HFT takers' first prints.

**Verdicts (iteration 6).** J1 partly supported (fresh joins at the touch after the token is sold); J2 rejected for the
filled orders; J3 open; **J4 supported with a new input: the center's skew follows Chainlink published ~2 s late
(held-out R^2 0.21; every exchange venue <= 0)**; J5 rejected (first prints, not continuations, pay); J6 supported for
VALIDATE (on/off nearly irrelevant there: 94.5% active, P(0 | quoted) 0.04 live); J7 supported (price within a tick
0.858 on the match clock vs 0.59 with a 2-s-old anchor).

## Iteration-6 checkpoint
- Primary metric (historical VALIDATE 2026-10-27..30, presence AUC, no own state): unchanged at **0.716** (R3 presence;
  rule R4 = R3 + the match-clock price, which needs the shared live recorder and so scores only on live blocks). A
  historical Chainlink 1-s series does not exist for us (data.chain.link 429), so the new input cannot be scored on the
  historical VALIDATE.
- Live VALIDATE (15:00-16:13 UTC 10-31, pre-registered): price within a tick 0.858 (each wallet 0.85-0.87; the trivial
  anchors 0.85-0.86, so the price rule IS the trivial anchor on a fresh clock, as the brief allows when stated); print
  selection AUC 0.747 with Chainlink + futures vs 0.636 activity only (recall 39% at lift 2.8); bin presence 0.641 vs
  0.604.
- Decoded this iteration (component by component): information = the current Chainlink BTC/USD report (the value
  stamped t-2 s, which is 'now' on the settlement clock; see the stamp check below), including its 1-s noise (the ladder
  center); timing = fresh joins at the touch ~0.1 s after the token is sold, filled ~0.7 s later; price = last
  print - 0.01 on the match clock; PnL = first prints of non-HFT takers; selection = every window quoted on VALIDATE
  and live (on/off is not the gap).
- Slim exam recorder `code6/examrec.py` (pid 20820) runs to 2026-11-02 00:00 UTC (~7.5 MB/h, cap 280 MB): the sealed
  blocks 10-31 18-24, 11-01 00-06 and 12-18 get the touch, every trade, the futures, Chainlink (dx_rtds), Deribit and
  Bitstamp.
- Next (iteration 7): (1) replicate the Chainlink center and selection result on the 11-01 06-12 development block
  (dx_* feeds) and race Deribit and Bitstamp (dx_drb, dx_bst) on it (X41); (2) build R5 = a print-level and bin-level
  rule on match-clock prints + Chainlink fair (stamp <= t - 2 s) + futures, fitted on live BUILD (10-31 12-18), chosen on
  11-01 06-12, with side = the token whose Chainlink edge at the touch is larger; (3) find a historical Chainlink 1-s
  source (X42) so the lot can test it; (4) M5 size controller, Q5, Q6, I3 still open.

**M5 size controller (X34; `code6/m5_size.py`, released lot; STUDY case by case, VALIDATE aggregate).** Base class per
BTC 5m window = the mode of the calldata original sizes of its filled orders. Weekday 12-21 UTC session: 500 in 98%
(STUDY) / 96% (VALIDATE) of windows. Outside it: 62 (276 / 353 windows), 250 (53 / 228) or 500 (25 / 74). The
off-session 500 windows are predicted by Binance futures realised 1-s vol before the open: AUC 0.76 (300 s) and 0.79
(|60-s return|) on STUDY, 0.93-0.95 (60-900 s vol) on VALIDATE; the STUDY threshold "300-s vol >= 7.5e-5 per s" gives
VALIDATE recall 0.88 at precision 0.71. The size controller is decoded to a session default plus a volatility upgrade
(VALIDATE-only). Hold times, cross-market simultaneity and the link to the off-runs are not done.

**Q2 direct identity (X36; `code6/q2_identity.py`).** Calldata of all 5,528 match transactions in the recorded BTC books
on 10-31 15:20-15:40 UTC: the cluster holds 1.6% of the 11,253 filled maker orders but **87.9% of the 207 filled orders
of exactly 500 shares** (8 other makers share the rest); none of the 161 exact-100 and 90 exact-250 filled orders are
the cluster's (23 and 6 other makers); the cluster's filled orders are 98.4% size 500. So the exact-500 stream behind
the F* center (M1/I2) is mostly the cluster's, while iteration 5's "100 second level" belongs to other makers (at least
on this day). The Q1/Q2 nulls that pooled 500 and 100 adds mix in other makers' 100s; the center race used 500 only.

**Explicit rung-reach rule and two consistency checks (live; `code6/rung_reach.py`, `code6/repost_dir.py`,
`code6/m1_race.py`).**
- Rung reach (M2 step 3, explicit): center_up = mid - 0.0053 + 0.207 x (Chainlink fair_up - mid) (fitted on live BUILD
  seconds), top rung = center - h (h = 0.065, 0.12 in the last minute); a print selling s at p reaches the cluster iff
  rung_s >= p. Live VALIDATE prints (20,624, 870 cluster): AUC of the gap 0.657; gap >= 0 flags 6% of prints and 11.8% of
  fills (lift 2.0); gap >= -0.03 flags 19% and 35% (lift 1.9). The explicit top-rung rule is weak: most fills come from
  at-touch joins, not from the modelled top rung; the Chainlink information is used better by the print-level model
  (0.70-0.75).
- Re-post direction by size class (7,259 exact-500 and 4,127 exact-100 near-touch re-posts): when the futures mid moved
  in the 50-250 ms before (4.6% / 2.8% of re-posts), the 500s moved the same way in 95.2% (n 333) and the 100s in 89.5%
  (n 114); over 50-1,050 ms 79% / 76%. So the cluster's 500 stream reacts to futures moves within 250 ms (iteration 5's
  result holds for the 500s, which are 88% the cluster's), while its center LEVEL follows Chainlink: the quotes re-anchor
  to the current mid (which other makers move with the futures) and add a Chainlink skew.
- Nowcast check: Chainlink stamped t-2 scaled by the futures change since then explains the skew slightly worse
  (held-out R^2 0.195) than the raw Chainlink value (0.206): the engine uses the latest published Chainlink value as is.

**Replication on the longest live VALIDATE (15:00-16:30 UTC; `code6/run_final_live.sh`).** Center race (2,268 test
seconds): Chainlink at 2 s held-out R^2 **0.212** (3 s 0.134; 0-1 s <= 0), every exchange venue at 0-4 s <= -0.02.
Print selection (26,063 test prints, 1,189 cluster): activity 0.637, + futures 0.638, + Chainlink 0.695, + both
**0.740** (recall 41.6% at lift 2.7). 10-s presence (18 test windows, 1,080 bins): activity 0.624, + futures 0.616,
+ Chainlink **0.667**, all 0.661; side in 171 one-sided bins: activity + Chainlink 0.655, Chainlink edge 0.62, activity
0.567, always-Up 0.561. R4 price (n 1,194): **0.828** within a tick (bosona 0.831, almach 0.830, mo-money 0.823); trivial
anchors last print 0.822, touch 200 ms before 0.845, touch - 0.01 0.842; the accuracy falls as the afternoon gets busier
(0.885 to 15:48, 0.858 to 16:13). BTC 15m windows (`code6/m1_race15.py`, 2,980 test seconds, only 961 fit seconds):
no input transfers (held-out R^2 -0.09 to -0.31); Chainlink at 2 s is again the best in- and out-of-sample (0.049 /
-0.086 vs futures 0.030 / -0.285); undecided for 15m.

**What the "2-s lag" is, and the economics of the Chainlink skew (`code6/gap_markout.py`; inline checks).**
- The RTDS TWAP-60 value stamped at a window start st equals exactly (MAD 0.000 USD over 28 windows) the mean of the
  RTDS Chainlink 1-s values stamped st-62 .. st-3. So the Chainlink price stamps run 2 s behind the TWAP/settlement
  stamps: the value stamped t-2 is the Chainlink report "as of" t on the settlement clock, and it is published by then
  (the newest value in a snapshot is stamped 1.2-1.8 s before its arrival). The center therefore follows the CURRENT
  Chainlink report, not a stale one. The sharp lag profile (0.00 at t-1, 0.21 at t-2, 0.13 at t-3) comes from the
  Chainlink series' 1-s noise: its 1-s changes have sd $9.0, 28% exceed $10, and their lag-1 autocorrelation is -0.47
  (single-second outliers that revert). The skew tracks that idiosyncratic aggregation noise, which no exchange price
  contains, so the engine reads the Chainlink stream itself.
- Economics (28 live BTC 5m windows, 1,430 fills with a match clock, settled by the RTDS TWAP rule): overall +3.8% on
  dollars bought. By gap = Chainlink fair - futures fair of the token at the fill: > +3 c (958 fills, 67%: the token is
  bought when the Chainlink report values it above the futures) -4.6% (-$680); -1..+1 c +26%; -3..-1 c +43%; < -3 c
  +1.5%. Per-share PnL correlates +0.27 with the futures edge and -0.10 with the Chainlink edge. Reading: the Chainlink
  skew (including its noise) makes the bids stand highest when Chainlink overvalues the token relative to the faster
  futures, and those fills lose; the profit comes from fills where both references agree. Small sample, descriptive.
- Point-in-time: a Chainlink value stamped T is used from T + 2 s (the settlement clock's "now"); measured arrival is
  1.2-1.8 s after T, so the margin is 0.2-0.8 s.
- Noise test (`code6/cl_noise.py`, 3,359 s): the skew correlates +0.244 (held out) with the Chainlink noise component
  CL(t-2) - mean(CL(t-6..t-3)) (+1.35 c of skew per $10), -0.12 with the same component one second later (it reverts),
  and -0.06 with the futures change over the same span. The engine reads the Chainlink stream itself.
- Exam recorder completeness (I4 step 3): 99.65% of the cluster's 866 BTC 5m/15m transactions of 15:55-16:29 UTC are in
  dx_clob's trade records; dx_rtds delivered 147 snapshots in 34 min (one per topic every ~28 s, full 1-s coverage).
- Print selection with the noise component added (exploratory): 0.724 (vs 0.740 without; small training set); the
  noise component alone ranks cluster-filled prints at AUC 0.633 (prints that sell a token right after a Chainlink
  uptick in its favour fill the cluster more often).
- Deribit and Bitstamp (X41 first look; `code6/m1_race_dx.py`, exam-recorder feeds, 15:55-16:30 UTC, 814 s, in-sample
  R^2 on the same seconds): Chainlink (from the independent dx_rtds recording) at t-2 0.247, t-3 0.144; Bitstamp
  0.026-0.030; Deribit index <= 0.001; Deribit perp mid <= 0.005; Binance futures <= 0.003. No London venue or index
  explains the skew; Chainlink does, in a second, independent recording.
- Quote-presence label (exploratory, `code6/pres_quote.py`): "an exact-500 add within one tick of the touch on s in the
  bin" (base rate 56%) is predicted at 0.630 by activity and 0.658 with Chainlink: the at-touch posting is as
  activity-driven as the fills, so this label does not open an easy route to 0.85 either.
- I3 first look (X28; `code6/i3_takers.py`, all 5,512 taker orders of 15:20-15:40 UTC): takers whose signature came
  within 300 ms after a futures mid move of >= $5 fill the cluster in 0 of 182 cluster matches (>= $3: 0.5%), against
  5.5% (7.6%) of the other matches and 0.5% at random times. Futures-triggered (latency) takers pick off other makers
  at 11x the base rate and never the cluster: its 500s re-anchor within 250 ms of futures moves. Its losing fills
  (Chainlink above futures) come from takers that are not futures-triggered within 300 ms.
- BTC 15m on the match clock (Q6 / X21 scope; `code6/i1_price_match15.py`, 312 live 15m maker fills): rule (a) within a
  tick 0.825 (live BUILD, n 114) and **0.843 (live VALIDATE, n 198; almach 0.800, bosona 0.797, mo-money 0.963)**; last
  print 0.823, touch 200 ms before 0.859. On the block clock the same rule scored 0.656-0.666 on BTC 15m (iteration 5),
  so the match-clock price rule transfers to the 15m windows; with BTC 5m it covers 87% of VALIDATE fills and 89% of
  absolute PnL, the brief's scope bar. Q6 proper (15m quotes priced off the 5m book) is still open.

### Iteration 7 (2026-10-31, local Windows laptop, started 17:21 UTC; 353 of 1,200 budget minutes used before it)

Read first: BRIEF (2026-10-31 version), NOTES, state.json, FINAL_RULE.md, panels/iter6_{information,mechanics,assumptions}.md.
The 15 panel proposals are catalog items X43-X57 (information I1-I6 = X43-X48, mechanics M1-M4 = X49-X52, assumptions
P1-P5 = X53-X57). Shared recorder running (pid 27184). Exam recorder code6/examrec.py running to 11-02 00:00 UTC.
Calendar (tools/sealed.py): development = before 10-31 06:00 and 10-31 12:00-18:00; sealed = 10-31 06-12, 18-24, 11-01
00-06, 12-18; the next development block is 11-01 06-12 UTC.

**Competing explanations (iteration 7) and what separates them**
1. K1 settlement-stream reader with a latency edge (panel M1 / I2-B): the engine reads Chainlink Data Streams directly
   and re-prices at stamp S + ~0.7 s, before the public RTDS relay publishes (S + 1.0-1.8 s). Separates: re-post
   direction steps BEFORE the relay publish ms P; engine-clock metrics >> public-clock metrics.
2. K2 public-relay reader (I2-A): it reads the same RTDS relay as the web page; its re-posts move 50-150 ms after P.
   Separates: the step comes after P.
3. K3 book-pegger (I5 null): the Chainlink skew is inherited from other makers who price off Chainlink; the cluster
   pegs to the book. Separates: other makers' near-touch adds respond to Chainlink updates first and as strongly.
4. K4 regime-specific / new version (I4, C4): the Chainlink noise (lag-1 autocorrelation -0.47) appeared on 10-31; the
   engine may always have priced off Chainlink (visible only now), or a new engine version started then. Separates:
   on the lot (smooth Chainlink regime) a Chainlink fair adds (or not) to presence, side and price over the Binance
   fair; a change point in the cluster's sizes/timing at the same hour.
5. K5 per-trade join decision (P1 / M2): after each trade that moves the touch, each wallet posts a fresh 500 at the
   new touch iff the touch is within a margin of its Chainlink-skewed reservation price. Separates: P(join | trade)
   steps at a stable threshold in gap_cl, and the two-stage selection beats the print model.
6. K6 taker-arrival bound (I3): fills are the join times the next seller; if non-HFT sellers react to the page's
   Chainlink display, their arrival is predictable from the display. Separates: sell hazard after display moves vs
   after futures moves of equal size.
7. K7 designed randomness in rung depth (M3): residual depth i.i.d. uniform -> an analytic presence ceiling.
8. K8 speed-bump liquidity provider: the ~190-ms taker speed bump lets makers re-price before any taker can react;
   the profit is spread minus adverse selection and Chainlink is only the anchor. Separates: PnL by gap source.
This iteration discriminates K4 (and the historical value of K1/K2's input) with the historical Chainlink series
(I1: the endpoint the information panel found), and starts the streaming RTDS recorder needed for K1/K2/K3 on the
next development block.

**Pre-registration (iteration 7, written before any Chainlink data of the lot was looked at).**
- Primary metric, BUILD/STUDY/VALIDATE split and live split unchanged.
- I1 sample (`code7/fetch_cl.py`): in each day of STUDY (10-23..26, fit) and VALIDATE (10-27..30, aggregate only), the
  window pairs (W_i, W_i+1) with i % 8 == 0: 288 STUDY + 288 VALIDATE windows, Chainlink stamped at every bin start
  minus 3 s (strict point-in-time: the relay publishes a value 0.97-1.81 s after its stamp, p90 1.81 s).
- Chainlink features at bin start t (stamp <= t - 3): fair_cl_s (digital of CL vs Gamma priceToBeat with the closing
  TWAP lock-in, R3's vol), edge_cl_s = fair_cl_s - last clean print, gap_s = fair_cl_s - fair_s (Binance), dcl10_s =
  signed 10-s Chainlink change, z_cl_s.
- Candidate R5 = R3 stacked with these features (logistic on logit(p_R3) + features, fitted on the STUDY sample), and
  the ablation (LightGBM with R3's features with vs without the Chainlink features, both trained on the STUDY sample).
  R5 is adopted only if its VALIDATE-sample presence AUC exceeds R3's on the same bins with a 2-h block-bootstrap
  lower bound > 0; side, price and PnL are reported alongside.

**Live lab (iteration 7).** Own streaming RTDS recorder `code7/rtdsstream.py` (feed dy_rtds, tools/live.py Writer,
filters "" so every 1-s update arrives with its server publish ms; btc/eth/sol, Chainlink and TWAP-60 topics; Binance
server-time calibration every 10 min; hard stop 2026-11-03 00:00 UTC; disk cap 60 MB) started 17:29 UTC (pid 29508),
so the sealed blocks from 10-31 18:00 have publish times for the examiner and 11-01 06-12 has them for development.

**Recorders (iteration 7).** The exam recorder `code6/examrec.py` (pid 20820) had stopped at 16:53:27 UTC (status file
not updated after 1793465607, stderr empty: killed, not crashed), so dx_* has no data after 16:53. Restarted detached at
17:41 UTC (pid 24316 via Start-Process, `--until 1793664000` = 11-03 00:00 UTC, stdout/stderr in
`.cache/re/directional-maker/examrec7_*.txt`). The own raw recorder code5/rawrec.py ran to its 18:00 hard stop. New
streaming RTDS recorder dy_rtds (pid 29508) runs to 11-03 00:00 UTC.

**Historical Chainlink endpoint (X42 / X43): verified, but slow.** `polymarket.com/api/crypto/crypto-price` answers
for any second of the lot (HTTP 200, `completed: true`). It sustains only about 1.5 requests/s from this laptop: bursts
above that get HTTP 429 (no Retry-After header; Cloudflare + Vercel, `x-vercel-id fra1::hnd1`). The shared polyrea
HttpClient blocked on the shared sqlite cache (no 400 responses in 4 minutes), so `code7/fetch_cl.py` uses httpx with an
adaptive limiter (0.25-1 s spacing) and keeps every response in `.cache/re/directional-maker/cl/cl_grid.parquet` (its
cache). The pre-registered stride-8 sample (8,830 requests) does not fit in one iteration at that rate; the fetch runs
the stride-16 half of it (pairs with i % 16 == 0: 144 STUDY + 144 VALIDATE windows, 4,320 requests); the stride-8
remainder is for the next iteration.
- Settlement check (1-s values over [st-61, st-2] and, through +300, the closing minute, three STUDY windows): Gamma
  priceToBeat = mean CL[st-61..st-2] exactly for 10-24 13:05 (80721.1471) and within $0.17 / $0.01 for the other two;
  finalPrice = mean CL[end-61..end-2] within $0.01-1.07. The endpoint is the settlement stream.
- Regime (I4 / X46): lag-1 autocorrelation of 1-s Chainlink changes in the six 60-s lot runs +0.23, +0.11, +0.27,
  -0.32, -0.03, +0.01 (sd of 1-s changes $0.65-3.17); on 10-31 17:29-17:44 (dy_rtds, five 180-s runs) -0.46 .. -0.60
  (sd $8.3-9.4). The panel's finding holds: the white-noise component (sd ~ $9/s, autocorrelation -0.5) is new on
  10-31; the lot has a smooth Chainlink stream.

**I2 / M1 / I5 pilot: the engine re-prices right after the public relay publishes (17:29-17:38 UTC, dy_rtds publish ms
P; `code7/i2_publish.py`).** RTDS publish minus value stamp p10/50/90 = 778 / 1,083 / 1,432 ms; laptop receive minus
publish 159 / 268 / 383 ms (laptop clock 43 ms off Binance). In these minutes the cluster posted almost no exact-500s
in BTC 5m (see the switch-off below), so the pilot uses BTC 15m (836 exact-500 re-posts with a price change).
Agreement of the re-post direction with dCL_S by the post's time relative to P_S: -700..-500 ms 0.34-0.43 (the
anti-agreement of a report not yet seen), 0-100 ms 0.81 (n 133), 100-200 ms 0.84 (n 127), back to 0.41-0.60 after
300 ms. Bursts (two or more same-price 500s within 20 ms): 0.885 at 0-50 ms and 0.906 at 100-150 ms after P. Other
makers' re-posts do not respond: small sizes (5-50 shares; 12,675 in 5m, 6,546 in 15m) 0.51 after vs 0.50 before;
exact-100s 0.50. So the re-price pass of the cluster's ladder is triggered by the Chainlink report and comes within
~0-150 ms of the relay's publish stamp, and no other maker reacts to it (I5: the skew is the cluster's own reading).
Caveat: P (RTDS server clock) vs s (CLOB server clock); their offset estimated from the laptop receive-time envelopes
is -131 ms (RTDS behind CLOB), which would put the bursts 80-130 ms before P; envelope estimates assume equal minimal
network latency to both services, so the engine's lead or lag relative to the relay is within about +-150 ms.
Either way, the engine acts at S + 0.8-1.4 s, when the relay publishes, not at a fixed S + 0.7 s.

**A live switch-off (X9 / X39; own state).** All three wallets' last BTC 5m trades came at 16:53:33-54 UTC, inside
window 16:50-16:55, and the cluster's exact-500 adds in the BTC 5m books fell from 276 in 16:53 to 12 in 16:54 and
0-25 per minute after (other makers' 500s), while BTC 15m continued at 200-500 per minute. That window lost $1,565 on
$2,426 bought and left the day's BTC 5m PnL (12:00-16:55) at its low, -$2,424 ($3,062 below the 15:40 peak).
Historical switch-offs (off-runs >= 1 h; `code7/stoploss.py`): BUILD 10-17 20:30 (window PnL rank 0.09, day -$901),
10-17 22:25 (0.08, -$1,546), 10-18 22:10 (0.87, -$2,337), 10-23 20:35 (0.02, -$4,618), 10-24 22:25 (0.38, +$747);
VALIDATE one (rank 0.05). AUC of "switch-off after this window" on BUILD: day PnL so far 0.80, window loss 0.71,
24-h drawdown 0.71 (5 events). A loss-limit controller is plausible (own state) but not established: three of five
historical switch-offs sit at 22:10-22:30 UTC and one followed a winning day.

**M1 step 3 (X49): the Chainlink input on several clocks, live print selection (`code7/sel_clock.py` = code6/sel_live.py
with the Chainlink value stamped floor((t - D) / 1000); same population, features, LightGBM and pre-registered split:
fit 10-31 12:00-15:00, test 15:00-16:30 UTC, 26,063 test prints, 1,189 cluster).** Test AUC of activity + futures +
Chainlink edge by D: 700 ms (the panel's engine clock S + 0.7 s, a latency oracle) 0.730; 1,083 (median publish delay)
0.740; 1,300 0.747; **1,432 (p90 publish delay) 0.764** (recall 0.44 at the BUILD top-15% threshold, lift 2.68); 1,500
0.755; 1,700 0.752; 2,000 (the iteration-6 t-2 convention) 0.728; 3,000 0.705; activity only 0.637, activity + futures
0.638. Univariate Chainlink edge peaks at D = 1,432-1,500 ms (0.693-0.695; 700 ms 0.653). The quote a print hits at t
carries the report stamped about t - 1.45 s: published about 1.1 s after its stamp, re-priced on within ~0.1 s, and hit
a few hundred ms later. This fits a public-relay reader (K2), not an engine that sees stamp S at S + 0.7 s (K1 would
peak at D <= 1 s). D was scanned on live VALIDATE (a choice made on VALIDATE, so optimistic by the scan); D = 1,432 ms
is pre-registered for the next development block (11-01 06-12 UTC). With the streaming recorder the strictly
point-in-time version is "the latest report published before t"; stamp floor((t - 1432)/1000) is published by t in
about 90% of cases.

**I2 / M1 / I5 on the full 31 minutes (10-31 17:29-18:00 UTC, development; `results/iter7_i2_publish_1793467740_1793469600.json`).**
1,801 Chainlink BTC updates with publish ms: publish minus stamp p10/50/90 = 788 / 1,091 / 1,472 ms; laptop receive
minus publish 116 / 234 / 347 ms. The cluster had no BTC 5m quotes (switched off since 16:53), so the test is on BTC 15m:
2,522 exact-500 re-posts with a price change, 43% of them in bursts. Agreement with dCL_S (|dCL| > $3) by the post's
time relative to the publish of stamp S: -1,300..-400 ms 0.35-0.44; **0-100 ms 0.705 (n 373), 100-200 ms 0.733 (n 360)**,
200-300 ms 0.62, later 0.42-0.55. Bursts: 0-50 ms 0.762 (n 168), 50-100 ms 0.805 (n 41), 100-150 ms 0.790 (n 143):
the re-price pass is bimodal at 0-50 and 100-150 ms after the publish, and 29% of all re-posts fall in the 200 ms after
a publish. On the stamp clock the agreement rises from 700 ms to 1,300 ms (0.55-0.71), exactly as the publish delays are
distributed. Other makers: small sizes 0.515 after vs 0.503 before (n 5,080 / 12,240 in 5m; 0.51 / 0.50 in 15m),
exact-100s 0.53 / 0.48. Clock check: CLOB receive minus server ms q01 -18 ms, RTDS receive minus publish q01 +55 ms,
so the RTDS clock is about 73 ms behind the CLOB clock if both services have the same minimal latency to the laptop.
**Verdict.** The engine re-prices its ladders on each Chainlink report within about 0-150 ms of the moment the public
RTDS relay publishes it (0.8-1.5 s after the stamp), and its reaction follows the relay's variable publish delay, not a
fixed S + 0.7 s. K1's latency edge (seeing the report 0.5-1 s before the public) is rejected; the remaining question
(public relay vs the same report from Chainlink a few tens of ms earlier) is below the clock resolution (~ +-100 ms).
K2 (public-relay reader) is supported; K3 (skew inherited from other makers) is rejected: no other maker reacts.

**I3 (X45): takers do not trade on the Chainlink display (`code7/i3_display.py`, 10-31 17:29-18:00, 1,801 publishes,
8,438 BTC 5m/15m trades).** Net Up selling (taker shares) in the 1 s after a publish vs the displayed change -dCL_S:
corr 0.032 (5m) and -0.013 (15m); 2 s 0.026 / -0.029; the same flow vs the futures mid move over the same second:
0.088 / 0.118 (2 s: 0.121 / 0.176). Prints after publishes with |dCL| > $10 vs < $2: 4.42 vs 3.52 per second in 5m, but
4.88 vs 3.63 in the second BEFORE the publish, so big Chainlink changes mark busy moments, not a reaction to the display.
The sellers who fill the cluster follow the futures, not the page's Chainlink price: the presence gap (taker arrival) has
no public trigger in the display. (With the cluster off BTC 5m in this half hour, this is about takers in general.)

**I4 (X46) economics across the regime change (own fills, development blocks only).** The cluster's BTC 5m trades held to
resolution: 10-31 00:00-06:00 UTC -$3,564 on $30,006 bought (**-11.9%**); 10-31 12:00-16:55 -$2,424 on $62,325
(**-3.9%**), then the BTC 5m switch-off. Historical 6-h blocks with > $5k bought (BUILD + lot, 75 blocks): median +3.1%,
p10 -9.6%, p5 -12.8%; 16 of 75 at or below -3.9% and 6 of 75 at or below -11.9%. Two consecutive losing development
blocks of this size have a probability of roughly 0.03-0.05 under the historical block distribution: suggestive that the
noisy Chainlink stream (which the engine follows unfiltered) costs it money and that the 16:53 switch-off is a loss
response, not proof (block returns are dominated by the directional residual).

**Pre-registration for the next development block (written 10-31 18:10 UTC, before any data of 11-01 06-12 exists).**
- Live primary metric (alongside the unchanged historical presence AUC): print-level selection AUC of BTC 5m prints
  (label = the print's transaction holds a cluster maker fill; the cluster's own taker prints dropped), and the same for
  BTC 15m prints, on 11-01 06:00-12:00 UTC, with recall and lift at the fit sample's top-15% threshold.
- Rule: code7/sel_clock.py's "activity + futures + Chainlink" LightGBM with the Chainlink report stamped
  floor((t - 1432 ms) / 1000) (and, as the strict variant, the latest report whose dy_rtds publish ms is <= t - 50 ms),
  fitted on all of 10-31 12:00-18:00 UTC; baselines: the same activity set, and the P3 strong activity set (sub-second
  sequence and clean-book features).
- If the cluster stays off BTC 5m in that block, the BTC 15m version is the metric.

**Control for the publish test (`code7/i2_control.py`, BTC 15m, 729 re-posts within 200 ms after a publish with
|dCL_S| > $3).** Agreement with dCL_S 0.72 overall; 0.725 (n 679) when the futures mid did not move (|move| <= $2)
during stamp second S, i.e. in 93% of the cases the Chainlink change has no futures counterpart (the 1-s noise) and the
re-post follows it; when the futures moved against the Chainlink change, the re-posts follow Chainlink 0.654 and the
futures 0.346 (n 26). The re-price pass reads the Chainlink report itself, not the exchange move behind it.

**I1 (X43) result: the Chainlink input on the lot (`code7/i1_cl_hist.py`, `results/iter7_i1_cl_hist.json`).** Sample
with Chainlink at every bin start - 3 s: 154 STUDY windows (312 positive bins) and 144 VALIDATE windows (8,640 bins,
850 positive). The frozen R3 on the full VALIDATE reproduces 0.7159 (activity 0.6843) from the lot panels.
- The Chainlink fair is almost the Binance fair on the lot: corr 0.988, |gap| median 0.010, p90 0.075.
- VALIDATE sample: R3 0.6923 -> **R3 + Chainlink stack 0.6997, gain +0.0075 (2-h block bootstrap 95% [+0.0016,
  +0.0131], P(gain <= 0) 0.007)**; better on 3 of 4 days (10-27 +0.013, 10-28 -0.004, 10-29 +0.008, 10-30 +0.014).
  Coefficients (STUDY fit): logit(p_R3) 1.23, gap_s (Chainlink fair - Binance fair) **+1.26**, edge_cl -0.76, fair_cl
  -0.69, dcl10 +0.05, z_cl +0.07: the cluster is filled more on the side whose Chainlink fair stands above the Binance
  fair, the historical trace of the live finding (fills where Chainlink values the token above futures). Univariate:
  gap_s 0.536, Chainlink edge 0.499 vs Binance edge 0.479.
- Side (798 one-sided bins of the sample): R3 0.647 -> stack 0.667; activity 0.588 -> 0.594.
- Ablation (LightGBM fitted on the 154 STUDY windows only): R3 features 0.641 -> + Chainlink 0.646; activity 0.641 ->
  + Chainlink 0.656. Activity + Chainlink logistic stack 0.6658 -> 0.6616 (worse; the stack on the activity score is
  misspecified).
- Fill prices (bin-start fairs): VALIDATE 3,586 fills MAD vs Chainlink fair 0.047 vs Binance fair 0.043 (corr 0.901 vs
  0.909; 43% closer to Chainlink); STUDY 0.062 vs 0.060. The Binance value here is 3 s fresher than the Chainlink one
  (t vs t - 3), so this comparison favours Binance; it does not show a Chainlink price anchor on the lot.
- **Decision (pre-registered criterion met): R5 = R3 stacked with the Chainlink features is adopted** (code/r5.py,
  code/cl_source.py, final_rule.py 'presence_r5'). Its gain is small (+0.0075) because the variation that separates the
  Chainlink stream from the exchanges (the 1-s noise) is absent from the lot; the full-VALIDATE R5 value needs the
  Chainlink series for all 1,152 windows (~13,000 more requests, ~2.3 h at the endpoint's rate). The stride-8 remainder
  of the pre-registered sample (offset 8, 4,320 requests) was started detached at 18:27 UTC (pid 22548,
  `log_it7_fetch_cl_b.txt`) so the next iteration starts with twice the sample.
- evaluate() smoke test (10-27 04:00-05:30, 18 windows, 4 with Chainlink, FETCH_CL False): runs end to end; R5 on the
  Chainlink windows 0.698 vs R3 0.665 (tiny). Note: the pooled 'auc_r5_with_r3_fallback' mixes two calibrations; the
  comparable numbers are the on-Chainlink-window ones.

## Iteration-7 checkpoint
- Primary metric (historical VALIDATE 10-27..30, presence AUC, no own state): **0.716** measured for R3/R4 on the full
  VALIDATE; R5 (adopted) adds +0.0075 [+0.0016, +0.0131] on the pre-registered VALIDATE sample (0.6923 -> 0.6997 on
  144 windows), so its full-VALIDATE value is estimated at about 0.72-0.73, not measured.
- Paradigm this iteration: the settlement stream on its own publish clock (Polymarket's historical endpoint for the lot,
  a new streaming RTDS recorder with publish ms for live).
- Decoded: the ladder re-price pass is triggered by each Chainlink report and comes within ~0-150 ms of the public RTDS
  relay's publish (bursts agree 0.76-0.81 with the report's change in the 150 ms after the publish, 0.35-0.44 before;
  follows the Chainlink change even when the futures moved the other way); no other maker reacts; takers do not trade on
  the display. The engine has no information lead over the public relay beyond the ~0.1-s clock resolution (K1
  rejected, K2 supported, K3 rejected). Print selection is best with the report stamped t - 1.43 s (0.764 vs 0.637
  activity, live). The Chainlink noise regime began between 10-30 15:00 and 10-31 00:30; since then the cluster's BTC
  5m trades lost -11.9% (10-31 00-06) and -3.9% (12-17), and BTC 5m was switched off in all wallets at 16:53:5x UTC at
  the day's PnL low (stop-loss hypothesis X58, own state).
- Not decoded: what makes a seller arrive at the fresh join (presence / selection are taker-bound; the display is not
  it); the join decision itself (P1); the rung depth (M3); the on/off trigger (X58 needs more events).
- Recorders: shared live.py running; examrec restarted (it had died 16:53); dy_rtds streaming; rawrec ended 18:00.
- Next (iteration 8): (1) freeze a live print-selection / presence rule with the Chainlink report on the publish clock
  (dy_rtds publish ms, else stamp floor((t - 1432)/1000)), fitted on 10-31 12-18, examined first on 11-01 06-12
  (pre-registered above); (2) the join decision P1 on the publish clock; (3) the switch-off: mark-to-market path,
  thresholds, re-enable time (does BTC 5m come back on 11-01?); (4) complete the CL sample (detached fetch) and, if
  time allows, all VALIDATE windows for a measured full-VALIDATE R5; (5) pin the regime change hour (I4) with sparse 1-s
  runs on 10-30 evening; (6) open items X48, X50-X57, D2, D3, A4, B9, C4b.

**P1 (X53) pilot: the per-trade join decision (`code7/p1_join.py`, live split, 37,234 clean BTC 5m prints that did not
fill the cluster, 14:06-16:30 UTC 10-31).** Label = an exact-500 add at the sold token's touch within 150 ms after the
trade: rate 2.4% (300 ms 4.4%; any exact-500 add on that side 21.6%), and the placebo (the same at the OTHER token's
touch) 2.7%: per trade, a fresh 500 at the touch is rare and not specific to the token just sold. Test AUC (>= 15:00,
673 positives): activity 0.560, + futures 0.537, + Chainlink at D = 1,083 ms 0.611 (700 ms 0.605, 1,432 0.585, 2,000
0.576); univariate Chainlink edge of the sold token 0.685 (700 ms), 0.678 (1,083), 0.659 (1,432), 0.628 (2,000). So the
posting is informed by the latest published Chainlink report (fresher clock than for the fills, as expected for a post
made right after the publish), but the trade-triggered join is a weak unit (AUC 0.61 << 0.80): most of the cluster's
at-touch 500s come from the publish-triggered re-price pass, and the earlier "fresh join ~95 ms after a trade" is a
property of the orders that got filled, not a per-trade rule. P1's signature (join AUC >= 0.80) is not met.

**P4 (X56), historical form: fill PnL by the Chainlink-Binance gap (`code7/p4_gap_hist.py`, the Chainlink sample
windows; gap = Chainlink fair - Binance fair of the token at the fill's bin start).** STUDY (1,394 fills, total +7.3%):
< -3 c +26.7% (16% of fills), -3..-1 c +7.7%, -1..+1 c +3.1% (39%), +1..+3 c **-11.1%** (16%), > +3 c -0.6% (19%).
VALIDATE (aggregate, 3,586 fills, +9.9%): < -3 c +11.9%, -3..-1 c +22.4%, -1..+1 c +4.8%, +1..+3 c **-12.2%** (15%),
> +3 c +26.3% (20%). The cluster fills more where Chainlink values the token above Binance (35-36% of fills vs 26-28%
below), the historical trace of R5's gap_s weight; the +1..+3 c fills lose in both halves (as live), but the > +3 c
bucket is mixed (STUDY -0.6%, VALIDATE +26%), so the "Chainlink-above-futures fills lose" economics is not stable on
the lot.

**M2 (X50) pilot: the quote posture after each Chainlink report (`code7/m2_posture.py`).** Unit = one Chainlink report
(and the current window); labels = an exact-500 add at the Up best bid / at the Down best bid within the re-price pass
([P, P + 200 ms] with publish ms; [S + 0.7, S + 1.5 s] by stamp where no publish ms exist); e = Chainlink digital fair
of Up (value of the report, Gamma priceToBeat, 1.4 x the 300-s futures 1-s vol, tau + 20 s; no fitted parameter) minus
the Up mid at the report.
- BTC 5m, 14:06-16:30 UTC (6,113 reports): P(Down at-touch post) falls from 0.21 in the lowest e quintile (e -0.18) to
  0.034 in the highest (e +0.16); P(Up) rises from 0.042 to 0.164. AUC Up 0.672, Down 0.720. **When exactly one side
  posts at the touch, sign(e) gives that side 0.776 (n 1,051; always-Up 0.503); live VALIDATE only (>= 15:00): 0.793
  (n 757; always-Up 0.538).**
- BTC 15m, 14:06-16:30 by stamp: 0.728 (n 721), live VALIDATE 0.758 (n 532); 17:29-18:00 with exact publish ms: 0.788
  (n 85), AUC Down 0.817.
The side decision of the QUOTE (which outcome's 500 goes to the touch on each report) is the sign of the Chainlink edge
over the Polymarket mid, at ~0.78-0.79 accuracy without any fitted parameter, against ~0.50-0.54 for always-Up. The fill
side stays lower (0.66) because which posted bid gets filled is the sellers' choice. This is the first component near the
0.80 bar; next: an activity-only baseline for the posture side (e.g. the token just sold, the last mid move), the
publish-clock version on 5m (11-01 06-12 with dy_rtds), and the two-stage fill presence = P(at touch | e) x P(seller).
- Market-only baselines for the posture side (same one-sided events, BTC 5m): live VALIDATE (n 757) sign of the
  Chainlink edge **0.793**; sign of the Binance-futures edge over the mid 0.573; cheaper side 0.542; always-Up 0.538;
  last 2-s mid move 0.502 (n 570 with a move); the token just sold 0.489. 14:06-16:30 (n 1,051): 0.776 vs futures
  0.586, cheaper side 0.584, always-Up 0.503, mid move 0.489, token just sold 0.495. The Chainlink edge beats every
  market-only and futures baseline by >= +0.2: the quote side is the cluster's own reading of the settlement stream.

**State at the end of iteration 7 (18:37 UTC).** Running and detached: shared recorder (pid 27184), exam recorder
code6/examrec.py (pid 24316, to 11-03 00:00), streaming RTDS recorder code7/rtdsstream.py (pid 29508, dy_rtds, to 11-03
00:00, 0.4 MB so far), Chainlink sample fetch, stride-8 remainder (pid 22548, `log_it7_fetch_cl_b.txt`, ~45 min, writes
cl_grid.parquet every 200 requests; it uses the endpoint's whole rate limit while it runs). evaluate() now also reports
`presence_r5` (pooled and per wallet, on the windows with Chainlink); smoke test 10-27 04:00-05:30 with 6 Chainlink
windows: R5 0.761 vs R3 0.744 (bosona 0.749 vs 0.732, almach 0.720 vs 0.717, mo-money 0.697 vs 0.696).
Tooling notes (not modified): tools/live.py and code6/examrec.py subscribe to RTDS with filters {"symbol": "btc/usd"},
which yields snapshots only; filters "" streams every 1-s update with its publish ms (code7/rtdsstream.py). The polyrea
HttpClient default for polymarket.com (4 requests/s) exceeds the crypto-price endpoint's sustained limit (~1.5/s), and
its shared sqlite cache stalled a bulk fetch (no 400 responses in 4 minutes).

**P3 (X55): the Chainlink gain against a stronger activity baseline (`code7/p3_strong.py`, same live split and prints as
sel_clock).** Adding sub-second book state from the raw touch series (spread, ms since the last touch change, 500-ms
mid move toward s, whether the print hit the pre-trade best bid of the sold token; no depth, which carries the
cluster's own resting 500s) to the activity set: 0.631 (activity 0.637), + futures 0.639, **+ Chainlink at 1,432 ms
0.764 (recall 0.45, lift 2.86)**, 1,083 ms 0.745, 2,000 ms 0.744. The gain (+0.125) survives the stronger baseline; a
window-block bootstrap of it and the examiner-style clean-book baseline remain for the 11-01 06-12 replication.

**X58 threshold check (BUILD, case by case).** Day PnL (UTC day, BTC 5m, held to resolution) at each switch-off: 10-17
20:30 -$901 (the day's low so far), 10-17 22:25 -$1,546 (first crossing of -$1,500 in that very window), 10-18 22:10
-$2,337 (low -$2,587; -$2,400 first crossed at 22:05), 10-23 20:35 -$4,618 (the day's low, but -$2,400 was crossed at
11:45, nine hours earlier), 10-24 22:25 +$747; live 10-31 16:53 -$2,424 (the day's low). Four of six switch-offs come at
a new daily low, but there is no fixed daily loss threshold (-$0.9k to -$4.6k, one after a gain): a loss controller
with a varying limit, or an operator reacting to losses, remains a hypothesis (X58 open).

### Iteration 8 (2026-10-31, local Windows laptop, started 19:04 UTC; 431 of 1,200 budget minutes used before it)

Read first: BRIEF, NOTES, state.json, FINAL_RULE.md, panels/iter7_{information,mechanics,assumptions}.md. The 15 panel
proposals are catalog items X59-X73 (information I7-1..I7-4 = X59-X62, mechanics M1-M6 = X63-X68, assumptions A1-A5 =
X69-X73). Calendar: the current block (10-31 18-24) and 11-01 00-06 are sealed; the next development block is 11-01
06-12 UTC, so this iteration has no new live development data: it works on the 10-31 12-18 recordings, the released lot
and the history before H. Recorders: shared live.py running (pid 27184); examrec (pid 24316) and dy_rtds (pid 29508)
alive (status files updated 19:07 UTC).

**PIVOT (required: progress flat for two iterations).** New paradigm: **the quote as the unit of decision, with an oracle
decomposition of fills (presence and selection ceilings given the observed quote), a structural inversion of the
engine's internal price across simultaneous markets, and a new data source: the June engine's signed millisecond
timestamps (true decision times).** No tuning of R3/R5.

**Competing explanations (iteration 8) and the observation that separates them**
1. L1 mid-anchored skewed ladder (current reading): each market's ladder hangs off that market's own Polymarket mid,
   skewed by the Chainlink edge (beta ~0.2), re-priced at each Chainlink publish; fills = seller arrival at the rung.
   Separates: the internal price inverted from two markets at the same instant disagrees by the mids' disagreement.
2. L2 one internal price for every market (structural digital pricer, panel M1): quotes_m = digital(S_hat, K_m, tau_m)
   +- h. Separates: S_hat_5m = S_hat_15m within a tick-equivalent in >= 70% of seconds; S_hat tracks Chainlink.
3. L3 path-dependent ladder (state machine, panel A3): rungs keep their rank and step toward the touch; the level
   depends on history. Separates: history features of public inputs predict the at-touch state beyond the current inputs.
4. L4 taker-bound fills (panel A4): given the quote, the fill is the sellers' choice; no quote decoder can reach 0.85
   on 10-s fill presence. Separates: the presence ceiling with the observed quote as an oracle.
5. L5 quote-bound selection: at the print level the quote decides whether a print reaches the cluster. Separates: the
   print-selection ceiling with the observed quote is above the target bar (AUC 0.80, recall 50% at lift 3).
6. L6 version change: the June engine (real signing ms, sizes 50/100/300) was a futures/spot-triggered signer and the
   October engine (timestamp 0) reads Chainlink; separates: lead-lag of June signing ms against Binance futures/spot
   at ms resolution and the phase of signing within the second.
7. L7 operator / loss controller for selection (BTC 5m off-switches): separates: switch-off hazard vs own PnL against
   public breakers on the full history (panel A2; needs the full-history activity, not done this iteration).

**Recorders started this iteration (development and sealed blocks filed by tools/live.py Writer).**
- `code8/rtdsbn.py` (I7-1 / X59): RTDS `crypto_prices` (Polymarket's Binance relay) with filters "" (btcusdt, ethusdt,
  solusdt: value, value stamp, publish ms, receive ms), feed dz_rtdsbn, hard stop 11-03 00:00 UTC, disk cap 60 MB;
  started 19:12 UTC (launcher pid 8580, worker pid 32308). Status counts after 2 min: 1,314 messages, 657 kept, 200 of
  another shape written raw (capped): the topic streams. Content not inspected (sealed block); check the format on 11-01
  06-12.
- `code8/delayed_rawrec.py` (mechanics critique 5): starts code5/rawrec.py (full-depth unaggregated BTC 5m current+next
  and 15m current books plus the reference feeds) at 11-01 05:55 UTC and stops it at 12:00 UTC (pid 17192, sleeping).

**A4 (X72): the fill-presence ceiling with the observed quote as an oracle (`code8/a4_ceiling.py`,
`results/iter8_a4_ceiling_1793455600_1793464202.json`; development block 10-31 14:06-16:30 UTC, BTC 5m; live split fit
< 15:00, test >= 15:00: 18 test windows, 1,080 test bins, 227 positive).** Unit = (window, side, 10-s bin), label =
cluster maker BUY fill. Held-out AUC: activity 0.624; public rule (+ futures + Chainlink edge) 0.661; **activity + the
contemporaneous cluster-class quote state (exact-500 adds at/above the touch of s in the bin, bursts, the highest 500
vs the touch, queue ahead) 0.796; public + quote oracle 0.804; + the bin's own future taker flow 0.794-0.803** (the
flow adds nothing once the quote is known: at-touch posts already follow trades). Univariate: at-touch 500 adds in the
bin 0.759. So even a perfect quote decoder would reach about 0.80 on 10-s fill presence, below the 0.85 bar: the
presence condition on fills is bound by which posted bid the sellers hit, not by the quote. Quantitative account for
fills: quote known 0.80, public 0.66, activity 0.62.

**A4 step 4: a quote-unit presence metric (same script).** Unit = (window, side, second), label = a cluster-class 500 at
the touch now (an exact-500 add at/above the touch of s in the last second whose price is still >= the touch; base rate
4.0%). Held-out AUC: activity (prints in 2/10 s, ms since the last trade and whether it sold s, ms since the last touch
change, mid, spread, time left) 0.672; + futures edge 0.671; **+ Chainlink edge (report stamped floor((t-1432)/1000))
0.740; + both 0.748; gain over activity +0.076 (window bootstrap 95% [+0.042, +0.110])**; Chainlink edge alone 0.623.
The quote state is predicted from public inputs at 0.75: the Chainlink input carries the gain (the futures add
nothing), but the at-touch state is far from deterministic.

**A4 / selection: the print-level selection ceiling with the observed quote (`code8/sel_oracle.py`,
`results/iter8_sel_oracle_1793455600_1793464202.json`; 27,318 test prints, 1,189 cluster).** Unit = clean BTC 5m print,
label = its transaction fills a cluster maker order. Held-out AUC (recall / lift at the BUILD top-15% threshold):
activity 0.611 (0.21 / 1.36); public (+ Chainlink + futures edges vs the print price) 0.686 (0.32 / 1.79); **activity +
quote oracle (an exact-500 add in the last 1.5 s at a price the print reaches, its gap, burst size, age, queue) 0.814
(0.62 / 3.32); public + oracle 0.834 (0.685 / 3.40)**. Only 50.5% of cluster-filled prints had a reachable exact-500
add in the previous 1.5 s (10.1% of other prints). So at the print level the quote IS the binding variable: with the
quote known, print selection passes the selection bar (AUC >= 0.80, recall >= 50% at lift >= 3). The target route is
selection, and the work is decoding the quote from public inputs (now 0.75 on the quote unit). (This sel_oracle public
set is smaller than code7/sel_clock.py's, which reached 0.764 with sequence features.)

**M1 (X64): one internal price for every market? Rejected (`code8/m1_invert.py`,
`results/iter8_m1_invert_1793455600_1793464202.json`; 2,266 seconds with top rungs on both outcomes of the current 5m
and 15m windows, tau >= 70 s in both).** Inverting each market's ladder center F = (top Up 500 + lowest Up-ask 500)/2
through the digital pricer with its own true strike (RTDS TWAP-60 at the start) and sigma = 1.4 x the 300-s futures vol:
|S_hat_5m - S_hat_15m| median 2.8 tick-equivalents (p75 6.0, p90 12.2; one tick-equivalent = $0.85 in 5m, $1.23 in
15m); **within one tick-equivalent 20% (M1's signature needed >= 70%)**. The disagreement is the markets' own mids:
regressing S_hat_5m - S_hat_15m on S_mid_5m - S_mid_15m (each mid inverted the same way) gives slope 0.83, R^2 0.79.
Each S_hat tracks its own market's mid-implied S best (residual sd $4.7 / $5.2, corr of 2-s changes 0.68 / 0.82)
against the futures in Chainlink units ($7.8 / $11.9; 0.56 / 0.70), Chainlink ($9.8 / $13.9; 0.43 / 0.47) or EMAs of
Chainlink (k = 2 s best: $8.5 / $13.1). The blend S_hat = S_mid + beta (CL - S_mid) is best near beta = 0.2 in both
markets (median error 2.5 / 2.3 tick-equivalents vs 2.9 / 2.5 at beta 0, 7.8 / 5.5 at beta 1). Verdict: L2 rejected,
L1 supported. There is no common model price behind the two ladders: each ladder hangs off its own market's mid with a
~0.2 Chainlink skew, and its level is not decodable to a tick from any reference price.

**A3 light (X71): public path-history features for the quote unit (`code8/a3_hist.py`,
`results/iter8_a3_hist_1793455600_1793464202.json`).** Adding the touch's changes over 1-10 s, the futures returns over
1-10 s and the Chainlink fair changes over 1-10 s to the quote-unit model lowers the held-out AUC (0.748 -> 0.737 ->
0.720; the BUILD hour has only 10 windows). No public path dependence is visible at this sample size; the strong form
(per-wallet rung state machine) is not tested.

**A5 (X73): the June engine signed real millisecond timestamps: decision times (`code8/june_fetch.py`,
`code8/fut_ms.py`, `code8/june_lag.py`, `code8/june_trig.py`, `code8/june_price.py`; results `iter8_june_*`).** Data:
the cluster's activity on 2026-06-10, 06-12 and 06-16 (~3,000 trades per wallet-day; mo-money absent on 06-10), up to
1,500 sampled transactions per wallet-day, calldata of every order in them (publicnode, ~13 tx/s: 06-12 21,475 orders
of which 4,685 the cluster's; 06-16 19,946 / 4,783; 06-10 20,284 / 3,016), Binance BTCUSDT USD-M futures and spot
aggTrades of 06-12 and 06-16 reduced to 50-ms last prices (SHA-256 checked, zips not stored).
- Verified: every June cluster order carries a real sign_ms and a per-wallet counter salt (06-12: 97-99% monotone;
  salt slopes 24-26 orders/s for bosona and mo-money, 4.3/s for almach); all BUY; sizes 300 / 100 / 50 / 40 / 200;
  markets BTC 5m (5,422 trades on 06-12), BTC 15m (1,041), BTC/ETH 4h, ETH/SOL/BNB 5m, daily DOGE.
- Sign-to-block lag of filled cluster orders (06-12): p1 1.39 s, p10 2.0, median 3.1, p90 7.5, p99 39 s.
- **Trigger: the cluster signs ~100-400 ms after Binance moves.** Mean |50-ms log move| around the signing ms relative to
  random times (06-12, n 3,049 BTC orders): futures 2.2-2.4x at 0.7-1 s before, rising to 4.0-4.8x at 150-400 ms before
  (peak 250-300 ms), 3.1x at 50-100 ms, **back to 1.0x in the last 50 ms and after the signature (0.7-1.3x)**; spot
  peaks 7.3x at 100-150 ms before, 1.0x in the last 50 ms. Other makers peak at 50-100 ms before signing (3.4x) and stay
  elevated at 0-50 ms; takers peak at 50-100 ms (5.9x). 06-16 (n 2,415): futures and spot peak 4.8x / 5.2x at 300-350 ms,
  elevated 3-4x across 50-500 ms and 1.8-2.1x at 0 (less sharp). Moves in [S-450, S-50] ms (1 bp): spot-only 5.3x vs
  futures-only 3.1x random on 06-12, but 3.3x vs 3.1x on 06-16 (and 5.6x vs 5.8x at 2 bp): which Binance market
  triggers it is not stable across the two days. So in June the engine was a Binance-reactive re-signer with a
  100-400 ms reaction (slower than other makers' 50-100 ms), with no sign of anticipating moves.
- **Price at the decision time (B3 at signing).** Limit price of 2,426 (06-12) / 1,171 (06-16) BTC 5m cluster BUY orders
  vs a digital fair from Binance at S - lag (venue's own pre-window TWAP strike, 1.4 x 300-s vol): futures corr 0.849 /
  0.853 (best at -250..0 ms, i.e. the reference at signing; 0.80-0.82 at 1 s, 0.77-0.80 at 3 s), spot 0.840 / 0.853;
  MAD(q - fair - median) 0.053 (futures, 06-12). The June quote is current at signing (no stale reference) but, as in
  October, is not a deterministic function of a Binance fair (MAD ~5 ticks).
- Chainlink 1-s values are not available for June (the endpoint refuses dates older than 30 days), so whether the June
  engine also re-priced on Chainlink publishes cannot be tested directly; the signing phase within the second is only
  mildly non-uniform (06-12 deciles 372-552 per 100 ms, no concentration in the relay's x.7-x.3 publish phases).
  Verdict on L6: the June version reacts to Binance moves at 100-400 ms; the October version's per-report Chainlink
  re-price pass is a later addition or was invisible then. Version boundary (timestamp -> 0 on 06-21/22) not decoded.

**A1 / M3 (X69, X65): the union universe BTC 5m + 15m, rule R6 (`code8/features15.py` = code/features15.py,
`code8/panel15.py`, `code8/train15.py`, `code8/union_val.py`; `results/iter8_train15.json`,
`results/iter8_union_val.json`).** R3's model class (same features with bins [0, 900) s, same LightGBM parameters, clock)
fitted on BUILD 15m windows 2026-10-09..26 (311,040 bins, 2.3% positive) and scored on VALIDATE 10-27..30 (aggregate;
384 windows, 69,120 bins, 1.3% positive, 53% of 15m windows active):
- BTC 15m: presence **0.812** vs activity 0.778 (gain +0.034); within active windows 0.792; side 0.733 (n 895; activity
  0.615, favourite 0.398); per-window PnL corr (expectation) 0.18 / 0.35.
- Union (pooled bins, 5m R3 frozen + 15m): presence **0.788** vs activity 0.780 (gain +0.009, 2-h block bootstrap
  [+0.003, +0.016]); side 0.672 (activity 0.613); PnL corr 0.260 / 0.327 (1,293 windows); price within a tick on the
  block clock ~0.705 (5m 0.709 on 27,988 fills, 15m 0.666 on 2,996). Coverage of the union on VALIDATE 0.868 of fills /
  0.891 of absolute PnL (iteration 5), development blocks 10-31 00-06 0.914 of trades / 0.949 of dollars, 12:00-16:54
  0.94 / 0.93, 16:54-18:00 0.82 / 0.93 (panel); BUILD 10-20 12-16 only 0.59 / 0.65 (smoke test): the union meets the
  scope bar on VALIDATE and in every development block since 10-27, not in early BUILD.
- Pre-registered here (before any sealed block is scored): R6's universe is BTC 5m + BTC 15m; a block with BTC 5m off is
  scored on BTC 15m; pooled and per-family metrics are both reported.
- evaluate() now builds the 15m panel through the same adapters (Gamma 15m windows, data-api taker tapes, activity),
  applies presence15_rule / presence15_activity, and reports `btc15m`, `union_btc5m_15m` and `scope`; smoke-tested on
  BUILD 10-20 12:00-16:00 (in-sample for both models: runs end to end; numbers not a validation).

**Per-fill side with the decoded quote-side rule (mechanics critique 4; `code8/fill_side.py`,
`results/iter8_fill_side_1793455600_1793464202.json`; development block 10-31 14:06-16:30 UTC; no fitted
parameter).** For every cluster maker BUY fill with a server match ms: predicted side = Up iff the Chainlink digital
fair of Up (report stamped floor((T - 1432)/1000), true strike, 1.4 x 300-s futures vol) exceeds the Up mid just before
the match. **BTC 5m live VALIDATE (15:00-16:30): 0.841 (n 1,207; at-touch fills 0.844, n 1,172; deeper 0.743, n 35);
BTC 15m 0.874 (n 199); pooled 0.846 (n 1,406).** Market-only baselines on the same fills: futures-edge sign 0.552 /
0.603, cheaper side 0.522 / 0.538, always-Up 0.607 / 0.513, the side the previous clean print sold 0.379 / 0.427. Per
wallet (5m): almach 0.905, bosona 0.849, mo-money 0.783; (15m) 0.84 / 0.89 / 0.91. Halves of live VALIDATE: 5m 0.890 /
0.788, 15m 0.853 / 0.887. Clock robustness (5m): report stamped t-0.7 s 0.788, t-1.083 0.814, t-1.432 0.841, t-2 0.822,
t-3 0.761; mid 1 s before the match 0.853, last clean print instead of the mid 0.851 (so the cluster's own resting bid
in the touch does not drive it). But live BUILD (14:06-15:00) is only 0.664 (5m, n 226) and 0.306 (15m, n 36): the
half hour 14:30-15:00 scores 0.447 (n 152) with fresh Chainlink values and strikes equal to Gamma's (checked), i.e.
whole windows where the cluster bought the side the Chainlink edge disfavoured (5m 14:55: 24 Down fills at a median
edge of +0.115 for Up; 15m 14:45: 0.14). So the side rule is ~0.84 on 90 minutes and fails on some windows: it must
replicate on 11-01 06-12. This is the first decision component at the 0.80 bar on held-out time against market-only
baselines (it is the quote-side posture of iteration 7 showing up in the fills: the fill lands on the outcome whose
500 the Chainlink edge put at the touch).

**R6 through `evaluate()` on the live development slices (`code8/smoke_r6_live.py`, `code8/eval_live_more.py`;
`results/iter8_eval_r6_*.json`).** The frozen path (shared recorder 'q' book mid, live Chainlink recordings, Gamma
strike, Binance REST 1-s fallback) reproduces the per-fill side: **15:00-16:30 UTC 0.836 (n 1,341; 5m 0.836, 15m
0.834; bosona 0.858, almach 0.871, mo-money 0.787)** vs Binance-spot edge 0.562, cheaper side 0.550, always-Up 0.608.
But **16:30-18:00 only 0.708 (n 284; 5m 16:30-16:53 0.609, n 115; 15m 0.775, n 169) against a Binance-spot-edge
baseline of 0.718**: in the half hour before the BTC 5m switch-off and in the 15m-only hour the rule is no better than
the market baseline. Match-clock price 0.860 (n 1,194, 15:00-16:30) and 0.765 (n 115, 16:30-16:53; anchor last print
0.835). 15m presence 0.767 / 0.775 vs activity 0.765 / 0.766 on the two slices (no gain live). Bug fixed on the way:
`price_match_clock` received compact transaction keys and raised AttributeError (R4's live price never ran inside
`evaluate()` with `_cluster_trades`' compact keys); it now maps them to full hashes (`_cluster_tx_hashes`).

**What the posture side depends on (live, `fill_side_*.parquet`; descriptive).** Live VALIDATE accuracy by |Chainlink
edge|: <= 1 c 0.33 (n 64), 1-2 c 0.71, 2-5 c 0.85, 5-10 c 0.83, 10-20 c 0.91, > 20 c 0.89; it does not depend on whether
the futures edge agrees (0.857 disagreeing, n 565, vs 0.838 agreeing), on time in the window (0.80-0.92) or on the mid
(0.82-0.89). Vol scale: our 1.4 x realised vol is best (x0.7 0.836, x1.4 0.765, x2 0.672); a threshold of +1 c would give
0.867 on VALIDATE but 0.599 on BUILD (not adopted). Live BUILD (14:06-15:00) stays at 0.56-0.68 for every variant; the
Chainlink noise was present then too (sd of 1-s changes $5.9-7.2, lag-1 -0.42..-0.53 by half hour, vs $8.8-10.9 later), so
the weak hour is not a smooth-stream regime. Example of a failing window (5m 14:55): 24 Down fills at 0.67-0.95 while
both the Chainlink and the futures fair valued Up 5-15 c above the mid (the cluster bought the favourite against both
references), i.e. there are windows where the engine's side has another driver.

**M4 step 1 (X66) on VALIDATE, aggregate (`code8/m4_pop.py`, `results/iter8_m4_pop_validate.json`; 27,971 cluster maker
fills, +$110.0k, +3.6% on dollars, 88% complement mints; window-block bootstrap CIs).** By the taker's signatureType:
EOA 2.2% of fills +17.2% [+2.9%, +30.1%] (13.5% of PnL); Magic proxy 24.4% +6.7% [-0.8%, +13.2%] (46.7%); Safe 13.8%
+5.5% [-2.9%, +14.7%] (19.4%); type 3 59.6% +1.3% [-4.7%, +6.9%] (20.4%). Taker limit beyond the cluster's level: <= 0.5 c
32.7% of fills +0.4%; 0.5-3 c +3.0%; 3-10 c 27.8% +5.3% (41% of PnL); > 10 c 12.7% +7.0% [+0.2%, +13.3%] (34%).
Round-USD buys 36% of fills +3.5% (35% of PnL; STUDY 107%); non-zero builder +2.6%. The direction of the panel's STUDY
finding holds (front-end order types and loose-limit sweeps pay; the type-3 majority roughly breaks even), but on
VALIDATE no population carries >= 80% of the profit with a CI above 0 (M4's signature not met). Step 2 (live arrival
hazard by population after display-only moves) not done.

**The posture side needs the match clock.** Same fills, inputs on the block clock instead (Chainlink stamped block
second - 3, the last clean print before block second - 2 as the mid; block time is a median 2.24 s after the match):
live VALIDATE 0.723 (5m 0.719, 15m 0.744) vs 0.846 on the match clock; live BUILD 0.504 vs 0.615. As for the price
(0.86 vs 0.69), the side decision is made on sub-second-fresh inputs; historical tapes (block clock) cannot show it at
full strength, which is also why the historical bin-level side stays at 0.66-0.67.

**Print selection with the posture edge (`code8/sel_oracle.py`, second run, `results/iter8_sel_oracle2_*.json`).** Adding
the Chainlink and futures edges relative to the mid (the posture variables) to the public print model does not help
(0.670 vs 0.686 held out): the live BUILD hour (14:06-15:00, 10 windows, the hour where the posture side is weak) is too
small and atypical to fit sub-second models on; the next fits should use all of 10-31 12:18-18:00 from the shared
recorder ('q' / 'x', 5.7 h) rather than the own raw recorder's 1-hour BUILD.

**Pre-registration for the next development block (11-01 06:00-12:00 UTC; written 10-31 19:55 UTC, before any data of
that block exists).**
1. Side: `final_rule.side_posture_match_clock` as frozen (CL_DELAY_MS 1432, no fitted parameter), per family, per wallet
   and per half of the block, against the Binance-spot-edge, cheaper-side and always-Up baselines; secondary variant on
   the strict publish clock (the latest Chainlink report whose dy_rtds publish ms is <= T - 50 ms). Pass mark for the
   component: >= 0.80 pooled and >= 0.77 in each half.
2. Presence and scope: `evaluate()` (R6 union) on the block, with `btc15m`, `union_btc5m_15m`, `scope`.
3. Quote unit (cluster-class 500 at the touch now) and print selection: models fitted on 10-31 12:18-18:00 from the shared
   recorder, tested on 11-01 06-12; the quote-oracle ceilings recomputed on 11-01.
4. X59: check dz_rtdsbn's message format in the first minutes; re-posts not within 200 ms after a Chainlink publish vs
   the latest RTDS-Binance publish (25-ms bins) and vs dx_bnf event time.
5. M1/A3/M2 on the full-depth recording (code8/delayed_rawrec.py, 05:55-12:00).
6. BTC 5m on/off: whether and when BTC 5m comes back (X58/X70).

## Iteration-8 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m presence AUC, no own state): unchanged at **0.716** (R3/R4; R5
  ~0.72-0.73 estimated). New frozen rule **R6** = R5 on BTC 5m + R3's model class refitted on BTC 15m + the per-fill
  Chainlink posture side; on the union universe VALIDATE presence 0.788 vs 0.780 activity (gain +0.009), side 0.672,
  price 0.705 (block clock), PnL 0.260 / 0.327, coverage 0.868 / 0.891 (scope bar met for the first time).
- Paradigm (pivot): the quote as the unit. Oracle decomposition: 10-s fill presence is capped at ~0.80 even with the
  quote known (taker-bound), print selection with the quote known reaches 0.81-0.83 at recall 62-69% / lift 3.3-3.4 (the
  selection bar), public quote prediction 0.748 (quote unit). Structural inversion across markets rejected (no common
  internal price; each ladder hangs off its own mid with a ~0.2 Chainlink skew). June decision times: a Binance-reactive
  signer (100-400 ms). New decoded component at the bar on held-out time: **fill side = sign of the Chainlink edge over
  the mid at the match ms, 0.836-0.846 on live VALIDATE 15:00-16:30 (n 1,341-1,406) vs <= 0.61 market-only**, but 0.71
  on 16:30-18:00 (baseline 0.72) and ~0.62 on 14:06-15:00: pooled over the live development data about 0.79.
- Not decoded: the ladder level to a tick; what makes the posture fail in some windows; the BTC 5m on/off trigger; the
  between-report clock (X59 recorder now running); a strict-fill replay for the outcome metric (X64).
- Recorders: shared live.py running; examrec (24316) and dy_rtds (29508) alive; new dz_rtdsbn (RTDS Binance relay) and a
  scheduled full-depth recorder for 11-01 05:55-12:00.

**X60 / I7-2 step 1 (live, `code8/x60_cross.py`, `results/iter8_x60_cross_1793449080_1793466000.json`; 10-31
12:18-16:40 UTC, shared recorder mids and trades).** For the 5m windows that end on a 15m boundary (same closing
TWAP-60), the 15m mid implies a 5m fair (Gaussian closing mean, 1.4 x 300-s Binance vol); gap = implied - 5m mid
(p10/50/90 -0.15 / -0.005 / +0.24 over 3,055 aligned seconds). The 5m taker flow does not arbitrage it: corr(gap, net
taker Up-buying over the next 3 s) +0.045 aligned vs -0.063 in the non-aligned placebo, and the next print buys Up 0.44
of the time when the gap favours Up vs 0.50 when it disfavours Up (the opposite of an arbitrage trigger). The cluster's
fill side goes against the gap in aligned windows (sign of the gap 0.285; the posture rule 0.821 on the same 358 fills):
the 15m book lags the 5m book, which in turn lags the Chainlink fair. Cross-horizon traders are not the trigger of the
sellers who fill the cluster (I7-2's live signature not met); Kalshi and the historical step not done.

**Side posture over the whole development block (`results/iter8_eval_r6_1793448000_1793458800.json`,
`iter8_side_pubclock_1793467740_1793469600.json`).** Through `evaluate()`: 12:00-15:00 **0.712** (n 600; 5m 0.738, 15m
0.589; baselines Binance-spot edge 0.557, cheaper side 0.627, always-Up 0.552), 15:00-16:30 0.836 (n 1,341), 16:30-18:00
0.708 (n 284; baseline 0.718); pooled 12:00-18:00 **0.786** (n 2,225). On the strict publish clock (17:29-18:00, 15m only,
n 56): 0.54 (stamp convention 0.57). By 15 minutes (own raw recorder, 14:00-16:30): 0.93, 0.93, **0.33** (14:45, n 122;
the futures-edge sign 0.14: the cluster bought the side both references disfavoured), 0.81, 0.94, 0.82, 0.89, 0.84,
0.77. The side rule is the dominant driver in most quarter hours and fails completely in some; the failing quarter
hours are not explained by the Chainlink noise level, the at-touch share (0.92-1.0 everywhere) or the edge size.
Other evaluate() numbers on 12:00-15:00: match-clock price 0.817 (n 526; anchor 0.781); 5m presence R3 0.708 vs 0.680,
R5 0.726 on the same windows (live gain +0.018); 15m presence 0.824 vs 0.818; union scope 0.88 of trades / 0.89 of
dollars.

**D2: a discrete-time hazard of the three-wallet burst posts on public clocks (`code8/d2_hazard.py`).** Unit: 50-ms bin
of each (market, Up-book side); event = a burst (>= 2 same-price exact-500 adds within 20 ms). Held-out AUC (last 40% of
the period): 14:06-16:30 with the publish proxy (stamp + 1.09 s): time/side 0.594, trade clock 0.595, futures clock
0.585, Chainlink clock 0.629, all 0.639; **17:29-18:00 with the true dy_rtds publish ms (BTC 15m, 1,384 bursts): time/side
0.743, trade clock 0.753, futures clock 0.773, Chainlink publish clock 0.793, all public clocks 0.826**. Hazard by ms
since the publish: 0.024-0.028 per bin in 0-150 ms, 0.006-0.010 at 150-1,000 ms (a 3-4x step down at 150 ms); by ms since
a futures mid change: 0.023-0.033 at 50-200 ms vs 0.008-0.010 after 500 ms. On the exact clocks the posting times are
predictable at 0.83 from public events alone; the stamp-based proxy blurs the step (0.64). The RTDS Binance-relay clock
(X59, now recorded) is the missing third clock.

polyrea note (not modified): `polyrea.analysis.updown.windows_from_markets` skips Up/Down markets whose Gamma record has
no `cryptoMarketConfig.asset`; the June 2026 BTC 5m records have none, so June windows were built from the raw records
(`code8/june_price.py`).

**R5 on the live slices (`evaluate()`, BTC 5m windows with Chainlink).** 12:00-15:00 R5 0.726 vs R3 0.708 vs activity
0.680 (36 windows); 15:00-16:30 0.730 vs 0.721 vs 0.659 (10); 16:30-18:00 0.680 vs 0.663 vs 0.710 (15, BTC 5m off
after 16:53). R5's stack (fitted on the smooth lot) adds +0.009..+0.018 live; R5 side 0.69-0.73 vs R3 0.57-0.70.

**A3 verification and X51 (`code8/a3_rungshift_verify.py`, the panel's p7/rungshift.py on 14:06-16:30 with an
addition).** 20,537 exact-500 removals followed within 20 ms by an exact-500 add at another price on the same side
(median rung age 590 ms): offset to the mid before and after correlates 0.85 (rank persists; quintiles -0.195 -> -0.155
... -0.035 -> -0.015); the step dp is +3.6 c on average and unrelated to the mid change since the old post (corr 0.002),
to the Chainlink change (0.007) and to the futures change (-0.023); dp > 0 in 95% of the pairs whatever the Chainlink
change (0.967 after +$5, 0.960 after -$5, 0.94 when |dCL| <= $1). These fast remove-then-add pairs are a mechanical
ratchet toward the touch (or a wallet-pairing artefact of the three-wallet bursts), not center moves; downward moves
must happen another way (add before cancel, or a delayed add). Rung depth is therefore not i.i.d. (X51's designed
randomness in its i.i.d. form is ruled out); the per-wallet state machine (A3 strong form) remains the open route to
the ladder level.

**Economics of the posture (14:06-16:30, fills held to resolution, Gamma payouts).** Fills on the side the Chainlink edge
favoured returned **+21.3%** on dollars; the 318 fills against it **-2.5%** (all fills +14.9%). In the failing quarter
hour (14:45) the fills against the posture lost 12.7% while the few posture-consistent ones made +59%: the deviations
are not better information, they cost money. Per wallet over the whole block (evaluate() slices pooled): bosona 0.785
(n 628), almach 0.813 (n 780), mo-money 0.761 (n 817).
- Add-then-remove order (5,409 pairs of an exact-500 add followed within 20 ms by an exact-500 removal at another price on
  the same side): the new add sits ABOVE the removed rung in 87% (median +3 c). In both orders the fast re-posts step up
  by 3-4 c; downward ladder moves do not happen as fast pairs. With a median rung age of 0.59 s, a rung climbs ~6 c/s
  toward the touch: the 500 stream behaves like a creeping bid that ratchets up to the touch (where it is filled or pulled),
  which fits "fresh joins at the touch" and is the move law A3's state machine should start from.

**Next steps (iteration 9; the next development block is 11-01 06:00-12:00 UTC).**
1. Run the pre-registered checks on 11-01 06-12 (side posture through `evaluate()`, R6 union presence and scope, the
   quote-oracle ceilings, the publish-clock hazard) and the X59 test once dz_rtdsbn's format is confirmed.
2. Decode the ladder as a state machine (A3 / X71 strong form) starting from the creeping-bid law measured here (fast
   re-posts step up 3-4 c every ~0.6 s, independent of the mid and of Chainlink; persistent rank): per-wallet rung
   resolution, the reset/pull rule, then a replay that predicts the at-touch state (the quote unit, 0.748 now) and print
   reach (selection ceiling 0.81-0.83 with the quote known).
3. Strict-fill replay (X64) of the posture + creeping-bid generator against the recorded takers for the outcome metric.
4. Why the posture side fails in some quarter hours (14:45 0.33, 17:29-18:00 0.54): own inventory (adds to the held side
   0.83 there, own state), the window's outcome, the market's own lead.
5. The BTC 5m on/off trigger on the full history (A2 / X70), the paying-population hazard live (X66 step 2), Kalshi and the
   historical cross-horizon step (X60), strike publication lag (X61), RTDS activity latency (X62).

**A4 robustness: a longer live BUILD (fit < 15:40, test 15:40-16:30, 10 windows; `results/iter8_a4_ceiling_*_split1793461200.json`).**
Fill presence: activity 0.635, public 0.677, + quote oracle 0.805-0.813 (+ future flow 0.807-0.813); quote unit: activity
0.682, + Chainlink 0.746, + futures 0.747 (gain +0.066, window bootstrap [+0.032, +0.094]). The ceiling (~0.81) and the
quote-unit level (~0.75) do not move with twice the training data.

**A3 public creep-state features (`code8/a3_creep.py`, `results/iter8_a3_creep_1793455600_1793464202.json`).** Run length
of a positive Chainlink edge, of an edge > 2 c, of a negative edge, and 3 / 10-s mean edges add nothing to the quote unit
(0.748 -> 0.748). The at-touch rate is 0.025 while the edge is negative, 0.063-0.074 in the first 1-8 s after it turns
positive and falls after that (0.054-0.060 at 8-32 s, 0.038 beyond): the 500 reaches the touch when the posture turns
(a step at the re-price pass), not by a slow creep that grows with the run length; the fast +3-4 c re-post pairs are a
within-pass mechanic. Iteration 8 stops new analyses here (20:06 UTC).

**A4b / X48 first measurement: Kalshi KXBTC15M (`code8/a4b_kalshi.py`; results `iter8_a4b_kalshi_*`; development block
10-31 12:45-16:45 UTC; Kalshi public trades API, no key, 646,684 trades in 18 quarters; quarters with > 40,000 trades are
truncated to their last 40,000).** Lead-lag of 1-s changes, Kalshi yes price vs the Polymarket 15m Up mid: corr 0.151 at
lag 0, **0.296 with Polymarket one second later**, 0.12 at 2-5 s, ~0 at negative lags: Kalshi moves first. Against
Binance spot 1-s returns (t-1, t, t+1) the Polymarket change is explained at R^2 0.094; adding the Kalshi change raises it
to 0.134 (standardised beta 0.22, the largest; in-sample): Kalshi's book leads Polymarket's 15m book by about a second
beyond what 1-s Binance spot shows (a ms futures control is still needed). The cluster's 15m fill side (159 fills with
Kalshi data, ~9 quarters, 14:06-16:30): the sign of the Kalshi 5-s change 0.433 (no information); the posture rule 0.692 on
the same fills; **the PM side that is cheap relative to Kalshi (PM Up mid above the Kalshi yes price -> Down) 0.792**.
The strikes differ (Kalshi: CF Benchmarks BRTI; Polymarket: Chainlink TWAP-60) and fills cluster by window, so this
is a lead to replicate with aligned strikes, not a result.
6. Replicate the Kalshi lead with aligned strikes and ms futures as the control; test sign(PM mid - Kalshi) as a side and
   posture input for BTC 15m (and the Kalshi hourly market for the hourly family).
- Kalshi lead with a millisecond futures control (14:15-17:15 UTC, dm_bnf bookTicker mid at the second boundaries and its
  move over the next 0.5 s; `results/iter8_a4b_kalshi_control_futures.json`, n 10,044 s): R^2 of the next-second Polymarket
  15m mid change 0.115 from the futures alone, 0.143 with the Kalshi change added (standardised beta 0.18; in-sample). The
  Kalshi lead survives the futures control: Kalshi is a candidate input the cluster's 15m quotes (or the 15m sellers) may
  use. Iteration 8 stops new analyses at 20:29 UTC.

### Iteration 9 (2026-10-31, local Windows laptop, started 20:55 UTC; 516 of 1,200 budget minutes used before it)

Read first: BRIEF, NOTES (iteration 8 in full), state.json, FINAL_RULE.md, panels/iter8_{information,mechanics,
assumptions}.md. Calendar (`tools/sealed.py directional-maker`): development [10-23, 10-31 06:00) and [10-31 12:00, 18:00);
the current block (10-31 18-24) and 11-01 00-06 are sealed; the next development block is 11-01 06-12 UTC, after this
iteration ends, so there is again no new live development data. Shared live.py running (status checked 20:56 UTC).
Panel proposals added as catalog items: information I8-1..I8-5 = X74-X78, mechanics M1-M4 = X79-X82, assumptions B1-B4 =
X83-X86.

**PIVOT (required: two iterations below +0.01 on the primary metric).** New paradigm: **the engine's pricer state as a
latent variable, decoded by interval-censored inversion of its own side decisions (the side decision rewritten as a
volatility comparison), on a new, much larger sample (every BTC 5m maker fill of BUILD and the released lot on the block
clock, ~86,000 fills, plus the June signed-ms orders), and the module state (on/off) as a selection component with a
family-general universe for scope.** No tuning of R3/R5/R6's models.

Key reformulation. With x = ln(S/K) and m = the Up mid, the posture "Up iff Phi(x / (sigma sqrt(tau))) > m" is
sigma-free when sign(x) != sign(Phi^-1(m)) (region D: the reference and the market disagree on the favourite: buy the
reference's favourite), and in region A (they agree) it is a volatility comparison: buy the favourite iff sigma_engine
< sigma_mkt = x / (sqrt(tau) Phi^-1(m)), the market-implied vol given the reference. So the "side" has two parts: an
information part (D: the reference leads the mid) and a volatility-view part (A: the engine thinks the market over- or
under-prices the remaining uncertainty).

**Competing explanations (iteration 9) and the observation that separates them**
1. V1 slow-vol digital pricer: the engine's sigma is a long realised vol (>= 30 min) or EWMA of Binance 1-s returns.
   Separates: in region A the side follows sigma_mkt vs a slow estimator; burst fills (v300/v3600 > 1.5) flip to the
   favourite; history (thousands of burst fills on the lot) replicates the 10-31 contrast.
2. V2 capped short vol: sigma = min(c1 v300, c2 v3600) (short in calm minutes, capped in spikes; mechanics panel bound
   pattern). Separates: in calm minutes the bounds pin sigma at 1.4 v300 < v3600; in spikes at <= v3600.
3. V3 constant / restart-set or window-open-frozen sigma. Separates: no within-block co-movement of the implied sigma
   with realised vol; steps at 01:00 UTC restarts or window opens.
4. V4 hysteresis / deadband posture (state with inertia). Separates: at |edge| <= 1 c the side follows the previous
   posture; per-taker-event accuracy of a (theta, k) state beats the previous-event baseline.
5. V5 reference level offset or drift (report bid/ask, futures premium). Separates: a constant-sign offset across blocks
   that lifts the small-edge bucket.
6. V6 per-wallet engine instances with different clocks or parameters (mo-money). Separates: per-wallet accuracy vs
   reference delay and vs sigma.
7. V7 settlement-source-specific skew vs one-feed engine (Binance-settled hourly/daily). Separates: their side follows
   the Binance-candle fair or Chainlink.
8. V8 operator module schedule (weekend nights off) vs a running controller. Separates: per-module switch calendar,
   salt counter continuity at a switch.
9. V9 the vol view is the edge: the cluster earns where its slow sigma disagrees with the market's implied sigma (region
   A) rather than from the reference lead (region D). Separates: PnL per region and per vol-ratio regime.

**Pre-registration H-VOL (written 21:02 UTC before vol_hist.py ran).** Unit: cluster maker BUY fill, BTC 5m, block
clock (S = Binance spot second b-3, K = Binance TWAP-60 strike, mid = last clean print at ts <= b-3; `code9/vol_hist.py`).
Family: v_L (L 120/300/900/1800/3600/7200), EWMA half-life 300/900/1800/3600, min(1.4 v300, c v3600) c 1.0/1.4, v3600
frozen at the window open; k 0.8/1.0/1.2/1.4. Choice on BUILD (10-09..22) + STUDY (10-23..26) pooled. Confirmation on
VALIDATE (10-27..30, aggregate): the chosen candidate beats R6's 1.4 x v300 pooled by >= +0.01 with a 2-h block bootstrap
lower bound > 0, and in the burst regime (v300/v3600 > 1.5) by >= +0.10. If it passes, R7 = R6 with that sigma in every
Chainlink-edge input, pre-registered for 11-01 06-12 (pass mark >= 0.80 pooled, >= 0.77 per half).

**H-VOL result (X74 I8-1 step 4, X79 M1): the slow sigma does NOT replicate on the historical block clock; the
pre-registered confirmation fails (`code9/vol_hist.py`, `code9/vol_analyze.py`, `code9/vol_scale_agg.py`, `code9/vol_agg.py`;
results `iter9_volhist_buildstudy.json`, `iter9_volhist_validate_e1800_1.0.json`).** Per-fill tables: BUILD 49,569, STUDY
8,256, VALIDATE 27,988 cluster maker BUY fills in BTC 5m (block clock).
- BUILD + STUDY (choice): R6's 1.4 x v300 0.592 pooled; best e1800 k1 0.611, v3600 / v3600-at-open k1 0.611 (+0.019);
  burst regime (v300/v3600 > 1.5, n 7,394) 0.566 -> 0.619. Region D (reference and market disagree on the favourite;
  sigma-free) 0.619 for every candidate; the gain is all in region A (85% of fills): 0.588 -> 0.610.
- VALIDATE (aggregate, the frozen choice e1800 k1): **0.569 vs R6 0.645, gain -0.076 (2-h block bootstrap [-0.119,
  -0.036])**; burst regime 0.434 vs 0.671 (n 3,380); every wallet and every day worse. Verdict: H-VOL fails; R7 (slow
  sigma) is NOT adopted on the historical evidence.
- Why (aggregate diagnostics): on VALIDATE the cluster's fills were underdog-heavy (cheaper-side baseline **0.679**, 0.81
  when the favourite is >= 0.90; BUILD 0.535, STUDY 0.484), and the block-clock accuracy rises monotonically with the
  sigma scale up to that baseline (v3600 x 0.5 / 1 / 1.4 / 2 / 3: 0.390 / 0.564 / 0.643 / 0.677 / 0.683; v300 the same
  within 0.01 at each k). So the VALIDATE preference for R6 is a preference for a LARGER sigma (closer to "buy the
  underdog"), not for the 300-s lookback: at equal scale the lookbacks tie (k 1.4: v3600 0.643, v300 0.645). The
  sigma-free region D scores only 0.575 on VALIDATE (0.616 BUILD, 0.640 STUDY): on the block clock the historical fill
  side is dominated by the fill composition (complement-mint fills of the underdog when takers buy the favourite) rather
  than by the posture. The block clock cannot identify the engine's sigma; only quote-level or match-clock data can.
- June signed-ms limit prices (`code9/june_vol.py`, `iter9_june_vol_*.json`; 06-12 futures and spot, 06-16 futures,
  2,203 / 1,158 orders after the first hour): MAD(q - fair - median) 0.053-0.063 for every candidate (06-12 fut best
  v300 x 1.4 0.0534, v3600 0.0551; 06-16 best e300 0.0543, v3600 0.0618; 06-12 spot best e1800 x 1.2 0.0597); corr
  0.83-0.87 for all. The June price level does not identify sigma either (X79 step 4: no estimator separates).

**Live posture on the match clock with the sigma family (`code9/vol_live.py`, `results/iter9_vol_live.json`; 10-31
12:00-18:00, 2,244 fills; descriptive: the panels read this block).**
- Region D (sigma-free; 26% of fills) **0.855**; region A R6 0.762, v3600 k1 0.825 (always-favourite 0.546).
- R6 vs v3600 k1 vs e1800 k1: all 0.786 / 0.832 / 0.823; 12-15 0.712 / 0.787 / 0.772; 15-16:30 0.835 / 0.843 / 0.834;
  16:30-18 0.709 / 0.881 / 0.877; 5m 0.794 / 0.811; 15m 0.753 / 0.917; burst (n 141) 0.390 / 0.936; calm (< 0.85, n 1,510)
  0.820 / 0.837; per wallet bosona 0.785 / 0.847, almach 0.812 / 0.888, mo-money 0.762 / 0.767.
- Interval-censored sigma_e per 10-min bin (region A, logistic link, common slope a = 2.25 on log sigma*): the slope is
  shallow, so each bin's 95% interval spans a factor ~16 and every candidate lies inside it in 95-100% of the 22 bins.
  corr(log sigma_e, log candidate): v3600 0.43, e1800 0.43, v1800 0.31, 1.4 x v300 -0.06. The favourite share in region
  A swings from 0.21 to 0.94 between bins (14:50 0.91 with 1.4 x v300 = 7.2e-5 vs sigma_e 1.0e-5; 15:50 0.94). The live
  data favour a slow sigma (corr), but the engine's sigma is not identified to a source (X75 I8-2 needs a regime change
  with match-clock data: 11-02 12-18 is the natural experiment).
- B3 (X85) per taker event (fills on the same side within 100 ms collapsed: 1,297 events, 71 windows): slow posture 0.823
  per event (R6 0.780), per-window mean 0.792; **own-history baseline "side of the previous event" 0.865**; switch events
  (n 165; the previous-event baseline is 0 there by construction): slow 0.764, R6 0.703; small-edge events (|e| <= 1 c, n
  80): posture 0.45, previous side 0.91 (inertia inside a deadband). A hysteresis band fitted on 12-15 (theta 0.03) gives
  0.820 on 15-18 vs 0.830 without (theta 0.01 would give 0.843: not chosen). The posture predicts the switches, an
  inertia term predicts the rest; neither alone reaches 0.865 per event.
- I8-4 (X77) constant reference offset per slice (slow sigma): best +0 / +3 / -1 dollars, gains <= +0.003: no stable
  offset. The level-offset reading is not supported; the small-edge bucket follows the previous side (inertia), not an
  offset.
- I8-3 (X76) per-wallet reference delay (`code9/wallet_delay.py`; frozen sigma, 14:06-16:30): bosona peaks at 1,083 ms
  (0.815), almach at 1,432 ms (0.852), **mo-money is flat and peaks later (700 ms 0.709, 1,432 0.771, 2,000 0.774, 3,000
  0.755)**; in the 24 windows where all three have >= 3 fills: 0.829 / 0.863 / 0.757. Mo-money reads an older or smoothed
  reference (its accuracy decays least with delay), but at its own best delay it is still 0.774 (< 0.80): the per-wallet
  signature of I8-3 is only partly met.

**B1 (X83) scope by 6-hour block and the module calendar (`code9/scope.py`, `results/iter9_scope.json`; every development
6-h block 10-08..10-31 with >= 30 trades, the lot as block aggregates).** Share of blocks where the universe holds
>= 0.80 of both trades and dollars: U1 (BTC 5m + 15m, R6) **0.34** (since the 10-16 version 0.34), U2 (+ BTC 4h) 0.45, U3 (+
BTC hourly/daily) 0.62, U4 (+ ETH all horizons) 0.89 (0.84), **U5 (every crypto Up/Down family) 1.00**. Minimum of min(trade
share, dollar share) by block type since 10-16 (U1 / U4 / U5): weekday 00 0.38 / 0.84 / 1.0, weekday 06 0.00 / 0.66 / 1.0,
weekday 12 0.59 / 0.87 / 1.0, weekday 18 0.32 / 0.73 / 1.0, weekend 00 0.00 / 0.56 / 1.0, weekend 06 0.00 / 0.58 / 1.0,
weekend 12 0.19 / 0.74 / 1.0, weekend 18 0.42 / 0.78 / 1.0. Iteration 8's coverage (0.868 / 0.891) is the VALIDATE
aggregate; per block R6 fails the scope bar in two thirds of the blocks. Only the all-crypto universe meets the bar in
every block type. Calendar gate (off Fri-Sun 18:00 ET to 09:00 ET next day), development windows since 10-16: BTC 5m
active 0.33 when the gate is off vs 0.76 otherwise, window AUC 0.68; BTC 15m 0.31 vs 0.65, AUC 0.63. BTC 5m off-runs >=
1 h: Sat 10-17 20:35 (1.3 h), Sat 10-17 22:30 (14.0 h), Sun 10-18 22:15 (14.2 h), Fri 10-23 20:40 (18.8 h), Sat 10-24
22:30 (15.0 h), Thu 10-29 18:00 (1.0 h, platform incident), Sat 10-31 16:53 (ongoing at 18:00): every long one starts on
a Friday-Sunday 16:35-18:30 ET evening except 10-31 (12:53 ET).

**M4 (X82): salt-counter forensics of the 10-31 16:53:54 BTC 5m switch-off (`code9/m4_salt.py`, `code9/m4_inspect.py`;
calldata of all 229 cluster fill transactions in 15:50-18:00, 254 new orders decoded; development).**
- The per-wallet counters run through the switch-off without a jump in all three wallets (bosona 739,095 at 16:53:54 ->
  740,208 at 16:55:16; almach 735,424 -> 736,744; mo-money 739,632 -> 740,867), and **the signing rate does not drop**:
  bosona 11.8 orders/s before (16:50-16:53:54) vs 13.6-15.5/s after (16:55-16:59) and 11.2/s over 17:07-17:52; almach
  12.4 vs 12.3/s; mo-money 13.4 vs 15.2/s. BTC 5m carried about half of the fills before the switch, so the engine did not
  stop signing at the switch: either its signing is paced at a fixed budget (removing BTC 5m reallocates it to other
  quotes) or it kept signing BTC 5m orders that were not posted (a gate after signing). The book shows no cluster-class
  500s in BTC 5m after 16:54 (iteration 7), so the orders, if signed, were never posted.
- **Two of the three engines were restarted 12-13 minutes later: almach's counter falls from 744,947 (17:06:21) to 559
  (17:07:21) and mo-money's from 744,640 (16:59:27) to 676 (17:06:52); bosona's runs on (749,304 at 17:07:21 ... 779,780 at
  17:52:51).** At the unchanged ~11.3-11.5 orders/s the restarts were at about 17:05:52 (mo-money) and 17:06:32
  (almach), 40 s apart, and the BTC 5m module stayed off after them. Reading: the switch-off was made inside the running
  processes of all three wallets within one second (a controller or a live configuration change, not a restart), and an
  operator (or a supervisor) restarted two processes one by one ~12 min later. X82's controller signature holds for the
  continuity and the simultaneity but not for the predicted rate drop; the later sequential restarts point to an operator.

**The slow sigma and the quote unit disagree (X74 I8-1 step 3; `code9/quote_slow.py`, `results/iter9_quote_slow.json`;
iteration 8's quote unit "a cluster-class 500 at the touch of s now", 10-31 14:06-16:30 BTC 5m, fit < 15:00, test >= 15:00,
same LightGBM; the Chainlink edge recomputed with v3600 k1 from the recovered ln(CL/K)).** Test AUC: activity 0.672;
+ Chainlink frozen 0.740, slow 0.737; + futures + Chainlink frozen **0.748**, slow **0.732** (slow - frozen, window
bootstrap [-0.033, +0.002]); univariate edge 0.623 vs 0.606; **in burst seconds (v300/v3600 > 1.5, n 690) the frozen edge
predicts the at-touch 500 at 0.695 and the slow edge at 0.368**. So where the cluster's exact-500 re-posts sit at the
touch, a FAST sigma describes them (in bursts its bids go to the underdog side), while the FILLS in bursts land on the
favourite (next item). The I8-1 signature "quote-unit AUC rises by 0.01-0.03" is not met.

**Which filled orders carry the slow-sigma side? (`code9/side_by_order.py`, `results/iter9_side_by_order.json`; 1,733 of the
2,244 12-18 fills joined to the filled order's original size in the calldata).** Exact-500 orders: all n 1,445 frozen 0.785
/ slow 0.841; **burst n 103: frozen 0.291 / slow 0.913, bought the favourite 0.72**; calm n 1,342: 0.823 / 0.835 (favourite
0.44). Other sizes >= 100 (n 211) 0.787 / 0.806; < 100 (n 77) 0.649 / 0.662. The burst fills are fills of the 500s on the
favourite. Together with the quote unit: in bursts the cluster re-posts its 500s mostly at the underdog's touch (fast-sigma
reading), yet the 500s that get FILLED are on the favourite: the fills in bursts select the side the takers sell (in a
burst, sellers dump the favourite into whatever bid sits there), so the per-fill side in bursts measures the taker flow
as much as the quote. The live per-fill gain of the slow sigma (0.786 -> 0.832) is therefore not evidence that the
engine's posture uses a slow sigma; the quote-level evidence points the other way, and the historical block clock
cannot decide (H-VOL). Status: X74 tried (not adopted), X79 tried (sigma_e not identified; quote level favours the fast
sigma), X75 open (natural experiment 11-02 12-18 with the full-depth book).

**M3 (X81): stale takers on the publish clock (`code9/m3_stale.py`, `results/iter9_m3_stale.json`; all 5,437 BTC 5m/15m
matches of 10-31 15:20-15:40 with taker signing ms; publish = stamp + 1,083 ms proxy; label = a cluster maker order in the
transaction, base rate 0.033).** 56% of takers are stale (a newer report published between signing and match - 150 ms).
P(cluster) by class: fresh 0.030 (lift 0.90), stale with the new report raising the fair of the token the taker is short
(dfair > +0.5 c) 0.037 (lift **1.11**), stale with the report lowering it 0.024 (0.73), stale flat 0.056 (1.68). The same
ordering holds for every signatureType (proxy 0.043 vs 0.024, Safe 0.038 vs 0.023, type 3 0.036 vs 0.026). Median
sign-to-match latency of takers who fill the cluster 764 ms vs 671 ms for others. The direction is the predicted one
(stale sellers of a newly favoured token fill the cluster more than stale sellers of a newly disfavoured one) but the
signature (>= 3x the base rate) is far from met: the cluster is not paid mainly by takers picked off on the publish clock.
X81 tried, not supported.

**M4 positive control: the daily 01:00 UTC restart (`code9/m4_restart0100.py`; calldata of the cluster's fills 10-31
00:40-01:50, development).** No cluster fill between 00:56 and 01:00; after it all three counters restart from zero within
about 20 s of each other (bosona salt 255 at 01:00:43, mo-money 921 at 01:01:24, almach's first post-restart fill later; at
the ~12 orders/s rate the restarts were at about 01:00:10-01:00:22). Before the restart the counters stood at 1.47-1.51
million (a day at ~17 orders/s). So the scheduled restart resets all three engines together; the 17:06 restarts of
10-31 (two engines, 40 s apart, the third not restarted) are not the schedule: an ad-hoc intervention after the 16:53
switch-off.

**Posture on the families nobody examined (`code9/posture_xfam.py`, `results/iter9_posture_xfam.json`; 10-31 12:00-18:00,
every cluster maker BUY fill in ETH/SOL 5m-15m-4h and BTC 4h with a shared-recorder match ms; the frozen BTC rule applied
unchanged with the asset's own Chainlink stream from the shared rtds feed, Gamma strike and Binance 1-s vol; no
parameter fitted).** Only 36 maker fills in 10 windows (BTC 4h 22 in one window, ETH 15m 8, SOL 5m 5, ETH 5m 1): frozen
**0.75**, slow sigma 0.58, cheaper side 0.64, always-Up 0.67; non-BTC (14 fills, 9 windows) frozen 0.79, slow 0.43; per
wallet frozen 0.60 / 0.90 / 0.82. Weak evidence (10 windows) that the same posture governs the other Chainlink families,
and again the fast sigma, not the slow one. On 10-31 these families carried few fills in the daytime; the weekend-night
blocks where they dominate are sealed so far.

**Kalshi with aligned strikes (X78 I8-5; `code9/kalshi_side.py`, `results/iter9_kalshi_side.json`; 18 quarters, 446 BTC 15m
fills of 10-31 12-18).** The basis floor_strike (BRTI 60-s mean before the open) minus priceToBeat (Chainlink TWAP-60 before
the open) runs from -$15 to -$35 over the block; both strikes are their own index's pre-open average, so the Kalshi yes
price is directly comparable with the Polymarket Up probability up to the basis drift. "PM cheap relative to Kalshi" (Up
iff Kalshi yes > PM Up mid) scores **0.345** vs the slow posture 0.917 (frozen 0.753); they disagree on 62% of the fills,
where the posture is right 96% and Kalshi 4%. The Kalshi level carries no side information beyond the posture (its
disagreement is dominated by a level offset between the venues); the iteration-8 lead-lag (Kalshi leads the PM 15m mid by
~1 s) stands as a market fact, not as the cluster's input. X78, X48 and A4b closed with these numbers.

**B2 (X84) settlement-source experiment on the Binance-settled hourly markets (`code9/b2_hourly.py`; 10-31 12-18, 40 cluster
BUY fills in 6 hourly markets, block clock).** Binance-candle fair 0.75 vs Chainlink fair 0.70 (cheaper side 0.53); the two
references disagree on 25% of the fills (Chainlink BTC/USD sat $134 below Binance BTCUSDT); with 10 disagreeing fills the
difference (2 fills) is far from the signature (>= 0.08 with n large). Inconclusive at this n; needs the weekend-night
blocks (where hourly/daily carry 13-19% of dollars) or a slim hourly-book recorder for the match clock.

**M2 (X80) ladder half-spread on the digital's risk (`code9/m2_spread.py`; 2,266 seconds with top rungs on both outcomes of
BTC 5m and 15m, 10-31 14:06-16:30, OLS fit < 15:00, scored >= 15:00).** h on [phi(z)/sqrt(tau), p(1-p), mid(1-mid), tau,
|F - mid|]: BTC 5m R^2 test **0.47** (frozen sigma) / 0.46 (slow), 15m 0.26 / 0.26; predicted top Up rung within a tick
0.26 (5m) and 0.28-0.30 (15m) vs 0.185 for a mid-minus-constant anchor. The spread rule explains part of the depth but
not to a tick (signature R^2 >= 0.6 and >= 50% within a tick not met), and the sigma choice does not matter here. The
level remains the state-machine problem (X71).

**B4 (X86) window-level anchor (`code9/b4_anchor.py`; 56 windows with >= 8 fills, 10-31 12-18).** Windows below 0.7 at zero
shift: 17 (frozen) / 11 (slow). The per-window best z-shift has no public correlate: Spearman with the 30 / 60 / 300-s
Binance returns, the open gap, v300/v3600 and the time left at the first fill all |rho| <= 0.21; in failing windows its
sign matches the 60-s trend 47% (frozen) / 45% (slow). No window-level public anchor (signature >= 70% of variance not met).

**Per-wallet split of the posture (`code9/wallet_sigma.py`).** Region D (sigma-free, the reference and the market disagree):
bosona 0.888, almach 0.886, **mo-money 0.799**; region A best (v3600 x 1): 0.833 / 0.889 / 0.756. Mo-money's deficit is
present in the sigma-free region too, so it is a clock or reference difference (older / smoothed report, as the delay
profile suggests), not a different sigma parameter.

**Where the money is (D4 / V9; `code9/region_pnl.py`; BTC 5m maker fills held to resolution, block-clock regions with the
Binance reference).** BUILD +2.2% on $1.59M: region D +3.1% (fills on the reference's side +4.4%), region A +2.1% of which
favourites +0.3% on $1.18M and **underdogs +12.1% on $213k ($25.7k = 73% of all PnL)**. STUDY +2.7%: D +18.5% (reference
side +23%), A favourites -1.5%, underdogs +16.1%. VALIDATE (aggregate) +4.3%: D +4.1% (reference side +12.8%, market
favourite -3.3%), A favourites +3.5% ($13.0k), underdogs +7.4% ($8.2k). The profit is concentrated in cheap underdog
fills when the reference and the market agree on the favourite (the cluster's underdog bids are filled when takers buy
the favourite through complement mints: it is short the favourite that retail flow overpays), plus the information part
(fills on the reference's side when the reference and the market disagree).

**Quote vs taker at the fill (`code9/quote_vs_fill.py`).** With the quote-unit label (an exact-500 add at/above the touch in
the last second), 80.5% of 5m fills have no fresh 500 on either side at the fill second: the label is too narrow to say
whether the resting 500 sat on one side only; where it is one-sided (19% of fills) the quote side equals the fill side
0.845. The resting-state book (adds minus removals per price) is needed to separate quote-bound from taker-bound sides.

**Quote-bound or taker-bound side? (`code9/touch_both.py`; 2,181 match-clock fills of 10-31 12-18; size at the touch of
both outcomes in the shared recorder's last top-of-book record before the match).** Touch size >= 500 on both outcomes
16% of fills (posture 0.83), only on the bought outcome 36% (0.87 frozen / 0.89 slow), only on the other outcome 16% (0.70
/ 0.81), neither 32% (0.71 / 0.79). Where exactly one outcome carries a >= 500 touch, it is the bought one in 70%. So in
about a third of the fills the quote alone decides the side (and the posture is right ~0.88 there), in a sixth the taker
chooses between two cluster-class touches, and the posture is weakest where the visible quote does not explain the fill.

**Pre-registration for the next development block, 11-01 06:00-12:00 UTC (written 10-31 21:40 UTC, before any data of that
block exists; it extends iteration 8's list).**
1. Forecast from the calendar gate (X83): BTC 5m has no cluster fills in 11-01 06-12 (Sunday 01:00-07:00 EST, inside the
   weekend-night gate); BTC 15m probably off too. If so, the side checks run on whatever Chainlink-settled family is on.
2. Side: `side_posture_match_clock` as frozen (R6, 1.4 x v300) is the rule; `it9_slow_sigma_v3600` is the secondary
   variant; both reported per family, per wallet, per half, by vol regime (`it9_by_regime`) and per taker event with the
   own-history baseline (`it9_taker_events`). Pass mark for the component unchanged (>= 0.80 pooled, >= 0.77 per half).
   The slow variant replaces the frozen one only if it beats it pooled AND in the burst regime on this block AND on the
   next block with BTC 5m on.
3. Cross-family posture (`code9/posture_xfam.py` unchanged) on every ETH/SOL/BTC-4h fill of the block: frozen vs slow.
4. Quote unit and print selection (iteration 8 item 3) and the quote-oracle ceilings, if BTC 5m or 15m is on.
5. M4 follow-up: salt counters at every module switch in the block (on or off) and at the 01:00 restart of 11-01 (sealed
   block 00-06: not read; the next 01:00 in a development block is 11-02 00-06).
6. X75 natural experiment: 11-02 12-18 (US open 14:30 UTC after DST); compare the side under the frozen and the slow sigma
   in the hour after the vol ramp, with DVOL from the historical endpoint.

**X65 counter conservation at the switch-off (own raw recorder, BTC 5m current+next and 15m current).** Exact-500 adds per
minute: 14:06-16:30 15m 260 + 5m 203; 16:20-16:50 281 + 130; 17:29-18:00 (BTC 5m off) 197 + 9 (other makers). The three
counters kept signing ~12 orders/s each (~2,160/min) across the switch. The 15m posting did not absorb the BTC 5m budget
(it fell), so signing is decoupled from the recorded posting (about 5x the exact-500 add rate before, 10x after): either
a fixed-cadence signer that moves its budget to unrecorded markets, or orders signed and never posted.

**B9: maker share and rebates (`code9/b9_share.py`, BUILD BTC 5m).** The cluster's maker fills are 1.7% of all traded shares
(median window 0.6%, p90 4.8%); its share rises with the window's total volume (Spearman +0.18; top quintile 2.2% vs
1.4-1.6%): it does not seek low-competition windows. Maker rebates $14.5k and rewards $3.4 over BUILD; fee rate 0.07 in all
4,032 BTC 5m windows.

**X76 step 3: age of the filled orders by wallet (`code9/wallet_age.py`; 1,286 confirmed orders of 10-31 14:04-16:13 joined to
the posture).** Median age (raw add to match) 574-753 ms, p75 1.8 s for almach and bosona vs **2.5 s for mo-money**;
posted before the latest Chainlink publish (proxy) 59-64% in every wallet; posture accuracy of those "stale" orders
0.82-0.86 vs "fresh" orders (posted after the latest publish, i.e. re-posts between reports) 0.76-0.79; mo-money is lower
in both (0.816 / 0.760). Its wrong-side fills are not explained by older orders (its stale share is the same); only its
resting tail is longer. The I8-3 signature is not met; mo-money stays the weak wallet (0.76-0.80) for an unknown reason
(clock, feed or parameters).

**B3 with own-history inertia (`code9/b3_combined.py`; 1,297 taker events of 10-31 12-18; theta chosen on 12-15, scored on
15-18).** Rule: if |edge| <= theta and a previous event exists in the window, repeat the previous event's side, else follow
the posture sign. Slow sigma: theta 0.05 chosen, **test 0.880** vs the previous-event baseline 0.859 and the posture alone
0.830; frozen sigma: theta 0.2 chosen, test 0.867 vs 0.861 (posture alone 0.799). So the side behaves as a state that
persists until the Chainlink edge moves by more than ~5 c (slow-sigma fair) against it; this uses own state (the previous
own fill) and is reported separately from the public posture. Pre-registered for 11-01 06-12 as a secondary description
(theta 0.05 slow, theta 0.2 frozen, unchanged).

**R6 on the development block 10-31 00:00-06:00 UTC, which no earlier analysis had scored (`code9/eval_0006.py`,
`results/iter9_eval_r6_1793404800_1793426400.json`; block clock; no live recording and no Chainlink, so R5 = R3).** BTC 5m
(72 windows, 1,178 maker fills, the wallets' maker return -10.0%): presence **0.679 vs activity 0.695 (gain -0.016)**,
within active windows 0.670 (own-inventory variant 0.742); side (bin level) 0.605 (n 281; last-print favourite 0.367);
price within a tick 0.683; per-window PnL corr 0.268 / 0.337 (62 windows). BTC 15m (24 windows, 412 fills): presence
**0.853 vs 0.815 (+0.039)**, side 0.914 (n 105; favourite 0.80), price 0.777, PnL corr 0.729 / 0.680 (20 windows). Union
presence 0.771 vs 0.767 (+0.004), side 0.689, price 0.707; scope 0.914 of trades / 0.949 of dollars. On this fresh block
(Friday night ET, the Chainlink noise regime, a losing block for the cluster) the BTC 5m presence model is no better than
market activity, while the 15m model holds its VALIDATE level.

**The posture on the Binance-settled BTC hourly family, historical block clock (`code9/hourly_side.py`; every cluster BUY
fill in the 334 hourly markets of 10-16..30; strike = Binance at the hour start).** BUILD 1,781 fills / 134 markets: frozen
sigma 0.563, slow (v3600) **0.657**, region D 0.884 (10% of fills), cheaper side 0.486; STUDY 893 / 70: 0.458 vs **0.682**;
VALIDATE (aggregate) 738 / 69: 0.607 vs **0.634**, region D 0.988. In the hourly family the slow sigma wins in every split,
including VALIDATE, and the volatility-free part is near-deterministic where it applies.

**Horizon-matched sigma? (new hypothesis V10; `code9/horizon_sigma.py`).** Lookback scan L 300-7200 s x k 1 / 1.4: BTC 5m
BUILD best v3600 x1 (0.620), STUDY v300 x1 (0.565), VALIDATE v900 x1.4 (0.655; scale-driven); live 5m best v3600 (0.811;
v300 0.768), live 15m best v3600 (0.917; v900 0.868). A lookback equal to the window length is not what fits; a ~1-h
lookback fits the live 5m and 15m fills and the hourly family, while the BTC 5m historical VALIDATE wants a larger scale.
V10 rejected; the slow sigma stays a pre-registered secondary.

**First per-family presence models beyond BTC 5m/15m (X83 groundwork; `code9/hourly_presence.py`, exploratory, not part of
the frozen rule).** Unit (market, side, 10-s bin), label = >= 1 cluster BUY trade (activity, all roles), clean data-api
tapes, Binance 1-s, clock; LightGBM fitted on 10-16..26, scored on VALIDATE 10-27..30 (aggregate). BTC hourly (204 / 69
markets, 49,680 test bins, 0.9% positive): activity **0.755**, rule (+ Binance fair, edge, z, vol, clock) 0.751, rule without
clock 0.759; gain -0.004 [2-h bootstrap -0.029, +0.021]. BTC 4h (59 / 22 markets, 0.34% positive): activity 0.615, rule 0.617,
without clock 0.635. Neither family's presence is decoded beyond market activity; for scope they are the families the
universe must add (U3 covers 0.62 of blocks, U4 0.89).

**The quote unit for BTC 15m and a lookback scan at the quote level (`code9/quote15.py`, `code9/quote_slow.py`,
`results/iter9_quote15.json`; own raw recorder 10-31 14:06-16:30; label = a cluster-class exact-500 at the touch of s now;
fit-free univariate AUC of the Chainlink edge).** BTC 15m (9 windows, 16,126 seconds, 2.2% positive): frozen 0.724, v300 x1
0.756, v900 0.761, v1800 0.767, **v3600 0.775, v7200 0.787**; test half (>= 15:00) frozen 0.731 vs v3600 0.764; burst seconds
(n 1,706) 0.593 vs **0.689**; LightGBM on the thin 3-window fit: activity 0.551, + frozen 0.677, + slow 0.689. BTC 5m (28
windows): frozen 0.613, v300 0.599, v900 0.607, v1800 0.610, v3600 0.601, v7200 0.605 (flat). So for the 15m ladder the
slow sigma is better at the quote level as well as at the fill level (0.917 vs 0.753), while for the 5m ladder the sigma
barely matters at the quote level (0.60-0.61) and the bursts favour the fast one. Reading: the posture's dependence on
sigma is a 15m (and hourly) matter; the 5m posture is dominated by the reference move itself. Pre-registered for 11-01
06-12 and later blocks: per family, the slow variant replaces the frozen one only if it wins on the new block(s).

**Pre-registration H-VOL15 (written 21:54 UTC before scoring): BTC 15m block-clock replication of the slow sigma (code9/vol_hist.py <split> 15m: BUILD 22,424 / STUDY 1,356 / VALIDATE 2,996 cluster maker BUY fills of BTC 15m from p15/cluster_btc15m_fills).** Candidate fixed in advance: v3600 k1 vs the frozen 1.4 x v300. Confirmation on VALIDATE (aggregate): gain > 0 with the 2-h block bootstrap lower bound > 0. If it passes, the 15m posture of the next rule uses v3600 k1 (pre-registered for 11-01 06-12 as well).

**H-VOL15 result (`code9/vol15_score.py`, `results/iter9_vol15.json`): the slow sigma does not replicate for BTC 15m on the
historical block clock either.** BUILD 22,424 fills: frozen 0.625 vs v3600 0.631 (+0.006, CI [-0.022, +0.033]; best k1
lookback v300 0.652); STUDY 1,356: 0.557 vs 0.653 (+0.097, [+0.028, +0.162]); **VALIDATE (aggregate) 2,996: frozen 0.799 vs
v3600 0.750, gain -0.049 [-0.107, +0.007]: the pre-registered confirmation fails.** The VALIDATE fills are again
underdog-heavy (cheaper side 0.636).

**Deribit implied volatility with a fixed scale (X75 candidate (d); `code9/dvol_sigma.py`).** sigma = c x DVOL (per second),
c 0.2-1.0: the best c is 0.2-0.3 on STUDY (5m 0.55, 15m 0.68) and on live 10-31 (5m 0.79, 15m 0.89), but 0.5-1.0 on VALIDATE
(5m 0.58, 15m 0.61), where it still loses to the frozen sigma (0.645 / 0.799). Median realised vol: VALIDATE v3600 4.5e-5/s,
STUDY 3.5e-5, live 10-31 2.3e-5; DVOL 6.7-7.2e-5 throughout. No constant scale fits; candidate (d) rejected. The
period-dependence (VALIDATE wants a large sigma for both families, every other sample a slow or small one) points to the
fill mix (underdog fills from takers buying favourites) rather than to a sigma the engine uses; the decisive data are
quote-level (15m: slow sigma better) and the next development blocks.

**Why the historical VALIDATE wants a large sigma: the fill mix is complement mints (`code9/mint_side.py`; every lot fill
joined to the taker order of its transaction in the lot calldata).** STUDY: 81% of the cluster's BTC 5m maker fills are
mints (the taker BUYS the complement), landing on the underdog 51% of the time (frozen 0.565, slow 0.572); 19% are direct
sells (underdog 38%; 0.445 / 0.492). VALIDATE (aggregate): **88% mints, underdog 69%** (frozen 0.654, slow 0.567); 12% direct
(underdog 57%; 0.579 / 0.539). On 10-27..30 takers mostly bought the favourite, and those mints filled the cluster's
underdog bids; a large-sigma fair "predicts" that because it always calls the underdog cheap. The historical block-clock
side mixes the posture with the takers' choice of token, so it cannot decide the engine's sigma.

**Groundwork for the family-general universe (`code9/fetch_fam.py`).** Data-api taker tapes of every BTC 4h (90) and BTC
hourly (334) market the cluster traded in 10-16..10-30 are in `.cache/re/directional-maker/fam/` (markets and tapes per
family) for the next iteration's per-family presence models.

## Iteration-9 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m presence AUC, no own state): unchanged at **0.716**; the frozen rule
  stays **R6** (no decision changed; `evaluate()` now also reports the pre-registered slow-sigma variant, the vol regime,
  halves and taker events with the own-history baseline).
- Paradigm (pivot): the engine's pricer state as a latent variable. The posture side splits into a volatility-free
  information part (the reference and the market disagree on the favourite: 0.855 live) and a volatility comparison (they
  agree: 0.76). The slow-sigma hypothesis from the panels fails its pre-registered historical replication (VALIDATE 0.569
  vs 0.645; the block clock prefers a larger sigma scale, not a lookback), fails the quote-level test (0.732 vs 0.748;
  bursts 0.37 vs 0.70) and the cross-family test (0.58 vs 0.75, n 36), while fitting the live fills better (0.832 vs 0.786):
  in bursts the 500 re-posts sit at the underdog's touch but the favourite's 500s are what gets filled. Not adopted.
- New facts: the side behaves as a state (own-history baseline 0.865 per event; posture + 5-c inertia 0.880 held out, own
  state); the switch-off of 10-31 was made inside the running processes (counters continuous, signing rate unchanged,
  posting halved), and two engines were restarted ad hoc 12-13 min later (the daily 01:00 restart resets all three within
  20 s); R6's universe fails the scope bar in 66% of 6-h blocks (only all crypto Up/Down passes everywhere); the profit is in
  underdog fills when reference and market agree and in reference-side fills when they disagree; mo-money is weaker in
  both regions and its orders rest longer, but not older relative to the publish.
- Closed this iteration (tried / measured): X74, X77-X82, X84-X86, A4, A4b, X48, X58, X60, X65, X66, X70, B9. Open: X75, X76,
  X83 and the earlier B9-free list (C4b, D3, X9, X24, X39, X41, X52, X54, X57, X59, X61, X62, X64, X67, X68, X71).
- Recorders: shared live.py running; no new recorder this iteration (the delayed full-depth recorder for 11-01 05:55-12:00
  and dz_rtdsbn are still scheduled / running from iteration 8).

**Next steps (iteration 10; the next development block is 11-01 06:00-12:00 UTC).**
1. Run the pre-registered 11-01 06-12 checks (iteration 8 list + iteration 9 items 1-6): side frozen vs slow per family /
   wallet / half / regime / taker event, cross-family posture, the forecast "BTC 5m off".
2. Build the family-general universe (X83): per-family presence (R3 class with family, horizon and asset as features, the
   calendar gate as a selection input) for BTC 4h / hourly / daily and ETH first (U4 covers 0.89 of blocks), using the
   tapes in `fam/` plus ETH tapes; freeze it before the next future exam and report coverage per block type.
3. The resting-state book (adds minus removals per price per side from the raw recorder) to separate quote-bound from
   taker-bound sides, then the strict-fill replay (X64).
4. X75 natural experiment on 11-02 12-18 (US open after the DST change): frozen vs slow sigma through the vol ramp.
5. X76 per-wallet burst hazard on the 11-01 full-depth book; X59 RTDS Binance relay clock; X61 / X62 on the 11-01 block.
- Addendum to the checkpoint (21:56 UTC): the 15m quote unit favours the slow sigma (univariate 0.775 vs 0.724; bursts 0.689 vs 0.593) while the 5m quote unit is flat across lookbacks (0.60-0.61); the pre-registered BTC 15m historical replication (H-VOL15) fails on VALIDATE (0.750 vs 0.799); the VALIDATE fill mix is 88% complement mints landing 69% on the underdog, which is why every historical VALIDATE comparison prefers a large sigma. The sigma question is a 15m (and hourly) question and is left to the next development blocks.

**C4b: change points vs Polymarket announcements (one web search, 21:57 UTC).** Taker fees on the 15m crypto markets began in early January 2026 ([The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates), [Cointelegraph](https://cointelegraph.com/news/polymarket-quietly-adds-taker-fees-15-minute-crypto-markets)); the 5m markets entered the maker-rebate schedule on 2026-02-12 at 20% fee-curve weighted ([docs](https://docs.polymarket.com/polymarket-learn/trading/maker-rebates-program)); the current crypto taker fee rate is 0.07 with a 20% maker rebate ([fees docs](https://docs.polymarket.com/trading/fees)). None of these matches the cluster's change points (06-21/22, 10-16, 10-31); no announcement for those dates was found.

**Mo-money's deficit sits in its 500-share rungs (10-31 12-18 match-clock fills joined to the filled order's size).** Posture accuracy of fills of exact-500 orders: bosona 0.835, almach 0.807, **mo-money 0.735** (86% of its sized fills); other sizes 0.703 / 0.743 / 0.822. The weak wallet's main rung generator is the one off the posture: a per-wallet clock or parameter of the 500-rung pass (X76), not its remainders.

- Checkpoint update (22:00 UTC): C4b and X39 were also tried (above / in state.json); X52 and X68 carry a feasibility measurement (taker signing ms in 97% of the lot's cluster-fill transactions) but stay open. Open catalog items: D3, X9, X24, X41, X52, X54, X57, X59, X61, X62, X64, X67, X68, X71, X75, X76, X83. Add to the next steps: decode mo-money's 500-rung pass (its 500 fills are 0.735 on the posture vs 0.81-0.84 for the other wallets).

**Mo-money's 500 rungs by reference delay (`code9/momoney_500.py`; 10-31 14:06-16:30 fills joined to the order size).** Exact-500 fills: bosona 0.817 / 0.849 / **0.852** / 0.814 / 0.730 at 700 / 1,083 / 1,432 / 2,000 / 3,000 ms (n 345), almach 0.780 / 0.848 / **0.865** / 0.838 / 0.721 (n 495), mo-money 0.687 / 0.706 / 0.755 / **0.763** / 0.740 (n 527). Mo-money's other-size fills (n 101) score 0.851 at 1,432 ms, like the other wallets' 500s. So the weak part of the cluster is one rung type in one wallet: mo-money's 500s, which are also first in the match order (mechanics panel: before almach in 74%, before bosona in 90%) and rest longer (p75 2.5 s vs 1.8 s). Candidate for iteration 10: mo-money's 500 is the earlier-posted (queue-front) rung that the next re-price pass does not move, i.e. a different rung of the same ladder, not a different clock.

**Posture at the add time vs the match time (`code9/posture_at_add.py`; iteration-6 confirmed filled orders, 10-31 14:04-16:13).** Exact-500 orders: almach 0.771 at the add / 0.825 at the match (n 411), bosona 0.768 / 0.851 (n 241), **mo-money 0.646 / 0.722** (n 424); the posture flips between add and match for 9-12% of the orders in every wallet. Mo-money's 500s are off the posture already when they are posted, so they are not stale rungs left behind by a slower re-price: its 500 pass places rungs on the disfavoured side more often (a different rung of the two-sided ladder, or another reference). Every wallet's filled orders agree with the posture more at the match than at the add (orders that turn against the posture are pulled before they fill).
- Final open list (22:03 UTC; X54 closed with the re-derived order facts): D3, X9, X24, X41, X52, X57, X59, X61, X62, X64, X67, X68, X71, X75, X76, X83.
- Recorders at 22:03 UTC: shared live.py running (status 20:56); own examrec (pid 24316), dy_rtds (29508), dz_rtdsbn (32308) writing (status files 22:03); the delayed full-depth recorder launcher (17192) waits for 11-01 05:55 UTC. Iteration 9 ends at 22:04 UTC (69 minutes).

### Iteration 10 (2026-10-31, local Windows laptop, started 22:33 UTC; 585 of 1,200 budget minutes used before it)

Read first: BRIEF, NOTES (iteration 9 in full), state.json, FINAL_RULE.md, panels/iter9_{information,mechanics,
assumptions}.md. Calendar (`tools/sealed.py directional-maker`, 22:34 UTC): released h1, h2; development [10-23, 10-31
06:00) and [10-31 12:00, 18:00); the current block (10-31 18-24) and 11-01 00-06 are sealed; the next development block
is 11-01 06-12 UTC, after this iteration ends: again no new live development data. Shared live.py running (status
22:34 UTC: clob_crypto, clob_wallets, rtds, sports connected). Panel proposals added as catalog items: information
I9-1..I9-5 = X87-X91, mechanics M1-M5 = X92-X96, assumptions A1-A4 = X97-X100.

**Competing explanations (iteration 10) and the observation that separates them**
1. E1 two-process maker (panel M1/A4): the ladder carries schedule-size posture rungs (Chainlink skew) and imbalance
   pairing bids (size = |own imbalance| on the under-held outcome); the money is the locked pairs plus rebates, and the
   posture is a defence that decides which side fills first. Separates: per-window PnL split (locked pairs vs residual vs
   rebates); the pairing bid's price follows a held-side anchor (1 - held-side cost - m); the residual is ~0 or negative.
2. E2 information-edge directional maker (FINAL_RULE's reading): the profit is the residual from the Chainlink lead;
   pairs are incidental. Separates: residual PnL positive in every split and rising with posture accuracy; locked pairs
   small.
3. E3 regime- or version-specific posture (panel A1, alternative): the Chainlink skew is visible only in the noise regime
   since 10-30/31 (or a recent version); the smooth-regime engine used another side rule. Separates: the sigma-free
   region D on a historical match clock (taker signing ms + calibrated delay) with the real Chainlink value: >= 0.80
   (stable rule) vs ~0.60 (regime-specific), after the same proxies reproduce ~0.85 on 10-31 12-18.
4. E4 queue-selection artefact (panel A2a): mo-money's deficit is its front-of-queue rank (it is filled during the brief
   life of wrong-posture rungs), not a different configuration. Separates: P(filled | wrong posture at the add) by queue
   rank within burst triplets, compared at equal rank across wallets.
5. E5 lost cancel races (panel M5): off-posture fills are takers that arrive before the re-price after a publish that
   flipped the posture. Separates: the posture at the taker's arrival (sign_ms + b - lambda) beats the match-clock posture
   by >= 2 points, concentrated where a flipping publish fell inside [sign_ms, match].
6. E6 rebate and volume engine (unlikely): the objective is maker-rebate share; before rebates the 15m family is flat,
   and the side rule only limits adverse selection. Separates: rebates vs PnL by family; volume tilted to p ~ 0.5 where
   the fee 0.07 p(1-p) peaks.
7. E7 operator clocks (panel I9-3/A3): a UTC cron (01:00 restart, Monday sweep) plus a US-Eastern human schedule (size
   session, weekend gate). Separates: switch times across the US DST change (11-01): UTC features shift by one hour in
   ET-driven components only (observable only from 11-01 06:00 development blocks).
8. E8 inventory-target engine (unlikely): every rung's side steers the window inventory to a target ratio. Separates:
   schedule rungs on the under-held side (panel: 29-31%, i.e. anti-balancing: already against E8 for schedule rungs).

This iteration discriminates E1 vs E2 (M1 pairing-bid decode + A4 PnL split, all on disk), E3 (A1 calibrated historical
match clock; needs Chainlink seconds from the 30-day endpoint, fetched now, which also starts I9-4's rescue of BUILD and
the lot before 11-08), E4 (A2a) and E5 (M5) on the 10-31 12-18 recordings.

**Pre-registration A3 (X99), written 23:13 UTC 10-31, before any post-DST data exists (US DST ends 11-01 06:00 UTC; EU
ended 10-25).** Every clock feature gets two frozen variants, UTC and US-Eastern (ET = UTC-4 before 11-01 06:00, UTC-5
after): hour of day, US-session flag (ET 08-17 = UTC 12-21 before, 13-22 after), size session (500s in the weekday
12-21 UTC session before the change; ET reading: 08-17 ET), calendar gate (Fri-Sun 18:00-09:00 ET; UTC reading: the
same UTC hours as before, 22:00-13:00 UTC), daily restart (01:00 UTC; ET reading 21:00 ET = 02:00 UTC after the change).
Observations, in development blocks only, timestamps only (never sweep amounts, recipients or which wallets swept):
(1) 11-02 00-06 UTC: time of the three salt-counter resets and of any treasury transaction (01:00 UTC -> UTC cron; 02:00
UTC -> ET cron). (2) 11-02 12-18 UTC: time of the first exact-500 order of the weekday session (12:00 UTC -> UTC; 13:00
UTC -> ET). (3) 11-01 18-24 UTC (Sunday evening): any BTC 5m/15m switch, at which ET hour. Each component's convention
is frozen by the observation that bears on it; R6's clock features are then re-scored under both on the post-DST
development blocks. Until then the frozen rule keeps UTC (no decision changes).

**M1 (X92): the imbalance pairing bid on the lot (`code10/m1_pair_lot.py`, `results/iter10_m1_pair_lot.json`; class frozen
as in the panel: calldata original size not a schedule size and within 2% of |own imbalance| at the block second; schedule
set {500, 1000, 2000, 250, 125, 100, 62, 50, 40, 31, 25, 20, 12, 10, 5, 300, 200}).**
- Share of the cluster's BTC 5m maker BUY fills: pairing class 11.2% (STUDY) / 14.1% (VALIDATE aggregate), other
  non-schedule sizes 2.9% / 4.4%. On the under-held outcome: pairing 1.000 / 1.000, other non-schedule 0.996 / 0.985,
  schedule rungs 0.298 / 0.316 (they pile onto the held side). Panel finding replicated.
- **Price: the pairing bid is not priced off the wallet's own held side.** Pair cost (limit + held-side VWAP) median 0.91
  (STUDY) / 0.81 (VALIDATE), q10-q90 0.50-1.42 / 0.44-1.24; below 1 in only 61% / 72%. Within a tick of 1 - held VWAP - m:
  1.4-4.7% for every m in 0-5 c; of 1 - last held fill price - m: 1.7-4.8%. The M1 signature (>= 60% within a tick of
  one own-cost anchor) fails: the pairing bid is a size/side decision (complete the pair) placed at a market price, like
  the posture rungs (the block-clock price rule "last print - 0.01" applies to both).
- PnL held to resolution by class: pairing fills +1.1% (STUDY, $13k) / -0.3% (VALIDATE, $81k); other fills +1.5% / +4.7%.
- **A4 (X100) window split (per wallet x window, all BTC 5m BUY activity): locked pairs min(Up, Down) x (1 - avg Up - avg
  Down) vs residual.** STUDY: locked -$0.9k, residual +$5.7k (total +$4.8k on $185k); VALIDATE (aggregate): locked
  +$33.3k, residual -$10.3k (total +$23.0k on $586k). var(residual)/var(total) 0.69 / 0.58, corr(total, residual) 0.86 /
  0.79, corr(total, locked) 0.56 / 0.65. Neither part is positive in every split: A4's signature ("the residual is ~0 or
  negative and pairs positive in every split") fails on STUDY, and E2's ("the residual earns in every split") fails on
  VALIDATE. The residual carries most of the cross-window variance, so the outcome bar needs the directional fills
  reproduced, not only the pairs.

**A1 (X97): is the posture a stable rule? Calibration first (`code10/a1_delay.py`, `code10/a1_score.py live`,
`results/iter10_a1_delay.json`, `results/iter10_a1_live.json`; 10-31 14:06-16:30).** Taker sign-to-match delay (1,649
takers of cluster fills): median 620 ms (q25 260, q75 2,455; by signatureType 404-640 ms); block second minus match
1.52 / 2.29 / 2.98 s (q10 / median / q90). Pre-registered match clock T_hat = clip(sign_ms + 620, block - 3.0 s, block -
1.5 s): |T_hat - T| median 368 ms. On 737 joined fills the sigma-free region D (Chainlink and market disagree on the
favourite) scores: truth (match ms, book mid) **0.965** (n 141); T_hat + Chainlink + book mid 0.908; **T_hat + Chainlink +
last clean print at b - 3 (the historical proxy) 0.953**; block clock (report b - 4) + last print 0.952; fill-price
diagnostic 0.898. The historical proxies reproduce the truth: neither the block clock nor the print proxy destroys the
region-D signal.

**M5 (X96): off-posture fills as lost cancel races, rejected (`a1_score.py live`, m5_cancel_race; 647 fills with taker
sign_ms).** The posture with the report in force at the taker's arrival (sign_ms + b - lambda, b {0, 190} ms, lambda {0,
100, 150} ms, the pre-registered grid) scores 0.698-0.718 vs 0.739-0.740 at the match on the same rows; where the two
disagree (5-8% of fills) the match-clock posture is right 0.70-0.75 and the arrival posture 0.25-0.30. The cluster's
filled rungs agree with the report at the match, not at the taker's arrival: its ladder had already re-priced for the
publish that arrived between the taker's signing and the match. E5 rejected.

**M2 (X93): a per-phase posture rule (`code10/m2_phase.py`, `results/iter10_m2_phase.json`; 2,244 live fills; candidates
frozen, slow v3600, TWAP lock-in digital; per phase the best on 12-15, scored on 15-18).** Chosen: slow for BTC 5m >= 120
s and both 15m phases, lock-in for 5m 60-120 s, frozen for 30-60 s and < 30 s. Test 15-18: **0.835 vs frozen 0.813** (n
1,644); per wallet mo-money 0.777 (0.751), almach 0.878 (0.868), bosona 0.860 (0.830); 60-120 s phase 0.782 (frozen 0.756;
slow would be 0.848). Per wallet and phase (frozen, whole block): mo-money 60-120 s 0.672 (n 177), 15m >= 120 s 0.640;
almach 0.80 / 0.80; bosona 0.725 / 0.756. The phase gain is mostly the slow sigma again, which failed its pre-registered
historical replications; the M2 signature (60-120 s >= 0.82, every wallet >= 0.80) is not met. Not adopted; the per-phase
rule is pre-registered as a secondary for 11-01 06-12 (choices above frozen).

**I9-2 (X88): can the examiner label the quote unit? (`code10/i92_label.py`, `code10/i92_dx.py`).** From the SHARED
recorder: no. Its `clob_crypto` files hold only 21,751 top-of-book snapshots for the 28 BTC 5m tokens over 14:06-16:30
(~0.09 per token-second): the "+500 at the touch" label has recall 0.010-0.022 (0.018-0.039 within +-1 s) against the raw
label. From the OWN exam recorder `dx_clob` (code6/examrec.py, schedule-size deltas within 3 ticks with server ms; BTC 5m
current+next, 15m current; running to 11-03 00:00 UTC, status updated 22:57 UTC): **recall 1.00** on the 15:53-16:30
overlap (7 windows, 4,200 cells), precision 0.44 (it also marks +500 adds that left the touch within the second; the raw
label keeps only those still at the touch: definitional, fixable from dx's touch fields). So the quote unit is examinable
on BTC 5m/15m through 11-03 00:00 from dx_clob, not from the shared recorder.
- New recorder (I9-2 step 3 / M4 = X95): `code10/famrec.py`, feed **dw_clob**, examrec's reduction for ETH, SOL, XRP, BNB,
  DOGE, HYPE 5m (current + next) and 15m (current); started 22:59:41 UTC (pid 31812 launcher), hard stop 11-03 00:00 UTC,
  disk cap 280 MB, status `.cache/re/directional-maker/famrec_status.json`. Hourly/daily and 4h books are not in it.

**I9-1 (X87) step 1: the pmxt archive version check (`code10/pmxt_pilot.py`, `results/iter10_pmxt_pilot_2026-07-22T13.json`).**
Host verified 23:00 UTC: `HEAD r2v2.pmxt.dev/polymarket_orderbook_2026-07-20T13.parquet` 200 (527,534,573 bytes),
08-09T13 200, 10-20T13 404. Hour 07-22 13:00-14:00 UTC, 11 BTC 5m windows, 490 cluster trades; the row groups of those
markets cost 67 MB of range reads (4.2 M events: 4.11 M price_change, 70,780 book, 33,266 last_trade_price, 11
tick_size_change). Calldata of 150 cluster-fill txs (166 cluster orders): **timestamp 0 and metadata 0 in 100%** (the
October engine family), per-wallet salt counters monotone 92-100% at **25-32 orders/s** (October ~11-18/s); original
sizes 500 (75), 300 (43), 50 (27), plus pairing-class sizes (454.89, 370.17, 123.48, ...). Book fingerprints of the
filled orders (add of exactly the original size at the limit price before the same-tx trade found for 62%): age median
1,044 ms (October ~0.7 s), at the touch 49% (October 78%), posted a median 69 ms after the market's previous trade
(October ~95 ms), 26% in same-size same-price bursts within 20 ms; of all 500-share adds in these books 12% are in such
bursts (300s 3%, 50s 6%). Verdict: same engine family with a different configuration (faster signer, less at the touch,
500/300/50 rungs); usable for ladder mechanics, queue and replay calibration; no Chainlink history exists for July, so
not for the Chainlink posture. The reduced events of this hour (36 MB) are cached in `.cache/re/directional-maker/pmxt/`.

**A1 (X97) on the lot and on 10-31 00-06: the strong posture is NOT a stable rule (`code10/a1_score.py lot`,
`code10/a1_0006.py`, `code10/a1_hours.py`; results `iter10_a1_lot.json`, `iter10_a1_dev1031_0006.json`,
`iter10_a1_hours.json`).** Chainlink values come from the detached fetch (`code10/fetch_cl_hist.py`; one random
pre-registered order over the lot's fill stamps, so the scored fills are a random subsample; ~12-13% of the lot fills at
23:11 UTC). Same pre-registered proxies as the calibration.
- STUDY (case by case; 979 fills scored): region D share 0.112 (live 0.19-0.20); **bought the Chainlink favourite 0.657 (n
  108; schedule-size rungs only 0.667, n 105)**; per-window mean 0.64 over 32 windows (one window holds 28 of the fills);
  per wallet mo-money 0.645, almach 0.605, bosona 0.735; fill-price diagnostic 0.455.
- VALIDATE (aggregate; 3,663 fills scored): region D share 0.042; **0.680 (n 153; schedule only 0.697)**; fill-price
  diagnostic 0.349.
- By the size of the disagreement |fair_CL - mid| (frozen sigma): STUDY 0.70 / 0.75 / 0.57 / 0.71 (gaps 0-0.05 / 0.05-0.1 /
  0.1-0.2 / > 0.2); VALIDATE 0.92 / 0.63 / 0.54 / 0.50. The live block's accuracy rises with the gap (0.84-0.86 above 0.1);
  the lot's does not (it falls on VALIDATE). Binance does not explain the misses: in Chainlink-region D the cluster buys the
  Binance favourite 0.50 / 0.56, and its Chainlink accuracy is about the same whether Binance agrees with Chainlink or with
  the market.
- The frozen posture with S = the real Chainlink value (instead of the Binance stand-in): STUDY 0.567 (Binance 0.543),
  VALIDATE 0.710 (0.645). The real reference helps by +0.02 / +0.07, far from the live 0.79.
- **10-31 00:00-06:00 UTC (development, block clock, all 1,178 BTC 5m fills scored): region D 0.679 (n 109, share 0.093)**,
  by hour 00 UTC 0.24 (n 37), 02 0.93 (n 15), 05 0.88 (n 50); per wallet bosona 0.714, almach 0.581, mo-money 0.774. On the
  lot, hour 00 UTC is low too (VALIDATE aggregate 0.33, n 21) while 12-13 UTC are 1.0 (n 30): region D fills cluster in a
  few windows and the accuracy swings by window.
- Verdict for A1: with proxies that reproduce the 10-31 truth (0.953 vs 0.965), the lot's disagreement fills land on the
  Chainlink side only about two thirds of the time (0.66-0.70, window mean 0.64), so the 10-31 12-18 posture (0.96 in
  region D, 0.79 per fill) is regime-, time- or version-specific, not the engine's stable rule over its history. The side
  component stays the frozen R6 rule for live blocks (the exam blocks are in the same regime as 10-31), tagged
  VALIDATE-only with this failed historical replication. What drives the lot's side in region D is not decoded: neither
  Chainlink nor Binance nor the market favourite (0.32-0.34).

**Chainlink noise regime by hour (`code10/cl_noise.py`, `results/iter10_cl_noise.json`; 30-s runs of consecutive endpoint
seconds).** 10-31 00:00-04:00 UTC (16 runs): sd of 1-s changes $3.2-8.8, lag-1 autocorrelation -0.14 to -0.80 (median
-0.5) in every hour including 00 UTC; lot days (few runs): sd $1.5-1.9, autocorrelation ~0. So the noise regime was
already on in hour 00 of 10-31, where region D was 0.24 (n 37), while hours 02-05 gave 0.88-0.93: the noise regime alone
does not make the fills follow Chainlink. Whether a configuration changed at the 10-31 01:00 restart is open (the stored
it9rs calldata has only salts; the order structure across that restart is for the next iteration).

**I9-5 (X91) candidate (b): the RTDS TWAP-60 topic (`code10/i95_twap.py`, `results/iter10_i95_twap.json`; 1,265
confirmed filled orders of 10-31 14:04-16:13).** Posture at the add, Chainlink vs TWAP-60: mo-money 500s 0.646 vs 0.608,
almach 0.771 vs 0.572, bosona 0.768 vs 0.589 (at the match 0.722 / 0.825 / 0.851 vs 0.58-0.61). The TWAP-60 topic is
nobody's input; it lowers every wallet. Candidates (a) the Binance relay (dz_rtdsbn, sealed so far), (c) the 15m mid and
(d) the complement's ask remain.

**M3 (X94) light form (`code10/m3_quick.py`, `results/iter10_m3_quick.json`; filled exact-500 orders, posture at the add;
selected on being filled, descriptive).** Off-posture filled 500s improved the touch when posted in 14.7% of mo-money's
(n 150) vs 2.9% of its on-posture ones and 5.4-6.4% of the other wallets' off-posture ones; at the touch 0.65 (mo-money
off) vs 0.82 (on); the off-posture fills sit at small edges (median |fair - mid| 0.03-0.09 vs 0.12 on-posture).
Mo-money's off-posture rungs step ahead of the book more often, which is the M3 direction; the survival test on unfilled
adds (11-01 full-depth book) is still needed.

**Pre-registration for the next exam claim: the quote unit (written 23:20 UTC 10-31; the fill-presence unit cannot pass,
oracle ceiling 0.80).** Unit (window, side s, second t) for every BTC 5m and 15m window (dx_clob) and, from 11-01 06:00,
the ETH / SOL / XRP / BNB / DOGE / HYPE 5m and 15m windows (dw_clob); label = an add of a schedule size (500 x 2^k, 250,
100, 62, 50, 12) at or above the touch of s in (t - 1 s, t] that is still at the touch at t; public features only (time
left, the Chainlink edge with the frozen sigma, the futures edge, book state excluding schedule-size levels, other
traders' prints, clock); activity-only baseline of the same model class; fit on the development blocks up to 11-02 00:00
UTC, choose on the later development blocks (aggregate). The 10-s fill presence on BTC 5m stays the reported primary
(0.716) until this unit has a VALIDATE value.

**Discovery (23:17 UTC): on the lot the Chainlink posture belongs to the 500-share rungs.** A quick split of the A1
region-D fills by the filled order's calldata original size: 500-share rungs follow Chainlink in region D 0.759 (STUDY, n
58) and **0.973 (VALIDATE aggregate, n 73)**, the live block's level; 62-share rungs 0.532 / 0.458 (n 47 / 48), 250-share
rungs 0.484 on VALIDATE (n 31). Frozen posture over all fills by class: 500s 0.613 / 0.742, 62s 0.509 / 0.650, 250s 0.549 /
0.654. The live block was 78% 500s (lot: 39-42% 500s, 19-35% 62s, 7-18% 250s), which is why it looked so strong. So the
A1 failure is a composition effect of rung classes, not (only) a regime: the 500 pass is the Chainlink-skewed rung; the
62/250 rungs follow another rule.

**Pre-registration R7-side (written 23:21 UTC, before code10/a1_class.py's per-class candidate table is read).** Side of a
fill by the class of the filled order (calldata original size): 500 x 2^k -> the frozen Chainlink posture (R6, unchanged);
62 / 250 / 125 / 100 / 12 -> the public candidate with the best STUDY accuracy among {cheaper side, market favourite (last
clean print), Binance posture (Binance S and strike, 1.4 x v300), Chainlink posture}; pairing class -> the under-held
outcome (own state, reported separately); other sizes -> the Chainlink posture. Confirmation on VALIDATE (aggregate):
the class-conditional public rule beats the frozen posture applied to all fills by >= +0.03, with the window-clustered
(2-h block) bootstrap lower bound > 0. If it passes it becomes R7's side component (the size class needs the calldata of
the fills, which evaluate() can fetch); it is then pre-registered for 11-01 06-12.

**R7-side test (pre-registered 23:21 UTC; `code10/r7_side.py`, `results/iter10_r7_side.json`; the same scored lot fills,
vectorised own imbalance).** Class mix of the scored fills: STUDY 500-class 41%, 62 34%, 250 8%, pairing 10%; VALIDATE
500-class 45%, 62 18%, 250 17%, pairing 13%. By UTC block (VALIDATE aggregate): 12-18 UTC 74% 500s, 18-24 53%, 00-06 22%
(62 32%, 250 25%), 06-12 3.5% (250 50%, 62 31%): the 500 rungs are the US-session ladder, the 62/250 rungs the off-session
ladder.
- **Region D by class (bought the Chainlink favourite, n, windows):** VALIDATE 500-class **0.973 (73 fills, 26 windows;
  window mean 0.974)**, 62s 0.458 (48, 25), 250s 0.484 (31, 15), pairing 0.444 (9); STUDY 500-class 0.759 (58, 11; window
  mean 0.694), 62s 0.532 (47, 17). Frozen posture over all fills by class: VALIDATE 500s 0.742, 62s 0.651, 250s 0.654,
  pairing 0.698, other 0.836; STUDY 500s 0.613, 62s 0.509, 250s 0.549.
- STUDY candidates for the off-session rungs: 62s cheaper 0.497 / favourite 0.503 / Binance posture 0.476 / Chainlink
  posture 0.509 (n 336): no public candidate; 250s favourite 0.634 (n 82); 100/12 favourite 0.735 (n 34). Chosen:
  62 -> Chainlink, 250 -> favourite, 100/12 -> favourite.
- **VALIDATE (aggregate): R7 public 0.660 vs the frozen posture 0.710, gain -0.049 (2-h block bootstrap [-0.085,
  -0.017]): the pre-registered R7-side FAILS** (the 250s' STUDY choice "favourite" scores 0.379 on VALIDATE; their
  cheaper side would be 0.62). With the pairing class on the under-held outcome (own state) 0.701. STUDY: 0.577 vs 0.567.
  Not adopted.
- Reading: the Chainlink posture is the side rule of the US-session 500 ladder, and it replicates on the historical
  VALIDATE in the sigma-free region at the live level (0.97 vs 0.965 live); the A1 "failure" on all fills is a
  composition effect of the off-session 62/250 ladder, whose side follows no public candidate (0.48-0.51 on STUDY, a coin
  flip against the reference): an unskewed two-sided ladder whose fill side the takers choose is the leading
  explanation (to be tested on the quote unit in an off-session development block, 11-01 06-12 is one).

## Iteration-10 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**;
  the frozen rule stays **R6** (no decision changed; the class-conditional side rule failed its pre-registered test).
- Paradigm: stability and composition of the decision. A calibrated historical match clock (taker signing ms + 620 ms,
  real Chainlink seconds from the 30-day endpoint) reproduces the live truth on 10-31 (region D 0.953 vs 0.965) and shows
  that the Chainlink posture is the side rule of the **US-session 500 ladder**: on the historical VALIDATE its 500-share
  rungs follow the report where it disagrees with the market 0.973 (26 windows), like live; the off-session 62/250 ladder
  (00-12 UTC) follows no public side candidate (0.46-0.53), which is why the posture looked unstable over all lot fills
  (0.66-0.68). The imbalance pairing bids are a separate order type (on the under-held outcome 100%, priced at the market,
  break-even), and the profit split between locked pairs and the directional residual changes sign between STUDY and
  VALIDATE.
- Rejected / not met: M5 cancel races (arrival posture 0.70-0.72 vs 0.74 at the match), M1's own-cost pairing price
  (2-5% within a tick), A4's and E2's profit signatures, I9-5's TWAP-60 input, M2's phase signature, the R7-side
  class-conditional rule (VALIDATE 0.660 vs 0.710).
- Data: pmxt archive verified (07-16..08-10 unaggregated books, same engine family in July: timestamp 0, salt counters at
  25-32 orders/s, 500/300/50 + pairing sizes); the shared recorder cannot label the quote unit (recall 0.01-0.02) but the
  own dx_clob can (recall 1.00) to 11-03 00:00; new recorder dw_clob (ETH/SOL/XRP/BNB/DOGE/HYPE 5m-15m) from 22:59 UTC;
  detached Chainlink fetch (52k stamps queued: the lot fills, switch-noise runs, BUILD, 15m; hard stop 11-01 10:00 UTC).
- Closed this iteration: X52, X68 (via X97), X88, X92, X93, X96, X97, X98, X100. Open: D3, X9, X24, X41, X57, X59, X61,
  X62, X64, X67, X71, X75, X76, X83, X87, X89, X90, X91, X94, X95, X99.

**Next steps (iteration 11; the next development block is 11-01 06:00-12:00 UTC, an off-session block).**
1. Off-session ladder (the undecoded side): on 11-01 06-12 with dx_clob / dw_clob and the 11-01 full-depth recorder
   (code8/delayed_rawrec.py, 05:55-12:00), test "unskewed two-sided ladder": are 62/250 rungs posted on both outcomes at
   symmetric distances from the mid, and does the fill side follow the taker flow (mint vs direct sell) rather than any
   reference? Then the per-fill side of the off-session ladder should be scored against a taker-flow baseline.
2. The 500 ladder: re-run R7-side with the 500-class posture only and the off-session classes scored separately (no
   transfer of STUDY choices); finish the lot fetch and report region D by class, day and wallet with window clustering;
   predict the size mode (500 vs 62/250) from public inputs (UTC/ET session, weekday, futures vol at the open) as the
   selector of the side rule.
3. Switch-noise test (X89 step 3) when the runs are fetched; the A3 clock observations on 11-01 18-24 and 11-02.
4. The quote unit as the target unit (pre-registered above): build it on dx_clob for 10-31 15:53-18:00 + 11-01 06-12.
5. pmxt (X87): reduce 3 h/day of 07-16..08-09 to per-market ladder events (bounded disk), the off-session ladder and the
   pairing bids at full depth; the replay (X64).

**Confirmation on a fresh development block: 10-31 00:00-06:00 UTC by rung class (`code10/a1_0006_class.py`,
`results/iter10_a1_0006_class.json`; calldata of all 1,178 cluster orders in the block's BTC 5m fill transactions fetched
this iteration; prediction written in the script before it ran: 500s >= 0.9 in region D, 62/250s ~0.5).** Region D
(Chainlink and the last clean print disagree on the favourite; report b - 4, block clock): **500-class 1.000 (41 fills, 10
windows)**, 62s 0.448 (58 fills, 6 windows), 100/12 0.25 (n 4). The block's hour 00 UTC was a 62-share hour (265 of 400
fills): its 62s bought the Chainlink favourite in region D 0.103 (n 29) while its 500s did 1.0 (n 6), which is the whole
"hour-00 anomaly" (0.24); hours 01-05 were 500-share hours (500s 1.0 in region D; 62s in hour 05 0.79, n 29). Prediction
met. The Chainlink posture is a property of the 500 ladder in every sample examined: live 10-31 12-18 (0.965), historical
VALIDATE (0.973, 26 windows), 10-31 00-06 (1.000, 10 windows); STUDY is weaker (0.759, 11 windows). The 62/250 ladder's
side rule is not decoded (0.10-0.79 by hour, 0.45-0.53 pooled).

**Skew of the fill price by class (`code10/skew_class.py`, `results/iter10_skew_class.json`): inconclusive.** The slope of
d = (bought token's last print - fill price) on e = (token's Chainlink fair - last print) is -0.10 / -0.03 for 500s and
-0.32 / -0.22 for 62s, -0.23 / -0.13 for 250s (STUDY / VALIDATE aggregate), but d and e share the last print with opposite
signs, so a stale print alone makes the slope negative: the fill-level test cannot measure the ladder's skew. The
"unskewed off-session ladder" stays a hypothesis for the quote-level test on 11-01 06-12.

**Per wallet, 500 ladder on the lot (`results/iter10_wallet_500.json`; same scored fills).** Region D (n, accuracy):
VALIDATE aggregate almach 14 / 1.000, bosona 16 / 1.000, **mo-money 43 / 0.953**; STUDY almach 28 / 0.643, bosona 18 /
0.944, mo-money 12 / 0.750. Frozen posture over all 500-class fills: VALIDATE almach 0.754, bosona 0.688, **mo-money
0.781**; STUDY 0.645 / 0.552 / 0.634. Mo-money's 500 deficit of the live block (0.735 vs 0.81-0.84) does not appear on the
historical VALIDATE (it is the best wallet there): X76 / X91 / X94 should treat it as a property of the 10-31 block (its
volatility bursts and the ad-hoc restarts), not as a fixed per-account parameter.

**Pre-registration H-VOL-500 (written 23:34 UTC before scoring).** The slow sigma restricted to the US-session 500 ladder
with the real Chainlink value on the calibrated match clock (the same scored lot fills as R7-side): candidate fixed in
advance v3600 x 1 (Binance 1-s realised vol over 3,600 s at b - 3) vs the frozen 1.4 x v300. Confirmation on VALIDATE
(aggregate) 500-class fills: gain >= +0.01 with the 2-h block bootstrap lower bound > 0. STUDY is reported alongside.

**H-VOL-500 result (`code10/hvol500.py`, `results/iter10_hvol500.json`): the slow sigma fails on the 500 ladder too.**
VALIDATE (aggregate) 500-class fills (n 1,633): frozen 1.4 x v300 **0.742** vs v3600 x 1 0.617, gain -0.125 (2-h block
bootstrap [-0.230, -0.034]); region A 0.731 vs 0.601; cheaper-side baseline 0.707. STUDY (n 403): 0.613 vs 0.633 (+0.020,
[-0.12, +0.15]). With the real reference and the right rung class, the historical evidence favours the frozen (fast) sigma,
as the 5m quote unit did in iteration 9; the live per-fill preference for the slow sigma was a property of 10-31's burst
fills. The frozen side rule stays.

**evaluate() smoke test with the new order-class diagnostic (`code10/smoke_r6_it10.py`,
`results/iter10_eval_r6_1793461200_1793464800.json`; development hour 10-31 15:00-16:00, FETCH_CL off, 2 rotation draws).**
Runs end to end; `side_posture_match_clock`: 0.844 per fill (n 1,104, Chainlink coverage 1.0, 1,086 transactions fetched);
`it10_by_order_class`: 500-class posture 0.855, region D 0.888 (n 267); 62/250-class posture 0.429 (n 28), region D 0.167
(n 12); other sizes 0.855 / 0.923 (n 165 / 39). The off-session classes go against Chainlink in this hour, as the 62s did
in hour 00 of 10-31 (0.10), while on the historical VALIDATE they are a coin flip (0.46-0.48).

**Are 62/250 rungs the far side of the 500 posture ladder? (`code10/opp_side.py`, `results/iter10_opp_side.json`; all lot
fills with calldata sizes; nearest same-wallet 500-class fill in the same window within +-30 s).** Control: a 500 fill's
nearest other 500 fill is on the opposite outcome only 3.7% (STUDY, 2,359 pairs) / 4.5% (VALIDATE aggregate, 9,236): the
posture ladder holds one side. 62/250 fills next to a 500 fill: 15% opposite on STUDY (only 20 pairs, 22 windows with both
classes) but **71% opposite on VALIDATE (163 pairs, 116 windows)**. Where the two classes coexist, the 62/250 rungs are
mostly the other outcome's rungs of the same ladder (which is why they go against Chainlink on 10-31 15-16, 0.17, and in
hour 00, 0.10); in the off-session windows without 500s their side is still undecoded.

**500 ladder by day (`results/iter10_500_by_day.json`; [region D n, region D accuracy, posture over 500 fills]).** VALIDATE
(aggregate per day): 10-27 [17, 1.000, 0.827], 10-28 [25, 0.920, 0.648], 10-29 [11, 1.000, 0.691], 10-30 [20, 1.000,
0.843]; STUDY: 10-23 [49, 0.735, 0.607], 10-24 and 10-25 no 500-class region-D fills (weekend: few 500s), 10-26 [9, 0.889,
0.584]. The 500 ladder follows Chainlink in region D on every VALIDATE day; the weak 500 day is Friday 10-23 (the day of
the 20:40 UTC switch-off), where 49 of STUDY's 58 region-D 500 fills sit.

**I9-3 (X89) step 3 result: Chainlink data quality before the switch-offs (`code10/i93_switch_noise.py`,
`results/iter10_i93_switch_noise.json`; six 30-s runs of consecutive endpoint seconds in the 2 h before each switch and at
the same clock times 3 and 4 days earlier; 104 runs).** Calendar switches (Fri-Sun evenings ET): sd of 1-s changes
$0.34 / 1.36 / 1.88 / 2.29 / 1.30 before 10-17 20:35, 10-17 22:30, 10-18 22:15, 10-23 20:40, 10-24 22:30 vs controls
$1.0-2.0; lag-1 autocorrelation -0.13..+0.44 vs -0.05..+0.29; Chainlink - Binance basis sd within a run 0.6-3.1 vs 1.4-3.2:
**no data-quality excursion before the calendar switches**. The ad-hoc 10-31 16:53 switch: sd **$9.29**, autocorrelation
**-0.51**, basis sd 6.8 and basis -$134 vs controls $2.0-2.6, ~0, 2.3-3.2 and -$112..-125: it happened inside the Chainlink
noise regime, which had been on since at least 10-31 00:00 (all hours of 00-04 noisy), i.e. after hours of the regime and
the block's losses, not minutes after an excursion. Reading: calendar switches are a schedule; the ad-hoc one is a
reaction to the noise regime (or to its losses). Signature partly met; the full-history zone test (DST) stays open.

**Recorders and jobs at the end of iteration 10 (23:46 UTC):** shared live.py running; own examrec (dx_*, to 11-03 00:00),
dy_rtds, dz_rtdsbn running; the delayed full-depth recorder for 11-01 05:55-12:00 still scheduled; new famrec (dw_clob,
pid 31812 launcher / 10824 worker, 4.6 MB at 23:38, to 11-03 00:00); detached Chainlink fetch code10/fetch_cl_hist.py
(pid 32528 launcher; queue `.cache/re/directional-maker/a1_queue10.parquet`: switch runs done, then the lot BTC 5m fill
stamps (random order), BUILD BTC 5m, BTC 15m; hard stop 11-01 10:00 UTC; chunks `cl/cl_hist10_<start>_*.parquet`). The
reduced pmxt hour (36 MB) is in `.cache/re/directional-maker/pmxt/`. Iteration 10 ends at ~00:10 UTC.

**Window-bootstrap intervals for region D by class (`results/iter10_classD_ci.json`; 23:47 UTC, the fetched subsample has
grown).** VALIDATE (aggregate): 500-class **0.933 (89 fills, 30 windows; 95% window bootstrap [0.837, 1.000])**, 62s 0.443
(70, 30; [0.25, 0.64]), 250s 0.515 (33, 16; [0.26, 0.84]); STUDY 500s 0.770 (61, 13; [0.63, 0.97]), 62s 0.549 (51, 18;
[0.34, 0.80]). The 500-vs-62 contrast on VALIDATE is outside both intervals. These are the numbers to quote; the earlier
0.973 (73 fills) was the smaller subsample.

**X61 (strike publication lag) scheduled; an endpoint fact.** `code10/strike_poll.py` (pid 30244 launcher, sleeping) polls,
for every BTC 5m and 15m window starting in the development hour 11-01 06:00-07:00 UTC, Gamma priceToBeat and the
crypto-price openPrice once per second from S - 15 s to S + 20 s, and writes the first-availability times to
`.cache/re/directional-maker/strike_poll_1793512800.jsonl` (hard stop 07:00; skips sealed windows). While choosing the 15m
variant name (development time 10-31 12:00 UTC): `variant=fiveminute` and `variant=fifteen` return the Chainlink value
stamped S (77490.7058...), while `fifteenminute` / `fifteen_minute` return a cents-rounded 77618.97, about $128 higher: the
size of the Chainlink - Binance BTCUSDT basis that day, i.e. probably a Binance-based price. Which one the 15m strike uses
must be checked against Gamma priceToBeat (the RE's 15m code takes the Gamma value, so R6 is unaffected).

Check (23:50 UTC): Gamma priceToBeat of the 10-31 12:00 windows is 77504.787 for both BTC 5m and BTC 15m (the Chainlink
TWAP of [S - 61, S - 2], full precision), not the cents-rounded `fifteenminute` value (77618.97): the 15m strike is the
Chainlink stream, as R6 assumes.

**Off-session rungs in windows without 500s (`results/iter10_offsession_side.json`; scored lot fills with a nonzero own
imbalance).** 62s (STUDY n 256 / VALIDATE n 581): under-held outcome 0.41 / 0.49, cheaper 0.50 / 0.57, Chainlink posture
0.43 / 0.58, Binance posture 0.40 / 0.59. **250s (n 49 / 586): on the already-held outcome 0.90 / 0.68** (under-held 0.10 /
0.32), Chainlink 0.55 / 0.65, cheaper 0.31 / 0.65. 62s in windows that also have 500s: under-held 0.97 (n 32, VALIDATE).
So the off-session 250 rungs keep buying the outcome the wallet already holds (own state: a within-window momentum of its
own inventory, like the "side of the previous event" baseline of iteration 9), the 62s next to a 500 ladder complete pairs,
and the pure off-session 62s follow nothing measured (0.41-0.59). Own-state descriptions only; the first side of an
off-session window is not decoded.

**The entry side of each window (`results/iter10_first_fill.json`; scored lot fills where the wallet holds nothing in the
window yet).** Chainlink posture / Binance posture / cheaper / favourite: off-session 62/250 first fills (no 500 in the
window) **0.661 / 0.618 / 0.550 / 0.454 (STUDY, n 251)** and **0.719 / 0.660 / 0.609 / 0.402 (VALIDATE aggregate, n 473)**;
500 first fills 0.675 / 0.669 / 0.497 / 0.528 and 0.753 / 0.691 / 0.676 / 0.315; all first fills 0.664 and 0.734. So the
off-session ladder ENTERS on the Chainlink posture side about as often as the 500 ladder does (0.66-0.72), and its later
fills drift away from the posture because its 250 rungs keep adding to the held outcome (0.68-0.90). Reading for
iteration 11: one posture decides the entry in both ladders; the off-session ladder then follows its own inventory
(momentum), while the 500 ladder keeps re-pricing on every Chainlink report. To test on the quote unit (11-01 06-12).

- Checkpoint addendum (23:52 UTC): the late findings change next step 1. The off-session ladder is better described as
  "enter on the Chainlink posture side (first fills 0.66-0.72), then keep adding to the held outcome (250s 0.68-0.90, own
  state)" than as an unskewed two-sided ladder; on 11-01 06-12 test both on the quote unit (are the off-session rungs
  re-priced on each Chainlink report, or left on the entry side?). Final 500-ladder number: VALIDATE region D 0.933 (30
  windows, [0.84, 1.00]); 10-31 00-06 1.000 (10 windows). Open catalog items: D3, X9, X24, X41, X57, X59, X61 (poller
  scheduled), X62, X64, X67, X71, X75, X76, X83, X87, X89, X90 (fetch running), X91, X94, X95, X99. Iteration 10 ends
  ~23:53 UTC (about 80 minutes).

**Entry side on 10-31 00-06 with sigma-free rules only (`code10/entry_0006.py`, `results/iter10_entry_0006.json`):
inconclusive for the posture.** Without the Binance 1-s vol for that block only sigma-free rules were scored: entries
(first block second of each wallet-window, n 295) bought the Chainlink favourite 0.45, the market favourite 0.39, the
cheaper side 0.61; later fills 0.33 / 0.31 / 0.69. The block was an underdog-buying block (and lost 10% on maker fills);
the sigma-free favourite rule is not the posture outside region D, so the entry-follows-posture reading (lot: 0.66-0.75)
still needs the posture with sigma on this block (fetch the 1-s klines next iteration).

**Frozen posture on the fresh 10-31 00-06 block by class (`results/iter10_entry_0006_posture.json`; block clock, report
b - 4, Binance 1-s v300 from the REST klines, Gamma strike; 1,234 fills).** All fills 0.664; **500-class 0.799 at the entry
(n 278) and 0.784 later (n 399)**, i.e. the live block's 0.785; 62/250 later fills 0.444 (n 338; only 2 entries, the
windows were entered with 500s); other sizes 0.60. On a block never used for a choice, the 500 ladder follows the frozen
posture at the live level, and the 62/250 rungs go against it, as on 10-31 15-16 and in hour 00.

### Iteration 11 (2026-11-01, local Windows laptop, started 00:19:55 UTC; 666 of 1,200 budget minutes used before it)

Read first: BRIEF, NOTES (iteration 10 in full), state.json, FINAL_RULE.md, EXAM_r1.md (backtest section),
panels/iter10_{information,mechanics,assumptions}.md. Calendar (`tools/sealed.py directional-maker`, 00:21 UTC): released
h1, h2; development [10-23, 10-31 06:00) and [10-31 12:00, 18:00); the current block 11-01 00-06 is sealed; the next
development block (11-01 06-12) starts after this iteration, so again no new live development data. Shared live.py
running (status 00:21 UTC: clob_crypto 123 reconnects, last error 1013 slow consumer at 17:15; rtds connected). Panel
proposals added as catalog items: information I10-1..I10-5 = X101-X105, mechanics P1-P4 = X106-X109, assumptions P1-P4
= X110-X113.

**PIVOT (required: progress flat at 0.803 for three iterations).** New paradigm: **the window is the unit of decision
and the model class is an executable state machine.** Instead of predicting fills per 10-s bin or per print, replay a
one-sided posture ladder second by second against the public taker tape under the examiner's strict-fill conventions
(trade-through only, latency 2 s, match slack 2), and score it on what the money and the outcome bar are made of: the
window's terminal net position (side and size) and its realized per-window PnL (mechanics P1 = X106, P4 = X109; D3 /
X64). Earlier iterations scored the outcome only through an expectation proxy (sum of P(fill) x payout per bin,
0.26-0.33) or the examiner's two-sided R2 replay (0.20 / 0.21).

**Competing explanations (iteration 11) and the observation that separates them**
1. E1 posture-ladder accumulation: the window PnL is the residual of a one-sided ladder on the Chainlink/Binance
   posture side; its size is the taker flow that sells the posture token through the ladder, times the rung class.
   Separates: a strict replay of a one-sided posture ladder reproduces the window PnL (corr >= 0.4) and the net side
   (>= 0.8 in one-sided windows); a two-sided replay does worse.
2. E2 taker-chosen two-sided ladder (information C2 / assumptions critique 1): the off-session ladder is two-sided and
   unskewed; the window PnL is the counterparties' imbalance. Separates: off-session, a two-sided replay matches the
   cluster's window PnL and net side better than the one-sided posture replay; in the US session the reverse.
3. E3 Binance pick-off (assumptions P1): off-session fills are latency takers after futures moves. Separates: replay
   with a pick-off side (loser of the last futures move) beats the posture replay off-session. (Mechanics panel already
   found no ms peak on 10-26: 0.43-0.58; information C3 no trigger spike.)
4. E4 regime-signed residual (assumptions P2): something at 10-27 ~12:00 turned the residual from the winner to the
   loser. Separates: if a public posture replay shows the same sign flip of corr(net, outcome) between STUDY and
   VALIDATE, the flip is in the market (the posture itself became adversely selected), not in the engine.
5. E5 size configuration (mechanics P2 / assumptions P4): rung class (62/250/500) is a central config that sets the
   window PnL magnitude. Separates: replay PnL corr with a public session size (500 in the weekday 12-21 UTC session,
   62 outside) vs unit size; the residual oracle ceilings (0.43 / 0.59 side only, 0.55 / 0.62 side + size).
6. E6 (unlikely) reward farming: quotes sized >= 50 within 4.5 c of the mid for liquidity rewards, the directional
   residual is a by-product. Separates: REWARD rows are 1 in the lot activity of almach (1 row in 8 days), so reward
   income cannot carry a +3-6% maker return on $0.7M; kept only as a footnote.
7. E7 (unlikely) the window PnL is set by queue priority alone: the cluster earns because it is first at the touch,
   and any side rule with first-in-queue fills would match its PnL. Separates: an at-touch (first-in-queue) replay
   with a random or cheaper-side rule matches the cluster's PnL as well as the posture replay.

**Pre-registration R7-price (written 00:43 UTC 11-01, before any in-block number is read; information panel I10-1 =
X101, price part).** Recording-free match clock for the price: the anchor of a cluster maker BUY fill is the last clean
print of its market before the fill's transaction in on-chain execution order (same block: lower position in
eth_getBlockByNumber's transaction list; otherwise the last clean print stamped before the block second, R3's anchor);
the price of a clean transaction with several rows is the taker's worst price in it (max for a taker BUY, min for a
taker SELL, token-mapped); predicted limit = anchor - 0.01 on the fill's token, on the dynamic tick. Sample: seed 1101,
3,000 VALIDATE and 1,500 STUDY fills (code11/inblock_fetch.py). Adopted as R7's price component if, on the VALIDATE
sample, within-a-tick >= the block clock + 0.03 and the 2-h block bootstrap lower bound of the gain > 0. Reported with the
trivial anchors on the same clock ('last print' with no offset, block clock 'last print - 0.01').

**Disk note (00:58 UTC).** `resources.py` reports free disk 1.86 GB (14.1 GB at 00:31); not this workspace
(.cache/re/directional-maker/ 1.3 GB, unchanged; it11/ ~60 MB). No large download was started after that.

**P1 = X106 / D3 / X64: the strict-fill window replay (`code11/replay.py`, `code11/replay_score.py`, `code11/replay_keys.py`;
results `iter11_replay.json`, `iter11_replay_keys.json`).** 2,291 lot BTC 5m windows (1,152 STUDY, 1,139 VALIDATE), 240
configurations each: side rule (posture = Binance stand-in digital with 1.4 x v300 vs the last clean print; two-sided;
cheaper; favourite; pick-off = the outcome the last Binance second moved against), delta {0, 0.01}, latency {2, 0} s, flow
{all taker prints except the cluster's own taker orders, clean prints only}, size per second {1, 100, 500, session
500/62}, trade-through or at-touch. Cluster PnL = its maker BUY fills held to resolution; windows with >= 1 cluster maker
fill: 583 STUDY / 1,089 VALIDATE; one-sided (>= 70% of shares on one outcome) 406 / 584.
- STUDY choice (pre-registered criterion, strict L = 2): **favourite, delta 0, session size, all prints: per-window PnL
  corr 0.286 / 0.174 (Pearson / Spearman), net side 0.618**; best posture candidate 0.030 / 0.086 (net side 0.414);
  two-sided 0.133 / 0.129; pick-off 0.110 / 0.096; cheaper -0.207 / -0.132.
- **VALIDATE (aggregate): the STUDY choice reverses: -0.103 / -0.082, net side 0.354** (h1 -0.018, h2 -0.155; per wallet
  -0.07..-0.12). At the same parameters the other rules give posture 0.219 / 0.223 (net side 0.673), pick-off 0.170 /
  0.172 (0.699), cheaper 0.153 / 0.138 (0.687), two-sided 0.112 / 0.132 (0.682). Latency 0 vs 2 s, at-touch vs
  trade-through, the flow and the size change these by <= 0.03.
- **Ceiling (`code11/replay_oracle.py`, `iter11_replay_oracle.json`): with an ORACLE side (the cluster's own terminal net
  side, quoted all window) the same strict replay reaches only 0.48-0.51 / 0.62-0.64 on STUDY and 0.46-0.47 / 0.52-0.53 on
  VALIDATE.** Under the examiner's strict-fill conventions (trade-through, latency 2 s, slack 2) the outcome bar (>= 0.5
  in both) sits at the ceiling of a perfect window side; the decoded side rules reach 0.22-0.25. The fills that make the
  cluster's window PnL are touch fills of fresh quotes (posted ~0.1-1 s before the match), which a trade-through replay
  on block-stamped prints cannot be credited with; its fills are trade-throughs, i.e. adverse moves (every strict replay
  loses 5-21% on notional).
- E4 per window: corr(net, outcome) of the cluster is +0.11..+0.21 on every STUDY day and -0.15..-0.39 on every VALIDATE
  day (Spearman); the favourite replay's is +0.50..+0.63 on every day. So the window net side of the cluster moves from
  the favourite to the underdog between the halves, while a fixed public side rule does not.

**P4 = X109: window net side against fill-free window rules (`code11/window_side.py`, `iter11_window_side.json`).**
One-sided windows: time-weighted posture majority (Binance stand-in) vs the cluster's net side **0.434 STUDY / 0.627
VALIDATE**; posture at the first quoting second 0.574 / 0.574; the cluster's first fill side = its net side 0.902 / 0.807.
The posture majority side wins only 0.295 / 0.279 of windows (1.4 x v300 makes the digital less extreme than the market:
an underdog-leaning rule), while the cluster's net side won 0.616 (STUDY) and 0.325 (VALIDATE). Per day the net side won
0.58-0.73 on 10-23..26 and 0.18-0.39 on 10-27..30. The window side bar (>= 0.80) is not met by any fill-free public rule
(best 0.63 on VALIDATE).

**E2 / E4 / X111: how the fills are matched (`code11/fill_type.py`, `iter11_fill_type.json`; `iter11_fav_by_block.json`).**
Complement mints (the taker buys the other outcome) are 81% of STUDY and 88% of VALIDATE maker fills. The bought token is
the favourite (fill price > 0.5) in 49% of STUDY mints / 63% of direct fills and in 30% / 42% on VALIDATE. Per day the
favourite share falls 0.59, 0.56, 0.53, 0.45 (10-23..26), 0.36, 0.37, 0.29, 0.25 (10-27..30); per 6-h block it ranges
0.37-0.76 on STUDY and 0.20-0.59 on VALIDATE (10-28 18-24: 0.59). It is a noisy drift with a large step around 10-26
12:00 (0.37) and 10-27 12:00 (0.22), not one clean break. Realised vol did not fall (v300 median at the fills 2.5-4.1e-5
on STUDY days, 2.9-6.0e-5 on VALIDATE days, highest on 10-30) and DVOL stayed 37-40: a constant-sigma engine against a
falling realised vol does not explain the drift (it would buy favourites on high-vol days, the cluster bought the most
underdogs on 10-29/30). The returns stay positive in most blocks either way (fills on the underdog win 31-45% at prices
below that). Reading: the side of the fills follows the takers' demand (mints of the outcome they buy) more than any
reference; the drift is in what the takers buy. Not decoded further this iteration.

**X110 (assumptions P1, the Binance pick-off) through the replay:** the pick-off side rule (the outcome the last Binance
second moved against) gives window net side 0.44-0.53 STUDY / 0.68-0.70 VALIDATE and PnL corr 0.10-0.20 / 0.10-0.19,
no better than the posture or the two-sided ladder (0.67-0.71 / 0.11-0.25 on VALIDATE); the mechanics panel's match-clock
test found no ms peak (0.43-0.58 on 10-26) and the information panel no trigger spike. Tried; no pick-off mechanism
beyond what any strict replay picks up from adverse moves.

**Pre-registration H11-SIDE-INBLOCK (written 01:06 UTC, before it is scored).** The per-fill posture on the lot (frozen
sigma 1.4 x v300, the real Chainlink value stamped floor((T_hat - 1,432 ms) / 1 s) where the detached fetch has it,
Gamma strike) with the market mid taken from the in-block anchor (the last clean trade before the fill in execution
order, the R7-price clock) instead of the last clean print at b - 3. Adopted as the historical side clock if, on VALIDATE
(aggregate), the per-fill accuracy is >= the b - 3 version + 0.02 with the 2-h block bootstrap lower bound of the gain
> 0. Region D is reported for both. (This is a measurement clock for the side, like the live book mid at the match.)

**R7-price on every lot fill and in evaluate() (`code11/inblock_fetch_all.py`, `inblock_score.py all`, `inblock15.py`;
`results/iter11_inblock_price_all.json`, `iter11_inblock_price_15m.json`).** 14,301 blocks (BTC 5m) + 1,932 (15m) fetched with
`eth_getBlockByNumber(block, false)`, 0 failures; the fill transaction's position found for 99.97%. **All 27,988 VALIDATE
BTC 5m maker fills: in-block 0.8065 vs block clock 0.7091 (gain +0.0975, 2-h block bootstrap [+0.084, +0.111]); per wallet
almach 0.805, bosona 0.800, mo-money 0.814; halves 0.806 / 0.807; exact 0.454; trivial 'last print' with no offset 0.773.**
STUDY 0.751 vs 0.617. BTC 15m: VALIDATE 0.766 vs 0.666 (2,996 fills), STUDY 0.730 vs 0.656. **Pooled VALIDATE 0.803
(block 0.705).** Adopted (pre-registered criterion met) as R7's price component: `code/inblock_price.py`, wired into
`evaluate()` (`price_inblock`, `price_r7` = match clock where the shared recorder has the trade else in-block,
`union_btc5m_15m.price_within_0.01_r7`). Smoke tests: live development hour 10-31 15:40-16:40 block 0.625 / in-block 0.719
/ match clock 0.849 / R7 0.843 (5m), union R7 0.823; historical VALIDATE hour 10-29 12-13 (no recordings) block 0.649 /
in-block 0.825 (680 fills), union 0.811. On busy live hours the in-block order recovers only part of the match-clock gain
(0.72 vs 0.85): R7 uses the match clock wherever it exists.

**H11-SIDE-INBLOCK result (`code11/side_inblock.py`, `iter11_side_inblock.json`): not adopted.** VALIDATE (16,387 fills with
the real Chainlink value now fetched, 59% of the lot's VALIDATE fills): posture with the b - 3 mid 0.691, with the in-block
mid 0.698 (gain +0.007, [-0.008, +0.021]); region D 0.62 (759) vs 0.58 (1,048). STUDY 0.58 / 0.58. The side gap is not a
clock artefact of the mid.

**Fast-clock window replay (`code11/replay_fast.py`, `iter11_replay_fast.json`; exploratory: execution order, latency ~0,
strict trade-through).** Posture: STUDY 0.093-0.098 / 0.18-0.19, **VALIDATE 0.18-0.23 / 0.24-0.26, return -0.9% / +0.8%**
(the 2-s replay loses 16%); two-sided 0.32-0.48 / 0.22-0.32 STUDY, 0.15-0.20 / 0.12-0.22 VALIDATE; **oracle side 0.50-0.54 /
0.64-0.65 STUDY, 0.46-0.49 / 0.52-0.53 VALIDATE.** Speed removes the adverse selection of the replay's fills (its return goes
from -16% to about zero) but not the gap to the outcome bar, which is the window side: with the cluster's own net side the
correlation is ~0.5 on either clock, with the posture ~0.2.

**X102 queued (`code11/queue_x102.py`, `code11/fetch_cl_x102.py`).** 26,352 crypto-price requests (pre-registered sample:
consecutive window pairs i = 0, 16, ..., 272 of every lot day, every even second of [S - 65, S + 300); each request also
returns tau + 300, which covers window i+1). The fetcher waits for the iteration-10 job (`cl_fetch10_status.json`, done
10,440 of 46,610 at 01:04 UTC, ~1.5 requests/s) to finish, then runs at the same polite rate; hard stop 11-01 22:00 UTC;
status `.cache/re/directional-maker/cl_fetch11_status.json`, chunks `cl/cl_hist11_*`.

## Iteration-11 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**. The
  frozen rule is now **R7 = R6 + the in-block execution-order price clock** (one decision changed, pre-registered).
- Paradigm (pivot): the window as the unit of decision with an executable state machine (strict-fill replay of the quote),
  plus a new data source for the price clock (the on-chain transaction order inside each block).
- target_metrics changes: price_within_tick 0.705 (block clock) -> **0.803** (in-block, pooled 5m + 15m, all VALIDATE fills;
  bar 0.80); pnl_corr now reports the target's own definition, the strict-fill replay of the frozen quote: **0.207 / 0.218**
  (it reported the expectation proxy 0.260 / 0.327 before); oracle-side ceiling 0.47 / 0.53 (fast clock 0.49 / 0.53).
- Closed: X106, X109, X110, D3, X64. Partial (open): X101 (price done; recorder successors and side/selection parts open),
  X104, X111, X112. Not run: X102 (queued), X103, X105, X107, X108, X113.
- What the pivot showed: (1) the outcome bar is side-bound and sits at the ceiling of a perfect window side under strict
  fills; (2) speed explains why the cluster earns where a 2-s copy loses (return -16% -> ~0% when the clock is the
  execution order), not which side it ends on; (3) the cluster's net side is set by its first fill (0.81-0.90) and drifted
  from the favourite to the underdog across the lot while 81-88% of its fills are complementary mints.

**Next steps (iteration 12; the next development block 11-01 06-12 UTC ends at 12:00).**
1. 11-01 06-12 (off-session, development): X103 (re-post race of the 62/250 ladder, full-depth recorder 05:55-12:00), the
   pre-registered quote-unit and per-phase checks, P1's pre-entry quote (is the entry side a quote decision?), X61 strike
   poll results (06:00-07:00).
2. Recorder continuity before 11-03 00:00 (X101 step 3): successor instances of dx_clob, dw_clob, dy_rtds (add
   xrp/bnb/doge/hype to KEEP) and dz_rtdsbn with hard stops at the end of the budget plus the exam.
3. X102 print-level selection with the endpoint Chainlink once `cl_fetch11` has run (pre-register the model first).
4. The window side: what predicts the first fill's side beyond the posture (0.57 fill-free; 0.66-0.75 at the fill with the
   real Chainlink), e.g. the taker population (X104) and the favourite-share drift (X111).
5. X107 / X113 (size configuration epochs, change points across wallets), X108 (same-pass salt adjacency).

**X108 (mechanics P3): same-pass salt adjacency (`code11/salt_pass.py`, `iter11_salt_pass.json`).** Filled maker BUY orders
of one wallet in one market with 0 < delta salt <= 40 (~3 s of signing; daily counter epochs from the 01:00 restart): on
the other outcome 0.08-0.10 (STUDY, 170 pairs) / **0.103 (VALIDATE, 880 pairs) vs a within-(wallet, market) permutation
null of 0.48 [0.45, 0.51]**; off-session 0.113 vs 0.492, session 0.096 vs 0.472; 62/250 rungs 0.123 vs 0.505, 500 rungs
0.094 vs 0.439. The off-session 62/250 ladder looks exactly like the one-sided 500 ladder on this statistic. Caveat: filled
rungs live ~0.5-1.5 s, so a filled pair close in salt is also a pair of fills close in time, and one-sided taker bursts
produce the same pattern; the test cannot by itself separate one-sided passes from taker-chosen sides (the quote-level test
on 11-01 06-12 can).

**Market-only taker-flow baseline for the entry side (`code11/entry_flow.py`, `iter11_entry_flow.json`; X104 step 3).** The
cluster's first maker fill of a window is on the outcome the clean-tape takers were NOT net-buying over the previous 10 /
30 / 60 s (strictly earlier block seconds): **0.600 / 0.616 / 0.659 (STUDY), 0.581 / 0.607 / 0.607 (VALIDATE)**; net side in
one-sided windows 0.57-0.62 / 0.52-0.59. Unlike the favourite rule it does not flip between the halves (the mints make the
cluster the complement of the takers' demand). The real-Chainlink posture at the entry fill (0.66 STUDY / 0.72 VALIDATE,
iteration 10) beats this market-only baseline by +0.05 / +0.11 on the entry; neither reaches 0.80.

**Entry side: posture and taker-flow complement together (`code11/entry_combo.py`, `iter11_entry_combo.json`;
exploratory, NOT pre-registered).** The window's first cluster maker fill with the real Chainlink value (VALIDATE 679 of
1,089 windows, STUDY 373 of 583): posture (T_hat - 1,432 ms, frozen sigma, last clean print at b - 3) **0.744 VALIDATE** /
0.611 STUDY; taker-flow complement (30 s) 0.592 / 0.593; they agree in 53% / 54% of windows, and **where they agree the
entry is on that side 0.817 (VALIDATE) / 0.690 (STUDY)**; where they disagree the posture is right 0.661 / 0.520.

**Pre-registration H12-ENTRY (written 01:12 UTC 11-01, for the development block 11-01 06:00-12:00 UTC, before any of
it exists).** Unit: each BTC 5m and 15m window with >= 1 cluster maker BUY fill; label = the outcome of the window's first
cluster maker fill (match clock from the shared recorder, else the in-block order). Predictors (frozen): P = the Chainlink
posture at the fill (live report stamped T - 1.432 s, Gamma strike, 1.4 x v300, Polymarket mid of the last clean trade
before the fill); Q = the complement of the net clean taker demand over the previous 30 s. Report P, Q, the agreement share
and the accuracy where they agree, per family and wallet. Prediction from the lot: P 0.70-0.78, agreement ~0.5, agreeing
windows >= 0.78. If the agreeing-window accuracy is >= 0.78 there and on the next development block, the window side
becomes "P where P and Q agree" with its coverage stated (a subset rule: reported, never counted toward the target).

**R7-price pooled per wallet and half (`code11/inblock15_wallet.py`, `iter11_inblock_pooled.json`).** VALIDATE BTC 5m + 15m,
30,984 maker fills: **0.8026; per wallet almach 0.800, bosona 0.797, mo-money 0.811; halves 0.804 / 0.801**; BTC 15m alone
per wallet 0.752 / 0.763 / 0.784, halves 0.784 / 0.757. The price bar (>= 0.80, every wallet and half within 3 points)
holds on VALIDATE, with the proviso that the rule is the trivial anchor "last print minus a tick" on this clock ("last
print" alone 0.773 on 5m).

**Checkpoint addendum (01:14 UTC).** Late results after the checkpoint above: X108 salt adjacency (one-outcome passes for
500 and 62/250 alike, 0.09-0.12 vs null 0.44-0.51, confounded with taker bursts); the market-only taker-flow complement
for the entry (0.58-0.66, stable across halves); the entry combo (0.82 on VALIDATE where posture and flow agree, 53% of
windows; exploratory, pre-registered as H12-ENTRY for 11-01 06-12); R7-price pooled per wallet 0.797-0.811 and halves
0.801-0.804. state.json updated by `code11/update_state11.py` (catalog X101-X113 added; D3, X64, X106, X108, X109, X110
closed; target_metrics price 0.8026 (in-block, pooled), pnl 0.2066 / 0.2181 (strict replay, the target's definition)).
The X102 fetch (`code11/fetch_cl_x102.py`) is waiting for the iteration-10 fetch to finish. Not yet in evaluate(): the
recording-free side path (taker sign_ms from the fill calldata -> T_hat, endpoint Chainlink, Gamma strike) for blocks
without recordings (X101 side part); next iteration.

**X111 / X104: who takes from the cluster, and did the market or the quote move? (`code11/takers_drift.py`,
`code11/market_demand.py`, `code11/k_by_day.py`; results `iter11_takers_drift.json`, `iter11_market_demand.json`,
`iter11_k_by_day.json`).**
- Takers are dispersed: 4,396 distinct takers on VALIDATE, top-10 12.6% of the fills, top-50 28.9%. 58% of VALIDATE fills
  come from takers already seen on STUDY, and **the same takers' fills moved from the favourite 0.517 (STUDY) to 0.319
  (VALIDATE)**; new takers 0.303. Excluding VALIDATE's top-10 takers changes no day by more than 0.02 (0.586 -> 0.255).
  All signature types moved (0.45-0.55 -> 0.27-0.35). Not a new taker population (assumptions P2 (a) rejected).
- The market's own taker demand did not move: on clean prints the favourite share of taker BUY shares is 0.46-0.51 on
  every lot day. In the cluster's transactions the takers' buys were on the favourite 0.28-0.34 on 10-23..25 and
  0.40-0.49 on 10-26..30 (with mints the cluster buys the complement). So the change is in which outcome the cluster's
  bids sat on at the touch: its own quote decision.
- **The posture's sigma multiplier is not stable over the lot (version-like step).** Per-fill posture with the real
  Chainlink value (T_hat - 1,432 ms; 59-67% of fills fetched), sigma = k x v300, k grid 0.5-2.5: best k per day 0.5 (10-23),
  0.85 (10-24), 0.5 (10-25), 1.2 (10-26), 2.0 (10-27), 1.4 (10-28), 2.0 (10-29), 2.0 (10-30); per 6-h block 0.5-1.2 up to
  10-26 06:00 and 1.4-2.5 from 10-26 12:00 on (exceptions 10-27 00: 1.0, 10-28 18: 0.85). At k = 1.4 (frozen) the days
  score 0.52 / 0.62 / 0.54 / 0.60 (STUDY) and 0.65 / 0.68 / 0.68 / 0.74 (VALIDATE); at k = 0.85 STUDY 0.54-0.73 and VALIDATE
  0.40-0.60. Implied engine sigma k x v300 ~ 1.3-2.3e-5 per sqrt(s) on 10-23..25 (annualised ~7-13%) vs 4.3-12e-5 on
  10-26..30, while DVOL stayed 37-40 and v300 rose only ~1.5x: neither a constant sigma, nor realised vol, nor DVOL x c fits
  both halves. The favourite share of the fills tracks the step (0.60 -> 0.24). Reading: the engine's volatility input or
  multiplier changed around 10-26 06-12 UTC (Monday; the weekly sweep/restart is 01:00 UTC; the ad-hoc restarts were
  later, ~19:39 UTC), which is the STUDY/VALIDATE side break and the residual's winner-to-loser flip. No rule is chosen from
  this (it is fitted per day); pre-registered for 11-01 06-12: report the per-fill posture at k = 1.4 (frozen) and k = 2.0
  side by side, per wallet, and the best k on the grid.

**The market did not change its vol; the engine did (`code11/market_k.py`, `iter11_market_k.json`).** The market-implied
multiplier k_m (sigma implied by each clean BTC 5m print as a digital on Binance S and the Binance TWAP strike, over v300)
has a median of 0.97-1.35 in every 6-h block of the lot (~1.15), with no step; Spearman with the cluster's best k across 28
blocks -0.28. So before ~10-26 06-12 UTC the engine priced the digital with LESS volatility than the market (k ~0.5-0.9
vs 1.15: its fair is more extreme, it buys favourites), after it with MORE (k ~1.7-2.0: less extreme, it buys underdogs).
Not a composition effect of the rung classes: Friday 10-23 12-18 UTC was 81% 500-share orders with best k 0.5 (0.624; k 1.4:
0.502), Monday 10-26 12-18 77% 500s with best k 1.7 (0.701); the off-session blocks step too (0.5-1.2 before, 1.0-2.0
after). The step falls between Friday 10-23 18:00 and Monday 10-26 12:00 (the weekend had few windows quoted; the Monday
01:00 UTC restart carries the weekly sweep; the night size class also changed from 250 on Friday to 62 on Mon-Wed): a
weekend configuration change of the engine (C4 bot versions). Consequences: (1) the pre-registered BUILD (10-09..26)
is mostly the old version, which is why models fitted on it transfer poorly; (2) the frozen k = 1.4 is a
post-step value (it was chosen on the live block); (3) the residual's winner-to-loser flip and the locked/residual PnL
swap are the version change, not a market regime. Next iteration: pre-register a version-aware split (fit on the
post-step lot days, confirm on the 10-31 and 11-01 development blocks) before refitting any presence or selection model.
- Next-step addendum (01:19 UTC): (6) version-aware evaluation: pre-register a split that respects the 10-24/25 engine
  change (fit on post-step development data, e.g. the 10-31 00-06 / 12-18 and 11-01 06-12 blocks, confirm on VALIDATE
  10-27..30 aggregate or the reverse), then refit the presence and selection models of R7 on the post-step version only;
  (7) find the driver of the step (operator config at the Monday 01:00 restart and sweep? a vol-source switch?) on the
  pre-H history: best k per day over 10-09..22 from the BUILD fills (the detached fetch is fetching BUILD Chainlink
  stamps; with the Binance stand-in until then).

**A weekly cycle of the posture's volatility multiplier (`code11/k_by_day_bn.py`, `iter11_k_by_day_binance.json`,
`iter11_k_sun_mon_blocks.json`, `iter11_k_vs_weekpnl.json`; Binance stand-in so it covers BUILD; VALIDATE days as daily
aggregates).** Best k per day (sigma = k x v300; acc at the best k): 10-09 Fri 1.2, 10-10 Sat 0.7, 10-11 Sun 0.85, **10-12 Mon
1.7**, 10-13 Tue 1.4, 10-14 Wed 1.0, 10-15 Thu 1.2, 10-16 Fri 1.4, 10-17 Sat 0.85, 10-18 Sun 0.85, **10-19 Mon 2.0**, 10-20 Tue
2.5, 10-21 Wed 1.2, 10-22 Thu 1.0, 10-23 Fri 0.5, 10-24 Sat 0.7, 10-25 Sun 0.5, **10-26 Mon 1.7**, 10-27 Tue 2.5, 10-28 Wed 1.4,
10-29 Thu 2.5, 10-30 Fri 2.5. The stand-in reproduces the Chainlink version of the lot (0.5 / 0.85 / 0.5 / 1.2-1.7 / 2.0-2.5 /
1.4 / 2.0-2.5 / 2.0-2.5). Per 6-h block the jump comes on Monday morning UTC every week (10-11 Sun blocks 0.5-1.0 -> 10-12 Mon
00: 1.2, 06: 2.0, 12: 1.4, 18: 2.5; 10-18 Sun 12: 0.85 -> 10-19 Mon 12: 1.7, 18: 2.0; 10-25 Sun 0.5 -> 10-26 Mon 00: 1.0, 06:
1.4, 12: 1.7), i.e. after the 01:00 UTC Monday restart with the weekly sweep. In weeks 1-2 k then decays to 0.5-0.85 by
Friday-Sunday (the favourite share of the fills rises to 0.53-0.68); in week 3 (10-26..30) it stays at 1.4-2.5 through
Friday, and the live Saturday 10-31 blocks still fit k = 1.4 (0.79-0.84 per fill), so the decay did not resume. Not the
PnL since Monday: Spearman(cumulative BTC 5m+15m PnL since Monday at the day's start, best k) = +0.31 over 22 days (week 3
gained +$49k and kept a high k; week 2 lost -$13k and decayed). Reading (hypothesis): the engine's volatility (or its
edge threshold) is a state re-initialised at the Monday restart and updated during the week; its update rule changed or
stopped around 10-26. The STUDY/VALIDATE side break is this cycle (STUDY = Fri-Mon of week 2/3, VALIDATE = Tue-Fri of
week 3). Driver candidates for the next iteration: a running vol estimate since the weekly restart (compare k with the
realised vol accumulated since Monday 01:00 under several estimators), the treasury cycle (the collateral balance from
Transfer logs, development periods only), a human weekly config; and the exam-relevant question whether the current
version keeps k >= 1.4 over the weekend (11-01 06-12 is a Sunday development block: pre-registered above, k 1.4 vs 2.0).

**Running volatility estimators do not stabilise k (`code11/k_since_restart.py`, `iter11_k_since_restart.json`;
exploratory).** With a wider grid (k 0.25-4.0) the per-day best k scatters: v300 sd(log k) 0.77 (pooled best 1.4, 0.610),
v3600 0.75 (1.4, 0.613), realised vol since the daily 01:00 restart 1.02 (1.7, 0.593); the since-Monday estimator scores
0.467 pooled with best k at the grid edges, which points to a bug in its epoch arithmetic (rerun before reading it). None
explains the weekly cycle: the step looks like a parameter or regime switch, not a running estimate.

**The k cycle by rung class (`code11/k_by_class.py`, `iter11_k_by_class.json`; real Chainlink, exploratory).** Every class
moves with the cycle. 10-27..30 (high k): best k 2.0 for 500s (0.720; k 1.4 0.709), 250s (0.725; 0.688), 62s (0.649; 0.627),
other sizes (0.714); region D (sigma-free) 500s 0.816, 250s 0.520, 62s 0.508. 10-23..25 (low k): 500s best k 0.5 (0.636; k
1.4 0.489), 62s 0.85 (0.625), 250s 1.0 (0.712), other 0.5. So the off-session 62/250 rungs share the cycle (their "no public
side" in iteration 10 was partly the k mismatch: at k 2.0 the 250s score 0.725 per fill on 10-27..30), but they do not
follow Chainlink where it disagrees with the market (region D 0.51-0.52): the 62/250 side is the favourite/underdog choice
the multiplier encodes (the cheaper side when k is high), not the report. Only the 500 ladder carries the Chainlink skew.

## Iteration-11 final summary (01:24 UTC)
- R7 = R6 + the in-block price clock (adopted, pre-registered): price within a tick 0.8026 pooled on VALIDATE (bar 0.80).
- Outcome under strict fills: 0.207 / 0.218 for the frozen quote; oracle-side ceiling 0.47-0.49 / 0.52-0.53 on either clock.
- New mechanism: the posture's volatility multiplier follows a weekly cycle (reset high after the Monday 01:00 UTC restart,
  decaying to 0.5-0.85 by the weekend in weeks 1-2, no decay in week 3); the market prices ~1.15 x v300 throughout; the
  same takers fill the cluster on the other side when k changes. This is the STUDY/VALIDATE side break.
- Primary metric unchanged (0.716). Open: 28 catalog items (see state.json).

### Iteration 12 (2026-11-01, local Windows laptop, started 01:52:21 UTC; 730 of 1,200 budget minutes used before it)

Read first: BRIEF, NOTES (iteration 11 in full), state.json, FINAL_RULE.md, panels/iter11_{information,mechanics,
assumptions}.md. Calendar (`tools/sealed.py directional-maker`, 01:53 UTC): released h1, h2; development [10-23, 10-31
06:00) and [10-31 12:00, 18:00); the current block 11-01 00-06 is sealed; the next development block 11-01 06-12 starts
after this iteration (so again no new live development data). Shared live.py running (pid 27184, status 01:53 UTC). Free
disk 13.4 GB, available memory 3.3 GB; this workspace's cache 1.4 GB. Panel proposals added as catalog items: information
I11-1..I11-5 = X114-X118, mechanics P1-P5 = X119-X123, assumptions P1-P4 = X124-X127 (X124 = assumptions P1 full-machine
replay, X125 = P2 band, X126 = P3 maker shares, X127 = P4 step-or-drift).

**PIVOT (required: two iterations below +0.01 on the primary metric).** New paradigm: **the decision is typed and the
fill is a joint outcome with the competitors.** (1) New data: the full data-api tape WITH maker rows (every competitor's
wallet on every print; pre-registered sample of 1,056 BTC 5m windows) and the wallets' whole activity history from the
first trade (almach 05-22, bosona 06-02, mo-money 02-04). (2) New unit: the order (order hash) typed by its decision
(near-side posture rung, deep longshot, pairing bid, far-side rung) instead of the pooled fill. (3) New model class for
the outcome: the whole decoded state machine (entry, held-outcome rungs, imbalance pairing) replayed under strict fills.

**Competing explanations (iteration 12) and the observation that separates them**
1. E1 sigma-multiplier state (the iteration-11 reading): the engine prices a Chainlink digital with k x v300 and k moves
   (weekly). Separates: the favourite tilt vanishes in k-invariant cells (|z| ~ 0, region D); the quote-level k equals
   the fill k. (The assumptions panel F2 already reports a tilt of the same size in the k-invariant cell: against E1.)
2. E2 intercept / configuration epochs: the engine's fair carries an additive favourite/underdog tilt pushed at discrete
   operator events, shared by the three processes. Separates: piecewise-constant residual tilt with steps simultaneous
   across wallets at restarts / size switches (PELT on the residualised favourite indicator; whole history).
3. E3 competition at the touch: the cluster's quote is stable, and other makers' favourite-side aggressiveness moves
   the cluster's fill composition. Separates: in the maker-row tape, a competitor (or the market's other makers) gains
   favourite-side maker share exactly where the cluster's favourite share falls (Spearman <= -0.5 over blocks), while the
   cluster's share of underdog-side maker volume is flat; vs the cluster's own favourite-side share falling with
   competitors flat (own quote).
4. E4 band / taker choice: the engine is two-sided inside |fair - mid| < h; the fill side there is the takers' (and
   competitors') choice; outside the band the posture holds every day. Separates: posture accuracy outside the band >=
   0.85 on every day with no weekly drift; the daily favourite share explained by the inside-band share x the takers' mix.
5. E5 order-type composition: the per-fill side mixes decisions with different laws (decided-window longshot bids at <=
   0.10, pairing bids on the under-held outcome, far-side 62/250 rungs, near-side posture rungs) whose shares move by day.
   Separates: per-type side accuracy stable across days, and the near-side posture rungs at >= 0.80 per order.
6. E6 volatility-driven tilt: the tilt is a monotone function of realised vol (weekends are low-vol). Separates: on the
   whole history (May-Oct) a stable slope of the favourite share on log RV and no weekday step net of RV.
7. E7 (unlikely) the exit makes the money and the side is incidental: the locked pairs (entry + imbalance pairing bids)
   carry the PnL and the outcome correlation (assumptions F3: on VALIDATE locked +$38k vs residual -$14k). Separates: the
   full-machine replay with a pairing leg reproduces the cluster's window PnL far better than the one-sided replay, and
   its locked part correlates with the cluster's locked part.
8. E8 (unlikely) a discretionary weekly view: a human sets a directional lean (momentum vs mean reversion at 5 minutes)
   once or twice a week. Separates: steps at human hours (ET business hours / Monday morning), aligned with nothing
   mechanical, and a sign that follows the previous week's BTC trend or the previous week's favourite returns.

**Pre-registrations (written 02:05 UTC 11-01, before any of these numbers is read).**
- **PR12-A (X124, full-machine replay; outcome).** Candidates: main rule {posture every second, held (posture until the
  replay's first fill, then the outcome it holds more of)} x pairing leg {off, on}; fixed: latency 2 s, slack 2,
  trade-through, last clean print - 0.01, session size (500 / 62), full flow (`code12/replay_machine.py`). Choose on STUDY
  by the mean of Pearson and Spearman of the per-window PnL against the cluster's maker-BUY window PnL (windows with >= 1
  cluster maker fill). Score the chosen one on VALIDATE (aggregate), per wallet and half, with the locked and residual
  parts separately; oracle_net (the cluster's terminal net side) with and without pairing as ceilings; latency 0
  exploratory. Adopt as R8's executable outcome rule if both VALIDATE correlations exceed R7's replay (0.207 / 0.218) and
  the 2-h block bootstrap lower bound of the gain in the mean correlation is > 0.
- **PR12-B (X125, the band; side).** Per fill on the lot with the real Chainlink posture (iteration-10/11 inputs: T_hat -
  1,432 ms, Gamma strike, frozen 1.4 x v300, last clean print at b - 3), e = fair(token) - mid(token). Two-regime rule:
  |e| > h -> the posture; |e| <= h -> an inside rule in {the cheaper token, the complement of the clean taker net demand
  over the previous 30 s}. (h, inside rule) chosen on STUDY over h in {0.01, 0.02, 0.03, 0.05, 0.07, 0.10}; scored on
  VALIDATE per fill against the frozen posture on the same fills. Adopt if the gain is >= +0.02 with the 2-h block
  bootstrap lower bound > 0. Also reported: the posture accuracy outside the band per day (E4's signature: >= 0.85 every
  day).
- **PR12-C (X120/X122, typed orders; side).** Unit = filled maker order (wallet, order hash); types frozen now: deep =
  calldata limit <= 0.10; pairing = calldata original size within 2% of the wallet's own |Up - Down| imbalance in the
  window just before the order's first fill and on the under-held outcome (X92's definition); near = limit within one
  tick of the in-block anchor minus 0.01 (R7-price); far = deeper. Per type: the frozen posture accuracy per order and
  per fill, the cheaper-side baseline, the own-inventory baseline, and the type's share by day. The oracle near-side
  share is reported as the per-fill ceiling of any one-side rule.
- **PR12-D (X114, whole history).** F_b = favourite share (fill price > 0.5) of the cluster's BTC 5m BUY TRADE rows per
  6-h block (activity; taker buys included as a first pass), from the first trade to 10-30. Models fitted on blocks
  before 09-30 and scored on 10-01..30 (VALIDATE days only as block aggregates): (a) weekday dummies (UTC), (b) log
  realised vol of the block (Binance 1-m returns), (a+b), (d) a piecewise-constant mean with change points (fitted on
  the history, last level carried forward). Report the out-of-sample R^2 of each and the Monday step net of RV.
- **PR12-E (X126/X115/X121, maker shares).** Sample fixed in `code12/fetch_makers.py` (windows starting at 02, 08, 14,
  20 UTC, 10-09..30). Per 6-h block: the cluster's favourite share of its maker BUY volume, its share of the
  favourite-side and of the underdog-side maker BUY volume, the market's maker favourite share, the top makers'
  favourite-side shares. Signatures as the panel wrote them: "competition" if a competitor's (or the top-k
  competitors') favourite-side share rises >= 0.15 where the cluster's falls with Spearman <= -0.5 over blocks; "own
  quote" if the cluster's favourite-side share falls while competitors are flat.

**Data added (iteration 12).**
- Whole activity history of the three wallets from the first trade (`code12/fetch_history.py`; almach 2026-05-22, bosona
  06-02, mo-money 02-04 with sports first): reduced to the crypto Up/Down rows in `.cache/re/directional-maker/it12/hist_btc.parquet`
  (66 MB; the raw chunks are deleted, the responses stay in the shared HTTP cache). 959,805 BTC 5m BUY fills in 637 6-h
  blocks from 05-22 18:00 to 10-30.
- Maker-row tapes (`code12/fetch_makers.py`, data-api `/trades` with `taker_only=False`) for the pre-registered sample:
  every BTC 5m window starting at 02, 08, 14 and 20 UTC of 10-09..30 (1,056 windows, 4.8M rows; 1.67M taker rows removed
  with the taker-only tape) compacted to `it12/maker_rows.parquet` (3.1M maker rows, 9,544 wallets, integer codes in
  `it12/maker_wallet_codes.parquet`).
- Owners of the three accounts (`code12/owners.py`, `results/iter12_owners.json`): mo-money is a Safe (owner EOA
  0xd1f9bc03...); almach and bosona are ERC-1967 proxies (implementation 0x58ca52eb..., factory 0x00000000000fb5c9...) whose
  immutable args name owner EOAs 0xb3f8b214... (almach, Polygon nonce 1,456) and 0x4acd0e52... (bosona, nonce 2). Their V2
  orders use signatureType 3 (signer = the proxy) for almach / bosona and 2 for mo-money (signer = the Safe owner).
  Hyperliquid: almach's and bosona's owners are unknown there; mo-money's owner has no fills in the 120 days before T0 and
  its last ledger event is a 2026-06-13 spot transfer.

**PR12-A result (X124, full-machine replay; `code12/replay_machine.py`, `replay_machine_score.py`;
`results/iter12_replay_machine.json`, at-touch variant `iter12_replay_machine_touch.json`).** The replay reproduces R7's
number exactly where it should (posture, no pairing, L 2: 0.2066 / 0.2181). **The pairing leg makes every replay worse:**
VALIDATE posture + pairing -0.016 / -0.002; held + pairing 0.027 / 0.028; **the oracle side + pairing 0.246 / 0.299 (without
pairing 0.473 / 0.527)**. The replay's pairing bids fill only on adverse trade-throughs: its locked-pair PnL on VALIDATE is
-$106k (posture) to -$236k (oracle) while the cluster's locked pairs made +$38.1k; with first-in-queue (at-touch) fills it is
still -$87k to -$236k. STUDY choice (pre-registered): held without pairing (0.049 / 0.120), VALIDATE 0.111 / 0.179, gain over
R7 [-0.148, +0.008] (P(gain <= 0) 0.96): **not adopted**. The panel's "the ceiling belongs to the one-sided replay" is
refuted in its own terms: with the decoded exit the ceiling under strict fills is lower (0.25 / 0.30), so the cluster's
locked-pair profit needs fills that do not trade through (fresh at-touch posts with queue priority, priced off the moving
market), which no tape replay can be credited with. This is now the quantitative account of the outcome gap.

**PR12-C result (X120 / X122, typed orders; `code12/typed_side.py`, `results/iter12_typed_side.json`).** Types by the
calldata order (limit vs the in-block anchor - 0.01, original size, own imbalance). Fill shares STUDY / VALIDATE: near
(within a tick of the R7 price) 0.59 / 0.48, pairing 0.13 / 0.18, far 0.12 / 0.07, above 0.10 / 0.08, deep (<= 0.10) 0.06 /
0.19. Posture (real Chainlink) per fill: near 0.571 / 0.648, far 0.46 / 0.50, above 0.54 / 0.53, deep 0.83 / 0.88 (cheaper
side 1.00: a 0.05 bid can only be on the cheap token), pairing 0.56 / 0.71 (under-held 1.00 by construction). **The own
held outcome beats the posture on near rungs on both halves: 0.753 / 0.741 per fill (0.654 / 0.634 per order).** The deep
share rose by day 2.5% (10-24) -> 8.6% (10-26) -> 15-23% (10-27..30); the near rungs' favourite share falls too (0.51-0.62
-> 0.33-0.47), so the drift is not only the deep type.

**PR12-B result (X125, the band; same script).** STUDY choice h = 0.02 with the 30-s taker-flow complement inside:
VALIDATE 0.6823 vs the posture 0.6826 on the same 26,433 fills (gain [-0.009, +0.010]): **not adopted**. E4's signature
fails: the posture outside the band is 0.51-0.75 by day (not >= 0.85) and does not rise with h (VALIDATE 0.69-0.72 for h
0.01-0.10; STUDY 0.58 -> 0.51). Historically the fill side does not become more posture-bound at larger edges.

**The side as a state machine (PR12-F, EXPLORATORY: designed at 02:30 UTC after the per-type VALIDATE aggregates above were
seen; `code12/composite_side.py`, `results/iter12_composite_side.json`, `iter12_composite_v2.json`).** Branches: decided
window (|Up mid - 0.5| > 0.4 at b - 3) -> the cheaper token; no position of the CLUSTER (three wallets pooled, maker + taker
BUY rows before the fill's second) -> the Chainlink posture; after entry -> the outcome the cluster holds more of for
schedule-size orders, the under-held outcome for non-schedule (pairing) orders. **VALIDATE 0.790 per fill (2-h block
bootstrap [0.766, 0.811]), 0.725 per order; halves 0.782 / 0.795; per wallet almach 0.795, bosona 0.783, mo-money 0.792; by
day 0.755 / 0.804 / 0.798 / 0.791. STUDY 0.753 / 0.690.** Branches on VALIDATE: decided 0.812 (27% of fills), entry 0.704
(9%), after entry schedule-held 0.771 (54%), non-schedule under-held 0.906 (10%). Baselines on the same fills: no own state
(decided-cheaper else posture) 0.693 (gain +0.097 [+0.074, +0.121]), posture 0.679, cheaper 0.679, favourite 0.322, own
inventory only (cluster held outcome, posture without a position) 0.611. With each wallet's own inventory instead of the
cluster's: 0.766 (STUDY 0.703), i.e. **the engine's state is the cluster position, not the wallet's** (wallet-level held
0.727, cluster-level 0.764-0.774 on the after-entry schedule fills). On STUDY the after-entry 500 and 250 rungs follow the
cluster's held outcome 0.88-0.89 (posture 0.55-0.70); where held and posture disagree, held still wins 0.77. The decided
branch is the unstable one (cheaper 0.59 STUDY / 0.81 VALIDATE), with the deep-bid module (below). Wired into evaluate() as
`side_state_machine` (`code/side_sm.py`; block clock, Chainlink stamp b - 4, calldata sizes for up to 3,000 transactions);
smoke test on the historical VALIDATE hour 10-29 12-13 (680 fills): composite 0.825 (bosona 0.81, almach 0.80, mo-money
0.87), no own state 0.678, cheaper 0.778, calldata joined 99%, Chainlink 86%, 41 s.

**Pre-registration H12-SIDE-SM (written 02:47 UTC 11-01, before the block exists).** On the next development blocks with
BTC 5m fills (11-01 06-12 first, then 11-01 18-24 and 11-02 00-06), evaluate()'s `side_state_machine.composite_own_state`
per fill >= 0.78 and >= `no_own_state` + 0.05, every wallet within 3 points. If it holds, R8's side component is tagged
"development-verified" (still own state); if not, the composite is reported as a VALIDATE-only description.

**PR12-E result (X126 = X115 = X121, maker shares; `code12/maker_shares.py`, `results/iter12_maker_shares.json`).** 2.8M
maker BUY rows, 79 sampled (day, hour) blocks, 7,439 makers; the cluster holds 1.97% of maker BUY volume, the top 10 others
20.0%. The market's maker favourite share is flat (0.50 / 0.51 BUILD+STUDY / VALIDATE; variance of its log-odds 0.017 vs
1.53 for the cluster's): **the cluster's favourite share is entirely its own relative presence on the two sides.** From
BUILD+STUDY to VALIDATE its share of the favourite-side maker volume stayed 0.022 -> 0.022 while its share of the
underdog-side volume rose 0.015 -> 0.026; the top-10 competitors' share of the favourite side stayed 0.185 -> 0.181. No
top-30 competitor's favourite-side share moves against the cluster's (Spearman over blocks -0.34..+0.28; the panel's bar
<= -0.5), others' favourite share vs the cluster's +0.12, and no top-15 maker shares the cluster's daily cycle (-0.47..+0.33).
**Competition is rejected; the change is the cluster's own quote: it added underdog-side bids** (consistent with the deep
longshot module below), it did not lose the favourite side.

**Longshot capture at constant opportunity (X120 step 1; `results/iter12_longshot_capture.json`).** Taker BUYs at >= 0.90
in the cluster's windows: 0.29-1.7M shares a day on 10-23..26, 1.7-2.3M on 10-27..30; the cluster's <= 0.10 fills: 0.7-5.8k
(10-23..25), 27.7k (10-26), 52-127k (10-27..30): **capture 0.2-0.4% -> 1.6% (Mon 10-26) -> 2.3-5.5%**, a >10x step at a flat
opportunity. The deep-bid module was switched on / up on Monday 10-26 and ramped through the week: a configuration of the
decided-window quote, part of the "weekly cycle".

**PR12-D result (X114 = information I11-1, first pass; also X127 / X123; `code12/hist_state.py`,
`results/iter12_hist_state.json`).** 637 blocks, 959,805 BTC 5m BUY fills (05-22..10-30). Out-of-sample R^2 of the
favourite share on 10-01..30 for models fitted before 09-30: constant -0.14, weekday -0.20, log RV -0.28, weekday + RV
-0.31, + time of day -0.35, change points carried forward -1.22; in-sample R^2 0.00-0.02. The weekday profile reverses
across the history (May-Jul: Monday 0.51 falling to Saturday 0.36; Aug-Sep flat 0.32-0.42; October Monday 0.37 rising to
Sunday 0.53), and corr(F, log RV) is +0.12 / +0.14 / -0.24 by period. Optimal-partition change points (whole series): one
(06-05 18:00, bosona's start), explaining 12% of the block variance. The three wallets' block favourite shares correlate
0.69-0.78. **Readings (a) Monday state, (b) volatility and (d) configuration steps are all rejected as the driver of the
favourite share; the share is a noisy block-level aggregate of window-entry decisions, synchronous across the wallets.**
(c) risk budget is not tested here (iteration-11 PnL since Monday +0.31; assumptions panel F4 against).

**X117 (information I11-4) falsifier (b) (`results/iter12_live_k_grid.json`).** On the live development block 10-31
14:06-16:30 (1,668 match-clock fills, real Chainlink) the per-fill posture on a wide multiplier grid peaks at k = 1.4
(0.809; k 0.7-1.2: 0.78-0.80; k >= 2.4: <= 0.60); window bootstrap of the argmax [0.7, 1.68], never >= 2.5. **Candidate (b),
the realised vol of the Chainlink stream in its noise regime as the engine's sigma, is out.** (a) Deribit front-expiry IV:
not run.

**Iteration-12 synthesis.** The side decision is now decoded as a window state machine shared by the three wallets: the
entry follows the Chainlink posture (0.66-0.70 per fill), then the cluster adds to the outcome it holds (schedule rungs,
0.77-0.79) and bids the imbalance on the other outcome (non-schedule pairing orders, 0.91-0.94), and in decided windows it
bids the cheap loser (a deep-bid module switched up on 10-26). Per fill 0.790 on VALIDATE with own state (0.693 without).
The "weekly k cycle" is not a stable state: the whole history rejects weekday, volatility and step models, the market's other
makers are flat, and the drift is the cluster's own entry and deep-bid decisions. The outcome gap is the exit: the cluster's
locked pairs (+$38k on VALIDATE) need queue-priority fills that a strict-fill replay of the same machine loses (-$106k to
-$236k).

**Late results (02:44-02:53 UTC).**
- **X116 / X119 step 1, the multiplier read off the quote (`code12/quote_k.py`, `results/iter12_quote_k_1793455600_1793464202.json`;
  live 10-31 14:06-16:30, Saturday).** Ladder center F of the exact-500 top rungs, inverted with the Chainlink report
  (publish lag 1,432 ms), the RTDS TWAP-60 strike and the 300-s futures vol: BTC 5m k median 1.14 (window bootstrap
  [0.99, 1.30], IQR 0.76-1.65, per-minute 10-90% 0.72-2.04; 3,082 s, 28 windows), BTC 15m 1.37 ([1.16, 1.62]). The
  fill-level best k on the same block is 1.4 ([0.7, 1.68]): quote k = fill k within the intervals on this block; the 5m
  ladder center sits near the market's own multiplier (~1.15). The Monday comparison (pre-registered by the panel: Monday
  quote k >= Sunday + 0.5) needs 11-01 06-12 and 11-02 00-06 / 12-18.
- **E9 cross-market own state (`code12/xmarket_entry.py`, `results/iter12_xmarket_entry.json`; exploratory).** Entry fills
  (no cluster position in the 5m window, not decided): with a cluster position in the overlapping BTC 15m window (21-23% of
  entries) the entry follows it 0.70 STUDY / 0.61 VALIDATE vs the posture 0.67 / 0.74 there; where they disagree the 15m
  position wins 0.55 / 0.35. The previous 5m window's net side: 0.57 / 0.50. Rejected: the entry is not a cross-market or
  carry-over decision.
- **Deep-bid module timing (`code12/deep_step.py`, `results/iter12_deep_step.json`).** Deep (limit <= 0.10) share of the
  cluster's filled orders by day 4.3%, 5.2%, 6.7%, 10.7% (Mon 10-26), 15.9%, 17.9%, 22.1%, 24.1% (10-30); among orders in
  decided windows 26%, 25%, 32%, 51%, 57%, 62%, 71%, 66%. Hourly on STUDY it is noisy (0-23%) and highest on 10-26
  12:00-17:00; it does not step at a salt-counter reset (resets on STUDY: the daily ~01:00-01:10 restarts of 10-23 and
  10-26, and ad-hoc restarts at 10-24 15:25:45, 10-26 16:38-16:42 and 10-26 19:36-19:39, all three wallets within 5 s).
  A ramp from Monday, not one configuration push.
- **R8 side on BUILD (replication, no calldata sizes; `code12/sm_build.py`, `results/iter12_sm_build.json`).** 49,569
  BUILD fills (10-09..22, Binance stand-in posture): the no-size state machine 0.705 vs no own state 0.608, posture 0.601,
  cheaper 0.535. **The after-entry branch (71% of fills) follows the cluster's held outcome 0.725 (posture on the same fills
  0.589), 0.62-0.80 by day with no weekly pattern**; the pairing fills count as errors in this variant (with sizes the
  lot gains +0.07-0.10).
- **BTC 15m (`results/iter12_composite_v2.json`).** Without sizes the 15m state machine scores 0.696 STUDY / 0.754 VALIDATE;
  the no-own-state rule 0.583 / 0.821 (the 15m posture is strong on VALIDATE). `evaluate()` now also reports
  `btc15m.side_state_machine` with calldata sizes (smoke hour 10-29 12-13: 98 fills, 0.867; no own state 0.592).

## Iteration-12 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**. The
  frozen rule is now **R8 = R7 + the window state-machine side** (reported by `evaluate()` as `side_state_machine` for 5m and
  `btc15m.side_state_machine`; counted part public; the own-state composite and the own-history baseline reported beside it).
- Paradigm (pivot): typed decisions and the fill as a joint outcome with competitors; new data (maker-row tapes of 1,056
  windows with every competitor's wallet; whole activity history from May; account owners), new unit (the typed order), new
  model class for the outcome (the full machine replay with the exit).
- target_metrics changes: side_accuracy 0.672 (bin level) -> **0.693** (per BTC 5m fill, the PUBLIC part of R8-side; market-only
  baseline 0.679); the own-state composite (0.790) is reported only, because the own-history baseline beats it (0.822, see
  'The confound, measured' below); everything else unchanged (presence 0.788 / 0.780 union, 0.716 / 0.684 5m;
  selection 0.685 / 29.5% / 2.87; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891).
- Closed: X114, X115, X120, X122, X124, X125, X126, X127, X24, X111. Partial (open): X116, X117 ((b) falsified), X118
  (owners recovered), X119, X121, X123. Open from before: X9, X41, X57, X59, X61, X62, X67, X71, X75, X76, X83, X87, X89,
  X90, X91, X94, X95, X99, X101-X105, X107, X112, X113.
- What the pivot showed: (1) after entry the fill side follows the cluster's own previous fills (same-side runs, 0.88) more
  than its position (0.77-0.79; BUILD 0.725), so the after-entry side is fill persistence, not a decoded quote rule (pairing
  bids on the under-held outcome stay decoded); (2) the favourite-share "weekly cycle" is not a parameter
  (whole history), not competition (maker shares) and not a band; it is the entry decisions plus a deep-bid module that
  ramped up from Monday 10-26; (3) the outcome gap is the exit: the decoded pairing leg loses heavily under strict fills.

**Next steps (iteration 13; the next development block 11-01 06-12 UTC ends at 12:00, then 11-01 18-24 and 11-02 00-06).**
1. H12-SIDE-SM on 11-01 06-12 (and later blocks) through `evaluate()`; the panel's X116 / X119 Monday quote-k series on
   11-02 00-06 with `code12/quote_k.py` adapted to dx_clob, and the X103 re-post race on the 11-01 06-12 full-depth recording.
2. The entry decision (posture 0.66-0.70 per fill, the remaining side gap): what sets the first quote's side when no
   position exists (a two-sided opening ladder whose fill side the takers choose?), on the live quote unit.
3. Selection with the state machine: print-level selection where the predicted resting side is the held outcome (own
   state, reported separately) vs the public posture, on the lot with X102's Chainlink seconds.
4. X118 sweep destinations; X117 (a) Deribit front IV; X121 per-match level labels; X123 minute-level change points.

**Entry branch by multiplier (`results/iter12_entry_k.json`, exploratory).** Entry fills (no cluster position, not decided, real
Chainlink): STUDY best k 1.0 (0.694; k 1.4 0.656), VALIDATE best k 1.4 (0.709; k 1.0 0.622); first fills of windows 0.657 /
0.722 at k 1.4. The multiplier drift of iteration 11 lives in the entry decision; the after-entry branch does not need it.

**X117 (a) Deribit front-expiry IV (`code12/deribit_iv.py`, `results/iter12_deribit_iv.json`).** history.deribit.com option
trades (148,444; 14,998 front-expiry ATM) for 80 blocks of 10-09..30: Spearman of the cluster's block favourite share with log
IV -0.21 (with log RV -0.43); on the 28 lot blocks with a best k, sd(log k) 0.52 vs sd(log(k x rv / iv)) 0.64 (the panel's bar
< 0.3): IV does not absorb the multiplier; Spearman(k, log IV) 0.11. With (b) out (live k 1.4), X117 is closed. Mean front IV
28.7% (BUILD + STUDY) vs 35.3% (VALIDATE aggregate).

**X118 note.** The sweep path was already decoded by the iteration-9 assumptions panel (proxy -> own EIP-7702 address ->
pUSD unwrapped to USDC.e -> ERC-4337 EntryPoint -> one plain EOA per wallet, 0xe3c61b5a... / 0x44c83a63... / 0x2084ab26...).
A naive any-token Transfer trace of the 10-12 sweep (`code12/sweep_trace.py`) picked up trade transfers; its output was
discarded. Still open: those three EOAs on Hyperliquid and Polygon.

**Caveat on R8-side (the confound the next iteration must separate).** After entry the cluster's net position in a window is
close to the side of its own earlier fills there, so 'buys the held outcome' cannot by itself tell a quote policy (schedule
rungs posted only on the held outcome, pairing bids only on the other) from taker-flow persistence (both outcomes quoted, takers
keep hitting the same side; the live own-history baseline 'side of the previous event' was 0.86 in iteration 9). For the policy
reading: the schedule rungs sit on the under-held outcome only 0.30-0.32 of the time (X92) and the pairing bids exist only there
by size; against it: the market-only taker-flow complement is weak (0.58). Test on the live quote (dx_clob, 11-01 06-12 and
later): after entry, the share of seconds with a schedule-size cluster rung at the touch of the under-held outcome vs the held
one. Until then R8-side is a description with own state, not a decoded quote rule.

**The confound, measured (03:00 UTC; `code12/persist_vs_policy.py`, `results/iter12_persist_vs_policy.json`).** After-entry
schedule-size fills (not decided, cluster position != 0): the outcome of the cluster's previous fill in the window predicts the
fill 0.885 STUDY / 0.884 VALIDATE vs the held outcome 0.787 / 0.771; **where the two differ (16-18% of these fills) the fill follows
the previous fill 0.815 / 0.823 and the held outcome 0.18.** Non-schedule (pairing) fills: under-held 0.94 / 0.91, previous fill
0.66 / 0.65. Per fill over all lot fills the own-history baseline (previous cluster fill's side, posture where none) scores
0.809 / 0.822, above the own-state composite (0.753 / 0.790). **So the after-entry branch is the persistence of same-side fill
runs, a trivial own-history baseline, not a decoded quote rule; the composite is withdrawn as a side claim.** target_metrics
side_accuracy now reports the public part of R8-side, 0.693 per fill (decided window -> cheaper token, else the Chainlink
posture) against the cheaper-token baseline 0.679; `evaluate()` reports `own_history_prev_fill` beside the composite and marks
`counted_side = no_own_state`. What remains real from the typing: pairing bids (non-schedule sizes) sit on the under-held
outcome (0.91-0.94; X92), and the deep-bid module and the entry decision carry the favourite-share drift.
(Iteration 12 ended 2026-11-01 03:05 UTC, about 72 minutes.)

**X129 (own): the side per fill run (`code12/side_runs.py`, `results/iter12_side_runs.json`).** A run = consecutive cluster fills
of one window on one outcome. STUDY 1,098 runs (7.5 fills each), VALIDATE 2,882 (9.7). The public R8 side scores 0.547 /
0.611 per run (per fill 0.569 / 0.693; cheaper per run 0.47 / 0.57). The window's first run (the entry) 0.619 / 0.725; the
later runs, which by construction switch outcome, 0.466 / 0.541, near chance. Quantitative account of the side: one entry
decision per window that follows the Chainlink posture ~0.62-0.73, then taker-chosen switches between outcomes that no
public input predicts, each repeated ~8-10 times by same-side fill runs; the per-fill number is a run-length-weighted mix
of the two.

**X116 addendum.** Second live development segment 10-31 17:29-18:00 (`results/iter12_quote_k_1793467740_1793469600.json`): BTC 15m ladder-center k 1.13 (700 s, 2 windows); BTC 5m had only 11 usable seconds (switched off at 16:53). Cache housekeeping: deleted agg_2026-10-26 / aggfut_2026-10-26 (iteration-4 one-day Binance reductions, regenerable) and it12/machine_windows_touch.parquet (its scored result stays in results/iter12_replay_machine_touch.json); the workspace cache is 1,510 MB. Shared live.py running at 03:04 UTC (not touched).

## Iteration 13 (started 2026-11-01 03:40 UTC; 802 of 1,200 minutes used)

Current block 11-01 00-06 is sealed; the next development block (11-01 06-12) starts after this iteration ends, so no
new live development data is available this iteration. Development live data: 10-31 00-06 and 10-31 12-18 only.
Recorders checked 03:43 UTC: examrec (dx_*), rtdsstream (dy_rtds), rtdsbn (dz_rtdsbn), famrec (dw/dx family books)
running; X102 endpoint fetcher 27,120 / 46,610 done; shared live.py running (not touched).

**Competing explanations (iteration 13) and the observation that separates them.**
1. *Settlement-fair ladder (public law a).* At each pass the engine prices every rung of an outcome at
   F_CL(k, lag) - h(tau, rung) and posts it unless it would cross; it is at an outcome's touch only when F - h >= the
   touch. Separator: the uncensored tracer re-sign prices follow F_CL - h within a tick >= 60% with no own-state residual;
   switches are level crossings of F_CL(under) - h into the touch.
2. *Mid-anchored skew (public law b).* The quote is the ex-cluster mid plus a fraction beta of the Chainlink edge minus h.
   Separator: beta well below 1 and a better tracer fit than (a); the quote follows the book, not the fair.
3. *Pair lock (own-state law c/d).* The under-held ladder is priced to lock a pair: 1 - m - (held outcome's top rung in
   the same pass) or 1 - m - held VWAP. Separator: tracer prices track the held side's rung (c) or are flat between own
   fills (d); the pair sum is constant.
4. *Touch peg (market-only law e).* touch - j ticks, j decreasing with time since the imbalance changed. Separator: the
   tracer's distance to its own touch is a function of age only, not of any fair.
5. *Private / faster reference (H8).* The engine sees the Chainlink report before the public RTDS relay. Separator:
   tracer re-signs that move in the direction of the next report precede its RTDS publish ms.
6. *Degraded October configuration (assumption panel).* The decision functions are stable and decodable in the Jun-Sep
   version; October (the whole development lot) is a wind-down with competitors near the strike. Separator: R8's public
   side, entry run and presence gain on 09-26..10-11 vs October with the same frozen functions.
7. *Calibration maker (side as a by-product).* Profit is bid price below outcome probability on whichever outcome is
   offered, largest in the tails; side is a consequence. Separator: per-bucket returns of fills vs the engine's fair;
   the late-window lock-in fair at the settlement switches (08-07, 08-14).

This iteration discriminates 1-5 with the tracer orders (new unit: the re-sign of a uniquely sized order, uncensored and
wallet-attributed; new data: the full-depth raw book with exact size deltas), tests the level-crossing switch rule on
the lot, and starts the data for 6 and the family settlement streams (I12-2).

**X131 step 1 (I12-2): family settlement-stream recorder started (03:44 UTC).** `code13/rtdsfam.py` = `code7/rtdsstream.py`
with KEEP = xrp/doge/bnb/hype and feed `dv_rtds` (Chainlink + TWAP-60 streaming updates with publish ms), hard stop
11-03 00:00, disk cap 60 MB, detached (Start-Process). Its status counter shows writes within the first minute, so RTDS
publishes at least one of those symbols; the current block is sealed, so the per-symbol check waits for 11-01 06:00.

**X135 (mechanics P1): tracer orders (`code13/tracers.py`, `tracer_laws.py`, `tracer_lag_scan.py`, `tracer_own.py`,
`tracer_touch.py`; results/iter13_tracer_*.json).** 10-31 14-18 dm_clob_raw (hour 14 cut by the corrupt gzip block): 619
cluster maker BUY orders in the live calldata, 92 with non-schedule sizes, 57 with an exact-size chain before their fill,
859 re-sign events (5m 683, 15m 176; momoney 416, almach 266, bosona 177). Split pre-registered: orders by fill time,
earlier half FIT, later half TEST.
- *Existence and size are own state, deterministic:* the tracer sits on the wallet's under-held outcome in 0.93 of
  re-signs and its size equals the wallet's own |Up - Down| (data-api activity) exactly in 0.78 (the rest is the block-
  second timing of the activity rows).
- *Level: no law decodes it.* Within one tick on TEST: (a) fair cap min(F_own - h, ask - 0.01) 0.233 (h = -0.035);
  (a2) h by time left 0.233; (b) mid skew 0.205 (beta 0.6); (c) complement lock vs the other outcome's same-pass top
  rung 0.173 (coverage 20%); (d) cost lock 1 - VWAP_held - m 0.169; (a + d) 0.207; (e) touch peg 0.120, by age 0.158;
  anchors: ex-tracer bid 0.193, bid - 0.01 0.270, last ex-cluster trade - 0.01 0.205. MAE 7-11 c for every law. The
  pair cost at the re-sign (tracer + held VWAP) spreads 0.61-1.19 (q10-q90): not a lock at a margin.
- *The reference is the latest public Chainlink report, with no lead:* the within-order Spearman correlation of the
  re-sign price with the Chainlink digital peaks sharply at a stamp lag of 1,250 ms (0.54-0.56; 0.49 at 1,000 and 1,750
  ms; 0.30 at 3,000 ms) and is 0.14-0.18 for future stamps (L < 0): the engine prices off the report already published
  on the relay, not the next one (explanation 5, a private faster reference, is rejected at this resolution). The
  multiplier is not identified by the order (k 0.7-1.4 within 0.02 of rho).
- *Where it rests:* at or above its own ex-tracer touch in only 10% of re-signs; the median depth goes from -17 c
  (edge F_own - touch < -0.3) to -5 c (edge > 0.3); at-touch AUC by the edge 0.69, by age 0.54. Even with the fair far
  above the touch it joins the touch only 17-20% of the time. So the pairing bid is a deep passive bid whose depth
  shrinks with the Chainlink edge, not a fair-capped bid at the touch.
- *Per wallet (X138):* the fair-cap h fitted per wallet (almach 0.00, bosona 0.105, momoney -0.035) does not transfer
  (TEST 0.11-0.24) and the pooled h does as well or better (bosona 0.31): no per-wallet parameter is identifiable from 57
  orders.

**X136 step 1 (mechanics P2): switches are mostly quote moves (`code13/switch_class.py`, results/iter13_switch_class.json).**
1,406 cluster filled orders on 10-31 14-18; the post (latest exact-size add at exactly the order's limit before the
fill) is found for 92%. Class (i) "the post was at or above the own touch" 0.73 of all fills (median age 0.86 s,
q75 2.9 s); class (ii) "rested below the touch (median 2 c) until the market came to it" 0.27. Switch fills (first fill
of every run after the first, n 111): class (i) 0.71 (schedule sizes 0.75, pairing 0.55), median age 0.42 s; entry-run
starts 0.81. The panel's signature "(i) carries >= 70% of switches" holds (0.71): a switch is the cluster moving its
quote to the other outcome's touch, not a taker sweep.

**X130 (information I12-1, partial): the side residual is the class-(ii) fills (`code13/post_posture.py`,
results/iter13_post_posture.json).** The Chainlink posture at the POST time (F_up at stamp lag 1,250 ms, 1.4 x 300-s vol,
Gamma strike, vs the Up mid carried by the add's price_change row): class (i) quote moves 0.807 (942 fills; cheaper
0.56), class (ii) resting orders reached by the market 0.507 (355 fills; chance), all 0.725. The posture decodes the
quote moves; the fills of resting deep rungs follow the market's move into the ladder (taker choice), which no
quote-side input can predict. (The match-clock posture scores 0.84 because the mid at the match already includes the move
that brought the market to the resting rung.)

**X143 (assumptions P4): online configuration rejected (`code13/online_config.py`, results/iter13_online_config.json).**
Calendar emulated on the lot (sealed-pattern iff d + j odd). k (0.5-3.0) and the decided-window branch read from the most
recent development-pattern block: per-fill gain over the frozen constants -0.007 on STUDY (0.593 vs 0.600; 2-h bootstrap
95% [-0.090, 0.098]) and -0.010 on VALIDATE aggregate (0.697 vs 0.707; [-0.051, 0.027]); entry run +0.035 STUDY,
-0.028 VALIDATE. The parameter swings do not persist at a 6-12-h horizon.

**X140 (assumptions P1): the frozen functions on the stable profitable version (`code13/fetch_stable.py`,
`code13/stable_score.py`, results/iter13_stable_score.json).** Pre-registered sample (written before any tape was read):
every BTC 5m window starting in the UTC hours 02, 08, 14, 20 of 09-11..10-11 (1,488 windows, 2.28M taker rows,
fetched in 12 min) plus the same hours of the October BUILD days 10-12..22 as a control (528 windows; tapes on disk).
No refit: frozen R3 presence model and activity baseline (BUILD 10-09..26 fit, so the October control is IN-SAMPLE for
the presence model), R8 public side with the Binance stand-in (no Chainlink history before ~10-01). 41,748 cluster maker
BUY fills.

| fold | windows | presence AUC | activity | gain | public side / fill | cheaper | entry run (public) | return / $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STUDY-stable 09-11..25 | 718 | 0.722 | 0.703 | +0.020 | 0.525 | **0.709** | 0.554 (cheaper 0.591) | +9.3% |
| VALIDATE-stable 09-26..10-11 | 768 | 0.754 | 0.732 | +0.022 | 0.621 | 0.582 | 0.664 (cheaper 0.509) | +7.4% |
| October control 10-12..22 | 528 | 0.815 (in-sample) | 0.776 | +0.039 | 0.666 | 0.452 | 0.679 | +0.6% |

By week from 09-11: public side 0.475, 0.566, 0.594, 0.633, 0.672, 0.623 while the cheaper-token share falls 0.774, 0.634,
0.645, 0.596, 0.500, 0.379 and the return goes 11.2%, 8.3%, 5.6%, 8.7%, 8.4%, -6.7%; presence gain 0.022, 0.020, 0.020,
0.034, 0.027, 0.044 (activity baselines 0.694 -> 0.775). Per wallet within 0.02 in every fold. Active windows 91% in
September (the module was always on), 64% in October.
**Verdict: the assumption panel's hypothesis is falsified in its strong form.** The stable, most profitable version is
LESS decodable by the frozen functions, not more: its fill side follows the cheaper token (0.71 per fill in 09-11..25)
and the posture is at chance there (0.49); the presence gain over activity is +0.02. The Chainlink posture side grows
week by week into October while the return falls. So the strategy changed configuration across September-October: a
profitable underdog-heavy maker (by fill count; favourites by dollars, F2) became a posture-skewed maker. The October
lot is not a degraded copy of a more decodable September; the side is a configuration-dependent by-product (explanation
7), and the September side's only good description is the market-only cheaper-token baseline.

**X139 (mechanics P5): the pairing bid is not posted for every imbalance change (`code13/pairing_process.py`,
results/iter13_pairing_process.json).** 876 changes of a wallet's net position to a new nonzero value (10-31 14:00-16:53,
activity block seconds): an add of exactly |Z| on the under-held side appears within [-3, +10] s of the block second
for 18.7% (placebo |Z| + 0.37: 0.1%); latency median -1.7 s from the block stamp (about 0.3 s after the match), first
add a median 11 c below the own touch (q10 -25 c, q90 0); no dependence on size (17-19%) or wallet (17-21%). When a
tracer exists its size is the wallet's imbalance (X135: 0.78) and it sits on the under-held outcome (0.93), but most
imbalance states get no exact-size pairing bid: the panel's signature (>= 90% within 1.5 s) fails, so the existence of
the pairing order is not a deterministic function of the wallet's imbalance.

**X134 (information I12-5): slow references, a conflict between the lot and the live clock (`code13/slow_ref.py`,
`slow_ref_lag.py`, `post_posture_twap.py`; results/iter13_slow_ref*.json, iter13_post_posture_twap.json).** Lot fills
with >= 20 endpoint grid values in the 60 s before b - 4 (X102 partial: 1,892 fills, 144 windows): STUDY 170 not-decided
fills, 17 disagreements (9 windows): TWAP-60 wins 0.47 (too few). VALIDATE aggregate 1,261 fills: current-report posture
0.615, TWAP-60 0.707, EWMA-30 0.673, EWMA-60 0.678, EWMA-10 0.606; in 275 disagreement fills (27 windows) TWAP-60 wins
0.709 (US 0.72, off-session 0.69, 62/250 0.79, 500 0.81). The win holds against every stamp alignment of the current
report (b - 0 .. b - 10: current 0.54-0.67 vs TWAP-60 0.69-0.76), so it is not a block-clock misalignment. **But on the
live exact clock (10-31 14-18, posts)** the current report wins decisively: quote moves 0.807 vs TWAP-60 0.620 /
EWMA-30 0.623; in 334 disagreement posts (18 windows) TWAP-60 wins 0.24. Not adopted: STUDY cannot confirm it and the
exact-clock sample rejects it; re-test when X102 completes (STUDY coverage) and on the 11-01 / 11-02 development blocks
(dy_rtds records the TWAP-60 topic).

**X130 (I12-1) book race at the decision unit (`code13/post_book.py`, results/iter13_post_book.json).** The Up book just
before each post's price_change message (1,293 posts of filled orders, 10-31 14-18; fit on posts before 16:00, test
after; logistic on standardised inputs): all posts: Chainlink posture sign 0.730, Chainlink-only logistic 0.755, book-only
(microprice - mid, top-of-book and 3-tick depth imbalance) 0.628, both 0.775. Class (i) quote moves (338 test): posture
sign 0.843, Chainlink-only 0.808, book-only 0.657, both 0.831. Class (ii) resting fills (159 test): posture 0.49, book-only
0.717, both 0.742 (microprice coefficient negative: the outcome whose book leans to the sell side is the one swept into the
resting ladder). The book adds about +0.02 to the Chainlink model on the quote moves and carries the class-(ii) fills;
the panel's signature (book term >= +0.10, side >= 0.80 in both sessions) is not met. A side rule with a book term would
have to be stated against a market-only baseline that includes the same book term.

**X138 / X76: per-wallet lag from tracers (`code13/tracer_lag_wallet.py`, results/iter13_tracer_lag_wallet.json).** Peak of
the within-order rank correlation by stamp lag: bosona 1,000 ms (order bootstrap q10-q90 1,000-1,750), mo-money 1,250
(1,000-1,500), almach 2,000 (1,000-2,000), pooled 1,250 (1,000-1,500). Same order as iteration 9 (bosona 1,083, almach
1,432); mo-money is not the slowest, so its posture deficit is not a slower feed. The intervals overlap; with 15-23
orders per wallet no per-wallet parameter is significant.

**X136 step 2: the level-crossing rule fails historically (`code13/level_cross.py`, results/iter13_level_cross.json).** Lot
fills after entry (not decided, cluster position != 0; block clock): predict the under-held outcome when F_CL(u) - h >=
mid(u) - 0.01, else the held one; h chosen on STUDY = 0.15 (edge of the grid, 0.664 vs held 0.690). VALIDATE aggregate:
0.695 per fill (held 0.667, posture 0.645, previous fill 0.932); at the first fill of later runs (1,144): 0.267 (posture
0.557, held 0.218). The rule degenerates to the held outcome; the panel's signature (later runs >= 0.70) fails. With
step 1 (switches are 71% quote moves and the quote moves follow the posture 0.81-0.84 at the post), the historical
failure is the block clock: the post time and the touch at the post are not observable on the lot.

**X142 (assumptions P3): the settlement switches identify the withdrawal rule (`code13/fetch_switch.py`,
`switch_score.py`, `withdraw_time.py`; results/iter13_switch_score.json, iter13_withdraw_time.json).** Pre-registered
sample: BTC 5m windows of the UTC hours 02/08/14/20 of 07-31..08-20 (1,007 windows; regime from each window's own
listing: spot 335, TWAP-30 336, TWAP-60 336; 23,285 cluster maker BUY fills).
- *Withdrawal, with the market as control:* median seconds left at the cluster's last fill per window 45 (spot), 71.5
  (TWAP-30), 101 (TWAP-60); the market's last clean print stays at 1-3 s left in every regime. Over the same sample
  hours the median is 85 s in 09-11..10-11 and 98.5 s in 10-12..22. So the cluster stops filling about 43 s + the
  settlement lookback before the end (43 / 73 / 103 predicted, 45 / 71.5 / 101 observed), and the market does not. The
  dollar share in the last 30 s fell for both (cluster 0.160 / 0.164 / 0.062, market 0.165 / 0.134 / 0.057), so that
  part is market-wide. By day the shift is gradual: 08-07..08 still 42-56 s, 08-10..13 48-95 s, 08-14..16 61-95 s,
  08-17 onward 106-140 s: an operator update within 1-3 days of each listing change, not a same-minute switch.
- *Late fair (fills with 0 < end - ts <= 90 s; Binance-consistent strikes, 1.4 x 300-s vol):* the fill prices are
  closest to the regime's own fair (MAD spot 0.142 in the spot week; TWAP-30 0.172 in the TWAP-30 week; TWAP-60 0.295
  in the TWAP-60 week; best fair per window spot 75% / TWAP-30 37% (spot 44%) / TWAP-60 45%). Since the cluster fills at
  the touch this mostly shows that the market prices the settlement rule. The cluster-specific signal is weak: the
  share of late fills with a positive edge is 0.58 / 0.52 / 0.72 and in the TWAP-60 week it is the same under all three
  fairs (0.716-0.721), so the edge criterion cannot tell the fair forms apart.
- *Verdict:* the withdrawal time is decoded with identification (a listing field, `twapLookbackSeconds`, plus ~43 s,
  adopted by the operator within days); the late-window fair form is not identified beyond the market's own pricing.

**Side per burst start (reporting added to `code/side_sm.py`; `code13/burst_side_lot.py`, results/iter13_burst_side_lot.json).**
Lot, block clock, bursts = consecutive cluster fills of one window on one outcome with block-second gaps < 3 s: public R8
side per burst start 0.539 STUDY (2,525 starts) / 0.637 VALIDATE (7,313) against per fill 0.569 / 0.693; cheaper 0.434 /
0.602; previous fill 0.735 / 0.712. By gap since the previous cluster fill: 3-10 s public 0.529 / 0.653 (previous 0.893 /
0.874), 10-30 s 0.500 / 0.620 (0.769 / 0.737), >= 30 s 0.512 / 0.587 (0.534 / 0.522). Window first bursts 0.619 / 0.725.
`evaluate()` smoke test on the historical VALIDATE hour 10-29 12-13 (`code13/smoke_r8_burst.py`): unchanged per-fill numbers
(680 fills, public 0.678, composite 0.825) plus `per_burst_start` (121 starts: public 0.628, composite 0.785, previous 0.669).

**X141 (assumptions P2): a cohort of entrant makers took a sixth of the maker volume across the boundary
(`code13/fetch_makers_stable.py`, `x141_makers.py`; results/iter13_x141_makers.json).** Maker-row tapes of the stable
sample (1,487 windows, 09-11..10-11; 6.6M rows) + the iteration-12 sample from 10-12 (912 windows; lot VALIDATE days only
as weekly aggregates). Entrants = makers with < 0.2% of maker BUY dollars in 09-11..19 and >= 1% in a later week (17
wallets). Their share of maker BUY dollars near the strike (0.40-0.60) by week from 09-11: 0.7%, 1.6%, 4.9%, 7.6%, 11.1%,
16.2%, 13.9%, 14.6% (tails 0.5% -> 15.5%: the entry is not specific to the strike). The cluster's own share near the
strike 1.9%, 3.0%, 3.1%, 3.6%, 2.5%, 2.1%, 1.8%; its near-strike return held to resolution +12.7%, +9.7%, -13.8%, -3.0%,
+8.4%, -34.2%, -4.8%, (+11.2% partial week). Spearman of entrant share and cluster near-strike return: over 8 weeks
-0.48 (p 0.23), over 719 windows -0.03 (p 0.47); entrants are active before almost every cluster fill from week 1, so the
with/without split is uninformative. Verdict: the competitive entry is real and large (17 new makers, ~15% of maker
volume by October), it coincides with the falling return, but the per-window markout does not depend on their presence;
the panel's signature (window Spearman <= -0.3) fails. Entrants listed in the result file for a follow-up (speed,
quote placement near the touch, signing-time lag to the RTDS publish).

**Match-time book race (`code13/match_book.py`, results/iter13_match_book.json) and a caution.** At the match time (Up book
just before the fill's trade, 10-31 14-18; fit before 16:00, test after, 570 test fills): Chainlink posture sign 0.775,
Chainlink-only 0.768, book-only 0.784 (top-of-book imbalance coefficient +1.41), both 0.782; class (i) 0.84 / 0.831 /
0.846; per wallet (both) momoney 0.72, almach 0.88, bosona 0.77. The book at the match contains the cluster's own resting
order, often the touch itself, so its lean is an own-quote oracle, not market information: not a public side rule. The
post-time race (book before the post, X130) is the valid one, and there the book adds only +0.02.

## Iteration-13 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). R8 stays frozen; no decision changed; `side_sm.py` reports the side per burst start (reporting only,
  smoke-tested). target_metrics unchanged (union presence 0.788 / 0.780; selection 0.685 / 29.5% / 2.87; side 0.693 /
  0.679; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891).
- Paradigm (pivot): the uncensored quote and the decision at its post time. New unit: the re-sign of a uniquely sized
  order (tracer) and the post of every filled order (quote move vs resting rung). New data: tracer chains and post times
  from the full-depth book; 3,500 more windows of tapes from July-October (stable version, settlement switches, maker rows
  across the September -> October boundary); the family settlement-stream recorder (dv_rtds).
- What it showed, in one paragraph: the cluster's quote moves (73% of live fills) follow the latest public Chainlink
  report (posture 0.81 at the post; tracer re-signs peak at a 1.25-s stamp lag, no lead), and the rest of its fills are
  resting rungs that the takers sweep (posture at chance, book lean 0.72). The deep pairing bids are not decoded (no
  law > 0.27 within a tick) and exist for only a fifth of imbalance changes. The withdrawal time is decoded with an
  intervention (about 43 s + twapLookbackSeconds before the end). The profitable stable version (September) is not a
  more decodable version of October: its side followed the cheaper token and its presence gain was +0.02 (+0.026-0.027
  with the R3 class refitted on its own BUILD fold), while 17 entrant makers grew from 1% to ~15% of maker volume and
  the posture-skewed configuration took over. The strict replay with the pairing leg at the tracer depth makes the
  locked pairs profitable (+$225k VALIDATE) but does not raise the window correlation (0.185 < 0.207).
- Closed: X76, X91, X94, X105, X128, X130, X135, X136, X137, X138, X139, X140, X141, X142, X143, X144 (own). Open (32):
  X9, X41, X57, X59, X61, X62, X67, X71, X75, X83, X87, X89, X90, X95, X99, X101-X104, X107, X112, X113, X116, X118,
  X119, X121, X123, X131 (step 1 done), X132, X133, X134 (conflict), X145 (own, new).
- Cache: `.cache/re/directional-maker` at ~1,506 MB after deleting the iteration-13 tapes (re-fetchable with
  `code13/fetch_stable.py` / `fetch_switch.py`, which skip existing files; the HTTP cache holds the responses), the raw
  maker-row files (compacted to `it13/makers_entrants_cluster.parquet`, 266k rows) and two unreferenced iteration-4 spot
  files. The successor should prune ~10-50 MB more if it adds data.

**Next steps (iteration 14; the next development blocks are 11-01 06-12, then 11-01 18-24 and 11-02 00-06).**
1. 11-01 06-12 is an off-session development block with a full-depth recording (`code8/delayed_rawrec.py`, dm_* feeds;
   check that its disk cap of 280 MB over all dm_* files does not stop it early): replicate X135 (tracer lag and laws),
   X136 step 1 (post classes) and the post-time posture (0.81 on quote moves?) on the 62/250 ladder. Freeze the post-time
   decomposition before reading it.
2. Mo-money's stale-rung test (X91 follow-up): for class-(ii) fills, the time since the last posture flip at the post
   and at the fill, and per-wallet cancel latency from the raw book; the book term (X144) adds only ~1 point once the
   filled order is removed, so do not build the side on it.
3. X131: check `dv_rtds` per symbol at 06:00 (development); score the posture side per family on `dw_clob` with it;
   compute per-block scope of the family universe.
4. X134: when X102 completes (~10:00) re-run `code13/slow_ref.py` (STUDY coverage) and the live TWAP-60 race on 06-12.
5. X145: schedule a full-depth recorder (new feed prefix, every size delta within 0.15 of the touch, hard stop, < 300 MB)
   for 11-01 18-24 and 11-02 00-06.
6. X141 follow-up: who are the 17 entrants (signing-time lag to the RTDS publish from calldata; placement at the touch);
   X132 (ms clock of burst starts with futures aggTrades) and X133 (aggregate delta) remain open.

**X144 step 0: the match-time book lean is the cluster's own order (`code13/match_book.py --exclude-own`,
results/iter13_match_book_exown.json).** Removing only the filled order's own size from its level before computing the
book features: book-only falls from 0.784 to 0.663 on the test half (class (i) 0.831 -> 0.725, class (ii) 0.742 -> 0.566);
Chainlink + book 0.784 vs Chainlink-only 0.770 (+0.014). Most of the raw match-time book signal was the cluster's own
resting order; what is left adds about one point to the posture.

**X91 / X94: mo-money's posture deficit is in its resting-rung fills, not its quote moves (`code13/wallet_class.py`,
results/iter13_wallet_class.json).** Posture at the post time (stamp lag 1,000 ms, the best lag for all three wallets on
this measure): class (i) quote moves momoney 0.842, almach 0.893, bosona 0.892 (shares of class (i) 0.71 / 0.75 / 0.72);
class (ii) resting fills momoney **0.301**, almach 0.622, bosona 0.595 (mostly 500 schedule rungs 2 c below the touch:
momoney 124 schedule + 9 pairing). So mo-money's resting 500s are filled on the anti-posture outcome 70% of the time,
twice as often as the other wallets'. Lead for iteration 14: are they stale rungs it fails to cancel after a posture flip
(time since the last flip at post vs fill; cancel latency per wallet from the raw book)?

**X91 follow-up: mo-money's anti-posture resting rungs are placed, not stale (`code13/stale_rungs.py`,
results/iter13_stale_rungs.json).** Class-(ii) fills by the posture at the post and at the fill (stamp lag 1,000 ms; the
mid at the fill implied by the order being at the touch): posted with the posture and filled after a flip (stale) momoney
7.5%, almach 7.2%, bosona 4.5%; **posted against the posture and still against at the fill: momoney 40.6%, almach 13.5%,
bosona 18.9%**; posted against and filled once the posture moved in their favour 22-29% for all three. Class (i) is alike
across wallets (with the posture throughout 0.77 / 0.85 / 0.84). So mo-money keeps resting 500 rungs about 2 c below the
touch on the anti-posture outcome two to three times as often as the other wallets, and takers sweep them: a ladder
placement difference, not a slower cancel or a different reference.

**X128 (own): the opening 500 ladder is two-sided (`code13/entry_ladder.py`, results/iter13_entry_ladder.json).** BTC 5m
windows of 10-31 14:00-16:50 (24): exact 500/1000 adds within 0.20 of the touch in the first 30 s split evenly between
the outcomes (dominant share median 0.54, no window >= 0.9); in the 10 s before the window's first cluster fill also even
(median 0.56; 17 windows) and the outcome with more adds is the first fill's outcome in only 5 of 15. Caveat: exact-500
adds include other makers' orders. The entry is not a one-sided opening ladder; which outcome fills first is decided by
which ladder reaches the touch (the class-(i) quote moves follow the posture 0.81-0.89).

**X137 (mechanics P3): the pairing leg at the tracer depth (`code13/replay_pair_depth.py`, results/iter13_replay_pair_depth.json).**
The iteration-12 full-machine strict replay (lot BTC 5m, L = 2 s, slack 2, trade-through) with the pairing bid at last
clean print - 0.01 - depth. Main = posture, VALIDATE aggregate (STUDY in brackets): no pairing (R7's replay) window corr
0.207 / 0.218 [0.033 / 0.070], PnL -$216k; pairing at the market (depth 0, iteration 12) -0.016 / -0.002, PnL -$466k,
locked -$106k; depth 0.05: 0.147 / 0.123, locked +$135k; **depth 0.11 (tracer median): 0.185 / 0.191, PnL -$341k, locked
+$225k [+$111k]** (cluster: PnL +$23.7k, locked +$38.1k). Main = held: depth 0.11 0.127 / 0.166. The tracer depth turns
the replay's locked pairs from a loss into a gain on both halves (the panel's first signature holds), but the window
correlation stays below the one-sided replay (0.185 vs 0.207) and the total PnL stays far negative: the missing piece of
the outcome is the main rung's execution (queue position and the sub-second re-pricing), not the pairing price.

**Historical replication of the fill classes on the lot (`code13/sweep_lot.py`, results/iter13_sweep_lot.json).** Proxy for
class (ii) on the block clock: a cluster fill whose transaction also fills another maker at a strictly better Up-book
price on the same side (the taker swept through a better level first). Sweep share 12.8% STUDY / 8.6% VALIDATE. Public R8
side on top fills 0.586 / 0.711 vs sweep fills 0.455 / 0.501 (cheaper 0.50 / 0.70 vs 0.38 / 0.45); the same contrast in
every wallet. So on the lot too the swept resting rungs are at chance while the top-of-book fills carry the posture; the
remaining gap of the top fills (0.71 vs 0.81-0.84 live) is the block clock.

**X140 limitation (for the auditors).** The stable-version test scored the FROZEN October functions; the panel's refit design
(BUILD 08-14..09-10 for a stable-version presence model and side rule, STUDY 09-11..25, VALIDATE 09-26..10-11) was not run,
so "less decodable" means "less decodable by the October rule". A refit needs taker tapes for 08-14..09-10 (same
pre-registered hours; `code13/fetch_stable.py` with other dates, ~10 min) and the R3 feature build on them; the
cheaper-token share (0.71 per fill in 09-11..25, 0.77 in its first week) is the first candidate side rule for that
version.

**Tool bug (not polyrea; reported, not fixed): `research/reverse_engineering/tools/live.py` `iter_live`** catches `EOFError`
and `OSError` but not `zlib.error`: `.cache/live/dev/dm_clob_raw/20261031T14.jsonl.gz` raises "Error -3 ... invalid block
type" part-way and aborts any iterator spanning that hour (confirmed this iteration; the code13 readers wrap each hour and
catch `zlib.error`, so 14:00 is read up to the corrupt block).

**X140 refit, the panel's pre-registered folds (`code13/fetch_stable_build.py`, `code13/stable_refit.py`,
results/iter13_stable_refit.json).** BUILD-stable 08-14..09-10 (1,313 windows of the same hours, 2.39M taker rows) -> the
R3 model class (final_rule FEATS rule / activity, train2 PARAMS, 300 rounds) refitted there: STUDY-stable 0.721 vs
activity 0.695 (gain +0.026), VALIDATE-stable 0.731 vs 0.704 (+0.027); the frozen October model on the same panels
0.722 / 0.703 and 0.754 / 0.732. Per wallet 0.714-0.735 vs 0.689-0.707. Bin-level side of the refitted score 0.639 /
0.589 (activity 0.571 / 0.554), i.e. mostly the cheaper token (favourite at the last print 0.36 / 0.46). So with its
own fit the stable version is exactly as (un)decodable as October by this model class (gain +0.03): the panel's "if
false" branch holds, over 15 weeks of the most profitable configuration. The fill-level presence gap is intrinsic to a
two-sided maker whose fills are joint outcomes with the takers, not a by-product of the October regime.

Recorders at 05:02 UTC: rtdsfam (dv_rtds) writing (pid 25172), examrec / rtdsstream / rtdsbn / famrec running, the
X102 endpoint fetcher running, the delayed full-depth recorder waiting for 05:55; shared live.py running (not touched).
(Iteration 13 ended 2026-11-01 05:06 UTC, about 86 minutes.)

## Iteration 14 (started 2026-11-01 05:33 UTC; 888 of 1,200 minutes used)

PIVOT REQUIRED (progress < 0.02 over two iterations). Paradigm of this iteration: **the quote as a lagged
partial-adjustment process on the fast reference, decided per post (the uncensored quote unit: every cluster-class post
at the touch, filled or not) and scored at the millisecond**, instead of the posture level per fill. New model class (a
two-regime pricer: Chainlink report level + under-reaction to the Binance USD-M move since that report), new unit (the
post, not the fill), new input on the lot (the futures move before each fill on the historical match clock).

Competing explanations of the money (what tells them apart):
- H1 lagged-quote liquidity provider: ladders hang off the mid with a Chainlink skew, re-priced on each report, and
  under-react to the fast reference between reports; uninformed mint takers pay the spread, fast pick-offs take some
  back. Tell-tale: the side of BOTH fill classes is a public function of the futures move before the post (quote moves on
  the outcome that fell, resting rungs on the outcome that rose), and it holds on unfilled posts too.
- H2 informed settlement-source skew: the profit is the Chainlink-vs-Binance disagreement (settlement is the Chainlink
  TWAP). Tell-tale: PnL concentrated where report and market disagree; side = posture at the post; dies in noise regimes.
- H3 taker-population harvest: a specific taker population (round-USD UI favourite buyers via mints) pays; the cluster's
  own decisions matter little. Tell-tale: one population carries most PnL and its share tracks the weekly return.
- H4 queue-priority / latency rent: first at the touch within 0.1-1 s; each order serves one taker batch and is
  cancelled (mechanics P4); slower copies get only trade-throughs. Tell-tale: one-batch life cycle; a batch-capped
  replay earns more than a trade-through replay.
- H5 rebates and rewards: post-October profit is mostly maker rebates and liquidity rewards (500 rungs >= rewardsMinSize
  50 within 4.5 c). Tell-tale: rebate+reward share of net PnL; eligible resting depth tracks the reward rows.
- H6 risk-managed module switching: a drawdown controller with manual re-enables keeps it out of losing regimes.
  Tell-tale: switch-offs at a stable drawdown threshold (mechanics P2).
- H7 (unlikely) private / faster reference: decisions lead the public relay. Tell-tale: posts before the RTDS publish
  (tracers: 1.25-s stamp lag, no lead; disfavoured).
This iteration discriminates H1 against the residual "class (ii) = takers' choice" of H2 (T1-T4), and does the scope
bookkeeping for the exam lot (T5, assumptions P1).

Pre-registered tests (written 05:40 UTC 11-01, before any record of the 11-01 06-12 block exists):
- T1 quote unit (mechanics P1 step 1): every schedule-size add (dz in {62, 250, 500, 1000}) at the touch at its server
  ms (Up bid sd 1 with p = bb; Up ask sd 0 with p = ba), BTC 5m/15m, 10-31 14:00-18:00. Label = Up iff sd 1.
  Predictors at the post t: M_W = outcome that fell over [t - W, t - 50 ms] on the Binance USD-M bookTicker mid
  (W 0.5 / 1 / 2 s); P = posture sign(F_CL(t - 1.25 s; k x sigma_fut300) - Up mid at t); C = M_W where |move| >= theta,
  else P. Market-only baselines: the outcome whose Polymarket Up mid fell over the same window; the token just sold.
  Fit (W, theta, k) on 14:00-16:00, test on 16:00-18:00, then frozen on 11-01 06:00-07:00 (whatever is recorded).
- T2 per fill (assumptions P3, mechanics P1 step 3): the 1,406 filled orders (it13/fills_posts); rule at the MATCH ms:
  the outcome the futures move went against over [match - D, match) where |move| >= theta, else the posture at the match;
  fit (D, theta) on 14-16, test 16-18, per class. Diagnostic only (class labels): class (i) -> fell, class (ii) -> rose
  at the post.
- T3 (information I13-1): class-(ii) posture with sigma = k x futures-mid sigma over 60 / 300 / 900 / 3,600 s, k 0.5-2.5,
  fit on class (ii) 14-16, test 16-18; class (i) must stay >= 0.80.
- T4 lot (VALIDATE aggregate, STUDY case by case): the frozen T2 rule on the historical match clock (taker signing ms +
  620 ms, X97) with 1-s futures (fut1s): the move over the 2 s before the match second; adopt as R9-side only if it beats
  R8's public side (0.693 VALIDATE per fill) and the cheaper / tape-momentum baselines.
- T5 scope (assumptions P1 steps 1-2): fill and |PnL| shares per crypto family and R8's coverage on the pre-registered
  weekend analogs (Saturday 06-12: 10-24, 10-17, 10-10; Saturday 18-24: the same days; Saturday-Sunday 00-06: 10-25,
  10-18, 10-11 and 10-31 00-06), from activity only.
- T6 = X147 (information I13-2, pre-registered 05:58 UTC before running): fill presence at event time. Unit (BTC 5m or
  15m window, outcome, 1-s bin) on the match clock (first server ms of the fill's transaction in the CLOB trade stream),
  label = cluster maker BUY fill; features strictly before T (activity: clean print counts and shares sold/bought on s
  over 1/2/5/10/30 s, last clean print and age, last hit side, the book mid; reference: Chainlink posture edge at
  T - 1.25 s with 1.4 x futures sigma300, its 1-s change, new-report flag, futures move toward s over 1/3 s, futures
  digital edge). Fit 10-31 14:00-16:00, test 16:00-18:00, LightGBM 7 leaves 200 rounds; gain = activity+ref minus
  activity on the same unit; the same scores at 10-s bin starts reported for the unit comparison (`code14/pres_event.py`).

### Iteration 14 results so far (05:55 UTC)

**T1 (mechanics P1 step 1, X146): on the uncensored quote unit the "fell" law is reversed; it is fill selection
(`code14/lagged_quote.py`, results/iter14_lagged_quote_1793455200_1793469600.json).** 2,411 (fit 14-16) and 3,673 (test
16-18) schedule-size posts at the touch (500/1000: 2,273 / 3,315). Posture at the post (k 1.4, futures sigma300):
0.756 fit / 0.721 test (500s 0.762 / 0.750). Only 3-13% of posts follow a futures move of >= $0.5-5 over 0.5-2 s, and
on those the rule "post on the outcome that fell" scores **0.09-0.47** (test W 0.5 s, $2: 0.164, n 152; W 1 s, $2:
0.245): the engine re-posts at the touch on the outcome that ROSE (it follows the moving mid), the opposite of the
filled class-(i) orders (fell 0.90-1.00 on the same block, T2). Polymarket-mid "fell" 0.32-0.44 likewise; the token just
sold 0.49-0.51. Combined (rose-rule where moving, else posture) adds at most +0.012. So the panel's "one lagged-quote
law" fails on unfilled posts: the takers' momentum selects which at-touch posts fill (the "if false" branch). The
uncensored quote's side is the Chainlink posture at 0.72-0.76 per post, and the fills are posture-enriched (0.82-0.86
per filled order) because takers fill the posture-side posts more often.

**T2 (assumptions P3, X148): the futures move adds nothing to the posture per fill.** Per filled order at the match
(n 799 fit / 498 test): posture at the match 0.855 / 0.815; "outcome the futures move went against" where |move| >=
theta over [match - D, match - 50 ms], else posture: best on fit W 0.5 s (0.855), test 0.825 (+0.010). By class at the
POST: class (i) fell 0.90-1.00 (n 16-79 moving posts), class (ii) rose (fell 0.13-0.25 fit; 0.0-0.58 test, n 4-12).
At the FILL the class-(ii) posture is 0.852 / 0.755 (at the post 0.663 / 0.572): the market's move into the rung is in the
fill-time mid. No class-free public rule at the fill beats the posture.

**T3 (information I13-1, X149): the class-(ii) volatility scale is not identifiable (fails out of sample).** Grid
lookback 60/300/900/3600 s x k 0.5-2.5 on futures-mid sigma: best on fit class (ii) L900 k0.7 = 0.760 -> test 0.541;
L900 k1.4 = 0.505 fit -> 0.742 test. Class (i) stays 0.76-0.85 for k 0.7-1.4. The class-(ii) side flips with the scale
because its fair sits near the mid; no single source/scale holds across the halves (I13-1 signature not met).

**T5 (assumptions P1 steps 1-2, X151): R8's universe fails scope in the most recent weekend analogs
(results/iter9_scope.json blocks; trade-count / dollar shares, |PnL| not available there).** U1 = BTC 5m + 15m:
Sat 06-12: 10-24 0.00/0.00, 10-17 0.87/0.94, 10-10 0.83/0.90; Sat 18-24: 0.53/0.52, 0.60/0.76, 0.82/0.91; Sun 00-06:
10-25 0.00/0.00, 10-18 0.43/0.59, 10-11 0.83/0.83, 10-31 00-06 0.91/0.95; Sun 12-18: 0.72/0.66, 0.53/0.52, 0.84/0.90.
U4 (+ BTC hourly/daily/4h + ETH): 10-24/25 blocks 0.58/0.85, 0.78/0.86, 0.56/0.81, 0.92/0.95; U5 (every crypto
Up/Down family) 1.00 in every analog. In the most recent weekend (10-24/25) the cluster was nearly idle in two of four
blocks (371 and 394 trades, $6.9k / $6.4k) and BTC 5m + 15m carried none of it. A frozen rule for the sealed future
blocks (Saturday 06-12, Saturday 18-24, Sunday 00-06, Sunday 12-18) must cover every crypto family.

**T6 (information I13-2, X147): event-time presence keeps the same gain (`code14/pres_event.py`,
results/iter14_pres_event_1793455200_1793469600.json).** 45,658 (window, outcome, 1-s) cells, 52 windows, positive
rate 1.1% (test 230 positives). Test AUC activity 0.774 (5m 0.691, 15m 0.769), activity + reference 0.805 (5m 0.736,
15m 0.798; Chainlink-only reference 0.805, 15m 0.810): gain +0.031 (20-min block bootstrap [+0.006, +0.044]); top gains
n10, edge_cl, edge_fut. The same 1-s scores at 10-s bin starts: 0.748 activity vs 0.728 reference (the 1-s model is not
a 10-s forecaster). Finer timing raises both the rule and the activity baseline; the gain stays at +0.03 to +0.045 per
family (I13-2 signature not met: not >= 0.85 with >= 0.05).

**P2 of the assumptions panel (X150): quote-geometry print selection fails (`code14/sel_geometry.py`,
results/iter14_sel_geometry_1793455200_1793469600.json).** 23,672 fit / 38,204 test clean prints (base 1.5%). Cluster
fills by d = last clean print on the hit token - print price: d 1 48%, d 0 22%, d 2-3 11%, d < 0 12%. The fixed score
(posture side at t - 1.25 s for d in {0, 1}, c for d in {2, 3}, c fitted = 0): AUC 0.558 (within-window 0.583), no
threshold with lift >= 3, lift 1.25 at recall 0.5. Activity-only LightGBM 0.683 (0.705), recall 0.20 at lift 3;
activity + posture + d 0.742 (0.762), recall 0.42 at lift 3, lift 2.74 at recall 0.5 (gain +0.059 over activity on this
unit). A first version of the metric credited arbitrary orders inside tied scores (recall 0.57 at lift 3.27); fixed by
evaluating thresholds only at tie-group ends. Selection route: public 0.74-0.76 vs the oracle 0.81-0.83 (X72); not
reached.

**T1 re-run with new price levels included (`code14/qu_oos.py` on 10-31 14-18; results/iter14_qu_oos_1793455200_1793469600.json).**
The it13 `sched_adds` table skipped adds at price levels not seen since the last book snapshot (tracers.py `old is None:
continue`), which drops part of the improving posts. Rebuilt from dm_clob_raw with them: 6,200 schedule-size posts at the
touch (500 5,539; 62 326; 250 198; 1000 137): posture 0.733; moving moments (3.8% / 6.2% of posts, $2 over 0.5 / 1 s):
"fell" 0.180 / 0.284, "rose" 0.820 / 0.716, posture there 0.545 / 0.589; rose-else-posture 0.743; Polymarket mid fell
0.356; bid hit by the last print 0.498. **By size: 500/1000 0.753, 62/250 0.509 (n 521): the off-session sizes at the touch
carry no posture.** By pass multiplicity 0.720 / 0.753 / 0.734 (singles / pairs / triplets).

**X153 (mechanics P3) on the quote unit: no triplet advantage (`code14/triplets_qu.py`, results/iter14_triplets_qu.json).**
it13 quote unit: singles / pairs / triplets 0.706 / 0.785 / 0.804 on 14-16 but 0.738 / 0.729 / 0.675 on 16-18 (and 0.720 /
0.753 / 0.734 on the rebuilt unit). The per-fill triplet advantage of the panel (0.876 vs 0.751) is fill selection, like
the "fell" signature. Signature (triplets >= 0.85 on the quote unit) not met.

**X154 (mechanics P4 step 2): the one-batch life cycle raises the replay's return, not its correlation
(`code14/replay_batch.py`, results/iter14_replay_batch.json).** Lot BTC 5m, L 2 s, slack 2, posture side, last clean
print - 0.01, session size; per decision second the quote fills at most the first reaching print ("batch1") instead of
the second's through-volume ("sum", = iteration 11, reproduced exactly 0.2066 / 0.2181). VALIDATE (aggregate): strict
posture sum 0.207 / 0.218, return -16.6%; **batch1 0.213 / 0.214, return -10.7%**; at-touch sum 0.222 / 0.226 (-12.8%),
batch1 0.228 / 0.222 (-6.2%). Oracle window side: strict sum 0.473 / 0.527, batch1 0.472 / 0.530; at-touch batch1 0.475 /
0.532. STUDY: posture 0.033 / 0.070 -> 0.095 / 0.108 (return -15.2% -> -10.2%), oracle 0.505 / 0.637 -> 0.517 / 0.639.
The first signature (return +5 points) holds; the second (oracle ceiling > 0.53) does not: one batch per order removes
part of the adverse tail but the window-PnL ceiling of a public-tape replay stays ~0.47-0.53. R8's executable outcome
is unchanged (0.207 / 0.218 kept as the reported metric; batch1 reported beside it).

**X159 (assumptions P4): who paid the profitable version (`code14/who_paid.py`, results/iter14_who_paid.json).** The
pre-registered stable sample (hours 02/08/14/20, re-fetched from the HTTP cache) + the October control: 34,410 cluster
maker BUY fills in 1,346 windows, 99.8% joined to their transaction's taker. September stable (09-11..10-11): +8.3% per $
($52.7k): rest 53% of shares / 42% of PnL (+6.6%), round-USD takers 23% / 26% (+9.2%), the top-20 September
counterparties 23% / 31% (+11.4%). October control (10-12..22): +0.6% ($1.2k): rest 62% (+4.1%, +$4.9k), round-USD 27%
(**-11.2%, -$6.0k**), top-20 9% (+3.2%). The top-20's share of the cluster's fills fell 63% (their market-wide taker
share 17% -> 11%); the round-USD population kept its market share (24-28%) but the cluster's side against it moved from
the cheaper token (0.70 of fills) to the favourite (cheaper 0.49), and that flow turned from +9% to -11%. Weekly Spearman
of the cluster's return with the population shares: round-USD -0.6, top-20 +0.6 (6 weeks). Signature (one population >=
60% of September PnL) not met: the September profit was spread over all three populations and came from buying the
cheaper token below its probability; the October loss is the cluster's own side change against unchanged retail flow
plus the exit of its best counterparties.

- T7 = X152 (mechanics P2, light form; pre-registered 06:07 UTC before computing): module switch-offs as a drawdown trip.
  Events: BTC 5m (and separately BTC 15m) off-runs of >= 60 min (no cluster trade in >= 12 consecutive 5m windows / 4 15m
  windows) after an active window, development periods 10-08..10-31 (VALIDATE 10-27..30 as aggregates only). At-risk
  points: every window start whose previous window was active. Measures at the point (own state, reported, never
  counted): cluster PnL over every market it traded, each window booked at its end (cash flows of TRADE, MERGE, REDEEM;
  non-parsable slugs booked at their last row), M1 drawdown from the running peak since the day's 01:00 UTC restart,
  M2 its level, M3 drawdown since the start of the current on-run (the last re-enable), M4 that level. Public
  comparison: the calendar gate (Fri-Sun 18:00 ET to 09:00 ET). Report the AUC per fold and the switch-off rate above /
  below the BUILD median of each measure at the BUILD switch-offs (`code14/trip.py`).

**T7 = X152 (mechanics P2, light form): the switch-offs follow drawdowns but at no fixed threshold
(`code14/trip.py`, results/iter14_trip.json).** BTC 5m: 7 off-runs >= 60 min in the development periods 10-08..10-31
(BUILD 3, STUDY 2, VALIDATE 1 (aggregate), live 1) among 4,802 at-risk window starts. AUC of the drawdown since the day's
01:00 UTC restart (M1): BUILD 0.875, STUDY 0.822, VALIDATE 0.927, live 0.73; since the last re-enable (M3) 0.565 /
0.889 / 0.960 / 0.922; the calendar gate 0.726 / 0.629 / 0.49 / 0.20. Values at the switch-offs (BUILD, STUDY, live): M1
$14.3k, $14.6k, $2.2k, $7.7k, $1.1k, $3.8k; day level -$8.4k, -$8.7k, +$1.0k, -$7.6k, +$2.5k, -$0.2k; M3 $0.06k-$2.3k:
no stable trip level (CV >> 0.25; the panel's signature fails), and only 7 events. Two kinds are visible: switch-offs at
~18:15-18:30 ET on weekend evenings at a positive or small drawdown (Sat 10-17 22:30, Sun 10-18 22:15, Sat 10-24 22:30;
scheduled-looking) and earlier ones after large losses (Sat 10-17 20:35 = 16:35 ET at -$8.4k; Fri 10-23 20:40 at
-$7.6k; Sat 10-31 16:55 = 12:55 ET at the day's low). BTC 15m (25 events): M1 AUC 0.547 / 0.797 / 0.53, gate 0.789 /
0.541 / 0.485. Description (own state, reported): an operator who turns BTC 5m off for weekend nights and, ad hoc, after
a losing stretch; not an automatic drawdown trip.

**X156 step 1 (information I13-3): GMX v2 on Arbitrum carries the settlement stream's BTC value, but sparsely
(`code14/gmx_probe.py` + inline probe, results/iter14_gmx_probe.json).** Endpoints: arbitrum-one-rpc.publicnode.com
refuses eth_getLogs on day-old blocks (HTTP 403 "Archive requests require a personal token"); arbitrum.drpc.org refuses
(HTTP 400 "ranges over 10000 blocks are not supported on free plan"); **arb1.arbitrum.io/rpc works**. EventEmitter
0xc8ee91a5... logs with eventName "OraclePriceUpdate" over 2,400 blocks (10-31 15:00-15:10 UTC, development): 99 updates
(WETH 53, USDC 29, ...), BTC index token 0x47904963... 3 and WBTC 0x2f2a2543... 3, provider 0x7ba7ae61... (the
Data Streams provider). Their (min + max) / 2 equals the RTDS Chainlink value of the same stamp to the cent for 4 of 6
(77,336.94 / 77,336.94; 77,308.20 / 77,308.20) and +$1.12 for the other 2. So the on-chain GMX report IS the settlement
stream's value, recoverable for any past date; but only ~3 distinct BTC stamps per 10 minutes (on a Saturday), far too
sparse to replace the 1-s reference at fill times. Usable as basis anchors for the September stand-in (step 2, not run).

**Quote unit and own inventory (own state, reported; `code14/qu_inventory.py`, results/iter14_qu_inventory.json).** For the
at-touch posts of 10-31 14-18: post on the outcome the cluster holds more of 0.570 (14-16) / 0.409 (16-18); flat before
the post 26% / 67%; where posture and inventory disagree the posture wins 0.693 / 0.819. The uncensored quote's side is
the Chainlink posture (0.72-0.76; 0.80 / 0.73 when flat), not an inventory rule.

**Family composition of the weekend analog blocks (activity; STUDY days case by case).** Sat 10-24 06-12 (340 buys,
$6.9k): BTC 4h 32% of $, BTC hourly 16%, BTC daily 12%, ETH 15m 11%, ETH daily 7%, ETH hourly 6%, XRP 5m 3%, BNB hourly 3%;
schedule sizes (62/250/500/12/100/1000) in 0-9% of buys. Sun 10-25 00-06 (364 buys, $6.4k): BTC 4h 51%, BTC hourly 14%,
ETH 15m 7%, XRP 5m 7%, BNB hourly 4%. Sat 10-24 18-24: BTC 5m 28%, BTC 15m 24%, BTC 4h 8%, ETH daily 7%. Sun 10-25 12-18:
BTC 5m 48%, BTC 4h 21%, BTC 15m 16%. Sat 10-31 00-06: BTC 15m 51%, BTC 5m 45%. With BTC 5m and 15m off, the cluster
runs small, non-schedule-size orders across ~10 longer-horizon and non-BTC families: a family-general R9 would be scored
on a few hundred fills per block spread over ~10 families.

**X155 (mechanics P5): pairing bids on persisting imbalance states (`code14/pairing_persist.py`,
results/iter14_pairing_persist.json; adds at new price levels included).** 876 imbalance changes (10-31 14:00-16:54):
exact-|Z| bid on the under-held outcome within 10 s 0.188 (placebo 0.001); states persisting >= 2 / 3 / 5 block seconds
0.210 / 0.220 / 0.221 (placebo <= 0.002). The one-fifth rate is not a transient-state artefact (signature >= 0.80
fails): the pairing bid is a sometimes-on module, not a deterministic own-state rule.

**Operational event (A8) found while preparing the 11-01 06-12 replication: no BTC/ETH 5m-15m windows are listed for
11-01 ~05:00-06:59 UTC (the US DST fall-back hour).** Gamma `markets?slug=` and `markets/slug/` return nothing for the
current windows (btc-updown-5m-1793513400 / -1793513700, btc-updown-15m-1793512800: 404), while windows from
1793516400 (11-01 07:00) on exist (created 10-31 07:07). My CLOB recorders found no tokens since about 04:20 UTC
(delayed_rawrec has no dm_clob_raw feed yet; examrec dx_clob and famrec dw_clob stalled; famrec running: []); they look
up the current window by slug and should resume at 07:00. The cluster's 06:00-06:16 activity (bosona) is ETH and BTC
daily trades only. The pre-registered T1 out-of-sample run on 11-01 06:00-07:00 is therefore impossible (no BTC 5m/15m
book exists); it moves to the next development block with books. The shared recorder (tools/live.py status 06:13 UTC):
clob_crypto connected with 6 tokens, rtds msgs 7,518 but written 0 (reported, not touched).

**X133 (information I12-4; own state, reported): the entry side does not hedge the aggregate BTC exposure
(`code14/agg_delta.py`, results/iter14_agg_delta.json).** For each BTC 5m window's first cluster BUY (entry), the net Up -
Down shares across the cluster's other open BTC 5m/15m/4h windows: entry on the offsetting outcome 0.455 (BUILD, 2,618
entries with |exposure| >= 10), 0.484 (STUDY, 508), 0.486 (VALIDATE aggregate, 843); with |exposure| >= 500: 0.436 /
0.517 / 0.458. No cross-window hedge (with the assumptions panel's N1, nested 5m/15m net-share correlation +0.07); the
slight lean to the same side (0.51-0.55) fits one reference driving all windows.

**Quote-unit posture parameters: the uncensored quote's side is decoded at 0.81 out of sample within the block
(`code14/qu_scan.py`, results/iter14_qu_scan_1793455200_1793469600.json).** Rebuilt at-touch 500/1000 posts of 10-31
14-18 (5,610 scored). Grid Chainlink stamp lag L 250-3,000 ms x k 0.7-2.0 (futures-mid sigma300), chosen on 14-16:
**L 1,000 ms, k 1.0: fit 0.815, test 0.811** (L 750 / k 1.0: 0.813 / 0.816; the R8-form L 1,250 / k 1.4: 0.761 / 0.749;
L 3,000: 0.635 / 0.591). With the frozen best, accuracy rises with |F - mid| only at the top (|edge| >= 0.1: 0.836, 44% of
posts; 0.02-0.1: 0.68-0.70; < 0.02: 0.59-0.72) and fails in the last minute (0-60 s left: 0.491; 60-900 s: 0.68-0.80). A
stamp lag of ~1.0 s at the post is what "use the report just published" means here (publish ~1.08 s after the stamp,
re-price pass 0-150 ms later; L 1,250 misses the newest report for posts in the first 0.25 s after a publish): no lead
over the public relay. Per filled order (`code14/fill_lag.py`, results/iter14_fill_lag.json) the same parameters lift
the class-(i) posts at the post (fit 0.877 / test 0.870 vs 0.786 / 0.844) but the match-clock posture keeps its R8 form
(L 1,250 / k 1.4: 0.855 / 0.815 vs L 1,000 / k 1.0: 0.817 / 0.781): the fills are judged at the match, the quote at the
post.

**Examinable form (`code14/qu_dx.py`; wired into `evaluate()` as the reported block `quote_unit_side`).** From the exam
recorder dx_clob ('pc' deltas with the record's touch), dx_bnf (else dm_bnf) futures sigma, Chainlink from cl_source and
the Gamma strike, frozen L 1,000 ms / k 1.0: 10-31 15:53-18:00 (dx_clob coverage) **0.804** (n 2,575; BTC 5m 0.788,
BTC 15m 0.832) against always-Up 0.506, cheaper 0.439 and "the outcome whose mid rose over 1 s" 0.648 (n 1,256 moving
posts); 15:53-16:54 windows only 0.816 (n 2,068). Caveats: exact 500/1000 adds include other makers' orders (~12%,
X36); the unit is the post, not the wallet; dx_clob covers the sealed blocks 10-31 18-24 and 11-01 00-~04:20 (BTC 5m
off from 16:53:54; the recorders found no windows in the 05:00-06:59 listing gap); parameters chosen on 14-16 of the
same day, so a second development block is still needed (X160).

**Quote-unit slices under the frozen quote posture (L 1.0 s, k 1.0; `code14/qu_slices.py`, results/iter14_qu_slices.json).**
500/1000 posts 0.812 (n 5,610); 62/250 posts 0.534 (n 521; the favourite 0.624); 500 posts in the last 60 s 0.681 (n 574,
92% in decided windows), where the favourite scores 0.92. A decided-window favourite branch does not help overall
(fit 0.818 vs 0.815, test 0.802 vs 0.811; on decided windows posture 0.59-0.68, favourite 0.62-0.63): not adopted. The
deep loser bids that fill in decided windows (R8's cheaper branch on fills) are not the at-touch quote, which sits on the
favourite near the end.

**Smoke test of `evaluate()` with the new block (10-31 16:00-17:00, development; results/iter14_eval_r8_1793462400_1793466000.json).**
quote_unit_side 0.816 (n 1,937; first half 0.799, second 0.851; BTC 5m 0.789, BTC 15m 0.867; always-Up 0.473, cheaper
0.445, mid-rose 0.634); per-fill match-clock side 0.768 (n 678; Binance 0.515, cheaper 0.537, always-Up 0.563); BTC 5m
presence 0.633 vs activity 0.668 (this is the noisy hour before the 16:53 switch-off), union 0.724 vs 0.742; R7 price
union 0.773; scope BTC 5m + 15m 0.979 of trades / 0.986 of dollars. Runs end to end in ~3 minutes.

## Iteration-14 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). R8 stays frozen; no frozen decision changed; one reported block added (`quote_unit_side`, the side
  of the uncensored quote from the exam recorder). target_metrics unchanged (union presence 0.788 / 0.780; selection
  0.685 / 29.5% / 2.87; side 0.693 / 0.679; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891).
- Paradigm (pivot): the uncensored quote unit (every at-touch post, filled or not) and event time (1-s match clock) in
  place of fills in 10-s bins; the side as a lagged pricer; selection by quote geometry; the order life cycle in the
  replay; plus the exam-lot scope, the switch-off controller, who paid the profitable version and a new on-chain source.
- What it showed (corrected 06:44, see CORRECTION below): the engine's at-touch quote follows the Chainlink posture
  computed from the latest published report (sigma 1.0 x futures sigma300) at 0.83 per post on the 30 minutes with exact
  publish times and 0.75-0.76 with a point-in-time-safe fixed lag (the 1.0-s stamp lag's 0.81 is not strictly point in
  time); the 62/250 posts do not; the fills are the takers' selection of those posts (match-clock
  per-fill side 0.77-0.86, with the "fell" signature and the triplet advantage both fill selection). Event-time presence
  keeps the +0.03 gain, for fills and (point-in-time safe) for posts alike; quote-geometry selection fails; one-batch-per-order fills raise a replay's return, not its
  correlation; switch-offs follow drawdowns at no fixed level; R8's universe fails scope on the latest weekend analogs.
- Closed: X132 (ruled out), X133, X146-X150, X152-X155, X159. Open (36): X9, X41, X57, X59, X61, X62, X67, X71, X75, X83,
  X87, X89, X90, X95, X99, X101-X104, X107, X112, X113, X116, X118, X119, X121, X123, X131, X134, X145, X151, X156-X158,
  X160, X161.
- Recorders: CLOB books stalled from ~04:20 UTC because no BTC/ETH 5m-15m windows were listed for 11-01 ~05:00-06:59
  (they look up the current window by slug; windows from 07:00 exist); reference feeds (dm_bnf etc., dx_bnf, dy_rtds,
  dz_rtdsbn, dv_rtds) running; shared live.py running (clob_crypto 6 tokens; its rtds feed shows written 0 at 06:13).
  Cache 1.5 GB after deleting the re-fetched stable tapes (re-fetchable in ~75 s from the HTTP cache).

**Next steps (iteration 15).**
1. X161 / X151: build R9, the family-general universe for the weekend exam blocks: every crypto Up/Down family in the
   period (listing-based); R7 price (family-agnostic); the R8 public side with each symbol's Chainlink where recorded
   (dv_rtds / rtds) and the cheaper token otherwise; presence by transfer of the R3 class (5m model to every 5m family,
   15m model to 15m and longer), frozen before scoring on the weekend analogs (10-24/25 blocks, 10-31 00-06).
2. X160: replicate the quote-unit side (frozen L 1.0 s, k 1.0) on 11-01 07:00-12:00 and 18-24 (dx_clob / dm_clob_raw
   should resume with the 07:00 windows), with the 62/250 posts reported separately.
3. X156 step 2: GMX anchors for the September stand-in basis (sparse; only if the stand-in matters for a decision).
4. X157 / X158 if time: the takers' clock; hour-of-week public covariates of the module state.
- T8 = X162 (own; pre-registered 06:31 UTC before running): QUOTE presence at event time, the brief's preferred maker
  unit ("whether it has an order resting"): label = an at-touch 500/1000 post on the outcome in [T, T+1) (rebuilt
  full-depth table, all makers' exact-size posts), same 1-s panel, features and split as T6 (fit 14-16, test 16-18), the
  posture in its quote form (stamp <= T - 1,000 ms, k 1.0); gain = activity + reference minus activity
  (`code14/pres_quote.py`).

**T8 = X162 result: on the quote unit the reference gain over co-occurrence is three times the fill gain
(`code14/pres_quote.py`, results/iter14_pres_quote_1793455200_1793469600.json).** 45,658 (window, outcome, 1-s) cells,
test positives 1,713 (an at-touch 500/1000 post). Test AUC: activity 0.672 (5m 0.639, 15m 0.689); activity + reference
**0.762** (5m 0.739, 15m 0.779); Chainlink-only reference 0.767 (15m 0.789). **Gain +0.090, 20-min block bootstrap
[+0.058, +0.117]** (fill presence on the same panel: +0.031). Top gain: edge_cl (the quote-form posture edge) 5,601, then
n30, mid_s, edge_fut. At 10-s bin starts the 1-s model gives 0.674 / 0.691 (not a 10-s forecaster). So the decoded quote
decision is visible above other traders' activity when the unit is the quote (gain clears the 0.05 bar with a positive
lower bound) but the level (0.76) is below 0.85; the label includes other makers' exact 500/1000 posts (~12%). Frozen
spec for replication on the next development block with books (X160): this script unchanged.

**Quote posture by time left (`code14/qu_tau.py`, results/iter14_qu_tau.json; post hoc, for replication).** Best sigma
multiplier per time-left band on the 500/1000 quote unit (lag 1.0 s; fit 14-16 / test 16-18): 0-60 s k 0.3 (0.830 /
0.878; k 1.0 0.601 / 0.720), 60-120 s k 1.4 (0.824 / 0.805), 120-300 s k 1.0-1.4 (0.844 / 0.822; 0.833 / 0.856), 300-600 s
(15m only) k 0.3-0.7 (0.888-0.900 / 0.895-0.906), 600-900 s unstable (fit-best k 2.0 0.853 -> 0.565 test; k 1.0 0.813 /
0.816). Band-wise fit-best k does not beat one k out of sample (0.803 vs 0.811, the 600-900 band breaks); "k 0.3 in the
last 60 s, else 1.0" gives about 0.827 on test (+0.016): in the last minute the at-touch quote sits on the favourite, as
a near-zero-uncertainty fair would. The engine's uncertainty does not scale as sqrt(time left) with one constant; a
second block is needed before any change (X160).

**Unit check: the reference gain lives at event time, not at 10-s bin starts (addendum to `pres_event.py` /
`pres_quote.py`, models refit on the 10-s unit, same block and split).** Fill presence, 10-s unit: activity 0.748,
activity + reference 0.742 (gain -0.005; 1-s unit +0.031). Quote presence, 10-s unit: activity 0.666, activity +
reference 0.667, Chainlink-only 0.688 (gain +0.001 / +0.022; 1-s unit +0.090). On this live block the decoded quote is
predictable from public inputs only at the second it is made (the posture changes within the 10 s; information panel
C2), which is why every 10-s presence model so far shows +0.02-0.03 at most. An examinable presence claim would have to
be made on an event-time quote unit, replicated on a second block (X160, X162).

**Per wallet (`code14/wallet_post.py`, results/iter14_wallet_post.json): the quote form lifts every wallet's post-time
side.** Filled orders of 10-31 14-18, posture at the post, quote form (L 1.0 s, k 1.0) vs R8 form (L 1.25 s, k 1.4):
class (i) bosona 0.899 (0.783), almach 0.890 (0.865), mo-money 0.839 (0.769); class (ii) 0.739 / 0.649 / 0.571 (0.694 /
0.667 / 0.526); all 0.854 / 0.829 / 0.762 (0.758 / 0.815 / 0.699). Mo-money's deficit stays in its resting rungs.

**X160 runner and a second reported block in `evaluate()` (`code14/x160_block.py`, frozen models in `code14/models/`).**
The event-time quote-presence models fitted on 10-31 14-16 (`pres_quote.py`, saved: activity, activity + reference,
activity + Chainlink) are applied without refit from the slim exam recorder only (dx_clob 'pc' deltas and 'x' trades,
dx_bnf / dm_bnf, cl_source, Gamma strike, cluster tx hashes from the data-api). Check on 10-31 16:00-16:50 (test-half
span, 13 windows, 11,378 cells, 958 positives): activity 0.658, activity + reference **0.769**, Chainlink-only 0.764,
gain **+0.111**; quote-unit side 0.816 (n 1,937). `evaluate()` reports it as `quote_presence_event_time` (VALIDATE-only,
one block; level < 0.85), beside `quote_unit_side`. Next development block with books: run
`code14/x160_block.py <start> <end>` (it writes results/iter14_x160_<start>_<end>.json).

**Smoke test 2 of `evaluate()` (10-31 16:00-17:00; results/iter14_eval_r8_1793462400_1793466000.json) and the
decomposition of the quote presence (`x160_block.py`, frozen models).** quote_presence_event_time on the full hour (16
windows, 14,370 cells, 996 positives): activity 0.698, rule **0.800**, Chainlink-only 0.795, gain **+0.102**;
quote_unit_side 0.816. Decomposition: WHEN (a post on either outcome in the second; 7,185 seconds, 13.6% positive):
activity 0.648 vs rule 0.713 (+0.065); WHICH outcome (964 seconds with a post on exactly one outcome): activity 0.629 vs
rule **0.824** (+0.195). The decoded reference adds to both the timing and the side of the quote; the side carries most
of it.

### CORRECTION (06:44 UTC, before the checkpoint is final): look-ahead in the 1.0-s stamp lag

The quote-form inputs above used the Chainlink report stamped <= t - 1,000 ms. Publish delays on the public relay
(dy_rtds, 17:29-18:00): q10 787 ms, median 1,088 ms, q90 1,471 ms. So a 1.0-s stamp lag can use a report up to ~0.5 s
before it is published.
- **Event-time quote presence (T8 / X162) was inflated by it.** At an integer-second cell start T the report stamped T - 1
  is published at ~T + 0.09 s (median), inside the label second. Re-run with the point-in-time-safe lag 1,432 ms (p90,
  R8's convention; `pres_quote.py ... 1432`, results/iter14_pres_quote_1793455200_1793469600_L1432.json): activity 0.672,
  activity + reference **0.701**, Chainlink-only 0.717: **gain +0.029 (Chainlink-only +0.045)**, i.e. the same as fill
  presence. The +0.090 / +0.102 / +0.111 figures and the WHEN / WHICH decomposition above are NOT point-in-time and are
  withdrawn. The frozen models in code14/models/ were re-saved from the safe run and `x160_block.py` now uses the safe lag.
- **Quote-unit side: checked on the exact publish clock (`code14/qu_pit.py`, results/iter14_qu_pit.json).** On the
  posts where dy_rtds has each report's publish ms (17:29-18:00, 585 posts, full-depth book, BTC 15m after the
  switch-off), the posture from the latest report published BEFORE the post (strictly point in time), k 1.0: **0.831**
  (17:29-17:41 0.900, n 260; 17:41-18:00 0.775, n 325), above every fixed stamp lag on the same posts (L 1,000 0.793,
  L 1,250 0.792, L 1,432 0.783). On 14-18 a fixed point-in-time-safe lag (1,432 ms) gives 0.764 / 0.749 (fit / test,
  k 1.0); the 0.815 / 0.811 of L 1,000 is an approximation of "the report just published" that is not strictly point in
  time. The exam-recorder form (`qu_dx.py`, now exact publish clock where dy_rtds exists, else L 1,432): 0.742 on
  15:53-18:00 (the exact-clock part, 17:41-18:00, 0.688 vs 0.775 on the full-depth book: dx_clob's touch comes only with
  schedule-size deltas, so its mid is staler). Honest statement: the uncensored quote's side is 0.75-0.78 with
  point-in-time-safe fixed lags and 0.83 on the 30 minutes with exact publish times; the exam blocks (10-31 18-24,
  11-01 00-06) have dy_rtds, so the exact form can be scored there.
- Safe frozen check (`x160_block.py`, models re-saved from the LAG 1,432 run) on 10-31 16:00-17:00: quote presence 0.744 vs
  activity 0.698 (gain +0.045); WHEN 0.684 vs 0.648, WHICH 0.724 vs 0.629. These replace the withdrawn figures.
- Final smoke test of `evaluate()` with the point-in-time-safe blocks (10-31 16:00-17:00; results/iter14_eval_r8_1793462400_1793466000.json):
  quote_presence_event_time 0.744 vs activity 0.698 (gain +0.045); quote_unit_side 0.741 (n 1,937, all on the fixed
  1,432-ms lag: dy_rtds starts at 17:29); per-fill match-clock side 0.768 (n 678). (Iteration 14 ended 2026-11-01 ~06:51
  UTC, about 80 minutes.)

## Iteration 15 (started 2026-11-01 07:14 UTC; 965 of 1,200 minutes used)

Situation at the start: the current development block (Sunday 11-01 06-12 UTC) is the idle weekend configuration
(06:00-07:20: bosona 94 activity rows, almach 39, mo-money 37, mostly BTC/ETH hourly and daily; BTC 5m/15m books
recorded again from 07:00 after the 05:00-06:59 listing gap). The next future exam is a weekend lot whose idle blocks
are carried by the non-BTC families. Laptop clock (X167): `dy_rtds` clk offsets (Binance minus laptop) 0.677 s at
06:03, 0.867 s at 07:03, 0.898 s at 07:13 (+0.031 s per 10 min; w32tm "not synchronized", last sync 11-01 02:29 UTC).
**The user should resync Windows time before 11-01 12:00 UTC** (agents may not change system settings); the code
guard is below.

Competing explanations of the money, this iteration (what tells them apart):
- E1 one engine, one rule everywhere: the mid-pegged ladder with a settlement-reference skew runs on every family;
  the non-BTC fills differ only because their books are thin. Tell: non-BTC fills follow the posture sign(F - mid) as
  much as the in-the-money side; R7 works where the anchor is fresh.
- E2 a separate always-on strike-gap module on the non-BTC families: it bids for the outcome in the money under the
  family's settlement reference (sign(S - K), sigma-free), mostly at the window open, at fixed per-family sizes, in
  all three wallets at once. Tell: opening fills follow sign(S - K) >= 0.85 against a market favourite <= 0.70; prices
  track the fair, not the last print.
- E3 long-horizon favourite harvest (hourly/daily/4h): it buys near-certain favourites (0.90+) hours before the end
  (favourite-longshot bias, carry). Tell: daily fills at >= 0.9; the in-the-money side equals the market favourite;
  PnL per $ small and positive with rare large losses.
- E4 taker-chosen fills on resting ladders everywhere: the module has no directional rule; one-sidedness is the takers'
  flow. Tell: side at chance against both the reference and the market.
- E5 liquidity rewards: per-family sizes set to rewardsMinSize, quotes within rewardsMaxSpread. Tell: sizes = Gamma
  rewardsMinSize. **Checked first (Gamma, development markets): rewardsMinSize is 50 and rewardsMaxSpread 4.5 on ETH 5m,
  BTC hourly, BTC daily and BTC 4h alike, while the configured sizes are 10/12/19/38 (below 50, not reward-eligible),
  50 (daily) and 400 (4h). Rejected for the 5m alts and the hourly family.**
- E6 cross-asset hedge: the non-BTC buys offset the cluster's BTC exposure. Tell: the alt side correlates with the
  cluster's net BTC delta (X133 found no hedge between BTC windows).
- E7 (unlikely) a faster reference at the open (e.g. Binance before the Chainlink relay): opening fills timed before the
  public reference moves.
This iteration discriminates E2/E3 against E1/E4 on the non-BTC families (they decide the idle half of the exam lot),
and checks the panels' clock and unit criticisms of the BTC quote unit.

Pre-registered tests (written about 07:27 UTC 11-01, before any of the measurements below were computed):
- T1 = X173 + X175 + X164 (assumptions P1 / P3, information I14-2; the non-BTC module's side). Universe: every cluster
  BUY trade (all roles; side is scored for every decision) on the crypto Up/Down families other than BTC 5m/15m:
  {eth, sol, xrp, bnb, doge}-updown-{5m, 15m}, {btc, eth, sol, xrp, bnb, doge}-updown-4h, <coin>-up-or-down-<date>-<h>-et
  (hourly, Binance 1h candle), <coin>-up-or-down-on-<date> (daily, Binance 1m close at noon ET vs the previous noon).
  Reference S = Binance spot 1-s close of second T - 3 (T = block second; the spot second is public one second after
  it ends and the print may have matched up to 2 s before T). Strike K: Chainlink TWAP families (5m/15m/4h) = the
  Binance TWAP-60 stand-in (mean 1-s close over [st - 60, st - 1]; same basis on both sides); hourly = the Binance
  1-s open at st (the 1h candle's open); daily = Gamma priceToBeat (the previous noon close; listing-time field).
  Rule (no fitting): **buy the outcome in the money, Up iff S > K** (sigma-free). Baselines: market favourite (the
  outcome priced above 0.5, from the fill price), cheaper token, always-Up. Strata: opening (T - st < 20 s) vs later;
  family; BUILD sample days (10-08..22 even days), STUDY 10-23..26 per day, VALIDATE 10-27..30 aggregate,
  development blocks 10-31 00-06 / 12-18 and 11-01 06:00-now. Signature (panel): opening >= 0.85 in every BUILD week and
  on STUDY with the market favourite <= 0.70; combined >= 0.80 per fill on the idle analogs.
- T2 = X168 (mechanics P1, light): the per-family size table from activity (modal size share per family x session x
  wallet), the /8 arithmetic, and the share of non-BTC fills whose size equals the family constant.
- T3 = X166 (information I14-4): the settlement-average variance law k(tau) = tau / (60 sqrt 3) for tau <= 60 and
  sqrt((tau - 40) / tau) above, on the rebuilt quote unit of 10-31 14-18 with the point-in-time-safe lag (1,432 ms)
  and on the exact publish clock (17:29-18:00), no fitting, against one global k 1.0 and the band fit, per tau band.
- T4 = X170 (mechanics P3): the quote-unit side on pure classes only: 500 posts at non-extreme prices (0.03 < p < 0.97),
  exact publish clock and safe lag, vs the extreme 500s and the 1000/250/62 posts.
- T5 = X163 / X169 (information I14-1 / mechanics P2; publish-anchored unit) where an active block with dy_rtds
  exists: units (window, outcome, publish P_i); label Q = an at-touch 500 add (non-extreme) on s in [P_i, P_i + 300 ms);
  frozen score without fitting = 1[posture from report i favours s] x |F_i - mid|, against an activity score
  (prints on s in the previous 1 s); placebo at P_i + 500 ms with report i - 1. Blocks: 10-31 17:29-18:00 (BTC 15m) and
  11-01 07:00-now (whatever the cluster quotes). Under-powered by construction this iteration; the full fitted test
  (fit 07:00-09:30, test 09:30-12:00) is left to the next iteration if BTC 5m/15m quote today.
- T6 = X174 (assumptions P2, light): the examiner's halves on mock weekend lots (Sat 06-12 + Sat 18-24 + Sun 00-06 of
  10-10/11, 10-17/18, 10-24/25): scope of R8's universe and of the all-family universe per half, from activity.

### Iteration 15 results (07:15-08:00 UTC 11-01)

**X167 (information I14-5): clock integrity.** dy_rtds clk offsets (Binance minus laptop): 10-31 17:36 0.043 s, 17:57
0.107 s; 11-01 06:03 0.677 s, then +0.031 s every 10 min to 0.898 s at 07:13 (w32tm: "Leap Indicator 3 (not
synchronized)", last successful sync 11-01 02:29 UTC; the rate was the same before that sync). Receive minus publish
for BTC Chainlink 07:00-07:30: median -596 ms (it was +234 ms on 10-31). Code guard: `final_rule._iter_live_x` and
`_iter_live_xq` now keep a record only if both its receive time and its server stamp `s` lie in development blocks; the
match-ms and book readers no longer fall back to the laptop `t`; `cl_source._live` also drops values whose value stamp or
publish ms is in a sealed block. The scripts that read through `tools/live.iter_live` (qu_dx, x160_block) still rely on
the filing by receive time (dev windows only, so sealed units are not scored; a dev window's records after a
dev-to-sealed boundary are cut by window end). **A resync of the Windows clock by the user is needed before 11-01
12:00 UTC (first leaking boundary, ~1.8 s); agents may not change system settings.**

**T1 = X173 + X175 + X164 (the non-BTC module's side; `code15/nb_side.py`, results/iter15_nb_side.json).** 117,912
cluster BUY trades parsed (BUILD sample days 60,689; STUDY 15,706; VALIDATE 36,612; development after T0 4,905), non-BTC
families 27,402. Rule "in the money under the family's Binance reference, Up iff S(T-3) > K" (no fitting):

| fold | opening fills (< 20 s): itm / market favourite (n) | later fills: itm / market favourite (n) | all non-BTC |
| --- | --- | --- | --- |
| BUILD (8 days) | **0.814** / 0.622 (2,097) | 0.598 / 0.606 (14,227) | 0.625 / 0.608 |
| STUDY 10-23 / 24 / 25 / 26 | 0.722 / 0.897 / 0.860 / 0.837 vs 0.48 / 0.65 / 0.67 / 0.77 | 0.64 / 0.75 / 0.75 / 0.65 vs 0.62 / 0.76 / 0.72 / 0.65 | 0.65 / 0.77 / 0.77 / 0.67 |
| VALIDATE (aggregate) | **0.778** / 0.485 (535) | 0.552 / 0.545 (4,382) | 0.576 / 0.539 |
| after T0 (development) | 0.54 / 0.23 (26) | 0.54 / 0.54 (326) | 0.543 / 0.517 |

By family (opening): alt 5m 0.848 BUILD / 0.77-0.90 STUDY / 0.791 VALIDATE (market favourite 0.73 / 0.59-0.86 / 0.61);
alt 15m 0.765 / 0.61-0.95 / 0.780. The longer families trade later in the window: hourly later 0.692 / 0.76-0.78 / 0.578,
4h later 0.668 / 0.71-0.82 / 0.496, daily 0.453 / 0.35-0.71 / 0.498. Per wallet the numbers are within 0.02 of each
other in every fold. Per one-sided market (>= 70% of shares on one outcome; 77-85% of markets) the first fill's itm side
gives the majority side 0.689 BUILD, 0.66-0.79 STUDY, 0.629 VALIDATE. **Verdict: the opening rule is real (+0.19 to
+0.29 over the market favourite on BUILD and VALIDATE) but below the panel's 0.85 signature (BUILD 0.81, VALIDATE 0.78),
and it covers only 13% of the non-BTC fills; later fills follow the market favourite (0.55-0.75), and on VALIDATE the
non-BTC side is 0.58 (market 0.54). R9's planned cheaper-token fallback would be the anti-rule (0.39-0.46).** Same rule on
BTC 5m: 0.34-0.64 (VALIDATE 0.335: the cluster bought the out-of-the-money outcome on two thirds of VALIDATE BTC 5m fills,
the favourite-share drift), BTC 15m after T0 0.80.

**T1b (post hoc; `code15/nb_posture.py`, results/iter15_nb_posture.json): relative value with the fill price as the
market price (description, not public).** buy s iff Phi(ln(S/K) / (k sigma300 sqrt(tau))) of s > the fill price;
k 1.0: non-BTC BUILD 0.667, STUDY 0.753, VALIDATE 0.676, after T0 0.622 (itm 0.625 / 0.721 / 0.576 / 0.543); by family
(BUILD / STUDY / VALIDATE): 4h 0.822 / 0.833 / 0.689, alt 15m 0.806 / 0.865 / 0.755, daily 0.790 / 0.803 / 0.786, hourly
0.659 / 0.656 / 0.630, alt 5m 0.561 / 0.749 / 0.600; k 1.4 and above is worse on every fold. The public version (last
clean print instead of the fill price) is T1d below.

**T1c (`code15/nb_pnl.py`, results/iter15_nb_pnl.json; Binance stand-in settlement): where the non-BTC money is.**
Later fills earn +3.5% per $ (BUILD, $319k cost), +3.1% (STUDY), +2.6% (VALIDATE); opening fills +0.6% / -14.5% / -2.4%.
The in-the-money opening fills lose (-2.4% BUILD, -14.8% STUDY, -8.7% VALIDATE) while the opening fills against the rule
win (+15% / -14% / +31%): the opening rule describes the side but is not where the profit is (E2's "takers trade the open
as 50/50" mechanism is refuted). The profit is in the 4h (+8.4% BUILD, +4.8% VALIDATE) and hourly (+7.5%, +10.0%) later
fills, i.e. buying below a Binance-volatility fair on the long-horizon families (E3-like value buying, not a favourite
harvest: the daily family earns about 0).

**T2 = X168 (size table from activity fill sizes; results/iter15_nb_side.json size_table).** Modal fill sizes per family
are identical in the three wallets: BTC hourly 38 off / 300 US session, BTC 4h 400, ETH 15m 30, SOL 15m 30, ETH 5m 50
off / 150 US, SOL 5m 50 (almach 12) / 100 US, XRP 5m 10 / 50, BNB 5m 10, DOGE 5m 10 / 40, dailies 50 (BTC daily 200),
ETH hourly 5. Mode shares are 0.07-0.76 because fills are partial; the calldata sizes of the mechanics panel are cleaner.
Calldata of 11-01 06:00-07:40 (`code15/today_sizes.py`, 239 transactions): BTC 5m 500 (28 of 43 cluster orders) and 100
(5), BTC 15m 500, ETH 5m 150, ETH 15m 30, ETH/SOL daily 50, XRP 5m 50: the high levels run on a Sunday morning. E5
(sizes = rewardsMinSize) is rejected (Gamma rewardsMinSize 50, rewardsMaxSpread 4.5 on every family checked).

**T3 = X166 (information I14-4; `code15/qu_law.py`, results/iter15_qu_law.json): the settlement-average variance law
does not beat one global k.** Non-extreme 500 posts of 10-31 14-18, safe lag: law 0.779 = k 1.0 0.779 (n 4,887); last
120 s: law 0.749 (fit 0.813 / test 0.705), k 1.0 0.731, band k 0.3 0.761 (n 427); exact publish clock 17:29-18:00: law
0.835 vs k 1.0 0.866 (n 447; the law is worse at 120-300 s, 0.746 vs 0.806). Signature (last 120 s >= 0.83 on both
halves without fitting) not met: the engine's time-left profile is not the TWAP variance law.

**T4 = X170 (mechanics P3, purity by class; same script).** Posture accuracy by label class, k 1.0: 500 at non-extreme
bids **0.779 (safe lag, n 4,887) and 0.866 (exact publish clock, n 447)**; 500 at bids <= 0.03 or >= 0.97 0.57-0.69;
1000 0.70-0.87; 250 0.49-0.61; 62 0.49-0.53 (n 324, mostly one 15m window's last minutes). The pure main ladder on the
exact clock clears the panel's 0.85 signature on the one block that has the clock; the "62/250 at chance" statement is
withdrawn as a statement about the off-session ladder (they are other makers' orders and deep rungs; mechanics panel).

**T5 = X163 / X169 (publish-anchored unit, no fitting; `code15/pub_unit.py`).** 10-31 17:29-18:00 (BTC 15m; 1,774
publishes, 7,010 (window, outcome, publish) cells, 119 non-extreme 500 posts in [P_i, P_i + 300 ms)): the report-i
posture level ranks the cells at **AUC 0.794** and picks the outcome at **0.866** (one-outcome cells), against no-fit
activity scores 0.53 (mid changes in the last 1 s) and 0.52; placebo [P_i - 300 ms, P_i) (posts before report i is
public): level 0.625, which 0.652; the CHANGE in posture from report i-1 to i scores 0.665 / 0.706 after the publish but
0.429 / 0.424 before it (posts just before a publish sit on the side the new report then reverses). That is the trigger
signature: the 500 ladder is re-sided by each published report within 300 ms. The Polymarket mid over the last second
points the other way (0.19 / 0.81: the engine posts on the outcome whose mid fell), so a fitted activity model would use
it; the fitted version is left for a full development block. 11-01 07:00-07:55 (Sunday, BTC 5m resumed; 2,714
publishes, 60 non-extreme 500 posts): level 0.675, which 0.717 (n 60), placebo before 0.609 / 0.633, change 0.601 after /
0.399 before: the same ordering, weaker.

**X160 replication on the second development block with books (`code15/qu_today.py`, `qu_today_scan.py`): fails on its
first 50 minutes.** 11-01 07:00-07:50 (12 windows, 279 non-extreme 500 posts; calldata shows the cluster's BTC 5m orders
are 500s again): exact publish clock k 1.0 0.624 (n 218; BTC 5m 0.614), safe lag 0.599; best of a k x reference scan
0.697 (Binance futures minus its rolling basis, k 1.4); cheaper token 0.663, always-Down 0.595. Per window the posts' Up
share and the window's posture agree in about half of the 12 windows and are opposite in others (5m-1793517000: posts
13% Up, posture 73% Up). The quote-unit side of 10-31 (0.83-0.87) does not carry to the Sunday-morning block on 50
minutes; the full block (to 12:00) must be scored before the quote side is made exam-facing.

**T6 = X174 (assumptions P2 light; `code15/mock_halves.py`, results/iter15_mock_halves.json): the examiner's halves on
weekend mock lots.** R8 universe share of trades / $ per half: 10-10/11 earlier 0.86 / 0.92, later 0.83 / 0.89; 10-17/18
earlier 0.87 / 0.92, **later 0.41 / 0.61**; 10-24/25 **earlier 0.39 / 0.38, later 0.28 / 0.32**. Per wallet the shares
move together (within 0.08). R8's universe fails scope in at least one half of two of the three mock lots; only the
all-family universe holds in every half. The non-BTC itm side per half: 0.55-0.82 (market favourite 0.65-0.75).

**R9 reporting block (`code/r9_nonbtc.py`, wired into evaluate() as `r9_nonbtc_module`, not counted).** Loads the
cluster's activity for the period, Binance 1-s klines by REST (development blocks only unless ALLOW_SEALED), Gamma
priceToBeat for dailies; reports the R8-universe scope (pooled, per wallet, per examiner-style half) and the non-BTC side
(itm open / later / by family / per wallet / per half, the fill-price posture as a description, baselines). Smoke test on
the development block 10-31 00-06 (68 s): R8 universe 0.914 of trades / 0.949 of $ (halves 0.90 / 0.94); non-BTC fills
156: itm 0.548 (open 0.82, n 18; later 0.51), fill-price posture 0.680, market favourite 0.519.

**X172 (mechanics P5, crude form; `code15/cancel_lag.py`, results/iter15_cancel_lag.json): mo-money's resting rungs
carry an older posture.** Filled orders of 10-31 14-18 (it14_fills_lq), posture from the report public before fill - L
(stamp lag 1,432 ms), k 1.0, mid just before the fill for every L (crude). Class (ii) (resting rungs): mo-money 0.617 at
L 0, 0.669 at 312 ms, 0.699 at 500 ms, **0.752 at 1,000 ms**, 0.647 at 2,000 ms; bosona 0.784 / 0.802 / 0.775 / 0.748;
almach 0.847 / 0.838 / 0.865 / 0.793. Class (i) is flat or falls with L for every wallet (0.83-0.87 at L <= 312 ms). So
mo-money's swept rungs match the posture of about one second earlier, while the other two wallets' rungs match the
current one: a slower cancel / re-side path in mo-money's engine instance (consistent with the panel's remainder-remove
latency 312 ms vs 73-118 ms). At its own best lag mo-money's class (ii) is within 3 points of bosona's best and 11 below
almach's: the per-wallet gap shrinks from 17-23 points to 3-11 but does not close. A proper version needs the mid series
at fill - L (dm_clob_raw), not the mid at the fill.

**X170 on the current block (`code15/purity_today.py`, results/iter15_purity_1793516400_1793519700.json): the 500 label is
pure on 11-01 too.** All-match calldata of every trade transaction recorded in dm_clob_raw for 11-01 07:00-07:55 (12,392
transactions): filled exact-size maker BUY orders that are the cluster's: **500 at non-extreme prices 0.907 (n 162)**,
500 extreme 0.33 (15), 100 non-extreme 0.13 (253), 100 extreme 0.02 (62), 250 0.00 (170), 1000 0.00 (11), 62 0.37 (19).
So the X160 replication failure below is not a label artefact: the cluster's own 500 posts changed side behaviour.

**X160 on the full hour 11-01 07:00-08:00 (`qu_today.py`, `qu_today_scan.py` on the rebuilt table, 17 windows, 429
pure-class 500 posts, 358 on the exact publish clock).** Posture k 1.0: 0.601 (exact clock), 0.578 (safe lag); BTC 5m
0.608, BTC 15m 0.569; scan: k 2.0-3.0 0.645-0.654, futures-minus-basis k 3.0 0.654; cheaper token 0.627-0.642. On this
Sunday-morning block the engine's at-touch quote is closest to a very flat fair (k 2-3, i.e. bid the underdog), about the
cheaper-token baseline, while on 10-31 17:29-18:00 (Saturday evening, BTC 15m) k 1.0 gave 0.866. The quote side is a
k-family whose configuration moves between blocks (as the fill-level k drift of iteration 11 showed); it is not one frozen
rule.

**Unit-membership fix (sealed-data hygiene).** The development activity of 10-31 12-18 held 19 rows of units that had
started in the sealed block before it (hourly 7am ET, BTC/ETH 15m 11:45, BTC 5m 11:55, BNB 4h 08:00; trades stamped after
12:00). They were purged from the cached act15 files and `nb_side.py` now drops every unit whose window starts in a sealed
block (the rule is by unit start, not by trade time); the T1 numbers were recomputed (below). None of these rows was
scored before (their strikes need spot seconds of the sealed block, which were never fetched), but they were counted in
the trade totals of the after-T0 fold. `code/r9_nonbtc.py` filtered by unit start from the beginning.

**X176 (assumptions P4; `code15/sel_open.py`, results/iter15_sel_open.json): print-level selection on the non-BTC 5m/15m
families fails; the takers' size selects the cluster's fills.** 167,734 taker prints in the alt 5m/15m windows the
cluster traded (STUDY, VALIDATE, after T0), 3,587 of them in cluster-fill transactions (base rate 2.1%). Frozen score
(maker-BUY outcome in the money + opening + small taker size), no fitting: AUC 0.621 (recall at k 0.12, lift 5.6); the
itm part alone 0.615; an activity-only score (opening + taker-size rank) **0.730** (recall 0.10, lift 4.8). Opening prints:
0.605 / 0.632 / 0.617; later prints 0.534 / 0.588 / 0.694. VALIDATE 0.581 / 0.584 / 0.714. Signature (opening >= 0.85,
all prints >= 0.80 with recall >= 50% at lift >= 3) not met: rejected; the larger the taker order, the likelier it reaches
the cluster's quotes (co-occurrence), whatever the side.

**X163 fitted form on the current block (`code15/pub_fit.py`, results/iter15_pub_fit_1793516400_1793520420.json; post hoc,
small).** 11-01 07:00-08:07, publish-anchored cells (14,382; 138 pure 500 posts in [P_i, P_i + 300 ms); fit on the first
60% of publishes, test on the rest; LightGBM 7 leaves 200 rounds): activity 0.748, activity + report-i posture 0.730,
gain **-0.018 (10-min block bootstrap [-0.055, +0.028])**; placebo before the publish -0.045. On the Sunday-morning
block, where the side relation is weak (0.60), the reference adds nothing to the publish-anchored presence either. With
the no-fit result of 10-31 17:29-18:00 (0.794 vs 0.53) the publish-clock account holds on one block and fails on the
next: X163 stays open for the full 07:00-12:00 block.

**T1d (post hoc, follows T1b; `code15/nb_public.py`, results/iter15_nb_public.json): the non-BTC posture with a PUBLIC
market price (the last clean taker print of the market stamped <= T - 2; dailies excluded because their tapes are too long
to page this iteration).** Non-daily non-BTC fills with a public price: STUDY 4,984, VALIDATE 3,877, after T0 271.

| fold / phase | itm | market favourite (public print) | public posture k 0.7 | k 1.0 | k 1.4 | fill-price posture k 1.0 |
| --- | --- | --- | --- | --- | --- | --- |
| VALIDATE all | 0.598 | 0.568 | 0.590 | 0.587 | 0.538 | 0.647 |
| VALIDATE opening (n 494) | 0.792 | 0.544 | **0.866** | 0.806 | 0.733 | 0.921 |
| VALIDATE later (n 3,383) | 0.569 | 0.572 | 0.550 | 0.555 | 0.509 | 0.607 |
| STUDY opening (n 841) | 0.843 | 0.613 | **0.924** | 0.882 | 0.730 | 0.929 |
| STUDY later (n 4,143) | 0.717 | 0.703 | 0.686 | 0.634 | 0.487 | 0.704 |
| after T0 opening (n 26) / later (n 245) | 0.54 / 0.66 | 0.31 / 0.66 | 1.00 / 0.64 | 0.92 / 0.53 | | |

At the window open the relative-value posture against the last public print (fair = Binance digital with 0.7 x the
symbol's 300-s volatility, strike = the TWAP-60 stand-in) picks the cluster's side at **0.866 on VALIDATE and 0.924 on
STUDY** (k 0.7 chosen among the three pre-listed values; it is best on both folds), against the market favourite 0.54 /
0.61: the opening quote of the alt families is decoded on public inputs. After the open no public rule beats the market
favourite (0.55-0.70), and the fill-price posture's extra points come from the fill price itself. Combined on VALIDATE
(posture k 0.7 at the open, market favourite later) the non-daily non-BTC side is about 0.61. By family (VALIDATE, all
phases): alt 15m posture k 1.0 0.695 (market 0.484), alt 5m itm 0.668 (0.661), hourly itm 0.589 (0.552), 4h 0.51-0.59
(0.501).

## Iteration-15 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). R8 stays frozen; no frozen decision changed; one reported block added (`r9_nonbtc_module`,
  `code/r9_nonbtc.py`); the live readers filter by server stamps (X167). target_metrics unchanged (union presence 0.788 /
  0.780; selection 0.685 / 29.5% / 2.87; side 0.693 / 0.679; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891).
- Paradigm: decode the module that carries the idle weekend blocks on its own terms (per-family sizes, the opening
  in-the-money rule, the settlement reference per family, where its money is) and test the panels' unit and clock
  criticisms of the BTC quote (publish-anchored cells with a placebo, label purity, the TWAP variance law, the second
  development block).
- What it showed: (1) outside BTC 5m/15m the cluster quotes a configured size per family in all three accounts; at the
  open of the 5m/15m alt windows its side is decoded on public inputs (a Binance-digital posture with 0.7 x sigma300
  against the last public print: 0.866 VALIDATE, 0.924 STUDY; in the money 0.78-0.81; market favourite 0.54-0.62), but
  those buys lose money; its profit there is in later 4h/hourly buys (+5-10% per $), whose side
  is at the market favourite level on public inputs; (2) R8's universe fails the scope bar in a half of two of three weekend
  mock lots; (3) on 10-31 17:29-18:00 each public Chainlink publish re-sides the pure 500 ladder within 300 ms (no-fit AUC
  0.794, outcome 0.866, placebo before the publish 0.625; the posture change predicts posts after the publish at 0.665 and
  anti-predicts those before at 0.429); (4) on the next development block (11-01 07:00-08:00, Sunday, label purity 0.91)
  the same quote follows the k 1.0 posture at only 0.60, best k 2-3 at 0.65, about the cheaper token (0.63-0.64): the
  quote's volatility configuration moves between blocks; (5) the TWAP variance law does not beat one k; (6) mo-money's
  resting rungs carry the posture of ~1 s earlier (class ii 0.62 at the fill -> 0.75 at fill - 1 s), the first mechanical
  account of its per-wallet deficit; (7) print-level selection on the non-BTC families fails (frozen score 0.62 vs an
  activity score 0.73: the takers' order size selects the cluster's fills); (8) fitted on the publish-anchored cells of
  11-01 07:00-08:07 the reference adds nothing to quote presence (gain -0.018 [-0.055, +0.028]); (9) the laptop clock drifts
  0.19 s/h (needs a user resync before 11-01 12:00 UTC).
- Closed this iteration: X164, X166, X167, X168, X170, X173, X174, X175, X176 (tried), X151, X161, X83 (tried). New open:
  X163 (fitted test on a full block), X165, X169, X171, X172 (crude form run, proper form open).

**Next steps (iteration 16).**
1. X163 / X169 fitted on the full development block 11-01 07:00-12:00 (dm_clob_raw to 12:00): publish-anchored cells, an
   activity LightGBM of the same class vs activity + report-i posture (k as a per-block state: fit k on the first hour,
   apply to the rest), labels from pure 500 posts; placebo before the publish; 20-min block bootstrap.
2. X160: score the quote side on the whole 07:00-12:00 block per hour with a k scan per hour, and test whether the
   block's k is predictable from public state at the block start (the market's own implied k, realised vol, weekday).
3. The non-BTC public posture (T1d): if it reaches >= 0.70 on VALIDATE, wire it into r9_nonbtc as the later-fill rule;
   fetch the daily tapes (excluded in iteration 15 for paging time).
4. X171 FIFO replay with the recorded queue on 10-31 14-18 and 11-01 07-12; X165 competition at the switch-offs.
5. Ask the user (via the return) to resync the Windows clock.

### Addendum (08:20 UTC): why the quote side did not replicate on 11-01 (post hoc; `code15/cl_sigma.py`, `edge_bands.py`)

- **The Chainlink noise regime ended.** The 300-s sd of 1-s Chainlink changes over the futures-mid sd: **8.2 on 10-31
  14-18** (Chainlink 10.2 $/s vs futures 1.2 $/s, the white-noise regime of 10-30/31) against **0.92 on 11-01 07-08**
  (1.29 vs 1.28). The engine does not price with the Chainlink stream's own volatility: with sigma = k x the Chainlink
  sigma300 the 10-31 posts score 0.45-0.53 (futures sigma k 1.0: 0.783); on 11-01 the two sigmas coincide (0.60-0.65).
- **Accuracy by |F - mid| (pure 500 posts, k 1.0, futures sigma):** 10-31 14-18: < 0.02 0.585, 0.02-0.05 0.625, 0.05-0.1
  0.720, 0.1-0.2 0.837, >= 0.2 **0.935**; 56% of posts at >= 0.1. 11-01 07-08: 0.611 / 0.556 / 0.517 / 0.726 / 0.783;
  27% at >= 0.1. In the clean regime the reference and the market disagree far less, so the posture carries less
  information, and even at the same edge the posts follow it less (small n at the top: 23 posts >= 0.2).
- Reading: the "0.83-0.87 decoded quote side" of iterations 13-14 is mostly a property of the noise regime, in which the
  noisy report pulled the engine's fair far from the market and the engine followed it (and lost money: the BTC 5m blocks
  of 10-31 lost 11.9% and 3.9% before BTC 5m was switched off). In the clean regime the at-touch quote is near the
  cheaper-token baseline. The quote's side rule is therefore "skew toward the latest published report", whose visible
  strength depends on how far the report sits from the market; it is not a stable 0.8+ public description of the posts.
  This also explains part of the k drift: a fitted k compensates for how often the report and the market disagree.

**evaluate() on the current development hour 11-01 07:00-08:00 (results in .cache/re/directional-maker/it15_eval_1101_07.json;
216 cluster BTC 5m maker fills, 12 windows; Sunday, clean Chainlink stream).** Per-fill match-clock side 0.740 (n 246)
against the cheaper token 0.736, Binance 0.598, always-Up 0.516: in the clean regime the fill side equals the
cheaper-token baseline. R7 price 0.912 (match clock 0.955, n 198). BTC 5m presence 0.580 vs activity 0.609 (gain -0.029);
union 0.719 vs 0.715. Quote unit side (exam-recorder form) 0.621 (n 525); quote presence at event time 0.743 vs 0.716
(gain +0.028). r9_nonbtc_module: R8 universe 0.78 of trades / 0.74 of $, **earlier half 0.54 / 0.41**, per wallet bosona
0.86, almach 0.51, mo-money 0.52; non-BTC opening fills public posture 1.00 (n 12), later 0.783 vs market favourite 0.767
(n 60). Both smoke tests of evaluate() (10-31 16-17, 10-31 00-01) ran end to end with the new block.

**Chainlink noise by 6-h block on STUDY days (`code15/noise_days.py`, X102 even-second values fetched so far, 10-23..25):**
sd of 2-s Chainlink changes over the futures' 0.69-0.98 (correlation 0.23-0.44): the lot's STUDY days were in the clean
regime; the white-noise regime (ratio 8.2 at 1 s on 10-31 14-18) is specific to 10-30/31 and had ended by 11-01 07:00.
It therefore does not explain the k step of the 10-24/25 weekend (iteration 11).

**T1e (`code15/nb_public_build.py`, results/iter15_nb_public_build_open.json): the opening posture replicates on BUILD.**
Opening fills (< 20 s) of the non-daily non-BTC families on the 8 BUILD sample days (n 2,027), the same public posture
(Binance digital, 0.7 x sigma300, against the price from the last clean taker print <= T - 2): **0.882** (k 1.0 0.817,
k 1.4 0.679; in the money 0.822; market favourite from the same print 0.623). By family: alt 15m 0.926 (n 337), alt 5m
0.874 (1,523), hourly 0.862 (159). With STUDY 0.924 and VALIDATE 0.866 the opening quote of the alt families is decoded on
public inputs at 0.87-0.92 on three folds, about +0.26 over the market favourite; it covers about 13% of the non-BTC
fills (the later fills stay at the market-favourite level).

**Persistence of the non-BTC fills (`code15/nb_persist.py`, results/iter15_nb_persist.json; own state, reported).** Per
non-daily non-BTC market: later fills (>= 20 s) on the outcome of the market's first cluster fill 0.628 BUILD / 0.676
STUDY / 0.674 VALIDATE (fill-weighted); on the outcome of the market's OPENING fill only 0.502 / 0.438 / 0.445; the
majority side by shares equals the first fill's side in 91-92% of markets. After the directional opening bid the module
buys both outcomes about equally (two-sided, the takers choose), and the opening fill decides the market's net side.
So per market the public opening posture (0.87-0.92 per opening fill) is the decoded part of the non-BTC side; the later
fills are a two-sided ladder (E4) at the market-favourite level (0.56-0.71).

**Is the decoded opening quote profitable? (`code15/nb_pub_pnl.py`, results/iter15_nb_pub_pnl.json; Binance stand-in
settlement.)** Opening fills that agree with the public posture: -0.4% per $ BUILD (n 1,787), -16.1% STUDY (777), -1.3%
VALIDATE (428); those against it +4.8% / -2.6% / +77% (n 240 / 64 / 66). Later fills: posture-agreeing +1.4% STUDY /
+7.8% VALIDATE, against it +16.8% / -10.5%. The decoded part of the non-BTC side (the opening bid) is break-even to
losing; the module's profit sits in the two-sided later fills, whose side is the takers' choice. As on BTC 5m, the public
decode reaches the engine's quote, not what makes the money.

**Opening posture per wallet and per half (results/iter15_open_posture_wallet.json).** almach / bosona / mo-money: BUILD
0.898 / 0.882 / 0.867, STUDY 0.922 / 0.919 / 0.931, VALIDATE 0.856 / 0.855 / 0.888 (n 153-723 each): the three engine
instances quote the opening alike. VALIDATE halves by window start: 0.944 (n 232) vs 0.798 (n 262): the halves differ by
0.15, so the opening component would fail the examiner's replication condition (3 points) on a lot like VALIDATE.
(Iteration 15 ended about 08:32 UTC 11-01, about 77 minutes.)

## Iteration 16 (started 2026-11-01 09:00 UTC; 1,042 of 1,200 minutes used)

Situation at the start: development block 11-01 06-12 UTC (Sunday) is recording (dm_clob_raw full depth by
code8/delayed_rawrec.py to 12:00, dy_rtds, dv_rtds, dw_clob, the shared recorder). The panels (panels/iter15_*.md)
agree on one point: on 11-01 the main BTC ladder ran in one wallet (bosona), so iteration 15's "the quote side did not
replicate" compared a three-instance block with a one-instance block, and the noise-regime reading is post hoc. The
information panel adds a point-in-time Chainlink nowcast (last public report + futures move since its stamp) that
scores 0.68-0.69 on the clean hour against 0.62 for the bare report. Housekeeping: `.cache/re/directional-maker/` was at
the 1.5 GB cap; the July pmxt slice (35 MB, iteration 10 pilot, referenced by no frozen code) was deleted.

Competing explanations of the money, this iteration (what tells them apart):
- E1 one engine, a k-family fair moved by the operator: the side tilt between 10-31 and 11-01 is the volatility
  multiplier k of a Chainlink digital. Tell: the ladder CENTER c follows F_k with the best k moving from ~1 to 2-3, no
  favourite/underdog offset.
- E2 a fixed fair (k ~1, Chainlink nowcast) with a per-instance favourite/underdog spread asymmetry: the center c follows
  F_1 on both blocks, and an offset gamma x (0.5 - mid) changes sign. Tell: c - mid regressed on (F_1 - mid, 0.5 - mid).
- E3 instance composition: after the sealed stretch 10-31 18:00 - 11-01 06:00 only bosona runs the main ladder; its own
  band-conditional side is the same as on 10-31. Tell: bosona's own fills, 10-31 vs 11-01, within |F - mid| bands.
- E4 a nowcast reference: the engine prices off the Chainlink level moved by the futures since the report's stamp, so in
  the clean regime the bare report is stale. Tell: nowcast >= report in every hour; the futures-move direction predicts
  at-touch posts (re-pegs) far above the report.
- E5 a mid-pegged two-sided ladder with taker-chosen fills (replenishment): at-touch posts follow the moving market (the
  outcome whose mid rose, the futures move) and the side of fills is the takers' choice; the profit is spread capture
  plus queue priority. Tell: post side = direction of the last futures move / mid change >> any reference level; fill
  side ~ cheaper token in the clean regime.
- E6 own inventory: posts lean to the held outcome (0.64-0.66 on both blocks, mechanics panel). Tell: stable own-state
  share across blocks and instances (reported, never counted).
- E7 (unlikely) a private faster feed or a copied maker: posts lead every public feed. Tell: the post side is
  explained by no public move within 1 s.

Pre-registered tests (written 09:07 UTC 11-01, before any of the numbers below were computed):
- T1 = X177 (assumptions P1 + mechanics P2, instance-module map; activity only). Units: 15-min slots of BUILD
  (10-08..22), STUDY (10-23..26), VALIDATE (10-27..30, aggregate counts only) and every development block since T0.
  "Split" := one wallet holds >= 0.80 of the mid-band (0.10 < price < 0.90) BTC 5m + 15m BUY fills of a slot with
  >= 20 such fills. Reported: split share per fold, per-wallet deep-band share (<= 0.10 or >= 0.90), first BTC fill per
  wallet per block. Signature of the split reading: split in most 11-01 slots and in ~0 BUILD/STUDY slots.
- T2 = X178 (natural experiment, E3): every cluster BTC 5m/15m BUY fill with a match ms (shared recorder trade with its
  tx hash) on 10-31 14:00-16:53 and 11-01 07:00-now; posture from the Chainlink report stamped <= T - 1,432 ms, Gamma
  strike, futures sigma300, k 1.0 and 1.4, against the Up mid just before the match (shared recorder top-10 book); per
  wallet and per |F - mid| band (< 0.05, 0.05-0.1, >= 0.1), mid-band prices only. Reading: if bosona's band accuracy on
  11-01 is within 0.03 of its 10-31 value in every band with n >= 30, the failure is composition; otherwise the rule or
  the regime changed inside one instance.
- T3 = X179 (information I15-3, nowcast): S_now(t) = CL(stamp s_i) + F(t - 50 ms) - F(s_i), CL the report in force on
  the safe clock (stamped <= t - 1,432 ms) or the exact publish clock (dy_rtds P), F the Binance USD-M mid (dm_bnf). k
  frozen on 10-31 14-18 (safe clock) from {1.0, 1.4}; then scored per hour on 11-01 07:00-now (pure non-extreme 500
  posts), against the bare report, the cheaper token and the futures-move direction. Signature: nowcast >= report in
  every hour and >= cheaper + 0.08 in the clean hours.
- T4 = X180 (assumptions P2 + mechanics P3, ladder center): per public publish P_i (dy_rtds) of 10-31 17:29-18:00 and
  11-01 07:00-now, the top pure-500 re-add price on each outcome in (P_i, P_i + 300 ms] (b_up, b_dn; both outcomes
  needed); c = (b_up + 1 - b_dn) / 2. Regress c - mid on F_k - mid (k 1.0, 1.4, 2.0, 3.0) and on (F_1 - mid, 0.5 - mid)
  per block. Reading (i) k: best k for c moves by > 0.3 and the (0.5 - mid) coefficient is ~0 on both blocks; (ii)
  spread: best k within 0.3 on both blocks and the (0.5 - mid) coefficient changes sign.
- T5 (information I15-2, cheap part): the alt 5m/15m opening fills (< 20 s) scored with Binance S(T - 3) against the
  TRUE strike (Gamma priceToBeat) vs against the Binance TWAP-60 stand-in, posture k 0.7 vs the last public print, on
  BUILD / STUDY / VALIDATE (aggregate). Reading: if the true-strike version beats the stand-in by >= 0.03 on every fold,
  the opening bid reads the published strike; the per-symbol Chainlink fetch (part a) follows only if time allows.

### Iteration 16 results (09:07-09:25 UTC 11-01)

**T1 = X177 (instance-module map; `code16/inst_map.py`, results/iter16_inst_map.json).** Split (one wallet >= 0.80 of
the mid-band BTC 5m + 15m BUY fills of a 15-min slot with >= 20): BUILD 9 of 1,016 slots (0.9%; mo-money 6, bosona 2,
almach 1), STUDY 0 of 147, VALIDATE 0 of 319 (aggregate), after T0 5 of 49, all of them 11-01 07:00-08:15 (bosona 35/0/0,
82/2/0, 33/0/0, 24/0/0, 48/0/0; 07:15 is 20/5/3). **From 08:30 mo-money is back on the mid band** (08:30 21/4/12, 08:45
53/11/33, 09:00 25/4/12 for bosona/almach/mo-money); almach stays low (4-11 per slot). Deep-band share of each wallet's
BTC BUY fills: 0.15-0.19 BUILD, 0.14-0.16 STUDY, 0.29-0.31 VALIDATE, 0.20-0.23 after T0 (equal across wallets in every
fold). Development block 11-01 06-12 so far: bosona 341 mid / 125 deep (first 07:00:48), almach 26 / 63 (first
07:15:03), mo-money 60 / 42 (first 07:15:03). Reading (pre-registered signature): the split is real on 11-01 07:00-08:15
and has never lasted a slot in STUDY/VALIDATE, but it is a transient of the first 75-90 minutes after the 05:00-06:59
listing gap, not a new configuration: mo-money rejoined the main ladder at ~08:30 (almach partly). Recorded as an
operational event (A8); the pooled rule stays, and evaluate() should report the per-slot instance mode (it now does,
`instance_mode`).

**T2 = X178 (natural experiment, own fills on the match clock; `code16/inst_side.py`,
results/iter16_inst_side_1793455200_1793524800.json).** Mid-band (0.10-0.90) BUY fills with a shared-recorder match ms;
posture from the report stamped <= T - 1,432 ms, futures sigma300:

| fills | 10-31 14:00-16:53 report k1.0 / nowcast k1.0 / cheaper (n) | 11-01 07:00-09:20 report k1.0 / nowcast k1.0 / k1.4 / cheaper (n) |
| --- | --- | --- |
| bosona | 0.851 / 0.847 / 0.552 (484) | 0.633 / 0.677 / 0.690 / 0.654 (297) |
| almach | 0.879 / 0.872 / 0.428 (580) | 0.522 / 0.565 / 0.522 / 0.565 (23) |
| mo-money | 0.830 / 0.828 / 0.490 (664) | 0.125 / 0.792 / 0.604 / 0.694 (48) |
| pooled | 0.852 / 0.848 / 0.487 (1,728) | 0.560 / 0.685 / 0.668 / 0.654 (368) |

bosona by |F1 - mid| band (report k1.0; 10-31 vs 11-01): < 0.05 0.719 (32) vs 0.435 (124); 0.05-0.1 0.866 (67) vs 0.582
(55); >= 0.1 **0.860 (385) vs 0.864 (118)** (nowcast 0.860 vs 0.907). Share of bosona's fills at >= 0.1: 0.795 vs 0.397.
Pre-registered reading: not within 0.03 in every band -> **not composition: inside one instance, the large-edge
behaviour is unchanged (0.86) while the small-edge fills went below chance (0.44-0.58)**, and the large-edge share halved.
mo-money's 48 fills of 11-01 08 (report 0.125, nowcast 0.792) sit in a fast move where the 1.4-s-old report points the
wrong way: the futures increment since the report's stamp fixes them. Deep-band fills follow the cheaper token
(0.77-0.95 per wallet and block), as R8's decided branch says.

**T3 = X179 (nowcast on the pure non-extreme 500 posts; `code16/nowcast.py`, results/iter16_nowcast.json).** k frozen
on 10-31 14-18 safe clock: nowcast k1.0 0.785 vs k1.4 0.748 (report 0.779 / 0.745) -> **k = 1.0**. Per hour (safe
clock; exact clock in brackets):

| hour | n | report k1.0 | nowcast k1.0 (frozen) | nowcast k1.4 | cheaper | futures-move rule on moving posts (share moving) | still posts: nowcast / report / cheaper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10-31 15 | 1,997 | 0.792 | 0.792 | 0.762 | 0.447 | 0.785 (0.03) | 0.794 / 0.796 / 0.444 |
| 10-31 16 | 1,934 | 0.771 | 0.766 | 0.774 | 0.467 | 0.808 (0.01) | 0.765 / 0.771 / 0.468 |
| 10-31 17 | 956 | 0.769 [0.863] | 0.808 [0.888] | 0.666 | 0.328 | 0.838 (0.08) | 0.796 / 0.782 / 0.332 |
| 11-01 07 | 428 | 0.570 [0.591] | 0.631 [0.643] | 0.682 | 0.629 | **0.964 (0.19)** | 0.629 / 0.612 / 0.678 |
| 11-01 08 | 786 | 0.532 [0.538] | 0.633 [0.631] | 0.711 | 0.660 | **0.891 (0.26)** | 0.573 / 0.552 / 0.699 |

Signature: nowcast >= report in every hour holds except 10-31 16 (-0.005); nowcast >= cheaper + 0.08 in the clean hours
fails (0.631 / 0.633 vs 0.629 / 0.660). Report-vs-nowcast disagreements on 11-01: 140, nowcast right 0.871. **The clean
block's at-touch posts are two processes: re-pegs after a futures move (a quarter of the posts; on the outcome whose
fair rose, 0.89-0.96) and "still" posts (no futures move in the last 0.45 s) that sit on the cheaper token (0.70) more
than on any reference posture (0.55-0.63).** On 10-31 (noise regime) only 1-8% of posts follow a futures move and the
still posts follow the report/nowcast (0.77-0.80; cheaper 0.33-0.47).

**T4 = X180 (ladder center per publish pass; `code16/ladder_center.py`, results/iter16_ladder_center.json).** Units =
(window, publish) with an exact 500/1000/2000 add on both outcomes in (P_i, P_i + 300 ms], non-extreme:

| block | units | half-spread h median (IQR) | c - mid on F_k - mid: slope / R2 (report k1.0, k1.4, k2.0, k3.0) | two-feature (nowcast k1.0): edge / (0.5 - mid) / R2 | center on cheaper side |
| --- | --- | --- | --- | --- | --- |
| 10-31 17:29-18:00 | 437 | 0.075 (0.060-0.095) | 0.31/0.52, 0.32/0.32, 0.12/0.04, -0.03/0.01 | 0.302 / -0.014 / 0.548 | 0.325 |
| 11-01 07:00-09:15 | 1,138 | 0.075 (0.055-0.100) | 0.09/0.03, 0.15/0.09, 0.16/0.12, 0.14/0.13 | 0.128 / **+0.090** / 0.173 | 0.637 |

Pre-registered readings: neither holds cleanly. The best k for c moves (1.0 -> 2-3: reading i), and the (0.5 - mid)
coefficient also changes sign (-0.014 -> +0.090: reading ii). With a digital, a larger k and a pull toward 0.5 are nearly
collinear, so the two readings are one family here. What is clear: the ladder geometry is the same (half-spread 0.075
on both blocks); what moved is the center: on 10-31 it moves 0.30 of the way from the mid to the Chainlink fair; on 11-01
only 0.13 of the way to the nowcast fair, plus a shrink toward 0.5 of 9% of (0.5 - mid) (about 2-4 c toward the
underdog at mids of 0.8-0.95). The shrink toward 0.5 is the same belief as the deep-bid module (buy the cheap loser); it
has not been seen on the noise block. Attenuation caveat: with a less informative reference in the clean regime the slope
on a mismeasured fair is biased toward 0 (the nowcast, a better measure, raises it from 0.09 to 0.15).

**X184 (assumptions P4, price on thin books; `code16/touch_price.py`, results/iter16_touch_price_1793512800_1793525100.json).**
Every cluster BUY fill of 11-01 06:00-09:25 with a recorder match ms (455; books: dw_clob for alt 5m/15m, clob_crypto
for BTC/ETH/SOL), share within a tick: alt 5m/15m (n 72) **touch (best bid of the bought token before the match) 0.722**,
touch - 0.01 0.611, ask - 0.01 0.597, R7 (last clean print - 0.01) 0.556, last print 0.431; BTC 5m/15m (n 383) touch
0.747, R7 **0.950**, last print 0.877. Per wallet R7 0.84-0.90 (bosona 0.897, mo-money 0.881, almach 0.843). On the alt
books the cluster's fills sit at the touch more often than at the stale print (median price - touch 0.00), but the touch
anchor is still below 0.80 there (n 72, one Sunday morning). Reading: on thin books the price is "join the best bid"
(a trivial anchor, a valid description), not R7; the 4h and hourly families had no recorded fills in this span. Not
adopted (one block, n 72); reported.

**X183 (assumptions P3, strict per-market replay of the idle module's decoded opening; `code16/idle_replay.py`,
results/iter16_idle_replay.json).** Alt 5m/15m markets the cluster traded (STUDY 781, VALIDATE 572 aggregate). Rule (frozen
T1d posture at st + 5 s, bid = last print - 0.01 at the family's off-session size, strict trade-through fills from
T + 2 s to end - 30 s on the clean taker tape, hold to resolution) vs the cluster's per-market PnL:

| fold | markets | rule side = cluster's first fill | rule Pearson / Spearman | oracle first-fill side Pearson / Spearman | cluster return |
| --- | --- | --- | --- | --- | --- |
| STUDY | 781 | 0.667 | 0.185 / 0.311 | 0.373 / 0.668 | +12.7% |
| VALIDATE | 572 | 0.612 | 0.084 / 0.105 | 0.417 / 0.697 | +2.8% |
| STUDY, first fill < 20 s | 283 | 0.855 | 0.402 / 0.653 | 0.422 / 0.726 | +12.0% |
| VALIDATE, first fill < 20 s | 193 | 0.751 | 0.305 / 0.394 | 0.428 / 0.710 | -2.3% |
| STUDY, first fill >= 20 s | 498 | 0.560 | 0.035 / 0.096 | 0.368 / 0.646 | +13.2% |

Signature (>= 0.5 both measures with the public posture; oracle >= 0.6) not met: even a perfect first-fill side gives
Pearson 0.37-0.43 under strict fills (Spearman 0.65-0.73), and 64% of the markets start later than the open, where the
rule's side is at chance (0.54-0.56). The outcome bar is out of reach on the idle families too: the later two-sided
fills (taker-chosen, where the module's money is) carry the per-market PnL.

**T5 part (c) (`code16/open_strike.py`, results/iter16_open_strike.json): the true strike with the Binance price is the
wrong comparison.** Opening alt fills (BUILD 1,860, STUDY 795, VALIDATE 400): posture against the stand-in strike 0.883 /
0.925 / 0.848, against Gamma priceToBeat 0.543 / 0.467 / 0.450; in the money 0.837 / 0.852 / 0.810 vs 0.609 / 0.547 /
0.555. The two strikes disagree on the in-the-money side for 35-44% of opening fills (median |K_standin / K_true - 1|
12-14 bp: the USDT/USD basis between Binance ETHUSDT-type prices and Chainlink USD), and there the stand-in is right
0.82-0.91, the true strike 0.15-0.20. So the opening decision compares like with like (a current price against the
average of the same series over the minute before the open), either Binance against Binance or Chainlink against
Chainlink (priceToBeat); Binance against priceToBeat is not what it does. Part (a) (per-symbol Chainlink at T - 2, which
separates the two) is being fetched (`code16/fetch_alt_cl.py`).

**X181 (mechanics P3, the fair cap on the main 500 ladder; `code16/fair_cap.py`, results/iter16_fair_cap.json).** Per
(window, publish, outcome) the top 500-class add within 300 ms after a public publish (10-31 17:29-18:00 1,278 units;
11-01 07:00-09:15 4,686) against min(touch_s, floor_tick(F_s - h)) with F from the report or the nowcast (k 1.0 / 2.0),
h in {0.03, 0.05, 0.075, 0.10}: within a tick **0.26-0.27 on 10-31 and 0.14-0.16 on 11-01** (best h 0.05; cap binding in
72-85% of units; 0.22-0.24 when capped, 0.35-0.41 when not); joining the touch 0.14 / 0.10, touch - 0.01 0.20 / 0.14;
only 7-9% of these re-adds are at or above the touch. Signature (>= 0.7 on the far side, at-touch state >= 0.85)
not met: rejected in this form. The re-signed rungs after a publish sit mostly below the touch, at prices neither the
touch nor a capped fair predicts (the earlier center-plus-half-spread fit reached 26-30% for the top rung, the same level).

**evaluate() end to end with the new blocks (development hour 11-01 08:00-09:00; .cache/re/directional-maker/
it16_eval_1101_08.json, ~4 min).** instance_mode: 4 qualifying slots, 2 split (08:00, 08:15; bosona), per wallet mid / deep
fills bosona 146 / 59, almach 15 / 50, mo-money 45 / 23. side_nowcast_match_clock (mid band, n 203): report 0.473, nowcast
**0.675**, cheaper 0.636 (by edge >= 0.1: 0.697 / 0.829 / 0.645). The counted live side (side_posture_match_clock, k 1.4,
Binance spot sigma) 0.670 vs cheaper 0.723; R7 price 0.932 (match clock 99%; per wallet 0.91 / 0.98 / 0.95).

**X182 part (a) (per-symbol Chainlink at the alt open; partial, VALIDATE fetched first; `code16/open_cl.py`).** priceToBeat
= mean CL[st - 61, st - 2] exactly on the verification windows (diff 0.0). VALIDATE ETH/SOL/XRP opening fills with a value
(n 256): the Binance stand-in and Chainlink-vs-priceToBeat disagree on the in-the-money side for only 3.5% (9 fills; the
panel's 11% was one Sunday morning), and on those 9 the cluster's side follows **Chainlink 9 of 9** (stand-in 0 of 9); in
the money 0.781 (stand-in) vs 0.816 (Chainlink), posture k 0.7 0.859 vs 0.879. VALIDATE halves (Chainlink posture) 0.945
vs 0.814: the reference does not explain the half split. STUDY and BUILD below once fetched.

**X186 light (information I15-4: are the alt quotes re-sided by the per-symbol Chainlink publish?; `code16/alt_publish.py`,
results/iter16_alt_publish_1793512800_1793525700.json).** 11-01 06:00-09:35, configured-size at-touch adds in dw_clob
(ETH 5m 50/150: 10,923; SOL 5m 50/100: 3,387; ETH 15m 30: 2,591; SOL 15m 30: 142; label purity NOT checked, other
makers use these sizes too), share on the outcome the latest ETH / SOL report change favours, posts within 300 ms after
a publish vs within 300 ms before it: ETH 5m 0.544 vs 0.507, SOL 5m 0.515 vs 0.456, ETH 15m 0.522 vs 0.509 (BTC 500s:
0.665 vs 0.429, X163). A weak publish-anchored signature at best (+0.01-0.06); the per-symbol futures race and the purity
check are still open (X186 stays open).

**X180 follow-up, own state (reported; `code16/center_inv.py`, results/iter16_center_inv.json).** Adding the cluster's net
position in the window (activity, block time <= P_i - 2 s) to the center regression: 10-31 (held the favourite in 77% of
units) R2 0.548 -> 0.548, (0.5 - mid) -0.014 -> -0.008; 11-01 (held the cheaper 30%, the favourite 24%) R2 0.173 ->
0.207, the center leans 1.4 c toward the held outcome, and the shrink toward 0.5 stays (+0.090 -> +0.082). **The 11-01
shrink toward 0.5 is not inventory management**; it is a setting of the center's fair.
Center regression (nowcast edge, cheapness) by half hour on 11-01: 07:00 0.05 / 0.09 (R2 0.13), 07:30 0.105 / 0.179
(0.33), 08:00 0.226 / 0.04 (0.16), 08:30 0.067 / 0.075 (0.12), 09:00 0.035 / -0.023 (0.01; n 65); by family 5m 0.131 /
0.083, 15m 0.130 / 0.103; 10-31 17:30 (433 of 437 units BTC 15m) 0.302 / -0.014 (R2 0.55). The 11-01 center is a weak
and drifting function of the reference within the block (not one setting per block), in 5m and 15m alike.

**Pre-registration T6 (written 09:45 UTC, before computing; source: T2's band table on the live blocks).** Candidate
R8b side (public, per fill) = decided window (|mid - 0.5| > 0.4) -> cheaper token; else |F_cl - mid| < 0.05 (the dead
zone, where bosona's fills fell below chance on 11-01) -> cheaper token; else the Chainlink posture (as R8). Scored on the
lot's typed fills (it12/typed_fills.parquet: real-Chainlink posture, Binance stand-in where missing) per fill, STUDY and
VALIDATE (aggregate). Adopt R8b only if VALIDATE improves by >= 0.01 over R8's public side and STUDY does not fall by
more than 0.01. The band 0.05 is fixed (no scan).
**T6 result (`code16/band_side.py`, results/iter16_band_side.json): R8b rejected.** Per fill: VALIDATE R8 0.6925 vs R8b
0.6862 (-0.006; halves 0.680 / 0.701 vs 0.653 / 0.709), STUDY 0.569 vs 0.521 (-0.049). The dead zone (|F_cl - mid| <
0.05, not decided) is 36-37% of the lot's fills, and there the Chainlink posture still beats the cheaper token (VALIDATE
0.632 vs 0.614, STUDY 0.568 vs 0.437). The below-chance dead zone of 11-01 (bosona 0.44) is specific to that block; R8
stays.

**X182 part (a), final (`code16/fetch_alt_cl.py` 1,915 endpoint requests in 30 min, no failures; `code16/open_cl.py`,
results/iter16_open_cl.json).** ETH / SOL / XRP 5m/15m opening fills (< 20 s), the per-symbol Chainlink value at T - 2
against Gamma priceToBeat (verified = mean CL[st - 61, st - 2] to < 1 bp on six windows) vs the Binance stand-in:

| fold | n | itm side disagreement | in the money: stand-in / Chainlink (on the disagreements) | posture k0.7 vs last print: stand-in / Chainlink (on the disagreements) |
| --- | --- | --- | --- | --- |
| BUILD | 1,754 | 3.6% (63) | 0.832 / 0.840 (0.381 / 0.619) | 0.890 / **0.916** (0.841 / 0.984) |
| STUDY | 741 | 2.3% (17) | 0.849 / 0.866 (0.118 / 0.882) | 0.931 / **0.941** (0.647 / 0.765) |
| VALIDATE | 323 | 2.8% (9) | 0.796 / 0.824 (0.000 / 1.000) | 0.864 / **0.882** (0.889 / 0.889) |

VALIDATE halves (Chainlink posture): 0.943 / 0.824 (stand-in 0.911 / 0.818). Reading: the opening bid reads the
settlement-grade per-symbol Chainlink against the published strike: it is the better reference on every fold (+0.01 to
+0.03) and wins the in-the-money disagreements on STUDY (15 of 17) and VALIDATE (9 of 9), less clearly on BUILD (39 of
63). But the two references disagree on only 2-4% of opening fills (the panel's 11% was one Sunday morning), so the
reference explains little of the opening posture's 6-12% error, and the VALIDATE half split (0.94 vs 0.82) is not a
reference artefact. Panel signature (>= 0.85 of the disagreements on every fold; >= 0.90 on every fold within 0.03 across
halves) not met. The alt opening side is now 0.88-0.94 on public settlement-grade inputs (13% of the non-BTC fills).

## Iteration-16 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). R8 stays frozen; no frozen decision changed (the one candidate change, R8b, failed its pre-registered
  VALIDATE test). Two reported blocks added to evaluate() (`code/r10_mode.py`: `instance_mode`, `side_nowcast_match_clock`;
  end-to-end smoke test on 11-01 08-09 in ~4 min). target_metrics unchanged (union presence 0.788 / 0.780; selection 0.685
  / 29.5% / 2.87; side 0.693 / 0.679; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891). The primary unit's oracle
  ceiling (~0.80 with the cluster's actual quote, X72) is now stated next to it in target_metrics.
- Paradigm: engine instances and the clean-regime quote (who runs the main ladder, the same instance across regimes, a
  point-in-time nowcast reference, the ladder center per publish pass), plus the idle module's outcome replay, thin-book
  price anchors and the settlement-grade per-symbol reference at the alt open.
- What it showed: (1) the 11-01 single-instance mode is a 75-90 minute transient after the listing gap (0 of 466 STUDY /
  VALIDATE slots, 0.9% of BUILD slots); (2) inside bosona the large-edge side is unchanged across the regimes (0.86 / 0.86)
  while small-edge fills fell below chance on 11-01, so the failure is not composition; (3) the nowcast (report + futures
  move since its stamp) is never worse than the report and adds +0.06-0.12 on the clean block (still not cheaper + 0.08);
  a quarter of the clean block's at-touch posts are futures re-pegs (0.89-0.96); (4) the ladder's half-spread is the same
  on both blocks (0.075) and only the center's dependence on the reference moved (0.30 -> 0.13 of the fair-minus-mid gap,
  plus a shrink toward 0.5 that inventory does not explain, drifting within the block); a capped-join law fails (0.14-0.27);
  (5) the idle module's decoded opening, replayed strictly, tracks per-market PnL at 0.08-0.19 Pearson (oracle side
  0.37-0.43): the outcome bar is out of reach there too; (6) on thin alt books the fill price is the best bid (0.72) rather
  than R7 (0.56); (7) the alt opening reads the per-symbol Chainlink against priceToBeat (posture 0.88-0.94; it wins the
  rare disagreements with the Binance stand-in), and Binance against the true strike is a basis-mismatched comparison;
  (8) the alt quotes show at most a weak publish-anchored re-siding (+0.01-0.06); (9) R8b (dead zone -> cheaper) is worse
  on VALIDATE (-0.006) and STUDY (-0.049).
- Closed this iteration: X177, X178, X179, X180, X181 (rejected), X182, X183, X184, X160, X61, X103 (tried); X191, X192,
  X193 (ruled out by the panel's measurements); X194 (R8b, tried and rejected); X185 (prices-history, after the checkpoint below). New open: X186, X187, X188, X189, X190.
- Laptop clock: dy_rtds offset 1.315 s (Binance minus laptop) at 09:26 UTC, w32tm not synchronized: **the user should
  resync Windows time** (agents may not change system settings); the own readers filter by server stamps.

**Next steps (iteration 17, the last ~58 budget minutes).**
1. Exam readiness: run evaluate() once on the full development block 11-01 06-12 after 12:00 (all blocks, per wallet and
   pooled) and record it; keep R8 frozen.
2. X188 light: the resting state at each print on 11-01 07-12 (fills vs the 500 orders live at the touch from
   dm_clob_raw adds and removes), to measure how much of the print-selection oracle gain a public post/cancel hazard
   recovers.
3. Wire the prices-history daily posture (X185: 0.74-0.75 on the later daily fills) and the per-symbol Chainlink opening posture (X182: 0.88-0.94) into r9_nonbtc as reported metrics; X190 (makerOrders queue positions) if time.

**X185 step 1 (information I15-1; `code16/ph_semantics.py`, results/iter16_ph_semantics.json): a CLOB prices-history
point is the preceding minute's mid.** BTC 4h 10-31 12:00 window (development; Up token; 227 fidelity-1 points vs the
shared recorder's 19,511 book records): median |p - X| = 0.0049 for the mean mid over [t - 60, t) (50% within 0.005), 0.005
for the mid at t - 30 / t, 0.012 for the mean over the next minute, 0.010 for the last trade. So a point stamped t is a
summary of the minute before t: usable at t (effective age ~30 s), an examinable market state for the unrecorded hourly
and daily families.

**Pre-registration X185 steps 2-4 (written 09:53 UTC, no fitting, before any score):** the cluster's later BUY fills
(>= 20 s after the open) of the hourly, daily and 4h families on STUDY and VALIDATE (aggregate); market state = the last
prices-history point of the bought token stamped <= T - 1 (fidelity 1). Side rules: posture = 1[F_s > mid_s], F = the
Binance digital of iteration 15 (S(T - 3) vs the family's strike, sigma = 1.0 x the symbol's 300-s Binance vol); baselines
market favourite (mid_s > 0.5) and cheaper token, both from the same mid. Price rules: fill price within a tick of
mid_s - 0.01, mid_s and mid_s - 0.02. Panel signature: later-fill side >= 0.75 per family on VALIDATE and >= the
mid-based favourite + 0.10; price within a tick >= 0.75.

**X185 steps 2-4 (`code16/ph_long.py`, results/iter16_ph_long.json; 864 token histories, every later fill matched).**
Later BUY fills (>= 20 s) of the long families against the prices-history mid of the bought token (stamped <= T - 1):

| fold, family (n) | posture vs mid (k 1.0) | market favourite (mid) | cheaper (mid) | price within a tick of mid - 0.01 / mid / mid - 0.02 | fill - mid median |
| --- | --- | --- | --- | --- | --- |
| STUDY hourly (1,785) | 0.625 | 0.705 | 0.292 | 0.257 / 0.262 / 0.221 | -0.005 |
| STUDY daily (717) | **0.753** | 0.593 | 0.403 | 0.523 / 0.548 / 0.368 | -0.005 |
| STUDY 4h (594) | 0.704 | 0.771 | 0.221 | 0.444 / 0.365 / 0.411 | -0.020 |
| VALIDATE hourly (1,395) | 0.515 | 0.564 | 0.430 | 0.315 / 0.292 / 0.257 | -0.015 |
| VALIDATE daily (953) | **0.736** | 0.513 | 0.485 | 0.452 / 0.485 / 0.344 | -0.005 |
| VALIDATE 4h (470) | 0.547 | 0.547 | 0.443 | 0.434 / 0.298 / 0.457 | -0.020 |
| VALIDATE all (2,818) | 0.595 | 0.544 | 0.451 | 0.381 / 0.358 / 0.320 | -0.015 |

Signature (>= 0.75 per family on VALIDATE and >= favourite + 0.10; price >= 0.75) not met. The DAILY family's later
fills follow a Binance-digital posture against the minute mid at 0.74-0.75 on both folds (+0.16-0.22 over the mid-based
favourite): the first public side rule for the daily fills (iteration 15 had them at 0.45-0.50 in the money). Hourly and
4h later fills stay at the market-favourite level, and no fixed offset from the minute mid prices the fills (0.22-0.55):
on these thin books the price is not a mid-minus-constant quote. Prices-history is examinable for sealed units (one
request per token), so this is a usable reported metric for a weekend lot.

**r9_nonbtc now also reports the long families against prices-history (X185; `code/r9_nonbtc.py` PRICES_HISTORY, reported,
not counted):** per group / phase / wallet / half `posture_prices_history_k1.0` and `mktfav_prices_history` (one
prices-history request per bought token). Smoke test 11-01 06:00-10:00 (36 s): hourly later fills posture 0.644 vs
favourite 0.814 (n 59), all non-BTC 0.675 vs 0.608 (n 83). Known gap: for markets still open (the 11-01 dailies)
`fetch_windows` returns no Gamma record, so the daily strike is missing and the daily posture is not scored; on resolved
markets (any exam lot) the strike is available.

**X189 step 1 (mechanics P4: purity of the alt configured sizes; `code16/purity_alt.py`, results/iter16_purity_alt_
1793520000_1793521200.json).** All-match calldata of every dw_clob trade transaction of 11-01 08:00-08:20: filled maker BUY
orders at non-extreme prices with the family size that are the cluster's: ETH 5m 50 **0.00 (n 138)**, SOL 5m 50 0.00 (33),
XRP 5m 10 0.00 (19), XRP 15m 10 0.00 (25), ETH 15m 30 0.026 (39), ETH 5m 150 1.00 (1); the cluster had only 2 filled alt
orders in the slice. The small configured sizes are other makers' sizes too (the panel's "if false" branch): the alt
module stays a fill-level description, and X186 light's publish-anchored test above was run on impure labels (mostly
other makers), so it says nothing about the cluster.

**X187 steps 1-2 light (information I15-5: the 4h ladder; `code16/purity_4h.py`, `code16/q4h.py`, results/iter16_purity_4h_
1793448000_1793469600.json, iter16_q4h_1793448000_1793469600.json).** All-match calldata of the 528 BTC/ETH/SOL 4h trade
transactions of 10-31 12-18: filled maker BUY orders at non-extreme prices: **BTC 4h 400 = the cluster's (purity 1.00,
n 19)**; BTC 4h 600 0.00 (64) and ETH 4h 300 0.00 (10) are another maker's (the panel's caution was right); the cluster's
other 4h orders are pairing-size bids (107.83, 191.98). With the pure label, every +400 bid-level increase in the shared
recorder's Up book (Down bids read as Up asks) of the 10-31 12:00 and 16:00 BTC 4h windows (3,148 adds, 2,456 scored): the
add sits on the cheaper outcome **0.666** (always-Up 0.649), on the Chainlink-posture side 0.388 (k1.0) / 0.521 (k2.0) /
0.590 (k4.0); only 3% at or above the touch; it rests a median **0.05 below the touch and 0.065 below the mid** (IQR
0.045-0.085). The BTC 4h module is a resting ladder about 5-7 c under the market that leans to the underdog, not a
Chainlink-skewed touch quote: its fills are takers' sweeps of 5+ c, which is where the iteration-15 4h profit (+4.8-8.4%
per $) comes from. Next: its price law (mid minus a constant per rung) and whether the rung distance depends on time left.

Addendum to the iteration-16 checkpoint (10:05 UTC): also closed X189 (purity of the alt configured sizes: other makers)
and advanced X187 (BTC 4h 400 is a pure cluster label; the 4h ladder rests 5-7 c under the market and leans to the
underdog); X186 stays open (its light test used impure labels). Second end-to-end evaluate() smoke test on 11-01 08-09
after the r9 change: all blocks ran (r9 prices-history posture n 12 in that hour). Open catalog: 38 items.

**Correction to T1 / X177 (10:06 UTC, the block through 10:00):** mid-band BTC 5m + 15m BUY fills per 15-min slot
(bosona / almach / mo-money): 07:00 35/0/0, 07:15 20/5/3, 07:30 82/2/0, 07:45 33/0/0, 08:00 24/0/0, 08:15 48/0/0, 08:30
21/4/12, 08:45 53/11/33, 09:00 35/4/12, **09:15 65/0/0, 09:30 58/9/3** (09:45-10:00 partial, bosona only). The split holds in
7 of the 10 qualifying slots of the block; mo-money (and a little almach) joined the main ladder only in 08:30-09:15. So
on 11-01 the main BTC ladder runs mostly in bosona alone, with almach and mo-money on deep bids and the slow families: a
mode of the whole development block so far, not a 75-90 minute transient (the earlier reading is withdrawn). It never
occurred in a STUDY/VALIDATE slot and in 0.9% of BUILD slots, so it is new after the sealed stretch 10-31 18:00 - 11-01
06:00. For the exam: if a sealed block runs in this mode, almach's and mo-money's BTC fills are mostly deep bids (R8's
decided branch, i.e. the cheaper token), and the per-wallet replication will compare different modules; evaluate()
reports `instance_mode` per slot so the examiner sees it.

**X187 step 3 light (the 4h rung depth; `code16/q4h.py`).** Median depth of the cluster's 400 adds below the token's mid:
0.055 with 0.5-4 h left, **0.08 in the last 30 min** (n 1,039); by the token's mid: 0.055 below 0.5 (the underdog), 0.065
at 0.5-0.7, **0.085 at >= 0.7** (the favourite's bid sits deeper). Within a tick of mid - 0.05 / 0.06 / 0.07: 0.36 / 0.39
/ 0.38; touch - 0.05: 0.40. The 4h ladder is asymmetric (underdog bid ~5.5 c under the mid, favourite ~8.5 c) and widens
near the end; a single offset prices only ~40% of the adds within a tick.

Tooling notes (iteration 16): `tools/live.py iter_live` raises `zlib.error` on a corrupt gzip member of the shared
recorder's clob_crypto files of 10-31 12-16 (and of dm_bnf hour 14:00), ending the iteration for that hour; the own
tolerant reader (`code5/rawread._members`, used by `final_rule._iter_live_xq`) skips such members, so every scoring script
of this iteration that reads clob_crypto goes through it. `polyrea.workflows.updown_study.fetch_windows` returns no record
for daily markets that are still open (11-01 dailies), so r9's daily strike is missing on a live block; not a data error
on resolved markets.

**X185 extension (post hoc, same frozen rules; `code16/ph_alt.py`, results/iter16_ph_alt.json): the alt 5m/15m later
fills against the prices-history minute mid.** Posture (Binance digital k 1.0 vs the minute mid) VALIDATE alt 5m 0.604 /
15m 0.625 (STUDY 0.642 / 0.700) vs the mid-based favourite 0.48 / 0.42 (0.54 / 0.52); but the fill sits a median 1.5-8 c
ABOVE the minute mid (price within a tick of the mid 0.03-0.15): for 5-15-minute windows a one-minute summary is too
stale to be the market state. Prices-history is the right state for the 4h / hourly / daily books, not for the alt 5m/15m.
(Iteration 16 ended about 10:12 UTC 11-01, about 72 minutes; the shared recorder and the own recorders examrec, dy_rtds,
dz_rtdsbn, dw_clob, dv_rtds and the delayed full-depth dm_* recorder (to 12:00) are running.)

## Iteration 17 (started 2026-11-01 10:46 UTC; 1,113 of 1,200 minutes used)

Situation: the last ~87 budget minutes. Development block 11-01 06-12 UTC is recording (shared recorder; own dy_rtds,
dv_rtds, dw_clob, dx_*, the delayed full-depth dm_* to 12:00). The three iteration-16 panels agree that the 11-01 brief
mandate (hidden dimensions, E1-E7) was never started: no `dimensions` or `indicators` ledger, no "Missing dimensions"
section, `residual_clustering` never run although the cluster quotes 5-20 markets at once. The workflow requires a
pivot (progress flat for three iterations). **Pivot: the residual becomes the target.** Instead of tuning the quote
model, this iteration studies what the best rule fails to explain: out-of-fold misses on BUILD (E2), their synchrony
across markets and assets (E7), and the counterparty (taker) dimension of each fill from V2 calldata (the taker's
commit-to-match latency and identity) as a new unit and a new data source (information panel P1/P2, assumptions P1).

Competing explanations of the money, this iteration (dimension status in `dimensions`; what tells them apart):
- H1 taker-censored side (dimensions: taker commit times [have, calldata], the venue's 150-ms taker hold [have, venue
  metadata]): the cluster quotes around a Chainlink-led fair; which outcome fills is chosen by the takers who arrive.
  The 11-01 fall of the side accuracy is a change in the taker mix. Tell: side accuracy per taker-latency class and
  edge band is stable across 10-31 and 11-01, and 10-31's class x band accuracies reweighted by 11-01's shares
  reproduce 11-01's accuracy within 0.03.
- H2 a faster hidden reference (dimension: Chainlink Data Streams low-latency reports [blocked: credentials], the
  Polymarket Perps index [missing: live-recordable]): misses are side errors where the public report is stale. Tell:
  misses coincide across BTC and ETH/SOL markets at second scale (E7 ratio >= 1.5, p <= 0.01) well above the hits.
- H3 an engine-wide risk state (dimension: per-account mark-to-market / drawdown [proxy from activity]): tilt and
  switch-offs come from a risk controller. Tell: misses cluster within one account across markets more than across
  accounts; they bunch in episodes of minutes to hours, not seconds.
- H4 operator pushes (dimension: operator actions [missing; inferred from salt resets, instance changes]): the side
  rule changes in discrete steps. Tell: the miss rate has hour-scale episodes and change points, no second-scale
  synchrony.
- H5 local liquidity provision (dimensions: book, tape [have]): misses are idiosyncratic per market, explained by local
  sweeps. Tell: miss synchrony ratio ~ hit synchrony ratio (~1.1), misses concentrated at small |F - mid|.
- H6 (unlikely) a copied provider or sibling (dimension: other wallets' orders [have via tapes]). Tell: misses align
  with one other wallet's prints at a fixed lag (not tested this iteration).

**Pre-registration (written 10:52 UTC 11-01, before any number below was computed).**
- T1 = E2 presence, out of fold: BUILD 10-09..22 BTC 5m (window, side, 10-s bin) cells (panel2_day); LightGBM with
  train2 PARAMS / 300 rounds, GroupKFold(5) over 2-h blocks of the window start; rule features = all_path_xwin + clock,
  baseline = activity. Report OOF AUC (rule, baseline) and the miss shape: FN = filled cells below the OOF 85th
  percentile, FP = unfilled cells above the OOF 99th percentile; by UTC hour, weekday, US session, time in window,
  |edge_s| band and vol tercile. Unexplained share = FN / filled cells.
- T2 = E2 side: BUILD fills, one decision per (transaction, token) over the three accounts: BTC 5m with R8's public
  side (decided |mid_up - 0.5| > 0.4 -> cheaper; else Binance posture fair_s > mid_s), non-BTC families with the
  iteration-15 rule (`rule_ok` of it15_nb_side). Misses = wrong side. Shape by hour, weekday, time in window, band,
  family.
- T3 = E7: `residual_clustering` (delta_s 2 s, 1,000 null draws, market = window) on the T2 misses and, as the
  control, on the T2 hits: (a) 5m + 15m families, period_s 900; (b) with hourly, period_s 3,600; (c) BTC vs non-BTC
  only (cross-asset pairs). Synchrony counts only with p <= 0.01, ratio >= 1.5 AND a miss ratio at least 0.3 above
  the hit ratio (else it is shared co-activity).
- T4 = X196 (information P2): every cluster BTC 5m/15m mid-band BUY fill with a match ms on 10-31 14:00-16:53 and 11-01
  07:00-10:50 joined to its calldata; L = match ms - taker sign ms; classes auto <= 300 ms, mid 0.3-2 s, slow > 2 s;
  side by block x class x |F1 - mid| band (report k1.0, nowcast k1.0, cheaper). Reading: |reweighted - actual 11-01|
  <= 0.03 -> the 11-01 regime is the counterparties; else the cluster's quote changed. Taker hold (X195 part): the
  floor (p1/p5) of L over all matched takers >= 150 ms on both blocks.
- T5 (E3 direction, added 10:57 UTC after the BUILD residual below and BEFORE any lot number): on NYSE trading days the
  BTC 5m window that starts at the NYSE open (09:30 America/New_York; 13:30 UTC in the lot) holds the cluster's fills
  on the cheaper token. Scored per fill on the lot's typed fills (it12/typed_fills.parquet; STUDY 10-23 Fri and 10-26
  Mon case by case, VALIDATE 10-27..30 aggregate): R8's public side vs R8c = R8 with that window -> the cheaper token.
  Signature: in the open window the cheaper token >= 0.75 on both folds and R8c - R8 >= +0.15 there. Adopt R8c only
  if, in addition, the VALIDATE per-fill accuracy over all BTC 5m fills does not fall. Reported, not part of the rule:
  the 13:35 window and the BTC 15m window starting at the open.

### Iteration 17 results (10:53-11:06 UTC 11-01)

**T1 = E2 presence, out of fold (`code17/e2_resid.py presence`, results/iter17_e2_presence.json).** BUILD 10-09..22, 241,920
BTC 5m cells, 12,872 filled. OOF AUC (GroupKFold(5) over 2-h blocks): **rule 0.780, activity 0.741** (gain +0.039; the
BUILD out-of-fold analogue of VALIDATE's 0.716 / 0.684). 54% of filled cells fall below the OOF 85th percentile (FN);
66.5% of the top-1% cells are unfilled (FP). FN share by |edge_s|: < 0.05 **0.74**, 0.05-0.1 0.58, 0.1-0.2 0.32, 0.2-0.4
0.14, >= 0.4 0.04. By activity: FN 0.73 when the activity-only model ranks the cell below its top 15%, 0.25 above. By
weekday: Mon-Fri 0.60-0.68, Sat/Sun 0.40. By hour: 13-15 UTC 0.39-0.46, 01 and 06 UTC 0.67-0.69. By time in window: the
last minute 0.26 (deep end-of-window bids), 60-180 s 0.63. By 300-s vol tercile: low 0.36, mid 0.66, high 0.62. Reading:
the presence rule finds the fills that a large reference edge or visible activity announces; it misses quiet
small-edge cells, where a fill needs one taker to arrive (the counterparty's timing), on weekdays and in mid/high vol.

**T2 = E2 side (`code17/e2_resid.py side`, results/iter17_e2_side.json).** 58,092 BUILD decisions (one per tx x token over
the three accounts; BTC 5m 46,021 with R8's public side on the Binance stand-in, non-BTC with the iteration-15 rule):
miss share **0.377**. By family: BTC 5m 0.379, ETH 5m 0.422, ETH 15m 0.420, BTC hourly 0.328, dailies 0.55-0.60 (later
fills), alt 5m/15m 0.14-0.38. By time in window: first 10% 0.286, last 10% 0.496. By |fair_s - mid_s| (BTC 5m): < 0.05
0.414 down to 0.307 at >= 0.2. By hour: **13 UTC 0.556** (n 3,590; every other hour 0.26-0.46). Weekdays at 13 UTC 0.614
vs weekends 0.451. Inside 13 UTC it is one window: **the BTC 5m window 13:30-13:35 UTC on weekdays, the NYSE open**: 702
decisions in 10 windows (70 per window vs ~16 elsewhere), miss share **0.899**, mean price 0.234, won 0.40, +0.166 per
share (vs +0.012 elsewhere); four of the ten windows won big (10-09, 10-12, 10-13, 10-22), the others lost. Other weekday
slots with high miss shares (06:15 0.86, 22:00 0.81, 07:45 0.79, 08:00 0.79, 17:00 0.74, 16:00 0.73) mostly LOST (won
0.03-0.26 at prices ~0.3): adverse fills of cheap-side bids, a different pattern (X211, open).

**T3 = E7 (`code17/e2_resid.py`, results/iter17_e2_side.json `e7`).** residual_clustering, delta 2 s, 1,000
period-shift draws:

| set | misses: ratio / p (n) | hits (control): ratio / p (n) |
| --- | --- | --- |
| (a) 5m + 15m families, period 900 | 1.44 / 0.227 (19,848) | 2.22 / 0.013 (32,471) |
| (b) with hourly, period 3,600 | 1.50 / 0.183 (20,738) | 1.95 / 0.014 (34,720) |
| (c) BTC vs alt only, period 900 | 1.34 / 0.044 | 2.04 / 0.044 |

The pre-registered bar (p <= 0.01, ratio >= 1.5, miss ratio >= hit ratio + 0.3) is met in no set: **the fill-level side
residual has no common second-scale driver**; it is idiosyncratic per market (H2 not supported at the fill level, H5
consistent). The hits are the synchronized ones (cross-market bursts on the posture side: sweeps after moves).
Exploratory (not pre-registered; assumptions P1 step 3, the cluster's own at-touch posts, BTC 5m + 15m, period 900,
results/iter17_e7_quote_unit.json): 10-31 14-18 misses 1.62 / p 0.010 vs hits 1.49 / 0.001 (difference 0.13 < 0.3: the
engine's shared pass); **11-01 07:00-09:15 misses 3.52 / p 0.007 vs hits 1.80 / 0.24**. The 11-01 synchronized miss
posts follow a futures move >= $2 in the 450 ms before in 40% (isolated misses 19%, hits 9-22%), on the outcome whose fair
rose in 93% (results/iter17_e7_quote_unit_futures.json): the common driver of the clean-block residual is largely the
futures move (a dimension we have: the nowcast / re-peg); 60% of the synchronized misses have no such move.

**T4 = X196 taker information class (`code17/taker_class.py`, results/iter17_taker_class.json).** 3,089 cluster BTC
5m/15m BUY fills with a match ms; 1,858 transactions' calldata were cached, 1,171 fetched; 2,817 fills with L. Taker hold:
**L p5 193 ms (10-31) / 187 ms (11-01), p10 202 / 192, median 640 / 376 ms**: the floor agrees with the 150-ms hold plus
transit (the information panel's reading is confirmed). Classes (mid band, with L): auto (<= 300 ms) 31% on 10-31, 45% on
11-01. Side accuracy (report k1.0) per class, 10-31 vs 11-01: auto 0.914 vs 0.712, mid 0.855 vs 0.603, slow 0.802 vs 0.708
(cheaper 0.40-0.56 vs 0.74-0.80). Pre-registered reweighting (10-31 class x band accuracies with 11-01 shares): report
**0.844 predicted vs 0.675 actual** (bosona 0.880 vs 0.729), nowcast 0.840 vs 0.723: the difference is far above 0.03, so
**the 11-01 drop is not the counterparties**; it is inside every taker class, mostly in the small-edge band (auto takers
0.963 (n 27) -> 0.478 (n 115)). In the large-edge band the posture holds on 11-01 for auto takers (0.872 report, 0.915
nowcast). H1 rejected. Note: in 252 of the 10-31 transactions (18 on 11-01) the taker order is a cluster account's own.

**T5 = X210 (R8c, pre-registered 10:57 UTC; `code17/nyse_open.py`, results/iter17_nyse_open.json).** The BTC 5m window
starting at the NYSE open (09:30 America/New_York on weekdays) -> the cheaper token:

| fold | open-window fills (windows) | cheaper | R8 (= posture there) | mean price | all BTC 5m fills: R8 -> R8c |
| --- | --- | --- | --- | --- | --- |
| STUDY 10-23 Fri, 10-26 Mon | 107 (2) | **0.991** | 0.402 | 0.189 | 0.5693 -> 0.5769 |
| VALIDATE 10-27..30 (aggregate) | 513 (4) | **0.899** | 0.442 | 0.282 | **0.6925 -> 0.7009** |

The signature is met on both folds and VALIDATE does not fall: **R8c adopted** (code/side_sm.py: counted side
`r8c_no_own_state`; R8's `no_own_state` is still reported). The next window (13:35) follows the posture on VALIDATE
(0.976) but not on STUDY (0.424; not part of the rule). Caveat for the exam: all development data is under US DST, where
the NYSE open is 13:30 UTC; from 11-02 it is 14:30 UTC. The rule follows the exchange clock (09:30 New York), the
economically grounded choice; if the operator keys a fixed 13:30 UTC instead, the rule misses after the DST change
(hypothesis; not separable on development data).

## Missing dimensions (E2, iteration 17; out-of-fold BUILD residuals)

- **Which component fails.** Presence (timing): 54% of filled BTC 5m cells are scored low out of fold, mostly at
  |edge| < 0.05 and in quiet cells (no visible activity). The side is right at large edges (0.86-0.91 on the live match
  clock) and wrong at small ones (0.41 miss share at < 0.05). By the brief's map: "side right, timing wrong" at large
  edges points to a missing trigger (the taker's arrival, which no public series shows before the match; the 150-ms hold
  makes it visible only to the engine); "timing right, side wrong" at small edges and at scheduled events points to a
  valuation input (the NYSE-open behaviour, now in R8c; the sigma multiplier k of the noise vs clean regimes, C5).
- **Unexplained shares.** Presence: AUC 0.780 out of fold on BUILD (FN 54% at the 85th percentile). Side: 37.7% misses
  per BUILD decision; 29.9% per VALIDATE fill after R8c. Price: R7 within a tick 0.80 (VALIDATE block clock), 0.93-0.95 on
  the match clock. Size: the schedule (500 / 1,000 / 2,000 and per-family configured sizes) explains the main sizes; the
  pairing sizes are own state.
- **When.** Weekdays (presence FN 0.60-0.68 vs 0.40 at weekends); 01 and 06 UTC worst for presence; the NYSE-open window
  is the side outlier (miss share 0.90; R8c); other market-structure slots (06:15, 22:00 = CME reopen, 07:45-08:00 =
  Europe opens) show cheap-side fills that lose (X211).
- **Synchrony (E7).** Fill-level side misses: no excess (ratios 1.34-1.50, p 0.04-0.23; hits 1.95-2.22). Quote-unit
  misses on 11-01: excess across the 5m and 15m windows (3.52, p 0.007), 40% of it futures re-pegs. There is no
  fill-level cluster time to look up in news archives; the 11-01 clusters point to the futures feed, which we have.
- **Lead.** Not re-run this iteration (legacy: reactions 0-250 ms after futures moves and Chainlink publishes; no
  decision precedes every public feed).
- **Who else.** Not run (X209 open).
- **Dimensions it points to.** (1) the counterparty's arrival (`pm_taker_commit_times`: available only after the match;
  the class mix is not the driver, X196); (2) the scheduled market calendar (`us_equity_market_open`: drives, R8c;
  `official_calendars_macro`: 12:30 UTC not elevated); (3) the futures move (`binance_usdm_futures`, have: the 11-01
  synchronized misses); (4) a regime / multiplier state (C5; an E6 latent: the noise vs clean Chainlink regime) for the
  small-edge side.

**Pre-registration of the first E3 screen (written 11:05 UTC).** Dimension
family: the scheduled market-structure calendar. Events (first occurrence per day, weekdays and weekends separately):
NYSE open 09:30 New York, NYSE close 16:00 New York, CME Globex reopen 18:00 New York, US macro release times 08:30 and
10:00 New York, Europe opens 08:00 London and 09:00 Frankfurt, the 00:00 UTC rollover, the 01:00 UTC cluster restart.
Decisions: the B1 signing times of the cluster's filled BTC 5m/15m orders (calldata samples on BUILD), and the quote-unit
posts on the live blocks; lags +-60 s and +-600 s (max_lag_s 1,200), 1-s bins, swap null by window with hour-of-week
strata. Signed version: the side relative to the cheaper token. Gates: |F - mid| < 0.1 and >= 0.1. BH over the family on
BUILD (q <= 0.10), confirmation once on VALIDATE (one-sided alpha 0.01, Holm).

**R8c across the whole history (C4 check, post hoc, activity only; it12/hist_btc.parquet May 22 - Oct 8, weekday BTC 5m
BUY fills of the cluster; "cheap" = fill price < 0.5).** The 13:30 UTC window (the NYSE open under US DST) is busy in every
month (30-73 fills per window vs 14-31 in the other windows), but its cheap-side share is NEW in October: May 0.06 (rest
0.17), June 0.10 (0.47), July 0.36 (0.60), August 0.46 (0.56), September 0.64 (0.70), **October 1-8 0.997 (0.59)**, then
BUILD 10-09..22 ~0.9, STUDY 0.99, VALIDATE 0.90. Before October the cluster bought the favourite at the open. On the four
NYSE holidays (05-25, 06-19, 07-03, 09-07) the window was an ordinary one (14.8 fills per window), so the busy open is the
equity open, not the UTC clock. So R8c describes the October configuration (a bot version, C4): valid on every October
fold, at risk if the configuration changes again, and untested across the 11-02 DST change. Weekend 13:30 windows: 26.8
fills per window, cheap 0.42.

**evaluate() smoke test with R8c** (VALIDATE slice 10-27 13:25-13:45, aggregate; .cache/re/directional-maker/
it17_eval_1027_1325.json): counted side `r8c_no_own_state`, 91 of 225 BTC 5m fills in the open window; R8c 0.742 vs R8
0.498 on the slice (per wallet 0.61-0.80); the BTC 15m path runs (no open-window fills; the rule is 5m only). The 'local'
mode has no cluster fills after 10-23 (cached activity ends at H), so the smoke test used the API path.

## Iteration-17 checkpoint
- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). One frozen decision changed: **R8 -> R8c** (the NYSE-open BTC 5m window -> the cheaper token),
  adopted on its pre-registered test; target_metrics side_accuracy 0.6925 -> **0.7009** (cheaper baseline 0.6785). The
  other target metrics are unchanged (union presence 0.788 / 0.780; selection 0.685 / 29.5% / 2.87; price 0.803; pnl 0.207
  / 0.218; coverage 0.868 / 0.891). The target is not met; the budget (1,200 minutes) is used up with this iteration.
- Paradigm (pivot): the residual became the target. Out-of-fold BUILD misses (E2) and their cross-market synchrony (E7),
  the counterparty dimension from calldata (taker commit-to-match latency, the 150-ms hold), and the scheduled market
  calendar found in the residual.
- Brief mandate of 11-01 done: E1-E7 in the catalog; `dimensions` (41 entries over every family, plus the panel-named
  ones); `indicators` (legacy rows from the hypotheses ledger, plus this iteration's E7, X195, X196, T5 rows); "Missing
  dimensions" above; the first E3 screen pre-registered (scheduled market-structure calendar), not run.
- What it showed: (1) presence misses are quiet small-edge cells (the taker's arrival is the missing trigger); (2) the side
  residual has no fill-level cross-market synchrony, so no shared hidden feed is indicated at that level (hits are the
  synchronized ones); (3) the 11-01 side drop is not the taker mix (reweighted 0.844 vs 0.675), it is inside every taker
  class at small edges; (4) the venue's taker hold is visible (L floor 187-193 ms); (5) the NYSE-open window is a scheduled
  event where the cluster buys the cheap token (an October configuration; R8c); (6) on the clean 11-01 block the
  off-posture posts coincide across the 5m and 15m windows (3.52, p 0.007), 40% after a futures move.
- Closed this iteration: E1, E2, E7, X196, X197, X205, X210 (tried); new open: E3-E6, X195 (partial), X198-X204,
  X206-X209, X211.
- Recorders: the shared recorder runs; the own recorders (examrec, dy_rtds, dz_rtdsbn, dw_clob, dv_rtds to 11-02 00:00;
  the delayed full-depth dm_* to 11-01 12:00) were not touched. The laptop clock offset (1.3 s at 09:26 UTC) still needs a
  Windows time resync by the user.

**For a successor (if the budget is extended).** (1) Run the pre-registered E3 calendar screen (B1 signing times on
BUILD, quote-unit posts live). (2) X211: the other scheduled slots with high side residuals (06:15, 22:00 CME reopen,
07:45-08:00) and whether the open-window rule survives the 11-02 DST change (14:30 UTC). (3) The mechanics panel's
walking-bid state machine (X200) and the step-hazard reference test (X201), on the full-depth 11-01 06-12 recording.
(4) X198: record the Polymarket Perps index and re-align the nowcast. (5) X207: the per-account MTM breaker as own state.

**Pre-registration T6 (written 11:09 UTC, after the BUILD look below and before any lot number): R8c15.** BUILD weekday
BTC 15m windows starting at 13:30 UTC: 232 fills in 6 windows, cheaper (nb_side `cheap_ok`) 0.974 vs 0.377 in the other
15m windows (mean price 0.26). Rule R8c15 = R8c plus the BTC 15m window that starts at the NYSE open -> the cheaper token.
Adopt only if the cheaper share in that window is >= 0.85 on STUDY and on VALIDATE (aggregate; nb_side folds) and at least
0.30 above the cheaper share of the other 15m fills of the same fold.
**T6 result (results/iter17_r8c15.json): R8c15 not adopted.** BTC 15m window starting at the NYSE open: STUDY cheaper
1.000 (8 fills, 2 windows; other 15m fills 0.344), VALIDATE (aggregate) 0.892 (111 fills, 4 windows; other 0.596):
the VALIDATE margin 0.296 misses the pre-registered 0.30 by 0.004, so R8c stays 5m-only (the 15m open window is a lead,
X212).

**Pre-registration T7 = X206 (assumptions panel P2; written 11:12 UTC, before any number): the side regime follows the
reference's recent informativeness.** Indicator H_N(t), public and causal: over the last N resolved BTC 5m windows
(end + 60 s <= t) whose Binance fair of Up at 150 s differs from the last clean Up print by >= 0.05, the share in which the
outcome went the fair's way (y = 1[F > m]); N = 36 primary (12 and 96 reported). Dependent: per 2-h block, the margin
acc(posture) - acc(cheaper) of the cluster's non-decided BTC 5m fills (|mid_up - 0.5| <= 0.4). Reading: Spearman(H_36 at the
block start, margin) >= 0.30 with p < 0.01 on BUILD 10-09..22. Only then a gated side G (non-decided fills: posture if
H_36(t) >= the BUILD median of H_36, else the cheaper token; NYSE-open window as R8c) is scored per fill on STUDY and
VALIDATE (aggregate) against R8c; adopt if VALIDATE gains >= 0.01 and STUDY does not fall by more than 0.01.
**T7 result (`code17/inform_gate.py`, results/iter17_inform_gate.json): rejected.** 6,336 BTC 5m windows (2,883
informative). Spearman(H_N at the 2-h block start, posture - cheaper margin of the cluster's non-decided fills) on BUILD
(151 blocks): N 12 -0.186 (p 0.022), **N 36 -0.130 (p 0.111)**, N 96 -0.083 (p 0.31). The pre-registered reading (>= 0.30,
p < 0.01) fails and the sign is negative: the cluster does not follow the reference more after the reference has been
informative. The gated rule was not scored on the lot (pre-registered condition). X206 closed as tried.

**Pre-registration T8 = X198 part 1 (information panel P4; written 11:15 UTC, before any number): the nowcast basis lag.**
S_L(t) = CL_i + F(t - 50 ms) - F(ts_i - L), L in {0, 0.5, 0.75} s (L = 0 is iteration 16's nowcast), safe clock, k 1.0, on
the pure non-extreme 500 posts (it14_qu_rebuilt). L chosen on 10-31 14-18; scored per hour on 11-01 07:00-09:15 (all posts
and the still posts). Reading: the chosen L beats L = 0 by >= 0.02 on 11-01 overall -> the report's value lags its stamp
and the engine's reference is aligned to it; else the stamp is the right basis. Information only (no cluster data): each
L's error in predicting the next report's change.
**T8 result (`code17/nowcast_lag.py`, results/iter17_nowcast_lag.json): no effect of the basis lag.** 10-31 14-18
calibration: L 0 0.7847, L 0.5 0.7831, L 0.75 0.7831 -> L = 0 frozen; 11-01 07:00-09:15 (1,214 posts): 0.633 / 0.634 / 0.634
(still posts 0.597 / 0.596 / 0.596). The reading fails; the report's stamp is the right basis. Information only: the
nowcast predicts the next report's value no better than the last report itself (median |error| 1.77 vs 1.69 on 10-31,
0.166 vs 0.156 on 11-01, any L): between reports the public Chainlink value is not a lagged futures price plus small noise.
X198 part 1 tried; part 2 (recording the Perps index) not started.

**Pre-registration T9 = X199 part 1 (information panel P5; written 11:17 UTC): the exam's Chainlink input.** For 12
window starts (every 10 min, 11-01 08:00-10:00) and BTC / ETH / SOL, the keyless crypto-price endpoint's openPrice
(value stamped tau) and closePrice (tau + 300) against the dy_rtds stream value with the same stamp. Reading: max |diff|
< 0.01 USD (BTC) / relative 1e-6 (ETH, SOL) on every stamp -> the fallback is exact and the exam input survives a stream
outage or the legacy-RTDS deprecation.
**T9 result (`code17/cl_parity.py`, results/iter17_cl_parity.json): exact.** 72 stamp pairs (BTC, ETH, SOL; 12 window
starts x open and close, 11-01 08:00-10:00): endpoint openPrice / closePrice minus the dy_rtds value with the same stamp
= 0.0 on every pair (no missing value on either side). The keyless endpoint reproduces the stream exactly, so
`code/cl_source.py`'s endpoint fallback keeps the exam's Chainlink input alive through a stream outage or the legacy-RTDS
deprecation (bounded by MAX_CL_REQUESTS = 3,000 requests per evaluate call; beyond that the Binance stand-in is used).
X199 part 1 tried.

**T10 (descriptive, written 11:18 UTC): what the NYSE-open fills are, from their orders (B1).** The lot's cluster fills
(typed_fills, STUDY case by case and VALIDATE aggregate) joined by salt to the decoded calldata (sign ms, limit, original
size): signing time relative to the window start and to the fill, limit price, size class, in the NYSE-open window vs
every other BTC 5m window. Question: pre-positioned resting bids hit by the opening move (signed before the window or long
before the fill, deep sizes) or a reactive decision to buy the cheap token after the move (signed seconds before the fill,
main-ladder sizes)?
**T10 result (results/iter17_open_orders.json).** B1 signing times do not exist for this cluster: its orders carry
`timestamp = 0` in 100% of the STUDY (8,475), VALIDATE (28,609), 10-31 live (2,050) and iteration-17 taker samples (known
since iteration 4: a custom signer; other makers set it in 99%). The per-wallet salt counter dates orders instead: **0% of
the NYSE-open window's filled orders have a salt below the highest salt of the same wallet's fills in the 5 minutes before
the open** (STUDY 107, VALIDATE 513), i.e. every one was created after the latest pre-open filled order; they are
main-ladder sizes (500 x 2^k: STUDY 100%, VALIDATE 92%, vs 38-41% of the fills in other windows) at mean limits 0.19 /
0.28 on the cheap token (0.99 / 0.90). So at the open the engine posts fresh main-ladder bids on the token the opening
move made cheap: a decision at the open, not stale resting bids run over. Correction to the E3 pre-registration above:
B1 signing times are infeasible for this cluster (timestamp 0); its decision series are the live-lab posts (weekday
development blocks from 11-02) and, historically, the salt order.

**Pre-registration T11 (written 11:20 UTC, before any lot number): other scheduled slots (X211).** Set S = the BUILD
weekday BTC 5m slots with miss share >= 0.69 and >= 60 decisions, excluding the 13:30 / 13:35 windows already scored:
{06:15, 22:00, 07:45, 08:00, 17:00, 16:00, 01:15, 21:45, 23:50, 14:05} UTC. Rule R8d = R8c with weekday windows starting
in S -> the cheaper token. Adopt only if in S the cheaper token is >= 0.70 and >= R8 + 0.10 on STUDY and on VALIDATE
(aggregate), and the VALIDATE per-fill accuracy rises by >= 0.003.
**T11 result (results/iter17_r8d_slots.json): R8d not adopted.** In S: STUDY cheaper 0.727 = R8 0.727 (231 fills, 15
windows), VALIDATE cheaper 0.777 vs R8 0.694 (988, 39 windows; +0.083 < 0.10); VALIDATE per fill 0.7009 -> 0.7038 (+0.0029
< 0.003). The NYSE open is the one scheduled slot with a decisive side; the other high-residual slots are not. X211 tried.
**R8c replication on VALIDATE (aggregate; results/iter17_r8c_replication.json).** Halves 10-27/28 0.6797 -> 0.6876, 10-29/30
0.7014 -> 0.7100 (cheaper 0.629 / 0.713: in the second half the rule is 0.003 under the cheaper token); per wallet
mo-money 0.692 -> 0.698, almach 0.702 -> 0.710, bosona 0.684 -> 0.695. The gain is in every half and wallet (+0.007 to
+0.011). C7 / mechanics P5 part 2: in the cached 10-31 all-match calldata, 253 transactions hold a cluster taker order and
1,739 a cluster maker order, and none holds both: no cross-account matching.

**Pre-registration T12 = X195 natural experiment (written 11:22 UTC, before any number): the taker hold as part of the
edge.** The crypto taker hold went 250 -> 50 ms on 08-17 11:00 UTC and 50 -> 150 ms on 09-04 14:00 UTC (changelog, read
by the information panel). Unit: the cluster's BTC 5m BUY fills (whole-history activity, all three accounts), return per $
= (payout - cost) / cost with the Gamma resolution (post-hoc fields used for settlement only, development units). Seven
days before vs seven days after each change. K8 (speed-bump liquidity provider) predicts a lower return after 08-17 and a
higher one after 09-04; reading: both differences have the predicted sign and |difference| >= 2 points per $, with a
day-block bootstrap 90% interval excluding 0 for the 09-04 change (the 08-17 change overlaps the settlement switches
07-31..08-20 and is reported only).
**T12 result (`code17/hold_natexp.py`, results/iter17_hold_natexp.json): the hold length does not show in the cluster's
returns.** 230,691 BTC 5m BUY fills in 8,090 resolved windows. 08-17 (250 -> 50 ms): 5.03% -> 4.62% per $ (difference
-0.41 points, day-bootstrap 90% [-3.7, +2.8]; cheap share 0.63 -> 0.47). 09-04 (50 -> 150 ms): 2.82% -> 1.82% (-1.00,
[-3.3, +1.0]; cheap share 0.59 -> 0.66): the sign is the opposite of the K8 prediction. Reading not met: the cluster earned
+2-5% per $ under 50-, 150- and 250-ms holds alike, so the hold's length is not a visible part of the edge at the
resolution of a week (an effect under ~3 points per $ cannot be excluded). X195: the floor and the natural experiments
are done; the hold-aware strict replay is split off as X213.

**Pre-registration T13 = E3 screen, reference-feed family (written 11:26 UTC, before any number).** Live-only dimensions,
so the brief's live split applies: development blocks of days 0-1 after T0 are BUILD (10-31 12-18, 11-01 06-12), days 2-3
VALIDATE (confirmation pending). Decisions: the cluster's at-touch 500/1000 posts of BTC 5m + 15m windows
(it14_qu_rebuilt: 10-31 14:00-18:00, 11-01 07:00-09:15; exact server ms), decision sign +1 for an Up post. Units:
consecutive 300-s clock slots. Indicators (event sign in Up terms): (1-3) Binance USD-M futures mid jumps on a 100-ms grid,
k = 3 sigma over h = 0.5 s, 2 s and 10 s (refractory 0.5 s); (4) Chainlink BTC report changes on the exact publish clock
(dy_rtds P; sign of the change). Lag ranges: +-2 s (bin 0.1 s, max_lag_s 4) and +-60 s (bin 1 s, max_lag_s 120). Swap
null, 300 draws, hour-of-day strata. BH over the joint family (8 unsigned + 8 signed p_link), survivors at q <= 0.10.

**Pre-registration T14 = E5 information dimensions against selection (written 11:29 UTC, before any number).** Daily
series over the development days 2026-08-01..10-22: the cluster's module-on share (share of BTC 5m windows with >= 1
cluster BUY fill, whole-history activity) and its BTC 5m BUY fill count. Indicators: GDELT DOC 2.0 `timelinevol` for
"bitcoin" (daily mean), the alternative.me Fear & Greed index and its absolute daily change. Point in time: the previous
day's value (known at the day's start); same-day values reported as co-movement only. Reading: Spearman |rho| >= 0.30 with
p < 0.01 for a previous-day indicator -> the news / sentiment dimension relates to selection; else no association at the
daily scale (the power of a daily test over ~80 days is low: |rho| < ~0.29 is undetectable at p 0.01).
**T13 result (`code17/e3_feeds.py`, results/iter17_e3_feeds.json): the futures dimension links, the Chainlink publish
changes do not in this form.** 7,433 posts, 75 five-minute units, swap null (61-70 units in the null), hour strata, joint
BH over 16 p-values:

| indicator (events) | +-2 s: p_link (q) / shape peak lag, lift | +-2 s signed: p (q) / peak lag, z | +-60 s: p_link (q) | +-60 s signed: p (q) |
| --- | --- | --- | --- | --- |
| futures jump k3 / 0.5 s (603) | 0.013 (0.043) / +0.05 s, 3.25 | **6.6e-5 (0.001)** / +0.15 s, 5.9 | **0.008 (0.031)** | 0.005 (0.025) |
| futures jump k3 / 2 s (296) | 0.056 (0.113) / +0.15 s, 3.64 | **6.2e-4 (0.005)** / +0.10 s, 4.8 | 0.143 (0.19) | 0.12 (0.19) |
| futures jump k3 / 10 s (112) | 0.349 (0.37) | 0.020 (0.053) / +0.05 s, 3.5 | 0.053 (0.113) | 0.186 (0.23) |
| Chainlink report change (9,917) | 0.269 (0.31) | 0.076 (0.14) | 0.143 (0.19) | 0.495 (0.50) |

BUILD survivors (q <= 0.10): the 0.5-s futures jump (unsigned at both lag ranges, signed at both), the 2-s jump (signed,
+-2 s) and the 10-s jump (signed, +-2 s, q 0.053). The cluster's posts follow sharp futures moves within 50-150 ms, on the
side the move favours: the futures feed is a timing and side input of the quote (as the re-peg reading of iteration 16
said, now in the brief's screen). The Chainlink report changes, near-continuous on the publish clock (9,917 events in
6.25 h), show no localized link in this form (the publish-anchored test of X163 used a different unit). Confirmation on
the live VALIDATE blocks (days 2-3 after T0) is pending: the survivors are BUILD-only.

**T14 result (`code17/e5_daily.py`, results/iter17_e5_daily.json): no daily association.** 83 development days
(08-01..10-22), module-on share mean 0.84. Spearman with the previous day's value: GDELT "bitcoin" volume vs on-share 0.181
(p 0.146), vs fills 0.143 (p 0.25); Fear & Greed vs on-share 0.210 (p 0.059), vs fills 0.080; |change in F&G| -0.162 (p
0.15). Reading not met. The power is low (|rho| < ~0.29 undetectable at p 0.01 over ~80 days), so the news and sentiment
dimensions stay `untested` at finer scales (E5 open: intraday GDELT 15-min and the RSS feeds, recorded live).

**New recorder (X214, information panel I16-4 step 2).** `code17/perpsrec.py`, feed `dp_perps` through tools/live.py's
Writer: the Polymarket Perps index, mark and last price of BTC / ETH / SOL (instruments 6 / 7 / 8) from the keyless REST
`api.perpetuals.polymarket.com/v1/info/tickers` (verified HTTP 200, JSON with index_price, mark_price, server timestamp
ms), polled about once a second (the index is published every 200 ms, so this is a 1-s sample). Started 11:28:40 UTC 11-01
(pid 33364, Start-Process, hidden), hard stop 2026-11-03 00:00 UTC, disk cap 60 MB, status
`.cache/re/directional-maker/perpsrec_status.json`. Development blocks it will cover: 11-01 18-24, 11-02 00-06 and 12-18
(the others are filed as sealed by the Writer). For the successor: race the index against dy_rtds publishes and the
futures (I16-4 step 3) on those blocks.

## Iteration-17 checkpoint, addendum (11:30 UTC)
- After the first checkpoint above, eight more pre-registered tests: T7 (reference informativeness gate, X206) rejected;
  T8 (nowcast basis lag, X198) no effect; T9 (Chainlink endpoint parity, X199) exact; T10 (salt-order dating) the
  NYSE-open orders are fresh main-ladder bids posted at the open; T11 (other scheduled slots, X211) not adopted; T12
  (taker-hold natural experiments, X195) no visible effect; T13 (E3 screen, reference-feed family, live BUILD) the
  0.5-s futures jumps link (signed q 0.001, peak +0.15 s), Chainlink report changes do not in this form; T14 (E5 daily
  news / sentiment vs selection) no association (low power). R8c replicates in both VALIDATE halves and in each wallet.
- Frozen rule: R8c (unchanged since the first checkpoint). target_metrics: only side_accuracy changed (0.7009).
- Open catalog: 52 items (E3-E6, the older X items, X200-X204, X207-X209, X213, X214).
- Iteration 17 used about 48 wall-clock minutes (10:46-11:34 UTC); recorders: the shared recorder and the own recorders
  untouched; the new dp_perps recorder runs to 11-03 00:00 UTC.

**Pre-registration T15 = X208 light (assumptions panel P4; written 11:31 UTC, before any number): side configuration
as discrete operator pushes.** Series: per 2-h block of BUILD 10-09..22, the margin acc(posture) - acc(cheaper) of the
cluster's non-decided BTC 5m fills (>= 30 fills per block). Change points: optimal partition with an l2 cost and a BIC
penalty (2 sigma^2 log n, sigma from the block-to-block differences). Operator events: the weekly Monday 01:00 UTC restart
(10-12, 10-19; the weekly capital sweep). Statistic: the number of change points within +-4 h of an event; null: the
event times shifted circularly by whole days (1-13), keeping the weekday structure out. Reading: the observed count is
at or above the null's 95th percentile and at least one change point falls within +-4 h of each Monday restart -> the
configuration steps are operator pushes at the weekly restart; else not shown.
**T15 result (`code17/cfg_steps.py`, results/iter17_cfg_steps.json): not shown.** 152 BUILD 2-h blocks; two change
points, 10-15 00:00 and 10-15 10:00 UTC: a 10-hour episode with margin -0.437 (fills on the cheap token 0.72-0.91, the
posture 0.25-0.51, won 0.32-0.65) between +0.11 (10-09..14) and +0.17 (10-15..22). None within +-4 h of the Monday 01:00
restarts (null 95th percentile 0.75): the side configuration's steps are not the weekly restart. Descriptive, post hoc
(results/iter17_margin_vol.json): the per-block margin falls with the block's BTC realised vol (same block rho -0.333,
p < 0.001; previous block -0.243, p 0.0025) and the cheap share rises with it (0.26 / 0.23).

**Pre-registration T16 (written 11:33 UTC, after the descriptive look above and before any lot number): a volatility
gate for the side (G3).** G3 = R8c, except that a non-decided BTC 5m fill outside the NYSE-open window goes to the cheaper
token when the trailing 2-h realised vol of BTC (Binance 1-s log returns over [ts - 7,202, ts - 2]) exceeds the 75th
percentile of that statistic over the BUILD fills; else the posture. Scored per fill on STUDY and VALIDATE (aggregate)
against R8c. Adopt only if VALIDATE gains >= 0.01 and STUDY does not fall by more than 0.01.
**T16 result (`code17/vol_gate.py`, results/iter17_vol_gate.json): G3 rejected.** Threshold (BUILD fills' 75th
percentile of the trailing 2-h RV) 0.00346; per fill STUDY 0.5769 -> 0.5460, VALIDATE 0.7009 -> 0.6961. In the high-vol
non-decided fills the posture still beats the cheaper token (STUDY 0.568 vs 0.482, n 2,951; VALIDATE 0.653 vs 0.640, n
10,024): the BUILD block-level association with vol does not become a fill-level side rule. R8c stays.

Final state of iteration 17 (11:33 UTC): frozen rule R8c; target_metrics side 0.7009, all others unchanged; primary metric
0.716. X208 tried (light form: change points vs the Monday restart, not shown). Exam readiness: evaluate() ran end to end
with R8c on a VALIDATE slice (10-27 13:25-13:45); the full 11-01 06-12 block run was not done (it needs ~25 minutes after
12:00 UTC, beyond the budget). Recorders: shared recorder and own recorders untouched; dp_perps running (to 11-03 00:00).
The user should resync the Windows clock (offset 1.3 s at 09:26 UTC; agents may not change system settings).

## Iteration 18 (started 2026-11-01 12:29:33 UTC; 1,161 of 1,200 minutes used)

Situation: the current block 11-01 12-18 UTC is sealed (sealed.py), so no live data is read this iteration; the
development live blocks are 10-31 00-06, 10-31 12-18 and 11-01 06-12 (next: 11-01 18-24, 11-02 00-06, 11-02 12-18).
Three panels after iteration 17 (panels/iter17_*.md). Two of them (mechanics P1, assumptions P1) independently name one
mechanism: the fair's sigma is a scheduled, forward-looking time-of-day volatility profile from about 10-01, and R8c (the
NYSE-open window) is its symptom. The assumptions panel's history check: the window-level slope of the cluster's
mid-band cheap share on log(profile) is negative in June-August, ~0 in September and +0.157 (s.e. 0.021) in October, flips
on 10-01/10-02 and holds outside 13:00-15:55 UTC. The information panel's P1: the clean-regime post side also reacts to
the report-specific Chainlink innovation u_i within (0, 150] ms of the public publish (0.71, n 65), never before it.
Catalog: the 13 proposals are entered as X215-X227 (state.json).

Competing explanations of the money this iteration (dimensions in `dimensions`; what tells them apart):
- K1 scheduled-vol fair (dimension `scheduled_vol_profile`, have: Binance 1-s archives; X215): from 10-01 the engine's
  sigma is k x a time-of-day profile (or max(v300, profile)), so at slots whose coming vol exceeds the trailing vol it
  leans to the cheap token; the money is the market's trailing-vol mispricing of favourites at those moments. Tell: a
  profile posture without any calendar branch reproduces the open window AND raises the small-edge side elsewhere; the
  October slope sign flip is the cluster's, not the market's.
- K2 configured calendar override (dimension `us_equity_market_open`, have): R8c is a hand-set rule at 09:30 New York;
  the rest of the side is the trailing posture. Tell: the profile helps only at 13:30 UTC; on 11-02 the behaviour moves
  to 14:30 UTC at once (exchange clock) or stays at 13:30 (UTC-keyed config).
- K3 two-input event re-pricer (dimensions `binance_usdm_futures`, `pm_legacy_rtds` innovation, have; X220): the quote is
  re-sided by futures jumps (50-150 ms) and the report innovation at public-relay timing; between events it is
  replenishment; the side residual at small edges is k (unidentified in level postures). Tell: event law E beats the
  posture at |F - mid| < 0.05 on blocks it was not frozen on.
- K4 taker-chosen pairs (dimensions: taker commit times, have; the display the takers see, `pm_display_state`, proxy;
  X221): the engine quotes both outcomes near the mid at small edges; which leg fills is the crowd's choice driven by the
  page display (strike crossings, results strip). Tell: the crowd's buy side follows display events; the cluster's filled
  side is its complement.
- K5 own-state order types (dimension `own_inventory`, have; X226): the presence and side residuals are mostly pairing,
  remainder and deep orders that no public feature can announce. Tell: >= 50% of the out-of-fold FN cells hold only
  those types.
- K6 (unlikely) hidden faster settlement feed (dimension `chainlink_data_streams_low_latency`, blocked): the engine sees
  the report before the public publish. Tell: post-side agreement with u_i rises before P_i (information panel C2: 0.505
  before, n 537: not supported; recorded as the trace test).
- K7 (unlikely) information-shock operator (dimensions `news_wires`, `gdelt`, missing at 15-min resolution; X222): module
  switches follow intraday news or vol shocks. Tell: off-run starts are preceded by GDELT bursts above placebo.

This iteration discriminates K1 vs K2 (T1, T2), records the K2 clock test for 11-02 (T5), and tests K5 (T4) and K3 (T3)
as far as time allows.

**Pre-registration T1 = X215 (written 12:37 UTC 11-01, before any number below was computed): the profile posture.**
- Profile P_d(s): UTC day d, 5-min UTC slot s; rv_d'(s) = sqrt(mean squared 1-s log return of Binance BTCUSDT spot
  inside the slot) (the per-second scale of v300); P_d(s) = median of rv_d'(s) over the previous N days d' in [d - N,
  d - 1] of the same day type. Variants (8): N in {28, 56}; day type pooled or split (NYSE trading day vs weekend /
  NYSE holiday, 09-07 the only holiday in range); day-type date by the UTC date or by the New York date of the slot
  (under DST the 00:00-04:00 UTC slots belong to the previous New York date). Source code18/slot_rv.py (archives 08-14..
  10-07, checksum-verified; cached 1-s 10-08..10-30).
- Fill slot = the window's start slot. Forms: F_max sigma = k x max(v300, P); F_geo(a) sigma = k x P^a x v300^(1 - a),
  a in {0.25, 0.5, 0.75, 1}; k in {0.8, 1.0, 1.2, 1.4, 1.7, 2.0, 2.5, 3.0}. The decided branch (|Up mid - 0.5| > 0.4 ->
  the cheaper token) is kept; the R8c calendar branch is removed (S1) or kept (S2).
- Fit on BUILD 10-09..22 only: every BTC 5m cluster maker BUY fill (code17/inform_gate.build_fills: mid and side), the
  Binance stand-in posture rebuilt from spot (S at b - 2, K = Binance mean of [st - 60, st), v300 at b - 2 over 300 s,
  tau = en - (b - 2)); the chosen (variant, form, a, k) maximises the per-fill accuracy of S1 over all BUILD fills.
- Score once on the lot (it12/typed_fills: R8's Chainlink posture where cl exists, else Binance; the same sigma
  substitution in both): STUDY 10-23..26 case by case and VALIDATE 10-27..30 aggregate, per fill, against R8c and R8;
  reported overall, in the open window, by |edge| band (|f_R8 - mid| < 0.05 / 0.05-0.1 / >= 0.1), by P / v300 band, per
  wallet and per VALIDATE half.
- Adoption: the better of S1 / S2 on VALIDATE replaces R8c iff VALIDATE per fill >= R8c + 0.005 and STUDY >= R8c - 0.01.
  Mechanism signature (reported, not an adoption condition): S1 reaches >= 0.85 in the open window on STUDY and VALIDATE
  with no calendar term, and its gain outside the open window is concentrated at |edge| < 0.05.

**Pre-registration T2 = X215 identification with a market control (assumptions P1 step 2; written 12:37 UTC).** For
BUILD 10-09..22 (the October fold with maker-row tapes on disk): per weekday BTC 5m window (>= 5 mid-band 0.15-0.85
fills), the cheap share of (a) the cluster's maker BUY fills and (b) the other makers' maker-side fills in the same
windows; OLS of the window cheap share on log P (N 28, pooled), with the window's realised |log return| and the trailing
1-h mean |5-min return| as controls; the 13:30 / 13:35 windows excluded. Reading: the cluster's slope > 0 with p < 0.01
and the market's slope at least 0.10 lower -> the October slope is the cluster's estimator, not a market effect.

**Pre-registration T5 = X218 (mechanics P4 / information I17-4 live; written 12:37 UTC, before 11-02 13:20 UTC).** A
full-depth recorder (code18/open_rec.py, pid 10460, Start-Process hidden; dm_* feeds through tools/live.py's Writer;
11-02 13:15-13:50 and 14:15-14:50 UTC; 11-02 12-18 is a development block; own disk <= 60 MB) records the first post-DST
NYSE open. Predictions, written now:
- (a) K1 with a New York-keyed profile: at 14:30:00 UTC the cluster's fresh 500 rungs go to the token the opening move
  makes cheap, and the ladder centre moves toward 0.5 within +-2 s of 14:30:00, before the first 3-sigma futures jump;
  nothing special at 13:30 UTC.
- (b) K1 with a UTC-keyed trailing-weeks profile: the lean stays at 13:30 UTC (an ordinary window after DST) for weeks.
- (c) K2 calendar override on the exchange clock: fresh bids only on the cheap token at 14:30, the favourite's rungs
  pulled, at 14:30 and not at 13:30.
- (d) K2 UTC-keyed: the behaviour appears at 13:30 UTC.
- Reading on 11-02: cheap share of the cluster's 14:30 window fills (shared recorder trades) >= 0.85 and the 13:30 window
  at its ordinary level -> exchange clock (a or c; a vs c by the favourite rungs and the centre move); the reverse -> UTC
  clock (b or d).

**Pre-registration T6 = X215 step 4 (mechanics P1; written 12:42 UTC, before any number): is the k-cycle the profile?**
Per day of BUILD 10-09..22 (best k from results/iter11_k_by_day_binance.json) and STUDY 10-23..26 (results/iter11_k_by_day.json;
VALIDATE days not used case by case): the median of P / v300 (P = utc_N28 profile of the window's slot) over the cluster's
non-decided BTC 5m fills of that day. Reading: Spearman(best k, median P / v300) >= 0.4 with p < 0.05 over the 18 days ->
the drifting multiplier is the profile's excess over the trailing vol; else the k-cycle is not the profile.

**Pre-registration T3b (written 12:46 UTC, after the freeze block and the 10-31 17:29-18:00 block were scored, BEFORE the
11-01 09:15-12:00 posts exist): law E2 = (1) a publish in (t - 150, t] with |u| >= $1 -> sign(u); else (2) the futures
mid moved >= $2 over [t - 500, t - 50] ms -> the direction of the move (the W500 'rose' rule of iteration 14); else (3)
the posture.** Reason: on the freeze block the W500 'rose else posture' rule (0.719) beat law E (0.665), its jump
detector covering 13% of posts against W500's wider move set. Scored once on 11-01 09:15-12:00 beside law E and the
baselines, with the same readings as E (signature: (0, 150] agreement >= 0.65 and (-300, 0] <= 0.55 at n >= 40; the law
beats the posture by >= 0.05 at |F - mid| < 0.05 and does not lose at >= 0.1).

### Iteration 18 results (12:38-12:48 UTC 11-01)

**Data added.** (1) `it18/slot_rv.parquet`: per-day x 5-min UTC slot 1-s realised vol of Binance BTCUSDT spot for 78 days
(08-14..10-30; 55 daily 1s-kline archives from data.binance.vision, SHA-256 checked against `.CHECKSUM`, reduced at once,
zips never written to disk; 10-08..10-30 from the cached 1-s files). (2) `it18/yahoo_1m*.parquet`: 1-minute bars of IBIT,
QQQ, SPY, COIN, MSTR for 10-02 13:30 .. 10-30 UTC (Yahoo chart API, keyless; the 10-01 chunk returned HTTP 422 because
1-minute history is kept for ~30 days; 10-02 was fetched at 12:40 UTC 11-01, minutes before it aged out). (3) The 11-01
09:15-12:00 quote-unit posts rebuilt from the full-depth `dm_clob_raw` (code14/qu_oos.py; 2,412 at-touch schedule adds;
`it14_qu_rebuilt_1793524500_1793534400.parquet`); never scored before this iteration. (4) Recorder X218 (code18/open_rec.py)
armed for 11-02 13:15-13:50 and 14:15-14:50 UTC (sleeps until then).

**T1 = X215 result (`code18/sched_vol.py`, results/iter18_sched_vol.json): the profile posture is NOT adopted.** BUILD
(49,569 fills): R8 (1.4 x v300) 0.5961, R8c 0.6049, best trailing k (1.0) 0.6136; best profile rule over 6 variants x 2
forms x 8 k x 4 a: utc_N28 (weekday/weekend profile over the previous 28 days, UTC date), sigma = 1.0 x max(v300, P):
**0.6276** (BUILD open window 0.669 vs R8 0.386, cheaper 0.984). Lot, per fill:

| fold | R8 | R8c | S1 (profile, no calendar) | S2 (profile + R8c branch) | cheaper | open window: R8c / S1 |
| --- | --- | --- | --- | --- | --- | --- |
| STUDY 10-23..26 (8,256) | 0.5693 | 0.5769 | 0.6142 | 0.6254 | 0.484 | 0.991 / **0.131** |
| VALIDATE 10-27..30 (27,988, aggregate) | 0.6925 | **0.7009** | 0.6863 | 0.6906 | 0.6785 | 0.899 / 0.667 |
| VALIDATE halves (S2) | | 0.6876 / 0.7101 | | 0.7286 / 0.6644 | | |

Adoption fails (VALIDATE S2 -0.010 vs the +0.005 bar); the mechanism signature fails (S1 does not reproduce the open
window: 0.13 STUDY, 0.67 VALIDATE). Decomposition (post hoc, descriptive; `code18/sched_vol_decomp.py`,
results/iter18_sched_vol_decomp.json): S1's STUDY gain is the k change (trailing k 1.0 alone 0.6107 vs S1 0.6142), its
VALIDATE loss too (trailing k 1.0 0.6344); at a fixed k the profile adds +0.052 (k 1.0) / +0.016 (k 1.4: 0.7081) on
VALIDATE and +0.004 / -0.020 on STUDY. In the open window the posture picks the cheap token in 100% (STUDY) / 98.9%
(VALIDATE) of fills only with 2 x max(v300, P): at the fill seconds P / v300 is just 1.33 / 1.64 (v300 at b - 2 already
holds the opening seconds), so a profile at k 1.0 cannot pull the fair far enough.

**T2 = X215 identification (`code18/ident_slope.py`, results/iter18_ident_slope.json): the slope is the cluster's, not the
market's (reading met).** BUILD weekday windows of the maker-row tapes (13:30 / 13:35 excluded), mid-band 0.15-0.85:
cluster cheap-share slope on log P **+0.229 (s.e. 0.080, one-sided p 0.002; 194 windows)**; the other makers in the same
194 windows **-0.013 (s.e. 0.007)** by exposure token, -0.017 by BUY rows (over all 480 windows -0.012 / -0.014). The
time-of-day gradient of the cheap share belongs to the cluster's own decision (or its quote's geometry), not to the
market's flow or its makers.

**T6 = X215 step 4 (`code18/k_vs_profile.py`, results/iter18_k_vs_profile.json): the k-cycle is not the profile.** 18 days
(BUILD + STUDY): Spearman(best k of iteration 11, median P / v300 at the non-decided fills) = 0.161 (p 0.52). Reading not
met.

Reading of T1/T2/T6: the profile matters for the cluster (T2: a cluster-only gradient over the day), but not as the
posture's sigma in these forms; the weekly k drift dominates every level posture, and the open window needs a fair
pulled about twice as far toward 0.5 as max(v300, P) gives. K1 is supported as a gradient, not as a decoded rule; K2 (a
configured open-window override) stays the frozen form (R8c), and the 11-02 recording (T5) decides its clock.

**T3 = X220 result (`code18/event_law.py`, results/iter18_event_law.json): the report innovation and the futures move are
two event inputs of the post side; confirmed out of sample.** Innovation model frozen on 11-01 07:00-08:00 (futures-only,
4 increments; 3,473 publishes; beta 0.031 / 0.236 / 0.524 / 0.385 on the increments ending stamp + 300, -200, -700,
-1,200 ms). Posts = at-touch 500/1000 schedule adds, 0.10-0.90:

| block | posts | law E | law E2 (T3b) | posture | cheaper | W500 rose else posture | E at \|F-mid\| < 0.05 vs posture | E at >= 0.1 vs posture | (0,150] agree (n, p) | (-300,0] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| freeze 11-01 07:00-09:15 (panel's look) | 1,018 | 0.665 | 0.721 | 0.590 | 0.618 | 0.719 | 0.622 vs 0.521 | 0.700 vs 0.647 | 0.729 (59, 3e-4) | 0.427 |
| **11-01 09:15-12:00 (untouched)** | 1,108 | **0.608** | **0.642** | 0.520 | 0.525 | 0.631 | **0.555 vs 0.467** | 0.685 vs 0.610 | **0.800 (45, 3e-5)** | 0.531 |
| **10-31 17:29-18:00 (noise regime)** | 418 | **0.792** | **0.804** | 0.713 | 0.306 | 0.751 | **0.674 vs 0.556** | 0.933 vs 0.942 | **0.856 (132, 9e-18)** | 0.400 |

Swap null (u moved to the publish 1-3 before / after) on the (0, 150] agreement: 0.33-0.71 (clean) and 0.14-0.58 (noise).
By source on 09:15-12:00: publish-u posts (4%) 0.80 vs posture 0.47; futures-jump posts (12%) 0.90 vs 0.29; the other 84%
fall to the posture (0.556). The pre-registered signature holds on both confirmation blocks ((0, 150] >= 0.65 at n >= 40,
(-300, 0] <= 0.55; law beats the posture by >= 0.05 at small edges); "not worse at >= 0.1" holds on the clean block and
misses by 0.008 (one post of 120) on the noise block. E2 (pre-registered T3b before the 09:15-12:00 posts existed) is the
better form on both confirmation blocks (+0.122 / +0.091 over the posture). No pre-publish reaction (K6 not supported,
third block). Side residual still open: 84% of clean-block posts follow no event (posture 0.556; 'opposite of the last-hit
token' 0.594, a flow-following lean). This is a live (match-clock) quote component; the historical VALIDATE per-fill side
cannot use it (no ms reference there), so target_metrics do not move.

**Pre-registration T4 = X226 (assumptions P4; written 12:50 UTC, before any number): the presence label by order type.**
VALIDATE 10-27..30 aggregate: frozen R3 BTC 5m presence scores per (window, side, 10-s bin) (code8/union_val.fam_panel);
filled cells typed by their fills' orders from the lot calldata (it12/typed_fills): pairing (original size within 2% of
the wallet's imbalance, on the under-held outcome), deep (limit <= 0.10), remainder (a later fill of an order already
filled in an earlier block second), main (a fresh schedule-size order), other. Cell classes: has_main_fresh (any main
fill), own_state_only (only pairing / deep / remainder fills), other_mix. FN = filled cells below the 85th percentile of
all cells' rule scores (E2's definition). Signature (panel): own_state_only cells hold >= 50% of FN cells and the
main-ladder FN share is <= 0.35. Otherwise the taker-arrival account stands, now measured per class.

**T4 = X226 result (`code18/fn_by_type.py`, results/iter18_fn_by_type.json): the taker-arrival account stands; own-state
order types hold a third of the misses.** VALIDATE (aggregate): 69,120 BTC 5m cells, 6,735 filled; fills by class: main
(fresh schedule-size orders) 49.7%, deep 18.7%, pairing 17.8%, remainder 13.3%, other 0.6%. FN share (below the 85th
percentile of the R3 rule score) 0.664 overall (activity 0.704). Cells with a fresh main-ladder fill (4,600): FN 0.635;
cells with only pairing / deep / remainder fills (2,100): FN 0.733 and **34.4% of all FN cells**; per class held: deep
0.750, pairing 0.649, remainder 0.621. Signature not met (own-state-only share 0.34 < 0.50; main FN 0.635 > 0.35). So
two-thirds of the misses are fresh main-ladder cells that the public score ranks low: the quiet-cell trigger (a taker's
arrival) remains the main unexplained part of presence, measured now on the main ladder alone.

**Pre-registration T7 = X223 (information I17-4, historical part; written 12:51 UTC, before any number): the equity open
as an information input.** Weekday BTC 5m windows starting at 13:30 UTC (the NYSE open under DST), 10-02..10-26 case by
case (VALIDATE 10-27..30 pooled only): the cluster's BUY trades (activity; cheap = price < 0.5), BTC's first-minute move
(13:30:00 -> 13:31:00, Binance 1-m kline), the equity first-minute return (SPY + QQQ, open -> close of the 13:30 bar).
agree = same sign. Reading (panel): the window cheap share differs by >= 0.3 between agreeing and diverging windows with
Mann-Whitney p < 0.05 -> the module reads the equity open; else a calendar fade (R8c stays as frozen). Also reported:
Spearman of the cheap share with |BTC move| and with |equity move|.

**T7 = X223 result (`code18/equity_open.py`, results/iter18_equity_open.json): the open-window lean does not read the
equity open (reading not met).** 17 development + STUDY open windows (10-02..10-26): the cluster's cheap share is 0.92-1.00
in every one of them; windows where the SPY + QQQ first-minute return agrees with BTC's first-minute move 0.983 (9) vs
diverging 0.988 (8), Mann-Whitney p 0.36; fills 73.6 vs 56.4 per window; Spearman with |BTC move| -0.005, with |equity
move| 0.30 (p 0.25). VALIDATE pooled 0.954 (4 windows). The module buys the token below 0.5 at the open whatever the
equities or BTC do, even with no BTC move (10-06: 0.0 bp, 69 fills, cheap 1.00): a fixed calendar fade, i.e. a fair held
at about 0.5 in that window (T1: the posture reproduces it only with >= 2 x max(v300, P)). R8c stays as frozen; its clock
(UTC vs New York) is the 11-02 test (T5).

**E2 in the exam path.** `code14/qu_dx.py` (evaluate()'s `quote_unit_side`) now also reports `law_E2` (frozen constants
from T3: innovation beta, |u| >= $1 within 150 ms, futures move >= $2 over [t - 500, t - 50] ms, else the posture) on the
exam recorder's dx_clob posts. Smoke test 11-01 09:15-10:15 (development): 364 non-extreme posts, E2 0.684 vs posture 0.536
(small edge 0.741 vs 0.577). Reported, not counted (a live-only input; dx_bnf / dy_rtds stop on 11-03 00:00).

**Pre-registration T8 = X225 (assumptions P2; written 12:56 UTC, before any number): the money by forward / trailing
volatility ratio.** Units: the cluster's BTC 5m BUY trades (activity, three accounts), windows 06-12..10-22 case by case,
the lot 10-23..30 pooled. R = utc_N28 profile of the window's slot / realised 1-s vol of the 300 s before the start.
Outcome: Binance proxy (sign of the window's close-to-close move), checked against Gamma on BUILD. Return per $ by month x
R quintile (within month) x cheap / favourite; day-block bootstrap for October. Signature (panel): October cheap fills in
the top R quintile earn >= 5 points per $ more than in the bottom quintile; June-August favourite fills in the top
quintile lose; most of the September -> October change is in the top two quintiles.

**T8 = X225 result (`code18/pnl_by_ratio.py`, results/iter18_pnl_by_ratio.json): the money is NOT where scheduled and
trailing vol disagree (signature fails, opposite sign).** Outcomes are exact: the cluster's own REDEEM rows (usdcSize /
size = 1 for the winner, 0 for the loser) for 33,463 windows (agreement with the Gamma resolution 100% on 4,387 overlapping
windows; the Binance close-to-close proxy agreed only 82.6% and was dropped), Gamma for 65 more, 318 windows without an
outcome dropped; settlement only. Cluster BTC 5m BUY trades, return per $ by month: June 2.35%, July 3.85%, August 4.09%,
September 2.93%, October 1-22 1.17%, lot 10-23..30 (pooled) 3.75%. By R quintile (R = profile / trailing 300-s vol at the
window start, within month), October: q0 +2.6%, q1 +1.7%, q2 +1.6%, q3 +3.8%, **q4 -2.5%** (cheap share 0.65; its cheap fills
-4.1%); cheap fills top - bottom quintile **-5.4 points** (day-bootstrap 90% [-20.1, +7.2]); lot pooled q4 -3.2% vs +4.4% to
+5.6% in q0-q3. June-August favourite fills in q4: -1.1%, -0.2%, +3.6% (no consistent loss). September -> October change
by quintile: +0.7, -0.5, -4.4, +0.1, -3.5 points. Reading: the October cheap lean at high forward / trailing ratios (T2's
cluster-only gradient) is a cost, not the alpha; the profit sits in the ordinary-ratio windows. K1's economic form
("the market misprices favourites at scheduled-vol moments and the cluster collects it") is rejected.

**Pre-registration T9 = X222 (information I17-3, event version at hourly resolution; written 13:02 UTC, before any number).**
GDELT DOC 2.0 returns hourly counts for 7-day ranges (checked 13:00 UTC: `date_resolution: hour`; 15-minute bins need
ranges under ~3 days), so the test is hourly. Development 08-02..10-22. BTC 5m module on = >= 1 cluster BUY trade in the
window; off-run = >= 12 consecutive off windows after >= 3 on windows. In the hour before each off-run start: a GDELT burst
('bitcoin'; '(crypto OR fed OR cpi)') = the last complete hour's article count >= the 95th percentile of the previous 168
hours; a vol jump = the max Binance slot rv of the 12 slots before >= the 95th percentile of the previous 7 days. Placebo:
20 starts per off-run at the same hour-of-week in other weeks with the module on before. Reading: burst share >= 0.5 and
>= 3 x placebo with binomial p < 0.01 -> a shock trigger of the switch-offs; else not shown (power stated).

**Pre-registration T10 = X227 (assumptions P3, steps 1 and 3 of its test; written 13:03 UTC, before any number): the 11-01
centre with the scheduled fair.** Centre units of iteration 16 (`it16_center_units_*`: 10-31 17:29-18:00, 11-01
07:00-09:15). F_sched = Phi(Phi^-1(F1_rep) x s0 / max(s0, P x v)), where F1_rep is iteration 16's report fair at k 1.0 x
futures sigma300 (s0, $ per root second, rebuilt from dm_bnf), v the report, P the utc_N28 profile (per-second log vol) of
the unit's 5-min UTC slot (weekend profile for both blocks). Fit c - mid = const + w (F - mid) + g (0.5 - mid) per block
with F1 and with F_sched (window-clustered s.e.), and w per 15-min bin on 11-01. Reading (panel): with F_sched |g| <= 0.03
on both blocks, |w(10-31) - w(11-01)| <= 0.05 and the sd of the 15-min w on 11-01 at most half of F1's -> the 11-01 regime
is the scheduled-vol excess; else the 11-01 change stays a configuration step.

**T10 = X227 result (`code18/center_sched.py`, results/iter18_center_sched.json): the 11-01 centre is not the scheduled-vol
excess (reading not met).** Centre units: 10-31 17:29-18:00 (437; the weekend profile binds in 54%, median profile / s0
1.37) and 11-01 07:00-09:15 (1,138; binds in 35%, median 1.00: on the Sunday block realised futures vol was at the weekend
profile, not below it). c - mid = const + w (F - mid) + g (0.5 - mid): with F1 w 0.294 / 0.061, g -0.018 / +0.091; with
F_sched w 0.380 / 0.100, g -0.067 / +0.077 (s.e. 0.006 / 0.016); 15-min w sd on 11-01 0.148 (F1) -> 0.204 (F_sched). The
cheapness term g does not vanish, w does not converge (gap 0.28), the drift grows: the 11-01 change stays a configuration
step (X208 reading), not a scheduled-vol effect.

**T11 (exploratory, on the two 11-01 full-depth blocks already used by T3; `code18/nonevent.py`,
results/iter18_nonevent.json): the posts law E2 leaves to the posture.** 763 / 868 of 1,151 / 1,108 posts. Posture 0.663 /
0.575; cheaper 0.666 / 0.558; opposite of the last-hit token 0.574 / 0.574; sign of the latest publish's innovation within
1 s 0.475 / 0.531, its raw change 0.480 / 0.505 (the report reaches the side only through its first 150 ms); a futures move
>= $1 over [t - 1,000, t - 50] ms (91 / 67 posts) 0.703 / 0.702, as a branch before the posture 0.699 / 0.595 (+0.035 /
+0.020); 5-s moves >= $2 0.534 / 0.434 (the side leans against slower moves). Three quarters of the clean-block posts
follow no event we record, and their side is the posture at 0.57-0.66.

**Pre-registration T12 (written 13:07 UTC 11-01, for the next development blocks; scored by evaluate()'s
`quote_unit_side.law_E2` and the successor): law E3 = E2 with a third event branch, a futures mid move >= $1 over [t - 1,000,
t - 50] ms -> its direction, before the posture.** Blocks: 11-01 18-24, 11-02 00-06, 11-02 12-18 (dx_clob posts, dx_bnf
futures, dy_rtds publishes; the futures-only innovation with T3's frozen beta). Readings: E3 >= E2 + 0.01 and E2 >= posture
+ 0.05 on posts pooled over the three blocks, at |F - mid| < 0.05 as well; the (0, 150] publish agreement >= 0.65 (n >= 40)
on each block with (-300, 0] <= 0.55.

**X224 probe (information I17-5).** `wss://ws.perpetuals.polymarket.com/v1/ws` connects and answers
`{"status":"err","error":"invalid request"}` to three common subscribe formats (op/args, type/channel, method/params;
13:10 UTC); the subscription message is undocumented, so no 200-ms recorder was started. The 1-Hz REST recorder (X214,
`dp_perps`) keeps running to 11-03 00:00. X224 open.

**X218 recorder fix.** The first launch of code18/open_rec.py (pid 10460, 12:36 UTC) died at once: its status path pointed
one level above the repository (`HERE.parents[3].parent`). Fixed and relaunched at 13:08 UTC (pid 27416); the status file
shows it waiting for 11-02 13:15 UTC with a dm_* cap of 318.9 MB (own disk <= 60 MB).

## Missing dimensions (E2 update, iteration 18)

- **Which component fails, measured by order type (X226).** On VALIDATE 66% of filled BTC 5m cells score below the 85th
  percentile of the public presence score. Two-thirds of those misses are cells with a fresh main-ladder fill (FN 0.635),
  one third cells with only pairing / deep / remainder fills (FN 0.733). The main-ladder misses are the taker's arrival in
  quiet cells, which no public series shows before the match (the 150-ms hold makes it visible only to the engine).
- **Side, live quote unit.** Two event dimensions now explain part of the post side: the report innovation at public
  timing (`pm_legacy_rtds`, drives) and the futures 0.5-s move (`binance_usdm_futures`, drives). Of the clean-block posts
  75% follow neither; on them the posture scores 0.57-0.66 and no other recorded series adds more than +0.02-0.035 (a 1-s
  futures move >= $1). That remainder points to replenishment / queue state (`pm_queue_and_cancels`: the post after a fill
  of the same rung) or to an unrecorded input; the lag-floor test per venue (X217) is the next discriminator.
- **Side, historical.** The October cheap lean has a cluster-only time-of-day gradient (`scheduled_vol_profile`, have), but
  it is not a posture sigma (T1), not the weekly k drift (T6), not the 11-01 centre (T10), and not where the profit is
  (T8). The k drift stays the main unexplained side state: a latent (E6) candidate.
- **Selection.** No information dimension tested so far explains the module switches: daily GDELT / Fear & Greed (T14,
  iteration 17), the equity open (X223); the intraday GDELT test (X222) is in "Iteration 18" below if the throttled fetch
  completed.
- **Lead.** Three blocks now show no reaction before the public publish (the Data Streams trace is absent).

**Pre-registration T13 = X217 light form (mechanics P3; written 13:16 UTC, before any number).** Posts: at-touch 500/1000
adds 0.10-0.90, 11-01 07:00-12:00 (both full-depth tables). Feeds on their own stamps: Binance USD-M bookTicker mid,
Binance spot aggTrades, OKX swap ticker, Bybit linear best mid, Coinbase ticker, Hyperliquid bbo, Deribit index,
Bitstamp trades, Chainlink publishes (dy_rtds P). Events = signed $1 bricks. Per post the lag to the last same-sign and
opposite-sign brick; per feed the 5-ms mode of the same-sign lag in (0, 500] ms and the shares inside mode +- 15 ms.
Signature (panel): one feed with >= 30% of posts in that band and <= 10% for the opposite-sign control.

**T13 = X217 result (`code18/lag_floor.py`, results/iter18_lag_floor.json): no feed has a sharp reaction floor
(signature not met).** 2,169 posts (11-01 07:00-12:00). Share of posts with a same-sign $1 brick in (0, 300] ms vs an
opposite-sign one, and the 5-ms mode: Binance USD-M bookTicker 0.165 vs 0.085 (mode 97.5 ms), Binance spot aggTrade 0.132
vs 0.073 (87.5 ms), OKX swap 0.120 vs 0.013 (102.5 ms), **Bybit linear 0.157 vs 0.015 (117.5 ms)**, Coinbase 0.192 vs
0.100 (132.5 ms), Hyperliquid 0.050 vs 0.023, Deribit index 0.061 vs 0.029, Bitstamp 0.042 vs 0.012, Chainlink publish
0.060 vs 0.027. Inside mode +- 15 ms no feed holds more than 3.5% of posts (bar 30%). Lead (not a test): the
same-minus-opposite excess is largest for Bybit (0.142) and OKX (0.107) against Binance futures (0.080) because the
opposite-sign control is ten times cleaner there; with fewer bricks on those venues this may be event density, not the
consumed feed. Pre-registered follow-up for the next development block (T14 below).

**Pre-registration T14 (written 13:17 UTC, for 11-01 18-24 / 11-02 00-06 / 11-02 12-18 with the dx_* and dm_* feeds that
exist then): head-to-head of the futures branch of law E2 on Binance USD-M (frozen) vs Bybit linear vs OKX swap mid moves
>= $2 over [t - 500, t - 50] ms.** Reading: a venue beats Binance by >= 0.03 on the posts its branch covers and by >= 0.01
on all posts -> the engine's futures reference is that venue (or a composite); else Binance stays.

**Pre-registration T15 = E3 screen of the report-innovation events (written 13:18 UTC, before any number).** Same BUILD
blocks, decisions, units, null (swap, hour strata, 300 draws) and lag ranges (+-2 s at 0.1 s, +-60 s at 1 s) as iteration
17's T13; events: public Chainlink publishes whose futures-only innovation |u| >= $1 and >= $2 (T3's frozen beta),
signed by u. One joint BH over the 8 p-values (unsigned and signed p_link per indicator and lag range); survivors at
q <= 0.10, to be confirmed once on the live VALIDATE blocks (11-02, 11-03 development blocks).

**T15 result (`code18/e3_innov.py`, results/iter18_e3_innov.json): the screen sees the timing link, and its sharpest
signed feature is before the publish.** 7,433 posts, 75 units (68-71 in the swap null), events: |u| >= $1 (u1) and >= $2
(u2). Joint BH over 8 p-values: unsigned p_link u1 0.047 (q 0.074) at +-2 s and 0.003 (q 0.025) at +-60 s (shape peaks
-1.65 s / -0.5 s, lifts 1.30 / 1.61), u2 0.027 / 0.030 (q 0.074); signed u1 at +-2 s 0.040 (q 0.074) with its peak at
**-0.25 s and z -3.4** (posts just before a publish sit against sign(u)); signed u1 at +-60 s 0.36, u2 0.12 / 0.09.
Reading: posts bunch around large-innovation publishes (unsigned survivors), and the signed screen's strongest localized
feature is the pre-publish anti-agreement, which is mechanical: before the publish the posts follow the futures move, and
u is the report's residual against exactly that move. The (0, 150] ms agreement of T3 (0.80 / 0.86) is a feature of a few
dozen posts that 0.1-s bins over +-2 s do not isolate as the peak. Survivors go to the live VALIDATE confirmation with
T3's (0, 150] ms window as the pre-registered signed test.

**Pre-registration T16 = X221 light form (information I17-2 step 2 only; written 13:21 UTC, before any number): does the
paying crowd buy what the page displays?** BUILD 10-09..15 BTC 5m windows; crowd = taker BUY prints of wallets that are
neither HFT takers (code/hft_takers3.json) nor cluster accounts. Display, point in time with a Binance stand-in: D(t) =
S(t - 1) - K (K = Binance mean of [st - 60, st)); displayed winner = Up iff D > 0; crossing = a sign change of D inside the
window. Per crowd buy: bought the displayed winner, bought the favourite (price > 0.5), by seconds since the last crossing
([0, 10), [10, 30), [30, 300), none yet). Reading: in [0, 10) s after a crossing the displayed-winner share exceeds the
favourite share by >= 0.05 with a window-bootstrap 95% interval above 0 -> the crowd trades on the display beyond the
price; else not shown.

**T16 = X221 light result (`code18/display_crowd.py`, results/iter18_display_crowd.json): the crowd buys the price, not the
display (reading not met).** 1,561,851 non-HFT, non-cluster taker BUY prints in 2,016 BUILD windows (10-09..15). Share on
the displayed winner vs on the favourite: [0, 10) s after a displayed crossing 0.617 vs 0.614 (diff +0.0025, window
bootstrap 95% [-0.004, +0.009]); [10, 30) s 0.622 vs 0.632; [30, 300) s 0.679 vs 0.687; no crossing yet 0.600 vs 0.612.
Right after a crossing, where display and price disagree most, the crowd still follows the price. Caveat: the display is
the Binance stand-in (the page shows the Chainlink value; BUILD has no Chainlink series), so crossings within the
Binance-Chainlink basis are blurred. X221 stays open for its demand model and presence step with the real display (lot
endpoint seconds, live dy_rtds).

**T9 = X222 result (`code18/gdelt_fetch.py`, `code18/offrun_shocks.py`, results/iter18_offrun_shocks.json): not
informative.** GDELT throttled the fetch (HTTP 429 on most chunks; 618 of ~1,970 hours returned for 'bitcoin', 406 for
'(crypto OR fed OR cpi)'). The pre-registered off-run definition gives 7 BTC 5m off-runs in 08-02..10-22 (16 off stretches
of >= 60 min exist, 9 of them without 3 on windows just before); bitcoin bursts 0 of 1 covered start (placebo 0 of 7);
vol jumps 1 of 7 vs 12 of 56 placebo (0.14 vs 0.21, p 0.82). With n 7 only a burst share above ~0.6 against ~0.1 would be
detectable. X222 stays open (needs the full GDELT series at a slower request rate, or the live RSS recording).

**Pre-registration T17 = E5 hourly screen (information I17-3 regression form at hourly resolution; written 13:27 UTC,
before any number).** Hours 08-02..10-22; dependent: the BTC 5m module-on share of the hour (12 windows, >= 1 cluster BUY
trade). Regressors lagged one hour: z of log(1 + GDELT count) for 'bitcoin' and '(crypto OR fed OR cpi)' against the
previous 168 hours; z of the log mean Binance slot rv of the previous hour. OLS with hour-of-week fixed effects, s.e.
clustered by day, and per half. Reading: a news coefficient with p < 0.01, |effect| >= 0.05 on-share per sd and the same
sign in both halves -> news relates to selection hourly; else no association. Runs on whatever the throttled GDELT fetch
returned (coverage reported).

## Iteration-18 checkpoint

- Primary metric (historical VALIDATE 10-27..30, BTC 5m 10-s fill presence AUC, no own state): unchanged at **0.716**
  (activity 0.684). No frozen decision changed: R8c stays (side 0.7009 vs cheaper 0.6785; union presence 0.788 / 0.780;
  selection 0.685 / 29.5% / 2.87; price 0.803; pnl 0.207 / 0.218; coverage 0.868 / 0.891). The target is not met.
- Paradigm: the panels' scheduled-volatility hypothesis tested as an input (posture sigma, T1), an identification with a
  market control (T2), the k-cycle link (T6), the economics with exact outcomes (T8) and the 11-01 centre (T10); and, on
  the uncensored quote unit, the report innovation and the futures move as event inputs, confirmed on held-out live blocks
  (T3) and added to evaluate() (`quote_unit_side.law_E2`).
- What it showed: (1) the October cheap lean has a cluster-only time-of-day gradient (slope +0.229, p 0.002; other makers
  -0.013), but a profile posture loses to R8c on VALIDATE (-0.010), does not reproduce the open window (0.13 STUDY), is not
  the k drift (rho 0.16), not the 11-01 centre, and the high-ratio windows lose money (October -2.5% per $ in the top
  quintile vs +1.6% to +3.8% elsewhere; exact REDEEM outcomes); (2) the open window is a fixed fade (cheap 0.92-1.00 in
  all 17 development / STUDY open windows, independent of the equity open); (3) law E2 (publish innovation within 150 ms,
  else a futures 0.5-s move >= $2, else the posture) beats the posture by +0.12 / +0.09 on two held-out blocks, with the
  publish reaction in (0, 150] ms and none before it (no Data Streams lead); (4) no venue shows a sharp reaction floor
  (best band share 3.5%); Bybit / OKX $1 moves show the cleanest same-vs-opposite contrast (lead for T14); (5) 65% of
  VALIDATE presence misses are fresh main-ladder cells (taker arrival), 34% own-state order types; (6) the paying crowd
  buys the price, not the displayed strike crossing (Binance stand-in display); (7) GDELT throttled (HTTP 429), so the
  news-vs-switch tests are not informative yet.
- Catalog: closed this iteration X215, X219, X220, X223, X225, X226, X227 (tried), X59 and X118 (closed on the iter17
  information panel's measurements), E4 (tried). Open: E3 (live VALIDATE confirmation pending), E5, E6, X214, X216, X217
  (light form run), X218 (recorder armed for 11-02), X221 (light form run), X222 (GDELT throttled), X224 (subscription
  format unknown), and the older open items.
- Recorders: the shared recorder runs (clob_crypto, clob_wallets, rtds, sports); own examrec (dx_*), dy_rtds, dz_rtdsbn,
  famrec and dp_perps run to 11-03 00:00 (status files updated 9-23 s before 13:27 UTC); code18/open_rec.py (pid 27416)
  waits for 11-02 13:15 UTC. The laptop clock offset (1.3 s at 09:26 UTC) still needs a Windows time resync by the user.

**For a successor.** (1) After 11-02 14:50 UTC read the 11-02 opens (code18/open_rec.py dm_* full depth plus the shared
recorder's trades): score T5's readings (cheap share at 14:30 vs 13:30 UTC; ladder centre vs the first 3-sigma futures
jump; favourite rungs pulled or not). That decides R8c's clock before the next exam, which runs on post-DST blocks.
(2) Score T12 (law E3 vs E2 vs posture) and T14 (Binance vs Bybit vs OKX futures branch) on 11-01 18-24, 11-02 00-06 and
11-02 12-18 (live VALIDATE days are 11-02 / 11-03 by the brief's split; 11-01 18-24 is BUILD); evaluate() already reports
`quote_unit_side.law_E2`. (3) X216: dense per-minute calldata salts on 10-31 / 11-01 to calibrate the per-market quanta.
(4) X221 with the real Chainlink display (lot endpoint seconds, dy_rtds). (5) Re-fetch GDELT at one request per 12 s
(code18/gdelt_fetch.py 12 fills only missing chunks) and rerun code18/e5_hourly.py and offrun_shocks.py.

**Pre-registration T18 = X216 step 1 light (mechanics P2; written 13:28 UTC, before any number): the salt rate across the
10-31 16:53:54 BTC 5m switch-off.** Decoded calldata of the cluster's live 10-31 fills (calldata/live1031_0002..0004,
~1,900 cluster orders), block times interpolated between two eth_getBlockByNumber calls. Per wallet: the slope of salt on
time over [16:23:54, 16:53:54) vs [16:53:54, 17:05:00) (before the ad-hoc restarts), outlier-trimmed. Reading: the slope
falls by >= 2 orders/s in every wallet -> the counter rate reads the module state (X216's premise); else not shown.

**T18 = X216 result (`code18/salt_rate.py`, `code18/salt_rate2.py`, results/iter18_salt_rate*.json): the signing rate does
not drop when the BTC 5m module stops (reading not met).** The live1031 calldata ends at 16:29:40 UTC (1.5 s per Polygon
block), so the window was rebuilt from the cluster's own 10-31 activity (262 transactions decoded, 137 own orders). Slope
of salt on time over [16:23:54, 16:53:54): almach 11.89, bosona 11.78, mo-money 11.82 orders/s (14:01-16:29 calldata:
11.9-12.7). Across the switch-off the counters advanced 1,319 in 105 s (almach), 1,235 in 90 s (mo-money) and 271 in 21 s
(bosona): 12.6-13.7 orders/s; almach after it 14.5 (n 7). So the per-wallet counter keeps its ~12 orders/s whether or not
the BTC 5m ladder is quoted: it is not a fill-free readout of the module state (X216's premise fails at its first check);
a constant-rate signing loop, or capacity moving to the other markets, both fit. X216 tried.

**Pre-registration T19 = X202 light (written 13:31 UTC, before any number): one engine pass for all markets?** All at-touch
schedule adds (62 / 250 / 500 / 1000) of 11-01 07:00-12:00 (full depth; BTC 5m current + next, BTC 15m current). A post is
in a multi-window pass if another window has a post within +-25 ms; null: each window's times shifted by +-1-5 s (50
draws). Readings: multi-window share >= 2 x null -> passes exist; side agreement across windows in a pass >= 0.8 -> one
input re-sides all markets; the trigger mix of passes (publish innovation within 150 ms, futures move >= $2 over 0.5 s,
neither) against single-window posts.

**T19 = X202 result (`code18/passes.py`, results/iter18_passes.json): passes across markets exist but are rare, and inside
a pass one input re-sides every market.** 4,422 at-touch adds in 79 windows: 3.4% sit within +-25 ms of another window's
add (null 0.55%, p95 0.84%: 6x); inside those passes the other windows' adds go the same way in 0.96. Pass triggers: a
futures move >= $2 over 0.5 s 29.5% (single-window posts 15.3%), a publish innovation 3.4% (4.4%), neither 67% (80%). So the
engine mostly re-prices window by window; the joint passes are futures-driven and directional. X202 tried (light).

**X218 readout prepared.** `code18/open_read.py <W> [<W2>]` reads, for BTC 5m windows starting at W, the full-depth
cluster-size adds per outcome and 10-s bin (price, ladder centre vs mid), the first cheap-side add and the first 3-sigma
futures jump after the open, and the cluster's BUY fills with their cheap share (data-api activity, development units).
Smoke test on 11-01 07:30 UTC (development): 1,647 exact-size adds (other makers' exact sizes included, ~12%), first cheap
add +0.06 s, cheap share of adds 0.30 (0-60 s) / 0.16 (60-300 s), first futures jump +49.7 s, 26 cluster fills (bosona
only), cheap share 0.69. For 11-02: `open_read.py 1793629800 1793626200` (14:30 UTC treatment, 13:30 UTC placebo).

**Pre-registration T20 = E7 on law E2 residual (written 13:35 UTC, before any number).** 11-01 07:00-09:15 and
09:15-12:00 at-touch 500/1000 posts (0.10-0.90): E2 misses vs hits; residual_clustering, delta 0.5 s and 2 s, period
900 s, 1,000 draws, market = window. Synchrony counts only with p <= 0.01, ratio >= 1.5 and a miss ratio >= hit ratio + 0.3.
Reading: if the E2 misses still coincide across windows, a common driver beyond the futures and the publish remains.

**T20 result (`code18/e7_e2.py`, results/iter18_e7_e2.json): E2's misses still coincide across windows at sub-second scale
on one of two blocks.** 11-01 07:00-09:15 (1,065 posts, miss share 0.272): misses delta 0.5 s ratio 8.0 (p 0.12, n 290)
vs hits 3.16 (p 0.003): not synchrony by the bar. 11-01 09:15-12:00 (1,108, miss share 0.358): misses 8.57 (p 0.006, n 397)
vs hits 4.81 (p 0.007): **meets the bar at 0.5 s**; at 2 s misses 2.97 (p 0.03) vs hits 3.17: no. Reading: both hits and
misses sit in cross-window passes (T19), and on the later block the wrong-side passes are tighter than the right-side
ones, so a common sub-second driver beyond the Binance futures and the publish remains for part of the residual
(candidates: another futures venue, the lead of T13, or the engine's own pass schedule). Pointer for T14.

**Checkpoint addendum (13:38 UTC).** After the checkpoint above: T18 (X216: the per-wallet signing rate keeps ~12-14
orders/s across the 10-31 BTC 5m switch-off, so it does not read the module state; X216 tried), T19 (X202: cross-window
passes are 3.4% of posts, 6x the null, futures-driven, sides agree 0.96; X202 tried), T20 (E7 on E2's residual: misses
synchronize at 0.5 s on 11-01 09:15-12:00, not on 07:00-09:15), the 11-02 readout code (code18/open_read.py, smoke-tested on
11-01 07:30). The throttled GDELT re-fetch (code18/gdelt_fetch.py 12, missing chunks only) was still running at 13:38 UTC;
code18/e5_hourly.py (T17, pre-registered) runs on whatever it returned.

**Notes on the pre-registrations of this iteration.** T3 (law E) ran on the design the information panel fixed in its
proposal I17-1 (innovation model, theta $1, the (0, 150] ms window, the k3 / 0.5-s jump detector, the confirmation blocks
and the signature); no separate NOTES entry was written before it ran. T3b (law E2) was written at 12:46 UTC, after E had
been scored on the freeze block and on 10-31 17:29-18:00 and before the 11-01 09:15-12:00 posts were rebuilt, so the
09:15-12:00 numbers are out of sample for both laws, while E2's 10-31 number is not. T14 can be scored only where OKX and
Bybit are recorded after 11-01 12:00: the 11-02 13:15-13:50 and 14:15-14:50 windows of code18/open_rec.py (dm_okx,
dm_byb); dx_* carries Binance only. Times of the pre-registrations were corrected to the shell clock (`date -u`).

**T3 robustness by hour (`code18/e2_hours.py`, results/iter18_e2_hours.json; descriptive, same frozen law).** E2 vs the
posture per hour: 07:00 0.743 vs 0.599, 08:00 0.710 vs 0.586, 09:00 0.695 vs 0.513, 10:00 0.560 vs 0.414, 11:00 0.668 vs
0.606: the gain holds in every hour (+0.06 to +0.18).

**T21 (exploratory, in sample on the two 11-01 blocks; `code18/venue_h2h.py`, results/iter18_venue_h2h.json): which venue
carries the futures branch?** E2 with its futures branch on each venue's own mid (move >= $2 over [t - 500, t - 50] ms):
Binance USD-M 0.721 / 0.643 (07:00-09:15 / 09:15-12:00), Bybit linear 0.675 / 0.635, Binance spot 0.679 / 0.579, Coinbase
0.670 / 0.599, OKX 0.666 / 0.592 (posture 0.590 / 0.520). Binance USD-M is the best single venue on both blocks; Bybit's
branch is as accurate where it fires (0.85 / 0.95) but fires less. T13's Bybit / OKX contrast was event density, not the
consumed feed; T14 stays pre-registered as the out-of-sample check.

**T17 result (`code18/e5_hourly.py`, results/iter18_e5_hourly.json) after the slower GDELT re-fetch (1,979 hourly rows:
953 'bitcoin', 1,026 macro, about half of 08-02..10-22; still partly refused with HTTP 429).** Module-on share per hour with
hour-of-week fixed effects, day-clustered s.e.; the z needs >= 100 of the previous 168 hours, so the news regressors cover
33-34% of the 1,968 hours (vol 95%): 'bitcoin' z +0.024 per sd (s.e. 0.012, p 0.046; first half +0.020, p 0.10; second half
50 hours), macro z -0.012 (p 0.28), Binance vol z -0.006 (p 0.75). Reading not met (p < 0.01 and >= 0.05 per sd): no hourly
association of news volume or volatility with the BTC 5m module state at this coverage; an effect of +-0.03 per sd would
have been detectable. T9 rerun on the fuller series: bursts before off-run starts 0 of 2 covered ('bitcoin'; placebo
0.06) and 0 of 1 (macro). X222 stays open (half the hours missing); E5 open.

Final state of iteration 18 (13:47 UTC): frozen rule R8c unchanged; target_metrics unchanged; primary metric 0.716.
evaluate() additionally reports `quote_unit_side.law_E2` (smoke-tested on 11-01 09:00-09:30: E2 0.779 vs posture 0.702,
n 299). Recorders: shared recorder running; own recorders running to 11-03 00:00; code18/open_rec.py waiting for 11-02
13:15 UTC. The cache folder is at its 1.5 GB cap (this iteration added 2.6 MB).

**Pre-registration T22 = X207 light (written 13:48 UTC, before any number; own state, reported as such): a rolling loss
breaker for the BTC 5m switch-offs.** Realised BTC 5m PnL per window (cluster BUY trades, exact REDEEM outcomes) booked at
window end + 60 s; rolling 2-h and 6-h pooled sums at t. Events: every BTC 5m off stretch >= 60 min in 08-02..10-22;
placebos: up to 20 per event at the same hour-of-week in other weeks with the module on in the previous 15 min. AUC of
-PnL (events vs placebos), label-permutation p (2,000). Reading: AUC >= 0.75 with p < 0.01 -> a loss breaker; else not shown.

**T22 = X207 result (`code18/mtm_breaker.py`, results/iter18_mtm_breaker.json; own state): switch-offs follow recent losses
on average, but not as a sharp breaker (reading not met).** 16 off stretches (08-02..10-22) vs 312 placebos: rolling 2-h
realised BTC 5m PnL AUC 0.624 (p 0.059; median -$211 before events vs +$366); rolling 6-h AUC **0.685 (p 0.0075; -$748 vs
+$929)**. The 6-h association is real at p < 0.01 but below the 0.75 bar: losses raise the chance of a switch-off without
fixing its time (as X152 found with the drawdown since the restart). Reported as own state; selection stays a hypothesis.
X207 tried (light).
