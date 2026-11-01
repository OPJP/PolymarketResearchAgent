# Panel, iteration 9: assumption breaker

Lens: what the investigation takes for granted that may be false. This round I looked at four things: the unit in which
"selectivity" is measured, what the per-window PnL is actually made of, whether the iteration-9 PnL ceiling includes the
mechanism that drives that PnL, and whether every decision leaves a trace.

I ran small checks on development data only:

- VALIDATE 10-19..22 (the 30 / 100 menu days, before H): `orders.parquet`, `windows.parquet` (outcomes used only to settle
  PnL), `binance_1s.parquet`, `b1_orders_sample.parquet`;
- the 10-31 12-18 development block: the frozen FULL hazard design of `stale9` / `flag9`, which I re-ran read-only (fit
  on A, scored on B and C), `ins9b_M.parquet`, `cd9.parquet`, and `btc5m_xclob` through `iter_live`.

Nothing sealed was read, listed or counted, and `.cache/live/sealed/` was not opened. The scripts and JSON outputs are in
the session scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`episode.py`, `episode2.py`, `pivot.py`, `pivot2.py`, `pair.py`, `seed.py`, `phase.py`, `refill.py`). In the PnL checks,
"large" means more than 30 filled shares on a 30 / 100 day, which leaves 11.9% of orders large. The fee is approximated as
0.035 p (1 - p) on taker-first orders.

## Critique

### 1. The "selectivity" numbers are measured on autocorrelated 100-ms grid points, not on decisions or opportunities

`flag9` and `select9` score every 100-ms grid point in the top 1-3% of the FULL score as a separate "flagged instant". The
label is "a cluster decision in [t + 100, t + 600)", so one decision makes up to 5 consecutive grid points positive.
Flagged grid points come in runs. Grouping them into episodes (same window and outcome, gaps of at most 1 s) on C, out of
sample, with the A threshold as in `select9`:

| unit (top 3%) | n | P(decision) |
|---|---|---|
| grid points | 1,094 | 20.4% |
| episodes (gap <= 1 s; median run 4 points, p90 15) | 173 | 35.3% |
| episodes (gap <= 300 ms) | 217 | 31.3% |

- **Top 1%.** 24.6% per point against 36.6% per episode.
- **Skips that are not skips.** 30-42% of the "skipped" flagged points on C (50% on A) lie inside episodes the cluster
  did take. They differ from the taken points only in their offset from the decision, so a taken-vs-skipped classifier
  over points has a low AUC built into it. `select9`'s AUC of 0.58 mixes this artefact with the real question.
- **Which numbers move.** The "decides ~1 in 4-5 flagged instants" claim moves, and so do overlap8's 8.2% at matched
  volume and finding 24's "68% of decisions must be reproduced". All three are per grid point.

### 2. Within an episode the take rate behaves like a constant hazard, and across windows it is overdispersed

- **One-parameter model.** A single parameter p = 0.094 per flagged 100-ms point, fitted on A's episodes as
  P(taken) = 1 - (1 - p)^n, predicts the out-of-sample take rate by run length:

  | run length | 1 | 2-3 | 4-9 | 10+ |
  |---|---|---|---|---|
  | C observed | 9.7% | 29.5% | 38.8% | 61.3% |
  | C predicted | 9.4% | 22.0% | 44.0% | 78.5% |
  | B observed | 17% | 19% | 37% | 86% |
  | B predicted | 9% | 20% | 44% | 81% |

- **Strength adds nothing consistent.** Within run-length strata, the peak hazard score separates taken from untaken
  episodes at AUC 0.41 / 0.54 / 0.61 / 0.58 (C) and 0.50 / 0.72 / 0.47 / 0.17 (B).
- **Window-level overdispersion.** Against that null, the take rate varies across windows more than chance allows:

  | grouping | chi2 / df | groups | p |
  |---|---|---|---|
  | window | 1.95 | 35 | 0.0006 |
  | (window, ladder segment) | 1.54 | 67 | 0.003 |
  | (window, outcome) | 1.24 | 66 | 0.09 |

  This uses 490 episodes over A, B and C.
