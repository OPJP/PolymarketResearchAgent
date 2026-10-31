# tommy-cs2-maker: frozen rule v3 (`tommy-v3-grid-league-upstream`, iteration 3, 2026-10-31)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`.

- Development data: 16-22 Oct 2026 (maker regime), the taker regime 06-16..10-15 for context, and the 10-31 12-18 UTC
  live development block.
- BUILD = gameStartTime in [10-16, 10-21). VALIDATE = [10-21, 10-23).
- Code: `code/final_rule.py`, which exposes `evaluate(start_ts, end_ts, intervals=None)`. Selection constants are in
  `code/final_rule_v2_constants.json` (unchanged from v2). The `build` set is fitted on BUILD and gives the VALIDATE
  numbers below. The `exam` set is the same recipe refitted on all development data, and `evaluate()` uses it by
  default.
- Nothing here is exam-verified. The rule does not meet the high-accuracy target: price and outcome fail, and presence
  stays below its baseline.

## What changed in v3

- **The v2 taker trigger is retracted.** It said the wallet buys a team 0.3-1.0 s after other makers cancel that
  team's asks. That came from comparing the wallet's signing time (its own clock, equal to the CLOB server's within
  about 40 ms) with the laptop's receive time, which runs 0.9-1.6 s behind the server and drifts by about -130 to -180 ms per
  hour.
  - On the server clock the order is reversed. The book is flat up to the wallet's signing. The first cancels, 13-16 ms
    after it, are the wallet's own 100-share complement bids. Other makers' cancels follow at 17 / 67 / 124 ms
    (p10 / p25 / p50).
  - A frozen rule reading the receive clock would have "matched" on the examiner's run for the wrong reason.
  - `evaluate()` now reports only a server-clock diagnostic (`live_taker_diagnostic_server_clock`) and makes no
    taker-timing claim.
- `price_within_tick` uses the tick in force at signing. That is 0.01 in play until a map is decided (the first
  sub-cent resting order has a median price of 0.999). v2 used 0.001, the post-hoc Gamma field.
- Size rule: 100 shares in CS2 markets, 10 in Dota 2 markets. Every 10-share maker order is in a Dota 2 market.

## The rule, component by component

