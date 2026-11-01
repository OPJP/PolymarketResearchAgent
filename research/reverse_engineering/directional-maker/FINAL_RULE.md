# directional-maker: frozen rule R8c (iteration 17 = R8 + the NYSE-open window side; R8 = iteration 12, R7 + the window state-machine side; iterations 13-16 and 18: reporting blocks added)

**Iteration 18 (no frozen decision changed; R8c stays; one reported block added: `quote_unit_side.law_E2` in
`code14/qu_dx.py`).** Tag of the new block: hypothesis (confirmed on two held-out blocks that the live split counts as BUILD;
the live VALIDATE blocks 11-02 / 11-03 are pending). What iteration 18 established (NOTES.md "Iteration 18",
results/iter18_*.json):
- **Two event inputs of the post side (X220, information panel I17-1).** Law E2 for the side of each at-touch 500/1000
  post (0.10-0.90): (1) a public Chainlink BTC publish in (t - 150 ms, t] whose report-specific innovation u (the report
  change minus a futures-only prediction from four 0.5-s increments of the Binance USD-M mid, beta frozen on 11-01 07-08) has
  |u| >= $1 -> the outcome u favours; (2) else a futures-mid move >= $2 over [t - 500, t - 50] ms -> its direction; (3) else
  the posture. Untouched 11-01 09:15-12:00 (1,108 posts): E2 0.642 vs posture 0.520 (|F - mid| < 0.05: 0.590 vs 0.467);
  10-31 17:29-18:00 (noise regime, 418): 0.804 vs 0.713. Posts in (0, 150] ms after a publish agree with sign(u) 0.80 (n 45)
  and 0.86 (n 132) against 0.53 / 0.40 in (-300, 0] ms: the engine reads the report at public-relay timing and never before
  it (no Data Streams lead, third block). Three quarters of the clean-block posts follow neither event (posture 0.57-0.66).
  In the exam path (dx_clob, dx_bnf, dy_rtds) E2 scored 0.684 vs 0.536 on 11-01 09:15-10:15. Live-only: it needs the
  recorders (to 11-03 00:00); it does not change the historical per-fill side.
- **Scheduled volatility (X215 / X219 / X225 / X227): a cluster-only gradient, not a decoded input.** The October cheap
  share rises with the time-of-day vol profile for the cluster (slope +0.229, p 0.002) and not for the other makers in the
  same windows (-0.013). But a profile posture (sigma = k x max(v300, P), chosen on BUILD) does not beat R8c (VALIDATE 0.6906
  vs 0.7009; open window 0.13 STUDY / 0.67 VALIDATE), the weekly k drift is not the profile (rho 0.16), the 11-01 centre is
  not explained by it, and the money is not there: October return per $ in the top forward/trailing-ratio quintile -2.5%
  (cheap fills -4.1%) vs +1.6% to +3.8% in the others (exact outcomes from the cluster's REDEEM rows).
- **The open window is a fixed fade (X223):** the cheap share is 0.92-1.00 in all 17 development/STUDY open windows,
  whether or not the equity open confirms BTC's first-minute move (0.983 vs 0.988), even with no BTC move. Its clock (13:30
  UTC vs 09:30 New York) is recorded live at full depth on 11-02 (code18/open_rec.py, X218).
- **Presence by order type (X226):** of the VALIDATE FN cells, 65% hold a fresh main-ladder fill (FN share 0.635) and 34%
  only pairing / deep / remainder fills (0.733): the quiet-cell taker arrival is the main unexplained part.

**Iteration 17 (one frozen decision changed: R8 -> R8c; tag VALIDATE-only).** The side of the BTC 5m window that starts at
the NYSE open (09:30 America/New_York on weekdays; 13:30 UTC under US DST, 14:30 UTC from 11-02) is the cheaper token,
whatever the Chainlink posture says (`code/side_sm.py` `nyse_open_window`; counted side `r8c_no_own_state`, R8's
`no_own_state` still reported). It was found in the out-of-fold BUILD residual (E2: the 13:30 UTC weekday window held
702 decisions in 10 windows, 4x the usual count, 0.90 of them against the posture, at a mean price 0.23) and passed its
pre-registered test: in that window the cheaper token is right 0.99 on STUDY (2 windows) and 0.90 on VALIDATE (4
windows), R8 0.40-0.44; per BTC 5m fill VALIDATE 0.6925 -> **0.7009** (STUDY 0.569 -> 0.577). The other iteration-17
measurements did not change the rule: the presence residual out of fold (BUILD AUC 0.780 vs activity 0.741) is quiet
small-edge cells; the fill-level side misses show no cross-market synchrony (E7 ratios 1.34-1.50, p 0.04-0.23, below the
hits' 1.95-2.22); the 11-01 side drop is not the taker mix (taker commit-to-match classes reweighted: 0.844 predicted vs
0.675 actual); the venue's 150-ms taker hold is visible in the floor of the takers' commit-to-match latency (p5 187-193
ms). Details in NOTES.md (Iteration 17, Missing dimensions) and results/iter17_*.json.
Version caveat (C4, measured on the whole activity history): the open window is busy in every month since May (30-73
fills per window vs 14-31), but the cheap-token behaviour is new in October (cheap share May 0.06 ... Sep 0.64, Oct 1-8
0.997); before October the cluster bought the favourite at the open. R8c therefore describes the October configuration
(every October fold agrees) and is untested across the 11-02 DST change (NYSE open 14:30 UTC).

