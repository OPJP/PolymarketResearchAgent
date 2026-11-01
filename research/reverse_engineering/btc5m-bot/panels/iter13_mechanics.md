# Panel, iteration 13: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers the pre-signed ladder and its sizes, the fan-out and how
legs are allocated to wallets, resting remainders and maker fills, the inventory path through the window, and the
operator's configuration as distinct from its responses to inputs.

Data I used, all development:
- `calldata_sample.parquet`: 11 sample hours on BUILD and VALIDATE days, all before H, with original order sizes and
  signing ms;
- `orders.parquet` and `fills.parquet`: VALIDATE 10-16..22;
- `it13/dcside13_frame.parquet`: operator taker orders with archive match ms, 10-17..22;
- `it13/streams_sec` / `streams_win`: two13's L / S labels;
- the frozen target's VALIDATE predictions `it12/nf12b_val` + `val_outcome_it4b` (the avg target), and `it12_win_net`;
- the reduced public HF capture for 10-20 (session scratchpad `it13/hf_dl`: `btc_2026-10-20`, `pm_trades_2026-10-20`);
- `m11_ev.parquet`: the 2,155 decisions of the 10-31 12-18 development block (session scratchpad).

Nothing sealed was read, and `.cache/live/sealed/` was not opened (`sealed.py btc5m-bot` at 03:48 UTC: released none). My
scripts are in the session scratchpad,
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m13\`:
- `m13_ab.py`, `m13_ab2.py`, `m13_ab3.py`, `m13_ab4.py`: the experiment schedule;
- `m13_pool.py`: ladder layout, copies, sizes by window index;
- `m13_label.py`: original vs filled size;
- `m13_late.py`, `m13_early.py`, `m13_cut.py`: the window net by segment;
- `m13_role.py`: taker vs maker role;
- `m13_overflow.py`, `m13_xmalone.py`, `m13_busy.py`, `m13_lifo.py`, `m13_burstshare.py`, `m13_xmpyr.py`: dispatch;
- `m13_transit.py`: Binance transit regimes;
- `m13_mclock.py`: a crude presence check on the match clock.

A few numbers come from inline one-offs of the same logic. Apart from this file I wrote nothing to the workspace. Written
11-01 ~03:50 UTC.

## Critique

1. **The operator runs window-index A/B experiments, and more than half of VALIDATE is inside one.** Arms are assigned by
   the 5-minute window index: arm B is `(start_ts / 300) mod 4 in {1, 2}`, the windows starting at :05, :10, :25, :30, :45
   and :50. Arm A is the rest. A scan per day over periods 2-12 (`m13_ab3.py`, ANOVA of per-window behaviour) finds only
   P = 4 and its multiples at p < 1e-6. Two phases:

   | phase (UTC, hourly test) | what alternates | A windows | B windows |
   |---|---|---|---|
   | size: 10-16 00-01 and 10-16 04 -> 10-19 13 (ends with the 10-19 13:40 restart) | base order size, every wallet (DS, GF, XM, W4) | 30 (10-17 DS calldata: 30:70 / 50:6 at k4 = 0) | 50 (10-17 DS: 50:77 at k4 = 1, 50:41 at k4 = 2) |
   | dispatch: 10-21 16 -> 10-22 13 | DS share of orders, hourly | 0.58-0.71 | 0.36-0.48 (GF takes it) |

   In the dispatch phase, DS has 62.7 taker orders per window in A windows and 35.6 in B. GF has 25.8 and 40.2. XM has
   6.2 and 7.0.

   - **What does not alternate.** The take rate does not: orders per window are 100-118 in both arms. The side does not:
     agreement with the 250-ms spot tick is DS 0.69, GF 0.73-0.77 and XM 0.75-0.76 in both arms. Nor does the price
     level.
   - **Coverage.** About 106 of the 168 VALIDATE hours lie in a phase.
   - **A BUILD hint, P = 2.** In the 10-15 sample hour, GF's 50-share orders are 50 / 146 and 52 / 145 in k4 = 0 / 2,
     against 8 / 91 and 16 / 103 in k4 = 1 / 3.
   - **10-31.** No strong phase in the 14:55-17:55 development block (`m11_ev`: DS 0.54 vs 0.60).

   Nobody has seen this. NOTES records "a fixed (small, large) menu per day", e.g. "10-16 (50, 30, 200)". The
   consequences:

   - **(a) The "large lean" on 10-16..19 is mostly the B arm's base size.** two13's LARGE label (filled ≥ 45 shares)
     covers 61-79% of B-arm shares and 19-28% of A-arm shares. Of all LARGE-stream shares, 76-84% come from B windows
     (10-16 0.757, 10-17 0.797, 10-18 0.843, 10-19 0.775; 10-20 0.513). That affects:
     - iteration 13's findings 1-3 (the cross-wallet L correlation 0.35-0.47, L13's r 0.32, the BUILD loadings);
     - side13's large / small split;
     - X49's size AUCs;
     - the size component as written.
   - **(b) The carrying wallet is predictable from public state in the dispatch phase.** dispatch13's "the carrying wallet
     is not predictable from public state" never tried the window index. On 10-21 / 10-22 it predicts DS vs GF strongly.
   - **(c) Part of the dispatcher's overdispersion is these arms.** The iteration-12 mechanics panel measured the DS share
     per 60-s block at sd 0.18 against 0.12 binomial.
   - **(d) Exam risk for condition 7.** A phase that falls in one half of h1 shifts the per-wallet shares between the
     examiner's halves. The rule cannot see the phase without the wallets' own orders.

2. **The size label is the decision times the race.** On the calldata sample hours, against the original size:
   - **10-19..22.** 264 of 609 original-100 taker orders (43%; DS 46%, GF 44%, XM 37%) fill fewer than 45 shares and are
     labelled SMALL. The filled-share quartiles are 15-18 / 50-79 / 100.
   - **10-17..18.** 191 of 419 original-50 orders (46%) are labelled SMALL.

   `dcside13_frame.osz` is filled shares as well. The race censors the large decisions most where the tick is strongest,
   because strong ticks lose more races. So any P(large | decision) fitted on these labels is attenuated, and so is any
   statement that "large size follows tick strength" measured on VALIDATE. The live AUC of 0.72 used calldata sizes.

3. **The window net is set in the first 150 s, and that is where the public headroom for condition 5 is** (`m13_late.py`,
   `m13_early.py`, `m13_cut.py`; VALIDATE, 2,016 windows). Against the window net N:

   | segment | r(N, operator flow in segment) | frozen avg target vs that flow |
   |---|---|---|
   | [0, 60) s | 0.465 | 0.494 |
   | [0, 150) s | 0.736 (L 0.600, S 0.298) | 0.515 |
   | [150, 300) s | 0.588 (S -0.19) | 0.375 |

   - The PnL oracle of flow[0, 150) x outcome is 0.628.
   - Truncating the frozen target does not help. Its r with N is 0.433 at T = 150, 0.484 at 240 and 0.480 at 300.
   - The late segment is the pairing (own state) and weak late ticks; the decision-clock side is 62-72% there.
   - The early segment is the tick-following lean, where the decision-clock side is 81-83%.

   The work for condition 5 belongs in the early segment. The late one is near its public limit.

4. **The maker-role net is a second, nearly independent stream that no component models** (`m13_role.py`; VALIDATE,
   pooled, 1,904 windows).
   - Size: the per-window sd is 369 shares for the taker net and 191 for the maker net.
   - Correlations: r(N, T) 0.902, r(N, M) 0.556 and r(T, M) 0.142. Per wallet, r(T, M) is DS 0.015, GF 0.217 and XM 0.018.
   - PnL: maker fills carry 32% of the pooled per-window PnL variance.
   - The frozen target predicts T at 0.416 and M at 0.298.
   - Timing: the median maker fill is at rel 114 s, and only 0.7% of maker shares come after 270 s.

   M is the lost-race remainder process: insertion at the old ask, a per-wallet TTL, and a fill by complement buyers. All
   of its parts are visible in the public capture.

5. **XM's ladder loop has no stall.**
   - The median signing span per wallet-burst is 170 ms for XM, against 908 / 916 ms for DS / GF.
   - The per-cent rate is the same (1.55 / 1.66 / 1.69 ms per cent), and so is the number of used levels (14 / 15 / 12).
   - The ~0.8-s await is in DS's and GF's loops only. It is possibly clob-client's per-instance tick-size / fee-rate fetch.

   Two consequences:
   - XM's bursts are the stall-free segments that X105 needs.
   - XM's orders come from a different client instance or code path, which fits per-wallet executors (iteration-11
     mechanics P3).

## Checks (so nobody redoes them)

- **Outside the phases, dispatch is close to a weighted lottery** (`m13_busy.py`, `m13_lifo.py`, `m13_burstshare.py`,
  `m13_overflow.py`; archive decision clock, 10-17..22).
  - XM is not an overflow wallet. Its single-leg orders (37% of its taker orders) occur with DS busy 6.0% and GF busy 6.4%
    of the time; busy means a match within (t - 250, t + 150] ms.
  - First legs with all three wallets free go DS 76.8%, GF 19.1% and XM 4.1%.
  - P(the chosen wallet = the most recently used free wallet) exceeds independence by only 2-4 points over 0.3-30 s.
  - XM's share is 5.7-7.5% at every offset from -10 to +10 s around the bursts.
  - Per window, XM's taker net against DS + GF's has r 0.092. Against DS + GF's legs in events of 3 or more legs it is
    0.299.
- **XM per window** (`m13_xmpyr.py`).
  - sign(net) equals the side of its first order in 72.8% of windows (66.3% of multi-order windows).
  - The first order sits at a median rel of 36 s and agrees with the spot tick 80.4%.
  - XM does not pyramid its own inventory: P(buy toward its own long side) is 0.475.
- **Copies** (`m13_pool.py`).
  - Per (wallet, burst, token, cent, size), mostly a single copy is used: DS 77%, GF 90%, XM 83%.
  - XM never uses more than two large copies.
  - Copy exhaustion is not observable from used orders. The iteration-11 panel's copy test stands.
- **No Binance-transit regime as the 30-60-s state** (`m13_transit.py`, 10-20).
  - Spot trade transit (receive minus exchange) has q50 134 ms, q90 158 ms and q99 1,427 ms.
  - Seconds with a median transit above 200 ms are 0.03% of the day. Episodes last 1.2 s, and the ACF is about 0 beyond
    1 s.
  - The spikes coincide with activity bursts: the decision rate rises with transit, from 0.33 to 0.58 per second, as
    activity does.
- **No PnL-driven risk scaling.** Spearman of |net| or gross against the previous window's or the previous hour's PnL is
  -0.016..+0.06 on BUILD and on VALIDATE, raw and day-demeaned.
- **A crude match-clock presence is not a shortcut** (`m13_mclock.py`).
  - Setup: 10-20, 250-ms bins, features ending 180 ms before the bin.
  - Result: held-out AUC 0.644 for market activity alone and 0.648 with the Binance tick.
  - A fixed bin with PIT features misses the trigger tick of most decisions inside it. The decision clock helps side
    and size, not a binned presence label.
- **The burst schedule does not steer dispatch:** wallet shares are flat across burst offsets (above).

## Proposals (ranked by the chance of closing the gap)

### 1. Decode the experiment schedule: phase map, arm-aware labels, refits within phases, and the exam risk (new)

**Hypothesis.** The operator runs controlled experiments on its own configuration.
- Arms are assigned by the 5-minute window index: mod 4 in {1, 2} on VALIDATE, and possibly mod 2 on 10-15.
- Phases are switched on and off at restarts or by hand.
- Order sizes and per-wallet dispatch weights are experimental settings, not responses to market state. The trigger and
  the side are not varied.

Several VALIDATE "components" are therefore mixtures over arms and phases: the daily menu, the large lean L, the
per-wallet loadings and the dispatch overdispersion. Some differences between days that look like versions are phase
changes.

**Why it fits.** Critique 1: the two P = 4 phases, the arm-dominated LARGE stream, and the dispatch shift with an
unchanged take rate and side. It also fits:
- the menus that change almost daily (60/100 -> 30/50 -> 50/30/200 -> 30/100);
- the fresh size per day in August (version10).

Both are what an operator tuning its parameters would do.

**Test.**
1. *Phase map.* For every development hour with data, compute per arm (mod 2 and mod 4):
   - the original-size mix;
   - wallet shares and orders per window;
   - P(large original);
   - pay-up share, view lag Λ (lam11) and remainder TTL;
   - burst offsets;
   - decision-clock side agreement.

   The data:
   - VALIDATE orders / fills;
   - the BUILD calldata sample hours;
   - the August-September version10 / 11 samples;
   - the 10-31 / 11-01 development blocks.

   Flag phases with a B-vs-A test per hour (p < 1e-3), and align the boundaries with restarts (signing-schedule breaks,
   the 10-19 13:40 change, outages) and with X9 / X26.
2. *Arm-aware labels.*
   - Define the size class against the window's arm menu, using original sizes:
     - 10-16: 200 is large in both arms;
     - 10-17..18: the B arm has no separate large, or 50 serves as the base size;
     - 10-19 to 13:40: the same as 10-17..18;
     - after 13:40: 100 is large.
   - Rerun two13 / ls13 / side13 with these labels: the cross-wallet L correlation, L13's window r, the pairing kernel
     and the per-wallet loadings, inside and outside phases.
3. *Natural experiments.* The arms are interleaved windows of the same hours, so they give causal contrasts:
   - the size arm (30 vs 50): fill fraction, race loss, maker refill and per-window PnL per share;
   - the dispatch arm: per-wallet fill fraction, pay-up and Λ at matched decisions. This shows what the operator was
     testing, for example which wallet's route wins races. It is direct evidence on the process topology (iteration-11
     mechanics P3).
4. *Exam risk, measured before the claim.*
   - Count phase-hours per development day.
   - Score the frozen tracker's per-wallet PnL r inside vs outside the dispatch phase.
   - Simulate condition 7's halves on VALIDATE with a phase in one half.
   - Write into `FINAL_RULE.md` which components are scheduled configuration (an arm schedule with unknown parameters) and
     which respond to inputs.
5. *Use the public part.* The window index is known at listing. Add `index mod 4` and `index mod 2` to the size and
   dispatch models on VALIDATE and report the gain per phase. It cannot reveal an unknown phase on h1, but it removes
   the arm from the residual inside known phases.

**Data.** `orders.parquet`, `fills.parquet`, `calldata_sample.parquet`, the version10 / 11 calldata samples, the
development blocks' calldata, the it13 frames.

**Signature if true.**
- Phases have sharp boundaries tied to restarts.
- Inside a phase the arm explains most of the size mix or the share shift (DS 0.36-0.48 vs 0.58-0.71).
- Arm-aware L gives a cleaner cross-wallet L structure and a higher public predictability than L13's 0.32.
- The size component becomes "arm-specific menus on a 20-minute schedule".

**If false.** The mod-4 effects are confined to the two phases found here and nothing else alternates. Then the relabel
in step 2 is still required for VALIDATE, and the phases become two dated configuration events in the version history.

### 2. The window net is formed in the first 150 s: an early-segment exposure model at millisecond resolution (strong form of X110 and of X113 step 5)

**Hypothesis.** The lean that decides the window's PnL is placed in minutes 0-2.5 by tick-following decisions. The rest
of the window is pairing on own state, plus late ticks that the bot follows only 62-72% of the time. A public model can
therefore move condition 5 only through the early segment. There the frozen block-clock target sees 0.515 of a flow that
carries 0.736 of the net.

**Why it fits.**
- Critique 3: the segment oracles and the frozen target's r by segment.
- The decision-clock side is 81-83% in minutes 0-2.
- The large orders are 1.4x more likely at the open.
- The late small flow runs against N (-0.19), as pairing does.

**Test** (pre-register before fitting; split 10-17..19 -> 10-20..22, as in pre-registrations 3 and 4).
1. *Target.* The operator's signed filled shares, taker plus maker, Up +, per second for rel in [0, 150), excluding
   W4 / W5.
2. *Features at each second's end,* from inputs the capture carries on every day, exam days included:
   - Binance spot-book events at 100-ms resolution: counts and signed strength of microprice ticks of at least
     0.1 / 0.5 / 1 bp, the maximum |tick| and returns over the last 100 / 250 / 500 / 1,000 ms;
   - the archive touch of o and ō: ask level, ask changes, spread;
   - non-operator archive trades: signed counts over the last 0.5 / 2 s, excluding every operator, W4 and W5 tx;
   - rel and the window's opening state.

   No own state.
3. *Splice.* The predicted early flow plus the frozen avg target over [150, 300). Run it through trk_a with the same
   constants, strict fills and latency of at least 2 s.
4. *Report:*
   - r(predicted early flow, early flow) against 0.515;
   - r(spliced target, N) against 0.480;
   - PnL r pooled and per wallet, with the 2-h block CI and the halves.

**Data.** The HF capture day files for 10-17..22 (the spot book is already reduced; touch for 10-20 / 10-21 only, so either
add the touch for 10-17..19 or drop the touch features), `fills.parquet`, the it12 VALIDATE predictions. Ingest politely:
coalesced ranges, no more than 2 threads, back off on 429.

**Signature if true.**
- The early-flow r reaches 0.62 or more.
- The spliced tracker's PnL r reaches 0.50 / 0.50 pooled, with the block CI lower bound at 0.45 or more.
- GF and DS rise in proportion.

**If false.** The early-flow r stays at 0.55 or below. Then the public share of the lean is bounded at millisecond
resolution too. That is the quantitative condition-5 account for the wall section: the oracle is 0.736, the public model
reaches X, and the gap is dispatch and race luck.

### 3. The true size decision: original sizes at the decision clock, with the capture's L2 book (strong form of X49 / X64; the lean L that drives GF's PnL)

**Hypothesis.** "Large" is a second threshold on the same trigger:
- edge = tick strength x delta - cost, as in fee9's V_k;
- possibly gated by thin visible depth at o's ask;
- applied per experiment arm (proposal 1).

On VALIDATE it looks weak because the label is filled shares (critique 2) and because the B arm contaminates it
(critique 1). GF's per-wallet PnL ceiling with a perfect L is 0.753, so a better L also moves condition 7 for GF.

**Why it fits.**
- Live, the 100-share size follows the millisecond tick at AUC 0.72 (calldata sizes).
- On VALIDATE the block-clock size AUC is about 0.5.
- Live, large orders come with thin books (DS touch-size AUC 0.37, n = 19-20, under-powered).
- fee9 found a sharp step in the hazard at V_k = 0 for every k: a threshold structure.

**Test.**
1. *Original sizes on VALIDATE.* Two routes:
   - batched `eth_getTransactionByHash` for the operator's taker txs, using the archive's tx hashes, in 4 sampled hours
     per day of 10-17..22 (about 25-30k txs; keep the decoded fields only);
   - or original = filled + the remainder inserted at (o, L) at m, read from the capture's `price_change` events. The
     `askSize` / `bidSize` / `askPrice` / `bidPrice` columns are not ingested yet. Read only the row groups of the sampled
     hours.
2. *Labels.* Arm-aware (proposal 1, step 2).
3. *Model.* P(large | decision) at a = m - 180 ms, within wallet, from:
   - |spot microprice return| over 100 / 250 / 500 ms;
   - V_k with the archive touch;
   - |ask - 0.5| and rel;
   - o's ask size and depth within 1-2 c at a - 30 ms (L2);
   - the size of the trade that removed the previous touch level;
   - non-operator prints in [a - 500, a).

   Fit on 10-17..19 and score on 10-20..22. Then build a large-flow model per window, L_dc = Σ P(decide) P(large) side x
   size, and compare its window r with the arm-aware true L.

**Data.** Archive tx hashes (`pm_trades_*`), Polygon RPC (drpc, about 100 txs per batch with backoff), the capture L2
columns for the sampled hours, `dcside13_frame`.

**Signature if true.**
- Within-wallet AUC of 0.70 or more on VALIDATE.
- A step in P(large) at a second V threshold, the same in both halves.
- L_dc window r of 0.45 or more, against L13's 0.32.
- A GF tracker built on L_dc reaches 0.45 or more.

**If false.** The AUC stays below 0.6 with original labels. Then the size is configuration (proposal 1) plus own-state
pyramiding (side13: +0.27 on large seconds), not an input response. Write the size component that way.

### 4. The maker-role net as a remainder process replayed on the archive book (strong form of X93 / X107 / X113 step 5, for the M stream)

**Hypothesis.** M is made of lost-race remainders:
- an operator BUY on o arrives after o's ask was consumed inside the 150-ms hold;
- it rests at the old ask L for a per-wallet TTL (Weibull, medians DS 328 / GF 240 / XM 124 ms, shape 0.63-0.77);
- it fills if a complement buyer (BUY ō at 1 - L or better, a mint) or an o seller crosses it;
- remainders under about 5 shares never rest.

Its sign follows the lost-race decisions, and its size follows the crowd's complement flow right after a move. Every one
of these events is in the public capture.

**Why it fits.** Critique 4, plus what is already measured:
- 69-83% of the resting orders are lost races;
- the remainder is inserted 17-33 ms before the trade message (ghost10);
- one third of lost races with nobody ahead are lost to maker requotes during the hold (queue10);
- maker fills come early (median rel 114 s).

**Test** (10-20 / 10-21, where the touch and the trades at server ms exist; add L2 for queue position).
1. For each trigger instant of the public decision-clock hazard (the frozen block-second presence score or the
   decision-clock flow model of proposal 2):
   - would a BUY at o's ask a - 30 ms, arriving at a + 150, have lost? That is, was the ask level consumed by
     non-operator trades in [a, a + 150)?
   - if so, would a bid resting at L behind the visible size at L be crossed by a non-operator trade within a TTL drawn
     from the per-wallet Weibull?
2. Expected M flow per second = hazard x P(lost) x P(fill) x side x the expected remainder size. Score the window sum
   against M, pooled and per wallet. Add it to the tracker's target, under the same pre-registration discipline.

**Data.** `pm_trades_2026-10-20/21`, `pm_touch_2026-10-20/21`, the capture L2 columns for those days, the rem10 / ins9b TTL
fits, `fills.parquet` (role M, for scoring only).

**Signature if true.**
- r(expected M, M) reaches 0.40 or more, against the frozen target's 0.298.
- The tracker with the expected M added reaches 0.50 / 0.50 pooled.
- XM's maker-role net (r(T, M) 0.018 for XM) gets its first public predictor.

**If false.** M follows the operator's private arrival order inside the hold. It is then race luck, and its share of the
PnL variance (32%) enters the condition-5 account as a measured unexplained part.

### 5. Dispatch as a scheduled lottery: prove that condition 7 for XM is a thinning limit (strong form of X55's dispatcher fit, X120 step 5 and X122)

**Hypothesis.** Outside experiment phases, the wallet that carries a decision is an i.i.d. weighted draw: for first legs,
DS about 77%, GF 19% and XM 4%. The draw is modified only by:
- the per-wallet slot (no second order within about 250 ms);
- the phase weights of proposal 1;
- the fixed leg order of fan-outs.

XM's legs are then a random 4-6% thinning of the operator's decisions, and no rule can reach the PnL r of about 0.47 for
XM that condition 7 asks.

**Why it fits.** The dispatch checks above:
- no overflow;
- stickiness of only 2-4 points;
- no burst effect;
- XM's net against DS + GF's at r 0.09.

Also the measured oracles: XM reaches 0.30 against the perfect pooled net, and 0.41 even with its true window share.

**Test.**
1. *Multinomial logit* of the first-leg wallet, all wallets free, on:
   - the window index mod 4 x phase;
   - each wallet's time since its last order, its window inventory and window PnL so far, and its last race outcome;
   - leg size, rel and UTC hour;
   - cumulative daily volume against the final daily volume (the tier or quota of X33 / X53);
   - day fixed effects.

   Compare held-out log-loss with the base rates per phase.
2. *Exact ceiling.* Keep the operator's true decisions and true fill fractions, re-draw the carrying wallet from the
   fitted weights 2,000 times, and get the distribution of XM's per-window PnL r against:
   - the true pooled net;
   - the frozen tracker.

   If XM's actual 0.30 lies inside the draws, the residual is lottery noise.
3. *Link to X105.* Once a PRNG state is recovered on XM's stall-free loops (critique 5), check whether a Math.random draw
   between decisions predicts the wallet.

**Data.** `dcside13_frame`, `fills.parquet`, the phase map of proposal 1.

**Signature if true.**
- Outside phases the log-loss gain is under 1%.
- The 97.5% quantile of the simulated XM r is below 0.47.

Condition 7 for XM is then a proven random-thinning limit. That is the statement the wall section needs. Side and price
per order do not depend on the wallet, apart from the pay-up, so XM's side condition is unaffected.

**If false.** A state predicts the wallet. Then build per-wallet rules on that state. If the state is public, it opens
condition 7. If it is own state, report it with and without.
