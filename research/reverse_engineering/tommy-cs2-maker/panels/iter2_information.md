# Panel, iteration 2: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iterations 1-2), state.json (ledger, catalog, components),
FINAL_RULE.md and panels/iter1_*.md. No EXAM or wall-audit files exist.

I ran small read-only checks on development data only: 16-22 Oct (the RE's parquet files in `.cache/re/tommy-cs2-maker/`
and cached bo3.gg match details), and the 10-31 12-18 UTC development block (`calldata_dev`, `collapse_events_dev`,
`activity_devblocks`). I also ran endpoint probes. Nothing sealed was read:
- the SX Bet probe listed only events whose gameTime falls in the 12-18 block;
- the bo3 `/matches/live` and OpenDota `/live` responses were fetched but only their length was printed.

Scripts: `C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter2info/`:
- `loop.py`, `loop2.py`, `phase.py`: client clock;
- `bo3fields.py`: bo3 pre-match fields against selection;
- `sib.py`: sibling-market collapses;
- `pending.py`: pending-order footprint;
- `makerfill.py`: maker fills after collapses;
- `cancellers.py`: rough canceller attribution;
- `probe*.py`: endpoints.

## Critique: what the investigation is missing or getting wrong

1. **The claim that the book is "a sufficient public trigger either way" is premature.**
   - The collapse rule's precision is 3.7%: the wallet acts on 4-8% of collapses.
   - A trigger that fires 25 times for every order it explains is a correlate, not the decision. The deciding input
     for the other 92-96% has not been named.
   - Two readings remain open:
     - it reads the book with some filter (persistence, depth left, a stale ask);
     - it reads a game feed, and the cancels are the faster makers' footprint of the same event.
   - The investigation has not used the one clock it has with millisecond quality, which is the wallet's own client.
     See check A.

2. **New check A: the wallet's client clock.** Signing times, 16-22 Oct, 25,878 orders; bursts are signings within
   150 ms.
   - **After a taker burst** the next burst starts 1,000-1,100 ms later in 409 of 1,059 cases. That bin holds 25x a
     typical 50-ms bin. The client blocks on the 1-s in-play delay of its FAK and signs the next orders (the re-pair
     bids) as soon as the response returns.
   - **Maker to maker**, the intervals spike at 1,000-1,010 ms (96 in that 10-ms bin against about 25 in the
     neighbouring bins) and at 500-550 ms (2.9x).
   - **No phase locking** modulo 250, 500 or 1,000 ms within 10-minute windows (Rayleigh test, same as the null). So it
     is sequential code with fixed sleeps or cooldowns, not a wall-clock timer.
   - **Consequence: the lag is not network latency.** Its round trip, signing included, is at most about 100 ms on top
     of the 1-s delay. Its median 0.77 s lag after a collapse (p10 0.32, p90 0.96) must therefore come from one of:
     - a deliberate wait or debounce on the book;
     - a cooldown after its previous action;
     - a slower information channel than the cancelling makers'.
   - A 50-ms book reader without a wait would sign within about 0.1 s.

3. **New check B: the collapse is not the footprint of a pending, speed-bumped taker order.**
   - The test: public taker orders that consume the collapsed team's asks (BUY X or SELL Y), signed in the 3 s before
     the collapse.
   - They appear before 1.3-2.6% of the 605 collapses (per window), the same as at control times 60 s earlier.
   - So the vanished depth is cancels, as the RE concluded. Matched-order leakage through the 1-s delay is ruled out.

4. **New check C: collapses span markets, but loosely.**
   - Data: the shared recorder, one event with two recorded markets (FiReSPORTS gls1-pcy, match and map 2), 14:29-14:56
     UTC.
   - 8 of 19 match-market collapses have a same-team map-2 collapse within 2 s. The expected count is 1.34 (p95 3)
     under ±30-120 s shifts. So collapses partly reflect an event-level shock, not one maker's quirk in one market.
   - The offsets are spread over -1.9 to +1.7 s. A single push feed to the first cancellers would give offsets within
     about 100 ms. The 200-ms throttle blurs this, but not by seconds.
   - The own recorder (`tommy_cs2_near`, unthrottled near-touch) can settle it (proposal 3).

