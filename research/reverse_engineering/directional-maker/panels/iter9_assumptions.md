# Panel after iteration 9: assumption breaker

Lens: what the investigation takes for granted that may be false. Here that means:
- that the side posture decoded on one Saturday block is the engine's rule throughout its history;
- that a wallet's per-fill accuracy measures that wallet's decisions;
- that the operator leaves no public footprint except fills and quotes;
- that every clock feature can stay in UTC through the exam;
- that the money comes from information and cheap underdogs.

Written 2026-10-31, about 22:10-22:45 UTC.

Data used (development only; checked with `tools/sealed.py directional-maker`: released h1 and h2, development up to
10-31 06:00 and 10-31 12:00-18:00):
- the three wallets' activity for 10-08..10-30 (`activity_*.parquet`, `exam/activity_*.parquet`). I used 10-27..30 only
  as weekly and 3-hourly aggregates;
- on-chain pUSD and USDC.e balances of the three proxy wallets, every 3 hours from 10-09 00:00 to 10-30 21:00 UTC
  (`eth_call` on drpc archive). No block at or after T0 was queried;
- pUSD and USDC.e `Transfer` logs from and to the wallets and their withdrawal addresses around 10-12, 10-19 and
  10-26 01:00 UTC (publicnode `eth_getLogs`);
- the RE's per-fill tables `it9/side_D_1793448000_1793469600.parquet` (10-31 12-18) and
  `it9/volhist_{build,study}.parquet`;
- the switch-off calldata `calldata/it9sw_1793465400_1793469600.parquet` (10-31 15:50-18:00).

Nothing from 10-31 06-12, 10-31 18:00 onward, VALIDATE case by case, or `.cache/live/sealed/` was read. One request
returned a `latest` balance by mistake while I was debugging the RPC. I did not decode or use it.

