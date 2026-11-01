# Panel after iteration 4: assumption breaker

Lens: what the investigation takes for granted that may be false (universe, unit, metric, size, what the counter
counts, who sets the switches). Written 2026-10-31 ~14:00 UTC. Data used: development only. That means activity before
H, the released lot's first half (STUDY, 2026-10-23..26) case by case, the 2026-10-31 00:00-06:00 and 12:00-14:00 UTC
development blocks, and a 75-s in-memory look at the public CLOB websocket during the current development block. I did
not touch VALIDATE (10-27..30) fills or anything sealed. Check scripts are in my scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
`deltas.py`, `moves.py`, `rawws.py`); the other checks are short inline reads of `.cache/re/directional-maker/`.

The mechanics panel (`iter4_mechanics.md`) already proposes these, and I do not repeat them: raw book events with a
size fingerprint, back-of-queue level depletion, the salt counter as an order budget, exit by complement-buying, and
"side is the taker's choice". Where my checks bear on them I say so.

## Critique: assumptions the investigation is making

1. **"The strategy is BTC 5m."** The target needs a universe with at least 80% of the wallets' fills and at least 80%
   of their absolute PnL. R3 covers 55% of fills, and `coverage_abs_pnl` has never been computed.
   - Pre-H activity, TRADE rows: BTC 5m is 49.7% of fills and 52.2% of dollars; BTC 15m 24.4% / 30.8%. Hourly and
     daily Up/Down markets (`bitcoin-up-or-down-october-8-2026-9pm-et`, `...-on-october-9-2026`) are 9.9% / 7.8%,
     ETH 5m 7.4% / 3.9%, BTC 4h 2.1% / 3.4%.
   - Cash-flow PnL 2026-10-09..H (REDEEM + MERGE + SELL - BUY; positions open at the boundaries ignored): BTC 5m
     +$29.8k, **BTC 15m -$12.2k**, hourly/daily +$9.5k, BTC 4h +$5.5k, ETH 5m +$3.3k. BTC 5m is about 46% of absolute
     PnL across families.
   - On 2026-10-31 00-06 UTC, BTC 5m is 68% of fills and BTC 15m 23%.
   - One salt counter signs every market, so the decision process is one cross-market engine. A BTC 5m-only rule fails
     the scope condition whatever its AUC.
   - The second-biggest market loses money, which the "Why it works" section does not explain.
2. **"Rule PnL per share is comparable to the wallet's dollar PnL."** In `final_rule.py`,
   `rule_pnl = p * (won_s - price)` carries no size, while the wallets' windows differ 8x in order size (62 vs 500).
   Ceiling check on STUDY (583 windows, the wallets' own maker fills): a perfect replica of the wallets' fills at one
   share each correlates with their dollar PnL at only **0.544 Pearson / 0.776 Spearman**. Dividing the dollar PnL by
   the window's order-size class gives 0.650 / 0.932. So the outcome metric (at least 0.5 on both) is capped near the
   bar by construction until the rule carries the size. The examiner's executable backtest had to invent a size (20
   shares).
3. **"Size follows a clock schedule"** (VALIDATE-only) is already contradicted by development data.
   - On 2026-10-31 00:00-06:00 UTC (a Friday night in the US and a Saturday in UTC, so "night/weekend" under the
     claimed schedule), BTC 5m has 38 fills of exactly 500 shares, from all three wallets in every hour 00-05, plus 21
     fills of 100 (the one-fifth level).
   - 62-share fills (86) appear only from 00:01 to 00:54 and from 05:54 on.
   - On Saturday 12:00-13:13 UTC there are 8 fills of exactly 500.
   - So the size is a runtime parameter that changes outside the claimed clock. The mechanics panel's fingerprint also
     assumes the clock schedule and must be keyed to the actual size class (from calldata), not to the hour.
