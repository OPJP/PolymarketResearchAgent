# Panel after iteration 5: information source and data

Lens: what the wallets see, earlier or better, that the investigation has not obtained, and which data would separate
the leading explanations. I read BRIEF.md, NOTES.md, state.json, FINAL_RULE.md, EXAM.md, the three iteration-4 panel
files and the iteration-5 mechanics and assumptions files (written in parallel; I avoid repeating their proposals and
say where mine build on them). I ran small checks on development data only: the live development block 2026-10-31
12:00-18:00 UTC (own `dm_*` feeds, the shared `clob_crypto` and `subs` feeds, the cluster's activity, which I fetched for
14:40-15:25 into my scratchpad), BUILD (10-09..22) and the 10-26 13:00-13:30 all-match calldata pilot. Nothing in
`.cache/live/sealed/` or in a sealed period was read. The scripts are in my session scratchpad
(`C:/Users/REMOTE~1/AppData/Local/Temp/claude/C--Dev-trading-research-PolymarketResearchAgent/97f207f2-bd1a-4cdb-a63d-2290c58d22c3/scratchpad/`:
`anchor_check.py`, `depth_check.py`, `toprung_check.py`, `jitter_check.py`, `touch_at_match.py`, `finebin_check.py`).
It is a quiet Saturday, so every live number below is small-sample and descriptive.

## What my checks found

C1. **No public price anchors the rungs, and the bot reads the live book with no lag.** 3,582 three-wallet bursts
(14:06-14:40 UTC, 10 markets). I took the offset of each burst price from several anchors: the token's best bid, mid,
last trade and Polymarket's display price, at lags 0-4,000 ms, plus the TWAP-60 fair of the futures bookTicker, Binance
spot, Coinbase and Bybit (vol x 1.0-2.0, lags 0-1,000 ms). No anchor concentrates the offsets. The entropy is 4.0-5.3
bits, and the three most common offsets hold only 12-27% of bursts. The best anchor is the current best bid, and every
lag makes it worse (top-3 share 0.216 at 0 ms, 0.197 at 1 s, 0.185 at 4 s), so a stale (REST-polled) view of the book is
ruled out. This agrees with mechanics finding 2. Depth-pegged placement also fails: "the level where the resting size
ahead first reaches D" is within a tick for at most 23% (D = 2,000 shares), the same as "best bid - 4 ticks". The size
ahead of a burst has a median of 4,174 shares, and **33.5% of bursts sit 10 or more distinct levels below the touch,
outside a top-10 snapshot.**

C2. **The two ladders share one hidden center that public inputs do not explain.** The offset below the touch is
autocorrelated: 0.59 between consecutive same-side bursts (about 1 s apart) and 0.31 ten bursts on (about 15 s); a
shuffled null gives -0.007. Mid, futures fair, futures edge, spread, time left and horizon explain R^2 = 0.096 of the
offset. The residual keeps autocorrelation 0.56 / 0.39 / 0.33 (lags 1 / 5 / 10), and it correlates **-0.52** with the
other token's latest residual: when the Up ladder is deeper than predicted, the Down ladder is shallower. I defined the
implied center F* = (top Up rung + 1 - top Down rung) / 2 (918 seconds, 8 windows). F* minus the Up mid has median
-0.02 and sd 0.037; the half-spread h* = (1 - qU - qD) / 2 has median 0.065 (p10-p90 0.04-0.085), which matches the
mechanics panel's pair sum of 0.88. **The futures fair minus the mid explains R^2 0.11 of F* - mid (slope 0.155), own
net inventory adds nothing (corr 0.005), and past mid changes or lagged futures fairs do not carry over to held-out
windows (R^2 < 0).** The unexplained part of F* has autocorrelation 0.62 / 0.37 / 0.19 at 1 / 5 / 15 s. That is a
reservation price with a half-life of a few seconds, set by an input nobody has measured yet.

C3. **Price is limited by information freshness, and the shared recorder fixes it.** I took 557 cluster BTC 5m BUY
fills (12:18-15:00 UTC) and found the server match ms of each through its transaction hash in the shared recorder's
`x` stream (544 matched with a book, 98%). The rule "last clean print before the match minus 0.01" is within a tick
for **0.781** of them (exact 0.450). The same rule with the anchor taken at least L ms before the match falls to 0.684
(250 ms), 0.618 (500 ms), 0.590 (1 s), 0.526 (2 s) and 0.487 (3 s). The token's best bid in the shared 200-ms snapshots
200 ms before the match gives **0.796** (500 ms: 0.628; 1 s: 0.573); at the match it gives 0.948, but that is
tautological. On the first 448 fills (to 14:46) the two rules gave 0.826 and 0.806. The block-time tape sees prints
about 2.3 s late, which on this decay curve is worth about 25 points. The VALIDATE score (0.709) comes from busier
weekdays, so it is not directly comparable.

