# Panel, iteration 14: information source and data (fresh eyes)

Lens: what the operator sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations (R: round results seen early, against K: an in-round kill state). Written
2026-11-01, about 12:10-13:45 UTC. The current block (12-18) is sealed. Nothing in `.cache/live/sealed/` was opened.
Live recordings were read only through `tools/live.py iter_live` (development blocks 10-31 12-18 and 11-01 06-12).
Every market, fill and listing I touched belongs to a unit that started in a development period:
- 16-22 Oct and earlier (before H);
- 10-31 12-18;
- 11-01 06-12.

## What I read and what I ran

I read:
- BRIEF.md: the premise, the hidden-dimension section and the catalog;
- NOTES.md: iteration 14 in full; iterations 1, 4, 8 and 13 by section;
- state.json: the catalog A1-X203 and E1-E7 with their evidence, the components, `dimensions` (38) and the target
  metrics;
- FINAL_RULE.md by section;
- the iteration-13 information panel and the proposal titles of every earlier panel.

There are no EXAM or wall-audit files.

Scripts and outputs are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter14info/`.
Each process stayed under 300 MB, and `resources.py --wait-mem 600` ran first. Nothing was written to the workspace
except this file, and no decoded data was put in `.cache/re/`.

- `bo3_fields.py`, `bo3_hdr.py`, `bo3_bets.py` (bo3 cache, offline):
  - bo3 round rows carry `created_at` / `updated_at`, but they are a batch insert after the demo parse (all rounds of
    a 10-19 map stamped 10-20 11:17:44.60-.63), so they are not a live clock;
  - `demo_header.server_name` is "unknown" on all 262 games (manually uploaded demos);
  - `bet_updates` is Thunderpick only.
- `sep_params.py`: Gamma listing parameters of the operator's CS2 / Dota / LoL markets by day, 07-07..10-01.
- `feed_dating.py`: daily esports trades of P4e, 0x2005d16a, 0x72aaaaf9, 0xf1ee4842 and 0x52661b8e, 08-20..10-05.
- `names.py`: data-api / Gamma profile fields of the group-P and group-G members.
- `unit_test.py`: is selection homogeneous within PandaScore's `serie` / `tournament` objects?
- Operator accounts per development event (inline scripts; data-api trades with makers included):
  - 10-31 12-18 and 11-01 06-12;
  - 16-22 Oct against the 384-event selection table.
- Sports socket and `tommy_cs2_near` coverage of the GRID events quoted by the operator (inline scripts, `iter_live`).
- `dota_snap*.py`: 0x7d67f01d's 11-01 Dota orders (123 txs decoded via publicnode into the scratchpad) against
  `tommy_dota_rt` snapshots.
- Web, as a plain visitor (docs and press pages only; no account, no key):
  - PandaScore: developer docs (low-latency feed overview, CS data sample, sandbox, `llms.txt`), its blog post of
    2026-05-06, its "predictions" page, and its status page and RSS;
  - GRID: the Polymarket partnership press release.

## Critique: what the investigation is missing or getting wrong

### 1. The operator's live decisions moved to its other accounts, and "never GRID" is an account allocation

On the development blocks after T0, I counted the fills of every known operator account in every event of the
notebook's development universe (data-api trades, makers included).

| Block | Study wallet | 0xd2bb9459 | 0x7d67f01d | 0x52661b8e |
| --- | --- | --- | --- | --- |
| 10-31 (dev) | 5 events, 723 fills | 3 events, 774 fills | 1 event, 67 fills | 1 fill |
| 11-01 06-12 | 0 | cs2-bca-pha, 215 fills | cs2-the9-5s 232 fills, dota2-synaps-hn 140 fills | 0 |

- On 10-31, 0xd2bb9459's three events are all GRID: cs2-fokus-baks (CCT Europe), cs2-jjh-bmb and cs2-og1-is (Circuito
  Retake). 0x7d67f01d's event is cs2-1win-5s (Moscow Cyber Games, tier 5).
- On 11-01, cs2-bca-pha is GRID: CCT Europe Series #12, gridSeriesId 3009874 on Gamma now. Iteration 14 called it
  non-GRID. cs2-the9-5s (tier 5, non-GRID) and dota2-synaps-hn (tier 5) complete 0x7d67f01d's events.
- So finding 16 ("the 11-01 06-12 VALIDATE-live block closes with no wallet record ... the pre-registered live tests
  have no units") is wrong at the operator level. The operator traded three events in that block, two on recorded
  books.
- Each event went to exactly one account in both blocks.

The same holds historically. Activity of the five other accounts for 10-15 12:00..H, matched to the 384-event
selection table:

| Account | Trades, 10-15..22 | Events | Titles |
| --- | --- | --- | --- |
| 0x10d79cc7 | 17,247 | 148 | CS2 13,117, Dota 3,647, LoL 483 |
| 0xd2bb9459 | 17,955 | 39 | CS2 10,002, LoL 7,953 |
| 0x7d67f01d | 4,798 | 28 | CS2 3,853, LoL 730, Dota 215 |
| 0x67119033 | 1,628 | 30 | CS2 |
| 0x52661b8e | 2,545 | 24 | CS2 1,723, Dota 755, Valorant 67 |

All of them are about 0.97-1.00 BUY.

- **Of the 122 GRID events the study wallet never traded, 74 were traded by these accounts**, mostly CCT, Elisa,
  Logitech G Pro, United21 and ESL Challenger.
- **Of the 185 non-GRID events the wallet skipped, 20 were traded by a sibling.** 14 of them were traded by
  0x7d67f01d alone, inside the wallet's own leagues: DraculaN ×7, Stake Ranked ×2, Stake Pulse ×2, PGL ×1 and CIS LAN
  ×2, mostly with gp72 = 2-4. The E2 "false alarms" (Stake Pulse, PGL) are among them.
- 14 non-GRID events had both the wallet and a sibling.
- Read from the operator side, with the wallet's gp72 score, the BUILD AUC is 0.605 and the VALIDATE AUC 0.802,
  against 0.849 / 0.892 for the wallet. The wallet's selection is the class of events the operator routes to this
  account, not the feed's coverage.

**Caveat.** The attribution is strong for 0x7d67f01d, 0x52661b8e and 0x67119033:
- names;
- 7.8-28.9x co-signing;
- owner keys;
- the $2,000 funding link.

It is weaker for 0x10d79cc7 and 0xd2bb9459:
- 7 vs 5 and 16 vs 16 near pairs;
- a shared delegate that 19 of 499 owners use.

The one-account-per-event pattern on 10-31 and 11-01 supports 0xd2bb9459.

Consequences:
- "Selection: explained (0.970)" and "never GRID" describe the operator's account routing.
- The feed covers GRID and tier-5 events: the operator trades them with the same BUY-only design.
- The forward exam blocks may hold few or no study-wallet events: 0 of 3 operator events on 11-01 06-12.
- The siblings carry the data the investigation has been asking for (critique 2, proposals 1, 4 and 5).

### 2. The decisive R-vs-K data are already recorded, in development blocks

Iteration 14 closes with: "the decisive data remain kill / round-end ticks (demos, consent) or the live sports socket
on GRID maps". The second exists. In the development blocks, the shared `sports` recording carries a full per-round
score clock for the GRID events the operator quoted, and the own recorder `tommy_cs2_near` holds their whole books.

| Event | Socket score changes | `tommy_cs2_near` records | Operator fills |
| --- | --- | --- | --- |
| cs2-fokus-baks (10-31 15:00) | 55 (map 1 to 2-0) | 283k price changes, 981 trades | 176 (0xd2bb9459) |
| cs2-jjh-bmb (10-31 14:30) | 44 | 149k price changes, 789 trades | 176 (0xd2bb9459) |
| cs2-bca-pha (11-01 11:00) | 26 (map 1, 22 rounds, 11:03:26-11:44:32) | 174k price changes, 594 trades | 215 (0xd2bb9459) |

The cs2-bca-pha score changes come every 60-160 s, one per round, with the winner. Together these are about 110-130
rounds with:
- a wallet-independent round-END clock (up to the socket's latency, which can be fitted);
- the round winners;
- the operator's quotes at server-ms;
- bo3's per-round kills, plants and economy once parsed.

That is X195 step 1 and the X188 GRID window, available today without consent (proposal 1).

### 3. The feed has a public candidate, PandaScore's Low Latency Feed, and the notebook dismissed PandaScore for the wrong product

What PandaScore's own pages say (unverified marketing, but specific):

- **The product.** The Low Latency Feed covers "League of Legends · CS2 · Dota 2", exactly the operator's titles.
  - It is one websocket per match, `wss://live.pandascore.co/matches/{MATCH_ID}/low_latency_feed`.
  - Matches carry a boolean `low_latency_feed` (`?filter[low_latency_feed]=true`), and `GET /low_latency_feeds` lists
    matches live or starting within 15 minutes.
  - The server is in Belgium; connections are limited to 3 per match.
