# directional-maker: frozen rule R5 (iteration 7)

Rule id: **R5-R3+chainlink-stack+match-clock-price** = R4 (iteration 6) with R3's presence score stacked with the
Chainlink settlement stream (adopted in iteration 7 by its pre-registered criterion; see "R5" below). Code: `code/final_rule.py` (`evaluate(start_ts, end_ts,
intervals=None)`, pooled and per wallet). R4 = the iteration-4 rule R3 plus a price rule on the match clock
(`price_match_clock`) for every period the shared live recorder covers (`.cache/live/<dev|sealed>/clob_crypto`,
records `x` with the transaction hash and the server match ms). On the historical VALIDATE (2026-10-27..30) there is no
live recording, so R4 = R3 there. Frozen model files: `presence3_rule.txt` (rule), `presence3_activity.txt`
(market-activity baseline), `presence3_own.txt` (own inventory, reported separately), `selection2_*.txt` with
`THETA_SEL`. Live trades are read with a tolerant gzip-member reader that honours `ALLOW_SEALED` (False except in the
examiner's driver). Scope: BTC 5m Up/Down windows, the three wallets (bosona, almach, mo-money) pooled, with per-wallet
metrics. New in iteration 7: `code/cl_source.py` (the Chainlink settlement stream by value stamp, from the live
recorders or Polymarket's own endpoint) and `code/r5.py` (the Chainlink features), used by R5.

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine signs every order of the three wallets: per-wallet sequential salt, `timestamp`, `metadata` and `builder` 0, restarted together daily at 01:00 UTC; ~13.5 signed orders/s per wallet. 88% of the filled exact-500 orders in 20 minutes of all-match calldata are the cluster's. | VALIDATE-only (counter); hypothesis (live) | B1 calldata; `code6/q2_identity.py` |
| Information | (R5 uses it: VALIDATE-only, small gain on the lot) The ladders are re-priced on each **Chainlink BTC/USD report (the settlement stream) as the public RTDS relay publishes it**: exact-500 re-posts agree with the report's 1-s change 0.71-0.81 in the 0-200 ms after the relay's publish ms (bursts 0.76-0.81) against 0.35-0.44 before it, and the agreement follows the relay's variable publish delay (0.8-1.5 s after the stamp), not a fixed lag. No other maker reacts (0.50-0.53). Print selection is best with the report stamped t - 1.43 s (0.764 vs 0.728 at t - 2 and 0.730 at the panel's "engine clock" t - 0.7). No lead over the public relay larger than the clock resolution (~ +-0.1 s). | VALIDATE-only (live, one evening half hour for the publish test; 15m) / hypothesis for 5m | `code7/i2_publish.py`, `code7/sel_clock.py` |
| Selection | One engine over crypto Up/Down. BTC 5m = 78% of VALIDATE fills / 69% of absolute PnL; BTC 5m + 15m 87% / 89%. Nearly every window is quoted (VALIDATE 94.5% active). Off-runs are rare operator or controller switches: live, BTC 5m was switched off at 16:53:5x UTC on 10-31 in all three wallets at once, right after a window that lost $1,565 and at the day's PnL low (-$2,424), while BTC 15m continued; historically the switch-off window's day PnL ranks it at AUC 0.80 (5 events, own state). | hypothesis | `results/iter5_coverage.json`, `code7/stoploss.py` |
| Timing | Quotes are re-posted about once a second: a re-price pass of the three wallets' ladders within ~0-150 ms of each Chainlink publish (29% of 15m re-posts fall in the 200 ms after a publish), plus single-wallet re-posts. The orders that fill sit at the touch (78%), were posted a median 95 ms after some trade (unambiguous orders: 52 ms) and are matched a median 0.68 s later; but per trade a fresh 500 at the sold token's touch within 150 ms is rare (2.4%) and as frequent on the other token (2.7%), so "join after a trade" is a property of the filled orders, not a per-trade rule (P1 pilot, AUC 0.61). Its exact-500 re-posts follow a futures mid move of the previous 50-250 ms in 95% of the cases with such a move. It stops ~30 s before the end. | VALIDATE-only (STUDY ms clocks, live) | `code6/q1_confirmed.py`, `code7/i2_publish.py`, `code7/p1_join.py` |
| Side | **Quote side** (iteration 7): on each Chainlink report, the outcome whose 500 bid goes to the touch in the re-price pass is the sign of the Chainlink edge over the Polymarket mid (digital fair of the report vs priceToBeat, no fitted parameter): BTC 5m 0.776 (n 1,051 one-sided posting events), **live VALIDATE 0.793 (n 757)** vs futures-edge 0.573, cheaper side 0.542, always-Up 0.538, last mid move 0.502, token just sold 0.489; BTC 15m 0.73-0.79. **Fill side**: it is filled on the side whose quote a seller hits; rule = the side with the higher predicted presence (R3 0.663 VALIDATE, exam 0.655; R5 on the VALIDATE sample 0.667 vs 0.647). Takers do not trade on the displayed Chainlink price (corr 0.03 vs 0.09-0.18 for the futures move). | quote side: VALIDATE-only (live pilot); fill side: exam-verified (partial) | `code7/m2_posture.py`; VALIDATE 0.663 vs 0.613 activity; exam 0.655 vs 0.600 |
| Price | Fill price = last clean print minus 0.01. On the match clock (R4) within one tick for 0.828 of live VALIDATE fills (15:00-16:30 UTC, n 1,194; each wallet 0.82-0.83); this is the trivial anchor "last print" on a fresh clock (trivial anchors 0.822-0.845). On the block clock (R3) 0.709 VALIDATE, 0.688 exam. | exam-verified (block clock); VALIDATE-only (match clock, live) | `code6/i1_price_match.py`, `price_match_clock` |
| Size | Size class 500 x 2^k (on 10-31 its filled orders were 98.4% size 500), switched for all wallets in the same second: 500 in the weekday 12-21 UTC session; outside it 62 or 250, upgraded to 500 when the 300-s Binance futures realised vol at the open is >= 7.5e-5 per second (VALIDATE recall 0.88, precision 0.71). Partially filled orders are re-posted with the remainder. | VALIDATE-only | `code6/m5_size.py` |
| Exit | Holds to resolution; taker-buys the under-held complement (72-83% of its taker buys) sized to the imbalance or a fifth, then merges in 17-51% of those windows; 2-4% of PnL. | VALIDATE-only | `results/iter5_flatten.json` |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints (and, for the live part, every trade record whose transaction holds a cluster trade).
2. Presence (R3): for every (window, side s, 10-s bin starting at t in [0, 300) s), P(cluster maker BUY fill on s in
   [t, t+10)) = `presence3_rule.txt` on features published by t (time, side, clean-tape activity, Binance 1-s TWAP-60
   fair, z, returns, realised vol, edge = fair - last clean print, window path, previous-window proxy outcome and
   strike move, UTC hour, weekday, US-session flag). No own state.
3. Side: in bins where it fills exactly one side, the side with the higher predicted presence.
4. Price: if the fill's transaction is in the shared live trade stream, the last trade of the same market before its
   match ms whose transaction holds no cluster trade (mapped to the fill's token) minus 0.01; otherwise the last clean
   data-api print on s strictly before the fill second minus 0.01. Both on the 0.01 grid.
5. Selection: R2's print score (`selection2_all.txt`) flagged at `THETA_SEL`.
6. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price).

## R5 (iteration 7): R3 stacked with the Chainlink settlement stream

7. Presence R5 (where the Chainlink series is available, R3 elsewhere): p_R5 = sigmoid(0.7244 + 1.2305 logit(p_R3) +
   1.2574 gap_s - 0.7608 edge_cl_s + 0.0454 dcl10_s + 0.0743 z_cl_s - 0.6915 fair_cl_s), all at the bin start t from
   the Chainlink BTC/USD value stamped t - 3 s (and t - 13 s): fair_cl_s = digital P(closing TWAP-60 >= Gamma
   priceToBeat) with the known part of the closing TWAP in the last minute and R3's volatility, gap_s = fair_cl_s -
   R3's Binance fair, edge_cl_s = fair_cl_s - last clean print, dcl10_s = 10-s Chainlink change (bp), z_cl_s its z
   (`code/r5.py`). Chainlink values come from the live recorders (dy_rtds streaming with publish ms, dx_rtds / dm_rtds
   snapshots) or Polymarket's `crypto-price` endpoint (`code/cl_source.py`; verified to reproduce priceToBeat and
   finalPrice); a value stamped t - 3 is always published by t (publish delay p90 1.47 s).
