# Panel, iteration 7: assumption breaker (fresh eyes)

## What I read and what I ran

I read BRIEF.md, NOTES.md (iteration 7 in full, the headings and findings of iterations 1-6), state.json (ledger H1-H82,
catalog A1-X100, components, splits), FINAL_RULE.md and panels/iter1-6. There are no EXAM or wall-audit files. Sealed
calendar (`sealed.py tommy-cs2-maker`): no released lots. I used only data from before H and from the 10-31 development
block (books through `iter_live`, the cached activity of development-start units). I wrote nothing in the workspace
except this file. Scratch scripts and outputs are in the session scratchpad.

Checks, so nobody redoes them:

1. **The wallet's market mix by day** (`activity_dev`, `activity_devblocks`, TRADE rows):

   | Period | CS2 fills | Dota 2 fills | Dota 2 share of fills | Dota 2 share of USD |
   | --- | --- | --- | --- | --- |
   | 10-16..10-21 | 27,129 | 0 | 0% | 0% |
   | 10-22 | 8,065 | 1,472 (first fill 08:11 UTC) | 15.4% | 3.9% |
   | 10-31 12-18 dev block (to 14:55) | 301 | 358 | 54.3% | 22.8% |

   The Dota 2 module started on the last VALIDATE day. It traded three events on 10-22 (Liquid-1win, Yandex-GL,
   TS8-Legion) and Yandex-GL on 10-31.
2. **Who leads the bursts the wallet misses.** The leader is the earliest pack signer on the burst's token in
   [t0 - 0.5, t0 + 2] s. Of the 1,757 wallet-absent census bursts without P4e, P93 led 446, 0x2005d16a 166, 0xf1ee4842
   149, 0xddb6e624 121, 0x8a80528d 119, the three-wallet POLY_PROXY cluster 327, and a non-pack wallet 429. About 835 of
   them were led by subscribers who sign 150-350 ms after the wallet's own fan-out slot. The stale liquidity survived
   that long, and a +50 ms subscriber did not take it. This supports "not competition" for the round-win kind, if these
   are feed messages.
3. **The lags are not clock offsets.** Floor of block time x 1000 - sign_ms over each signer's taker orders (16-22 Oct;
   0.2% / 1% quantiles, ms): wallet 2,094 / 2,143; P4e 1,764 / 2,115; 0x2005d16a 2,099 / 2,138; 0xf1ee4842 2,172 / 2,260;
   0x8a80528d 2,129 / 2,248; 0xddb6e624 2,161 / 2,214; P93 2,106 / 2,152. These floors (path minus clock offset) agree
   within about 120 ms. So P93's +400 ms is a real reaction delay. The 50 ms between P4e and the wallet is below this
   resolution, which fits the coin-flip engine arrival.
4. **Co-signed and alone takes look like one module.** I matched the wallet's 1,698 takes to subscriber same-token BUYs
   in their lag windows: 22.9% co-signed. Co-signed vs alone: cap-or-round sizes 26% vs 25%, median limit 0.50 vs 0.49,
   map-market share 55% vs 55%, median hour 15 UTC for both. Co-signed takes are larger (median 1,000 vs 740 shares).
   These features show no second take module on a second input.
5. **Its takes do not anticipate the pack's next burst.** After a wallet-led burst, the next wallet-absent burst in the
   same market (5-150 s later) is on the same team in 58.5% of cases (n 200). The base rate for absent bursts is 65.1%
   (n 1,495). Its information is not a precursor of the round wins it skips.
