# Panel, iteration 7: assumption breaker

Lens: what the investigation takes for granted that may be false. This round that means the unit of decision (order
vs event), the role of the four wallets, what gates the trigger, and which exam the rule will actually face.

I ran small checks on development data only. Nothing sealed was read, listed or counted.

- **Live development block**, 10-31 13:00-14:47 (`live6_takers.parquet`: 782 cluster taker matches with matching-engine
  ms; `post/cd6_live.parquet`: their calldata; `post/own6_all.parquet`: all cluster fills of that block).
- **Calldata sample** (`calldata_sample.parquet`, 11 pre-H hours, 11,407 cluster taker orders). The 30/100 days
  10-19..22 are used where the size class matters.
- **VALIDATE fills** (`fills.parquet`, windows 10-16..23, 142,638 taker orders).

Definitions used below:

- An **event** is a run of cluster taker matches on the same window and outcome, each less than 300 ms after the
  previous one.
- A **leg** is one order in an event.
- A **fast pair** is two legs less than 50 ms apart.
- **Pay-up** is the order's limit minus the best effective ask the same match consumed.

## Critique

1. **The decision unit is a multi-leg event spread over the wallets, not an order.** Every size, pay-up and side
   analysis so far scores orders, or orders per wallet. Two checks show a different structure.
   - **Live (606 events).** Fast pairs are always two different wallets (72 of 72). Their limits are one cent apart:
     +1 c in 51 and -1 c in 12. They are never at the same price (0 of 72). Same-price legs do exist, but they rest:
     in 53 of 606 events another wallet's order at the first leg's price takes a maker fill within 2 blocks.
   - **Historical (calldata 10-19..22, same block and same token).**
     - Pairs of cluster orders in consecutive transactions are cross-wallet in 85% of 119. Same-wallet pairs make up
       15%, against an independence null of 52% (sum of squared wallet shares, DS 0.66, GF 0.28, XM 0.06).
     - The cross-wallet consecutive pairs differ by exactly +-1 c in 79% and share a price in 4%.
     - Over all same-block pairs the same-wallet share is 0.32 (n = 2,247).

   So a decision fires legs at adjacent ladder levels, one leg per wallet, and the legs share the side: legs within
   300 ms have the same outcome in 92-94%.
2. **Pay-up (X42) and the large size (X29) are mostly properties of the multi-leg event.**
   - **Pay-up.** Live, pay-up of 1 c or more is 39% in fast pairs, 10% elsewhere and 8% in single-order events. It is
     11.6% for first legs and 32% for second legs.
   - **Large size.** Historically, cross-wallet same-block pairs at +-1 c contain a large order in 39%, against 14% at
     the same price. Wallet composition confounds this, so it needs the controlled test of proposal 1.
   - The iteration-7 conclusion "the large size is event-level but unpredictable" fitted P(large) per order inside a
     wallet. That is the wrong unit: the unit is the event's intensity (legs, levels, sizes).
3. **"Participation is flat in trigger strength" (X16) does not hold at the leg level.**
   - The fast multi-leg share is 9% when the largest trade move is at most 0.05 bp and 19-20% at 0.2-1 bp.
   - It is 6% in trade-quiet matches and 16% otherwise.
   - The multi-wallet share rises from 13-25% before 240 s to 36% at 240-300 s, the same late-window pattern as
     pay-up.
4. **The wallets behave like concurrency slots, with a per-wallet refractory period.**
   - **Minimum gaps.** Over 521 live matches, DS never has two matches less than 120 ms apart (1st percentile
     201 ms). GF's minimum is 47 ms (n = 222) and XM's 236 ms (n = 39).
   - **Pairs within 300 ms.** There are 15 same-wallet pairs, only 1 of them under 100 ms. There are 195 cross-wallet
     pairs: 85 under 50 ms and 28 under 10 ms.
   - **First leg when DS is busy.** When DS matched in the previous 200 ms, the next event's first leg is DS in 1 of
     6 events. Within 400 ms it is DS in 53% (n = 34), against 82% when DS was idle.
   - **Why it matters.**
     - It is a mechanical reason for running several wallets, an alternative to the tier story of X33.
     - It explains why XM is sparse and one-sided.
     - It makes the wallet assignment a decision component that the per-wallet replication condition will score.
       Condition 7 requires PnL r >= 0.47 for every wallet with at least 300 fills. DS's split-half per-window PnL is
       -0.03, so DS can be matched only by holding DS's own orders, which means knowing which legs go to DS.
   - **Caveat.** The 80/20 "DS first" split is partly selection: a DS leg that lost the race rests and is not in the
     taker list.
