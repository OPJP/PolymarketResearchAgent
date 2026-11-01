# Panel, iteration 14: assumption breaker (fresh eyes)

Written 2026-11-01, about 11:40-12:55 UTC. Nothing sealed was opened. I checked every unit I touched against
`tools/sealed.py` (`tommy-cs2-maker`: development 10-31 00-06, 10-31 12-18, 11-01 06-12; everything else from H on is
sealed). The 11-01 events below started 09:00-11:00 UTC and the 10-31 events 12:10-17:45 UTC, so all are development
units.

New network reads, all through the polyrea adapters and the shared cache:
- data-api `/activity` for the six operator accounts over development windows only: 10-16..H, 10-31 00-06, 10-31
  12-18 and 11-01 06-12;
- Gamma `markets_by_condition` for 48 sampled operator markets of 06-15..10-12 (development). I printed only the
  parameter fields and stored no raw record.

Everything else came from `.cache/re/tommy-cs2-maker/`: orders, chain fills, calldata, cached tapes and the listing
projections.

**What I read**
- BRIEF.md in full.
- NOTES iteration 14 in full, plus the earlier sections the checks below depend on.
- state.json: all 242 catalog items, the 38 dimensions, components, target_metrics and the hypothesis ledger.
- FINAL_RULE.md (rule table, price, size and outcome rows).
- panels/iter13_assumptions.md in full, and the proposal titles of the earlier panels.
- There are no EXAM or wall-audit files.

