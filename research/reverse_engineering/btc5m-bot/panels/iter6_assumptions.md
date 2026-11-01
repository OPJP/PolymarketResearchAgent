# Panel, iteration 6: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means the PnL ceiling, the size component,
the fair value behind the side, whether the decoded microprice trigger is a trigger at all, and the unit of XM's side
condition. I ran small checks on development data only:

- VALIDATE fills (`.cache/re/btc5m-bot/fills.parquet`, windows starting 10-16..10-23, 235,525 fills);
- the live development block events (`live6_events.parquet`, 10-31 13:00-14:47);
- the 24 cached VALIDATE taker tapes (`eval/tapes`);
- `binance_1s.parquet`, for daily realized volatility.

Nothing sealed was read. Definitions used below:

- an order is an `orderHash`;
- per-window PnL is the sum over fills of shares x (payout - price) - fee;
- "big" means an order with at least 90 filled shares. This is a proxy for the 100-share size. It mixes the size choice
  with fill depth, so the calldata sizes should replace it.

## Critique

1. **The PnL ceiling "by construction" (X17) does not hold.**
   - **Split-half reliability.** I split each wallet's own VALIDATE orders into two random halves by order-hash parity.
     The per-window PnL of the two halves correlates -0.03 (DS), 0.14 (GF) and -0.03 (XM). Per-window net shares give
     the same numbers.
   - Per-window PnL is net x outcome (r = 0.89-0.92). A wallet therefore has no window-level direction: its per-window
     PnL is a sum of independent order-level bets.
   - The siblings are disjoint draws from one decision stream. They also compete for the same stale ask (DS first, GF
     about 54 ms later). Their low correlation (0.00-0.20) says nothing about a replica that holds the same orders.
   - **What counts is order overlap in (window, outcome, price, size).** Timing does not count, and neither does who
     got the fill: an order at the same price on the same outcome contributes the same PnL. I simulated a replica made
     of a random share q of the wallet's own orders, plus false orders placed in random windows:

     | q matched | extra orders (x matched) | DS r / rho | GF r / rho | XM r / rho |
     |---|---|---|---|---|
     | 0.25 | 0 | 0.48 / 0.46 | 0.58 / 0.53 | 0.49 / 0.39 |
     | 0.50 | 0.5 | 0.57 / 0.51 | 0.65 / 0.57 | 0.59 / 0.52 |
     | 0.50 | 1.0 | 0.49 / 0.44 | 0.55 / 0.48 | 0.49 / 0.41 |
     | 0.75 | 0.5 | 0.71 / 0.66 | 0.77 / 0.70 | 0.69 / 0.63 |

   - **The size carries the variance.** The PnL of the big orders alone correlates with the wallet's total PnL at
     GF 0.85, XM 0.73 and DS 0.35. Big orders are 8.4%, 10.3% and 1.5% of the orders.
   - Big-order PnL also correlates 0.47-0.55 across siblings (GF-DS 0.55, GF-XM 0.49, DS-XM 0.47), against 0.00-0.20
     for their totals. GF's total PnL correlates 0.45 / 0.48 with DS's and XM's big-order PnL, and the pooled total
     correlates 0.70 / 0.72 with the pooled big-order PnL. The shared, replicable part of the PnL is in the big orders.
   - **The frozen replica cannot pass for GF or the pool, even with perfect decisions.** I replayed the wallet's exact
     orders (actual window, outcome and price) at a fixed 30 shares, as in H37. Against the actual PnL this gives
     DS 0.78 / 0.79, GF 0.40 / 0.48, XM 0.54 / 0.58 and pooled 0.41 / 0.49. The 0.18 of the frozen rule says more
     about its 30-share, 2-s-latency design than about any ceiling.
   - Note on the brief: latency >= 2 s is stated for the held-out return. The correlation condition asks for "strict
     fills". Pre-register which applies before building the replica (see proposal 1).

