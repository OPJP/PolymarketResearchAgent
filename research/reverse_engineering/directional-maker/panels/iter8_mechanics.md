# Panel after iteration 8: mechanics and on-chain forensics

Lens: how the orders are built: the pricer behind the posture, the ladder depth, the salt counter, the order structs
of the takers who fill the cluster, and inventory limits. Written 2026-10-31, about 21:00 UTC.

**Data I used.** All of it is development data, read only from the RE's extractions and the dev-block recorders.
- Live BUILD (10-31 14:06-15:00 UTC), case by case:
  - `it6/fill_side_*` (the per-fill posture table);
  - `it6/ev_*` (the raw book) and `it6/touch_*`;
  - `it6/m1inv_*` (top rungs per second);
  - `it6/confirmed_*`;
  - `dm_rtds` through `pres_live.iter_dm`;
  - Binance spot 1-s klines from the REST API for 13:00-16:30.
- Live VALIDATE (15:00-16:30): aggregates only, and two pre-specified variants only. Sources:
  - `fill_side`;
  - `calldata/allmatch1793460000_*` (15:20-15:40).
- BUILD history 10-09..22: the three wallets' activity files.

I did not touch `.cache/live/sealed/` or any sealed block. Scripts:
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it8m\`
(`vol_lookback.py`, `vol_lookback_val.py`, `strike_cand.py`, `capped_peg.py`, `ratchet_artefact.py`, `burst_order.py`,
`size_role.py`).

## What my checks found

1. **The posture side fails where the frozen pricer's volatility spikes. In those windows the cluster's own quote, not
   a sweep, sat on the "wrong" side.**
   - Live BUILD, per window. The failing windows are all near the money (median z between -0.14 and -0.46):
     - 5m 14:10: 0.09 (n 11);
     - 15m 14:45: 0.14 (n 29);
     - 5m 14:50: 0.52 (n 67);
     - 5m 14:55: 0.00 (n 24).
   - The passing windows have |z| of 0.7-1.7.
   - In 14:45-15:00 the 300-s realized vol was **2.0-2.4 times the 1-h vol**. Before 14:45 the ratio was 0.54-0.95.
   - 90% of the fills against the posture were at the touch, as were 95-100% of the fills with it. The cluster's own
     500 sat at the touch on the side the rule calls disfavoured. The taker sweeps did not reach a deep rung.
   - Implied bounds. For each fill I took σ*, the per-√s vol at which the Chainlink digital equals the mid; the fill's
     side then says whether the engine's σ is above or below σ*.
     - 14:45-15:00: 24-54 fills per window require **σ_e below about 0.46-0.51 bp/√s (minimum 0.34-0.42), while 1.4 ×
       v300 was 0.65-0.84**.
     - 14:25 and 14:40: the bounds pin σ_e to **0.17-0.19, equal to 1.4 × v300 (0.18)** and below 1.4 × v3600
       (0.27-0.31).
   - So the engine's vol follows the short realized vol in calm minutes and does not spike with it.
   - Fixed lookbacks do not fix it (same fills, spot vol):

     | vol estimator | live BUILD (n 262) | 14:45-15:00 | live VALIDATE, aggregate (n 1,406) |
     | --- | --- | --- | --- |
     | 1.4 × v300 (frozen form) | 0.618 | 0.344 | 0.814 |
     | 1.4 × v3600 | 0.817 | 0.836 | 0.754 |
     | 1.0 × v900 | 0.817 | 0.943 | not run |

     No fixed lookback works in both regimes. The engine's estimator is something else: a cap, an EWMA, a
     per-window value, or Chainlink-based.
2. **The strike is not the cause.** Candidate strikes leave the failing windows failing:
   - the Chainlink report at the start (not the TWAP);
   - TWAP-60 stamped ±1 s;
   - the mean of the last 60 reports.

   5m 14:55 stays at 0.00. Its Chainlink-at-start strike is $49 lower than the TWAP, which moves the fair the wrong
   way.
3. **The ladder below the touch is not a cap at "fair minus a margin".** I split the RE's per-second top rungs (5m, live
   BUILD) into at-touch seconds and below-touch seconds.
   - Below-touch seconds: 494 for Up, 440 for Down, a median 5-7 c under the touch. Their offset to the mid regresses
     on the Chainlink edge with slope 0.175 (Up) and 0.086 (Down), R² 0.10 and 0.03.
   - Only 8% of below-touch rungs are within a tick of (fair - constant), against 26% for (mid - constant).
   - At-touch seconds track the touch (86-95% within a tick of mid - constant).
   - Conclusion: the deep level is a spread rule around the mid, not a fair-value cap.
4. **The half-spread h behaves like a spread on the digital's risk.**
   - 5m, live BUILD, 544 seconds: corr(h, p(1-p)) 0.45, corr(h, φ(z)/√τ) 0.38, corr(h, |z|) -0.36. OLS R² is 0.29
     (residual sd 0.030, against a raw sd of 0.036).
   - 15m: R² 0.18.
   - This uses the frozen 1.4 × v300 pricer, which is wrong in spikes (finding 1).
5. **The "creeping ratchet" is a real price move.**
   - It is not a pairing artefact from same-price re-signs: only 2.3% of the 7,030 BUILD pairs have a same-price
     re-add within ±20 ms, and dp > 0 in 97%.
   - Raw example (5m 14:20, Up book). Three -500 at 0.91 (t = 293, 295, 298 ms) and three +500 at 0.93 (297, 301,
     312 ms), the touch: one three-wallet step to the touch.
6. **There is no hard per-window position cap.** BTC 5m, 10-09..22, per wallet, window and side, crossings before 180 s.
   P(no further fill on that side after the cumulative shares cross a threshold) rises smoothly:

   | threshold (shares) | 400 | 450 | 500 | 600 | 800 | 1,000 |
   | --- | --- | --- | --- | --- | --- | --- |
   | P(no further fill) | 0.44 | 0.46 | 0.47 | 0.45 | 0.50 | 0.54 |

   The pile-up of totals at 500-600 shares (657 against 451 at 400-500) is one fully consumed 500 order. It is not a
   stop rule.
7. **Book events cannot be labelled by wallet from the match order.**
   - In the 10-31 calldata only 39 of 1,739 cluster maker txs contain two or more cluster wallets at one price (2%).
   - Their maker order is not fixed. Mo-money comes before almach in 74% and before bosona in 90%; almach and bosona
     split 50/50.
8. **A weak lead: the takers who pay may be slow, not fast.** VALIDATE aggregate, 15:20-15:40, 5,512 taker orders.
   - Median sign-to-match latency of takers who fill the cluster against those who fill others:
     - Magic proxy: 999 vs 557 ms;
     - Safe: 1,502 vs 1,075 ms;
     - EOA: 840 vs 880 ms;
     - type 3: 657 vs 684 ms.
   - Share of orders slower than 1 s: 0.445 vs 0.418.
   - The populations X66 found paying (Safe, front-end) are the slower ones.

## Critique

1. **The side failures are read as "another driver". They are a mis-specified pricer.**
   - The RE concluded that the failing quarter hours "are not explained by the Chainlink noise level, the at-touch share
     or the edge size", and that "there are windows where the engine's side has another driver".
   - The failing fills are the engine's own at-touch quotes, near the money, inside a vol spike. In those minutes the
     fills bound the engine's σ to half of what R6's pricer uses.
   - The rule's input (Chainlink) is right. Its vol estimator is wrong in exactly the windows that break replication
     (the 14:45 quarter hour, and probably 16:30-18:00).
   - Scanning a constant multiplier (x0.7 / x1.4 / x2) cannot find this. In spikes the error is a ratio of 2-2.4, in
     calm minutes about 1, so a constant scale trades one regime against the other. That is what the scan showed.
2. **Every downstream edge feature inherits the same error.** These all use the same digital with 1.4 × v300:
   - the quote-unit model (gain +0.076, carried by the Chainlink edge);
   - the print-selection posture variables;
   - R5's stack;
   - the M1 inversion.

   In vol spikes the edge's sign is wrong near the money. The quote-unit gain and the selection numbers are measured
   mostly in calm hours. They will shrink on any exam block with a spike, unless the pricer is decoded.
3. **The ladder-depth problem is being sent to a state machine before the spread rule has been tried.**
   - Below-touch rungs do not track the fair (finding 3), so a cap model is out.
   - But h co-moves with the digital's risk (finding 4). No regression of the depth on the pricer's own risk terms has
     been run; X30 only measured h's quantiles.
   - Try the memoryless spread rule on the decoded pricer first. Then model what remains as a state.
4. **The presence route should be pre-registered on the decision unit that already works.**
   - The posting hazard on exact public clocks reaches 0.826, against a 0.753 trade-clock baseline (D2). It is the
     cluster's own action, and the publish clock is cluster-specific (X47: other makers do not respond to it).
   - Write it down before 11-01 06:00 as a candidate presence unit, with its activity baseline.
   - Check that the sealed-block recorders store what it needs: dy_rtds publish ms, and exact-500 adds at the depth
     the bursts occur. examrec keeps only deltas within 3 ticks of the touch, and the shared feed is aggregated.
5. **The outcome replay (X64) depends on point 1.** A strict-fill replay with the frozen pricer will buy the market
   favourite in spikes exactly as the wallet did. But it will also be wrong in calm windows where the wallet was right,
   whenever its σ differs from the engine's. Decode σ_e before building the replay, or its PnL correlation is capped
   by the side errors.

## Proposals (ranked by the chance they close the gap)

### M1. Invert the engine's volatility (and price) from its own side decisions: an interval-censored pricer-state series (new; strong form of B3, H14, X13)

- **Hypothesis.** The engine prices each window with a Chainlink digital whose σ_e comes from an estimator that does not
  follow the 300-s realized vol in spikes. Candidates:
  - a long EWMA;
  - a capped short estimator;
  - a value frozen per window at the open;
  - vol from 1-s Chainlink changes or from 1-min bars.

  R6's posture misses whole near-the-money windows during spikes because its σ is 2-2.4 times σ_e there.
- **Why it fits.**
  - Findings 1 and 2: failures near the money, in the 14:45 spike quarter hour, made by at-touch quotes.
  - Implied σ_e is below 0.46-0.51 there, against 0.65-0.84 used. It equals 1.4 × v300 at 14:25-14:40.
  - The 15m 14:45 window goes from 0.14 to 0.97 with any vol of half the size. This happens in both 15m BUILD windows.
- **Test.**
  1. Unit: every cluster maker fill on the match clock in all of 10-31 12:00-18:00 (the evaluate() slices), plus the
     per-report posture labels of X50.
  2. Bounds. For each fill compute σ*, where the Chainlink digital (Gamma strike, TWAP-60 lock-in for τ ≤ 60 s) equals
     the token mid at T. When z and Φ⁻¹(mid) share their sign, the bought side gives one bound:
     - z < 0 and bought Up: σ_e > σ*;
     - z < 0 and bought Down: σ_e < σ*;
     - mirrored for z > 0.
  3. Fit σ_e(t) piecewise-constant per minute by maximum likelihood (logistic link on log σ_e - log σ*), on BUILD time
     only (12:00-15:00).
  4. Race a pre-registered family against the implied series. Data: BUILD. The family:
     - realized vol of futures, spot and Chainlink 1-s changes over L ∈ {120, 300, 600, 900, 1800, 3600} s;
     - EWMA with half-life ∈ {60, 300, 900, 1800} s;
     - min(1.4 × v300, c × v3600);
     - frozen at the window open;
     - Deribit DVOL.

     Add a second data source: the June engine's 12.5k signed-ms orders (`code8/june_price.py`). Pick the estimator
     whose fair minimizes the June limit-price residual at the signing ms. It may be shared code across versions.
  5. Separate σ_e from the engine's price S_e with co-settling windows (5m and 15m ending together; 15m and 1h).
     - At instants when the two windows have z of opposite sign, the two readings make different predictions about
       the failing postures.
     - Our σ too high: both postures flip toward their own favourites, which are opposite directions in Up
       probability.
     - Engine price stale or low: both flip toward Down.
     - Count which pattern the failing minutes show.
  6. Freeze one estimator.
     - Re-score the per-fill side on 15:00-16:30 and 16:30-18:00 (aggregate) and pre-register it for 11-01 06-12.
       Pass mark: ≥ 0.80 pooled, in each half, and in every quarter hour with ≥ 30 fills.
     - Recompute the quote unit, the print selection and R5's stack with the new edge.
- **Data.**
  - On disk: `it6/fill_side_*`; dm_rtds, dy_rtds and dx_rtds; dm_bnf and dx_bnf; Binance REST 1-s klines; Gamma
    priceToBeat; the June calldata.
  - Coming: the 11-01 06-12 block.
- **Signature if true.**
  - One estimator lies inside the implied interval in ≥ 90% of minutes.
  - The side reaches ≥ 0.80 in 14:45-15:00 and in 16:30-18:00 without dropping below 0.83 on 15:00-16:30.
  - The quote-unit gain over activity grows to at least +0.10.
  - A large realized/engine vol ratio precedes the 16:30-16:53 losses and the 16:53 switch-off. That feeds X70: a
    vol-divergence breaker or a loss controller set off by it.

### M2. Decode the ladder depth as a spread on the digital's risk, on the decoded pricer (new; strong form of X30, X19, B3)

- **Hypothesis.** At each re-price pass every rung sits at mid_s + β(fair_s - mid_s) - h_k. The half-spread is h_k =
  a_k + b · φ(z_e)/√τ (+ c · p(1 - p)), the move of the digital fair over one re-price interval. The posture side's
  top rung is lifted to the touch. The deep rungs are this spread rule, not a cap and not noise.
- **Why it fits.**
  - Finding 4: corr(h, p(1-p)) 0.45 and corr(h, φ(z)/√τ) 0.38 with the wrong σ in spikes.
  - X30's h is 0.083 in the last minute, against 0.06 overall.
  - Below-touch rungs ignore the fair (finding 3), so the depth must come from a spread term.
  - The RE's 21% within a tick fits the level with no risk term.
- **Test.**
  1. Unit: each publish-triggered pass (bursts in [P, P + 200 ms] on dy_rtds publish ms; on 10-31 14:06-16:30, the
     stamp + 1.08 s proxy).
  2. Labels: the top-rung offset below the mid per side, the second rung's offset, and the pair sum.
  3. Regressors:
     - φ(z_e)/√τ and p(1-p) with M1's σ_e;
     - τ, the book spread, and the number of other makers' adds at the touch in the last second;
     - own state, reported separately: the window inventory and the time since the last own-side fill.
  4. Fit on BUILD passes. Score on held-out passes: within one tick of the top rung, against the touch, touch - 1 and
     the 21% anchor.
  5. Then generate the ladder from public inputs (posture + h) and score:
     - the quote unit (500 at the touch now);
     - print reach: does the print's price reach a generated rung;
     - the selection metric against the strongest activity baseline.
- **Data.**
  - On disk: `it6/ev_*` and `it6/m1inv_*` (14:06-16:30); dy_rtds.
  - Coming: the 11-01 06-12 full-depth recording (`code8/delayed_rawrec.py`).
- **Signature if true.**
  - The held-out top rung is within a tick in ≥ 50% of passes (anchor 21%), and h's R² is ≥ 0.6 in both families.
  - The generated at-touch state reaches AUC ≥ 0.82 on the quote unit.
  - Print selection reaches ≥ 0.80 with recall ≥ 50% at lift ≥ 3, and the gain over activity is ≥ 0.05. The ceiling
    with the observed quote is 0.81-0.83.
  - If R² stays near 0.3 after M1, the depth is state (A3/X71). Then M2's residual is the state machine's target.

### M3. Stale takers on the publish clock: the cluster's paid fills are orders signed before the latest Chainlink publish and matched after the re-price pass (new; strong form of the iteration-6 speed-bump check, X28 and X45)

- **Hypothesis.** The re-price pass lands 0-150 ms after each publish. Taker orders wait at least about 190 ms between
  signing and the match. So every taker who signed before a publish and is matched after it trades against the new
  posture.
  - Front-end takers (Magic and Safe, round-USD, loose limits) are slow: medians of 1.0-1.5 s.
  - Those that sell the token the new report favoured hit the 500 the engine just lifted to the touch.
  - The cluster is paid by the information in the publish, through the latency of other people's orders.
- **Why it fits.**
  - Finding 8: the populations that pay (X66) are slower when they fill the cluster.
  - The iteration-6 check measured staleness against the cluster's post time (41% signed before it), not against the
    publish that set the posture.
  - X45 pooled all takers. The front-end population is slow by construction.
- **Test.** Block: 11-01 06-12 (dy_rtds publish ms, liveall calldata of every match, the shared trade stream's server
  ms).
  1. For each match, staleness = (the latest publish at least 150 ms before the match) - the taker's sign_ms. Both are
     public at block time.
  2. Label: the match fills the cluster.
  3. Run an event study by population and by the sign of the publish's change in the token's fair.
  4. Compare returns: stale fills against fresh fills.
  5. Add staleness × posture to the print-selection model. Feed the activity baseline the same taker-struct fields
     except the publish clock, so the gain is not co-occurrence.
- **Data.** dy_rtds, the liveall calldata (`code6` extraction), the shared `clob_crypto` trades, and the cluster
  activity for 11-01 06-12.
- **Signature if true.**
  - P(fills the cluster | stale taker selling the newly favoured token) is at least 3 times the base rate.
  - Stale fills carry ≥ 70% of the PnL.
  - Print selection gains ≥ +0.05 AUC over the strongest activity baseline.
  - Otherwise (no staleness asymmetry once the population is controlled), drop it: the sellers are not reacting late
    to the publish.

### M4. Salt-counter forensics of the BTC 5m on/off switches: same process or restart, signing stopped or posting stopped (new; feeds X70, X58, X9)

- **Hypothesis.** The kind of switch shows in the per-wallet counter salt.
  - A running controller (a loss limit or a vol breaker) keeps the counter continuous.
  - It stops signing BTC 5m orders, so the signing rate steps down by BTC 5m's share at the switch. All three wallets
    switch within about 1 s.
  - An operator restart resets or jumps the counter, like the daily 01:00 UTC restart.
  - A gate after signing (orders signed but not posted, or post-only rejections) keeps the rate unchanged.
- **Why it fits.**
  - At 16:53:5x all three wallets switched off BTC 5m while BTC 15m continued.
  - The counter is a free ms-free clock of the engine's activity (16.7-17.2 orders/s per wallet).
  - No test so far separates "the engine decided" from "the operator decided". The selection component (and the
    future exam blocks, where BTC 5m may be off for hours) depends on it.
- **Test.**
  1. Fetch the calldata of the cluster's fills in all markets for 10-31 16:30-18:00 (development).
  2. Do the same around every off/on switch in BUILD and STUDY with lot calldata (b1). This covers the historical
     switch-offs and the 13:33 and 15:25 UTC returns.
  3. Per wallet, fit the salt against block time and measure at each switch:
     - the counter jump;
     - the slope before and after;
     - the lag between wallets.
  4. Compare with the 01:00 restarts as the positive control for a reset.
- **Data.** Polygon RPC (`eth_getTransactionByHash` batches), activity, `b1_orders_lot.parquet`, `code7/stale*`
  switch times.
- **Signature if true.**
  - Controller: a continuous counter, a rate drop equal to BTC 5m's share of signatures (about 40-60% of fills), all
    wallets within a second, on every historical switch. Then search the trigger among internal states: own window
    PnL, and M1's realized/σ_e ratio.
  - Operator: resets or gaps and returns at round clock times. Then the on/off belongs in the description as an
    operator schedule, with a quantitative share of the presence gap.

## Notes for the RE

- The two VALIDATE numbers above (0.814 and 0.754) are aggregates of two variants fixed before I looked: the frozen
  form, and the 3600-s lookback that fixed BUILD. Nothing was chosen on VALIDATE. M1's estimator family should be
  written down before it is fitted, and 11-01 06-12 is its first untouched test.
- My vol series is Binance spot (REST); `fill_side` used the futures mid. The two agree: my 5m BUILD accuracy is 0.668
  against your 0.664, and 15m is 0.306 in both.
- Do not spend time on these, which I checked:
  - strike variants (finding 2);
  - a fair-capped deep rung (finding 3);
  - a same-price pairing artefact in the ratchet (finding 5);
  - a hard per-window share cap (finding 6);
  - wallet labelling of the book from the match order (finding 7).