5. **New check D: collapses barely move the presence metric.**
   - Within 3 s of a collapse, the wallet gets a maker fill on the complement token with probability 3.5%, and 3.0% on
     the same team. At control times the figures are 1.5-2.0% and 1.3%. That is about 2x on both tokens and not
     side-specific.
   - The 30-s fill presence metric is dominated by maker fills from ordinary taker flow. So even on future blocks the
     book route will not lift `presence_auc` much.
   - h1 and h2 have no books at all. For the first exam the only component that can pass is **selection**. Its
     information source is where the next gain has to come from (proposal 1).

6. **New check E: selection inside a league is per match or group, not per channel or team.**
   - DraculaN, 10-19, group stage:
     - Group C was traded 5 of 5 times, on draculancs, draculancsb and draculancsc at 11, 12, 14 and 17 UTC;
     - Groups A, B and D were traded 0 of 15 times, on the same channels at the same hours.
   - So stream-channel proxies (X6, +0.005) cannot work.
   - Team identity carries over weakly: a BUILD team-rate score gives an AUC of 0.587 within the partly traded leagues
     on VALIDATE.
   - Coverage is decided per match, as a data provider or bookmaker covers a fixture. It is not the stream.

7. **New check F: bo3.gg pre-match fields carry a selection signal nobody has used.**
   - The RE used only bo3 `tier`. Here are 112 non-GRID events of 20-22 Oct matched to bo3 details (41 traded):

     | Feature | Event AUC | Within partly traded leagues (n 50) |
     | --- | --- | --- |
     | bo3 `stars` (0-3) | 0.911 | 0.750 |
     | Pre-game distinct wallets (`e_pre_w`, the baseline's best) | 0.879 | 0.717 |
     | bo3 `tier_rank` | 0.833 | |
     | Lower team id (established team) | 0.790 | 0.572 |
     | bo3 `bet_updates` present (a bookmaker line) | 0.700 | |

   - Traded rate by stars: 0 stars 5%, 1 star 45%, 2 stars 95%, 3 stars 100%.
   - `rating` scores 0.938, but its meaning and point-in-time status are unknown. Treat it as post-hoc until checked.
     `parsed_status` and `status` are post-hoc.

8. **The pack rotates.** P4e and P93, the two strongest pack wallets of 16-22 Oct, have no transactions in the 10-31
   development block. Pfe, P25, P72 and Pf1 are present, as pure takers. Every rule or feature built on a fixed pack list
   from 16-22 Oct will decay. The pack is a role, so define it by behaviour, not by address.

9. **Endpoints probed, so they need not be probed again:**

   | Source | Result |
   | --- | --- |
   | PandaScore `/matches/<id>`, `/lives` | 403 "Token is missing" |
   | SX Bet `/sports`, `/leagues/active`, `/markets/active` | 200. Lists CS2 FiReSPORTS, PGL Masters, DFRAG, CCT Europe, Circuito Retake and Gamers Club with CLOB trading |
   | SX Bet `/live-scores` | Map-level only, stale (updatedAt the previous day) |
   | SX Bet `/orders`, `/orders/odds/best` | 400 "OrderBook V2 is no longer supported" |
   | SX Bet `/trades` | 404 |
   | Azuro subgraph hosts (thegraph.onchainfeed.org, thegraph.azuro.org, thegraph.bookmaker.xyz) | DNS fails |
   | Thunderpick API | Cloudflare challenge (not bypassed) |
   | Rivalry API | 301 via Cloudflare |
   | Kick chat replay `/api/v2/channels/<id>/messages?start_time=` | 200 with 0 messages at times inside dev-period VODs, so no historical chat clock |
   | OpenDota `/api/live` | 200 without a key (Dota 2 live league games) |
   | bo3 `/api/v2/matches/live` | 200 |

10. **Smaller points.**
    - The Gamma `eventMetadata.context_requires_regen` key is absent on 63 non-GRID events, none of them traded. They
      are mostly leagues that are never traded (ESEA, CIS LAN, Dust2.dk). Check whether it is set at listing before
      using it.
    - `eventMetadata.tournament` ("Group A".."Group D", "Playoffs") resolves the DraculaN group effect, but only after the
      fact.
    - The R5 owner check (owner() differs) does not cover the funding graph or the POLY_PROXY owners. Proposal 3 gives
      a sharper operator test.

## Proposals (ranked by the chance that they close the gap)

### 1. Selection is the per-match live-coverage of a betting data feed; measure it with bo3.gg pre-match fields (strong form of X6 and of the bo3-tier test)

- **Hypothesis.**
  - The pack and the wallet trade a non-GRID match when a betting-grade live feed covers that fixture. That is a data
    provider selling to sportsbooks.
  - Such feeds cover fixtures with ranked or recognisable teams, chosen match by match. That is why DraculaN Group C is
    covered while Groups A, B and D are not.
  - bo3.gg's pre-match importance (`stars`, from team rankings), `tier_rank`, team rank and the presence of a bookmaker
    line (`bet_updates`) are public, pre-game proxies of that coverage. They carry over to new leagues (CyberClash,
    FiReSPORTS), where the league prior cannot.
- **Why it fits.**
  - Stars alone give AUC 0.911 on 112 non-GRID events, against 0.879 for the best pre-game activity feature.
  - Within the partly traded leagues stars give 0.750 against 0.717.
  - 2-3 star events are traded 95-100%, 0 star events 5%.
  - Coverage is per match, not per channel (check E).
  - The pack is absent from 0-star events (the iter-1 info panel: 0 of 52 pack-less events traded).
- **Test.**
  - (a) Fetch bo3 details for every CS2 match of 16-22 Oct. Use `/api/v2/matches/finished?date=D&filter[discipline_id][eq]=1`
    and `/api/v1/matches/<slug>`, which is cached. Match them to all 384 Gamma events, using bo3_coverage.py's team-name
    matching plus start time within 2 h.
  - (b) Add `stars`, `tier_rank` and the two teams' bo3 ranks (from bo3 team endpoints at match time) to the frozen
    event logistic. Fit on BUILD and report VALIDATE AUC, gain over the activity baseline, recall and lift, per
    VALIDATE day (the replication rule).
  - (c) Point-in-time check. For development-unit matches only (gameStart in 11-01 06-12 or 18-24 UTC, filtered before
    printing), snapshot bo3 `stars`, `tier_rank`, `bet_updates` and the team ranks at T-3 h, T-1 h and after the match.
    Keep the feature only if the pre-match values equal the post-match ones, or use the pre-match snapshot as the
    feature. The examiner would then call bo3 for h1 events; store only the pre-match fields.
  - (d) Check that it holds on the new leagues: CyberClash and FiReSPORTS events of the development blocks.
- **Data.** bo3.gg API (verified, no key) and the Gamma event projection already on disk. It is cheap: about 400
  cached GETs.
- **Signature if true.**
  - Stars or team rank add at least +0.03 AUC over the current rule on VALIDATE in both days, with the gain's lower
    bound above 0.
  - Pre-match values are stable.
  - New-league events are scored correctly.
  - Selection then rests on a feed-coverage proxy, not a league list, which is what the h1 examiner can judge.

### 2. Book reader or slower feed: use the wallet's own client clock and the collapse's persistence (strong form of next step 2)

- **Hypothesis.** The client is fast: about 100 ms or less per round trip, with blocking calls and fixed 0.5 s and
  1.0 s sleeps (check A). So the 0.3-1.0 s lag is a rule or a channel, not latency. Two options:
  - (a) **Book reader with a confirmation rule.** It acts only if the collapse persists, that is, the depth is still at
    or below a fraction f of the reference, and the team's ask has not come down, at about Δ = 0.3-0.5 s, or at its
    next loop tick after its own cooldown. Most collapses heal within a few hundred ms as makers requote, which explains
    the 4-8% acted share.
  - (b) **Feed reader.** It receives the same game event as the cancelling makers, about 0.7 s later. The book's state
    at its signing does not matter beyond a stale ask existing.
- **Why it fits.**
  - The interval spike at 1,000-1,100 ms after its takers puts its latency well under 100 ms.
  - Acted collapses are deeper (remaining 21% vs 34% of the reference) and leave the best ask unchanged, which fits
    persistence.
  - It never acts when the ask fell, which fits a stale-ask filter.
  - In 4 of 32 orders it signs before the collapse, which would fit (b) if those are not artefacts of the 200-ms
    snapshots.
- **Test.** Dev blocks, own recorder `tommy_cs2_near` (ms, unthrottled within 5c) and decoded calldata. All CS2 markets
  of development-unit games; the BUILD and VALIDATE live split as pre-registered.
  - (i) For every collapse, compute three things:
    - persistence: the time until depth recovers above 0.5x the reference;
    - the depth and best ask at t + 0.3, 0.5 and 0.8 s;
    - the wallet's idle time: time since its last signing in the event, and whether a cooldown (0.5 or 1.0 s after its
      previous action) is still running.
  - (ii) Precision and recall of three acting filters, each fixed on BUILD:
    - "depth still at or below f at t + Δ, and the ask unchanged";
    - the same with the extra condition "no own cooldown running";
    - the RE's depth-left / ask-move filter.
  - (iii) Regress the lag on collapse speed (time from 90% to 50% depth) and on own idle time.
  - (iv) Phase: whether signing times fall at its previous action + k x 500 ms more often than at random.