6. **The untriggered-pull markout is not momentum** (BUILD-live, the iteration-7 bursts and others' mid).
   - Untriggered-all pulls (213) have a pre-trend of -0.22c over 10 s (shift null +0.005c, p 0.04), and -0.005c over
     2 s.
   - With a flat 10-s pre-trend (|pre10| < 0.5c, n 100), the 10-s markout is -0.755c.
   - OLS: mk10 = -0.596c + 0.022 x pre10.
   - At random times the 10-s pre/post correlation of the others' mid is -0.078 (reversion, not momentum).
   - So X94 survives this confound.
7. **Session start vs schedule** (merge-loop runs of NOTES finding 7 vs `events_sel`). Runs start 4-23 min after the
   first traded event's scheduled start on 5 of 7 days (08:00 -> 08:10, 14:10 -> 14:17, 08:00 -> 08:11, 09:00 -> 09:04,
   08:00 -> 08:23). On 10-22 the process was up from 08:30 but skipped an 08:00 event of a traded league and first
   traded at 11:00. Runs end 1.3-3.3 h after the last traded event starts. The data cannot separate a human morning
   start from an event-driven launch. The pre-registered clock-change test should log the first selected event's live
   start next to the first MERGE pass, or a moved event list will be misread as a moved clock.

## Critique: assumptions that look false or unproven

### 1. The scope item is taken as met, but the universe is CS2 only and the wallet added a Dota 2 module on 10-22

- `target_metrics.coverage_fills` = 0.927 is computed on VALIDATE 10-21..22, where Dota 2 trading existed for one day.
  On 10-22 alone the CS2 universe covers 84.6% of fills. On the 10-31 forward block it covers 45.7%.
- `evaluate()` does not compute coverage on the lot it is given. The forward-block result file
  (`final_rule_v3_devblock_iter7.json`) has no coverage key. The examiner's item 1 (>= 80% of fills and of absolute PnL)
  can therefore fail on h1 without anyone having seen it coming.
- The cause is the 10-share Dota maker orders: they make many small fills. By count, they push the CS2 share far below
  80% even where Dota USD is small.
- FINAL_RULE treats Dota 2 as a size footnote ("10 shares in Dota 2"). Yet the Dota leg is a separate module with its
  own input: its 67 takes are never co-signed by any CS2 subscriber, although the multi-title subscribers trade 6-8 of
  its 13 Dota tokens. This module is growing.

### 2. Selection is modelled as a league table plus popularity; the evidence says it is the feed's coverage, which turns over daily

- P4e is present in 39-48% of the non-GRID events of the wallet's leagues and in 0% of other non-GRID events (X15). The
  feed's subscribers were already in those leagues before 10-16 (X65, finding 24). On the forward block, 3 of the 4
  traded events were in a league that v3 had never seen (recall 1 of 4).
- The h1 / h2 lots are 62-63% tier 5 (iteration 6). A frozen league table extrapolates there through a 3% tier prior.
- So the transferable object is "the events the feed covers today", not "the leagues it covered on 16-22 Oct". X31's
  pack-lag variant used previous days of the wallet's own markets. Its pack data (`pack_orders`) exists only in markets
  the wallet traded, so a coverage feature built from it is partly circular.

### 3. "Shared push feed" is the best reading, but the pre-registered test cannot prove it; and "multi-title" stops at esports

- The verdict rule asked for event and platform components under 15 / 20 ms. Any design where several bots read one
  common source with stable pipelines passes that rule, because the source's own delay cancels in the pairwise
  offset. One example is several readers of the same broadcast-side JSON (a HUD socket or scorebot). The rule rejects
  only readers with different per-platform pipelines.
- "One message fanned out, not separate stream readers" (FINAL_RULE) is stronger than the test allows. Only an absolute
  clock separates them.
- The subscribers are not esports traders only:
  - 0x2005d16a trades CS2, football and tennis.
  - 0x8a80528d and 0xddb6e624 (one process) trade CS2, football, NBA and Valorant.
- The source search has looked only at esports sources (GRID, PandaScore, bo3, HLTV, streams, demos). Two consequences
  are untested:
  - In football and NBA, ESPN wall clocks give an absolute clock on the same subscribers at no consent cost.
  - A multi-sport B2B feed would point to sportsbook frontends as its public footprint.

