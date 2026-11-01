# Panel, iteration 10: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-10 with the late additions), state.json (ledger, catalog A1-X143, components,
target metrics), FINAL_RULE.md and the information panels of iterations 1-9. There are no EXAM or wall-audit files.
The current block (11-01 00-06) is sealed; I read no live recording and no Polymarket record of a sealed unit.

Small checks (scripts in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter10info/`):

- bo3.gg frontend bundle (Nuxt chunks, read as text) and its API, on finished development matches only (10-17, 10-19,
  10-21).
- Internet Archive CDX listing of `www.hltv.org/matches/*` for 10-15..10-23, and two archived match pages of
  development events (1win Private Club, 10-16 / 10-22 snapshots).
- SX Rollup's Blockscout explorer API (`explorerl2.sx.technology/api/v2`): stats, a name search, and one 40-block sample.
- The wallet's own order record (`orders.parquet`, before H): timing of its first maker orders relative to the scheduled
  game start.
- One request to Polymarket's public-profile endpoint for the wallet.

Sealed-data notes on these checks:

- The SX block sample (blocks 10,694,000-10,694,036) turned out to be stamped 10-23 11:16 UTC, inside h1. I printed only
  the `to` addresses and method selectors of those transactions (no market, odds, stake or outcome). The successor must
  clamp SX block ranges with `is_sealed` on block timestamps.
- One probe of a bookmaker-embedded match-tracker data endpoint (Sportradar's widget backend) used widget-style request
  headers. The permission system stopped the follow-up as access circumvention, and I did not pursue it. That source
  class needs the user's clearance and is not proposed below.

## Critique: what the investigation is missing or getting wrong

1. **The search has mapped Feed P's timing almost completely, but the target is blocked by content: the wallet's
   valuation.**
   - Price is at 0.32 within one tick against the 0.80 target, and outcome is at -0.13 against 0.5. Both need the
     number the wallet quotes from, not the moment it acts.
   - Every pending information test (X133 odds, X118 Valve, X38 / X87 chat, X47b round books, X91, X101) runs only on
     live development blocks. Those blocks are thin: 5 and 4 CS2 events on 11-01.
   - Apart from demos, which need consent, the plan has no historical CS2 content source. Yet the first two exam rounds
     are historical (h1 / h2).
   - Three key-free historical content sources were never used:
     - second venues that settle on chain (SX Rollup, which lists the same tier-3 events in play, and Azuro);
     - archived bookmaker lines (Internet Archive copies of HLTV match pages);
     - bo3.gg's per-player round fields. I checked these below: they are not a clock as they stand.

2. **X133's pre-registered design can give a false negative even if E4 is true.**
   - The live index is polled every 3 s, and nobody has measured how fast bo3 refreshes `bet_updates` there. The
     iteration-1 panel saw it unchanged over 3 polls in 40 s while the match was live, so the cadence may be bo3's own
     relay cadence, not Thunderpick's.
   - The tests use only one mapping: proportional de-margining of `(c1, c2)`. They omit:
     - the "lay" form, a bid on token A at 1 - 1/c_B. This is what a maker that copies a book's price for the other
       side would post;
     - a margin that depends on the price level (bookmakers' overround is not split proportionally at the extremes).
   - The verdict "SD(top - p_TP) <= 1.5c" mixes Thunderpick's margin with the wallet's. A shared upstream odds vendor
     would show up as a fixed lag between the two series and a level-dependent offset, not as a small raw SD.
   - The recorder takes only `status = current` matches, so it misses the pre-game line. Pre-game is the one window with
     no game state (see point 5).

3. **X138 reads the outcome item as "needs the +50-ms take timing". That holds for copying the wallet's two legs, but
   the target is a per-market correlation.**
   - An executable rule that earns a positive margin per unit of the same in-play activity can correlate with the wallet
     without copying a single take.
   - X82 bounds this from above: the activity pseudo-PnL already reaches 0.51 / 0.37 (Pearson / Spearman) on VALIDATE.
   - The public replays fail because they are adversely selected (pair cost about 1.00), not because they lack the
     takes.
   - The information that would protect a public maker exists and is public: the receivers' cancel wave on Polymarket's
     own book websocket, starting +14-51 ms after a Feed P message on the server clock, about 1 s before any delayed
     take executes. Its receive-time latency on this laptop has never been measured as a rule input. X70's executable
     replay on the recorded books (its steps 3-4) never ran.

4. **bo3.gg has a live in-round API, and it is not available for these matches. A negative check, so nobody re-probes
   it.**
   - The frontend bundle has two sockets, `wss://live.bo3.gg/` and `wss://updates.bo3.gg/`. Channel `ws/live_game`
     carries these events:
     - round start / end, freeze-time start / end, pauses;
     - bomb planted / defusing / defused;
     - economy info, aggregated game state;
     - `GAME_ROUNDS_TEAMS_WIN_PREDICTIONS`.
   - REST endpoints: `/live/matches/{id}/last_snapshot`, `/live/matches/{id}/game_state` and
     `/live/matches/{id}/games/{n}/rounds/{r}/win_predicts` (with a `based_on_event` field).
   - The source enum is `{BAYES: 1, GRID: 2, ABIOS: 3}`.
   - Coverage is absent:
     - In 71 finished CS2 matches of 10-17 and 10-19 (bo3 tiers s 2, a 2, b 32, c 35), `live_coverage` is false and
       `live_coverage_source` and `live_updates` are empty in every one. The investigation found the same for 201
       matches of 20-22 Oct.
     - `win_predicts` answers `[]` for finished matches. `last_snapshot` answers "Snapshot for the match not found".
   - So bo3 resells no Bayes / Abios / GRID live data for these tier-3 matches. That weakly argues against Feed P being
     a vendor bo3 already buys.
   - bo3's per-player round fields (`/games/{id}/rounds/{n}/players_stats`) were also checked:
     - The fields include `alive_time` (ns), `alive_periods_count`, `first_death`, `bomb_plant_attempts` and
       `economy_level`.
     - `alive_time` comes in 6-s steps with a per-round offset, and teammates often share a value. It does not fit the
       round's length: in game 189719 round 12 (CT win by elimination, round 89.7 s) all five T players show 15.08 s
       and the CTs 75.06 s.
     - So it is not a death clock unless someone first decodes its semantics. `round_map_data` is null.

5. **There is an unused window where E1 and E4 separate cleanly: pre-game.**
   - The wallet's first filled maker orders on the match market come a median 73 s after the scheduled start. 25% of
     them come before it (p10 -1,373 s, p25 -496 s; 80 match markets, before H).
   - Before the first round there is no game state. Any systematic gap between its level and Polymarket's own book must
     come from its own model (team ratings) or from an external line.
   - Nobody has compared its opening levels with a bookmaker line.

6. **A small fact for the outcome replays.** Polymarket's public profile lists the wallet at taker tier 6 ("Obsidian",
   weighted volume about $1.09M). If the validated engine charges the default taker fee on its FAK leg, the taker leg's
   PnL is slightly understated. This matters only for the E / F sets of X138.

## Proposals (ranked by the chance that they close the gap)

### 1. Thunderpick as the valuation, tested where it can discriminate: pre-game, quiet in-play orders, and the shared-vendor branch (strong form of X133 / X48 (a))

- **Hypothesis.** The wallet's quote level is an in-play odds product, either Thunderpick's own or that of the odds
  vendor upstream of Thunderpick and of Feed P. It is not the wallet's own model of raw events. Its bids are a fixed
  transform of that price minus a margin: proportional de-margin, the lay form 1 - 1/c_other, or a level-dependent
  margin. Feed P's event product reaches P4e first. The odds product is published tens of ms later, which would explain
  the wallet's +51 ms lag.
- **Why it fits.**
  - Its level is more informative than every subscriber-class maker (X135: 0.24 against <= 0.13), as a professional
    trading model's would be.
  - It re-prices all markets of an event coherently at the BO3 series sensitivity (finding 12), which is what an odds
    engine pricing the whole event does.
  - It re-prices on Feed P's messages without sharing a value with the other receivers (X139 ICC 0.28-0.43). That fits
    the wallet buying a different product (odds) than the event receivers.
  - Most of the price gap sits in quiet orders (71% of fills), where an odds product changes in steps and an
    event-only model has nothing new.
- **Test** (on every development block; pool all blocks before any verdict).
  1. Cadence first. For matched development units, poll bo3's per-match endpoint at 1 s alongside the 3-s index (still
     under 1 request/s). Report:
     - the distinct `bet_updates` states per in-play minute from each source;
     - the median gap between changes.

     If the index lags the per-match object, run (b)-(f) on the faster stream.
  2. Record pre-game. Add `status = upcoming` polls for development-start units from 60 min before the scheduled start.
     Compare the wallet's maker levels before the first round (its first quotes) with:
     - (i) round(p_TP - delta) and round(1 - 1/c_other - delta), with delta fitted on the first half of the pooled blocks;
     - (ii) Polymarket's own touch and last print.
  3. In-play, add both functional forms and a margin linear in |p - 0.5| to X133 (c) / (d), fitted on the first half.
  4. Event-time test. Among the wallet's quiet-class level changes (more than 5 s after any Feed P message), take the
     share that falls within one poll interval of a p_TP change. Compare it with 2,000 within-match shifts of the p_TP
     change times.
  5. Shared-vendor branch. Cross-correlate the wallet's level series with p_TP at lags of -10..+10 s. A sharp peak at a
     fixed lag, plus an offset that the level-dependent margin removes, means one upstream vendor. Then a lagged p_TP is
     a usable public proxy of the valuation for the quiet class, even if Thunderpick is not the wallet's direct input.
- **Data.** bo3.gg API (key-free, already in use; per-match `api.bo3.gg/api/v1/matches/<slug>`), the shared books, the
  block calldata, and `orders.parquet` for the pre-game timing. The direct bookmaker probes stay with X48 (b) and need
  consent.
- **Signature if true.**
  - Pre-game levels track the de-margined p_TP (or its lay form) within one tick on at least 60% of opening orders,
    against at most 40% for Polymarket's touch.
  - Quiet level changes coincide with p_TP changes at 3 times the null or more.
  - In-play within one tick reaches 0.6 or more on match markets.
- **Signature if false.**
  - Pre-game levels sit on Polymarket's book (the prior is Polymarket's price).
  - Quiet changes are at the null.
  - p_TP trails the market.

  Then E4 is closed for Thunderpick, and only a different book with the user's consent, or the vendor itself, can
  reopen it.

### 2. Second venues that settle on chain: SX Bet fills through the SX Rollup explorer, and Azuro bets on Polygon (strong form of X73 and X41; historical, key-free)

- **Hypothesis.** The same tier-3 CS2 events trade in play on SX Bet, whose market listing (`api.sx.bet/markets/active`,
  key-free, X23) already shows events the wallet trades, and possibly on Azuro. Their makers include Feed P receivers,
  possibly the same operator or the same odds vendor. Every fill carries odds and a timestamp on chain. This gives:
  - (a) a historical in-play price series for development and, for the examiner, h1 / h2: the only historical external
    price this investigation could have;
  - (b) a cross-venue test of E4. Does any SX maker's implied probability sit at the wallet's level?
  - (c) a cross-venue receiver hunt. Do SX makers or takers act at Feed P's message times?
- **Why it fits.**
  - X23 found SX lists the same in-play tier-3 events, but every odds or order endpoint of the API needs a key.
  - X73 stopped because the chain address was not found by web search. The chain is readable without any key:
    - SX Rollup's Blockscout API answers `GET explorerl2.sx.technology/api/v2/stats` with 200 (23.6M transactions, 74k
      today);
    - `/api/v2/search?q=Outcome` returns the verified `OutcomeReporter` contracts 0xC0e96f73... and 0xa21ac143...;
    - in one sampled block range the most frequent non-system target was 0x890482680C3a0116aBB003B17e7D694D13a6c1eB
      (method 0x468e5f52, unverified): a candidate exchange to verify against the docs.sx.bet contract list.
    - The Gelato RPC host did not resolve, so use the explorer's logs API.
  - Azuro (X41) failed on its subgraph's DNS and on one API path. Its contract addresses are published in its own
    toolkit package, which can be read as text, with no install and no execution. Logs then come through the Polygon
    RPC already in use.
- **Test.**
  1. Verify the SX exchange and its fill event against the explorer's verified ABI or the docs. Pull fill logs for
     blocks stamped 10-16..10-22, clamped below H with `is_sealed`.
  2. Decode the market hash, maker, taker, odds, stake and timestamp. Map market hashes to events through `markets/find`
     or `markets/active` (key-free per X23; check that it serves finished markets). Keep the CS2 matches the wallet
     traded or skipped.
  3. Measure:
     - the density of in-play fills per map;
     - the implied probability at each fill against the wallet's latest maker level, Polymarket's last print, and the
       touch (SD and within one tick);
     - the lead-lag of SX implied-probability changes against Polymarket prints and against P4e's message times;
     - for each SX address, its fill hazard in the 0-1 s after Feed P messages, against shifted messages.
  4. Azuro: list its CS2 games of 16-22 Oct first. Run steps 2-3 only if the wallet's leagues appear.
- **Data.** SX Rollup Blockscout API (key-free, verified), `api.sx.bet/markets/*` (key-free listing), Azuro toolkit
  source as text plus Polygon RPC, the wallet's calldata, and the decoded P4e messages.
- **Signature if true.**
  - At least one SX maker (or Azuro's quoted odds) sits within 1-1.5c of the wallet's level after a level-dependent
    margin, or leads Polymarket's print after messages.
  - Fills are dense enough (at least about 1 per in-play minute on the match market) to anchor quiet orders.
  - The SX price becomes a historical price input for the h1 / h2 rule, and any shared receiver is a second witness of
    the feed.
- **Signature if false.** SX / Azuro in-play fills are sparse, or their implied probabilities follow Polymarket's print
  with a lag. The second-venue class is then closed with a measurement, which also completes the wall account for E4 on
  the historical lots.

### 3. Polymarket's own book websocket as the public echo of Feed P: the input of an executable, protected maker for the outcome item (strong form of X70 steps 3-4 and X80; challenges the reading of X138)

- **Hypothesis.** A public maker, quoting a two-sided whole-cent ladder in the wallet's selected markets, can avoid most
  of the adverse selection that sinks the public replays (pair cost about 1.00):
  - it pulls when the receivers' cancel wave appears on the market websocket;
  - it re-posts at the post-wave touch.

  The 1-s in-play delay gives it about 0.8 s after the echo before any delayed take executes. Its realized per-market
  PnL then scales with each market's uninformed flow, as the wallet's locked pair margin does (margin vs PnL
  0.82 / 0.75). That can reach the outcome correlation without copying the take timing.
- **Why it fits.**
  - Critique 3.
  - X82: activity alone reaches 0.51 / 0.37.
  - The recorded books on the server clock show the consumed-side depth at 1.00 up to signing, then 0.66 at +0.1 s and
    0.13 at +1.0 s: most makers already escape inside the delay.
  - What has never been measured is how early a laptop client sees the first non-own cancel of the wave. That is the
    information input of this rule.
- **Test.**
  1. On BUILD-live, using P4e and member signing times from the block calldata as the message clock, measure:
     - the receive-time latency of the first non-own cancel or near-touch change on any book of the event after each
       message (local receive clock against the server clock; the offset is known);
     - the share of messages with an echo within 200 / 400 ms;
     - the false-alarm rate per minute of the same detector at shifted times.
  2. Freeze on BUILD-live:
     - a detector with a threshold on the number of non-own cancels within 50 ms;
     - a ladder (touch - k, the wallet's 100-share size, the [0.05, 0.95] band);
     - a pull on detection plus the 300-ms laptop latency;
     - a re-post at the post-wave touch after 1.5 s (X79's timer).
  3. Replay it with strict queue-position fills on the recorded books. Score on VALIDATE-live:
     - per-market realized PnL against the wallet's (Pearson and Spearman);
     - pair cost;
     - return.
- **Data.** Recorded books (shared `clob_wallets` and the own CS2 recorders) with server timestamps, block calldata, the
  X57 engine for fills. Development blocks only.
- **Signature if true.**
  - The echo is seen within 200 ms of at least 70% of messages.
  - Pair cost falls to 0.99 or below, and the rule is profitable.
  - Per-market correlation with the wallet is 0.5 or more on both coefficients.

  This item can then be examined on the future blocks, which have books. For h1 / h2 the investigation states the
  bound: no books.
- **Signature if false.** The echo arrives too late or too noisily (false alarms cost more than they save), or the
  correlation stays at X82's level. The outcome item is then speed-bound for every public input, which is a quantified
  wall item, and X138's conclusion stands for the right reason.

### 4. Internet Archive copies of HLTV and Liquipedia pages: archived bookmaker lines and data-partner fields (new route; clear it with the user first)

- **Hypothesis.** Two things the investigation could not fetch directly (HLTV and Liquipedia answer 403, X36 / X71) are
  available as dated public copies:
  - (a) the bookmakers' pre-match lines for the wallet's matches. That gives the prior test of proposal 1 for the
    historical record, and the list of books that price each match, which tells X48 (b) which books to probe;
  - (b) the tournaments' data-partner, broadcast and server fields, which name Feed P's vendor.
- **Why it fits.**
  - The CDX index lists 213 current-season HLTV match pages archived between 10-15 and 10-23. By team names, 38 of the
    wallet's 80 traded development events have at least one: DraculaN 12, 1win Private Club 6 (+2 "1win"), Stake Ranked
    4, PGL 4, Circuit X 4, Stake Pulse 3, NODWIN 2, CIS LAN 1.
  - A pre-match snapshot (match 2398990, captured 10-16 14:07 for a 10-19 match) holds the betting table: 32 odds cells
    and about 40 provider links, including Thunderpick, Stake, GG.bet and 1xBet.
  - A post-match snapshot (2398995) has no odds table, so only pre-match snapshots carry lines, and their age varies.
  - archive.org throttles: it answered 429 twice before serving the first page, after a 15-20-s backoff.
- **Test.**
  1. With the user's clearance, list the CDX snapshots for every traded and every skipped non-GRID event of 16-22 Oct.
     Fetch at most 1 page per 15 s, keep only the parsed fields (provider, two odds, snapshot time, match time), and
     drop the HTML.
  2. Score the wallet's opening match-market levels (first quotes before the first round) against:
     - the median line and each book's line, de-margined, keeping only snapshots under 24 h old;
     - Polymarket's last print at the same moment.
  3. From archived Liquipedia tournament pages of its leagues, tabulate the organiser and any data-partner, broadcast or
     server fields. Join them to group P's coverage (X102).
- **Data.** Internet Archive CDX and snapshots (key-free, public archive), `orders.parquet`, tapes.
- **Signature if true.**
  - Opening levels sit closer to a specific book or to the consensus than to Polymarket's print (within-one-tick gain
    of at least 0.15 on at least 30 events).
  - Or the archived pages name one data partner across the leagues group P covers and none across the leagues it
    misses.
- **Signature if false.** Opening levels follow Polymarket's book, and the pages name no common partner. The prior is
  then Polymarket's own price, and the vendor stays unnamed. Report the result as a measurement in the E4 account.

### 5. A free add-on to the X133 recorder: log bo3's live-coverage fields and subscribe to its live socket when one of the wallet's matches turns on (new; low prior)

- **Hypothesis.** bo3.gg resells Bayes, GRID or Abios live data (critique 4). If any of the wallet's matches gets
  bo3 live coverage on a development block, a key-free in-round CS2 clock appears: plant, defuse, round boundaries,
  economy and a per-event win prediction.
  - If the source is Abios or Bayes and its events precede P4e's messages by a fixed lag, that names Feed P's class.
  - If they trail by a fixed lag, the source is downstream of the same game feed.
- **Why it fits.**
  - The endpoints and the socket exist and are key-free.
  - Today none of 71 sampled development matches has coverage, so this is a watch item, not a plan.
- **Test.**
  1. In the X133 recorder's index loop, store `live_coverage`, `live_coverage_source` and `live_updates` per match.
  2. When a development-start match the wallet trades shows coverage, open `wss://live.bo3.gg/` (`ws/live_game`) for
     that match only, with unit-rule filing and the recorder's caps.
  3. Align its plant / round events with P4e's messages and with the wallet's re-pricings, using shifted-event nulls.
- **Data.** bo3.gg live index and socket, the block calldata.
- **Signature if true.** bo3 events and P4e messages coincide at a fixed lag with SD of 1 s or less. The CS2 in-round
  value can then be modelled from bo3's state for the future-block exams.
- **Signature if false.** Coverage never appears on the wallet's matches. That costs nothing and closes this source.

## Ranking note

- Proposal 1 is the one external valuation candidate whose data arrive now. It is ranked first because the
  pre-registered X133 tests can miss a true E4 (critique 2), and because pre-game is a window where no game-state
  explanation competes.
- Proposal 2 is the only key-free route to a historical external price for the same events, so the only one that could
  help h1 / h2. Its chain half is verified reachable.
- Proposal 3 attacks the outcome item with public information that already exists (the book's own echo of Feed P). It
  can be examined only on future blocks.
- Proposal 4 tests the prior and names the vendor from a public archive. It needs the user's clearance because the
  original sites block automated access.
- Proposal 5 costs nothing and is ranked last on its low prior.
- Nothing here needs sealed data. Proposals 1, 3 and 5 run on development blocks; proposals 2 and 4 run on 16-22 Oct.
