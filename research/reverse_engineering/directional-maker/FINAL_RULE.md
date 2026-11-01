# directional-maker: frozen rule R8 (iteration 12 = R7 + the window state-machine side; iterations 13-14: unchanged, reporting blocks added)

**Iteration 14 (pivot: the uncensored quote unit and event time; no frozen decision changed; R8 stays; two reported
blocks added: `quote_unit_side` and `quote_presence_event_time`).** `evaluate()` now also reports the side of the
uncensored quote: every 500 / 1000 post at the touch of a BTC 5m / 15m window in the exam recorder dx_clob, scored
against the posture computed AT THE POST from the latest Chainlink report PUBLISHED before it (the streaming recorder's
publish ms where it exists, else the point-in-time-safe stamp lag 1,432 ms; priceToBeat; sigma = 1.0 x the 300-s Binance
USD-M mid sigma; `code14/qu_dx.py`), and the event-time presence of those posts per (window, outcome, second) from
frozen LightGBM models fitted on 10-31 14-16 with point-in-time-safe inputs (`code14/x160_block.py`,
`code14/models/quote_presence_*.txt`; rule vs the activity-only model of the same class). Tag: VALIDATE-only (one
block). These describe the decoded quote, not fills; the per-fill metrics are unchanged.
What iteration 14 established (details in NOTES, results/iter14_*.json):
- **Side of the uncensored quote (VALIDATE-only, one block):** at-touch 500/1000 posts follow the posture from the latest
  published report at **0.831** on the 585 posts with exact publish times (17:29-18:00 on the full-depth book; every fixed
  stamp lag scores 0.78-0.79 on the same posts), and at 0.75-0.76 with the point-in-time-safe fixed lag on 14-18
  (baselines: always-Up 0.51, cheaper 0.44, "the outcome whose mid rose over 1 s" 0.65). A 1.0-s stamp lag gives 0.815 /
  0.811 but can use a report up to ~0.5 s before its public publish (publish delay q10 0.79 s, median 1.09 s, q90 1.47 s),
  so it is not counted. The exam-recorder form is noisier (0.742 on 15:53-18:00; its touch comes only with schedule-size
  deltas). The 62/250 posts at the touch are at chance (0.51, n 521). Own inventory does not set the quote's side.
- **The fills are a selected subset of the quote:** per filled order the match-clock posture keeps its R8 form (0.855 /
  0.815) and is higher than on the quote unit because the takers fill the posture-side posts. The "fell" law of the
  mechanics panel (class-(i) fills on the outcome that fell 0.90-1.00) is reversed on unfilled posts (the engine re-posts
  at the touch on the outcome that ROSE after a futures move, 0.72-0.82): fill selection, not the engine's rule. A
  futures two-regime rule adds <= +0.01 per fill; the class-(ii) volatility scale is not identifiable out of sample.
- **Presence at event time:** (window, outcome, 1-s) fill presence 0.805 vs activity 0.774 (gain +0.031): the gain is the
  same as on 10-s bins. **Quote presence** on the same panel (label: an at-touch 500/1000 post on the outcome in the
  second; the brief's "order resting" unit) with point-in-time-safe inputs: 0.701 vs activity 0.672 (Chainlink-only
  0.717): gain +0.029 / +0.045, the same as fills. (A first run with a 1.0-s stamp lag showed +0.090; that lag reads the
  report published inside the label second, so it was look-ahead and is withdrawn.)
- **Selection by quote geometry:** fixed score 0.558; activity + posture + price geometry 0.742 (recall 0.42 at lift 3).
- **Order life cycle in the replay:** one taker batch per order raises a strict replay's return by 5-7 points (VALIDATE
  -16.6% -> -10.7%) but not its window correlation (0.213 / 0.214; oracle ceiling 0.47-0.53).
- **Selection (own state, reported):** BTC 5m switch-offs follow drawdowns since the 01:00 restart (AUC 0.82-0.93, 7
  events) at no fixed level ($1.1k-$14.6k), plus scheduled-looking switch-offs at ~18:15-18:30 ET on weekend evenings.
