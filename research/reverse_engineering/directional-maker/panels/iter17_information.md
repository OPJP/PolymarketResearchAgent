# Panel after iteration 17: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md (premise, hidden dimensions, catalog), NOTES.md (iteration 17 in full; earlier
iterations by search), state.json (catalog, components, dimensions, live_lab, splits), the iteration-16 information panel
in full and the proposal titles of every earlier panel. Of the parallel iteration-17 panels I read only the mechanics
panel's proposal titles, to avoid duplicates (its P3 and P4 touch my C2 and I17-4; see there).

Data I touched. All of it is development by `sealed.py` (released h1, h2; current block 11-01 06-12):

- `iter_live` reads of `dy_rtds`, `dz_rtdsbn`, `dm_cb`, `dm_bnf`, `dm_bns`, `dm_okx`, `dm_byb`, `dm_hl`, `dx_bst` and
  `dx_drb` for 11-01 07:00-09:15 UTC;
- the RE's quote-unit table `.cache/re/directional-maker/it14_qu_rebuilt_1793516400_1793524500.parquet` (11-01
  07:00-09:15; side convention from `code14/qu_oos.py`: `sd == 1` is an Up bid);
- Polygon RPC (publicnode): USDC.e `Transfer` logs for blocks 95,374,000-95,684,000 (the 10-12 sweep and the week
  after, BUILD), `eth_getCode`, nonce and balance of 12 addresses;
- data-api `activity` (with `end` <= H) and `value` for addresses that are not the studied wallets; Hyperliquid
  `userFills` and `userNonFundingLedgerUpdates` for one address.

Nothing sealed was read. I did not open the `btc5m_*` folders in `.cache/live/dev/`, which belong to another strategy.
My scripts ran from the session scratchpad and are not in the workspace; each check states its construction.

## What my checks found

**C1. In the clean regime about half of each Chainlink report is knowable from no public venue.**

- Data: 11-01 07:00-09:00 UTC; fit 07-08, test 08-09; 7,074 BTC report stamps; publish delay median 1,081 ms.
- Target: dCL(s) = CL(s) - CL(s - 1) for the value stamped s. Predictors: each venue's mid or last trade on a
  100-ms server-ms grid.
- Single venues (held-out R²), with the increment over [s + a - 1 s, s + a]:

  | venue | a = -1.0 s | -0.5 s | -0.25 s | 0 | +0.3 s |
  | --- | --- | --- | --- | --- | --- |
  | Binance USD-M futures | 0.12 | **0.42** | 0.40 | 0.27 | 0.08 |
  | OKX swap | 0.09 | 0.37 | **0.42** | 0.34 | 0.15 |
  | Binance spot | 0.08 | **0.40** | 0.34 | 0.27 | 0.11 |
  | Bybit perp | 0.12 | **0.39** | 0.33 | 0.24 | 0.11 |
  | Coinbase BTC-USD | 0.11 | **0.33** | 0.32 | 0.25 | 0.13 |
  | Deribit index | 0.01 | 0.08 | 0.09 | 0.31 | **0.39** |
  | Bitstamp, Hyperliquid | <= 0.03 | <= 0.10 | <= 0.14 | <= 0.19 | <= 0.20 |

- All eight venues together, with 0.5-s increments known by s + 300 ms (about 0.8 s before the publish): R² **0.52**.
  Futures alone: **0.46**. Known by s - 200 ms: 0.52 / 0.47.
- So the report-specific part u = dCL - prediction has sd $1.45, against $1.99 for dCL. Its lag-1 autocorrelation is
  -0.24, so part of it is reporting noise that reverts.
