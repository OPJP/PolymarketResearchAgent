# directional-maker: frozen rule R6 (iteration 8)

Rule id: **R6** = R5 on BTC 5m (unchanged: R3 presence stacked with the Chainlink settlement stream, R4 match-clock
price) + **BTC 15m in the universe** (R3's model class refitted on BTC 15m) + **the fill side scored per fill with the
decoded quote-side rule** (sign of the Chainlink edge over the Polymarket mid at the match ms). Code: `code/final_rule.py`
(`evaluate(start_ts, end_ts, intervals=None)`, pooled and per wallet, per family and over the union). R5 is archived as
`code/final_rule_r5.py`, R2 as `code/final_rule_r2.py`. Frozen model files: `presence3_rule.txt` / `presence3_activity.txt`
/ `presence3_own.txt` (BTC 5m), `presence15_rule.txt` / `presence15_activity.txt` (BTC 15m, new), `selection2_*.txt` with
`THETA_SEL` (BTC 5m). Feature code: `features2.py` (5m), `features15.py` (15m: the same features with bins [0, 900) s).
Live inputs (the shared recorder's `clob_crypto` trades `x` and books `q`, the Chainlink recordings dy_rtds / dx_rtds /
dm_rtds) are read with tolerant readers that honour `ALLOW_SEALED` (False except in the examiner's driver); Chainlink
values missing from the recordings come from Polymarket's `crypto-price` endpoint when `FETCH_CL` (`code/cl_source.py`).
Binance 1-s seconds come from the daily archive, with a REST 1-s kline fallback for days not yet archived (new).

**Universe (pre-registered 2026-10-31 iteration 8, before any sealed block was scored):** BTC 5m and BTC 15m Up/Down
windows, the three wallets (bosona, almach, mo-money) pooled with per-wallet metrics; metrics are reported per family
and pooled over the union; a block in which BTC 5m is off is scored on BTC 15m. Coverage of the union: VALIDATE
2026-10-27..30 0.868 of fills / 0.891 of absolute PnL; development blocks 10-31 00-06 0.91 of trades / 0.95 of dollars,
12:00-16:54 0.94 / 0.93, 16:54-18:00 0.82 / 0.93 (BTC 5m off); early BUILD (10-20) only 0.59 / 0.65.

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine signs every order of the three wallets: per-wallet sequential salt; until ~06-21 every order carried its real signing ms, since 06-22 `timestamp`, `metadata`, `builder` 0; daily restart 01:00 UTC; 13-26 signed orders/s per wallet. | VALIDATE-only | B1 calldata (lot, June); `code8/june_fetch.py` |
| Information | The ladders are re-priced on each **Chainlink BTC/USD report** (the settlement stream) within ~0-150 ms of the public RTDS relay's publish (bursts agree 0.76-0.81 with the report's change after the publish, 0.35-0.44 before); no other maker reacts. Between reports its 500s re-post 50-250 ms after Binance futures moves (October); in June (real signing ms) it signed 100-400 ms after Binance moves (|move| 4-7x random at 150-400 ms before signing, 1.0x in the last 50 ms), with the limit price current at signing (corr 0.85 with a Binance fair at the signing ms). No lead over public feeds. | VALIDATE-only (live, June development data) | `code7/i2_publish.py`, `code8/june_lag.py`, `code8/june_price.py` |
| Selection | One engine over crypto Up/Down; the rule's universe is BTC 5m + 15m (see above). Nearly every window is quoted (VALIDATE 94.5% of 5m windows active; 15m 53%). BTC 5m is switched off for hours at a time (10-31 16:53:5x UTC in all wallets at the day's PnL low); trigger not decoded (loss limit, breaker or module failure; X58/X70). BTC 15m presence (R3 class) 0.812 vs 0.778 activity on VALIDATE. | hypothesis (on/off); VALIDATE-only (15m presence) | `code8/train15.py`, `code7/stoploss.py` |
| Timing | Re-price passes on each Chainlink publish plus re-posts after Binance moves; the filled orders are fresh 500-share posts at the touch (78%), posted a median ~95 ms after some trade and matched ~0.7 s later; it stops ~30 s before the end. | VALIDATE-only (live) | `code6/q1_confirmed.py`, `code7/i2_publish.py` |
| Side | **The outcome it buys is the one whose Chainlink edge over the Polymarket mid is positive.** Per fill, at the server match ms: Up iff the digital fair of Up from the Chainlink report stamped floor((T - 1.432 s)/1 s) (Gamma priceToBeat strike, 1.4 x 300-s realised vol) exceeds the Up mid of the latest book record. No fitted parameter. **Live VALIDATE (10-31 15:00-16:30): 0.836 through `evaluate()` (n 1,341; 5m 0.836, 15m 0.834; bosona 0.858, almach 0.871, mo-money 0.787)**, 0.841 / 0.874 on the own raw touch (`code8/fill_side.py`); market-only baselines on the same fills: Binance-spot edge 0.56, futures edge 0.55-0.60, cheaper side 0.52-0.55, always-Up 0.51-0.61, the side the previous print sold 0.38-0.43. Not stable over the whole development block: 16:30-18:00 0.708 (n 284; 5m 0.61 before the 16:53 switch-off, 15m 0.775) against a Binance-spot-edge baseline of 0.718, and 14:06-15:00 0.62 (the half hour 14:30-15:00 0.45: whole windows bought against the edge); pooled over 14:06-18:00 about 0.79. On block-clock inputs the same rule scores 0.72 (vs 0.85 on the match clock). Window level (one-sided windows, n 21): 0.62 from the public mean edge, 0.76 from the edge at its fill times. Historical bin-level side (R3/R6 presence score): 0.672 union, 0.663 5m (exam 0.655). | VALIDATE-only (live; needs replication on 11-01 06-12) | `code8/fill_side.py`, `side_posture_match_clock` |
| Price | Fill price = last clean print minus 0.01. Match clock (R4): **0.860** within a tick through `evaluate()` on live VALIDATE (n 1,194; each wallet 0.85-0.87; anchor last print 0.856), BTC 15m 0.843 (iteration 6); block clock 0.709 (5m VALIDATE), 0.666 (15m), exam 0.688. This IS the trivial anchor "last print" on a fresh clock. The ladder LEVEL is not decoded to a tick: each market's ladder hangs off its own mid with a ~0.2 Chainlink skew; inverting the 5m and 15m ladders at the same instant gives internal prices that agree within a tick-equivalent only 20% of the time, and their disagreement is the two mids' disagreement (slope 0.83, R^2 0.79). | exam-verified (block clock); VALIDATE-only (match clock) | `price_match_clock`, `code8/m1_invert.py` |
| Size | October: 500 x 2^k with a one-fifth level; 500 in the weekday 12-21 UTC session or when the 300-s futures vol at the open is high, else 62 / 250; June: 50 / 100 / 300; remainders re-posted. | VALIDATE-only | `code6/m5_size.py`, June calldata |
| Exit | Holds to resolution; small complement taker buys sized to the imbalance and merges (2-4% of PnL). | VALIDATE-only | `results/iter5_flatten.json` |

