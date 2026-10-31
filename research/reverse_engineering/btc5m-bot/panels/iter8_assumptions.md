# Panel, iteration 8: assumption breaker

Lens: what the investigation takes for granted that may be false. This round that covers four things: which conditions
actually bind on the lots the rule will face, who XM is now, which decisions the live work scores, and what the PnL
condition measures.

I ran small checks on development data only:

- the BUILD and VALIDATE windows before H (`fills.parquet`, `orders.parquet`, `b1_orders_sample.parquet`,
  `val_side_*`);
- the 10-31 development blocks 00-06 and 12-18 (`post/own_*.parquet` on-chain fills, `post/cd*.parquet` calldata of
  12:00-14:47).

Nothing sealed was read, listed or counted, and `.cache/live/sealed/` was not opened. Scripts are in the session
scratchpad. Roles are classified as in `build_fills.py` / `final_rule.py`: T if the counterparty is a V2 exchange,
else M.

## Critique

1. **XM on 10-31 is not the XM of VALIDATE, and the live work has not noticed.**
   - **Role.** XM's maker share of fills was 41% (BUILD) and 44% (VALIDATE). On the 10-31 development blocks it is
     **91%** (4,454 of 4,905 fills). Pure-maker orders (never a taker fill) were 23% of XM's orders on VALIDATE
     weekdays and 28% on weekends. On 10-31 they are **76%** (00-06) and **85%** (12-18).
   - **Size.** On 10-31 12:00-14:47 (calldata), 86% of XM's 181 pure-maker orders are **60-share** orders. XM's taker
     orders are 30 / 100 (51 / 49%), and **no 60-share order ever took liquidity**. In BUILD and VALIDATE no wallet-day
     has a role-specific size: maker and taker orders share each day's mix.
   - **Same factory.** The 60-share orders come from the same order factory: signed in the same three bursts, with
     signatureType 3, 317-byte signatures and 1-cent limits.
   - **Interpretation.** XM now runs a passive (post-only-like) component with its own size class. The "30 / 60 / 100
     menu of 10-31" in FINAL_RULE is two taker sizes plus XM's maker size.
   - **Other wallets.** DS and GF also have more pure-maker orders (28-37% vs 13-23%), but with the same 30 / 100 mix
     as their taker orders, which looks like lost races.
   - **Activity.** XM's activity moved three times:
     - 19-20k fills a day on 10-09..13;
     - 1.6-3.0k on 10-14..22;
     - a ~9.8k-a-day pace on 10-31, with a median of 29 fills per window against 7 on VALIDATE.
   - **What the live work covered.** Every live XM analysis (vote 7 of 9, pay-up 38-46%, large share 46%) describes
     the 9% of XM's fills that are taker matches.
2. **XM's side condition is a counting artifact.** The investigation treats the side condition as binding through XM
   (one-sided in 24.3% of VALIDATE windows).
   - **Count null.** A null that keeps XM's order count per window and draws each side from the pooled cluster's Up
     share in that window gives **26.0%**. GF is 3.1% against a null of 3.7%, and DS 0.2% against 0.7%. XM does not
     choose a side per window. It is sparse after 10-13, and its one-sided share tracks its activity: 0-5% before
     10-13, 17-35% on 10-15..22.
   - **On 10-31.** XM is one-sided in 3.7% of 134 windows, GF in 6.7% and DS in 0.7%. On a 10-31-like lot no wallet
     reaches the 20% bar.
   - **Consequence.** The weak-vote side work, iterations 7-8's main thread, may target a condition that will not bind
     on the future-block exams. Meanwhile the conditions that will bind are not covered for half of the fills:
     presence, price within a tick, PnL, and per-wallet replication.
3. **The live decision population is censored to race winners.** The scored decisions differ by component:

   | component | what it scores | what that misses |
   |---|---|---|
   | side, hazard, refractory, kernels, pay-up, decision overlap | taker matches only | |
   | `_live_vote` / `side.decision_units` | `role == "T"` | |
   | price 95.1% | taker orders vs the calldata touch | maker fills: only the tape anchor (44-53%) |

   - **Share of maker orders.** On 10-31, pure-maker orders are 38-50% of the cluster's orders per hour, and maker
     fills are 49-65% of its filled shares.
   - **Effect on the hazard.** Its positives are wins, so a submission that lost the race after a strong tick is
     scored as a negative.
   - **Effect on the gate.** Finding 5 may be partly a race-outcome filter. "Hazard doubles when o's ask falls" is
     what selection would produce: an order at the ask it saw still crosses a falling ask and rests below a rising
     one.
   - **Why nobody tried it.** X15 ruled out attributing unfilled submissions. But maker-first orders that do fill are
     attributable: the chain gives their exact token, price, size and wallet, and subs6 already found the insertion
     for 81% of resting cluster orders. Nobody has used those insertions as decision instants.
