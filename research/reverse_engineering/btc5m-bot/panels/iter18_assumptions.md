# Panel, iteration 18: assumption breaker

Lens: what the iteration-18 account takes for granted that may be false. After iteration 18 the account is:

- side and timing run on the Binance spot top-of-book microprice at a fixed knee 230-260 ms before the match;
- no venue on disk carries information beyond that knee, so the out-of-time side failure (0.72-0.75) is put down to clocks;
- the take is a coin among high-hazard instants;
- the size state S is "partly public" through the siblings W4 / W5, with an S agreement of 0.49 / 0.61 below the 0.75 bar;
- the size-class rate is configuration.

My central finding is that **the decision clock and the side input depend on whether CME Globex is open**. When Globex is closed
(the weekend, and the daily 21:00-22:00 UTC break), the operator's side saturates at the Binance spot knee, as the account says.
When Globex is open, the operator's side keeps aligning with Binance spot moves that occur up to about 100 ms after anything it
could have seen from Binance. That is the signature of an input that leads Binance spot in Globex hours. The crowd shows no such
rise on any day. The "sharp knee" of iteration 14 was measured on fit days that were two-thirds weekend. The live venue studies
were all run on a Saturday and a Sunday. The dimension inventory has no CME or Globex entry.

Second: iteration 18's S-agreement shortfall is a counting artifact plus a wrong sibling. Where the sibling state exists it agrees
with the operator's S at 0.80-0.84. W5 does not carry S at all. The binding term is coverage, and the same evidence says W4 is the
operator itself.

## Data and checks

Development data only:

- the capture-day frames of 10-17..22 (`it14/dcclock14_frame.parquet`, `dcclock14_crowd.parquet`, `hazard14_scored.parquet`);
- `it18/sib_frame.parquet`;
- the complete calldata of 10-20..22 (`it16/cdfull_*`);
- the data-api tapes of the VALIDATE week (`it16/tapes`);
- `.cache/re/btc5m-bot/fills.parquet` (before H).

`sealed.py btc5m-bot` at 12:23 UTC on 11-01 showed:

- released none;
- future examined until 10-31 00:00;
- development blocks 10-31 00-06 and 12-18, and 11-01 06-12;
- the current block (11-01 12-18) sealed.

