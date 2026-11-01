# Panel after iteration 17: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 17 the working assumptions are:
- the October behaviour is a set of separate configuration facts, each with its own patch: "the posture side is an
  October configuration", "R8c is new in October", the weekly k-cycle, "the configuration moved on 11-01";
- the engine's volatility input is backward-looking (1.4 x v300, with v3600, 2-h RV, DVOL and front IV tried as
  alternatives);
- the presence misses are the takers' arrival, so they are noise from the engine's point of view;
- the money is locked pairs plus rebates, and the directional part loses;
- the module switches are the operator's hand.

Written 2026-11-01, about 11:40-13:10 UTC. The mechanics panel's P1 (a scheduled, forward-looking volatility; suggested
X215) reached the same mechanism from the NYSE-open window. My checks below are the history-based test of it, and they
are independent of theirs. P1 below is that item's strong form, not a second item. P2-P4 are new.

**Data used (development and released lots only).** `tools/sealed.py directional-maker`: released h1 and h2.
- Cluster BTC 5m BUY trades:
  - `.cache/re/directional-maker/it12/hist_btc.parquet` (05-22..10-07);
  - `activity_{bosona,almach,momoney}.parquet` (10-08..22);
  - `exam/activity_*.parquet` (10-22..30, released lots).
  - Units are counted by window start, and only windows starting before T0 are kept.
  - The lot (10-23..30) is used only as one aggregate.
- Binance BTCUSDT spot 5-minute klines from the public REST API, up to T0, plus the two development blocks
  10-31 12-18 and 11-01 06-12.
- Nothing from `.cache/live/sealed/`. No sealed unit after T0 was read or used.
- **Disclosure.** The first version of `block_ratio.py` asked for one continuous kline range, 10-31 00:00 to
  11-01 09:15. That range includes the sealed blocks 10-31 06-12, 10-31 18-24 and 11-01 00-06.
  - Those bars were held in memory only. They were not written, printed or used.
  - The script now fetches the development ranges only. The rerun gave identical numbers.
- `mcp__polyrea__inspect_collateral` (bosona, as_of = H) hung for 30 minutes without a response. Do not call it in an
  iteration. The mechanics panel's check 5 already closes the collateral door.

