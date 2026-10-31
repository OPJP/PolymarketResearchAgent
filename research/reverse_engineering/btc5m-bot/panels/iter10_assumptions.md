# Panel, iteration 10: assumption breaker

Lens: what the investigation takes for granted that may be false. This round looks at four assumptions:

- the bot sees every venue tick;
- features aligned on exchange and server time are what the bot saw;
- the condition-5 ceiling (0.47-0.58) has the right size-feedback channel;
- the order salt is only a fingerprint.

I also closed three side questions with measurements.

## Data and checks

All checks used development data only:

- `calldata_sample.parquet` and `b1_orders_sample.parquet`: pre-H BUILD and VALIDATE hours.
- `it9/cd9.parquet` and `it10/cdall10.parquet`: 10-31 12-18, a development block.
- `btc5m_clob_raw2` through `iter_live`, 10-31 15:00-16:00 only.
- Six `eth_call` balance reads at pre-H blocks.

Nothing sealed was read, listed or counted, and `.cache/live/sealed/` was not opened. The calendar was checked with
`sealed.py btc5m-bot` at 22:43 UTC: no lots released.

The scripts are in the session scratchpad
(`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`):

| script | what it checks |
|---|---|
| `prng_triple.py`, `prng_gf2.py`, `prng_solve.py`, `prng_dfs.py`, `prng_selftest.py` | PRNG state recovery from the salts |
| `exhaust.py`, `mode.py`, `mode2.py`, `natexp.py` | how the size is chosen |
| `sib.py` | sibling wallets |
| `pmclock.py` | a Polymarket-message clock |

## Critique

### 1. The condition-5 ceiling assumes a feedback channel that was never tested

`lean10` re-draws sizes from the operator's net built from REALIZED fills. That makes race luck change later sizes,
and the result was the "edge of attainability" bound of 0.47-0.58. Two other channels would give the fixed-size
ceiling of 0.70-0.77 instead:

- the size reads the bot's intended position (the orders it sent);
- the size follows a slow regime that race outcomes do not touch.

Nothing so far separates these channels.

The large-share table `lean10` draws from was also estimated on FILLED orders. "Large" means filled shares above 1.5
times the modal size, so a large decision that lost its race counts as no large order. That table mixes the size
choice with the fill probability: large orders pay up 41% of the time and fill differently.

What I measured on the VALIDATE and BUILD calldata sample (13,289 orders, block clock; large = the day's larger menu
size):

- **Real persistence.** Take consecutive orders of a wallet 5-60 s apart in the same window. After a large order the
  next one is large 37 points more often than after a small one. Shuffling sizes within (wallet, hour, half-window)
  gives 17 points (99th percentile 22).
- **A slow component no own-net model has.** The shuffle null itself is 17 points: the large share moves a lot
  between hours and half-windows.
- **Other outcome only: no excess.** 22 points against a null of 17 (99th percentile 24). This fits own-net
  pyramiding on the same outcome.
- **A race-luck natural experiment.** I used the fill fraction of a large order to predict the next same-outcome
  size, with (wallet, hour) fixed effects (n = 1,345). Coefficients against a 50-99% fill: full fill -0.01 (se 0.20),
  at most 50% filled -0.20 (se 0.16). No detectable realized-fill feedback, but the test is under-powered at the
  block clock.

The bound is an assumption until a causal test runs. That is proposal 2.

### 2. The selection search assumes the bot sees every tick, at a fixed lag

Every onset, hazard and taken-versus-skipped AUC (`flag10b`, `evt10`, `crowd10`) is built on the recorded venue
updates. These are already coalesced to 20-30 ms, timed in exchange ms, and read on a 100-ms grid.

If the bot consumes a conflated or snapshot stream, or confirms a tick before acting, many flagged onsets never
existed for it. Several measurements fit that reading:

- the reaction kernels are about 100 ms wide;
- the hazard is front-loaded at the onset (23-26%, then 2-8% per 100 ms);
- the take rate rises with tick strength (17 / 28 / 50% by tercile);
- size-only depletion events sit at the base rate;
- the iteration-9 Rayleigh test found no phase lock on Polymarket's clock. A snapshot stream's phase lives on the
  venue's clock, which that test could not see.

