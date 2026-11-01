# Panel, iteration 11: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers the pre-signed ladder (loop layout, stalls, salts), the
one-order-in-flight slot, cancels and remainders, fan-out legs, maker requote cadence as a clock, versions, and
fingerprints of the bot software.

Data I used, all development:
- `calldata_sample.parquet` (BUILD/VALIDATE sample hours, before H);
- the 10-31 14:55-17:55 block (development): `it10/cdall10`, `it9/cd9`, `post/cd*`, `it10/txms10`, `it10/rem10`,
  `it9/own_1231_12_18`, `it9/ins9b_M` and `it11/onset_A` / `onset_C`;
- the lab feeds `btc5m_clob_raw2` and `btc5m_venues2`, read only through `live_lab.recs` (`iter_live`, `allow_sealed=False`);
- `fills.parquet` (VALIDATE);
- 1-byte HTTP range requests that check whether archive files exist, for development dates only: pmxt 06-20 to 10-22 and
  Tardis 07-01 / 08-01.

Nothing sealed was read, and `.cache/live/sealed/` was not opened. My scripts are in the session scratchpad,
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`m11_burst.py`, `m11_burst2.py`, `m11_loop.py`, `m11_refire.py` (it saves `m11_ev.parquet`, the 2,155-decision table with
won / lost / crowd-ahead), `m11_makertrig.py`, `m11_copies.py`, `m11_fresh.py`, `m11_wslag.py`, `m11_armed.py`,
`m11_ratchet.py`, `m11_w4.py`, `m11_cancel.py`, `m11_cancel2.py`, `m11_echo.py` and `m11_stall.py`. Apart from this file I
wrote nothing to the workspace. Written 11-01 ~00:10 UTC.

## Critique

1. **The "coin" verdict on the selection rests on too few events to carry the weight the wall account puts on it.**
   - Finding 8's taken-versus-skipped AUCs among price-level events use 293 events on A and 181 on C, about 30% of them
     taken. They all come from one Saturday afternoon: 34 windows and 2,155 decisions.
   - At n of about 180 with 54 taken, the standard error of an AUC near 0.58 is about 0.047 (Hanley-McNeil). The 95%
     interval runs from about 0.49 to 0.67.
   - So "indistinguishable from a coin given every public input" is mostly a statement about power. Free archives give 16
     times the sample, on a weekday and on older bot versions (proposal 1), and they have never been used for the
     selection.

2. **"Internal, self-exciting state" is not yet shown to be internal.** Three of my checks argue against reading rec30 as
   a private state (details under "Checks"):
   - The take decays smoothly with the time since the last decision on o: on A, 12.3% at 0.5-1 s, 7.5% at 3-5 s, 4.3% at
     12-20 s and 2.4% after 60 s. There is no step, so no "armed for T seconds" timer.
   - The take doubles when the venue has moved beyond its level at the last decision on o (x2.1 on A, x2.3 on C). But
     anchors that are not the bot's own do as well or better: the level 0.5 x dt ago gives AUC 0.637 / 0.634 against
     0.587 / 0.627 for the own anchor. That is recent momentum, not an own-order anchor.
   - The re-fire rate after a WON race equals the rate after an exogenously LOST one (no fill feedback on presence).

   The honest statement is: "the operator's recent decisions proxy a persistent state that no recorded feature captures".
   That state may be public (repricing lag, multi-venue momentum) or private.

3. **X99's negative used an offset model that the ladder's own layout contradicts.**
   - The panel searched placements of same-millisecond copies within ±24 calls. Inside one millisecond the order of the
     copies is unknown, so that is the weakest possible constraint.
   - The signing loop has a measurable layout:
     - the wallets are signed one after another;
     - within a wallet, one token's cents go up at 1.66 ms per cent, then the other token's;
     - both sizes and all copies of a cent fall within one ms;
     - 90% of the loops rise monotonically.
   - That layout fixes the generation offsets ACROSS cents, up to two or three integers (proposal 2).
   - The ~0.8-s stalls inside the loops are awaits: decisions continue during them. Other tasks may call Math.random
     there, so a solver must use loop segments without a stall.

