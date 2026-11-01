# Panel after iteration 11: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 11 the main assumptions are:
- the posture's volatility multiplier k is an engine parameter that follows a weekly cycle;
- a change in the cluster's fill side, with the same takers and flat market demand, must be a change in its quote;
- "the outcome bar sits at the ceiling of a perfect window side" is a property of the strategy;
- the per-fill side, pooled over the three wallets, is the right unit for the side decision.

Written 2026-11-01, about 01:30-02:20 UTC.

**Data used.** Development data only. `tools/sealed.py directional-maker` gives released h1 and h2; development
[10-23, 10-31 06:00) and [10-31 12:00, 18:00); the current block is sealed. I read the RE's own tables:
- `it9/volhist_{build,study,validate}.parquet` (BTC 5m maker fills with the Binance stand-in);
- `results/iter11_k_by_day.json` and `results/iter11_k_by_day_binance.json`;
- `exam/fills_holdout.parquet`, `exam/windows_5m.parquet`, `exam/taker5m_day_*.parquet`;
- `activity_*.parquet` (BUILD) and `exam/activity_*.parquet` (lot).

What I read and did not read:
- VALIDATE (10-27..30) only as per-day or per-half aggregates.
- Nothing from 10-31 06-12, nothing after 10-31 18:00, nothing from `.cache/live/sealed/`.
- One network pilot: data-api `/trades` (full tape with maker rows) for 37 BTC 5m windows of 10-09..30 starting at
  14:00 and 15:00 UTC, through `PolymarketData().market_trades` (cached).

