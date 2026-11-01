# Panel, iteration 8: assumption breaker (fresh eyes)

## What I read and what I ran

I read BRIEF.md, the dossier entry in strategies.json, NOTES.md (iteration 8 in full, iteration 1 and the headings and
key findings of iterations 2-7), state.json (catalog A1-X117, ledger H1-H99, components, splits), FINAL_RULE.md and
panels/iter1-7. There are no EXAM or wall-audit files. Calendar (`sealed.py tommy-cs2-maker`): no released lots; future
examined to 10-31 00:00. I used only data from before H (16-22 Oct calldata and taker tapes in
`.cache/re/tommy-cs2-maker/`) and the BUILD-live tables the reverse engineer already built from the 10-31 12-18
development block (`linked_adds_dev`, `level_events_dev`). Nothing sealed was opened. I wrote nothing in the workspace
except this file. My scripts are in the session scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`grid_subscribers.py`, `grid_subs_tier.py`, `grid_subs_pit.py`, `alone_vs_cosigned.py`, `alone_vs_cosigned_nosub.py`,
`queue_rules.py`).

Checks, so nobody redoes them:

1. **The 19 "fixed-lag subscribers" are two populations with different coverage** (`grid_subscribers.py`,
   `grid_subs_tier.py`; taker-windowed tapes of all 384 CS2 events of 16-22 Oct, 37,894 subscriber BUY prints, block
   time).
   - P4e, 0x2005d16a and the slow trio (0xfe8a28be, 0x72aaaaf9, 0x2529c68d) almost never trade a GRID event: P4e 0,
     0x2005d16a 0, the trio 16-18 prints each, against about 1,800 each in non-GRID events. I call this group P.
   - The +100-230 ms group (0x8a80528d, 0xddb6e624, 0xf1ee4842, 0xe8e086f7, 0xc7097421, 0x14e72e19, 0x67706ec3,
     0x42a1b2b4, 0x775d9de0, 0x7c8cc255, 0xbb8ef638, 0xfca6d645, ...) trades GRID events heavily: 8,613 prints in 103 of
     the 122 GRID events. I call this group G.
   - In GRID events group G co-prints with another subscriber on the same token within 2 s 63% of the time (shift null
     5.5%). It is informed there, not late: 10-s markout +2.8c, 60-s markout +3.1c (median +1.2c), 10-s pre-trend
     +0.13c. Per wallet, the GRID 60-s markout is at least the non-GRID one (for example 0x8a80528d +1.8 vs +1.1c,
     0xbb8ef638 +8.4 vs +6.8c).
   - Event presence by class:

     | Class | Events | Wallet traded | Group P present | Group G present | Wallet traded, given P present | Wallet traded, G present without P |
     | --- | --- | --- | --- | --- | --- | --- |
     | GRID | 122 | 0% | 1.6% | 84.4% | 0% | 0% |
     | non-GRID tier 3 | 22 | 90.9% | 100% | 100% | 90.9% | n/a |
     | non-GRID tier 4 | 96 | 51.0% | 65.6% | 89.6% | 77.8% | 0% |
     | non-GRID tier 5 | 144 | 5.6% | 4.2% | 65.3% | 50% | 5.7% |

     In-event presence (a diagnostic, not point-in-time) separates the wallet's events with AUC 0.944 for log1p
     group-P prints and 0.793 for group G.
2. **A point-in-time group-P coverage feature beats the pooled one and P4e alone** (`grid_subs_pit.py`). The feature
   counts distinct group-P wallets with a print in another event of the same league in [gs - H, gs), before gs. Raw
   AUC on VALIDATE (CS2 only, 128 events, 36 traded):

   | Feature | VALIDATE AUC | AUC inside non-GRID events | Recall / lift at > 0 | GRID events with > 0 |
   | --- | --- | --- | --- | --- |
   | group P, 72 h | 0.917 | 0.871 | 0.972 / 2.44 | 8.2% |
   | group P, 24 h | 0.899 | 0.858 | 0.917 / 2.44 | 6.6% |
   | P4e only, 24 h | 0.806 | 0.788 | 0.667 / 2.94 | 0% |
   | all 19 pooled, 24 h | 0.854 | 0.841 | 1.000 / 1.07 | 91% |
   | pre-game prints (single feature) | 0.869 | | | |

   Caveat: I fixed group membership by looking at the GRID / non-GRID split over all of 16-22 Oct. The reverse
   engineer must fix it on BUILD only (proposal P1).
