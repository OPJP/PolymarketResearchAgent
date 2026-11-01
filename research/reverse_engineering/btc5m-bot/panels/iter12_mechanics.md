# Panel, iteration 12: mechanics and on-chain forensics

Reviewer lens: how the orders are built and used. That covers the pre-signed ladder, the slots and the fan-out, how legs
are allocated to wallets, how size classes are used, complement pairs, inventory feedback, requote cascades and the
software fingerprints.

Data I used, all development:
- `orders.parquet` (VALIDATE 10-16..22: one row per filled order hash, with total filled shares, role and block ts). The
  cleanest subset is 10-19..22 (the 30 / 100 menu, 1,057 windows).
- `cells/*.parquet` for 10-19..22 (`flow1`: other traders' Up-signed taker flow per second, cluster excluded);
- the it12 VALIDATE net-flow predictions (`it12/nf12b_val`, `nf12c_val`, `nf12m_val`);
- the 10-31 14:55-17:55 development block:
  - `it11/onset_A` / `onset_C`;
  - `it9/cd9` + `it10/cdall10` calldata, with `it10/txms10` match ms;
  - the 2,155-decision table `m11_ev.parquet` (iteration-11 mechanics panel, session scratchpad);
  - `btc5m_clob_raw2` token map, read only through `live_lab.recs` (`iter_live`, `allow_sealed=False`).

Nothing sealed was read, and `.cache/live/sealed/` was not opened. My scripts are in the session scratchpad,
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\`:
- `m12_pairing.py` (output in `m12_pairing.json`): the size-class structure and the pairing event study;
- `m12_pairplacebo.py`: the crowd placebo for the pairing;
- `m12_strictcoat.py`: co-take by crowd signing time;
- `m12_slowcrowd.py`, `m12_deficit.py`, `m12_dispatch.py`, `m12_band.py`, `m12_anchor.py`.

Some numbers below come from inline one-off runs of the same logic: the size-class tables on all VALIDATE days, the lag
profile and the counts. Apart from this file I wrote nothing to the workspace. Written 11-01 ~01:40 UTC.

## Critique

1. **The wallets' leans are not "nearly independent". Two common legs cancel each other.** Iteration 12 concludes that
   condition 7 is out of reach because the wallets' per-window PnLs correlate only 0.00-0.20. Split the window net by
   order size (10-19..22, 1,057 windows) and the picture inverts:

   | | DS-GF | DS-XM | GF-XM |
   |---|---|---|---|
   | large-order nets, across wallets | 0.61 | 0.51 | 0.55 |
   | small-order nets, across wallets | 0.34 | 0.25 | 0.59 |
   | total nets, across wallets | 0.28 | 0.01 | 0.13 |

   - Within a wallet, the large and small nets are anti-correlated: DS -0.30, GF -0.68, XM -0.56. Pooled the correlation is
     -0.665.
   - Var(net) / Σ(leg size²) is 5.28 for the large leg, 2.68 for the small leg and 1.67 for the total. Each leg is strongly
     systematic. Only their sum looks close to a random walk of legs.
   - The wallets mix the legs differently. The large share of shares is DS 17%, GF 45% and XM 53%. So each wallet's total
     is a different difference of two shared factors.
   - The current target models predict the window total at r 0.49 (the avg target), but the large leg at only 0.31 and the
     small leg at 0.11.

   Condition 7 is therefore a two-factor problem with per-wallet loadings, not a hunt for three private leans (proposals 1
   and 3).

2. **The catalog's "pairing rejected" (B4, H18, X50) tested the wrong inventory.** X50 used the total inventory as a
   per-second side rule (+0.2 points). The pairing is driven by the operator's realized LARGE fills, and it acts on the side
   of the small orders that follow. Measured on 10-19..22:
   - After a fully filled large order (95 or more of 100 shares, n 5,253), the operator's small orders buy a net 90 / 116
     shares of the complement in 0-30 / 30-120 s.
   - After a partially filled large order (31-60 shares, n 6,952), they buy only 21 / 31: a dose response in the realized
     fill.
   - After a small order (placebo) they buy +16 / -3 toward the same side.
   - The crowd moves the other way. Over 30-120 s it buys +17 toward the large side after full large fills, against -68
     after small anchors.

   This is own-inventory feedback, operator-level, with a 2-minute horizon. B4 should be reopened (proposal 1).

3. **The co-take with the fast crowd (X101) is not locked to the onset, so "a shared input at the onset" is the wrong
   reading.** Split the crowd orders by their signing time relative to τ:

   | crowd signed relative to τ (ms) | log OR, A | log OR, C |
   |---|---|---|
   | -250..-100 | 1.05 | 0.82 |
   | -100..0 | 1.03 | 1.10 |
   | 0..50 | 1.00 | 1.12 |
   | 50..100 | 1.22 | 1.39 |
   | 100..150 | 1.31 | 1.17 |
   | 150..250 | 1.08 | 1.15 |
   | ≥ 250 | 0.99 | 1.08 |

   Crowd orders signed 100-250 ms BEFORE the Binance onset are as associated with the cluster's take as those signed after
   it. A common trigger at or after τ would concentrate the excess in the post-τ bins. A reaction to the cluster's own print
   would concentrate it in the ≥ 250 bin.

   What the two share is a state that exists before the onset. Each group acts at its own moment inside it. That fits:
   - pmlock (the bot decides "while Polymarket is repricing toward o");
   - the 90% of decisions that are not locked to a tick.

   The onset is the wrong unit for the shared part of the selection (proposal 2).

4. **The 30-60-s operator state is an intensity, not a directional deficit.** I tested the natural mechanical reading: a
   controller on the sent net against a public target. On the 10-31 onsets (fit A, score C, and the reverse), with
   dA_H = the change of o's ask over H s and S_H = the operator's sent net toward o over H s:
   - the coefficient on dA60 is negative (-0.09 / -0.08);
   - the coefficient on S60 is positive (+0.04 / +0.08);
   - FULL + dA60 + S60 gives 0.684 / 0.690, against FULL 0.680 / 0.690.

   The whole own-kernel gain sits in the non-directional count: + N60 gives 0.716 / 0.719, against the kernel's 0.714 /
   0.718. So two separate mechanisms are in play:
   - an "on" intensity, which decides when the bot acts, is undirected and is still own state;
   - inventory pairing, which decides which side the small legs buy, is directional and is driven by the large fills.

   They should be modelled separately. Mixing them in one own-state term is why every directional own-state test came out
   flat.

5. **Version risk for any per-wallet rule.** The leg mix is a per-wallet, per-day setting:
   - VALIDATE: XM carries 53% of its shares in large orders.
   - 10-31: XM is the late 60-share leg that wins 15% of its races (`m11_ev`: DS 75%, GF 66%), with menus DS 30 (97%), GF
     30 (92%) and XM 60 (72%).

   Per-wallet loadings fitted on VALIDATE need not transfer to h1. The rule cannot see h1's menus without reading the
   wallets' own orders. Measure this before planning condition 7 on h1 (proposal 3, step 4).

## Checks (so nobody redoes them)

- **Operator-level pairing of large fills** (10-19..22; `m12_pairing.py`, `m12_pairplacebo.py`).
  - Complement share of the operator's small orders after a full large fill, by block-ts lag:

    | lag (s) | -10..-4 | -4..0 | 1-2 | 2-4 | 6-10 | 10-20 | 20-40 | 40-80 | 80-160 |
    |---|---|---|---|---|---|---|---|---|---|
    | complement share | 0.52 | 0.48 | 0.57 | 0.59 | 0.61 | 0.60 | 0.59 | 0.58 | 0.57 |

    After small anchors the share is 0.42-0.46 in the first 4 s (same-side clustering) and 0.49-0.50 after that.
  - The tilt starts within the first block after the fill, so the bot learns its fills in real time (order response or user
    channel), not from a slow poll.
  - It is a side tilt, not extra activity. Small orders in 0-30 / 30-120 s:

    | | 0-30 s, complement / same | 30-120 s, complement / same |
    |---|---|---|
    | after a full large fill | 10.5 / 7.2 | 16.1 / 11.7 |
    | after a small anchor | 8.5 / 9.1 | 15.8 / 15.6 |

  - Every wallet does it. In 30-120 s, complement / same orders: DS 52.1k / 40.9k, GF 25.8k / 17.1k, XM 6.9k / 3.3k.
  - As a per-order side rule, "buy the complement of the operator's realized large net over [t-120, t-2] s" is right
    58.0-60.3% of the time, on the 42-70% of small orders where that net is at least 30-200 shares. A tilt to layer on the
    vote, not a side rule by itself.
- **Size-class structure on all VALIDATE days** (thresholds by menu): large-net cross-wallet 0.49-0.56, small 0.26-0.49,
  pooled large vs small -0.62.
  - Leave-one-wallet-out, in-sample: a wallet's total net on the OTHER wallets' large and small nets gives R² DS 0.037, GF
    0.206, XM 0.056, against 0.035 / 0.058 / 0.007 on the other wallets' total net.
  - The two-factor form doubles GF (r 0.24 -> 0.45) and triples XM (0.08 -> 0.24).
  - The avg target predicts the large legs at DSL 0.25, GFL 0.31, XML 0.15 and the small legs at DSS 0.26, GFS -0.05,
    XMS -0.12.
- **Strict co-take** (`m12_strictcoat.py`): see critique 3. Of the fast-crowd orders co-taking a taken onset, 80% were signed
  before the cluster's first arrival (median -120 ms).
- **Slow fast-crowd activity is not the own kernel** (`m12_slowcrowd.py`). Fast-crowd (sign-to-match 180-400 ms) taker
  BUYs on o and on ō over [τ-60 s, τ-3 s), from calldata and block-confirmed:
  - correlation with rec60 is 0.39 / 0.43;
  - the take rises across its quartiles (A 5.0 -> 8.3%, C 2.8 -> 6.5%);
  - but FULL + crowd adds +0.002-0.006 AUC out of sample, against +0.03 for the own kernel, and with both the kernel still
    carries the gain.
- **No hard order-count cap** (`m11_ev`, 2,155 decisions). Operator decisions in sliding windows have smooth tails:

  | window | 1 s | 5 s | 10 s | 30 s | 60 s |
  |---|---|---|---|---|---|
  | max | 11 | 22 | 35 | 72 | 108 |
  | q99 | 7 | 18 | 27 | 65 | 91 |

  No pile-up at a ceiling, so no API or bot-side token bucket.
- **No adaptive ladder band** (`m12_band.py`). The take at clean onsets RISES with |o's ask − o's ask at the serving burst|:
  4.5% within 5 c, 5.8-6.1% at 5-15 c, 7.7% at 20-25 c, 10-11% at 25-40 c. There is no cliff, so the pre-signed range does
  not follow the burst-time price.
- **No burst-anchored state** (`m12_anchor.py`). The within-|ask − 0.5|-stratum AUC of |move since anchor| is:

  | anchor | burst | burst ± 15-45 s | t − 30 | t − 60 / t − 90 |
  |---|---|---|---|---|
  | A | 0.559 | 0.52-0.58 | 0.571 | 0.55 |
  | C | 0.576 | 0.55-0.57 | 0.563 | 0.50-0.56 |

  The burst time is not special.
- **No sent-net deficit controller** (`m12_deficit.py`): see critique 4.
- **Dispatcher statistics on 10-31** (`m12_dispatch.py`; 1,549 events at ≤ 300 ms, same outcome).
  - Legs per event: 1 → 1,089, 2 → 351, 3 or more → 109.
  - First leg: DS 68%, GF 18%, XM 14%. DS is still first 57% when it had a decision in the last 1 s, so this is not a
    free-slot priority.
  - P(next decision on the same wallet) by gap:

    | gap | < 300 ms | 0.3-2 s | 2-10 s | > 10 s |
    |---|---|---|---|---|
    | P(same wallet) | 0.12 | 0.43 | 0.55 | 0.49 |

    Under independence it would be 0.42, so the dispatcher is sticky at 2-10 s.
  - The DS share per 60-s block has sd 0.18, against about 0.12 binomial.
  - DS / GF share by window minute: DS 0.63, 0.63, 0.56, 0.54, 0.43; GF 0.21, 0.20, 0.22, 0.26, 0.37.
  - There is no per-window primary wallet (DS leads in all 34 windows) and no split by outcome or by price.

## Proposals (ranked by the chance of closing the gap)

### 1. A two-leg inventory policy: large directional fills, and operator-level complement pairing by the small orders (strong form of B4 / H18 / X50 / X84; new for the side, condition 5 and condition 7)

**Hypothesis.** The operator runs two legs.
- (a) A LARGE leg that takes the directional snipes. The window's large net is common across wallets (0.51-0.61), so the
  large decision is made once per operator and fanned out.
- (b) A SMALL leg that buys the strong-tick direction, with its side tilted toward the complement of the operator's
  realized large inventory. That pairs the large lean back within about 2 minutes. The tilt is dose-dependent on the
  realized fill and is done by all wallets.

The window net is large-lean minus pairing, plus the late large fills that are not yet paired. That is iteration 12's
"buy the move, buy back against the earlier minutes" path, with its cause identified. The "87% paired at 0.979" is this
loop's output.

**Why it fits.** Critiques 1-2 and the checks:
- the large/small anti-correlation (-0.665 pooled, -0.30 / -0.68 / -0.56 within wallet);
- the dose response (90 / 116 vs 21 / 31 shares), against the crowd's direction at 30-120 s;
- the immediate onset and slow decay of the tilt;
- the target models predict the large and small legs far worse than their sum;
- live, the large size follows the tick strength (iteration 11), which is the directional leg.

**Test.**
1. *Mechanism.*
   - Fit a distributed-lag kernel K(Δt, q): the operator's small-order side on o and ō as a function of the operator's
     realized large fills q at t − Δt (Δt = 1-180 s, block clock). Use window fixed effects, the frozen side model's
     probability as an offset, and the crowd's `flow1` path as a control.
   - Do it separately for same-wallet and other-wallet pairing, and with W4 / W5 fills in and out of the operator
     inventory.
   - Test linearity in q, and whether the tilt saturates once the large inventory is paired: the tilt should vanish when
     cumulative complement shares since the fill reach q.
2. *Side (condition 3).* Add K's input to the frozen block-clock side model: the operator's realized large net over
   [t − 180, t − 2] s, decayed with the fitted kernel, plus its interaction with the vote / psb strength. BUILD-fit,
   VALIDATE-score. Report:
   - with and without this own-state input;
   - against the own-inventory-only baseline (X50's short-leg rule) and the market-only baseline.
3. *Net target (condition 5).* BUILD-fit two per-second flow models with the same feature set as nf12c:
   - L̂ for large-order net flow;
   - Ŝ for small-order net flow, after removing K's pairing term.

   Pre-register a tracker target N*(s) = Σ L̂ + Σ Ŝ − K * (the RULE's own realized large-size fills). The rule sends its
   large component when L̂ calls for it, and pairs its OWN fills with K. That is own state of the rule, so it is
   legitimate. Score pooled and per wallet, once.
4. *Decision replica on recorded books (the future-block exams).* Put both legs into X93's simulator, where the race is
   deterministic given the arrival (race11): large orders on strong-tick onsets, small pairing on the replica's own large
   fills.

**Data.**
- `orders.parquet`, `fills.parquet` and the cells for BUILD / VALIDATE;
- calldata sample hours, for the true order sizes (the filled-shares classification is biased toward a positive large /
  small correlation, so the anti-correlation is understated);
- `it12` nf models;
- W4 / W5 OrderFilled logs;
- the 10-31 and 11-01 development blocks for the replica.

**Signature if true.**
- K is linear in the realized q, is the same for same-wallet and other-wallet small orders, and vanishes once q is paired.
- The side model gains 2 or more points on weak-vote seconds, and pooled accuracy reaches at least 79-80%.
- The pre-registered two-leg tracker reaches window-net r ≥ 0.55 and PnL r ≥ 0.50 / 0.50, and GF rises toward the pooled
  value.

**If false.** K disappears once the crowd's path is controlled at 1-s resolution, so the reversal is market-driven. Then
the two-leg target still stands as a pure decomposition, but the pairing term is not a policy.

### 2. The selection the bot shares with the crowd is a pre-onset Polymarket repricing state: decode it from the maker requote cascade (strong form of X101, pmlock and X108's echo makers)

**Hypothesis.** The cluster and the fast crowd take inside the same ~0.5-1-s repricing episodes of o's book: makers
requoting toward o, and fill-reactive makers re-signing 0-20 ms after being hit. Each acts at its own moment inside the
episode, so neither is locked to the Binance onset. The bot's take is then a function of the episode state as of its
~30-ms-old view, not of the onset that happens to fall inside the episode:
- how many cents o's touch has stepped toward o in the last 0.5-2 s;
- how many levels were removed or requoted;
- the depth left at the ask;
- the venue composite's agreement.

The 30-60-s "own" kernel may be the persistence of such episodes, which the onset table only sees through the operator's
own decisions.

**Why it fits.**
- Critique 3: the co-take log OR is 0.8-1.4 in every crowd-signing bin from τ − 250 to τ + 500 ms, and 80% of the
  co-takers signed before the cluster's first arrival.
- pmlock: o-ask-up and o-bid-up enrichment is flat over 0-120 ms, with no lag peak.
- About 90% of decisions are unlocked (lock12).
- The recorded design explains 14-21% of the co-take (coat12).
- The ~140 echo makers (the iteration-11 panel) are a mechanical source of cascades.

**Test** (10-31 A / C; 11-01 06-12 as the replication):
1. From `btc5m_clob_raw2`, for every clean onset, compute PIT features over [τ − 2,000, τ) and [τ − 500, τ):
   - o-bid-up and o-ask-up events;
   - net cents moved toward o;
   - levels removed at the ask;
   - insertions at or above the best bid;
   - market-channel taker prints on o and ō;
   - the age of the current ask level.
2. Stratify the co-take by terciles of the pre-onset repricing score, restricting the crowd to orders signed before τ.
   Report the log OR inside the strata, and coat12's "share explained".
3. Add the score to the evt10-style FULL logistic: fit on one half, score the other. Compare with and without the own
   kernel.
4. Re-define the unit as the repricing episode: a run of same-direction touch changes with gaps of 300 ms or less. Label
   it "operator decides inside the episode" and fit the take on the episode state at each step k. A step-k trigger gives
   the unlocked majority its clock.

**Data.** `btc5m_clob_raw2` (development blocks only), onset tables, `cd9` / `cdall10` (crowd labels, diagnostics only),
11-01 06-12 when released.

**Signature if true.**
- The co-take log OR within strata falls below 0.5 (more than half explained).
- FULL + episode state reaches ≥ 0.72 out of sample, and the own kernel adds ≤ 0.005 beyond it: the "own" state was a
  public repricing regime.
- Inside episodes, decisions cluster after a fixed step count.

**If false.** The co-take survives inside every stratum. Then the shared pre-onset state is in a feed both groups have and
the recordings lack (Binance spot depth, Coinbase level2, Chainlink Data Streams: rec_eu11 / X100 step 2). Name the
candidates by the crowd's pre-τ signing lag (median about 100-250 ms before τ) and the venues whose transit matches.

### 3. Per-wallet allocation of the two legs: a sticky dispatcher plus per-wallet size menus (strong form of X55, X106 step 3 and X67; the route to condition 7)

**Hypothesis.** Each wallet's net is a wallet-specific combination of the two operator legs of proposal 1. The loadings are
set by:
- (i) the wallet's size menu (DS mostly small, GF and XM large-heavy on VALIDATE);
- (ii) a sticky dispatcher, under which a wallet keeps receiving decisions for 2-10 s;
- (iii) a shift with time in the window (GF takes a larger share in minute 4).

Per-wallet PnL is then predictable as a_w(minute) L̂ + b_w(minute) Ŝ, up to a thinning noise that can be computed in
advance. That noise, not a private lean, is condition 7's ceiling.

**Why it fits.** Critiques 1 and 5 and the dispatcher check:
- not a free-slot priority (DS first 57% even when busy);
- stickiness 0.55 vs 0.42;
- per-minute shares;
- the leave-one-out two-factor R² doubles GF and triples XM over the total-net form.

**Test.**
1. On BUILD, fit each wallet's per-window (and per-minute) net on the pooled large and small nets of the OTHER wallets,
   with minute-specific loadings. Score VALIDATE out of sample (r per wallet).
2. With proposal 1's L̂ / Ŝ, pre-register per-wallet tracker targets with the BUILD loadings. Report per-wallet Pearson /
   Spearman and the halves (condition 7's 0.03 tolerance).
3. Compute the thinning ceiling for each wallet: the r reached by the TRUE pooled leg nets with the BUILD loadings. This is
   the maximum any public rule can reach. Report it in the wall account.
4. Version transfer: refit the loadings on the 10-31 development blocks (30 / 60 / 100 menu, XM as the late leg) and score
   VALIDATE, and the reverse. If they do not transfer, condition 7 on h1 depends on the h1 menu, which the rule cannot
   observe. Record that as a measured limit before the exam.
5. On 10-31, model the first-leg wallet as a multinomial on:
   - each wallet's time since its last decision;
   - its in-flight state (the per-wallet gap floors);
   - its recent decision count;
   - window minute and leg size.

   This tests whether the stickiness is a dispatcher rule or per-wallet "on" periods (proposal 2's regime seen per wallet).

**Data.** `orders.parquet` / calldata sizes (BUILD, VALIDATE), `m11_ev` / `large_dec` (10-31), 11-01 blocks.

**Signature if true.**
- VALIDATE per-wallet r with the two-leg loadings: GF ≥ 0.45, DS ≥ 0.43, XM ≥ 0.25, with the thinning ceiling within 0.05
  of the attained values.
- The loadings transfer between menus within 0.1.

**If false.** The loadings change with the menu. Then condition 7 is bounded by version, and the bound is the transfer loss
measured in step 4.
