# directional-maker: frozen rule R7 (iteration 11 = R6 of iteration 8 + a recording-free price clock)

**Iteration 11 change (one frozen decision changed, pre-registered 00:43 UTC 11-01, adopted on VALIDATE): R7-price.** The
price rule is unchanged ("the last clean trade of the market before the fill, minus 0.01"), but "before" is now measured on
the best available clock: the shared recorder's server match ms where it has the fill's trade (R4), otherwise **the on-chain
execution order inside the fill's block** (`eth_getBlockByNumber(block, false)` lists the block's transactions in order; the
anchor is the last clean transaction of the same market earlier in the block, else the last clean print stamped before the
block second; a multi-row clean transaction is priced at its taker's worst price). Code: `code/inblock_price.py`; reported by
`evaluate()` as `price_inblock`, `price_r7` (5m) and `union_btc5m_15m.price_within_0.01_r7` / `price_within_0.01_inblock`.
Point-in-time note: the earlier transaction was matched, and broadcast on the CLOB market channel, before the fill's match;
under the brief's block-stamp convention for tape prints it would count as published at the block time, so the block clock
(`price`) is still reported beside it. Everything else in R6 is unchanged; the previous file is `code10/final_rule_before_it10.py`
plus the iteration-10 diagnostics (no other decision changed in iterations 9-11).

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
| Side | **On the 10-31 12-18 development block it buys the outcome whose Chainlink edge over the Polymarket mid is positive** (Up iff the digital fair of Up from the report stamped floor((T - 1.432 s)/1 s), Gamma strike, 1.4 x 300-s realised vol, exceeds the Up mid of the latest book record; no fitted parameter): 0.786 per fill (n 2,244), 0.965 where the reference and the market disagree on the favourite (match ms and book mid, 14:06-16:30; 0.855 over 12-18 with the R6 inputs), 0.762 where they agree. **Iteration 10 (A1 + rung classes): it is the side rule of the US-session 500 ladder, and it replicates historically.** With pre-registered historical proxies (match clock = taker signing ms + 620 ms clipped to [block - 3 s, block - 1.5 s], the real Chainlink value from the crypto-price endpoint, the last clean print at block - 3 s) that reproduce the 10-31 truth (0.953 vs 0.965), the lot's 500-share rungs buy the Chainlink favourite where it disagrees with the market 0.933 (VALIDATE aggregate, 89 fills in 30 windows; 95% window bootstrap [0.84, 1.00]) and 0.770 (STUDY, 13 windows; [0.63, 0.97]); the off-session 62/250 rungs (62/250 are 57-81% of the fills in 00-06 and 06-12 UTC) do not (0.46-0.53) and follow no public candidate (cheaper side, favourite, Binance or Chainlink posture 0.48-0.51 on STUDY); where they coexist with 500s in a window they sit on the other outcome (71% of 163 VALIDATE pairs: the far-side rungs of the same ladder), so over all lot fills region D is only 0.66-0.68. The off-session ladder's entry fills (no inventory yet in the window) follow the Chainlink posture 0.66 (STUDY) / 0.72 (VALIDATE aggregate), like the 500 entries (0.68 / 0.75); after the entry its 250s keep adding to the held outcome (0.68-0.90, own state). On the fresh development block 10-31 00-06 (calldata of all 1,178 cluster orders; prediction written before the run) the 500s score 1.000 in that region (41 fills, 10 windows) and the 62s 0.448 (hour 00 UTC, a 62-share hour: 0.103), all fills 0.679; there the frozen posture itself (block clock, Binance 1-s vol from the REST klines) scores 0.799 on 500-class entries and 0.784 on later 500 fills (the live block's 0.785) but 0.444 on 62/250 fills. A class-conditional public rule failed its pre-registered VALIDATE test (0.660 vs 0.710, gain -0.049 [-0.085, -0.017]). Imbalance pairing bids (11-14% of lot fills) sit on the under-held outcome 100% (own state). Off-posture fills are not lost cancel races (posture at the taker's arrival 0.70-0.72 vs 0.74 at the match). Per wallet 0.79 / 0.81 / 0.76 live: mo-money's 500 rungs are off the posture already when posted (0.646 at the add; the TWAP-60 topic gives 0.608). A per-phase fair (slow sigma / TWAP lock-in) scores 0.835 vs 0.813 on 15-18 but is mostly the slow sigma, which fails its historical replications: secondary only. Market-only baselines <= 0.63. **Iteration 11:** the posture's volatility multiplier follows a weekly cycle (best k ~1.4-2.5 after the Monday 01:00 UTC restart, decaying to 0.5-0.85 by Fri-Sun in 10-09..25; no decay in week 3, 10-26..31) while the market prices with ~1.15 x v300 throughout; the frozen k = 1.4 is a week-3 value. Per window the first fill sets the net side (0.81-0.90); posture at the entry 0.744 (VALIDATE), 0.82 where it agrees with the market-only taker-flow complement (53% of windows). | VALIDATE-only (500 ladder: live 10-31 and historical VALIDATE region D); hypothesis (off-session 62/250 ladder: no decoded side; the weekly cycle's driver) | `code8/fill_side.py`, `code9/vol_*.py`, `code10/a1_*.py`, `code10/m2_phase.py` |
| Price | Fill price = last clean trade before the fill minus 0.01. **In-block execution-order clock (R7, recording-free): 0.807 on all 27,988 VALIDATE BTC 5m maker fills (block clock 0.709; gain +0.098, 2-h block bootstrap [+0.084, +0.111]; per wallet 0.800 / 0.805 / 0.814; halves 0.806 / 0.807), 0.766 on BTC 15m (block 0.666), pooled 0.803 (block 0.705); STUDY 0.751 / 0.730.** Trivial anchor 'last print' with no offset on the same clock 0.773. Live match clock (R4): 0.83-0.86 (10-31 15:40-16:40: block 0.625, in-block 0.719, match 0.849, R7 combined 0.843): the in-block order recovers part of the match-clock gain on busy hours. Block clock exam 0.688. This IS the trivial anchor "last print" minus a tick on a fresh clock. The ladder hangs off each market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in 15m; top rung within a tick 26-30% vs 19% for a mid-minus-constant anchor). | exam-verified (block clock); VALIDATE-only (in-block clock, match clock) | `price_inblock`, `price_r7`, `price_match_clock`, `code11/inblock_*.py`, `code8/m1_invert.py` |
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
5. Price (R7): the last clean trade of the market before the fill, mapped to the fill's token, minus 0.01 (0.01 grid),
   with "before" on the live match clock where the shared recorder has the trade, else on the in-block execution order
   (`code/inblock_price.py`), else on the block clock (the last clean print before the fill second).
