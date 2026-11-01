# Panel, iteration 17: mechanics and on-chain forensics

Reviewer lens: how the orders are built, timed, typed and routed. That covers the pre-signed ladder and its copies, the order type
of each leg, the sibling wallets' public prints, the recorder's own clock, and the salt generator.

Data used. Everything is development data:
- `it16/cdfull_10-2{0,1,2}.parquet`: the complete calldata of 10-20..22, with 72,772 unique operator BUY orders (salt, original size,
  limit, signing ms).
- `it14/dcfit14_pred.parquet`: operator taker orders with server-ms matches.
- `it16/tapes/*`: data-api taker tapes, used for the W4 / W5 legs.
- `it13/hf_dl/*`: capture spot book and trades, for 10-20..22.
- The new-regime record `it17/*`: `post60_17`, `mkx17_orders`, `post17_fills`, `post17_xms`, `post17_cd`, `oot17b_pred`.
- rec_bn15 v2 `btc5m_bnspot2`, read through `live.iter_live`, for 11-01 06:00-09:30 UTC.
- Gamma listings of two development windows (10-22 00:00 and 11-01 07:00), fee fields only.

Nothing sealed was read and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` at 11:04 UTC 11-01 reported "released none;
future examined until 2026-10-31 00:00", with the current block 06-12 in development. Each live read asserts `is_sealed` False at
both ends.

Scripts and small intermediates are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p17m\`:
- `pool.py`, `pool2.py`: ladder copies;
- `fresh.py`: off-burst orders;
- `ladflip.py`, `ladflag.py`: ladder and size;
- `timer.py`: local periodicity;
- `loadlag.py`: knee by load;
- `uclock.py`, `tlag.py`, `stall.py`: the live clock;
- `shadow.py`, `shadow2.py`: XM's 60-share orders;
- `w4S.py`: sibling large prints;
- `grain.py`: salt resolution.

Apart from this file I wrote nothing to the workspace.

## Critique

### 1. The out-of-time side failure is partly the recorder's feed stalls, not only clock drift

Pre-registrations 11 and 11b (0.718 / 0.752) put the cause on a drifting laptop clock. On the same block the laptop's Binance spot
stream also stalls. For 07:00-08:00 UTC (`tlag.py`):
- 4,690 receive gaps over 200 ms in the hour, and 749 over 500 ms. The longest is 29.7 s.
- Trade receive lag minus its trailing-60-s median: q25 -1.8 ms, q50 +7, q75 +88, q95 +621, q99 +1,209 ms. A quarter of the trades
  arrive about 90 ms or more late against the local clock, in bursts.
- Message order is intact: the bookTicker `u` is strictly increasing in receive order (share 1.000). The stamps are wrong; the
  sequence is not.

Scoring the frozen dc14 side again (`oot17b_pred`, local clock), split by the feed's health over the 500 ms before each order's cut
(`stall.py`; max over trades with T in [cut - 500, cut) of the receive-lag deviation):

| feed before the cut | accuracy | n |
|---|---|---|
| clean (<= 20 ms) | **0.780** (DS 0.773, GF 0.804, XM 0.759) | 627 |
| 20-60 ms | 0.788 | 52 |
| 60-150 ms | 0.711 | 83 |
| > 150 ms | 0.673 | 107 |
| no trade in the 500 ms | 0.692 | 130 |

19% of orders sit on a stalled feed. Between the capture's 0.837 and the out-of-time 0.752:
- about 3 points come from the recorder;
- the rest (0.780 on clean feed against 0.837) is a real transfer loss, or Sunday noise (n = 627, ±3.3 points).

The diagnostic "5 points per 25 ms of clock mapping" mixes the two effects. rec_bn15 v2 has a hard stop at 11-01 12:00 UTC, so the
next development block (18-24) has no full-rate spot record unless a recorder is started.

### 2. XM's 60-share orders: the record can tell post-only from always-late

Finding 8 says it cannot. It can, through the operator's own winning legs at the same limit (`shadow.py`, `shadow2.py`; 274 XM
60-share postings, 1,143 operator taker legs of 11-01 06:00-09:30).
- **Coincidence.** 45% of the XM-60 postings have an operator taker leg on the same outcome in [post - 400, post + 100] ms (placebo
  5 s earlier: 4.4%).
- **Offsets.** The offset m_leg - t_post has median -12 ms (q10 -313, q90 +213). The XM-60 posting falls on both sides of the winning
  leg's match.
- **Same limit.** In 72 of the 101 pairs within ±100 ms, the XM-60 limit equals the winning leg's limit. Elsewhere it differs by
  -1 c (12), -2 / -3 c (10) or +1 / +2 c (7).
- **Never takes.** The leg takes at that limit, and XM-60 never does (0 of 274).

A GTC order at the same limit that arrives within tens of ms of a winner would take part of the time. It would take most of the time
when it arrives first. XM's own 30 / 100-share fast followers do take (73 taker fills in the block). So the 60-share class is most
likely post-only, or another order type that never crosses. Its visible postings are then the subset whose arrival found the ask
already gone, and the ones that would have crossed were rejected without a trace.

Caveat: this compares the book channel's posting stamp with the trade server stamp. Redo it on server-stamped `price_change` events
(proposal P3).

Neighbourhood within ±150 ms on the same outcome:

| what is near the XM-60 posting | share |
|---|---|
| nothing | 38% |
| a winning taker leg only | 26% |
| a taker leg and a lost leg | 18% |
| a lost leg only | 18% |

DS's own lost races carry an XM-60 within 150 ms in only 18% (GF 24%). So XM-60 is not a shadow attached to every decision; it is a
leg of its own in the dispatch.

### 3. The sibling wallets' public large prints carry the operator's decision memory

The investigation treats S, the side of the last large order, as private (pre-registration 12: a replica's own memory agrees 0.55).
W4 and W5 carry large legs of the same operator. Their fills are public on chain at block time. On 10-20..22 (`w4S.py`; data-api tapes;
9,455 W4 and 534 W5 taker legs; 13.5% of W4's and 50% of W5's legs are filled at 60 shares or more):

| state at each DS / GF / XM order (W4 / W5 prints usable from block ts + 1 s) | agreement with the operator's S (three wallets) | n |
|---|---|---|
| side of W4 / W5's last LARGE print (filled >= 60) | **0.814** | 37,563 (51% of orders) |
| side of W4 / W5's last SMALL print (control) | 0.427 | 55,298 |
| side of W4 / W5's last print of any size (control) | 0.483 | 56,393 |

**What the controls show.** The small-print control is at or below 0.5. So the agreement is not "recent operator flow follows the
same Binance move". It is the large-order state itself.

**The class relation.** With the dcfit14 `osz >= 90` label (not the complete-calldata classes), P(large) is:
- 0.081 with S_W4 and 0.022 against;
- 0.091 and 0.014 for the true S.

The AUC of the with / against / none relation is 0.627 for S_W4 (DS 0.639, GF 0.625, XM 0.664) and 0.696 for the true S on the same
label. So S_W4 recovers about two thirds of the true state's discrimination above chance, from public prints.

Whether this is admissible is exactly X170. The frozen rule already counts W4 / W5 prints as market activity, so it is consistent
with the current treatment. But it must not be adopted before the examiner's ruling, and it is the strongest reason yet to get that
ruling now.

### 4. Checked and not supported (so nobody redoes them)

- **No per-cent pool cap on large copies** (`pool2.py`). Within (wallet, burst, outcome, cent), two or more large orders are used
  more often than under a within-burst label permutation:
  - DS 50 cells against a null of 34.7 [24, 46];
  - GF 271 against 185 [162, 208];
  - XM 22 against 14 [9, 19].

  P(large) rises after an earlier large order at the same cell (DS 0.117 vs 0.030). This is the clustering of S, not a depleted ladder.
- **No exhaustion fallback** (`fresh.py`). Off-burst (freshly signed) operator orders are 0.35% (DS), 0.15% (GF) and 0.13% (XM).
  Many of them are the 40 / 200 sizes of the 10-20 size phase.
- **No per-ladder large flag** (`ladflag.py`). Ladders with 8 or more orders and no large order sit at the permutation rate:
  - GF 0.043 against 0.029 [0.020, 0.039];
  - DS 0.415 against 0.381 [0.366, 0.395];
  - XM 0.018 against 0.015.

  The variance-to-mean ratios are also at the null (1.85 vs 2.16 for GF).
- **S is not a per-ladder setting** (`ladflip.py`). Large orders inside one (wallet, window, ladder) are on both outcomes in 19.1%
  of cells, against 42.7% under permutation (that is S). But flips mostly happen inside a ladder: P(flip) is 0.249 at a ladder change
  against 0.162 inside one (within a wallet 0.279 vs 0.181), and the ladder-change rate is confounded with the longer gap.
- **No local timer in the decision times** (`timer.py`; 57,630 first-leg matches of 10-20..22, pairwise phase coherence inside 60-s
  blocks, periods 20-300 ms plus 400 / 500 / 1000).
  - The maximum is Z = 2.3 (P = 500 ms), and P = 100 ms gives -0.38.
  - The crowd control shows its known 1-s rhythm (Z 8.8).
  - So the bot runs neither a `setInterval` loop nor a Binance `depth@100ms` snapshot input with timing jitter below about 35 ms.
    The trigger is event-driven.
- **The reaction lag does not depend on load** (`loadlag.py`; 2,467 first legs of 10-21 13:18-15:23, capture book clock).
  - The knee peak is 275-285 ms in every tercile of the Binance book message count (2-115 / 116-306 / 307-1,481 messages in the
    800 ms before) and of the Polymarket trade count.
  - Only the upper half-maximum edge widens at high load (325 to 385 ms).
  - There is no event-loop queueing to correct the clock with.
- **No 32-bit PRNG behind the salts** (`grain.py`; 4,000 salts). r = salt / Date.now() lands on a 2^-k grid at exactly the rate a
  continuous r gives, for k = 24-36 (for example k = 32: 0.0037 vs 0.0024 expected; k = 36: 0.043 vs 0.038). Seeded 32-bit generators
  (mulberry32, sfc32) are excluded. The generator outputs at least about 36 bits, as V8, JavaScriptCore or a CSPRNG would.
- **No listing marker for the regime change.** The Gamma fee fields are identical on 10-22 00:00 and 11-01 07:00:
  - `feeSchedule` {rate 0.07, exponent 1, takerOnly, rebateRate 0.2};
  - `makerRebatesFeeShareBps` 10000, `makerBaseFee` / `takerBaseFee` 1000;
  - `rewardsMinSize` 50, `rewardsMaxSpread` 4.5;
  - `holdingRewardsEnabled` false.

  The configuration switch between 10-22 and 10-31 is not a fee or reward change visible in the listings.

## Proposals (ranked by the chance to close the gap)

### P1. Read the operator's decision memory from the siblings' public large prints (condition 5's size coin; strong form of X170 / X66 / X169, new input)

**Hypothesis.** The size controller's state S is held at the operator level and shared by all five wallets. W4 and W5 carry part of
the large stream. Their fills are public on chain within about 2 s of the match. A replica that updates its S from its own large
draws, and overwrites it whenever a W4 / W5 large print becomes public, stays synchronized with the operator's S far better than its
own memory (0.55). That converts much of "which decisions are large" from a private coin into a public, lagged state.

**Why it fits.**
- Critique 3: S_W4 agrees with S at 0.814, while the small and any-size controls are at 0.43-0.48.
- S_W4's class AUC is about two thirds of the true state's on the same label.
- S locks in within a window (iteration 16: 0.64 at 15 s to 0.88 at 240 s), so a 2-3 s lag costs little.
- Pre-registration 12 showed that the true S / E lifts the window-net r to 0.58 / 0.73. The missing piece was synchronization.

**Test.**
1. **Exact labels.** Rebuild S_W4 on 10-20..22 with exact large labels for W4 / W5.
   - Fetch the calldata of W4 / W5's own taker txs: about 3.2k txs per day, about 2 min per day with cdfull16's batched
     `eth_getTransactionByHash`. This gives the original sizes, not the filled sizes.
   - Make each print usable from block time + 2 s.
   - Report the agreement with the operator's S and the slot x relation AUC table of smach17 step 1, for S_W4 and for the hybrid
     S_hyb (the replica's own draws, overwritten by public W4 / W5 large prints).
2. **Pre-register in the smach17 harness, unchanged except for the state.**
   - Replica: dc14 side; the frozen transition model fit on 10-20; state S_hyb / E_hyb; 300 redraws.
   - Score on 10-21..22 and on the reverse split.
   - Bars: S agreement of 0.75 or more on both splits, and window-net r of at least the menu + 0.05 on both splits.
   - Then feed E[size] into the mix14 tracker and report Pearson / Spearman.
3. **Ask the examiner first (X170).**
   - If W4 / W5 are ruled "the wallet", P1 is void, and their prints must also leave the frozen tape features.
   - If they are ruled "other traders", P1 is admissible, and so is the examiner's use of their prints in its baseline. The
     presence gain was unchanged with and without them (iteration 12, w45chk12), so condition 2 does not lose.
4. **Out of time.** Repeat step 1 on 11-01 06:00-09:30 (W4's P(large) there is 0.206) to check that the shared state survives the
   new configuration.

**Data.** W4 / W5 tapes (on disk), their taker-tx calldata (to fetch), the smach17 frame, and the new-regime record.

**Signature if true.**
- S_hyb agreement of 0.75 or more of legs (S_own was 0.55);
- the class AUC of the replica's P(large) rises from 0.69 / 0.75 to 0.75 / 0.80 or more;
- window-net r of the menu + 0.05 or more on both splits;
- the tracker's Spearman at 0.50 or more.

**If false.** If the agreement is high but the replica's window-net r does not move, the binding term is E (commitment) and the flip
timing, not the side of S. Report the share of the class entropy left after S_hyb as condition 5's wall component.

### P2. A stall-proof Binance clock for the live route: arrival-order brackets, update-id anchors and an isolated recorder (strong form of X167 / X164; condition 3 out of time and every future-block exam)

**Hypothesis.** The live side route loses about 3 points to the recorder's delivery stalls. Message order survives the stalls, so
every book message can be placed on Binance's own clock without the laptop clock.
- **Spot trades.** These carry T.
- **Spot bookTicker.** This carries the update id u. Each bookTicker lies between the T of the last trade received before it and the
  first trade received after it.
- **Spot depth.** A `btcusdt@depth@100ms` subscription gives (E, U, u) anchors every 100 ms on the same update-id sequence.

On clean feed the frozen side is already 0.78-0.80.

**Why it fits.**
- Critique 1: clean 0.780 (GF 0.804) against 0.67-0.71 stalled.
- u is strictly monotone in receive order.
- The capture's collector does not stall (hourly transit 125-140 ms), which is why the capture days score 0.837.
- My first attempt at a u-to-T map from quantity-matched trades (`uclock.py`, 15.6k monotone anchors) has a held-out anchor error of
  q50 25 ms / q90 112 ms. The anchors are too sparse (median spacing 134 ms), which is why the depth stream's 100-ms anchors are
  needed.

**Test.**
1. **On the existing 11-01 record.** Re-stamp every spot bookTicker by its arrival-order bracket [T_prev, T_next], taking the midpoint
   when the bracket is under 40 ms. Score dc_exam14 once with the brackets in place of the trailing-median offset, with no refit.
   Report clean / stalled per wallet and the share of cuts with a bracket over 40 ms.
2. **Recorder fix before 11-01 18:00 UTC.** rec_bn15 v2 stops at 12:00.
   - A dedicated process for Binance spot `@bookTicker` + `@trade` + `@depth@100ms`.
   - A monotonic `perf_counter_ns` stamp next to the wall clock.
   - No compression in the receive coroutine.
   - A logged event-loop lag probe.
   - A read-only `w32tm /query /status` every 10 min, to separate system-clock steps from delivery stalls.
3. **Pre-register now.** dc_exam14 with the depth-anchored clock on the next development blocks (11-01 18-24, 11-02 00-06 /
   12-18). Bar 0.80 per order pooled, reported with clean / stalled. Add a feed-health guard: a cut counts as covered only when its
   bracket is under 40 ms. Report the guard's coverage, and fall back to the trailing-median clock when it is not met.

**Data.** rec_bn15 v2 (11-01 06-12), a restarted recorder for the next blocks, and the `oot17` / `oot17b` harness.

**Signature if true.**
- step 1 lifts the stalled subset toward the clean 0.78;
- on the next blocks the stalled share is under 5%, and the pre-registered side is 0.80 or more pooled with GF / DS within 3 points;
- the "5 points per 25 ms" sensitivity shrinks, because no cut sits inside a stall.

**If false.** If clean-feed orders stay near 0.78 on weekday blocks, the out-of-time loss is real model transfer. The next step is
then the per-wallet knee (DS 255 vs GF 285 ms) as a per-wallet cut, not the clock.

### P3. XM's 60-share class is post-only: prove it on the recorded book, then replicate XM's resting stream (strong form of X177; condition 7 in the new regime)

**Hypothesis.**
- In the new configuration, the dispatcher sends some XM legs as 60-share post-only BUYs at the limit of the decision (the ask the
  bot saw).
- Those that would cross are rejected and leave no trace.
- Those that arrive after the makers pulled rest at L and fill on the way back.

XM's new-regime PnL is that resting stream (finding 3: 92% maker fills). Its survival and fills are deterministic given the public
book and the decision. A replica can then reproduce it once the XM-60 routing rule is known.

**Why it fits.**
- Critique 2: there are 72 same-limit pairs with a winning operator leg within ±100 ms, and 0 of 274 XM-60 orders take, while XM's
  30 / 100-share orders do take.
- The limit is the ask at the view in 63% (finding 8).
- 38% of postings have no other operator leg nearby, so the class is a dispatch slot, not a shadow of every decision.

**Test.**
1. **Server stamps.** Redo critique 2 on server-stamped book events: the unthrottled channel's `price_change` server timestamp, not
   the receive time. Report the offset distribution of t_post - m_leg for same-limit pairs.
2. **GTC counterfactual.** On the recorded event-level book, insert each XM-60 as a GTC order arriving at t_post - 150 ms (the hold;
   race11's machinery: the race is deterministic given the arrival).
   - Count the predicted taker fills. Under GTC with XM's arrival times, the expectation is far above 0. Post-only predicts exactly 0.
   - Report both, together with the binomial probability of 0 / 274 under GTC.
3. **Routing rule.**
   - Among decisions of the new record (taker first legs plus DS / GF lost-race postings, grouped within 300 ms), fit
     P(XM-60 | decision features) on 06:00-08:00 and score on 08:00-09:30. Features: slot occupancy, W4 / W5 legs in the last
     300 ms, time in window, knee strength, and the ask move during the hold.
   - Then simulate the post-only survival on the book for every decision the rule selects.
4. **XM tracker.** Pre-register it: survivors rest at L until the end of the window (check XM-60 cancels in the book first), and are
   filled by complement BUY prints at 1 - L or more. Score XM's per-window maker PnL r on the next development block, separately from
   pre-registration 14's pooled remainder stream (which was adversely selected).

**Data.** The new-regime record (it17), the unthrottled channel with server stamps, the event-level book of 11-01 06-12, and the
next blocks.

**Signature if true.**
- The GTC counterfactual predicts 30% or more taker fills against 0 observed (p < 1e-6).
- The routing rule names XM-60 legs at AUC 0.75 or more out of time.
- The XM-60 tracker's per-window r is 0.5 or more against XM's maker PnL with the true postings (oracle), and 0.40 or more with the
  public routing.

**If false.** If GTC also predicts about 0 (XM-60 always behind the depth), the class is "always late". Then XM's stream is bounded
by its arrival offsets, and the route is the per-wallet knee (P2's fallback).

### P4. If the salt generator is recovered, count its draws between bursts (payoff form of X149; lower priority)

**Hypothesis.** The size, carrier and take coins are Math.random draws in the process that makes the salts. The generator's state at
two consecutive bursts of one wallet then fixes the number of draws between them. That number counts every coin drawn between the
bursts, including the coins of instants the bot evaluated and skipped. It would be a direct measurement of the take coin's
denominator.

**Why it fits.**
- 32-bit seeded generators are now excluded (critique 4), and V8 is excluded (prng15 / prng16).
- The salts carry about 40 bits of each output.
- JavaScriptCore's xorshift128+ (Bun) outputs the low 53 bits of a sum, which a carry-aware SMT model can invert from 4-6 consecutive
  outputs.

**Test.**
1. **Solver self-test.** Generate synthetic salts with JSC's `WeakRandom` (output (x + y) & (2^53 - 1), double = value / 2^53) under
   the three layouts prng16 used. Check that the solver recovers them.
2. **Real data.** Run the solver on the 130 same-ms copy groups.
3. **If one solves.** Step the generator forward from burst k's state to burst k + 1's first salt. Report the jump length against
   the count of top-hazard instants and of decisions in between.

**Data.** The complete calldata salts (on disk); a solver installed in a scratch venv from PyPI (z3-solver).

**Signature if true.**
- held-out salts predicted exactly;
- a jump length per inter-burst interval that rises with the window's hazard mass.

**If false.** If 0 / 130 groups solve under JSC as well, close X149 as a CSPRNG (`crypto.getRandomValues`) and record the take /
size coins as unrecoverable from the salts.
