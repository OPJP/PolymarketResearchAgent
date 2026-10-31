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