2. **Size is treated as a per-wallet ratio (component confidence 0.7). The big orders look like a shared, event-level
   decision.**
   - Within 1 s of a GF big taker order, DS has a big order on the same outcome 9.6% of the time, against a DS base
     rate of 1.5% (x6.4). After an XM big order, GF has one 24.7% of the time (base 8.4%, x2.9); after a DS big order,
     26.7% (x3.2). A big order on the opposite outcome follows only 0.6-2.8% of the time.
   - Per-window big-order nets correlate +0.48 to +0.54 across wallets.
   - The nets of big and small orders are negatively correlated, both within a wallet (GF -0.36, XM -0.33, DS -0.23)
     and across wallets (XM big vs GF small -0.31, XM big vs DS small -0.25). Within a window the small orders lean
     against the big ones.
   - A wallet's small orders that follow its own net big exposure take the opposite outcome 56-66% of the time
     (live, quiet matches: 58%, n = 140).

3. **The side's fair value is assumed to be the market's.**
   - `levelfv6.py` picked the vol multiplier k at placebo instants so that FV matches the market mid, and then found the
     side at chance. If the bot's FV differs from the market's in a structured way, that calibration removes exactly the
     difference the bot trades on.
   - A model-free signature of such a difference exists. A pure "follow the composite move" rule treats both outcomes
     alike (a digital's delta is the same for Up and Down), so it predicts an underdog share of 0.5 at every price.
     The cluster instead buys the underdog more often the further the price is from 0.5.
   - Underdog share of VALIDATE cluster taker orders (|p - 0.5| >= 0.02):

     | rel (s) | small orders, \|p-0.5\| <= 0.1 | small orders, \|p-0.5\| 0.3-0.4 | big orders, \|p-0.5\| 0.3-0.4 |
     |---|---|---|---|
     | 0-60 | 0.497 | 0.628 | 0.537 |
     | 60-120 | 0.494 | 0.618 | 0.645 |
     | 120-180 | 0.491 | 0.585 | 0.686 |
     | 180-240 | 0.495 | 0.501 | 0.697 |
     | 240-300 | 0.445 | 0.487 | 0.646 |

   - Late in the window, close to 0.5, the small orders turn toward the favourite (0.445).
   - Other takers do the opposite. In the 24 cached tapes their BUY prints are 26-31% underdog at |p - 0.5| = 0.3-0.4
     by count (size-weighted 0.48-0.58).
   - Late small orders earned a gross +4.5 c/share on underdogs vs +0.55 c on favourites (n about 19k each). This is
     noisy, because outcomes cluster by window.

4. **"Quiet trigger decoded" rests on P(tick sign | match), not on P(match | tick).**
   - The vote moves before 90% of matches inside a 500-ms window, so as a presence trigger it has almost no
     specificity.
   - Out of sample, the quiet agreement fell from 84.0% to 77.3% (placebo 55%).
   - After quiet matches, venue prices keep moving the bot's way for 1-3 s (70-92%), and participation is flat in the
     trigger strength.
   - This is also what a correlate of a faster or deeper input looks like. The brief warns about exactly this kind of
     co-occurrence match, and the trigger-versus-correlate test has not been run.

5. **XM's side condition is set off by sparse participation.**
   - XM's 420 one-sided VALIDATE windows (24.3%) hold a median of 1 XM order (mean 1.64; its two-sided windows have a
     median of 7). Only 14.5% of them contain an XM big order, against 50% of its two-sided windows.
   - XM's first order in such a window has a sibling order within 2 s 92.6% of the time, and 65.8% of those sibling
     orders are on the same outcome.
   - So the examiner's window-level criterion is really a test of XM's decision in one or two fire events. Pre-register
     the unit (per order and per one-sided window, with maker remainders assigned to the taker decision that created
     them) before the exam. The per-fill-second 72.6% is the wrong unit.

