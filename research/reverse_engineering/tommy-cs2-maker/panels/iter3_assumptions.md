# Panel, iteration 3: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. That covers the target and the unit of
decision, who the "pack" really is, one operator or several, the metric and its pivot rule, and the input class
of the taker leg.

## What I read and what I ran

I read `BRIEF.md`, `NOTES.md` (iterations 1-3), `state.json` (catalog X1-X36, hypotheses H1-H34),
`FINAL_RULE.md`, the six earlier panel files, the strategy dossier and the wallet report
(`research/wallets/0x0063.../REPORT.md`). There are no EXAM or wall-audit files.

I ran four small read-only checks:

- on `orders.parquet` (16-22 Oct, development data);
- on the own recorder `tommy_cs2_near` (10-31 development block, 14:50 to about 17:15 UTC, server clock), limited
  to the wallet's development-unit markets in `dev_markets.parquet`, with `calldata_dev.parquet`.

Nothing sealed was read, and I fetched nothing except one web search. The scripts are in my scratchpad:
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/p3/`
(`concurrency.py`, `cascade.py`, `cascade2.py`, `pulls.py`, `pulls2.py`). Live samples are small (40 wallet takes),
so treat those numbers as leads.

## Critique: assumptions that look false or unproven

### 1. "Nothing public precedes its signing" was tested on a quarter of the event's markets

- The 80 events it traded in 16-22 Oct hold 1,651 markets. Of these, 1,220 are round markets, which it never
  trades: round handicap and total-rounds over/under for each map (`smt` `round_handicap_game_k`,
  `round_over_under_game_k`).
- The own recorder records only match and map-winner markets. `presign_public.json` ("any market of the event")
  therefore covers only those.
- Round markets reprice on exactly the in-round swings the taker leg trades. Their makers can cancel at once,
  while takers wait out the 1-s delay. A fast maker pulling round-handicap asks before its signing would be a
  public trigger that nobody has looked at.
- Separately, the fact that it never trades these markets is itself a clue about its input (proposal 2).

### 2. The own-cancel coupling is undercounted, so part of the "other makers' wave" is the wallet

The coupling test looked only for 100-share cancels. I listed the cancels in the 40 ms after each take, other
than 100-share cancels:

- In 15 of the 21 takes counted as "no own cancel", a pull of 3-5 levels follows at +13 to +22 ms after its
  signing. All levels in a pull have one size: 68 shares (one event) or 54 or 58 shares (another event). These
  are its own ladder at an inventory-scaled size. In total, 34 of 40 takes are followed by such a pull of its
  own ladder, not 45-61%.
- In takes with 100-share pulls, some cancels of other sizes land at the same time or earlier: 168 shares at
  +3 ms, 31.26 at +5 ms, 45 at +9 ms, 460 / 199 at +11 ms, 340 / 180 at +12 ms.
  - 168 = 100 + 68, and the fractional sizes look like remainders of partly filled orders. So these may also be
    the wallet's own levels.
  - With size-only attribution it is not settled whether any other maker cancels before the wallet's own pull is
    public (+11 to +14 ms).
- The p10 of +17 ms for "other makers' cancels" is contaminated by its own non-100 levels. Two conclusions rest on
  attribution that has not been done:
  - "the fastest cancellers act on the same external event within a few tens of ms";
  - the dismissal of U3 (stream reader) because offsets are only tens of ms wide.

### 3. The "pack" contains book readers, so pack timing and pack presence are not evidence of a shared feed

- **The 3-wallet cluster** (0x72aaaaf9, 0xfe8a28be, 0x2529c68d) behaves like one bot run from three wallets. In
  16-22 Oct each wallet has about 300 follows of the wallet's takes, with lag p10 374-383 ms and p50 464-475 ms,
  and 15.8-16.5% of its takes are such follows.
- **On the 10-31 block** (57 cluster takes in the wallet's markets):
  - only 16% follow a wallet take;
  - 88% of the others come after a cancel on the consumed side in the previous 600 ms (about 23% expected at
    random), with lag from that first cancel p25 / p50 of 349 / 393 ms;
  - after the wallet's pulls it signs at +364 to +373 ms (very few cases).
- This is a book reader with a fixed latency of roughly 350-400 ms. It trades on cancel waves, whoever starts
  them.
- **Consequences:**
  - "pack signs 0.2-0.5 s after the wave" is not a second subscriber of the wallet's feed;
  - "every traded non-GRID event had the pack in play (100% vs 50%)", and the lagged pack-presence selection
    feature, partly measure where informed leaders pull quotes. One of those leaders is the wallet itself.

### 4. The primary metric and the pivot rule point at the wrong gap

- `presence_auc` (fill per 30-s bin) is bounded by co-occurrence. The target can be met through selection
  instead, and selection already passes on VALIDATE.
- The binding failures are:
  - price: 0.305 against 0.80;
  - outcome: -0.12 / -0.06 against 0.5;
  - replication of the selection gain.
- The rule "if the next iteration brings < 0.01 on presence_auc, pivot" therefore tracks a number that does not
  decide the exam.
- Also check the reading of the replication rule. The brief says every threshold "holds within 0.03" on each
  half. That reads as a slack on the threshold, not as two halves within 0.03 of each other. Under that reading,
  the 10-21 gain of +0.034 does not fail by itself.
- Whatever the reading, h1/h2 have no books. Price and outcome must be scored there from tape and calldata only,
  so the server-clock price findings cannot carry the h1 exam.

### 5. Quick checks that came out negative, so nobody redoes them

- **No single attention / human spotter.** For 1,635 taker decisions (fan-out legs merged) in 148 pairs of
  traded events live at the same time (more than 20 min of overlap), I measured how often the other live event
  has a decision within ±w, against a null that circularly shifts each event's decisions within its own quoting
  span (300 draws):

  | Window | Ratio of observed to null | P(null <= observed) |
  | --- | --- | --- |
  | ±5 s | 0.95 | 0.38 |
  | ±30 s | 0.97 | 0.36 |
  | ±120 s | 1.04 | 0.80 |

  Taker decisions per event-hour against the number of traded events live at once: 10.2 / 9.95 / 7.1 / 10.4 /
  8.6 / 7.2 / 5.8 for 1-7 events, with the same shape in maker orders (157 to 101 per hour). So decisions in
  different events are independent. Its input covers several matches at once: it is not one person or one
  pipeline watching one stream at a time.
- **Pulls without a visible take are mostly not the same signal.**
  - 171 pulls on the own recorder: bursts of at least two 100-share cancels on one side within 5 ms, with no
    100-share re-add within 500 ms.
  - 12 follow a wallet take (5 levels on average). The team whose asks were pulled moves at least +2c in 10 s in
    83% of them, and at least -2c in 17%.
  - The 159 pulls without a take show +2c 24% / -2c 14%; random times show 7% / 7%.
  - So at most a modest number of invisible attempts exist, perhaps about as many as the visible ones.
- **The screen period is mostly the old taker regime.** The 105-day significance screen is mostly the old taker
  regime (report: "pre-selection 105d"; the taker regime was positive only through the Obsidian taker rebate). The
  maker regime's case rests on 13 days ($43.7k, every day positive). This matters for the claim, not for the
  decode.

## Proposals, ranked by the chance they close the gap

### P1. Extend "nothing public precedes" to the round markets of the same map (new)

- **Hypothesis.** Fast makers and informed takers in the round-handicap and total-rounds markets react to the
  in-round event before the wallet signs, or at the same moment. Those books, not the match and map books, carry
  the first public trace.
- **Why it fits.**
  - Critique 1: 1,220 of the 1,651 markets in its events are round markets that nobody recorded or decoded.
  - A round handicap reprices on every round swing.
  - The wallet is first among same-team signers only in its own market.
- **Test.**
  - (a) Historical, VALIDATE events (10-21..22):
    - fetch the taker tapes (data-api `/trades`) of the round markets of each map in which the wallet took;
    - decode the calldata of their taker transactions (publicnode, batches of 40) to get signing ms;
    - map each round market's side to the team: handicap yes/no gives it; over/under is used as an event clock
      only.
    - For every wallet take, measure the share with a round-market taker signing in [-1,000, 0) ms, and in
      [-200, 0) ms, against random times in the same maps.
    - Report who those signers are and their markouts.
  - (b) Live: add the round markets of non-GRID events in play to a recorder. Either widen the own recorder's
    subscription list, or start a small `live.Writer` recorder with a hard stop. Use the 11-01 development blocks
    and repeat `presign_public` on the server clock with these books included.
- **Data.** `universe.parquet` (round-market cids), data-api trades, Polygon calldata, and a live recording.
  Development units only.
- **Signature if true.** Cancels or signings in round markets lead its signing in well above the random 14-15%
  (e.g. 50% or more within 200 ms) on the same team. That gives a public taker trigger, testable on h1/h2 through
  signing ms.
- **Signature if false.** No excess. "Upstream of every Polymarket feed" then holds for the whole event, which
  is part of the quantitative wall account.

### P2. The input is a live odds or win-probability feed, not raw game state (new input class)

- **Hypothesis.** The taker leg reacts to an external price (a bookmaker's in-play odds or a data provider's
  win-probability stream for match and map) rather than to kills or rounds. That would explain four things:
  - why it trades only match and map winners;
  - why its FAK limit is a target price;
  - why it never trades events without a stream;
  - why it lost in GRID events, where bookmakers and Polymarket makers share official data.
- **Why it fits.**
  - It never trades the round markets (critique 1). A bot with raw state (kills, man advantage, economy) could
    price them too.
  - Its limit is the pre-event ask + 0-5c and its size about 0.31x the pre-event depth: "buy up to a new fair
    value".
  - Events with only hltv.org as their resolution source (no stream) are never traded (0/12). Bookmakers rarely
    offer in-play markets without a stream.
  - It covers several matches at once (critique 5).
- **Test.**
  - (a) On disk (VALIDATE, 1,698 taker orders):
    - take the limit premium = limit minus the lowest maker price filled in its transaction (a proxy for the
      stale ask);
    - regress the bought team's public move at +10 / +30 / +60 s on that premium, against the same with other
      takers' premiums.
    - A model price shows as premium predicting the size of the move, and the move levelling off near the
      limit. A rule of "ask + k" gives no relation.
  - (b) Probe in-play odds sources for its tier-3 events and record every failing request as evidence:
    - on-chain sportsbooks with public subgraphs or sockets (Azuro, Overtime; verify that endpoints and esports
      coverage exist);
    - frontend odds endpoints of the bookmakers that run its leagues (1win, Stake) and of Thunderpick, GG.bet and
      Pinnacle. Check their terms; no logins;
    - an odds aggregator with esports in-play data. odds-api.io advertises CS2 live odds over WebSocket with a
      free key tier. This needs the user to supply a key, so ask in chat.
  - (c) Where an odds stream is obtained, measure on the development blocks the lead-lag of odds-change or
    suspension times against its signing (server clock).
- **Data.** `orders.parquet`, `calldata_all`, tapes (on disk); probes; live odds recordings via `live.Writer`.
- **Signature if true.** The premium correlates positively with the later repricing (0.3 or more). Some odds
  source updates a near-constant 50-300 ms before its signings in 80% or more of takes. The selection boundary
  then becomes "events with in-play odds at that source".
- **Signature if false.** No premium-move relation, and the odds sources lag it. That points back to raw-state
  feeds (provider scouts or stream CV; P3).

### P3. Attribute every early cancel at order level: is the wallet the only fast leader? (strong form of X21 / X34)

- **Hypothesis.** All cancels in the first ~40 ms after its signing are its own: 100-share pulls, inventory-scaled
  pulls of 54-68 shares, and remainders. Every other maker and the pack react to its public pull. If so, it is the
  only fast actor in these books, the "shared feed" inference is void, and U3 (stream or CV reader) is open again.
- **Why it fits.** Critiques 2 and 3:
  - its own pull follows 34 of 40 takes;
  - cancels at +3 to +12 ms have sizes that decompose into its own levels;
  - the 3-wallet cluster is a book reader at about +350-400 ms;
  - other cancels at p25 / p50 of +67 / +124 ms are ordinary reaction times to a message at +13 ms.
- **Test** (own recorder, development blocks).
  - Rebuild the wallet's resting quantity at each price level of each token from its level additions. Use the
    ladder fingerprint: whole-cent adds of 100 / 68 / 54 / 10 shares at +19 to +24 ms after its signed orders
    (`ladder_decode`), extended to unfilled bursts by the equal-size multi-level pattern.
  - Assign each decrease to the wallet up to its resting quantity at that level; the remainder goes to others.
  - Report:
    - (i) the share of takes with any non-wallet cancel before its first own cancel message;
    - (ii) the distribution of others' first-cancel lag measured from its first own cancel, and whether it has a
      hard floor;
    - (iii) the same lags for waves led by others (pack takes without a wallet take): who leads those, by
      fingerprint.
  - Also compare the cluster's lag dispersion measured from its signing and from its first cancel, on fan-out
    match-market legs where the pull may come at a different time.
- **Data.** `tommy_cs2_near`, `calldata_dev`. Then the 11-01 development blocks for more takes.
- **Signature if true.** (i) is about 0. (ii) has a floor of a few ms and a mode at 30-150 ms. Pack timing then
  says nothing about the input. The stream clock (X4 / X22) becomes the single decisive test and should be put to
  the user with this evidence.
- **Signature if false.** Identified other makers cancel before its pull is public in a sizeable share of takes.
  Their identity and the events they cover then become the selection and input lead (C1 / C3 on those makers).

### P4. Make the pull the unit of the taker decision and test the event type without a clock (strong form of iter-2 P1 / X30 and of X8 / H32)

- **Hypothesis.**
  - Its pull of the complement ladder is a public, fill-independent record of its signal. FAKs that find nothing
    leave no trace, but a pull does.
  - The signal's team sequence per map follows a specific in-round event, such as opening kills.
- **Why it fits.**
  - The pull follows 34 of 40 takes at +11 to +22 ms.
  - Pulls without a take carry a small directional excess (critique 5).
  - X30 tested censoring only through other makers' collapses, the weak form.
  - X8 is blocked "for lack of a clock". A per-map count or order test needs none.
- **Test.**
  - (1) Using P3's attribution, list all of its pulls, with or without a fill at +1.04 s. Measure:
    - signals per map and per bo3 round;
    - the share of signals that filled, by pre-event stale depth.
  - (2) Clock-free, on 16-22 Oct:
    - per (map, team), the number of its take events (fan-out merged; pulls on future blocks);
    - a Poisson regression with map fixed effects on that team's bo3 per-round counts: opening kills, round
      wins, bomb-plant rounds (`end_reason`), trade kills;
    - the key contrast is the 28% of rounds where the opening-kill team lost the round;
    - add an order-only variant: monotone alignment of its team sequence to each candidate label sequence
      (opening-kill team, round winner), against a null that permutes labels within the map.
  - Report the pack (P4e) the same way, as a second informed actor.
- **Data.** `orders.parquet`, `bo3_taker_rounds.parquet` and the bo3 per-round team stats already fetched,
  `tommy_cs2_near`.
- **Signature if true.** A positive opening-kill coefficient beyond round wins (p < 0.01), or alignment to the
  opening-kill sequence beyond the null. On live blocks, about one signal per round with a fill share that rises
  with stale depth. This decodes the side and event type, and gives the examiner a taker label (pulls) on future
  blocks.

### P5. The old taker regime as a natural experiment on the input's latency class (new use of X16 data)

- **Hypothesis.** Its source is slower than official GRID data but faster than everyone in non-GRID events, as a
  stream, scout or CV feed would be. In GRID events (taker regime) the market had already repriced before its
  orders matched. In non-GRID events it moves first.
- **Why it fits.**
  - In GRID events it took liquid books and lost to fees (gross about +1%).
  - It left GRID entirely on 10-16, and the switch was not a fee change.
  - The 1% of taker-regime volume in non-GRID events is a within-regime control.
- **Test.**
  - Orders in the taker regime were pre-signed, so place each match at block time minus ~2 s, bounded below by
    the newest counterparty maker order's signing ms. Use `calldata_taker` for 10-01..10-15, tapes from data-api
    (development data).
  - Measure the bought team's mean public price path from -30 s to +60 s around its match, and do the same for
    sells.
  - Compare GRID events, non-GRID events in the same regime, and the maker regime's takes (flat before, +2.6c at
    10 s).
- **Data.** `calldata_taker`, `taker_regime_txs_1001_1015`, `activity_taker`, data-api tapes.
- **Signature if true.** In GRID events most of the move comes before its match (it was late), while in
  non-GRID events it comes after. Its source is then not official-grade data; pursue stream and scout sources
  (X4 / X22, PandaScore).
- **If false.** A "flat, then jump" path in GRID events too means it had official-speed data. That favours a
  provider feed and weakens the stream reading.

### P6. One operator across wallets: read the signer EOA from the calldata (strong form of C1 / X14)

- **Hypothesis.** The 3-wallet cluster is one operator (critique 3), and possibly linked to the wallet's owner
  0x8af810f0. If so, part of the "pack fills its re-pair bids" flow is an intra-operator transfer, and per-wallet
  PnL attribution (pair margin) is misleading.
- **Why it fits.** The three wallets have identical lag distributions and follow shares. X14 stopped at "POLY_PROXY
  wallets have no owner() view". But the V2 order struct carries `signer`, which for POLY_PROXY and Safe orders
  is the controlling EOA, and the decoder discards it.
- **Test.**
  - Re-decode `signer` for the pack's and the top late makers' orders: about 100 transactions from cache or
    publicnode.
  - Compare signers, then the USDC / pUSD funding transfers into each proxy via `eth_getLogs` (topic2 = proxy)
    and their sources.
  - Then the share of its re-pair fills taken by linked wallets.
- **Data.** Polygon RPC (publicnode). An indexer key for native POL funding would need the user.
- **Signature if true.** A shared signer or funder. Treat the linked wallets as one strategy for the PnL
  decomposition and for the follower rule. If false, the cluster is an independent book reader, which simplifies
  P3.
