# Panel, iteration 11: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations (E1 own model on Feed P's raw events, E4 an in-play odds product).

## What I read and what I ran

I read BRIEF.md; NOTES.md (iteration 11 in full, iterations 1-10 by section, with the late additions on Feed P, the
Dota clock and the quote level); state.json (catalog A1-X157 with evidence, components, target metrics, data sources,
live lab); FINAL_RULE.md by section; panels/iter10_information.md in full; the earlier panels by grep for every source
named below. There are no EXAM or wall-audit files. `tools/sealed.py tommy-cs2-maker`: no released lots, future
examined up to 10-31 00:00; the current block 11-01 06-12 is development.

Checks (scripts in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter11info/`:
`xevent_sync.py`, `burst_period.py`, `loop_phase.py`, `loop_share.py`, `loop_others.py`; three more ran inline). Each
stayed under 300 MB and 10 minutes.

- On-chain, development only: `orders.parquet` (the wallet's 24,180 filled maker orders and 1,698 taker orders, every
  signing time before H) and `calldata_pub/` (99,375 maker orders of 1,807 other makers in the wallet's CS2 markets,
  16-22 Oct, signed before H).
- Live, development only: `own_bursts_dev.parquet` (2,998 own add / pull bursts on the server receive clock, the
  BUILD-live block 10-31 12-18). Nothing in `.cache/live/sealed/` was opened and no recording was read.
- Web, as a plain client with default headers (nothing bypassed): Sofascore's esports schedule for 10-20 (403, no data
  returned); cyberscore.live, escorenews.com, egamersworld.com (403, Cloudflare); hawk.live (200; its home page lists
  current Dota 2 matches, and I printed only the URL slugs, which name teams and tournaments, no scores, odds or
  outcomes); gosugamers.net and flashscore.com (200, status only); Kick's channel API for one resolution-source
  channel, `kick.com/api/v2/channels/stake_pulse` (200, key-free; I printed the first 200 characters: ids, slug and an
  Amazon IVS playback URL; no playlist or video was fetched) and `api.kick.com/public/v1/channels` (401).

## Critique: what the investigation is missing or getting wrong

### 1. The quiet class has a decision clock, and nobody found it: a single ~504-ms loop for all events

The wallet's maker engine re-quotes on one free-running loop with a period of about 504 ms, shared by all events.
Its takes are off the loop.

| Check (development data) | Result |
| --- | --- |
| Pairwise Rayleigh, own maker bursts of the same event 20-300 s apart (n 249,247 pairs), 490-520 ms grid | best P 504.25 ms, R 0.0285 against a grid median of 0.0028 (Z about 200) |
| The same across DIFFERENT events (n 375,383 pairs) | best P 504.00 ms, R 0.0222 against 0.0022: one phase for all events |
| Top 25 other makers in its markets (calldata_pub), same scan | none has a peak above the max-of-grid noise level (2-3x the median, against the wallet's 16x); the cross-phase with the wallet at 504.1 ms sits at the grid median for most (largest: the slow trio 0xfe8a28be 0.012 / 0x2529c68d 0.010 against about 0.0045, consistent with message co-timing) |
| Consecutive-burst intervals, all events pooled, 10-ms bins | [500, 510) 108 against about 45 in the neighbouring bins; [1000, 1010) 133 vs 55; [1510, 1520) 68 vs 35; [2010, 2020) 76 vs 32; [2520, 2530) 60; [3020, 3030) 66 |
| Phase lock to the tick predicted by the previous own burst (within +-10 ms, uniform 4.0%) | quiet maker bursts 9.3% (n 5,950); taker orders 4.3% (n 369): takes are event-driven |
| Live server clock (own_bursts_dev), within +-15 ms of the predicted tick (uniform 6.0%) | untriggered adds 31.6% (98), untriggered pulls 29.2% (89); triggered adds 10.9% (969), triggered pulls 11.3% (734); [500, 510) holds 211 intervals against about 90 |

What follows:

- **The iteration-10 mechanics panel's negative check ("no hidden periodic requote clock") is a false negative.** It
  tested exact round periods (100-10,000 ms) with one absolute phase over a whole event. The true period is 504 ms,
  not 500. Within 120-s windows the leave-one-out phase residual is a broad bump about +-60 ms wide (only 5.9%
  within +-10 ms against 4.0% uniform, while consecutive intervals are sharp to 10 ms), so the phase drifts like a
  random walk. That is the signature of a
  `setTimeout(500)` chain with about 4 ms of work per pass, in a Node / TypeScript client, which fits the salt
  fingerprint (C8). Only a relative-phase (pairwise) test sees it.
- **The "hard 1.5-s re-post timer" (X79, finding 13 of iteration 6) is three loop ticks (1,512 ms).** The shared
  1.5-s re-posts in other bots' markets (X79 step 4) are probably other loops or other libraries, because no maker in
  its markets shares the wallet's 504-ms phase.
- **No blocking poll sits inside the loop.** A synchronous HTTP call per pass would add tens of ms of variable RTT and
  blur the period. Whatever moves V between messages is pushed into memory asynchronously. That excludes a "poll an
  odds API every tick" form of E4. Cross-event synchrony is small: 0.30% of quiet bursts have a burst of another event
  within 5 ms, against 0.08% under per-event shifts. So in the filled record a tick almost never re-prices two
  events at once.
- **The trigger windows used for the quiet class are the wrong unit.** X63 used 50 ms before a burst, crossbook_sync
  +-40 ms, and X94 / finding 16 short windows. If the quiet re-pricings are loop samples, whatever changed V happened
  anywhere in the previous tick interval (up to 504 ms), and the "untriggered" label (no public trade in 2 s) says
  nothing about non-trade inputs in that interval. The quiet class is 70.6% of its filled orders, and its input has
  never been searched at the right unit (proposal 1).

### 2. "Its own valuation" is a residual category, not an identification

The iteration-11 statement ("its level is a private, informed, event-coherent value") records what failed: SX, a
fresh touch, co-receiver increments, game state at Dota's true clock. It does not say which input moves V between
messages. In CS2 every candidate content source is either consent-bound (demos X122 / X37, video X4 / X22, HLTV X64,
PandaScore X55, bookmaker probes X48 b) or live-only (X133 / X144 Thunderpick via bo3, X118 Valve). The first two exam
lots (h1 / h2) are historical and have tapes, calldata and bo3's round records, nothing else. One historical,
key-free CS2 state source exists and has been used only in weak forms: bo3.gg's per-round records (round_duration,
end_reason, winner side, equipment values, loss bonus).

- Iteration 1 aligned them with one global (offset, gap) per map, and pauses broke it (13 of 109 maps).
- Iteration 2 (X10) aligned P4e's taker clusters, which are mostly in-round events, by timing only.
- Nobody aligned the signed public round-end jumps with a pause-aware DP, so economy was never tested as a V input.
- **X2 was "rejected" on 14.1% of maker signings within 15 s after a round-end proxy against 8.1% at random.** That is a
  1.74x enrichment, evidence for re-pricing at round boundaries, not against it. It is the buy phase, when economy
  becomes visible.

### 3. E4's pre-registered tests miss the most distinctive behaviour of an odds product

`tp_valuation_tests.py` scores Thunderpick levels against filled orders (censored), plus one event-time test on fill
price changes. Two things are missing:

- **Suspensions.** An odds product suspends at plants, round ends and map ends. A copier withdraws event-wide for a
  variable time and returns at a new level. An own-model maker only shows the fixed 3-tick hole after a pull. The
  recorder already stores Thunderpick's `active` flags (a1, a2), and nobody uses them.
- **The loop lag.** With an odds input sampled by the loop, a V change follows an odds change by U(0, 504 ms) plus the
  relay lag. The 6-s window of test 4 is right in size, but test 5 (cross-correlation of 5-s changes) cannot resolve
  it.

### 4. The stream side is measured on Twitch only, though 69% of the traded events are on Kick

Resolution sources of the 384 events of 16-22 Oct: kick.com 244 (53 traded), twitch.tv 101 (23 traded), hltv.org 39
(1 traded). So Kick carries 53 of the 77 traded events. The chat recorder covers
Twitch only. Kick chat waits for the user (X38), and Kick video needs consent (X4 / X22). But Kick's channel API is
key-free (verified above) and returns the IVS playback URL. IVS media playlists are text with a
`#EXT-X-PROGRAM-DATE-TIME` per segment, so the stream's encoder clock and edge latency can be recorded without
fetching any video. "Speed against stream watchers" has never been tested as a dose-response (proposal 5).

### 5. Second venues: only half of the class is closed

SX is closed with a measurement (sparse, follows Polymarket). Azuro was closed as "infeasible" on its subgraph's DNS
and 404s (X41). Its contracts were never read on chain, although the iteration-10 panel proposed exactly that and the
Polygon RPC is already in use. Azuro is the larger on-chain esports book. A professional in-play line with a
historical, examinable record would be the only external price for h1 / h2 (proposal 4).

## Proposals (ranked by the chance that they close the gap)

### 1. The 504-ms loop as the decision clock: tick-level attribution of what moves V between messages (new)

- **Hypothesis.**
  - Quiet re-pricings are samples of an in-memory value V taken at the wallet's own loop ticks. The quiet ledger
    class is 70.6% of its filled maker orders; on the live book, 15% of its own bursts are untriggered by the
    `own_bursts_dev` definition.
  - Event-driven actions (takes, take-time pulls, the immediate reaction to messages) bypass the loop.
  - So each on-tick V change has its cause in the preceding tick interval. The cause is one of:
    - (a) non-own changes on another book of the event, sampled up to 504 ms late, which the 40-50-ms windows miss;
    - (b) Feed P messages of kinds no subscriber trades;
    - (c) a clock-driven in-round model (round timer, bomb timer);
    - (d) a pushed odds stream (E4).
- **Why it fits.**
  - Critique 1: the loop is sharp (Z about 200), shared across events, wallet-only, and holds about 30% of untriggered
    live adds and pulls within +-15 ms of the predicted tick against 6% uniform, while triggered actions sit near
    uniform.
  - The quiet class carries most of the price gap (last print 0.375 there).
  - It carries outcome too. Re-pricing the quiet class at the last print costs 0.15 Spearman alone, and 0.36 together
    with the follow class (X151).
- **Test** (BUILD-live first, then each development block with wallet activity).
  1. Phase tracker. Run a phase-locked loop (Kalman on the residuals of consecutive untriggered own actions, all
     events pooled, period free around 504 ms, tolerance +-15 ms on the server clock after the known receive offset).
     Label every own add and pull as on-tick or off-tick. Validate: taker orders and take-time pulls must be off-tick.
     On the historical record, the same labels from signing ms (sharper: client clock).
  2. Attribution. For every on-tick action where its top level on a token changed, list everything observable in
     (tick - 504 ms, tick - 5 ms]:
     - non-own level changes on the same book and, separately, on each sibling book;
     - public trades;
     - its own fills and merges;
     - group-P / P4e signings (calldata) and its own off-tick actions;
     - Valve / bo3 / chat records when present.

     Controls: on-tick moments of the same event and phase where V did not change. Fit a conditional logit by event.
     Report the share of V changes with no observable change in the interval.
  3. The unexplained residue:
     - sign persistence of consecutive on-tick dV per token (run lengths against shuffled signs);
     - dV as a function of time since its last off-tick action;
     - the step-size distribution (1c drift against multi-cent jumps).
  4. Off-tick own actions with no take of its own are wallet-visible message arrivals, including kinds nobody trades.
     - Count them per round and regress on bo3's per-round kills, first kills and plants (map fixed effects, as X50),
       and compare with group-P message counts.
     - On the historical record do it with filled-order censoring stated.
  5. If (a) dominates, score a tick-sampled follower (V_tick = others' best moved by the sibling's change since the
     last tick, mapped through the series sensitivity) within one tick on quiet adds, against the touch (0.45 adds).
- **Data.** `orders.parquet`, `calldata_dev` / `calldata_pub`, `own_bursts_dev`, `tommy_cs2_near` raw book,
  `tommy_tp_odds2`, `tommy_dota_rt`, bo3 per-round stats (all in hand or recording).
- **Signature if true.**
  - (a) At least half of on-tick V changes have a same-sign non-own change on a sibling or the same book in the
    previous tick. The quiet class is then a sampled reaction to public book state, and the follower beats the touch
    by 0.05 or more.
  - (b) Off-tick no-take actions per round rise with bo3 kills (slope at least 0.5 per kill, p < 0.0025), which
    names the event kinds of Feed P.
  - (c) Unattributed changes run in same-sign sequences of 3 or more ticks at 2x or more the shuffled rate, with
    direction set by time since the last message: a clock-driven in-round model.
  - (d) Unattributed changes are multi-cent steps at irregular times, coincident with the other makers' synchronous
    re-pricings (finding 13): a pushed odds stream.

  Each outcome closes a branch of "own valuation". (a) also gives an examinable live price input.

### 2. A suspension fingerprint for E4, independent of Thunderpick's level (strong form of X144)

- **Hypothesis.** If V is a pushed odds product (E4), the wallet inherits its suspensions. At plants, round ends and
  map ends it withdraws every level on every book of the event for a variable time, then re-posts at a new level.
  Under E1 the only holes are the fixed 3-tick (1,512-ms) re-posts after its own pulls.
- **Why it fits.**
  - Critique 3.
  - Thunderpick's `active` flags are already recorded and unused.
  - The holes in its "patchy presence" were explained as the 1.5-s timer, which is now three ticks of the loop (a
    mechanism, not a suspension). Anything left over is unexplained.
- **Test.**
  1. On the raw BUILD-live book and every development block, define event-wide withdrawal episodes: no own level on
     any book of the event for at least 2 ticks, inside its session, while the event is in play.
  2. Report:
     - the duration distribution (mass at exactly 3 ticks against a broad tail);
     - onsets relative to its off-tick actions, its takes and others' cancel waves;
     - the level change at re-post.
  3. Coincidence with Thunderpick suspensions (a1 or a2 false in `tommy_tp_odds2`, at the faster of the B / P series):
     the share of episodes overlapping a suspension, against 2,000 within-match circular shifts.
  4. A loop-aware version of X144 test 4: the lag from each p_TP change to the first on-tick change of its top, against
     shifted p_TP changes.
- **Data.** `tommy_cs2_near` raw book with snapshots, own-label validation (X92), `tommy_tp_odds2`, calldata of the
  development blocks.
- **Signature if true** (E4). Variable-length event-wide withdrawals (median 3 s or more, not quantized at 3 ticks)
  that overlap Thunderpick suspensions at 3x the null or more, with re-posts within one tick of the post-suspension
  p_TP minus the fitted margin.
- **Signature if false.** Withdrawals are quantized at 3 ticks and follow its own takes and pulls, with no Thunderpick
  coincidence. E4's suspension prediction then fails, independently of the 15-s cache problem of bo3's relay, which
  limits the level tests.

### 3. A historical in-round clock and economy from bo3, aligned to signed public jumps with pauses (strong form of X2 / X8 / X10)

- **Hypothesis.** Part of V's quiet component is round-level state the stream shows only at the buy phase and the
  market prices slowly: both teams' equipment value, loss bonus and the score state. bo3 records it for every
  development and exam match. A pause-aware alignment of bo3's rounds to the public tape gives a point-in-time
  round clock for h1 / h2, the only examinable CS2 state input.
- **Why it fits.**
  - Critique 2.
  - The 1.74x round-boundary enrichment of maker signings.
  - Iteration 1's global alignment failed only on pauses.
  - Round-end jumps, signed by bo3's winner, are the largest public moves on map markets.
- **Test.**
  1. Per map, run a DP over rounds. Gap(k-1 -> k) = restart + freeze + round_duration_k + pause_k, with pause_k >= 0
     sparse (a penalty per pause). The emission is a public taker move of at least 3c within 20 s after the predicted
     end, in the bo3 winner's direction, at block time with the wallet's own prints excluded.
  2. Controls: permuted winners and permuted durations. Keep maps with at least 70% of rounds linked.
  3. Rebuild the round start (end - duration) causally: no pause is assumed until the next jump confirms one.
  4. On the true clock, redo the iteration-1 boundary test by phase (buy phase, early round, late round, post-plant
     rounds via end_reason).
  5. Regress the wallet's offset (its first maker level after freeze end minus the last print) on the equipment
     differential, loss bonus and score state.
  6. Fit a round-state plus economy Markov anchor on BUILD maps. Score it within one tick on VALIDATE against the last
     print, under a point-in-time rule: results at their jump, equipment at freeze end plus 5 s, the delay the brief
     allows for plays.
- **Data.** bo3 `/games/<id>/rounds` (cached for 91 maps; fetch the rest of 16-22 Oct), data-api tapes and calldata
  (in hand). `evaluate()` can fetch bo3 for the examiner's lot.
- **Signature if true.**
  - At least 60% of maps lock against 20% or less under permutation.
  - The buy-phase offset correlates with the equipment differential beyond the score (|Spearman| >= 0.15, event
    bootstrap CI excluding 0).
  - The anchor gains at least +0.05 within one tick over the last print on VALIDATE.

  That is a decoded V input that exists for h1 / h2.
- **Signature if false.** Locked maps show no economy dependence. Economy is then not a V input the market misses,
  and the historical price item is bounded by the last print with this source closed too.

### 4. Azuro on chain: a professional in-play line with a historical, examinable record (strong form of X41)

- **Hypothesis.** Azuro's esports odds come from a professional provider, and many tier-3 CS2 matches trade in play
  there. Every bet carries the odds it was accepted at, on chain, with the block time. If in-play bets on the
  wallet's events are dense enough, the provider's de-margined line is a historical E4 candidate and the only
  external price that h1 / h2 could use. Azuro is the larger on-chain esports venue. SX's sparseness does not carry
  over by assumption.
- **Why it fits.**
  - Critique 5.
  - X41 failed on API hosts, not on the chain.
  - The iteration-10 panel's contract route was never run.
  - The SX decoder pattern (calldata + summary logs) is already written.
- **Test.**
  1. Read Azuro's deployed core and live contract addresses on Polygon (and Gnosis / Base, if Azuro's esports live
     market sits there) from its own toolkit package as text, without installing anything.
  2. Verify one bet event against a receipt.
  3. Pull bet logs for blocks stamped 10-16..10-22, clamped below H with `is_sealed` on block times.
  4. Map conditions to games through the on-chain condition creation data, or through a game-id listing if any
     endpoint answers. Keep CS2.
  5. Measure on the wallet's traded events (as for SX):
     - in-play bet density per map;
     - the de-margined implied probability against the wallet's latest bid and the last print (SD, within 1c);
     - the lead-lag of odds changes against Polymarket prints and P4e messages.
