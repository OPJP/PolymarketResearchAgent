# Panel after iteration 13: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iterations 12 and 13 in full, earlier iterations by search),
state.json (every open catalog item, components, target metrics), FINAL_RULE.md, `iter12_information.md` and the
proposal titles of every earlier panel. I did not read the iteration-13 mechanics or assumptions panels, which are
written in parallel.

Data I used, all development (10-31 14:00-18:00 UTC, block 12-18 of T0, development by `sealed.py`):

- the RE's tables in `.cache/re/directional-maker/it13/`: `fills_posts` (1,406 filled cluster orders with their post),
  `sched_adds`, `tracer_events`, `trades` (62,630 prints with server ms from `dm_clob_raw`);
- live calldata `calldata/live1031_*` (taker orders of the cluster's fills) and `calldata/allmatch1793460000_*` (every
  match of 10-31 15:20-15:40);
- `dm_rtds` (Chainlink snapshots) and `dm_bnf` (Binance USD-M bookTicker), read file by file (hour 14 stops at its
  corrupt gzip block);
- two requests to `clob.polymarket.com/markets/<condition_id>` for the 5m and 15m windows of 10-31 14:20 (listing
  fields only).

I did not open `.cache/live/sealed/`, any sealed block, any other strategy's files, or any record after 10-31 18:00.
I added nothing to the cache. Scripts:
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i13/`
(`bump_trigger.py`, `cascade_sel.py`, `cascade_sel2.py`, `class2_futures.py`, `posture_vs_fut.py`, `ref_race.py`,
`vol_sens.py`).

My posture is the RE's form with two inputs swapped: F_up = Phi((CL(stamp <= t - 1,250 ms) - K) / (k x sigma x
sqrt(tau))), K = the mean of the Chainlink stamps in [start - 61 s, start - 2 s] (the RE showed this equals
priceToBeat), sigma = the 300-s standard deviation of 1-s changes of the Binance USD-M bookTicker mid (in $), market
reference = the Up book mid at the post from the RE's own join. The RE uses Binance spot 1-s log volatility.

## What my checks found

**C1. The side of the resting rungs (class ii) depends on the volatility scale; the quote moves (class i) do not.**

Post-time posture accuracy, 942 class-(i) and 355 class-(ii) filled orders. k multiplies the futures-mid volatility.

| k | class (i) | class (ii) |
| --- | --- | --- |
| 0.5 | 0.724 | 0.631 |
| 1.0 | 0.804 | **0.662** |
| 1.4 | **0.815** | 0.623 |
| 2.0 | 0.778 | 0.499 |
| 3.0 | 0.680 | 0.510 |
| 5.0 | 0.607 | 0.518 |
| the RE (spot log-vol x 1.4) | 0.807 | 0.507 |
| Chainlink 1-s $-vol, any k | 0.56-0.63 | 0.44-0.47 |

By half (fills before and after 16:00; class (i) n 603 / 339, class (ii) n 196 / 159):

| k | class (i) early / late | class (ii) early / late |
| --- | --- | --- |
| 0.70 | 0.766 / 0.805 | 0.709 / 0.566 |
| 1.00 | 0.766 / 0.870 | 0.714 / 0.597 |
| 1.40 | 0.788 / 0.864 | 0.663 / 0.572 |
| 2.00 | 0.773 / 0.788 | 0.337 / 0.698 |

- Class (i) stays at 0.75-0.87 for k from 0.7 to 2.0. Class (ii) swings from 0.34 to 0.72 with k, and its best k differs
  between the halves. So class (ii) is not "at chance"; it is unstable under one unidentified input.
- Class (ii) is 92% schedule sizes, a median 2.8 s old at the fill, and its fair sits a median 0.13 from the mid. For
  these rungs the level of F matters, not just its sign near the mid. They are the subset that can identify the
  engine's volatility.
- The median futures-mid volatility is $1.2 per root second. The Chainlink 1-s volatility in the noise regime is
  $10.1, which rules that source out again (as X117 (b) did).
- Market reference: the last clean print and the book mid disagree on only 1.3% (class i) and 6.5% (class ii) of posts.
  Where they disagree the last print wins 0.92 / 0.91 (n 12 / 23). That is too few to matter.

**C2. 78% of the filled orders were posted inside the 10-s bin in which they filled.**

| bin | all | class (i) | class (ii) |
| --- | --- | --- | --- |
| 10 s | 0.782 | 0.858 | 0.580 |
| 5 s | 0.648 | 0.763 | 0.344 |
| 2 s | 0.493 | 0.582 | 0.259 |
| 1 s | 0.355 | 0.430 | 0.158 |

In the pre-registered presence unit, the decision that produces a fill (a re-price 0-150 ms after a Chainlink
publish, filled a median 0.86 s later) comes after the bin start for 86% of quote moves. The bin-start features have
to forecast the next ten reports. The +0.02-0.03 gain over activity (lot and X140 refit) is partly a property of that
unit.

**C3. The takers who fill fresh posts are often already in flight when the cluster posts. The trigger is neither
Chainlink nor the futures.**

- Taker signing ms (calldata) minus the post's server ms, class-(i) fills with prompt takers (signing to match < 1.5 s;
  629 of 942): 39% signed before the post. 115 signed in the 200 ms before it, against 63 in the 200 ms after it.
- Other makers with ms timestamps (all-match calldata, 4,819 fills by orders signed within 3 s of the taker) show the
  same shape: 531 in the 200 ms before against 460 after. The race is generic among fast makers.
- The CLOB market records have `seconds_delay: 0` for both the 5m and 15m windows. The ~190-ms floor (iteration-6
  mechanics) is taker latency, not a venue delay that exposes orders.
- What came in the 300 ms before the in-flight takers signed:

  | group | n | PM print | futures move >= $5 | Chainlink publish (stamp + 1,083 ms) |
  | --- | --- | --- | --- | --- |
  | random times, same windows | 840 | 0.507 | 0.008 | 0.274 |
  | in flight (signed 0-600 ms before the post) | 205 | 0.756 | 0.054 | 0.322 |
  | signed 0-600 ms after the post | 160 | 0.631 | 0.000 | 0.275 |
  | class (ii) takers | 218 | 0.853 | 0.000 | 0.312 |

- Prints come in bursts: 76% of all prints come within 300 ms of the previous print. On the print unit, followers are
  slightly less likely to fill the cluster (lift 0.94). So "takers follow prints" describes the market. It is not a
  cluster-specific trigger.

**C4. Print-level selection on the match clock is bounded by the queue at the cluster's own price.**

10-31 14-18, 55,138 non-cluster-taker prints, 1,598 cluster fills (base 2.9%). BTC 5m before its 16:53 switch-off.

| rule | share flagged | lift | recall |
| --- | --- | --- | --- |
| print on the posture outcome | 0.539 | 1.36 | 0.733 |
| price match (maker price = previous clean print on that outcome - 0.01, +-0.005) | 0.306 | 1.57 | 0.480 |
| both | 0.155 | 2.41 | 0.375 |

- The iteration-7 LightGBM on the same block reached 0.764, with lift 2.68 at recall 0.44.
- The cluster is about 3% of the makers at its own price. What decides between it and them is queue position, which
  no external feed carries.

**C5. The posture is not just the maker side of Binance-driven taker flow.**

- Class-(i) posts after a futures move of $2 or more over 2 s (104 of 942): the posture and the rule "the outcome the
  move disfavoured" both score 0.913 and agree 90%.
- Over 5 s (177 posts):
  - posture 0.825, anti-move 0.757;
  - where they disagree (56), the posture wins 0.607.
- With no move of $2 or more in 5 s (765 posts), the posture still scores 0.826.

## Critique

1. **The class-(ii) verdict rests on one volatility estimator.**
   - X130 / X136 concluded that the resting rungs follow "the market's move into the ladder (taker choice), which no
     quote-side input can predict".
   - C1 shows their post-time side moves between 0.34 and 0.72 with the volatility scale alone. The volatility source
     has been open since iteration 8 (X75).
   - The resting rungs are where that source can be identified, and 27% of the fills depend on it. On recorded blocks
     a class-(ii) side of 0.70 would put the per-fill side near 0.80.
2. **The presence gap was measured on a unit that hides the decision (C2).**
   - The iteration-8 D2 hazard showed that posting is predictable at 0.83 from public event clocks when the clocks are
     exact.
   - Fill presence has never been scored at event time. "The fill-level presence gap is intrinsic" (X140) is
     established for 10-s bins only.
3. **Every pre-October test lacks the engine's reference.**
   - The endpoint's Chainlink history starts around 10-01. So the stable profitable version (X140), the August
     settlement switches (X142) and the July pmxt pilot (X87) were scored with a Binance stand-in or not at all.
   - "The posture is at chance in September" is a statement about the stand-in.
   - The same Chainlink Data Streams reports are verified on-chain by other protocols on other chains. That historical
     source has not been tried.
4. **More reference feeds will not lift selection (C4).** The print-level gap is the queue at the cluster's own price.
   Public information can still move:
   - the side, through the volatility input (C1);
   - presence, through the event unit (C2);
   - on/off.
5. **The module on/off is still the largest presence lever, and it has been raced against public competition once.**
   - The iteration-1 oracle gave presence 0.866.
   - X39 compared one live switch-off with the book's add counts.
   - The October off-runs began as the entrant cohort reached ~15% of maker volume (X141) and the return fell. No
     public hour-of-week covariate has been raced against the calendar gate (AUC 0.68).

## Proposals (ranked by the chance they close the gap)

### I13-1. Identify the engine's volatility on the resting rungs, and score the class-(ii) side with it (strong form of X75 and X117; side component)

- **Hypothesis.**
  - The ladder is priced off F_CL(k x sigma_src) and the touch. A rung posted below the touch is placed on the outcome
    where F_CL - h exceeds the rung price, so its side depends on the level of F.
  - The engine's sigma source is identifiable on class (ii). Candidates:
    - realised volatility of the futures mid at some lookback;
    - Binance spot;
    - the RTDS Binance relay (dz_rtdsbn);
    - Deribit front-expiry IV;
    - a noise-filtered Chainlink realised volatility (2-s or 5-s sampling);
    - a constant.
  - With the right source, class (ii) carries the posture (>= 0.70) and class (i) keeps >= 0.80.
- **Why it fits.**
  - C1: class (i) is flat in k, class (ii) swings by 0.38 with k and between halves.
  - The k "cycle" and the entry-branch k drift (iterations 11-12; STUDY best k 1.0, VALIDATE 1.4) are what an
    unmodelled sigma source would produce.
  - X117 ruled out only the Chainlink-stream realised volatility and found that Deribit IV does not absorb the
    block-level k.
- **Test.**
  1. Pre-register a grid: sources x lookbacks (60, 300, 900, 3,600 s) x k from 0.5 to 2.5, with the RE's spot estimator
     included. Fit on class-(ii) posts of 10-31 14:00-16:00. Score on 16:00-18:00 and on the full-depth development
     blocks: 11-01 06-12 (the 62/250 ladder), 11-01 18-24 and 11-02 00-06 (X145).
  2. Apply the chosen source to class (i): it must stay at or above 0.80.
  3. Historical replication on the lot:
     - class (ii) through the same-transaction sweep proxy (8.6-12.8% of fills);
     - sigma from Binance USD-M aggTrades reduced to 1-s mids (the X132 archives, one day at a time), against the spot
       klines.
  4. Report the per-fill and per-burst-start side with the chosen sigma, against the cheaper-token and own-history
     baselines.
- **Data.** On disk (dm_bnf, dm_bns, dz_rtdsbn, dm_rtds, the it13 tables); the next full-depth blocks; the X117
  Deribit code; futures aggTrades (about 20 MB a day, reduced at once).
- **Signature if true.**
  - One source and k give class (ii) >= 0.70 on both halves and on 11-01 06-12, with class (i) >= 0.80.
  - The per-fill side on the match clock is >= 0.78.
  - The same source removes most of the k drift between STUDY and VALIDATE.
  - If every source stays unstable between halves, the resting-rung side is the takers' choice. That remainder is
    then a measured one (with this grid as evidence), not an assumed one.

### I13-2. Score fill presence on the publish clock, the unit at which the engine decides (strong form of D2, X72 and X49; presence target)

- **Hypothesis.**
  - The gain over activity is small at 10-s bins because the decisive information arrives inside the bin.
  - At the event unit (each RTDS Chainlink publish, per outcome), the just-published report predicts the cluster's
    next re-price, and with the touch, whether it will occupy that outcome's touch in the next second.
  - The activity baseline at the same unit cannot see the report.
- **Why it fits.**
  - C2.
  - The D2 hazard reached 0.83 for posts on exact public clocks (0.64 on the stamp proxy).
  - Posts come 0-150 ms after a publish and fills a median 0.86 s after the post.
  - The live print-selection gain over activity was +0.127 on the match clock (iteration 7, 0.764 vs 0.637). The lot
    block clock shows +0.03.
- **Test.**
  1. Unit: (window, outcome, publish k).
     - Label: a cluster maker BUY fill on that outcome in [P_k, P_k+1). Add a 2-s variant.
     - Features at P_k:
       - F - touch per outcome from the report just published;
       - the change of F from the previous report;
       - the TWAP strike and the time left;
       - the R3 activity features.
     - Baseline: the same model class with activity only, on the same unit.
  2. Fit on 10-31 12:00-15:00 and score on 15:00-18:00. Use stamp + 1,083 ms as the publish time, or dy_rtds publish ms
     where present.
  3. Freeze the model, then score it on 11-01 06-12, 11-01 18-24 and 11-02 00-06 (dy_rtds publish ms; that recorder
     runs to 11-03).
  4. Historical replication on the lot: stamp + 1,083 ms, R7's in-block execution clock, and X102's 1-2-s Chainlink
     grid.
  5. Report the 10-s-bin AUC beside it, so the pre-registered metric stays comparable.
- **Data.** On disk; the dy_rtds blocks; X102.
- **Signature if true.**
  - At the event unit the gain over the activity baseline is >= 0.05 on both halves and on the next block, against
    +0.02-0.03 at 10-s bins.
  - The gain is concentrated in units where the new report moves F across the touch.
  - If the gain stays at or below 0.03, the presence gap is the takers' arrival, now measured on the decision unit.
    That is the quantitative account the wall rule asks for.

### I13-3. Historical Chainlink Data Streams from on-chain consumers on other chains: the reference for July to September (new data source; strong form of X90, X87, X140 and X142)

- **Hypothesis.**
  - Perps protocols verify the BTC/USD Data Streams reports on-chain at every order execution (GMX v2 on Arbitrum and
    Avalanche emits an oracle price event with the report timestamp and the min/max price).
  - This gives a Chainlink history at seconds resolution where the investigation has only Binance.
  - With it, one of two things holds:
    - the September posture is at chance with the true reference too, which proves the configuration change;
    - or the stand-in hid it, so the posture is the stable rule and the September side gap was a measurement artefact.
- **Why it fits.**
  - X140 scored the stable version with the Binance stand-in. The posture share there rose smoothly by week (0.475 ->
    0.672) while the cheaper-token share fell.
  - The X87 pilot found the July engine to be the same family, but "no Chainlink history exists for July".
  - X142 could not identify the late-window fair beyond the market's own pricing.
- **Test.**
  1. No new data needed first. On 10-01..10-22, where the endpoint Chainlink exists (X90), measure the agreement of the
     stand-in posture with the real posture, by week. If it falls going back toward early October, the stand-in is
     suspect in September.
  2. Find GMX v2's oracle event on Arbitrum through a public RPC (publicnode). This is the EventEmitter `EventLog1` with
     eventName "OraclePriceUpdate" and the BTC token as topic. Steps:
     - decode one hour of the released lot (10-23..30): (min + max) / 2, the timestamp and the provider;
     - compare with the RTDS / endpoint values at the same stamps.
     A match within about $1 means it is the same stream. If not, try the Avalanche deployment or another Data Streams
     consumer, and record the failing comparison.
  3. Fetch only the pre-registered stable-sample hours (02 / 08 / 14 / 20 UTC of 08-14..10-11) and the X142 August
     sample. Report the median gap between BTC reports.
  4. Re-score the frozen R8 side and the posture per week with the true reference. Re-run X142's late-window fair test.
- **Data.** `eth_getLogs` on Arbitrum (a few thousand blocks per call); a decoded (timestamp, price) table under 20 MB.
- **Signature if true.**
  - GMX values equal the RTDS values within about $1 on the overlap.
  - The median gap is <= 5 s in the sample hours.
  - The September posture is then either >= 0.65 per fill (a stable rule) or <= 0.55 (a proven configuration change).
  - Either way, the September and July findings rest on the reference the engine reads.

### I13-4. The takers' clock: what puts a taker order in flight just before the cluster's post (strong form of X28, X45 and X81 with the post identified; presence co-occurrence account)

- **Hypothesis.** There are two readings:
  - (a) A common public trigger that both the cluster and the takers act on. The cluster's post reaches the book first
    because the takers' signing-to-match latency is at least about 190 ms. That trigger then belongs in both the rule
    and the activity baseline.
  - (b) The cluster detects flow before the match. With `seconds_delay = 0` no venue delay exposes orders, so (b)
    would need a non-public or cross-venue channel.
- **Why it fits.**
  - C3: 39% of prompt takers signed before the post.
  - Neither Chainlink publishes (0.32 vs 0.27) nor futures moves of $5 or more (5% vs 1%) precede them often enough to
    be the trigger.
  - Prints precede them, but prints precede everything (the market is bursty).
  - The other recorded venues (dm_cb, dm_okx, dm_byb, dm_hl, dm_bns) and the RTDS Binance relay (dz_rtdsbn) have not
    been raced on the taker clock.
- **Test.**
  1. The re-post-cycle null. From the cluster's exact-size add timeline (sched_adds plus the tracer chains), compute the
     probability that a random arrival at t finds a cluster order at that token's touch posted after t - latency.
     Compare it with the observed 39%, by latency bucket.
  2. For in-flight takers, the events in the 0-300 ms before signing on every stream with a millisecond clock:
     - prints and book events on both tokens (dm_clob_raw);
     - the RTDS Binance relay;
     - Binance spot and futures bookTicker;
     - Coinbase, OKX, Bybit and Hyperliquid;
     - Chainlink publish ms (dy_rtds, on the 11-01 blocks).
     Compare them with placebo arrivals.
  3. Repeat the test for the X141 entrants' fresh fills.
- **Data.** All recorded on disk (10-31 12-18) plus the 11-01 development blocks; the all-match calldata of more
  segments (about 75 tx/s through publicnode).
- **Signature if true.**
  - (a): one stream's events precede >= 50% of in-flight takers within 300 ms, at >= 3x the placebo rate. Name it, put
    it in both the rule and the baseline, and report the presence gain net of it.
  - (b): the cluster's posts after the taker's signing exceed the re-post null by >= 2x, with no public precursor. That
    is a measured non-public channel, with its share of fills.

### I13-5. Public hour-of-week covariates of the October module on/off (strong form of X39 and X9; selection)

- **Hypothesis.**
  - The October switch-offs (weekend evenings ET) avoid hours that a public statistic marks as bad for a maker.
    Candidates:
    - market-wide maker markouts by hour of week (every maker's fills against resolution, from the tape);
    - the entrant cohort's share of maker volume;
    - taker toxicity (the share of taker volume within 300 ms of futures moves);
    - Binance futures volume or depth.
  - The operator recomputes this calendar from the trailing weeks.
- **Why it fits.**
  - The module was on in 91% of September windows.
  - The off-runs began in October as the entrants rose to about 15% of maker volume and the return fell.
  - The calendar gate is only 0.68.
  - X39 compared one live switch-off with book add counts.
- **Test.**
  1. Data: hour-of-week cells over 09-11..10-30, from the tapes on disk:
     - taker tapes of every BTC 5m window of 10-09..30;
     - the stable sample hours for September;
     - maker rows of the iteration-12 and iteration-13 samples.
  2. For each covariate, compute the trailing 2- and 4-week value per cell.
  3. Choose the threshold on 10-01..15 and predict the cluster's window participation on 10-16..30.
  4. Compare with the calendar gate and with the cluster's own trailing PnL per cell (own state, reported only).
  5. Check the two DST changes as instruments: the EU change on 10-25 is already in the data; the US change on 11-01
    can be checked on the 11-02 development blocks (X57 / X99).
- **Data.** On disk; no new fetch is needed for the BTC 5m part.
- **Signature if true.**
  - A public covariate predicts the off cells at window AUC >= 0.80 (vs 0.68) on both halves of 10-16..30.
  - Its cells do not follow a clock change, unless the covariate itself is clock-driven.
  - If only the own-PnL calendar predicts them, the selection gap is own state. The share of presence it costs is then
    the quantitative account.

## Notes for the RE

- **Cheapest first.**
  1. I13-1 steps 1-2 on the 10-31 tables already on disk (about 15 minutes; my `vol_sens.py` is the skeleton).
  2. I13-3 step 1 (X90 data, no fetch).
  3. Both should finish before the 11-01 06-12 full-depth block is scored, so that block can serve as the held-out
     test for the sigma choice.
- **Closed or weakened by my checks.**
  - A venue speed bump as the reason the cluster is first: `seconds_delay = 0`.
  - "Print followers" as a selection feature: lift 0.94.
  - The posture as a by-product of Binance-driven taker flow: 0.826 on posts with no futures move.
  - More reference feeds for print-level selection: bounded by the queue (C4).
- **Book terms.** Any book or print-burst term that enters a rule must also enter the market-only baseline. A rule
  with an event-time unit must be compared with an activity baseline fitted on the same unit.
- **CLOB listing fields** for crypto 5m and 15m (10-31): `minimum_tick_size` 0.001, `minimum_order_size` 5,
  `maker_base_fee` / `taker_base_fee` 1000, rewards `rates` None (min size 50, max spread 4.5). They give nothing per
  market for selection beyond what Gamma carries.
