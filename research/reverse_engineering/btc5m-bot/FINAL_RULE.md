# btc5m-bot: frozen rule (iteration 15: UNCHANGED from iteration 14; side = decision clock on Binance's own clock, dc_exam14; presence / price unchanged since iteration 8; the PnL rule is the exposure tracker with the mix14 target, pre-registration 7)

Iteration 15 in one paragraph (no candidate adopted; the scored rule, code/final_rule.py and target_metrics are unchanged). The
pivot was a new data source and target: the ASK-side L2 book of every BTC 5m token, rebuilt from the public capture's price_change
level sizes for 10-20..22 (best-ask check 98.2-98.4%), and the operator's realized taker fill as an execution against it. Three
results change the account. (1) The realized size is NOT the visible depth: for orders that fill less than their original size,
the depth at or below the limit is a median 107 shares at the bot's view against a median fill of 11, and ~95% of it is CANCELLED
untraded during Polymarket's 150-ms hold (other takers explain 3.5%, the operator's own legs 1.0%); a depth-bound order fills what
the slower makers leave (median 15 left, 14 filled). With the TRUE decisions, public size information gives a window-net r of
0.39-0.44 against 0.70-0.75 with the true fills, and a fill model on decision-time public data reaches r 0.29: about 0.3 of
condition 5 is the makers' cancel race after the decision. The pre-registered depth-weighted hazard nowcast (pre-registration 8)
lost to mix14 (0.4772 / 0.4556 vs 0.4792 / 0.4594 on 576 windows) and was not adopted. (2) The Polymarket BOOK predicts the
operator's decisions as well as the decoded Binance trigger: a market-only baseline with the book's depth and its 100-ms changes
reaches 0.873 against the hazard's 0.881 at the decision clock (0.910 vs 0.912 on bins with no operator print nearby); the
operator trades into the makers' cancellation wave on the bought outcome (o's near-touch ask depth falls to 0.85 of its level
200 ms before the match and 0.61 at 100 ms; placebo flat). That match sits in the last ~50 ms before the bot's own Polymarket
view: with the book cut at e (before the bot's view for every label in the band) the decoded hazard gains +0.058 [0.050, 0.065]
over the book-aware baseline, with it cut at e + 50 only +0.008; pre-registration 9 replicated this in the reverse split (score
10-20: +0.0805 [0.075, 0.086] at the e cut, +0.023 at e + 50). Condition 2 at the decision clock therefore hinges on a 25-50-ms
cut convention that must be fixed from physics (the bot's view = arrival - 30 ms) in the exam pre-registration; the book also carries part of the late-trigger sixth (book-only side right on 62% of dc14's errors;
dc14 + book 0.838 vs 0.8135, not pre-registered). (3) The salts are not V8 Math.random output (a GF(2) state solver validated on
real Node v22 output fails on all 130 copy groups); JSC / Bun is untested (no SAT solver in the venv). Also: a sharper allocation
model (clock features, XM AUC 0.79) lifts XM's thinning ceiling only to 0.46 < 0.47; the iteration-13 per-wallet pay-up anchor
(ask + 0 / 1 / 1 c for DS / GF / XM) holds out of sample per wallet and day (XM 0.82 / 0.79). A full-rate Binance recorder
(rec_bn15) records the 11-01 06-12 development block for the out-of-time check.

Iteration 14 in one paragraph. The decision clock was wrong by ~50-80 ms, and fixing it changes the side and the selection
accounts. Both panels found that pre-registrations 3-4 (decision a = m - 180 ms on the collector's receive clock) cut off the
last 50-60 ms of the bot's information. Pre-registration 5 fixed the anchor from physics (150-ms taker delay + 105-ms
Binance-to-London + 5 ms = 260 ms before the match, on Binance's exchange clock), refitted the spot-only exam route on 10-17..19
and scored it once on 10-20..22: **83.7% per taker order (DS 83.1, GF 85.5, XM 81.3%), 82.4% per decision**, against 74.2% for
the old anchor on the same orders, 56.8% for a Polymarket-only model and 53.9% for the own-inventory rule. The placebo anchors
(m -/+ 3 s) give 50%. On the fit days the information arrives in a 60-ms band ending ~230 ms before the match (+15.5 points from
c = 320 to 260 ms, +1.2 from 260 to 200). Crowd orders that do not co-arrive with the operator show no such band. The input is the
Binance SPOT top of book, mostly sub-tick queue-imbalance moves; no other venue adds information after its knee. This model is
now the exam route `side_decision_clock` (code/dc_exam14.py) and `target_metrics.side_accuracy`. On the same clock the TAKE is
largely decoded: a 50-ms decision hazard reaches AUC 0.889 against 0.759 for Polymarket activity (VALIDATE-only, taker first
legs, reported as `presence_decision_clock`, code/dc_hazard14.py). Two results go the other way. (1) The block-second presence
margin does not survive a CAPTURE-AWARE market baseline: others' server-ms prints 1-3.5 s before the block second lift the
baseline to 0.846 against the frozen model's 0.870 (+0.024 < 0.05), so condition 2 now FAILS against my stronger baseline.
(2) Neither a millisecond net-flow nowcast (pre-registration 6) nor the hazard nowcast lifts condition 5. A decision-hazard nowcast (pre-registration 7) gives a window-net r of 0.5125 for the mix and a tracker of 0.5065 / 0.4674 against the frozen target's 0.4973 / 0.4607 on 10-20..22 (adopted).
The size is scheduled configuration: window-index A/B arms (arm B = (start/300) mod 4 in {1, 2}) with a larger base size in B
windows during size phases, and one dispatch phase (10-21 16 -> 10-22 13) that moves DS / GF shares. Condition 7 for XM is a
random-thinning ceiling: with the operator's TRUE decisions and the best public allocation model, XM's PnL r is at most 0.39-0.43,
below the 0.47 required. Further checks this iteration: the knee-clock design explains 53% of the fast crowd co-takes in the same 50-ms band (iteration
12: 14-21%) and leaves the own-decision kernel only +0.010 AUC (it was +0.037), so the shared input and most of the 30-60-s
"operator state" were the full-rate Binance spot book on the right clock; the hazard replicates in the reverse split (0.925 vs
0.781); Deribit and Coinbase move after the order has arrived (lagging copies, no faster input); and the ORIGINAL order size is
not a response to the knee-clock move (AUC ~0.60 within wallet), so size stays configuration plus own state.


Iteration 13 in one paragraph (nothing in the scored rule or target_metrics changed and no candidate was adopted; `evaluate()`
gains one reported component, `side_decision_clock`, described below). The inventory path is two
operator-level streams. A LARGE-size lean is fanned out to every wallet (cross-wallet window-net correlation 0.35-0.47) and
pyramided. A SMALL-size taker counter-flow buys the complement of the operator's REALIZED large inventory within about two
minutes: on small-order seconds the realized large net has t = -26.5 beyond the frozen side model, a small-order placebo goes
the other way (+4.0), and the crowd's flow has no effect. Inside each wallet the two streams cancel (corr -0.26 to -0.60),
which is why the wallets' total nets look independent. A pre-registered two-stream net-flow model and tracker were NOT
adopted (0.468 / 0.432 against 0.476 / 0.440): public data sees the same information either way (corr 0.957 with nf12b), and
the public share of the window net is bounded by the public share of the lean (r ~0.32). Condition 7 is now a measured
limit. Even a PERFECT copy of the pooled net gives XM only 0.30 (0.41 with XM's true per-window share, 0.04 from the other
wallets' legs), because XM's PnL is the side of its own dispatched legs, and no public state predicts which wallet carries an
order (accuracy 0.61 against a base rate of 0.61 at the decision clock). New data: a public CC0 capture of Polymarket's BTC 5m
market channel (Hugging Face Fahri-5/updown-5m-polymarket-raw, revision f848a77c) gives the operator's server-ms match time
for 97% of its VALIDATE txs. At that decision clock the side is the Binance spot microprice over the last 100-250 ms, which
gives 77.2-77.3% of taker orders at full coverage (fit 10-20 -> score 10-21 and the reverse), +4.5 points over the
block-clock per-order 72.7%. It is 81-83% in the first two minutes of the window and 62-72% after three, where the decisions
mix weak tick-following with pairing; there is no settlement-TWAP lock-in. The block-clock side model's inputs end a median
~0.2 s after the match, so part of its 76.7% is post-decision continuation. The limit is within a tick of the archive ask at
the arrival for 93.4% of 2,476 calldata taker orders. Rejected this iteration: a settlement-basis input (no gain), an
implied-vol scale of the buy-back (the replicated interaction is realized vol), and the open as a separate decision type.


Iteration 12 in one paragraph (PIVOT: condition 5 as an exposure-path target). Per VALIDATE window the cluster's PnL is its
signed net exposure times the outcome (r = 0.884 pooled, 0.887-0.921 per wallet), so the PnL condition does not need the
bot's decisions, only its NET PATH. The new executable rule (`_strict_tracker`, pre-registered before scoring) keeps a
target net equal to the cumulative predicted cluster net flow (0.5 x the frozen it4b per-second netflow model + 0.5 x a new
BUILD-fitted net-flow model with slow spot-path features, `model_it12_nf12b.txt`) and buys the deficit at the last implied
ask + 2 c with strict fills (other traders' taker prints, latency >= 2 s), re-sending what does not fill. On VALIDATE its
per-window PnL correlates with the cluster's at Pearson **0.476** / Spearman **0.440** (2-h block CI [0.423, 0.522]; halves
0.460 / 0.487) against 0.18 / 0.17 for the iteration-4 30-share replica, with the realized net tracking its target at r =
0.993; every execution variant lands at 0.43-0.48, so the remaining gap is the net PREDICTION (window-net r 0.48), not fills.
Per wallet it reaches GF 0.34, DS 0.43 and XM 0.06: the three wallets' per-window PnLs are nearly independent of each other
(DS-GF 0.20, DS-XM 0.00, GF-XM 0.15), so one pooled rule cannot carry every wallet. The net path is structured: within a
window the cluster buys with the current minute's BTC move (t 5-11) and buys back against the earlier minutes' moves (t -3
to -12), leans with the previous window's outcome (t 2-4); a strike-at-open fair value is not supported (the TWAP-minute
coefficient flips sign between BUILD and VALIDATE). End-to-end `evaluate(1792627200, 1792638000)` (36 VALIDATE windows, 77 s)
reproduces the offline tracker exactly. Selection: the recorded Coinbase ticker adds a small replicated gain to the onset
selection (out-of-sample AUC +0.016 / +0.014 in both directions; strong Binance ticks are taken 43-48% when Coinbase has
not traded, 22-25% when it already moved toward o). Timing correction: only ~9% of the live decisions are time-locked to a
sharp venue move in the recorded feeds beyond a placebo (13.2% vs 4.7%); those are the strong-tick, large, early, more often
won snipes, and ~90% of decisions have no sharp clock in any recorded feed. The take's window-level heterogeneity is an
operator-level state with a 30-60-s time scale (an own-decision kernel with 30-60-s decay predicts held-out takes best, AUC
0.718 vs 0.681; inside 2-minute segments the 30-s count is within a redraw null), not a sub-30-s self-excitation and not a
race-success controller; slow public state adds nothing to
presence at the block clock (0.8747 either way). The onsets the bot takes are also taken by the independent fast crowd far
more often (0.39-0.42 vs 0.17-0.20 when it skips), and the recorded inputs explain only 14-21% of that shared selection: the
take runs on an input that fast traders share and the recordings do not contain yet.

Iteration 11 in one paragraph (nothing in the scored rule changed): the panel's selection mechanisms were tested on one onset table and rejected: a self-kept
vol scale (z-scored tick, tick counts, within-window percentile) is no better than the raw bp tick, a snapshot / confirmation gate does not select, Polymarket's
other crypto books do not confirm, and the crowd re-timed on the server clock still follows Polymarket activity. Among Binance price-level ticks the take is
indistinguishable from a coin given every public input (AUC <= 0.58 in both halves) and rises with the bot's own recent decisions (a self-exciting internal
state). The size does not feed back from realized fills (it reads the intended position or a regime), and live the 100-share size follows the tick strength
(AUC 0.72; not visible at the block clock even with millisecond trades), so the condition-5 ceiling for a replay that reproduces the decisions is the fixed-size
0.70-0.77, and on a recorded book the race is nearly deterministic given the arrival. The bot reads Polymarket's book ~30 ms old and Binance ~100 ms old: it
runs next to Polymarket's engine. Iteration 10's 'fresh-signed until 08-18' is retracted: August was pre-signed on other schedules.

Target status on VALIDATE: scope met; presence met in the block-second unit (0.875; +0.054 over the stronger of my two
market baselines, 0.821, 2-h block CI [0.051, 0.056]; per wallet +0.051 to +0.066); price within a tick met (95.1% of
VALIDATE taker orders against the touch of the same match, from calldata; the trivial touch anchor, stated as such); side
76.7% per one-sided second (72.7% per taker order), below 80%, but no wallet is one-sided beyond its order-count null (XM
24.3% vs 26.1% on VALIDATE, 3.5% vs 6.1% on 10-31), so the condition does not bind in substance (XM is above the literal
20% bar on VALIDATE); executable PnL correlation 0.476 / 0.440 with the iteration-12 exposure tracker (< 0.5; it was 0.18
with the 30-share replica; per wallet GF 0.34, DS 0.43, XM 0.06). The account below (iterations 9-11) concerns replays of the
DECISIONS; the tracker side-steps it by reproducing the net path instead. Iteration 10 corrected the iteration-9 account of the PnL
condition: with sizes held fixed the true rule replayed under the race lottery would correlate 0.70-0.77 with itself, but
the size depends on the operator's own net (large orders pyramid the leg it holds), and with that feedback re-simulated the
true rule's test-retest correlation is only 0.47-0.58 pooled (0.41-0.62 per wallet). The per-window PnL is the large-order
lean, a coin with respect to the outcome that race outcomes seed and the size rule amplifies, so condition 5 is at the edge
of what even a perfect decode could reach. Target not reached; nothing is exam-verified.

Iteration 13 addition to `evaluate()` (reported, not a target key): `side_decision_clock` (`code/dc_exam13.py`, pre-registration 4).
For each cluster taker order it reads the matching-engine ms from the public CC0 capture Fahri-5/updown-5m-polymarket-raw
(revision f848a77c, range requests over the row groups of the evaluation period only) and the Binance spot book of the same
capture. The decision instant is a = m - 180 ms; the features are the microprice / mid returns over [a - K, a) and rel; the model is
`model_it13_dcside_spot.txt`, frozen. It reports the per-order accuracy per wallet and per half, and the one-sided-window side per
wallet. Development runs never open a capture day file that starts at or after H. The end-to-end check on 10-20 11:00-12:00
reproduces the offline frame exactly (929 orders, 71.0%).

Code: `code/final_rule.py`, `evaluate(start_ts, end_ts, intervals=None) -> dict` (with `intervals`, only windows that start
in one of the `[a, b)` pairs count; live recordings are read through `iter_live(..., allow_sealed=ALLOW_SEALED)` with the
module constant `ALLOW_SEALED = False`). Models are trained on BUILD only (windows 2026-10-09 .. 2026-10-16 00:00 UTC);
VALIDATE = 2026-10-16 .. 2026-10-23 00:00 UTC (2,016 windows, 1.21M cells). Nothing was fitted on VALIDATE or sealed data.
Live (future-block) components, all fitted or chosen on development blocks of 10-31 only:
- `side_live_decision` (`_live_vote`, frozen in iteration 7): six-series exam-feed vote, now reading both the rec_exam7 and
  the rec_exam8 feed names (identical records); with the PRE-REGISTERED full-coverage fallback of iteration 8
  (`full_coverage`, reported as `side_accuracy_live_decision_full_coverage`);
- `side_live_decision_ext` (pre-registered secondary, iteration 8): the same vote plus Bybit linear L1 from `btc5m_xfam`;
- `presence_live_decision` (`_live_hazard`, iteration 8): decision-level hazard with frozen coefficients `HAZ_FULL_COEF` and
  the Polymarket-activity baseline `HAZ_BASE_COEF`, both fitted on 10-31 16:04:30-16:33 UTC.
- `evaluate` is a wrapper (iteration 8): if the historical pipeline cannot run (e.g. a day's Binance 1-s archive is not
  published yet), it returns the live components only (`_evaluate_live_only`) instead of failing; tested through the exam
  path on 10-31 16:35-17:05 (development).
- Iteration 10 data-loading fix (the rule is unchanged): drpc's free plan now refuses `eth_getLogs` ranges above ~100-199
  blocks, so `cluster_fills` falls back to 100-block chunks (`_get_logs_chunked`) when a 3,000-block request fails; tested on
  an uncached BUILD hour (1,872 fills in 16 s; ~25 min of log fetching for a 4-day lot). Both evaluate paths were re-run after
  the iteration-10 changes: `evaluate(1792706400, 1792713600)` reproduces iteration 9 exactly, and the exam path on 10-31
  16:35-17:05 returns the new `_pit` keys.
- `presence_live_decision.edge_rule_V8` (iteration 9, PRE-REGISTERED secondary, never counted toward the target; constants
  `EDGE_K = 8`, `EDGE_SIGMA_BP = 0.67`, `EDGE_FEE_NET = 0.035`, `EDGE_MOVE_WIN_MS = (600, 100)`): act on o iff 8 x 100 x
  Delta_o x (mean BTC microprice move toward o over [t - 600, t - 100) ms) exceeds 100 x (half spread + 0.035 p (1 - p)),
  Delta_o = phi(Phi^-1(mid_o)) / (sigma sqrt(tau)); precision and recall for the match label against the frozen hazard at the
  same volume. On the exam feeds of 10-31: lift 1.5 / 7.7 / 3.1 on 16:04-16:33 / 16:35-17:05 / 17:05-17:55 (unstable); first
  clean test 11-01 06-12. The frozen rule itself is unchanged.
- Iteration 10, PRE-REGISTERED 10-31 ~21:40 UTC (first clean test 11-01 06-12; reported next to the frozen versions, which
  stay unchanged). Polymarket holds every marketable order on these markets for a taker delay D = 150 ms (`itode`; measured:
  fresh-signed orders of other wallets reach the match >= 186-190 ms after signing on BTC 5m vs 35-73 ms on markets without
  a delay), so the bot's order ARRIVES at a = m - D and its last input is about a - delta = m - 180 ms. The frozen live vote
  [m - 600, m - 100) and price anchor (m - 50) read up to 50-130 ms past that point. Constants `TAKER_DELAY_MS = 150`,
  `POST_LATENCY_MS = 30`:
  - `side_live_decision_pit`: the same vote over [m - 650, m - 180) = [a - 500, a - delta) (in sample 16:04-17:55: 83.3%
    on 67.6% voted vs the frozen 83.2% on 65.8%; placebo 50.2%);
  - `price_live_book_pit`: o's ask at m - 180 (in sample 90.7% within a tick, 72.1% exact, vs 92.3% / 78.2% at m - 50);
  - `presence_live_decision.pit_label`: the frozen hazard scored against a match in [t + 180, t + 680) (a decision at
    a - delta in [t, t + 500)); target keys `side_accuracy_live_decision_pit`, `price_within_tick_live_pit`,
    `presence_live_decision_auc_pit` / `_baseline_pit`.
Exam inputs recorded through the sealed blocks: `code/rec_exam7.py` (btc5m_xclob / btc5m_xven, 10-31 16:03 -> 11-02 06:00),
`code/rec_exam8.py` (the same recorder as btc5m_xclob8 / btc5m_xven8, 11-02 05:59 -> 11-03 18:00: weekday sealed blocks
11-02 06-12 and 18-24, 11-03 00-06 and 12-18) and `code/rec_fam8.py` (btc5m_xfam: Binance USDC-M and COIN-M perps, spot
USDC / FDUSD books, Deribit perp quotes, Bybit L1; btc5m_xliq: liquidations; 10-31 17:45 -> 11-03 18:00). The sealed block
10-31 06-12 has no exam inputs; there the historical (block-clock) rule applies.

Tags: **exam-verified** (passed a sealed exam: none yet), **VALIDATE-only** (measured on VALIDATE / development data,
including the 10-31 live development blocks), **hypothesis** (supported by little data or by argument).

## The decision process, component by component

1. **Order generation (decoded from V2 calldata, B1) - VALIDATE-only, deterministic.** The bot never prices an order when
   it trades. It PRE-SIGNS a ladder of BUY limit orders for each window: both outcomes, every price on the 1-cent grid, a
   few copies per level and two sizes per level (e.g. 30 and 100 shares), in a burst of ~1 s per wallet (~1.7 ms per price
   level), three times per window at rel = -89.5 s, +42.0 s and +172.7 s. One process signs XM, then DS (+1.06 s), GF
   (+2.17 s) and a fourth wallet 0xd84403ef... (+3-4 s). Salt = round(Math.random() * Date.now()) (TypeScript clob-client),
   signatureType 3, builder = metadata = 0. Check in `evaluate`: 99.9% of 13,443 VALIDATE orders inside the predicted bursts.
   The schedule is identical on 10-31 (signing-time quantiles -89.6 / 42.3 / 43.5 / 173.2 / 174.7 s vs VALIDATE -89.7 /
   40.8 / 42.9 / 172.7 / 174.6 s). Versions (iterations 10-11, calldata samples of August-September): the bot
   PRE-SIGNED in August too, on other schedules: two bursts per window at ~0-30 / 150-180 s mod 300 (early August) and ~40-90 /
   180-240 s (08-09..21), then the three-burst schedule from 08-22; operator orders on 08-05 and 08-12 were signed 3-121 s
   before their block (DS taker median 48 / 111 s) against 2.8-3.5 s for the other wallets' taker orders in the same txs
   (results/version11.json). Iteration 10's 'fresh-signed until 08-18' counted only the October burst phases and is
   retracted. Size menus: one size per day in August (90, 60, 50, 100, 20, 80, 30), two sizes from 08-22 (30 / 90, 25 / 75,
   20 / 60 / 80 / 200 on 09-01 / 09-08, 60 / 100, 30 / 50 and 30 / 100 in October); the maker share of the fills moved with
   these versions as much as with the delay changes (results/version10*.json, refill11.json).
2. **Selection - VALIDATE-only.** Every BTC 5-minute Up/Down window (94-99% traded), nothing else; inside a window only
   prices in the ladder range (~0.12-0.88). Whole-cluster outages (40 min to 5 h) are bot-side.
3. **Timing / trigger - VALIDATE-only (live development blocks).** The decision is the SUBMISSION of a pre-signed order
   Iteration 14 (VALIDATE, decision clock on exchange time): the bot reads the Binance spot book ~80-110 ms after the stamp and its order arrives 150 ms
   before the match; a 50-ms decision hazard on that clock reaches AUC 0.889 vs 0.759 for Polymarket activity (DS 0.881, GF 0.903, XM 0.919), top inputs the
   100 / 250-ms spot microprice return toward o and |p - 0.5|; only ~8% of decisions follow a price-level tick (placebo 1.2%); followers ~200 ms later are
   re-decisions on fresher spot. Older text below:
   ~250-350 ms before its MATCH after a microprice tick (size-weighted touch) of the Binance USD-M BTC/ETH perps (earliest,
   sharpest), OKX and Bybit toward the outcome. Of those 250-350 ms, 150 ms are Polymarket's taker delay (the order is held
   before matching; iteration 10, measured with a no-delay control) and ~30-40 ms signing / posting, so the bot itself
   reacts ~100-150 ms after the venue tick, and its last input is ~180 ms before the match. Its limit equals o's ask 50-100
   ms before the match in 74-75% of live orders (placebo 5-7%) because that ask usually survives the hold. The hazard is gated by Polymarket activity, not by stale
   liquidity: per 500 ms, P(match on o) is 22% with a > 0.5 bp tick toward o while o's ask falls, 11-12% with the tick and
   an unchanged or rising ask, 5% when the touch moves with no tick, 2% when nothing moves. Decision-level presence on the
   exam feeds (frozen hazard, scored on the later interval 16:33-17:55): AUC 0.656 vs 0.598 for the Polymarket-activity
   baseline (trades, touch changes, touch age, price), gain +0.058 (window bootstrap 95% CI [0.041, 0.076]). Historically
   (block clock) the presence score on block seconds is `model_it5_blk_full`; flag `p >= 0.30` (fixed in iteration 1). The
   bot does not act on one identifiable message (the latest lag-shifted tick does worse than the vote).
