# Panel, iteration 15: assumption breaker (fresh eyes)

Written 2026-11-01, about 14:05-14:50 UTC.

**Sealed data.** Nothing sealed was opened. Every check below uses units that started before H (16-22 Oct, plus the
taker-regime GRID days 10-12..10-16). The only network reads were data-api taker tapes for 125 round-handicap,
round-O/U, map-handicap and totals markets of five BUILD events (16-20 Oct), fetched through the polyrea adapter and
the shared cache. They are stored only in the scratchpad.

**Scripts.** All scripts and their JSON outputs are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/p15/`:

| Script | Check |
| --- | --- |
| `match_mode.py` | A |
| `match_share.py` | B, C |
| `shadow_lead.py`, `shadow_pairs.py` | D |
| `sib_fetch.py`, `sib_analyze.py` | E |
| `event_unit.py` | F |

Each process stayed under 300 MB.

**What I read**
- BRIEF.md: premise, catalog and accuracy sections.
- NOTES iteration 15 in full, plus the earlier sections the checks depend on (X29, X158, X176, X203, X215).
- state.json: all catalog items, components, gauges and hypotheses.
- FINAL_RULE.md: rule table, mechanism and "not explained".
- panels/iter14_assumptions.md in full, and the proposal titles of every earlier assumptions panel.
- There are no EXAM or wall-audit files.

## Checks (so nobody redoes them)

### A. The ~1-s mode of its message-locked re-pricings is the visible take's MATCH, not its own take-repost cycle

Setup:
- **Decisions:** E3-1 V-change bursts, i.e. filled maker orders at their true signing times.
- **Messages:** wallet-free group-P takes on the event.
- **Split:** whether the wallet had its own take within 300 ms of the message.
- **Measure:** excess over a ±30..120 s shift null, in 250-ms bins of the lag (decision − take signing).

| Messages | Period | Excess | 0-250 ms | 250-1000 ms | **1.00-1.25 s** | 1.25-3 s |
| --- | --- | --- | --- | --- | --- | --- |
| group P, no own take | BUILD | 889 | 170 | 138 | **297** | 285 |
| group P, no own take | VALIDATE | 896 | 140 | 172 | **254** | 330 |
| group P, with own take | BUILD | 157 | 14 | 10 | 60 | 73 |
| group P, with own take | VALIDATE | 123 | 7 | 17 | 56 | 43 |

How to read it:
- 82-83% of the ~1-s mode (297 of 357 on BUILD, 254 of 310 on VALIDATE) comes at messages where the wallet did not
  take. So it is not "after its own take" (iteration 15, finding 9; the timing component in state.json).
- Re-measured from the take's estimated match time (sign + 1,040 ms, capped at the block), the excess sits 0-250 ms
  after the match: 233 of 643 on BUILD, 261 of 687 on VALIDATE.
- About two thirds of the message-locked re-pricings come at or after the informed take matches. Only about one third
  fall inside the 1-s delay window, which is where a maker gains from knowing first.

### B. Measured from the jump trade's match time, the "2.5-5 s lead over public prints" disappears

Setup: 6,897 BUILD and 7,588 VALIDATE ≥2c clean-print jumps. For each one, I histogrammed the wallet's V-change
decisions of the same direction against two clocks: the data-api (block) timestamp and the jump transaction's match
time (taker sign_ms + 1,040 ms).

| Clock | Where the decisions peak (0.5-s bins) |
| --- | --- |
| Block time | [-3.0, -2.0) s: 274 / 275 BUILD, 280 / 271 VALIDATE; flat level about 60-90 |
| Match time | [-0.5, +0.5) s: 296 / 302 BUILD, 270 / 349 VALIDATE |

Around the match peak, the excess is split about evenly between [-1.5, 0) s and [0, 1.5) s.

**Caveat.** For slow signers, sign + 1,040 ms runs early (X29), which shifts decisions toward positive lags. That is
why P3 step 1 asks for per-signer offsets measured on the server clock.

So E3-1's finding ("decisions precede public print jumps by 2.5-5 s; the public tape is downstream of its input") is
mostly the block-timestamp lag of the data-api tape. Measured against the CLOB trade itself, the wallet re-prices in
the same second:
- half of these re-pricings come inside the informed taker's delay;
- half come after the match.

### C. The share of decisions within 300 ms after a public match is small, and it sits almost entirely in the non-dark class

Setup: any taker transaction on any book of the event, same direction, against a shift null.

| Decisions | Period | n | Observed | Null | Excess |
| --- | --- | --- | --- | --- | --- |
| All | BUILD | 7,640 | 9.8% | 2.8% | **7.0%** |
| All | VALIDATE | 9,384 | 9.5% | 2.8% | **6.7%** |
| Dark (no group-P take in the 3 s before) | BUILD | 5,919 | 4.9% | 2.7% | 2.2% |
| Dark | VALIDATE | 7,605 | 4.8% | 2.7% | 2.1% |
| Non-dark | BUILD | | | | 23.7% |
| Non-dark | VALIDATE | | | | 26.2% |

The dark majority (77-81% of decisions) is not a reaction to public trades. It stays private.

### D. The operator's own shadow accounts sign 0-4 ms after 0xd2bb9459 and 0x10d79cc7, at the same price, in GRID events

Setup:
- Data: decoded GRID-event transactions (`sib_grid/calldata`, `calldata_grid`; 10-01..10-17, before H).
- For each shadow order, I looked for makers whose order on the same token was signed 0-5 ms before it, against the
  5-50 ms rate per ms. This is X176's bar: siblings 7.8-28.9x, everyone else at most 4.5x.

| Shadow | Leader | 0-5 ms | 5-50 ms | Ratio per ms |
| --- | --- | --- | --- | --- |
| 0x67119033 (owned by 0x116342d6, the wallet owner's $2,000 recipient) | 0xd2bb9459 | 8 | 5 | **14.4x** |
| 0x67119033 | 0x10d79cc7 | 7 | 1 | **63x** |
| 0x52661b8e ("TommyLeePeeecan") | 0xd2bb9459 | 2 | 0 | 18x |
| 0x67119033 | 0x6e2c0e94 (a feed co-subscriber) | 2 | 41 | 0.4x |

The co-subscriber's pattern (most pairs at 5-50 ms) is the contrast case.

The pairs, listed in `shadow_pairs.json`:
- 16 of 23 are at the identical cent. The other 7 sit 1-3c away, as slots of a 1c ladder.
- On 10-12 19:09:19, 0x67119033 signs 10-share orders at 0.40 / 0.39 / 0.38 / 0.37 within 0-1 ms of 0xd2bb9459's
  100-share 0.37 order. Only filled orders are decoded, so the leader's other slots are probably just unseen.
- On 10-15 and 10-16, it signs 20-share orders at 0-1 ms behind 0x10d79cc7's 20-share orders at the same price.

This is the X176 shadow fingerprint, and two things rule out a copier or co-subscriber:
- **A copy is too slow.** An order reaches the book about 24 ms after signing, so a same-price order signed 0-4 ms
  later cannot be a reaction to the leader's order.
- **A co-subscriber shows the opposite pattern.** The feed co-subscriber in the same books, 0x6e2c0e94, has most of its
  pairs at 5-50 ms.

So the two GRID accounts were the operator's main accounts in GRID events, at least on 10-12..10-16. That contradicts
iteration 15, finding 3 ("not the operator's process") and finding 12. Their failure to co-sign across markets with
the wallet in 16-22 Oct shows a separate quoting loop, not a separate operator.

What is not yet shown:
- The decoded shadow GRID orders end on 10-17 (10 orders that day), so whether the shadowing went on during 16-22 Oct
  is still open (P2, step 1).
- 0x10d79cc7 also leads 0x67119033 at 0-1 ms with equal 20-share sizes, so which of the two is the "shadow" is a
  label, not a fact.

### E. Negative: the event's prop markets do not carry the dark messages

Setup:
- Five BUILD events with the most decisions (cs2-9ine-unity, cs2-all-priv, cs2-fnc-prv, cs2-nip-mibr, cs2-tl1-mgc).
- Their 125 round-handicap, round-O/U, map-handicap and totals markets, of which 40 had any trade: 572 taker prints
  in all.
  - By market type: map handicap 290, totals 136, round O/U 102, round handicap 44.
  - Group-P takers: 120, mostly the trio. Group G: 0.

None of these markets has a tape in the workspace cache, and E3-1's indicators never included them.

Around the wallet's 1,398 dark decisions, prints in [-2, +5) s of block time:

| Prints | Excess | Null |
| --- | --- | --- |
| All takers | 33.6 (2.4% of decisions) | 99.4 |
| Group P / G | 7.8 (0.6%) | 27.2 |

The prop markets are too thin to be the invisible message layer.

### F. Negative: the event as the outcome unit does not rescue the outcome item, and there is no cross-market hedging

Correlation with the wallet's PnL (Pearson / Spearman), per market and per event (sum of the match and map markets):

| Rule | VALIDATE, per market | VALIDATE, per event | BUILD, per event |
| --- | --- | --- | --- |
| C0 (X202 L5) | 0.315 / 0.238 | 0.270 / 0.191 | 0.204 / 0.292 |
| T26 | 0.432 / 0.181 | 0.443 / 0.320 | -0.160 / 0.142 |
| Knockout D | 0.245 / 0.089 | 0.223 / 0.223 | 0.245 / 0.155 |
| Oracle copy at 2 s (T_lo) | 0.431 / 0.404 | 0.332 / 0.364 | 0.255 / 0.364 |
| **In-play prints baseline** | 0.517 / 0.367 | **0.585 / 0.556** | 0.502 / 0.349 |

Within an event, the wallet's match-book and map-book PnL correlate +0.05 / +0.15 (BUILD, 38 events) and
+0.19 / +0.22 (VALIDATE, 39 events). The variance ratio of the event sum to independent markets is 1.08 / 1.28. So
the books do not offset each other: no event-level hedge or cap is hiding there.

Conclusion: keep the outcome unit at the market. At the event level the co-occurrence baseline itself would clear 0.5
on VALIDATE.

## Critique: what the investigation takes for granted

1. **"The public tape is downstream of its input by 2.5-5 s" is a clock artefact (checks B, C).**
   - What the claim rests on: E3-1, X190 and the FINAL_RULE timing row measure public print events at data-api block
     time, which trails the CLOB match by 1.4-3.5 s.
   - What the trade itself shows: against the match, the wallet re-prices in the same second as the informed trade.
     Half of these re-pricings come inside the delay and half after it.
   - **The private lead over the public trade stream is at most the 1-s taker delay**, on the decisions that have a
     visible message.
   - What stays private is the dark majority, which has no public match near it (2%).
   - The latency yardstick should be re-stated against the trade stream as well:
     - the CLOB trade stream (public on the market websocket at match time) already precedes about two thirds of the
       message-locked re-pricings;
     - the "0.25 s after the message" bar applies only to the one third inside the delay.
   - The print-anchored round clock behind R vs K (findings 7, 13 and 21-24) uses block-time anchors too. Its jitter
     of 1.4-3.5 s is a candidate reason it "snaps only 1.30x as often as a reversed sequence".

2. **"The ~1-s mode is the take-then-repost cycle after its own take" (finding 9) is false for over 80% of the mode
   (check A).** It is locked to the match of other subscribers' takes when the wallet does not take. The decision unit
   "message-locked re-pricing" pools three different decisions:
   - re-pricing ahead of the informed takes (the co-sign mode);
   - re-pricing inside the delay;
   - re-pricing after the trade.

   Only the first two are the maker's informational edge.

3. **"One process" is being used as the test for "one operator" (check D).**
   - The cross-market 0-5 ms test refutes a shared quoting loop. The operator can run two loops: one for its feed
     ladder on non-GRID events, one for GRID.
   - The operator's own shadows, which by X176 belong to no one else, sign at the same price 0-4 ms behind 0xd2bb9459
     and 0x10d79cc7.
   - Consequences:
     - iteration 14's "GRID arm" is real at least through 10-16;
     - X207 and X216 were ruled out on a refuted premise;
     - the user's question about the exam wallet list currently names the wrong set of accounts.
   - The design difference (single 50-600-share orders; 20-share ladders) is what one operator would run where it has
     no Feed P. Finding 5 measured that GRID value as carrying nothing beyond the map print.

4. **"The live tests must wait for the wallet's own units" (X215 ruled out, X208 not run) applies the wrong gate.**
   - The X215 gate asks for the five-slot design. The pre-registered live tests ask an information question: does the
     value move at Thunderpick suspensions, at Valve snapshot events, at the stream clock?
   - For that, the property that matters is being on Feed P: a fixed lag behind group P, and informed markouts.
   - The operator's 0x7d67f01d units of 11-01 06-12 (cs2-the9-5s, dota2-synaps-hn) ran while `tommy_tp_odds2`,
     `tommy_dota_rt`, `tommy_kick_pdt` and `tommy_chat` were recording. They are the only development units with
     those recordings inside the budget.

5. **"VALIDATE is the exam bot" has been checked for design drift (X156), not for feed drift.** Since H:
   - the wallet's share of the operator's non-GRID events fell to 0 of 4;
   - 0x7d67f01d switched to single orders;
   - P4e and 0x2005d16a had no take in the 56 recorded 10-31 markets;
   - X121 found 10 of 71 of the wallet's 10-31 takes co-signed by group P / G within 800 ms, against 38.5% of take
     clusters in 16-22 Oct (different definitions, so not yet comparable).

   v5's gp72 term and the whole price / outcome picture assume the 16-22 Oct fan-out. Nobody has replicated the
   fan-out on a development block after T0.

## Proposals (ranked by the chance they close the gap)

### P1. A same-feed gate in place of the same-process gate: run the frozen live information tests on the operator's development units now (strong form of X215 / X208 / X118 / X144 / X168 / X162)

**Hypothesis.** 0x7d67f01d is on the same feed in 10-31 12-18 and 11-01 06-12, even with single-order quoting. So its
value changes carry Feed P's messages. The pre-registered live tests can then be read on its units:
- **Thunderpick as V (X144 / X168):** the value tracks the bookmaker's in-play line and its suspensions.
- **Valve as the Dota feed (X118 / X208):** the value moves at the spectator-state events in the 4-s snapshots.
- **The stream clocks (X162 Kick PDT, X87 chat).**

**Why it fits**
- Critique 4.
- Iteration-14 check A: the operator traded cs2-the9-5s (232 rows) and dota2-synaps-hn (140 rows) on 0x7d67f01d in
  11-01 06-12, and cs2-1win-5s and dota2-xe-hn in 10-31 12-18.
- `tommy_tp_odds2` (from 05:29), `tommy_dota_rt` (from 02:14) and `tommy_kick_pdt` (from 07:51) were recording that
  block.
- 0x7d67f01d took 34 ms behind P4e in 10-08..10-15 (X176) and is 28% taker rows on cs2-1win-5s, so a co-signing test
  has takes to work with.

**Test** (development units only; each unit's start checked with `sealed.is_sealed`)
1. **Inputs.** Decode 0x7d67f01d's transactions on the four units (activity → publicnode). Decode the public taker
   transactions of those markets as well: data-api tapes plus calldata for group P, the trio and group G.
2. **Same-feed gate, written in NOTES before any recorder is read.**
   - Its takes co-sign with the trio / group P / group G at their 16-22 Oct lags, with a fixed lag and an event SD of
     no more than about 15 ms, against a shifted null.
   - Its value changes (top of each single-order burst) move the clean print their way at 60 s, at least +1c on new
     highs, as the wallet's do (+1.8-2.3c).
3. **If the gate passes, run each frozen test unchanged:**
   - X168 on cs2-the9-5s: coincidence of its value changes with Thunderpick suspensions and re-opens, against 2,000
     circular shifts, and its level at re-open against the de-margined coefficient;
   - X118 on dota2-synaps-hn: re-pricing by snapshot event class against shifted clocks;
   - X162 / X87 on the Kick / Twitch units.

   Report them as "VALIDATE-live (operator, same feed)", separately from the wallet.

**Data.** data-api activity and tapes, and publicnode calldata (development units). Through `iter_live`:
`tommy_tp_odds2`, `tommy_dota_rt`, `tommy_kick_pdt`, `tommy_chat`, `tommy_cs2_near`.

**Signature if true**
- The gate passes, and at least one test returns its pre-registered verdict.
- In particular, if Thunderpick suspensions coincide with its value changes and the re-open level is within 1c in at
  least half the cases, V is (or tracks) a key-free in-play line. The live price rule for future blocks can then carry
  it.
- If its Dota value moves within one snapshot after Valve kill / tower events and ahead of the market, the Dota half
  of the feed is public spectator state.

**If false**
- The gate fails: 0x7d67f01d is off the feed after H, which feeds P4.
- Or the tests fail on gated units: X144 / X168 / X118 close with a measurement instead of "no units".

### P2. Re-attribute the GRID accounts by the shadow fingerprint, then use the GRID arm as the operator's public-information control (re-opens X216 / X207 / X188 with check D; new identity test)

**Hypothesis.** One operator runs two arms:
- the Feed-P ladder (the wallet, 0x7d67f01d) on non-GRID events;
- a GRID arm (0xd2bb9459 single orders; 0x10d79cc7 20-share ladders) on GRID events.

Its shadows, 0x67119033 and 0x52661b8e, follow both. Events are routed by data source, not by feed coverage alone.

**Why it fits**
- Check D: 0-4 ms, same price, 14-63x per ms.
- X203's 9.0x and 12.6x before 10-16.
- Iteration-14 check A: about 15.5k BUY-only rows with merges per account in 16-22 Oct, and the shadows' 18-20
  events per account that the wallet did not trade.

**Test**
1. **Persistence.** Decode 0x67119033's and 0x52661b8e's 16-22 Oct transactions in the events the wallet did not
   trade. Run check D's statistic against 0xd2bb9459 and 0x10d79cc7 there, with the wallet as the control in its own
   events. Repeat on the 10-31 12-18 GRID units (fokus-baks, jjh-bmb).
2. **The control.** If step 1 passes, the GRID arm is the same operator's quoting without Feed P. Iteration 15,
   finding 5 has already measured it: no in-round information beyond the map print. Add:
   - its sign-time anchoring to the last print (X216 step 2, on calldata);
   - the X163 machine with V = print + offset on its 20-share ladders.

   That quantifies exactly what the operator's process does without the feed.
3. **LoL twin (X207, premise restored).**
   - 0x10d79cc7 traded LoL in 16-22 Oct and on 10-31 12-18 (264 rows).
   - Map Polymarket LoL games to Riot game ids through Leaguepedia's RiotGameId (X191, key-free).
   - Pull Riot livestats windows.
   - Fit V = f(gold, kills, towers, dragons, game time) on BUILD, and score within one tick against the print on
     VALIDATE.
4. **The user question.** Restate the exam wallet-list question to the user with 0xd2bb9459 and 0x10d79cc7 included,
   and with this evidence.

**Data.** data-api activity of the shadows and the GRID accounts (development windows), publicnode calldata, Riot
livestats, Leaguepedia cargo.

**Signature if true**
- The shadow ratio is at least 7.8x against the GRID accounts in 16-22 Oct (and below 4.5x against everyone else).
- The GRID arm's value equals print + offset within one tick at least 0.45.
- On LoL, a public-state fit beats the print by at least 0.10 within one tick.

Together, these decode the operator's machine and value-model class where the input is public. They pin the wallet's
CS2 residual to Feed P alone.

**If false.** The shadowing stops at 10-16: those two accounts were the operator's only before the switch, and finding
3's conclusion stands for 16-22 Oct, now with a stated date boundary.

### P3. Re-time the public tape at the CLOB match and split the message-locked decision by its clock (strong form of X29 / X217 / X190 / E3-1; new unit)

**Hypothesis.** Its V-change decisions at visible messages are three different decisions:
1. ahead of every informed taker (the co-sign mode);
2. inside the 1-s delay;
3. 0-300 ms after the informed trade matches: a public-trade reaction.

The first two are its edge. The third is public on the market websocket and may be a public function of the
post-trade book. The block-time anchors also blur the round clock that R vs K needs.

**Why it fits.** Checks A-C: two thirds of the message-locked mass is at or after the match, and the print-jump peak
moves from about -2.5 s (block) to ±0.5 s (match).

**Test**
1. **Re-stamp every public print at its transaction's match time.** Use taker sign_ms plus the per-signer
   sign→match offset measured on the live server clock (fall back to the block). Re-run:
   - the E3-1 shapes of I3-I6;
   - X190;
   - the print-anchored round clock and findings 7, 13, 21-24.

   Report the clock's snap ratio against the reversed sequence, block time vs match time.
2. **Decompose on BUILD / VALIDATE:** shares, 60-s markouts and price-item numbers (last print, rebuilt touch, V
   oracle) per class 1 / 2 / 3 / dark.
3. **Class 3 on BUILD-live (server clock).** Measure V_new against post-trade book quantities:
   - the deepest consumed level ± k;
   - the new touch;
   - the complement at 1 − ask.

   Freeze the best one before the next VALIDATE-live block as a secondary live price rule for that class.

**Data.** calldata (sign_ms of every public transaction, already decoded), tapes, BUILD-live `tommy_cs2_near` /
`clob_wallets` trades and books.

**Signature if true**
- E3-1's public-event peaks sit in [-1.5, +0.5] s of the match.
- Class 3 is about a third of message-locked decisions, and its V_new is within one tick of a post-trade book quantity
  in at least 0.6 of cases.
- The match-time round clock snaps clearly more often than 1.30x, and the decided-early / previous-winner tests
  tighten, deciding R vs K on the wallet's own record.

At most about 7-9% of all decisions become public-predictable this way, but the private part of V is then stated
exactly: class 1 + class 2 + dark.

**If false.** Class 3's level is not a book function: the reaction carries private value too, and the "public after
the match" share is timing only.

### P4. Is the 16-22 Oct fan-out still there after T0? Test the feed relationship before an exam scores a frozen rule built on it (new; strong form of X156 / X98 for the input, not the design)

**Hypothesis.** Around or after H, the fan-out changed: subscribers churned, or the operator's tier or vendor
changed. The exam lots (h1 / h2, 10-23..30) then straddle a regime change that VALIDATE (10-21 / 22) does not
represent.

**Why it fits.** Critique 5:
- the wallet's share fell to 0 of 4;
- the sibling switched to single orders;
- P4e and 0x2005d16a were absent from 56 recorded markets on 10-31;
- the 10-31 co-signing rate is lower (10 of 71 within 800 ms);
- the taker caps are gone and the merge law drifted (X156).

**Test** (development blocks after T0 only)
1. **Replicate the X97 / X111 fan-out table** on every development unit of 10-31 00-06, 10-31 12-18 and 11-01 06-12.
   Use public calldata of all CS2 / Dota markets in play, not only the wallet's. For each subscriber: the lag behind
   the first signer, the event SD, and the co-signing rate per message.
2. **gp72's input:** distinct group-P members with prints in non-GRID league events per development day, against
   16-22 Oct.
3. **The wallet's information:** the wallet's 10-31 V-change markouts (dark new highs at 60 s), against 16-22 Oct.
4. **If the fan-out changed:** say so before the exam. Pre-register how `evaluate()` reports h1 by sub-period (listing
   metadata only), so the examiner does not read a regime change as a failed decode.

**Data.** data-api tapes and publicnode calldata of the development-block markets, `selection_groupP.json`, and
`iter_live` books for the BUILD-live check.

**Signature if true.** Subscriber lags or membership differ from 16-22 Oct (for example the first signer is no longer
P4e, or the trio's lag moved by more than 30 ms), or gp72 collapses toward 0. Then v5's threshold (20th percentile of
fitted positives) needs a stated fallback, and the price / outcome account must be re-dated.

**If false.** Same lags, same members: VALIDATE represents the exam bot apart from the known size / merge drift. The
forward silence is allocation (P2), not a feed change.

## Ranking rationale

- **P1** is the only route inside the budget to a key-free value source on units that already have recordings.
- **P2** corrects the operator's identity, using the operator's own fingerprint. It gives the decode its
  public-information control and its LoL twin.
- **P3** restates which part of V is private, and gives R vs K a sharper clock. It cannot move the per-order price
  item by more than a few points.
- **P4** protects the one passing component and the dating of every claim. It does not close a gap itself.

Every check above is pre-H. Nothing here touches the frozen v6.
