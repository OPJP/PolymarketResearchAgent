# btc5m-bot: frozen rule (iteration 6)

Target status on VALIDATE: scope met; presence met in the block-second unit (0.875, +0.055 over a pure market baseline,
CI > 0); price within a tick met (95.1% of VALIDATE taker orders against the touch of the same match, from calldata; the
trivial touch anchor, stated as such); side not met where it likely applies (XM is one-sided in 24.3% of its windows:
80.7% on the seconds where the pooled cluster is one-sided, 72.6% on all of XM's one-sided seconds; pooled 76.7% per
second, but the pooled cluster is two-sided in 99.8% of windows); executable PnL correlation 0.18 (< 0.5), and the
operator's own wallets correlate only 0.00-0.20 with each other per window. Target not reached; nothing is exam-verified.

Code: `code/final_rule.py`, `evaluate(start_ts, end_ts, intervals=None) -> dict` (with `intervals`, only windows that start
in one of the `[a, b)` pairs count; live recordings are read through `iter_live(..., allow_sealed=ALLOW_SEALED)` with the
module constant `ALLOW_SEALED = False`). Models are trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC);
VALIDATE = 2026-10-16 .. 2026-10-23 00:00 UTC (2,016 windows, 1.21M cells). Nothing was fitted on VALIDATE or sealed data.
Iteration 6 added `price.calldata_touch` (used as `price_within_tick` where no live book covers the period, e.g. h1/h2)
and `side_condition_by_wallet` (share of one-sided windows per wallet).

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
3. **Timing / trigger - VALIDATE-only (live development block for the ms results).** The decision is the SUBMISSION of a
   pre-signed order. Live (10-31 13:00-14:47, 782 taker matches; matching-engine ms of each match from the recorded trade
   with the same tx hash, venue trades at exchange ms): when one of the fast venues moved over the reaction window
   [m - 600, m - 100) ms the bot buys in that direction: Binance USD-M ETH 94.1% (moved before 24% of matches vs 5% at
   placebo times), OKX ETH swap 94.0%, Binance spot BTC 93.5%, Binance USD-M BTC 93.9%; the largest of the six
   Binance/OKX series moved (> 0.1 bp) before 50% of the matches with 86.5% agreement (> 0.05 bp: ~94% on the first
   633). 37% of the matches are quiet on all eight recorded trade feeds over the last second, and the five sized quote
   feeds barely move before them; they concentrate late in the window (rel 200-300 s: ~69% quiet), come in bursts (59%
   within 2 s of a previous cluster match) and sit inside Polymarket book activity (the bought outcome's bid and ask rose
   in the last 300 ms in ~40% vs 9% at placebo times). **Their trigger is the perps' top of book**: over the same
   reaction window the MICROPRICE (size-weighted touch) of the ETH and BTC perps ticks in the bot's direction before most
   of them (Binance USD-M ETH 85%, OKX ETH 83%, Bybit ETH 81%, Bybit BTC 90% when it moved; placebo 35-56%); a vote of ten
   sized quote series (Binance USD-M and spot, Bybit, OKX, Hyperliquid; BTC and ETH) covers 90% of the 204 covered taker
   matches with 86.4% side agreement (quiet 84.0%, moving 87.3%; placebo 46%), and the venues' prices then follow in the
   next 1-3 s (the bot reacts to the start of a move). VALIDATE-only (live development block, 34 minutes, Saturday); not
   yet in the frozen historical rule: the historical book exists only for Bybit (orderbook.200 archives; BTC is in the
   side model since iteration 5, ETH is being fetched). Earlier hypothesis for these matches (now superseded)
   (hypothesis: a value / stale-quote rule evaluated on Polymarket book changes; see Known limitations). Historically the
   presence score on block seconds is `model_it5_blk_full` (it4b features, BUILD block seconds); on all seconds
   `p = model_it4b_all_y`; flag `p >= 0.30` (fixed in iteration 1). Chainlink RTDS (the settlement feed) carries no
   side information at any assumed availability lag of 0-3 s.
