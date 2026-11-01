# Panel, iteration 16: assumption breaker

Lens: what the iteration-16 account takes for granted that may be false. After iteration 16 three conditions still fail:

- condition 2, at the block clock against the capture-aware baseline (+0.024), and at the decision clock unless the book is cut at e;
- condition 5, where Spearman is 0.467 and Pearson 0.5065;
- condition 7: per wallet the PnL r with the pooled tracker is GF 0.39, DS 0.42, XM 0.04.

The account explains conditions 5 and 7 with two separate coins:

- a size coin with **per-wallet base rates** (DS ~4%, GF ~32%, XM ~34%) that repeats on the side of the realized large lean;
- a **carrier** that a size-blind priority list sets (DS > GF > W4 > XM > W5, 300-ms slot).

The replica that has to earn the PnL correlation is a **net-path tracker**. This round tests three things behind that account:

- that the size class belongs to the wallet;
- that routing does not depend on the size;
- that the per-window PnL is "net x outcome", so that tracking the net is enough.

## Data and checks

Development data only. `sealed.py btc5m-bot` at 11-01 08:53 UTC showed: released none, future examined until 10-31 00:00, and the
current block (06-12) is development. I read nothing sealed and did not open `.cache/live/sealed/`. Inputs:

- `.cache/re/btc5m-bot/fills.parquet` (VALIDATE 10-16..22);
- the session scratchpad `it16/size16_pred_cd.parquet` (46,569 operator taker orders of 10-21..22 with exact calldata size labels,
  `m`, `m0` and the frozen size predictions);
- `it16/cdfull_10-20..22.parquet`, `it16/hazbins16.npz` (the frozen knee-clock hazard on every 50-ms bin of 10-20..22) and
  `it16/tapes`;
- `it15/l2tok_*`;
- `it13/hf_dl/pm_trades_2026-10-21/22` (server-ms trades of the public capture).