**Iteration 16 (no frozen decision changed; R8 stays; two reported blocks added from `code/r10_mode.py`: `instance_mode`
and `side_nowcast_match_clock`).** `instance_mode` tabulates, per 15-min slot, which wallets run the main BTC ladder
(mid-band 0.10-0.90 BTC 5m + 15m BUY fills per wallet; a slot is "split" when one wallet holds >= 0.80 of >= 20 fills).
`side_nowcast_match_clock` scores the per-fill side on the live match clock under the Chainlink report stamped <= T - 1,432
ms and under the latency-corrected nowcast S_now = CL(s) + F(T - 50 ms) - F(s), F = the Binance USD-M bookTicker mid
(dx_bnf, else dm_bnf), k 1.0 x the futures 300-s sigma, per wallet and per |F - mid| band; `r9_nonbtc_module` also scores the
hourly / daily / 4h fills against the CLOB prices-history minute mid (`posture_prices_history_k1.0`). Tag: VALIDATE-only, reported,
not counted. What iteration 16 established (details in NOTES, results/iter16_*.json):
- **Engine instances (hypothesis -> measured):** on 11-01 one wallet (bosona) ran the main BTC ladder alone in 7 of the 10
  qualifying 15-min slots to 10:00 (mo-money joined only 08:30-09:15); almach and mo-money kept the deep bids (<= 0.10 /
  >= 0.90) and the slow families. This never happened in a STUDY or VALIDATE slot (0 of 466) and in 0.9% of BUILD slots: a
  new mode after the sealed stretch 10-31 18:00 - 11-01 06:00, reported per slot as `instance_mode`.
- **The side inside one instance:** bosona's own fills on the match clock keep their large-edge behaviour across the two
  blocks (|F - mid| >= 0.1: 0.860 on 10-31 vs 0.864 on 11-01), but its small-edge fills fell below chance on 11-01
  (0.44-0.58 vs 0.72-0.87) and the large-edge share halved (0.80 -> 0.40). So the 11-01 failure is not composition; the
  reference stopped carrying information at small edges.
- **Nowcast:** the Chainlink level moved by the futures since the report's stamp is never worse than the bare report and
  helps in the clean regime (11-01 pure 500 posts 0.546 -> 0.632, fills 0.560 -> 0.685; 10-31 0.779 -> 0.785 and 0.852 ->
  0.848), k frozen at 1.0 on 10-31; it does not beat the cheaper token by the pre-registered 0.08 on the clean block. On
  the clean block a quarter of the at-touch 500 posts are re-pegs within ~0.5 s of a futures move (on the outcome whose
  fair rose: 0.89-0.96); the rest sit on the cheaper token (0.70).
- **Ladder center:** per publish pass the half-spread is the same on both blocks (median 0.075); the center moved 0.30 of
  the way from the mid to the Chainlink fair on 10-31 (R2 0.52) but only 0.13 on 11-01, with a shrink toward 0.5 of 9% of
  (0.5 - mid) (best single k 2-3): the configuration that moved is the center's fair, not the spread. A fair-capped join
  (min(touch, floor(F - h))) predicts the re-signed top rung within a tick only 0.14-0.27: rejected.
- **The idle module:** a strict per-market replay of the decoded alt opening tracks the cluster's per-market PnL at only
  0.08-0.19 Pearson (0.10-0.31 Spearman), 0.37-0.42 with the cluster's own first-fill side as an oracle: the later
  two-sided fills carry the per-market PnL, so the outcome bar is out of reach there too. On the thin alt books the fill
  sits at the best bid before the match (0.72 within a tick vs R7 0.56; one block, n 72). At the alt open the cluster
  reads the settlement-grade per-symbol Chainlink against priceToBeat (VALIDATE: on the fills where it disagrees with
  the Binance stand-in the cluster follows Chainlink 9 of 9; Binance against the true strike is a basis-mismatched
  comparison, 0.45-0.54). Final (1,915 endpoint values): the opening posture on the per-symbol Chainlink against priceToBeat
  is 0.916 BUILD / 0.941 STUDY / 0.882 VALIDATE (Binance stand-in 0.890 / 0.931 / 0.864); the two references disagree on only
  2-4% of opening fills, so the VALIDATE half split (0.94 / 0.82) remains.