4. **Side - VALIDATE-only.** Per second it buys the outcome the composite just moved toward (side model
   `model_it5_side_book.txt`: it4b features + lagged segments + Bybit perp top-of-book imbalance; 76.7% of VALIDATE
   one-sided seconds). Live: ~94% after a fast move; the vote of the perps' microprice ticks over the 100-600 ms before
   the match 86.4% of taker matches (84.0% of the quiet ones; out-of-sample later interval 83.0% / 77.3%, placebo 55%).
   Candidate not yet frozen: adding the Bybit ETHUSDT order-book archive features to the side model gives 77.17% on
   VALIDATE (taker seconds 80.3%; McNemar p = 1e-9 vs 76.66%), `model_it6_side_book_eth.txt` (VALIDATE-only). Pooled, it buys BOTH outcomes in 99.8% of windows; XM alone is
   one-sided in 24.3% of its windows, so the side condition may apply to XM (80.6% / 72.7%, see above).
5. **Price - VALIDATE-only.** Limit = the touch (best ask) of the chosen outcome at the decision: it submits the
   pre-signed ladder order at that price. This is the trivial "touch" anchor, and the rule says so. Historical check
   from calldata (`price.calldata_touch`): on the 7 sampled VALIDATE hours the limit is within one tick of the best maker
   price the same match consumed for **95.1%** of 6,306 taker orders (equal 83.9%; halves 95.0% / 95.3%; DS 96.6%, GF
   93.9%, XM 84.0%); in 11% the limit is one or more cents ABOVE every consumed level (more often for large orders: the
   bot sometimes submits a higher ladder level, a small sweep). Live: 93.2% within a tick of the recorded ask 50 ms
   before the match. An unfilled remainder rests at the limit (its only maker activity).
6. **Size - VALIDATE-only.** A fixed (small, large) menu per day, the same at every price: 60/100 (10-09..11), 30/50
   (10-15..18, 200 on 10-16), 30/100 (10-19..22 and 10-31). Large share is a per-wallet setting (DS 5%, GF 30%, XM 32%).
7. **Exit / inventory - VALIDATE-only.** Holds every position to resolution: no sells, merges, splits or conversions;
   REDEEM once per window; TAKER_REBATE once a day = exactly 0.5 x the previous day's taker fees; MAKER_REBATE once a day;
   no liquidity or holding rewards.
8. **Fan-out across wallets - VALIDATE-only (live).** One trigger fans out to one or more wallets: 633 live taker matches
   form 486 events (< 300 ms apart, same window and outcome; 75% single-wallet); DS goes first in 80%, GF follows a
   median 69 ms later; participation does not rise with the trigger strength (Saturday sample).

## VALIDATE metrics (2026-10-16..23; target thresholds in brackets)

| metric | VALIDATE | target |
|---|---|---|
| scope: fills / abs PnL in the rule's universe | 100% / 100% (every BTC 5m window) | >= 80% (met) |
| presence AUC over BLOCK seconds, no own state, `model_it5_blk_full` | **0.8747** (GF 0.875, XM 0.893, DS 0.857; halves 0.875 / 0.873) | >= 0.85 (met) |
| PURE market-activity baseline on the same bins | 0.8193 -> gain **+0.055**, 2-h block bootstrap 95% CI [0.052, 0.058]; by wallet +0.065 / +0.068 / +0.052 | gain >= 0.05, CI > 0 (met with my baseline) |
| presence over ALL seconds (unit pre-registered in iteration 1) | 0.9132 vs pure 0.8781 (+0.035) | |
| selection (size classes + cell score), 2.74M in-window taker prints | AUC 0.869, recall 68.6% at lift 4.63 (pure baseline 0.846) | AUC >= 0.80, recall >= 50% at lift >= 3 (met; gain 0.023 < 0.05) |
| side, pooled one-sided seconds (n = 90,170) | 76.7% (taker 79.4%); market-only 63.2%; favourite 45.9% | >= 80% where it applies |
| side, XM (one-sided in 24.3% of its windows) | frozen side model on all 10,749 XM one-sided seconds 72.6% (pooled-one-sided seconds 80.7%, seconds where a sibling bought the other outcome 59.1%, XM taker seconds 79.1%; halves 73.2 / 72.1); an XM-only model 72.4% | >= 80% (not met) |
| price within one tick (taker orders) | **95.1%** vs the touch of the same match from calldata (6,306 orders); live book 93.2%; tape anchor 53% | >= 80% (met, trivial touch anchor) |
| per-window PnL correlation, executable strict-fill rule | Pearson 0.18, Spearman 0.17 | >= 0.5 (not met) |
| ceiling reference: the operator's own wallets per window | DS-GF 0.198, DS-XM 0.002, GF-XM 0.145 (Spearman 0.28 / 0.02 / 0.17) | |
| B1 ladder check (orders signed in the three predicted bursts) | 99.9% (chance 5%) | (component check) |

