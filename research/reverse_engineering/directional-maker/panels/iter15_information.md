# Panel after iteration 15: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 15 in full, earlier iterations by search), state.json
(every catalog item, components, target metrics, live_lab), the structure of FINAL_RULE.md and the proposal titles of
every earlier information panel (iter14 in full). I did not read the iteration-15 mechanics or assumptions panels, which
are written in parallel.

Data I touched. All of it is development by `sealed.py` (released lots h1/h2, 10-31 12-18, 11-01 06:00-08:40 UTC).
Nothing sealed was read, and nothing from another strategy's workspace or cache.

- `iter_live` reads of dy_rtds, dv_rtds, dz_rtdsbn, dw_clob, dm_bnf, subs and clob_crypto (BTC/ETH 4h books of
  10-31 12-18);
- the RE's rebuilt quote tables `it14_qu_rebuilt_{1793455200_1793469600, 1793516400_1793520000}.parquet` and
  `it15_nb_side.parquet`, plus `fam/btc_4h_tapes.parquet`;
- about 230 Kalshi requests (KXBTCD markets and 1-min candlesticks of 33 BTC hourly windows), 45 Binance 1-s kline
  requests (alts, 11-01 06:00-08:40), 33 Binance 1h klines, 3 CLOB `prices-history` requests and 8 Gamma requests.

The scripts ran from my session scratchpad and are not saved in the workspace. Each check below states its exact
construction so it can be reproduced. Nothing was added to `.cache/re/`.

## What my checks found

**C1. A latency-corrected Chainlink nowcast recovers part of the clean-regime quote side, on the exact clock and on the
safe clock alike.**

- Construction: S_now(t) = CL_i + F(t - 50 ms) - F(ts_i).
  - CL_i is the BTC report in force: the last one published before t on the exact clock (dy_rtds `P`), or the last one
    stamped <= t - 1,432 ms on the safe clock (cl_source._live).
  - ts_i is that report's observation stamp, and F is the Binance USD-M bookTicker mid (dm_bnf, Binance event ms).
- The rest is the RE's `qu_today_scan.py` unchanged: strike = Gamma priceToBeat, sigma = futures sigma300, F > mid,
  pure non-extreme 500 at-touch posts.

| block | posts / windows | report k1.0 / k1.4 / k2.0 | nowcast k1.0 / k1.4 / k2.0 | cheaper | report-vs-nowcast disagreements |
| --- | --- | --- | --- | --- | --- |
| clean 11-01 07-08, exact clock | 428 / 16 | 0.591 / 0.619 / 0.645 | 0.643 / **0.682** / 0.671 | 0.629 | 28, nowcast right 0.893 |
| clean 11-01 07-08, safe clock | 429 / 17 | 0.581 / 0.620 / 0.651 | 0.645 / **0.690** / 0.673 | 0.627 | |
| noise 10-31 17:29-18:00, exact | 447 / 7 | **0.866** / 0.761 / 0.615 | **0.886** / 0.774 / 0.615 | 0.342 | 9, nowcast right 1.00 |
| noise 10-31 14-18, safe clock | 4,948 / 49 | 0.778 / 0.744 / 0.650 | 0.783 / 0.746 / 0.652 | 0.434 | |

- Halves of the clean hour (safe nowcast, k 1.0): 0.664 / 0.618; report 0.570 / 0.597.
- The published TWAP-60 topic is worse than the report on both blocks: clean k 1.0 0.533; noise 0.691.
- Reading:
  - The nowcast never loses to the report, and adds about +0.06 in the clean hour. There the futures increment carries
    the information the 1.0-1.5 s old report lacks (report age p50 1.5 s).
  - In the noise regime it adds nothing on the safe clock. There the newest report's Chainlink-only noise is what the
    engine follows, and no futures increment reproduces it.
  - The clean-hour level is still only 0.68-0.69, about 0.06 above the cheaper token. The best k stays at 1.4-2.0
    (bid the underdog: in-the-money is 0.40-0.44).

**C2. The Kalshi KXBTCD hourly ladder is not the fair of the cluster's BTC hourly fills (weak form).**

- Sample: the top BTC hourly windows by later cluster fills (BUILD 14, STUDY 10, VALIDATE 10 requested; 33 had Kalshi
  data), with 1,210 later fills.
