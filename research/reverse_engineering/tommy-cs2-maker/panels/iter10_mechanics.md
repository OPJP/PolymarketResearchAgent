# Panel, iteration 10: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built, how the 1-s in-play delay shapes who gets filled, and which decisions carry the
per-market PnL.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 10 in full, iterations 1-9 by section;
- state.json: the catalog A1-X143, the components, the target metrics and the strategy statement;
- FINAL_RULE.md, by section;
- panels/iter9_mechanics.md in full, and the proposal headings of every earlier mechanics panel;
- panels/iter10_assumptions.md and panels/iter10_information.md, to avoid duplicating them (see "Overlap").

There are no EXAM or wall-audit files. `tools/sealed.py tommy-cs2-maker` reports no released lots, the future examined
up to 10-31 00:00, and the current block (11-01 00-06) sealed.

Every record I read is development data: the on-chain tables of 16-22 Oct (`orders`, `calldata_all`, `calldata_pub`,
`ledger_rows_iter10`, `per_market`, `activity_dev`, `markets_dev`). All signing times are before H. I opened nothing
in `.cache/live/sealed/`, read no live recording, called no endpoint, and wrote nothing outside this file. My scripts
are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m10\`:
`pack_lag_edge.py`, `ladder_ceiling.py`, `phase_lock.py`, `map_break.py`, `receiver_print.py`, `decay_rule.py` and
`chop.py`. A few more checks ran inline. Each ran in under 5 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The outcome bound never sampled the lags that the 1-s delay creates

X138 moves the taker leg to three lags: its block + 1 s, its own block, and its own block + 2c. Each of these is at
least 2.4 s after the decision. But the in-play delay holds every taker until about +1.04 s, while maker posts and
cancels act at once. The message becomes public on the book at +17 / +67 / +124 ms after the wallet signs (p10 / p25 /
p50 of other makers' cancels on the server clock; the iteration-3 lead table). That is long before any informed take
executes. A public reaction at +100-400 ms is therefore a different regime from block time, and nobody has measured
it:

- X80 step 3 (latency sweep) was not run;
- X57 step 5 (live-book variant) was not run;
- iteration-2 plan item 4 (an executable collapse-taker leg on recorded books) was dropped when the collapse clock was
  retracted. That retraction concerned the wallet's input. It says nothing about a public rule's trigger.

What the on-chain record already says about the remainder after the wallet's take (`pack_lag_edge.py`; 1,682 in-play
takes; other takers' BUY FAKs on the same token, matched by signing ms):

| Follower signing lag after the wallet's take | (0, 100] ms | (100, 300] ms | (300, 1000] ms |
| --- | --- | --- | --- |
| Follower orders | 116 | 414 | 971 |
| Fill fraction (median) | 0.76-0.92 | 0.93-1.00 | 1.00 |
| Executed at or below the wallet's own limit | 40% | 36% | 52% |
| Executed within its limit + 2c | 73% | 62% | 77% |
| Median price vs the wallet's VWAP | +1.1 to +2.7c | +1.2 to +2.5c | +1.0c |

- Volume bought by followers at or below the wallet's limit: 19k shares within 100 ms, 28k within 300 ms and 100k
  within 1 s. The wallet's own take fills total 320k shares.
- Only 16% of its takes have any same-token follower within 300 ms.
- So almost nobody competes for the stale remainder before +300 ms. A public FAK there would mostly face the slow
  makers' leftover orders.
- What decides feasibility is the consumed-side depth between +1.04 s and +1.04 s + Δ with the wallet's own fill added
  back. X25 measured the depth only up to +1.04 s (1.00 → 0.66 at +0.1 s → 0.13 at +1.0 s).
- The settlement edge per follower bin is too noisy to use (equal-weight +2.0c / -2.1c / +2.3c, 95% intervals about
  ±10c). A markout or next-jump measure is needed.

A warning for the replica: per-market pair cost is not a public path property. Per market, 1 - pair cost has these
Spearman correlations:

- with the public in-play oscillation of the tape (total variation minus net move, at 1-min steps): -0.07 (BUILD) /
  -0.05 (VALIDATE);
- with the wallet's taker share of shares: 0.09 / 0.04.

Yet 1 - pair cost correlates 0.58-0.59 with the per-market PnL. Oscillation explains the paired volume instead
(0.66 / 0.69).

A public maker, however well protected, will therefore copy the volume channel: X82's prints baseline, 0.51 / 0.37,
and my oscillation × prints index, 0.43-0.47 Pearson / 0.23-0.27 Spearman. It will not copy the wallet's pair cost.
Spearman is the coefficient at risk.

### 2. Two numbers in the wall account are fill-selected

The assumptions panel (its check J) makes the same point. Here is the point-in-time number:

- **Own previous level.** The frozen "own previous level" anchor is the previous filled order on the token by signing
  time (`a_own = shift(1)`): 0.509 / 0.513 within one tick (BUILD / VALIDATE). Restricted to the wallet's own fills
  that were on chain before the signing, it scores 0.247 / 0.264 (coverage 0.96). That is below the last print
  (0.305).
- **Persistence and the oracle union.** The 0-2-s persistence (0.716) and the oracle union (0.599) inherit the same
  selection. Adjacent ladder levels are often filled by one sweep:
  - 28% of filled orders share a 30-ms signing burst with another filled order;
  - multi-fill bursts span 1c in 64% of cases and 2c in 20%.
- **Sweep structure.**
  - 81% of the wallet's maker fill rows are its highest-priced order hit in that transaction; 12% are one level
    below.
  - Bursts are signed top-first: in 88% of bursts with at least 3 filled orders, price falls along the signing order,
    and in only 1% it rises.
  - Consecutive orders of a burst are signed 0 ms apart (median; p90 5 ms).

Both numbers describe sweeps, not the bot's state at signing. The strategy statement, FINAL_RULE.md and the wall
account should quote the point-in-time 0.25-0.26, or the live-book own state, instead of 0.500 / 0.599.

### 3. The historical price plateau is reached in silence, and it is low

Within one tick of the last print, by time since the last wallet-independent message (VALIDATE + BUILD ledger rows):

| Time since the last message | Within one tick | Median offset from the print |
| --- | --- | --- |
| < 0.15 s | 0.14 | 6c |
| 0.15-1 s | 0.20 | 5c |
| 1-5 s | 0.16 | 6c |
| 5-15 s | 0.29 | 3c |
| 15-30 s | 0.33 | 3c |
| 30-60 s | 0.38 | 2c |
| 60-120 s | 0.41 | 2c |
| 120-300 s | 0.38 | 2c |
| > 300 s | 0.34 | 2c |

- The private part decays as the market catches up (half-life about 5-15 s). The plateau, about 0.4, comes from the
  ladder slot and the stale print, not from V.
- Map breaks give the same picture. On match-market orders signed 60-240 s after the previous map's last print (182
  orders, 45 events), the last print scores 0.47. A naive BO3 series value built from the next map's last print scores
  0.04-0.08 (rough: equal per-map strengths assumed).
- A point-in-time decaying adjustment does not help (`decay_rule.py`). The rule is the last print + δ·exp(-age/τ),
  with δ signed by the token P4e bought and age measured from P4e's block time; BUILD fit δ = -3c (hurt) / +1c
  (helped), τ = 30 s. It scores 0.310 on VALIDATE against 0.305 for the last print (0.273 vs 0.255 on the 27% of
  orders that have a public P4e take less than 60 s old).

No examinable h1 / h2 price rule is left in this direction. The open question is whether 0.8 per order is reachable
even with V known (proposal P2).

### 4. Negative checks, so nobody redoes them

- **No hidden periodic requote clock.** Quiet-class maker signings are not phase-locked to any period from 0.1 to 10 s.
  Per event, the median Rayleigh Z is 0.83-1.17 (uniform: 1), and at most 1.3% of 79 events reach Z > 9.2. Their ms
  within the second are uniform.
- **The merge loop does not block quoting.** Around the first merge of each of 739 passes, maker signings run at
  6.2 / 5.6 / 5.3 / 5.6 / 5.8 per minute (-120..-60 / -10..0 / 0..10 / 10..30 / 60..120 s); inside multi-merge passes
  the rate is 8.1. Taker signings are flat at 0.35-0.49 per minute.
- **No capital gating by concurrency.** The event start size (median of the first 10 maker orders, 77 events) against
  the number of other events quoted in the previous 10 min: Spearman -0.14 (p 0.22).
- **Receiver-made prints are no better anchors.** The last on-chain bid-hit print by a Feed-P maker receiver
  (0xed446954, 0x2005d16a, 0x68915897, 0x52661b8e, ...) that is at most 10 s old scores 0.35 / 0.36 within one tick.
  Any maker's print scores 0.35 / 0.33 and a non-receiver's 0.33 / 0.31. The merge-law siblings (0x52661b8e,
  0xf1f2b3c6) score 0.43 / 0.41 but cover 0.4% of orders.

## Proposals, ranked by the chance they close the gap

### P1. The take and the repair at public sub-second lag: the stale-remainder survival curve and a three-leg replica (outcome; strong form of X138 and X80 step 3, complementing information P3 and assumptions P3)

- **Hypothesis.** The wallet's message machine has three legs, all inside the 1-s delay window:
  - the FAK take at +50 ms;
  - the hurt-side pull at +11-19 ms after its take;
  - the complement repair at K - L, about 1.04 s after the take.

  X138's "the outcome needs the +50-ms timing" was measured only against lags of 2.4 s or more. If the stale remainder
  survives to +1.04 + Δ s for Δ up to about 300 ms, then:
  - a public trigger (the first non-own cancels of the wave) can place the take and the repair at Δ;
  - the taker-timing part of the outcome wall becomes a public-book latency problem;
  - only the maker value V stays private.

  If the remainder is gone within 100 ms of the wallet's match, the wall is exact: the outcome needs an input less than
  X ms after the message.
- **Why it fits.**
  - Critique 1: followers before +300 ms take only 9% of the wallet's volume at its limit, and only 16% of its takes
    have one.
  - The informed takers' FAKs all wait until at least +1.04 s.
  - The wave is public from +17 ms (server time).
  - The real taker leg turns A (0.43 / 0.33) into E (0.87 / 0.80).
  - X57 step 4: the oracle re-pair alone lifts a public ladder from +0.09 to +0.26 Pearson.
  - Neither other panel covers the take or the repair. Information P3 replicates only the maker pull, and assumptions
    P3 delays the wallet's own decisions as a bound.
- **Test.** Run one grid that also hosts the other two panels' outcome proposals.
  1. **Historical feasibility (validated X57 engine, 229 markets, BUILD / VALIDATE).**
     - Maker leg M: A (the wallet's own orders), D (the public ladder), D + full hurt-side pull at message + Δ with
       re-post after 1.5 s.
     - Taker leg T: real; sign + Δ for Δ in {50, 100, 200, 300, 500, 1000} ms; block.
     - Repair R: none; the real repairs; the repair at the leg's own match + 1.04 s, priced at K - L (K = 0.94).
     - A shifted take is matched at sign + Δ + 1.04 s against the engine's resting set. The wallet's own take is
       removed, every other signer is processed in signing order (P4e and 0x2005d16a before it, the followers by
       their real ms), and the limit premium and size cap are the wallet's.
     - The message clock is iteration 10's wallet-independent one (6,628 messages).
     - Report per-market Pearson / Spearman (event bootstrap), pair cost, residual and the share of the wallet's take
       shares refilled.
     - Bias note: the engine knows only filled orders, so this is optimistic about slow makers who would have
       cancelled after +1.04 s, and pessimistic about never-filled resting orders. Step 2 fixes both.
  2. **Survival on the recorded books (server clock; BUILD-live 10-31 12-18 `tommy_cs2_near`, then every VALIDATE-live
     block).**
     - At each wallet take, measure the consumed-side depth at or below its limit from +1.00 to +1.60 s in 20-ms steps,
       with its own fill added back.
     - Split what removes the depth into non-own cancels and other takers' fills, and give the depth left at
       +1.04 + Δ.
     - Run the same at P4e-only messages.
     - This is the curve that decides Δ_max.
  3. **Executable replica on recorded books.**
     - Detector, frozen on BUILD-live: at least 2 non-own decreases on one token's bid side within 40 ms, no trade,
       the wallet's sizes excluded by the validated label. Side = the token whose complement bids vanish. Kind filter =
       reversal (the previous burst was on the other team; X99 / cosigned_kind).
     - Report recall and precision against the wallet's takes and against P4e messages, and false alarms per minute
       in retail busy phases.
     - Latency: receive at server ts + 150 ms, order arrival at decision + 150 ms; also 300 and 500 ms.
     - The take is a FAK at the stale ask + the wallet's median premium, size 0.3x the pre-event depth, matched
       against the recorded book at arrival + 1.0 s minus the depth already consumed. The repair follows the take's
       own match. The maker leg is the frozen live join ladder with the pull.
     - Pool the development blocks before any verdict.
- **Data.**
  - On disk: `engine_check_rows`, `knockout_markets`, `calldata_all`, `calldata_pub`, the ledger message clock,
    `level_events_dev`, `linked_adds_dev`.
  - To come: `tommy_cs2_near` on the VALIDATE-live blocks (11-01 06-12, 11-01 18-24, 11-02 00-06, ...). Its hard stop
    is 11-03 00:00 UTC, so extend it before the future-block exam if this rule is frozen.
- **Signature if true.**
  - The A × T(Δ ≤ 300 ms) cell keeps at least 0.75 / 0.65 (E is 0.87 / 0.80, block 0.60 / 0.40).
  - The survival curve keeps at least 50% of the wallet's refill at Δ = 300 ms.
  - Then the taker timing is public for the future-block exams, and the wall shrinks to V.
  - If the fully public cell (D + pull, T(Δ), R) also reaches 0.5 / 0.5 on VALIDATE and on pooled VALIDATE-live, the
    outcome item is executable on books. Tag the take as a public proxy of the private message, report its overlap
    with the wallet's takes, and report a wave-only baseline, because the examiner may call it co-occurrence.
  - Expected from critique 1: the D cells plateau near the volume channel (Spearman 0.2-0.4). That ablation itself
    says the remaining outcome gap is the maker price.
- **Signature if false.**
  - A × T(100 ms) falls to block level (≤ 0.65 / 0.45), or the survival curve loses more than 80% of the refill by
    +1.14 s.
  - Then the outcome wall reads: the remainder is gone X ms after the wallet's match, which is less than the earliest
    public trace plus network.
  - This is the quantitative statement that auditors need.

### P2. The per-order price ceiling with the wallet's own value known: a ladder-slot account and the decision unit (price; strong form of the iteration-7 "set problem" and X108's oracle union)

- **Hypothesis.** Even an oracle that knows V exactly cannot predict 80% of the wallet's orders within one tick. Each
  add fills one of about six slots below V, and the slot is chosen by ladder state that the examiner cannot see
  historically. If so, item 4 at the per-order unit is structurally out of reach for this bot. The decode target then
  becomes the top-change decision (the touch already scores 0.63 there) plus a slot policy.
- **Why it fits.**
  - Adds spread almost evenly over 0..-5c from the touch (iteration-7 panel: 17.6 / 14.8 / 10.4 / 10.8 / 16.5 / 8.1%,
    and 10.2% at +1c).
  - Own bursts on the live book have a median of 1 level (mean 1.9), so a slot is chosen per add, not per ladder.
  - X108: own top within one tick of only 0.246 of adds; an oracle choosing among four slot rules reaches 0.726.
  - Critique 3: even 60-300 s after a message, the public plateau is about 0.4.
  - Critique 2: 81% of fills hit the wallet's top at fill time but not at signing.
  - The ceiling with V known has never been measured. Without it, "price not decoded" cannot be told apart from
    "price unscoreable per order".
- **Test (BUILD-live fit, VALIDATE-live scoring; validated own-add label).**
  1. **V oracle.** Take the wallet's top on the token after the burst; also the top before the burst, and the next top
     change within 2 s. All are own state read off the live book.
  2. **Target.** The add's slot offset from the V oracle, in whole cents (-8..+3).
  3. **Classifier.** LightGBM multiclass using:
     - own ladder occupancy (slots held relative to the top, their ages, the slot of the last own fill and the last
       own cancel, the 1.5-s timer state);
     - others' book (gap to others' best, sizes at and ahead of each slot);
     - time since the last wave;
     - own inventory.
     Score within one tick on held-out events, for every add and for linked filled orders. This estimates the best a
     rule can do with V known.
  4. **Decomposition.** Report misses by slot class (top change, refill, deeper add).
  5. **On chain, for h1 / h2.** Report the same oracle at fill time (93% of fill rows lie within 1c of the wallet's
     highest order hit in the transaction) against signing time, to show how much of the gap is signing-time slot
     choice.
- **Data.** `level_events_dev`, `linked_adds_dev`, `own_bursts_dev`, the validated label (X92), `calldata_dev`, the
  VALIDATE-live blocks, `calldata_all`.
- **Signature if true.**
  - The ceiling with V known is below 0.8 on adds and on fills (expected 0.5-0.7).
  - Write the number into the wall account as a structural limit of the per-order price item for a multi-slot ladder.
  - Report the decision-unit result next to it: top changes, touch 0.63, plus the slot classifier's accuracy given V.
  - Ask the user whether the examiner may score the top-change unit. This is a target definition, not a narrowing:
    every order belongs to exactly one top state.
- **Signature if false.** The ceiling is at least 0.8. V is then the only blocker, and the information search (X133,
  X118) stays the priority with a known payoff: the price item passes as soon as V is found.

### P3. Localize the outcome item by decision class: a class-wise knockout of the wallet's own record (outcome and price priorities; strong form of X124 and X137)

- **Hypothesis.** The per-market Spearman is carried by one or two decision classes, not by the whole ladder.
  Candidates:
  - the message re-prices and repairs, about 8% of orders but 19% (repair) of maker PnL;
  - the quiet ladder, 71% of orders and 56% of maker PnL;
  - the endgame bids on the collapsing side.

  The quiet class is the most public-predictable (0.38-0.41 against the last print in silence; the touch is likely
  higher). If replacing only the quiet class by a public counterpart keeps the outcome at 0.5 or more, the outcome needs
  only the message classes decoded. If the quiet class carries it, the outcome is the price item, with no shortcut.
- **Why it fits.**
  - X124: the price level carries the margin, and windows do not.
  - X137 gives class shares of PnL, but not of the per-market correlation.
  - Per market, 1 - pair cost correlates 0.58 with PnL, and the loser / winner share ratio correlates -0.36 / -0.48
    (BUILD / VALIDATE). The winner and loser average costs move against each other (covariance about -0.015 against
    variances of 0.016).
  - Which decisions set the pair cost and the imbalance per market is unknown.
- **Test (validated engine, VALIDATE with BUILD as a check).** Start from E (own maker orders + real takes, 0.87 /
  0.80). Replace one class at a time, as split by the ledger (`ledger_rows_iter10.cls`) plus an endgame class (orders
  on the eventual loser below 0.15):
  - quiet orders → the public anchor (last print historically, the touch on live blocks), keeping their signing times
    and sizes;
  - message + follow orders → the same;
  - repairs → none;
  - endgame → stop at 0.15.

  Report per-market Pearson / Spearman, pair cost, the loser / winner share ratio and the residual after each
  replacement, and for pairs of classes. Give the Spearman loss per class with an event bootstrap.
- **Data.** `engine_check_rows`, `ledger_rows_iter10`, `knockout_markets`, `calldata_all`, `calldata_pub`; the live
  touch on VALIDATE-live for the live variant.
- **Signature if true (the outcome sits in a small class).** Replacing the quiet class keeps at least 0.5 / 0.5, and
  replacing the message or repair classes drops below. The outcome item then needs only the message classes: about 8%
  of orders, the ones P1's public sub-second triggers and the assumptions panel's synchrony clock aim at. Price work
  should concentrate there.
- **Signature if false (the outcome is diffuse).** Every single-class replacement costs more than 0.15, or the quiet
  class alone does. The outcome item is then the price item over the whole ladder, and P2's ceiling also bounds the
  outcome. The wall account should say so.

### P4. Make the wall account and the frozen rule examiner-proof: re-derive every own-state and fill-based anchor point-in-time (correction; affects X137, the strategy statement, FINAL_RULE.md)

- **Hypothesis.** Several headline numbers use the fact that an order was filled later, which is a censoring
  lookahead on h1 / h2:
  - own previous level 0.500;
  - persistence by gap 0.716 / 0.591 / 0.516 / 0.233;
  - the oracle union 0.599;
  - the linked-add 0.64 (already flagged);
  - assumptions check G's 0.65.

  An auditor will discount them, and the examiner cannot compute them.
- **Why it fits.**
  - Critique 2: the own previous level restricted to fills on chain before the signing scores 0.247 / 0.264.
  - Sweep co-fills explain the gap between the two versions (81% top-of-transaction, top-first bursts signed in the
    same ms).
- **Test.**
  1. For each anchor, compute three versions:
     - point-in-time on chain (inputs with block time ≤ signing);
     - own state on the live book (uncensored, BUILD-live / VALIDATE-live);
     - the current fill-selected version.
  2. Add a same-transaction exclusion (drop pairs filled in one sweep) to the persistence and oracle numbers.
  3. Replace the 0.500 / 0.599 citations in `state.json` (components.price, the strategy statement) and FINAL_RULE.md
     with the point-in-time or live versions.
  4. Keep the fill-selected version as a descriptive footnote only.
- **Data.** `orders` (`first_fill_ts`, `sign_ms`), `calldata_all`, the live-book own label.
- **Signature if true.** The point-in-time own-state anchors fall to the level of the last print or below, as found
  for the own previous level. The account then reads: no own-state anchor the examiner can compute beats the public
  print. On the live book own state is fully visible, and P2 measures how far it goes.
- **Signature if false.** A point-in-time own-state anchor keeps 0.45 or more. It is then the best examinable price
  rule for h1 / h2. Freeze it as own state, reported with and without own state.

## Overlap with the ledger, the catalog and the other panels

- **P1.**
  - What exists: X138 (lags of 2.4 s or more), X80 step 3 and X57 step 5 (not run), H62 (the wallet's own pulls,
    withdrawn), X26 / X67 (repair at K - L), and X57 step 4 (oracle re-pair).
  - The other panels: information P3 (a public maker with wave pulls) and assumptions P3 (own decisions delayed by L).
  - What is new: the public-lag take and repair, the stale-remainder survival curve after +1.04 s, and one grid that
    runs all three panels' outcome proposals together.
- **P2.**
  - What exists: the iteration-7 critique (set problem), X108 (oracle union of four slot rules, 0.726), X75 (top
    changes 0.628) and the iteration-9 information panel (oracle future mid 0.45-0.52).
  - What is new: the ceiling with V known, the slot classifier with full own state, and the decision-unit question
    for the user.
- **P3.**
  - What exists: X124 knocked out windows against prices, and X138 knocked out taker timing.
  - What is new: the knockout by ledger class and endgame, scored on the per-market correlation, which is what the
    exam scores.
- **P4.** It corrects X137 / `own_persistence.json` and agrees with assumptions check J. The point-in-time number is
  new.
- **Not proposed, and why.**
  - **Shared dV with fast makers on the live book.** The assumptions panel's P1 / P2 already cover it (its check H:
    dV correlation 0.56-0.58 with 0x2005d16a / 0x51dbdd2b). My on-chain check adds only that their block-time prints
    are no better than anyone's.
  - **X96 (salt PRNG).**
    - V8's xorshift128+ output is linear over GF(2), so the V8 case needs Gaussian elimination, not z3; step 1
      already covered strides 1-9.
    - JavaScriptCore and SpiderMonkey add the two state words, which is nonlinear and needs a solver.
    - A Rust client (ChaCha) would make the item futile.
    - The payoff is uncensored order counts, which touch neither price nor outcome.
  - **Reverted settlement transactions** as a source of unfilled orders. They emit no logs, so they need full-block
    scans of the operator's transactions: too heavy for the shared connection, with an unknown and probably tiny yield.
  - **Balance or merge gating of quotes** (critique 4: no effect).