**What I ran.** The scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/p14/`:
`fill_time_anchor.py`, `fill_time_own.py`, `bidside_anchor.py`, `fill_null_others.py`, `inv_cap.py` and
`inv_skew_price.py`, with JSON outputs next to them, and `sib_events_1016_H.json`. The account and Gamma checks ran
inline. Each process stayed under 300 MB.

## Checks (so nobody redoes them)

### A. The wallet is one outlet of the operator's process. Events it "skips" are traded by sibling accounts.

**Development blocks after T0** (data-api activity, TRADE rows by event; each event went to exactly one account):

| Block | Studied wallet | 0xd2bb9459 | 0x7d67f01d | Others |
| --- | --- | --- | --- | --- |
| 10-31 12-18 | 2,324 rows (2,200 trades, 114 merges); 5 CS2 + 2 Dota events | 382 rows (17 merges): cs2-fokus-baks 176, cs2-jjh-bmb 176, cs2-og1-is 7 | cs2-1win-5s 67, dota2-xe-hn 143, LoL | 0x10d79cc7 LoL 264 |
| 11-01 06-12 | **0 rows** | 672 rows (648 trades, 24 merges): **cs2-bca-pha 137**, cs2-jjh-mzp 511 | 410 rows (36 merges): **cs2-the9-5s 232**, **dota2-synaps-hn 140** | 0x52661b8e tennis only |

- Every trade above is a BUY. Median sizes are 43-52 (0xd2bb9459) and 28-42 (0x7d67f01d).
- Iteration-14 findings 16 and 4 report the 11-01 06-12 block as "0 traded, no AUC", with cs2-bca-pha and
  dota2-synaps-hn skipped. The operator traded both of them, and cs2-the9-5s, on other accounts.

**16-22 Oct (10-16..H)**

| Account | Esports events | Shared with the wallet | Notes |
| --- | --- | --- | --- |
| Wallet | 80 | | |
| 0x7d67f01d | 19 | 4 | |
| 0x52661b8e | 18 | 10 | 5-share shadows |
| 0x67119033 | 20 | 2 | |
| **0x10d79cc7** | **116** | **0** | 15,501 rows from 10-16 00:02 to 10-22 21:47: 14,280 trades, 963 merges, BUY 1.0 |
| **0xd2bb9459** | **29** | **0** | 15,502 rows: 14,773 trades, 586 merges, BUY 1.0 |

Iteration-14 finding 7 says these two accounts "quote before 10-16, in the earlier account's markets". That holds only
inside the calldata sets the census decoded. Their full activity runs through the whole BUILD / VALIDATE window.

**Where the two new accounts trade.** Of their CS2 trades:
- 0x10d79cc7: 10,475 are in GRID-flagged events. Its leagues are CCT Europe 28, Elisa BreakOut 9, Logitech G Pro 8,
  CCT South America 6, Thunderpick World Championship 6, EPL 5 and United21 4. Another 3,127 of its trades fall
  outside the CS2 listing universe (Dota events) and 337 in non-GRID events.
- 0xd2bb9459: all 9,128 are in GRID-flagged events.
- In all, the sibling accounts traded 52 Dota events in 16-22 Oct, against the wallet's handful of maps.
- In the CS2 listing universe of 16-22 Oct (384 events), the wallet traded 77 events and sibling accounts alone traded
  94 more.
- So "GRID 0/122" belongs to the wallet, not to the operator. **The operator trades GRID events at scale, on other
  accounts.** These trades are BUY-only with merges; X203 measured maker shares of 0.97 / 1.00 on the two accounts'
  decoded pre-10-16 orders. Activity rows do not say maker or taker, so the maker share inside 16-22 Oct is not yet
  measured.

**The wallet's own skips in its leagues.** Of the 72 non-GRID events in its leagues that the wallet skipped in 16-22
Oct, 14 were traded by 0x7d67f01d:
- on 10-16, the switch day: PGL ef1-bca, and Stake Pulse fnc-hero and nip-tl1;
- on 10-19..10-22: DraculaN 7, Stake Ranked 2 and CIS LAN 2.

That covers both Stake Pulse false alarms of E2 and 1 of its 4 PGL ones.

Allocation is not simple overflow. At the start of each event, the mean number of other wallet events already in
progress is:

| Event class | Other wallet events in progress |
| --- | --- |
| Traded by the wallet | 3.19 |
| Given to a sibling | 2.57 |
| Skipped by every account | 3.38 |

**Trend.** The wallet's share of the operator's covered non-GRID events:

| Period | Wallet share |
| --- | --- |
| 16-22 Oct | about 77 of 91 |
| 10-31 12-18 | 7 of 12 |
| 11-01 06-12 | 0 of 4 |

The exam lots h1 / h2 (10-23..10-30) lie between the first two.

### B. The GRID arm, first look (fill time only; activity rows mix maker and taker trades)

Within one tick of the last clean print strictly before the fill second (the operator's own transactions excluded):

| Fills | n | At -1c | At 0c | In [-5, +1]c | Median offset |
| --- | --- | --- | --- | --- | --- |
| 0x10d79cc7, GRID CS2 | 10,375 | 0.525 | 0.515 | 0.713 | 0c |
| 0xd2bb9459, GRID CS2 | 8,494 | 0.606 | 0.560 | 0.791 | -1c |
| Wallet, VALIDATE filled maker orders | | 0.479 | | | |
| Generic whole-cent makers (check C) | | 0.605 | | | |

The GRID accounts lie between the wallet and the generic makers. This is inconclusive until their calldata gives sign
times (proposal P3).

### C. The quote at fill time: the brief's own "censored observation of the quote"

`evaluate()` scores each filled maker order against the last print at its signing second. Scoring the same orders
against the last clean print strictly before the fill block gives (VALIDATE, n = 12,113):
- 0.305 raw at signing becomes **0.395 raw at the fill**;
- with the BUILD median offset (-1c), 0.300 becomes **0.479**;
- BUILD: 0.306 becomes 0.518.

By age at the fill (VALIDATE, raw print):

| Age at fill | Share of fills | At signing | At the fill | In [-5, +1]c at the fill (at signing) |
| --- | --- | --- | --- | --- |
| 0-2 s | 1.5% | 0.25 | 0.26 | 0.65 (0.54), for 0-10 s |
| 2-10 s | 36% | 0.33 | 0.41 | |
| 10-30 s | 29% | 0.34 | 0.44 | 0.77 (0.56) |
| 30-120 s | 25% | 0.25 | 0.35 | 0.82 (0.48) |
| > 120 s | 8% | 0.26 | 0.31 | 0.87 (0.49) |

So the market does catch up with its value while an order rests. The miss that remains at the fill is mostly the
slot and short-lived (adverse) fills.

**Population null** (`fill_null_others.py`): other makers' whole-cent BUY maker orders in wallet-free transactions of
the same markets (VALIDATE, 55,264 fills, 1,070 makers), against the same anchor:

| Age | Within one tick at -1c | In band |
| --- | --- | --- |
| All | **0.605** | 0.803 |
| 0-10 s | 0.43 | |
| 10-30 s | 0.66 | |
| 30-120 s | 0.75 | |
| > 120 s | 0.84 | |

**Reading.** The wallet is 13 points less print-anchored than a generic maker, even at the fill. The 0.80 bar sits
above what the maker population reaches against any public anchor. Other public anchors at the fill do worse:
- the wallet's own previous fill on the token: 0.40;
- the bid-side print alone: 0.376;
- the union ceilings: 0.51-0.55.

The fill-time unit does not rescue the price item, but it gives an exact private share.

### D. A hard net-inventory cap that no outcome replay uses

CS2 maker fills (own state), with net = shares of the token minus the complement before the fill. The share of fills
that land on the long side:

| Net position | Share on the long side (VALIDATE) |
| --- | --- |
| < 200 | 0.44 |
| 200-400 | 0.37 |
| 400-600 | 0.21 |
| >= 600 | **0.00-0.03** (n about 1,000) |

BUILD is the same. Other measurements:
- **Peak net position per market:** median 590; 63% of markets reach 550 or more.
- **Price skew:** small. The median offset is -1c, and -2c when long 200 or more. A skew rule fitted on BUILD scores
  0.24 on VALIDATE against 0.30 for the constant.
- **The unpaired side won only 32% of markets.** The residual is -$14.2k on the 155 markets it lost and +$5.8k on the
  74 it won. corr(residual, unpaired x (2 won - 1)) = 0.966.
- **Variance:** locked margin explains 81% of the per-market PnL variance (corr 0.84).
- **The replays:** `margin_replay.py` (iteration 5) used IMAX 400. The X202 continuous five-slot ladder (0.315 / 0.238)
  has no inventory cap.

### E. The 09-17 change point is not a Polymarket parameter change

48 operator markets, 06-15..10-12:
- unchanged throughout: `secondsDelay` 1, `clearBookOnStart` true, `orderMinSize` 5, `rfqEnabled` false;
- changed in July, not September: the fee moved from `sports_fees_v2` (rate 0.03, rebate 0.25, still in force on
  07-06) to `sports_fees_v3` (rate 0.05, rebate 0.15, from 07-20);
- reward parameters vary by market.

Nothing changes at 09-03..09-17, so the design change is the operator's own (C4b for the 09-17 point).

## Critique: what the investigation takes for granted

1. **"The wallet is the strategy."** The decision process belongs to the operator. The wallet is one of at least five
   outlets, and events are routed to one account each (check A).
   - **Selection is two decisions.** Selection, the only component that passes on VALIDATE, mixes operator coverage
     with account allocation. The rule decodes only the first.
   - **The forward record is drifting away from the wallet:**
     - the "0 traded" VALIDATE-live block is an allocation artefact;
     - h1 / h2 sit inside a period when events were moving to 0xd2bb9459 and 0x7d67f01d.
   - **Exam risk.** If allocation is not predictable, the wallet's exam recall can collapse while the operator's
     process is unchanged. No price or V work can protect against that.
   - **The user's wallet list.** Whether it should be the operator's accounts is a question for the user, and it is
     cheap to ask now.
2. **"The non-GRID boundary is the feed's coverage."** At the operator level it is false. 0x10d79cc7 and 0xd2bb9459
   traded about 200 CS2 markets, nearly all in GRID-flagged events, during 16-22 Oct (BUY-only, with merges).
   - Either the operator quotes GRID events without the push feed, or it has a second feed.
   - Either way the GRID arm is the cleanest natural experiment available: the same machine with a different
     information set.
   - X188 tried this on the 5- and 20-share shadows with 71 rounds. The new accounts give about 19.6k GRID-event trades with cached
     tapes.
3. **"The pre-registered live tests have no units."** The operator's process traded 4 development units in 11-01 06-12
   and 5 more beside the wallet in 10-31 12-18. These include dota2-synaps-hn and dota2-xe-hn, the Dota units X118
   has waited for. They sat on recorded books, Valve snapshots and Thunderpick polls.
4. **"A value lagged by 0.25 s keeps none of the price item" is stated relative to the wallet's own burst.**
   - The wallet re-prices +0.4 to +1.5 s after the feed's message (E3-1). A source with latency L after the message
     therefore leads the burst in every case where the burst comes later than L.
   - X201 excludes the stream, chat and Valve's 4-s snapshots. It does not exclude a sub-0.4-s source, such as a
     sportsbook or vendor socket.
   - The consent requests should be framed against the message, not the burst.
5. **The price bar against the right population.** At the fill, the brief's own censored observation, a generic maker
   is only 0.61 within one tick of the best public anchor (check C).
   - The 0.80 bar is unreachable by public anchoring for any maker, and the per-order oracle cap with V known is 0.73.
   - The unit ruling (set unit or top-of-burst) is therefore not optional. It should be asked with these numbers.
6. **The outcome replays leave out the wallet's exit policy.** The cap is about 600 CS2 shares (check D), and the
   per-market PnL is 81% locked margin plus a cap-bounded adverse residual. Until a replay carries the wallet's own
   cap, band and re-pair, "the outcome item is gated by V" is not yet shown.

## Proposals (ranked by the chance they close the gap)

### P1. Decode the operator, not the wallet: account allocation as a decision component, and pooled selection (new; strong form of X176 / X187 / X203)

**Hypothesis**
- The operator's process trades the events of its coverage and routes each event to one account by a rule. Candidate
  inputs:
  - league or organizer, and the GRID flag;
  - the title (CS2, Dota or LoL);
  - the scheduled hour;
  - each account's concurrent load and its USDC balance;
  - a rotation or A/B schedule (0x7d67f01d's profile name is "BACKTESTEOCARAIO1").
- The wallet's skips in covered leagues, and its forward silence, are allocations.

**Why it fits.** Check A:
- each event goes to one account;
- 14 of the wallet's 72 in-league skips went to 0x7d67f01d;
- the 11-01 06-12 non-GRID events went to the siblings;
- the GRID events went to 0x10d79cc7 and 0xd2bb9459;
- the wallet's share fell from about 0.85 (16-22 Oct) to 0.58 (10-31 12-18) to 0 (11-01 06-12).

**Test** (laptop, development periods only)
1. **Operator event table.** For every CS2 / Dota / LoL event in the listing universe, 06-16..H and each development
   block after T0, record which operator account traded it. Use data-api activity of the six accounts clamped to
   development periods; the calls above cost 32 requests per account-week.
2. **Allocation model.** Fit a multinomial on BUILD with outcomes wallet / 0x7d67f01d / 0xd2bb9459 / 0x10d79cc7 /
   none, on listing-time features only:
   - league, organizer, tier, GRID flag, title, scheduled hour and weekday;
   - the operator events in progress per account at listing and at start;
   - each account's USDC.e / USDC balance at listing, from Transfer logs;
   - days since each account's first trade.

   Score it on VALIDATE and on the 10-31 / 11-01 development blocks.
3. **Pooled selection.** Re-score frozen v5 on the same events against "any operator account traded" and against "the
   wallet traded". Report AUC, recall at lift 3 and gain over activity for both.
4. **Rotation.** Daily share of the operator's events per account from 09-01 to 11-01 (development periods only), with
   change points (C4). Align them with the 09-17 design change and the 10-16 switch.

**Data.** data-api activity (development windows), the listing projections (`universe*.parquet`,
`listing_proj_iter10.parquet`) and Polygon Transfer logs for the balances.

**Signature if true**
- Allocation is predictable out of fold (multinomial AUC >= 0.80, or a clean schedule or round-robin), and the
  forward share of the wallet follows from it.
- Pooled v5 selection keeps VALIDATE AUC >= 0.95 with recall >= 0.8 at the operator level.

Then:
- the selection component becomes "coverage x allocation", examinable on h1;
- the user should be asked to add the operator's accounts to the strategy's wallet list, so the examiner scores the
  process, not one outlet.

**If false.** Allocation is unpredictable from public listing data. Then:
- the wallet's exam selection is bounded by allocation;
- the investigation must report that bound before h1;
- the pooled scoring question goes to the user.

### P2. Run the pre-registered VALIDATE-live tests on the operator's units now, as a declared amendment (new)

**Hypothesis.** The same process quoted cs2-bca-pha, cs2-jjh-mzp, cs2-the9-5s and dota2-synaps-hn in 11-01 06-12, and
cs2-fokus-baks, cs2-jjh-bmb, cs2-1win-5s and dota2-xe-hn in 10-31 12-18, through 0xd2bb9459 and 0x7d67f01d. The frozen
live tests can therefore get units today. These are:
- X118 / X132, Dota re-pricing bursts by Valve snapshot class;
- X144 / X168, Thunderpick suspensions and levels;
- X47b / X164, round books before its signings;
- X159 / X175, withdrawals;
- X38 / X162, chat and Kick.

**Why it fits.** Check A. The own recorders `tommy_dota_rt`, `tommy_tp_odds2`, `tommy_cs2_near`, `tommy_cs2_rounds`,
`tommy_chat` and `tommy_kick_pdt` were running in both blocks, and the shared `clob_wallets` recorder may not hold
books of markets the wallet did not trade.

**Test**
1. **Amendment first.** Before reading any result, write a pre-registration amendment in NOTES: the account
   substitution, the size fingerprints, and the same frozen verdict rules.
2. **Same-process gate.** Decode the siblings' block transactions (publicnode, about 1.5k transactions) for signing ms,
   price and size. Require all of:
   - BUY-only whole-cent ladder, five slots, band [0.05, 0.95];
   - 0-5 ms co-signing excess with an operator account;
   - 504-ms loop phase on quiet bursts (X158);
   - a fixed lag behind P4e or group P;
   - the 300.22 + 7.28 x merges merge law.
3. **Labels.** If the gate passes, label the siblings' own levels on the recorded books by their size fingerprints
   (43-52 and 28-42 shares), validated against calldata as in X92.
4. **Run the frozen tests unchanged.** Report them as VALIDATE-live (operator), separately from the wallet.
   dota2-synaps-hn (140 trades) and dota2-xe-hn (143) are the first Dota units with Valve snapshots at receive time.

**Signature if true**
- The gate passes.
- At least one frozen live test returns a verdict. R vs K on the Dota units: re-pricing bursts by snapshot class
  (own-team kill, other-team kill, objective, none) against shifted clocks. Thunderpick as V: suspension coincidence
  and level at reopen.

**If false.** The siblings run a different design (the gate fails). Then the "one process" claim needs narrowing, and
the live tests wait for the wallet as before.

### P3. The GRID arm: the same machine with a different information set (strong form of X188; new data)

**Hypothesis.** One of two readings holds.

*(a) No push feed in GRID events.* The operator quotes the five-slot machine at V = public print + offset. Then:
- the machine (X163) is decoded with a public V;
- the wallet's private part is exactly the feed;
- the GRID-arm price item may pass on the set unit.

*(b) A GRID-covering feed.* Group G's vendor covers GRID and non-GRID events with the same delivery order (X120 /
X128). Then:
- the operator subscribes to two feeds;
- the vendor search (X102) changes;
- the wallet's GRID boundary is allocation, not coverage.

**Why it fits**
- Check A: about 19.6k GRID-event CS2 trades (BUY-only, with merges) by two operator accounts in 16-22 Oct, with cached tapes for 217 of 218
  markets.
- Check B: fill-time anchoring of 0.525 / 0.606 against the wallet's 0.479 and the population's 0.605. That lies
  between the two readings and needs sign times.

**Test** (historical, development)
1. **Calldata.** Decode a sample of 2-3k transactions per account from the activity transaction hashes: signing ms,
   limit price, size, and other orders.
2. **Sign-time anchoring.** Within one tick of the last clean print at signing, by burst class (V change vs refill),
   and the five-slot structure through the frozen X163 machine with V = print + BUILD offset.
3. **E3-style event study.** Their V-change decisions against:
   - group-G and group-P informed takes (I1 / I2 with group G);
   - public print jumps, other-book jumps and the first print after silence (I3-I6), at the pre-registered lags.

   Do they lead or follow the public tape?
4. **Fan-out lag.** Their lag behind group-G members on the same token: a fixed ms lag with a small event SD means a
   feed.
5. **In-round level change.** X181 form: the round-winner AUC of their in-round level change on bo3 rounds, against
   the print's.

**Signature (a)**
- Sign-time within one tick >= 0.45 at a constant offset.
- V changes follow public print jumps (positive lags) and not group-G signatures.
- In-round AUC about equal to the print's.
- The X163 machine with V = print scores >= 0.80 on the set unit.

**Signature (b)**
- Within one tick <= 0.32.
- V changes precede print jumps by 2-5 s and follow group-G signatures at a fixed ms lag.

### P4. Outcome replay with the wallet's own exit policy (strong form of X57 IMAX / X202)

**Hypothesis.** The per-market PnL is locked margin (81% of variance) plus a cap-bounded adverse residual (check D).
A public five-slot ladder that also carries the wallet's exit policy may track the wallet's per-market PnL much better
than the uncapped L5 (0.315 / 0.238). The exit policy is:
- a hard net cap of about 600 CS2 shares (and the Dota analogue, to be measured);
- a taper of long-side quoting from 200;
- the band;
- the 300-s merge loop;
- the K - L complement re-pair after takes.

**Test**
- Use the validated X57 engine: strict fills, the public anchor usable 2 s after its transaction, `match_slack` 2.
- Run L5 with IMAX in {400, 600, a 200-600 taper fitted on BUILD}, with and without the re-pair.
- Choose on BUILD and score once on VALIDATE. Report:
  - Pearson / Spearman against the wallet;
  - return;
  - per-market residual correlation with the wallet's residual;
  - halves.

**Signature if true.** VALIDATE Pearson and Spearman >= 0.5, return >= 0, on both halves. The outcome item then
becomes examinable with a public rule.

**If false.** The outcome item is gated by V even with the wallet's own exit policy, which is a sharper wall clause
than X155.

### P5. Fix the two yardsticks before the unit question goes to the user (metric; new form)

**Hypothesis.** Two yardsticks are measured against the wrong reference:
- the public ceiling of the price item is the maker population's, not the trivial anchor's;
- the latency a source needs is relative to the feed's message, not to the wallet's burst.

**Test**
1. **Population baseline.** Add the population baseline and the fill-time anchor to `evaluate()` (check C's
   definitions; BUILD offset), stratified by order age, beside the sign-time anchor.
2. **Latency CDF.** Redo X201 against the message. For V-change bursts with a visible informed cluster (E3-1 I2) or an
   informed take (I1), give the CDF of the burst's lag behind the message. A source with latency L precedes the burst
   in 1 - CDF(L) of cases. Also report the set unit with V known from the message on (message + L) for L in
   {0, 0.1, 0.25, 0.5} s.

**Signature if true**
- Population fill-time ceiling about 0.6.
- Median burst lag behind the message >= 0.35 s.

Then the user's ruling on the unit (burst-set or top-of-burst) and the consent requests can be framed with numbers:
which sources can carry the price item (latency < about 0.3 s after the message) and which can only identify the
feed's class.

## Overlap
- **P1 comes first and is cheap.** Steps 1 and 3 need about 30 minutes, and they decide whether h1 can pass selection
  at all.
- **P2 depends on P1's gate,** that is, on whether the siblings run the same process.
- **P3 replaces X188's shadow-account sample** with the GRID accounts. P1's allocation table gives its event list.
- **P4 reuses X57 / X202** and only adds the wallet's exit policy.
- **P5 changes no rule.** It changes how the unit question and the consent requests are put to the user and the
  examiner.
