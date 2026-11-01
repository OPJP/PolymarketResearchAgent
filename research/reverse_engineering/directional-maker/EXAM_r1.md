# directional-maker: independent examination of the frozen rule R2

Examiner run on 2026-10-31 (local Windows laptop). Wallets: mo-money `0x32ed2e54...`, almach `0x3725d52f...`, bosona
`0xc2ad03f7...`, pooled as one operator. Rule under test: R2-presence-lgbm-clean-path-xwin (`code/final_rule.py`,
models `code/presence2_*.txt`, `code/selection2_*.txt`). I did not change it. Every number below comes from my own runs on
the holdout. I did not copy any number from NOTES.md, FINAL_RULE.md or state.json.

## Verdict

| criterion | result | one-line reason |
| --- | --- | --- |
| (6) match | **partial** | Beats the rotation null (p = 0.005 on both strata, recall 32% at lift 2.6), but every high-accuracy target is missed and most of it is co-occurrence: presence AUC 0.700 against 0.681 for market activity alone. |
| (7) backtest | **fail** | Strict fills, 2 s latency, slack 2, no rebates: -12.8% on $100k bought (t = -7.1, p(profit) = 1.0). It loses on every one of the 8 days and in every sensitivity, including the optimistic bounds. |
| (8) replicable | **fail** | The only public-data version of the rule loses heavily for a newcomer (2-5 s latency, back of the queue, 0% rebate tier) and loses more at larger size. The wallet's own profit depends on things the rule cannot see: which windows it trades, and how fast it requotes. |
| (9) persists | **fail** | The deploy-now statement is not supported. The rule's holdout PnL is significantly negative, including the forward day 2026-10-30 (-16.9%). The wallets' own BTC 5m maker fills did earn +4.0% on the holdout (p = 0.005), but nobody can deploy that edge from public data. |

High-accuracy target (brief): **not met** on any metric.

## Holdout sample

All 2,304 BTC 5m Up/Down windows that start in [2026-10-23 00:00, 2026-10-31 00:00) UTC: 8 full days. The last of them,
2026-10-30, comes after as_of and did not exist when the study was designed. 2026-10-31 is left out because Binance
publishes its 1-s archive the next day. The panel has 138,240 (window, side, 10-s bin) rows, and the cluster has 36,244
maker BUY fills (plus 840 taker fills). Selection uses 368,849 sampled in-window taker prints: all 33,697 prints that fill
the cluster, plus 10% of the others at weight 10. In 12 windows (2026-10-29 18:00-19:00 UTC) nothing traded inside the
window. A fresh API call confirmed this, so it was a pause, not missing data. They stay in the sample with no prints.

Data came through the polyrea adapters and the shared HTTP cache (`exam/exam_fetch.py`): Gamma windows, data-api taker
tapes [start-120, end) per window (2,292 complete, 12 empty), the three wallets' activity, and the Binance 1-s archive
(SHA-256 checked). The files are in `.cache/re/directional-maker/exam/` (about 0.3 GB).

## 1. Leakage audit

- **Frozen constants.** `MODEL`, `BASELINE`, `OWN_MODEL`, `THETA_SEL`, `PRICE_OFFSET = 0.01`, `PRE = 120` and
  `SEL_NEG_FRAC` are literals. `evaluate()` only loads boosters and predicts; nothing is fitted in it.
- **The models are a BUILD-only fit.** I refit the presence models with `train2.PARAMS` on the BUILD panels
  (2026-10-09..16) and they reproduce the frozen files exactly (maximum prediction difference 0.0, 300 trees). I re-ran
  `sel2`'s training on BUILD days: it reproduces `selection2_*.txt` exactly, and both `THETA_SEL` values to the last digit
  (`results/exam_refit_check.json`, `results/exam_refit_sel.json`).
- **No development read at or after H.** Every development fetch script clamps to < H: `fetch_local`, `fetch_tapes`,
  `fetch_activity`, `fetch_chain`, `warm_tapes`, `tapes_from_cache`, `spotflow3`, `kraken3` and `meta3`. No timestamp
  literal after H appears in `code/`. The development files on disk end before H: spot 1792713599, activity 1792713551,
  tapes 1792713593, last window end = H. The holdout files are mine and sit in their own directory.
- **Point-in-time features** (I read `features2.py` and `sel2.py`):
  - A Binance second k is used from k+1 on, and tape prints only when ts < t.
  - The strike is the TWAP of [start-60, start).
  - Path and cross-window features use earlier bins or windows only.
  - Gamma provides listing fields only (tokens, times, fee rate). `up_payout` is used only to settle `won_s` and the PnL.
  - The wallet's own prints are removed: every tape row in a cluster transaction, plus the cluster's taker prints (34,537
    holdout rows).
  - Own inventory appears only in the separately reported model. Own fill counts and time since the last own fill are
    not used.
  - There is no ESPN input (crypto strategy).