| Component | Rule | Tag | Evidence |
| --- | --- | --- | --- |
| Selection | Unit = CS2 event (match plus all map-winner markets). `s_lg` = 0 if `eventMetadata.gridSeriesId` is set (GRID official data), else the league's traded rate among fitted non-GRID events, shrunk (k = 3) toward the tier rate. Score = logistic(log1p pre-game taker prints, USD and distinct wallets in [gs-1h, gs) over the event's markets; `s_lg`). Trade the event iff score >= thr (20th percentile of the fitted positives' scores). | VALIDATE-only | VALIDATE: AUC 0.954 vs pre-game activity baseline 0.892, gain +0.062 [0.019, 0.115], p(gain <= 0) = 0.002 (event bootstrap, 4000). Recall 0.722 at lift 3.30. GRID events traded: 0 of 122. bo3.gg stars add nothing beyond popularity (0.929 vs 0.930 for activity + GRID). Every traded non-GRID event also had the informed pack in play (100% vs 50% of skipped). A lagged league pack-presence feature reaches 0.949 (p 0.0003; new leagues 0.941 vs 0.914) but is not adopted (within noise of v2). |
| Timing (maker) | Quotes from game start to the end of each market, re-signing continuously. At its own taker signal it cancels its 100-share complement bids within 13-16 ms, and re-quotes them 3-8c lower about 1.04 s later, as soon as its FAK returns. | VALIDATE-only (re-quote); live dev block (cancel) | 99% of fills in-play. Complement fills in the 2.5 s after a take come from bids signed a median +1.04 s after it; only 2-9% were signed before. Re-sign hazard on the complement: 236x in [1.00, 1.14) s after its take, 0x during the delay. Size-100 cancels on the consumed side within 40 ms: 54-61% of its takes, 5% of the pack's, 0.5% of other takers', 0.15% at random times; offsets 13 / 14 / 16 ms (p10 / p50 / p75). |
| Timing (taker) | At in-round game events seen on a private feed. Not decoded: on the server clock it signs before every public Polymarket trace. | hypothesis | 10-31 dev block, 64-69 orders: consumed-side depth 1.00 (median) up to signing; the first drops at +13-16 ms are its own cancels, other makers' at +17 / +67 / +124 ms (p10 / p25 / p50). Collapse in the 2 s before signing: 13-14%, against 1.6-2.3% at random times. No excess of book changes in any market of the event in the 100 ms before it (14.7% vs 14.4%). It is the first same-team signer in 90% of cases; the pack signs 0.2-0.5 s after the wave. Fan-out legs (map + match) are signed 1-4 ms apart. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team that just gained in-round, which is the team whose asks the fastest makers pull right after it signs. | hypothesis | 67-72% of its orders are followed within 1.1 s by a collapse of that team's asks; none on the other team. The team gains +2.6-2.9c in 10 s. |
| Price (maker) | BUY near the best bid, whole cents (the in-play tick), in ladders 1c apart. | VALIDATE-only | Last-print anchor within one tick: 0.305 (`price_within_tick`); on a match clock (taker sign + 1,040 ms) 0.353, not adopted (possible look-ahead for slow signers). Rebuilt touch: 0.396. Live, server clock, book 50 ms before signing: at the bid 29.3%, within 1c 55.4%, 1c above 14.7%. |
| Price (taker) | FAK at the pre-event best ask + 0-5c. | live dev block (server clock); hypothesis as a rule | Book 50 ms before signing, 69 orders: limit = ask 26%, +1c 22%, +2-3c 29%, +4-5c 21% (98.6% at or above the ask). Calldata: limit = matched maker price + 0c in 52% of fills. |
| Size | Maker 100 shares in CS2 (10-99 near small inventories), 10 in Dota 2. Taker: about 0.3x of the pre-event depth up to its limit; drifting. | VALIDATE-only (maker); hypothesis (taker) | CS2 100 shares: 89.4% (16-22 Oct), 78.4% (dev block). Dota 2: 100% are 10 shares. Taker size / pre-event depth median 0.31; the wave removes 82% of that depth, and it fills 98% of what is left. 1000/2000-share caps: 14.4% on VALIDATE, 0% on 10-31. |
| Exit | Never sells. At its takes it pulls the complement ladder at once and re-pairs through complement bids, posted 1.04 s later, that slower informed takers fill (pair cost 0.96-0.99). Merges complete pairs and holds the residual. | VALIDATE-only | Pair cost overall 0.9785. The residual ends on the loser 68% of the time. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.954 | Baseline 0.892. Recall 0.722, lift 3.30. The gain passes 0.05 with a positive lower bound, p 0.002 (just under the 0.0025 alpha). Fragile across days: +0.034 (10-21) and +0.094 (10-22). |
| Presence AUC | 0.872 | Baseline 0.899 (fill presence per 30-s bin). |
| `price_within_tick` | 0.305 | In-play tick, last-print anchor (exact 0.001 match: 0.115). |
| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.121 / -0.061 | Executable generic tape ladder with strict fills. |
| Side | Not applicable at market level | The maker is two-sided. The taker side follows the unobserved feed. |
| Coverage | 0.927 of fills, 0.990 of absolute PnL | Dota 2 markets fall outside the CS2 universe. |
| Live taker diagnostic (not a target) | 61 orders | Server clock, 10-31 dev block: collapse before signing 14.8% vs random 2.1%; after signing 72.1%. Match minus sign: p50 1,040 ms. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The taker decision cannot be judged from public data on any lot, because its input is upstream of every
    Polymarket feed.
- **Future sealed blocks.** `evaluate()` reads `tommy_cs2_near`, then `clob_wallets`, through
  `iter_live(..., allow_sealed=ALLOW_SEALED)`, on the server clock. It reports the diagnostic above.

## Why it works (economic mechanism)

1. **Universe** (VALIDATE-only). It trades only events without official GRID data. In those events Polymarket's own
   sports feed carries map scores but no round scores, so most makers price in-round swings late (from the stream or
   the tape).
   - On 10-16 it left GRID events entirely, where it had been a losing round-trip taker.
   - The informed pack was already in the new leagues. Every non-GRID event it trades also has the pack in play
     (100%, against 50% of the ones it skips), so it trades a subset of the events its feed peers cover.
2. **Taker leg** (hypothesis on the input, live evidence on the timing).
   - A private in-round feed reaches the wallet before anyone else who moves the Polymarket book. It buys the team
     that gained with FAK orders, in the map and the match market within milliseconds.
   - The 1-s in-play delay holds its order. Meanwhile the fastest other makers cancel (+17 / +67 / +124 ms, p10 / p25 /
     p50), and its order matches at +1.04 s against the makers who did not.
   - The pattern fits buying the team that just won a duel. In its matches the opening-kill team wins 72% of rounds,
     against its 64-67% next-jump hit rate. This is a consistency check, not a test.
   - The losers are the stale makers. The market reprices +2.6-2.9c within 10 s and +4-5c within 60 s, but 20-23% of
     orders see a >= 4c adverse move within 60 s (in-round information, not known round results).
3. **Pull and re-pair** (live dev block for the pull; VALIDATE-only, descriptive, for the re-pair).
   - At the same signal it cancels its own 100-share complement bids within 13-16 ms. Those bids are asks on the team
     that just gained, and the slower informed takers would otherwise pick them off. Cancels are not delayed.
   - As soon as its FAK returns (+1.04 s), it posts the complement bids again, 3-8c lower. The slower informed takers'
     delayed FAKs fill them (55-67% of those fills come from the pack).
   - It thus sells part of the position back at the new price and locks pairs at 0.96-0.99.
   - The first cancels of the public "wave" after its signing are its own. Other makers' cancels follow at
     17 / 67 / 124 ms (p10 / p25 / p50).
4. **Maker ladder** (VALIDATE-only). Whole-cent bids near the touch on both tokens, merged into pairs (overall pair cost
   0.978), plus maker rebates (about $2.05k in 16-22 Oct). A generic public-data ladder in the same markets loses 5-10%.
   The ladder pays only together with the informed legs and the pairing.
5. **Paid for:** information speed (a feed faster than every Polymarket participant who moves the book), intermediation
   between stale makers and slower informed takers inside the delay window, and rebates.

## Can a normal user deploy it now

- **Needs:** a real-time in-round data feed for tier-3 non-GRID CS2 matches, faster than the fastest Polymarket makers.
  It is not identified: not GRID (absent from these events), not Polymarket's sports socket (map scores only), not
  bo3.gg (no live coverage). It also needs a CLOB client that signs FAKs within tens of milliseconds of the feed, a
  two-sided ladder with merging, and about $10k of capital.
- **Conditions still hold** in the 10-31 development block: it is active in non-GRID events (CyberClash,
  FiReSPORTS) and still signs before the cancel waves.
- **A replicator with public data and a home connection** would see the event only through the cancel wave (the
  wallet's own cancels at +13-16 ms, other makers' from +17 ms) or later. Following the wave, it would arrive with the pack, 0.2-0.5 s behind, after most of the
  stale depth has gone. Following the pack's prints already lost out of sample (iteration 1).
- **Expected edge without the feed:** about zero or negative. The re-pair leg (selling to the pack inside the delay
  window) might be partly reproducible from the wave. That is not measured yet.

## Not explained yet

- The taker input. Every public source obtained comes after its signing: the book, trades, the sports socket and bo3.
  The HLTV scorebot is behind a Cloudflare challenge, SX Bet odds need a key, and PandaScore needs a token.
  Candidates are a betting-data provider's live feed or server logs. Testing them needs a PandaScore token or video
  consent from the user.
- Selection inside non-GRID events beyond popularity and league (per-match coverage of that feed?).
- The maker price beyond the touch. On the server clock, 29% of its orders are at the bid. Its full ladder (own
  recorder) has its top at the ask - 1c in 48% of bursts, and 32% of bursts sit 3-4c below the bid, which is
  unexplained.
- The outcome target.
