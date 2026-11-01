# Panel after iteration 13: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 13 the working assumptions are:
- R8 should be tuned to the historical VALIDATE (10-27..30, Tuesday to Friday) and to the weekday US-session BTC 5m 500
  ladder, and the next exam will look like that;
- 10-s fill presence on BTC 5m is still the primary target, even though iteration 8 showed that the cluster's own quote,
  used as an oracle, caps it at about 0.80;
- the 27% of fills on resting rungs ("class ii") are the takers' choice and cannot be predicted;
- the September configuration earned its money through the cluster's own decisions, and only makers have been checked as
  the counterparties that changed.

Written 2026-11-01, 05:05-06:00 UTC.

**Data used.** Development data only. `tools/sealed.py directional-maker`: released h1 and h2; development
[10-23, 10-31 06:00) and [10-31 12:00, 18:00); sealed [10-31 06:00, 12:00) and [10-31 18:00, now).
- `.cache/re/directional-maker/it13/` `sched_adds`, `fills_posts` and `trades` (the RE's tables for 10-31 14-18,
  development).
- `calldata/allmatch1793460000_*` (10-31 15:20-15:40, development).
- Activity of the three wallets in `activity_*.parquet` and `exam/activity_*.parquet`. I used only windows that end
  before 10-27 00:00 (BUILD plus STUDY).
- No network fetches. Nothing from `.cache/live/sealed/`. No VALIDATE case-level data.

