# Panel, iteration 12: assumption breaker (fresh eyes)

Written 2026-11-01, about 07:50-09:00 UTC. Nothing sealed was opened and nothing new was fetched.

**What I read**
- BRIEF.md.
- NOTES iteration 12 in full, plus the earlier findings that each proposal depends on (X63, X97, X135, X154, X158,
  X170, X171, finding 14 of iteration 9).
- state.json: all 171 X items, the non-X catalog, components and target_metrics.
- FINAL_RULE.md.
- panels/iter11_assumptions.md, and the iteration-12 information and mechanics panels, to check overlap.

**What I used** (development tables only)
- BUILD-live, 10-31 14:50-18:00: `own_bursts_dev`, `linked_adds_dev`, `level_events_dev`, `dev_markets` and
  `iter12/slot_vrel_rows`.
- On chain, 16-22 Oct, all blocks before H: `ledger_rows_iter10`, `orders` and `calldata_pub`.

**Scripts** (session scratchpad, each process under 300 MB): `vrel_diag.py`, `xmkt_tick.py`, `ivl.py`, `attn.py`,
`feedsplit.py`, `biasprint.py`, `trigstate.py`, `reactfloor.py`, `reactfloor2.py` and `chainclusters.py`.

## Where the gap is

Selection passes on VALIDATE. Price and outcome fail, and iteration 12 attributes both to two things: one private
value V per burst, and a +50-ms take.

The account of V rests on a two-clock model:
- **the loop path**: quiet, private 1c steps on the 504-ms tick;
- **the event path**: "triggered actions a median 17 ms after a book change". Withdrawals "start with triggered pulls
  and end with triggered adds".

The planned VALIDATE-live tests inherit this split:
- the X158 replication (triggered vs untriggered);
- X159 / X168 (what starts a withdrawal);
- the X163 V proxies (J and the touch at sign - 100 ms);
- the mechanics panel's P3 (the precursor each triggered action copies).

My main check says the event path is mostly not a reaction to the public book at all.

## Checks (so nobody redoes them)

### A. "Triggered" own adds are mostly signed before their trigger reaches the book

**Data.** 156 calldata-linked own adds on BUILD-live, each with its client signing time and its book (server) time.
- The trigger is the most recent non-own change on the same book within 40 ms before the add's book time.
- Own adds and pulls from `own_bursts_dev` are removed within 3 ms, and wallet-size levels (whole 50-100 shares) are
  dropped.

**Transit, sign to book:**

| Signer | p5 | p10 | p25 | p50 |
| --- | --- | --- | --- | --- |
| Wallet | 18 ms | 19 ms | 20 ms | 23.5 ms |
| Other linked makers | 9.8 ms | 17.6 ms | 21 ms | 30 ms |

**Triggered adds.** 89 of the 156 count as triggered. Their book lag behind the trigger is 6 / 11 / 23 ms
(p25 / p50 / p75). Their signing time minus the trigger's book time:

| p10 | p25 | p50 | p75 | p90 |
| --- | --- | --- | --- | --- |
| -151 ms | -32 ms | -14 ms | -1 ms | +7 ms |

So **75% were signed before the trigger reached the book** (81% without the size drop; 65% with a 30-ms own-removal
window).

**Clock caveat.** The wallet's 18-ms transit floor, against the others' 9.8 ms, allows its clock to run up to about
8 ms behind the server. Even then, about two thirds of these adds cannot be reactions to their trigger.

**What the triggers are**
- Kind: 51 cancels, 37 adds, 1 trade.
- Only 15% of them follow an own pull within 40 ms, so they are not followers of its own cancel.
- Sizes: 10 shares in 33 (0x893575c7, 0x3f348100, 0x42a1b2b4, ...), 20 shares in 12 (mostly 0x2e3c40fa), 5 shares
  in 7.
- 53% sit on the other side of the book (the complement token).

**Before signing.** Other makers' changes cluster around its signing on both sides:
- a non-own same-book change in [sign - 20, sign - 2] ms: 0.494 against 0.123 at ±1-3 s shifts;
- in [sign - 100, sign - 20] ms: 0.474 against 0.287.
- Trades explain little: any trade on the event in [sign - 40, sign - 2] ms, 0.077 against 0.003.
- Sibling-book changes in [sign - 40, sign - 2] ms: 0.147 against 0.058.

**Reading.** Most of the event path is a cluster of makers moving on a common hidden event, with the wallet inside the
pack. It is not a public trigger followed by a response.

This is consistent with X63's symmetric co-occurrence (non-own changes before its bursts 66.8%, after 69.1%, null
18.8%), which nobody reconciled with the "triggered" label.

