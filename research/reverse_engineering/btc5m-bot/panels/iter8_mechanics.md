# Panel, iteration 8: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That means calldata, the ladder and its copies, the signing loop,
sizes, pay-up, remainders and cancels, sets, inventory, collateral, fees and rebates, and fingerprints of the bot.

Data I used, all development:
- `b1_orders_sample.parquet`, `calldata_sample.parquet` and `calldata_sample_txs.parquet` (11 pre-H hours);
- `fills.parquet` (10-09..23), `cells/`, `windows.parquet` and `binance_1s.parquet`;
- `live6_events.parquet` and `post/cd6_live.parquet` (10-31 13:00-14:47);
- REDEEM activity rows for the VALIDATE week, from the cached data-api adapter;
- one Polygon receipt (`eth_getTransactionReceipt`) of a pre-H cluster transaction.

I did not open `.cache/live/` and read nothing sealed. Most checks ran as inline scripts; the one saved script
(`sizeconf.py`) and the REDEEM extract are in my session scratchpad. I wrote nothing to the workspace except this file.
Time of writing: 10-31 19:25 UTC.

## Critique

1. **The PnL condition is bound by decision overlap. No window-level exposure exists to copy.** I checked the 1,904
   VALIDATE cluster windows.
   - Per-window PnL against the cluster's end-of-window net times (outcome - 1/2): r = 0.885.
   - The net does not follow the window's public price path:
     - corr(end net, Binance return from the open to T) is -0.02 at 60 s, 0.03 at 120 s and 0.08 at 180-290 s;
     - the net's sign agrees with the 240-s return in 49% of windows;
     - corr(PnL, tanh(return_T / 5 bp) x (outcome - 1/2)) is at most 0.06 (Spearman at most 0.11).
   - With own state the picture is different: corr(PnL, net_T x (outcome - 1/2)) is 0.63, 0.76 and 0.85 at T = 120,
     180 and 240 s.
   - So the PnL sign is set by which orders the cluster got, mostly the large ones, not by a direction a public rule
     could hold. Together with replica8 (0.13-0.18 for every size rule) and overlap8 (8.2% of decision instants
     reproduced), this is enough for the wall account of condition 5. More replica variants without new decision
     information will not move it.

2. **The h1 side condition will fail for XM by construction. The live side is where the gap can close.**
   - XM is the only wallet that is one-sided in at least 20% of windows.
   - At the block clock XM scores 73.1% per decision, and the clock costs XM the most (72.4% -> 51.5% live, clock7).
   - On future blocks the frozen vote gives 85% on 68% of decisions. The binding gap there is the 31-45% weak-vote and
     no-vote decisions (64-80%). Proposal 1 targets exactly that.

3. **X5 (W4 in the baseline) is still open, and it is the cheapest presence lever for h1.**
   - W4 is a fourth slot of the same process, signed after GF in the same loop. Its prints sit in the "other traders"
     features of both the rule and the pure baseline.
   - It co-fires on the cluster's decisions: same outcome and same block second before 12.3% of cluster orders, against
     2.8% at placebo. So the baseline partly predicts the operator from the operator.
   - W4 is also missing from the operator net that drives size: size8 sums only the three studied wallets.
   - Both are cheap to fix (proposal 4). The examiner's own baseline will be built from the same features, so FINAL_RULE
     should name W4 as the operator's and exclude it in both models.

4. **About half of the own-state size signal is persistence of the large mode, and the "flat" bin is tiny.**
   Within-wallet univariate AUC on VALIDATE, with "big" meaning a fill of at least 90 shares (a fill-based proxy):

   | wallet | net from big fills | net from small fills |
   |---|---|---|
   | GF | 0.695 | 0.552 |
   | XM | 0.729 | 0.491 |
   | DS | 0.568 | 0.498 |

   - P(large) given a big fill on o in the last 5 s: GF 0.59 vs 0.39, XM 0.62 vs 0.41, DS 0.24 vs 0.18.
   - The "flat" bin behind the 77-83% headline is the first operator order of a window: n = 30 for GF, 6 for XM.
   - A genuine book effect remains. Among orders with no big fill yet in the window, the small-fill net still gives AUC
     0.669 for GF (n = 551) and 0.706 for XM (n = 122); DS 0.524.
   - Report H79 with a persistence control (whether the operator's previous order on o was large, and whether a big fill
     came in the last 5 s).
   - The large mode is a joint size-and-side decision. Taker orders that filled at least 90 shares bought the leg the
     operator was already long 78-82% of the time (all orders: 41-47%). A side rule that reads the order's own size is
     therefore an oracle; do not use it for condition 3.