3. **The "alone" takes are the same module on smaller events, not a second input** (`alone_vs_cosigned_nosub.py`). The
   test uses the 1,567 take clusters of 16-22 Oct and the iteration-8 co-sign windows: 38.5% are co-signed in any
   market of the event. Markouts come from non-wallet fills. I removed the subscribers' own take transactions, so the
   followers' impact is not counted.
   - Co-signed: +3.0c at 10 s [2.2, 3.8], +4.4c at 60 s [3.3, 5.4], +5.7c at 300 s; FAK premium over the last print
     2.5c.
   - Alone: +1.6c at 10 s [1.0, 2.1], +3.2c at 60 s [2.3, 4.1], +3.3c at 300 s; premium 1.6c.
   - Both classes pay about half the 60-s move as premium (0.51 / 0.58). The alone takes are informed, and the market
     learns their information slowly (by 60 s, not 10 s). With the subscribers' prints included, the co-signed
     10-s markout rises to +4.9c: part of the "co-signed" effect is the followers' own impact.
   - Odd sizes and the 1000 / 2000 caps behave alike inside each class.
4. **The deep ladder group is not a queue-position choice** (`queue_rules.py`, BUILD-live, 2,738 validated own adds,
   my own crude book replay from `level_events_dev`; 7% of my snapshots are crossed, and my touch scores 0.418 where
   the reverse engineer's scores 0.472). Within one tick:

   | Rule | Within one tick |
   | --- | --- |
   | touch | 0.418 |
   | ask - 1c | 0.267 |
   | 1c above the largest wall within 8c | 0.311 |
   | highest empty level at or below min(best + 1c, ask - 1c) | 0.272 |

   Of the adds 2c or more below the touch, only 23.6% go to a level that was empty before. Queue seeking does not
   explain the deep group; no catalog item needs this.
5. **Fees and rebates, 16-22 Oct** (calldata `fee`, activity rows).
   - The taker leg paid $3,550 in fees on $155k of taker USD (2.3%) and got $1,361 of TAKER_REBATE.
   - The maker leg paid no fees and got $2,052 of MAKER_REBATE.
   - Per-fill settlement is +$9.1k for the taker leg and +$4.0k for the maker leg. The net split is therefore about
     +$6.9k taker and +$6.1k maker. The two legs carry about equal weight, and the per-fill split is arbitrary for
     pairs anyway.

## Critique: assumptions that look false or unproven

### 1. "One push feed with at least 19 subscribers" pools two products, and that pooling has been costing the selection item

- The fixed-lag scan (finding 20) treats every wallet that co-signs P4e-alone events at a fixed lag as a subscriber of
  one feed. Check 1 shows that the +100-230 ms group trades the 122 GRID events where P4e, 0x2005d16a, the slow trio
  and the wallet never trade. It also trades them informed, with tight co-prints.
- So group G has a source that covers GRID events. For non-GRID events it receives the messages about 150 ms after
  group P. Group P (P4e first, the wallet +50 ms, the trio +450-600 ms) shares one coverage: non-GRID tier 3 always,
  two thirds of tier 4, almost no tier 5 and no GRID.
- The iteration-8 coverage feature cov24 pooled the two groups. That is why it was > 0 in 92% of GRID events and lost
  to the popularity control within non-GRID events (finding 9). The same pooling inflates the "co-signed" share and
  muddles every "who receives which kind" statement.
- The selection mechanism the investigation already believes in ("the wallet trades its feed's coverage", H85) was
  scored with the wrong product.

### 2. "The GRID boundary is the feed's coverage" is right only for group P's product

- GRID events are covered by a source that group G uses, and they are tradable with an edge (check 1).
- The wallet's boundary is therefore not "no in-round data exists for GRID events". It is "the product the wallet
  (and P4e) buys does not include them".
- This narrows the vendor question. Feed P is a product without GRID's events and without most tier-5 events. Group G
  either buys a second product (GRID-licensed) or one vendor's higher tier, delivered 150 ms after Feed P on the
  non-GRID events.
- The fixed +150 ms behind P4e on non-GRID events means group G's non-GRID messages are downstream of the same
  upstream as Feed P's. The GRID events are the place where group G's source can be timed without Feed P, and nobody
  has decoded their calldata yet.

### 3. Z8 (an automated reader of spectator relays) assumes a machine; the coverage pattern looks like staffing

- Tier 3 is always covered, tier 4 two thirds of the time, tier 5 4%, and coverage switches on and off within a match
  (X72, supported). A relay reader would cover every event with a public relay, whatever the tier.
- A vendor whose scouts watch the broadcast or the in-game spectator view and key in events would cover by tier and
  by staff availability. It would also show the same Dota offset (the spectator delay plus a short reaction time), no
  fragment clock, raw events, esports only, and per-subscriber pricing.
- The two readings differ in one measurable quantity: the spread of the lag behind the in-game event. A machine lags
  by a near-constant; a human scout's reaction time varies by hundreds of milliseconds, with a right skew. That spread
  has not been measured. The Dota alignment fixed the offset D but did not look at the residuals.

### 4. The "61-71% alone" share is not evidence of a second input

Check 3 shows that the alone takes are informed (+3.2c at 60 s), price their premium the same way, and differ mainly
in size and speed of repricing. Being co-signed is selected by event size and by followers (the 10-s markout of
co-signed takes rises from 3.0c to 4.9c once the followers' own prints are counted). Q2 (two sources) has no support
from information content. The remaining question is the kind filter, not a second feed.

### 5. The scope fix assumes the title set is CS2 plus Dota 2

- The wallet added Dota 2 on 10-22 (15% of fills that day). Dota was 54% of its fills on the 10-31 forward block.
- Group G (and per iteration 7 some group-P wallets) also trade LoL and Valorant through the same fan-out.
- `evaluate()` now reports coverage on the lot, which makes a failure visible but does not prevent it. If the wallet
  started a third title during 10-23..10-30, item 1 fails on h1 whatever else holds.

## Proposals, ranked by the chance they close the gap

### P1. Selection = group P's coverage: rebuild the coverage feature on the right product and freeze it into the exam pool (strong form of X113 / X102 / X98; new split)

- **Hypothesis.** The wallet trades the events that Feed P covers. Feed P's subscribers (group P: wallets that act on
  the shared messages but almost never in GRID events) reveal its coverage in other events of the same league or
  tournament before the event starts. Group G's activity is a different product and only adds noise.
- **Why it fits.**
  - Check 1: wallet traded given group P present 91% / 78% / 50% (tiers 3 / 4 / 5), against 0% / 0% / 5.7% when only
    group G is present. In-event group-P presence gives AUC 0.944.
  - Check 2: the point-in-time group-P feature reaches 0.90-0.92 raw AUC on VALIDATE (recall 0.92-0.97 at > 0, GRID
    share 7-8%), against 0.81-0.83 for P4e alone and 0.85 for the pooled set.
  - Selection is the one item that passes. It is fragile forward (recall 0.50 on the 10-31 block) and on h1, where 25%
    of the leagues were never seen.
- **Test.**
  1. Fix group membership on BUILD only (16-20 Oct). A member co-signs P4e-alone events at a fixed lag (the iteration-8
     rule) and has at most 2% of its takes in GRID events. Freeze the list. Also scan all public takers, not only the
     19, for "fixed lag behind P4e, never in GRID": more members add coverage power.
  2. Feature for event e: distinct group-P members with a print in another event of the same league, and separately
     of the same tournament or serie (Gamma `meta_json`), in [gs_e - 24 h, gs_e) and [gs_e - 72 h, gs_e). Use the
     data-api tapes of all CS2 and Dota events; prints are counted at block time before gs_e. Make one variant with
     P4e's own Dota 2 and LoL prints (multi-title coverage).
  3. Market-level variant, if the examiner scores per market. For map-2 and map-3 markets, add group-P prints in the
     same event's earlier maps, before that map's start. These are point-in-time, because the later maps start minutes
     after the first.
  4. Pre-register, then score without refit on VALIDATE, its unseen-league events, the 10-31 12-18 block and every
     later development block:
     - group-P coverage alone;
     - activity + group-P coverage (BUILD-fitted logistic);
     - v4;
     - v4 + group-P coverage.

     Report the gain over both activity baselines and the X98 switching rule.
  5. Report the GRID flag's coefficient once group-P coverage is in the model.
- **Data.** Taker-windowed tapes (already cached for 16-22 Oct; fetch the Dota and later development-block tapes),
  `events_sel` / `events_meta` (league, tournament), Gamma listing projections for the forward pool.
- **Signature if true.**
  - Group-P coverage plus activity matches or beats v4 on VALIDATE (>= 0.95).
  - It beats v4 on unseen-league events and on the forward blocks (recall >= 0.75 at lift >= 3 where v4 got 0.50).
  - The GRID flag becomes redundant (coefficient near 0).
- **Signature if false.** Group-P coverage adds nothing over v4 forward; then selection follows the league as such,
  not the feed.
- **Why it closes the gap.** It is point-in-time and wallet-independent, the examiner can compute it on sealed lots,
  and it states the mechanism. It also replaces a frozen league table that cannot extrapolate to h1's unseen leagues.

### P2. GRID events as the natural experiment for the feed's structure and latency: decode group G's takes where Feed P is absent (new)

- **Hypothesis.** Group G receives one fan-out in both event classes from one vendor. That vendor has GRID-grade data
  for GRID events and, for non-GRID events, messages 150 ms behind Feed P (one upstream, two delivery tiers, or a
  reseller of Feed P). The alternative is that group G merges two sources: official GRID data in GRID events and
  Feed P's messages in the others.
- **Why it fits.**
  - Check 1: group G trades GRID events with tight co-prints and positive markouts, and keeps the same members across
    classes.
  - In Dota the same wallets trade GRID-flagged EPL Masters at 91% (NOTES finding 10), while P4e and the wallet skip
    it.
  - In GRID events, Polymarket's own data is GRID's, so the only fast movers there are GRID-grade.
- **Test.**
  1. Decode the public taker calldata (`fetch_calldata.py`) of about 25 GRID CS2 events of 16-22 Oct and of the
     GRID-flagged Dota events. A few thousand transactions; the taker tapes are cached.
  2. Measure group G's relative lags among themselves (for example 0x8a80528d -> 0xddb6e624 -> 0xf1ee4842 -> 0xc7097421,
     and the slowest members) in GRID events against non-GRID events. Report median, IQR, event SD and a 30-s shift null.
  3. Find the earliest signer of each group-G cluster in GRID events. Is it a group-G member, a wallet that never
     appears in non-GRID events, or nobody? Compare its lead over the first public repricing (first print of a
     >= 3c move by non-members) with group P's lead in non-GRID events.
  4. Count message kinds per class with the iteration-7 census, by the previous burst's team. Do group G's GRID-event
     clusters carry the plant / turn kind as well as round wins?
