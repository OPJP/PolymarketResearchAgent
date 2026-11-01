# Panel, iteration 15: assumption breaker

Lens: what the iteration-15 account takes for granted that may be false. After iteration 15 three conditions still fail:

- condition 2 against a book-aware baseline at the decision clock, unless the book is cut at e;
- condition 5, where Spearman is 0.467;
- condition 7, for XM and GF.

The account explains them with three "coins": the take among top-hazard instants, the size menu and the carrying wallet. It also
adds a fourth limit, the makers' cancel race inside the 150-ms hold. This round tests two claims behind that account:

- the carrying wallet is an i.i.d. weighted lottery among free wallets, so XM is a random thinning. This is the premise of
  X134 / X138 / X148, of the iteration-13 mechanics check "XM is not an overflow wallet", and of thin14 / thin15;
- the cancel race limits only a predictor, not a replay.

## Data and checks

Development data only:

- the iteration-15 scratch frames `it15/depth15_orders.parquet` (73,577 operator taker orders, 10-20..22), the 50-ms L2 grid
  `it15/l2grid_*` / `l2tok_*`, the 16-offset ask vectors `it15/l2ordb_2026-10-20.*` and the calldata sample `it15/cl_orders.parquet`;
- `it14/dcfit14_pred.parquet` (first legs, rank 0);
- `it13/hf_dl/pm_trades_2026-10-21` and `btc_2026-10-21`.

I read nothing sealed, and I did not open `.cache/live/sealed/`. `sealed.py btc5m-bot` at 11-01 ~07:36 UTC showed no released
lots, and the current block (06-12) is a development block.

