# tommy-cs2-maker: frozen rule v3 (`tommy-v3-grid-league-upstream`; unchanged in iterations 4 and 5, 2026-10-31)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`.

- Development data: 16-22 Oct 2026 (maker regime), the taker regime 06-16..10-15 for context, and the 10-31 12-18 UTC
  live development block.
- BUILD = gameStartTime in [10-16, 10-21). VALIDATE = [10-21, 10-23).
- Code: `code/final_rule.py`, which exposes `evaluate(start_ts, end_ts, intervals=None)`. Selection constants are in
  `code/final_rule_v2_constants.json` (unchanged since v2). The `build` set is fitted on BUILD and gives the VALIDATE
  numbers below. The `exam` set is the same recipe refitted on all development data, and `evaluate()` uses it by
  default.
- Nothing here is exam-verified. The rule does not meet the high-accuracy target: price and outcome fail, and presence
  stays below its baseline (selection carries the presence-or-selection condition).

## What iteration 5 established (no rule change)

No candidate beat the frozen rule on VALIDATE. Iteration 5 changed the unit of decision (quote probes, a validated
order-level fill engine, a census of informed bursts) and found:

- **The fill engine is valid.** Replaying the wallet's own maker orders through the strict price-time engine assigns
  88-89% of its real maker shares to the same transaction (6.5% phantom), and the copy's maker-only pair cost is 0.975
  against the real 0.978. The earlier replay's 1.005 came from its quote rule.
- **A public ladder can match the pair cost but not the outcome.** Quoting 4c below the other makers' bid seen 2 s
  earlier, 5 levels, gives pair cost 0.972 / 0.978 (BUILD / VALIDATE) and +$3.4-3.8k of locked margin, but its unpaired
  residual loses $13.4k per split. Per-market PnL correlation with the wallet: VALIDATE +0.02 / -0.02.
- **Its resting ladder is not a public function.** On 29,341 uncensored probes (fully consumed levels of other takers'
  sweeps), its presence is predicted at VALIDATE AUC 0.669 from public state (activity alone 0.663; with own inventory
  0.715). Presence does not depend on the level's distance from the public touch seen 2 s earlier.
- **Its taker input covers a subset of the in-round events.** Of the informed BUY bursts that move a token 3c+ in 10 s,
  80% have no wallet take (78% when the wallet was quoting the market within 60 s). Those bursts follow round wins
  (p 3e-9). The wallet's own bursts follow bomb plants beyond round wins (p 0.03). At the event level (no wallet take in
  any market of the event within 30 s) 69% are wallet-absent. At pack-only events (live) its own-size pulls on the
  exposed side run 2.8x a busy-phase control before the pack signs and 5x after it, with no zero-fill FAK signature, and
  its ladder is hit in 37% of them. In the bursts it misses, its complement bids are hit in 19-22%, with markouts of
  -1.5c to -3.2c.
- **No leak from the delay queue.** Uninformed (retail) pending orders trigger no cancels at their arrival (8.5% against
  a 5.0% null, no spike). The fast-maker reactions are tied to informed orders only.
- **Price anchors.** On the live book with its own levels removed, its re-quote tops join the other makers' best bid
  exactly in 37% and within one tick in 67% (5,853 bursts, one development block). It reacts within about 100 ms to
  changes of the others' best at any gap, with no band threshold. K - L (K 0.94, L = the limit of its last take on the
  other token) is within one tick for 57% of the maker orders signed in the 1.04 s after a take, then decays. That is
  about 2% of orders. Own-cost anchors give 6-22%, and the best historical public anchors 25-34%.
- **Size.** In 36% of events an event-wide size starts at 50-96 shares (lower when pre-game volume is low) and steps up
  monotonically to 100. No global schedule fits it. Taker caps of 1000 / 2000 shares were a weak early sub-policy
  (settlement +2.6-3.5%, against +10.6-15.5% for odd sizes).
- **Selection labels.** 64 of the 256 BUILD skips fall in hours with no wallet order anywhere (downtime). The
  session-clean refit gives VALIDATE AUC 0.959 and recall 0.78 (frozen recipe: 0.957 / 0.75). That is within noise, so
  it is not adopted. A 3-hour session day in an exam lot would cost about 0.06 AUC.
- **Exam data.** The round-market and chat recorders now record in every block, and they file the records of
  sealed-start units into the sealed folder. The future-block examiner will have them.