## The rule (all parameters constant)

1. Tape hygiene: drop every data-api taker print in a transaction where a cluster wallet traded, and the cluster's own
   taker prints; for live inputs, every trade record whose transaction holds a cluster trade.
2. Presence, BTC 5m (R3, unchanged): P(cluster maker BUY fill on s in [t, t+10)), t in [0, 300) = `presence3_rule.txt`
   on features published by t (time, side, clean-tape activity, Binance 1-s TWAP-60 fair, z, returns, realised vol,
   edge, window path, previous-window proxy outcome and strike move, UTC hour, weekday, US-session flag). No own state.
   R5's Chainlink stack where the series exists (unchanged; `code/r5.py`).
3. Presence, BTC 15m (new): the same feature definitions on bins t in [0, 900) (`features15.py`) scored by
   `presence15_rule.txt` (fitted on BUILD 15m windows 2026-10-09..26 with R3's LightGBM parameters and rounds).
4. Side: per fill on the match clock (where the shared recorder has the fill's transaction): Up iff fair_CL(Up) > Up mid
   (step "Side" above, `side_posture_match_clock`); per bin (historical, block clock): the side with the higher predicted
   presence.
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
| coverage fills / abs PnL | 0.868 / 0.891 | 0.783 / 0.686 | | 0.80 / 0.80 |

Live VALIDATE (development block 10-31 15:00-16:30 UTC, pre-registered in iteration 6; through `evaluate()`):
per-fill side **0.836** (n 1,341) vs market-only <= 0.61; match-clock price **0.860** (n 1,194); 5m presence 0.711 vs
0.655 activity; union presence 0.775 vs 0.750.

Quantitative account of what is still unexplained (iteration 8, `code8/a4_ceiling.py`, `code8/sel_oracle.py`, live):
- 10-s fill presence is taker-bound: with the cluster's actual quote given as an oracle it reaches only 0.80 (public
  inputs 0.66, activity 0.62); adding the bin's own future taker flow does not help. The presence bar (0.85) cannot be
  reached on fills by any quote decoder on this unit.
- At the print level the quote is binding: with the quote as an oracle, print selection reaches 0.81-0.83 with recall
  62-69% at lift 3.3-3.4 (the selection bar), against 0.69 from public inputs. So the open problem is predicting the
  quote: whether a cluster 500 sits at the touch now is predicted at 0.748 from public inputs (activity 0.672; the
  Chainlink edge carries the gain), and the ladder level is not a function of any reference price to a tick.

## Why it works

It is a two-sided liquidity provider whose ladders hang off the Polymarket mid of each market and are skewed toward the
settlement source itself, the Chainlink BTC/USD report, re-priced the moment Polymarket's public relay publishes each
report; no other maker re-prices on the report. The skew puts the 500-share bid of the outcome that the latest report
favours at the touch, so the cluster ends up buying the outcome the settlement stream favours (0.84 of its fills live)
from sellers who are reacting to the futures (their direction agrees with the futures, not with the displayed
Chainlink price). It is paid the spread (pair cost ~0.88) by takers who cross it, mostly front-end and non-HFT first
prints; latency takers do not reach it because it re-anchors within ~250 ms of futures moves and the venue's taker speed
bump keeps reacting takers behind its re-post. The skew has a cost when the Chainlink report itself is noisy (since
10-31, 1-s white noise of ~$9): fills where Chainlink valued the token above the futures lost money live, and the BTC 5m
blocks of 10-31 lost 11.9% and 3.9% before BTC 5m was switched off. It is not paid for liquidity rewards ($0.81 in nine
days) and only a little for maker rebates (8% of PnL).

## Can a normal user deploy it now

Not from the public-data rule. The tape-only version lost 12.8% under strict fills at 2-s latency in exam round 1. What it
needs, all still true on 2026-10-31: the Chainlink report from Polymarket's public RTDS relay (filters "" for every 1-s
update), a CLOB connection that re-prices within ~0.1 s of each publish and of Binance moves, capital for 500-share rungs
on both outcomes of several BTC 5m and 15m windows (~$45-56k of collateral per wallet), and unchanged fees (0.07 taker),
listings and matching. A home connection receives the relay 0.12-0.35 s after its publish stamp and would be one of the
slower makers this strategy profits from: expect zero or a loss without low latency. In the new Chainlink noise regime
the strategy itself lost money on BTC 5m (10-31) and its operator switched BTC 5m off.

## Open leads (not part of the frozen rule)

- Kalshi KXBTC15M leads the Polymarket 15m book by about a second (corr of 1-s changes 0.30 at +1 s, R^2 beyond 1-s
  Binance spot 0.094 -> 0.134), and the cluster's 15m fills were on the Polymarket side that was cheap relative to Kalshi in
  79% of 159 fills (~9 quarters, strikes not aligned): to replicate with aligned strikes (`code8/a4b_kalshi.py`).
- The fast re-posts of its 500s step up 3-4 c toward the touch in 87-95% of cases regardless of the mid, Chainlink or
  futures change (persistent rank, corr 0.85): the ladder is stateful (A3), the route to predicting the quote level.
- The posting hazard on exact public clocks (RTDS publish ms, futures changes, trades) reaches 0.83 per 50-ms bin.