- **Scope on the exam lot:** on the latest weekend analogs (10-24/25) R8's universe holds 0.00-0.72 of trades and dollars;
  with BTC 5m/15m off the cluster runs small non-schedule orders on BTC 4h/hourly/daily, ETH and XRP. Only a universe of
  every crypto Up/Down family (1.00) meets the scope bar on those blocks; R9 (X161) is not built yet. Operational event:
  no BTC/ETH 5m-15m windows were listed for 11-01 ~05:00-06:59 UTC (the US DST fall-back hour).
- **Who paid:** in September (+8.3% per $) the profit was spread over all taker populations; in October (+0.6%) the
  top-20 September counterparties' share of its fills fell 63% and its fills against round-USD retail moved from the
  cheaper token (0.70) to the favourite (0.49) and lost 11%.
- **Data:** GMX v2 on Arbitrum (arb1.arbitrum.io) emits the Chainlink Data Streams BTC value on chain, equal to the RTDS
  value to the cent, but only ~3 BTC stamps per 10 minutes.

**Iteration 13 (no frozen decision changed; R8 stays; one reporting block added).** `code/side_sm.py` now also reports the
side per burst start (`side_state_machine.per_burst_start`, all starts and starts after a gap of >= 30 s; burst =
consecutive cluster fills of one window on one outcome with block-second gaps < 3 s). Smoke test through `evaluate()` on
the historical VALIDATE hour 10-29 12-13 reproduces iteration 12 (680 fills, public 0.678, own-state composite 0.825) and
adds 121 burst starts (public 0.628, composite 0.785, previous-fill baseline 0.669; gap >= 30 s: 0.634 / 0.756 / 0.610).
Lot per burst start (`code13/burst_side_lot.py`): public 0.539 STUDY / 0.637 VALIDATE (per fill 0.569 / 0.693), cheaper
0.434 / 0.602, previous fill 0.735 / 0.712; after a gap >= 30 s: public 0.512 / 0.587 vs previous fill 0.534 / 0.522;
window first bursts (entries) 0.619 / 0.725.
What iteration 13 established about the components (details in NOTES, results/iter13_*.json):
- **Side, decomposed on the exact live clock (10-31 14-18, VALIDATE-only):** 73% of fills are class (i), an order the
  cluster posted at or above the touch a median 0.9 s before the fill, and 27% are class (ii), a resting order 2 c below
  the touch that the market came down to. The Chainlink posture at the POST time decodes the class-(i) quote moves (0.81;
  0.84 out of sample after 16:00) and is at chance on class (ii) (0.51), whose side follows the book's lean (book-only
  0.72). Run switches are quote moves too (71%). The public side gap is therefore (a) the class-(ii) fills, which are the
  takers' choice of which resting ladder to sweep, and (b) the block clock, which cannot see the post time.
- **Version shift (VALIDATE-only, pre-registered stable sample 09-11..10-11):** in the most profitable stable weeks the
  frozen functions decode less, not more: per-fill side 0.525 (09-11..25) with the cheaper token at 0.709, posture at
  chance; presence gain over activity +0.020-0.022. The posture side rises week by week into October (0.475 -> 0.672)
  while the return falls (11.2% -> -6.7% per $ on the sampled hours). The posture-skewed engine is the October
  configuration, not the strategy's steady state.
  Refitted on the panel's stable BUILD fold (08-14..09-10), the R3 class gains only +0.026 / +0.027 over activity on
  STUDY-/VALIDATE-stable (0.721 / 0.731): the fill-level presence gap is intrinsic to this maker, not an October effect.
- **Withdrawal (identified by the settlement switches, VALIDATE-only):** the cluster's last fill per window comes a
  median 45 / 71.5 / 101 s before the end under spot / TWAP-30 / TWAP-60 settlement (07-31..08-20; 98.5 s in October),
  about 43 s plus `twapLookbackSeconds`, adopted within 1-3 days of each listing change; the market keeps printing to
  1-3 s before the end.
