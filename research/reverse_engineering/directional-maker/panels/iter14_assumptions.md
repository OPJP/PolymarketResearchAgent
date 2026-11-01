# Panel after iteration 14: assumption breaker

Lens: what the investigation takes for granted that may be false. After iteration 14 the working assumptions are:
- the cluster's trades outside BTC 5m/15m (the "idle" weekend blocks, and 5-15% of trades in every block) come from the
  same engine as the BTC ladders, so R9 can transfer R3 (presence), R7 (price) and R8 (side, with "the cheaper token"
  where no Chainlink series exists) to every family;
- the exam can be prepared on the weekday VALIDATE (10-27..30), with pooled numbers;
- the strict-replay outcome ceiling (0.47-0.53 with an oracle side) and the +0.03 presence gain are properties of the
  strategy, not of the weekday BTC 5m configuration they were measured on.

Written 2026-11-01, 06:50-08:00 UTC.

**Data used.** Development data only. `tools/sealed.py directional-maker`: released h1 and h2; development
[10-23, 10-31 06:00), [10-31 12:00, 18:00) and [11-01 06:00, now); sealed [10-31 06:00, 12:00) and [10-31 18:00,
11-01 06:00).
- Activity of the three wallets: `.cache/re/directional-maker/activity_*.parquet` (10-08..22) and `exam/activity_*.parquet`
  (10-22..30). I used only rows before 10-27 00:00 (BUILD plus STUDY). STUDY days (10-24, 10-25) were used case by case,
  as the brief allows. Nothing from VALIDATE 10-27..30.
- data-api taker tapes (`PolymarketData.market_trades`, taker_only) for 32 markets of the two idle STUDY blocks, through
  the shared HTTP cache.
- Binance spot 1-s klines:
  - REST, for the ETH/SOL/XRP 5m/15m windows of the idle STUDY blocks;
  - daily archives (SHA-256 checked) for XRPUSDT, ETHUSDT and SOLUSDT on 10-10, 10-14, 10-18 and 10-22, reduced to
    parquet in the scratchpad. Nothing was written to the shared cache.
- `.cache/re/directional-maker/cluster_btc5m_fills.parquet`, `windows_5m.parquet` and `spot_btc_1s.parquet` (BUILD and
  the pre-H VALIDATE).
- Nothing from `.cache/live/sealed/` or from sealed units.

