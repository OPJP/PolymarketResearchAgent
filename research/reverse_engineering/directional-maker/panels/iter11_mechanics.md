# Panel after iteration 11: mechanics and on-chain forensics

Lens: how the orders are built and what the engine's own clocks and order types do to the side metric. I focus on the
weekly k cycle (the main new finding), on what the fill-weighted side metric is made of, and on the one natural
experiment the next development blocks offer. Written 2026-11-01, 01:30-02:30 UTC.

**Data I used.** Development data only, all on disk from the RE's extractions:
- `it9/volhist_{build,study,validate}`: every BTC 5m maker BUY fill, with the frozen posture inputs (Binance stand-in,
  block clock).
- `b1_cluster_orders_{study,valid}`: lot calldata, with original size, limit and salt.
- `exam/windows_5m`.
- `activity_*` and `exam/activity_*`, cut at 10-31 00:00.
- A pilot I fetched myself through `PolymarketData().market_trades(taker_only=False)`: full maker-row tapes of 24 BUILD
  windows (6 each on 10-12, 10-17, 10-19 and 10-22, 13-18 UTC).

STUDY is read case by case. VALIDATE is read only as per-day or per-phase aggregates. I did not open `.cache/live/sealed/`
or any sealed block. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it11m\`:
`kcomp.py`, `kwallet_tau.py`, `entrydecomp.py`, `entrytime.py`, `restartstep.py`, `pricehist.py`, `pricehist2.py`,
`deeppnl.py`, `sidestate.py`, `clockdrift.py`, `calib.py`, `rebate.py`, `makers_pilot2.py`. Run them from the repo root.

## What my checks found

1. **The cycle is one shared state, and it is set before the entry.**
   - The favourite share of each wallet's fills moves together every day. On all 22 days (10-09..30) the three wallets
     are within 0.08 of each other. Examples: 10-12 0.34 / 0.35 / 0.28; 10-17 0.67 / 0.68 / 0.68; 10-30 0.27 / 0.24 /
     0.25.
   - The cycle is in the window's first fill. The entry favourite share per day runs from 0.31 to 0.65. Fills per window
     after a favourite entry and after an underdog entry are about equal (e.g. 10-29: 11.8 vs 12.4; 10-17: 6.1 vs 6.9).
     So the follow-up quantity does not carry the cycle.
   - Entries in the first 10 s after the open already show it: favourite 0.36 (VALIDATE), 0.41 (Mon-Tue of weeks 1-3),
     0.51 (Wed-Sun).
   - Composition does not explain it. Within every time-left bucket and every price band the favourite share shifts.
     Inside the 0.15-0.85 band the daily favourite share runs 0.33-0.69. In the decided-window bucket
     (|mid - 0.5| > 0.4) it is 0.19 on VALIDATE, 0.25 Mon-Tue and 0.38 Wed-Sun.
   - So the cycle is a parameter or input shared by all three processes. It is not per-process learned state.
2. **The step is not at the 01:00 restart.** I compared 21:00-01:00 with 01:00-05:00 around every daily restart
   (`restartstep.py`).
   - No weekday shows a consistent step at 01:00.
   - Monday 10-26: favourite share 0.61 before the restart, 0.57 after it, 0.45 by 13:00-01:00. The RE's 6-h blocks for
     that Monday read 1.0 → 1.4 → 1.7.
   - Monday 10-12: Sunday night was already high-k.
   - So "reset at the Monday restart" is not established. The rise comes during Monday.
3. **Clock drift is ruled out.** The one-fifth class (100/12 rungs) is a time-left band on the engine's own clock, so it
   is the cleanest reading of that clock.
   - On every lot day its fills span tau p05 49.8-61.3 s and p95 108-116 s (10-30 136.6 s, n 48).
   - This holds across the 10-26 step, i.e. within about 5 s. A tau error that small cannot produce the k change.
4. **About a fifth of the cycle on VALIDATE is a separate order type: longshot bids at ≤ 0.10 on the losing outcome
   of decided windows.**

   | | BUILD | STUDY | VALIDATE |
   | --- | --- | --- | --- |
   | share of fills with limit ≤ 0.10 | 14.9% | 9.8% | 26.2% |
   | share of filled orders (order hash) | | 7.8% | 20.3% |
   | fills per order: deep / mid-price | | 2.62 / 2.10 | 3.15 / 2.35 |
   | share of 500-class fills that are deep | | 9.2% | 24.6% |
   | share of 250-class fills that are deep | | 0.7% | 26.0% |
   | share of 62-class fills that are deep | | 6.1% | 16.6% |
   | share of other-size fills that are deep | | 27.2% | 41.6% |
   | return on these fills | +22.6% | -36.8% | +13.5% |

   - By day the deep share runs from 3.9% (10-24) to 32.5% (10-30).
   - These fills are 2.3% of VALIDATE cost and about 10% of the cluster-window PnL variance (corr 0.21 with the window
     total).
   - So they matter for the per-fill side metric, not for the money. The counterparties are takers buying the
     near-certain favourite at 0.90-0.99 by complement mint.
   - Fill weighting inflates the cycle. The order-weighted favourite share is 0.56 / 0.384 (STUDY / VALIDATE), against
     a fill-weighted 0.514 / 0.312.
5. **Even an oracle k leaves the per-fill side near 0.70.** `sidestate.py` uses the Binance stand-in on the block clock,
   with the k grid 0.5-3.5 and the best k per day chosen on that day's own fills (an upper bound).

   | | in play | decided windows | pooled |
   | --- | --- | --- | --- |
   | BUILD | 0.632 | | 0.625 |
   | STUDY | 0.600 | | 0.597 |
   | VALIDATE | 0.650 | 0.796 | 0.690 |
   | VALIDATE, cheaper-side baseline | 0.629 | 0.812 | 0.679 |
   | VALIDATE, frozen k = 1.4 | | | 0.645 |

   - Decoding the cycle is worth about 3-5 points per fill. On the RE's real-Chainlink match clock that is about 0.72-0.75.
   - The remaining 0.05-0.08 to the 0.80 bar is in which rungs the takers reach, not in the scale.
6. **Competition for the touch.** In my 24 BUILD windows the cluster is only 1-4% of the maker shares on either side of
   the favourite's book:
   - 678-871 distinct makers per 6 windows.
   - 90% of maker rows are BUYs.
   - Single competitors are strongly one-sided at up to 10% of a side: 0xee65685d on 10-17 is 10.3% of the
     favourite-bid side and 0.4% of the favourite-ask side.

   The RE's statement "the side change is in the quote" therefore rests on the takers alone. Nobody has looked at the
   cluster's quote on both outcomes on low-k and high-k days. Salt adjacency is confounded, as the RE says.
7. **Nulls, so nobody re-runs them.**
   - **Rebates.** MAKER_REBATE rows land daily at 00:45:03-00:55:18 UTC for all three wallets (15 min before the
     restart). The daily rebate is unrelated to the next day's favourite share (Spearman +0.16, n 21).
   - **Calibration.** A favourite-longshot calibration controller is contradicted by its own sign. The EWMA of
     previous days' favourite excess return vs the favourite share is Spearman -0.56 (n 21); since Monday it is -0.47
     (n 18). A calibrating learner would give a positive sign. I record this as an anomaly; it may be a vol regime proxy.
   - **Time-left exponent.** σ ∝ τ^a with a in {0.5, 0.75, 1.0, 1.25} gives no stable a across days.

## Critique

1. **The investigation is chasing a few points with the k cycle and has not said so.**
   - With the best k per day chosen in hindsight, the per-fill side reaches only 0.63 (BUILD), 0.60 (STUDY) and 0.69
     (VALIDATE) on the historical clock (finding 5).
   - The cycle explains the STUDY/VALIDATE break, the halves and the replication risk. It cannot by itself reach the
     0.80 side bar.
   - The next steps should state the per-fill ceiling of the posture family, and the share of fills on rungs that no
     single-side rule can call. These are the near versus far rungs, the pairing bids and the decided-window longshot
     bids.
2. **"The side change is in the quote" is inferred, not observed.**
   - The evidence is that the same takers filled the cluster on the other side while the market's demand did not move.
   - The cluster is 1-4% of maker volume, and one-sided competitors exist. A change in who holds the favourite-bid touch
     would give the same taker picture.
   - The quote has to be read directly, on both outcomes, on a low-k and a high-k day.
3. **The plan does not use the single best natural experiment of the study.**
   - The 11-02 00:00-06:00 UTC block is a development block (day 2, block 0). It contains the Monday restart, which
     carries the weekly sweep: 01:00 UTC, or 02:00 if the cron follows ET after the 11-01 DST change.
   - The own full-depth recorder dx_clob runs to 11-03 00:00. So the ladder on both outcomes can be read second by second
     through the weekly reset. The 11-02 12-18 development block (Monday US session) follows.
   - The next exam's sealed blocks also straddle this Monday. If k steps there, the frozen k = 1.4 is wrong for part of
     the exam whatever its value now. That makes the measurement exam-critical, not exploratory.
4. **The fill-weighted side metric mixes decisions.**
   - On VALIDATE, 20% of filled orders are deep longshot bids filled about three times each by near-certain-favourite
     buyers.
   - Pairing bids are 11-14% of fills, and far-side 62/250 rungs are 71% opposite when next to 500s.
   - Each type has its own side law. The weekly cycle shows strongly in the deep type, which the posture describes only
     indirectly (through a large k).
   - Score the side per order hash and per order type, and report the fill-weighted number beside it.
5. **The restart narrative is ahead of the data.** "k jumps after the Monday 01:00 restart" does not survive a ±4 h
   window around 01:00 (finding 2): the rise happens during Monday. Use "a weekday/weekend state" until the quote-level
   series shows where the step is.

## Proposals (ranked by the chance they close the gap)

### P1. Read the engine's scale off its own ladder, second by second, through the Monday reset (11-02 00-06 live) and over four more weekly cycles in July (pmxt) (new; strong form of X79, X27/X30, X87 and the RE's k-by-day)

- **Hypothesis.** The posture's scale k is one engine-wide parameter. It has a definite update law, and the law is one
  of:
  - (a) a value pushed at a scheduled operator event (the Monday restart and sweep, or a weekday/weekend schedule);
  - (b) a running estimate of a public input (a vol, trade-count or message-rate statistic) that differs from v300;
  - (c) a weekly retrained model, with a step at deployment and drift through an input normalisation;
  - (d) a drawdown or PnL controller. Week 2 lost and decayed; week 3 gained and did not. The RE's PnL-since-Monday
    Spearman is +0.31.

  Each predicts a different shape of k(t) at second-to-minute resolution. Per-day best-k fits on fills cannot see that
  shape: flat accuracy curves, sd(log k) 0.77, taker-selected.
- **Why it fits.**
  - The three wallets move together within 0.08 every day.
  - The cycle sits in the entry and in every time-left and price bucket, so it is set before any fill.
  - The step is not at 01:00 (findings 1-2).
  - The engine's clock is stable (finding 3), so the scale itself changes.
  - The ladder center F* was already measured live (X27/X30: top 500 pairs, h* 0.06). F* = (1 + top Up bid − top Down
    bid) / 2 is independent of the half-spread when that spread is symmetric.
- **Test.**
  1. **Live (dx_clob, RTDS).** Blocks: 10-31 12-18 (Saturday, k ≈ 1.4 per fill), 11-01 06-12 (Sunday), 11-02 00-06
     (Monday reset) and 11-02 12-18 (Monday US session).
     - Every second, read the top same-class rung on each outcome. Take the 500 class, or the session class off-session.
     - Compute F*(t) and the Chainlink x(t) = ln(S/K) from the report at the RE's publish lag.
     - Invert the scale where |F* − 0.5| > 0.05 and τ > 60 s: k(t) = x / (v300 · √τ · Φ⁻¹(F*)). Take the median per
       minute.
     - Fit a step model with candidate breaks at the salt-counter resets (restart log from the calldata of filled
       orders) against a smooth model.
     - Regress log k(t) on log v_N for N = 30-3,600 s (Binance spot, futures and Chainlink), the Binance trade count,
       the RTDS message rate and own cumulative PnL since the restart (labelled own state).
  2. **July (pmxt, X87; same engine family, 07-16..08-10 = 3.5 weeks, 4 Mondays).**
     - First the cheap part: best k per day from the July fills with Binance 1-s klines, as `k_by_day_bn.py` does. Does
       a weekly cycle with a Monday rise exist in July?
     - Then 2 h per day (13-15 UTC) of unaggregated books reduced to per-second top-of-ladder by size fingerprint
       (500/300/50), giving the same k(t) series.
     - Restart times come from the July calldata salts (the RE has 150 txs; sample about 50 per day).
  3. **Joint epochs.** Check whether the k(t) breaks coincide with the other configuration parameters: night size
     250 ↔ 62 (X107/X113), the one-fifth band, and the salt slope (orders/s per wallet = rungs per pass × pass rate).
- **Data.**
  - dx_clob and dx_rtds/dy_rtds, plus the shared RTDS recording, for the four development blocks.
  - The calldata salts of the blocks' filled orders.
  - pmxt range reads (about 67 MB per hour of BTC 5m, streamed and reduced), July Binance 1-s klines and the July
    activity.
- **Signature if true.**
  - (a): k(t) is flat within ±15% inside an epoch and steps by more than 30% at one operator event, on 11-02 and on
    July Mondays, with the size class switching at the same instant.
  - (b): one v_N (or a count statistic) explains R² ≥ 0.7 of log k(t), with no step at restarts.
  - (c): a step at deployment, followed by drift that tracks a normalised input.
  - (d): k falls after cumulative losses within an epoch, with the lag consistent across epochs.
  - If none of these fits, the quantitative account is k(t)'s unexplained variance at minute resolution. The RE then
    needs a version-aware rule with the state estimated online (own-state, reported separately).
  - Any of (a)-(c) gives the exam a point-in-time k and removes the halves/replication risk of the side component.

### P2. Decided-window longshot bids as their own order type; score the side per order hash and per window state (new; strong form of X92/P4-iter10, on the side metric's composition)

- **Hypothesis.** In decided windows the engine keeps BUY rungs at 0.01-0.10 on the losing outcome. These are full
  schedule rungs (500/250/62), each filled about three times by takers buying the near-certain favourite. How deep and
  how persistently it posts them is a configuration: a ladder floor or a depth N, or quoting the loser at all. That
  setting moved with the weekly state. Over all fills, this type makes the cluster look like a high-k (underdog) buyer
  on VALIDATE.
- **Why it fits.**
  - Finding 4: 20.3% of VALIDATE filled orders against 7.8% on STUDY.
  - Every rung class shows it: 24.6% of 500-class fills and 26.0% of 250-class fills on VALIDATE, against 9.2% and 0.7%
    on STUDY.
  - It amounts to 2.3% of cost and about 10% of PnL variance.
  - The cheaper-side baseline already scores 0.81 in decided windows. The examiner's market-only baseline is strong
    exactly where these fills sit.
- **Test.**
  1. **Opportunity-normalised capture, per day (BUILD, STUDY, and VALIDATE as aggregates).**
     - capture = the cluster's ≤ 0.10 fill shares / clean-tape taker BUY shares at ≥ 0.90 in the same windows.
     - The opportunity is the taker volume.
     - Look for a step in capture at constant opportunity.
  2. **Price law of the deep orders (calldata limits).**
     - Is the limit on a fixed grid (0.01, 0.02, 0.03, 0.05, ...) or is it the last print − 0.01?
     - Check the 0.001 dynamic tick below 0.04.
     - Do the limits move with τ and x as Φ(x / (kσ√τ)) − h would?
  3. **Live dx_clob.** In decided windows, do 0.01-0.10 rungs rest for seconds to minutes? What are their lifetimes, and
     are they re-posted every pass? Compare with the near-side touch posts (~0.7 s).
  4. **Re-score the side component** per order hash and per type: posture rung, deep longshot, pairing bid, far-side
     62/250. Score by window state (in play vs decided), with the fill-weighted number beside it.
- **Data.** volhist, `b1_cluster_orders_*`, the lot and BUILD taker tapes, and dx_clob for 11-01 06-12 and 11-02.
- **Signature if true.**
  - Capture steps at a weekly state change while the opportunity is flat.
  - Deep limits sit on a static grid with lives far above the near side's.
  - Removing this type shrinks the STUDY/VALIDATE side swing in the in-play band.

  If instead the limits track the k-digital, the type is the posture at large k. It is then still reported separately,
  because its fill multiplicity distorts the per-fill score.

### P3. Read the cluster's quote on both outcomes at every match from the taker's limit: complement-aware level censoring from all-match calldata (strong form of X67; decides "quote vs competition" and labels the quote unit historically)

- **Hypothesis.** For each matchOrders transaction, the taker struct gives the taker's limit, size, side and token, and
  the maker list gives each matched price and maker. Price priority across the direct and complement books then bounds
  where the cluster's top bid on each outcome sat at that instant.
  - A taker BUY of A that matched up to price L′ consumed every A-ask ≤ L′ and every B-bid ≥ 1 − L′ ahead of it.
  - So the cluster's B-bid was at or above the exhausted level if it was matched. It was below that level, or behind the
    queue at it, if it was not matched while the level was fully cleared.

  At thousands of instants per day, this gives a historical, taker-independent read of the cluster's top rung on both
  outcomes.
- **Why it fits.**
  - The side-change claim rests on takers (critique 2).
  - The cluster is 1-4% of maker volume, and one-sided competitors hold up to 10% of a side (finding 6).
  - X67 was set aside because the tape lacks the levels. The calldata has them, and the decoder exists (b1 code).
  - The RE already holds 10,500 public txs of Monday 10-26 (`pub1026`), the step day. The pilot can run today.
- **Test.**
  1. Sample all-match calldata: 15 min per 6-h block over BUILD weeks 1-2 and the lot (about 40k txs; keep the decoded
     fields only).
  2. Per match, label the cluster present at the exhausted level, absent with the level cleared, or uninformative.
  3. Per day, compute P(cluster present | favourite-bid level cleared within 1 tick of the touch) and the same for the
     favourite-ask level (underdog bid).
  4. Compare low-k days (10-17, 10-22..25) with high-k days (10-12, 10-19..20, 10-27..30, VALIDATE as aggregates).
  5. Second use: the same labels give an inverse fit of F* on the lot and a quote-unit presence label at match instants.
- **Data.** eth_getTransactionByHash in batches (drpc, polite), the RE's matchOrders decoder, Gamma tokens.
- **Signature if true.**
  - Quote: on high-k days the cluster is absent from cleared favourite-bid levels in ≥ 90% of cases and present at the
    underdog-bid touch, and the reverse on low-k days.
  - Competition: the cluster is present on both sides at similar rates on all days, and only its queue share against
    named competitors moves. The k cycle is then not an engine parameter at all.

### P4. Measure the per-fill side ceiling from the ladder's geometry: near-side (touch) vs far-side (deep, pairing, longshot) hits, and the side unit to claim (new; the quantitative account behind the side bar)

- **Hypothesis.** The ladder is two-sided, with near-side posture rungs at the touch and a far side made of deep 62/250
  rungs, pairing bids and longshot rungs. A taker's size and direction decide which rung it reaches. For any rule that
  names only the near side, the per-fill side is capped by the near side's share of fills. That share is about
  0.75-0.80 live (78% of confirmed filled orders were at the touch, X33) and lower on the lot. The side claim then
  belongs on the units where one decision is made: the window entry, the pass (salt-adjacent order group) and the
  order.
- **Why it fits.**
  - Finding 5: even an oracle k gives 0.60-0.69 per fill historically.
  - 71% of 62/250 fills next to 500s are on the other outcome.
  - Pairing bids are on the under-held outcome 100% of the time.
  - The entry follows the posture 0.744, and 0.82 where it agrees with the market-only taker-flow complement.
- **Test.**
  1. On the live development blocks (dx_clob), classify each cluster fill by its rung's position at the match: at the
     touch on the posture side, deep on the posture side, or far side (any depth).
  2. The oracle near-side accuracy is the share of fills in the first class. Report it per class, per wallet and per
     session.
  3. On the lot, use the calldata limit vs the last clean trade in execution order (R7-price clock) as the near/far
     proxy. Within one tick of the anchor is near; deeper is far.
  4. Score the frozen posture on near fills only and on each decision unit (entry, pass, order).
- **Data.** dx_clob blocks, R7 in-block anchors, `b1_cluster_orders_*`.
- **Signature if true.**
  - The near share is ≤ 0.80. The posture on near fills reaches ≥ 0.85 (live) or ≥ 0.80 (lot, region D 0.93 for the
    500s).
  - Then 0.80 per fill is structurally unreachable for a one-side rule. The side component should be stated per entry
    or pass, with the far-side share as the measured unexplained part.
  - If the near share is ≥ 0.9, the per-fill gap is in the posture, and P1 is the route.

### P5. One configuration vector, one change log: align every operator-visible parameter switch on a common clock (new; joint form of X107, X113, X82 and P1 step 3)

- **Hypothesis.** The engine reads one configuration that changes at discrete times for all three wallets at once.
  It holds k, the night size class (250 ↔ 62), the one-fifth band, module on/off and the ladder floor (P2). The switch
  times are the operator's schedule, and the schedule is public through on-chain side effects. Those side effects are
  salt resets (process restarts), the salt slope (rungs per pass), the size class of the first order after a gap, MERGE
  batch timing, and sweep timestamps (amounts and recipients are never used).
- **Why it fits.**
  - On 10-23 the 62 → 250 switch happened at ~04:20:56 UTC in two wallets within the same second, with no counter
    reset (iter-10 panel).
  - The night size changed between Fri 10-23 and Mon 10-26, together with the k step.
  - The k cycle is synchronous across the wallets (finding 1) but not at 01:00 (finding 2).
- **Test.**
  - Minute-resolution change points per wallet on:
    - the calldata size class of filled orders;
    - the per-hour favourite share (or k from P1);
    - the deep-order share (P2);
    - the salt slope between consecutive fills.
  - Coverage: the lot plus BUILD (sample about 50 txs per hour for salts), and July (pmxt calldata).
  - Then a permutation test: do the change points of different parameters coincide (within 5 min) more often than
    under random shifts?
- **Data.** Calldata samples of filled orders (BUILD needs a fetch; lot on disk), volhist, block timestamps.
- **Signature if true.**
  - At least 3 parameters switch together at the same instants across wallets (p < 0.01 against shifted change points).
  - The switch instants fall on a small set of clock times (e.g. 00:00 ET, 04:20 UTC, Monday morning).
  - The configuration epoch is then the selector of the side and size sub-rules, and its schedule can be frozen
    point-in-time.