5. **The investigation assumes that every microprice tick is an opportunity, and reads the low hazard (2.3% -> 8.7%)
   as "necessary, not sufficient".** It has not asked what gates the decision. A latency taker can only take where a
   stale order still rests. Two signs point that way.
   - **Round prices.** Fill counts on the favourite spike 10-19% at round prices 0.60, 0.65, 0.70, 0.75 and 0.80,
     with no spike at round underdog prices. A favourite ask at 0.80 is a resting underdog bid at 0.20, the classic
     retail lottery order. The edge per share is +2.06 c at round favourite prices and +1.03 c at the others (window
     bootstrap of the difference, 95% CI [-0.3, 2.1]; suggestive, not significant).
   - **Prey maker.** One maker, 0xec10d230, is over-represented in quiet matches (X23).

   The hazard model so far conditions on the tick and on trade activity, never on whether the touch of o has already
   repriced after the tick.
6. **The exam the rule will face is not the one the work is aimed at.**
   - **The first exam runs on h1** (10-23, 10-25, 10-27, 10-29), whatever is claimed. On h1 none of the live
     components can run: `side_live_decision` is None there, the block clock caps side at 72.7% per order, and the
     >= 2 s convention caps PnL at 0.40 even with the wallet's own decisions. The live work pays off at exam round 3 at
     the earliest.
   - **The exam-input recorder covers weekend sealed blocks only.** rec_exam7 stops on 11-02 06:00 UTC, so its sealed
     coverage is 10-31 18-24 (Saturday), 11-01 00-06 and 11-01 12-18 (Sunday). That is the regime where the decoded
     side rule is weakest:
     - weak votes rose from 22% to 42% to 56% of decisions over Saturday's three intervals;
     - agreement fell from 86% to 83% to 75%;
     - large orders were 3.5% of Saturday taker matches, against 8-33% per wallet in VALIDATE.
   - **One sealed block has no recording at all.** 10-31 06-12 is sealed and lost. The next future lot starts after
     10-31 00:00, so it will include 6 h without the live inputs. If the rule has no stated fallback there, scope can
     fall below 80%.
7. **Versions.** 10-31 runs a 30 / 60 / 100 menu, while VALIDATE ended on 30 / 100, so the configuration changed during
   the sealed week. The live-decoded parameters must be checked against VALIDATE before they are used on h1: reaction
   kernel, refractory, legs per event, pay-up rate and burst times (X26 / X9 in their strong form). Some of them
   (legs, pay-up, burst times, large share) can be measured from calldata on both sides of the change.
8. **Checked and not supported** (so nobody redoes them):
   - **Per-window exposure caps** as the source of the underdog tilt. The tails per (wallet, window, outcome) are
     smooth: DS p99 $1,299, p99.9 $1,629, max $2,358; GF $898 / $1,178 / $1,485; XM $327 / $433 / $503. There is no
     pile-up below a round number, and per-window net shares are smooth too.
   - **"Continuation" as the side of weak-move matches.** Beyond the 300-ms event, a weak-move match has the side of
     the previous cluster match 0.3-1 s earlier in 72% and 1-2 s earlier in 65%. That is no better than the weak vote
     (64-66%). Within 300 ms it is 92%, but those are legs of the same event (critique 1).
   - **Self-dealing / sibling maker.** The TypeScript-fingerprinted co-racer and maker 0x41e2e1cc has 658 orders in
     the calldata sample: 317-byte signatures, signatureType 3, salt/timestamp median 0.47. It signs throughout the
     window (rel quantiles 15 / 58 / 128 / 193 / 246 s) with no burst schedule, so it is not a sibling.

## Proposals (ranked by the chance of closing the gap)

### 1. The decision is a multi-leg sweep; its intensity is the size decision, and its top leg reads out the reservation price (strong form of X16 + X29 + X42; new X44)

- **Hypothesis.** On a trigger the bot decides how deep to sweep. It fires one pre-signed leg per wallet slot at
  adjacent ladder levels (touch, touch + 1 c, ...), and it uses the large size on the touch leg when the stale depth
  justifies it.
  - The intensity of the event (number of legs, top leg minus the touch, total signed shares) rises with the trigger
    in fair-value units.
  - The top leg's limit is an interval-censored readout of FV_bot - m. That is the missing handle for the bot's own
    fair value (X21 / X30 were inconclusive because their FV was calibrated to the market mid).
  - The big-order PnL (0.70 of the pooled per-window PnL) is the PnL of high-intensity events.