- **Long families against CLOB prices-history (a point stamped t = the mean mid of the minute before t; examinable for
  sealed units):** the daily later fills follow a Binance-digital posture against that mid at 0.74-0.75 on STUDY and
  VALIDATE (market favourite 0.51-0.59), the first public side rule for the dailies; hourly and 4h later fills stay at the
  favourite level (0.52-0.70); no fixed offset from the mid prices them (0.22-0.55 within a tick).
- **The BTC 4h module (where the idle money is):** its 400-share orders are a pure label (calldata purity 1.00; the 600s and
  the ETH 300s are another maker's). Its adds rest a median 5 c below the touch (6.5 c below the mid; 3% at the touch) and
  sit on the cheaper outcome 0.67, on the Chainlink posture side only 0.39-0.59: a resting ladder under the market that
  takers sweep, leaning to the underdog. The alt 5m/15m configured sizes (50 / 30 / 10) are other makers' sizes too
  (purity 0.00-0.03), so the alt module can only be read from fills.
- **Rejected this iteration:** R8b (dead zone -> cheaper token; VALIDATE 0.686 vs R8 0.693, STUDY 0.521 vs 0.569) and the
  fair-capped join on the main ladder (0.14-0.27 within a tick).


**Iteration 15 (no frozen decision changed; R8 stays; one reported block added: `r9_nonbtc_module`, `code/r9_nonbtc.py`).**
`evaluate()` now also reports the scope of R8's universe against every crypto Up/Down family (pooled, per wallet and per
examiner-style half: window start before / after the period's median listed start) and the side of the cluster's fills
outside BTC 5m/15m under two unfitted rules: **itm** (public, sigma-free: buy the outcome in the money under the family's
Binance reference, Up iff S(T - 3) > K; K = the Binance TWAP-60 stand-in for the Chainlink TWAP families 5m/15m/4h, the
hour's Binance open for hourly, Gamma priceToBeat for daily) and **posture_fillprice** (a description that uses the fill's
own price as the market price: buy s iff Phi(ln(S/K) / (1.0 x sigma300 sqrt(tau))) of s exceeds the fill price), with the
market-favourite, cheaper-token and always-Up baselines, plus **posture_public_k0.7** (public: the same posture with k 0.7
against the price implied by the last clean taker print stamped <= T - 2; dailies skipped). The live readers now also require each record's server stamp to
lie in a development block (X167, the laptop clock drifts ~0.19 s/h). Tag: VALIDATE-only, reported, not counted.
What iteration 15 established (details in NOTES, results/iter15_*.json):
- **The non-BTC module (idle weekend blocks):** sizes are a configured table per family, identical in the three wallets
  (BTC hourly 38 / 300, BTC 4h 400, ETH 5m 50 / 150, ETH/SOL 15m 30, SOL 5m 50 / 100, XRP 5m 10 / 50, BNB 5m 10, DOGE 5m
  10 / 40, dailies 50); not reward-driven (rewardsMinSize 50 on every family). Its opening fills (< 20 s) buy the outcome
  in the money under the family's Binance reference: 0.814 BUILD, 0.72-0.90 STUDY, 0.778 VALIDATE, against the market
  favourite 0.62 / 0.48-0.77 / 0.49; later fills follow the market favourite (0.55-0.75); all non-BTC fills 0.58 on
  VALIDATE (market 0.54). Against the last PUBLIC print (the last clean taker trade <= T - 2) a Binance-digital posture
  with 0.7 x the symbol's 300-s volatility picks the opening side at **0.866 on VALIDATE (n 494), 0.924 on STUDY and
  0.882 on BUILD (n 2,027)** (market favourite 0.54 / 0.61 / 0.62): the opening quote of the alt families is decoded on public inputs; after the open no
  public rule beats the market favourite (0.55-0.70), and after the open the module buys both outcomes about equally (later
  fills on the opening fill's outcome 0.44-0.50). The opening buys, decoded or not, are break-even to losing (posture-agreeing
  opening fills -0.4% BUILD, -16.1% STUDY, -1.3% VALIDATE per $); the module's profit is in the later 4h
  and hourly fills (+5-10% per $, Binance stand-in settlement). R9's planned cheaper-token fallback is the anti-rule there
  (0.39-0.46) and is not used. Print-level selection on these families fails (frozen score 0.62 vs an activity score 0.73:
  the taker's order size selects the cluster's fills).
- **Scope on the examiner's halves:** R8's universe holds 0.86-0.87 of trades in the earlier halves of the 10-10/11 and
  10-17/18 weekend mock lots but 0.41 (10-17/18 later), 0.39 and 0.28 (10-24/25): only every crypto family meets the
  scope bar in every half.
- **The BTC quote unit:** on pure labels (500 posts at bids between 0.03 and 0.97) the posture side is 0.779 with the safe
  lag and **0.866 on the exact publish clock** (10-31 17:29-18:00, n 447); publish-anchored cells (one per public
  Chainlink publish) rank the next 300 ms of 500 posts at AUC 0.794 (outcome 0.866) with no fitting, and the placebo
  before the publish falls to 0.625 (the change in posture from the previous report predicts the posts after the publish
  at 0.665 and anti-predicts those before it at 0.429): each published report re-sides the ladder. **But on the second
  development block with books (11-01 07:00-07:50, Sunday, 279 pure 500 posts) the quote side is 0.624, below the
  cheaper token (0.663): not replicated yet.** Why (post hoc): the Chainlink noise regime ended (1-s sd of the Chainlink
  stream over the futures mid: 8.2 on 10-31 14-18, 0.92 on 11-01 07-08); in the noise regime the report sat far from the
  market (56% of posts at |F - mid| >= 0.1, accuracy 0.94 at >= 0.2) and the engine followed it; in the clean regime the
  disagreement is small (27% at >= 0.1) and the posts follow the posture less (0.78 at >= 0.2, 0.52-0.61 below 0.1). The
  quote-side level of iterations 13-14 is regime-specific. The settlement-average variance law does not beat one global k.
- **R8 through evaluate() on the development hour 11-01 07:00-08:00 (clean regime, 216 BTC 5m maker fills):** per-fill
  match-clock side 0.740 vs the cheaper token 0.736; R7 price 0.912; BTC 5m presence 0.580 vs activity 0.609; R8 universe
  0.78 of trades (earlier half 0.54; almach 0.51, mo-money 0.52): the weekend scope problem appears on a live development
  hour too.
- **Per wallet (crude, own fills of 10-31 14-18):** mo-money's resting rungs match the posture of about 1 s before the fill
  (class ii 0.62 at the fill, 0.75 at fill - 1 s) while bosona's and almach's match the current one (0.78-0.87): a slower
  cancel / re-side path in mo-money's engine instance accounts for part of its per-wallet deficit.
- Corrections: the "62/250 posts at chance" of iteration 14 are other makers' orders and deep rungs (mechanics panel's
  calldata), not the off-session ladder; the weekend "non-schedule sizes" are the per-family configured sizes; the 1000s
  at the touch on 10-31 are another maker's bids at >= 0.97.


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
| Engine | One engine runs three wallet processes (iteration 16: on 11-01 bosona ran the main BTC ladder alone in 7 of 10 slots, mo-money joining only 08:30-09:15; split slots 0 of 466 in STUDY/VALIDATE): per-wallet sequential salt; the daily ~01:00 UTC restart resets all three counters within ~20 s; ~11-18 signed orders/s per wallet; until ~06-21 every order carried its real signing ms, since 06-22 `timestamp`, `metadata`, `builder` are 0. | VALIDATE-only | B1 calldata (lot, June, 10-31); `code9/m4_*.py` |
| Information | The ladders are re-priced on each Chainlink BTC/USD report (the settlement stream) within ~0-150 ms of the public RTDS relay's publish; between reports its 500s re-post 50-250 ms after Binance futures moves (June: signed 100-400 ms after Binance moves). No lead over public feeds. | VALIDATE-only | `code7/i2_publish.py`, `code8/june_lag.py` |
| Selection | **Iteration 18 (hypothesis; own state where noted):** switch-offs follow rolling 6-h realised losses (AUC 0.685, p 0.0075 over 16 off stretches; own state) but not at a fixed level; no hourly association with GDELT news volume or Binance vol (half the GDELT hours were refused); the per-wallet signing rate (~12 orders/s) does not change when the BTC 5m module stops, so it cannot label the module state. One engine over crypto Up/Down. BTC 5m and 15m are modules switched off for hours, mostly from Friday-Sunday US-Eastern evenings to the next morning (calendar gate window AUC 0.68 for BTC 5m, 0.63 for 15m, since 10-16). The 10-31 16:53:54 UTC switch-off happened inside the running processes (salt counters continuous, signing rate unchanged) and two engines were restarted ad hoc 12-13 min later. R6's universe holds >= 80% of trades and dollars in only 34% of 6-h development blocks (0% in weekend 00-06 UTC blocks); only the all-crypto universe does in every block type. BTC 15m presence (R3 class) 0.812 vs 0.778 activity on VALIDATE. | hypothesis (on/off); VALIDATE-only (15m presence) | `code9/scope.py`, `code9/m4_salt.py`, `code8/train15.py` |
| Timing | **Iteration 18 (hypothesis: held-out BUILD blocks, live VALIDATE pending):** two event inputs re-side the at-touch posts: the report-specific Chainlink innovation within (0, 150] ms of the public publish (agreement 0.80 / 0.86 on two held-out blocks, 0.40-0.53 before the publish) and a futures-mid move >= $2 over the last 0.5 s (0.90 of those posts); law E2 0.642 vs posture 0.520 on the untouched 11-01 09:15-12:00 block; reported as `quote_unit_side.law_E2`. Re-price passes on each Chainlink publish plus re-posts after Binance moves; filled orders are fresh 500-share posts at the touch (78%), matched ~0.7 s later; it stops ~30 s before the end; its filled rungs agree with the report in force at the match, not at the taker's signing (M5). July engine (pmxt): posts a median 69 ms after the market's previous trade, filled orders ~1.0 s old, 49% at the touch. | VALIDATE-only (live) | `code6/q1_confirmed.py`, `code7/i2_publish.py` |
| Side | **Iteration 18:** the October cheap lean grows with the time-of-day vol profile for the cluster only (slope +0.229, p 0.002; other makers -0.013), but a profile posture does not beat R8c (VALIDATE 0.6906 vs 0.7009) and the open window is a fixed fade (cheap 0.92-1.00 whatever the equity open does): R8c stays (hypothesis for the mechanism, VALIDATE-only for the rule). **Iteration 17 (R8c, VALIDATE-only):** the BTC 5m window starting at the NYSE open (09:30 New York, weekdays) -> the cheaper token (open window: STUDY 0.99, VALIDATE 0.90 vs R8 0.40-0.44; all VALIDATE fills 0.6925 -> 0.7009). Hypothesis inside it: the clock is the exchange's (09:30 New York), not a fixed 13:30 UTC; development data cannot separate them (all under US DST). **Iteration 12 (R8).** Counted, public: decided window -> the cheap loser (= the cheaper-token baseline; a deep-bid module ramped from Monday 10-26: <= 0.10 orders 4% -> 24% of filled orders, 26% -> 71% of orders in decided windows, capture of the >= 0.90 taker-BUY opportunity 0.2-0.4% -> 2.3-5.5% at a flat opportunity), else the Chainlink posture (entry fills 0.66 / 0.70; best multiplier 1.0 on STUDY entries, 1.4 on VALIDATE entries): 0.569 STUDY / 0.693 VALIDATE per fill vs cheaper 0.484 / 0.679. Reported, own state: after entry fills come in same-side runs (previous fill's side 0.88 of schedule fills; own-history baseline 0.809 / 0.822 per fill, above the held-outcome composite 0.753 / 0.790); pairing bids on the under-held outcome 0.91-0.94. Live 10-31: the US-session 500 ladder follows the Chainlink edge over the mid 0.786 per fill (0.965 where reference and market disagree; historical VALIDATE region D 0.93). The favourite-share drift (the 'weekly k cycle') is the entry and deep-bid decisions: the whole history rejects weekday, volatility and step models (out-of-sample R^2 < 0), the market's other makers are flat (maker-row tapes), the ladder-center multiplier on the live Saturday block is 1.14 (5m) / 1.37 (15m) vs a fill-level best k of 1.4, and a band rule fails (0.682 vs 0.683). | VALIDATE-only (public part); own-state description (not decoded) | `code/side_sm.py`, `code12/typed_side.py`, `code12/persist_vs_policy.py`, `code8/fill_side.py` |
| Price | Fill price = last clean trade before the fill minus 0.01. **In-block execution-order clock (R7, recording-free): 0.807 on all 27,988 VALIDATE BTC 5m maker fills (block clock 0.709; gain +0.098, 2-h block bootstrap [+0.084, +0.111]; per wallet 0.800 / 0.805 / 0.814; halves 0.806 / 0.807), 0.766 on BTC 15m (block 0.666), pooled 0.803 (block 0.705); STUDY 0.751 / 0.730.** Trivial anchor 'last print' with no offset on the same clock 0.773. Live match clock (R4): 0.83-0.86 (10-31 15:40-16:40: block 0.625, in-block 0.719, match 0.849, R7 combined 0.843): the in-block order recovers part of the match-clock gain on busy hours. Block clock exam 0.688. This IS the trivial anchor "last print" minus a tick on a fresh clock. The ladder hangs off each market's own mid with a ~0.2 Chainlink skew; its half-spread follows the digital's risk only partly (R^2 0.47 in 5m, 0.26 in 15m; top rung within a tick 26-30% vs 19% for a mid-minus-constant anchor). | exam-verified (block clock); VALIDATE-only (in-block clock, match clock) | `price_inblock`, `price_r7`, `price_match_clock`, `code11/inblock_*.py`, `code8/m1_invert.py` |
| Size | **Iteration 15:** a configured size per family, identical in the three wallets (BTC hourly 38 / 300, BTC 4h 400, ETH 5m 50 / 150, ETH/SOL 15m 30, SOL 5m 50 / 100, XRP 5m 10 / 50, BNB 5m 10, DOGE 5m 10 / 40, dailies 50); not reward-driven. October BTC: schedule rungs 500 x 2^k with a one-fifth level (100 / 12 only at 30-120 s left); 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; plus **imbalance pairing bids** of exactly the own abs(Up - Down) shares (calldata original size within 2% of the imbalance; 11-14% of lot fills; not remainders). July (pmxt pilot, same engine family): 500 / 300 / 50 + pairing sizes; June: 50 / 100 / 300. | VALIDATE-only | `code6/m5_size.py`, `code10/m1_pair_lot.py`, `code10/pmxt_pilot.py` |
| Exit | Holds to resolution; after entry bids its own imbalance on the under-held outcome (non-schedule sizes), priced at the market, plus small complement taker buys; merges ~65 s before the end. Locked pairs +$38.1k and residual -$14.4k on VALIDATE (maker BUY fills). **Iteration 12: a strict-fill replay of the decoded machine with this pairing leg loses $106k to $236k on its locked pairs (at-touch fills: $87k to $236k) and lowers the oracle-side outcome ceiling from 0.47 / 0.53 to 0.25 / 0.30**: the cluster's pairs need queue-priority fills that do not trade through. | VALIDATE-only | `code12/replay_machine.py`, `code10/m1_pair_lot.py` |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints; for live inputs, every trade record whose transaction holds a cluster trade.
2. Presence, BTC 5m (R3): P(cluster maker BUY fill on s in [t, t+10)), t in [0, 300) = `presence3_rule.txt` on features
   published by t (time, side, clean-tape activity, Binance 1-s TWAP-60 fair, z, returns, realised vol, edge, window path,
   previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag). No own state. R5's Chainlink stack
   where the series exists (`code/r5.py`).