- **Data.** Cached taker tapes of untraded GRID markets, publicnode calldata, `events_sel`.
- **Signature if true (one vendor, two tiers).**
  - Group G's relative lags are identical in both classes (within about 10 ms).
  - In GRID events P4e's slot is simply empty, and group G's first member leads the market there by as much as P4e
    leads it in non-GRID events.
- **Signature if false (two sources).**
  - Different spacing or order in GRID events.
  - A different lead signer in GRID events, or a larger lead there (server-side data ahead of Feed P's broadcast-side
    clock). That lead difference in seconds would be the first CS2 measurement of Feed P's latency class, and it needs
    no consent.
- **Why it matters.** It names what kind of product Feed P is (official vs broadcast-side, by its lag behind a
  GRID-grade source) and so tells which of X101 / X117 / the stream clocks to pursue. It also removes group G from
  every fan-out statistic in the wall account.

### P3. Machine reader or human scouts: measure the spread of the feed's lag behind the in-game event (strong form of H98 / Z8 / X88)

- **Hypothesis.** Feed P is keyed by scouts who watch the broadcast or the spectator view. Its messages then lag the
  in-game event by a human reaction time (median about 0.5-1.5 s, SD at least 0.4 s, right skew), not by a
  near-constant machine delay.
- **Why it fits.** Critique 3: coverage by tier with partial tier 4, within-match on/off states (X72), the Dota offset
  at the spectator delay, no fragment clock, raw events priced by each subscriber. In the existing Dota runs, 39 of 43
  hits fall inside a 3-s window (`dota_feed_align_w3` vs the 6-s run). That is compatible with both readings at
  1-s kill resolution.
