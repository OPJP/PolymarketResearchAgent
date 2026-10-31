# tommy-cs2-maker: frozen rule v3 (`tommy-v3-grid-league-upstream`; selection unchanged in iterations 4-7, live price re-frozen in iteration 7, 2026-10-31)

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

## What iteration 7 established (selection unchanged; the live price rule re-frozen to the touch)

- **The taker input is (at least partly) a shared push feed.** 26% of its take clusters are co-signed at fixed lags by
  at least one of six other wallets (null 0.3%); the other 74% it takes alone. Its takes are co-signed on the same token by P4e 0x4ebc2722
  (-50 ms, 203 takes) and 0x2005d16a (-20 ms, 49). Their offsets have event components of 7-9 ms and no platform effect
  (Kick - Twitch +2 ms [-7, +12]): one message fanned out, not separate stream readers (pre-registered verdict). Four
  slower wallets (0xf1ee4842, 0x8a80528d, 0xddb6e624 at ~+200 ms after P4e, P93 at ~+400 ms) act at the same fixed lags
  on P4e's round-win events and on the wallet's plant / turn events (each on 1-3% of P4e's takes). **The feed delivers
  the round-win kind to them; the wallet's takes avoid it** (its own bursts load on plants, P4e-alone ones on round
  wins), and it does not decline by edge: once its own followers are removed, the edge P4e left does not
  predict its presence (p 0.17), while the event kind does (reversal +0.61, same-team follow-on -0.52). None of these
  co-receivers co-signs its 67 Dota 2 takes (the three slower ones trade 6-8 of its 13 Dota tokens, never within
  400 ms of it). P4e is a pure taker in its markets (0 maker rows), so the co-signers cannot be
  reading a P4e book trace: the delivery is a push at fixed lags. At the pack's (round-win) events its ladder pulls
  barely more than in a control (17% vs 10%), so the selectivity sits at its input (handler or subscription), not at
  the take decision. The same subscriber order shows up in Dota 2 and LoL (0xf1ee4842 50-69 ms before the
  0x8a80528d / 0xddb6e624 pair), so the source is multi-title. The fan-out already existed on 10-09..10-15 with the same
  lags; the wallet joined it at its 10-16 switch.
- **The private input also reaches the maker leg between takes** (BUILD-live). 15.5% of its calldata-validated pulls
  have no public trigger anywhere in the event within 300 ms, no timer and no take. The others' mid of the pulled
  token then falls 0.22 / 0.60 / 0.65c at 2 / 10 / 30 s (p < 0.0005 against 2,000 within-book shifts). Triggered pulls show
  nothing. These pulls are not failed takes (FAK-return re-post 3.8%), and they come about 2.6 times as often as its
  takes. Pre-registered for VALIDATE-live.
