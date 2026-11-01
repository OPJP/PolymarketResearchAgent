# Panel, iteration 5: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and kept. That covers the ladder as a state machine on the live book, the scoring unit
of the price metric, the residual and its control, the client's timers, and what a copy of the maker leg can and cannot
reach on the outcome target.

## What I read and what I ran

I read BRIEF.md, NOTES.md (iterations 1-5), state.json (catalog up to X69, components, target metrics), FINAL_RULE.md
(v3) and every earlier panel file (iterations 1-4, all three lenses).

I ran small read-only checks on development data only:

- **Live, 10-31 14:50-18:00 UTC development block:** `level_events_dev.parquet` (the 7 dev-unit CS2 token-0 books,
  both sides, server clock; own levels by the 100 / 68 / 58 / 54 whole-cent fingerprint, as in `band_hazard.py`) and
  `dev_wallet_trades.parquet` (own inventory).
- **History, 16-22 Oct (before H):** `per_market.parquet`, the V2 fills, `orders.parquet`, `activity_dev.parquet`,
  `markets_dev.json` (outcomes for settlement only) and the windowed taker tapes.
- **One new fetch:** CLOB `/prices-history` (fidelity 1 minute) for 3 VALIDATE tokens, through the cached polyrea
  adapter, with the window clamped below H.

`tools/sealed.py tommy-cs2-maker` confirms that 10-31 12-18 is a development block and that no lot is released. I
opened nothing in `.cache/live/sealed/` and read no unit that started at or after H outside that block. The scripts
are listed at the end.

## Critique: what the investigation is missing or getting wrong

### 1. "Joins the other makers' best within one tick in 67%" uses a unit that is not the decision, nor what the examiner will score

**Most add bursts do not move its top.**

- Adds can only raise the best own level, so `band_hazard.py` scores pure ladder extensions and refills together with
  real top decisions.
- Of 5,766 add bursts, 63.9% leave its top unchanged. They raise it by 1c in 18.1% and by 2c or more in 18.0%.

**The 67% hides two regimes.**

| Own top just before the burst | n | New top = previous top | New top within one tick of others' best |
| --- | --- | --- | --- |
| At others' best | 1,573 | 86.7% | 97.5% |
| 1c below it | 1,157 | 58.9% | 98.9% |
| 2c or more below it | 1,679 | 34.5% | 38.5% |
| Above it (others pulled) | 886 | 85.6% | 46.7% |
| No own level on that side | 471 | - | 34.4% |

- Where it already sits at the touch, "join" is close to exact.
- About a third of the bursts come from deep states (2c or more behind, or no own level). There "join" is wrong
  about 60% of the time.
- Those deep states are the open part of the price rule.

**The examiner will most likely score filled orders.** Those are the orders calldata attributes with certainty, and
on the live block they sit at 45.6% within one tick of others' best (X43). So 67% is not the number to plan around.

**What the live book can and cannot give.** Within one tick of others' best, by book age:

| Book age | 1 ms | 100 ms | 500 ms | 1 s | 2 s |
| --- | --- | --- | --- | --- | --- |
| Within one tick | 0.679 | 0.658 | 0.624 | 0.575 | 0.532 |

- A replicator 2 s behind still gets 0.53. The best historical anchors get 0.25-0.34.
- So the historical deficit is the reconstruction of the other makers' book from fills, not latency. No latency
  assumption rescues h1 / h2 price. Only a different anchor family can (proposal 3).

### 2. "A fast touch-follower within ~100 ms at any gap" overstates its protective reactions

**Time on the token-0 books, by where its top sits:**

| Its top relative to others' best | Share of time |
| --- | --- |
| Strictly above (sole best) | 7.4% |
| At others' best | 23.1% |
| Behind | 47.4% |
| No own level | 22.1% |

**It rarely follows the others down.** In 684 episodes the other makers' cancels left it alone at the top.

- The episode ended because the others re-added in 66.1%.
- It ended by its own cancel in only 23.7%: 7.6% within 100 ms and 16.2% within 1 s.
- The median episode lasted 148 ms, the p90 11.6 s.