Scripts are in
`C:\Users\Remote-BEAST\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p15a\`.
Each ran in under 300 MB and under 2 minutes.

| script | what it checks |
|---|---|
| `slots.py`, `dens.py` | the carrier against the other wallets' in-flight orders and the local decision density |
| `wavew.py`, `wavew2.py`, `wavew3.py` | the makers' cancellation wave by carrying wallet, with composition and own-leg controls |
| `leftover.py` | the strict fill at the order's own match time on the recorded L2 (a replay, not a prediction) |
| `cent.py`, `cap.py` | deterministic routing keys; a per-window cap or overflow |
| `netarm.py`, `xmrole.py` | cross-wallet window nets by arm and day; XM's side against the operator's running net |
| `leak.py` | whether makers react to held taker orders (crowd BUYs at quiet Binance times) |
| `signrate.py` | the signing-throughput fingerprint (orders per signing ms; ms per cent) |

## Critique

### 1. The carrying wallet is not an i.i.d. lottery: it follows the operator's own in-flight orders

**The table.** For every operator taker match on 10-20..22 (73,577), a wallet counts as "in flight" if it has a match in the
previous 150 ms (`slots.py`). The carrier, by the state of the other wallets:

| in flight (by fills) | n | DS | GF | XM |
|---|---|---|---|---|
| none | 64,977 | 0.700 | 0.249 | 0.051 |
| DS only | 6,811 | 0.009 | **0.934** | 0.057 |
| GF only | 1,418 | 0.599 | 0.022 | **0.379** |
| DS and GF | 371 | 0.183 | 0.129 | **0.687** |

- The carrier is itself in flight in only 0.3-1.0% of cases (the known ≥ 120-ms refractory).
- The split among the free wallets is far from fixed weights:
  - with DS busy, GF : XM is 16 : 1, against 5 : 1 unconditionally;
  - with GF busy, DS : XM is 1.6 : 1, against 10 : 1;
  - with both busy, XM gets 69% (65.8 / 65.4 / 78.7% on the three days).
- A fills-only priority rule (DS, then GF, then XM) names the carrier for 72% of orders. Always-DS gets 63%.

**A priority list explains every cell once two kinds of occupancy are counted that fills cannot show:**

- unfilled lost races, about 0.3-0.45 per filled order (X65);
- W4 / W5 legs.

For example, a DS leg that lost its race followed by a filled GF leg reads as "GF only". Under the priority list the next
decision then goes to XM, which matches the 38% in that cell.

**Local decision density.** P(XM) rises tenfold with it, and the pattern is stable over days (`dens.py`). By the number of
operator matches in the previous 300 ms:

| matches in the previous 300 ms | P(XM) |
|---|---|
| 0 | 3-9% |
| 1 | 8-14% |
| 2 | 35-41% |

**XM-led first legs meet a book the makers have already drained.** This is the strongest point (`wavew*.py`; 57,630 first legs,
50-ms capture L2). o's ask depth at best .. best + 4 c, relative to m0 - 1500 ms:

| at | DS | GF | XM |
|---|---|---|---|
| m0 - 250 | 0.93 | 0.83 | 0.54 |
| m0 - 400 | 0.97 | 0.91 | 0.72 |

- The ordering survives a composition control: XM-count-weighted medians over 24 window-time x price strata give 0.937 / 0.832 /
  0.541.
- It survives an own-leg control: on first legs with no operator match on either outcome in [m0 - 1500, m0 - 250) it is
  0.932 / 0.849 / 0.513, with n 20,208 / 5,640 / 950.
- The share of XM-led legs with a ≥ 30% drop over the 100 ms ending at m0 - 300 is 0.28, against DS 0.08 and the placebo 0.07.
- m0 - 250 is before XM's own Polymarket view (about m0 - 205 on the book clock).

Under an i.i.d. lottery with one pipeline, the book before the decision would not depend on the carrier.

**Reading.** XM's leading decisions come late in a move: after DS / GF attempts or after a slower path, not at random.

- The iteration-13 check ("XM's single-leg orders occur with DS busy 6.0%"; "first legs with all wallets free go 76.8 / 19.1 /
  4.1") used visible occupancy only.
- regime12's per-wallet decomposition is the footprint a priority dispatcher leaves: a wallet's take does not rise with its own
  recent decisions (beta_own ≤ 0) but does rise with the others' (beta_other > 0).
- The XM wall component (ceiling 0.43-0.46) is therefore unproven: it bounds predictors that treat the carrier as a coin.

### 2. The size coin is partly the carrier

The large share is a per-wallet setting: DS 5%, GF 30%, XM 32% on 10-19..22. The "both-large co-occurrence 1.68x" is what bursts
routed to GF / XM produce. If the dispatcher is decoded, E[size] follows from the routing, so part of the condition-5 size coin is
the same mechanism as the condition-7 wallet coin.

### 3. The cancel race also limits a replay, not only a predictor (checked; this narrows convention (b))

`leftover.py` uses 10-20: 27,008 operator taker orders in 265 windows, the TRUE decisions, size E[menu], and a fill simulated as a
strict execution on the recorded L2. The fill is min(E[menu], ask depth ≤ L) at m - x.

| fill rule | window taker-net r | per-order r(fill) |
|---|---|---|
| unit size | 0.553 | |
| E[menu] alone | 0.537 | |
| depth at m - 180 | 0.572 | 0.21 |
| depth at m - 50 | 0.592 | 0.45 |
| depth at m - 35 | 0.590 | 0.47 |
| depth at m - 20 (includes the match itself) | 0.366 | |

Executing on the book the order actually met adds only +0.02-0.05 over the menu. Co-arrivals in the hold queue, fan-out legs on
the same leftover and the 50-ms grid leave the realized fill mostly unexplained even in a replay. "The fill is a coin" holds for
convention (b) too.

### 4. Smaller points

- **The PRNG test assumed one isolate.** prng15 treats same-ms copies as nearby calls of one Math.random stream. Up to 8 distinct
  filled orders of one (wallet, token) share a signing ms, at 1.63-1.70 ms per cent, and only 133 of 10,896 same-ms groups span two
  cents (`signrate.py`). The data do not yet separate "one fast thread with a per-cent timestamp" from "parallel signers (worker
  isolates), each with its own generator". The two need different groupings for the solver.
- **DS-XM window-net correlation by arm** (`netarm.py`): arm A -0.086, arm B +0.109. The A values are -0.084 / -0.105 / -0.030 on
  10-20..22 and the B values +0.140 / +0.199 / -0.011. It is weak and unexplained; XM's pairing does not differ by arm (below).

## Checked and not supported (so nobody redoes them)

- **No deterministic routing key** besides the known window-index arms (window mod 4: chi2 / dof 59; mod 12: 17). None of these
  exceeds chi2 / dof 2.8 (orders are not independent, so these are upper bounds; `cent.py`):
  - the limit cent mod 2 / 3 / 5 / 10;
  - the token;
  - the match ms mod 2 / 3 / 10;
  - the second mod 2 / 3.
- **No per-window cap or overflow by cumulative state.** P(XM) does not rise with DS's or GF's cumulative gross or |net| in the
  window. Window time alone gives AUC 0.593; adding the cumulative state gives 0.606 (`cap.py`).
- **XM is not an arm-specific pairing leg.** XM buys the running DS + GF long leg 44.8% (A) and 43.6% (B), falling from 0.54 to
  0.40 through the window. DS buys the other wallets' long leg 47-48% and GF 51-52% (`xmrole.py`).
- **No sign that makers see held orders** (`leak.py`, 10-21; 202,903 non-operator taker BUY matches with no ≥ 0.2-bp Binance spot
  mid move in the previous 1.5 s).
  - The touch depth falls from 0.93 at m - 300 to 0.85 at m - 150, then only to 0.81 at the match: no acceleration inside the
    hold. The placebo stays at 0.995-1.0.
  - The operator's own orders under the same filter fall from 0.64 at m - 200 to 0.23 at the match.
  - Caveat: 0.2 bp is coarse against the operator's 0.002-bp ticks, so the "quiet" set still contains trigger moves.
- **Strict execution at the match time does not rescue condition 5** (critique 3).

## Proposals (ranked by the chance they close the gap)

### 1. The carrier is a priority-slot dispatcher on the operator's own in-flight orders, with hidden occupancy (strong form of X55; tests the premise of X134 / X138 / X148)

**Hypothesis.** One decision stream. Each decision goes to the first free wallet in a fixed list (DS, GF, XM, possibly W4 / W5).

- A wallet is busy for the hold of its last submitted order, whether that order fills or loses its race.
- A "fan-out" is just consecutive decisions within one hold.
- XM is the overflow slot.
- Routing looked like a lottery because lost races (≈ 30% of decisions) and W4 / W5 legs occupy slots invisibly.
- Rival explanation, which the test must separate: XM is a slower or jittered path for random decisions.

**Why it fits.** Critique 1:

- the routing table (GF 93% with DS busy, XM 69% with both busy, XM 38% with only GF busy);
- the tenfold rise of P(XM) with local density;
- the drained book before XM-led first legs, which survives the composition and own-leg controls;
- regime12's beta_own ≤ 0 < beta_other;
- XM's broad, "earlier" knee profile.

**Test** (10-20..22 on the capture; replicate on the 11-01 06-12 development block with the shared recorder and the chain).

1. **Tick lock per carrier.** For each first leg, take the time t_k of the last Binance spot microprice tick toward o before
   m0 - 150 (exchange clock, on the 131-ms transit). Compare the distribution of m0 - t_k by carrier on a 10-ms grid.
   - Overflow: XM's distribution is as sharp as DS's (~230-260 ms) but locked to a later tick of the same move.
   - Slow path: it is shifted by a constant Δ or broadened.
2. **Hidden-occupancy census.**
   - Locate unfilled operator decisions as bid insertions of the day's menu sizes (30 / 100) at the ask the bot saw. They appear
     about arrival + 150 ms with no trade: in the ingested ask book, as o' asks at 1 - L. Use X86's finder (88-97% on known
     remainders).
   - Attribute them to wallets where a later maker fill or cancel reveals the order.
   - Add W4 / W5 matches from the chain logs.
   - Compare their rate in the 150 ms before XM-led versus DS-led first legs, matched on the drain state at m0 - 250 and on
     window time.
3. **Fit the dispatcher** with the hidden occupancy:
   - grid the busy window H over 120-200 ms;
   - search the priority order π over permutations of up to 5 wallets;
   - report carrier accuracy per day and arm against 72% (fills-only priority) and 63% (always DS).
4. **Does the same occupancy gate the take?** Measure P(take | top-hazard instant) at matched burst state, by the number of
   occupied slots (X72).

**Data.**

- `it15` L2: ask side at event level. Re-ingest with sizes per event, or use l2ingest15 with a finer grid.
- `fills.parquet` (both roles) and the calldata sample (order hashes of maker-first orders).
- W4 / W5 OrderFilled logs from polyrea's chain adapter.
- `it13/hf_dl/btc_*`.
- For replication: the shared recorder's `clob_crypto`, the chain and `btc5m_bnspot2` on 11-01 06-12.

**Signature if true.**

- Carrier accuracy ≥ 90% with hidden occupancy (72% from fills alone).
- ≥ 70% of XM-led first legs are preceded by hidden DS and GF occupancy, against ≤ 20% of DS-led ones.
- XM's tick lock is as sharp as DS's.

**If false.** XM's tick lock is shifted or broad, with no hidden-occupancy excess. XM is then a slower path for lottery decisions.
Write the measured Δ and its jitter into the condition-7 wall account, and the ceiling stands.

### 2. Condition 7 (and part of 5) through a replica that simulates its own occupancy on the recorded book (new; the payoff of proposal 1)

**Hypothesis.** A replica that routes its OWN decisions through the decoded dispatcher predicts each wallet's lean far better than
any thinning P^.

- Its own lost races follow from its arrival time on the recorded book; X93 found the race close to deterministic, with a 4-7%
  flip rate at a 25-50 ms timing error.
- Overflow happens in public bursts: dense top-hazard bins and a drained book at e.
- So the replica's XM and GF decisions coincide in time with the operator's.
- E[size | carrier, menu, arm] then also follows the routing (critique 2).

**Why it fits.**

- thin15's best P^ (AUC 0.79) has no occupancy or burst-density inputs and is match-anchored.
- The drained-book signal at m0 - 250 is public before XM's view.
- XM's share is 3-9% / 8-14% / 35-41% by local density.

**Test** (fit 10-20, score once on 10-21..22; pre-register first).

1. **PIT allocation model at the decision clock.** Among the operator's decision bins, estimate P(XM | state at e), with:
   - spot features;
   - o's near-touch depth and its 100 / 250-ms changes, cut at e;
   - the count of top-hazard bins in [e - 300, e);
   - the replica's own simulated occupancy from its own decisions and the book-resolved races.

   Report AUC against thin15's 0.67 / 0.79.
2. **Oracle ceiling.** Run the dispatcher on the TRUE decision stream (true decisions, simulated occupancy) and recompute thin15's
   XM and GF ceilings.
3. **Per-wallet trackers.** For each wallet w, lean_w = Σ over bins of hazard x P^(w) x E[size | w, menu, arm] x side. Report
   window-PnL r per wallet and per half, and the pooled r with the carrier-based E[size].

**Data.** `model_it14_hazard_full.txt` with all-bin scoring, the capture L2 grid for 10-20..22, `dcfit14_pred`, `fills.parquet`,
the calldata menus, and the proposal-1 dispatcher.

**Signature if true.**

- PIT allocation AUC ≥ 0.85.
- Oracle-dispatcher ceiling for XM ≥ 0.6 (thinning gives 0.46).
- The XM and GF trackers reach r ≥ 0.47 on both halves.
- Pooled window-net r rises by ≥ 0.03.

**If false.** The allocation at e stays ≤ 0.8 and the per-wallet r stays below 0.47. Condition 7 is then a measured limit of the
occupancy coin, which is set by the makers' cancel race (lost races). Write it as such.

### 3. The operator's versions are dispatcher configurations: XM's 10-14 step and its 10-31 "late leg" role (strong form of X9 / X122 step 1; exam transfer)

**Hypothesis.** The allocation "versions" are changes of the slot list or the hold length, not per-wallet probabilities:

- XM's fills step from 19-20k a day (10-09..13) to 1.6-3.1k (10-14..22);
- they rise again to about 10k a day on 10-31, "mostly as the late leg";
- the 10-21 16:00 .. 10-22 13:00 dispatch phase (DS share A / B 0.685 / 0.426).

A frozen rule that hard-codes the VALIDATE routing fails condition 7 on any lot where the list changed.

**Why it fits.**

- XM's volume steps are discrete.
- The routing table is sharply state-dependent (critique 1).
- The arm-dependent DS share in the dispatch phase.
- W4 / W5 run the same bot and are candidate slots.

**Test.**

1. Rerun the conditional routing table (`slots.py`, with W4 / W5 matches added from the chain) per day:
   - BUILD 10-09..16 (`fills.parquet`);
   - VALIDATE;
   - the post-T0 development blocks 10-31 00-06 and 12-18, and 11-01 06-12.
2. Run a change-point search on P(XM | DS busy, GF free) and P(XM | none), and on the implied priority order.
3. Date W4's and W5's first and last activity against XM's steps.

**Data.** `fills.parquet` (BUILD and VALIDATE), polyrea chain logs for W4 / W5, the development blocks after T0.

**Signature if true.**

- Before 10-14, XM sits second in the list: P(XM | DS busy, GF free) is high.
- From 10-14, GF is second and XM third, or W4 is inserted ahead of XM.
- The order changes again by 10-31.

The rule then needs the slot list as a version parameter, and the exam's lot-half replication (condition 7) must be checked for a
change inside h1.

### 4. The salts come from more than one generator: regroup the PRNG solve by signer, not by millisecond (strong form of X149 / X105)

**Hypothesis.** The ladder is signed by parallel signers: Node worker_threads, each with its own V8 isolate and Math.random
state, or separate processes.

- The copies of one cent in one ms are one call from each of several streams, not nearby calls of one stream.
- So prng15's copy groups are inconsistent by construction.
- Each signer's stream runs ACROSS cents at about 1.66 ms per cent.

**Why it fits.**

- Up to 8 filled distinct orders of one (wallet, token) share a ms, and copies of a cent share one ms in 97% of cases.
- 1.63-1.70 ms per cent, with only 1.2% of same-ms groups spanning two cents.
- A single thread with ethers-v5 signing (~1 ms a signature) cannot produce that. One fast thread with a per-cent timestamp
  could; parallel signers would too.
- The solver recovers real Node output, so the failure is in the grouping or the runtime.

**Test.**

1. **Throughput fingerprint.** Regress ms per cent on the orders per cent that the day's menu and copy count imply: 2-size days
   against the 3-size day 10-16 (50 / 30 / 200), and the per-wallet copy maxima. A single thread scales with orders per cent;
   parallel signers are flat.
2. **If flat,** form chains: for each (wallet, burst, token), one salt per cent at Δt ≈ 1.66 ms. Then:
   - run the existing V8 GF(2) depth-first search over chain offsets (one or a few calls per cent);
   - validate by exact prediction of other filled salts of the burst (chance about 2^-38).
3. **If it scales,** the one-isolate grouping is right, V8 is closed, and only a non-V8 runtime (JSC / Bun, or a port to another
   language) remains. A CSPRNG then makes the coins unobservable, which closes X149 in the wall account.

**Data.** `calldata_sample.parquet` / `it15/cl_orders.parquet` (salt, sign_ms, wallet, token, price, size) and prng15.py /
v8real15.py.

**Signature if true.** ≥ 20 chains solve and are validated by held-out salts. The recovered streams then expose the size and take
draws (proposal 2 of iteration 14).

## Sources

- `NOTES.md` iterations 1-15 (findings 1-14 of iteration 15, and iteration-6 finding 1 on the rebate).
- `state.json`: catalog X1-X150, components and target_metrics.
- `FINAL_RULE.md` (VALIDATE metrics, known limitations).
- `panels/iter14_assumptions.md`; `panels/iter13_mechanics.md` (dispatch checks); `panels/iter11_assumptions.md` and
  `panels/iter10_mechanics.md` (copy-budget checks); `panels/iter12_information.md` (held-order leak check).
- `code/prng15.py`, `code/wave15.py`, `results/wave15.json`.
