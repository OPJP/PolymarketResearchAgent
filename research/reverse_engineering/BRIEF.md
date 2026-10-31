# Deep reverse engineering: brief for every agent

You are an expert quantitative reverse engineer. Your job is to decipher, as
exactly as the public record allows, what one Polymarket trading strategy
does: which markets it trades, when it acts, which side, at what price, why,
and how it makes money. Previous attempts (see your dossier) found only
partial matches: the best public-data rules ranked the wallet's trades above
other traders' 55-65% of the time and covered 25-50% of its trades. That is
not good enough. Go deeper, use more data, and keep going until you reach a
high accuracy or a genuine wall.

## Frozen dates and the holdout (non-negotiable)

- Study date `as_of` = 1793318400 (2026-10-30 00:00 UTC).
- Holdout start `H` = 1792713600 (2026-10-23 00:00 UTC).
- **Development data: anything with timestamps before `H`.** Go back as far
  as the data allows (the wallet's whole history, not just 30 days). Split it
  yourself into BUILD (explore, fit) and VALIDATE (the last 7+ days before H,
  or the last 30%+ of events); choose between candidate rules on VALIDATE only.
- **Holdout: [H, latest available)**, which includes the forward days after
  `as_of`. Do not load, plot or summarize holdout-period market data, spot
  data, fills or outcomes while developing. An independent examiner will run
  your frozen rule on the holdout once, and will read your code to check that
  nothing was fitted on it.
- For event strategies with sparse events (FOMC meetings), the holdout is the
  events that resolve on or after H.
- Prior study files in `research/` report some numbers for 2026-10-23..30;
  they are context only, never a fitting target.

## No future data

Every decision feature at time t may use only information published at or
before t: tape prints at their block timestamp (and remember a print stamped
T may have matched up to 2 s earlier), a spot second one second after it
ends, a play at its ESPN wall clock plus a delay of at least 5 s, market
metadata fields known at listing (never outcomePrices, closedTime,
eventMetadata.finalPrice/priceToBeat as of resolution). Outcomes only settle
PnL. The wallet's own net inventory in a market is legitimate state for
describing its policy (it knows its book), but report every model with and
without own-state features, and never use the time since its own last fill or
its own fill counts as features (they predict activity trivially).

## Data: expand it (the earlier studies used too little)

The HTTP cache `.cache/http.sqlite` is shared and safe for concurrent use; go
through the polyrea adapters so every fetch is cached. Fetch politely (the
clients rate-limit per host). Useful sources:

- **Wallet record**: `PolymarketData().activity(wallet, start, end)` back to
  its first trade (cursor paging, cached); `/v2/user-pnl` daily series;
  `/positions`, `/value`. `polyrea.workflows.investigate.load_window` builds a
  ledger.
- **Every market the wallet traded** in your development period, not a sample:
  Gamma metadata (`markets_by_condition`), full tapes from data-api `/trades`
  (`PolymarketData().market_trades(cid, start, end, taker_only=...)`; taker
  rows are aggressive orders, the rest are maker rows; tape prices are snapped
  with `polyrea.analysis.updown.snap_price`). Also a matched set of markets it
  did not trade, to learn what it avoids.
- **On-chain orders** (new, powerful for makers): Polygon `eth_getLogs` for
  `OrderFilled` on the CTF exchanges, filtered by topic2 = maker (the wallet,
  32-byte padded) or topic3 = taker. In the study period fills come from the
  V2 exchanges `0xe111180000d2663c0091e4f400237545b87b996b` and
  `0xe2222d279d744050d28e00520010520000310f59` (both verified in cached
  receipts), topic0
  `0xd543adfd945773f1a62f74f0ee55a5e3b9b1a28262980ba90b1a89f2ea84d8ee`, topics
  [orderHash, maker, taker], data [side, tokenId, makerAmountFilled,
  takerAmountFilled, fee, ...] (side 0 = BUY). Older history used the V1
  exchanges (topic0 `0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6`,
  data [makerAssetId, takerAssetId, makerAmountFilled, takerAmountFilled,
  fee]); verify V1 addresses from a receipt before filtering on them.
  `polyrea/adapters/chain.py` (`decode_fills`) decodes both. Grouping a
  wallet's maker fills by `orderHash` reconstructs each resting order: its
  limit price, size, how long it rested, how often it was replaced, the price
  ladder it keeps. Block timestamps via `eth_getBlockByNumber` (cache them).
  RPC: `https://polygon.drpc.org` through `HttpClient.post_json` (keep blocks
  per call small, a few thousand; drpc rate-limits).
- **Reference prices**: `polyrea.adapters.spot.binance_seconds` (1-s klines),
  Binance aggTrades archives with millisecond timestamps
  (`https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-YYYY-MM-DD.zip`,
  SHA-256 in `.CHECKSUM`; fetch with `HttpClient.get_bytes`), Kraken trades,
  Coinbase/OKX candles (registered external sources in `polyrea/pit.py`),
  Chainlink's on-chain BTC/USD aggregator on Polygon if useful.
- **Sports and esports**: `polyrea.adapters.espn` (play-by-play with wall
  clocks, win probability, soccer key events); test reachability of other
  public sources (e.g. bo3.gg for CS2) before relying on them.
- **Events**: FOMC calendar, deadline markets via Gamma.

Put large intermediate data in `.cache/re/<your key>/` (git-ignored), not in
the research folder.

## Tools you can reuse (read the code)

- `polyrea/analysis/updown.py`: Up/Down window model (`windows_from_markets`,
  `fair_up_vectorized` with the pre-window TWAP strike, `SpotIndex`), score
  functions, `match_test` (rotation null, two stratifications, effect size,
  `tape_momentum_sign` control), `maker_buy_prints`, `taker_flow`, taker and
  maker backtests (`backtest`, `maker_backtest`, `spot_reactive_maker_backtest`
  with `match_slack`, `fixed_price_ladder_backtest`), `quote_price` (dynamic
  tick).
- `polyrea/workflows/updown_study.py`: `sample_blocks`, `all_blocks`,
  `load_period` / `_load_period`, `run_frozen_rule_extension`.
- `polyrea/workflows/sports_study.py`, `polyrea/workflows/maker_study.py`,
  `polyrea/analysis/tape_maker.py`, `polyrea/analysis/profile.py`,
  `polyrea/analysis/ledger.py`, `polyrea/analysis/rebates.py`,
  `polyrea/pit.py` (point-in-time store and guarded view), `polyrea/stats/`.
- Python packages: numpy, pandas, scipy, statsmodels, scikit-learn, lightgbm,
  pyarrow. Interpreter: `/home/user/PolymarketResearchAgent/.venv/bin/python`,
  run from the repo root.

## How to work (suggested ladder; go beyond it)

1. Read your dossier and, if continuing, your `NOTES.md` and `state.json`.
2. Expand the data (above). Measure what you could not see before.
3. Describe the behaviour precisely: per market and per second, what the
   wallet does (fills, sides, prices relative to the touch, order sizes and
   lifetimes, inventory paths, timing relative to spot moves, tape moves,
   game events), and what it avoids.
4. Behaviour cloning: train models (e.g. LightGBM) on point-in-time state to
   predict its actions (whether it is filled / trades in a market-second, which
   side, at which price). Use the model to discover which signals matter, then
   distill them into an explicit rule. Report feature importances.
5. Test explicit rules against the wallet on VALIDATE, and keep a ledger of
   every hypothesis (family, description, validation metrics, verdict).
6. Try genuinely different families, not variations of a failed one: other
   reference feeds and latencies, order-book reconstruction from on-chain
   orders, inventory management, cross-market signals, event feeds, time-of-
   day/regime effects, sizing rules, multi-wallet coordination.
7. Look for the information source: lead-lag between the wallet's actions and
   every public signal you can get. If its actions systematically precede all
   of them, that is evidence of a private or faster source (an information
   wall); quantify it.

## Accuracy: what to measure (on VALIDATE while developing; the examiner on the holdout)

- **Selection**: does the rule pick out the wallet's trades among all
  comparable trades? For crypto Up/Down use `match_test` (stratified AUC vs
  the rotation null, recall and lift at the pre-registered threshold); for
  sports and events use a timeline-shift or market-permutation null.
- **Behaviour cloning**: (a) presence: AUC of predicting whether the wallet is
  filled / trades in each (market, time-bin); (b) side: accuracy of the side
  it takes given it acts, against the best market-only baseline (e.g. "buy the
  favourite"); (c) price: share of its fills whose price the rule predicts
  within one tick.
- **Outcome**: correlation between the rule's per-market (or per-window) PnL
  and the wallet's; the rule's held-out return under strict fills, latency >= 2
  s and (for makers) `match_slack=2`, against the wallet's own return on the
  same markets.

**High accuracy target** (my definition; all point-in-time, on the holdout):
selection AUC >= 0.80 with recall >= 50% at lift >= 3 (p < 0.01), or
presence AUC >= 0.85 without own-state features; and, where the wallet
chooses a side, side accuracy >= 80% and significantly above the market-only
baseline; and per-market PnL correlation >= 0.5. Report every metric even
when the target is not met.

## The wall (when to stop)

- Budget: at most 5 iterations of about 60 minutes of wall-clock work each
  (about 5 hours per strategy). Each iteration ends with a checkpoint.
- Diminishing returns: from iteration 3 on, stop if your best VALIDATE score
  on your primary metric improved by less than 0.01 (AUC) or 2 points
  (accuracy) over the last two iterations although each tried at least three
  genuinely new hypothesis families.
- Information wall: you show, with lead-lag evidence, that the wallet's
  decisions precede every public signal you could obtain.
- Target: you meet the high-accuracy target on VALIDATE (the examiner then
  checks the holdout).

## Engineering rules (shared machine: 4 cores, 15 GB, other agents running)

- Keep every Python process under 3 GB RSS; run one heavy process at a time;
  check `free -m` before a heavy job and wait if less than 4000 MB is
  available. Stream per market / per window; store intermediates as parquet.
- Write only inside `research/reverse_engineering/<your key>/` (code, small
  results, notes) and `.cache/re/<your key>/` (large data). Do not modify
  `polyrea/`, other folders or other agents' files; if you find a bug in
  polyrea, write it in `NOTES.md` and report it in your return. No git
  commands. Delete large intermediates you no longer need.
- Keep tool output short (summaries, not dumps) and write findings into
  `NOTES.md` as you go, so a successor can continue from it.

## Files you maintain (in `research/reverse_engineering/<your key>/`)

- `NOTES.md`: lab notebook: data gathered, hypotheses, evidence, metrics,
  decisions, open questions, what to try next.
- `state.json`: `{primary_metric, best: {rule_id, validate_metrics}, hypotheses:
  [{id, family, description, validate_metrics, verdict}], data_sources: [...],
  iterations: [{n, minutes, best_validate_score, families}]}`.
- `FINAL_RULE.md` and `code/final_rule.py`: the best rule so far, frozen (all
  parameters constants). `final_rule.py` must expose
  `evaluate(start_ts, end_ts) -> dict` that loads the data it needs for that
  period, applies the frozen rule point-in-time, and returns the metrics above
  (selection, behaviour cloning, outcome), so the examiner can run it on the
  holdout without editing it.
