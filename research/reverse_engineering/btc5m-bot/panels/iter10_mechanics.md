# Panel, iteration 10: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers calldata, the pre-signed ladder and its copies, signing
schedules and versions, the 150-ms hold and how races resolve, cancels and lifetimes, and fingerprints of the bot.

Data I used, all development:
- `calldata_sample.parquet` / `b1_orders_sample.parquet` (the 11 sampled BUILD/VALIDATE hours), `orders.parquet`,
  `fills.parquet`, `ptb.parquet` and `binance_1s.parquet` (VALIDATE windows only);
- `it9/cd9.parquet`, `it10/cdall10.parquet`, `it10/txms10.parquet` and `it10/rem10.parquet` (10-31 14:55-17:55);
- the lab feeds `btc5m_clob_raw2` and `btc5m_venues2` for 10-31 14:55-17:55, a development block, read only through
  `live_lab.recs` (`iter_live`, `allow_sealed=False`);
- new: on-chain operator fills for 2026-08-12 16:00-16:15 UTC (100-block `eth_getLogs` chunks, 478 cluster txs) and the
  V2 calldata of 200 sampled txs. I decoded the fields only and kept them in my scratchpad. This is before H.

I did not open `.cache/live/sealed/` and read nothing sealed. My scripts are in the session scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`lat1.py`, `copy1.py`, `phase1.py`, `phase2.py`, `fresh1.py`, `basis1.py`, `basis2.py`, `volel.py`, `volel2.py`,
`pmk.py`, `stale.py`, `cancel.py`). Apart from this file I wrote nothing to the workspace. Written 10-31 ~22:30 UTC.

## Critique

1. **Finding 17 misreads the August version. The bot pre-signed in August too; it never "signed fresh".**
   - My check covers 08-12 16:00-16:15, inside the D = 250 ms regime that finding 17 calls fresh-signed. I sampled 200
     txs, which held 202 operator orders.
   - Sign-to-block times:
     - DS taker orders: median 75 s, minimum 9.2 s;
     - XM taker orders: median 95 s, minimum 6.2 s;
     - GF taker orders: minimum 57 s;
     - every maker order: at least 7.0 s;
     - W4's minimum: 2.3 s;
     - other wallets' taker orders in the same txs: median 3.7 s, q25 2.6 s (they really do sign fresh).
   - The signing phases mod 300 s form two tight bursts:
     - 133 orders at 40-75 s;
     - 64 orders at 190-225 s.
   - 33% of the orders share a signing ms with another order (copies). The size is a single one: 100 for DS, GF and XM,
     and 5 for W4.
   - The iteration's own `results/version10b.json` shows the same thing. Its daily phase quantiles (q10 / q50 / q90) are
     as tight as the October ones:
     - 08-01..07: about 2-6 / 8-30 / 161-173 s;
     - 08-09..21: 45-54 / 63-69 / 213-216 s;
     - from 08-22: 40.5-41 / 43 or 171 / 210 s.
   - `version10*.py` counts "share signed in bursts" only inside the October phases (|ph - 210.5| < 3, |ph - 42.4| < 4,
     |ph - 173.3| < 4). A schedule at other phases therefore reads as "fresh".
   - What this changes:
     - August holds at least three pre-signed schedule versions: two bursts per window at about 0-30 / 160-175 s, then
       at about 50-70 / 214 s from 08-08/09, then the October three-burst schedule from 08-22.
     - The story "pre-signing was introduced after the 08-17 delay cut to remove signing latency" is unsupported.
     - The strategy statement's "until 08-18 it signed orders fresh" is wrong.
     - The 250 -> 50 ms cut on 08-17 fell INSIDE one version (two bursts, one size per day). That makes the 45% -> 26%
       maker-share drop a cleaner natural experiment than the notes claim.

