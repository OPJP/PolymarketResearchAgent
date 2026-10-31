# directional-maker: frozen rule R4 (iteration 6)

Rule id: **R4-R3-presence+match-clock-price**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts, intervals=None)`,
pooled and per wallet). R4 = the iteration-4 rule R3, unchanged, plus a price rule on the match clock
(`price_match_clock`) for every period the shared live recorder covers (`.cache/live/<dev|sealed>/clob_crypto`, records
`x` with the transaction hash and the server match ms). On the historical VALIDATE (2026-10-27..30) there is no live
recording, so R4 = R3 there. Frozen model files: `presence3_rule.txt` (rule), `presence3_activity.txt` (market-activity
baseline), `presence3_own.txt` (own inventory, reported separately), `selection2_*.txt` with `THETA_SEL`. Live trades are
read with a tolerant gzip-member reader that honours `ALLOW_SEALED` (False except in the examiner's driver). Scope: BTC
5m Up/Down windows, the three wallets (bosona, almach, mo-money) pooled, with per-wallet metrics.

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine signs every order of the three wallets: per-wallet sequential salt, `timestamp`, `metadata` and `builder` 0, restarted together daily at 01:00 UTC; ~13.5 signed orders/s per wallet (10-31, all markets). Exact-500/100 adds in the recorded BTC books never exceed the three wallets' signatures (0 of 124 minutes; R^2 0.53); in the calldata of all 5,528 matches of 20 minutes, 88% of the filled exact-500 orders are the cluster's and none of the exact-100 or exact-250 ones. | VALIDATE-only (counter); hypothesis (live) | B1 calldata; `code6/q2_salt.py` |
| Information | The ladder's center (mid of the top Up and Down rungs; their sum is 0.88) is skewed off the Polymarket mid by the **current Chainlink BTC/USD report (the settlement source)**: the value stamped t-2 s, which is 'now' on the settlement clock (the TWAP-60 stamped st is exactly the mean of the values stamped st-62..st-3), explains the skew with held-out R^2 0.21 (0.13 at t-3, <= 0 at t-1 and t; BTC 15m undecided). The skew tracks the stream's own 1-s noise (lag-1 autocorrelation of its changes -0.47), which no exchange contains: Binance futures, spot, Coinbase, OKX and Bybit at 0-4 s all <= 0. | hypothesis (one live block) | `code6/m1_center.py`, `code6/m1_race.py` |
| Selection | One engine over crypto Up/Down. BTC 5m = 78% of VALIDATE fills / 69% of absolute PnL; BTC 5m + 15m 87% / 89%. Nearly every window is quoted: 94.5% of VALIDATE windows active; live 24 of 24 windows quoted, P(0 fills given quoted) 0.04. The rare long BTC 5m off-runs are operator switches with no public correlate yet. | hypothesis | `results/iter5_coverage.json`, `iter6_m3_quoted_*.json` |
| Timing | Quotes are re-posted about once a second. The orders that fill are fresh joins at the touch (78% at the touch, 68% joining an existing level, 9.5% improving it), posted a median 95 ms after a trade (59% within 150 ms vs 41-46% for other makers' touch adds) that sold that token (61% vs 42-44%), and matched a median 0.68 s later (resting at-touch orders are 11 s old at random moments). Its exact-500 re-posts follow a futures mid move of the previous 50-250 ms in 95% of the cases with such a move (fast re-anchoring to the mid; the skew comes from Chainlink). It stops ~30 s before the end. | VALIDATE-only (STUDY ms clocks); hypothesis (live) | `code6/q1_confirmed.py` |
| Side | Up and Down are quoted around one center; it is filled on the side whose quote reaches the touch. Rule: the side with the higher predicted presence. Live: the Chainlink edge picks the filled side in 0.63 of one-sided bins (n 127; always-Up 0.60). | exam-verified (partial) | VALIDATE 0.663 vs 0.613 activity; exam 0.655 vs 0.600 |
| Price | Fill price = last clean print minus 0.01. **On the match clock (R4) within one tick for 0.828 of live VALIDATE fills (15:00-16:30 UTC, n 1,194; bosona 0.831, almach 0.830, mo-money 0.823; 0.858 to 16:13)**; this is the trivial anchor "last print" on a fresh clock (the trivial anchors score 0.822-0.845 on the same fills). On the block clock (R3, prints seen 1-3 s late) 0.709 VALIDATE, 0.688 exam; with a 2-s-old anchor live 0.59. | exam-verified (block clock); VALIDATE-only (match clock, live) | `code6/i1_price_match.py`, `price_match_clock` |
| Size | Size class 500 x 2^k (on 10-31 its filled orders were 98.4% size 500; the 100s in the book are other makers'), switched for all wallets in the same second: 500 in the weekday 12-21 UTC session (96-98% of windows); outside it 62 or 250, upgraded to 500 when the 300-s Binance futures realised vol at the open is >= 7.5e-5 per second (STUDY threshold; VALIDATE recall 0.88, precision 0.71, AUC 0.95). Partially filled orders are re-posted with the remainder. No edge dependence. | VALIDATE-only | `code6/m5_size.py` |
| Exit | Holds to resolution; taker-buys the under-held complement (72-83% of its taker buys) sized to the imbalance or a fifth, then merges in 17-51% of those windows; 2-4% of PnL. | VALIDATE-only | `results/iter5_flatten.json` |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints (and, for the live part, every trade record whose transaction holds a cluster trade).
2. Presence (R3): for every (window, side s, 10-s bin starting at t in [0, 300) s), P(cluster maker BUY fill on s in
   [t, t+10)) = `presence3_rule.txt` on features published by t (time, side, clean-tape activity, Binance 1-s TWAP-60 fair,
   z, returns, realised vol, edge = fair - last clean print, window path, previous-window proxy outcome and strike move,
   UTC hour, weekday, US-session flag). No own state.
3. Side: in bins where it fills exactly one side, the side with the higher predicted presence.
4. Price: if the fill's transaction is in the shared live trade stream, the last trade of the same market before its
   match ms whose transaction holds no cluster trade (mapped to the fill's token) minus 0.01; otherwise the last clean
   data-api print on s strictly before the fill second minus 0.01. Both on the 0.01 grid.
5. Selection: R2's print score (`selection2_all.txt`) flagged at `THETA_SEL`.
6. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price).

## Metrics

Historical VALIDATE (2026-10-27..30, 1,152 windows, 27,988 cluster maker fills; R4 = R3 there):

| metric | value | target |
| --- | --- | --- |
| presence AUC, no own state (primary) | **0.716** | >= 0.85 |
| market-activity-only baseline | 0.685 (gain +0.032) | gain >= 0.05 |
| with own inventory (separate) | 0.747 | |
| side accuracy (6,339 one-sided bins) | 0.663 (activity 0.613, own inventory 0.70) | >= 0.80 |
| price within one tick (block clock) | 0.709 | >= 0.80 |
| per-window PnL corr Pearson / Spearman | 0.329 / 0.325 | >= 0.5 |
| selection AUC / recall / lift | 0.685 / 29.5% / 2.87 | 0.80 / 50% / 3 |
| coverage of fills / absolute PnL (BTC 5m) | 0.783 / 0.686 | 0.80 / 0.80 |

Live VALIDATE (development block 2026-10-31 15:00-16:30 UTC, pre-registered in iteration 6; exploratory models not
frozen): R4 price within one tick **0.828** (each wallet 0.82-0.83; trivial anchors 0.822-0.845); print-level selection
AUC 0.740 with the Chainlink and futures fairs vs 0.637 for market activity alone (recall 42% at lift 2.7); 10-s presence
0.667 with Chainlink vs 0.624 activity only; side 0.655 vs 0.567 activity; the center's skew follows Chainlink at 2 s with
held-out R^2 0.212 (every exchange <= -0.02).

The high-accuracy target is not met. Where the gap is: (1) presence and selection depend on whether the cluster's fresh
touch join meets the next seller, which public activity predicts at 0.60-0.64 and the Chainlink-skewed center improves by
+0.04 (bins) to +0.10 (prints) live; (2) the Chainlink 1-s series exists only live (data.chain.link answers 429), so the
historical VALIDATE and the released lot cannot score that input; (3) the side is the taker's choice of which token to
sell into the quotes, only partly set by the center's skew.

## Why it works

It is a two-sided liquidity provider whose reservation price follows the settlement source itself, the current Chainlink
BTC/USD report, with a ~6-cent half-spread on each outcome (pair cost 0.88). Pricing off the settlement stream has a cost:
on the live block, fills where the Chainlink report valued the token more than the faster Binance futures did (67% of
fills) returned -4.6%, while fills where the two agreed returned +26%; the spread and the agreeing fills carry the profit. Its filled orders are
fresh 500-share joins at the best bid of the token that was just sold, matched within a second, so it supplies liquidity
to selling waves. It is paid by takers who cross its spread: the profit comes from the first prints of non-high-frequency takers (+5.7%
on VALIDATE, +3.7% on STUDY), while against high-frequency takers it roughly breaks even (-0.9% to +0.1%). Latency
takers do not reach it: in 20 minutes of all-match calldata, takers signing within 300 ms after a $5 futures move filled
other makers in 5.5% of matches (11x the random rate) and the cluster in 0 of 182, because its 500-share quotes re-anchor
to the moving mid within 250 ms. The losers are the slower makers and the uninformed takers who cross a 6-cent spread. In busy periods the paired round trips across the two
outcomes paid (+11% on paired dollars) and the directional remainder lost. It is not paid for liquidity rewards ($0.81 in
nine days) and only a little for maker rebates (8% of PnL). It sizes up (500 instead of 62 or 250) in the weekday US
session and when futures volatility is high, when its edge is largest.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version (R2) lost 12.8% under strict fills at 2-s latency in exam round 1:
a quote that reacts in 2+ seconds is the stale quote that takers pick off. The wallets' own edge persists (+3.95% on the
exam lot, +4.3% VALIDATE). What it needs, all still true on 2026-10-31: the Chainlink BTC/USD report as published (RTDS or
Data Streams; values arrive 1.2-1.8 s after their stamps), a Polymarket CLOB connection that re-posts within about a second and joins the
touch within ~100 ms of a trade, capital for 500-share rungs on both outcomes of several BTC 5m and 15m windows at once,
and unchanged fees (0.07 taker), listings and matching. A replicator on a home connection could subscribe to the same
public feeds, but the measured edge sits in sub-second joins and sub-second queue position; without matching that speed
they would be one of the slower makers this strategy profits from: expect zero or a loss.
