# Panel, iteration 4: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. That covers the unit and target, survivorship in
the timing evidence, who else is informed, one operator or several, the selection labels, and where the PnL comes
from.

## What I read and what I ran

I read `BRIEF.md`, `NOTES.md` (iterations 1-4), `state.json` (hypotheses H1-H45, catalog through X52),
`FINAL_RULE.md`, the nine panel files of iterations 1-3, and the two iteration-4 panels already on disk
(`iter4_information.md`, `iter4_mechanics.md`), so that I do not repeat them. There are no EXAM or wall-audit files.

I ran inline, read-only checks on `.cache/re/tommy-cs2-maker/`: `calldata_all`, `calldata_pub`, `orders`,
`per_market`, `pack_orders`, `pack_clusters`, `events_sel`, `price_touch` and the tapes.

- All of it is development data from 16-22 Oct. BUILD and VALIDATE appear only as aggregates.
- I made one polyrea adapter fetch: 0x51dbdd2b's TRADE activity for 10-12..10-15, which is before H and so
  development data.
- I read no live recording and nothing sealed, and I wrote no file other than this one.

Definitions used below:

- **pack**: the 9 non-wallet signers in `pack_orders.parquet`.
- **retail**: takers with at most 20 taker transactions in the wallet's markets.
- **far**: more than 3 s from any wallet take signing in the same event.
- **in-play**: block time at least gs + 60 s.
- **markout**: the token's last print at +30 s / +120 s, with every transaction that contains a wallet order left out.

## Critique: assumptions that look false or unproven

### 1. "It signs before every public trace" is survivorship: it was measured only on events the wallet acted on

Every timing result (server-clock presign, round-market takers, X51, race rank) is anchored on the wallet's own takes.
Events where it was late or blind leave no take, so they never enter the sample. The matched-order record shows those
events exist, and that they are not rare: the pack hits the wallet's resting ladder far from any wallet take far more
often than the wallet takes.

| 16-22 Oct, in-play | Count |
| --- | --- |
| Wallet takes | 1,698 |
| Pack taker txs that fill a wallet maker order, far from any wallet take | 3,857 (2,647 bursts with 3-s gaps, 80 events) |
| Of those bursts, followed by a wallet take 3-10 s later / 10-30 s later | 3.6% / 7.0% (rough base rate 2-5%) |
| Pack clusters >= $100 without the wallet / with it (`pack_clusters`) | 1,507 / 476 |
| Clusters with the wallet where another pack signer signed first / where the wallet did | 280 / 196 (uncalibrated client clocks, so this is a lead only) |

The wallet's quotes do not dodge the pack. Its share of maker fill volume, in-play:

| Taker class | Far from its takes | Near (<= 3 s) |
| --- | --- | --- |
| pack | 9.5% | 6.1% |
| retail | 6.7% | 7.4% |
| other | 11.7% | 16.6% |

And the pack's fills are the adverse ones (all in-play fills by taker class, cents per share, share-weighted):

| | BUILD +30 s | BUILD +120 s | VALIDATE +30 s | VALIDATE +120 s |
| --- | --- | --- | --- | --- |
| pack | -0.02 | -1.00 | +0.52 | +0.35 |
| retail | +0.50 | +0.54 | +1.06 | +1.11 |
| other | +0.63 | +0.38 | +0.77 | +0.38 |

- At settlement (noisy, binary outcomes), its maker fills from far pack FAKs lose -7.3% (-$8.8k on $120k). Retail
  fills earn +2.2% (+$7.0k) and other fills +1.5% (+$5.6k), for a maker leg of about +$3.8k.
- 28% of its orders that the pack hits were signed after the pack signer signed, against 12-13% for the other classes.
  Some of this volume is re-posting into the delay window, and some is stale.

**Reading.** A feed that sits upstream of every public trace would also show the pack's events about 1 s before the
pack's FAKs match, and a bot that pulls its complement within 11-19 ms at its own takes would pull there too. The
mechanics panel finds the 829 no-take pulls non-directional.