### 4. Every fan-out share is a filled-order share

A FAK that arrives after the earlier subscribers and the cancel wave have taken the stale depth fills nothing and leaves
no on-chain trace. Several figures are censored by queue position:

- "each slower subscriber covers 1-3% of P4e's takes";
- "it takes 74% alone";
- the per-subscriber kind loadings.

They are lower bounds, biased toward events with depth left. The slow subscribers join P4e 2-4 times more often when
the wallet also takes, which fits censoring (bigger, deeper events) as well as kind. The wallet's own blindness to the
round-win kind does not rest on this: it is hit by the pack at its events and could cancel inside the 1-s delay, and
check 2 shows liquidity that survived 150-350 ms. But the claim that "the shared feed explains only a quarter of its
events" does rest on it.

### 5. The kind filter is assumed to be a message-type subscription

The facts so far are the following:

- untriggered pulls about 2.6 times its takes, with small -0.6c drifts;
- takes on reversals and plants;
- a FAK premium that scales with the later move;
- untriggered pulls lead its own later takes in 21% of cases, on the favoured team in 62%.

These facts fit just as well a continuous private fair value (an in-round state model) that the wallet thresholds.
Under that reading, round wins carry no news for it because its model had already moved at the decisive kill or plant.
The two readings predict different relations between its pulls, takes and quotes (proposal 5).

## Proposals, ranked by the chance they close the gap

### P1. Make the universe cover what the wallet trades now: decode the Dota 2 module and put coverage into `evaluate()` (new; scope item)

- **Hypothesis.** From 10-22 the wallet runs a second universe (Dota 2: 10-share maker ladders plus FAK takes on an
  input not shared with the CS2 subscribers). It is a large share of its fills in the exam lots. A CS2-only rule then
  fails item 1 (>= 80% of fills and of absolute PnL) on h1 / h2 and the future blocks, whatever its other metrics.
- **Why it fits.** Check 1 (0% -> 15% -> 54% of fills; 0% -> 4% -> 23% of USD). Dota takes are never co-signed (finding
  23). The Dota maker size differs (10 shares). Coverage 0.927 is a static VALIDATE figure, and `evaluate()` reports no
  coverage.
- **Test.**
  1. Coverage by day and by forward block: the rule universe's share of fills and of absolute settlement PnL on
     10-16..10-22 day by day and on 10-31 12-18. Use activity clamped to development units, and the
     settlement-from-activity ledger, not `/positions`.
  2. Add `coverage_fills` / `coverage_abs_pnl` computed on the lot to `evaluate()`. The examiner can then see item 1,
     and the rule fails visibly rather than silently.
  3. Decode the Dota module with the CS2 recipe:
     - Selection: Dota events of 10-22 and the dev blocks against all Polymarket Dota events. Check GRID / PGL-Oddin /
       tier fields, pre-game activity, and the leagues of the multi-title subscribers.
     - Maker size and ladder: 10 shares, whole cents.
     - Merges: is the Dota inventory in the same 300-s loop?
     - The Dota takes against the X88 OpenDota live recorder. Its `delay` field gives the one public game clock in the
       wallet's universe.
  4. Widen the selection and price items to Dota and re-score VALIDATE (10-22 only) and the forward pool.
- **Data.** `activity_dev`, `activity_devblocks`, later development blocks, Gamma for Dota events, calldata of the
  wallet's Dota txs (`code/fetch_calldata.py`), `tommy_dota_live` v2.
- **Signature if true.** Dota share of fills above 20% on every development block after 10-22, and the CS2-only
  coverage below 0.8 there. A Dota selection rule with its own gain over activity.
- **Why it closes the gap.** It removes a near-certain exam failure on item 1. The Dota leg may also be the decodable
  half: Valve's spectator feed is a public in-game clock, which CS2 non-GRID events lack.