4. **The PnL condition measures a sign that public data barely predicts.**
   - **What drives per-window PnL.** It correlates 0.63-0.69 per wallet (0.69 pooled, VALIDATE) with
     sign(final unpaired net) x outcome.
   - **How early the sign is fixed.** It agrees with the net at rel 30 s in 64%, at 60 s in 69% and at 120 s in 81%.
   - **Agreement with public directions:**
     - the BTC move from the open to +5..60 s: <= 50%;
     - the underdog at T = 60-270 s: 48-52%;
     - the underdog at the open (spot vs the 60-s TWAP strike): 57% (61% when |S0 - K| > 2 bp).

     Lean proxies built from these correlate <= 0.13 with the per-window PnL.
   - **Reliability.** Siblings from the same process correlate 0.00-0.20 per window, and the split-half correlation
     within a wallet is -0.03 to 0.16. That is the test-retest level of the target, and the replica's 0.18 already
     sits on it.
   - **What is missing.** X17's resampling ceiling was never computed, so FINAL_RULE says "bound by decision overlap"
     where the stronger claim may be "unattainable by the true rule".
5. **The presence pass is against a soft baseline.**
   - **Block-second unit.** The gain is +0.055 over a "pure" baseline (`MKT_PURE`: rel, tau, the tape state and
     flows, dm5 / dm10 / dm30). That baseline has no 1-2-s Polymarket price change, no complementary-outcome tape
     state, no counts of bot-size prints by others, no self-exciting intensity of other takers, and W4 is still
     counted as "other traders" (X5 open).
   - **Live hazard.** Its +0.058 is against trades, touch changes, touch age and price only.
   - **Why it matters.** The examiner fits its own baseline. Both gains sit within 0.01 of the 0.05 bar.
6. **The size is a sticky per-(window, outcome) mode more than a function of the running net.**
   - **Mode beats net.** The leave-one-out large share inside the same (wallet, window, burst, token) predicts the
     large size with AUC DS 0.80, GF 0.76 and XM 0.74. The operator net gives 0.58 / 0.75 / 0.67.
   - **Large follows large on the same token.** P(large | a large order already used on the same token in the
     window) is 0.20 / 0.42 / 0.17. When the earlier large order was on the other token only, it is 0.04 / 0.13 /
     0.06.
   - **Timing.** The first large order of a window comes at a median rel of 26 s (DS), 12 s (GF) and 36 s (XM).

   This is own state either way and does not change the PnL conclusion, but "large when flat or adding" is a proxy for
   it.

**Checked and not supported** (so nobody redoes them):

- **Pool depletion of the pre-signed ladder as the size or pay-up mechanism.** P(large) falls with the rank of use at
  a level: DS 0.14 -> 0.07 -> 0.05. Up to 4 large copies of one level are used per burst.
- **Remainders blocking a wallet.** The gap to the wallet's next taker match is the same after a remainder as after
  a full fill: DS median 2.7 vs 2.4 s, < 1 s 24% vs 26%.
- **Chasing a remainder on the same side.** The same side within 0.3-2 s is 59% after a remainder and 74% after a
  full fill.
- **Pair completion as the quiet-second side.** On VALIDATE no-move one-sided seconds the short-leg rule scores 51%,
  and 59% when the pair cost is below 0.96, against 66% for psb.
- **Martingale sizing after a losing window.** Spearman of the large share against the previous window's PnL is
  -0.21..+0.21, with no consistent sign.

## Proposals (ranked by the chance of closing the gap)

### 1. XM changed role: decode its passive 60-share component, and re-derive which conditions bind on future lots (new; strong form of X9 / X26 / X57)

- **Hypothesis.** Between 10-22 and 10-31 the operator reconfigured XM into a passive wallet. XM posts dedicated
  60-share pre-signed BUY orders as resting quotes (post-only or priced below the ask), plus a few 30 / 100 taker
  legs.
  - A plausible motive: the large taker overlay lost 1.1-1.9 c per share after fees on VALIDATE. Moved to resting
    orders, it pays no taker fee and earns maker rebates.
  - On a 10-31-like lot:
    - no wallet is one-sided in 20% of its windows, so the side condition does not apply;
    - XM's per-wallet presence, price, PnL and replication (condition 7) are dominated by a component the frozen rule
      does not model.