- **Reading.** The open selection problem may consist of two parts that the instant-level search cannot see:
  - a near-memoryless thinning while the trigger state lasts;
  - a window-level rate.

  An instant-level AUC is the wrong instrument for both. The sample is small (one Saturday afternoon), so all of this
  needs replication on 11-01 06-12.

### 3. The per-window PnL is the large-order lean, so "decision overlap" is the wrong target for condition 5

On VALIDATE 10-19..22 (1,057 windows):

| measure | pooled | DS | GF | XM |
|---|---|---|---|---|
| corr(window PnL, large-order-only PnL) | 0.78 | 0.47 | 0.89 | 0.79 |
| corr(window PnL, small-order-only PnL) | -0.05 | 0.68 | -0.25 | 0.08 |
| sign(netLarge) agrees with the outcome | 51.0% | 49.2% | 50.2% | 50.8% |
| first large order's side agrees with sign(netLarge) | 68% | 82% | 76% | 86% |
| median rel of the first large order | 14 s | 55 s | 18 s | 62 s |

- **Large orders carry the PnL.** corr(window PnL, netLarge x outcome) is 0.77. The large-order PnL has 1.78 times the
  variance of the total, because small orders partly offset it.
- **No directional edge in the lean.** The lean is a coin with respect to the outcome. It is not information; it is the
  outcome of the process.
- **The two size classes play different roles.** Against the operator's running three-wallet net (block clock):
  - large orders go to the long leg in 70% of cases (60% at |net| 60-150, 79% at |net| >= 400): they pyramid;
  - small orders go to the short leg in 57% of cases (54% rising to 61%): they weakly complete sets.

  sign(netLarge) and sign(netSmall) agree in only 38% of windows.
- **Consequence.** For GF and XM, condition 5 is about reproducing a handful of large decisions per window (median 5 and
  2 large orders per wallet window), not 68% of all decisions. Finding 24's formula treats every decision as equally
  weighted and independent, which this structure contradicts.

### 4. The iteration-9 PnL ceiling (0.74) holds sizes fixed, which removes the mechanism that drives the PnL

- **What the ceiling holds fixed.** `pnlceil9`'s r = 1 - (1 - q) kappa resamples race outcomes with the realized sizes
  held fixed. But the size is chosen from the operator's own net, and the large legs then pyramid on it.
- **What a replay would change.** A missed or filled large leg changes the next sizes, and the next sizes change which
  side the lean ends on.
- **Status of 0.74.** It is an upper bound, which FINAL_RULE says in passing. The iteration-8 panel's step 2 ("the size
  mode re-run on each replay's own net") was never run. Until it runs, nobody knows whether condition 5 is attainable at
  all.

### 5. Two load-bearing claims rest on a decision record that is partly inferred

- **What is inferred.** The decision count (1.45 per filled order) treats an unfilled lost race as a GTC order resting at
  the old ask. Their number is inferred as M-first lost races x (1 - pi) / pi, with pi = 0.458 taken from T-first
  remainders.
- **What the finder was validated on.** The 502 truth orders were MT remainders, which rested by construction because
  they later filled as maker. The 273 T-first remainders that never filled were never checked for a book insertion.
  - The anonymous crowd's bot-size increments at the old ask live a median of 70 ms (`pianon9`), so kill-style order
    handling is common on this book.
- **What depends on it.** If some cluster submissions are killed (FAK) or rejected, they leave no trace. Then both "a
  selective bot, not a race lottery" and the 0.74 ceiling would be built on an undercount.

### 6. The next exam is h1, scored at the block clock

The live work of iterations 6-9 (the vote, the hazard, the decision record, edge_rule_V8) cannot be applied to
h1 / h2. There, condition 5 (0.18) and side (76.7%) are decided by the block-clock rule. Two more points:

