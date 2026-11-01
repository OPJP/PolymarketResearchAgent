# Panel, iteration 14: assumption breaker

Lens: what the iteration-14 account takes for granted that may be false. This round tests the claims behind the conditions that
still fail (2 at the block clock, 5, 7) and the claims that let the others count as met:

- "conditions 5 and 7 fail because a public input is missing", against "they fail because the operator flips coins";
- "condition 7 for XM is a measured random-thinning ceiling, sqrt(0.185) = 0.43";
- "the remaining coins are unobservable": which top-hazard instant is taken, which size copy is used, which wallet carries it;
- "the capture-aware market baseline is made of independent traders";
- "the A/B arms are one process with a configuration switch" and "size is not a trigger response";
- "the VALIDATE numbers are what the examiner will compute on h1".

## Data and checks

Development data only:

- `fills.parquet` (windows starting before H; max fill ts 1792713552 < H);
- the reduced HF capture already on disk (`it13/hf_dl`: `pm_trades_*`, `btc_*`, 10-17..22);
- `it13/tapes` (data-api taker tapes of the VALIDATE windows, with `proxyWallet`);
- the iteration-14 frames `it14/dcclock14_frame.parquet` and `it14/dcfit14_pred.parquet`;
- `calldata_sample.parquet` with `_txs` (max block ts 1792684772 < H) and `b1_orders_sample.parquet` (starts < H).

