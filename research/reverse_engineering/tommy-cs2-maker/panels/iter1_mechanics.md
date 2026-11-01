# Panel, iteration 1: mechanics and on-chain forensics (fresh eyes)

Reviewer lens: how the orders are built (V2 calldata, signing ms, FAK vs resting, child orders, complement pairs,
latency fingerprints). I read BRIEF.md, NOTES.md, state.json, FINAL_RULE.md and the results/*.json files, and ran
small read-only checks on `.cache/re/tommy-cs2-maker/{orders.parquet, orders_inv.parquet, calldata_all.parquet,
calldata_pub/}`. All the checks below pool BUILD and VALIDATE (development data before H only). They are
exploratory, not VALIDATE results. Nothing sealed was read.

## Critique: what the investigation is missing or getting wrong

1. **There is one engine, not two components.** Its filled maker orders signed in [+1.0, +2.0) s after its own
   taker signing run at 29x the control rate on the *opposite* token (734 orders) and 9.7x on the same token
   (267). Controls are the same markets at +-15 min. The rate is still 3-7x at +2..+5 s. Within +-0.5 s of the
   taker signing there is no spike: 25 orders vs 20 in the control. So the maker side reacts to the **match** of
   its own taker order (sign + the 1-s in-play delay), not to the decision itself. The ladder is driven by its
   own fills. Treating "maker component" and "taker component" as independent processes hides this.
2. **The time base is wrong for own state.** Own inventory (`orders_inv.own_net`) and "after a fill" are computed
   from fills with *block* time < signing time. But the bot learns of a fill at the off-chain match: about
   taker sign + 1 s (`secondsDelay` = 1). That is 1.4-8.7 s before the block (block minus taker sign: p5 2.44 s,
   p50 3.93 s, p95 9.68 s). Every child order the bot signs in that gap is attributed to the wrong state. Use
   `taker sign_ms + 1000` from the same transaction's calldata as the match clock. 98.5% of the wallet's fill
   rows have a valid taker sign time. With that clock, 1,854 maker orders are signed 0-250 ms after an own fill,
   vs 558 at 250-500 ms.
3. **The "~30 s before the round end" claim is not established by the test used.** `next_jump.py` cannot see a
   jump that ends less than 10 s after the order (`bt - 15 >= t - 5`). By bin of time-to-jump:
   - jumps ending 10-20 s after the order go its way 77-80% (n = 568), against a control of 51-55%;
   - jumps at 20-60 s are noisy, 0.49-0.71;
   - jumps after 60 s are near the control.

   The information concerns something that just happened, or happens within about 20 s. That also covers the
   pack's own price impact. "It predicts the round in progress 30 s early" is one reading. "It reacts at once
   to a round-level event (round end, or bomb plant), and the tape catches up over 10-20 s" fits the same
   numbers. These two readings need different feeds and give different rules.
4. **The pack is the best event clock you have, and it is treated as a confound.** Signing-ms offsets of same-team
   taker orders relative to its own taker orders, within +-3 s:

   | wallet | n | q10 | q25 | q50 | q75 | q90 |
   | --- | --- | --- | --- | --- | --- | --- |
   | 0x4ebc2722 | 265 | -0.204 | -0.074 | **-0.051** | -0.022 | +0.205 |
   | 0x72aaaaf9 | 291 | 0.376 | 0.410 | 0.478 | 0.686 | 1.156 |
   | 0xfe8a28be | 276 | 0.355 | 0.402 | 0.475 | 0.656 | 1.158 |
   | 0x2529c68d | 271 | 0.344 | 0.404 | 0.477 | 0.662 | 1.172 |
   | 0x8a80528d | 72 | (-0.686) | 0.116 | 0.159 | 0.261 | 1.406 |
   | 0xddb6e624 | 63 | (-0.569) | 0.122 | 0.159 | 0.344 | 1.471 |

   - The offsets are tight, with an IQR of 50-300 ms. That is the signature of a pushed, timestamped event. A
     video stream would scatter the offsets by seconds.
   - 0x4ebc2722 signs about 51 ms **before** the wallet. So the wallet is not the leader. The RE's "first of the
     burst in 41%" counts takers that were already public, so it misses this.
   - Three wallets have identical quantiles. They are one operator with one latency path.
   - 0x4ebc2722 placed 3,044 in-play taker orders in the wallet's markets: a median of 51.5 events per match,
     about 24 events per hour, with a median gap of 75 s. That is **about one event per round**. The wallet fires
     on only about 7% of 0x4ebc2722's events.
   - So the trigger is round-level, not kill-level. The wallet's decision is a filter on a shared event stream.
5. **Taker orders are FAK, and their fill fraction carries information.**
   - Every taker order has exactly one fill transaction, and no taker order hash ever rests or fills later as a
     maker (0 of 25,878 orders have both roles).
   - The limit equals the worst matched price in 67% of orders (`limit - worst matched` = 0).
   - Odd-size orders fill bimodally: p25 3.6%, p50 15%, p75 93.5%. Fixed 1000/2000 orders fill p50 5%, p75 20%.
   - The "12% filled" figure is not a design choice. It measures how much ask depth survived the 1-s delay,
     that is, how many makers saw the same event and cancelled in time.
6. **Censoring.** Burst sizes, the 2% two-sided bursts, "ladders of 2-9 levels" and the 0.97 bid sum all come
   from *filled* orders only. They are not the ladder. The presence target (fills per 30-s bin) is
   co-occurrence by construction for a maker. Two units can beat the activity baseline:
   - order *signings*, which are decisions, linked to own fills and to round events;
   - resting orders seen in the live books, as the brief's "or better, whether it has an order resting".

## Proposals (ranked by the chance that they close the gap)

### 1. Round-level event sniping through the 1-s in-play delay; identify the event and the feed with the pack's latency clock

- **Hypothesis.** Its taker orders react to a round-level event that a push feed broadcasts, possibly a feed the
  public can reach.
  - The event is round end (the score change), bomb plant, or another per-round message.
  - The wallet and the pack consume the same feed: 0x4ebc2722 about 51 ms earlier, the 3-wallet operator about
    475 ms later.
  - FAK at ask + 1c takes whatever stale asks survive the delay.
  - The rule is: on event e, buy team X with FAK if the ask on X is below V(state after e) - margin. Here V is a
    round-score (or post-plant) value.
- **Why it fits.**
  - Offsets are tight and in the order of a push feed (critique 4).
  - 0x4ebc2722 fires about once per round.
  - The information is concentrated in jumps 10-20 s out (77-80%).
  - FAK fill fractions are bimodal, which looks like a race with cancelling makers.
  - The 5-s markout is about 0 while the 30-300 s markouts are positive, so it is not a prediction of a far
    event.
- **Tests.**
  - (a) **Dev data, now.** Build the event list from 0x4ebc2722's in-play taker orders. Cluster its orders across
    the match and map markets of one event within 3 s, which gives about one event per round. Each event carries
    the team bought and the first signing ms. Sequence-align these per-map event sequences to the bo3.gg round
    sequences (winner, winner side, end_reason, bomb fields, equipment). Use Needleman-Wunsch on the winner
    sequence; it is far easier than aligning to 4c jumps (13 of 109 maps). Then, for the wallet's 1,698 orders,
    read off the round, and measure:
    - P(bought team = winner of the round that just ended);
    - P(bought team = T side);
    - P(bought team = winner of the round in progress);
    - events per round.

    This also gives the wall clock for bo3 rounds that the RE lacked.
  - (b) **Live lab, development blocks** (10-31 12-18 UTC now, then 11-01 06-12 and 18-24). The wallet does not
    need to trade. For every CS2 match in which 0x4ebc2722 or the three-wallet cluster trades in-play:
    - decode the calldata of their taker txs (signing ms);
    - compare with the `sports` receive time of each score change (`6-3|0-0|Bo3`, period).

    The cluster trades far more widely than the wallet, so this works even if the wallet trades nothing in a
    development block.
- **Data.** `calldata_pub` (on disk). bo3.gg rounds for all BUILD and VALIDATE maps (only 20-22 Oct are fetched).
  Live `sports` recordings plus Polygon calldata of the cluster's development-block txs (publicnode batches
  of 40).
- **Signature if true.**
  - Round end: in (a), bought team = winner of the round just ended in at least 85-90% of aligned events, and
    events per round close to 1 (bomb plant would show T side well above 50% with a 65-70% round win rate
    instead). In (b), sign minus score-change receive time is a constant with an IQR below 300 ms. A negative
    constant means their feed is upstream of the Polymarket socket (GRID or a scorebot); a positive one means it
    is the socket itself.
  - Then the taker presence (P(order in the 2 s after a score change)) is driven by a non-market feed. It should
    beat the activity baseline by far more than 0.05, and it gives an executable, point-in-time rule.
  - If instead the pack signs 5-40 s before score changes, the input is in-round (kills or plant), and the
    wallet's 7% filter must be decoded against bo3 in-round state at the aligned clock.

### 2. Fill-triggered child-order quote function (strong form of B2/B3 with own state, on the match clock)

- **Hypothesis.** Each maker order is a child of an own match event: the wallet's maker or taker fill, at
  `taker sign + 1 s`.
  - It replenishes the filled token at the same price (or +1c), in 100 shares.
  - It bids the complement at K(inventory) - p_fill.
  - It extends the ladder at -1c steps.

  The quote is anchored to its own last fill, not to the last print or a fair value. The 10-share and 11-99-share
  orders are pair-completion remainders.
- **Why it fits.**
  - 1,854 maker orders are signed 0-250 ms after an own match (3.3x the next 250 ms).
  - Among orders signed within 2 s after an own fill:
    - on the same token, price - fill price is 0.00 in 32.8% and +0.01 in 15.2% (vs 11-12% when more than 10 s
      later);
    - on the complement, price + fill price is 0.99 / 0.98 / 0.95 / 0.96 / 0.97 in 16 / 15 / 12 / 11 / 11%.
  - After own *taker* fills, 67% of child orders are on the complement; after own maker fills, 33%.
  - The last-print anchor is exact for only 11.5% of orders.
- **Test.**
  - Re-time every wallet fill by the match clock.
  - Fit on BUILD a small deterministic table: parent type (maker or taker fill, same or complement token) x
    inventory-imbalance bucket -> child price offset, size and number of levels.
  - On VALIDATE, score `price_within_tick` over all maker orders. Report it with own state, and against the
    last-print anchor and a touch reconstructed from all makers' matched orders in the previous 2 s.
  - Strong form of the RE's timing cross-correlogram: split the +0.5..1.0 s peak after public taker signings by
    whether that taker order matched the wallet, matched only other makers, or was killed. A user-channel
    (own-fill) trigger shows the peak only after its own matches. A market-channel trigger shows it after all of
    them.
- **Data.** `calldata_all.parquet` and `calldata_pub/` (on disk).
- **Signature if true.**
  - Price within tick of at least 0.5 overall, and at least 0.7 for orders signed within 2 s of an own match.
  - The +1 s peak exists only after its own matches.
  - The 11-99 sizes equal the paired deficit on the match clock (they do not on block time: `held_*` matches
    <1%).

### 3. Take-then-make: the profit unit is the pair (informed FAK leg plus a delayed-pack re-pair leg)

- **Hypothesis.** After its FAK buy of X, it posts 100-share bids on Y within 1-2 s at about 0.95 - p_X. Through
  MINT matching these are asks on X 4-6c above its entry, and the pack's *delayed* X buys hit them. Each event
  is then a near-locked round trip plus an unpaired remainder. The "adversely selected maker fills" (42% in
  favour) partly *are* these re-pair legs: they sit on the losing team by construction.
- **Why it fits.**
  - 853 re-pair orders follow taker orders by 0.5-3 s. Price_Y + limit_X has median 0.95 (IQR 0.93-0.96).
  - 1,412 re-pair fills: 87% are mints (the counterparty bought X); 26% come from the pack, vs 12% of all its
    maker fills.
  - At least 25% of re-pair fills come from takers who signed 0.38-0.73 s *after* the wallet's own taker order:
    the delayed pack, matched against bids that did not exist when they signed.
  - The fill delay is p25 3.4 s and p50 14.9 s. Re-paired shares are 62k of 312k taker shares filled.
- **Test.**
  - Link each child to its parent taker order (match clock).
  - Compute PnL per pair unit (taker leg + children until the parent's shares are paired or the map ends, merges
    at 1.00, the residual at settlement, net of the taker fee and rebates).
  - Run an event bootstrap per split.
  - Compare with the per-leg accounting in FINAL_RULE (taker +6% p 0.16-0.21; maker +0.47%).
  - Replay the pair unit against the public tape as the executable rule for `pnl_corr_*`.
- **Data.** On disk (orders, calldata_all, calldata_pub, inventory merges).
- **Signature if true.**
  - The pair-unit PnL is significant per split (lower bound > 0) where the leg PnL is not.
  - The locked margin is a stable 4-6c.
  - The re-pair fill delay is bimodal (2-4 s pack, and later).
  - The replayed pair rule's per-market PnL correlates with the wallet's.

### 4. Selection and size from stale depth: it trades the leagues where makers do not cancel within the delay

- **Hypothesis.**
  - Odd taker sizes equal the visible ask depth up to the limit at decision time ("sweep what you see"). The
    fixed 1000/2000 sizes are caps.
  - Fill fraction = the depth that survived the 1-s delay.
  - The league whitelist is the set of leagues where post-event stale depth (the profit of event sniping) was
    high on earlier days. That is a market-microstructure property that pre-game activity does not measure.
- **Why it fits.**
  - The bimodal fill of odd sizes (critique 5).
  - Its size is not the matched depth: |size - sum of matched originals| < 1 in only 0.9%, ratio median 5.2. That
    points to depth that vanished between signing and matching.
  - The league whitelist does not follow time of day (CCT 0/59 inside 09-19 UTC).
- **Test.**
  - (a) Live books (`clob_wallets`): odd size vs cumulative ask depth up to the limit in the last snapshot before
    the signing ms.
  - (b) Dev data: from the data-api taker tapes of *untraded* markets (CCT, ESEA, ESL Challenger), measure the
    pack's (0x4ebc2722 and the cluster) per-event fill fraction and 30-s markout by league.
  - Build a point-in-time league score from the previous days' "stale-depth profit at round events". Test it as
    a selection score against the activity baseline (gain >= 0.05?).
- **Data.** Tapes of untraded markets (fetched by `fetch_tapes.py`), calldata of the pack's txs in those markets
  (new fetch, about 10-20k txs), live books.
- **Signature if true.**
  - |odd size - visible depth| < 1 share in most odd orders.
  - The pack's event profit is high in its leagues and about 0 in CCT and ESEA.
  - The league stale-depth score predicts selection beyond activity (combined AUC gain >= 0.05 with a positive
    lower bound).

### 5. Operator clustering by latency fingerprint, and owner recovery (strong form of C1/C7)

- **Hypothesis.** Wallets with identical signing-offset distributions are one operator:
  - 0x72aaaaf9, 0xfe8a28be and 0x2529c68d (sigType 1);
  - 0x8a80528d and 0xddb6e624.

  0x4ebc2722 may be the wallet's own sibling: sigType 3 like the wallet, it signs 51 ms earlier with an IQR of
  52 ms, and it is the wallet's top maker counterparty (1,027 txs). In that case the wallet's taker orders are a
  second wallet's share of one signal, routed by per-wallet caps, balances or resting ladders. Decoding "which 7%
  of events it fires on" is then a router rule.
- **Test.**
  - (a) Recover the owner EOA behind the sigType-3 signatures (ERC-1271 wrapper: ecrecover of the inner ECDSA
    signature over the EIP-712 order hash, or the deposit-wallet contract's owner) for the wallet and
    0x4ebc2722. Repeat for the clusters.
  - (b) Map the USDC funding and withdrawal graph of the proxies (Polygon `Transfer` logs).
  - (c) On joint events: are the sizes complementary (the wallet's size + 0x4ebc2722's size close to a constant
    cap)? Does the wallet fire mainly when 0x4ebc2722 is capped or absent in that market?
  - (d) Do the wallet's maker fills against 0x4ebc2722 happen at 0x4ebc2722's events, that is, does it pick off
    its own sibling?
- **Data.** On-chain only (calldata on disk; signatures need the raw `signature` bytes, which `fetch_calldata.py`
  dropped and must re-fetch for a sample of about 200 txs).
- **Signature if true.** The same owner or funder, complementary sizing, and the wallet firing when 0x4ebc2722 is
  absent or capped. Then the selection and timing rule should be decoded jointly over the family, and the
  examiner's scope must include the sibling. If false, 0x4ebc2722 is simply the fastest consumer of the same
  feed, which still makes it the event clock for proposal 1.

## How to reproduce my quick numbers

- **Match clock.** For each wallet fill row in `calldata_all`, `mt = sign_ms of the idx == -1 row of the same tx + 1000`.
- **Child spike.** For each taker order, take its filled maker orders signed in bins from -30 to +30 s, split
  same and opposite token. The control is 5 random shifts of +-900 s per order in the same market.
- **Pack offsets.** Use public taker rows (`idx == -1`) of `calldata_pub` on the same market and team (BUY of
  token oi, or SELL of the complement) within +-3 s.
- **0x4ebc2722 events.** Take its in-play taker orders, cluster them within 3 s per event slug, and count events
  per event slug and per hour of span.
- **Next-jump bins.** Same code as `next_jump.py`, with a histogram of `dt` by bin.
