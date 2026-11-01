# Panel, iteration 9: information source and data (fresh eyes)

Lens: what the wallet sees, earlier or better, that the investigation has not obtained, and which data would most
sharply separate the leading explanations.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-9 with the late additions), state.json (ledger, catalog A1-X131, components,
target metrics), FINAL_RULE.md and panels/iter8_*. There are no EXAM or wall-audit files.

All checks used development data only:

- the BUILD-live tables of the 10-31 12-18 block (`linked_adds_dev`, `others_mid_dev`, `calldata_dev`);
- bo3.gg match objects of 16-22 Oct events, through the shared cache;
- a record count of the shared recorder's `clob_wallets` feed for the 10-31 12-18 block, read through `iter_live`. I
  counted only Dota units that started in that block: ty-gl 13:00, xe-hn 12:10 and ts8-gl 17:25 (the last one is cut at
  18:00). The 12:00 hour file raised the known zlib error and was skipped.

The current block (11-01 00-06) is sealed. I listed bo3.gg's live-match index once and printed only one slug, its tier,
its status and whether a `bet_updates` field exists. I read no odds, scores or market data of that match.

Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/iter9info/`:

- `oracle_anchor.py`: the price ceiling of an oracle fair value;
- `peg_check.py`, `peg_timing.py`, `lead_maker_anchor.py`: other makers re-pricing around the wallet's adds;
- `bo3_bet_cls.parquet`: bo3.gg odds coverage by event.

## Critique: what the investigation is missing or getting wrong

1. **More information about the fair value cannot close the price item. The missing input sets the wallet's offset
   from value, not only the value** (`oracle_anchor.py`).
   - Setup: the 2,740 validated own adds of BUILD-live (63% in multi-level bursts). The anchor is the others' mid,
     rounded to the cent, plus the best constant fitted in-sample, minus k cents for the k-th level of the burst
     (k taken from the wallet's own burst). This is an upper bound.

   | Anchor | within one tick, top only | with ladder index k |
   | --- | --- | --- |
   | others' mid 100 ms before (public) | 0.414 | 0.447 |
   | others' mid 2 s later (oracle) | 0.449 | 0.523 |
   | others' mid 10 s later (oracle) | 0.381 | 0.432 |
   | others' mid 30 s later (oracle) | 0.305 | 0.328 |

   - Burst tops alone (1,651) give 0.44 / 0.49 / 0.42 / 0.34.
   - Bid plus k cents minus the mid has an SD of 3.2c against the mid now (IQR -4.5 to -0.5c), 3.7c at 10 s and 5.1c
     at 30 s.
   - Finding 14 says the level leads the mid, and it does. But the level sits a variable 0-5c below any public value,
     present or future. So the price item needs whatever moves that offset: an external price that differs from
     Polymarket's, the game phase or hazard, or own state such as the pair cap. A better fair value alone, even a
     perfect copy of the feed's value, stops at about 0.5.
   - Each information proposal below therefore has to explain a ±3c offset, not just a direction.

2. **Finding 14's "private value leads the public book" is entangled with other makers who re-price at the same moments,
   some of them the feed's own subscribers** (`peg_check.py`, `peg_timing.py`).
   - Within 500 ms of a wallet add, another maker adds at its price or one cent better on the same book side:
     - after 44%, 46% and 64% of its adds (low, middle and high offset tercile);
     - 1.0-2.1 such adds per wallet add, against a shifted null of 0.04-0.05;
     - the wallet's fingerprint sizes (100, 10, 54, 58, 68) are excluded from "other makers".
   - Timing, in 25-ms bins:
     - in the 300 ms before its add, about 100-145 per bin (a shifted null gives about 6);
     - in the 125 ms after, 275-335 per bin, peaking at +50 to +75 ms.
   - The most common joiner sizes are 20 and 5 shares.
   - From the block's calldata:
     - the main 20-share maker is 0x2e3c40fa, the cancel-wave maker of X34;
     - the slow trio (0x2529c68d, 0xfe8a28be, 0x72aaaaf9) rests 5-share maker orders;
     - group-G members 0x42a1b2b4 and 0xe8e086f7 rest 10-share maker orders.
   - 10-, 5- and 20-share adds fall within ±1 s of its adds at 5.5-6.4x the shifted null. 52-58% come after it, with
     lag IQRs of about 120-575 ms. Only 12-18% sit at exactly its price.
   - The feed's subscribers re-price their own quotes on the same moments, slightly later and at their own levels. So
     the subscribers share the timing, not a cent-level value. The "concurrent half" of finding 14 (+1.27c within
     ±100 ms) is partly these co-movers and joiners.
   - The latest other-maker add before its burst gives 0.47-0.51 within one tick on its burst tops, against 0.46 for
     the mid on the same rows (`lead_maker_anchor.py`). No public maker reliably leads its level.

3. **Uncensored Dota ladders are already on disk and have not been analysed.**
   - The shared recorder's `clob_wallets` holds the 10-31 development-block books of three development units:
     dota2-ty-gl (8,326 records), dota2-xe-hn (5,860) and dota2-ts8-gl (2,667). The records are 11,390 top-10
     snapshots, 3,365 full books and 2,098 last trades with transaction hashes.
   - The BUILD-live tables (`linked_adds_dev`, `others_mid_dev`, ...) cover only the CS2 books from the own recorders.
   - Dota carried 54-57% of the wallet's fills on that block. Every Dota maker test so far used filled orders (X119,
     X123: censored).
   - The iteration-9 plan waits for X118 on a future block. The uncensored Dota maker leg can be put on the OpenDota
     clock today.

4. **The exam lots have no books and no live feeds, and the plan does not say what each component will run on there.**
   - h1 and h2 (10-23..30) have tapes, calldata, OpenDota parses, bo3.gg post-match rounds, and, with consent, demos
     and replays. No order books, no Valve recorder, no chat.
   - Every price or outcome rule built on the recorded books (touch, untriggered pulls, add levels) can be scored only
     from the third exam round on.
   - The investigation should state, per component, its historical (h1/h2) form and its live form, or state which
     items cannot be met on h1/h2 and why.
   - For CS2 on h1/h2 the only fine-grained game clock is the demos. X122 / X37 should go to the user as one sized
     request. For example: 10 demos parsed and deleted one at a time, under 300 MB of disk at any moment, plus
     demoparser2 from PyPI.

5. **No external in-play price has ever been obtained, and one is reachable through an endpoint the investigation
   already uses.**
   - X48(b) has waited for a terms check since iteration 3.
   - bo3.gg's match object (`api.bo3.gg/api/v1/matches/<slug>`) carries `bet_updates`, a Thunderpick odds object:
     team coefficients, `active` flags, `max_coeff`, `markets_count` and `additional_markets` such as handicaps.
   - In 45 sampled matches of 16-22 Oct, 25 carry it. In 16 of the 25 the final snapshot is a deep in-play state
     (1.001-1.06 against 7-14), and the lower coefficient is the eventual winner in 21. bo3.gg therefore updates the
     object during play.
   - As a coverage fact (retrospective, not point-in-time), in non-GRID events with a bo3 match:

     | Thunderpick odds in bo3.gg | events | wallet traded |
     | --- | --- | --- |
     | deep in-play snapshot | 79 | 46 (58%) |
     | shallow (pre-game-like) | 50 | 17 (34%) |
     | none | 63 | 5 (8%) |

     - Inside non-GRID events the AUC is 0.705, below the league table. 1win Private Club has 5 traded events with no
       Thunderpick odds at all. GRID events: 0 of 103 traded.
     - So Thunderpick's coverage is not the wallet's input. Thunderpick's live price is an untested candidate for its
       private value.

6. **The information effort is still aimed at the feed's identity.** Selection passes on VALIDATE (0.970 vs 0.886).
   The fan-out and the source class have been characterized over nine iterations. What blocks the target is price
   (0.32) and outcome (-0.13). The proposals below are ranked by what they can do for those two items.

## Proposals (ranked by the chance that they close the gap)

### 1. Uncensored Dota ladder on the books already recorded, on the OpenDota game clock (strong form of X119 / iteration-8 information P2; new use of data on disk)

- **Hypothesis.** The 10-share Dota ladder re-prices on game events seen on the feed's spectator clock. Its offset from
  the others' mid widens or the ladder pulls during teamfights, and after a fight it re-anchors by an amount that
  scales with the fight's gold swing. The weak results so far (kill locking 13% vs 10%; the V anchor 0.41 vs 0.43) are
  censoring and minute resolution, not absence.
- **Why it fits.**
  - Critique 3: uncensored books exist.
  - Critique 1: the missing input sets the offset, and game phase is a natural driver.
  - D_feed sits at the 900-s spectator delay plus start to horn, 1035-1050 s on four PARI maps (finding 24).
  - Filled maker orders already lean toward own-team kills (48 vs a null of 25.3 in the iteration-8 panel; 7.8% vs
    5.2% in X119).
  - OpenDota parses give teamfights (start, end, per-player gold and xp deltas, deaths), objectives (towers, roshan,
    barracks), buybacks and runes at second resolution. They are key-free, and they also exist for the h1/h2 Dota maps,
    so this is the one route to an exam-ready public state input for the price and outcome items.
- **Test.**
  1. Extract the Dota books of the three 10-31 development units with `iter_live` (hour by hour with try/except), and
     the 10-share whole-cent level changes.
  2. Validate the wallet's label against the calldata of its filled Dota orders (`dota_pub_1031`, X92 recipe).
     Group-G makers also rest 10-share orders on CS2 books, so the size alone is not proof.
  3. Fetch OpenDota matches 9069952836 and 9070062078 (ty-gl), and the other units' maps if the wallet traded them.
  4. Fit D per map with the side-label-null D-scan on the wallet's add and cancel events. The prior window is 1040 ± 60 s
     (from the PARI series; the recorder logged a 900-s delay).
  5. Classify each re-pricing burst by what precedes it on the feed's clock: own-team kill, other-team kill, inside a
     teamfight, fight end, objective, buyback, or nothing.
  6. Measure the offset (bid minus others' mid) and the ladder depth inside versus outside fights. Regress the level
     change after a fight on the fight's net gold swing.
  7. Placebo clocks D ± 120 / 300 s.
  8. Then score `last print + f(phase, swing) - s` within one tick on VALIDATE (10-22, 857 filled Dota orders), with f
     fitted on 10-31, and against the touch on the 10-31 books.
- **Data.** The shared recorder's `clob_wallets` (development block, on disk), `dota_pub_1031` calldata (on disk), and
  OpenDota `/api/matches/<id>` (key-free, cached for the ty-gl maps).
- **Signature if true.**
  - At least 50% of uncensored re-pricing bursts fall within 6 s of a parsed event, against a null near 10%.
  - Offsets are wider (or the ladder is pulled) inside fights, by at least 1.5c.
  - The post-fight level change has the sign of the swing, with a slope that is significant at the true clock only.
  - Within one tick improves on the last print by at least 0.10 on 10-22.
- **Signature if false.** Uncensored re-pricings are at the null and the offset does not depend on the phase. The Dota
  private value is then not public game state at any resolution OpenDota has, which points to proposal 2.

### 2. An external in-play price as the private value: Thunderpick's live odds through bo3.gg (strong form of X48 (b); new key-free route)

- **Hypothesis.** The wallet quotes off an external in-play price p_ext (a bookmaker's or an odds vendor's live
  probability), bidding at p_ext minus a stable margin on each token. Polymarket's mid converges to p_ext within
  seconds. This produces at once:
  - a level that leads the mid (finding 14);
  - an offset from the Polymarket mid that varies by 3c (critique 1), because it equals p_ext minus the mid minus the
    margin;
  - no public tape or game-state predictor (finding 11; X123);
  - takes when p_ext jumps past the Polymarket ask.
- **Why it fits.**
  - Critiques 1 and 5.
  - The organizers of its leagues are mostly bookmakers (1win, Stake) whose traders price in-play from official data.
  - The subscribers' maker quotes do not share its cent level (critique 2), so the value is the wallet's own or
    external, not the feed's.
  - bo3.gg's `bet_updates` is updated in play and is key-free.
- **Test.**
  1. On the next development block, write a small recorder: the `tools/live.py` `Writer` with unit-rule filing through
     `unit_writer`, so sealed-start units are filed sealed for the examiner; a hard stop; under 100 MB of memory and
     300 MB of disk; recorded in `live_lab`.
     - Poll `api.bo3.gg/api/v1/matches?filter[matches.status][in]=current&filter[matches.discipline_id][eq]=1` every
       60 s. This endpoint was verified here: 200, 1.4 KB.
     - Map each match to its Gamma event by teams and date (the `events_sel_bo3` matcher).
     - For matched development-start units, poll `api.bo3.gg/api/v1/matches/<slug>` every 3 s, at most 1 request per
       second in total. Store the receive time, both coefficients, the `active` flags, `markets_count` and
       `additional_markets`.
  2. Measure:
     - (a) the refresh cadence: distinct states per in-play minute, and suspension (`active` = false) episodes;
     - (b) the lead-lag of the de-margined p_TP against the others' mid of the match market and against the wallet's
       add levels, at -30..+30 s;
     - (c) the SD of the wallet's burst top minus p_TP, compared with 3.2c against the mid;
     - (d) within one tick of round(p_TP - δ), with δ fitted on the first half, against the touch's 0.47;
     - (e) suspensions against its untriggered pulls and takes;
     - (f) p_TP's changes against the feed's messages (P4e and member takes from the block's calldata). A bookmaker
       that follows the same vendor moves at a fixed lag after them.
  3. With the user's consent only (gambling sites' terms, geo-blocking): the same measurement on Thunderpick's own
     match page channel and, for their own leagues, on 1win and Stake. That is X48 (b) in its direct form.
- **Data.** bo3.gg API (key-free, already used), the shared books and the block's calldata. The direct bookmaker
  probes need consent.
- **Signature if true.**
  - p_TP leads the Polymarket mid by seconds.
  - The wallet's top minus p_TP has an SD of at most 1.5c.
  - Its level changes and takes follow p_TP changes at a short, fixed lag.
  - Within one tick reaches 0.6 or more on match markets. The recording then becomes an exam input for the future
    blocks.
- **Signature if false.** If p_TP trails the Polymarket mid (the bookmaker follows the exchange), or the wallet's offset
  to it is as wide as to the mid, Thunderpick is not the input. A slow refresh (30 s or more) still allows (c) and (d)
  but not timing.

### 3. The offset driver on the feed's own clock: message phase and intensity, then its earliest public echo (strong form of iteration-9 finding 11 and the `price_offset_model`)

- **Hypothesis.** The wallet sets its spread from event hazard. It quotes close to its value in quiet phases (freeze
  time, farming) and further away, or pulls, while messages are arriving or an event is pending. The ±3c offset of
  critique 1 is that spread. The feed's message stream is the input. Part of it is public: the fan-out of P4e, group P,
  group G and the slow trio at fixed lags.
- **Why it fits.**
  - Critique 1 (the offset carries most of the price gap).
  - Critique 2 (adds cluster on event moments).
  - The untriggered re-pricings (X94, X107) and the 1.5-s re-post timer (X79).
  - Finding 11 put member takes into a tape model at their public block time only. It never measured the ceiling at
    the true message clock, and never used the earlier publication on the CLOB socket.
- **Test.**
  1. Ceiling, descriptive. On BUILD-live CS2 (2,740 adds), rebuild the message times from every decoded member take on
     the seven books and their siblings: signing time minus the member's known lag behind P4e. Regress the add's offset
     from the others' mid, and its burst depth, on:
     - time since the last message (any team, own team);
     - messages in the last 5 / 30 s;
     - the last message's direction for the token;
     - match versus map.

     Report the residual SD against 3.2c and the within-one-tick gain.
  2. Only if the ceiling clears 0.10 over the touch, the point-in-time form:
     - the same stream as first published: the shared recorder's `x` records give each member take at server match
       time, about the signing time plus 1.04 s, with its transaction hash;
     - the hash's calldata gives the taker's identity and limit price. Check whether a pending transaction is
       readable before mining, with `eth_getTransactionByHash` on the record's hash in the first second;
     - block time is the historical (h1/h2) form;
     - score on BUILD-live and pre-register for VALIDATE-live.
- **Data.** On disk: `linked_adds_dev`, `others_mid_dev`, the decoded member transactions behind `feed_member_adds.py`,
  and the shared `clob_wallets` `x` records. Polygon RPC (publicnode) for the pending-transaction check on a
  development block.
- **Signature if true.**
  - Phase and intensity explain at least 40% of the offset variance at the true clock.
  - The point-in-time echo, about 1.1 s late, keeps at least half of that.
  - Within one tick rises 0.10 or more over the touch.
- **Signature if false.** No phase dependence even at the true clock. The offset is then own state (pair cap,
  inventory; mechanics) or an external price (proposal 2).

### 4. Who re-prices with it: subscriber makers and joiners as the control for finding 14 and as instruments (new; Polymarket's own books)

- **Hypothesis A (shared timing, own levels).** The feed's subscribers re-price their maker quotes on the same messages
  at their fan-out lags. The wallet's apparent lead is mostly its position in the fan-out (P4e first, the wallet
  +50 ms, group G +150-230 ms, the trio +540-600 ms).
- **Hypothesis B (followers).** Pegging bots join its visible bid 50-125 ms later and move the mid mechanically.
- **Hypothesis C (unique value).** Its level carries information no other maker has.
- **Why it fits.** Critique 2:
  - joiners at 20-45x the null;
  - peaks at +50-75 ms;
  - slow-trio 5-share and group-G 10-share maker orders on the same books;
  - 0x2e3c40fa (the X34 cancel-wave maker) is the main 20-share joiner;
  - only 12-18% of co-movers sit at exactly its price.
- **Test.**
  1. Attribute other adds to makers by size and by the calldata of their fills (X92 recipe).
  2. For each attributed maker, measure:
     - its lag behind the wallet's add and behind the rebuilt feed message (proposal 3). A fixed lag behind the message
       makes it a subscriber; a lag behind the wallet's visible add of socket latency plus tens of ms makes it a
       follower;
     - its own add-level informativeness (Spearman of offset against the 10-s others'-mid move, as in
       `add_level_info.py`).
  3. Recompute finding 14 with:
     - the mid built without the subscriber makers and without joiners in (0, 2] s;
     - the move split into bid-side and ask-side parts. Pegging moves bids; information also moves the asks of the
       token, that is, the complement's bids.
- **Data.** On disk: `linked_adds_dev`, `level_events_dev`, `calldata_dev`.
- **Signature.**
  - A: subscriber makers about as informative as the wallet and later by their fan-out lag, so the edge is the
    feed's position.
  - B: the 2-s effect collapses once joiners are removed, while the 10-30-s effect survives.
  - C: its 10-s Spearman stays at 0.3 or more against at most 0.15 for every subscriber maker, with ask-side moves.
- **What it decides.** Whether the price item needs the feed itself (A, C) or is partly a mechanical artefact (B). It
  also gives an honest number for the wall account.

## Ranking note

- Proposal 1 is runnable today, attacks the price item in the title that carried most of the recent fills, and uses
  the only fine-grained public game data that also exist for the exam lots.
- Proposal 2 is the one information class never obtained. It is the most direct explanation of a level that leads the
  mid with a variable offset, but it can only be checked from the next development block on, and it helps only the
  future exam rounds.
- Proposal 3 measures the ceiling of the feed's own message stream for the offset before any point-in-time
  engineering.
- Proposal 4 does not raise a metric, but it decides how much of finding 14 is information.

All four need only development data and key-free endpoints. The direct bookmaker probes (proposal 2, step 3) and the
CS2 demos (critique 4) need the user's consent.