- The report reflects the venues about 0.25-0.5 s before its stamp (as iteration 16's C2 found for the futures).
  The Deribit index lags the report.

**C2. The cluster's at-touch posts react to that report-specific part within 150 ms of the public publish, and never
before it.**

- Units: 1,151 non-extreme (0.10-0.90) at-touch 500/1000 posts, 11-01 07:00-09:15.
- Signed event study around each `dy_rtds` publish P_i with |u_i| >= $1. "Agree" means the post is on the outcome
  whose Chainlink fair the innovation raised:

  | window relative to P_i | (-600, -300] | (-300, 0] | **(0, 150]** | (150, 300] | (300, 600] | (600, 1000] |
  | --- | --- | --- | --- | --- | --- | --- |
  | posts | 105 | 92 | **65** | 42 | 84 | 124 |
  | agree with sign(u_i) | 0.46 | 0.54 | **0.71** | 0.55 | 0.54 | 0.46 |
  | posts per 100 ms | 35 | 31 | **43** | 28 | 28 | 31 |

- One-sided binomial p for 46 of 65 is about 4e-4. The size of the reaction grows with |u|: 0.64 (n 84) at
  |u| >= $0.5, 0.71 at >= $1, 0.74 (n 43) at >= $2.
- With the futures-only innovation, which is all the 11-02 recordings support, the numbers are 0.64 / 0.73 / 0.75.
- It holds in both hours: 0.81 (n 21) at 07-08 and 0.66 (n 44) at 08-09:15; futures-only 0.84 / 0.68.
- No early reaction: posts 0-1 s before P_i agree with u_i at 0.505 (n 537). In (-300, 0] the agreement is 0.43-0.54
  for |u| >= $1 and >= $0.5. One exception: at |u| >= $2 the all-venue version gives 0.63 (n 51), but the
  futures-only version gives 0.53 (n 45), so it is probably leakage from the venue-predicted part.
- So the engine shows no Data Streams lead. It reads the report at public-relay timing, which agrees with iteration 13's
  tracers on the noise block.
- The venue-predicted part shows the same agreement for the current and the next report (0.68-0.78 for both), so it is
  the known futures re-peg, not a reaction to the report.
- Do venues beyond the futures move the post side? A logistic of the post's Up/Down on each venue's move over
  [t - 450, t - 50] ms (fit 07-08, n 359; test 08-09:15, n 792):

  | inputs | all posts | posts where a venue moved >= $2 (n 361) |
  | --- | --- | --- |
  | futures | 0.681 | 0.829 |
  | all 8 venues (+ u) | 0.705 (0.702) | 0.814 |

  Where anything moves, the futures carry all of it. Coinbase, OKX and the others add nothing.
- 59.5% of these posts follow no venue move >= $2 in 400 ms, and fewer than 6% fall within 150 ms of a large-innovation
  publish. For the majority, no external feed decides the side.

**C3. X59 can be closed: Polymarket's RTDS Binance relay is Binance spot at whole seconds.**

- `dz_rtdsbn` BTC on 11-01 08:00-08:30: 1,800 stamps. The value equals the last Binance spot aggTrade price at the
  stamp's exact second in 99.2% of stamps (86% at -100 ms, 85% at +100 ms).
- It is published 128 ms after the second (p10 122, p90 143).
- So it carries strictly less than a direct Binance spot feed.

**C4. The weekly sweep leaves Polymarket for a custodial venue, and the three treasuries meet there.**

- On 10-12 the three sweep EOAs forward the full amounts to one address 16-28 blocks after they receive them:
  - 0xe3c61b5aaf28dbe533816d9587ce1abaf97c974b (mo-money): $26,258.50;
  - 0x44c83a63e3d614a8a2c38f088808c56d678a1d92 (almach): $27,574.81;
  - 0x2084ab26cd2ccdeb659cd83b4250c429fd7b2ee5 (bosona): $21,402.99;
  - destination 0x1891b583a86daf0f149ba9712a61506138526c6f (blocks 95,374,394 / 401 / 408).

  This corrects iteration 9's "never commingled": the three flows join at this second hop.
- The destination looks like an exchange consolidation wallet:
  - a plain EOA, nonce 25,120, 915 POL, $1.11M USDC.e now;
  - over 10-12..10-19: 42 senders, $13.6M in, 118 receivers, $14.7M out;
  - $7.26M minted and $7.63M burned through the PoS bridge;
  - round transfers of $500k-$725k, in triplets at adjacent blocks, to EOAs with nonces of 295k-441k;
  - no Polymarket activity before H, and no Hyperliquid fills or ledger.
- So the three sweep EOAs look like deposit addresses at one centralized venue. Whatever the operator does off Polymarket
  (banking, or a hedge on its reference venue, Binance futures) is custodial and not on chain.

## Critique

1. **The negative "Chainlink report changes do not link" is a weak-form result.**
   - T13 screened 9,917 raw report changes on the publish clock. In the clean regime about half of each change is the
     futures move of 0.5-1 s earlier (C1), and that part has already been acted on by the re-peg.
   - Decomposed, the report-specific part does link, sharply and only after the publish (C2).
   - The engine therefore reads two inputs in the clean regime: futures at about 150 ms, and the Chainlink report when
     it is published.
   - The level posture cannot show this at small edges, because it also carries the unidentified sigma (k) and the
     strike mapping. A change-on-change unit is free of both. Iterations 15-17 drew the clean-regime conclusion ("the
     post side is near the cheaper token") from level tests only.

2. **H2 (a faster hidden reference) can now be narrowed with data the RE already holds, but has not been.**
   - The clean block 11-01 06-12 has eight venue recordings (`dm_cb`, `dm_okx`, `dm_byb`, `dm_bns`, `dm_hl`, `dx_bst`,
     `dx_drb`, `dm_bnf`) that no iteration after 6 used. Iteration 6's venue race ran in the noise regime.
   - What C1 and C2 show:
     - no venue predicts more than about 52% of the report;
     - the engine shows no reaction before the publish;
     - non-futures venues add nothing on moving posts.
   - Together with iteration 13's tracers (noise regime), this is the measured footprint of "no Data Streams lead, no
     composite" on both regimes. It belongs in `dimensions` as `no_effect` with its power. It is not still open.

3. **The remaining side residual is mostly internal to Polymarket, and the account should say so quantitatively.**
   - 59.5% of at-touch posts follow no external move and no fresh report (C2). Feeds cannot explain their side.
   - Earlier evidence says those posts are re-joins about 95 ms after a trade on the token (X35), i.e. replenishment of
     rungs that takers consumed.
   - The information lens has two targets left:
     - (a) the events that do move the quote (I17-1);
     - (b) the information of the takers whose arrival picks the filled side (I17-2).

     The second is a counterparty description, not an engine input, and must be reported that way.

4. **The data plan for the next exam has a hole.**
   - The live inputs that the frozen rule's timing component rests on stop on 11-03 00:00: `dx_bnf`, `dy_rtds` and the
     venue feeds (`dm_*` already ended 11-01 12:00). The shared recorder has no Binance futures at all.
   - Exam blocks after 11-03 are scorable only on recording-free inputs. The Chainlink values are covered (T9: endpoint
     parity is exact). The futures jump detector on Binance aggTrades archives (ms) has not been checked against the
     bookTicker version. The publish clock would have to be the stamp plus 1,081 ms (p10 781, p90 1,479).

5. **Ledger corrections from my checks:**
   - C3 closes X59;
   - C4 corrects iteration 9 F2 and advances X118: the next hop is custodial, so the on-chain hedge route is closed;
   - C1 and C2 are the strong form of E3's Chainlink row and the first E4 discrepancy indicator (report minus venue
     nowcast).

## Proposals (ranked by the chance they close the gap)

### I17-1. The report innovation is an engine input at public-relay timing: a side law from reference events, confirmed out of sample, plus its recording-free exam path (new; strong form of E3's Chainlink row, E4, X163 and X198)

- **Hypothesis.**
  - The quote is re-sided by two event streams:
    - Binance futures jumps, within 50-150 ms;
    - the report-specific innovation u_i of each public Chainlink publish, within 150 ms of P_i.
  - Between events, the side persists, or is replenishment.
  - An event law describes the at-touch posts, and the fills taken from them, better than the level posture at small
    edges, where the posture fails because k is not identified.
  - The engine has no earlier access to the report.
- **Why it fits.**
  - C2: 0.71 agreement in (0, 150] ms against 0.46-0.55 in every other window, with a 1.4x post rate and a dose
    response in |u|.
  - T13: futures 0.5-s jumps, signed q 0.001, peak +0.15 s.
  - X163: posture-change signature 0.67-0.72 after the publish against 0.43 before.
  - Iteration-13 tracers follow the report stamped about 1.25 s earlier.
  - The clean-block small-edge failures (0.44-0.58) and the 11-01 E7 synchronized misses, 60% of which no futures move
    explains.
- **Test.**
  1. Freeze everything on 11-01 07:00-09:15, which I have already looked at, so treat it as BUILD:
     - the innovation model: futures-only, four 0.5-s increments known by stamp + 300 ms, OLS on 07-08;
     - θ_u = $1;
     - the window (0, 150] ms;
     - the T13 futures-jump detector (k3 / 0.5 s).
  2. Event law E, for each at-touch 500/1000 post at t, in this order:
     - if a publish has P_i in (t - 150 ms, t] and |u_i| >= θ_u, take sign(u_i);
     - else, if a futures jump ended in (t - 450, t - 50] ms, take its sign;
     - else take the R8c posture.

     Score accuracy overall and by |F - mid| band (< 0.05, 0.05-0.1, >= 0.1) against:
     - the posture;
     - the cheaper token;
     - the W500 "rose" rule;
     - "the token whose bid was hit by the last clean print".
  3. Confirm once, out of sample, on:
     - 11-01 09:15-12:00 (posts rebuilt from `dm_clob_raw`, same day, not yet scored);
     - 10-31 17:29-18:00 (noise regime, `dy_rtds` exists; u dominates there);
     - 11-01 18-24, 11-02 00-06 and 11-02 12-18 (`dx_clob` posts, `dx_bnf` futures-only innovation).

     Nulls:
     - a one-sided binomial for the (0, 150] agreement;
     - a swap null that moves each innovation to the publish 1-3 before or after.
  4. Latency, per instance:
     - the agreement curve in 25-ms bins over (-1,000, +500] ms around P_i;
     - per wallet, on filled orders attributed by calldata salt. X76 found wallet delays of 1,083 / 1,432 ms; a
       different peak per wallet names a different feed path.
  5. On fills on the match clock, the counted unit of the live exam lot: E against R8c per fill, per wallet and by
     band.
  6. A recording-free path for exam blocks after 11-03:
     - build the 0.5-s jump detector from the Binance USD-M aggTrades archive (ms) and measure its event agreement with
       the `dx_bnf` bookTicker detector on one development hour;
     - publish clock = stamp + 1,081 ms, values from the crypto-price endpoint.
- **Data.**
  - On disk: `dy_rtds`, `dm_*` (to 11-01 12:00), `dx_bnf` / `dx_clob` (to 11-03 00:00), the RE's quote-unit builder
    (`code14/qu_oos.py`), and calldata for wallet attribution.
  - New downloads: one aggTrades archive day (~20-60 MB, checksum).
- **Signature if true.**
  - (0, 150] agreement >= 0.65 on every confirmation block with n >= 40, with (-300, 0] <= 0.55.
  - E beats the posture on posts by >= 0.05 at |F - mid| < 0.05 and does not lose at >= 0.1.
  - Per fill on the match clock, >= +0.02 over R8c on the post-T0 development blocks.
  - A peak inside (-900, 0] ms instead would be the footprint of direct Data Streams access, a blocked dimension found
    by its trace.
  - If confirmation fails, record E3's Chainlink row as `no_effect` with the minimum detectable agreement (about 0.15
    above 0.5 at n 65).