- **Price of the pairing bid (not decoded):** the imbalance bids rest a median 11 c below the touch (at or above it in
  10% of re-signs), track the latest public Chainlink report (stamp lag 1.25 s, no lead), and no law (fair cap, mid skew,
  complement or cost lock, touch peg) puts more than 27% of re-sign prices within a tick. Only 19% of imbalance changes
  get an exact-size pairing bid within 10 s, so "every unbalancing fill is followed by a bid for the missing shares" is
  withdrawn.
- **Wallet differences (VALIDATE-only):** mo-money's lower posture share comes from its resting rungs: 41% of its class-(ii)
  fills were 500 rungs placed against the posture and still against when swept (almach 14%, bosona 19%); its quote moves
  follow the posture like the others (0.84 vs 0.89). The raw match-time book lean (0.78) is the cluster's own resting
  order; with the filled order removed the book adds about one point to the posture (X144).
- **Lot replication of the fill classes (VALIDATE aggregate):** fills whose transaction also fills another maker at a better
  level (the taker swept through, 8.6% of VALIDATE fills) score 0.50 on the public side against 0.71 for top-of-book fills.
- **Outcome (X137):** pricing the replay's pairing leg at the tracer depth (0.11 below the last print) turns its locked
  pairs from -$106k into +$225k on VALIDATE (+$111k STUDY), but the window correlation stays at 0.185 / 0.191, below the
  frozen one-sided replay (0.207 / 0.218): the outcome gap is the main rung's execution, not the pairing price.
- Rejected this iteration: online configuration from the previous development block (X143), the level-crossing switch
  rule on the block clock (X136 step 2), the TWAP-60 reference (X134: wins on lot VALIDATE 0.707 vs 0.615 but loses on the
  exact live clock 0.62 vs 0.81; not adopted).