### P2. Selection = the feed's coverage today, read from the subscribers' activity in other events before the event starts (strong form of X31 / X98)

- **Hypothesis.** The wallet trades the events its feed covers. Coverage turns over with tournaments, faster than a
  league table learns. The subscribers reveal it in other events, before the event starts:
  - P4e, 0x2005d16a, the 0x8a80528d / 0xddb6e624 process, 0xf1ee4842 and P93;
  - the signal is a take in an earlier event of the same league, tournament or serie (Gamma `meta_json`).
- **Why it fits.** Critique 2: P4e's presence is exclusive to the wallet's leagues, the subscribers predate it there,
  forward recall is 1 of 4 in a new league, and the exam lots are tier-5 heavy.
- **Test.**
  1. Rebuild the subscribers' takes over all CS2 and Dota events of 16-22 Oct and the dev blocks, not only the wallet's
     markets. Use data-api activity for 6-9 wallets x 8 days, or the universe tapes' proxyWallet. This avoids the
     circularity of `pack_orders`.
  2. Feature for event e: any subscriber take in another event of the same league / tournament / serie with game start
     in [gs_e - 24 h, gs_e), counted before gs_e. Make a same-day variant and a decayed count.
  3. Control: the same feature built from all takers' activity in those earlier events. Separate "the feed covers it"
     from "the league is popular".
  4. Score the following without refit (pre-register first):
     - v3, v3-tier and the tier rule;
     - activity + GRID + coverage;
     - coverage alone.

     Score them on VALIDATE, on its 16 unseen-league events, and on the forward pool under the X98 switching rule.
     Report the gain over both baselines.
  5. Diagnostic only (co-occurrence, not for the rule): a subscriber take in the event's own first 10 in-play minutes.
     This gives the ceiling of event-level coverage.
- **Data.** Public activity of the subscribers, Gamma listing fields (league, serie, tournament, pandascore id), the
  universe tapes, `events_sel`.
- **Signature if true.** Coverage beats the all-takers control by at least 0.03 AUC. On new-league events, recall is at
  least 0.75 where v3 gets 0.25-0.6. The GRID flag becomes redundant (subscriber coverage of GRID events is 0).
- **Why it closes the gap.** Selection is the only item that passes. h1 is the next exam, it is tier-5 heavy, and a
  frozen table will meet unseen leagues there. This feature is point-in-time, the examiner can compute it on sealed
  lots, and it is mechanistic ("trades what the feed covers"). A PandaScore free-tier token from the user, if given,
  would test `live.supported` as the listing-time form of the same idea. That is a selection test, not a feed test, and
  it is cheaper to ask for.

### P3. Is the shared feed multi-sport? Cross-sport fan-out and an ESPN clock on its subscribers (new)

- **Hypothesis.** One B2B push product delivers football, NBA, tennis and esports events to the same subscribers in a
  fixed order. Then its public footprints are the sportsbooks that consume it (in-play suspensions), not esports sites.
  If the CS2 fan-out does not repeat in other sports, the CS2 feed is an esports-only vendor (the PandaScore / Bayes /
  Oddin class).
- **Why it fits.** Critique 3: the pairwise-offset test cannot separate a push feed from common-source readers. The
  subscribers trade football, NBA, tennis and Valorant. The fan-out already repeats in Dota 2 and LoL (finding 23).
  ESPN publishes wall clocks for NBA plays and soccer key events (brief, polyrea `espn`).
- **Test.**
  1. Decode the subscribers' taker txs in football / NBA / tennis markets of 16-22 Oct (`fetch_calldata.py`, a few
     thousand txs).
  2. Count same-token BUY co-signs within 500 ms between 0x2005d16a and the 0x8a80528d / 0xddb6e624 pair (in CS2 the
     pair signs about 180 ms after 0x2005d16a). Report median, IQR, the event variance component and a 30-s shift null.
  3. Event study of their signing times against ESPN wall clocks: NBA scoring plays, soccer goals and cards. Report the
     lead or lag distribution and its stability. A stable lead over ESPN means an official or courtside-scout feed.
  4. If (2) holds, re-rank the user asks: odds and suspension probes of the sportsbook frontends first (X48 terms
     check), then the PandaScore token (X55).
