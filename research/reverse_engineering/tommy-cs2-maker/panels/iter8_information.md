# Panel, iteration 8: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-8, including the late additions and Z8), state.json (ledger, catalog A1-X117,
components, target metrics), FINAL_RULE.md and panels/iter7_*. There are no EXAM or wall-audit files.

All checks used development data only: 10-16..10-22 (before H), the cached OpenDota parses of the wallet's 10-22 Dota
maps, and the strategy's own `.cache/re/tommy-cs2-maker/` files. The block running during this panel (11-01 00-06) is
sealed, so no live Polymarket unit was touched. Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter8info/`:

- `probe_rt.py`, `probe_lg.py`, `probe_rt2.py`: key-free status of Valve's Dota live endpoints. Verified on a
  live league game whose team names appear in no Polymarket Dota listing (`universe_dota.parquet`), with 0
  spectators. Only field names and the update cadence were printed, no game content.
- `alone_killclock.py`, `alone_kinds.py`, `alone_dscan.py`: are the wallet's Dota takes without a co-signer on the
  feed's kill clock?
- `maker_killclock.py`: are the wallet's 10-share Dota maker orders signed on the feed's kill clock?
- `dota_poll_clock.py`: are the feed's Dota messages quantized to a 4-s snapshot grid?
- `p4e_dota2.py`: P4e's and the slow trio's Dota events, by league and GRID flag.
- `grid_feed2.py`, `grid_edge.py`: do the feed's slower subscribers co-receive inside GRID events, and what do they
  earn there?

## Critique: what the investigation is missing or getting wrong

1. **For Dota, the feed's clock is now known, and Valve publishes the state on that clock without a key.**
   - Finding 24 places the feed's Dota messages at the spectator delay: D_feed 1035-1050 s, `delay` 900 s.
   - The investigation still treats the feed as unobtainable. It records OpenDota `/live` every 15 s (X42 / X88),
     which is too coarse to time anything.
   - Verified here:
     - `https://www.dota2.com/webapi/IDOTA2League/GetLiveGames/v001` answers 200 without a key. It lists live league
       games with `server_steam_id`, `match_id`, `league_id`, team names and `time`.
     - `https://www.dota2.com/webapi/IDOTA2MatchStats/GetRealtimeStats/v001?server_steam_id=` answers 200 without a
       key: 10.5 KB, RTT about 10 ms.
       - `match`: timestamp, game_time, game_state, picks / bans.
       - `teams`: score, net_worth.
       - `players`: kill_count, death_count, assists_count, net_worth, gold, x, y, items, abilities.
       - Also `buildings`, `graph_data` and `delta_frame`.
     - Its snapshot advances every about 4 s (5 distinct `match.timestamp` values in 20 one-second polls).
     - The `api.steampowered.com` versions of the same calls return 403 (key required).
   - This is the first public, point-in-time input on the feed's own clock for any title. Dota is no longer marginal:
     it carried 54-57% of the wallet's fills on the 10-31 12-18 block.

2. **In Dota, the "alone" takes ride the same delayed clock; there is no real-time second source.**
   - Setup: wallet takes with no take by P4e, the slow trio or the other Dota co-signers within ±1 s on the same
     token, on the 10-22 maps, at each map's D_feed (`alone_kinds.py`, `alone_dscan.py`).

   | Takes | n | bought-team kill within 8 s before | other-team kill | nothing parsed within 8 s |
   | --- | --- | --- | --- | --- |
   | Alone | 27 | 8 (null 1.8) | 0 (null 2.3) | 17 (null 16.8) |
   | Co-signed | 25 | 16 (null 1.9) | 0 | 5 (null 16.2) |

   - A D-scan of the alone takes on their own peaks at D - D_feed = 0 to +3 s (7 vs 0 hits). Near -900 s, where a
     real-time source would sit, the scan shows nothing above the background (best 1 vs a p99 of 3).
   - So the alone takes that react to kills are the same feed's kill messages, and the other two thirds follow no
     parsed discrete event.
   - Q2 (an exclusive faster input) loses its main support in Dota. The residual looks like a private value computed
     on richer state (net worth, positions, fight development), which is exactly what `GetRealtimeStats` carries.
   - Caveats: small n, and D_feed was fitted on the same maps.

