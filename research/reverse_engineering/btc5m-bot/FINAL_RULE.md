# btc5m-bot: frozen rule (iteration 8)

Target status on VALIDATE: scope met; presence met in the block-second unit (0.875, +0.055 over a pure market baseline,
CI > 0); price within a tick met (95.1% of VALIDATE taker orders against the touch of the same match, from calldata; the
trivial touch anchor, stated as such); side not met where it likely applies (XM, one-sided in 24.3% of its windows:
72.6% per one-sided second, 73.1% per taker order; per taker order pooled 72.7% at the block clock); executable PnL
correlation 0.18 (< 0.5). Iteration 8 showed that no size rule lifts the executable replica (0.13-0.18 for every rule,
including a size driven by the replica's own book): the PnL condition is bound by decision overlap at the block clock.
Target not reached; nothing is exam-verified.

Code: `code/final_rule.py`, `evaluate(start_ts, end_ts, intervals=None) -> dict` (with `intervals`, only windows that start
in one of the `[a, b)` pairs count; live recordings are read through `iter_live(..., allow_sealed=ALLOW_SEALED)` with the
module constant `ALLOW_SEALED = False`). Models are trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC);
VALIDATE = 2026-10-16 .. 2026-10-23 00:00 UTC (2,016 windows, 1.21M cells). Nothing was fitted on VALIDATE or sealed data.
Live (future-block) components, all fitted or chosen on development blocks of 10-31 only:
- `side_live_decision` (`_live_vote`, frozen in iteration 7): six-series exam-feed vote, now reading both the rec_exam7 and
  the rec_exam8 feed names (identical records); with the PRE-REGISTERED full-coverage fallback of iteration 8
  (`full_coverage`, reported as `side_accuracy_live_decision_full_coverage`);
- `side_live_decision_ext` (pre-registered secondary, iteration 8): the same vote plus Bybit linear L1 from `btc5m_xfam`;
- `presence_live_decision` (`_live_hazard`, iteration 8): decision-level hazard with frozen coefficients `HAZ_FULL_COEF` and
  the Polymarket-activity baseline `HAZ_BASE_COEF`, both fitted on 10-31 16:04:30-16:33 UTC.
- `evaluate` is a wrapper (iteration 8): if the historical pipeline cannot run (e.g. a day's Binance 1-s archive is not
  published yet), it returns the live components only (`_evaluate_live_only`) instead of failing; tested through the exam
  path on 10-31 16:35-17:05 (development).
Exam inputs recorded through the sealed blocks: `code/rec_exam7.py` (btc5m_xclob / btc5m_xven, 10-31 16:03 -> 11-02 06:00),
`code/rec_exam8.py` (the same recorder as btc5m_xclob8 / btc5m_xven8, 11-02 05:59 -> 11-03 18:00: weekday sealed blocks
11-02 06-12 and 18-24, 11-03 00-06 and 12-18) and `code/rec_fam8.py` (btc5m_xfam: Binance USDC-M and COIN-M perps, spot
USDC / FDUSD books, Deribit perp quotes, Bybit L1; btc5m_xliq: liquidations; 10-31 17:45 -> 11-03 18:00). The sealed block
10-31 06-12 has no exam inputs; there the historical (block-clock) rule applies.

Tags: **exam-verified** (passed a sealed exam: none yet), **VALIDATE-only** (measured on VALIDATE / development data,
including the 10-31 live development blocks), **hypothesis** (supported by little data or by argument).

## The decision process, component by component

1. **Order generation (decoded from V2 calldata, B1) - VALIDATE-only, deterministic.** The bot never prices an order when
   it trades. It PRE-SIGNS a ladder of BUY limit orders for each window: both outcomes, every price on the 1-cent grid, a
   few copies per level and two sizes per level (e.g. 30 and 100 shares), in a burst of ~1 s per wallet (~1.7 ms per price
   level), three times per window at rel = -89.5 s, +42.0 s and +172.7 s. One process signs XM, then DS (+1.06 s), GF
   (+2.17 s) and a fourth wallet 0xd84403ef... (+3-4 s). Salt = round(Math.random() * Date.now()) (TypeScript clob-client),
   signatureType 3, builder = metadata = 0. Check in `evaluate`: 99.9% of 13,443 VALIDATE orders inside the predicted bursts.
   The schedule is identical on 10-31 (signing-time quantiles -89.6 / 42.3 / 43.5 / 173.2 / 174.7 s vs VALIDATE -89.7 /
   40.8 / 42.9 / 172.7 / 174.6 s).
2. **Selection - VALIDATE-only.** Every BTC 5-minute Up/Down window (94-99% traded), nothing else; inside a window only
   prices in the ladder range (~0.12-0.88). Whole-cluster outages (40 min to 5 h) are bot-side.
