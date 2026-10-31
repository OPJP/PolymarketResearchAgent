# btc5m-bot: frozen rule (iteration 5)

Target status on VALIDATE: scope met; presence met in the block-second unit (0.875, +0.055 over a pure market
baseline, CI > 0); side condition not applicable pooled (two-sided in 99.8% of windows); price within a tick met only
where the Polymarket book is recorded (93% live, 53% historically); executable PnL correlation 0.18 (< 0.5) not met.
Target not reached; nothing is exam-verified.

Code: `code/final_rule.py`, `evaluate(start_ts, end_ts, intervals=None) -> dict` (with `intervals`, only windows that start
in one of the `[a, b)` pairs count; live recordings are read through `iter_live(..., allow_sealed=ALLOW_SEALED)` with the
module constant `ALLOW_SEALED = False`). Models are trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC);
VALIDATE = 2026-10-16 .. 2026-10-23 00:00 UTC (2,016 windows, 1.21M cells). Nothing was fitted on VALIDATE or sealed data.

Tags: **exam-verified** (passed a sealed exam: none yet), **VALIDATE-only** (measured on VALIDATE / development data),
**hypothesis** (supported by little data or by argument).

## The decision process, component by component

1. **Order generation (decoded from V2 calldata, B1) - VALIDATE-only, deterministic.** The bot never decides a price when
   it trades. It PRE-SIGNS a ladder of BUY limit orders for each window: for both outcomes, every price on the 1-cent
   grid (filled prices 0.13-0.88 seen), a few copies per level and two sizes per level (e.g. 30 and 100 shares), in a
   burst of ~1 s per wallet (~1.7 ms per price level). It re-signs the ladder three times per window, at
   rel = -89.5 s (before the window opens), +42.0 s and +172.7 s (spacing ~131.5 s), and uses each order 4-136 s after
   signing. One process signs the wallets one after another: XM, then DS (+1.06 s), then GF (+2.17 s), then a fourth
   wallet 0xd84403ef... (+3-4 s). Orders carry salt = round(Math.random() * Date.now()) (TypeScript clob-client),
   signatureType 3, builder = metadata = 0. Check in `evaluate` (`order_generation_b1`): share of a seeded sample of
   the period's filled cluster orders signed inside the three predicted bursts (VALIDATE: 99.9% of 13,443 orders; last
   2 VALIDATE hours 100% of 1,514; chance 5%).
2. **Selection - VALIDATE-only.** Every BTC 5-minute Up/Down window (94-99% of windows traded, all three wallets in the
   same windows); no other market. Inside a window it only trades prices inside the ladder range (~0.12-0.88).
3. **Timing / trigger - VALIDATE-only (live: hypothesis).** The decision is the SUBMISSION of a pre-signed order. It
   fires within ~1-2 s of a short-horizon move of a multi-venue, multi-asset composite (Binance USD-M futures and spot,
   OKX swap and spot, Bybit perp and spot, ETH / SOL / XRP / DOGE perps; ETH leads BTC at 0.5 s); the order matches
   ~2.0 s before its block timestamp (live median 2.0-2.2 s, 5-95% 1.3-3.2 s). Live (10-31 13:00, Saturday): most orders
   come inside bursts of other traders' trades (median 80 ms after another trade on the market) while the bought
   outcome's ask is rising (58.5% vs 22% at random times), often with no BTC/ETH futures TRADE move in the previous 2 s;
   the Chainlink RTDS 1-s price does not predict its side (50-54%). The quiet-order trigger is still open (candidate:
   venue quote changes, now recorded by `code/rec_binance_fut.py`). Given a mid-range price its activity RISES through the window (fill rate per
   cell 0.11 at 0-15 s, 0.32-0.34 at 240-270 s) and stops at ~270-290 s; the apparent taper at 240-270 s is the price
   leaving the ladder range. Presence score on block seconds `model_it5_blk_full` (it4b features, BUILD block seconds);
   on all seconds `p = model_it4b_all_y`; flag `p >= 0.30` (fixed in iteration 1).
4. **Side - VALIDATE-only.** Per second it buys the outcome toward which the composite just moved (side model
   `model_it5_side_book.txt`: it4b features + the lagged segments + Bybit perp top-of-book imbalance). At the window
   level it buys BOTH outcomes in 99.8% of windows (one-sided 0.2% pooled), so there is no window-level side choice.