3. **The maker leg was never placed on an in-game clock. In Dota it can be, and it is on the feed's clock**
   (`maker_killclock.py`; filled 10-share maker orders, so this is a censored view).
   - Maker orders signed 0-6 s after a kill by the token's own team: 48 of 473 in the first 20 game minutes. The null
     (400 shifts of D by ±20-300 s) averages 25.3, its p95 is 40, and 0 of 400 shifts reach 48.
   - After a kill by the other team: 33 vs 27.5 (p 0.26).
   - The add rate per kill doubles to triples after the kill offset: about 0.05 per second before, 0.10-0.15 per
     second over the following 15 s.
   - Z4 has so far rested on markouts (X94 / X104 / X107). This puts the re-pricing input on a public game clock. The
     blocked price item (0.32) is therefore attackable in Dota with public state.

4. **"The boundary is the feed's coverage" is stated more strongly than the data allow, and Z8 does not explain it in
   Dota.**
   - In CS2 the slower subscribers co-receive inside GRID events (`grid_feed2.py`, data-api TRADE rows, 16-22 Oct):
     - 0xf1ee4842 and the 0x8a80528d process are different operators with different keys.
     - They take the same token within ±2 s in GRID events 63 times in 806 rows (60-120-s shift null 0.75). In
       non-GRID events: 163 in 1,852 (null 12.5).
     - They trade 73 and 61 GRID events. P4e, 0x2005d16a and the wallet trade none, P93 trades 8.
   - In Dota (`p4e_dota2.py`, 10-16..H), P4e's Dota events are exactly the wallet's 3 PARI Universe events; the slow
     trio has 4, all PARI Universe. None trades any of these, although DotaTV shows every ticketed league game:
     - 52 GRID-flagged events (EPL Masters, DreamLeague, BLAST Slam);
     - 10 non-GRID 1win Streamers League events.
   - So a public-relay reader (Z8 as written) would cover the biggest Dota leagues. Coverage alone does not explain
     why P4e and the wallet skip GRID events while two slower subscribers of a fixed-lag feed trade them.
   - Settlement returns (`grid_edge.py`, noisy, all CIs span 0):

     | Subscriber | GRID | non-GRID |
     | --- | --- | --- |
     | 0xf1ee4842 | -4.8% | +0.7% |
     | 0x8a80528d | -2.6% | -0.2% |
     | P93 | -3.5% | +3.1% |
     | P4e | (not present) | +2.8% |

   - The alternative the investigation has not tested: GRID events are where a faster, server-side official feed
     prices the market, so a spectator-clock feed is late there and its fastest subscribers abstain. That is a
     relative-speed boundary, not a coverage boundary. It matters for the forward exam: such a boundary moves when
     official data reach tier-3 events.

5. **The information effort is still aimed at selection and co-signing, while the blocking items are price (0.32) and
   outcome (-0.13).**
   - Selection already passes on VALIDATE (0.953 vs 0.886).
   - Every remaining gap needs the private value's input. For Dota, a public form of it now exists (critique 1). For
     CS2, the only tick-level route is the demos (X37), and the Dota per-map D-scan has now shown that the method
     works with 10-40 anchors per map.

6. **The feed's Dota messages show no 4-s snapshot grid** (`dota_poll_clock.py`; 145 clusters, 685 within-event pairs
   4-300 s apart).
   - Rayleigh maximum in [3.5, 4.6] s: p 0.50 (feed), 0.90 (P4e and wallet) and 1.00 (wallet), against a ±4-s jitter
     null.
   - So the vendor probably does not poll the 4-s web snapshot. It more likely reads the broadcast stream. A public
     1-s poller of `GetRealtimeStats` should then trail the feed by 0-4 s, which proposal 1 measures.

## Proposals (ranked by the chance that they close the gap)

### 1. Valve's key-free Dota spectator state as the public form of the feed's Dota half (strong form of X42 / X88 / X24; new data source)

- **Hypothesis.** The feed's Dota messages, and the wallet's Dota takes and ladder re-pricings, are reactions to the
  spectator-clock game state that Valve publishes on `www.dota2.com/webapi`. A recorder of that state reproduces the
  input at a measurable lag.
