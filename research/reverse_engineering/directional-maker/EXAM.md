# directional-maker: independent examination, round 2 (lot f1)

Examiner run on 2026-11-01 between 13:50 and 15:30 UTC on the shared Windows laptop. The wallets are mo-money `0x32ed2e54...`, almach
`0x3725d52f...` and bosona `0xc2ad03f7...`, pooled as one operator. The rule under test is **R8c**, frozen in `code/final_rule.py`
at iterations 17-18, with its models `code/presence3_*.txt`, `presence15_*.txt` and `selection2_*.txt`. I did not edit any file
in `code/`. Every number below comes from my own runs on the lot. I took none from NOTES.md, FINAL_RULE.md or state.json; those
appear only as "VALIDATE (RE)" for comparison.

## Verdict

| criterion | result | reason in one line |
| --- | --- | --- |
| (6) match | **fail** | target not met. The rule loses to market activity alone on presence (0.597 vs 0.632) and on selection (0.675 vs 0.687). The selection rotation null fails (p = 0.987 within windows). |
| (7) backtest | **fail** | strict fills, 2 s latency, slack 2, no rebates: -14.5% on $114k, t = -3.14, p(profit) = 0.999. It loses in both halves and in every sensitivity. |
| (8) replicable | **fail** | at newcomer latency and queue position the executable rule gets only trade-throughs. It loses 15-19%, and more at larger size. |
| (9) persists | **fail** | the deploy-now statement is not supported. The rule loses significantly on the newest half (-16.5%). The wallets' own edge persists, but the rule does not capture it. |

**High-accuracy target: not met** (scope is met; presence/selection, side, outcome and replication are not).

## 0. Sample and sufficiency (listing metadata only, before any fill was read)

`exam/r2_step0_listing.py` and `results/exam_r2_step0.json`. Lot f1 is 18 sealed hours: 10-31 06:00-12:00 UTC and 10-31 18:00
to 11-01 06:00 UTC, a Saturday and a Sunday night.

- **BTC 5m:** 203 listed windows. Gamma listed none of the 13 scheduled windows from 11-01 04:55 to 05:55 (the US DST
  fall-back hour).
- **BTC 15m:** 67 listed windows; the 5 scheduled windows from 04:45 are not listed.
- **Other crypto Up/Down units:** 1,753 in the same intervals, used for scope.
- **Fee rate:** 0.07 on every BTC 5m window.

**Half split.** The cut is the median listed BTC 5m start, **10-31 20:25 UTC**:
- early half: 06:00-11:55 and 18:00-20:20, 101 windows;
- late half: 20:25 to 04:50, 102 windows.

**Sample size and power.**
- The lot has 12,180 presence bins in 9 two-hour blocks.
- After the fills were read: 807 positive bins, 3,184 BTC 5m maker BUY fills, 176 BTC 5m windows with cluster fills, and 3,028
  sampled selection prints that carry a cluster fill.
- Precision of each metric against its bar:

  | metric | standard error | bar vs observed |
  | --- | --- | --- |
  | presence AUC | about 0.01 | the 0.85 bar is 25 standard errors above the observed value |
  | side accuracy | about 0.008 | 0.80 vs 0.70 is 12 standard errors |
  | per-window correlation (176 windows) | about 0.07 | |

- With 9 two-hour blocks, a block bootstrap can resolve p of about 1/2001.
- The lot has enough data to reject every failing threshold. It has too few blocks to estimate a small gain precisely: the
  presence gain's 95% interval is ±0.02.
- The exam was not deferred.

## 1. Leakage audit

**Constants.** Every parameter of the rule is a literal:
- `final_rule.py`: model names, `THETA_SEL`, `PRICE_OFFSET = 0.01`, `PRE`, `SEL_NEG_FRAC`, `CL_DELAY_MS = 1432`;
- `side_sm.py`: `DECIDED = 0.4`, `SIGMA_K = 1.4`, `CL_STAMP_LAG = 4`, the NYSE-open flag;
- `r5.py`: the logistic coefficients;
- `inblock_price.py`: `OFFSET`.