4. **The exit model for X93's simulator is missing two mechanical rules.**
   - Part of the cancel is the wallet's single slot. A cancelled remainder is followed by a same-wallet arrival within 300
     ms in 16.8% of cases and preceded by one in only 3.1% (placebo about 7.5% per side). In other words: cancel, then
     send.
   - Remainders under about 5 shares never rest (they are dropped at the engine). These are the 11.8% "no insertion"
     never-filled remainders of X86: median 3.4 shares, against 20 for those that were found. They are not FAK posts.

   A replica that keeps the remainder TTL independent of its own next decision will mis-time the maker refills, and those
   refills are about half of the lost races' fills.

5. **The h1 exam fails condition 5 whatever is decoded.** Finding 5 shows that under the latency >= 2 s convention even
   the oracle reaches r = 0.40 at the block clock. The work that can still pass a round is therefore the work that runs on
   recorded books: future blocks, and the archived days of proposal 1, which are a stand-in for them. There, selection
   and size are deterministic given the arrival (race11), and the release of the first half of h1 should be planned as
   diagnosis, not as a target.

## Checks (so nobody redoes them; 10-31 14:55-17:55 unless stated)

- **No fill-driven re-arm of the take.** This bears on information-panel proposal 4 at short horizons; the 1-2 min
  controller of assumptions-panel proposal 4 is not covered. Same-outcome operator decision after decision i:

  | after decision i | n | within 1 s | within 3 s |
  |---|---|---|---|
  | won, fully filled | 823 | 33.4% | 54.4% |
  | won, partly filled | 503 | 22.1% | |
  | lost, any | 829 | 31.4% | 48.6% |
  | lost, crowd queued ahead (exogenous) | 460 | 33.3% | |
  | lost, no crowd ahead | 369 | 29.0% | |

  Matched on how far o's ask ran 500 ms after the match (>= 3 c): won 46.9% (147), lost 41.5% (386). No
  retry-until-filled controller, and no win-driven excitation.
- **No set-completion trigger.** For each of 2,729 operator maker fills on ō, I counted operator taker decisions on o
  within the next 300 ms:
  - 6.7%, against a placebo of 5.5% (x1.20);
  - on the same outcome: x1.49 (co-activity).
- **No copy-exhaustion or duplicate-rejection signature.** P(take | onset) by the number of operator decisions at the
  same (window, outcome, cent) earlier in the same ladder segment, for 0 / 1 / 2-3 / 4+:
  - A: 5.9 / 6.1 / 10.4 / 10.8%;
  - C: 4.4 / 7.3 / 4.4 / 1.0%.

  The two halves disagree.
- **No Polymarket feed-freshness gate.** By the age of the last near-touch message at τ − 30 ms:
  - under 50 ms: 6.6% (A) and 5.0% (C);
  - 200-1,000 ms: 0.9-1.2%;
  - 1-3 s: 4.1-6.1%.

  The pattern is not monotone, and ages of 200 ms or more cover only 7% of onsets. The recorder's detrended ws
  publication lag is not monotone either; at more than about 650 ms the take is 1.7-4.0%.
- **No timer.** The take decays smoothly with the time since the last decision on o (critique 2). With no earlier
  decision on o in the window it is 2.4% (A, n 2,193) and 1.5% (C, n 5,097).
- **No own-order ratchet** (critique 2).
- **W4 is not a probe.** On 10-31 it uses the same 30/100 menu (327 and 126 legs). Main-wallet arrivals on the same token
  come before or with W4's taker arrival:
  - in (−300, −50] ms: 42.7% (placebo 2.8%);
  - in (−50, 50] ms: 31.3%;
  - in (50, 300] ms: 23.3%.

  W4 is a late fan-out leg.
- **No FAK posting** (critique 4).
- **No hard operator-level net cap.** Over VALIDATE fills, the pre-trade operator net toward the bought outcome decays
  smoothly to ±1,400 shares (100-share bins beyond +700: 3,574 / 2,079 / 904 / 262 / 101 / 27 / 7). The per-window max
  |running net| shows no pile-up.