**Scripts.** All in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p11\`;
run them from the repo root with `.venv/Scripts/python.exe -I`:
- `edge_split.py`, `ext_split.py`, `zero_z.py`: the favourite-share drift by edge, extremeness, displacement and time left;
- `locked.py`: per-window locked/residual PnL split and its public correlates;
- `calib.py`, `load.py`: two candidate drivers;
- `makers_pilot.py` and its output `makers_pilot.parquet`: the maker-row pilot.

**Multiple-testing warning.** I scanned buckets and lags on aggregates. Treat every number below as exploratory.

## What my checks found

**F1. "Best k" is the favourite share under another name.**
- Per day, the best k on the grid and the favourite share of the fills (fill price > 0.5) have Spearman:
  - **-0.88** with the Binance stand-in (22 days, 10-09..30, the RE's `iter11_k_by_day_binance.json`);
  - **-0.93** with the real Chainlink (8 lot days);
  - -0.75 over 26 lot 6-h blocks with n >= 150 (`iter11_k_by_day.json`).
- Accuracy at the per-day best k is only 0.55-0.72 (stand-in) and 0.61-0.76 (Chainlink).
- So even a perfect per-day oracle for k leaves the per-fill side well short of 0.80. The cycle is real as a
  favourite-share cycle. As a description of the side rule it is worth about +0.05 at most (pooled k 0.61, per-day best
  0.55-0.72).

**F2. The drift shows up where a sigma multiplier has no leverage.**
- **By edge.** Edge e = fair - mid at the market's own multiplier k_m = 1.15, so the split does not depend on the
  cluster's k. The daily favourite share drifts the same way in every |e| bucket:

  | \|e\| bucket | <= 0.02 | 0.02-0.05 | 0.05-0.10 | > 0.10 |
  | --- | --- | --- | --- | --- |
  | sd across days | 0.15 | 0.13 | 0.11 | 0.12 |
  | range | 0.20-0.68 | 0.21-0.65 | 0.27-0.64 | 0.33-0.76 |

  Accuracy at k_m is 0.41-0.74 in every bucket.
- **By market price and time left.** The drift is the same at every market price level (0.50-0.58 up to 0.85-1.0)
  and in every time-left bucket.
- **The k-invariant cell.** Take |z| < 0.05, with z = ln(S/K) / (v300 sqrt(tau)), and the market at >= 0.53. There
  every k on the grid gives a fair within ~0.04 of 0.5, so the posture says "buy the cheaper token":
  - it names the favourite 0-4% of the time at k 0.5 (10-27: 16%) and 0% at k 2.5;
  - the cluster bought the favourite **0.07-0.64 by day (sd 0.16 over days with n >= 40)**: Mondays 10-12 and 10-19
    0.08-0.11, but 10-14 0.64, 10-16 0.54, 10-11 0.50, 10-23 0.45.
  - Caveat: this is the Binance stand-in. With Chainlink, part of this cell is region D.
- **The last minute has its own regime.** The favourite share of fills with < 60 s left is:
  - 0.20-0.32 on 10-09..13;
  - 0.56-0.85 on 10-14..27;
  - 0.25-0.30 on 10-28..30.

  The steps fall on Wednesdays (10-14, 10-28), not on Mondays. At least two components with different change points
  are pooled in the "weekly cycle": the main ladder and the last-minute or TWAP lock-in behaviour of A1_B3b.
- So what varies is a tilt toward or away from the favourite that does not depend on the reference's displacement. A
  change in sigma cannot produce it.

**F3. On VALIDATE the locked pairs carry all the profit and most of the outcome correlation.**
- Per window of the lot: the cluster's maker BUY fills held to resolution, split into locked pairs, min(Up, Down) x
  (1 - average Up price - average Down price), and the directional residual.

| half | windows | window PnL | locked | residual | corr(PnL, locked) P / S | corr(PnL, residual) P / S |
| --- | --- | --- | --- | --- | --- | --- |
| STUDY | 583 | +$4.8k | +$0.3k | +$4.5k | 0.58 / 0.47 | 0.89 / 0.85 |
| VALIDATE (aggregate) | 1,089 | +$23.7k | **+$38.1k** | **-$14.4k** | **0.67 / 0.63** | 0.80 / 0.72 |

- My split uses maker BUY fills only, so it differs from the RE's iteration-10 numbers (+$33.3k / -$10.3k, which
  include taker pairing buys).
- Paired shares per window rank with the window's clean taker volume (Spearman 0.39-0.41) and weakly with its Up-price
  range (0.19-0.24). The locked PnL itself is not predicted by the range (-0.08 / +0.13).
- `code11/replay.py` and the oracle replay have no pairing bids, no adds to the held outcome and no merges.

**F4. Three driver candidates for the cycle, checked and not supported.**
- **Capital: the cash path contradicts it.** In week 2 (10-19..25) the cluster made little profit. Two wallets had no
  sweep on 10-26, so cash stayed near the ~$22k target, yet the favourite share rose to 0.59-0.61 by Thu-Fri. In week 3
  cash grew to $43-49k and the favourite share fell to 0.26. A binding cost of favourite bids predicts the opposite
  (iteration-9 assumptions panel F2 cash path).
- **Engine load.** The markets or families traded per day against the BTC 5m favourite share give Spearman -0.15 /
  +0.10 (22 days). Notional gives -0.07.
- **An online outcome calibration.** Favourite over-performance (realised win minus price) in the trailing blocks
  against the cluster's favourite share:
  - Spearman -0.01 (previous block), -0.11 (4 blocks), -0.34 (12 blocks);
  - per day -0.57 (trailing 3 days, n 19).

  If anything this is the opposite sign to an adaptive learner. It is autocorrelated and exploratory.

**F5. Pilot: the full tape carries every maker, so the competition is measurable.**
- Scope: 37 windows; about 6 s per window with the polite client.
- Maker BUY volume is dispersed: about 280-560 maker wallets per day in two windows. The top maker has 3.4% and the
  top-10 20.8%. The cluster has 2.3%.
- The market-wide maker favourite share is 0.51 / 0.52 / 0.55 (BUILD / STUDY / VALIDATE aggregate).
- One wallet (0xee65685d...) bought only favourites on STUDY and VALIDATE, and its share of maker volume doubled
  (2.6% -> 5.2%).
- The pilot is far too small for the cluster's own numbers: its favourite share in the 8 STUDY windows was 0.03,
  against the RE's 0.45-0.59 over all STUDY fills. It shows feasibility, not a result.

## Critique

1. **The weekly k cycle is a relabelled favourite share, and calling it an engine sigma multiplier is not earned (F1,
   F2).**
   - The tilt appears with the same size where k cannot change the side: the k-invariant cell, every edge bucket, every
     time-left bucket.
   - The iteration-12 plan follows from the sigma reading:
     - the driver search for a sigma (running vol, PnL since Monday, collateral);
     - the "version-aware" refit of presence and selection per k state;
     - the pre-registered "k 1.4 vs 2.0" check for 11-01 06-12.

     That reading may be chasing a parameter that does not exist.
   - Even a perfect per-day k caps the per-fill side at about 0.72-0.76. The k story cannot close the side gap, so it
     should not get the next iteration's budget unless F2 is refuted with the real Chainlink.
2. **"Same takers, flat market demand, so the change is in the cluster's quote" leaves out the other makers.**
   - The market's favourite-side maker volume is fixed by taker demand. When the cluster's slice moves, someone else's
     slice moves the other way. That is an identity.
   - Whether the cluster pulled back or was crowded out has never been measured historically:
     - X24 has been open since iteration 4;
     - X39 was only checked live, for one switch-off.
   - The cluster is about 2% of maker volume. Its fill composition is a thin slice of a crowded queue, and very
     sensitive to who else sits at each outcome's touch.
3. **The outcome ceiling belongs to the replay, not to the strategy (F3).**
   - The iteration-11 replay quotes one side all window. The cluster's decoded machine has entry, adds to the held
     outcome, imbalance pairing bids and merges.
   - On VALIDATE the locked pairs hold all of the profit and 0.63-0.67 of the window-PnL correlation.
   - "The outcome bar sits at the ceiling of a perfect window side" should read "at the ceiling of a one-sided replay".
     It becomes a statement about the strategy only once the exit is in the replay.
4. **The entry side works on two horizons (hypothesis from F3).**
   - A pair locks below 1 when the price moves toward the entry side before the pairing bid fills. The residual pays at
     resolution.
   - On VALIDATE the entries were right over the short horizon (+$38k locked) and the residuals wrong at resolution
     (-$14k).
   - The posture is scored against the window's net side and resolution through a level comparison (fair vs mid).
     Economically, the entry looks like a short-horizon bet whose residual is adversely selected at the end. Which
     horizon the side rule is judged on changes which fair fits.
5. **The side unit pools decisions.**
   - Per fill, over three wallets, one quote counts up to three times: 94.8% of multi-wallet cells buy the same side.
   - A taker sweep counts several rungs.
   - Burst windows, where "whole windows fail", therefore dominate the per-fill number. The per-decision unit (taker
     event or re-price pass, wallets de-duplicated) and the window entry exist live (`it9_taker_events`). They should be
     the historical side units too (D1).

## Proposals (ranked by the chance they close the gap)

### P1. Replay the whole decoded state machine, exit included (strong form of X106 / X64; the outcome target's definition)

- **Hypothesis.** The per-window outcome bar is bound by a one-sided replay, not by the strategy. The full machine is:
  - entry on the posture;
  - schedule rungs on the held outcome;
  - imbalance pairing bids of exactly |Up - Down| on the under-held outcome at the R7 price;
  - a merge about 65 s before the end.

  This machine reproduces the locked-pair component, which on VALIDATE carries all the profit and 0.63-0.67 of the
  window-PnL correlation.
- **Why it fits.**
  - F3.
  - The pairing class is decoded: X92 (under-held 1.000, 11-14% of fills, priced at the market, not off its own cost).
  - The replay code has no pairing leg.
  - The examiner scores the executable rule's realised PnL. Leaving a decoded component out of the executable rule
    under-states the rule.
- **Test.**
  1. Extend `code11/replay_frozen.py` with a pairing leg.
     - State: the replay's own Up and Down shares.
     - While unbalanced, bid the imbalance on the under-held outcome at last clean print - 0.01 (dynamic tick).
     - Strict fills: trade-through, latency 2 s, slack 2, on the same flow.
     - Merge pairs at end - 65 s (cash-neutral; held to resolution otherwise).
  2. Pre-register the configuration on STUDY, case by case.
  3. Score on VALIDATE (aggregate) per window:
     - the total PnL corr, Pearson and Spearman;
     - corr(replay locked, cluster locked) and corr(replay residual, cluster residual) separately;
     - each with the posture entry and with the oracle entry;
     - on the 2-s clock and on the execution-order clock.
  4. Report the replay's return under strict fills against the cluster's.
- **Data.** On disk: the it11 tables, `exam/` tapes, windows and fills, `inblock_blocks_all.parquet`.
- **Signature if true.**
  - The oracle-entry ceiling rises from 0.47 / 0.53 to >= 0.6.
  - The posture-entry replay rises from 0.21 / 0.22 to >= 0.35.
  - The locked-part correlation is >= 0.5, and the replay's locked PnL is positive on VALIDATE as the cluster's is.
- **If false.** The ceiling statement then holds for the full machine. That is a much stronger quantitative account of
  the unexplained outcome than the one-sided version.

### P2. The posture is a band, not a sign: two-sided quoting inside |edge| < h, the taker's choice inside the band (strong form of X20 / X30 / X85; replaces the "k cycle")

- **Hypothesis.**
  - The engine bids an outcome when fair minus its own bid exceeds a threshold. Its bids sit about h below the mid on
    each side (top 500-rung pair sum 0.88, h* 0.06, X30), so both outcomes are bid while |fair - mid| < h.
  - Inside the band the fill side belongs to the takers, and to the competitors (P3). Outside the band the posture
    holds: region D 500s 0.93.
  - What varies by day is the share of fills inside the band and the takers' mix there, and possibly h itself, not
    sigma.
  - For print-level selection the same model is a quote predictor: on the posture token only outside the band, on both
    tokens inside it, at last print - 0.01.
- **Why it fits.**
  - F2: the tilt is present at |e| near 0 and in every bucket.
  - The live posture accuracy rises with |edge|: 0.37-0.60 below 3 c, 0.84-0.86 above 10 c (iteration-9 assumptions
    panel F1).
  - A sixth of the live fills had cluster-class touches on both outcomes ("the taker chooses", 0.83).
  - Small-edge fills follow the previous event (0.91), not the edge (0.45).
  - Window entries are 0.82 where the posture and the taker-flow complement agree (iteration 11).
- **Test.**
  1. **Quote level, live** (dx_clob 10-31 15:57-18:00, dm_clob_raw 14:04-18:00; then 11-01 06-12 and dw_clob once those
     blocks are development).
     - Per second: does the cluster have a 500/100 at or within a tick of the best bid on both outcomes, or on one?
     - Fit P(one-sided | |e|), with e = the Chainlink fair at the frozen k minus the mid, and read h as the |e| where
       one-sided reaches 50%.
     - Check h's stability across blocks and wallets.
  2. **Lot (real Chainlink, T_hat clock), a two-regime per-fill side frozen from STUDY.**
     - |e| > h: the posture.
     - |e| <= h: the market-only taker-flow complement (Q of `code11/entry_flow.py`, 30 s), or the cheaper side.
     - Score on VALIDATE per fill and per taker event against the frozen 0.710, per day.
     - Report the daily share of fills inside the band against the daily favourite share.
  3. **k-invariant check on the lot.** In region D and in the near-zero-z cell, does the posture's accordance co-move
     with the fitted best k? If it does, what cycles is how often the cluster leaves the band, not sigma.
  4. **Selection.** Score print-level selection with the band quote predictor as the score (the live blocks now; the
     lot with X102's Chainlink seconds), against the activity baseline.
- **Data.** Own recorders (dx_clob, dm_clob_raw, dw_clob), lot calldata and T_hat, the cached Chainlink seconds, the
  clean tape.
- **Signature if true.**
  - One-sided seconds rise steeply around |e| of about 0.05-0.07.
  - Fills outside the band follow the posture >= 0.85 on every day, with no weekly drift.
  - Fills inside the band follow the taker flow >= 0.6.
  - The daily favourite share is explained by the inside-band share times the takers' mix (R^2 >= 0.6 over days).
  - The side component then reads: the posture outside the band (decoded), plus a stated taker-choice share (the
    quantitative unexplained part). Print-level selection gains from knowing when the cluster is on both tokens.
- **If false.** The quote is one-sided at every |e| and the tilt persists outside the band. Then the engine's fair has
  a shifting intercept toward or away from the favourite, not a sigma. P4 becomes the model: an intercept per epoch.

### P3. Maker-share accounting: is the favourite-share drift the cluster's quote or the other makers'? (strong form of X24 / X39; "counterparty flow" extended to competitor flow)

- **Hypothesis.** The cluster's fill composition (favourite share 0.26-0.68 by day) is set by its queue position against
  other makers on each outcome.
  - A competitor, or a population of them, may bid the favourite more aggressively in some periods, for example after
    its own weekly reset. It then takes the underdog-buying taker flow, and the cluster's fills tilt to the underdog
    with no change in its quote.
  - The competitor may also be an unknown sibling of the operator that uses another client: C1 searched only for the
    timestamp-0 fingerprint.
- **Why it fits.**
  - F1 and F2: a tilt independent of the reference.
  - Flat market taker demand (RE, iteration 11).
  - The cluster is about 2% of maker volume (F5; B9 1.7%).
  - Pilot: a favourite-only maker doubled its share from STUDY to VALIDATE. This is weak: 37 windows.
- **Test.**
  1. **Pre-register a sample.** Every BTC 5m window starting in four fixed hours per day (02, 08, 14 and 20 UTC: 48
     windows a day), 10-09..30. Use development data only, with VALIDATE days as per-block aggregates. That is about
     1,050 windows, roughly 2 h of polite fetching via `market_trades(cid, taker_only=False)` plus `taker_only=True` to
     mark taker rows (`makers_pilot.py` is the template).
  2. **Per 6-h block:**
     - maker BUY volume by wallet x favourite/underdog token x time-left phase (< 60 s and the rest);
     - the cluster's share of favourite-side and of underdog-side maker volume;
     - the market's maker favourite share;
     - HHI.
  3. **Co-movement.** For the top-50 makers, their favourite share and volume share per block. Look for makers whose
     favourite-side share moves inversely with the cluster's (Spearman over blocks), and compare their change points
     with the cluster's: the Monday 01:00 restart, the Wednesday last-minute steps 10-14 and 10-28, 10-26.
  4. **Price race.** For the cluster's fills on each outcome, compare its price with the best competing maker price in
     the same second. Did its favourite-side fills move from the best level to behind it?
  5. **Live control.** On dx_clob 10-31 12-18 (and 11-01 development blocks): the cluster's share of seconds with a 500
     at the favourite's best bid vs at the underdog's, against the competitors' presence at those levels.
- **Data.** data-api full tapes (cached), Gamma tokens, the RE's fill tables, the live recorders for the control.
- **Signature if true.**
  - The cluster's share of underdog-side maker volume is flat while its favourite-side share falls exactly when one or
    a few competitors' favourite-side shares rise: Spearman <= -0.5 over blocks, with matched change points.
  - Then a public side input exists: the other makers' recent favourite-side activity (public maker rows before t).
    Score it as a market-only side feature on VALIDATE against 0.710, and report it as part of the market-only
    baseline.
- **If false.** The other makers' composition is stable and the cluster's own share of the favourite side fell. The
  change is then the cluster's quote, which sends the work back to P2 (band) or P4 (intercept epochs).

### P4. Step or drift: piecewise-constant configuration pushes per module (strong form of C4 / C5 / X113 applied to the side tilt)

- **Hypothesis.** The favourite tilt is a configuration value changed at discrete times:
  - the Monday 01:00 restart;
  - the ad-hoc restarts;
  - the minutes of the size-class switches (10-23 04:20 and 10-29 03:13-03:16 UTC, simultaneous across wallets).

  The main ladder and the last-minute module have separate values (F2: Wednesday steps in the last minute, Monday jumps
  in the main ladder). The "weekly cycle" is then at least two step processes.
- **Why it fits.**
  - F2.
  - The size switches are simultaneous across wallets at night ET.
  - Ad-hoc restarts followed losing blocks.
  - The decays within weeks 1-2 are reported only on 6-h and daily grids, with no intervals. Weekend days have 437-1,335
    fills in few windows.
- **Test.**
  1. Residualise the per-fill favourite indicator on the market state (mid level, z, time left, region D) with one
     logistic model fitted on all development data.
  2. Run a change-point search (PELT or Bayesian online) on the residual at 15-30-min resolution, per wallet and
     separately for > 60 s left and < 60 s left.
  3. Test simultaneity across wallets (within +-5 min) and alignment with the salt-counter restarts (daily 01:00 and
     ad hoc), the size-class switch times and the ET clock.
  4. Report whether steps explain >= 70% of the between-block variance (piecewise constant) or whether the tilt drifts.
  5. Put window-bootstrap intervals on every per-day best k already reported.
- **Data.** Fills, calldata (salt epochs, sizes), activity; all on disk.
- **Signature if true.**
  - A handful of steps, simultaneous across the three wallets and at restarts or size switches; constant tilt between
    steps.
  - The side rule is then the posture plus a per-epoch intercept re-estimated after each restart. This is own state:
    report it separately. The epochs become the version-aware split the RE plans, defined by restarts instead of k.
- **If false.** The tilt drifts smoothly. Then it is a state updated during operation (P3's competitor or a controller
  not yet named), and its smooth path is the quantitative account.

## Notes for the RE

- Before the 11-01 06-12 pre-registered "k 1.4 vs 2.0" check, add two things to the same pre-registration, so that the
  result can tell a sigma from a tilt:
  - the favourite share in the k-invariant cell;
  - the favourite share by |e| bucket.
- Do not refit presence or selection "per k state" until P2 or P4 says what the state is.
- My locked/residual numbers use maker BUY fills only. The RE's split includes taker pairing buys. Use the RE's
  definition in P1, and report both.
- Report the per-fill own-inventory and own-history side baselines (held outcome, previous event's side) historically
  on VALIDATE, next to the public rule. The brief allows a side rule that is one of the baselines if it says so.
  Scoring per decision with the three wallets de-duplicated (critique 5) keeps that number honest.
- The pilot's per-day cluster figures (`makers_pilot.parquet`) come from 2 windows per day and must not be read as
  results.
