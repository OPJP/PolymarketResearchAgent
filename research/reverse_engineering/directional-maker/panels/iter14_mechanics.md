# Panel after iteration 14: mechanics and on-chain forensics

Lens: how the orders are built, sized, labelled and cancelled, with calldata as the ground truth for whose order is
whose. The main point: the next exam is the weekend and off-session blocks, and the notebook's picture of them rests
on two things that calldata contradicts.
- **"Small orders of non-schedule sizes" on BTC 4h, hourly, daily, ETH and XRP.** These are the same engine quoting
  every family at a fixed configured size per family. The sizes are identical in all three wallets.
- **"The 62/250 posts at the touch are at chance."** That set is mostly other makers' decided-window bids plus one
  15m window's last three minutes. It says nothing yet about the cluster's off-session ladder.

The second point is about method. The 1-s presence cell cuts between the engine's trigger (a public Chainlink publish)
and its response (0-150 ms later). The look-ahead correction therefore threw away the decision input instead of
re-anchoring the unit to the trigger.

Written 2026-11-01, 06:55-07:25 UTC.

**Data I used.** Development data only:
- STUDY calldata of the cluster's other-market fills (`calldata/othstudy_*`, 7,273 cluster orders, 10-23..26) joined
  to `other_mkts_study.parquet`;
- all-match calldata of 10-31 15:20-15:40 (`calldata/allmatch1793460000_*`, 5,528 transactions, 11,253 maker
  orders) and `liveall1031_*`;
- the RE's rebuilt quote unit (`it14_qu_rebuilt_1793455200_1793469600.parquet`) and `it13/fills_posts.parquet`;
- the exam-folder activity (10-22..30; STUDY days case by case, nothing case by case on 10-27..30);
- my iteration-13 remainder table (`remainder_trail.parquet`, 10-31 15-18).

