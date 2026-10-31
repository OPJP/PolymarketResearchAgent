# jld-inplay-taker: lab notebook

Wallet `justaluckydude` `0xbca08c1bc204a34f2fddbe47b438b9bd42ac9705` (in-play US-sports taker).
Brief: `research/reverse_engineering/BRIEF.md`. Workspace: this folder + `.cache/re/jld-inplay-taker/`.
Dossier: `research/verdicts/0xbca08c...json`, `research/wallets/0xbca08c.../`,
`research/review_2026-10-31/challenge-inplay-taker-justaluckydude/`.

## Pre-registration (iteration 1, fixed for all iterations)

- H = 1792713600 (2026-10-23 00:00 UTC). Nothing at or after H is loaded: activity is fetched with end = H-1,
  tapes are requested with end <= H-1 and truncated at H, ESPN games used only if they start before H.
- A market's period = its Gamma `gameStartTime` (fallback: the wallet's first fill in it).
- **BUILD** = markets with game start in [2026-09-01, 2026-10-13) = [1790812800, 1791849600).
  (The wallet's whole history before 2026-10-13 may be used for description.)
- **VALIDATE** = markets with game start in [2026-10-13, 2026-10-23) = [1791849600, 1792713600), tapes cut at H.
  Choices between candidate rules are made on VALIDATE only (fitting happens on BUILD).
- **Primary metric (higher is better)**: `sel_auc` = within-market selection AUC on VALIDATE.
  Population: every public taker BUY print (data-api `/trades?takerOnly=true` row with side BUY; one row = one
  aggressive order) at or after game start in VALIDATE markets the wallet traded. Positives = the wallet's
  prints. Score = the frozen rule's point-in-time score: features use only tape prints in strictly earlier
  seconds than the print (t-1 and before), ESPN plays with wallclock + D <= t with D >= 5 s, market metadata
  known at listing, and the print's own price/outcome (what the decision maker sees in the book).
  No own-state features, no print-size features (size is a fingerprint, reported separately).
  AUC is the stratified (within-market) Mann-Whitney: sum over markets of concordant pairs / all pairs.
- Secondary (always reported): recall and lift at the pre-registered threshold (top 20% of scores within each
  market's population), market-permutation / timeline-shift p-value, presence AUC on (market, 10 s bin)
  in-play, side accuracy given it acts (vs market-only baselines: buy the favourite; buy the side whose price
  rose in the last 60 s), price within one tick, per-market PnL correlation, rule return under strict fills
  with latency >= 2 s.

## Data gathered

(updated as fetches complete)

## Hypotheses (mechanism candidates, iteration 1)

- M1 fast-feed reactor: it reacts to game events (scores and other WP-moving plays) faster than ESPN's public
  API; its buys follow the true event time and precede most other takers. Prediction: the wallet's prints lead
  the market's price move (others' prints follow), lag to ESPN wallclock is ~0-5 s, and direction agrees.
- M2 fair-value taker vs an external live line (sportsbook odds feed): it buys whichever side is cheap vs a
  live fair value, often both sides in one market (48% two-sided). Prediction: buys are followed by price
  moving toward its side (positive markout) even without game events; buys happen after Polymarket price moves
  that are not justified by game state (it fades noise), i.e. many buys are contrarian to recent tape moves.
- M3 cross-market propagation: after the moneyline moves, it buys stale spreads/totals of the same game
  (or vice versa). Prediction: its buys in market X follow price moves in sibling markets of the same event.
- M4 state-based value: buys driven by ESPN WP level (or a game-state model) vs price, not by changes.
- M5 schedule/inventory: periodic buying (e.g. scaling into a position) unrelated to events.

## Log

### Iteration 1 (2026-10-31, start 08:10 UTC)