- **Evidence.** Critique 1-2:
  - XM's maker share is 91% of fills on 10-31 against 41-44% before, and 76-85% of its orders are pure-maker;
  - 86% of XM's pure-maker orders are 60 shares, and 0 of them took liquidity;
  - no role-specific size exists anywhere in BUILD or VALIDATE;
  - XM's one-sided share on VALIDATE (24.3%) equals the order-count null (26.0%) and is 3.7% on 10-31.
- **Test.**
  1. **Census.**
     - Per wallet and hour on every development block (10-31 00-06 / 12-18, 11-01 06-12, then weekdays), and per day
       over the whole pre-H history (chain logs back to July):
       - fills;
       - pure-maker share by orders and by shares;
       - the size mix by role;
       - the one-sided share against the order-count null;
       - the large share;
       - the slot in the signing loop.
     - Also compare the Gamma listing fields (feeSchedule, rebateRate, makerRebatesFeeShareBps, tick) of the 10-31
       development windows with VALIDATE.
     - The result is a change-point table for the role and size class.
  2. **Insertions.** For each XM 60-share order on the development blocks, find its insertion in btc5m_clob_raw2 /
     btc5m_xclob: the touch side at the order's price, a size increase of exactly 60 (or the unfilled remainder), in
     [first fill - 136 s, first fill]. Record:
     - the bid and ask seen 50-150 ms before;
     - limit - bid and ask - limit;
     - the ten-series vote at insertion;
     - the resting time and the removal time (size decrease without a trade);
     - requotes (a new 60 at the new touch after removal);
     - queue position;
     - counterparties.
  3. **Rules to compare.** Fit and compare quote rules on one interval and score them on the next:
     - join the best bid;
     - bid + 1 c;
     - FV_DVOL - margin;
     - lean side by operator net;
     - "taker legs routed late".
  4. **Economics.** Compute the per-share PnL after maker rebates of XM's 60-share fills, with outcomes of the
     development windows only.
  5. **Exam path.**
     - Run `evaluate` on the 10-31 development blocks per wallet and report every condition with XM's maker fills in
       scope: presence, price on all fills, side applicability with the count null, PnL.
     - Pre-register an XM maker component in `final_rule.py` before scoring 11-01 06-12.
- **Data.**
  - `post/own_*.parquet` and calldata of development blocks;
  - btc5m_clob_raw2 / btc5m_xclob / btc5m_xven via `iter_live`;
  - pre-H chain logs per wallet (topic2 / topic3);
  - Gamma listing projection.
- **Signature if true.**
  - 60-share XM orders are inserted at or below the best bid, or at least 1 c under the ask seen, and are not
    tick-locked: the excess over placebo of a venue tick in the 250-350 ms before insertion is under 0.03.
  - They rest for seconds with requotes and have a fitted quote rule within 1 c in >= 80% of cases.
  - The change appears as a single dated step in the census.
- **Signature if false.**
  - The orders are inserted at the ask seen, 250-350 ms after ticks, with vote agreement >= 85%. Then they are XM taker
    attempts that systematically arrive late (the slot or the network path) and belong to proposal 2.
  - Either way, the side condition's applicability must be re-derived per lot from the count null, not assumed from
    VALIDATE.

### 2. Score the decisions that lost the race: book insertions of filled maker-first orders as decision instants (strong form of X15; re-test of the gate, X36 and the live side)

- **Hypothesis.** A large share of the bot's decisions lose the race. On 10-31, DS and GF pure-maker orders are 28-37%
  of their orders, with the same size mix as their taker orders. These orders were submitted at the ask the bot saw,
  after the same triggers, and rested because the ask moved first.
  - Lost races should be strong-trigger decisions, because strong ticks draw competitors.
  - Counting them as decisions should do three things:
    - raise the decision-level side and the full-coverage share;
    - raise the hazard's recall (8.2% at matched volume);
    - shrink the "falling ask doubles the hazard" gate, which would be partly a race-outcome filter.
- **Evidence.** Critique 3:
  - every live decision metric uses `role == "T"`, while maker fills are 49-65% of filled shares on 10-31;
  - the gate result has exactly the shape selection would produce;
  - subs6 found an insertion for 81% of resting cluster orders, so attribution is feasible for orders that fill;
  - the iteration-1 lost-race test (68.6% vs 7.4% placebo) was on VALIDATE, where maker orders were 13-23%.