3. **Timing / trigger - VALIDATE-only (live development blocks).** The decision is the SUBMISSION of a pre-signed order
   ~250-350 ms after a microprice tick (size-weighted touch) of the Binance USD-M BTC/ETH perps (earliest, sharpest), OKX
   and Bybit toward the outcome. The Polymarket leg is fast: the order's limit equals the ask 50-100 ms before the match in
   74-75% of live orders (placebo 5-7%), so the lag is upstream. The hazard is gated by Polymarket activity, not by stale
   liquidity: per 500 ms, P(match on o) is 22% with a > 0.5 bp tick toward o while o's ask falls, 11-12% with the tick and
   an unchanged or rising ask, 5% when the touch moves with no tick, 2% when nothing moves. Decision-level presence on the
   exam feeds (frozen hazard, scored on the later interval 16:33-17:55): AUC 0.656 vs 0.598 for the Polymarket-activity
   baseline (trades, touch changes, touch age, price), gain +0.058 (window bootstrap 95% CI [0.041, 0.076]). Historically
   (block clock) the presence score on block seconds is `model_it5_blk_full`; flag `p >= 0.30` (fixed in iteration 1). The
   bot does not act on one identifiable message (the latest lag-shifted tick does worse than the vote).
4. **Side - VALIDATE-only.** Per decision (live): the sign of the microprice vote over [m - 600, m - 100) ms. Ten-series
   vote by interval 86.4% / 83.0% / 75.3% / 85.2% (fourth interval 16:33-17:55: 1 agreeing series 69.9%, 2: 79.7%, 3-4:
   89.5%, >= 5: 96.8%); the frozen exam-feed six-series vote 80.4% on 61.5% (16:04-16:25) and 85.4% on 68.0% (16:33-17:55;
   placebo 54%). Full coverage (pre-registered 10-31 18:16 UTC, chosen on 14:55-17:55; first clean test 11-01 06-12): vote
   -> the outcome whose Polymarket ask rose over [m - 600, m - 100) -> the outcome whose ask fell over [m - 3000, m - 100)
   -> the underdog; 70.6% / 78.2% in sample. Per block second (historical; side model `model_it5_side_book.txt`) 76.7% of
   VALIDATE one-sided seconds, 72.7% per taker order; the block clock costs 11-25 points (iteration 7). The side does NOT
   reference the operator's own book (+0.2 points on VALIDATE) nor an exact-strike fair value (50-55%). It buys both
   outcomes in 99.8% of windows and tilts to the underdog as prices leave 0.5 (58% small / 69% big at |p - 0.5| 0.3-0.4).
   Hypothesis for the tilt (VALIDATE-only): the bot's fair value uses an implied (options-market) vol. Deribit DVOL is
   2.1x (quartiles 1.5-2.8) the 5-min realized vol at its orders, the same multiplier a revealed-preference fit finds
   (k ~ 2-3), and a fair value at sigma = DVOL puts more of its buys below fair value (53.6%; underdogs 81%) than any fixed
   multiple of realized vol; such a fair value sits closer to 0.5 than Polymarket's, so underdogs look cheap. Underdog buys
   follow flat or adverse 12-s moves; the move before a buy is the same for favourites and underdogs (not a return-unit
   threshold).
5. **Price - VALIDATE-only.** Limit = the touch (best ask) of the chosen outcome as the bot saw it 50-150 ms before the
   match: it submits the pre-signed ladder order at that price (the trivial "touch" anchor, and the rule says so). 95.1% of
   6,306 VALIDATE taker orders within one tick of the best consumed maker price (equal 83.9%). 16% are deliberately one or
   more cents ABOVE the touch (GF 27%, XM 38-46%, DS 9-10%; the same shares on VALIDATE and 10-31; 18 of 21 live pay-up
   orders had seen the consumed touch, so it is not a stale view). The pay-up share rises with the implied-vol fair value
   above the touch (12-14% when the FV is below the touch, 23% when it is > 10 c above), a weak reservation-price
   behaviour rather than a clean FV - margin limit.
6. **Size - VALIDATE-only (own state).** A fixed (small, large) menu per day, the same at every price: 60/100 (10-09..13),
   30/50 (10-15..18), 30/100 (10-19..22 and 10-31). Which size is used follows the OPERATOR'S OWN BOOK in the window: the
   large size is used when the three wallets together are flat or long the bought outcome (GF 59-77%, XM 59-83% of orders)
   and rarely when the order would reduce an opposite position (net < -200 shares: GF 12%, XM 15%, DS 10%). Within-wallet
   VALIDATE AUC (BUILD-fitted): GF 0.751, XM 0.666, DS 0.578 vs market controls 0.489 / 0.353 / 0.546 and a market-trend
   analog (BTC return since the open) 0.52. Large orders lose 1.1-1.9 c per share after fees. Report without own state:
   the size is not predictable (within-wallet 0.44-0.59, iteration 7).