**The re-join hazard after a change of the others' best is about 14-26% per 100 ms, in both directions.** This counts
a re-join made by either party, so it is an upper bound on its own reaction.

| Others' best moved | Gap after the move | n | Re-joined within 100 ms | 500 ms | 2 s |
| --- | --- | --- | --- | --- | --- |
| Down | it is 1c above | 503 | 25.8% | 43.7% | 61.0% |
| Down | it is 2c above | 329 | 13.7% | 23.7% | 39.5% |
| Up | it is 1c behind | 988 | 18.0% | 49.6% | 70.4% |
| Up | it is 2c behind | 560 | 17.7% | 36.8% | 58.0% |

So the ladder does not protect itself by following the fast makers' cancel waves, which are public. That fits the
census (its complement is hit in 19-22% of the bursts it misses) and the 37% hit rate at pack-only events. The FINAL_RULE
price row and the `timing` component should say "a stochastic re-join hazard", not "within ~100 ms".

### 3. Presence is not a public function even on the live book, so the probe AUC is not a staleness artefact

- I sampled random times on the live block and asked, for each level from others' best + 2c down to others' best − 8c,
  whether its fingerprinted order rests there (197,340 level-times, base rate 0.24).
- P(own level present) is 0.26-0.37 from others' best down to 4c below it, and 0.17-0.22 further down. At any instant
  the ladder is patchy, not a contiguous block of L levels under the touch.
- AUC of the gap alone, fitted on the first half of the block and scored on the second: 0.706. Given that it quotes
  that side at all (74% of the time): 0.723.

This is close to the historical probe's 0.669. Where its levels sit depends on its own action history (fills
consuming levels, cancel-and-re-post cycles, timers; see proposal 5), not on the public touch. It confirms the
iteration-5 reading with a live, uncensored label, and it rules out the hope that live books alone will lift presence.

### 4. The outcome target is a residual-control problem, and even an exact copy of the maker leg is borderline

**The wallet's per-market PnL is its margin, not its volume.**

| Split | PnL against paired volume, P / S | PnL against locked margin, P / S |
| --- | --- | --- |
| BUILD | 0.46 / 0.22 | 0.85 / 0.66 |
| VALIDATE | 0.54 / 0.36 | 0.83 / 0.74 |

- Its margin per pair varies a lot across markets (median 2.1c, IQR -0.5 to 4.4c, standard deviation 4.9c).
- That margin does not follow its taker share (Spearman 0.11 / 0.05) or its volume.
- Copying the volume is not enough (iteration 5: paired-volume Spearman 0.79-0.92, PnL correlation about 0).

