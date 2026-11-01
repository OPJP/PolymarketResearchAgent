# Panel after iteration 13: mechanics and on-chain forensics

Lens: how the cluster's orders are built and how long they live, with the order as the unit and wallet attribution from
calldata. The main point of this report: the two fill classes of iteration 13 are probably not "the engine's decision"
and "the takers' choice". They look like one mechanism seen from two sides. The engine's quote under-reacts to the fast
reference. On the outcome that just fell, the market comes to the cluster's quote, so the post lands at or above the
touch (class i). On the outcome that just rose, the market leaves the quote behind (class ii). If that is right, the
class-(ii) side is a public function of the move before the post, and the "27% at chance" account is premature.
Written 2026-11-01, 04:55-05:35 UTC.

**Data I used.** Development data only:
- the RE's extracts of the development block 10-31 14-18: `it13/fills_posts.parquet`, `sched_adds.parquet`,
  `trades.parquet`, `tracer_events.parquet`;
- the live calldata `calldata/live1031_*`, `liveall1031_*`;
- `dm_clob_raw` and `dm_bnf` for 10-31 15-18, read through `live.iter_live`. Both 14:00 files stop at a corrupt gzip
  block;
- `live_activity_17934*` (data-api, the same block);
- STUDY calldata `b1_takers_study`, `b1_all_makers_study`.

