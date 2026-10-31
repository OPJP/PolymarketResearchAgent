# directional-maker: frozen rule R6 (iteration 8, kept unchanged in iteration 9)

Rule id: **R6** = R5 on BTC 5m (R3 presence stacked with the Chainlink settlement stream, R4 match-clock price) + **BTC 15m
in the universe** (R3's model class refitted on BTC 15m) + **the fill side scored per fill with the decoded quote-side
rule** (sign of the Chainlink edge over the Polymarket mid at the match ms). Code: `code/final_rule.py`
(`evaluate(start_ts, end_ts, intervals=None)`, pooled and per wallet, per family and over the union). R5 is archived as
`code/final_rule_r5.py`, R2 as `code/final_rule_r2.py`. Frozen model files: `presence3_rule.txt` / `presence3_activity.txt`
/ `presence3_own.txt` (BTC 5m), `presence15_rule.txt` / `presence15_activity.txt` (BTC 15m), `selection2_*.txt` with
`THETA_SEL` (BTC 5m). Feature code: `features2.py` (5m), `features15.py` (15m). Live inputs (the shared recorder's
`clob_crypto` trades `x` and books `q`, the Chainlink recordings dy_rtds / dx_rtds / dm_rtds) are read with tolerant
readers that honour `ALLOW_SEALED` (False except in the examiner's driver); Chainlink values missing from the recordings
come from Polymarket's `crypto-price` endpoint when `FETCH_CL` (`code/cl_source.py`). Binance 1-s seconds come from the
daily archive, with a REST 1-s kline fallback for days not yet archived.

**Iteration 9 change to the code (reporting only; no frozen decision changed):** `side_posture_match_clock` now also reports
the pre-registered secondary variant with a slow sigma (`it9_slow_sigma_v3600`: 3,600-s realised vol, k 1), the split by
vol regime (`it9_by_regime`), per half (`it9_halves`) and per taker event with the own-history baseline "side of the
previous event" (`it9_taker_events`, own state, reported separately). Smoke-tested on 10-31 15:20-16:20 (development):
frozen 0.850 per fill, slow 0.850, per event 0.828 / 0.830 vs own-history 0.859.

**Universe (pre-registered iteration 8):** BTC 5m and BTC 15m Up/Down windows, the three wallets (bosona, almach,
mo-money) pooled with per-wallet metrics; a block in which BTC 5m is off is scored on BTC 15m. **Iteration 9 measured that
this universe fails the scope bar in most 6-hour blocks** (below).

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine runs three wallet processes: per-wallet sequential salt; the daily ~01:00 UTC restart resets all three counters within ~20 s; ~11-18 signed orders/s per wallet; until ~06-21 every order carried its real signing ms, since 06-22 `timestamp`, `metadata`, `builder` are 0. | VALIDATE-only | B1 calldata (lot, June, 10-31); `code9/m4_*.py` |
| Information | The ladders are re-priced on each Chainlink BTC/USD report (the settlement stream) within ~0-150 ms of the public RTDS relay's publish; between reports its 500s re-post 50-250 ms after Binance futures moves (June: signed 100-400 ms after Binance moves). No lead over public feeds. | VALIDATE-only | `code7/i2_publish.py`, `code8/june_lag.py` |
| Selection | One engine over crypto Up/Down. BTC 5m and 15m are modules switched off for hours, mostly from Friday-Sunday US-Eastern evenings to the next morning (calendar gate window AUC 0.68 for BTC 5m, 0.63 for 15m, since 10-16). The 10-31 16:53:54 UTC switch-off happened inside the running processes (salt counters continuous, signing rate unchanged) and two engines were restarted ad hoc 12-13 min later. R6's universe holds >= 80% of trades and dollars in only 34% of 6-h development blocks (0% in weekend 00-06 UTC blocks); only the all-crypto universe does in every block type. BTC 15m presence (R3 class) 0.812 vs 0.778 activity on VALIDATE. | hypothesis (on/off); VALIDATE-only (15m presence) | `code9/scope.py`, `code9/m4_salt.py`, `code8/train15.py` |
| Timing | Re-price passes on each Chainlink publish plus re-posts after Binance moves; filled orders are fresh 500-share posts at the touch (78%), matched ~0.7 s later; it stops ~30 s before the end. | VALIDATE-only (live) | `code6/q1_confirmed.py`, `code7/i2_publish.py` |
| Side | **It buys the outcome whose Chainlink edge over the Polymarket mid is positive** (Up iff the digital fair of Up from the report stamped floor((T - 1.432 s)/1 s), Gamma strike, 1.4 x 300-s realised vol, exceeds the Up mid of the latest book record; no fitted parameter). 10-31 development block on the match clock: 0.786 per fill (n 2,244): **0.855 where the reference and the market disagree on the favourite** (a volatility-free information part, 26% of fills) and 0.762 where they agree (the choice is then a volatility comparison: buy the favourite iff the engine's sigma is below the market-implied one). Per taker event 0.78 against an own-history baseline "side of the previous event" of 0.865 (own state). Per wallet 0.79 / 0.81 / 0.76: the deficit is one rung type in one wallet (mo-money's 500s score 0.72-0.76 at every reference delay and are off the posture already when posted; its other sizes score 0.85, like the other wallets' 500s). Unexamined families (ETH/SOL 5m-15m, BTC 4h; 36 fills, 10 windows) 0.75. Market-only baselines <= 0.63. Historical block clock 0.60-0.65 for 5m and 0.80 for 15m on VALIDATE (88% of the VALIDATE fills are complement mints landing 69% on the underdog: the takers' choice of token shapes the historical side). A slow (~1-h) sigma raises the live per-fill score to 0.83 and the 15m quote level (0.775 vs 0.724), but fails both pre-registered historical replications (5m VALIDATE 0.569 vs 0.645; 15m 0.750 vs 0.799) and does not help the 5m quote level (0.732 vs 0.748): not adopted; it is reported by `evaluate()` as the pre-registered secondary. | VALIDATE-only (live; replication on 11-01 06-12 pre-registered) | `code8/fill_side.py`, `code9/vol_*.py`, `code9/quote_slow.py`, `code9/posture_xfam.py` |
| Price | Fill price = last clean print minus 0.01. Match clock (R4): 0.83-0.86 within a tick (anchor last print 0.82-0.86); block clock 0.709 (5m VALIDATE), 0.666 (15m), exam 0.688. This IS the trivial anchor "last print" on a fresh clock. The ladder hangs off each market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in 15m; top rung within a tick 26-30% vs 19% for a mid-minus-constant anchor). | exam-verified (block clock); VALIDATE-only (match clock) | `price_match_clock`, `code8/m1_invert.py`, `code9/m2_spread.py` |
| Size | October: 500 x 2^k with a one-fifth level; 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; June: 50 / 100 / 300; remainders re-posted. | VALIDATE-only | `code6/m5_size.py`, June calldata |
| Exit | Holds to resolution; small complement taker buys sized to the imbalance and merges (2-4% of PnL). | VALIDATE-only | `results/iter5_flatten.json` |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints; for live inputs, every trade record whose transaction holds a cluster trade.
2. Presence, BTC 5m (R3): P(cluster maker BUY fill on s in [t, t+10)), t in [0, 300) = `presence3_rule.txt` on features
   published by t (time, side, clean-tape activity, Binance 1-s TWAP-60 fair, z, returns, realised vol, edge, window path,
   previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag). No own state. R5's Chainlink stack
   where the series exists (`code/r5.py`).
3. Presence, BTC 15m: the same feature definitions on bins t in [0, 900) (`features15.py`) scored by `presence15_rule.txt`.
4. Side: per fill on the match clock (where the shared recorder has the fill's transaction): Up iff fair_CL(Up) > Up mid
   (`side_posture_match_clock`); per bin (historical, block clock): the side with the higher predicted presence.
5. Price: match clock where recorded (last clean trade of the market before the match ms, mapped to the fill's token,
   minus 0.01), else the last clean data-api print on s before the fill second minus 0.01; 0.01 grid.
6. Selection: R2's print score (BTC 5m only), flagged at `THETA_SEL`.
7. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price) (an expectation proxy; the strict-fill
   replay the target asks for is not built yet, X64).

## Metrics

Historical VALIDATE (2026-10-27..30; aggregate only), union BTC 5m + 15m (`code8/union_val.py`):

| metric | R6 union | BTC 5m (R3/R5) | BTC 15m | target |
| --- | --- | --- | --- | --- |
| presence AUC, no own state | 0.788 | **0.716** (primary, pre-registered) | 0.812 | >= 0.85 |
| market-activity baseline (gain) | 0.780 (+0.009, 2-h bootstrap [+0.003, +0.016]) | 0.684 (+0.032) | 0.778 (+0.034) | gain >= 0.05 |
| side, bin level | 0.672 (activity 0.613) | 0.663 | 0.733 | >= 0.80 |
| price within a tick, block clock | 0.705 | 0.709 | 0.666 | >= 0.80 |
| per-window PnL corr (expectation) | 0.260 / 0.327 | 0.329 / 0.325 | 0.180 / 0.345 | >= 0.5 |
| selection AUC / recall / lift (5m only) | | 0.685 / 29.5% / 2.87 | | 0.80 / 50% / 3 |
| coverage fills / abs PnL (VALIDATE aggregate) | 0.868 / 0.891 | 0.783 / 0.686 | | 0.80 / 0.80 |

Scope per 6-hour block (iteration 9, every development block 10-08..10-31): R6's universe meets 0.80 of trades and dollars
in 34% of blocks; + BTC 4h 45%; + BTC hourly/daily 62%; + ETH 89%; every crypto Up/Down family 100%.

Live (development block 10-31 12:00-18:00 UTC, match clock, through `evaluate()` and `code9/vol_live.py`): per-fill side
0.786 (15:00-16:30 0.836, the pre-registered live VALIDATE), match-clock price 0.82-0.86, 5m presence 0.71 vs 0.66-0.68
activity, union presence 0.775 vs 0.750.

Quantitative account of what is still unexplained:
- 10-s fill presence is taker-bound: with the cluster's actual quote as an oracle it reaches only 0.80 (public inputs
  0.66, activity 0.62), so the presence bar (0.85) cannot be reached on fills by any quote decoder on this unit; at the
  print level the quote is binding (oracle 0.81-0.83, recall 62-69% at lift 3.3-3.4) and public quote prediction is
  0.748 (activity 0.672).
