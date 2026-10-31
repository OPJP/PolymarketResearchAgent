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
