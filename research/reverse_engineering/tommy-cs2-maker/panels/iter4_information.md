# Panel, iteration 4: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations.

I read BRIEF.md, NOTES.md (iterations 1-4), state.json (ledger, catalog X1-X52, components), FINAL_RULE.md and every
file in panels/. No EXAM or wall-audit files exist.

I ran small checks on development data only:
- 16-22 Oct: `events_meta.parquet`, `events_sel.parquet`;
- the 10-31 14:50-18:00 UTC development block: `tommy_cs2_near` through `iter_live`, and `calldata_dev`;
- the source of the own recorders (`code/iter4/chat_recorder.py`, `round_recorder.py`).

I also made one web search and two GET probes of Sportradar's widget backend. The first probe returned
`{"code":403,"message":"Unauthorized feed"}`. The permission system blocked a second probe of a client-specific
widget path, and I did not pursue it. Any use of a licensed widget feed is the user's call.

Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter4info/`
(`sync_pulls.py`, `probe_sr.py`). Nothing sealed was opened, listed or counted.

## Critique: what the investigation is missing or getting wrong

1. **The exam will not see the new clocks.** Iteration 4 started two recorders, `tommy_chat` (X38) and
   `tommy_cs2_rounds` (X47b). Both idle in sealed blocks (`if sealed.is_sealed(now, KEY): return`). The round recorder
   also never subscribes to a unit that started in a sealed block.
   - `live.Writer` already files sealed-block records into `.cache/live/sealed/`, where the agent never reads them. The
     shared recorder works this way.
   - As written, the examiner of the future-block exam has no chat clock and no round-market books. No rule,
     diagnostic or feature built on them can ever be examined.
   - Fix: let both recorders run in every block. Choose channels and markets from listing-time fields only (Gamma
     `resolutionSource`, scheduled start), which the brief allows for sealed units. Check the same for
     `tommy_dota_live`.

2. **The binding gaps are price and outcome, and both need data that exists only on future blocks.**
   - On VALIDATE, selection already meets the selection branch of the target: AUC 0.954, recall 0.72 at lift 3.3, gain
     +0.062 with CI [0.019, 0.115]. The per-day replication (+0.034 on 10-21) and p = 0.002 against alpha 0.0025 are
     the weak points.
   - What fails is price (0.305 against 0.80) and outcome (-0.12 against 0.5). Iteration 4 showed that both need the
     live book: the best live anchor reaches 0.526, and the tape-and-calldata replay pays a pair cost of 1.005.
   - h1 and h2 have no books, so no public-data rule can pass price or outcome there. Every information decision should
     therefore aim at the future-block exam: record every input there (point 1), and make the rule read only inputs
     that are recorded in sealed blocks.
   - The planned pivot of presence to quote presence is fine, but it does not touch the binding gaps.

3. **X38 has no pre-registered number, and the two readings predict very different ones.**
   - Tournament rulebooks commonly mandate a stream delay: PolyLAN 43 makes 105 s mandatory, Red Bull Login requires at
     least 3 min, and the competitive server default is `tv_delay 90`.
   - V1 (a server-log or scorebot-grade feed, upstream of the broadcast): broadcast reactions should lag its takes by
     about the league's delay plus 2-6 s of platform latency, so 90-190 s, constant per organiser.
   - V2 (a feed built from the stream by scouts or CV): the lag is 2-10 s.
   - That is a separation of more than an order of magnitude. The investigation should write the prediction down,
     collect each traded league's stated delay from its rulebook before the data arrives, and accept the verdict.
   - It also does not need to wait for live data (proposal 1).

4. **The taker is the sparsest observation of the feed, and the investigation keeps using it as the only label.** The
   wallet makes about 13 takes an hour. But the feed also drives its maker ladder. My check (proposal 2) finds about
   12x more cross-market synchronous own pulls than chance, and 43 of 47 are not at a take.

5. **Polymarket's own listing names its data vendor, and the join is unused.** `eventMetadata.pandascoreMatchId` is
   set on 100% of the 1,324 CS2 events in `events_meta.parquet`. `gridSeriesId` is set on 42%.
   - The investigation asked for a PandaScore token as a generic source (next_steps).
   - It has not stated what the exact join enables: a per-match live-coverage flag (`live.supported`), detailed-stats
     and tier fields, and the identity of the slow non-GRID map scores in the sports socket.

6. **Smaller point.** The 10-16 "faster input" (X51) uses block time - 2 s as the decision time for every group. The
   taker-regime calldata (`calldata_taker`, 10-01..10-15) has signing ms. Rerun X51 on `sign_ms` before using
   "new feed on 10-16" to date the feed (proposal 5).

## Check: cross-market synchronous own pulls on the 10-31 development block

- **Data.** `tommy_cs2_near`, 14:50-18:00 UTC, the wallet's 8 dev-unit CS2 markets.
- **Detector.**
  - A cancel is a level decrease with no trade print on that market within 150 ms.
  - An own-size cancel is a cancel of exactly 100, 68, 58 or 54 shares. Own-size cancels within 5 ms are merged into
    one pull event. That gives 4,844 pull events, mostly the routine requote cycle.
  - A synchronous pull is a pull event on two or more markets of the same event (map and match) within 5 ms.
  - Only two events had two or more markets recorded: gls1-pcy (3 markets) and shin-isg (2).
- **Results.**

  | Measure | Value |
  | --- | --- |
  | Per-market hits within 5 ms | 94 |
  | Time-shift controls (±3, 7, 11, 20 s) | 2-14, mean 7.5 (about 12x fewer) |
  | Synchronous pull events | 47 |
  | Of these, within -5 / +60 ms of a wallet take | 4 (39 takes in the window) |

  Gaps between consecutive synchronous pulls within an event: p10 / p25 / p50 / p75 / p90 = 0.9 / 7.2 / 46 / 101 /
  200 s. 27% of the gaps are under 10 s.
- **Caveats.**
  - Only 17 of the 94 hits had no public change on any of the event's markets in the prior 300 ms (controls 0-3).
    300 ms is coarse, so "prompted" and "unprompted" pulls are not cleanly separated yet.
  - Some 100-share cancels may belong to other makers.
  - Two events only.
- **Reading.** A single internal signal fans out to the map and match ladders many times per map, mostly without a
  take: a candidate observation of the feed's event stream that is about 10x denser than the takes.

## Proposals (ranked by the chance that they close the gap)

### 1. Twitch VOD chat replay as a historical broadcast clock for 16-22 Oct, scored against a pre-registered delay prediction (strong form of X38; new data source)

- **Hypothesis.** Under V1, broadcast reactions lag the wallet's takes by the league's stream delay (90-190 s). Under V2
  the lag is 2-10 s. Chat replay of Twitch VODs gives the broadcast clock for the BUILD and VALIDATE takes now, without
  video and without waiting for live blocks.
- **Why it fits.**
  - 23 of the 77 traded non-GRID events of 16-22 Oct were Twitch-streamed (`resolutionSource`), 8 of them in VALIDATE:
    - stariy_bog: 9 (1win Private Club);
    - vanfantv: 7 (PGL qualifier co-streams);
    - MPKBK: 2 (CIS LAN);
    - one each for officialhyper, Trottah, floppyacs, roman and 0vpme084ngfu.
  - Kick chat replay is empty (iteration-2 panel), but Twitch keeps chat with its VODs.
  - Retention is 7 days for ordinary channels, 14 for affiliates, and 60 for partners. Affiliate VODs of 10-21/22
    expire around 11-04/05, so this window is closing now.
- **Test.**
  1. Pre-register (in NOTES, before any fetch):
     - collect the stated broadcast or GOTV delay of each traded league from its rulebook or Liquipedia page;
     - V1 predicts a chat-burst lag after its takes of about that delay plus 2-6 s, and V2 predicts 2-10 s.
  2. For each listed channel, find the VOD that covers the match and record its `recordedAt` and length.
  3. Fetch its chat replay. Keep only the offset in seconds, the message length and an emote flag: no text, no user
     names.
  4. Wall clock = `recordedAt` + offset. Calibrate the ingest latency on map starts and ends: the socket's map-score
     changes and bo3 `begin_at` are on the scale of minutes, enough to rule out a 90-s error.
  5. Cross-correlate the chat-rate bursts with:
     - the wallet's taker signings (`calldata_all`, ms);
     - the pack's clusters;
     - the public repricing jumps (tape).
     Use a ±600-s time-shift null and an event block bootstrap. Report the peak lag per channel and per organiser, and
     the same for the jumps (D_M).
  6. On the dev blocks, cross-check with the live `tommy_chat` recorder (tmi-sent-ts) on the same channels.
- **Data.**
  - Twitch VOD metadata and chat replay through Twitch's public web endpoint (gql.twitch.tv with the web player's
    public client id, no account). Clear this access route with the user first, as the investigation did for Kick's
    client key.
  - Volume is a few MB in all. 16-22 Oct only; the examiner can do the same for h1 and h2.
- **Signature if true.**
  - V1: a sharp chat peak at +90-190 s after its takes, stable per channel. The co-streams of one event (PGL: vanfantv,
    Trottah, officialhyper) differ by their own small re-stream lags. The market's own jumps (D_M) then sit near 0 and
    the chat near the delay. That means the pack and the wallet share a pre-broadcast source, and the losers are makers
    who price off the stream.
  - V2: the peak at +2-10 s, with D_M at about the same value.
  - Either way the "unobserved feed" becomes a named class of source. Under V1 it also says that a scorebot or
    server-log relay is what to look for (proposal 4).

### 2. The feed's event stream from the wallet's fan-out pulls: a label 10x denser than the takes, without consent (new)

- **Hypothesis.** The private feed drives the maker ladder at every event that changes the bot's valuation: kills,
  plants, round ends. The bot repriced the map and match ladders from one valuation (fan-out legs 1 ms apart; match
  premium = map premium x series sensitivity). So a pull on two markets of one event within 5 ms, with no public change
  just before, is an observation of a feed event, whether or not a take follows.
- **Why it fits.**
  - My check: 47 synchronous pulls in 3.2 h on two events, about 12x the time-shift control, and only 4 of them at its
    takes.
  - X46 found 829 own-size pulls without a take but tested only the FAK-return signature, not fan-out across markets.
  - The co-subscriber 0x51dbdd2b cancels within 9-13 ms of the wallet: a second recording of the same events.
- **Test.**
  1. Tighten the detector on every development block:
     - own pulls by size fingerprint plus remainders of its calldata orders;
     - "unprompted" = no public trade and no non-own level change on any market of the event in [s - 50, s - 5] ms;
     - add the event's round markets (`tommy_cs2_rounds`);
     - for each synchronous pull, attribute the other makers' cancels within ±15 ms (0x51dbdd2b by its sizes) and the
       public mid move at +1 s, +10 s and +60 s.
  2. **Clock-free granularity.** Per map, regress the count of unprompted synchronous pulls on the bo3 per-map counts
     of rounds, kills, plants and clutches. The pull count should track the event type the feed delivers:
     - kill-level: about 7-9 per round;
     - round-level: about 1 per round;
     - an odds or model feed: proportional to time, including freeze time and timeouts.
  3. **Refractory test.** CS2 has about 7 s of round-restart delay plus 15-20 s of freeze time after each round. A
     raw-event feed leaves a dead zone of about 22-27 s after a round-ending event (one with a large repricing). An
     odds feed keeps updating there, because buys and economy change the valuation.
  4. Use these events as the dense label for the chat lead-lag of proposal 1, and as the "pull" part of the
     quote-presence pivot.
- **Data.** `tommy_cs2_near`, `tommy_cs2_rounds`, `calldata_dev` and bo3 per-round team stats; all on disk or recorded.
  Needs maps where both the map and the match market were recorded from the game start.
- **Signature if true.**
  - Unprompted synchronous pulls run at 10x or more over controls.
  - Other fast makers cancel within 15 ms in a fixed share of them.
  - Their per-map count follows one event type (kills or plants) beyond round wins.
  - A dead zone of about 22 s follows round-end pulls.
  - Then the trigger's event type is named without any external clock. With proposal 1, the wallet's quote decisions
    can also be modelled as a function of feed events instead of fills.

### 3. Exact PandaScore join through `pandascoreMatchId`: per-match live coverage as the selection flag, and the vendor's round clock (strong form of the X23 / next-step PandaScore ask)

- **Hypothesis.** Polymarket lists esports from PandaScore. The vendor's per-match live coverage tells which events have
  a fast commercial feed, and therefore which have stale makers. The selection is "no GRID, no fast commercial feed,
  enough liquidity". The league rate and the falsified organiser-level data-rights flag are proxies for this.
- **Why it fits.**
  - `pandascoreMatchId` is set on 100% of the 1,324 events, so the join is exact.
  - The slow non-GRID map scores in the sports socket (60-110 s behind the market, iteration-3 panel) look like
    PandaScore's non-live tier.
  - The league-rate term cannot carry over to new leagues, and it is weak on 10-21.
- **Test.**
  1. Ask the user to create a free PandaScore account and supply the token. The agent must not create accounts.
  2. Fetch `/matches/{id}` for the 384 selection events of 16-22 Oct. Fields: `live.supported`, `live.opens_at`,
     `detailed_stats`, tier, `streams_list`.
  3. Freeze the flag as of listing time. If a field may have been changed after the fact, say so.
  4. Add the flag to the frozen event logistic. Report VALIDATE AUC, gain over activity + GRID [CI], recall, lift and
     per-day replication.
  5. If the plan exposes per-round or per-event timestamps for past games, use them as an event clock for 16-22 Oct.
     Compare round ends with the wallet's takes and with the repricing jumps; that is the X37 information without demo
     downloads.
- **Data.** PandaScore REST, about 400 calls, with the user's token.
- **Signature if true.**
  - Traded events concentrate where the vendor has no live feed (or only a slow one). Skipped non-GRID events (ESEA,
    Exort, CCT SA, Gamers Club) are where it has one.
  - The flag adds at least +0.02 AUC on both VALIDATE days and replaces the league rate.
  - If the vendor's round timestamps lag the wallet's takes by seconds and the market's jumps by little, PandaScore is
    the slow side of the race, and the wallet's source is upstream of it.

### 4. A server-log relay (HLTV scorebot class) as the named V1 source: a selection fingerprint the user can check in their own browser (strong form of X36)

- **Hypothesis.** The shared pushed source is a scorebot fed from the game server's log stream. HLTV is the canonical
  one for tier-3 CS2. Two subscribers (the wallet and 0x51dbdd2b) receive it within about 10 ms of each other, before
  the delayed broadcast. Where GRID official data exists, sportsbook-fed makers are as fast, so the edge disappears;
  that is the GRID boundary.
- **Why it fits.**
  - Push to several clients within 10 ms.
  - In-round, side-neutral events (T side 54%), including plants.
  - The GRID skip.
  - A valuation that scales with event size, which needs alive counts and economy, as a scorebot gives them.
  - X36 failed on access (Cloudflare 403), not on evidence. The investigation must not bypass that, but the user can
    open the pages as a normal visitor.
- **Test.**
  1. Selection fingerprint. The user opens the HLTV match pages of about 10 traded and 10 skipped non-GRID matches of
     16-22 Oct (the agent lists them) and notes whether each page shows a scorebot or live log.
  2. Score "scorebot present" as a selection flag against activity + GRID on those matches.
  3. Timing (only with the user's explicit consent): during one development block, the user keeps one live HLTV match
     page open with the browser's network log recording, and exports the websocket frame receive times as a HAR file.
     The agent aligns them with the wallet's signings on the server clock, using the CLOB-derived laptop offset.
- **Data.** User-side page views and one HAR export. No automated access to HLTV.
- **Signature if true.**
  - Scorebot coverage on traded leagues (DraculaN, 1win, Stake, Circuit X, PGL qualifiers) and none on ESEA, Exort,
    CCT and Gamers Club.
  - Scorebot kill or plant frames 0-50 ms before the wallet's signings in most takes, and before its synchronous pulls
    (proposal 2).
  - Then a normal user can see the input, and FINAL_RULE's "Can a normal user deploy it" changes.

### 5. Date the feed by the co-subscribers' history: common entry dates and latency change points (strong form of C4b with a second operator)

- **Hypothesis.** If one vendor's coverage or a new product is the input, every subscriber shows the same discontinuity:
  entry into the same leagues on the same dates, or a drop in requote latency on the same day. The 10-16 switch is
  then a feed event that a press release or changelog can name.
- **Why it fits.**
  - 0x51dbdd2b trades 69% of the wallet's events and all 3 of its Dota 2 events.
  - P4e was in the new leagues before 10-16.
  - X51 says the input got faster on 10-16, but on a block-time proxy (critique 6).
- **Test.**
  1. Activity of 0x51dbdd2b and P4e back to their first trades, before H.
  2. Per-league first-trade dates for the wallet, 0x51dbdd2b and P4e.
  3. For a sample of their maker orders (calldata), the delay from a public taker signing to their requote, per day.
  4. A change-point test on both series.
  5. Rerun X51 on the taker-regime `sign_ms`.
  6. Search vendor announcements (PandaScore, Oddin.gg, Bayes, Abios, GRID) and the leagues' data-partner notes within
     ±3 days of any common change point.
- **Data.** Public data-api activity and Polygon calldata, all before H.
- **Signature if true.**
  - A common change point within a day across the operators, matched by a public coverage or product announcement. That
    names the provider.
  - No common change, with 0x51dbdd2b already fast in these leagues before 10-16: the feed predates the switch, and the
    wallet bought into an existing source. Then the selection is that source's coverage intersected with liquidity.

## Sources (web search)

- [PolyLAN 43 CS2 rulebook (105-s mandatory stream delay)](https://storage.polylan.ch/public-files/reglements/p43/PolyLAN43_Reglement_CS2_EN.pdf)
- [Red Bull Login Jordan CS2 rulebook (minimum 3-min stream delay)](https://www.redbull.com/mea-en/events/red-bull-login-jordan/rule-book-cs2)
- [Supercraft: CS2 GOTV relay setup (tv_delay 90 as the competitive default)](https://supercraft.host/wiki/counter-strike-2/gotv-relay-setup)
- [DatHost: CS2 match API GOTV fixes](https://dathost.net/changelog/cs2-match-api-gotv-fixes)