Whether a tick SURVIVES 50-200 ms after its onset has never been a covariate. The hazard design labels a decision
anywhere in [t + 100, t + 600) on a 100-ms grid, so it cannot resolve survival. That is proposal 1.

### 3. Features are aligned on exchange and server time, not on the bot's time

**Per-venue lags.** The per-venue kernel peaks differ by 50-100 ms in exchange time:

| venue | kernel peak |
|---|---|
| Binance USD-M | [m - 300, m - 250) |
| OKX | [m - 350, m - 300) |
| Bybit | [m - 400, m - 350) |

That fits venue-specific transit to one unknown location.

**Polymarket view lag.** `lstar8`'s profile puts a rough bound on how stale the bot's view of the Polymarket book is,
which I call Λ:

- P(limit == o's ask at m - L) is flat at 73-75% for L = 30-190 ms;
- it falls from about 220 ms (66.7% at 240, 62.6% at 300, 49.1% at 500).

So the bot's view at its arrival time a = m - 150 is roughly at most 50-150 ms old.

**Consequences.** The investigation reads the "reaction 100-150 ms after the tick" as the bot's speed; it is probably
mostly transit. Features such as these mix information the bot had with information it did not yet have:

- "o's ask moved since the onset";
- "venues agreeing in [tau - 100, tau]";
- "crowd orders ahead".

The laptop's own round-trip times (Binance 347 ms) say nothing about the bot's. That is proposal 3.

### 4. The salt is used only as a fingerprint

The salt is round(Math.random() x Date.now()): salt / timestamp is uniform on [0, 1] with a maximum of 1.0. One process
signs the four wallets' ladders in loops, with up to 8 filled copies of one level in the same ms. If that generator
also drives the parts of the policy that look random, its state would expose those draws:

- the take probability of about 1/4-1/2 at an onset;
- the timer-like time-to-live of 0.1-1 s, with a long tail;
- the fan-out legs.

Nobody has tried. My test of the simplest form is negative (proposal 4); the strong forms are untested.

### 5. "Skipped instants are genuine non-decisions" holds only for submissions that reach the book

`flag10` and `ghost10` show that an accepted submission leaves an insertion. A rejected one would leave nothing. I
checked the most plausible rejection channel, collateral, and it does not bind (next section). Other rejection classes
look unlikely at scale, but the claim should say "accepted submissions".

## Checked and not supported (so nobody redoes them)

### Collateral rejections (X27, and the collateral part of X85)

Collateral balances via `polyrea.adapters.chain.collateral_at`, at six pre-H blocks from H - 36 h to H - 1 h (10-21
12:00 to 10-22 23:00 UTC):

| wallet | pUSD balance |
|---|---|
| GF | $12.5-18.8k |
| XM | $70.5-72.6k |
| DS | $62.4-64.8k |
| W4 | $11.4-14.6k |

USDC.e is 0 for all four. A wallet spends about $0.4-0.7k per window (REDEEM totals per window: GF about $400, DS about
$670), so free collateral is 15-100 times a window's spend. It is also unrelated to activity: XM holds the most and
trades the least. Collateral cannot gate the take rate. Close X27 and the collateral part of X85 with this measurement.

### A Polymarket-message clock for the evaluation loop

Data: 642 operator taker matches with match ms on 10-31 15:00-16:00. The latest Up-touch price_change before the
arrival a = m - 150 is within 10 ms for 71.6% of decisions and for 60.7% of placebo instants. The only excess is 1.5x
at 2-5 ms. Polymarket book messages arrive every few ms, so such a clock cannot gate two thirds of the onsets.

### Copy exhaustion of the pre-signed ladder as the size or pay-up rule

At the first fill of a (wallet, segment, token, level), P(large) is 24.5% (n = 10,869):

| what came before at that level in the segment | P(large) |
|---|---|
| one small fill | 6.2% |
| two small fills | 4.1% |
| one large fill, no small | 63.9% (n = 305) |
| two large fills, no small | 93.2% (n = 59) |

The size at a level is sticky and does not switch to the other size once one is used up, so there is no
exhaustion signature. Within a wallet, P(large | previous order large) stays flat at 0.48-0.54 for gaps of 0 to 60 s.
The persistence is in time, not per level.

### Hidden siblings

Census of crowd orders signed inside the operator's burst intervals (cd9 + cdall10, 132 bursts; chance share 6.2%,
crowd 6.0%). One clear new candidate: 0x03b4c58b1bb31007cb97e2c8f2216d33c805d29c.

