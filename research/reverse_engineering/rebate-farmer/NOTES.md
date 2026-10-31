# rebate-farmer: lab notebook

Wallet `0xb55fa1296e6ec55d0ce53d93b9237389f11764d4` (crypto Up/Down volume trader, profit = Diamond taker rebate).

## Pre-registration (iteration 1, written before any VALIDATE data was looked at)

- Frozen dates: as_of 1793318400; holdout H = 1792713600 (2026-10-23). Nothing at or after H is loaded
  (every fetcher passes end < H and asserts it).
- BUILD = [2026-09-01, 2026-10-16) (1788220800..1792108800), extended further back in later iterations.
- VALIDATE = [2026-10-16, 2026-10-23) (1792108800..1792713600), the last 7 days before H.
  Candidate rules are chosen on VALIDATE only; all fitting/exploration on BUILD.
- Primary metric (fixed across iterations, higher is better): **presence AUC without own-state
  features** on (market, 10-second bin) cells, VALIDATE, pooled over the wallet's crypto Up/Down
  families (all assets, 5m/15m/1h/4h), universe = every market of those families whose window
  overlaps VALIDATE, cells over [window_start - pre, window_end) where `pre` is fixed from BUILD
  (see "Universe" below). Label = wallet has >= 1 fill (activity TRADE row) in the cell.
- Secondary (always reported): side accuracy given action (with and without own-state, vs the
  best market-only baseline), price-within-one-tick share, per-market PnL correlation,
  maker/taker role accuracy.

## Data gathered

(see sections below; large data in `.cache/re/rebate-farmer/`)

## Hypotheses ledger

(see state.json for the machine-readable copy)

## Log
