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

## Hypotheses ledger

(see state.json; summary table kept here)

| id | family | description | VALIDATE | verdict |
|----|--------|-------------|----------|---------|

## Open questions / next

- Does the wallet bid in EVERY resolution-pending market (price >= 0.99 after endDate), i.e. is it the
  dominant 0.999 bidder? Measure its share of maker flow at >= 0.99 from market tapes.
- On-chain order reconstruction (orderHash): limit-price ladder, order sizes, re-posting cadence.
- Sizing: USD per market vs market volume / depth at its price.