- **The pitch.** It is "built specifically for prediction bots and professional traders", "faster than the streams",
  and "in sync with our odds feed".
- **The coverage.** The predictions page lists about 10k matches per year in 3 games. Its CS2 data points are:
  - round scores;
  - player dead / alive status;
  - sides;
  - bomb status;
  - map and map picks;
  - the round timer.
- **Customers.** Polymarket is the one named customer.
- **Event types.** The live API's CS events (Pro Live plan) are `kill` (with `round_number`, `elapsed_round_time`),
  `round_start` and `round_end`, with `ts` in ms.

Sources: https://developers.pandascore.co/docs/low-latency-feed-overview ,
https://www.pandascore.co/blog/low-latency-esports-data-feed-prediction-bot , https://www.pandascore.co/predictions ,
https://developers.pandascore.co/docs/data-sample-csgo.md .

Fit with the evidence:

- **The listings are PandaScore's objects.** Polymarket's esports `eventMetadata` is `{league, leagueTier,
  pandascoreMatchId, serie, tournament, gridSeriesId}`. "serie" is PandaScore's own naming, so `leagueTier` is
  PandaScore's tier. X102's coverage boundary ("tier 3 22/22, tier 4 36/96, tier 5 0/144") is drawn in a PandaScore
  field.
- **The fixed-lag fan-out exists in exactly the three LLF titles.** From the notebook's own
  `subscribers_other_titles.json`, for cross-operator pairs:

  | Title | Pairs vs null | Lag IQR |
  | --- | --- | --- |
  | LoL | 7-16 vs 0-3 | 21.5-74.5 ms |
  | Dota 2 | 9-20 vs 0-1 | 27-105 ms |
  | Valorant | 13-16 vs 2 | 152-171 ms (no fixed lag) |

  CS2 shows the same ordering as LoL and Dota. LLF has no Valorant.
