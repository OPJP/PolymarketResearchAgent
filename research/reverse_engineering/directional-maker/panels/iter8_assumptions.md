# Panel after iteration 8: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means:
- that the exam lot will look like VALIDATE (weekdays, BTC 5m and 15m on);
- that the BTC 5m on/off is "an operator decision invisible in public data";
- that the per-fill side score measures a per-report decision;
- that Chainlink is the engine's input because it is the settlement source;
- that the pooled union metric measures decoding.

Written 2026-10-31, about 20:30-21:00 UTC.

Data used (development only, checked with `tools/sealed.py directional-maker`: development up to 10-31 06:00 and
10-31 12:00-18:00):
- the three wallets' activity for 10-08..22 (`.cache/re/directional-maker/activity_*.parquet`);
- the released lot's activity (`exam/activity_*.parquet`). I used 10-27..30 only as day and 6-hour aggregates, and
  10-23..26 (the study half) hour by hour;
- the cluster's 10-31 12:00-16:30 activity (`live_activity_*.parquet`);
- the RE's per-fill side table `it6/fill_side_1793455600_1793464202.parquet` (10-31 14:06-16:30);
- Gamma metadata and outcomes for the 10-31 12-18 windows (polyrea adapter, development block).

Nothing from 10-31 06-12, 10-31 18:00 onward or `.cache/live/sealed/` was read.

