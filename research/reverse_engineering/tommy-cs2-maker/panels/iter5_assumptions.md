# Panel, iteration 5: assumption breaker (fresh eyes)

Lens: what the investigation takes for granted that may be false. That covers the unit and the target, what "absent"
means, the latency built into every public test, how the outcome metric is built, and whether VALIDATE represents the
exam.

## What I read and what I ran

I read `BRIEF.md`, `NOTES.md` (iterations 1-5), `state.json` (H1-H60, catalog through X69, components,
`target_metrics_notes`, `live_split`), `FINAL_RULE.md` and the twelve panel files of iterations 1-4. No EXAM or
wall-audit files exist.

All my checks are small, read-only passes over files already in `.cache/re/tommy-cs2-maker/`: `probes`, `census_bursts`,
`orders`, `per_market`, `calldata_all`, `activity_dev`, `events_sel`, `selection_scores`, the tapes, `pack_orders`, and
for the 10-31 14:50-18:00 development block `level_events_dev`, `calldata_dev` and `tommy_cs2_near` through
`live.iter_live`.

- All of it is development data. BUILD and VALIDATE (16-22 Oct) appear only as aggregates.
- I made no network fetch. I opened, listed and counted nothing sealed.
- Scripts: `attn.py`, `cap.py`, `path.py`, `inv.py`, `gaps.py`, `order_check.py` in
  `C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`.
  The probe checks were inline one-liners on `probes.parquet`. The pack set is the makers in `pack_orders.parquet`.

## Critique: assumptions that look false or unproven

### 1. "Wallet-absent" is read as "blind", but the maker ladder dodges the pack's sweeps

The census (X58) labels 80% of the informed 3c+ bursts wallet-absent because there is no wallet take. From that, the
statement concludes that the input "covers a subset of event types" and that the ladder "stays exposed at the pack's
events it does not detect". The investigation's own uncensored probe table says something else. Split the 29,341 sweep
probes by who swept:

| Split | Taker of the sweep | Probes | Wallet resting at the swept level |
| --- | --- | --- | --- |
| BUILD | pack signer | 4,275 | 12.0% |
| BUILD | any other taker | 9,125 | 31.0% |
| VALIDATE | pack signer | 4,261 | 18.7% |
| VALIDATE | any other taker | 11,680 | 33.7% |

- **By depth.** The gap holds at every depth: at k = 1-2 levels into the sweep, 40-43% against 11-22%.
- **Controlled.** A logit with depth, |level - stale touch|, prints in the last 10 / 60 s, elapsed time, price, price²,
  own net and |own net| gives an odds ratio for a pack sweep of 0.21-0.26 on BUILD (CI [0.23, 0.28]) and 0.43-0.48 on
  VALIDATE ([0.44, 0.52]).
- **Away from its takes.** The gap holds more than 30 s from any wallet take in the event: OR 0.23 [0.20, 0.26] (BUILD)
  and 0.42 [0.37, 0.47] (VALIDATE). So it is not the known pull at its own takes. 17.8% of pack probes lie within 3 s
  of a wallet take, against 2.5% of the others.
- **By market.** Presence is lower at pack sweeps in 83% of the 213 markets that have both kinds.
- **The control is conservative.** "Other takers" include the fast informed avoiders, so the real gap between informed
  and uninformed sweeps is larger still.

So at the pack's events the ladder is present about half as often (VALIDATE) to a quarter as often (BUILD) as at
ordinary sweeps. The wallet does something before most pack events, even though it takes in only about 20% of them.
"It cannot see round wins" and "it sees them but does not take, and moves its ladder" predict the same take census but
opposite probe tables. The probe table favours the second reading, or a third one: it follows the other makers'
cancels (critique 2).

This changes which events X37 / X38 must clock, and it changes the exit component. The ladder is not left exposed
wholesale; it is hit at the pack sweeps it fails to dodge.

### 2. Every test that calls its presence "not a public function" used state at least 2 s old

- **Probes.** The probe models (X56: AUC 0.669 against 0.663 for activity) use prints at block time and "others' touch
  seen 2 s earlier".
- **Replays.** The margin replay, X44 and the oracle bound use observations at least 2 s old. X44 also tried LAT 1 s,
  but still on the block clock.
- **The delay window.** Every informed FAK waits about 1.04 s between signing and matching (X25 / X27). A maker who
  reacts within a few hundred ms to anything public that appears in that window is invisible to all of these tests.

