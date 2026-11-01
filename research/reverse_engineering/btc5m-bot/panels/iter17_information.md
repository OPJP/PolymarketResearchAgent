# Panel, iteration 17: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

Written 11-01 ~11:00 UTC.

## Data used for my checks

Development data only. I ran `sealed.py btc5m-bot` at 10:42 UTC: no lots released, future examined until 10-31 00:00, and the
current block (11-01 06-12) is development. Nothing was opened from `.cache/live/sealed/`, from any capture day at or after H,
or from another strategy's workspace. Every process stayed under 300 MB.

- **Public capture (pre-H days):** `it13/hf_dl/btc_2026-10-18/20/21/22.parquet` (Binance rows), `pm_trades_2026-10-20..22`.
- **Investigation frames (10-20..22):** `it14/hazard14_scored.parquet`, `it14/dcfit14_pred.parquet`, `it14/dcclock14_frame.parquet`,
  `it15/l2ord_*`, `it16/cdfull_*`; `it17/oot17b_pred.parquet` (the 11-01 record).
- **Live lab, development block 11-01 06:58-10:00, through `iter_live`:** `btc5m_bnspot2` and `btc5m_bnusdm2` (rec_bn15 v2, one
  process).
- **data-api `/activity`, type TAKER_REBATE, for DS / GF / XM / W4:** only rows whose fee day is before H (the row paid at
  10-23 00:00 carries 10-22's fees).
- **Gamma:** fee and reward fields only, for three BTC 5m listings: 10-09 00:00, 10-21 00:00 and 11-01 07:00.
- **File names only:** the Hugging Face file listing of `Fahri-5/updown-5m-polymarket-raw`.
- **Wayback CDX:** the capture dates of the Polymarket rebate docs.

Scripts are in
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p17i\`:

| script | what it checks |
|---|---|
| `burst_transit.py`, `burst_capture.py` | receive-stamp lag in message bursts: the laptop's feed vs the capture's collector |
| `usdm_gauge.py` | whether the same process's exchange-stamped USD-M messages measure that lag |
| `knee_lag.py`, `cap_notrade.py` | lag in the knee band of the 11-01 orders; side accuracy by subset, laptop vs capture |
| `phase_take.py`, `phase_m.py` | whether the take is phase-locked to the whole-second grid (Chainlink observation grid) |
| `size_notional.py` | Binance aggressive notional as an input to the large class |
| `tier_wv.py` | the operator's taker-rebate tier arithmetic under the official weighted-volume rule |

## Critique

### 1. Pre-registration 11 was scored with an instrument that is late exactly at the knee

The laptop's Binance receive stamps lag in message bursts, and the knee is a burst. Out-of-time scoring and every sub-100-ms
live measurement inherit this lag.

**The measurement.** For each spot trade message, the residual is its transit (receive − exchange T) minus the trailing 60-s
median transit. This is the clock that pre-registration 11b used. The table gives the median residual (q90 in brackets) in ms,
by how many messages arrived in the previous 100 ms:

| messages in prior 100 ms | 0 | 6-10 | 11-20 | 21-40 | 41-80 | > 80 |
|---|---|---|---|---|---|---|
| laptop, `btc5m_bnspot2`, 11-01 07-10 | −2.2 (0.6) | −0.4 (14) | 2.3 (76) | 7.5 (146) | 17 (172) | 51 (229) |
| capture, 10-20 07-10 | 0 (0.2) | 1 (3) | 2 (4) | 3 (7) | 6 (11) | 9 (23) |
| capture, 10-18 (a Sunday) | 0 (0.5) | 0.5 (2) | 1.2 (3.5) | 3 (6) | 5.5 (10) | 11 (28.5) |

The receive spread inside same-T trade groups (one match fanned into several messages) is also wider on the laptop: q50 / q90 /
q99 2.5 / 11 / 40 ms against 2 / 7 / 16 ms in the capture.

**The lag is on the laptop, not on Binance's side.** rec_bn15 records spot and USD-M in one process. In the same moments the
spot-trade residual and the USD-M residual (USD-M messages carry E) correlate at r = 0.78 (27,059 pairs within 10 ms, 07:00-08:30).
The spot residual rises with the USD-M residual: median −1 / 9 / 28 / 72 / 173 ms when the USD-M residual is < 5 / 5-20 / 20-50 /
50-100 / > 100 ms. Subtracting the concurrent USD-M residual takes the spot q90 from 42 to 9.6 ms (q99 from 311 to 138).

The cause is shared backlog on this host, which carries many agents' processes. Binance's publishing is not the cause; the
capture's collector does not show it.

**It sits where the decisions are.** Of the 999 out-of-time orders:
- 52.5% have a spot trade stamped in the knee band [m − 320, m − 200] (36% at random instants);
- the knee-band residual is q50 / q75 / q90 0.6 / 21.5 / 139 ms (random instants −2.0 / −0.9 / 5.3).

The book stream has no exchange stamp, so its lag in book-only bursts cannot even be measured. Accuracy falls in both subsets:

| subset | laptop, 11-01 | capture, 10-21 |
|---|---|---|
| a spot trade in the knee band | 0.79 | 0.876 |
| no spot trade there | 0.72 | 0.814 |

**What it explains.** A book event the laptop stamps late falls after the cut, so the model sees less of the move. That is the
conservative direction, not a leak. Three readings of iteration 17 follow from it:
- The post-hoc "+25 ms gives 0.804" (finding 1) is the size of this lag, not evidence that the 0.80 bar fails.
- The "knee moved from 265 to 255 ms" (finding 2) has the sign this bias produces.
- PolyBolt and the CLOB channel are recorded by different processes with different backlogs, so their comparison on
  laptop-received clocks (X166, Λ = 10 / 0) is confounded. Only producer and server stamps are clean.

So the fact that would decide exam readiness is still unknown: whether the frozen route transfers to the new regime. My checks
point to the instrument as the cause of the failure. They do not prove the route holds.

### 2. The clean out-of-time instrument exists, and the open question is access

The public capture's pinned revision (sha f848a77c, lastModified 11-01 01:16 UTC) lists `btc/2026-10-31.parquet` and
`polymarket/2026-10-31.parquet`. That day holds two development blocks (00-06, 12-18) of the new regime, on the collector clock
the model was fitted on. It is the only route on which the exam itself is scored.

Iteration 13 (finding 18) left these files unopened until "the question whether a footer-only row-group selection is allowed is
settled". The 11-01 file will presumably follow overnight. Its 06-12 block is the same 999 orders that pre-registration 11
scored, which gives a same-orders, two-clocks comparison.

### 3. The capture's own clock is late in bursts too, by less, and that also lowers conditions 2 and 3

In the capture the book is stamped as receive − 131, which is about the quiet-time transit. In bursts the collector lags a further
+6 to +13 ms (median; q90 +11 to +31) against trade T. This is larger than, and opposite in sign to, the ~4 ms bookTicker-before-trade
lead that X167 corrects for.

At the decision clock the gain moves by ~0.05 AUC per 50 ms of cut and the side by ~5 points per 25 ms. Correcting the stamps
toward Binance's exchange time is the brief's own PIT definition: published at or before e on the publisher's clock.

### 4. The rate of the size class may be set by a public incentive the investigation never priced: the taker-rebate tier

Official rule (docs.polymarket.com/programs/taker-rebates):
- weighted volume wV = trade size (USD) × (1 − entry price) × 2.3 for crypto, so wV = 32.9 × the taker fee;
- 30-day wV of $10M or more is Obsidian, with a 50% rebate; Diamond (≥ $4M) pays 44%;
- tiers are recomputed daily at 00:00 UTC, and a tier is lost after a grace period.

**What the rebate rows give.** From TAKER_REBATE rows (fee = 2 × rebate; fee days before H), the 30-day wV on 10-20 was:

| wallet | DS | GF | XM | W4 | pooled |
|---|---|---|---|---|---|
| 30-day wV | $3.9M | $2.4M | $4.3M | $1.4M | $12.0M |

No single wallet ever reached $10M; XM's maximum was ~$5.8M on 09-22. Yet every wallet was paid exactly 50% on 10-10..22. So
either the tier is computed on the pooled operator volume, or a bonus multiplier applies.

**Why it matters.** On the pooled reading the operator sits ~15-20% above the threshold, and the rebate is 85-90% of its profit
(iteration 6). Losing 6 rebate points costs ~12% of income. The investigation's "configuration" (the class rate, the size phases,
XM's role) would then be a volume controller.

There is one suggestive alignment, with n = 2. Pooled wV slid from $12.33M (10-14) to $11.61M (10-18). The size phases, which buy
extra fee volume at no better gross return (iteration 14, finding 20), came on 10-19 01-13 h and 10-20 19 h.

### 5. Checked, so nobody redoes them

- **No bot-specific phase lock to the whole-second (Chainlink observation) grid.**
  - Rayleigh R of operator first-leg m0 mod 1000 ms is 0.0185 (n 57,630), against 0.0208 for all other traders' txs (n 1.08M).
    The mean phases are 445 and 395 ms.
  - The take rate in the top 1 / 3% hazard bins varies 0.075-0.121 / 0.059-0.081 by 100-ms phase, with no structure beyond the
    market-wide one.
  - The 1-s modulation is shared by every trader: it is co-occurrence, not an input of this bot. RTDS Chainlink is served
    0.7-1.9 s after its whole-second observations, too late for any knee-scale gate.
- **Binance aggressive notional does not pick the large class where the coin binds** (10-21..22, 43,780 orders, exact classes).
  - Univariate AUC of signed spot notional toward o over [m − 820, m − 200] is DS 0.603, GF 0.605, XM 0.612. The 250-ms
    microprice gives 0.574 / 0.594 / 0.603.
  - Added to a 3-feature logistic (fit 10-21, scored 10-22): DS 0.644 → 0.696, GF 0.640 → 0.650, XM 0.577 → 0.587.
  - GF and XM, where the coin is, gain ~0.01. DS's size16 public model is already at 0.77.
- **Market fee and reward parameters did not change across the regimes.** Gamma for 10-09, 10-21 and 11-01 07:00 BTC 5m listings
  shows the same values: feeSchedule rate 0.07, takerOnly, rebateRate 0.2, makerRebatesFeeShareBps 10000, rewardsMinSize 50,
  rewardsMaxSpread 4.5, feeType crypto_fees_v2. Whatever moved the class rate is not a per-market fee field.
- **A sealed-boundary hygiene point.** The laptop clock runs ~1 s behind true time (receive − T ≈ −0.64 to −1.16 s with
  ~0.13 s of transit). `Writer` files by `time.time()`, so about the first second after every development-to-sealed boundary
  (e.g. 11-01 12:00:00-12:00:01) is filed in `dev/`, and `iter_live` filters by the same laptop stamp. Cut every live analysis
  by server stamp (`s`, `T`, `E`) and window start, and drop the last 2 s before each such boundary.

## Proposals (ranked by the chance they close the gap)

### P1. Score the frozen exam route out of time on the capture's own 10-31 (and 11-01) day files, on the collector clock (strong form of X164; replaces pre-registration 11 as the out-of-time test)

**Hypothesis.** dc_exam14 (side), dc_hazard14 (presence at the e cut) and the touch price transfer to the new regime: side ≥ 0.80
per taker order, as on 10-20..22 (0.837). Pre-registration 11's 0.718 / 0.752 was the laptop's burst lag (critique 1), not the
regime.

**Why it fits.**
- The laptop lags +17 to +51 ms (median) and +150 to +230 ms (q90) at > 40 messages per 100 ms, against +6 to +11 ms (q90 +11
  to +28) in the capture.
- The lag concentrates at the knee (q90 139 ms vs 5 ms at random instants).
- Accuracy falls by 8-9 points in both the trade and the no-trade subset.
- The post-hoc +25-ms optimum equals the lag.

**Test.**
1. **Access rule (get it ruled now, together with X170).**
   - From each 10-31 file's footer, take only the row-group ranges of `timestampMs` / `exchangeTimestampMs`.
   - Decode only row groups whose whole range lies inside a development block (10-31 00:00-06:00, 12:00-18:00). Never decode a
     row group that straddles a boundary.
   - Drop windows that do not start in a development block.
   - This is the access `final_rule.evaluate()` already uses on exam lots ("only overlapping row groups are read"); it is tighter
     because it excludes straddlers.
2. **Decision record.** All operator taker txs of the two blocks (census31_17 sampled 1,500 per block; cdfull16 needs ~2-3 min
   per block). Match ms from the capture's trade rows by tx hash, as on 10-20..22.
3. **Pre-register and score once, nothing refitted.**
   - Side per order and per wallet, against the 0.80 bar.
   - The hazard's gain over the book-aware baseline at the e cut, against the 0.05 bar.
   - Price within a tick.
   - Per wallet and per block, with the placebo at m ± 3 s.
4. **When the 11-01 file appears (expected about 11-02 01:00), rescore the post17 record.** The 06-12 block holds the same 999
   orders, now on the collector clock: the same-orders, two-clocks comparison. Add 18-24 as its second half.

**Data.** The capture's 10-31 / 11-01 files (needed columns only, about 600 MB per day by range requests, as in iteration 15), and
Polygon calldata through drpc.

**Signature if true.**
- Collector-clock side ≥ 0.80 (pooled; DS / GF ≥ 0.80) on 10-31 and on the 11-01 rescore, while the same 999 orders read
  0.72-0.75 on the laptop.
- The cut-shift optimum sits at 0 ± 10 ms.
- The decision knee returns to 260-265 ms.

The rule then needs only its version parameters restated (class rate, large list, XM's role) before the exam. Nothing in its
decision routes changes.

**If false.** The side is ≤ 0.76 on the collector clock too. The decision side changed with the version, and dc14 must be refit on
the new regime before any exam on future blocks. h1 lies between the regimes and is then at risk as well. That is worth knowing
before spending an exam round.

### P2. Restamp the live Binance spot book with the same process's exchange-stamped messages, and audit every live finding that used a receive clock (new; makes the live lab usable for the coming blocks)

**Hypothesis.** The live lab's receive stamps carry a shared, burst-correlated host backlog. The exchange-stamped messages recorded
by the same process measure it at each instant. A physics-only restamp removes it.

**Why it fits.** Critique 1: r = 0.78 between the spot-trade and USD-M residuals, and the spot q90 falls from 42 to 9.6 ms after the
correction.

**Test.**
1. **Pre-register "11c" before any score.** For every spot bookTicker message:
   - t_ex = receive − (trailing 60-s median trade transit + r(t)), where r(t) is the residual of the nearest USD-M message (E) within
     ±10 ms of receive;
   - fallback: the nearest spot-trade residual within ±20 ms; otherwise 0;
   - then cut at X* = m − 260 exactly as dc_exam14.
2. Score once on the 11-01 06-12 record, with the cut-shift scan reported alongside. The +25-ms optimum should collapse to 0.
3. **For the next development blocks (11-01 18-24, 11-02 00-06 / 12-18), start a minimal recorder.**
   - Raw frames, stamped with `time.time_ns()` right at the socket read; no JSON parsing or gzip in the receive task; its own
     process at above-normal priority.
   - Subscribe to spot `bookTicker` + `trade` and USD-M `bookTicker` on one connection, so the gauge shares the path.
   - Add an SNTP offset log every 10 s against two public servers, so the laptop clock is absolute.
   - Use the Writer, a hard stop, and keep under 100 MB of memory.
   - Bar: spot residual q90 ≤ 15 ms at > 40 messages per 100 ms (the capture's level).
4. **Re-read every sub-100-ms live result that used receive time:**
   - knee17;
   - the laptop-received legs of pbview17 / X166;
   - the 10-31 rec_lab6 / rec_exam7 kernels (kernel7, lam11, msg8);
   - fol17's live parts, if any.
   Results on server, producer or exchange stamps stand.

**Data.** `btc5m_bnspot2` and `btc5m_bnusdm2` (on disk), the next development blocks (recorder).

**Signature if true.**
- 11c lands within ~2 points of the collector-clock score of P1.
- The new recorder's burst residuals match the capture's.
- The live lab can then carry pre-registered out-of-time checks every development block, which conditions 6 and 7 need.

**If false.** The restamp moves the score by < 1 point and the optimum stays at +25 ms. Then the lag lies in the book stream's own
path (bookTicker is pushed on a different internal queue) or the regime moved the side, and P1 decides between those.

### P3. Re-stamp the capture's Binance book to exchange time in bursts, and refit conditions 2 and 3 on the corrected clock (strong form of X167; the opposite-sign and larger term)

**Hypothesis.** In bursts the capture's book rows are stamped ~6-13 ms (median) and up to ~30 ms (q90) later than Binance published
them. Every decision-clock feature therefore misses the last part of the move that the bot saw. Correcting it raises the
reference-feed model and leaves the market baseline unchanged.

**Why it fits.**
- Critique 3. The two clock effects are opposite: the ~4 ms bookTicker-before-trade lead (X167) and this burst lag.
- In bursts the burst lag dominates, so the net stamp is late, in the conservative direction.
- Condition 2 stands at +0.024 at the block second and +0.058 [0.050, ...] at the decision clock. It is decided at the scale of
  tens of ms.

**Test.**
1. Estimate the capture's per-message backlog from trade rows: r(t) = (receivedTs − exchangeTs) − its trailing 60-s median.
2. For each book row: Te' = received − 131 − r_near(t), where r_near is the nearest trade within ±20 ms of receive.
   Conservative variant: subtract the bookTicker lead (median 4 ms) as well.
3. Rebuild dcclock14 / hazard14 frames with Te'.
4. Pre-registered refit on 10-17..19 and one score on 10-20..22, plus the reverse split:
   - side per order;
   - the hazard's gain over the book-aware baseline at the e cut;
   - the block-second presence unit of target_metrics.
5. Non-inferiority first: the frozen model scored on Te' inputs without a refit.

**Data.** The capture day files on disk (`it13/hf_dl/btc_*`), the existing frame builders.

**Signature if true.**
- Side +1 to +2 points.
- Decision-clock hazard gain +0.01 to +0.02, with the block bootstrap lower bound rising.
- If the block-second unit reaches ≥ 0.05 over the capture-aware baseline, condition 2 is met on a clock an examiner cannot
  fault as a leak: every feature is cut at Binance's publication time, which is ~110 ms before the arrival.

**If false.** Gains under 0.005 bound the clock as a source of the condition-2 deficit. The deficit then belongs to the take coin
(X72), with a number attached.

### P4. The class rate and the operator's configuration as an Obsidian-tier volume controller on pooled weighted volume (strong form of X53 and X33 with the official wV rule; E5 for the configuration schedule)

**Hypothesis.** The operator manages the 30-day weighted taker volume (wV = 32.9 × taker fee) across its wallets to stay above
$10M (Obsidian, 50%). The size phases, the class-rate changes and XM's move to resting orders are that controller's actions, timed
to the daily 00:00 UTC tier update and to the volume leaving the 30-day window. Which decisions are large stays a coin; how often
is public arithmetic.

**Why it fits.**
- Critique 4: no wallet ever reached $10M alone, yet all were paid 50%; the pooled operator was at $11.6-12.3M.
- The rebate is 85-90% of profit.
- The size phases buy fee volume at no better gross return, and came after the pooled slide to $11.61M on 10-18.
- The new wallet W5 (105 / 210 menu) is what a volume ladder or a level-up-bonus farm would add. The bonuses are $10 / $50 /
  $250 / $1,500 / $7,500 / $25,000, and XM's $1,500 row on 07-15 is the Platinum bonus.

**Test** (development fee days only; never the rebate rows paid 10-24..10-31, which carry sealed days' fees).
1. **Tier unit.** From all TAKER_REBATE rows since each wallet's first day, compute the daily realized rate (rebate / previous
   day's fee) from on-chain taker fees.
   - Date each step of the climb (3 / 8 / 18 / 32 / 44 / 50%) and each bonus row.
   - Ask whether the steps follow per-wallet or pooled wV crossings ($2k, $20k, $200k, $1M, $4M, $10M), and how long the grace is.
2. **Controller.** Daily pooled slack, projected one day ahead: S(d) = wV_30(d) − $10M − (the wV leaving the window tomorrow).
   - Over 08-22..10-22, test whether the configuration change points fall where S(d) is small. These are the size phases, the arm
     switches, XM's role changes (10-13 14:10, 10-14) and W4's start.
   - Test the daily class rate per wallet against S(d) (Spearman), with a 2,000-draw date-rotation null.
3. **Rule changes.** Diff the Wayback versions of docs.polymarket.com/programs/taker-rebates (captures 08-07, 09-18, 09-19,
   10-21) and /programs/maker-rebates (08-07, 08-14, 09-18) for category-weight, bonus-multiplier or grace changes. Fetch any later
   capture to date a change around the regime switch.
4. **The new regime.** XM's MAKER_REBATE rows on fee days 10-09..13 (60-share component on) against 10-14..22 (off): is the
   resting stream paid by the maker program?

**Data.** data-api `/activity` with types TAKER_REBATE and MAKER_REBATE (cached adapter), on-chain fills of development days, the
official docs, and Wayback CDX (no key).

**Signature if true.**
- The rate steps track pooled crossings.
- Change points fall in the lowest-slack decile more often than under the rotation null (p ≤ 0.01).
- The daily large share rises as slack falls (ρ ≤ −0.3).
- The rule can then state the class rate as a function of public slack instead of a version constant, which is worth something
  in condition 5's window-level rate and in the h1 version statement.

**If false.**
- Steps follow per-wallet crossings with a long grace, or no change point aligns with slack. Then the configuration is not
  incentive-driven: record E5's last route as tested.
- The 50%-without-$10M puzzle still needs a recorded explanation, either a multiplier or account linking.

## Sources

- Polymarket docs, taker rebates: https://docs.polymarket.com/programs/taker-rebates.md (fetched 11-01): the tier table,
  wV = trade size × (1 − entry price) × category weight (crypto 2.3) × bonuses, daily update at 00:00 UTC, grace on downgrade.
- Polymarket docs, programs index: https://docs.polymarket.com/trading/taker-rebates, and third-party summary
  https://startpolymarket.com/learn/polymarket-taker-tiers/ (thresholds only).
- Hugging Face API, file names only: https://huggingface.co/api/datasets/Fahri-5/updown-5m-polymarket-raw/tree/main/btc and
  `/polymarket`.
- Wayback CDX: https://web.archive.org/cdx/search/cdx?url=docs.polymarket.com/programs/taker-rebates.
- Gamma `/markets?condition_ids=...` (fee and reward fields of three development listings).
