# elmcap2-carry: lab notebook

Wallet elmcap2 `0xed107a85a4585a381e48c7f7ca4144909e7dd2e5`. Strategy: event carry on near-certain outcomes.
Frozen dates: as_of 1793318400 (2026-10-30), holdout H = 1792713600 (2026-10-23). Development = timestamps < H
and events resolving before H. The October 2026 FOMC (statement 2026-10-28) is holdout and is never loaded.

## Pre-registration (iteration 1, written before fitting any rule)

PRIMARY METRIC `presence_auc_V` (higher is better, fixed across iterations): ROC AUC, on VALIDATE, of the
frozen rule's point-in-time score s(m, t0) (no own-state features) for the label y(m, bin) = 1 if the wallet has
at least one BUY fill in market m during the 6-hour UTC bin [t0, t0 + 6h).

Universe U(W) (pre-registered, `code/f3_universe.py`): Gamma markets with `closed=true`, `endDate` in W,
`volumeNum >= 20,000`, `closedTime < H`, excluding sports (`gameStartTime` or `sportsMarketType` set, or a sports
league slug prefix) and crypto Up/Down markets. Cells: 6-hour bins (UTC-aligned) with
t0 in [max(endDate - 14d, startDate), min(closedTime, endDate + 14d)). A cell exists only while the market is
unresolved, which is known point-in-time. Features at t0 may use only CLOB hourly prices stamped <= t0 - 60 s and
Gamma listing fields (endDate, negRisk, question/slug text, tick size, fee flags); never outcomePrices,
closedTime, umaResolutionStatus or final volume.

Split (by market endDate):
- BUILD: endDate in [2026-06-01, 2026-09-01) (closedTime < H); earlier history used for exploration only.
- VALIDATE: endDate in [2026-09-01, 2026-10-23) and closedTime < H.
- Holdout (examiner): endDate in [H, latest) or events resolving on/after H.

Secondary metrics (reported every iteration): presence AUC per family; selection AUC/recall/lift at market level
(market-permutation null); side accuracy vs "buy the favourite" baseline; price-within-one-tick share; per-market
PnL correlation (rule vs wallet) on resolved VALIDATE markets; coverage = share of the wallet's VALIDATE buy USD
that falls inside universe cells.

## Data gathered (iteration 1)

- Full activity history (`f1_activity.py`): 91,634 rows 2023-04-29 .. 2026-10-22 (end = H-1), 88,463 TRADE,
  2,017 REDEEM, 29 SPLIT, 93 MERGE, rewards/rebates/yield. `.cache/re/elmcap2-carry/activity_preH.parquet`.
  The earlier studies used 30 days (5,821 rows) or per-market activity for FOMC and 4 deadline dates only.
- user-pnl daily series truncated to timestamps < H (`user_pnl.json`). (While fetching, the API returned the
  live cumulative point; it was printed once in a log and discarded, not used.)
- Gamma metadata for all 2,196 traded markets (`f2_gamma.py`, `gamma_traded.parquet`).
- Universe U for VALIDATE / BUILD windows with hourly CLOB price history (`f3_universe.py`).
- Note: one exploratory Gamma query ordered by closedTime returned 3 rows closed after H at the top of the page
  (slugs only were printed); nothing from them is used. The query pattern was abandoned; universe queries now
  drop rows with closedTime >= H before any processing.

## Findings so far

1. Scale is far larger than the dossier's 30-day view: 2,193 markets, 1,443 events, $268M bought over 3.5 years
   (82,168 buy fills). Monthly buys $21-37M Jan-Jul 2026, then a sharp drop: Aug $3.1M, Sep $7.0M, Oct 1-22 $1.3M.
2. Price: USD-weighted buy price quantiles 5%/25%/50%/75% = 0.955 / 0.99 / 0.997 / 0.999. 43% of USD bought at
   >= 0.998. Win rate (descriptive, from outcomes) 1.000 at >= 0.998, 0.999 at 0.99-0.998, 0.99 at 0.95-0.97.