The live block shows that such public signals exist and that the wallet moves with them. Pack takes with no wallet
take within 3 s (n 54, 10-31 14:50-18:00, server clock, consumed side, [pack sign, match)):

| First cancel inside the window | n | Wallet maker hit in the pack's tx |
| --- | --- | --- |
| Another maker cancels first, then the wallet (own-size cancel) | 14 | 50% |
| Wallet first | 4 | 50% |
| Others cancel, the wallet does not | 24 | 33% |
| Wallet only | 1 | 1 of 1 |
| Nobody | 11 | 18% |

- **Timing.** When both cancel, the wallet's first cancel comes a median 15 ms after the first non-own cancel (p25
  +4 ms, p75 +82 ms). The first non-own cancel comes a median 60 ms after the pack signs (p25 14 ms).
- **Reading.** Others usually move first, and the wallet follows within tens of ms, far inside the 1.04-s window. A
  home-connection rule at 100-300 ms would still be about 700 ms ahead of the match.
- **Coverage.** In 24 of the 38 events where others cancel, the wallet does not. A public follower could therefore be
  better protected than the wallet, which matters for the outcome item (it must track the wallet, not beat it).

Iteration 4's mechanics panel proposed a live-book replay with a trigger on the public cancel wave (its proposal 1,
step 5). It was not run. The conclusion in `FINAL_RULE.md` ("its resting ladder is not a public function", "the
missing input for the outcome is the wallet's quote presence") is therefore conditional on 2-s staleness. It is not yet
a finding.

### 3. The outcome target is an activity-driven, joint-leg quantity, and item 5 has no co-occurrence baseline

Per-market facts, 16-22 Oct:

- **Margin.** Wallet PnL is the pair margin: corr 0.84 with pairs × (1 - pair cost), margin variance 40.6k against
  residual variance 15.0k. The top 10 of 229 markets carry 59% of the total PnL.
- **Activity alone.** Market activity alone tracks the wallet's per-market PnL far better than any executable replay.
  The wallet's own prints are excluded.

  | Public quantity, in-play | BUILD P / S | VALIDATE P / S |
  | --- | --- | --- |
  | Count of non-wallet taker prints | +0.43 / +0.20 | +0.52 / +0.38 |
  | Non-wallet taker USD | +0.39 / +0.17 | +0.42 / +0.36 |
  | Total variation of the 10-s last price | +0.40 / +0.23 | +0.49 / +0.29 |
  | Net displacement (end - start) | -0.01 / -0.02 | +0.19 / +0.14 |

- **Single legs.** Neither of the wallet's own legs, settled alone, tracks its total.

  | Leg | BUILD P / S | VALIDATE P / S | Sum |
  | --- | --- | --- | --- |
  | Its maker fills only | +0.39 / +0.50 | +0.38 / +0.34 | -$0.1k / +$3.9k |
  | Its taker fills only | +0.15 / -0.05 | +0.09 / +0.13 | +$5.2k / +$4.1k |

Three consequences:

- **(a) Co-occurrence.** A rule that earns a stable, small positive margin per public print reaches Pearson about 0.5
  on VALIDATE without decoding anything. Item 5 needs the same co-occurrence baseline the brief demands for presence:
  a "constant × public in-play prints" pseudo-PnL, and the partial correlation of the rule's PnL given it. Without
  that baseline a pass could be co-occurrence, which the brief calls a worse failure.
- **(b) Single-leg ceiling.** A perfect maker-only decode settles near +0.38 / +0.34 on VALIDATE. Item 5 cannot be met
  without the taker leg, because the PnL lives in pairs formed across the two legs (take, then the K - L re-pair). The
  wall account should say "outcome = taker input" with this number, and maker-replay effort should go to price, not
  outcome.
- **(c) Why replays score near zero.** The replays fail because their margin per unit of action is negative or
  unstable under 2-s latency (critique 2). They do not fail because they pick the wrong markets: their paired volume
  already ranks markets like the wallet's (Spearman 0.79-0.92).

### 4. VALIDATE may not represent the exam's league mix (the only passing component)

- **Unseen leagues.** Of the 91 non-GRID VALIDATE events, 16 are in leagues absent from BUILD, and 8 of them were
  traded (Circuit X 8 / 10, ESL Challenger League 0 / 6).
- **v3 on them.** On those 16 the frozen v3 scores AUC 0.844 with recall 0.625. On seen leagues it scores 0.958 with
  recall 0.786.
- **Turnover.** Tier-3 leagues turn over within days. PGL, Stake Pulse, GLuck and CyberClash appear only in BUILD.
- **Exam risk.** The h1 / h2 and future-block lots will hold more unseen leagues than VALIDATE did. The league rate is a
  lookup of the wallet's past labels, and on new leagues it falls back to the tier rate.
- **Already measured.** X31 found a league-free variant: a lagged pack-presence rate scores 0.941 on new leagues
  against 0.914. It was not adopted because the two were "comparable" on the VALIDATE mix.

### 5. Smaller points

- **Fees are part of the taker economics and of "where the PnL comes from".**
  - Every wallet taker order pays a fee of 0.050 × shares × p(1 - p): median 0.0504, p5-p95 0.050-0.054. That is
    $3,550 on $155k of taker USD, or 2.3%.
  - The next day's `TAKER_REBATE` row is exactly 50.0% of the previous day's taker fees (10-17 $543 → $271.7; 10-21
    $962 → $481.1).
  - `MAKER_REBATE` is 0.31-0.33% of the previous day's maker USD.
  - The D4 split (+$4.0k maker, +$9.1k taker) is gross of all of these. The taker leg nets about +$7.3k, and the
    effective hurdle of a take is premium + 2.5% × p(1 - p) per share.
- **Merge loop.** 2,129 MERGE rows, inter-arrival p10 / p50 / p90 = 6 / 8 / 308 s, median $348. While active it merges
  about every 8 s, which is the "merge timer" the next steps want to model.
- **The plant reading is weak.**
  - The per-map GLM regresses burst shares on round-win and plant differences. Every 3c+ move follows some scoring
    change, so "absent bursts follow round wins" (p 3e-9) is close to tautological.
  - The plant term rests on 196 bursts over 64 maps (p 0.03).
  - The bursts' own timing shows no plant-then-round-end pairing either. Led bursts are followed by another burst
    within 15-45 s in 13.5% of cases, against 10.8% for absent bursts.
  - Led bursts are rare within 5 s of a previous burst (4-6% against 14-20%). Those are the pack's follow-ons.
- **Non-stationarity.** The dodge odds ratio moves from 0.23 (BUILD) to 0.42-0.48 (VALIDATE), and the per-day
  selection gains are +0.034 / +0.094. Two VALIDATE days are a thin base for exam-level claims. The 10-31 live rules
  (join 67%, pull 11-19 ms) come from a third period, after a size-mix change (CS2 100 shares 89% → 78%).

## Quick checks that came out negative (so nobody redoes them)

| Idea | Check | Result |
| --- | --- | --- |
| **Single attention.** One watcher, one stream at a time. | Observed / expected chance of a take in a concurrent event B within ±60 / 120 / 300 s of a take in A, against the same statistic for pack bursts | Wallet 0.79 / 0.78 / 0.78, pack 0.76 / 0.76 / 0.84. Absent share flat in the number of concurrent events. No attention signature. |
| **Own-state gating of takes.** Already long, or a cooldown. | Net position in the bought token before the burst | Led median +62 / +18, absent +50 / +60 shares (MWU p 0.45 / 0.08). Led share flat across net bins (13-20%). |
| **Refractory period after a take.** | Led share by time since its last take in the market | 15-17% at 0-10 s, 22-28% at 10-45 s, 11-12% beyond 600 s. No refractory gap. |
| **Capital-release trigger of the size ramp.** | Size step-ups (161) within 5 / 15 / 30 / 60 s after a MERGE, against random times in the event | 3.1 / 6.8 / 12.4 / 21.7% against 5.1 / 9.4 / 13.5 / 21.7%. Not supported. |

## Proposals, ranked by the chance they close the gap

### P1. The maker's protection is a sub-second public reaction inside the 1-s delay (strong form of X56 / X57; iteration-4 mechanics P1 step 5, never run)

- **Hypothesis.** Its ladder dodges informed sweeps mostly by following the other makers' cancels, which appear on the
  public book a median 60 ms after an informed signing, about 1 s before the FAK matches.
  - If so, its resting presence is a fast public function, and the outcome failure of every replay is the ≥ 2-s
    latency built into it, not a private quote input.
  - The decodable part is a rule: join others' best, and pull a side within tens of ms of a non-own cancel near the
    touch.
- **Why it fits.**
  - Critique 1: odds ratio 0.23-0.48 at pack sweeps, far from its takes.
  - Critique 2: others cancel first in 14 of 18 events where both cancel, and it follows a median 15 ms later.
  - Band hazard: it reacts to changes in others' best within 100 ms, 22-37% of the time against a 2-5% null.
  - Probe presence is lowest exactly at the stale touch (0.18 against 0.27-0.30 deeper). Those levels are the first to
    be cancelled by a wave.
- **Test.** BUILD-live is the 10-31 12-18 and 11-01 06-12 blocks. VALIDATE-live runs from 11-01 18:00, per
  `live_split`.
  1. **Live probes with sub-second features.** Use the 153 live probes plus every new block.
     - Fit presence on the X56 2-s-stale features, then add delay-window features:
       - non-own cancels (count, shares) within 2c of the touch on that side in [match - 1,040, match);
       - time since others' best on that side last dropped;
       - others' best changes in the last 100 / 250 / 500 ms.
     - Report AUC with and without the delay-window features, with a market bootstrap. No own state; report it
       separately.
  2. **Ordering at every informed sweep.** Extend `order_check.py` and `pack_event_pulls.py` from pack-only takes to
     all informed sweeps:
     - the share of own pulls that follow a non-own cancel by 0-30 ms, 30-200 ms, or precede every non-own cancel;
     - a busy-phase control (retail BUYs), as in the iteration-5 correction.
  3. **Latency sweep of a public follower on the live book.** Run on the validated price-time engine, with own levels
     subtracted.
     - The rule: join others' best on both tokens, 100 shares, 5 levels 1c apart. Cancel a side when non-own cancels
       of at least X shares hit within 2c of the touch. Re-join after the match or after 1.5 s. Merge every 8 s.
     - Run it at λ = 25, 100, 250, 500, 1,000 and 2,000 ms.
     - Score informed-fill avoidance (pack share of its maker shares; the wallet's is 16-18%), pair cost, markouts
       against pack fills, and per-market PnL as markets accumulate.
  4. **Settle λ with the examiner before claiming anything.**
     - The brief's latency ≥ 2 s applies to the held-out return; item 5 says "strict fills".
     - Pre-register a home-connection λ (for example 250 ms) and report the whole curve.
- **Data.** `tommy_cs2_near`, `level_events_dev` (rebuild it per block), `calldata_dev` for every development block,
  the X57 engine, and the own-level fingerprint with event-specific sizes (the X56 step 2 fix).
- **Signature if true.**
  - Step 1 lifts live presence AUC from about 0.67 to 0.80 or more.
  - Step 2 shows most own pulls 0-200 ms after a non-own cancel.
  - Step 3: the follower's pair cost reaches 0.98 or below, with pack-fill avoidance at least the wallet's, at λ of
    250 ms or less, and both collapse toward the 2-s ladder (1.010) as λ approaches 1 s.
  - Then the maker presence and residual control are decoded as a public rule examinable on future blocks. The
    frozen rule's `evaluate()` should carry it for the future-block lot. "Not a public function" is withdrawn, and the
    wall account keeps only the taker input.
- **Signature if false.**
  - Delay-window features add less than 0.03 AUC.
  - Its pulls precede every non-own cancel at pack events, and the follower is hit like the 2-s ladder.
  - Then presence is private (a shared source with the fast makers), and the number goes into the wall account.

### P2. Price: the unit is one two-token quote, read at the bot's view time (strong form of H43 / H60 / X63)

- **Hypothesis.** The live join rule (67.4% within one tick, 37% exact, 5,853 bursts) misses for three reasons:
  - **(a)** It scores the two tokens independently. The bot sets one quote per market: the side whose book moved is
    re-joined, and the other side follows a pair-sum constraint (K - top), or keeps its own previous top.
  - **(b)** "Others' best just before" is read on the server clock at signing. The bot read the book a few ms to tens
    of ms earlier.
  - **(c)** 100 shares is a common size, so fingerprinting other makers' 100-share orders as its own shifts "others'
    best".
- **Why it fits.**
  - The misses sit in whole-cent clusters: -2c 7.4%, +2c 5.0%, ±3c 5-6%, -4 / -5 / -6c 1.4-3.5%. Fractional offsets
    are rare, so the reference is another whole-cent quantity, not noise.
  - Others' bid sums cluster at 0.95-0.99. The re-post top plus the FAK limit has a mode at 0.95-0.96.
  - It follows others' cancels a median 15 ms later (critique 2).
  - Pair-cap rules were scored only on 171 filled orders (H43), never on all re-quote bursts.
- **Test.** Run on all live re-quote bursts of every development block, per order, not per burst.
  1. Take the distribution of its own simultaneous tops, top_X + top_Y, after each burst. If the IQR is 1c or less,
     the quote is (mid, spread).
  2. The rule:
     - trigger side = the token whose others' best changed in the last 100 ms, and its new top = others' best;
     - other side = K - top (K fitted on BUILD-live) or unchanged;
     - deeper levels = top - rank × 1c by signing order within the burst.
     Score the share of orders within one tick and exact, against the 67.4% join.
  3. Anchor lag: use others' best at sign - Δ, for Δ = 0, 5, 10, 25, 50, 100 and 250 ms. The peak of the exact share
     dates its view latency.
  4. Fingerprint precision: in `calldata_dev`, every fingerprinted own add that later fills must have the wallet as
     its maker. Report precision and recall by size, and re-run steps 1-3 on the clean set.
- **Data.** `level_events_dev` (rebuilt per block), `tommy_cs2_near`, `calldata_dev`.
- **Signature if true.** At least 80% of orders within one tick with the joint rule. The exact share peaks at Δ ≈ 5-30
  ms, and fingerprint precision is at least 95%. The price component then passes on the future-block lot. It is not
  examinable on h1 / h2, which have no book; say so up front.
- **Signature if false.**
  - Own-top sums scatter widely, so the tokens are quoted independently.
  - The ±2-3c group stays after the lag and fingerprint fixes. Then test its own previous top (refill at the same
    price) as the second anchor.
  - Report the price ceiling as a wall number.

### P3. Give the outcome item an activity baseline and single-leg ceilings before building more replays (new; a metric and specification fix)

- **Hypothesis.** The wallet's per-market PnL is mostly how much action a market has, times a stable per-unit margin
  that needs both legs. So:
  - any rule with a stable positive per-unit margin co-occurs at about 0.5 Pearson;
  - no single-leg decode exceeds about 0.38 on VALIDATE;
  - the binding outcome input is the taker trigger, not the maker quote.
- **Why it fits.** Critique 3: public print count +0.52 / +0.38; maker-only fills +0.38 / +0.34; taker-only +0.09 /
  +0.13; PnL ≈ margin (0.84); the top 10 markets carry 59%.
- **Test.** BUILD and VALIDATE, history, then live.
  1. Add to `evaluate()` an outcome baseline: the per-market pseudo-PnL c × public in-play prints (c fitted on BUILD),
     and for every candidate rule the partial correlation of its PnL with the wallet's given public prints. Report
     Pearson and Spearman.
  2. Ceilings on the validated engine, using the wallet's own orders:
     - (i) its maker orders alone;
     - (ii) its taker fills alone;
     - (iii) both.
     Report each one's per-market correlation with the real wallet. Step (iii) bounds what engine error alone costs.
  3. For every replay, report per-unit margin (margin per paired share) by market, and its stability: the share of
     markets with a positive margin and the Spearman of margin with public prints.
- **Data.** `per_market`, `calldata_all`, tapes, `engine_check_rows`, the X57 / oracle replays.
- **Signature if true.**
  - Ceiling (i) stays below 0.5 in both splits, while (iii) stays near 1.
  - Then item 5 is reachable only with the taker trigger. Write it into the wall account as "outcome = taker input",
    with the ceilings, and move maker effort to price.
  - Any future "pass" must beat the activity baseline by a pre-registered margin.
- **Signature if false.** Ceiling (i) is at least 0.5, so a maker-only decode can carry the outcome, and P1's follower
  is the route.

### P4. The take is a decision on an event it sees, not a blind spot (strong form of X58 / H49; run after P1 step 2)

- **Hypothesis.** It sees most of the pack's events (it dodges them, critique 1) and takes only when its edge after
  the hurdle is positive. The hurdle is premium + 2.5% × p(1 - p) net fee per share, plus enough stale depth left at
  +1.04 s. At round wins every maker cancels, so nothing is left to take. At subtler events slow makers stay.
- **Why it fits.**
  - It dodges the pack's sweeps far from its own takes.
  - Its taker fill fraction is low (median 12%).
  - The premium-move dose-response is wallet-specific (H36).
  - Its led share is higher at prices 0.2-0.5.
  - The plant reading is statistically weak (critique 5).
- **Test.** History; descriptive, with own state reported separately.
  1. **Label "seen".** Label each pack-led burst "seen" if its probe levels on the exposed side are empty while the
     wallet had quoted that side in the prior 60 s, and "hit" otherwise. Wallet-led bursts are "taken".
  2. **Compare taken with seen-not-taken.** Use:
     - the remaining stale depth at the pre-burst ask (from the matched-order record);
     - the share of informed volume filled at +1.04 s;
     - the price level and the net fee;
     - the move at +10 / 60 s (the bot's value proxy; diagnostic only, not a rule feature);
     - match or map market, and game time.
     A take ⇔ edge > hurdle structure would separate them at AUC 0.8 or more.
  3. **Live check.** At pack events where its pull precedes every non-own cancel (P1 step 2), check whether a zero-fill
     FAK attempt follows (the X46 signature).
- **Data.** `probes`, `census_bursts`, `calldata_all` / `calldata_pub`, tapes; live `calldata_dev`, `level_events_dev`.
- **Signature if true.**
  - Taken and seen-not-taken bursts separate on remaining depth and edge net of the hurdle.
  - Seen-not-taken bursts are mostly round-end-like, with full cancel waves and little stale depth.
  - The feed may then be complete. "Covers a subset of event types" is withdrawn, the take rule becomes "event seen +
    edge > premium + net fee + a depth floor", and X37 / X38 clock both classes.
- **Signature if false.**
  - Seen-not-taken bursts carry as much stale depth and edge as taken ones.
  - Or P1 shows the dodges follow the public wave.
  - Then the partial-detector reading stands.

### P5. Freeze the selection rule for the exam's league turnover (new; protects the one passing component)

- **Hypothesis.** The exam lots hold more events in leagues without a fitted rate than VALIDATE did. There v3 falls
  back to the tier rate and scores about 0.84 instead of 0.96, and the gain over activity may drop below 0.05. A
  league-free key generalizes better.
- **Why it fits.** Critique 4: unseen VALIDATE leagues score AUC 0.844 with recall 0.625, and the leagues turn over
  within days. X31's lagged pack-presence variant holds 0.941 on new leagues.
- **Test.**
  1. From the listing projection that the brief allows for sealed units (event title / series / league, scheduled
     start, gridSeriesId; no outcome, volume or fill), count h1 / h2 non-GRID events by whether their league has a
     fitted v3 constant.
  2. Reweight the VALIDATE seen / unseen results to that mix to get the expected exam AUC and gain for v3, for the X31
     pack-lag variant, and for an organiser- or sponsor-level rate for new leagues. The candidates are brands such as
     Stake, 1win, NODWIN, PGL and DraculaN. Note that Stake Pulse, Stake Ranked, 1win and 1win Private Club are
     sportsbook-branded and almost always traded.
  3. Pre-register the choice before the first exam.
- **Data.** `events_sel`, `selection_scores`, `final_rule_v2_constants.json`, the listing projection.
- **Signature if true.** At least 30% of h1 / h2 non-GRID events fall in unseen leagues, and v3's expected gain falls
  near or below 0.05 while a league-free variant keeps at least 0.94 on unseen leagues. Freeze the league-free variant
  (or v3 with a league-free fallback) for the exam.
- **Signature if false.** Few unseen leagues. Keep v3.

## Overlap with the ledger and earlier panels

- P1 is the untested step 5 of iteration-4 mechanics P1. Here it targets the pull (protection) rather than an in-delay
  re-post, and it re-scores the X56 probes with delay-window features. The probe split by taker class is new.
- P2 extends H43 (171 filled orders) and H60 / X63 (join and band) to the joint two-token quote, the view lag and the
  fingerprint precision.
- P3 is new. The co-occurrence baseline exists for presence and selection in the brief, but not for item 5.
- P4 re-reads X58 / H49 with the probe dodge and the fee hurdle.
- P5 extends X31 / X61 with exam-lot turnover from the allowed listing projection.