4. **"Signed orders are BTC 5m requotes."** The 10-23 orders/s per wallet are counter increments, not observed
   resting orders.
   - Raw CLOB market websocket, 75 s, current BTC 5m market (~13:55 UTC): 2,043 `price_change` messages. Each carries
     exactly one order event (two mirrored changes), so a level delta equals one order's size; the raw stream does
     expose single orders.
   - In those 75 s, events of exactly 500 shares number 7 and of 100 shares 42 (0.65 events/s for both outcomes,
     adds and cancels together). The 5-share events alone number 1,293.
   - That is at most about 0.3 re-quotes a second for all three wallets in that size class. The mechanics panel's own
     estimate is that BTC 5m takes 1.5-3 signed orders/s.
   - In the 200-ms snapshots (10-31 12:00-13:40), a +500 add at the fill level within the 30 s before a fill is found
     for 28 of 123 cluster BTC 5m fills (22.8%) vs 423 of 6,000 other trades (7.1%). So its 500-share orders are in
     the book, but far less often than the signing rate implies.
   - Either most signatures never rest (post-only rejects, unposted or other-market orders) or today's sizes are
     different. The requote-engine story (E1) rests on this unverified equivalence.
5. **"Book features will close the presence gap."** Every feature built from public market state also feeds the
   examiner's market-activity baseline. That includes books, maker rows and depth, provided they carry no
   cluster-specific quote. The required +0.05 gain can only come from what the activity model cannot compute: the
   cluster's own quote function q(fair, book), compared with the competitors' levels. The book paradigm has to be
   framed as "is q above the competing best bid", not "add book features to LightGBM". Otherwise the gain stays
   +0.03, as it has for four iterations.
6. Minor: `code4/b1_age.py` (unreported) is uninformative. 85.4% of orders have lag 0, and 75% of its "> 60 s" ages
   fall on 10-26 19:00-23:00 after the 19:36 ad-hoc restart, which its segmentation misses. Do not use it.
7. Checked and not supported (so not proposed): the cluster copying one competing maker. In the STUDY all-maker
   calldata, the other makers at the cluster's price are 545 distinct wallets, and the top shares (2-4%) equal their
   base shares in all matches. Historical bid/ask-center extraction from adjacent-salt opposite-token pairs is too
   sparse: only 7 pairs with salt gap <= 20 in STUDY.

## Proposals (ranked by the chance they close the gap)

### Q1. One universe for one engine: all crypto Up/Down horizons, plus the taker hedges (new item; scope)

- **Hypothesis.** The decision process is a single engine over BTC/ETH/SOL 5m, 15m, hourly, daily and 4h Up/Down
  markets, with horizon-specific parameters. BTC 5m is half of it. BTC 15m, a net loser before H, is either the same
  quoter with a worse parameterisation or a different component (inventory or hedge leg). Either way it must be inside
  the rule's universe for the scope condition (80% of fills and of absolute PnL), and decoding it changes the "where the
  PnL comes from" story.
- **Why it fits.** Coverage 0.55 and abs-PnL coverage never computed. The family mix and PnL in critique item 1. One
  counter for all markets. 5m and 15m net directions agree in 70% of slots. The mechanics panel's 157 exact-imbalance
  taker buys are also wallet fills outside the maker-only universe.
- **Test.**
  1. On STUDY, case by case, compute `coverage_fills` and `coverage_abs_pnl` by family with settlement (payout per
     token, not cash flow), maker and taker separately.
  2. Run the R3 pipeline unchanged on BTC 15m and on the hourly BTC market: same feature code, time in window
     normalised by horizon, and the strike rule from each market's Gamma `resolutionSource`. Check it: hourly/daily
     markets may settle on a Binance candle rather than Chainlink TWAP-60. Use BUILD then VALIDATE.
  3. Report per-family presence, side, price within a tick, and PnL by component (paired vs directional, maker vs
     taker, by time to expiry).
  4. Then report the pooled metrics over the smallest union that reaches 80% / 80%.
- **Data.** data-api taker tapes and Gamma metadata of the BTC 15m and hourly windows (same adapters), the wallets'
  activity (have), Binance 1-s and futures 1-s (have).
