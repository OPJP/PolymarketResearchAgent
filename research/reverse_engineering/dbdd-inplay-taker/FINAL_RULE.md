# dbdd-inplay-taker: frozen rule (iteration 1)

**Rule id**: `R-LGB-PUB-1` (behaviour-cloning score; not yet distilled to a hand rule).

**What it scores**: every in-play taker BUY print (one data-api `takerOnly` row) in a market the wallet trades.
The score estimates how likely the print is this wallet's, from public, point-in-time state only:

- tape state at T-2 s for the print stamped T: seconds since the previous print (quiet), last price of the token,
  the print's price minus the last price, token price moves over 10/30/60/300/900 s, taker print counts / USD /
  signed flow over 10/60/300 s, prints so far in the market, game minute (from Gamma `gameStartTime`);
- sibling markets of the same game (base event slug): prints in the last 10/60 s, largest price move over
  30/120 s, seconds since a sibling print, number of siblings;
- listing metadata: sports market type, family, line, fee rate, outcome label (Over/Under/Yes/No).

No own-state features (no wallet inventory, no own fill counts, no time since its own last fill). The print's own
size is NOT used (a size fingerprint model is reported separately as a diagnostic only).

**Frozen artefacts**: `code/model_lgb_public.txt` (LightGBM, trained on BUILD games 2026-09-23..10-13 only,
early-stopped on the last 20% of BUILD by time), `code/model_lgb_public_spec.json` (feature list, category
lists). Flag threshold (pre-registered): top 15% of scores within each market.

**Evaluate**: `code/final_rule.py: evaluate(start_ts, end_ts)` loads the wallet's activity, Gamma metadata and
full public taker tapes for the markets it traded with game start in [start_ts, end_ts), builds the same
features, scores and returns selection (within-market AUC, recall/lift at top 15%, stratified rank-sum p),
side baseline, and outcome metrics (rule's per-market PnL on flagged other-taker prints vs the wallet's).

**VALIDATE performance**: see `state.json` -> `best.validate_metrics` (filled at the end of iteration 1).

**Known limits**: the population is conditional on the wallet's market choice; the side model and price model
are not yet frozen; the rule identifies *when* the wallet tends to trade within a market (early in the in-play
life, quiet book after a recent up-tick), not *why* (its information source is not in the public data so far).