5. **New mechanics facts (calldata sample):**
   - **FIFO copy queue.**
     - Where copies of one (wallet, burst, token, price, size) carry different signing ms, the earlier-signed copy is
       used first in 99.6% of 252 cases.
     - Across bursts of the same window, an old-burst copy is used after a new-burst copy at the same level in 1 of
       1,039 transitions.
     - 3.9% of orders (310 of 8,016) are first used after the next same-window burst was signed, about 95% of them
       within 4 s.
     - So the bot keeps a FIFO queue per level and swaps ladders roughly when all four wallets have finished signing
       (XM -> DS -> GF -> W4 takes about 4 s).
     - Filled copies per level per burst have smooth geometric tails (max 8), so no copy cap binds among filled orders.
   - **The signing loop has a fixed pause.** The second outcome's loop starts either right after the first (about
     150 ms for cents 1-99 at 1.7 ms per cent) or 934-944 ms after the first loop's cent 1, a fixed pause of about
     770 ms. The split is bimodal (DS +42-s bursts mostly paused, GF +42-s bursts mostly not). Each wallet's slot is
     about 1.06 s either way. This looks like an `await` on fixed I/O (for example per-token or per-wallet lookups),
     not CPU work.
   - **The 317-byte signature is the standard ERC-7739 wrapper**: 65 + 32 + 32 + 186 + 2, where 186 is the exact
     length of the Order type string. Large non-cluster makers (0x41e2e1cc, 0x9d57c42e, 0x239e726f) use the same
     type-3, 317-byte signature. The signature length therefore does not discriminate siblings; only the schedule and
     the loop do.
   - **Redemption runs as a fixed job**: REDEEM 90-96 s after each window's end (median 92 s), every window, all wallets.
   - **Two small wallets match the schedule but run other software.** 0xeb942f0f (18 maker orders, 12 signed at -89.2
     to -87.7 s; type 1, 65-byte signature, 1-10 USDC orders) and 0xc7501744 (10 taker orders at +40.1 to +40.5 s;
     type 2; salt not from the TypeScript generator) are not siblings. Others signing at about -89 s suggest that the
     -89.5-s burst is keyed to the window's CLOB availability. Gamma `acceptingOrdersTimestamp` would show it; minor.

6. **Negatives that save time** (each a quick measurement):
   - **The fee is paid in USDC, not in shares.** In tx 0x6cc97e46... GF paid 48.7437 collateral (47.0 plus a 1.7437 fee
     = 0.07 x 0.47 x 0.53 x 100) and received 100 shares; the fee went to 0x115f48dc in the collateral token. So no fee
     asymmetry can explain the underdog tilt, and fills.parquet's fee_usd is right.
   - **No rate-limit ceiling.** Orders per wallet per 10 s, 60 s and 600 s have smooth tails: DS p99.9 is 16, 61 and
     347, with maxima of 22, 72 and 349.
   - **No volume-pacing controller.** Across hour quintiles of seconds with a move above 1 bp, the quiet-order rate per
     quiet second rises from 0.094 to 0.28, while the quiet share of orders falls from 0.87 to 0.51. Quiet decisions ride
     on activity; they do not substitute for missing triggers.
   - **No drawdown sizing.** The big-order share after an operator-losing window (w-2) equals the share after a winning
     one: DS 3.0% vs 3.4%, GF 10.0% vs 9.7%, XM 6.7% vs 6.1%. Its correlation with the previous hour's PnL is -0.01 to
     -0.03.
   - **No collateral step at redemption (X27, quick form).**
     - Per-wallet order counts in 5-s bins are flat across the moment the previous window's REDEEM lands (for example DS
       1,733-2,339 per bin, with no break at 0). The same holds around a fixed rel of 92 s.
     - The early-window share of orders placed before the redemption does not depend on its size (0.44-0.56 across
       quartiles).
     - The full balance path would close X27; it is unlikely to matter.
   - **No CPU blackout.** On 10-31 13:00-14:47, 12 of 776 matches fall inside signing-burst spans against 12.3 expected
     (loop extents estimated from filled orders only). Signing does not block decisions.
   - **No timer in quiet matches.** The Rayleigh phase test of match ms over periods of 20-5,000 ms (per 20-min phase)
     gives a maximum of 18.1 for the 285 quiet matches, against 18.3 at the 95% point of a jitter null.
   - **No large-size band around the price at signing.** P(large) is flat in |limit - price at the burst|: GF 0.24-0.26,
     DS 0.05-0.08 and XM 0.08-0.12 across five bins.