- **Signing-loop layout** (calldata_sample, 389 wallet-bursts with 12 or more used orders):
  - token loops go up in cent in 90% of cases, at a median 1.66 ms per cent, monotone;
  - two sizes at one cent are signed within 1 ms (q90 1 ms, n 297);
  - stalls longer than 100 ms: 0.77 per wallet-burst, median 813 ms (q10 156, q90 965), 147 between tokens and 154 inside
    a token loop;
  - one burst: XM 0-163 ms, DS 1,127-2,162, GF 3,001-4,018, W4 4,138-5,049 (wallets one after another, about 1 s apart).
  - On 10-31, decisions arrive during the stalls at 0.237/s (224 s of stalls) against 0.282/s in ±20-s controls, so the
    stalls are awaits, not a blocked event loop or GC deafness. The whole burst runs at 0.85x the control rate (X32's dip).
- **Requote echo** (for proposal 5): 90,483 consumed non-operator maker legs on 10-31.
  - 58% have a later filled order from the same maker and token.
  - The gap s_next − m (next order's signing time minus the match) spikes at [0, 20) ms: 1,435 legs, against 182-333 in
    the neighbouring 20-ms bins.
  - In [−5, 25) ms: 1,613 legs, 1,414 txs (2.9% of txs) and 137 makers. They touch 63 of the 1,536 operator taker txs
    directly.
- **Archive coverage** (1-byte range requests):
  - pmxt hourly files exist from 06-20 (06-20T14 275 MB, 07-01T14 398 MB) to 08-10T00. They answer 404 from 08-10T05 and
    on 08-11, 08-20, 09-10, 10-01, 10-16 and 10-22.
  - The Tardis free days answer 206: 07-01 and 08-01 binance-futures `book_ticker` BTCUSDT (272 MB and 62 MB gz), 07-01
    bybit `book_snapshot_25` (118 MB) and okex-swap `quotes` (11 MB).

## Proposals (ranked by the chance of closing the gap)

### 1. Two archived live labs: 07-01 (Wednesday, XM alone) and 08-01 (Saturday, all wallets) from pmxt plus the Tardis free days; decode the selection by version (strong form of X60's never-run selectivity part, X37 and X95)

**Hypothesis.** One of two things is true:
- (a) The 1-in-3 take and the persistence are a layer added later: a multi-wallet allocator or router (DS / GF start
  07-19/20), a filter, or a throttle. The XM-only version takes nearly every strong onset, or follows a simple
  threshold.
- (b) The take is coin-like and persistent from the start. With 16 times the sample, the wall statement then becomes a
  measurement instead of a power limit.

Either way the decision rule becomes identifiable on a weekday, at server ms, with the bot's own input. That input is the
Binance USD-M bookTicker, which Tardis has tick by tick for these two days only.

**Why it fits.**
- Critique 1: the selection verdicts rest on n of about 180-290 price-level events from one Saturday afternoon.
- Older versions are mechanically simpler: one size per day, two bursts per window (version11, panel iteration 10), and
  one wallet before 07-19.
- X60 was closed on a two-hour delay-regime test. Its selectivity search (iteration-8 information P2, steps 3-4) never
  ran, and the Tardis days were never downloaded.
- The full live-lab chain needs only:
  - pmxt (server-ms book changes and trades with tx hashes; the BTC 5m row groups through range requests, as in
    `pmxt11.py`);
  - operator OrderFilled logs;
  - book insertions at the old ask (ins9's finder);
  - the Tardis book_ticker.

**Test.**
1. Reduce on the fly, nothing raw kept:
   - for 12 hours of 07-01 and 12 hours of 08-01 (06-18 UTC first), the pmxt BTC 5m trades and near-touch price changes;
   - the Tardis Binance USD-M BTC and ETH book_ticker to microprice events, merged within 50 ms (evt10's definition), plus
     Bybit snapshot_25 and OKX quotes as the second and third series;
   - streaming the gzip from the start, keeping only the hours needed.
2. Measure D for each day from the crowd floor (V2 calldata sign-to-match where it exists) or from the cluster gap floor
   (`pmxt11`). Build the decision record:
   - won races: cluster taker trades at the server ms − D;
   - lost races: insertions at the old ask with the day's size.
3. Re-run onset11 / price11 / regime11 / flag10b unchanged on each day, fitting on the first half and scoring on the
   second. Report:
   - the take rate per strong episode;
   - taken-versus-skipped AUC among price-level events (n in the thousands);
   - the decay of the take with the time since the last decision on o;
   - the share of decisions with no vote.
4. Diff the three versions (07-01, 08-01, 10-31) component by component. If (a) holds, test the router directly: when
   several wallets are free, which one fires, and whether the 1-in-3 appears only when two or more wallets exist.
5. Where 07-01 orders are V1, decode `expiration`, `nonce` and `feeRateBps` from the calldata. A GTD expiration at a fixed
   offset from signing, or at the window end, recovers pre-signing in V1 and a version fingerprint.

**Data.**
- r2v2.pmxt.dev (no key; about 100-400 MB of range reads per hour);
- the datasets.tardis.dev free days (GET with Range);
- Polygon logs (V1 / V2 exchange addresses verified from a receipt);
- Gamma `closed=true` listing fields;
- `resources.py --need-disk` before each day.

**Signature if true.**
- (a) On 07-01, the take among price-level episodes is >= 0.7, or a single threshold separates taken from skipped at
  AUC >= 0.80 out of sample, and the 1-in-3 / persistence pattern first appears on 08-01 or later. The change point
  names the added component, and the router or filter is decoded from the wallets' slot states.
- (b) The same coin-like take and smooth decay on all three days, with the price-level AUC <= 0.60 at n >= 2,000. The
  "not decoded" account is then a measured bound, on a weekday and across versions.

### 2. Recover the PRNG with the loop layout fixing the offsets (strong form of X99)

**Hypothesis.** Salts come from Math.random in loop order. The relative generation index of two used orders in one
wallet-token loop is n x (Δcent) + Δslot, where:
- n is the number of orders per cent, constant within a loop: about 1.66 ms per cent divided by the time per signature,
  so 4-16;
- Δslot is in [0, n);
- in V8, the 64-value LIFO cache phase adds one more unknown in [0, 64).

V8's output is the top 52 bits of state0, which is GF(2)-linear in the 128-bit state. Four to six orders then fix the
state by Gaussian elimination, with no z3. JSC (Bun) outputs the low 53 bits of s0 + s1 and needs z3.

**Why it fits.**
- Critique 3: the earlier test used same-millisecond groups, whose internal order is unknown, and no cross-cent
  constraint.
- The layout is now measured: ascending cents, monotone steps, both sizes in 1 ms.
- salt / timestamp is uniform, with a maximum of 1.0.
- The parts of the policy that look random are the ones left: the take at strong onsets, the choice of fan-out wallet,
  and the TTL.

**Test.**
1. Synthetic first. Generate V8 xorshift128+ with the 64-cache, a loop with n orders per cent, and the observed density
   of used orders (median 16-21 per wallet-burst for XM / DS). Verify unique recovery and a null rate of zero.
2. Real data. Use stall-free loop segments with 8 or more used orders spanning 20 or more cents. Scan n in 1..16, the
   cache phase in 0..63 and the slots incrementally, keeping 28-40 trusted bits per salt. Variants:
   - Date.now() = sign_ms ± 1;
   - two calls per order.
3. Accept a solution only if it predicts the top bits of 3 or more held-out salts in the same loop.
4. If a state is found:
   - chain the bursts with GF(2) jump-ahead;
   - count the hidden draws between bursts;
   - regress them on the evaluated onsets, decisions, lost races and cancels in the interval;
   - align the drawn values in time order with the onsets (take iff u < p) and with the wallet picks.

**Data.** `calldata_sample.parquet`, `cd9` / `cdall10` / `post/cd*`, numpy (z3-solver for JSC).

**Signature if true.**
- One parameter set predicts the held-out salts exactly (false-positive odds below 2^-80).
- The hidden draws equal about one per evaluated onset: the take is u < p(.), decoded as a mechanism. Or one per decision:
  the wallet choice is random. Either way, report it as own state, never as a target feature.

**If false.** No placement under any variant with fixed offsets. The salts are then not consecutive Math.random draws
(worker threads or a crypto RNG). Close X99 on that measurement.

### 3. Where the hidden state lives: per-wallet executor processes or one strategy state (process topology; new)

**Hypothesis.** The persistent "on" state is one of two things:
- (a) Per wallet: separate executor processes, each with its own connections and latency. This fits the per-wallet view
  lag (DS 50 / GF 10 / XM 30 ms), gap floor (254 / 196 / 152 ms), remainder TTL (328 / 240 / 124 ms) and kernel.
- (b) Operator-wide: a target position or regime that a dispatcher spreads over the wallets.

Under (a) the take is each process's race eligibility, a latency and connection state. Under (b) it is a strategy state
whose target can be inverse-fitted.

**Why it fits.** The per-wallet differences above. Every multi-leg event spans two or more wallets. Signing is one process,
but nothing shows that deciding is.

**Test** (onset tables, plus the 07-01 / 08-01 archive days when available):
1. Logistic P(wallet w takes onset k), with:
   - the FULL public score;
   - rec_w (w's own decisions on o in the last 10 s);
   - rec_−w (the other wallets');
   - (window x 2 min) fixed effects.
2. Compare β_own / β_other.
3. Measure the joint-take excess, P(w and w' | k) − P(w | k) P(w' | k), given the score.
4. Rerouting: when w is inside its slot (an order in flight, or the cancel → send gap of critique 4), does another wallet
   take the onset more often than when w is free?

**Data.** `m11_ev.parquet`-style decision tables per wallet, onset_A / C, slot intervals from the arrivals and the
measured floors.

**Signature.**
- (a) β_own >> β_other, joint takes independent given the score, no rerouting. Then decode per-process arrival jitter and
  eligibility, and the replica draws per-wallet latencies.
- (b) β_own ≈ β_other, a strong joint excess, rerouting present. Then the state is a target: fit the episode's
  cumulative sent shares by interval regression on public state at the episode onset.

### 4. The exit as a slot discipline, carried into the recorded-book simulator (strong form of X94 / X93)

**Hypothesis.** Each wallet has a single request slot covering both orders and cancels. A resting remainder lives until
the earlier of two events:
- its TTL (Weibull, per wallet);
- the wallet's next decision, which first cancels it (cancel → response → send).

Remainders under about 5 shares never rest. Weibull shapes below 1 are the mixture of these two removal modes.

**Why it fits.** Critique 4 (16.8% vs 3.1% asymmetry; the no-insertion remainders are 3.4-share remainders). The gap floor
of D + 2-104 ms is one in flight per wallet.

**Test.**
1. On 10-31, and on 11-01 06-12 when released:
   - for every cancelled remainder, the event order on the market channel (removal, then the same wallet's next
     insertion or match) and the floor of (next arrival − removal);
   - whether several resting orders of one wallet are removed in the same server ms (cancelAll);
   - TTLs refitted on the remainders with no same-wallet decision within their life.
2. Put both rules in X93's simulator. Score the maker-refill share and timing against the wallet's own, and the
   per-window PnL correlation of the oracle replay, with and without the slot rule.

**Data.** `rem10`, `ins9b_M`, `btc5m_clob_raw2`, the decision table.

**Signature if true.**
- A tight floor (a few to about 20 ms) in next arrival − removal.
- The refit TTL is closer to exponential or timer-like.
- The oracle replay's refill timing error halves, and its per-window r rises toward the 0.85 the iteration-10 mechanics
  panel set as the target.

### 5. Requote-echo anchors for the historical match clock (strong form of X89)

**Hypothesis.** About 140 BTC 5m makers re-sign their next order 0-20 ms after their order is filled. These are colocated
fill-reactive requoters. Their next order's sign_ms minus about 10 ms is the match time of the transaction that consumed
them: a ~10-ms anchor class that works at the block clock on h1 / h2. It complements X89's fresh-signed taker anchors,
tx_index and tip.

**Why it fits.** The echo spike: 1,435 legs in [0, 20) ms against about 200-300 per neighbouring bin, 1,414 txs (2.9%),
63 operator taker txs touched directly. Anchors inside the same block constrain the operator's matches through X89's
within-block ordering.

**Test.**
1. On 10-31, keep the makers whose echo spread (IQR) is 25 ms or less, fitted on 14:55-16:25.
2. Score on 16:25-17:55:
   - the anchor error on non-operator txs;
   - the share of operator taker txs within 100 / 200 ms after X89's isotonic fit with and without echo anchors.
3. Check that the echo makers are active before H, in the calldata sample hours.

**Data.** `cdall10` / `cd9` / `post` (truth), `calldata_sample` (persistence), Polygon receipts for the examiner's lot
fetch.

**Signature if true.** Echo anchors are within 25 ms on held-out txs, and with them 75% or more of operator taker txs land
within 200 ms. That is X89's bar, and it opens the PIT vote and price on h1 / h2.

**If false.** Echo makers are too sparse in the blocks that hold operator txs. That is one more measured limit of the block
clock.
