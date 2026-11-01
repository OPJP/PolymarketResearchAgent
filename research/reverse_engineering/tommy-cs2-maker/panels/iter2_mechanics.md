# Panel, iteration 2: mechanics and on-chain forensics (fresh eyes)

Lens: how the orders are built and timed. That covers V2 calldata (signing ms, original size, limit), the 1-s in-play
delay, resting orders and cancels, the quote function, complement pairs, and fingerprints of the bot.

I read BRIEF.md, NOTES.md, state.json, FINAL_RULE.md, panels/iter1_*.md and the iteration-2 code. I then ran small
read-only checks on `.cache/re/tommy-cs2-maker/{calldata_all, calldata_pub, calldata_dev, activity_devblocks}` and on
the development-block recordings (`clob_wallets` via `iter_live`, 10-31 12:00-15:30 UTC, dev-unit tokens only). Nothing
sealed was read. All numbers below are exploratory: the live sample is small (23-40 taker orders, 266 maker orders),
and the historical sample pools BUILD and VALIDATE.

## Critique: what the investigation is getting wrong

### 1. The live-lab clock is about 1.1-1.3 s slow, and the headline taker trigger is an artifact of it

Every live result in iteration 2 compares the wallet's signing time (`sign_ms`, the wallet's own clock, from the
calldata) with the recorder's receive time `t` (this laptop's clock). The laptop clock is behind the CLOB server by
about a second.

- **Recorder records.** Every recorded record also carries the server timestamp `s`. For book records, `t - s` has a
  median of -852 ms (all wallet-market tokens) and -1,047 ms (dev-unit tokens, `q` and `f`). For trade records
  (`x`), the median is -1,046 ms, with p5 -1,210 and p95 +84. A message cannot arrive before it was sent.
- **External time sources (15:33 UTC).** HTTP `Date` second flips from www.google.com put the laptop 1.25-1.31 s
  behind. `clob.polymarket.com/time` returned 1793460780 while the laptop read 1793460779.05-.33.
- **The wallet's clock matches the server.** I joined the `x` records (tx hash `h`, server match time `s`) to
  calldata_dev. For its 40 taker orders, server match time minus `sign_ms` is:

  | p5 | p25 | p50 | p75 | p90 |
  | --- | --- | --- | --- | --- |
  | 1,035 ms | 1,038 ms | 1,040 ms | 1,042 ms | 1,056 ms |

  That is the 1-s delay plus about 40 ms. So the wallet's clock is within about ±40 ms of the server's, and its order
  reaches the CLOB about 40 ms after signing. The fast pack signers look the same: medians of 1,055-1,058 ms for
  0x2529c68d, 0xfe8a28be and 0x72aaaaf9.

**Consequence: on the server clock, the depth collapse comes after its signing.** I recomputed the RE's median
near-touch depth profile on the side its taker order consumes (within 3c of the best; 23 orders with books; depth
relative to its value at -2 s).

