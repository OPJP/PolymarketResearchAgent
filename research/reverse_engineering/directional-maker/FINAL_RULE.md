# directional-maker: frozen rule (iteration 1)

Rule id: **R1-presence-lgbm-all_reg**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts)`),
model files `code/presence_model_all_reg.txt` (rule) and `code/presence_model_activity_reg.txt`
(market-activity-only baseline). Features: `code/features.py` (`build_panel`). Nothing is fitted
inside `evaluate`; both models were trained once on BUILD (2026-10-09..16) and chosen on VALIDATE
(2026-10-16..23).

Scope: BTC 5m Up/Down windows (55% of the cluster's volume). The cluster = bosona, almach,
mo-money (one operator; fills pooled).

## What the cluster does (evidence: NOTES.md)

A top-of-book two-sided maker on the 0.01 grid. When a taker hits it, its bid is the best price
in the sweep 90% of the time and it is usually the only maker filled; 85% of its fills are mint
matches against takers buying the other outcome. Orders are mostly 500 shares (per-wallet size
signature 498 / 500 / 502), filled once and replaced. It quotes only inside the window (no fills
before the start, few in the last 30 s), skips high-volatility windows more often and has long
off periods (hours). Its quotes track the Binance 1-s fair value of the TWAP-60 settlement with no
lead over public data. Which side it ends up buying is mostly which of its two quotes is at the
top: the side where the spot fair value is above the last print (strongest in the first 30 s,
when the market has not yet absorbed the TWAP strike), and it keeps adding to the side it already
holds (not inventory balancing).

## The rule

1. Presence: for every (window, side s, 10-s bin starting at t in [0, 300) s), P(cluster maker BUY
   fill on s in [t, t+10)) = LightGBM(all_reg) on features published by t: time in window, side,
   Binance fair value of the TWAP-60 outcome (strike = TWAP of the 60 s before the start), z-score,
   1/2/3/5/10/30/60-s spot returns, 30-min realized vol, last taker print on s, fair - last print,
   number of prints, taker hits of s-bids and complement-bids and their volume in the last
   10/30/60 s, tape price change over 10/30/60 s. No own-state.
2. Side (given a bin where it fills exactly one side): the side with the higher predicted presence.
3. Price (given a fill at second T on side s): last taker print on s strictly before T, minus 0.01,
   rounded to 0.01.
4. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price).

## VALIDATE metrics (2016 windows, end-to-end through `evaluate`)

| metric | value | target |
| --- | --- | --- |
| presence AUC, no own-state (primary) | **0.772** | >= 0.85 |
| presence AUC, market-activity-only baseline | 0.732 | |
| presence AUC with own inventory (separate model, not the rule) | 0.823 | |
| presence AUC within windows where it is active | 0.743 | |
| side accuracy (3,805 one-sided fill bins) | 0.675 | >= 0.80 |
| side baseline: favourite by last print / Binance favourite | 0.515 / 0.545 | |
| side vs favourite, sign test on disagreements | p = 5e-45 | |
| price exact (0.001 tick) / within 0.01 | 0.210 / 0.529 | |
| per-window PnL correlation, Pearson / Spearman (1,086 windows) | 0.418 / 0.492 | >= 0.5 |
| selection AUC (match_test) | not run in iteration 1 | >= 0.80 |
| cluster's own BTC 5m maker return on VALIDATE | -2.5% (BUILD +4.1%) | |

Diagnostics (not part of the rule): with an oracle for which windows the cluster is switched on, the same
presence model would score 0.866; public pre-window features predict the on/off at AUC 0.54 only. A
separate selection pilot over taker prints (`code/selection.py`) reaches AUC 0.755 (recall 43% at lift 3.8;
0.703 without the print's own size); it is not yet the brief's match_test.

The high-accuracy target is not met.