### I17-2. The display the paying takers see: strike crossings, the results strip and the countdown as the counterparty's information, for the filled side and for the arrival in quiet cells (new dimension; strong form of X45 and of X104's entry-flow baseline)

- **Hypothesis.**
  - The takers who pay the cluster trade on what the Polymarket page shows them:
    - the displayed current price against the price to beat (the RTDS report at its publish);
    - its crossings of the strike;
    - the strip of recent window results;
    - the countdown.

    These takers are non-HFT first prints, round-USD and Magic/Safe signers.
  - 81-88% of the cluster's maker fills are complement mints. The filled side is therefore the outcome opposite to what
    this crowd buys.
  - Their arrival after a displayed crossing is also the missing trigger of the quiet small-edge presence cells.
- **Why it fits.**
  - The presence residual is "one taker arrives" in quiet cells at |edge| < 0.05 (E2: FN 0.74 there).
  - The paying flow is non-HFT first prints (X38, X159).
  - The cheaper-token baseline (0.68) is itself the crowd buying favourites.
  - X45 tested only 1-s display changes (corr 0.03), never crossings or streaks. X104's net-flow baseline (0.58-0.66)
    is the crowd's past flow, not its information.
  - A display feature is a reference-feed feature, so it is outside the examiner's activity baseline.