- **Why it fits.**
  - D_feed sits at the spectator delay (finding 24).
  - Alone takes are on the same clock (critique 2).
  - Maker adds follow kills on the same clock (critique 3).
  - The endpoints are key-free and carry kills, net worth, gold, positions and buildings per 4-s snapshot
    (critique 1).
- **Test.**
  1. A `Writer`-based recorder (`tools/live.py`), with a hard stop, under 100 MB of memory and 300 MB of disk,
     records filed by unit through `unit_writer` (sealed-start units always filed sealed), entered in `live_lab`:
     - poll `GetLiveGames` every 30 s;
     - for every live game matched to a Polymarket Dota event by team names, poll `GetRealtimeStats` every 1 s.
       Store the receive time, `match.timestamp`, `game_time`, `game_state`, team score and net worth, and the
       per-player kill / death / net-worth / x / y fields.
  2. First verify on a development block that league games of Polymarket events return data, and record the snapshot
     cadence.
  3. Pre-register, on development blocks only:
     - (a) the lag of each feed take (P4e, the wallet, the slow trio; from the block's public taker calldata, Dota
       markets included) behind the first snapshot showing the bought team's kill increment;
     - (b) the same for the wallet's 10-share ladder events on the recorded books (adds and cancels by size
       fingerprint);
     - (c) for takes with no kill increment, whether a net-worth or position change (two teams converging, a
       building) precedes them in the snapshot.
     - Verdicts:
       - a constant lag <= 1.5 s with IQR <= 1.5 s for >= 50% of kill-linked takes: the feed is (a reseller of)
         this state;
       - takes 0-4 s before the snapshot, spread like the snapshot cadence: the vendor reads the broadcast, and the
         snapshot is a public proxy with a known lag;
       - takes >= 10 s before the snapshot: a server-side source.
  4. As a by-product for selection, `GetLiveGames` lists every DotaTV-visible league game, so "coverage = public
     relay" can be tested directly against P4e's event set.
- **Data.** The two dota2.com webapi endpoints (verified), the shared `clob_wallets` books, and the block's decoded
  Dota taker transactions (`dota_cosign.py` pattern).
- **Signature if true.**
  - Kill-increment snapshots lead or trail the feed's takes by a tight, constant offset.
  - The ladder's re-pricing bursts sit 0-6 s after snapshots with a kill or a net-worth jump.
  - Takes without a parsed event line up with jumps in net worth or position.
  - That gives an executable, point-in-time Dota taker and pull rule, and a state input V(net worth, kills, game
    time) for the Dota ladder: the first public input for the price and outcome items. The examiner gets the recording
    through `iter_live`.

### 2. Rebuild the Dota ladder's price from the spectator-clock events (new: the maker leg on an in-game clock)

- **Hypothesis.** The 10-share Dota ladder re-anchors after each spectator-clock event. It raises its bids on the
  gaining team and pulls or lowers them on the other. The anchor is a function of game state, so the price item can be
  modelled from public state instead of from the touch.
- **Why it fits.**
  - Filled maker adds 0-6 s after own-team kills: 48 vs a null of 25.3 (p < 0.0025). Other-team kills: 33 vs 27.5.
    The add rate rises 2-3x after the kill offset (critique 3).
  - The own-state machines reach only 0.29 (X108) and the touch 0.47, so the missing part is an external re-anchor.
- **Test.**
  1. Retrospectively, now: take the 10-31 ty-gl development maps on the shared books (BUILD-live).
     - Use uncensored ladder events: adds and cancels of exactly 10 shares, plus ground-truth cancels.
     - Fit D per map from the feed's takes, or from the maker events themselves with a side-label null.
     - Get the kill and building logs from OpenDota parses.
  2. Classify each re-pricing burst: within 6 s of an own-team kill, an other-team kill, a building, or nothing.
  3. Fit the post-event ladder top as the touch plus k x ΔV, with ΔV from a pre-registered logistic of the net-worth
     lead and game time (BUILD-fitted). Score price_within_tick on VALIDATE-live against the touch.
  4. Then run an executable replay (strict fills, `match_slack=2`) for the Dota PnL correlation.
- **Data.** Recorded books (shared recorder, development blocks), OpenDota parses (key-free), and proposal 1's
  recorder for the live, point-in-time version.
