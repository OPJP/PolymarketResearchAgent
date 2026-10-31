# directional-maker: frozen rule R3 (iteration 4)

Rule id: **R3-presence-lgbm-refit-build4-clock**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts, intervals=None)`,
pooled and per wallet), features `code/features2.py`, selection helpers `code/sel2.py`. Frozen model files next to the
code: `presence3_rule.txt` (rule), `presence3_activity.txt` (market-activity-only baseline), `presence3_own.txt`
(own-inventory variant, reported separately), `selection2_all.txt` / `selection2_activity.txt` with `THETA_SEL` (R2's,
unchanged). The previous rule R2 (examined in round 1) is archived unchanged as `code/final_rule_r2.py`.

What changed from R2: the presence models are refitted on BUILD = 2026-10-09..26 (the old BUILD and VALIDATE plus the
first half of the released lot) with R2's features and LightGBM parameters, plus three clock inputs (UTC hour,
weekday, US-session flag = weekday 12:00-21:00 UTC). Chosen on the new VALIDATE = 2026-10-27..30 (the lot's second
half, aggregate metrics only). Scope: BTC 5m Up/Down windows (about 55% of the cluster's fills), the three wallets
(bosona, almach, mo-money) pooled, with per-wallet metrics.

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine signs every order of the three wallets: per-wallet sequential salt counter, `timestamp`, `metadata` and `builder` left at 0, restarted together daily at 01:00 UTC (plus ad-hoc restarts). | VALIDATE-only | B1 calldata of all 34,606 lot transactions that filled it (NOTES iteration 4) |
| Selection | BTC 5m is switched on or off inside the running engine: on in weekday US hours, off overnight or at weekends on some days (10-23 21:00 to 10-24 15:25, 10-24 23:00 to 10-25 13:33 UTC); 94.5% of VALIDATE windows active. The switch is not a restart and has no public correlate beyond the clock. | hypothesis | salt counter keeps running at the same rate while BTC 5m is off; clock features add +0.002 AUC |
| Timing | Continuous requoting, 10-23 orders/s per wallet, faster when Binance moves (Spearman 0.67). Its fills are exposed only to Binance moves of the last ~0.25-1.5 s (the average other maker 3-5 s). It is not the fastest maker: at levels holding a competing order under 0.5 s old it is almost never at the top (pilot book from all matches of 10-26 13:00-13:30). Orders rest at the open; it stops about 30 s before the end. | VALIDATE-only (STUDY ms data) | takers' signing ms as match clock; aggTrades; all-match calldata |
| Side | Bids the side its fair value says the market underprices (strongest at the open: spot vs the new strike), adds to the side it holds. Rule: side with the higher predicted presence. | exam-verified (partial) | VALIDATE 0.663 vs 0.613 activity-only; exam r1 0.655 vs 0.600 |
| Price | 0.01 grid at the best bid. Rule: last clean print on s minus 0.01. | exam-verified (partial) | within one tick 0.709 VALIDATE (exam r1 0.688); live pilot: fill = best bid in 11/15 |
| Size | Clock schedule: 500 shares on weekdays 12:00 to ~21:00 UTC, 62 (or 250) at night and at weekends, plus a one-fifth level (100 / 12 / 50). Size does not depend on the edge within a session. | VALIDATE-only | original sizes from calldata (STUDY 75.7% / 65.3% on schedule; VALIDATE 70.4% / 38.8% + 25.7% at 250) |
| Exit | Holds to resolution; occasional merges; adds to the held side. | hypothesis | REDEEM / MERGE rows |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints.
2. Presence: for every (window, side s, 10-s bin starting at t in [0, 300) s), P(cluster maker BUY fill on s in
   [t, t+10)) = `presence3_rule.txt` on features published by t: time, side, clean-tape activity, Binance 1-s TWAP-60
   fair value, z, returns, realized vol, edge = fair - last clean print, window path, previous-window proxy outcome
   and strike move, UTC hour, weekday, US-session flag. No own state.
3. Side: in bins where it fills exactly one side, the side with the higher predicted presence.
4. Price: last clean taker print on s strictly before the fill second, minus 0.01, on the 0.01 grid.
5. Selection: R2's print score (`selection2_all.txt`) flagged at `THETA_SEL`.
6. Rule PnL per window: sum over bins and sides of P(fill) x (payout_s - rule price).

## VALIDATE metrics (2026-10-27..30, 1,152 windows, 27,988 cluster maker fills; `results/iter4_r3_validate_*.json`)

| metric | R3 | frozen R2 on the same days | target |
| --- | --- | --- | --- |
| presence AUC, no own state (primary) | **0.716** | 0.705 | >= 0.85 |
| market-activity-only baseline (same BUILD) | 0.685 (gain +0.032) | 0.673 | gain >= 0.05 |
| with own inventory (separate) | 0.747 | 0.740 | |
| within active windows | 0.708 | 0.698 | |
| side accuracy, 6,339 one-sided fill bins | **0.663** | 0.652 | >= 0.80 |
| side baseline (activity-only model) / own-inventory model | 0.613 / 0.70 | 0.600 | |
| price within one tick / exact | **0.709** / 0.359 | same | >= 0.80 |
| per-window PnL corr, Pearson / Spearman (1,089 windows) | **0.329 / 0.325** | 0.264 / 0.303 | >= 0.5 |
| selection AUC / within-window / recall / lift (R2 model) | 0.685 / 0.639 / 29.5% / 2.87 | same | 0.80 / 50% / 3 |
| per wallet presence (bosona / almach / mo-money) | 0.712 / 0.706 / 0.705 | | |
| per wallet side | 0.655 / 0.666 / 0.654 | | |
| per wallet price within tick | 0.710 / 0.706 / 0.710 | | |
| per wallet PnL corr Pearson | 0.302 / 0.290 / 0.316 | | |
| wallets' own BTC 5m maker return | +4.3% | | |

The high-accuracy target is not met. Why it is capped (VALIDATE aggregate): even with an oracle for the bin's own
future taker flow, a presence model reaches only 0.68 (0.73 with R3's features). In active windows 89.5% of bins
have bids hit on the side, but the cluster is filled in 11.7% of them. The missing variable is whether its bid is at
the top of the book at that moment, which the historical tape cannot show. Only books (the live lab, recording since
2026-10-31 12:18 UTC) or a book rebuilt from every match's calldata can.

## Why it works

It is a fast (though not the fastest) liquidity provider. It earns the spread from many dispersed takers whose orders
are larger than the tape's typical print, and it avoids most of the stale-quote losses that the average maker takes.
Sub-second makers own the freshly repriced levels; the cluster is filled where its price stands alone or ahead of
older orders. On 2026-10-26, measured
with each taker's own signing millisecond: other makers' bids are hit right after adverse Binance moves (12.5% of
their fills follow an adverse move of more than $5 in the last second, 7.2% within 250 ms). The cluster's fills are
exposed only to the last ~0.25-1.5 s (9.8% and 4.1%), because it re-signs its quotes 10-23 times a second and faster
when Binance moves. Its quotes track a TWAP-60 fair value of Binance (best explained by the futures price at the match
time) with a skew toward the side the market underprices, most clearly right after the open. It scales size with the
clock: 500-share orders in weekday US hours, when its return is highest (+4.7% STUDY, +5.1% VALIDATE on dollars
bought), and 62-250 at night and at weekends (+0.4% / +3.3%). In the busy second half of the lot most of the profit
came from round trips across the two outcomes: the shares it ends up holding on both sides of a window cost 0.89 per
pair on average (+$38.1k, +11.0% on $347k of paired dollars), while the unpaired directional remainder lost $14.4k
(-7.3%). In the quiet first half the directional part carried the profit (+4.6%). It sits at the best price but
usually behind part of the queue (first at its level in 31% of multi-maker matches), so it is filled when larger or
repeated taker orders use up the orders ahead of it. It is not paid for liquidity rewards ($0.81 in nine days) and
only a little for rebates ($5.0k, 8% of the lot PnL). The losers are the slower makers whose stale bids absorb the
informed flow, and the takers who cross its spread in both directions during a window without a speed edge.

## Can a normal user deploy it now

Not from this rule. The public-data version (R2) lost 12.8% under strict fills at 2 s latency in exam round 1, on
every day, because a quote that reacts in 2+ seconds is exactly the stale quote that takers pick off. The wallets'
own edge persists (+3.95% exam lot, +4.3% on VALIDATE). It depends on:

- sub-second requoting against Binance (spot or futures websocket) and the Polymarket CLOB: thousands of signed
  orders per minute per wallet (10-23 per second), which needs a co-located or low-latency setup and an API rate
  budget a home connection may not sustain;
- being at the top of the book on the 0.01 grid ahead of competing makers;
- capital for 500-share orders on both sides of several windows at once (roughly $50-150k turnover a day per wallet);
- the conditions in the latest development data: unchanged fee rate (0.07), continuous listings, the 01:00 UTC restart.

A replicator with a normal connection and computer should expect to be one of the slow makers this strategy profits
from, so zero or a loss, unless they can requote within about a second of every Binance move.