8. Side (R5): the side with the higher p_R5.

Fitted (logistic) on a STUDY sample of 154 windows; chosen on a pre-registered VALIDATE sample of 144 windows (pairs of
consecutive windows every 80 minutes over 10-27..30): presence 0.6923 (R3) -> **0.6997** (gain +0.0075, 2-h
block-bootstrap 95% [+0.0016, +0.0131]; better on 3 of 4 days); side 0.647 -> 0.667. The gain is small because on the
lot the Chainlink fair correlates 0.988 with the Binance fair (smooth stream); its largest weight is on gap_s: the
cluster is filled more on the side whose Chainlink value stands above the Binance one.

## Metrics

Historical VALIDATE (2026-10-27..30, 1,152 windows, 27,988 cluster maker fills; R4 = R3 there; R5 needs the Chainlink
series, which this iteration fetched for a 144-window sample only):

| metric | value | target |
| --- | --- | --- |
| presence AUC, no own state (primary), R3/R4 full VALIDATE | **0.716** | >= 0.85 |
| R5 on the VALIDATE sample (144 windows) vs R3 on the same bins | 0.6997 vs 0.6923 (+0.0075 [+0.0016, +0.0131]) | |
| market-activity-only baseline | 0.685 (gain +0.032) | gain >= 0.05 |
| with own inventory (separate) | 0.747 | |
| side accuracy (6,339 one-sided bins) | 0.663 (activity 0.613, own inventory 0.70) | >= 0.80 |
| price within one tick (block clock) | 0.709 | >= 0.80 |
| per-window PnL corr Pearson / Spearman | 0.329 / 0.325 | >= 0.5 |
| selection AUC / recall / lift | 0.685 / 29.5% / 2.87 | 0.80 / 50% / 3 |
| coverage of fills / absolute PnL (BTC 5m) | 0.783 / 0.686 | 0.80 / 0.80 |

