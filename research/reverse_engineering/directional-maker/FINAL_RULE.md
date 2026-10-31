# directional-maker: frozen rule R6 (iteration 8, kept unchanged in iterations 9 and 10)

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

**Iteration 10 change to the code (reporting only; no frozen decision changed):** `side_posture_match_clock` also reports `it10_by_order_class`: the per-fill posture and the sigma-free region-D accuracy split by the class of the filled order (calldata original size from Polygon RPC, at most `IT10_MAX_TX` = 3,000 transactions: 500 x 2^k = the US-session posture ladder; 62 / 250 = the off-session ladder; other; unjoined). The previous file is kept as `code10/final_rule_before_it10.py`. The class-conditional side rule itself failed its pre-registered VALIDATE test and is not part of R6.

**Universe (pre-registered iteration 8):** BTC 5m and BTC 15m Up/Down windows, the three wallets (bosona, almach,
mo-money) pooled with per-wallet metrics; a block in which BTC 5m is off is scored on BTC 15m. **Iteration 9 measured that
this universe fails the scope bar in most 6-hour blocks** (below).

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine runs three wallet processes: per-wallet sequential salt; the daily ~01:00 UTC restart resets all three counters within ~20 s; ~11-18 signed orders/s per wallet; until ~06-21 every order carried its real signing ms, since 06-22 `timestamp`, `metadata`, `builder` are 0. | VALIDATE-only | B1 calldata (lot, June, 10-31); `code9/m4_*.py` |
| Information | The ladders are re-priced on each Chainlink BTC/USD report (the settlement stream) within ~0-150 ms of the public RTDS relay's publish; between reports its 500s re-post 50-250 ms after Binance futures moves (June: signed 100-400 ms after Binance moves). No lead over public feeds. | VALIDATE-only | `code7/i2_publish.py`, `code8/june_lag.py` |
| Selection | One engine over crypto Up/Down. BTC 5m and 15m are modules switched off for hours, mostly from Friday-Sunday US-Eastern evenings to the next morning (calendar gate window AUC 0.68 for BTC 5m, 0.63 for 15m, since 10-16). The 10-31 16:53:54 UTC switch-off happened inside the running processes (salt counters continuous, signing rate unchanged) and two engines were restarted ad hoc 12-13 min later. R6's universe holds >= 80% of trades and dollars in only 34% of 6-h development blocks (0% in weekend 00-06 UTC blocks); only the all-crypto universe does in every block type. BTC 15m presence (R3 class) 0.812 vs 0.778 activity on VALIDATE. | hypothesis (on/off); VALIDATE-only (15m presence) | `code9/scope.py`, `code9/m4_salt.py`, `code8/train15.py` |
| Timing | Re-price passes on each Chainlink publish plus re-posts after Binance moves; filled orders are fresh 500-share posts at the touch (78%), matched ~0.7 s later; it stops ~30 s before the end; its filled rungs agree with the report in force at the match, not at the taker's signing (M5). July engine (pmxt): posts a median 69 ms after the market's previous trade, filled orders ~1.0 s old, 49% at the touch. | VALIDATE-only (live) | `code6/q1_confirmed.py`, `code7/i2_publish.py` |
| Side | **On the 10-31 12-18 development block it buys the outcome whose Chainlink edge over the Polymarket mid is positive** (Up iff the digital fair of Up from the report stamped floor((T - 1.432 s)/1 s), Gamma strike, 1.4 x 300-s realised vol, exceeds the Up mid of the latest book record; no fitted parameter): 0.786 per fill (n 2,244), 0.965 where the reference and the market disagree on the favourite (match ms and book mid, 14:06-16:30; 0.855 over 12-18 with the R6 inputs), 0.762 where they agree. **Iteration 10 (A1 + rung classes): it is the side rule of the US-session 500 ladder, and it replicates historically.** With pre-registered historical proxies (match clock = taker signing ms + 620 ms clipped to [block - 3 s, block - 1.5 s], the real Chainlink value from the crypto-price endpoint, the last clean print at block - 3 s) that reproduce the 10-31 truth (0.953 vs 0.965), the lot's 500-share rungs buy the Chainlink favourite where it disagrees with the market 0.933 (VALIDATE aggregate, 89 fills in 30 windows; 95% window bootstrap [0.84, 1.00]) and 0.770 (STUDY, 13 windows; [0.63, 0.97]); the off-session 62/250 rungs (62/250 are 57-81% of the fills in 00-06 and 06-12 UTC) do not (0.46-0.53) and follow no public candidate (cheaper side, favourite, Binance or Chainlink posture 0.48-0.51 on STUDY); where they coexist with 500s in a window they sit on the other outcome (71% of 163 VALIDATE pairs: the far-side rungs of the same ladder), so over all lot fills region D is only 0.66-0.68. The off-session ladder's entry fills (no inventory yet in the window) follow the Chainlink posture 0.66 (STUDY) / 0.72 (VALIDATE aggregate), like the 500 entries (0.68 / 0.75); after the entry its 250s keep adding to the held outcome (0.68-0.90, own state). On the fresh development block 10-31 00-06 (calldata of all 1,178 cluster orders; prediction written before the run) the 500s score 1.000 in that region (41 fills, 10 windows) and the 62s 0.448 (hour 00 UTC, a 62-share hour: 0.103), all fills 0.679; there the frozen posture itself (block clock, Binance 1-s vol from the REST klines) scores 0.799 on 500-class entries and 0.784 on later 500 fills (the live block's 0.785) but 0.444 on 62/250 fills. A class-conditional public rule failed its pre-registered VALIDATE test (0.660 vs 0.710, gain -0.049 [-0.085, -0.017]). Imbalance pairing bids (11-14% of lot fills) sit on the under-held outcome 100% (own state). Off-posture fills are not lost cancel races (posture at the taker's arrival 0.70-0.72 vs 0.74 at the match). Per wallet 0.79 / 0.81 / 0.76 live: mo-money's 500 rungs are off the posture already when posted (0.646 at the add; the TWAP-60 topic gives 0.608). A per-phase fair (slow sigma / TWAP lock-in) scores 0.835 vs 0.813 on 15-18 but is mostly the slow sigma, which fails its historical replications: secondary only. Market-only baselines <= 0.63. | VALIDATE-only (500 ladder: live 10-31 and historical VALIDATE region D); hypothesis (off-session 62/250 ladder: no decoded side) | `code8/fill_side.py`, `code9/vol_*.py`, `code10/a1_*.py`, `code10/m2_phase.py` |
| Price | Fill price = last clean print minus 0.01. Match clock (R4): 0.83-0.86 within a tick (anchor last print 0.82-0.86); block clock 0.709 (5m VALIDATE), 0.666 (15m), exam 0.688. This IS the trivial anchor "last print" on a fresh clock. The ladder hangs off each market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in 15m; top rung within a tick 26-30% vs 19% for a mid-minus-constant anchor). | exam-verified (block clock); VALIDATE-only (match clock) | `price_match_clock`, `code8/m1_invert.py`, `code9/m2_spread.py` |
| Size | October: schedule rungs 500 x 2^k with a one-fifth level (100 / 12 only at 30-120 s left); 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; plus **imbalance pairing bids** of exactly the own abs(Up - Down) shares (calldata original size within 2% of the imbalance; 11-14% of lot fills; not remainders). July (pmxt pilot, same engine family): 500 / 300 / 50 + pairing sizes; June: 50 / 100 / 300. | VALIDATE-only | `code6/m5_size.py`, `code10/m1_pair_lot.py`, `code10/pmxt_pilot.py` |
| Exit | Holds to resolution; completes pairs with maker pairing bids on the under-held outcome, priced at the market rather than off its own cost (pair cost median 0.91 STUDY / 0.81 VALIDATE, below 1 in only 61-72%), plus small complement taker buys; merges ~65 s before the end. Window PnL split (locked pairs vs directional residual): STUDY -$0.9k / +$5.7k, VALIDATE aggregate +$33.3k / -$10.3k: neither part is reliably the profit; the residual carries 58-69% of the window-to-window variance. | VALIDATE-only | `results/iter5_flatten.json`, `code10/m1_pair_lot.py` |

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
settlement source, the Chainlink BTC/USD report, re-priced the moment Polymarket's public relay publishes each report. It
completes pairs: every own fill that leaves a window unbalanced is followed by a maker bid for exactly the missing shares on
the other outcome. Its BTC 5m fills earn 2-4% of volume (BUILD +2.2% on $1.6M, VALIDATE +4.3%); maker and taker rebates and
rewards add about a fifth of net PnL ($23.0k of $111.7k over 10-08..30, measured by the assumptions panel; BUILD maker
rebates $14.5k against BTC 5m's $35k), and BTC 15m is near break-even before rebates (0.4% on $1.26M). Iteration 10 shows
that the profit cannot be pinned to one decision: the locked pairs earn -$0.9k on STUDY but +$33.3k on VALIDATE, the
directional residual +$5.7k vs -$10.3k. Who pays: takers who buy favourites through complement mints (88% of VALIDATE fills
are mints) fill its underdog bids, and in the 10-31 noise regime takers fill its Chainlink-skewed bids. The Chainlink skew
earned on the lot where the report and the market disagreed (+12.8% on those VALIDATE fills, block clock), and on the
historical VALIDATE its US-session 500 rungs follow the report where it disagrees with the market 93% of the time
(A1), while its off-session 62/250 ladder shows no skew; and in the noise regime of 10-31 the BTC 5m blocks lost 11.9%
and 3.9% before BTC 5m was switched off.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay, a CLOB connection that
re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs on both outcomes of several BTC
5m and 15m windows (a working capital of ~$22-24k per wallet, reset by a weekly Monday sweep at the 01:00 UTC restart and growing to $43-49k by the end of the week; no deposits in 10-09..30), and unchanged fees (0.07 taker), listings and matching. A home
connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the slower makers this strategy
profits from: expect zero or a loss without low latency. In the new Chainlink noise regime the strategy itself lost money
on BTC 5m (10-31), and its operator switched BTC 5m off and restarted two of the three engines.

## Open leads (not part of the frozen rule)

- A1 follow-up: what sets the side on the lot where Chainlink and the market disagree (0.66-0.70 on the Chainlink side;
  neither Binance nor the market favourite explains it); a per-window regime test against the Chainlink 1-s noise (noise
  runs for every hour of 10-31 00-06 and the lot's fill stamps are being fetched by a detached job to 11-01 10:00 UTC).
- Slow vs fast volatility and the per-phase fair: pre-registered for 11-01 06-12 and the 11-02 12-18 regime change.
- The quote unit as the primary unit for the next exam: examinable for BTC 5m/15m from the own exam recorder dx_clob
  (recall 1.00 vs the raw label) to 11-03 00:00 UTC, and for the other 5m/15m crypto families from the new dw_clob
  recorder (from 10-31 22:59 UTC); the shared recorder cannot label it (recall 0.01-0.02).
- The pmxt archive (07-16..08-10, unaggregated book with server ms and tx hashes for every family): the same engine
  family with another configuration, for the ladder state machine, the queue and the strict-fill replay (X64).
- Clock conventions across the US DST change (pre-registered, X99); module switches against public data-quality triggers
  (pre-registered, X89).
- Mo-money's 500-rung input (X91 / X94): neither a Chainlink delay, a Binance blend nor the TWAP-60 topic.
