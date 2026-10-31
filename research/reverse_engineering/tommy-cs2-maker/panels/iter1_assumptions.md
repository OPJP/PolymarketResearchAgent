# Panel, iteration 1: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. That covers the unit of decision, pooled
regimes, where the PnL comes from, the metric and its baseline, and whether the inputs exist for the exam.

I read BRIEF.md, NOTES.md, state.json, FINAL_RULE.md, results/*.json and the mechanics panel
(`panels/iter1_mechanics.md`, same round). I then ran small read-only checks on `.cache/re/tommy-cs2-maker/`:
orders, calldata_all, calldata_pub, chain fills, taker tapes, universe and activity. I also read the dev-block
`sports` recording through `iter_live`, and fetched one bo3.gg game.

All numbers below pool BUILD and VALIDATE (development data before H). They are exploratory, not VALIDATE
results. Nothing sealed was read. The mechanics panel already proposes four directions:

- round-level event sniping, with the pack as the event clock;
- fill-triggered child orders on the match clock;
- the take-then-make pair unit;
- stale-depth selection and owner clustering.

I do not repeat them. Where my checks corroborate them, I say so in the critique.

## Critique: assumptions that look false

1. **"It predicts the round in progress about 30 s early" is an artifact of the test.** The mechanics panel
   showed that `next_jump.py` cannot see jumps less than 10 s out. I measured the price path directly. Take
   the mean public price of the bought team, signed, relative to the last public print before its taker
   *signing* (wallet transactions excluded). The wallet's 1,630 taker orders, against random times in the
   same markets:

   | horizon | -60 s | -2 s | +2 s | +4 s | +6 s | +10 s | +30 s | +120 s |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | mean move | +1.06c | +0.07c | -0.07c | **+1.01c** | **+1.94c** | **+2.60c** | +3.40c | +4.59c |
   | control | -0.14c | -0.01c | +0.01c | +0.05c | +0.09c | +0.08c | -0.02c | -0.07c |

   - At +10 s, P(move >= 2c in its favour) is 0.42 vs 0.07 in the control.
   - Excluding the prints of the pack (0x4ebc2722, 0x93078b5d, 0xfe8a28be, 0x2529c68d, 0x72aaaaf9, 0x2005d16a,
     0xf1ee4842, 0x8a80528d, 0xddb6e624), the move is still +1.85c at 10 s and +4.22c at 120 s. So it is not the
     pack's own impact.
   - The path is the same for 1000/2000 and odd sizes (+2.72c vs +2.56c at 10 s), on BUILD and VALIDATE (+2.90c
     vs +2.35c), on map and match markets, and on every day.

   The market reprices 2-10 s after the wallet decides, with nothing before. The "+5-s markout -0.14c" is
   measured from the block time and the fill price, about 3.4 s after the decision and 1c above the touch.
   So the target is a sharply timed event, not a 30-s prediction. In-round state 30 s before a round end, the
   RE's next step 2, is the wrong window to search.

2. **"Taker earns about 70% of the PnL; the maker is ordinary and adversely selected" splits hedged legs.** I
   settled every fill at the Gamma outcome, per market (229 markets).
   - Per-market maker-leg PnL and taker-leg PnL correlate **-0.85** (Spearman -0.78).
   - The per-market standard deviation is $447 for the maker legs and $440 for the taker legs, but only $242
     for the total.
   - The legs are two halves of one position: the taker buy of X, and the complement bids on Y that the pack
     fills about 1 s later.
   - So per-role attribution says nothing about where the money comes from. The maker fills look adversely
     selected because the re-pair legs are, by construction, on the team that just lost the event.

   It also matters for the target. The per-market correlation with the total is 0.30 for maker-only PnL
   (Spearman 0.34) and 0.22 for taker-only PnL (0.12). **No single component can reach `pnl_corr >= 0.5`.**
   Only an executable position path can.

   My settlement also does not reproduce the RE's numbers:
   - mine: maker +$3.85k and taker +$14.2k gross. The taker fills also carry $3.55k in the OrderFilled `fee`
     field (2.5% of $155k notional), and the maker fills carry $0;
   - the RE's: +$4.0k / +$9.1k, total $13.1k vs my $18.0k.

   Reconcile the units of the fee field (USDC or outcome tokens), the settlement source and the merges before
   any attribution claim.

3. **The 16-22 Oct sample is assumed to be "the strategy".** The wallet was a pure CS2 taker from 06-16 to
   10-15, with about 100k trades. The significance screen almost certainly ran mostly on that period. Its
   taker rebate on 10-15 (for 10-14) is $868, against $10-481 per day afterwards.
   - The investigation decoded the trigger on 1,698 orders from 7 days of a regime that was new and still
     changing:
     - the share of 1000/2000-share orders falls from 52-64% to 12-17%;
     - 10-share maker orders appear only on 10-22;
     - 10-18 had 3 active hours.
   - It never fetched calldata for the taker regime, which is development data with perhaps 10-30x the orders.

4. **The exam inputs are assumed to exist.** The first two exams use h1 and h2 (10-23..30). The live recorder
   started on 10-31, so no `sports` or book recording exists for them. bo3.gg gives no wall clock: I checked one
   game that began at 00:38. Its round records have `created_at` = `updated_at` = 07:02:55.200-.233 the next
   morning, all within 33 ms, i.e. written when the demo was parsed. The sports websocket messages carry only
   these fields: `gameId`, `leagueAbbreviation`, teams, `status`, `score` ("6-3|0-0|Bo3"), `period`, `live`,
   `ended`, `elapsed`, `finishedTimestamp`. There is no source timestamp.
   - **A trigger keyed to a game feed can therefore only be examined on future blocks.** On h1/h2 the only
     public event clock is the chain: public takers' signing ms, and match times rebuilt from the calldata.
   - That clock is legitimate for rules that act at or after a public match, such as the +1 s requote. It is
     not legitimate for the wallet's own taker decision, which comes before any public print.
   - The plan should say which components will be judged on which lot.

5. **The presence target is structurally co-occurrence.** Inside a selected event it quotes from game start,
   and fills arrive with other takers. A fill-per-30-s-bin target can never beat the activity baseline by
   0.05. The winnable routes are:
   - selection at the event level (lift >= 3 needs precision >= 0.9 at a 30% base rate);
   - the signing-level unit the mechanics panel proposes.

   The selection unit should be the event: it trades 97% of the markets of a traded event, so market-level AUC
   counts each decision three to five times.

6. **Quick negatives, so nobody redoes them:**
   - **Capacity cap.** P(traded) for whitelisted events against the number of whitelisted events already live
     by schedule is flat, 0.32-0.65 for 0-6 live events.
   - **On/off sessions.** 60 of 72 skipped whitelisted events fell while the bot was active in another event.
   - **Own-cost anchor of the whole ladder.** Price + the opposite token's last fill price has an IQR of 0.10,
     no better than the last-print offset (IQR 0.08). This is consistent with the mechanics finding that the
     anchor works only for children within about 2 s of an own fill.
   - **Within-league patterns** that are left for proposal 1:
     - DraculaN's traded share rises by day: 5/20, 7/15, 9/12, 3/4;
     - 9 of 12 DraculaN Bo1 events are skipped;
     - NODWIN is traded at about one event in three every day;
     - 9 of 24 DraculaN teams appear in both traded and skipped events, so it is not a team list.

   **Corroboration of mechanics P1-P3:**
   - Opposite-token maker signings after its own taker signing: 0 in [-0.5, +0.9) s, then 625 in
     [+0.9, +1.1) s.
   - The top re-pair bid plus the taker limit is 0.95-0.96 in 54% of cases, and within 1c of 0.95 in 65%
     (393 orders).
   - After 4,536 pack events with no own taker order, its opposite-team re-signs peak at
     [+1.00, +1.25) s after the pack's first signing: 725, against about 44 per 0.25-s bin at random times.

## Proposals (ranked by the chance that they close the gap)

### 1. Selection is the coverage of the round-level event feed, not a league preference

- **Hypothesis.** It quotes and takes only in games where its live round-event feed works. Without the feed
  its ladder would be picked off by the pack at every round event, as happens to stale makers.
  - The likely source is Polymarket's sports socket, or the provider behind it: `gameId` is the PandaScore id.
  - Coverage is set per organiser or data-rights holder. CCT is run by GRID's organiser arm, and
    ESEA/ESL Challenger by ESL FACEIT Group. These skipped leagues may lack round-level data at that provider.
  - The partial leagues (DraculaN 24/51, NODWIN 6/23, Stake Ranked 8/14) would be explained by per-match
    coverage.
- **Why it fits.**
  - It trades whole events from game start, and never pre-game.
  - The whitelist does not follow the hour (CCT 0/59 inside 09-19 UTC), the tier or the teams.
  - Its taker and maker actions are keyed to round events that a feed broadcasts with 50-300 ms dispersion
    (critique 1; mechanics critique 4).
  - Some sports-socket messages carry only a map score ("000-000|1-1|Bo3"). So round-level coverage varies.
- **Test.**
  - (a) **Live lab, now.**
    - Take every CS2 game whose start lies in a development block. It does not have to be in its leagues. Map
      `gameId` to the Gamma event (`pandascoreMatchId`) and then to the league.
    - From `sports` (`iter_live`), measure the share of map time with round-level scores, the number of
      distinct round-score states per map against the rounds played, and the gap between updates.
    - For its own events, measure the delay from the first round-level update to its first order: does it
      start only once round scores flow?
  - (b) **History, pre-H, with no live data.** Use the pack as the coverage proxy.
    - Count, per map of every CS2 market of 16-22 Oct, the in-play pack event clusters per round played (bo3.gg
      `rounds_count`). The taker tapes of untraded markets are already fetched.
    - Coverage predicts about one cluster per round in its leagues and about zero in the skipped leagues.
    - The mechanics stale-depth hypothesis instead predicts that the pack is present but unprofitable there.
  - (c) If coverage separates the events, look for a listing-time proxy for the exam: Gamma event fields, the
    pre-game sports message, or the PandaScore tier in `eventMetadata`. Score it at event level against the
    activity baseline.
- **Data.** The `sports` recording (dev blocks), the Gamma listing projection, the tapes on disk, bo3.gg
  `rounds_count`.
- **Signature if true.**
  - Round-level coverage is close to 100% in its leagues and close to 0 in CCT, ESEA, ESL Challenger, United21
    and EPL.
  - The pack is absent where coverage is absent.
  - Inside DraculaN, NODWIN and Stake Ranked, the skipped events lack coverage.
  - An event-level selection rule reaches precision >= 0.9 at recall >= 0.6, with a gain over the pre-game
    activity baseline of 0.05 or more.

  If coverage is uniform across leagues, the gate is a private feed, and the selection is that feed's league
  list.

### 2. Decode the taker trigger on the taker regime (06-16..10-15), where the screened profit and most decisions are

- **Hypothesis.** The 16-22 Oct taker orders continue a months-long CS2 taker strategy. That regime holds:
  - most of the profit that passed the significance screen;
  - 10-30x more taker decisions, with the same trigger.

  The maker module is a 7-day add-on and still changing (critique 3).
- **Why it fits.**
  - The taker orders carry the same sizes (1000/2000), the same limits (touch + 1c) and the same in-play-only
    behaviour.
  - The taker rebate for 10-14 alone ($868) exceeds every later day.
  - The current sample is too small to settle the trigger. The taker settlement edge has p = 0.16 and 0.21,
    and bo3.gg aligned only 13 maps.
- **Test.**
  - (a) Fetch the activity (cursor paging) and the V2 OrderFilled logs (topic2 = wallet) back from 10-15. Start
    with 10-01..10-15, then sample back to 06-16. Note: V1 before the V2 switch, so verify the exchange from a
    receipt.
  - (b) Decode the B1 calldata (publicnode, batches of 40; about 10-15k transactions for 10-01..15).
  - (c) Repeat the 1-s price-path event study of critique 1, the event-per-round count, and the signing-ms offset
    against 0x4ebc2722 and the cluster (did they exist before 10-16?).
  - (d) Compare the leagues traded against the maker-regime whitelist.
  - (e) Build a daily net PnL series (settlement, fees, rebates) by regime, from activity clamped before H.
- **Data.** Public activity, Polygon logs and calldata, taker tapes of those markets, bo3.gg rounds for the maps.
  All before H.
- **Signature if true.**
  - The same flat-then-jump path (+2-3c within 10 s), the same leagues and the same sizes: one trigger with 10x
    the sample for alignment and fitting. The taker regime carries most of the history's profit.
  - If the leagues or the path differ, the 10-16 switch is a strategy change (a new feed or deal, C4b), and
    pooling the regimes would be wrong in the other direction.

### 3. The outcome target needs the position path, not a decoded trigger: replay the inventory, test on the residual

- **Hypothesis.** Per-market PnL is set by the unpaired residual at settlement. That residual is about -$8.4k
  and ends on the loser 68% of the time. Hedged leg pairs and the end-of-map inventory produce it, not the
  per-leg edges (critique 2).

  An executable rule that reproduces the residual can reach `pnl_corr` without the hidden trigger. A rule that
  decodes only the trigger cannot.
- **Why it fits.**
  - Leg PnLs correlate -0.85 per market.
  - Single-leg correlations with the total are 0.30 and 0.22.
  - It never sells.
  - The residual is 29% of max |net| at the median.
- **Test.**
  - (a) Decompose each market's PnL into the locked pairs (pairs x (1 - pair cost)) plus the residual x
    (payoff - cost), and report each part's share of the per-market variance.
  - (b) Replay a generic two-sided ladder against the full matched-order record:
    - 100 shares on whole cents at the touch minus k, both tokens;
    - re-sign at each public match + 1 s;
    - merge pairs, hold the rest.

    The record is `calldata_pub`: every matched order with signing ms, so the touch can be rebuilt from all
    makers' matched orders.
  - (c) Report the per-market Pearson and Spearman correlation with the wallet, with and without its own taker
    orders injected as given. The variant with injected orders is an oracle and only diagnostic.
  - (d) Regress the residual's sign and size on public state in the last 10 minutes of each map.
- **Data.** On disk (calldata_all, calldata_pub, chain fills, tapes, outcomes).
- **Signature if true.**
  - The residual explains most of the per-market PnL variance.
  - The generic ladder replay already reaches a correlation of about 0.4-0.5, and the injected taker orders
    add little.
  - Then the outcome target is attainable with a tape and chain-evaluable rule, and the trigger can stay a
    tagged hypothesis.

  If the replay correlation stays near 0, the residual comes from its inventory skew (67% of fills on the
  short side). Decode that rule next, on the match clock.

### 4. Plan the claim around which inputs exist on each exam lot

- **Hypothesis.** The current plan decodes the taker trigger from a live feed (the sports socket, the books).
  It will produce a rule whose key input does not exist for h1 and h2 (critique 4). The first two exam
  rounds would then fail for lack of input, not for a wrong rule, and every failed round raises the bar.
- **Why it fits.**
  - Recordings start on 10-31.
  - bo3.gg has no live timestamps.
  - The sports socket has no source timestamps, and its feed history is not available (unverified; see the
    test).
  - The only clock rebuildable for [H, T0) is the chain: public taker sign_ms plus the 1-s in-play delay, which
    gives the match time.
- **Test.**
  - (a) Check for any historical, timestamped round-event source:
    - a REST history on `sports-api.polymarket.com` (game or score endpoints);
    - Gamma event score fields that update in-play;
    - stream or VOD chapters.

    Record each failing request as infeasible evidence.
  - (b) Run `final_rule.evaluate` on development data with the live inputs removed. Show which metrics survive
    on tape, calldata and listings alone.
  - (c) Decide, before claiming, which components are claimed on h1/h2 and which only on the future-block exam:
    - h1/h2: event-level selection, the match-clock requote, prices relative to the rebuilt touch, and the
      position-path PnL;
    - future blocks: the taker trigger with the sports feed.

    Tag each component accordingly.
- **Data.** Probing requests only. The development-period evaluate run.
- **Signature if true.**
  - No historical event clock exists, and the metrics without live inputs equal the current ones.
  - The h1 claim should then rest on selection, price and the position path.
  - If a history source does exist, it becomes the most valuable data in the study, because it gives the
    trigger's wall clock for all of 06-16..10-22 (it combines with proposal 2).

## How to reproduce my quick numbers

- **Price path.** For each taker order (`orders.parquet`, role taker), load `tapes/<cid>_tkw.parquet`. Drop the
  wallet's own transactions (`calldata_all.maker == wallet`) and, for the robustness row, the pack's
  `proxyWallet`. Express the price in outcome 0, take the last print at or before `sign_ts`, then the last print
  at or before `sign_ts + h`, and sign the difference by the bought outcome. Control: the same order shifted by
  U(-900, 900) s.
- **Leg correlation.** Chain fills (`common.chain_fills`), settled at Gamma `outcomePrices` from
  `markets_dev.json`. Per-market sum of `shares * pay - usdc` by role. Pearson and Spearman correlation of the
  two columns, and of each with the sum.
- **Re-sign timing.** Maker orders' `sign_ts` minus the same market's taker-order `sign_ts`, split by token.
  Pack events are the first signing in each 10-s cluster of public BUY taker orders (`calldata_pub`,
  `idx == -1`) by the pack addresses per (market, token).
- **Concurrency.** Whitelisted events (leagues with at least one traded event). Scheduled duration is 2.5 h if
  the event has 3 or more markets, else 1 h. "Live" means scheduled start <= t < start + duration.
- **bo3.gg.** `/api/v1/games/<id>/rounds` for the first game of `/api/v2/matches/finished?date=2026-10-21`:
  round `created_at` / `updated_at`. Its `game_round_team_clans` also gives `team_side`, `kills`,
  `first_kills`, `players_count` and `equipment_value` per round. Use these for the T-side and first-kill
  tests once the rounds are aligned.