Live VALIDATE (development block 2026-10-31 15:00-16:30 UTC, pre-registered in iteration 6): R4 price within one tick
**0.828** (each wallet 0.82-0.83; trivial anchors 0.822-0.845); print-level selection (exploratory, not frozen) AUC
**0.764** with the futures fair and the Chainlink report stamped t - 1.43 s (iteration 7; D chosen on this block) vs 0.637
for market activity alone (recall 44% at lift 2.7); 10-s presence 0.667 with Chainlink vs 0.624 activity only; side
0.655 vs 0.567 activity.

The high-accuracy target is not met. Where the gap is: (1) presence and selection depend on whether the cluster's fresh
touch join meets the next seller; the sellers follow the futures, not the displayed Chainlink price, and public activity
predicts them at 0.60-0.64; (2) on the lot the Chainlink stream is smooth (lag-1 autocorrelation of 1-s changes about
0, sd $1-3) and its fair correlates 0.99 with the Binance fair, so the variation that identifies the Chainlink input
live (the 1-s white noise that appeared on 10-31, sd ~ $9) is absent historically; (3) the side is the taker's choice of
which token to sell into the quotes, only partly set by the center's skew.

## Why it works

It is a two-sided liquidity provider whose reservation price follows the settlement source itself, the Chainlink BTC/USD
report, re-priced the moment Polymarket's public relay publishes each report, with a ~6-cent half-spread on each outcome
(pair cost 0.88). No other maker in the book re-prices on the report. Pricing off the settlement stream has a cost: on
the live block, fills where the Chainlink report valued the token more than the faster Binance futures did (67% of
fills) returned -4.6%, while fills where the two agreed returned +26%; the spread and the agreeing fills carry the
profit. Its filled orders are fresh 500-share joins at the best bid of the token that was just sold, matched within a
second, so it supplies liquidity to selling waves. It is paid by takers who cross its spread: the profit comes from the
first prints of non-high-frequency takers (+5.7% on VALIDATE, +3.7% on STUDY), while against high-frequency takers it
roughly breaks even. Latency takers do not reach it: takers signing within 300 ms after a $5 futures move filled other
makers in 5.5% of matches and the cluster in 0 of 182, because its 500-share quotes re-anchor to the moving mid within
250 ms and the venue's ~190-ms taker speed bump keeps any reacting taker behind its re-post. The losers are the slower
makers and the uninformed takers who cross a 6-cent spread. It is not paid for liquidity rewards ($0.81 in nine days)
and only a little for maker rebates (8% of PnL). It sizes up in the weekday US session and when futures volatility is
high, and on 10-31 it switched BTC 5m off at its daily PnL low.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version (R2) lost 12.8% under strict fills at 2-s latency in exam round 1:
a quote that reacts in 2+ seconds is the stale quote that takers pick off. The wallets' own edge persists (+3.95% on the
exam lot, +4.3% VALIDATE). What it needs, all still true on 2026-10-31: the Chainlink BTC/USD report as Polymarket's
public RTDS relay publishes it (subscribe with filters "" to get every 1-s update with its publish ms; the symbol-filtered
subscription only sends snapshots), a CLOB connection that re-prices within ~0.1 s of each publish and joins the touch
within ~100 ms of a trade, capital for 500-share rungs on both outcomes of several BTC 5m and 15m windows at once, and
unchanged fees (0.07 taker), listings and matching. The information is public: this laptop receives the relay 0.12-0.35 s
after its publish stamp, so a home connection is a few hundred ms behind the engine and would be one of the slower makers
this strategy profits from: expect zero or a loss without co-located latency.