`evaluate()` fits nothing.

I refit the presence models on the rule's BUILD data (`train4.load`, starts 10-09 to 10-26). They reproduce
`presence3_rule.txt`, `presence3_own.txt` and `presence3_activity.txt` exactly on the lot panel: the maximum prediction
difference is 0.0 (`results/exam_r2_refit_check.json`).

**Sealed data in development code** (code read; timestamp literals in `code*/` checked against the calendar; 89 parquet files
in `.cache/re/directional-maker/` scanned for units that start in the lot):

- No file in the RE's cache holds a unit that starts in the lot. I found no raw Gamma record of a lot market. No code path
  reads `.cache/live/sealed/` unless the examiner sets `ALLOW_SEALED`; the recorders only measure the folder's size.
- Minor boundary reads:
  - Iteration 9 fetched Binance 1-s spot, ETH, SOL and Deribit DVOL for 10-31 10:00-18:00
    (`it9/spot1s_*_1793440800_1793469600`). That includes 2 h of the sealed 06-12 block, loaded as a sigma lookback for the
    12-18 development block. The scripts that read it score only stamps from 12:00 on.
  - `cl/cl_eval_cache.parquet` holds 3 Chainlink stamps on block edges (11:59:47, 11:59:57 and 18:00:00), which are lookbacks
    of development windows.
  - None of this can carry information about the lot's fills or decisions. I record it as a procedural note, not a leak.
