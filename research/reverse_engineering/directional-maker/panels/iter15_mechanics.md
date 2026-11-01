# Panel after iteration 15: mechanics and on-chain forensics

Lens: how the orders are built, which engine instance posts them, how long they rest, and what a fill needs
mechanically. Two points matter most.

1. **The 11-01 replication failure was measured on a different operating mode, not just a different Chainlink regime.**
   On 11-01 07:00-08:00 the main BTC 5m/15m ladder ran in one wallet. bosona had 234 BTC trades, almach 20 and
   mo-money 22, and almach's and mo-money's fills were 65-86% at prices <= 0.10 or >= 0.90, which is the
   decided-window deep-bid module. The book shows the same thing: 89% of the pure 500 posts are singles, against 43% on
   10-31. So X160 compared a three-instance block with a one-instance block. The noise-regime reading may still be
   right, but it is confounded with this mode change. Per-wallet replication is an exam condition, so the mode matters
   for the exam too.
2. **The primary metric is a unit whose ceiling is below the bar, and the unit whose ceiling is above it is not being
   worked on.**
   - 10-s fill presence with the observed quote as an oracle tops out at ~0.80 (X72). No quote decode can reach 0.85
     there.
   - Print-level selection with the same oracle reaches 0.81-0.83 at recall 0.62-0.69 and lift 3.3 (X72). The missing
     input is the cluster's resting state at the print: is a 500 live at the touch of the sold token, and how much
     queue sits ahead of it.
   - Every iteration since 13 has decoded the side of posts (adds). None has decoded the resting state (adds minus
     cancels), the cancel rule or the queue position.

Written 2026-11-01, 08:35-09:10 UTC.

**Data I used.** Development data only:
- the RE's rebuilt quote units `it14_qu_rebuilt_1793455200_1793469600` (10-31 14-18) and
  `it14_qu_rebuilt_1793516400_1793520000` (11-01 07-08);
- activity `act15_*` for 10-31 00-06, 10-31 12-18 and 11-01 06:00-08:02, plus BUILD `activity_*.parquet`
  (10-08..22);
- `it15_today_orders.parquet` (11-01 calldata);
- `it15_nb_public_lot.parquet` (STUDY, VALIDATE aggregate, dev after T0; only aggregates by fold, family and phase
  printed).