- 37 orders, 89% inside the bursts;
- signatureType 3, 317-byte signature, builder 0;
- salt / timestamp uniform (q10 / 50 / 90 = 0.13 / 0.51 / 0.92, max 0.998);
- role M 20, T 17.

Weaker: 0xdc358e30... (128 orders, all maker, 27% inside the bursts, uniform salts) and 0x2aeaa186... (35%). They are
too small to explain the skips. They belong in X66 step 4 (the fingerprint census) and in the operator net.

## Proposals (ranked by the chance of closing the gap)

### 1. The bot reads a conflated or confirmed venue input: skipped onsets are ticks that did not survive to its next snapshot (new)

**Hypothesis.** The bot does not act on every top-of-book update. Either it consumes a snapshot or conflated stream,
or it acts only on a tick still in place after a confirmation delay. Candidate streams:

- Binance USD-M `@depth5@100ms` or `@depth@100ms`;
- OKX `books5` (100 ms);
- Bybit `orderbook.50` (20 ms) or `orderbook.200` (100 ms);
- its own timer sampling a cached state.

An onset becomes a decision only if the microprice change persists to the snapshot or confirmation point. Onsets that
revert or are overwritten first are invisible to it, and these are the "skips".

**Evidence.**

- The reaction kernels are about 100 ms wide.
- The hazard is front-loaded: 23-26% at the onset, then 2-8% per 100 ms.
- The take rate rises with strength (17 / 28 / 50%): strong ticks survive more often.
- Size-only depletion events sit at the base rate (a snapshot nets them out); price-level ticks are taken 29-30% of
  the time.
- There is no phase lock on Polymarket's clock.
- Survival has never been a covariate (critique 2).

**Test (runnable now on 10-31 12-18; replicate on 11-01 06-12).**

1. **Survival.** For every frozen A / C onset (`flag10b` episodes, `evt10` events), measure whether the onset's
   microprice change on Binance USD-M BTC and ETH, OKX and Bybit is still in place at +50 / +100 / +150 / +200 ms. "In
   place" means the same sign and at least 50% of its size, in `btc5m_venues2` / `btc5m_xven` (20-30-ms coalescing is
   enough at this scale). Report P(take | survived) against P(take | reverted) within strength terciles: fit on A,
   score on C.
2. **Kernel shape.** For taken decisions, the distribution of (a - t_onset) per venue in 10-ms bins:
   - a flat block about 100 ms wide with a sharp leading edge means conflation;
   - a narrow peak means a confirmation delay;
   - a right-skewed gamma means internal latency jitter.
3. **Phase on the venue clock.** A Rayleigh test of (a - L_v) modulo 20 / 50 / 100 / 200 ms on Binance event time,
   per hour, so that a slow phase drift is allowed.
4. **Record the candidate streams** in the next development block with a small Writer recorder (at most 100 MB, hard
   stop, development blocks only): Binance USD-M btcusdt / ethusdt `@depth5@100ms` and `@depth@100ms`, OKX `books5`,
   Bybit `orderbook.50` and `orderbook.200`, all with exchange timestamps.

   For each stream, measure the lag from its last message before each decision to the decision, and the take
   probability per snapshot that shows the change.

**Data.** `btc5m_venues2` / `btc5m_xven` / `btc5m_xfam` through `iter_live`, the decision record (taker matches and
located lost races: `cdall10`, `ghost_cand`, `rem10`), the `flag10b` and `evt10` episode and event tables, and the new
recording.

**Signature if true.**

- Onsets that reverted before +100 ms (or the period found) are taken at about the base rate (at most 5%); onsets that
  survived are taken at 50-60% or more within every strength tercile.
- The kernel is flat-topped with the stream's period as its width.
- One recorded stream shows a lag peak at least 3 times the placebo in one 5-ms bin.
- Onset AUC out of sample reaches 0.80 or more.

That would be a deterministic selection rule ("act on the first snapshot that shows the tick").

**Signature if false.**

- Survival adds nothing beyond strength.
- The kernel is a smooth gamma.
- No stream shows a peak.

Selection then really is stochastic or driven by another input.

### 2. Test the size-feedback channel causally before calling condition 5 "at the edge of attainability" (strong form of X82 / X84)

