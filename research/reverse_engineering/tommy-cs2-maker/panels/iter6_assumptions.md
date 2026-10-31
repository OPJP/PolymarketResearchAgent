# Panel, iteration 6: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. Here that means four things: who else receives
the wallet's events, what the "Y1 rejected" test actually measured, whether the one passing component survives
outside 16-22 Oct, and the unit of the price decision.

## What I read and what I ran

I read `BRIEF.md`, `NOTES.md` (iterations 1-6, with the runbook), `state.json` (catalog through X86, components,
ledger), `FINAL_RULE.md`, the fifteen panel files of iterations 1-5, and `panels/iter6_mechanics.md` (written this
round). No EXAM or wall-audit files exist.

All checks are small passes over files already in `.cache/re/tommy-cs2-maker/` (`orders`, `calldata_all`,
`calldata_pub`, `pack_orders`, `census_bursts`, `per_market`, `events_sel`, `events_meta`, `universe`, the windowed
tapes, `calldata_taker`, `cooldown_pairs_dev`, `results/final_rule_v3_devblock.json`, `results/session_labels.json`).
There were two small network passes, both on development units:

- publicnode `eth_getTransactionByHash` for 329 historical transactions (16-22 Oct), to get their in-block order;
- data-api trades plus publicnode calldata for two untraded 10-31 12-18 dev-start markets (FOKUS-BakS game 2 and
  JJH-BMB game 1), the same markets `timer_owner.py` used, ending at 18:00.

