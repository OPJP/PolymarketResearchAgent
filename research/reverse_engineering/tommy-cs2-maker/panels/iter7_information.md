# Panel, iteration 7: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-7), state.json (ledger, catalog A1-X100, components), FINAL_RULE.md and the
panel files of iterations 1-6. There are no EXAM or wall-audit files.

Small checks, development data only (16-22 Oct before H, and the already-seen BUILD-live block 10-31 12-18). Scripts
are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter7info/`:

- `phase_clock.py`, `phase_clock2.py`, `phase_clock3.py`: is the signing time of each subscriber's take clusters
  quantized to a fixed period within an event (stream segments, CSTV+ fragments, pollers)? Inputs:
  `pack_orders.parquet`, clusters with a 500-ms gap.
- `limit_agree.py`: do the feed's subscribers share a target price on the same token (limits from the calldata)?
- `wave_split.py`: do other makers cancel after the wallet's own pulls, at its takes and at its untriggered pulls?
  Does that explain the X94 markout? Inputs: `level_events_dev`, `own_bursts(_markouts)_dev`, `calldata_dev`.
- `outage.py`: does the wallet keep taking when all six subscribers go silent in busy minutes?
- Web searches as a normal visitor: official data partners of its leagues.

Nothing sealed was opened, listed or counted. The live recorder was not touched.

## Critique: what the investigation is missing or getting wrong

1. **The book publishes the wallet's private events within 10-150 ms, and that contaminates the Z4 evidence.**
   Data: BUILD-live, 7 books, 4 events (`wave_split.py`). I counted non-own cancels on the event's books in a window
   after each own pull, against a ±20-120 s shift null. Untriggered means no non-own event on any book of the
   event in the 300 ms before the pull.

   | Anchor | n | (+5, +60] ms | (+60, +150] ms | Share with >= 1 in (+5, +60] |
   | --- | --- | --- | --- | --- |
   | Own pull at its takes | 31 | 3.81 (null 0.33) | 7.61 (0.42) | 0.65 |
   | Untriggered ladder pulls (>= 2 levels) | 74 | 2.18 (0.24) | 3.91 (0.34) | 0.58 |
   | Untriggered single pulls | 136 | about 0.5 in (+5, +150] | | |
   | Triggered pulls | 1,064 | 3.35 (0.40) | 5.13 (0.64) | 0.75 |

   - After an untriggered ladder pull there is nothing for the first 10 ms. The response then ramps up and peaks
     at 40-120 ms.
   - The response stays on the same book: 5.28 cancels there against 0.81 on the event's sibling books.
   - An event-level feed would hit the map and match books together, as the wallet's own fan-out does. This
     pattern instead looks like makers who read its pulls on the public book and follow them.
   - **Consequence for X94.** The others' mid falls partly because the others follow its pull. Split by follower
     cancels on the same book in (+5, +150] ms, the 10-s markout of its untriggered pulls is:
     - none, n 87: -0.49c (moves <= -1c 25%, >= +1c 18%);
     - 1-2 followers, n 61: -0.58c;
     - 3 or more followers, n 62: -0.80c (2-s markout -0.48c against -0.17c with none).
   - So Z4 survives, but it is weaker than reported. The pre-registered VALIDATE-live test (c) will pass in part
     because of the followers.
   - Report a markout on public trade prints, and the no-follower stratum, next to the frozen test. Do not change
     the test.

2. **The official-data-rights falsifier was run in one direction only.** X39 tested "a rights holder blocks the
   feed" and rejected it, because PGL (Oddin.gg official) was traded 9 of 13. The reverse reading, "the feed is that
   holder's official feed", was never tested. It fails on the same table:
   - Exort Fiesta (Oddin.gg exclusive): 0 of 11.
   - ESEA (ESL FACEIT, Bayes exclusive, never GRID-flagged): 0 of 37.
   - Untraded tier-5 non-GRID leagues with other or no holders: GLuck Yungstar 0 / 10, VOID 0 / 7, Gamers Club 0 / 7,
     Dust2.dk 0 / 6.

   So no single rights holder is the boundary. Tier does most of the work, and P4e shows the same boundary (X15).
   That fits a vendor that sells live in-round data tiered by tournament. Polymarket's `leagueTier` probably comes
   from its own data provider, whose ids it stores (`pandascoreMatchId` on 100% of events). Proposal 2.

3. **"Multi-title source" is weaker than stated.** One subscriber order in CS2, Dota 2 and LoL (0xf1ee4842 about
   50 ms ahead of the 0x8a80528d / 0xddb6e624 pair) is also what you get with a different vendor per title. It is
   enough that every vendor delivers from the same region and each operator's servers and code sit at fixed
   distances from it. A fixed order measures the operators' infrastructure. A vendor fingerprint would be a
   common-mode shock: a delay or outage that hits every title in the same minute (proposal 6).

4. **No segment or fragment clock in any subscriber's takes (negative; nobody needs to redo this).**
   - The quantity: within-event differences between take-cluster signing times, for pairs 20-600 s apart.
   - Rayleigh R at exactly P = 1, 2 and 3 s, against a U(-P/2, P/2) jitter null with 400 draws:
     - wallet alone (1,162 clusters): p 0.65 / 0.76 / 0.71;
     - wallet co-signed (390): 0.18 / 0.80 / 0.69;
     - P4e: 0.66 / 0.75 / 0.92;
     - P93, 0xf1ee4842, 0x8a80528d: 0.13-0.92.
   - The one exception is 0x2005d16a at 1 s (p 0.0075). It is a general in-play maker, so this has no bearing on
     the feed.
   - Below 5 s the structure at ~1.04 s is FAK re-attempts after the in-play delay, not a feed clock.
   - So no source class that batches its decisions on HLS segment or CSTV+ fragment arrival with fixed processing
     fits, neither for the shared events nor for the wallet's 74% alone takes. A reader that plays the stream in
     real time is not excluded.
   - The absolute ms-of-second phase is uniform for every signer, so there is no wall-clock-aligned poller either.

5. **The 74% "alone" takes happen in the same live phases as the feed's events.**
   - In 4,191 busy CS2 minutes (at least 3 public non-subscriber taker orders in its markets), consider the minutes
     with no take by any of the six subscribers within ±5 min (179). The wallet takes in 1.1% of them, against 27.0%
     in the other minutes.
   - With the wallet's process up: 1.5% (133 minutes) against 27.3%.
   - With the subscribers still active in Dota 2 / LoL / Valorant in those minutes (feed up), it is 2.0% (101).
   - So CS2 silence is mostly game phase (pauses, between maps), and the wallet falls silent with the subscribers.
     This fits one source with a kind filter, but does not prove it. A real outage test needs outages (proposal 6).

6. **Do the subscribers share a target price? Not the wallet and P4e** (`limit_agree.py`).
   - P4e to the wallet on the same token within 150 ms (196 pairs): limit difference median -1c, IQR 4c, SD 3.2c.
     Exact-cent equality 8%, which is chance (11% after shuffling within 5-cent levels).
   - P4e to P93 at +200-700 ms (131 pairs): equal 24% against 13% (p 0.002). That could be a shared book anchor
     rather than a shared value.
   - 0x8a80528d = 0xddb6e624 in 98% of pairs: the same process, as iteration 7 found.
   - A value-carrying odds feed with the wallet as one of its readers is therefore not supported at the cent level.
     The strong form needs the stale ask (proposal 5).

7. **Every public in-round source examined so far was an API, never a web page's push channel.** Covered so far:
   - bo3.gg REST `live_coverage` (null);
   - Polymarket's sports socket (a 20.3-s re-send cycle);
   - HLTV (403);
   - SX Bet (needs a key);
   - Azuro (DNS failure).

   Nobody has listed the WebSocket / SSE channels behind the live pages of the trackers, organisers and broadcasts
   of its events. X91 covers only Polymarket's own page. That is where a key-free push feed with many subscribers
   at fixed lags would most plausibly be found (proposal 1).

## Proposals (ranked by the chance that they close the gap)

### 1. Push channels behind public live pages: trackers, organisers and broadcasts (strong form of X71 / X91 / A5; new data class)

- **Hypothesis.** Some public web page carries in-round events (kills, plants, round ends) for the wallet's non-GRID
  tier-3/4 matches over a push channel (WebSocket, socket.io, SSE or Twitch PubSub). That channel is either the
  feed itself or a public view of it. Candidates:
  - a tracker's live match page (bo3.gg's web page, not its REST API);
  - an organiser's match page (1win, StarLadder for Stake Ranked, PGL, NODWIN, Digital Crusade for DraculaN,
    FiReSPORTS);
  - a broadcast overlay or Twitch extension on the official channel.
- **Why it fits.**
  - The feed is a push fan-out: at least 6 subscribers, event SD 7-9 ms, no platform effect.
  - It covers a tier-defined set of leagues (critique 2) and serves several titles.
  - Every source tested so far is a REST API or a polled socket (critique 7). Organisers and trackers of
    betting-sponsored tier-3 leagues routinely run live scoreboards from a CSTV+ relay or a vendor widget.
- **Test.**
  1. In the next development block (11-01 06-12 or later), use dev-start units only. Open each live page as a normal
     visitor in the browser pane:
     - the bo3.gg match page;
     - the organiser's page;
     - the official Twitch channel (extension iframes).
  2. List its push channels with `read_network_requests` (`ws`, `wss`, `eventsource`, long-poll XHR to the same host).
     Note the message types and cadence for 10-15 minutes. Stop at any login, captcha or key, and never open a
     sealed unit.
  3. If a channel carries in-round events, write a `Writer`-based recorder (hard stop, under 100 MB of memory and
     300 MB of disk, filed by unit) and record it in `state.json` `live_lab`.
  4. Pre-register before scoring. Take the lead or lag of the channel's in-round events over three anchors on the
     server clock (event bootstrap): the wallet's take signing, P4e's signing, and the validated untriggered pulls.
     - If the channel precedes at least 50% of the wallet's takes, or sits at a constant lag of 100 ms or less behind
       them, it is the public form of the feed. The taker rule can then be frozen on it, and the examiner gets the
       recording.
     - If it lags by a constant D of 1 s or more, it is broadcast-side. It still gives the in-round clock that X8 /
       X50 never had: the event kind of every take and untriggered pull (plant against kill).
- **Data.** Public web pages and their push channels (key-free), the shared and own book recorders, and the dev-block
  calldata. No account, no download.
- **Signature if true.** A channel whose messages are typed in-round events, with sign-to-message lags as tight as
  the fan-out (IQR tens of ms). Its coverage, set by tier, would match P4e's event set.

### 2. Name the vendor from the feed's own coverage: P4e's event set as the label (strong form of X15 / X39 / X90)

- **Hypothesis.** The feed is a B2B live product whose coverage is defined by tournament tier, plus GRID's exclusives
  removed. It is not one rights holder's official feed.
- **Why it fits.**
  - Critique 2: PGL (Oddin.gg) traded 9 of 13, but Exort (Oddin.gg exclusive) 0 of 11 and ESEA (Bayes, never
    GRID-flagged) 0 of 37.
  - "Non-GRID and tier <= 4" picks 3 of 4 forward events (iteration 7).
  - P4e, a pure feed taker, is absent from every non-whitelisted league (X15).
  - Polymarket stores PandaScore ids for every event, and its `leagueTier` is probably that provider's tier.
- **Test.**
  1. Label = each subscriber's presence per event (P4e for CS2; 0xf1ee4842, 0x8a80528d and 0xddb6e624 for Dota 2 /
     LoL / Valorant). These labels are wallet-independent, so the selection rule is not being refitted.
  2. Competing boundaries, all from listing time or public pages:
     - `leagueTier`;
     - the GRID flag;
     - the official rights holder (press releases: Oddin.gg, Bayes, GRID, others or none);
     - bookmaker-owned organiser;
     - LAN or online;
     - stream platform.
  3. Fit each boundary alone, by title. A tier-only boundary that is identical in CS2 and in the other titles
     indicates a tiered multi-title product.
  4. Then check `leagueTier` against PandaScore's tier for the same tournaments: PandaScore's public documentation of
     tiers, plus the X55 token if the user provides one.
- **Data.** Gamma listing fields and subscriber calldata (both on disk), and vendor press releases (web).
- **Signature if true.**
  - Subscriber presence follows tier, and not the rights holder, in every title. Then the user ask becomes one
    named product (a PandaScore-class live API) instead of the current list.
  - A holder boundary instead names that holder's feed. Its bookmaker customers' in-play pages are then the only X48
    probes worth clearing.

### 3. Polymarket's own data provider as a latency yardstick, with GRID events as the positive control (new)

- **Hypothesis.** The provider behind the sports socket for non-GRID events (gameId = PandaScore id) sits at a fixed
  point of the latency chain, and that point can be measured.
  - It may be server-fast. Then a PandaScore-class live product is the feed's prime candidate.
  - It may be a stream scout, with a lag on the order of the broadcast delay. Then the feed is elsewhere.
- **Why it fits.** The socket re-sends each game every 20.3 s (iteration-6 critique 1). With many map ends, the lower
  envelope of the lags still estimates the provider's latency to within about 1 s. GRID events give the same number
  for a known server-side official feed.
- **Test.**
  1. Use the dev blocks already recorded (10-31 12-18; 11-01 06-12 when it exists) and dev-start units.
  2. For every map end, take the market's terminal repricing on the map market: the first print at 0.985 or more
     with no later print below 0.95.
  3. Take the socket's first message with the incremented map score.
  4. Compute lag = socket - market for each map end, and estimate the lower envelope L (the minimum and the 10th
     percentile, with an event bootstrap) separately for GRID and non-GRID events.
  5. Also poll Gamma's `score` / `period` event fields key-free on two dev units, every 2 s for 10 minutes, to see
     whether they update off the socket's cycle.
- **Data.** The shared `sports` and `clob_*` recordings (dev blocks), Gamma event fields.
- **Signature if true.**
  - L_nonGRID within a few seconds of L_GRID: the provider is server-speed for these events. The PandaScore token
    (X55) moves to the top of the asks, together with a prediction to check: the vendor's round-end timestamps lead
    the market's round-end repricing.
  - L_nonGRID of 30 s or more above L_GRID: the provider scouts streams, it cannot be the feed, and the asks drop
    it.

### 4. The book as the carrier of its private events: re-score Z4 on prints and classify the followers (new; check in critique 1)

- **Hypothesis.** Other makers read the wallet's pulls on the public market websocket and copy them within 10-150 ms.
  Part of the others'-mid markout of its untriggered pulls is that copying, not price discovery. The remainder is
  its private information.
- **Why it fits.** Critique 1:
  - ~10x the shift null in (+5, +150] ms;
  - a 10-ms dead time;
  - 6.5x more on the same book than on sibling books;
  - the markout grows with the number of followers (-0.49 / -0.58 / -0.80c).
- **Test.**
  1. Markout on public trade prints: VWAP of non-wallet prints in (+5, +15] s, (+25, +35] s and (+100, +140] s
     against the last print before the pull. Also the mid at +120 / +300 s, after the book has refilled.
  2. Stratify by follower count, and report the no-follower stratum next to the frozen VALIDATE-live test.
  3. Positive control for book-reading: run the same follower count after other makers' untriggered ladder pulls of
     similar size (attributed with the calldata-validated linking).
  4. Name the followers by size fingerprint or linked adds.
- **Data.** On disk for BUILD-live. 11-01 blocks for VALIDATE-live.
- **Signature if true.**
  - Followers react equally to other makers' large pulls: they are book readers, and Z4 rests on the no-follower
    and print-based markouts.
  - Followers react only to the wallet's pulls: they are informed-maker followers. That is a second public channel
    through which its information leaks, and a reason its maker edge is ordinary.
  - Either way the wall account gets a cleaner number for the private input between takes.

### 5. Value or raw events: cross-subscriber limits against the stale ask (strong form of X48(a) / V4 / Y4)

- **Hypothesis.** If the feed carries a value (live odds or a win probability), co-signing subscribers' limits track
  a common latent target, limit_i = V_e - m_i, independent of the stale ask. If it carries raw events, each
  subscriber anchors on the stale ask plus its own premium.
- **Why it fits.** Critique 6: the wallet and P4e do not agree at the cent level; P93 copies P4e's limit at twice the
  chance rate. X48(b), the odds probes, waits for terms that this test could make unnecessary.
- **Test.**
  1. On co-signed events (16-22 Oct matched-order record), rebuild the stale ask at each signer's sign - 100 ms from
     prints in transactions without that signer, using the X29 match clock.
  2. Regress limit_i - stale ask on the event's realized 60-s move. Decompose the cross-subscriber covariance of the
     premiums into an event factor and noise.
  3. Repeat on BUILD-live books with the true touch.
- **Data.** On disk. Live books for the check.
- **Signature if true.**
  - Premiums share an event factor with near-constant offsets (residual SD under 1c): a value feed. The X48 probes
    then target the odds products of the vendor from proposal 2.
  - Premiums uncorrelated beyond the stale ask and the move: raw events, and the odds-feed class closes.

### 6. Outages as natural experiments: one source or two (new)

- **Hypothesis.** If the wallet's alone takes and untriggered pulls come from the same feed as P4e's events, they stop
  in a feed-wide outage. If the wallet has its own source, it goes on acting through the feed's outages and stops
  during its own.
- **Why it fits.** Critique 5 shows the co-variation is mostly game phase, so only true outages separate the two.
  Iteration 7 also found 3 gaps of 30 minutes or more with the merge loop running (the process up, but idle).
- **Test.**
  1. Wallet-side gaps: in each idle-but-up gap, count P4e's and the other subscribers' takes in live events of its
     leagues, against matched windows.
  2. Feed-side outages: find minutes with no subscriber take in any title while at least two titles have live games
     (busy public tapes, plus the sports socket's live / period fields from 11-01). Measure the wallet's takes and,
     live, its untriggered pulls.
  3. Common-mode delays: per hour, the P4e - 0x2005d16a lag in CS2 and the 0xf1ee4842 - pair lag in Dota 2 / LoL.
     Test their correlation against an hour-shift null; a single vendor shows shared shocks.
- **Data.** On disk for 16-22 Oct. Live socket for the phase control.
- **Signature if true.**
  - Subscribers active during its idle-but-up gaps: its input was down while the feed was up, which means a separate
    source or subscription and an exam-day downtime risk.
  - The wallet active through a feed-wide outage: a second source for the 74%.
  - Correlated lag shocks across titles: one vendor, which also tests critique 3.

## Sources (web search)

- [Oddin.gg extends partnership with esports organizer PGL (Canadian Gaming Business)](https://canadiangamingbusiness.com/?p=16356)
- [Oddin.gg secures multi-year data partnership with Exort (Gambling Insider)](https://www.gamblinginsider.com/news/29018/oddin-gg-secures-multi-year-data-partnership-with-exort)
- [Oddin.gg enters official data rights space with PLAYzone deal (iGaming Future)](https://igamingfuture.com/oddin-gg-enters-official-data-right-space-with-playzone-deal/)
- [Bayes Esports and Oddin.gg enter strategic partnership (Bayes)](https://bayesesports.com/press-releases/bayes-esports-and-oddin-enter-strategic-partnership)
- [GRID, Oddin.gg in esports data deal (Intergame)](https://www.intergameonline.com/sports-betting/grid-oddingg-in-esports-data-deal)
- [Abios obtains official CS2 and Dota 2 data through Bayes (iGaming Future)](https://igamingfuture.com/abios-obtains-official-counter-strike-2-and-dota-2-esports-data-through-bayes-esports-partnership-extension/)
