# Panel, iteration 13: assumption breaker (fresh eyes)

Written 2026-11-01, about 10:10-10:50 UTC. Nothing sealed was opened. The only new network reads were read-only chain
state (`eth_getCode` at `latest` on publicnode) for four deposit wallets and their owner keys. bo3.gg responses came
from the shared cache through `shared_client` (`max_age=None`, as the iteration-12/13 scripts do).

**What I read**
- BRIEF.md: the premise, the accuracy section and the catalog.
- NOTES iteration 13 in full, plus the earlier sections that the checks below depend on: X171, X181, X97, X105,
  X124, X138, X154, X155 and X177.
- state.json: all 220 catalog items (status, source, evidence head), the hypothesis ledger verdicts, the components
  and target_metrics.
- FINAL_RULE.md: the iteration-13 section, the rule table, the mechanism and "Not explained yet".
- The proposal titles of every earlier panel, and iteration-12 assumptions and iteration-11 assumptions / information
  in full where they overlap.
- There are no EXAM or wall-audit files.

**What I ran.** Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`:
`printcens.py`, `inround_variants.py`, `inround_state.py`, `inround_endreason.py`, `phase_hit.py` and
`limit_anchor.py`, with JSON outputs next to them. All use development data only: orders signed before H, tapes
clipped to H, and the cached bo3 rounds of 16-22 Oct. Each process stayed under 300 MB.

The in-round scripts copy `code/iter13/inround_drift.py` line for line: the same 86 maps, 894 rounds and boundaries
from the print's X171 fit. They reproduce its headline exactly: 0.8993 against 0.6753.

## Checks (so nobody redoes them)

### A. How much of the tape the "clean print" removes

The comparator throughout the price and in-round work is the last public print with every transaction that holds a
wallet order excluded. Over its CS2 map markets, 16-22 Oct:

| Measure | Value |
| --- | --- |
| Public taker transactions containing a wallet order | 27.8% (26.0% with the wallet as maker; 27.0% of USD) |
| Print moves of >= 3c (team-A space) in such transactions | 36.4% |
| P4e takes in such transactions | 24.5% (564 takes) |
| Wait from an excluded P4e take to the next clean print (p25 / p50 / p75 / p90) | 3 / 9 / 24 / 64 s |

So the clean print is censored most heavily at informed moments. That is legal, and required for features, but it
makes the comparator and the print-fitted round clock late.

### B. X181 survives the comparator and the own-take aftermath

AUC of the within-round change for the bo3 round winner:

| Variant | Rounds | Its level | Print |
| --- | --- | --- | --- |
| X181 as run (clean print) | 894 | 0.899 | 0.675 |
| Full tape (all public prints, wallet transactions included) | 971 | 0.911 | 0.680 |
| Clean, bursts within 5 s after any own take in the event dropped | 859 | 0.884 | 0.667 |
| Same, plus the last 45 s before the inferred end dropped | 745 | 0.784 | 0.620 |
| Rounds with no own take at all (clean / full) | 560 / 618 | 0.879 / 0.896 | 0.679 / 0.707 |

The headline is not an artefact of the exclusion rule or of its K - L re-pairs after takes.

### C. Where in the round its lead sits: the market prices the opening duel as well as it does

I joined bo3's per-round team stats (`first_kills`, `clutches`, `kills`, `bomb_plants`, `end_reason`, `team_side`)
to the same rounds. AUC for the round winner, its level against the print:

| Round class | n | Whole round | Last 45 s cut | First 30 s | First 60 s |
| --- | --- | --- | --- | --- | --- |
| Aligned (the winner took the opening kill, no clutch) | 595 | 0.914 / 0.728 | 0.811 / 0.664 | 0.630 / 0.645 | 0.689 / 0.668 |
| Contrary (the loser took the opening kill, or the winner clutched) | 297 | 0.867 / 0.569 | 0.740 / 0.521 | 0.513 / 0.452 | 0.604 / 0.481 |
| Clutch won | 102 | 0.874 / 0.569 | 0.717 / 0.519 | **0.400** / 0.454 | 0.504 / 0.481 |

The opening-kill team as the target: first 30 s 0.580 for its level against 0.606 for the print; first 60 s 0.595
against 0.617.

**Reading**
- In the opening phase its value is no better informed than the print, even about the opening duel.
- In clutch rounds it first leans toward the eventual loser (0.40), then ends with the winner.
- Its lead builds in the second half of the round, where the print carries nothing: 0.52 in contrary rounds once the
  last 45 s are cut.

### D. Kills, not the clock

Mean within-round change of its level toward the CT team, against the print:

| End reason | n | Its level | Print | AUC (level / print) | Last 45 s cut: level / print |
| --- | --- | --- | --- | --- | --- |
| TargetSaved (time ran out, no plant) | 44 | +5.8c | -0.1c | 0.896 / 0.520 | +3.7c / -0.2c (AUC 0.756 / 0.488) |
| CTWin (elimination) | 319 | +5.9c | +1.3c | 0.893 / 0.685 | +3.6c / +0.7c |
| BombDefused | 115 | +6.4c | +0.9c | 0.900 / 0.649 | +3.6c / +1.1c |
| TargetBombed | 191 | -6.3c | -1.1c | 0.912 / 0.669 | -3.5c / -0.8c |
| TerroristsWin (elimination) | 225 | -6.6c | -1.8c | 0.899 / 0.713 | -4.0c / -0.8c |
| T wins by elimination, no plant | 45 | -8.7c (87% of rounds toward T) | -2.2c | | -5.9c |

The discriminating row is the last one. The round clock favours CT and the kills favour T, and its level goes
toward T. So its in-round value follows the kill state, not a round-timer or bomb-timer model. The no-plant timer is
a new null; the post-plant timer was already null in iteration-11 assumptions check F.

### E. Phase of the public anchor's failure

The last clean print plus the per-map, per-token median offset, within one tick of its burst tops (7,006 bursts,
86 maps):

| Time to the print-inferred end | 0-10 s | 10-30 s | 30-60 s | 60-120 s | > 120 s |
| --- | --- | --- | --- | --- | --- |
| Within one tick | 0.068 | 0.101 | 0.214 | 0.271 | 0.320 |

- First 45 s of the round, not in its last 45 s, no own take within 5 s: 0.329.
- The failure concentrates at round ends. Even in quiet early phases the print is far from 0.8, because of the ladder
  slots and its offset.

### F. Informed takers' signed limits are not its value (strong form of iteration-11 assumptions check E)

- **Anchor.** FAK limits of group P and group G: P4e, 0x2005d16a, 0xf1ee4842, 0x8a80528d, 0xddb6e624, 0x7c8cc255,
  0x67706ec3 and 0xc7097421. I used only transactions without a wallet order, each public from its block with a
  1-s margin.
- **Population.** In the 10.5% of its bursts signed within 30 s after such a limit, and no older than the latest
  clean print.
- **Result (VALIDATE, BUILD offsets).** Limit anchor 0.094 within one tick, against 0.258 for the print on the same
  bursts. Overall the print scores 0.292.
- The pack's limits carry each subscriber's own premium, not V.

### G. The EIP-7702 delegate is a usable fingerprint of the operator

**Operator keys.** The three operator owner keys read so far all delegate to 0x63c0c19a:
- 0x8af810f0, the wallet's owner;
- 0x80a19b87, owner of 0x7d67f01d;
- 0xe6f64514, owner of 0x52661b8e.

0x63c0c19a is probably MetaMask's EIP-7702 stateless delegator; I did not verify this.

**Other bots' keys.** The owners of four other bots' deposit wallets (same factory, 0xd729a0cb) are plain EOAs with
no code:

| Bot | Owner |
| --- | --- |
| P4e 0x4ebc2722 | 0xbf6461fa |
| 0x758dac51 | 0xad3dedb9 |
| 0xed446954 | 0x1aaef256 |
| 0x42a1b2b4 | 0xfd04ce73 |

So the delegate is not Polymarket's default. It is a cheap filter for P5, though not universal: 0x116342d6, owner of
0x67119033, was not checked.

## Critique: what the investigation takes for granted

1. **"V is an in-round win-probability state" is right in kind but wrong in shape, and the plan follows the wrong
   shape.**
   - Checks C-E show the following:
     - The market prices the opening phase of a round as well as its value does.
     - Its private part is the late-round kill state: eliminations, clutches, post-plant and retake fights, and a
       side that runs out of players before the clock. Nobody else trades on these until the round result.
     - There is no clock component.
   - The iteration-13 next step 2 builds a winner-free round clock and re-tests the freeze-time level and the in-round
     drift on it. That targets the phase where V has no private information. A round clock by itself cannot make V
     point in time, because V's private moves are kill-driven.
   - What is missing is a model of V given the kill state (P1, P2), and then a real-time kill state.
2. **The price item is treated as a V problem; it is a timing problem.**
   - Its orders are signed at V changes. The own top just before the burst, through the frozen machine, already falls
     to 0.326 (X177 R1).
   - So an input that lags V by even a fraction of the loop misses the orders that matter:
     - the stream, Twitch chat or Kick timing;
     - Valve's 4-s Dota snapshots;
     - an HLTV page in a browser.
   - These sources can name the feed's class. Whether they can carry the price item is unmeasured (P3), and the consent
     requests to the user should say which of the two each source can do.
3. **The per-order cap is binding before any data question.**
   - With V known, the ladder machine gives 0.73 per order (0.875 on the burst-set unit).
   - The price item cannot pass per order even with a perfect feed, so the unit ruling is worth more than any further
     V work. Ask the examiner both of these:
     - (a) the burst-set unit;
     - (b) per-order scoring with the wallet's own resting slots and its signing order within the burst as reported
       own state. Own resting levels are visible on the recorded books; the brief bans only fill counts and the time
       since the last fill.
4. **"The outcome item is the price item" (X124) was established for continuous quoting only.**
   - Check E shows the public anchor's failure piles up in the last minute of rounds. Adverse selection against stale
     makers does too: group P takes at round ends.
   - A public ladder that is gated by round phase on a point-in-time on-chain clock was never run (P4).
5. **The forward lots are not the development mix.**
   - Dota 2 is 54-57% of fills in the 10-31 development block (X112), against about 4% of trades in 16-22 Oct (7% of
     VALIDATE fills).
   - The decode work is almost all CS2. Dota is the only title where a real-time public state exists (Valve's
     spectator-clock stats), so the X118 live test decides more of the exam than any CS2 test does. Its
     pre-registration should include P3's lag curve.
6. **One operator, but only one of its processes was searched for.**
   - The census looks for orders 0-5 ms after a wallet order on the same token. It can only find shadow copies of
     the same process.
   - The two shadow accounts look like activity farming:
     - minimum-size 5-share orders;
     - 0x52661b8e trades LoL, Dota, CS2, BTC and football, with BUY 17.8k / SELL 14.9k;
     - 0x67119033 trades tennis and Valorant as well.
   - That farming may also explain why the main wallet keeps quoting through phases where it is adversely selected
     (the -$8.4k unpaired residual).
   - Other processes of the operator could exist in places the census never looked, with different lags or no
     co-signing (P5):
     - round, total and handicap books;
     - LoL;
     - GRID events;
     - a taker-only account on the feed.

## Proposals (ranked by the chance they close the gap)

### P1. Decode V as a kill-state model: a latent kill-order lattice per round, fitted to its levels, with bo3's per-round kill totals as the endpoints (new; strong form of X171 / X181 / X160)

**Hypothesis.** Within round r its value is

V = W(s) x M(a + 1, b) + (1 - W(s)) x M(a, b + 1),

where:
- M is the map table (MR12 / MR3) at the score (a, b);
- W(s) is a round-win model of the in-round state s = (alive_A, alive_B, planted, side);
- s steps along the round's actual kill sequence;
- the private input is only the timing of that sequence.

**Why it fits**
- Check D: in T wins by elimination without a plant it moves -8.7c toward T, and the print moves -2.2c.
- Check C: clutch rounds first lean to the eventual loser.
- X173: the same cents move on the map and match books.
- X171: the round-only table fits no better than the print, because all of its fit is inside rounds.

**Test** (historical, development, no new data)
1. **Latent states.** For each round, use the boundaries of the full-tape print fit; check B shows the full tape is
   sharper at round ends. The state is (dA, dB), the deaths of each team, running monotone from (0, 0) to bo3's
   totals (`death` per team in `game_round_team_clans`). Add one plant step when bo3 has `bomb_plants > 0`. The
   lattice has at most 6 x 6 x 2 states.
2. **Fit.** Assign the round's bursts to states by Viterbi (monotone in time; per-token offsets mu as in X171).
   Use W(s) = logistic(alpha_side + beta x (alive_A - alive_B) + gamma x planted x sign_side), with alpha, beta and
   gamma fitted by EM on BUILD maps and frozen for VALIDATE.
3. **Controls**, each on the same VALIDATE maps:
   - (i) X171's round-only model;
   - (ii) the same lattice fitted to the print;
   - (iii) the kill totals permuted among rounds with the same winner and side;
   - (iv) a free monotone step function with the same number of steps (the flexibility control).
4. **Score.** Residual SD per map, and within-one-tick of its burst tops through the frozen X163 machine with V from
   the fit (an oracle on the kill timing, so diagnostic only).

**Data.**
- `orders.parquet`, the tapes, and the cached bo3 `games/<id>/rounds` (kills, death, first_kills, clutches,
  bomb_plants, bomb_defuses, team_side);
- `round_markov_fit.py` (viterbi, fit, markov_table).

**Signature if true**
- Its lattice residual is at most 1.5c, and at least 0.7c below both control (i) and control (iii).
- The print gains less than 0.3c from the lattice.
- beta > 0, and the fitted W is plausible (5v4 about 0.6-0.7 for the man-advantage side).

Then:
- price = W-model + X163 machine, and the only private input left is the kill timeline at the feed's speed;
- the wall account becomes exact;
- the demo consent request (X37 / X122) gets a concrete pay-off: with demo kill ticks the oracle timing becomes
  observed.

**If false.** The lattice gains no more than control (iv). Its late-round moves then follow another variable:
- an odds stream (E4 on CS2, Thunderpick X144);
- economy;
- a per-message delta (P2).

### P2. V as a per-book delta integrator with re-anchoring (strong form of X173; a different model class from P1)

**Hypothesis.**
- Each in-round message adds the same cent delta to every book of the event: V_book += delta(message).
- The level is re-anchored at fixed points, such as the first burst after a round or map end, its own takes, or a
  quiet tick, to a value that may be public (the print or touch at re-anchor) or its own table.
- The equal cents on map and match books (|ratio| 1.00 / 0.92 / 0.80 over the s terciles, not s ~ 0.45) is the
  signature of an integrator, not of a coherent series model.

**Test** (historical, the 33 CS2 Bo3 events of X173; then VALIDATE-live with both books recorded)
1. **Within-round drift ratio.** For each print-inferred round (full tape), take the drift of its match-book level
   over the drift of its map-book level. An integrator gives about 1; a coherent model gives about s.
2. **Across-round level ratio.** Take the change between the first bursts of consecutive rounds on both books.
   Re-anchoring gives about s.
3. **Re-anchor events.** Find where the match book jumps back toward the s-coherent level, at bursts with no message
   cluster on any book of the event. Classify each jump: round start, own take, map end, loop tick.
4. **Public re-anchor.** If the re-anchor value is public, score V = anchor at the last re-anchor plus the cumulative
   map-book deltas since then (oracle deltas) through the machine, against the same rule with the print as the
   anchor.

**Signature if true**
- Within-round ratio 0.8-1.2 and across-round ratio within 0.1 of s.
- Re-anchoring jumps at an identifiable event class in at least 70% of cases.
- The re-anchor level within one tick of a public value in at least 60% of cases.

Then V = public anchor + private deltas. The deltas are per message kind (P1 gives their size), and the price gap
reduces to the message stream.

**If false.** The ratio is about 1 at every horizon: one private level is written to both books with no public
anchor, and P1's model sets the level.

### P3. Measure the lag tolerance of the price item before asking for any delayed public source (new; decides the route and the wall number)

**Hypothesis.** The price item tolerates almost no input lag: the orders that are scored are signed at V changes.
- If so, the stream, chat and Kick clock (X38 / X87 / X162), Valve's 4-s Dota snapshots (X118) and HLTV pages (X64)
  can identify the feed's class but cannot carry the price item.
- Only the push feed, or a source with comparable latency, can.

**Test** (BUILD-live uncensored own levels, then every VALIDATE-live block)
1. Run the frozen X163 machine with V = its own top on the token at t - L, with L in {0+, 0.1, 0.25, 0.5, 1, 2, 4, 8}
   s.
2. Score per order and on the set unit, separately for:
   - bursts at a V change and bursts at an unchanged V (refills);
   - CS2 and Dota.
3. Report the share of orders, and of filled orders, in each class.
4. On VALIDATE-live Dota, repeat with V from Valve's realtime state at its 4-s cadence, once X118 has overlap.

**Data.** `own_bursts_dev`, `level_events_dev`, `slot_vrel_rows` and the X163 code; `tommy_dota_rt` when available.

**Signature if true.** The set unit is at most 0.40 at L = 0.25 s and at most 0.30 at L = 4 s, and filled orders sit
mostly in the V-change class. The price item is then a wall item for every delayed public source, with these numbers,
and the consent requests should be re-scoped to source identification.

**If false.** The set unit is at least 0.6 at L = 4 s. A delayed public in-round state (Valve for Dota, the stream for
CS2) can carry most of the price item, and X118 and the stream consent become the exam path.

### P4. A round-phase-gated public ladder for the outcome item (new unit: the round phase; strong form of X124 / X138 / X155)

**Hypothesis.**
- The stale-maker cost is concentrated in the last minute of rounds:
  - check E: the public anchor scores 0.07-0.10 within one tick in the last 30 s, against 0.32 earlier;
  - check A: 36% of the >= 3c moves sit in the informed transactions there.
- A public ladder that quotes only between a point-in-time round start and a fixed horizon earns a positive pair
  margin. Its per-market PnL then tracks the wallet's through the shared scale, which is 0.82 / 0.75 locked margin
  versus PnL.

**Test** (X57 validated engine; strict fills, latency >= 2 s, match_slack 2)
1. **Point-in-time round clock.** Use informed take clusters: at least 2 group-P / group-G members' BUY takes on one
   event signed within 300 ms, usable from their block + 2 s.
2. **Quoting rule.**
   - Quote the five-slot whole-cent BUY ladder at the last clean print minus the BUILD offset, with the band and
     PAIR_CAP 0.99.
   - Quote only in [cluster + d, cluster + d + W]. Fit d in {5, 10, 20} s and W in {20, 40, 60} s on BUILD; pull
     otherwise.
   - Merge on the 300-s loop and hold the residual.
3. **Score on VALIDATE.** Return and per-market Pearson / Spearman against the wallet, against knockout D
   (continuous, 0.25 / 0.09) and the prints baseline (0.33 / 0.28).

**Signature if true.**
- Return >= 0, Pearson and Spearman >= 0.5 on VALIDATE and on each half, and the gain over D significant at
  p < 0.0025 by game-block bootstrap.
- The outcome item then passes with a public rule. This is the first examinable item after selection, and h1 / h2 can
  judge it.

**If false.** Early-phase quoting loses as well. The stale-maker cost then lies in every phase, and the outcome item
stays gated by V. That is a measured wall clause.

### P5. Find the operator's other processes by key fingerprint, not by co-signing (strong form of X176 / C1 / X74 / X188)

**Hypothesis.** The operator runs processes beyond the shadow copies. Candidates:
- accounts on other machines (fixed lag rather than 0-5 ms);
- accounts in books the census never covered: round, total and handicap books, LoL, Valorant, GRID events;
- a taker-only account on the push feed.

Any of these would give the following:
- a second view of V where the state is public: LoL through Riot live stats (X184), GRID events through the socket's
  round scores (X188);
- possibly the "kind filter" as account routing rather than a value threshold.

**Test**
1. **Owner census.** For every sigType-3 address with >= 50 orders in the operator's categories, 06-16..H (the
   decoded calldata of all of its markets, plus the esports markets of 0x7d67f01d, 0x52661b8e and 0x67119033), read
   the owner from the proxy tail. Then read the owner's code: is it a 7702 designator to 0x63c0c19a?
2. **Funding.** USDC.e / USDC transfer links (October logs are readable) to the known operator EOAs: 0x8af810f0,
   0x116342d6, 0x80a19b87, 0xe6f64514, 0xf70da978 (the wallet owner's funder) and 0x4cd00e38.
3. **Profile names.** data-api name and pseudonym fields.
4. **Confirm each candidate on behaviour:**
   - co-signing within 0-5 ms (or at a fixed lag) with any operator account on any token of the same event;
   - the 300.22 + 7.28 x merges s merge law;
   - whole-cent BUY-only and the band.
5. Also check P4e's owner 0xbf6461fa against the funding set. It is a plain EOA, so only funding can link it.

**Data.**
- `calldata_all`, `calldata_pub`, `calldata_grid`, `sib7d67` and `sib_grid`;
- publicnode `eth_getCode` (2 calls per address);
- Polygon logs for October.

**Signature if true.** At least one new operator account. A LoL or GRID-event account with enough rounds runs X184 /
X188 as a public-state experiment on the same V. A taker-only account on the feed changes X170's take reading into
routing.

**If false.** No other fingerprinted account. The four accounts are the whole operator, and X176's account stands.

## Overlap

- **P1 and P2 are rival model classes for the same levels.** Run P2's step 1 first: it is cheap and decides whether
  P1's W x M mapping should be fitted per book or once per event with deltas.
- **P3 overlaps X118 / X156 (Dota first) and the iteration-13 consent asks.** It is the measurement that sizes them.
- **P4 reuses X57 / X124 machinery.** It differs from earlier replays only in the phase gate and the point-in-time
  cluster clock (X180 step 2's clock, built from informed takers rather than co-moving makers).
- **P5 extends X176 from timing to fingerprints.** X184 (LoL) and X188 (GRID) depend on it for data.