- **Data.** Public activity of 0x2005d16a / 0x8a80528d / 0xddb6e624, Polygon calldata, ESPN play-by-play (cached
  adapter), Gamma for those markets. Development period only, and nothing from the rn1 workspace.
- **Signature if true.** Co-signs in football / NBA at the CS2 order and spacing (null 0-2), with a stable ESPN lead.
  If false: no co-signs outside esports, or a different order.
- **Why it closes the gap.** It is the only consent-free absolute clock on the shared feed. It names the vendor class,
  and with it the place where a public footprint (fast enough to act inside the 1-s delay) could exist.

### P4. Uncensor the fan-out: P(follower co-signs | depth left at its arrival) (strong form of X97 / finding 26)

- **Hypothesis.** The low co-sign rates and "74% alone" are mostly fill censoring. The slower subscribers send FAKs on
  most of the same events, and theirs fill only when depth survives their lag.
- **Why it fits.** Critique 4: fill fractions are small (the wallet's median 0.11), the followers join 2-4 times more
  often on wallet-taken (deeper) events, and the cancel wave removes depth within tens of ms.
- **Test.**
  1. On BUILD-live and every VALIDATE-live block (server clock, `tommy_cs2_near`): for each subscriber or wallet take,
     measure the resting depth within the follower's typical limit at the follower's expected match time (leader sign +
     follower lag + 1.04 s). Fit P(co-sign) against that depth. Do not use the historical "edge left": it contains the
     followers' own fills and is circular.
  2. Restate the shared share of the wallet's takes at ample depth.
- **Data.** Live books, development-block calldata (`dev_calldata3.py`).
- **Signature if true.** P(co-sign) rises steeply with depth and exceeds 50% at ample depth. The wallet's input is then
  the shared feed on most of its events, not a quarter of them.
- **Why it matters.** It decides whether one source or two must be found for the wall account and for P3, and whether
  the subscribers' public fills can serve as a near-complete label of its event times.

### P5. Discrete message kinds vs a continuous private fair value: an accumulation test on its own actions (new; reframes H75 / X94)

- **Hypothesis.** The wallet runs its own in-round win-probability model on a state feed (kills, plants, economy) and
  acts at thresholds: a pull when its value falls below its bid, a take when the value clears ask + fee + margin. Round
  wins are no news to it. Under this reading the kind filter is a threshold, not a subscription.
- **Why it fits.** Critique 5: untriggered pulls about 2.6 times its takes, with small drifts; the premium scales with
  the later move; pulls lead its takes on the favoured team (62% vs 48%); there are no takes at the pack's round-win
  follow-ons (0 of 5).
- **Test.**
  1. On BUILD-live (now) and VALIDATE-live (pre-register before 11-01 06-12 is read), model the take hazard in an event
     against the signed count of untriggered pulls in the previous 10 / 30 / 60 s:
     - the count is positive when the pulled bids are the other team's;
     - the controls are public book state and the shift null.
  2. Regress the FAK premium and the take's 10-s move on the same count.
  3. Check whether its next add top on each token shifts with the count (own-state price model, reported separately
     and not toward the target).
- **Data.** `own_bursts_markouts_dev`, `calldata_dev`, the live books, the same tables for later development blocks.
- **Signature if true.** The take hazard and the premium rise monotonically with accumulated same-direction pulls, and
  the add tops shift with them. If false: no dose-response, so its takes are single-message events.
- **Why it matters.** It decides what kind of input to look for (raw state vs alert messages). If the reading holds, it
  also gives an own-state price component for the live price item, which today stops at the touch's 0.47.
