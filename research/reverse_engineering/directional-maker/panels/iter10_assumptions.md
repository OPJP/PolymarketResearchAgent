# Panel after iteration 10: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means:
- that every filled order's side is the wallet's choice, so an undecoded side must be own state;
- that STUDY and VALIDATE are one engine facing one market, so the PnL split can be pooled;
- that the pre-registered quote unit can be examined on the next exam lot;
- that "62/250" is one off-session ladder on a clock schedule.

Written 2026-10-31, about 23:55 UTC to 11-01 00:50 UTC.

**Data used.** Development data only; `tools/sealed.py directional-maker` gives released h1 and h2, and development
up to 10-31 06:00 and 10-31 12:00-18:00. I read the RE's existing extractions:
- the lot calldata of the cluster's orders: `b1_cluster_orders_{study,valid}.parquet` and `b1_orders_lot.parquet`;
- `it10_m1_study.parquet` (own inventory per fill) and `it9/volhist_study.parquet`;
- the lot windows, tapes, activity and Binance 1-s data in `exam/` (`windows_5m`, `taker5m_day_*`, `activity_*`,
  `spot_btc_1s`);
- the 10-31 00-06 development block: `calldata/it10_0006_orders.parquet`, `live_activity_1793404800_1793426400.parquet`
  and `it10_bn1s_*`;
- the live 10-31 12-18 per-fill table `it9/side_D_*` with `it9/spot1s_BTCUSDT_*`.

What I did and did not read:
- STUDY (10-23..26) case by case.
- VALIDATE (10-27..30) only as aggregates: per class, per session and per day, with window-bootstrap intervals.
- Nothing from 10-31 06-12, nothing after 10-31 18:00, nothing from `.cache/live/sealed/`, and no network fetch.

**Multiple-testing warning.** I scanned lags and thresholds on VALIDATE aggregates. Treat every number below as
exploratory: the RE must pre-register and confirm on a fresh development block (11-01 06-12 is the next one).