5. **Price - VALIDATE-only (development live block 10-31 13:00-13:22).** Limit = the best ask of the chosen outcome at
   the decision instant (it submits the ladder order at that price; it never sweeps; an unfilled remainder rests at
   that price and is the bot's only "maker" activity). Rule price: the recorded best ask 50 ms before the recorded match
   of the same transaction (`price.live_book`, `PRE_MATCH_MS`) when the live recorder covers the period; otherwise the
   last implied ask from other traders' prints. Live check (frozen code, 277 taker orders): the fill price equals that
   ask in 78.1% and is within one tick in **93.2%** (DS 95.4%, GF 94.7%, XM 62.5% of few); with a fixed lag (block - 2 s)
   only 56%; at signing time the limit equalled the then-ask in 0.8% (orders are not priced when signed).
6. **Size - VALIDATE-only.** A fixed (small, large) menu per day, the same at every price: 60/100 (10-09..11), 30/50
   (10-15..18, 200 on 10-16), 30/100 (10-19..22 and 10-31). Large-size share is a per-wallet setting (DS 5%, GF 30%,
   XM 32%), weakly higher after large moves.
7. **Exit / inventory - VALIDATE-only.** Holds every position to resolution: no sells, merges, splits or conversions;
   REDEEM once per window; MAKER_REBATE once a day (~$3.1k per week); no liquidity rewards, no holding rewards.

## VALIDATE metrics (2026-10-16..23; target thresholds in brackets)

| metric | VALIDATE | target |
|---|---|---|
| scope: fills / abs PnL in the rule's universe | 100% / 100% (every BTC 5m window) | >= 80% (met) |
| presence AUC over BLOCK seconds (the only seconds that can hold a fill), no own state, `model_it5_blk_full` | **0.8747** (GF 0.875, XM 0.893, DS 0.857; halves 0.875 / 0.873) | >= 0.85 (met) |
| PURE market-activity baseline on the same bins (prints, timing, time in window, price level; no reference feed) | 0.8193 -> gain **+0.055**, 2-h block bootstrap 95% CI [0.052, 0.058], one-sided p < 0.0005; by wallet +0.065 / +0.068 / +0.052; halves +0.055 / +0.055 | gain >= 0.05 with CI > 0 (met on VALIDATE with my baseline) |
| presence over ALL seconds (unit pre-registered in iteration 1) | 0.9132 vs pure 0.8781 (+0.035, CI [0.034, 0.036]); old baseline with Binance FV gaps 0.8889 | |
| decision-aligned presence (label at block s+1, horizon = decision time) | all seconds 0.9070 vs 0.8717; block seconds 0.8628 vs 0.8062 | |
| selection (size classes + cell score), all 2.74M in-window taker prints | AUC 0.869, recall 68.6% at lift 4.63 | AUC >= 0.80, recall >= 50% at lift >= 3 (met) |
| selection pure baseline | 0.846 (gain +0.023) | gain >= 0.05 (not met) |
| side, one-sided seconds (n = 90,170) | 76.7% (taker 79.4%); market-only 63.2%; favourite 45.9% | >= 80% where it applies; window-level one-sided share 0.2%, so the condition does not apply pooled |
| price within one tick | 53% (taker, last implied ask, last 2 VALIDATE hours: no book history); **93.2%** (exact 78.1%) against the recorded book 50 ms before the match (live development block 10-31 13:00-13:22, 277 taker orders; DS 95%, GF 95%, XM 63% of few) | >= 80% (met only where the book is recorded) |
| per-window PnL correlation, executable strict-fill rule | Pearson 0.18, Spearman 0.17 | >= 0.5 (not met) |
| per-window PnL correlation, volume proxy (no fill check) | 0.439 / 0.414 | |
| B1 ladder check (orders signed in the three predicted bursts) | 99.9% (chance 5%) | (component check) |

End-to-end `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 52 s incl. a 1,500-tx calldata sample): presence
over block seconds 0.846 vs pure baseline 0.784 (+0.063; all seconds 0.893 vs 0.857), side 77.9%, selection AUC 0.884
(recall 72.4% at lift 4.57), taker price within a tick of the last implied ask 53.2%, strict-fill PnL corr 0.38 / 0.32
(24 windows), ladder check 100%.

Why block seconds: Polygon produced a block every 1.5 s, so one second in three holds no block and can never hold a
fill; any model that infers the block phase (the market baseline does, from the timing of other traders' prints) gets
those structural zeros for free. The chain clock is fitted per UTC hour from (block number, block timestamp) pairs
(`_block_keep`; 154 of 166 VALIDATE hours locked, every VALIDATE fill inside a predicted block second). The unit
removes impossible bins only: 100% of fills and PnL stay in scope.

## Why it works

- Who pays: makers whose quotes lag the crypto price. 92% of the makers it hits are resting BUY orders on the
  complementary outcome; buying Up at the Up ask sells Down to a stale Down bidder. The bot forecasts BTC's next second
  from many venues and coins (ETH and alts lead BTC by a fraction of a second) and lifts the stale ask before it is
  repriced. Its whole design minimises reaction time: the orders are already signed (a full 1-cent ladder per outcome,
  refreshed every ~131 s), so a decision costs only the submission.
- What it is paid for: the latency edge (+3 c/share gross after a clear move) and, in the study weeks, the taker fee
  rebate on its very large volume; the quiet-regime volume roughly breaks even only with the rebate. It earns no
  liquidity rewards and no holding rewards; maker rebates are ~$3k per week.

## Can a normal user deploy it now

- Dependencies: low-latency websockets from several exchanges and coins, a pre-signed order ladder (any TypeScript
  clob-client user can do this), submission within ~1-2 s of a move, ~$2.5M per week of order flow across the wallets,
  and a high fee-rebate tier. All feeds are public; the conditions held through 10-22 and on 10-31 (sizes 30/60/100,
  same schedule).
- A replicator with a normal connection: with >= 2 s latency and strict fills the rule bought $262k on VALIDATE and lost
  1.6% before rebates (+0.1% with a 50% fee rebate). Without the rebate tier and co-location it should expect to lose.

## Known limitations

- Presence passes on VALIDATE only in the block-second unit (+0.055 over my pure baseline; +0.035 over all seconds);
  the examiner's own baseline may be stronger. Selection gain over the pure baseline is +0.023 (< 0.05).
- Live, ~70% of its orders come with no BTC/ETH futures trade or quote change in the previous second and inside bursts of
  other takers lifting the same asks (85% within 0.5 s after another trade): the trigger of those orders is not decoded.
- The Chainlink RTDS 1-s price carries no side information (50-54%, n = 212).
- Price within a tick needs the book; there is no public Polymarket book history for exam lots before 10-31.
- PnL correlation of an executable replica is low (0.18): the net position is a small difference of large two-sided
  volumes and a slow replica does not get the bot's fills.
- 18.7% of one-sided seconds have no visible move on any BTC series or ETH (side ~64% there).
- A fourth wallet (0xd84403ef...) runs the same bot; its prints still count as "other traders" in the tape features.
