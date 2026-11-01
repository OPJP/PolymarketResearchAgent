# Panel, iteration 16: mechanics and on-chain forensics

Reviewer lens: how an order is built and routed. That covers the pre-signed ladder, which leg of a decision carries which size, the
state the bot keeps between decisions, the fan-out to wallets, the sibling wallets, and what each of these leaves on chain and in the
book.

Data used. Everything is development data from before H:
- `it16/cdfull_10-2{0,1,2}.parquet`: complete calldata of the operator's taker txs, including the maker structs. Joined to
  `it14/dcfit14_pred.parquet` and `it15/l2ord_*`, it gives 73,577 operator taker orders of 10-20..22 with exact original size, limit
  and signing ms. The 19-h size phase of 10-20 is left out of every size table.
- `.cache/re/btc5m-bot/fills.parquet` (order hashes, maker fills, PnL), `binance_1s.parquet`, `ptb.parquet`.
- `it13/hf_dl/pm_trades_*`: capture trades with server ms and tx hashes.
- `it16/tapes/*`: data-api taker tapes, used for the W4 / W5 legs. Also `it16/size16_pred_cd.parquet`.

Nothing sealed was read and `.cache/live/sealed/` was not opened. `sealed.py btc5m-bot` at 09:21 UTC 11-01 reported "released none;
future examined until 2026-10-31 00:00".

