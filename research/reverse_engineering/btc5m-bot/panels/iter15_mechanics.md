# Panel, iteration 15: mechanics and on-chain forensics

Reviewer lens: how an order becomes a fill. That covers the pre-signed cell the bot submits, the 150-ms hold, the book the order
meets when the hold ends, the remainder, the original size, and which wallet carries the leg.

Data used. Everything is development data from before H:
- `it15/depth15_orders.parquet`: 73,577 operator taker orders of 10-20..22; calldata limits and original sizes for 3,718 of them.
- `it15/l2ordb_2026-10-20`: o's ask vector at 16 offsets m - 1 .. m - 500 for 27,008 orders.
- `.cache/re/btc5m-bot/calldata_sample.parquet`: the 11 sample hours.
- `.cache/re/btc5m-bot/fills.parquet`: 794 windows of 10-20..22.

Nothing sealed was read and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` at 07:23 UTC 11-01 reported "released
none; future examined until 2026-10-31 00:00".

My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p15m\`:
- `posthold.py` and `posthold2.py`: execution on the post-hold book;
- `ownrem.py` and `ownrem2.py`: own resting orders in the cancel wave;
- `origdepth.py` and `origwave.py`: original size against depth;
- `stock.py`: pre-signed cell usage;
- `disp.py`, `slots.py`, `gap.py`, `budget.py` and `slotoracle.py`: dispatch.

Apart from this file I wrote nothing to the workspace.

## Critique

### 1. The condition-5 account calls the makers' cancel race unexplained. It is execution, and the public book records it.

Finding 2 shows that the depth at or below L collapses during the hold and that a depth-bound order fills what is left. It then
measures how well public data at the decision predicts the fill (r 0.29) and books "~0.3 of condition 5 on the true decisions" to
the cancel race. A strict-fill executable rule does not have to predict its fill. It executes against the book its order meets
when the hold ends, and the capture records that book.

I checked this on 10-20 with `posthold2.py`: 929 calldata taker orders, 126 of them large. D(t) is o's ask depth at or below L at
time t.

| model of the realized taker fill | r | within 10% |
|---|---|---|
| original size alone | 0.401 | |
| D(m - 35) alone | 0.422 | |
| min(orig, D(m - 180)), the bot's view | 0.500 | 52.9% |
| **min(orig, D(m - 35)), the book the order meets** | **0.876** (R² 0.77) | **84.5%** |
| the same, large orders only | 0.863 (vs 0.364 at the view) | |
| the same per wallet | DS 0.85, GF 0.90, XM 0.83 (vs 0.58 / 0.47 / 0.46 at the view) | |

The last row of the table holds for all three wallets.

The result is sensitive to the arrival time. At m - x the fit is:
- 0.728 at x = 20, which is the match itself;
- 0.876 at 35;
- 0.837 at 50;
- 0.750 at 75;
- 0.666 at 100;
- 0.551 at 150.

So, given the original size, the realized fill is close to a deterministic identity on public post-decision data:
fill = min(original, the depth left ~35 ms before the match on the book clock).

What the size still leaves unexplained is the original size, not the cancel race. At the window level the menu blur dominates:
with E[menu] in place of the original size, the window taker net on 10-20 (265 windows, true side) has r 0.537 with the menu
alone, 0.573 with the view depth and 0.592 with the post-hold depth.

The ~0.3 of r that the wall account gives to "maker cancellations" should therefore move to "execution, which a replay can
simulate". The binding terms then become the original-size decision and decision overlap. X145 step 1 was written as "minus
cancels at L seen in the capture inside the hold", but no replica has been run with that execution model.

### 2. Get a ruling on the latency convention now

Condition 5 asks for "strict fills, not an expectation". The ≥ 2 s latency in the brief belongs to the held-out return. The
iteration-7 pre-registration counts convention (b), the decoded latency, only if the examiner accepts it.

Every decision-level replica so far was built either at ≥ 2 s or on block-second decisions, and reached 0.13-0.18. With the
knee-clock hazard (AUC 0.88-0.90 on 50-ms bins) and the capture's L2 book, a decision replica at the decoded latency can be built
for the first time. Ask the examiner about (b) before building it: the answer decides whether condition 5 is a tracker problem or a
replica problem.

### 3. Condition 7's 0.03 tolerance looks unevenly applied

Condition 7 asks every threshold in conditions 2-5 to hold "within 0.03 (AUC, correlation)" on each half and for each wallet. The
investigation uses 0.47 (0.5 - 0.03) for XM's PnL. For XM's presence gain, though, it applies the full 0.05: "fails for XM even
under the PIT cut", at +0.030.

Read the same way, the per-wallet gain bar is 0.02, and XM's +0.030 at the e cut passes. Get the examiner's reading before
spending more on XM's presence part.

### 4. Checked and not supported (so nobody redoes them)

**a. The operator's own resting orders are not the cancel wave.**
- Why it was worth checking: the operator's BUY remainders on the other outcome sit in o's ask book at 1 - L', because the
  outcomes are mirrored. hazbook15's own-print check removed the operator's matches, but not its resting orders or cancels.
- Test (`ownrem2.py`, 10-20, 27,008 orders): take the earlier operator orders on the other outcome in [m - 2 s, m - 150].
  Compare levels of earlier orders that probably left a remainder (taker fill not 30 or 100) with levels of fully filled
  orders, which sit at the same distance from the touch but leave no own resting order.
- Result:
  - Remainder levels carry 7.69% of the hold decrement at or below L (decrement / size 0.737).
  - Full-fill levels carry 6.87% (0.700).
  - At single own-remainder levels, the median decrement is 0 against an implied remainder of 20, and only 3.3% match within one
    share.
  - Own resting orders account for about one point of the wave at most.
  - A naive ±2 c placebo gives 14.0% vs 5.7% (`ownrem.py`), but distance from the touch biases it.

**b. Wallet slots are real, but they do not decide XM.**
- The slot structure (`slots.py`, `gap.py`):
  - When DS matched within the last 200 ms, the next operator leg is GF 93.1% of the time.
  - When both DS and GF did, it is XM 63.3%, against XM 5.0% when no slot is busy.
  - A slot frees about 300 ms after its match. After a DS leg, a gap of 200-300 ms gives GF 75.8%; a gap of 300-400 ms gives DS
    76.8%.
- What it leaves out:
  - 68% of XM's legs come with no visible busy slot.
  - A deterministic DS > GF > XM rule recalls only 10-17% of XM's legs.
  - Its oracle XM window taker net correlates 0.26-0.29 with XM's, no better than base rates (0.29) (`slotoracle.py`).
- Two other dispatchers are weak as well:
  - per-wallet rate budgets or load-balancing counters: XM-vs-rest AUC 0.53-0.58 on own counts over 2-60 s and on XM's recent
    share (`budget.py`);
  - copy exhaustion of the pre-signed cells: uses per (wallet, burst, token, cent) fall off geometrically (DS 3,999 / 978 / 276 /
    91 / 14 / 3 for 1-6 uses) with no pile-up at a cap (`stock.py`).

### 5. The large original size does not follow visible depth in the "size = depth" direction

Within (wallet, arm), the AUC of D at the view for a large original size is:
- DS 0.33 / 0.37;
- GF 0.49;
- XM 0.43 / 0.46.

Within price bands, DS is at 0.30-0.44, so large orders go into thin visible depth. On 10-20:
- the depth 500 ms earlier gives AUC 0.716;
- the wave state D(m - 180) / D(m - 500) gives 0.616.

Large orders come when makers are already pulling a deep book (`origdepth.py`, `origwave.py`). The samples are small: 126 large
orders on 10-20 and 3,718 calldata orders over three days. The size has only ever been decoded from 11 sample hours, about 5% of
the orders on the capture days.

The maker role is secondary for the window net. On 10-20..22 the taker net has r 0.918 with N (0.70 of its variance) and the maker
net 0.578 (0.17). The remainder process still matters for XM, whose maker shares are 26% of its total.

## Proposals (ranked by the chance to close the gap)

### 1. Execute on the post-hold book: a closed-loop decision replica at the decoded latency (strong form of X145 / X93 / X36 / X133; corrects the condition-5 account of finding 2)

**Hypothesis.** The window net is the sum over decisions of min(original size, the depth at or below L that survives the hold),
plus the remainder's maker fills. The fill is execution, and the public book records it.

A replica that decides from point-in-time inputs and executes on the capture's L2 at its own arrival + 150 ms gets the operator's
fills wherever its decisions overlap the operator's. Its own realized net then feeds its own size rule (pyramiding) without any
oracle state.

**Why it fits.**
- Critique 1: 0.876 against 0.500.
- The tracker's net follows its target at 0.993, so the tracker cannot gain from execution.
- Decision replicas have only failed on block seconds (0.13-0.18). None has been run on the knee clock with an execution model.
- In the iteration-14 mechanics oracle, a size lookup on the realized own net gave r(N) 0.601 against 0.401 for the sent position.
  That realized net is now something a replica can simulate.

**Test.**
1. **Execution model.** Run `posthold2` on every calldata order of 10-20..22 (the `l2ingest15b` offsets for 10-21 and 10-22, about
   12 minutes a day), per wallet and per day half. Pre-register the model:
   - book clock = trade clock - 25 ms;
   - the order meets the book at arrival + 150 - 35 ms;
   - fill = min(size, D at or below L), minus the replica's own earlier consumption at those levels inside the same hold;
   - the remainder rests at L behind the visible queue at insertion, fills from recorded crowd SELLs of o at or below L and BUYs
     of the other outcome at 1 - L or above (the M stream, X133), and is cancelled by the pooled TTL Weibull (rem10).
2. **Ceiling on the true decision times.** This step is an oracle for the decisions only:
   - side: dc14;
   - size: a frozen rule on the replica's own simulated realized net, P(large | wallet, arm, own net bin on o and the other
     outcome, |knee move|), fitted on the calldata hours of 10-17..20;
   - execution as in step 1.

   Report r(N), the PnL r, and the split between the true original size and the modelled size.
3. **The replica.**
   - Decisions: frozen dc_hazard14 bins above a threshold fixed on 10-20, so that the decision rate matches the operator's first
     legs plus lost races.
   - Arrival: e + 105 ms on the trade clock.
   - Limit: the ask at the view + k.
   - Dispatcher: the first free slot in DS > GF > XM with a 300-ms slot (critique 4b), otherwise base-rate weights.
   - Execution: as in step 1, on a 10-ms L2 grid.

   Score it once on 10-21..22, and on the reverse split. Report window PnL against the cluster's and per wallet under convention
   (b), with (a) alongside.
4. **Exam path.** The shared recorder's `clob_crypto` writes the top 10 levels at most every 200 ms per token, and `btc5m_xclob*`
   records touch changes only. Neither can run this execution model. Before the next sealed blocks, add a full-rate recorder of
   Polymarket L2 level sizes (best + 0..4 c, every `price_change` with server ms) through the Writer. Also check that the capture
   has day files for h1, using the listing only.

**Data.** The capture's L2 (`l2ingest15` at a 10-ms grid for the replica's bins), the capture trades for the M stream, the calldata
sample, `fills.parquet` and the frozen models.

**Signature if true.**
- Step 1: r of 0.85 or more on all three days and for every wallet.
- Step 2: window-net r of 0.70 or more with the modelled size.
- Step 3: pooled PnL r of 0.55 / 0.55 or more, both halves within 0.03, beating mix14 (0.507 / 0.467).

**If false.**
- If step 2 is below 0.6, the original size is the binding term (proposal 2).
- If step 3 falls far below step 2, decision overlap is binding, measured as the replica's precision at the operator's rate.
- Either way, these numbers replace the "cancel race ~0.3" line in the wall account.

### 2. The complete decision record: calldata of every operator taker tx on the capture days, and the original-size decision decoded on it (strong form of X132 / X49 / X64 / X51)

**Hypothesis.** The original size (30 or 100) is close to a deterministic function of state the bot holds at the decision:
- its sent position (the sum of original sizes, which the bot knows exactly);
- the arm and phase;
- the move strength and the state of the cancel wave.

It has been measured badly so far because only 11 sample hours carry original sizes and the sent state was approximated by realized
nets.

**Why it fits.**
- Critique 1: the original size alone has R² 0.16, and 0.77 together with the post-hold depth. Once execution is simulated, the
  original size is what remains.
- Critique 5: large orders go into thin visible depth and when makers are pulling a deep book.
- X49: own net reaches AUC 0.75 for GF.
- size9: tick strength reaches AUC 0.62-0.81.

**Test.**
1. Fetch the calldata of every operator taker tx of 10-20..22 with `eth_getTransactionByHash`, 25 calls per POST and at most 3 POSTs
   per second. Iteration 1 fetched 17,709 txs in 475 s, so the ~74k txs take about 35 minutes. Then do 10-17..19 together with
   their L2 ingest. Keep only the decoded fields (salt, sign_ms, maker_amt, taker_amt, token, wallet), about 10 MB of parquet.
2. Build these features:
   - sent position on o and on the other outcome, and the realized net;
   - leg rank, and the gap since the wallet's own last order (own state, reported as such);
   - arm and phase;
   - |knee move|;
   - D at the view, D(m - 500) and D(m - 180) / D(m - 500);
   - p and the time in the window.
3. Fit on 10-17..20 and score once on 10-21..22, with and without own state, per wallet. Distill the result into a tree of depth 3
   or less.

The full record also yields every surviving maker's order struct in the operator's taker txs: address, sign_ms (the quote's age)
and original size. That shows which makers survive the hold (X51, X90).

**Signature if true.**
- Within-wallet AUC for the large size of 0.80 or more with own sent state, and 0.70 or more without, stable on both halves.
- A depth-3 rule that reproduces at least 85% of the size classes.
- In proposal 1 step 2, the modelled size closes at least two thirds of the gap between E[menu] and the true original size.

**If false.** The size is a configuration coin (the A/B arms and phases). Condition 5 is then bounded by it, and the bound is
measured on the complete record rather than on 5% of it.

### 3. Identify the trigger clock by latency dispersion: the Binance stamp or Polymarket's first cancel? (strong form of finding 9 / X41 / X52; settles the condition-2 cut)

**Hypotheses.**
- **A.** The operator's arrival is locked to the Binance knee-band event at a fixed latency, and Polymarket's makers react to the
  same event faster.
- **B.** On some decisions the bot fires on Polymarket's own cancels. In finding 9, the book-only top decile is taken 9x more often
  than baseline without a Binance L1 move.

**Why it fits.**
- Finding 10: the steep part of the wave runs from m0 - 200 to m0 - 100, and the operator arrives around m0 - 175 on the book clock.
- Finding 12: the book's power sits in the last 50 ms before the bot's own view.
- A fixed-latency trigger has a tight lag distribution on its own clock. A co-reacting signal has a wide one.

**Test.** For every first leg of 10-20..22:
- t_bn is the Binance spot event that completes the knee-band microprice move toward o, on exchange time (dcclock14 frame);
- t_pm is the first Polymarket `price_change` after m0 - 800 at which o's ask depth at best .. best + 4 c has fallen 30% or more
  from its level at m0 - 800, on server time, taken from the event-level ingest rather than the 50-ms grid;
- a = m0 - 150 on the trade clock.

Then:
1. Among legs where both events come before a - 30, compare the IQR and peak width of a - t_bn and a - t_pm.
2. Regress a on both event times.
3. For the book-only top-decile takes, look for a USD-M or other-venue event at the knee (a common input), or establish that there
   is none.
4. Run the same analysis on matched fast crowd takers as a placebo.

**Data.** The capture's L2 events and the Binance spot book of 10-20..22, and the dcclock14 frame.

**Signature of A.**
- IQR(a - t_bn) of 30 ms or less.
- a - t_pm diffuse (IQR of 100 ms or more).
- t_pm at least 20 ms after t_bn in most legs.

The input is then Binance, the cut at the bot's view is physical, and the book's power is co-reaction. Write that into the
pre-registration of the condition-2 unit.

**Signature of B.** A subset whose a - t_pm peaks tightly at the bot's Polymarket latency (~30-60 ms) with no Binance event. Market
activity triggers those decisions, so the rule must say so. On them the presence target is unattainable by construction, which
makes a measured wall component.

### 4. Complete the slot record with zero-fill orders and test the priority dispatcher as the condition-7 route for XM (strong form of X55 / X106 / X120 / X134)

**Hypothesis.** XM is the overflow slot. A leg goes to the first free wallet in DS > GF > XM, and XM's apparently free legs are
sent while DS or GF are busy with orders the taker record does not show:
- lost races with no taker fill that rested and were then cancelled;
- remainder cancels still in flight.

**Why it fits.**
- Critique 4b: the visible slot structure is sharp, but 68% of XM's legs look free.
- Among those free legs, the gap since the previous operator leg has an AUC of 0.37 for XM, so XM comes right after recent legs
  and something is occupying the slots.
- Up to about one decision in three is an unfilled lost race (X72, ins9b).
- Remainder cancels are sent from 14-26 ms after the post (X94).

**Test.**
1. From the capture's L2, find every operator bid insertion at (o, L) of a menu-consistent size with no matching trade, using the
   ins9b fingerprint (17-33 ms before the would-be trade message).
2. Assign the wallet from the order's later maker fills (order hashes in `fills.parquet`) or by elimination, and locate the
   removal.
3. Add these orders to each wallet's slot intervals. Refit the slot length and offset on 10-20.
4. Score the deterministic DS > GF > XM rule once on 10-21..22: XM recall and precision, and the slot-oracle XM window PnL r (the
   `slotoracle.py` design, which is thin14's oracle with the allocation replaced).

**Data.** The capture's L2 and trades, `fills.parquet` order hashes, and `depth15_orders`.

**Signature if true.** XM recall of 0.6 or more at a precision of 0.6 or more, and a slot-oracle XM PnL r of 0.6 or more (against
0.29 for base rates and 0.44 for thin15). Condition 7 for XM would then be a dispatch rule that a replica can simulate from its own
slots, and the thinning ceiling would not apply.

**If false.** XM's free legs are a weighted coin (3-5%). The thinning ceiling stands, now measured on complete slot data.