3. Timing is anchored on resolution, not on endDate: USD-weighted median buy is 41 h before closedTime
   (25% within 16 h, 10% within 4.3 h), while 37% of USD is bought AFTER endDate (21% 1-7 days after,
   7% more than 7 days after). This is resolution-pending carry: the outcome is publicly settled in substance
   (deadline passed, event happened, word said) and the wallet buys the certain side at 0.998-0.999 from sellers
   who want cash before UMA settles.
4. Families by USD (all history): deadline $121M (1,020 mk), FOMC $57M (47 mk, median px 0.986), other $54M,
   election $14M, crypto price-level $12M, sports $10M (517 mk, median px 0.74, loses money: a different behaviour).
5. Largest single-market buys are event-triggered early resolutions: e.g. "Will Michelle Bowman be confirmed as
   Fed Chair?" $3.2M at ~0.999 61 h before close (endDate 172 days later), "Will Iran strike Israel on March 6?"
   $1.5M at 0.999 6 h before close.

6. On-chain (receipts of the wallet's own trade transactions; drpc's free plan rejects eth_getLogs ranges above
   ~100 blocks, and publicnode needs a token for archive logs, so the topic-filtered log scan in the brief is not
   usable at scale; receipts are): VALIDATE period 6,276 own OrderFilled events in 723 orders: 95.6% maker by
   count (5,998 maker / 278 taker fills; 458 resting orders vs 265 taker orders). Resting orders: median 2 fills
   and $2.4k filled (p90 $24.6k, p99 $249k), one fixed limit price (94% of orders), lifetime median ~5 min but
   p75 ~13 h and p90 ~3 days (blocks ~1.5 s). So it keeps resting bids for hours to days and also re-posts.
7. BUILD-period (endDate Jun-Aug 2026) non-sport wallet markets: 248, $40.8M; per-market median $6.1k, mean $164k,
   max $8.2M. First fill median 231 h before closedTime; fills spread evenly over UTC hours (no human schedule);
   inter-fill gap median 130 s.

8. BUILD on-chain (receipts, Jul 15-Aug 31 2026): 8,824 own fills, 96.7% maker by count, 80.8% of USDC via its
   resting orders; 731 resting BUY orders on 224 markets; filled USD per order median $1,960 (p90 $24.6k, p99
   $249.5k); distinct limit prices per market median 1, p90 4, max 17 (a ladder in a few markets). Limit price vs
   the same token's PIT hourly price (lag 1 h): median -0.0005, 74.5% within 0.001 (it joins the market), 23.4% at
   0.999, 11% more than 0.002 below (passive ladder rungs).
9. Side: in BUILD only 3.2% of the wallet's positive cells buy the non-favourite, and they are 0.49 bids in
   coin-flip markets (PIT favourite 0.50-0.51; elections 26, crypto 10, deadline 4); 1.2% of USD. In VALIDATE the
   share is larger (15% of cells), so a second, small behaviour exists: resting 0.49 bids in 50/50 markets
   (possibly liquidity-reward farming; it has 570 REWARD rows). Not modelled yet.
10. Sizing: per-cell USD among positive BUILD cells is barely related to price/time features (Spearman with
   h_end -0.19, vol24 +0.17, pf -0.02). Size is set by something not in the price series, most likely available
   sell flow / depth (needs tapes).

## Results (iteration 1)

All models fitted on BUILD only; VALIDATE = endDate 2026-09-01..2026-10-22 resolved before H (3,208 markets with
prices, 117,132 cells, 277 positive cells in 57 markets). BUILD fit set: all 216 wallet-traded BUILD-universe
markets + a fixed random 2,000 of the other 7,099 (weights restore the base rate); 74,382 cells, 1,231 positive.