7. **Exit / inventory - VALIDATE-only.** 59% of taker orders leave a remainder; it rests as a GTC bid for at most a few
   seconds and is cancelled. Holds every position to resolution: no sells, merges, splits or conversions; REDEEM once per
   window; TAKER_REBATE once a day = exactly 0.5 x the previous day's taker fees; MAKER_REBATE once a day. 87.4% of the
   shares bought in a window end paired in complete sets, at a share-weighted pair cost of 0.9786 (VALIDATE).
8. **Fan-out across wallets - VALIDATE-only (live).** Each wallet carries one order at a time: no wallet has two taker
   matches less than 120 ms apart (three live intervals), and same-wallet pairs are 4-9% of the matches less than 300 ms
   apart against 51-52% under independence. One trigger fans out to one or more wallets (17% of events have 2+ legs, always
   on 2+ wallets, usually 1 c apart); DS goes first in ~80%. The number of legs rises weakly with the trigger strength
   (12-16% -> 22-25%; AUC 0.64-0.67 vs 0.61-0.63 for activity).

## VALIDATE metrics (2026-10-16..23; target thresholds in brackets)

| metric | VALIDATE | target |
|---|---|---|
| scope: fills / abs PnL in the rule's universe | 100% / 100% (every BTC 5m window) | >= 80% (met) |
| presence AUC over BLOCK seconds, no own state, `model_it5_blk_full` | **0.8747** (GF 0.875, XM 0.893, DS 0.857; halves 0.875 / 0.873) | >= 0.85 (met) |
| PURE market-activity baseline on the same bins | 0.8193 -> gain **+0.055**, 2-h block bootstrap 95% CI [0.052, 0.058] | gain >= 0.05, CI > 0 (met with my baseline) |
| presence over ALL seconds (unit pre-registered in iteration 1) | 0.9132 vs pure 0.8781 (+0.035) | |
| selection (size classes + cell score) | AUC 0.869, recall 68.6% at lift 4.63 (pure baseline 0.846) | met; gain 0.023 < 0.05 |
| side, pooled one-sided seconds (n = 90,170) | 76.7% (taker 79.4%); market-only 63.2%; own-inventory-only (short leg) 51.0%; side model + own state 75.5% | >= 80% where it applies |
| side, XM | 72.6% of its one-sided seconds; per taker order 73.1%; one-sided windows by first decision 20/29 = 69% | >= 80% (not met) |
| side per taker order, every order scored (seven 2-h chunks, 13,189 orders) | pool 72.7% (market-only 59.9%); GF 74.6%, DS 71.8% | |
| price within one tick (taker orders) | **95.1%** vs the touch of the same match (calldata); live book 93.2%; tape anchor 53% | >= 80% (met, trivial touch anchor) |
| per-window PnL correlation, executable strict-fill rule (latency >= 2 s, 30 shares) | Pearson 0.18, Spearman 0.17 | >= 0.5 (not met) |
| executable replica at the decoded latency, best size rule (presence-weighted) | pool 0.18 / 0.16; own-net size rules 0.13-0.16 | |
| oracle: the wallet's own taker decisions through the frozen fill model (>= 2 s) | true size pool 0.40 / 0.39; 30 shares 0.14 / 0.21 | (ceiling of convention a) |
| oracle: own decisions, fills in the same block window | true size pool 0.68 / 0.66; 30 shares 0.26 / 0.31 | (ceiling of convention b) |
| oracle: own orders, no fill model | 30 shares pool 0.41 / 0.49; size class (30 / 100) 0.88 / 0.87 | |
| B1 ladder check (orders signed in the three predicted bursts) | 99.9% (chance 5%) | (component check) |

Live development blocks of 10-31 (not VALIDATE; reported for the future-block exam, never counted toward the target):

| metric | value |
|---|---|
| side, frozen six-series exam-feed vote | 85.4% on 68.0% of 462 decisions (16:33-17:55); 80.4% on 61.5% (16:04-16:25); placebo 52.7-53.9% |
| side, ten-series lab vote, four intervals | 86.4% / 83.0% / 75.3% / 85.2% of voted decisions |
| side, pre-registered full coverage (in sample) | 70.6% (16:04-16:33), 78.2% (16:33-17:55) |
| presence, frozen decision-level hazard (exam feeds), later interval | AUC 0.656 vs Polymarket-activity baseline 0.598; gain +0.058, CI [0.041, 0.076] |
| price, limit = ask 50 ms before the match | 74.9% exact (171 orders), 93.2% within a tick (277 orders, iteration 5) |