3. Presence, BTC 15m: the same feature definitions on bins t in [0, 900) (`features15.py`) scored by `presence15_rule.txt`.
4. Side (R8c, counted, public): the BTC 5m window that starts at the NYSE open (09:30 America/New_York, weekdays) ->
   the cheaper token; else R8's public side (decided window |Up mid - 0.5| > 0.4 at b - 3 -> the cheaper token; else the
   Chainlink posture, stamp b - 4, Gamma strike, 1.4 x 300-s Binance vol, Binance stand-in fallback), `code/side_sm.py`.
   Also reported: per fill on the match clock (where the shared recorder has the fill's transaction): Up iff fair_CL(Up) > Up mid
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
- Iteration 15 (the quote's configuration moves between blocks): the pure 500 ladder (label purity 0.91 on 11-01,
  0.88 on 10-31 by all-match calldata) follows the k 1.0 Chainlink posture at 0.866 on 10-31 17:29-18:00 (exact publish
  clock) but at 0.601 on 11-01 07:00-08:00 (best k 2-3: 0.65; cheaper token 0.63-0.64). The trigger is decoded (each public
  publish re-sides the ladder within 300 ms: no-fit AUC 0.794 after the publish vs 0.625 before it), the volatility
  configuration that sets which side the ladder favours is not: it moves between blocks like the fill-level k drift of
  iteration 11, and no public input tested so far predicts it.
- Iteration 15 (the idle module): outside BTC 5m/15m the public side is 0.58 on VALIDATE (market favourite 0.54); the
  opening fills are decoded (in the money vs the strike, 0.78-0.81) but they are 13% of those fills and lose money; the
  later fills, where the module's profit is, sit at the market-favourite level on public inputs (0.55-0.75); with the fill
  price as the market price a Binance-vol fair explains 0.68 (description only).
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

Iteration 18 measures where the BTC 5m money sits along the volatility calendar, with exact outcomes (the cluster's own
REDEEM rows, 33,463 windows, 100% agreement with Gamma on 4,387 overlapping windows). Return per $ on the cluster's BTC 5m
BUY trades: June 2.4%, July 3.9%, August 4.1%, September 2.9%, October 1-22 1.2%, the lot 10-23..30 3.8%. In October the
windows whose scheduled (time-of-day) vol most exceeds the trailing 300-s vol, where the cluster leans hardest to the cheap
token (cheap share 0.65), LOST (-2.5% per $, cheap fills -4.1%); the other four quintiles earned +1.6% to +3.8%. The October
cheap lean at scheduled-vol moments (a cluster-only gradient: the other makers in the same windows show none) is therefore a
cost or a risk setting, not the source of the profit: the money stays in ordinary windows, where the engine is re-pegged
first after each futures move and each published Chainlink report (two event inputs confirmed this iteration, at public
timing) and minting takers hit its bids at the touch. Who pays is unchanged: non-HFT takers buying the other outcome.

Iteration 17 adds one scheduled event to the economics. At the NYSE open the cluster's BTC 5m fills jump to about four
times their usual count, and they land on the token that the opening move just made cheap (mean price 0.19-0.28). On
BUILD those fills won 40% of the time at a mean price of 0.23 (+0.17 per share; four of ten windows paid off big, six
lost). The orders are fresh: by the per-wallet salt counter every open-window filled order was created after the
latest order that filled in the five minutes before the open, and they are main-ladder sizes (500 x 2^k, 92-100%), so
the engine posts new bids on the cheap token at the open (measured). Hypothesis for who pays: the takers who dump the
losing outcome during the opening move, the cluster being paid for absorbing that liquidity when the move overshoots.
Other scheduled slots (06:15, 22:00 = CME reopen, 07:45-08:00 = Europe opens) show cheap-side fills that lose, and a
pre-registered rule for them was not adopted (VALIDATE +0.003), so the open is not a general rule of the market
calendar. The taker hold's length did not change the cluster's returns at the two hold changes (08-17, 09-04). The
side residual elsewhere is idiosyncratic per market (no cross-market synchrony at fill level). The taker mix (automated
takers committing within ~0.3 s of the match, against slower ones) does not explain why the reference stopped
predicting small-edge fills on 11-01.

Iteration 16 sharpens where the money is not. On the idle families a strict replay of the decoded opening bid, even with
the cluster's own first-fill side, tracks per-market PnL at only 0.37-0.43 Pearson: the profit there comes from the later
two-sided fills, taken at the best bid of thin books (0.72 within a tick), whose side the takers choose. On BTC the ladder's
geometry is fixed (half-spread 0.075 per side at the top rungs) and its center is skewed toward the Chainlink report by a
configurable amount (0.30 of the fair-minus-mid gap on 10-31, 0.13 plus a shrink toward 0.5 on 11-01); at-touch posts
follow Binance futures moves within ~0.5 s. It is paid for liquidity and speed: being re-pegged first after each futures
move and each published report, so that minting takers hit its bids at the touch, rather than for a private signal.

Iteration 15 adds the families outside BTC 5m/15m, which carry the idle weekend blocks. There the cluster quotes a fixed
size per family in all three accounts at once; at the open of the 5m/15m alt windows it buys the outcome that is in the
money against the strike (the strike is the TWAP of the minute before the open, so the open already has a favourite),
but those opening buys lose money. What earns is the later buying on the long-horizon families (4h and hourly, +5-10%
per $ on BUILD and VALIDATE with a Binance stand-in settlement): bids below a Binance-volatility fair that takers sell
into over hours, i.e. liquidity provision with a fair-value filter, not a favourite harvest (the daily family earns
about zero).

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

Iteration 18: the two event inputs that re-side the cluster's quotes are both public (the RTDS Chainlink publish and the
Binance USD-M book), and the engine reacts to them within 0-150 ms (publish) and 50-450 ms (futures), inside the venue's
~150-ms taker hold. A replicator on a home connection (tens of ms to the venues, a laptop clock that drifted 1.3 s) could
compute the same law but would post after the takers who read the same events; the decoded law describes the cluster's
quote, it does not give a normal user its queue position. The scheduled-volatility lean that is new in October is not a
profit source (the high-ratio windows lost money in October), so copying it would not help. The 11-02 open (first after the
DST change) is recorded at full depth to fix the open rule's clock before the next exam.