- **The live "own level" label was 76% precise.** Calldata ground truth (873 linked adds) shows that single 100-share adds
  are the wallet's only half the time; multi-level bursts (0.93) and odd sizes (0.98) are reliable.
  - The iteration-6 wave-follower reading (it pulls 15 ms after the public cancel wave at the pack's events) is
    withdrawn: with the validated label it pulls at 17% of those events, against 10% in a busy-phase control.
  - The 1.5-s re-post is its own on odd sizes (11 vs 0.5 per control window).
  - The live join price barely moves (0.424 -> 0.419). The plain touch scores 0.471, so `live_price` now reports the touch
    as its primary prediction.
- **The 300-s merge loop is the maker process's clock.** The law is 300.22 s + 7.28 s per merge (residual SD 1.33 s).
  - It is absent in the taker regime; the first merge was 10-16 13:45 UTC.
  - The process runs as daily sessions, starting 08:10-09:04 UTC and ending 16:40-23:30 UTC.
  - Two other buy-only makers follow the same law without phase lock: the loop is a shared design, not a mark.
- **Exam lots carry the same market parameters** (listing projection): 1-s delay, clear-book, the sports_fees_v3 fee
  with a 0.15 rebate rate, and the same reward parameters.
- **Selection forward check.** On the 10-31 12-18 development block, v3 caught 1 of 4 traded events: three were in
  FiReSPORTS, a league it never saw. A switching rule to a league-free tier variant is pre-registered for the forward
  development blocks.
- **Price units.** Hole-filling a 4-level target ladder scores 0.48-0.50 on adds and 0.35 on filled orders. The retail
  flow cannot place either source on the broadcast chain. No public bot (poly-maker family) matches the client.

## What iteration 6 established (no rule change; `evaluate()` now also reports the outcome baseline)

Iteration 6 changed the unit to the informed EVENT (every 3c+ informed burst: it takes, it follows the public wave, or
it is hit) and tested the mechanism of its reactions:

- **It does not see the pack's events; it follows their public cancel wave** (the wave-follower part was WITHDRAWN in
  iteration 7: an artefact of the size label; see above). At its own takes its pull comes 14-17 ms
  after its signing and precedes every public cancel in 69% (event-locked). At the informed pack's takes without a
  wallet take (54 events, BUILD-live), it pulls in 48%, a median 15 ms AFTER the first public cancel (slope 1.40 on the
  wave's onset, corr 0.81, permutation p 0.008), and before it in only 14%. Its maker orders fill in the pack's
  transaction about equally often with or without that pull (39% vs 42%). So the "complete feed that chooses not to
  take" reading is rejected; the wave-follower is public (books record it) but protects little.
- **Its takes are the first informed move against the last one.** Among informed bursts it is present 29-35% after a
  burst on the other team within 120 s, 6-8% after one on the same team. Most of the apparent per-match on/off
  persistence is this composition (stratified nulls); a point-in-time model of which informed bursts it leads (pre-burst
  public features) scores VALIDATE AUC 0.698 (0.747 with burst-size features measured after the burst starts). The
  event itself stays private.
- **The outcome item needs both legs.** An activity-only "c x in-play prints" pseudo-PnL already correlates +0.51 /
  +0.37 with its per-market PnL on VALIDATE; its maker fills alone reach +0.38 / +0.34 and its taker fills alone
  +0.10 / +0.13, while its locked margin (pairs formed across the legs) reaches +0.82 / +0.75. `evaluate()` reports
  `pnl_baseline_prints_*` and the rule's partial correlation given log prints (frozen ladder: -0.053).
- **Quote structure.** Each re-quote burst touches one token only; the two tops sum to 0.92-0.99 (median 0.97, cap
  ~0.99), so it is not one (mid, spread) quote. Resting occupancy on the live book: AUC 0.635 from the gap alone,
  0.767 with slow book shape (others' size at / ahead of the level, price level); sub-second cancel features add
  nothing.
- **Exam lots** (listing projection only): 25-26% of the non-GRID events of h1 / h2 fall in leagues the v3 table has
  not seen (2-3 leagues), below the 30% switch threshold; v3 stays frozen (pre-registered), with the pack-lag variant
  as the documented fallback. Tier-3 non-GRID events are rare in those lots (4 / 6).
- **Organiser owner and stream platform.** Its led share is the same in sportsbook-run leagues (0.160) and others
  (0.168); Kick 0.176 vs Twitch 0.141 (weak).
- **A frozen live price rule is now in `evaluate()`** (`live_price`, for the future-block lots): others' best bid on
  the order's token 100 ms before signing, its own levels removed, capped at 0.99 minus its own top on the other
  token. BUILD-live check (10-31, 172 filled maker orders): within one tick 0.424 (exact 0.198) against the last trade
  0.187 on the same rows. Historical anchors stay near 0.31 (an aggressor-side-adjusted last print 0.313): 27% of its
  filled orders sit 6c or more below the last print (ladder depth), which no tape anchor can predict.
- **A hard 1.5-s re-post timer.** One cancel class is re-posted exactly 1,500-1,520 ms later (225 intervals against
  4-12 per 20-ms bin), at the cancelled price in 51%. Other bots in markets it never trades show the same timer (sizes
  30 and odd sizes), so it is a shared client behaviour, not a unique fingerprint.
- **Outcome ceiling.** Even an exact copy of its maker leg with a BUILD-chosen public residual hedge stays at 0.38 /
  0.34 on VALIDATE (hedges help VALIDATE only and lose money): the outcome item needs the taker leg.
- **Price ceiling on the live book.** Join within one tick: top changes 0.63, every own add 0.38 (ladder rule 0.40),
  filled orders 0.42 (its own previous top 0.45). No unit reaches 0.8 from public book state, with or without own
  state (BUILD-live).
- **Its maker client is a common design.** In markets it never trades (GRID events included), 100-share buy-only
  whole-cent ladders with the same 1.5-s re-post belong to six other deposit wallets, all with different owners.
- **Live split re-registered** (before any 11-01 data exist): BUILD-live = 10-31 12-18, VALIDATE-live = 11-01 06-12 and
  later development blocks, because the old VALIDATE-live (from 11-01 18:00) falls after the projected budget end.

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
| Timing (taker) | At messages of a shared CS2 push feed (>= 6 subscribers at fixed lags; P4e signs 50 ms before it), of the plant / turn kind only: typically the first informed move against the previous burst. Not decoded: on those events it signs before every public Polymarket trace, it acts on only about 16-20% of the informed 3c+ bursts in its markets, and it skips the round-win kind the other subscribers take, without an edge-based decline. | hypothesis (fan-out structure: development data, iteration 7) | Match / map books flat until it signs. Round-market takers precede it in 0.9% (controls 0.2-0.7%). Census: 80% of informed bursts wallet-absent; present 29-35% after a burst on the other team, 6-8% after one on the same team; point-in-time AUC 0.698 for which bursts it leads (pre-burst public features). Absent bursts follow round wins, its own follow bomb plants beyond wins (p 0.03). No delay-queue leak. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team that just gained in-round on plant-type events. | hypothesis | The team gains +2.6-2.9c in 10 s. T side only 54% (p 0.13). |
| Price (maker) | BUY at the other makers' best bid (join), whole cents (the in-play tick), in ladders 1c apart; one token per re-quote burst, the two tops summing to at most ~0.99. After its own take: complement top = K - L (K 0.94). | VALIDATE-only (historical anchor); live development block (join rule) | Last-print anchor within one tick: 0.305 (`price_within_tick`, VALIDATE). Live, own levels removed: re-quote top within one tick of others' best 67.4% (exact 37%). Revealed best bid from the matched-order record: 0.25-0.28 against last print 0.22-0.25 on the same rows. K - L: 57% in the first 1.04 s after a take (n 247), 6-14% later. Probe presence AUC 0.67. |
| Price (maker, live, frozen) | `live_price` (re-frozen in iteration 7, before any VALIDATE-live record): primary = the touch, i.e. the full-book best bid on the order's token at sign - 100 ms (LIVE_PRICE_PRIMARY "touch"). Secondary = the join: others' best bid with the size-labelled own levels removed, min with 0.99 - own top on the other token (LIVE_VIEW_MS 100, PAIR_CAP 0.99). | hypothesis (BUILD-live only) | 10-31 block, 172 filled maker orders: touch 0.471, join 0.424 (0.419 with the calldata-validated label), last trade 0.187. The whole 12-18 block through `evaluate()` (328 orders, early books from the shared recorder): touch 0.280, join 0.256. To be scored on VALIDATE-live (11-01 06-12 on) and by the future-block examiner. |
| Price (taker) | FAK at the stale ask + a premium that grows with the expected repricing (0-5c), kept below the post-event price; match-leg premium = map-leg premium x series sensitivity. | VALIDATE-only (premium-move relation); hypothesis as a rule | Controlled OLS: +0.87c of 10-s move per 1c of premium (p 7e-11, VALIDATE). Caps (1000 / 2000 shares) carry little of it. |
| Size | Maker: 100 shares in CS2. In 36% of events an event-wide size starts at 50-96 (median 54) and steps up monotonically to 100. 10 shares in Dota 2. Taker: odd sizes about 0.3x of the pre-event depth up to its limit; 1000 / 2000 caps early and fading. | VALIDATE-only (maker 100 and the ramp's shape); hypothesis (ramp clock, taker) | CS2 100 shares: 92.1% (BUILD), 88.3% (VALIDATE). No global (a, b) schedule (0-4% of non-100 within one share). Start size vs pre-game USD: Spearman 0.55. |
| Exit | Never sells. Pulls the complement at its takes and re-pairs it through bids posted 1.04 s later, which slower informed takers fill. Between takes it pulls the bids of the team about to lose value on private events (untriggered pulls: -0.6c others'-mid markout in 10 s). Merges complete pairs in a 300-s loop (minimum 100 shares) and holds the residual. (The iteration-6 public-wave follower is withdrawn: an artefact of the size label.) | VALIDATE-only (pairs, merge law); hypothesis (untriggered pulls, BUILD-live) | Pair cost 0.978, reproduced by the validated engine on its own orders (0.975). In bursts it misses, its complement is hit in 19-22% (-1.5 to -3.2c markouts). A public ladder 4c below the stale touch reaches 0.978 but loses $13.4k per split on its residual. |

## Target metrics on VALIDATE (`state.json` `target_metrics`)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.954 | Baseline 0.892. Recall 0.722, lift 3.30. The gain passes 0.05 with a positive lower bound at p 0.002. Fragile across days: +0.034 (10-21), +0.094 (10-22). |
| Presence AUC | 0.872 | Baseline 0.899 (fill presence per 30-s bin). The iteration-5 probe target (resting presence at swept levels): 0.669 against 0.663 for activity. |
| `price_within_tick` | 0.305 | In-play tick, last-print anchor. Live filled orders reach 0.526 at best (full-book bid). |
| `pnl_corr_pearson` / `pnl_corr_spearman` | -0.121 / -0.061 | Executable generic tape ladder (partial given log prints -0.053). Best public ladder on the validated engine: +0.024 / -0.019. Co-occurrence baseline (c x in-play prints): +0.515 / +0.357; its maker leg alone +0.38 / +0.34; its locked margin +0.82 / +0.75. |
| Side | Not applicable at market level | The maker is two-sided. The taker side follows the unobserved feed. |
| Coverage | 0.927 of fills, 0.990 of absolute PnL | Dota 2 markets fall outside the CS2 universe. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The outcome replay on tape and calldata does not track the wallet, so h1 / h2 cannot pass outcome with any
    public-data rule found so far.
  - Sweep probes exist on h1 / h2 too (on-chain), but no rule predicts them well (AUC 0.67).
- **Future sealed blocks.** `evaluate()` reads `tommy_cs2_near`, then `clob_wallets`, through
  `iter_live(..., allow_sealed=ALLOW_SEALED)`, on the server clock, and reports a taker diagnostic and the frozen live
  price rule (`live_price`). From 10-31 19:28 UTC the
  own recorders `tommy_cs2_rounds` (round markets) and `tommy_chat` (chat clock) record every block too.

## Why it works (economic mechanism)

1. **Universe** (VALIDATE-only). It trades only events without official GRID data. There, Polymarket's own sports
   feed has map scores but no round scores, so most makers price in-round swings late. The informed pack was already
   there before 10-16.
2. **A faster input from 10-16** (VALIDATE-only). Before the switch its trades came after 30-40% of the move. After it,
   its takes come before any move.
3. **Taker leg** (hypothesis on the input, live evidence on the timing).
   - A shared CS2 push feed delivers in-round events to at least six wallets at fixed lags (P4e first, the wallet
     50 ms later, the slowest ~400 ms later), before every public Polymarket trace. The wallet acts on its plant / turn
     messages only; the other subscribers also take the round-win messages.
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
  - a subscription to the real-time in-round push feed that the informed wallets share for non-GRID CS2 matches (at
    least six subscribers; not GRID, not Polymarket's sports socket, not bo3.gg; its vendor is not identified), with a
    position in its fan-out at least as early as the wallet's;
  - a CLOB client that signs FAKs and cancels within milliseconds;
  - a live-book two-sided ladder with merging;
  - about $10k of capital.
- **Conditions still hold** in the 10-31 development block: it is active in non-GRID events and still signs first.
- **A replicator with public data and a home connection** sees the event only through the cancel wave or later.
  - The wallet's own ladder is hit at about a third of the pack's events and barely pulls there (17% vs 10% in a
    control, iteration 7); a home connection 100-300 ms behind the cancel wave would be hit more often. Its maker adds
    land about 24 ms after signing and its take-time pulls 11-19 ms after its signing, so it is co-located with the CLOB.
  - Following the pack's prints lost out of sample.
  - A tape-based ladder 4c below the touch locks the same pair cost, but its unpaired residual makes it lose about 6%
    of the volume it buys.
- **Expected edge without the feed:** negative.

## Not explained yet

- **The taker input.** It sits upstream of every public Polymarket feed on the events it acts on and covers only about
  a fifth of the informed bursts (plant-type, not round wins). Iteration 7: it is a shared push feed (>= 6 subscribers at
  fixed lags); the wallet's filter on it (kind, not edge) and the feed's origin are not public. The same input reaches
  its maker leg (untriggered pulls) about 2.6 times as often as it takes.
  - Whether it comes before the broadcast (server log / scout) or from the broadcast (CV) needs an event clock.
  - Chat clock (X38): pre-registered, recording from 11-01 06:00 UTC.
  - Twitch VOD chat (X53), bo3 demo ticks (X37) and HLTV page checks (X64) need the user.
- **The maker quote.** Its resting presence is not a public function (probe AUC 0.67), and the price is anchored
  within one tick only right after its takes.
- **The outcome target.** Its residual control depends on the private leg: the maker leg alone settles at 0.38 /
  0.34 against the target 0.5, an activity-only pseudo-PnL at 0.51 / 0.37.
