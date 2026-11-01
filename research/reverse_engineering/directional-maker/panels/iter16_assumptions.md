# Panel after iteration 16: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 16 the working assumptions are:
- whatever the decoded rule misses is the takers' choice (which posted rung a taker hits), so it is noise from the
  quote's point of view;
- the center's dependence on the reference (0.30 of the fair-minus-mid gap on 10-31, 0.13 plus a shrink toward 0.5 on
  11-01) is a configuration that "no public input predicts", so it is set by hand;
- module switches are manual or calendar-driven, and the instances are the three accounts of one process;
- the side bar can only be met by a public rule, so the own-state composite (0.790) and the own-history baseline
  (0.822) do not count;
- the next exam looks like the historical VALIDATE weekdays.

Written 2026-11-01, 10:15-10:50 UTC.

**Data used (development only).** `tools/sealed.py directional-maker`: released h1 and h2; development
[10-23, 10-31 06:00), [10-31 12:00, 18:00) and [11-01 06:00, now); sealed [10-31 06:00, 12:00) and [10-31 18:00,
11-01 06:00).
- Cluster activity: `.cache/re/directional-maker/activity_*.parquet` (BUILD), `exam/activity_*.parquet` (10-22..30),
  `act15_*_1793448000_1793469600.parquet` (10-31 12-18), plus a fresh `PolymarketData().activity` pull for 11-01
  06:00-10:15. Units are counted by window start, and sealed units are dropped with `sealed.is_sealed`. VALIDATE
  (10-27..30) is used only as aggregates (per fold, or daily aggregates as in the RE's iteration 11).
- Gamma listing records of 48 development BTC 5m/15m windows (10-19, 10-26, 10-27, 10-29, 10-31 13-15, 11-01 07 and 09).
  Only listing fields were read, and no sealed unit was requested.
- The RE's `it16_center_units_*` parquets (publish-pass ladder centers, 10-31 17:29-18:00 and 11-01 07:00-09:15).
- `fam/btc_4h_tapes.parquet` and `fam/btc_hourly_tapes.parquet` (10-16..30).
- Nothing from `.cache/live/sealed/` or from sealed units.

**Scripts** (in `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p16a\`;
run from the repo root with `.venv/Scripts/python.exe`; each takes under 2 minutes and under 300 MB):
- `meta.py`: listing parameters across days;
- `withdraw.py`: last and first main-ladder fill per window, per day;
- `center_refill.py`: the 11-01 center regression with and without passes next to an own fill;
- `flowside.py`: a public taker-flow side baseline for the long families;
- `idle_pair.py`: whether idle-module later fills pair or add to the held side;
- `tiltfam.py`: whether the favourite tilt moves together across families;
- `lead.py`: whether the book mid closes the reference gap, per block.

## Quick checks

**Q1. Nothing changed in the listings or the clocks between 10-31 and 11-01.** I compared the Gamma records of 48
development BTC 5m/15m windows from 10-19 to 11-01 09:30. Every listing parameter is identical on every day:
- `feeSchedule` {rate 0.07, takerOnly, rebateRate 0.2, exponent 1};
- `makerRebatesFeeShareBps` 10000, `makerBaseFee` and `takerBaseFee` 1000, `feeType` crypto_fees_v2;
- `cryptoMarketConfig` twap-60, `clearBookOnStart` False, `version` v1, resolution by oracle.

On 11-01, `eventStartTime` and `endDate` match the slug epochs. Only the creation and UMA timestamps vary.

The withdrawal shows no clock shift either. Time left at the cluster's last mid-band BTC 5m fill per window (q10):
- 11-01 06-12: 49 s (30 windows);
- BUILD and STUDY days: 17-48 s;
- VALIDATE aggregate: 41 s.

So the 11-01 change in the center is not a new fee, rebate or settlement configuration on the post-DST listings.
It is also not a DST-shifted expiry in the engine (that would put fills up to the end, or make 5m and 15m
distort differently; the RE found the same coefficients in both).

**Q2. The 11-01 shrink toward 0.5 is not refill mechanics.** I redid the RE's center regression on the 11-01 07:00-09:15
publish-pass units, c - mid on (F1_now - mid, 0.5 - mid):

| units | n | edge | shrink | R2 |
| --- | --- | --- | --- | --- |
| all | 1,138 | +0.128 | +0.090 | 0.172 |
| no cluster fill in [P - 3 s, P + 1 s] | 1,040 | +0.135 | +0.088 | 0.175 |
| own fill next to the pass | 98 | +0.051 | +0.110 | 0.17 |

Only 8.6% of passes sit next to an own fill (6.4% on 10-31). The shrink is a property of the center itself, not of
rungs refilled after takers hit the cheaper outcome.

**Q3. A public taker-flow baseline does not predict the long families' later side.** Cluster maker BUY fills more
than 20 s after the open, scored by the sign of the clean taker pressure toward bids on the bought outcome (taker SELL
of it plus taker BUY of the other outcome, minus the reverse) over the prior 30/120/600 s, and by the last clean print:

| family, fold (n) | 30 s | 120 s | 600 s | last print | market favourite |
| --- | --- | --- | --- | --- | --- |
| hourly BUILD (1,584) | 0.57 | 0.58 | 0.61 | 0.50 | 0.54 |
| hourly STUDY (737) | 0.51 | 0.45 | 0.50 | 0.45 | 0.72 |
| hourly VALIDATE (570) | 0.59 | 0.53 | 0.61 | 0.54 | 0.46 |
| 4h BUILD (739) | 0.61 | 0.60 | 0.53 | 0.58 | 0.71 |
| 4h STUDY (422) | 0.59 | 0.65 | 0.58 | 0.63 | 0.82 |
| 4h VALIDATE (255) | 0.62 | 0.53 | 0.49 | 0.51 | 0.47 |

On 4h, 30-s coverage is only 0.30-0.47. "The takers choose" does not mean that the earlier tape tells you which way
they will choose.

**Q4. The idle module does not pair. It adds to the held side, like the BTC schedule rungs.** I took later fills at
0.10-0.90 and computed the cluster's net shares before each fill (block-time order):

| family | share on the under-held outcome (BUILD / STUDY / VALIDATE) | fill size = imbalance (+-2%) |
| --- | --- | --- |
| alt 5m | 0.24 / 0.18 / 0.22 | 0.03-0.05 |
| alt 15m | 0.26 / 0.28 / 0.36 | 0.07-0.11 |
| BTC 4h | 0.49 / 0.31 / 0.38 | 0.03 |
| hourly | 0.34 / 0.39 / 0.35 | 0.05-0.07 |
| BTC 5m (reference) | 0.31 / 0.29 / 0.31 | 0.02-0.03 |

The same-side share of consecutive fills (0.86-0.93) includes one taker filling two or three accounts in the same
transaction. That inflates every persistence number (see critique 4).

**Q5. The favourite tilt moves only partly with BTC 5m across families** (favourite share of mid-band fills per day,
10-08..30, days with at least 25 fills).

| family vs BTC 5m | day-over-day Spearman (n) | level Spearman |
| --- | --- | --- |
| ETH 5m | +0.53 (22), p 0.011 | +0.40 |
| SOL 5m | +0.40 (20), p 0.08 | |
| BTC hourly | +0.30 (22) | +0.40 |
| BTC 15m | +0.28 (22) | |
| BTC 4h | -0.02 (20) | |
| bitcoin daily | | +0.62 (n 11) |

This is suggestive of one knob, but it cannot yet be told apart from a market-wide taker effect: the other makers'
favourite share per family is the missing control.

**Q6. Pilot for proposal P2.** I regressed the change in the book mid over h seconds on (F1_now - mid) at the publish
passes, with window-clustered s.e.:

| block | h = 10 s | h = 30 s | h = 60 s |
| --- | --- | --- | --- |
| 10-31 17:29-18:00 | +0.026 (0.011) | +0.053 (0.006) | +0.041 (0.012) |
| 11-01 07:00-09:15 | -0.020 (0.084) | -0.16 (0.15) | +0.04 (0.13) |

The reference led the market on the noise block and not detectably on the clean one. This is circular in part,
because the mid contains the cluster's own skewed quotes. It is a pilot, not evidence.

## Critique

1. **The hidden-dimension pass required since 11-01 has not been done for this strategy.** `state.json` has no
   catalog items E1-E7 and no `dimensions` or `indicators` ledger, and NOTES has no "Missing dimensions" section.
   - The two load-bearing claims of the current account have never been tested in the way the brief now requires:
     - "the residual side is the takers' choice";
     - "no public input predicts the configuration".
   - In particular, residual_clustering (E7) is mandatory for a wallet that quotes 5-15 markets at once, and it has
     never been run. A taker-choice residual has a testable signature: misses in unrelated markets do not coincide.
     The investigation has assumed that signature instead of measuring it (P1).
2. **"No public driver" was searched for in the wrong family.** The drivers tested for the center/tilt are market
   calibration (favourite excess win, realized-move ratio), volatility (v300, v3600, DVOL, front IV, Chainlink RV),
   competition, weekday, PnL since Monday and restarts.
   - A maker that blends a signal into its quote usually weights the signal by its recent predictive power. That is
     a public, point-in-time quantity: how much the reference predicted outcomes or mid moves beyond the mid.
   - Its sign matches the one clean contrast the investigation has: high weight in the noise regime, where the
     report sat far from the market and the market followed it (Q6), and low weight on the clean Sunday.
   - It has not been tested (P2).
3. **"Switched by hand" is the fallback label for selection, but the strongest measured signal is own state.**
   - The drawdown since the 01:00 restart has AUC 0.82-0.93 at no fixed level. That pattern is what a loss breaker
     on the wrong state variable looks like.
   - Since iteration 16 the operator's unit of switching is the account (instance), and the 9 BUILD split slots
     (one account alone on the main ladder: mo-money in 6, bosona in 2, almach in 1) have never been used as
     per-account breaker events.
   - X152 stopped at the weak form (pooled, since-restart, 7 events); the per-account and mark-to-market variants
     are explicitly "not run" (P3).
4. **The side metric is read more strictly than the target, and the persistence numbers are inflated.**
   - The target's side clause (point 3) says nothing about own state. It asks for accuracy against the market-only
     and own-inventory-only baselines and accepts "a side rule that is just one of those baselines" if it says so.
     The explicit ban on own state is in the presence clause.
   - Either the side bar is passable by an honestly labelled own-state description, or it is uninformative for this
     maker. The RE should settle which with the user before the next exam rather than decide it silently.
   - In both cases the unit must be the taker event, one per (transaction, outcome) across the three accounts.
     Today a taker that sweeps three identical rungs counts as three same-side decisions (Q4), and the 0.82-0.93
     "previous fill" numbers carry that.
5. **The next exam is a weekend lot, and the frozen rule is a weekday rule.**
   - The future sealed blocks since the last future exam are 10-31 06-12 (Sat), 10-31 18-24 (Sat evening), 11-01 00-06
     (Sun, US Saturday night) and 11-01 12-18 (Sun).
   - R8's universe held 0.28-0.41 of trades in the later halves of the weekend mock lots.
   - The 11-01 instance split (bosona alone on the main ladder) began inside that sealed stretch, so the per-wallet
     replication will compare unlike instances.
   - R9 (every family) is still not frozen. Without it the exam fails on scope before any component is read.
6. **The outcome bar is called "out of reach" from replays that cannot give queue priority.**
   - The only strict-fill model that can credit a quote refreshed within 0.1-1 s is a FIFO replay on the recorded L2
     queue, which replaces the cluster's own resting orders with the rule's at the same post times (X171).
   - It is still open, and the recorded exam books (dx_clob to 11-03) make it examinable.
   - Until it is run, "the outcome bar is capped at 0.47-0.53" is a property of the trade-through replay, not of the
     strategy.

## Proposals (ranked by the chance they close the gap)

### P1. Is the residual the takers' choice or an engine-wide input? Cross-market synchrony of out-of-fold misses (E2 + E7, required and never run; new X item)

- **Hypothesis.** A material part of what R8 misses is not local to a market. It comes from one engine-wide input that
  the public rule does not have: an internal fair or nowcast update, a configuration push, or the engine's own pass loop.
  - If misses were independent taker choices, misses in markets with different takers and different reference feeds
    (BTC vs ETH/SOL) would not coincide more than hits do.
- **Why it fits.**
  - The side residual is structured: whole windows fail in volatility bursts, and on 11-01 small-edge fills fell
    below chance inside one instance.
  - The tilt co-moves day by day with ETH 5m (+0.53, Q5).
  - The engine has one salt counter per wallet across all markets (X17).
  - The RE has never tested the alternative to "taker choice".
- **Test.**
  1. Out-of-fold residuals on BUILD (10-08..22). Refit R8's public side and the R3 presence model with GroupKFold over
     2-h blocks (choose k in fold).
     - Misses are (a) wrongly predicted sides, per taker event (one per transaction and outcome across the three
       accounts), and (b) false negatives of presence at the 10-s bin, using the top-decile residuals.
     - Do the same for the alt 5m/15m opening and later fills with the r9 posture.
  2. Run `residual_clustering` on the miss times with market = window:
     - delta_s 2 s on the block clock, `period_s` 900 for BTC 5m + 15m and 3600 once hourly is included;
     - separately for (i) BTC 5m vs BTC 15m and (ii) BTC vs ETH/SOL families (different publishes, different takers);
     - run the same on hits as the control. Shared busy minutes and cross-market arbitrage takers lift hits and
       misses alike.
  3. Live version on 10-31 14-18 and 11-01 07-12: the at-touch 500 posts that the nowcast posture gets wrong, at
     delta_s 0.25 s, across simultaneous 5m/15m windows and the alt books. Here the publish clock is in the rule, so
     synchrony that remains means an input outside it.
  4. Top clusters: look them up against publish gaps and jumps (dy_rtds), futures jumps above 3 sigma over 1 s, salt
     resets, module switches and status.polymarket.com.
- **Data.** On disk: activity, typed fills, Chainlink endpoint values, Binance 1-s, the live recordings.
- **Signature if true.**
  - Misses: ratio at least 1.5 at p <= 0.01 across assets (ii); hits near 1.1.
  - The top clusters line up with one series, which is then the hidden input to screen (E3), or with no public series,
    which makes it an internal state to infer (E6).
- **If false.** Misses are market-local at a measured ratio. That is the first quantitative support for the taker-choice
  account, and it belongs in "Missing dimensions" with the unexplained share per component.

### P2. The center's weight on the reference is learned online from the reference's recent informativeness (new; strong form of X191 and X116 with the right driver family)

- **Hypothesis.** The engine's center is c = mid + w_t (F - mid) + g_t (0.5 - mid), where:
  - w_t is a trailing estimate of how much the Chainlink nowcast F has added over the Polymarket mid, for outcomes or
    for mid moves;
  - g_t is the fallback toward a 0.5 prior when the reference has carried little information.
  - In the noise regime the report led the market (w 0.30, g ~0). On the clean Sunday it added nothing (w 0.13,
    g +0.09).
  - The same state may produce the weekly tilt and the deep-bid ramp: buy the cheap loser when the reference tells
    you nothing.
- **Why it fits.**
  - The half-spread did not move (0.075 on both blocks). Only the reference's weight and the shrink moved, and inside
    11-01 the weight drifts by half-hour (0.035-0.226), which a fixed setting does not do.
  - X191 and iteration 11 tested calibration of the market, not informativeness of the reference.
  - Q6: the mid closed 5.3% (s.e. 0.6%) of the gap in 30 s on 10-31 and nothing detectable on 11-01.
- **Test.**
  1. Pre-register two causal indicators per time t:
     - I_out(t): over the last N resolved BTC 5m + 15m windows (N 12, 36, 96), the logistic coefficient on logit F at
       fixed offsets (60, 150, 240 s), with logit(mid) as an offset. Outcomes are settled before t only.
     - I_mid(t): over the trailing 30/60/120 min, the OLS slope of mid(t + h) - mid(t) on F - mid (h 10/30 s), with
       the mid computed from clean prints, or from the book with exact schedule-size levels removed where recorded.
  2. Dependent variables:
     - w and g per 15-min bin from the publish-pass center units (10-31 17:29-18:00, 11-01 07-12, and every later
       development block: 11-01 18-24, 11-02 00-06, ...);
     - on the lot, per 2-h block, the fill-level margin (Chainlink posture k 1.0 minus the cheaper token), using
       endpoint values where fetched and the Binance stand-in elsewhere.
  3. Fit one monotone map from I to the margin on BUILD (stand-in) and STUDY, and score it on VALIDATE aggregate. Then
     freeze R8c: posture where the predicted margin is positive, cheaper token where it is negative.
- **Data.** Tapes, the endpoint Chainlink values, Binance 1-s, Gamma strikes and outcomes, center units, dm_clob_raw.
- **Signature if true.**
  - Spearman(I, w) >= 0.6 on the recorded bins, with the 10-31 and 11-01 blocks on the same curve.
  - Spearman(I, margin) >= 0.5 on the lot blocks.
  - R8c beats R8 by >= 0.01 on VALIDATE without losing more than 0.01 on STUDY.
  - That would give a public, examinable driver of the configuration, the thing the account says does not exist.
- **If false.** The weight is not a public learned state. Go to P4 (operator pushes).

### P3. A per-account rolling mark-to-market loss breaker drives the module switches and the instance split (strong form of X152; the weak form was pooled and since-restart only)

- **Hypothesis.** Each account (instance) runs a breaker on its own rolling mark-to-market loss over all its modules.
  A trip turns off that account's main ladder, but not its deep bids or slow families, for a set time.
  - The weekend-evening schedule is a separate calendar.
  - The 9 BUILD split slots and the 11-01 07:00-08:30 split are per-account trips. Mo-money rejoined at 08:30 when its
    timer or window reset.
- **Why it fits.**
  - Since-restart drawdown ranks the switch-offs at AUC 0.82-0.93 but at $1.1k-$14.6k. A restart-anchored drawdown is
    the wrong state for a rolling breaker, so its level drifts.
  - The 10-31 16:53:54 switch-off came inside a window that lost $1.6k of $2.4k.
  - The operator's switching unit is now known to be (account, module) (X177).
- **Test.**
  1. Per account, build the mark-to-market PnL at 10-s resolution from activity cash flows plus open positions marked
     at the clean-tape mid, on development units only. Reset at every sealed boundary, because the state across it is
     sealed.
  2. Events, BUILD and STUDY: per-account main-ladder off-switches (no mid-band 5m/15m fill for at least 30 min while
     another account keeps quoting, or all accounts at once), plus the BTC 15m events.
  3. Null: matched non-event times at the same hour of week.
  4. Pre-register one rolling horizon from {5, 15, 30, 60, 120 min} and one level per family. Score AUC and hit rate,
     and, in each split slot, whether the accounts that dropped off the main ladder had deeper rolling losses than
     the one that kept it.
  5. Check on the VALIDATE aggregate, then out of sample on 11-01 18-24 and 11-02 00-06, starting from zero at each
     block's start.
- **Data.** Activity (all families), clean tapes for marks, instance_mode slots.
- **Signature if true.**
  - One horizon with a stable level (CV < 0.25) over at least 8 events, AUC >= 0.85 against matched non-events.
  - In at least 7 of the 9 split slots, the accounts that dropped off have deeper rolling losses than the one that
    stayed.
  - Selection is then an own-state rule (reported, not counted for presence), and the exam's per-wallet halves can be
    explained.
- **If false.** The switches are a schedule plus discretion. Record the shares of each in the selection account.

### P4. Configuration as discrete operator pushes: a change log of the center and tilt against operator footprints (strong form of X123 + E6)

- **Hypothesis.** The center weight w, the shrink g, the deep-bid intensity and the size class are set in discrete
  pushes at operator moments: daily and ad-hoc restarts, salt resets, module switches and the Monday sweep. They are
  constant in between, and the within-block drift is estimation noise plus instance mix.
  - If so, no public driver exists. The honest account is "a human configuration explains X% of the side error".
- **Why it fits.**
  - The weekly jump after the Monday 01:00 restart.
  - The change between the 10-31 17:29 block (w 0.30, after the ad-hoc restarts) and 11-01 07:00 (w 0.13), which
    straddles the 01:00 restart.
  - X143 failed at 6-12 h, consistent with pushes between blocks.
- **Test.**
  1. Estimate the latent (w, g) per 10-min bin with bootstrap CIs on every recorded block, and find PELT change points.
  2. Align them with salt-counter resets (all-match calldata of the dm_clob_raw transactions), instance_mode changes
     and the 01:00 restart, against a circular-shift null.
  3. On the lot (fills only), find change points of the per-2-h margin (posture minus cheaper, k 1.0), the deep share
     and the size class. Compare them with the known resets (10-24 15:25:45, 10-26 16:38-16:42, 19:36-19:39,
     10-28 13:00, 19:55, the daily 01:00).
  4. One knob or several: compare the per-block tilt of BTC 5m, 15m, hourly, 4h and alt families net of each family's
     other-maker favourite share (maker-row tapes as the control; Q5 is the uncontrolled pilot).
  5. Measure how much re-estimating (w, g) from the first 30-60 min of a block recovers on the rest of it. This is an
     own-quote, self-excitation-class description: report it, never count it.
- **Data.** Center units, dm_clob_raw calldata, activity, maker-row tapes (it13/makers).
- **Signature if true.**
  - At least 70% of change points within 10 min of a footprint (null 20% or less).
  - Flat within segments.
  - Co-movement across modules after the market control.
- **If false** (continuous drift, no footprints). It is a state variable, which sends the search back to P2.

### P5. One operator, more books: wallets that go quiet at the cluster's restart and switch seconds (strong form of C1 by event timing instead of fingerprint; "who else" for selection)

- **Hypothesis.** The switches and restarts come from an operator-level host that also runs other wallets (other
  markets, other signing code). The breaker or the schedule may act on the operator's combined book.
  - C1 searched only for the same fingerprint (timestamp 0, counter salt) in BTC 5m transactions.
- **Why it fits.**
  - Restarts are scripted to the second across three separately funded accounts (01:00:10-01:00:22).
  - The ad-hoc restarts of 10-31 came 12-13 min after a switch-off.
  - The treasuries end in three EOAs whose other activity is unknown (X118).
- **Test.**
  1. Pull V2 OrderFilled logs (both exchanges, topic0 only) for 00:59:30-01:01:00 UTC on 20 development days (about
     45 blocks a day). For every maker with at least 20 fills in those windows, test for a fill gap at
     01:00:05-01:00:30, with 02:00 and 03:00 as placebo windows.
  2. Then pull plus or minus 10 min around 10-31 16:53:54, 17:05:52 and 17:06:32, and around the ad-hoc resets of
     10-24 and 10-26.
- **Data.** Polygon logs through drpc, block timestamps (cached).
- **Signature if true.** A non-cluster wallet has the gap on at least 15 of 20 days (placebo 3 or fewer) and goes
  quiet at 2 of the 3 ad-hoc events. Its PnL then enters P3 as a candidate breaker input, and its quotes enter P4 as a
  shared-configuration marker.

## Notes for the RE

- **Order for the last iteration.**
  1. The required E1/E2/E7 entries, with P1's synchrony test as the E7 run. It is all on disk.
  2. Freeze R9 for the weekend exam and report per instance (critique 5).
  3. P2's I_out on the lot. It needs only resolved windows, tapes and the endpoint values already fetched.
  4. Raise critique 4 (own-state side, taker-event unit) with the user.
- **Ruled out here; no need to repeat:**
  - listing or fee changes, and a DST-shifted expiry, as the cause of the 11-01 center (Q1);
  - the 11-01 shrink as refill mechanics after own fills (Q2);
  - prior public taker flow as the side of the long families' later fills (Q3);
  - a pairing module on the idle families (Q4: they add to the held side).
- **The mechanics panel's P3 (one engine pass for all markets) is complementary to P1.** Its pass detector gives the
  live unit for P1 step 3. P1 asks whether the misses, not the passes, are synchronous across assets.
