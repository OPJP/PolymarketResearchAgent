# Panel after iteration 9: mechanics and on-chain forensics

Lens: how the orders are built. What the wallet-attributed order structs (calldata original size, limit price, salt) say about
order types, ladder phases, per-wallet configuration and the switch-off. Written 2026-10-31, 22:10-23:05 UTC.

**Data I used.** Development data only, read from the RE's extractions and the dev folder of the shared recorder.
- Live 10-31 14:06-16:30 UTC:
  - `it6/fill_side_*` (1,668 match-clock BTC 5m/15m fills);
  - `calldata/live1031_*` (1,992 txs, all joined);
  - `it6/confirmed_*`, `live_activity_*`, `it6/x_*`.
- Live 10-31 15:50-18:00: `calldata/it9sw_*` (229 cluster fill txs, all families) and `it9/act_*`.
- Shared `clob_crypto` and `subs` dev files, 16:23-17:50 UTC (200-ms top-10 snapshots).
- The lot, BTC 5m:
  - `b1_cluster_orders_{study,valid}` (calldata original sizes);
  - `exam/activity_*` (inventory);
  - `it9/volhist_{study,validate}` (frozen posture on the block clock).
  - STUDY is read case by case; VALIDATE (10-27..30) **aggregate only**.
- BUILD activity (REDEEM timing).

