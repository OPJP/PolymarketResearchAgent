# Panel, iteration 7: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and kept: signed order fields, the live-book labels, the client's loops and timers,
the cancel and re-post patterns, and what the software is.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iteration 7 in full, earlier iterations by section), state.json (catalog A1-X100,
components), FINAL_RULE.md, panels/iter6_mechanics.md, and the headings and overlapping proposals of the two other
iteration-7 panel files. There are no EXAM or wall-audit files.

`tools/sealed.py tommy-cs2-maker`: nothing is released, and the future is examined up to 10-31 00:00. Every record I
read is development data:

- `calldata_all`, `calldata_pub` (16-22 Oct);
- `calldata_dev`, `level_events_dev`, `linked_adds_dev`, `own_bursts_markouts_dev`, `dev_markets` (BUILD-live, 10-31
  12-18);
- `events_sel` (16-22 Oct selection table);
- `tommy_cs2_near` trade records through `iter_live` for 10-31 14:50-18:00 only.

New fetches:

- 12 development-period transactions (16-22 Oct) through `eth_getTransactionByHash` on the RPC that `fetch_calldata.py`
  uses, to read the raw signature bytes;
- one docs page (Polymarket market channel).

I opened nothing in `.cache/live/sealed/`, recorded nothing live (the current block is sealed), and wrote nothing
outside this file. My scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m7\`.
Each ran in under 2 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The cancel label behind Z4 was never validated, and the effect sits in its least specific half

X92 validated the own-level label on adds only: 873 adds linked to calldata, where multi-level bursts are 0.93
precise and odd sizes 0.98. The pull label ("validated multi-level or odd-size cancels") was carried over to cancels
without any ground truth. Yet the iteration-7 headline (Z4: the private input reaches the maker leg at 2.6 times the
take rate) and pre-registered test (c) for VALIDATE-live both rest on that label. The split is telling:

- multi-level untriggered pulls (74) carry the effect, at -1.26c over 10 s;
- single odd-size pulls (139), the half of the label that is most specific on adds, show only -0.25c.

Ground truth for cancels exists on disk and has not been used. A partially filled order whose remainder later leaves
the book without a trade is a known cancel of a known maker. `calldata_dev` holds 193 such wallet orders (27% of its
712 filled orders) and 1,032 of other makers.

Other makers also post 100-share multi-level ladders in these books, though rarely as same-ms bursts:

- 0x904ed7c7: 17 orders of 100 shares, 40% in bursts;
- 0x893575c7: 13 orders, 48% in bursts.

So label precision on cancels is an open number, not an assumed one. This is the same failure mode that sank H62 last
iteration.

### 2. The price item is a set problem, and the anchor search is exhausted

I scored the full-book state at sign - 100 ms on BUILD-live, using 156 linked filled orders and 2,588 validated adds.
The wallet's add prices relative to the touch spread almost evenly over 0 to -5c:

| Offset from the touch | 0 | -1 | -2 | -3 | -4 | -5 | +1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Share of validated adds | 17.6% | 14.8% | 10.4% | 10.8% | 16.5% | 8.1% | 10.2% |

That is a 6-level ladder, so no single anchor can reach 0.8 per order. Every anchor family I tried is at or below the
plain touch:

- **Complement side.** Ask (= 1 - the other token's bid) minus the best constant: 0.42 / 0.33 (filled / adds). Mid
  minus a constant: 0.42 / 0.36. Touch: 0.52 / 0.42.
- **Size-filtered touch.** The best bid with at least S shares, for S from 5 to 500, is never better than S = 0.
  Burst tops score 0.528 at S = 0 and fall to 0.42 at S = 100.
- **Book-view lag.** Burst tops within one tick of the touch: 0.528 at a 100-ms view, 0.493 at 300 ms, 0.396 at 1 s,
  0.369 at 2 s. Its book view is fresh.
- **First empty level (queue position).** 0.10 / 0.26. Only 40-44% of its adds go to an empty level.

What remains is the ladder manager itself: which slot each order fills, and when the set shifts. That is own-ladder
state plus private shifts. The investigation keeps adding anchors; it should decode the manager as a state machine
(P2).

### 3. Untriggered pulls are mostly not the take handler's pattern

I split its pulls by class on BUILD-live, by distance from its takes in calldata:

| Class | n | Levels (mean) | Multi-level | 100-share | 10-s markout |
| --- | --- | --- | --- | --- | --- |
| Pulls 0-200 ms after its own takes (median 15 ms) | 42 | 3.7 | 88% | 43% | -3.6c |
| Untriggered | 213 | 1.6 | 35% | 13% | -0.6c |
| Other triggered | 1,115 | 2.3 | 64% | 47% | +0.1c |

At a message it acts on, the handler strips the whole complement ladder. Most untriggered pulls are single odd-size
cancels, which is ladder-manager behaviour. The "about 3.6 events per take" stream in the wall account therefore
mixes two mechanisms. Only the multi-level subset (74) looks like a handler receipt without a take. The investigation
also never asks the decodable question that follows: given that the handler received a message, when does it take
rather than only pull (P3)?

### 4. An on-chain field nobody has decoded: every order carries an ERC-7739 nested signature

All 14 of the wallet's orders I sampled (6 taker, 8 maker, 16-22 Oct) carry a 317-byte signature with this layout:

- a 65-byte ECDSA signature;
- a 32-byte app domain separator (`3264e159...7af3d2`, the same in every order: the exchange's);
- a 32-byte contents hash (the Order struct hash);
- the type string `Order(uint256 salt,address maker,address signer,uint256 tokenId,uint256 makerAmount,uint256 takerAmount,uint8 side,uint8 signatureType,uint256 timestamp,bytes32 metadata,bytes32 builder)`;
- its length, 0x00ba.

`calldata.py` drops the signature, and C1 / X14 took the owner from `owner()`. The key that actually signs each order
can be recovered. It can separate processes (maker vs taker), date key changes (the 10-16 switch) and link wallets
through a shared key, none of which salts, sigTypes or funding could do (P4).

### 5. The process architecture is two programs, started by hand

- 1,688 of its 1,698 taker orders (99.4%) fall inside the merge-loop runs.
- The 10 outside all come 1-5 minutes before the first merge pass of the day: 10-17 08:06-08:07 (first pass 08:10),
  10-20 09:03 (09:04), 10-21 08:19-08:22 (08:23), 10-18 14:16 (14:17), 10-16 13:40 (13:45).

So the taker service starts first and the maker / merger process a few minutes later. The start times differ by
minutes from day to day, which looks like a person starting both each morning. This supports Z5 and X98 step 3 (a
local-time session). It also means "process up" belongs to two processes, and the selection-by-session reading
should use the taker's first take as well as the first merge.

### 6. Two smaller points

- **Single push stream with a kind filter vs a second, narrower stream.** These two readings are not separated.
  The decisive fact is the maker leg. With the full stream it would have about 950 ms at every round-win message to
  pull its exposed ladder before P4e's FAK matches. It pulls in 17% (control 10%) and is hit in about a third of
  those events. A filter "at the input" and "a different input" predict the same thing there. They predict different
  lag structure (P5).
- **Two taker order builders, one handler.** 114 takes (6.7%) are USD-amount market orders, the other 93% limit
  orders at integer sizes. Two examples:
  - 2,035.7142 shares at 0.56 = $1,140.00;
  - 1,265.9791 shares at 0.48 = $607.67, a floor-rounded 1,266 x 0.48.

  Their co-sign rate (33%) and P4e lag (median -57 ms) match the limit takes (27-29%, -48 to -54 ms). So these are
  two code paths in one handler, not a second source.

## Quick checks (so nobody redoes them)

| Check | Result | Script |
| --- | --- | --- |
| Untriggered pulls as delayed reactions to its own fills (user-channel / confirmation lag) | 6.6% have an own fill on the same token 0.3-10 s before (shift null 5.4%). The 159 with no own fill within 60 s still show -0.6c at 10 s. Not an own-fill artefact. | `fillreact.py` |
| Untriggered pulls as post-trade momentum | With no trade on the event for > 30 s (n 78): -0.22 / -0.65 / -0.65c at 2 / 10 / 30 s. Not a recent-trade artefact. (The information panel's follower confound is separate and stands.) | `tradereact.py` |
| One sequential executor across P4e, 0x2005d16a and the wallet (fixed order, ~25-ms steps = one POST round trip) | 0x2005d16a signs after the wallet in 6 of 20 P4e-led triples, and twice before P4e: no fixed chain, so the push verdict survives. Residual coupling: the wallet's lag after P4e is +9 ms when P4e signs >= 2 orders (MWU p 0.074; within-event permutation p 0.11). P4e signs its own legs exactly 4 ms apart (p10-p90 4-5 ms, 461 pairs); the wallet signs its legs 0.8-3 ms apart. | `seqloop.py` |
| C4 timer law (plant message -> explosion round end at +40 s) | Wallet take -> later P4e clusters, 39.5-41.5 s: at most 4 per 0.1-s bin (median 0). Any other taker: at most 25 (median 15). No spike. Inconclusive: an explosion is priced before it happens. | `c4law.py` |
| Selection as process capacity (concurrent eligible events) | Logit given log pre-game wallets, tier and session hours: -0.02 per running event (p 0.62). Negative. | inline |
| Anchors for the maker price (critique 2) | Touch best; ask, mid, size-filtered and lagged anchors no better. | `anchors.py`, `sizetouch.py`, `emptylvl.py` |
| Taker order builders (critique 6) | Same co-sign rate and lag. | `ctor.py` |
| Market-channel `hash` as an order key | The docs' per-change `hash` is 40 hex characters, not a 32-byte order hash: probably a book digest, so order-level linking from the feed is unlikely. Verify on the next dev block (the shared recorder drops the field). | docs |
| Raw signatures | ERC-7739 layout, critique 4. | `sigpeek.py`, `sigpeek.json` |

## Proposals, ranked by the chance they close the gap

P1 comes first because it is time-critical: it must run before the 11-01 06-12 block is scored, and it decides
whether the maker leg can be used as a label of the private input at all. P2 is the only route found to the failing
price item. P3-P5 tighten the timing component and the wall account.

### P1. Validate the cancel label with ground-truth cancels, then re-score Z4 before VALIDATE-live (correction; strong form of X92 / X94)

- **Hypothesis.** The "validated" pull label is materially less precise on cancels than on adds, above all in its
  multi-level part. Part of the untriggered-pull markout then belongs to other makers. Those may themselves be
  informed, for example 100-share ladder makers that react to the same events.
- **Evidence.**
  - Critique 1: no cancel was ever validated.
  - The effect sits in the multi-level pulls (-1.26c) and not in the odd-size pulls (-0.25c), which are the most
    specific on adds.
  - Several other makers post 100-share whole-cent ladders in the same books (critique 1).
- **Test (BUILD-live; nothing from 11-01 is opened).**
  1. Ground truth. For every maker order in `calldata_dev` with remaining size >= 1 after its last on-chain fill
     (193 wallet, 1,032 other), follow its (token side, price) level on the server-clock book. The first trade-free
     decrease that removes at least the remainder is a cancel of a known owner. Accept it only when that order is the
     only same-size order at the level, using the linked-add table.
  2. Score the frozen pull label (multi-level F_mkt, odd size, and the single 100-share cancels it excludes) on these
     cancels: precision and recall per class and per book. Also score it on the take-time pulls (their timing makes
     them the wallet's).
  3. Re-run `untriggered_v2.py` restricted to: (a) ground-truth wallet cancels (small n, descriptive); (b) the
     sub-label whose cancel precision is at least 0.95; (c) the complement, as a placebo. Report each next to the
     frozen number.
  4. Pre-registration. Leave test (c) unchanged, as frozen. Add before 11-01 06-12 is read: (c') the same 10-s
     markout on the >= 0.95-precision sub-label, at the same alpha. Report it next to the information panel's
     no-follower stratum.
- **Data.** `calldata_dev`, `level_events_dev`, `linked_adds_dev` (on hand), and the same tables for later
  development blocks.
- **Signature if true.** Multi-level cancel precision is below about 0.85, and the -1.26c markout shrinks or moves to
  other owners on ground-truth cancels. Z4 must then be restated, possibly as "other informed makers pull between the
  wallet's takes".
- **Signature if false.** Cancel precision is at least 0.93 in both classes, and ground-truth wallet cancels without a
  trigger show the negative markout. Z4 then stands on a validated label, which the wall account needs.

### P2. Decode the ladder manager as an explicit state machine with own state, per order (strong form of X75 / X100 / D2 for the price item)

- **Hypothesis.** The wallet's resting set on each token is a deterministic function of three things:
  - a top T (the touch with a pair cap);
  - a fixed 6-level target set {T, T - 1c, ..., T - 5c};
  - a refill / shift policy driven by its own events (a fill at level p, a cancel, a take, an untriggered pull,
    the 1.5-s timer).

  Each new order fills a slot of that set. With own state, the per-order price is predictable well beyond the touch's
  0.47. Without it, the ceiling is the top-slot share (critique 2).
- **Evidence.**
  - Offsets spread over 0 to -5c (critique 2).
  - Hole-filling a 4-level target already reaches 0.48-0.50 on adds (X100).
  - The re-post timer returns to the cancelled price in 51% (H69). Its own previous top scores 0.45 on filled orders.
  - The anchor families are exhausted (critique 2).
  - The brief allows own state for describing the policy, if reported with and without it.
- **Test.**
  1. On BUILD-live, rebuild its own resting ladder per token at every event from validated adds, P1-validated
     cancels and on-chain fills.
  2. For each own add, set the target to the slot index relative to its own top T before the burst (and relative to
     the touch). Features:
     - the ladder shape (occupancy of T .. T - 6c);
     - the last own event type and its age (fill at p, cancel, take, untriggered pull, timer);
     - the change in the touch since the last own burst;
     - the pair-cap headroom (0.99 minus its top on the other token);
     - the spread.
  3. Fit a depth-4 tree on the first half of BUILD-live and score it on the second half. Distill it into a rule list,
     freeze it, and score it on VALIDATE-live (11-01 06-12 on), per add, per top change and per filled order.
     Report it with and without own state, against the touch.
  4. Decompose the misses by the last own event. If they concentrate after untriggered pulls and takes, the residual
     is the private fair-value shift. Measure the shift size: the re-posted top minus the old top, against the later
     10-s / 30-s move of the others' mid.
- **Data.** On hand for BUILD-live; future development blocks for VALIDATE-live; `evaluate()` can apply the frozen
  machine on future sealed blocks from the books.
- **Signature if true.** A short rule list reaches at least 0.8 within one tick per add and per filled order on
  VALIDATE-live with own ladder state, with the misses concentrated after private events. The live price item is
  then met as an own-state description, with the private shift as the stated residual.
- **Signature if false.** At most about 0.6 with own state. The ladder is then re-anchored by private shifts often
  enough that price stays bounded by the private input. The wall account gets the share of misses after untriggered
  pulls and takes.

### P3. Handler identity, then the take filter conditional on a message receipt (new; complements the assumptions panel's P5)

- **Hypothesis.** The feed handler issues two outcomes per received message: take plus strip the complement ladder,
  or strip only. Which one it chooses is a public execution filter: stale depth on the gaining team's ask, spread,
  price level, room under the pair cap. The kind selectivity would then be at least partly this filter, not a
  subscription.
- **Evidence.**
  - Take-time pulls strip 3.7 levels, 88% of them multi-level (critique 3).
  - 74 untriggered multi-level pulls look like that pattern without the FAK, and carry the large markout.
  - X99 tested an edge filter at P4e's events, not at the wallet's own receipts.
- **Test.**
  1. Handler identity, on P1-validated cancels. Compare take-time pulls with untriggered multi-level pulls on:
     - the share of own levels on the token removed;
     - the server-ms spread of the removals (one batch vs sequential cancels);
     - whether the other token is touched;
     - the re-post delay distribution (1.04 s FAK return vs 1.5 s timer vs other);
     - sizes.

     A match on every dimension except the FAK means handler-issued.
  2. Receipts = its takes plus handler-like untriggered pulls (BUILD-live, then VALIDATE-live). At receipt time
     (server clock, sign - 0 ms for takes, pull time for pulls), record:
     - the best ask and the depth within 1c / 2c on the gaining token (the complement of the pulled one);
     - the spread and the price level;
     - match vs map;
     - the time since the last public burst, and whether that burst was on the same team;
     - its own pair-cap headroom (own state, reported separately).

     Fit a logit for take vs strip-only on BUILD-live, freeze it, and score it on VALIDATE-live.
- **Data.** Live books, `calldata_dev`, and own bursts for each development block.
- **Signature if true.**
  - The two pull types are indistinguishable except for the FAK.
  - Take vs strip-only reaches AUC >= 0.75 from public execution state, for example "takes only when at least D
    shares rest within 2c of the stale ask".
  - The timing component becomes "private message x public execution filter", with the filter decoded.
- **Signature if false.** The patterns differ, or the filter AUC is about 0.5. Untriggered pulls are then mostly
  ladder management, and the kind filter sits in the message content.

### P4. Recover the actual signing key of every order from its ERC-7739 signature (new data field; strong form of C1 / C8)

- **Hypothesis.** The deposit wallet accepts orders signed by keys other than, or in addition to, `owner()`. The
  recovered keys separate the wallet's processes, date its controller changes, and may be shared with other wallets
  of the same operator.
- **Evidence.** Critique 4 gives the format. Critique 5: two processes, started minutes apart. The 10-16 switch
  changed everything at once: universe, maker client, merge loop, and joining the fan-out.
- **Test.**
  1. Implement keccak-256 and secp256k1 public-key recovery in pure Python (no package install needed). Self-test:
     recompute the Order struct hash from the decoded fields and match it to the 32-byte contents field inside each
     signature.
  2. Read the wallet's `eip712Domain()` (ERC-5267, selector `0x84b0196e`) with `eth_call`. Build the ERC-7739
     TypedDataSign hash from the app domain separator, the contents, the wallet's name / version / chainId /
     verifyingContract / salt, and the `Order(...)` type string, then recover the signer.
  3. Sample, keeping only (tx, order index, recovered signer) in `.cache/re/`:
     - the wallet: all 1,698 taker orders plus 500 maker orders of 16-22 Oct, and its taker-regime orders of
       10-01..10-15 if they are V2 sigType 3;
     - the same for P4e, P93, 0xf1ee4842 (sigType 3) and the merge-law siblings 0xf1f2b3c6 / 0x52661b8e;
     - for sigType 1 / 2 wallets (0x2005d16a and the 0x8a80528d / 0xddb6e624 pair), plain ECDSA recovery against
       the `signer` field.
  4. Compare signers across maker vs taker orders, before vs after 10-16, by day (restarts), and across wallets.
- **Data.** Transaction inputs via `eth_getTransactionByHash`, the same RPC and pacing as `fetch_calldata.py`
  (about 3k transactions), and one `eth_call` per wallet.
- **Signature if true.**
  - Distinct signers for the taker and maker legs: two processes or two people.
  - A signer change at 10-16: a new controller took over the wallet.
  - A signer shared with P4e, a subscriber or a sibling: one operator. The fan-out and the "pack" fills on its
    ladder are then internal, and the pooled wallets become one strategy's decisions (scope and data both widen).
- **Signature if false.** Every order recovers to `owner()` 0x8af810f0. Record it as the negative that closes C1 at
  the key level.

### P5. One stream or two: the lag structure by event class and the residual coupling to P4e (strong form of X97; mechanics side of the assumptions panel's critique 3)

- **Hypothesis A (one fan-out, kind filter).** One message reaches P4e and the wallet at a fixed offset. The
  wallet - P4e lag is then the same for every event class, price level and P4e order count.
- **Hypothesis B (two detectors of one in-game event).** Two different pipelines see the same in-game event at
  latencies that depend on the event type. Then:
  - the lag depends on the event class;
  - the wallet's non-protection at P4e's round-win events (critique 6) is expected.
- **Evidence.**
  - The pre-registered verdict used platform, leg, day and game-time terms, not event class.
  - The co-signed share is 26%.
  - The residual coupling of +9 ms (quick checks) is unexplained under A.
- **Test.**
  1. Historical (16-22 Oct plus the 10-09..10-15 subscriber record). MixedLM of the wallet - P4e lag with event
     random effects. Fixed terms:
     - the burst class (reversal / same-team follow-on / isolated);
     - plant-loaded maps (bo3 per-map dBP);
     - the price level;
     - P4e's order count and the time of its last order.

     Do the same for 0x2005d16a - P4e, as a subscriber-to-subscriber control.
  2. VALIDATE-live, if P4e trades: the share of validated multi-level pulls on the exposed token in [P4e sign +
     60 ms, P4e sign + 950 ms] at P4e-alone events, against a busy-phase control and against the wallet's 87% at its
     own takes. Pre-register the windows before reading the block.
  3. Extension (geography). Each subscriber's CLOB latency (FAK match - sign - 1,000 ms from live trade times; sign
     -> add for maker legs) against its feed lag after P4e. Lags that add up along network distance point to the
     source's location: near the venues / game servers or near a cloud vendor.
- **Data.** On hand (historical); 11-01 development blocks.
- **Signature of A.** The lag is invariant across classes (differences < 10 ms) and the order-count effect
  vanishes. Pull rate at P4e-alone events is at control level, so the filter is at the input.
- **Signature of B.** A class-dependent offset (for example plant-loaded co-signs earlier or later by >= 20 ms), or a
  lag locked to P4e's last order. There are then two sources, and the wall account must name both.

## Overlap with the ledger and the other panels

- **P1** is new. X92 validated adds only, and nothing validated cancels. It complements the information panel's
  follower confound: that one concerns who moves after the pull, this one who made the pull.
- **P2** is the strong form of X75 / X100. Those tried a fixed hole-filling target and anchors; P2 adds own-event
  transitions, a learned and distilled machine, and miss decomposition. It overlaps the assumptions panel's P5
  step 3 (own-state price) only in its last step.
- **P3** is new as a test. X94 measured markouts, X99 the edge at P4e's events, and the assumptions panel's P5 the
  accumulation of pulls before takes.
- **P4** is new: the signature bytes were never decoded.
- **P5** is the mechanics form of the open "one source or two" question. The information panel's P6 approaches it
  through outages, the assumptions panel's P4 through fill censoring.
