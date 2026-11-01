# btc5m-bot: exam round 1 (lot h1), independent examiner

Lot h1: every BTC 5-minute Up/Down window that starts on 2026-10-23, 10-25, 10-27 or 10-29 UTC. The rule is the frozen iteration-14 rule
(`code/final_rule.py`, sha256 starting 0523a66c, last modified 11-01 13:25 UTC, before the exam). Everything below was recomputed
from the chain, the data-api tapes, the public Hugging Face capture and the exchange archives, using only the exam cache
`.cache/exam/btc5m-bot`.

## Verdict

| | result |
|---|---|
| target_met | **false** |
| (6) match | **partial**: the side is decoded, but the presence and selection gains over market activity are below 0.05, and the PnL correlation is below 0.5 |
| (7) backtest | **fail**: the executable rule makes -0.98% before rebates with fills timed as the RE did (P(return <= 0) = 0.77), and -2.39% once block-time slack is respected |
| (8) replicable | **fail**: the edge needs colocation and a ~100-ms Binance feed inside a 150-ms taker hold; a copy that trades 2 s later loses money |
| (9) persists | **fail**: the deploy-now statement is not supported (the rule loses; the wallets' own edge persists, but it is not available to a normal user) |
| components | selection pass, timing partial, side pass, price partial, size partial, exit pass |

## 0. Sufficiency (listing metadata only)

- Windows listed: 1,152, i.e. 288 on each of the 4 days. The halves were fixed by listing start time before any fill was read:
  - earlier half: 10-23 and 10-25 (576 windows);
  - later half: 10-27 and 10-29 (576 windows).
- The truncation sample was drawn from the listing with seed 20261101: 12 windows, 20 decision seconds each.
- Power:
  - 48 two-hour blocks;
  - the iid SE of a per-window correlation near 0.5 is 0.022 pooled and 0.031 per half;
  - presence has 81,981 positive block seconds, so an AUC SE is below 0.002.
- The exam was not deferred. Data actually used:
  - 1,131 traded windows;
  - 160,664 cluster BUY fills;
  - 92,963 unique taker orders, 95.7% of them matched to the capture.
- Gaps:
  - the public capture has no rows for 23:00-24:00 UTC on any day, so the decision-clock routes miss 4.3% of taker orders;
  - the Binance USD-M archives for 10-28 return HTTP errors. Only next-day look-ahead files were affected, and feed coverage stays at 1.000;
  - h1 has no live recordings, so the live components return None.

## 1. Leakage audit: **not passed** (one item failed; the verdict does not depend on it)

What passed:
- **Constants.** Every rule parameter is a module constant. The models are frozen files dated 10-31 or earlier. ALLOW_SEALED is False in code/.
- **No sealed reads in development code.**
  - Every archive, Bybit-book and capture loader refuses days that end after H unless the examiner passes `allow_sealed`. The L2 ingest asserts `DAY < 2026-10-23`.
  - A scan of `.cache/re/btc5m-bot` (`exam/leak_scan.py`) found no file name or parquet time range inside [H, T0). The 79 files dated after H all lie in the development blocks 10-31 00-06 and 12-18.
  - No code reads `.cache/live/sealed/`, `http.sqlite` or another strategy's workspace. The recorders only write through `live.py Writer`.
  - Gamma records are stored for development windows only.
- **Truncation and corruption tests at the code's own stated horizons** (`exam/trunc_test.py`, `exam/trunc_dc.py`). All inputs after the cut were replaced by noise (timestamps kept), and the windows' features were rebuilt with the frozen functions:
  - 960 / 960 checks identical (block-second full model, pure baseline, decision-aligned model, net-flow model);
  - decision-clock side features: 300 / 300 orders identical;
  - hazard features (inputs of the PnL target): 200 / 200 bins identical;
  - the clean rebuild reproduces evaluate() (max |dp| 0.021 on one window, from float order).
- **Own prints.** The three wallets' prints, and transactions that hold one of their maker fills, are excluded from every feature.

What failed:
- **The block-second presence unit does not respect the 2-s block-time slack.** A fill stamped at block second s matched up to 2 s earlier, but the unit uses others' prints stamped s-1 and venue trades in [s-2, s-1). Corrupting only that slice changes 480 / 480 sampled predictions (mean |dp| 0.178, p90 0.437). Its AUC therefore includes post-match continuation. The slack-clean decision-aligned unit is reported next to it (section 3).

Smaller items:
- The operator's fan-out wallets W4 / W5 count as market activity in the tape features. They print in [s-3, s-1] for 8% of block cells and 19.9% of positives, and excluding those cells leaves the gain over the strongest baseline at +0.012.
  - Ruling on X170: W4 is signed by the same process in the same bursts, so it is the operator's own wallet and belongs in own state.
- The hazard's Polymarket inputs end 55-105 ms after the decision, in both the model and its baseline.
- nf12b's `prev_up_spot` reads the close of start-1 at rel 0-1, at most 1 s early.

## 2. evaluate() on the lot

- **How it was run.** `exam/run_eval.py` ran `evaluate(a, b, intervals=[(a, b)])` on 16 six-hour chunks. A 4-day call would not fit in memory (peak 1.99 GB per chunk). Each run took 4,719 s and returned no errors.
- **No file in code/ was changed, so there is no patch diff.** The driver only:
  - sets `ALLOW_SEALED = True`;
  - points `EVAL_DIR` at `.cache/exam/btc5m-bot/eval`;
  - wraps functions read-only to save intermediates;
  - memoizes capture row groups, returning exactly the rows the consumers keep.
- **Smoke test.** On development data (10-22 22-24) the driver reproduces the RE's 0.846 vs 0.784.
- **Aggregates over the 16 chunks** (pooled AUCs are in section 3):
  - side at the decision clock: 0.8193 per taker order;
  - block-clock side: 0.7608 per one-sided second, against 0.6314 for the market-only model;
  - price (calldata touch): 0.9534 on 14,130 sampled orders;
  - order signing inside the predicted ladder bursts: 99.6%;
  - mix14 tracker: -0.98%; 30-share strict replica: -2.33%;
  - per-chunk presence 0.835-0.897 against the pure baseline's 0.79-0.86.

## 3. Independent recomputation

All results come from the examiner's own code (`exam/an_*.py`), which reproduces evaluate() exactly wherever both compute the same number.

### Presence and selection

| metric | pooled | earlier half | later half | GF | XM | DS |
|---|---|---|---|---|---|---|
| block-second presence AUC, frozen full | **0.8673** | 0.8718 | 0.8627 | 0.8615 | 0.8408 | 0.8526 |
| RE's capture-aware MSB baseline (pres14 recipe, refit on 10-17..19) | **0.8564** | 0.8574 | 0.8558 | 0.8580 | 0.8583 | 0.8387 |
| RE's pure baseline (model_it5_blk_pure) | 0.8190 | 0.8169 | 0.8200 | 0.8114 | 0.8060 | 0.8033 |
| examiner's own MKTX baseline (BUILD, same class and budget) | 0.8214 | 0.8188 | 0.8234 | 0.8134 | 0.8069 | 0.8055 |
| gain over the strongest (MSB) | **+0.0109 [0.0072, 0.0145]** | +0.0144 | +0.0069 | +0.004 | **-0.018** | +0.014 |

The examiner's baselines use the same LightGBM model class and tuning budget as the RE's, fitted on BUILD 10-09..15.

- **Gains over the other baselines.**
  - Over RE pure: +0.0483 [0.0450, 0.0515].
  - Over MKTX: +0.0459 [0.0412, 0.0497].
  - Even against the RE's own weakest baseline the gain stays below 0.05. P(gain <= 0) < 0.0005 everywhere, but P(gain <= 0.05) = 1.0 against MSB.
- **Window-permutation null** (2,000 draws): 0.587 mean, 0.600 max, p = 0.0005.
- **At the frozen threshold 0.30:** recall 64.5% at lift 2.77.
- **Slack-clean decision-aligned unit** (label at s+1): 0.9053 vs RE pure 0.8765 (+0.029 [0.027, 0.031]). Halves 0.908 / 0.903.
- **All seconds:** 0.9115 vs 0.8902.
- **Selection** (every in-window taker print, 1.72M):
  - AUC 0.8939, recall 73.5% at lift 5.34;
  - baseline 0.8762, so the gain is +0.0177 [0.0151, 0.0204] < 0.05;
  - per wallet the AUCs are 0.89-0.90 with the same gap.
- **Decision-clock hazard** (reported, not the pre-registered unit): 0.85-0.93 per chunk against 0.73-0.82 for its Polymarket-prints-only baseline. That baseline has no book, and the RE showed that a book-aware one closes most of the gap.

### Side (the decision-clock route; the examiner's own feature code, identical to evaluate on every chunk)

- **Accuracy:** 0.8193 per taker order.
  - Halves: 0.8213 / 0.8176.
  - By wallet: DS 0.8204, GF 0.8255 (0.825 / 0.826), XM 0.7789 (0.789 / 0.772).
- **Baselines on the same orders:**
  - market-only: underdog 0.538, others' last taker buy 0.538, favourite 0.462, Polymarket momentum 0.50-0.51;
  - own inventory (buy the short leg): 0.506 for the cluster, 0.505 per wallet.
- **Tests:**
  - McNemar against the best market-only baseline: p ~ 0;
  - within-window permutation null (2,000 draws): 0.512 mean, p = 0.0005;
  - placebo anchors at m +- 3 s: 0.47-0.52 on every chunk.
- **Globex session:** open 0.818, closed 0.824. The ~2.5-point gap the RE predicted is not there.
- **Applicability:** XM is one-sided in 19.9% of its windows, against an order-count null of 18.3%. GF is at 3.2% and DS at 0.4%.
  - So by the 20% rule the side condition does not apply.
  - If it did, it would be met, with XM inside the 3-point tolerance.
- **Coverage:** taker orders only. Maker fills (26% of USDC; 47% for XM) have no side rule.

### Price (calldata touch, 14,130 sampled cluster taker orders)

- **Within one tick of the touch:** 95.3% (exact 84.7%).
  - Halves: 95.4 / 95.3.
  - By wallet: DS 97.1, GF 94.2, XM 81.8 (halves 80.4 / 83.0).
- **Trivial anchors on the same orders:**
  - touch + 1 tick: 97.5%, better than the rule;
  - touch - 1 tick: 84.7%;
  - last implied ask from prints at s-1 (the only point-in-time anchor): 50.4%.
- **Limits 2 c or more above the touch:** 4.7% overall, 18% for XM.
- The condition holds only under the brief's proviso. The rule is the trivial touch anchor, read off the match itself, and it is not a forecast.

### Outcome (the examiner's re-implementation of the tracker; identical to evaluate on every chunk)

| convention | per-window PnL corr P / S | halves | GF | XM | DS | rule return before rebates |
|---|---|---|---|---|---|---|
| frozen (a): prints [s+1, s+3], capture 1.0 | **0.4245 / 0.4114** (CI 0.371-0.478 / 0.357-0.463) | 0.445/0.456, 0.402/0.367 | 0.279/0.269 | 0.141/0.167 | 0.416/0.375 | **-0.98%** on $154k (P(<= 0) 0.77, CI [-3.6%, +1.7%]) |
| slack 2 s: prints [s+3, s+5] | 0.418 / 0.404 | 0.439/0.452, 0.394/0.358 | 0.276/0.264 | 0.144/0.163 | 0.407/0.368 | **-2.39%** on $134k (P(<= 0) 0.945) |
| (a), capture 0.5 | 0.420 / 0.408 | | | | | -1.11% |

- **Rotation null** for the frozen convention (4,000 draws, shifts of at least 1 h): p = 0.00025 pooled and 0.0005 per wallet. The rule tracks the wallets far better than chance, but below the 0.5 bar.
- **With a 50% fee rebate:** +0.56% (P(<= 0) = 0.33), not significant. A newcomer is on the 0% rebate tier.
- **30-share strict replica:** -2.33%.
- **By day (frozen convention):** 10-23 -1.6%, 10-25 -0.3%, 10-27 -3.2%, 10-29 +1.1%.
- **Wallets' own return on the same windows:** +0.92% before rebates (P(<= 0) = 0.014) and +2.05% with the 50% taker-fee rebate (p ~ 0).
  - By wallet before rebates: GF +1.14%, XM +2.29%, DS +0.56%.
  - Earlier half +0.12% (n.s.), later half +1.58%.
- **Exit** (activity and chain):
  - no SELL fills, MERGE, SPLIT or CONVERSION;
  - REDEEM after every window;
  - TAKER_REBATE daily, equal to half the previous day's taker fees;
  - MAKER_REBATE daily.

## 4. Target conditions

| condition | status |
|---|---|
| scope | met (100% of fills and \|PnL\|) |
| presence or selection | **not met**: gain +0.011 over MSB (+0.048 over the RE's own pure baseline); selection gain +0.018 |
| side | not applicable (XM 19.9% one-sided); would be met (0.819) |
| price | met under the proviso (trivial touch anchor at the match, 95.3%) |
| outcome | **not met**: 0.4245 / 0.4114 |
| significance | the nulls reject (p <= 0.0005), but the gain >= 0.05 is rejected |
| replication | **not met**: XM presence (second half 0.811, negative gain) and every wallet's PnL correlation is below 0.47 |

## 5. Why it works, and the deploy-now statement

**Why it works.** The operator is a latency arbitrageur of stale Polymarket asks inside the 150-ms taker hold.
- It reads the Binance spot book next to Polymarket's London engine and lifts the outcome the spot microprice is moving toward. On the lot that side is right for 82% of taker orders, against 54% for any market-only rule.
- It buys both outcomes of 98% of windows. 88.6% of its shares end paired, at a share-weighted pair cost of 0.9795, which locks $26.5k gross on the lot.
- After $32.3k of taker fees its trading PnL is +$13.1k (+0.92% of $1.42M). The next-day 50% taker rebate (+$16.2k) more than doubles it.
- Its taker fills earn about zero after fees (+0.03 c a share). Its maker fills, mostly lost races resting at the old ask (26% of USDC), earn +1.66 c a share.
- Who loses: the makers whose asks still stand when the hold ends, and Polymarket's rebate pool.

**The deploy-now statement is not supported.**
- The deployable rule loses before rebates on the lot (-0.98%, or -2.39% with block-time slack), including on the newest days (10-27 -3.2%, 10-29 +1.1%, neither significant).
- The wallets' own edge persists (assess_persistence as of 11-01):
  - GF and DS: recent 30 days p < 1e-4, with no decline;
  - XM: recent p = 0.0017, but its last 15 days declined (p = 0.0018).
- The conditions behind that edge held on the lot: the 150-ms hold, the 50% taker rebate paid daily, and the BTC 5m listings.
- That edge is the operator's colocation, queue position and Obsidian rebate tier, which a normal user does not have.

## 6. Diagnosis (case detail from the earlier half only: 10-23 and 10-25)

1. **Timing / presence: the margin is co-arrival.**
   - Against the capture-aware market baseline the block-second score gains only +0.014. For XM it is below the baseline (-0.012).
   - The margin sits in minutes 0-1 of the window (0.790 vs 0.753 and 0.796 vs 0.769) and vanishes from minute 3 (0.913 vs 0.906, then 0.980 vs 0.983).
   - Maker-only cells are 24.5% of positive cells. On them the frozen score is below the baseline (0.818 vs 0.825), and recall at 0.30 is 44%, against 69% on taker cells. The rule has no model of resting or lost-race orders.
   - It is strongest against the baseline in hour 23, where the capture (and so the baseline's millisecond prints) is missing: 0.873 vs 0.836.
   - The within-window AUC has a median of 0.861 and is lower in busier windows (rho -0.59 against the number of positives).
   - This suggests measuring timing at the decision clock against a book-aware baseline cut at the bot's own view. The block clock reveals the operator mostly through others' co-arrivals.
2. **Side: errors are late-window, low-signal inventory decisions.**
   - Accuracy falls from 0.877 in minute 0 to 0.857, 0.834, 0.756 and 0.662 in minute 4.
   - Late in the window the spot microprice moved more than 0.05 bp in the 250-ms window for only 5% / 4% of orders, and 19% / 33% of orders are low-confidence (|p - 0.5| < 0.1, accuracy 0.533).
   - Full 30-share fills are at 0.787 and large (>= 100) orders at 0.773, against 0.86-0.88 for partial fills. XM's 30-share fills are at 0.751.
   - When the cluster's net inventory is large the errors buy the short leg: 54% of errors at |net| > 300 shares and 72% at > 1,000. This is the pairing stream, not a spot trigger.
   - There is no Globex effect (0.820 open vs 0.823 closed) and no favourite / underdog effect (0.817 vs 0.825).
   - This suggests a separate inventory-driven side regime for late, low-signal decisions.
3. **Outcome: the per-window lean is a coin the tracker cannot see, and the wallets diverge.**
   - Correlation 0.445 / 0.456, with signs agreeing in 66% of windows. In the top-decile |PnL| windows, which carry 33% of |PnL|, signs agree in 78%.
   - The wallets' PnL is their net position times the outcome (r 0.894), and the net's sign matches the outcome in 51% of windows.
   - The correlation by hour ranges from 0.09 (hours 12 and 23, the capture gap) to 0.75.
   - Per wallet: DS 0.45, GF 0.29, XM 0.12. The wallets' window PnLs barely co-move (GF-XM 0.22, XM-DS 0.10), so one pooled target cannot carry XM.
   - This points again to the per-wallet allocation and the large-class lean.
4. **Price.** XM's limits are 2 c or more above the touch in 19% of its taker orders, so the touch rule reaches only 80.4% for XM. A size-dependent pay-up would fix most of this (touch + 1 tick is 91% for XM).

Later half (aggregates only): presence 0.8627 vs MSB 0.8558; side 0.8176 (XM 0.7717); price 0.953; PnL correlation 0.402 / 0.367; rule -0.91% before rebates.

## 7. Release

After this report, lot h1 is released to the reverse engineer with `sealed.py btc5m-bot --release h1`. On the open access question (X178), one view: in a capture day file that straddles development and sealed blocks, only row groups whose time statistics lie entirely in development blocks may be read.

Evidence (results/):
- exam_r1.json and exam.json;
- exam_r1_step0, _presence, _selection, _side, _price, _pnl, _econ, _activity, _persistence, _truncation, _trunc_dc, _evaluate_agg, _diagnosis, _metrics_bundle.

Scripts are in exam/. Per-chunk evaluate() outputs and intermediates are in .cache/exam/btc5m-bot/chunks/.
