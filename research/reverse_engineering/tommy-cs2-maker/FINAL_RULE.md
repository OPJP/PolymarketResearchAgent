# tommy-cs2-maker: frozen rule v6 (`tommy-v6-groupP-bidside-outcome`; v5 with a bid-side anchored outcome replay, iteration 15, 2026-11-01)

Wallet TommyLeePeeca `0x0063b23cdeb43166d6c0246c05baaf9b9bd72dd2`.

- Development data: 16-22 Oct 2026 (maker regime), the taker regime 06-16..10-15 for context, and the 10-31 12-18 UTC
  live development block.
- BUILD = gameStartTime in [10-16, 10-21). VALIDATE = [10-21, 10-23).
- Code: `code/final_rule.py`, which exposes `evaluate(start_ts, end_ts, intervals=None)`. CS2 selection constants are in
  `code/final_rule_v2_constants.json` (unchanged since v2); the Dota 2 league table (same recipe, same periods) is in
  `code/final_rule_v4_dota.json`; the v5 group-P members and coefficients are in `code/final_rule_v5_groupP.json`. The `build` set is fitted on BUILD and gives the VALIDATE numbers below. The `exam`
  set is the same recipe refitted on all development data before H, and `evaluate()` uses it by default.
- Nothing here is exam-verified. The rule does not meet the high-accuracy target: price and outcome fail, and presence
  stays below its baseline (selection carries the presence-or-selection condition; scope passes).
- Iteration 10 changed no rule component (v5 stays frozen); it added the decoded exit band, the pre-registered treatment
  of the exam lots' PGL Masters stratum, and quantified why price and outcome are out of reach of public data.
- Iteration 11 changed no rule component either. It closed the second-venue route (SX Bet on chain), showed that
  no point-in-time own-state anchor beats the last print, that a fresh public touch is not the wallet's value, that
  even a rule knowing its value caps at about 0.71-0.75 per order, and that the outcome item breaks at any public
  lag of the take because its own take empties the stale remainder.
- Iteration 12 changed no rule component. It took the wallet's value V itself as the target (hidden-Markov valuation
  fits, the ladder under V, the loop as the decision unit, natural experiments) and corrected one wall number (the
  price cap with V known).
- Iteration 13 changed no rule component. It found the operator's other accounts (one of them ran this strategy before
  the wallet did), replicated the selection rule out of sample on that account, rejected three bookmakers' Dota lines
  as the value, and measured the value's in-round information against bo3 round winners.
- Iteration 14 changed no rule component. It ran the 11-01 brief's hidden-dimension pass (dimension inventory,
  out-of-fold residual shape, cross-event synchrony, a pre-registered event-state indicator screen confirmed on
  VALIDATE) and measured the price item's lag tolerance, an own-state transport rule, a phase-gated public ladder, the
  value's path on the feed's own clock, and the operator's sports quoting and further accounts.
- Iteration 16 changed no rule component. It moved the R-vs-K reading toward round results (clock-free per-map counts,
  a match-time print clock), split the price item's private part by the clock of the visible message, re-attributed
  0x10d79cc7 to the operator by the shadow fingerprint, found that the fan-out lost P4e after T0, and verified that a
  vendor sells the historical book for the development period (key needed).
- Iteration 15 changed only the outcome component (v6): the executable replay in `evaluate()` now quotes one BUY level
  per token at the others' bid on that token (the latest wallet-free print that consumed bids on it, usable 2 s after
  its block) under a 0.99 pair cap, instead of anchoring both tokens on the last print. Selection, presence, price and
  size are v5's. It also re-decided which accounts are the operator's, tested the wallet's exit policy as the outcome
  carrier, and found the first evidence that the private value prices in-round events rather than round results only.

## What iteration 16 established (no rule change; v6 stays frozen)

- **R vs K now leans R** (hypothesis). Clock-free per-map counts (94 maps of 16-22 Oct) show no kills-per-round or
  plants-per-round effect on its value changes at fixed rounds, and its large moves scale with the map's rounds
  (coefficient 1.34), with the count of rounds rather than with the map's duration when both are in the model; the
  one-move-per-kill form is excluded. Re-stamping the public tape at the CLOB match (instead of
  the block) leaves the print clock as weak as before (1.33x vs 1.30x over a reversed sequence) and turns the
  decided-early contrast to -0.14 [-0.45, +0.09], which no longer excludes round-end messages. So, on the filled record, the private input is
  mostly round results delivered early, with a small in-round part not excluded. On the one live block the filled
  record is not a jump-timed sample of its quote moves (6.0% of filled vs 7.4% of unfilled value changes sit within
  10 s of a 2c print jump), so censoring does not explain the pattern there; the uncensored 16-22 Oct ladder (Telonex
  files) would settle it with power.
- **Where the private part of the price item sits.** Of its value changes, 82-85% have no visible informed take in the
  3 s before (dark), 4-5% come ahead of or inside the informed takers' 1-s delay, and 5-6% come after the informed trade
  has matched (public on the market socket). About 90% of the decisions therefore carry V before any public trade.
- **Operator accounts.** The operator's shadow accounts sign 0-5 ms behind 0x10d79cc7 at the same price in 16-22 Oct
  (10 vs 2 pairs at 5-50 ms; every other maker 0), so 0x10d79cc7 (20-share ladders in GRID and LoL events) is the
  operator's, as a separate quoting loop; 0xd2bb9459 is not attributed. Its GRID quotes are not the public print plus an
  offset (at most 0.147 within one tick), so that arm runs on another input (GRID's official data is the candidate).
  "Never GRID" is therefore the boundary of the wallet's loop, not of the operator.
- **After T0 the fan-out lost its first signer.** P4e has no take on the operator's four development-block units; the
  trio and RN1 still take with unchanged internal lags. The sibling 0x7d67f01d fails a pre-registered same-feed gate
  there (lag spread, markout +0.98c against the +1c bar), so the recorded Thunderpick / Valve / Kick tests could not be
  read on it (no Thunderpick record of any operator unit in any case). Exam risk is small for selection: the frozen v5
  with gp72 recomputed without P4e scores AUC 0.972, recall 0.667, lift 3.33 on VALIDATE (0.970 / 0.744 / 3.155 with
  it). The wallet's own information edge persists on 10-31 (new-high markout +1.89c at 60 s vs +2.5c in 16-22 Oct).
- **The historical book exists.** Telonex's key-free availability endpoint lists full book snapshots, quotes and
  on-chain fills for the wallet's 16-22 Oct CS2 markets; downloads need an API key (the user's account).
