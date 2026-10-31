# Panel after iteration 7: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means:
- the universe the rule covers;
- what switches BTC 5m off;
- whether the quote is a memoryless function of its inputs;
- whether the primary metric can be reached at all;
- which parts of the history are usable.

Written 2026-10-31, about 18:40-19:30 UTC.

Data used (development only):
- cluster activity of 10-31 12:00-18:00 UTC, filtered by `sealed.is_sealed` on the trade time and the unit start
  (last row 17:52:51);
- the shared recorder `clob_crypto` and `subs` for 16:50-17:00 UTC;
- the iteration-6 raw-book extract `it6/ev_1793464800_1793466600.parquet` (10-31 16:00-16:30 UTC);
- the all-match calldata `calldata/allmatch1793460000_*` (10-31 15:20-15:40 UTC);
- the 10-09..22 on-chain fills and `cluster_btc5m_fills.parquet`;
- a few dozen early cluster transactions (2026-05-22..09-27), decoded with `code4/calldata.py`;
- four requests to `polymarket.com/api/crypto/crypto-price`.

Nothing from the lot's VALIDATE half, the 10-31 06-12 block or anything after 10-31 18:00 was read.

My check scripts are in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p7\`:
- `fam.py` (family mix before and after the switch-off);
- `v2early.py` and `v2trans.py` (signing timestamps in the early history);
- `rungshift.py` (rung moves);
- `builder.py` (taker builder codes and signature types);
- `cycle.py` (position of the window in the 15-min cycle).

Run them from the repo root.

## Critique

1. **The rule is built for a universe the exam may not contain.**
   - Every frozen rule (R2-R5) covers BTC 5m only. Its VALIDATE coverage is already below the scope bar: 0.783 of
     fills and 0.686 of absolute PnL, against 0.80 / 0.80 required.
   - On 10-31, after the 16:53 switch-off, the cluster made 0 BTC 5m trades. Of its 206 development-block trades from
     16:54 to 17:53, 168 (82%) and $7.7k of $8.2k (93%) were BTC 15m.
   - Before the switch-off (12:00-16:54), the mix was:

     | family | share of trades | share of dollars |
     | --- | --- | --- |
     | BTC 5m | 81% | 72% |
     | BTC 15m | 13% | 21% |
     | hourly and daily "up-or-down" | 4% | 5% |
     | BTC 4h | 1% | 2% |

   - The examiner's next lot is the sealed future blocks from 10-31 18:00. If BTC 5m stays off there, a BTC 5m rule
     covers about 0% of the fills.
   - Recorder coverage has gaps:
     - the exam recorder covers only the BTC 5m current and next windows and the BTC 15m current window;
     - no recorder covers the hourly markets, which are 4-9% of trades.
2. **The primary metric cannot carry what has been decoded.**
   - The historical fill-presence AUC has been 0.716 for four iterations.
   - The input decoded since then shows its identifying variation only live: the Chainlink report's 1-s noise and the
     per-report posture. On the lot the Chainlink fair correlates 0.988 with the Binance fair.
   - The investigation keeps reporting the historical fill AUC as primary. It has not asked whether any rule can reach
     0.85 on fills once the quote is known. The brief also allows "or better, whether it has an order resting", which
     the investigation has not taken up.
3. **"BTC 5m switched off at the PnL low" is read as a stop-loss. The same second fits two other triggers.**
   - The cluster's last BTC 5m trades (16:53:33-54) fall inside a market-wide trade burst. The shared recorder's
     crypto books printed 167-189 trades per 10 s at 16:53:50-16:54:10. That compares with 42-101 per 10 s in the two
     minutes before and 19-55 after.
   - The exam recorder died at 16:53:27, with nothing in stderr.
   - The CLOB drops slow websocket consumers during bursts (code 1013 "send buffer full"). The raw recorder logged
     this at 16:25:58 UTC and the exam recorder at 17:51:51 UTC.
   - So a volatility or message-burst breaker, or a BTC 5m module failure, fits that second as well as a loss limit.
   - X58's own facts already argue against a fixed limit: the thresholds range from -$0.9k to -$4.6k, and one switch
     came after a gain.
4. **"No single quote function of public inputs exists at tick precision" (iteration 5) assumes a memoryless quote.**
   - The rungs behave like persistent state (proposal 3).
   - The rung-reach rule (AUC 0.657), the 21% within-tick level fit, and X51's "designed randomness" all fit levels as
     a fresh function of the current inputs.
5. **The history before 10-09 was set aside as "description only", but it holds the decisive data.**
   - The wallets trade from 05-22 (almach), 06-02 (bosona) and 02-04 (mo-money, sparse early on).
   - For about 06-04..06-20, the current counter-salt engine **signed real millisecond timestamps** (proposal 5).
     That is the B1 decision-time measurement that iteration 4 called "impossible for this cluster".
   - The history also holds many more switch-off events than the six used for X58.
6. **The historical Chainlink source is a rolling 30-day window.**
   - `crypto-price` answers HTTP 400 "Timestamp too old for Chainlink API (max 30 days)" for 2026-10-01 12:00 and for
     June. It answers 200 for 10-02 00:00.
   - The BUILD days 10-09..22 drop out between 11-08 and 11-21, and the lot between 11-22 and 11-29.
   - Any Chainlink test on BUILD (noise episodes, the 10-17/18 off-runs) has to be fetched within the next week.
7. **R5's Chainlink weights are off-distribution for the exam.**
   - The stack's coefficients on dcl10, z_cl and gap were fitted on the smooth lot (1-s changes sd $1-3).
   - The sealed future blocks are in the noise regime (sd about $9, lag-1 autocorrelation -0.5).
   - The parameter-free posture logic (the sign of the Chainlink edge over the mid) transfers. Fitted magnitudes may
     not. A rule for the future blocks should be refitted on live BUILD, or be parameter-free.
8. **Checked and not supported, so not proposed.**
   - **Counterparty routing by front-end.**
     - Data: the all-match calldata of 10-31 15:20-15:40, with 5,516 taker orders, 182 of them in cluster matches.
     - A nonzero builder code appears in 12% of taker orders in both groups.
     - The signature types are close: type 1 24.7% vs 21.0%, type 3 59% vs 62%.
     - No builder concentrates cluster fills: the largest builders' cluster rates are 2-9%, against a base of 3.3%,
       on small n.
   - **Maker SELLs missing from the label.** All 97,074 cluster maker fills of 10-09..22 are BUYs, so the label is
     complete.
   - **Load sharing across the 15-min cycle.**
     - The BTC 5m active share by window position within the 15-min window is 0.67-0.70.
     - Fills per window differ by about 10% by position, and the ordering is not stable from day to day.

## Proposals (ranked by the chance they close the gap)

### A1. Freeze the rule for the universe the engine trades when the exam runs (strong form of X21; scope)

- **Hypothesis.**
  - The future sealed blocks will not look like VALIDATE. BTC 5m may stay off, and BTC 15m (plus 4h and hourly) will
    then carry most fills and PnL.
  - A rule whose universe is BTC 5m fails the scope condition by construction. It fails it already on VALIDATE
    (0.783 / 0.686).
  - The same engine prices every family with a horizon parameter, so one family-general rule should transfer.
- **Why it fits.**
  - After 16:54, 82% of trades and 93% of dollars were BTC 15m, and BTC 5m was 0 (critique 1).
  - The BTC 15m posture side is 0.73-0.79 and the match-clock price 0.843 live (iterations 6-7).
  - BTC 5m + 15m reached 0.868 / 0.891 coverage on VALIDATE.
- **Test.**
  1. On every development block (10-31 00-06 and 12-18, then 11-01 06-12 and 18-24), compute fills and absolute PnL
     by family, and the coverage of the union BTC 5m + 15m + 4h + hourly.
  2. Freeze one rule over that union. Use R5's features with tau and horizon, the posture side, and the match-clock
     price.
  3. Make `evaluate()` report pooled and per-family metrics.
  4. Pre-register now that a block with BTC 5m off is scored on the remaining families.
  5. Start a slim recorder for the BTC hourly books (tools/live.py Writer, hard stop, disk cap) before the next sealed
     block, so the hourly fills are examinable.
- **Data.** Activity of the development blocks (cached adapter), the shared recorder, examrec, dy_rtds and a new
  hourly-book feed.
- **Signature if true.**
  - Union coverage >= 0.80 / 0.80 in every development block, whatever the state of BTC 5m.
  - Per-family side and price within 3-5 points of BTC 5m.
- **If false.** The 15m (or hourly) quotes follow a different law. Then decode that family separately before any exam
  claim.

### A2. What switches BTC 5m off: a four-way race on the full history (strong form of X58, X9, X39)

- **Hypothesis.** The BTC 5m on/off is a runtime switch with one of four triggers:
  - (a) an own loss limit (X58 as stated);
  - (b) a volatility or message-burst breaker: a futures move, or the Polymarket trade rate over the last 1-5 min;
  - (c) an operational failure of the BTC 5m module (a websocket slow-consumer drop during a burst), cleared by a
    restart or by hand;
  - (d) a data-quality breaker on the Chainlink stream (noise or staleness of the reports the engine prices off).

  Triggers (b) and (d) are public inputs. Either would make the off-runs, and so presence on sealed blocks with BTC 5m
  off, decodable without own state.
- **Why it fits.**
  - The live switch-off sits inside a market-wide burst (critique 3).
  - X58's loss thresholds vary from -$0.9k to -$4.6k, and one switch followed a gain.
  - Three of five historical switch-offs fall at 22:10-22:30 UTC.
  - The Chainlink noise regime began between 10-30 15:00 and 10-31 00:30, and the 10-31 BTC 5m blocks lost 11.9% and
    3.9%.
  - Only six events exist in 10-09..31, but the history goes back to May and June.
- **Test.**
  1. Build the BTC 5m on/off series for each wallet over the whole history: the cached adapter, `activity(start=0,
     end=H)`.
  2. List every off-run of at least 1 hour, with its switch-off second and its re-enable second.
  3. For each event and for matched control windows, compute:
     - own BTC 5m PnL (window, day, 24-h drawdown), and total cash and equity across all markets from the activity
       cash flows;
     - Binance futures |return| and 1-s realised vol over 1 and 5 min (archives);
     - BTC 5m print rate over the last 60 s (data-api tape);
     - salt-counter restarts within +-10 min of the re-enable, from the calldata of the first fills after it;
     - UTC and US-Eastern hour;
     - for 10-02 onward, Chainlink 1-s lag-1 autocorrelation and staleness from `crypto-price`, 10 consecutive
       seconds per hour, about 80 min at the endpoint's rate. Fetch it before the window rolls.
  4. Fit each trigger as a hazard on the earlier events and score it on the later ones.
- **Data.** Full-history activity, data-api tapes around the events, futures archives, calldata of the re-enable
  fills, and the `crypto-price` endpoint (10-02..).
- **Signature if true.**
  - One trigger fires before at least 80% of switch-offs, with fewer than one false alarm per 3 days.
  - (c) also predicts re-enables at counter restarts.
  - (b) and (d) give a public on/off rule that can be frozen into presence.
  - If none fires, record the switch as a manual decision and quantify it (event count, timing distribution), as the
    wall rule requires.

### A3. The ladder is a state machine, not a memoryless quote function (strong form of X19, X51 and D2)

- **Hypothesis.**
  - Each wallet keeps rungs with persistent ranks.
  - A re-post moves one rung by a discrete step, mostly +2 ticks, instead of recomputing every rung level from the
    current inputs.
  - Levels are therefore path-dependent. Every memoryless fit misreads this state as noise: the iteration-5 level
    model (21% within a tick), the rung-reach rule (AUC 0.657), and X51's i.i.d. depth.
- **Why it fits.** My check, on the development raw book 10-31 16:00-16:30 UTC, used 3,788 exact-500 removals followed
  within 20 ms by an exact-500 add on the same market and side at a different price.
  - The removed rung's offset to the mid (at its post) and the new rung's offset correlate:
    - 0.84 overall (0.85 with more than 120 s left);
    - **0.65-0.76 within (market, side, 2-5 s) buckets**, so this is not a common slow driver such as time left.
  - Step sizes, in ticks:

    | step | +1 | +2 | +3 | +4 | +5 | -1 | -2 or lower |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | moves | 58 | 1,408 | 691 | 349 | 225 | 96 | 37 |

  - The step is not the mid change since the post: dp = -0.29 x dmid + 0.043.
  - By quintile, the old and new offsets are (-0.215, -0.155), (-0.145, -0.105) ... (-0.045, -0.015). The rank
    persists and every rung steps toward the touch.
  - Caveat: the three-wallet bursts can pair one wallet's removal with another wallet's add, and downward moves may be
    cancel-only.
- **Test.**
  1. Resolve rungs per wallet, using the three-wallet burst structure, the remainder sizes and the calldata of fills.
  2. Decode the move law: P(move), step and direction as functions of:
     - rung rank;
     - the change of the Chainlink center since that rung's last move;
     - the change in mid;
     - time since post;
     - a fill on the other side.
  3. Decode the reset rule: at the window open, after a fill, or at each report.
  4. Replay the state machine on held-out time (D3) to predict each wallet's top rung per second and per Chainlink
     report.
  5. Score at-touch state and print-level rung reach on live VALIDATE, then on 11-01 06-12.
- **Data.** Own raw recorder (14:06-18:00), the examrec 3-tick band, dy_rtds, live calldata.
- **Signature if true.**
  - Top-rung price within a tick for at least 80% of held-out seconds (the memoryless fit gets 21%).
  - Rung-reach print selection >= 0.80 with recall >= 50% at lift >= 3, against the P3 strong baseline.
- **If false.** The within-bucket persistence disappears once rungs are resolved per wallet. Then X51's randomness
  account stands.

### A4. Measure the fill-presence ceiling with the observed quote as an oracle, and move the primary metric to the quote if it is below 0.85 (strong form of X50 and H46)

- **Hypothesis.**
  - Given the cluster's actual quote, whether a 10-s bin gets a fill is set by taker arrival. So no rule can reach
    0.85 on fills.
  - The brief's alternative unit, "whether it has an order resting", is the one the strategy can be decoded on and
    examined on.
- **Why it fits.** No result so far approaches 0.85:
  - future taker flow as an oracle gives 0.682 alone and 0.730 with R2's features;
  - the per-trade join model gives 0.61;
  - the posture AUCs are Up 0.672 and Down 0.720;
  - the bin-level Chainlink gain is +0.035-0.043, against +0.10-0.13 at the print level.
- **Test.**
  1. On live development blocks, per (window, side, 10-s bin), give the presence model the observed cluster quote
     state as an oracle, together with activity:
     - the seconds with a cluster-signature exact-500 at the best bid;
     - its queue ahead;
     - burst multiplicity.
  2. Run it again with contemporaneous taker flow added.
  3. If the quote-oracle ceiling is below 0.85, report it as the quantitative account for fills.
  4. Then pre-register a quote-level primary metric. Unit: (window, side, second) or (window, Chainlink report).
     Label: a cluster exact-500 resting at, or posted to, the touch, readable from the examrec band.
  5. Put it in `evaluate()` with an activity-only baseline.
- **Data.** Raw book extracts (it6), examrec dx_clob, dy_rtds, live calldata.
- **Signature if true.**
  - Ceiling about 0.75-0.82 on fills.
  - On the quote unit, the posture / ladder rule beats the activity baseline by >= 0.05 with a positive bootstrap
    lower bound.
- **If false.** The ceiling is above 0.85. Then the quote is the gap after all, and A3 is the route.

### A5. Decision times exist in the history: the counter-salt engine signed real ms timestamps until about 06-20 (new; B1, C4, C4b)

- **Hypothesis.**
  - From about 06-04 to 06-20, the current engine lineage signed every order with its real millisecond timestamp.
    It used the per-wallet counter salt and served all three wallets.
  - Over those ~17 days, the decision time of every filled order is observed.
  - The salt counter plus signing ms gives each wallet's total signing rate, filled or not, at every moment: a direct
    record of the re-price cadence.
  - The switch to timestamp 0 is itself a dated version change.
- **Why it fits.** I decoded about 70 early cluster orders, all on the V2 exchange 0xe111... with selector 0x3c2b4399.

  | dates | salt | timestamp |
  | --- | --- | --- |
  | 05-22..06-02 | random 9-10 digits | ms |
  | 06-04..06-20 | counter: 3,012 (06-04), 11,953 (06-06), 3,448 (06-10, restarted), 24,593 (06-12) ... 308,135 (06-20) | ms; sign to block 1.7-7 s, one 76 s |
  | 06-21 | counter | almach 0; bosona and mo-money still ms |
  | 06-22 on | counter | 0 for all |

  - Sizes then were 50/100/150/300.
  - The staggered 06-21 change also shows that the wallets run separately deployed instances under a shared config.
- **Test.**
  1. Fetch the cluster's transactions for 06-03..06-21: activity, then hashes, then publicnode batched calldata;
     sample if there are more than 100k.
  2. Decode sign_ms and salt.
  3. Signing rate from the salt slope, at 100-ms resolution.
  4. Event study of signing ms against:
     - Binance futures and spot aggTrades (June archives);
     - Polymarket prints, with the taker's signing ms in each match as a millisecond clock for other traders;
     - the phase within the second (ms mod 1000).
  5. Limit price at signing against the futures and spot fairs and the mid: B3 at the true decision time.
  6. Sign-to-match lifetimes.
  7. Line up the timestamp-0 change point with the other changes (sizes, ladder, reference) and with Polymarket
     announcements (C4b).
  8. Chainlink 1-s is not available for June (`crypto-price` refuses anything older than 30 days). So the Chainlink
     race there must use the 5-min priceToBeat / finalPrice, or Polygon's Chainlink aggregator rounds. The futures,
     print and phase triggers are measured directly.
- **Data.** Full-history activity, publicnode calldata (~2.7 KB per tx, decoded fields only), Binance June archives,
  data-api tapes and Gamma for June windows.
- **Signature if true.**
  - A sharp trigger law: signing bursts at a fixed latency after a named feed's events, or at a fixed phase of the
    second, with a hazard AUC >= 0.85 on 100-ms bins of the signing-rate series.
  - Price at signing within a tick of a deterministic function for at least 80% of orders.
  - If the June engine follows futures and the October one follows Chainlink, the reference change is a dated version
    boundary. Decode each version separately (C4) instead of pooling them.