- **The notebook's dismissal checked the wrong product.**
  - It ruled PandaScore out through Polymarket's sports socket (iteration-8 finding 11: map scores 26-169 s behind
    the market).
  - The socket is PandaScore's standard data (gameId = pandascoreMatchId), not the LLF.
  - Its token ask (X55) is phrased for `live_supported`, not for `low_latency_feed`.
- **There is a conflict to keep in view.** In Dota the feed's messages sit about 1035-1050 s after OpenDota's
  `start_time` plus game time (`dota_feed_align_with1031.json`). I measured the same offset (1044 s) between
  Valve's public spectator snapshot and `start_time` + game time on an 11-01 PARI game (`tommy_dota_rt`; `st` equals
  OpenDota `start_time`). So the Dota feed is at the spectator delay, not "≤ 5 s from the game server". Proposal 5
  separates the readings.
- **The dimension is unhandled.** `feed_vendor_identity` is `missing / untested` in `dimensions`. This is the
  concrete thing to fetch.

### 4. Smaller points (measured, so nobody redoes them)

- **The 09-17 change point is not a Polymarket parameter change.**
  - On the operator's CS2 / Dota / LoL markets, `secondsDelay` is 1 everywhere from 07-07 to 10-01.
  - The fees are 0.05 / rebate 0.15 from 07-11; on some 07-07..07-15 markets they are 0.03 / 0.25.
  - Rewards are 50 / 4.5c from 08-03, and the tick is 0.001.
  - Nothing changes on 09-03 or 09-17.