6. Selection: R2's print score (BTC 5m only), flagged at `THETA_SEL`.
7. Rule PnL per window: evaluate() still reports the expectation proxy (sum over bins and sides of P(fill) x (payout_s -
   rule price)). The executable version (iteration 11, `code11/replay.py` / `replay_frozen.py`): quote the posture side
   at last print - 0.01, session size (500 in the weekday 12-21 UTC session, else 62), from the open to 30 s before the end,
   strict fills (trade-through, latency 2 s, slack 2) on the public taker tape; its per-window PnL is the target's outcome
   metric and is reported in state.json target_metrics.

## Metrics

Historical VALIDATE (2026-10-27..30; aggregate only), union BTC 5m + 15m (`code8/union_val.py`):

| metric | R6 union | BTC 5m (R3/R5) | BTC 15m | target |
| --- | --- | --- | --- | --- |
| presence AUC, no own state | 0.788 | **0.716** (primary, pre-registered) | 0.812 | >= 0.85 |
| market-activity baseline (gain) | 0.780 (+0.009, 2-h bootstrap [+0.003, +0.016]) | 0.684 (+0.032) | 0.778 (+0.034) | gain >= 0.05 |
| side, bin level | 0.672 (activity 0.613) | 0.663 | 0.733 | >= 0.80 |
| price within a tick, in-block clock (R7) | **0.803** | **0.807** (all 27,988 fills) | 0.766 | >= 0.80 |
| price within a tick, block clock | 0.705 | 0.709 | 0.666 | |
| per-window PnL corr, strict-fill replay of the quote (target definition) | | **0.207 / 0.218** (1,089 windows; STUDY 0.033 / 0.070) | | >= 0.5 |
| same, oracle window side (ceiling of a strict replay) | | 0.473 / 0.527 (STUDY 0.505 / 0.637) | | |
| per-window PnL corr (expectation proxy) | 0.260 / 0.327 | 0.329 / 0.325 | 0.180 / 0.345 | |
| selection AUC / recall / lift (5m only) | | 0.685 / 29.5% / 2.87 | | 0.80 / 50% / 3 |
| coverage fills / abs PnL (VALIDATE aggregate) | 0.868 / 0.891 | 0.783 / 0.686 | | 0.80 / 0.80 |

Scope per 6-hour block (iteration 9, every development block 10-08..10-31): R6's universe meets 0.80 of trades and dollars
in 34% of blocks; + BTC 4h 45%; + BTC hourly/daily 62%; + ETH 89%; every crypto Up/Down family 100%.

Live (development block 10-31 12:00-18:00 UTC, match clock, through `evaluate()` and `code9/vol_live.py`): per-fill side
0.786 (15:00-16:30 0.836, the pre-registered live VALIDATE), match-clock price 0.82-0.86, 5m presence 0.71 vs 0.66-0.68
activity, union presence 0.775 vs 0.750.

