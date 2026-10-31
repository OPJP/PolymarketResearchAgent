# RN1 in-play maker (0x2005d16a84ceefa912d4e380cd32e7ff827875ea): lab notebook

## Pre-registration (iteration 1, written before any VALIDATE number was computed)

- Development data: timestamps < H = 1792713600 (2026-10-23). Holdout [H, ...) is never loaded.
- **BUILD** = [1790899200, 1792108800) (2026-10-02 .. 10-15, 14 days).
  **VALIDATE** = [1792108800, 1792713600) (2026-10-16 .. 10-22, 7 days). Candidate rules are chosen on VALIDATE only.
- **Primary metric: `presence_auc`** (higher is better, fixed across iterations): ROC AUC on VALIDATE of the rule's
  score for "RN1 has >= 1 maker fill in this (market, 60-s bin)", over the universe of cells
  (market, minute) such that (i) the market belongs to an event in a seeded random sample of the events RN1 traded
  in the period (all sibling markets of the sampled event are included, traded or not), (ii) the bin lies in
  [gameStart - 2 h, gameStart + 5 h], (iii) the public tape has >= 1 taker print in the market in that bin.
  Features: strictly point-in-time (data with ts < bin start, plus listing metadata). No own-state features in the
  primary score. (Caveat: the event universe is conditioned on RN1 having traded the event; it measures market
  choice inside events and timing, not event choice.)
- Secondary metrics (reported every iteration): selection AUC among public maker fill rows (is the maker RN1?);
  side accuracy (which outcome of a binary market RN1 buys in a bin, vs "buy the favourite"/"buy the underdog");
  price: share of RN1 fills whose price the rule predicts within 1 tick; per-market PnL correlation rule vs RN1.

## Data gathered (iteration 1)

- data-api activity of RN1, one UTC day per call, 2026-10-02 .. H (21 days): `.cache/re/rn1-inplay-maker/activity/`.
  ~6.7-10k rows/day; types TRADE, REDEEM, rebates/rewards. No MERGE/SPLIT rows: complete pairs are held to
  resolution and redeemed.
- On-chain OrderFilled (V2 exchanges, topic2 = RN1) per day via publicnode (2,000-block getLogs):
  `.cache/re/rn1-inplay-maker/chain/` (VALIDATE week first, then BUILD).
- Gamma metadata of every market RN1 traded 10-02..H: `markets_<p0>_<p1>.parquet`.
- Full public tapes (taker + maker rows) of every market in 100 sampled VALIDATE events (seed 1) and 100 BUILD
  events (seed 2), window [gameStart-2h, gameStart+5h]: `.cache/re/rn1-inplay-maker/tapes/`.

## Hypotheses (see state.json for the machine-readable ledger)

## Log