I did not open `.cache/live/sealed/` or any sealed block, and I did not look at VALIDATE case by case. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it13m\`:
`remainder_trail.py`, `burst_posture.py`, `sweep_pickoff.py`. Run them from the repo root, e.g.
`.venv/Scripts/python.exe <path>/remainder_trail.py 1793458800 1793469600`. Each one peaks below 300 MB.

## What my checks found

1. **The engine cancels a partially filled rung and never re-posts the remainder (a new mechanic; it contradicts
   C8's "remainders re-signed" and the iteration-5 note).**
   - Of the 619 cluster maker BUY orders in the 10-31 live calldata, 78.7% end partially filled.
   - The 321 partially filled schedule-size orders whose last fill falls in 15:00-18:00 were checked against the full
     book:
     - An exact-size add of the remainder appears in the 120 s after the last fill for only 2.8% of them. A placebo
       size (remainder + 0.37) matches 0.0%.
     - An exact-size remove of the remainder is found for 44.5%, a median 165 ms after the last fill (q25 28 ms,
       q75 0.62 s, q90 1.43 s). The other cases are most likely merged into other deltas at the same level.
   - So every cluster order serves one taker batch (on average 3.2 fills, mostly in one block second), and then it is
     cancelled. The decision unit is the order, and the per-fill metrics weight each decision by the size of its taker
     batch.
2. **A historical post clock from the salt counter is a dead end at the lot's anchor density. Do not re-run it.**
   - Basic facts: the salt is monotone in post time for 94-96% of orders (50-ms tolerance), and the signing rate is
     about 15 orders/s per wallet.
   - Interpolating a filled order's post time from its neighbours' post times (leave-one-out) misses by a median
     2.4-3.2 s (p90 21-41 s). The cause is that the same wallet's filled orders are a median 43-56 s apart in salt-time.
   - The "salt lag" (the order's salt against the largest salt of the same wallet's fills within ±1-2 s) correlates
     with the true age at only Spearman 0.21-0.30. It covers 11-21% of orders and separates class (ii) at AUC
     0.55-0.58.
3. **Triplet posts carry the posture; single-wallet posts carry the per-wallet deficit.**
   - Burst size here is the number of same-size schedule adds at the post's price within ±25 ms.
   - Posture at the post (stamp lag 1.0 s), per fill:

     | burst | fills | posture | class (i) | class (ii) |
     | --- | --- | --- | --- | --- |
     | singles | 830 | 0.751 | 0.859 | 0.477 |
     | pairs | 237 | 0.785 | 0.917 | 0.357 |
     | triplets | 145 | 0.876 | 0.935 | 0.703 |

   - Per order the posture is 0.742 / 0.821 / 0.795 (252 / 78 / 44 orders).
   - Per wallet, singles against triplets: mo-money **0.666** (299 fills) vs 0.793; almach 0.789 vs 0.959; bosona
     0.807 vs 0.895.
   - Singles are not replenishments after an own fill: only 9.1% follow an own fill on the same token within 1.5 s.
   - They are not inventory rungs either. Excluding orders posted while the wallet was flat, 38% of all orders sit on
     its under-held outcome; for class (ii) it is 42%. The posture of orders on the under-held outcome is 0.65, against
     0.82 on the held one.
4. **The Binance futures move before the post separates the two classes, with opposite signs.**
   - When the USD-M bookTicker mid moved in the 1 s before the post:
     - class (i) posts were on the outcome that **fell** (0.949, n 98; at the fill time 0.941, n 119);
     - class (ii) posts were on the outcome that **rose** (0.729, n 48; 0.83-0.85 for moves of at least $0.5-2,
       n 33-36).
   - With 2 s windows the numbers are 0.93 and 0.70-0.77.
   - Coverage is small: the 14:00 hour is unreadable, the block was a quiet Saturday, and a move within 1 s precedes
     only ~10-20% of fills. The rule is also measured on filled orders only.
   - Still, it is the first input that orders class (ii) at all, and on class (i) it beats the posture at the post
     (0.81).
5. **The cluster's marketable orders are ladder rungs that crossed, not a separate taker module.**
   - STUDY calldata has 219 cluster taker orders. 94% match by mint. Their sizes are mostly schedule sizes (62: 68,
     500: 24, 12: 10, 250: 7), so X18's "taker buys" are mostly rungs that crossed.
   - 46% fill at their limit. The rest have the limit above the fill price: median 1 c, q90 5 c, q95 15 c, max 39 c.
   - Whether the large gaps are the engine's raw quote or the book moving while the order was in flight cannot be told
     without the pre-post book. That needs a full-depth block, which is P1 step 2.

## Critique

1. **"Class (ii) is the takers' choice" was concluded from the posture alone.**
   - The posture at the post is a level: the Chainlink fair minus the mid. Class (ii) is defined by where the post
     landed relative to the touch.
   - Check 4 suggests a single mechanism behind both classes. The engine's quote moves less than the market after a
     fast move, so:
     - its post lands at or above the touch on the outcome that fell;
     - its post is left below the touch on the outcome that rose.
   - In such moments the posture is right for class (i) and wrong for class (ii) by construction. The class-(ii)
     "chance" result is then a mixture, not randomness.
   - The panel's own placement result fits this: mo-money's anti-posture resting 500s (41%) are "placed, not stale".
2. **The order life-cycle in the replays and in the fingerprint is wrong.**
   - Rungs are killed about 0.2 s after their first fill and never re-posted at the remainder size (check 1). C8's
     "remainders re-signed" is from a 40-min window of 10-31 and does not hold on 15-18.
   - The strict replays let each second's quote collect up to Q on trade-through volume. The cluster's order instead
     collects one taker batch at the touch and is then replaced at the back of the queue.
   - The outcome gap is described as "queue position and sub-second re-pricing" without modelling this.
3. **The selection component (confidence 0.45) still rests on a calendar gate (AUC 0.68).**
   - The loss controller was tested only weakly:
     - BTC 5m UTC-day PnL on 5-6 events (X58), with no fixed threshold;
     - trailing per-window markouts scored as an AUC over all windows (X25), which dilutes a rare threshold event.
   - Iteration 13 found that the hours-long switch-offs started in October, as the return fell from 7-9% to under 1%
     per $. That is exactly what a drawdown trip would do, and nobody has tested it as one.
4. **The next exam lot is not the historical lot.**
   - The sealed future blocks already add up to 18 hours (10-31 06-12, 10-31 18-24, 11-01 00-06): weekend and night,
     the off-session ladder, and BTC 5m often off.
   - Every exact-clock fact so far comes from one Saturday afternoon (10-31 14-18, part of it unreadable).
   - The notebook keeps improving lot block-clock numbers, which the examiner will not score next.
5. **The per-wallet replication condition is still unexplained.**
   - The deficit sits in single-wallet posts (check 3), which no component describes.

## Proposals (ranked by the chance they close the gap)

### P1. One lagged-quote law explains both fill classes: the side is where the market crosses an under-reacting quote (strong form of X110, X10 and X132 on the post unit; replaces the "class (ii) = takers' choice" account)

- **Hypothesis.**
  - At each pass the engine prices each outcome as the value at the last Chainlink report plus β times the change of
    the fast reference since then (Binance USD-M), with β below the market's own response γ.
  - After a move, the outcome that fell has the cluster at or above its touch (class i, sold into by continuing
    sellers). The outcome that rose leaves the cluster's rung below the touch (class ii), filled only when the market
    reverts or is swept.
  - The side of both classes is then a public function of the move since the last report and its size relative to the
    quote's lag. The posture is this law's quiet-market limit.
- **Why it fits.**
  - Check 4: 0.95 "fell" for class (i) and 0.73-0.85 "rose" for class (ii).
  - X10: re-posts follow the futures mid within 250 ms (96-97%).
  - The tracer price peaks at a 1.25-s stamp lag to Chainlink.
  - The class-(ii) posture is at chance and mo-money's anti-posture rungs are placed (X91 follow-up).
  - X110's pick-off rule was pooled over both classes, which have opposite signs, and was scored on a derived clock.
- **Test.** Pre-registered split; freeze the rule before reading the later half.
  1. **Quote unit (live).** Data: 10-31 15-18 full-depth, then the 11-01 06-12 block.
     - Unit: every schedule-size post at or above the touch, filled or not, so that fill selection is out of the
       picture.
     - Score the side rules: "outcome that fell over [post − W, post − 50 ms]" for W of 0.5, 1 and 2 s, the posture,
       and the posture in quiet moments combined with the move rule in moving ones.
     - Market-only baselines with the same window: the token's Polymarket mid change, and the token just sold.
  2. **Law (live).** On the tracer re-signs and on the cluster's marketable orders, regress
     price = a + b·F_CL(lag 1.25 s) + c·[F_fut(t) − F_fut(t_report)] + touch terms.
     - It is partial adjustment if 0 < c < γ, with γ the market mid's response to the same increment.
     - For the marketable orders, compare the limit with the ask 150 ms before the post: is the limit the raw quote or
       an in-flight cross?
  3. **Per fill (live and lot).**
     - A public class-(ii) predictor at the decision time: a sweep in progress on that token, and the sign of the
       Polymarket mid move against the futures move.
     - Branch rule: class (i) → fell; class (ii) → rose.
     - On the lot, use the in-block clock with USD-M aggTrades at ms resolution (the X132 data, about 8 daily archives):
       top fills against the same-transaction sweep proxy. STUDY case by case, VALIDATE aggregate only.
- **Data.**
  - On disk: dm_clob_raw and dm_bnf 10-31; dx_bnf; the lot calldata.
  - Still to obtain: the 11-01 06-12 full-depth block (`delayed_rawrec`); the USD-M aggTrades archives for 10-23..30
    (reduce to 100-ms bins at once and delete the zips).
- **Signature if true.**
  - On the live held-out half: class (i) ≥ 0.90 and class (ii) ≥ 0.75 in moving moments.
  - The per-fill public side ≥ 0.80, with the Polymarket-only move baseline ≤ 0.70.
  - The fitted c is positive and below γ, and its residual has no own-state structure.
  - Lot VALIDATE aggregate: the sweep proxy's side under "rose" ≥ 0.70 (it is 0.50 under the posture now).
- **If false.** The move rule holds only on filled orders (the takers' momentum selects the fills) and not on
  unfilled posts. Then class (ii) really is taker-chosen, and the ceiling (0.73 × class-(i) accuracy + 0.27 × 0.5) is a
  measured account.

### P2. Selection is a drawdown trip with a manual re-enable, not a calendar (strong form of X58, X70 and X25; the selection component and the exam scope)

- **Hypothesis.**
  - The hours-long October switch-offs are in-process trips of a drawdown limit on a PnL measure nobody has tried:
    the cluster's (or a wallet's) equity across all crypto markets, marked at the last clean print, since the 01:00 UTC
    restart or the last re-enable, measured as drawdown from the running peak.
  - The re-enables are manual operator restarts.
  - A trip in a US evening stays off until the operator's morning. That produces the "Friday-Sunday ET evening to next
    morning" pattern without any calendar rule.
  - Trips multiplied in October because the return fell.
- **Why it fits.**
  - The 10-31 16:53 switch happened inside the running processes, with counters continuous and the signing rate
    unchanged. Two engines were restarted 12-13 min later (X82).
  - Four of six switch-offs come at a new daily low; the live one came $3.06k below the 15:40 peak (X58).
  - The returns look manual: 13:33 and 15:25 UTC are 09:33 and 11:25 ET.
  - In September the module ran in 91% of windows while earning 7-9% per $ (X140).
  - The BTC 5m-only, UTC-day, held-to-resolution measure has no fixed threshold (−$0.9k to −$4.6k). That points to the
    wrong measure, not to no controller.
- **Test.**
  1. **Events.** From the whole-history activity (code12 fetch; development periods only, the lot's STUDY case by
     case, VALIDATE as counts only), list every module off-run of at least 60 min (BTC 5m and BTC 15m separately)
     while the market traded (public tape volume), and every re-enable.
  2. **Measures.** Pre-register 8 PnL measures before computing any: {cluster, per wallet} × {since the 01:00
     restart, since the last re-enable} × {drawdown from the running peak, level}. All crypto markets, marked to the
     last clean print every 10 s; realized-at-resolution as a variant.
  3. **Fit and score.**
     - Choose the threshold D on BUILD (10-08..22).
     - Report on STUDY and VALIDATE: the hazard ratio of a switch-off after the first crossing of D, recall of
       switch-offs within 10 min, and the false-trip rate.
  4. **Re-enables.** Look for a salt-counter reset within ±2 min (lot calldata) and the ET hour of the day.
  5. **Competing public breakers, same event design.** 300-s realized vol, the Chainlink-Binance gap, Chainlink 1-s
     noise, Polymarket message rate.
- **Data.**
  - On disk: whole-history activity; lot calldata salts; tapes for marking.
  - Still to obtain: window outcomes from Gamma for the traded windows, or the Binance proxy.
- **Signature if true.**
  - One measure has a stable threshold at the switch-offs (CV ≤ 0.25 over ≥ 8 events).
  - At least 80% of switch-offs come within 10 min of its first crossing, and at most 20% of crossings have no
    switch-off.
  - At least 70% of re-enables are at counter resets.
- **What it would give.**
  - Selection becomes a decoded rule on own state. It is reported, not counted toward presence.
  - The exam's universe rule can then say which modules are on: BTC 15m and the other families carry the weekend
    blocks.
  - If a public breaker wins instead, selection becomes a public, counted rule.

### P3. Triplet passes are the public decision; single-wallet posts are each wallet's residual (new; per-wallet replication and the quote-unit labels; strong form of X36, X94 and X98)

- **Hypothesis.**
  - When the three engines post the same price within 25 ms, they acted on the shared public inputs: posture 0.876 per
    fill, 0.935 on class (i).
  - A single post is one wallet's own decision: its own scheduler slot, latency or book state. That is where mo-money's
    deficit sits (0.666 against 0.793 on triplets).
  - The quote unit's public ceiling should then be measured on passes, not on a pooled cluster-class label.
- **Why it fits.**
  - Check 3.
  - Singles are 68% of schedule fills and are neither replenishments (9%) nor inventory rungs (38-42% on the
    under-held outcome).
  - Mo-money has the most singles.
  - X36: about 12% of exact-500s are other makers' orders. Triplets are clean of them by construction.
- **Test.**
  - Data: 10-31 15-18 and 11-01 06-12.
  - Label every schedule-size add burst by multiplicity (1, 2 or 3 same-size adds at one price within 25 ms).
  - Score the quote unit and the side from public inputs (with P1's move rule) on triplet passes and on singles
    separately.
  - For filled singles, attribute the wallet from calldata and test:
    - whether the other two wallets' identical rung was still resting (the single is a re-post of a rung the others
      kept);
    - the wallet's salt gap since its previous post (scheduler phase);
    - the wallet's own imbalance.
  - Report each wallet's single share and single posture, and the part of mo-money's deficit they carry.
- **Data.** On disk: dm_clob_raw 10-31, sched_adds, live calldata. Still to obtain: the 11-01 06-12 full-depth block.
- **Signature if true.**
  - Triplet passes are decoded at ≥ 0.85 on the quote unit and ≥ 0.90 on the side.
  - Singles are explained by the wallet's own scheduler or book state.
  - Mo-money's single share and single posture account for ≥ 70% of its 3-point-plus deficit.
- **Reporting rule.** This is a decomposition, not a scope cut. The counted metric stays the one over all posts and
  fills.

### P4. The order life-cycle: one taker batch per order, then cancel. Rebuild the fill unit and the replay on it (new mechanic; strong form of B2 and X54's remainder trail, and of the X106/X124/X137 fill model)

- **Hypothesis.**
  - Each cluster order lives about 1 s at the touch. It collects one taker batch, and the engine cancels the remainder
    about 165 ms after the last fill.
  - The rung is then re-posted at full size at the next pass, at the back of the queue.
  - The cluster's window PnL is therefore made of first batches at the touch. A replay quote that keeps filling on
    trade-through volume buys the adverse tail the cluster cancels away.
- **Why it fits.**
  - Check 1.
  - Iteration 13: 73% of fills are fresh posts 0.86 s old, and the strict replay loses 11-16% while its locked pairs
    turn positive only at the tracer depth.
- **Test.**
  1. **Confirm the cycle.** On 11-01 06-12 (full depth, off-session 62/250 ladder): for each partial fill, the exact
     remove of the remainder, and the next same-size add on the same outcome within 0.5 s at the same or another price.
     Report the shares of cancel-replace, cancel-only and remainder re-posts, per size class.
  2. **Replay variant.** In `code11/replay.py` and `code12/replay_machine.py`: each quote fills at most one taker
     batch (the prints of one block second, or one in-block transaction run), then is withdrawn until the next decision
     second. Keep latency 2 s and slack 2.
     - Score on VALIDATE aggregate: the window correlation, the oracle-side ceiling and the return.
  3. **Per-order reporting.** Report side and price per order (one decision per order) beside the per-fill numbers.
- **Data.** On disk: the replay inputs and calldata. Still to obtain: the 11-01 06-12 recording.
- **Signature if true.**
  - Cancel-replace in ≥ 80% of partial fills.
  - The batch-capped replay's return improves by ≥ 5 points, and its oracle-side window correlation rises above 0.53.
  - Per-order and per-fill side differ by more than 2 points, which is the multiplicity bias in the side metric.
- **If false.** If the replay does not move, the outcome gap is the side and the queue entry time, not the life-cycle,
  and that is then measured.

### P5. The pairing process on persisting imbalance states (strong form of X139)

- **Hypothesis.** X139 found an exact-|Z| pairing bid after only 18.7% of imbalance changes. The reason may be that it
  counted every transient state: fills come in runs of several taker transactions in one block second, so most
  intermediate |Z| values live under one pass. The engine bids the imbalance that survives a pass.
- **Why it fits.**
  - The pairing add comes a median 1.7 s before the activity block stamp (about 0.3 s after the match). That is one
    pass.
  - Same-second fill batches are the norm (check 1; iteration-12 finding 4).
  - The rate is the same in every size bucket and every wallet, which looks like a counting artefact rather than a
    size rule.
- **Test.**
  - Re-run `code13/pairing_process.py`, keeping imbalance states that persist at least 1.5, 3 or 5 s with no further
    change to that wallet's position in the market.
  - Report the found rate against the placebo, the latency, and the add's depth below the own touch, against the
    Chainlink edge of the under-held outcome.
- **Data.** On disk: dm_clob_raw 10-31 and the live activity.
- **Signature if true.** At least 80% of persisting states get an exact-size pairing bid within 2 s. The pairing bid's
  existence is then a deterministic own-state rule, and its price, which is still undecoded, is the only open part of
  the exit.
- **Rank.** Lowest of the five: it fixes a component description, not a target bar. It is cheap (minutes).

## Notes for the RE

- **`dm_bnf` is cut too.** `.cache/live/dev/dm_bnf/20261031T14.jsonl.gz` raises the same zlib "invalid block type" as
  `dm_clob_raw` 14:00, so the 14:00 hour of both own feeds is partial. Wrap readers per hour.
- **Stale facts to correct in C8, the fingerprint and NOTES.**
  - "Remainders re-signed" (iteration 5) does not hold on 10-31 15-18: 2.8% of partial fills, placebo 0%.
  - The partially filled rung is cancelled about 165 ms after its last fill.
- **The futures sign test is on filled orders.** P1 step 1 must use the unfilled posts as well. Otherwise the takers'
  momentum, which decides which posts get filled, is mistaken for the engine's choice.
- **The salt clock (check 2) needs no further work.** Its errors are set by how far apart the anchors are, not by the
  method.