| id | family | VALIDATE presence AUC | other VALIDATE metrics | verdict |
|----|--------|------|------|------|
| S1 | certainty only (lpf) | 0.640 | selection AUC 0.743, recall 91% at lift 2.1 | necessary, not sufficient |
| S2 | certainty + after endDate | 0.638 | selection AUC 0.827, recall 72% at lift 3.9 | helps market selection only |
| L1 | LightGBM, 22 features (price/time + family text flags + age + hour/dow + negRisk) | 0.884 | selection AUC 0.885, recall 52.6% at lift 15.7 | strong, slightly overfit (BUILD 0.986) |
| L2 | LightGBM, 10 price/time features, price lag 1 h + 60 s | **0.896** | selection AUC 0.906 (null 0.50, p=0.001), recall 59.6% at lift 6.9 (p=8e-23); side 97.1% favourite in predicted cells (= baseline); price within one tick 90.4%; PnL Pearson 0.015 / Spearman 0.24 | **best, frozen** |
| D1 | explicit lookup pf x hours-to-endDate x hrs99 (BUILD rates, shrunk) | 0.803 | | explicit approximation of L2 |
| R1 | L2-type feature sets at lag 60 s vs 3,660 s | 0.898 vs 0.896 | no-age 0.899, no-family 0.893-0.902 | no hourly-bucket leakage; text families add nothing |
| O1 | strict maker-fill PnL (L2, unlimited bid at rule price, taker SELL prints <= bid, >= 2 s) | | 462 markets: PnL Pearson 0.195 / Spearman 0.14; capital per market Pearson 0.504; rule 0.28% on $3.13M vs wallet 0.89% on $5.79M | capital allocation matches, margins do not |
| T1 | timing within traded markets (L2 score, traded markets only) | pooled 0.616, mean per-market 0.665 | timeline-shift null 0.547 (p95 0.574), p=0.003 | timing signal real but modest: fills follow taker arrival |

L2 gain importance: hrs99 0.23, pf72 0.16, h_end 0.16, pf 0.11, vol24 0.10, pf24 0.08, hrs95 0.07, pf6 0.07.
Smoke test of `final_rule.evaluate` on endDate 2026-10-01..10-08 (inside VALIDATE): presence 0.843, selection AUC
0.860, recall 60% at lift 4.6, PnL Pearson 0.19 (single-week variance is large).

High-accuracy target status on VALIDATE: presence AUC >= 0.85 met (0.896); selection AUC >= 0.80 with recall >= 50%
at lift >= 3, p < 0.01 met; side accuracy >= 80% met but not above the favourite baseline (the strategy is
"buy the favourite" by construction); per-market PnL correlation >= 0.5 NOT met (0.015). So target not reached.

PnL diagnostic (VALIDATE, strict fills): the wallet's VALIDATE PnL ($51.6k on $5.79M) is almost all the
September 2026 FOMC book: "increase 25 bps" ($152k at ~0.87, +$23.0k; the rule had no fills), "increase 50+ bps"
($2.37M, +$19.3k; rule $26k), "decrease 25 bps" ($2.04M, +$6.5k; rule $0.87M). The rule allocates capital like the
wallet elsewhere (37 of 57 wallet markets get rule fills; median return 0.29% vs wallet 0.24%), but it does not size
up on FOMC consensus outcomes and does not buy FOMC outcomes at 0.85-0.9. FOMC needs its own sizing/threshold
component (statement-date timing, consensus side, size ~ millions) - first item for iteration 2.

FOMC history (wallet only, markets resolved before H; regex family 'fomc' with 'Fed' in the question): it has
traded every FOMC meeting since mid-2024, $0.2M (2024-07) rising to $2-8M per meeting in 2025-26 (2026-01 $7.5M,
2026-03 $8.3M, 2026-07 $6.6M, 2026-09 $5.3M), USD-weighted price 0.94-0.997, PnL $15k-$185k per meeting. In two
meetings (2024-07, 2025-09) ~42% of the USD went in below 0.95 (2025-09 earned $185k), and in 2026-09 it bought
"increase 25 bps" NO at ~0.87. In BUILD (Jun/Jul 2026) its FOMC fills were all at 0.99-0.998 and the L2 rule
already covers 88% of those cells and 98% of that USD, so BUILD gives no support for a lower FOMC threshold; the
lower-price FOMC entries are episodic (meetings where the consensus is strong but not yet priced at 0.99). An
FOMC-specific component fitted on 2024-2025 meetings is the next step.