- **Presence unit.** Presence passes only in the block-second unit, adopted in iteration 5 after the pre-registered
  all-seconds unit missed the gain bar (+0.035). The examiner may score the unit that was pre-registered.
- **Side condition.** XM is literally one-sided in 24.3% of VALIDATE windows. The count-null argument shows the condition
  does not bind in substance, but it is not a pass.

Whatever closes condition 5 has to work at the block clock first. The PnL decomposition in critique 3 does, because it
needs only orders and outcomes.

## Checked and not supported (so nobody redoes them)

- **A timer-loop decision clock.**
  - Cluster taker-match server ms on 10-31 14:00-17:55: DS 537 matches, GF 170.
  - No phase locking at any period from 20 to 1,500 ms. The maximum global Rayleigh n R^2 was 8.2 over about 1,500
    periods, about what chance gives. The crowd reached 11.4, with no peak at 1,000 ms.
  - DS inter-match gaps: 1% at 252 ms, 5% at 305 ms, none under 150 ms. That is a per-wallet refractory period, not a
    clock.
- **A binding pre-signed copy budget.**
  - Visible filled copies per (wallet, window, burst, token, level, size) decay smoothly: DS 30-share 2,613 / 714 / 215 /
    69 / 11 / 2 for 1-6 copies, with no pile-up at a cap.
  - Around the +172.7 s burst, orders used just after the new ladder are LESS often at levels the wallet had used at
    least twice in the previous 120 s than orders used just before it: 5.9% vs 9.7% pooled (DS 9.0% vs 13.5%). That is
    the opposite of a refill signature. The post-burst activity spike of X32 is not depleted levels refilling.
- **The first big BTC move after the open seeding the window's lean.**
  - The first Binance 1-s move of at least 1-5 bp agrees with the first large order's side 49-61% of the time, and with
    sign(netLarge) 47-56%.
  - The first large order falls within 3 s of that move in only 4-20% of windows.
  - The first large order's side does follow the move in [ts - 4, ts - 2] in 74-81% of windows. It is a tick-triggered
    decision at an instant that something else selects.
- **Hidden operator clones taking the skipped instants.**
  - comp9's top competitors co-occur with cluster decisions MORE than chance: skipped : decided ratios of 1.7-6.1
    against a base of 4.8, mostly 1.7-4.3.
  - That makes them co-racers on the same triggers. Dispatcher slots of one operator would be mutually exclusive with
    the cluster.

## Proposals (ranked by the chance of closing the gap)

### 1. Re-target condition 5 on the large-order lean, and compute the PnL ceiling with the own-state size feedback re-simulated (strong form of X69 / X17; new)

- **Hypothesis.** The per-window PnL is |netLarge| times a coin (critique 3). The lean comes from a positive-feedback
  size rule: large orders go to the long leg 70-79% of the time, and size is chosen from the operator's net. Replaying
  the true rule with independent race outcomes and re-chosen sizes then gives a test-retest correlation well below the
  fixed-size 0.74. Either of two things follows:
  - condition 5 is unattainable unless the large-size choice is deterministic in a public input;
  - or, if the bound stays high, the whole PnL target sits in roughly 5-10% of decisions (the large ones).
- **Evidence.**
  - Large-only PnL correlates with the window PnL at 0.78 pooled (GF 0.89, XM 0.79), small-only at -0.05;
    netLarge x outcome at 0.77.
  - The pyramiding shares in critique 3.
  - pnlceil9 holds sizes fixed.
  - Iteration 8 measured the own-net size rule at within-wallet AUC 0.75 / 0.70 / 0.59 with W4. That is strong state
    dependence, but noisy.