- **Test.**
  1. Now (10-22 PARI Universe maps, existing code `dota_feed_align.py`): scan D in 0.1-s steps and window widths
     w = 0.8, 1.2, 1.6, 2, 3 s, and report hits(w) / hits(3 s). Integer kill seconds give a uniform 1-s spread. A
     machine (constant lag) saturates by w of about 1.2-1.6 s; a scout with SD >= 0.4 s keeps adding hits to 3 s.
     Split the hits by kill context: isolated pick-offs against teamfight kills (>= 3 kills within 10 s). A machine
     follows each kill at the same lag; a scout sends one message per fight, later than its first kill.
  2. With the user's consent (a file download): the replays (`.dem.bz2` from OpenDota's `replay_url`) of the same five
     maps give tick-level (33 ms) kill times. The lag SD then decides at once: under 100 ms means a machine, 300 ms or
     more with a right skew means a human.
  3. Error test, now, on 16-22 Oct CS2. Scouts mis-key. Count clusters where at least two group-P members bought the
     same team within their lag windows and the 60-s markout was <= -5c, then (within 30 s) a cluster on the other team.
     Compare with group G's clusters and with non-subscriber bursts. A machine reader shows no excess of coordinated
     wrong-way messages.
  4. On every development block with a Dota take, the pre-registered `tommy_dota_live` calibration (receive time,
     game_time, delay) gives the absolute lag. Add its spread across kills to the pre-registration.