6. **The ladder lifecycle shows in presence. It is not market activity and has not been examined.**
   - Taker first fills per block second, relative to rel 150-168 (3-s rolling): around the +172.7 s burst, XM dips to
     0.75-0.77, GF to 0.84 and DS to 0.84 in the ~10 s around the burst. Then they spike 8-12 s after it: XM 1.54,
     GF 1.43, DS 1.16 at block rel 184-186.
   - The pattern is weaker around +42 s (XM 0.87-0.89, then 1.22 at rel 54) and very weak at rel 210 (the next
     window's -89.5 s burst).

7. **Checked and not supported** (so nobody redoes them):
   - **Daily volume quota.** Over 14 days, DS and GF daily taker fees correlate 0.86 and 0.83 with daily BTC realized
     vol (fee CV 0.39 vs RV CV 0.34). The volume follows the market and is not a quota. XM is at -0.12 only because of
     the 10-13 switch.
   - **Live hedging chains.** A quiet match is on the same outcome as the previous cluster match within 0.3-2 s 69% of
     the time (moving matches 67%). There is no pair-completion rule at the decision level.
   - **Pair-cost conditioning.** The less-held share rises from 0.44-0.59 to 0.58-0.63 when the pair cost "if bought"
     is below 0.95. This is mostly mechanical selection (the less-held side is cheap when the bot was right), not a
     hedge rule.

## Proposals (ranked by chance of closing the gap)

### 1. The PnL target is an order-overlap problem, not a ceiling (strong form of X17; new X28)

- **Hypothesis.** Per-window PnL is a sum of independent order-level bets with no window-level direction, so a replica
  correlates with a wallet exactly to the extent that it holds the same orders in (window, outcome, price, size). Two
  things kept the investigation below 0.5:
  - the fixed 30-share size, which caps even perfect decisions at 0.40 / 0.48 for GF and 0.41 / 0.49 pooled;
  - a 2-s latency that moves the replica off the wallet's prices in the moving regime.

  The sibling correlations are not a bound, because siblings hold disjoint orders.
- **Evidence.** Critique 1:
  - split-half per-window PnL correlation -0.03 / 0.14 / -0.03;
  - the overlap table;
  - big-order PnL correlates 0.85 (GF) and 0.73 (XM) with the total, and 0.47-0.55 across siblings;
  - the oracle-decision replay at 30 shares.
- **Test.**
  1. Reproduce the split-half and overlap curves per wallet, on both VALIDATE halves, with calldata sizes. Pre-register
     the overlap the target needs: per the table, about 50% of the wallet's order PnL variance matched with at most 50%
     extra orders, or 25% with no extras.
  2. Define an order-matching score. Greedily pair, within each window, replica orders with wallet orders on the same
     outcome, |price difference| <= 1 c and the same size class. Report recall and precision weighted by
     size x p(1 - p) (the per-order PnL variance).
  3. Oracle-decision ceiling of the fill model: feed the wallet's own decisions (calldata time, side, limit, size) through
     the replica's strict-fill model and correlate the result with the actual PnL. This is the true ceiling of that fill
     model.
  4. Rebuild the executable replica:
     - decoded trigger and side at the decoded latency (100-600 ms), limit at the touch, size from proposal 2;
     - fills from observed liquidity: live, the recorded book at decision + latency; historically, the depth of the
       touch from other traders' orders (tape, and the makers in the consumed levels);
     - score it against the 2-s, 30-share version.
  5. Settle with the examiner's definition, before running: whether the latency >= 2 s applies to the correlation
     condition or only to the held-out return.
- **Data.** `fills.parquet`, the calldata sample (sizes, limits), `cd6_live.parquet`, the live books, VALIDATE tapes.
- **Signature if true.**
  - The oracle-decision ceiling is >= 0.7 per wallet.
  - A size-aware replica reaches >= 0.5 for GF, XM and the pool on both halves.
  - DS tracks the overlap curve: it needs about half of its small orders matched.
- **Signature if false.** The oracle-decision replay under strict fills is already below 0.5 for some wallet. That is
  the honest, quantitative wall for the PnL condition, and FINAL_RULE should state it with these numbers instead of the
  sibling argument.

### 2. The large size is an event-level decision (strong form of C4 and the size component; new X29)

- **Hypothesis.** The bot picks the large size (100; 50 or 200 in other regimes) on strong events, such as a large
  venue move, a sweep priced above the touch, or a large value gap. It picks it across wallets at the same time; it is
  not a fixed per-wallet ratio. These events carry most of the replicable PnL.
- **Evidence.** Critique 2:
  - big-order co-occurrence across wallets at x2.9-x6.4 the base rate on the same outcome, and below 3% on the
    opposite one;
  - per-window big-order nets correlate +0.48-0.54 across wallets;
  - large orders are priced above the touch more often (23% vs 11%; iteration 6) and are more common after large
    moves (16-21% vs 8%; iteration 5).
- **Test.**
  1. Use the calldata sample (17,863 cluster orders) with the signed size, not the filled size, to remove the
     fill-depth confound.
  2. Measure large-order co-occurrence inside fan-out events (< 300 ms, same window and outcome) against a permutation
     that shuffles size labels within wallet-day (2,000 draws).
  3. Model P(large | decision features). Features: the largest venue move over [d - 600, d - 100) ms (d estimated from
     the block clock and tx order, X22), the move in FV units, ask - FV (proposal 3), how many cents above the touch the
     order was priced, touch depth, |p - 0.5| and rel. Fit on BUILD and report the AUC on VALIDATE. Repeat on the live
     block with matching-engine ms.
- **Data.** The calldata sample, the venue caches, the Bybit book archives, and the live block.
- **Signature if true.**
  - Large orders cluster in events well above the permutation null.
  - P(large) rises with signal strength, with AUC >= 0.75.
  - With the size rule, proposal 1's replica gains most of the gap for GF and XM.
- **Signature if false.** If size is random per wallet, a replica cannot match the large orders. The PnL condition for
  GF and the pool is then out of reach (the oracle-decision 30-share replay gives 0.40 / 0.48), and that becomes part of
  the wall account.

### 3. The bot's fair value is not the market's: fit it by revealed preference, with the underdog-tilt surface as the signature (strong form of X21 and X13; new X30)

- **Hypothesis.** One level rule, "buy o when ask_o <= FV_bot,o - m", explains both regimes:
  - at the start of a move FV_bot jumps and the ask is stale (the moving regime);
  - later, Polymarket reprices past FV_bot and the other outcome becomes cheap (the quiet, late, small orders that fade
    the move).

  FV_bot differs from the market's FV in a structured way: a wider or term-structured vol, or a lag. That difference
  produces the underdog tilt that grows with |p - 0.5|, the late turn to the favourite, the negative big-small
  correlation and the fade of older moves (23-46% live).
- **Evidence.**
  - Critique 3: the underdog surface; other takers tilt the opposite way.
  - Critique 2: small orders lean against the big ones; DS's per-window PnL in the first vs second half of the window
    correlates -0.10.
  - Iteration 6: older moves (1-3 s before, then quiet) are faded.
  - X21 calibrated k to the market mid, which assumes the very thing this hypothesis denies.
- **Test.**
  1. Model-free surface on BUILD and VALIDATE. Measure the underdog share of cluster taker decisions by
     rel x |p - 0.5| x size x regime (moving or quiet from the six-series move). Condition it on the Polymarket mid
     change over the last 10-30 s:
     - a tilt that persists at prices unchanged for 30 s points to a different vol or shape;
     - a tilt that appears only after recent moves points to a lagged FV (fade).
  2. The same surface for other takers on the full VALIDATE tapes, with the cluster and W4 removed, count- and
     size-weighted.
  3. Revealed-preference fit on BUILD one-sided taker decisions, as a conditional logit of the chosen outcome on
     ask_o - FV_o:
     - FV_o = P(TWAP-60 > strike | S at t - L, k x sigma, tau);
     - strike = the window's priceToBeat, which is the previous window's settlement and known at the open;
     - S = the ETH-led composite;
     - free parameters k, L, ETH weight, margin m and the late-window TWAP treatment.

     Report the side accuracy on VALIDATE, moving and quiet separately, against the frozen 76.7%, and check that the
     fitted rule reproduces step 1's surface.
  4. Run iteration 5's two-sided check (not done yet). Take opposite-outcome cluster orders within 1 s of each other.
     Under one FV with m > 0, both are possible only if FV moved between them, so check whether the fitted FV did.
- **Data.** `fills.parquet`, the VALIDATE tapes, the venue caches, the Gamma priceToBeat (known at listing for the
  next window), and the live block for the ms check.
- **Signature if true.**
  - Fitted k != 1 or L > 0, and the surface is reproduced.
  - One rule covers both regimes.
  - Side >= 80% on taker decisions, and the quiet side >= 75%.
  - The ask - FV feature is not market activity, so it should also add to the presence gain.
- **Signature if false.** At the fitted parameters the tilt is a liquidity or ladder artefact. Then the same tilt
  appears in the bot's maker remainders and depends on touch depth.

### 4. Is the microprice tick the trigger or a correlate? (strong form of D2, and of H21/H33 at ms resolution; new X31)

- **Hypothesis.** The microprice vote co-moves with the bot's real input (a deeper book, order flow on an unrecorded
  venue, or a slower level rule as in proposal 3) and is not the trigger. The decoded 86% would then be partly
  co-occurrence, and the presence trigger is still open.
