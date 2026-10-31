# btc5m-bot: frozen rule (iteration 7)

Target status on VALIDATE: scope met; presence met in the block-second unit (0.875, +0.055 over a pure market baseline,
CI > 0); price within a tick met (95.1% of VALIDATE taker orders against the touch of the same match, from calldata; the
trivial touch anchor, stated as such); side not met where it likely applies (XM, one-sided in 24.3% of its windows:
72.6% per one-sided second, 73.1% per taker order, 20/29 one-sided windows; live per decision 75-86%, 90-97% on strong
votes); executable PnL correlation 0.18 (< 0.5). Iteration 7 showed that
0.18 is the ceiling of the replica's own design (30 shares, >= 2 s latency): even the wallet's OWN decisions reach only
0.14 / 0.21 through that fill model, and 0.40 at their true sizes. Target not reached; nothing is exam-verified.

Code: `code/final_rule.py`, `evaluate(start_ts, end_ts, intervals=None) -> dict` (with `intervals`, only windows that start
in one of the `[a, b)` pairs count; live recordings are read through `iter_live(..., allow_sealed=ALLOW_SEALED)` with the
module constant `ALLOW_SEALED = False`). Models are trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC);
VALIDATE = 2026-10-16 .. 2026-10-23 00:00 UTC (2,016 windows, 1.21M cells). Nothing was fitted on VALIDATE or sealed data.
Iteration 7 added `side_live_decision` (`_live_vote`: the decision-level side rule on the exam-input recording, reported as
`side_accuracy_live_decision`; None where the period has no recording, e.g. h1/h2) and `outcome.pnl_overlap_diagnostics`
(`_pnl_overlap`: split-half and oracle ceilings from the wallet's own fills; diagnostics only, never toward the target).
The exam-input recorder `code/rec_exam7.py` writes the live rule's inputs (`btc5m_xclob`, `btc5m_xven`) in EVERY block
through tools/live.py Writer from 10-31 16:03:48 UTC to 11-02 06:00 UTC, so the sealed blocks 10-31 18-24, 11-01 00-06 and
11-01 12-18 carry them for a future-block exam.

Tags: **exam-verified** (passed a sealed exam: none yet), **VALIDATE-only** (measured on VALIDATE / development data,
including the 10-31 live development block), **hypothesis** (supported by little data or by argument).

## The decision process, component by component

1. **Order generation (decoded from V2 calldata, B1) - VALIDATE-only, deterministic.** The bot never prices an order when
   it trades. It PRE-SIGNS a ladder of BUY limit orders for each window: both outcomes, every price on the 1-cent grid
   (filled prices 0.13-0.88 seen), a few copies per level and two sizes per level (e.g. 30 and 100 shares), in a burst of
   ~1 s per wallet (~1.7 ms per price level), three times per window at rel = -89.5 s, +42.0 s and +172.7 s; each order is
   used 4-136 s after signing. One process signs XM, then DS (+1.06 s), GF (+2.17 s) and a fourth wallet 0xd84403ef...
   (+3-4 s). Salt = round(Math.random() * Date.now()) (TypeScript clob-client), signatureType 3, builder = metadata = 0.
   Check in `evaluate` (`order_generation_b1`): VALIDATE 99.9% of 13,443 orders inside the predicted bursts (chance 5%).
2. **Selection - VALIDATE-only.** Every BTC 5-minute Up/Down window (94-99% traded), nothing else; inside a window only
   prices in the ladder range (~0.12-0.88). Whole-cluster outages (40 min to 5 h) are bot-side.
3. **Timing / trigger - VALIDATE-only (live development block).** The decision is the SUBMISSION of a pre-signed order,
   triggered by a tick-level MICROPRICE move (size-weighted touch: queue depletion or price change) of the BTC and ETH
   perps and spot (Binance USD-M and spot, OKX, Bybit, Hyperliquid) toward the outcome. Iteration 7 tested trigger vs
   correlate (14:50-16:05, 695 taker matches): the side agreement of the vote in 100-ms bins peaks at 75% in
   [m - 400, m - 200) ms before the matching-engine ms m and falls to ~50% from m + 300 ms (placebo ~50% throughout); on a
   100-ms grid of all window time the hazard of a cluster match on o in the next 100-600 ms rises from 2.3% (no tick) to
   5.1% (0.02-0.1 bp toward o), 5.6% (0.1-0.5 bp) and 8.7% (> 0.5 bp), and stays at 2.2-2.5% for ticks against o (first
   interval: 1.0% -> 9.4%). A trigger, necessary but with a low base hazard (the signed tick adds +0.02 / +0.08 AUC over
   Polymarket trade activity at the decision level). Per-series kernels (50-ms bins) name the primary stream: Binance
   USD-M BTC peaks first and sharpest at [m - 300, m - 250) (87.9% toward the bought side), then Binance USD-M ETH, OKX
   and Bybit at m - 300..-400; Hyperliquid peaks later (m - 200..-100) and is a follower. Historically (block clock) the presence score on block seconds is
   `model_it5_blk_full`; flag `p >= 0.30` (fixed in iteration 1). Chainlink RTDS carries no side information at 0-3 s lags.
4. **Side - VALIDATE-only.** Per decision (live): the sign of the microprice vote over [m - 600, m - 100) ms. The
   ten-series vote agreed with 86.4% (14:15-14:47), 83.0% (14:55-15:10) and 75.3% (16:04-16:25) of covered taker
   decisions (placebo 46-55%): it replicates but decays. The frozen exam-feed version (`_live_vote`, six series: Binance
   USD-M + spot, OKX; BTC and ETH) covers 61.5% of 16:04-16:25 decisions at 80.4% (placebo 52.7%). Per block second
   (historical; side model `model_it5_side_book.txt`) 76.7% of VALIDATE one-sided seconds; the block clock blurs the
   sub-second trigger (84.8% at match ms vs 76.8% at block time on the same live matches, iteration 6). It buys BOTH
   outcomes in 99.8% of windows (pooled), and tilts to the underdog as prices leave 0.5 (at |p - 0.5| 0.3-0.4: 58% of small
   and 69% of big orders vs 35% for other takers; also at prices unchanged for 30 s), so its fair value is not the
   market's (hypothesis: a wider vol; not fitted yet).
5. **Price - VALIDATE-only.** Limit = the touch (best ask) of the chosen outcome at the decision: it submits the
   pre-signed ladder order at that price. This is the trivial "touch" anchor, and the rule says so. Historical check
   from calldata (`price.calldata_touch`): **95.1%** of 6,306 VALIDATE taker orders within one tick of the best maker
   price the same match consumed (equal 83.9%); 11% are one or more cents ABOVE the touch (more for large orders). Live:
   93.2% within a tick of the recorded ask 50 ms before the match.
6. **Size - VALIDATE-only.** A fixed (small, large) menu per day, the same at every price: 60/100 (10-09..13), 30/50
   (10-15..18, 200 on 10-16), 30/100 (10-19..22 and 10-31). Large share by wallet DS 8%, GF 33%, XM 13% (calldata sample),
   plus an EVENT-level component: two wallets' orders on the same token within 1 s are both large 1.68 x as often as
   independence (permutation null 0.75, p = 0.0005). Nothing measured at the block clock predicts it (within-wallet AUC
   0.44-0.59 for BTC moves, price, time). Hypothesis: depth at the touch or the live tick size (to be tested on weekday
   live blocks).
7. **Exit / inventory - VALIDATE-only.** 59% of taker orders leave a remainder; it rests as a GTC bid for at most a few
   seconds (19% of remainders refill, within 0-3 s; a cheaper ask that a resting bid would have matched prints a median
   5 s after the last fill) and is cancelled. Holds every position to resolution: no sells, merges, splits or conversions;
   REDEEM once per window; TAKER_REBATE once a day = exactly 0.5 x the previous day's taker fees; MAKER_REBATE once a day;
   no liquidity or holding rewards.
8. **Fan-out across wallets - VALIDATE-only (live).** One trigger fans out to one or more wallets: 633 live taker matches
   form 486 events (< 300 ms apart, same window and outcome; 75% single-wallet); DS goes first in 80%, GF follows a
   median 54-69 ms later; participation does not rise with the trigger strength (Saturday sample).

## VALIDATE metrics (2026-10-16..23; target thresholds in brackets)

| metric | VALIDATE | target |
|---|---|---|
| scope: fills / abs PnL in the rule's universe | 100% / 100% (every BTC 5m window) | >= 80% (met) |
| presence AUC over BLOCK seconds, no own state, `model_it5_blk_full` | **0.8747** (GF 0.875, XM 0.893, DS 0.857; halves 0.875 / 0.873) | >= 0.85 (met) |
| PURE market-activity baseline on the same bins | 0.8193 -> gain **+0.055**, 2-h block bootstrap 95% CI [0.052, 0.058] | gain >= 0.05, CI > 0 (met with my baseline) |
| presence over ALL seconds (unit pre-registered in iteration 1) | 0.9132 vs pure 0.8781 (+0.035) | |
| selection (size classes + cell score) | AUC 0.869, recall 68.6% at lift 4.63 (pure baseline 0.846) | met; gain 0.023 < 0.05 |
| side, pooled one-sided seconds (n = 90,170) | 76.7% (taker 79.4%); market-only 63.2% | >= 80% where it applies |
| side, XM | 72.6% of its one-sided seconds; per taker order 73.1% (769 orders in seven 2-h chunks, market-only 63.9%), one-sided windows by first decision 20/29 = 69% | >= 80% (not met) |
| side per taker order, every order scored (`side.decision_units`, seven 2-h chunks = 14 h, 13,189 orders) | pool 72.7% (market-only 59.9%); GF 74.6%, DS 71.8% | |
| side per decision, live (not historical) | ten-series vote 86.4% / 83.0% / 75.3% in three intervals, stable by vote strength (>= 5 series: 90-97%; 1 series: 64-66%); exam-feed six-series 80.4% on 61.5% | |
| price within one tick (taker orders) | **95.1%** vs the touch of the same match (calldata); live book 93.2%; tape anchor 53% | >= 80% (met, trivial touch anchor) |
| per-window PnL correlation, executable strict-fill rule (latency >= 2 s, 30 shares) | Pearson 0.18, Spearman 0.17 | >= 0.5 (not met) |
| executable replica, presence-weighted size, fills in [s, s+2] (decoded latency) | pool 0.18 / 0.16 (DS 0.19, GF 0.12, XM -0.01) | |
| oracle: the wallet's own taker decisions through the frozen fill model (>= 2 s) | true size pool 0.40 / 0.39; 30 shares 0.14 / 0.21 | (ceiling of convention a) |
| oracle: own decisions, fills in the same block window | true size pool 0.68 / 0.66; 30 shares 0.26 / 0.31 | (ceiling of convention b) |
| oracle: own orders, no fill model | 30 shares pool 0.41 / 0.49; size class (30 / 100) 0.88 / 0.87 | |
| split-half per-window PnL of a wallet's own orders | DS -0.03, GF 0.14, XM -0.03, pool 0.16 | (no window-level direction) |
| B1 ladder check (orders signed in the three predicted bursts) | 99.9% (chance 5%) | (component check) |

PnL convention, pre-registered in iteration 7 before any new replica is scored: the correlation is reported (a) with
latency >= 2 s (fills against other takers' prints in [s+1, s+3]) and (b) at the decoded latency (decision at s from
information <= s-1, fills in [s, s+2]); (b) counts toward the target only if the examiner accepts the decoded latency.

End-to-end `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 52 s, iteration-7 code): presence over block seconds
0.846 vs pure baseline 0.784, side 77.9%, selection AUC 0.884 (recall 72.4% at lift 4.57), price within a tick 96.4%
(calldata touch), strict-fill PnL corr 0.38 / 0.32 (24 windows), overlap diagnostics pool split-half 0.24, oracle
30-share 0.79, size class 0.90; `side_live_decision` None (no recording for that period).

## Why it works

- **What it is paid for: mostly the taker-fee rebate.** Polymarket pays each wallet, every day, exactly 50% of its
  previous day's BTC 5m taker fees (TAKER_REBATE rows; 13 of 13 days checked for every wallet). In the VALIDATE week the
  cluster paid $61.6k of taker fees and got $30.8k back, plus ~$3k of maker rebates, against a trading PnL after fees of
  only +$4.4k (t = 0.50 over 1,904 windows). About 85% of its income is the rebate, a fixed function of its volume.
- **Who pays on the trading side:** makers whose quotes lag the perps' top of book. A queue depletion or price tick of
  the BTC/ETH perps shifts the fair value of the 5-minute digital; 200-500 ms later the bot lifts the stale ask before
  the makers (93% of them complementary BUY orders, i.e. the other side of a mint) reprice. Its pre-signed ladder makes
  each decision a single submission. Per order the edge is small and noisy (per-window PnL is a sum of independent
  order-level bets); the rebate on the volume makes the whole profitable.

## Can a normal user deploy it now

- Dependencies: low-latency websockets with sized top of book from Binance (USD-M and spot), OKX, Bybit and Hyperliquid
  (BTC and ETH), a reaction time of ~200-500 ms from a perp tick to a Polymarket match, a pre-signed order ladder (any
  TypeScript clob-client user can do this), ~$2.5M per week of order flow, and the 50% taker rebate (paid per wallet on its
  own fees; the conditions held through 10-22 and on 10-31: sizes 30/60/100, the same schedule, TAKER_REBATE rows daily).
- A replicator with a normal connection: with >= 2 s latency and strict fills the frozen rule bought $262k on VALIDATE and
  lost 1.6% before rebates (+0.1% with a 50% fee rebate); at the decoded latency the presence-weighted replica bought
  $1.04M at +0.5% before rebates. Without the rebate a slow copy loses money; with it, it roughly breaks even.

## Known limitations

- The PnL condition: under the >= 2 s strict-fill convention no rule can reach 0.5 pooled (the wallet's own decisions and
  sizes give 0.40). At the decoded latency the ceiling is 0.66-0.70 with the right size class but 0.26-0.31 with a fixed
  size, and the executable replica built from block-second scores reaches 0.18: the gap is decision overlap (block clock)
  and the unpredictable large size.
- The live side rule's aggregate agreement falls across intervals (86% -> 83% -> 75%) because quiet markets bring more
  weak-vote decisions (per vote strength it is stable: 90-97% with >= 5 agreeing series, 64-66% with one); the six-series
  exam version abstains on 38% of decisions; at the block clock every decision scores 72-79%. The 80% side bar is not
  met per decision; the quiet, weak-vote decisions are the unexplained part of the side.
- Presence passes only in the block-second unit (+0.055 over my pure baseline); the examiner's own baseline may be
  stronger. Selection gain over the pure baseline is +0.023 (< 0.05).
- Price uses the touch of the match itself (calldata) for historical lots: it measures the decoded rule, not a PIT
  forecast of the touch; live, the recorded book 50 ms before the match gives 93%.
- A fourth wallet (0xd84403ef...) runs the same bot; its prints still count as "other traders" in the tape features.
