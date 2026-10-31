# Panel, iteration 6: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-6), state.json (ledger, catalog A1-X86, components, live_lab), FINAL_RULE.md
and the earlier panel files (iterations 1-5). There are no EXAM or wall-audit files.

Small checks, development data only (scripts in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter6info/`):

- `sports_probe.py`: the shared `sports` feed of the 10-31 12-18 block, read hour by hour through `iter_live`. Only
  the gameIds of the 20 dev-start events were kept, filtered before anything was printed (PandaScore ids from Gamma by
  slug, dev units only). The hour-12 file raises the known zlib error; hours 13-17 read fine.
- `map_end.py` and `map_end_match.py`: map ends in 16-22 Oct (census bursts, windowed taker tapes, orders).
- `cosub_pregame.py`: whether 0x51dbdd2b ever trades before game start (cached activity, before H).
- `hop2.py`: second hop of the funding graph (Polygon USDC.e / USDC Transfer logs, 10-12..H). It was cut at its
  15-minute limit after the first address; the result for that address is complete.

Nothing sealed was opened, listed or counted.

## Critique: what the investigation is missing or getting wrong

1. **Polymarket's sports socket is a 20-s poll as recorded, not an event push.** Over 5,781 messages of the 20
   dev-start events (10 GRID, 10 non-GRID), each game is re-sent every 20.3 s (gaps p10 / p50 / p90 19.9 / 20.3 /
   20.7 s). All 360 score changes arrive exactly on that cycle: 0% come off-cycle, although the docs say messages
   come when a game changes. Two consequences follow.
   - X3's "in GRID events the market leads the socket by a median 23 s" is mostly the cycle: a mean wait of about
     10 s, plus the upstream lag.
   - The socket cannot serve as an event clock, even where it carries rounds. Map-score updates give map-end anchors
     only to within about 10 s.
   Every A5a-style latency number against the socket needs this caveat.

2. **The pre-registered X38 rule cannot separate the two most likely broadcast-side sources.**
   - The rule reads a chat peak at 60-300 s as V1 (upstream of the organiser's delay) and one at 0-20 s as V2
     (stream-derived).
   - A bot reading the CSTV/GOTV relay, or a vendor whose scouts watch GOTV, sits downstream of `tv_delay` but upstream
     of the stream's CDN. It also lands in 0-20 s.
   - Pooling channels with unknown and different delays (0 s at some LANs, 90-180 s online) also costs most of the
     power.
   - The pack's events are about four times more numerous than the wallet's. They are free calibrators, and the rule
     ignores them (proposal 1).

3. **The source serves more than one game, which removes most CS2-only source classes.**
   - The wallet trades CS2 and Dota 2 (PARI Universe) from the same client. Its Dota takes were in the server-clock
     "first trace" sample (64 CS2 + Dota orders).
   - Its co-timed maker 0x51dbdd2b trades CS2 (10,158 rows), Dota 2 (4,854), Valorant (464) and LoL (157)
     (`cosub_coverage.json`).
   - The HLTV scorebot (X36 / X64), CS2 server-log HTTP relays and CSTV relays (iteration-5 P2, X71) and a CS2-HUD
     vision system are all CS-only.
   - So either the operator runs a separate pipeline per game, or the input is a multi-game source: a B2B data vendor
     with scouts or official rights, or a generic broadcast pipeline. This should reorder the asks to the user, and
     proposal 4 tests it.

4. **"It does not see the pack's events" is right, but the pull test is not what shows it.**
   - At its own takes the pull comes +11-19 ms after the FAK signing, so it is part of the take routine. Nothing shows
     that the bot pulls protectively on an event it sees and declines.
   - The cleaner evidence is the absence itself. The wallet is 0.2-0.5 s faster than the pack on its own events. If
     its feed carried the pack's events, it would lead some of them, yet it is absent from about 80%.
   - My map-end check points the same way. At the most certain round-win events of all, map ends:
     - it leads 1 and is near on 1 of the 31 informed bursts on the map winner (absent 90%, against 82% for all
       bursts in those maps);
     - it takes the winner in the last 30 s of only 6 of 141 maps (random 32-s windows: 3.0 per 141);
     - at the 100 map ends with a mid-range match price, it makes 1 match-market take (random windows: 2.4);
     - its loser-side maker fills there are lower (4 maps against 14.8; 2.9 against 12.9 shares).
   - Its avoidance of prices of 0.8 and above confounds this. Still, it leaves near-riskless 8c edges at 0.92 to the
     pack. Either its feed is not first on round ends, or it caps prices. Either way, round ends are not its event
     class.

5. **Dead ends checked, so nobody redoes them.**
   - **Money trail.** The wallet's only external USDC counterparty in 10-12..H, 0x4cd00e38, is a hub contract.
     - It has 65,302 senders and $208.7M in, all forwarded to EOA 0xf70da978 (nonce 3.3M), the same hot wallet that
       sent the owner EOA its $2,000.
     - P4e, Pf1, 0xed446954, 0x5d40576b and 0x893575c7 also pay into it.
     - It is a mass on/off-ramp, so the USDC trail ends there and identifies neither a vendor nor an operator.
     - 0x51dbdd2b's payer 0x3a3bd7bb is a contract (probably a distributor); not followed.
   - **Co-subscriber as a pre-game selection proxy.** 0x51dbdd2b trades before game start in only 5 of 262 non-GRID
     events, so it cannot serve. Its first-10-minute presence is strongly associated with the wallet's selection
     (traded 61% / 88% against 12% / 28%, BUILD / VALIDATE), but that is in-play co-occurrence.

6. **The user asks are ordered by convenience, not by information.** One block of stream timing settles V1 / V2 for
   CS2:
   - a live Twitch or Kick HLS playlist (text only, `EXT-X-PROGRAM-DATE-TIME`) for two or three traded channels;
   - plus a few 160p segments around the wallet's takes.
   That is worth more than any of the other open asks. Demos (X37) come next: they are the only route to typed
   in-round events for h1 / h2 (BUILD / VALIDATE too). The PandaScore token (X55) and HLTV pages (X64) rank lower,
   and HLTV loses most of its prior after point 3. Ask in that order. Decide first what each answer implies:
   - **Broadcast-derived** (the market is downstream of the stream): the taker input is public. A low-resolution stream
     recorder in every block becomes the examiner's input, and the taker leg can be frozen as a rule.
   - **Upstream:** the input is private. The wall account is then "upstream of the broadcast by D s on X% of its events".

## Proposals (ranked by the chance that they close the gap)

### 1. Within-channel chat clock with two anchor classes and map-end calibration (strong form of X38; re-register before 11-01 06:00 data exist)

- **Hypothesis.** The informed traders in these markets read sources at different points of the broadcast chain:
  - the server, a venue scout or official data (upstream of `tv_delay`);
  - the CSTV/GOTV relay (at `tv_delay`);
  - the stream (`tv_delay` plus the CDN).
  The wallet's class (in-round turns) and the pack's (round wins) may sit at different points. The position of each
  class relative to one channel's chat is measurable even when that channel's delay is unknown.
- **Why it fits.** Critique 2. The wallet and the pack have different event classes and no shared lead (Y2). Map ends
  give typed, unambiguous round ends with a sharp market timestamp (the map market's terminal repricing).
- **Test.**
  1. Per channel c (the `tommy_chat` v2 channels of dev-start units), build event-triggered chat z-scores (the X38
     recipe, 1-s bins, lags -60..+400 s) around four anchor classes in that channel's event:
     - (a) map ends (the first print with the winner at 0.985 or more and no later print below 0.95);
     - (b) pack-only informed bursts (census recipe);
     - (c) wallet-led bursts with no other informed burst within 30 s after them (isolated, to avoid the following
       round end);
     - (d) random busy-phase times (retail FAKs).
  2. Estimate the peak lags L_a(c), L_b(c), L_c(c), with an anchor bootstrap.
  3. The statistic is Δ(c) = L_b(c) - L_c(c), pooled over channels by inverse variance. Report L_a(c) as the
     channel's market-to-chat delay.
  4. For events with two or more channels (official plus co-stream, Kick and Twitch), the difference in L_a between
     channels is their relative platform latency. A wallet watching channel j shows its smallest lead on j.
  5. Optional typed clock. Keep the text of messages from verified-bot accounts only (badge `bot`, or a fixed list of
     known bot names), never from human users. Some broadcasts post score or round lines automatically.
  6. Pre-register the decision table now, before any data:
     - L_a of 60 s or more and |Δ| of 15 s or less: both classes are upstream of the broadcast (V1 for the wallet's
       source).
     - L_a of 60 s or more and Δ of 45 s or more: the pack is upstream and the wallet is broadcast-side.
     - L_a of 20 s or less: the whole informed market runs on the broadcast clock. Point 4 then separates a relay
       reader from a stream reader.
     - Otherwise: inconclusive.
- **Data.** `tommy_chat` v2 (records in every block), `tommy_cs2_near` books, and each dev block's calldata (census
  recipe). No keys.
- **Signature if true.** A clean L_a(c) peak per channel; Δ(c) consistent across channels; the decision table says
  which link of the broadcast chain each source sits on. With Δ and L_a known, the wallet's lead over the broadcast
  becomes a number (seconds, share of events), which is what the wall account or a frozen broadcast rule needs.

### 2. Dota 2's public spectator feed, with Valve's known delay, as the one key-free in-game clock (strong form of X24 / X42)

- **Hypothesis.** The same client trades Dota 2. Valve's spectator data (OpenDota `/api/live`, with a `delay` field,
  typically 120-300 s) is the public in-game state, delayed by a known amount. Whether the informed traders in Dota
  markets lead it by about `delay`, or follow it, places their source upstream or downstream of the public spectator
  feed. Because the client and the timing profile are shared, this is the best available prior for CS2.
- **Why it fits.** Critique 3: one client, two games; 0x51dbdd2b trades 51 Dota events. X42 asked for 3-5-s polling,
  but that is not needed: the decision is "lead about `delay`" against "lead about 0", and 30-s polling already
  resolves 120-300 s. The current recorder runs only while PARI Universe is in play, and it has no overlap with a
  wallet take yet.
- **Test.**
  1. Widen `tommy_dota_live` to every Polymarket Dota 2 event in play, in every block, with records filed through
     `unit_writer` so the examiner gets them. Poll every 10-15 s while those events are live. That is about 300 calls
     an hour, inside OpenDota's free 60-per-minute limit.
  2. Labels:
     - every informed Dota burst (census recipe on Dota markets: pack, wallet and other fast takers);
     - the wallet's Dota takes;
     - 0x51dbdd2b's re-quotes after informed signings (matched-order record).
  3. Anchors: OpenDota kill-score and net-worth-lead changes, placed on server time with `t - delay`.
  4. Statistic: lead of each label class over the anchor, against `delay`, with an event bootstrap.
  5. Pre-register: a lead of `delay` ± 30 s means an undelayed source; a lead of 0 ± 30 s or a lag means a reader of
     the public spectator feed (recordable, so decodable).
- **Data.** OpenDota live (key-free, verified), the shared books of the wallet's Dota markets (server field `s`), and
  calldata of the Dota markets' taker transactions.
- **Signature if true.** The Dota takes of the wallet (and 0x51dbdd2b's re-quotes) sit about `delay` before the
  spectator feed's changes, which is the undelayed-source class. Or they sit right after them, and then the Dota leg's
  input is a public feed that a frozen rule can use; the CS2 analogue is the CSTV relay. Either answer moves CS2's
  prior sharply, and it needs no consent.

### 3. Polymarket's slow flow as the broadcast's footprint, by anchor class (strong form of X40; runs on 16-22 Oct today)

- **Hypothesis.** Retail and UI takers bet on what they see on the stream. The lag of their turn toward the team after
  an informed event is the broadcast's delay relative to that event's source. Differencing the lag between anchor
  classes in the same event cancels the unknown per-event broadcast delay.
- **Why it fits.** X40 looked only at the wallet's takes and asked for one fixed delay. Its own numbers do not fit
  plain price-chasing: retail turns at 72 s when the public jump comes within 10 s, and at 40 s when the jump comes
  more than 40 s later. Anchor classes and map ends were never used.
- **Test.**
  1. For each VALIDATE event, take retail net flow on the bought team in 4-s bins (addresses with 20 or fewer orders,
     X40 recipe) after each anchor class: map ends, pack-only bursts, and wallet-led bursts (isolated, as in
     proposal 1). Subtract time-shifted controls.
  2. Estimate each class's turn lag (first sustained positive cumulative flow) and the within-event difference
     Δ_e = turn(pack) - turn(wallet). Use an event bootstrap, BUILD for the method and VALIDATE for the number.
  3. Repeat on the dev blocks and compare with proposal 1's chat lags on the same events. Retail is a second, independent
     viewer clock.
- **Data.** On disk: windowed taker tapes, census bursts and the orders.
- **Signature if true.**
  - Retail turns at a similar lag after both classes: both sources sit at the same point of the chain.
  - Retail turns markedly later after pack anchors than after wallet anchors: the pack is upstream and the wallet is
    broadcast-side.
  - Map ends give the channel-free calibration (retail sees "GG" at broadcast time).
  - No turn at all: retail is a price-chaser, and this clock is ruled out with a measurement.

### 4. Name the source class from the games it serves (new; narrows the vendor and reorders the user asks)

- **Hypothesis.** The wallet's input, which it shares with 0x51dbdd2b, is a multi-game source: a B2B esports data
  vendor (scouts or rights), or one broadcast pipeline across games. It is not a CS2 log, relay or scorebot.
- **Why it fits.** Critique 3. The wallet trades CS2 and Dota 2 from one client. 0x51dbdd2b trades four games and
  reacts to the wallet's event class within about 10 ms.
- **Test.**
  1. Server-clock profile of the wallet's Dota takes on the shared books of its Dota markets (10-31 block and later):
     consumed-side depth flat up to signing, its own complement pull at +11-19 ms, the first public cancel after it. The
     same profile as in CS2 means one pipeline.
  2. 0x51dbdd2b's re-quote hazard in Valorant and LoL markets on 16-22 Oct (matched-order record, `cosub_hist.py`
     recipe): its complement re-quotes within 100 ms after informed takers' signings, against its baseline.
  3. If both hold, compare its game and league footprint with the public coverage statements of the multi-game vendors
     (PandaScore, Oddin.gg, Bayes, GRID, Abios), as a normal visitor.
- **Data.** Shared books, calldata of Valorant and LoL markets for 16-22 Oct (cached adapters, before H), and public
  vendor pages.
- **Signature if true.**
  - A sub-100-ms complement re-quote after informed signings in Valorant and LoL: a multi-game source. The CS2-only
    classes (X36 / X64 / X71) can then be closed with evidence, and the PandaScore token (X55) moves up the user list.
  - The re-quote absent outside CS2 and Dota: a per-game pipeline, which keeps the CS2-specific classes alive.

### 5. Polymarket's own live channels beyond the 20-s socket (new; cheap, low prior)

- **Hypothesis.** The socket the recorder uses re-sends each game every 20.3 s (critique 1). The site's live esports
  widget, or a per-game channel, may carry event-driven or richer state (PandaScore frames, round data) that a bot could
  read and the investigation has not recorded.
- **Why it fits.** Nothing public precedes the wallet. The one public sports channel examined is a 20-s poll whose
  observed behaviour contradicts its own documentation.
- **Test.**
  1. During a development block, open the page of one dev-start non-GRID CS2 event on polymarket.com as a normal
     visitor in the browser pane. Never open a sealed unit's page.
  2. List its network channels (`read_network_requests`: WebSocket URLs, message types, cadence), and record which
     fields change and when, on the server clock.
  3. Stop at any login or key.
  4. Also check whether the public socket's cycle depends on the connection: connect twice, offset by 10 s, for 5
     minutes, on dev units only.
- **Data.** A public web page and the public socket.
- **Signature if true.**
  - An event-driven channel with round or in-round state for non-GRID events. It would be the first public in-round
    source, and it could be recorded for the examiner with a `Writer`-based recorder.
  - Otherwise the socket's 20-s cycle is confirmed and the A5a branch closes for good.

## Sources (web search)

- [Polymarket docs: Sports WebSocket overview](https://docs.polymarket.com/developers/sports-websocket/overview)
- [Polymarket docs: WebSocket overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Polymarket docs: RTDS overview](https://docs.polymarket.com/developers/RTDS/RTDS-overview)
