# Panel, iteration 18: mechanics and on-chain forensics

Reviewer lens: how the orders are built and what the operator's own machinery leaves on chain. That covers the sibling wallets'
prints and orders, the size register, the pre-signed ladder, the order hashes, rebates and rewards, and the salt generator.

Data used. Everything is development data:
- `it18/sib_frame.parquet`: 73,577 operator taker orders of 10-20..22 with exact classes, the true S / E and sib18's public state.
- `it16/tapes/*`: W4 / W5 prints. `it16/cdfull_10-2{0,1,2}.parquet`: complete operator taker calldata.
- `it14/dcclock14_frame.parquet` (knee moves) and `.cache/re/btc5m-bot/fills.parquet` (on-chain fills of 10-09..22).
- `binance_1s.parquet`.
- The new-regime record `it17/post17_*` (11-01 06:00-09:30; every window asserted not sealed).
- data-api `/activity` REWARD and MAKER_REBATE rows of GF / XM / DS / W4, for 2026-08-12..H-1 only, through the polyrea adapter.

Nothing sealed was read and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` reported "released none; future examined
until 2026-10-31 00:00". The current block (11-01 12-18) is sealed, and nothing from it was touched. Scripts are in the session
scratchpad, `p18m/chk1.py` .. `chk15.py`. Apart from this file I wrote nothing to the workspace.

The assumptions panel (`iter18_assumptions.md`, critique 4 and P3) has already shown three things. The 0.49 / 0.61 "S agreement" is
coverage times conditional agreement. Covered agreement is 0.80-0.84. W5 is not an S-carrier. I do not repeat those points. The
items below are additional, and two of them change what the planned tracker run will show.

## Critique

### 1. The sibling state feeds the transition model an E on the wrong scale

`sib18_run.py` fits the smach17 transition model on the operator's true E: large shares of all three wallets since S was last set.
It then scores the public variant with `Epub`, the W4 / W5 large shares since the last sibling flip. Two things are wrong with that.
- `Epub` is several times smaller. The median E / Epub ratio on the fit days is 6.0 (10-20) and 5.0 (10-21..22), so the model's
  log1p(E) x relation terms read the public state as weakly committed.
- The fill >= 60 rule drops W4's 100-share orders that filled 31-59 shares. W4's menu is 30 / 100, so any fill of 31 or more is a
  large order.

One constant k (median E / Epub on the FIT days only) fixes the first, and W4 >= 31 fixes the second. The deterministic sib18 scorer
reproduces sib18 exactly (`chk8.py`, `chk15.py`):

| state (deterministic scorer) | coverage | agreement where covered | window-net rN | PnL-proxy Spearman | gain vs sib18, paired 2-h blocks |
|---|---|---|---|---|---|
| menu, fit 10-20 -> 10-21..22 | | | 0.290 | 0.224 | |
| sib18 (W4 + W5, fill >= 60, raw E) | 0.619 | 0.800 | 0.387 | 0.336 | |
| W4 only, fill >= 31, raw E | 0.651 | 0.841 | 0.394 | 0.353 | +0.017 [0.002, 0.037] |
| **W4 only, fill >= 31, E x k (k = 6.0)** | 0.651 | 0.841 | **0.453** | **0.444** | **+0.106 [0.067, 0.149]** |
| sibling S (W4 >= 31 / W5 >= 106) with the operator's true E (oracle E) | | | 0.470 | 0.445 | |
| true-state ceiling | | | 0.588 | 0.566 | |
| menu, reverse (fit 10-21..22 -> 10-20) | | | 0.435 | 0.405 | |
| sib18, reverse | 0.527 | 0.820 | 0.536 | 0.511 | |
| **W4 only, fill >= 31, E x k (k = 5.0), reverse** | 0.588 | 0.823 | **0.602** | **0.577** | **+0.066 [0.020, 0.109]** |
| true-state ceiling, reverse | | | 0.721 | 0.706 | |

- The share of the above-menu ceiling the public state recovers rises from about a third (33% / 35%) to 64% / 57%.
- Most of the iteration-18 shortfall was this E mismatch, not a "within-window commitment E" the public record lacks. With the E scale
  fixed, the public state reaches the oracle-E level (0.444 vs 0.445).
- Before the fix, the sib-to-ceiling gap split about 60 / 40 between the covered orders (staleness and E) and coverage (`chk11.py`).
  After it, the gap is about half coverage and half staleness. The uncovered orders sit early in the window (median rel 76 s,
  covered 163 s) and carry 41% of the large orders.

The tracker run that NOTES.md lists as next step 1 will under-deliver if it reuses sib18's `Epub`.

### 2. A plain copy of the siblings already reaches condition 5's level, so the menu is the wrong baseline

The proxy gains above are measured against the menu. But the siblings are the operator, and copying them needs no decoded input.

| no-decode proxy (`chk12.py`, 10-20..22, 734-759 windows) | Pearson | Spearman |
|---|---|---|
| pooled operator window PnL vs (W4 / W5 large net) x outcome | 0.483 | **0.547** |
| the same, by day half | 0.484 / 0.492 | 0.551 / 0.550 |
| pooled vs (W4 / W5 large net - 0.5 x small net) x outcome | 0.508 | **0.576** |
| GF / XM / DS vs (W4 / W5 large net) x outcome | 0.496 / 0.285 / 0.165 | 0.548 / 0.270 / 0.248 |

- The siblings' small net runs against GF's net (r -0.39), as the pairing leg does inside the operator.
- This gross proxy uses neither the decoded side nor oracle decision times, yet it is above the frozen tracker's Spearman of 0.467.
- Under the brief's "Who else" rule, any sibling-informed size input has to be measured against a tracker that copies the same
  wallets' prints. sib18's gain is measured against the menu. Its "baseline that already contains W4 / W5 prints" is the tracker's
  tape features, which do not copy the siblings' lean.

**The siblings write into the operator's size register, not only read it** (`chk14.py`). Take S5, the latest large event among the
three wallets' large orders and W4 / W5's large prints. Where S5 and the three-wallet S disagree (1,738 orders), the class follows S5:
- pooled P(large) is 0.166 when the order is with S5, against 0.125 when it is with S3;
- GF 0.31 vs 0.26;
- XM 0.54 vs 0.42.

W4's large orders change the studied wallets' next size exactly as their own do. This adds to the assumptions panel's "W4 holds the
operator's memory": W4 is a writer of the same state. It is the strongest evidence for the X170 ruling. The likely ruling makes every
sibling input own state.

### 3. Out of time, the sibling state does not carry S

On the new-regime record (`chk13.py`; 11-01 06:00-09:30, 30 windows, 999 DS / GF / XM taker orders with calldata sizes, 62 large):

| | value |
|---|---|
| sibling large prints (W4 >= 31 / W5 >= 106; W4 >= 60) | 33 / 26 |
| coverage | 0.576 / 0.525 |
| agreement with the operator's S where covered | **0.564 / 0.412** (capture days 0.82-0.84) |
| P(large) with / against the sibling state | 0.073 / 0.055 |
| P(large) with / against / none, the operator's own S | 0.115 / 0.033 / 0.049 |

The operator's own register still works in the new configuration. The siblings' view of it does not: there are about 2 large orders
per window, and W4's own large rate (0.21) is now far above GF's (0.08). The sample is small, but the direction is the opposite of what the route
needs. The assumptions panel's P4 (a configuration tracker from W4) carries the same risk. h1 lies between the two configurations.

### 4. Condition 2 at the decision clock is decided by the cut, not by the unit

X190 (the order unit) is listed as the strongest route to condition 2. The gain over a book-aware baseline moves from +0.058 at the
cut e = m0 - 230 to +0.008 at e + 50 (reverse split +0.081 / +0.023; X146). X151 brackets DS's own Polymarket view in
(m - 250, m - 180] on the book clock, which contains both cuts. Changing the unit does not move this; measuring the view does.

X151 step 1 decides whether condition 2 is reachable against a book-aware baseline at all. That is the per-order bracket from
event-level `price_change` rows: the view is after o's ask last became L and before it left L. Run it before investing in X190. Ask
the examiner, together with X170, whether the market-activity baseline includes the order book. The brief's definition lists prints,
timing, time in window and price level.

### 5. Checked and not supported (so nobody redoes them)

- **The class is not front-loaded or budgeted inside a lean** (`chk5.py`). P(large) on the k-th with-S order since S was set is flat
  (0.20-0.25 for k = 0..12; DS 0.06-0.10, GF 0.44-0.50, XM 0.57-0.79). There is no cap on E: P(large) rises from 0.21 to 0.29 with
  E, the episode max E reaches 3,300, and the large shares per (window, side) reach 3,800 with no pile-up.
- **Strong knee events do not write S** (`chk9.py`). Take the dc14 side of the latest decision whose confidence is >= theta, or
  whose |microprice 250 ms| is >= theta. Its agreement with S is 0.51-0.58 for every theta. Binance 1-s return signs over 2-120 s,
  and the move since the open, agree with S at 0.36-0.575.
- **The siblings' small prints carry S only weakly** (`chk10.py`). On orders without a sibling large print, -sign(W4 / W5 small
  net over 15-300 s) agrees with S at 0.54-0.56.
- **Latency of the sibling feed barely matters** (`chk7.py`). Moving sibling prints from block + 2 s to block - 1.3 s (about the match
  time) raises coverage by about 1.6 points and agreement by about 1 point. A mempool or RTDS activity feed for the siblings is not
  worth building.
- **The hourly large rate is persistent but not a feedback controller** (10-19..22, 90 hours, osz proxy). Its lag-1 autocorrelation
  is 0.50-0.66, but its Spearman with the previous 1 h / 3 h operator PnL is 0.01-0.12 and with BTC realized volatility -0.08..0.11.
  That points to scheduled configuration (B5 drawdown response not supported).
- **No pre-signed order is submitted twice.** 0 of 72,602 operator taker orders of 10-20..22 appear as taker in two transactions,
  and 8 span more than one block. There is no FAK resubmission of a pre-signed order.
- **No event-loop stall at the signing bursts.** Order density 2-5 s before a burst dips by about 10% at most, and side accuracy
  around the bursts (0.80-0.83) is at the window-time level.
- **The maker rebate is an exact per-fill amount.** MAKER_REBATE on day d+1 equals 0.0140 x sum of shares x p(1 - p) of day d's maker
  fills, that is 20% of the taker fee, for GF, XM and DS on every day checked. XM's rebate fell from $184-354 a day to $30-62 on 10-14
  only because its maker volume fell (19.2k to 3.5k fee-weighted shares). So the 10-13/14 role switch was not a rebate-rate change.
  A replica can book maker rebates per fill and per window.
- **Liquidity rewards ended on 09-06.** REWARD rows exist for all four wallets from 08-12 to 09-06 (XM up to $387 a day), and none
  afterwards. B7's ruling holds for every development day since then. The 09-06 stop is a C4b date to match against announcements.
- **XM's post-T0 60-share class is a new route, not the BUILD configuration coming back.** On 10-09..13 (menu 60 / 100), XM's orders
  that filled 31-60 shares were taker-first 24,899 times and maker-first 4,752 times. Post-T0, 0 of 274 XM 60-share orders take,
  while its 30 / 100 orders do. See P4.
- **No copy-pool cap in the ladder** (also in the assumptions panel). Distinct filled copies per (wallet, burst, token, cent, size)
  are geometric, with at most 8 small and 7 large.

## Proposals (ranked by the chance they close the gap)

### P1. Rescale E and keep W4 only before the tracker run (correction and strong form of X182 / assumptions P3; condition 5)

**Hypothesis.** The public sibling state is a lagged observation of the operator's register S / E. With the commitment measured on
the operator's scale and W4's menu read correctly, it carries about 60% of the above-menu value of the true state, against 33-35%
in sib18. That is enough to move the executable tracker's Spearman by the missing 0.033, if the examiner admits it.

**Why it fits.** Critique 1:
- the k-rescaled W4 state gains +0.106 [0.067, 0.149] and +0.066 [0.020, 0.109] in PnL-proxy Spearman over sib18 on the two splits;
- it equals the oracle-E proxy (0.444 vs 0.445);
- covered agreement is 0.84 / 0.82.

**Test.**
1. In the sib18 harness, set the state to W4 only, fill >= 31 (or exact class, step 2), and E_pub x k, with k = median(E) /
   median(E_pub) on the fit days. Keep the true-state transition model.
   - Report coverage and covered agreement separately, by window-time band.
   - Report the paired 2-h block bootstrap against sib18 and against the menu, on both splits.
2. **Exact classes for W4.** Fetch the calldata of every W4 transaction of 10-17..22, taker and maker-only, about 3.2k a day with
   cdfull16's batched `eth_getTransactionByHash`.
   - Use original size >= 90 as large. That adds the 100-share orders that filled 30 or fewer, about a third of large orders by the
     cluster's own osz recall of 0.63.
   - Add the large lost races revealed by their maker fills, usable from that fill's block.
   - Shared transactions with DS / GF / XM stay excluded.
3. Execute E[size | corrected state] in trk_a with the mix14 target under strict fills, on both splits. Freeze it behind the
   assumptions panel's `size_route` switch.
4. Run P2's copy baseline and out-of-time gate in the same run. Adopt nothing that fails either.

**Data.** `it18/sib_frame.parquet`, `it16/tapes`, W4 calldata (to fetch, about 2 min a day), the mix14 harness.

**Signature if true.**
- Proxy Spearman of 0.44 / 0.58 or more, reproduced with a lower CI bound above 0 against sib18.
- Calldata coverage of 0.70 or more at covered agreement of 0.82 or more.
- An executable tracker Spearman of 0.50 or more on both splits.

**If false.** If the proxy moves but the executable tracker does not, the binding term is strict-fill execution of the lean, not
the size expectation. Then report condition 5's size term as attained in expectation and lost in execution.

### P2. Score a sibling-copy tracker and an out-of-time gate before any sibling input is adopted (new baseline; strong form of X170)

**Hypothesis.** W4 (and W5) are fan-out slots and register writers of one operator. Any sibling-derived input is then co-occurrence
with the operator itself. A rule that just holds the siblings' large lean reproduces most of the operator's per-window PnL ranking,
and the sibling view of the register does not survive configuration changes.

**Why it fits.**
- Critique 2: the copy proxy reaches Spearman 0.547 / 0.576 with no decoded input; S5 dominates S3 where they differ.
- Critique 3: out of time, covered agreement is 0.41-0.56 with no class separation.

**Test.**
1. **Executable copy tracker.** trk_a with its target set to the W4 / W5 per-second signed net flow from their public prints
   (block_ts + 2 s, shared transactions excluded), strict fills, latency 2 s or more, both splits. Run three variants: large only,
   all prints, and large - 0.5 x small. Report Pearson / Spearman, pooled and per wallet.
2. **Reporting rule, pre-registered.** A sibling-informed rule counts only by its paired 2-h block gain over the best copy tracker.
   This is the brief's "Who else" baseline. The menu is not that baseline.
3. **Out-of-time gate.** Use the three post-T0 development blocks (10-31 00-06 / 12-18, 11-01 06-12; 142 windows) with the post17
   pipeline: on-chain fills of all five wallets, plus calldata for the classes.
   - Bars: covered agreement of 0.75 or more, and P(large | with) / P(large | against) of 2 or more.
   - Below them, the route is version-bound and stays out of the frozen rule whatever X170 says.
4. **Ruling.** Send the S5 table and the copy-tracker numbers to the examiner with X170.

**Data.** On disk, plus the post-T0 W4 / W5 fills and calldata.

**Signature if true (the siblings are the operator).**
- The copy tracker alone reaches an executable Spearman of 0.45 or more.
- The decoded rule plus the sibling state gains less than 0.03 over it.
- Out of time, covered agreement is below 0.65.

**If false.** If the copy tracker stays below 0.35 and P1's rule gains 0.05 or more over it, both in time and out of time, the
decoded state adds information beyond copying. It can then be put to the examiner as a size input with that evidence.

### P3. Prove the size draw is a coin inside the register, then test the salts' generator as its source (strong form of X149 / X185)

**Hypothesis.** Once S is known, which decision is large is a Bernoulli draw with per-wallet, per-slot rates that drift by the hour.
The process's PRNG makes that draw. The salts are the only public carrier of it that is not the operator's own prints. If the
runtime is Bun (JavaScriptCore WeakRandom: output (h_n + h_{n-1}) mod 2^53), the stream is recoverable from salts, and the draws
between two bursts can be aligned with the decisions.

**Why it fits.**
- Critique 5: flat in k, no budget, no public event writes S, no carry-over, no PnL or volatility controller.
- Positive lag-1 dependence beyond S (GF 0.53 vs 0.40; 0.59 vs 0.43 at gaps over 2 s) matches the hourly drift (rate autocorrelation
  0.5-0.66).
- V8 is excluded with a validated solver (prng15 / 16), and 32-bit generators are excluded (salts keep 36 bits or more).
- A weak prior for Bun: the operator's tooling names point to Claude Code, whose native build runs on Bun.

**Test.**
1. **Exchangeability (cheap, decisive for the wall account).**
   - Strata: wallet x UTC hour x slot x S-relation x E tercile.
   - Permute the class within strata, 2,000 times. Test lag-1 same-class rate and runs within (wallet, window).
   - If the class is exchangeable: the per-decision class is an i.i.d. private draw. Compute condition 5's redraw ceiling: the
     tracker driven by the true transition probabilities with redrawn classes, 300 draws, with and without P1's public state. If it is
     under 0.50, condition 5 is out of reach for any public rule, and that is a quantified wall component.
2. **JSC solver.**
   - Self-test z3 (scratch venv, z3-solver from PyPI) on synthetic WeakRandom salts in prng16's three layouts.
   - Then run it on the 130 same-ms copy groups.
3. **If a group solves.** Step the stream to the wallet's next burst.
   - Align the intervening outputs to that wallet's decisions in time order, by dynamic programming, allowing unknown other calls.
   - Test u_i < p_w(slot, S-relation) against large_i.
   - Also count the draws per inter-burst interval against top-hazard instants (X185's take-coin denominator).

**Data.** Complete calldata salts (on disk), the sib frame, z3-solver in a scratch venv.

**Signature if true.**
- Held-out salts are predicted exactly.
- The aligned outputs separate large from small at AUC 0.95 or more; the draws per interval rise with hazard mass.

**If false.**
- Step 1 alone still turns "undecoded size" into a measured private coin with an explicit ceiling.
- 0 / 130 under JSC closes X149 as a CSPRNG.

### P4. The post-T0 XM 60-share class against its own history: a natural GTC counterfactual (strong form of X184 / X188; condition 7 in the new regime)

**Hypothesis.** The post-T0 60-share XM orders are sent post-only (or on a route that never crosses). On 10-09..13 the same wallet
sent 60-share orders as the small class of a 60 / 100 GTC menu. Those took most of the time. Matched on the same dispatch position,
the two periods separate post-only from always-late without the book simulation X184 needs.

**Why it fits.**
- Critique 5: BUILD 60-share-filled orders are taker-first 24,899 vs maker-first 4,752; post-T0 it is 0 of 274, while XM's 30 / 100
  orders take.
- The iteration-17 reading ("the same 60-share maker-first orders ... dominant again") conflates the two.

**Test.**
1. In both periods, select XM 60-share orders that follow a W4 leg on the same outcome within 300 ms (the slot after W4; X154).
   - Post-T0 timing comes from the it17 record. On 10-09..13 use W4's data-api prints and, where the capture covers those days, server
     ms.
2. Compare P(take) and the ask's survival at arrival: o's ask still at L at m - 35 on the capture book, where available.
3. **Post-only predicts:** BUILD takes whenever the ask survives, post-T0 never. **Always-late predicts:** post-T0 arrivals find the
   ask gone at the rate BUILD late-slot orders did.
4. Then book XM's maker stream per window with the exact rebate, 0.014 x p(1 - p) per maker share, for X186 / X188.

**Data.** `fills.parquet` (10-09..13), W4 tapes for 10-09..13 (to fetch), the it17 record, the capture book where it exists.

**Signature if true (post-only).**
- In matched slots BUILD takes in 50% or more of orders whose ask survived.
- Post-T0 takes 0 with surviving asks present in a comparable share (binomial p < 1e-6).

**If false.** If post-T0 arrivals almost never see a surviving ask in matched slots, the class is always late. XM's new-regime
stream is then bounded by its arrival offsets, the per-wallet knee route.