- **Test.**
  1. Display state at time t, point in time, using publishes with P <= t - 0.2 s:
     - D = CL_disp - strike, in $ and in σ√τ;
     - seconds since the last displayed crossing and the number of crossings in the window;
     - the last 1-3 window outcomes (known at the window start);
     - seconds left.
  2. Pre-register an E3 screen (`indicators.crossings` on D; streak states as gates) against the outcome bought by the
     non-HFT takers of the BTC 5m tape (signed) and against their arrival rate. BUILD 10-09..22 (Binance stand-in for
     CL where the endpoint series is missing), BH q <= 0.10, confirmation on VALIDATE (aggregate).
  3. Freeze a small logistic for the crowd's demand side on BUILD. Score on STUDY / VALIDATE:
     - (a) the crowd's side against "the favourite at the last clean print";
     - (b) the cluster's per-fill side as the complement of the predicted demand, in the non-decided band, against R8c
       and the cheaper token, both halves and per wallet;
     - (c) the crossing terms as added presence features (gain over the activity baseline, block bootstrap).
- **Data.** The data-api BTC 5m tapes with taker identities (cached), the RE's taker classes, the lot's endpoint
  Chainlink seconds (X90/X102 chunks), and `dy_rtds` for the live blocks. Nothing new to fetch.