- **Truncation and corruption test** (`exam/exam_trunc.py 40 2026`, `results/exam_truncation.json`). On 40 seeded
  holdout windows × 30 bins × 2 sides, I rebuilt each bin's row with the rule's own `build_panel` in two ways:
  - with all prints, Binance seconds and cluster fills at or after t deleted;
  - with the data after t corrupted (random prices, sizes, sides, assets, wallets and times, a random-walk spot, and
    fake 500-share cluster fills).

  Both gave **0 mismatches in features and in the three models' predictions**. The positive control, truncating one
  second too early (t-1), changes the features in 1,042 of 1,200 bins, so the test can detect a leak. The price rule
  (last clean print before the fill second) matched on all 656 fills.

  In selection, 1 of 360 prints differed. I traced it (`results/exam_trunc_sel_open.json`): for prints stamped in the
  first 2 s of a window, the strike TWAP inside `fair_p` uses seconds start-2..start-1. Those seconds are published by
  the print time but not by "ts - 2", the rule's own stated lag. This is not future data relative to the decision. It is
  a minor inconsistency with the docstring.
- **Robustness to block-time slack.** I delayed every tape print and Binance second by 2 s (`exam_panel.py 2`). Presence
  AUC moves from 0.6996 to 0.6965 and the baseline from 0.6809 to 0.6774 (`results/exam_lag2.json`), so the result does
  not depend on the last two seconds. The backtest below uses latency 2 s and `match_slack = 2`.
- **Labels.** In a seeded sample of 150 holdout fills, all 150 receipts were found on Polygon. The decoded `OrderFilled`
  events agree with the tape-inferred maker/taker role in 150/150 cases and with the shares in 147/150
  (`results/exam_onchain_roles.json`).

Leakage check: **passed**.

## 2. The frozen evaluate() on the holdout

`evaluate(1792713600, 1793404800)` ran unchanged in 500 s (`results/exam_evaluate_holdout.json`).

**Only mechanical change:** in my driver `exam/exam_run_evaluate.py` I set `final_rule.CACHE` to the exam directory and
used `local=True`. `final_rule.py` itself is not edited. The reason is memory: the adapter path keeps every tape row of
the period as a Python tuple, about 2 GB for 8 days, which is over this laptop's per-process budget. My fetcher writes the
same adapter output in `fetch_local.py`'s day-file format.

On a 2-hour slice, `local=True` and the pure adapter path (`local=False`) agree on windows, bins, fills, presence AUCs,
price and PnL correlation. The only difference is 31,584 vs 31,587 tape rows: three prints the API returned on the fresh
call (`results/exam_evaluate_equivalence.json`). The rule's own output equals my independent computation wherever they
overlap.

## 3. Holdout metrics (my code unless noted)

