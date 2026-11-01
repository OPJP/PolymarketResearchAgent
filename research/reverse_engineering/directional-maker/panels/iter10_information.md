# Panel after iteration 10: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md (iteration 10 in full, iteration 9 by section), state.json (catalog,
components, live_lab, latest statement), FINAL_RULE.md, EXAM.md (head), and every earlier panel's proposal list,
including `iter9_information.md` in full. I did not read the iteration-10 mechanics or assumptions panels, which are
written in parallel.

Data I used, all development:

- the released lot (h1 + h2) only through the RE's existing tables: `b1_orders_lot`, `b1_cluster_orders_{study,valid}`,
  `b1_takers_{study,valid}`, `calldata/othstudy_*`, `it9/volhist_{study,validate}`, `fut1s/<day>`. STUDY is read case by
  case; VALIDATE (10-27..30) is reported as aggregates only;
- five requests to the crypto-price endpoint at 2026-10-22 12:00:00Z (before H), one per symbol;
- `tools/live.py status` (process fields only: start time, reconnects, last error; no record counts of sealed blocks).

I did not open `.cache/live/sealed/`, any sealed block, any other strategy's workspace, or any market data after
10-31 18:00. Scripts: `C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/i10/`
(`salt_age.py`, `salt_age2.py`, `mom_side.py`, `taker_trig.py`; the two-sidedness and endpoint checks were inline).

## What my checks found

**C1. The off-session 62/250 rungs are re-signed as often as the 500s. They are not a static ladder left on the entry
side.**