**Scripts.** All in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p10\`;
run them from the repo root with `.venv/Scripts/python.exe -I`.
- `salt_rate.py`: salt spacing between consecutive fills.
- `salt_age.py`: lower-bound ages. Its epoch detection is unreliable on STUDY; do not use its output.
- `pickoff_class.py`, `pickoff_lot.py`, `pickoff_lag.py`, `pickoff_cover.py` and `pickoff_0006.py`: the pick-off signature.
- `posture_vs_pickoff_live.py`: the live control.
- `residual_flow.py`: the per-window residual.

## What my checks found

**F1. The off-session 62/250 ladder is re-signed continuously; it is not a stale grid.**
- Test: for consecutive distinct filled orders of one wallet in one BTC 5m window with a gap dt >= 5 s, compute
  r = (salt difference) / dt.
- If the later order had been posted together with the earlier one and left resting, r would be about 0.
- Result:
  - The median r is 13-28 orders/s in every class and session, about the wallet's signing rate.
  - Fewer than 0.7% of pairs have r < 1.
  - This holds for 2,139 STUDY pairs and 7,102 VALIDATE pairs.
  - Off-session 250s: median 21.9/s (STUDY) and 17.2/s (VALIDATE). Off-session 62s: 16.8 and 14.7.
- Consecutive same-token fills of one class step up and down in limit price about equally often, so no walk-down
  ladder either.
- So the "left on its entry side" branch of the RE's next step 1 is already answered from history. Every filled rung was
  signed seconds before its fill. The open question is how it is priced, not whether it is old.

**F2. Off-session fills land on the outcome the last Binance second moved against.**
- Measure: P(the fill bought the loser of the Binance 1-s move over [b-4, b-3]), for fills with |move| >= $1.
  - b is the block second, and the match lies about 1.5-3 s before b.
  - The loser is Up if BTC fell and Down if it rose.
  - 95% window-bootstrap intervals in brackets.

| sample | class | n | P(bought the loser) |
| --- | --- | --- | --- |
| STUDY | off-session 250 | 57 (18 windows) | **0.842** [0.64, 0.97] |
| STUDY | off-session 62 | 311 | 0.601 [0.49, 0.72] |
| STUDY | off-session 500 | 130 | 0.415 |
| STUDY | US-session 500 | 721 | 0.538 [0.45, 0.63] |
| VALIDATE (aggregate) | off-session 250 | 936 (160 windows) | **0.746** [0.68, 0.81] |
| VALIDATE (aggregate) | off-session 62 | 581 | 0.611 [0.53, 0.69] |
| VALIDATE (aggregate) | off-session 500 | 1,216 | 0.618 |
| VALIDATE (aggregate) | US-session 500 | 2,570 | 0.633 [0.58, 0.68] |
| 10-31 00-06 (fresh development) | 62, hour 00 | 56 | **0.786** |
| 10-31 00-06 (fresh development) | 62, all hours | 62 | 0.774 |
| 10-31 00-06 (fresh development) | 500 | 103 | 0.738 |

- Hour 00 of 10-31 is the RE's "hour-00 anomaly": its 62s bought the Chainlink favourite in region D only 0.10. The
  pick-off reading predicts that hour's 62s at 0.79.
- On VALIDATE the signature peaks at [b-4, b-3]: 0.746 there, against 0.61-0.67 at the neighbouring seconds.
- Coverage is the weak point: only 28-48% of fills have a >= $1 move in that one second at block resolution. With the
  three most recent seconds, the rule scores 0.61-0.66 on 250s.
- On STUDY, the 250s on the held outcome and the 250s that bought the loser are the same fills (agree in 19 of 20). So
  the RE's own-state "inventory momentum" of the 250s may be a public event: the BTC trend repeating pick-offs on one
  outcome.

**F3. Control: the US-session 500 posture is not a pick-off artefact.**
- On the live match clock (10-31 12-18, 2,244 fills), fills with no Binance move >= $1 in the 1-3 s before the match
  follow the posture 0.79-0.81 (n 1,921-2,183). That is the same as overall (0.786).
- Where the posture and the pick-off prediction disagree, the fills split 0.43-0.63 between them.
- So F2 is a property of the 62/250 classes and of the historical lot, not a hidden flaw in the 500 rule.

**F4. Where the PnL is: the residual's link to the window's BTC move flips sign at 10-27.**
- Measures, per BTC 5m window of the lot:
  - R = the cluster's net Up minus Down shares bought (activity);
  - ret = the Binance move over the window;
  - F = the other takers' net Up demand on the clean tape (cluster transactions removed).
- R is unrelated to F (Spearman 0.05-0.12 in every split). The residual does not mirror the other takers' flow.
- Per day, Spearman of R with -ret (positive = net long the outcome BTC moved against):

  | day | 10-23 | 10-24 | 10-25 | 10-26 | 10-27 | 10-28 | 10-29 | 10-30 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | corr(R, -ret) | -0.02 | -0.28 | -0.07 | -0.10 | +0.24 | +0.13 | +0.31 | +0.31 |
  | corr(R, outcome) | +0.16 | +0.32 | +0.18 | +0.28 | -0.12 | -0.14 | -0.38 | -0.23 |

  Outcome = Up payout - 0.5. The VALIDATE days are aggregates.
- On every STUDY day the residual sits on the winner. On every VALIDATE day it sits on the loser.
- Locating the break:
  - It is not the 10-26 ad-hoc restarts: after 19:39 UTC on 10-26 the residual is still on the winner (+0.43, 62
    windows).
  - 10-27 01:00-12:00 is neutral (+0.05 / +0.07).
  - From 10-27 12:00 the residual is on the loser (-0.27, 286 windows).
- This is the residual's sign flip (STUDY +$5.7k, VALIDATE -$10.3k), seen per window. It holds in both sessions: US
  -0.11 -> +0.20, off-session -0.06 -> +0.30.
- The US-500 pick-off share rises in the same split, 0.54 -> 0.63 (F2).

**F5. The size class is a central configuration that switches at arbitrary minutes, not at the clock or with vol.**
- 62 -> 250 switches happen in all three wallets within about 3 minutes of each other:
  - 10-23 04:20 UTC (00:20 EDT);
  - 10-29 03:13-03:16 UTC (23:13 EDT).
- The switches back to 62 are 10-23 ~15:24-18:00 and 10-28 21:00. None falls on the 01:00 restart.
- 62 vs 250 is not ordered by the 300-s vol at the window open:
  - STUDY: 250 2.61e-5 vs 62 3.24e-5;
  - VALIDATE: 250 3.72e-5 vs 62 2.62e-5;
  - the 500 off-session windows are the high-vol ones, as the RE found.
- Within-window structure on 10-31 00-06:
  - 00:40-00:55: each window opens with 500s and drops to 62s 7-200 s later;
  - 01:00-05:45: 500s only;
  - 05:45: the 62s are back.
- 500 fills do not have larger edges than 62 fills on the Binance proxy (US medians 0.066 vs 0.083), so size is not set
  by the edge.

## Critique

1. **The side component assumes that every filled order's side is the wallet's choice.**
   - For a two-sided maker, the taker chooses which rung fills. The wallet only sets the skew and the latency.
   - The RE describes the off-session ladder with own state ("enters on the posture side, then adds to the held
     outcome"). F2 suggests a public mechanism instead: Binance-reactive takers pick off a ladder that has no Chainlink
     skew.
   - The RE's planned "taker-flow baseline" for 11-01 is a Polymarket-only baseline. The signature in F2 is in the
     reference feed, and it can be scored on the historical lot now.
   - The brief also requires the own-inventory-only side baseline per fill. On the lot it may beat the public frozen
     rule: 250s held 0.68-0.90, pairing bids under-held 1.00. Report it before the exam, not after.
2. **STUDY and VALIDATE are pooled as one engine in one market. F4 shows a regime break inside 10-27.**
   - Before the break the residual accumulates the window's winner; after it, the loser.
   - The locked-pair vs residual PnL split, the 500 posture's weaker STUDY score and the "two-sided maker earning 4%"
     story all straddle that break.
   - The outcome bar (per-window PnL corr >= 0.5) is mostly the residual (58-69% of variance), so the rule must know
     which regime it is in. Nobody has asked what changed at 10-27 ~12:00. Candidates:
     - a new taker population;
     - a quiet engine change at the 10-27 01:00 restart;
     - the Chainlink-Binance relation.
3. **The pre-registered quote unit cannot be examined on the next exam lot.**
   - The next future exam takes every sealed block that has ended since T0, so it always contains 10-31 06-12.
   - No own recorder covered that block:
     - dm_clob_raw started at 14:04;
     - dx_clob started at 15:57, with a gap from 16:53 to 17:41;
     - the full-depth recorder runs only on 11-01 05:55-12:00.
   - The shared recorder labels the quote with a recall of 0.01-0.02.
   - A quote-unit claim would either fail scope or be narrowed to a convenient subset, which the brief rates worse than
     "not decoded".
   - The presence or selection bar on the next lot has to be met on a unit the whole lot supports: the shared trade
     stream (tx hash, server ms), the shared rtds Chainlink and the public tapes.
4. **"62/250" is treated as one off-session ladder on a session clock.**
   - F5 shows centrally switched configuration epochs at minutes no clock or vol explains, plus a dynamic 500 overlay
     (window opens, high vol).
   - Every class-level side number mixes epochs:
     - STUDY's 250s are one Friday morning;
     - VALIDATE's 250s are 10-29/30;
     - the 62s are 10-24..28.
   - The class-conditional R7 failed partly for that reason.
5. **Two smaller points.**
   - The historical match clock (taker signing ms + 620 ms) is now good enough to put a futures-ms move on every lot
     fill. That is the natural input for every pick-off and trend test.
   - The hour-00 anomaly and the 250 "momentum" should be re-read through F2 before more own-state descriptions are
     added.

## Proposals (ranked by the chance they close the gap)

### P1. The off-session fill side belongs to the takers: a Binance pick-off of a ladder without the Chainlink skew (new; strong form of X28 / C3 for the 62/250 classes; replaces the own-state "inventory momentum")

- **Hypothesis.**
  - The 62/250 ladder is re-signed continuously (F1). It is not skewed to the Chainlink report, and it re-prices on
    Binance moves more slowly than the 500 ladder's 50-250 ms.
  - Latency takers who react to Binance futures choose which outcome's rung fills.
  - Its entry side and its "adds to the held outcome" are then one public event: the outcome the latest futures move
    hurt. A stale report against a fresh mid looks like a posture edge on exactly that outcome, and BTC trends make the
    event repeat within a window.
- **Why it fits.**
  - F2: 0.75-0.84 for 250s, about 0.6 for 62s on the lot and 0.79 for the hour-00 62s, against 0.54-0.63 for 500s.
  - F3: the 500s show no such signature live.
  - X28 found that latency takers never fill the US-session 500 ladder (0 of 182). The off-session classes were never
    tested.
  - Off-session returns are lower: +0.4% / +3.3% against +4.7% / +5.1% in the US session.
- **Test.**
  1. Put the RE's calibrated match clock on every lot fill: T = taker signing ms + 620 ms, clipped (A1). Take Binance
     USD-M futures aggTrades from the daily archive for 10-23..30 and 10-31.
  2. For each class (500 / 62 / 250 / pairing), score P(fill on the outcome the futures move over (T - Delta, T] hurt):
     - Delta in {100, 250, 500, 1,000, 2,000} ms;
     - |move| >= theta, with theta in {$2, $5};
     - window-bootstrap intervals.
     Fix Delta and theta on STUDY.
  3. Apply X28's latency-taker metric by class on the lot calldata (`b1_takers_*`): the share of fills whose taker
     signed within 300 ms after a futures mid move >= $5.
  4. Score the held-outcome effect of the 250s within strata of the pick-off flag and of the 30-60 s futures trend.
  5. Quote level on 11-01 06-12 (dx_clob / dw_clob / full depth): how long after a futures move >= $5, and after a
     Chainlink publish, the 62/250 rungs are re-posted, against the 500s' 50-250 ms and 0-150 ms.
  6. Pre-register a combined public side rule and score it on VALIDATE (aggregate) against the frozen 0.710 and the
     own-inventory baseline. Confirm it on 11-01 06-12. The rule:
     - posture for 500s;
     - for 62/250, the loser of the futures move in (T - Delta, T] when |move| >= theta, else the posture.
     Run a class-free variant too: "loser of the move when |posture edge| < epsilon".
- **Data.** Lot calldata (cluster orders and taker structs), Binance futures aggTrades (ms), Gamma tokens, the 10-31
  00-06 orders, the 11-01 06-12 recorders.
- **Signature if true.**
  - On the match clock the 62/250 pick-off share peaks at a lag of a few hundred ms, at >= 0.75, against <= 0.6 for
    500s.
  - Latency takers fill the 62/250 classes at >= 3 times the 500 rate.
  - The held-outcome effect falls to <= 0.55 within pick-off strata.
  - The 62/250 rungs re-post >= 0.5 s after futures moves and do not respond to Chainlink publishes.
  - The combined rule beats 0.710 with a lower bound above 0, and the own-state description of the off-session side is
    retired.
- **If false.** There is no ms peak and the latency-taker share is like the 500s'. Then the off-session side is a
  decision on an input nobody has named. The 250 momentum is genuine own state, and the unexplained share is the
  62/250 fills, 30-45% of the off-session fills.

### P2. The 10-27 break: which counterparty or engine change turned the residual from the winner to the loser (new; "counterparty flow is the edge", pooling across regimes; needed for the outcome bar)

- **Hypothesis.** From about 10-27 12:00 UTC something makes the cluster accumulate the outcome the window's BTC move
  hurts. Three rivals:
  - (a) a new taker population that picks off the ladder after Binance moves;
  - (b) a quiet engine change at the 10-27 01:00 restart, such as a weaker skew, slower re-pricing or more pairing;
  - (c) a change in the Chainlink-Binance relation, such as the lag or basis before the 10-30/31 noise regime.

  Whichever it is, the residual direction per window (58-69% of the PnL variance) is then trend times regime sign. That
  is public within the window, and the per-window PnL bar depends on modelling it.
- **Why it fits.**
  - F4: every STUDY day has the residual on the winner and every VALIDATE day on the loser.
  - The break lies inside 10-27, not at the 10-26 ad-hoc restarts.
  - The pick-off share of US 500s rises from 0.54 to 0.63 across the same split.
  - Locked pairs and the residual swap sign: STUDY -$0.9k / +$5.7k, VALIDATE +$33.3k / -$10.3k.
- **Test.**
  1. Per 6-h block from 10-09 to 10-31 06:00 (BUILD, the lot, 10-31 00-06), compute:
     - corr(R, -ret) and corr(R, outcome);
     - the same by class (500 / 62 / 250 / pairing) and per wallet.
     This shows whether the break is unique and whether BUILD's losing week (10-16..22, -$8.3k) has the same sign.
  2. (a) Counterparties. For each cluster fill, take the taker's wallet, signatureType, size and signing latency after
     a futures move (lot calldata). Rank takers by their share of the fills that built the against-trend residual
     after 10-27 12:00 and before it. Check whether a few wallets or one latency class appear at the break.
  3. (b) Engine fingerprint per block: salt rate, pairing-bid share, size mix, the posture's best Chainlink delay per
     wallet, the time-left phase profile.
  4. (c) Chainlink fingerprint per block: the cross-correlation lag of 1-s Chainlink changes against Binance (crypto-price
     endpoint; the RE's detached fetch), the basis, the lag-1 autocorrelation.
- **Data.** Activity, lot calldata (`b1_takers_*`, `b1_cluster_orders_*`), data-api tapes, Binance 1-s and futures
  aggTrades, Chainlink 1-s (cached `cl/` chunks), BUILD chain fills.
- **Signature if true.**
  - One of (a)-(c) steps at the break. For (a): <= 10 taker wallets, or one latency class, carry >= 50% of the
    post-break against-trend fills and are absent or rare before it.
  - The block-level corr(R, -ret) is then predictable from that public state (the takers' activity in the previous
    blocks, or the Chainlink lag).
  - A strict-fill replay with a regime-signed trend term reaches a per-window PnL corr well above the expectation proxy
    (0.26-0.33).
- **If false.** The sign changes block to block with no measurable state. Then the residual is the unexplained part of
  the outcome bar, and its size (58-69% of the variance) is the quantitative account.

### P3. Pre-register an exam unit that the whole next lot supports (new; target variable and scope)

- **Hypothesis.** The assumption "the quote unit is the next exam's unit" is false: 10-31 06-12 is in every future
  next-exam lot and has no own recorder (critique 3). The only units the examiner can score on the whole lot are:
  - 10-s fill presence on the match clock (capped at 0.80 by the quote oracle);
  - print-level selection: does a taker print fill a cluster order?
- **Why it fits.**
  - Shared-recorder quote recall is 0.01-0.02 (X88).
  - At the print level, the live quote oracle reaches 0.81-0.83 with recall 62-69% at lift 3.3-3.4. Public features got
    0.748 against activity 0.672 (X31, with the Chainlink stamp at t - 2 s and no class or pick-off terms).
- **Test.**
  1. Coverage table for each next-exam block, built only from recorder status and log files, not their content: the
     shared `clob_crypto` trades with tx hash and server ms, `rtds`, and the own recorders. Confirm 06-12 is
     shared-only.
  2. On the development blocks 10-31 12-18 and 11-01 06-12, restrict the inputs to what the shared recorder and public
     data provide. Score the print-level selection unit (match_test with the rotation null) with these features:
     - the printed token's Chainlink posture at the calibrated delay;
     - the region-D flag;
     - the print price minus (last clean print - 0.01);
     - the print size against the 500 / 250 / 62 rungs;
     - P1's pick-off flag;
     - time left and the clock.
     Score the activity-only baseline of the same model class alongside.
  3. Freeze the unit and its thresholds before 11-02 00:00.
- **Data.** Shared recorder (development blocks), data-api tapes, Binance futures, Gamma.
- **Signature if true.**
  - On shared-only inputs, print-level selection reaches AUC >= 0.80 with recall >= 50% at lift >= 3, and a gain
    >= 0.05 over activity on development blocks. The next exam then has a passable presence/selection unit.
  - If it stays near 0.75, say now that the presence bar cannot be met on this lot, with the measured ceiling. Spend
    the exam round on side, price and outcome rather than on presence.

### P4. Size configuration epochs: decode the 62 <-> 250 switch and the 500 overlay as their own component, and score every component per epoch (strong form of X34 and C4; pooling of configurations)

- **Hypothesis.**
  - The off-session base size is a central configuration (62 or 250) switched for all three wallets at arbitrary
    minutes (F5).
  - A dynamic 500 overlay sits on top: at window opens, in high vol, and on 10-31 01:00-05:45.
  - The trigger is one of:
    - own state: trailing PnL, or cash since the Monday sweep;
    - a slow public state: 1-24-h vol or DVOL;
    - a person: switches at waking ET hours.
  - Side behaviour may differ by epoch, not only by class.
- **Why it fits.**
  - The switches are simultaneous across wallets (a controller), fall at 23:13 and 00:20 EDT, and are not ordered by
    the open vol. In the lot, 62 epochs and 250 epochs fall on different days.
  - The class-level side numbers mix epochs (STUDY 250s are one Friday morning).
- **Test.**
  1. Run change-point detection of the modal original size per wallet-window over every period with calldata: June
     (06-10/12/16), July (pmxt adds), BUILD (fetch the cluster's BTC 5m fill-transaction calldata, sampled), the lot,
     and 10-31 00-06.
  2. Test simultaneity across wallets.
  3. Fit a hazard of each switch on the candidate triggers:
     - own trailing 6/24-h PnL and PnL since the Monday sweep (development periods only, from activity; never balances
       after 10-31 06:00);
     - futures vol at 5 min, 1 h and 24 h; DVOL; the Chainlink noise regime;
     - the ET hour and weekday.
  4. Within each epoch, re-score posture, P1's pick-off rule and the held outcome per class.
- **Data.** `b1_orders_lot`, `it10_0006_orders`, June calldata, pmxt, BUILD calldata (new fetch), activity, Binance,
  Deribit DVOL.
- **Signature if true.**
  - A handful of epochs with simultaneous switches, and a trigger that predicts the next off-session window's class
    with AUC >= 0.9.
  - Within-epoch side rules that hold across days. The class selector becomes a public (or disclosed own-state) switch
    between side rules.
  - If the switches cluster at ET waking hours with no measurable trigger, record the size mode as a manual parameter.
    List its switch times as the unexplained part, and condition the side rule on the filled order's observed class.
    This is admissible only if the examiner agrees; say so.

## Notes for the RE

- F1 also closes the salt-age question for filled orders: use salt spacing, not the lower envelope. `salt_age.py`'s
  epoch logic merges days on STUDY, because BTC 5m was off across two daily resets. Ignore its STUDY output.
- The F4 correlations use activity BUY rows, merges excluded. R includes pairing bids and taker buys; repeat them with
  the maker schedule rungs only.
- Before the exam, report the per-fill own-inventory baseline (held outcome, with pairing bids to the under-held
  outcome) next to the public side rule on the same unit.
