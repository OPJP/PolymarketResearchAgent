# Panel, iteration 13: information source and data

Reviewer lens: what the bot sees, earlier or better, that the investigation has not obtained; which data would most sharply
separate the leading explanations; how to fetch it on this laptop.

## Data used for my checks

Development data only. Nothing was opened from `.cache/live/sealed/`, from any capture day file at or after H, or from any
other strategy's workspace or cache. Every process stayed under 300 MB.

- **Investigation intermediates (this strategy's cache):**
  - `.cache/re/btc5m-bot/it13/dcside13_frame.parquet`: 117,791 operator taker orders with a capture match ms, 10-17..22;
  - `windows.parquet`, `fills.parquet` (used only for operator tx hashes and token maps);
  - `fut/<day>.parquet` (Binance USD-M BTCUSDT aggTrades, exchange ms).
- **The reduced public capture** (Fahri-5/updown-5m-polymarket-raw, revision f848a77c), as already ingested by the
  investigation in the session scratchpad `it13/hf_dl/`: `btc_2026-10-17..22` (Binance spot book on the collector receive
  clock, spot trades with exchange ms), `pm_trades_*` (server-ms matches with tx hashes), `btcrtds_*` (RTDS Chainlink).
- **New metadata only:**
  - the Hugging Face dataset listing (search "polymarket", by last modification) and file trees of six datasets; only names
    of files dated before H were kept;
  - three READMEs;
  - the PolyBolt contract `https://ws-live-v2.polymarket.com/asyncapi.json` (HTTP 200, 63 KB).
- **Scripts and outputs:**
  `C:\Users\REMOTE~1\AppData\Local\Temp\claude\C--Dev-trading-research-PolymarketResearchAgent\97f207f2-bd1a-4cdb-a63d-2290c58d22c3\scratchpad\p13i\`:
  - `legs_info.py` / `legs_info2.py`: fan-out leg timing;
  - `lagscan.py` / `lagscan2.py`: 30-ms information windows around the decision;
  - `cutscan.py` / `cutscan2.py` / `cutscan3.py`: cumulative windows by cutoff;
  - `sizescan.py`: size;
  - `crowdknee.py`: the crowd's horizon;
  - `hftree.py`: dataset trees.

  Each script has a matching `.json` output.

All checks are univariate with no fitted parameter. I looked at all six capture days, including 10-20..22, which the
investigation uses as its pre-registered scoring days. The proposals below therefore choose every constant by physics or on
10-17..19 only, never from my curves.

## Critique

### 1. The historical decision clock ends 45-60 ms too early, and that, not a missing series, is why the archive side is 75% while the live side was 83%.

**How the clock is built now.** The frozen exam route (`dc_exam13`) and `dcside13` set the decision at a = m - 180 ms on the
capture's collector receive clock. That collector receives Binance about 131 ms after the exchange stamp (spot trades: 131-134
ms median). So every feature window ends at exchange time ~ m - 311.

**Where the side information actually is.** Three independent readings put it later, at exchange time ~ m - 300 to m - 250:

- **The live lab already measured it.** kernel7 put the earliest sharp peak, Binance USD-M BTC, at exchange time
  [m - 300, m - 250), with 87.9% agreement.
- **The capture shows the same.** In 30-ms windows, single-leg first legs (16,335 on 10-20, 12,792 on 10-21) agree at the
  following rates:

  | series | window (exchange time) | agreement | note |
  |---|---|---|---|
  | Binance spot trades | [m - 296, m - 251) | 84.5-85.1% / 81.5-82.8% | |
  | Binance USD-M aggTrades | same | 80.6-81.2% / 79.1-79.6% | trade-price changes occur twice as often there as 300 ms earlier |
  | collector spot book | [a + 20, a + 50) | 80.8% / 78.0% | |

  Agreement falls back to 63-77% by 60-90 ms later, so this is a short event, not a slow drift.
- **The cumulative cutoff scan agrees.** It uses the spot-book microprice sign over [m0 - c - 250, m0 - c) on the
  exchange-equivalent clock (receive - 131). Every leg inherits its event's FIRST-leg match m0, so this is honest per
  decision. There is no fit, full coverage, and all six VALIDATE days:

  | cutoff c (ms before m0) | all orders | first legs | per day, first legs | XM one-sided windows (411) |
  |---|---|---|---|---|
  | 311 (= the frozen route) | 67.2% | 68.2% | 67-69% | 74.3% |
  | 281 | 73.4% | 74.3% | | 77.3% |
  | 266 | 78.2% | 79.1% | 76.4-83.4% | 81.9% |
  | 251 | 80.6% | 81.4% | 77.2-85.7% (weekend included) | 82.7% |

  At c = 251 the by-wallet figures per order are DS 81.0%, GF 80.7% and XM 75.9%.

**The gain stops at the knee.** On 10-20 / 10-21, first legs:

| cutoff c | 10-20 | 10-21 |
|---|---|---|
| 311 | 68.2% | 69.9% |
| 281 | 75.4% | 76.1% |
| 251 | 83.7% | 82.3% |
| 221 | 84.9% | 83.1% |

The information arrives between exchange m - 281 and m - 251 and almost none after. Post-decision continuation would keep
rising.

**The knee is not generic market drift.** Non-operator taker BUYs on 10-20 that do not co-arrive with the operator
(284,346) agree 59.9% at c = 311, 60.3% at 266 and 58.8% at 191: their curve is flat. The 18,981 crowd BUYs matched within
±50 ms of an operator match show the operator's knee: 72.9%, then 80.0%, then 81.6%.

**Physics.** The knee implies that transit plus reaction is about (m - 150) - (m - 255) ≈ 100-110 ms. That is the
Tokyo-to-London one-way that iteration 11 measured for a well-routed London host (105-115 ms). The investigation stacked the
slower collector's 131 ms and a 30-ms posting latency on top of the 150-ms delay.

**What this changes.**

- Finding 14 of iteration 13 ("the live 83% is not a missing-series effect") is right about series and wrong about the
  cause. The capture's windows end before the trigger arrives.
- The next-step item that routes the full venue model into `evaluate()` would freeze the mis-clocked windows into the exam
  route. It should wait for a re-clocked, pre-registered model.

### 2. The other "no sharp clock" results were computed on clocks with the same offset risk.

The following results all fix the decision at a = m - 150 or m - 180 on receive clocks, or label takes in a 550-ms window:

- "only ~9% of decisions are time-locked";
- "79% have no Binance price change in [a - 500, a - 10)";
- the flat (a - tau) onset kernel;
- "the recorded inputs explain only 14-21% of the shared selection".

If the bot's horizon is exchange m - 250, an onset at exchange tau produces a match near tau + 250 ± 15 ms. The take label
should be about 30 ms wide, not 550. These measurements need to be redone on the knee clock before they are used in a wall
account (proposals 2 and 3).

### 3. Follower legs mix post-decision information into the per-order and XM figures.

**The gaps between legs are bimodal.** Same-outcome legs within 300 ms, over six days:

- a mode at 0-40 ms (8,773 gaps): a true fan-out;
- a second mode at 180-220 ms (4,133 gaps; trough 870 at 160-180 ms). That is one taker delay plus 30-70 ms.

**Sequential followers carry later information.** For followers 150-300 ms after the previous leg, the move over their own
last 250 ms agrees 82.4% (XM 87.2%). The previous leg's features give 70.3% (XM 69.2%).

**XM is affected most.** 44.8% of XM's orders are followers, with a median lag of 183 ms behind the first leg.

So XM's reported 81-84% one-sided-window side partly reads moves that happened after the operator's first decision. Scored
per decision on the current clock, XM's windows give 74.3% univariate. The re-clocked 82.7% should carry the XM claim, not
the follower continuation.

### 4. Two things re-clocking does not fix, which bound what the knee can deliver.

- **Size.** P(large) from |move| at the knee has AUC 0.620 (0.631 at the old clock; first legs on 10-20 / 10-21, 3.6% large).
  The lean is not tick strength at this scale. It stays own-state (pyramiding), as found before.
- **Late decisions.** The late window stays weak. First legs by window time:

  | window time | c = 251 | old clock |
  |---|---|---|
  | 0-60 s | 86.5% | 71.0% |
  | 60-120 s | 85.9% | 70.5% |
  | 120-180 s | 81.9% | 68.4% |
  | 180-240 s | 74.6% | 61.0% |
  | 240-300 s | 67.4% | 58.2% |

  The late decisions have another input or are pairing.

### 5. No public BUILD-period millisecond capture exists, and the paid or gated one needs the user.

**What the listing shows.**

- No new non-gated dataset covers 10-09..16 with server-ms Polymarket matches:
  - Houroux/polymarket-l2-history and trentmkelly/polymarket_historical_data hold only July files before H;
  - whodisidk's exchange data ends 08-29;
  - marketlens is one June day;
  - polyorderbooks is a 250-ms grid;
  - TimeSeventeen/Polymarket-v2 is on-chain OrderFilled logs, like the investigation's own.
- RabbitGo777 published one-day all-venue files for ETH, SOL, XRP, DOGE and BNB on 10-20 (10-31 21:58 UTC). They allow the
  ETH lead to be tested on the same clock.

**What would change it.** polydata5/polymarket-updown-5m-ws is gated "auto" and covers 08-21 onward. With it, decision-clock
models could be fitted on BUILD rather than on VALIDATE's first three days. Only the user can accept those terms.

**PolyBolt is not the shared input.** Its `price.crypto` channel is gated and sends "about one update per second per symbol"
(source pyth or chainlink). It cannot carry a millisecond trigger. The Chainlink RTDS reports in the capture sit on an
exact 1-s grid (timestamp mod 1000 = 0 for all 81,393 on 10-20), relayed 0.76-1.69 s late.

## Proposals (ranked by the chance they close the gap)

### 1. Re-clock the side on exchange time at the bot's information knee (new; it supersedes the window placement of pre-registrations 3 and 4)

**Hypothesis.**

- The bot's information horizon is a fixed exchange-time offset, about 250-265 ms before the match. That is the 150-ms delay
  plus a ~100-110 ms Tokyo-to-London route plus a few ms of reaction.
- The side is the Binance microprice move just before that horizon.
- At the right clock, the public capture gives at least 80% per decision at full coverage, pooled and per wallet. The
  investigation's 75-77% is a clock artefact.

**Why it fits.**

- Critique 1: 67% univariate at the frozen clock against 79-81% at c = 251-266 on all six days.
- The live kernel7 peak sits in the same place.
- The knee flattens beyond it.
- Slow crowd orders show no such rise.

**Test.**

1. **Pre-register the cutoff from physics, not from accuracy**, before any refit: c = D + T + r = 150 + 105 + 5 = 260 ms.
   - D is the measured taker delay.
   - T is the iteration-11 measurement of Binance-to-London transit.
   - r is the reaction.
   - As a second, data-driven definition, take the knee of a two-segment linear fit of accuracy against c, estimated on
     10-17..19 only.
2. **Move every series onto its own exchange stamps, cut at m - c:**
   - spot book: collector receive - 131;
   - spot trades: capture `exchangeTimestampMs`;
   - USD-M BTC / ETH aggTrades: `T`;
   - OKX trades: exchange ms;
   - Bybit ob: bin end.

   Refit dcside13's model unchanged (PARAMS / ROUNDS, K = 100..2000) on 10-17..19 and score 10-20..22 once. Report:
   - per decision, with every leg at its event's first-leg instant;
   - per order;
   - per wallet;
   - XM's one-sided windows;
   - each half.
3. **Falsification checks, reported whatever the result:**
   - placebo instants m ± 3 s show no knee;
   - the knee sits at the same offset per wallet and on the weekend days;
   - the gain from c = 260 to c = 200 is at most 1.5 points;
   - on the 10-31 live decisions (the investigation's E-stamped venue records), the knee sits at the same exchange offset.
4. **Exam route.** Change only the cutoff constant in `dc_exam13`, under a new pre-registration. The capture's day files
   carry spot trades with exchange ms and the spot book, so the route needs nothing new.

**Data.** Already on disk: `it13/hf_dl`, `fut/`, `bybit_ob/`, `venues/okx`.

**Signature if true.**

- Per decision ≥ 80% on 10-20..22 at c = 260 (univariate already 78-80%), and DS, GF and XM each ≥ 77%.
- The knee is in the same place on every day.
- The curve is flat beyond the knee.
- The side condition then holds pooled, not only for XM.

**If false.** The gain keeps rising past the knee as fast as before it. The 80% is then post-arrival continuation and must
not be used. The block-clock and current decision-clock figures stand, and the account says so.

### 2. Rebuild the take selection and the hazard on the knee clock with a 30-ms label (strong form of X111 step 3, X101 step 3 and X113's PIT hazard)

**Hypothesis.** The selection looked "weakly decoded" and "shared with the fast crowd on an unrecorded input" for two
reasons:

- the onset tables and labels sit on receive clocks 45-60 ms off;
- the take label spans 550 ms.

On the knee clock, an operator match follows a qualifying Binance move by a fixed 250 ± 15 ms. The fast crowd's co-takes are
the same move seen on the same route.

**Why it fits.**

- Critique 2.
- The co-arriving crowd shows the operator's knee (critique 1).
- Kernel7's peak in live data.
- The "locked" excess was measured inside a ±25-ms bin of that same peak.

**Test.**

1. **The unit.** On the capture's six days, 10-ms instants tau on the exchange-equivalent clock.
2. **The features**, all ending at tau:
   - spot microprice changes over 30 / 100 / 250 ms;
   - USD-M trade changes;
   - rel;
   - |ask - 0.5|;
   - age of o's ask (server ms) where the touch exists (10-20 / 10-21).
3. **The label:** an operator taker match on o in [tau + 235, tau + 280). Fit on 10-17..19, score on 10-20..22.
4. **The comparison.** Compare with the same model under the old label [tau + 150, tau + 700), and with features ending
   45-60 ms earlier.
5. **Recompute on the knee clock:**
   - the time-locked share;
   - the "no Binance change before the decision" share;
   - the crowd co-take log OR conditional on the design (X101), taking crowd matches from the capture's non-operator BUYs.
6. **Then the replica.** Feed the hazard to the decision-level replica (X113 step 5), where races are resolved by arrival on
   the capture.

**Data.** As in proposal 1, plus the capture's `pm_trades_*` for crowd matches. W4 and W5 must be excluded by tx hash.

**Signature if true.**

- The locked share rises from 9-13% to a majority.
- The hazard's held-out AUC at the 30-ms label is clearly above the 0.68-0.72 of the onset tables.
- The crowd co-take OR conditional on the knee-clock design falls by at least half.
- The replica's per-window net correlates above nf12b's 0.42. Condition 5 then moves through decision overlap.

**If false.** The selection really does run on something besides the Binance trigger. The residual is then stated on the
right clock.

### 3. A per-venue and per-trader knee map: which feed the bot reads and who shares its route (strong form of X87 steps 1-4 and X115, moved onto VALIDATE)

**Hypothesis.** If the bot reads venue v directly from London, its knee on v's exchange clock sits at about
m - 150 - r - T(v, London).

| venue | transit to London |
|---|---|
| Deribit (LD4) | ~1-2 ms |
| Coinbase (us-east) | ~38 ms |
| Binance, OKX, Bybit | ~100-115 ms |

A venue whose knee sits later than Binance's, after its own transit is removed, and which still adds side information is a
faster input than Binance. Iteration 11's "London relay" (Deribit reflects Binance about 60 ms after the Binance stamp) is
the candidate. The same map per trader shows whether the fast crowd shares the operator's latency class.

**Why it fits.**

- Proposal 1's knee implies about 100-110 ms. That is consistent with a direct Tokyo route, but a relay has not been ruled
  out on VALIDATE.
- The examiner will need a physical defence of the cutoff, and this map provides it.

**Test.**

1. **Fetch the venue histories** for 2-4 hours of 10-17..19 and 10-20..22:
   - Deribit BTC-PERPETUAL trades (`/api/v2/public/get_last_trades_by_instrument_and_time`, also served by
     history.deribit.com, ms stamps, no key);
   - Coinbase BTC-USD trades (`api.exchange.coinbase.com/products/BTC-USD/trades`, paged by trade id);
   - Kraken XBTUSD trades (`/0/public/Trades?since=<ns>`);
   - OKX and Bybit (on disk);
   - Coinbase L2, OKX 400 levels, Bybit 50 levels and the Rabbit ETH file, from RabbitGo777 on 10-20, all on one clock.
2. **Scan each venue.** For each venue, scan accuracy against the cutoff c_v on its own exchange clock (per decision, legs
   at the first-leg instant) and locate knee_v. Add each venue's post-knee window to the proposal-1 model and measure the
   gain.
3. **Scan per trader.** Group the capture's non-operator BUYs by taker wallet (from calldata on the sampled hours) and
   locate each fast wallet's knee.

**Signature if true.**

- One venue's knee lies later than Binance's by about its transit advantage, and it adds at least 1.5 points beyond the
  Binance knee. That venue is the bot's fastest input, and the cutoff is justified physically by it.
- If instead every venue's knee lines up with "Binance + 100-110 ms", the bot reads Binance directly from London. The fast
  crowd wallets with the same knee are its peers on the same route, which closes X101's "unrecorded shared input".

**If false.** No venue is earlier than Binance in the bot's information. The knee is the bot's Binance route, and the
cutoff rests on the measured 105-115 ms transit.

### 4. Follower legs fired on the bot's own acknowledgements: the dispatch route to condition 7 (new; complements X120 and X122)

**Hypothesis.**

- The second gap mode at 180-220 ms is the bot sending the next leg when the previous leg's match or HTTP response comes
  back, about D + RTT later.
- Its inputs are its own fill confirmation and the move since then.
- The wallet that gets the leg is the next free slot in DS → GF → XM.

Then XM's legs, which are the part of condition 7 that no pooled oracle reaches, are a deterministic function of race
outcomes that the capture resolves. A replica that simulates its own fills can assign them.

**Why it fits.**

- Critique 3.
- The fixed leg order (finding 11).
- The refractory of at least 120 ms per wallet (X55).
- The pay-up that rises with leg rank (finding 12): later legs price over the level that earlier legs consume.

**Test.**

1. **When was the follower decided?** On the 2,476 calldata taker orders (10-20 11:00, 10-21 13:00), compare each
   sequential follower's limit with:
   - o's ask at its own arrival - 30 ms;
   - the first leg's limit + k c.

   An ack-loop follower tracks its own-instant ask. A pre-planned follower tracks the first leg.
2. **What triggers it?** Measure P(sequential follower within 150-300 ms) by the previous leg's outcome: fully filled, left
   a remainder (calldata size vs the capture's matched size), or lost.
3. **Which wallet gets it?** Measure P(wallet | earlier legs in flight).
4. **The replica.** Replay the dispatch on the capture with deterministic races. Score XM's per-window net and PnL
   correlation against the oracle ceilings of two13.json.

**Data.** The calldata sample (payrank13), `pm_trades_*` sizes, fills.

**Signature if true.**

- Follower limits sit at their own-instant ask plus the wallet pay-up.
- Followers occur after fills or remainders at a fixed lag.
- Wallet choice follows from in-flight state with at least 0.8 accuracy, against a base rate of 0.61.
- XM's replayed net reaches r ≥ 0.47 with XM's realized net.

**If false.** The legs are pre-planned at the first decision. XM's dispatch stays a measured limit, and the honest XM side
is the per-decision one.

### 5. Audit the presence margin against a capture-aware market baseline (data risk for condition 2)

**Hypothesis.** The capture gives every other trader's print at server ms, a median 2.2 s before its block. A market-only
baseline built on it sees the crowd's co-arrivals: on 10-20 alone, 18,981 non-operator BUYs matched within ±50 ms of an
operator match. It sees them 1-2 s before the block second in which the operator's fill appears. The block-clock baseline
cannot, so the +0.054 margin may belong to the block clock.

**Why it fits.**

- The co-arrival excess (iteration 12, and critique 1 here).
- The margin is thin (DS +0.051).

**Test.**

1. **The baseline.** Refit the block-second market baseline with server-ms features of others' prints on o and on the
   complement, in 100-ms bins over [s - 3.5 s, s - 1 s). Exclude the dossier wallets, W4 and W5 by tx hash.
2. **The full model.** Refit it with the same features plus proposal 1's knee-clock Binance features.
3. **The split.** Both on the same split (10-17..19 → 10-20..22, since BUILD has no capture), with the 2-h block bootstrap.

**Data.** `pm_trades_*` and the existing cells.

**Signature if true.**

- The gain over the ms baseline falls below 0.05. The presence pass then depends on the examiner using the block clock, and
  the account must say so.
- If the knee-clock Binance features restore at least +0.05 over the ms baseline, presence survives a capture-aware
  examiner.

## Checked and not supported (so nobody redoes them)

- **PolyBolt.** `price.crypto` is gated ("about one update per second per symbol"; source pyth or chainlink). It cannot be a
  millisecond trigger. `price.polymarket` (public) is a conflated best bid and ask per token.
- **No new public BUILD-period millisecond capture.** Critique 5 lists what each dataset covers.
- **Size from tick strength.** At the knee, P(large) from |move| has AUC 0.620, against 0.631 at the old clock.
- **Late decisions are not fixed by the clock.** At 180-300 s they stay at 67-75% after re-clocking.

## Sources

- **Hugging Face dataset API**, metadata only:
  - `https://huggingface.co/api/datasets?search=polymarket&sort=lastModified&direction=-1&limit=100`;
  - `/api/datasets/<id>/tree/main?recursive=true` for six datasets (Houroux, trentmkelly, TimeSeventeen, whodisidk,
    polyorderbooks 250ms-l2, marketlens);
  - READMEs of TimeSeventeen/Polymarket-v2, polyorderbooks/polymarket-crypto-btc-5min-250ms-l2 and
    marketlens/polymarket-btc-5m-l2-depth.
- **PolyBolt contract:** `https://ws-live-v2.polymarket.com/asyncapi.json` (HTTP 200, 63,428 bytes, read 10-31 20:29 local
  time).
- **No data from any day at or after H was opened.** File names of later days were not kept.