- **Signature if true.** One engine: the price rule (last clean print - 0.01) and the side rule transfer to 15m and
  hourly within a few points, and the pooled universe clears 80% / 80% with presence no worse than BTC 5m. A distinct
  component: BTC 15m has a different price offset or side rule, its losses sit in late or taker fills, and its fills
  follow the 5m fills of the same slot.

### Q2. Size is a runtime parameter, and it belongs in the outcome metric (strong form of C5/H42; new item for the metric)

- **Hypothesis.** The order size class (500/100, 250/50, 62/12) is set by the same runtime controller that enables
  markets. It is not a 12:00-21:00 UTC clock. It drives most of the cross-window variance of dollar PnL, so a rule
  without it cannot reach PnL corr 0.5.
- **Why it fits.** The 10-31 development blocks contradict the clock schedule (critique item 3). The per-share
  ceiling is 0.544 / 0.776, against 0.650 / 0.932 with the size class (critique item 2). The examiner had to pick 20
  shares.
- **Test.**
  1. Decode original sizes from calldata for every cluster fill in the 10-31 development blocks (00-06 and 12-18 UTC)
     and STUDY. Find size-class change points per wallet. Line them up against:
     - the clock;
     - the salt-counter restarts;
     - the BTC 5m on/off switches;
     - Binance vol;
     - which other markets are filled;
     - trailing own PnL and markouts.
  2. Freeze two size predictors on BUILD:
     - public point-in-time: clock, vol, weekday;
     - own-state, reported separately: the size class of the wallet's previous filled order in any market. This is not
       a fill count or a time since the last fill, so the brief allows it as state if it is reported separately.
  3. Recompute R3's per-window PnL correlation with `rule_pnl * size_hat`. Give the executable rule that order size.