- **Test.**
  1. **Insertions.** On the development intervals already used (14:14-17:55, then 11-01 06-12), take every cluster
     order with a maker fill and no taker fill before it, from on-chain fills and calldata. Locate its insertion in
     the unthrottled book as in proposal 1.
  2. **Price.** Record limit vs the ask seen 50-150 ms before insertion. A lost race has limit = ask seen. A passive
     quote has limit < ask.
  3. **Side.** Score the frozen `_live_vote` and the ten-series vote at the insertion instant. Report won-race and
     lost-race decisions separately, by vote strength, and pooled into one decision population.
  4. **Hazard and gate.**
     - Re-run gate8 with positives = matches ∪ insertions.
     - Refit the frozen hazard design on one interval, score it on the next, and compare with the matches-only
       hazard.
     - Re-run overlap8 at matched volume.
  5. **Price on all fills.** Price maker fills as "limit = ask seen at insertion" and report price within a tick over
     all fills.
  6. **Historical analogue (block clock).** Price maker-first orders as the ask just before the last other-taker print
     on o at the order's price in the 5 s before its first fill. That gives a point-in-time price for h1 / h2.
- **Data.** On-chain fills and calldata of the development intervals; btc5m_clob_raw2 / btc5m_xclob, btc5m_venues2 /
  btc5m_xven; for the historical part, `fills.parquet` and the VALIDATE tapes.
- **Signature if true.**
  - Lost-race decisions have limit = ask seen in >= 70%.
  - Their insertion follows a tick toward o 250-350 ms earlier at least as often as for won races, with vote
    agreement >= 85% and a lower weak-vote share.
  - The pooled decision-level side rises by >= 2 points.
  - With insertions as positives, P(decision | tick, ask rose) approaches P(decision | tick, ask fell), and the
    hazard AUC and overlap recall rise.
- **Signature if false.** The vote at insertion is near placebo, or the limits sit below the ask seen. Then maker-first
  orders are a separate passive behaviour (proposal 1 for every wallet), and the matches-only gate stands as a real
  decision gate.

### 3. Compute the PnL condition's test-retest ceiling by race-lottery resampling, and report the components (strong form of X17)

- **Hypothesis.** The per-window PnL is the sign of the unpaired net times the outcome. That sign is decided by race
  outcomes and own-state feedback, and public data predicts it at 50-60%. So the true rule replayed twice would not
  reach 0.5 against itself, and condition 5 is unattainable by construction. That is the quantitative account the
  brief requires, in place of "bound by decision overlap".