- Kalshi data: the strikes within $700 of the Binance 1h open, using the yes-bid/ask mid of the 1-min candle that closed
  before the fill. The basis comes from the first minute's implied median (median -$83).
- Results:
  - The cluster's fill price is below the Kalshi fair on 0.62 of fills (BUILD 0.68, STUDY 0.52, VALIDATE 0.65).
  - The bought outcome is the Kalshi favourite on 0.52 of fills, against in-the-money 0.55 and the market favourite 0.51
    on the same fills.
- Returns by Kalshi edge, pooled: > +0.05 +21%/$; |edge| <= 0.05 +9%; < -0.05 -13%. The sign flips on VALIDATE
  (-13% / +26%) with about 10 windows, so outcomes dominate.
- The hourly endpoints verified: `/markets?event_ticker=KXBTCD-26OCT2812` (188 strikes, rules = BRTI 60-s average
  before the hour) and `/series/KXBTCD/markets/<ticker>/candlesticks?period_interval=1`, both historical and keyless.
- Polymarket's own hourly "Bitcoin above ___ at H ET" ladders exist but are thin ($305 volume in the event checked).
  The daily "Bitcoin above ___ on <date>" ladder is deep ($1.15M) and settles on the same Binance noon 1-m close as the
  daily Up/Down.

**C3. At the alt-window open, the per-symbol Chainlink side and the RE's Binance stand-in disagree often enough to
separate them.**

- Windows: dev windows of 11-01 06:00-08:30 for ETH/SOL (dy_rtds) and XRP/DOGE/BNB (dv_rtds).
- Chainlink side: CL(T-2) against mean CL[st-61, st-2], the verified priceToBeat construction.
- Binance side: close(T-3) against mean close[st-60, st-1], from Binance 1-s klines.
- Disagreement rate at T = st + 5/10/15/20 s:
  - 5m (26-27 windows per symbol): ETH 0.08 / 0.12 / 0.04 / 0.16, SOL 0.12 / 0.12 / 0.15 / 0.20, XRP 0.07 / 0.04 /
    0.15 / 0.12, DOGE 0.22 / 0.11 / 0.11 / 0.08, BNB 0.07 / 0.07 / 0.15 / 0.04;
  - 15m (9 windows per symbol): 0.00-0.33.
- Pooled, about 11%. That is about the size of the opening posture's error (0.87-0.92 correct), and it would be about
  370 fills among the ~3,400 historical opening fills.

**C4. The CLOB `prices-history` endpoint gives a recording-free ~1-min market price for every family, historically.**

- Development tokens checked, at fidelity 1, median step 56-60 s, values like 0.495 / 0.9995 (mid-like):
  - ETH daily (10-27 16:00 -> 10-28 16:00): 1,432 points;
  - BTC hourly 10-26 9pm ET: 108 points;
  - BTC 4h 10-26 20:00: 276 points.
- polyrea already wraps it: `PolymarketData().price_history`, chunked at 4 days. No workspace file uses it; A7's
  evidence lists only tapes and books.
- In the idle hour 11-01 06:00-07:00 the cluster's money was in BTC hourly ($1.8k), BTC daily ($1.7k) and ETH daily
  ($1.3k). Nobody records books for these families: clob_crypto covers 5m/15m/4h of BTC/ETH/SOL, and dw_clob covers alt
  5m/15m.

**C5. The 4h books in the shared recorder carry size fingerprints.**

- Positive level-size deltas in the top 3 levels of the 200-ms 'q' records:
  - BTC 4h 10-31 12:00 window (14-16): bid Up +600 x524, +400 x394; bid Down +600 x503;
  - BTC 4h 16:00 window: +600 x364 / x338, +400 x117;
  - ETH 4h 16:00 window: +300 x338 / x391.
- The RE's size table has BTC 4h = 400. Label purity for 600/400/300 is unchecked (an X170-style calldata join is
  needed).
- The cluster's BTC 4h fills of 10-16..30 are 94% maker by $ (taker share 0.10 of rows / 0.06 of $, from the cached
  taker tapes). The 4h money (+8.4% / +4.8% per $) is earned on a resting ladder.

## Critique