My check scripts are in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p8\`:
- `offruns.py`: the BTC 5m off-runs of 1 hour or more;
- `offmix.py`: the family mix during off-runs and R6 coverage by lot day and 6-hour block;
- `onoff_cal.py`: activity by weekday and US-Eastern hour, and a calendar gate;
- `inv_base.py`: own-history side baselines, taker-event collapse and per-window accuracy;
- `volscale.py`: posture side against the vol scale.

Run them from the repo root.

## Critique

1. **VALIDATE is the most favourable regime the strategy has. The next exam lot is a weekend.**
   - VALIDATE (10-27..30) is Tuesday to Friday. On those days R6's universe (BTC 5m + 15m) holds 0.84-0.90 of the
     cluster's dollars per day.

     | lot day | R6 share of trades | R6 share of dollars |
     | --- | --- | --- |
     | 10-23 Fri | 0.71 | 0.77 |
     | 10-24 Sat | 0.28 | 0.27 |
     | 10-25 Sun | 0.58 | 0.52 |
     | 10-26 Mon | 0.78 | 0.80 |

   - In 14 of the lot's 32 six-hour blocks, R6's dollar share is below 0.80. That includes every weekend block (four
     of them at 0.00) and several 00-06 and 06-12 UTC weekday blocks.
   - In both of the lot's weekend-night off-runs, **BTC 5m and BTC 15m were off together**:
     - 10-23 20:40 to 10-24 15:25 UTC;
     - 10-24 22:30 to 10-25 13:30 UTC.

     R6 covered 0.1% and 0.0% of the trades. The engine kept trading BTC 4h (32-37% of dollars), BTC hourly and daily
     (13-19%), ETH 15m, XRP 5m and the daily markets.
   - The pre-registration "a block with BTC 5m off is scored on BTC 15m" assumes that 15m stays on. In the latest
     version's weekend nights it did not.
   - The next future exam takes the sealed blocks 10-31 06-12 and 18-24, then 11-01 00-06 and 12-18: a Saturday and a
     Sunday. As frozen, R6 fails the scope bar there.
2. **The on/off decision was closed as an invisible operator choice (H13, H20, H51). It is the largest lever on
   presence, and it is partly a public schedule.**
   - H13 measured that an on/off oracle lifts presence to 0.866. The examiner measured 0.700 -> 0.794 on the lot.
   - Each of the six off-runs of 1 hour or more in 10-08..30 is either a weekend evening or the 10-29 platform
     incident. The weekend ones start Friday to Sunday at 16:35-18:30 ET and end at 08:30-11:25 ET the next morning.
     Other markets stay 82-95% active throughout, so the engine is running and only modules are switched off.
   - A hand-written gate scores well since the 10-16 version and fails before it. The gate is "off from Friday,
     Saturday or Sunday 18:00 ET to 09:00 ET the next day".

     | period | active when the gate says off | active otherwise | window-level AUC |
     | --- | --- | --- | --- |
     | development since 10-16 | 0.30 | 0.63 | 0.63 |
     | lot | 0.29 | 0.87 | 0.77 |
     | 10-08..15 | 0.90 | 0.82 | 0.45 |

   - So the gate holds for one version, and only partly. Exceptions: 10-25 (Sunday night) had 5m on and 15m off from
     20:00 UTC, 10-30 (Friday night) stayed on, and 10-31 switched off at 12:53 ET.
   - VALIDATE has almost no off time (94.5% of windows active), which is why the lever never showed in the primary
     metric.
3. **The per-fill side score of 0.836 is weaker evidence than its n of 1,341 suggests.**
   - One taker order fills all three wallets, and half of the windows are one-sided.
   - On 10-31 14:06-16:30 I collapsed fills on the same side within 100 ms into one taker event. That gives 881
     events, and the posture scores 0.801 per event and 0.772 per window (34 windows).
   - Own-history baselines that the examiner may fit (side component, own-inventory-only):

     | baseline | score |
     | --- | --- |
     | side of the previous taker event | **0.854** |
     | side of the previous fill | 0.92 |
     | side it holds more of | 0.69-0.70 |

     The posture beats the inventory baseline but loses to the plain "same side as last time".
   - When the posture sign flips between two events, the fill side switches in only 45% of cases, against 8% without
     a flip. The posture drives the switches, but with inertia.
   - At |edge| <= 1 c the accuracy is 0.33, below chance. That is the signature of a deadband with memory: inside the
     band the engine keeps its previous posture.
4. **No single fair-value setting fixes the failing windows.**
   - Scaling the vol of the Chainlink digital fair (zcl / s):

     | s | effect |
     | --- | --- |
     | 1.0 | best overall: 0.809 per fill, 0.772 window-weighted |
     | 0.6 | repairs the 15m 14:45 window (0.14 -> 0.76) and the 15m 15:00 window (0.48 -> 0.90), but breaks 5m 14:15 (0.94 -> 0.35) and 5m 14:30 (1.0 -> 0.35) |

   - The failures are wholesale at the window level, and in failing windows the posture-consistent fills still earn
     +16% (anti-posture fills -16%). So in some windows the engine holds a state that its fair does not carry.
   - One example: in the three windows settling at 15:00 the cluster bought Down against both references, and Down
     won all three. It bought Down in the Binance-settled 10am-ET hourly market in the same minutes.
5. **The pooled union AUC mainly measures family base rates.**
   - The per-family gains are +0.032 (5m) and +0.034 (15m). Pooled, the gain shrinks to +0.009, because both models
     learn that 5m bins fill more often than 15m bins.
   - Report AUC stratified by family, and the gain per family, as the pre-registered presence number.
6. **The size fingerprint is regime-bound.**
   - The quote-unit label (cluster-class exact-500) and the X36 identity result (87.9% of filled exact-500 orders are
     the cluster's) hold in the 500-share regime only.
   - In the same 10-31 15:20-15:40 sample, 0 of 90 filled exact-250 orders were the cluster's. When the size schedule
     drops to 62/250 (nights and weekends), the label collides with other makers.
7. **The hourly and daily markets do not settle on Chainlink.**
   - Gamma `resolutionSource` checked for 10-31:

     | market | settles on |
     | --- | --- |
     | `bitcoin-up-or-down-october-31-2026-10am-et` | Binance BTC/USDT 1-hour candle, close >= open |
     | `bitcoin-up-or-down-on-october-31-2026` | Binance 1-minute candle closes at noon ET |
     | `btc-updown-4h-*` and `btc-updown-15m-*` | Chainlink TWAP-60 |

   - So the engine trades markets with two different settlement sources. The statement "it skews toward the
     settlement source itself" makes a prediction for the Binance-settled markets that has never been tested.
8. **The next development block may have no BTC 5m at all.**
   - 11-01 06-12 UTC is Sunday 01:00-07:00 EST, starting at the moment DST ends. BTC 5m has been off since 10-31
     16:53. By the weekend pattern it returns around 13:30-14:30 UTC, and BTC 15m may go off as well.
   - So the pre-registered BTC 5m checks may have nothing to score:
     - the posture pass mark;
     - the quote-oracle ceilings;
     - the delayed full-depth recorder, which records only BTC 5m and 15m.
   - Nothing records the hourly or XRP books (the shared recorder covers BTC, ETH and SOL 5m, 15m and 4h only).

## Proposals (ranked by the chance they close the gap)

### B1. The exam lot is a weekend: freeze one family-general universe and treat the module state as a selection component (strong form of X69, X65, X70 and H51)

- **Hypothesis.**
  - The engine runs separately switchable modules: BTC 5m, BTC 15m and an always-on set (BTC 4h, hourly and daily,
    and ETH/XRP/SOL/DOGE/BNB short windows).
  - Since the 10-16 version, the BTC 5m and often the 15m module go off on most weekend nights (US-Eastern evening
    to morning), and the night and weekend book shifts to the always-on families.
  - A rule whose universe is BTC 5m + 15m fails the scope bar on any weekend-heavy lot. The on/off gate is worth
    about +0.09 presence AUC wherever off time exists.
- **Why it fits.** Critique 1 and 2:
  - R6 covers 0.0-0.1% of trades in the lot's weekend off-runs;
  - 14 of 32 lot blocks are below 0.80;
  - every long off-run is a weekend evening ET;
  - the gate scores window AUC 0.77 on the lot;
  - with an on/off oracle, presence goes from 0.700 to 0.794 (examiner) and from H13's baseline to 0.866.
- **Test.**
  1. Build per-module on/off series at 5-minute resolution over the whole history (May to 10-22 via the cached
     activity adapter, plus the lot's study half and the 10-31 development blocks). Modules: BTC 5m, BTC 15m,
     BTC 4h, BTC hourly, BTC daily, ETH 5m/15m, XRP 5m.
  2. List every switch event. Mark whether 5m and 15m switch together, the ET clock time, the weekday and the
     version (salt-counter restarts, size regime).
  3. Score the calendar gate frozen above, and a version-aware variant (fitted only on events before 10-23), on later
     events: window-level AUC for each module.
  4. Combine the gate with the X70 public candidates (futures vol, burst rate, Chainlink noise) in a hazard. Do not
     use own PnL here: it is own state.
  5. Compute coverage per 6-hour block of nested universes (R6; + BTC 4h; + BTC hourly/daily; + every crypto
     Up/Down) and pick the smallest universe with >= 0.80 of trades and dollars in every block type (weekday day,
     weekday night, weekend day, weekend night).
  6. Pre-register it, with per-family presence (R3 class with horizon and asset as features) and the gate, before
     the next future exam.
  7. Forecast now, before the data exist: on 11-01 06-12 UTC, BTC 5m stays off. If it does, re-point that block's
     recorders and checks to the families that are on.
- **Data.** Full-history activity (cached adapter), Gamma listings of all crypto Up/Down families, the shared
  recorder for 4h/ETH/SOL. A slim recorder (tools/live.py Writer, hard stop) for the BTC hourly and XRP 5m books.
- **Signature if true.**
  - The chosen universe covers >= 0.80 / 0.80 in every block type, weekend nights included.
  - The gate or hazard predicts module-off windows at AUC >= 0.80 after 10-16.
  - 11-01 06-12 has no BTC 5m fills.
  - Presence over a weekend-containing period gains >= +0.05 over the activity baseline once the gate is included.
    The activity baseline cannot see the switch.
- **If false.** If the modules switch with no calendar or public correlate, the switch is a manual decision. Record
  its event count and timing as the quantitative unexplained part, and still freeze the family-general universe for
  scope.

### B2. The settlement-source natural experiment: Binance-settled hourly/daily markets against Chainlink-settled 5m/15m/4h (new)

- **Hypothesis.**
  - The rule's economic story says each ladder is skewed toward the source that settles that market.
  - If so, in the hourly and daily markets (settled on Binance BTC/USDT candles, with the candle open as strike) the
    cluster's side follows the sign of a Binance-spot fair minus the mid, not the Chainlink fair.
  - In the 4h market (Chainlink TWAP-60) it follows Chainlink.
  - The alternative: Chainlink is just the fastest composite feed the engine reads, and it skews every market by
    Chainlink, including those that settle on Binance (where the skew should then lose).
- **Why it fits.**
  - The strategy statement attributes the edge to the settlement source, but every test so far ran on
    Chainlink-settled markets, where "settlement source" and "Chainlink feed" cannot be told apart.
  - The always-on families that carry the weekend nights include Binance-settled ones (13-19% of dollars in the off
    runs). Their side rule is needed for scope anyway (B1).
  - On 10-31 the cluster bought Down in the 10am-ET hourly market during the same minutes it bought Down in the 5m
    and 15m windows settling at 15:00, against the Chainlink edge (critique 4).
- **Test.**
  1. Collect every cluster fill in BTC hourly and daily markets on development data:
     - the 10-17/18 and 10-18/19 weekend nights (~140-170 hourly trades per night);
     - the lot's study half;
     - 10-31 12-18 (37 hourly + 39 daily trades);
     - 11-01 development blocks, with a slim recorder of the hourly books (match clock).
  2. For each fill, compute two edges:
     - (a) the Binance-spot digital fair (strike = the candle open, which is public at the hour start; horizon to
       the candle close) minus the mid;
     - (b) the same with the Chainlink 1-s series (crypto-price endpoint; fetch 10-17..19 before it ages out
       around 11-16).
  3. Score sign accuracy per taker event and per window for each.
  4. Do the same for BTC 4h (Chainlink-settled control) and for ETH hourly against ETH 15m.
  5. Secondary check, settlement-instant coupling: for every instant at which several families settle (e.g. 15:00),
     test whether a Chainlink-posture failure in 5m/15m coincides with the cluster's side in the hourly market and
     with the Binance candle state.
- **Data.** Activity (cached), data-api tapes of the hourly/daily markets (block-clock mid), Binance spot 1-s
  archives and aggTrades, the Chainlink crypto-price endpoint, Gamma, and a slim hourly-book recorder for live
  blocks.
- **Signature if true.**
  - On hourly/daily, the Binance fair beats the Chainlink fair by >= 0.08, and Binance scores >= 0.75 per event.
  - On 4h and 5m/15m, Chainlink wins.
  - Then the information mechanism is "skew to each market's own settlement source", and the posture extends to
    every family with a family-specific reference.
  - If Chainlink wins everywhere, the engine reads one feed. Its Binance-settled fills should then show a basis loss
    that can be measured.

### B3. The posture is a state with inertia, scored on the wrong unit (strong form of X50, X71 and D2)

- **Hypothesis.**
  - The quote-side posture is a public-input state machine, not a fresh sign at every report. The engine keeps its
    current favoured outcome until the Chainlink edge crosses a band (+theta / -theta) or holds for k reports.
  - Per-fill scoring mixes this up with the clustering of one taker order across three wallets.
  - The right unit is the taker event or the re-price pass, with own-history baselines next to the market-only
    ones.
- **Why it fits.** Critique 3:
  - after a posture flip the side switches in only 45% of cases (8% without a flip);
  - at |edge| <= 1 c the accuracy is 0.33;
  - per event the posture scores 0.801, against 0.854 for "same side as the previous event";
  - window-weighted it scores 0.772;
  - the R5 / X50 posture AUCs (Up 0.67, Down 0.72) also suggest a lag between the edge and the at-touch state.
- **Test.**
  1. On the shared recorder for 10-31 12:18-18:00, build the posture from public inputs only: Chainlink publish ms
     from dy_rtds where present, else the stamp convention.
  2. Fit (theta, k), plus an optional EMA of the edge, on live BUILD 12:00-15:00.
  3. Score on 15:00-18:00 and on the next development blocks:
     - per taker event (fills on the same side within 100 ms collapsed);
     - per window;
     - on switch events only;
     - per re-price pass (which outcome's 500 goes to the touch).
  4. Baselines on the same units:
     - market-only;
     - own-inventory-only (held-more side);
     - own-history (previous event side).
  5. Pre-register the unit and the baselines now, so that the examiner's own-inventory baseline is not a surprise.
- **Data.** Shared recorder `q` and `x`, dy_rtds, the per-fill table, and the full-depth recording when BTC 5m is on.
- **Signature if true.**
  - The hysteretic posture reaches >= 0.85 per event and >= 0.80 on switch events, and beats the previous-event
    baseline.
  - The <= 1 c bin rises from 0.33 toward the overall rate.
  - The quote-unit AUC (0.748) rises when the posture state replaces the raw edge.
- **If false.** If the previous-event baseline still wins, the side is mostly a window-level choice. Then decode the
  window-level choice (B4).

### B4. A window-level anchor that the fair does not carry: the failing windows (new; strong form of the "posture fails in some quarter hours" next step)

- **Hypothesis.**
  - In some windows the engine's posture is set by a per-window quantity that the RE's fair does not contain.
  - Candidates:
    - a drift or momentum term (the recent Chainlink or futures trend);
    - a provisional strike for orders posted before the open (X61);
    - a different vol lookback per window;
    - a cross-market anchor (the 15m or hourly position, or Kalshi for 15m).
  - Because of it, whole windows go against the edge (0.00-0.14 accuracy), while the same rule is 0.85-1.0 in
    others.
- **Why it fits.**
  - Failures are wholesale by window (5m 14:55 0.00, 15m 14:45 0.14, 5m 14:10 0.09) and cluster in time
    (14:50-14:57 across three markets).
  - No global vol scale repairs them without breaking others (critique 4).
  - The 15m posture drops to 0.71 in the last 5 minutes of the window (n 152), against 0.92 earlier.
  - Fills against the posture in failing windows still lose (-16%), so this is a state of the engine, not better
    information on average.
- **Test.**
  1. For each window of 10-31 12-18, and of every later development block, find the shift of the reference (in
     Chainlink dollars or in z) that maximises agreement with the cluster's taker events. This is one parameter per
     window, used as a diagnostic only.
  2. Regress that shift, on BUILD windows, on public candidates computed at the window open or rolling:
     - the Chainlink and futures returns over 30-300 s;
     - Gamma priceToBeat minus the Chainlink spot at the open;
     - 60/300/900-s realised vol and DVOL;
     - the 15m-implied 5m fair gap (X60);
     - the Kalshi gap for 15m.
  3. Freeze the best single term and score it on VALIDATE slices.
- **Data.** Shared recorder, dy_rtds, Binance futures 50-ms series, Kalshi trades (public), Deribit DVOL, Gamma.
- **Signature if true.**
  - One public term explains >= 70% of the per-window shift variance on BUILD.
  - The frozen term lifts the 12:00-15:00 and 16:30-18:00 slices to >= 0.80 without lowering 15:00-16:30.
  - If it is momentum, the shift has the sign of the recent trend in every failing window.
- **If false.** If no public term explains the shift, the failing windows are an own-state or operator effect. Report
  their share of fills and PnL as the unexplained part of the side.