My scripts and their small intermediates are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p16m\`:
- `occsize.py`, `state.py` .. `state4.py`, `fanauc.py`, `width.py`, `flip.py`, `opening.py`, `seed.py`, `lockin.py`: the size state;
- `smachine.py`: an oracle ladder for the state machine;
- `early.py`, `early2.py`: window phases;
- `w4win.py`, `xmS.py`, `xmrole.py`: XM;
- `hidden_size.py`, `fak.py`, `gapload.py`, `phase.py`, `makers.py`: checks;
- `../p16m_layout.py`: ladder layout.

Apart from this file I wrote nothing to the workspace.

## Critique

### 1. The size state is the bot's decision memory, not its inventory

Findings 8 and 9 condition the size on the operator's realized large net so far (fills <= m - 2 s). A simpler state does better
everywhere: S = the side of the operator's most recent large order (any wallet, strictly before the order).

Here S counts only large orders that matched, because lost large legs are not yet in the record.

Within-wallet AUC of each state for the large class, 10-20..22:

| wallet | all orders: S (last large side) | sent large net | realized large net | realized, >= 2 s lag | fan-out followers: S | realized |
|---|---|---|---|---|---|---|
| GF | **0.742** | 0.711 | 0.706 | 0.697 | **0.853** | 0.802 |
| XM | **0.815** | 0.762 | 0.756 | 0.736 | **0.881** | 0.794 |
| DS | **0.698** | 0.660 | 0.655 | 0.636 | **0.846** | 0.768 |

S leads on every day and for every wallet:
- +0.027 to +0.076 over all orders;
- +0.04 to +0.11 among fan-out followers (`state4.py`).

The sign of the latest large order beats any net, including the net of original sizes.

Why it matters: pre-registration 10(b) failed (0.314 vs 0.356 for the menu), but it tested a realized-lean controller on the
replica's simulated fills. It did not test this controller. A replica knows its own last large order exactly, without simulating any
fill. The question becomes whether the replica's memory agrees with the operator's, which is a question about the transitions of S
(critique 2).

### 2. Where the size coin lives: fast fan-out followers, and the transitions of S

I classified every leg by the gap to the previous operator leg on the same (window, outcome):
- fast follower: less than 150 ms;
- sequential follower: 150-400 ms;
- first leg: otherwise.

P(large) by class and by the leg's side relative to S (with / no S yet / against):

| wallet | fast follower | sequential follower | first leg |
|---|---|---|---|
| GF | **0.866** / 0.627 / **0.157** (n 6,271) | 0.220 / 0.157 / 0.035 | 0.342 / 0.263 / 0.068 |
| XM | 0.801 / 0.579 / 0.067 | 0.600 / 0.521 / 0.077 | 0.668 / 0.487 / 0.123 |
| DS | 0.623 / 0.316 / 0.044 | 0.156 / 0.110 / 0.027 | 0.052 / 0.025 / 0.010 |

**DS -> GF pairs on one outcome.**
- With a gap under 50 ms, GF is large 52.5% and DS 4.6%.
- At 50-150 ms, GF is large 49.8%.
- At 150-400 ms, GF is large 9.4%.

The fast follower carries the large order. The sequential follower, sent after the first leg has matched, is mostly a small refill.
The "multi-leg events carry the large legs" result of iteration 16 mixes these two classes.

**The fan-out width does not depend on S.**
- DS-led decisions get a fast follower 13.8% / 14.7% / 13.8% of the time, against S / with no S / with S.
- From the dcclock14 decision features the width is only weakly public: AUC 0.62 (GF-led 0.63), fit 10-20 and scored on 10-21..22.
- Whether any leg of a DS-led decision is large: public 0.657, S alone 0.696, both 0.762 (`width.py`).

**Large orders outside fan-outs.**
- On 10-21..22, GF's large orders are 48% fast followers, 43% single first legs and 9% sequential followers.
- The hidden-DS-leg proxy (a DS maker-first remainder at L or L - 1 c within [m0 - 1, m0 + 4] s) precedes 11.0% of GF's large single
  legs and 10.1% of its small ones.
- So GF's large singles are not mainly fan-outs whose DS leg disappeared.

**Flips: commitment hysteresis.**
- Of 13,819 GF and XM legs against S, 8.7% are large (a flip).
- The flip rate falls with E, the large shares the operator has sent on S since S was last set: by quintile of E 0.210 / 0.076 /
  0.039 / 0.023 / 0.011 (AUC 0.78 inverted).
- It also falls with time in the window (0.152 -> 0.041) and with the number of large orders so far (0.148 -> 0.050).
- On legs with S, E has no effect (AUC 0.51). Once committed, S locks (`flip.py`).

**The seed.**
- The first large order of a window comes at a median of 9.3 s (q25 4.1 s, q90 37.7 s).
- It is on GF 71% of the time, and in 56% of windows it is its carrier's first order of the window.
- Its side matches GF's first order of the window 76% of the time, and the majority side of the first 10 s of decisions 72%.

**Lock-in.**
- S at time T matches the sign of the final large net 0.64 / 0.71 / 0.77 / 0.84 / 0.88 for T = 15 / 30 / 60 / 120 / 240 s.
- There are 2.0 flips per window on average; 253 of the 749 windows with a large order have none.

Reading. Once S is known, the size of an order is close to a fixed function of its slot class and S. Three coins remain, and all of
them act early in the window:
- the fan-out width, about 14% of decisions and 0.62 from public data;
- the side of the seed;
- the flips while commitment is still low.

The current account's "lean-relative coin conditioned on the realized lean" is mostly this state machine.

**A caution from my own oracle ladder (`smachine.py`).** I took the true decisions, sides and fills, and made an order large exactly
when it is a fast follower on the S side, with S seeded by the first fast follower. That gives window-net r 0.548 to 0.578, against
0.573 for all-small. A state machine that ignores the singles and the true seed does not beat all-small.

### 3. The window lean is set early and paired late; a uniform imbalance target averages across the change of sign

Per window (756 windows, the three wallets' taker orders with realized fills), the large net has:
- r +0.344 with the decision-side imbalance of the first 60 s;
- r -0.354 with the imbalance after 60 s;
- r +0.005 with the imbalance of all decisions.

The window net with two-phase inputs, out of sample. Fit on 10-20, scored on 10-21..22, Pearson / Spearman, reverse split in brackets:

| target <- inputs | uniform weights | two phases (< 60 s, >= 60 s) |
|---|---|---|
| window net <- TRUE sides | 0.465 / 0.437 (0.544 / 0.547) | **0.548 / 0.515** (0.636 / 0.614) |
| window net <- dc14 sides at the true decision times | 0.421 / 0.410 (0.487 / 0.495) | 0.432 / 0.429 (0.498 / 0.489) |
| large net <- TRUE sides | 0.209 / 0.098 | 0.426 / 0.419 (0.453 / 0.405) |
| large net <- dc14 sides | 0.086 / 0.139 (0.188 / 0.235) | **0.250 / 0.307** (0.287 / 0.294) |

With public sides, most of the two-phase gain on the total net disappears, but it stays on the large stream. The binding piece is
the side accuracy of the first-minute decisions that seed S:
- the sign of the summed dc14 side before T matches S(T) 0.78 at 15 s and 0.69 at 60 s;
- iteration 13's finding X124 put the [0, 15) s decisions at 0.738 against the spot tick.

### 4. W4 and W5 are treated two ways

The frozen tape features count W4 / W5 prints as market activity (FINAL_RULE, known limitations). Findings 15-16 count the same legs
as the operator's own occupancy, which a public replica may not use. Both cannot be right.

The brief excludes only the studied wallets' prints. W4 / W5 prints are public:
- on chain at block time;
- in the capture's trade messages (server ms and tx hash) once the tx is mined.

At the window level, XM's leg count follows W4's. With W4's taker legs per window from the data-api tapes:
- Spearman 0.861;
- partial rank correlation 0.558 after DS + GF legs (`w4win.py`).

XM is the slot after W4 (finding 11). X5 and X66 have been open since iterations 5 and 8. This needs the examiner's ruling before
more work goes into XM.

### 5. Checked and not supported (so nobody redoes them)

- **Within-second phase of the operator's matches.**
  - It is the market-wide rhythm: at a 1000-ms period the crowd's Z is 128-202 and the operator's 4-12, with the same decile shape.
  - The 10-ms lock (phase 5 ms) is shared with the crowd, so it is a timestamp artifact (`phase.py`).
- **FAK versus GTC by size.**
  - Large remainders rest: 25.8% of 6,666 large orders with a taker remainder are later maker-filled, against 31.5% of small ones.
  - There is no order-type split (`fak.py`).
- **The fan-out gap as an acknowledgement latency.**
  - DS -> GF fast-follower gaps: q10 6 ms, median 30, q90 110.
  - Spearman with the market-wide tx count of the last second is 0.09.
  - The median gap is 28 ms for large followers and 32 ms for small ones.
  - No response-coupled posting is visible (`gapload.py`).
- **Ladder layout.**
  - Large and small orders at one cent are signed in the same cent group, large about 0.4-0.6 ms after small (median residual; 214 of
    228 DS and 201 of 216 GF groups within ±3 ms).
  - There is no separate large pass, so the size is chosen at submission (`p16m_layout.py`; this confirms iteration 1).
- **Counterparty makers.**
  - The operator's taker txs carry 147,134 maker orders from 1,679 makers; the top 10 hold 20%, and nearly all are BUY (mint)
    orders.
  - No dominant market maker exists whose outages could serve as a natural experiment for condition 2 (`makers.py`).
- **XM's maker remainders.**
  - They carry 26% of XM's window-PnL variance and are uncorrelated with its taker part (r 0.03).
  - A taker-only XM tracker therefore caps at about r 0.86 against XM's total, so the maker part does not bind condition 7
    (`xmrole.py`).
- **S as a public sign.**
  - S agrees with sign(BTC - priceToBeat) 0.47 of the time, with the move since the open 0.59, and with the last 5-120 s moves
    0.55-0.58.
  - Flips go against the move since the open: P(toward the new side) is 0.385, against 0.54 for continuing large orders
    (`state3.py`).
  - S is not a public sign of BTC.

## Proposals (ranked by the chance to close the gap)

### P1. The size controller is a hysteresis state machine on the bot's own sent orders: decode its transitions and run it on the replica's own memory (new state definition; strong form of pre-registration 10(b), E5, X124 and X54)

**Hypothesis.** In each window the bot keeps two pieces of state:
- a large-side state S, the side of its last large order;
- a commitment E, the large shares sent on S since S was last set.

A leg is large with high probability when it is a fast fan-out follower or a GF / XM single on S. S flips with a probability that
falls with E, and the first large decision seeds S early in the window. All of this is the bot's own sent state, so a replica holds
it exactly. The binding coins are the seed, the early flips and the width.

**Why it fits.**
- Critique 1: S beats every net-based state, by +0.04 to +0.11 inside fan-outs.
- Critique 2:
  - fast followers are large 0.87 with S and 0.16 against;
  - flips fall from 0.21 to 0.01 across quintiles of E;
  - the width does not depend on S.

**Test.**
1. **Freeze the state definitions on 10-20; score on 10-21..22 and on the reverse split.** Compare S, the sent net and the realized
   net per wallet x slot class.
   - Signature: S leads by 0.03 or more in every cell, on both splits.
2. **Fit the transitions on 10-20.** Use a logistic model or a tree of depth 3 or less, per wallet x slot class, for:
   - P(large | on S);
   - P(flip | against S, E, t, |knee move|, p);
   - P(seed side | public state at the first decisions: dc14 side, knee move, opening ask);
   - P(fast follower | decision, public).

   Report each AUC on 10-21..22.
3. **Complete S with the lost large legs.**
   - In the event-level L2 of 10-20 (`l2ingest15b`), find menu-large bid insertions at L on o, or the ask at 1 - L on the
     complement, within 0-40 ms of a would-be match with no trade (the ins9b fingerprint).
   - Attribute them by elimination and add them to the S sequence.
   - Re-measure the AUC of S and the flip rate.
   - Signature: some apparent flips are preceded by an unseen large order on the new side, and the fan-out AUC rises above 0.88.
4. **Replica on the true decision record of 10-21..22** (timing and carrier known):
   - dc14 side;
   - size from step 2, with S_own and E_own taken from the replica's own sent orders;
   - 500 redraws and a deterministic argmax.

   Report:
   - the share of legs where S_own = S_operator;
   - the AUC of S_own for the large class;
   - the window-net r, against the menu's 0.356 and pre-registration 10(b)'s 0.314.

   Then repeat with the frozen knee-clock hazard choosing the decision times, and feed E[size] into the mix14 tracker.

**Data.**
- the complete calldata of 10-20..22;
- the dcclock14 frame;
- for step 3, the capture's event-level L2 for 10-20.

**Signature if true.**
- S agreement of 0.75 or more of legs;
- AUC of S_own of 0.70 or more for GF and XM;
- window-net r of 0.45 or more with the dc14 side on the true decisions (the menu plus 0.05 or more), on both halves.

**If false.** The coin sits in the seed side and the early flips. Report their entropy in bits per window and the lock-in curve as
condition 5's wall component, in place of "a lean-relative coin conditioned on the realized lean".

### P2. XM is W4's overflow: get a ruling on W4 / W5, then allocate XM from the sibling's public legs (strong form of X5, X66 and X161 step 1)

**Hypothesis.** XM gets a leg when DS, GF and W4 are busy. W4's legs are on chain and in the public trade feed. A rule that uses them
from the moment they are public recovers the operator's local decision density for XM without any of the studied wallets' own
prints.

**Why it fits.**
- Critique 4: at the window level XM's leg count follows W4's legs, at a partial rank correlation of 0.558 after DS + GF legs.
- Finding 11: 36.6% of XM-led first legs follow a W4 / W5 leg within 300 ms (median gap 45 ms).
- 41.7% of all XM taker orders have a W4 / W5 leg in the 300 ms before them.
- Finding 16: the public hazard misses the true decision density (XM oracle 0.48, against 0.53-0.56 with the true density).

**Test.**
1. **Ask the examiner whether W4 / W5 count as "the wallet" or as other traders.**
   - As the wallet: own state, kept out of every feature.
   - As other traders: allowed in market-activity features and in the baseline.

   Then make the frozen rule consistent either way; today it is both.
2. **If they count as other traders: rerun thin16's allocation with public inputs only.**
   - Inputs: the clock features, the frozen hazard sums, and W4 / W5 legs in the last 300 ms.
   - The W4 / W5 times come from the capture's trade messages at server ms, attributed by tx hash, and are usable from block time
     + 1 s.
   - No DS, GF or XM prints.
   - Fit on 10-17..19 (or 10-20) and score once on 10-21..22.
   - Report XM's one-vs-rest AUC, the oracle XM PnL r and the redraw ceiling, per half.
3. **Pre-register an XM tracker.**
   - Target: the pooled mix14 target x P^(XM) from step 2, summed over the bins.
   - Executed at 2 s or more (convention a).
   - Score XM's window-PnL r on 10-21..22 and on its halves.

**Data.**
- the data-api taker tapes (W4 / W5 legs);
- the capture trades with tx hashes;
- `hazbins16`, `fills.parquet`.

On the exam lot, W4's fills come from public chain data.

**Signature if true.** XM oracle of 0.50 or more, and a tracker of 0.47 or more on both halves, using W4 / W5's public legs.

**If the ruling says W4 / W5 are the operator.**
- Record XM's PnL part of condition 7 as bounded by the take coin (finding 16).
- Remove W4 / W5 prints from the condition-2 baseline (X5).

### P3. The window lean locks in during the first minute: an early-window side model and a two-phase target for the tracker (condition 5's Spearman; strong form of X124 and X121)

**Hypothesis.** The first minute's decisions set the window's large lean (the seed, and the flips while commitment is low), and the
later decisions pair against it. A target that does two things ranks windows better than mix14's uniform hazard imbalance:
- it weights the first-minute decisions by a side model built for them;
- it treats later decisions as pairing flow.

**Why it fits.** Critique 3 shows two things.
- With true sides, two phases lift the window net from 0.465 / 0.437 to 0.548 / 0.515.
- With dc14 sides, two phases lift the large stream from 0.09-0.19 to 0.25-0.31, but the total net only by +0.01 to +0.02.

The gap between the two is the accuracy of the early side. X124 measured 0.738 in [0, 15) s.

**Test.**
1. **Measure dc14's side accuracy by phase** (0-15 s, 15-60 s, after 60 s) and on the seed decisions, 10-20..22.
   - If the early side is weaker, fit an early-window side model on 10-17..19 and score it on 10-20..22. Its inputs are the
     window-open state: spot against priceToBeat at the open, the opening ask, and the first knee moves.
2. **Pre-register mix14 with a two-stream target.**
   - Large stream: L(t) = w_e x Σ over bins before 60 s of h x (2q - 1) with the early model, minus w_l x the later imbalance.
   - Small stream: as in mix14.
   - The 60-s boundary is fixed now. Fit the weights on 10-17..19 and score once on 10-20..22: Pearson and Spearman, halves,
     per wallet.

**Signature if true.** Spearman and Pearson of 0.50 or more on both halves, and GF at 0.47 or more.

**If false.** The early side is the limit. Report the side accuracy of the seed decisions as the binding term.

### P4. Is the fast follower a second trigger? Time the width decision, the last size coin once S is known

**Hypothesis.** A fast follower, 5-150 ms after the leader on the same outcome, is a second decision fired by a later message: a
second venue's tick, or the continuation of the spot microprice. It is not one decision posted twice. If so, the width is public at
its own time, and the size coin reduces to S.

**Why it fits.**
- The follower gap is broad (q10 6 ms, median 30, q90 110 ms).
- The gap does not track CLOB load, and large and small followers have the same gap distribution.
- The width does not depend on S, and public data at the leader's decision give it only 0.62.
- Finding 2: the tick lock of GF-led legs is shifted by about 20 ms.

**Test.** Use the 6,008 DS -> GF fast-follower pairs of 10-20..22.
1. Build per-venue PSTHs on the dcclock14 exchange clock: spot book ticks, and USD-M, OKX and Bybit trades. Align them at the
   follower's arrival m_GF - 150 and at the leader's m_DS - 150.
2. For each follower, find the latest knee-band event before its arrival minus 80-110 ms, and test whether that event comes after the
   leader's event.
3. Fit P(follower | the knee-band move between the leader's knee and the gap) on 10-20, and score it on 10-21..22.

**Signature if true.**
- The follower locks sharply, with a half-maximum width of 60 ms or less, to an event that comes after the leader's event in 60% or
  more of pairs.
- The width AUC at the follower's own cut is 0.75 or more.

**If false.** The follower is locked to the leader's event at a constant posting offset. Then the width is a coin of a single
decision, and P1 step 2 carries it as such.