Iteration 17: the venue holds every crypto taker order ~150 ms before matching (floor of the commit-to-match latency
187-193 ms on 10-31 and 11-01). A maker that re-prices within that hold is protected from takers reacting to the same
public move; one that re-prices in 0.3-2 s is not. The NYSE-open behaviour needs no speed (bids on the cheap token during
the open window), but on development data it is ten windows with a high variance (four large wins, six losses). The clock
change on 11-02 (the NYSE open moves to 14:30 UTC) is untested.

Iteration 16: the engine's instances do not always run the same modules (on 11-01 one wallet ran the main ladder alone in
7 of 10 slots), and the center's skew configuration changes between days with no public driver found, so a
copy would trade a moving configuration. A replicator would need the futures re-peg (posts within ~0.5 s of a futures move)
and the latency-corrected Chainlink nowcast; the laptop used here drifted 1.3 s against Binance by 11-01 09:26 UTC, which
alone would put a copy behind the takers it relies on.

Iteration 15: the part that runs on weekends (the non-BTC families at 10-400 shares per order) needs no sub-second
latency at the window open, but its opening in-the-money buys lose money; the later long-horizon buys (4h, hourly)
earned +5-10% per $ on development data with a Binance stand-in settlement, on small volume (about $0.20M of 4h and $0.30M of
hourly fills over 10-08..30 for the three accounts, all coins). A copy would be capacity-limited and its public side rule is not
decoded beyond the open (later fills 0.55-0.75 against the market favourite). The laptop running this study has a
drifting clock; any live replication needs a synchronized clock (iteration-15 offsets reached 0.9 s).

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay, a CLOB connection that
re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs on both outcomes of several BTC
5m and 15m windows (a working capital of ~$22-24k per wallet, reset by a weekly Monday sweep at the 01:00 UTC restart and growing to $43-49k by the end of the week; no deposits in 10-09..30), and unchanged fees (0.07 taker), listings and matching. A home
connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the slower makers this strategy
profits from: expect zero or a loss without low latency. In the new Chainlink noise regime the strategy itself lost money
on BTC 5m (10-31), and its operator switched BTC 5m off and restarted two of the three engines. Iteration 12: the three accounts have three different owner keys (a Safe for mo-money, ERC-1967 smart-wallet proxies for almach and bosona) whose fill sides move together; mo-money's owner has a Hyperliquid account with no fills in the 120 days before T0. A copy would also need the queue priority: replaying its own decoded pairing leg with strict fills turns the +$38k of locked pairs into a loss of $0.1-0.2M.