**Caveat.** Linked adds are filled orders only (top-heavy, busy moments). The same test on all 2,550 triggered bursts
needs the burst's sign time, which unfilled orders lack. Use the per-maker lag order instead (P1, step 1).

### B. No attention budget in its value changes (E19, human desk)

**Data.** Filled maker bursts, 16-22 Oct; 8,604 event-minutes with public transactions.

**Model.** Poisson regression of quiet-class V changes per event-minute on:
- log(concurrently live events it quotes; 1-8, median 3);
- log(public transactions);
- event and hour fixed effects, with clustered SE.

**Result**
- Elasticity on concurrency: -0.06 (SE 0.11); all quiet bursts -0.06 (SE 0.11).
- A single trader gives -1.
- A desk would need about one trader per live event (up to 8).

V is set by a machine, not by people.

### C. No persistent private offset

**Anchor.** The last print plus its own offset from the print (its own levels revealed on chain before signing: the
last one, the mean of the last 3, the median of the last 5).

**Result.** Worse than the plain print on both splits:

| Split | Bias-corrected print | Plain print, same rows |
| --- | --- | --- |
| BUILD | 0.24-0.25 | 0.305 |
| VALIDATE | 0.22-0.24 | 0.305 |

The quiet class drops from 0.375-0.38 to 0.27-0.29. V's private part is transient, not a standing valuation bias.

### D. Same-tick synchrony of untriggered bursts (BUILD-live, ±15 ms)

| Pair | Same tick | Shifts of ±3 or ±5 ticks |
| --- | --- | --- |
| Complement token of the same market | 16.5% | 1.3% |
| Another market of the same event | 2.9% | 0.4% |

This matches the information panel's map-match coupling (3.8% vs 0.29%). Most quiet re-pricings are still
single-book actions.

### E. Where the untriggered adds come from and go (BUILD-live, 209 add bursts matched to the slot rows)

- **Before.** Its top was 1c below J in 25%, at J in 15%, 2-4c below in 27%; 11% were fresh.
- **Step.** +1c in 33%.
- **After.** V = J exactly in 41%, within one tick in 71%.
- **Triggered adds for comparison.** Exact 34%, within one tick 66%.
- **Spread dependence.** At a 1c others' spread its top is more than 1c below J in 34% of bursts. Above 5c it is more
  than 1c above J in 36%. V is a value inside the spread, not a join rule.
- **Mid anchors.** Mid-based anchors (floor or round of the mid minus 0-3c) peak at 0.58 within one tick, below J's
  0.67.

### F. Group P is nearly everywhere it trades

**Group P with a print in its markets (16-22 Oct, CS2):** 72 of its 77 events. In the 5 without one it still takes,
at a higher take rate. There is no "uncovered events" natural experiment here.

### G. A wallet-independent message clock exists on chain

**Clusters.** Two or more distinct other makers whose filled maker orders were signed within 20 ms of each other on
the same event (16-22 Oct, public transactions only: a lower bound).

| Relative to P4e's 3,091 takes | Observed | ±10-20-s shifts |
| --- | --- | --- |
| Cluster in (0, +300] ms after P4e's signing | 13.1% | 0.8% |
| Cluster in [-300, 0) ms before it | 0.9% | 0.7% |

The co-receivers' maker legs leave an examinable trace of the messages, after the message only.

## Critique: what the investigation takes for granted

1. **"Triggered" means "caused by a public change".**
   - Check A says that, for most ground-truth adds, the identified trigger is a co-mover that signed at the same moment.
   - The "event path" is then the hidden stream itself, reaching 5-, 10- and 20-share makers as well. It is far denser
     than the take-kind messages, and it covers about 85% of its bursts.
   - Consequences for VALIDATE-live:
     - withdrawals do not "start on a public change";
     - the X163 proxies at sign - 100 ms are stale by construction;
     - the mechanics panel's P3 already falls on its "if false" branch for the linked adds.
2. **X171's "not a score table" mixes two things.**
   - The overall residual is dominated by movement within the round, which no round-level hidden state can fit.
   - The one criterion that isolates the table, the freeze-time residual, went the table's way: 2.69c against the
     print's 2.90c, under the 3c bar.
   - The table also had a single round-win probability per map, with no CT / T asymmetry and no side switch.
3. **"V leads the book" is measured against a mid its followers can set.**
   - Finding 14 named the caveat. The joiner-free mid was never built (X135), and the print-based check had n = 30.
   - If the quiet lead is partly the followers', the quiet path may be a public book-state controller. The X158
     attribution conditions on a change in the previous tick, not on the state, so it cannot see one.
4. **The take selectivity ("no round-win kind in its input") rests on pull rates** (17% vs 10%). It has not been
   tested on whether its maker leg re-prices inside the co-mover clusters at those messages. Check A says it is inside
   such clusters most of the time.