- **Evidence.** Critique 1-3:
  - fast cross-wallet legs at +-1 c, never at the same price, live and in historical consecutive transactions (79% at
    +-1 c, 4% at the same price);
  - pay-up 39% in fast pairs vs 8% in single-order events;
  - the fast multi-leg share doubles with the move (9% -> 19-20%) and is highest late in the window;
  - adjacent-level cross-wallet pairs hold a large order 39% vs 14% at the same price.
- **Test.**
  1. **Events with lost legs.** On every live development block, build events from cluster matches (taker and maker
     first fills with match ms, W4 included via topic2) and add their lost legs: cluster maker fills at a leg price
     within 2 blocks whose order hash has no taker fill. Record for each event:
     - legs;
     - wallets;
     - the levels relative to the touch 50 ms before the first leg;
     - the total signed shares, from calldata.
  2. **Intensity model.** Model P(legs >= 2), the top leg minus the touch, and the total signed shares. Features at
     the first leg's ms:
     - the signed microprice move toward o in FV cents (market-implied delta x move);
     - the Binance USD-M BTC tick in [m - 350, m - 250);
     - |vote|;
     - depth at touch..touch + 3 c (btc5m_xclob snapshots plus touch changes);
     - |p - 0.5| and rel.

     Split by halves and report AUC against an activity-only baseline (other trades in the last 1 s, touch changes in
     the last 300 ms).
  3. **Reservation price.** Fit FV_bot = P(TWAP-60 > strike | S = the microprice composite at t - L, k x sigma, tau),
     with free k, L and ETH weight, by maximum likelihood on the interval [L_top, L_top + 1 c) for events whose sweep
     stopped while depth remained. Validate on the next block:
     - calibration of FV - m against L_top;
     - side of single-leg weak-vote decisions as argmax(FV_o - ask_o);
     - whether the fit reproduces the underdog surface (tilt7).
  4. **Historical intensity.** Build events from same-block and consecutive-tx cross-wallet cluster orders (calldata
     sample; extend it to the 7 VALIDATE days). Measure legs per event by day and menu, and fit P(multi-leg) at the
     block clock from the six-series move and the Bybit BTC/ETH book (BUILD -> VALIDATE).
  5. **PnL.**
     - Measure the share of per-window PnL variance carried by multi-leg events.
     - Run an oracle replay with the event intensity in place of the order size.
     - Size the convention-(b) replica by predicted intensity (1 leg = small, >= 2 legs = small + large) and score it
       against the 0.18 replica and the 0.66-0.70 ceiling.
- **Data.** Live development blocks (btc5m_xclob / xven, btc5m_clob_raw2 / venues2, own-chain fills, calldata of every
  live cluster tx), `calldata_sample.parquet` plus more VALIDATE calldata, `fills.parquet`, venue and Bybit book caches.
- **Signature if true.**
  - Intensity rises with the FV-unit move: AUC >= 0.70 at ms against an activity baseline <= 0.60.
  - The top leg minus the touch increases monotonically with the move.
  - The fitted FV is calibrated to <= 1.5 c at L_top and explains the underdog tilt.
  - Multi-leg events carry most of the big-order PnL, and the intensity-sized replica at least doubles 0.18.
- **Signature if false.** Intensity does not depend on any decision feature (AUC <= 0.55). Then the sweep depth is a
  dispatcher draw, and the size part of the PnL condition is out of reach by construction. That is a quantitative wall
  item.

### 2. Wallets are concurrency slots with a refractory period, and the dispatcher is a decision component (new X45; strong form of X16 / X27, and it motivates X5)

- **Hypothesis.** Each wallet carries at most one in-flight order: the client awaits the response, so the refractory
  is about 100-250 ms. A decision's legs go to idle wallets by a rule: a priority, a busy-skip, or random draws with
  per-wallet rates. W4 is the fourth slot.
  - The rule decides which wallet's per-window PnL holds which decision. The examiner scores that per wallet
    (condition 7).
  - It also produces XM's sparse, one-sided windows: XM's side is then the side of the event it joined.
- **Evidence.** Critique 4:
  - DS's minimum gap is 120 ms over 521 matches;
  - same-wallet pairs within 100 ms: 1, against 101 cross-wallet pairs under 100 ms;
  - when DS is busy (a match in the last 200-400 ms) the first leg moves away from DS (1/6 and 53% vs 82%);
  - historically, same-wallet consecutive-tx pairs make up 15% against a null of 52%.