- The salt counter, used as a clock (15 orders/s, per wallet), with anchors densified across markets: 43,500 cluster
  orders from the BTC 5m lot calldata plus 7,273 STUDY orders from other markets. For each filled order: the lower bound of
  its age = (highest rate-adjusted salt of the same wallet's orders filled within ±10 s − its salt) / 15. Coverage: 40% of
  the lot's classified orders.
- Lower-bound age (median / p75 / p90, seconds):

  | | 62/250, outside the weekday 12-21 UTC session | 500, outside the session | 500, in the session |
  | --- | --- | --- | --- |
  | STUDY | 0.40 / 2.3 / 5.5 (n 756) | 1.30 / 3.8 / 6.8 (n 57) | 1.09 / 5.0 / 11.0 (n 366) |
  | VALIDATE (aggregate) | 0.47 / 2.9 / 5.9 (n 1,496) | 0.93 / 4.9 / 10.4 (n 399) | 0.87 / 4.7 / 10.1 (n 1,303) |

- Caveat: this is a lower bound, and the covered fills lean towards busy periods. Even so, nothing points to an entry
  ladder left resting for tens of seconds. The iteration-4 `b1_age` was degenerate because its anchors were BTC 5m fills
  only, 39-48 s apart. With other-market anchors the counter becomes usable.

**C2. Off-session windows are more two-sided than 500 windows.**

Wallet × window cells with at least 3 classified fills:

| | 62/250-only windows: two-sided share, median majority share | 500-only windows: two-sided share, median majority share |
| --- | --- | --- |
| STUDY | 0.64, 0.72 (556 windows) | 0.60, 0.85 (316 windows) |
| VALIDATE (aggregate) | 0.74, 0.67 (1,253 windows) | 0.67, 0.77 (1,086 windows) |

**C3. The takers who fill the off-session ladder are not latency pick-offs.**

- Measure: the |1-s Binance futures move| at the taker's signing second minus k (k = 0..5), relative to the mean over the
  same clock hours. Takers come from the lot calldata, joined to the class of the filled order.
- 62/250 fills, 00-12 UTC:
  - STUDY: 1.33, 1.57, 1.12, 1.12, 1.05, 1.09 (n 628);
  - VALIDATE: 1.34, 1.05, 1.18, 1.08, 0.93, 0.87 (n 2,631).
- 62/250 fills, 12-24 UTC: 0.5-1.2.
- 500 fills: a flat 1.5-1.7 in the session and 2.8-3.1 off-session. The profile is flat, with no spike before the signing.
  That is a regime effect: off-session 500 mode is chosen when volatility is high (X34). It is not a trigger.
- Neither class shows a pick-off spike, so the counterparties do not see a Binance move that the cluster misses.

**C4. The favourite-to-underdog flip between the halves is common to both rung classes.**

- Fill side (S and K from the RE's `volhist` tables, Binance):

  | | Binance favourite, STUDY | Binance favourite, VALIDATE | cheaper side, STUDY | cheaper side, VALIDATE |
  | --- | --- | --- | --- | --- |
  | 500 | 0.61 | 0.40 | 0.43 | 0.62 |
  | 62/250 | 0.61 | 0.41 | 0.43 | 0.59 |

- Against the sign of the futures move over the previous 1-120 s (does the fill follow the move?), 62/250:
  - STUDY: 0.44 / 0.48 / 0.52 / 0.48 / 0.48 / 0.52 / 0.55 for 1 / 2 / 5 / 10 / 30 / 60 / 120 s;
  - VALIDATE: 0.46 / 0.46 / 0.47 / 0.44 / 0.41 / 0.40 / 0.41.
- 500s show the same pattern (0.40-0.48 on VALIDATE).
- The off-session ladder is no more momentum-driven than the 500 ladder. The halves differ in the taker mix (88% complement
  mints on VALIDATE). The locked-pair / residual PnL sign change of iteration 10 sits on the same flip.

**C5. Which data exist for the next future exam.**

- **The shared recorder started at 10-31 12:18:18 UTC.** The status `started` field is 1793449098; this matches NOTES line
  441.
- The own recorders started later:

  | recorder | start (10-31 UTC) |
  | --- | --- |
  | rawrec | 14:04 |
  | examrec / dx | 15:53 |
  | dy_rtds | 17:29 |
  | dz_rtdsbn | 19:13 |
  | famrec / dw | 22:59 |

- **So the sealed block 10-31 06-12 has no live recording of any kind.** It is the first block of the next future exam,
  and with 10-31 18-24 it already makes the 12 sealed crypto hours that exam needs.
- In 10-31 18-24, dw_clob covers the non-BTC families only from 22:59.
- Every own recorder hard-stops at 11-03 00:00. The shared recorder stops at 11-05 12:18.
- The shared `clob_crypto` socket has reconnected 122 times. Its last error is 1013 "slow consumer: send buffer full", so
  the examiner's match-clock trades have gaps.
- dy_rtds keeps only btc/eth/sol (`KEEP` in `code7/rtdsstream.py`).
- The crypto-price endpoint does serve the other families. On 2026-10-22 12:00Z it returned HTTP 200 with
  openPrice/closePrice for XRP, DOGE, BNB, HYPE and ETH. The all-crypto universe therefore has a settlement-grade
  reference historically (30 days), but no publish clock.

## Critique

1. **The planned claim path cannot be examined on the lot the calendar will hand the examiner.**
   - The pre-registered quote unit is labelled from dx_clob and dw_clob only.
   - The first sealed block of the next future exam (10-31 06-12) has no recording at all.
   - The own recorders stop on 11-03 00:00.
   - Scoring the quote unit on the recorded blocks only would be a subset metric that does not count.
   - A recording-free path exists for the side: the A1 proxies reproduce the live truth, region D 0.953 vs 0.965, and the
     block clock gives 0.952. It is not used for the presence/selection target.
   - The one target unit that can be labelled in every block from public history (print-level selection) has never been
     scored historically with the settlement-grade reference. X31 called it impossible before the endpoint was found; X43
     then used the endpoint for presence bins only.
2. **The off-session ladder is being searched for a side reference, but its fills look like the taker's choice.**
   - The ladder is about 44% of the lot's classified orders and 57-81% of the fills in 00-12 UTC.
   - It is re-signed about as often as the 500s (C1).
   - It is more two-sided (C2).
   - It is filled by takers with no Binance trigger (C3).
   - The flip of its side between the halves is shared with the 500s (C4).
   - So what is missing is the information set of its quote and of its counterparties, not another reference scored on its
     fills.
   - Its quote inputs have never been raced. A2, X10 and X44 measured only the US-session 500 ladder on 10-31.
3. **Per-fill side accuracy on the lot moves with the taker mix whatever the rule.** The rule should be scored on the
   quote, or with the taker-flow baseline stated, before the next pre-registration. C4 shows a 0.61 → 0.40 swing in the
   favourite share for both classes.
4. **Every quote-level fact still comes from about 6 h of US-session live data.**
   - The off-session quote has never been observed; 11-01 06-12 will be the first time.
   - pmxt (July-August) can replicate the re-post trigger race on 24 days of off-session hours. That race needs Binance and
     the book, not Chainlink, so the missing July Chainlink history does not block it.
5. **The shared recorder is lossy for the inputs R6 depends on**: slow-consumer disconnects, and no per-second Chainlink
   (snapshots only). For non-BTC families, no recorder keeps the Chainlink publish clock. These are inputs of the
   all-crypto universe, which is the only universe that meets the scope bar in every block.

## Proposals (ranked by the chance they close the gap)

### I10-1. Make the claim examinable on every block of the next exam: a recording-free evaluation path, and recorders that cover the exam horizon (strong form of X88, X29, X95)

- **Hypothesis.** The target can only be met on units and inputs that exist in every sealed block the examiner takes.
  For 10-31 06-12 that means public history only: the data-api tape, the lot-style calldata (taker signing ms), the
  crypto-price endpoint and the Binance archive. For blocks after 11-03 00:00 it means new recorder instances. A
  recording-free path that reproduces the recorded path's side, price and selection metrics on a development block makes
  the claim examinable everywhere.
- **Why it fits.**
  - C5: 10-31 06-12 has no recording, the own recorders stop on 11-03, the shared socket drops data, and dy_rtds drops
    the non-BTC/ETH/SOL symbols.
  - A1 shows the historical proxies already reproduce the match-clock truth for the side (0.953 vs 0.965).
  - Price: block clock 0.70 vs match clock 0.83-0.86. A historical match clock from the taker signing ms, plus the
    in-block transaction order (75% correct pairs, iteration-7 mechanics), was never applied to the price anchor.
- **Test.**
  1. Write evaluate()'s recording-free path for every family:
     - match clock T_hat = clip(taker sign_ms + 620 ms, b − 3 s, b − 1.5 s);
     - the previous print taken from the in-block order of the market's OrderFilled logs;
     - Chainlink from the endpoint (all symbols);
     - the Binance archive.
  2. On 10-31 12-18 (development) run it beside the recorded path. Report side, price and selection/presence for each
     path, per family and per wallet.
  3. Before 11-03 00:00, start successor instances of dx_clob, dw_clob, dy_rtds (with xrp/bnb/doge/hype added to `KEEP`)
     and dz_rtdsbn. Each gets a hard stop at the planned end of the budget plus the exam, under 100 MB of memory and
     300 MB of disk, and is recorded in `live_lab`.
  4. Pre-register, before the claim, which unit and which path are scored in blocks without own recordings.
- **Data.**
  - Polygon RPC (publicnode for calldata, drpc for logs) for the taker structs and logs of the cluster's fill transactions
    in each block;
  - the endpoint;
  - the Binance archive;
  - the own recorders.
- **Signature if true.** On 10-31 12-18 the recording-free path's side, price-within-a-tick and selection AUC are within
  0.02 of the recorded path (price at least 0.80). The successor recorders' status shows them alive across 11-03 00:00. If
  the price stays near 0.70 without recordings, the price bar cannot pass on the unrecorded block. Say so before the claim.

### I10-2. Print-level selection on the lot with the settlement-grade reference and the public size mode: the only target unit labelable in every block (strong form of X31's historical part, X43, X55)

- **Hypothesis.** The prints that fill the cluster are picked out, historically, by public inputs:
  - the Chainlink posture of the token whose bid the print fills (for a mint, the complement), with the report at b − 4;
  - the public size mode (500 vs 62/250, from session and open volatility);
  - the calendar gate.

  These give a gain over activity close to the live one (0.764 vs 0.637). That makes the selection bar (0.80, recall 50%
  at lift 3) the claimable target, with the rung reach as the measured remainder.
- **Why it fits.**
  - Live, the quote is binding at the print level: oracle 0.814-0.834 with recall 0.62-0.685 at lift 3.3-3.4.
  - The public Chainlink feature carries most of the gain (X31, X55).
  - Historical selection is still R2's Binance score (0.685, recall 29.5%, lift 2.87).
  - The block clock keeps the Chainlink signal (A1: 0.952 vs 0.965), so no all-match calldata is needed.
  - The posture belongs to the 500 mode only (iteration 10), and the mode is predictable: 96-98% in the weekday session,
    off-session AUC 0.76-0.95 (X34). R2 had neither.
  - Off windows are easy negatives with the gate, and the activity baseline cannot see them.
- **Test.**
  1. Take the X43 stride-16 windows (144 VALIDATE, 154 STUDY). Queue endpoint requests for every second of [S − 65, E]
     of each: two values per request, about 150 requests per 5-m window, about 22k requests in all (about 4 h detached at
     the polite rate, after the RE's current queue). It must finish before the lot leaves the 30-day window (about 11-22).
  2. Pre-register the per-print model (clean tape; the cluster's own transactions excluded from features):
     - activity only (the examiner's class of model) vs activity + the Chainlink posture of the filled-bid token at b − 4
       (frozen sigma) + the public size mode + the calendar gate;
     - fit on STUDY, score VALIDATE in aggregate;
     - recall and lift at the pre-registered threshold;
     - 2-h block bootstrap of the gain; rotation null with 2,000 draws.
  3. Report per wallet and per half. Report the oracle-quote ceiling on the live block as the decomposition of what
     remains.
- **Data.** The endpoint (verified), the data-api tapes already cached for the lot, Gamma strikes, the Binance archive.
- **Signature if true.**
  - VALIDATE print AUC at least 0.76, gain at least 0.08 over activity (bootstrap lower bound > 0), recall at least 40% at
    lift 3, every wallet within 0.03.
  - The per-window PnL correlation of the selected-print replay rises above R6's 0.26-0.33. The residual's sign is then
    reproduced from public taker flow.
  - If the gain stays at R2's level (≈ +0.02), the Chainlink selection lift of 10-31 is specific to the live block.

### I10-3. The off-session ladder's information set: race its re-posts against every feed on 11-01 06-12, then replicate on 24 days of pmxt off-session hours (strong form of A2, X10 and X44 for the 62/250 ladder; never measured off-session)

- **Hypothesis.** The off-session ladder is the same pricer without the Chainlink skew. It is re-signed on each Chainlink
  publish and after Binance futures moves, centred on the market mid, two-sided, and its fill side is chosen by the taker.
  The alternatives:
  - (b) it reads another venue in Asian hours: OKX, Bybit or Upbit;
  - (c) it follows only Polymarket trades (the 69-95 ms post-after-trade law), with no external input.
- **Why it fits.**
  - C1: it is re-signed as often as the 500s. C2: it is more two-sided. C3: there are no pick-off takers.
  - Its fill side follows no reference (0.43-0.59) and flips with the taker mix (C4).
  - The re-post trigger race (Binance futures 91-97%, publish-locked within 0-150 ms) was run only on the US-session 500
    ladder on 10-31.
  - The 62/250 classes are 57-81% of 00-12 UTC fills.
- **Test.**
  1. On 11-01 06-12 (development; full-depth recorder 05:55-12:00 with dm_bnf, dm_bns, dm_okx, dm_byb, dm_cb, dm_hl,
     plus dy_rtds and dz_rtdsbn):
     - identify 62/250 adds, i.e. exact sizes in two- and three-wallet bursts within 20 ms, on both outcomes;
     - for each re-post, measure the agreement of the price change's direction with each venue's move over the previous
       50-250 ms, and with the change of the Chainlink report in the 150 ms after each publish;
     - measure the re-post hazard after Polymarket trades on the same and on the complement token;
     - measure the skew of the ladder centre on the Chainlink edge (the 500 ladder's ~0.2).
     - Optionally add a 1-h Upbit KRW-BTC recorder through the shared `Writer` (public websocket, hard stop).
  2. Replication: pmxt hours 00-12 UTC of 07-16..08-09, range-read per market (the reader from my iteration-9
     scratchpad). Use Binance futures aggTrades from the archive. Run the same race on the July small-size rungs (50s),
     with no Chainlink needed.
- **Data.** The 11-01 own recorders; pmxt; the Binance spot and futures archives.
- **Signature if true.**
  - (a) Off-session re-posts agree with the futures move at least 90% of the time, re-posts lock to publishes, and the
    skew is at most 0.05. In that case the side of the 62/250 ladder is decided at the quote (both outcomes, centred on
    the mid) and is scored there. Its fill side gets the taker-flow baseline, stated as such.
  - (b) Another venue leads at least 85% of the time while futures stays at or below 70%: a second information set,
    absent from every current rule.
  - (c) Re-posts follow only Polymarket trades: a book-following ladder.
  - The same pattern on pmxt off-session hours decides it on thousands of windows instead of one block.

### I10-4. Who fills the off-session ladder and what they act on (strong form of X28, X66 and X81, all measured on the US-session 500 ladder)

- **Hypothesis.** For a two-sided ladder, the side and the timing of the fills are the counterparties' decisions. A few
  taker populations, such as UI-driven Magic and smart-wallet traders or round-USD orders, carry most of the 62/250 fills
  and buy a predictable side, such as the displayed Chainlink favourite or the market favourite in the last minute. Then:
  - the off-session fill side = the complement of a predictable taker side;
  - off-session presence = the arrival of those populations, which public data on the UI's salient events can time
    better than generic activity.
- **Why it fits.**
  - C3: no Binance trigger, unlike HFT pick-offs.
  - C4: the fill side flips with the taker mix between the halves.
  - X66 found that type 1 and type 3 takers carry 67% of VALIDATE PnL; that was not split by rung class.
  - X45 tested only the displayed Chainlink *change*, not the level against the strike shown on the page. The Chainlink
    favourite flip, i.e. a crossing of the price to beat, is the UI's most salient event.
- **Test.**
  1. On the lot calldata (`b1_takers_*`; STUDY case by case, VALIDATE aggregate), classify the takers of 62/250 fills and
     of all other off-session cluster prints by signatureType, round-USD amount, limit looseness, sign-to-block lag, size
     and repeat address.
  2. For each class, report:
     - the outcome bought against the displayed Chainlink favourite, the market favourite, the cheaper side and time
       left;
     - markouts.
  3. Pre-register a public taker-side predictor:
     - net clean-tape taker buying by outcome over the previous 10-60 s;
     - plus "Chainlink crossed the strike within the last 2-10 s" (endpoint value at b − 4).

     Score it for the cluster's off-session fill side, reported as a market-only baseline.
  4. Repeat on 11-01 06-12 with the RTDS `activity` topic (X62), which gives taker identity in real time.
- **Data.** The lot calldata (on disk), the clean tapes, the endpoint, X62's recording.
- **Signature if true.**
  - One or two populations carry at least 70% of the 62/250 fills.
  - They buy one predictable side at least 70% of the time, so the cluster's fill side is its complement at the same
    rate.
  - The hazard of their prints rises at least 2x in the 2-10 s after a strike crossing.

  If takers are dispersed and side-random, the off-session side is not a decision of the wallet. Report the
  one-sided-window share (C2: 26-36% one-sided), so that the examiner's side-applicability rule is settled in advance.

### I10-5. Pin the Chainlink noise regime's onset on 10-30 and carry a regime flag into the frozen rule (strong form of X46 / X89 step 3)

- **Hypothesis.** The 1-s noise regime (sd $9.3, lag-1 autocorrelation −0.51) is a change in the stream or the relay that
  began on 10-30 (released lot h2).
  - It roughly doubles region D, because noise crosses the strike.
  - It turns the 62/250 rungs against the report in region D (hour 00 of 10-31: 0.10).
  - It precedes the cluster's losses and the ad-hoc switch-off.

  If it persists into the sealed blocks, R6's per-class mix and its module state change there, and the exam measures the
  regime rather than the rule.
- **Why it fits.**
  - X46 left the onset between 10-30 15:00 and 10-31 00:30.
  - The noise was on in every hour of 10-31 00-06 and at the 16:53 switch.
  - The lot's VALIDATE day 10-30 is the only historical day that may straddle it.
- **Test.**
  1. Fetch one 30-s run of consecutive endpoint seconds every 30 min over 10-30 12:00-24:00, and the same clock times on
     10-29 as a control. That is about 24 runs × 15 requests, a few minutes at the polite rate.
  2. Locate the change point in the sd and the lag-1 autocorrelation.
  3. Report the aggregate 10-30 cluster metrics before and after it: region-D share, 500 vs 62/250 region D, PnL. These
     are VALIDATE aggregates, so no case-by-case reading.
  4. Freeze a public regime flag (rolling 5-min lag-1 autocorrelation of the reports) in evaluate() as a reported stratum,
     not as a decision.
- **Data.** The endpoint, and the RE's lot tables.
- **Signature if true.**
  - A sharp onset, within one 30-min step, inside 10-30.
  - The aggregate region-D share and the cluster's BTC 5m PnL change at it.
  - In development blocks after 11-01 06:00, the flag predicts whether BTC 5m is quoted, beyond the calendar gate.

## Notes for the RE

- **Salt clock.** The counter is usable as a clock once the anchors include the wallet's orders in every market. With
  only the STUDY other-market calldata, coverage is 40% within ±10 s. Fetching every cluster transaction of a few lot
  days, in all markets, would make it about 90% and give posting times for the static-vs-re-priced question at once (C1
  already argues "re-priced").
- **Sealed-block coverage.** Do not count records of sealed blocks to check coverage. The recorders' start and stop
  times (state.json `live_lab`, the status `started` field) are enough to see that 10-31 06-12 has no recording.
- **Endpoint for the non-BTC families.** It serves the Chainlink values of XRP, DOGE, BNB, HYPE and ETH at a given second,
  so the family-general universe has a historical reference until each day leaves the 30-day window.
- **Ruled out by my checks.**
  - The off-session ladder as a static entry ladder (C1).
  - Binance momentum, or a taker pick-off, as its side driver (C3, C4).