- **Test.**
  1. **Decomposition.** Per wallet, pooled and by half, on all VALIDATE days with the day's menu from calldata. Report
     window PnL against large-only and small-only PnL, netLarge x outcome, and the variance shares. This step uses only
     orders and outcomes, so it also works at the block clock for h1.
  2. **Replay with feedback.** Keep the wallet's decision instants, sides and limits fixed. For each replay:
     - resample each order's fill fraction from a BUILD-fitted P(fill fraction | size, first role, price, block-clock
       depth proxy);
     - re-draw the size from the BUILD-fitted P(large | four-wallet operator net as it stands in this replay, wallet,
       rel, price, day menu).

     A missed large fill then changes later sizes. Draw 200 pairs and report r(replay, replay) and r(replay, wallet),
     Pearson and Spearman, per wallet and pooled, with 2-h block bootstrap intervals. This is a LOWER bound, because the
     fitted size rule is noisier than the bot's. The 0.74 is the UPPER bound.
  3. **Partly public size rule.** Repeat step 2 with the live tick-strength term added to the size model, on the 10-31
     and 11-01 development blocks with calldata sizes. This shows how far a better size decode lifts the lower bound.
  4. **Large-decision overlap.** Restrict finding 24's thinning formula to large orders. Report the share phi_L of the
     wallet's LARGE decisions a replica must reproduce for r >= 0.5.
- **Data.** `orders.parquet`, `fills.parquet`, the calldata sample (sizes and limits), `windows.parquet` outcomes,
  W4's fills (`w4size9`), the BUILD tapes for the fill model, and the 10-31 / 11-01 calldata. All development data.
- **Signature if true.**
  - The feedback lower bound is below 0.5 pooled and for GF / XM. The bracket [lower, upper] goes into FINAL_RULE as
    the quantified account of condition 5: unattainable unless the size choice is public.
  - The selection search (X72) then matters for presence and side, not for PnL.
- **Signature if false.**
  - The lower bound stays at or above 0.6. Condition 5 is attainable, and phi_L is the target: work moves to
    proposal 3, the large decisions.
  - "68% of all decisions" is retired.

### 2. Measure selection on episodes, and test evidence accumulation against a constant-hazard null (strong form of X72; corrects flag9 / select9 / overlap8)

- **Hypothesis.** The bot decides at most once per trigger episode (per wallet, with hysteresis), when some accumulated
  quantity crosses a threshold. The alternative null is a memoryless thinning (p ~ 0.09 per 100 ms while the trigger state
  lasts).
  - Under the first, the selection is decodable but invisible to instantaneous features measured per grid point.
  - Under the second, the instant-level selection is genuinely stochastic and belongs in the wall account.
- **Evidence.** Critiques 1-2:
  - the episode take rate is 31-37% against 20-25% per grid point;
  - 30-42% of "skips" lie inside taken episodes;
  - the constant-hazard null predicts B and C by run length;
  - peak strength adds nothing consistent;
  - "positive points per taken episode" has a median of 3, i.e. one decision.
- **Test.**
  1. **Episodes, two ways.**
     - (a) Runs of the frozen FULL score above the A threshold, with gaps of at most 300 ms or 1 s.
     - (b) Independent of any fitted model: runs where the six-series composite toward o over [t - 600, t - 100) ms
       exceeds x bp, with x fixed on A.
  2. **Discrete-time survival model.** Model the first cluster decision in an episode (any wallet, W4 included; matches
     plus lost-race insertions) in 100-ms steps. Censor when o's ask is taken by others or moves up.
     - Covariates, all point-in-time: time since onset; evidence accumulated since onset (cumulative composite move;
       EMAs of the microprice composite at 0.25 / 0.5 / 1 / 2 / 5 s half-lives; the number of venues agreeing so far);
       the change of o's ask since onset; and the instantaneous features of `select9`.
     - Fit on A; score on B, C and the 11-01 06-12 block.
     - Pre-register now the null p = 0.094 per 100 ms in state.
  3. **Hysteresis.** Count decisions per episode per wallet. Compare the hazard after a decision until the score falls
     below a lower threshold with the hazard after that re-arm.
  4. **Re-score at matched volume.** Score overlap8 and the live replica with "one decision per episode, at the first
     step where the survival hazard crosses h*", at matched volume.