## The rule, component by component

| Component | Rule | Tag | Evidence |
| --- | --- | --- | --- |
| Selection | Unit = CS2 event (match plus all map-winner markets). `s_lg` = 0 if `eventMetadata.gridSeriesId` is set (GRID official data), else the league's traded rate among fitted non-GRID events, shrunk (k = 3) toward the tier rate. Score = logistic(log1p pre-game taker prints, USD and distinct wallets in [gs-1h, gs) over the event's markets; `s_lg`). Trade the event iff score >= thr (20th percentile of the fitted positives' scores). | VALIDATE-only | VALIDATE AUC 0.954 vs pre-game activity 0.892, gain +0.062 [0.019, 0.115], p 0.002 (event bootstrap). Recall 0.722 at lift 3.30. GRID events traded: 0 of 122. Per day +0.034 / +0.094. Part of the skips are downtime; the rule cannot see it. |
| Timing (maker) | Quotes from game start to the end of each market, re-signing continuously in busy phases. At its own taker signal it cancels its complement ladder within 11-19 ms and re-quotes it about 1.04 s later, when its FAK returns. | VALIDATE-only (re-quote); live dev block (pull) | Own pull after 90-95% of live takes. Re-post hazard on the complement: 236x in [1.00, 1.14) s after its take. Its re-quote bursts co-occur symmetrically with other makers' changes (50 ms before 67%, after 69%, null 19%); no period. |
| Timing (taker) | At plant-type in-round events of a private feed. Not decoded: on those events it signs before every public Polymarket trace, but it acts on only about 20% of the informed 3c+ bursts in its markets. | hypothesis | Match / map books flat until it signs. Round-market takers precede it in 0.9% (controls 0.2-0.7%). Census: 80% of informed bursts wallet-absent; absent bursts follow round wins, its own follow bomb plants beyond wins (p 0.03). No delay-queue leak. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team that just gained in-round on plant-type events. | hypothesis | The team gains +2.6-2.9c in 10 s. T side only 54% (p 0.13). |
| Price (maker) | BUY at the other makers' best bid (join), whole cents (the in-play tick), in ladders 1c apart; re-quoted within ~100 ms of their changes. After its own take: complement top = K - L (K 0.94). | VALIDATE-only (historical anchor); live development block (join rule) | Last-print anchor within one tick: 0.305 (`price_within_tick`, VALIDATE). Live, own levels removed: re-quote top within one tick of others' best 67.4% (exact 37%). Revealed best bid from the matched-order record: 0.25-0.28 against last print 0.22-0.25 on the same rows. K - L: 57% in the first 1.04 s after a take (n 247), 6-14% later. Probe presence AUC 0.67. |
| Price (taker) | FAK at the stale ask + a premium that grows with the expected repricing (0-5c), kept below the post-event price; match-leg premium = map-leg premium x series sensitivity. | VALIDATE-only (premium-move relation); hypothesis as a rule | Controlled OLS: +0.87c of 10-s move per 1c of premium (p 7e-11, VALIDATE). Caps (1000 / 2000 shares) carry little of it. |
| Size | Maker: 100 shares in CS2. In 36% of events an event-wide size starts at 50-96 (median 54) and steps up monotonically to 100. 10 shares in Dota 2. Taker: odd sizes about 0.3x of the pre-event depth up to its limit; 1000 / 2000 caps early and fading. | VALIDATE-only (maker 100 and the ramp's shape); hypothesis (ramp clock, taker) | CS2 100 shares: 92.1% (BUILD), 88.3% (VALIDATE). No global (a, b) schedule (0-4% of non-100 within one share). Start size vs pre-game USD: Spearman 0.55. |
| Exit | Never sells. Pulls the complement at its takes and re-pairs it through bids posted 1.04 s later, which slower informed takers fill. Merges complete pairs and holds the residual. Stays exposed at the informed events it does not detect. | VALIDATE-only | Pair cost 0.978, reproduced by the validated engine on its own orders (0.975). In bursts it misses, its complement is hit in 19-22% (-1.5 to -3.2c markouts). A public ladder 4c below the stale touch reaches 0.978 but loses $13.4k per split on its residual. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.954 | Baseline 0.892. Recall 0.722, lift 3.30. The gain passes 0.05 with a positive lower bound at p 0.002. Fragile across days: +0.034 (10-21), +0.094 (10-22). |
| Presence AUC | 0.872 | Baseline 0.899 (fill presence per 30-s bin). The iteration-5 probe target (resting presence at swept levels): 0.669 against 0.663 for activity. |
| `price_within_tick` | 0.305 | In-play tick, last-print anchor. Live filled orders reach 0.526 at best (full-book bid). |
| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.121 / -0.061 | Executable generic tape ladder. Best public ladder on the validated engine: +0.024 / -0.019. |
| Side | Not applicable at market level | The maker is two-sided. The taker side follows the unobserved feed. |
| Coverage | 0.927 of fills, 0.990 of absolute PnL | Dota 2 markets fall outside the CS2 universe. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The outcome replay on tape and calldata does not track the wallet, so h1 / h2 cannot pass outcome with any
    public-data rule found so far.
  - Sweep probes exist on h1 / h2 too (on-chain), but no rule predicts them well (AUC 0.67).
- **Future sealed blocks.** `evaluate()` reads `tommy_cs2_near`, then `clob_wallets`, through
  `iter_live(..., allow_sealed=ALLOW_SEALED)`, on the server clock, and reports a diagnostic. From 10-31 19:28 UTC the
  own recorders `tommy_cs2_rounds` (round markets) and `tommy_chat` (chat clock) record every block too.

## Why it works (economic mechanism)

1. **Universe** (VALIDATE-only). It trades only events without official GRID data. There, Polymarket's own sports
   feed has map scores but no round scores, so most makers price in-round swings late. The informed pack was already
   there before 10-16.
2. **A faster input from 10-16** (VALIDATE-only). Before the switch its trades came after 30-40% of the move. After it,
   its takes come before any move.
3. **Taker leg** (hypothesis on the input, live evidence on the timing).
   - A private feed reaches it first on a subset of in-round events (plant-type), before every public Polymarket
     trace, and reaches a few fast makers within about 10 ms.
   - It buys the team that gained with FAK orders at the stale ask plus a premium that scales with the expected
     repricing.
   - The 1-s in-play delay holds the order while the fast makers cancel. It then matches against the makers who did
     not cancel. The losers are those stale makers.
4. **Pull and re-pair** (live dev block for the pull, VALIDATE-only for the re-pair). It pulls its complement within
   11-19 ms of its own signal and re-posts it 1.04 s later at K - L, so the slower informed takers buy the team back
   from it. Pairs lock at 0.96-0.99.
5. **Maker ladder** (VALIDATE-only).
   - Whole-cent bids near the touch on both tokens, merged into pairs, plus maker rebates (about $2.05k in 16-22 Oct).
   - 38-40% of its fill shares sit behind the transaction's best price level, and 15% come from orders posted inside
     the takers' delay.
   - It pays the informed pack at the events it does not detect: pack takers are 16-18% of its maker shares, at -1.5c
     to -4.5c per share.
6. **Paid for:** information speed on its event class, intermediation inside the delay window, liquidity provision to
   uninformed flow, and rebates.

## Can a normal user deploy it now

- **Needs:**
  - a real-time in-round feed for tier-3 non-GRID CS2 matches, as fast as the fastest makers (not GRID, not
    Polymarket's sports socket, not bo3.gg);
  - a CLOB client that signs FAKs and cancels within milliseconds;
  - a live-book two-sided ladder with merging;
  - about $10k of capital.
- **Conditions still hold** in the 10-31 development block: it is active in non-GRID events and still signs first.
- **A replicator with public data and a home connection** sees the event only through the cancel wave or later.
  - Following the pack's prints lost out of sample.
  - A tape-based ladder 4c below the touch locks the same pair cost, but its unpaired residual makes it lose about 6%
    of the volume it buys.
- **Expected edge without the feed:** negative.

## Not explained yet

- **The taker input.** It sits upstream of every public Polymarket feed on the events it acts on and covers only about
  a fifth of the informed bursts (plant-type, not round wins).
  - Whether it comes before the broadcast (server log / scout) or from the broadcast (CV) needs an event clock.
  - Chat clock (X38): pre-registered, recording from 11-01 06:00 UTC.
  - Twitch VOD chat (X53), bo3 demo ticks (X37) and HLTV page checks (X64) need the user.
- **The maker quote.** Its resting presence is not a public function (probe AUC 0.67), and the price is anchored
  within one tick only right after its takes.
- **The outcome target.** Its residual control depends on the private leg.