So the wallet's input is not a superset of the pack's. Either it detects a subset of in-round events, or it is slower
than the pack on the events the pack trades (P4e follows round wins). "Upstream of every Polymarket feed" holds for
the events it acts on and has not been tested on the rest. This changes:

- the timing and exit components: at most of the pack's events it stays exposed;
- the economics: the ladder pays the pack roughly what the taker leg earns;
- which events X37 and X38 should clock.

### 2. The co-subscriber reading is thin, rests on an untested alternative, and covers only one of several informed makers

**The base is small.** "Another maker cancels between its signing and its own pull in 17-20% of takes" rests on 6-7 of
35 takes, and 4 of the 11 cancels come from one take transaction. Only 2 cancels are matched to 0x51dbdd2b.

**The alternative.** Nobody has tested whether a delayed taker order becomes visible in some way while it waits in the
1-s queue. If it does, cancels at +3 to +14 ms are reactions to the wallet's pending FAK, not to a shared source.

**0x51dbdd2b came first, not the wallet.** It is an established multi-game maker that was already in the wallet's
future universe:

- On 10-12..10-15 it has 6,755 TRADE rows: Dota 2 3,644, CS2 2,787, LoL 179, Valorant 145.
- It traded 45 CS2 events then: Stake Pulse 17, PGL 10, NODWIN 4, plus GRID events (Thunderpick WC 8, Elisa 3).
- The wallet moved into its universe on 10-16.

Its fingerprint:

- sigType 1 on all 5,785 orders; builder = metadata = 0;
- `Math.random() * Date.now()` salts, like the wallet;
- 91.5% whole cents (the wallet 99.6%);
- 22% SELLs (the wallet none).

The mechanics panel adds that its merge job is different.

**It is one of several avoiders.** I computed, per maker, the ratio of its presence in the wallet's FAK transactions to
its presence in other in-play FAK transactions (top 30 makers by presence):

