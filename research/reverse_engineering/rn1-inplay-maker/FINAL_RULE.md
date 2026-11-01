# RN1 in-play maker: frozen rule after iteration 1

Wallet `0x2005d16a84ceefa912d4e380cd32e7ff827875ea`. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts,
intervals=None)`), models in `code/models/`. Tags: **exam-verified** (passed a sealed exam; none yet),
**VALIDATE-only** (measured on VALIDATE 2026-10-16..22, or on live development blocks), **hypothesis**.

Status: **not decoded**. The presence rule is far below the target (see the metrics table). What is decoded is
the shape of the quote (price, size, two-sidedness, holding), not when and where the quote rests.

## Components

1. **Selection** (VALIDATE-only, weak). It makes in-play markets of soccer, tennis, CS2 and US football:
   moneyline, totals, spreads, exact score, first-half totals, halftime result; it skips most player/prop markets
   (unknown market type: 0% of cells filled) and team totals (0.6%). Inside its markets it is filled in only
   ~15-18% of in-play minutes that carry a taker print. Encoded as listing features of the presence model
   (sportsMarketType, family, line, event size).
2. **Timing** (VALIDATE-only, weak). Almost never filled before kick-off (0.6-1.2% of pre-game cells with taker
   prints vs 10-13.5% in play), most often in the first 90 minutes of play. Withdraws around game events (legacy:
   1.4% of passive fills in the first 5 s after ESPN plays vs 4.9% for all makers; absent after soccer goals before
   the public price jump). The trigger of its withdrawals and requotes is not identified (sports websocket event
   study p_link 0.20).
3. **Side** (VALIDATE-only). BUY-only, both outcomes. The outcome it ends up buying in a minute is the complement
   of the taker's direction; the tape predicts it no better than "buy the underdog" (0.54), which is the rule. Its
   fills run on the side it already holds more of (P(deficit side) 0.41-0.42): it does not skew toward completing
   pairs.
4. **Price / quote placement** (hypothesis from live development blocks, BUILD for live-only data; VALIDATE-only
   for the pair structure).
   - Both outcomes are quoted as a **1-tick market**: near-simultaneous fills on the two outcomes sum to 0.990
     (VALIDATE, n = 517, q25 = q75 = 0.990).
   - Against the recorded book at signing: it **joins a 1-tick spread and improves a wider spread by one tick**
     (exact 55.5% vs 39.9% for the touch; within one tick 87.9% vs 90.7% for the touch); posting latency from
     signing to the book is a median ~250 ms.
   - On the tape (no book, pre-T0 lots), the rule reduces to the last other-trader print on the outcome, one tick
     lower when that print lifted the ask: within one tick 71.5% (the last-print anchor itself 72.1%).
   - Requotes: filled orders are a median 12.8 s old (2.8 s at the 5th percentile); orders are re-signed often.
5. **Size** (VALIDATE-only). Order size in shares, independent of price (log-log slope 0.02): median ~1,550 shares,
   modes near 700 / 1,500 / 3,000 shares. What sets the tier is not identified.
6. **Exit** (VALIDATE-only). None: no SELL, MERGE or SPLIT rows in 21 development days; positions are redeemed at
   resolution. Complete pairs lock the 1-tick margin; the unpaired residual carries the adverse selection.

## Metrics on VALIDATE (pre-registered primary metric: presence AUC)

See `state.json` `target_metrics` and `results/presence_iter1_*.json`, `results/final_rule_validate_iter1.json`.

## Why it works

RN1 sells immediacy on both sides of in-play markets at the narrowest possible spread (one tick) and holds what it
buys to resolution. Complete pairs bought at bid + (0.99 - bid) earn the tick for sure (+$372k in the 14 BUILD
days, +$184k in the 7 VALIDATE days), plus maker rebates and liquidity rewards (~$8k a day). Its losses are the
unpaired inventory left when the price moves through its quote (residual +$93k BUILD, -$125k VALIDATE). The
takers who pay the tick are the in-play flow that wants immediacy (2,669 distinct takers in one VALIDATE week, the
largest 6.8% of its fills). What keeps the residual small enough is not visible in public data yet: the earlier
studies show it is off the book before game events move the price, which public-data makers are not (they lose
5-19% in the same markets). The 1-second taker delay of sports markets gives a maker with a fast event feed time to
cancel before delayed takers arrive.

## Can a normal user deploy it now

Not as decoded. The quote shape (1-tick two-sided bids of ~1,500 shares, join or improve the inside, hold to
resolution) is easy to copy, but a public-data copy of it loses money in the same markets (earlier backtests:
-5% to -19% at 0-30 s latency with strict fills), because the edge depends on withdrawing before game events,
which needs an event feed faster than the public price. It also needs ~$1-2M of collateral to run at its scale.
Conditions still hold in the latest development data (live blocks of 10-31 and 11-01: same order sizes, ages and
placement).
