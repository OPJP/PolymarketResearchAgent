# Panel, iteration 2: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. That covers the unit of decision, censoring,
pooled versions, the metric and its baseline, and where the PnL comes from.

## What I read and what I ran

I read `BRIEF.md`, `NOTES.md`, `state.json`, `FINAL_RULE.md`, the three iteration-1 panels and the dossier
verdict. I then ran small read-only checks on `.cache/re/tommy-cs2-maker/`:

- `orders.parquet`, `calldata_pub/`, `calldata_taker/`, `activity_taker.parquet`;
- `per_market.parquet`, `events_sel.parquet`, `collapse_events_dev.parquet`, `pack_orders.parquet`.

Data scope:

- The selection numbers are fitted on BUILD and scored on VALIDATE.
- All other numbers pool development data from before H, or come from the 10-31 12-18 UTC development block
  (`collapse_events_dev`). They are exploratory.
- Nothing sealed was read, and I fetched nothing.

The scripts are in my scratchpad:
`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`
(`tick_check.py`, `sib.py`, `first.py`, `presign.py`, `packmk.py`, `selgrid.py`, `listing.py`).

## Critique: assumptions that look false

### 1. "It acts on 4-8% of collapses" measures filled orders, not decisions

A FAK order that finds nothing to fill leaves no trace: there is no on-chain fill and no book entry. Every
taker order the investigation sees therefore had at least one fill, and the evidence says many attempts had
none.

- **Fill fractions pile up near zero.** Of its 1,698 taker orders (16-22 Oct), 34% filled less than 5% of their
  size, 20% filled 10 shares or fewer, and 9% filled 5 shares or fewer (the minimum order size). The density
  keeps rising toward zero, so many orders that filled nothing are missing from the record.
- **The live order sizes point the same way.** On live books the order size is a cap above the stale depth
  (size/depth median 1.22).
- **The wallet and the pack act on the same collapses far more often than chance** (`collapse_events_dev`,
  797 collapses):

  | Collapses | Wallet acted |
  | --- | --- |
  | Where the pack acted (21) | 5 (24%) |
  | All others (776) | 23 (3%) |

  This fits one shared trigger plus a race for a few stale shares, where the loser's FAK fills nothing and
  disappears from the record.

So the precision (3.7%) and the "which collapses it acts on" filter are partly the outcome of that race. A
filter frozen on 28 filled orders from one block would encode one block's race outcomes.

### 2. The selection gain is the GRID flag; the league rate adds almost nothing

I refitted on BUILD and scored on VALIDATE:

| Model | VALIDATE AUC |
| --- | --- |
| Pre-game activity only | 0.890 |
| Activity + GRID flag | **0.943** |
| Frozen rule (adds the league rate) | 0.954 |

Within the 91 non-GRID VALIDATE events (36 traded):

| Model | AUC |
| --- | --- |
| Activity only | 0.904 |
| Activity + shrunk league rate | 0.907 |
| League rate alone | 0.835 |

What this means:

- The gain over the baseline comes from moving popular GRID events to zero. Its size depends on how many popular
  GRID events a lot contains. That explains the per-day swing (+0.034 vs +0.094) better than league turnover
  does.
- The decode is missing the choice inside non-GRID events:
  - ESEA 0 of 13 on VALIDATE (28 of its 37 non-GRID events in 16-22 Oct resolve to hltv.org, i.e. have no
    stream channel);
  - Exort Fiesta 0 of 11, ESL Challenger 0 of 6, CyberClash 0 of 8 (but traded on 10-31);
  - DraculaN's four Kick channels: draculancsd 2 of 11 against draculancsb 7 of 14 and draculancsc 7 of 11.
- 27 of the 128 VALIDATE events (8 of the 36 positives) are in leagues not seen in BUILD.

### 3. The unit of the taker decision is the game event, not one market's book

- 60 pairs of taker orders (120 orders, 7% of all taker orders, in 29 events, on every day from 10-16 to 10-22)
  sit in a map market and the match market of the same event.
- They are signed 0-38 ms apart (median 1 ms), always for the same outcome index. In 49 of the 60 pairs the map
  order comes first.
- A rule that reads each book separately cannot fire in two markets within 1 ms unless both books cross the
  threshold in the same message.
- Only pairs in which both legs filled are visible, so the true rate of firing in both markets is higher.
  Match-market orders are 760 of the 1,698.

### 4. The 0.001 tick is the post-hoc Gamma field; in play the tick is 0.01

The brief lists the current tick size as a post-hoc field. Gamma's 0.001 is what a resolved market shows.

- In 219 of the 220 traded markets, the first sub-cent maker order (in all public calldata) has a median price of
  0.999, i.e. it appears when a map is decided.