My check scripts are in the scratchpad
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p9\`:
- `bal.py`: the 3-hourly collateral balances;
- `flow.py`: balance change minus activity cash flow, i.e. the external transfers;
- `sweep.py` and `dest.py`: the withdrawal transactions and where the money goes next;
- `fampnl.py`: held-to-resolution PnL by market family and week.

I ran the posture-by-edge, per-wallet and post-restart checks inline on the tables named above. Run the scripts from
the repo root.

## What my checks found

**F1. The historical side deficit is not a composition effect.** I took the posture as frozen (1.4 x v300, no
fitted parameter) and scored it by |edge| = |fair - Up mid|, for BTC 5m only:

| \|edge\| | live 10-31 12-18 (match clock, Chainlink) | BUILD (block clock, Binance proxy) | STUDY (block clock) |
| --- | --- | --- | --- |
| <= 0.01 | 0.60 (n 55) | 0.51 | 0.45 |
| 0.01-0.03 | 0.37 (n 158) | 0.58 | 0.53 |
| 0.10-0.20 | 0.84 (n 595) | 0.62 | 0.58 |
| > 0.20 | 0.86 (n 517) | 0.63 | 0.49 |
| all | 0.794 (n 1,798) | 0.601 (n 49,569) | 0.543 (n 8,256) |

- Weighting the live accuracy curve by the historical mix of |edge| predicts 0.752 (BUILD) and 0.747 (STUDY).
- So the larger live edges explain only a small part of the 0.79-vs-0.60 gap. Historically the posture fails even at
  edges above 10 c, where it should be at its most reliable.
- Either the block clock and the Binance stand-in destroy it, or the engine's footprint differs between the smooth
  Chainlink regime (to 10-30) and the noise regime (since 10-30/31). The RE's iteration-9 reading picked the first
  without a test that can tell them apart.

**F2. The operator's automation is on-chain, and capital never binds.**
- The activity endpoint reproduces on-chain cash exactly. The balance change minus the activity cash flow has a median
  of $0 per 3-hour interval (p90 $36). Every external flow is therefore visible.
- In 10-09..30 there are **no deposits**, and the only withdrawals are a **weekly sweep on Mondays at the 01:00 UTC
  restart**:

  | Monday sweep | mo-money | almach | bosona |
  | --- | --- | --- | --- |
  | 10-12, 01:00:21-24 UTC (blocks 95,374,362-364) | $26,258.50 | $27,574.81 | $21,402.99 |
  | 10-19, 01:01:00-03 | $10,447.56 | $5,098.44 | $13,383.63 |
  | 10-26, 01:00:06 | none | none | $4,365.47 |

- After each sweep, the cash of every wallet is equal to within about $0.5k: $23.2-24.2k on 10-12, $22.2-22.3k on 10-19
  and $24.4-24.9k on 10-26. The engine withdraws everything above a target working capital. Cash then grows during the
  week, to $43-49k by 10-30.
- The flow pattern is the same every week:
  1. each wallet sends to its own address, which has 23 bytes of code (the length of an EIP-7702 delegation);
  2. that address unwraps pUSD to USDC.e within about 7 blocks;
  3. within about 8 more blocks it forwards the USDC.e through the ERC-4337 EntryPoint (0x4337084d...) to its own plain
     EOA: 0xe3c61b5a... (mo-money), 0x44c83a63... (almach), 0x2084ab26... (bosona).

  The three treasuries are scripted together but never commingled.
- Minimum cash over 10-09..30 is $19.7k (mo-money), $21.0k (almach) and $21.8k (bosona). No off-run (10-17, 10-18,
  10-23, 10-24) coincides with a transfer.
- So collateral gating of the module on/off is ruled out on this period. The 01:00 UTC restart is a scheduled job
  that also runs a weekly treasury.

**F3. Where the money is (held-to-resolution cash flows).** Markets first traded on or after 10-09 and last active before
10-30 12:00:

| family | bought | net PnL | return |
| --- | --- | --- | --- |
| BTC 5m | $2.59M | +$56.8k | 2.2% |
| BTC 15m | $1.26M | +$4.6k | **0.4%** |
| BTC hourly (Binance-settled) | $230k | +$6.6k | 2.9% |
| BTC 4h | $165k | +$6.6k | 4.0% |
| other crypto (ETH/SOL/XRP/DOGE/BNB, all horizons) | | ~+$13k | |
| maker and taker rebates, rewards (10-08..30) | | **+$23.0k** | |
| total | $4.69M | +$111.7k | |

- Rebates are about 21% of net PnL. In BUILD they are $14.5k against BTC 5m's $35k.
- BTC 15m is break-even before rebates.
- Weekly BTC 5m PnL: +38.0k (10-09..15), -8.3k (10-16..22), +26.3k (10-23..29). BTC 15m: -0.4k, -9.5k, +10.4k.

**F4. The per-wallet differences look partly like fill selection.** Pooled 5m and 15m fills of 10-31 12-18:
- Posture accuracy with the Chainlink fair is almach 0.812, bosona 0.785, mo-money 0.762. With the Binance fair it is
  0.570, 0.558 and **0.602**: mo-money is the least Chainlink-like and the most Binance-like of the three.
- In the 115 (window, second) cells where two or more wallets were filled, all of them bought the same side in 94.8%.
- Mo-money's deficit is spread over the |edge| buckets. It is not a small-edge effect.

**F5. No visible new configuration after the 17:06 ad-hoc restarts (checked, not supported).**
- BTC 15m posture after 17:06 is almach 0.853 (n 68, restarted), bosona 0.743 (n 35, not restarted) and mo-money 0.644
  (n 45, restarted). The pattern does not follow which engines were restarted.
- The new orders' original sizes after the restart are still 500 / 62 / 50 / 10.
- 54 minutes is too short to exclude a change. The exam lot begins right after it.

## Critique

1. **The side component, and with it the strategy's economic story, rests on one 6-hour Saturday block in a regime that
   began the day before.**
   - The 0.79 per fill, the 0.855 sigma-free part, the per-wallet numbers and the inertia all come from 10-31 12-18.
   - The historical replications fail, and F1 shows the failure is not the edge mix.
   - X52 and X68 (a historical match clock) were set aside as "lower priority because the exams run on live blocks".
     But the examiner's halves and per-wallet replication, and every later exam, depend on whether the posture is a
     stable rule or a property of the noise regime.
2. **Per-fill accuracy by wallet is treated as a property of the wallet's decision.**
   - The three wallets post the same rung within milliseconds, and mo-money is first in the match order in 74-90% of
     cases.
   - A front-of-queue order is the one that a passing small taker fills in the moment before a wrong-posture rung is
     pulled. The RE showed that filled orders agree with the posture more at the match than at the add.
   - So mo-money's 0.76 may be partly queue order, not a different engine. The per-wallet replication condition then
     turns on a selection effect that the quote rule cannot fix.
3. **"Why it works" does not match the measured PnL.**
   - FINAL_RULE says the cluster is paid "only a little" in rebates. They are about a fifth of net PnL (F3) and about
     40% of BUILD's BTC 5m PnL.
   - D4 measured locked pairs +$38.1k (+11.0%) against directional -$14.4k on VALIDATE. The "information + cheap
     underdog" story uses block-clock regions with a Binance reference, which the RE says cannot identify the side.
   - BTC 15m, half of R6's universe, earns 0.4%.
   - The investigation has not established which decision earns the money, so it does not know which component the
     outcome metric (PnL corr >= 0.5 under strict fills) has to reproduce.
4. **The operator's footprint has not been read.**
   - Cash, deposits and withdrawals are public, and they are cleaner than any fill-based measure (F2).
   - They rule out capital gating and tie the 01:00 UTC restart to a scripted weekly treasury.
   - FINAL_RULE's "~$45-56k of collateral per wallet" is the end-of-week peak. The working capital is reset to about
     $22-24k every Monday.
   - **Leak hazard.** Any balance, value or sweep amount at or after 10-31 06:00 aggregates sealed PnL. Use only the
     timestamps of the sweep transactions, never their amounts, recipients or which wallets swept.
5. **The exam spans the DST change, and the frozen rule's clocks are UTC.**
   - R3/R6 use UTC hour, weekday and a US-session flag (12-21 UTC). The calendar gate is in ET. The size session
     (08-17 ET) and the weekend gate look like US-hours schedules, while the cron (01:00 UTC) may be server time.
   - Every exam block after 11-01 06:00 UTC is in EST. X57 records the DST change as a future natural experiment. No
     ET-clock variant has been frozen, and the frozen rule will be wrong by an hour in at least one of these features.
6. **The primary metric is still a unit that cannot pass.** BTC 5m 10-s fill presence has an oracle ceiling of 0.80.
   The investigation should say which presence or selection bar it intends to meet and on which unit, before the next
   exam, not after.

## Proposals (ranked by the chance they close the gap)

### A1. Is the posture a stable rule? A historical sigma-free test on a match clock rebuilt from taker signing ms (strong form of X52/X68)

- **Hypothesis.** The engine has skewed toward the Chainlink report throughout the current version. The historical
  side deficit (0.60 BUILD, 0.54 STUDY; 0.62-0.63 even at |edge| > 0.1) comes from the block clock and the Binance
  stand-in. The alternative: the posture (or its visibility in fills) is specific to the noise regime since 10-30/31,
  or a version change near it. Then the side component is regime-conditional, and the lot and the next exams can
  disagree with the live block.
- **Why it fits.** F1: the |edge| mix explains about 0.75 of the live 0.79 if the rule were stable, but the historical
  accuracy is lower in every bucket. The sigma-free region D scores 0.855 live against 0.616 (BUILD), 0.640 (STUDY) and
  0.575 (VALIDATE aggregate) on the block clock. Region D does not depend on sigma, so the lower historical numbers
  come from the clock, the data or a different engine.
- **Test (sigma-free, so no vol choice enters).**
  1. Match time per historical cluster fill: T = the taker order's signing ms plus a sign-to-match delay calibrated on
     10-31, capped at the block time. The taker's ms is in the lot calldata for 97% of fill transactions. On 10-31 the
     server match ms and the calldata are both known; fit the delay by signatureType (median 671-764 ms).
  2. Chainlink report at floor((T - 1.432 s)/1 s), from `polymarket.com/api/crypto/crypto-price` 1-s data. Fetch STUDY
     and BUILD now: the endpoint keeps 30 days, so 10-09 drops out around 11-08. Strike = Gamma priceToBeat (`ptb_lot`
     for the lot).
  3. Market favourite at T from two proxies:
     - (a) the last clean print before T, at block resolution (usable in a rule);
     - (b) as a diagnostic only, the fill's own price where |p - 0.5| > 0.05, which fixes the market favourite without
       a book.
  4. Region D = sign(ln(CL/K)) disagrees with the market favourite. Score P(bought the Chainlink favourite) on STUDY
     case by case and on VALIDATE in aggregate.
  5. Calibrate first: the same proxies applied to 10-31 12-18 must give about 0.85. If they do not, fix the proxies
     before reading history.
  6. Secondary check: 5-60-s Binance markouts of posture-consistent against inconsistent fills, live and historical. If
     posture-consistent fills lose live, the live score partly measures pick-offs of a noise-driven skew.
- **Data.** Lot calldata (`b1_takers_*`, `b1_cluster_orders_*`), crypto-price 1-s Chainlink, `ptb_lot`, data-api tapes,
  the 10-31 calldata and recorder for calibration.
- **Signature if true (stable rule).**
  - Historical region D >= 0.80 with proxies that reproduce about 0.85 live.
  - The match-clock posture is then pre-registered for any historical replication, and the block-clock side numbers are
    retired.
- **If false.**
  - Region D stays near 0.60-0.65 with calibrated proxies: the posture belongs to the noise regime or to a recent
    version.
  - Then split the side component by Chainlink regime (lag-1 autocorrelation and 1-s noise per block, X46), pre-register
    the regime test, and report the smooth-regime side honestly as undecoded.

### A2. Mo-money: queue order or a per-account reference weight, not "a different clock" (strong form of X76)

- **Hypothesis, two rivals.**
  - (a) Queue selection. Inside the three-wallet bursts the three orders carry the same side and price, and the wallet
    first in the queue is filled during the brief life of wrong-posture rungs before they are pulled. Mo-money is
    first in 74-90% of matches, so its fills look off the posture.
  - (b) Per-account configuration. The three wallets are three separately treasured accounts (F2) and may carry
    different parameters. Mo-money's fair puts less weight on Chainlink and more on Binance: its Binance-fair posture
    is the highest of the three (0.602 vs 0.557-0.570) and its Chainlink posture the lowest (F4).
- **Why it fits.**
  - Mo-money's deficit appears in the sigma-free region D (0.799 vs 0.886-0.888), in every |edge| bucket, and already at
    the add (0.646 vs 0.77).
  - Its delay profile is flat, and its other sizes score like the other wallets' 500s. A clock offset predicts a shifted
    delay peak, which was not found.
- **Test.**
  1. (a) From the raw book and the calldata, take every burst triplet: two or more cluster wallets adding the same
     price, side and size within 20 ms. Compute P(filled before removal) by wallet and by queue rank, separately for
     right-posture and wrong-posture rungs at the add.
  2. (b) Fit one weight per wallet, fair = Phi(ln((w CL + (1 - w)(BN + basis)) / K) / (sigma sqrt(tau))), with basis =
     the trailing 60-s Chainlink minus Binance futures. Fit on 10-31 12-15 and score on 15-18 against the frozen rule
     and the delay scan.
  3. Repeat both on the 11-01 full-depth recording when any BTC or ETH family is on.
- **Data.** Own raw recorder / it6 extracts, `calldata/live1031_*` and `allmatch*`, `side_D`, dy_rtds, Binance
  futures 50-ms series.
- **Signature if true.**
  - (a) Within triplets the posture at the add is equal across wallets, but P(fill | wrong posture) is higher at queue
    rank 1 whatever the wallet. Mo-money's deficit falls by at least half when compared at equal rank. The per-wallet
    replication should then be stated for the quote, and the fill-side rule needs a queue term.
  - (b) Mo-money's weight w is about 0.4-0.6 and the others' about 1.0, with a held-out gain of at least +0.04 for
    mo-money and none for the others. A per-wallet constant then enters the frozen rule.
  - If neither holds, mo-money's 500 pass uses an input nobody has named yet. Record the size of the gap as the
    unexplained part.

### A3. Fix the clock conventions before the post-DST exam blocks, using the on-chain cron as a marker (strong form of X57; new marker)

- **Hypothesis.** The engine runs two clocks:
  - a server cron in UTC: the 01:00 restart, plus the Monday treasury sweep (F2);
  - a US-hours schedule in ET: the 08-17 ET size session, and the Friday-Sunday 18:00-09:00 ET module gate, perhaps run
    by a person.

  After 11-01 06:00 UTC the second clock moves one hour later in UTC. The first stays only if the cron is in UTC.
- **Why it fits.**
  - The sweeps fire at 01:00:06-01:01:03 UTC, inside the restart's 20 s, three wallets in consecutive blocks: a script.
  - The off-run starts (16:35-18:30 ET) and ends (08:30-11:25 ET) and the 12-21 UTC (08-17 EDT) size session read as US
    hours.
  - The frozen rule encodes all of these in UTC.
- **Test (all on development blocks; timestamps only).**
  1. 11-02 00-06 UTC (Monday, development): timestamp of the first sweep transaction and of the three salt-counter
     resets. Is it 01:00 UTC (UTC cron) or 02:00 UTC (ET cron)? Read neither the amounts, nor the recipients, nor which
     wallets swept: they aggregate sealed PnL.
  2. 11-02 12-18 UTC (Monday, first post-DST weekday session): the first 500-class order of the day in the calldata.
     Is it at 12:00 UTC (UTC session) or 13:00 UTC (ET)?
  3. 11-01 18-24 UTC (Sunday evening, development): if BTC 5m or 15m switches, at which ET hour.
  4. Pre-register now, before step 1, both variants of every clock feature (UTC hour, US-session flag, size session,
     calendar gate, restart). Freeze whichever the three observations pick. Re-score R6's clock features on the
     post-DST development blocks under both.
- **Data.** Polygon logs (pUSD Transfer from the three wallets, timestamps only), the cluster's calldata salts, the
  shared recorder.
- **Signature if true.**
  - The cron stays at 01:00 UTC, the size session moves to 13:00 UTC, and the gate follows ET.
  - R6's US-session and hour features, left in UTC, lose part of their contribution on post-DST blocks.
  - The ET-clock variant recovers it, and the calendar-gate AUC holds its pre-DST value only in ET.
- **If false.** Everything stays in UTC. One feature family is then closed with evidence before the exam rather than
  after it.

### A4. Locate the profit decision: pair completion and rebates against the directional posture (strong form of D4 and B9; required for "Why it works" and the outcome bar)

- **Hypothesis.** The cluster's net edge is mostly two-sided spread capture and rebates:
  - pairs completed below 1 within a window;
  - about 21% rebates (F3).

  The Chainlink skew is a defence that chooses which side fills first, so that the unpaired residual is not picked off.
  It is not a profit source by itself. If so, the per-window PnL variance that the outcome metric must reproduce is the
  residual × outcome, and a strict-fill replay must model pair completion from the recorded two-sided taker flow.
- **Why it fits.**
  - VALIDATE locked pairs +$38.1k (+11.0%) against directional -$14.4k (D4).
  - BTC 15m earns 0.4% on $1.26M before rebates. BTC 5m weeks swing from +38k to -8k.
  - Rebates are $14.5k against BTC 5m's $35k in BUILD.
  - The region-based story (73% of BUILD PnL from underdog fills in region A) uses the block clock that iteration 9
    showed cannot identify the side.
- **Test.**
  1. Per window and wallet, for BTC 5m, 15m, 4h and hourly (BUILD, STUDY, VALIDATE aggregate, live), split the PnL into
     three parts:
     - locked pairs: min(Up, Down) shares × (1 - pair cost), merges included;
     - the residual (net shares × (outcome - average price));
     - the rebate share: the daily MAKER_REBATE allocated by the wallet's fee-weighted maker fills, fee 0.07 p(1-p) per
       share.
  2. Regress each part on the window's posture accuracy (live) and on its region mix (historical).
  3. Compute which part carries the cross-window variance of the wallet's PnL.
  4. Design X64's replay to reproduce that part first.
- **Data.** Activity (TRADE, MERGE, REDEEM, MAKER_REBATE), Gamma outcomes, the RE's per-fill tables, the recorder for
  the live blocks.
- **Signature if true.**
  - The residual earns about zero or less in every split while pairs and rebates are positive in every split.
  - Posture accuracy predicts a smaller residual loss, not a larger profit.
  - Over 80% of the cross-window PnL variance is in the residual, so the PnL-corr bar is a replay of taker flow against
    the ladder, not a better side signal.
- **If false.** The residual earns in every split and rises with posture accuracy. Then the information story stands,
  and FINAL_RULE should give rebates their measured weight.