- **Test.**
  1. **Refractory.** For each wallet, plot the gap distribution between consecutive matches with match ms (taker and
     maker, W4 included) and estimate the floor and the busy kernel. Repeat on every development block and day.
  2. **Dispatcher.** For each event, record each wallet's busy state: an own match or an unexpired remainder in
     [m - 400, m). This is own state and is reported only as a policy description. Fit three candidate rules (fixed
     priority with busy-skip, rate-weighted random, round-robin), score wallet-per-leg accuracy on a later block, and
     include lost legs to reduce selection.
  3. **Historical replication.** Use the same-block tx order from calldata on all VALIDATE days.
  4. **Consequences for the metrics.**
     - Re-dispatch the pooled decision stream with the fitted rule and with random assignment. Compute per-wallet
       per-window PnL correlations against each wallet's actual PnL (an oracle on decisions, not on wallets).
     - Measure the share of XM's orders that are non-first legs, and XM's side per event.
     - Remove W4 (slot 4) from the market-activity features (X5) and rerun the block-second baseline.
- **Data.** Live development blocks with match ms, `cd6_live` / new live calldata, `calldata_sample.parquet` (tx_index),
  `fills.parquet`, W4's fills via topic2.
- **Signature if true.**
  - A hard per-wallet floor that is stable across blocks.
  - A dispatcher rule with >= 85% leg-to-wallet accuracy.
  - The oracle re-dispatched by the rule keeps per-wallet PnL r >= 0.6, while random dispatch drops DS / GF to <= 0.3.
  - XM is mostly a later leg.
- **Signature if false.** Dispatch is random given idle slots. Per-wallet PnL replication (condition 7) is then
  unattainable for any rule, and FINAL_RULE should say so with the random-dispatch ceiling.

### 3. The tick is the clock, stale liquidity is the gate: hazard conditional on an unrepriced touch (strong form of D2 / X31 and X23; new X46)

- **Hypothesis.** A tick toward o creates an opportunity only while the touch of o still rests at its pre-tick level.
  That happens when the maker has not repriced: slow quoters, or retail round-price bids on the other outcome. The bot
  fires on tick x unrepriced touch.
  - The low unconditional hazard (2.3% -> 8.7%) is the mixture of ticks whose stale level had already gone with ticks
    whose level was still there.
  - In quiet periods the opportunity is a slow FV drift that crosses a stale level.
- **Evidence.** Critique 5:
  - favourite fill counts +10-19% at round prices, with no spike at round underdog prices;
  - +1 c edge at round favourite prices (not significant);
  - prey maker 0xec10d230 over-represented in quiet matches;
  - the matches sit inside Polymarket book activity in both directions (iteration 6) but have never been split by
    whether the touch had repriced.