I did not open `.cache/live/sealed/` or any sealed block.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it15m\`:
`wallet_mode.py`, `post_inventory.py` and `nb_price_law.py`. Run them from the repo root. Each one peaks below 250 MB.

## What my checks found

1. **On 11-01 07-08 the main BTC ladder ran in one wallet. This had not happened in BUILD.**

   BTC 5m/15m trades per wallet per hour:

   | hour (UTC) | almach | bosona | mo-money |
   | --- | --- | --- | --- |
   | 10-31 00-05 (each hour) | 47-166 | 48-169 | 59-144 |
   | 10-31 13-17 (each hour) | 71-325 | 39-293 | 47-352 |
   | **11-01 07** | **20** | **234** | **22** |

   - In BUILD (10-08..22, 325 hours with at least 60 BTC 5m/15m trades), a max/min wallet ratio of 5 or more occurs in
     0.3% of hours, and that one hour is a 01:00 restart hour. A ratio of 3 or more occurs in 2.5%.
   - Share of each wallet's 11-01 07-08 BTC fills at prices <= 0.10 or >= 0.90: almach 0.65, mo-money 0.86, bosona 0.27.
     On 10-31 14-18 the same share is 0.14-0.16 for all three.
   - First BTC fill: bosona 07:00:48, in the first window listed after the DST gap. almach and mo-money both start at
     **07:15:03**, the same second, at the 15m 07:15 window's open. Their later fills also coincide with each other
     (07:44:00/01, 07:53:18), at median 110-372 s left.
   - So on 11-01 the cluster ran {main ladder: bosona} plus {deep-bid module: all three}. The 11-01 calldata agrees:
     127 of bosona's filled BTC orders against 16-17 for each of the others.
2. **The book shows the mode change.**
   - Burst multiplicity of the non-extreme at-touch 500 adds (same window, side, price and size within 25 ms):

     | span | singles | triples |
     | --- | --- | --- |
     | 10-31 14-18, every half hour | 0.41-0.49 | 0.24-0.32 |
     | 11-01 07:00-07:30 | 0.82 | 0.07 |
     | 11-01 07:30-08:00 | 0.94 | 0.01 |

   - The 10-31 numbers are flat across the 16:53 switch-off and the ad hoc restarts.
   - So "one engine posts each decision in all three wallets" describes 10-31. It does not describe 11-01.
3. **The posts lean toward the cluster's own inventory at about the same rate in both blocks.**
   - Pure 500 posts on the cluster's held outcome (aggregate net shares up to 1 s before the post): 0.642 on 10-31
     (n 3,170) and 0.663 on 11-01 (n 285).
   - Posts on the outcome of the window's last cluster fill: 0.638 and 0.728.
   - So own state is a stable ~0.65 description of the post side in both blocks. The public posture swings between
     0.78-0.87 (10-31) and 0.60 (11-01).
   - (`sd` in the rebuilt table is the Up book side: 1 = Up bid, 0 = Up-book ask = Down bid. Iteration 14's "own
     inventory does not set the quote's side" should be re-read with that mapping.)
4. **Non-BTC fill prices: the opening bids sit at the market, and the later bids are pegged to the last print, not to a
   fair.**
   - Opening fills (under 20 s):
     - price minus the last public print: median 0.000-0.020;
     - F(k 0.7) − price: median 0.07-0.11, IQR 0.05-0.08;
     - F_s − p_pub ≥ 0.05 for 77% (STUDY) / 62% (VALIDATE) of opening fills.
     - So at the open the engine joins the market price on the outcome whose fair exceeds the market. The cap does not
       bind there.
   - Later fills:
     - price minus the last public print: median 0.00-0.02;
     - within ±0.01 of "last print − 0.01": hourly 0.52-0.62, 4h 0.38-0.40, alt 15m 0.37-0.41, alt 5m only 0.18;
     - F − price IQR 0.12-0.20, with no constant offset (best share within a tick 0.08-0.19).
   - The module's money-making later bids are therefore touch or last-print pegged, not fair minus spread. Their price
     is decodable only from the book they sit in.

## Critique

1. **The regime explanation for the X160 failure is post hoc and confounded.**
   - The two blocks differ in the Chainlink noise ratio (8.2 against 0.92). They also differ in:
     - the number of instances running the main ladder (3 against 1);
     - day and session (Saturday US afternoon against Sunday Asia morning);
     - post multiplicity.
   - No test so far separates these.
   - The panel's earlier per-wallet facts (mo-money's slower cancel, its anti-posture rungs) show that the instances
     are not identical. One instance alone is a different sample.
2. **Work on fill presence cannot reach the bar.**
   - The primary metric (BTC 5m 10-s fill presence) has an oracle ceiling of ~0.80. Pushing it is wasted budget
     except as reporting.
   - The examiner accepts selection (AUC ≥ 0.80 with recall ≥ 50% at lift ≥ 3). It also accepts presence on "whether
     it has an order resting".
   - On print selection the oracle clears the bar. Public inputs are at 0.742, recall 0.42 (X150). The gap between
     them is the resting state, which nobody has decoded.
3. **The quote is still treated as a side choice.**
   - The quote unit counts at-touch adds and scores which outcome they are on.
   - A two-sided maker's state is a price per outcome, and most of the information is in where the far side rests
     and when the near side is pulled.
   - The fair-cap (capped-join) law was tested only on pairing tracers (X135) and on the block clock (X136 step 2).
     It was never tested on the main 500 ladder with the full-depth book.
4. **The idle-weekend module was decoded on fills only, although the books exist.**
   - `dw_clob` and `clob_crypto` record ETH, SOL, XRP, BNB and DOGE 5m/15m and BTC, ETH and SOL 4h. The per-family
     configured sizes (10, 12, 19, 30, 38, 50, 400) are distinctive labels.
   - The opening quote (0.87-0.92 on fills) can be scored as a quote and as a presence unit at the open, where activity
     baselines are weakest. That has not been done.
5. **evaluate() assumes three synchronized instances.**
   - The per-wallet replication condition counts only wallets with at least 300 fills or 30 markets. With one instance
     on the main ladder, almach and mo-money may fall below that.
   - Their deep-bid-only fills would then be scored by R8's decided branch alone. The rule should report the
     per-wallet module mode it sees.

## Proposals (ranked by the chance they close the gap)

### P1. Decode the resting state at each print, then score print selection (strong form of X72, X150, X169, D2 and X71; the only unit whose oracle ceiling is above the bar)

- **Hypothesis.** A cluster fill at a print requires three things:
  - (a) a pure-class order live at the touch of the sold token at the match;
  - (b) the print reaching it through the queue ahead;
  - (c) no cancel in between.
  (a) and (c) are public functions of event clocks: posts on Chainlink publishes and after prints, and cancels on
  publishes that move the posture against the order, on futures moves and on the touch moving away. (b) is a public
  function of L2 depth at the order's last re-sign. Together they turn print selection from 0.74 into ≥ 0.80.
- **Why it fits.**
  - The oracle numbers (X72).
  - D2: the post hazard on public clocks reaches 0.826 per 50 ms with the true publish ms.
  - B2: the life of an exact-500 order has median 0.69 s, cancel-to-re-add median 15 ms, and 52-87% of removals are
    re-signed within 100 ms.
  - The cluster is first at its level in only 31% of multi-maker matches.
  - X176: the taker's size selects the cluster's fills, which is what (b) predicts.
- **Test.**
  1. **Order life-cycle table.** On 10-31 14-18 and 11-01 07-12, from `dm_clob_raw`, build every pure 500 order
     (non-extreme, purity 0.88-0.91 by all-match calldata): add ms, price, outcome, remove ms, and filled/cancelled. A
     remove matched to a print at that level in the same ms counts as a fill. Attribute the filled ones to a wallet
     through calldata.
  2. **Two frozen hazards on public covariates.** Fit both on one block.
     - **Post hazard:** per (window, outcome, 50 ms). Covariates are time since the last publish; the posture and its
       change; time since the last print at the touch and that print's side; the touch change; |futures move| over
       0.25/1 s; time left.
     - **Cancel hazard:** per live order per 50 ms. Covariates are the posture change since its post, signed toward its
       outcome; the touch moving away; futures moves; age; time left.
  3. **Resting probability.** Integrate the two hazards along the public event path to get P(cluster live at the touch
     of s at the print ms).
  4. **Queue ahead.** Estimate it as the L2 size at the level at the cluster's expected last re-sign (the last publish
     pass), minus prints at the level since then. See P5 for the law that justifies this.
  5. **Print-level selection score.** P(live) × P(print size > queue ahead).
  6. **Baseline.** A LightGBM on prints, time left, price level, print size and the L2 depth at the touch. Depth goes
     into the baseline too, so the gain is not depth co-occurrence.
  7. **Splits.** Fit on 10-31, test on 11-01, and the reverse. Use a 20-minute block bootstrap. Report per wallet, and
     report the bosona-only main ladder separately (P2).
- **Data.** On disk or recording: `dm_clob_raw`, `clob_crypto` prints with server ms, `dy_rtds` publish ms, `dx_bnf`,
  all-match calldata (publicnode).
- **Signature if true.**
  - Selection AUC ≥ 0.80 with recall ≥ 0.5 at lift ≥ 3 on both test blocks.
  - A gain ≥ 0.05 over the depth-augmented activity baseline, with the bootstrap lower bound above 0.
  - The decoded state recovers ≥ 60% of the oracle's gain.
- **If false.** Report the fraction of the oracle's gain each hazard recovers.
  - If the cancel hazard is unpredictable from public events (AUC ≤ 0.6) while the post hazard is not, the unexplained
    part is the cancel path. That is the instance's own clock (X172) and is quantified per wallet.
  - That is wall-grade evidence for the selection bar, not a shrug.

### P2. Per-wallet module configuration: label each block's mode and re-run X160 per instance (new; from checks 1 and 2)

- **Hypothesis.** Modules are switched per engine instance, not per engine.
  - The main BTC ladder, the deep-bid module and the non-BTC families each run in a subset of wallets.
  - The mode can be read from public data: post multiplicity in the book plus calldata attribution of fills.
  - Each instance's quote follows the same law. The 11-01 failure is mostly a single-instance sample: one wallet's
    posts, one queue position, one cancel latency.
- **Why it fits.**
  - Checks 1 and 2.
  - The synchronized 07:15:03 start of almach and mo-money, against bosona's 07:00:48.
  - The RE's own per-wallet scope on 11-01: bosona 0.86, almach 0.51, mo-money 0.52.
  - Iteration 15's per-wallet cancel lag (mo-money about 1 s stale).
- **Test.**
  1. For every development block with books (10-31 12-18, 11-01 06-12, and each new development block), tabulate per
     10 minutes:
     - fills per wallet by module: main ladder (non-extreme 500 / 100 / 62) against deep bids (≤ 0.10 or ≥ 0.90)
       against pairing sizes;
     - book burst multiplicity of pure 500 adds;
     - calldata attribution of filled 500s and their post's multiplicity.
     Freeze a mode label: number of instances on the main ladder.
  2. Re-score the quote side within one instance and one mode.
     - bosona's attributed filled posts on 10-31 against 11-01, both class (i), within the same |F − mid| bands
       (< 0.05, 0.05-0.1, ≥ 0.1).
     - If bosona's band-conditional posture accuracy matches across the two blocks (within 0.03), the failure is
       composition (fewer large-|F − mid| moments and one instance), not a changed rule.
  3. Look for what switches an instance. Find per-wallet asymmetry events (ratio ≥ 3 in 10-min bins) on BUILD and on
     the released lot (aggregate counts on VALIDATE). Test, per wallet:
     - (a) the wallet's own realized PnL since the 01:00 restart at the switch, for a common per-wallet threshold (the
       cluster-level trip had no fixed level, $1.1k-$14.6k);
     - (b) switch-ons at window boundaries (:00:03, :15:03), which would point to periodic market discovery;
     - (c) listing gaps (the DST hour) followed by staggered resumption.
  4. In `evaluate()`, report the mode per block and the per-wallet metrics conditional on it, so that the examiner's
     per-wallet split sees the same thing.
- **Data.** On disk: `act15_*`, `dm_clob_raw`, BUILD activity, calldata via publicnode for the 11-01 07-12 trades.
- **Signature if true.**
  - Mode is stable within blocks and changes at discrete times shared by instances.
  - Within one instance and one |F − mid| band, the quote side replicates across the two blocks.
  - Per-wallet switch-offs sit at a common per-wallet loss or at fixed discovery times.
- **If false.** If bosona's band-conditional accuracy also drops on 11-01, the regime or rule change is real. It is
  then measured without the instance confound.

### P3. Read the full ladder at each publish pass and test the fair cap on the main 500 ladder (strong form of X30, X80 and X136 step 2; the fair cap of X135 applied to the main ladder)

- **Hypothesis.** At each pass the engine sets, for each outcome s:
  - q_s = min(touch_s(+0.01), floor_tick(F_s − h(τ, z))), with F from the latest published report;
  - the lower rungs at fixed tick offsets below q_s.
  The posture is visible only when the cap stops binding on one side (|F − mid| ≳ h). That gives the dead-zone
  accuracy profile of iteration 15: 0.59 at |F − mid| < 0.02, 0.94 at ≥ 0.2. In the dead zone both sides rest below
  the touch, and at-touch posts come from another process (replenishment singles).
- **Why it fits.**
  - The top-rung pair sum has median 0.88 (X30), which is ≤ 1 − 2h by construction under a cap.
  - Class (ii) rungs rest 2 c below the touch.
  - Accuracy rises steeply with |F − mid|.
  - At-touch posts per hour fall 2-3× in the clean block. This is confounded with P2: one instance instead of three
    would give the same drop, so P2 must be run first.
  - The non-BTC opening joins the market on the outcome whose fair is ≥ 0.05 above it (check 4).
  - X63 and X80 fitted a symmetric centre ± half-spread, and X136 used the block clock. None of them tested the
    asymmetric min() structure.
- **Test.**
  - From `dm_clob_raw` and B2's re-sign rule, take the snapshot of pure 500 re-adds in (p, p + 150 ms] after each
    publish p, on both outcomes and at all depths. Since 71% of re-signs keep the price, each pass reveals most of the
    ladder.
  - Per (pass, outcome), regress the top rung's price change on ΔF and Δtouch, split by whether F_s − h ≥ touch_s.
  - Score the within-tick share of min(touch, floor(F − h)) for h as one constant, h(τ), and h(φ(z)/√τ). Fit on 10-31
    14-16 and test on 16-18 and on 11-01 (bosona).
  - Also score the prediction that no at-touch 500 exists on either side when |F − mid| < h − spread/2.
- **Data.** `dm_clob_raw`, `dy_rtds`, `dx_bnf`, Gamma strikes.
- **Signature if true.**
  - When capped, the far-side top rung moves about 1:1 with F and about 0 with the touch. When uncapped, the near side
    moves about 1:1 with the touch and about 0 with F.
  - Within one tick ≥ 0.7 on the far side.
  - The at-touch state 1[F_s − touch_s ≥ h] ≥ 0.85 per (pass, outcome) on both blocks with one h-law.
  - This would give R8 a structural price and side law for both outcomes, and P1 its P(live).
- **If false.** If the far side follows the mid (slope on the touch about 1) rather than F, the ladder is mid-pegged
  with a skew (X63). The 0.2 skew is then the whole reference effect, and the side ceiling in the clean regime is
  measured by the dead-zone fraction.

### P4. The non-BTC module as a quote on its own recorded books: configured-size labels, the opening quote, and touch-pegged later bids (strong form of the iteration-14 mechanics P1 step 3, which iteration 15 ran only for sizes)

- **Hypothesis.** The exam's idle weekend half is carried by one quoting process per family:
  - **At the window open:** a configured-size bid on the outcome whose Binance-digital fair (0.7 × sigma300) exceeds the
    market, posted at the market price.
  - **Later:** configured-size bids on both outcomes, pegged to the last print or the touch.
  With labels from the distinctive sizes, both parts are scorable as quotes, and the open is where activity baselines
  are weakest.
- **Why it fits.**
  - The opening posture scores 0.87-0.92 on three folds, within 0.03 per wallet.
  - Check 4: the opening price is at the market and the later price is at last print − 0.01 (0.52-0.62 on hourly).
  - The sizes are identical in the three wallets.
  - Iteration 15's later fills are two-sided (0.44-0.50 on the opening fill's outcome).
- **Test.**
  - On `dw_clob` and `clob_crypto` for 11-01 06-12 and later development blocks, take the exact configured-size adds
    per family: ETH 5m 50/150, SOL 5m 50/100, XRP 5m 10/50, BNB/DOGE 5m 10/40, ETH/SOL 15m 30, 4h 400.
  - Measure purity from all-match calldata of one 20-minute slice per family. Some of these sizes, such as 400 or
    30, may be shared with other makers.
  - Score:
    - (a) the side of opening posts against the public posture (k 0.7, last print ≤ T − 2), the market favourite and
      in the money;
    - (b) presence of a configured-size order at the touch per (window, outcome, 1 s) in the first 60 s, against an
      activity model of the same class;
    - (c) later posts' price relative to the touch and the last print, and whether later posts are re-sided on that
      symbol's Chainlink publishes (rtds eth/sol, `dv_rtds` xrp/bnb) as BTC's are;
    - (d) the resting life of the opening bid (held to fill, or cancelled on publishes).
- **Data.** `dw_clob`, `clob_crypto`, rtds and `dv_rtds`, Binance 1-s klines, calldata.
- **Signature if true.**
  - Opening configured-size posts follow the public posture ≥ 0.85, with purity ≥ 0.85.
  - Presence at the open gains ≥ 0.05 over activity.
  - Later posts sit at the touch in ≥ 0.8.
  - The weekend half of R9 then gets a quote-level side and price for about 13% of its fills (the open) and a
    touch-pegged price law for the rest. The later side remains the takers' choice, and that should be stated
    explicitly as a valid description.
- **If false.** If purity is below 0.6, the family sizes are shared by other makers, and the module stays a fill-level
  description.

### P5. The replace-all re-sign and its queue law: the cluster's queue resets at every pass (new mechanical hypothesis; the fill half of P1 and the fill model X171 needs)

- **Hypothesis.** The engine re-signs every rung at every publish pass, at the same price for most (B2: 71% keep the
  price; median life 0.69 s, about the publish interval of 1.05-1.2 s).
  - Each re-sign sends the order to the back of its level.
  - The queue ahead of the cluster at a print is therefore the level's size at the last pass, minus prints at the level
    since then. It is not the queue since the first post.
  - This is why fills come from "fresh" orders (age 0.68 s against a length-biased null of 11.2 s), why the cluster is
    first at its level in only 31% of matches, and why the taker's size selects its fills (X176).
- **Why it fits.**
  - Iteration 15's mo-money finding: its rungs carry the posture of 1 s earlier. That is one pass, which fits a
    per-pass re-sign that runs late.
  - The "fresh post" facts of X33 are otherwise unexplained by any trigger.
- **Test.**
  - On 10-31 14-18, for each pure 500 order removed and re-added at the same price within 100 ms, check that its book
    position resets. The level size seen by later adds includes it: a same-price re-add appears behind every add made
    at that level since the original add.
  - For each cluster fill, compare the shares ahead in its matchOrders makerOrders array with three predictions:
    - (i) the level size at the last pass before the match, minus prints;
    - (ii) the level size at its original (first) add, minus prints;
    - (iii) zero.
  - Then estimate P(fill | print size, predicted queue ahead) on 10-31 and apply it frozen to 11-01.
- **Data.** `dm_clob_raw`, `dy_rtds` passes, the all-match calldata (makerOrders order is price-time priority; the
  RE's iteration-3 check found 71% of same-price neighbours in signing order).
- **Signature if true.**
  - Prediction (i) explains the shares ahead within ±100 for ≥ 70% of fills, against (ii) ≤ 40%.
  - The fill law transfers across blocks (calibration slope 0.8-1.2).
  - P1's queue term and X171's FIFO replay then use the last-pass queue.
  - It also changes the outcome account: the cluster pays queue priority for being re-sided every pass. Locked pairs
    then need takers large enough to reach the back, which a replay with the recorded queue can reproduce.
- **If false.** If (ii) wins, re-signs keep priority. The CLOB then treats a same-price re-sign as an amendment, which
  is worth knowing in itself. The fresh-post facts would then need a trigger explanation.

## Notes for the RE

- **Hygiene and clock:** every number here comes from development blocks and BUILD.
- **Correct the strategy statement.** Replace "One engine ... posts each decision in all three" with "on 10-31; on
  11-01 07-08 the main ladder ran in bosona only and almach and mo-money ran only deep bids". The 11-01 quote-side
  failure should carry that caveat before it is called a regime effect.
- **The rebuilt quote unit's `sd`** is the Up book side (1 = Up bid). Any script that read `sd == 0` as Up flipped its
  outcome mapping. I did that myself at first. Worth a grep.
- **Per-wallet replication on the next exam:** if a sealed block repeats the 11-01 mode, almach and mo-money may have
  fewer than 300 fills. Their metrics then come from the deep-bid branch (R8's decided branch, the cheaper token). It
  is cheap to report that branch's accuracy per wallet now.
- **The fill-presence primary metric** stays pre-registered, but its ~0.80 oracle ceiling should be stated next to it in
  `target_metrics`, so that the budget goes to P1's unit.