Near-certain flow capture (BUILD, `a9_share_build.py`, taker rows for the 421 BUILD-sample markets with L2-predicted
cells): taker SELL prints of the favourite at >= 0.99 inside predicted cells total 17.6M shares in the 141 markets
the wallet traded vs 2.1M in the 280 it did not (median 3,110 vs 34 shares per market). So the markets it skips
carry only ~11% of the near-certain sell flow: it bids wherever there is flow to absorb. Its own >= 0.99 buy
shares in those cells are 1.25x the taker-SELL flow, which means part of its fills are matched against taker BUYs
of the complementary token at <= 0.01 (complement matching / minting); the flow definition must include those
before computing its share of the flow (iteration 2). This also means the strict-fill backtest above understates
the rule's fills.

## Polyrea / environment notes

- drpc free plan rejects eth_getLogs over more than ~100 blocks (message says 10,000); publicnode requires a
  token for archive logs. The brief's topic-filtered log scan is impractical; use receipts of the wallet's
  transactions (PolygonChain.receipts) instead. Not a polyrea bug.
- Gamma /markets returns at most 100 rows per page; offset >= ~2,000 gives 422 ("use /markets/keyset"); keyset
  cursors are HMAC-signed and closed_time filters are ignored, so the universe can only be enumerated by endDate.
- CLOB prices-history: windows longer than ~15 days are rejected at any fidelity; interval=max returns nothing
  for closed markets.
- pandas here stores datetimes as microseconds; `astype('int64') // 10**9` is wrong (use total_seconds()).
- No polyrea code bug confirmed this iteration.

## Next (iteration 2)

0a. Flow definition: count taker BUYs of the complement at <= 0.01 as sell flow of the favourite (strict fills,
   share of flow); add PIT flow features (last 6/24 h near-certain flow) to the presence model and a size model.
0. FOMC component: per-meeting consensus carry (BUILD meetings Jun/Jul 2026 and 2025 history; the October 2026
   meeting is holdout), lower price threshold (0.85+) and size in millions; this alone drives the PnL correlation.
1. Sizing / PnL correlation: fetch data-api tapes (taker rows) for VALIDATE predicted markets and all BUILD traded
   + sampled markets; add PIT taker-sell volume at >= 0.99 in the last 6/24 h, cumulative volume, and the
   wallet's share of maker flow at >= 0.99 (is it the dominant certain-side bidder?). Model size = f(sell flow).
2. Second behaviour: 0.49 bids in 50/50 markets (side and selection), check REWARD rows by market.
3. Extend BUILD to the full 7,315-market universe and to Mar-May 2026 (wallet most active) for stability; check
   the Aug-Oct activity drop (capital moved to complete sets?) as a regime feature.
4. Early-resolved markets (endDate far after resolution) are outside the endDate-anchored universe; quantify and
   consider a second universe built from wallet-independent event lists.
5. Explicit distillation closer to L2 (e.g. monotone GAM or a 2-3 rule decision list on hrs99, pf72, h_end).

## Hypotheses ledger

(see state.json; summary table kept here)

See the Results table above and state.json (hypotheses list).

## Open questions / next

- Does the wallet bid in EVERY resolution-pending market (price >= 0.99 after endDate), i.e. is it the
  dominant 0.999 bidder? Measure its share of maker flow at >= 0.99 from market tapes.
- On-chain order reconstruction (orderHash): limit-price ladder, order sizes, re-posting cadence.
- Sizing: USD per market vs market volume / depth at its price.