- **Closed without a rule change:** an own-inventory price skew (real, 1-2c when long, +0.006 on VALIDATE), small net
  caps on the public ladder (all negative on VALIDATE), a pre-game vendor fingerprint (none), and `clob_wallets` as an
  input (subscribed only after the wallet's first trade in 8 of 9 markets: never a presence or selection input).

## What iteration 15 established (v6: the outcome replay; nothing else changed)

- **Outcome component replaced** (VALIDATE-only). `_replay_v6`: one level per token at floor(others' bid on that
  token), pair cap 0.99, band [0.05, 0.95], 100 shares (10 in Dota) refilled every 10 s, strict trade-through fills on the
  data-api taker tape. It was the BUILD choice among the pre-registered tape-engine variants and beat the frozen replay
  on VALIDATE in both coefficients: per-market Pearson / Spearman **0.197 / 0.027** (v5 replay -0.131 / -0.081; prints
  baseline 0.329 / 0.289). The gain removes the old replay's ask-side quotes; it is not a decode of the outcome.
- **The wallet's own exit policy does not carry the outcome** (X218). A five-slot public ladder with the measured net
  cap (about 600 CS2 shares) and the 200-600 taper, in the validated calldata engine: BUILD chooses no cap (0.067 /
  0.275), so VALIDATE stays at 0.315 / 0.238; capped variants reach 0.41-0.48 Pearson on VALIDATE but 0.11-0.21
  Spearman and negative BUILD Pearson.
- **Which accounts are the operator's.** Cross-market 0-5 ms co-signing with the wallet (the one-process test) confirms
  0x7d67f01d (4.4x) and refutes 0xd2bb9459, 0x10d79cc7, 0x68915897 and 0x5d40576b (0-1 pairs). Their earlier
  same-market co-signing is what co-subscribers of one feed produce. No attributed account quotes GRID events, so
  "never GRID" stays the operator's boundary. In 16-22 Oct 20 of 97 non-GRID operator events went to 0x7d67f01d only;
  that routing is too sparse to fit.
- **R vs K: not decided** (hypothesis). For K: on the print-anchored round clock the share of its value's move before
  the print's jump is the same in decided-early rounds (defuse after a wipe, bomb with CTs saving) as in elimination
  rounds (0.682 vs 0.680; R predicted 0.40 or less), and its dark re-pricings stay informed after removing censoring
  artefacts and followers (+1.8-1.9c at 60 s). For R: the busy 2-20 s after a round end follow the round just won (not
  the new round's buy), and with the previous round's winner controlled its mid-round moves point to the current
  winner only 0.53-0.55. Reading: its value moves at feed messages that are mostly round results, before and around
  the market's reaction, with a small in-round part. PandaScore's Low Latency Feed remains the candidate vendor (the
  API answers 403 'Token is missing'; a token is the user's to create).
- **Latency yardstick.** Its message-locked re-pricings come a median 1.1 s after the first visible co-receiver's take;
  a source arriving 0.25 s after the message would precede 85% of them.
- **New reported metric.** `price_within_tick_at_fill_m1c` = 0.496 on VALIDATE (the fill unit, last wallet-free print
  before the fill block minus 1c); the target metric stays the order unit at signing (0.322). Generic makers reach
  0.605 at the fill.

## What iteration 14 established (no rule change)

- **The residual's shape (E2, out of fold on BUILD; VALIDATE-only evidence for the rule).** Selection is almost fully
  explained (OOF league AUC 0.939, no traded event missed). Timing inside traded markets is co-occurrence (OOF 0.910
  for the rule vs 0.9105 for activity alone). The price item carries the unexplained part: 68% of orders are off the
  last print, piling up at round ends. No cross-event synchrony of the misses (E7: ratio 0.63-0.99, p >= 0.54), so no
  shared outage, headline or cross-market driver.
- **The wallet acts before the public tape and just after the push feed's visible subscribers (E3-1, pre-registered;
  13 of 18 rows confirmed on VALIDATE at Holm alpha 0.01; hypothesis-level reading).** Its re-pricing decisions follow
  informed takers' signatures by +0.4-1.5 s, sign-concordant, and precede public print jumps, other-book jumps and the
  first print after a silence by 2.5-5 s, in the same direction. Only 12-18% of its re-pricings have a visible
  informed take in the 3 s before them (null about 3%); the rest sit at messages no wallet-free take prints.
- **The price item tolerates no input lag (X201; BUILD-live).** Through the frozen ladder machine, its own value lagged
  by 0.25 s keeps 0.355 of the set unit (4 s: 0.293; oracle 0.875); the orders that fill are 90% V-change bursts, which
  score 0.20-0.23 at any lag. A delayed public in-play state (stream, Valve 4-s Dota snapshots, HLTV) can name the
  feed's class but cannot carry the price item.
- **Own state does not carry it either (X198).** The freshest own level transported over the complement (K 0.97) and
  the series map (map to match slope 0.46) gives 0.44 within one tick on VALIDATE with its own knowledge at signing,
  and 0.26-0.27 with only what is public at block time (the last print: 0.305-0.322).
- **On the feed's clock its value steps at the message (X189 / X195 first pass).** Around 2,111 informed clusters
  its value moves 42-57% of its 60-s move within (-1, +3] s, with no private ramp before the message (beyond the
  print's own pre-trend), and the print follows 2-5 s later on those messages. It also moves (+1.0c) at clusters that
  favour the round's eventual loser, but the print-inferred clock cannot separate "round results" from "in-round
  events".
- **Round results or in-round events: still open (hypothesis, first pass).** On a round clock built from bo3
  durations snapped to the feed's winner-direction informed clusters (weak: 1.39x the snaps of a reversed winner
  sequence; 61 rounds), its winner-signed move sits at the round-end message (+2.84c) with none mid-round (-0.47c). With
  single informed takes as anchors (1.34x; 141 rounds) it also moves mid-round (+2.11c; VALIDATE +3.02c, mid-round
  AUC 0.67 vs the print's 0.61). On the print's own clock it has moved most of the way before the print reacts (the
  10-45 s lead). No public anchor set gives a reliable round clock, so "round results seen early" vs "in-round events"
  is not decided; kill / round-end ticks (demos, consent) would decide it.
- **Version history (VALIDATE-only).** The operator's esports maker quoted two-sided around the public print in
  July-August (within one tick 0.43, bid -1c / ask +1c, no merges) and switched, after a pause from 09-03 to 09-16, to
  the BUY-only merge design with the private value on 09-17 (the second account from 09-21).
- **A phase-gated public ladder does not carry the outcome item (X202).** Quoting a five-slot public ladder only after
  a point-in-time informed-take clock: VALIDATE per-market Pearson / Spearman with the wallet 0.253 / 0.046 (return
  +0.5%); no variant reaches 0.5.
- **The operator.** At least six accounts on one process: two more BUY-only whole-cent CS2 makers (0x10d79cc7,
  0xd2bb9459) co-sign with the operator's accounts at 0-5 ms (12.6x / 9.0x per ms) and share the owners' EIP-7702
  delegate (which 19 of 499 deposit-wallet owners use, so the delegate alone is not proof). Its sports account
  (0x52661b8e, September) is a BUY taker (1,148 takes, 152 single-slot makers bidding above the print) whose MLB takes
  show no fixed-lag reaction to official play ends (statsapi; p_link 0.52-0.90): the push-feed maker is an esports
  product, which narrows the vendor search.

## What iteration 13 established (no rule change)

- **One operator, at least four accounts, one signing process (VALIDATE-only; on-chain).** A census of every maker in
  the wallet's 16-22 Oct markets for orders signed 0-5 ms after a same-token wallet order (before the wallet's own order
  can be on the book) finds three 5-share accounts at 8-29x the [5, 50)-ms rate: 0x52661b8e (profile name
  "TommyLeePeeecan"), 0x67119033 (its owner key 0x116342d6 received the wallet owner's only outgoing $2,000) and
  0x7d67f01d ("BACKTESTEOCARAIO1"). All come from the same deposit-wallet factory; the owners of two of them are EIP-7702
  accounts with the wallet owner's delegate. Their 5-share orders sit in the wallet's five ladder slots (98% of
  co-bursts inside V - 4c): the first historical confirmation of the ladder machine.
- **The 10-16 "switch" is an account migration (VALIDATE-only).** 0x7d67f01d made the non-GRID CS2 / Dota (and LoL)
  markets with the wallet's design from at least 09-21: BUY-only plus merges, 100 shares with the 50-79 ramp, whole
  cents, the [0.05, 0.95] band, and taker FAKs with 1000 / 2000 caps signed +34 ms (October) / +65 ms (late September)
  after P4e. Its October maker prices relate to the public print exactly as the wallet's do (0.298 within one tick of the
  last print against the wallet's 0.305-0.309, offset -1c; September -3c). In 10-01..10-15 it traded 133 CS2 events,
  all non-GRID, while the wallet was a GRID taker; from 10-16 the wallet makes and 0x7d67f01d winds down. No Polymarket
  change was needed for the switch (C4b). Bot versions on that account: in June its maker (7-12 shares, whole cents,
  band) quoted at the stale public print (0.455 within one tick, offset 0c); by late September the value was private
  (0.218 at -3c) and the account sat in the push feed's fan-out (+65 ms behind P4e); in October -1c and +34 ms.
- **Selection replicates out of sample on the earlier account (VALIDATE-only).** The frozen league / GRID component of
  v4 / v5 (fitted on the wallet's 10-16..10-22 events) scores 0x7d67f01d's choice among all 718 CS2 events of
  10-01..10-15 at AUC 0.942 (0.868 within non-GRID events); the wallet's own GRID-taker events of that window score 0.134.
- **The value is an in-round win-probability state (hypothesis with a historical, outcome-validated measurement).**
  Within rounds inferred from the public print, its level moves toward the bo3 round winner at AUC 0.899 against the
  print's 0.675 (gap 0.224 [0.185, 0.263]); 0.788 vs 0.619 even with the last 45 s before the inferred round end left
  out; using only the bursts before the print's first 2c move inside the round, 0.708 vs 0.540 (0.616 in the rounds
  where the print moves later), so part of it is ahead of anything the market has priced. One value per event: same-tick map / match re-pricings agree in team direction in 96% and move by about the
  same cents (not scaled by the series sensitivity), while the public match book moves far less.
- **Not the value:** three CIS bookmakers' archived in-play Dota lines (BetBoom, SpinBetter, Parimatch from hawk.live; no
  closer than the print after a clock-free alignment); EMA filters of the public prints (0.12-0.30 within one tick
  against the last print's 0.305); its own previous top plus the sign of the last-second public move (0.35 through the
  ladder machine against others' best 0.50); a side-aware MR12 score table at round starts (residual 3.96c against
  the print's 2.82c).
- **The event path is co-reception.** 65-81% of its "triggered" adds were signed before their trigger reached the book;
  the co-movers are other operators' makers on the same hidden stream; withdrawals start on the same co-mover clusters
  as its other pulls; its maker leg re-prices at the pack's messages it does not take (5.3x shifted), so the take's
  kind filter is a decision (value threshold), not a gap in its input. The lead of its level holds on other traders'
  executed prices (Spearman 0.32 vs 0.15 for other makers) and on a joiner-free mid (0.42 at 10 s vs 0.17), although
  other makers do join its new top (3.5-6.4x).
- **Salts.** Not one recoverable V8 Math.random stream, for the wallet alone or merged with its 5-share accounts.
- **First VALIDATE-live block (11-01 06-12).** By 09:43 UTC six development-unit events had started (four GRID); v5
  selected none and the wallet traded none (6 of 6 agree, no positive yet).

## What iteration 12 established (no rule change)

- **The ladder under V is mechanical (VALIDATE-only, BUILD-live oracle; `code/iter12/ladder_machine.py`, constants
  frozen).** A burst of n adds takes the n highest free whole-cent slots V, V - 1c, ..., V - 4c inside [0.05, 0.95],
  top-first. With V known (its own top after the burst) this gets 0.875 of its 2,698 adds within one tick when the
  burst's prices are matched to the slots by rank (the burst-set unit), 0.73 per order without that rank, 0.83 of whole
  bursts; up / fresh / down bursts 0.87-0.94, unchanged-V bursts 0.56. V must be exact to the cent (+-1c: 0.70 / 0.81;
  +-2c: 0.22 / 0.08). This corrects iteration 11: the price item fails because V is private, not because of the
  ladder. Public V proxies through the machine stay at 0.41-0.50.
- **V is not a round-score table (VALIDATE-only).** A clock-free hidden-Markov fit of its levels to an MR12 / MR3 Markov
  valuation on 92 maps fits no better than the same fit of the public print (residual 3.22c vs 3.21c; the true bo3
  winner sequence ranks 0.14 vs 0.10 among permutations). Pre-registered verdict: not a score table.
- **V is not a map of public per-minute Dota state (VALIDATE-only).** An inverse fit of its Dota levels on gold / xp /
  kill leads and the pre-game prior scores 0.17 within one tick (MAE 5.4c) against the last print's 0.42: the right
  clock beats shifted clocks (0.07-0.09), so the state carries the coarse level, but not the cent.
- **The quiet class runs on its ~504-ms loop (hypothesis, BUILD-live).** 73% of its untriggered adds fall within 15 ms
  of the tick predicted from its previous untriggered burst (6% uniform); takes are never on the loop (0 of 22).
  Public book changes in the previous tick explain at most about 14 points of those re-pricings.
- **It takes when its revealed value reaches the stale ask (hypothesis, BUILD-live).** After its takes its own bid on
  the bought token sits a median 1c under the old ask; after untriggered re-pricings 3c under it (AUC 0.81, no sharp
  threshold).
- **It withdraws whole events for variable lengths (hypothesis, BUILD-live).** 64 event-wide holes of two ticks or
  more last a median 12.5 s (p90 113 s), only 3% at the three-tick repair, and bracket public price action. That is
  what an odds-product suspension or a round-boundary policy would produce; the Thunderpick coincidence test waits
  for development records of matched matches.
- **The outcome bound at public latency is a property of the market (VALIDATE-only).** In 3,028 informed bursts
  without the wallet, later takers obtain at the leader's limit after its match only 3-7% of what the wallet takes in
  comparable bursts: the stale remainder is gone by the match anyway (the T_lo world is real, not a replay convention).
- **Examinable historical price.** A point-in-time book built from other makers' partially filled orders does not
  beat the last print (0.274 vs 0.275 on VALIDATE).
- **No predecessor wallet.** The deposit wallet was created on 06-16 at 13:00 UTC, 5.5 h before its first trade; its
  owner is an EIP-7702 account (nonce 3) whose Polymarket Safe was never deployed.
- **Recorder.** Kick stream clocks (IVS playlist timestamps, text only) are recorded from 11-01 07:51 UTC
  (`tommy_kick_pdt`).

## What iteration 11 established (no rule change)

- **No examinable own-state price anchor beats the last print** (point-in-time re-derivation; the earlier 0.500 /
  0.599 / 0.716 used the predecessor's later fill, a censoring lookahead). Within one tick on VALIDATE: last print
  0.305; its own level that the chain had revealed at signing 0.280; the union of the two 0.418. The fill-selected
  numbers stay only as descriptive footnotes.
- **A second venue does not carry its value.** Every SX Bet fill on the SX Rollup chain in 16-22 Oct was decoded
  key-free: 29,603 fill txs, but only 11 CS2 markets with 63 fills in the whole week (6 of its 80 events, about one
  in-play fill per hour). Where they exist, SX makers quote +4.2c above Polymarket's last print (SD 3.6c) and far from
  the wallet's level (SD 7.1c). No historical external price for h1 / h2 comes from there.
- **The fast receivers' fresh levels are not its value.** On the raw BUILD-live book, a touch built only from levels
  re-priced in the last D seconds scores below the full touch at every D (0.39 vs 0.40 on fills, 0.39 vs 0.41 on adds,
  second half). Synchronous re-pricings of the six fast makers do not share its increment (correlation 0.28 against a
  shifted control of 0.28; pre-registered verdict: own model).
- **The per-order price item is capped even with its value known.** With V = its own top after the burst (an oracle),
  its adds sit at slot 0 (44%), -1 (19%), -2 (13%), -3 (10%), -4 (13%): "price = V" is within one tick of 63% of adds and
  71% of filled orders, and a slot classifier on its own ladder and the book reaches 0.75. No rule that knows V reaches
  0.80 per order; the unit a value decode could pass is its top level. (Corrected in iteration 12: with ladder state
  relative to V the oracle reaches 0.73-0.79 per order and 0.875 on the burst-set unit.)
- **The outcome item hinges on the take, not on the maker's timing.** Its own maker orders delayed by up to 2 s plus
  its real taker leg still correlate 0.70 / 0.62 with its per-market PnL (VALIDATE; 0.89 / 0.82 at 0 s). Delaying the
  take is what breaks it on the observed record: its own FAK empties the stale remainder at its limit (median residual
  0 after its match on the BUILD-live book), so a public copy at any lag gets at most 0.50 / 0.41. Only in a world
  without the wallet would the slow makers' stale orders (flat over the last ~200 ms before its match) survive a
  further 100-300 ms.
- **At the brief's executable latency the outcome item is out of reach by definition.** Executing every one of its
  own decisions 2 s late on the observed record (an oracle copy) gives 0.43 / 0.40 on VALIDATE and 0.23 / 0.36 on
  BUILD, below 0.5 on Spearman whatever the decode. A class-wise knockout (its maker classes re-priced at the last
  print, real taker leg kept) shows the outcome is spread over the whole ladder: quiet, follow and message orders
  each cost 0.10-0.19 Spearman, repairs and the endgame almost nothing; only re-pricing the quiet and follow classes
  together (92% of its orders) drops it below 0.5. Stopping its loser bids at 0.15 would raise its replayed maker
  PnL (VALIDATE +$4.6k to +$9.2k): bidding a collapsing team down to 0.05 costs it money.
- **The event stream reaches other makers too.** On the live book, 30% of its untriggered re-pricings coincide within
  40 ms with a non-own change on another market of the same event (20% at 0.2-1 s shifts): about a tenth are
  synchronous beyond clustering, without a shared increment (one event stream, each receiver's own model).
- **An echo-protected public maker is not admissible.** The informed flow completes inside the 1-s delay (depth at the
  take limit 0.34 of its signing value at +140 ms), so a rule with the brief's >= 2-s latency cannot protect itself.
- **Pre-game it bids 1-2c under Polymarket's own price** (within one tick of the last print 0.39-0.49 before the start,
  narrower than in play): no large private prior before game state exists.
- **The forward build drifted in taker size and merge timing, not in price.** On the 10-31 development blocks the band,
  whole cents and the Dota 10-share size hold; the CS2 100-share share is 57% (88-92%) because 3 of its 4 CS2 events
  there use the known event-wide ramp (54-87 shares), the taker size fell to a median of 129 shares without the 1000 /
  2000 caps, and the merge loop's per-merge increment no longer fits (50% of passes within 10 s of the law, 99%
  before). The taker-size and merge constants need a BUILD-live re-fit before a future-block exam.
- **Recorder.** The Thunderpick recorder now also records the pre-game line, the per-match object's cadence and bo3's
  coverage fields (`tommy_tp_odds2`, from 11-01 05:29 UTC).

## What iteration 10 established (no rule change)

- **PGL Masters is the exam lots' only non-GRID tier-1/2 stratum, and v5 treats it by coverage** (listing projection;
  pre-registered before any exam). h1 holds 18 PGL Masters events and h2 21; development had none (every development
  tier-1/2 CS2 event was GRID-flagged). The league first appears on 10-24, an h2 day, so every h1 PGL Masters event has
  an earlier event of the league within 72 h. v5 then decides each event by gp72 (group-P prints in those earlier
  events, which the examiner counts): about 0.40 at gp72 = 0 (not selected; threshold 0.472), 0.57 at 1 and 0.66 at 2
  (selected). The organiser's lower-tier league PGL was traded 9 of 13 in development, and non-GRID traded rates rise
  as the tier number falls (tier 5 0.06, tier 4 0.51, tier 3 0.91). Residual risk: if the wallet trades PGL Masters
  but group P does not print in the earlier events, h1 recall falls to about 0.45. h1's expected base rate is
  0.145-0.222, so the lift ceiling (4.5-6.9) does not bind.
- **Exit band.** All 25,878 of its orders (maker bids and taker limits) lie in [0.05, 0.95], while 10% of the public
  makers' bids in the same markets lie outside: a client constant. It bids the eventual loser down to that floor
  without an earlier stop.
- **The message re-pricing is event-locked.** On P4e's messages the wallet signs before, or less than 20 ms after, the
  fastest co-receiver maker (0xed446954, +18 ms) on 33% of shared messages (a book reaction needs >= 20-30 ms). The two
  lags correlate -0.48, and the wallet's lag is the same with and without any faster maker's order. It is not copying
  a faster maker's book move.
- **The feed carries events, not a price.** Across 501 messages with two or more takers on the same token, the
  receivers' limit premiums over the stale print share little (ICC 0.28-0.43 after receiver fixed effects; a broadcast
  price would give >= 0.8). Each receiver values the raw events with its own model.
- **Its add level is its own information.** Measured from 100 ms after the add, its level predicts the others' mid
  (Spearman 0.24 at 10 s, 0.36 in quiet books) far better than every subscriber-like maker class (5-share 0.10,
  10-share 0.08, 20-share 0.13; quiet books <= 0.10).
- **One valuation per event.** On the same feed message, its re-pricing of the match market follows its re-pricing of
  the current map market at about the BO3 series sensitivity (median ratio 0.50 on map 1, 0.40 on map 2; same sign
  0.78 / 0.74 against a within-event permutation null of 0.56 / 0.52). Its maker leg prices every market of the event
  from one model of the game, as its taker leg does. That reduces the price unknown to its map value, which is the
  private value itself.
- **The price gap is everywhere, not at messages.** 71% of its filled maker orders are signed more than 5 s after any
  message or own take, and even these sit within one tick of the last print only 37.5% of the time (54% of its own
  previous level). Message phase explains 4% of the offset at the true clock. Own-state persistence looked like the best
  historical anchor (0.500; 0.72 within 2 s of its previous order on the token), but that number uses the predecessor's
  later fill; point-in-time it is 0.280 (iteration 11), below the last print.
- **The outcome item needs its +50-ms take timing.** With its real taker leg, a replay of its own maker orders
  correlates 0.87 / 0.80 with its per-market PnL (VALIDATE). With the taker moved to its earliest public trace, even
  that oracle maker leg reaches at most 0.60 / 0.44 (BUILD 0.46 / 0.50), and every executable public set stays at or
  below 0.33 / 0.21.
- **New source.** Thunderpick's in-play odds, relayed key-free by bo3.gg's live index, are recorded from 11-01 03:59 UTC
  (`tommy_tp_odds`). Tests (a)-(f) and verdicts are pre-registered (NOTES iteration 10). This is the only external
  in-play price obtained so far.

## What iteration 9 established (v5: the selection score adds group-P coverage; nothing else in the rule changed)

- **Selection = the coverage of the feed product the wallet buys.** Fixed on BUILD only, the fixed-lag co-signers of
  P4e split by their GRID share into group P (P4e, 0x2005d16a, the slow trio 0x72aaaaf9 / 0x2529c68d / 0xfe8a28be: at
  most 1.6% of their prints in GRID events) and group G (the +150-230-ms group: 28-53%). v5 = logistic(1.248 logit(v4
  score) + 1.189 log1p(gp72) - 1.113), gp72 = group-P members with a print in another event of the same league in the
  previous 72 h (point-in-time, wallet-independent). Adopted under the criterion pre-registered before scoring. VALIDATE
  pooled AUC 0.970 (v4 0.953) vs activity 0.886, gain +0.084 [0.030, 0.152], recall 0.744, lift 3.155; CS2 unseen
  leagues 0.974 (v4 0.928). In development runs the earlier events of sealed periods are skipped, so on forward
  development blocks gp72 is under-counted (10-31 block: recall 0); the examiner counts every earlier event.
- **GRID is a coverage boundary, not a speed boundary.** Group G's fan-out has the same delivery order in GRID events
  (lags behind 0xf1ee4842 within 2-15 ms of their non-GRID values) and is more informed there (60-s markout +2.80c vs
  +1.57c, no pre-move). The wallet's product does not carry GRID events.
- **The fan-out is one broadcast** (the order of co-signers is what their own lags predict; common-mode lag residual
  r 0.86), with a load-dependent queue at the slow trio (+142-188 ms per extra message in 1 s). Isolated Dota kill
  messages look machine-timed (77% of kill-linked hits inside a 0.8-s window), small n.
- **The outcome item is the price item.** In the validated engine, the wallet's own prices quoted continuously earn
  +1.3-1.4% and keep most of the per-market margin correlation (BUILD 0.66 / 0.61), while its own resting windows at the
  public anchor lose 2.3-4.5% at pair cost ~1.00. The best executable public variant correlates 0.25 / 0.09 with its
  per-market PnL (below the prints baseline 0.33 / 0.28).
- **No public state predicts the price level.** A public game-state fair value for Dota (gold / xp / kill leads on the
  feed's clock) scores 0.41 within one tick against the last print's 0.43; a public tape-state model 0.285 against
  0.298; the Dota ladder is only weakly locked to kills (13% of bursts within 6 s vs 10% on shifted clocks). CS2 has no
  public round clock for its events (P4e's take sequence does not align with bo3's round winners: identity 0.785 vs
  0.792 permuted).
- **Its residual is taken by group P** (14.8% of its maker shares; -4.1c per share on the residual), not group G (2.0%).
- **Its quote level is an informed private value that leads the public book** (BUILD-live, uncensored adds). The
  offset of each validated own add from the others' mid predicts the others' mid move: Spearman 0.52 / 0.44 / 0.34 at 2 /
  10 / 30 s (other makers' adds 0.24 / 0.17 / 0.09; time-shift null ~0), 0.38 at 10 s without any own take or public
  trade just before; the offset does not follow the prior 2-s move of its own or the sibling book (0.02 / 0.03). Its
  informative re-pricings precede 11% of the slower subscribers' takes within 1 s (about 10x the shifted null): the
  maker leg moves on the feed's messages, which is why no public anchor reaches the price item.
- **Co-receivers.** Other makers cancel within 8 ms after its alone takes (0.115 vs 0.021 per take, p 0.007), before
  its order or own pull can be visible: weak support for one feed with the kind filter at the takers.
- **New key-free source.** Valve's dota2.com webapi spectator state (4-s snapshots) is recorded from 11-01 02:14 UTC
  (`tommy_dota_rt`) for the pre-registered Dota timing tests.

## What iteration 8 established (v4: the universe adds Dota 2; nothing else in the rule changed)

- **Scope was going to fail the exam.** The wallet started a Dota 2 module on 10-22. A CS2-only universe covered 0.846 of
  its fills on 10-22 and 0.43-0.46 on the 10-31 12-18 development block (0.78-0.93 of absolute PnL). v4 adds every Dota
  2 match / map-winner market (Gamma series 10309) and `evaluate()` now computes `coverage_fills` /
  `coverage_abs_pnl` on the lot: 1.000 / 1.000 on VALIDATE and on the forward block.
- **The Dota module is the same maker process**: 10-share whole-cent BUY ladders on both outcomes, merges in the same
  300-s loop, pairs at ~0.98, plus 67 takes on the same push feed (P4e signs 50 ms before 22% of them, as in CS2; iteration 7 had missed this because P4e's Dota takes sit in public transactions that were never decoded). **The GRID boundary holds there
  too**: EPL Masters (GRID-flagged) 0 of 33 events; PARI Universe (non-GRID) 3 of 4 on 10-22 and 2 of 3 on 10-31.
- **The wallet's selection is the feed's coverage.** P4e (a pure feed taker) is present in 0 of 122 GRID events and in
  22 of 22 non-GRID tier-3, 36 of 96 tier-4 and 0 of 144 tier-5 events; the wallet trades 88% of P4e's events and 8% of
  the others. One tiered esports product with the GRID-exclusive events removed. Point-in-time coverage features (the
  subscribers' takes in earlier events of the league) beat a league-popularity control (+0.05 AUC) but not the league
  table on VALIDATE (0.944 vs 0.957), so v3's table stays and the coverage variants join the forward pool.
- **The feed: one esports fan-out of raw events.** The wallet - P4e lag does not depend on the event class (reversal -
  follow-on +10 ms [-4, +22]); the CS2 fan-out does not repeat in football / NBA / tennis (13 co-signs, null 4); the
  wallet's limit shares no value with P4e's (premium correlation 0.21, SD of the difference 3.3c); Polymarket's own score
  provider is 16 s to minutes behind the market for GRID and non-GRID events alike; 0xf1ee4842's later signing is on the
  feed side (its CLOB path is only 5-15 ms slower than the wallet's).
- **A first in-game clock (Dota 2, hypothesis).** The feed's Dota messages (P4e's and the wallet's takes) follow kills
  of the team they buy at one per-map offset (1035-1050 s after the replay's start_time on four maps of two series;
  side-label null p < 0.005-0.07); public price moves sit 3-14 s later on the same clock. The tournament's spectator
  delay is 900 s (own OpenDota recorder), so the Dota half of the feed may ride the delayed broadcast, a few seconds
  ahead of the stream-watching market; the calibration on a live development block is pre-registered.
- **One controller.** Every sampled order (both legs, both regimes, 10-01..10-22) is signed by owner() 0x8af810f0 (ERC-7739
  nested signatures recovered); no key is shared with any other maker sampled, the subscribers included.
- **Maker leg between takes.** Ground-truth cancels (remainders of partially filled orders) confirm the pull label
  (co-burst precision 0.955) and show the untriggered effect on the wallet's own cancels (-0.94c in 10 s, n 17, p 0.034)
  but not on other makers' (+0.74c). The untriggered pulls are ladder re-pricings (re-added in 6-261 ms), not take
  receipts (re-post 1.03 s after a take); public execution state does not separate takes from them (AUC 0.52). The take
  hazard rises weakly with earlier re-pricings (3.5% vs 0.8% after 3+ in 10 s).
- **Price and outcome stay blocked.** No own-state ladder machine beats the touch (0.29 vs 0.47 per add; oracle union of
  four rules 0.73); a balanced pair-ladder replay correlates 0.03 / -0.09 with the wallet's per-market PnL.

## What iteration 7 established (selection unchanged; the live price rule re-frozen to the touch)

- **The taker input is (at least partly) a shared push feed.** 26% of its take clusters are co-signed at fixed lags by
  at least one of six other wallets (null 0.3%); the other 74% it takes alone. Its takes are co-signed on the same token by P4e 0x4ebc2722
  (-50 ms, 203 takes) and 0x2005d16a (-20 ms, 49). Their offsets have event components of 7-9 ms and no platform effect
  (Kick - Twitch +2 ms [-7, +12]): one message fanned out, not separate stream readers (pre-registered verdict). Four
  slower wallets (0xf1ee4842, 0x8a80528d, 0xddb6e624 at ~+200 ms after P4e, P93 at ~+400 ms) act at the same fixed lags
  on P4e's round-win events and on the wallet's plant / turn events (each on 1-3% of P4e's takes). **The feed delivers
  the round-win kind to them; the wallet's takes avoid it** (its own bursts load on plants, P4e-alone ones on round
  wins), and it does not decline by edge: once its own followers are removed, the edge P4e left does not
  predict its presence (p 0.17), while the event kind does (reversal +0.61, same-team follow-on -0.52). (Corrected in iteration 8: P4e co-signs 15 of its 67 Dota 2 takes at -50 ms once the Dota markets' public transactions are decoded.) None of these
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
| Selection | Unit = CS2 or Dota 2 event (match plus all map-winner markets; Gamma series 10310 and 10309). v4 score: `s_lg` = 0 if `eventMetadata.gridSeriesId` is set, else the league's traded rate among fitted non-GRID events shrunk (k = 3) toward the tier rate; logistic(log1p pre-game taker prints, USD and distinct wallets in [gs-1h, gs); `s_lg`). v5 score = logistic(a logit(v4) + b log1p(gp72) + c), gp72 = distinct group-P members (P4e, 0x2005d16a, 0x72aaaaf9, 0x2529c68d, 0xfe8a28be; fixed on BUILD) with a public taker print in another event of the same league that started in [gs - 72 h, gs), prints before gs. Trade the event iff the v5 score >= thr (20th percentile of the fitted positives). | VALIDATE-only | v5 pooled VALIDATE AUC 0.970 vs pre-game activity 0.886, gain +0.084 [0.030, 0.152] (0 of 4,000 draws <= 0), recall 0.744 at lift 3.155; CS2 0.972 (unseen leagues 0.974 vs v4 0.928), Dota 0.926. GRID events traded: CS2 0 of 122, Dota 0 of 33. Mechanism: the coverage of its feed product (group P); GRID events are covered by group G's fan-out with the same delivery order. Forward 10-31 12-18 (development run, sealed earlier events skipped): AUC 0.842, recall 0. Iteration 13: the league / GRID component scores the operator's earlier maker account (0x7d67f01d) on 10-01..10-15 at AUC 0.942 out of sample (non-GRID only 0.868); first VALIDATE-live block so far 6 of 6 skips agree. |
| Timing (maker) | Quotes from game start to the end of each market, re-signing continuously in busy phases. At its own taker signal it cancels its complement ladder within 11-19 ms and re-quotes it about 1.04 s later, when its FAK returns. | VALIDATE-only (re-quote); live dev block (pull) | Own pull after 90-95% of live takes. Re-post hazard on the complement: 236x in [1.00, 1.14) s after its take. Its re-quote bursts co-occur symmetrically with other makers' changes (50 ms before 67%, after 69%, null 19%). Iteration 12 (hypothesis, BUILD-live; X158): the quiet re-pricings run on a free ~504-ms loop (73% of untriggered adds within 15 ms of the predicted tick, 6% uniform; takes 0 of 22 on the loop), with little public trace in the previous tick; it withdraws whole events for a median 12.5 s at moments of public action (X159 steps 1-2). |
| Timing (taker) | At messages of a shared CS2 push feed (>= 6 subscribers at fixed lags; P4e signs 50 ms before it), of the plant / turn kind only: typically the first informed move against the previous burst. Not decoded: on those events it signs before every public Polymarket trace, it acts on only about 16-20% of the informed 3c+ bursts in its markets, and it skips the round-win kind the other subscribers take, without an edge-based decline. | hypothesis (fan-out structure: development data, iteration 7) | Match / map books flat until it signs. Round-market takers precede it in 0.9% (controls 0.2-0.7%). Census: 80% of informed bursts wallet-absent; present 29-35% after a burst on the other team, 6-8% after one on the same team; point-in-time AUC 0.698 for which bursts it leads (pre-burst public features). Absent bursts follow round wins, its own follow bomb plants beyond wins (p 0.03). No delay-queue leak. Iteration 13: its maker leg re-prices within +-30 ms of the pack's clusters it does not take (5.3x shifted), so the kind selectivity is a take decision (value threshold), not a gap in its input; the operator's earlier account took on the same feed at +34-65 ms behind P4e from late September. |
| Side (maker) | BUY both outcome tokens. | VALIDATE-only | 97.4% of bought shares end in pairs. |
| Side (taker) | The team that just gained in-round on plant-type events. | hypothesis | The team gains +2.6-2.9c in 10 s. T side only 54% (p 0.13). |
| Price (maker) | BUY at the other makers' best bid (join), whole cents (the in-play tick), in ladders 1c apart; one token per re-quote burst, the two tops summing to at most ~0.99. After its own take: complement top = K - L (K 0.94). | VALIDATE-only (historical anchor); live development block (join rule) | Last-print anchor within one tick: 0.305 (`price_within_tick`, VALIDATE). Live, own levels removed: re-quote top within one tick of others' best 67.4% (exact 37%). Revealed best bid from the matched-order record: 0.25-0.28 against last print 0.22-0.25 on the same rows. K - L: 57% in the first 1.04 s after a take (n 247), 6-14% later. Probe presence AUC 0.67. Iteration 12 (VALIDATE-only as a mechanism, BUILD-live oracle; X163): given its value V, a burst of n adds takes the n highest free whole-cent slots V .. V - 4c, top-first (0.875 on the burst-set unit, 0.73 per order); V is not a round-score table (X171) nor a map of public Dota state (X167); a point-in-time partial-fill book does not beat the last print (X165). Iteration 13 (hypothesis, historical outcome-validated): V is an in-round win-probability state (within-round drift toward the bo3 round winner AUC 0.90 vs the print's 0.68), one value per event on the map and match books; not a de-margined BetBoom / SpinBetter / Parimatch Dota line, not an EMA of prints, not its own top plus the public delta; the five-slot ladder confirmed historically through the operator's 5-share accounts (98%). |
| Price (maker, live, frozen) | `live_price` (re-frozen in iteration 7, before any VALIDATE-live record): primary = the touch, i.e. the full-book best bid on the order's token at sign - 100 ms (LIVE_PRICE_PRIMARY "touch"). Secondary = the join: others' best bid with the size-labelled own levels removed, min with 0.99 - own top on the other token (LIVE_VIEW_MS 100, PAIR_CAP 0.99). | hypothesis (BUILD-live only) | 10-31 block, 172 filled maker orders: touch 0.471, join 0.424 (0.419 with the calldata-validated label), last trade 0.187. The whole 12-18 block through `evaluate()` (328 orders, early books from the shared recorder): touch 0.280, join 0.256. To be scored on VALIDATE-live (11-01 06-12 on) and by the future-block examiner. |
| Price (taker) | FAK at the stale ask + a premium that grows with the expected repricing (0-5c), kept below the post-event price; match-leg premium = map-leg premium x series sensitivity. | VALIDATE-only (premium-move relation); hypothesis as a rule | Controlled OLS: +0.87c of 10-s move per 1c of premium (p 7e-11, VALIDATE). Caps (1000 / 2000 shares) carry little of it. |
| Size | Maker: 100 shares in CS2. In 36% of events an event-wide size starts at 50-96 (median 54) and steps up monotonically to 100. Exactly 10 shares in Dota 2 (1,292 of 1,292 orders). Taker: odd sizes about 0.3x of the pre-event depth up to its limit; 1000 / 2000 caps early and fading. | VALIDATE-only (maker 100 / 10 and the ramp's shape); hypothesis (ramp clock, taker) | CS2 100 shares: 92.1% (BUILD), 88.3% (VALIDATE). No global (a, b) schedule (0-4% of non-100 within one share). Start size vs pre-game USD: Spearman 0.55. |
| Outcome (executable, v6) | `_replay_v6`: one BUY level per token at floor(others' bid on that token) = the latest wallet-free taker print that consumed bids on the token, usable 2 s after its block; pair cap 0.99; band [0.05, 0.95]; 100 shares (Dota 10) refilled every 10 s; strict trade-through fills; settlement PnL per market of v5-selected events. | VALIDATE-only | Per-market Pearson / Spearman with the wallet 0.197 / 0.027 (v5 replay -0.131 / -0.081; prints baseline 0.329 / 0.289; partial given prints 0.176). Not the wallet's process: its outcome needs its value and its informed takes (an oracle copy at 2 s caps at 0.43 / 0.40; the wallet's exit policy in a public ladder does not lift it, X218). |
| Exit | Never sells. Pulls the complement at its takes and re-pairs it through bids posted 1.04 s later, which slower informed takers fill. Between takes it pulls the bids of the team about to lose value on private events (untriggered pulls: -0.6c others'-mid markout in 10 s). Merges complete pairs in a 300-s loop (minimum 100 shares) and holds the residual. Hard price band: it never bids below 0.05 or above 0.95, and it keeps bidding a collapsing team down to that floor (no earlier stop). (The iteration-6 public-wave follower is withdrawn: an artefact of the size label.) | VALIDATE-only (pairs, merge law, band); hypothesis (untriggered pulls, BUILD-live) | Pair cost 0.978, reproduced by the validated engine on its own orders (0.975). In bursts it misses, its complement is hit in 19-22% (-1.5 to -3.2c markouts). A public ladder 4c below the stale touch reaches 0.978 but loses $13.4k per split on its residual. Band (iteration 10): 0 of 25,878 orders outside [0.05, 0.95] against 10.0% of public maker BUYs; last fill on the eventual loser p50 0.11, minimum <= 0.06 in 24% of markets; the band does not repair public replays (D 0.245 / 0.087 with it, 0.245 / 0.089 without). Iteration 15: net position capped near 600 CS2 shares with a long-side taper from 200 (share of fills on the long side 0.44 below 200, 0.21 at 400-600, 0.00-0.03 above 600). |

## Target metrics on VALIDATE (`state.json` `target_metrics`; v6, build constants)

| Metric | Value | Baseline / note |
| --- | --- | --- |
| Selection AUC | 0.970 | Baseline 0.886 (pre-game activity). Recall 0.744, lift 3.155. Gain +0.084 [0.030, 0.152], 0 of 4,000 bootstrap draws <= 0. CS2 0.972 vs 0.892; Dota 0.926. v4 on the same events 0.953. |
| Presence AUC | 0.883 | Baseline 0.891 (fill presence per 30-s bin; v5 event score x in-play). Forward block 0.911 vs 0.823. |
| `price_within_tick` | 0.322 | In-play tick, last-print anchor at signing (order unit). Fill unit (iteration 15, reported, not the target unit): 0.496 against the last print before the fill minus 1c; generic makers 0.605. Live (BUILD-live): touch 0.472 per add, 0.471 on filled orders; own-state machines 0.09-0.50. |
| `pnl_corr_pearson` / `pnl_corr_spearman` | 0.197 / 0.027 (v6) | v6 bid-side anchored replay; the v5 generic tape ladder scored -0.131 / -0.081 on v5's selected events. Validated-engine public ladder (knockout D) +0.245 / +0.089 on the wallet's markets; balanced pair ladder +0.034 / -0.085. Co-occurrence baseline (in-play prints) +0.325 / +0.283. |
| Side | Not applicable at market level | The maker is two-sided in CS2 and Dota. The taker side follows the unobserved feed. |
| Coverage | 1.000 of fills, 1.000 of absolute PnL | Computed on the lot by `evaluate()` (v4). A CS2-only universe: 0.927 / 0.990 on VALIDATE, 0.43-0.46 of fills on the 10-31 block. |

## Which exam lot can judge what

- **h1 and h2 (10-23..30)** have no books and no game feed: the recordings start on 10-31.
  - They can judge selection, maker size, maker price against the last print, and exit.
  - The outcome replay on tape and calldata does not track the wallet, so h1 / h2 cannot pass outcome with any
    public-data rule found so far.
  - Sweep probes exist on h1 / h2 too (on-chain), but no rule predicts them well (AUC 0.67).
- **`clob_wallets` is never a presence or selection input** (iteration 16, X222): in 8 of 9 of the wallet's markets of
  the 10-31 development block it was first subscribed 3-19 min after the wallet's first trade. It serves only as the
  fallback book of the live price rule, for orders that already exist.
- **Future sealed blocks.** `evaluate()` reads `tommy_cs2_near`, then `clob_wallets`, through
  `iter_live(..., allow_sealed=ALLOW_SEALED)`, on the server clock, and reports a taker diagnostic and the frozen live
  price rule (`live_price`). From 10-31 19:28 UTC the
  own recorders `tommy_cs2_rounds` (round markets) and `tommy_chat` (chat clock) record every block too.

## Why it works (economic mechanism)

- **Iteration 16 note** (hypothesis). The clock-free counts and the match-time clock point to round results as the content of the feed's informative messages; what the operator is paid for is knowing who won the round before the market does, and quoting the new value on both books while the stale makers and the slower subscribers still trade at the old one. The operator runs the same business on GRID events through a separate account (0x10d79cc7) whose quotes are not the public print either.
- **Iteration 15 note** (hypothesis). The private input is a push feed whose messages are mostly round results, delivered before and around the market's reaction, with a small in-round part. The operator is paid for pricing those results a second or more before the market does. Its counterparties are the makers it picks off and the takers who sell into its bids after it has already moved.

1. **Universe** (VALIDATE-only). It trades only events without official GRID data, in CS2 and (from 10-22) Dota 2; the set is the coverage of its push feed (P4e's presence follows the same tier x GRID boundary, iteration 8). There, Polymarket's own sports
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
   uninformed flow, and rebates. Iteration 9: the margin is earned by the LEVEL of its bids (its own price sequence quoted
   continuously earns +1.3%; the public anchor at its own resting windows loses 2.3-4.5%), so the private value prices the
   ladder, not only the takes. The informed counterparty that takes its unpaired residual is group P, the earlier
   subscribers of its own feed, on the messages it does not take.

7. **What the value knows (iteration 13, historical, outcome-validated).** Within a round its value drifts toward the
   eventual round winner (AUC 0.90) while the market's print does much less (0.68; 0.79 vs 0.62 with the last 45 s
   before the print-inferred round end left out): it is an in-round win-probability state updated by in-round events
   from the push feed (part of the gap may be its faster reaction to round results, since the rounds are inferred from
   the print). The stale makers it intermediates against, and
   the informed pack on the messages it does not take, are on the other side of that gap.
8. **Who runs it (iteration 13, on-chain).** One operator with at least four accounts on one signing process; the same
   strategy (maker design, prices, feed position, selection) ran on the earlier account 0x7d67f01d before 10-16 and was
   moved to the main account when its GRID taker stopped. The edge is the operator's feed position and value model,
   not a Polymarket programme.

9. **Leading hypothesis for the source (iteration 8, untested):** the feed is a broadcast-side automated reader of the
   games' public spectator relays (CSTV+ / GOTV, DotaTV), which would explain the GRID and tier-5 gaps in its coverage,
   the Dota offset at the 900-s spectator delay, the raw events and the absence outside esports. Its subscribers then
   earn by being seconds faster than stream watchers and slower bots inside the 1-s in-play delay.

## Can a normal user deploy it now

- **Iteration 16 note.** Two conditions changed after T0: the fan-out's fastest subscriber (P4e) no longer takes in the operator's development-block events, and the wallet itself made no trade in the 11-01 06-12 block. A replicator would still need a round-result source that beats the market by about a second; neither Polymarket's sports socket (20.2-s polling, GRID only) nor any key-free score source found so far does. A historical tick-level book for back-testing a copy is for sale (Telonex), not free.
- **Iteration 15 note.** The feed has to deliver its messages within about 0.25 s of the first co-receiver to precede 85% of the wallet's message-locked re-pricings. Polymarket's sports socket polls round scores every 20.2 s and only for GRID events, and Valve's Dota snapshots arrive every 4 s, so neither can stand in for it. A public-only copy of the ladder (v6's outcome replay) earns about zero and does not track the wallet's per-market PnL.

- **Needs:**
  - a subscription to the real-time in-round push feed that the informed wallets share for non-GRID CS2 matches (at
    least six subscribers; not GRID, not Polymarket's sports socket, not bo3.gg; its vendor is not identified), with a
    position in its fan-out at least as early as the wallet's;
  - a CLOB client that signs FAKs and cancels within milliseconds;
  - a live-book two-sided ladder with merging;
  - about $10k of capital.
- **Conditions still hold** in the 10-31 development block: it is active in non-GRID events and still signs first.
  In the first VALIDATE-live block (11-01 06-12) it had not traded by 09:43 UTC (the block's non-GRID events so far
  were outside its selection, and v5 skipped them too). Iteration 13: the strategy is older than the wallet's maker
  regime (on another account of the same operator from at least late September), so the conditions are not a one-week
  anomaly. Iteration 14: the whole 11-01 06-12 VALIDATE-live block passed without a wallet trade (cs2-bca-pha, its
  last candidate, still untraded at 11:56 UTC).
- **Iteration 14 numbers for a replicator.** The feed is esports-only as far as the operator's accounts show (its sports
  account is a slower state-based taker). A copy that receives the same messages 0.25 s later than the wallet already
  loses 60% of the price item (X201); a public ladder gated on the visible informed-take clock earns about 0% and does
  not track the wallet's per-market PnL (X202). So without the feed and a fan-out position near the wallet's, there is
  no reduced version worth running.
- **A replicator with public data and a home connection** sees the event only through the cancel wave or later.
  - The wallet's own ladder is hit at about a third of the pack's events and barely pulls there (17% vs 10% in a
    control, iteration 7); a home connection 100-300 ms behind the cancel wave would be hit more often. Its maker adds
    land about 24 ms after signing and its take-time pulls 11-19 ms after its signing, so it is co-located with the CLOB.
  - Following the pack's prints lost out of sample.
  - A tape-based ladder 4c below the touch locks the same pair cost, but its unpaired residual makes it lose about 6%
    of the volume it buys.
- **What the feed is not** (iteration 8): not Polymarket's sports socket (16 s to minutes behind the market), not a
  multi-sport B2B feed (no fan-out in football / NBA / tennis), not an odds feed (no shared value with P4e). It is an
  esports push product of raw in-round events, tiered by tournament, without GRID's exclusive events.
- **Expected edge without the feed:** negative. Iteration 9 measured it on the validated engine: a continuous public
  ladder at the revealed others' best bid loses 1.9-3.2%, the same windows as the wallet's at the public anchor 2.3-4.5%.
- **Public-lag copying of its takes does not rescue it (iteration 10).** Re-executing each of its takes at its
  earliest public trace (the block of its own take, prices up to its limit plus 2c) refills only 22-34% of its shares,
  and combined with the public ladder the per-market result tracks the wallet at 0.33 / 0.21 at best. Its edge is the
  50-ms position in the feed's fan-out, which a replicator cannot buy on the open market (vendor unidentified).
- **No second venue substitutes (iteration 11).** SX Bet, the only on-chain in-play book for these events, had 63 CS2
  fills in a whole week, quoted 4c above Polymarket. The stale remainder a delayed copy would need is consumed by the
  wallet's own take (median residual 0 at its limit after the match), and a public maker cannot protect itself at a
  normal latency because the informed flow completes inside the 1-s in-play delay. The 10-31 build also changed its
  taker sizes (caps gone, median 129 shares) and merge timing, so any copy of its constants must be re-fitted on recent data.
- **Dota 2 only:** Valve publishes the spectator-clock game state key-free (4-s snapshots); the feed's Dota messages sit
  on that clock, so a replicator could in principle time Dota events from public data a few seconds behind the feed.
  Whether that is fast enough against the 1-s in-play delay is the pre-registered X118 test.

## Not explained yet

- **Iteration 16 account.** Price: V at the message for about 90% of its value changes (82-85% dark, 4-5% ahead of or inside the informed takers' delay; 5-6% follow a public trade); the messages are mostly round results (R favoured on clock-free counts and on the match-time clock), so the missing input is a real-time round-end source faster than the market, or the vendor feed itself (PandaScore token) and, for the uncensored ladder, the historical book (Telonex key). Outcome: unchanged (v6 0.197 / 0.027); no inventory cap from 20 to 600 shares lets a public ladder track the wallet. Selection: explained on VALIDATE; the post-T0 exit of P4e from the fan-out is a drift risk for gp72.

- **Iteration 15 account.** Price: V at the message; the messages are mostly round results with a small in-round part (R vs K not decided, weak clocks). Outcome: 0.197 / 0.027 for the frozen executable replay, 0.315 / 0.238 for the best public replay in the calldata engine; the wallet's exit policy does not change that. Selection: explained on VALIDATE; a small, drifting share of the operator's non-GRID events goes to 0x7d67f01d, which no listing field predicts out of fold with 20 cases.

- **Iteration 14 account.** Price: its value moves at the push feed's messages (a step within 0-3 s of the visible
  informed clusters, no private ramp before them), and only 12-18% of its re-pricings have a visible message in the
  3 s before; the other ~85% sit at messages no wallet-free take prints. The item tolerates no input lag (0.25 s costs
  60% of the set unit), so only the feed itself can carry it; own state transported across books reaches 0.44, the
  last print 0.31. Which message kinds move V (round results vs in-round kills / plants) needs a true round clock or
  demo kill ticks (consent). Outcome: a phase-gated public ladder stays at 0.25 / 0.05 (VALIDATE). The vendor: an
  esports-only push feed (the operator's sports account shows no fixed-lag reaction to official MLB plays).

- **Iteration 13 account.** Price: V to the cent. V is an in-round win-probability state (within-round drift toward
  the round winner AUC 0.90 vs the print's 0.68), one value per event on its map and match books, that leads other
  traders' executed prices (0.32 vs 0.15); its input is the push feed's in-round events, which its maker leg receives
  even when it does not take. No public source obtained reproduces it: three bookmakers' archived Dota lines (no closer
  than the print), EMA filters of prints (<= 0.30), public deltas on its own top (<= 0.46 through the machine), plus
  the iteration-12 list. Outcome: unchanged (bounded below 0.5 at public lag). The strategy's own history on the
  operator's earlier account (September-October) shows the same private value with the same feed position, so no
  feed-free period exists in the record from 09-26 on.

- **Iteration 12 account.** Price: one private number per burst (V) plus a mechanical ladder; with V known the ladder
  machine reaches 0.875 on the burst-set unit and 0.73 per order, so the item is gated by V alone, to the cent. V is not
  an MR12 round-score table (no closer to it than the print), not a map of public per-minute Dota state (0.17 vs the
  last print 0.42), not a sampled copy of public book changes (at most ~14 points of its on-tick re-pricings), and the
  best examinable historical anchor stays the last print (a point-in-time partial-fill book ties it). What moves V
  between ticks in about 85% of its quiet re-pricings has no public trace in the data obtained. Outcome: the stale
  remainder is gone by the informed leader's match even when the wallet does not take (3-7% of its typical take
  survives), so a public-lag rule cannot reach the item on the observed market. Open live tests: Thunderpick
  suspensions vs its event-wide withdrawals (median 12.5 s), the rounds-book clock, Valve Dota state at receive time,
  the Kick stream clock.

- **Iteration 11 account.** Price: no examinable anchor beats the last print (0.305; point-in-time own level 0.280,
  union 0.418); live, the touch 0.42 / 0.45 and every fresh-touch variant lower; SX Bet sparse and off its level; and
  even knowing its value, slot choice caps a per-order rule at about 0.71-0.75. Outcome: its own maker orders survive a
  2-s delay (0.70 / 0.62 with the real taker leg), the take does not (its own FAK empties the stale remainder; a public
  copy gets at most 0.50 / 0.41). The value V and the +50-ms take stay private.

- **Iteration 8 numbers.** The push feed has at least 19 fixed-lag subscribers (P4e first, the wallet +50 ms, a group at
  +100-230 ms, a slow group at +450-600 ms; every one also co-signs P4e-alone events at its lag). It is an esports product
  (CS2 and Dota 2 for the wallet and P4e; no fan-out in football / NBA / tennis) of raw in-round events (no shared value),
  tiered by tournament without GRID's exclusive events, and Polymarket's score socket is not it (16 s to minutes behind
  the market). 38.5% of the wallet's take clusters are co-signed by a subscriber in some market of the event (null
  0.4%); the other ~61% are its own (a stricter kind filter on the same feed, or a second input). Its signing key is its
  owner's and nobody else's. The maker's price re-anchors on the same private value (own-state rules at most 0.73 even
  as an oracle union), and public replays do not track its per-market PnL (-0.13 to +0.03).

- **The taker input.** It sits upstream of every public Polymarket feed on the events it acts on and covers only about
  a fifth of the informed bursts (plant-type, not round wins). Iteration 7: it is a shared push feed (>= 6 subscribers at
  fixed lags); the wallet's filter on it (kind, not edge) and the feed's origin are not public. The same input reaches
  its maker leg (untriggered pulls) about 2.6 times as often as it takes.
  - Whether it comes before the broadcast (server log / scout) or from the broadcast (CV) needs an event clock.
  - Chat clock (X38): pre-registered, recording from 11-01 06:00 UTC.
  - Twitch VOD chat (X53), bo3 demo ticks (X37) and HLTV page checks (X64) need the user.
- **The maker quote.** Its resting presence is not a public function (probe AUC 0.67), and the price is anchored
  within one tick only right after its takes.
- **Iteration 10 account.** Price: the best public anchor on the historical record is the last print (0.305 within
  one tick, VALIDATE), the best own-state anchor its previous level (0.500 fill-selected; 0.280 point-in-time, iteration 11), the touch on live adds 0.47; the offset
  from any public value (SD 6.0c) is not message phase (R^2 0.04), not a shared receiver value (ICC <= 0.43), not a
  faster maker's book move (event-locked), not public tape or game state. Outcome: reachable only with the +50-ms take
  timing (0.87 / 0.80 with it; at most 0.60 / 0.44 without it, executable <= 0.33 / 0.21). The only untested external
  candidate for the private value is an in-play bookmaker price (Thunderpick, recording).
- **The outcome target.** Its residual control depends on the private leg: the maker leg alone settles at 0.38 /
  0.34 against the target 0.5, an activity-only pseudo-PnL at 0.51 / 0.37.