End-to-end `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 55 s incl. a 1,500-tx calldata sample): presence over
block seconds 0.846 vs pure baseline 0.784, side 77.9%, selection AUC 0.884 (recall 72.4% at lift 4.57), **price within a
tick 96.4%** (calldata touch, 1,075 taker orders; tape anchor 53.2%), strict-fill PnL corr 0.38 / 0.32 (24 windows), ladder
check 100%.

## Why it works

- **What it is paid for: mostly the taker-fee rebate.** Polymarket pays each wallet, every day, exactly 50% of its
  previous day's BTC 5m taker fees (TAKER_REBATE rows; 13 of 13 days checked for every wallet). In the VALIDATE week the
  cluster paid $61.6k of taker fees and got $30.8k back, plus ~$3k of maker rebates, against a trading PnL after fees of
  only +$4.4k (t = 0.50 over 1,904 windows). About 85% of its income is the rebate, a fixed function of its volume. Since
  June-July the four wallets received $413k of taker rebates and $56k of maker rebates.
- **Who pays on the trading side:** makers whose quotes lag the crypto price. After a fast move on Binance (ETH and BTC
  futures and spot lead), the bot lifts the stale ask within ~100-600 ms, before the makers (93% of them complementary
  BUY orders, i.e. the other side of a mint) reprice; those moving-regime trades earn ~+3 c/share gross. Its pre-signed
  ladder makes each decision a single submission. The quiet-regime trades (about half of the matches, late in the
  window) earn roughly the fee net of the rebate: they are break-even volume that the rebate makes profitable.

## Can a normal user deploy it now

- Dependencies: low-latency websockets from Binance (USD-M and spot, BTC and ETH) and other venues, a reaction time of
  ~100-600 ms from a Binance print to a Polymarket match, a pre-signed order ladder (any TypeScript clob-client user can do
  this), ~$2.5M per week of order flow, and the 50% taker rebate (it is paid per wallet on its own fees; the conditions
  held through 10-22 and on 10-31: sizes 30/60/100, the same schedule, TAKER_REBATE rows daily).
- A replicator with a normal connection: with >= 2 s latency and strict fills the rule bought $262k on VALIDATE and lost
  1.6% before rebates (+0.1% with a 50% fee rebate). Without the rebate the strategy loses money on the quiet half of its
  volume; with it, a slow copy roughly breaks even. The edge after fees is small, and most of the profit is the rebate
  on volume.

## Known limitations

- 37% of the live taker matches have no move on any recorded trade feed (8) in the previous second, and the quote feeds
  (5 venues) barely move before them; their trigger is not decoded (candidates tested and rejected or weak: Chainlink
  RTDS at any lag, sub-tick moves 62-68%, move-based value gap 59-68%, a calibrated level FV at chance with a 4.8-c
  calibration error, fresh maker quotes 26% vs 21%, settlement-TWAP lock-in not significant, inventory balancing 43%).
- The per-window PnL correlation target (0.5) looks unreachable for any executable replica: the operator's own wallets,
  driven by the same engine, correlate 0.00-0.20 with each other.
- Side: XM's own one-sided seconds where a sibling bought the other outcome (4,033 of 10,749) are not predicted by the
  pooled side model; per-wallet side rules are not decoded.
- Presence passes only in the block-second unit (+0.055 over my pure baseline; +0.035 over all seconds); the examiner's
  own baseline may be stronger. Selection gain over the pure baseline is +0.023 (< 0.05).
- Price uses the touch of the match itself (calldata) for historical lots: it measures the decoded rule, not a PIT
  forecast of the touch; live, the recorded book 50 ms before the match gives 93%.
- A fourth wallet (0xd84403ef...) runs the same bot; its prints still count as "other traders" in the tape features.