- **Data.** Own recorder, calldata of the dev-block markets, and the wallet's orders. No new fetch.
- **Signature.**
  - (a) Persistence plus cooldown lifts precision from 4% to 30% or more at unchanged recall. The lag measured from the
    moment depth crosses f (or from the end of the cooldown) is tight, with an IQR under 100 ms. It never signs before
    the collapse, once the snapshot artefacts are removed.
  - (b) The lag does not depend on collapse speed or persistence. Some signings come before depth reaches its minimum.
    The acted collapses are not separable by book state. In that case the trigger needs the external feed (proposals
    3 and 4).

### 3. Event-wide cancel clock and canceller identity: who sees it first (new; Polymarket's own book plus calldata)

- **Hypothesis.** A few fast makers cancel first, and their cancel times across all markets of one game reveal the
  information root:
  - offsets within about 100 ms point to one push feed;
  - offsets of 0.3-2 s point to a cascade of book readers.
  The wallet either consumes the event-wide signal, firing even in thin markets without a local collapse, or only the
  local one. If one of the first cancellers shares an owner or funder with the wallet, the cancel-then-take order is one
  operator's internal sequencing: a private feed, with the "trigger" being its own pull.
- **Why it fits.**
  - Check C: 8 of 19 match-market collapses sit within 2 s of a same-team map collapse, against 1.34 expected, but
    with offsets of seconds.
  - 17 of 49 live taker orders had no local collapse (thin books under the 200-share reference, or Dota 2).
  - The pack's offsets between operators are 50-300 ms.
  - The owner check covered only 3 wallets (R5 / X14).