| Maker | Ratio |
| --- | --- |
| 0xe40ecff6 | 0.05 |
| 0x2005d16a | 0.12 |
| 0x51dbdd2b | 0.16 |
| 0xed446954 (also the top late poster into the wallet's delay window) | 0.27 |
| next five | 0.41-0.49 |
| the rest | 0.75-5.1 |

Who sees the events is therefore a set of makers, and the investigation has profiled one of them.

### 3. The selection labels include hours when the bot was not running

- The maker regime starts on 10-16 at 13:38:34 UTC (first maker order).
- The 10-16 events before that hour are labelled as skips in BUILD:
  - nip-tl1 (Stake Pulse, $144.6k pre-game volume, the most popular non-GRID event of the week);
  - fnc-hero (Stake Pulse);
  - ef1-bca (PGL);
  - brute-wal2 and bw-rustec (NODWIN).
- On Sunday 10-18 it was active only from 14:00 to 16:45. All 4 of the day's events in traded leagues that fall outside
  that window were skipped.
- **Non-circular check.** For the 133 non-GRID events in the 8 leagues it trades, count the wallet's orders in other
  markets in [gs, gs + 1 h]. In 17 events it was not active anywhere; 10 of those are skips, all in BUILD (6 of them popular, pre-game volume above $1k).
  About 17% of the skips in its own leagues are probably downtime, not decisions.
- These labels feed the BUILD league-rate constants for Stake Pulse, PGL and NODWIN.
- h1 contains Sunday 10-25, and the frozen rule cannot see downtime. Features built from the wallet's own activity are
  banned, rightly.

### 4. Smaller points

- **Outcome "executable".** The brief's executable return carries latency >= 2 s and `match_slack = 2`. The
  iteration-5 plan, a live-book replay with pulls at the cancel wave, needs sub-second reactions. Settle with the
  examiner whether the per-market correlation in target item 5 is scored on a 2-s-latency rule before building it.
- **The taker leg pools two size classes with different economics.**
  - Caps of 1000 / 2000 shares: 391 orders, median fill 5.2%, settlement +0.3%.
  - Odd sizes: 1,307 orders, median fill 15.3%, settlement +4.3%.
  - The cap share is 52% on 10-17 and 14-17% on 10-21/22.
  - The premium dose-response (H36), X50 and any feed label built from takes pool both.
- **Facts I agree with and do not repeat.** The iteration-4 mechanics panel already shows three things:
  - the maker-only pair cost equals the overall 0.978;
  - the ceilings of exact copies;
  - the no-take pulls are not directional.

## Proposals, ranked by the chance they close the gap

### P1. A survivorship-free event census: map the feed by the events it misses (new)

- **Hypothesis.** The wallet's input covers a subset of in-round events, or is slower than the pack on some of them. At
  the pack's events it stays exposed and is picked off. The class of events it leads, against the class it misses,
  identifies the feed: a complete server-log feed misses nothing, while a narrow detector or a slower provider misses a
  whole event type.
- **Why it fits.** Critique 1:
  - 2,647 far pack bursts hit its ladder, against 1,698 takes;
  - its fill share in pack FAKs is not lower than in retail flow;
  - the pack's fills are adverse;
  - its no-take pulls are not directional;
  - P4e follows round wins, while the wallet is side-neutral with a weak bomb-plant lean.
- **Test.**
  1. **Event list** (16-22 Oct; explore on BUILD, report on VALIDATE).
     - Source: the full matched-order record (`calldata_all` plus `calldata_pub`).
     - Bursts: in-play BUY signings on one team, within 1 s, by informed signers (pack, wallet and the P2 avoiders),
       followed by a move of at least 3c on that team at +10 s.
     - Label each burst wallet-led, wallet-late (its signing comes after the first other informed signer, within 30
       s) or wallet-absent.
     - Historical client clocks are uncalibrated. Use the dev-block per-signer offsets (X27), or call a burst led only
       when the gap exceeds 200 ms.
  2. **Exposure in wallet-absent bursts.**
     - Its orders on the losing token that rested before the first signing and filled inside the burst's
       transactions (stale hits), against orders posted inside the delay window.
     - Their markouts at 10 / 30 / 120 s, and the share of bursts in which it was exposed and hit.
  3. **Event type, clock-free** (the X50 recipe). A binomial GLM with map fixed effects of wallet-led and of
     wallet-absent burst counts per team, on the bo3 per-round items: round wins, plants, opening kills, clutches,
     kills.
  4. **Live, on the server clock** (10-31 14:50-18:00, then 11-01 06-12). At pack-led events, where the first informed
     signer is a pack wallet (calibrated as match - 1,040 ms), what happens to the wallet's own exposed ladder?
     - It cancels before the pack signs.
     - It cancels within 150 ms of the public cancel wave (a book reader).
     - It is hit at +1.04 s.

     Does it also take later?
- **Data.** Files already on disk (`calldata_*`, tapes, `pack_orders`, `bo3_*`), `tommy_cs2_near` and `calldata_dev`.
- **Signature if true.**
  - Wallet-absent bursts are a large share of the events with a 3c+ move (30% or more).
  - It is hit stale in most of them, at markouts below retail.
  - The two burst classes load on different bo3 items, for example the pack's on round wins and the wallet's on
    mid-round items.
  - Live, it does not cancel before the pack.

  The decode then states the event class it detects and its share. The maker exit becomes "pull only at its own
  signal; stay exposed to the rest", with the rest's cost measured. X37 / X38 should clock both classes, because the
  gap between them dates the feed.
- **Signature if false.**
  - Wallet-led in 90% or more of the bursts with a 3c+ move.
  - Its exposed fills in the rest are no worse than retail.
  - "Upstream of everything" then holds generally and can go in the wall account.

### P2. Who else is informed: an avoidance census, operator tests, and the delay-queue leak control (strong form of X49 / H45 / C1 / C3)

- **Hypothesis.** One of three readings holds:
  - (a) several independent makers subscribe to one vendor, whose coverage is the wallet's selection;
  - (b) some of them are the same operator;
  - (c) the fast cancels at +3-14 ms react to the wallet's pending FAK through a leak in the 1-s queue, with no shared
    source at all.
- **Why it fits.** Critique 2:
  - the base is 6-7 takes;
  - nobody has tested the leak;
  - there are four makers with ratios of 0.05-0.27;
  - 0x51dbdd2b predates the wallet in these leagues.
- **Test.**
  1. **Census** (development data).
     - For every maker present in at least 1% of in-play other-taker transactions, compute the ratio r from critique
       2, per event, with an event bootstrap.
     - Use only other FAKs more than 3 s from the wallet's takes, so that the re-pair window does not inflate it.
     - For the set with r < 0.3, list sigType and signer (calldata), and their CS2 coverage (GRID, non-GRID, by
       league) and other games before and after 10-16.
     - Add per-league entry dates from data-api activity before H. The information panel's P5 (date the feed by
       co-subscribers) can use the same pull.
  2. **Same process or not** (live, server clock). For takes with both an own pull and a cancel by a low-r maker,
     compute Δ = their cancel - the wallet's first own pull cancel.
     - A shared client gives |Δ| <= 3 ms, with latencies correlated across takes.
     - An independent subscriber gives a wide, uncorrelated Δ.
     - Add funding: pUSD / USDC.e Transfer logs into each proxy (`eth_getLogs`, topic2) and their sources.
  3. **Leak control** (live). Count cancels by non-wallet makers in [a, a + 15 ms]. Here a is the arrival of a delayed
     taker order in the queue: its server match time minus 1,000-1,040 ms, using the per-signer calibration.
     - Do it separately for the wallet's takes, the pack's, and retail takers' (small orders more than 3 s from any
       informed burst).
     - Take the base rate from random 15-ms windows on the same side.