- 85.8% of the wallet's mid-range orders (0.04-0.96) come before any sub-cent order in their market.

Consequences:

- **The C8 fingerprint "whole cents although the tick is 0.001" is mostly empty.**
- **`price_within_tick` = 0.115 is an exact-match rate, not "within one tick".** Within 1c the figures are 0.305
  for the last print (`price_touch.json`), 0.41 for the rebuilt touch, and 0.56 for the live best bid.
- **There is one real fingerprint.** After the tick drops to 0.001, other makers' mid-range orders are sub-cent
  36% of the time, while the wallet's are sub-cent in 0 of 3,672. It hard-codes a 0.01 tick.

### 5. Per-market PnL is mostly the locked pair margin

From `per_market.parquet` (229 markets), with locked = pairs x (1 - pair cost):

- It correlates with per-market PnL at Pearson 0.84 and Spearman 0.70. It carries a variance of 40.8k of the
  PnL's 50.2k.
- The residual correlates at 0.45 / 0.37.

So an outcome replay should first reproduce the per-market pair margin. That margin depends on when its bids on
each side get hit, not on the trigger. The replays tried so far use a 10-s requote at the last print minus delta,
which is not the wallet's rule (join the bid, re-sign at the public match + 1 s, never pull).

### 6. Quick checks that came out negative or confirmed earlier findings, so nobody redoes them

- **The taker regime really used pre-signed orders; the delay was not in settlement.** 6,289 transactions from
  10-01..10-15 have signing-to-block above 20 s. In 90.6% of them the newest counterparty maker order was signed
  more than 5 s after the wallet's timestamp (median 69 s), and the block came a median 3.4 s after that newest
  maker order. In 24% of consecutive transactions the wallet's orders settle in reverse signing order. This is a
  pool of pre-signed FAK orders fired later.
- **Selection is decided before the game, not in reaction to the pack.**
  - The wallet's first order per event comes a median 0.95 min after the scheduled start (p25 -8.3 min, p10
    -22.9 min).
  - That is a median 260 s before the pack's first in-play order.
  - In at least 25% of traded events its first fill is more than 5.9 min before the start, so "from game start"
    is not exact.
- **Its event list is not loaded once at start-up.** In whitelisted leagues, non-GRID events listed after the
  wallet's first order of the day are traded 21 of 42 times, against 56 of 107 for events listed before.
- **0x4ebc2722 never posts maker orders** (0 maker orders in the 220 markets), so it cannot be the maker that
  cancels. By contrast, 0x2005d16a is both the third-largest maker (4.9% of maker USD) and a pack taker.
- **State file hygiene.** `state.json` `hypotheses` repeats H11-H16 about ten times (the `write_state` scripts
  append rather than replace).

## Proposals, ranked by the chance they close the gap

### P1. Treat the taker unit as an attempt censored by a fill race, and decode it on attempts

- **Hypothesis.** The wallet sends a FAK on nearly every qualifying collapse (deep, and the team's ask not
  falling). Only the attempts that win some stale depth after the 1-s delay are visible. The 4-8% acting rate
  and much of the "acting filter" come from that race, which the pack often wins. They are not the wallet's
  choice.
- **Why it fits.**
  - Critique 1: fill fractions pile up near zero; the size is a cap above the depth; the wallet acts on 24% of
    pack-acted collapses against 3% of the rest.
  - Acted collapses keep a stale best ask (59% vs 38%), which is exactly what a FAK needs in order to fill.
- **Test** (development blocks only: `tommy_cs2_near`, with `clob_wallets` as fallback; units filtered by game
  start).
  - For each collapse at time t_c, take the hypothetical arrival time t_a = t_c + 0.77 s + 1.0 s.
  - From the book and the last trades, classify the asks at or below ask_before + 2c that rested at signing time
    (t_c + 0.77 s):
    - (i) still resting at t_a, untouched;
    - (ii) consumed by other takers' trades in [t_c, t_a] (record who);
    - (iii) cancelled before t_a.
  - Report P(wallet acted | i) against P(wallet acted | ii or iii), stratified by depth left and by the move in
    the best ask.
  - Repeat for the pack's addresses.
  - Then refit the acting filter only on the collapses in (i). Those are the only ones where "did not act" is
    observable.
- **Data.** Recorded books and trades from the development blocks (10-31 12-18 so far, then the live VALIDATE
  blocks from 11-01 18:00), and the calldata of every taker transaction in those markets (`dev_calldata.py`).
- **Signature if true.**
  - P(acted | i) is high (0.5 or more), and almost all good collapses it skipped fall in (ii) or (iii).
  - The frozen trigger becomes "fire on every qualifying collapse, whose side is the team whose asks
    vanished", with the race described separately.
  - Precision and the taker presence AUC rise on the live VALIDATE blocks, and the filter stops shifting from
    block to block.