2. **The condition-5 ceiling of X82 (r = 0.47-0.58 "even for a perfect decode") assumes the race is a lottery. On recorded
   books it is not.**
   - X82 replays the wallet's decisions with independent fill draws (q per decision). The examiner's strict-fill
     simulation on a future block does not draw coins. It replays the recorded book, so a decode that submits the same
     orders at the same arrival times faces the same race the wallet faced.
   - The iteration's own data say the race is resolved by recorded events:
     - `who9` attributes 100% of the lost races to something on the book: other takers 52.7%, the operator's own earlier
       legs 17.4%, a requote with no taker 29.9%;
     - `queue10` shows the crowd orders ahead in the hold.
   - So the 0.47-0.58 bound covers only what a book replay cannot resolve: arrival-time error, near-ties inside the hold,
     and hidden engine ordering. On future blocks it is unmeasured.
   - It does apply to h1/h2, where only tapes at the block clock exist.
   - Writing "condition 5 is at the edge of attainability for a perfect decode" into the wall account is premature.
     Measured properly, the PnL condition may turn out to be a decision-overlap problem, which brings it back to the
     selection question.

3. **The decision rate does not respond to contemporaneous volatility. No bp-scaled trigger can produce that, yet every
   hazard, event and selection model so far uses bp tick terms.** Units: VALIDATE, 1,904 windows, the cluster's filled
   orders per window, Binance 1-s realized vol, OLS on logs.
   - With controls for the share of seconds inside the ladder range (a wide-vol FV between 0.15 and 0.85) and for
     hour-of-day and day fixed effects:
     - elasticity to the window's own vol: -0.11 (se 0.06);
     - elasticity to the trailing 30-min vol: +0.48 (0.08).
   - Per wallet (own vol / trailing vol): DS -0.10 (0.05) / 0.46, GF -0.13 (0.07) / 0.51, XM -0.03 (0.08) / 0.32.
   - What simple triggers predict on the same controls:
     - the count of 1-s moves above 1 bp: +1.73;
     - a 2-sigma z-score on the trailing 30-min vol: +1.56.
   - Segment level (activity at 120-240 s, n = 757 windows):
     - own segment's vol: -0.02 (0.09);
     - the same window's 0-120 s vol: +0.21 (0.10);
     - the previous window's vol: -0.06 (0.15);
     - the trailing 30 min: +0.83 (0.19).
   - Lost races do not absorb it: the maker share rises only +0.030 (0.005) per log-vol unit.
   - The bot thus trades as much in a quiet window as in a hot one at the same regime. Whatever selects the onsets
     normalizes the window's own activity away.
   - This fits the iteration-10 facts:
     - the onset take rate rises only weakly with bp strength (17 / 28 / 50%);
     - the window overdispersion is chi2 / df ~ 2;
     - on the 100-ms decision clock the cluster's venue model (0.655) is no better than Polymarket activity (0.657).
   - Caveats:
     - these are filled orders, not the complete decision record;
     - 1-s klines are coarse;
     - the trailing-vol effect may be regime activity (makers, crowd).