- **Data.** `calldata_*`, data-api activity, Polygon logs, `tommy_cs2_near` and `calldata_dev`. Development only.
- **Signature, by reading.**
  - (c) leak: the cancel rate is also raised after retail arrivals. The shared-source claim is withdrawn, the wallet is
    the only fast informed actor, and the event clock is the single decisive test.
  - (a) shared vendor: the rate is raised only for informed arrivals, and the low-r makers share the wallet's
    non-GRID coverage. The selection is that vendor's coverage. Join it through `pandascoreMatchId` (information panel
    P3), and test Oddin.gg too: it holds PGL's data rights, and PGL is traded 9 of 13.
  - (b) same operator: a shared funder, or |Δ| <= 3 ms. Model selection and maker price at the operator level, for
    example the wallet's top against the sibling's resting top on the live book.

### P3. One valuation, two legs: is the maker top the bot's model value minus a half-spread? (competitor to the mechanics panel's P4)

- **Hypothesis.** The ladder is centred on the same private valuation V that sets its FAK limit, with
  top_Y = K - V_X and top_X = V_X - c. V tracks the public mid in quiet periods and jumps at its own events.

  This explains three things:
  - why no public anchor passes 0.53 even on the live book;
  - why a tape copy pays 1.005;
  - the -3/-4c group of ladder tops.
- **Why it fits.**
  - Re-post top plus FAK limit has its mode at 0.95-0.96, within 1c in 54-65%.
  - Its re-posts after takes come 3-8c lower.
  - The premium is a private valuation (H36).
  - 81% of its filled maker orders are the top of their burst, and 93% are within 1c of the top. The ladder depth is
    not why price fails; the anchor of the top is.
  - Its filled tops sit at the last print minus a median 1c, but 6c or more below it in a quarter of orders (q - last
    p10 / p25 / p50 / p75 / p90: -0.09 to -0.10 / -0.06 / -0.01 / +0.01 / +0.04).
- **Test.**
  1. **On calldata only, scorable on h1 / h2.** Own state is reported separately. After each own take on X at limit L,
     predict its next maker tops: top_Y = K - L (K fitted on BUILD) and top_X = L - c.
     - Report the within-one-tick share on VALIDATE by time since the take (0-1.04 s, 1.04-5 s, 5-30 s, 30-120 s,
       over 120 s), against the last print and the rebuilt touch in the same windows.
     - Report the time over which the rule decays.
  2. **Live, on the full resting ladder by fingerprint** (not only filled orders).
     - Compute the implied mid m_W = (top_X + 1 - top_Y) / 2 and the implied spread 1 - top_X - top_Y.
     - Regress the 5-s and 30-s change of the others'-book mid on (m_W - mid).
     - Control: the same statistic for every other maker quoting both tokens in the same markets.
     - Leave out the 3 s after its takes.
  3. **Competitor.** Fit the mechanics panel's hysteresis band on others' book to the same changes.