- **Signature if false.** P(acted | i) stays near 5%. Then there is a real selection variable (round phase,
  price level, inventory, which maker cancelled; see P5), and it has to be found on (i) alone.

### P2. Recast selection as "GRID boundary + popularity" and decode the choice inside non-GRID events (and check whether that label is censored too)

- **Hypothesis.** The selection decode is complete except inside non-GRID events. There, two things are
  possible:
  - (a) a second data-coverage boundary exists that the current rule does not see. Candidates: leagues on
    FACEIT servers (ESEA, ESL Challenger), events with no stream (hltv.org source), and the concurrency of
    parallel streams inside one league (DraculaN a/b/c/d);
  - (b) the wallet quotes in every whitelisted non-GRID event, and "popularity" only decides whether a taker
    ever fills it. In that case the activity baseline wins by co-occurrence, and the real decision is a list.
- **Why it fits.**
  - Critique 2: the GRID flag carries +0.053 of the +0.064 gain; the league rate adds +0.003 inside non-GRID
    events.
  - ESEA 0 of 13, Exort 0 of 11, ESL Challenger 0 of 6; DraculaN-d 2 of 11 against b/c 7 of 14 and 7 of 11.
  - The per-day swing in the gain matches how many GRID events each day has.
- **Test.**
  - (1) Freeze activity + GRID flag as the selection rule, dropping the league rate, and report it beside the
    frozen v2.
  - (2) Estimate replication risk from listings only.
    - Count the GRID and non-GRID events per pseudo-half of the dev split, and the activity rank of the GRID
      events, then regress the gain on them.
    - For h1/h2 use only the listing projection (event counts, GRID id, league, start). Read no tapes of sealed
      units.
  - (3) Inside non-GRID events, test listing-time candidates:
    - organiser or server platform (FACEIT-run leagues);
    - resolution source of hltv.org versus a stream;
    - number of concurrent matches in the same league at game start, and the event's rank among them;
    - stream platform and channel.
    Score each with the event bootstrap against activity alone.
  - (4) For (b): on the own recorder (10-31 onward, development blocks), look for the wallet's quotes in the
    books of untraded non-GRID events. The signature is 100-share level changes at whole cents that join the best
    bid on both tokens at the same moment.
    - Use the wallet's traded markets as the positive control (where its fills confirm the detector) and GRID
      markets as the negative control.
- **Data.** `events_sel` / `events_meta` (on disk), the listing projection for later lots, and `tommy_cs2_near`.
- **Signature if true.**
  - (a) A listing-time field separates ESEA, ESL Challenger and Exort (and DraculaN-d) from the traded events,
    with a gain of at least 0.02 inside non-GRID events.
  - (b) Its quote signature appears in untraded non-GRID events at about the rate seen in traded ones, and
    stays near zero in GRID markets. Selection is then a list, and the fill-based AUC is capped by
    co-occurrence. Say so in `FINAL_RULE.md`.

### P3. Make the taker unit (event, team, time); separate a book reader from a game-feed reader with fan-out legs

- **Hypothesis.** One internal event signal produces orders in the map market and in the match market of the
  same event within a few milliseconds.
  - The match-market leg either has no collapse of its own (cross-market propagation from the map, or a game
    feed), or its collapse arrives in the same websocket frame.
  - The 24% of CS2 taker orders without a collapse of their own in the 2 s before may largely be such legs.
- **Why it fits.** Critique 3: 60 pairs signed a median 1 ms apart, always for the same outcome index, 49 of 60
  with the map order first. Only the pairs where both legs filled are visible.
- **Test.**
  - (1) On the development-block books, for every wallet taker order record:
    - whether its own market had a collapse;
    - whether the other live markets of the same event had one for the same team, and when.
  - (2) Look specifically at the 4 orders signed before any collapse and the 17 with none: are they fan-out
    legs?
  - (3) Rebuild the presence target on (event, team, 0.5-s) bins with "a collapse in any market of the event",
    and compare its AUC with the per-market version.
  - (4) In 16-22 Oct (tapes), compare the match-market price path before the fan-out legs with the map market's.
- **Data.** Recorded books (development blocks), `orders.parquet`, and the windowed tapes.
- **Signature if true.**
  - The match-market legs follow a map-market collapse by 0.3-1.0 s while their own book is quiet.
  - Recall rises from 76% toward 90% or more, and the event-level presence AUC exceeds the per-market one.
  - This is also the cleanest discriminator so far between a book reader and a feed reader:
    - fan-out legs fired while every book of the event is quiet mean a game feed;
    - legs that always trail a collapse in a sibling mean a cross-market book reader.