Nothing sealed was read, listed or counted, and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` at 11-01 05:08 UTC
showed no released lots and a sealed current block.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p14a\`.
Each ran under 300 MB and under 3 minutes.

| script | what it checks |
|---|---|
| `pnldec.py` | per-window PnL: the lean against the pair / fee term, and Pearson against Spearman |
| `netform.py`, `xmentry.py` | how early the window lean forms; XM's first order in each window |
| `netcorr.py`, `loo.py`, `splithalf.py` | cross-wallet net correlations; a leave-one-wallet-out oracle; the natural split-half ceiling |
| `routestate.py`, `rr.py` | wallet routing by the add / reduce state; round-robin against i.i.d. in the decision sequence |
| `coarr.py`, `fpcheck.py` | co-arrival census of the fast crowd at server ms; calldata fingerprint of the top co-arrivers |
| `armproc.py` | the signing process by arm |
| `sizeev.py`, `largecount.py`, `depthsize.py`, `dsregime.py`, `sizehours.py` | size: an EV-scaled trigger, large counts per window, consumed depth by size, DS's large regime, size-scale hours |

## Critique

### 1. Conditions 5 and 7 are treated as prediction problems. The data say they are reliability problems.

**The ranks are the lean.**

- Spearman(wallet window PnL, the TRUE lean x outcome sign) is 0.907 pooled; the Pearson is 0.885.
- The pair / fee term carries 13.7% of the PnL variance.
- So nothing in the wallet's own PnL needs a separate Spearman story: condition 5 is "predict the final lean".

**The lean forms throughout the window.** corr(final net, net at rel < 60 / 120 / 180 / 240 s) = 0.47 / 0.66 / 0.81 / 0.93. The
net after the first second of the operator's activity in the window gives only 0.13.

**The wallets share very little lean.**

- Window-net correlations on VALIDATE: DS-GF 0.209, DS-XM 0.001, GF-XM 0.120. No single common factor produces DS-XM ~ 0
  together with GF-XM = 0.12.
- A leave-one-wallet-out oracle predicts each wallet's window PnL from the OTHER wallets' true realized leans x outcome. On
  10-20..22 it gives (Pearson / Spearman):
  - DS 0.25 / 0.35;
  - GF 0.25 / 0.34;
  - XM 0.05 / 0.09.
- The public tracker already does better for DS (0.467) and GF (0.401) than the siblings' true leans do. XM's PnL shares
  almost nothing with the rest of the operator.

**A natural split-half.** The operator's decisions are spread across the wallets at random (critique 2), so the wallets are random
subsets of one decision stream. On 10-20..22, the per-order signed-share variance shares are DS 0.45, GF 0.44 and XM 0.12, and
fan-out legs are not merged. A thinning model fitted to corr(L_w, L_rest) gives:

- the reliability of the common (path plus operator-state) part of the pooled lean: 0.42-0.48 (DS and GF splits);
- for a predictor that knew that common part perfectly, ceilings of ~0.65-0.70 pooled, ~0.49 for DS, ~0.54 for GF and ~0.18 for
  XM (XM's own split gives 0.08 with the rest).

Fan-out legs inflate the cross-wallet correlation, so these are upper bounds of the common part.

**XM's lean is one draw per window.** XM's final net sign equals the sign of its first order in 69.4% of windows (corr 0.42). That
first order sits at a median rel of 32 s.

**Reading.** Condition 7 asks for ~0.47 per wallet and per half.

- Under the operator's own coin flips, DS sits at its common-part ceiling and XM far below it.
- The planned decision replica and arm-aware size can still move the pooled number.
- They cannot move these ceilings unless one of the coins is not a coin.

The brief's wall test asks for exactly this statement ("statistically indistinguishable from random given every state variable
you measured"), and the account does not make it yet.

### 2. The XM ceiling: the conclusion is right, the argument is model-relative

thin14 says "no predictor can exceed sqrt(0.185) = 0.43". That number is the test-retest of redraws from P^(wallet | public),
which has an XM AUC of 0.67 on the inputs rel, hour, k4, tick strength and leg rank.

- The iteration-13 panel already measured 0.768-0.785 for XM with the decision-clock spot and venue state.
- A sharper P^ gives a higher redraw ceiling.
- The sentence is a theorem only if the allocation is random given everything. As written, it bounds predictors that use this
  P^.

The sequence data support near-i.i.d. allocation (`rr.py`, `routestate.py`):

- **Gaps between XM-led events** have a mean of 22.5 decisions, which is the geometric value. The CV is 1.13 against 0.98, which
  is mild clustering: P(gap = 1) is 0.072 against 0.045.
- **P(XM leads)** is flat at 0.03-0.05 across the decision index 0..30 of the window.
- **Leader transitions:** DS -> XM 0.041, GF -> XM 0.053, XM -> XM 0.072.
- **Routing by the operator's inventory state:** XM carries 7.4% of reducing orders and 5.5% of flat or adding ones. The
  carrying wallet barely depends on the add / reduce state.

The proof still needs two things:

- the ceiling recomputed with the best P^;
- the curve ceiling(AUC), so that the allocation AUC XM would need for 0.47 is known.

The information panel's P2 (per-wallet clocks) supplies the stronger P^.

### 3. "Unobservable coins" is an assumption: the operator's randomness source leaks into public data

One TypeScript process signs every ladder, with salt = round(Math.random() x Date.now()). If the wallet, size and take choices
also call Math.random in the same isolate, the coins are draws from a stream whose outputs are partly public: the salts of filled
orders.

- X99 was tested only in its simplest form. Iteration 10 assumed V8, one call per order, copies within +-24 calls and Date.now()
  equal to the timestamp field.
- X105, which places the outputs with the loop layout, was never run.

Under the user's premise ("inputs that exist somewhere"), this is the one place where the residual coins could become an input. A
wall claim will not survive the auditors while it is open.

### 4. The fast crowd is independent, so the block-second failure stands (checked)

Co-arrival census, 10-20..22 (`coarr.py`):

- **Rates.** 4.73% of non-operator taker BUYs match within +-40 ms of an operator match on the same token. The placebos give 1.94%
  (+1 s) and 1.75% (other token).
- **Concentration of the excess.** The top 5 wallets carry 38.5% of it, the top 10 51.5% and the top 50 83.4%.
- **W4 and W5 lead.** W4 is first: 32.3% of its 9,392 taker transactions co-arrive. W5 co-arrives in 42.5%.

The next heavy co-arrivers are 0xb15cd20d (20.5%), 0xeebde7a0 (17.7%), 0x576b0696 (17.4%), 0x095fd7cc (24.6%) and a few more. They
are not operator legs (`fpcheck.py`):

- they sign fresh: a median sign-to-block of 2.8-4.2 s, against the operator's 71 s with 98% pre-signed;
- they use other signature types: sig_type 1 or 2 with length 65, or sig_type 3 with length 480;
- they match a median 2-22 ms after the operator.

They are independent fast takers on the same route. One of them sits within 40 ms of 15.9% of the operator's taker matches.

The capture-aware baseline is therefore legitimate, and the decision clock is the only honest presence unit. The mechanics panel's
P3 already reports a touch-aware baseline of 0.776. A practical use: these ~10 wallets are the race, and their calldata `sign_ms`
gives their decision instants.

### 5. Size: three more mechanisms ruled out

**Not an EV threshold.** On the 30 / 100 days, the large size has an AUC of 0.565-0.596 on the delta-scaled knee move
(phi(z) / sqrt(tau) x move). The raw move gives 0.561-0.590. On 10-19 (the arm phase) the AUC falls below 0.5.

**The original size is not depth-aware.** At the taker step, 30-share and 100-share orders consume the same liquidity:

| P(taker step fills >= x shares) | x = 10 | x = 20 | x = 29.5 |
|---|---|---|---|
| 30-share orders | 0.833 | 0.679 | 0.535 |
| 100-share orders | 0.805 | 0.667 | 0.596 |

100-share orders fill a mean 53% at the taker step, against 75% for 30-share orders. This fits the mechanics panel's "filled size
is the visible depth": the menu is a coin, and the fill is min(menu, depth).

**Large counts per window.**

- GF and XM are binomial: variance 12.5 against 13.5, and 2.0 against 2.3.
- DS is overdispersed: 15.7 against 3.0.
- That matches pyramiding. After a large decision, the next decision on the same outcome is large 19.5% of the time, and the next
  decision on the other outcome 6.3%.

One operational hour stands out: on 10-20 at 19 UTC every wallet was 57-71% large. Only a few windows traded in it (0.6% of the
lean variance). It looks like a restart default.

### 6. The arms are one process

- **Same signing schedule in both arms.** The b1 burst sits at DS 42,427 vs 42,383 ms, and the GF - DS stagger is 1,083 vs 1,086 ms.
- **Same loop speed:** 1.65-1.69 ms per cent in both arms.
- **What B is.** B windows are the windows whose end time falls in an odd 10-minute block (floor(end / 600) odd). That is a
  10-minute alternation offset by 5 minutes: a scheduler setting, not a second host.

### 7. The exam path rests on assumptions nobody has tested

**The label clock.** The decision-clock presence needs the examiner to place fills by the capture's match ms.

- The capture has a match ms for 97.3% of transactions.
- Hour 23 sits in the next day's file.
- If the examiner labels by block timestamp, the unit collapses to the block second, and that unit fails.

**The BUILD clause.** The examiner fits its baseline "with the same BUILD data", and BUILD (10-09..16) has no capture.

**The size menus.** The menu changed almost daily before 10-19: (60, 100), (30, 50), (50, 30, 200), (50, 30), (30, 100). The three
score days 10-20..22 all ran 30 / 100, so a pooled Pearson over days with different menus has never been tested.

**The h1 calendar.**

- h1 includes Sunday 10-25. The side was never scored out of sample on a weekend, although the hazard was.
- It includes 10-29 with its 1-hour pause: bins with spot moves but no market.

**Condition 7's halves for XM's side.**

- Per order: 0.847 / 0.786, inside the 77% floor.
- Per decision: 0.807 / 0.764, below it.

## Checked and not supported (so nobody redoes them)

- **The pair / fee term as the cause of the Spearman deficit.** It carries 13.7% of the variance; the lean alone gives Spearman 0.907.
- **Hidden operator legs among the top co-arrivers.** Apart from W4 and W5, they sign fresh and use other signature types
  (critique 4).
- **The arms as two hosts or two processes.** The signing offsets, stagger and loop speed are identical.
- **Size as an EV threshold or as visible depth at the original-size choice** (critique 5).
- **Round-robin or counter-based dispatch.** The gaps are near-geometric, and XM's share is flat across the decision index.
- **Routing by the add / reduce state.** XM carries 7.4% of reducing orders and 5.5% of flat or adding ones.
- **A per-window large budget.** GF and XM are binomial, and DS's overdispersion is pyramiding.
- **A window-level public trigger for DS's large regime.** Spearman of the DS large count with the previous window's realized vol
  is 0.10 and with the window's own realized vol 0.05.

## Proposals (ranked by the chance they close the gap)

The gap is "decoded, but conditions 5 and 7 fail". Proposal 1 closes it either way: it makes the wall statement exact, or it shows
which coin is not random. Proposal 2 is the only route by which the coins could become inputs. Proposal 3 removes failure modes
that belong to the procedure, not to the strategy.

### 1. Settle conditions 5 and 7 as an attainability question: is the operator a draw of its own decoded process? (strong form of X81 / X82 / X134; H181)

**Hypothesis.** After the knee-clock decode, three coins remain: the take among top-hazard instants, the size menu and the carrying
wallet. Together they set the window lean.

- The operator is statistically one draw of the decoded generative process.
- Its window PnL is predictable only up to that process's own reliability: ~0.65-0.70 pooled, ~0.5 for DS and GF, < 0.2-0.43 for XM.
- If instead the operator correlates with the process mean better than the draws do with each other, a coin is not random and an
  input is missing. That tells you where to look.

**Why it fits.**

- Critique 1: the LOO oracle (DS / GF 0.25, XM 0.05), the split-half ceilings, and every public nowcast saturating at window-net
  r ~ 0.51 (nfms14, mix14, nf12b).
- Critique 2: the allocation is near-i.i.d.
- Critique 5: size is a menu coin plus pyramiding.
- X83: the take among top instants follows a constant-hazard thinning.

**Test** (10-20..22; fit days 10-17..19).

1. **Model-free split-half, done properly.**
   - Merge fan-out legs (< 60 ms, same window and outcome) into one decision and assign it to its leader.
   - Compute per-window L_w and corr(L_w, L_rest). Fit the thinning model with decision-variance shares.
   - Report the common-part reliability and the ceilings, pooled and per wallet, with a 2-h block bootstrap and per half.
2. **The decoded-process simulator.**
   - Score every 50-ms bin with `model_it14_hazard_full.txt`, calibrated (isotonic regression on the fit days, undoing the 1%
     negative weights).
   - Draw decisions from it; take the side from dc14 at the bin.
   - Draw the menu from P(large | the draw's own sent net on o, day menu, arm).
   - Draw the wallet from the best P^(wallet | state): the information panel's P2 features plus the leg slot.
   - Resolve fills as in the mechanics panel's P2 (depth-limited, capture book).
   - Generate 200 independent streams.
3. **Three numbers per scope** (pooled, DS, GF, XM; per half):
   - tt = corr(draw_i, draw_j) of the window PnL;
   - corr(operator, mean field), where the mean field is the average of the draws;
   - sqrt(tt).
   - Calibration test: under a correct generative model, corr(operator, mean) ~ sqrt(tt). If it is clearly above sqrt(tt), the
     model's coins are noisier than the operator's (missing input). If it is clearly below, the model is overconfident or
     misspecified.
4. **Ceiling(AUC).** Mix the true wallet label into P^'s logits at graded strengths and recompute XM's perfect-replica redraw
   ceiling. Report the allocation AUC at which it crosses 0.47, next to the best AUC reached with public plus replica-own state.
5. **What to write down.**
   - If step 3 shows the operator ~ a draw, write conditions 5 and 7 as wall components with these numbers.
   - Otherwise, attribute the excess to the coin whose redraw costs most (redraw one coin at a time while the others are held at
     their true values).

**Data.**

- `fills.parquet`, `it14/dcclock14_frame` / `dcfit14_pred` / `hazflow14` (all-bin scores; rescore if they were not kept), the
  capture day files 10-17..22, and `calldata_sample` for menus.
- The fill resolver from the mechanics panel's P2.

**Signature if true** (the coins are random).

- corr(operator, mean field) within +-0.03 of sqrt(tt) in every scope and half.
- sqrt(tt) pooled ~0.6, below 0.5 for XM; the ceiling(AUC) crossing for XM above any attained AUC.
- Conditions 5 and 7 then become measured wall components, with the coin each one is bound by.

**Signature if false.** corr(operator, mean field) > sqrt(tt) + 0.05 in some scope. The coin whose one-at-a-time redraw drives the
gap is the one with a missing input, and that becomes the next iteration's target.

### 2. The coins are Math.random draws: count them between bursts (strong form of X99 / X105)

**Hypothesis.** One Node / V8 (or Bun / JSC) isolate signs every ladder and also draws the trigger-time choices with Math.random.

- The salts reveal the generator state at each burst. In V8, Math.random outputs bits of state0 of xorshift128+, which is
  GF(2)-linear in the state.
- The number of generator steps between two consecutive bursts then counts the random draws the bot made while it traded.
- If that count tracks the operator's decisions, the wallet, size and take coins are draws from that stream and can be
  reconstructed.

**Why it fits.**

- Iteration 1: salt / timestamp is uniform on [0, 1], with a maximum of 1.0.
- One process signs XM -> DS -> GF.
- The loop is monotone in price, 1.66 ms per cent, with copies signed at the same ms.
- Critique 2: the allocation is random-like.
- Only the weakest variant was ever tested (iteration-10 panel, `prng_*.py` in the scratchpad).

**Test.**

1. **Synthetic self-test.** Use V8 xorshift128+ with the 64-entry cache consumed last-in-first-out, the observed ladder layout
   (outcomes x cents x copies x sizes x wallets) and sparse filled positions. Observe only the top 38 bits of r = salt /
   Date.now(), with Date.now() within +-2 ms of the timestamp field. Confirm that 4-8 observed salts per burst recover the state
   with copy offsets enumerated. Do the same for JSC with z3 (`pip install z3-solver` into the venv).
2. **Real bursts.** For each (window, burst) in the calldata sample hours (VALIDATE), place the filled orders by the loop layout,
   solve, and validate by predicting the burst's other filled salts. An exact 38-bit match has chance ~2^-38. If the sample is too
   sparse per burst, fetch the full calldata of the operator's fills for ~20 windows (~3k transactions, batched, polite).
3. **Inter-burst distance.**
   - Step the recovered state forward n = 1..3x10^5 until burst b+1's salts match.
   - Regress n on the operator orders sent in the 131-s interval: taker orders, plus lost-race insertions from the capture's
     book at the operator's sizes.
4. **If n tracks decisions,** reconstruct the draw sequence and test whether "XM", "large" and "take" are thresholds on fixed draw
   slots per decision.
5. **Point in time.** Note when the state becomes public: the first fills of a burst land on-chain ~2 s after their match.

**Data.** `calldata_sample.parquet` (salt, sign_ms, maker, token, amounts), Polygon RPC for more transactions, the capture for sent
counts, numpy (GF(2) elimination) and z3.

**Signature if true.**

- At least 90% of tested bursts solve, with exact predictions of held-out salts.
- n correlates >= 0.9 with the sent-order count across >= 30 burst pairs.
- The reconstructed draws separate the XM and large choices at AUC >= 0.95.
- Conditions 5 and 7 are then open again, on an input that is public in principle.

**If false.** No consistent state under V8 or JSC with the layout and the +-2-ms tolerance in >= 20 bursts. The salts then do not
come from a recoverable stream (crypto RNG, several isolates or another runtime), the coins are unobservable, and that sentence
closes X99 / X105 in the wall account.

### 3. Run the examiner's procedure on a development pseudo-lot before the next claim (new)

**Hypothesis.** The VALIDATE numbers are offline frames computed by the investigator. The exam is evaluate() in a fresh process,
with the examiner's choices:

- labels from block timestamps or from capture ms;
- its own baseline fitted on BUILD;
- halves split on listing metadata;
- per-wallet replication;
- 2-h block CIs and nulls at alpha 0.0025.

Some conditions may fail through the procedure rather than through the strategy. Examples: the capture's hour-23 rollover, the
2.7% of transactions without a capture match, a menu change inside the lot, a pause or a post-only restart, a weekend day.

**Why it fits.**

- evaluate() has been checked end to end on single hours only.
- Critique 7: the label clock, the BUILD clause, the menu changes, Sunday 10-25, the 10-29 pause, XM's side halves.
- Finding 5: the presence result already flipped once with the baseline.

**Test.**

1. **Build a pseudo-lot from development units shaped like h1.** For example 10-16, 10-18, 10-20, 10-22 against 10-17, 10-19,
   10-21. It holds a weekend, three size menus (50 / 30 / 200, 50 / 30, 30 / 100) and the 10-21 dispatch phase. Split it into
   halves on listing metadata.
2. **Run evaluate()** in a clean process: no scratchpad frames, ALLOW_SEALED False, intervals given.
3. **Compute every condition 1-7 per wallet and per half,** with the 2-h block CIs and 2,000-draw nulls, under:
   - (a) capture-ms labels and block-ts labels;
   - (b) a baseline fitted on BUILD 10-09..16 (block clock) and one fitted on the capture fit days.
4. **Operational stress.** Replay one hour with the market's trades removed (a synthetic pause) and two minutes with taker prints
   removed (post-only). Check that presence, the tracker and the side gate on "market accepts takers".
5. **Write the pre-registration** of the label clock and the fit set from the result.

**Data.** Development days only, `final_rule.evaluate()`, the capture day files 10-17..22, the BUILD archives.

**Signature if true.** At least one condition fails mechanically: the label clock, the coverage of hours 23 and 0, a pooled Pearson
across menus, or XM's side per decision in a half. A fix found now saves an exam round.

**If false.** Every condition reproduces the offline VALIDATE numbers within 0.01. The claim then rests on the strategy alone.

## Sources

`NOTES.md` iterations 1-14; `state.json` (catalog X1-X138, hypotheses H1-H196, components); `FINAL_RULE.md`; `panels/iter13_*.md`,
`panels/iter14_information.md` and `panels/iter14_mechanics.md` (titles and the overlapping proposals only); `code/thin14.py`,
`results/thin14.json`.