- **Signature if true.**
  - Crossing events shift the crowd's buy side within 0-10 s, with q <= 0.10 on BUILD, confirmed on VALIDATE.
  - The cluster's per-fill side gains >= +0.02 over R8c on VALIDATE in the non-decided band, in both halves.
  - The presence gain is >= +0.01 with a bootstrap lower bound above 0.
  - Report it as a counterparty or market-structure description (the brief allows a baseline-type rule that says so),
    not as an engine input.
  - If nothing passes, the side residual's counterparty share is measured as the crowd being unpredictable from its
    display, and the quiet-cell presence bound stands.

### I17-3. Intraday information shocks against the module switches and the instance mode (strong form of E5 / T14, which was daily with |rho| < 0.29 undetectable; selection component)

- **Hypothesis.**
  - The operator's switches react to information shocks at the 15-minute to 1-hour scale:
    - BTC 5m/15m off-runs;
    - the 11-01 bosona-only mode;
    - the October open-window module.
  - Candidate shocks:
    - news bursts (GDELT);
    - scheduled macro events (FOMC 10-28 at 18:00 UTC, CPI, payrolls);
    - realised-vol jumps and futures dislocations.
  - Alternatively, the switches are a human weekly schedule (Fri-Sun 16:35-18:30 ET) that no shock explains.
