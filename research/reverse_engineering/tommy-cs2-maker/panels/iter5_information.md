# Panel, iteration 5: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-5), state.json (ledger, catalog A1-X69, components), FINAL_RULE.md and every
file in panels/. There are no EXAM or wall-audit files.

I ran small checks on development data only:
- 16-22 Oct: `census_bursts.parquet`, `orders.parquet`, `calldata_all`, `calldata_pub`, the windowed tapes,
  `universe.parquet`, `events_sel.parquet`;
- bo3.gg game records through polyrea's `HttpClient` (cached), plus 40 new GRID-map lookups;
- one read of the shared `sports` feed for the 10-31 12-18 block.

Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter5info/`:
`bomb_timer.py`, `bomb_timer2.py`, `dead_zone.py`, `dead_zone_tape.py`, `coverage_runs.py`, `coverage_cross.py`,
`lag_drift.py` and `map_end_clock.py`.

I also ran three web searches.

**Sealed-data note.** My first sampler of the `sports` feed printed one record of a sealed unit before it filtered
anything: Nemiga-FURIA, which started in the sealed 06-12 block, appears in a dev-block file. The record was its map
score. Nothing from it was stored or used. Every reader of the dev folders must filter by the unit's start before it
prints anything. The same file also raised the known `zlib.error` from `iter_live`.

## Critique: what the investigation is missing or getting wrong

1. **"Its input covers a subset of event types" rests on per-map GLMs. The burst record says something sharper: the
   wallet's presence is per match, and it is intermittent.** Data: `coverage_runs.py` and `coverage_cross.py`, on the
   3,623 informed 3c+ bursts with "late" bursts dropped. Present means wallet-led or wallet-near.

   | Check | BUILD | VALIDATE |
   | --- | --- | --- |
   | Present share | 0.162 | 0.166 |
   | Overdispersion across markets, chi2 (null median) | 147 (87), p < 0.0005 | 165 (85), p < 0.0005 |
   | Overdispersion across events, chi2 (null median) | 80 (36) | 96 (34) |
   | Runs within markets, observed (within-market permutation median) | 411 (436), p 0.015 | 432 (464), p 0.003 |
   | P(present), previous burst in the market within 120 s present / absent | 0.239 / 0.113, p 0.0025 | 0.240 / 0.116, p 0.005 |

   - The state persists at gaps of 120-600 s: 0.278 against 0.191.
   - It is not a global on/off state such as a session, an outage or bot load. Against the nearest burst of another
     event within 120 s, P(present) is 0.156 against 0.166 (n 2,349, p 0.66).
   - It prefers reversals. When the previous burst within 120 s was on the other team, P(present) is 0.30-0.37. When it
     was on the same team, it is 0.05-0.18.
   - It is not latency drift. Over the 1,035 pack bursts with a wallet take in [-1, +30] s, the wallet-minus-pack
     signing lag is not autocorrelated within markets: consecutive-lag Spearman 0.055, p 0.09. Lead after lead is
     0.32, against 0.31 after a follow.
   - Caveat: price level (it leads more at 0.2-0.5) and half / side composition also persist over minutes. The
     permutation must be stratified by them (proposal 3).
   - Even so, a pure event-type filter does not predict cross-match independence plus within-match persistence. A
     per-match source with an on/off state does: a stream session, a relay connection or a scout.

2. **Game-phase clocks have no power on this record, so do not spend on them.** I tested two of them.
   - **Bomb-timer echo.** CS2's C4 timer is 40 s. A plant-type take followed by a burst at the explosion would pile
     up near +40 s on the same token. Over the unfiltered bursts (1,612 wallet, 10,605 pack, 8,568 large public), the
     39.5-42 s bins are flat:
     - wallet to pack, same token: ratio 0.97;
     - pack to pack: ratio 0.93;
     - census bursts: ratio 1.03.
   - **Round-restart dead zone.** CS2 waits about 7 s after a round, plus 15-20 s of freeze time. I looked for a quiet
     period after 4c+ repricings:
     - after 2,394 wallet-absent bursts, there is none in the wallet's takes or in the pack's bursts;
     - on the tapes, there is none in GRID markets either (1,363 anchors) or in non-GRID markets (1,779 anchors). The
       rate of large prints stays at 2-4x the mean for 60 s.
     The positive control fails, so a tape or burst dead zone cannot say whether a feed is event-driven.
   - Treat the X54 refractory test with care for the same reason. Only an external typed clock can name the event
     type.

3. **The official-data-rights map is now falsified in both directions.**
   - Exort Series has a multi-year exclusive official data deal with Oddin.gg, and Exort Fiesta is traded 0 of 11.
   - ESEA (ESL FACEIT Group, Bayes live data) is traded 0 of 37.
   - PGL (Oddin.gg) is traded 9 of 13.
   - So "covered by official data, skip" fails (X39), and so does the inverse, "an Oddin-type feed, trade". Retire the
     organiser data-deal axis. Selection is something else at platform or league level (proposal 2).

4. **The bo3 half-level clock has never been validated against the market, and a rough check could not validate it.**
   - `map_end_clock.py` compares the market's decisive map-end repricing with bo3 `begin_at + duration` on 175 maps.
   - The median lag is -214, -327 and -413 s, with p25-p75 spans of 300-500 s. That holds for traded, untraded and
     GRID maps alike.
   - Part of this is my detector: the last print below 0.85 can come several rounds before the end. So the result is
     not a calibration. It does show that the clock is not known to the minute.
   - The T-side tests (53.8% and 56.5%) exclude only ±3 min around halftime, so misassigned takes pull the share toward
     0.5. Calibrate each map's clock on its own market first, using the map start (first in-play moves) and the map
     end. Then rerun the side test before using it against the plant reading.

5. **"The resting ladder is not a public function" was tested on the wrong public state.**
   - The probes score 2-s-stale tape state (AUC 0.669). But the bot reacts to the live book within about 100 ms: it
     joins others' live best within one tick in 67.4% of re-quotes, against 25-34% for every historical anchor.
   - The live book is public, and it is recorded in every block. That includes sealed blocks, so the examiner has it
     too.
   - The conclusion that the outcome needs private input (oracle bound, X57) is premature until occupancy and the
     replay are scored on the live book (proposal 1).

6. **The source search has turned into requests to the user.** The open items X53, X55, X64, X37, X4 / X22 and X48
   all need the user. Meanwhile the key-free sources specific to tier-3 CS2 have not been searched:
   - the organisers' own match-server panels;
   - CSTV / GOTV+ HTTP relays, whose `sync` JSON carries the broadcast delay;
   - SX Bet's on-chain fills. The API was tried (X23), but the chain was not.

## Proposals (ranked by the chance that they close the gap)

### 1. The maker leg runs on the live book: re-score quote occupancy and the outcome on the recorded books (strong form of X56 / X63 / X57)

- **Hypothesis.** The maker ladder's input is public but fast. It is the other makers' live book with the wallet's own
  levels removed, at about 100 ms: their best, their depth, and their cancels or re-quotes in the last few hundred ms.
  Its own take events add to this.
  - Occupancy at a whole-cent level is a function of that state.
  - The residual it avoids, by not sitting at levels while the price trends, follows others' pulls (cancel waves)
    within about 100 ms.
  - Tape state 2 s old cannot see any of this, which is why the probes stop at 0.67.
- **Why it fits.**
  - Live re-quote tops are within one tick of others' best in 67.4% of re-quotes (exactly at it in 37%), against
    25-34% for historical anchors.
  - It reacts to others' best within 100 ms at any gap (22-37%, against a 2-5% null). 15% of its fill shares come from
    orders posted in the takers' 1-s delay.
  - The probe label agrees with the live own-level tracker in 90.8%.
  - X57's own diagnosis: "the missing input for the outcome is the wallet's quote presence".
- **Test.**
  1. Labels. Build a dense label from the own-level tracker on `tommy_cs2_near`, using the event-size fingerprint fix
     from `probe_validate_live.py`: occupancy of each whole-cent level within 6c of others' best, per token and 100-ms
     tick. Add the sweep probes of the same blocks.
  2. Features, at t - 100 ms, from the live book only (own levels removed, no own state; report an own-inventory
     variant separately):
     - level minus others' best bid;
     - others' size at and ahead of the level;
     - others' best on the complement, and the pair sum;
     - counts of others' best changes and cancels per side in the last 100 and 500 ms;
     - age and side of the last trade;
     - game time.
     Baselines: the stale-tape probe model (`sweep_probes.py` features) and prints-only activity. BUILD = the 10-31
     blocks; VALIDATE = the development blocks from 11-01 18:00 (the pre-registered live split).
  3. Distill the model into a rule (tree to rule) and replay it as an executable ladder on the recorded books with the
     validated engine.
     - Fills come from the blocks' matched-order record, with strict price-time priority.
     - Re-quote and cancel latency 100 ms. Also report the brief's latency of 2 s or more, and settle with the examiner
       which one item 5 uses.
     - Pair cap K, and merges.
     - Report per-market PnL correlation with the wallet on the dev blocks, with margin and residual separately.
  4. Wire occupancy and the replay into `evaluate()` through `iter_live(..., allow_sealed=ALLOW_SEALED)`, so the
     future-block exam can score price and outcome. h1 and h2 have no books.
- **Data.** The own recorders (running in every block), calldata of each block's taker transactions, and the wallet's
  on-chain fills.
- **Signature if true.**
  - Occupancy AUC of 0.85 or more from the live book, against about 0.67 from stale tape.
  - The replayed ladder is hit where the wallet is hit (37% of pack-only events).
  - Per-market PnL correlation of 0.5 or more, and price within one tick climbing toward 0.8 once the deeper levels
    are modelled.
  - If occupancy stays near 0.7 on the live book too, the private input reaches the maker leg, and the outcome gap can
    be stated as private with a number attached.

### 2. Key-free organiser-side live sources: CSTV (GOTV+) relays and match-server web panels, mapped league by league (new source class)

- **Hypothesis.** The pushed in-round source is the match server itself, reached through an organiser-side channel
  that is public but that the market does not use. Two forms:
  - a CSTV / GOTV+ HTTP broadcast relay (a "playcast" URL), whose delay is set by the organiser;
  - the live page of a match-management panel (eBot, Get5 / G5API with MatchZy, Challengermode or similar). These
    stream kills, bomb events and scores from the server log. CS2 can POST its logs over HTTP to several addresses,
    with an optional delay per address (`logaddress_add_http`, `logaddress_add_http_delayed`).
  Coverage would then be per organiser platform. That explains league-level selection that neither GRID nor official
  data deals explain (critique 3).
- **Why it fits.**
  - Two operators act within about 10 ms on the same events, the signature of a push.
  - Nothing public on Polymarket precedes it.
  - No vendor seen so far has live round data for these events: not PandaScore through the socket, not bo3, not the
    SX listing.
  - A log or relay carries plants as discrete events, and plants are the event type its takes load on.
- **Test.**
  1. **Platform map.** For each of the 22 non-GRID leagues of 16-22 Oct, and the newer dev-block leagues (FiReSPORTS,
     CyberClash), read the Liquipedia tournament pages, rulebooks and organiser match pages as a normal visitor
     (WebFetch, no login). Look for:
     - the match server or platform;
     - any public "watch in CS2" / playcast / CSTV link;
     - any live match page with round or kill updates.
  2. **Selection.** Score "public live log or relay" as a league flag against activity + GRID on VALIDATE: AUC, the
     gain's CI, per-day gains, and especially leagues not seen in BUILD.
  3. **Live record, relay.** Where a traded league has a public relay, poll `<relay>/sync` every 0.5-1 s during a
     development block. It is a small JSON with tick, real-time delay, ticks per second and map. Use a Writer-based
     recorder with a hard stop and caps.
     - The relay's own delay says directly whether, and by how much, the public broadcast runs behind the server.
     - Parsing the fragments into events needs a demo parser, so the user's consent. The `sync` metadata does not.
  4. **Live record, panel.** Where a traded league has a public panel, record its event stream: event type and time
     only. Then run lead-lag of panel events against the wallet's `sign_ms` and its own-size pulls on the CLOB server
     clock, by event type.
  Stop at any login, key or Cloudflare challenge; do not work around access controls.
- **Data.** Public web pages and relay or panel endpoints. No keys.
- **Signature if true.**
  - Traded leagues run on platforms with a public live log or relay. Skipped leagues do not, or run on FACEIT or GRID.
  - Panel or relay events precede its signings by 0-200 ms on the events it takes (plants).
  - Its absent bursts are event types the source does not push, or pushes late.
  - The taker trigger becomes a frozen rule on a recordable input, and "Can a normal user deploy it" changes.
  - If no traded league exposes such a source, this source class is ruled out with evidence, and the X38 chat clock
    remains the discriminator between V1 and V2.

### 3. The per-match coverage state: what switches the wallet's input on and off (new; from critique 1)

- **Hypothesis.** The 80% absence is a per-match input that switches on and off over minutes. The causes could be a
  stream session, a relay connection, or a scout who follows one match.
  - Under V2 (broadcast-derived), the on-state follows the broadcast: which match the channel shows, technical breaks,
    replays.
  - Under V1, it follows the relay or log connection, and nothing the broadcast does.
- **Why it fits.** Critique 1: overdispersion across markets, fewer runs than chance, persistence over 120-600 s, no
  dependence across concurrent events, no latency drift, and a fourfold preference for reversals.
- **Test.**
  1. **Controls.** Rerun the within-market permutation stratified by price level (0.1 bins), map versus match, game
     time, and half / side on a market-calibrated clock (critique 4). Then keep "previous informed burst on the other
     token within 120 s" as a pre-registered public covariate. Add it to the census, and to the live taker presence
     model (0.5-s bins x team).
  2. **Segments.** Fit a two-state HMM per market over the sequence of informed bursts: emission = present or absent
     given the public covariates. Estimate the on and off segments and their durations.
  3. **Alignment.** On the dev blocks, align the segments with the broadcast-state recordings:
     - `tommy_chat` message rate per channel, as a proxy for the stream being live and active on that match;
     - co-streams of the same event;
     - the wallet's own-size pull rate. If the input is off, the pulls should drop too, not only the takes.
- **Data.** Census bursts (on disk), calldata, `tommy_chat` and `tommy_cs2_near`.
- **Signature if true.**
  - V2: off segments coincide with chat lulls or stream breaks. On a channel shared by concurrent matches, only one is
    on at a time. Its pulls stop with its takes.
  - V1: the segments do not depend on the chat or stream state.
  - If the clustering disappears after the controls, the event-type reading stands, and the input is a typed filter
    (proposal 2 then names it).

### 4. SX Bet's on-chain in-play fills as a second venue's clock (strong form of iteration-3 information P5; only the API half was tried)

- **Hypothesis.** SX Bet offers in-play CS2 on the same tier-3 events: X23 found FiReSPORTS ShindeN v Isurus listed
  in play. Its in-play makers price from a B2B feed. Its fills and odds settle on the SX chain, which is public chain
  data and needs no API key. They give an independent clock for whether a vendor feed reprices at the wallet's events
  (before or after it), and which events that vendor covers.
- **Test.**
  1. Take the SX chain RPC and the exchange contract addresses from docs.sx.bet. Verify the endpoint first.
  2. During dev-block CS2 events, note the market hashes that `api.sx.bet/markets/active` lists while the events are
     live (key-free per X23).
  3. Read the fill events: block time, market hash, odds, side and stake.
  4. Run lead-lag of SX fills and odds changes against the wallet's takes and the CLOB cancel wave, split by burst
     class (wallet-led against pack-only).
  5. Use SX in-play availability per event as a selection feature on the dev blocks.
- **Data.** The SX chain RPC, the SX listing, and the Polymarket recordings.
- **Signature if true.**
  - SX odds move within a block or two after the wallet's takes on its event types, but not on the pack's (or the
    reverse). That would name the class of the wallet's or the pack's feed.
  - SX in-play coverage overlaps the wallet's events beyond activity.
  - Low priority: fills are sparse, block resolution is coarse, and SX applies its own bet delay.

### 5. Funding graph of the wallet and 0x51dbdd2b: one operator or two subscribers (strong form of C1 / X14; funding was never checked)

- **Hypothesis.** 0x51dbdd2b is the same operator's maker wallet, driven by the same signal, not a second subscriber
  of a vendor. It trades 69% of the wallet's events and all 3 of its Dota 2 events. It cancels 9-13 ms after the
  wallet's signings and never leads the wallet.
- **Test.**
  1. Run Polygon `eth_getLogs` for ERC-20 Transfer events with topic2 = each address, on USDC.e, USDC and the exchange
     collateral. Use block windows of ±3 days around each address's first trade and around large balance changes.
  2. Addresses:
     - the wallet and its owner 0x8af810f0;
     - 0x51dbdd2b and its signer 0xdecd4b4c;
     - 0xe40ecff6 and 0xed446954;
     - P4e.
  3. Find each EOA's first POL funding by bisecting `eth_getTransactionCount` over blocks.
  4. Look for common funders, shared exchange deposit addresses, direct transfers and synchronized withdrawals.
- **Data.** Polygon RPC (publicnode), a few hundred calls.
- **Signature if true.**
  - A shared funder or direct transfers mean one operator. The 10-ms co-timing is then one process, and the
    information story collapses to one private input.
  - No link leaves "two subscribers of one source" standing.

## Sources (web searches)

- [Oddin.gg and Exort: multi-year exclusive official data partnership for Exort Series CS2 events (iGamingBusiness)](https://igamingbusiness.com/company-news/oddin-gg-and-exort-announce-multiyear-data-partnership-for-exort-series-counter-strike-2-events)
- [Oddin.gg secures multi-year data partnership with Exort (Gambling Insider)](https://www.gamblinginsider.com/news/29018/oddin-gg-secures-multi-year-data-partnership-with-exort)
- [Oddin.gg and PGL multi-year partnership (AGB)](https://agbrief.com/news/elsewhere/24/04/2024/oddin-gg-in-multi-year-partnership-with-esports-tournament-organizer-pgl/)
- [Bayes Esports and Oddin.gg strategic partnership (Bayes; Bayes is the official live data supplier for ESL FACEIT Group)](https://bayesesports.com/press-releases/bayes-esports-and-oddin-enter-strategic-partnership)
- [CS2 `logaddress_add_http_delayed` (TotalCSGO)](https://totalcsgo.com/commands/logaddressaddhttpdelayed)
- [cs2-log-parser README (CS2 HTTP log streaming)](https://cdn.jsdelivr.net/npm/cs2-log-parser@1.1.0/README.md)
- [BLAST srcds-log-parser (CS2 logs over HTTP)](https://npmjs.com/package/@blastorg/srcds-log-parser)