- **The feed predates the operator's design.** The visible subscribers traded CS2 through the operator's silent weeks
  of 09-03..09-16 (P4e 205-1,369 CS2 trades a day; 0x2005d16a up to 4,872; 0x72aaaaf9 up to 976). The operator
  joined or rebuilt on an existing feed; this does not date a vendor launch.
- **Profiles.**
  - 0x2005d16a is "RN1" with xUsername "RN1polymarket" (X is blocked from here);
  - P4e is "aaaa298";
  - the trio are "Donkoo", "Absing" and "MaxFomo";
  - 0xf1ee4842 is "Jimmyman132".

  There are no bios. A web search found nothing linking RN1 to a data vendor.
- **No outage experiment.** PandaScore's status page (Atlassian; components Rest API, Live API, Widget, Trading Feed)
  has no incident after 2023-11-06.
- **The coverage unit is not PandaScore's tournament.** 8 of 38 multi-event (league, serie, tournament) groups are
  mixed. Examples:
  - PGL Bucharest Closed Qualifier, 9 of 13 traded;
  - Stake Ranked Episode 6 Closed Qualifier, 8 of 14.

  The leave-one-out tournament rate scores AUC 0.897 against 0.878 for the league rate (16-22 Oct, non-GRID). A
  per-match flag is consistent with this; a per-tournament flag is not.
- **No 15-minute cliff.** The study wallet's first filled order per event sits a median 0.9 min after the scheduled
  start, and 22.5% sit more than 15 min before it (up to 3 h). This does not fingerprint LLF's discovery window.
- **Dota, first look (inconclusive, n small).**
  - Sample: 0x7d67f01d's 115 orders on dota2-synaps-hn (11-01; 37 takes, 78 makers, 57-61 shares, BUY only).
  - They are not phase-locked to the arrival of Valve's public snapshots. Snapshots arrive every 4.14-4.79 s, and the
    order phase quantiles are 0.43 / 1.17 / 1.98 / 3.54 s.
  - Its takes follow a Valve-visible kill increment in only 3% of cases; 8-12% of in-game snapshots show one.
  - The lag scan of Valve-visible kills around its takes has no peak at 0-20 s.

## Proposals (ranked by the chance that they close the gap)

### P1. The GRID-map natural experiment on recorded development blocks: the operator's quotes against a public round-END clock (strong form of X188 and X195; R vs K decided; the feed's speed against GRID's public data)

- **Hypothesis.** The operator's private value is the round result. V steps once per round, a constant Δ after the
  true round end, and is flat mid-round (R). Or it moves at kills inside the round (K). On GRID maps the sports socket
  gives the true round sequence with wall-clock stamps; its latency can be fitted. The same maps have the operator's
  full quotes (0xd2bb9459) on the raw book, so R and K can be told apart without demos.
- **Why it fits.**
  - Critique 2: the data exist, about 110-130 rounds.
  - Critique 1: 0xd2bb9459 runs the same BUY-only design in these events.
  - Iteration 14's clocks snap only 1.3-1.45x as often as a reversed winner sequence. The socket's score sequence is
    the winner sequence with times, so no snapping to informed clusters is needed.