- **Signature if true.**
  - >= 50% of Dota re-pricing bursts sit within 6 s of a spectator-clock event, against a shift null.
  - Event-signed bid moves: up on the gaining team, pull or down on the losing team.
  - The state-based anchor beats the touch by >= 0.1 within one tick on Dota orders, and the Dota replay's per-market
    PnL correlation rises above the 0.33 activity baseline.
  - If false, the event share of re-pricings is at the null, and the ladder's private value is not game state.

### 3. GRID events as a natural experiment: coverage boundary or relative-speed boundary (strong form of X5 / X102 / X117; new test)

- **Hypothesis.** The feed, or a feed with the same fixed-lag fan-out, also covers GRID events. P4e, 0x2005d16a and
  the wallet abstain because in GRID events a faster server-side official feed (GRID) moves the market before the
  spectator-clock messages arrive. The selection boundary is therefore where the feed is still the fastest source.
- **Why it fits.**
  - Two different operators of the slower group co-receive inside GRID CS2 events at 84x the shift null, at the same
    rate as in non-GRID events (critique 4).
  - In Dota, P4e and the trio skip every GRID-flagged league that DotaTV shows (critique 4).
  - The slower subscribers' settlement returns point negative in GRID events (noisy).
  - GRID markets its data as server-side, not broadcast-side (NOTES desk research).
- **Test.**
  1. **Feed presence.** Decode the public taker transactions (calldata) of the ~20 GRID CS2 events where 0xf1ee4842
     and 0x8a80528d co-take. Is their lag (+56.5 ms median, IQR 120 ms, in non-GRID events) the same there? Do the
     +150-ms group and the slow +500-ms group co-sign there at their fixed lags too?
  2. **Speed.** For the slower subscribers' takes, compare GRID and non-GRID events (event bootstrap, development
     events):
     - the public pre-move: the bought token's price change in the 10 s before the take;
     - the 10-s and 60-s markouts.
  3. **Dota clock.** Run the `dota_market_align.py` D-scan, with public anchors only, on EPL Masters / DreamLeague /
     BLAST Slam maps of 10-16..22. Map them to OpenDota match ids with `/proMatches` and team names. Compare
     D_market with the PARI Universe maps (D_feed + 3-14 s).
  4. Optional: the subscribers' activity from 10-01 to date the wallet's first fixed-lag co-sign. If it is 10-16,
     the regime switch is the subscription.
- **Data.** Public data-api activity and Polymarket tapes, Polygon calldata of GRID markets, and OpenDota
  `/proMatches` and `/matches` (key-free).
- **Signature if true.**
  - The same fixed lags in GRID events (same feed).
  - In GRID events, larger pre-moves in the take's direction and markouts near zero or negative (the market already
    moved).
  - In GRID Dota maps, D_market near start -> horn (real time) rather than delay + start -> horn.
  - Then the frozen selection rule should be restated as "no faster official-data seller for the event" (GRID today),
    and the forward risk flagged: the boundary moves when official data reach tier-3 events.
- **Signature if false.** No fixed-lag co-signing inside GRID events once calldata are decoded (a different source
  there). The coverage reading then stands.

### 4. Co-receiver makers as wallet-independent witnesses of the messages behind the alone takes and the untriggered pulls (new; Polymarket's own book feed as the instrument)

- **Hypothesis.** Other makers on the same feed cancel or re-price on its messages before the wallet's own pull can be
  visible to them. Their presence or absence at the wallet's alone takes and untriggered re-pricings tells whether
  those moments carry a feed message that others also receive (kind filter at the takers) or an exclusive input.
- **Why it fits.**
  - The cancel wave at its takes starts a median 51 ms after signing, p25 at +14 ms (A7). Its own pull lands at
    +11-19 ms (X49), so some non-own cancels are too early to be followers.
  - At pack-only events, 57% of its pulls come after the first non-own cancel (X78 / X80), so co-receiver makers
    exist.
  - The iteration-7 critique counted followers only after untriggered pulls ("nothing in the first 10 ms"). Nobody
    has looked before them.