- **Evidence.** Critique 4:
  - r(PnL, sign(final net) x outcome) = 0.63-0.69;
  - the final-net sign against every public direction: 48-57%, and 61% at most for large open gaps;
  - sibling per-window correlations 0.00-0.20 and split-half -0.03 to 0.16;
  - the replica at 0.18 against oracles of 0.40 (>= 2 s) and 0.68 (same block, the wallet's own decisions).
- **Test.**
  1. **Win model.** On VALIDATE, take the wallet's own decision stream: taker orders, and maker-first orders as lost
     races. Fit P(win, filled fraction | trigger strength at block clock, rel, price, other takers' prints in the
     block, size) on BUILD.
  2. **Replays.** Draw pairs of independent replays: decisions fixed, race outcomes resampled, the size mode from
     critique 6 re-run on each replay's own net. Recompute the per-window PnL of each replay.
  3. **Correlations.** Report r(replay 1, replay 2) and r(replay, actual), Pearson and Spearman, per wallet, pooled and
     by half. Use 2-h block bootstrap intervals.
  4. **Decomposition.** Split each window's PnL into locked-set PnL (pairs x (1 - pair cost) - fees) and the unpaired
     remainder. Report the frozen replica's correlation with each part. The locked part is the replicable one.
- **Data.** `fills.parquet`, the calldata sample (sizes, limits), the VALIDATE tapes, `windows.parquet` outcomes (all
  development).
- **Signature if true.** Replay-replay r < 0.5, plausibly 0.2-0.4, and replay-actual at or below that; the replica's
  0.18 is close to the ceiling on the unpaired part and higher on the locked part. Condition 5 then goes into
  FINAL_RULE as unattainable with that number.
- **Signature if false.** Replay-replay r >= 0.6. Then decision overlap is the real limit, and the work should go to a
  decision-level replay replica (X36).

### 4. Audit the presence gain against an examiner-strength market-only baseline, and remove W4 from both sides (strong form of X4 / X5)

- **Hypothesis.** The examiner's own baseline (same model class and budget, BUILD data) will include market-only
  features the pure baseline lacks. Either the +0.055 block-second gain or the live hazard's +0.058 may then fall
  below 0.05. W4 is the same process (fourth slot in the signing loop). Its prints inflate whichever side uses them, so
  they belong to neither.
- **Evidence.** Critique 5: `MKT_PURE` has no dm1 / dm2, no other-outcome state, no bot-size print counts, no intensity
  terms, and includes W4. The live baseline omits co-racer trades at ms. Both gains are within 0.01 of the bar.
- **Test.**
  1. **Historical (block-second unit).** Add these features to the baseline:
     - dm1 and dm2 (Polymarket implied-price change over 1 and 2 s);
     - the other outcome's ask / bid / flow and the Up + Down implied ask sum;
     - counts of other traders' prints of exactly 30 / 50 / 60 / 100 / 200 shares in the last 1-5 s;
     - exponentially weighted print intensity of other takers at 0.5 / 2 / 10 s;
     - the deterministic window clock terms (time since rel 42 s and 172.7 s).

     Remove W4's prints from every feature of both models. Refit with the same LightGBM budget on BUILD and report on
     VALIDATE the AUC, the gain, its 2-h block-bootstrap CI and the gain per wallet.
  2. **Live (100-ms grid).** Add to the Polymarket-activity baseline:
     - other takers' trades on o and on the other outcome in [t - 600, t);
     - the touch size and age of both outcomes;
     - the cluster-independent crowd count.

     Score the frozen hazard against it on the later interval.
- **Data.** VALIDATE cells (`cells/`), tapes (re-read from the HTTP cache), W4's fills by topic2; live development
  intervals.
- **Signature if true.** The gain stays >= 0.05 with CI > 0 against the strongest baseline, for every wallet. The
  presence claim is then exam-safe.
- **Signature if false.** The gain falls below 0.05. Presence passes only against a weak baseline, and the next
  iteration has to find a unit or input where the gain is larger before any exam round is spent.

### 5. One process, several assets: shared capacity as the reason most high-hazard instants are skipped (new; strong form of C1 / X27)

- **Hypothesis.** The same TypeScript process may also run ETH / SOL 5m (or BTC 15m) windows with other wallets. Its
  bursts and in-flight slots are then shared, which would explain three things:
  - the 92% of high-hazard instants with no BTC match;
  - the synchronized dips before the +172.7 s burst;
  - part of the day-level activity changes.
- **Evidence.**
  - One process signs XM -> DS -> GF -> W4 in ~4 s per burst, and all 5m windows of every asset share the clock.
  - The trigger is necessary but not sufficient (overlap8: 8.2%, lift 2.75).
  - The X32 dip starts ~3 s before the BTC burst and is not staggered by wallet.
  - The C1 census looked only inside BTC 5m transactions.
- **Test.**
  1. **Fingerprint search.** For 4-6 development windows, fetch the calldata of ETH 5m, SOL 5m and BTC 15m matches.
     Look for orders with:
     - signatureType 3, 317-byte signatures, builder = metadata = 0;
     - salt / timestamp uniform on [0, 1];
     - signing ms in bursts at rel -89.5 / +42 / +172.7 s of their own windows.

     Check whether those bursts interleave with the BTC loop (e.g. +4..8 s after W4).
  2. **Capacity test.** If such wallets exist, check whether the BTC hazard (frozen) is lower in the 300 ms after a
     same-process match on another asset or during its signing burst. Compare the BTC dip times with the other asset's
     bursts.
- **Data.** Polygon calldata of a few ETH / SOL / BTC-15m development windows (~1.4k txs per window, decoded fields
  only); chain logs for any wallet found; the live development intervals for the capacity test.
- **Signature if true.**
  - Sibling wallets with the fingerprint exist on other assets, with bursts interleaved in the same loop.
  - The BTC match hazard drops by >= 30% while the process is busy elsewhere.
  - Adding "busy elsewhere" lifts the decision overlap recall.
- **Signature if false.** No fingerprinted wallets outside BTC 5m. The process is BTC-only, and the skipped triggers
  belong to proposal 2 (lost races) or to an unobserved gate.