5. **Exam arithmetic.** h1 and h2 have no books or game feed. Price and outcome cannot pass there with any rule found
   so far, and two of the four exam rounds go to those lots first. The on-chain cluster clock (G) is the only new
   historical input I found that h1 / h2 could use.

## Proposals (ranked by the chance they close the gap)

### P1. The event path is a common-cause cluster: build the co-mover message clock and re-run the event-path analyses and the price item on it (new; corrects the X158 / X159 labels; strong form of X54 / X121 / X154)

**Hypothesis.**
- Most off-loop own bursts respond to a hidden event that reaches several other makers within about ±20 ms: the
  "trigger" is a co-mover.
- The cluster of near-simultaneous non-own changes is the public witness of the message stream: on the live book for
  future blocks, and on chain (filled orders) for h1 / h2.

**Why it fits.** Check A, Check G, X63's symmetric co-occurrence, the X154 step 2 cross-book synchrony, and X121
(others cancel within 8 ms of its alone takes).

**Test.**
1. **Ordering on the sign clock.** For every calldata-linked own add and pull, and every linked non-own order within
   ±40 ms (BUILD-live, then each VALIDATE-live block), fit each signer's fixed lag to the cluster onset, as X97 did
   for takers.
   - A reaction chain shows a leader, with followers signing at least 20 ms after the leader's book time.
   - A common cause shows overlapping sign times in a fixed per-maker order, with the wallet inside.
2. **Cluster clock.**
   - Onset: two or more distinct non-own makers change a level on any book of the event within 30 ms, with no trade
     on the event in the prior 300 ms.
   - Validate against group-P take sign times (share of P4e messages with an onset in [-50, +100] ms against shifts),
     and against Thunderpick suspensions once matched.
3. **Re-label.** Re-run X158's on/off-tick classes, the X159 withdrawal starts and ends, and X170's kind against the
   cluster clock, instead of "a same-book change within 40 ms".
4. **Price, point-in-time.**
   - Population: its orders signed at least 100 ms after an onset (loop ticks and refills after the message).
   - Predictor: V_pred = its own top before the onset + f(signed cluster move: co-movers' bid cancels against adds
     above), fitted on the first half of BUILD-live.
   - Scoring: the X163 machine, per order and on the set unit.
   - Historical form for h1 / h2: the on-chain clusters of Check G.

**Data.**
- `own_bursts_dev`, `linked_adds_dev` (156 own and 717 other linked adds), `level_events_dev`, `calldata_dev`;
- VALIDATE-live blocks (same scripts with TOMMY_BLOCK_SUFFIX);
- `calldata_pub` / `calldata_all` for the on-chain clock.

**Signature if true.**
- The median |sign - onset| is under 20 ms, with a stable per-maker order and the wallet inside the pack.
- The clock catches at least 50% of group-P messages at 10x or more the shifted rate.
- Withdrawal starts sit at onsets.
- After onsets, its V moves in the sign of the cluster at least 75% of the time.

**If false.** A leader-follower chain with the wallet 20 ms or more behind a public leader. The triggered class is
then a public reaction, and the leader's new level is a point-in-time anchor for V.

### P2. V is an in-round win-probability state, not a round-level value: test it on the round in progress, with a side-aware table at freeze time (strong form of X171 / X160)

**Hypothesis.**
- V moves within each round with in-round state (kills, plants) from the hidden stream, and resets close to a
  side-aware score table at freeze time.
- X171's verdict comes from the within-round movement, not from the table.

**Why it fits.**
- X171's freeze-time residual: 2.69c against 2.90c.
- X160: +4.5c ahead of the print, in the previous winner's direction, right after a round ends.
- Consecutive same-sign changes: 70.6% against 64.5% shuffled.
- Iteration 1: its maker orders before same-team takes see the next jump go their way 60-62%, against 41-42%.
- Its takes buy the team that gained within the round.

**Test** (historical, 92 bo3 maps of 16-22 Oct, no new data).
1. **Round ends** from a wallet-independent clock: the X171 fit on the print, the Check G on-chain clock, or both
   agreeing within 10 s.
2. **Round-level drift**, for each round r:
   - Delta_w: change of its level (team-A space, every maker class, excluding the 2 s after its own takes) from the
     first burst after the previous end to the last burst before r's end;
   - Delta_p: the print's change over the same span;
   - outcome: bo3's winner of r.
3. **Score.** AUC of Delta_w and of Delta_p, and Delta_w residualised on Delta_p (map-cluster bootstrap, 2,000 draws).
4. **Table at freeze time.** Refit X171 on the first burst within 20 s after each inferred end only, with per-map
   p_CT and p_T swapping at the half and in overtime. Compare V's residual against the print's.

