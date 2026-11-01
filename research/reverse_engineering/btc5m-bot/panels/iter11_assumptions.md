# Panel, iteration 11: assumption breaker

Lens: what the investigation takes for granted that may be false. This round tests five load-bearing claims of the
iteration-11 account with small measurements:

- the take "rises with the bot's own recent decisions, a self-exciting internal state" (finding 13, and the closure of X85);
- the decision is a reaction "about 100-150 ms after a microprice tick" (the timing component);
- the per-window PnL lean is "a coin that race outcomes seed and the size rule amplifies" (the condition-5 account);
- the 'on' periods are "directional" against a p = 0.5 null (finding 7);
- a skipped onset means the bot chose not to act (and not that it could not).

## Data and checks

Development data only: pre-H BUILD / VALIDATE (`fills.parquet`, `calldata_sample.parquet`, `binance_1s.parquet`,
`ptb.parquet`, all with window start < H) and the 10-31 12-18 development block (`it11/onset_A|C.parquet`,
`it11/large_dec.parquet`, `it10/rem10.parquet`, and `btc5m_venues2` / `btc5m_clob_raw2` read through `iter_live`, which
returns development blocks only). Nothing sealed was read, listed or counted; `.cache/live/sealed/` was not opened. Calendar
checked with `sealed.py btc5m-bot` at 2026-11-01 00:05 UTC: no lots released, current block sealed.