C4. **Faster reference data does not predict when it is filled.** 13 BTC 5m windows, 340 fills timed at the match ms
(14:10-15:10 UTC). The futures bookTicker mid move against the token over the previous 250 / 500 / 1,000 / 3,000 ms
ranks a fill in the next 1 s at AUC 0.52 / 0.52 / 0.55 / 0.57, and in the next 10 s at 0.51 / 0.52 / 0.55 / 0.59.
Polymarket trades in the previous 10 s give 0.66-0.68. On held-out windows, activity scores 0.584 and activity plus
futures 0.579 (1-s bins); for 10-s bins, 0.602 and 0.584. The examiner's 2-s delay test (presence -0.003) points the
same way: for presence the trigger is Polymarket taker arrival, not a feed.

C5. **Two information directions I checked and do not propose.**
- Same-expiry alignment. BTC 5m windows that end with a 15m window hold 35.7% of BUILD fills (33.3% expected), and
  their return is no higher; hour-end windows are no better either. The cluster's BTC 15m buy dollars fall 45.9% in
  600-840 s of the window, against 38.5% for all taker dollars, so the "late" 15m work is mostly where the market
  trades. This weakens assumptions Q6 without killing it.
- Counterparty app. In the 10-26 all-match pilot, the takers filling the cluster carry builder 0 in 87.6% of cases
  (others 85.2%), and signature type 1 in 22% (19%): no front-end concentration (n 113).

C6. **"Side = the token just sold" fails on the last print.** At the match clock, the last clean print before the
match predicts the cluster's side in only 0.45-0.55 of fills (n 544). If assumptions Q1's reactive post exists, its
side has to come from the post's own trigger, not from the last print.

## Critique

1. **One clock for two problems.** Every rule runs on the block-time tape. For price that costs about 25 points (C3);
   for presence it costs almost nothing (C4, examiner lag test). The investigation has treated faster feeds as the
   route to presence (futures features +0.0007, the venue race, X11 parked as open). Information freshness belongs in
   the price and quote rules. Presence is bound by taker arrival, so its ceiling should be measured (mechanics M2)
   before more feeds are added to it. Note that the old on/off oracle (0.862) no longer applies: 94.5% of VALIDATE
   windows are active, and within active windows R3 scores 0.708.
2. **The quote is fitted one side at a time and raced against one feed at a time.** The reported law
   q = -0.055 + 0.69 mid + 0.25 F is a per-side regression. It hides a common center whose residual is -0.52
   correlated across the two ladders (C2). Every information race so far was run on single-side quotes:
   - Binance futures against other venues, on re-post direction, conditional on a futures move (6-9% of re-posts);
   - Chainlink, on near-touch single-side quotes, a subset selected on the touch (MAD 0.105 with a +0.08 median offset
     flagged for a stamping recheck).

   Neither settles what the engine's fair is. The right target is F* - mid. Its slope and R^2 against a candidate
   (fair_X - mid) do not care about a constant offset or a basis error.
3. **No venue near the bot has been tested.** The cluster posts about 85 ms after a Polymarket print (assumptions Q1)
   and 50-250 ms after a Binance futures move. A bot co-located with the CLOB would react to prints in a few ms, so
   85 ms suggests the engine sits one network hop away from the matching engine. From there, venues in its own region
   could be faster than Binance (Tokyo). The race had no Deribit (London), Bitstamp, LMAX or Kraken stream.