Nothing sealed was read, `.cache/live/sealed/` was not opened, and no network call was made. The scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p18a\`.
Each ran in under 300 MB and under 3 minutes.

| script | what it measures |
|---|---|
| inline (knee profile by day) | first legs: accuracy of the univariate spot microprice sign over [m0 - c - 250, m0 - c) for c = 400..150 ms, per capture day (frame columns k400..k150) |
| inline (session split) | the same profile by CME Globex session (open Sun 22:00 -> Fri 21:00 UTC, daily break 21:00-22:00 UTC; CDT until 11-01); hourly gains, OLS with activity and move-size controls |
| inline (crowd control) | the same profile for 975,955 non-operator taker BUYs (`dcclock14_crowd`) by day |
| inline (hazard by session) | weighted AUC of the frozen knee-clock hazard (`hazard14_scored`, 10-20..22) by session |
| `drift.py`, `dayeff.py`, `armside.py`, `hiconf.py` | dc14-spot-like side model (same features and params as dcfit14): fit on one day and score every other day (6 x 6); out-of-fold by day, confidence and window minute; A/B arm x dispatch phase |
| `w4only.py`, inline | iteration 18's sibling state: coverage and agreement conditional on coverage; W4 only, W5 only, W4 + W5 |
| `behsib.py` | behavioural sibling search: for every non-operator wallet, agreement of its large (>= 60) and small BUY prints with the operator's true S |
| `w4rate.py`, `w4rate2.py` | hourly large share of DS / GF / XM against W4's, with the crowd's large share as a control (VALIDATE week) |
| `seed.py`, `takeS.py`, `cells.py`, inline | is the lean seed public; does the take hazard depend on S; is there a copy cap in the pre-signed ladder; does S carry across windows; does a rebate allocation change the per-window ranks |

## Critique

### 1. The knee is a property of the CME Globex session, not a constant of the bot

Univariate accuracy, first legs, nonzero moves only. c is the cut before the first leg's match m0, on the capture's exchange-mapped
spot book:

| day (session) | c = 400 | 300 | 260 | 230 | 200 | 160 | gain 260 -> 160 |
|---|---|---|---|---|---|---|---|
| 10-17 Sat (closed) | 0.641 | 0.736 | 0.834 | 0.837 | 0.832 | 0.821 | -0.013 |
| 10-18 Sun (closed until 22:00) | 0.616 | 0.729 | 0.864 | 0.862 | 0.859 | 0.856 | -0.008 |
| 10-19 Mon (open) | 0.612 | 0.705 | 0.822 | 0.836 | 0.850 | 0.860 | +0.038 |
| 10-20 Tue (open) | 0.592 | 0.704 | 0.823 | 0.845 | 0.865 | 0.882 | +0.059 |
| 10-21 Wed (open) | 0.602 | 0.719 | 0.815 | 0.829 | 0.839 | 0.850 | +0.035 |
| 10-22 Thu (open) | 0.647 | 0.720 | 0.781 | 0.786 | 0.793 | 0.796 | +0.015 |

Split by session over all six days:

| session | first legs | c = 260 | 200 | 160 | gain |
|---|---|---|---|---|---|
| Globex closed | 19,646 | 0.850 | 0.846 | 0.839 | **-0.011** |
| Globex open, US equity hours | 25,182 | 0.812 | 0.844 | 0.847 | **+0.036** |
| Globex open, other hours | 47,245 | 0.808 | 0.833 | 0.847 | **+0.039** |

- **Hourly test.** Over hours with at least 100 first legs, the mean gain is +0.036 in 85 open hours and -0.010 in 49 closed hours
  (Mann-Whitney p = 2e-14).
  - OLS of the hourly gain on open, log activity and log median move size: open +0.045 (t 6.1), activity and move size about 0.
  - In low-activity hours: open +0.036 (6 h), closed -0.009 (39 h). The effect is not quietness.
  - Per wallet, open / closed: DS +0.041 / -0.012, GF +0.023 / -0.010, XM +0.041 / 0.000.
- **The daily break hour (21-22 UTC) on the four weekdays** reads +0.019, -0.015, -0.022 and -0.004. The neighbouring hours read
  20h -0.001 / +0.031 / +0.006 / +0.011 and 22h +0.007 / +0.011 / +0.028 / +0.028. This is suggestive, not conclusive (about 100-500
  legs per hour).
- **Crowd control.** On every day, including the open ones, the crowd's profile peaks at c = 260 and falls after it. For example,
  10-20 reads 0.595 at 260 and 0.580 at 160. The weekday rise is specific to the operator; it is not market momentum.
- **The iteration-14 E1 test was pooled over mixed sessions.** Pre-registration 5's control (ii) asked for at most +1.5 points from
  c = 260 to 200, and it passed pooled (+1.2) on fit days that were Saturday, Sunday and Monday. Per day the gain is:

  | day | gain, c = 260 -> 200 | criterion (<= +1.5 points) |
  |---|---|---|
  | 10-17 | -0.2 | passes |
  | 10-18 | -0.5 | passes |
  | 10-19 | +2.8 | fails |
  | 10-20 | +4.2 | fails |
  | 10-21 | +2.4 | fails |
  | 10-22 | +1.2 | passes |

  It fails on three of the four weekdays. **E1 holds when Globex is closed; E2-like behaviour appears when it is open.**
- **This is not a usable feature.** By the investigation's own physics (Binance -> host about 105 ms, plus the 150-ms hold), the spot
  moves after about m0 - 255 reach the operator after its order has arrived. They are a lagging copy of what it reacted to. They are
  evidence of an earlier input in Globex hours, not something to put in a rule.

### 2. Every "no faster input" result was measured where none was expected

- All the live-lab venue work (kernel7, X20 / X24 / X41, X100 Coinbase, X88 alt venues) ran on 10-31 (Saturday) and 11-01 (Sunday),
  with Globex closed. The iteration-10 information panel noted this; nobody split by session.
- knee14's per-venue knees were measured on the fit days, two thirds of them weekend.
- knee14b's finding was that Deribit and Coinbase "keep rising past the arrival". That is exactly what a 24/7 venue looks like when it
  lags a Globex-led move.
- Weekends carry about half the orders (iteration 1). That fits an extra trigger source on weekdays.
- The 31-entry dimension inventory has no CME or Globex dimension; `state.json` never mentions CME.

A Globex product is the natural candidate:

- **CME BTC / MBT futures**, with **ES / NQ** as alternatives. They trade exactly when the effect appears, including the daily
  break.
- **Latency.** Aurora to London is about 35-40 ms one way, against about 105 ms from Tokyo. An operator reading CME would act on
  moves that Binance spot prints about 60-100 ms later, which is what the table shows.

### 3. The take coin is partly this missing input

The frozen knee-clock hazard on 10-20..22 (weighted AUC) by session:

| session | bins / positives | full | spot-only | Polymarket prints only |
|---|---|---|---|---|
| closed (the 21-22 UTC break hours) | 5,292 / 1,430 | **0.933** | **0.887** | 0.746 |
| open | 145,637 / 56,199 | 0.887 | 0.803 | 0.759 |

- When Globex is closed, Binance spot explains when the operator acts far better (0.887 against 0.803). Caveat: on the scored days the
  closed bins are only the break hours.
- In open hours, a decision triggered by a move that Binance has not yet printed looks like a random take on the Binance hazard. That
  is a candidate for part of the "coin" and for the presence gain that condition 2 lacks.

### 4. The iteration-18 size-state verdict is a counting artifact plus a wrong sibling

- **The counting.** `sib18_run.py` line 75 counts every order without a public state (`Spub == 0`) as a disagreement. The reported
  0.4319 / 0.495 public agreement equals coverage times conditional agreement:

  | split | coverage | agreement where covered |
  |---|---|---|
  | 10-20 | 0.527 | **0.820** |
  | 10-21..22 | 0.619 | **0.800** |

  The agreement by age of the latest print is 0.86 / 0.89 / 0.85 / 0.73 for 0-5 / 5-20 / 20-60 / over 60 s (10-20).
- **W5 is not an S-carrier.** Agreement with the operator's S:

  | state from | coverage | agreement where covered |
  |---|---|---|
  | W4 + W5 (sib18) | 0.53 / 0.62 | 0.82 / 0.80 |
  | **W4 only** | 0.50 / 0.58 | **0.84 / 0.84** |
  | W5 only | 0.08 / 0.17 | 0.62 / 0.53 |

  - P(large) with / against S_W4 is 0.21 / 0.05.
  - W5 runs a different menu (105 / 210, iteration 17 census).
  - sib18's S_pub is therefore contaminated by W5 prints.
- **Only W4 shares the decision memory.** In `behsib.py`, over the 10,036 non-operator wallets printing on 10-20..22:
  - W4's large prints agree with S 0.920 and its small prints 0.416;
  - W5 reads 0.587 / 0.539;
  - the pooled crowd 0.498 / 0.522;
  - no other wallet with at least 40 large and 40 small prints comes close (the next one has a difference of 0.30 on 57 prints).
- **What binds is coverage, not agreement.** Coverage rises through the window: 0.19 (0-30 s), 0.34 (30-60 s), 0.49 (60-120 s), 0.76
  (after 120 s), with agreement about 0.81 throughout.
- **The same evidence settles what W4 is.** W4 holds the operator's private hysteresis state, which no independent trader could.
  That is the strongest evidence yet that W4 is the operator. If the examiner rules so under X170, the route is inadmissible. The
  next iteration should not count on it, and the ruling should be asked now, separately for W4 and for W5.

### 5. The configuration rate is operator-wide and visible in W4 within the hour

Hourly large shares (fills of at least 60 per order) over the VALIDATE week, 163 hours with at least 20 W4 orders:

| | DS | GF | XM | pooled |
|---|---|---|---|---|
| same hour vs W4, Spearman | 0.70 | 0.63 | 0.69 | 0.74 (Pearson 0.84) |
| partial, given the crowd's hourly large share | 0.68 | 0.68 | 0.68 | 0.77 |
| W4's previous hour -> this hour | 0.69 | 0.57 | 0.63 | 0.68 |
| own previous hour (own state) | 0.71 | 0.72 | 0.64 | 0.75 |

The crowd's own large share correlates only 0.43-0.56. The size phases and the configuration changes are operator-wide settings,
publicly visible in W4 with a lag of under an hour. That carries the same X170 caveat.

### 6. Smaller points

- **10-22 is a day-level anomaly in the side.**
  - High-confidence (|p - 0.5| > 0.4) misses double on 10-22: 5.3-11.6% against 2.7-9.3% by window minute, in every wallet
    (DS 6.1 vs 3.3%, GF 5.9 vs 3.0%, XM 9.5 vs 4.4%) and in both A/B arms.
  - It persists outside the dispatch phase; the worst hours are 10-22 13h, 14h, 17h and 02h.
  - On that day the profile is flat at 0.78-0.80 at every cut. The operator's input diverged from Binance spot even 100 ms later.
  - A CME record of 10-22 would show whether the operator followed CME that day.
- **Condition 7's side halves sit on the margin.** They read 0.852 / 0.823 on 10-20 / 10-21..22, a gap of 2.9 points against a bar of
  3. This day factor decides it.

## Checked and not supported (so nobody redoes them)

- **The side mapping does not drift.**
  - Fit on one capture day and score every other day: the two-way fixed-effects slope of accuracy on the gap in days is -0.0008 per
    day.
  - The monotone 0.857 / 0.837 / 0.815 over 10-20..22 is score-day difficulty. 10-22 scores 0.81-0.82 under every fit, 10-18
    0.85-0.87.
  - Weekend days are not harder: out-of-fold 10-17 reads 0.847 and 10-18 0.871.
  - The share of confident decisions (0.48-0.61 by day) explains most of the day differences. Standardized to the pooled
    composition, the days read 0.825-0.850.
  - So the out-of-time 0.72-0.75 is not drift and not a weekend effect.
- **The A/B arm does not change the side.** Both arms read 0.816-0.818 in the dispatch phase and 0.846-0.849 outside it.
- **S resets every window.** The first large order's side equals the previous window's final S in 0.523 of windows and the previous
  outcome in 0.507. Only 6.9% of orders fall before the window's first large one.
- **The seed (the first large decision) is not publicly identifiable.**
  - The AUC of |microprice 250 ms| for "this is the seed", among the orders up to the seed, is 0.685.
  - Seeds are fast followers 60% of the time against 8.6% for first legs, and are carried by GF / XM. Both of those come from the
    operator's own timing.
- **The take hazard does not depend on the direction of S.**
  - Weighted P(take) is 0.0065 with S and 0.0075 against it.
  - Adding the true S to the frozen hazard gains +0.004 / +0.001 AUC; adding S_W4 gains +0.001 / +0.000.
- **The pre-signed ladder has no copy cap.** The number of distinct used orders per (wallet, burst, token, cent, size) cell is
  geometric, with no pile-up (DS small: 24,455 / 6,129 / 1,564 / 409 / 105 / 26 / 4 / 1). There is one signing ms per cell.
- **A rebate allocation does not move condition 5.** Adding 0.5 x fee per window leaves the per-window ranks at Spearman 0.998.
  - The trading PnL after fees on 10-20..22 is +$4.1 per window (t = 0.50).
  - The income is the rebate (B6). Condition 5 measures a zero-mean exposure term, so it is not a lever.

## Proposals (ranked by the chance they close the gap)

### P1. A Globex-hours input: when CME is open the operator reacts to a venue that leads Binance spot by about 100 ms (new missing dimension; strong form of the iteration-6 / 10 information-panel remarks, and of E7 / X127 per session)

**Hypothesis.** When CME Globex is open, the side and timing decisions run on a Globex product: CME BTC or MBT futures, or ES / NQ.
Binance spot is the input only when Globex is closed. That covers:

- the drop of the knee rule from 0.850 to 0.81 in open hours;
- the weekday "continued rise";
- the hazard's 0.803 against 0.887;
- part of the take coin.

**Why it fits.** Critique 1-3: the session split is t = 6.1 after activity controls, the crowd is flat, and all 24/7 venues lag.

**Test.** Three steps, runnable on this laptop.

1. **On disk, now.** Run knee14 / knee14b with a session split for every venue on disk, on 10-17..22 first legs:
   - venues: spot book, spot trades on T, USD-M BTC / ETH, OKX swap, Bybit 100-ms bins, and the cached Deribit / Coinbase hours;
   - if a venue saturates at its own physical knee in open hours while spot keeps rising, that venue is the weekday input, and the rule
     can use it point in time today.
2. **A natural experiment this week, pre-registered before the data exist.** US DST ends on 2026-11-01. From then on, Globex opens on
   Sunday at 23:00 UTC and breaks daily at 22:00-23:00 UTC. The calendar makes these development blocks:

   | block | Globex | predicted gain G |
   |---|---|---|
   | 11-01 18:00-23:00 | closed | <= +0.005 |
   | 11-01 23:00-24:00 | open | >= +0.02 |
   | 11-02 00-06 | open | >= +0.02 |
   | 11-02 12-18 | open | >= +0.02 |
   | 11-03 06-12 | open | >= +0.02 |
   | 11-03 18-24 | break 22:00-23:00 UTC | the closed pattern moves from 21-22 to 22-23 UTC |

   - G = acc(c = 150-160) - acc(c = 260) on first legs.
   - The profiles use exchange-stamped Binance spot aggTrades from data.binance.vision (published the next morning), so no laptop
     clock enters.
   - The operator's match ms come from the live lab's CLOB trade records by tx hash, through iter_live.
3. **If no venue on disk saturates.** Enter the dimension `cme_globex_futures` as missing / paid, and ask the user to approve a data
   source. Millisecond CME data is not free; Databento CME MDP3 BTC / MBT for a few weekday hours of 10-19..22 is enough.
   - Measure the operator's knee on CME's clock. About 190-220 ms is expected: about 40 ms to the host plus the 150-ms hold.
   - Then score the side and the knee-clock hazard on CME in open hours.
   - Meanwhile (E6), label which open-hour decisions are Globex-led from the ex-post common move of the 24/7 venues in
     [m0 - 250, m0 - 100). This is a diagnostic, not a feature.

**Data.**

- the capture frames (on disk);
- the venue archives (on disk);
- data.binance.vision aggTrades for 11-01..03;
- the live-lab CLOB trades, and on-chain fills and calldata of the development blocks (the post17 pipeline);
- CME data only with the user's approval.

**Signature if true.**

- In step 1, every 24/7 venue keeps rising past its knee in open hours and saturates in closed hours.
- In step 2, G is at or below 0 before 23:00 UTC on 11-01 and positive after it and on 11-02, and the break hour moves to 22-23 UTC on
  11-03.
- In step 3, CME shows a sharp knee and the side reaches 0.88 or more on open-hour first legs. The open-hour hazard on CME returns to
  the closed-hour level of about 0.89 for the trigger alone, and the 10-22 anomaly disappears on CME.
- That would be the first input that could lift condition 2 at the decision clock above the book-aware baseline, because makers who
  read Binance would react after the operator.

**If false.**

- If G is session-independent on 11-01..03, the weekday rise is a weekday latency path of the operator's own. The anchor must then be
  measured per day, and the frozen 260-ms constant is a weekend value.
- If a venue on disk saturates, adopt it per session.

### P2. Make the frozen routes session-aware now (point in time; no new data; exam protection)

**Hypothesis.** dc14 and the hazard were fitted on 10-17..19, where about half of the first legs (53%) fall in closed sessions, and
scored on open days. The public Globex calendar is a legitimate input. Session-specific fits (or a session term) should help in open sessions:
there the weight shifts to the inputs and windows that track the leading move best, possibly the USD-M / ETH / OKX series at their
earlier knees (200-220 ms). It would also protect the exam's closed hours: 10-25 (Sunday, closed until 22:00) and the 21-22 UTC
breaks of h1.

**Why it fits.** Critique 1:

- the knee-level accuracy is 0.850 closed against 0.81 open;
- the hazard reads 0.887 against 0.803;
- h1 mixes the sessions.

**Test.**

- Pre-register first. Fit dc14_spot, dc14_full and the hazard separately on the open and the closed decisions of 10-17..19 (or one
  model with a session indicator and its interactions).
- Score once on 10-20..22 and on the reverse split (fit 10-20..22, score 10-17..19).
- Report by session, per wallet and by halves.
- Adopt only if the pooled per-order side and the hazard's gain over the book-aware baseline both improve on both splits, with closed
  sessions non-inferior (within 0.005).
- Never cut later than the physics floor. The rise at c below 255 ms is not a feature.

**Data.** On disk (`it14` frames and the capture).

**Signature if true.** In open sessions the side gains 1-3 points and the hazard's gain over the book-aware baseline rises. On the
reverse split the closed-session fit beats the frozen model on 10-17 / 10-18.

**If false.** Without the true input, session fits add nothing. Then P1 step 3 is the only route.

### P3. Correct the size state before the tracker run: W4 only, coverage-aware, and a two-part X170 (correction and strong form of X182 / X170)

**Hypothesis.** The public sibling state is accurate where it exists (0.84 with W4 only). Iteration 18's partial lift reflects
coverage (0.50-0.58) and W5 noise, not a weak state.

**Why it fits.** Critique 4:

- covered agreement is 0.82 / 0.80 with W5 and 0.84 / 0.84 without it;
- W5 alone reads 0.53-0.62;
- among 10,036 wallets only W4 shows the large 0.92 / small 0.42 signature.

**Test.**

1. Rerun sib18 with W45 = {W4}. Pre-register the bar as agreement of at least 0.80 on covered orders on both splits, with coverage
   reported by window-time band and age of print.
2. Execute E[size] from S_W4 in the mix14 tracker under strict fills, forward and reverse. Compare it with the same tracker without
   siblings, using a paired 2-h block bootstrap of the Pearson and Spearman gains.
3. Freeze both variants behind a switch (`size_route = menu | w4_state`), so the examiner applies its ruling without a refit.
4. Put X170 to the examiner as two questions, with this evidence:
   - (a) W4 shares the operator's private decision memory: is it the operator?
   - (b) W5 runs a different menu and does not share the memory: is it another trader?

**Data.** `it18/sib_frame.parquet`, `it16/tapes`, the mix14 harness.

**Signature if true.**

- Covered agreement of at least 0.84 on both splits.
- A PnL-proxy Spearman gain over the menu larger than sib18's +0.111 / +0.109.
- An executable Spearman of at least 0.50 on both splits, which is condition 5's missing 0.033.

**If false.** An executable gain under 0.02 even with W4 alone means the binding term is strict-fill execution, not the size
expectation. Either way, the honest prior is that (a) will be answered "the operator". The route then closes, and condition 5 must
come from non-operator inputs.

### P4. A point-in-time configuration tracker for the frozen version parameters (strong form of X175 / X181 / X123)

**Hypothesis.** The size-class rate (size phases, the post-T0 GF cut, the A/B arm's large share) is an operator-wide setting, visible
in W4's prints within the hour and in the wallets' own trailing large share. A frozen per-wallet constant is wrong whenever the
configuration moves, and h1's configuration is unknown.

**Why it fits.** Critique 5:

- the partial correlation with W4 is 0.68-0.77 given the crowd;
- W4's previous hour predicts this hour at 0.57-0.69;
- the operator's own previous hour predicts it at 0.64-0.75;
- the crowd tracks it at only 0.43-0.56.

**Test.**

1. Model the per-wallet rate as a_w + b_w x the trailing-60-min large share. Use W4 (pending X170) and, as a separately reported
   own-state variant, the wallet's own trailing share.
2. Fit on 10-16..19, which includes the size phases. Score on 10-20..22 (the 10-20 19-h phase) and on the three post-T0 development
   blocks (on-chain fills in `post/own_*`).
3. Report the per-window calibration of E[size] and the mix14 tracker's Pearson / Spearman against the frozen constants.

**Data.** On-chain fills, tapes, and W4's on-chain fills for the post-T0 blocks.

**Signature if true.**

- The rate tracks the phase onsets (10-19 01h, 10-20 19h) within an hour.
- It tracks the post-T0 GF cut (0.27 -> 0.08) within each block's first hour.
- The tracker's r improves by at least 0.02 on phase days and post-T0 blocks, and is unchanged elsewhere.

**If false.** If the rate is not trackable within the hour, write the configuration as an exam-time unknown in FINAL_RULE, with the
measured range of the class rate.