**Iteration 12 change (side component; counted part is public): R8-side.** The side of each BTC 5m maker fill is
described by a window state machine (`code/side_sm.py`, reported by `evaluate()` as `side_state_machine` and
`btc15m.side_state_machine`, block clock, no recordings needed). **Counted (public, `counted_side = no_own_state`):** decided
window (|Up mid - 0.5| > 0.4 at b - 3) -> the cheaper token (this branch IS the market-only cheaper-token baseline), else the
Chainlink posture (report stamped b - 4, Gamma strike, 1.4 x 300-s Binance vol; Binance stand-in digital where the value is
missing): **VALIDATE 0.693 per fill** (27,988 fills; STUDY 0.569) against the cheaper-token baseline 0.679 (STUDY 0.484).
**Reported, never counted (own state):** after entry, (a) the held-outcome composite (schedule-size orders -> the outcome
the cluster holds more of, non-schedule pairing orders -> the under-held outcome) scores 0.790 per fill (STUDY 0.753), but
(b) the own-history baseline "side of the cluster's previous fill in the window" scores 0.822 (STUDY 0.809) and wins 0.82
where the two disagree: after entry the fills come in same-side runs, which is fill persistence, not a decoded quote rule.
Pairing bids (non-schedule sizes) sit on the under-held outcome 0.91-0.94 (X92). The entry is where the multiplier drift
lives (best k 1.0 on STUDY entries, 1.4 on VALIDATE entries). Smoke test through `evaluate()` on the historical VALIDATE
hour 10-29 12-13: public 0.678, own-state composite 0.825 (680 fills). Everything else in R7 is unchanged; the
`side_state_machine` blocks only add reported metrics.

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
| Side | **Iteration 12 (R8).** Counted, public: decided window -> the cheap loser (= the cheaper-token baseline; a deep-bid module ramped from Monday 10-26: <= 0.10 orders 4% -> 24% of filled orders, 26% -> 71% of orders in decided windows, capture of the >= 0.90 taker-BUY opportunity 0.2-0.4% -> 2.3-5.5% at a flat opportunity), else the Chainlink posture (entry fills 0.66 / 0.70; best multiplier 1.0 on STUDY entries, 1.4 on VALIDATE entries): 0.569 STUDY / 0.693 VALIDATE per fill vs cheaper 0.484 / 0.679. Reported, own state: after entry fills come in same-side runs (previous fill's side 0.88 of schedule fills; own-history baseline 0.809 / 0.822 per fill, above the held-outcome composite 0.753 / 0.790); pairing bids on the under-held outcome 0.91-0.94. Live 10-31: the US-session 500 ladder follows the Chainlink edge over the mid 0.786 per fill (0.965 where reference and market disagree; historical VALIDATE region D 0.93). The favourite-share drift (the 'weekly k cycle') is the entry and deep-bid decisions: the whole history rejects weekday, volatility and step models (out-of-sample R^2 < 0), the market's other makers are flat (maker-row tapes), the ladder-center multiplier on the live Saturday block is 1.14 (5m) / 1.37 (15m) vs a fill-level best k of 1.4, and a band rule fails (0.682 vs 0.683). | VALIDATE-only (public part); own-state description (not decoded) | `code/side_sm.py`, `code12/typed_side.py`, `code12/persist_vs_policy.py`, `code8/fill_side.py` |
| Price | Fill price = last clean trade before the fill minus 0.01. **In-block execution-order clock (R7, recording-free): 0.807 on all 27,988 VALIDATE BTC 5m maker fills (block clock 0.709; gain +0.098, 2-h block bootstrap [+0.084, +0.111]; per wallet 0.800 / 0.805 / 0.814; halves 0.806 / 0.807), 0.766 on BTC 15m (block 0.666), pooled 0.803 (block 0.705); STUDY 0.751 / 0.730.** Trivial anchor 'last print' with no offset on the same clock 0.773. Live match clock (R4): 0.83-0.86 (10-31 15:40-16:40: block 0.625, in-block 0.719, match 0.849, R7 combined 0.843): the in-block order recovers part of the match-clock gain on busy hours. Block clock exam 0.688. This IS the trivial anchor "last print" minus a tick on a fresh clock. The ladder hangs off each market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in 15m; top rung within a tick 26-30% vs 19% for a mid-minus-constant anchor). | exam-verified (block clock); VALIDATE-only (in-block clock, match clock) | `price_inblock`, `price_r7`, `price_match_clock`, `code11/inblock_*.py`, `code8/m1_invert.py` |
| Size | October: schedule rungs 500 x 2^k with a one-fifth level (100 / 12 only at 30-120 s left); 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; plus **imbalance pairing bids** of exactly the own abs(Up - Down) shares (calldata original size within 2% of the imbalance; 11-14% of lot fills; not remainders). July (pmxt pilot, same engine family): 500 / 300 / 50 + pairing sizes; June: 50 / 100 / 300. | VALIDATE-only | `code6/m5_size.py`, `code10/m1_pair_lot.py`, `code10/pmxt_pilot.py` |
| Exit | Holds to resolution; after entry bids its own imbalance on the under-held outcome (non-schedule sizes), priced at the market, plus small complement taker buys; merges ~65 s before the end. Locked pairs +$38.1k and residual -$14.4k on VALIDATE (maker BUY fills). **Iteration 12: a strict-fill replay of the decoded machine with this pairing leg loses $106k to $236k on its locked pairs (at-touch fills: $87k to $236k) and lowers the oracle-side outcome ceiling from 0.47 / 0.53 to 0.25 / 0.30**: the cluster's pairs need queue-priority fills that do not trade through. | VALIDATE-only | `code12/replay_machine.py`, `code10/m1_pair_lot.py` |

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
| side, bin level (R7) | 0.672 (activity 0.613) | 0.663 | 0.733 | >= 0.80 |
| side per fill, R8 public part (decided -> cheaper, else posture) | | **0.693** (cheaper 0.679; own-state composite 0.790 and own-history baseline 0.822 reported, not counted) | 0.821 (no sizes; own-state 0.754) | >= 0.80 |
| price within a tick, in-block clock (R7) | **0.803** | **0.807** (all 27,988 fills) | 0.766 | >= 0.80 |
| price within a tick, block clock | 0.705 | 0.709 | 0.666 | |
| per-window PnL corr, strict-fill replay of the quote (target definition) | | **0.207 / 0.218** (1,089 windows; STUDY 0.033 / 0.070) | | >= 0.5 |
| same, oracle window side (ceiling of a strict replay) | | 0.473 / 0.527 (STUDY 0.505 / 0.637) | | |
| per-window PnL corr (expectation proxy) | 0.260 / 0.327 | 0.329 / 0.325 | 0.180 / 0.345 | |
| selection AUC / recall / lift (5m only) | | 0.685 / 29.5% / 2.87 | | 0.80 / 50% / 3 |
| coverage fills / abs PnL (VALIDATE aggregate) | 0.868 / 0.891 | 0.783 / 0.686 | | 0.80 / 0.80 |