- **Data.** publicnode calldata for the development-block txs (the RE's `code4/fetch_calldata.py`), activity (have).
- **Signature if true.** Size changes align with restarts or controller events, not with 12:00/21:00. Pearson PnL corr
  rises from 0.33 toward or above 0.5. Spearman rises less, because the sign of a window's PnL dominates ranks.

### Q3. Signed is not posted: the counter counts attempts, and the quote is a post-only race (new item; tests the basis of E1)

- **Hypothesis.** Most counter increments never become resting BTC 5m orders. They are post-only orders rejected
  because they would cross (the engine tries to post at or near the touch right after a reprice), orders for other
  markets, or signed-but-unsent orders. Its real resting presence is sparse and short. It arrives at the touch just
  after a reprice and is the youngest order at its level. That fits:
  - the mechanics panel's back-of-queue result (last at its price in 56.5% vs a null of 29.3%);
  - the 0.25-1.5 s exposure window;
  - "never at the top where a competing order is < 0.5 s old".

  Presence is then the success of a race, not a standing quote.
- **Why it fits.** The raw-websocket and snapshot counts in critique item 4: about 0.65 events/s of its size class in
  BTC 5m, against 10-23 signed orders/s per wallet. The RE has not shown any resting cluster order outside a fill.
- **Test.**
  1. In one development block with a raw-event recorder running (the mechanics panel's P1), take every cluster fill
     in all crypto markets of that block (activity), its calldata salt and its original size.
  2. Over the block, per wallet, compute signed orders/s (salt envelope) and fingerprinted adds and cancels/s at its
     size class across all recorded crypto markets. The ratio posted/signed is the key number.
  3. Measure the lifetime of its fingerprinted adds (to cancel or fill), the share of adds placed exactly at the
     touch, and their delay after Binance futures moves (ms).
- **Data.** Public CLOB market websocket (raw `price_change`), calldata of the block's cluster txs, Binance futures
  websocket or aggTrades. All in development blocks (2026-11-01 06-12 and 18-24 UTC, 2026-11-02 12-18 UTC are
  development).
- **Signature if true.**
  - posted/signed is far below 1 (say < 0.2);
  - adds sit at the touch and live under about 1-2 s;
  - adds cluster 100-500 ms after futures moves;
  - fills come from adds that were the youngest at their level.

  If instead posted/signed is about 1 at its size class, the counter is a requote counter and the fingerprint can be
  used directly.

### Q4. The cluster's top-of-book state is the complement of the sub-second makers' state, and that is public history (strong form of the "competitor identity" item, which used takers only)

- **Hypothesis.** A small set of sub-second makers owns the freshly repriced levels. The cluster is filled where those
  makers have pulled or have not yet repriced, and its own fair-based quote then stands alone at the best bid. Their
  quoting state is partly visible in historical public data, because a maker's fill reveals its level and its
  timing. So the quote-state gap can be attacked on the whole history, not only on live blocks.
- **Why it fits.** In the pilot book, at levels holding a competing order under 0.5 s old, the cluster is at the top
  in 0.1% of 4,680 events. Where it is filled, the other makers present are older (3.7 vs 0.8 s). Every presence
  feature so far comes from taker prints. Maker identities were never used: `features2.py` and `feat3.py` read taker
  rows only. No single leader maker exists (critique item 7), so the right object is the set of fast makers.
- **Test.**
  1. Fetch maker rows (data-api `/trades`, `taker_only=False`) for BUILD and STUDY BTC 5m windows.
  2. Freeze on BUILD the list of fast makers: sub-second sign-to-match in the calldata samples, or top maker volume.
  3. Per (window, side, bin), build point-in-time features:
     - each fast maker's last fill price on s and on the complement, and its age;
     - fast-maker fills in the last 1, 5 and 30 s;
     - the gap between the cluster's predicted quote (R3 price rule or a futures-fair quote) and the fast makers' last
       level on s.
  4. Compare R3 + these features with an activity baseline that also gets the maker-row features, BUILD then
     VALIDATE.
- **Data.** data-api maker rows (cached adapter), the STUDY all-maker calldata (have), futures 1-s (have).
- **Signature if true.** P(cluster fill | bid hits on s) rises steeply with the fast makers' staleness on s. The
  presence gain over the strengthened baseline comes from the "cluster quote minus fast-maker level" interaction, not
  from the maker features alone, which would raise the baseline equally.

### Q5. On/off and size are set by a risk controller watching maker toxicity, not by a calendar or a person (new item; strong form of the on/off-vs-PnL test)

- **Hypothesis.** A standard market-making kill switch:
  - disable a market, or cut the size class, when the rolling markout of fills turns negative;
  - re-enable after a cool-down, or when market-wide toxicity normalises.

  Markouts, not realized PnL, are the input. That is why the RE's own-PnL test was inconsistent, with one stop after
  -5.8% and one after +6.8%.
- **Why it fits.**
  - The switches happen at unrounded times (20:39, 22:27, 13:33, 15:25 UTC).
  - The old-VALIDATE off runs followed losing evenings.
  - The old-VALIDATE edge decay was adverse selection after fills (N7).
  - Previous on/off correlates (taker mix, spot regime, listing fields, clock) never included markouts.
  - Size and on/off both change outside the clock (critique item 3).
- **Test.**
  1. Build point-in-time markout series:
     - market-wide: all clean-tape maker fills' 5-, 30- and 60-s markouts against the futures TWAP-60 fair, using
       only fills whose horizon ended before t (public, so allowed in no-own-state models);
     - own: the cluster's fills, reported separately.
  2. Run an event study around every on/off and size-class change in BUILD, STUDY and the 10-31 development blocks
     (about 12-15 events).
  3. Fit a hazard model of switch-off and a window-level on/off AUC from markouts, BUILD then VALIDATE.
- **Data.** Clean tapes and futures 1-s (have), calldata sizes from Q2, activity.
- **Signature if true.**
  - switch-offs and size cuts follow markout drops below a stable threshold within 30-60 min;
  - switch-ons follow a fixed cool-down or a recovery;
  - the window on/off AUC from markouts is above 0.7, against 0.47-0.58 for every earlier public correlate.