| offset from signing (s) | -1.0 | -0.7 | -0.5 | -0.3 | 0.0 | +0.2 | +0.5 | +0.8 | +1.0 | +1.1 | +1.3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| receive clock `t` (the RE's) | 1.00 | 0.55 | 0.48 | 0.24 | 0.60 | 0.79 | 0.87 | 0.89 | 0.89 | 0.89 | 0.90 |
| server clock `s` | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | 0.66 | 0.48 | 0.32 | **0.15** | 0.71 | 0.79 |

I also ran the RE's frozen event rule (frac 0.5, reference >= 200, no trade in 1.5 s) on both clocks:

| | Event in [sign - 2 s, sign] (recall) | Event in (sign, sign + 1.1 s] | Event minus sign: p10 / p50 / p90 |
| --- | --- | --- | --- |
| receive clock | 56.5% | 8.7% | -954 / -776 / +71 ms |
| server clock | **0.0%** | 56.5% | **+64 / +149 / +787 ms** |

What follows from this:

- The wallet does not react to the book. It signs first. Other makers then cancel during the 1-s delay window, from
  about 60-150 ms after its signing until the match at +1.04 s. The depth refills at +1.1 s.
- Several iteration-2 numbers come from the clock offset, not the strategy:
  - "collapse precedes 76% of its CS2 taker orders";
  - "median lag 0.77 s", "0.3-1.0 s after", "the pack 1.06 s";
  - "4 of 32 beat the cancels";
  - "acts on 4-8% of collapses" and its acting filter (deep collapse, best ask unchanged);
  - the taker presence AUC (0.846 / 0.900 / 0.943 against about 0.5);
  - the open question "book reader or feed reader".
- **The frozen `final_rule.py` taker trigger is a leak.** In true time, the events it reads come after the decision.
  The examiner's future-block run uses the same laptop clock, so it would reproduce the "match", for the wrong reason.
  The brief calls that kind of result worse than an honest "not decoded". Retract it, or re-tag it as
  "hypothesis, invalid (clock)", before any exam.
- **What survives is stronger than the artifact.** On every public clock, the wallet is the first trace of the game
  event: earlier than the fastest cancelling makers by a median of about 0.15 s, and earlier than the sports socket.
  Its input is upstream of all Polymarket data. The cancel wave is a downstream marker (other operators' reactions).
  As a predictor of its fills (which land at +1.04 s), the wave is market activity, so it falls under the
  co-occurrence baseline, not under a decode.
- **Quick negative: the engine does not lock liquidity for pending FAKs.** Take the 43 maker orders that existed
  before its FAK and were later matched by it. 70% of them are still visible at their level at +0.3, +0.6 and +0.9 s
  (67% at -0.2 s; the rest are outside the recorded top 10). Only 23% are visible at +1.2 s. So the collapse is
  other makers cancelling, not pending orders hiding depth.

### 2. Maker price against the touch was measured on books from after its own order

`dev_books.py` and `price_join_own.py` take "the last snapshot received before `sign_ms`". With `t` about 1 s slow,
that snapshot is from about 1 s after signing, and it often already contains the wallet's new order. I reran it on
the server clock (266 filled maker orders, book 50 ms before signing):

| Price relative to the best bid | Share of orders |
| --- | --- |
| At the bid | **33.5%** (the RE's 44.7%) |
| 1c above | 15.0% |
| 2c above | 6.8% |
| 1c below | 12.8% |
| 2c below | 7.9% |
| 3c below | 4.9% |
| 5c below | 6.0% |

With the book 300 ms after signing, the at-bid share returns to 47%, because its own order made or joined the level.
"Joins the best bid" is therefore partly self-reference. About 22% of its filled maker orders set a new best bid.
Those improving bids are followed within 1.5 s by a cancel wave on the *other* team 18% of the time, against 6% for
at-bid orders (n = 66 vs 89). They look like re-pair or complement bids around events, not quotes placed ahead of the
book on the same team.

### 3. The FAK fill is a race inside the 1-s window, not only "the stale remainder"

From calldata_all (16-22 Oct; 1,698 taker transactions; ages are maker `sign_ms` minus the wallet's `sign_ms`):

- **Late orders.** 19.0% of the maker USD its FAKs took came from orders signed *after* its own FAK was signed, a
  median of 0.54 s later. They were posted into the delay window. 38% of its taker transactions contain at least one
  such order.
- **Other takers.** In other takers' transactions in the same markets, late orders supply 11.3% of maker USD.
- **One large requoter.** One maker, 0xed446954, supplies 27% of the late USD. It is a large maker with odd sizes
  (about 1,000-4,700 shares) in 8,251 fills against 1,850 takers, and 30% of its filled orders were signed after the
  taker's order.
- **Limit premium.** On late orders, the limit premium over the matched maker's price is 0c in 52% of cases, 1c in
  21% and 2c in 9%, much the same as on old orders.
- **Overall age.** Over all orders it takes, the median age is 4.6 s; 36% of the USD comes from orders older than
  30 s.
- **Concentration.** Its taker counterparties are diffuse: the top 1 / 3 / 10 makers supply 9% / 17% / 32% of its
  taker USD, across 557 makers. 91% of the USD it takes comes from complement BUY orders (mints).

So the taker price (ask + 0-2c) and the size cap ("1.22x visible depth") need a model of who is still there at
+1.04 s: stale makers who do not cancel, plus requoters who post into the window. The present model only counts what
was visible at signing, and that visibility was itself measured on the wrong clock.

### 4. Smaller issues

- `state.json` `hypotheses` holds H11-H16 about ten times over; `write_state.py` appends them on every run.
- The sports socket has no source timestamp, so every lead or lag measured against it needs the laptop offset. The
  offset is not constant: -0.85 s, -1.05 s and -1.25 s show up in different checks. Estimate it continuously from the
  CLOB records (for example, a rolling low quantile of `t - s` on `x` records), or record a reference clock next to
  the sports feed.
- This is a property of the laptop, so the shared recorder's `t` is equally affected for every strategy. Report it as
  a tool issue in NOTES and in the return.

## Proposals (ranked by the chance that they close the gap)

### 1. Server-clock forensics of the 1-s delay race: retract the book trigger and rebuild the taker decode on calibrated clocks

- **Hypothesis.** The taker decision runs on a game feed upstream of all public data. On a calibrated clock:
  - it signs a median of about 0.15 s before the first cancels;
  - the fast makers cancel during the delay window;
  - its FAK matches at +1.04 s against the makers who did not cancel and the requoters who posted into the window.

  Nothing public precedes its signing at more than the random rate.
- **Why it fits.** Critique 1:
  - collapse recall before signing is 56.5% on the receive clock and 0% on the server clock;
  - the wave starts at +64 ms (p10) and +149 ms (p50);
  - the wallet's sign-to-match lag is a tight 1,035-1,042 ms.
- **Test (dev blocks, runnable now and on every new dev block).**
  1. Re-run every live result on `s` (the CLOB) and on an offset-corrected `t` (the sports feed): `collapse_*`,
     `dev_book_*`, `taker_size_depth`, `price_join_own`, `grid_collapse` and the `final_rule.evaluate` live path.
  2. For each taker order, from `tommy_cs2_near` price changes in server time:
     - when the first near-touch decrement comes after signing;
     - how fast the wave unfolds;
     - what is left at +1.04 s.

     Use the same measures for each pack member, using their own calibrated clocks (proposal 3).
  3. Control: the rate of server-time collapses in [sign - 2 s, sign] against random times. It should be about 3%.
- **Data.** `clob_wallets` and `tommy_cs2_near` (both carry `s`), calldata_dev, and the `x` records with tx hashes for
  the calibration.
- **Signature if true.**
  - Pre-sign recall stays at the random rate on every dev block.
  - The wave onset sits at about +50-150 ms with a narrow IQR. That means the cancellers share the wallet's feed one
    hop later. A wide, uniform onset over [0, 1 s] would mean heterogeneous, slower feeds.
  - The taker component returns to "unobserved upstream feed". The examinable claims are then selection, the maker
    leg and the exit, and the information lens owns the feed hunt (the cancel wave is its event clock).
  - If instead collapses do precede signing on the server clock on later blocks, the book trigger is rehabilitated
    with a correct lag.

### 2. The maker leg as a feed-blind state machine driven by fills and trades (strong form of X11/B2/B3, aimed at price and outcome)

- **Hypothesis.** The maker ladder runs separately from the taker sniper and has no game feed.
  - It re-signs on public matches and on its own fills (user channel, about 40-80 ms after the server match). It does
    not re-sign on cancel waves.
  - Its price is a deterministic function of the best bid of the *other* makers, its own concurrent complement quote
    (a pair-sum target K of about 0.97, skewed by inventory) and the level just traded.
  - That is why it "does not pull". After the others cancel, its own bid is still the best bid, so a join-the-bid rule
    keeps it. The pack then fills it at +1.04 s.
- **Why it fits.**
  - In iteration 1, its opposite-team re-signs peak at +0.9-1.1 s after its own taker signing, and at +1.00-1.25 s
    after a pack signing with no own taker order. Both are the pack's match time, not the event time (about 0 s).
  - Re-signs follow public takers that matched only other makers at 2.8-3.2x the control rate.
  - Two-sided bursts sum to 0.97.
  - On the server clock, 22% of its filled orders sit above the pre-sign bid, and they cluster around other-team waves.
  - It supplies 8.6% of the pack's maker USD.
- **Test.**
  1. **Historical (calldata_all + calldata_pub, all of 16-22 Oct; also usable on h1/h2 once released).**
     - Put every public match on a match clock: taker `sign_ms` plus that signer's calibrated delay (proposal 3).
       Flag signers whose calibration is wide; the other-taker distribution is p50 1,134 and p75 1,829 ms.
     - Fit the hazard of its maker signings by time since each trigger type:
       - own fill on the same token;
       - own fill on the complement;
       - a public match at its level;
       - a public match elsewhere in the market;
       - none (timer).
  2. **Live (server time).** At each cancel wave that leaves its own complement bid as the top of book (identify its
     orders by `sign_ms`, price and size, from fills, plus +100 level increments at its whole cents), check whether it
     cancels or reprices before the pack's match at +1.04 s.
  3. **Price.** For each trigger type, score `price = min(best other bid [+ step], K(inventory) - own complement bid)`.
     Use the burst structure for deeper levels. Score `price_within_tick` on VALIDATE, against the touch and last-print
     anchors, with and without own state.
- **Data.** On disk (calldata_all, calldata_pub, orders, inventory merges), plus the dev blocks for step 2.
- **Signature if true.**
  - Hazard spikes 40-100 ms after own fills and after public matches at its level.
  - No response to cancel waves within 1 s.
  - Price within a tick for at least 60-80% of orders signed within 2 s of a trigger, well above the 33.5% server-time
    touch.
  - Then an executable replay becomes possible: the ladder plus fills by the observed pack plus merges, on recorded
    books with queue position. That is the only route to `pnl_corr` >= 0.5, because the per-market PnL is set by these
    picked-off complement bids (the residual ends on the loser 68% of the time; maker and taker legs correlate
    -0.85).
  - If instead it does cancel within about 150 ms of the wave, the maker leg shares the feed and the price rule needs
    that feed.

### 3. Per-signer clock calibration through the in-play delay: a sub-50-ms event clock and race ranks for every informed operator

- **Hypothesis.** For every signer, `server match - sign_ms` equals 1 s plus its one-way latency, minus its clock
  offset.
  - The wallet and the fast pack sit at 1,040-1,058 ms with p10 near 1,036-1,040 ms. That makes them precise,
    calibratable clocks.
  - Once corrected, the per-event signing order shows who is first.
  - The wallet's "acts on a small share of events" filter may be a race-position or leftover filter: it fires when it
    expects to be early in the delay queue with enough non-cancelling depth. It may not be about which events its feed
    sees.
- **Why it fits.**
  - The wallet's calibration is tight (1,035-1,042 ms, p5-p75).
  - Iteration-1 offsets are sharp: 0x4ebc2722 at -51 ms (IQR about 50 ms), and the 3-wallet cluster at +0.48 s with
    identical quantiles.
  - FAK fills are bimodal, and 19% of its taker USD comes from orders posted inside the window.
- **Test.**
  1. Live: calibrate each pack signer (P4e, P93, the 3-wallet cluster, P8a, Pdd, Pf1) from `x` server times joined to
     its calldata, for each dev block, including CS2 markets the wallet does not trade.
  2. Historical: apply the offsets to `pack_orders.parquet`. Per event, rebuild the corrected first-signer, the
     wallet's rank, and the gap to the next signer.
  3. Relate the wallet's act / no-act on pack events to:
     - its rank;
     - the server-time book at the event (stale depth that historically does not cancel, its own resting orders,
       spread, price level);
     - the expected leftover at +1.04 s.
  4. Report this as oracle-conditioned on the event (not PIT), as the brief requires.
- **Data.** `x` records with tx hash, calldata of the pack's dev-block transactions (publicnode batches of 40), and
  `pack_orders.parquet`.
- **Signature if true.**
  - Corrected offsets are stable across blocks (within about 10 ms).
  - The wallet acts when it ranks first or second and the expected leftover clears a threshold. That would give a
    frozen rule for the taker side, limit and size, given an event.
  - If instead acting does not depend on rank or leftover, the filter is about its feed's coverage of the event, and
    the information lens should target that.

### 4. The delay-window requoters: decode the taker limit premium and size cap from who posts into the window

- **Hypothesis.** The limit premium (+0-2c) and the size cap above visible depth are set to catch makers who reprice
  during the 1-s window.
  - These are cancel-and-replace requoters such as 0xed446954. They repost 1-2c higher, still too low, after the
    event.
  - The premium is 0 when no requoter is active in that market.
- **Why it fits.**
  - Late-signed orders supply 19% of its taker USD, against 11% for other takers.
  - 0xed446954 alone supplies 27% of that.
  - Its size is 1.22x the (mis-timed) visible depth.
- **Test.**
  1. For each late-signed maker order the FAK matched (calldata_all), find the same maker's previous order on that
     token: from its earlier fills, or live from the level it vacated in server-time price changes.
  2. Measure the requote step against the pre-event ask, and the requote latency after the wallet's signing.
  3. Regress the wallet's premium and size on the requoters' presence in the market (their fills in the previous
     N minutes, which is public) and on the stale depth.
  4. Compare the economics: the USD and markout of late against stale counterparties.
- **Data.** On disk, plus live server-time price changes.
- **Signature if true.**
  - Late orders sit 1-2c above the pre-event touch.
  - The wallet's premium is higher in markets where requoters were active in the last minutes.
  - Size tracks stale depth plus the requoters' typical size. That would give a taker price and size rule that is not
    a trivial anchor.

### 5. A historical match-clock tape for the exam lots without books (h1/h2)

- **Hypothesis.** Trades are published on the CLOB websocket at match time. The `x` record carries the server match
  time and tx hash, so this can be checked directly. For tight-calibration signers, the match time can be rebuilt
  historically as taker `sign_ms` plus a calibrated delay, 2-4 s earlier than block time.
  - The RE's historical anchors use block time: the last print, and the "resting" set of the rebuilt touch, meaning
    orders filled after `s` by *block* time.
  - So they count orders already consumed at match time as resting, and miss the trades the bot reacted to.
- **Test.**
  1. Validate on the dev blocks: the `x` server time against `sign_ms` + delay, per signer.
  2. Rebuild `price_touch.py` and the requote hazards (proposal 2) on the match clock.
  3. Show the examiner the block-time and match-clock versions side by side, and ask them to rule on its
     point-in-time status before using it.
- **Data.** On disk, plus the `x` records.
- **Signature if true.**
  - The rebuilt touch's exact share rises from 24% toward the server-time live figure (about 33%).
  - Combined with proposal 2's trigger-conditioned prices, `price_within_tick` becomes measurable on h1/h2.
  - The FINAL_RULE notes that h1/h2 "can only judge price against the last print". This would lift that limit.

## How to reproduce my quick numbers

- **Clock offset.**
  - `iter_live("clob_wallets", h, h + 3600)` for the 10-31 dev hours: the median of `t - s` over `q`, `f` and `x`
    records.
  - `httpx` HEAD requests to www.google.com in a loop, comparing the local time at the moment the `Date` second
    flips; plus GET `https://clob.polymarket.com/time`.
- **Wallet calibration.** Join `x` records (`h` lower-cased, minimum `s` per hash) to the taker rows of calldata_dev
  (`idx == -1`); compute `s - sign_ms` per taker address.
- **Depth profile and recall.** Use the RE's `near()` (3c) and event rule from `collapse_trigger.py`, unchanged, but
  sort and index by `s` instead of `t`. The consumed side is token-0 `o` for team 0 and token-0 `b` for team 1.
  Profile at `sign_ms + offset`, relative to the value at -2 s.
- **Maker price.** Token-0 `bb` / `ba` from the last `q` / `f` with `s <= sign_ms - 50`, mirrored for token 1;
  `price - bid`.
- **Late orders.** In calldata_all, take wallet taker transactions; their maker rows (`idx >= 0`) with
  `sign_ms > wallet sign_ms`; USD = `fill x price`. 0xed446954 comes from calldata_pub plus calldata_all.
- **No-lock check.** For each maker order matched by the wallet's FAK and signed before it, take its token-0 level
  (`eff` or `1 - eff`) at `sign_ms + {-0.2, 0.3, 0.6, 0.9, 1.2}` s on the server clock, and check that the level size
  is at least 0.9 x the matched fill.