- **Test** (development only: 10-31 12-18 fokus-baks and jjh-bmb, 11-01 06-12 bca-pha map 1; recordings cut at the
  block ends).
  1. **The socket's lag.** For each map, the socket's round-change times minus the cumulative bo3 `round_duration`
     (pause-inclusive), for the rounds bo3 parses. The residual SD gives the socket's jitter, and the per-map constant
     gives its lag.
  2. **Its quotes.** Label 0xd2bb9459's levels on `tommy_cs2_near` by size fingerprint, with calldata of its filled
     orders (sizes 100-200-480, whole cents, BUY) for signing ms.
  3. **Round-locked path.** Build its value path V (top of its ladder per token) and the clean print, locked to the
     clock's round ends (lag -60..+30 s). Do the same mid-round, against bo3 kill counts per round, plants and
     `alive_time`-derived mean death times.
  4. **Statistics, on the true clock:**
     - share of V's >= 1c moves within [end - 3, end + 5] s;
     - the mid-round signed change for the round winner, as an AUC against the print's;
     - V's lead over the socket and over the handicap / totals books' deterministic moves.
- **Data needed.** All are local or public, development only:
  - `sports` and `tommy_cs2_near` via `iter_live`;
  - data-api trades and calldata of these three events;
  - bo3 rounds for them (parsed by now; they are development units).
- **Signature if true.**
  - **R:** >= 70% of V's >= 1c moves in a narrow window at a constant lag to the clock's round ends; mid-round
    winner AUC for V not above the print's.
  - **K:** a mid-round AUC >= 0.65 that rises with the kill margin, and V moving at clusters before the round end.
  - **Either way,** Δ gives the feed's lead over GRID's official public data.
- **If true.** For the exam's future blocks the sports socket is recorded in sealed blocks too, so on GRID events a
  socket-clocked table with a fitted Δ is an examinable input. The measured lead also tells whether the feed beats
  GRID.

### P2. Label the operator, not the address: relabel selection and presence over all six accounts and model the routing (new; affects every target metric and the exam)

- **Hypothesis.** The routing of an event to an account is a separate decision of the operator, made by event class
  (GRID / non-GRID, tier, title) and perhaps by time. The study wallet's "skips" in covered leagues and its zero
  activity on 11-01 06-12 are routing, not the feed's coverage. A rule decoded at the operator level is the strategy;
  the wallet-level target mixes routing into selection and presence.
- **Why it fits.**
  - Critique 1: 74 of 122 GRID events and 20 of 185 skipped non-GRID events went to siblings. 14 of the latter went to
    0x7d67f01d inside the wallet's leagues, including both Stake Pulse and the PGL false alarm.
  - On 10-31 and 11-01, one account per event, and 0 of 3 events on the wallet on 11-01.
- **Test.**
  1. Pull activity for all six accounts (development periods only) and build an operator label per event (BUILD /
     VALIDATE).
  2. Refit v5 on the operator label. Report:
     - selection and presence AUC against the activity baseline at both levels;
     - recall at the same lift.
  3. Fit the routing rule (which account gets the event) on BUILD and score it on VALIDATE. Inputs: listing-time
     fields (gridSeriesId, tier, title, league, start hour) and concurrency.
  4. Recount the forward development blocks at both levels.
  5. Put the question to the user: should the exam's wallet list be the operator's accounts? This is the user's call,
     not the agent's, and it must be settled before the next exam.
- **Data needed.** data-api activity of the six accounts (development periods only), the cached selection tables, and
  calldata for co-signing checks of the two weakly attributed accounts.
- **Signature if true.**
  - The routing rule predicts the account at >= 0.9 accuracy from listing fields.
  - The operator-level selection needs the GRID flag for routing only: coverage of group P / G becomes the operator's
    selection boundary.
  - The forward blocks show the study wallet's share falling: 0.46 of operator fills on 10-31, 0 on 11-01 06-12.
- **If false.** If the routing is not predictable, the wallet-level selection has a floor set by an operator coin.
  Either way the exam needs to know.