Scope per 6-hour block (iteration 9, every development block 10-08..10-31): R6's universe meets 0.80 of trades and dollars
in 34% of blocks; + BTC 4h 45%; + BTC hourly/daily 62%; + ETH 89%; every crypto Up/Down family 100%.

Quote unit (iteration 14, reported as `quote_unit_side` and `quote_presence_event_time`; VALIDATE-only on one block):
side of every 500/1000 post at the touch from the latest published report 0.831 (585 posts with exact publish times),
0.75-0.76 with the point-in-time-safe fixed lag, 0.742 from the exam recorder (15:53-18:00); event-time post presence
0.701 vs 0.672 activity (gain +0.029).

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
- Iteration 12 (the full machine): adding the decoded pairing leg to the strict-fill replay makes every correlation worse
  (posture -0.02 / -0.00, oracle side 0.25 / 0.30) because a pairing bid that fills only on a trade-through buys the
  under-held outcome as it falls (replay locked PnL -$106k to -$236k vs the cluster's +$38k). The outcome gap is the exit's
  queue priority: the cluster's pairing bids are filled at the touch by takers who buy its held outcome through complement
  mints, before the price moves through them.
- Iteration 12 (side): the public side is 0.693 per fill on VALIDATE (decided-cheaper plus the Chainlink posture). With own
  state the per-fill number exceeds 0.80 only through fill persistence (the previous cluster fill's side, 0.822), a
  trivial own-history baseline, so the remaining public gap is the entry decision (posture 0.70 per entry fill; its best
  multiplier moves between the halves) and the decided-window branch (cheaper 0.59 STUDY / 0.81 VALIDATE) that moves with
  the deep-bid module.
- Iteration 12 (side per run, X129): per run of same-outcome fills the public side is 0.611 on VALIDATE (0.547 STUDY): the
  window's entry run follows the posture 0.725 (0.619), the later runs, which switch outcome, only 0.541 (0.466). One public
  decision per window (the entry), then taker-chosen switches that no public input predicts, each repeated ~8-10 times by
  same-side fill runs.
- Selection: the module on/off schedule is partly a calendar (weekend nights ET) and partly ad hoc (the 10-31 12:53 ET
  switch-off and the restarts after it); its trigger is not decoded.

## Why it works

It is a two-sided liquidity provider whose ladders hang off each market's Polymarket mid and are skewed toward the
settlement source, the Chainlink BTC/USD report, re-priced the moment Polymarket's public relay publishes each report. It
completes pairs with maker bids for exactly the missing shares (iteration 13: for only about a fifth of the imbalance
changes, resting a median 11 c below the touch) on
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
mints) fill its bid on the other at the touch; a slower copy only gets the trade-throughs, which are the adverse moves. Iteration 12 sharpens who pays: the maker-row tapes show the market's other makers keep a flat favourite share (0.50-0.51) while the cluster's own share of the underdog side rose from 1.5% to 2.6% of maker volume between the halves (its favourite-side share stayed 2.2%), and its deep loser bids captured 2.3-5.5% of the takers' >= 0.90 favourite buys from Monday 10-26 (0.2-0.4% before). Those longshot fills returned +13.5% on VALIDATE and -36.8% on STUDY (mechanics panel): it is paid by takers who pay 0.90-0.99 for near-certain favourites through complement mints, and by takers whose buys of its held outcome fill its imbalance bids at the touch.

Iteration 13 adds the time dimension of the economics. On a pre-registered sample of the stable weeks (BTC 5m windows of the hours 02/08/14/20, 09-11..10-11) its maker fills earned +9.3% (09-11..25) and +7.4% (09-26..10-11) per dollar held to resolution, against +0.6% on the same hours of 10-12..22; in those profitable weeks it bought the cheaper token on 71% of fills (09-11..25) and its side did not follow the Chainlink posture (0.49). So the money of the stable version came from buying below the outcome probability on whichever side the takers sold, mostly the underdog by count and the favourite by dollars (assumptions panel F2), and the Chainlink-skewed quoting is the configuration that ran while the return fell. On the live block, the fills split into quote moves to the touch (73%, side = the Chainlink posture 0.81) and resting rungs about 2 c below the touch that the takers sweep (27%, side = the book's lean, not the posture): the second group is paid by takers who push one outcome down through several price levels in one block.

Iteration 14 adds the counterparties of the profitable version (pre-registered stable sample, 34,410 maker fills joined
to their takers). In September it earned +8.3% per $ from all three taker populations alike (round-USD retail +9.2%, the
top-20 counterparties +11.4%, the rest +6.6%), mostly by buying the cheaper token below its probability. In October
(+0.6%) the top-20 counterparties' share of its fills fell 63%, and against unchanged retail flow its fills moved to the
favourite (cheaper share 0.70 -> 0.49) and lost 11%. The engine's quote is a mid-pegged ladder skewed to the Chainlink
report just published: it follows the posture at 0.75-0.83 per at-touch post (0.83 on the exact publish clock), and the
takers then choose which posts fill.

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay, a CLOB connection that
re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs on both outcomes of several BTC
5m and 15m windows (a working capital of ~$22-24k per wallet, reset by a weekly Monday sweep at the 01:00 UTC restart and growing to $43-49k by the end of the week; no deposits in 10-09..30), and unchanged fees (0.07 taker), listings and matching. A home
connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the slower makers this strategy
profits from: expect zero or a loss without low latency. In the new Chainlink noise regime the strategy itself lost money
on BTC 5m (10-31), and its operator switched BTC 5m off and restarted two of the three engines. Iteration 12: the three accounts have three different owner keys (a Safe for mo-money, ERC-1967 smart-wallet proxies for almach and bosona) whose fill sides move together; mo-money's owner has a Hyperliquid account with no fills in the 120 days before T0. A copy would also need the queue priority: replaying its own decoded pairing leg with strict fills turns the +$38k of locked pairs into a loss of $0.1-0.2M.

Iteration 13: the configuration that earned 7-9% per dollar in September (module always on, underdog-heavy fills) is no longer what runs; the October configuration earned +0.6% per dollar on the October BUILD sample hours before rebates, and the operator updates the engine within 1-3 days of listing changes (the last-fill time moved from ~45 s to ~100 s before the end when the settlement switched to TWAP-60). A replicator would be copying a moving target whose current version earns little before rebates.

## Open leads (not part of the frozen rule)

- X160: replicate the quote-unit side (latest published report, k 1.0) and the safe event-time quote presence on the
  next development blocks with BTC books and dy_rtds publish times (11-01 07:00-12:00, 18-24), including the 62/250 posts
  (`code14/x160_block.py <start> <end>`).
- X161 / X151: R9, a family-general universe for the weekend exam blocks (every crypto Up/Down family: R7 price, the R8
  public side with the cheaper-token branch where no Chainlink series exists, presence by transfer of the R3 class), frozen
  before it is scored on the weekend analogs.

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