Scripts are in
`C:\Users\Remote-BEAST\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p16a\`.
Each ran in under 300 MB and under 2 minutes.

| script | what it checks |
|---|---|
| `arm_size.py` | the 10-21 16:00 -> 10-22 13:00 dispatch phase as a randomized routing experiment: pooled and per-wallet large share by arm, and the first-leg carrier by size class |
| `route_size.py`, `event_size.py` | P(large) by carrier and visible occupancy; leg concordance inside events; first-leg carrier by class |
| `rank_size.py` | public burst intensity (the frozen hazard summed over the 300 ms before the order's knee bin) and public lean proxies as size inputs |
| `cap_size.py` | whether the large stream has a per-window cap |
| `ladder_size.py` | whether the size is fixed at signing time (both sizes in the same burst, cent and ms) |
| `pnl_rank.py`, `pnl_c_drivers.py`, `pnl_c_sib.py`, `pnl_c_wallet.py`, `pnl_c_sim.py`, `pnl_role.py` | the per-window PnL split into the directional part, the outcome-independent pair margin and the maker-role remainders, and what each would add to the tracker |
| `sel_print.py` | print-level selection on the decision clock as an alternative route to condition 2 |

## Critique

### 1. The size class belongs to the decision, not the wallet, and routing is keyed on it

The working account (FINAL_RULE size component; E3) gives each wallet its own large rate. Read as a mechanism, that predicts:

- if routing moves decisions from DS to GF, the pooled large share rises by Δshare x (p_GF - p_DS);
- each wallet keeps its own rate.

**The test.** The dispatch phase (10-21 16:00 -> 10-22 13:00 UTC) is a randomized experiment on routing: arm B = (start / 300)
mod 4 in {1, 2}, assigned by window index, so the Binance-driven decision stream has the same distribution in both arms.
On complete calldata labels (`arm_size.py`, 237 windows):

| | arm A | arm B |
|---|---|---|
| order shares | DS 0.670, GF 0.273, XM 0.057 | DS 0.432, GF 0.489, XM 0.079 |
| pooled P(large), all orders | 0.136 | 0.133 |
| GF P(large) | 0.318 | 0.138 |
| DS P(large) | 0.041 | 0.084 |
| XM P(large) | 0.39 | 0.36 |

- The B - A difference in pooled P(large) is -0.004 (window bootstrap [-0.014, +0.006]).
- If the size belonged to the wallet, arm B's routing at arm A's per-wallet rates would give **0.204**. That is rejected by a wide
  margin.

**First legs (m == m0) show the mechanism:**

| first legs, dispatch phase | small: DS / GF / XM | large: DS / GF / XM | first-leg large share |
|---|---|---|---|
| arm A | 0.839 / 0.135 / 0.026 | 0.236 / 0.564 / 0.200 | 0.090 |
| arm B | 0.472 / 0.486 / 0.042 | 0.314 / 0.468 / 0.218 | 0.096 |

- The experiment re-routed **small** decisions (DS to a near 50 / 50 split).
- **Large** decisions kept, roughly, their own list: GF first, then DS and XM.
- The first-leg large share did not move.

Outside the phase the same split holds:

- small first legs DS 0.80-0.82, GF 0.15-0.17, XM 0.03;
- large first legs DS 0.26-0.30, GF 0.52-0.55, XM 0.17-0.18 (`event_size.py`).

So the size class is drawn per decision (or per event) **before** routing, and the router uses a different wallet list for each
class. The per-wallet "base rates" are routing artefacts.

Consequences the account has not drawn:

- **Within-wallet size AUCs mix size with routing.** DS's "public" large class (AUC 0.77-0.84) consists of the large decisions that
  reached DS:
  - on the visible record, P(large | DS) is 0.035 with nobody busy and 0.14 / 0.19 / 0.22 at 1 / 2 / 3 operator legs in the
    previous 300 ms;
  - the public burst intensity alone (the frozen hazard summed over 300 ms) gives DS AUC 0.70, against GF 0.56 and XM 0.54
    (`rank_size.py`).

  A size model fitted per wallet partly learns the overflow, not the size decision.
- **Ladder16's 'public model 0.401' and 'per-wallet constant 0.351' used the TRUE carrier**, and the carrier leaks the class:
  P(GF | large first leg) 0.57 against P(GF | small first leg) 0.17. The replica-attainable size term is lower than those ladders
  say. The oracle labels in the condition-5 account need restating.
- **The size-blind dispatcher (0.778) and E6 ("size follows the dispatcher") have the direction backwards.** The class comes first.
  XM is the third wallet of the LARGE list: XM's share of large first legs is 0.17-0.22, against 0.03 of small. XM's 0.81
  correlation with large-only PnL (X82) is the same fact seen from the PnL side.
- **Condition 7 for GF and XM becomes the size problem.** Their legs are mostly the large stream, so a replica's GF / XM trackers are
  its own large stream routed through the large list. DS's tracker is the small stream plus large overflow.

Inside events the class is shared too:

- P(second leg large | first leg large) 0.636, against 0.285 after a small first leg (7,673 events of two or more legs, all on the
  same outcome);
- the common visible event is DS small followed by GF large (1,683 of 5,216 DS -> GF events).

So a second reading must be separated from "size-keyed lists" (R1). In R2, a large event is a small probe at the ask on the first
free small-list slot, followed by a large leg at ask + 1 c on the next slot. A GF-led large first leg would then be a probe that
lost its race without a trace. In arm B the large legs did shift by 0.08 toward DS, which fits R2 in part. Both readings agree on
the point that matters: the size is a decision-level variable.

### 2. The executable PnL rule replicates one of the operator's three PnL streams

The exit component says "per-window PnL = net x outcome", and the frozen rule (trk_a with mix14) buys only the deficit between a
target net and its own net. The wallet's per-window PnL (the condition-5 target, before rebates) has three parts.

**(i) The directional unpaired part D.**

**(ii) An outcome-independent pair margin C = paired shares x (1 - pair cost) - fees.**

| | sd C | sd D | C's share of W's variance |
|---|---|---|---|
| VALIDATE 10-16..22 | 75 | 188 | 0.137 |
| 10-20..22 | 77 | 212 | 0.115 |

- Per wallet on 10-20..22, C's share of variance is DS 0.127, GF 0.056, XM 0.085.
- corr(C, D) is about 0.01, so C is independent of the outcome bet.
- C is **common across the operator's wallets**, which per-window total PnL is not:

  | C across siblings (10-16..22) | DS-GF | DS-XM | GF-XM |
  |---|---|---|---|
  | C | 0.52 | 0.23 | 0.25 |
  | pair cost alone | 0.51 | 0.25 | 0.22 |

  The total PnL correlates only 0.20 between DS and GF (iteration 6).
- C is carried by the small orders: corr(C from small orders only, C) = 0.88. Its split-half reliability is 0.60.
- Crude public path features do not explain it (R² 0.04, `pnl_c_drivers.py`): the Up-price range, total variation, 0.5-crossings,
  crowd volume.

So C is a shared consequence of the decision stream, not a property of the price path. The tracker trades no pairing flow, so its C
is near zero by construction.

**(iii) The maker-role remainder fills (lost races and remainders resting as GTC bids at L).** On 10-20..22 (`pnl_role.py`):

| fills by role | share of fills | share of shares | mean PnL per window | share of W's variance | corr with W | corr of net with total net |
|---|---|---|---|---|---|---|
| maker | 34% | 19.5% | **+$8.08** | 0.165 | 0.605 | 0.578 |
| taker | 66% | 80.5% | **-$3.99** | | | |

Before rebates, the trading profit sits in the maker remainders. The tracker is taker-only and has no remainder stream (X133 is
still "not tested").

**What C alone is worth** (`pnl_c_sim.py`; directional part degraded to the frozen rule's Pearson on 10-20..22, 40 redraws):

| a replica's C_rep correlates ρ with the operator's C | Spearman gain | Pearson gain |
|---|---|---|
| ρ = 0.3 | +0.009 | |
| ρ = 0.5 | +0.024 | +0.026 |
| exact C (VALIDATE) | +0.063 | +0.071 |

The Spearman gap is 0.033. The maker stream is a second, larger lever (var share 0.165, corr 0.605 with W) that has never been
replicated.

### 3. Condition 2 hinges on the unit's forecast origin, not on physics

The investigation argues the cut at e from the bot's own view time. Under ordinary point-in-time rules no such argument is needed if
the unit is written as a forecast:

- origin e;
- every feature of every model at or before e;
- label = a first leg arriving in (e + 205, e + 255].

A baseline that sees the book at e + 50 then looks past the origin. If instead the examiner reads presence literally ("filled in
time bin b", features before b), the baseline sees the makers' cancel wave and the gain collapses (+0.008 / +0.023). This is a
definition the examiner has to rule on before the next claim. It is not something more decoding can fix.

I also checked whether print-level SELECTION on the decision clock escapes the problem. It does not (`sel_print.py`):

- 649,126 taker BUY matches of 10-21..22, one per tx, server ms; the operator is 6.7%;
- a market-only LightGBM (fill size, price, distance from 0.5, time in window, maker rows, co-arrivals at 20 / 100 / 500 ms), fit
  on 10-21 and scored on 10-22, reaches AUC 0.9275 (recall 0.906 at lift >= 3);
- adding the frozen hazard at the print's own knee bin gives 0.9442 (+0.017);
- the operator's prints are recognizable from their menu-shaped sizes and maker rows. The gain from Binance is small.

### 4. Smaller points

- **XM after W4 is not copy trading.** The median W4 -> XM gap is 45 ms, shorter than the 150-ms hold plus transit, so XM cannot be
  reacting to W4's visible match. Both legs come from one decision.
- **The lean is a monotone own-position feedback with no cap** (`cap_size.py`, GF + XM). P(large) by the realized large fill
  already on the order's side:

  | realized large fill on this side (shares) | <= -300 | -100..0 | 0 | 0..100 | > 1000 |
  |---|---|---|---|---|---|
  | P(large) | 0.050 | 0.226 | 0.337 | 0.392 | 0.506 |

  P(large) also falls through the window: 0.356 at 0-30 s, 0.19 at 240-300 s. Large orders per window: median 11, q99 34, max 43.
  No cap is visible. The free draws are the lean-initiating ones, early in the window.
- **Exam transfer.**
  - Every phase boundary found so far sits on a whole UTC hour: the size runs, the 10-19 01-13 h and 10-20 19 h size phases, and
    the 10-21 16 h -> 10-22 13 h dispatch phase. These are scheduled or manual configuration changes.
  - XM's ~10k fills a day on 10-31, against 1.6-3.1k on VALIDATE, says the routing changed again after VALIDATE.
  - A frozen rule that hard-codes per-wallet rates or one routing list carries that risk into h1 and its halves (condition 7).

## Checked and not supported (so nobody redoes them)

- **The size is not fixed at signing** (`ladder_size.py`, complete calldata 10-20..22):
  - both sizes are pre-signed in the same burst, at the same cent, in the same ms: the median sign-ms of large minus small is 0 over
    1,241 pairs;
  - 42% of bursts with two or more used orders hold both sizes;
  - of the (wallet, burst, cent) cells used twice or more, those holding two sizes are DS 7%, GF 25%, XM 23%.

  The class is chosen at decision time.
- **No per-window large cap** (critique 4).
- **Burst rank is not GF's or XM's size input.** Visible-rank AUC is GF 0.569 and XM 0.459, and the public burst intensity gives
  0.54-0.59. It matters for DS only: 0.70.
- **Public lean proxies are weak but beat the 3-state simulated lean of pre-registration 10(b).** Within-wallet AUC on 10-21..22, no
  fitting:

  | | DS | GF | XM |
  |---|---|---|---|
  | cumulative signed hazard so far in the window | 0.572 | 0.609 | 0.626 |
  | opposite-outcome hazard over the last 3 s (inverted) | | 0.586 | 0.614 |
  | lean16's simulated lean | | 0.52-0.54 | 0.52-0.54 |
  | the operator's realized lean | 0.663 | 0.705 | 0.764 |

- **C is not a path statistic**: R² 0.04 on public path features (critique 2).
- **Print-level selection on the decision clock**: +0.017 over market-only (critique 3).

## Proposals (ranked by the chance they close the gap)

### 1. Size-keyed routing: the class is drawn per decision and the router keeps one wallet list per class (new; falsifies E3 and E6 as stated; changes X159 / X160 / X161 and the ladder16 / lean16 ceilings)

**Hypothesis.**

- Each decision (or event) draws its size class first: about 9% of first legs, 13-14% of all legs, outside size phases.
- A **small** decision goes to the small list (DS > GF > W4 > XM > W5 outside the dispatch phase).
- A **large** decision goes to a large list in which GF comes first, then DS and XM; a priority-slot list or a weighted draw is to be
  decided.
- The 10-21 dispatch experiment changed only the small list.
- Rival reading R2: a large event is a small probe on the small list plus a large follow-up on the next free slot.

**Why it fits.** Critique 1:

- pooled P(large) is invariant to a randomized routing change (-0.004 [-0.014, +0.006], against +0.068 predicted by per-wallet
  rates);
- the first-leg carrier depends on the class (GF 0.57 for large, 0.17 for small);
- legs in an event share the class (0.636 vs 0.285);
- DS's large share doubles in arm B;
- DS's "public" size AUC is half burst intensity.

**Test** (complete calldata 10-20..22; on-chain size proxy >= 90 shares and calldata samples for BUILD).

1. **Replicate the invariance on every routing change on record:**
   - XM's 10-13 / 10-14 step (fills 19-20k -> 1.6-3.1k a day; calldata sample hours on both sides);
   - the 10-31 00-06 / 12-18 and 11-01 06-12 development blocks, where XM is back at ~10k a day (calldata of the operator's taker
     txs; match ms from the shared recorder's `clob_crypto`).

   On each: pooled first-leg large share, and the per-class carrier shares.
2. **Fit class-specific priority-slot dispatchers** (visible occupancy plus W4 / W5 legs; H 150-400 ms; all orders of up to 5
   wallets per class). Fit on 10-20 and score once on 10-21..22.
   - Report carrier accuracy given the true class against 0.778, and XM's precision and recall inside the large class.
   - Separate R1 from R2 with `hidden16`'s maker-first remainder census split by the GF leg's class. R2 predicts that small DS probes
     at L_GF - 1 c precede large GF-led first legs far more often than small ones.
3. **Re-fit the size model at the decision level, pooled, with no wallet identity.**
   - Include the decision-time public burst intensity, the continuous public lean (critique 4) and window time.
   - Re-run ladder16 with the carrier DRAWN from the class-specific dispatcher, using E[large], instead of the true carrier.
   - Restate the condition-5 oracle ledger.
4. **Per-wallet trackers for condition 7.** GF and XM come from the replica's own E[large]-weighted decisions through the large list;
   DS from the small stream plus overflow. Pre-register, then report per-wallet Pearson and Spearman by half.

**Data.**

- `it16/size16_pred_cd.parquet`, `it16/cdfull_*`, `results/disp16b.json`'s W4 / W5 legs and `hidden16.py`;
- the calldata samples in BUILD;
- the post-T0 development blocks: chain calldata plus `clob_crypto`.

**Signature if true.**

- The pooled first-leg large share stays within ±0.02 across every routing change, while per-wallet rates move by 2x or more.
- Class-specific lists name 0.85 or more of carriers given the class.
- XM's large legs are the large list's overflow: precision ≥ 0.6 and recall ≥ 0.4 among large legs.
- Dropping wallet identity collapses DS's within-wallet public size AUC toward its burst component (about 0.70).

**If false.** The invariance fails on the other routing changes. The dispatch-phase result was then a coincident size change in arm
B, and per-wallet rates stand. Write the measured deltas into the size component.

### 2. A three-stream replica for condition 5: add the pair margin and the maker remainders to the net tracker (new for the pair margin; strong form of X133)

**Hypothesis.** The tracker reproduces only the directional net, about 67-70% of W's variance. A replica that also:

- (ii) trades the small two-sided flow at its own decoded decisions, where the tracker absorbs that flow's net, and
- (iii) leaves its lost races and remainders resting as GTC bids at L with the measured TTL,

earns a C_rep and an M_rep that co-vary with the operator's. That adds Spearman, and also breaks the ties at zero PnL in thin
windows.

**Why it fits.** Critique 2:

- C has 11.5-13.7% of W's variance, is independent of D, is common across the operator's wallets (0.52) and is carried by small
  orders (0.88);
- maker-role fills have 16.5% of W's variance, correlate 0.605 with W and earn +$8 a window against -$4 for takers;
- the simulation gives +0.009 to +0.024 Spearman from C alone at ρ 0.3-0.5. The gap is 0.033.

**Test** (capture days; fit on 10-20, score once on 10-21..22, then the reverse; pre-register first).

1. **Stream (ii).** At every frozen-hazard decision bin (dc_hazard14's top bins at the frozen rate), BUY 30 shares on the dc14 side
   at the ask seen + 0.
   - Fill = min(30, ask depth <= L at m - 35) on the capture's L2 (posthold16 physics, r 0.895).
   - The deficit tracker absorbs the stream's net.
2. **Stream (iii).** The unfilled part rests as a bid at L with a TTL drawn from the measured per-wallet Weibull (X94).
   - Fill strictly against later SELL prints at <= L, or complement BUYs at >= 1 - L, with `match_slack` 2.
   - Queue position: behind the book's resting size at L at insertion.
3. **Report per stream:**
   - corr(C_rep, C) and corr(M_rep, M) per window;
   - pooled and per-wallet Pearson and Spearman of R_total against W;
   - the share of windows where the rule has zero PnL, before and after;
   - both latency conventions (a) and (b), with a ruling from the examiner on which one counts.

**Data.**

- `fills.parquet`;
- the capture L2 grid (`it15/l2grid_*`, `l2tok_*`) and `it16/hazbins16.npz`;
- `dcfit14_pred`;
- the `it16` tapes and the HF trades for (iii).

**Signature if true.**

- corr(C_rep, C) ≥ 0.3 and corr(M_rep, M) ≥ 0.3.
- Pooled Spearman rises by 0.02-0.05, crossing 0.5 together with Pearson on both splits.
- DS's per-wallet r gains the most (largest C share).

**If false.** Both correlations stay under 0.15. C and M are then execution-specific (shared by siblings only because they share the
operator's exact decisions and races), and the condition-5 account must say that ~30% of the target's variance is unreachable for a
replica, with these measured shares.

### 3. Freeze the rule on the invariants, and measure the configuration drift before the next exam (strong form of X162 / X123)

**Hypothesis.** The operator changes routing and size settings by schedule:

- on whole UTC hours;
- by window-index arm;
- with XM's role changed again after VALIDATE.

What transfers to an exam lot is the decision-level size share and the class-keyed structure, not per-wallet rates or one routing
list.

**Why it fits.**

- Every known phase boundary sits on an hour.
- The dispatch experiment re-routed small decisions only (proposal 1).
- XM runs ~10k fills a day on 10-31 against 1.6-3.1k on VALIDATE.

**Test.** On the three post-T0 development blocks (10-31 00-06 and 12-18, 11-01 06-12):

- the per-class carrier table, the pooled first-leg large share and the visible-occupancy list fit;
- a change-point scan by hour over 10-09..22 of P(large | first leg), P(DS | small first leg) and P(GF | large first leg), dated
  against the hour grid.

Then decide which parameters the frozen rule may carry: pooled class rate, class-keyed lists, arm terms. Say in FINAL_RULE which
ones are version parameters.

**Data.** Calldata of the operator's taker txs in those blocks (batched `eth_getTransactionByHash`, as cdfull16), the shared
recorder's `clob_crypto` 'x' records for match ms, and `fills.parquet` for BUILD.

**Signature if true.**

- The pooled first-leg large share stays at about 0.08-0.10 on every block.
- The small-list order differs on 10-31 (XM or W4 promoted).
- Phase boundaries fall on hours.
- The exam risk for condition 7 is then quantified before a claim, not after.

### 4. Target the lean's free draws: the first large decisions of a window, with a continuous public lean (strong form of X124 and pre-registration 10(b))

**Hypothesis.** The large stream is an urn on the operator's own large position:

- P(large) runs from 0.05 against a 300-share position, to 0.34 at zero, to 0.51 above 1,000 shares on the same side;
- there is no cap;
- the only free draws are the lean-initiating large decisions, concentrated early in the window (P(large) 0.36 at 0-30 s).

A replica cannot copy the realization, but the SIDE of the initiation follows the window's early public decision flow better than
pre-registration 10(b)'s 3-state controller captured.

**Why it fits.** Critique 4:

- the continuous cumulative signed hazard gives within-wallet large-class AUC GF 0.609 and XM 0.626 with no fitting, against
  0.52-0.54 for lean16's simulated lean;
- the opposite-outcome hazard over the last 3 s, inverted, gives 0.586 and 0.614;
- sign agreement with the realized lean is 0.24-0.27.

**Test.**

1. Per window, label the first large decision. Measure how well its side and its time are predicted from public data at that
   moment: the cumulative signed hazard, and the dc14 side of the window's first decisions.
2. Build a target net in which each decision's weight is P(large | the decision-level model, the continuous public lean, window time)
   from proposal 1's pooled model. Initiation-heavy weights: early decisions count most, and saturation follows the public lean.
3. Pre-register it against mix14 in trk_a on 10-21..22, adopting it only if it beats mix14 on both Pearson and Spearman.

**Data.** `it16/size16_pred_cd.parquet` and `it16/hazbins16.npz` (10-20..22); `dcfit14_pred`; the frozen tracker.

**Signature if true.**

- The side of the first large decision is predicted at ≥ 0.75.
- The window-net r of the new target exceeds mix14's 0.503 / 0.491 by ≥ 0.02.
- Tracker Pearson and Spearman both rise.

**If false.** The initiation side is ≤ 0.65 predictable. The lean is then seeded by the coin. Write the urn's free-draw count per
window (median about 1-3) as the irreducible part of condition 5.

## Sources

- `NOTES.md` iterations 6, 8, 12-16 (iteration-6 finding 1 rebate, iteration-8 finding 14 economics, iteration-14 findings 2 / 5 /
  20 arms and capture baseline, iteration-16 findings 1-15).
- `state.json`: catalog X1-X163, components, target_metrics and target_metrics_notes; `FINAL_RULE.md`.
- `panels/iter15_assumptions.md` and earlier panels.
- `results/econ8.json`, `results/hazflowD15.json`.
- `code/final_rule.py` (`_strict_tracker`), `code/lean16.py`, `code/hazbins16.py`.
