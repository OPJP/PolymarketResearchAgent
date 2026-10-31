# elmcap2-carry: frozen rule after iteration 1

Rule id: `L2_lgbm_price_time_lag3660`. Code: `code/final_rule.py` (`evaluate(start_ts, end_ts)`), model file
`code/model_L2.txt` (LightGBM, fitted on BUILD only by `code/a7_final.py`), cell features `code/cells.py`, universe
`code/universe.py`, metrics `code/metrics.py`.

## What the wallet does (mechanism as deciphered so far)

elmcap2 is a resolution-pending carry book. It rests large maker bids (95.6% of its own on-chain fills are
maker fills) on the side the market already treats as certain, mostly at 0.99-0.999 (USD-weighted median buy
price 0.997; 37% of USD at 0.999), and holds to resolution. Its timing is anchored on when the outcome becomes
settled in substance, not on the calendar: the USD-weighted median buy is 41 h before on-chain resolution and
37% of USD is bought after the market's endDate (deadline passed, event happened, word said) while UMA has not
yet settled. It keeps resting orders for hours to days (on-chain order lifetimes p75 ~13 h, p90 ~3 days) and
re-posts. FOMC markets are the same trade a few days before the statement at 0.95-0.99.

## The rule (point-in-time, no own-state features)

For each non-sports, non-Up/Down market with endDate in the window (Gamma volumeNum >= $20k), every 6-hour cell
from endDate - 14 d until resolution (cap endDate + 14 d), compute from CLOB hourly prices stamped at or before
t0 - 1 h - 60 s:

- `pf`: favourite price (max of the two sides), `lpf = -log10(1 - pf)`;
- `pf6`, `pf24`, `pf72`: the same side's price 6/24/72 h earlier;
- `hrs99`, `hrs95`: hours since that side last traded below 0.99 / 0.95 (time spent in the "settled" state);
- `vol24`: std of hourly price changes over the last 24 h;
- `h_end`: hours to endDate (negative after it), `after_end`.

Score = LightGBM probability (model_L2.txt). Gain importance: hrs99 0.23, pf72 0.16, h_end 0.16, pf 0.11,
vol24 0.10, pf24 0.08, hrs95 0.07, pf6 0.07. In words: the wallet is present when one side has been priced at
0.99+ for a while (it waits for the outcome to be settled in substance, then sits on the bid), around and after
the endDate, in calm markets; presence per 6-h cell rises from <0.1% at pf < 0.95 to 0.8% at 0.99-0.995 and
1.9% at 0.995-0.998 (BUILD, weighted).

- Side: buy the favourite (`pf` side).
- Price: bid the PIT favourite price rounded down to the tick (0.001 above 0.96), capped at 1 - tick.
- Thresholds (fixed on BUILD): market selected if its max cell score >= 0.05083; cell predicted if score >= 0.02672.
- Sizing: not modelled; under strict maker fills the rule's capital per market correlates 0.50 with the wallet's, but
  the PnL correlation is 0.20 (the wallet earns 0.89% on its book vs 0.28% for the rule: it gets better prices or
  avoids some low-margin fills).

## VALIDATE metrics (endDate 2026-09-01..2026-10-22, resolved before H; 3,208 markets, 117,132 cells, 277 positive)

| metric | value | target |
|---|---|---|
| presence AUC (primary) | **0.896** | >= 0.85 met |
| presence AUC by family | crypto 0.93, deadline 0.85, election 0.97, FOMC 0.85, other 0.86 | |
| selection AUC (market level) | 0.906 (permutation null 0.50, p = 0.001) | >= 0.80 met |
| selection recall / lift at BUILD threshold | 59.6% / 6.9x (hypergeometric p = 8e-23) | >= 50% at >= 3x met |
| side: wallet buys the PIT favourite | 97.1% of predicted cells; 84.8% of all its cells | >= 80% met, but equals the "buy the favourite" baseline (not above it) |
| price within one tick | 90.4% of predicted cells; 77.3% of all its cells | |
| per-market PnL correlation, unit size per predicted cell | Pearson 0.015, Spearman 0.24 | >= 0.5 NOT met |
| per-market PnL correlation, strict maker fills (unlimited bid at the rule price, filled only by later taker SELL prints at or below it, >= 2 s after the cell starts; 462 markets) | Pearson 0.195, Spearman 0.14; capital deployed per market Pearson 0.504 | >= 0.5 NOT met (capital allocation matches, PnL does not) |
| strict-fill return vs wallet's own return on the same markets | rule 0.28% on $3.13M, wallet 0.89% on $5.79M | |
| cell level at cell threshold | recall 37.5%, lift 10x, 52.7% of the wallet's USD | |

Robustness (VALIDATE AUC, BUILD-fitted): price lag 60 s 0.898 vs 1 h + 60 s 0.896 (no hourly-bucket leak); full
22-feature model 0.881-0.884; without age 0.899; without text family flags 0.893-0.902; explicit 3-way lookup
table (pf x hours-to-endDate x hrs99) 0.803.

## Not yet met / next

PnL correlation needs a sizing/price model from tape liquidity (the wallet's per-market USD spans $4 to $8M); side
accuracy cannot beat the favourite baseline by construction unless the 0.49 coin-flip bids (3% of BUILD cells, 15%
of VALIDATE cells) are modelled. `evaluate()` reports unit-size and strict-fill PnL (slack 0 and 1 tick).