- **Data.** `orders`, `calldata_all`, tapes, `tommy_cs2_near`, `level_events_dev`.
- **Signature if true.**
  - m_W leads the mid beyond the control.
  - The implied spread is stable.
  - K - L beats the public anchors for tens of seconds after takes.

  The maker price is then decoded as "model value minus half-spread, with the value revealed by its FAK limits"
  (VALIDATE-only). The h1-scorable part is the post-take window, and the rest goes into the wall account with its size.
- **Signature if false.** No lead, and the band explains the offsets: the price is a public placement rule, and its
  live-book fit is the iteration-5 work.

### P4. Session-clean selection labels and the exam-day downtime risk (new; the one passing component)

- **Hypothesis.** Part of the "skips" are hours when the bot was off: the switch afternoon, Sunday 10-18, and gaps.
  This biases the BUILD league rates, and a down day in h1 could break recall or the gain even with a correct rule.
- **Why it fits.** Critique 3: 10 of the 58 skips in its own leagues fall where it had no orders anywhere in
  [gs, gs + 1 h], all of them in BUILD. Among them is nip-tl1, at $144.6k.
- **Test.**
  1. Rebuild daily operating windows from its orders in all markets, Dota 2 included:
     - 10-16 13:38-18:51;
     - 10-17 08:05-20:17 (gap 16:43-17:22);
     - 10-18 14:00-16:45;
     - 10-19 08:04-21:56;
     - 10-20 09:01-20:11;
     - 10-21 08:04-23:26;
     - 10-22 08:10-23:15 (gap 10:01-11:00).
  2. Refit the frozen recipe with BUILD restricted to units after the switch and inside those windows. This is label
     cleaning at a version and operations boundary, never a feature. Report:
     - the league rates (Stake Pulse, PGL, NODWIN);
     - the VALIDATE metrics on all units (as the examiner will) and on in-session units;
     - the within-non-GRID AUC against activity alone (0.904).
  3. **Sensitivity.** Recompute VALIDATE recall, lift and the gain CI if one day had a 10-18-like 3-hour window.
  4. **C5 on the development days.** Session starts on 10-31 (Saturday) and in the 11-01 06-12 block (Sunday). Is
     there a fixed weekly schedule (a frozen constant), or manual starts by a human operator?
- **Data.** `orders`, `events_sel`, `final_rule.py`, `calldata_dev`.
- **Signature if true.** The league constants move, the within-non-GRID AUC rises above 0.904, and per-day gains
  stabilize. A regular schedule becomes a constant of the rule. An irregular one is reported as an unexplained selection
  component, with its expected cost on a lot.

### P5. Split the taker leg by size class before using it as the feed's label (pooling of sub-policies)

- **Hypothesis.** The 1000 / 2000-share FAKs (23% of takes) are a different sub-policy or an older version: a
  fixed-size probe, or an event class that does not reprice. They dilute every take-based inference.
- **Why it fits.**
  - Cap orders fill a median 5.2% and earn about +0.3% at settlement, against 15.3% and +4.3% for odd sizes.
  - The cap share falls from 52% (10-17) to 14-17% (10-21/22), and is 0% on the dev block (X35).
- **Test.** Re-run, separately for caps and odd sizes and by day:
  - H36 (Spearman and OLS of the move on the premium);
  - the next-jump win rate;
  - markouts at 10 / 60 s;
  - X50's per-map GLM.

  Run a change-point test on the daily cap share.
- **Data.** `orders`, `premium_value.py` inputs, tapes, `bo3_*`.
- **Signature if true.** Caps show no premium-move relation and no edge. Use odd-size takes, or the pulls, as the feed
  label in P1, X50 and the clock tests, and date the version boundary.
