# directional-maker: frozen rule R3 (iteration 4, kept in iteration 5)

Rule id: **R3-presence-lgbm-refit-build4-clock**. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts, intervals=None)`,
pooled and per wallet), features `code/features2.py`, selection helpers `code/sel2.py`. Frozen model files next to the
code: `presence3_rule.txt` (rule), `presence3_activity.txt` (market-activity-only baseline), `presence3_own.txt`
(own-inventory variant, reported separately), `selection2_all.txt` / `selection2_activity.txt` with `THETA_SEL`. The rule
reads no live recording (`ALLOW_SEALED = False` is kept for the examiner's driver). Iteration 5 did not change the rule:
it moved the investigation from fills to the cluster's observed quotes in the raw book (development block 2026-10-31),
which is where the next rule has to come from. Scope: BTC 5m Up/Down windows, the three wallets (bosona, almach,
mo-money) pooled, with per-wallet metrics.

## Components (tags: exam-verified / VALIDATE-only / hypothesis)

| component | what the cluster does | tag | evidence |
| --- | --- | --- | --- |
| Engine | One engine signs every order of the three wallets: per-wallet sequential salt counter, `timestamp`, `metadata` and `builder` 0, restarted together daily at 01:00 UTC. About 17 signed orders/s per wallet (10-31). The three wallets post the same quote within 20 ms (same-side bursts of exactly 2-3 adds: 27% triplets, 0.6% of 4+). Orders are not post-only. | VALIDATE-only (counter); hypothesis (bursts, live block) | B1 calldata of the lot; `code5/live5k.py` |
| Selection | One engine over crypto Up/Down. BTC 5m is 78% of VALIDATE fills and 69% of absolute PnL; BTC 5m + 15m 87% / 89% (STUDY 54% / 56% and 63% / 75%). The BTC 15m window is worked mostly in its last five minutes with the same price rule (within one tick 66% vs 71% in BTC 5m). Which BTC 5m windows are switched on is a runtime switch with no public correlate yet. | hypothesis | `results/iter5_coverage.json`, `iter5_q1_15m.json` |
| Timing | Each wallet re-posts every quote about once a second (median 0.98 s per side, cancel-to-re-add 15 ms, a new price 96% of the time); Up and Down independently. When the Binance USD-M futures mid moves, the next re-post moves the same way within 50-250 ms (91% of 255 near-touch re-posts over 55 min, 85-97% in sub-samples; Bybit 70%, OKX 66%, Coinbase, Binance spot and Hyperliquid 48-55%); between futures moves the re-posts follow the Polymarket touch (89%). Its filled orders were posted 0-5 s before the match (46% within 1 s vs 6% at random). It stops about 30 s before the end. | VALIDATE-only (STUDY ms clocks); hypothesis (live block) | `iter5_live_c/d/g/j/k_*.json` |
| Side | Up and Down are quoted independently; it is filled on the side whose rung reaches the best bid, i.e. the side the futures fair says the market underprices. Rule: side with the higher predicted presence. | exam-verified (partial) | VALIDATE 0.663 vs 0.613 activity-only; exam round 1 0.655 vs 0.600 |
| Price | Fill tape: 0.01 grid at the best bid; rule = last clean print on s minus 0.01. Quotes (live): a ladder of 500-share rungs about 7.5 cents below the token's mid (q = -0.055 + 0.69 mid + 0.25 futures TWAP-60 fair, residual MAD 0.037), deeper near the end of the window and above fair 0.8; rung prices are not predictable to a tick from public inputs (held-out 21%). | exam-verified (partial) for the fill rule; hypothesis for the ladder | within one tick 0.709 VALIDATE, 0.688 exam; `iter5_live_quotefit.json` |
| Size | Runtime size class with a one-fifth level: 500/100 on Saturday 10-31, 62/12 or 250/50 on other days (not a clock schedule); several 500 rungs per side; a partially filled order is re-posted with its remainder (492.44, 76.38, ...). Size does not depend on the edge. | VALIDATE-only (calldata); hypothesis (live) | calldata of the lot and of the live block |
| Exit | Holds to resolution. Taker-buys the under-held complement (72-83% of its BTC 5m taker buys), sized to the imbalance or one fifth of it, at a pair cost of 1.06-1.12, then merges in 17-51% of those windows: a loss cap that carries only 2-4% of PnL; maker-maker pairs are ~90% of paired shares. | VALIDATE-only | `results/iter5_flatten.json` |
| Information | Reference = Binance USD-M futures (bookTicker mid). Not settlement-informed: its late inventory follows the true outcome in 60% of the windows where the Binance proxy is wrong (market 73-85%); a Chainlink TWAP-60 fair explains its quotes worse than the futures fair (MAD 0.105 vs 0.037). Settlement = RTDS `crypto_prices_twap_sixty` at the window end (= Gamma finalPrice, 3/3). | VALIDATE-only (disagreement windows, aggregate); hypothesis (live) | `iter5_disagree.json`, `iter5_live_h_*.json` |

## The rule (all parameters constant; unchanged since iteration 4)

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

| metric | R3 | target |
| --- | --- | --- |
| presence AUC, no own state (primary) | **0.716** | >= 0.85 |
| market-activity-only baseline (same BUILD) | 0.685 (gain +0.032) | gain >= 0.05 |
| with own inventory (separate) | 0.747 | |
| side accuracy, 6,339 one-sided fill bins | **0.663** (activity 0.613, own inventory 0.70) | >= 0.80 |
| price within one tick / exact | **0.709** / 0.359 | >= 0.80 |
| per-window PnL corr, Pearson / Spearman (1,089 windows) | **0.329 / 0.325** (x size class: 0.321-0.341 / 0.283-0.288; ceiling 0.688 / 0.780) | >= 0.5 |
| selection AUC / recall / lift | 0.685 / 29.5% / 2.87 | 0.80 / 50% / 3 |
| coverage of fills / of absolute PnL (BTC 5m) | 0.783 / 0.686 (BTC 5m + 15m: 0.868 / 0.891) | 0.80 / 0.80 |
| per wallet presence (bosona / almach / mo-money) | 0.712 / 0.706 / 0.705 | |
| wallets' own BTC 5m maker return | +4.3% | |

The high-accuracy target is not met. Where the gap is (iteration 5): the fill is decided by whether one of its ladder rungs
stands at the price a taker reaches. The rung prices are visible in the raw book but are not a tick-precise function of
the public inputs tried (futures fair, the token's book, time left: 21% within a tick on held-out time). The historical
tape shows neither the rungs nor the book.

## Why it works

It is a liquidity provider whose ladder is anchored to the Polymarket book and pulled along by the Binance USD-M futures
price faster than the average maker: its re-posts follow a futures move within 50-250 ms, while other makers' stale bids
stay exposed for 3-5 s (STUDY ms clocks). It earns the spread from many dispersed and large takers: its fills come from
larger prints than the tape's typical one and from prints that reach down to its rungs. In busy periods most of the profit
came from buying both outcomes cheaply at different moments of a window (paired shares at 0.89 per pair, +11% on paired
dollars), while the unpaired directional remainder lost. It is not paid for information about settlement (it prices off
Binance futures, not Chainlink, and its late inventory is no better than the market's), not for liquidity rewards ($0.81
in nine days), and only a little for rebates (8% of PnL). The losers are slower makers whose stale bids absorb the
informed flow, and takers who cross its spread in both directions during a window.

## Can a normal user deploy it now

Not from this rule. The public-data version (R2) lost 12.8% under strict fills at 2 s latency in exam round 1, because a
quote that reacts in 2+ seconds is the stale quote that takers pick off. The wallets' own edge persists (+3.95% exam lot,
+4.3% VALIDATE). It depends on: a Binance USD-M futures websocket feed and a Polymarket CLOB connection with re-posts within
~250 ms (several 500-share rungs per side, re-posted about once a second, ~17 signed orders a second per wallet); capital
for 500-share rungs on both sides of several BTC 5m and 15m windows at once; and unchanged fees (0.07 taker), listings and
matching behaviour, which held on 2026-10-31. A replicator with a home connection and computer should expect to be one of
the slower makers this strategy profits from: zero or a loss, unless they can match its re-post speed.