4. **The future exam has no data for a quote-state rule yet.** These blocks are sealed, so the examiner's next lot is
   recorded only by what is running now:
   - 10-31 18-24 UTC (it starts in under 3 hours), then 11-01 00-06 and 12-18 UTC.
   - `code5/rawrec.py` stops at 18:00 UTC, and the plan restarts it in development blocks only.
   - The Binance futures bookTicker has no archive (404).
   - The shared `clob_crypto` keeps top-10 levels: 33.5% of bursts are outside them, and only 10-11% of bursts appear
     as exact increments. Its status shows 49 reconnects, the last with "slow consumer: send buffer full".

   As configured, `dm_clob_raw` grows about 19 MB/h and `dm_bnf` about 2.7 MB/h, so the 300 MB cap lasts about 13 h. A
   slim exam recorder would fit 36-48 h: futures bookTicker and aggTrade, the CLOB raw stream of the current BTC 5m and
   15m windows restricted to levels within about 25 ticks of the touch plus `x` records, and RTDS; it would drop
   Coinbase, OKX, Bybit, Hyperliquid and spot, which lost the race. Without it, a rule built on these feeds can never be
   examined on future blocks, and the investigation fails by construction.
5. **Reader robustness is part of the rule.** `tools/live.py iter_live` still dies on today's shared files: I got
   `zlib.error: invalid block type` on `subs` within the 12:00-15:00 block. `code5/rawread.iter_dm` reads the same
   shared feeds correctly. A frozen rule that takes the shared recorder through `iter_live` may crash on the
   examiner's sealed files. Give `final_rule.py` a tolerant reader that honours `ALLOW_SEALED`.
6. **The size and switch events are the only decision times with a clock.** The engine leaves `timestamp` at 0, but a
   size switch shows in all three wallets within the same second (mechanics finding 7). Those few dozen
   second-precise events are where external inputs can be timed. Mechanics M5 already proposes the vol hazard. From
   this lens, add the external clocks to it: Binance funding at 00/08/16 UTC, Deribit's 08:00 UTC expiry, the CME
   Sunday open, US data releases in the period, DVOL jumps and status.polymarket.com events. I do not make this a
   separate item.

## Proposals (ranked by the chance they close the gap)

### I1. Price (and the R3 features) on the match clock from the shared recorder's trade stream: an examinable rule now (strong form of X11 / iter-4 I2)

- **Hypothesis.** The cluster prices its filled orders off Polymarket's match-time stream, at the print or the touch
  of the last few hundred ms. The 29% price misses of R3 are mostly the 2.3-s staleness of the block-time tape. A rule
  that reads the shared recorder's `x` records and `q` snapshots on server ms reaches the 80% bar. The anchor is
  trivial, which the price component must state, as the brief allows. This also gives assumptions Q1 (a fresh post at
  the touch about 85 ms after a print) a direct, examinable form.
- **Why it fits.**
  - C3: 0.781 / 0.796 on 544 fills; 0.826 / 0.806 on the first 448.
  - The accuracy decays monotonically with the anchor's age, by 10 points in the first 250 ms. That is the signature
    of a quote set from the latest print, not from a fair.
  - Iteration 2 found that within-second print order moves the anchor by 8 points.
- **Test.**
  1. Freeze the rule on 10-31 12-18 UTC. Candidates: (a) last clean `x` print before the match minus 0.01; (b) the
     touch at match - 200 ms; (c) (b) when its snapshot is under 250 ms old and the last print is older, else (a).
     Choose among them on 11-01 06-12 UTC only.
  2. Score on 11-01 18-24, 11-02 00-06 and 11-02 12-18 UTC, the first weekday US session. Report it per wallet,
     against the trivial anchors on the same clock, and against R3's block-time anchor on the same fills (data-api
     tape).
  3. Report the share of cluster fills whose transaction appears in `x` (98% today) and the accuracy of the data-api
     fallback for the rest.
  4. Rebuild R3's presence and side features on the same clock (server-ms prints, bins on match time) with a same-clock
     activity baseline. The gain over the block-clock version is expected to be small for presence (C4), so report it
     and move on.
  5. For the released lots, use the taker `sign_ms` of all-match calldata as the match clock (X11) on a few STUDY
     hours. Only the future blocks can examine the shared-recorder version.
- **Data.** Shared `clob_crypto` (`x` with hash and server ms, `q` snapshots), `subs` for tokens, the cluster's
  activity, all through a tolerant reader. All of it already exists in sealed blocks for the examiner.
