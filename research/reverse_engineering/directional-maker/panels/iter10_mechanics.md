# Panel after iteration 10: mechanics and on-chain forensics

Lens: how the orders are built and what the inventory path does with them: the window's position from the first fill
to resolution, the size configuration, and the re-price pass seen through the salt counter. Written 2026-11-01,
00:00-00:20 UTC.

**Data I used.** Development data only, from the RE's extractions:
- `it9/volhist_{study,validate}` (every BTC 5m maker BUY fill of the lot with the frozen posture inputs on the block
  clock, Binance S);
- `b1_cluster_orders_{study,valid}`, `b1_orders_lot`, `b1_counter_study`, `b1_takers_study` (calldata);
- `exam/spot_btc_1s` and `aggfut_2026-10-26` (Binance).

STUDY (10-23..26) is read case by case. VALIDATE (10-27..30) is read **as aggregates only**. I did not open
`.cache/live/sealed/` or any sealed block. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it10m\`:
- `residual.py` / `residual_val.py`: window net position;
- `samepass.py`: salt adjacency;
- `saltclock.py` / `saltclock2.py`: historical age;
- `adverse.py` / `adverse_ms.py`: pick-off side.

## What my checks found

1. **The profit, and the outcome bar, sit in the window's terminal net position. That position is mostly set by the
   entry.**
   - Unit: wallet x BTC 5m window, all maker BUY fills, resolved.
   - Residual = Up shares - Down shares at the end. Locked pairs are split off as in A4.

   | | STUDY (1,425 wallet-windows) | VALIDATE, aggregate (2,933) |
   | --- | --- | --- |
   | var(residual PnL) / var(window PnL) | 0.73 | 0.58 |
   | corr(window PnL, residual PnL) | 0.89 | 0.80 |
   | one-sided wallet-windows (one outcome only) | 58.7% | 39.8% |
   | terminal residual side = side of the first fill | **0.855** | **0.775** |
   | same, in two-sided windows only | 0.650 (n 588) | 0.626 (n 1,766) |
   | residual side = majority of schedule-rung shares | 0.967 | 0.936 |
   | residual side won | 0.594 | 0.404 |
   | abs(residual) shares, median / p90 | 62 / 340 | 81 / 500 |
   | **PnL corr if the residual side were known (oracle), unit size** | 0.49 / 0.73 | **0.43 / 0.59** |
   | PnL corr, residual side and size known (oracle) | 0.71 / 0.81 | **0.55 / 0.62** |
   | "spot above strike at T-60" as the residual side, unit size | 0.05 / 0.07 | -0.07 / -0.07 |

   - Even a perfect residual-side oracle misses the Pearson bar (0.43-0.49). The 0.5 bar needs the residual side
     *and* its size, which ranges from 0 to more than 500 shares and scales with the rung class.
   - The wallets enter the same side in 85% (STUDY) / 78% (VALIDATE) of the windows they share.
   - Entry posture by entry time (frozen posture, block clock with the Binance stand-in, so a lower bound; the RE's
     real-Chainlink entries score 0.66-0.75):

     | first fill | STUDY | VALIDATE |
     | --- | --- | --- |
     | 0-10 s after the open | **0.841** (n 170) | **0.714** (n 465) |
     | 10-30 s | 0.655 | 0.643 |
     | 30-90 s | 0.600 | 0.614 |
     | 90-300 s | 0.521 | 0.671 |

     Late STUDY entries go to the spot/market favourite (0.70-0.75). VALIDATE entries go to the underdog: market
     favourite 0.34-0.39.

2. **The night size configuration switches inside the running processes, at a time that matches no clock rule
   frozen so far.**
   - STUDY 10-23 (Friday): all three wallets ran 62/12 until 03:52-04:01 UTC. Their first 250 rungs came at
     04:20:56-04:20:57 UTC, for almach and mo-money in the same second.
   - The counters did not restart. The lowest 250-class salt is 178,550-184,983, which is about 3.4-3.6 h at
     ~14.4 orders/s after the 01:00 restart.
   - 04:00 UTC is 00:00 ET.
   - 500-class fills start in hour 11 UTC that day, against 12:00:04-12:00:54 UTC on 10-26..30.
   - Lot aggregates by day and 6-h block:
     - 62 is the night class on Mon-Wed 10-26..28;
     - 250 is the night class on 10-23 06-12 (0.79), 10-29 06-12 (0.77) and 10-30 06-12 (0.69);
     - 10-29 00-06 is mixed (62 0.38, 250 0.32), so the config switched inside that block;
     - per the RE, 10-31 hour 00 was 62s and 500s ran from the 01:00 restart on.
   - So the size is not a pure UTC schedule. It looks like a configuration reset at discrete times: an ET day roll,
     the 01:00 restart, or ad hoc.

3. **The salt counter shows the ladder's structure in each re-price pass (STUDY).**
   - In 61 of 8,195 transaction-wallet groups, two of the wallet's own orders were filled together. All 61 are on
     one token. Their salts differ by a median of 1 (q75 5, q90 11). They are equal-size rungs at adjacent ticks,
     and the lower price was signed first:
     - 62 @ 0.95 / 62 @ 0.96 (Δsalt 1);
     - 250 @ 0.20 / 0.22 (Δ5);
     - 500 @ 0.14 / 0.16 (Δ5).

     A schedule rung and an imbalance-size bid are signed in the same pass too: 62 + 7.27 and 62 + 12.24, each
     with Δsalt 1.
   - Across transactions, 233 same-market pairs of filled orders lie within 40 salts of each other:
     - 209 are on the same outcome (Δsalt median 11-14);
     - 24 are on both outcomes (Δsalt median 25-34).

     Off-session (00-12 UTC) 5 of 62 pairs are on both outcomes; in the session (12-24 UTC) 19 of 171.
   - So a pass signs one outcome's ladder as a block. Whether the off-session ladder is two-sided can be measured
     on the whole lot from salt adjacency, without waiting for 11-01 06-12.
4. **Nulls, so nobody re-runs them.**
   - **Pick-off side for the off-session 62s.**
     - Block clock, STUDY: the side whose Binance spot fell in the last 1-3 s scores 0.57-0.60, against the posture's
       0.535.
     - 10-26 match clock (taker signing ms + 620 ms) with Binance futures ms: 0.43-0.58 at every lag (0-500 ms) and
       window (0.25-5 s), n 735. There is no pick-off signature.
     - The off-session 500s are filled on the token whose spot rose over the last 5-10 s (0.68-0.73).
   - **Historical order age from the salt counter.**
     - In the stored counter table, consecutive fills of a wallet are 30-60 s apart (median) and the rate is
       14.4-14.6/s. That gives about ±15 s of age noise.
     - Ages above 30 s are 9-12% in every class (500, 62 and 250 alike). There is no sign of minute-scale resting
       62/250 rungs, but ages under 15 s cannot be resolved at this anchor density.

## Critique

1. **The investigation scores the decision per fill, but the money and the outcome bar are per window.**
   - The terminal residual carries 58-73% of the PnL variance.
   - Its side is the entry side in 78-86% of wallet-windows (all of the 40-59% one-sided ones, and 63-65% of the
     two-sided ones).
   - Even a perfect residual-side oracle reaches only 0.43-0.49 Pearson at unit size. The outcome bar therefore needs
     the residual *size* as well. R6's PnL proxy cannot carry that size. It sums P(fill) x (payout - price) per side,
     with no pairing, no netting and one share per bin.
   - The off-session side search (R7-side, 62/250 per fill) is looking at the part of the window that matters least
     for PnL. The later 62 fills often complete pairs; what matters is the entry and how much stays unpaired.
2. **Size is treated as a clock schedule, but it is a configuration state.**
   - Night configs change inside the running processes (10-23 ~04:20 UTC, 10-29 00-06), with no restart.
   - The rung class sets the residual magnitude: 62 vs 250 vs 500 is a factor of 2-8 in the PnL each window
     carries.
   - Without a point-in-time config predictor, neither the residual size nor the side sub-rule can be chosen on a
     sealed block.
3. **The RE waits for live blocks for questions the lot's calldata can already answer.** Two examples:
   - Is the off-session ladder two-sided? Salt adjacency inside a pass answers this.
   - What does the ladder look like (equal-size rungs, spacing, signing order)? Same-pass rungs answer this.

   The live blocks remain the confirmation, but the historical version covers 8 days and both lots' sessions.
4. **Two claims rest on live blocks only.**
   - "Filled orders are fresh posts". On the lot, the salt counter at the stored anchor density cannot resolve ages
     under ~15 s.
   - Entry posture is weaker for later entries (block clock 0.84 → 0.52-0.67). The "timing" component should say
     which of these it rests on.

## Proposals (ranked by the chance they close the gap)

### P1. Decode the window's terminal net position (entry, accumulate, pair, residual) as the outcome and side unit, and build the strict-fill replay as that state machine (new; strong form of X64 / X100 / D4)

- **Hypothesis.** Each wallet-window runs a fixed path:
  1. Before any fill, the engine quotes the posture side only, with schedule rungs. The first fill is the entry, and
     it sets the side.
  2. Schedule rungs keep adding to that side while the posture holds.
  3. Pairing bids sized to the imbalance try to complete it on the other outcome.
  4. Quoting stops at ~T-30 s, with merges ~T-65 s.

  The terminal residual is whatever the pairing bids have not completed: the entry side times the rung class times
  the unpaired count. It carries the PnL variance. A rule that reproduces (a) the entry side, (b) side flips when the
  500 posture flips mid-window, and (c) the residual size from the config and the public taker flow is the only route
  to per-window PnL corr ≥ 0.5.
- **Why it fits.**
  - Finding 1: residual = entry side 0.78-0.86; the residual carries 58-73% of the variance.
  - Oracle ceilings: 0.43 / 0.59 (side only) and 0.55 / 0.62 (side and size), VALIDATE aggregate.
  - Entries in the first 10 s follow the posture 0.71-0.84 even with the Binance stand-in.
  - The three wallets enter the same side in 78-85% of shared windows.
  - The 500 ladder is one-sided (a 500 fill's nearest 500 fill is on the opposite outcome 3.7-4.5%).
- **Test.**
  1. **Pre-entry quote** (dx_clob, 10-31 15:53-18:00 and 11-01 06-12): for each window, before the cluster's first
     fill, the share of seconds with schedule-size rungs at the touch on the posture side only, the other side only,
     or both. If posture-only dominates, the entry side is a quote decision, not the taker's.
  2. **Entry side with the real Chainlink on the calibrated match clock** (A1 machinery), by entry time (0-10 /
     10-30 / 30-90 / 90-300 s), region (A/D) and class. Pre-register the 0-30 s cell.
  3. **Net-position model.**
     - Side: the posture at the entry, flipped if the 500 posture flips for ≥ x s while the public taker volume that
       would fill posture-side bids is ≥ y. Freeze x and y on BUILD+STUDY.
     - Size: rung class (P2) x the predicted number of posture-side fills before T-30, minus the predicted pairing
       completions. Use the public taker volume on the posture token's bid and its complement's ask.
     - Score net-side accuracy and corr(predicted net x (payout - price), wallet residual PnL) on VALIDATE
       (aggregate).
  4. **Executable replay (X64)** of the same state machine under strict fills (latency ≥ 2 s, `match_slack = 2`;
     queue from the pmxt calibration):
     - the entry rung at last print - 0.01 on the posture side;
     - adds on the same side;
     - pairing bids for the exact imbalance at the market;
     - stop at T-30.

     Report per-window Pearson and Spearman against the wallet, with the oracle ceilings beside them.
- **Data.** On disk: `volhist_*`, `b1_cluster_orders_*`, `exam/activity_*`, the tapes, the Chainlink fetch. Live:
  dx_clob for the pre-entry quote.
- **Signature if true.**
  - The pre-entry quote is posture-only in ≥ 70% of window-seconds.
  - The entry side is ≥ 0.85 in the 0-30 s cell with real Chainlink.
  - Net-side accuracy is ≥ 0.80 in one-sided windows.
  - The replay's per-window corr is ≥ 0.40 on VALIDATE, against a sized-oracle ceiling of 0.55 / 0.62.
  - If the pre-entry quote is two-sided, the entry is taker-chosen. The outcome bar is then out of reach for any
     public rule, and that is the quantitative account to report.

### P2. The size configuration is a controller state reset at discrete times: find the reset clock and its driver (equity, trailing PnL or vol), and use it as the point-in-time selector of rung class and residual size (new; strong form of X34 / C5 / X99, absorbs X95 step 4)

- **Hypothesis.** The base rung size is a step function of a risk budget: 500 / 250 / 125 / 62 = 500 x 2^-k.
  - The budget is evaluated at fixed times: the ET day roll (00:00 ET = 04:00 UTC before 11-01, 05:00 UTC after),
    the 01:00 UTC restart, or an hourly check.
  - It is computed from the wallet's equity (reset by the Monday sweep), its trailing realised PnL, or the recent vol.
  - The weekday 12-21 UTC session is a separate override to 500.
- **Why it fits.**
  - Finding 2: 62 → 250 at ~04:20 UTC on 10-23 in all three wallets within about a second, with no counter reset.
  - The 62 night class on Mon-Wed after the Monday sweep, and 250 on Thu/Fri.
  - A mixed 10-29 00-06 block.
  - 62 again at 10-31 00 UTC, after the losing noise-regime Friday, then 500 from the 01:00 restart.
  - Overnight stops after losing evenings (B5).
  - The weekly treasury cycle (FINAL_RULE: $22-24k after the Monday sweep, growing to $43-49k).
- **Test.**
  1. **Change points.** Find them at minute resolution in the filled orders' calldata size class, per wallet, over
     BUILD (the 500/1000 → 500/250/125 version changes) and the lot (VALIDATE: switch times only, no case-level
     side or PnL). Do they line up across wallets within seconds? Do they fall on a fixed clock mark (ET roll,
     01:00 UTC, the hour)?
  2. **Driver.** Reconstruct per-wallet equity at each candidate reset: collateral-token Transfer logs plus CTF
     positions marked at the mid, development periods only. Also compute the trailing 24-h realised PnL and the
     trailing vol. Fit a one-threshold rule on BUILD+STUDY and score the night config on VALIDATE per night
     (aggregate).
  3. **Merges.** Test whether merges (87 of 662 paired STUDY windows) happen when free collateral is low. That would
     show capital is a binding state.
  4. **Pre-registered DST observation (development block 11-02 00-06).** Does a config change, if one happens,
     come at 05:00 UTC (ET roll) or 04:00 UTC?
- **Data.** Calldata on disk. Polygon `eth_getLogs` for the collateral token and CTF events of the three wallets,
  development periods only. `exam/activity_*`.
- **Signature if true.**
  - Switches fall at one clock mark ± minutes in all three wallets.
  - One threshold on equity or trailing PnL classifies ≥ 90% of nights.
  - Feeding the predicted class into P1's size model raises VALIDATE PnL corr by ≥ 0.05 over the class-free
     version.

### P3. Same-pass salt adjacency: reconstruct the ladder's geometry and its two-sidedness on the whole lot from calldata (new; historical strong form of X19 / X71 and of the RE's next step 1)

- **Hypothesis.** Each re-price pass signs, per market:
  - one outcome's ladder as a consecutive salt block: equal-size rungs at adjacent ticks, lowest price first;
  - the imbalance bid in the same pass.

  Off-session, the pass either signs both outcomes (a two-sided ladder whose fill side the takers choose) or one
  (posture only, like the 500 ladder). The salt offsets inside a pass then give, historically and per class:
  - rung count and spacing (the replay's fill law: how a sweep walks the ladder);
  - two-sidedness;
  - which markets share a pass (the per-wallet universe over time).
- **Why it fits.** Finding 3:
  - same-transaction rungs have Δsalt median 1, one token, ordered by price;
  - schedule rung + imbalance bid with Δsalt 1;
  - both-outcome same-market pairs sit at larger Δsalt (25-34 vs 11-14).

  The 500 ladder is one-sided by the fill test. The off-session side is undecoded.
- **Test.**
  1. Fetch calldata for every cluster fill in every family on the lot. Now: BTC 5m all, other families sampled.
     About 15-20k transactions, polite RPC.
  2. Per wallet, sort all filled orders by salt. Define passes by salt gaps against the publish clock: the slope of
     salt vs time is ~14/s, and the 10-31 blocks give the publish ms to calibrate the pass length.
  3. For each pass that holds a filled order, tabulate the other filled orders within the pass: same token, the
     other outcome, other markets.
  4. Correct for observability with a null that keeps each order's fill probability but shuffles which outcome it
     is on within the window.
  5. Compare the session 500 ladder with the off-session 62/250 ladder.
- **Data.** Polygon RPC (`eth_getTransactionByHash` batches), the cached B1 tables, the 10-31 publish clock (dy_rtds).
- **Signature if true.**
  - Both-outcome same-pass rate off-session ≥ 2x the null and ≥ 2x the session's → a two-sided off-session ladder.
    Score its side as taker-chosen, and put its decodable decision (the skew) into P1's entry model.
  - Not above the null → the off-session ladder is one-sided too, and its side is a quote decision still to be
    found.
  - Either way, the rung geometry (count, spacing) is fixed for the replay.

### P4. Report the side component on the unit the examiner can test: the window entry and the net side, with the per-fill side split by role (re-scoping of the side component; uses P1's measurements)

- **Hypothesis.** The examiner's side test applies "where the wallet chooses one" (one-sided in ≥ 20% of windows or
  markets). That holds: 40-59% of wallet-windows are one-sided. For those windows the decision is the entry. For
  two-sided windows the per-fill side mixes three roles:
  - posture rungs (the decision);
  - pairing bids (own state, by definition on the under-held outcome);
  - fills of a two-sided off-session ladder (the taker's choice, if P3 finds one).

  A per-fill pooled side ≥ 0.80 cannot be reached across these roles. A window-level side of the net position, plus a
  per-role split of fills, can.
- **Test.**
  1. Freeze, from P1, the window net-side rule: posture at the entry, with the flip rule.
  2. Score it on VALIDATE (aggregate) and on the next development blocks, per wallet and half, against the market-only
     baseline (favourite / cheaper side) and the own-inventory baseline.
  3. Report the per-fill side by role: schedule rungs to the posture; pairing class to the under-held outcome, as
     the own-inventory baseline, labelled so.
- **Signature if true.** Window net-side accuracy ≥ 0.80 in one-sided windows on VALIDATE and in both halves, with
  every wallet within 3 points.

## Notes for the RE

- All my VALIDATE numbers are aggregates. No parameter was chosen on VALIDATE.
- The posture in finding 1 is the block-clock Binance stand-in (`volhist_*`). Re-measure it with the real Chainlink
  and the calibrated match clock before using it.
- "Residual" here is per wallet-window from maker BUY fills only. The cluster's small complement taker buys and merges
  are not netted in. Add them before freezing P1.
- For P2, measure equity from development-period activity and on-chain logs before H. Do not use the current-state
  endpoints (they include sealed positions).