- **Procedural breach of the other-strategies rule.** `code/fetch_local.py` reads `.cache/re/btc5m-bot/tapes/` ("read-only
  reuse of another agent's identical data-api pulls"). Its windows and rows are clamped to before H, so the data is
  development data for everyone, and the directory no longer exists. No sealed content can have come through it, but the
  brief forbids the read.
- The final rule's live readers keep a record only if both its receive time and its server stamp lie in a development block.
  The `tools/live.iter_live` readers in the reported blocks rely on filing by receive time, so a laptop clock that drifts by up
  to about 1 s can misfile records at block edges. These blocks are reported, not counted.

**Point in time** (`exam/r2_trunc.py`, `exam/r2_trunc_rest.py`, `results/exam_r2_truncation.json`):

| decision input | sample | truncated after t | corrupted after t | positive control (one second earlier) |
| --- | --- | --- | --- | --- |
| presence features and the three models | 29 windows × 30 bins, drawn from the listing (seed 20261101) | 0 mismatches | 0 | 756 feature / 670 prediction mismatches |
| R8c side (prints ≤ b-3, spot < b-2, Chainlink ≤ b-4) | 300 fills | 0 | 0 | 16 |
| price, block clock | 300 fills | 0 | 0 | 79 |
| selection print features (dq_last, fair_p) | 300 prints | 0 | 0 | |

The side rule leaves room for block-time slack: prints stamped up to b-3, Chainlink up to b-4 and spot up to b-3, for a fill
stamped b.

The tape is cleaned of the wallets' own prints: 3,110 rows in cluster transactions, plus 77 cluster taker rows. There is no
ESPN input. priceToBeat is used only from the window start.

**R7 price clock caveat.** The R7 price anchors on the last trade before the fill, either on the server match clock or in the
block's execution order. Under the brief's convention a print counts as published at its block timestamp, so a trade in the
fill's own block is not "before" the fill. No clock can say whether the anchor trade came before the order was posted, because
the cluster's orders carry no signing time. The block-clock version is the point-in-time-safe one, and I report it beside R7.

**Labels.** I fetched the activity independently (`exam/r2_scope.py`), and my labels match the rule's on 100% of bins. In a
seeded sample of 120 BTC 5m BUY trades, Polygon receipts (V2 `OrderFilled`) agree with the tape-inferred maker/taker role in
120 of 120 cases and with the shares in 119 of 120 (`results/exam_r2_onchain.json`).

**Mechanical changes.** None to any file. My driver `exam/r2_run_evaluate.py` sets:
- `final_rule.ALLOW_SEALED = True`;
- `POLYREA_CACHE_DIR` to the exam cache;
- `cl_source.CLDIR` and `r9_nonbtc.CACHE` to `.cache/exam/directional-maker/`, so the endpoint values and klines of the sealed
  lot are not written into the RE's cache before the release.

It also wraps `build_panel`, `Spot` and `sel2.day_prints` to save their outputs unchanged. No patch was needed, so there is no
`exam_r2_patch.diff`.

**Leakage check: passed**, with the procedural notes above.

## 2. The frozen evaluate() on the lot

`evaluate(1793426400, 1793512800, intervals=f1)` ran unchanged in 2,762 s (`results/exam_r2_evaluate.json`). Its own numbers
equal my independent recomputation wherever they overlap:

| metric | evaluate() | mine |
| --- | --- | --- |
| BTC 5m presence | 0.5973 | 0.5973 |
| activity baseline | 0.6320 | 0.6320 |
| R8c side | 0.6991 | 0.6991 |
| block-clock price | 0.750 | 0.750 |
| match-clock price | 0.882 | 0.882 |
| selection AUC | 0.6750 | 0.6750 |

The `scope` field of evaluate() counts trades by timestamp, including the development block 12-18, so it gives 0.52. Its
`r9_nonbtc_module` scope is unit-based and gives 0.844, the same as my own count.

## 3. Lot metrics (my code unless noted; target thresholds in brackets)

| metric | lot pooled | early / late half | per wallet (bosona / almach / mo-money) | VALIDATE (RE) |
| --- | --- | --- | --- | --- |
| scope: share of trades / abs PnL in BTC 5m+15m [0.80 / 0.80] | **0.844 / 0.914** | 0.843 / 0.844; 0.901 / 0.929 | 0.891 / **0.776** / 0.807 trades; 0.92 / 0.91 / 0.91 abs PnL | 0.868 / 0.891 |
| presence AUC, BTC 5m, no own state [0.85] | **0.597** | 0.562 / 0.625 | 0.603 / 0.599 / 0.590 | 0.716 |
| RE activity baseline / examiner baseline (ACT + extended activity, same LightGBM, PARAMS and BUILD) / examiner ACT + clock | 0.632 / 0.630 / 0.609 | 0.614 / 0.647 (RE) | 0.640 / 0.633 / 0.628 | 0.684 |
| gain over the stronger baseline [+0.05, lower 95% bound > 0] | **-0.035**, 2-h block bootstrap [-0.049, -0.009], p(gain ≤ 0) = 0.9985 | -0.053 / -0.022 | -0.037 / -0.034 / -0.044 | +0.032 |
| presence with own inventory (reported, not counted) | 0.715 | 0.701 / 0.708 | | |
| presence BTC 15m / union 5m+15m (evaluate) | 0.785 vs 0.822 / 0.716 vs 0.738 | | | 0.812 / 0.788 |
| selection AUC (stratified global / within window) [0.80] | **0.675** (0.685 / 0.648) | 0.693 / 0.662 | 0.674 / 0.692 / 0.692 | 0.685 |
| recall / lift at THETA_SEL [50% / 3] | 49.2% / **2.01** | 51% / 2.17; 48% / 1.89 | | 29.5% / 2.87 |
| selection: RE activity / examiner activity (same class and BUILD days) | 0.685 / 0.687; gain -0.012 [-0.023, +0.002] | | | 0.651 |
| selection rotation null (2-h blocks, 2,000 draws) [p < 0.0025] | global p = 0.027, within-window p = **0.987** (z = -2.1) | | | |
| side applies? (windows ≥95% one outcome) | 45% of 176 windows: yes | | | |
| side per BTC 5m maker fill, R8c [0.80] | **0.699** | 0.709 / 0.693 | 0.697 / 0.685 / 0.717 | 0.701 |
| best market-only baseline (cheaper token) | 0.637; McNemar 327 vs 128, p = 2e-21 | 0.634 / 0.638 | 0.648 / 0.628 / 0.618 | 0.679 |
| best own-inventory-only baseline (side of the cluster's previous fill) / held outcome | 0.797 / 0.649 | 0.836 / 0.774 | 0.773 / 0.853 / 0.810 | 0.822 |
| side rotation null (reference path rotated in 2-h blocks, 2,000 draws) | null 0.639 (max 0.684), **p = 0.0005** | p 0.0005 / 0.0045 | | |
| side BTC 15m (evaluate) | 0.774 (cheaper 0.319, favourite 0.681) | | | 0.821 |
| price within a tick, R7 frozen clock (match where recorded, else in-block) [0.80] | **0.868** (union 5m+15m 0.856) | 0.864 / 0.871 | 0.888 / 0.843 / 0.842 (halves 0.80-0.89) | 0.807 |
| price, block clock (point-in-time-safe) | 0.750 | 0.774 / 0.736 | | 0.709 |
| price on the match clock (2,179 fills): rule / last print / touch / touch - tick | 0.882 / 0.838 / **0.971** / 0.940 | | | |
| price, independent in-block sample (150 fills, 06-12 block) | 0.86 (block clock 0.77) | | | |
| per-window PnL corr, executable R8c strict replay vs cluster maker PnL [0.5 / 0.5] | **0.365 / 0.248** (176 windows; permutation p 0.002 / 0.0025, 2,000 draws) | 0.466 / 0.172; 0.208 / 0.319 | 0.376 / 0.390 / 0.352 Pearson | 0.207 / 0.218 |
| RE's own executable variant (Binance posture) / BTC 15m | 0.328 / 0.111; 0.412 / 0.283 | | | |
| rule return, strict fills, L = 2 s, slack 2, 62 shares, no fees or rebates [p < 0.05] | **-14.5%** on $113.9k (t = -3.14, p(profit) 0.999; block bootstrap p(≤0) = 1.0, 95% [-23.4%, -6.6%]) | -12.9% / -16.5% | | |
| wallet's own BTC 5m maker BUY return, same windows | **+12.9%** (+$10,672 on $82,496; 9-block bootstrap p(≤0) = 0.105) | +$10,852 / -$179 | | |

**Executable rule** (`exam/r2_replay.py`, my implementation of the conventions of EXAM_r1 and `code11/replay.py`):
- at each second d from the open to 30 s before the end, the R8c side computed at d (decided → cheaper token, else the
  Chainlink posture, report stamped d-2);
- BUY 62 shares (the rule's off-session size) at the last clean print minus 0.01, live in (d+2, d+3];
- a print stamped T counts at T-2, and fills only when it trades through the bid; at most 62 per second.

Sensitivities:

| variant | return |
| --- | --- |
| latency 5 s | -18.6% |
| 500 shares | -16.3% |
| clean flow | -15.1% |
| the RE's own executable variant | -14.3% |
| BTC 15m | -4.2% (p(profit) 0.72) |

## 4. Target conditions and criteria

| condition | result | numbers |
| --- | --- | --- |
| 1 scope | met (pooled) | 0.844 of trades and 0.914 of abs PnL; both halves ≥ 0.84 / 0.90. almach has 0.776 of its trades in the universe (reported) |
| 2 presence or selection | **not met** | presence 0.597 < 0.85, with a gain of -0.035 [-0.049, -0.009]. Selection 0.675 < 0.80, recall 49% < 50%, lift 2.0 < 3, gain -0.012 |
| 3 side | **not met** | applies (45% of windows one-sided). 0.699 < 0.80; market-only 0.637, own-inventory-only 0.797 |
| 4 price | met on the rule's own clock, with flags | R7 0.868 (halves 0.864 / 0.871; every wallet and half ≥ 0.80). It *is* the trivial anchor "last print minus a tick", and the touch anchor scores 0.971. On the point-in-time-safe block clock it is 0.750 |
| 5 outcome | **not met** | 0.365 / 0.248 < 0.5 |
| 6 significance (one-sided α = 0.0025) | **not met** | presence gain p = 0.9985 and selection gain p = 0.952, both in the wrong direction. Selection rotation p = 0.987. Side rotation p = 0.0005 and correlation permutation p = 0.002 / 0.0025 are significant, but on metrics below their bars |
| 7 replication (halves; every wallet with ≥ 300 fills) | **not met** | no threshold of 2, 3 or 5 holds pooled. Price holds in both halves and for every wallet |

**target_met = false.**

**Components.**
- **selection: fail.** Below both activity baselines on prints and on presence windows. The rotation null fails.
- **timing: fail.** Presence is below market activity in both halves. The RE's event-time quote-presence block gains +0.001.
- **side: partial.** A real but modest signal: +0.062 over the cheaper token (rotation p 0.0005). It is far below 0.80 and
  below the own-history baseline.
- **price: partial.** It meets 0.80 only as the trivial last-print anchor on a fill-time clock, and the touch anchor beats it by
  9 points.
- **size: fail.** On this weekend lot, 83% of the early-half fills came from 500-share orders, against the rule's off-session
  62/250.
- **exit: partial.** The cluster made no sells. 119 merges and 927 redeems are consistent with hold-to-resolution and pairing.
  BTC 5m merges came a median 77 s before the end and the last fill a median 86 s before the end. Exit is not part of the counted
  rule.

**(6) match: fail.** target_met is false. The methodology's match test is the selection score against the rotation null; it
fails within windows (p = 0.987, z = -2.1), and its effect size sits at the floor (recall 49% at lift 2.0). The rule adds
nothing over market activity on presence and selection. The side and outcome associations are statistically real, but they
are components below their bars, not a methodology match.

**(7) backtest: fail.** -14.5% under strict fills at 2 s latency with slack 2 and no rebates, p(profit) = 0.999. It loses in
both halves and in every sensitivity. Rebates worth about 1% of notional could not close the gap.

**(8) replicable: fail.** Every input is public: the Binance and Chainlink RTDS feeds, the tape and the book. But a copy at
normal latency and newcomer queue position is filled only when the market trades through its bid, which makes it adversely
selected. It loses 15-19%, and more at 500 shares, so the $50k/month capacity question does not arise.

The cluster's own maker fills sit at the best bid 97% of the time on the match clock. That is queue position, which a newcomer
does not have.

**(9) persists: fail.** "This strategy is statistically significant to continue working if I deployed it now" is not supported:

- **The rule loses on the newest part of the lot.** The late half (10-31 20:25 to 11-01 04:50) returned -16.5%. Its presence
  (0.625) and selection (0.662) stay below their activity baselines.
- **The wallets' own record** (`polyrea.tools.assess_persistence`, as_of 11-01 00:00, days through 10-31, no one-off bonuses
  found):

  | wallet | last-30-day p | late 15-day decline p |
  | --- | --- | --- |
  | mo-money | 0.0065 | **0.044** (fails the methodology's late-decline condition) |
  | almach | 0.0078 | 0.110 |
  | bosona | 0.0023 | 0.111 |
  | cluster pooled | 0.0044 | 0.078 |

  The cluster made +$84k over the last 7 days. Its BTC 5m maker edge on the lot is +12.9%, but that is not significant over 9
  blocks (p = 0.105), and the late half was flat (-$179).
- **Conditions.** The fee rate is unchanged (0.07). Listings were interrupted at the DST hour, an operational event. These
  conditions favour the operator's queue position, not a public-data copy. The wallets' edge persists; the rule does not
  capture it.

## 5. Why it works (lot evidence)

**What the cluster does.** It is a top-of-book maker on the BTC Up/Down windows, and it only buys:
- on the lot it made 4,884 BUY trades and no sells;
- it holds to resolution or merges pairs;
- 97% of its match-clock maker fills are at the best bid.

**Who pays it.** The takers who cross into its bids:
- 80% of the taker volume in its fill transactions are buyers of the *other* outcome (complementary mints);
- 20% are sellers of the same token;
- 1,097 distinct takers; the top 10 make up 44%.

**Where the lot's profit came from.** BTC 5m maker fills earned +$10.7k:
- fills at 0.10-0.30: +$6.9k on $4.8k, a few large wins;
- fills at 0.5-0.9: +6-7%;
- fills at 0.9 and above: +3.3%;
- deep loser bids below 0.10: -$1.5k.

**What it is paid for.** Liquidity provision with priority at the touch: a quote refreshed on each public Chainlink report and
each Binance move, so that minting takers hit it first. It is not paid for a private signal. The rule's Chainlink posture
predicts the side only 6 points better than "cheaper token", and a strict-fill copy at 2 s latency loses 14.5%.

**Rebates.** Maker rebates add to the wallets' PnL and are excluded from the rule's backtest, as required.

**The deploy-now statement is not supported.** The public-data rule is significantly unprofitable on the lot, including its
newest half. The wallets' own profit relies on queue position and refresh speed that a normal user cannot replicate.

## 6. Diagnosis for the reverse engineer (first half only, case by case; second half aggregates only)

Early half: 101 BTC 5m windows (10-31 06:00-11:55 and 18:00-20:20 UTC) and 1,201 maker fills (`results/exam_r2_diagnosis.json`,
`results/exam_r2_diag_sizes.json`).

1. **Presence ranks windows backwards.**
   - The mean predicted presence per window ranks "window gets a fill" at AUC **0.26** (activity 0.33). The windows the model
     rates busiest are the ones the cluster skipped: 24% of the early windows had no fill, and only 62% of the 18:00-20:25
     windows were active.
   - Within active windows the rule is also below activity: 0.596 vs 0.637, and per window 0.633 vs 0.661.
   - Of the positive bins, 41% fall in the rule's bottom half. 59% of those misses sit at deep prices (last print < 0.10 or >
     0.90), against 15% of the hits, and their edge is about 0 (hits 0.063). **The deep-bid and decided-window fills are what
     the presence model misses.**
   - By hour, the rule beats activity at 06, 07, 11 and 18 UTC and loses at 08-10 and 20 UTC. At 19 UTC both are below 0.5.
   - The weekend clock is not the cause: setting `dow` to a weekday moves the early AUC only from 0.562 to 0.580.
2. **Side: the decided-window branch is two different decisions.**
   - All 108 decided-branch misses are **favourite buys at a median price of 0.98**, and 89% of them come in the last 2 minutes
     of the window (51 in the last 60 s). They carry $19.7k of notional, the largest dollar block of the early half, at
     +3.9%.
   - The decided-branch hits are deep loser bids: 342 fills, $691 notional, all lost.
   - So in decided windows the cluster bids on the loser early and buys the near-certain favourite late. R8c always says
     "cheaper".
   - The posture branch scores 0.68:

     | \|Chainlink fair - mid\| | accuracy |
     | --- | --- |
     | below 0.10 | 0.58-0.68 |
     | 0.10-0.20 | 0.82 |
     | above 0.20 | 0.65 |

   - By time in the window:

     | seconds | accuracy |
     | --- | --- |
     | 0-30 | 0.64 |
     | 30-120 | 0.74 |
     | 120-240 | 0.78 |
     | 240-300 | **0.34** |

   - When the posture is wrong, the cluster bought the cheaper token only 15% of the time (75% when it is right): **its
     posture misses are favourite buys.**
   - 67% of the misses repeat the cluster's previous fill side, so the misses come in runs. 28% of the windows have most of
     their fills wrong.
3. **Size: the 500 ladder ran all Saturday.**
   - 83% of the early-half maker fills come from 500-share orders (calldata), 86% in the 06-12 block. This is outside the
     weekday 12-21 UTC session, where the frozen schedule and the executable replay use 62/250; those sizes make up 1.7% of
     fills.
   - Side accuracy by order class: 500s 0.73, other sizes 0.63.
4. **Price.**
   - The block clock scores 0.78. Its misses are mostly 2-3 c below the anchor (resting rungs), plus ±0.10 tails at deep
     prices.
   - Deep fills score 0.91 within a tick and mid fills 0.69.
   - R7 scores 0.864: in-block for the 06-12 block, with 0.86 on my independent sample.
   - On the 18:00-20:25 match clock the touch (0.978) beats the rule (0.940): the fill is at the best bid, and "last print
     minus a tick" is a proxy for it.
5. **Outcome.**
   - Over 78 windows the per-window correlation is 0.466 Pearson and 0.172 Spearman, and the signs agree in 55%.
   - The cluster won while the replay lost in 23 windows (12 the other way).
   - The cluster's 10 best windows carry 135% of its early-half BTC 5m PnL (+$10.9k). A 62-share trade-through replay (-12.9%
     in this half) cannot reproduce that heavy tail.
6. **Selection.** The rule is below activity both on deep prints (0.666 vs 0.670) and on mid prints (0.752 vs 0.767).
7. **Scope.** The early half has 0.843 of trades and 0.901 of abs PnL in the universe (bosona 0.83, almach 0.83, mo-money
   0.87). The rest is BTC hourly and 4h, and small amounts in ETH and other coins.

**What these suggest** (no fix attempted):
- In decided windows, condition the side on time in the window: early deep loser bids, late favourite buys at 0.97-0.99.
- Do not key size or presence on the weekday session clock; the 500 ladder ran on a weekend morning.
- The window-level inversion says the cluster's module choice (which windows it skips) is not in the public inputs the model
  uses. It is the presence gap, not timing within a window.
- Small-edge posture fills stay near chance.
- The price "rule" should be stated as the touch (best bid).

**Second half, aggregate only.**

| metric | value |
| --- | --- |
| presence | 0.625 vs activity 0.647 |
| selection | 0.662 vs 0.679 |
| side | 0.693 (cheaper 0.638; rotation p 0.0045) |
| price R7 | 0.871 |
| outcome correlation | 0.208 / 0.319 |
| replay | -16.5% |
| wallet's BTC 5m maker PnL | -$179 |

In 15 of the lot's 49 qualifying 15-min slots, all after 21:45, bosona ran the main ladder alone.

## Files

- **Exam code** (`exam/`): `r2_common.py`, `r2_step0_listing.py`, `r2_scope.py`, `r2_run_evaluate.py`, `r2_baseline_fit.py`,
  `r2_metrics.py`, `r2_selection.py`, `r2_side_null.py`, `r2_replay.py`, `r2_r7_halves.py`, `r2_onchain.py`, `r2_trunc.py`,
  `r2_trunc_rest.py`, `r2_persist.py`, `r2_diagnosis.py`, `r2_assemble.py`.
- **Results** (`results/`): `exam_r2.json` (verdict and key metrics), `exam_r2_evaluate.json` (the frozen evaluate()), and
  `exam_r2_{step0, scope, metrics, selection, side_null, replay, price_r7, onchain, truncation, persistence, diagnosis,
  diag_sizes, refit_check, baseline_fit}.json`.
- **Cache:** the sealed data stays in `.cache/exam/directional-maker/`, including its own `http.sqlite`.
- **Notes for the maintainers:**
  - `tools/live.iter_live` stops with `zlib.error` on a corrupt gzip member: `dev/rtds` and `dev/clob_crypto` `20261031T12`.
    My readers skip such members.
  - The `scope` field of `evaluate()` is not unit-based.
- The lot was released after this exam (`sealed.py directional-maker --release f --until 1793512800`).