## Proposals (ranked by the chance of closing the gap)

### 1. The stale-quote edge since o's touch last changed: inverse-fit of the trigger's quote function (strong form of X13 and of iteration-7 mechanics P4 step 3, which did not run)

- **Hypothesis.** The bot snipes stale quotes against a *relative* fair value.
  - For each outcome it keeps the Polymarket quote state at the last update of o's touch (time a, mid m_o(a)) and the
    venue composite S(a) at that moment.
  - It values o at m_o(a) + Delta_o x (S(t) - S(a)) and buys when that value exceeds ask_o(t) + c. Here c is about the
    net taker fee after the 50% rebate, 0.035 p(1 - p) per share, or about 0.9 c at mid prices.
  - The 500-ms vote is the special case of a fresh anchor. Weak-vote decisions are cases where the touch has been
    stale for seconds while the venues drifted in sub-tick steps.
  - Pay-up is the edge beyond the next level.
- **Evidence.**
  - Absolute fair values never timed the decisions: FV_DVOL - ask alone gives AUC 0.48-0.50, and the hazard is U-shaped
    in it (val8). X21's level FV sits 4.8 c from the market mid. A value anchored at the touch's last update cancels the
    level error that every absolute FV carries.
  - gate8: the hazard is highest when a venue ticks toward o while o's ask falls (22% vs 11-12%). Both raise this edge.
  - Weak votes come late in the window and in quiet books, where touch updates are rarer and anchors older. Quiet
    matches cluster within 2 s of earlier cluster matches.
  - The consumed prey quotes are 1-2 s old at the match (prey8).
  - value6's fixed 5-10-s value gap already gave 59-68% in quiet matches: the right quantity, measured in the wrong
    window.
  - msg8: no single message beats the vote, so the trigger is an accumulated quantity.
  - My Rayleigh check: quiet matches carry no timer phase, so their timing must come from a state like this one.
- **Test** (development recordings; then the next development block).
  1. Inputs: `btc5m_clob_raw2` (o's touch, every change, server ms) and `btc5m_venues2` (Binance USD-M BTC + ETH
     microprice at exchange ms, ETH scaled 1.235 as in the vote) for 10-31 13:00-17:55. Build an examinable version
     from `btc5m_xclob` + `btc5m_xven`.
  2. Anchor a_o(t) is the last change of o's best-ask price. Variants: price or size changes, and an anchor age cap of
     10 s.
  3. Delta_o = phi(Phi^-1(mid_o)) / (sigma sqrt(tau)). Take sigma from DVOL, or from a market-only regression of
     Polymarket mid changes on composite changes over 1-5 s on interval A.
  4. Edge E_o(t) = m_o(a) + Delta_o (S(t - 250 ms) - S(a)) - ask_o(t), in cents.
  5. Hazard: label a cluster match on o in [t + 100, t + 600) on the 100-ms grid. Fit a two-parameter threshold
     logistic in E on A (14:55-16:04), freeze it, and score it on B, C and 11-01 06-12. Score it alone and added to
     HAZ_FULL, against HAZ_FULL (0.656) and the Polymarket-activity baseline (0.598).
  6. Side on weak and no-vote decisions: argmax_o E_o(m - 50 ms). Pre-register it before 11-01 06-12, beside the DVOL
     fallback already planned. Report it by vote strength and by anchor age.
  7. Fit c by maximum likelihood and compare it with the net fee.