**Scripts** (in `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p17a\`;
run from the repo root with `.venv/Scripts/python.exe <script> <out.json>`; each takes under 3 minutes and under
300 MB):
- `seasonal_vol.py`: the slot-volatility gradient of the cheap share, by month;
- `seasonal_vol_oct.py`: the same for the October folds; an extra argument drops the 13:00-15:55 UTC slots;
- `daily_beta.py`: the daily slope, to date the flip;
- `macro_days.py`: Thursday 08:30 ET releases and the 10-28 FOMC;
- `vol_gate.py`: module-on versus the profile;
- `block_ratio.py`: profile versus realised volatility on the recorded center blocks.

## Quick checks

Definitions, used in every check below:
- **Profile.** For each 5-minute UTC slot of the weekday, the median |5-min log return| of BTCUSDT over the 8 weeks
  before the month. It is point in time. It is a forward measure, the vol expected for the coming window.
- **Window cheap share.** Over the cluster's mid-band (0.15-0.85) BUY fills of one weekday BTC 5m window (>= 5 fills),
  the share with fill price < 0.5. Each window counts once.
- **Slope.** The window-level OLS coefficient of the cheap share on log(profile), with two controls: the window's own
  realised log|return| and the trailing 1-h mean |5-min return| before the window. The open windows (13:30, 13:35) are
  excluded, so R8c's slot plays no part.

**Q1. The slope changed sign between the summer and October. It is not a property of the 13:30 slot.**

| month | windows | slot Spearman (p) | slope (s.e.) | cheap share by profile quintile, low -> high | 13:30 window cheap share |
| --- | --- | --- | --- | --- | --- |
| 2026-06 (short profile) | 2,880 | -0.24 (4e-5) | -0.054 (0.016) | 0.46, 0.43, 0.43, 0.42, 0.37 | 0.08 |
| 2026-07 | 4,442 | -0.15 (0.01) | -0.009 (0.018) | 0.47, 0.50, 0.43, 0.46, 0.44 | 0.20 |
| 2026-08 | 3,996 | -0.22 (2e-4) | -0.050 (0.017) | 0.50, 0.48, 0.46, 0.45, 0.42 | 0.26 |
| 2026-09 | 4,714 | -0.04 (0.50) | +0.008 (0.015) | 0.66, 0.67, 0.65, 0.62, 0.66 | 0.50 |
| 2026-10 (1-30) | 3,230 | **+0.27 (4e-6)** | **+0.157 (0.021)** | 0.43, 0.46, 0.55, 0.53, 0.56 | 0.99 |

- In October the two controls carry almost nothing: +0.02 for the realised move, -0.04 for the trailing 1-h vol.
- The sign flip is the prediction of an estimator change. An engine that prices with trailing vol underestimates the
  vol of slots where it is about to rise. It overprices certainty there and leans to the favourite: a negative slope,
  as in June-August. An engine that prices with the scheduled vol stops doing that, and leans cheap in those slots: a
  positive slope.
- The market's takers did not change over this boundary (H11-TAKERS: same takers, same demand), so a taker effect
  would not flip sign.

**Q2. In October the slope holds in every fold, and outside the US-open hours too.** The profile is fixed from the
8 weeks before 10-01.

| fold | all slots except 13:30/13:35: slope (s.e.), slot rho | also without 13:00-15:55 UTC: slope (s.e.), slot rho |
| --- | --- | --- |
| 10-01..08 | +0.158 (0.036), 0.14 | +0.152 (0.044), 0.14 |
| BUILD 10-09..15 | +0.063 (0.046), 0.24 | +0.168 (0.055), 0.32 |
| 10-16..22 | +0.220 (0.063), 0.24 | +0.333 (0.074), 0.37 |
| lot 10-23..30 (aggregate) | +0.204 (0.038), 0.33 | +0.242 (0.047), 0.33 |

- The highest-profile slots outside US hours are all high on cheap share in the lot: 12:30 0.82, 16:00 0.76.
- So the October behaviour is a gradient over the whole day. R8c captures its peak, and R8d (discrete slots with a
  threshold) was the wrong form of it.

**Q3. The flip is dated 10-01/10-02.** I fitted the slope per weekday (median 186 windows a day), with the profile fixed
from 07-20..08-31.
- September: mean +0.006, positive on 11 of 22 days.
- 10-02..10-30: mean +0.160, positive on 19 of 21 days. The exceptions are 10-15 (-0.15, the RE's 10-hour episode)
  and 10-30.
  - Sign test p 2e-4. Mann-Whitney against September, p 4e-4.
- 10-01 itself is -0.11.
- This matches the RE's open-window history: cheap share 0.64 in September, 0.997 from 10-01.

**Q4. Scheduled releases do not show the same lean** (one FOMC, three or four Thursdays a month; tiny n).
- The 12:30 UTC window on Thursdays (jobless claims, 08:30 ET) is less cheap than on other weekdays in October: 0.51
  vs 0.68. The same holds at 12:25/12:35.
- The 10-28 FOMC windows (14:00 ET = 18:00 UTC) were busy: 61, 82 and 45 fills at 18:00, 17:55 and 18:30. They were
  **favourite**-heavy: cheap share 0.16, 0.04 and 0.00. The other October weekdays in the same slots were at 0.84, 0.41
  and 0.60.
- So the mechanics panel's variant (c) is disfavoured. That variant adds release bumps to the profile.
  - The profile looks like a time-of-day statistic, not an event calendar.
  - Around FOMC the engine did something else: a lag in the profile, a pause or a manual override.

**Q5. Module-on is not a gate on the profile.** Module-on means the BTC 5m window has >= 1 cluster BUY fill. I scored it
against the profile of the window's slot by day type (8 weeks before the month).

| month | AUC of the profile | AUC of trailing 1-h vol | AUC of hour x day type (in-sample) |
| --- | --- | --- | --- |
| 07 | 0.47 | 0.57 | 0.67 |
| 08 | 0.51 | 0.59 | 0.66 |
| 09 | 0.44 | 0.53 | 0.65 |
| 10 | 0.46 | 0.52 | 0.63 |

- Weekday cell rho is 0.04-0.43. The October on-share by profile quintile is flat (0.76-0.83).
- So the forward vol enters the **price**, not the switch, and selection needs a different driver (the mechanics
  panel's P2 salt-rate state is the right next step). This door is closed.

**Q6. On the two recorded center blocks, the scheduled profile exceeds the realised vol most where the center shrank.**
The ratio is the median profile of the block's slots over the median |5-min return| of the block itself (descriptive).

| block | realised (bp / 5 min) | profile / realised: all days pooled | weekdays | weekends |
| --- | --- | --- | --- | --- |
| 10-31 17:30-18:00 Sat (w 0.30, no shrink) | 4.2 | 1.17 | 1.27 | 0.63 |
| 11-01 07:00-09:15 Sun (w 0.13, shrink +0.09) | 2.8 | **1.61** | **1.98** | 0.84 |
| 10-31 14:00-18:00 Sat (quote-unit block) | 3.4 | 1.84 | 2.20 | 1.01 |

- Whatever day type the profile uses, the 11-01 block has the larger forward excess. That is the direction of a fair
  pulled toward 0.5 there.
- The counterpoint is the 10-31 14-18 block. It has the largest ratio, yet the trailing-sigma posture worked there
  (0.815). This is the noise regime, where the report sat far from the market and large report edges dominate the side.
  P3 has to explain both blocks or fail.

## Critique

1. **One estimator change is being read as five configuration facts.** Each of these got its own rule or its own
   "configuration" label:
   - the October posture;
   - the NYSE-open window (R8c);
   - the 10-30-plus small-edge failures;
   - the block-level margin falling with vol (rho -0.33);
   - the 11-01 shrink.

   Q1-Q3 show one dated change on 10-01/10-02, consistent with a switch from trailing to scheduled volatility. The
   May-September history is not just "a different version" to set aside (H13-STABLE). It is the control that
   identifies the estimator: the sign of the slope flips. A patch per symptom (R8c, R8c15, R8d) cannot generalise to the
   post-DST exam. An estimator can.
2. **Every volatility test so far is a trailing statistic, so the investigation could not find this.** The list is
   long: H-VOL, X74, V10-horizon-sigma, H10-HVOL-500, X117 (DVOL, front IV, Chainlink RV), the iteration-11 running
   estimators, and T16's 2-h RV gate. In the G3 test, the margin's association with block vol did not survive at the
   fill level. Trailing 2-h vol is the wrong sign of the information: Q2 shows the forward profile carries the slope
   while the trailing 1-h vol does not.
3. **The pooled per-fill side metric hides a gradient behind one slot.** The NYSE-open window has about 70 decisions per
   window against 16 elsewhere. So one slot moved target_metrics by +0.008, while a mechanism spread thinly over every
   small-edge fill moves the aggregate little per slot.
   - Any forward-vol rule must be judged by |edge| band and by forward/trailing-ratio band, besides the aggregate.
   - Otherwise a real mechanism will be rejected on the aggregate, which nearly happened to R8d (+0.0029 vs a +0.003
     bar).
4. **"Where the PnL comes from" was never split by the input that changed.** D4 splits locked pairs from the
   directional residual. The replays (X106, X124, X154) all price with a trailing-vol posture.
   - If the alpha is the scheduled-vol lean, those replays could not earn it. Their 0.21 PnL correlation and negative
     strict returns would then say "wrong estimator", not "queue priority out of reach".
   - The RE's own whole-history return series points the same way: about +2-5% per $ in August-September, +4.0% on the
     October holdout (examiner).
   - This has not been tested.
5. **"Presence misses are the taker's arrival" was accepted without splitting the label by order type.** The presence
   label pools four order types, all with known calldata sizes:
   - main-ladder posts, which react to public events;
   - pairing bids, which exist only because of the cluster's own imbalance (X92, X139: 11-19% of fills);
   - deep resting bids (<= 0.10);
   - remainders of partly filled rungs.

   The E2 breakdown is by edge, activity, hour, weekday and vol, never by order type. Until it is, the 54% FN share is
   not a quantitative account of the takers.

## Proposals (ranked by the chance they close the gap)

### P1. One estimator change on 10-01: the fair's sigma became a scheduled time-of-day profile; identify it by the contrast with May-September (strong form of mechanics P1 / X215; the history test that P1's step 3 asks for, with the result above)

- **Hypothesis.** From 10-01/10-02 the engine's sigma is a scheduled profile, sigma = k x profile(slot)^a x
  v300^(1 - a) with a near 1. The profile is the expected vol of the coming 5 minutes for that time of day.
  - Before 10-01 it was trailing (a near 0).
  - R8c's open window, the cheap-share gradient over the day, the October posture and the margin-vol association are
    all this one input.
  - Release events are not in the profile (Q4).
- **Why it fits.**
  - Q1: the slope flips from negative (June-August) to positive (October).
  - Q2: it is present outside US hours.
  - Q3: the flip is dated 10-01/10-02, the same date as the open-window step.
  - The mechanics panel's check 1: forward/trailing is 2.6 at 13:30 and about 1 at 13:35, where the posture holds.
- **Test.**
  1. **Profile variants, all point in time.** Build each from the 4 and the 8 weeks before the scored day:
     - (i) UTC slot vs New York slot;
     - (ii) day-type profiles vs all days pooled;
     - (iii) median |5-min return| vs 1-s realised vol over the slot;
     - (iv) Binance spot vs the strike-to-strike moves of past BTC 5m windows (priceToBeat, public). The last one would
       be a Polymarket-native profile.
  2. **The identification statistic (pre-register it before fitting any rule).** Use the window-level slope of Q1 per
     month, May-October, with the window's realised move and the trailing vol as controls.
     - A trailing engine predicts slope <= 0. A scheduled engine predicts > 0.
     - Market control: the same statistic for the other makers' mid-band fills in the same windows (the maker side of
       the clean-tape prints, from the X115 maker rows). A flip that belongs to the cluster does not appear in the
       market's slope.
  3. **The rule.** Use the Chainlink posture of `code/side_sm.py` (Binance stand-in fallback), with R8c's calendar
     branch removed and sigma = k x profile^a x v300^(1 - a).
     - Choose (a, k, variant) on BUILD 10-09..22 only, then pre-register.
     - Score per fill on STUDY (case by case) and VALIDATE (aggregate) against R8c: overall, in the open window, by
       |edge| band and by profile/v300 band.
     - Fit (a, k) again on September and on August, as description: the estimator change predicts a near 0 there.
  4. **Date pin and footprint.** Run a change-point on the daily slope (Q3 series, extended back to 08-01). Then check
     the 09-30..10-02 calldata and activity for a deployment footprint: a salt-counter reset outside 01:00, a size or
     ladder change, or a restart time. Q3's date predicts one on 10-01.
  5. **Exam clock.** With variant (i) chosen on development data, write down the 11-02 prediction before the 11-02
     12-18 development block.
     - A UTC trailing-weeks profile keeps its peak at 13:30 UTC for weeks after DST, while the market's vol peak moves to
       14:30.
     - A New York profile moves to 14:30 at once.
     - The mechanics panel's P4 observes the open live. This step makes it a test of the estimator, not only of R8c.
- **Data.** On disk: hist_btc, activity, exam activity, the calldata. Public: Binance klines or archives (from 04-01 for
  May's profile). The Gamma priceToBeat is needed for (iv) and is already cached for the lot and BUILD.
- **Signature if true.**
  - The monthly slope is <= 0 for May-August and > 0 in every October fold, while the market-control slope does not flip.
  - The fitted a is >= 0.7 in October and <= 0.3 in August-September.
  - The rule reproduces the open window (cheaper token >= 0.85 on STUDY and VALIDATE) without a calendar branch.
  - VALIDATE per fill is >= R8c + 0.005, with the gain in the |edge| < 0.05 band and in the high-ratio band.
  - The change-point falls within one day of 10-01, with a footprint.
- **If false.**
  - The slope does not flip, or the market's slope flips too: then it is a market effect, and R8c stays a configured
    calendar override.
  - The rule gains only at 13:30: then R8c is a configured calendar override, and P4 of the mechanics panel decides its
    clock.

### P2. The PnL lives where scheduled and trailing volatility disagree: decompose the money by the forward/trailing ratio, before and after 10-01, and replay with the scheduled posture (new; D4 and D3 for the input that changed)

- **Hypothesis.** The cluster's edge is selling favourites that the market prices with trailing vol at moments when the
  vol is predictably about to rise.
  - Market participants underprice the cheap token there. The cluster's fills at high forward/trailing ratio carry most
    of its directional PnL from 10-01.
  - Before 10-01 the cluster lost at those moments (it leaned to the favourite, Q1).
  - If so, the earlier replays failed mainly because they priced with trailing vol, not because they lack queue
    priority.
- **Why it fits.**
  - Q1 and the RE's history: return per $ on BTC 5m BUY fills of about +2-5% in August-September, +4.0% on the October
    holdout.
  - D4: the directional residual lost -$14.4k on VALIDATE. That is a pooled number, never split by ratio.
  - H-REGION-PNL: the profit is concentrated in underdog fills.
- **Test.**
  1. **Units.** Whole-history BTC 5m BUY fills (all three accounts), development units only.
     - Return per $ = (payout - cost) / cost, with the Gamma resolution used for settlement only.
     - The ratio R at the fill = profile(slot) / v300 at the fill (from Binance 1-s, available k+1 s).
  2. **Table.** Return per $ by month x R quintile x cheap/favourite, with a day-block bootstrap.
  3. **Replay.** Use the X124/X154 strict replay machinery (R7 price, one batch per decision second), with the P1
     posture against the trailing posture on VALIDATE, and report:
     - window PnL Pearson/Spearman;
     - the strict return;
     - the outcome by R band.
- **Data.** hist_btc, activity, Gamma outcomes (cached), Binance 1-s archives, the replay code (code11 / code12 /
  code14).
- **Signature if true.**
  - In October, the cheap fills in the top R quintile earn >= 5 points per $ more than in the bottom quintile.
  - In June-August, the favourite fills in the top R quintile lose.
  - Most of the September -> October change in return per $ comes from the top two quintiles.
  - The scheduled-posture replay raises the window PnL correlation by >= 0.10 (0.21 -> >= 0.31).
- **If false** (flat across R, and no replay gain). The scheduled vol is a risk setting, not the alpha. The money stays
  "pairs plus rebates", and that becomes a measured statement instead of an assumption.

### P3. The 11-01 "regime" is the scheduled-vol excess on a quiet Sunday, not a new configuration: re-run the center regression and the bosona natural experiment with the scheduled fair (new; strong form of H16-NAT-EXP, H16-CENTER and X208, which all assumed the fair was right and the configuration moved)

- **Hypothesis.** The ladder center is c = mid + w (F_sched - mid). F_sched is the Chainlink fair at the scheduled
  sigma, and w is one constant across blocks.
  - On 11-01 the profile exceeded the realised vol (Q6: 1.6-2.0 pooled or weekday, 0.84 weekend). So F_sched is closer
    to 0.5 than the trailing-sigma fair, and the regression on the trailing fair shows it as "w 0.13 plus a shrink
    g +0.09".
  - The small-edge side drop inside one instance (bosona 0.880 predicted vs 0.729 actual, X196) is the same thing.
- **Why it fits.**
  - Q6.
  - The iteration-16 panel found the half-spread unchanged and only w and g moved, with w drifting by half-hour inside
    11-01 (0.035-0.226). A ratio that varies by slot produces exactly that drift.
  - Listings, fees and the expiry clock did not change (iteration-16 panel, Q1).
- **Test.**
  1. Rebuild F with the P1 profile variants (pooled, weekday and weekend day types), with k frozen on 10-31 14-18.
     Re-fit c - mid = w (F - mid) + g (0.5 - mid) on the publish-pass center units (`it16_center_units_*`, 10-31
     17:29-18:00 and 11-01 07:00-09:15), with window-clustered s.e. Report it per 15-min bin as well.
  2. Recompute bosona's band-conditional side (H16-NAT-EXP / X196 reweighting) with F_sched in place of the report fair.
  3. Pre-register a prediction for the next weekend development block (11-07/11-08), and for the next block of the
     opposite regime.
- **Data.** Center units, dy_rtds, Binance 1-s for both blocks, the 8-week profile (public).
- **Signature if true.**
  - With F_sched, g is within 0.03 of 0 on both blocks and w agrees within 0.05 across blocks.
  - The per-15-min w drift on 11-01 halves.
  - Bosona's small-edge side on 11-01 rises to >= 0.80, within 0.03 of the reweighted prediction.
  - It must not break 10-31 14-18, where the trailing posture scored 0.815: that block has to keep >= 0.80 under
    F_sched. Otherwise the variant is max(trailing, profile), and the test is repeated with it.
- **If false.** The 11-01 change is a real configuration step, and X208's change-point / operator-push reading stands.

### P4. Split the presence label by order type before attributing the residual to takers (new; E2 strong form, D1 unit purity)

- **Hypothesis.** A large part of the out-of-fold presence FN (54% of filled cells) is order types that public
  features cannot announce by construction. The public-rule residual of the main ladder is much smaller than 54%.
  - Pairing bids exist only after an own imbalance.
  - Remainders keep resting after a partial fill.
  - Deep bids sit for minutes.
- **Why it fits.**
  - FN is 0.74 at |edge| < 0.05 and 0.26 in the last minute. Pairing and remainder fills sit at small edges in the
    middle of the window.
  - With own inventory, presence gains +0.05 (H9).
  - Pairing is 11-19% of fills (X92, X139).
  - Iteration 17 attributes the FN to "a single taker's arrival" without this split.
- **Test.**
  1. On the lot calldata (`b1_cluster_orders_study/valid`, `b1_orders_lot`; salts, original sizes, limits), class each
     filled cell's fills by the order that filled:
     - main ladder: schedule sizes 500 x 2^k, or the per-family sizes;
     - pairing: original size within 2% of the wallet's |imbalance| in that window at the previous fill;
     - deep: limit <= 0.10;
     - remainder: an order with an earlier partial fill.
  2. Score the frozen R6 presence (no own state) and the own-state variant per class on VALIDATE (aggregate). On BUILD,
     use the E2 out-of-fold scores where calldata exists, with a sample fetch if not.
  3. Report the FN share per class and the share of all FN cells each class explains.
- **Data.** The decoded calldata on disk, the activity, the E2 scores (`code17/e2_resid.py`).
- **Signature if true.**
  - >= 50% of FN cells hold only pairing, remainder or deep fills.
  - The main-ladder FN share is <= 0.35.
  - The own-state variant recovers most of the pairing class.
  - The honest account then reads: "public presence misses X% of main-ladder cells; Y% of all misses are own-state
    order types", and the next presence work targets the main ladder only, reported as a decomposition, not as a
    narrowed score.
- **If false** (the main-ladder FN is as high as the pooled one). The taker-arrival account stands, now measured. The
  quiet-cell trigger goes to the information panel's I17-2 (what the paying takers see).

## Notes for the RE

- **Order.**
  1. P1 step 2 (the identification statistic with the market control). It is cheap, and everything in P1-P3 depends on
     it.
  2. P1 step 3, before the 11-02 12-18 development block, so the post-DST prediction is written down in advance.
  3. P3. Center units and the profile are all on disk or public.
  4. P2.
  5. P4.
- **Ledger entries these checks support.**
  - X215 (mechanics P1): add the Q1-Q3 history evidence, the slope flip and its date.
  - A new indicators row: "slot-vol slope of the window cheap share", monthly, legacy period.
  - Closed here:
    - module-on as a scheduled-vol gate (Q5: AUC 0.44-0.51);
    - release bumps in the profile (Q4, low n: FOMC 10-28 windows were favourite-heavy, Thursday 12:30 not cheap).
- **The 10-28 FOMC windows are an operational question of their own.** They had heavy activity, favourite-heavy, the
  opposite of the NYSE open. Look at the salt counters and the instance mode in 17:50-18:40 UTC of 10-28 (lot calldata,
  aggregate only) before freezing anything that touches release days. The exam lots will contain the next FOMC
  (12-08/09) only if the study runs that long, but CPI, NFP and claims days come every week.
- **Do not use `mcp__polyrea__inspect_collateral`**: it hung for 30 minutes on one call.