**Scripts.** All in the scratchpad folder
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`.
Run them from the repo root with `.venv/Scripts/python.exe -I`:
- `trip.py` and `trip2.py`: multi-wallet synchronized posts;
- `repl.py`: whether posts follow the wallet's own fills;
- `chk3.py`: pre-open fills, and BTC 15m quote traffic at the 16:53:54 switch-off;
- `ties.py`: ties in print selection;
- `nest.py`: hedging between nested 5m and 15m windows.

These are small exploratory checks. All but the first come out negative. I report them so that nobody spends time on
them again.

## Quick checks (all development data)

**N1. No hedging between nested windows.** I paired each BTC 15m window with the 5m window that ends at the same second
(same settlement value). That gives 790 pairs over 10-08..26. Cluster net Up shares correlate +0.07 between the two
windows (Spearman +0.10), and per-window PnL correlates +0.01. Var(PnL_15m + PnL_5m) / (var 15m + var 5m) is 1.01.
- The first and second 5m windows of each period give the same numbers (+0.08 / +0.02 and +0.07 / +0.02).
- The 5m and 15m books are run as independent inventories. No PnL hides in cross-horizon locks, so the per-window
  outcome metric is not mis-specified on this count.

**N2. No sign of a fixed signing budget being redistributed.** At the 10-31 16:53:54 BTC 5m switch-off, exact-500 adds
within 0.20 of the touch changed as follows:
- BTC 5m: 150-193 per minute before, 5-6 per minute after;
- BTC 15m: 219 per minute in the half hour before, 294 in the half hour after, but 305 in the half hour before that (the
  rate follows the 15m window's phase).

Two other facts argue against a budget shared at a fixed rate:
- the wallets' signing rates rose after the switch (X82);
- BTC 5m's 500 traffic is only about 3 of the cluster's roughly 40 signatures per second.

**N3. The posts behind fills are not a separate process.** Synchronized multi-wallet posts (three exact-500 adds at one
price within 30 ms) make up 19% of the 44,128 near-touch 500 post events, and 15% of the filled orders' posts.
- Posts that come within 300 ms after the same wallet's own fill on that outcome are 10% of filled posts (class i 13%,
  class ii 2%).
- So the fill-generating quotes are ordinary re-signs, not a replenish loop and not the synchronized pass.

**N4. No pre-open fills.** All 1,406 filled orders of 10-31 14-18 lie inside their window; 0.5% of schedule adds are
before the open. The presence panel's [0, 300) range loses nothing.

**N5. Ties do not cap the selection AUC.** In the 20-minute all-match sample, 14% of the cluster's maker BUY rows share
(transaction, token, price) with another maker. But only 1.2% of the (cluster, other) comparison pairs in within-window
strata are such ties, so the tie ceiling is 0.994.

## Critique

1. **The final exam lot is already fixed. It is a weekend lot, and R8 is a weekday rule.**
   - The budget has about 312 minutes left (888 of 1,200 used), so it runs out around 11-01 10:00-11:00 UTC. At that
     point the examiner takes every sealed future block that has ended since 10-31 00:00:
     - 10-31 06-12 (Saturday 02-08 ET);
     - 10-31 18-24 (Saturday 14-20 ET);
     - 11-01 00-06 (Saturday 20:00 to Sunday 02:00 ET).
   - None of these resembles VALIDATE (10-27..30, Tuesday to Friday).
   - In these blocks:
     - BTC 5m was switched off at 16:53:54 on Saturday 10-31, and its off-runs start on Friday to Sunday evenings ET;
     - R6/R8's universe held at least 80% of trades and dollars in 0% of the weekend 00/06 development blocks
       (iteration 9);
     - the off-session 62/250 ladder carries no Chainlink skew where the report and the market disagree (region D
       0.51-0.52).
   - No own recorder ran in 10-31 06-12. Rawrec started at 14:04, examrec at 15:53 (it died at 16:53 and was back at
     17:41), dy_rtds at 17:29, dz_rtdsbn at 19:13, dw_clob at 22:59. The post-time posture, the tracers and the quote
     unit therefore cannot be examined in a third of the lot.
   - The iteration-14 plan does not address this:
     - X145 schedules a recorder for 11-01 18-24 and 11-02 00-06, which are after the budget ends;
     - the per-family universe (X83, open since iteration 8) is still unbuilt.
   - The one weekend-type development block scored (10-31 00-06) points the other way from R8's emphasis:
     - BTC 5m: presence gain -0.016, side 0.605;
     - BTC 15m: presence 0.853 vs 0.815, side 0.914, PnL proxy 0.73 / 0.68.
2. **The primary metric is a unit the target cannot be met on.**
   - 10-s fill presence is capped at about 0.80 even with the cluster's real quote (X72). Yet it is still the primary
     metric and the quantity reported every iteration.
   - The brief's condition is "presence >= 0.85 *or* selection >= 0.80 with recall >= 50% at lift >= 3".
   - At the print level the quote binds, and the bar is within reach:
     - with the quote oracle: 0.814, recall 62% at lift 3.32;
     - live public score: 0.764, recall 44% at lift 2.68.
   - The only explicit quote-law print score ever tried (X31) predates everything iteration 13 learned:
     - it used a center-skew law and a 2-s report lag, and scored 0.657;
     - the touch join on the posture side, the deep 2 c rungs on both outcomes and the 1.25 s lag were not yet known.
   - Iteration 14 does not plan any work on selection.
3. **"Class (ii) is the takers' choice" is an argument, not a measurement.**
   - Iteration 13 showed that the 27% of fills on resting rungs about 2 c below the touch are at chance on the
     posture. It also showed that the book at the post leans the right way (0.717).
   - Nobody has tested whether these fills come at Binance moves faster than the cluster's own 50-250 ms futures
     requote (X10). The tests so far were:
     - X110: window net side on the block clock;
     - X96: Chainlink at the taker's signing time;
     - X132 (open): burst starts on the lot.
   - On the live match clock the per-fill side already clears 0.80 in the pre-registered half (0.836-0.841). The
     whole-block number (0.786) and the bad half hour (0.45) come from volatility bursts, where "the fills land on the
     favourite's 500s". That is the class-(ii) mechanism.
4. **Where the money came from is still measured on one side of the trade only.**
   - The most profitable version (09-11..25, +9.3% per dollar) took the cheaper token (0.71 per fill), which is a
     market-only baseline. The posture-following October version earned +0.6% before rebates.
   - X141 measured who entered as maker (17 entrants, no window-level markout effect).
   - Nobody has measured who stopped paying as taker across the same boundary. Iteration-12 P2 step 4 was never run,
     and X66 / X104 sit inside October. "Why it works" for the version that passed the significance screen is
     therefore unknown.
5. **The side is measured on a different unit from the examiner's.** Round 1 scored the side on one-sided 10-s fill
   bins (8,605 bins). target_metrics reports it per fill. On a lot with same-side runs and sweeps the two can differ by
   several points, so report both.

## Proposals (ranked by the chance they close the gap)

### P1. Freeze the rule for the lot the examiner will actually use: three weekend blocks, scored on weekend development analogs with only the inputs that exist in those blocks (strong form of X83, X112 and X101; new: the lot is fixed by the calendar and the budget)

- **Hypothesis.** The decision process the examiner sees in 10-31 06-12, 10-31 18-24 and 11-01 00-06 is the weekend
  configuration:
  - BTC 5m mostly off;
  - 62/250 rungs;
  - BTC 15m and the other families carrying the fills.

  On that version a family-general rule could meet scope, and it may be more decodable than the weekday BTC 5m engine
  (BTC 15m in 10-31 00-06: presence 0.853, side 0.914). R8 fails scope there for certain.
- **Why it fits.**
  - Scope of U1 is 0.00 in weekend 00/06 blocks (code9/scope.py). Adding ETH gives 0.89, and all families give 1.00.
  - The 16:53:54 switch-off.
  - The calendar gate (Friday to Sunday ET evenings).
  - The region-D numbers of the 62/250 ladder.
  - The recorder start times in `state.json` `live_lab`.
  - `sealed.py`: future examined only until 10-31 00:00.
- **Test.**
  1. Pre-register the analogs before reading them, by weekday and block:
     - Saturday 06-12: 10-24, 10-17, 10-10;
     - Saturday 18-24: 10-24, 10-17, 10-10, and 10-31 16:54-18:00 as the live piece;
     - Saturday-Sunday 00-06: 10-25, 10-18, 10-11, and 10-31 00-06;
     - plus the full-depth Sunday block 11-01 06-12 when it ends.
  2. For each analog, compute:
     - the share of fills and of |PnL| per family (every crypto Up/Down family, from activity);
     - the BTC 5m / 15m module state;
     - the size class.
  3. Run `evaluate()` for R8, and for a family-general R9 (the R3 class per family plus the calendar gate, frozen
     before the scoring). Restrict each block's inputs to what exists in its sealed twin:
     - 06-12: shared recorder, in-block clock and public archives only;
     - 18-24: also dx/dy (and dz from 19:13);
     - 00-06: also dw and dv.
  4. Report scope, presence and selection, the side (per fill and per one-sided 10-s fill bin), price and the
     strict-replay outcome per analog and per wallet.
  5. From listings only (allowed for sealed units through the projection), compute the families and windows listed in
     the three sealed blocks, so that the frozen universe matches the lot.
- **Data.** Activity (on disk), tapes and in-block calldata for the analog days (BUILD tapes partly on disk, the rest
  cached), the shared recorder for 10-31, and the 11-01 06-12 recordings.
- **Signature if true.**
  - R8's scope is below 0.80 in at least two of the three analog types.
  - An R9 universe meets 0.80 / 0.80 in every analog.
  - At least one family block in R9 (BTC 15m, ETH 15m) carries presence or selection near the bar.
  - Then R9 replaces R8 as the frozen claim, and the remaining iterations are spent on its weakest family.
- **If false.** R8's universe covers the weekend analogs (BTC 5m on in the mornings). Then the weekday rule is the right
  object, and the work shifts to P2 and P3.

### P2. Claim through print-level selection, scored with the decoded quote geometry instead of a presence-model output (strong form of X31 and X102; the weak form was a center-skew law with a 2-s lag, 0.657)

- **Hypothesis.** A print is the cluster's when the decoded quote stands at its price. That means one of two things:
  - the top rung joins the touch of the posture outcome (posture at t - 1.25 s, class i, 73% of fills);
  - or a deep rung about 2 c below the touch, on either outcome, is swept (class ii, 27%).

  A fixed score built from these two bands, plus the in-block or match-clock anchor (the last clean trade before the
  print), reaches the selection bar. The fill-presence ceiling does not apply to this unit.
- **Why it fits.**
  - The X72 ceiling: with the oracle, 0.814, recall 62% at lift 3.32. Public 0.686, and 0.764 / 44% / 2.68 with the
    1.43-s report.
  - The oracle in X72 included only "cluster-class 500 at the touch". The deep band (27% of fills) lies outside it, so
    both the oracle and the public score are under-measured.
  - The iteration-13 class split and the 1.25-s tracer lag.
  - R7: fills sit at the last clean trade - 0.01, 0.80 within a tick.
  - N5: ties do not cap the AUC.
- **Test.**
  1. Unit: maker BUY prints of BTC 5m and 15m (other families where dw_clob and dv_rtds exist), with their match ms
     from the shared recorder, or the in-block execution order on the lot.
  2. Score, written down before scoring:
     - s = 1[token = Chainlink posture side at t - 1.25 s] for d in {0, 1};
     - s = c for d in {2, 3};
     - s = 0 otherwise;
     - here d = (last clean trade on the token before the print's transaction - print price) in ticks, and c is the
       only fitted constant (FIT 10-31 12:00-15:00).
  3. Score it with `match_test`: global and within-window strata, rotation null with 2,000 draws, θ fitted on FIT,
     recall and lift on TEST (10-31 15:00-18:00), then out of sample on 11-01 06-12, and on the lot where X102's grid
     has the report.
  4. Compare with:
     - the activity-only LightGBM (examiner style, plus book state);
     - R2's print score;
     - an extended oracle: the cluster's identified orders at the print price, any rung.
  5. Run a 2-h block bootstrap of the gain, per wallet and per half.
- **Data.** The shared recorder (trades with server ms, books, rtds), dy_rtds, dm_clob_raw for the oracle labels, the
  in-block calldata on the lot, and X102's Chainlink grid.
- **Signature if true.**
  - Stratified AUC >= 0.80, recall >= 50% at lift >= 3, gain >= 0.05 over the stronger activity baseline with a
    bootstrap lower bound > 0, on TEST and on 11-01 06-12;
  - the extended oracle >= 0.85.
  - Then make selection the claimed condition in `state.json` and report fill presence only.
- **If false.**
  - Public score <= 0.77 while the extended oracle is >= 0.85: the missing piece is the queue at the touch. Measure it
    from dm_clob_raw as the share of posture-side touch prints where the size ahead of the cluster exceeded the print.
    That is the quantitative account of the gap.
  - The extended oracle is also < 0.82: the selection route is closed on this unit too. Say so in FINAL_RULE.

### P3. Class-(ii) fills are Binance pick-offs of the deep ladder: a public two-regime side rule at the match millisecond (strong form of X110, X96 and X132; never tested per fill on the exact clock)

- **Hypothesis.** Takers who react to Binance USD-M moves faster than the cluster's 50-250 ms futures requote sweep its
  resting rungs about 2 c below the touch. The bought outcome is the one the move went against.
  - A public rule follows: if a futures move of at least θ dollars occurred in [match - Δ, match), the side is the
    outcome the move went against; otherwise it is the Chainlink posture.
  - This rule would fix the volatility-burst windows and the bad half hour (0.45).
- **Why it fits.**
  - Class (ii) is at chance on the posture (0.507).
  - The pre-post book leans to the swept outcome (microprice coefficient negative, 0.717).
  - The cluster itself re-quotes 50-250 ms after futures moves (91%; X10).
  - "Whole windows fail in volatility bursts" (FINAL_RULE).
  - Mo-money's swept anti-posture 500s.
  - The match-clock posture scores 0.84 instead of 0.81 partly because the mid at the match already contains the move.
- **Test.**
  1. Sample: the 355 class-(ii) and 942 class-(i) fills of 10-31 14-18 (`fills_posts`).
  2. Inputs:
     - Binance USD-M aggTrades in ms (the 10-31 archive, or the recorded dm_bnfa / dx_bnfa);
     - the RTDS Binance relay (dz_rtdsbn).
  3. For Δ in {100, 250, 500, 1,000, 2,000} ms, compute the signed move and the change in the Binance digital, and
     score "against the move" on class (ii) and class (i).
  4. From the calldata, take the takers' signing ms relative to the move.
  5. Fit θ and Δ on 14-16 and test on 16-18. Then apply the frozen two-regime rule to every fill on the match clock
     (no class labels) on 10-31 12-18 and 11-01 06-12, per wallet and per half.
  6. Baseline: market-only, including tape momentum and the ex-own book lean (X144).
- **Data.** On disk, plus the 10-31 futures archive (about 20-60 MB, reduced at once).
- **Signature if true.**
  - Class (ii) scores >= 0.75 against the move for some Δ <= 500 ms, with taker signatures 0-300 ms after the move.
  - The two-regime rule gives >= 0.80 per fill on the whole 10-31 12-18 block and in both halves, and lifts the burst
    half hour.
- **If false.** Class (ii) is at chance on Binance too. The resting rungs are then swept by uninformed demand (the mint
  takers), and the side residual of about 27% x 0.5 is irreducible by any reference feed. That is a quantitative account
  of the unexplained part, and should be stated as such.

### P4. Who paid the profitable version: taker populations across the September -> October boundary (strong form of iteration-12 P2 step 4, X66 and X104; the taker side was never run)

- **Hypothesis.** The September return (+9.3% / +7.4% per dollar, cheaper token 0.71) came from a specific taker
  population, and its share fell in October as the return went to +0.6%. Candidates:
  - round-USD UI takers buying favourites through mints;
  - a few large favourite buyers.

  The decision that mattered was being on the opposite side of that flow. The posture skew, measured as the side
  component, is a later configuration.
- **Why it fits.**
  - Iteration-12 F2: the return comes from fill price vs outcome in every bucket, while the net side wins only
    0.45-0.56.
  - X66: round-USD takers carried 107% of the cluster's PnL on the lot.
  - 81-88% of the fills are mints.
  - X141: 17 entrant makers took about 15% of maker volume, but this does not explain the window markouts.
- **Test.**
  1. Re-fetch the pre-registered stable sample taker tapes (`code13/fetch_stable.py`, about 12 min, cached) plus the
     October control.
  2. Join each cluster maker fill to its taker row (same transaction).
  3. Classify the takers:
     - round-USD notional;
     - high-frequency (from a calldata sample: signing within 300 ms of a futures move);
     - the top-20 September counterparties;
     - the rest.
  4. By week 09-11..10-22: each population's share of the cluster's fills and held-to-resolution PnL, its BTC 5m
     market-wide volume, and the cluster's markout against it.
- **Data.** Cached data-api tapes, activity on disk, and a few hundred calldata transactions per week.
- **Signature if true.**
  - One population supplies >= 60% of the September PnL.
  - Its volume (or its share of the cluster's fills) falls >= 50% by October.
  - The cluster's weekly return tracks it (Spearman >= 0.7 over the 6 weeks).
  - "Why it works" is then that flow. The rule's presence and selection inputs should then use that population's
    footprint (hour of day and session as seen in the public tape), with the co-occurrence caveat stated.
- **If false.** The counterparties are stable across the boundary. The fall in return is then the cluster's own
  reconfiguration plus the entrant makers. The side should be stated as a configuration by-product, with no
  counterparty account to add.

## Notes for the RE

- Do the P1 bookkeeping first, because it is cheap and it decides what the frozen rule must be. The final exam lot is
  determined now. A rule frozen for weekday BTC 5m will fail scope whatever its AUC.
- Report the side on the examiner's round-1 unit (one-sided 10-s fill bins) next to the per-fill number.
- X145's recorder for 11-01 18-24 and 11-02 00-06 lies after the budget ends. Spend the effort on the 11-01 06-12
  block and on the recording-free path for 10-31 06-12-type blocks instead.
- N1-N5 close five tempting side roads: cross-horizon hedges, a fixed signing budget, separate fill-generating
  processes, pre-open fills and tie ceilings. Record them in the ledger so they are not re-proposed.