**Hypothesis.** The ceiling of 0.47-0.58 holds only if the size rule reads REALIZED fills. If it reads the bot's
intended position (orders sent), or follows a slow operator regime that race outcomes do not touch, replays must hold
the size path fixed. The ceiling is then the fixed-size 0.70-0.77, condition 5 is attainable in principle, and the
binding terms become decision overlap plus decoding that regime.

**Evidence.** Critique 1:

- persistence of 37 points against a shuffle null of 17;
- the null itself shows a large between-hour and between-half-window component;
- no detectable fill-fraction feedback with (wallet, hour) fixed effects (-0.01 ± 0.20 and -0.20 ± 0.16);
- the `lean10` state table was estimated on filled orders.

**Test.**

1. **Natural experiment on the live decision record** (10-31 14:55-17:55; 11-01 06-12 for replication).
   - Take large decisions that WON (taker match) against those that LOST (located lost races, including 0-fill ones).
   - Split the losses by an exogenous cause: crowd orders queued ahead (`queue10`) and maker requotes during the hold
     (`who9`). Neither depends on the bot's state.
   - Compare the next decisions' sizes within 1-30 s: same wallet and operator-wide, same and other outcome.
   - Own-net feedback predicts that after a won large on o, P(large on o) goes up and P(large on ō) goes down,
     against the lost case. Intention-based or regime sizing predicts no difference.
2. **The same at the block clock on VALIDATE**, with the fill fraction split by its cause: the touch depth consumed
   (from the maker orders in the same transaction) against queue luck.
3. **A two-state model.** Fit an operator-level model of the large share on BUILD: own-net terms plus a latent slow
   state, with the latent state shared across wallets or not.
   - Public predictors of the latent state: DVOL, realized vol over 30-300 s, |p - 0.5|, tau, the 15m window's
     state.
   - Operator predictors: distance to the rebate tier (X53), daily PnL.
4. **Corrected ceilings.** Re-run `lean10` with sizes driven by:
   - (A) intentions, not fills;
   - (B) the latent path held fixed;
   - (C) the latent state re-simulated from its public predictors.

   Report r(replay, replay) and r(replay, wallet), Pearson and Spearman, per wallet and pooled, with 2-h block
   intervals.

**Data.** `cdall10`, `cd9`, `ghost_cand`, the `queue10` and `who9` decompositions, `calldata_sample`, `fills`,
`windows` (outcomes settle PnL only), DVOL, priceToBeat, and W4's fills.

**Signature if true.**

- The next sizes after won and lost large races differ by at most 3 points, with the CI covering 0 (n of 200 or more
  large decisions).
- The corrected ceiling is 0.65 or more pooled.
- FINAL_RULE's account of condition 5 changes from "bounded by the race lottery" to "bounded by decision overlap and
  the regime decode".

**Signature if false.** The won and lost contrast shows the own-net signs. `lean10`'s bound then becomes a measured,
not an assumed, part of the wall account.

### 3. Align on the bot's clock: triangulate its location, then re-express every feature in bot time (strong form of X39 / X41 / X52; new for the Polymarket side)

**Hypothesis.** The bot sees venue v at t + τ_v and the Polymarket book at t + Λ. Selection depends on what it had
seen. With Λ of 30-150 ms and τ_v that differ by tens of ms between venues, server-time features mix information the
bot had with information it did not yet have. Among them:

- o's ask moved since the onset;
- maker requotes;
- venues agreeing;
- the crowd queue.

That mixing blurs the taken-versus-skipped separation (0.67-0.74). Possibly the first venue at the bot is not the
first in exchange time either.

**Evidence.** Critique 3: per-venue kernel peaks 50-100 ms apart, and the `lstar8` profile bounds Λ to roughly at
most 50-150 ms.

**Test.**

1. **Per-venue lags.** For each venue, the leading edge (5th percentile) and the mode of (a - t_tick,v) over the
   decisions that venue votes for, with bootstrap CIs.
   - Fit τ_v + processing.
   - Compare the differences between venues with public inter-region latency tables (AWS ap-northeast-1, ap-east-1,
     ap-southeast-1, eu-west-2, us-east-1, and Equinix LD4) to get candidate locations.
2. **Λ directly.** On the 2,155 decisions, take orders whose o-ask changed in [a - 300, a]. The share with
   limit == o's ask at a - Λ, as a function of Λ, peaks at the view lag.