- **Evidence.** Critique 4: 90% coverage inside 500 ms, out-of-sample quiet agreement 84.0% -> 77.3%, continuation of
  70-92% after the match, and participation flat in the trigger strength.
- **Test.** On the live development blocks (`btc5m_venues`/`venues2` and `btc5m_clob_raw`/`raw2`):
  1. **Specificity.** In 100-ms slices, measure P(cluster match within 100-600 ms | vote toward o, ask_o in the ladder
     range), by tick size in FV units, against the base rate. This gives the precision and recall of the vote as a
     presence trigger.
  2. **Lag profile.** Measure side agreement in 50-ms bins over [m - 3,000, m + 3,000] ms:
     - a trigger peaks in the latency band and does not keep rising after the decision;
     - a correlate rises monotonically through m.
  3. **Incremental information.** Regress the venue move over [m, m + 2 s] on every recorded pre-match feature (ticks,
     trades, the Polymarket book), with and without the bot's side, and report the partial R². Repeat for co-racers'
     matches on the same outcome as a control.
- **Data.** The two recorders' feeds through `iter_live`, `live6_events.parquet`, and the next development blocks.
- **Signature if true (correlate).** P(fire | tick) is barely above base, agreement rises through m, and the bot's side
  adds R² beyond every recorded input. That part is the quantified unexplained input the brief requires for a wall.
