# Panel after iteration 12: mechanics and on-chain forensics

Lens: how the orders are built, and what the cluster's own order flow shows when it is attributed exactly. The main
point of this report: the cluster leaves exactly identifiable *tracer orders* in the public book. These are its
imbalance-sized pairing bids, whose size is unique to 0.01 share. Every re-sign of a tracer is visible in the
full-depth recording as an exact size increment. They give the quote function uncensored, wallet-attributed and at
pass resolution, and nobody has used them yet. Written 2026-11-01, 03:10-03:55 UTC.

**Data I used.** Development data only:
- `dm_clob_raw` (own full-depth recorder; every price change with server ms), 10-31 15:00-18:00, through
  `live.iter_live`. The 14:00 file is unreadable after a corrupt gzip block (see Notes).
- Live calldata `calldata/live1031_*`, `liveall1031_*` (10-31 development block).
- STUDY calldata `b1_all_makers_study`, `b1_cluster_orders_study`, `b1_counter_study` (case by case is allowed).
- BUILD fills `cluster_btc5m_fills.parquet` and `it9/volhist_{build,study}`.
- Message-format check: about 25 s of the public CLOB market channel on a long-dated non-crypto market, which is not a
  unit of this strategy. It was a format check only and nothing from it was used.

I did not open `.cache/live/sealed/`, any sealed block, or VALIDATE case by case. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it12m\`:
`track_unique3.py` (tracer chains with a size placebo), `tracer_pass.py` (same-pass ladder around tracer re-signs),
`queue_order.py`, `cap_check.py`, `grid_check.py`, `ws_format.py`. Run them from the repo root, e.g.
`.venv/Scripts/python.exe <path>/track_unique3.py 1793458800 1793469600`.

## What my checks found

1. **Tracer orders exist and can be followed exactly through the book.**
   - Tracers are cluster BUY orders whose calldata original size is not a schedule size: the imbalance pairing bids
     (X92). They are 14.7% of STUDY filled orders, with 514 distinct sizes.
   - In the 10-31 15:00-18:00 recording, 62 such orders have their fill print in the trade stream.
   - Recognition: 95.2% of them have at least one add of exactly their size in the same market in the 120 s before the
     fill. A placebo size (size + 0.37) matches 3.2%.
   - Re-signs before the fill (exact-size adds): median 8 (q25 2, q75 18.5, p90 39).
   - The first add comes a median 9.6 s before the fill (q25 3.0 s, q75 25.6 s, p90 68 s), i.e. about one re-sign per
     1.2 s, the Chainlink pass rate.
   - Where it sits, measured against its own token's touch:

     | | median | q25 | q75 |
     | --- | --- | --- | --- |
     | first add | −10 c | −15.5 c | −2 c |
     | last add before the fill | 0.0 c | −1 c | |

   - Share of re-signs at or above the touch, per order: median 13% (q25 6.5%, q75 31%).
   - Successive re-signs move up 50% and down 40% of the time (per-order medians). The price span is a median 14 c
     (p90 51 c).
   - **So the pairing bid is not "placed at the market".** It rests 7-15 c below the touch, is re-priced about once a
     second in both directions, and reaches the touch only in the last second or so before it fills. Its filled limit
     looks like "the market" only because fills select the moments when it is at the touch.
2. **Tracers are rungs of the same ladder as the schedule orders (16:00-17:00; 42 orders, 497 tracer re-signs).**
   - Within ±20 ms of a tracer re-sign, a schedule-size add appears on the same outcome in 63% of cases and on the other
     outcome in 27%. This matches iteration 10's finding that a pass signs one outcome at a time.
   - The nearest same-outcome schedule rung is at exactly the tracer's price in 40% of cases and within a tick in 56%.
     The other common offsets are −1 c (13%) and −3 c (12%). Its size is 500 (46%), 62 (20%), 100 (16%) or 12 (10%).
   - When the other outcome's schedule rung is at its touch in the same pass (n 37), the tracer sits a median 7 c below
     its own touch (q25 −13 c, q75 −2 c), and the pair sum is a median 0.92 (q25 0.86, q75 0.97).
   - So a tracer's path is a clean sample of the under-held outcome's ladder level. Unlike the 500s, it is uncensored
     by the touch, uncontaminated (12% of exact-500 fills belong to other makers, X36) and attributable to one wallet.
3. **Nulls, so nobody re-runs them.**
   - **Maker array order is not time priority.** In 3,559 same-price groups with two or more timed non-cluster makers in
     one `matchOrders`, the maker array is in signing-time order 50.7% of the time (random). Multi-price groups are
     monotone 56%. The array therefore cannot bracket the cluster's posting time historically.
   - **The public stream carries no order identity.** Each `price_change` entry has a 40-hex `hash` that differs
     between the two mirrored tokens and has the format of the `book` message's hash: a book-state hash, not a 32-byte
     order hash. The size is the only identifier available, which is why tracers matter.
   - **No per-window position cap.** BUILD per-wallet max |Up − Down| quantiles at 25/50/75/90/95/99%:
     86 / 233 / 500 / 762 / 1,000 / 1,535 shares. The only modes are the rung sizes 500 and 1,000. The share of fills
     that add to the held side rises with the position: 0.80-0.88 above 1,500 shares, and 0.93 for the pooled cluster
     above 5,000.
   - **No signing budget.** Salt rate from the STUDY counter table (gaps 20-180 s): 7-29 orders/s at p10-p90 (2-54 at
     p1-p99) in every wallet. It is demand-driven with no ceiling, so cross-market contention for orders is not the
     hidden quote state.
   - **No grid / averaging down.** For held-side adds, price minus own VWAP has median 0.00 and is below the VWAP 53% of
     the time.
4. **What a "run" is.** BUILD successive same-token maker fills of one wallet are at the same price 76.5% of the time,
   with a median gap of 0 s (the same block second). Price falls 12.6% and rises 10.9%. So a run of 7.5-9.7 fills is
   mostly a handful of resting quotes, each consumed by several taker transactions in one block second. The per-fill
   side weights each quote decision by its taker multiplicity.

## Critique

1. **The quote decode is the bottleneck for every bar still reachable, and it has only been attempted with bad labels.**
   - The reachable bars:
     - the quote unit (0.75 now, needs 0.85);
     - print-level selection (0.81-0.83 with the oracle quote, X72).
   - The labels used so far have three defects:
     - **Censored.** Filled orders are at the touch by selection (78%, X33).
     - **Contaminated.** 12% of exact-500 fills are other makers' (X36).
     - **Ambiguous.** Remove/add pairing cannot say which wallet's rung moved (the X71 "ratchet" may be an artefact of
       this).
   - X19, X27/X30 and X80 fitted the level on these labels: within a tick 21-30%, skew R² 0.21. The iteration-9 M1
     proposal asked for the pairing bid's price at the add time on the live raw book (X92 steps 2-3). X92 was closed on
     fill-time limits only.
2. **The replay's pairing leg is built on a selection artefact, so "needs queue priority" is not yet an account.**
   - X124 places the pairing bid at the market because the filled limits are at the market (X92).
   - The tracer path shows the bid sits 7-15 c below the touch and reaches it only after the engine re-prices it there
     (finding 1).
   - The at-touch variant also loses (−$87k to −$236k). This fits a mis-specified price law better than missing queue
     priority.
3. **"Taker-chosen switches that follow no public input" were scored with a sign rule.**
   - The mechanics give a level-crossing rule instead. After entry the under-held ladder sits about 7-10 c under its
     touch, so a switch needs that ladder to reach the touch. That is a threshold on the size of the engine's edge for
     the under-held outcome (or a sweep down to it), not a sign change.
   - The 0.54 for later runs therefore says the sign is not the rule. It does not say the switch is random.
   - The run unit is also inflated by taker multiplicity (finding 4). The decision unit is the quote, i.e. the pass.
4. **The plan waits for data it already has.**
   - X128 (entry one-sided or not), the confound test of the after-entry branch and the X103 re-post race are
     scheduled for 11-01 06-12. `dm_clob_raw` 10-31 15:00-18:00 already holds every price change with server ms, and
     the tracers give the pass identity.
   - Note that `dx_clob` keeps schedule-size deltas only. Tracers exist only in full-depth recordings: `dm_clob_raw` on
     10-31 and any later full-depth run.
5. **Per-wallet replication is scored blind to the per-wallet ladder.**
   - The examiner checks every wallet within 3 points. Mo-money's deficit (X76/X91/X94) is still open because "filled
     orders alone are selected at the touch" (X94).
   - Tracers are wallet-attributed, since their size is the wallet's own imbalance, and they are uncensored. That
     removes X94's blocker.

## Proposals (ranked by the chance they close the gap)

### P1. Tracer orders: decode the quote function from the exact, uncensored price paths of the cluster's own unique-size orders (new identification; strong form of B3, X19, X27/X30, X80, X92 steps 2-3 and X50's "Tobit depth")

- **Hypothesis.** The engine prices all the rungs of an outcome's ladder with one function at each pass. The pairing
  bid is one rung of that ladder, at the same price as a schedule rung in 40% of passes and within a tick in 56%.
  - Its size is unique, so every re-sign is observed. Its price path (about 1 Hz, mostly below the touch) is therefore
    an uncensored, exactly attributed sample of the quote function.
  - One of five laws produces that path:
    - (a) a fair cap, F_CL(k, publish lag) − h(τ, vol);
    - (b) a mid-anchored skew, mid_ex + β(F_CL − mid_ex) − h;
    - (c) a complement lock, 1 − m − (the held outcome's top rung in the same pass);
    - (d) a cost lock, 1 − VWAP_held − m;
    - (e) a touch peg, touch − j ticks with j falling over time.
  - (a) and (b) are public; (c) and (d) are own state; (e) is market-only.
- **Why it fits.**
  - Findings 1-2.
  - The 500-based fits stop at a within-a-tick share of 21-30% (X19, X80) on censored, contaminated labels.
  - The quote-oracle ceilings say the bars are reachable only if the quote is decoded (X72).
  - The pair sum of 0.92 when the held side is at the touch fits (c) about as well as (a)/(b). Only the tracer path can
    separate them.
- **Test.**
  1. **Tracer table.**
     - Data: 10-31 15:00-18:00 (`dm_clob_raw`; `track_unique3.py` is the extractor), plus 11-01 06-12 if the full-depth
       recorder ran.
     - Take every cluster maker order with a non-schedule calldata size. Chain its exact-size adds and removes in the
       120 s before its first fill, with the side and price on its own token and the server ms.
     - Mark each re-sign's pass: the schedule-size adds within ±20 ms, and the RTDS publish and futures move that came
       before it.
  2. **Features at each re-sign.**
     - Chainlink value at each wallet's publish lag, Gamma strike, τ, v300, futures mid.
     - The own token's mid and touch with the tracer and the schedule-size levels removed, and the complement's touch.
     - Own state, labelled as such: the wallet's and the cluster's imbalance, held-side VWAP, and the held outcome's top
       rung in the same pass.
  3. **Fit and score.**
     - Fit laws (a)-(e) on 15:00-16:30 and score them on 16:30-18:00. Report the within-a-tick share and the MAE of
       re-sign prices.
     - Report the residual's structure: autocorrelation, dependence on own state, and a step at fills.
     - Then check the 11-01 06-12 off-session block.
  4. **Transfer to the 500s.**
     - Apply the best public law, with the fitted offset ladder (0 / −1 / −3 c), to the schedule rungs.
     - Score the pre-registered quote unit as P(law price ≥ best ex-cluster bid), against the activity baseline (0.68),
       on the later development blocks.
- **Data.** On disk:
  - `dm_clob_raw` 10-31;
  - live calldata;
  - `dm_rtds`/`dx_rtds`, `dm_bnf`/`dx_bnf`.

  Still to obtain:
  - the 11-01 06-12 full-depth recording;
  - pmxt hours of July (X87) for a version check. The July calldata shows pairing-class sizes (454.89, 370.17, ...),
    so tracers exist there too.
- **Signature if true.**
  - A public law ((a) or (b)) puts at least 60% of held-out re-sign prices within a tick, against 21-30% for the
    500-based fits. Its residual shows no own-state structure.
  - Transferred to the 500s, it lifts the quote unit to ≥ 0.85 with a gain of ≥ 0.05 over activity. That is the
    pre-registered claim.
  - If only (c) or (d) fits, the quote level is own-state. Then the presence gap's quantitative account is the share of
    level variance that own state carries.
  - If nothing fits beyond 30%, the level has a hidden state, and the tracer residual measures it exactly.

### P2. The run switch is a level crossing of the under-held ladder into the touch, not a posture flip (strong form of X129, X85 and X125; the side after entry)

- **Hypothesis.** After entry the held outcome's rung sits at the touch and the under-held ladder (tracer and rungs)
  rests h ≈ 7-10 c below its touch. The fill side switches when one of two things happens:
  - **(i) Quote move.** The engine's price for the under-held outcome rises to its touch: F_eng(under) − h ≥
    touch(under). This is a threshold on the size of the edge, with h measured from the tracers.
  - **(ii) Sweep.** A taker sweep pushes the under-held touch down to the resting ladder. That is the taker's choice.

  A sign rule cannot see (i), which is why the later runs score 0.47-0.54 (X129).
- **Why it fits.**
  - The tracer's first add is 10 c under the touch and its last add 0 c, a median 0.5 s before the fill (finding 1).
  - The pair sum is 0.92 with the held side at the touch (finding 2).
  - X85's live inertia band (theta 0.05) is the shadow of a threshold.
  - X125's band was a band on |fair − mid| per fill, scored against cheaper-side or flow rules, not on the under-held
    ladder against its touch.
- **Test.**
  1. **Classify every switch (10-31 15:00-18:00).**
     - Use the tracer and the schedule-size ladder (P1's table) together with the trades.
     - (i): the under-held ladder's last re-sign before the switching fill moved up to the touch.
     - (ii): the ladder held its price and prints swept the touch down to it.
     - Report the shares, and for (i) the public trigger of the pass.
  2. **Historical rule (no books).**
     - On the lot, at each fill of a run, predict a switch when F_CL(under) − ĥ ≥ (last clean trade(under) − 0.01) on
       the in-block clock.
     - ĥ is fixed from the tracer depths of step 1, or chosen on STUDY over {0.03, 0.05, 0.07, 0.10}.
     - Score the later runs and the per-fill public side on VALIDATE (aggregate).
- **Data.** P1's tracer table; the lot calldata, the in-block clock and the fetched Chainlink seconds (all on disk).
- **Signature if true.**
  - (i) carries at least 70% of the switches, and the threshold rule scores ≥ 0.70 on the later runs on VALIDATE
    (from 0.54), with the per-fill public side ≥ 0.76 (from 0.69).
  - If (ii) dominates, the switches are taker sweeps. The side bar is then capped by the entry share, and the measured
    sweep share is the quantitative account.

### P3. Replay the pairing leg with its tracer-decoded price law instead of "at the market" (strong form of X124, X106 and X92; the outcome gap)

- **Hypothesis.** The replay's locked pairs lose (−$106k to −$236k, or −$87k at the touch, against +$38.1k for the
  cluster) for a specific reason. Its pairing bid sits at the touch from its first second, so every adverse
  trade-through fills it. The real bid rests 7-15 c lower and is re-priced up to the touch only when the engine's price
  for the under-held outcome rises. Its fills are therefore conditional on a favourable re-price, and the pairs it
  locks cost less than 1.
- **Why it fits.**
  - Finding 1.
  - X92's pair cost below 1 in 61-72% of pairing fills.
  - The at-touch replay variant also loses, which argues against queue priority as the missing piece.
- **Test.**
  - In `code12/replay_machine.py`, replace the pairing leg's price by P1's best law (and, separately, by the empirical
    tracer depth profile: depth versus time since the imbalance changed).
  - Re-price at each Chainlink report on the in-block clock, post-only, with strict trade-through, size = own
    |imbalance| and latency 2 s as before.
  - Choose on STUDY, then score VALIDATE in aggregate, per wallet and per half.
  - Report locked and residual PnL, the window correlations, and the oracle-side ceilings with and without the leg.
- **Data.** P1's law; the on-disk replay inputs.
- **Signature if true.**
  - The replay's locked-pair PnL is ≥ 0 on STUDY and VALIDATE.
  - The oracle-side ceiling with the leg rises above the one-sided 0.47 / 0.53.
  - The executable posture replay rises above R7's 0.207 / 0.218.
  - If the decoded law still loses, "queue priority" becomes a measured account, with the law in hand.

### P4. Per-wallet ladder parameters from wallet-attributed tracers: mo-money's deficit and the per-wallet replication condition (strong form of X94, X76 and X91)

- **Hypothesis.** The three engines share the price law but differ in one or two parameters: publish lag, skew β,
  half-spread h, or re-sign cadence. Mo-money's posture deficit is one of those parameters, not a different input.
  - The 500 triplets cannot be attributed to a wallet in the book.
  - A tracer can, because its size is that wallet's own imbalance.
- **Why it fits.**
  - X94 stopped because "filled orders alone are selected at the touch". Tracers remove exactly that limitation.
  - X76 found different per-wallet Chainlink delays (bosona 1,083 ms, almach 1,432 ms; mo-money undecided).
  - The examiner scores each wallet with ≥ 300 fills within 3 points.
- **Test.**
  - Split P1's tracer table by maker.
  - Per wallet:
    - re-sign times against RTDS publishes (an exact pass lag);
    - P1's law with a wallet-specific (lag, β, h), tested for equality across wallets with a likelihood-ratio test.
  - Then apply the per-wallet parameters to that wallet's lot fills (posture per wallet) and to its quote unit.
- **Data.** P1's table; the dm/dx RTDS recordings.
- **Signature if true.**
  - One parameter differs significantly for mo-money (e.g. h or lag) and the others are equal.
  - With it, mo-money's posture moves within 3 points of the other two on the live block and on the lot.
  - If the parameters are equal, mo-money's deficit lies in its queue position or fills, not its quote. X98 already
    argued this; it would then be measured.

### P5. Quoted but unfilled: the complete pairing-bid process from the imbalance path, and the fill hazard at the touch (strong form of X32, X72's two-stage presence and X23)

- **Hypothesis.** Every change in a wallet's imbalance produces a pairing bid of the new |imbalance| within about one
  pass. That bid lives until it is filled or until the imbalance changes again. The process can be reconstructed in
  full: its existence is own state, its price is P1's law, and its fill hazard given at-touch time depends only on
  public taker flow. That splits fill presence for this order type exactly into "quote at the touch" and "taker
  arrives".
- **Why it fits.**
  - The size is predictable from public activity (the wallet's own fills), so even the unfilled tracers can be found.
    Calldata only ever shows the filled ones.
  - The quote-oracle ceiling (0.80) has never been decomposed with an exact quote.
- **Test.**
  - From the 10-31 development activity, compute each wallet's imbalance after each own fill.
  - Search `dm_clob_raw` for adds of exactly the new size on the under-held outcome in the following 5 s, and chain
    them until they disappear without a fill.
  - Measure:
    - the share of imbalance changes followed by a tracer, and its latency;
    - the lifetime, the seconds at the touch, and the cancel reason (imbalance change or window end);
    - P(fill | at the touch) per second, as a function of the public taker flow in the next 1 s.
  - Report the two-stage presence AUC against the oracle ceiling.
- **Data.** Development activity (data-api, clamped to 10-31 12-18) and `dm_clob_raw`.
- **Signature if true.**
  - At least 90% of imbalance changes get a tracer within 1.5 s: a deterministic existence rule.
  - The fill hazard at the touch is explained by public flow alone, with an AUC of the second stage ≥ 0.85.
  - The presence account for this order type is then exact: the quote (P1) times public taker flow. The same
    decomposition, applied to the 500s with P1's transferred law, gives the gap's exact budget.

## Notes for the RE

- **`tools/live.py` bug.** `iter_live` catches `EOFError` and `OSError` but not `zlib.error`. The file
  `.cache/live/dev/dm_clob_raw/20261031T14.jsonl.gz` raises "Error -3 ... invalid block type" partway through, and that
  aborts any iterator spanning that hour. My scripts wrap `iter_live` per hour and catch `zlib.error`. The 14:00 hour is
  readable only up to that block. Record this in NOTES; it is not my file to fix.
- **Overlap with the information panel.** I12-1 reads the touch state S(t) from schedule rungs at the touch. P1-P2 add
  what S(t) cannot see: where the cluster's ladder is when it is not at the touch, attributed per wallet and per pass.
  Run P1 first. Its tracer table also gives I12-1 an exact pass clock.
- **Disk and memory.** One hour of `dm_clob_raw` streamed by `track_unique3.py` peaks at under 300 MB. The tracer
  deltas are tiny, so filter by the target sizes while streaming.
- **Recorder.** Any recorder that keeps a full-depth view for the coming development blocks must keep every size
  delta, not only schedule sizes, within at least 0.15 of the touch; otherwise the tracers are lost. For scale:
  `dm_clob_raw` at full depth was about 22 MB/h compressed for the three BTC markets. A 0.15 band should need a
  fraction of that (my estimate, not measured). Check this against the 300 MB cap before starting a run.