4. **Side - VALIDATE-only.** Per decision (live): the sign of the microprice vote over [m - 600, m - 100) ms. Ten-series
   Iteration 14 (pre-registration 5, the scored side): sign of the Binance spot microprice / mid / last-trade returns over [X - K, X), X = m - 260 ms on
   exchange time (book: receive - 131), K = 100..2000 ms, LightGBM model_it14_dcside_spot.txt fitted on 10-17..19: 83.7% per taker order on 10-20..22
   (DS 83.1, GF 85.5, XM 81.3%; per wallet and 36-h half DS 84.3 / 81.8, GF 87.7 / 83.9, XM 84.7 / 78.6%), 82.4% per decision, XM one-sided windows 84.3%
   (halves 91.1 / 76.8%). Exam route dc_exam14 reads the capture's day files. Older text below:
   vote by interval 86.4% / 83.0% / 75.3% / 85.2% (fourth interval 16:33-17:55: 1 agreeing series 69.9%, 2: 79.7%, 3-4:
   89.5%, >= 5: 96.8%); the frozen exam-feed six-series vote 80.4% on 61.5% (16:04-16:25) and 85.4% on 68.0% (16:33-17:55;
   placebo 54%). Full coverage (pre-registered 10-31 18:16 UTC, chosen on 14:55-17:55; first clean test 11-01 06-12): vote
   -> the outcome whose Polymarket ask rose over [m - 600, m - 100) -> the outcome whose ask fell over [m - 3000, m - 100)
   -> the underdog; 70.6% / 78.2% in sample. Per block second (historical; side model `model_it5_side_book.txt`) 76.7% of
   VALIDATE one-sided seconds, 72.7% per taker order; the block clock costs 11-25 points (iteration 7). The side does NOT
   reference the operator's own book (+0.2 points on VALIDATE) nor an exact-strike fair value (50-55%). It buys both
   outcomes in 99.8% of windows and tilts to the underdog as prices leave 0.5 (58% small / 69% big at |p - 0.5| 0.3-0.4).
   Hypothesis for the tilt (VALIDATE-only): the bot's fair value uses an implied (options-market) vol. Deribit DVOL is
   2.1x (quartiles 1.5-2.8) the 5-min realized vol at its orders, the same multiplier a revealed-preference fit finds
   (k ~ 2-3), and a fair value at sigma = DVOL puts more of its buys below fair value (53.6%; underdogs 81%) than any fixed
   multiple of realized vol; such a fair value sits closer to 0.5 than Polymarket's, so underdogs look cheap. Underdog buys
   follow flat or adverse 12-s moves; the move before a buy is the same for favourites and underdogs (not a return-unit
   threshold).