- **Data.**
  - `btc5m_clob_raw2` / `btc5m_xclob`, `btc5m_venues2` / `btc5m_xven` / `btc5m_xfam` via `iter_live`;
  - `ins9b_M`, `cd9`, on-chain fills;
  - the 11-01 06-12 development block when it exists.
- **Signature if true (accumulation).**
  - The hazard rises with accumulated evidence, not with time in state.
  - The out-of-sample episode-level AUC from point-in-time features is at least 0.70.
  - At least 80% of taken episodes have one decision per wallet.
  - Overlap at matched volume rises from 8% to 25% or more.
- **Signature if false (coin).**
  - The hazard is flat in time since onset after the 250-350 ms reaction lag, and no point-in-time feature beats the
    in-state indicator.
  - Report the selection as a stochastic thinning with its rate. This is a valid quantitative account. It also feeds
    proposal 1, because a stochastic selection lowers every replica's ceiling.

### 3. Large and small orders are two decision streams: decode the large one (initiation plus pyramiding) as a window-level state machine (new; strong form of X29 / X49 / size9)

- **Hypothesis.** The bot runs two policies through one order factory:
  - the small stream: tick-locked takes that weakly complete sets (57% on the short leg);
  - the large stream: an "initiate, then pyramid" policy. It opens a lean with a large order at some selected strong
    decision, then uses large only on the long leg (70-79%).

  The per-window lean, and with it the PnL, is the state of the large stream. Its initiation instant is selected by
  something other than the first big move. The candidates, all testable:
  - tick strength at decision level (live within-wallet AUC 0.62-0.81);
  - episode accumulation (proposal 2);
  - the implied-vol value gap FV_DVOL - ask;
  - the fan-out (legs >= 2 are event-level, and large co-occurs across wallets 1.68x);
  - pay-up (large orders pay up 41%).
- **Evidence.**
  - Critique 3.
  - The first large order's side follows the move in [ts - 4, ts - 2] in 74-81% of windows, but it falls within 3 s of
    the first big move in only 4-20% of windows.
  - The first large order fixes sign(netLarge) in 76-86% of each wallet's windows.
  - Large orders lose 1-2 c per share, and yet the operator keeps them.
- **Test.**
  1. **Size by rank and state.** On VALIDATE and the 10-31 / 11-01 calldata, per wallet: P(large) by order rank within
     the window, and by four-wallet operator net state (flat / long o / short o).
  2. **Initiation.** Among decisions taken while the operator is flat, find what makes one large. Test the candidates
     above at decision level, live, against market controls; fit on A, score on C and 11-01.
  3. **Continuation.** P(large | long o, adding) as a function of the same features.
  4. **Window-level replica.** Simulate this machine on its OWN state, with public triggers. Score it per window
     against the wallet:
     - agreement of sign(netLarge);
     - |netLarge| rank correlation;
     - PnL correlation, at the block clock (h1) and live.
- **Data.** Calldata sizes (VALIDATE sample, `cd9`, 11-01); on-chain fills incl. W4; the lab venue feeds; DVOL and
  priceToBeat for FV_DVOL.
- **Signature if true.**
  - The within-wallet AUC of initiation from public features is at least 0.75.
  - The replica's sign(netLarge) agrees with the wallet's in at least 70% of windows, and its per-window PnL correlates
    with the wallet's at 0.4 or more.
  - The size component becomes partly public, and condition 5 moves.
- **Signature if false.**
  - Initiation is no better than its own-state null.
  - The lean is then an own-state lottery seeded by race outcomes; together with proposal 1 that is the quantified wall
    for condition 5.

### 4. Selection has a window-level rate: find the window state behind the overdispersion (new; strong form of X27 and of setgate9)

