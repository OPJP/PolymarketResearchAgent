# Panel, iteration 14: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and what the order record (filled, censored) and the live book (uncensored) can say
about the input behind V. The open question the latest iteration left is R (V prices round results that the feed
delivers early) against K (V prices in-round events: kills, plants). Every proposal below either decides that question
without demos or a bo3-duration clock, or says what the order record can and cannot carry.

Written 2026-11-01, about 12:05-12:45 UTC, inside the sealed block 11-01 12-18. I read no record of that block.

## What I read and what I ran

I read:

- BRIEF.md: the premise, the hidden-dimensions section and the direction catalog;
- NOTES.md: iteration 14 in full (competing explanations, E3-1, E2 / E7, findings 1-17, late addition 14), and earlier
  sections by search (iteration 1 header, X79 / timer_owner, finding 19 of iteration 6, Z8, crossbook sync);
- state.json: the catalog A1-X203 and E1-E7 (status and evidence of every item), the components and target metrics;
- FINAL_RULE.md (the components table and the presence lines);
- panels/iter13_mechanics.md in full, and the proposal titles of every earlier panel;
- results: crossbook_sync*.json, loop_steps.json, withdrawals*.json, message_coverage.json, e3_screen.json,
  round_takers_hist.json, owner_census.json.

`tools/sealed.py tommy-cs2-maker`: no released lots; the future is examined up to 10-31 00:00; development blocks
after H are 10-31 00-06, 10-31 12-18 and 11-01 06-12; the current block 11-01 12-18 is sealed.

Every record I used is development data:

- `orders.parquet`, `calldata_all`, the queue_replay record (public calldata) and the per-market tapes, all before H;
- the BUILD-live tables built by the investigation from the 10-31 12-18 block: `own_bursts_dev.parquet`,
  `iter12/slot_vrel_rows.parquet`, `dev_markets.parquet`;
- the shared recorder's `sports` feed for 10-31 12-18 (`.cache/live/dev/sports/20261031T1*.jsonl.gz`), read for event
  names and score granularity only;
- bo3 `/games/<id>/rounds` responses already in the shared HTTP cache (read-only; 355 games, 6,218 rounds);
- data-api taker trades of the markets of two VALIDATE events (cs2-priv-fnc-2026-10-21, cs2-bcg-jjh-2026-10-22),
  through the shared adapter, clamped to before H;