- **Data.** Azuro toolkit source (text), Polygon or Gnosis RPC logs, the wallet's calldata, tapes.
- **Signature if true.** At least one in-play bet per minute on the wallet's maps, and an implied probability within
  1-1.5c of its level (after a level-dependent margin) more often than the last print is, or leading the print after
  messages. That gives a historical price input for the examinable rule.
- **Signature if false.** Sparse, or it follows Polymarket. The second-venue class is then closed on chain for both
  venues, which completes E4's historical account.

### 5. Kick's stream clock without video, and a dose-response test of "speed against stream watchers" (strong form of X4's metadata half and X86)

- **Hypothesis.** The wallet's informed edge is its feed's lead over the stream that the market's takers watch. Per
  event, that edge should scale with the stream's latency: platform, IVS latency mode and organiser delay.
- **Why it fits.**
  - Critique 4.
  - The Dota market sits 3-14 s behind the feed on kills (finding 24 of iteration 8).
  - Kick events show a weakly higher led / near share than Twitch (X86).
  - The Kick API answers key-free with the IVS playback URL. Playlists are text and carry the encoder clock.
- **Test.**
  1. A recorder (Writer, unit-rule filing, hard stop, under 50 MB) for the Kick channels of development-start CS2 /
     Dota events in play. Every 2 s it stores each media playlist's newest `PROGRAM-DATE-TIME`, the segment duration
     and the receive time. No segment is fetched.
  2. Per event, compute the edge latency (receive time minus the newest PDT) and its changes, which flag organiser
     delay changes and stream restarts.
  3. Across events, take Spearman of the wallet's per-event lead metrics against the stream latency:
     - the next-jump gain of its takes;
     - the 10-s markout of its untriggered adds (finding 14);
     - its maker pair margin.
  4. Also measure the lag from its off-tick actions to the market's public jump.