### P3. Name the vendor: PandaScore's Low Latency Feed (new; turns `feed_vendor_identity` from missing into fetchable)

- **Hypothesis.** The push feed is PandaScore's LLF, or that product's message stream. Its CS2 messages are kill /
  round_start / round_end events plus frames (alive status, bomb, round timer), one websocket per match, server in
  Belgium. Coverage is the per-match boolean `low_latency_feed`.
- **Why it fits.** Critique 3:
  - titles CS2 / Dota / LoL with no Valorant, matching the fan-out by title;
  - Polymarket's metadata is PandaScore's, and the coverage boundary sits in PandaScore's tier field;
  - a product sold to prediction bots, with Polymarket a customer;
  - per-match sockets fit E7's null (no cross-event synchrony);
  - per-match coverage fits the within-tournament mixing.
- **Test.**
  - **(a) Key-free, now.**
    - Title fingerprint at scale: a month of cross-operator co-signing in Valorant, LoL, Dota and CS2 (and any other
      esports title Polymarket lists), with the fixed-lag criterion (IQR <= 40 ms, excess >= 5x).
    - Pre-game message types that LLF lists: CS2 "map picks", and draft picks in Dota / LoL.
      - Do the operator's and group P's pre-game Map-N re-pricings cluster at one moment per event (the veto's end)?
      - Do Dota / LoL subscribers act during the draft?
      - A CSTV / GOTV reader cannot see vetoes, so this splits LLF from a relay reader.
  - **(b) User-gated, decisive.**
    - Ask the user to obtain a PandaScore token. The agent may not create accounts.
    - With the free tier, read `low_latency_feed` on every development match (`pandascoreMatchId` is on every event).
      Pre-register the AUC of the flag against the operator-level label of P2 and against group-P presence, including
      the within-tournament mixed events.
    - With the real-time / Pro Live plan, pull historical `/csgo/games/{id}/events` and `/rounds` (ms `ts`) for the
      16-22 Oct maps. Lag-scan the operator's V-change decisions against `kill` / `round_end` `ts`; a peak with SD
      below 50 ms confirms the identity.
    - Then fit V = f(round score, alive counts, bomb, timer, side) directly. That separates R from K at once.
    - For a sealed lot, the examiner can fetch the same historical events point in time. That is the only route by
      which the price item becomes examinable on h1 / h2.
- **Data needed.**
  - (a): public calldata of Valorant / LoL / Dota markets and pre-game tapes (development).
  - (b): a PandaScore token from the user (free tier for the flag; a paid real-time plan for the events).
- **Signature if true.**
  - (a): tight fan-out in CS2 / LoL / Dota only; pre-game re-pricing clusters at veto or draft completion.
  - (b): flag AUC >= 0.95 at the operator level, with every traded match flagged; event-`ts` lock of the operator's
    re-pricings at a fixed lag.

### P4. LoL as the public-state twin, on 0xd2bb9459's 7,953 LoL trades of 16-22 Oct (strong form of X191; development data, Riot's state is public with timestamps)

- **Hypothesis.** The operator's LoL quoting is the same architecture as its CS2 quoting. In LoL the full game state is
  public with wall-clock timestamps (Riot livestats windows). So the message set and the value function can be fitted
  with every input observed. LLF's LoL list (kills, timer, draft, sides; the docs name no objectives) predicts a value
  that moves at kills and not at dragon, baron or tower changes beyond their kills. A fuller feed would move at the
  objectives too.
- **Why it fits.**
  - Critique 1: 0xd2bb9459 traded LoL heavily in 16-22 Oct, more than the September Worlds sample X191 planned to use.
  - Critique 3: LoL is in LLF and in the tight fan-out.
- **Test.**
  1. Decode 0xd2bb9459's LoL transactions of 16-22 Oct (`fetch_calldata.py`; about 2-3 k txs).
  2. Map its LoL events to Riot game ids. Use Leaguepedia `MatchScheduleGame` (`RiotPlatformGameId`), slowly (>= 60 s
     a query), or `Special:CargoExport` with the same pacing.
  3. Pull `feed.lolesports.com/livestats/v1/window/<id>` and `/details/<id>`. This is key-free and public; check first
     that past games are still served.
  4. Event study of its V-change decisions against kill, tower, dragon, baron and inhibitor changes, with shifted
     nulls. Condition the objectives on no kill within ±5 s.
  5. Fit V on (gold, kills, objectives, time), leaving one game out.
- **Data needed.** 0xd2bb9459's LoL calldata (publicnode), LoL tapes (data-api), Leaguepedia ids, Riot livestats. All
  before H.
- **Signature if true.**
  - Its re-pricings lock to kills at a fixed lag, with no extra lock at objectives (LLF-like), or with one (fuller
    state).
  - The leave-one-game-out fit beats the last print by >= 0.10 within one tick.
  - Its lead over Riot's frames gives the feed's position for LoL.

### P5. Dota: is the Dota half read from Valve's public spectator state? (strong form of X118 / X117 / X167; decides whether half the forward fills rest on a key-free public input)

- **Hypothesis.** The vendor's Dota messages sit at the spectator delay, at the same offset as Valve's public
  GetRealtimeStats snapshot (1044 s against 1035-1050 s; critique 3). Two readings follow:
  - the vendor polls Valve's webapi: messages lock to the arrival of new snapshots, which come every ~4.3 s;
  - it reads DotaTV at tick rate: messages come up to 4 s before the snapshot that shows the change.

  Either way the Dota input is public at the same delay. A Valve-state value function, plus the snapshot timing, could
  carry the Dota price item on the examiner's future blocks: the `tommy_dota_rt` recorder files sealed blocks for the
  examiner (its hard stop is 11-03 00:00).
- **Why it fits.**
  - The offsets match.
  - Valve's snapshots are recorded in development blocks.
  - The operator's siblings trade Dota heavily: 0x10d79cc7 3,647 Dota trades in 16-22 Oct, 0x7d67f01d on 11-01.
  - My 11-01 first look (37 takes) has no power either way.
- **Test.**
  1. On 11-01 06-12, decode every group-P / G subscriber's and every operator account's Dota orders in all Dota events
     of the block. First fix the recorder's match-to-event labels: it stamps 11 Valve games with one event; use the
     L-record team names.
  2. Measure each order's phase relative to the latest snapshot arrival, and its sign against the snapshot's kill and
     tower changes. Run a lag scan of -10..+10 s around the snapshot that first shows each change.
  3. Historically, use 0x10d79cc7's Dota of 16-22 Oct against OpenDota's parsed logs on the per-map D.
  4. Test the message set:
     - kills;
     - towers;
     - Roshan (with no kill within ±5 s);
     - barracks;
     - buybacks.
- **Data needed.** `tommy_dota_rt` (development blocks), the Dota calldata of the block, OpenDota (key-free), and the
  siblings' Dota activity. Extend the `tommy_dota_rt` and `sports` recorders' hard stops past 11-03, within the live
  lab rules, so future exam blocks carry them.
- **Signature if true.**
  - Polling reading: >= 60% of subscriber Dota takes in a <= 1.5-s window after the snapshot arrival that first shows
    the event (uniform would be about 35%), and none before it.
  - DotaTV reading: a peak 0-4 s before that snapshot.
  - LLF's Dota list predicts locks at kills and towers, none at isolated Roshan kills.

## Not worth budget now

- More bookmaker relays: hawk.live and SX already track the print, and E4 failed for three CIS bookmakers.
- PandaScore's status page as an outage experiment: no incidents since 2023.
- bo3 `created_at` as a clock: it is a batch insert.
- The 15-minute discovery window as a fingerprint: the wallet's pre-game orders start up to 3 h before.