5. **Price - VALIDATE-only.** Limit = the touch (best ask) of the chosen outcome as the bot saw it 50-150 ms before the
   match: it submits the pre-signed ladder order at that price (the trivial "touch" anchor, and the rule says so). 95.1% of
   6,306 VALIDATE taker orders within one tick of the best consumed maker price (equal 83.9%). 16% are deliberately one or
   more cents ABOVE the touch (GF 27%, XM 38-46%, DS 9-10%; the same shares on VALIDATE and 10-31; 18 of 21 live pay-up
   orders had seen the consumed touch, so it is not a stale view). The pay-up share rises with the implied-vol fair value
   above the touch (12-14% when the FV is below the touch, 23% when it is > 10 c above), a weak reservation-price
   behaviour rather than a clean FV - margin limit. Pay-up is not the level where the visible depth covers the order
   (17.6%; iteration 9). The value the decisions imply (iteration 9, hypothesis on 140 pairs): opposite-outcome legs within
   1 s bracket the Polymarket mid shifted by the venue move (midpoint - mid follows the 500-ms Binance move, corr 0.94 on 20
   moving pairs), and 42% of those pairs cost more than 1: the legs answer successive opposite ticks; they are not set
   arbitrage at a static value.
6. **Size - VALIDATE-only (own state).** A fixed (small, large) menu per day, the same at every price: 60/100 (10-09..13),
   Iteration 14: the menu alternates by WINDOW INDEX inside phases (arm B = (start/300) mod 4 in {1, 2} carries the larger base size: 33.9 vs 24.6 filled
   shares per taker order in 37 phase hours; 76-84% of the >= 45-share shares on 10-16..19 are B-arm windows): scheduled configuration, not an input
   response. Older text below:
   30/50 (10-15..18), 30/100 (10-19..22 and 10-31). Which size is used follows the OPERATOR'S OWN BOOK in the window: the
   large size is used when the three wallets together are flat or long the bought outcome (GF 59-77%, XM 59-83% of orders)
   and rarely when the order would reduce an opposite position (net < -200 shares: GF 12%, XM 15%, DS 10%). Within-wallet
   VALIDATE AUC (BUILD-fitted): GF 0.751, XM 0.666, DS 0.578 vs market controls 0.489 / 0.353 / 0.546 and a market-trend
   analog (BTC return since the open) 0.52. Large orders lose 1.1-1.9 c per share after fees. Report without own state:
   the size is not predictable (within-wallet 0.44-0.59, iteration 7). Iteration 9: the operator's book includes the fourth
   wallet W4 (14% of the flow): with W4 in the net the AUC is GF 0.771, XM 0.703, DS 0.591. Live (10-31, 2,155 decisions, 111
   large; iteration 11) the 100-share size follows the tick strength at the decision: univariate AUC 0.72 (DS 0.73, GF 0.68,
   XM 0.75) for the six-series tick toward o over [a - 530, a - 30), above the operator's SENT net (0.68); P(large) 1-5% in
   tick deciles 1-8, 10.7% at 0.67-1.88 bp, 17.1% above 1.88 bp (XM 36-38% in its top decile). The block clock does not show
   it, even with millisecond Binance USD-M trades (max 300-ms move toward o in [bt - 3.0, bt - 0.2]: within-wallet 0.48-0.57;
   results/sizems11.json), and the VALIDATE large share (16-44%) is far above 10-31's 5%: the tick link may be a regime of the
   30 / 60 / 100 menu (pre-registered test on 11-01 06-12). No realized-fill feedback (iteration 11, size11): after a large
   decision that won vs lost its race the next same-outcome decision is large 19% vs 27%; the size reads the intended
   position or a regime (hypothesis, 111 large decisions).
