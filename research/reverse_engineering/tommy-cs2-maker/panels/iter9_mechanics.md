# Panel, iteration 9: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and re-priced, who else re-prices on the same messages, and what the per-market PnL
is made of.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 9 in full, earlier iterations by section;
- state.json: the catalog A1-X131, the components, the target metrics and the strategy statement;
- FINAL_RULE.md, by section;
- panels/iter8_mechanics.md in full, and the proposal headings of every earlier panel.

There are no EXAM or wall-audit files. `tools/sealed.py tommy-cs2-maker` reports no released lots, the future examined
up to 10-31 00:00, and the current block sealed.

Every record I read is development data:

- the BUILD-live tables of the 10-31 12-18 block: `linked_adds_dev`, `level_events_dev`, `others_mid_dev`;
- the on-chain calldata of 16-22 Oct: `calldata_all` and `calldata_pub`. I checked that both end before H (last
  block 96,005,357; last plausible signing time 10-22 23:56 UTC).

I opened nothing in `.cache/live/sealed/`, called no live endpoint, and wrote nothing outside this file. My scripts
and their JSON output are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m9\`.
They are `addlevel_confounds.py`, `persize.py`, `linked_cmp.py`, `clip.py`, `sharedV.py`, `maker_vs_p4e.py`,
`maker_vs_p4e2.py`, `p4e_anchor.py`, `cosub_limits.py`, `coreceiver_makers.py` and `coreceiver_levels.py`. Each ran
in under 4 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The maker side of these books is a cascade of feed receivers, so finding 14 used the wrong placebo

Finding 14 compares the wallet's adds with "other makers" and reads the gap as a private value. I took every maker
with at least 1,200 filled orders in the wallet's markets (16-22 Oct, on chain). For each one I counted the filled
maker orders it signed within 0-150 ms after P4e's taker signings on the same event. I kept only P4e-alone messages
(no wallet take within 1 s) and compared the counts with 40 within-event shifts of the P4e clock:

| Maker | Filled orders | In [0, 150) ms | Shift null | Ratio | Median lag after P4e |
| --- | --- | --- | --- | --- | --- |
| 0xed446954 | 4,873 | 192 | 7.0 | 27x | **+14 ms** |
| 0x2005d16a (group P) | 3,515 | 81 | 4.4 | 19x | +40 ms |
| **the wallet** | 24,180 | 783 | 30.7 | 26x | **+52 ms** |
| 0x68915897 | 5,769 | 112 | 6.2 | 18x | +80 ms |
| 0x52661b8e | 1,270 | 70 | 1.1 | 64x | +84 ms |
| 0x51dbdd2b | 5,778 | 80 | 8.2 | 10x | +91 ms |
| 0x893575c7 | 7,442 | 82 | 9.4 | 9x | +95 ms |
| 0x5cb5352d / 0xc4fe8174 / 0x6d8c0f6b | 1.4-1.8k | 25-36 | 1.7-2.0 | 15-18x | +109 to +119 ms |
| 0x5d40576b | 4,260 | 55 | 4.4 | 12x | +129 ms |
| 0xe8e1b119 (largest other maker) | 14,414 | 26 | 17.9 | 1.5x | — |
| slow trio (as makers) | ~1,200 each | 0 | ~1 | — | — |

P4e's FAK is held in the 1-s in-play delay, so nobody can see it within 150 ms. These makers sign new orders on the
same message P4e acts on:

- Two makers sign BEFORE the wallet: 0xed446954 at +14 ms and 0x2005d16a at +40 ms.
- A group follows at +80-130 ms, probably partly reacting to the public cancel wave.

The others' mid in finding 14 is moved by these co-receivers. "Its level leads the others' mid by 2-30 s" is then
fully compatible with "the wallet sits early in a cascade of makers who all re-price on the same messages". A private
value that only the wallet has is a different claim.

On the few messages where the wallet and a co-receiver both have a filled order on the same token within 150 ms,
their levels agree within 1c:

| Co-receiver | Pairs | Within 1c | Rolled control |
| --- | --- | --- | --- |
| 0xed446954 | 5 | 5 of 5 | 0% |
| 0x2005d16a | 10 | 80% | 10% |
| 0x68915897 | 13 | 69% | 0% |
| 0x51dbdd2b | 10 | 80% | 0% |

The numbers are tiny, but they point the same way.

What I confirmed: finding 14 itself is not a measurement artefact. I rebuilt a strict others' mid from
`level_events_dev`. It drops every whole-cent quantity of a wallet-like size (100 / 68 / 62 / 59 / 58 / 54 / 77 / 71,
and 10), so unlabelled wallet re-adds cannot move it. I measured the offset at s - 1 ms and the move only from
s + 100 ms. The table gives Spearman at 2 / 10 / 30 s:

| Adds | n | Wallet | Clean other makers |
| --- | --- | --- | --- |
| All | 2,732 / 42,482 | 0.35 / 0.29 / 0.25 | 0.13 / 0.09 / 0.06 |
| Quiet book (no mid change in the 500 ms before) | 884 / 21,530 | 0.26 / 0.20 / 0.15 | 0.08 / 0.04 / 0.04 |

The original numbers reproduce exactly (0.522 / 0.442 / 0.344). The excess survives, but the placebo has to be the
co-receiver set (proposal 1).

### 2. The maker re-pricing is message-locked on the full on-chain record, at the taker handler's latency

Around the 3,679 P4e-alone messages of 16-22 Oct:

- **When the wallet signs.** Its filled maker orders peak at +40-65 ms (69 orders in the +50-55 ms bin). The rest of
  P4e's delay window ([150, 600) ms) holds about 2.7 orders per 5-ms bin, so the peak is about 21x that level, and
  the fill selection of P4e's own delayed FAK cannot produce it. The median lag, 51-52 ms, equals the wallet's taker
  lag behind P4e (about 50 ms). Most likely one handler serves both legs, and it receives the messages the taker leg
  skips.
- **Where the 783 orders sit.**
  - 57% are on the complement of P4e's token (the side the message hurts).
  - 37% are on sibling markets of the event: the match and the other maps. They come at +56 ms, and none is filled
    inside P4e's transaction.
  - 6% are on P4e's own token.
- **The complement re-prices.**
  - They sit at 1 - L - 2c (median; p10 / p25 / p75 / p90 = -5.2 / -4.0 / 0.0 / +2.0c), where L is P4e's FAK limit.
  - 32% of them are filled inside P4e's own FAK transaction, and 50% by P4e overall.

So the wallet re-posts the hurt side within 51 ms, at a level P4e's delayed FAK still crosses. It under-reacts to the
message. This is the mechanism behind the group-P residual (X131: 14.8% of its maker shares, -4.1c per share). It is
also an on-chain, historical label of the maker's message re-pricings that h1 / h2 can carry. Finding 16 found the same
thing at 1-s resolution, with slow members as the clock, on one live block.

### 3. Two public routes to the private value that do not work (so nobody redoes them)

- **P4e's limit as a lagged anchor.**
  - Method: public time = taker signing + 2.5 s (an approximation). For each wallet maker BUY, take the latest P4e
    take in the same market that was public before the signing. Predict 1 - L + c1 on the complement and L + c2 on
    P4e's token, with c fitted on 16-19 Oct and scored on 20-22 Oct.
  - Within one tick, rule vs last print:

    | P4e take age | Coverage | Rule | Last print |
    | --- | --- | --- | --- |
    | ≤ 5 s | 6.7% | 0.219 | 0.207 |
    | ≤ 60 s | 27.6% | 0.205 | 0.269 |
    | ≤ 300 s | 55.9% | 0.161 | 0.316 |

  - So the message value is not public at block time in any usable form.
- **Group-P makers as V carriers on chain.** The latest filled order by 0x2005d16a on the same token, signed within
  10 s, is within 1c of the wallet's in 0.634 of cases (coverage 3.3%). Placebo makers score 0.46-0.75 and any other
  maker 0.611. On fills, nothing beyond the shared book shows.
- **Same-message FAK limits.**

  | Taker vs P4e | Within 1c, same message | Within 1c, previous message |
  | --- | --- | --- |
  | Slow trio | 0.46-0.55 | 0.12-0.13 |
  | The wallet | 0.36 | 0.15 |
  | 0x2005d16a | 0.22 | 0.23 |
  | Group G | 0.22-0.23 | 0.14-0.15 |

  Agreement is moderate, and most of it is explained by a shared stale ask. This does not decide between an event
  feed and a price feed.
- **The iteration-3 "top = ask - 1c" rule (48% on 50 burst tops) does not generalise.** On 2,748 validated own adds
  against the strict others' book at s - 1 ms:

  | Position | Share |
  | --- | --- |
  | At or above the ask | 4.6% |
  | Ask - 1c | 10.4% |
  | Inside the spread | 22.5% |
  | At the bid | 18.3% |
  | 1-3c below the bid | 31.7% |
  | More than 3c below | 18.3% |

  An oracle that picks the better of {ask - 1c, bid} reaches only 0.51 within one tick (others 0.37). No
  book-relative clip explains the level.

### 4. The outcome item cannot be reached by any maker-only rule, and the next replays should start from that

Knockout A, the wallet's own exact maker orders in the validated engine, correlates only 0.43 / 0.33 with the
wallet's total per-market PnL on VALIDATE. Its margin correlates 0.61 / 0.54. The maker and taker legs' settlement PnL
correlate -0.87 (iteration-8 critique).

So the per-market variation the exam scores is carried by message pairs: the taker leg plus the complement re-pricing
of critique 2. A perfect decode of the maker price would still fail the 0.5 threshold. Before more maker-side replays,
the investigation needs a taker-side knockout. It would tell whether the outcome item is reachable at all with public
lag (proposal 3), and the number belongs in the wall account either way.

### 5. Smaller points

- **The own-add label.** `vown` leaves 4,381 single 100-share F_mkt adds unlabelled (label precision 0.506). They sit
  in "others" and in the others' mid. The strict mid shows this does not drive finding 14, but the pre-registered
  VALIDATE-live add test should also report the strict-mid, post-add and quiet-book version.
- **The live presign check.** Iteration 3 found no excess of public book changes in the 100 ms before its takes
  (75 takes on 10-31). It was run before anyone knew a maker signs at +14 ms after P4e. 0xed446954's add would reach
  the book about 10-15 ms before the wallet signs, so that check has to be repeated per co-receiver (proposal 1).
- **Filled-order bias.** On filled-linked live adds the wallet's 10-s Spearman is 0.64 (156), against 0.31 for all
  linked others (670), 0.49 for 0x51dbdd2b (47) and 0.37 for 0x2e3c40fa (54, the wave canceller of X34). All these
  numbers are inflated by fill selection. Compare them only within the same selection.

## Proposals, ranked by the chance they close the gap

### P1. Map the co-receiver maker cascade on chain, then test whether the wallet's re-pricing is event-locked or leader-locked (new; strong form of X121 / X78 / X63 for adds, and the correct placebo for finding 14)

- **Hypothesis.**
  - The wallet's quote level is a value shared by a set R of makers who receive the same messages (critique 1).
  - Either (a) the wallet re-prices on its own feed at a fixed +51 ms, or (b) its maker leg follows the fastest
    public co-receiver's new quote within its known book-reaction latency of 10-20 ms (X49 / X78 show pulls at +11-19
    ms and wave-locked pulls).
  - Under (b), the price input is public on the live book. It is the leader's re-priced level, and the price item
    becomes decodable live.
- **Why it fits.**
  - Makers re-price at fixed lags after P4e's messages: 0xed446954 +14 ms, 0x2005d16a +40 ms, the wallet +52 ms, then
    others at +80-130 ms.
  - Same-message levels agree (5 of 5, 80%, 69%, 80% within 1c against a 0-10% control).
  - Finding 14's "concurrent half" (+1.27c within ±100 ms) is where a cascade would show.
  - X63 already found a fast touch-follower: the wallet acts within 100 ms after a change of others' best in 22-37%
    of cases (null 2-5%).
- **Test.**
  1. **Fix R on BUILD (16-19 Oct, on chain).** For every maker with at least 300 filled orders, build the lag
     histogram of its filled-order signings after each wallet-independent message clock: P4e, plus 0x2005d16a, the
     trio and group G with their fixed lags subtracted. Use P4e-alone and co-signed messages, a within-event shift
     null (2,000 draws), and the in-window level [150, 1000) ms as a second null. A maker joins R if its peak is at
     least 5x both nulls and its IQR is at most 40 ms.
  2. **Locking test (historical, then live).** On messages where the wallet and a faster member of R both re-price,
     regress the wallet's lag behind P4e on the leader's lag. Event-locked predicts a slope near 0 and the wallet's lag
     constant at about 51 ms. Leader-locked predicts a slope near 1, with the wallet's lag equal to the leader's plus
     sign-to-book (~24 ms) plus 10-20 ms. This is the X78 design, used there for pulls.
  3. **Point-in-time anchor (live development blocks).** Identify R's adds on the recorded books through linked
     calldata and size fingerprints. For each wallet re-pricing add, check whether an R add on the event's books
     reached the book before the wallet's signing. If it did, anchor = that level plus the fitted pair offset. Score
     within one tick against the touch and the last print, and report coverage.
  4. **The correct placebo for finding 14.** Re-run `add_level_info` with:
     - R's adds as the placebo;
     - the others' mid rebuilt from non-R makers only;
     - the strict mid of critique 1.
- **Data.** `calldata_pub`, `calldata_all` (on chain, 16-22 Oct); `linked_adds_dev`, `level_events_dev` and the
  development blocks from 11-01 06-12 on; the X121 decoded member calldata.
- **Signature if true (leader-locked, shared level).**
  - Locking slope ≥ 0.7, and the wallet's lag tracks the leader message by message.
  - The R-anchor scores at least the touch + 0.15 within one tick on the covered orders.
  - With R as the placebo, the wallet's excess in finding 14 shrinks by more than half.
  - The price item then has a public live input (the leader's quote). The selection and taker legs keep the feed
    reading.
- **Signature if false.**
  - Slope near 0: the wallet's lag stays at +51 ms whatever the leader does.
  - On messages it re-prices first, its level disagrees with R's (within 1c ≤ 0.4).
  - Its information stays above R's.
  - The private value is then its own, on its own feed. The lag table becomes the quantified wall for price: who
    re-prices when, and how often the wallet precedes every public trace.

### P2. The maker message ledger: decode the V update per message and localize the price gap by order class (strong form of finding 16 / X26 / X67; historical, so examinable on h1 / h2)

- **Hypothesis.**
  - Between messages, the maker ladder is mechanical: timer re-posts, refills and ladder extensions at the current V.
  - V changes only at feed messages, by an update rule. That rule is either a fixed step per message class (which
    side, which market, reversal vs follow-on) or the message's value.
  - The price gap (0.32 vs 0.80) is then concentrated in the message class.
- **Why it fits.**
  - Critique 2: 783 message re-prices at +51 ms, complement-first, siblings at +56 ms, priced at 1 - L - 2c.
  - The wallet under-reacts: 32% of the complement re-prices are filled in P4e's own FAK. That looks like a rule,
    not a value.
  - X79 (1.5-s re-post timer), X26 (complement re-quote at +1.04 s after own takes) and X67 (K - L, 53% within one tick
    in the first 1.04 s, then about 14%) are the pieces of a state machine whose input events were never timed for
    the maker leg.
- **Test.**
  1. **Message clock.** Use wallet-independent subscriber signings: P4e, plus the members' signings minus their fixed
     lags, deduplicated within 30 ms; on live blocks, add the R re-pricings of P1. Label every wallet maker order as:
     - message (0-150 ms after a message);
     - follow-on (0.15-5 s);
     - quiet (more than 5 s);
     - re-pair (within 0.9-1.2 s after its own take).
  2. **Update rule.** Per message and token: ΔV = the wallet's new level minus its last level on that token before
     the message. Use own state: filled-order levels on chain, every add on live books. Split by hurt or helped side
     and by same or sibling market. Regress ΔV, in logit units, on:
     - P4e's premium (L minus the pre-message ask);
     - the pre-message price level;
     - the message class (X99's reversal vs follow-on);
     - the title.
     Then cluster ΔV.
  3. **Price per class.** Score within one tick against the best public anchor (last print, touch) and against a
     state-machine rule: own pre-message level plus the fitted ΔV for message and follow-on orders, and the own current
     level for quiet ones. Report it with and without own state. Report class shares of orders and of PnL on BUILD and
     VALIDATE.
  4. **Wall account.** Give the share of orders signed before any public trace (the message class), with their lag
     distribution, per title.
- **Data.** `calldata_all`, `calldata_pub`, `orders.parquet` (16-22 Oct); `dota_pub*` for Dota; the BUILD-live and
  VALIDATE-live add tables.
- **Signature if true (fixed-step updater).**
  - ΔV falls into a few clusters per class.
  - Its slope on P4e's premium is below 0.3.
  - Quiet-class orders reach at least 0.6 within one tick with the state-machine or public rule.
  - The rule then fails only on message orders, and those can be decoded as "pre-level + step(class)" once a message
    is detected (by R on live books).
- **Signature if false.**
  - ΔV tracks P4e's premium with a slope near 1.
  - Quiet orders are no better priced than message orders.
  - V is then the message's value, and the price item is a quantified wall: X% of orders, Y ms before every public
    trace.

### P3. Outcome: a taker-side knockout and a feasibility bound before any further maker replays (strong form of X124 / X12 / X17)

- **Hypothesis.** The per-market PnL the exam scores is carried by message pairs: the informed take plus the
  complement re-pricing, or the complement fill against P4e. It is not carried by the maker ladder. A public executable
  rule can reach 0.5 only if a lagged copy of the message pairs keeps their per-market variation.
- **Why it fits.**
  - Knockout A, the wallet's own exact maker orders, reaches 0.43 / 0.33 against its total PnL.
  - The two legs correlate -0.87.
  - The locked margin carries 81% of the PnL variance.
  - Critique 2 shows the complement fills are the message pairs.
- **Test.** In the validated X57 engine, per market:
  - **E**: the wallet's maker orders plus its taker orders as they were (sanity check, about the wallet's PnL);
  - **F**: the same maker orders plus taker orders delayed to the first public trace of the message (P4e's
    transaction block time + 1 s), filled at that book with the wallet's limit premium and size cap;
  - **G**: the public maker set D (the executable public-anchor ladder of the iteration-9 knockout) plus the oracle
    taker;
  - **H**: D plus the delayed taker (fully executable).

  Report the per-market Pearson and Spearman against the wallet, and decompose the wallet's per-market PnL variance
  into message pairs (take plus complement within 5 s), maker-maker pairs and residual.
- **Data.** `calldata_all`, `calldata_pub`, `per_market`, `knockout_markets`, the engine code.
- **Signature if true.** F ≥ 0.5 and H near 0.5: the outcome item is reachable by public-lag taking plus a public
  maker, and the work should move to the taker trigger's public footprint.
- **Signature if false.** F < 0.5: the outcome item needs the +50-ms timing itself. It then belongs in the wall
  account with F's number, and the maker price search should stop being justified by the outcome item.

### P4. One quote function across all receivers: event feed or price feed (new; B3 inverse fit across wallets)

- **Hypothesis.** Feed P / G push a fair price, not only events. Every receiver quotes or takes around one shared
  value with its own constant margin. The alternative: each receiver turns events into its own value.
- **Why it fits.**
  - Same-message maker levels agree within 1c in 69-100% of the few pairs.
  - The trio's FAK limits agree with P4e's within 1c in 46-55% on the same message (12-13% on the previous one).
  - The wallet's implied post-message value from its complement re-price (1 - p' - s, with s ≈ 1.5c from its 0.97 pair
    sum) is about L + 0.5c, close to P4e's limit.
- **Test.**
  - Per message, compute each receiver's implied value:
    - for takers, the limit minus its own BUILD-fitted premium given the pre-message ask;
    - for makers, the re-priced bid plus its half-spread, fitted from its own pair sums.
  - Run a variance decomposition (intraclass correlation) of implied values across receivers within a message, after
    receiver fixed effects, against the same with the pre-message ask as the only common input.
  - Run it in CS2 and Dota separately, and on group-G messages in GRID events (their calldata is decoded).
- **Data.** `calldata_pub`, `calldata_all`, `calldata_grid`, `dota_pub*`.
- **Signature if true (price feed).**
  - ICC ≥ 0.8 beyond what the ask explains.
  - Receiver offsets are stable between BUILD and VALIDATE.
  - The wallet's maker level is the shared value minus a constant.
  - Consequences: a public receiver's footprint carries the value, the vendor is a B2B odds or fair-price product
    (this narrows the information search), and selection risk becomes that product's coverage.
- **Signature if false (event feed).** Receivers' values differ beyond the shared ask (ICC ≤ 0.4). The value is each
  receiver's own model of the events, and P2's update rule is the decode target.

## Overlap with the ledger and the catalog

- **P1.**
  - What exists: X121 (non-own cancels within 8 ms after its takes, live), X78 / X80 (the wallet's pulls are
    wave-locked) and X63 (a fast touch-follower), all live and about pulls or followers.
  - What is new: makers as message receivers, measured on the full on-chain record with a lag table; the locking
    test for the wallet's re-pricing adds; and R as the placebo for finding 14.
  - X28 lists 0xed446954 only as a late maker inside its FAK delay window. Its +14-ms message lag is not in the
    ledger.
- **P2.**
  - What exists: finding 16 (live, 1-s window, slow members as the clock) and X26 / X67 / X79 / X108 (state-machine
    pieces without a message clock).
  - What is new: the ms-locked maker re-pricing on P4e-alone messages over 16-22 Oct (783 vs 31), its complement and
    sibling structure, the under-reaction, and the class-wise price decomposition. It is examinable on h1 / h2 because
    it uses only on-chain fields.
- **P3.** iter8 P2 and X124 knocked out maker-side components only. The taker-side knockout and the feasibility bound
  are new.
- **P4.** X105 compared the wallet's and P4e's taker limits on co-signed pairs. The cross-receiver value model
  (makers and takers, ICC with the ask control) is new.
- **Not proposed.** X96 (salt PRNG with z3) stays as catalogued. Its payoff is an uncensored historical ladder, which
  P2 would use if it lands.
