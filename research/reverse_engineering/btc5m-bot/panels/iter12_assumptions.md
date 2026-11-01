# Panel, iteration 12: assumption breaker

Lens: what the investigation takes for granted that may be false. This round tests the load-bearing claims of the
iteration-12 account that decide the two failing exam conditions (5 and 7):

- "one operator, three nearly independent leans" (finding 3), and so "condition 7 is out of reach for XM";
- "the net follows the current minute's move and is bought back later" as the whole inventory path (finding 4);
- "the remaining gap is the window-net prediction (r 0.48)", with progress at ~0.968;
- "the wallets are refractory slots of one operator-level state" (findings 10, 16), carried over to the inventory path;
- "the fast crowd shares the selection" (finding 14), with its open caveat that the crowd may be reacting to the operator.

## Data and checks

Development data only: pre-H BUILD / VALIDATE (`fills.parquet`, `orders.parquet`, `b1_orders_sample.parquet`,
`windows.parquet`, `binance_1s.parquet`, `cells/`, `it12/nf12b_val.parquet`, all windows starting before H) and the 10-31
14:55-17:55 part of the 12-18 development block (`it11/onset_A|C.parquet`, `it9/cd9`, `it10/cdall10`, `it10/txms10`, and
`btc5m_clob_raw2` through `live_lab.recs`, which calls `iter_live` with `ALLOW_SEALED = False`). Nothing sealed was read,
listed or counted; `.cache/live/sealed/` was not opened. Calendar checked with `sealed.py btc5m-bot` at 2026-11-01 01:55 UTC:
no lots released, the current block is sealed.

