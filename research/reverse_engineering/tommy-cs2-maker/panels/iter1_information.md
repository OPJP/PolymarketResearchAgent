# Panel, iteration 1: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained. I read BRIEF.md, NOTES.md,
state.json, FINAL_RULE.md, results/*.json and panels/iter1_mechanics.md. I ran small read-only checks on
development data only:
- the windowed taker tapes in `.cache/re/tommy-cs2-maker/tapes/` (16-22 Oct);
- Gamma listing fields (`eventMetadata`, `resolutionSource`) for the 384 CS2 events of 16-22 Oct;
- the live recorder through `iter_live`, 10-31 12:00-13:45 UTC (development block; only units starting at or
  after 12:00);
- endpoint probes of bo3.gg, Kick and HLTV.

Nothing sealed was read. The 11:00 Nemiga-FURIA match (a sealed unit) was excluded. Scripts are in my
scratchpad, `C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`
(`grid_check.py`, `pack_leagues.py`, `lag3.py`, `ws_cov.py`).

## Critique: what the investigation is missing or getting wrong

1. **The selection boundary is a data-feed boundary, and it is already in the listing.** Gamma
   `eventMetadata.gridSeriesId` (GRID's official-data series id) is set for 122 of the 384 CS2 events of
   16-22 Oct.
   - The wallet traded **0 of those 122 events** (0 of 356 markets).
   - It traded 77 of the 262 events without a GRID id (220 of 664 markets). Every one of its 220 markets is a
     non-GRID event.
   - In mixed leagues it skips the non-GRID events as well (CCT SA, ESL Challenger, EPL, United21), so the
     league still matters. But "never trades a GRID event" holds without exception, and it is a pre-game field.
2. **The whole informed pack shares its whitelist.** I measured taker USD in the windowed taker tapes for
   0x93078b5d, 0x4ebc2722, 0xfe8a28be, 0x2529c68d, 0x72aaaaf9 and 0x2005d16a:

   | Market group | Markets | Pack share of taker USD | Pack present in |
   | --- | --- | --- | --- |
   | Traded by the wallet | 220 | 15.3% | 98.6% |
   | Not traded, no GRID id | 444 | 10.0% | 13.1% |
   | GRID events | 356 | 0.03% ($3.4k of $10.9M) | 3.7% |

   - The pack is absent from big, liquid GRID events: CCT Europe ($1.48M of taker volume, 177 markets) and
     Thunderpick WC ($8.46M).
   - In the partly traded leagues (DraculaN, NODWIN, Stake Ranked, PGL, CIS LAN), the wallet traded **0 of 52
     events with no pack activity** and 49 of 65 events with pack activity.
   - So the selection is not this wallet's own preference. It is the coverage of an information source that
     several bots share, plus the absence of GRID. "Why these leagues" is the same question as "what is the
     feed".
3. **Polymarket's sports websocket is GRID-relayed, so it is useless for the wallet's events.** In the
   10-31 12:00-18:00 development block:
   - The socket carried round-level scores for the GRID events (CCT Europe bca-9ine, EPL invict1-don,
     Gamers Club nao-pain).
   - It carried only map scores (`000-000|...`) for the non-GRID events (CyberClash wraith-ntr, FiReSPORTS
     gls1-pcy, Battle of Baltics gg1-esprot).
   - Even where it has rounds, it is slow. On 21 rounds of those 3 GRID map markets, the market's sharpest
     3-s jump came a median **23 s before** the socket's round update (p10 -47, p25 -36, p75 -9.5, p90 +18 s).
     81.5% of rounds had completed half their move before the update.
   - So the plan to measure "the latency of its taker orders against the sports feed" cannot work. In its
     leagues there is no round feed to compare with, and where there is one, it lags the market. A different
     clock is needed.
4. **No time-stamped game state has been obtained, so the claim that it is "30 s early" has no reference.**
   - The cumulative bo3.gg clock aligned 13 of 109 maps.
   - The next-jump test measures the wallet against the market, not against the game. It cannot tell whether
     the wallet is early or the market is late (a delayed stream).
   - The mechanics panel shows the effect sits in jumps 10-20 s after the order, and that the pack signs within
     50-300 ms of each other (a pushed event).
   - The missing quantity is where the game event, the stream display, the pack's signing, the market jump and
     the socket fall on one time axis.
5. **The decisive data is public and fetchable on this laptop, and it has not been considered.**
   - Gamma `resolutionSource` is the event's stream channel: kick.com/draculancs(b/c/d), kick.com/stake_pulse,
     kick.com/starladder, kick.com/circuitx, kick.com/nodwin_cs2, twitch.tv/stariy_bog, and others.
   - Kick's API (`kick.com/api/v2/channels/<slug>` and `/videos`) answers 200 without auth. It returns VODs of
     16-22 Oct: draculancs 5, stake_pulse 7, circuitx 2.
   - The VOD media playlists carry `#EXT-X-PROGRAM-DATE-TIME` (ingest wall clock, ms) on every 12.5-s segment.
     Checked: 2,480 tags for 2,480 segments.
   - `ffmpeg` is installed (WinGet Links). That gives a historical, wall-clocked stream timeline for the
     wallet's own BUILD and VALIDATE matches.
6. **Smaller points.**
   - bo3.gg has no kill-level endpoint (kills, events and timeline all return 404). Its per-round team records
     do carry `first_kills`, `kills`, `death`, `bomb_plants`, `bomb_defuses`, `clutches`, `equipment_value`,
     `enemy_equipment_value`, `money_spent` and `alive_time`. Only the winner and the duration were used.
   - bo3 `bet_updates` is a static Thunderpick pre-match line: unchanged over 3 polls in 40 s while the match
     was in play. It is not an in-play odds feed.
   - The HLTV scorebot (scorebot-lb.hltv.org) answers 403 with a Cloudflare challenge.
7. **Tool bug, data loss.** `iter_live` stops with `zlib.error: invalid block type` in the 10-31 hour-12 files
   of `sports` and `subs` after 12:17:53 UTC: 544 and 4 records, then nothing.
   - This matches the recorder restart at about 12:18 UTC: process creation 05:18 local, which appended a new
     gzip member after an unterminated one.
   - 12:18-13:00 of this development block is unreadable unless `iter_live` resyncs at the next gzip header.
     That needs a fix in `tools/`.
   - This is a different failure from the "current hour" bug already listed.

## Proposals (ranked by the chance that they close the gap)

### 1. A stream clock from Kick VODs: put the game, the stream, the pack, the wallet and the market on one time axis

- **Hypothesis.** The market in non-GRID events is priced off the delayed broadcast. The wallet and the pack act
  on a source that is ahead of it. The candidates make different predictions:
  - (a) a server-side feed (scorebot or tournament data) ahead of the stream by the broadcast delay D: orders
    come before the stream shows the event;
  - (b) automated reading of a low-latency stream (CV on the HUD): orders come 0.5-3 s after the stream shows it;
  - (c) economy at freeze-end: orders cluster at the stream's round start.
- **Why it fits.**
  - Market jumps come 10-20 s after its orders, with no instant markout.
  - The pack signs within 50-300 ms of each other (mechanics panel).
  - In its events no official (GRID) feed exists for makers.
  - The event's stream channel is in the listing.
- **Test.**
  - For 10-20 BUILD and VALIDATE maps on Kick channels, pick the VOD whose PDT range covers the map: DraculaN
    (4 channels), Stake Pulse, Stake Ranked (kick.com/starladder), Circuit X, NODWIN.
  - Use `ffmpeg` on the lowest rendition to grab 2 frames per second of two crops: the HUD score and round
    timer, and the kill feed (top right).
  - Detect score changes (round ends) and kill-feed entries by numpy pixel differences. No OCR is needed.
    Calibrate the crop once per channel by saving one PNG and viewing it.
  - Each frame's wall time is segment PDT plus offset. Then compute five things:
    - (i) the lag from the stream's round end to the tape's >= 4c jump. A lag near 0 means the market is
      stream-driven.
    - (ii) the cross-correlogram of its 1,698 taker signing times, and of the pack's, against stream round
      ends, kill-feed events and freeze-ends, at lags of -60..+10 s.
    - (iii) the bought team against the team that wins the round shown next on the stream, and against the
      team that just scored a kill.
    - (iv) the same correlogram for its maker re-sign bursts.
    - (v) piecewise round alignment of bo3.gg rounds, which comes for free from the stream score changes.
  - Repeat (i) on CCT Europe VODs (kick.com/cct_cs*, GRID events) as the control.
- **Data.**
  - Kick VOD playlists (public).
  - About 70 MB per 40-min map at 160p, or about 1 GB for 15 maps. Stream it through ffmpeg into a numpy
    reduction, keep only event times, and keep each process far under 300 MB.
  - The calldata on disk, the tapes and the bo3 rounds.
  - Confirm with the user before pulling VOD segments if they count as a download under the session rules.
- **Signature if true.**
  - (a) Its and the pack's taker signings peak at a constant negative lag -D, for example -15..-30 s, before
    the stream's round end or kill event. D is constant per channel. The bought team equals the next
    stream-shown round winner at 80% or more when aligned.
  - (b) A sharp peak at +0.5..+3 s after kill-feed or score events on the stream.
  - (c) A peak at a fixed offset after the stream's freeze-end, and the side is the equipment-advantage team.
  - In GRID events the market's jump leads the stream's round end, so the market is not stream-delayed there.
    That is why nobody snipes them.

### 2. GRID as the boundary of the edge: the selection rule and the mechanism (pre-game, listing-level)

- **Hypothesis.**
  - In events with an official GRID feed, makers (and the GRID-relayed Polymarket socket) see the server state,
    so in-round quotes are not stale and the pack has nothing to take.
  - Without GRID, in-play quotes are set off the delayed broadcast, and the fastest unofficial source picks
    them off.
  - The wallet trades non-GRID events covered by its feed and never GRID events. Selection follows the
    information gap, not the league as such.
- **Why it fits.**
  - 0 of 122 GRID events traded, and the pack has 0.03% of taker USD in them.
  - Every one of the wallet's markets is in a non-GRID event.
  - The socket carries rounds only for GRID events (critique 3).
- **Test.** These run on the tapes already on disk, BUILD and VALIDATE separately.
  - (a) For all 1,020 CS2 markets, compare GRID and non-GRID events on two measures:
    - the share of each >= 4c round jump that is pre-empted by drift in the 30 s before it;
    - the next-jump-in-favour of all takers' in-play orders, by taker, against random times.
    The prediction: in non-GRID events there is a set of takers 15-30 s ahead, which is the pack; in GRID
    events there is none, or it is a different maker-side set.
  - (b) A frozen selection rule: no `gridSeriesId`, AND (league prior OR, for leagues never seen, the tier
    prior). Report its AUC, recall and lift against the activity baseline on VALIDATE.
  - (c) Check whether `gridSeriesId` is set at listing: compare `deployingTimestamp` and `createdAt` of
    development events, and confirm that the sealed listing projection carries it. If it is filled in later,
    it is not point-in-time.
- **Data.** Gamma events (cached, 384 events) and the windowed taker tapes. It is cheap.
- **Signature if true.**
  - Zero traded GRID events persists in every development day and in the examiner's lot.
  - Non-GRID events show stale in-round pricing: little drift before round jumps, and the informed pack has
    next-jump-in-favour of 0.65 or more.
  - GRID events show early repricing and no informed takers.
  - The rule predicts first-time leagues (new tournaments) correctly, which the league prior cannot. That is
    where a gain over the activity baseline could come from.

### 3. Identify the feed by its coverage fingerprint, event by event

- **Hypothesis.** The pack's source covers a specific set of non-GRID events, not whole leagues. That set
  identifies the source:
  - a stream-reading operation limited to certain channels;
  - a scorebot or parser with per-match live coverage;
  - a provider's live list (PandaScore, Bayes, Oddin, Abios).
  The wallet trades about 75% of the covered events (49 of 65) and none outside them (0 of 52).
- **Why it fits.**
  - Coverage within DraculaN varies by stream channel. Pack present / wallet traded: draculancs 58% / 50%,
    draculancsb 57% / 50%, draculancsc 82% / 64%, draculancsd 45% / 18%.
  - Outside the main channels the leagues are partly covered: NODWIN 30% / 26%, CIS LAN only on
    twitch.tv/mpkbk (40% / 20%).
  - It does not depend on how many events run at the same time: mean concurrent traded events 4.3 for traded
    events, 4.5 for skipped ones.
- **Test.**
  - For each non-GRID event, label coverage = any pack taker print in-play.
  - Model coverage on pre-game fields: channel (`resolutionSource`), platform (Kick or Twitch), league, tier,
    bo3 tier and parse status, start hour, team ranks.
  - Then check coverage against candidate sources:
    - bo3.gg `parsed_status` and demo availability;
    - whether the stream ran in low-latency mode;
    - whether the VOD exists;
    - for live dev blocks, bo3 `/api/v2/matches/live` `live_coverage`.
  - Also check whether the pack's misses within a covered league line up with stream outages or channel
    switches, using VOD gaps in the PDT sequence.
- **Data.** Tapes and listings on disk, Kick channel and VOD metadata, bo3.gg match metadata.
- **Signature if true.**
  - One observable (for example "stream on channel X with a VOD", or "bo3 live parse") separates covered from
    uncovered events with an AUC of 0.9 or more.
  - Channel-driven coverage means a stream-based source.
  - Coverage by match regardless of channel means a provider list.
  - Either gives a point-in-time selection feature that the market-activity baseline does not contain.

### 4. Live latency ladder with an own recorder from listing time (forward, for the exam), including the book-event trigger

- **Hypothesis.** The forward lots require the same chain live: stream, then pack and wallet, then book, then
  socket.
  - The shared `clob_wallets` feed subscribes only after a studied wallet trades: 3-min polling, then a
    200-ms throttle of the top 10 levels.
  - So it misses the first minutes and the sub-second book changes.
  - It also leaves the strong form of A7 open: does any public Polymarket book event (cancels or requotes by
    informed makers) come before its taker signings?
- **Why it fits.**
  - The pack fires within 0.5 s, which suggests a broadcast event.
  - The only Polymarket broadcast that is fast enough is the book (`price_change`). The socket is too slow
    (critique 3).
- **Test.**
  - A small recorder (`live.py` `Writer`, hard stop, < 100 MB RAM, < 300 MB disk) for CS2 events in development
    blocks. For example 11-01 06-12 and 18-24 UTC; list them with Gamma first.
  - Cover the non-GRID whitelisted leagues plus 2 GRID controls, subscribed from game start, with:
    - unthrottled `price_change` and `last_trade_price` for both tokens of all map and match markets;
    - the Kick live playlist PDT plus 2 fps HUD crops via `ffmpeg`, the same pipeline as proposal 1;
    - the sports socket.
  - After the block, decode the wallet's and the pack's calldata (signing ms) for those markets.
  - Then test:
    - (i) the lag from stream event to signing, live, to confirm proposal 1;
    - (ii) the rate of ask-side size drops without trades on the bought token in [-1, 0] s before its taker
      signings, against random times;
    - (iii) the reverse order: book changes that only follow the signing.
- **Data.** CLOB market websocket, Kick live HLS, sports socket, publicnode calldata. Record it in `state.json`
  `live_lab`.
- **Signature if true.**
  - (i) shows the same constant as proposal 1, so the rule can run forward.
  - If book events come first in 50% or more of its orders, against about 10% at random, the trigger is
    public Polymarket data and a public rule exists.
  - If book changes come only after its signing, the information is external, and the A7 branch is closed by
    measurement.

### 5. bo3.gg per-round team stats as labels for what it knows

- **Hypothesis.** Once rounds are aligned (proposal 1 gives exact alignment), bo3.gg's per-round team records
  tell which in-round fact the wallet acts on. The candidates:
  - the result of the round just ended;
  - the bomb plant (T side, `bomb_plants`);
  - the opening duel (`first_kills`);
  - the economy (`equipment_value` against `enemy_equipment_value`);
  - a clutch.
- **Why it fits.** These fields exist for every parsed game and have never been used.
  - The mechanics panel's "about one pack event per round" points to a round-level event.
  - The 64-67% hit rate is in the range of opening-kill and economy win rates.
- **Test.** For each aligned taker order, take the round in progress or just ended and compute the share of
  orders where the bought team is:
  - the team that won that round;
  - the team with the first kill;
  - the team with the equipment advantage;
  - the T side, in rounds with a plant.

  Compare with matched random times in the same rounds. Fetch bo3 rounds for all BUILD and VALIDATE maps,
  not only 20-22 Oct.
- **Data.** bo3.gg `/api/v1/games/<id>/rounds` (verified; per-team stats are in `game_round_team_clans`).
- **Signature if true.** One label reaches 85% or more where the others sit at their base rates. For example:
  - just-ended winner at 90% points to round-end sniping;
  - first-kill team at 85% with a peak 20-45 s into the round points to a kill feed;
  - equipment advantage with a peak just after freeze-end points to an economy model.

### 6. The 10-16 switch against the GRID and coverage boundary

- **Hypothesis.** The switch from taker to maker on 10-16/17 followed a change in where the edge was. Two
  candidates:
  - GRID ids (and GRID-fed makers) arrived in leagues it used to snipe;
  - the pack's feed started covering its maker-regime leagues.
- **Why it fits.**
  - Gamma market parameters did not change (C4b).
  - The selection now follows the GRID boundary exactly.
- **Test.**
  - Fetch the 1-15 Oct activity (the local cache holds only 15-22 Oct).
  - Join it to Gamma `eventMetadata.gridSeriesId` and league.
  - Measure pack presence by day and league in the same markets.
- **Data.** Data-api activity, Gamma events, data-api taker tapes for the 1-15 Oct markets.
- **Signature if true.**
  - In the taker regime it traded leagues or events that later carry GRID ids, or the pack was absent from its
    later leagues before 10-16.
  - The switch date coincides with the first GRID id or the first pack activity in those leagues.