- **Data.** On disk (development blocks 10-31 13-18), plus 11-01 06-12 and the weekday development blocks.
- **Signature if true.**
  - A step in the hazard at E ≈ c: P(match) above c is at least 4 x the base, and c is within about 0.5 c of the net
    fee.
  - Out-of-sample AUC of at least 0.72 (a gain of at least 0.10 over the activity baseline).
  - Weak-vote side accuracy of at least 75%, rising with anchor age. With the strong-vote 85-97%, full-coverage live
    side would then clear 80%: condition 3 on future blocks.
  - The cells of gate8 ordered by their mean E.
  - If false (E adds less than 0.01 AUC and weak-vote side stays at or below 70%): the bot does not anchor on the
    Polymarket quote, and the weak decisions need an input outside the record. Their share and side then go into the
    wall account.

### 2. Visible Polymarket depth at the decision sets the pay-up level, the size and the fan-out (strong form of X42, X29 and X54)

- **Hypothesis.** The bot reads the book it is about to hit. At the decision it measures the stale depth on o (the
  levels at or below its value) and:
  - (a) sets the limit at the level where cumulative visible depth covers its order. That is the 16% pay-up.
  - (b) picks the large size when stale depth is large. In a second variant, it picks large when the touch is thin and
    it wants to rest a bid, which would explain why 84% of large orders leave remainders.
  - (c) sends further legs to free wallets when stale depth exceeds one order. Fan-out is then a sweep split across
    one-order-per-wallet slots.
- **Evidence.**
  - Pay-up is deliberate (18 of 21, lstar8), and more common for large orders (41% vs 12.8%), late in the window
    (thinner books) and when the FV is above the touch.
  - Consecutive same-block cluster pairs are cross-wallet in 71-80% and ±1 c apart in 45-53%, the shape of a sweep
    across wallets.
  - The prey are small (median original size 10 shares), so 100 shares rarely sit on one level. A depth rule predicts
    large orders where several stale small quotes stack.
  - The historical rejection of a depth rule (iteration 7, finding 14) used post-race depth: competitors take the stale
    depth between the bot's view, 50-150 ms before the match, and its arrival. It cannot reject a rule on visible
    depth.
  - X54 used ask changes and activity, never depth. Iteration-8 Next item 2 (a size decoder from touch depth) has not
    run.
  - The X51 depth-aware strict-fill model needs the same depth reconstruction.
- **Test.**
  1. Live development blocks: for every taker decision with calldata (signed size, limit), take the unthrottled book at
     m - 50 ms. Record the visible ask ladder of o from the touch to touch + 3 c with sizes, and its cumulative depth
     D(L).
  2. Price: the share of pay-up orders whose limit equals min{L : D(L) ≥ size}, against the touch rule. Also check
     non-pay-up orders: does the touch depth cover them?
  3. Size: within-wallet AUC of P(large) from visible depth (touch size, D(touch + 1 c), stale depth under the
     proposal-1 value), alone and with the operator net (including W4). Does depth explain the net away?
  4. Fan-out: P(legs ≥ 2) and the number of legs from D / small size, against X54's 0.61-0.63 baseline.
  5. The weekday development blocks 11-02 00-06 and 12-18 are needed for at least 100 large orders. The exam feed holds
    the touch with sizes and 10-level snapshots every 10 s, so report the touch-only version as the examinable one.
- **Data.** `btc5m_clob_raw2`, live calldata, on-chain fills; the weekday development blocks.
- **Signature if true.**
  - The depth-cover level predicts at least 70% of pay-up limits (the touch rule predicts 0%).
  - Visible depth gives a within-wallet large AUC of at least 0.70 and removes at least half of the own-net effect.
  - The legs AUC is at least 0.70.
  - Size then becomes a public input. An executable replica can carry the size class (the own-decision oracle goes from
    0.41 at 30 shares to 0.88 at the size class), and the price rule covers the pay-up mode exactly.
  - If false: size is own-state policy, as the reverse engineer reads it, and pay-up is a value margin, not depth.

### 3. Ghost orders: the full decision record from the touch feeds (strong form of X15, X35 and X36)

- **Hypothesis.** Every decision is a GTC BUY at the touch. A lost race leaves the order resting at the old ask L until
  its TTL cancel: as the new best bid of o, or for Down as the best Up ask at 1 - L. These ghost orders appear in the
  touch feeds, including `btc5m_xclob` in sealed blocks.
  - So the full decision record (filled and unfilled) can be built.
  - It answers the question every remaining gap depends on: is the decoded hazard's 92% miss a selective bot (no
    decision) or a race lottery (a decision made, the fill lost)?