- **Data.** kick.com channel API (key-free, verified), IVS playlists (text), recorded books, calldata. Video download
  (X4 / X22) and Kick chat (X38) stay with the user's consent.
- **Signature if true.** The edge metrics rise with stream latency (Spearman >= 0.4 over at least 15 events), and the
  market's lag behind its messages tracks the stream latency at a fixed offset. The economic mechanism is then speed
  against stream watchers, measured with a public, per-event, point-in-time covariate the outcome item can use.
- **Signature if false.** No dose-response. The edge is then model quality, not feed speed, which points back to
  proposals 1-3 for V's content.

## Ranking note and overlap

- Proposal 1 is first because it uses data already in hand, rests on a new and very strong regularity (the loop), and
  turns "own valuation" into four measurable branches. Branch (a) would also give a live price input.
- Proposal 2 is the cheapest decisive test of E4 that does not depend on bo3's 15-s cache.
- Proposal 3 is the only route to an examinable CS2 state input for h1 / h2 without consent.
- Proposal 4 is the last unread historical external price.
- Proposal 5 explains the mechanism more than it closes a metric.
- Not proposed again: PandaScore (X55, the token is with the user; its live socket against P4e's signing would be the
  identity test once a token exists), demos, video, HLTV, bookmaker frontends. The consent items, ordered by
  information value per unit of user effort:
  1. a free PandaScore token (coverage and identity);
  2. demos (the only historical in-round state for h1 / h2);
  3. Kick chat and video.
- Correction for the mechanics side: the "no hidden periodic requote clock" negative check of the iteration-10
  mechanics panel should be withdrawn, and the 1.5-s timer re-read as three loop ticks. The slot classifier of X150
  may also gain from tick counts since its own pulls: the re-post at the same price comes exactly three ticks later.
