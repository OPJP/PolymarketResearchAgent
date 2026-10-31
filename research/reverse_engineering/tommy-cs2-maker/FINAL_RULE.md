# tommy-cs2-maker: frozen rule v2 (`tommy-v2-grid-league-collapse`, iteration 2, 2026-10-31)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`.

- Development data: 16-22 Oct 2026 (maker regime), the taker regime 06-16..10-15 for context, and the 10-31 12-18 UTC
  live development block.
- BUILD = gameStartTime in [10-16, 10-21). VALIDATE = [10-21, 10-23).
- Code: `code/final_rule.py`, which exposes `evaluate(start_ts, end_ts, intervals=None)`. Constants are in
  `code/final_rule_v2_constants.json`. The `build` set is fitted on BUILD and gives the VALIDATE numbers below. The
  `exam` set is the same recipe refitted on all development data, and `evaluate()` uses it by default.
- Nothing here is exam-verified. The rule does not meet the high-accuracy target: price and outcome fail, and presence
  stays below its baseline.

## The rule, component by component

| Component | Rule | Tag | Evidence |
| --- | --- | --- | --- |
| Selection | Unit = CS2 event (match plus all map-winner markets). `s_lg` = 0 if `eventMetadata.gridSeriesId` is set (GRID official data), else the league's traded rate among fitted non-GRID events, shrunk (k = 3) toward the tier rate. Score = logistic(log1p pre-game taker prints, USD, distinct wallets in [gs-1h, gs) over the event's markets; `s_lg`). Trade the event iff score >= thr (20th percentile of the fitted positives' scores). | VALIDATE-only | VALIDATE: AUC 0.954 vs pre-game activity baseline 0.892, gain +0.062 [0.019, 0.115], p(gain <= 0) = 0.002 (event bootstrap, 4000). Recall 0.722 at lift 3.30. GRID events traded: 0 of 122 (16-22 Oct). |
| Timing (maker) | Quotes from game start to the end of each market, re-signing continuously. | VALIDATE-only | 99% of fills in-play. Fill presence per 30-s bin: 0.872 vs activity 0.899 (co-occurrence by construction). |
| Timing (taker) | Within about 1 s (median 0.77 s) after a **depth collapse** on one side of the public book. A collapse means the near-touch depth (within 3c of the best) falls to <= 0.5 of its max over [-1.5, -0.4] s, with reference >= 200 shares and no trade in the last 1.5 s. | VALIDATE-only (live BUILD, 31 orders); hypothesis as a frozen rule | 10-31 dev block: a collapse precedes 87% of its taker orders (random times: 3% have a >= 30% drop). It acts on 5-8% of collapses. Taker presence AUC (0.5-s bins x team): 0.943 vs prints-only 0.529. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team whose asks collapsed. | VALIDATE-only (live) | 100% of collapse-matched orders are on the collapse side. The team gains +2.6-2.9c in 10 s. |
| Price (maker) | BUY at the best bid (join), whole cents. Deeper ladder levels 1c apart are censored. | VALIDATE-only | Live: 42.7% exactly at the best bid at signing. Rebuilt touch (all makers' filled orders): 24%. Last print: 11.5% (`price_within_tick`). |
| Price (taker) | FAK at the best ask + 0-2c. | VALIDATE-only (live) | Live: limit = best ask 52%, ask + 1-2c 29%. Median fill 12% (iter 1). |
| Size | Maker 100 shares (10 or 11-99 near small inventories). Taker: variable. | VALIDATE-only (maker); hypothesis (taker) | 100-share accuracy 0.883 (VALIDATE), 0.78 (live). |
| Exit | Never sells. Merges complete pairs and holds the residual. | VALIDATE-only | Pair cost 0.9785. The residual ends on the loser 68% of the time. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.954 | Baseline 0.892. Recall 0.722, lift 3.30. The gain passes 0.05 with a positive lower bound, p 0.002. Fragile: a LightGBM pair gives +0.053, p 0.055. |
| Presence AUC | 0.872 | Baseline 0.899 (fill presence per 30-s bin). |
| Live taker presence | 0.943 | Prints-only baseline 0.529, in-sample, one development block. Not VALIDATE. |
| `price_within_tick` | 0.115 | Last-print anchor. Live join-the-bid 0.43. |
| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.121 / -0.061 | Executable generic tape ladder with strict fills. |
| Side | Not applicable at market level | The maker is two-sided. |
| Coverage | 0.927 of fills, 0.990 of absolute PnL | Dota 2 markets fall outside the universe. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The taker trigger cannot be examined there; `evaluate()` returns `live_trigger = None`.
- **Future sealed blocks** can judge the taker trigger.
  - Data: the own recorder `tommy_cs2_near`, which records every CS2 match and map-winner market and is filed into
    sealed folders by `live.Writer`.
  - `evaluate()` reads it through `iter_live(..., allow_sealed=ALLOW_SEALED)` and falls back to the shared
    `clob_wallets`.

## Why it works (economic mechanism; VALIDATE-only and live evidence, mechanism partly hypothesis)

1. **Universe.** The edge exists only in events without official (GRID) data.
   - In GRID events the makers price from the same fast data, and the pack is absent.
   - In non-GRID tier-3 events most makers price from the stream. A few fast makers, with some faster game feed,
     cancel their stale asks on the team that just gained in-round.
   - The wallet switched into exactly these events on 10-16. Until then it ran a round-trip taker strategy in GRID
     tier-1/2 events (99% of its USD), which lost after fees. The informed pack was already working the new leagues
     before the switch.
2. **Taker leg.** The wallet buys a team 0.3-1.0 s after the near-touch asks of that team disappear, and pays at most
   1-2c over the remaining best ask.
   - The cancels are a public, pushed signal (the CLOB book). The pack does the same about 0.3 s later.
   - The losers are the slow makers whose asks are still resting, and later sellers.
   - The market reprices +2.6-2.9c within 10 s and +4-5c within 60 s. The team still loses the round often enough
     that 20-23% of orders see a >= 4c adverse move within 60 s.
3. **Maker leg.** It joins the best bid with 100-share whole-cent orders on both tokens and does not pull. Its
   complement bids are the asks the pack hits after an event, which completes pairs it merges at 1 (pair cost 0.978).
   - Live (10-31): the wallet supplies 8.6% of the maker USD in the pack's taker transactions, against 1.0% in other
     takers'.
   - It never fills its own orders.
   - Locked margins plus rebates make the pairs pay.
   - A generic public-data ladder in the same markets loses 5-10%, and its per-market PnL is negatively correlated with
     the wallet's.
   - So the maker leg is profitable only together with the informed taker leg and the pairing.
4. **Paid for.** Speed in reading other makers' cancels (or a similar feed), supplying the stream-priced side, and
   rebates (maker about $2.05k, taker about $2.2k in 16-22 Oct).

## Can a normal user deploy it now

- **Needs:**
  - a CLOB websocket client that reacts to near-touch depth collapses within about 0.5 s, plus FAK orders with the 1-s
    in-play delay;
  - a two-sided 100-share ladder that joins the bid, plus automatic merging;
  - about $10k of capital;
  - non-GRID CS2 listings on Polymarket.
- **Conditions still hold.** In the 10-31 development block it is active in non-GRID events (CyberClash,
  FiReSPORTS), and the collapse pattern precedes its taker orders.
- **Competition.** At least two faster or equal operators (0x4ebc2722 at -51 ms, and a 3-wallet operator at +0.5 s)
  compete for the same stale asks, so fill rates are low (12%).
- **Expected result.** A replicator on a home connection (about 100-200 ms to the CLOB) would arrive after the pack.
  The leftover depth after the 1-s delay would mostly be gone, so the expected edge is small or negative. This is not
  measured: the trigger rule's executable return needs the future blocks.

## Not explained yet

- Which 5-8% of collapses it acts on. Descriptive so far (28 acted of 795 events):
  - deep collapses: 12.9% acted when <= 10% of the depth is left, 2% otherwise;
  - the team's best ask did not fall: it never acts when the ask fell.
- Whether its input is the book itself or a game feed it shares with the fast makers.
- The taker size rule.
- The maker ladder depth and its cancel rule.
- An executable rule whose per-market PnL tracks the wallet's. Tape replays tried: strict ladder, follow-the-pack, both
  combined, and an at-touch ladder. None is positive in both splits. The per-market PnL comes from its stale bids being
  hit while it buys the other team, and replaying that needs the live books and its queue position.