Quantitative account of what is still unexplained:
- Outcome (iteration 11, the window as the unit): a strict-fill replay of the decoded quote (posture side, last print -
  0.01, session size) tracks the cluster's window PnL at 0.21 / 0.22 on VALIDATE; with an ORACLE window side (the
  cluster's own terminal net side) the same replay reaches only 0.47 / 0.53 (STUDY 0.51 / 0.64). Under the examiner's
  strict-fill conventions the outcome bar sits at the ceiling of a perfect window side: the cluster's window PnL is made of
  touch fills of quotes refreshed within ~0.1-1 s, which a 2-s-latency trade-through replay on block-stamped prints cannot
  be credited with (its fills are the adverse trade-throughs; every strict replay loses 5-21% of notional). Per window the
  first fill sets the net side (0.81-0.90); the net side won 62% on STUDY (favourite) and 33% on VALIDATE (underdog); the
  favourite share of fills drifts 0.59 -> 0.25 across 10-23..30 while 81-88% of fills are complementary mints (the fill
  side follows what the takers buy); no public window rule reaches 0.80 (best 0.63).
- 10-s fill presence is taker-bound: with the cluster's actual quote as an oracle it reaches only 0.80 (public inputs
  0.66, activity 0.62), so the presence bar (0.85) cannot be reached on fills by any quote decoder on this unit; at the
  print level the quote is binding (oracle 0.81-0.83, recall 62-69% at lift 3.3-3.4) and public quote prediction is
  0.748 (activity 0.672).
- Side: 21% of fills go against the posture. Of the fills, about a third have a >= 500 touch only on the bought outcome
  (posture 0.87-0.89 there), a sixth have cluster-class touches on both outcomes (the taker chooses; 0.83), the rest have
  neither visible (0.71-0.79); small-edge fills follow the previous event's side (0.91), not the edge (0.45); whole windows
  fail in volatility bursts, where the fills land on the favourite's 500s while the 500 re-posts sit at the underdog's touch.
- Side, iteration 11 (version change): the posture's effective volatility multiplier stepped over the 10-24/25 weekend.
  Per 6-h block the best k (sigma = k x v300, real Chainlink) is 0.5-1.2 up to 10-26 06:00 UTC and 1.4-2.5 from 10-26 12:00
  (Friday 10-23 12-18, 81% 500s: best k 0.5, frozen 1.4 scores 0.50; Monday 10-26 12-18, 77% 500s: best k 1.7), while the
  market prices the same digital with ~1.15 x v300 in every block. Before the step the engine's fair was more extreme than
  the market's (it bought favourites, the net residual won 62% of windows); after it, less extreme (underdogs, 33%). The
  same takers filled it on the other side after the step and the market's taker demand did not move (0.46-0.51 favourite
  buys every day). R7's k = 1.4 is a post-step value; the STUDY half of the lot belongs to the older configuration.
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
and 3.9% before BTC 5m was switched off. Iteration 11 adds the execution side of the economics: the same quote replayed
with a 2-s latency under strict (trade-through) fills loses 15-17% of notional on the lot and tracks the cluster's window
PnL at only 0.21 / 0.22. What the cluster is paid for is being first at the touch with a quote refreshed within ~0.1-1 s of
the last trade and of each Chainlink report: the takers who buy one outcome (88% of its VALIDATE fills are complementary
mints) fill its bid on the other at the touch; a slower copy only gets the trade-throughs, which are the adverse moves.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay, a CLOB connection that
re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs on both outcomes of several BTC
5m and 15m windows (a working capital of ~$22-24k per wallet, reset by a weekly Monday sweep at the 01:00 UTC restart and growing to $43-49k by the end of the week; no deposits in 10-09..30), and unchanged fees (0.07 taker), listings and matching. A home
connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the slower makers this strategy
profits from: expect zero or a loss without low latency. In the new Chainlink noise regime the strategy itself lost money
on BTC 5m (10-31), and its operator switched BTC 5m off and restarted two of the three engines.

## Open leads (not part of the frozen rule)

- X102 (information panel I10-2): print-level selection with the settlement-grade reference on the lot. A pre-registered
  queue (`code11/queue_x102.py`: consecutive window pairs i = 0, 16, ..., 272 of every lot day, every even second of
  [S - 65, S + 300), 26,352 requests) is fetched by `code11/fetch_cl_x102.py`, which waits for the iteration-10 fetch to
  finish and stops at 11-01 22:00 UTC.
- The window state machine with a fast clock: the strict replay is capped by its 4-5 s information lag; a replay on a
  historical match clock (taker signing ms of every print, all-match calldata) would measure how much of the window PnL a
  fast executable copy of the quote reproduces.
- The favourite-share drift (0.59 -> 0.25 across the lot) and who the minting takers are (X104, X111).

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