- **Test.**
  - (a) Extend the own recorder, for development blocks only and within its caps, to every market of the
    whitelisted non-GRID events: map totals, handicaps and pistol-round props, which makers also pull.
  - (b) Event clock = the first collapse in any market of the event. Report:
    - the distribution of cross-market offsets at ms resolution;
    - the wallet's lag relative to the event clock and to the local collapse;
    - the share of its local-collapse-free orders that have an event-clock collapse in the prior 2 s.
  - (c) Attribution:
    - match book level increases (token, price, size equal to the order's original shares, time = sign_ms + 30-500 ms)
      to calldata maker orders (maker address, price, original shares, sign_ms), which labels resting orders by owner;
    - attribute level decreases without trade at collapse times to labelled orders whose remaining size equals the
      drop.
    My rough tape-only version (`cancellers.py`) cannot separate collapse from control times; the book join is needed.
  - (d) For the top first-cancellers: owner(), the funding path of their deposit wallets (first USDC transfer
    in), activity in GRID events and pre-game.
- **Data.** Own recorder, public calldata of the event's markets (publicnode batches of 40), eth_call owner(), and
  Polygon transfer logs for funding.
- **Signature if true.**
  - A push feed: cross-market first cancels within 100 ms; the wallet's lag constant relative to the event clock; it
    fires in thin markets after a sibling's collapse, which recovers part of the 24% of taker orders that are not
    explained.
  - A book cascade: offsets of 0.3-2 s, and the wallet acts only after local collapses.
  - Operator: a first-canceller shares the funder or owner 0x8af810f0. The decisive input is then that operator's
    private feed, and the selection proxy is the canceller's coverage.

### 4. Event-locked stream clock with about 50 MB of video (strong, cheap form of X4; needs the user's consent)

- **Hypothesis.** The fast cancels come from a source that is either ahead of the broadcast by a constant D (server
  logs, GOTV/CSTV, a data provider), or behind it (low-latency stream reading). The 30-s lead of the informed takers
  over the market's repricing suggests the broadcast is deliberately delayed in these online tier-3 events, and that
  the root is server-side.
- **Why it fits.**
  - In-round information that reverses in 20-23% of cases.
  - The next jump comes a median 32-37 s after its taker orders.
  - The socket and bo3 give no round clock for non-GRID events.
  - Kick chat replay is empty (check 9), so no text-only historical stream clock exists.
- **Test.**
  - Download no whole maps. For about 40 BUILD taker orders and pack clusters in Kick-streamed events (DraculaN
    channels, kick.com/starladder, circuitx, nodwin_cs2), fetch only the 2-3 VOD segments at 160p whose
    `#EXT-X-PROGRAM-DATE-TIME` covers [t-25 s, t+10 s]. That is about 0.35 MB per 12.5-s segment, so 40-50 MB in all.
  - Decode 10 fps frames with ffmpeg into numpy. Use pixel-difference energy in the kill-feed crop and the
    alive-players / score crop; calibrate one PNG per channel.
  - Measure the offset from the stream's kill or score change to the wallet's signing and the pack's first signing.
    Measure the stream's round end against the tape's next ≥4c jump, which gives the market's stream lag.
  - Live variant: the same on one development-block map of the Kick live HLS, together with `tommy_cs2_near`, to tie
    the stream to the first cancel at ms.
- **Data.** Kick VOD playlists (public). Downloading video segments needs an explicit yes from the user, stating the
  file count, source and about 50 MB. The panel cannot grant it; the RE should ask in its return.
- **Signature if true.**
  - Signings and first cancels at a constant -D (for example -15 to -60 s) before the stream shows the kill or round
    end, with D constant per organizer: a server-side source.
  - A peak at +0.5 to +3 s after the stream's event: stream readers.
  - The tape's jumps at about +0-3 s after the stream's round end: the slow makers price from the stream.

### 5. Another venue's in-play price and a provider coverage flag (strong form of A4b; partly needs the user)

- **Hypothesis.** The first cancellers price off a sportsbook-grade feed. A venue whose market makers use the same feed
  moves before the Polymarket collapse, and that provider's "live supported" flag is the selection list.
- **Why it fits.**
  - SX Bet lists tier-3 CS2 leagues with CLOB trading, including FiReSPORTS, which the wallet trades since 10-31.
  - Polymarket lists events from PandaScore (`pandascoreMatchId`). PandaScore match objects carry `live.supported` and
    `live.opens_at`, a per-match live-data flag. Today that needs a token (403).
- **Test.**
  - (a) Find SX Bet's current order-book and trades API. The v2 paths answer 400 or 404, so read api.docs.sx.bet.
    Record its best odds for development-unit CS2 markets in dev blocks with a Writer-based recorder that has a hard
    stop. Lead-lag against `tommy_cs2_near` collapses.
  - (b) Ask the user whether they will provide a PandaScore free-tier token. Neither the RE nor the panel may create
    the account. With it, test `live.supported` as a pre-game selection feature on BUILD and VALIDATE, and check it
    point-in-time on upcoming dev-unit matches.
  - Record the other probes as infeasible with their responses (check 9).
- **Data.** SX Bet public API (listings verified); PandaScore REST only with the user's token.
- **Signature if true.**
  - SX odds move 0.2-1 s before the Polymarket first cancels in most of the matched events.
  - `live.supported` separates traded from skipped non-GRID events beyond stars and activity. That would be the
    selection rule's cleanest input and would carry over to new leagues.

### 6. Dota 2 as a natural experiment with a public server-state feed (new; small, cheap)

- **Hypothesis.** The operator uses public server-state feeds where they exist. Dota 2 has one: OpenDota `/api/live`,
  verified 200 with no key, carries scores and gold for live league games after Steam's spectator delay. In CS2 it
  would then use the CS2 equivalent, a scorebot or log feed, rather than the book.
- **Why it fits.**
  - The wallet trades Dota 2 (4% of maker-regime markets; 3 of 40 live taker orders).
  - None of those 3 had a book collapse before it.
  - Dota 2 is the one game where a public, timestamped game-state feed can be recorded on this laptop.
- **Test.**
  - During development blocks, poll `/api/live` every 3 s with a Writer-based recorder that has a hard stop. It is
    tiny.
  - Map games to Polymarket Dota events by team names and start time.
  - Lead-lag of the wallet's and the pack's Dota taker orders, and of the Dota book collapses, against kill and
    net-worth swings in the feed.
- **Data.** OpenDota live (public), the own recorder (add Dota match and map-winner markets), calldata.
- **Signature if true.**
  - Its Dota orders follow feed events by a short, constant lag: it consumes public server-state where it exists, which
    supports a feed (not the book) in CS2 too.
  - Orders that precede the feed by the spectator delay: real-time private access.
  - Orders unrelated to the feed: its Dota activity is book-driven like CS2.