**Data.** `ledger_rows_iter10`, `orders`, the cached bo3 rounds (machinery in `round_markov_fit.py`), the tapes.

**Signature if true.**
- AUC(Delta_w) is at least 0.70 and at least AUC(Delta_p) + 0.08, with the residualised term significant at
  p < 0.0025.
- V's freeze-time residual is at most 2c, and at least 0.7c below the print's.
- Then V = side-aware table + in-round increments:
  - buy-phase orders become examinable on a round clock;
  - the in-round part needs kill-level data (X37 / X122 with consent; Dota realtime, X118).

**If false.** AUC(Delta_w) is close to AUC(Delta_p). V follows the market within rounds, and its private part is
confined to the events it acts on.

### P3. The "lead" of V may be its followers' doing; if so, the quiet path is a public book-state controller (strong form of finding 14's caveat, X135 and X158 step 2)

**Hypothesis.**
- Part of the 0.52 / 0.44 / 0.34 lead over the others' mid comes from quote followers pegging to its top.
- Its quiet loop steps act on book STATE (the gap of its top to J and to the others' second level) on the tick,
  whenever J changed.

**Why it fits.**
- Check E: it moves from 1c below J to J; V = J exactly in 41%.
- The joiner-free mid was never built (X135). X104 had 30 prints.
- loop_market_pull is not separable with adds only (0.736 against 0.728).

**Test.**
1. **Follower census and the lead without them.**
   - Measure the rate of non-own adds at its new top price within 0-2 s after its untriggered adds, against shifts.
   - Rebuild a joiner-free mid (drop those levels and P1's co-movers) and recompute the lead.
   - Also score the lead against the non-wallet trade VWAP in (t + 5, t + 60] s, and against P2's round winner.
2. **Per-tick controller.**
   - Units: every loop tick (its phase tracker) on every token where it holds levels.
   - State: own top - J, own top - others' second level, J size, J age, spread, own level count, own fills since the
     last tick.
   - Outcome: +1c, -1c, another change, or none.
   - Fit a multinomial model on the first half of BUILD-live; score it on the second half and on VALIDATE-live.
   - Look for an absorbing state.

**Data.** `own_bursts_dev`, `level_events_dev`, `linked_adds_dev`, the raw `tommy_cs2_near` books with snapshots,
VALIDATE-live.

**Signature if true.**
- The joiner-free and trade-based lead falls to the other makers' level (at most 0.15 at 10 s).
- Tick actions are predicted at macro AUC 0.85 or more, with an absorbing gap delta* where no step happens.
- Then quiet V = J + delta* (public), and the private part is confined to P1's event responses.

**If false.** The lead survives joiner removal and trades, and the tick actions are not predictable from the state.

### P4. Is the round-win kind missing from its input, or received and declined? (new; strong form of X99 / X83 on the maker side)

**Hypothesis.**
- Its client receives the round-win messages: its maker leg re-prices inside the co-mover clusters at those messages.
- It does not take because its value already moved or the gap is below its threshold (X170).
- The "kind filter at the input" reading would then be withdrawn, and the take becomes a value-threshold decision.

**Why it fits.**
- Check A: its re-pricings are co-receptions.
- X170: it takes when its revealed value reaches the stale ask.
- X99: presence rises with the edge P4e left (8.7% to 30.6%) before followers are removed.
- Iteration 5: own pulls run 2.8x control before the pack signs.

**Test.** At the pack's round-win messages without a wallet take (X58 census; BUILD-live, then VALIDATE-live):
1. Measure its maker membership in the cluster (an own add or pull within ±30 ms of the onset, on any book of the
   event) against shifts, compared with its membership at plant messages.
2. Check whether the direction of its V change matches the pack's bought team.
3. Historical form: its filled orders on calldata at P4e's round-win takes (on-chain sign times).

**Data.** `census_bursts`, `calldata_pub`, `own_bursts_dev`, VALIDATE-live.

**Signature if true.** Membership at 3x the shifted rate or more, with V moving toward the pack's team in at least 70%
of cases. Then its input includes round wins, and the fan-out kind filter is withdrawn.

**If false.** No membership excess at round-win messages, while present at plant messages. The subscription then lacks
the round-win kind, as now assumed.

## Overlap

- **Information panel, proposals 2-3** (one value per event; rounded slow filter). They are compatible with P1 and P3.
  P1's cluster clock is the natural clock for its slow-filter test.
- **Mechanics panel, P3** (the precursor each triggered action copies). It presupposes reaction. Check A puts the
  linked adds on its "if false" branch, so run P1 step 1 first.
- **Mechanics panel, P1** (the 0x52661b8e co-signed account). It is consistent with Check A's 5-share co-movers.
- **E19 (human desk).** Closed by Check B, except for one trader per live event.
