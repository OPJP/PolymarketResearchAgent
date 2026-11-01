# Panel, iteration 8: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and kept, what the per-market PnL is made of, and which public clock the quotes
follow.

## What I read and what I ran

I read:

- BRIEF.md;
- NOTES.md: iteration 8 in full, earlier iterations by section;
- state.json: the catalog A1-X117, the components and the target metrics;
- FINAL_RULE.md, by section;
- panels/iter7_mechanics.md, and the headings of every earlier mechanics panel.

There are no EXAM or wall-audit files. `tools/sealed.py tommy-cs2-maker` reports nothing released, the future
examined up to 10-31 00:00, and the current block sealed.

Every record I read is development data:

- `per_market`, `calldata_all`, `calldata_pub`, `orders`, `census_bursts` and `queue_replay_markets` (16-22 Oct);
- `dota_pub` (the 10-22 Dota public transactions);
- `universe_dota` (listing fields of the 10-22 Dota events);
- `results/dota_feed_align*.json`, `queue_replay.json` and `ladder_machine.json`;
- five OpenDota match records of the 10-22 maps and the Gamma markets of those events, both through the polyrea
  shared client and both already cached.

I opened nothing in `.cache/live/sealed/`, read no live recording and wrote nothing outside this file.

My scripts and their output are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\m8\`
(`burst_pull_replay.py` with its `.json`, `costcap.py`, `lagshape.py` and `dota_ladder_gamestate.py`). Each ran in
under 3 minutes and under 300 MB.

## Critique: what the investigation is missing or getting wrong

### 1. The outcome item is the maker-only pair margin, and the replays fail on pair cost, not on volume or protection

All numbers below are per market, over 229 markets, 16-22 Oct.

**The wallet's PnL is almost entirely its pair margin.**

- Settlement PnL against the locked margin `pairs x (1 - avg_a - avg_b)`: Pearson 0.84, Spearman 0.70. The margin
  carries 81% of the PnL variance.
- With the taker fills removed, the margin from maker fills alone is still 0.685 / 0.615 against the PnL. A rule
  that reproduced only the maker leg's per-market margin would clear the 0.5 threshold.
- The two legs offset each other inside a market: the maker leg's and the taker leg's settlement PnL correlate
  -0.87. The taker leg alone tracks the PnL at 0.12 / 0.05.

So the cross-market variation the exam scores is the maker leg's pair cost. It is not the informed taker leg, and it
is not the residual.

**The X44 queue replay gets the volume right and the pair cost wrong.**

| Replay vs wallet (K 0.97, L 1, LAT 2 s) | Pearson | Spearman |
| --- | --- | --- |
| Paired volume | 0.894 | 0.859 |
| Pair cost | -0.05 | -0.03 |

Against the informed bursts (`census_bursts`, Spearman):

- the replay's margin rate falls with the market's number of bursts (-0.22) and its PnL falls with it (-0.50);
- the wallet's margin rate rises with it (+0.12) and its PnL rises with it (+0.30).

**Burst protection is not what is missing.** I re-ran the X44 engine and pulled the replay's bid on the complement of
the bought team at every informed burst (`burst_pull_replay.py`):

| Variant (pull the complement for W s) | BUILD PnL corr | VALIDATE PnL corr | VALIDATE return |
| --- | --- | --- | --- |
| No pull (frozen X44) | -0.32 / -0.13 | -0.04 / -0.04 | -4.4% |
| Executable: from a feed subscriber's on-chain take + 2 s, W 30 | -0.41 / -0.17 | +0.13 / +0.10 | -3.7% |
| Executable: the same, W 120 | -0.46 / -0.32 | -0.11 / -0.03 | -5.3% |
| Oracle: from the burst's first signing, W 30 | -0.25 / -0.03 | +0.19 / +0.13 | -2.7% |
| Oracle: the same, W 120 | -0.20 / -0.11 | +0.05 / +0.04 | -3.1% |

The executable rows use the 20 subscribers, and subscriber prints in transactions with the wallet as maker are
excluded. The oracle rows use the label's +10-s move.

Even the oracle, which pulls at the start of every informed burst, cuts the losses but leaves the correlation near
zero. The pair-cost gap therefore sits in where and when the wallet's bids rest outside the bursts. That is the price
and lifetime of the quote, so the outcome item is the price item in disguise.

**An own-cost pair cap is not binding** (`costcap.py`). Take every maker order with its own fills known at least
2 s before signing, and add the wallet's own average cost on the other token to the order's price:

| Side the order is on | Orders | Pair sum p10 / p50 / p90 | Share at or below 0.98 |
| --- | --- | --- | --- |
| Short (it holds fewer shares of this token) | 14,156 | 0.80 / 1.00 / 1.22 | 0.455 |
| Long | 5,594 | 0.71 / 0.93 / 1.15 | 0.629 |

It quotes the short side 2.5 times as often as the long side, but at market levels, and it does not cap those bids
against its own cost. The "soft cap" of X81 concerns its two current bids, not its cost basis. So the per-market
margin is made by the timing and level of its bids, not by an accounting rule.

### 2. A public game clock exists for Dota, and nobody has applied it to the maker leg

Finding 24 put the feed's Dota messages on a per-map game clock: the offset D after `start_time` is 1035-1050 s on
four maps and 840 s on one. P4e alone gives the same D within 2 s, so D does not depend on the wallet. The clock was
used only for the taker leg.

I applied it to the wallet's Dota maker orders on the five 10-22 maps (`dota_ladder_gamestate.py`, 532 orders):

- The outcome is the order's limit minus the last public print on that token. Wallet transactions are excluded, and
  the print is taken at least 2 s before signing.
- The predictor is the order's team's kills minus the other team's kills in the 60 game-seconds before the order,
  with wall time = `start_time` + D + game time.

| Clock | Wallet's orders: Spearman | Other makers' resting orders: Spearman |
| --- | --- | --- |
| D (finding 24) | **+0.193 (p 8e-6)** | +0.136 (p 4e-22, 5,044) |
| D - 300 s | +0.04 | +0.00 |
| D - 120 s | -0.12 | +0.03 |
| D + 120 s | -0.02 | -0.03 |
| D + 300 s | -0.11 | -0.05 |

The wallet's mean deviation from the stale print, by net kills in the window:

| Net kills in the 60 s | Against its team | None | For its team |
| --- | --- | --- | --- |
| Mean deviation | -2.2c | -1.9c | -0.7c |

So the Dota ladder moves, relative to the last print, with the game state on the broadcast clock, and only on that
clock. Other makers do the same, more weakly. This is the first public input shown to move the maker's quote beyond
the stale print.

Dota is 54-57% of the wallet's fills on the 10-31 12-18 block (CS2-only coverage 0.43-0.46). The price item counts
orders, so this half of the exam's orders is where a game-state anchor can be built from public data. The game state
can be used at its broadcast time plus a delay (the brief's ESPN rule: a play at its wall clock plus at least 5 s),
historically from parsed matches and live from `tommy_dota_live`.

### 3. The price ceiling for a point anchor is about where the touch already is

Offsets of the validated adds from the touch (`ladder_machine.json`):

| Offset (cents) | +1 | 0 | -1 | -2 | -3 | -4 | -5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Share of adds | 13.6% | 27.8% | 10.1% | 5.7% | 7.3% | 8.6% | 13.0% |

The best one-tick window around any touch-relative point is {+1, 0, -1}, which holds 51.5% of adds. The touch already
scores 0.47-0.51, so no touch-relative anchor, fresh or lagged, can reach 0.8.

Most adds are single re-pricings (2,739 adds in 1,694 bursts), so the spread is not the ladder index. It is the
re-anchoring itself: (V - touch) varies by up to 5c. Only an input that predicts V(t) - touch can move the item, which
is why critique 2 matters more than further own-state machines.

The bimodality (0 / +1 against -5) still deserves one explicit test: a fixed-depth ladder of about 6 levels whose
bottom is re-filled at touch - 5 after its top is consumed. The frozen "extend" rule scored 0.089, which is low for a
13% mode. It may rest on the own-bottom label rather than on the touch.

### 4. Smaller points

- **The fan-out is not a poller at the wallet** (`lagshape.py`). The wallet's lag behind P4e on the same token
  (233 co-signs, CS2 16-22 Oct plus Dota 10-22) is peaked, not a uniform poll window: p10 / p25 / p50 / p75 / p90
  10 / 32 / 50 / 68 / 96 ms, excess kurtosis 3.0, KS against uniform p < 0.001.
  - The Python-client group (0x8a80528d, 0xddb6e624) is broad: p25-p75 140-286 ms.
  - The slow trio is broad and flat: p10 to p90 about 425-900 ms. That fits a slow consumer, or a poller of about
    0.5 s, on their side.
  - Earlier phase tests (iteration 3 and 6 mechanics, iteration 7 information) already excluded a phase-locked
    poller.
- **The X44 oracle variant (pulls at the wallet's own takes) changes almost nothing** (VALIDATE -0.01 / -0.02). So the
  take-time pull is not where the wallet's margin comes from either.

## Proposals, ranked by the chance they close the gap

### P1. Dota game-state fair value as the maker's anchor (strong form of B3 on the title with a public game clock; new)

- **Hypothesis.** The maker ladder's top is V(game state at broadcast time) - s, where V is a win probability from
  kills, gold and xp lead, towers, Roshan and game time. The private feed only makes the wallet a few seconds faster
  on the same V. For Dota, V can be built from public data at broadcast time plus 5 s. The same V drives the Dota
  takes: buy team X when V - ask > premium after a kill burst.
- **Why it fits.**
  - The feed's Dota messages follow kills of the bought team at one D per map (finding 24).
  - The market follows 3-14 s later.
  - The wallet's maker limit moves with recent kills, relative to the stale print, only at the true D (critique 2).
  - Other makers price the same state more weakly.
  - Dota is half of the recent fills.
- **Test.**
  1. Fix D per map without the wallet. Use the P4e-only alignment, which agrees within 2 s. Better, use the
     pre-registered calibration from `tommy_dota_live`: D = delay + `start_time` to horn, taken from game_time
     against receive time.
  2. Fit V offline on public OpenDota pro matches of development dates only (radiant_gold_adv, radiant_xp_adv,
     kills_log, objectives; outcome radiant_win), with no wallet data. A logistic or a small GBM is enough.
  3. On the 10-22 Dota maker orders, and on every development block's Dota orders, score the price item: within one
     tick of round_down(V(t - 5 s) - s), with s fitted on BUILD maps. Score it against the last print (0.476 within
     1c on these five maps), the live touch, and V at D ± 120 / 300 s as a placebo clock.
  4. Score the take hazard: P(take on X in (t, t + 1 s]) against ΔV over the last kill events, compared with the
     public-activity baseline.
  5. Run a Dota replay with V-anchored two-sided 10-share ladders that pull when |ΔV| > θ, and score its per-market
     PnL correlation.
- **Data.**
  - Cached OpenDota match records for the maps; `/proMatches` pages of development dates for the V fit, skipping
    sealed matches before storage;
  - `dota_pub` / `dota_pub_1031` calldata and `orders.parquet`;
  - `tommy_dota_live` on development blocks;
  - `dota_feed_align*.json`.
- **Signature if true.**
  - Within one tick on Dota orders rises clearly above the last print, to 0.65 or more, at the true clock and falls
    back at the shifted clocks.
  - Order limit minus last print regresses on V(t - 5 s) minus last print with a slope near 1.
  - Kill-burst takes beat the activity baseline on the take hazard.
- **Signature if false.** The game-state value adds at most the small kill effect (Spearman ≤ 0.2, within-tick gain
  under 0.03): the private V is not the public game state, and the Dota price item is then a quantified wall.
- **Extension to CS2.** The same test with a CS2 round clock: P3, and demo ticks if the user consents to X37.

### P2. Outcome by component knockout in the validated engine (strong form of X44 / X57 / D4)

- **Hypothesis.** The per-market pair cost, which carries the outcome item (critique 1), is set by either (a) the
  price level of the wallet's bids or (b) their resting windows (presence and pulls). An executable rule needs to
  copy only the carrier.
- **Why it fits.**
  - Pairs replicate at 0.89 and pair cost at about 0.
  - Oracle burst pulls do not fix it.
  - The own-cost cap is not binding.
  - The X57 engine assigns 88% of the wallet's real maker shares to the right transaction, so it can serve as the
    counterfactual machine.
- **Test (16-22 Oct, then BUILD-live with ground-truth lifetimes).** In the X44 / X57 engine, replay four quote sets
  per market:
  - A: the wallet's own filled maker orders, at their prices, from sign_ms to the last fill;
  - B: A's resting windows at the rule's anchor price (last observed best bid, or the touch on live books);
  - C: A's prices quoted continuously, with no wallet lifetimes;
  - D: B and C together (the frozen rule).

  For each set, report:
  - pair cost per market against the wallet's, and PnL corr;
  - a per-fill attribution of the replay-wallet pair-cost gap:
    - fills the replay takes and the wallet avoided, with their 60-s markout;
    - who the counterparty is: one of the 19 subscribers, or retail with 20 orders or fewer per address;
    - fills the wallet takes at deeper levels that the replay misses.

  On BUILD-live, swap A's windows for the ground-truth windows (adds, GT cancels and the validated label).
- **Data.** `calldata_all`, `calldata_pub`, `per_market`, `queue_replay.py` / `engine_check`; on BUILD-live
  `linked_adds_dev`, `gt_cancels_dev` and `level_events_dev`.
- **Signature.**
  - If B (wallet timing, public price) keeps the correlation at 0.5 or more, presence and pulls carry the margin.
    The outcome item then needs only the timing decode, which may follow the cancel-wave and V triggers.
  - If C keeps it, the price level carries it. Outcome and price are then one problem, and P1 / P3 are its route.
  - If neither does, the joint (price, time) choice carries it, and the attribution shows whether the avoided fills
    are subscriber-hit (private feed) or retail (an inventory or level policy).
  - This also gives the wall account a number: the share of the pair-cost gap that sits in subscriber-hit fills.

### P3. A CS2 round clock from P4e's round-win messages, and a round-score fair value for the CS2 ladder (new; strong form of X2 / X10)

- **Hypothesis.** In CS2 the private V is mostly P(map win | round score, side). The round score can be kept online
  from public data: P4e's on-chain round-win takes (at block time; P4e loads on round wins, dW +1.09) give round ends
  and winners about 2 s late. bo3.gg's per-round winner sequence is used only to validate the reconstruction on
  BUILD.
- **Why it fits.**
  - X2 rejected a round-score model only because the socket has no rounds for these events.
  - X10's alignment to bo3 used timing only. P4e's takes carry the round winner's team label, which turns the problem
    into a binary sequence alignment of about 24 rounds per map with strong labels.
  - The Dota result of critique 2 shows that the ladder follows game state when a clock exists.
- **Test.**
  1. On BUILD maps with bo3 rounds (91 maps, X8), align the sequence of teams P4e bought per round-win cluster to
     bo3's round winners. Report the alignment accuracy against a shuffled-label null.
  2. Fit the round-score table (P(map win | score, side, map)) from bo3 historical rounds of development dates, with
     no wallet data.
  3. On VALIDATE, score the wallet's CS2 maker limits (filled orders, and adds on BUILD-live) relative to the last
     print against V(score known at t - 2 s) - s. Score them against the last print, the touch, and a clock shifted by
     ±1 round.
  4. Score the same for 0x2005d16a's maker quotes as a placebo maker.
- **Data.** `calldata_pub` (P4e takes), bo3 per-round tables (`events_sel_bo3`, `bo3_taker_rounds`), `orders.parquet`,
  BUILD-live adds.
- **Signature if true.**
  - Sequence alignment well above the null, and 80% or more of rounds placed.
  - The wallet's limit deviation from the stale print correlates with the round-score V change at the true clock,
    and the effect is gone at ±1 round.
  - Within-tick gains over the last print on CS2 orders.
- **Signature if false.** P4e's round-win clusters do not align beyond the null. The CS2 V is then not on P4e's round
  stream, and the CS2 decode needs demo ticks (X37, with the user's consent).

### P4. The fan-out's delivery structure: one broadcast or a sequential sender (strong form of the iteration-7 `seqloop` check and X106 step 3)

- **Hypothesis.** The fixed subscriber lags (0, +35, +50, +100-230, +450-600 ms) come either from (a) one broadcast,
  where the lags are subscriber-side processing and network, or (b) a sender that serves subscribers in a queue: a
  webhook loop, a messaging bot, or a vendor-run executor. It matters for identifying and accessing the product. In
  case (b), the wallet's +50 ms is a position in a vendor's list, and its 61% "alone" takes may be messages that reach
  only the early positions.
- **Why it fits.**
  - The lag groups match client families only partly. The Python-salt wallets (0x8a80528d, 0xddb6e624, 0xc7097421)
    sit at +100-230 ms, but so does the TS client 0xf1ee4842, and the TS slow trio sits at +450-600 ms. So client
    speed alone does not set the groups.
  - The wallet's lag is peaked and not a poll window (critique 4).
  - Iteration 7 tested a fixed chain among only three wallets.
- **Test (16-22 Oct CS2 plus Dota, all 19 subscribers).**
  1. For messages with 3 or more co-signers, measure the pairwise rank-order consistency against a jitter null, which
     draws each subscriber's lag from its own marginal.
  2. Regress each subscriber's lag behind P4e on the feed's queue load: the number of distinct P4e or subscriber take
     clusters across all concurrent events in the previous 1 s, and the number of other subscribers acting on the
     same message.
  3. Correlate the lag residuals of two subscribers on the same message (common mode) against residuals on different
     messages.
- **Data.** `calldata_pub`, `dota_pub`, `cs2_cosign_scan.json` lists.
- **Signature.**
  - Sequential sender: 90% or more of pairs in a consistent order, positive slopes of 10 ms or more per queued
    message for the later positions, and no common-mode residual.
  - Broadcast: random order within jitter, no load slopes, and a common-mode residual only from the vendor's own
    publish time.

## Overlap with the ledger and the catalog

- **P1.**
  - What is new: the game-state V applied to the maker's quote and to the take hazard.
  - What exists: X24 / X42 / X88 cover the Dota takes against kills and the live recorder, and the pre-registered
    Dota calibration is the information panel's.
- **P2.** It uses the X44 / X57 engine. The knockout and the per-fill attribution are new. X17 / X44 / X82 / X76
  report correlations but never which quote component carries the pair cost.
- **P3.** It reopens X2 and X10 with a labelled sequence instead of timing alone. X8 / X50 used bo3 stats without a
  clock.
- **P4.** It extends iteration 7's three-wallet `seqloop` and X106 step 3 (common-mode shocks) to every subscriber
  and to queue load.
- **Not proposed.** X96 (salt PRNG with z3) stays as catalogued. Its payoff would be the uncensored ladder on h1 / h2.