- **Signature if true.** Within one tick >= 0.80 in every development block and for each wallet, with the same decay
  curve. On the same fills, the block-time version scores 0.15-0.25 lower. If accuracy stays near 0.78 on weekdays,
  look at the misses: two ticks below after the level was used up (iteration 4: "after a bid hit it is often filled
  two ticks lower") points to adding the depth consumed by the print.

### I2. Identify the ladder's center F* and race the information inputs on it, now that futures and inventory fail (new; strong form of A1/A2/X10/X12, on the target the mechanics panel's M1 builds)

- **Hypothesis.** Both ladders hang off one reservation price, F*(t) = mid + w (X(t - tau) - mid) + slow state. X is an
  input the investigation has not built, and F* follows it with a half-life of a few seconds. The skew of the center is
  the cluster's only directional decision. It sets which ladder stands nearer the touch, and so which side fills. The
  candidates, in order of prior:
  - (a) a Chainlink-based fair: the RTDS 1-s Chainlink price against the window's real strike, which is the RTDS
    TWAP-60 stamped at the window start (= priceToBeat, known from the start). The futures-Chainlink basis moves on a
    seconds-to-minutes scale, which would produce exactly a slowly varying skew. A positive result would revive E3 in a
    pricing (not settlement-informed) form;
  - (b) a venue near the bot (critique 3): Deribit BTC-PERPETUAL and its index, Bitstamp, Kraken;
  - (c) a composite or median of venues (Chainlink-like);
  - (d) a different fair model: vol lookback 30-900 s, vol scale 1.0-1.6 or DVOL, digital with or without the TWAP
    lock-in, a drift from the futures basis or funding, an EMA of the futures fair (half-life 2-30 s). In C2, F* - mid
    correlates 0.18-0.24 with the mid change over the last 10-60 s, a hint of a slow filter;
  - (e) for BTC 15m, Kalshi's 15-minute BTC market on the same quarter hour (A4b; REST order book polled at 1 Hz).
- **Why it fits.** C2:
  - one center with a -0.52 cross-ladder residual correlation;
  - an unexplained sd of 3.7 c;
  - autocorrelation 0.62 at 1 s;
  - futures R^2 0.11 and inventory 0.

  The mechanics panel's M1 regresses the skew on the futures fair and inventory. On my sample that regression already
  fails its R^2 >= 0.5 signature. The information question is what else enters.
- **Test.**
  1. On 10-31 12-18 and 11-01 06-12 UTC (fit) and 11-01 18-24 and 11-02 (test), compute F* and h* every second where
     both sides have a top rung within 1.5 s. Also use explicit rung tracking where it works, and check whether the
     results change with the second rung.
  2. Calibrate the CLOB and Binance server clocks first, using the cluster's own trades, which appear in both the CLOB
     `x` stream and the block.
  3. For each candidate X and lag tau (0-2,000 ms), regress F* - mid on (fair_X - mid). Compare held-out R^2, the
     slope and the residual autocorrelation, and condition on the best candidate (a horse race, as in iter-4 I1).
  4. Add the London venues to the recorder: Deribit `ticker.BTC-PERPETUAL.raw` and `deribit_price_index.btc_usd` on
     `wss://www.deribit.com/ws/api/v2` (public); the Bitstamp `live_trades_btcusd` channel. Use server stamps.
  5. Triangulate the bot's location from its two reaction lags (about 85 ms to Polymarket prints, 50-250 ms to Binance)
     and public inter-region RTTs. The venue nearest the bot is the first candidate to race.
- **Data.** `dm_clob_raw`, `dm_rtds` (staggered, 99% coverage), `dm_bnf`, plus Deribit and Bitstamp (to add); Deribit
  DVOL (works); Kalshi public market data (to verify, record the failing request if it is blocked).
- **Signature if true.**
  - One input gives held-out R^2 >= 0.5 on F* - mid with a stable slope.
  - It removes most of the residual autocorrelation and the -0.52 cross-ladder correlation.
  - Its lag peaks at a fixed tau consistent with the bot's location.
  - The top rung, center minus h*(time left), is then within a tick for >= 60% of bursts (21% now).
  - Side, as the ladder nearer the touch, rises above R3's 0.663.

  If no input reaches R^2 0.3, the center is internal state (its own fills, a filter of its own, or noise). The account
  of the unexplained part is then "sd 3.7 c of the reservation price, explained by no public feed", with the list
  above as evidence. That is the quantitative wall statement the brief asks for.

### I3. What the counterparties act on: taker signing ms against the RTDS display, Polymarket jumps and futures moves (new; strong form of C3, complements assumptions Q4)

- **Hypothesis.** The takers who reach a ladder 4-8 ticks below the touch, through about 4,000 shares, come in two
  classes. Slow takers react to what the Polymarket page shows (the RTDS Chainlink price, 1-2 s behind futures, or a
  Polymarket price jump) and cross at stale prices. They pay the cluster. Fast takers sign within 100-300 ms of a
  futures move and pick it off. The windows that pay ("busy periods": paired cost 0.89) are the ones with many slow
  takers, and a replayed quote law earns the same windows only if it reproduces where the slow class reaches.
- **Why it fits.**
  - C4: fills are not triggered by futures moves.
  - Fills come from larger, dispersed takers (iterations 2-3).
  - The PnL correlation is stuck at 0.33 against a 0.69 / 0.78 ceiling, and size is not the reason (X22).
  - The iteration-4 match-clock study saw favourable 2-5 s token moves before fills and adverse 0.25-1.5 s moves.
- **Test.**
  1. In the development blocks, fetch the calldata of every BTC 5m match (about 800 per 3 minutes; sample 10-20
     minutes per block).
  2. Each taker order's `sign_ms` gives its lag behind the last futures bookTicker move of more than $5, the last RTDS
     Chainlink update (payload timestamp and receive time), and the last Polymarket mid jump of 2 ticks or more. Use
     the laptop clock only through server stamps.
  3. Classify the takers by lag mode. For matches filling the cluster against the rest, compute the class shares and
     the cluster's markout per class (payout minus price, and the futures fair move after 5/30/60 s).
  4. Historically (STUDY, `b1_takers_study.parquet`, futures ms from `aggfut_2026-10-26.parquet`), use the futures part
     only. Then, per window, correlate the cluster's PnL with slow-class volume.
- **Data.** publicnode calldata (works at about 75 tx/s), `dm_rtds`, `dm_bnf`, `dm_clob_raw`, STUDY calldata on disk.
- **Signature if true.**
  - The cluster's profitable fills come from takers whose signing follows RTDS updates or Polymarket jumps by
    0.3-3 s with no futures move.
  - Its losing fills come from takers signing within 300 ms of futures moves.
  - Per-window cluster PnL correlates with slow-class volume at 0.4 or more.

  The PnL component then has its missing input, and the replay (D3) must use per-class arrival rates rather than the
  pooled tape. If the classes do not separate the markouts, the counterparties are not the information story, and the
  remaining PnL gap is the cluster's own quote state (I2).

### I4. A slim exam recorder through the sealed blocks, built around the inputs of I1 and I2 (data; required for any live-input rule)

- **Hypothesis.** Not a strategy hypothesis. It is the condition for "found" on the future exam: a rule whose inputs
  are the raw book, futures bookTicker or RTDS can be examined only if those inputs are recorded in sealed blocks. The
  next one starts at 18:00 UTC today.
- **Why it fits.** Critique 4: no archive for bookTicker; 33.5% of rungs outside the shared top-10; `rawrec.py` stops
  at 18:00 UTC; the shared feed has slow-consumer disconnects.
- **Test.**
  1. Restart `code5/rawrec.py`, or a slim copy, with `--until` at the end of the exam horizon (for example 2026-11-02
     18:00 UTC). Feeds: futures bookTicker and aggTrade; BTC 5m current and next and BTC 15m current; CLOB raw changes
     within 25 ticks of the touch plus `x` and full books every 30 s; RTDS (staggered); Deribit perp if I2 adds it.
  2. Measure MB/h in the first hour and stay under 300 MB and 100 MB of memory. Record it in `state.json` `live_lab`.
  3. In every development block, check completeness against the cluster's calldata: the share of its filled orders
     whose posting add is in the recording.
- **Data.** Public websockets already verified; tools/live.py `Writer` (files sealed blocks automatically).
- **Signature if true.** At least 95% of cluster fills in development blocks have their posting add and match in the
  recording, with gaps under 1% of seconds. The examiner can then run I1 and any I2-based rule on 12+ sealed hours.

## Notes for the RE

- Do now, before 18:00 UTC: I4 (the recorder), then I1 steps 1-3 on today's block, which need only data that already
  exists.
- I2 shares its construction with mechanics M1. Run them as one study: M1 builds F* and h*, and I2 races the inputs on
  them. If both fail, I2's list is the evidence for the wall statement.
- Readers: use `code5/rawread.iter_dm` (or a copy in `code/`) for the shared feeds too, in development and in
  `final_rule.py`.
- My checks used a laptop-clock filter only to pick files; every timing above uses server stamps (CLOB `s`, Binance
  `T`).
