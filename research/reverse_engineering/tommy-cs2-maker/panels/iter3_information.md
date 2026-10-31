# Panel, iteration 3: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would separate the
leading explanations.

I read BRIEF.md, NOTES.md (iterations 1-3), state.json (ledger, catalog, components), FINAL_RULE.md and panels/iter1-2.
No EXAM or wall-audit files exist.

I ran small checks on development data only:
- 16-22 Oct: `calldata_all`, `calldata_pub`, `orders.parquet` and `events_sel`;
- the 10-31 12-18 UTC development block: `sports` through `iter_live`, `tommy_cs2_near` / `clob_wallets` trade records,
  and `calldata_dev`;
- bo3.gg API probes on matches of 10-20 and 10-21;
- two web searches.

Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter3info/`:
`retail_lag.py`, `mapend.py`, `mapend_hist.py`, `sports_cs2.py`, `bo3probe*.py` and `bo3head.py` (HEAD requests only).

**Sealed-data incident (report it in NOTES).** `sports_cs2.py` listed the map-score changes of every CS2 / Dota 2 gameId
in the sports socket from 13:00 UTC on 10-31, before I filtered by unit start. Its output included units that started in
the sealed 06-12 block:
- Nemiga-FURIA;
- Optibet-Fraternity;
- Betclic Apogee-9INE;
- Xipto-HellNight (Dota 2), whose start I could not confirm.

Nothing from them was stored or used. Every number below comes from the dev units in `dev_markets.parquet` only.

## Critique: what the investigation is missing or getting wrong

1. **"Upstream of every Polymarket feed" is not "upstream of the game broadcast".** Iteration 3 rejected U3 (stream
   reading) because the cancellers follow the wallet within 17-124 ms.
   - Tight offsets show that the operators share one pushed source. They do not show where that source sits relative to
     the broadcast.
   - A betting-data provider that builds its live feed from the stream (scouts or computer vision, the usual method for
     tier-3 events with no official data) pushes to all its clients within tens of ms, exactly like a server-log feed.
   - Only an event clock can separate the two: the in-game time of the kill, or the time the stream showed it.
   - No event clock has been obtained yet. Every catalog item that would give one is open (X4, X8, X22, X24) or blocked
     (X23, X36).
   - The strategy statement "an unobserved private feed upstream of every public trace" is therefore not yet a
     description of the input.

2. **The paradigm is stuck because the input data class is missing, not the model.**
   - Fill presence is bounded by co-occurrence: 0.872 against a 0.899 baseline.
   - The brief already allows the feature that would add information beyond activity: a play at its wall clock plus a
     delay of at least 5 s. Kills, plants and round ends with a reconstructed wall clock are the CS2 analogue of ESPN
     play-by-play.
   - Such data would also be the only way to examine the taker trigger on h1 and h2, which have no books.
   - The investigation treats "no live public source" as the end of the search. It has not looked for post-hoc,
     wall-clock-reconstructable sources. Demo files are one (proposal 1).

3. **New check A: Polymarket's own slow takers reveal a delayed public clock.**
   - Data: 16-22 Oct; 107k public taker orders from calldata; 1,698 wallet takes.
   - Measure: net same-team order count per 4-s bin after its taker orders, against a ±600 s time-shift control.

   | Taker class | Around its take | Later |
   | --- | --- | --- |
   | Retail (≤ 20 orders per address) | Net *against* its team: excess -22 at [-8, -4) s, -54 at [-4, 0), -49 at [0, 4), -33 at [4, 8) | Flips to its team from about +24 s: +19 / +17 / +33 / +38 at 24-44 s, +51 at 56-60 s, +53 at 80-84 s |
   | Mid (21-200) | Same contra dip (-82 at [0, 4)) | Flips at about +16-24 s |
   | Heavy (> 200) | +1,998 at [0, 4) s (the pack burst) | Nothing comparable |

   - So the broadly available information reflects its event only about 20-30 s later.
   - That fits either a broadcast delay or retail reacting to the round end. One round clock would separate them.
   - This is exploratory: one control, no bootstrap.

4. **New check B: the socket's non-GRID map scores trail the market by a minute or more.**
   - Dev units, server clock estimated with the t - s offset of the CLOB trade records:

   | Map | Market before the socket's map-score update |
   | --- | --- |
   | wraith-ntr, map 2 | 0.98 at -55 s |
   | gls1-pcy, map 2 | 0.99 at -25 s |
   | gls1-pcy, decider (match market) | 0.01-0.03 from -109 s |

   - Whatever supplies Polymarket's non-GRID scores (probably PandaScore's non-live tier) is far slower than the market.
     It is not the wallet's feed.
   - A crude historical version of the map-end test is too noisy to use. Lag from the last informed buy of the map winner
     to the first retail buy at ≥ 0.90: p25 / p50 / p75 = 20 / 75 / 250 s on 63 of 134 maps.

5. **New check C: bo3.gg has the demos, and the demo is a continuous clock.**
   - `api.bo3.gg/api/v1/games/<id>` returns:
     - `demo_url` (for example `demos/manually_uploaded/1792571140_joga-de-terno-vs-gremio-m2-ancient.dem`);
     - `demo_header` (filestamp `PBDEMS2`, a CS2 demo; frame_rate 128);
     - `duration` in ns, the full demo length including freeze time and pauses (2,649 s for a 24-round map);
     - `begin_at`.
   - The "no kills endpoint" result stands: `/replay`, `/kills`, `/round_events`, `/player_rounds`, `/timeline` and v2
     rounds all return 404, and `round_map_data` is null in every round of the 12 games I sampled.
   - But the round_align failure (pauses break a clock built from summed round durations) does not apply to the demo
     itself. In a demo, every kill, plant, defuse and round boundary sits on one tick clock, pauses included.
   - The download host is not verified:
     - a HEAD request to `bo3.gg/<demo_url>` returns the SPA HTML;
     - `files.bo3.gg` returns 404;
     - `cdn.`, `storage.` and `demos.bo3.gg` have no DNS.
   - The bo3 web app's "download demo" link will show the real host.

6. **New check D: the GRID boundary may be a special case of an official-data-rights boundary.**
   - Skipped non-GRID leagues of 16-22 Oct that have an exclusive live-data holder at organizer level:

   | League | Traded | Data-rights holder |
   | --- | --- | --- |
   | Exort Fiesta | 0 / 11 | Oddin.gg (official, multi-year deal) |
   | ESEA | 0 / 37 | ESL FACEIT Group, whose exclusive data partner is Bayes |
   | ESL Challenger | 0 / 6 | ESL FACEIT Group (Bayes) |
   | CCT South America | 0 / 8 | GRID-partner organizer, events without a series id |
   | Gamers Club | 0 / 7 | GRID-partner organizer, events without a series id |
   | European Pro League | 0 / 5 | GRID-partner organizer, events without a series id |
   | United21 | 0 / 4 | GRID-partner organizer, events without a series id |

   - Together that is 78 events.
   - The traded leagues (DraculaN, NODWIN, 1win, Stake, Circuit X, CyberClash, FiReSPORTS) have no official holder
     that I could find. PGL (9 of 13 traded) must be checked: an official holder there would falsify the idea.
   - The mechanism: where an official feed exists, sportsbook-fed makers get the event as fast as anyone, so no stale
     makers are left to pick off. That is the GRID story, generalized.

7. **Smaller points.**
   - Twitch IRC messages carry `tmi-sent-ts`, a server-side ms stamp. A chat clock would therefore not inherit the
     laptop's drifting clock.
   - The Dota 2 recorder polls every 30 s. That is too coarse to tell a stream delay of seconds from a spectator delay
     of minutes (proposal 6).

## Proposals (ranked by the chance that they close the gap)

### 1. Demo-tick event clock from the bo3-hosted CS2 demos (strong form of X8; an alternative to video for X4 / X22)

- **Hypothesis.** The taker fires on specific in-round events (opening kill, a 2-man advantage, a plant, a clutch
  duel), received with a fixed latency L_W. The slow market reprices on the broadcast at a fixed delay L_M. The demo
  gives the event times on one continuous clock per map, with a single unknown wall-clock offset.
- **Why it fits.**
  - In-round information that reverses in 20-23% of cases.
  - The opening-kill team wins 72% of rounds, against its 64-67% next-jump hit rate.
  - One internal signal per game event: fan-out legs 1 ms apart.
  - The round_align failure came from summed round durations, which lose pauses. The demo keeps them, because the
    game `duration` includes freeze time and pauses.
  - bo3 lists `demo_url` / `PBDEMS2` for parsed matches, which covers its leagues (bo3 parsed 40 of its matches).
- **Test.**
  1. For 20 BUILD and 20 VALIDATE maps with at least 10 wallet taker orders, download the demo and reduce it at once to
     an event table: tick, type, team, attacker and victim side, players alive. Keep only the table, about 50 KB per
     map.
  2. Per map, fit two offsets:
     - O_M, aligning round_end ticks to the market's round-end repricing (tape jumps);
     - O_W, aligning the wallet's taker signings to the nearest preceding event that favours the bought team.
     Use a grid search over ±300 s, with a permuted-event control (shuffle the inter-event gaps within the map).
  3. Report:
     - the residual spread of signings after events (IQR);
     - the share of takes within 0-1.5 s after an event of the bought team;
     - the event types it acts on and skips;
     - O_M - O_W per organizer;
     - the same measures for the pack's clusters and for the server-clock cancel waves on the dev-block maps that also
       have own-recorder books.
  4. Presence pivot: add the features "event favouring team s within the last 5-30 s", at the event's wall clock + 5 s
     (the brief's play-by-play rule), with O fixed per organizer on BUILD and never fitted on the scored map. Score
     fill and taker presence against the activity baseline.
- **Data.**
  - The bo3 API (verified). The demo files: host not verified; likely 50-300 MB each, about 2-6 GB in all, reduced and
    deleted at once.
  - This needs the user's explicit consent for the downloads (state the file names, source and size per file), and for
    installing a CS2 demo parser from PyPI (for example `demoparser2`).
  - The examiner can fetch the demos of h1 and h2 matches after the fact. They are the only taker-trigger data those
    lots can have.
- **Signature if true.**
  - Signings form a sharp peak (IQR < 1 s) after a small set of event types, with O_W stable across the maps of one
    organizer.
  - O_M - O_W of 5 s or more, constant per organizer: the feed is server-side or real-time, ahead of a delayed
    broadcast.
  - O_M ≈ O_W within 1-3 s: a stream-derived provider feed.
  - The kill-event features lift presence above the activity baseline by 0.05 or more, which the primary metric has
    never done.

### 2. Live chat clock on Twitch and Kick: a stream clock without video (new)

- **Hypothesis.** Chat bursts mark the moments the broadcast shows big plays: round ends, clutches, aces. Their lag
  after the wallet's takes measures how far its feed leads the stream.
- **Why it fits.**
  - Check A: retail flow flips to its team about 20-30 s after its take.
  - Gamma `resolutionSource` is the stream channel: Kick for 28 of 53 traded events, Twitch for 8 of 26.
  - Kick chat replay is empty (iteration-2 panel), so only live chat works.
  - It is text: kilobytes, not video, so it needs no download consent.
- **Test.**
  1. A Writer-based recorder with a hard stop, run during development blocks for every CS2 event in play with a
     Twitch or Kick channel.
  2. Twitch: anonymous IRC (`irc.chat.twitch.tv`, nick `justinfanNNNN`, no credentials). Keep `tmi-sent-ts` (server
     ms), the message length and an emote or keyword flag.
  3. Kick: the public chat websocket of the channel's chatroom. Its client identifier is embedded in Kick's web page;
     ask the user if in doubt.
  4. On the server clock, compute the cross-correlogram of the chat rate (and its bursts) with:
     - the wallet's taker signings;
     - the pack's signings;
     - the CLOB cancel waves;
     - the repricing jumps.
     Use a time-shift null.
  5. Per channel, estimate D = peak lag after its takes, and D_M = peak lag after the market's round-end jumps.
- **Data.** Live development blocks only. Tiny volume.
- **Signature if true.**
  - A constant D of 5 s or more per channel (for example 20-40 s): its feed is upstream of the broadcast. Combined
    with proposal 1, that means a server-log or scorebot-grade source.
  - D ≈ 1-3 s: its provider reads the stream.
  - D varying by organizer could also explain which leagues are worth trading: the longer the delay, the more stale the
    stream-priced makers.

### 3. Official-data-rights map as the selection boundary (strong form of X5 / R8)

- **Hypothesis.** The wallet trades CS2 events whose organizer has no exclusive official live-data holder. Where GRID,
  Bayes (ESL FACEIT Group), Oddin.gg (Exort) or another official provider exists, sportsbook makers get the events as
  fast as anyone, so nothing is left to snipe. The per-event gridSeriesId is a partial, late proxy for this.
- **Why it fits.**
  - Check D: 78 skipped non-GRID events sit in leagues with an official holder.
  - The pack is absent from all of them.
  - The gridSeriesId is attached only 1-1.3 h before the start, while rights deals are public months ahead.
  - The league-rate term cannot carry over to new leagues, and it makes the 10-21 half weak.
- **Test.**
  1. Build an organizer → official-data-holder table as of 10-16 from public press releases, the providers' newsrooms
     and Liquipedia. Freeze it before scoring.
  2. Use the flag "official holder (any provider)" in place of, or alongside, the GRID zeroing in the frozen event
     logistic, fitted on BUILD.
  3. Report VALIDATE AUC, gain over activity [CI], recall and lift, per day (the replication rule), and on new
     leagues.
  4. Falsification: any traded league with an official holder (check PGL first).
- **Data.** Web pages: press releases, Liquipedia tournament pages. No keys.
- **Signature if true.**
  - Every traded event has no official holder.
  - The flag adds at least +0.02 AUC over activity + GRID on both VALIDATE days.
  - It replaces the league rate, so the rule carries over to leagues not seen in BUILD (CyberClash, FiReSPORTS)
    without a learned prior.

### 4. Polymarket's slow takers as a historical broadcast clock (new; no new data)

- **Hypothesis.** UI-placed orders (people watching the stream) react to the wallet's event at the stream delay. So the
  lag of their same-team turn, measured per organizer on 16-22 Oct, is the delay of the broadcast relative to its feed.
- **Why it fits.** Check A: retail flow is contra its team in [-8, +12) s and turns to its team from about +24 s;
  mid-size takers turn at +16-24 s.
- **Test.**
  1. Classify UI orders by fingerprint: FOK market orders with whole-dollar notional, sig_type 1 or 2, a slow
     sign-to-match of about 2 s, and few orders per address.
  2. For each wallet take, the net UI flow per 1-s bin out to 120 s, with a block bootstrap over events. Estimate the
     turn time per organizer and per channel.
  3. Separate "reacting to the kill" from "reacting to the round end". Condition on takes whose next public repricing
     jump comes within 10 s (the take is near the round end), against takes whose jump comes more than 40 s later.
  4. Cross-check against D from proposal 2 on the dev blocks.
- **Data.** `calldata_pub` and `calldata_all` (on disk).
- **Signature if true.**
  - A turn lag that is constant per organizer and does not depend on the time to the next jump: a broadcast delay.
  - If it tracks the time to the next jump instead, the public reacts to round ends, and the delay must come from
    proposal 1 or 2.

### 5. Second venues that settle on-chain: Azuro (Polygon) and SX Network fills (strong form of A4b / X23)

- **Hypothesis.** Bookmaker-grade venues that price tier-3 CS2 in play take their data from a provider that may be the
  pack's. Their live coverage lists and in-play prices are public on-chain, even where their APIs need keys.
- **Why it fits.**
  - SX Bet lists in-play CS2 markets of the same tier-3 events (FiReSPORTS ShindeN v Isurus), but its odds API needs a
    key.
  - Azuro's subgraph hosts did not resolve, but its live bets settle on Polygon, which the RE already queries.
- **Test.**
  1. From the venues' docs, take the contract addresses: Azuro LiveCore / core contracts on Polygon, and SX Rollup
     exchange contracts with a public RPC or explorer.
  2. Pull the fills (or bet-acceptance events) of dev-unit CS2 matches: block time, odds, outcome.
  3. Measure:
     - lead-lag against the Polymarket server-clock cancel waves and the wallet's takes;
     - the venue's set of live-offered matches as a selection feature against activity.
- **Data.** eth_getLogs on Polygon (publicnode) and the SX chain RPC. No keys.
- **Signature if true.**
  - The venue's in-play odds or acceptances jump within about 2 s of the wallet's takes, at block resolution, and
    before the Polymarket repricing jumps.
  - Its live coverage matches the wallet's events beyond activity + GRID, which would name the provider tier.
- Priority is low: fills are sparse, block resolution is about 2 s, and both venues apply their own bet delays.

### 6. Dota 2 natural experiment at the right resolution (strong form of X24)

- **Hypothesis.** The operator's Dota 2 takes come either before OpenDota's live game state by about the spectator
  delay (real-time server access) or after it (stream or feed).
- **Why it fits.**
  - The `tommy_dota_live` recorder exists, but it polls every 30 s. That cannot separate a lag of seconds from a delay
    of minutes.
  - The retrospective variant failed on game-time-to-wall-time mapping. The live variant avoids that.
- **Test.**
  1. Poll `/api/live` every 3-5 s, only while a dev-unit Dota 2 event is in play (about 140 KB per poll, so keep only
     the matched games).
  2. Record `delay`, `last_update_time`, `game_time`, the scores and `radiant_lead`.
  3. Event-study the wallet's Dota taker signings (server clock) against kill-score changes, shifted by `delay`.
- **Data.** OpenDota live (no key). Modify the RE's own recorder.
- **Signature if true.**
  - Its takes lead the delayed feed's kill changes by about `delay`, with a tight spread: real-time server-side
    information.
  - Takes that lag the feed: a stream or slower feed.
  - Either way, it says what class of data the operator buys, and that class likely carries over to its CS2 events.

## Sources (web searches)

- [Oddin.gg secures multi-year data partnership with Exort (Gambling Insider)](https://www.gamblinginsider.com/news/29018/oddin-gg-secures-multi-year-data-partnership-with-exort)
- [Oddin.gg and Exort announce multi-year data partnership (iGaming Business)](https://igamingbusiness.com/company-news/oddin-gg-and-exort-announce-multiyear-data-partnership-for-exort-series-counter-strike-2-events)
- [Bayes Esports becomes exclusive data partner of ESL FACEIT (iGaming Business)](https://igamingbusiness.com/esports/esports-betting/bayes-esports-becomes-exclusive-data-partner-of-esl-faceit/)
- [ESL FACEIT retains Bayes Esports as exclusive match data provider (SportBusiness)](https://www.sportbusiness.com/news/esl-faceit-retains-bayes-esports-as-exclusive-match-data-provider/)