- Side: 21% of fills go against the posture. Of the fills, about a third have a >= 500 touch only on the bought outcome
  (posture 0.87-0.89 there), a sixth have cluster-class touches on both outcomes (the taker chooses; 0.83), the rest have
  neither visible (0.71-0.79); small-edge fills follow the previous event's side (0.91), not the edge (0.45); whole windows
  fail in volatility bursts, where the fills land on the favourite's 500s while the 500 re-posts sit at the underdog's touch.
- Selection: the module on/off schedule is partly a calendar (weekend nights ET) and partly ad hoc (the 10-31 12:53 ET
  switch-off and the restarts after it); its trigger is not decoded.

## Why it works

It is a two-sided liquidity provider whose ladders hang off each market's Polymarket mid and are skewed toward the
settlement source itself, the Chainlink BTC/USD report, re-priced the moment Polymarket's public relay publishes each
report; no other maker re-prices on the report. Its BTC 5m profit (BUILD +2.2% on $1.6M of fills, VALIDATE +4.3%) has two
sources. (1) The information part: when the latest Chainlink report and the market disagree on the favourite, it buys the
report's side (+4.4% BUILD, +23% STUDY, +12.8% VALIDATE on those fills). (2) The cheap side: when they agree, most of the
money is in underdog fills (BUILD +12.1% on 13% of the dollars = 73% of all PnL; VALIDATE +7.4%), i.e. it is short the
favourite that takers buy; 88% of its fills are complement mints, so its underdog bids fill when takers buy the
favourite at the ask. It is not paid for liquidity rewards ($3 in two weeks of BUILD) and only a little for maker rebates
($14.5k over BUILD; its fills are 1.7% of BTC 5m volume, more in busier windows). The skew has a cost when the Chainlink
report itself is noisy (since 10-31, 1-s white noise of ~$9): the BTC 5m blocks of 10-31 lost 11.9% and 3.9% before BTC
5m was switched off.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay, a CLOB connection that
re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs on both outcomes of several BTC
5m and 15m windows (~$45-56k of collateral per wallet), and unchanged fees (0.07 taker), listings and matching. A home
connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the slower makers this strategy
profits from: expect zero or a loss without low latency. In the new Chainlink noise regime the strategy itself lost money
on BTC 5m (10-31), and its operator switched BTC 5m off and restarted two of the three engines.

## Open leads (not part of the frozen rule)

- Slow vs fast volatility in the posture: pre-registered for 11-01 06-12 and the 11-02 12-18 regime change (the slow
  variant is reported by `evaluate()`).
- The all-crypto universe for scope: per-family presence and the module calendar gate (X83), the binding condition for
  any weekend exam block.
- Mo-money's clock (X76): per-wallet burst hazard after each publish on the 11-01 full-depth book.
- The ladder level as a state machine (X71): the fast re-posts step 3-4 c toward the touch; the half-spread rule explains
  R^2 0.47 only.