**Oracle check (diagnostic; it uses the wallet's real maker fills).** On the wallet's maker fills I added a public
completion hedge: whenever |imbalance| > X shares, buy the short token at its last public print (2 s stale, wallet
transactions excluded) + 1c, assuming a full fill.

| Variant | BUILD P / S | VALIDATE P / S | BUILD / VALIDATE sum |
| --- | --- | --- | --- |
| Maker-only locked margin (ceiling) | 0.73 / 0.66 | 0.63 / 0.58 | - |
| Maker leg, no hedge | 0.39 / 0.50 | 0.38 / 0.34 | -$70 / +$4.1k |
| + hedge X = 400 | 0.34 / 0.50 | 0.69 / 0.56 | +$0.7k / +$4.4k |
| + hedge X = 200 | 0.34 / 0.41 | 0.58 / 0.54 | +$2.2k / +$4.1k |
| + hedge X = 100 | 0.36 / 0.40 | 0.31 / 0.41 | +$3.0k / +$4.4k |

- With a perfect copy of the maker ladder and a crude public hedge, VALIDATE passes at X 400, but BUILD fails Pearson
  at every X.
- The outcome target therefore needs two things:
  - a maker leg equal to the wallet's, which only a decoded live ladder can give;
  - a residual control that tracks what its private taker leg does.
- The "public 4c ladder plus oracle take fills" bound (0.24) measured a different thing: a wrong maker leg with the
  right takes.

### 5. Quick checks that came out negative (so nobody redoes them)

- **CLOB `/prices-history` (A7, never tried here).** At fidelity 1 minute it returns 60-s points whose values look
  like midpoints (0.475 / 0.525). Within one tick of its maker orders: 0.14-0.34 on 3 VALIDATE tokens, no better than
  the last print. It is not a historical book.
- **Capital or concurrency does not set the event start size.**
  - Concurrent quoted events: Spearman -0.155 (p 0.18).
  - Cash proxy from fills, merges and redeems: Spearman -0.143 (p 0.21).
  - Net 2-h spend: Spearman 0.071 (p 0.54).
  - 77 events, 36% of them with a ramp. The CLOB balance check is not the ramp's clock.
- **A public hysteresis state machine does not beat plain join.** Follow the others up at once and down only past g
  cents: g 0 (join) 0.679, g 1 0.658, g 2 0.612, g 3 0.572, never 0.154. The persistence that matters is not a public
  hysteresis (proposal 1).
- **Pair-sum and spread rules add a few points only.** On the 5,065 bursts with an own level on the other side:

  | Rule | Within one tick |
  | --- | --- |
  | Join | 0.707 |
  | Join capped at K 0.98 minus its own opposite top | 0.736 |
  | The cap, plus a 1c improvement when the others' spread is 3c or more | 0.761 |
  | An oracle switch among join, the cap and ask - 1c (upper bound) | 0.817 |

  By the others' spread: at 1-2c, join or mid - 1c gets 0.77-0.88. At 3c or more (47% of bursts), join gets 0.50-0.64,
  and ask - 1c and mid - 1c are no better.
- **The wallet is two-sided in every market.** The smaller-to-larger share ratio is never below 0.2, so side stays
  not applicable.

## Proposals, ranked by the chance they close the gap

### 1. Price for the future-block exam: decode the ladder's deep states, with own inventory and the pair cap as declared state (strong form of X43 / X63 / B3)

**Hypothesis.** The new top on token s is

    top_s = min( others_best_s(t - λ) + δ(inv_s, spread_s), K - own_top_other(t) )

- δ is +1c on the short side when the others' spread is 2-3c or more, and -1c on the long side beyond about 300
  shares.
- The deep states (2c or more behind, or no level) are re-entries:
  - after its own take (K - L);
  - after a pull or cooldown (proposal 5);
  - on the long side.

  Each is its own branch, and each has its own anchor.

**Why it fits.** Critique 1 and my checks:

- At or 1c under the touch, join is 97.5-98.9% within one tick. The rule fails only in the deep states.
- The cap against its own opposite top adds +3 points, and the spread-conditional improvement +2.5.
- Inventory shades as a skew predicts:
  - long beyond 300 shares (n 346): mean offset -0.89c, -1c in 37.6%, +1c in only 2.6%;
  - short by 100-300 shares: +1c in 21.7%.
- A depth-5 tree on public book state scores 0.70 within one tick on the held-out second half of the block, about the
  same as join (0.71 there). Adding the wallet's own previous top lifts it to 0.85 (exact 0.59). The state that matters
  is the ladder's own history.

**Test.**

1. **Split.** BUILD = the 10-31 12-18 block. VALIDATE = 11-01 06-12, then the live VALIDATE blocks from 11-01 18:00.
2. **Units.** Score three units and declare in `evaluate()` which one the examiner should use:
   - (a) filled orders (calldata);
   - (b) every fingerprinted own add;
   - (c) top changes only.
3. **Variants.** Fit the explicit rule above. Report it:
   - with public book state only;
   - plus own inventory (own state, declared);
   - plus the wallet's own previous top (diagnostic only; it conditions on its own presence).
4. **Deep states.** Label each deep-state burst by:
   - the time since its own last take, measured from `calldata_dev` signing;
   - the time since its own last pull or cooldown cancel;
   - inventory, and the others' spread.

   Fit an anchor per branch:
   - K - L after takes;
   - the cancelled level ± k after cooldowns;
   - the series fair value of proposal 3 in wide books.
5. **Book age.** Re-score with the book at s - λ for λ = 0-200 ms to estimate its view latency. Use the fitted λ in
   the rule.

**Data.** `tommy_cs2_near` through `iter_live` (rebuild `level_events` for every token of every dev-unit market, not
only token 0 of 7 markets), `calldata_dev` for each dev block, and the wallet's dev-unit trades.

**Signature if true.**

- At least 0.80 within one tick on unit (a) or (b) on the VALIDATE live blocks, with public state plus own inventory.
- It holds in both halves of each block.
- If only the own-previous-top variant passes, write it down as the quantitative account: the share of price
  decisions that depend on the private placement history.

### 2. Outcome: copy the maker leg, then find a public residual control chosen on BUILD (new; strong form of X57 step 4)

**Hypothesis.** The per-market outcome is the maker leg's locked margin plus how the residual is controlled. A rule
whose maker fills track the wallet's, plus a public completion hedge, reaches Pearson and Spearman of at least 0.5. The
wallet's private taker leg then matters only through how the hedge cost is distributed across markets.

**Why it fits.** Critique 4:

- PnL tracks the locked margin (0.83-0.85), not the volume.
- An exact maker leg plus a crude hedge passes VALIDATE (0.69 / 0.56) but not BUILD (0.34 / 0.50).
- The gap between the two splits is the hedge design, which nobody has optimised.

**Test.**

1. **Oracle-leg hedge search on history (diagnostic, uses the wallet's maker fills).** Triggers:
   - an imbalance cap X;
   - a price stop: hedge when the long token's 2-s-stale print falls m cents below its average cost;
   - a time stop: flatten at the map's last rounds, as public map-score proxies give them;
   - a merge timer.

   Run the hedge through the validated engine with strict fills, not at "print + 1c". Choose the trigger on BUILD and
   score it on VALIDATE (Pearson and Spearman, event-bootstrap CI). Also report each half of each split, as the
   examiner's replication rule does.
2. **Executable version.** Replace the oracle leg with the proposal-1 rule on the live books and the validated engine
   (its own orders, price-time priority, post = decision + λ + 24 ms; takers from calldata with match = sign + their
   per-signer delay).
   - Per-market correlation needs at least 24 h of markets, so on dev blocks use an intermediate metric: the share of
     the wallet's maker fill shares that the copy also gets in the same transaction (target 0.6 or more), and the
     reverse.

**Data.** History: `chain_fills`, `calldata_all`, tapes, `per_market`, the X44 engine. Live: `tommy_cs2_near`,
`calldata_dev`.

**Signature if true.**

- A BUILD-chosen hedge reaches at least 0.5 in both P and S on VALIDATE with the oracle leg. Outcome then reduces to
  the ladder copy (proposal 1) and becomes a future-block claim.
- If no trigger passes BUILD and VALIDATE together, the outcome wall is quantitative:
  - with the exact maker leg, any public residual control tops out at x / y;
  - the private taker leg supplies the rest, as the -0.85 per-market correlation between the legs implies.

### 3. A cross-market series fair value as the maker anchor in thin books, and as a historical anchor for h1 / h2 (new)

**Hypothesis.** When the others' spread is 3c or more, the bot quotes off its own fair value, not off the thin local
touch. That value comes from the sibling market (match ↔ map) through the series formula and the map score. For a bo3,
with per-map probability r taken from the pre-game match price:

    P_match = q · r(2 - r) + (1 - q) · r²      (map 1, 0-0)

so q = (P_match - r²) / (2r(1 - r)), and the sensitivity 2r(1 - r) is 0.5 at r = 0.5. The map-2 and map-3 states
follow the same way.

**Why it fits.**

- In wide books (47% of bursts) join is 0.50-0.64 within one tick, and ask - 1c and mid - 1c are no better.
- Its fan-out FAK premiums have a match / map ratio of 0.50-0.58, which equals the series sensitivity (X45). So it
  already carries a series model.
- It quotes every market of the event at once.
- Cross-market tests so far (A4, E8) asked only whether a sibling leads its taker trigger. None used the sibling as
  the maker's anchor.

**Test.**

1. **Live (dev blocks).**
   - For each burst in market m, compute q from the sibling's others' mid at s - 50 ms. Own levels are removed by
     fingerprint; `tommy_cs2_near` holds every market of the event.
   - Take the map score from the sports socket, which carries map scores for its events.
   - Take r from the last pre-game print of the match.
   - Candidate rule: top = the fair value minus h, rounded down to the cent, against join, scored separately in wide and
     tight books.
2. **History (VALIDATE).** Build the same anchor from the sibling's match-clock last print. Use the revealed others' bid
   when it is fresher. The previous maps' results come from their markets' last prints, which are public at the time.
   Score `price_within_tick` on filled orders against the last print (0.305) and the rebuilt touch (0.396).

**Data.** Live: `tommy_cs2_near`, the `sports` feed, `calldata_dev`. History: `calldata_all`, `calldata_pub`, tapes,
the Gamma listing (to group markets by event).

**Signature if true.**

- In wide books the series anchor beats join by at least 10 points.
- On VALIDATE, `price_within_tick` rises clearly above 0.396.
- It is the only route I see to a price number on h1 / h2 that is not capped by the missing book.
- If it fails, the deep-state branch of proposal 1 is private placement. That is part of the quantitative account.

### 4. At the events it misses, are its pulls locked to the public cancel wave or to the pack's signing? (strong form of X58 step 4 / X60)

**Hypothesis.** Two readings compete:

- **A.** At pack-only events its pulls are reactions to the public cancel wave: a book-reader hazard. A public rule can
  copy them, which bears on proposal 2's residual control.
- **B.** They come from a slower path of its own feed: locked to the event with a fixed offset, whatever the wave does.
  Then its residual control at those events is private.

**Why it fits.**

- Pulls run 2.8x the busy-phase control before the pack signs and 5x after, with no zero-fill FAK signature, and its
  ladder is hit in 37% of those transactions (iteration 5).
- Critique 2 shows its general re-join hazard is slow and stochastic. So if its pulls at pack events are fast and
  tight, they are not that hazard.

**Test.** For each pack-only burst (and, for contrast, each wallet-led burst) on the dev blocks, server clock:

1. Record:
   - p = the pack's first signing;
   - w = the onset of the public wave (the first non-own cancel on the consumed side after p);
   - u = its own first pull on that side.
2. Regress u - p on w - p across events. A slope near 1 with a tight u - w means wave-locked (A). A slope near 0 with
   a tight u - p means event-locked (B).
3. Time-shift null and busy-phase control, as in `pack_event_pulls.py`.
4. Also measure:
   - the share of pulls with no wave before them;
   - the hit rate when a wave comes without a pull.

**Data.** `tommy_cs2_near`, `calldata_dev` for 10-31 (54 pack-only events) and 11-01 06-12.

**Signature if true.**

- (A) u - w is tight (IQR under 30 ms) and the slope is about 1. The protective part is public, so proposals 1 and 2
  can include it.
- (B) u - p is tight and independent of w. Its feed sees those events late. The residual control is private and
  belongs in the account.

### 5. The client's timers: a 1.5-s cancel → re-post cooldown as part of the ladder state machine and as a software fingerprint (new; C8 / X66 strong form)

**Finding.** The intervals between consecutive own action bursts on the live books are mostly smooth, with one sharp
spike:

- 160 intervals fall in 1,500-1,520 ms, against 6-18 per 10-ms bin around them.
- 80% of them are a cancel followed by an add, and 87% are on the same side.
- A smaller spike sits at 500-510 ms.
- Burst phases modulo 500 / 1000 ms are uniform, so there is no global clock.

**What those 153 "cooldown" cancels look like.**

- They are single-level and single-book: 0% have an own cancel in another book within 5 ms, against 2.1% for other own
  cancels. They are not feed fan-out events.
- They are mildly protective: the others' best on that side worsens by 1c or more within 500 ms in 9.2% and improves
  in 1.3%. Other own cancels: 18.0% and 17.4%. Random times: 1.2% and 1.2%.

**Hypothesis.** The client has a per-level re-entry timer of 1.5 s, beside the FAK-return re-post at 1.04 s. Each
level's lifecycle is post → (fill or cancel) → wait T → re-post. These timers create deterministic absence windows,
which are part of why its presence is patchy (critique 3). They also give the deep-state branch of proposal 1 its
clock.

**Test.**

1. **Trigger.** For each cooldown cancel, look at:
   - the age of the cancelled level (a constant age means a refresh timer);
   - the change of the others' best in the previous 100 ms;
   - an own fill on that side.
2. **Re-post price.** Where does the re-post land relative to the cancelled price and to the others' best?
3. **Presence model.** P(own level at gap g) as a function of the time since its last own cancel or fill at that level.
   This is own state, used for the policy description and declared. Check whether it lifts the live presence AUC above
   0.72 (critique 3).
4. **Siblings.** Scan every CS2 book in `tommy_cs2_near`, GRID markets included, for cancel → re-add at 1,500 ± 10 ms
   with consistent size fingerprints. Map those sizes to wallets through calldata. Any other wallet with the same timer
   runs the same software.

**Data.** `tommy_cs2_near`, `calldata_dev`, `calldata_pub`.

**Signature if true.**

- A level-age or event timer explains most cooldown cancels, and the time-since-own-action state lifts presence and
  deep-state price.
- A sibling with the same 1.5-s timer in other events or games widens the decision sample and maps the operator's
  coverage.

## Overlap with earlier panels and the ledger

- **Proposal 1** is the strong form of X43 (pair-capped join), X63 (band hazard) and B3. It changes the unit (deep
  states, three scoring units) and adds own inventory, the pair cap against its own opposite top, and book age.
- **Proposal 2** is new. X57 step 4 bounded a wrong maker leg with the right takes; this bounds the right maker leg with
  a public hedge.
- **Proposal 3** is new: a maker anchor from sibling markets, which A4 / E8 never tried.
- **Proposal 4** is the timing-lock form of X58 step 4 and X60.
- **Proposal 5** is new. It is a client timer as a state-machine element and as a C8 / X66 fingerprint.
- The event clock (X37 / X38 / X53) remains the only route to the taker input, and nothing here replaces it. Proposals
  2 and 4 say how much of the outcome needs that input.

## How to reproduce my quick numbers

The scripts are in
`C:/Users/Remote-BEAST/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/tommy_iter5mech/`.
They read development data only, and they use the same own-level fingerprint as `band_hazard.py`.

| Script | What it computes |
| --- | --- |
| `price_rules.py` | Join, cap, spread and penny rules; persistence by pre-burst state; the time-split tree; the inventory skew |
| `lag_view.py` | Join fit against book age |
| `sm_sim.py` | The public hysteresis state machine |
| `exposure.py` | Sole-best episodes and how they end |
| `asym.py` | Re-join hazard up and down |
| `live_presence.py` | Live level-presence AUC from the gap to others' best |
| `period.py`, `period2.py` | Action-interval histogram and the 1.5-s spike |
| `cooldown.py`, `cool_sync.py` | Direction, prior activity and cross-book synchrony of the cooldown cancels |
| `hedge_ceiling.py` | Oracle maker leg plus a public completion hedge, against per-market PnL |
| `capital.py` | Start size against concurrency and the cash proxy |
| `ph_check.py` | CLOB `/prices-history` as an anchor |

Caveats:

- **Small live sample.** All live numbers come from one development block, 7 token-0 books, about 3 hours.
- **The hedge proxy is optimistic.** It fills fully at print + 1c.
- **The fingerprint misses ramp sizes.** It omits event sizes other than 100 / 68 / 58 / 54, so a few own levels
  count as others' (probe agreement was 90.8%).