I did not open `.cache/live/sealed/` or read any sealed block. Scripts:
`C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\it9m\`
(`queue_rank.py`, `salt_pass.py`, `size_tleft.py`, `pair_hist.py`, `realloc3.py`).

## What my checks found

1. **The "remainders" are not remainders. They are pairing bids sized to the window's exact imbalance, on the under-held
   outcome.** "Remainder" here means a filled maker order whose calldata original size is not a schedule size.
   - Live (14:06-16:30). Own inventory = Up minus Down shares the wallet bought in the window before the fill's block
     second.
     - Non-schedule orders are on the under-held outcome in **100%** of fills: 145 of 145 in BTC 5m, 30 of 30 in BTC 15m.
     - Their size is |imbalance| within 2% in 79% (5m) and 73% (15m) of fills. The median ratio is 1.000 (q10-q75 1.000).
     - Schedule 500s are on the under-held side in only 31% (5m) and 15% (15m) of fills. They pile onto the held side,
       which is the anti-balancing that B5 saw.
   - Lot replication (BTC 5m, block clock):

     | sample | fills | non-schedule fills | on the under-held outcome | size = imbalance (±2%) | schedule sizes on the under-held outcome |
     | --- | --- | --- | --- | --- | --- |
     | STUDY | 5,726 | 1,206 (21%) | 0.999 | 0.768 | 0.291 |
     | VALIDATE (aggregate) | 22,006 | 5,302 (24%) | 0.996 | 0.751 | 0.311 |

     Every wallet scores 0.992-1.000 on the under-held outcome.
   - Example. "492.44" is a bid for the 492.44 shares that would complete the pairs after the wallet was filled 500 on
     one outcome and 7.56 on the other. It is not a partly filled 500 posted again.
   - So the ladder holds two order types, each with its own side rule:
     - **posture rungs** (500 x 2^k, 100, 62 and 250 by the schedule) follow the Chainlink edge;
     - **imbalance pairing bids** follow own inventory (B4 merges the pairs ~65 s before the end).
   - Side accuracy when the side is assigned by order type: pairing class (non-schedule, plus the 15m late 62s, item 2)
     to the under-held outcome, the rest to the posture. **Own state; descriptive.**

     | sample | combined rule | posture alone |
     | --- | --- | --- |
     | live BTC 5m | 0.842 | 0.820 |
     | live BTC 15m | 0.906 | 0.783 |
     | live almach | 0.921 | 0.876 |
     | live bosona | 0.849 | 0.809 |
     | live mo-money | 0.794 | 0.767 |
     | lot STUDY | 0.613 | 0.517 |
     | lot VALIDATE (aggregate) | 0.721 | 0.646 |

2. **The ladder changes with time left, and the posture's errors cluster in one phase.**
   - The one-fifth rung (100 / 12) exists only between 30 and 120 s before the end:
     - live 12-18: every 100 was posted at 53-114 s left, in 19 of 30 windows;
     - lot (STUDY, and VALIDATE aggregate): 100 / 12 fills make up 4-12% of the fills at 60-120 s left, 1-3% at 30-60 s,
       and 0% at >= 120 s and < 30 s.
   - BTC 15m:
     - in the last 120 s, 64-68% of fills are 62s, against 0-2% earlier;
     - this happened in 4 of the 7 windows with late fills;
     - those 62s are on the under-held outcome in 100% of fills (n 52): a pairing phase.
   - Posture accuracy by phase, live 14:06-16:30, BTC 5m:

     | time left | accuracy | n |
     | --- | --- | --- |
     | >= 120 s | 0.822 | 986 |
     | **60-120 s** | **0.756** | 307 |
     | 30-60 s | 0.932 | 118 |
     | < 30 s | 0.59 | 22 |

     The 100-class fills score 0.712.
   - Each wallet runs the 60-120 s phase differently:
     - almach keeps posting 500s there and scores 0.90 (n 90);
     - bosona switches to 100s (75 of 78 fills) and scores 0.68;
     - mo-money keeps posting 500s and scores **0.65** (n 102). At >= 120 s it scores 0.77, against 0.86-0.87 for the
       other two.
3. **Mo-money's deficit is not a reference, clock or queue effect. It is how its ladder is configured.**
   - Its exact-500 fills on BTC 5m/15m, where the Chainlink and futures edges disagree on the side:
     - mo-money follows Chainlink in 0.832 of fills (n 191);
     - bosona 0.826, almach 0.969.
   - Where the two edges agree, mo-money buys against both in ~29% of fills, against 13-18% for the others.
   - It is not the queue. Most fill txs hold one cluster order (1,318 of 1,355 exact-500 fills). When I classify fills
     by whether sibling copies at the same token and price were also filled within 3 s, mo-money is lower in every
     class. For example, where it was filled first: 0.80, against almach 0.99.
4. **The 16:53:54 switch-off cut 500-class posting in several families; it did not move it elsewhere.**
   - Pilot on the shared 200-ms snapshots: +500 level deltas per minute, in three periods:
     - 30 min before the switch-off;
     - the 11 min after it, before the restarts;
     - 17:08-17:50.

     | family | before | after (11 min) | 17:08-17:50 |
     | --- | --- | --- | --- |
     | BTC 5m | 2.7 | 0.2 | 0.2 |
     | BTC 15m | 11.3 | 8.2 | 6.1 |
     | ETH 15m | 2.4 | 0.3 | 0.9 |
     | SOL 15m | 1.8 | 0.1 | 1.2 |

     Other size classes did not change.
   - Caveats: snapshots net out cancels and re-adds that fall within 200 ms, and the size class is not unique to the
     cluster.
   - The counters kept signing ~12 orders/s. After the switch-off the cluster had fills in **XRP 5m and BNB 5m**, which
     no recorder covers.
5. **Nulls (so nobody re-runs them):**
   - Filled orders' salt is monotone in their raw-book add time (2 exceptions in 238), at a rate of 14.0-14.3 /s, so
     there is no sign of a pre-signed order pool.
   - REDEEM rows come 60-95 s after the window end (median 89 s) in every wallet, so capital is not parked in
     unredeemed winners.

## Critique

1. **Two decision processes are pooled as one.**
   - Every side, price, presence and PnL analysis pools the posture rungs with the imbalance pairing bids.
   - The pairing bids are 21-24% of the BTC 5m maker fills on the lot.
   - FINAL_RULE describes them in two wrong ways:
     - as "remainders re-posted" (size);
     - as an exit of "small complement taker buys and merges (2-4% of PnL)".
   - Yet D4 measured locked pairs at +$38.1k (+11.0%) on VALIDATE, against -$14.4k for the directional part.
   - So the pairing bids may be where the money is made. A PnL replay (X64) without them cannot correlate with the
     wallet's PnL.
2. **The side component is scored against the wrong baseline mix.**
   - On pairing fills the side is the own-inventory baseline, exactly. The brief allows that as a description, if it
     says so.
   - The posture should then be judged on the posture rungs only.
   - The H-VOL replication and the "88% complement mints on the underdog" diagnosis used all fills, so the
     sigma-identification debate was partly a mix-composition debate.
3. **The ladder is a phase machine, and the analyses pool its phases.** The weak spots are:
   - the 60-120 s phase in 5m (0.756);
   - bosona's 100s and mo-money's 500s there;
   - the 15m last-120-s pairing phase.

   These are what pull the pooled posture below 0.80. Neither a vol estimator nor a reference delay can fix a
   phase-specific rule. Iteration 9 tried both.
4. **The quote-unit label is incomplete.** "A cluster-class exact-500 at the touch now" misses three kinds of order:
   - the pairing bids;
   - the 100 rung;
   - the 15m late 62s.

   So the quote-unit AUC (0.748) and the print-selection ceilings (0.81-0.83) were measured on part of the quote only.
5. **Per-wallet replication will fail as long as the wallets' configurations are averaged.** Mo-money's 500s at 60-120 s
   score 0.65 and bosona's 100s score 0.68. The examiner requires every wallet within 3 points, so the rule must be
   decoded per wallet configuration, not pooled.

## Proposals (ranked by the chance they close the gap)

### M1. Two order types: decode the imbalance pairing bid (price, trigger, lifetime) and score each component by order type (new; corrects C8/size "remainders", strong form of B4/X18)

- **Hypothesis.**
  - The engine posts two kinds of order:
    - posture rungs of schedule size, which follow the Chainlink edge;
    - for every window with an imbalance, a pairing bid on the under-held outcome of exactly |Up - Down| shares. It is
      re-signed after each own fill, which is why it looks like a "remainder".
  - The pairing bid's price is set so that the pair costs less than 1, e.g. q_pair = 1 - (average cost of the held side)
    - m, or a fixed offset from that outcome's touch.
  - Pairs are merged ~65 s before the end.
  - This is the strategy's lock-in and a large share of its PnL.
- **Why it fits.**
  - Finding 1: under-held in 0.996-1.000 of non-schedule fills, with size = imbalance in 75-79%, live, STUDY and
    VALIDATE (aggregate), in every wallet.
  - D4: locked pairs +11% against directional -$14k on VALIDATE.
  - B4: merges of the full paired amount.
  - X18: the taker complement buys are sized to the imbalance too.
- **Test.**
  1. Freeze the class definition: the calldata original size is not a schedule size, and is within 2% of |own
     imbalance| at the fill's block second. Classify every lot fill and every live fill.
  2. Price rule, at the add time on the live raw book and at the block clock on the lot.
     - Candidate anchors:
       - 1 - VWAP of the held side;
       - 1 - the held side's best bid (that is, the under-held side's ask minus a tick);
       - the under-held side's touch;
       - 1 - the last own fill price on the held side.
     - Fit on BUILD/STUDY, score on VALIDATE (aggregate) and on the live block.
  3. Trigger and lifetime.
     - On the raw book (`ev_*`): the add of an imbalance-sized order relative to the fill that changed the imbalance (the
       trade-stream ms; descriptive, not a feature).
     - Its lifetime, and whether it is cancelled when the posture flips.
  4. Side, R7-side:
     - schedule orders go to the posture;
     - pairing orders go to the under-held outcome. This is own state and is reported as the own-inventory baseline.
     - A public-only variant: P(pairing fill) = the under-held side's touch is within a tick of the decoded q_pair.
  5. PnL: per window, the share of realised PnL from locked pairs. In X64, replay the two order types separately.
- **Data.** All of it is on disk:
  - `b1_cluster_orders_{study,valid}`, `exam/activity_*` and `it9/volhist_*`;
  - live `live1031_*` / `it9sw_*` calldata, `ev_*` and `confirmed_*`.
- **Signature if true.**
  - q_pair is within a tick of one anchor in >= 60% of pairing orders.
  - The combined side is >= 0.80 in every wallet and half on live 10-31 and on 11-01 06-12.
  - Locked-pair PnL is >= 60% of the window PnL on VALIDATE.
  - The strict-fill replay with both order types lifts the per-window PnL correlation towards 0.5.
  - If q_pair fits no anchor, its price is a second posture. Decode it like the 500 rung, conditioned on inventory.

### M2. The ladder as a time-left phase machine with per-wallet phase configurations (new; strong form of X71 and A1_B3b)

- **Hypothesis.** The engine switches rung sets at fixed times left. For BTC 5m: >= 120 s; 60-120 s (adds a one-fifth rung,
  and may change the fair); 30-60 s (TWAP lock-in); < 30 s (stop). For BTC 15m: a pairing phase in the last 120 s (62s on
  the under-held outcome). Each wallet process carries its own phase table (bosona: 100 rungs; almach and mo-money: 500s).
  In the 60-120 s phase the posture may use another fair, e.g. a TWAP-60 lock-in digital with σ_eff² = σ²(τ - 60) +
  σ²·60/3, or a projected TWAP. A pooled sigma cannot capture that.
- **Why it fits.**
  - Finding 2: the 100 / 12 rungs exist only at 30-120 s, live and on the lot.
  - The posture scores 0.756 at 60-120 s against 0.82 / 0.93 in the neighbouring phases.
  - Each wallet behaves differently at 60-120 s: 0.90 / 0.68 / 0.65.
  - The 15m late 62s are 100% on the under-held outcome.
  - A1_B3b: the last-60-s prices fit the lock-in fair.
- **Test.**
  1. Phase boundaries: change-point detection on the calldata size class against time left, per wallet and per version
     (10-09..16, 10-16..22, the lot, live 10-31). Do the boundaries stay at 120 / 60 / 30 s?
  2. Per phase and per wallet, report:
     - the size mix;
     - posture accuracy (frozen, slow, and lock-in-digital fairs, pre-registered before scoring);
     - the half-spread regression (X80) refitted per phase;
     - the quote-unit AUC with the phase's own size class in the label.
  3. Is the 100 rung a posture rung, a pairing rung, or the opposite-side rung? Compare its side against the posture, the
     under-held side and the cheaper side.
  4. Freeze a per-phase side rule on live 12-15 and score it on 15-18 (aggregate) and on 11-01 06-12.
- **Data.**
  - On disk: `b1_cluster_orders_*`, `it6/fill_side_*`, `ev_*`, `m1inv_*` and the live calldata.
  - Coming: the 11-01 06-12 full-depth book.
- **Signature if true.**
  - Step changes at the same time-left marks in all three wallets, with rung classes that differ by wallet.
  - The 60-120 s posture reaches >= 0.82 with one pre-registered phase fair.
  - The per-phase top rung is within a tick in >= 50% of cases, against 26-30% pooled.
  - The pooled posture rung side reaches >= 0.80 in every wallet.

### M3. Mo-money's deficit is a ladder parameter, not a reference: per-wallet skew and spread from wallet-attributed limit prices (new; replaces the clock reading of X76)

- **Hypothesis.** Mo-money's 500 pass uses a smaller skew β or a smaller half-spread on the side the posture disfavours.
  Another possibility is that it skips the cancel on posture flips. Either way, its off-posture rung sits at the touch
  more often, so takers fill it.
- **Why it fits.**
  - Finding 3: it follows Chainlink where the references disagree (0.83, like bosona).
  - It buys against both references in 29% of the fills where they agree.
  - It is lower in every sibling-copy class, so this is not queue position.
  - Its deficit sits in the 60-120 s and >= 120 s phases.
  - Its 500s are already off the posture at the add time (0.646, RE).
- **Test.**
  1. Unit: every filled order (calldata limit price, wallet, original size) joined to the raw-book mid, touch and
     Chainlink edge at its add ms (`confirmed_*`).
  2. Fit per wallet and per phase: (limit - mid) = a_w + β_w(fair - mid), split by whether the order is on the posture
     side or the other side.
  3. Survival of off-posture rungs per wallet. The remove times come from `ev_*`, matched by price and size, and the
     posting wallet is known from the filled copies.
  4. Fix the per-wallet replication condition with a per-wallet (β, h) frozen on 12-15 and scored on 15-18 and 11-01
     06-12.
- **Data.** `confirmed_*`, `ev_*`, the live calldata and `dy_rtds`. Coming: the 11-01 full-depth recorder.
- **Signature if true.**
  - Mo-money's off-posture offset to the touch is >= 1 tick smaller, or its β is <= 0.5 x the others'.
  - With per-wallet parameters, every wallet's posture rung side is within 3 points of the pooled value.

### M4. Account for every signature: where ~12 orders/s per wallet go, with posting per family including XRP / BNB / DOGE and hourly / daily (strong form of X65 / X82; feeds X83)

- **Hypothesis.** The signer runs a fixed cadence over a list of quoting slots. Three readings would explain the
  signatures that are not posted in the recorded books:
  - posting in families no recorder covers (finding 4: XRP 5m and BNB 5m fills right after the switch-off);
  - orders rejected by the CLOB (balance or allowance on open-order notional);
  - per-family size changes.

  The answer decides two things: whether the universe is a priority allocator with fixed capacity (then selection is a
  ranking), and whether X83's universe must add XRP / BNB / DOGE.
- **Test.**
  1. In the next development blocks, run a slim recorder (live.py `Writer`, < 100 MB) on the XRP / BNB / DOGE 5m-15m and
     BTC/ETH hourly and daily books, with exact-size deltas at full depth.
  2. Fetch the calldata of every cluster fill in every family.
  3. Per wallet, regress the salt increments per 10 s on the per-family counts of cluster-class adds. Do this at every
     module switch and at the 01:00 restart of a development block.
  4. Reconstruct each wallet's collateral balance on chain (ERC-20 Transfer logs of the V2 collateral token) and compare
     it with the resting notional when posting falls.
- **Data.** Polygon RPC, the new recorder, the calldata, and `clob_crypto`.
- **Signature if true.**
  - Allocator: the signature residual is explained by unrecorded families, and the families' posting rates sum to a
    constant.
  - Rejection: signatures exceed all posting, and free collateral is near zero at the halving.
  - Configuration change: per-family size or enable steps that line up across wallets within 1 s.

### M5. Off-posture fills as lost cancel races: the posture at the taker's arrival time, not at the match (new; uses B1 taker structs, related to X52 / X81)

- **Hypothesis.** An off-posture fill happens when the taker's order (signed at sign_ms, plus the ~190 ms taker bump)
  reaches the engine before the cluster's re-price after a publish that flipped the posture. In that case the side
  follows the posture at (taker arrival - the cluster's cancel latency).
- **Why it fits.**
  - 9-12% of filled orders' postures flip between add and match.
  - Filled orders agree with the posture more at the match than at the add, so orders that turn against the posture
    are pulled.
  - Takers of cluster fills sign a median 764 ms before the match.
- **Test.**
  1. Unit: the live fills.
  2. Take the taker's sign_ms from `live1031_*` (97% coverage) and the publish ms from `dy_rtds` (16:29-18:00) or the
     stamp + 1,083 ms proxy.
  3. Score the side with the reference in force at sign_ms + b - λ, with b ∈ {0, 190} ms and λ ∈ {0, 100, 150} ms
     (pre-registered grid), against the match-clock rule.
- **Signature if true.**
  - Off-posture fills concentrate where a flipping publish fell in [sign_ms, sign_ms + b + λ].
  - The rule gains >= 2 points per fill, most of it in mo-money and in the 60-120 s phase.

## Notes for the RE

- My live numbers are aggregates over 14:06-16:30 and 12-18. The VALIDATE lot numbers are aggregates. No parameter was
  chosen on VALIDATE.
- The schedule set I used is {500, 1000, 250, 125, 100, 62, 50, 12, 300, 40, 200}.
- "Own imbalance" = BUY shares on Up minus Down in the window before the fill's block second, from the wallet's own
  activity. It is own state; report it as such.
- The class labels need the calldata. For the exam, `evaluate()` would need the calldata of the sealed fills. The RE's
  `code6` extraction pattern already fetches it per transaction.
- In the size component, "remainders re-posted" should be replaced by "imbalance pairing bids". The exit component
  should carry the maker pairing bids (21-24% of fills), not only the taker buys.