4. **Cheap negatives** (each one measurement, so nobody needs to re-run them):
   - **No copy budget.** Pre-signed inventory does not drive pay-up or skips. Data: 11,382 VALIDATE calldata taker
     orders, pay-up 11.3%.
     - Pay-up by prior used copies at the consumed-ask cent (same wallet, burst, token and size): 0: 11.9%, 1: 9.0%,
       2: 7.2%, 3: 5.3%. It falls; it does not rise.
     - By time since the burst signed it: flat at 9.5-15.9%.
     - By window time inside burst 2: 10.4% / 15.2% / 28.0% at 120-180 / 180-240 / 240-300 s.
     - Used copies per level: 1 (8,923), 2 (1,494), 3 (348), 4 (95), 5 or more (20).
     - Pay-up follows window time (gamma), not inventory.
   - **The copy index cannot be recovered.** All copies of a level and both sizes share one signing ms (e.g. four Up 0.36
     copies in one ms), and the salts are random. A historical ghost count from gaps in used copies is therefore
     impossible.
   - **No polling loop at a fixed wall-clock phase.** Rayleigh Z of taker match ms mod 10-1,000 ms:
     - DS at most 1.6 (n = 965), GF at most 2.0 (354);
     - the crowd phase-locks (Z 12-14 at 10 / 200 / 500 ms on match ms; Z 41 at 200 ms on its own signing ms): those
       are its own timers.
   - **No Polymarket-message clock.** I took unique server ms of near-touch price changes in 5-ms bins before the
     arrival a = m - 150 of each market's first cluster decision (n = 870):
     - 1.3x placebo over the last 80 ms, then flat;
     - the fast fresh crowd: 1.6x, decaying slowly;
     - no spike at a fixed lag. The excess is makers requoting on the same tick.
   - **No venue staleness guard that I can see.** I measured the age of the Binance USD-M BTC bookTicker message
     (receive minus E, detrended) in [a - 260, a - 80):
     - q90: cluster 2.0 ms, placebo 1.0;
     - max-q90: cluster 12, placebo 6 ms;
     - the ticks before decisions are older, not fresher. This is limited by laptop jitter, and the recorder keeps E but
       not T.
   - **The strike is not a hidden window state.** Window net Up share against the detrended (priceToBeat - Binance 60-s
     TWAP):
     - rho 0.007 for the whole window, 0.031 for the first 60 s;
     - the open-gap effect (rho 0.16-0.17) is the known underdog tilt.
   - **Remainder lives are not keyed to Polymarket feed lag.** Spearman of life against the max detrended ws lag in
     [m0, m0 + 300): 0.05 for never-filled remainders (n = 239) and -0.03 for later-filled ones (225).
     - The lives do differ by wallet: for cancelled never-filled remainders (n = 150) the median is DS 328, GF 240 and
       XM 124 ms.
     - 68 of 239 never-filled remainders are censored at 10 s.

## Proposals (ranked by the chance of closing the gap)

### 1. Decode the trigger's normalizer: a vol-adaptive (z-score) threshold or a rate controller, not a bp threshold (new; strong form of X72 / X83 / X85; inverse fit of the trigger function)

- **Hypothesis.** The take decision at an onset compares the tick with a short-horizon scale that the bot keeps itself:
  - (a) a rolling sigma of the microprice changes or of the composite over h of about 5-120 s, or the recent tick count:
    take iff |tick| / sigma_h >= z*;
  - (b) or a pacing controller that targets a decision rate per window or minute and thins onsets in proportion to their
    abundance.

  Either way, bp-scaled features are the wrong units. A fixed cut in bp selects the "wrong" third in every window whose
  vol differs from the pooled average. That is why taken vs skipped looks almost random (0.67-0.74) given every recorded
  input.
- **Evidence.** Critique 3: own-window elasticity is about 0, against +1.5-1.8 for bp or 30-min z triggers, and it holds
  per wallet. Also:
  - the take rate rises with the bp tick but stays at 17-50%;
  - window overdispersion of chi2 / df ~ 2;
  - the venue model does not beat Polymarket activity on the decision clock.
- **Test** (live; 10-31 12-18 development, then 11-01 06-12 and 18-24).
  1. On the iteration-10 onset sets (flag10b episodes, evt10 events), add point in time:
     - z_h = tick / sigma_h for h in {5, 15, 30, 60, 120, 300} s, with sigma_h over the same series (Binance USD-M BTC
       microprice, then the composite);
     - n_h, the tick count over h;
     - the within-window percentile of the onset tick among the window's earlier onsets.
  2. Fit on A and score on C. Compare raw bp, z_h, n_h and percentile, alone and together.
  3. Separate (a) from (b):
     - (a) predicts a step in z within windows, a stable z* across A / C and wallets, and no dependence on decisions
       already made;
     - (b) predicts that P(take | onset) falls with the operator's decisions in the last N s relative to a target rate
       (own state, so report it separately), little dependence on strength within a window, and var / mean of decisions
       per minute below 1 within regimes.
  4. Replicate critique 3 on the complete live decision record (won and located lost races): the elasticity of decisions
     per minute to the minute's tick count. It should be about 0 under (a) and (b), and about 1 under bp.
  5. Historical transfer: refit the block-second presence and side models with z_h-scaled venue features instead of bp.