**Scripts.** All in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p14a\`.
Run them from the repo root with `.venv/Scripts/python.exe -I`:
- `wk.py`, `tte.py`, `shared.py`: composition of the idle blocks, timing and synchronized fills;
- `role.py`, `anchor.py`: maker or taker role, and R7 on the idle maker fills;
- `xrpfair.py`, `getkl.py`, `famopen.py`: the opening side against a Binance digital fair;
- `fam5.py`, `btcopen.py`, `pnl_open.py`: the same measurements per family, and on BTC 5m.

These are small and crude:
- the fair is Binance spot, not Chainlink;
- the strike is a TWAP-60 of Binance closes;
- sigma is the 300-s realised volatility;
- the activity rows include the ~14% taker fills.

Each needs the RE's proper version before anyone relies on it.

## Quick checks (development data)

**Q1. What the cluster does in the idle weekend blocks (STUDY, Sat 10-24 06-12 and Sun 10-25 00-06).**
- Volume: 371 and 394 BUY trades ($6.9k and $6.4k) over 175 markets and about 10 families.
- Wallets: all three take part almost equally (136 / 127 / 108 and 143 / 133 / 118 trades).
- Role: 86% are maker fills (305 of 356 on 32 sampled markets; XRP 5m 41 of 41).
- Synchronized fills:
  - 22% of the cluster's transactions fill two or three cluster wallets at once (2.5% on BTC 5m in BUILD);
  - in 128 of the 129 shared transactions, all the wallets bought the same outcome, at the same price or one tick
    apart, usually with the same size (for example 38 / 38 / 38 at 0.52, 10 / 10 at 0.76, 50 / 50 / 50 at 0.97).

  So each decision is posted three times, once in each account.
- Sizes are constant within a family and differ between families:

  | family | size (shares) |
  | --- | --- |
  | XRP 5m | 10 |
  | SOL 5m | 12 |
  | ETH 5m | 19 |
  | BTC, ETH and BNB hourly | 38 |
  | daily | 50 |

  None of them is a BTC schedule size.
- Shares of dollars:
  - BTC 4h 28-46%;
  - hourly (BTC/ETH/BNB) about 22-27%;
  - daily (BTC/ETH/SOL) about 7-20%;
  - ETH 15m 8-12%;
  - the rest in the 5m families of XRP, SOL, ETH, BNB and DOGE.

  The 4h, hourly and daily windows together hold about 72-76% of the idle dollars.

**Q2. On the 5m families, the trading happens at the window open, and it has done so in every development week.**
- In the idle blocks, 37% of the 5m-family fills fall in the first 10 s of the window and 50% in the first 20 s.
- In BUILD and STUDY (every block, 10-08..26), the share of fills in the first 20 s is:
  - XRP 5m 41%, SOL 5m 26%, ETH 5m 20%, ETH 15m 20%, BNB 5m 32%, DOGE 5m 28%;
  - BTC 5m 10%, BTC 15m 4%.
- The non-BTC 5m share in the first 20 s is between 0.14 and 0.42 on every single day. This is an always-on component,
  not a weekend artefact.

**Q3. The side of the opening fills is a public function of the strike gap, and the market favourite does much worse.**
- Rule: for fills in the first 20 s, take the outcome that a Binance digital fair prices above 0.5. The fair is
  Phi(ln(S / K) / (sigma_300 * sqrt(tau))), with K the TWAP-60 of the minute before the open.
- On four BUILD days (10-10, 10-14, 10-18, 10-22; ETH/SOL/XRP 5m and 15m; 878 opening fills):

  | | share of opening fills |
  | --- | --- |
  | on the fair favourite | **0.842** |
  | on the market favourite (price > 0.5) | 0.671 |

  - Per day the fair favourite scores 0.84 / 0.86 / 0.86 / 0.76, and the market favourite 0.79 / 0.69 / 0.67 / 0.53.
  - By family: ETH 5m 0.91, XRP 5m 0.90, ETH 15m 0.74, SOL 5m 0.70.
  - Fill price against the fair: corr 0.89.
- On the idle STUDY blocks: 0.87 (n 142) against 0.67.
- After the first 20 s the fair favourite falls to 0.43-0.68, near the market favourite.
- BTC 5m does not behave like this. For its fills in the first 20 s the fair favourite scores 0.41-0.76, with the sign
  changing between BUILD and the pre-H VALIDATE, and its PnL is not concentrated at the open.

  So the opening rule belongs to the non-BTC families.

**Q4. R7 does not carry over to the idle families.**
- Test: R7 (the last clean print - 0.01, block clock) on 257 idle maker fills.
- Within 0.01: 0.44 pooled, with XRP 5m at 0.14, ETH 5m/15m at 0.51 and the BTC/ETH hourly and daily markets at
  0.58-0.61.
- The last clean print before a fill is a median 2-108 s old in these markets. That is stale compared with the 0.1-1 s
  touch refresh that R7 was built on.

**Q5. R9's planned fallback side points the wrong way.**
- In the idle blocks the cluster buys the outcome priced above 0.5 in 62-79% of fills, depending on the window length:
  15m 0.62, 5m 0.73, 4h 0.74, daily 0.78, hourly 0.79.
- "The cheaper token" (R9's fallback where no Chainlink series is recorded) therefore scores about 0.21-0.38 on those
  fills.
- The daily fills average a price of 0.92, with 69% at 0.90 or above, a median of about 9 h before the end. The hourly
  and daily families settle on Binance (X84), not on Chainlink.

**Q6. No switch-off on Sunday 10-25 evening.** BTC 5m traded through Sunday 10-25 20:00-03:00 UTC (930 trades). So the
"scheduled weekend-evening switch-off" (X152) is not a regular calendar event.

## Critique

1. **R9 assumes that one engine trades every family. The idle families look like a different module.**
   - The non-BTC trading that carries the idle blocks, and probably the second half of the lot, differs from the BTC
     ladders on every component:
     - its timing is concentrated at the open (Q2);
     - its side is the strike-gap fair favourite, not the posture over the mid (Q3);
     - its price is not "last print - 0.01" (Q4);
     - its sizes are fixed per family (Q1);
     - it posts the same order in all three wallets at once (Q1).
   - Each of the three planned transfers (R3 presence, R7 price, and the R8 side with a cheaper-token fallback) is
     likely to fail on these fills, the fallback by construction (Q5).
   - The family-general universe solves scope only if what it scores in those families is decoded.
2. **The lot is heterogeneous, and the examiner's replication split will see it.**
   - The sealed blocks are 10-31 06-12, 10-31 18-24 and 11-01 00-06 (11-01 12-18 is added if the exam runs after it
     ends). What the analogs and the development blocks around them suggest:
     - the first block is probably active: 10-31 00-06 had BTC 5m+15m at 0.91;
     - the second block lost BTC 5m at 16:53:54; BTC 15m was still on at 17:29-18:00;
     - the third block may be idle (its analogs score 0.00 / 0.43 / 0.83 on 10-25 / 10-18 / 10-11), and it has the
       05:00-06:59 listing gap and the US DST change.
   - The examiner splits the lot into an earlier and a later half from listing metadata. Every threshold must then
     hold on each half within 0.03, and for each wallet.
   - So the rule must meet the bar on the active configuration and on the idle configuration separately.
   - Every number in `target_metrics` is pooled over a weekday VALIDATE that resembles neither half.
3. **The outcome ceiling and the presence gap are measured on one configuration.**
   - The "0.47-0.53 oracle ceiling" and "+0.03 gain on every unit" are BTC 5m weekday statements.
   - The idle configuration has 2-3 fills per market, 83% of markets one-sided (at least 70% of shares on one outcome),
     and a side set at the open. Its per-market PnL is close to sign(side) × outcome, which a decoded side can track.
   - The weekend BTC 15m block (10-31 00-06) already showed a PnL proxy of 0.73 / 0.68 and a side of 0.914.
   - Nobody has measured the strict replay on the idle or weekend configuration.
4. **The settlement source is assumed to be Chainlink.**
   - R9 plans "each symbol's Chainlink where recorded".
   - The hourly and daily families settle on Binance 1-minute candles (about 30-47% of the idle dollars). The 4h
     settlement source has not been checked; with the 4h windows the share is about 72-76%.
   - A Chainlink posture is the wrong reference for them, and the cheaper-token fallback is the wrong default.
5. **Clock conventions for the lot's last block (minor; part of X99).**
   - 11-01 06:00 UTC is the US fall-back, and the slug hour "1am ET" occurs twice.
   - Any window time parsed from hourly or daily slugs with a fixed -4 h offset is one hour off after 06:00 UTC.
   - Fix: take start and end from Gamma's listed times, not from slugs.

## Proposals (ranked by the chance they close the gap)

### P1. Decode the non-BTC module on its own terms: an opening strike-gap quoter with fixed per-family sizes (strong form of X161, X83, X95 and X131; replaces R9's planned transfers)

- **Hypothesis.** On every crypto Up/Down family other than BTC 5m/15m, the operator runs a separate, always-on module.
  - **Timing.** At each window open (mainly the first 20 s), it bids, in all three wallets, for the outcome that its
    reference fair favours given the strike.
    - For TWAP-60 windows the strike is the TWAP of the minute before the open, so the fair is already away from 0.5
      at the open.
    - It stays on through the window with smaller activity.
  - **Size.** A per-family constant (10 / 12 / 19 / 38 / 50).
  - **Price.** Tied to the fair (fair minus a margin), not to the last trade.
  - **Counterparty.** It is paid by takers who trade the open as if it were 50/50.
  - **Weekend idle blocks.** This module runs alone. So it is the object the second half of the lot will score.
- **Why it fits.** Q1-Q5:
  - the opening fill share is 0.14-0.42 on every development day;
  - on 878 BUILD opening fills the fair favourite scores 0.842 against 0.671 for the market favourite, consistent over
    four days of three weeks;
  - the prices track the fair (corr 0.89);
  - triplets of the same price and size;
  - R7 is at 0.44 and the anchor ages are 2-108 s.
- **Test.** Pre-register, then fit on BUILD and score on STUDY case by case, VALIDATE as aggregates, and 10-31 00-06 /
  12-18 plus 11-01 06-12 (development).
  1. **Unit.** Maker BUY fills of the cluster on every family except BTC 5m/15m, from activity joined to the taker tape
     for role (on-chain logs where available). Separate the opening fills (t - start < T_open, with T_open chosen on
     BUILD from {10, 20, 30} s) from the later ones.
  2. **Reference per family, by settlement source** (Gamma `resolutionSource`):
     - Chainlink TWAP-60 for the 5m/15m windows: the dv_rtds / rtds recordings where they exist; historically
       Polymarket's crypto-price endpoint for a sample, else Binance spot as a stand-in with the basis reported;
     - the Binance 1-minute candle for hourly windows (strike = the hour's open) and daily windows (strike = the
       previous noon ET close);
     - check the 4h windows' source first.
  3. **Side rule (frozen on BUILD).**
     - Opening fills: the fair favourite.
     - Later fills: the pre-registered better of the posture (fair over mid) and the market favourite.
     - Baselines: market favourite, cheaper token, and own inventory (reported).
     - Score per fill, per one-sided market (the examiner's round-1 style unit) and per wallet.
  4. **Price.** "Fair minus δ_family" (δ fitted on BUILD), rounded to the tick, against R7 on the block and in-block
     clocks and against the trivial anchors.
  5. **Presence.** The R3 class per family, with |z_open|, the open bucket and the strike gap. Report it against an
     activity-only model of the same class, pooled over all bins of all non-BTC families and per family.
  6. **Size and structure.** Per-family constants, and the triplet share (a description, no metric).
- **Data.** Activity (on disk); data-api taker tapes for the non-BTC markets of BUILD/STUDY (cached fetch, a few
  thousand markets; prioritise the 5m families and the 4h/hourly/daily markets that carry the dollars); Binance 1-s
  archives for XRP, SOL, ETH, BNB and DOGE (about 1.5 MB per day each; reduce at once); dv_rtds for the live blocks.
- **Signature if true.**
  - The opening-fill side is at least 0.85 in every BUILD week and on STUDY, against a market favourite of 0.70 or less.
  - The combined side is at least 0.80 per fill on the idle analogs.
  - The fair-anchored price is within a tick on at least 0.70 of fills where R7 is 0.50 or less.
  - On the idle families, presence gains at least 0.05 over the activity model of the same class.
  - Then R9 = R8 on BTC 5m/15m plus this module elsewhere.
- **If false.**
  - The opening side drops below 0.75 at scale, or flips between weeks as BTC 5m's did (Q3). Then the non-BTC fills are
    taker-chosen like BTC 5m's, and the honest R9 states a low side on those families.
  - That is still better than a transferred cheaper-token rule that scores about 0.3.

### P2. Emulate the examiner's split on weekend analog lots and choose R9 on a weekend VALIDATE (new; the replication rule against a heterogeneous lot)

- **Hypothesis.** On a weekend lot the examiner's earlier and later halves are different configurations: active
  Saturday morning against an idle Saturday night. R8, and any rule tuned on the weekday VALIDATE, will differ by more
  than 0.03 between the halves on several criteria. The rule can pass replication only if it is selected and reported
  per configuration.
- **Why it fits.**
  - The calendar of the sealed blocks; T5's analogs (U1 0.00-0.91 across the three block types).
  - Critique items 2 and 3.
  - On the weekend BTC 15m block, presence and side are near the bar (0.853 / 0.914), while BTC 5m's gain was negative
    there (-0.016).
- **Test.**
  1. Build three development "mock lots" with the sealed lot's block types:
     - Sat 10-24 06-12 + Sat 10-24 18-24 + Sun 10-25 00-06 (STUDY, case by case);
     - the same blocks of 10-17/18 and of 10-10/11 (BUILD).
  2. Split each mock lot into halves by scheduled window start, before reading fills, as the examiner will.
  3. Run R8's `evaluate()` and the candidate R9 on each half and each wallet. Report:
     - scope (fills and |PnL|);
     - presence with its gain and the gain's 2-h block bootstrap;
     - the side per fill and per one-sided market;
     - price on the block and in-block clocks;
     - the strict-replay per-market PnL correlation.
  4. Pre-register a weekend VALIDATE for choosing between R9 variants: 10-31 00-06 and 12-18, and 11-01 06-12 when it
     ends. Use the weekday VALIDATE only as a secondary report.
- **Data.** On disk and in the cache, plus the tapes P1 fetches.
- **Signature if the assumption is false (the halves differ).**
  - R8's halves differ by more than 0.03 on at least two criteria in at least two mock lots.
  - R8's scope fails in the idle half.
  - Then R9 must be judged half by half, and the remaining minutes go to the weaker half (very likely the idle module of
    P1).
  - If the strict replay on the idle half reaches 0.5 per market, the outcome criterion is not out of reach on this lot.
    The "0.47-0.53 ceiling" should then be restated as a weekday BTC 5m property.
- **If true (the halves agree).** The weekday-tuned R8 plus scope coverage is the right object. The work stays on the BTC
  side gap.

### P3. Use the settlement source per family, and drop the cheaper-token default (strong form of X84 and part of X161)

- **Hypothesis.** For every family, the side of the non-BTC module is the favourite under that family's settlement
  reference:
  - the Binance 1-minute candle for hourly and daily windows;
  - Chainlink TWAP-60 for 5m and 15m windows.

  The hourly, daily and 4h markets carry about 72-76% of the idle dollars, and much of the idle |PnL| because their
  fills are larger. They decide both the |PnL| scope and the per-market outcome correlation of the idle half.
- **Why it fits.**
  - The idle fills buy the outcome priced above 0.5 in 0.74-0.79 of the 4h, hourly and daily fills.
  - The daily fills buy 0.92 favourites about 9 h before the end.
  - X84 established that hourly and daily windows settle on Binance.
  - R7 on these markets is 0.58-0.61 with anchors 8-10 s old.
- **Test.**
  1. Sample: every BUILD/STUDY cluster fill on the hourly, daily and 4h families.
  2. Strikes from the Binance 1-m archive: the open of the hour for hourly windows, the previous noon ET close for daily
     windows; the 4h strike from its listed resolution source.
  3. Fair with 1-h or 1-d realised volatility and the time left.
  4. Score:
     - the side: fair favourite against market favourite and cheaper token, per fill and per market;
     - the price: fair minus δ against R7;
     - the per-market PnL correlation of a strict replay, "buy s_fav at fair - δ, family size".
- **Data.** Activity; the Binance 1m klines archive (small); the tapes of these markets (cached fetch); Gamma listings
  for the resolution source.
- **Signature if true.**
  - The fair favourite is at least 0.85 per market on hourly/daily/4h, and the cheaper token at most 0.25.
  - The replay correlation per market is at least 0.5 on these families.
  - Then the idle half's outcome criterion rests on them.
- **If false.** The long-horizon buys do not follow the settlement-source favourite (for example, they are resting bids
  at fixed prices that takers hit). Then decode them as a fixed-price ladder (`fixed_price_ladder_backtest`) per family.

### P4. Selection at the print level on the opening unit of the non-BTC families (new unit for the counted selection route)

- **Hypothesis.** In the first 20 s of a non-BTC window, a taker print that sells the fair favourite (or buys the fair
  underdog by mint) below the fair is very likely the cluster's fill. The activity baseline sees the time and the price
  but not the strike gap, so the gain over co-occurrence should be large on this unit. The later prints follow the
  market favourite, so they carry less.
- **Why it fits.**
  - Q3: the fair favourite scores 0.84 against 0.67, and corr(price, fair) is 0.89 at the open.
  - About 20-42% of non-BTC fills fall in the first 20 s.
  - On BTC 5m, iteration 14 found that print selection fails because the cluster's price is everyone's touch (X150,
    0.558). In these thinner books at the open, the cluster's fair-anchored bid is the distinctive part.
- **Test.**
  1. Unit: all clean prints of every non-BTC 5m/15m window of BUILD (fit) and STUDY (test case by case; VALIDATE as an
     aggregate).
  2. Score frozen on BUILD: 1[t < T_open] × 1[the maker side of the print is the fair favourite] × (fair - price), plus
     the family size (prints at or below the family constant).
  3. Run `match_test` with within-window strata and a rotation null of 2,000 draws. Report recall and lift at the BUILD
     threshold, against an activity-only LightGBM with the same budget.
  4. Report the opening unit and all prints separately. Only the all-prints number can count, because a counted metric
     must not be narrowed to the opening subset.
- **Data.** The tapes of P1 and the per-symbol 1-s references.
- **Signature if true.**
  - The opening prints reach a within-window AUC of at least 0.85 with a gain of at least 0.10.
  - All prints of the non-BTC universe reach AUC 0.80 or more, with recall of at least 50% at lift 3 or more, and a gain
    of at least 0.05 with a bootstrap lower bound above 0.
  - Then the selection condition can be met on the idle half without the 10-s fill-presence unit.
- **If false.** All-prints selection stays at 0.75 or below while the opening unit is high. The later non-BTC fills are
  then as taker-bound as BTC 5m's, and that is the quantitative account of the idle half's presence gap.

## Notes for the RE

- Run P1 steps 1-3 and P3 first. They need only activity, tapes and small Binance archives, and they decide whether R9
  is a transfer (likely to fail on the idle half) or a second decoded module.
- Do not freeze R9 with the cheaper-token fallback. On idle-block fills it is the anti-rule (Q5).
- Use Gamma's listed start and end for the hourly and daily windows (US DST at 11-01 06:00 UTC; "1am ET" occurs twice).
- My opening-side numbers use a Binance-spot stand-in fair, and the activity rows still include the ~14% taker fills.
  Redo them maker-only with the settlement reference before adopting anything.
- Ruled out quickly, so nobody re-proposes them:
  - The opening effect does not hold on BTC 5m: the fair favourite at the open scores 0.41-0.76 with a sign flip between
    BUILD and the pre-H VALIDATE, and the PnL is not concentrated in the first 20 s.
  - The weekend-evening switch-off is not regular: BTC 5m traded through the Sunday 10-25 evening.