3. **Profile the alignment.** Re-express the Polymarket-book features at t - Λ and the venue features at t - τ_v.
   Refit the onset hazard and the taken-versus-skipped model on A, score on C, and profile the AUC over a (Λ, τ) grid.
4. **Record what is near the inferred location** in the next development block if it is not yet recorded:
   - near London: Deribit perp (already in `btc5m_xfam` from 11-01 06-12), LMAX Digital and Bitstamp public
     websockets;
   - near us-east-1: Coinbase level2.

**Data.** `btc5m_clob_raw2`, `btc5m_venues2`, `btc5m_xven`, `btc5m_xfam`, `cdall10` limits, and the decision record.

**Signature if true.**

- An interior optimum (Λ*, τ*) gains 0.03 AUC or more out of sample over exchange-time alignment.
- The leading-edge differences match one region's latency vector within ±10 ms.
- A venue near that location has a sharper kernel than Binance USD-M.

**Signature if false.** The AUC is flat in Λ and τ. Report the measured Λ and τ_v as the bot's latency fingerprint
(this closes X39 properly).

### 4. Recover the bot's PRNG state from the order salts (new)

**Hypothesis.** The salt = Math.round(Math.random() x Date.now()) exposes the generator of the one process that signs
all four wallets. If that generator also drives the policy's random-looking parts, recovering its state:

- enumerates every salt of each burst, which gives the exact ladder;
- counts the draws made between bursts (hidden randomness);
- may expose the selection coin itself, by aligning the draws to the evaluated onsets: is a take where u < p(strength)?

The random-looking parts: the take probability of about 1/4-1/2 at the onset, the drawn time-to-live of 0.1-1 s, the
fan-out.

**Evidence.**

- The salt / timestamp ratio is uniform on [0, 1] with a maximum of 1.0 (iteration 5).
- Ladders are signed in tight loops; one XM group has 8 filled copies at Up 0.51 in one ms (a BUILD hour on 10-09).
- The policy has stochastic-looking parts.

**My check (simplest form, negative).**

- **Why it is testable.** In V8, Math.random's top bits are GF(2)-linear in the xorshift128 state.
- **Triple checks.** Over 38,544 ordered triples of same-wallet operator orders signed within ±1 ms, a parity test of
  consecutive generation offsets gives:

  | offsets | parity bits | hits | expected by chance |
  |---|---|---|---|
  | (0, 1, 2) | 13 | 8 (pairs that mirror each other) | 4.7 |
  | (0, 1, 3) | 13 | 4 | 4.7 |
  | (0, 1, 4) | 8 | 137 | 151 |
  | (0, 2, 4) | 8 | 151 | 151 |

- **Full placement.** I searched for the densest group's placement at offsets within ±12 (28 trusted bits) and ±24
  (34 bits):
  - a synthetic planted state is recovered uniquely in 4-50 s;
  - a random null finds none;
  - the real group finds none.

So the simplest form fails: Node V8, one Math.random call per order, copies within ±24 calls, Date.now() equal to the
order timestamp.

**Strong form (test).**

1. **Bun / JavaScriptCore.** Math.random returns the low 53 bits of (s0 + s1), which is not linear. Solve with z3
   (`pip install z3-solver` in the venv) on 5-6 orders of a dense group, with small offsets enumerated.
2. **V8 variants.** Two or three calls per order (offsets x2, x3), and the jumps where the 64-value LIFO cache refills.
3. **A different Date.now() in the salt.** Trust at most 28 bits and use six or more observations.
4. **If a state is found,** step it across bursts:
   - the draw count between consecutive bursts minus the signed orders gives the hidden draws;
   - regress that count on the number of flagged onsets and lost races in the interval;
   - align the draws to the onsets to test a per-onset coin.

**Data.** `calldata_sample.parquet` (13,558 operator orders, pre-H), `cd9` / `cdall10` (10-31 development), and the
decision record.

**Signature if true.**

- One placement predicts the top bits of 3 or more further observed salts exactly (false-positive odds below 2^-80).
- The hidden draws scale with flagged onsets (a selection coin) or with lost races (a random time-to-live).

**Signature if false.** No placement under any runtime variant. Record the salt as a fingerprint only (C8) and stop.