- **Why it fits.**
  - Selection is the weakest component (0.45, "operator-switched").
  - The daily test had about 80 observations.
  - The off-runs that break the weekly schedule (10-29, 10-31 16:53) and the 11-01 split have never been looked up in
    news or vol at their own hour.
  - C4 shows a professional, custodial operator. Such operators switch on risk events.
- **Test.**
  1. Units: 15-min slots 08-01..10-22 (development, about 7,900).
     - Dependent variables: BTC 5m module-on (>= 1 cluster BUY fill) and the fill count.
     - Model: a conditional logit with hour-of-week fixed effects.
  2. Regressors, lagged one slot:
     - GDELT DOC 2.0 `timelinevolraw` for "bitcoin" and for "crypto OR fed OR cpi". Fetch in 7-day chunks, which
       should keep 15-min resolution (verify the resolution returned; one request per 5 s; 2 queries x 12 chunks);
     - Binance 1-s realised vol over the slot and its z against the hour-of-week norm;
     - |futures - spot| basis jumps;
     - scheduled-event dummies (±1 h).
  3. Event version: every off-run >= 60 min and every slot where the instance mode is split (X177). Count GDELT bursts
     (z >= 3) and vol jumps in the hour before, against 20 placebo hour-of-week matched starts.
  4. Live: record Google News RSS / CoinDesk RSS headlines with timestamps through the 11-02 / 11-03 development blocks
     (the brief's E5 live clause), and look up the first post-DST switches.
- **Data.** GDELT (keyless; about 24 requests), Binance archives (cached), the RE's whole-history activity, the FOMC /
  BLS calendars.
- **Signature if true.**
  - A shock regressor with Wald p < 0.01 and a marginal effect >= 0.10 on P(on), stable in both halves of the period.
  - Or >= 50% of the off-run starts preceded by a burst, against <= 15% of placebo starts.
  - Otherwise selection is recorded as a schedule plus own-state trips, with the test's power stated: with 7-25 events,
    only a burst share above about 0.45 is detectable.

### I17-4. What the open module reads at 09:30 New York: the equity session, the opening print, or BTC's move (information half of the NYSE question; complements the mechanics panel's live P4; time-critical data)

- **Hypothesis.**
  - The October open-window behaviour (fresh main-ladder bids on the token the opening move made cheap) reads US equity
    information: the session state, or the equities' opening print and its relation to BTC's move.
  - It is not a 13:30 UTC timer and not a BTC-only fade.
  - It fades BTC's opening move when the equity open does not confirm it.
- **Why it fits.**
  - On NYSE holidays the window was ordinary (iteration 17). So equities, not the UTC clock, make the window busy.
  - The behaviour switched on in October 1-8, before PolyBolt's 10-21 "equity status" field. So if it reads a session
    flag, the flag is its own calendar.
  - It earns: won 0.40 at mean price 0.23 on BUILD.
  - Whether it survives the 11-02 DST change decides R8c's value in the next exam.
- **Test.**
  1. Fetch 1-minute bars of IBIT, QQQ, SPY, COIN and MSTR for 10-02..10-30 now. The Yahoo chart API (`interval=1m`, 7-day
     ranges) serves 1-minute history for only about the last 30 days (verify on the first request). The early-October
     open windows (cheap share 0.997, the configuration's first days) therefore drop out from about 11-02.
  2. For every weekday open window of 10-01..10-30 (about 21), compute BTC's move from 13:30:00 to the first cluster fill
     (Binance 1-s) and the equities' first-minute return. Test whether the cheap-token share, the fill count and the
     return depend on:
     - agreement between the equity and BTC moves;
     - the size of the BTC move.

     A fixed fade predicts no dependence. An information rule predicts favourites (or no module) when equities confirm
     BTC.
  3. Live, on 11-02 and 11-04 12-18 (development; the NYSE open is at 14:30 UTC, and 13:30 UTC is the placebo): the same
     two contrasts on the first fresh main-ladder posts.
- **Data.** Yahoo chart JSON (keyless; about 20 requests), Binance 1-s (cached), the lot's typed fills, `dx_clob` and the
  shared recorder.
- **Signature if true.**
  - The cheap share differs by >= 0.3 between windows where equities confirm and where they diverge (Fisher p < 0.05 at
    n about 21, so only a large effect is detectable).
  - The module fires at 14:30 UTC on 11-02 and 11-04 and not at 13:30.
  - Then R8c is restated on the exchange clock with the equity condition.
  - If the share is flat across the contrasts, R8c is a calendar fade and stays as frozen.

### I17-5. The Perps index at its native 200 ms as a public early proxy of the settlement report: does any public series see the innovation before the RTDS publish? (strong form of X214, whose 1-Hz REST poll cannot resolve the 0.8-1.1 s gap)

- **Hypothesis.**
  - The Perps index is computed every 200 ms from Pyth, Chainlink Data Streams and Hyperliquid. Through its Data
    Streams constituent it may move with the report's innovation u_i before RTDS publishes it.
  - If it does, a public early proxy of the settlement report exists:
    - the cluster's absence of a pre-publish reaction (C2) then shows it does not use one;
    - takers who use one would be the informed flow against the cluster at publish times.
- **Why it fits.**
  - C1: u_i is about half of each report, and no exchange venue anticipates it.
  - C2: the cluster acts on u_i only after P_i.
  - X214's recorder polls REST at about 1 Hz, which cannot resolve stamp + 0.3 s to P_i ≈ stamp + 1.08 s.
- **Test.**
  1. Record `wss://ws.perpetuals.polymarket.com/v1/ws` `tickers` for instruments 6/7/8 (index, mark, server ms) with
     `live.py`'s `Writer`:
     - verify the endpoint first (named by the iteration-16 panel);
     - hard stop 11-03 00:00;
     - under 60 MB on disk;
     - entered in `live_lab`.
  2. On 11-01 18-24 and 11-02 00-06 / 12-18: regress u_i (from the futures-only model of I17-1) on the index change over
     (stamp, stamp + 600 ms], against the futures over the same span.
  3. Score the takers matched in (P_i - 400, P_i + 150] ms against the cluster, by whether the index anticipated u_i.
     Calldata gives the taker sign ms.
- **Data.** The new recording, `dy_rtds`, `dx_bnf`, `dx_clob`, and calldata samples (about 1,000 transactions).
- **Signature if true.**
  - The index change explains >= 0.2 of u_i's variance beyond the futures, before P_i.
  - Takers in that window fill the cluster on the side u_i made stale at >= 1.5x the base rate.
  - Otherwise record the Perps index as `no_effect` for the report, which closes the last public early-proxy route
    for H2.

## Ledger entries this panel's checks support (for the RE to record)

- **X59, the RTDS Binance relay:** `tried`, no information beyond Binance spot. It is the last spot trade at each whole
  second (99.2% exact, 1,800 stamps of 11-01 08:00-08:30) and is published at +128 ms.
- **X118 and iteration-9 F2:**
  - all three 10-12 sweeps forward to 0x1891b583a86daf0f149ba9712a61506138526c6f within 16-28 blocks;
  - that address is an exchange-like consolidation wallet (C4);
  - the on-chain hedge or treasury route is closed: custodial, not observable. The full sweep EOA addresses are in C4.
- **dimensions:**
  - `chainlink_data_streams_low_latency`: no pre-publish reaction on 11-01 (0.505, n 537), which with iteration 13
    covers both regimes;
  - `other_spot_venues`: `no_effect` beyond the futures on the post side (moving posts 0.829 futures vs 0.814 all
    venues);
  - `pm_legacy_rtds`: `drives` (the report innovation, 0.71 in (0, 150] ms, pending I17-1's confirmation).
- **E4:** the first discrepancy indicator, the report minus the venue nowcast. On the clean block the venues explain
  R² 0.52 of the 1-s report change (futures 0.46).
