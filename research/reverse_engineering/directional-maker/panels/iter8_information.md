# Panel after iteration 8: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 8 in full, earlier iterations by section), state.json
(catalog, components, latest statement), FINAL_RULE.md, `code/final_rule.py` (`side_posture_match_clock`), the panel
files of iterations 4-7 and the headings of `iter8_assumptions.md` (written in parallel; one of its claims is answered
in C1).

Data used, all development:

- the RE's per-fill side table `it6/fill_side_1793455600_1793464202.parquet` and M1 table `it6/m1inv_*.parquet`
  (10-31 14:06-16:30);
- the own-recorder feeds `dm_rtds` and `dm_bnf` through the RE's dev-only reader;
- the frozen R6 side path re-run on 10-31 12:00-18:00 (shared recorder `clob_crypto`, Gamma, activity, Chainlink cache);
- Binance BTCUSDT 1-s klines from the public REST API for 10-31 10:00-18:00;
- Deribit DVOL (`public/get_volatility_index_data`, resolution 60) for 10-31 11:00-18:00;
- Kalshi `/markets/{ticker}` and `/markets/{ticker}/orderbook` for one market that closed on 10-21 (before H).

I did not read `.cache/live/sealed/`, any sealed block, another strategy's files or anything after 10-31 18:00. My
scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i8/`:
`volside.py` (frozen side path with the vol swapped; it saves `volside_D.parquet`), `kgrid.py`, `resid.py`,
`sigpath.py`, `volsrc.py`, `m1vol.py`, `refrace.py`, `wallet_win.py`, `strike.py`, `lockin.py`, `nowcast.py`.

## What my checks found

**C1. The posture side's failures are mostly our volatility input, not the engine's deviation.**

The RE's fair is Phi(ln(CL/K) / (sigma sqrt(tau))) with sigma = 1.4 x the 300-s realised 1-s vol. The 1.4 x 300-s
choice comes from the price fits of iterations 1-3 (X13), where it was fitted on STUDY fill prices. It was then reused
for the posture side, and on the side only the multiplier was varied, never the lookback or the source. I re-ran the
frozen path (`side_posture_match_clock` copied verbatim, inputs built as in `evaluate()`) on the whole development block
10-31 12:00-18:00. It reproduces the RE exactly: n 2,244, accuracy 0.786. Then I swapped only sigma (same Chainlink
value, strike, mid and tau):

| sigma input (k = scale) | all | 12:00-15:00 | 15:00-16:30 | 16:30-18:00 | 5m | 15m |
| --- | --- | --- | --- | --- | --- | --- |
| 300-s realised x 1.4 (frozen R6) | 0.786 | 0.712 | 0.835 | 0.709 | 0.794 | 0.753 |
| 30-min realised, k 1 | 0.819 | 0.757 | 0.834 | 0.877 | 0.804 | 0.881 |
| **1-h realised, k 1** | **0.832** | **0.787** | **0.843** | **0.881** | **0.811** | **0.917** |
| 2-h realised, k 0.8 | 0.820 | 0.760 | 0.834 | 0.881 | 0.798 | 0.910 |
| EWMA half-life 30 min, k 1 | 0.823 | 0.772 | 0.834 | 0.877 | 0.801 | 0.913 |
| one constant for the block (median 300-s x 1.2) | 0.815 | 0.755 | 0.829 | 0.877 | 0.792 | 0.908 |

The gain sits in one regime. I split by the ratio of the 300-s to the 1-h realised vol at the fill:

| sigma_300 / sigma_3600 | fills | 300-s vol (k 1.0-1.4) | 1-h vol (k 1) |
| --- | --- | --- | --- |
| > 1.5 (after a burst) | 142 | 0.39-0.46 | **0.93** |
| 1.15-1.5 | 227 | 0.72-0.84 | 0.81 |
| 0.85-1.15 | 361 | 0.81-0.84 | 0.80 |
| 0.6-0.85 | 1,060 | 0.83-0.85 | 0.85 |
| < 0.6 | 454 | 0.71-0.76 | 0.79 |

- The quarter hours the RE flagged as "the engine has another driver" are burst windows. In 14:50-14:57 the 300-s vol
  was 4.5-6.5e-5/s against 2.3e-5/s over the hour. 5m 14:55 goes from 0.00 to 1.00, 15m 14:45 from 0.14 to 0.97 and 5m
  14:50 from 0.52 to 0.93. The 16:30-18:00 slice, which the RE read as "no better than the market baseline before the
  switch-off", goes to 0.88.
- Windows with at least 8 fills that score below 0.7: 17 of 56 with the frozen vol, 11 of 56 with the 1-h vol.
- `iter8_assumptions.md` critique 4 says that no single fair-value setting fixes the failing windows. That holds for
  the vol scale it tested. It does not hold for the lookback: one global slow sigma, with no per-window parameter,
  repairs most of them.
- **Caveat:** I chose among 13 inputs x 5 scales on these same fills (about 70 windows). Every input with a lookback of
  at least 30 min, or a constant, lands at 0.815-0.832. So the qualitative result (a slow sigma) is robust, but the
  exact lookback is not identified.

**C2. The engine's sigma is slow, and it is not an unscaled implied vol** (`sigpath.py`).

- For each 20-minute block I took the constant sigma that maximises posture accuracy. It ranges 0.8-4.0e-5/s.
- At 14:50 the engine's sigma is about 1.6e-5/s: 0.935 accuracy, against 0.362 at the frozen 6.5e-5/s.
- Deribit DVOL was flat at 39.96-40.56 over 10-31 11-18 UTC, which is 7.2e-5/s. That is 2-4 times the engine's sigma.
  An implied input would need a fixed scale of about 0.3-0.4, which makes it indistinguishable from "a constant" on
  this block.
- The 20-minute path is too noisy to separate 1-h realised from a session constant. With a sigma chosen per block (14
  free parameters, in-sample) the side reaches about 0.90. That is the ceiling a perfect vol input could give here; the
  remaining ~10% is something else.

**C3. The M1 rejection is not a vol artefact** (`m1vol.py`, on the RE's 2,266 two-market seconds).

- In 833 seconds the 5m and 15m windows share the strike. There, "one internal price and one sigma" implies
  z5 sqrt(tau5) = z15 sqrt(tau15), whatever the sigma.
- This holds within one 5m tick in only 19% of those seconds (27% with tau - 40 for the TWAP averaging).
- With the 1-h vol, |S_hat_5m - S_hat_15m| is within one tick-equivalent in 12-15% of all seconds.
- "Each ladder hangs off its own mid" stands. The slow sigma matters for the side decision, not for the ladder level.

**C4. Chainlink at T - 1,432 ms stays the best reference, and mo-money lags the others in the same windows**
(`refrace.py`, `wallet_win.py`).

On 14:06-16:30 (1,668 fills), with the 1-h vol, accuracy by reference:

| reference | accuracy |
| --- | --- |
| Chainlink report stamped T - 1,432 ms | **0.815** |
| Chainlink, T - 1,000 ms | 0.798 |
| Chainlink, T - 2,000 ms | 0.775 |
| Chainlink, T - 3,000 ms | 0.731 |
| Chainlink, T - 5,000 ms | 0.640 |
| RTDS TWAP-60 topic | 0.577 |
| Binance futures mid with a rolling 60-s basis correction | 0.621 |

Per wallet over 12:00-18:00 with the 1-h vol: almach 0.888, bosona 0.847, **mo-money 0.767**.

- In the 42 windows where at least two wallets have 5 or more fills: almach 0.888, bosona 0.871, mo-money 0.793.
- Mo-money scores about 0.74 at every delay from 1,000 to 2,000 ms.
- Its accuracy does not depend on whether the fill adds to its held side (0.757 vs 0.763). Almach and bosona are better
  when they add (0.909 / 0.882 against 0.843 / 0.754).
- Mo-money is also weaker at large edges: 0.82 against 0.93 for almach at |e| > 10 c.

**C5. Small edges, the strike convention and the last minute** (`strike.py`, `lockin.py`, `nowcast.py`; 14:06-16:30).

- With the 1-h vol, accuracy is 0.38-0.50 at |e| <= 1 c (n 114-121) and 0.62-0.72 at 1-2 c.
- Strike conventions rebuilt from the RTDS 1-s stream (means over [st-60, st), [st-59, st] and [st-61, st-1)) sit
  within $0.2-0.6 of Gamma's priceToBeat and change nothing. Chainlink at st is worse (0.718).
- Lowering the strike by $2-4, which is the same as shifting the fair 1-2 c toward Up, raises the small-edge bucket from
  0.515 to 0.63-0.66 and the total from 0.809 to 0.825-0.832. This is in-sample on one 2.4-hour slice. It points to a
  systematic level or drift difference between the engine's S and the RTDS `value`.
- The TWAP-60 lock-in fair for the last 60 s changes nothing overall (0.803 vs 0.801). In the last 30 s it gives 0.613
  -> 0.692, on few fills.
- Adding the futures increment since the Chainlink stamp gives +0.01-0.02, and the result is not robust.

**C6. Kalshi strikes can be aligned from public metadata.**

- Verified on KXBTC15M-26OCT211015-15, which closed 10-21 14:15 UTC.
- `/trade-api/v2/markets/{ticker}` returns:
  - `floor_strike` (83,792.65), the simple average of the 60 seconds of CF Benchmarks BRTI before the open, published at
    the open;
  - `strike_type`;
  - the rules text.
- `/markets/{ticker}/orderbook` answers 200 without auth (empty for a closed market).
- So the BRTI-Chainlink basis of each quarter is `floor_strike - priceToBeat`, known at the open. The iteration-8
  Kalshi test compared misaligned strikes, used trades only, and its 159 fills were scored against the 300-s-vol
  posture (0.692).

## Critique

1. **One input of the decoded rule was never treated as an information source.** The side component is the closest to
   the bar. Its residual was read as "windows where the engine's side has another driver" (NOTES), and the failing
   quarter hours were checked against Chainlink noise, the at-touch share and the edge size, but not against the vol.
   The fair's sigma was carried over from the price fits. On the same fills, a slow sigma takes the side from 0.786 to
   about 0.83 pooled, and from 0.71 to 0.79 and 0.88 on the two slices that failed (C1). The headline economics
   ("fills against the posture lose 2.5%"; "the deviations cost money") and the "BTC 5m off after a bad posture half
   hour" reading must be recomputed with the corrected posture labels.
2. **The same sigma sits in every Chainlink-edge feature.** It is in the quote-unit model (0.748, carried by the
   Chainlink edge), the print-selection model (0.686 public), the X50 posture labels, the beta ~0.2 skew estimate and
   R5's stack. The selection route to the target (with the quote known, print selection is 0.81-0.83 at recall 62-69%,
   lift 3.3-3.4) runs through predicting the at-touch state. A free input correction there is worth more than any new
   feed. None of these has been re-scored with a slow sigma.
3. **The exam lot will vary exactly this input.** 10-31 is a quiet Saturday with a few vol bursts. A weekday exam block
   (US open, data releases) has more bursts and sustained vol ramps. A 300-s sigma fails after bursts (0.39-0.46 in the
   σ300/σ3600 > 1.5 regime), and the examiner's earlier/later halves would fall on different regimes. The pre-registered
   11-01 06-12 check (pass mark 0.80 pooled, 0.77 per half) should be run with both sigmas and reported by vol regime.
4. **Per-wallet replication is the next binding condition.** The brief requires each wallet with at least 300 fills
   to hold within 3 points. Mo-money is at 0.767 even with the best sigma, and 0.79 in the same windows where almach
   is 0.89 (C4). Its deficit is not own inventory. Nothing in the notes says which wallet's engine instance sees what,
   on which clock.
5. **The next development block may not discriminate between vol sources.** 11-01 06-12 is a Sunday morning. The
   natural experiment is 11-02 12-18, the US open at 14:30 UTC after the US DST change. Any recorder needed for that
   test (option IVs) must be running before it, and recorders cannot be started during a sealed block for data that
   would be read in it.

## Proposals (ranked by the chance they close the gap)

### I8-1. A slow volatility input for every Chainlink-edge component (new; the vol was never raced as an input)

- **Hypothesis.** The engine's digital fair uses a slowly varying sigma: a realised vol over 30 min or more, or a
  session constant. It does not use a 300-s realised vol. The posture "failures" after vol bursts are our input error.
  The same error degrades every model that carries the Chainlink edge.
- **Why it fits.**
  - C1: 0.786 -> 0.832 on the whole 12-18 block; 0.39-0.46 -> 0.93 after bursts; 15m 0.753 -> 0.917.
  - The R3 tape features already use a 1,800-s lookback (`features.py` / `features2.py`, `Spot.sigma(look=1800)`); only
    the posture path uses 300 s.
  - An engine that re-prices on every Chainlink publish has no reason to re-estimate sigma from 5 minutes of data.
- **Test.**
  1. Before 11-01 06:00 UTC, pre-register R6' = R6 with sigma = the sd of Binance spot 1-s log returns over the
     previous 3,600 s, k = 1. Use the series `evaluate()` already loads. The secondary variant is one constant per
     6-hour block (the block's median 300-s sigma x 1.2, fixed from the previous development block).
  2. Score both through `evaluate()` on 11-01 06-12. Report pooled, per wallet, per half, per family and by
     sigma_300 / sigma_3600 regime, next to the frozen R6 and the market baselines.
  3. Recompute the slow-vol edge for:
     - the quote-unit model (cluster-class 500 at the touch);
     - live print selection (`sel_oracle.py` public set, `code7/sel_clock.py`);
     - the X50 posture-event labels;
     - the M1 skew beta.

     Fit on 10-31 12:18-18:00 and test on 11-01 06-12, against the same activity baselines.
  4. Historical replication on the released lot. Score the block-clock side in the seconds with
     sigma_300 / sigma_3600 > 1.5, with both sigmas, using:
     - Chainlink from the X43 endpoint sample;
     - Binance 1-s archives;
     - STUDY case by case, VALIDATE in aggregate only.

     The lot's weekday sessions have many more bursts than 10-31, so this gives thousands of burst fills now.
- **Data.** Binance 1-s klines (archive and REST, both already in `evaluate()`), the shared recorder, `dy_rtds`, the
  X43 Chainlink sample of the lot.
- **Signature if true.**
  - On 11-01 and on the lot, burst-regime accuracy is at least 0.85 with the slow sigma and at most 0.55 with the 300-s
    sigma.
  - The pooled side is at least 0.82, with both halves at least 0.79.
  - The quote-unit AUC rises by 0.01-0.03 over 0.748, and live print selection rises over 0.686/0.764.
  - If the burst contrast does not replicate on 11-01 or on the lot, C1 was in-sample luck: close with the numbers.

### I8-2. Name the vol source: invert the engine's sigma path and race candidate sources through a vol regime change (new)

- **Hypothesis.** The slow sigma comes from one identifiable source:
  - (a) Binance (spot or futures) realised over 30-120 min;
  - (b) Chainlink RTDS realised, inflated by its negative lag-1 noise;
  - (c) a constant set at the daily 01:00 UTC restart or by configuration;
  - (d) Deribit implied (DVOL, or the nearest-expiry ATM `mark_iv`) times a fixed scale;
  - (e) the sigma implied by Polymarket's own longer windows (the 4h book in `clob_crypto`) at the Chainlink price.
- **Why it fits.**
  - C2: the engine's sigma is slow and 2-4 times below DVOL, so (d) needs a scale. A constant does almost as well as
    1-h realised on 10-31 (0.815 vs 0.832), so a quiet day cannot separate (a), (c) and (d).
  - M5 shows the size controller reads a short futures vol (60-900 s) for the 500 upgrade. If the engine has one
    estimator, its size switches and sigma changes should coincide.
- **Test.**
  1. Each fill, or each Chainlink report in the X50 unit with the side at the touch observed in the full-depth book,
     gives a one-sided bound on sigma_eng. For example, if x = ln(CL/K) > 0, buying Up at mid m needs
     sigma < x / (sqrt(tau) Phi^-1(m)). Pool the bounds in 5-minute bins into an interval path sigma_eng(t).
  2. For each candidate, report the share of bins whose interval contains it, and the posture accuracy during
     transitions (the hour after a sustained change of the 1-h realised vol by at least 50%).
  3. Natural experiment: the 11-02 12-18 development block (US open 14:30 UTC). Expected behaviour by source:
     - (a) follows the ramp 30-60 min late;
     - (c) ignores it until the next restart;
     - (d) moves at or before the open;
     - (e) moves with the 4h book.
  4. Cross-check against the size controller. Do 62/250 -> 500 switches outside the US session coincide with jumps of
     sigma_eng?
- **Data.**
  - Deribit public API: `get_volatility_index_data` at resolution 60 (verified 200 today). Option marks come from
    `public/get_book_summary_by_currency?currency=BTC&kind=option`, polled once a minute by a small `Writer` recorder
    with a hard stop, started at a development block boundary.
  - `clob_crypto` 4h books, `dy_rtds`, Binance REST, and the scheduled full-depth recorder.
- **Signature if true.** One candidate's path lies inside the sigma_eng intervals in at least 80% of bins. Only that
  candidate keeps the posture at 0.80 or above through the regime change. Restart-constant (c) would show as a step in
  sigma_eng at 01:00 UTC and none in between.

### I8-3. Mo-money's own clock and feed: a per-wallet information source (new; required by the per-wallet replication condition)

- **Hypothesis.** The three wallets run separate engine instances (per-wallet salt counters), and mo-money's instance
  reads Chainlink or the book on a slower or different connection. It then decides its posture on an older report, or
  on a stale mid. (Mechanical alternative: mo-money runs different parameters, such as deeper rungs that fill on
  sweeps.)
- **Why it fits.**
  - C4: in the same windows mo-money scores 0.793, against 0.888 / 0.871.
  - It is flat at about 0.74 across delays of 1,000-2,000 ms.
  - Its errors are not inventory (0.757 vs 0.763).
  - It is weaker even at large edges (0.82 vs 0.93).
  - The examiner splits per wallet, and 0.767 is below 0.80 - 0.03.
- **Test.**
  1. Per wallet: where the D2 burst-hazard step lies after each `dy_rtds` publish (the 150-ms step for the pooled
     bursts), on 10-31 17:29-18:00 and 11-01. Use calldata or salt to attribute the posts to a wallet.
  2. Per wallet: the re-post lag after Binance futures mid changes.
  3. For mo-money's wrong-side fills: the age of the filled order (raw-book add to match), and whether it was posted
     before the latest publish.
  4. The posture scored for each wallet at its own measured delay.
- **Data.** `dm_clob_raw` / the 11-01 full-depth recorder, `dy_rtds`, `dx_bnf`, calldata of the matches (owner per
  order).
- **Signature if true.**
  - Mo-money's step is at least 100 ms later than the other two, or bimodal (a second host).
  - Its wrong fills sit on orders older than the latest publish.
  - Scored at its own clock, its accuracy is 0.80 or higher.
  - If the clocks are equal, the deficit is a per-wallet parameter. Freeze it per wallet (the rule may differ by wallet
    if it is pre-registered) instead of pooling.

### I8-4. The reference level near the strike: Data Streams report fields or a drift input (new; alternative to the "deadband with memory" reading)

- **Hypothesis.** The engine's S differs systematically from the RTDS `value` by a few dollars. It may read the Data
  Streams report's bid/ask or mid rather than the benchmark price, or add a drift from the futures premium or funding.
  This only shows at small edges.
- **Why it fits.**
  - C5: with the 1-h vol, accuracy at |e| <= 1 c is 0.38-0.50, below a coin flip.
  - A $2-4 strike shift (1-2 c toward Up) raises it to 0.63-0.66 and the total to 0.83.
  - Strike conventions from the stream do nothing.
  - The assumptions panel reads the same below-chance bucket as inertia (the engine keeps its previous posture inside
    a deadband).
  - The two readings make different predictions:
    - inertia: small-edge fills follow the previous posture sign;
    - level offset: they follow sign(e + offset) whatever the history.
- **Test.**
  1. Fit the best offset separately on each development block (10-31 12-18, 11-01 06-12, 11-01 18-24) and check its
     sign and size:
     - constant: a level difference;
     - the sign of the window's trend: drift or momentum;
     - flips at random: an artefact.
  2. Race the inertia and offset readings on the small-edge fills only.
  3. Report-level fields:
     - Decode the Data Streams reports carried by Polymarket's resolution transactions on Polygon (one per window close,
       if present: benchmark, bid, ask at the settlement stamp) for lot windows. Check whether finalPrice is the
       benchmark or the mid, and how wide bid-ask is.
     - Optionally, the BTC/USD reports in Arbitrum Data Streams consumers' keeper transactions.
  4. Binance `/fapi/v1/premiumIndex` (public) as a drift input.
- **Data.** Polygon RPC (drpc / publicnode) for resolution transactions, Binance futures REST, the shared and own
  recorders.
- **Signature if true.** The offset is stable in sign across blocks and close to the bid/ask-mid minus benchmark gap, or
  to the premium-implied drift, and lifts the small-edge bucket to at least 0.7. Otherwise close it, and keep the
  inertia reading for the mechanics panel.

### I8-5. Kalshi with aligned strikes and books, as an increment over the corrected posture (strong form of X48 / A4b)

- **Hypothesis.** Part of the 15m posture residual, and of seller arrival in the 15m book, follows Kalshi's
  same-quarter book, which leads the Polymarket 15m mid by about 1 s.
- **Why it fits.** The iteration-8 lead (corr 0.30 at +1 s; R^2 0.115 -> 0.143 beyond millisecond futures) is real. The
  side test, however, was weak: misaligned strikes, trades only, and 159 fills scored against the 300-s-vol posture
  (0.692), which C1 shows is the wrong comparator. With the slow sigma the 15m posture is 0.917, so the increment has to
  be measured again.
- **Test.**
  1. Per quarter, compute basis = `floor_strike` (BRTI, public at the open) - Gamma priceToBeat.
  2. Poll `/markets/{ticker}/orderbook` once a second through a `Writer` recorder on 11-01 06-12 (public, no auth;
     verified). Convert the Kalshi yes mid to P(Chainlink close >= K_pm) by shifting the strike by the basis.
  3. Race "Polymarket cheap relative to Kalshi" against the slow-vol posture on the 15m fills, and on the 5m windows
     that close on a quarter.
  4. Add the Kalshi gap to the quote-unit and seller-arrival hazard for 15m.
- **Data.** Kalshi public REST (markets, orderbook, trades), shared recorder, `dy_rtds`.
- **Signature if true.** At least +0.02 side accuracy on 15m beyond the slow-vol posture, and a gain in the 15m quote
  unit or hazard with a block-bootstrap CI above 0. Otherwise close X48 with those numbers.

## Notes for the RE

- **Before 11-01 06:00 UTC.** Write the R6' pre-registration (I8-1: 1-h Binance spot realised sigma, k 1; secondary:
  block constant) into NOTES, next to the frozen R6 check. Score both on 11-01 06-12 by vol regime and per wallet.
  - The fix changes nothing in the exam fallback. Binance 1-s seconds are always available to `evaluate()`.
  - The 10-31 06-12 sealed block has no `dy_rtds` publish ms, but the side path uses the stamp convention anyway.
- **Before 11-02 12:00 UTC.** Start a once-a-minute Deribit option-mark poller (and DVOL) for the regime-change test
  (I8-2), and keep the 4h books in view.
- **Re-score with the corrected posture labels.** Redo the economics of the posture (+21% / -2.5%), the "failing
  quarter hours" list and the X58 reading (posture failures before the 16:53 switch-off), since most of the failures
  were burst windows.
- **Closed or weakened by my checks.**
  - "No common internal price" survives a slow sigma, and the vol-free same-strike test gives 19-27% (C3).
  - The RTDS TWAP-60 topic and a basis-corrected futures mid are poor posture references (0.58 / 0.62).
  - The last-60-s lock-in fair does not move the side.
  - Strike conventions from the 1-s stream equal Gamma's within $0.2-0.6.