- **Test.** Work on the unthrottled book (btc5m_clob_raw / raw2, btc5m_xclob) on a 100-ms grid, as in lag7.
  1. **Features at t.**
     - the signed microprice tick toward o over [t - 500, t);
     - the touch of o: price, size and age (ms since its price or size last changed);
     - whether the touch has changed since the last tick toward o ("unrepriced");
     - a round-price flag for the touch;
     - trades in the last 1 s.
  2. **Label.** A cluster match on o in [t + 100, t + 600).
  3. **Hazard table.** Tick strength x unrepriced x touch age. Then a logistic or GBM fitted on the first half and
     scored on the second, against tick-only and activity-only models.
  4. **Historical corroboration.** Compare the age and the maker class (continuous quoter vs one-shot order, from the
     maker's calldata signing pattern) of the orders the cluster consumed with those consumed by co-racers' matches
     and at placebo times.
- **Data.** btc5m_clob_raw2 / xclob and venues2 / xven (development blocks), live calldata of the consumed makers, the
  calldata sample.
- **Signature if true.**
  - Hazard >= 20% for a tick >= 0.1 bp with an unrepriced touch, and <= 2% when the touch already repriced.
  - The tick x unrepriced model reaches decision-level AUC >= 0.80 against activity <= 0.70. That gives a
    decision-level presence rule with a gain well above 0.05 for the future-block exam.
  - Quiet-match side follows the sign of FV minus the stale level.
- **Signature if false.** Repricing state adds nothing to the tick. The gate is elsewhere (dispatcher capacity,
  proposal 2) or unobserved.

### 4. Aim the rule at the exams it will face: h1 first, and record weekday sealed blocks (strong form of X34 and X26; new X47)

- **Hypothesis.** The two things that can still fail an exam before any decoding question is reached:
  - **Sequence.** The h1 exam (historical, block clock) comes first and decides most of the remaining budget. The
    live-only side and PnL work cannot be examined there.
  - **Regime.** The future-block lot, when it comes, will be weekend-only plus a 6-h block with no recording. The
    decoded live side rule is regime-dependent (weak-vote share) and the large size is nearly absent on weekends, so
    that lot is biased against the rule.
- **Evidence.** Critique 6:
  - rec_exam7 hard stop 11-02 06:00 UTC, ~7 MB/h (10 MB written by 10-31 17:30);
  - sealed coverage Saturday 18-24, Sunday 00-06 and 12-18, and 10-31 06-12 lost;
  - Saturday weak votes 22 -> 56%, agreement 86 -> 75%, large 3.5%.
- **Test.**
  1. **Weekday vs weekend.** Run the frozen `_live_vote` and the intensity measures (proposal 1) on the weekday
     development blocks 11-02 00-06 and 12-18 (Monday). Compare them with the Saturday and Sunday development blocks:
     weak-vote share, agreement by vote strength, large share, legs per event.
  2. **Re-plan the recorder under the 300 MB cap.** Keep 10-31 16:03 -> 11-01 06:00 (14 h, ~100 MB; sealed 18-24 and
     00-06). Pause through Sunday. Record 11-02 00:00 -> 24:00 (24 h, ~170 MB): weekday development 00-06 and 12-18,
     weekday sealed 06-12 and 18-24. Total ~270 MB. Record the change in state.json `live_lab`.
  3. **Fallback.** Write and freeze in `final_rule.py` the fallback for blocks without exam inputs (the block-clock
     rule), so that scope stays >= 80% on any future lot.
  4. **Version check for h1.** Measure on VALIDATE calldata vs the 10-31 calldata the parameters that h1 depends on:
     menu, pay-up rate, legs per event, refractory floor (block-level), burst times, large share per wallet.
- **Data.** tools/sealed.py, rec_exam7 status, development live blocks, calldata of VALIDATE and 10-31.
- **Signature if true.**
  - Weekday development blocks show weak votes <= 30%, per-decision agreement >= 85% and large >= 10%, against the
    weekend's 56% / 75% / 3.5%.
  - The re-planned recorder gives >= 12 weekday sealed hours.
  - The version check shows which live parameters transfer to h1.
- **Signature if false.** No regime difference: the weekend lot is representative, and the recorder plan can stay.

### 5. The underdog tilt as a return-unit threshold or a liquidity shape, not a different vol (alternative families for X30 step 3; new X48)

- **Hypothesis.** The tilt that grows with |p - 0.5| (58% small / 69% big at 0.3-0.4, also at static prices) comes from
  the decision threshold or from where stale depth rests, not from a wider-vol fair value. Two candidates:
  - **Return threshold.** The bot fires when (FV_o - ask_o) / ask_o >= theta. A threshold in cents, in log-odds or
    against the fee 0.07 p(1 - p) is symmetric between Up and Down and cannot tilt. A return threshold is asymmetric:
    at p = 0.8 the favourite needs about 4 times the underdog's cent edge.
  - **Liquidity shape.** Stale asks exist where retail rests round-price bids.
- **Evidence.**
  - The underdog share by cent (VALIDATE taker orders) falls smoothly: 0.64 at 12-13 c, 0.57-0.61 at 15-19 c,
    0.53-0.56 at 20-27 c, ~0.51 at 28-49 c.
  - It dips at round favourite prices (0.60 / 0.65 / 0.70 / 0.75 / 0.80: 0.48-0.53 against neighbours 0.51-0.56).
  - Other takers tilt the other way (35%).
- **Test.**
  1. **Required move.** On VALIDATE taker orders with the it4b six-series move per order (block clock) and on live
     decisions (microprice, ms), at matched |p - 0.5| bins, compare the delta-scaled move in cents preceding underdog
     buys and favourite buys, and the share of buys against the tick.
     - Return threshold: both follow the tick, and the required-move ratio is about p_fav / p_und.
     - Vol premium: an additive shift, and underdog buys with no tick or against it.
  2. **Families.** Fit a conditional logit of the side on ask vs FV under three threshold families (cents, log-odds,
     return) and compare log-likelihood on VALIDATE.
  3. **Liquidity.** Repeat excluding round favourite prices.
- **Data.** `fills.parquet`, the it4b cells / side features, live decision table.
- **Signature if true.** The return family beats the others by >= 10 log-likelihood units per 1,000 decisions and
  reproduces tilt7's surface with tick-following on both sides. Alternatively, the round-price exclusion removes most
  of the tilt.
- **Signature if false.** Underdog buys occur against the tick at extremes. Then the wider-vol FV (X30) is the
  explanation, and proposal 1's reservation-price fit should find k > 1.