- **Data.** `dota_pub/`, OpenDota parsed matches (cached), `calldata_all` / `calldata_pub`, the replays (consent).
- **Signature if true.** Residual spread about 0.5 s or more with a right skew, fight kills lagged more and coalesced,
  and an excess of coordinated wrong-way clusters.
- **Signature if false.** Saturation by about 1.2 s, the same lag for pick-offs and fights, no coordinated errors.
- **Why it matters.**
  - If scouts key the feed, its clock is the broadcast plus about 1 s. The X117 relay census would then fail by
    design, and coverage is a staffing rule (a tier rule, which is the selection result).
  - The public route to its timing on sealed lots is then the stream (X4 / X22 / X87), with the scout's reaction as a
    measured constant.
  - If a machine keys it, X117 becomes the first priority.

### P4. Scope insurance for a third title before h1 is examined (strong form of X112)

- **Hypothesis.** The wallet adds titles over time (Dota from 10-22). The feed carries LoL and Valorant for other
  subscribers. A sealed lot can contain a third module that v4's universe excludes.
- **Why it fits.** Critique 5. Coverage is 1.0 on the 10-31 block only because nothing outside CS2 and Dota traded
  there by 14:55.
- **Test.**
  1. On every development block, tabulate the wallet's activity by Gamma series: all esports series, not only 10309 /
     10310.
  2. From the cached and development-block tapes, measure whether group P (P4e above all) trades LoL / Valorant
     events, and in which leagues. If Feed P covers a title, the wallet can switch it on.
  3. Widen `evaluate()`'s universe to every esports series with in-play match / map markets (`secondsDelay` 1). Score
     titles without history with the title-agnostic part of the rule: GRID flag + tier + group-P coverage (P1). An
     unseen title is then scored rather than excluded. Report coverage per title.
- **Data.** Activity of development blocks, Gamma series listings (projection only for sealed units), tapes.
- **Signature if true.** Group-P prints in LoL / Valorant events, or any wallet fill outside CS2 / Dota on a
  development block.
- **Why it matters.** Item 1 is binary. This costs one universe change, and it cannot hurt selection on CS2 / Dota.

### P5. Make the outcome item's denominator explicit: the per-market PnL is the pair margin, and group G is where the residual comes from (reframing of X82 / H65; small and runnable now)

- **Hypothesis.** The wallet's per-market residual (the unpaired, losing side) is the fills taken by group G on the
  round-win kind, the messages the wallet does not receive. The per-market outcome then splits into:
  - a pair margin that a public rule can approximate, because replays already match its paired volume at 0.8-0.95
    (`margin_replay.json` `corr_pairs`);
  - a residual set by group G's activity in that market.
- **Why it fits.**
  - Replays lose on the residual (-$9k to -$16k), not on volume.
  - Pack takers are 16-18% of its maker shares at -1.5 to -4.5c.
  - Group G is present in 90-100% of the tier-3 / tier-4 events it trades.
- **Test.**
  1. On 16-22 Oct, attribute every wallet maker fill to group P, group G or others by the taker of the transaction.
  2. Regress per-market wallet PnL on (paired shares, group-G-taken shares, others' prints) and report the variance
     shares.
  3. Score one pre-specified replay variant without refit: the existing balanced pair ladder, whose residual is cut
     whenever a group-G take prints in the market (latency >= 2 s, strict fills). Report it next to the activity
     baseline. This is diagnostic of what item 5 needs, not a rule claim.
- **Signature if true.** Group-G-taken shares explain most of the residual variance, and the 2-s-late variant raises
  the Pearson / Spearman correlation above the 0.33 / 0.28 print baseline.
- **Signature if false.** The residual is spread over all takers; then item 5 truly needs the private taker leg and
  the wall account can say so with a number.

## Notes for the wall account

- After the split in check 1, the "shared feed" statements should be restated for group P only: its share of the
  wallet's take clusters, the lag table, and the "alone" share.
- Check 3 removes the information-content argument for a second input.
- Check 4 closes queue-seeking placement as a price explanation (descriptive, crude book).
- Price and outcome still need the private value. P2 and P3 are the consent-free routes to the feed's latency class
  and its keying mechanism. P1 and P4 protect the only passing component and the scope item for the exam.