Iteration 13: the configuration that earned 7-9% per dollar in September (module always on, underdog-heavy fills) is no longer what runs; the October configuration earned +0.6% per dollar on the October BUILD sample hours before rebates, and the operator updates the engine within 1-3 days of listing changes (the last-fill time moved from ~45 s to ~100 s before the end when the settlement switched to TWAP-60). A replicator would be copying a moving target whose current version earns little before rebates.

## Open leads (not part of the frozen rule)

- Iteration 17 open items: the E3 calendar screen on weekday live blocks (B1 signing times do not exist for this
  cluster: timestamp 0), the BTC 15m NYSE-open window (VALIDATE cheaper 0.892, margin 0.296, 0.004 short of its
  pre-registered bar), the DST question for R8c (NYSE open 14:30 UTC from 11-02), X213 (hold-aware strict replay),
  X214 (record the Polymarket Perps index), X200-X203 (walking-bid state machine, step hazards, engine passes, chain
  origins on the 11-01 full-depth recording), X207 (per-account MTM breaker), X208 (operator pushes), X209 (other
  wallets at the restart seconds), E4-E6.
- Iteration 16 open items (panels after iteration 15): X188 the resting state at each print (post and cancel hazards on
  public clocks, queue ahead) and print-level selection, the only unit whose oracle ceiling (0.81-0.83 at recall
  0.62-0.69) is above the selection bar; X190 whether the queue resets at every publish pass (makerOrders positions vs
  the level size at the last pass); X185 CLOB prices-history as the examinable market state of the hourly, daily and 4h
  families; X186 which feed moves the alt 5m/15m and 4h ladders; X187 the long-horizon fair on the 4h ladder; X189 the
  non-BTC module as a quote on its recorded books. Closed in iteration 16: X160 (the 10-31 quote side does not replicate
  on the clean Sunday block, 0.53-0.63; inside bosona the large-edge part does), X177-X180, X181 (fair cap rejected),
  X182-X184.
- Why the center's fair moved between 10-31 and 11-01 (k 1 -> 2-3, or a shrink toward 0.5) is not decoded: no public
  calibration driver tracks it (assumptions panel Q4), the half-spread did not move, and the same instance (bosona) shows
  the change.
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
