# Panel after iteration 7: mechanics and on-chain forensics

Lens: how the orders are built and matched: calldata, the salt counter, the re-price pass, the ladder, queue position,
the counterparties' order structs, and collateral. Written 2026-10-31, about 18:55 UTC.

**Data I used.**
- STUDY calldata, case by case (released lot, first half, 10-23..26): `calldata/study_*`, `b1_orders_lot.parquet`
  with `tag == 'study'`, and `exam/windows_5m.parquet` for payouts.
- The 10-26 public sample `calldata/pub1026_*`.
- Development block 10-31 12-18 UTC:
  - the RE's extraction `it6/ev_1793455600_1793463203` (14:06-16:13) and `it6/x_*`;
  - the all-match calldata `calldata/allmatch1793460000_*` (15:20-15:40);
  - the shared recorder (`clob_crypto`, `subs`), read only through `iter_live` for 16:50-16:56;
  - 30 Polygon block bodies (`eth_getBlockByNumber`, hashes only) and 24 `eth_call balanceOf` reads at blocks inside
    that block.

Part of this is live VALIDATE (15:00 or later), so treat those numbers as exploratory. I did not touch the historical
VALIDATE case by case, `.cache/live/sealed/`, or anything sealed. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it7m\`:
`txorder.py`, `takerclass.py`, `saltrate.py`, `xmkt.py`, `cash.py`, `gap1653.py`.

## What my checks found

1. **One pass re-prices the 5m and the 15m books together.** Unit: bursts of exact-500 adds, meaning two or more adds
   at the same price within 20 ms in one window.
   - Data: 14:06-16:13 UTC, 13,971 bursts (6,124 in 5m, 7,847 in 15m).
   - Of the 5m bursts, 41% / 58% / 67% have a 15m burst within 50 / 150 / 300 ms. A placebo with the 15m times shifted
     by 500 ms gives 11% / 27% / 43%.
   - Within one 5m window, a pass (bursts within 200 ms) re-posts both outcomes in only 29% of passes (median one burst
     per pass). The pass rewrites the rungs that changed; it does not redraw the whole ladder.

2. **The tx order inside a block is a partial match clock.** Data: 30 blocks of 15:20-15:40 UTC, each with 8 or more
   txs that also have a server match ms in `x`.
   - The within-block Spearman correlation of `transactionIndex` with the match ms has median 0.69 (p10 -0.17).
   - Pair inversions are 628 of 2,538 (25%), against 50% for block-second ordering.
   - Within a block, match times span a median 1.41 s (p90 1.79 s).
   - The 5,528 txs come from 1,891 different senders, so a per-sender nonce adds almost no ordering.

3. **Who pays the cluster can be read from the taker's order struct.** Data: STUDY, 8,256 cluster maker BUY fills with
   a known payout, 81% of them complement matches.

   | taker signatureType | share of fills | return | share of PnL |
   | --- | --- | --- | --- |
   | 0 (EOA) | 1.7% | -25.5% | -7% |
   | 1 (Magic proxy) | 21.4% | +2.5% | +30% |
   | 2 (Safe) | 11.2% | +21.4% | +70% |
   | 3 | 65.7% | +0.3% | +7% |

   - Round-USD BUY orders (the front-end "buy $X" form): 36% of fills, +5.6%, 107% of PnL. Other orders: -0.4%.
   - Taker limit 3-10 c beyond the cluster's level (a loose slippage limit sweeping into the ladder): 32% of fills,
     +6.5%, 87% of PnL. Limits within 0.5 c: +2.7%. Limits 10 c or more: -2.0%.
   - A non-zero builder code: 11.8% of fills, +4.8%.
   - The signatureType mix of the cluster's counterparties matches the market's. Takers in the public 10-26 sample are
     65% type 3, 20% type 1 and 12% type 2. So the cluster does not select retail by count. The profit, though, sits with
     one population.
   - Caveat: resolution PnL is noisy. Two type-2 takers account for $2.1k of the $3.4k.

4. **No collateral constraint.** Collateral (pUSD plus USDC.e) of bosona / almach / mo-money:

   | time (10-31 UTC) | bosona | almach | mo-money |
   | --- | --- | --- | --- |
   | 15:20 | $55.1k | $50.6k | $46.7k |
   | 16:53:00 | $55.9k | $51.4k | $47.1k |
   | 16:54:30 | $55.8k | $51.6k | $46.8k |
   | 17:50 | $54.0k | $49.7k | $45.6k |

   - The ladders need a few thousand dollars, so the 16:53 switch-off was not a cash limit.
   - The pre-end merges (median 65 s before the end) are not for cash either. They are housekeeping or an internal
     position cap.

5. **No venue-side websocket outage at 16:53.** The shared recorder's `clob_crypto` for 16:50-16:56 shows 200-600
   records per 10 s and no gap between records longer than 1.5 s. The only subscriptions are the regular window rolls
   (16:50:17, 16:55:19). The exam recorder's death at 16:53:27 was on the laptop side, and the cluster's switch at
   16:53:5x is not explained by a public feed outage.

6. **No API rate-limit ceiling in the salt counter.**
   - On STUDY, over 30-300 s spans between fills of the same wallet, the signing rate per wallet has q10 / 50 / 90 / 99
     / max of 9.3 / 16.5-17.3 / 27.2 / 37.6-37.9 / 49-55 orders per second. The distribution is smooth, with no flat top.
   - The rate is lower in 18-23 UTC (median 10.5-13/s) than in 00-17 UTC (19-23/s).
   - The three wallets are not in lockstep: the almach minus bosona salt difference drifts by about 630 per hour (about
     1% of the rate).

## Critique

1. **The frozen rule cannot pass scope on the next exam.**
   - `final_rule.py` builds only `window_slugs("btc", "5m", ...)`.
   - BTC 5m was switched off at 16:53 in all three wallets. The next exam takes the sealed blocks from 10-31 18:00.
   - If BTC 5m stays off, or comes back only part of the time, coverage of fills and absolute PnL collapses, whatever
     the AUC.
   - The engine is one pass over 5m and 15m (finding 1). The match-clock price already transfers (0.843 in 15m), and
     the posture side is 0.73-0.79 in 15m.
   - Put BTC 15m into `evaluate()` now. Also add every family that holds 5% or more of development fills (proposal M4).
     Scope is the only target condition the RE can secure by construction.
2. **The outcome metric is not the target's metric.**
   - `pnl_corr` 0.33 is the correlation of an expectation (sum over bins of P(fill) x (payout - price)).
   - The target asks for the realized PnL of an executable rule under strict fills.
   - That needs a replay of the quote against the taker stream (M2). An expected-value proxy will stay near 0.3 by
     construction, because the per-window PnL is set by which ladder side the takers actually hit.
3. **"Sellers follow the futures" mixes two populations.**
   - The fills are 81-95% complement mints: the counterparty buys the other outcome.
   - Pooled, takers follow the futures, and the pool is about 66% type-3 order flow, against which the cluster breaks
     even (finding 3).
   - I3 (X45) should be redone by taker population. Only the population that pays the cluster needs a trigger.
4. **Side is scored on the wrong unit.**
   - The fill side is scored per 10-s bin, with the posture taken at the bin start and taken from R3's presence score.
   - The decoded decision is the posture at each publish (0.79). The examiner's side is "the side it takes given that it
     acts".
   - Score the fill side per fill, with sign(CL edge - mid) at the last publish before its match ms. Report touch fills
     (78%) and deep-rung fills separately.
5. **Deep rungs are invisible in the sealed blocks.**
   - The top rung sits a median 5-7 ticks below the touch. `examrec` stores schedule-size deltas within 3 ticks only.
   - `rawrec` (full depth) stopped at 18:00 and covered BTC 5m and 15m only.
   - No generator test that needs the top rungs (M1, X51, the Tobit depth) can be examined or replicated on 11-01 06-12.
   - Restart a slim full-depth recorder before 11-01 06:00: only deltas whose |d| is in the size schedule, at all
     levels, for BTC 5m, 15m and 1h. Use the `Writer` and stay under 300 MB.
6. **Two loose ends I closed (do not spend time on them).**
   - Collateral does not bind (finding 4).
   - There was no public websocket outage at 16:53 (finding 5).
   - Two leads remain for X58: a loss controller, or a market-specific error on the engine's side. One way to tell them
     apart is to check whether the cluster's taker flattening (complement buys) fired in all three wallets at 16:53.

## Proposals (ranked by the chance they close the gap)

### M1. Invert the engine's internal price from simultaneous re-posts in several markets (new; strong form of B3, X19, X30)

- **Hypothesis.**
  - One pass prices every window of the same underlying from one internal estimate Ŝ_P (and σ̂).
  - Each market m's top rungs are digital(Ŝ, K_m, τ_m, closing-TWAP lock-in) ± h(τ_m).
  - Ŝ_P is one of three things: the raw Chainlink report that triggered the pass, a filter of it (an EMA or Kalman
    filter against its lag-1 autocorrelation of -0.47), or a blend with the futures.
  - The single-market center fits (R^2 0.21-0.81, X27, X41) are limited by h, rung depth and the PM-mid regressor. All
    three cancel when two markets are inverted at the same instant, because only Ŝ is common to both.
- **Why it fits.**
  - Finding 1: 41% of 5m bursts have a 15m burst within 50 ms (placebo 11%).
  - The pair sum (0.88) is invariant, and h is about 0.06.
  - The posture side follows the raw CL edge (0.79) with no fitted parameter.
  - The fills, the re-posts and the posture all point to one center. Nobody has identified it apart from the
    regressors.
- **Test.**
  1. Unit: each publish-triggered pass, i.e. the bursts in [P, P + 200 ms].
  2. Development data: `it6/ev` 14:06-16:13 (5m and 15m at full depth, stamp + 1.08 s as the publish proxy), then
     11-01 06-12 (dy_rtds publish ms, plus the full-depth recorder of critique 5).
  3. Take the top burst price per (market, outcome).
  4. Fit h(τ) on BUILD from the pair sums.
  5. For each pass with two or more markets, solve for Ŝ_P with σ from the 300-s futures vol x 1.4, or jointly for Ŝ and σ
     when three or more quotes exist.
  6. Report the following.
     - |Ŝ_5m - Ŝ_15m|, against the dollar equivalent of one tick at each market's delta.
     - Ŝ - CL_P (the latest published report), Ŝ - the futures mid at P, and Ŝ - EMA_k(CL) for k = 1-10 s.
     - Out of sample: the next pass's top rung in every market, predicted from CL_P through the fitted generator, and
       the share within a tick. The anchors are the touch, touch minus a tick, and the RE's 21%.
- **Data.** `it6/ev`, `dm_rtds` and `dy_rtds`, `dm_bnf` and `dx_bnf`, Gamma priceToBeat. For 11-01, a full-depth
  exact-class recorder for BTC 5m, 15m and 1h.
- **Signature if true.**
  - Ŝ_5m and Ŝ_15m agree within one tick-equivalent in at least 70% of passes.
  - Ŝ tracks CL_P (residual sd at most about $5) better than the futures and better than every EMA.
  - The top-rung prediction is within a tick for at least 60% of passes, in both markets.
  - Then the quote generator is decoded outright, and it transfers to 15m (scope).
  - If Ŝ is a filter of CL, the filter constant is the parameter R5 is missing. With the noise regime it should raise
    side, selection and presence at once.

### M2. Strict-fill replay of the decoded generator against the recorded takers (strong form of D3; the outcome target requires it)

- **Hypothesis.** The cluster re-signs every rung on every pass (life about 0.7 s) and is the last maker at its price in
  79% of shared-price groups. Its fill law is therefore mechanical: a rung at q on outcome s fills when a taker order
  reaching q exceeds the queue that stood at q when the rung was posted. Put the decoded generator (M1, or the current
  posture rule plus the 0.88 pair-sum ladder) through this law against the recorded taker stream. The replay should then
  reproduce the cluster's per-window PnL and its fills. In this system the taker flow is given, and the decision is
  where the quote sits.
- **Why it fits.**
  - Critique 2.
  - The replay's fill presence comes from the quote, so its gain over a quote-free baseline measures the decision and
    not co-occurrence.
  - The examiner already replays maker rules this way (R2: -12.8% at 2-s latency).
- **Test.**
  1. Development blocks: 10-31 12:00-16:53, then 11-01 06-12; BTC 5m and 15m.
  2. Run the generator on the publish clock (the report published at least 50 ms before), and in the examiner's ≥ 2-s
     latency variant.
  3. Queue: take the level size at posting from the `q` records (200 ms), minus 500 for each cluster-class rung already
     at the level.
  4. Fills: the `x` trades (server ms, price, size), applied in match order.
  5. Metrics:
     - per-window strict-fill PnL against the cluster's (Pearson and Spearman);
     - the share of the cluster's fill txs in which the replay also fills;
     - replay-fill presence AUC on 10-s bins;
     - fill side and price.
  6. Baseline: the same replay with a symmetric ladder around the PM mid (no Chainlink skew) and the same h.
- **Data.** The shared recorder `x`, `q` and `f` records (development blocks), `dy_rtds`, Gamma priceToBeat, and the
  cluster's live fills.
- **Signature if true.**
  - Replay PnL correlation of at least 0.5 in both Pearson and Spearman, against at most 0.3 for the symmetric
    baseline.
  - The replay fills in at least 50% of the cluster's fill txs.
  - Replay presence beats the activity baseline by at least 0.05.
  - If the correlation stays low with a good overlap, the PnL gap is the rungs' size and depth (M1, X51), not the
    posture.

### M3. Find the engine's universe through the signature counter, and freeze the exam scope (strong form of X21, X23)

- **Hypothesis.**
  - The engine signs about 13.5-17 orders per second per wallet across every market it quotes.
  - Posted adds of the cluster's size class, summed over markets, should equal the signing rate. Today BTC 5m and 15m
    account for about half (X23).
  - The other half is the rest of the universe (hourly, 4h, ETH, SOL, XRP).
  - After the 16:53 switch-off the signatures were re-allocated, not stopped. Wherever they went is the universe the
    sealed blocks will be scored on.
- **Why it fits.** Critique 1. Finding 6: the rate shows no cap, and it falls to 10-13/s in the evening (fewer markets
  quoted?). The X23 ratio is 0.5. The RE's own recorders see only BTC 5m current and next, and BTC 15m current.
- **Test.**
  1. Per minute on 10-31 12-18 and on 11-01 06-12, take the signed rate per wallet from the salts of consecutive
     filled orders. Use the live calldata `live1031_*`, spans of 60 s or less, interpolated.
  2. Compare it with exact-class adds in every book of the shared recorder (BTC, ETH and SOL 5m, 15m and 4h; read top-10
     increments) and with live activity per market family.
  3. Treat the remainder as unrecorded families or rejects. Close it with activity: fills by family per hour.
  4. Extend `evaluate()` to every family with at least 5% of development fills, starting with BTC 15m (τ = 900, same
     generator).
- **Data.** `calldata/live1031_*` (fetch the same for 11-01 06-12), the shared `clob_crypto`, and live activity of the
  three wallets.
- **Signature if true.**
  - With all families included, the add-to-signature ratio is about 1.
  - After 16:53 the share of signatures moves from BTC 5m to other families, while the total rate holds.
  - Scope of at least 80% of fills and of absolute PnL then holds on the sealed blocks by construction.

### M4. The paying counterparty, read from the order struct: split I3 by taker population (new; strong form of C3 and X45)

- **Hypothesis.**
  - The cluster's profit is paid by front-end market orders: signatureType 1 or 2, round-USD amounts, and limits 3-10 c
    loose that sweep into its rungs.
  - It breaks even against type-3 and EOA bots.
  - If that population arrives on a trigger the bots do not follow, that trigger is the public input of the presence
    gap that pooled I3 could not see. Candidates: the page's Chainlink display, the window open, the countdown, displayed
    moves with no futures counterpart.
- **Why it fits.** Finding 3 (type 2: +21% and 70% of PnL; round-USD: 107% of PnL; loose limits: 87% of PnL) and
  critique 3. The cluster's depth (5-7 ticks below the touch) is reachable only by sweeps.
- **Test.**
  1. STUDY case by case, and VALIDATE in aggregate: markouts at +10 s, +60 s and resolution by population, with
     window-block bootstrap CIs. Also the population mix of the cluster's fills against all maker fills at the same
     depth below the touch.
  2. Live: all-match calldata for two hours of 11-01 06-12 (batched `eth_getTransactionByHash`), together with dy_rtds
     publish ms. Measure the arrival hazard by population in the 0-2 s after a publish with |dCL| > $10 and no futures
     move, against futures moves of equal size with no CL move.
  3. If one population follows the display, add its predicted arrival (a function of the displayed CL move since the
     open; public) to the presence and selection models, against the activity baseline.
- **Data.** STUDY calldata (already in hand), live all-match calldata (new), dy_rtds, futures bookTicker.
- **Signature if true.**
  - The retail-type orders carry at least 80% of the markout profit, with the CI above 0.
  - Their hazard rises after display-only moves while the bots' does not.
  - A presence or selection gain of at least 0.02 over the strongest activity baseline from that hazard.
  - If they do not follow the display, it is still the quantitative "who loses" section for FINAL_RULE.

### M5. Historical posture labels from cleared levels in the tape (strong form of X16 and X19)

- **Hypothesis.**
  - On the lot, the cluster's at-touch posture is observed, censored, in the public tape. Take any tx whose maker rows
    on outcome s span two or more prices. It cleared every level above its lowest price, so every order resting there
    was filled.
  - At the top cleared level, the label is whether a cluster maker row exists at that price (cluster at the touch, 1/0).
  - With these labels, the quote-side rule sign(CL edge - mid) can be tested historically where it disagrees in sign with
    sign(Binance edge - mid). That is where the information source is identified on the lot's smooth regime.
- **Why it fits.**
  - X16 measured P(cluster | the hit clears the level) pooled over all levels and times (0.63%), the weak form, without
    any posture input.
  - The posture is decoded live only (0.79).
  - On the lot the fairs correlate 0.988, but the edges are small differences whose signs often disagree.
  - The RE has the CL 1-s series for 298 sample windows.
- **Test.**
  1. STUDY case by case, and the VALIDATE sample in aggregate, on windows with CL.
  2. Take every clean multi-level taker tx and label it as above.
  3. Features at its block time t: e_CL from the report stamped floor((t - 1432)/1000), e_BN from the Binance futures
     fair, the mid from the last clean prints of both tokens.
  4. Report the label AUC of e_CL and e_BN; the side accuracy in sign-disagreement events; and, as a check, the same
     labels on the live block against the observed book.
- **Data.** Lot tapes (data-api `/trades` maker rows with proxyWallet), the CL sample (`cl/cl_grid.parquet`), futures 1-s
  bars.
- **Signature if true.**
  - In disagreement events the label follows Chainlink at least 0.7 of the time (Binance at most 0.3), in both halves.
  - That verifies the information component on the lot (not a 10-31 noise artefact).
  - It also gives a historical resting-at-touch label that the examiner could score.

### M6. A historical match clock from tx index, signing ms and the speed bump (strong form of X52)

- **Hypothesis.** X52 assumed the in-block order is unobservable. It is observable, partly:
  - `transactionIndex` orders matches correctly in 75% of within-block pairs (finding 2);
  - every taker signs a ms timestamp;
  - marketable orders wait at least about 190 ms.
  An isotonic estimate of the match ms, min(block time, sign_ms + 190 ms) adjusted to respect tx order, should rebuild
  most of the match clock on the lot.
- **Why it fits.** R4's price is 0.83 on the match clock and 0.709 on the block clock, and the block clock confounds
  every historical print feature ("a print stamped T may have matched up to 2 s earlier").
- **Test.**
  1. Fit and score on the live slice: the true server ms in `x` against the estimate; report the median absolute error
     and the pair inversions.
  2. Apply to STUDY windows. This needs block tx lists (`eth_getBlockByNumber`, hashes only, about 150 blocks per window)
     plus the takers' sign_ms (cluster txs are already decoded; other prints need calldata, which can be sampled).
  3. Score R4's price rule and the trivial anchors.
- **Data.** Block bodies (hashes only; small) and calldata for the prints of sample windows.
- **Signature if true.** Lot price within a tick of 0.80 or more per wallet, matching the live 0.83. This is lower
  priority now that the exams run on recorded live blocks, where the server match ms exists.