- **Hypothesis.** Given the trigger state, the take rate is set per window (or per ladder segment) by one window-level
  variable. Candidates:
  - the wallets' free collateral, i.e. USDC balance minus open-order reservations, which depends on when the previous
    windows' REDEEMs land (X27, never run);
  - the operator's set state (setgate9: 31% vs 12%);
  - the strike distance and implied vol at the open;
  - crowd intensity in the window;
  - an operator schedule (window parity, minute of the hour, per-wallet hour);
  - the previous window's PnL.

  If one of these explains most of the between-window variance, a large part of the open selection is a
  window-level rule, decodable and replicable.
- **Evidence.**
  - chi2 / df 1.95 by window (p = 0.0006) and 1.54 by (window, segment) against the constant-hazard null.
  - Only 1.24 by (window, outcome). The window effect may be outcome-asymmetric, which fits the set state.
  - Remainders hold reservations, and every position is locked until REDEEM.
- **Test.**
  1. **Random effects.** A hierarchical logistic model on episodes with window and segment random effects (A, B, C,
     then 11-01 06-12). Extract the window effects (BLUPs) and their AR(1) across consecutive windows: a slow regime vs a
     per-window draw.
  2. **Collateral path.** Rebuild each wallet's collateral from Polygon USDC Transfer logs (topic filters on the four
     wallet contracts): fills, REDEEMs, deposits. Add the reservations of known resting orders from the decision record.
  3. **Candidates.** Regress the window effects on each candidate; report the share of variance explained, out of
     sample. Report own-state candidates (set state, collateral) separately.
- **Data.**
  - The Polygon RPC (drpc / publicnode, as in iteration 1) for Transfer logs of development blocks only;
  - on-chain fills and REDEEM activity clamped to development periods;
  - the decision record; Gamma priceToBeat; DVOL.
- **Signature if true.**
  - One variable explains 50% or more of the window-effect variance.
  - For collateral: P(take) collapses when free collateral is below one large order's notional, and recovers right
    after REDEEMs land.
- **Signature if false.** The window effects are an iid draw, with AR(1) near 0 and no candidate above 10%. The window
  rate then goes into the wall account as a per-window draw.

### 5. Does every decision leave a trace? Check the never-filled remainders for a book insertion (strong form of X65 / X35)

- **Hypothesis.** Some cluster submissions are killed (FAK) or rejected and leave no book insertion: for example the
  pay-up or large orders, a balance or self-trade rejection, or orders that arrive after the ask has gone. If so, the
  decision record undercounts unfilled lost races, the 1.45 decisions per filled order is too low, part of the "skips"
  are invisible lost races, and the 0.74 ceiling is too high.
- **Evidence.** Critique 5:
  - the finder's truth set rested by construction;
  - 273 never-filled T-first remainders of 10-31 were never looked up;
  - the crowd's 70-ms median life on the same book.
- **Test.**
  1. **Lookup.** For every T-first order with an unfilled remainder and no maker fill (14:14-17:55, then 11-01 06-12),
     look for a size increment equal to the remainder at (o, limit), within 0-60 ms of the match, in
     `btc5m_clob_raw2`. Use the `ins9` finder unchanged.
  2. **Removals.** For the ones found, find their removal (a size decrease with no trade) and the lifetime.
  3. **Compare** the found share with the truth set's 92.4%, by wallet, size, pay-up and price.
  4. **Recompute** the decision count and the iteration-9 ceiling if the found share falls short.
- **Data.** `cd9` / live calldata, on-chain fills, `btc5m_clob_raw2` (development blocks).
- **Signature if true.** The found share is well below 92% (say 50%) for a definable class. Then:
  - some decisions are invisible;
  - the decisions per filled order rise toward the race-lottery range for that class;
  - the selection question shrinks to race outcomes.
- **Signature if false.** At least 90% are found, with TTLs like the MT remainders. The decision record stands, and
  proposals 2-4 carry the selection question.
