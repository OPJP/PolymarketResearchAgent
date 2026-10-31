# directional-maker: frozen rule (iteration 2)

Rule id: **R2-presence-lgbm-clean-path-xwin**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts)`), features
`code/features2.py`, selection helpers `code/sel2.py`. Frozen model files next to the code:
`presence2_all_path_xwin.txt` (rule), `presence2_activity.txt` (market-activity-only baseline),
`presence2_all_path_xwin+own.txt` (own-inventory variant, reported separately), `selection2_all.txt` and
`selection2_activity.txt` (print selection and its baseline). Thresholds `THETA_SEL` are constants in the code.
Everything was trained once on BUILD (2026-10-09..16) and chosen on VALIDATE (2026-10-16..23); nothing is fitted in
`evaluate`. Scope: BTC 5m Up/Down windows (55% of the cluster's volume); the three wallets (bosona, almach, mo-money)
are pooled as one operator.

Change vs iteration 1: every taker print in a transaction where a cluster wallet traded is now removed before any
feature is computed (iteration 1 counted those prints, so its 0.772 was partly the cluster's own fills; the same
features on the clean tape score 0.759).

## What the cluster does (evidence: NOTES.md)

Three copies of one quoting engine. Each wallet rests BUY orders on the 0.01 grid (mostly 500 shares; signature
498 / 500 / 502), usually one tick below the last public print of that outcome, at the top of the book (its price is
the best in 90% of sweeps; 85% of its fills are mint matches against takers buying the other outcome). Orders are
resting at the window open (first fill <= 6 s after the start in 21% of BUILD windows); it stops near the end. The
side: it bids the outcome that its Binance-based TWAP-60 fair value says the market underprices, most clearly right
after the open, when the market has not priced the gap between spot and the strike (side = sign(spot at the start -
strike) 76-79% when the gap exceeds 3 bp), and then keeps adding to the side it holds. Quotes follow Binance 1-s data
with no lead over it. The wallets do not split windows or sides; each works its own orders in parallel.

Orders carry one price each, most are filled once, and multi-fill orders are consumed within 0-2 s. Order sizes
shrank from BUILD (500 / 1000 / 498 / 502) to VALIDATE (a 500 / 250 / 125 ladder plus small orders).

Which windows it trades is the operator's choice, not market state: when it has no BTC 5m fill it still trades other
markets in 89-93% of 5-min slots; in VALIDATE BTC 5m was off for 13 h twice (23:00 to 12:00 UTC on 10-17/18 and
10-18/19, both after losing evenings) and only partly on afterwards (by hour: 74-75% of windows 12-20 UTC vs 38-40% 00-12 UTC).
Public tape statistics of on and off windows are the same. This caps the no-own-state presence AUC.

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
and inside a window its spot component barely beats the rotation null (p = 0.04, or 0.35 with another negative sample): which print fills the cluster is
print mechanics (size, price vs the last print). The presence AUC is capped by the operator's BTC 5m schedule (with an
oracle for the active windows R2 would score 0.862). `evaluate` runs the 99-draw null by default
(n_perm=99, negatives 10%); the examiner can run it on the holdout unchanged.

## Why it works

It is paid for liquidity provision with a fair-value skew, not for speed or rebates. Takers who buy the other outcome
at market cross a spread the cluster sets one tick below the last print, on the side its Binance TWAP model says is
cheap. Its edge is the directional residual: right after the open the market has not priced where spot stands
relative to the strike that was just fixed, and the cluster leans on that side and keeps adding. The locked pair
spread is about zero, rebates are small (Gold 18%), and it shows no lead over public Binance 1-s data. The people who
lose are takers paying the spread and the mispriced open: thousands of different takers (3,200 in VALIDATE, top-10 =
13%), whose orders are larger than the tape's typical print (median 18 vs 8 shares) and 86-89% of which buy the other
outcome; the fast high-frequency takers rarely hit it (0.3% of their prints). In BUILD this earned +4.1% per dollar
bought; in VALIDATE it lost 2.3% while it cut its BTC 5m windows and fill count by about 60% and its order sizes, so
the edge decayed or competition caught up.

## Can a normal user deploy it now

The rule needs only public data: the Binance spot feed (websocket, sub-second), the Polymarket CLOB (post and replace
BUY orders on both outcomes at the window open, 0.01 grid, 5-share minimum, no taker fees as a maker) and capital of
roughly $50-150k for the cluster's turnover (about $1.1M of maker buys per BUILD week). No privileged latency is
implied: its quotes match Binance 1-2 s before the block timestamp, which a home connection can do. But the evidence
before H says it would not pay now: the cluster's own BTC 5m maker fills returned -2.3% on VALIDATE, it switched BTC 5m
off overnight (23:00-12:00 UTC on two nights, after losing evenings) and traded fewer windows afterwards while staying
active elsewhere, and every public-data maker built from the same data (spot
fair value, spot-reactive, tape-anchored, fixed ladders, buy-the-dip) lost or was insignificant. A replicator with a
normal connection and computer should expect about zero or a loss after adverse selection, unless they find the part
of the side signal we cannot see (why the cluster's own fills earned +3% to +6% on other held-out windows).
