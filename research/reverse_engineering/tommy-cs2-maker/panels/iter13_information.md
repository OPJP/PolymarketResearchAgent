# Panel, iteration 13: information source and data (fresh eyes)

Lens: what the wallet sees earlier or better than the market, what the investigation has not obtained, and which data
would most sharply separate the leading explanations. After iteration 13 the ledger reads: E1b "own in-round
win-probability model on the private push feed's raw events (kills, plants)" strengthened (finding 18: within-round AUC
0.90 vs the print's 0.68); E4 rejected for three Dota bookmakers; E22 one operator, four accounts.

## What I read and what I ran

I read BRIEF.md (premise, hidden dimensions, catalog, data); NOTES.md (iteration 13 in full, the iteration-1/4/8 bo3
and Z8 sections, the rest by heading); state.json (catalog A1-X188 with evidence, components, target metrics, live
lab, data sources); FINAL_RULE.md by section; the iteration-12 information panel. There are no EXAM or wall-audit
files. `tools/sealed.py tommy-cs2-maker` at 10:34 UTC: no released lots, future examined up to 10-31 00:00; the
current block 11-01 06-12 is development.

Checks (scripts and outputs in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter13info/`;
each process under 300 MB and a few minutes; nothing written to the workspace except this file):

- `path_sign.py` -> `path_sign.json`, `path_sign_rows.parquet`. The X181 machinery unchanged (same 86 maps of
  16-22 Oct, the wallet's filled maker burst tops, the last public print without wallet transactions, the print's X171
  segmentation), plus the bo3 per-round attributes the notebook has never used for V: the opening-kill team (the
  unique team with `first_kills` > 0), the T-side plant (`bomb_plants`), `end_reason`, and the next round's winner and
  opener. Development data only, read through the shared client from its cache (offline mode).
- `future_print.py`, `future_print_ev.py` -> `future_print.json`. Within one tick of its burst tops against the last
  public print stamped at or before t + L (L = 0..600 s), with the per-token offset fitted on BUILD and scored on
  VALIDATE, and per event. A diagnostic of the size of the information lead, NOT a rule (it uses later prints).
- `bo3_round_fields.py`, `bo3_rmd.py`: the bo3 round schema on 12 development games (10-19/20).
- Web, as a plain client with default headers, development dates or configuration only (nothing bypassed):
  - Sportradar widget JSON (`lmt.fn.sportradar.com/.../gismo/...`): `Unauthorized feed` (403 in a 200 body) for the
    public aliases; `stats.fn.sportradar.com/sportradar/.../config_sports` answers, but lists no CS2, Dota 2 or LoL
    sport (only "ESport Call of Duty" and "ESport King of Glory"). Dead end for these titles.
  - SofaScore API (`api.` and `www.sofascore.com/api/v1/sport/esports/...`): HTTP 403.
  - Kick: the channel API answers key-free; `/api/v2/channels/<id>/messages?start_time=<ISO>` answers 200 but with 0
    messages for development times of a traded DraculaN match (2 tries) and for a CCT channel. No key-free historical
    chat replay as tested.
  - Leaguepedia (lol.fandom.com, MediaWiki Cargo, key-free): `cargofields` for `MatchScheduleGame` lists `RiotGameId`,
    `RiotPlatformGameId`, `GridSeriesId` and `VodGameStart`; the `cargoquery` itself answered `ratelimited` four times
    in about 90 s (it needs slow pacing, see proposal 3).
  - The earlier account 0x7d67f01d's cached activity (offline): 38 LoL events, 10,051 trades, 09-22..10-22, all before H.

## Critique: what the investigation is missing or getting wrong

### 1. The "in-round state" reading of V is not supported by the in-round events themselves

Finding 18 measures V's change inside print-inferred rounds against the round winner. Those segments are coarse: in my
re-run their duration is median 116 s, p75 236 s, so many span more than one real round. A value that simply learns the
round result some seconds before the print scores high on that test without pricing anything that happens inside the
round. The guards do not remove this. The 45-s guard and the "before the print's first 2c move" window both cut on the
print's own clock, which is the late clock.

The bo3 round rows carry what separates the two readings: who got the opening kill and whether T planted. Both are
in-round events, and both are partly decoupled from the winner: the opener wins only 72%, and a plant is followed by a
defuse in 13% of rounds. On the same 86 maps (873 segments with all attributes), I regressed the segment change in cents
on the winner, the opener, a T-side plant, the next round's winner and the next round's opener. All coded +1/-1 in
team-A space; SEs from a map-cluster bootstrap.

| Change inside the segment | winner | opener | plant toward T | next winner | next opener |
| --- | --- | --- | --- | --- | --- |
| Its level V, all segments | **5.88** (0.34) | **0.17** (0.29) | 0.10 (0.34) | **1.02** (0.29) | 0.02 (0.28) |
| Last print, all segments | 0.68 (0.20) | **0.71** (0.15) | **0.43** (0.18) | 0.26 (0.20) | -0.01 (0.21) |
| V, last burst >= 45 s before the inferred end | 3.38 (0.36) | 0.12 (0.30) | 0.09 (0.34) | 0.56 (0.30) | 0.32 (0.25) |
| Print, same | 0.35 (0.25) | **0.63** (0.19) | 0.07 (0.24) | -0.01 (0.22) | 0.15 (0.22) |
| V, segments <= 150 s (n 516) | 4.75 (0.42) | 0.08 (0.37) | -0.08 (0.41) | **1.08** (0.33) | -0.03 (0.32) |
| Print, segments <= 150 s | 0.59 (0.26) | **0.62** (0.19) | 0.36 (0.25) | 0.18 (0.21) | 0.16 (0.24) |

What the table shows:

- **The print prices the in-round events and V does not.** Beyond the winner, the print moves toward the opening-kill
  team (0.6-0.7c) and toward T after a plant (0.4c). V shows neither, and its CIs exclude the print's opener effect.
- **First moves.** First >= 1c move inside a segment, as a linear probability model:
  - V: winner 0.228 (0.035), opener 0.076 (0.035);
  - print: winner 0.172 (0.043), opener 0.105 (0.043).
  - When the opener lost the round, V's first move goes toward the opener 42.4% of the time (n 231); the print's 46.6%
    (n 178).
- **Retakes.** In BombDefused rounds (T planted, CT won), V's first move goes toward T in 36.3% (n 113). A plant-tracker
  would go toward T first. Its "excursion toward the eventual loser" is 0.539 in retakes against 0.525 in all other
  rounds.
- **The next round's winner loads on V** (1.0c, about 3 SE, also in short segments) and not on the print. Either its
  lead sometimes exceeds the print's segment, or V carries an economy-informed next-round term. Adding bo3's
  equipment of round k+1 separates the two.

Reading: the private part of V is mostly the round result, seen before the market, not a kill / plant state. Two things
follow:

- Finding 18's AUC 0.90 vs 0.68 and finding 19's "in-round event information (kills, plants)" are better described as
  an earlier view of round results. Finding 19's own early windows say the same: inside the first 30 s, 0.595 vs 0.586.
- This changes what data is missing. The investigation has been asking for a KILL clock: demos, stream OCR, HLTV. Only
  the user can unlock those. The test says the decisive missing dimension is a feed-time round-END clock, and public
  traces can approximate one (proposals 1 and 2).
- Caveats: burst tops are censored (fills, not quotes), and the segmentation is still the print's. Proposal 1 removes
  both.

### 2. The information lead has a size, and it is 10-45 s, organiser by organiser

The notebook's lead evidence is correlational (Spearman of the offset against later mid moves). The within-one-tick
question has a direct form: which later market price does V equal?

On the CS2 VALIDATE burst tops (9,946), within one tick of print(t + L) + offset:

| L (s) | 0 | 5 | 10 | 20 | 30 | 45 | 60 | 90 | 120 | 300 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| within one tick | 0.336 | 0.410 | 0.450 | **0.461** | 0.449 | 0.419 | 0.379 | 0.317 | 0.257 | 0.139 |
| MAE (c) | 4.21 | 3.34 | 3.01 | 3.02 | 3.16 | 3.50 | 3.97 | 4.87 | 5.88 | 10.46 |

The BUILD numbers are the same within 0.03.

- **Per event** (68 events with >= 80 bursts), the best L is:
  - 10-45 s in 64 of the 68 events;
  - median gain in within-one-tick +0.15;
  - structured by organiser: NODWIN 30-45 s (5 of 5), Circuit X and Stake Ranked about 30 s, DraculaN 10-15 s (19
    events), PGL and 1win about 15-20 s.
- **This is the signature of a broadcast chain.** The market (stream watchers plus slower bots) learns each round
  result an organiser-specific 10-45 s after the wallet. That fits Z8's relay reader against the HLS stream. It does
  not fit a server-side feed against a stream at tv_delay (90-180 s).
- **It also sets the price item's realistic bar.** A perfect "market 20 s later" anchor reaches only 0.46 against the
  frozen 0.322. The rest of the oracle's 0.875 is the ladder slots and the cent-level offset. A score-clock V should be
  judged against 0.46, not 0.875.

### 3. The remaining budget has almost no development live time; the plan rests on it

At 10:34 UTC about 288 budget minutes remain, so the budget ends around 15:20 UTC. The blocks are:

- 11-01 12-18: sealed;
- 18-24: development, but after the budget ends;
- 11-02 00-06: development, after the budget ends.

So the only development live time left is 10:34-12:00 today (cs2-bca-pha). Most open items wait for VALIDATE-live:

- X144 Thunderpick, X159 / X168 suspensions;
- X163 / X158 / X173-X177 live forms;
- X164 round-book clock, X118 / X167 Valve Dota state;
- X38 / X87 chat.

They will not run within budget. The consent items (X4, X22, X37, X53, X55, X64, X122, X147) have been asked for since
iteration 3 without an answer. The next iterations should go to historical, no-consent tests, which is how the
proposals below are ranked.

### 4. The 11-01 brief's hidden-dimension ledger is absent, and this is where the round clock belongs

state.json has no `dimensions` or `indicators`, no E1-E7 catalog items, and NOTES has no "Missing dimensions" section.
The inventory is where the finding of critique 1 should be recorded, as two entries:

- "feed-time round-end clock (non-GRID CS2)": status `proxy`; best indicator: group-P take clusters, co-receiver
  signing clusters and handicap / total books; verdict `drives` (price);
- "kill-level in-round state": `untested` at tick level, with critique 1 against it as a price input.

E7 (`residual_clustering`) has never been run. It is the one dimension tool aimed at the primary metric, which has sat
below its activity baseline since iteration 1 (proposal 4).

### 5. Smaller points

- **bo3 per-round rows are richer than used.** `first_kills`, `kills` / `death`, `alive_time` (summed player alive
  time, ns), `bomb_plants` / `bomb_defuses`, `clutches` with `clutch_attempts_vs`, `end_reason`, `equipment_value`,
  `loss_bonus_streak`. `round_map_data` is null on all 263 rounds probed, so there are still no kill times.
  `alive_time` with deaths gives each team's mean death time inside the round. That is a clock-free proxy for when the
  in-round swing happened, and it can sharpen the critique-1 test.
- **LoL.** The earlier account quoted LoL Worlds 2026 (10-03..10-17: e.g. lol-bro2-jdg, lol-navi-jdg, lol-fox1-kt) and
  September regional events with the maker design. Riot's official LoL data is distributed to betting through an
  official partner, and Leaguepedia stores `GridSeriesId` per game. So the "never GRID" boundary may be a property of
  the CS2 feed product, not of the operator. Worth a one-line check on Gamma's `gridSeriesId` of those LoL events.

## Proposals (ranked by the chance that they close the gap)

### 1. Round-END clock on the feed's time, then V as a side / economy-aware score table (strong form of X181, X171, X160)

- **Hypothesis.** V's private component is the round score as the feed reports round ends, 10-45 s before the market,
  mapped through a side-, economy- and series-aware table. Inside a round it does not re-price kills or plants (at most
  it withdraws). V = table(score on the feed clock) + a per-token offset, then the five-slot ladder.
- **Why it fits.**
  - Critique 1: V loads on winners, the print on in-round events; retakes; first moves.
  - Critique 2: V equals the market 10-45 s later, by organiser.
  - Finding 19's flat early windows.
  - X160: its level sits 4.5c beyond the print toward the previous round's winner at the first burst after a
    print-inferred end.
  - Finding 24: at print-inferred round starts V "already carries the next round".
  - The 504-ms quiet loop: a level that is re-sampled, not re-modelled.
  - X171's failure is expected: a constant-p table on V's censored burst tops, with no side or economy terms.
- **Test (historical, no consent, VALIDATE for the verdict).**
  1. **Feed-time round ends, without the winners.** Candidate messages are:
     - clusters of group-P take signings (calldata_pub; P4e "follows round wins", X50);
     - clusters of >= 2 distinct non-wallet makers signing on the event's map and match tokens within 20 ms (all
       filled orders carry signing ms);
     - simultaneous prints in the same map's handicap / total books (the 665 cached round-market tapes).
     Align bo3's round count and round durations to these candidates with the pause-aware DP of X160 steps 1-3.
     Validate the clock on BUILD against the bo3 winner sequence (a check only, never an input).
  2. **Undo the censoring.** Use the union top of the wallet and the 5-share siblings' slots (finding 10: inside
     [V - 4c, V] in 98% of bursts).
  3. **Fit on the clock, leave one map out.** Fit an MR12 / MR3 round-state table with side (bo3), equipment and loss
     bonus, and the series map to the match book, to V and, as the control, to the print. Report the residual SD and
     the within-1c share.
  4. **Inside clock-defined rounds,** regress V's changes on the opener, the plant, `alive_time` / deaths, and the
     winner.
  5. **The clock-end step.** Measure the share of V's >= 2c changes within 3 s after a clock round end, and the
     per-event lead of V's step over the print's and over retail-only prints (<= 20 orders per address).
- **Data needed.** Everything is cached:
  - bo3 rounds of the 86 maps;
  - `orders.parquet`, `calldata_all` / `calldata_pub`, tapes, the round-market tapes;
  - `sib7d67*` / `sib_grid` calldata for the siblings' slots.
- **Signature if true.** On the feed clock:
  - V's residual to the table is <= 1.5c, and >= 1c below the print's;
  - the in-round opener / plant coefficients stay < 0.3c (the print's 0.6c / 0.4c remain);
  - >= 70% of V's >= 2c changes sit within 3 s after a clock round end;
  - the lead is a per-organiser constant.

  If instead V moves >= 0.7c at openers on the true clock and toward T at plants in retake rounds, the kill-state
  reading stands, and the missing data is the kill clock (proposal 5).

### 2. A point-in-time round-end signal from public prints as the price rule's score clock (historical strong form of X164, plus X180 step 2)

- **Hypothesis.** The round results it prices 10-45 s early reach the public tape within about 1-3 s, through two
  channels:
  - prints of the feed's other subscribers (group P);
  - the same map's handicap and total books, which reprice deterministically at round ends.

  A score table advanced on those prints, point in time, reproduces V much better than the last print. It uses only
  data the examiner has for h1 / h2 (tapes plus calldata), with no live books.
- **Why it fits.**
  - Critique 2's ceiling (0.46 for the market 20 s later) says most of the gap to the print is timing of round results.
  - Group-P prints are public at block time, about 2 s after the feed.
  - X47 found that round-market takers follow its takes within 500 ms (6.7% vs 0.2-0.8%): they ride the same messages.
  - X164 was planned for VALIDATE-live only, and that live time no longer exists within budget.
- **Test.**
  1. On BUILD, define a round-end detector on print clusters: a group-P BUY print, and/or the map / match / handicap /
     total books moving toward the same team within 2 s. Fit its threshold against the bo3 sequence (BUILD only).
  2. On VALIDATE, V_hat(t) = table(score_pub(t)) + the BUILD offset, with prints stamped at or before t (block time,
     minus nothing).
  3. Score V_hat:
     - within one tick of its maker orders and burst tops, against the last print (0.305) and the 0.46 ceiling;
     - through the frozen X163 ladder machine (set unit);
     - the latency of score_pub behind V's own step.
- **Data needed.**
  - Tapes of the map, match and 665 round markets (cached);
  - `calldata_pub` signing ms for group-P membership (members fixed on BUILD, X127);
  - bo3 sequences for BUILD calibration only.
- **Signature if true.**
  - VALIDATE within one tick >= 0.40 on burst tops (>= +0.08 over the print, event-bootstrap CI excluding 0);
  - per-order gain >= +0.05;
  - score_pub lags V's own step by a median <= 5 s.

  This would be the first point-in-time price input that carries the private part. If the signal is too sparse (group P
  absent from many round ends), the gain stays under +0.03. The price item then needs the live book (co-receiver
  re-pricings within 20-50 ms), which only future exam blocks will have.

### 3. LoL natural experiment without the lolesports key (strong form of X184)

- **Hypothesis.** The operator's LoL value, on the earlier account (BUY-only, whole cents, band, merges; 100 shares in
  September, 10 in October), is the same architecture as CS2: a game-state value updated at major state changes on a
  feed some seconds ahead of the market. LoL is the one title where the full game state is public with wall-clock
  stamps, so the value function and its update events can be fitted with all inputs observed, then transferred to Dota.
- **Why it fits.**
  - Finding 15 (same design on LoL);
  - critiques 1-2 (the CS2 value is round-result driven);
  - Dota (half the forward fills) is a MOBA like LoL, and its DotaTV state is public (finding 24 of iteration 8, X118),
    yet X167's per-minute inverse fit reached only 0.17 within one tick. The form of the function, not the data, may be
    what is missing.
- **Test.**
  0. **Game ids.**
     - Events: 38 LoL events of 0x7d67f01d, 09-22..10-22 (cached activity, before H; Worlds 2026 10-03..10-17 plus
       September regional events).
     - Decode their calldata (`fetch_calldata.py`, as for `sib7d67`) for signing ms, prices and sizes.
     - Map each game to `RiotGameId` through Leaguepedia Cargo `MatchScheduleGame`: fields verified by
       `cargofields`, no key. Pace queries at >= 60 s each, one per tournament overview page.
     - Pull `feed.lolesports.com/livestats/v1/window/<id>` and `/details/<id>` frames (key-free per X184; 10-s windows
       with `rfc460Timestamp`, gold, kills, towers, inhibitors, dragons, barons).
  1. **Locking.** Lock its re-pricings to frame-level events (kill count, tower / inhibitor / dragon / baron changes)
     with a lag scan of -90..+90 s and shifted-clock nulls.
  2. **The future-print profile** for LoL.
  3. **Inverse fit, leave one game out.** V ~ gold difference x time, towers, dragons and soul, baron, inhibitors,
     kills. Compare within one tick against the last print.
  4. **Transfer to Dota.** Carry the fitted event kernel and rounding / offset rule over to the 10-22 / 10-31 Dota
     maps, on the iteration-8 D clock.
- **Data needed.** Leaguepedia Cargo (slow); Riot livestats (key-free); the sibling's LoL calldata (publicnode); the LoL
  tapes (data-api). All before H.
- **Signature if true.**
  - V's steps lock to objectives at a stable lag; for kills there is no lock beyond the objectives, if critique 1
    generalizes;
  - the inverse fit reaches >= 0.5 within one tick against the print's <= 0.35;
  - the transferred kernel lifts Dota within one tick over the print by >= 0.05.

  If its LoL steps precede Riot's frames, its LoL feed is faster than the official stats, which bounds the feed's
  position for every title.

### 4. Feed-state synchrony across concurrent events (E7) as a presence input (new; aimed at the primary metric)

- **Hypothesis.** Part of the presence residual is a common driver across concurrent, unrelated events: the feed's
  connection state (outages, reconnects, a vendor-wide pause), or the operator's process (restarts). Neither appears in
  any per-market feature. The co-subscribers see the same outages.
- **Why it fits.**
  - presence_auc 0.8834 sits below the activity baseline 0.8907 after 13 iterations, with no feed-state feature;
  - X106's two idle-but-up gaps showed group P quiet at the same times (10.6 / 2.0 prints per hour vs 52.8);
  - the merge loop's 6 phase breaks (X95) show the process does restart;
  - the brief's E7 has not been run.
- **Test.**
  1. Out-of-fold BUILD residuals of the presence model (GroupKFold over 2-h blocks), then `residual_clustering` across
     markets of DIFFERENT events (p <= 0.01, ratio >= 1.5; keep only bins well after each start, per the brief).
  2. Look up the top clusters against:
     - group-P members' simultaneous silence across all their events;
     - the merge-loop phase;
     - Polymarket status history.
  3. If synchrony holds, add a point-in-time feed-state indicator: seconds since any group-P member printed in ANY
     event (block time). Measure `incremental_auc` over the activity baseline and v5, grouped by 2-h blocks.
- **Data needed.** The existing presence bins (`bins_*.parquet`), tapes and calldata_pub (group-P prints), merge rows.
  All historical.
- **Signature if true.** A synchrony ratio >= 1.5 at p <= 0.01 whose top clusters coincide with group-P-wide silences;
  the feed-state feature adds >= +0.01 VALIDATE AUC over the activity baseline (CI excluding 0). If false, presence is
  per-market and E7 closes with its power statement.

### 5. A pure-Python CS2 demo game-event extractor, so X37 / X122 need one consent instead of two (strong form)

- **Hypothesis.** The tick-level truth separates the round-result reading from the kill-state reading outright:
  `round_end`, `player_death`, `bomb_planted`, `bomb_defused` and `round_freeze_end` ticks. Aligned to proposal 1's
  feed clock, it also gives the feed's delay behind the server per organiser (relay at tv_delay + about 24 s, against
  a server-side feed).
- **Why it fits.**
  - Critique 1 needs a confirmation at tick level.
  - Critique 2's organiser-structured lead calls for a per-organiser delay measurement.
  - The consent items have waited since iteration 3, partly because they bundle a PyPI parser install with the
    downloads.
- **Test.**
  1. Write a ~250-line extractor with no third-party code:
     - PBDEMS2 outer frames: varint cmd with the 0x40 compressed flag, tick, size;
     - a pure-Python Snappy decoder;
     - a minimal protobuf wire-format reader;
     - the `CDemoPacket` bit reader (ubitvar type, varuint size);
     - `CMsgSource1LegacyGameEventList` / `CMsgSource1LegacyGameEvent` for the five events.
     No entity parsing is needed.
  2. Verify bo3's demo host with HEAD requests only, so the request to the user can state file names, host and sizes
     (the `demo_header` field shows which games have demos).
  3. With the user's consent for about 10-20 VALIDATE maps (50-300 MB each; 59 GB free):
     - fit the per-map tick-to-wall offset to proposal 1's clock;
     - score V's changes at kills against round ends;
     - estimate each organiser's delay.
- **Data needed.** The demos (consent to download); bo3 game metadata (cached).
- **Signature if true** (round-result reading). V steps within a few seconds after `round_end` + delta, with delta
  constant per organiser, and shows no step at kills or plants beyond the shifted-clock null. If V steps at kills,
  proposal 1's table must carry an in-round term fed by the kill clock, and the price item needs these events.

## What I would not spend budget on now

- Live-only recorders and tests: there is no development live block within budget after 12:00 today.
- Further bookmaker relays for CS2. Bookmakers price round ends at the stream's pace. hawk.live showed they track the
  print in Dota, and critique 2 places V's lead before the stream.
- More web sources of in-round state. HLTV, SofaScore and Sportradar's public widgets are closed, and bo3 has no kill
  times.
