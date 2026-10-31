# directional-maker: frozen rule (iteration 2 rule, kept unchanged after iteration 3)

Rule id: **R2-presence-lgbm-clean-path-xwin**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts)`), features
`code/features2.py`, selection helpers `code/sel2.py`. Frozen model files next to the code:
`presence2_all_path_xwin.txt` (rule), `presence2_activity.txt` (market-activity-only baseline),
`presence2_all_path_xwin+own.txt` (own-inventory variant, reported separately), `selection2_all.txt` and
`selection2_activity.txt` (print selection and its baseline). Thresholds `THETA_SEL` are constants in the code.
Everything was trained once on BUILD (2026-10-09..16) and chosen on VALIDATE (2026-10-16..23); nothing is fitted in
`evaluate`. Scope: BTC 5m Up/Down windows (55% of the cluster's volume); the three wallets (bosona, almach, mo-money)
are pooled as one operator.

Iteration 3 tried twelve new families (print signature, public correlates of the schedule, counterparty-type arrival,
Binance order flow, a conditional side model, schedule deconfounding, post-fill convergence, stale-quote pick-off,
sizing, stop timing, grid position of the touch, Kraken as the reference feed; NOTES.md). None beat R2 on VALIDATE, so R2 stays frozen. The run stops on the brief's
diminishing-returns rule (presence AUC 0.759 -> 0.763 -> 0.763 over three iterations).

## What the cluster does (evidence: NOTES.md)

Three copies of one quoting engine. Each wallet rests BUY orders on the 0.01 grid, at the top of the book (its price
is the best in 90% of sweeps; 85% of its fills are mint matches against takers buying the other outcome), usually
one tick below the last public print of that outcome and on average 2.9 cents below our Binance TWAP-60 fair value
(other makers' fills print at that fair value; 40% of the cluster's fills are at or above it, so its own fair value
differs from ours). Order sizes follow a fixed ladder that does not depend on the edge, the price
or the time in the window: mostly 500 and 1000 shares in BUILD (signature 498 / 500 / 502 per wallet), 500 / 250 / 125
in VALIDATE. Orders carry one price each, most are filled once, and multi-fill orders are consumed within 0-2 s.

Timing: orders are resting at the window open (first fill <= 6 s after the start in 21% of BUILD windows); it stops
quoting about 30 s before the end (median last fill 200 s; fills in the last 30 s fall to a third). After a sharp move
of the Binance fair against one of its bids, other makers' bids on that outcome are hit three times as often while the
cluster's fills rise only 1.6x: it reprices or cancels faster than the average competing maker.

Side: it bids the outcome that its Binance fair value says the market underprices, most clearly right after the open,
when the market has not priced the gap between spot and the strike that was just fixed (side = sign(spot at the start
- strike) 76-79% when the gap exceeds 3 bp), and then keeps adding to the side it holds. Quotes follow Binance 1-s data
with no lead over it (Binance fits its prices better than Kraken) and do not lean on Binance order flow. The wallets
do not split windows or sides.

Which windows it trades is the operator's choice, not market state: when it has no BTC 5m fill it still trades other
markets in 89-93% of 5-min slots; in VALIDATE BTC 5m was off for 13 h twice (23:00 to 12:00 UTC on 10-17/18 and
10-18/19, both after losing evenings) and only partly on afterwards. Nothing public tracks it: the window-level on/off
AUC is 0.47-0.58 from tape statistics, the previous hour's taker mix and competitor identity, the spot regime and the
listing fields (the reward programme is the same for every window). This caps the no-own-state presence AUC.

## The rule

1. Presence: for every (window, side s, 10-s bin starting at t in [0, 300) s), P(cluster maker BUY fill on s in
   [t, t+10)) = LightGBM `presence2_all_path_xwin` on features published by t (clean tape): time, side; activity
   (prints so far, hits on s / complement bids and volumes over 10/30/60 s, price changes, distinct takers and big
   prints in 60 s, previous window's print count, last print on s); Binance 1-s fair value of the TWAP-60 settlement,
   z, returns, realized vol; edge = fair - last print; window path (edge at the first print, running max / mean /
   share-positive of the edge, fair and z at 10 s); previous window's Binance proxy outcome and strike move.
   No own-state.
2. Side (bins where it fills exactly one side): the side with the higher predicted presence.
3. Price: last clean taker print on s strictly before the fill second, minus 0.01, on the 0.01 grid.
4. Selection: each in-window taker print (except the cluster's own) scored by `selection2_all` (the presence row of
   the side whose bid it hits + the print's price, size, second, direction, price minus the last clean print, Binance
   fair minus price); flagged when the score >= THETA_SEL (BUILD top 15%).
5. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price).

## VALIDATE metrics (2,016 windows; end-to-end `evaluate(1792108800, 1792713600, local=True)`, and `code/null99.py`)

| metric | value | target |
| --- | --- | --- |
| presence AUC, no own-state (primary) | **0.763** | >= 0.85 |
| presence AUC, market-activity-only baseline | 0.735 (gain +0.029) | |
| presence AUC with own inventory (separate model) | 0.822 | |
| presence AUC within windows where it is active | 0.736 (baseline 0.712) | |
| presence AUC with an oracle for its active windows (ceiling) | 0.862 | |
| side accuracy, 3,805 one-sided fill bins | 0.679 (0-30 s: 0.769; top-25% confidence: 0.816) | >= 0.80 |
| side baselines: favourite by last print / Binance favourite | 0.515 / 0.545 (p ~ 0) | |
| price exact / within 0.01 (13,934 fills) | 0.313 / 0.585 | |
| selection AUC / stratified (price x time x side) / within-window | 0.770 / 0.757 / 0.669 | >= 0.80 |
| selection rotation null, 99 draws (stratified / within-window) | null 0.680 / 0.655: p = 0.01 (z 8.7) / p = 0.04 (z 1.7; 0.35 with another negative sample) | p < 0.01 |
| selection recall / lift at the BUILD top-15% threshold | 49.0% / 3.80 | >= 50% / >= 3 |
| selection, market-activity-only baseline | AUC 0.744, strat 0.724, within-window 0.664, recall 47.1%, lift 3.23 | |
| per-window PnL correlation rule vs wallet, Pearson / Spearman (1,086 windows) | 0.334 / 0.393 | >= 0.5 |
| cluster's own BTC 5m maker return on VALIDATE | -2.3% (BUILD +4.1%) | |

The high-accuracy target is not met. Selection recall/lift is at the bar (49% at lift 3.8) but its AUC (0.77) is not,
and inside a window its spot component barely beats the rotation null: which print fills the cluster is print
mechanics (size, price vs the last print), not spot. The presence AUC is capped by the operator's BTC 5m schedule.
`evaluate` runs the 99-draw null by default (n_perm=99, negatives 10%); the examiner can run it on the holdout
unchanged.

## Why it works

It is paid for liquidity provision with a fair-value skew, plus faster repricing than the competing makers. It is not
paid for forecasting spot or for rebates. It bids on average 2.9 cents below a Binance fair value, at the top of the book,
on the outcome the market underprices relative to Binance (mostly right after the open, when the market has not yet
priced where spot stands against the new strike). Takers who sell into that bid, or buy the other outcome at market,
pay the spread and the stale price. It fills when the market trades below Binance (in BUILD the last print was 2.4
cents under the fair). In BUILD the market then rose 0.7 cents above that print within 60 s (1.2 cents above the fill
price) while Binance fell 0.7 cents: it earned from the market catching up with Binance. When Binance jumps, it pulls or reprices its bids sooner
than other makers, so stale-quote snipers mostly hit the others. The locked pair spread is about zero, rebates are
small (Gold 18%) and its quotes show no lead over public Binance 1-s data. The losers are thousands of different
takers (3,200 in VALIDATE, top-10 = 13%) whose orders are larger than the tape's typical print (median 18 vs 8
shares). In BUILD most of the profit came from the largest orders (top size quartile, > 62 shares). The fast
high-frequency takers rarely hit it (0.3% of their prints).

The edge decayed before H. In VALIDATE its fills kept the same 2.9-cent mean discount to our Binance fair at the fill,
but the fair then fell 1.6 cents within 60 s, against 0.7 cents in BUILD at the same discount: the takers who traded
with it now knew better where spot was going next. (Our fair model is over-confident and drifts back toward the fill
price after every fill, so only the comparison between the two periods is clean.) This was broad, not one new sniper
(old and new counterparties alike). The worst fills were near the money in mid-window (30-120 s: -10.7%; fair
0.4-0.6: -14.9%). It turned +2.1 cents per share in BUILD into -1.7 cents. The operator cut BTC 5m windows and fills
by about 60% and shrank the order ladder.

## Can a normal user deploy it now

The rule needs only public data: the Binance spot feed (websocket, sub-second), the Polymarket CLOB (post and replace
BUY orders on both outcomes at the window open, 0.01 grid, 5-share minimum, no taker fees as a maker) and capital of
roughly $50-150k for the cluster's turnover (about $1.1M of maker buys per BUILD week). Its quotes match Binance 1-2 s
before the block timestamp, which a home connection can do. But its protection against stale-quote sniping comes from
repricing faster than the average maker after Binance moves, and a home setup would likely be slower than this
operator. And the evidence before H says it would not pay now: the cluster's own BTC 5m maker fills returned -2.3% on
VALIDATE because they were adversely selected on the next minute's spot move, it switched BTC 5m off overnight
(23:00-12:00 UTC on two nights, after losing evenings) and traded fewer windows afterwards while staying active
elsewhere, and every public-data maker built from the same data (spot fair value, spot-reactive, tape-anchored, fixed
ladders, buy-the-dip) lost or was insignificant. A replicator with a normal connection and computer should expect about
zero or a loss after adverse selection.