7. **Exit / inventory - VALIDATE-only.** 59% of taker orders leave a remainder; it rests as a GTC bid at the old ask for
   Iteration 14: the executable PnL rule is the exposure tracker with the target mix14 = 0.5 x the frozen avg net flow + 0.5 x 5.935 x h(s), h(s) = the
   sum over the 50-ms bins ending in [s - 2, s - 1) s of P^(take Up) - P^(take Down) from the frozen decision hazard (dc_hazard14.hazard_imbalance);
   10-20..22: 0.5065 / 0.4674 vs 0.4973 / 0.4607 for avg. A millisecond net-flow nowcast (nfms14) was not adopted. Older text below:
   ~0.1-1 s and is cancelled (iteration 10, at server ms: never-filled remainders found in the book in 88%, life p25 94 ms,
   median 240 ms, p75 0.8 s, p90 3 s; the block-resolution "a few seconds" was an upper bound). Holds every position to resolution: no sells, merges, splits or conversions; REDEEM once per
   window; TAKER_REBATE once a day = exactly 0.5 x the previous day's taker fees; MAKER_REBATE once a day. 87.4% of the
   shares bought in a window end paired in complete sets, at a share-weighted pair cost of 0.9786 (VALIDATE).
8. **Fan-out across wallets - VALIDATE-only (live).** Each wallet carries one order at a time: no wallet has two taker
   matches less than 120 ms apart (three live intervals), and same-wallet pairs are 4-9% of the matches less than 300 ms
   apart against 51-52% under independence. One trigger fans out to one or more wallets (17% of events have 2+ legs, always
   on 2+ wallets, usually 1 c apart); DS goes first in ~80%. The number of legs rises weakly with the trigger strength
   (12-16% -> 22-25%; AUC 0.64-0.67 vs 0.61-0.63 for activity).

9. **The decision record: lost races, selectivity - VALIDATE-only (live development block 10-31 12-18; iteration 9).**
   Every cluster order is a decision at the touch. Of 1,041 located insertions of orders whose first fill was a maker fill,
   80% are LOST RACES: the order's limit was o's ask within 300 ms (60%) or 1 s (20%) before it reached the book, someone
   else took that ask first (other takers 53%, the operator's own earlier legs 19%, a maker requote 28%), and the order then
   rested at the old ask. The vote at those insertions is 80.5% (63 / 84 / 86 / 95% by strength), the same as at won races
   (80.6%). A resting remainder or lost race gets a maker fill 46% of the time before its cancel, so the bot makes ~1.45
   decisions per filled order: it is SELECTIVE, not a race lottery. At the top 1% of the decoded hazard it decides ~23% of the
   time (17% at the top 3%), while another taker buys the outcome in ~80% of the flagged instants it skips; its own busy
   slots, other assets (none: the process is BTC-5m-only), a stale-quote edge and the visible depth do not explain the skips.
   XM's 91% maker share and 60-share class on 10-31 are its place at the end of the fan-out (late legs that lose the race,
   vote 79.8%), not a passive quoting component. What selects the decisions among flagged instants is the open part: taken
   vs skipped flagged instants are separated at AUC 0.58 by every recorded public input (0.60 with the operator's own set
   state; a fee-aware edge "8 x Delta x move > half spread + net fee" marks a 6-10x hazard step but reaches 13% of decisions).
   The PnL condition would need ~68% of the decisions reproduced (r ~ overlap x 0.74).
10. **Iteration 10 corrections to the decision record - VALIDATE-only (10-31 14:55-17:55).** (a) Every decision leaves a
   book trace: 88% of never-filled remainders and 97% of later-filled ones are found as insertions at (o, L). (b) The skipped
   flagged instants are genuine non-decisions, not hidden lost races: XM's 60-share legs can be attributed by the fan-out
   fingerprint (>= 313 unfilled ones against 363 filled, all maker-first: XM makes >= 1.86 decisions per filled 60-share
   order), and at skipped top-1% instants such insertions run at 0.24x the taken-instant rate, against 0.53x for crowd
   sizes. (c) Per flagged episode the bot reacts mostly at the onset: first-decision hazard 23-26% at the first flagged
   point, then 2-8% per 100 ms; the onset take rate rises with the onset tick (17 / 28 / 50% by tercile on C); accumulated
   evidence adds nothing (per-step AUC 0.735 instantaneous vs 0.728 with accumulation). (d) Busy wallets do not suppress
   decisions. (e) Per Binance bookTicker event, price-level ticks (29-30%, 34-41% at 0.05-0.2 bp or with the Polymarket ask
   already moving) and multi-venue agreement (3x) mark the decisions; size-only queue depletion does not (= base rate).