Scripts (all under 300 MB, each under 2 minutes), in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p11a\`:

| script | what it checks |
|---|---|
| `hawkes.py`, `fescale.py`, `fenull.py` | own-recent-decision effect under segment fixed effects, with a mechanical null |
| `segfe.py` | whether take-rate heterogeneity resets at the ladder bursts |
| `netwin.py`, `netwin2.py` | window net exposure vs the public BTC path (BUILD fit, VALIDATE score) |
| `dirnull.py`, `dirmove.py` | the directional 'on' periods vs a tick-direction null and vs BTC moves |
| `pmlock.py`, `timer.py` | Polymarket book events and internal periodicity as the decision clock |
| `lag.py` | Binance delivery delay (laptop receive minus exchange stamp) as a selector |
| `copies.py`, `slotlock.py`, `cancelrep.py` | ladder copy exhaustion, one open order per wallet, cancel-on-new-trigger |
| `slowgate.py` | slow BTC-path states as an onset-level take gate |

## Critique

### 1. "Self-exciting" is a pooled correlation; within 1-2 minutes there is none

Finding 13 says P(take) rises with the operator's decisions in the last 30 s (rec30), and X85 was closed on that basis. That
is a between-segment comparison. I put the onset table's take label on log(1 + rec30) with |bp| and the event class, and
added fixed effects for segments of the window of length L (linear probability model):

| fixed effects | A coef (se) | C coef (se) |
|---|---|---|
| none, with public slow terms (|ask - 0.5|, rel, act) | +0.013 (0.002) | +0.014 (0.002) |
| window (L = 300 s) | +0.019 (0.002) | +0.015 (0.002) |
| L = 120 s | +0.007 (0.003) | +0.002 (0.002) |
| L = 60 s | -0.021 (0.004) | -0.008 (0.002) |
| L = 30 s / 15 s | -0.044 / -0.084 | -0.032 / -0.073 |

Short segments carry a mechanical negative bias, so I built a null: every onset's time is redrawn uniformly inside its
(window, minute) segment, with the clean-event filter enforced, and rec30 and the label are recomputed from the actual decisions
(15 draws). At L = 60 s the observed coefficient is -0.0203 on A against a null of -0.0107 +- 0.0026 (range -0.015 to -0.006),
and -0.0052 on C against -0.0023 +- 0.0022 (range -0.006 to +0.003).

So:

- the whole positive effect is absorbed by 2-minute fixed effects;
- within a minute there is no self-excitation, and on A there is a refractory effect beyond the mechanical bias;
- public slow terms already halve the pooled coefficient.

The latent is a slow regime with a correlation time of about 1-2 minutes, and it is partly public. That is a different object
from "self-exciting internal state". Unlike millisecond ticks, it survives the block clock, so it is the one part of the open
selection problem that can move the historical exams (h1, h2).

The regime does not reset at the ladder bursts. chi2 / df of segment take counts against a public logit is 10.6 (A) and 9.9
(C) for burst-aligned cuts (42 / 172.7 s), against 10.2 and 9.8 (q90 11.7 and 10.6) for random cuts.

The G2 pacing rejection used the same pooled sign. Inside segments the sign is the one pacing predicts, so pacing is not
rejected.

### 2. Most decisions are not timed by any recorded input

The statement says the bot submits "about 100-150 ms after a microprice tick". Three measurements say this holds for a minority
of decisions.

- **Onsets do not time the decisions.** In `onset11`, the arrival-minus-onset kernel of taken clean Binance events is flat over
  0-550 ms (A: about 30 +- 6 per 10-ms bin, n = 1,734; only a 20-30% bump at 90-180 ms; C the same). A trigger with a fixed
  100-150-ms reaction would pile up there.
- **The decision-locked excess is small.** In `kernel7`, Binance USD-M BTC moved in [m - 300, m - 250) before 14.9% of matches,
  against 2.9% by placebo (excess 0.110). For ETH the excess is 0.092. Together these lock perhaps a quarter of the decisions.
- **Polymarket's book is not the clock either** (`pmlock`). Before 2,155 decisions, o-ask-up and o-bid-up events are enriched
  about 2x against a same-window ±1-4 s placebo, flat over every 5-ms bin from 0 to 120 ms, with no lag peak. o-ask-down events
  (a new cheap offer) are not enriched. The bot decides while Polymarket is repricing toward o, not at a fixed lag after any
  book message.
- **No internal timer.** The intervals between decisions show no periodicity at 10-1,000 ms (all decisions: max Rayleigh Z 40
  against a jitter-null maximum of 46). Fan-out-merged events show a weak Z = 29 at about 868 ms against a null maximum of 19.6
  (20 draws, period scan): replicate it, but do not build on it.

The vote (83%) carries direction, not timing. One third of the decisions have no vote at all, and in this record 53% have a
six-series tick below 0.05 bp. Those weak-vote decisions lean underdog (56.5% vs 48.2%) and are rarely large (2.7% vs 7.9%).
Two processes may be pooled: a venue-locked sniper and an unlocked one.

### 3. The PnL lean has a public, structured part; condition 5 is an exposure target

Per VALIDATE window (n = 1,904), corr(PnL, net × (2 outcome - 1)) = 0.887. The PnL condition is the condition of reproducing
the operator's signed net exposure, not decision overlap.

The investigation calls that net a coin. Its sign agrees with the outcome 48.5% of the time, which is true, but the net itself
is not unpredictable.

A linear model on the Binance 1-s path fitted on BUILD predicts the VALIDATE window net at r = 0.199 out of sample. The
coefficients are structured and replicate across BUILD and VALIDATE (VALIDATE t-values below; net per minute of the window as
the target):

| target | R² | with the current minute's move | against the previous minute's move | pre-open terms |
|---|---|---|---|---|
| net bought in [0, 60) | 0.135 | w0 +9.9 | | M1 +7.4, M2 -7.7 |
| net bought in [60, 120) | 0.147 | w60 +11.4 | w0 -11.3 | |
| net bought in [120, 180) | 0.090 | w120 +10.1 | w0 -7.7, w60 -6.8 | |

The terms:

- M1 = the move over [open - 300, open - 60), before the strike's TWAP minute;
- M2 = the move over the strike's TWAP minute [open - 60, open);
- the spot-vs-strike gap itself adds nothing once M2 is in the model.

In addition:

- window k's net correlates with outcome(k - 1) at 0.13;
- the net after 60 s already correlates 0.47 with the final net (0.66 after 120 s).

The bot buys with the current move, buys back against the previous minute's move, and its opening lean fades the TWAP minute
and follows the 4 minutes before it. That pattern points at a fair value whose strike or drift differs from Polymarket's
priceToBeat digital, a hypothesis the investigation tested only for the per-second side (X45: 50-55%). It never fitted the
fair value to the aggregate, low-noise target where the signal shows. R² is small, so this does not close condition 5 by
itself. It does falsify "the lean is seeded only by race luck", and it gives the replica a target it can execute.

### 4. Finding 7's null was mis-specified, but the excess survives, and it is the underdog

Finding 7 compares 30-s bins with at least 5 decisions to a binomial p = 0.5 null. A null in which the side follows each bin's
strong-tick direction at 83% gives the same mean, 0.135 (q99 0.156), against the observed 0.223. So the excess is not the tick
direction.

What it is: in the 165 active bins of 10-31, the bin's Up share correlates +0.28 with the bin's own 30-s BTC move and -0.29
with the move since the window open, and 70.6% of active bins buy mostly the side NOT favoured since the open (R² 0.12).

The directional 'on' state is underdog accumulation on ticks back toward the strike. It is visible in public series, contrary
to finding 13's "not in any recorded public series". At the onset level it does not change the take probability (slowgate:
AUC 0.49-0.53 for the since-open move). So it must enter through the number of decisions per take (legs, chase steps) or
through the unlocked decisions of critique 2.

## Checked and not supported (so nobody redoes them)

- **Binance delivery delay as a staleness gate.** Laptop receive minus exchange stamp for Binance USD-M / OKX / Bybit BTC,
  detrended with a 5-minute rolling median: q05-q95 -10..0 ms. At the onset (and as a 50-message context) it does not separate
  taken from skipped: AUC 0.47-0.55, inconsistent between A and C, on all and price-level events. Binance-side publication
  jitter does not select. The bot's own path cannot be observed.
- **Ladder copy exhaustion as the selector** (pre-H calldata, 13,558 operator orders). Filled copies per (wallet, burst,
  token, level, size) decay geometrically, with no pile-up at a cap:

  | wallet | 1 copy | 2 | 3 | 4 | 5 | 6 | 8 |
  |---|---|---|---|---|---|---|---|
  | DS | 4,273 | 908 | 254 | 78 | 12 | 2 | |
  | GF | 2,750 | 270 | 36 | 2 | 1 | | |
  | XM | 1,911 | 320 | 54 | 15 | 2 | 1 | 1 |

  The copies of a level are signed in one ms (97%).
- **One open order per wallet, resting remainders included.** It is false. While its remainders rest (277 located,
  median life 327 ms), DS submits 66 new decisions against 59.9 expected from its local rate. GF: 4 against 4.1.
- **Cancel-on-new-trigger as the time-to-live rule.** Only 6.6% of the 196 cancelled remainders have a same-wallet arrival
  within ±100 ms of the removal. There is a slight excess 100-250 ms after the removal (17 against 4), which is weak.
- **Slow BTC-path states as an onset-level gate.** The previous-minute move, the move since the open and pre-open M1 / M2,
  signed toward o: AUC 0.45-0.53 on all events. On price-level events A and C disagree.
- **A daily volume quota (rebate tier).** Daily taker notional varies with weekends (CV 0.39 for DS and GF; XM steps down on
  10-14). There is no quota signature.

## Proposals (ranked by the chance of closing the gap)

### 1. Decode the 1-2-minute regime that the investigation calls self-excitation (re-opens X85; strong form of X72; corrects G2)

**Hypothesis.** The take probability among onsets is modulated by a slow latent regime with a correlation time of about 1-2
minutes. That regime, not a self-exciting kernel, produces the over-dispersion (chi2 / df about 10-15), the 'on' periods and
the rec30 association. It is largely a function of slow public state:

- the underdog-since-open configuration;
- |p - 0.5| and the distance to the strike in vol units;
- time in the window;
- realized vol;
- the Polymarket touch depth and spread on both outcomes;
- the Up + Down ask sum;
- fast-crowd presence.

Inside the regime the bot thins its decisions (refractory or pacing). The regime survives the 2-3-s block clock, so it can
raise the historical presence gain and the selection AUC.

**Evidence.** Critique 1: the coefficient goes from +0.019 (window FE) to +0.007 / +0.002 (120 s) to negative at 60 s, beyond
the mechanical null on A. Public slow terms halve the pooled effect. The regime is not burst-aligned. Critique 4: the active
bins are 70.6% underdog-since-open.

**Test (runnable now on 10-31 14:55-17:55; replicate on 11-01 06-12).**

1. Redo the fixed-effect scan for L = 15, 30, 60, 120 and 300 s with the redraw null (200 draws, clean filter). Report where
   the observed coefficient leaves the null, in both halves.
2. Fit three models on A and score them on C with the same public covariates. Compare held-out log-likelihood per event
   (window-block bootstrap):
   - (a) a Hawkes model with an exponential kernel on the operator's own decisions;
   - (b) a Cox / hidden Markov model with 2-3 latent rate states and Markov transitions;
   - (c) both together.
3. Regress the decoded state, or the segment take rate (obs / exp), on slow PUBLIC variables over 30-300 s:
   - the move since the open toward the underdog;
   - |p - 0.5| and the distance to the strike;
   - rel;
   - realized vol;
   - touch depth and spread on Up and Down;
   - the ask sum;
   - the fresh-signed crowd count in the hold (crowd10);
   - the Polymarket trade rate;
   - Polymarket feed health (server-stamp gaps on the window's book, and the shared recorder's slow-consumer reconnects).

   Report own-state alternatives apart: the operator's unpaired exposure, the set cost of held legs, window PnL so far.
4. Within the decoded 'on' state, measure the refractory curve: P(take | onset) by time since the operator's last decision,
   beyond the one-in-flight floor.
5. Port the public-only state to the block clock: add minute-scale features to `model_it5_blk_full`, fit on BUILD, and report
   the presence gain over the stronger baseline on VALIDATE.

**Data.** `it11/onset_A|C`, `large_dec` (decision times), `btc5m_clob_raw2` touch depth, crowd10 / cdall10, and for step 5
the pre-H cells and tapes.

**Signature if true.**

- (b) beats (a) on C, and rec30 adds nothing beyond the null at L >= 60 s in both halves.
- A public-only state lifts the onset AUC from 0.681 to 0.72 or more on C.
- Price-level ticks are taken at 45% or more in the 'on' state and 15% or less in the 'off' state.
- The block-second presence gain rises from +0.054 to +0.065 or more on VALIDATE.

**Signature if false.** Hawkes wins and the within-segment coefficient stays above the null. Finding 13 then stands as a
measured self-exciting kernel, with its decay time.

### 2. Make condition 5 an exposure-path target and fit the bot's fair value on the window net (new; strong form of X82 / X45 / X30)

**Hypothesis.** Per-window PnL is about net × outcome (r = 0.887), so an executable rule that reproduces the operator's signed
net path reproduces the PnL without reproducing the decisions. The net path follows a structural rule:

- follow the current move;
- buy back against the previous minute's move (pairing);
- open the window with a lean against the TWAP minute (M2) and with the earlier momentum (M1).

That rule reveals a fair value whose strike or drift differs from Polymarket's priceToBeat digital.

**Evidence.** Critique 3: BUILD-fit, VALIDATE-scored r = 0.20; per-minute t-values of about 7-11 that replicate across BUILD
and VALIDATE (M1 +3.5 / +7.1, M2 -3.1 / -7.6); corr(net_k, outcome_{k-1}) = 0.13. Live active bins buy the underdog-since-open
on its upticks.

**Test (now, on pre-H data).**

1. Build a 30-s bin net-change model on BUILD, in two versions: LightGBM, and a linear structural version. Target: Δnet per
   bin per outcome. Inputs:
   - current and lagged BTC moves (1-s klines; ms aggTrades for the bin);
   - the move since the open;
   - M1, M2 and the 15-minute move;
   - the distance to the strike over σ√τ;
   - the Polymarket touch from the tape (the operator's own and W4's prints excluded);
   - the ask sum.
2. Predict the VALIDATE window nets. Report Pearson and Spearman, per wallet and pooled, with 2-h block CIs.
3. Build an executable replica: each bin, buy the predicted Δnet on the predicted outcome at the touch with strict fills,
   under both pre-registered latency conventions. Report the per-window PnL correlation.
4. Decode the fair value from the window net and the active-bin direction. Candidate FV_bot variants:
   - strike: priceToBeat, spot at the open, spot at open - 60 s, the previous window's priceToBeat, the 15m / 1h windows'
     strikes;
   - drift: 1-15-minute momentum;
   - vol: k ∈ [1, 3] or DVOL.

   The M1 (+) / M2 (-) pair discriminates between them: a strike-at-open fair value fades M2, and a momentum drift follows M1.

**Data.** `fills.parquet`, `binance_1s`, the Binance aggTrades archives, `ptb.parquet`, the tapes, and DVOL.

**Signature if true.**

- The out-of-sample window-net r is 0.45 or more.
- The replica's PnL r is 0.4 or more at the decoded latency.
- One FV_bot variant reproduces the M1 / M2 and lagged-minute coefficients, and adds to the side model at the block clock.

**Signature if false.** The out-of-sample net r stays at 0.25 or less with the nonlinear model. The condition-5 account then
gets a measured public share (0.20), and the rest is own state or race.

### 3. Split the decisions into locked and unlocked, and judge every new feed by time-locking, not by AUC lift (strong form of X87 / X88 / X96 step 4 / X76)

**Hypothesis.** Perhaps a quarter of the decisions are venue-locked snipes. The rest come from a second process, or a
state-sampled one, whose clock is not in the recorded feeds. Pooling the two hides both. The 11-01 feeds (rec_eu11, xsnap,
rec_pb10, xfam, xliq) should be scored by whether they time the unlocked decisions.

**Evidence.** Critique 2:

- the onset kernel is flat;
- the decision-locked excess is 0.11 (BTC) and 0.09 (ETH);
- Polymarket events are enriched 2x with no lag peak, and new cheap offers are not enriched;
- there is no internal period;
- weak-vote decisions lean underdog and are rarely large.

**Test.**

1. Flag each decision as locked when any recorded venue microprice event toward o falls inside that series' sharp kernel bin
   (the kernel7 peak ±25 ms). Estimate the locked fraction against a time-shift placebo.
2. Compare locked and unlocked decisions on:
   - side against the vote;
   - the underdog-since-open share;
   - size and wallet;
   - won or lost race;
   - rel;
   - o's ask path (rising or static);
   - the maker-fill share.
3. For the unlocked decisions, compute event-locked and decision-locked kernels at 5-ms resolution for:
   - every 11-01 feed;
   - Polymarket event classes per outcome (ask decrease, size inserted at the ask, bid steps);
   - a composite crossing time (the venue-implied value, at the London arrival, crosses o's ask plus the net fee).

   The criterion: a peak of at least 3x the placebo in a width of 20 ms or less.
4. Report the union coverage of the decisions by all locked clocks.

**Data.** `large_dec`, the kernel7 lag table, `btc5m_venues2` / `btc5m_xven` / `btc5m_xfam`, `btc5m_clob_raw2`, and the 11-01
06-12 recordings.

**Signature if true.**

- A feed or a crossing time locks half or more of the unlocked decisions.
- Unlocked decisions differ systematically (for example 65% or more underdog-since-open, static asks, more maker fills).

That gives a second rule for side and timing, and the full-coverage side moves toward 80%.

**Signature if false.** The union coverage stays at 40% or less. The clock is internal, and presence should be modelled as a
state-sampled intensity (proposal 1's Cox model) over continuous state, not over onsets.

### 4. A competition-aware controller: the regime is the bot's recent race success (new; own-state mechanism with a public proxy)

**Hypothesis.** The bot raises its aggressiveness after winning races and backs off after losing them, as a bandit or
fill-ratio controller would. The win rate depends on the fast crowd queued in the same hold, so the regime has a public proxy:
crowd fast-taker presence over the last 1-2 minutes.

**Evidence.**

- The regime lasts 1-2 minutes (proposal 1).
- Win rates depend on the crowd ahead (DS 80% vs 69%, GF 72% vs 61%).
- Race outcomes are nearly deterministic given the arrival (race11), so losses that the crowd causes are exogenous to the
  bot's state.
- size11 tested this channel for the size only, not for the take.

**Test (10-31; replicate on 11-01 06-12).**

1. For each onset, count the operator's decisions in [tau - 120 s, tau) and the share of them that won.
2. Split the losses by cause: crowd orders queued ahead (queue10) or a maker requote (who9).
3. With (window × 2 min) fixed effects and proposal 1's null, test P(take) against the recent win share with the count held
   fixed, and the same with only the exogenous losses.
4. Public proxy: the count of fresh-signed crowd orders in the hold (crowd10) over 30-120 s, as a predictor of the 'off'
   state.
5. Historical analogue at the block clock: the operator's maker-first share of fills (lost races) over the previous 2-5
   minutes against the next minute's taker rate per wallet.

**Data.** Won and lost decisions (ins9b_M lost_300 / lost_1000, taker matches), queue10 / who9, crowd10, and the pre-H
calldata sample.

**Signature if true.**

- With the count fixed, P(take) after mostly won races is at least 2x the rate after mostly lost ones, and the effect holds
  for exogenous losses.
- Crowd fast-taker presence predicts the 'off' state at AUC 0.65 or more out of sample.

**Signature if false.** P(take) is flat in the win share, and the regime is not a race controller.