I opened, listed and counted nothing sealed. Scripts are in
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`:
`racepair.py`, `p4disp.py`, `p4alone.py`, `p4block.py`, `p4ladder.py`, `p4cov.py`, `nearlag.py`, `c4clock.py`,
`sibsync.py`.

## Critique: assumptions that look false or unproven

### 1. "Its taker input is private, and the pack's round-win events come from a different source": the main pack member receives a share of the wallet's events at the same instant

The statement says the wallet's events come from a private feed that sits upstream of every public trace. It also
says "a different source [is] behind the pack's round-win events" (finding 21). The calldata says something else.
For every wallet taker order (1,698, 16-22 Oct), I looked for BUY taker orders on the same token signed within 300
ms, by pack signer:

| Signer | Pairs within ±300 ms | Offset to the wallet's signing (their stamp - its stamp), p10 / p25 / p50 / p75 / p90 ms | Reading |
| --- | --- | --- | --- |
| P4e 0x4ebc2722 | 218 | -97 / -72 / -51 / -32 / -11 | signs about 50 ms before it |
| 0x2005d16a (the rn1-inplay-maker wallet) | 66 | -46 / -31 / -16 / +31 / +114 | about 17 ms before it |
| 0xf1ee4842 | 47 | +66 / +89 / +113 / +160 / +173 | follower |
| 0x8a80528d | 53 | +55 / +146 / +158 / +184 / +228 | follower at a fixed ~157 ms |
| 0xddb6e624 | 42 | +52 / +144 / +156 / +168 / +260 | follower at a fixed ~157 ms |
| P93 0x93078b5d | 95 | +155 / +196 / +219 / +232 / +268 | follower |

The P4e co-signing is not noise:

- **Size and null.** P4e co-signs 200 of the 1,698 wallet takes (window [-120, +20] ms, same token). That is 12.3% of
  its take clusters, and 18.7% of its takes on tokens P4e trades. Shifting the wallet's times by ±30 s gives 0 and 2.
- **Stable over days.** Per-day median offsets are -47, -49, -54, -40, -49.5, -54.5 and -61 ms (10-16..10-22).
- **Stable over events, venues and leagues.** The per-event median has a between-event SD of 17 ms (25 events with 4
  or more co-signs). That is smaller than the mean within-event SD of 24 ms. By league: DraculaN -49 (61 co-signs),
  Stake Pulse -51 (41), 1win Private Club, offline in Serbia, -60 (35), PGL, online, -45 (33), Stake Ranked LAN -41
  (24). 0x2005d16a shows the same pattern at -8 to -34 ms, including Circuit X in Brazil (-17).
- **It does not need the wallet's public trace.** On P4e-active tokens it co-signs 18.7% of the takes where the
  wallet had no complement maker order signed in the previous 60 s (no ladder to pull, so nothing public to follow;
  761 takes). With such an order it co-signs 16.4% (353 takes).
- **Engine arrival is a coin flip.** In the 204 pairs, P4e's transaction lands in the same block in 165. Inside the
  block, its transaction index comes first in 95 and after in 70. Across blocks it is earlier in 13 and later in 26.
  So the two orders reach matching at about the same time, P4e first in 108 of 204.
- **P4e's own events are mostly its own.** Of its 4,012 BUY takes, 3,809 have no wallet co-sign. Their only frequent
  tight co-signer is 0x2005d16a (53 cases, median +22 ms).
- **The same universe.** P4e and 0x2005d16a avoid GRID events as the wallet does: 15 and 0 taker rows in 575 GRID-event
  tapes, against 8,556 and 2,717 in non-GRID ones. X15 already found P4e only in the wallet's whitelisted leagues.

What this means:

- **Several subscribers.** At least two other wallets act on about an eighth of the wallet's events at the same instant,
  within tens of ms. Two independent viewers of a stream cannot hold an offset that is constant to about 20 ms across
  events, LAN and online venues, platforms and days. HLS players differ by hundreds of ms and drift. The signature is a
  push message fanned out to several subscribers in a fixed order.
- **The wallet is not on its own.** The input is a shared feed product, or one relay, with at least three users. So
  the "wallet runs its own CV or watches a stream" branch (V2 of the X38 pre-registration) loses most of its support on
  data already in hand. A provider that itself works from streams is not excluded.
- **Not the only first.** "It signs first on its events" holds against public traces. It does not hold against other
  subscribers: P4e's stamp is earlier in nearly every co-sign (6 of the 218 pairs within ±300 ms fall at 0 to +50
  ms).
- **The pack is not one source.** P4e receives both kinds of event, its own round-win kind and the wallet's kind. So
  either one feed carries both kinds and the wallet uses only one (see critique 2), or P4e holds two feeds. The census
  "near" class (208 bursts) is mostly this co-signing: the wallet's signing sits at 0 ms (61) or 30-100 ms (89 of the
  other 147) after the burst's first signer. C2 noted "P4e -51 ms" in iteration 2. The consequence was never drawn.

### 2. "Y1 rejected" was measured on the maker module, which is downstream of the take

X78 / X83 reject Y1 ("a complete feed that declines to take") because its pulls at the pack's events are locked to
the public cancel wave. That test assumes the module that pulls the ladder sees the same feed as the module that
takes. The evidence says it does not:

- **The pull follows the order.** At its own takes the pull comes 11-19 ms after its own signing, never before it (IQR
  3 ms). A ladder fed by the event would be locked to the event and could pull at or before the signing. This one is
  locked to the take order: the take triggers the pull.
- **The ladder is uninformed between takes.** Outside the 30 s before a take, its maker orders see the next jump in
  their favour 41-42% of the time, the same as an uninformed maker (iteration 1).
- **No signature is expected.** A taker that declines leaves no zero-fill FAK and no pull-plus-1.04-s re-post, so "no
  zero-fill signature" (X46) cannot tell a decline from blindness.
- **The label may not be the wallet's.** The mechanics panel shows that the 100-share "own" label on 10-31 is about 27%
  other makers. Part of the "wave-locked pulls" may belong to others.

So X78 shows that the maker module does not see the pack's events. It says nothing about the taker module. Critique 1
makes the question concrete: P4e, a co-receiver, takes both kinds of event.

### 3. "Selection passes" rests on two VALIDATE days; the only forward development block gives recall 1 of 3

`results/final_rule_v3_devblock.json` scores frozen v3 (exam constants) on the 10-31 12-18 development block: 14 events
(8 GRID), 3 traded, AUC 0.758 against an activity baseline of 0.424, **recall 0.333** (1 of 3) at lift 4.67, gain p
0.128. NOTES never discusses it. Two traded leagues there, CyberClash and FiReSPORTS, were 0-traded in 16-22 Oct.

The exam lots point the same way:

- **Tier-5 lots.** Their non-GRID events are mostly tier 5: h1 62 of 100, h2 60 of 95. Tier 3 has 4 and 6 events.
- **Base rates.** In 16-22 Oct the wallet traded 5.6% of non-GRID tier-5 events (8 / 144), 51% of tier 4 (49 / 96)
  and 91% of tier 3 (20 / 22).
- **Daily PnL.** The dossier (context only) reports $43.7k for 17-29 Oct with every day positive, more per day than
  16-22 Oct. With few tier-3 events left, it must have traded tier-4/5 or new leagues on those days.
- **What fails.** A league table built on 16-22 Oct that falls back to a 6% tier-5 prior would miss them. That fails
  recall >= 0.5 on the exam, and possibly the replication item too (the per-day gain was already +0.034 / +0.094).

A schedule effect may add to this.

- **Start time.** Sessions begin at 08:04-08:10 UTC on five of seven days, the first in-play minutes of 08:00
  matches.
- **Early events.** All 11 non-GRID events that started before 08:00 UTC were skipped. Two were CIS LAN, a league it
  trades.
- **Clock changes.** EU clocks went back on 10-25, so every h1 / h2 day falls after the change. US clocks go back on
  11-01. If the start is tied to a local clock, events between 08:00 and 09:00 UTC change status on the exam days.

### 4. Smaller points and checks that came out negative (so nobody redoes them)

| Idea | Check | Result |
| --- | --- | --- |
| The wallet declines round wins because P4e beats it (competition form of Y1) | Wallet takes per traded market with vs without any P4e order | 7.8 (143 markets) vs 6.8 (86). The led share doubles without P4e (0.17 vs 0.08-0.10), but only through the denominator: P4e adds round-win bursts. Competition with P4e does not explain the absence. |
| Event-level hedging makes the per-market outcome unit wrong | Per-market residual (PnL - pairs x (1 - pair cost)) within events | var(event sum) / sum(var) = 1.27, match-vs-map residual corr +0.01 (149 pairs): no cross-market hedge, per-market is the right unit |
| Plant-type takes should show the 40-s bomb clock | Gap from led bursts to the next burst, 4-s bins | No mass at 36-44 s (4 + 1 of 157 same-team gaps). It neither supports nor kills "plants": the plant take may price the detonation in advance. |
| The 10-16 switch brought a new SDK | Salt / sign_ms and sigType, taker regime (11,692 orders) vs maker regime (25,878) | 0.503 vs 0.498, sigType 3 in both: same signing client, no SDK change |
| The "siblings" run the wallet's client | Salts of the 100-share 1.5-s-timer makers (FOKUS-BakS g2, JJH-BMB g1) | 0x2b55d2ee, 0x68915897, 0xca0b532d, 0xd3bd48ab: salts uniform up to 2^53 (log10 median 15.6-15.8, max 15.95; salt / sign_ms 2,400-3,550). Only the wallet and 0xd2bb9459 use round(U x Date.now()), and 0xd2bb9459 is not a 100-share ladder (7%). Different signing code: this supports the mechanics panel's point that part of "its" 1.5-s timer belongs to others. |
| The siblings are one process | Cross-wallet signing within 1 ms in those two markets | 0.048 vs a ±7-60 s shift null of 0.015, 4 of 268 shared ms stamps. Weak; co-reaction to the same book can produce it. |

## Proposals, ranked by the chance they close the gap

### P1. The input is a shared push feed: use its co-receivers as instruments (new; strong form of C2 / X65 / X38)

**Hypothesis.** The wallet's taker events reach it through a push feed that P4e, 0x2005d16a and probably 0x51dbdd2b
also receive. Messages fan out in a fixed order (P4e about 50 ms, 0x2005d16a about 17 ms before the wallet), and the
feed's coverage is the wallet's universe (non-GRID, whitelisted leagues). The subscribers differ in policy (which
event kinds they trade), not in information timing.

**Evidence.** Critique 1:

- 200 co-signs at -51 ms, IQR about 30 ms, null 0-2;
- a constant offset across days, leagues and LAN or online venues (between-event SD 17 ms);
- co-signing does not depend on the wallet having a public ladder to pull;
- engine arrival is a coin flip;
- the same GRID avoidance;
- 0x51dbdd2b cancels at the wallet's events 11-41 ms after its signing, before the public wave in 58% (finding 21).

**Test.** Runnable now on the history, then on the 11-01 06-12 block.

1. **Fan-out signature, historical (minutes).** Split the P4e and 0x2005d16a offsets by stream platform (Kick vs
   Twitch, Gamma `resolutionSource`), LAN vs online, match vs map leg, and game time. Fit a variance-components model:
   event, day and platform effects against residual. Repeat for 0x51dbdd2b's filled maker re-quotes after the wallet's
   takes, which `cosub_hist.py` already ranks at 100-500 ms. Pre-register the result now:
   - a shared push feed if the platform and event components are each under 15 ms and the platform difference is
     under 20 ms;
   - per-subscriber stream pipelines if either is 100 ms or more.
2. **Clock calibration, live.** On every development block, measure match minus sign for P4e's and 0x2005d16a's
   FAKs (server clock) as X27 did for the wallet. Then decide between two readings:
   - **Simultaneous.** P4e's clock runs about 50 ms early: the same instant, the same path length.
   - **Upstream.** P4e truly signs about 50 ms earlier but its order path is about 50 ms longer. Then it sits closer to
     the feed's origin than to the CLOB, and the wallet is the one co-located with the CLOB.

   Either reading keeps the shared feed. The second also locates the origin.
3. **What the feed carries.** Run the X50 / X58 per-map GLM on P4e's bursts split into co-signed with the wallet (203)
   and alone (3,809), on round wins and on bomb plants.
   - If P4e-alone bursts load on round wins only and co-signed ones on plants, the feed carries both kinds, P4e takes
     both, and the wallet takes one: a policy (go to P3).
   - If P4e-alone bursts also load on plants where the wallet is absent, the wallet's subscription or filter is
     narrower than P4e's.
4. **Coverage = selection.** In each league, the earliest date of P4e / 0x2005d16a activity and the share of their
   events with co-signing give a feed-coverage map. Compare it with the wallet's selection. This is a league-free,
   point-in-time feature (activity in previous days only) and the natural successor to X31's pack-lag variant, which
   scored 0.941 vs 0.914 on new leagues.
5. **Other titles.** Look for the same co-signing in the wallet's Dota 2 takes (72 orders) and in 0x2005d16a's public
   trades in other esports titles (polyrea adapters, development periods only; do not read the rn1 workspace). The
   same fan-out across titles means a multi-title data provider. Then the user can be asked for that provider's
   access (X55 PandaScore, whose match ids Gamma carries for exactly these events) with evidence instead of a guess.

**Data.** `orders`, `calldata_all`, `calldata_pub`, `pack_orders`, `events_meta` (platform), the census, bo3 rounds,
live calldata and books of 11-01 06-12 on, and 0x2005d16a's public trades for development periods.

**Signature if true.**

- Platform and event variance components under 15 ms.
- P4e's match minus sign is at least 1,040 ms (its path is not shorter than the wallet's).
- P4e-alone bursts load on both event kinds.
- The fan-out also shows in Dota 2.

If false, the offsets depend on platform or event by 100 ms or more, and P4e's co-signs are confined to events where
the wallet left a public trace.

**Why it closes the gap.** It turns "an unobserved private feed" into "a shared feed product with at least three
subscribers, whose coverage is the universe". That is falsifiable on the exam's future blocks, and the source becomes
identifiable and obtainable. It also settles the stream-or-upstream question that X37 / X38 / X53 wait on for user
consent, from data already in hand.

### P2. Out-of-time selection on every development block after T0, before the exam judges it (strong form of X84 / X61 / iteration-5 P5)

**Hypothesis.** The 16-22 Oct league table does not transfer. After 10-22 the wallet moved into leagues and tiers it
did not trade in 16-22 Oct (tier 4/5, CyberClash, FiReSPORTS). It may also run on a local-time schedule that shifted by
an hour on 10-25. Frozen v3 then fails recall >= 0.5 at lift >= 3 on the exam.

**Evidence.**

- The forward block scores recall 0.333 (1 of 3), AUC 0.758 (`final_rule_v3_devblock.json`), and NOTES never
  discusses it.
- Tier-5 events dominate the exam lots (62% and 63% of non-GRID events), and the wallet traded 5.6% of them in
  16-22 Oct.
- Daily profit continued on exam days (dossier, context only).
- Sessions start at 08:0x UTC, and the 11 earlier events were all skipped.

**Test.**

1. **Pre-register now (before 11-01 06-12 data exist)** a forward selection evaluation, pooled over every development
   block from T0 to the end of the budget (10-31 12-18, 11-01 06-12, and every later development block). Use the
   exam's thresholds: AUC, recall at the frozen threshold, lift, and the gain over activity with an event bootstrap.
   Score three rules with no refit:
   - frozen v3;
   - activity + GRID flag (X31, 0.930 on VALIDATE);
   - the league-free coverage variant (P1 step 4, or X31's pack lag).
2. **Switching rule.** Write it down now. If pooled forward recall for v3 is below 0.5 and a league-free variant is at
   or above 0.5 with a gain at or above 0.05, carry the variant into the exam. The forward blocks are development data,
   so this is a legitimate choice.
3. **Schedule.** On the first 06-12 development block after 11-01 (US clocks back), check:
   - whether the first wallet activity moves from 08:0x to 09:0x UTC;
   - whether 08:00-09:00 UTC events of traded leagues are skipped.

   If so, add the operator's local hour to selection as a listing-time feature, and note that every h1 / h2 day falls
   after the EU change.
4. **Exam-day parameters.** Through the allowed listing projection, check that h1 / h2 and the future-block markets
   carry the same `feeSchedule`, rebate share, `secondsDelay` and `clearBookOnStart` as 16-22 Oct. X1 checked only
   10-01..10-22. A change in the 1-s delay or the fees would change the whole taker mechanism on exam days.

**Data.** `events_meta` / `events_sel`, the listing projection of the exam lots (`exam_league_mix.py`), live
recordings and wallet activity of development blocks (dev-start units only).

**Signature if true.** Pooled forward recall of v3 below 0.5, with the missed traded events in leagues missing from
the table or in tier 5. A later session start after a clock change.

**Why it matters for the gap.** Selection is the only component that passes. If it fails on h1, nothing else can
carry item 2, and four exam rounds are a limited budget.

### P3. Re-open Y1 on the taker module: does it see the round-win events and decline them? (strong form of X78 / X83 / H62)

**Hypothesis.** The taker module receives the same feed as P4e, round wins included, and takes only "turns": events
against the last informed burst, which the faster subscribers' policies do not take. The maker module gets only
"I took" notifications (critique 2).

**Evidence.**

- The pull is locked to its own take order at +11-19 ms.
- Between takes the ladder is an uninformed maker's.
- A declining taker leaves no signature.
- The wave-follower label is partly other 100-share makers (mechanics panel).
- P4e, a co-receiver, takes both kinds of event (P1).
- My competition check (critique 4) is negative: P4e's presence does not change its take count.

So if it declines, the reason is the event kind, not the race.

**Test.**

1. **Event kind of the "near" class.** Near (208 bursts) and led bursts were pooled in the X58 GLM. Split them, and
   split near by co-signer (P4e or 0x2005d16a vs others). If near bursts with P4e load on round wins, the wallet acts
   on round-win events at the feed's instant: it sees them.
2. **Large-edge round-win bursts.** Take the P4e-alone bursts where edge was left after the pack's matching: P4e's FAK
   filled 100%, the price kept moving at least 5c in 10 s, and at least 100 stale shares were still at the old price
   after the match (tape and calldata). Measure the wallet's take rate in [P4e signing, +300 ms]:
   - Y2 (blind) predicts about 0 across hundreds of opportunities;
   - Y1 (policy) predicts a positive rate that rises with the edge left.
3. **Live.** On 11-01 06-12, with the own-level label validated by calldata (mechanics P1), score its taker leg, not
   its pulls, at pack events: any wallet FAK within 0-50 ms of a co-receiver's FAK on the server clock.

**Data.** census, `pack_orders`, `calldata_all` / `calldata_pub` (fills and the depth left), bo3 rounds, live
calldata and books.

**Signature if true.** Near-P4e bursts load on round wins, and the wallet takes some large-edge round-win bursts at
the feed's instant. If false: zero takes at large-edge round-win bursts, and near bursts load only on plants.

**Why it matters.** If Y1 holds, the 16-20% coverage is a decodable policy (the event kind, relative to the last
burst) over a feed whose clock P4e's signings reveal. The unexplained part shrinks to the feed's existence, and the
taker rule can be written as "kind x reversal x edge".

### P4. The price decision is a target ladder, and each order fills a hole in it (new unit of decision; own state)

**Hypothesis.** The wallet keeps a target set of levels on each token, {J, J - 1c, ..., J - (N - 1)c}, where J is the
join anchor under the pair cap. Each new order is priced at the highest level of that set it does not already occupy.
The price of an order is the set difference between target and own resting levels, not a function of the book alone.
Its own resting orders are legitimate state: it knows its book.

**Evidence.**

- 46% of bursts are single-level.
- 51% of timer re-posts land at the same price.
- Its own current top scores 0.453, above every book anchor (0.38-0.42).
- The ladder rule "J - k from the burst top" scores only 0.396 because most adds are refills, not new ladders from the
  top.
- No tested rule takes its own resting set as input (X75: own top, last removed level, K - L only).

**Test.** On BUILD-live (refit allowed) and then VALIDATE-live (frozen):

- Rebuild its resting set from the calldata-validated own-level label (mechanics P1).
- Fit N, which is 4-6 in the ladder decode, on BUILD-live.
- Predict each own add as the highest unoccupied level of the target set at sign - 100 ms, else J - N.
- Score it on every add and on filled orders, against join alone and against own top.

**Data.** `level_events` rebuilt with the validated label; `calldata_dev`; books from 11-01 on.

**Signature if true.** Within one tick at or above 0.7 on adds and filled orders, where join gives 0.38-0.42, and the
largest gain on single-level bursts. If false, no gain over own top (0.453), which would put the price ceiling in
writing.

**Limits.** h1 / h2 have no books, so this can only pass on future blocks. Say so in `FINAL_RULE.md`.

## Overlap with the ledger and earlier panels

- **P1 is new as a conclusion.** C2 recorded "P4e -51 ms" in iteration 2 as "a common trigger, not copying". No item
  treats P4e and 0x2005d16a as co-receivers of the wallet's feed. None tests the fan-out signature (variance by event
  and platform) or uses co-receivers for clock calibration, event kinds or coverage. It feeds X38 / X53 (stream or
  upstream) and X55 (provider) with in-hand evidence.
- **P2 extends X84 (listing mix) and X61 (sessions).** The forward-block recall and the clock-change schedule test are
  new, and so are the exam-day `secondsDelay` / fee checks: X1 covered only 10-01..10-22.
- **P3 challenges the X78 / X83 reasoning.** The taker-side tests (near class by co-signer, large-edge round-win
  bursts) are new. My P4e-competition check rules out one variant.
- **P4 is a new unit for X75 / X67.** It depends on the mechanics panel's P1 label fix.
- The salt check in critique 4 supports the mechanics panel's critique 1 and its P2 / P5 (client identity).

## How to reproduce my quick numbers

- `racepair.py`: per-signer offsets of BUY taker orders within ±300 ms of the wallet's takes on the same token; P4e
  co-sign counts per day; the ±30-s shift null.
- `p4disp.py`: per-event and per-league offset dispersion for P4e and 0x2005d16a.
- `p4alone.py`: co-signers of P4e's takes without the wallet.
- `p4block.py`: block and in-block transaction order of the 204 co-signed pairs (329 `eth_getTransactionByHash`).
- `p4ladder.py`: co-sign rate with vs without a recent complement maker order.
- `p4cov.py`: census shares and wallet takes per market by P4e presence.
- `nearlag.py`: the wallet's lag to the burst's first signer for the near and late classes.
- `c4clock.py`: gaps to the next burst (bomb-timer check).
- `sibsync.py`: sibling salts and cross-wallet co-timing (10-31 12-18 dev-start units only).
- The selection, tier and hour numbers come from `events_sel.parquet`, `results/final_rule_v3_devblock.json` and
  `results/session_labels.json`.
