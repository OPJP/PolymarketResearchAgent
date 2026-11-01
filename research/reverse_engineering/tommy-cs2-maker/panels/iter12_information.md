# Panel, iteration 12: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations. The current ledger has E1b (own model on Feed P's raw events) leading by
elimination, E4 (a relayed in-play odds product) open, and E16 (own level pulled to the market) "partly consistent".

## What I read and what I ran

I read BRIEF.md; NOTES.md (iteration 12 in full, the iteration-8 Z8 section and the earlier sections by heading);
state.json (catalog A1-X171 with evidence, components, target metrics, live lab); the information panels of
iterations 1-11 (headings, and iteration 11 in full); FINAL_RULE.md by section. There are no EXAM or wall-audit files.
`tools/sealed.py tommy-cs2-maker`: no released lots, future examined up to 10-31 00:00; the current block 11-01 06-12 is
development.

Checks (scripts in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter12info/`:
`xevent_tick.py`, `xbook_tick.py`, `xbook_hist.py`, `xbook_pairs.py`, `xbook_dir.py`; the web probes ran inline). Each
one stayed under 300 MB and a few minutes.

- **On-chain, development only.** `ledger_rows_iter10.parquet` gives the wallet's filled maker orders with ledger
  classes, signed before H. I grouped them into 20,067 bursts by token within 50 ms. `orders.parquet` and
  `universe.parquet` give book types and outcome names.
- **Live, development only.** `own_bursts_dev.parquet` (BUILD-live, 10-31 12-18). Nothing in `.cache/live/sealed/` was
  opened and no recording was read.
- **Web, as a plain client with default headers (nothing bypassed).**
  - hawk.live home page. I parsed the page state for its schema, and printed the odds-provider list, the socket host
    and the slugs of three live series. Those three series are in Destiny League, Mad Dogs League and Ultras Dota Pro
    League, which are not in the Polymarket Dota universe. The upcoming list was parsed in memory for its schema only;
    no value was printed or stored.
  - hawk.live pages of two series. One is a Destiny League series, for schema and counts only. The other is the
    **10-22 PARI Universe Team Yandex vs GamerLegion series = development unit `dota2-ty-gl-2026-10-22`**: same
    scheduled start, 10-22 08:00 UTC, before H. A copy is in the scratch folder as `hawk_tygl_1022.json`.
  - One PARI Universe post on hawk.live, for its links only.
  - bo3.gg finished matches of 10-20 (development), for the `bet_updates` schema.
  - Status checks only:
    - betsapi.com and oddspedia.com: HTTP 403, Cloudflare challenge, not bypassed;
    - cybersport.ru, strafe.com, gosugamers.net and esportsbet.io: HTTP 200, no usable odds API found;
    - ws.hawk.live: plain HTTPS GET timed out (it is a socket host).

## Critique: what the investigation is missing or getting wrong

### 1. V is modelled per book, but the wallet re-prices the match book on the same loop tick as the map in play

Everything since iteration 9 treats V as one number per book and per burst: the ladder machine (X163), the proxies,
the loop attribution (X158), the take gap (X170). Nobody asked whether the wallet's books share one value. I checked
it on the record that already exists:

| Check | Result |
| --- | --- |
| Historical (16-22 Oct, filled record): quiet map-book bursts with a filled own match-book burst within +-5 ms | 1.92% (141 of 7,351) against 0.08% at the same loop phase (shifts of +-2..6 x 504 ms): **23.5x** |
| Match book to map book, same | 1.96% vs 0.09% (21.5x) |
| Map book to another map book of the same event | **0 of 7,196** |
| Quiet bursts against other events (cross-event) | 0.26% vs 0.18% (1.4x); follow class 1.9x |
| Same-tick map / match pairs where both levels changed: team-space direction agreement | 86.5% (n 104); \|dV_match\| / \|dV_map\| median 0.92 (IQR 0.33-1.62; censored, since dV spans fill gaps) |
| BUILD-live (uncensored own bursts; only 2 of 4 events had two recorded books) | untriggered 3.8% vs 0.29% (13x, n 342); triggered 5.1% vs 0.57% (9x) |
| BUILD-live cross-event, untriggered, +-15 ms | 0 of 341 (null 0.15%): no power |

So the quiet re-pricings are coupled between the map in play and the match book of the same event, in the same
team direction. They are not coupled to the other maps, and barely to other events. That is what one game-level value
mapped into two books by a series model predicts. It is also what two per-book filters predict if the two public books
move together.

- Nobody has separated these two readings. The series sensitivity s (the change in the match price per unit of map
  price) is the discriminator, and it is public (proposal 2).
- If V is one value per event, the price item has one unknown per event, not one per book. The match-book quote is
  then a function of the map-book quote and the public series state, a cross-book constraint the examiner can check.

### 2. "No public trace in the previous tick" is also the signature of a rounded slow filter of public prices

X158 attributed on-tick changes only to public changes in the previous tick interval (<= 504 ms), and only on the
match and map winner books. A filter of public prices with memory (an EMA with a half-life of seconds, rounded to the
cent with hysteresis) has three properties:

- it steps on ticks with no public change nearby;
- it moves in 1c steps (69% of on-tick changes are 1c);
- its step size rises with the gap to the market (finding 14: slope 0.43-0.53 per cent).

So the "85% private" reading of X158 has a public alternative that was never fitted. Two gaps make this worse:

- The handicap / totals / round books of the same event are recorded (`tommy_cs2_rounds`) but were in no attribution.
  BUILD-live holds only 24 minutes of them.
- Finding 14's adds-only sample cannot separate a pull to the market from composition.

The fix needs VALIDATE-live pulls and adds together (proposal 3).

### 3. The Dota half is half of the forward fills, and a historical multi-bookmaker in-play odds archive exists for it

CS2-only coverage of fills is 0.43-0.46 on the 10-31 12-18 development block. On forward lots the pooled price item
is decided by the 10-share Dota ladders about as much as by CS2. The Dota value is treated as an appendix (X167 step 1:
public per-minute state 0.17 within one tick, against the print's 0.42; X118 waits for live data). No iteration has
used a bookmaker source for Dota, although the wallet's Dota leagues are bookmaker-run (PARI Universe, 1win Streamers
League, BetBoom Streamers Battle).

**hawk.live archives exactly this** (verified on the development unit `dota2-ty-gl-2026-10-22`):

- **Per map, the in-play map-winner lines of three bookmakers.** Map 1 / map 2 update counts: BetBoom 141 / 77,
  SpinBetter 130 / 88, Parimatch 107 / 86.
  - Margins are 5-8%.
  - The median step is 2c after de-margining.
  - Each provider's sequence has 3-11 runs of null odds per map (suspensions).
- **Game states** every ~20 s of game time (score, net-worth advantage, building state).
- **Picks and stream links.** This series streamed on fissure_dota_en (Kick) and fissure_dota_ru (Twitch).
- **The update ids are one shared autoincrement across providers**, so the archive gives the order in which the
  bookmakers re-priced. It has no timestamps.
- **The site lists ten odds providers** (GGBET, EGB, Stake, BetBoom, Coinplay, Parimatch, Megapari, 1xBit, BC.GAME,
  SpinBetter) and runs a public Pusher-style socket (ws.hawk.live:8443) for live updates.

This is the first historical, examinable, multi-vendor in-play line for any of the wallet's markets (proposal 1).

### 4. The CS2 odds test rests on one bookmaker behind a 15-s CDN cache

- **Cadence.** bo3 serves its live index with `cache-control: public, max-age=15` (X144). A 15-s cached relay cannot
  test V to the cent at a 504-ms loop: in-play CS2 levels move several cents in 15 s around events. Tests (1)-(5) in
  `tp_valuation_tests.py` measure the cadence first. If the effective cadence is >= 10 s, only two tests are
  informative: the quiet-period level test and the suspension-clock test. Read test 1 that way rather than as a cent
  verdict.
- **Static fields.** bo3's `bet_updates` on finished matches hold the LAST in-play line plus `max_coeff` (verified on
  10-20 matches: e.g. coeff 1.001 / 12.0 with max_coeff 5.3). They are not a pre-match line or a path. So the
  historical CS2 side has no external value at all. That is why the Dota archive matters: it is the only place where E4
  can be tested historically and on the exam lots.

### 5. The withdrawals have a public antecedent that nobody has named

33 of 64 event-wide withdrawals start with a triggered pull, a median 17 ms after a public book change. 53 end with a
triggered add. Yet the notebook reads them as "its private event stream". Whose change, on which book, of what kind,
was never attributed. If one class of public change (a given co-receiver maker's cancel, a round-book re-price, a
sibling-book take) starts most of them, the withdrawal input is public and examinable. The next-step list names round
ends, pauses, Thunderpick suspensions and inventory, but not the trigger's identity (proposal 4).

## Proposals (ranked by the chance that they close the gap)

### 1. hawk.live's archived and live multi-bookmaker Dota lines as the Dota value (new source; E4 for the Dota half)

- **Hypothesis.** The wallet's Dota V, the top of its 10-share ladders, is one CIS bookmaker's in-play map price
  de-margined, minus a fixed offset. That is E4 on the half of the book where a vendor is visible. If it is false in the
  strong form, the wallet's Dota jumps precede every listed bookmaker. Then its Dota input is faster than ten
  bookmakers' trading desks, which puts E1b on a faster feed at the head of the Dota half.
- **Why it fits.**
  - The cent is not in public Dota state (X167: 0.17 within one tick).
  - Feed P's Dota messages ride the 900-s DotaTV delay (iteration-8 finding 24), the same delayed state that
    bookmakers without official data trade on.
  - Its Dota leagues are run by bookmakers whose lines hawk.live carries.
  - Its withdrawals look like suspensions (finding 7), and the archive carries each provider's suspension runs.
  - Dota is > 50% of fills on the forward development block.
- **Test.**
  0. **Data.** For every development Dota event the wallet traded, fetch the hawk.live series page once, as a normal
     visitor:
     - 10-22: ty-gl (found at `/dota-2/matches/pari-universe-group-stage/team-yandex-vs-gamerlegion`), ts8-legion1 and
       liquid-1win (slugs to be found the same way);
     - 10-31: ty-gl;
     - the VALIDATE-live maps.

     Parse `props.seriesPageData.matches[].oddsBundles` (provider, odds sequence, null = suspended), `states`, `picks`
     and `streams` into parquet under `.cache/re/tommy-cs2-maker/hawk/`. Sealed units' pages carry outcomes: leave them
     to the examiner, and put the fetch inside `evaluate()`.
  1. **Historical, clock-free (examinable on h1 / h2 Dota maps).**
     - De-margin each provider's sequence to p_A, choosing proportional, power or Shin on the BUILD maps.
     - Align the wallet's burst-top sequence in team space (band edges excluded) to each p_A sequence with the X171
       machinery: a monotone hidden index over updates, emission N(p_A,k + mu, sigma^2).
     - Report the residual SD and the within-1c share at the best path, against three controls:
       - (a) the last public print aligned the same way;
       - (b) the same provider's sequence from another map (placebo);
       - (c) the time-reversed sequence.
     - The shared update ids also say which bookmaker moves first at each jump. Test the leader first.
  2. **Live, with timestamps (development blocks with a traded Dota map).**
     - Poll the series page every 10 s through a `Writer`-based recorder with a hard stop (< 0.1 req/s) and record
       (receive time, odds id, values, null flags).
     - The site's socket would give sub-second updates. Its app key is embedded in every page for anonymous clients,
       but ask the user first, as was done for Kick chat.
     - Score three statistics:
       - the within-1c share of the wallet's quiet Dota adds against each provider's de-margined p at sign - 100 ms;
       - the lead-lag of provider changes against its off-loop jumps;
       - withdrawal starts inside a provider's null runs (window [-20, +2] s, 2,000 circular shifts).
- **Data needed.** hawk.live series pages (key-free, HTTP 200, ~135 KB each; one per series). The wallet's Dota orders
  (`orders.parquet`, `calldata_dev`) and the Dota tapes. `tommy_dota_rt` for the live clock.
- **Signature if true.** One provider's de-margined p is within 1c of its top on >= 50% of quiet Dota orders (the print
  gives 0.42). Its re-pricings precede the wallet's jumps by a stable relay lag. Its null runs contain the wallet's
  withdrawal starts at >= 3x the null (p < 0.0025).
  - If this holds, the Dota price item becomes computable on h1 / h2 from the archive, and E4 gets a named vendor
    class. The CS2 analogue is the same bookmakers' CS2 lines, which need X48 (b) consent.
  - If the wallet leads every provider by >= 2 s on its jumps, E4 is dead for Dota.

### 2. One game value per event: map-match same-tick coupling against the series sensitivity (new; Polymarket's own books)

- **Hypothesis.** On each loop pass the wallet computes one value for the map in play from game state. It writes it to
  the map book, and to the match book through a series model. The other maps are not re-priced.
- **Alternative (E16).** Per-book filters of each book's own public prices, coupled only because the public books move
  together.
- **Why it fits.** Critique 1:
  - map-match same-tick coupling at 21-23x the loop-phase null, historically;
  - zero map-to-map coupling;
  - 1.4x across events;
  - 86.5% team-direction agreement;
  - BUILD-live 13x (uncensored but small).
- **Test (VALIDATE-live, uncensored own adds and pulls on all recorded books of each event).**
  - For each on-tick change of the in-play map's own top, measure P(own change on the match book in the same tick).
    Model it as a function of the series sensitivity s = P(series | win map) - P(series | lose map).
  - s is point-in-time public: it comes from the series score, known from the previous maps' terminal prints, and the
    map and match markets' own prices before the tick.
  - Also report the magnitude ratio \|dV_match\| / (s \|dV_map\|).
  - Controls:
    - the same statistics on the other makers' mids;
    - the wallet's triggered changes;
    - shifted ticks;
    - a conditional logit that adds "public change on the match book in the previous tick" and checks whether it
      absorbs the s term.
  - Replicate historically on the filled record by restricting to pairs where both books filled. That gives the
    examinable form.
- **Data needed.** `tommy_cs2_near` (check that every traded event's match book is recorded). The shared recorder's
  sports feed, or Gamma map resolutions, for the series score. `calldata_dev` and the 16-22 Oct ledger for the
  historical form.
- **Signature if true (pre-register).**
  - The co-occurrence rises with s (slope one-sided p < 0.0025): >= 70% in a decider map, where match = map, against
    <= 20% at s < 0.3.
  - Direction agreement is >= 90%.
  - The median of \|dV_match\| - s \|dV_map\| is <= 0.5c.
  - The public-change term does not absorb s.
- **What each result means.** If the public-change term absorbs s, the coupling is common public motion (E16); go to
  proposal 3. Either way the question has a direct next step:
  - **Game-value branch.** One private number per event remains. The exact form of the mapping then separates an own
    model (an exact bo3 recursion with a map-3 prior) from a relayed product (a bookmaker's separately margined match
    line).
  - **Filter branch.** The quiet class is public.

### 3. A rounded slow filter of the event's public composite, including the handicap / totals books (strong form of E16)

- **Hypothesis.** The quiet component follows a rule of the form V_k = round_1c(V_{k-1} + step(EMA_h(C) - V_{k-1}))
  with hysteresis, evaluated on each 504-ms tick.
  - C is an event-level public composite: the map book's mid or microprice, the match book mapped back through s, and
    the same map's handicap / totals books.
  - h is a half-life of seconds to a minute.
- **Why it fits.** Critique 2:
  - 85% of on-tick changes have no public change in the previous tick, which a memoryful filter predicts;
  - the steps are 1c;
  - finding 14's slope of 0.43-0.53 per cent of gap;
  - the round books were never part of any attribution.
- **Test (VALIDATE-live, on-tick changes, adds and pulls).**
  - Fit a discrete-time hazard per (token, tick) for {+1c, -1c, none} on gap_h at h in {0.5, 2, 5, 15, 60 s}, for C
    computed (i) from the same book only and (ii) from the event composite with the round books.
  - Fit on the first VALIDATE-live block and score on the next.
  - Report:
    - sign accuracy;
    - timing AUC against within-token shuffles;
    - the within-1c share of the filter's V through the frozen X163 ladder machine, against the touch (0.45) and
      others' best + 1c (0.47-0.50).
  - For the historical form, rebuild C from prints (transactions with wallet orders excluded) and score it on 16-22
    Oct.
- **Data needed.** `tommy_cs2_near` and `tommy_cs2_rounds` on VALIDATE-live blocks; the X163 machine; the tapes.
- **Signature if true.** One h gives sign accuracy >= 85% and timing AUC >= 0.75, and the filter's V scores >= 0.6 per
  order through the machine. Then the quiet class (70% of filled orders) is public and examinable on h1 / h2 from
  prints. If false, together with proposal 2's game-value branch, the quiet steps are private game-state updates. In
  that case stop fitting public anchors and commit to game-state sources: demos (X122, consent), Valve (X118) and the
  bookmaker lines of proposal 1.

### 4. Name what starts and ends each event-wide withdrawal (strong form of X159 / X168)

- **Hypothesis.** The trigger is one of four:
  - (a) a public echo of a Feed P message: a co-receiver maker's cancel, a group-P take on a sibling or round book;
  - (b) a bookmaker suspension: Thunderpick a1 = a2 = 0 for CS2, hawk.live null runs for Dota;
  - (c) a round end from the round-handicap / totals books, which re-price at round ends;
  - (d) its own stale-feed guard.
- **Why it fits.** Critique 5:
  - starts are triggered pulls 17 ms after a public change;
  - ends are triggered adds (53 of 64);
  - other makers keep their depth (median 1.00);
  - a >= 2c public move follows within 20 s twice as often as it precedes.
- **Test.**
  - **Attribution (BUILD-live first, then VALIDATE-live).** For each episode, attribute the public change just before
    the start and just before the end by:
    - book (same, sibling map / match, round book);
    - side;
    - size;
    - price relative to the touch;
    - owner (size fingerprint; calldata link for filled orders; group-P or co-receiver membership).

    Compare with the same attribution at triggered pulls that did NOT start an event-wide withdrawal.
  - **Ends.** Measure the delay from the first public print >= 2c away from the pre-episode level to its return. A
    fixed delay after the public re-price means it "waits for the market to absorb the event".
  - **Suspension overlap.** Score Dota against hawk.live null runs (proposal 1, step 2) and CS2 against the
    pre-registered Thunderpick test.
- **Data needed.** `tommy_cs2_near`, `tommy_cs2_rounds`, `calldata_dev` (owners), `tommy_tp_odds2`, the hawk.live
  live recorder, `withdrawal_episodes.parquet`.
- **Signature if true.**
  - (a) One change class precedes >= 60% of starts against <= 20% of non-withdrawal triggered pulls: the withdrawal
    input is public, and the timing component becomes examinable.
  - (b) Suspension overlap >= 3x the null (p < 0.0025).
  - (c) Starts lock to round-book re-pricing.
  - (d) None of the above, and ends come at a fixed lag after the public re-price: its own guard.

## Ranking note and overlap

- **Proposal 1** is the only new external value source, and the only one with a historical arm that the h1 / h2
  examiner can run. It covers the half of the forward fills that the investigation has neglected.
- **Proposals 2 and 3** are complementary and cheap. Proposal 2 decides whether proposal 3 can work, and both run on
  books already recorded.
- **Proposal 4** extends X159 / X168 to the trigger's identity and adds the Dota suspension clock.

Not proposed, already in the ledger:

- Demos (X37 / X122), video (X4 / X22), HLTV (X64 / X147), PandaScore (X55) and direct bookmaker probes (X48 b) still
  need the user's consent. They stay the decisive CS2 game-state route if proposals 2 and 3 land on "private game
  value".
- No key-free CS2 multi-bookmaker line was found: betsapi and oddspedia return Cloudflare 403, and the others carry no
  odds API.