- one web search (the 7702 delegate's identity).

I opened nothing in `.cache/live/sealed/`, wrote nothing outside this file and my scratchpad, and started no recorder.
My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m14\`
(`vpath.py`, `vclass.py`, `refractory.py`, `dark_split.py` with `dark_split.json`, `per_round.py`, `alive.py`,
`endclass.py`). Each process ran under 300 MB and under 5 minutes, after `resources.py --wait-mem 600`.

## Critique: what the investigation is missing or getting wrong

### 1. The "85% of re-pricings at invisible messages" are informed, but the historical V-change label mixes in ladder artefacts

Finding 9 says only 12-18% of its V-change decisions have a visible group-P take in the 3 s before. Nobody has asked
whether the other 85% carry information. I split the E3-1 decisions (same definition: first order of a 50-ms burst
whose filled top differs from the previous filled top on the token; 16-22 Oct) into three classes:

- visible-agree: a wallet-free group-P take on the event in the 3 s before, in the same team direction;
- visible-other: such a take, in the other direction;
- dark: none.

For each class I measured the signed move of the market's clean print (wallet transactions excluded), from the last
print before the decision to t + h, in the decision's direction:

| Period, class | n | +10 s mean (c) | +10 s share up / down | +60 s mean (c) | +60 s share up / down |
| --- | --- | --- | --- | --- | --- |
| BUILD, dark | 6,276 | +0.80 | 0.29 / 0.11 | +1.88 | 0.54 / 0.25 |
| BUILD, visible-agree | 1,138 | +4.44 | 0.79 / 0.07 | +5.85 | 0.83 / 0.13 |
| BUILD, visible-other | 226 | -2.35 | 0.25 / 0.60 | -3.39 | 0.33 / 0.62 |
| VALIDATE, dark | 8,011 | +0.83 | 0.29 / 0.11 | +1.79 | 0.52 / 0.25 |
| VALIDATE, visible-agree | 1,137 | +4.76 | 0.78 / 0.08 | +6.47 | 0.81 / 0.13 |
| VALIDATE, visible-other | 236 | -1.82 | 0.29 / 0.54 | -2.45 | 0.33 / 0.58 |

So the dark decisions point the right way about 2 : 1 at 60 s, at about a third of the visible ones' strength. Two
caveats keep this from being a finding:

- **Censoring artefacts.** On the filled record, a refill of the lower slots (top V - 3c after a burst whose filled top
  was V) counts as a "down" V-change, and a later return to V counts as "up". Falling tops are the more "informed" of the
  dark ones (+2.6-2.7c at 60 s, 0.58-0.61 up) and rising tops the less (+1.1-1.3c, 0.47-0.48 up). That is the wrong
  way round for a clean value signal and the right way for sweep-filled lower slots, after which the market keeps
  falling.
- **Followers.** Non-own makers join its new top within 2 s at 3.5-6.4 times the shifted rate (X182). A print that
  follows its level can be the joiners' doing, not information.

The visible-other class (its value moving against the informed takers) loses 2-5c by 60 s. These are most likely
lower-slot refills on the losing token, the same artefact.

Consequences:

- the historical "V-change" unit (E3-1, finding 5, finding 9, `message_coverage`, X189) needs a censoring-free
  definition before counts or shares are read as message counts;
- whether the dark re-pricings are messages is the R-vs-K question in another form (proposal P3).

### 2. On the uncensored live book its value moves several times per round, mostly to within a cent of the others' best

From the X163 rows of BUILD-live (10-31 14:50-18:00; V_after = its own top after each validated add burst; 1,508
bursts, 1,169 with a changed V):

- V-change sizes: 1c 563, 2c 261, 3c 114, 4c 73, 5c 69, 6c+ about 90.
- Merged into "moments" (changes on a token within 2.5 s), the shin-isg map 1 book has 125 / 127 moments per token in
  56 min (2.2-2.3 per minute, median gap 10-11 s, 69-70% of gaps under 20 s). The gls1-pcy map 2 book has 1.7-1.8 per
  minute. The match books have 0.8-1.0 per minute (bhe-bar2 2.6-2.7).
- Against others' best bid J at the burst: 65% of V-changes land within 1c of J, 19% at 2c or more below it, and 15%
  at 2c or more above it. On shin-isg map 1 the leading changes come at 0.71 moments per minute (median gap 20 s); on
  gls1-pcy map 2, 1.5 per minute (n 17).
- A large move does not open a quiet window. After a moment of 6c or more on the map books, the next moment comes
  within 5 s in 51% of cases (median 4.9 s, n 45).

A CS2 map runs at about 0.4-0.5 rounds per minute. R allows about one leading value step per round plus mechanical
moves. The live path shows two to five times that rate of moves, most of them to the others' level. This does not
decide R vs K: joins and co-receiver re-pricings (iteration 11, finding 13) can produce the at-J moves. But this is the
only record where V's step sequence is complete, and nobody has aligned it to the rounds of those maps (proposal P3).

The filled historical record gives a lower bound with artefacts. Over the 92 bo3-matched maps, filled V-change moments
(1 s merge, map book) number 2.65 per round (median map 2.4), and 1.39 per round for changes of 3c or more.

### 3. The round books cannot anchor a round clock in these events (negative check)

The iteration-13 information panel proposed simultaneous prints in each map's handicap and total-rounds books as clock
anchors, and the iteration-14 plan lists "winner-direction jumps on every book". I counted in-play taker trades
(data-api, gs - 10 min to gs + 4.5 h, before H) on two busy VALIDATE events:

- **cs2-priv-fnc.** 19 round-handicap / round-O/U markets: 18 with 0 trades, one with 13. The series-level books trade:
  map handicap 1,083 and 8, games total 56.
- **cs2-bcg-jjh.** 16 round markets: counts 0-6 (six-trade maximum). Moneyline 998, maps 306 / 974, games total 98,
  map handicap 16 / 11.

Round books in tier-3 events are empty in play, so they cannot serve as anchors, and the X47 (b) live test will have
nothing to read. The map-handicap and games-total books move with map results, not round results.

### 4. The shared 7702 delegate is MetaMask's, so the six-account claim rests on co-signing counts

`0x63c0c19a282a1b52b07dd5a65b58948a07dae32b` is MetaMask's `EIP7702StatelessDeleGator`: verified source on Etherscan
under that name, with transactions labelled "MetaMask: EIP-7702 Delegator"; it is the implementation the MetaMask
Delegation Framework audit describes. Sharing it says only that the owners use MetaMask smart accounts, which is
common. The two new accounts therefore rest on 7 and 16 near-coincident orders (12.6x and 9.0x per ms).

Two cheap checks would harden or refute this before anything is built on the new accounts:

- their merges inside the operator's 300-s passes (one sequential pass at about 7.28-s spacing across accounts);
- 0-5-ms cross-market co-signing with the wallet in the same session (one process serializes its signings across
  events, as X203 found).

The owner census lists 0xca0b532d (owner 0xdd952f37) and 0x2b55d2ee (owner 0x4e87b336) among the MetaMask-delegate
BUY-only makers. Both are also in iteration 6's `timer_owner` set (critique 5).

### 5. An operator account quoted GRID events on the BUILD-live block, where the sports socket carries round scores

Iteration 6's `timer_owner.json` found the filled 100-share whole-cent BUY orders in four untraded 10-31 12-18 markets
(FOKUS-BakS, JJH-BMB, SKR2-FOR10, lowcor1-tdp). They belong to 0xca0b532d, 0x2b55d2ee, 0xd3bd48ab, 0x68915897,
**0xd2bb9459** (10 orders) and 0x5d40576b. Iteration 14 (X203) has since shown that 0xd2bb9459 co-signs with the
operator at 0-5 ms. Nobody has connected the two facts. All four events are GRID events in `universe_t0`:

| Event | League | Tier | grid_series_id |
| --- | --- | --- | --- |
| cs2-fokus-baks | CCT Europe | 4 | 3009872 |
| cs2-jjh-bmb | Circuito Retake | 4 | 3022561 |
| cs2-skr2-for10 | CCT Europe | 5 | 3013899 |
| cs2-lowcor1-tdp | Gamers Club Masters | 4 | 3022531 |

The shared recorder's development `sports` files for 10-31 12-18 carry round-level scores for exactly these events:
FOKUS-BakS 54 score changes, Low Cortisol-Turma do Pagode 49, Sakerorg-Fortress 45, JiJieHao-BASEMENT BOYS 43. The
wallet's own events carry map scores only (ShindeN-Isurus, Galorys-Procyon, Bounty Hunters-BARCA: 1-3 changes).

On the BUILD-live block the investigation therefore already holds three things together:

- the recorded books of those markets (`tommy_cs2_near` records every development-start CS2 book);
- an operator-process ladder in them;
- a wallet-independent round-by-round score stream.

That is the true round clock X195 is looking for, on a development unit (proposal P2).

### 6. Smaller points

- **X201's lag curve on V-change bursts is true by construction.** By definition a V-change burst is one where V
  differs from the V in force just before, so any lagged copy of V misses it. The informative numbers are the class
  shares (89.6% of filled orders are V-change bursts) and the refill curve (0.808 at 0+, 0.532 at 4 s). The conclusion
  holds: the fill-weighted price item is set at message time.
- **bo3 `alive_time` (team sum) calibrates cleanly.** For teams with no deaths, alive_time / 5 = round_duration -
  17.6 s (IQR -20.4 to -15.5 s, n 814). So round_duration includes about 17.6 s of freeze and restart time, and the team
  sum gives each side's mean death time since freeze end (median 0.38 of the round for wiped teams). The per-player
  field has 6-s steps (iteration-10 information panel), so treat it as a coarse kill-timing summary. P1 uses it only to
  size the decision gap.

## Proposals, ranked by the chance they close the gap

### P1. Decided-early rounds: the sign of V's lead over the print separates R from K (new; uses the cached bo3 end reasons)

- **Hypothesis.** In about 29% of CS2 rounds the outcome is settled well before the official round end:
  - **defuse after T wipe** (BombDefused with all five T dead): 724 of 6,218 cached rounds (12%); the round ends at the
    defuse, 5-10 s or more after the last T death;
  - **bomb with CTs alive** (TargetBombed, CT deaths < 5, mostly saves): 1,065 (17%); the round ends at the explosion,
    up to 40 s after the plant, while the result is clear once the CTs cannot or will not retake.

  Stream watchers, and so the print, react to the decisive moment. Under **R** V steps at the feed's round-end
  message, after the official end. So in these rounds V's lead over the print shrinks by the decision gap, or turns
  into a lag. Under **K** (kills and plants priced at the message) V steps at the decisive kill, and its lead is the
  same as in elimination rounds (CT_elim_T 2,180, T_elim_CT 1,806, where the last kill is the end).
- **Why it fits.** R and K are undecided because no public anchor set gives a reliable clock (late addition 14: snaps
  only 1.30-1.45x the reversed placebo). This test does not need an accurate clock. It compares the same clock's
  readings across end classes: the clock's noise is common to all classes, and the effect lies in a sign. The
  print-anchored clock already has 412 rounds with both ends snapped, and on it 76% of V's winner-signed move comes
  before the print's jump (mid-round 49%, late 27%). Finding 10 split cluster directions by plant and end reason, but
  not V's timing against the print.
- **Test** (BUILD to set the windows, VALIDATE for the verdict).
  1. Join each snapped round of `round_clock_print_15_30` (and the cluster and single-take clocks) to its bo3 row: end
     reason, deaths per side, plants, `alive_time`.
  2. Per class, measure V's winner-signed change in fixed windows around the print anchor e_r: mid, late (-10..-1 s),
     at (-1..+4 s) and after (+4..+40 s). Report the share before e_r and V's step time relative to e_r, defined as the
     first time V reaches half its round move.
  3. Statistic: the difference in V's before-anchor share (or median step time) between decided-early classes and
     elimination classes, with a map-cluster bootstrap. Repeat with the print's own move as the control, which should
     show no class effect.
  4. Inside "bomb with CTs alive", regress the step-time difference on the gap (round end - plant), with
     `bomb_plants` and the CTs' mean death time from `alive_time`.
- **Data.** Everything is cached: `round_clock_*.json` and the code that made them (`code/iter14/round_clock.py`), bo3
  rounds of the 86 maps, `orders.parquet`, tapes.
- **Signature if R.** In decided-early rounds V's before-anchor share falls to 40% or less (elimination rounds about
  75%), and its half-move time sits after e_r, more so the longer the decision gap; in elimination rounds nothing
  changes.
- **Signature if K.** No class difference: the bootstrap CI of the difference covers 0 and excludes R's predicted drop.
  V moves at the decisive kill, so its private input contains in-round events.

Either way the result fixes which public score (round results) or which event stream (kills) a structural V would need.

### P2. The operator's GRID ladders on BUILD-live, with the sports socket's round scores as a true clock (new data link; strong form of X188 / X195)

- **Hypothesis.** The operator's process also quotes GRID CS2 events (X188: 0x67119033, 0x52661b8e in October, and
  0xd2bb9459 on 10-31, critique 5). In those events Polymarket's sports socket publishes the round score at every round
  end. With that clock and the uncensored live book, three questions get a direct answer:
  - does the operator's V in GRID events carry in-round information beyond the print (X188's first pass: 0.66 vs 0.36
    on 71 rounds)?
  - is that information concentrated at round ends (R) or spread over the round (K)?
  - is it the same valuation process as in non-GRID events (five slots, series map, 504-ms loop), and therefore a view
    of the same model with a different input?
- **Why it fits.**
  - Critique 5: four GRID events with round-level socket scores (43-54 changes each) on a development block, recorded
    books, and an operator-process account among their makers.
  - X103 measured the socket's map-score lag for GRID (minimum 20 s, p10 47 s), so a round tick bounds the round end
    from above.
  - The bo3 durations then only fill the gaps between ticks, instead of carrying the whole clock.
- **Test** (development block 10-31 12-18 only).
  1. **Identity on 10-31.** For 0xd2bb9459, 0xca0b532d, 0x2b55d2ee, 0xd3bd48ab, 0x68915897 and 0x5d40576b, decode
     their transactions in the four GRID events and the wallet's in its events. Test 0-5 ms cross-market co-signing and
     merges inside the operator's 300-s passes.
  2. **Own-level label.** Fingerprint their levels in `tommy_cs2_near` by size (100 / 200 / 20 / 5) and validate with
     calldata as in X92. Build V_after paths per token, as for the wallet.
  3. **Clock.** Take the socket's round ticks (score path, receive time). Estimate the per-event lag of the tick behind
     the market's winner-direction print jump, and snap with the X195 tracker using the socket as the backbone. Report
     snaps against a reversed and a shifted sequence.
  4. **Measure** (as in X181 / late addition 14): V's winner-signed change mid-round, late, at the round end and after;
     the in-round AUC for the round winner against the print; V's reaction time to the socket-clock end against the
     print's. Also the P1 split by end class, from bo3 once the 10-31 maps are parsed.
  5. **Process signatures.** Five-slot bursts, the 1.512-s slot cooldown, the band, the series slope on the match book,
     and the 504-ms phase on quiet bursts.
- **Data.** `.cache/live/dev/tommy_cs2_near` and `sports` for 10-31 12-18 (development); Polygon calldata for a few
  thousand txs of those markets; bo3 rounds for the four GRID matches (development units).
- **Signature if true** (same process, private in-round V).
  - Co-signing and merge-pass identity hold on 10-31.
  - Mid-round AUC for the round winner at least 0.15 above the print's on the socket clock.
  - The share at round ends against mid-round decides R / K directly. If GRID V is R-like and the non-GRID V shows the
    same step profile on the message clock (finding 5), R becomes the leading reading for the operator's model.
- **Signature if false.** The GRID ladders sit at the print (no private input in GRID events), or the accounts are not
  the operator's. The operator's private value is then Feed-P-only, which narrows the vendor to the push feed's
  coverage, and the GRID books give a print-pegged control on the same block and clock.

### P3. Are the dark re-pricings messages? Censoring-free and follower-free informativeness, and their count per round (strong form of finding 9 / E3-1 / X189)

- **Hypothesis.** R predicts about one informed value step per round (the round result, perhaps a plant), with the rest
  of its V-changes mechanical (joins, refills, pair-cap adjustments). K or D predicts several informed steps per round,
  their number rising with the round's kills.
- **Why it fits.**
  - Critique 1: the dark decisions are informed at about a third of the visible ones' strength on the raw label, but
    that label is contaminated.
  - Critique 2: the uncensored path moves 2.2 times a minute per token on a map book, 65% of the moves to J ± 1c.
  - Historical lower bound: 2.65 filled V-change moments per round.
  - Finding 10: V moves +1.0c at clusters that favour the round's eventual loser.
- **Test.**
  1. **Censoring-free label (historical).** Count a decision as a V change only when its filled top lies above every own
     level that the slot rule (X163, five slots, cooldown) allows given the previous burst and the fills since. Use the
     union top of the wallet and its 5-share siblings (98% inside [V - 4c, V]) to see the true top. Report how many of
     the 85% dark decisions survive.
  2. **Follower-free outcome.**
     - (a) AUC of the decision direction for the bo3 round winner of the round in progress, on the print-anchored and
       single-take clocks, against the print's direction at the same time.
     - (b) Signed markout on the OTHER book of the event, using only txs whose makers include no joiner (any non-own
       maker signing within 2 s after the decision at its new top ± 1c, from calldata).
     - (c) Map winner given the print at t (logistic, event-clustered).
  3. **Count.** Informed dark moments per map (1-s merge across the event's books; informed = positive on (a) or (b)
     with thresholds set on BUILD), regressed on bo3 rounds and total kills (`/rounds` team `kills`) with map duration as
     the offset. Repeat on BUILD-live's uncensored path with the lead-of-at-least-2c class.
- **Data.** Cached: `orders.parquet`, `calldata_all` / `calldata_pub`, the sibling calldata for the union top, tapes,
  bo3 rounds, the BUILD-live X163 rows.
- **Signature if K.**
  - Dark decisions that survive step 1 keep a round-winner AUC of at least 0.60 beyond the print.
  - At least two informed moments per round.
  - A positive kills coefficient at fixed rounds.
- **Signature if R.** After steps 1-2 the dark decisions' information disappears: their markout was artefact or
  follower effect. Informed moments are about one per round, and they are the visible ones plus a few. Then about 85% of
  its re-pricings are mechanical, so a structural price rule needs only the round-result times and a join rule.

### P4. The uncensored BUILD-live path against the bo3 rounds of the same maps: a freeze-time refractory test (new; the uncensored form of X195 / X199)

- **Hypothesis.** CS2 has hard dead time: the round restart delay (about 5-7 s) plus freeze time (15 s) plus the time
  to first contact, so in-round events cannot occur for about 25-40 s after each round end. If V prices in-round events
  (K), its leading moves stop for that long after each round-end step and cluster in the action phase. If it prices
  round results (R), it makes one leading step per round and is quiet otherwise.
- **Why it fits.** Critique 2: no quiet window after large moves (51% followed within 5 s), but without round ends a
  large move is not necessarily a round end. The bo3 rounds of the 10-31 maps (shin-isg map 1, gls1-pcy map 2,
  bhe-bar2 maps) have not been fetched; bo3 parses demos within about a day, and these are development units.
- **Test.**
  1. Fetch the bo3 rounds for the wallet's 10-31 BUILD-live maps through the shared cached client.
  2. Align the lead-class V-steps (2c or more above J) and their signs to bo3's winner sequence and durations with the
     pause-aware DP (X160 steps 1-3). On the uncensored path every round-end step is visible, so the alignment is far
     better constrained than on fills. Validate it against the print's winner-direction jumps.
  3. Report the hazard of lead-class and at-J V-moments against time since the aligned round end (0-60 s, 2-s bins),
     and the count of lead moments per round.
  4. Same for the Dota map ty-gl game 1 on 10-31, with OpenDota kill times: fit the offset D on P4e's and the wallet's
     takes only, score the maker re-pricings, with a scan-maximum side-label null. This removes X132's circularity.
- **Data.** `slot_vrel_rows`, `own_bursts_dev`, bo3 rounds for 3-4 maps, OpenDota for the 10-31 ty-gl match.
- **Signature if K.** Lead-class hazard near 0 for about 25 s after each aligned end, then 2-5 lead moments in the
  action phase.
- **Signature if R.** One lead moment within a few seconds of each aligned end, flat otherwise, with the at-J moves
  following J.
- **Limit.** Only 2-3 CS2 maps (about 60 rounds); this is a check on P1 / P3, not a verdict alone.

### P5. Two order-construction fingerprints that name the feed class: the exact series identity and the rounding rule (strong form of X173 / X200 / X198)

- **Hypothesis.** If the bot holds one unrounded map probability p and computes the match quote itself as
  series(p; maps won, q), every same-ms map / match co-repricing satisfies one identity:
  - V_map = R(p - m);
  - V_match = R(series(p) - m');
  - R is floor or nearest, m and m' are margins, and q is fixed per event.

  An odds feed that supplies both a map and a match price would not satisfy one identity: bookmaker match lines carry
  their own margin and lag. Whether the feed is a price feed (H120, an odds product) or a state feed with the bot's own
  model changes the vendor search.
- **Why it fits.**
  - Iteration-13 mechanics critique 1: slope 1.05 on s x dV_map, 53 pairs.
  - X198: slope 0.46 on BUILD.
  - The pair constant K = 0.97.
  - Nobody has tested exactness or the rounding rule, and the 1-cent rounding rule is worth up to a tick of the price
    item on every order.
- **Test.**
  1. Collect every same-ms (within 5 ms) co-repricing pair on the map and match books of an event: historical fills,
     5-share sibling union tops, and BUILD-live uncensored pairs.
  2. Per event, search (q, m, m', R) on BUILD: the share of pairs consistent with a single p interval, with q free or q
     from the pre-game match price inverted through the Bo3 formula. Compare with a null that pairs each map change with
     a random match change of the same event.
  3. With the identity fixed, read p at sub-cent resolution where the two roundings intersect. Check whether the bot
     rounds p down (floor) or to the nearest cent, and whether m depends on the token or the price level.
- **Data.** Cached; no fetch.
- **Signature if the bot computes the series.** At least 90% of pairs fit one identity per event; q equals the pre-game
  implied map strength within 2c; one rounding rule.
- **Signature if the feed supplies both prices.** Residuals of ±2c or more remain, with match changes not tied to map
  changes at the same ms. The private input is then a price feed (odds), and the vendor search moves to live-odds
  products for these leagues.

## Overlap with the ledger, the catalog and the other panels

- **P1.** New. Related: X189 / X195 (clocks), finding 10 (cluster directions by end reason), X181 (in-round drift).
  New here: the end-class contrast of V's timing against the print, which does not require an accurate clock.
- **P2.** Related: X188 (operator GRID quoting, first pass 11 maps), X195, X164, X203, timer_owner (iteration 6).
  New: the link between an operator-process account and the four GRID books of the BUILD-live block whose socket feed
  carries round scores, so the clock X195 wants already exists on a development unit.
- **P3.** Related: finding 9 (`message_coverage`), E3-1, X182 / X186 (joiners), X163 (slot rule), X176 (union top).
  New: the informativeness split of dark decisions (critique 1), the censoring-free label and the per-round count
  regressed on kills.
- **P4.** Related: X195, X199, X160, X132. New: the uncensored path, the 10-31 bo3 rounds and the freeze-time refractory
  signature; for Dota, an offset fitted on takes and scored on maker re-pricings.
- **P5.** Related: X173, X200, X198, H120 / X133. New: the exactness and rounding tests and the feed-class reading.
- **Negative checks, so nobody redoes them.**
  - Round O/U and round-handicap books have 0-13 in-play taker trades per market in two busy VALIDATE events (critique
    3): no round-book clock.
  - The 7702 delegate is MetaMask's stateless delegator (critique 4): no operator information in sharing it.
  - The X201 lag curve on V-change bursts holds by construction (critique 6).
  - bo3 team `alive_time` = 5 x (round_duration - 17.6 s) for teams without deaths (critique 6).

Sources for critique 4: [Etherscan, 0x63c0c19a...](https://etherscan.io/address/0x63c0c19a282a1b52b07dd5a65b58948a07dae32b),
[Consensys Diligence, MetaMask Delegation Framework audit (Feb 2025)](https://diligence.security/audits/2025/02/metamask-delegation-framework-february-2025/).