11. **Iteration 11 tests of the selection, the size channel and the race - VALIDATE-only (10-31 14:55-17:55).** (a) No
   normalizer: on evt10's event unit (fit A, scored C) the z-scored tick, tick counts and within-window percentile add +0.015
   (CI [-0.002, +0.032]) to the FULL model (0.681); |bp| 0.588 vs z 0.51-0.57; the decision rate is barely elastic to the
   minute's price-level tick count (0.08-0.30) and over-dispersed (var / mean 13). (b) No snapshot / confirmation gate: P(take |
   the onset still in place at +50..+200 ms) exceeds P(take | reverted) by 0.4-2.5 points; price-level ticks almost always
   survive and are taken 29% either way. (c) No cross-market confirmation from the other crypto books (FULL 0.681 -> 0.674).
   (d) The crowd re-timed on the server clock still follows Polymarket activity (venue 0.58-0.59 vs 0.65-0.66). (e) Among
   price-level ticks no public feature separates taken from skipped in both halves (best 0.58); the take rises with the
   operator's own recent decisions (own state; 0 recent: 0 / 19 and 2 / 16 taken), beyond public crowd activity (FULL + crowd
   0.685, FULL + own 0.715 on C): the 'on' periods are a self-exciting internal state, and they are directional (30-s bursts
   |share Up - 0.5| 0.224 vs 0.130 by chance). (f) View lag: limits match o's ask at a - 30 ms best (won races 30 ms, lost
   races 180 ms): the bot reads Polymarket ~30 ms old. (g) Race determinism: an arrival 25 / 50 / 100 ms earlier would have
   won 11 / 21 / 40% of the lost races and later arrivals <= 1%; won races keep their ask for 25-150 ms earlier arrivals in
   87-97%: on a recorded book the outcome follows from the arrival time. (h) Remainder TTL per wallet (median DS 328, GF 240, XM
   124 ms; Weibull shape 0.63-0.77) and refills that fall when the hold rises (09-04: 22.4% -> 17.5%) but not the reverse.
   (i) The 250-ms delay regime as a natural experiment (pmxt archive with server ms, 08-06 16-17 UTC): the crowd's fresh-signed
   floor is 248 ms (186-190 ms on 10-31), each wallet's gap between consecutive taker matches has q01 377-393 ms (152-254 ms on
   10-31), and the cluster's reaction kernel peaks 400-475 ms before the match (250 ms on 10-31): the match lag is the bot's
   reaction plus the hold, and one order per wallet is in flight until its response. Replicated on 08-05 16-17 UTC (crowd floor
   303 ms, XM gap q01 325 ms, kernel peak 500 ms before the match). In August the limits also matched o's ask ~50 ms before the
   arrival (30 ms on 10-31) and a one-series Binance vote agreed 72-76% (placebo 54-56%): same location next to Polymarket, a
   slower venue reaction then (deciding tick 150-250 ms before the arrival vs ~100 ms on 10-31).

12. **Iteration 12: the inventory (net exposure) path and the executable PnL rule - VALIDATE-only.** (a) Per window the PnL
   is the net x outcome (r 0.884 pooled; 0.887-0.921 per wallet); the net's sign matches the outcome in 48.5% of VALIDATE
   windows (54.5% on BUILD). (b) The net path, per window-minute (OLS, HC1 t-values, BUILD / VALIDATE): the current minute's BTC
   move + (t 5.8-7.8 / 4.7-11.1), the earlier minutes' moves - (w0 in minute 1: -3.4 / -11.7; in minute 2: -4.8 / -6.4), the
   previous window's outcome + (minute 0: 3.1 / 2.3; window total 3.5 / 3.8); pre-open M1 / M2 and the spot-vs-strike gap do
   not replicate in sign (minute-0 M2 +3.4 / -2.9): the bot buys the move as it happens and pairs it back later, and nothing
   points at a fair value with another strike. The net after 60 / 120 / 180 s correlates 0.46 / 0.66 / 0.81 with the final
   net. (c) Public predictability of the net: the frozen it4b per-second netflow summed over the window r = 0.458 (Spearman
   0.450), the new nf12b 0.424, their average 0.480; per-wallet models do not beat the pooled one (GF 0.30, DS 0.34, XM 0.05
   for their own nets). (d) The executable rule: `_strict_tracker` (constants `TRK_*`, `MODEL_NF12B`, weights 0.5 / 0.5): target
   net N*(s) = cumsum of the predicted flow; the rule's own realized net R; every free second, if |N* - R| >= 10 shares, BUY the
   deficit (multiples of 10) of the outcome it points to at the last implied ask + 2 c (ask in (0.05, 0.95)); fills only against
   other traders' taker BUY prints at <= limit with block ts in [s+1, s+3] (convention (a); (b) [s, s+2] reported apart), at the
   print price, excluding cluster takers and transactions with a cluster maker fill; next decision at s + 4; unfilled shares
   stay in the deficit. VALIDATE: 119k fills, $569k bought, -3.1% before rebates (-1.6% with the 50% fee rebate); realized net
   vs target 0.993, vs the cluster's net 0.484; per-window PnL corr pooled 0.476 / 0.440, (b) 0.474 / 0.438. Variants (slack 0
   to 5 c, lot 5 / 30, capture 0.5, cluster-maker txs kept) 0.432-0.442 with the it4b target alone. (e) The wallets' per-window
   PnLs correlate only 0.00-0.20 with each other, so per-wallet replication of condition 5 needs per-wallet net predictors,
   which reach 0.05-0.34. (f) Co-occurrence: a net-flow model on market activity alone (other traders' tape state, no spot or
   venue input) drives the same tracker to 0.360 / 0.315; the decoded reference inputs add +0.116 / +0.125 (paired block CIs
   exclude 0). About three quarters of the reproduced PnL co-moves with the crowd's own lean on the same BTC moves.
   (g) Selection side notes (VALIDATE-only, 10-31 live block): the recorded Coinbase ticker adds +0.014 / +0.016 out-of-sample
   AUC to the onset take model in both directions (strong Binance ticks are taken 43-48% when Coinbase has not traded, 22-25%
   when it already moved toward o; weak ticks 3-4x more when Coinbase confirms); the take's window-level heterogeneity is an
   operator-level state with a 30-60-s time scale (own-decision kernel with 30-60-s decay; the 30-s count is inside a 200-draw
   redraw null at 2-minute FE; GF / XM follow the other wallets' recent decisions and are refractory to their own; the wallets
   take the same onsets jointly far above independence), not a sub-30-s self-exciting kernel (iteration 11's finding 13
   corrected); the fast crowd shares the selection and the recorded inputs explain 14-21% of that shared part.
13. **Iteration 15: execution against the visible book (capture L2, 10-20..22) - VALIDATE-only (hypothesis where marked).**
   (a) Size, realized part [VALIDATE-only]: the realized taker fill = the ask depth at or below the limit that survives the 150-ms
   hold. The depth the bot saw at its limit (median 107 shares for depth-bound orders, 190 for all) is ~95% cancelled untraded
   before the match (non-operator takes 3.5%, own other legs 1.0%); public data at the decision predicts the fill at r 0.29. Not in
   the scored rule (the depth-weighted nowcast of pre-registration 8 lost to mix14). (b) Timing [VALIDATE-only]: the operator's
   first legs fall inside a cancellation wave on the bought outcome's asks (near-touch depth 0.85 of its 1.5-s-earlier level at
   200 ms before the match, 0.61 at 100 ms; placebo 1.00) while the other outcome's asks grow; a book-only model predicts the
   take at 0.871 vs the decoded hazard's 0.881. (c) Side [VALIDATE-only, not pre-registered]: the book of both outcomes at
   m0 - 210 ms gives 0.712 alone and dc14 + book 0.838 vs 0.8135 (10-21..22). (d) Price [VALIDATE-only]: per-wallet anchor ask +
   (DS 0, GF 1, XM 1) c within a tick DS 0.947, GF 0.937-0.948, XM 0.795-0.820 per day on 10-21..22. (e) Coins [hypothesis
   rejected for V8]: the salts are not nearby V8 Math.random outputs (validated solver, 0 / 130 groups); a JSC / Bun generator is
   untested. (f) Dispatch [VALIDATE-only]: XM-led first legs carry a broader, earlier information profile (no sharp knee, plateau
   0.785 vs DS 0.837); with those clock features P(XM) reaches AUC 0.79-0.81 and XM's thinning ceiling 0.46 (< 0.47).

## VALIDATE metrics (2026-10-16..23; target thresholds in brackets)