1. **The quote side's clean-regime failure was read as "the configuration moves between blocks" before the reference
   was made point in time.**
   - The scan that diagnosed it tried only the bare report and "futures minus a rolling 600-s median basis".
   - The brief's own picture of the engine is futures for the requote trigger (91-97% within 50-250 ms, A2/X10) and
     Chainlink for the skew (X44, X163). Combined, those describe a nowcast: the Chainlink level moved by the futures
     since the report's stamp.
   - That nowcast is point in time on history as well (C1). It adds about +0.06 in the clean hour (0.62 -> 0.68 at
     k 1.4, about a quarter of the gap to the noise block's 0.87), and it costs nothing in the noise block.
   - "Regime-specific" is premature until the nowcast is scored on the full 07-12 block. The evidence so far is 17
     windows of one Sunday hour. The remaining 0.68 vs 0.87 still has to be explained.
2. **The one decoded non-BTC component is measured against a Binance stand-in, not the settlement reference.**
   - At the open |S - K| is tiny, so the stand-in flips the in-the-money side about 11% of the time (C3). That is the
     same order as the posture's error, and it may explain why the VALIDATE halves split 0.94 / 0.80.
   - The conclusion that the opening bids lose (-16% STUDY) rests on stand-in settlement as well.
   - The settlement-grade per-symbol series exists: the endpoint for history, verified for ETH/SOL/XRP, and dv_rtds/dy_rtds
     live.
3. **The exam lot is likely carried by the long families, and they have no market-state series in R9.**
   - R9 scores the non-BTC side and price against the last clean taker print.
   - The dailies were dropped from T1d because their tapes are too long to page, and hourly/daily books are recorded by
     nobody.
   - `prices-history` (C4) is the examinable, recording-free market state for exactly these families: one request per
     token, available to the examiner for sealed units. The 0.44 price result and the "market favourite level" side
     result on thin books were both measured on a stale anchor.
4. **The information set of the module that carries the idle blocks has never been measured.**
   - A2/X10/X44 (which feed moves the ladder, at what latency) were run on BTC 5m/15m only.
   - For the alt 5m/15m ladders (dw_clob, with server ms since 10-31 22:59) and the 4h ladders (clob_crypto), nobody
     has asked which feed they follow: per-symbol Binance futures, BTC futures (cross-asset), the per-symbol Chainlink
     publish, or the RTDS Binance relay (dz_rtdsbn, published about 120 ms after each second).
   - Opening bids that follow the public posture yet lose (C3 aside) are what a module without a fast per-symbol feed
     would show.
5. **Where the non-BTC money is (later 4h/hourly fills, +5-10% per $), the fair has been tried only as a Binance digital
   with short-horizon sigma.**
   - My Kalshi check (C2) removes one long-horizon candidate in weak form.
   - The 4h ladder is directly observable through its fingerprints (C5) and has not been looked at.
6. **Housekeeping on the clock.**
   - The nowcast and every proposal below use server stamps only: Binance E, Chainlink ts/P, CLOB s.
   - The Windows resync before 11-01 12:00 UTC is still needed for the recorder filing.

## Proposals (ranked by the chance they close the gap)

### I15-1. `prices-history` as the examinable market state of the long families, and the idle module's side and price against it (new data source; strong form of T1d / X175 and of A7's unused endpoint)

- **Hypothesis.**
  - In the idle weekend configuration the cluster quotes the hourly, daily and 4h families around a settlement-reference
    fair: Binance close for hourly/daily, Chainlink for 4h.
  - It rests on the outcome that is cheap against the market mid.
  - Its later fills look "two-sided, at the market-favourite level" only because they were scored against the last taker
    print, which in these thin books is minutes old.
  - Against the 1-min mid, the side rule (fair_s > mid_s) and a mid-relative price rule (bid = mid_s - h, rounded to the
    tick) describe the fills.
- **Why it fits.**
  - The fill-price posture, which uses the fill price as the market price, is 0.79 / 0.80 / 0.79 on dailies and
    0.82 / 0.83 / 0.69 on 4h (BUILD / STUDY / VALIDATE).
  - The public last-print version is 0.51-0.59 on 4h (VALIDATE); dailies were not scored. In the money is
    0.45 / 0.35-0.71 / 0.50 on dailies.
  - The difference between them is the market price input. The fill-price version is inflated, because a maker's bid
    is always below the mid. The mid is the honest middle ground.
  - Price fails only on these books (0.44 with R7's last-trade anchor).
  - C4: the series exists for every token and every period, and the examiner can fetch it for sealed units.
- **Test.**
  1. Verify the endpoint on the recorded BTC 4h books (clob_crypto, 10-31 12-18 and 11-01 08-12). Is a point at t_p the
     mid at t_p, the last trade, or an average over the minute? Fix the point-in-time rule from that: use points
     stamped <= t - 2 s, or <= t - 60 s if a point summarises the minute ahead.
  2. Fetch fidelity-1 histories for both tokens of every hourly, daily and 4h market the cluster traded in the BUILD
     sample days, STUDY, VALIDATE and the development blocks after T0 (about 1,000 requests, cached).
  3. On BUILD only, choose among a pre-listed set:
     - fair: Binance digital with sigma = v300 x {0.7, 1.0, 1.4} or v3600 x 1.0, on the family's own settlement series;
     - h: {0, 0.01, 0.02}.
  4. Freeze. Score per family on STUDY, VALIDATE and each examiner-style half of the weekend mock lots:
     - side per fill and per market (net side);
     - price within one tick;
     - baselines from the same mid: the market favourite, the cheaper token, in-the-money.
  5. Wire the series into `r9_nonbtc` with `allow_sealed` passed through, so the examiner's run uses it.
- **Data.** CLOB `prices-history` (keyless, verified), Binance 1-s/1-m klines, the endpoint Chainlink for 4h, Gamma
  priceToBeat, and the RE's `it15_nb_side.parquet`.
- **Signature if true.**
  - Later-fill side >= 0.75 per family on VALIDATE and on both halves, >= the mid-based market favourite + 0.10.
  - Price within one tick >= 0.75 on the long families.
  - Daily side >= 0.78 on public inputs.
  - If the side stays at the mid-based favourite level, the long-family side is the takers' choice measured on the
    right anchor. R9 then reports it as a baseline description, with the number.

### I15-2. The settlement-grade per-symbol Chainlink at the alt-window open: which strike and price the opening bid reads, and who beats it (strong form of I14-2 / X164 / X173, which used the Binance stand-in)

- **Hypothesis.**
  - The opening bid of the alt 5m/15m windows is priced off one specific reference: (a) per-symbol Chainlink against the
    true priceToBeat, (b) Binance against a Binance TWAP stand-in, or (c) Binance against the true priceToBeat.
  - The ~8-13% of opening fills that the stand-in posture misses, the 0.94 / 0.80 half split, and the opening losses
    are concentrated where those references disagree.
- **Why it fits.**
  - C3: about 11% disagreement at T = st + 5-20 s on the clean morning of 11-01.
  - The decoded opening posture is 0.87-0.92, with its VALIDATE halves 0.94 / 0.80.
  - "Posture-agreeing opening bids lose" (-0.4% BUILD, -16.1% STUDY, -1.3% VALIDATE) was computed with stand-in
    settlement.
  - Takers who sell the itm token at the open and win are what a reference error would produce.
- **Test.**
  1. For every opening fill (< 20 s) of the alt 5m/15m families, fetch the endpoint's Chainlink value at T - 2:
     BUILD 2,027, STUDY 841, VALIDATE 494, about 3,400 (symbol, second) requests, or a pre-registered stratified half.
     Verify first the variants for DOGE/BNB/HYPE (ETH/SOL/XRP are verified).
  2. Take the true strike from Gamma priceToBeat (a listing-time field at the window start) and the true outcome from
     the endpoint's closePrice or Gamma's resolution (development units only).
  3. Score (a), (b) and (c) on all opening fills and on the disagreement subset. Run the public posture (k 0.7 vs the
     last print) with each reference.
  4. Recompute the opening PnL with true settlement, split by agreement.
  5. Repeat on the dev blocks with dv_rtds/dy_rtds on the exact publish clock: is the engine within 300 ms of the
     per-symbol publish, as on BTC?
- **Data.** `polymarket.com/api/crypto/crypto-price` (about 1.5 requests/s), Gamma, Binance 1-s klines, dv_rtds,
  dy_rtds.
- **Signature if true.**
  - One reference wins >= 0.85 of the disagreement subset in BUILD, STUDY and VALIDATE.
  - The opening posture on that reference is >= 0.90 on every fold and within 0.03 across the VALIDATE halves.
  - If (b) or (c) wins and the disagreement fills carry the opening losses, the module prices the open off Binance and
    is beaten by takers who read the settlement feed. That is a quantitative account of where it loses.
  - If (a) wins, the module reads the settlement feed at the open, as on BTC.

### I15-3. One reference for both regimes: the Chainlink nowcast (strong form of X49's untested nowcast step and of X59; side and quote presence on BTC 5m/15m)

- **Hypothesis.**
  - The engine's fair uses S_now = the latest public report + the futures move since that report's stamp: the
    Chainlink level with the futures increments.
  - On the exact clock this is what it reads. On history and in every block without dy_rtds, the safe-clock version
    reproduces it in the clean regime.
- **Why it fits.**
  - C1: never worse than the report; about +0.06 on the clean hour on both clocks; 25 of 28 and 9 of 9 disagreements go
    to the nowcast.
  - It unifies the two established inputs: the futures requote trigger (A2/X10) and the Chainlink re-siding at each
    publish (X163).
  - The posture-change signature on 11-01 (0.601 after vs 0.399 before the publish) shows the publish trigger survives
    in the clean regime, while the level does not.
- **Test.**
  1. Freeze k on 10-31 14-18 (safe clock) with S_now: one value from {1.0, 1.4}, no per-block k.
  2. Score per hour on 11-01 07-12 (pure 500 posts; exact and safe clocks), then on 11-01 18-24 and 11-02 00-06 /
     12-18 as they come in.
  3. Also score:
     - the per-fill side branch of R8, on the lot via the endpoint report at the safe stamp + futures aggTrades;
     - the publish-anchored presence cells of X163 with the nowcast change between publishes as a feature;
     - posts between publishes, which only a nowcast can explain.
  4. Report every block against the bare report, the cheaper token and the per-hour Chainlink/futures noise ratio.
- **Data.** dy_rtds / cl_source, dm_bnf / dx_bnf, Binance futures aggTrades archives, the rebuilt quote tables, the
  endpoint.
- **Signature if true.**
  - The nowcast >= the report in every hour, >= the cheaper token + 0.08 in clean hours, with the k chosen on 10-31 still
    best (or within 0.02 of best) on 11-01/02.
  - The per-hour accuracy no longer tracks the noise ratio.
  - If clean hours stay <= 0.70 on the full block, the clean-regime posts are mostly re-pegs (mechanics). The side should
    then be scored on the resting state (X169 label B), with the nowcast as its input.

### I15-4. The information set of the idle module: which feed moves the alt 5m/15m and 4h ladders, and how fast (strong form of A2 / X10 / X44 for the non-BTC families, never measured)

- **Hypothesis.** The non-BTC ladders requote on one identifiable public feed:
  - per-symbol Binance USD-M futures;
  - BTC futures, a cross-asset trigger inherited from the BTC engine;
  - the per-symbol Chainlink publish;
  - or the RTDS Binance relay, which the engine reads on the same socket as Chainlink.

  Its latency decides whether its opening and later quotes are picked off.
- **Why it fits.**
  - The decoded opening bid follows a public posture but loses.
  - mo-money's rungs carry a ~1-s older posture (X172), so the instances differ in their cancel path.
  - The engine has per-family configured sizes. The non-BTC families may be a separate, slower module.
  - dz_rtdsbn shows the relay publishing about 0.1-0.2 s after each 1-s stamp for btc/eth/sol (one sample: 124, 130,
    213 ms). A requote clock locked to
    the relay's publish ms rather than Binance's event ms would identify the relay as the input.
- **Test.**
  1. On 11-01 06-12 (dev), take the alt 5m/15m best-bid / best-ask changes and schedule-size deltas from dw_clob (server
     ms), and the BTC/ETH/SOL 4h touch changes from clob_crypto.
  2. Get per-symbol Binance futures aggTrades: REST `/fapi/v1/aggTrades` for 06-12, or the 11-02 daily archives.
  3. Run the X10 table per family: requote direction agreement at 0-50, 50-250 ms and 0.25-1 s after each candidate
     feed's move, and after each dv_rtds / dy_rtds publish and each dz_rtdsbn publish, with placebo windows before the
     move.
  4. Identify the cluster's adds by the family sizes. Check purity on a calldata sample, as X170 did for BTC.
- **Data.** dw_clob, clob_crypto, dv_rtds, dy_rtds, dz_rtdsbn, dm_bnf, Binance futures REST/archives, calldata via
  drpc.
- **Signature if true.**
  - One feed reaches >= 0.85 direction agreement within 250 ms on each alt family, and the others reach <= 0.65.
  - If the relay's publish clock wins over Binance's event clock, the module reads RTDS for prices.
  - If BTC futures beat the per-symbol futures on ETH/SOL, the alt quote is a cross-asset hedge.
  - If no feed exceeds 0.65, the alt ladder is mid-pegged with no reference trigger. Its side and presence are then the
    takers', and R9 should say so.

### I15-5. The long-horizon fair on the 4h ladder itself: fingerprinted rungs, ladder center, and a horizon-matched fair race (strong form of B3 for the non-BTC module; Kalshi weakened by C2)

- **Hypothesis.**
  - The 4h (and hourly) ladder is centred on a long-horizon fair, and the residual of that fair against the market mid is
    where the +5-10% per $ comes from.
  - Candidate fairs:
    - a Binance or Chainlink digital with horizon-matched realised vol (v3600 / v14400) or Deribit front-expiry IV;
    - the Kalshi KXBTCD ladder at its trade resolution;
    - for dailies, Polymarket's own deep "above ___ on <date>" ladder interpolated at priceToBeat (same Binance noon
      settlement).
- **Why it fits.**
  - C5: +400/+600 (BTC 4h) and +300 (ETH 4h) adds in the shared recorder, so the cluster's 4h quotes are observable
    without calldata.
  - The cluster's 4h fills are 94% maker by $.
  - The fair was tried only as a short-horizon Binance digital.
  - C2 shows the cluster does not quote below a 1-min Kalshi fair (0.62 of fills), so Kalshi enters as one candidate
    among four, not as the lead.
- **Test.**
  1. Check label purity of 600/400/300 by calldata on the fills of 10-31 12-18 and 11-01 08-12 (4h windows starting at
     12:00, 16:00 and 08:00 are development units).
  2. Rebuild the cluster's bid on each outcome per second, and the center c = (b_up + 1 - b_down) / 2.
  3. Regress c - mid on (fair_X - mid) for each candidate, with no fitting beyond one scale per candidate, chosen on
     10-31 and tested on 11-01/02.
  4. For hourly and daily, use the fills with the `prices-history` mid (I15-1). Add Kalshi trades (`/markets/trades`)
     instead of 1-min candles, and the daily above-K ladder's history.
  5. Locate the PnL by the winning fair's edge at the fill.
- **Data.** clob_crypto 4h books, calldata, Binance, the endpoint, Deribit option trades (history.deribit.com), Kalshi
  trades and candles, Gamma, `prices-history`.
- **Signature if true.**
  - One candidate explains c - mid with slope 0.7-1.3 and R^2 >= 0.5 on the test block, at least 0.2 above the
    short-horizon digital.
  - The later fills' profit concentrates in positive-edge fills on every fold.
  - If no candidate explains the center, the 4h ladder is mid-pegged. The money is then spread capture plus the takers'
    choice, and the "why it works" section should say so with the locked-pair share.

## Notes for the RE

- C1 needs no new data: run the nowcast inside `qu_today_scan.py` (two lines) and in X163's cells on the full 07-12
  block before anything else.
- For I15-2, verify the endpoint variant per symbol (`fiveminute` / `fifteen` for DOGE/BNB/HYPE) on one dev window
  against dv_rtds before the bulk fetch. C3's disagreement rate is from one clean morning. Weekday rates may differ.
- `prices-history`: confirm on a recorded book what a point represents before choosing its point-in-time lag. Gaps up to
  about 2 min occur in quiet hourly markets.
- The 600/400 adds on BTC 4h may be two makers. Do not assume 600 is the cluster's without the calldata join.
- The Kalshi hourly event ticker is `KXBTCD-<yy><MON><dd><HH ET, 24h>`, closing at the top of the ET hour. October 2026
  is EDT (UTC-4) until 11-01 06:00 UTC, EST afterwards. Handle that in any code that crosses the DST change.
