# tommy-cs2-maker: frozen rule v3 (`tommy-v3-grid-league-upstream`; unchanged in iteration 4, 2026-10-31)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`.

- Development data: 16-22 Oct 2026 (maker regime), the taker regime 06-16..10-15 for context, and the 10-31 12-18 UTC
  live development block.
- BUILD = gameStartTime in [10-16, 10-21). VALIDATE = [10-21, 10-23).
- Code: `code/final_rule.py`, which exposes `evaluate(start_ts, end_ts, intervals=None)`. Selection constants are in
  `code/final_rule_v2_constants.json` (unchanged since v2). The `build` set is fitted on BUILD and gives the VALIDATE
  numbers below. The `exam` set is the same recipe refitted on all development data, and `evaluate()` uses it by
  default.
- Nothing here is exam-verified. The rule does not meet the high-accuracy target: price and outcome fail, and presence
  stays below its baseline.

## What iteration 4 established (no rule change)

The frozen rule is unchanged because no candidate beat it on VALIDATE. Iteration 4 tested the panel's proposals and
narrowed what any rule can do:

- **Outcome is not reachable from tape and calldata.** A queue-aware replay of a public quote (join the other
  makers' observed best bids, pair-sum cap, strict price-time priority, on the full matched-order record) gets the
  wallet's volume where the wallet gets it (paired volume Spearman 0.79 BUILD / 0.91 VALIDATE). But it pays a pair
  cost of 1.005 against the wallet's 0.978 and loses 4-5%. Its per-market PnL does not correlate with the wallet's
  (VALIDATE -0.04 / -0.04). Inserting the wallet's own pulls changes nothing. The margin needs the live book.
- **Price.** On the live book (171 filled CS2 maker orders, own levels subtracted), the best anchor is the full-book
  best bid 5 ms before signing: 52.6% within one tick. Others' best bid gives 45.6%, and the panel's pair-sum-cap rule
  24-46%. 41.5% of its filled orders sit above others' best bid, because the orders that improve the bid are the ones
  that fill (fill selection).
- **The taker's limit is a private valuation.** The premium over the stale ask predicts the size of the repricing
  (Spearman 0.26 at 10 s, CI [0.17, 0.35] on VALIDATE); other takers' premiums do not (0.04). The match-leg premium
  is the map-leg premium times the series sensitivity (ratios 0.58 / 0.50 against 0.5). The price ends 2-5c above its
  limit, so the limit keeps a margin below the post-event value.
- **Who else is fast.** Its own pull follows 90% of its takes at +11 / +14 / +19 ms. In 17-20% of its takes another
  maker cancels between its signing and its pull, against a 0.37% base rate. Some makers therefore act on the same
  event within about 10 ms of it.
  - One of them is named: 0x51dbdd2b19427dc8e88bb15a4046a38d8427f9b3, a POLY_PROXY maker (signer 0xdecd4b4c...).
  - It traded 69% of the wallet's CS2 events, against 12% of the non-GRID events the wallet skipped, plus all 3 of
    its Dota 2 events.
  - It cancels +9-13 ms after the wallet signs in some takes, and never before the wallet.
  - It re-quotes both tokens within 0.1-0.5 s of the wallet's takes.
  - This makes it a candidate second subscriber of the same source.
- **Round-market takers.** They only follow it: 0.9% sign in the second before its takes, 6.7% in the 500 ms after.
- **The 10-16 switch brought a faster input.** In the taker regime about 30-40% of each move came before its trades,
  in GRID and non-GRID events alike. In the maker regime nothing moves before its takes.
- **Event type.** It is not the opening kill. Per map, its take shares follow round wins and bomb plants (p 0.06), but
  it buys the T side only 54% of the time (p 0.13). The pack P4e buys the CT side 59% of the time (p 6e-10).

## The rule, component by component

| Component | Rule | Tag | Evidence |
| --- | --- | --- | --- |
| Selection | Unit = CS2 event (match plus all map-winner markets). `s_lg` = 0 if `eventMetadata.gridSeriesId` is set (GRID official data), else the league's traded rate among fitted non-GRID events, shrunk (k = 3) toward the tier rate. Score = logistic(log1p pre-game taker prints, USD and distinct wallets in [gs-1h, gs) over the event's markets; `s_lg`). Trade the event iff score >= thr (20th percentile of the fitted positives' scores). | VALIDATE-only | VALIDATE AUC 0.954 vs pre-game activity 0.892, gain +0.062 [0.019, 0.115], p 0.002 (event bootstrap). Recall 0.722 at lift 3.30. GRID events traded: 0 of 122. An organiser-level official-data-holder flag is falsified: PGL has an exclusive Oddin.gg data deal, yet it traded 9 of 13 PGL qualifier events. |
| Timing (maker) | Quotes from game start to the end of each market, re-signing continuously. At its own taker signal it cancels its complement ladder (100 shares, or an inventory-scaled 54 / 58 / 68) within 11-19 ms, and re-quotes it about 1.04 s later, when its FAK returns. | VALIDATE-only (re-quote); live dev block (pull) | Own pull after 89.7% of 39 live takes (p10 / p50 / p90 = 11 / 14 / 19 ms). Re-post hazard on the complement: 236x in [1.00, 1.14) s after its take. |
| Timing (taker) | At in-round game events of a private feed. Not decoded: on the server clock it signs before every public Polymarket trace. | hypothesis | Match / map books flat until it signs. Round-market takers precede it in 0.9% vs 0.2-0.7% at control times, and follow it in 6.7% vs 0.2-0.8%. Another maker cancels inside its 11-14 ms pre-pull window in 20% of takes (base rate 0.37%). Zero-fill attempts add about 20-35% to the visible takes. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team that just gained in-round. | hypothesis | The team gains +2.6-2.9c in 10 s. Per-map shares follow round wins and bomb plants, not opening kills. T side 54% (p 0.13). |
| Price (maker) | BUY near the best bid, whole cents (the in-play tick), in ladders 1c apart. | VALIDATE-only | Last-print anchor within one tick: 0.305 (`price_within_tick`, VALIDATE). Live filled orders: full-book bid 0.526, others' bid 0.456, pair-cap rules 0.24-0.46. |
| Price (taker) | FAK at the stale ask + a premium that grows with the expected repricing (0-5c), kept below the post-event price; match-leg premium = map-leg premium x series sensitivity. | VALIDATE-only (premium-move relation); hypothesis as a rule | Spearman(premium, 10-s move) 0.26 (BUILD and VALIDATE), others 0.04-0.05. Controlled OLS: +0.87c of 10-s move per 1c of premium (p 7e-11, VALIDATE). A favourable >= 4c move within 60 s follows 53% of takes at premium 0 and 79% at 3+c. 60-s move at premium 0 / 3 / 5+c: +2.2 / +5.5 / +9.6c (VALIDATE). Price 2-5c above the limit at 60-120 s. Size grows weakly with the premium (Spearman 0.14-0.22). |
| Size | Maker 100 shares in CS2 (54 / 58 / 68 near small inventories), 10 in Dota 2. Taker: about 0.3x of the pre-event depth up to its limit; drifting. | VALIDATE-only (maker); hypothesis (taker) | CS2 100 shares: 89.4% (16-22 Oct), 78.4% (dev block). Dota 2: 100% are 10 shares. |
| Exit | Never sells. Pulls the complement at its takes and re-pairs it through bids posted 1.04 s later, which slower informed takers fill. Merges complete pairs and holds the residual. | VALIDATE-only | Pair cost overall 0.9785. The residual ends on the loser 68% of the time. A public copy of the ladder pays 1.005 per pair. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.954 | Baseline 0.892. Recall 0.722, lift 3.30. The gain passes 0.05 with a positive lower bound at p 0.002. Fragile across days: +0.034 (10-21), +0.094 (10-22). |
| Presence AUC | 0.872 | Baseline 0.899 (fill presence per 30-s bin). Unchanged for two iterations, so iteration 5 must pivot. |
| `price_within_tick` | 0.305 | In-play tick, last-print anchor. Live filled orders reach 0.526 at best (full-book bid). |
| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.121 / -0.061 | Executable generic tape ladder. The iteration-4 queue-aware replay gives -0.04 / -0.04. |
| Side | Not applicable at market level | The maker is two-sided. The taker side follows the unobserved feed. |
| Coverage | 0.927 of fills, 0.990 of absolute PnL | Dota 2 markets fall outside the CS2 universe. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The outcome replay on tape and calldata does not track the wallet (iteration 4), so h1 / h2 cannot pass outcome
    with any public-data rule found so far.
  - The taker decision cannot be judged there from public data. bo3 demos (X37, needs the user's consent) would be
    its only possible label.
- **Future sealed blocks.** `evaluate()` reads `tommy_cs2_near`, then `clob_wallets`, through
  `iter_live(..., allow_sealed=ALLOW_SEALED)`, on the server clock, and reports a diagnostic. The own recorders
  `tommy_cs2_rounds` and `tommy_chat` record development blocks only.

## Why it works (economic mechanism)

1. **Universe** (VALIDATE-only). It trades only events without official GRID data. There, Polymarket's own sports
   feed has map scores but no round scores, so most makers price in-round swings late. The informed pack was already
   there before 10-16.
2. **A faster input from 10-16** (VALIDATE-only). Before the switch its trades came after 30-40% of the move. After it,
   its takes come before any move.
3. **Taker leg** (hypothesis on the input, live evidence on the timing).
   - A private in-round feed reaches it before every public Polymarket trace, and reaches a few fast makers within
     about 10 ms (20% of its takes).
   - It buys the team that gained with FAK orders in the map and match markets, at the stale ask plus a premium that
     scales with the expected repricing.
   - The 1-s in-play delay holds the order while the fast makers cancel. It then matches against the makers who did
     not cancel.
   - The losers are those stale makers. The market reprices +2.6-2.9c within 10 s.
4. **Pull and re-pair** (live dev block for the pull, VALIDATE-only for the re-pair).
   - At its own signal it pulls its complement bids (asks on the team that gained) within 11-19 ms.
   - It re-posts them 1.04 s later, so the slower informed takers buy that team back from it. Pairs lock at
     0.96-0.99.
5. **Maker ladder** (VALIDATE-only).
   - Whole-cent bids near the touch on both tokens, merged into pairs, plus maker rebates (about $2.05k in 16-22 Oct).
   - The same ladder run from the tape with queue priority gets the same volume but loses 4-5%. The ladder pays only
     with a live view of the book and its private pulls.
6. **Paid for:** information speed (an input at least as fast as the fastest Polymarket makers), intermediation inside
   the delay window, and rebates.

## Can a normal user deploy it now

- **Needs:**
  - a real-time in-round feed for tier-3 non-GRID CS2 matches, as fast as the fastest makers (not GRID, not
    Polymarket's sports socket, not bo3.gg);
  - a CLOB client that signs FAKs and cancels within milliseconds;
  - a live-book two-sided ladder with merging;
  - about $10k of capital.
- **Conditions still hold** in the 10-31 development block: it is active in non-GRID events and still signs first.
- **A replicator with public data and a home connection** sees the event only through the cancel wave or later.
  Following the pack's prints lost out of sample. The tape-based ladder loses 4-5% even with queue priority.
- **Expected edge without the feed:** negative.

## Not explained yet

- **The taker input.** Its source sits upstream of every public Polymarket feed and is shared with a few fast makers.
  Whether it comes before the broadcast (server log / scout) or from the broadcast (CV) needs an event clock: bo3 demo
  ticks (X37, the user's consent) or the Twitch chat clock (X38, recording from 11-01 06:00 UTC).
- **The event type.** Not the opening kill; round wins and bomb plants are associated per map, but there is no strong
  T-side preference.
- **The maker price beyond the touch** (0.53 at best) and **the outcome target** (needs a live-book replay on future
  blocks).