Scripts (each under 300 MB and 2 minutes) are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p12a\`:

| script | what it checks |
|---|---|
| `twofac.py` | large-order vs small-order nets per wallet: within-wallet and cross-wallet correlations, public predictability, oracle ceilings |
| `invctl.py`, `role.py` | per-wallet minute flow against own vs other wallets' prior net (roles); per-wallet role model on the public path |
| `firstlg.py`, `opengap.py`, `xwin.py` | when the window's large lean starts, what predicts its side, cross-window persistence |
| `coatpre.py` | fast-crowd co-take restricted to orders signed before any operator match; per-wallet concentration and co-timing |
| `decomp.py`, `wnet.py`, `burstlean.py` | PnL = net term + price term; per-wallet net correlations by minute; large-order side per burst |

"Large" means an order (grouped by order hash) with at least 45 filled shares in the 30-share eras and at least 80 in the
60-share era (10-09..11). The results do not depend on that cut: with "> 30 shares" or ">= 90 shares" in the 30/100 era the
signs and sizes below hold.

## Critique

### 1. "Three nearly independent leans" is a cancellation, not independence

Finding 3 reads the near-zero correlations between the wallets' window nets (DS-GF 0.21, DS-XM 0.00, GF-XM 0.12) as three
independent leans. Split every wallet's net into its large-order net L and its small-order net S, and the picture reverses
(VALIDATE windows):

| | DS-GF | DS-XM | GF-XM |
|---|---|---|---|
| total net T | 0.209 | 0.001 | 0.120 |
| large-order net L | 0.456 | 0.346 | 0.468 |
| small-order net S | 0.350 | 0.245 | 0.512 |
| L, 30/100 era only (after 10-19 13:40) | 0.64 | 0.58 | 0.57 |
| L, BUILD 10-09..11 (60/100) | 0.60 | 0.59 | 0.49 |

Inside every wallet the two streams cancel: corr(L_w, S_w) is -0.26 (DS), -0.60 (GF) and -0.46 (XM) on VALIDATE, and -0.31 /
-0.69 / -0.57 in the 30/100 era. BUILD shows the same pattern (-0.14 / -0.45 / -0.28 and -0.21 / -0.42 / -0.36). Pooled,
corr(L, S) = -0.60. The cancellation comes from small **taker** orders: pooled corr(L, S_taker) = -0.58 against corr(L, S_maker)
= -0.32. It is an active counter-flow, not passive remainder fills.

So the operator runs two shared streams: a large-size lean that fans out to every wallet, and a small-size counter-flow that
buys the other side back. Each wallet carries a different mix (corr(T_w, L_w) is DS 0.61, GF 0.90, XM 0.83), so the totals
decorrelate. The wallets' leans are common. What differs is how much of the common hedge each wallet carries.

### 2. The frozen net predictor sees the lean poorly and the hedge not at all

The nf12b window sum, part of the primary tracker's target, predicts the pooled streams as follows:

| target | corr with the nf12b window sum |
|---|---|
| L_pool | 0.318 |
| S_pool | 0.049 |
| T_pool | 0.436 |

Write S = -0.366 L + e, with sd(L) 549, sd(S) 334, sd(e) 267 and sd(T) 439 shares. Then T = 0.635 L + e, and nf12b predicts e at
0.301. To first order, the T prediction is (349 rho_L + 267 rho_e) / 439. That gives 0.437 at today's values, which matches the
0.436 measured.

The model is trained on T, where the two streams cancel. A predictor needs either rho_e of about 0.45 (with rho_L unchanged) or
rho_L of about 0.45 (with rho_e unchanged) to reach a window-net r of about 0.53. That would put the PnL above 0.5.

The iteration-13 plan names "per-outcome gross-flow targets". The decomposition that matters is by **size stream**, not by
outcome.

### 3. The lean starts at the open, persists, and changes meaning through the window

Finding 4 describes the inventory path as "buy the current minute's move, buy back later". That holds for T. The L stream adds
a window-level state that a per-second model on T cannot represent:

- **The lean starts at the open.** The window's first large fill is at a median of 14 s (q10 5 s, q25 7 s, with a spike at
  block seconds 5-6). GF places 59% of these first large orders, DS 29% and XM 12%.
- **The first side persists.** The first large order's side equals sign(window netLarge) in 69% of windows, and sign(window
  net) in 62%. The large up-share of consecutive burst segments correlates at 0.31 (segments 0-1) and 0.50 (segments 1-2).
- **Public open state barely predicts that side.** Agreement with the first large order's side:
  - spot vs the TWAP strike at the open: 48%;
  - M2: 45% (it fades M2);
  - M1: 53%;
  - the previous outcome: 53%;
  - the outcome with the larger FV - ask gap at that second: 56%;
  - the first 1-s move of 1.5 bp or more before it: 60%, but only 14-26% of windows have one.
- **The meaning of large orders changes through the window** (30/100 era). sign(L in the segment) = outcome is 53-55% in
  0-60 s, then 51%, 46%, 42% and 47% in 60-120, 120-173, 173-240 and 240-300 s. Large fills drift toward the underdog: 46% of shares at
  prices below 0.5 in minute 0, 57% in minute 3.
- **The late small orders hedge.** Their PnL correlates negatively with the window PnL (-0.21 in 180-240 s and -0.20 in
  240-300 s). The large orders' PnL correlates +0.37 to +0.53 in every minute.

### 4. The progress figure omits condition 7, and no pooled rule can pass it for XM

The ~0.968 progress figure is the mean of five capped **pooled** conditions. Condition 7 asks every wallet with at least 300
fills to meet condition 5 within 0.03, i.e. about 0.47 each. Per-wallet PnL correlation against oracles of the **pooled**
streams times the outcome (upper bounds, because each pooled stream contains the wallet's own flow):

| oracle | DS | GF | XM | pooled PnL |
|---|---|---|---|---|
| T_pool x outcome (perfect pooled net) | 0.630 | 0.695 | 0.304 | 0.885 |
| L_pool x outcome (perfect pooled large lean) | 0.339 | 0.753 | 0.367 | 0.777 |
| the pooled PnL itself | 0.686 | 0.800 | 0.362 | 1 |

Even a perfect copy of the pooled operator leaves XM at 0.30-0.37: condition 7 for XM cannot be met by any pooled rule, however
good the pooled tracker gets. GF is better served by the L stream (0.75) than by the total (0.70), and DS by the total.

So the gap is not "0.024 on Pearson". It is the per-wallet dispatch of the two streams, plus the public predictability of L.

### 5. One state for the take, but roles for the inventory

Findings 10 and 16 make the operator one state with wallets as refractory slots. For the inventory path that is false. The test
is an OLS of each wallet's flow in minute k (k >= 1) on its own net before k, the other wallets' net before k, the minute's BTC
move and the earlier moves. Coefficients are in shares per 1 sd of the regressor, with window-clustered t in brackets:

| | own prior net | others' prior net | minute move | earlier moves |
|---|---|---|---|---|
| BUILD DS | -6.0 (-4.0) | -12.7 (-8.2) | +15.4 | -6.6 |
| BUILD GF | -3.9 (-3.3) | -3.4 (-2.8) | +14.0 | -4.0 |
| BUILD XM | -14.1 (-6.8) | -19.6 (-11.5) | +11.0 | -3.7 |
| VALIDATE DS | -4.3 (-2.8) | -15.5 (-9.9) | +15.4 | -10.7 |
| VALIDATE GF | **+3.2 (2.1)** | **+4.7 (3.2)** | +16.3 | -7.8 |
| VALIDATE XM | -2.5 (-3.2) | -1.9 (-2.9) | +4.7 | -0.7 |

- **DS hedges the other wallets' position**, not mainly its own.
- **GF pyramids on VALIDATE but paired back in BUILD.**
- **XM was the strongest pairer in BUILD and almost passive on VALIDATE.**
- **The large share of orders is a wallet property.** After the 10-19 13:40 restart it is DS 3%, GF 14-18% and XM 19-21%;
  before it, 21-34%, 33-43% and 34-43%.

The roles are version-specific. A per-wallet model fitted on BUILD learns the wrong sign for GF. This is a better explanation
than "XM's lean is unpredictable" for why the per-wallet net-flow models never beat the pooled one.

### 6. Finding 14's caveat is closed: the shared selection is not copying and not hidden legs

I restricted the fast crowd (non-operator taker BUYs with sign-to-match 180-400 ms, matched in [tau + 150, tau + 700)) to orders
**signed at or before tau + 150 ms**, i.e. before any operator match on that onset can exist:

- A: P(crowd | taken) 0.267 vs P(crowd | skipped) 0.115, log OR 1.03 (all crowd orders: 1.03);
- C: 0.243 vs 0.097, log OR 1.09 (all: 1.13).

The co-take is not a reaction to the operator's prints.

Concentration of the positive excess co-take over the 1,196 wallets (A / C):

| top wallets | share of the excess |
|---|---|
| 10 | 36% / 47% |
| 25 | 52% / 65% |
| 100 | 82% / 94% |

Eight of the top ten are the same wallets in both halves (0xdc3f4623, 0x5d634050, 0x26d76c9b, 0xeebde7a0, 0x62cadb35,
0xd581b376, 0x5b39cce1, 0x5a06acba). They are not operator legs:

- their matches fall a median 0.8-2.9 s from the nearest operator match on the same token, and only 11-40% within 100 ms
  (W5: 34 ms, 76%);
- they use signature types 0, 1 and 3.

About 25 independent fresh-signing bots carry most of the shared selection.

### 7. The next exam is historical

h1 is 10-23, 25, 27 and 29. Item 1 of "Next (iteration 13)" is live-only and cannot move h1's conditions 5 and 7. Items 2-3 can.
The iteration-10 information panel already said this; the plan still ranks the live block first.

## Checked and not supported (so nobody redoes them)

- **The outcome-independent price term as a lever for condition 5.** PnL = (Y - 1/2) net + [(U + D) / 2 - cost]. The price
  term is 26% of the PnL variance but correlates -0.39 with the net term and only 0.086 with the PnL. Spearman(PnL, net term)
  = 0.907, and adding c x gross lowers both Pearson and Spearman for every c >= 0.005. The Spearman gap (0.44 vs 0.476) is net
  prediction, not pairing edge.
- **BUILD / VALIDATE version mismatch as the cause of the window-net error.** The frozen nf12b window sum predicts the net
  better in the 30/100 era, which is absent from BUILD (0.468), than in the 30/50 era (0.403). Per day it ranges from 0.389
  (10-16) to 0.496 (10-21). Refitting on the latest version is not supported as the pooled fix (it may still matter per
  wallet, critique 5).
- **Per-wallet inventory control (each wallet pairs its own book).** No: DS reacts to the others' position about 3.6x more
  than to its own (critique 5).
- **Per-wallet role models on the public predicted path** (minute flow on the predicted pooled flow and its prior sum, fit on one
  VALIDATE half, scored on the other): DS 0.391 / 0.341 vs pooled-prediction 0.399 / 0.338; GF 0.370 / 0.266 vs 0.365 / 0.261;
  XM 0.068 / 0.102 vs 0.069 / 0.100. The roles enter through the realized positions (own state), not through a public
  reweighting.
- **An order-rate cap per wallet as the 30-60-s state** (API rate limit). Sliding-window counts of filled orders taper smoothly,
  with no pile-up: DS max 25 / 10 s and 87 / 60 s, GF 20 / 63, XM 16 / 32.
- **Large orders pre-committed to one outcome per burst.** In segments with at least 2 large and 2 small orders, the large
  majority share is 0.84 against 0.77 for draws from the segment's small-order side mix, and 53% of segments have large orders
  on one side only. A weak lean concentration, not a one-sided pre-signed large ladder. corr(large up-share, small up-share) is
  -0.37, the same counter-flow as critique 1.
- **Cross-window carry of the lean.** Lag-1 autocorrelation of netLarge is 0.124; it correlates 0.123 with the previous outcome
  and 0.10 with the 15-min move. The first two are already features of nf12.

## Proposals (ranked by the chance of closing the gap)

### 1. Two-stream exposure target: a large-order lean L and a small-order counter-flow S (new decomposition; strong form of X110 / X82 / X84)

**Hypothesis.** The operator's window net is the sum of two coupled operator-level streams:

- **L**: large-size orders fanned out to every wallet. The lean starts in the first seconds of the window, persists, and is
  pyramided.
- **S**: small-size taker orders. They buy the current tick and buy back the operator's L position.

A model trained on T = L + S sees the two cancel, so it learns each stream's public response poorly. Separate stream models
should predict T better:

- an L model with window-state features;
- an S model whose hedge term reads the replica's own L position (the rule's own state, which is legitimate);
- T̂ = L̂ + Ŝ.

The same models give GF, an L wallet, its own target.

**Evidence.** Critiques 1-3:

- cross-wallet corr of L 0.46-0.64, of S 0.25-0.51, against 0.00-0.21 for T;
- within-wallet corr(L, S) between -0.26 and -0.69, replicated in BUILD;
- the counter-flow is in the small taker orders;
- nf12b predicts L at 0.32 and the S residual at 0.30;
- pooled PnL against L_pool x outcome is 0.777;
- the first large order (median 14 s) fixes the lean's sign in 69% of windows;
- late large orders are anti-informative (42% in 173-240 s).

**Test** (pre-H data, BUILD-fit, VALIDATE-scored; pre-register before any VALIDATE score):

1. Stream labels from fills grouped by order hash: large = filled size above the day's small size (>= 45 in the 30-share
   eras, >= 80 in the 60-share era). Check the labels against the calldata sizes of the 11 sampled hours.
2. Per-second L model: nf12b's spot-only features plus PIT window-state features:
   - the sign and time of the first 1-s move of k bp or more after the open, and counts of such moves toward each outcome so
     far (k from {1, 1.5, 2, 3}, fixed on BUILD);
   - the since-open move, M1, M2 and the previous outcome;
   - rel, interacted with the outcome's price level (the early-momentum / late-underdog change).
3. Per-second S model: the same features plus the operator's L position up to s - 1 (own state). Fit it with the true L
   position on BUILD and score it with the replica's own L position. Report it with and without the own-state term.
4. Score the VALIDATE window L, S and T̂ = L̂ + Ŝ against nf12b (L 0.318, S 0.049, T 0.436) and the frozen average (T
   0.477). Then a pre-registered two-stream tracker (same TRK constants, target L̂ + Ŝ): pooled Pearson / Spearman with the
   2-h block CI and halves.
5. Per wallet: GF and XM against an L-stream tracker, DS against the T tracker, with mixes fixed on BUILD.

**Data.** `fills.parquet` (BUILD and VALIDATE), the calldata sample sizes, `binance_1s` and cells, the frozen nf12b / it4b
features.

**Signature if true.**

- The window T̂ reaches r >= 0.52 (or the L̂ r >= 0.45).
- The two-stream tracker reaches >= 0.50 in both Pearson and Spearman, with the block CI lower bound above the frozen
  tracker's 0.476.
- GF from the L tracker reaches >= 0.45 (its oracle is 0.753).

**Signature if false.** L̂ stays at 0.35 or less and the S model adds nothing beyond its hedge term. The lean's initiation
input is then not visible at the block clock (go to proposal 4), and the account of condition 5 reads: the public share of
the window net is bounded by the public share of L.

### 2. Condition 7 is a dispatch problem with version-specific roles: decode which wallet carries which stream, and publish per-wallet ceilings (strong form of X67 / X106 / X14; new: the role table and the oracle ceilings)

**Hypothesis.** The wallets are not interchangeable slots for the inventory path. Per version, a dispatcher gives each wallet
a role:

- a lean carrier: GF on VALIDATE, and the first large order of the window;
- a hedger of the other wallets' position: DS;
- a late or thin leg: XM.

A wallet's net is its dispatch share of the two shared streams. Per-wallet PnL is reproducible only through the stream it
carries and its share, and the roles flip at restarts (GF pairs in BUILD and pyramids on VALIDATE).

**Evidence.**

- Critique 5's role table.
- Large shares by wallet: DS 3%, GF 14-18%, XM 19-21% after 10-19 13:40.
- GF places 59% of first large orders.
- Pooled-oracle ceilings (critique 4): XM 0.30-0.37 under any pooled rule; GF 0.75 from L; DS 0.63 from T.
- Out-of-half fits of each wallet's total on the other wallets' (L, S): GF 0.33-0.41, XM 0.16-0.28, DS 0.04-0.08. DS's total
  hedges the others' L, so it is not a function of their streams.

**Test.**

1. **Role table per version**: BUILD 60/100 (10-09..11), 30/50 (10-12..16 and 10-16..19 13:40), 30/100 (10-19 13:40..23),
   and the 10-31 live block. Run critique 5's minute regression per wallet and per stream (own vs others' prior L and S,
   minute-move controls, window-clustered t). Do the coefficients change at the restarts (10-12, 10-14, 10-17, 10-19 13:40)?
2. **Dispatch model on decisions**: calldata sample hours, the 2,155 live decisions of 10-31, and W4 / W5 fills. Fit P(wallet
   | stream, side relative to the operator's net, leg rank inside the fan-out event, burst, rel, tick strength) and report the
   accuracy against the base rate. Is large-leg assignment deterministic (first large -> GF; third leg -> XM)?
3. **Attainability ledger per wallet.** Per-wallet PnL ceilings under:
   - (i) the pooled T oracle;
   - (ii) the pooled L + S oracle with BUILD-fitted per-wallet mixes;
   - (iii) a stream x dispatch-share oracle;
   - (iv) W4 + W5's window nets (from chain) as an independent thinned copy of the operator streams, i.e. a test-retest
     estimate of the common lean that needs no simulation assumptions.
4. If the roles are stable within a version, pre-register per-wallet trackers. Fit the stream mixes on the first half of the
   30/100 era and score the second half. Freeze the latest-version mixes for h1.

**Data.** `fills.parquet`, `orders.parquet`, `b1_orders_sample` / calldata, `it11/large_dec`, W4 / W5 OrderFilled logs for
VALIDATE (topic2 = 0xd844... and 0x03b4...).

**Signature if true.**

- Role coefficients are stable within versions and change at restarts.
- Dispatch is predictable (wallet assignment >= 70% against a base of ~55%).
- On the held-out half, DS reaches >= 0.47 and GF >= 0.45.
- For XM, ceiling (iii) with public stream predictions stays below 0.47. That is a measured wall component for condition 7,
  with its cause named (XM's dispatch share).

**Signature if false.** Roles drift within a version and dispatch is at the base rate. Per-wallet replication is then bounded
by the pooled-oracle ceilings times the public stream r, and that bound belongs in FINAL_RULE.md in place of "XM's lean is
unpredictable".

### 3. The shared input lives in ~25 independent fresh-signing bots: use their signing ms as exact decision clocks (strong form of X101 step 3 and X87; it rests on critique 6)

**Hypothesis.** The operator and a small set of independent fast bots act on the same input, and they do not copy each other.
The operator's orders are pre-signed, so its decision time is only inferred (arrival - 180 ms). These bots sign at the
decision, so their `sign_ms` is an exact decision clock, available for many more onsets.

A feed that time-locks these bots is the candidate input for the operator's 90% unlocked decisions (X111). If nothing locks
them either, the shared driver is a slow market-wide state. In that case, test whether the operator's "30-60-s own-decision
state" is that market-wide state, visible in their activity, rather than own state.

**Evidence.** Critique 6:

- the co-take survives restriction to orders signed before any operator match (log OR 1.03 / 1.09);
- the top 25 wallets hold 52-65% of the excess, and 8 of the top 10 are the same in both halves;
- their co-timing and signature types exclude operator legs;
- finding 14: the recorded design explains only 14-21% of the co-take.

**Test.**

1. Fix the co-taker set on A (top 25 by excess co-take) and check its overlap and excess on C.
2. For all their orders (BTC 5m, and ETH / SOL 5m or BTC 15m if they trade them), build decision-locked kernels at 5-ms
   resolution around `sign_ms` for every recorded series, with time-shift placebos:
   - Binance USD-M / spot, Coinbase, Bybit, OKX, Hyperliquid, Deribit;
   - each outcome's Polymarket book events;
   - RTDS;
   - on 11-01, rec_eu11 (Bitstamp, Kraken, Coinbase level2) and rec_pb10 (PolyBolt).
3. Fit a take selector on their takes on A, transfer it to the operator's onsets on C (and the reverse), and report the AUC
   gain over FULL and the share of the co-take log OR it explains.
4. **Market-wide state.** Add the co-takers' own decision kernel (30-60-s decay, from their public prints) next to the
   operator's own-decision kernel in hawkes12's design. Does it replace the own kernel out of sample?

**Data.** `it9/cd9`, `it10/cdall10`, `it10/txms10`, `it11/onset_A|C`, the 10-31 venue recordings, and the 11-01 06-12
recordings.

**Signature if true.**

- A feed shows a peak of at least 3x the placebo within 20 ms or less for the co-takers.
- Transferred, it raises the operator's onset AUC by at least +0.03 in both directions and explains at least 50% of the
  co-take log OR.
- Or (step 4): the co-takers' kernel matches the own kernel's held-out log loss. The 30-60-s state is then public market
  activity, not own state, which changes the selection account and the co-occurrence account of the presence gain.

**Signature if false.** The co-takers are as unlocked as the operator, and their kernel adds nothing beyond the own kernel. The
shared selection is then a state both sample without a clock, and the wall account must say so with these numbers.

### 4. The window open is its own decision type: the opening snipe seeds the lean (new; the historical and live analog of proposal 1's L initiation)

**Hypothesis.** The first decisions of each window are a distinct decision type: block seconds 3-6, decided about 1-4 s after
the open with orders signed at -89.5 s. They react to the open itself: the strike is fixed, and the book reprices from about
0.5 toward the exact-strike value. Their side sets the window's large lean, which is then pyramided and hedged.

The pooled onset and kernel analyses (X41, X78, X111) never separate these decisions from the rest, and the opening book is
where makers are stalest relative to the strike.

**Evidence.**

- First fills of the window pile up at block seconds 5-6 (726 of 1,904 windows' first fill at second 5).
- The first large order comes a median 14 s after the open, with a spike at seconds 5-6.
- The large share of orders is higher in seconds 1-13 (0.16-0.26, mean 0.20) than in 20-60 s (0.157).
- The first large order's side fixes netLarge's sign in 69% of windows.
- At the block clock, the open-state features give only 45-56%, so the opening input is finer than the block clock, or it
  is the book.

**Test.**

1. **Live** (10-31 development blocks now; 11-01 06-12 when it exists): for every window, list the operator's decisions in
   [0, 15 s), with side and size. Compare them with:
   - the exact-strike FV (Gamma priceToBeat, spot from the recorded venues) against o's recorded opening asks;
   - the first venue ticks after the open;
   - the time the strike became visible in the recorded feeds (first book update after the open, RTDS).

   Report their side accuracy and P(large) against the same rule on decisions after 30 s, and the decision-locked kernel to
   the first opening book event.
2. **Historical** (block clock): on BUILD, fit a side model for each window's first operator fills, using the exact
   priceToBeat, Binance spot at the open, the first tape prints of both outcomes and the open's ask sum. Score it on VALIDATE,
   and also against sign(window netLarge).

**Data.** `btc5m_clob_raw2` / `btc5m_venues2` (10-31), `ptb.parquet`, tapes for BUILD / VALIDATE, `fills.parquet`.

**Signature if true.**

- Opening decisions follow an opening value gap at >= 75% (vs 56% at the block clock now), with P(large) at least 2x the
  later rate.
- At the block clock, an opening-side feature predicts sign(netLarge) at >= 60% on VALIDATE and lifts the L stream of
  proposal 1.

**Signature if false.** Opening decisions follow the same tick vote as the rest. The L lean is then seeded by the first strong
tick at ms resolution, which the block clock cannot see, and proposal 1's L stream has a measured public bound.