| metric | VALIDATE | target |
|---|---|---|
| scope: fills / abs PnL in the rule's universe | 100% / 100% (every BTC 5m window) | >= 80% (met) |
| presence AUC over BLOCK seconds, no own state, `model_it5_blk_full` | **0.8747** (GF 0.875, XM 0.893, DS 0.857; halves 0.875 / 0.873) | >= 0.85 (met) |
| PURE market-activity baseline on the same bins | 0.8193 -> gain **+0.055**, 2-h block bootstrap 95% CI [0.052, 0.058] | gain >= 0.05, CI > 0 (met with my baseline) |
| STRONGER baseline (pure + dm1, dm2, the other outcome's tape state, Up + Down ask sum; iteration 9) | 0.8211 -> gain **+0.054**, CI [0.051, 0.056]; GF +0.063, XM +0.066, DS +0.051; halves +0.053 / +0.053 | met (not yet: bot-size print counts, W4 removed) |
| one-sided windows vs order-count null (side applicability) | XM 24.3% vs 26.1%, GF 3.1% vs 3.7%, DS 0.2% vs 0.7% (10-31: 3.5 / 6.3 / 0.7% vs 6.1 / 6.8 / 1.6%) | condition applies at >= 20% |
| PnL test-retest ceiling of the TRUE rule, sizes FIXED (race lottery, r = 1 - (1 - q) kappa; iteration 9) | pooled 0.74 [0.71, 0.76] at q = 0.61, 0.80 at q = 0.70; DS 0.62, GF 0.73, XM 0.59 (q = 0.61); simulated 0.70 / 0.77 | upper bound |
| the same with the own-net SIZE FEEDBACK re-simulated (iteration 10, lean10) | pooled 0.47-0.50 (q = 0.61), 0.55-0.58 (q = 0.70); per wallet 0.41-0.62; Spearman 0.46-0.59 | at the 0.5 bar even for the true rule |
| per-window PnL vs large-only PnL / netLarge x outcome; sign(netLarge) = outcome | 0.77 (DS 0.53, GF 0.90, XM 0.81) / 0.75; 48.8% | the PnL is the lean, a coin |
| ITERATION 14: presence on block seconds vs a CAPTURE-AWARE market baseline (others' server-ms prints on o / other outcome, 500-ms bins over [s - 3.5, s - 1); fit 10-17..19, scored 10-20..22) | frozen full 0.8701 vs 0.8464 -> gain **+0.024**, CI [0.017, 0.031]; GF 0.863 / 0.842, XM 0.883 / 0.882, DS 0.851 / 0.828 | gain >= 0.05 (**NOT met**) |
| ITERATION 14: decision-clock take hazard (50-ms bins, label = first leg at m0 - [205, 255) ms; VALIDATE-only, taker first legs) | 0.8885 vs Polymarket-only 0.7591 (+0.129, CI [0.122, 0.137]; vs a stronger Polymarket baseline 0.7623: +0.126; reverse split 0.925 vs 0.781); DS 0.881 / 0.749, GF 0.903 / 0.773, XM 0.919 / 0.841 | (not the pre-registered unit) |
| ITERATION 14: PnL, exposure tracker trk_a with target mix14 = 0.5 x avg + 0.5 x 5.935 x decision-hazard imbalance (pre-registration 7, adopted; 864 windows of 10-20..22) | **0.5065 / 0.4674** (Pearson / Spearman; CI [0.437, 0.5713]; halves [0.4949, 0.5151]; GF [0.4013, 0.3819], DS [0.4665, 0.4477], XM [-0.0009, 0.0228]) against the frozen avg target 0.4973 / 0.4607 | >= 0.5 both (**NOT met**: Spearman; XM fails condition 7) |
| ITERATION 14: side at the decision clock (pre-registration 5; target_metrics.side_accuracy) | **0.8369** per taker order (DS 0.831, GF 0.855, XM 0.813), 0.8236 per decision; market-only 0.568, own-inventory 0.539, old anchor 0.742 | >= 0.80 (met on VALIDATE 10-20..22) |
| presence over ALL seconds (unit pre-registered in iteration 1) | 0.9132 vs pure 0.8781 (+0.035) | |
| selection (size classes + cell score) | AUC 0.869, recall 68.6% at lift 4.63 (pure baseline 0.846) | met; gain 0.023 < 0.05 |
| side, pooled one-sided seconds (n = 90,170) | 76.7% (taker 79.4%); market-only 63.2%; own-inventory-only (short leg) 51.0%; side model + own state 75.5% | >= 80% where it applies |
| side, XM | 72.6% of its one-sided seconds; per taker order 73.1%; one-sided windows by first decision 20/29 = 69% | >= 80% (not met) |
| side per taker order, every order scored (seven 2-h chunks, 13,189 orders) | pool 72.7% (market-only 59.9%); GF 74.6%, DS 71.8% | |
| price within one tick (taker orders) | **95.1%** vs the touch of the same match (calldata); live book 93.2%; tape anchor 53% | >= 80% (met, trivial touch anchor) |
| per-window PnL correlation, EXPOSURE TRACKER (iteration 12, strict fills, latency >= 2 s; `target_metrics.pnl_corr_*`) | **Pearson 0.476, Spearman 0.440** (2-h block CI [0.423, 0.522]; halves 0.460 / 0.487; GF 0.34 / 0.35, DS 0.43 / 0.39, XM 0.06 / 0.05); convention (b) 0.474 / 0.438 | >= 0.5 (not met) |
| the same with the it4b netflow target alone (pre-registered first primary) | 0.441 / 0.419 (CI [0.387, 0.489]); variants 0.432-0.442 | |
| co-occurrence baseline of the PnL rule: the same tracker on a market-activity-only net-flow model | 0.360 / 0.315 -> gain of the reference feeds **+0.116 / +0.125** (paired 2-h block CI [0.075, 0.159] / [0.087, 0.158]) | (reported; not a target condition) |
| primary tracker per VALIDATE day (Pearson) | 0.370, 0.485, 0.511, 0.499, 0.542, 0.452, 0.512 | |
| three-model target (pre-registration 3, not adopted: Pearson not higher) | 0.4756 / 0.4446 | |
| per-window PnL correlation, iteration-4 strict-fill rule (latency >= 2 s, 30 shares; superseded) | Pearson 0.18, Spearman 0.17 | |
| executable replica at the decoded latency, best size rule (presence-weighted) | pool 0.18 / 0.16; own-net size rules 0.13-0.16 | |
| oracle: the wallet's own taker decisions through the frozen fill model (>= 2 s) | true size pool 0.40 / 0.39; 30 shares 0.14 / 0.21 | (ceiling of convention a) |
| oracle: own decisions, fills in the same block window | true size pool 0.68 / 0.66; 30 shares 0.26 / 0.31 | (ceiling of convention b) |
| oracle: own orders, no fill model | 30 shares pool 0.41 / 0.49; size class (30 / 100) 0.88 / 0.87 | |
| B1 ladder check (orders signed in the three predicted bursts) | 99.9% (chance 5%) | (component check) |
| iteration 13: side at the DECISION clock (public HF capture, a = match - 180 ms; fit 10-20 -> score 10-21 and reverse; not frozen) | 77.2% / 77.3% of taker orders at full coverage (GF 81-82%, XM 80-85%, DS 75%); venue-only 76.1-76.3%; Polymarket-only 58.6-58.8%; 81-83% in minutes 0-2, 62-72% after 180 s | >= 80% (not met) |
| iteration 13: `side_decision_clock` in evaluate() (pre-registration 4; spot-book-only exam route, `code/dc_exam13.py`, model fit on 10-17..19) | 74.2% per taker order on 10-20..22 (DS 72.1%, GF 77.8%, XM 78.1%); XM one-sided windows (24.9% of its windows) 81.4% (by day 89.9 / 80.5 / 72.6%); the full venue model (not exam-routed) 76.3% / XM windows 84.3% | >= 80% where the condition applies (XM) |
| iteration 13: price at the decision clock (2,476 calldata taker orders, 10-20 / 10-21) | limit within a tick of the archive ask at the arrival 93.4% (exact 74.3%); per-wallet anchor ask + c_w (0 / 1 / 1 c) 94.5% (XM 83%); touch at the match 81.3% | >= 80% |
| iteration 13: two-stream tracker (pre-registered, not adopted) | 0.4681 / 0.4320 vs the primary 0.4758 / 0.4404 | |
| iteration 13: per-wallet PnL ceilings under PERFECT pooled-stream oracles (condition 7) | pooled net: GF 0.695, DS 0.630, XM 0.304; pooled large lean: GF 0.753, DS 0.339, XM 0.366; XM with its true per-window share 0.406; other wallets' legs only GF 0.420, DS 0.175, XM 0.036 | each >= 0.47 (XM unreachable by any pooled rule) |

Live development blocks of 10-31 (not VALIDATE; reported for the future-block exam, never counted toward the target):

| metric | value |
|---|---|
| side, frozen six-series exam-feed vote | 85.4% on 68.0% of 462 decisions (16:33-17:55); 80.4% on 61.5% (16:04-16:25); placebo 52.7-53.9% |
| side, ten-series lab vote, four intervals | 86.4% / 83.0% / 75.3% / 85.2% of voted decisions |
| side, pre-registered full coverage (in sample) | 70.6% (16:04-16:33), 78.2% (16:33-17:55) |
| presence, frozen decision-level hazard (exam feeds), later interval | AUC 0.656 vs Polymarket-activity baseline 0.598; gain +0.058, CI [0.041, 0.076] |
| price, limit = ask 50 ms before the match | 74.9% exact (171 orders), 93.2% within a tick (277 orders, iteration 5) |
| side / price, point-in-time clean (iteration 10, pre-registered; 16:04-17:55 in sample) | vote [m - 650, m - 180) 83.3% on 67.6% (frozen 83.2% on 65.8%); ask at m - 180 90.7% within a tick (2,581 taker orders) |
| taker delay (iteration 10) | fresh-signed sign-to-match floor 186-190 ms on BTC 5m vs 35-73 ms on no-delay markets; DS taker-match gap q1 254 ms |

PnL convention, pre-registered in iteration 7 before any new replica is scored: the correlation is reported (a) with
latency >= 2 s (fills against other takers' prints in [s+1, s+3]) and (b) at the decoded latency (decision at s from
information <= s-1, fills in [s, s+2]); (b) counts toward the target only if the examiner accepts the decoded latency.

End-to-end `evaluate(1792706400, 1792713600)` (last 2 VALIDATE hours, 51 s, iteration-8 code): presence over block seconds
0.846 vs pure baseline 0.784, side 77.9%, selection AUC 0.884 (recall 72.4% at lift 4.57), price within a tick 96.4%
(calldata touch), strict-fill PnL corr 0.38 / 0.32 (24 windows); the live entries are None (no recording for that period).

## Why it works

- **Iteration 15, who loses and why the fills are small:** the operator and Polymarket's makers react to the same Binance move. Most
  makers pull their stale asks within the 150-ms taker delay (the depth at the bot's limit falls ~95% before its order executes,
  almost none of it traded), so the operator is paid by the SLOWEST makers, whose asks are still there when the hold ends; the
  delay that Polymarket added to protect makers is exactly what caps the operator's fills. The race is against makers'
  cancellations, not against other takers (3.5% of the vanished depth). [VALIDATE-only]

- **Iteration 14, the edge in one line:** the bot is a latency arbitrageur of the Binance SPOT queue imbalance against Polymarket's quotes. It sits next
  to Polymarket's engine, sees Binance ~80-110 ms after the stamp, and lifts the outcome the spot book is moving toward before the makers requote; the
  makers who lose are those whose quotes lag the spot book by more than the 150-ms taker delay plus its route. Sizes are an operator experiment (A/B arms).

- **It buys complete sets below 1 by sniping stale quotes on both sides, and the fee rebate pays for the fees.** In the
  VALIDATE week the cluster bought both outcomes of almost every window; 87.4% of its shares ended paired at a pair cost of
  0.9786, so each pair locks ~2.1 c. Gross trading PnL before fees was $65,960: $48,923 from locked sets and $17,037 from
  the unpaired remainder. Fees were $61,572 and Polymarket paid back exactly half of the taker fees ($30,786) the next day,
  plus ~$3k of maker rebates. Net ~ $38k for the week, of which the taker rebate is ~80% (all rebates ~88%); trading
  alone made +$4.4k after fees.
- **Who pays:** makers whose quotes lag the perps' top of book. A queue depletion or price tick of the BTC/ETH perps shifts
  the fair value of the 5-minute digital; ~250-350 ms later the bot lifts the ask before the makers (mostly complementary
  BUY orders, i.e. the other side of a mint) reprice, and it does so most often while the Polymarket touch is already
  moving. Each pre-signed order is one HTTP submission; one order in flight per wallet is why it runs several wallets.
  It competes with a crowd of fast takers: at the instants its trigger flags most strongly another taker buys the outcome
  ~80% of the time, and a race the bot loses leaves its order resting at the old ask, where it is filled as a maker about
  half the time (no taker fee on that fill).
- **What loses:** the large-size overlay. The bot uses its large size when its own book is flat or long the outcome, so the
  large orders build the window's unpaired position; they lose 1.1-1.9 c per share after fees and carry most of the
  per-window PnL variance (per-window PnL vs the unpaired part r = 0.93; vs large-only PnL 0.77). The lean is a coin with
  respect to the outcome (sign(netLarge) = outcome 48.8%): it adds variance, not edge. Iteration 12: the net path follows
  the current minute's BTC move and is bought back against the earlier minutes' moves, so the window lean ends independent
  of the outcome; an executable copy of that lean from public data loses 3.1% before rebates (-1.6% with the 50% rebate).
- **The race:** Polymarket holds every marketable order on these markets for 150 ms, so the bot and the crowd of fast takers
  queue in the same delay buffer after the same venue ticks; the bot wins ~70% of its DS / GF races and XM, whose leg comes
  last, wins none of its 60-share races on 10-31 (they all rest at the old ask and some fill as maker). The queue matters:
  with no crowd order ahead in the buffer DS wins 80% and GF 72%, with one or more ahead 69% / 61% (iteration 10); the rest
  of the lost races are maker requotes during the hold. The crowd it races is mostly driven by Polymarket's own activity
  (its fresh-signed decisions are predicted better by Polymarket trades than by the venues), the bot by the venue ticks.

- **The inventory loop (iteration 13):** the window's unpaired position is built by the LARGE leg (fanned out to every wallet,
  pyramided) and taken apart by the SMALL leg, whose side tilts toward the complement of the operator's REALIZED large fills
  within ~2 minutes (t -26.5 beyond the side model; a small-fill placebo and the crowd's flow do not do this). The small leg
  turns lean into locked sets; what is left unpaired at the end is the coin that carries the per-window PnL variance.
  The side of each submission follows the last 100-250 ms of the Binance spot / perp microprice (77% of taker orders on
  VALIDATE weekdays at the true decision instant, 81-83% in the first two minutes), i.e. the bot is paid for being ~100 ms
  faster than the makers it lifts, not for a better forecast of the outcome.

## Can a normal user deploy it now

- **Iteration 15:** what a copy would receive is the makers' leftovers after the 150-ms hold, and that leftover is decided after the
  decision (r 0.29 from public data at the decision). A replicator that fires on the same Binance move from a normal connection
  arrives after the faster makers have cancelled and after the operator; it would fill even less. Nothing changed in the
  conditions on the latest development data (10-20..22 capture; rec_bn15 records 11-01 06-12 for the next check).

- **Iteration 14:** the decision needs a host near Polymarket's engine (London) with a direct Binance spot feed arriving within ~100 ms of the stamp, and
  the information is a 60-ms band: a home connection or a slower relay (the public collector receives Binance ~131 ms after the stamp) loses most of it
  (74% side at an anchor 50 ms too early). A copy executed >= 2 s later earns about -3% before rebates (exposure tracker).

- Location (iteration 11): the bot's limits match the Polymarket ask ~30 ms before its order arrives, while its reaction to
  Binance comes ~100-150 ms after the Binance stamp: it runs next to Polymarket's matching engine and sees Asian venues late,
  like any European host.
- Dependencies: low-latency websockets with sized top of book from Binance USD-M (and spot), OKX and Bybit (BTC and ETH),
  a reaction time of ~250-350 ms from a perp tick to a Polymarket match (of which 150 ms are Polymarket's own taker delay,
  the same for everyone, and ~100-150 ms the bot's own processing and posting), a
  pre-signed order ladder (any TypeScript clob-client user can do this), several wallets for parallel orders, ~$2.5M per
  week of order flow, and the 50% taker rebate (paid per wallet on its own fees). These conditions held through 10-22 and on
  10-31 (same signing schedule, same pay-up shares, sizes 30/60/100, TAKER_REBATE rows daily).
- Iteration 12: the exposure tracker (the executable rule that reproduces the cluster's per-window PnL best, r 0.48) bought
  $569k on VALIDATE with >= 2 s latency and lost 3.1% before rebates (-1.6% with a 50% fee rebate): copying the bot's net
  exposure from public data at a normal latency does not make money; the bot's edge is in the pairs and the rebate, not in
  the lean.
- A replicator with a normal connection: with >= 2 s latency and strict fills the frozen rule bought $262k on VALIDATE and
  lost 1.6% before rebates (+0.1% with a 50% fee rebate); at the decoded latency the replica bought $0.75-1.25M at -0.3% to
  +0.5% before rebates for every size rule tried. Without the rebate a slow copy loses money; with it, it roughly breaks
  even. Dropping the large-size overlay would raise the bot's own return (small orders earn +0.2 to +1.3 c per share).

- Iteration 13: the decision-clock side needs only public, historical data (the CC0 Hugging Face capture of Polymarket's market
  channel and the Binance spot book at ms), so the side rule is reproducible by anyone near London; the edge it reflects is
  speed against stale makers inside Polymarket's 150-ms taker delay, which a home connection does not have.

## Known limitations

- **Iteration 15:** (a) condition 2 is not met by any pre-registered unit so far: at the block clock +0.024 over a capture-aware
  baseline; at the decision clock +0.008 [0.002, 0.013] over a BOOK-aware market baseline whose book ends at e + 50 ms, but +0.058
  [0.050, 0.065] when the book ends at e, before the bot's own Polymarket view (finding 12). An examiner who adds book depth cut at
  e + 50 will find the gap closed; the cut has to be pre-registered from the bot's measured view (arrival - 30 ms) before any claim.
  Per wallet at the e cut: DS +0.059, GF +0.061, XM +0.030, so XM's presence part fails condition 7 even then. (b) condition 5: about 0.3 of the window-net r on the true
  decisions is the makers' cancel race inside the hold (measured on the capture L2); the adopted mix14 tracker stays at 0.5065 /
  0.4674. (c) condition 7: XM's PnL ceiling 0.43-0.46 < 0.47 (thin14 / thin15); the price part now holds per wallet with the
  iteration-13 anchor (VALIDATE-only, not wired into evaluate(): target_metrics.price_within_tick stays the trivial touch anchor).
  (d) The L2 ingest exists for 10-20..22 only (session scratchpad); code/l2ingest15.py rebuilds it from the capture for any
  development day (2 threads, ~12 min per day).

- **Iteration 14:** the decision-clock components (side, take hazard, the mix14 PnL target) read a public third-party capture
  (Hugging Face Fahri-5/updown-5m-polymarket-raw, revision pinned); if its exam-day files are missing the routes report errors and
  target_metrics fall back to the block-clock side and the avg tracker. The capture-aware presence baseline (pres14.py) is offline only.
  The hazard labels taker first legs (77.9% of fills with their remainders, 86.3% of |PnL|).

- Iteration 13, condition 7 is a MEASURED limit for XM, not a missing input (results/two13.json, share13.json). Per-wallet PnL r against PERFECT
  oracles of the pooled operator streams: pooled net x outcome GF 0.695, DS 0.630, XM 0.304 (halves 0.32 / 0.29); pooled large lean GF 0.753,
  DS 0.339, XM 0.366; BUILD-loaded L + S GF 0.766, DS 0.640, XM 0.218; XM's TRUE per-window gross share x the perfect pooled net 0.406; the
  other wallets' legs alone GF 0.420, DS 0.175, XM 0.036. XM's PnL is the side of its own dispatched legs, and the wallet that carries an
  order is barely predictable from public state at the decision clock (multiclass accuracy 0.61-0.68 vs base 0.61-0.67). With the current
  public predictions the per-wallet tracker values are GF 0.34, DS 0.43, XM 0.06. Any pooled rule fails condition 7 for XM on VALIDATE.
- Iteration 13, the side at the block clock: its inputs (spot closes <= block ts - 2 s, others' prints <= block ts - 1 s) end a median ~0.2 s
  AFTER the operator's match (block - match 1.25 / 2.20 / 3.14 s), so part of the 76.7% is post-decision continuation. That is legal under the
  block-time PIT rule but is co-movement rather than the decision's input. At the true decision instant (public HF capture) the public
  venues give 77.2-77.3% per taker order at full coverage (VALIDATE 10-20 / 10-21), not yet frozen into evaluate() (exam route: X113 step 6).

- Iteration 12 supersedes the decision-replay account below for the pooled PnL condition: the exposure tracker reaches
  0.476 / 0.440 under the >= 2 s convention (above the 0.40 'oracle' of the wallet's own decisions, because it re-sends
  unfilled shares instead of dropping them). The binding term is now the public predictability of the window net (r 0.48).
  Per wallet it is 0.06-0.43, and the wallets' leans are nearly independent of each other: condition 7 (per-wallet
  replication) is not met for XM (and not for GF) by any rule found so far. The PnL rule uses capture 1.0 (upper bound);
  capture 0.5 changes it by -0.003.
- The frozen tape features exclude the three dossier wallets but not the operator's fourth / fifth fan-out wallets (W4
  0xd844..., W5 0x03b4...), whose legs precede 7.4% of the cluster's taker seconds. Rebuilding VALIDATE without them leaves
  every metric unchanged (presence 0.8747, gain +0.0557; tracker 0.4756 / 0.4394; iteration 12, w45chk12.json); the exclusion
  is still not coded in `final_rule.py`.
- The PnL condition (decision replays, iterations 7-11): under the >= 2 s strict-fill convention no rule can reach 0.5 pooled (the wallet's own decisions and
  sizes give 0.40). At the decoded latency the ceiling is 0.66-0.70 with the right size class, but the executable replica
  built from block-second decisions reaches 0.13-0.18 whatever its size rule (iteration 8): the gap is decision overlap.
  Live, at the decoded latency, the frozen hazard flagging as many 100-ms instants as the wallet's matches catches only
  8.2% of them (lift 2.75): the trigger is necessary but not sufficient. Iteration 9 showed this is not a lottery wall: the
  true rule replayed would correlate 0.74 pooled (0.59-0.73 per wallet) with the wallet (the model reproduces the measured
  split-half correlations exactly), and the bot makes only ~1.45 decisions per filled order. Iteration 10: that ceiling held
  the sizes fixed; with the own-net size feedback re-simulated (large orders pyramid the leg the operator holds) the true
  rule's test-retest correlation is 0.47-0.58 pooled and 0.41-0.62 per wallet, so condition 5 is at the edge of what a
  perfect decode can reach, and a replica that reproduces only part of the decisions cannot reach it. Iteration 11 revised this:
  no realized-fill feedback is detected (after a won vs lost large race the next same-outcome decision is large 19% vs 27%;
  the sent net predicts the size as well as the realized one), so the fixed-size ceiling 0.70-0.77 applies to a replay that
  reproduces the decisions, and on a recorded book the race outcome follows from the arrival time (lost races flip in 4-7% at a
  25-50 ms timing error). The binding terms are decision overlap (the onset selection, not decoded) and the large-size regime;
  under the >= 2 s convention even the wallet's own decisions with true sizes reach 0.40.
- The weekend regime: quiet one-sided seconds are 28% on weekend days vs 15% on weekdays (VALIDATE), and the live
  weak-vote share was 44-56% on Saturday; the first future-block exam (weekend sealed blocks) will be scored in that regime.
- The live side: per decision strength it is stable (90-97% on strong votes) but the weak / no-vote decisions (31-45% of
  live decisions) are 64-80% at best, and their Polymarket fallbacks were not stable between intervals; the full-coverage
  rule is pre-registered and untested out of sample. At the block clock every decision scores 72-79%.
- Presence passes only in the block-second unit (+0.055 over my pure baseline, +0.054 over the stronger baseline of
  iteration 9 with the other outcome's state and 1-2 s price changes; DS +0.051 is closest to the bar); the examiner's own
  baseline may be stronger still (bot-size print counts, sub-second intensities and W4's prints are not yet in mine).
  Selection gain over the pure baseline is +0.023 (< 0.05). The decision-level hazard gains +0.058 out of sample but at an
  AUC of 0.66 (0.73 when lost races count as decisions, lab feeds).
- Maker fills: half of the 10-31 filled shares are maker fills of lost races; their limit is the ask the bot saw 150-1,000
  ms before the order reached the book, which a historical (block-clock) rule cannot see. The 95.1% price figure covers
  taker orders only.
- Price uses the touch of the match itself (calldata) for historical lots: it measures the decoded rule, not a PIT
  forecast of the touch; live, the recorded book 50 ms before the match gives 75% exact and 93% within a tick.
- The size rule uses own state (the operator's net); without own state the size is not predictable.
- A fourth wallet (0xd84403ef...) runs the same bot; its prints still count as "other traders" in the tape features.
- Versions: the rule describes the three-burst pre-signed-ladder version that runs since 08-22 (VALIDATE, 10-31 and the exam
  lots are all in it). Before 08-22 the bot pre-signed on two-burst schedules at other phases with one size per day (iteration
  11 correction), so the burst check and the size menu do not apply to that history.
- The selection among trigger onsets (which ~1 in 3 the bot takes) is not decoded: every recorded input separates taken from
  skipped onsets at out-of-sample AUC 0.58-0.74 (grid points, events, crowd-flagged instants); busy wallets, accumulated
  evidence, queue depletion, the stale-quote edge, visible depth and competitor identities were ruled out as the selector.
  Iteration 11 added a self-kept vol normalizer, a snapshot / confirmation gate, cross-market confirmation and the crowd's
  server-clock timing to the ruled-out list; what remains is internal to the bot (its own recent activity) or unrecorded
  (European venues, alt perps, the maker at the touch, the PRNG): recorders for the first two run from 11-01 05:59 UTC.