- **Signature if false (trigger).** A lag peak at 100-300 ms, no incremental information, and a hazard that steps up
  with tick size.

### 5. Ladder lifecycle: queued decisions around the +172.7 s burst (new mechanics item; new X32)

- **Hypothesis.** The bot is a single-threaded Node process. While it signs four ladders (+172.7 to about +177 s) it
  does not submit, and triggers that arrive meanwhile are queued and sent afterwards as stale decisions. Some of these
  look quiet at the match because the move came 1-5 s earlier. An alternative: the old ladder runs out before the new
  one is usable (a copy budget).
- **Evidence.** Critique 6: per-wallet dips of 0.75-0.84 around the burst and spikes of 1.16-1.54 at 8-12 s after it.
  The effect is weaker at +42 s.
- **Test.**
  1. Historically, align each wallet's dip with its own signing offset from calldata (XM 0, DS +1.06 s, GF +2.17 s):
     - staggered dips mean the signer blocks that wallet;
     - one common dip means the process blocks.
  2. Live, for matches at rel 176-188: measure the quiet share, and the side agreement with venue moves at
     [m - 5,000, m - 600) vs [m - 600, m - 100).
  3. Repeat at +42 s and at rel 210.5 (the next window's burst).
- **Data.** The calldata sample, `fills.parquet`, and the live blocks.
- **Signature if true.** Dips staggered by wallet, and a post-burst spike enriched in quiet matches whose side agrees
  with the move at queue time. This is a deterministic schedule term for the rule. It explains only a slice of the
  quiet matches.

### 6. Economics: tier bonuses and why there are four wallets (low priority; C1/B6; new X33)

- **Hypothesis.** The multi-wallet structure is rebate-driven. The operator moves volume so that each wallet climbs
  the taker tiers and stays in them:
  - Obsidian needs $10M of 30-day weighted volume for the 50% rate;
  - polyrea's table lists one-time level-up bonuses totalling $34.3k per wallet up to Obsidian.

  If so, per-wallet participation is a dispatcher setting (fixed shares within a regime), not a market decision.
- **Evidence.** GF's first rebate rows include the $10 and $50 bonuses. XM's volume share dropped from 0.51 to 0.085 at
  10-13 14:10 with no outage. Daily volume follows realized vol (critique 7), so this is an allocation and not a quota.
- **Test.**
  1. From the first row to H, compute each wallet's daily ratio of TAKER_REBATE to the previous day's fees. Look for
     the step path through the tiers (0.03 -> 0.50) and for one-off rows near $250, $1.5k, $7.5k and $25k.
  2. Check whether the 10-13 14:10 shift and the start of W4 line up with tier crossings.
  3. Compute each wallet's trailing 30-day volume against the $10M threshold.
- **Data.** Data-api activity (TAKER_REBATE and TRADE rows, development periods only) and `fills.parquet`.
- **Signature if true.** Bonuses are paid at each crossing, and volume moves to the wallet that is closest to its next
  tier. Then decode the pooled stream, treat the wallet assignment as fixed shares, and correct "Why it works" for the
  one-off bonuses.