- **Data.** On disk (`btc5m_venues2`, the flag10 / evt10 inputs, `orders.parquet`, `binance_1s.parquet`), plus the next
  development blocks.
- **Signature if true.**
  - At the best h, z_h raises the taken-vs-skipped AUC at onsets from 0.67-0.74 to at least 0.80 on C.
  - The window random effect falls to chi2 / df ~ 1.
  - z* is the same within 10% across wallets and blocks.
  - The live decision rate is flat in the tick count.
  - Presence at the block clock gains over the bp version.
  - If (b) holds instead, the selection is a scheduler. State it as a rate rule (take onsets in tick order until the
    window's quota), which is still an executable decode.

### 2. Resolve the race on the recorded book: measure the condition-5 ceiling with deterministic execution, not an independent lottery (strong form of X36 / X69 / X82; re-opens X81)

- **Hypothesis.** Given an order (o, L, Z) arriving at a, the outcome follows from recorded events:
  - non-cluster ask liquidity at or below L that survives to a + 150;
  - the crowd orders ahead of it in the hold (FIFO);
  - maker cancels during the hold;
  - for remainders, crowd sells and complement buys at L until the decoded cancel time.

  A perfect decode replayed through this simulator then reproduces the wallet's fills and its own-net size feedback, so
  its PnL correlation with the wallet is close to 1, not 0.47-0.58. Condition 5 on future blocks becomes a
  decision-overlap problem concentrated in the large orders, which carry the PnL (corr 0.77).
- **Evidence.**
  - Critique 2.
  - who9 attributes every lost race to a recorded cause.
  - queue10's P(won) moves from 67% to 46% with the visible queue.
  - The arrival times of won and lost races are exact on the server clock: m - 150 and insertion - 150.
- **Test** (10-31 14:55-17:55; repeat on 11-01 06-12).
  1. Build the simulator from `btc5m_clob_raw2`, the calldata match ms and the crowd orders, with every operator print
     and insertion removed. This is legitimate execution modelling, not a decision feature.
  2. Oracle step: feed it the wallet's own 2,155 decisions with exact arrivals and sizes. Report:
     - won / lost agreement;
     - the filled-share error;
     - maker refills, using the per-wallet cancel times of critique 4 / proposal 3;
     - the per-window PnL correlation with the wallet (Pearson and Spearman; pooled, per wallet, per half).
  3. Degradation maps:
     - jitter the arrivals by sigma in {10, 25, 50, 100} ms;
     - drop decisions at random to 90 / 70 / 50%, separately for small and large orders;
     - redraw sizes from the own-net rule on the simulated book.
     The result is r(overlap, timing error, size rule).
  4. Then: does an engine-internal lottery exist? Compare P(won) for near-ties (another arrival within 5 ms) with
     P(won) for clear orders.
- **Data.** On disk, plus the next development blocks.
- **Signature if true.**
  - The oracle replay agrees with won / lost in at least 90% of decisions, and the per-window r is at least 0.85.
  - r stays at 0.5 or more at sigma = 50 ms with at least 70% of the large decisions reproduced.
  - The X82 bound is then restricted to h1/h2, and the condition-5 work targets the large-decision overlap.
  - If oracle agreement stays below 70%, there is an engine lottery (for example a random release order inside the
    hold). That is a mechanics finding in itself and the quantitative wall account for condition 5.

### 3. The cancel timer is armed at submission, so the hold eats the remainder's resting time: decode it per wallet and test it on the delay regimes (strong form of X79 and X75; explains the "against the prediction" maker-share step)

- **Hypothesis.** Each lost race or remainder is cancelled about tau after the bot's POST, not after its insertion on the
  book.
  - tau differs by wallet, or by process queue.
  - The resting time is tau - D. A longer hold therefore does two things: it creates more lost races (more requotes
    during the hold) and it shortens their resting time (fewer refills).
  - The 08-17 cut (D 250 -> 50) and the 09-04 rise (50 -> 150) then have opposite-signed effects whose net depends on
    tau. This explains why the maker share fell after the 09-04 rise inside one version (58% -> 47%).
- **Evidence.**
  - The life of cancelled never-filled remainders differs by wallet: medians DS 328, GF 240, XM 124 ms.
  - The life is not tied to Polymarket feed lag or to adverse ticks (critique 4, rmv10).
  - The floor of about 90-100 ms after insertion is about 240-250 ms after arrival.
  - The two regime steps are of opposite sign.
- **Test.**
  1. Live:
     - fit lognormal or Weibull TTLs per wallet and size, both from the POST arrival a and from the insertion a + 150;
     - check whether the floor and the per-wallet shape are tighter from a;
     - treat the 28% that are censored at 10 s as a separate mode, a failed cancel or a different order type, and check
       whether they carry the 46% refill share.
  2. Historical, within a version (the corrected version map, proposal 4): from operator OrderFilled logs (block-level is
     enough), measure per day:
     - P(a take-then-rest order gets a maker refill);
     - the refill delay distribution.
     Do this around 08-17 (inside the 50-70 / 214-s schedule) and 09-04 (inside 80 / 200). Predict the refill change
     from the live TTL shifted by delta D.
  3. Carry the TTL into proposal 2's simulator (the maker echo of X79).
- **Data.** `rem10` / `ghost10`, plus the next development blocks; the historical fill logs in 100-block chunks, one
  hour per day.
- **Signature if true.**
  - The TTL measured from a has a sharper floor and lower dispersion than the one from the insertion.
  - The per-wallet tau is stable across blocks.
  - The historical refill probability per remainder falls when D rises and rises when D falls, by the amount the shifted
    TTL predicts.
  - The maker-share path of finding 14 is reproduced as (lost-race rate as a function of D) x (refill rate as a function
    of tau - D).

### 4. Rebuild the version history from the signing schedule itself, and use the restarts as change points (corrects finding 17; strong form of X9 / X26 / X75 / C4b)

- **Hypothesis.** Every redeploy changes a mechanical fingerprint:
  - burst count and phases mod 300 (free-running in early August, window-locked from 08-22);
  - per-wallet stagger and burst span;
  - ms per cent;
  - copies per ms;
  - the size menu;
  - sign-to-block (pre-signed vs fresh);
  - taker-order share and pay-up share.

  The day-to-day phase jumps of early August (08-08/09) are process restarts: a free deployment log.
- **Evidence.**
  - Critique 1: version10b's own phase quantiles show three schedules in August, all pre-signed, and my 08-12 calldata
    confirms the pre-signing.
  - Version10 classified by membership in the October phases only.
- **Test.**
  1. For every day from each wallet's first fill (XM from 06-20; DS / GF from 07-19/20; verify the V1 / V2 exchange
     addresses from a receipt), sample 150 operator txs of one hour in 100-block `getLogs` chunks.
  2. Decode the calldata (fields only) and compute the fingerprint vector above.
  3. Change points are the days where the vector changes. Align them with the changelog (C4b) and the delay regimes.
  4. If any segment is truly fresh-signed (taker sign-to-match of about 0.19-3 s), its sign_ms is a millisecond decision
     record on the bot's own clock. Decode the trigger kernel and the onset selection there at 10-100x the live sample,
     with that day's Binance USD-M aggTrades and Bybit book archives.
  5. Otherwise, retract finding 17's causal story and redo delayreg10 / vol10 within versions.
- **Data.** Public Polygon RPC (about 30 `getLogs` calls and 6 batch calls per day) and the Binance and Bybit archives if
  needed.
- **Signature if true.**
  - A clean segmentation, with every segment homogeneous in the fingerprint.
  - The 08-17 delay cut falls inside one segment, so its effect is a clean natural experiment.
  - Either a fresh-signed segment exists, which gives a historical ms decision clock and the strongest data upgrade
    available for the selection decode, or none does, and the strategy statement and FINAL_RULE drop the "fresh until
    08-18" claim.