| metric | holdout | VALIDATE (RE's report) | target |
| --- | --- | --- | --- |
| presence AUC, no own state | **0.700** (window-bootstrap 95% CI 0.693-0.707) | 0.763 | >= 0.85 |
| co-occurrence (market-activity-only) baseline | 0.681 | 0.735 | |
| gain over baseline | +0.019 (CI 0.014-0.023) | +0.029 | |
| presence AUC with own inventory (separate model) | 0.772 | 0.822 | |
| within active windows / with an oracle for active windows | 0.709 / 0.794 | 0.736 / 0.862 | |
| forward day 2026-10-30: R2 / baseline | 0.690 / 0.631 | | |
| side accuracy, 8,605 one-sided fill bins | **0.655** (0-30 s: 0.735; top-25% confidence 0.712) | 0.679 | >= 0.80 |
| best market-only side baseline (activity model) | 0.600; also underdog by last print 0.562, favourite 0.441, more bid hits 0.557 | | |
| side vs best baseline (McNemar, one-sided) | 1,384 vs 911 discordant, p = 2e-23 | | |
| price within one tick / exact (36,244 fills) | **0.688** / 0.350 (anchor "last print" alone: 0.609) | 0.585 / 0.313 | |
| selection AUC / stratified global / within-window | **0.681** / 0.686 / 0.643 | 0.770 / 0.757 / 0.669 | >= 0.80 |
| rotation null (2-h blocks, 200 draws): global / window | 0.624 +- 0.004 / 0.631 +- 0.004 (max 0.642); p = 0.005 on both (z 15.6 / 2.6) | | p < 0.01 |
| recall / lift at the frozen THETA_SEL | **31.8% / 2.57** | 49.0% / 3.80 | >= 50% / >= 3 |
| selection, activity-only baseline | AUC 0.656, within-window 0.634, recall 32.6%, lift 2.23 | | |
| per-window PnL corr: rule (expected) vs wallet, 1,672 windows | **0.295** Pearson / 0.334 Spearman | 0.334 / 0.393 | >= 0.5 |
| per-window PnL corr: strict backtest vs wallet, all 2,304 windows | 0.203 / 0.211 | | |
| rule return, strict fills, L = 2 s, slack 2, no rebate | **-12.8%** on $100,161 (11,428 fills; t = -7.08, p(profit) = 1.0, bootstrap 1.0) | | p < 0.05 |
| wallet's own BTC 5m maker return, same windows | **+3.95%** on $719,559 ($28,448; per-window t = 2.56, p = 0.005) | -2.3% | |

The rule's own `evaluate()` computes the selection null by rotating within UTC days with 99 draws. It gives the same
AUCs, with p = 0.01 (the floor of 99 draws) on both strata.

**Backtest definition** (`exam/exam_backtest.py`). R2 has no quoting threshold, and its "rule PnL" is an expectation,
so I fixed an executable version before looking at any holdout result:

- **When it quotes:** at each bin start t, on each side whose p_R2 is at or above the BUILD 85th percentile (0.1374,
  computed from the development panels).
- **Order:** BUY 20 shares at round(last clean print - 0.01, 2), live in (t+2, t+12].
- **Fills:** a print counts at T-2 (slack 2) and only if it trades through the bid: a taker sell below q, or a
  complementary buy above 1-q. Fill = min(20, through volume).
- **Costs:** no fee, no rebate.

| variant | return | t |
| --- | --- | --- |
| primary P | -12.8% | -7.1 |
| top 5% only | -19.7% | -6.2 |
| every bin | -9.1% | -37.6 |
| higher-p side only | -11.0% | -4.7 |
| latency 5 s | -15.8% | -8.5 |
| slack 0 (optimistic) | -10.6% | -5.9 |
| at-touch / first in queue (optimistic) | -12.6% | -7.0 |
| 100 shares | -14.7% | -8.0 |

Daily PnL of P is negative on all 8 days. On the forward day it is -$1,552 (-16.9%). On VALIDATE the same code gives
-12.2% (sanity check). A 20% maker-rebate share of the fee equivalent would be worth about 0.8% of notional at these
prices, so rebates would not close the gap.

## 4. Criteria

**(6) match: partial.** By the methodology's own match test, the rule's selection score passes:
- it beats the rotation null on both strata (p = 0.005, the floor of 200 draws; normal-approximation z = 15.6 and 2.6);
- it clears the effect-size floor (recall 32% >= 20% at lift 2.6 >= 2).

The within-window z of 2.6 (p of about 0.005) is close to failing a Holm correction over this rule plus the DM and SR
families tested in the verdicts.

Against the brief's high-accuracy target, every metric falls short:

| metric | target | holdout |
| --- | --- | --- |
| selection AUC | 0.80 | 0.681 |
| recall / lift | 50% / 3 | 32% / 2.6 |
| presence AUC | 0.85 | 0.700 |
| side accuracy | 80% | 65.5% |
| per-window PnL correlation | 0.5 | 0.29 |

Most of the signal is co-occurrence. Market activity alone gives presence 0.681 (the rule adds +0.019) and selection
0.656 / 0.634 within windows (the rule adds +0.026 / +0.009). Presence, side, selection and PnL correlation all dropped
from VALIDATE to the holdout. Only the price rule improved (within one tick 0.585 -> 0.688).

The side signal is real but modest: 0.655 vs 0.600 for the best market-only model, p = 2e-23. It is strongest right
after the open (0.735 in the first 30 s), which fits the opening strike-gap mechanism. The rule describes part of what
the wallets do. It does not decode them.

**(7) backtest: fail.** Under strict fills at 2 s, with slack 2 and no rebates, the rule loses 12.8%. It loses on every
day and in every sensitivity, including both optimistic bounds.

**(8) replicable: fail.** A normal user can build every input: the Binance websocket, the Polymarket tape and the CLOB.
But the rule built from those inputs is adversely selected. Its bids are hit when the market goes through them, which is
when the price is moving against them, at 2-5 s latency, with newcomer queue position and 0% rebates. A larger size
loses more (-14.7% at 100 shares), so capacity toward $50k/month does not help.

The wallets make money in the same markets, $28k in 8 days, roughly $107k a month across the three, on two things the
rule lacks:
- **Its schedule.** Which windows it trades is an operator choice that is invisible in public data: holdout active share
  by day was 19%-97%.
- **Its execution.** It sits at the top of the book and requotes faster than competing makers after Binance moves. Its
  price was the best level in about 90% of the RE's sampled BUILD sweeps; that is the RE's receipts work, which I did
  not re-run.

None of this is in the public-data rule.

**(9) persists: fail** (deploy-now statement not supported). The evidence:

- **The rule fails out of sample.** Holdout PnL is -$12.8k, -12.8%, p(profit) = 1.0. The forward day 2026-10-30 alone is
  -16.9%, p(profit) = 0.9998. Its presence AUC fell from 0.763 to 0.700 and its selection AUC from 0.770 to 0.681.
- **The wallets' own PnL** (`polyrea.tools.assess_persistence`, as_of = 2026-10-31 00:00, no one-off bonuses found to
  remove): all three wallets' last 30 days are significant.

  | wallet | last 30 days p | late 15-day decline p |
  | --- | --- | --- |
  | mo-money | 0.007 | 0.043 (significant: fails the methodology's late-decline condition) |
  | almach | 0.009 | 0.082 |
  | bosona | 0.002 | 0.111 |

  The cluster's total PnL over the 8 holdout days is +$61.3k, but that is only p = 0.059 with 8 daily observations.
  Its BTC 5m maker fills turned from -2.3% on VALIDATE back to +3.95% (p = 0.005). Activity fell to $7k on 10-24 and
  came back to $112-193k a day on 10-28..30. The edge decay that FINAL_RULE.md describes for the wallet did not
  continue. The wallet's edge persists; the rule's does not.
- **Conditions.** The fee rate is unchanged (0.07 on all 2,304 windows), and listings are continuous (one 1-h pause on
  10-29). These conditions hold, but they help the operator, not a replicator: the public-data rule loses with them.

## 5. Why it works (holdout evidence: `results/exam_mechanism.json`, plus the RE's iteration-3 order-level work)

The cluster is a top-of-book liquidity provider on BTC 5m Up/Down windows. It works as three copies of one quoting
engine, resting BUY orders on both outcomes on the 0.01 grid. It is paid the spread by takers who cross it. The RE
measured (iteration 3, development data; I did not re-run it) that after a sharp Binance move its fill rate rises 1.6x
while other makers' rises 3x. So it reprices or cancels faster, and the stale-quote snipers mostly hit other makers.

On the holdout:
- Its fills are on average 1.5 cents below our Binance fair, and 47.5% are at or above that fair. This is a mild
  fair-value skew, not a forecast.
- Half its dollars (about $357k) are on outcomes with Binance fair above 0.8, which earn +3.4%.
- Almost all of the $28.4k profit comes from the largest quartile of fills (> 40 shares: +$26.8k). Mid-window fills
  (30-120 s) earn +10%.

The losers are the many dispersed takers who send larger market orders into its bids. Per the RE, the fast
high-frequency takers rarely hit it. It
is not paid for rebates: the observed taker tier is Gold, and the verdicts' PnL at the 0% tier is 97% of reported PnL. It
is not paid for a private feed either: there is no lead over Binance 1-s data. A public-data copy cannot capture this,
because the edge comes from queue position, requote speed and the operator's choice of windows, none of which the
public tape reveals.

## 6. Can a normal user deploy it now?

**No.** "This strategy is statistically significant to continue working if I deployed it now" is not supported. The
deployable rule (R2 plus its price rule, run as a maker at 2 s latency with newcomer fills) lost 12.8% on 2,304 holdout
windows. It lost on every day, including the forward day after as_of, with p(profit) of about 1. The wallets themselves
are still profitable and significantly so, but nobody can reproduce that edge from public data at a normal latency.

## Files

- Exam code: `exam/exam_fetch.py`, `exam_panel.py`, `exam_run_evaluate.py`, `exam_trunc.py`, `exam_trunc_sel_open.py`,
  `exam_refit_check.py`, `exam_refit_sel.py`, `exam_metrics.py`, `exam_selection.py`, `exam_backtest.py`, `exam_lag2.py`,
  `exam_onchain.py`, `exam_persist.py`, `exam_mechanism.py`, `exam_assemble.py`, `exam_write_json.py`.
- Results: `results/exam.json` (verdict and key metrics), `results/exam_details.json` (everything) and the per-test
  files `results/exam_*.json`.
- polyrea notes: nothing was modified. Two points for the maintainers:
  - `final_rule.evaluate(local=False)` keeps a whole period's tape as Python tuples. That is fine for a day and too large
    for a week on this laptop.
  - Selection `fair_p` uses strike seconds after "ts - 2" for prints stamped in the first 2 s of a window. This is
    harmless but inconsistent with its docstring.