- **Test.**
  1. On BUILD-live (and VALIDATE-live from 11-01 06-12), on all books of the event, count non-own cancels and price
     changes in (-150, -60], (-60, 0] and (0, +8] ms around:
     - co-signed takes and alone takes (co-sign status from the block's public calldata);
     - validated untriggered pulls;
     - random busy-phase times.
     Use within-book time shifts as the null.
  2. Attribute those events to makers by size fingerprint and ground-truth remainder cancels (`cancel_truth.py`).
  3. Confirm each such maker is a feed subscriber through its fixed lag at P4e-only events (X115, when P4e trades a
     recorded book) or at its own co-signed takes.
- **Data.** The shared `clob_wallets` books, the dev-block calldata, and `gt_cancels_dev.parquet`. Nothing new to
  fetch.
- **Signature if true** (one feed, kind filter): the pre-visibility co-receiver rate is the same at alone and co-signed
  takes, and above the null at untriggered pulls.
- **Signature if false** (exclusive input): co-receivers fire at co-signed takes only, and the alone takes and
  untriggered pulls are silent before +10 ms. The alone CS2 takes are then a second source, to be named.

### 5. The CS2 game clock: the Dota protocol on CS2 demos (strong form of X37, which was never run)

- **Hypothesis.** In CS2 the feed also rides a spectator clock: CSTV+ at tv_delay plus about 24 s, or the organiser's
  broadcast. The per-map offset, the event kinds of the alone takes (plants, per `census_p4e_types`) and the maker
  re-pricing triggers can all be read from tick-level demo events, as in Dota.
- **Why it fits.**
  - The Dota D-scan with a side-label null reached p < 0.005 per map with 10-40 anchors.
  - CS2 maps carry 20-60 feed take clusters each.
  - No other CS2 clock exists: bo3 has no kill times, the sports socket has map scores only, HLTV is blocked.
  - The fragment-clock test (finding 25) excluded fragment-arrival readers, not real-time players of the delayed
    relay.
- **Test.**
  1. Choose 6-10 traded non-GRID maps of 16-22 Oct: half rich in P4e plus wallet clusters, half dominated by alone
     takes.
  2. Parse kills, plants, defuses, round ends, freeze-end and equipment values at tick times.
  3. Per map, scan D for:
     - the co-signed anchors;
     - then the alone anchors (D - D_feed ≈ 0 is the same feed; a separate peak is a second clock);
     - then the filled maker orders.
  4. Classify the kinds within 0-6 s of each take.
  5. To identify the relay: if an organiser's playcast URL is public, its `/sync` JSON (tick, `rtdelay`, `rcvage`,
     fragment) gives the relay delay against the server directly (X117).
- **Data.** Demos (50-300 MB each) via the bo3.gg match page's download link as a normal visitor, or HLTV through the
  user (X64), plus a demo parser from PyPI. **Needs the user's explicit consent** for both downloads and the install.
- **Signature if true.**
  - A sharp per-map offset with bought-team events (plants, the decisive kill), identical for P4e and the wallet.
  - Alone takes on plants at the same offset.
  - Maker re-pricings after round-state changes.
  - That gives the CS2 counterpart of proposals 1-2, and quantifies the feed's lead over the stream-watching market
    for the wall account.

## Ranking note

Proposals 1 and 2 attack the two items that block the target (price and outcome) with public point-in-time data, in
the title that now carries most of the fills. Proposal 3 decides what the selection boundary means, which is the
component most exposed to forward drift. Proposal 4 settles Q2 for CS2 without new data. Proposal 5 is the most
decisive CS2 dataset, but it waits on the user.

## Sources (desk research, normal-visitor web search)

- [PARI Universe 2026 (esports.ru)](https://esports.ru/dota-2/tournaments/pari-universe-2026/): FISSURE-organised;
  broadcast on the organiser's Kick channel; no data partner found.
- [Oddin.gg in multi-year partnership with PGL (AGB)](https://agbrief.com/news/world/24/04/2024/oddin-gg-in-multi-year-partnership-with-esports-tournament-organizer-pgl/)
- [Stake and StarLadder partner to launch Stake Ranked (StarLadder)](https://starladder.com/en/news/stake-and-starladder-partner-to-launch-new-cs2-lan-tournament-series):
  no official data partner named for Stake Ranked or 1win Private Club in the results found.