PnL convention, pre-registered in iteration 7 before any new replica is scored: the correlation is reported (a) with
latency >= 2 s (fills against other takers' prints in [s+1, s+3]) and (b) at the decoded latency (decision at s from
information <= s-1, fills in [s, s+2]); (b) counts toward the target only if the examiner accepts the decoded latency.

End-to-end `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 51 s, iteration-8 code): presence over block seconds
0.846 vs pure baseline 0.784, side 77.9%, selection AUC 0.884 (recall 72.4% at lift 4.57), price within a tick 96.4%
(calldata touch), strict-fill PnL corr 0.38 / 0.32 (24 windows); the live entries are None (no recording for that period).

## Why it works

- **It buys complete sets below 1 by sniping stale quotes on both sides, and the fee rebate pays for the fees.** In the
  VALIDATE week the cluster bought both outcomes of almost every window; 87.4% of its shares ended paired at a pair cost of
  0.9786, so each pair locks ~2.1 c. Gross trading PnL before fees was $65,960: $48,923 from locked sets and $17,037 from
  the unpaired remainder. Fees were $61,572 and Polymarket paid back exactly half of the taker fees ($30,786) the next day,
  plus ~$3k of maker rebates. Net ~ $38k for the week, of which the taker rebate is ~80% (all rebates ~88%); trading
  alone made +$4.4k after fees.
- **Who pays:** makers whose quotes lag the perps' top of book. A queue depletion or price tick of the BTC/ETH perps shifts
  the fair value of the 5-minute digital; ~250-350 ms later the bot lifts the ask before the makers (mostly complementary
  BUY orders, i.e. the other side of a mint) reprice, and it does so most often while the Polymarket touch is already
  moving. Each pre-signed order is one HTTP submission; one order in flight per wallet is why it runs several wallets.
- **What loses:** the large-size overlay. The bot uses its large size when its own book is flat or long the outcome, so the
  large orders build the window's unpaired position; they lose 1.1-1.9 c per share after fees and carry most of the
  per-window PnL variance (per-window PnL vs the unpaired part r = 0.93).

## Can a normal user deploy it now

- Dependencies: low-latency websockets with sized top of book from Binance USD-M (and spot), OKX and Bybit (BTC and ETH),
  a reaction time of ~250-350 ms from a perp tick to a Polymarket match (of which <= 50-150 ms on the Polymarket leg), a
  pre-signed order ladder (any TypeScript clob-client user can do this), several wallets for parallel orders, ~$2.5M per
  week of order flow, and the 50% taker rebate (paid per wallet on its own fees). These conditions held through 10-22 and on
  10-31 (same signing schedule, same pay-up shares, sizes 30/60/100, TAKER_REBATE rows daily).
- A replicator with a normal connection: with >= 2 s latency and strict fills the frozen rule bought $262k on VALIDATE and
  lost 1.6% before rebates (+0.1% with a 50% fee rebate); at the decoded latency the replica bought $0.75-1.25M at -0.3% to
  +0.5% before rebates for every size rule tried. Without the rebate a slow copy loses money; with it, it roughly breaks
  even. Dropping the large-size overlay would raise the bot's own return (small orders earn +0.2 to +1.3 c per share).

## Known limitations

- The PnL condition: under the >= 2 s strict-fill convention no rule can reach 0.5 pooled (the wallet's own decisions and
  sizes give 0.40). At the decoded latency the ceiling is 0.66-0.70 with the right size class, but the executable replica
  built from block-second decisions reaches 0.13-0.18 whatever its size rule (iteration 8): the gap is decision overlap.
  Live, at the decoded latency, the frozen hazard flagging as many 100-ms instants as the wallet's matches catches only
  8.2% of them (lift 2.75): the trigger is necessary but not sufficient.
- The weekend regime: quiet one-sided seconds are 28% on weekend days vs 15% on weekdays (VALIDATE), and the live
  weak-vote share was 44-56% on Saturday; the first future-block exam (weekend sealed blocks) will be scored in that regime.
- The live side: per decision strength it is stable (90-97% on strong votes) but the weak / no-vote decisions (31-45% of
  live decisions) are 64-80% at best, and their Polymarket fallbacks were not stable between intervals; the full-coverage
  rule is pre-registered and untested out of sample. At the block clock every decision scores 72-79%.
- Presence passes only in the block-second unit (+0.055 over my pure baseline); the examiner's own baseline may be
  stronger. Selection gain over the pure baseline is +0.023 (< 0.05). The decision-level hazard gains +0.058 out of sample
  but at an AUC of 0.66.
- Price uses the touch of the match itself (calldata) for historical lots: it measures the decoded rule, not a PIT
  forecast of the touch; live, the recorded book 50 ms before the match gives 75% exact and 93% within a tick.
- The size rule uses own state (the operator's net); without own state the size is not predictable.
- A fourth wallet (0xd84403ef...) runs the same bot; its prints still count as "other traders" in the tape features.