I did not open `.cache/live/sealed/` or any sealed block.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it14m\`:
`oth_orders.py` and `wkd_sizes.py`. Run them from the repo root. Each one peaks below 200 MB.

## What my checks found

1. **Every non-BTC-5m family has a fixed configured order size, and it is the same in all three wallets.**
   - Source: calldata original sizes of the cluster's maker orders, STUDY 10-23..26.
   - Fingerprint: timestamp 0, counter salt, metadata and builder 0 in 100% of the 7,273 orders. It is the same signer
     as BTC 5m.
   - Modal original size per family, with the mode's share per (family, session, day):

     | family | off session | US session / high level |
     | --- | --- | --- |
     | BTC hourly | 38 (0.71-0.86) | 300 (0.64-0.88) |
     | BTC 15m | 62 (0.53-0.93) | 500 (0.74-0.77) |
     | SOL 5m | 12 (0.58-0.96) | 100 (0.82-1.00) |
     | ETH 5m | 19 (0.51-0.91) | 150 / 19 |
     | XRP 5m | 10 (0.67-0.91) | 50 (1.00) |
     | BTC 4h | 400 (0.76-0.95) | 400 |
     | ETH 15m | 30 (0.83-0.98) | 30 |
     | ETH hourly | 50 (0.65-0.96) | 50 |
     | BNB hourly | 50 (0.70-0.91) | 50 |

   - Per wallet, the modes are 38 / 62 / 12 / 19 / 10 / 400 / 30 / 50 / 50 in every wallet, with mode shares
     0.59-0.94.
   - **The low level is the high level / 8 under round-half-even:** 500 → 62, 300 → 38, 100 → 12, 150 → 19.
     - That is exactly what Python's `round()` gives.
     - JavaScript `Math.round` would give 63 / 38 / 13 / 19, and `floor` would give 62 / 37 / 12 / 18.
     - The night 250 = 500 / 2, and the late-window one-fifth level (100 = 500 / 5, 12 = round(62.5 / 5)), fit the same
       arithmetic.
   - **The high level is not one global clock.** The first high-size order of 10-26 is at different times per family:
     XRP 01:01, ETH 5m 01:45, SOL 03:45, BTC hourly 08:12, BTC 15m 12:27 UTC. This fits X34's per-window volatility
     upgrade, applied per family.
   - **The idle weekend blocks are this table running alone.**
     - 10-24 06-12: 371 orders, 89% maker, all BUY. Modes: BTC hourly 38, ETH 15m 30, XRP 5m 10, SOL 5m 12, BTC 4h 400,
       ETH hourly / ETH daily / BNB hourly 50.
     - 10-25 00-06: 394 orders, 90% maker. Same sizes.
     - "Non-schedule" was measured against the BTC 5m size list.
2. **The quote-unit labels outside the 500 class are other makers' orders.** Source: 10-31, all-match calldata of
   15:20-15:40.
   - Exact-1000 filled maker orders: 87, with **0% the cluster's**. All come from one maker (`0x55aeeb3e...`,
     signature type 2, bids at 0.01).
   - Exact-250: 90 orders, 0% the cluster's, from 6 makers, at 0.01 / 0.02 / 0.99.
   - Exact-62: 2 orders, 0% the cluster's.
   - Exact-500: 207 orders, 88% the cluster's. The other makers' 500s sit at 0.01 and 0.99.
   - In the rebuilt quote unit (6,200 posts, bid price on the posted outcome):
     - the 1000 posts are 92% bids at ≥ 0.97;
     - the 250 posts are 38% at ≤ 0.03 and 35% at ≥ 0.97;
     - **10.7% of the 500 posts sit at ≤ 0.03 or ≥ 0.97.**
   - Posture accuracy with the table's stored F:

     | posts | posture accuracy | n |
     | --- | --- | --- |
     | 500, non-extreme | **0.777** | 4,887 |
     | 500, extreme | 0.583 | 588 |
     | 1000 | 0.637 | — |
     | 250 | 0.589 | — |
     | 62 | 0.460 | 324 |

   - The decided-window extremes, mostly other makers' 0.01 / 0.99 bids, pull the main ladder's number down by about
     2 points.
3. **The cluster's 62s on 10-31 are a late-window rung, not the off-session ladder.**
   - `fills_posts` has 58 cluster orders of original size 62. Of these, 39 are in `btc-updown-15m-1793463300`
     (16:15-16:30), filled at 23-187 s left (median 45 s).
   - For comparison:
     - the 100s fill at 56-117 s left (median 93 s, BTC 5m);
     - the 500s have a median of 178 s left.
   - 146 of the quote unit's 326 62-posts are in that one window, mostly 16:27-16:29. That is where the k-1.0 posture
     fails for every size (0-60 s left: 0.491; k 0.3 best).
   - So no development block with books has yet recorded the cluster's 1/8-level ladder. The sealed weekend blocks
     will be mostly that ladder.
4. **mo-money cancels a partially filled rung later than the other two wallets** (10-31 15-18, exact-remainder
   removes after the last fill).
   - Median latency: mo-money 312 ms (n 54), almach 73 ms (39), bosona 118 ms (50).
   - Share above 250 ms: 0.56 for mo-money against 0.38 for the other two (one-sided Mann-Whitney p = 0.034).
   - This is small-sample, but it fits its longer-lived 500s (age p75 2.5 s against 1.8 s, X76) and its anti-posture
     resting fills (H13-MOMONEY-RESTING).

## Critique

1. **The exam scope is being solved without the module table.**
   - X161 plans R9 as "every listed crypto family" with a cheaper-token fallback, and describes the weekend flow as
     small non-schedule orders. The calldata says otherwise: it is the same quoting engine on each family at a
     configured size, maker-side, BUY only.
   - With those sizes:
     - each family's quote is labellable on `dw_clob` / `dx_clob`;
     - the universe is the families with configured-size orders;
     - the size component becomes a formula.
2. **A contaminated set is reported as a fact about the off-session engine.**
   - "The 62/250 posts at the touch are at chance (0.51, n 521)" appears in FINAL_RULE, the strategy statement and
     X160's design.
   - The 250s are not the cluster's, and the 62s are one window's last minutes.
   - If the off-session ladder actually follows the posture, R9's side on the exam blocks should be the posture, not
     the cheaper token.
3. **The look-ahead correction removed the trigger instead of re-anchoring the unit.**
   - The engine re-prices 0-150 ms after each public publish (X44).
   - On a clock-second cell the triggering report is published inside the cell. A point-in-time model must then use
     the previous report.
   - The drop from +0.090 to +0.029 is the size of that loss, not evidence that the gain was spurious. A unit anchored
     at the publish ms can use the triggering report legitimately.
   - The side analysis already did this (0.831 on the exact clock against 0.76 at a fixed lag). Presence did not.
4. **Every outcome number comes from the lot's block clock with trade-through fills.**
   - The ~0.5 oracle ceiling is a ceiling of that fill model. That model cannot credit fresh at-touch posts.
   - X64's recorded-book FIFO replay, the original proposal, was never run. Yet the exam's future blocks are exactly
     where the server-ms trades and the L2 queue exist.
5. **Per-wallet replication is an exam condition, and mo-money's deficit is still attributed to "an unnamed input".**
   - A slower cancel path is a mechanical candidate that has not been tested per wallet.

## Proposals (ranked by the chance they close the gap)

### P1. The per-family configured size vector is the engine's module table: build R9's universe, size rule and family quote labels from it (strong form of X107, X113 and X123; the missing input of X161 and X151)

- **Hypothesis.**
  - One engine quotes every crypto family at a configured base size. The order size is
    `round_half_even(base_f × m)`, where:
    - m ∈ {1, 1/2, 1/8} is chosen per family and window (session default plus a volatility upgrade, X34);
    - a 1/5 factor applies in the late phase of a window.
  - A family is "on" exactly when its configured-size orders exist.
  - On weekends the active set is {BTC hourly 38, ETH 15m 30, ETH 5m 19, SOL 5m 12, XRP 5m 10, BTC 4h 400, ETH and
    BNB hourly / ETH daily 50, BTC 15m 62}. BTC 5m is switched off by hand.
- **Why it fits.**
  - Check 1: stable modes over four days, identical in three wallets, and the /8 arithmetic in four families.
  - The idle weekend blocks are made of these sizes.
  - The salt counter keeps signing ~12/s across the BTC 5m switch-off (X65, X82): the engine was busy on the other
    families.
- **Test.**
  1. **Size formula on the whole development history.**
     - Extend the calldata of the cluster's other-market fills to BUILD (10-09..22) and to the 10-31 / 11-01
       development blocks. Sample up to about 20k transactions (publicnode batched `eth_getTransactionByHash`, about
       75 tx/s).
     - Per (family, window), fit base_f and m.
     - Report the exact-match share per family. The non-matching orders should be pairing tracers (|imbalance|
       sizes); check that.
     - Find the change points of m per family, and see whether they line up with salt resets.
  2. **Universe.**
     - Freeze "every family with configured-size orders in the previous 7 days of development data", listing-based.
     - Score its fill and |PnL| coverage on the weekend analogs: 10-10/11 and 10-17/18 (BUILD), 10-24/25 (STUDY), and
       the current development block 11-01 06-12.
  3. **Labels.**
     - On `dw_clob` (ETH, SOL, XRP, BNB 5m/15m) and `dx_clob` (BTC 15m), take the at-touch adds of exactly the
       family's configured size.
     - Measure purity from all-match calldata of one 20-minute slice per family (the tx hashes of `dw_clob` 'x'
       trades).
     - Score the posture per post with each symbol's own Chainlink (rtds eth/sol, dv_rtds xrp/bnb), on the exact
       publish clock where recorded, on 11-01 07:00-12:00.
- **Data.** On disk: `othstudy` calldata, `other_mkts_study`, `dw_clob`, `dx_clob`, `dv_rtds`, rtds. To fetch: BUILD
  other-market calldata, and the all-match calldata of one 20-minute slice per family on 11-01 07-12.
- **Signature if true.**
  - At least 85% of non-tracer cluster orders are reproduced exactly by the size formula, with the same base table
    in all three wallets.
  - The configured-size universe covers at least 0.95 of fills and |PnL| on every weekend analog.
  - Per-family label purity is at least 0.85.
  - The per-family quote posture is at least 0.75.
  - R9's side then needs no cheaper-token fallback.
- **If false.** Purity below 0.6 means other makers quote at the same sizes, and the family quote unit falls back to
  fills. The universe and the size formula stand anyway.

### P2. Anchor the presence unit at the public publish: the at-touch resting state 250 ms after each Chainlink publish (strong form of X50 and X162)

- **Hypothesis.**
  - The quote decision is made at each publish pass, from the report just published.
  - Measured on the pass, the decoded inputs determine which outcome the cluster holds at the touch. The clock-second
    cell hides this behind its boundary.
- **Why it fits.**
  - X162: +0.090 when the cell could see the report published inside it, and +0.029 when it could not.
  - X44: the re-posts agree with the report's change 0.719 in the 200 ms after a publish, against 0.441 before.
  - The quote side is 0.831 on the exact publish clock against 0.75-0.76 at a safe fixed lag.
  - X50's per-report pilot already gave 0.776-0.793 with the old sigma and the stamp clock.
- **Test.**
  - **Unit:** (publish p from dy_rtds btc 'P', window, outcome).
  - **Labels:**
    - (A) a post at that outcome's touch in (p, p + 250 ms], from the pure classes of P3;
    - (B) the resting state at p + 250 ms. Track the adds and exact removes of pure-class orders in `dm_clob_raw` /
      `dx_clob`; an order is resting if it was added and not yet removed.
  - **Features at p:**
    - the new report's posture edge (k 1.0 × futures sigma300, Gamma strike) minus the mid at p;
    - |Δreport| and its sign;
    - mid, spread and time left.
  - **Baseline:** the same model class on activity at p: prints over 0.25 / 1 / 2 / 5 / 10 s, mid changes, last print
    side, time left.
  - **Variant:** add each clean print at either touch as an extra pass, the trade-follow trigger of X35.
  - **Split and scoring.**
    - Fit on 10-31 17:29-18:00 plus 11-01 07:00-09:00; test on 09:00-12:00, then on the next development block.
    - 20-minute block bootstrap.
    - Report WHEN (any post) and WHICH outcome separately.
    - `evaluate()` builds the same unit on the sealed blocks from `dy_rtds` and `dx_clob`.
- **Data.** On disk, or recording now: `dy_rtds` (publish ms), `dm_clob_raw` / `dx_clob`, `dx_bnf`, Gamma strikes.
- **Signature if true.**
  - Test AUC of at least 0.85 on label B (or A), with a gain of at least +0.05 over the activity model and a block
    bootstrap lower bound above 0.
  - WHICH at least 0.85.
  - This is the only route I see to a legitimate presence gain above 0.05. The level is the open question.
- **If false.** A gain of at most +0.03 on the pass unit means posting is driven by the touch (trade-follow), not by
  the report. The quote-presence gap is then co-occurrence by construction, and it is measured.

### P3. Label purity before any quote-unit or off-session claim (new; corrects "62/250 at chance")

- **Hypothesis.** The exact-size labels mix in other makers' orders and decided-window extreme bids, the deep module
  or other makers'. This understates the main ladder and leaves the off-session ladder unmeasured.
- **Why it fits.** Checks 2 and 3.
- **Test.**
  - For every scored block, fetch the all-match calldata of one 20-minute slice per hour (the tx hashes of `dx_clob`
    'x', about 5k transactions per slice).
  - Tabulate purity by:
    - exact size;
    - bid region (≤ 0.03 / 0.03-0.97 / ≥ 0.97);
    - burst multiplicity (1 / 2 / 3 within 25 ms);
    - time left (0-60 / 60-180 / > 180 s).
  - Keep the classes with purity of at least 0.9.
  - Re-score the quote-unit side (exact publish clock) and P2 on the pure, non-extreme set.
  - Score the extreme-price bids as their own order type, the deep module (X120).
  - Score the 62 class only on 11-01 07-12 or 18-24, wherever the 1/8 level runs, with pure labels and by time-left
    band.
- **Data.** `dx_clob`, `dm_clob_raw`, and calldata via publicnode.
- **Signature if true.**
  - Pure non-extreme 500 posts reach at least 0.85 on the exact publish clock (0.831 pooled now).
  - Pure 62s outside the last 3 minutes reach at least 0.75. Then the off-session ladder follows the posture, and the
    "62/250 at chance" statement is withdrawn.
  - If pure 62s are still at chance, the off-session side really is a different rule. That is X160's branch, now
    measured on the right orders.
- **Rank.** This is the cheapest of the five (under an hour) and a prerequisite for X160 and P2. Run it first.

### P4. The outcome ceiling on recorded blocks: a FIFO replay with the recorded queue, the observed quote as an oracle against the public quote (strong form of X64; the outcome analogue of X72)

- **Hypothesis.**
  - The lot's ~0.5 oracle-side ceiling and its 0.21 public correlation come from the block clock and from
    trade-through fills, which cannot credit fresh posts at the touch.
  - With server-ms trades and the L2 queue at the post, a replay of a decoded at-touch quote reproduces the cluster's
    window PnL.
- **Why it fits.**
  - 73% of fills are fresh at-touch posts about 0.9 s old, joined behind a median of 500 shares.
  - The fast-clock lot replay already removes the adverse selection (return −16% → ~0%, X106).
  - With the cluster's own fills at one share, the window correlation is 0.69-0.78 (X22).
- **Test.** Blocks: 10-31 14-18 (about 52 BTC 5m/15m windows) and 11-01 07-12.
  - **(a) Oracle quote:** the cluster's pure exact-size resting orders per outcome, from the book (price, size,
    post ms).
  - **(b) Public quote:**
    - side: the posture from the latest published report;
    - price: the touch (R7 on the match clock);
    - size: the P1 formula;
    - one taker batch per order, re-posted at each publish.
  - **Fills:**
    - The rule's order enters the queue at post ms + L (L = 0.15 s and 2 s), behind the recorded L2 size at its level.
    - It fills from recorded trades at its level (server ms) beyond the queue ahead, or by trade-through.
    - Strict: no credit for volume traded before entry.
  - **Scoring:** per-window PnL correlation with the cluster's realized PnL, the return, and a window bootstrap.
- **Data.** `dm_clob_raw` (full depth on 10-31), `dx_clob`, the shared `clob_crypto` trades, `dy_rtds`, activity.
- **Signature if true.**
  - The oracle replay reaches at least 0.75: the FIFO model is right.
  - The public replay reaches at least 0.5 at L 2 s: the outcome bar is reachable on the recorded exam blocks.
  - If the oracle replay stays at or below 0.55, the outcome gap is in queue priority against other makers. That is
    then measured, not assumed.

### P5. mo-money's deficit as a slower cancel path (per-wallet replication; strong form of X76 and X96 per wallet)

- **Hypothesis.**
  - mo-money's engine instance cancels and replaces later (Check 4: 312 ms against 73-118 ms after a fill).
  - Its rungs therefore stay at prices the posture has already left. That makes its anti-posture resting fills
    (41% of its class-(ii) fills) lost cancel races specific to one wallet. X96 rejected this hypothesis pooled
    across wallets.
- **Test.**
  - On 10-31 14-18 plus 11-01 07-12, compute per wallet:
    - (a) the latency from a fill to the exact remove of the remainder;
    - (b) the latency from a posture-flipping publish to the remove of each filled order's resting rung on the
      now-wrong side. Attribute through the remainder chain and calldata.
  - Re-score mo-money's class-(ii) fills with the posture taken at (taker arrival − its own measured cancel latency).
- **Signature if true.**
  - mo-money's cancel latency is at least 2× the others' (bootstrap lower bound above 1).
  - Re-scoring on its own latency brings its side within 3 points of the other wallets: the per-wallet replication
    condition is then met by a wallet-specific latency parameter.
- **Rank.** Lowest of the five: the sample is small, and it is an own-clock parameter, but it is the only mechanical
  candidate for the per-wallet condition.

## Notes for the RE

- Correct these statements in FINAL_RULE, the strategy statement and NOTES:
  - "62/250 posts at chance";
  - "non-schedule sizes" on the weekend;
  - "500/1000" as one class. The 1000s on 10-31 are another maker's bids at ≥ 0.97.
- The extreme-price 500 posts (10.7%) belong in the deep or near-certain order type, not in the posture ladder.
- Python-style round-half-even in the size arithmetic is a C8 fingerprint. A GitHub search for Python Polymarket
  makers with a per-family base size and a 0.125 night multiplier is cheap.