### P4. Fix the price metric to the in-play tick, then decode the ladder on unfilled levels

- **Hypothesis.** The price component is judged on the wrong tick. With the in-play tick of 0.01, "within one
  tick" is within 1c: 0.31 for the last print, 0.41 for the rebuilt touch, 0.56 for the live bid. The gap to 80%
  is then the ladder depth: levels 1-5c below the bid.
  - A rule "join the bid with k levels 1c apart, whole cents even when the tick is 0.001" can be scored per
    order once k and the requote cadence are known from unfilled levels.
- **Why it fits.**
  - Critique 4: first sub-cent orders at 0.999; 85.8% of its orders come before any sub-cent order; 0 sub-cent
    orders of its own after the tick change, against 36% for others.
- **Test.**
  - (1) Recompute `price_within_tick` per order with the tick in force at signing. Historically that tick is
    0.01 until the first sub-cent order in the market; live, use the recorder's `tick_size_change` messages.
    Report it against all three anchors on VALIDATE.
  - (2) From `tommy_cs2_near`, count the wallet's 100-share whole-cent levels per token, filled or not, relative
    to the best bid, together with their lifetimes and requote times.
  - (3) Score "join the bid plus k levels" per order: the order's price is predicted correctly when it lies within
    one tick of one of the rule's levels at signing. Report the trivial anchors next to it, as the brief requires.
- **Data.** `orders.parquet`, `calldata_pub/`, and `tommy_cs2_near` (development blocks).
- **Signature if true.** `price_within_tick` reported honestly at about 0.4-0.56 (not 0.115), and a fixed ladder
  depth with a stable level-share profile. A k-level rule then covers 80% or more of the orders at signing on
  live books. On h1/h2, the price claim stays limited to the touch rebuilt from calldata.

### P5. The cancels belong to identifiable makers; test the strong form of copying through their cancels

- **Hypothesis.** The collapses it acts on are the pulls of one or two specific fast makers. The wallet follows
  those makers' cancels (C2 through cancels, not through prints), and their presence in an event is also part of
  its selection.
- **Why it fits.**
  - 0x4ebc2722 never makes, so it is not the canceller.
  - 0x2005d16a is both the third-largest maker in its markets (4.9% of maker USD) and a pack taker, which is the
    profile of a maker that pulls stale asks and then takes.
  - The largest makers, 0xe40ecff6 (7.6%) and 0xed446954 (7.4%), are candidates too.
  - The lost depth is not in the wallet's own 100-share units.
- **Test** (development blocks).
  - Attribute the lost levels in each collapse window [-1.5, 0] s to makers by two methods:
    - (a) size matching: match level decrements against the original sizes of each maker's orders on that token,
      from the calldata of fills within ±10 min. Control: the same matching shifted by random times;
    - (b) "stopped filling": a maker whose orders at that level filled in the minute before and never again at
      that price.
  - Compare the mix of cancelling makers between acted and non-acted collapses. Restrict the comparison to
    class (i) from P1, so that the fill race does not mix in.
  - If one maker dominates, test that maker's lagged presence as a maker in a league's earlier events as a
    point-in-time selection feature.
- **Data.** Recorded books, and the calldata of every taker transaction in those markets.
- **Signature if true.** P(acted | maker M pulled) is much larger than P(acted | others pulled), the precision of
  the trigger rises severalfold, and M's lagged league presence predicts the traded non-GRID events beyond
  activity.

### P6. Do not pool the 16-22 Oct version with the 10-31 version across the sealed gap

- **Hypothesis.** The live trigger was decoded on 10-31, after 8 sealed days, in leagues the wallet had never
  traded before (CyberClash, FiReSPORTS). The client may have changed: taker sizing already drifted within
  16-22 Oct, and 10-share maker orders appear only from 10-22. If it changed, the selection and maker
  components fitted on 16-22 and the trigger fitted on 10-31 belong to different versions.
- **Test.** Compare fingerprints between VALIDATE (10-21/22) and the 10-31+ development blocks:
  - the share of exact 1000/2000-share taker orders and the taker fill-fraction distribution;
  - signing to block (p5-p95);
  - the maker size mix (100, 10, 11-99), the ladder gap and burst size;
  - merge cadence and pair cost;
  - the fan-out rate (P3) and the pre-order price path (flat, then +2-3c in 10 s);
  - the GRID share (still 0).
  Run a change-point test on daily values, using development days only.
- **Data.** `orders.parquet`, `calldata_dev`, `activity_devblocks`.
- **Signature if true.** A break between 10-22 and 10-31. Then fit and claim the h1/h2 components on 16-22 and
  the future-block components on 10-31 and later, separately. If the fingerprints match, pooling is justified.