- **Evidence.**
  - Pure resting orders are 16% of VALIDATE orders (28,342 of 175,831), and only about 19% of remainders ever refill.
    If lost races behave like remainders, there are 3-4 unfilled lost races per pure resting fill, so decisions are
    about 1.5-1.7 x filled orders. That prior is testable.
  - X15 was ruled out on order size alone.
  - The attribution steps of the iteration-6 mechanics panel (lifetime, fan-out co-insertions, synchronized cancels)
    never ran. X35 only bounded the TTL historically.
- **Test.**
  1. Truth set. Take the on-chain cluster M and MT orders of the development blocks. Find each one's insertion (+R at L
     on o) within ±50 ms of its match, and its removal (-R with no trade). This gives the live TTL by wallet and size,
     and shows whether removal follows a contrary tick or a fixed delay.
  2. Fingerprint from mechanics only, never trigger features, so that the hazard test stays non-circular:
     - size in the day's menu, or menu size minus the taker part;
     - price equal to o's ask within the previous 300 ms;
     - lifetime inside the TTL distribution;
     - identical co-insertions at the same level at the fan-out lags (7-250 ms), with synchronized removal.

     Measure precision on held-out truth orders against non-cluster resting orders whose maker is known on chain.
  3. Build the decision record for 10-31 13:00-17:55 and 11-01 06-12. Report:
     - decisions per filled order;
     - P(fill | decision) by regime;
     - the ghosts' side agreement with the vote by strength;
     - the hazard refit on decisions, with recall at matched volume.
  4. Use it for size: a lost-race natural experiment. Compare P(next order on o large | the previous decision won) with
     P(... | it lost) at a matched trigger. That separates a size driven by own fills from a decision-level mode.
- **Data.** `btc5m_clob_raw2`, `btc5m_xclob`, live calldata, on-chain fills, trade events.
- **Signature if true.**
  - Race lottery: at least 2.5 decisions per filled order, and hazard precision at matched volume of at least 25%.
    Presence should then be stated on the decision record (the brief's "has an order resting" label), and the fill
    lottery becomes the quantified wall for fill presence and PnL.
  - Selective bot: about 1.5 decisions per filled order. Then the trigger is genuinely selective, and proposals 1-2 (or
    an unrecorded input) must explain it.
  - Either way, ghost side agreement should equal filled side agreement (one trigger).

### 4. Operator completeness: W4 into the operator net and out of "market activity" (strong form of X5 and C1)

- **Hypothesis.** W4 is the fourth slot of the same process: the same schedule and loop, signed after GF.
  - (a) Its fills belong in the operator net that drives size.
  - (b) Its prints are the operator's own decisions sitting inside the market-activity baseline, which inflates the
    baseline that the presence gain is measured against.
- **Evidence.**
  - W4 shows the same outcome in the same block second before 12.3% of cluster orders, against 2.8% at placebo.
  - It has 344 fills in a VALIDATE hour, against about 2,000 for the three wallets, so the operator net misses about 15%
    of the operator's flow.
  - size8 sums only GF, XM and DS.
  - The C1 search filtered on the 317-byte signature, which is the standard ERC-7739 wrapper (critique 5).
- **Test.**
  1. Fetch W4's fills for BUILD and VALIDATE (eth_getLogs, topic2 = W4).
  2. Add W4 to the operator net in size8 and report the change in within-wallet AUC.
  3. Remove W4's prints (and any confirmed sibling's) from the tape features of both the rule and the pure baseline.
     This needs the BUILD tapes again (about an hour through the cached adapter). Recompute the block-second gain and its
     2-hour block-bootstrap CI.
  4. Run a sibling census on a full-market calldata sample, using the mechanical fingerprint: same-ms copies used FIFO,
     1.7 ms per cent loops, the three-burst schedule, the ladder swap.
- **Data.** Polygon logs and calldata (pre-H), the data-api tapes from the shared HTTP cache.
- **Signature if true.**
  - The baseline drops more than the rule, adding +0.005 to +0.01 to the gain and moving the CI's lower bound further
    above 0.05 before the examiner fits its own baseline.
  - Size AUC rises by 0.02-0.05 with W4 in the net.
  - If W4's prints carry nothing, the baseline is clean and the question is settled for the examiner.
